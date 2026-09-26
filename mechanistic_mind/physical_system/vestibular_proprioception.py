"""Physical vestibular sensing × rotational proprioception.

Body-local rotational transducers only. No compass, no target direction,
no SELF_MOTION / WORLD_MOTION labels. Cognition receives anonymous vest_*/prop_*.

Decision: direct bounded transduction (no transducer time-constant memory)
— minimal, deterministic, no hidden semantic processing.
Linear body-local acceleration channels: DEFERRED (not required for VP gates).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.physical_system.articulated_head import ArticulatedHeadConfig
from mechanistic_mind.physical_system.near_field_exteroception import wrap_angle


def _tanh_bound(x: float, scale: float) -> float:
    """Symmetric bounded response in (-1, 1)."""
    s = max(1e-12, float(scale))
    return float(math.tanh(float(x) / s))


@dataclass
class VestibularConfig:
    """Whole-body rotational sensing. Default OFF."""

    mode: str = "OFF"  # OFF | EXPERIMENTAL
    # Scale for tanh transduction of omega (rad/tick).
    omega_scale: float = 0.20
    # Scale for tanh transduction of alpha (rad/tick²).
    alpha_scale: float = 0.15

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "VestibularConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


@dataclass
class NeckProprioceptionConfig:
    """Neck-relative proprioception. Default OFF. Independent of vestibular."""

    mode: str = "OFF"  # OFF | EXPERIMENTAL
    # Normalize relative angle by neck limit when available.
    angle_scale: float = math.pi / 2
    omega_scale: float = 0.20

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "NeckProprioceptionConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def body_angular_acceleration(
    body: PhysicalBodyState,
    *,
    orientation_meta: dict[str, Any] | None = None,
    prev_omega: float | None = None,
) -> float:
    """Physical α from orientation meta, else finite difference of ω."""
    if isinstance(orientation_meta, dict) and orientation_meta.get("enabled"):
        if orientation_meta.get("alpha") is not None:
            return float(orientation_meta["alpha"])
    omega = float(getattr(body, "omega", 0.0) or 0.0)
    if prev_omega is not None:
        return float(omega - float(prev_omega))
    return 0.0


def cognition_vestibular_fragments(
    body: PhysicalBodyState,
    cfg: VestibularConfig,
    *,
    orientation_meta: dict[str, Any] | None = None,
    prev_omega: float | None = None,
) -> dict[str, float]:
    """Agent-accessible anonymous vestibular channels. Empty when OFF."""
    if not cfg.enabled:
        return {}
    omega = float(getattr(body, "omega", 0.0) or 0.0)
    alpha = body_angular_acceleration(
        body, orientation_meta=orientation_meta, prev_omega=prev_omega
    )
    return {
        "vest_0": _tanh_bound(omega, cfg.omega_scale),
        "vest_1": _tanh_bound(alpha, cfg.alpha_scale),
    }


def cognition_neck_proprioception_fragments(
    body: PhysicalBodyState,
    cfg: NeckProprioceptionConfig,
    *,
    articulated_head: ArticulatedHeadConfig | None = None,
) -> dict[str, float]:
    """Agent-accessible anonymous neck proprioception. Empty when OFF.

    Requires articulated head physics to be meaningful; if head mechanism OFF,
    still returns empty (no fabricated zeros masquerading as sensing).
    """
    if not cfg.enabled:
        return {}
    head_on = bool(articulated_head is not None and articulated_head.enabled)
    if not head_on:
        return {}
    rel = float(getattr(body, "head_relative_angle", 0.0) or 0.0)
    how = float(getattr(body, "head_omega", 0.0) or 0.0)
    ang_scale = float(cfg.angle_scale)
    if articulated_head is not None and float(articulated_head.neck_angle_limit) > 1e-9:
        ang_scale = float(articulated_head.neck_angle_limit)
    return {
        "prop_neck_0": _tanh_bound(rel, ang_scale),
        "prop_neck_1": _tanh_bound(how, cfg.omega_scale),
    }


def vestibular_world_gt(
    body: PhysicalBodyState,
    cfg: VestibularConfig,
    *,
    orientation_meta: dict[str, Any] | None = None,
    prev_omega: float | None = None,
    agent_fragments: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Observer WORLD GT + AGENT-ACCESSIBLE split for vestibular sensing."""
    omega = float(getattr(body, "omega", 0.0) or 0.0)
    alpha = body_angular_acceleration(
        body, orientation_meta=orientation_meta, prev_omega=prev_omega
    )
    frags = agent_fragments if agent_fragments is not None else cognition_vestibular_fragments(
        body, cfg, orientation_meta=orientation_meta, prev_omega=prev_omega
    )
    return {
        "enabled": bool(cfg.enabled),
        "WORLD_GT": {
            "body_theta": float(getattr(body, "theta", 0.0) or 0.0),
            "body_omega": omega,
            "body_alpha": alpha,
        },
        "AGENT_ACCESSIBLE": {
            "vest_0": frags.get("vest_0") if cfg.enabled else None,
            "vest_1": frags.get("vest_1") if cfg.enabled else None,
            "status": "AVAILABLE" if cfg.enabled else "NOT_AVAILABLE",
        },
        "semantics": {
            "no_compass": True,
            "no_absolute_heading_to_cognition": True,
            "measures_physical_rotation_not_action_command": True,
            "not_self_motion_label": True,
        },
        "transduction": "direct_bounded_tanh",
    }


def neck_proprioception_world_gt(
    body: PhysicalBodyState,
    cfg: NeckProprioceptionConfig,
    *,
    articulated_head: ArticulatedHeadConfig | None = None,
    head_meta: dict[str, Any] | None = None,
    agent_fragments: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Observer WORLD GT + AGENT-ACCESSIBLE for neck proprioception."""
    head_on = bool(articulated_head is not None and articulated_head.enabled)
    frags = agent_fragments if agent_fragments is not None else cognition_neck_proprioception_fragments(
        body, cfg, articulated_head=articulated_head
    )
    available = bool(cfg.enabled and head_on)
    hwh = wrap_angle(
        float(getattr(body, "theta", 0.0) or 0.0)
        + float(getattr(body, "head_relative_angle", 0.0) or 0.0)
    )
    return {
        "enabled": bool(cfg.enabled),
        "articulated_head_enabled": head_on,
        "WORLD_GT": {
            "body_theta": float(getattr(body, "theta", 0.0) or 0.0),
            "head_relative_angle": float(getattr(body, "head_relative_angle", 0.0) or 0.0),
            "head_world_heading": float(hwh),
            "head_omega": float(getattr(body, "head_omega", 0.0) or 0.0),
            "neck_motor": float(getattr(body, "neck_motor", 0.0) or 0.0),
            "neck_alpha": (head_meta or {}).get("alpha"),
        },
        "AGENT_ACCESSIBLE": {
            "prop_neck_0": frags.get("prop_neck_0") if available else None,
            "prop_neck_1": frags.get("prop_neck_1") if available else None,
            "status": "AVAILABLE" if available else "NOT_AVAILABLE",
        },
        "semantics": {
            "no_head_world_heading_to_cognition": True,
            "no_target_angle": True,
            "body_local_neck_state_only": True,
        },
    }
