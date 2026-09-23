"""Generic physical force exertion (PUSH) — contact-mediated only.

Not PUSH_AGENT / PUSH_OBJECT. No target identity. No action-at-a-distance.
Force enters the ordinary velocity integrator via soft-contact resolution.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState


@dataclass
class PhysicalPushConfig:
    """Generic EXERT_FORCE / PUSH motor. Default OFF."""

    mode: str = "OFF"  # OFF | EXPERIMENTAL
    # Impulse magnitude scale (momentum units ≈ mass·Δv).
    push_impulse_scale: float = 0.40
    # Work cost when discrete_action_work accounting is ON.
    push_work_cost: float = 0.05

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PhysicalPushConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def clear_push_exertion(body: PhysicalBodyState) -> None:
    body.push_exertion = 0.0


def set_push_exertion(body: PhysicalBodyState, magnitude: float) -> None:
    """Arm contact-mediated force for this tick. Magnitude in [0, 1]."""
    body.push_exertion = float(max(0.0, min(1.0, magnitude)))


def apply_push_through_contact(
    a: PhysicalBodyState,
    b: PhysicalBodyState,
    cfg_a: PhysicalBodyConfig,
    cfg_b: PhysicalBodyConfig,
    *,
    contact: bool,
    push_cfg: PhysicalPushConfig | None,
    width: int,
    height: int,
) -> dict[str, Any]:
    """If contact and a pusher has push_exertion>0, apply body-heading impulse.

    Direction = pusher body.theta (physical geometry). No target coords.
    Equal-and-opposite on both masses. Cleared after application attempt.
    """
    receipt: dict[str, Any] = {
        "contact": bool(contact),
        "push_applied": False,
        "pusher": None,
        "impulse_a": [0.0, 0.0],
        "impulse_b": [0.0, 0.0],
        "causally_linked": False,
        "semantics": {
            "not_push_agent": True,
            "no_target_identity": True,
            "contact_required": True,
            "later_cognition_not_causal": True,
        },
    }
    if push_cfg is None or not push_cfg.enabled:
        clear_push_exertion(a)
        clear_push_exertion(b)
        return receipt
    if not contact:
        # No force at a distance — clear armed exertion without transfer.
        receipt["push_without_contact"] = bool(
            float(getattr(a, "push_exertion", 0.0) or 0.0) > 0.0
            or float(getattr(b, "push_exertion", 0.0) or 0.0) > 0.0
        )
        clear_push_exertion(a)
        clear_push_exertion(b)
        return receipt

    scale = float(push_cfg.push_impulse_scale)
    # Resolve toroidal separation for optional alignment check.
    dx = float(b.x - a.x)
    dy = float(b.y - a.y)
    if abs(dx) > width / 2:
        dx -= math.copysign(width, dx)
    if abs(dy) > height / 2:
        dy -= math.copysign(height, dy)

    applied_any = False
    for pusher, other, p_cfg, o_cfg, sign in (
        (a, b, cfg_a, cfg_b, +1),
        (b, a, cfg_b, cfg_a, -1),
    ):
        mag = float(getattr(pusher, "push_exertion", 0.0) or 0.0)
        if mag <= 1e-12:
            continue
        theta = float(getattr(pusher, "theta", 0.0) or 0.0)
        fx = math.cos(theta) * scale * mag
        fy = math.sin(theta) * scale * mag
        mp = max(1e-6, float(p_cfg.mass))
        mo = max(1e-6, float(o_cfg.mass))
        # Equal-opposite momentum: pusher recoils, other receives.
        dv_p = (-fx / mp, -fy / mp)
        dv_o = (fx / mo, fy / mo)
        pusher.vx = float(np.clip(pusher.vx + dv_p[0], -p_cfg.v_max, p_cfg.v_max))
        pusher.vy = float(np.clip(pusher.vy + dv_p[1], -p_cfg.v_max, p_cfg.v_max))
        other.vx = float(np.clip(other.vx + dv_o[0], -o_cfg.v_max, o_cfg.v_max))
        other.vy = float(np.clip(other.vy + dv_o[1], -o_cfg.v_max, o_cfg.v_max))
        applied_any = True
        key = "a" if pusher is a else "b"
        receipt["pusher"] = key
        receipt[f"impulse_{key}"] = [float(dv_p[0]), float(dv_p[1])]
        other_key = "b" if key == "a" else "a"
        receipt[f"impulse_{other_key}"] = [float(dv_o[0]), float(dv_o[1])]
        receipt["push_heading"] = float(theta)
        receipt["push_magnitude"] = mag
        # Only one pusher per pair per tick to keep determinism simple.
        break

    clear_push_exertion(a)
    clear_push_exertion(b)
    receipt["push_applied"] = applied_any
    receipt["causally_linked"] = applied_any  # motor → contact force → Δv
    receipt["causal_chain"] = (
        ["push_motor", "contact_force", "velocity_delta"] if applied_any else []
    )
    return receipt


SNAPSHOT_PUSH_FIELDS = ("push_exertion",)
