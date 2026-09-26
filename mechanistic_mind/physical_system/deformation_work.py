"""Finite mechanical work reservoir for body-local deformation.

This is an explicit abstract mechanical work reservoir, not metabolism.
Overdamped site mechanics:

    γ v = F_act + F_env_radial − k d

with U = ½ k Σ‖d‖² (linear restoring force about the existing rest footprint).
When F_env = 0 and F_act is chosen to match the established kinematic tracker,
v = (k/γ)(target − d) with k/γ = relaxation — same geometry as work-OFF kinematics.

Work identity (dt = 1 tick):
    W_act + W_env = ΔU + W_viscous + residual
where W_viscous = γ Σ‖v‖² and residual captures clips / projection.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.physical_system.body_deformation import (
    BodyDeformationConfig,
    ensure_deformation,
    radial_axes,
    rest_geometry,
)


@dataclass
class DeformationWorkConfig:
    """Independent of body_deformation.mode. Historical missing key → OFF."""

    mode: str = "EXPERIMENTAL"
    transfer_enabled: bool = True  # reservoir ↔ actuator work (ablation edge)
    actuator_enabled: bool = True  # internally powered F_act
    env_deform_enabled: bool = True  # F_env can change shape without reservoir
    stiffness: float = 1.0
    # If None, viscous_coeff = stiffness / relaxation so unlimited-work kinematics match.
    viscous_coeff: float | None = None
    reservoir_max: float = 4.0
    reservoir_init: float = 2.0
    recovery_to_reservoir: bool = True
    # BODY-01: optional passive reservoir trickle (work units / tick). Default 0
    # preserves historical snapshots (missing key → 0). Not experimenter supply.
    passive_reservoir_trickle: float = 0.0

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DeformationWorkConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def deformation_potential(d: np.ndarray, stiffness: float) -> float:
    d = np.asarray(d, dtype=np.float64)
    return 0.5 * float(stiffness) * float(np.sum(d * d))


def kinetic_energy(body: PhysicalBodyState, mass: float, inertia: float) -> float:
    v2 = float(body.vx) ** 2 + float(body.vy) ** 2
    w2 = float(getattr(body, "omega", 0.0) or 0.0) ** 2
    return 0.5 * float(mass) * v2 + 0.5 * float(inertia) * w2


def drag_dissipation(vx: float, vy: float, omega: float, drag: float, angular_drag: float) -> float:
    """Known CoM/spin sinks this tick under linear drag, dt=1: F_drag·v = drag‖v‖²."""
    return float(drag) * (float(vx) ** 2 + float(vy) ** 2) + float(angular_drag) * (float(omega) ** 2)


def ensure_reservoir(body: PhysicalBodyState, cfg: DeformationWorkConfig) -> float:
    w = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
    if cfg.enabled:
        w = min(max(0.0, w), float(cfg.reservoir_max))
    body.mechanical_work_reservoir = w
    return w


def _env_radial(env_force_body: np.ndarray | None, axes: np.ndarray, n: int, enabled: bool) -> np.ndarray:
    F = np.zeros((n, 2), dtype=np.float64)
    if not enabled or env_force_body is None:
        return F
    raw = np.asarray(env_force_body, dtype=np.float64)
    if raw.shape != (n, 2):
        return F
    # Only the radial DOF exists in the established deformer.
    proj = np.sum(raw * axes, axis=1, keepdims=True)
    return axes * proj


def _rate_limit(delta: np.ndarray, max_rate: float) -> np.ndarray:
    lengths = np.linalg.norm(delta, axis=1)
    scale = np.ones_like(lengths)
    nz = lengths > max_rate
    scale[nz] = max_rate / lengths[nz]
    return delta * scale[:, None]


def _clip_displacement(d: np.ndarray, max_disp: float) -> np.ndarray:
    mag = np.linalg.norm(d, axis=1)
    over = mag > max_disp
    if np.any(over):
        d = d.copy()
        d[over] *= (max_disp / mag[over])[:, None]
    return d


def _solve_actuator_scale(a: float, b: float, w_avail: float, w1: float) -> float:
    """s in [0,1] such that W(s)=a s^2 + b s does not exceed w_avail when W(1)>0."""
    if w1 <= 1e-15:
        return 1.0
    if w_avail <= 1e-15:
        return 0.0
    if w1 <= w_avail + 1e-15:
        return 1.0
    # a s^2 + b s - w_avail = 0; take root in [0,1]
    if abs(a) < 1e-18:
        if abs(b) < 1e-18:
            return 1.0
        s = w_avail / b
        return float(np.clip(s, 0.0, 1.0))
    disc = b * b + 4.0 * a * w_avail
    if disc < 0.0:
        return 0.0
    s = (-b + np.sqrt(disc)) / (2.0 * a)
    return float(np.clip(s, 0.0, 1.0))


def empty_work_ledger() -> dict[str, Any]:
    return {
        "mechanical_energy_accounting": "NOT DEMONSTRATED",
        "work_transfer_enabled": False,
        "reservoir_before": 0.0,
        "reservoir_after": 0.0,
        "reservoir_work_supplied": 0.0,
        "actuator_work": 0.0,
        "env_work_on_deformation": 0.0,
        "delta_potential": 0.0,
        "potential_before": 0.0,
        "potential_after": 0.0,
        "dissipated_viscous": 0.0,
        "deformation_residual": 0.0,
        "actuator_scale": 1.0,
        "work_limited": False,
        "reservoir_depleted": False,
        "shape_change_source": "NONE",
        "where_did_the_work_come_from": [],
    }


def _deformation_w1(
    body: PhysicalBodyState,
    footprint: tuple[tuple[int, int], ...],
    deform_cfg: BodyDeformationConfig,
    work_cfg: DeformationWorkConfig,
    *,
    env_force_body: np.ndarray | None = None,
) -> float:
    """Positive unconstrained actuator work request W(1); does not mutate body."""
    rest = rest_geometry(footprint)
    d = ensure_deformation(body, len(rest)).copy()
    axes = radial_axes(rest)
    n = len(rest)
    B_site = getattr(body, "B_site", None)
    norms = (
        np.linalg.norm(np.asarray(B_site, dtype=np.float64), axis=1)
        if B_site is not None and np.asarray(B_site).shape[0] == n
        else np.full(n, float(deform_cfg.neutral_B_norm), dtype=np.float64)
    )
    if not (deform_cfg.enabled and work_cfg.enabled and work_cfg.transfer_enabled and work_cfg.actuator_enabled and deform_cfg.material_drive_enabled):
        return 0.0
    scalar_target = np.clip(
        deform_cfg.material_gain * (norms - float(deform_cfg.neutral_B_norm)),
        -deform_cfg.max_displacement,
        deform_cfg.max_displacement,
    )
    target = axes * scalar_target[:, None]
    relax = max(0.0, min(1.0, float(deform_cfg.relaxation)))
    v_kin = _rate_limit((target - d) * relax, deform_cfg.max_rate)
    k = float(work_cfg.stiffness)
    gamma = float(work_cfg.viscous_coeff) if work_cfg.viscous_coeff is not None else (k / max(relax, 1e-9))
    gamma = max(gamma, 1e-9)
    env_on = bool(work_cfg.env_deform_enabled)
    F_env = _env_radial(
        env_force_body if env_force_body is not None else getattr(body, "deformation_env_force", None),
        axes, n, env_on,
    )
    v_p = _rate_limit((F_env - k * d) / gamma, deform_cfg.max_rate)
    dv = v_kin - v_p
    w1 = float(gamma * np.sum(dv * dv) + gamma * np.sum(dv * v_p))
    return max(0.0, w1)


def preview_positive_actuator_work(
    body: PhysicalBodyState,
    footprint: tuple[tuple[int, int], ...],
    deform_cfg: BodyDeformationConfig,
    work_cfg: DeformationWorkConfig,
    *,
    env_force_body: np.ndarray | None = None,
) -> float:
    return _deformation_w1(body, footprint, deform_cfg, work_cfg, env_force_body=env_force_body)


def apply_deformation_work(
    body: PhysicalBodyState,
    footprint: tuple[tuple[int, int], ...],
    deform_cfg: BodyDeformationConfig,
    work_cfg: DeformationWorkConfig,
    *,
    env_force_body: np.ndarray | None = None,
    work_budget: float | None = None,
) -> dict[str, Any]:
    """Advance deformation with optional finite work accounting. Never writes CoM/theta/omega."""
    rest = rest_geometry(footprint)
    d = ensure_deformation(body, len(rest))
    before = d.copy()
    axes = radial_axes(rest)
    n = len(rest)
    B_site = getattr(body, "B_site", None)
    norms = (
        np.linalg.norm(np.asarray(B_site, dtype=np.float64), axis=1)
        if B_site is not None and np.asarray(B_site).shape[0] == n
        else np.full(n, float(deform_cfg.neutral_B_norm), dtype=np.float64)
    )
    if deform_cfg.enabled and deform_cfg.material_drive_enabled:
        scalar_target = np.clip(
            deform_cfg.material_gain * (norms - float(deform_cfg.neutral_B_norm)),
            -deform_cfg.max_displacement,
            deform_cfg.max_displacement,
        )
        target = axes * scalar_target[:, None]
    else:
        target = np.zeros_like(d)

    relax = max(0.0, min(1.0, float(deform_cfg.relaxation)))
    v_kin = _rate_limit((target - d) * relax, deform_cfg.max_rate)

    k = float(work_cfg.stiffness)
    gamma = float(work_cfg.viscous_coeff) if work_cfg.viscous_coeff is not None else (
        k / max(relax, 1e-9)
    )
    gamma = max(gamma, 1e-9)
    U0 = deformation_potential(before, k)

    work_on = bool(deform_cfg.enabled and work_cfg.enabled)
    transfer = bool(work_on and work_cfg.transfer_enabled)
    actuator_on = bool(transfer and work_cfg.actuator_enabled and deform_cfg.material_drive_enabled)
    env_on = bool(work_on and work_cfg.env_deform_enabled)

    F_env = _env_radial(
        env_force_body if env_force_body is not None else getattr(body, "deformation_env_force", None),
        axes,
        n,
        env_on,
    )
    v_p = (F_env - k * d) / gamma
    v_p = _rate_limit(v_p, deform_cfg.max_rate)

    reservoir0 = ensure_reservoir(body, work_cfg) if work_on else float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
    w_cap = reservoir0 if work_budget is None else min(reservoir0, max(0.0, float(work_budget)))

    if not deform_cfg.enabled:
        used = np.zeros_like(d)
        ledger = empty_work_ledger()
        ledger.update({
            "enabled": False,
            "material_drive_enabled": bool(deform_cfg.material_drive_enabled),
            "geometry_coupling_enabled": bool(deform_cfg.geometry_coupling_enabled),
            "rest_geometry": rest.tolist(),
            "deformation_before": before.tolist(),
            "deformation": d.tolist(),
            "actual_geometry": rest.tolist(),
            "B_site_norms": norms.tolist(),
            "max_displacement": float(deform_cfg.max_displacement),
            "max_rate": float(deform_cfg.max_rate),
            "potential_before": U0,
            "potential_after": U0,
        })
        return ledger

    if not work_on or not transfer:
        # Established kinematic tracker; reservoir is inert (ablated transfer / work OFF).
        d_new = _clip_displacement(d + v_kin, deform_cfg.max_displacement)
        body.deformation = d_new
        used = d_new if deform_cfg.geometry_coupling_enabled else np.zeros_like(d_new)
        ledger = empty_work_ledger()
        ledger.update({
            "enabled": True,
            "material_drive_enabled": bool(deform_cfg.material_drive_enabled),
            "geometry_coupling_enabled": bool(deform_cfg.geometry_coupling_enabled),
            "rest_geometry": rest.tolist(),
            "deformation_before": before.tolist(),
            "deformation": d_new.tolist(),
            "actual_geometry": (rest + used).tolist(),
            "B_site_norms": norms.tolist(),
            "max_displacement": float(deform_cfg.max_displacement),
            "max_rate": float(deform_cfg.max_rate),
            "mechanical_energy_accounting": "BYPASSED" if work_on else "NOT DEMONSTRATED",
            "work_transfer_enabled": False,
            "reservoir_before": reservoir0,
            "reservoir_after": reservoir0,
            "potential_before": U0,
            "potential_after": deformation_potential(d_new, k),
            "delta_potential": deformation_potential(d_new, k) - U0,
            "shape_change_source": "KINEMATIC_UNMETERED",
            "where_did_the_work_come_from": ["TRANSFER_ABLATED_OR_WORK_OFF"],
        })
        return ledger

    dv = v_kin - v_p
    a = float(gamma * np.sum(dv * dv))
    b = float(gamma * np.sum(dv * v_p))
    w1 = a + b  # W(1)

    if not actuator_on:
        s = 0.0
    elif w1 <= 0.0:
        s = 1.0
    else:
        s = _solve_actuator_scale(a, b, w_cap, w1)

    v = v_p + s * dv
    v = _rate_limit(v, deform_cfg.max_rate)
    d_new = _clip_displacement(d + v, deform_cfg.max_displacement)
    dx = d_new - d
    # Realized overdamped forces on the accepted step (dt = 1).
    F_act = k * d + gamma * dx - F_env
    W_act = float(np.sum(F_act * dx))
    W_env = float(np.sum(F_env * dx))
    U1 = deformation_potential(d_new, k)
    dU = U1 - U0
    W_visc = float(gamma * np.sum(dx * dx))
    residual = W_act + W_env - dU - W_visc
    # Explicit Euler uses F_spring = −k d at the start of the tick;
    # trapezoid would include +½ k ‖dx‖² in ΔU. That gap is a known quadrature term.
    known_quadrature = float(-0.5 * k * np.sum(dx * dx))
    unexplained_residual = float(residual - known_quadrature)

    supplied = min(w_cap, max(0.0, W_act)) if actuator_on else 0.0
    recovered = 0.0
    if actuator_on and work_cfg.recovery_to_reservoir and W_act < 0.0:
        recovered = min(float(work_cfg.reservoir_max) - reservoir0, -W_act)
    reservoir1 = min(float(work_cfg.reservoir_max), max(0.0, reservoir0 - supplied + recovered))
    body.mechanical_work_reservoir = reservoir1
    body.deformation = d_new

    depleted = reservoir1 <= 1e-12 and (supplied > 0 or (actuator_on and w1 > 1e-12 and s < 1.0 - 1e-9))
    limited = bool(actuator_on and s < 1.0 - 1e-6 and w1 > 1e-12)
    geom_delta = float(np.max(np.abs(dx)))
    toward_rest = float(np.sum(d * dx)) < -1e-12 and float(np.linalg.norm(F_env)) < 1e-12

    sources = []
    if supplied > 1e-12:
        sources.append("MECHANICAL_WORK_RESERVOIR")
    if W_env > 1e-12:
        sources.append("EXTERNAL_SITE_FORCE")
    if dU < -1e-12:
        sources.append("STORED_DEFORMATION_POTENTIAL")
    if not sources and geom_delta > 1e-12:
        sources.append("PASSIVE_OVERDAMPED_RELAXATION")
    if geom_delta <= 1e-12:
        sources = ["NO_CONFIGURATION_WORK"]

    if geom_delta <= 1e-12:
        shape_src = "STATIC"
    elif supplied > 1e-12 and s > 1e-6:
        shape_src = "INTERNALLY_POWERED"
    elif W_env > 1e-12 and (not actuator_on or s <= 1e-6):
        shape_src = "ENVIRONMENTALLY_FORCED"
    elif toward_rest or (s <= 1e-6 and float(np.linalg.norm(F_env)) < 1e-12):
        shape_src = "PASSIVE_RELAXATION"
    else:
        shape_src = "MIXED"

    used = d_new if deform_cfg.geometry_coupling_enabled else np.zeros_like(d_new)
    return {
        "enabled": True,
        "material_drive_enabled": bool(deform_cfg.material_drive_enabled),
        "geometry_coupling_enabled": bool(deform_cfg.geometry_coupling_enabled),
        "rest_geometry": rest.tolist(),
        "deformation_before": before.tolist(),
        "deformation": d_new.tolist(),
        "actual_geometry": (rest + used).tolist(),
        "B_site_norms": norms.tolist(),
        "max_displacement": float(deform_cfg.max_displacement),
        "max_rate": float(deform_cfg.max_rate),
        "mechanical_energy_accounting": "ACTIVE",
        "work_transfer_enabled": True,
        "actuator_enabled": actuator_on,
        "env_deform_enabled": env_on,
        "stiffness": k,
        "viscous_coeff": gamma,
        "reservoir_before": reservoir0,
        "reservoir_after": reservoir1,
        "reservoir_work_supplied": float(supplied),
        "reservoir_work_recovered": float(recovered),
        "actuator_work": float(W_act),
        "env_work_on_deformation": float(W_env),
        "delta_potential": float(dU),
        "potential_before": float(U0),
        "potential_after": float(U1),
        "dissipated_viscous": float(W_visc),
        "deformation_residual": float(residual),
        "known_quadrature": known_quadrature,
        "unexplained_residual": unexplained_residual,
        "first_law": {
            "input_reservoir_supplied": float(supplied),
            "input_env_work": float(W_env),
            "input_recovered_to_reservoir": float(recovered),
            "stored_change": float(dU),
            "dissipation": float(W_visc),
            "residual": float(residual),
            "known_quadrature": known_quadrature,
            "unexplained_residual": unexplained_residual,
            "identity": "W_act + W_env = dU + W_viscous + residual",
            "W_act_plus_W_env": float(W_act + W_env),
            "dU_plus_diss_plus_residual": float(dU + W_visc + residual),
        },
        "actuator_scale": float(s),
        "work_limited": limited,
        "reservoir_depleted": bool(reservoir1 <= 1e-12),
        "shape_change_source": shape_src,
        "where_did_the_work_come_from": sources,
        "geometry_delta_max": geom_delta,
        "note": (
            "mechanical_work_reservoir is an abstract finite work budget for F_act·dx; "
            "not metabolism, reward, or internal.c."
        ),
    }
