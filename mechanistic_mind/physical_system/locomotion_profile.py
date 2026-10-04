"""Acanthostega-only grounded CoM integration profile.

Tiktaalik uses the historical equations when this profile is inactive.
Φ remains a scalar potential — not geometric height.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

import numpy as np

from mechanistic_mind.planet.topology import wrap_coord
from mechanistic_mind.physical_system.resource_objects import (
    PHYSICAL_RESOURCE_OBJECTS,
    PHYSICAL_RESOURCE_OBJECT_VISION,
)
from mechanistic_mind.physical_system.physical_manipulator import (
    BILATERAL_GRASP_RELEASE,
    BILATERAL_PHYSICAL_MANIPULATORS,
    BILATERAL_BRING_TOGETHER,
    PHYSICAL_GRASP_RELEASE,
    SINGLE_PHYSICAL_MANIPULATOR,
)

PROFILE_TIKTAALIK = "TIKTAALIK"
PROFILE_ACANTHOSTEGA_GENTLE = "ACANTHOSTEGA_GENTLE"
GENTLE_TERRAIN_LOCOMOTION = "gentle_terrain_locomotion"
ACANTHOSTEGA_ONLY_MECHANISM_IDS = frozenset({
    GENTLE_TERRAIN_LOCOMOTION,
    PHYSICAL_RESOURCE_OBJECTS,
    PHYSICAL_RESOURCE_OBJECT_VISION,
    SINGLE_PHYSICAL_MANIPULATOR,
    PHYSICAL_GRASP_RELEASE,
    BILATERAL_PHYSICAL_MANIPULATORS,
    BILATERAL_GRASP_RELEASE,
    BILATERAL_BRING_TOGETHER,
    "passive_material_properties",
    "explicit_surface_deposition",
    "surface_affinity_traction",
    "surface_traction_experience_bridge",
    "surface_traction_prediction_adaptation",
    "physical_surface_optical_coating",
    "world_material_transactions",
    "multi_content_spatial_index",
    "procedural_surface_columns",
    "conservative_surface_column_transfer",
    "local_physical_signal_transport",
    "physical_contact_acoustic_emission",
    "free_resource_object_kinematics",
    "physical_body_resource_object_contact",
    "body_resource_object_contact_impulse",
    "body_resource_object_impact_acoustic_emission",
    "physical_resource_object_pair_contact",
    "resource_object_pair_contact_impulse",
    "resource_object_pair_impact_acoustic_emission",
    "held_resource_object_foreign_body_contact",
    "body_normal_load_traction",
    "continuous_surface_geometry",
    "body_static_traction_threshold",
    "held_resource_object_terrain_contact_geometry",
    "held_resource_object_terrain_mechanical_transmission",
    "held_mediated_surface_exertion_integration",
    "detached_terrain_material_initial_placement",
    "bnlt_move_breakaway_locomotion_repair",
    "repeated_conservative_surface_column_separation",
    "active_locomotion_traction_vs_sliding_friction",
    "event_driven_crowded_placement_retry_contract",
    "detached_material_amount_scaled_collision_radius",
    "held_combine_radius_resize_transaction",
    "held_deposition_radius_shrink_transaction",
    "free_space_state_and_pe_authority_contract",
    "vertical_terrain_landing_contact_response",
    "effector_bounded_actuator_effort",
    "surface_exertion_terrain_material_resistance",
    "effector_terrain_contact_geometry",
    "manipulator_relative_world_actuation",
    "conservative_surface_material_separation",
})


@dataclass
class LocomotionPhysicsProfile:
    """Ground-support knobs. Unused unless enabled on an Acanthostega config."""

    name: str = PROFILE_TIKTAALIK
    enabled: bool = False
    # Scale applied to flow/site + Φ + ambient before traction (WAIT vs MOVE).
    env_force_scale_wait: float = 0.08
    env_force_scale_move: float = 0.55
    # Absorb passive env force up to this magnitude when locomotor is inactive.
    traction_threshold: float = 0.012
    # Extra linear damping −c v when locomotor is inactive (cells/tick units as body.drag).
    grounded_damping: float = 0.85
    # Snap residual speed to 0 after damping when locomotor is inactive.
    v_stop_threshold: float = 0.006
    # Scale Φ force only (not geometric slope). 1.0 = Tiktaalik κ coupling.
    potential_force_scale: float = 0.35

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "LocomotionPhysicsProfile":
        if not data:
            return tiktaalik_locomotion_profile()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        return cls(**payload)

    @property
    def active_name(self) -> str:
        if self.enabled and str(self.name).upper() == PROFILE_ACANTHOSTEGA_GENTLE:
            return PROFILE_ACANTHOSTEGA_GENTLE
        return PROFILE_TIKTAALIK


def tiktaalik_locomotion_profile() -> LocomotionPhysicsProfile:
    return LocomotionPhysicsProfile(name=PROFILE_TIKTAALIK, enabled=False)


def acanthostega_gentle_locomotion_profile() -> LocomotionPhysicsProfile:
    return LocomotionPhysicsProfile(
        name=PROFILE_ACANTHOSTEGA_GENTLE,
        enabled=True,
    )


def gentle_mechanism_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": GENTLE_TERRAIN_LOCOMOTION,
        "config_path": "locomotion_profile.enabled",
        "label": "GENTLE TERRAIN LOCOMOTION",
        "description": (
            "Acanthostega-only grounded CoM coupling: absorb weak passive "
            "environmental force at rest; do not treat Φ as height."
        ),
        "validation": "Acanthostega Phase A gentle locomotion profile.",
        "provenance": "acanthostega_gentle_locomotion",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "PHYSICAL",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "dependencies": [],
        "toggle_policy": "RESET_RECOMMENDED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key preserves Tiktaalik / Phase 0 physics",
        "live_state_available": True,
        "receipts_available": True,
        "events_available": False,
    }


def profile_is_active(config: Any) -> bool:
    if config is None:
        return False
    if str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    prof = getattr(config, "locomotion_profile", None)
    if prof is None:
        return False
    return bool(getattr(prof, "enabled", False)) and str(
        getattr(prof, "name", "")
    ).upper() == PROFILE_ACANTHOSTEGA_GENTLE


def set_gentle_terrain_locomotion(config: Any, enabled: bool) -> None:
    """Enable only on Acanthostega. OFF restores compatible Tiktaalik CoM equations."""
    on = bool(enabled)
    line = str(getattr(config, "model_line", "") or "").upper()
    if on and line == "ACANTHOSTEGA":
        config.locomotion_profile = acanthostega_gentle_locomotion_profile()
    else:
        config.locomotion_profile = tiktaalik_locomotion_profile()


def integrate_com_translation(
    body: Any,
    *,
    body_cfg: Any,
    f_site: tuple[float, float],
    f_terrain: tuple[float, float],
    f_ambient: tuple[float, float],
    extra_drag: float,
    locomotor_active: bool,
    profile: LocomotionPhysicsProfile | None,
    width: int,
    height: int,
    apply_translation: bool,
    profile_active: bool,
    body_normal_load: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """CoM force composition + Euler step. Inactive profile is bit-compatible with Tiktaalik.

    When body_normal_load is active: bypass Gentle grounded_damping + v_stop; keep env absorb;
    apply Coulomb kinetic friction after force integrate and before position (FOGF order).
    """
    vx0 = float(body.vx)
    vy0 = float(body.vy)
    fsx, fsy = float(f_site[0]), float(f_site[1])
    ftx, fty = float(f_terrain[0]), float(f_terrain[1])
    fax, fay = float(f_ambient[0]), float(f_ambient[1])
    mass = float(body_cfg.mass)
    v_max = float(body_cfg.v_max)
    base_drag = float(body_cfg.drag)
    extra = max(0.0, float(extra_drag))

    support = [0.0, 0.0]
    env_scale = 1.0
    phi_scale = 1.0
    grounded = 0.0
    snapped = False
    slope_force_meta = None
    bnlt = body_normal_load if isinstance(body_normal_load, dict) and body_normal_load.get("active") else None
    bypass_gentle_vel = bool(bnlt and bnlt.get("bypass_gentle_grounded_damping"))

    if profile_active and profile is not None:
        env_scale = float(
            profile.env_force_scale_move if locomotor_active else profile.env_force_scale_wait
        )
        phi_scale = float(profile.potential_force_scale)
        f_phi_x, f_phi_y = phi_scale * ftx, phi_scale * fty
        f_pass_x = env_scale * (fsx + fax + f_phi_x)
        f_pass_y = env_scale * (fsy + fay + f_phi_y)
        if not locomotor_active:
            mag = float(np.hypot(f_pass_x, f_pass_y))
            thr = max(0.0, float(profile.traction_threshold))
            if mag <= thr:
                support = [-f_pass_x, -f_pass_y]
            elif mag > 1e-15:
                u = thr / mag
                support = [-u * f_pass_x, -u * f_pass_y]
            # BNLT: never stack Gentle grounded_damping with body Coulomb.
            if not bypass_gentle_vel:
                grounded = max(0.0, float(profile.grounded_damping))
        fx = f_pass_x + support[0]
        fy = f_pass_y + support[1]
        # Coherent slope dynamics: inject F_gt AFTER absorb (single seam).
        slope_force_meta = None
        if bnlt is not None:
            try:
                from mechanistic_mind.physical_system.coherent_slope_dynamics import (
                    compose_slope_force_into_horizontal,
                )

                fx, fy, slope_force_meta = compose_slope_force_into_horizontal(fx, fy, bnlt)
            except Exception:
                slope_force_meta = None
        drag_eff = base_drag + extra + grounded
    else:
        f_phi_x, f_phi_y = ftx, fty
        f_pass_x = fsx + fax + ftx
        f_pass_y = fsy + fay + fty
        fx, fy = f_pass_x, f_pass_y
        drag_eff = base_drag + extra
        slope_force_meta = None

    fx_t = fx - drag_eff * vx0
    fy_t = fy - drag_eff * vy0
    vx1 = float(np.clip(vx0 + fx_t / mass, -v_max, v_max))
    vy1 = float(np.clip(vy0 + fy_t / mass, -v_max, v_max))

    friction_meta: dict[str, Any] | None = None
    static_meta: dict[str, Any] | None = None
    if bnlt is not None:
        # Pre-integration demand ledger (forces already composed; v not yet committed).
        f_pass_ledger_x = float(fx)  # after absorb/support, before drag term separation
        f_pass_ledger_y = float(fy)
        # Reconstruct passive env (without drag): fx,fy already exclude -drag*v
        grace = int(getattr(body, "_boc_impulse_grace_ticks", 0) or 0)
        external_ineligible = grace > 0
        if external_ineligible:
            try:
                body._boc_impulse_grace_ticks = grace - 1
            except Exception:
                pass
        static_on = bool(bnlt.get("static_traction_active"))
        if static_on:
            from mechanistic_mind.physical_system.body_static_traction_threshold import (
                apply_static_then_kinetic,
                build_pre_integration_demand_ledger,
            )
            # Prefer tick-stamped capacity-limited MOVE impulse (repair / demand ledger).
            move_j = tuple(bnlt.get("move_impulse_xy") or (0.0, 0.0))
            if (abs(move_j[0]) + abs(move_j[1])) <= 1e-18:
                try:
                    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
                        read_move_impulse_xy,
                    )

                    move_j = read_move_impulse_xy(body)
                    if (abs(move_j[0]) + abs(move_j[1])) > 1e-18:
                        bnlt = {**bnlt, "move_impulse_xy": move_j}
                except Exception:
                    pass
            demand = build_pre_integration_demand_ledger(
                vx0=vx0,
                vy0=vy0,
                f_pass_x=f_pass_ledger_x,
                f_pass_y=f_pass_ledger_y,
                m_eff=float(bnlt.get("m_eff") or mass),
                dt=float(bnlt.get("dt") or 1.0),
                locomotor_active=bool(locomotor_active),
                grounded=bool(bnlt.get("grounded")),
                external_impulse_ineligible=bool(external_ineligible),
                mu_static=bnlt.get("mu_static"),
                normal_load_N=bnlt.get("normal_load_N"),
                move_impulse_xy=move_j,
            )
            static_cfg = bnlt.get("static_config")
            static_meta = apply_static_then_kinetic(
                vx1,
                vy1,
                bnlt_ctx=bnlt,
                static_cfg=static_cfg,
                locomotor_active=bool(locomotor_active),
                external_impulse_ineligible=bool(external_ineligible),
                demand_ledger=demand,
            )
            vx1 = float(static_meta["vx"])
            vy1 = float(static_meta["vy"])
            # Map into BNLT friction_meta shape for existing receipt path + extras.
            friction_meta = {
                "vx": vx1,
                "vy": vy1,
                "applied": bool(static_meta.get("applied")),
                "mode": static_meta.get("mode"),
                "state_class": static_meta.get("state_class"),
                "mu_k": static_meta.get("mu_k"),
                "mu_static": static_meta.get("mu_static"),
                "a": static_meta.get("a"),
                "dv": static_meta.get("dv"),
                "speed_before": static_meta.get("speed_before"),
                "speed_after": static_meta.get("speed_after"),
                "kinetic_before": static_meta.get("kinetic_before"),
                "kinetic_after": static_meta.get("kinetic_after"),
                "kinetic_dissipated": static_meta.get("kinetic_dissipated", 0.0),
                "rest_transition": bool(static_meta.get("rest_transition")),
                "stopped_by_friction": bool(static_meta.get("rest_transition")),
                "normal_load_N": static_meta.get("normal_load_N"),
                "m_eff": static_meta.get("m_eff"),
                "held_mass": bnlt.get("held_mass"),
                "mass_independent_a": True,
                "gentle_bypassed": True,
                "surface_affinity": bnlt.get("surface_affinity"),
                "cell_x": bnlt.get("cell_x"),
                "cell_y": bnlt.get("cell_y"),
                "deposit_id": bnlt.get("deposit_id"),
                "deposit_present": bnlt.get("deposit_present"),
                "physical_static_hold": static_meta.get("physical_static_hold"),
                "numerical_zero_normalization": static_meta.get("numerical_zero_normalization"),
                "kinetic_applied": static_meta.get("kinetic_applied"),
                "j_static_max": static_meta.get("j_static_max"),
                "j_hold_mag": static_meta.get("j_hold_mag"),
                "j_static": static_meta.get("j_static"),
                "static_work": static_meta.get("static_work", 0.0),
                "demand_ledger": static_meta.get("demand_ledger"),
                "eligibility_reason": static_meta.get("eligibility_reason"),
                "static_traction": static_meta,
            }
        else:
            from mechanistic_mind.physical_system.body_normal_load_traction import (
                apply_body_coulomb_to_velocity,
            )
            friction_meta = apply_body_coulomb_to_velocity(vx1, vy1, bnlt)
            vx1 = float(friction_meta["vx"])
            vy1 = float(friction_meta["vy"])
        # Coulomb / static owns rest; never apply Gentle v_stop when BNLT ON.
        snapped = False
    elif profile_active and profile is not None and not locomotor_active:
        grace = int(getattr(body, "_boc_impulse_grace_ticks", 0) or 0)
        if grace > 0:
            try:
                body._boc_impulse_grace_ticks = grace - 1
            except Exception:
                pass
        elif float(np.hypot(vx1, vy1)) < float(profile.v_stop_threshold):
            vx1, vy1 = 0.0, 0.0
            snapped = True

    x0, y0 = float(body.x), float(body.y)
    if apply_translation:
        body.vx = vx1
        body.vy = vy1
        if body_cfg.displacement_enabled:
            body.x = float(wrap_coord(body.x + body.vx, width))
            body.y = float(wrap_coord(body.y + body.vy, height))

    out = {
        "locomotion_profile": (
            PROFILE_ACANTHOSTEGA_GENTLE
            if profile_active
            else PROFILE_TIKTAALIK
        ),
        "gentle_terrain_locomotion": bool(profile_active),
        "locomotor_active": bool(locomotor_active),
        "self_force": [0.0, 0.0],
        "environment_force": [fsx + fax, fsy + fay],
        "potential_force": [float(f_phi_x), float(f_phi_y)],
        "support_force": [float(support[0]), float(support[1])],
        "env_force_scale": float(env_scale),
        "potential_force_scale": float(phi_scale),
        "drag_eff": float(drag_eff),
        "grounded_damping": float(grounded),
        "velocity_before": [vx0, vy0],
        "velocity_after": [float(body.vx), float(body.vy)],
        "velocity_delta": [float(body.vx) - vx0, float(body.vy) - vy0],
        "displacement": [float(body.x) - x0, float(body.y) - y0],
        "v_stop_applied": bool(snapped),
        "contact_force": [0.0, 0.0],
        "push_force": [0.0, 0.0],
        "slope_force_meta": slope_force_meta,
    }
    # Omit BNLT receipt keys when inactive so pre-BNLT / Tiktaalik snapshot
    # hashes stay bit-identical (inactive profile is bit-compatible).
    if bnlt is not None:
        out["gentle_grounded_damping_bypassed"] = bool(bypass_gentle_vel)
        out["gentle_v_stop_bypassed"] = True
        out["body_normal_load_active"] = True
    if friction_meta is not None:
        out["body_normal_load_friction"] = friction_meta
        out["body_normal_load_ctx"] = {
            k: bnlt.get(k)
            for k in (
                "mode", "grounded", "mu_k", "mu_static", "normal_load_N", "m_eff", "held_mass",
                "g", "surface_affinity", "cell_x", "cell_y", "apply_coulomb",
                "static_traction_active",
            )
        }
    if static_meta is not None:
        out["body_static_traction"] = static_meta
    return out


def apply_ground_rest_after_self_drive(
    body: Any,
    *,
    body_cfg: Any,
    profile: LocomotionPhysicsProfile | None,
    profile_active: bool,
    locomotor_active: bool,
    bypass_gentle_v_stop: bool = False,
) -> dict[str, Any] | None:
    """After endogenous Δv (no extra x+=v). Does not run on Tiktaalik or during MOVE.

    When body normal-load traction is ON, Gentle v_stop is bypassed (Coulomb owns rest).
    """
    if bypass_gentle_v_stop:
        return {
            "velocity_before": [float(body.vx), float(body.vy)],
            "velocity_after": [float(body.vx), float(body.vy)],
            "v_stop_applied": False,
            "gentle_v_stop_bypassed": True,
            "body_normal_load_active": True,
        }
    if not profile_active or profile is None or locomotor_active:
        return None
    vx0, vy0 = float(body.vx), float(body.vy)
    snapped = False
    vx1, vy1 = vx0, vy0
    grace = int(getattr(body, "_boc_impulse_grace_ticks", 0) or 0)
    if grace > 0:
        # Grace is decremented in integrate_com_translation (one skip per tick).
        pass
    elif float(np.hypot(vx0, vy0)) < float(profile.v_stop_threshold):
        vx1, vy1 = 0.0, 0.0
        snapped = True
        body.vx, body.vy = vx1, vy1
    return {
        "velocity_before": [vx0, vy0],
        "velocity_after": [vx1, vy1],
        "v_stop_applied": snapped,
    }
