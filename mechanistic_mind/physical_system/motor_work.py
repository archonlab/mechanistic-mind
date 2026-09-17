"""Work-limited realization of endogenous motor drive.

Drive generation stays in endogenous_motor.update_motor_state.
This module only meters the mechanical velocity increment against
mechanical_work_reservoir. Not effort, fatigue, motivation, or metabolism.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass
class EndogenousMotorWorkConfig:
    """Fresh CURRENT INTEGRATED default ON; from_dict missing → OFF (historical free motor)."""

    mode: str = "EXPERIMENTAL"

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EndogenousMotorWorkConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def ke_increment(mass: float, vx: float, vy: float, dvx: float, dvy: float) -> float:
    m = float(mass)
    return m * (float(vx) * float(dvx) + float(vy) * float(dvy)) + 0.5 * m * (float(dvx) ** 2 + float(dvy) ** 2)


def _clip_v(vx: float, vy: float, v_max: float) -> tuple[float, float]:
    vm = float(v_max)
    return float(np.clip(vx, -vm, vm)), float(np.clip(vy, -vm, vm))


def requested_delta_v(
    *,
    vx: float,
    vy: float,
    drive_ux: float,
    drive_uy: float,
    mass: float,
    v_max: float,
    increment_mode: str,
) -> tuple[float, float]:
    """increment_mode: 'acceleration' (site path Δv=u) or 'force' (lumped Δv=u/m)."""
    if increment_mode == "force":
        ax, ay = float(drive_ux) / max(float(mass), 1e-12), float(drive_uy) / max(float(mass), 1e-12)
    else:
        ax, ay = float(drive_ux), float(drive_uy)
    vx1, vy1 = _clip_v(vx + ax, vy + ay, v_max)
    return vx1 - float(vx), vy1 - float(vy)


def scale_positive_ke(mass: float, vx: float, vy: float, dvx: float, dvy: float, budget: float) -> float:
    w1 = ke_increment(mass, vx, vy, dvx, dvy)
    if w1 <= 1e-15:
        return 1.0
    w_avail = max(0.0, float(budget))
    if w_avail <= 1e-15:
        return 0.0
    if w1 <= w_avail + 1e-15:
        return 1.0
    a = 0.5 * float(mass) * (float(dvx) ** 2 + float(dvy) ** 2)
    b = float(mass) * (float(vx) * float(dvx) + float(vy) * float(dvy))
    if abs(a) < 1e-18:
        if abs(b) < 1e-18:
            return 1.0
        return float(np.clip(w_avail / b, 0.0, 1.0))
    disc = b * b + 4.0 * a * w_avail
    if disc < 0.0:
        return 0.0
    s = (-b + np.sqrt(disc)) / (2.0 * a)
    return float(np.clip(s, 0.0, 1.0))


def allocate_shared_work(
    w_avail: float,
    w_def_req: float,
    w_mot_req: float,
    w_action_req: float = 0.0,
) -> dict[str, float]:
    w_avail = max(0.0, float(w_avail))
    d = max(0.0, float(w_def_req))
    m = max(0.0, float(w_mot_req))
    act = max(0.0, float(w_action_req))
    tot = d + m + act
    if tot <= 1e-15:
        return {
            "available": w_avail,
            "requested_deformation": d,
            "requested_motor": m,
            "requested_action": act,
            "allocated_deformation": 0.0,
            "allocated_motor": 0.0,
            "allocated_action": 0.0,
        }
    if tot <= w_avail + 1e-15:
        return {
            "available": w_avail,
            "requested_deformation": d,
            "requested_motor": m,
            "requested_action": act,
            "allocated_deformation": d,
            "allocated_motor": m,
            "allocated_action": act,
        }
    return {
        "available": w_avail,
        "requested_deformation": d,
        "requested_motor": m,
        "requested_action": act,
        "allocated_deformation": w_avail * d / tot,
        "allocated_motor": w_avail * m / tot,
        "allocated_action": w_avail * act / tot,
    }


def preview_motor_positive_work(
    *,
    vx: float,
    vy: float,
    drive_ux: float,
    drive_uy: float,
    mass: float,
    v_max: float,
    increment_mode: str,
) -> float:
    dvx, dvy = requested_delta_v(
        vx=vx, vy=vy, drive_ux=drive_ux, drive_uy=drive_uy,
        mass=mass, v_max=v_max, increment_mode=increment_mode,
    )
    return max(0.0, ke_increment(mass, vx, vy, dvx, dvy))


def empty_motor_work_ledger() -> dict[str, Any]:
    return {
        "accounting_enabled": False,
        "increment_mode": "acceleration",
        "motor_drive_requested": [0.0, 0.0],
        "motor_force_requested": [0.0, 0.0],
        "motor_delta_v_requested": [0.0, 0.0],
        "motor_work_requested": 0.0,
        "motor_force_realized": [0.0, 0.0],
        "motor_delta_v_realized": [0.0, 0.0],
        "motor_work_realized": 0.0,
        "motor_work_unrealized": 0.0,
        "work_limit_fraction": 1.0,
        "mechanical_work_reservoir_before": 0.0,
        "mechanical_work_reservoir_after": 0.0,
        "kinetic_energy_change_from_motor": 0.0,
        "work_limited": False,
        "work_unavailable": False,
        "receipt_id": None,
        "where_did_the_motor_work_come_from": [],
        "note": "Motor drive ≠ realized force. Not effort/fatigue/motivation.",
    }


def apply_motor_realization(
    body,
    *,
    mass: float,
    v_max: float,
    increment_mode: str,
    accounting_enabled: bool,
    work_budget: float | None,
    receipt_tick: int,
    reservoir_max: float,
) -> dict[str, Any]:
    """Apply drive as velocity increment; optionally limit by allocated work. Center-applied, no torque."""
    ux = float(getattr(body, "motor_ux", 0.0) or 0.0)
    uy = float(getattr(body, "motor_uy", 0.0) or 0.0)
    vx0, vy0 = float(body.vx), float(body.vy)
    m = float(mass)
    dvx_req, dvy_req = requested_delta_v(
        vx=vx0, vy=vy0, drive_ux=ux, drive_uy=uy, mass=m, v_max=v_max, increment_mode=increment_mode,
    )
    w_req = max(0.0, ke_increment(m, vx0, vy0, dvx_req, dvy_req))
    w0 = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
    ledger = empty_motor_work_ledger()
    fx_req, fy_req = m * dvx_req, m * dvy_req
    ledger.update({
        "accounting_enabled": bool(accounting_enabled),
        "increment_mode": increment_mode,
        "motor_drive_requested": [ux, uy],
        "motor_force_requested": [float(fx_req), float(fy_req)],
        "motor_delta_v_requested": [float(dvx_req), float(dvy_req)],
        "motor_work_requested": float(w_req),
        "mechanical_work_reservoir_before": w0,
        "receipt_id": f"mw-{int(receipt_tick)}",
    })

    if not accounting_enabled:
        vx1, vy1 = _clip_v(vx0 + dvx_req, vy0 + dvy_req, v_max)
        body.vx, body.vy = vx1, vy1
        dvx, dvy = vx1 - vx0, vy1 - vy0
        dke = ke_increment(m, vx0, vy0, dvx, dvy)
        ledger.update({
            "motor_force_realized": [float(m * dvx), float(m * dvy)],
            "motor_delta_v_realized": [float(dvx), float(dvy)],
            "motor_work_realized": 0.0,
            "motor_work_unrealized": float(w_req),
            "work_limit_fraction": 1.0,
            "mechanical_work_reservoir_after": w0,
            "kinetic_energy_change_from_motor": float(dke),
            "where_did_the_motor_work_come_from": ["HISTORICAL_UNACCOUNTED_MOTOR"],
            "note": "Ablated/historical path: velocity increment without reservoir debit.",
        })
        return ledger

    budget = w0 if work_budget is None else min(w0, max(0.0, float(work_budget)))
    s = scale_positive_ke(m, vx0, vy0, dvx_req, dvy_req, budget)
    vx1, vy1 = _clip_v(vx0 + s * dvx_req, vy0 + s * dvy_req, v_max)
    body.vx, body.vy = vx1, vy1
    dvx, dvy = vx1 - vx0, vy1 - vy0
    dke = ke_increment(m, vx0, vy0, dvx, dvy)
    w_real = max(0.0, dke)
    w_real = min(w_real, budget)
    w1 = min(float(reservoir_max), max(0.0, w0 - w_real))
    body.mechanical_work_reservoir = w1
    frac = 1.0 if (abs(dvx_req) + abs(dvy_req)) <= 1e-15 else float(np.hypot(dvx, dvy) / max(np.hypot(dvx_req, dvy_req), 1e-15))
    sources = []
    if w_real > 1e-12:
        sources.append("MECHANICAL_WORK_RESERVOIR")
    ledger.update({
        "motor_force_realized": [float(m * dvx), float(m * dvy)],
        "motor_delta_v_realized": [float(dvx), float(dvy)],
        "motor_work_realized": float(w_real),
        "motor_work_unrealized": float(max(0.0, w_req - w_real)),
        "work_limit_fraction": float(min(1.0, max(0.0, frac))),
        "mechanical_work_reservoir_after": float(w1),
        "kinetic_energy_change_from_motor": float(dke),
        "work_limited": bool(s < 1.0 - 1e-6 and w_req > 1e-12),
        "work_unavailable": bool(w_req > 1e-12 and w_real <= 1e-12),
        "allocated_budget": float(budget),
        "actuator_scale": float(s),
        "where_did_the_motor_work_come_from": sources,
    })
    return ledger
