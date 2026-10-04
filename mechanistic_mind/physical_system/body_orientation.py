"""Experimental body orientation (theta, omega) + torque from distributed site forces.

DEFAULT OFF. No semantic site roles. No goal angle or steering controls.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.state import PlanetState
from mechanistic_mind.planet.topology import wrap_coord
from mechanistic_mind.physical_system.morphology_mechanics import (
    MorphologyMechanicsConfig,
    ensure_B_site,
    susceptibility,
)
from mechanistic_mind.physical_system.body_deformation import (
    BodyDeformationConfig,
    step_deformation,
)


@dataclass
class BodyOrientationConfig:
    mode: str = "EXPERIMENTAL"  # OFF | EXPERIMENTAL — CURRENT INTEGRATED default; from_dict({}) stays OFF
    inertia: float = 1.0
    angular_drag: float = 0.15
    omega_max: float = 0.35  # numerical stability bound (rad/tick); documented
    force_scale: float = 1.0  # scales site forces for torque/translation when orientation drives morph path
    apply_net_force_to_com: bool = True
    # telemetry: OFF | sampled | event | full
    site_telemetry: str = "sampled"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BodyOrientationConfig":
        # Missing/empty dict = historical PRE-INTEGRATION (OFF). Explicit keys load as given.
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"


def wrap_theta(theta: float) -> float:
    """Wrap to (-pi, pi]."""
    t = float(theta)
    t = (t + np.pi) % (2.0 * np.pi) - np.pi
    if t == -np.pi:
        t = np.pi
    return float(t)


def rotation_matrix(theta: float) -> np.ndarray:
    c, s = float(np.cos(theta)), float(np.sin(theta))
    return np.array([[c, -s], [s, c]], dtype=np.float64)


def body_local_to_world(r_body: np.ndarray, theta: float, center: tuple[float, float]) -> np.ndarray:
    """r_body: (2,) or (N,2) in body-local (x=dx cell, y=dy cell)."""
    R = rotation_matrix(theta)
    r = np.asarray(r_body, dtype=np.float64)
    if r.ndim == 1:
        return np.asarray(center, dtype=np.float64) + R @ r
    return np.asarray(center, dtype=np.float64) + (R @ r.T).T


def world_to_body_local(r_world: np.ndarray, theta: float, center: tuple[float, float]) -> np.ndarray:
    R = rotation_matrix(theta)
    r = np.asarray(r_world, dtype=np.float64) - np.asarray(center, dtype=np.float64)
    if r.ndim == 1:
        return R.T @ r
    return (R.T @ r.T).T


def footprint_body_local(footprint: tuple[tuple[int, int], ...]) -> np.ndarray:
    """Footprint entries are (dy, dx); body-local vectors are (dx, dy)."""
    return np.array([[float(dx), float(dy)] for dy, dx in footprint], dtype=np.float64)


def oriented_site_cells(
    body: PhysicalBodyState,
    width: int,
    height: int,
    footprint: tuple[tuple[int, int], ...],
    *,
    theta: float | None = None,
    r_body: np.ndarray | None = None,
) -> list[tuple[int, int]]:
    """World grid cells for footprint sites. If theta is None, use body.theta when present else 0 with unrotated integer offsets."""
    if theta is None:
        theta = float(getattr(body, "theta", 0.0) or 0.0)
    r_body = footprint_body_local(footprint) if r_body is None else np.asarray(r_body, dtype=np.float64)
    center = (float(body.x), float(body.y))
    worlds = body_local_to_world(r_body, theta, center)
    out = []
    for xw, yw in worlds:
        ix = int(wrap_coord(int(np.floor(xw)), width))
        iy = int(wrap_coord(int(np.floor(yw)), height))
        out.append((iy, ix))
    return out


def site_world_positions(
    body: PhysicalBodyState,
    footprint: tuple[tuple[int, int], ...],
    theta: float,
    r_body: np.ndarray | None = None,
) -> np.ndarray:
    local = footprint_body_local(footprint) if r_body is None else np.asarray(r_body, dtype=np.float64)
    return body_local_to_world(local, theta, (body.x, body.y))


def torque_2d(r: np.ndarray, F: np.ndarray) -> float:
    """Scalar torque tau = r_x F_y - r_y F_x for 2D."""
    return float(r[0] * F[1] - r[1] * F[0])


def step_orientation_mechanics(
    body: PhysicalBodyState,
    planet: PlanetState,
    body_cfg: PhysicalBodyConfig,
    orient_cfg: BodyOrientationConfig,
    morph_cfg: MorphologyMechanicsConfig | None = None,
    deformation_cfg: BodyDeformationConfig | None = None,
    *,
    internal_c: np.ndarray | None = None,
    apply_translation: bool = True,
    work_cfg: Any | None = None,
    work_budget: float | None = None,
    terrain_cfg: Any | None = None,
    ambient_cfg: Any | None = None,
    locomotor_active: bool = False,
    locomotion_profile: Any | None = None,
    locomotion_profile_active: bool = False,
    elevation_runtime_config: Any | None = None,
    elevation_body_id: str | None = None,
    elevation_tick: int | None = None,
) -> dict[str, Any]:
    """Experimental tick: rotated site sampling, local forces, net force + torque, angular update.

    When morphology config enabled, uses B_site susceptibility; otherwise uniform susc=1.
    Mutates body (and optionally planet/internal via material exchange when morph local material ON).
    Terrain (optional): F += -κ∇Φ and CoM drag += coupling·γ_local. External only —
    never credits mechanical_work_reservoir.
    Ambient (optional): F += ambient_fx/fy (static horizontal). External only.
    """
    meta: dict[str, Any] = {"enabled": False}
    if not orient_cfg.enabled:
        return meta

    morph_cfg = morph_cfg or MorphologyMechanicsConfig(mode="OFF")
    h, w = planet.T.shape
    theta = wrap_theta(float(getattr(body, "theta", 0.0)))
    omega = float(getattr(body, "omega", 0.0))
    body.theta = theta
    body.omega = omega

    deformation_cfg = deformation_cfg or BodyDeformationConfig(mode="OFF")
    deformation_meta = step_deformation(
        body,
        body_cfg.footprint,
        deformation_cfg,
        work_cfg,
        env_force_body=getattr(body, "deformation_env_force", None),
        work_budget=work_budget,
    )
    r_body = np.asarray(deformation_meta["actual_geometry"], dtype=np.float64)
    n_sites = len(r_body)
    cells = oriented_site_cells(body, w, h, body_cfg.footprint, theta=theta, r_body=r_body)
    worlds = site_world_positions(body, body_cfg.footprint, theta, r_body=r_body)
    # lever arms in world frame from CoM
    levers = worlds - np.array([body.x, body.y], dtype=np.float64)

    use_morph = bool(morph_cfg.enabled)
    if use_morph:
        B_site = ensure_B_site(body, n_sites)
        # local material exchange at oriented cells
        if morph_cfg.local_material_enabled and body_cfg.material_enabled:
            for si, (iy, ix) in enumerate(cells):
                M_loc = planet.M[:, iy, ix]
                for k, perm in enumerate(body_cfg.permeability):
                    p = float(perm) * float(morph_cfg.permeability_scale)
                    flux = p * (float(M_loc[k]) - float(B_site[si, k]))
                    if flux > 0:
                        flux = min(flux, float(M_loc[k]))
                    else:
                        flux = -min(-flux, float(B_site[si, k]))
                    B_site[si, k] = float(np.clip(B_site[si, k] + flux, 0.0, body_cfg.B_max))
                    if body_cfg.material_backreact and abs(flux) > 0:
                        planet.M[k, iy, ix] = float(max(0.0, float(planet.M[k, iy, ix]) - flux))
        if morph_cfg.internal_site_coupling and internal_c is not None:
            c = np.asarray(internal_c, dtype=np.float64)
            ns = min(n_sites, c.shape[0])
            for i in range(ns):
                for k in range(min(3, c.shape[1])):
                    js = float(morph_cfg.kappa_site) * (float(B_site[i, k]) - float(c[i, k]))
                    c[i, k] = float(c[i, k] + js)
                    B_site[i, k] = float(np.clip(B_site[i, k] - js, 0.0, body_cfg.B_max))
            internal_c[:] = np.clip(c, 0.0, None)
        body.B = np.clip(B_site.mean(axis=0), 0.0, body_cfg.B_max)
        body.B_site = B_site
        strength = float(morph_cfg.strength)
        include_wave = bool(morph_cfg.include_wave)
        site_mech = bool(morph_cfg.site_mechanics_enabled)
    else:
        B_site = None
        strength = 0.0
        include_wave = True
        site_mech = True

    site_forces = []
    Fx = Fy = 0.0
    tau = 0.0
    exposures = []
    terrain_meta: dict[str, Any] = {"enabled": False}
    ambient_meta: dict[str, Any] = {"enabled": False}
    locomotion_receipt: dict[str, Any] | None = None

    if site_mech and body_cfg.mechanical_enabled:
        for si, (iy, ix) in enumerate(cells):
            vx_i = float(planet.vx[iy, ix])
            vy_i = float(planet.vy[iy, ix])
            u_i = float(planet.u[iy, ix])
            T_i = float(planet.T[iy, ix])
            if use_morph and B_site is not None:
                susc = susceptibility(B_site[si], strength)
                B_norm = float(np.linalg.norm(B_site[si]))
            else:
                susc = 1.0
                B_norm = None
            fx = susc * body_cfg.flow_coupling * vx_i * orient_cfg.force_scale
            fy = susc * body_cfg.flow_coupling * vy_i * orient_cfg.force_scale
            if include_wave:
                if abs(vx_i) + abs(vy_i) < 1e-12:
                    wx, wy = 0.0, 0.0
                else:
                    n = float(np.hypot(vx_i, vy_i))
                    wx, wy = vx_i / n, vy_i / n
                fx += susc * 0.15 * body_cfg.wave_coupling * u_i * wx * orient_cfg.force_scale
                fy += susc * 0.15 * body_cfg.wave_coupling * u_i * wy * orient_cfg.force_scale
            Fi = np.array([fx, fy], dtype=np.float64)
            ri = levers[si]
            ti = torque_2d(ri, Fi)
            tau += ti
            Fx += fx
            Fy += fy
            exposures.append({
                "site": si,
                "cell": [iy, ix],
                "world_xy": [float(worlds[si, 0]), float(worlds[si, 1])],
                "r_body": [float(r_body[si, 0]), float(r_body[si, 1])],
                "r_world_lever": [float(ri[0]), float(ri[1])],
                "vx": vx_i, "vy": vy_i, "u": u_i, "T": T_i,
                "susc": susc, "B_norm": B_norm,
                "fx": fx, "fy": fy, "tau_i": ti,
            })
            site_forces.append({"site": si, "fx": fx, "fy": fy, "tau_i": ti, "susc": susc})
        Fx /= max(1, n_sites)
        Fy /= max(1, n_sites)
        # Terrain: potential force + extra dissipative drag (external channel only).
        extra_drag = 0.0
        f_site = (float(Fx), float(Fy))
        f_terrain = (0.0, 0.0)
        f_ambient = (0.0, 0.0)
        if terrain_cfg is not None and bool(getattr(terrain_cfg, "enabled", False)):
            from mechanistic_mind.planet.terrain import sample_terrain_force

            terrain_meta = sample_terrain_force(
                planet,
                cells,
                terrain_cfg=terrain_cfg,
                body_vx=float(body.vx),
                body_vy=float(body.vy),
                locomotor_active=bool(locomotor_active),
            )
            f_terrain = (
                float(terrain_meta.get("fx") or 0.0),
                float(terrain_meta.get("fy") or 0.0),
            )
            extra_drag = float(terrain_meta.get("extra_drag") or 0.0)
        if ambient_cfg is not None and bool(getattr(ambient_cfg, "enabled", False)):
            from mechanistic_mind.planet.ambient import sample_ambient_force

            ambient_meta = sample_ambient_force(
                planet,
                cells,
                ambient_cfg=ambient_cfg,
                body_vx=float(body.vx),
                body_vy=float(body.vy),
                locomotor_active=bool(locomotor_active),
            )
            f_ambient = (
                float(ambient_meta.get("fx") or 0.0),
                float(ambient_meta.get("fy") or 0.0),
            )
        Fx = f_site[0] + f_terrain[0] + f_ambient[0]
        Fy = f_site[1] + f_terrain[1] + f_ambient[1]
        # Body-local site loads for next-tick deformation work / passive env deformation.
        if site_forces:
            F_world = np.array([[sf["fx"], sf["fy"]] for sf in site_forces], dtype=np.float64)
            R = rotation_matrix(theta)
            body.deformation_env_force = (R.T @ F_world.T).T
        locomotion_receipt = None
        # translation from mean site force + drag (+ terrain drag)
        if apply_translation and orient_cfg.apply_net_force_to_com:
            from mechanistic_mind.physical_system.locomotion_profile import integrate_com_translation

            x_before_loco, y_before_loco = float(body.x), float(body.y)
            vx_before_loco, vy_before_loco = float(body.vx), float(body.vy)
            bnlt_ctx = None
            if elevation_runtime_config is not None:
                from mechanistic_mind.physical_system.body_normal_load_traction import (
                    body_normal_load_traction_is_active,
                    prepare_body_coulomb_context,
                )
                if body_normal_load_traction_is_active(elevation_runtime_config):
                    bnlt_ctx = prepare_body_coulomb_context(
                        planet,
                        body,
                        elevation_runtime_config,
                        body_mass=float(body_cfg.mass),
                        body_id=str(elevation_body_id or "body"),
                    )
            locomotion_receipt = integrate_com_translation(
                body,
                body_cfg=body_cfg,
                f_site=f_site,
                f_terrain=f_terrain,
                f_ambient=f_ambient,
                extra_drag=extra_drag,
                locomotor_active=bool(locomotor_active),
                profile=locomotion_profile,
                width=w,
                height=h,
                apply_translation=True,
                profile_active=bool(locomotion_profile_active),
                body_normal_load=bnlt_ctx,
            )
            # Surface elevation support: proposal already applied; gate may revert / debit work.
            from mechanistic_mind.physical_system.surface_elevation_support import (
                surface_elevation_support_active_on_world,
                commit_body_elevation_gate,
            )
            elev = None
            if surface_elevation_support_active_on_world(planet, elevation_runtime_config):
                elev = commit_body_elevation_gate(
                    planet,
                    elevation_runtime_config,
                    body,
                    x0=x_before_loco,
                    y0=y_before_loco,
                    x1=float(body.x),
                    y1=float(body.y),
                    body_id=str(elevation_body_id or "body"),
                    body_mass=float(body_cfg.mass),
                    tick=int(elevation_tick or 0),
                )
                if locomotion_receipt is not None and isinstance(elev, dict):
                    locomotion_receipt["surface_elevation_gate"] = {
                        "accepted": elev.get("accepted"),
                        "event_kinds": elev.get("event_kinds"),
                        "work_debit": elev.get("work_debit"),
                        "block_reason": elev.get("block_reason"),
                    }
                    locomotion_receipt["displacement"] = [
                        float(body.x) - x_before_loco,
                        float(body.y) - y_before_loco,
                    ]

            if bnlt_ctx is not None and locomotion_receipt is not None:
                from mechanistic_mind.physical_system.body_normal_load_traction import (
                    record_body_traction_receipt,
                )
                friction = locomotion_receipt.get("body_normal_load_friction") or {
                    "vx": float(body.vx),
                    "vy": float(body.vy),
                    "applied": False,
                    "mode": bnlt_ctx.get("mode"),
                }
                record_body_traction_receipt(
                    planet,
                    tick=int(elevation_tick or 0),
                    body_id=str(elevation_body_id or "body"),
                    ctx=bnlt_ctx,
                    friction=friction,
                    velocity_before=[vx_before_loco, vy_before_loco],
                    velocity_after=[float(body.vx), float(body.vy)],
                    start_position=[x_before_loco, y_before_loco],
                    end_position=[float(body.x), float(body.y)],
                    gentle_grounded_damping_bypassed=bool(
                        locomotion_receipt.get("gentle_grounded_damping_bypassed")
                    ),
                    gentle_v_stop_bypassed=bool(
                        locomotion_receipt.get("gentle_v_stop_bypassed")
                    ),
                )
                # Coherent slope dynamics work-identity receipt (researcher-only).
                try:
                    from mechanistic_mind.physical_system.coherent_slope_dynamics import (
                        finalize_body_tick_receipt,
                        coherent_slope_dynamics_is_active,
                    )

                    if coherent_slope_dynamics_is_active(elevation_runtime_config):
                        plan = elev if isinstance(elev, dict) else None
                        d_fric = float(friction.get("kinetic_dissipated") or 0.0)
                        static_hold = bool(
                            (friction.get("state_class") == "STATIC_HOLD")
                            or (friction.get("physical_static_hold"))
                        )
                        finalize_body_tick_receipt(
                            planet,
                            elevation_runtime_config,
                            entity_id=str(elevation_body_id or "body"),
                            entity_kind="body",
                            m_eff=float(bnlt_ctx.get("m_eff") or body_cfg.mass),
                            g=float(bnlt_ctx.get("g") or 0.0),
                            vx=float(body.vx),
                            vy=float(body.vy),
                            z=float(getattr(body, "z", 0.0) or 0.0),
                            d_friction=d_fric,
                            w_motor=0.0,
                            endpoint_delta_u=(
                                None if plan is None else plan.get("endpoint_delta_u")
                            ),
                            endpoint_pe_applied=float(
                                0.0 if plan is None else (plan.get("endpoint_pe_applied") or 0.0)
                            ),
                            endpoint_pe_dissipated=float(
                                0.0 if plan is None else (plan.get("endpoint_pe_dissipated") or 0.0)
                            ),
                            slope_meta={
                                "n_hat": bnlt_ctx.get("slope_n_hat"),
                                "g_t_magnitude": bnlt_ctx.get("slope_g_t_magnitude"),
                                "N_projected": bnlt_ctx.get("normal_load_N"),
                                "a_xy": bnlt_ctx.get("slope_a_xy"),
                                "force_meta": locomotion_receipt.get("slope_force_meta"),
                            },
                            static_hold=static_hold,
                        )
                except Exception:
                    pass
                static_res = locomotion_receipt.get("body_static_traction")
                if static_res is not None and bnlt_ctx.get("static_traction_active"):
                    from mechanistic_mind.physical_system.body_static_traction_threshold import (
                        record_static_traction_receipt,
                    )
                    record_static_traction_receipt(
                        planet,
                        tick=int(elevation_tick or 0),
                        body_id=str(elevation_body_id or "body"),
                        result=static_res,
                        velocity_before=[vx_before_loco, vy_before_loco],
                        velocity_after=[float(body.vx), float(body.vy)],
                        start_position=[x_before_loco, y_before_loco],
                        end_position=[float(body.x), float(body.y)],
                        gentle_grounded_damping_bypassed=bool(
                            locomotion_receipt.get("gentle_grounded_damping_bypassed")
                        ),
                        gentle_v_stop_bypassed=bool(
                            locomotion_receipt.get("gentle_v_stop_bypassed")
                        ),
                    )
                # Beta 4 MOVE breakaway repair receipt + clear tick stamp.
                try:
                    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
                        bnlt_move_breakaway_locomotion_repair_is_active,
                        classify_active_move_outcome,
                        clear_move_impulse_on_body,
                        record_repair_step,
                        read_move_impulse_xy,
                        RECEIPT_KIND as _REPAIR_RECEIPT,
                        BANNER as _REPAIR_BANNER,
                        MECHANISM_ID as _REPAIR_ID,
                        PROFILE_VERSION as _REPAIR_PROFILE,
                    )
                    import math as _math

                    if bnlt_move_breakaway_locomotion_repair_is_active(elevation_runtime_config):
                        static_meta = locomotion_receipt.get("body_static_traction") or {}
                        fric_meta = locomotion_receipt.get("body_normal_load_friction") or {}
                        dx = float(body.x) - float(x_before_loco)
                        dy = float(body.y) - float(y_before_loco)
                        disp = float(_math.hypot(dx, dy))
                        j_move = read_move_impulse_xy(body)
                        cls = classify_active_move_outcome(
                            locomotor_active=bool(locomotor_active),
                            grounded=bool(bnlt_ctx.get("grounded")),
                            external_ineligible=False,
                            displacement_mag=disp,
                            speed_after=float(_math.hypot(float(body.vx), float(body.vy))),
                            drive_accel=static_meta.get("move_breakaway_repair_drive_accel")
                            or static_meta.get("drive_accel"),
                            friction_a=static_meta.get("a") or fric_meta.get("a"),
                            rest_transition=bool(
                                static_meta.get("rest_transition")
                                or fric_meta.get("rest_transition")
                            ),
                            state_class=str(
                                static_meta.get("state_class")
                                or static_meta.get("mode")
                                or ""
                            ),
                        )
                        record_repair_step(
                            planet,
                            elevation_runtime_config,
                            receipt={
                                "receipt_kind": _REPAIR_RECEIPT,
                                "mechanism": _REPAIR_ID,
                                "profile_version": _REPAIR_PROFILE,
                                "banner": _REPAIR_BANNER,
                                "tick": int(elevation_tick or 0),
                                "body_id": str(elevation_body_id or "body"),
                                "classification": cls,
                                "move_impulse_xy": [float(j_move[0]), float(j_move[1])],
                                "drive_accel": static_meta.get("drive_accel"),
                                "repair_drive_accel": static_meta.get(
                                    "move_breakaway_repair_drive_accel"
                                ),
                                "legacy_trial_speed_drive_proxy": static_meta.get(
                                    "legacy_trial_speed_drive_proxy"
                                ),
                                "kinetic_a": static_meta.get("a") or fric_meta.get("a"),
                                "velocity_before": [vx_before_loco, vy_before_loco],
                                "velocity_after": [float(body.vx), float(body.vy)],
                                "displacement": [dx, dy],
                                "displacement_mag": disp,
                                "rest_transition": bool(
                                    static_meta.get("rest_transition")
                                    or fric_meta.get("rest_transition")
                                ),
                                "kinetic_dissipated": float(
                                    static_meta.get("kinetic_dissipated")
                                    or fric_meta.get("kinetic_dissipated")
                                    or 0.0
                                ),
                                "researcher_only": True,
                                "agent_accessible": False,
                            },
                        )
                        clear_move_impulse_on_body(body)
                except Exception:
                    pass
                # Beta 4 active locomotion traction vs sliding friction receipt.
                try:
                    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
                        active_locomotion_traction_vs_sliding_friction_is_active,
                        record_traction_vs_sliding_step,
                        RECEIPT_KIND as _TVS_RECEIPT,
                        BANNER as _TVS_BANNER,
                        MECHANISM_ID as _TVS_ID,
                        PROFILE_VERSION as _TVS_PROFILE,
                    )
                    import math as _math_tvs

                    if active_locomotion_traction_vs_sliding_friction_is_active(
                        elevation_runtime_config
                    ):
                        static_meta = locomotion_receipt.get("body_static_traction") or {}
                        if static_meta.get(
                            "active_locomotion_traction_vs_sliding_friction_active"
                        ):
                            dx = float(body.x) - float(x_before_loco)
                            dy = float(body.y) - float(y_before_loco)
                            record_traction_vs_sliding_step(
                                planet,
                                elevation_runtime_config,
                                receipt={
                                    "receipt_kind": _TVS_RECEIPT,
                                    "mechanism": _TVS_ID,
                                    "profile_version": _TVS_PROFILE,
                                    "banner": _TVS_BANNER,
                                    "tick": int(elevation_tick or 0),
                                    "body_id": str(elevation_body_id or "body"),
                                    "locomotor_active": bool(locomotor_active),
                                    "traction_protection_applied": bool(
                                        static_meta.get("traction_protection_applied")
                                    ),
                                    "full_drive_protected": bool(
                                        static_meta.get("full_drive_protected")
                                    ),
                                    "protected_mag": static_meta.get("protected_mag"),
                                    "slip_speed_before": static_meta.get("slip_speed_before"),
                                    "slip_speed_after": static_meta.get("slip_speed_after"),
                                    "speed_after": static_meta.get("speed_after"),
                                    "displacement_mag": float(_math_tvs.hypot(dx, dy)),
                                    "velocity_after": [float(body.vx), float(body.vy)],
                                    "researcher_only": True,
                                    "agent_accessible": False,
                                },
                            )
                except Exception:
                    pass

    # angular dynamics: I alpha = tau - c omega
    I = max(1e-9, float(orient_cfg.inertia))
    alpha = (tau - float(orient_cfg.angular_drag) * omega) / I
    omega = float(omega + alpha)
    omega = float(np.clip(omega, -orient_cfg.omega_max, orient_cfg.omega_max))
    theta = wrap_theta(theta + omega)
    body.omega = omega
    body.theta = theta

    meta.update({
        "enabled": True,
        "n_sites": n_sites,
        "theta": theta,
        "omega": omega,
        "alpha": alpha,
        "tau": tau,
        "net_force": [Fx, Fy],
        "site_forces": site_forces if orient_cfg.site_telemetry != "OFF" else [],
        "exposures": exposures if orient_cfg.site_telemetry in ("sampled", "event", "full") else [],
        "morphology_used": use_morph,
        "omega_max": orient_cfg.omega_max,
        "angular_drag": orient_cfg.angular_drag,
        "inertia": orient_cfg.inertia,
        "deformation": deformation_meta,
        "terrain": terrain_meta,
        "ambient": ambient_meta,
        "locomotion": locomotion_receipt,
    })
    if use_morph and B_site is not None:
        meta["B_site_spread"] = float(np.std([np.linalg.norm(B_site[i]) for i in range(n_sites)]))
    return meta
