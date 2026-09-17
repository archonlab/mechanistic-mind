"""Work accounting for the discrete physical action bridge.

Cognition selects an action string upstream. This module translates the
selected action into a requested world-frame velocity intervention and meters
its positive kinetic-energy increment against mechanical_work_reservoir.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .actions import BRIDGE_ID, BRIDGE_MISSING, action_direction
from .motor_work import ke_increment, scale_positive_ke


@dataclass
class DiscreteActionWorkConfig:
    """Fresh default ON; missing snapshot key preserves historical free MOVE."""

    mode: str = "EXPERIMENTAL"
    impulse_scale: float = 0.35

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "DiscreteActionWorkConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def request_discrete_action(
    *,
    action: str,
    vx: float,
    vy: float,
    mass: float,
    v_max: float,
    impulse_scale: float,
    tick: int,
) -> dict[str, Any]:
    """Build the downstream physical request without mutating body state."""
    kind = str(action)
    direction = action_direction(kind)
    receipt_id = f"aw-{int(tick)}"
    if kind == "WAIT" or kind.startswith("WAIT"):
        return {
            "selected_action": kind,
            "mass": float(mass),
            "bridge": BRIDGE_ID,
            "bridge_available": True,
            "direction_frame": "WORLD",
            "action_dv_requested": [0.0, 0.0],
            "action_dv_requested_after_vmax": [0.0, 0.0],
            "action_impulse_requested": [0.0, 0.0],
            "action_work_signed_requested": 0.0,
            "action_work_requested": 0.0,
            "action_negative_work_requested": 0.0,
            "receipt_id": receipt_id,
        }
    if direction is None:
        missing = kind in BRIDGE_MISSING or kind.split(":", 1)[0] in BRIDGE_MISSING
        return {
            "selected_action": kind,
            "mass": float(mass),
            "bridge": "BRIDGE_MISSING" if missing else "UNKNOWN_NOOP",
            "bridge_available": False,
            "direction_frame": "WORLD",
            "action_dv_requested": [0.0, 0.0],
            "action_dv_requested_after_vmax": [0.0, 0.0],
            "action_impulse_requested": [0.0, 0.0],
            "action_work_signed_requested": 0.0,
            "action_work_requested": 0.0,
            "action_negative_work_requested": 0.0,
            "receipt_id": receipt_id,
        }

    gain = float(impulse_scale) * float(v_max)
    nominal = np.asarray(direction, dtype=np.float64) * gain
    v0 = np.asarray([vx, vy], dtype=np.float64)
    v_try = np.clip(v0 + nominal, -float(v_max), float(v_max))
    dv = v_try - v0
    signed = ke_increment(float(mass), float(vx), float(vy), float(dv[0]), float(dv[1]))
    return {
        "selected_action": kind,
        "mass": float(mass),
        "bridge": BRIDGE_ID,
        "bridge_available": True,
        "direction_frame": "WORLD",
        # Nominal request remains observable even when v_max blocks realization.
        "action_dv_requested": nominal.astype(float).tolist(),
        "action_dv_requested_after_vmax": dv.astype(float).tolist(),
        "action_impulse_requested": (float(mass) * dv).astype(float).tolist(),
        "action_work_signed_requested": float(signed),
        "action_work_requested": float(max(0.0, signed)),
        "action_negative_work_requested": float(max(0.0, -signed)),
        "receipt_id": receipt_id,
    }


def realize_discrete_action(
    body,
    request: dict[str, Any],
    *,
    accounting_enabled: bool,
    allocated_work: float | None,
    reservoir_max: float,
) -> dict[str, Any]:
    """Apply accepted action Δv, limiting only positive work when enabled."""
    vx0, vy0 = float(body.vx), float(body.vy)
    mass = float(request.get("mass") or 1.0)
    dv_req = np.asarray(request.get("action_dv_requested_after_vmax") or [0.0, 0.0], dtype=np.float64)
    signed_req = float(request.get("action_work_signed_requested") or 0.0)
    positive_req = max(0.0, signed_req)
    w0 = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)

    if not bool(request.get("bridge_available")):
        scale = 0.0
    elif not accounting_enabled or signed_req <= 0.0:
        scale = 1.0
    else:
        budget = w0 if allocated_work is None else min(w0, max(0.0, float(allocated_work)))
        scale = scale_positive_ke(mass, vx0, vy0, float(dv_req[0]), float(dv_req[1]), budget)

    dv = scale * dv_req
    body.vx = float(vx0 + dv[0])
    body.vy = float(vy0 + dv[1])
    signed_real = ke_increment(mass, vx0, vy0, float(dv[0]), float(dv[1]))
    positive_real = max(0.0, signed_real) if accounting_enabled else 0.0
    budget = w0 if allocated_work is None else min(w0, max(0.0, float(allocated_work)))
    if accounting_enabled:
        positive_real = min(positive_real, budget)
        body.mechanical_work_reservoir = min(
            float(reservoir_max), max(0.0, w0 - positive_real)
        )
    w1 = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)

    req_norm = float(np.linalg.norm(dv_req))
    frac = 1.0 if req_norm <= 1e-15 else float(np.linalg.norm(dv) / req_norm)
    out = dict(request)
    out.update({
        "mass": mass,
        "accounting_enabled": bool(accounting_enabled),
        "action_work_allocated": (
            positive_req if not accounting_enabled or allocated_work is None
            else float(max(0.0, allocated_work))
        ),
        "action_dv_realized": dv.astype(float).tolist(),
        "action_impulse_realized": (mass * dv).astype(float).tolist(),
        "action_work_signed_realized": float(signed_real),
        "action_work_realized": float(positive_real),
        "action_negative_work_realized": float(max(0.0, -signed_real)),
        "action_work_unrealized": float(max(0.0, positive_req - positive_real)),
        "action_work_limit_fraction": float(np.clip(frac, 0.0, 1.0)),
        "work_limited": bool(positive_req > 1e-12 and scale < 1.0 - 1e-6),
        "work_unavailable": bool(positive_req > 1e-12 and positive_real <= 1e-12),
        "mechanical_work_reservoir_before": w0,
        "mechanical_work_reservoir_after": w1,
        "negative_work_policy": "TRACKED_DISSIPATIVE_REMOVAL_NOT_RECOVERED",
        "center_applied": True,
        "torque": 0.0,
        "where_did_action_work_come_from": (
            ["MECHANICAL_WORK_RESERVOIR"] if positive_real > 1e-12
            else (["HISTORICAL_UNACCOUNTED_ACTION"] if not accounting_enabled and positive_req > 1e-12 else [])
        ),
    })
    return out
