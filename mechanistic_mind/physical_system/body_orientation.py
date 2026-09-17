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
) -> dict[str, Any]:
    """Experimental tick: rotated site sampling, local forces, net force + torque, angular update.

    When morphology config enabled, uses B_site susceptibility; otherwise uniform susc=1.
    Mutates body (and optionally planet/internal via material exchange when morph local material ON).
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
        # Body-local site loads for next-tick deformation work / passive env deformation.
        if site_forces:
            F_world = np.array([[sf["fx"], sf["fy"]] for sf in site_forces], dtype=np.float64)
            R = rotation_matrix(theta)
            body.deformation_env_force = (R.T @ F_world.T).T
        # translation from mean site force + drag
        if apply_translation and orient_cfg.apply_net_force_to_com:
            Fx_t = Fx - body_cfg.drag * body.vx
            Fy_t = Fy - body_cfg.drag * body.vy
            body.vx = float(np.clip(body.vx + Fx_t / body_cfg.mass, -body_cfg.v_max, body_cfg.v_max))
            body.vy = float(np.clip(body.vy + Fy_t / body_cfg.mass, -body_cfg.v_max, body_cfg.v_max))
            if body_cfg.displacement_enabled:
                body.x = float(wrap_coord(body.x + body.vx, w))
                body.y = float(wrap_coord(body.y + body.vy, h))

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
    })
    if use_morph and B_site is not None:
        meta["B_site_spread"] = float(np.std([np.linalg.norm(B_site[i]) for i in range(n_sites)]))
    return meta
