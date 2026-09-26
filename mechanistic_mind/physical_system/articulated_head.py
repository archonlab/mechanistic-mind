"""Articulated head / neck DOF — physical sensor orientation.

Observer-only GT may expose head angles. Cognition receives only exo_*
consequences after FOV changes. No LOOK_AT / TRACK / ATTENTION semantics.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.physical_system.near_field_exteroception import wrap_angle


@dataclass
class ArticulatedHeadConfig:
    """Physical neck parameters. Default OFF → legacy body-heading vision."""

    mode: str = "OFF"  # OFF | EXPERIMENTAL
    # Relative angle limit (rad). ±π/2 ≈ ±90°.
    neck_angle_limit: float = math.pi / 2
    # Motor torque scale (rad/tick² per unit motor command in [-1,1]).
    neck_motor_torque: float = 0.08
    neck_angular_velocity_limit: float = 0.25
    neck_damping: float = 0.35
    # Soft restoring toward relative angle 0 when motor is neutral (HOLD/0).
    neck_restoring_strength: float = 0.04
    # Optional mechanical work cost per |motor| unit when discrete_action_work ON.
    neck_work_cost_per_motor: float = 0.02

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ArticulatedHeadConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def head_world_heading(body: PhysicalBodyState) -> float:
    """World-frame sensor forward axis = body θ + relative neck angle."""
    body_theta = float(getattr(body, "theta", 0.0) or 0.0)
    rel = float(getattr(body, "head_relative_angle", 0.0) or 0.0)
    return wrap_angle(body_theta + rel)


def sensor_heading_for_vision(
    body: PhysicalBodyState,
    *,
    articulated_head: bool,
) -> float:
    """Vision orientation authority. Legacy: body.theta when articulated_head=false."""
    if not articulated_head:
        return float(getattr(body, "theta", 0.0) or 0.0)
    return head_world_heading(body)


def step_articulated_head(
    body: PhysicalBodyState,
    cfg: ArticulatedHeadConfig,
    *,
    neck_motor: float = 0.0,
) -> dict[str, Any]:
    """Integrate neck DOF for one tick. Deterministic; no RNG.

    Motor command in [-1, 1] produces torque. Passive damping + soft restore
    keep the head well-behaved without active input (no fan-blade spin).
    """
    if not cfg.enabled:
        # Legacy: keep relative angle at 0; clear motor residue.
        body.head_relative_angle = 0.0
        body.head_omega = 0.0
        body.neck_motor = 0.0
        return {
            "enabled": False,
            "head_relative_angle": 0.0,
            "head_omega": 0.0,
            "head_world_heading": float(getattr(body, "theta", 0.0) or 0.0),
            "neck_motor": 0.0,
            "clamped": False,
        }

    limit = max(1e-6, float(cfg.neck_angle_limit))
    omega_max = max(1e-6, float(cfg.neck_angular_velocity_limit))
    motor = float(max(-1.0, min(1.0, neck_motor)))
    body.neck_motor = motor

    rel = float(getattr(body, "head_relative_angle", 0.0) or 0.0)
    omega = float(getattr(body, "head_omega", 0.0) or 0.0)

    # Torque: motor drive − damping·ω − restoring·angle (when |motor| small).
    restore = float(cfg.neck_restoring_strength) * rel
    if abs(motor) > 0.05:
        restore *= 0.15  # reduced restore under active drive
    alpha = float(cfg.neck_motor_torque) * motor - float(cfg.neck_damping) * omega - restore
    omega = omega + alpha
    omega = max(-omega_max, min(omega_max, omega))
    rel = rel + omega

    clamped = False
    if rel > limit:
        rel = limit
        omega = min(0.0, omega)
        clamped = True
    elif rel < -limit:
        rel = -limit
        omega = max(0.0, omega)
        clamped = True

    body.head_relative_angle = float(rel)
    body.head_omega = float(omega)
    hwh = head_world_heading(body)
    return {
        "enabled": True,
        "head_relative_angle": float(rel),
        "head_omega": float(omega),
        "head_world_heading": float(hwh),
        "body_theta": float(getattr(body, "theta", 0.0) or 0.0),
        "neck_motor": motor,
        "alpha": float(alpha),
        "clamped": clamped,
        "neck_angle_limit": float(limit),
        "semantics": {
            "physical_dof_only": True,
            "not_gaze_target": True,
            "not_attention": True,
        },
    }


# Snapshot fields required for future deterministic resume.
SNAPSHOT_HEAD_FIELDS = (
    "head_relative_angle",
    "head_omega",
    "neck_motor",
)
