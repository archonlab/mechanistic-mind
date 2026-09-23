"""Physical action bridge for Current MM on PhysicalSystemRuntime.

BRIDGE: body_velocity_impulse_v1 (+ optional neck / push motors)

WAIT  — no impulse (autonomous WORLD/BODY/INTERNAL continue).
MOVE:* — add a bounded impulse to body.vx / body.vy before the physical step.
NECK_LEFT / NECK_RIGHT / NECK_HOLD — neck motor channels (articulated head ON).
PUSH — arm contact-mediated force exertion (physical_push ON).

TAKE / RELEASE / CONTACT / EMIT — no production PSR mapping (BRIDGE MISSING).
No PUSH_AGENT / LOOK_AT / semantic targets.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.physical_body.config import PhysicalBodyConfig

# Canonical Current MM physical action repertoire on PSR (legacy default).
CANONICAL_ACTIONS = (
    "WAIT",
    "MOVE:N",
    "MOVE:S",
    "MOVE:E",
    "MOVE:W",
)

NECK_ACTIONS = ("NECK_LEFT", "NECK_RIGHT", "NECK_HOLD")
PUSH_ACTIONS = ("PUSH",)
OSC_ACTIONS = (
    "OSC_FREQ_UP",
    "OSC_FREQ_DOWN",
    "OSC_AMP_UP",
    "OSC_AMP_DOWN",
    "OSC_EMIT",
)

BRIDGE_ID = "body_velocity_impulse_v1"
BRIDGE_NECK = "neck_motor_v1"
BRIDGE_PUSH = "contact_push_v1"
BRIDGE_OSC = "oscillatory_emit_v1"
BRIDGE_MISSING = ("TAKE", "RELEASE", "CONTACT", "EMIT")

_DIRS = {
    "MOVE:N": (0.0, -1.0),
    "MOVE:S": (0.0, 1.0),
    "MOVE:E": (1.0, 0.0),
    "MOVE:W": (-1.0, 0.0),
}

# Neck motor command in [-1, 1]. Positive = NECK_LEFT (CCW relative).
_NECK_MOTOR = {
    "NECK_LEFT": 1.0,
    "NECK_RIGHT": -1.0,
    "NECK_HOLD": 0.0,
}


def action_direction(action: str) -> tuple[float, float] | None:
    """Existing canonical MOVE direction in the world frame."""
    return _DIRS.get(str(action))


def neck_motor_command(action: str) -> float | None:
    """Return neck motor u ∈ [-1,1] or None if not a neck action."""
    return _NECK_MOTOR.get(str(action))


def is_push_action(action: str) -> bool:
    return str(action) in PUSH_ACTIONS


@dataclass(frozen=True)
class ActionApplyResult:
    action: str
    applied: bool
    bridge: str
    detail: dict[str, Any]


def available_actions(
    *,
    articulated_head: bool = False,
    physical_push: bool = False,
    oscillatory_signaling: bool = False,
) -> tuple[str, ...]:
    """Physical motor repertoire. Optional DOFs only when mechanisms enabled."""
    out = list(CANONICAL_ACTIONS)
    if articulated_head:
        out.extend(NECK_ACTIONS)
    if physical_push:
        out.extend(PUSH_ACTIONS)
    if oscillatory_signaling:
        out.extend(OSC_ACTIONS)
    return tuple(out)


def apply_physical_action(
    body: PhysicalBodyState,
    action: str,
    *,
    body_config: PhysicalBodyConfig,
    impulse_scale: float = 0.35,
) -> ActionApplyResult:
    """Apply a cognitive action onto the embodied body before physical step."""
    kind = str(action)
    if kind == "WAIT" or kind.startswith("WAIT"):
        return ActionApplyResult(
            action="WAIT",
            applied=True,
            bridge=BRIDGE_ID,
            detail={"impulse": (0.0, 0.0)},
        )
    if kind in BRIDGE_MISSING or kind.split(":", 1)[0] in BRIDGE_MISSING:
        return ActionApplyResult(
            action=kind,
            applied=False,
            bridge="BRIDGE_MISSING",
            detail={"reason": "no_psr_physical_mapping"},
        )
    if kind in _NECK_MOTOR:
        u = float(_NECK_MOTOR[kind])
        body.neck_motor = u
        return ActionApplyResult(
            action=kind,
            applied=True,
            bridge=BRIDGE_NECK,
            detail={"neck_motor": u},
        )
    if kind in PUSH_ACTIONS:
        body.push_exertion = 1.0
        return ActionApplyResult(
            action=kind,
            applied=True,
            bridge=BRIDGE_PUSH,
            detail={"push_exertion": 1.0},
        )
    if kind in OSC_ACTIONS:
        from mechanistic_mind.physical_system.oscillatory_signaling import (
            OscillatorySignalingConfig,
            apply_osc_motor_action,
        )
        # Config is resolved by caller via body flag when mechanism ON.
        osc_cfg = getattr(body, "_osc_cfg", None) or OscillatorySignalingConfig(mode="EXPERIMENTAL")
        detail = apply_osc_motor_action(body, kind, osc_cfg)
        return ActionApplyResult(
            action=kind,
            applied=bool(detail.get("applied")),
            bridge=BRIDGE_OSC,
            detail=detail,
        )
    if kind in _DIRS:
        dx, dy = _DIRS[kind]
        vmax = float(getattr(body_config, "v_max", 0.3) or 0.3)
        gain = float(impulse_scale) * vmax
        body.vx = float(max(-vmax, min(vmax, body.vx + dx * gain)))
        body.vy = float(max(-vmax, min(vmax, body.vy + dy * gain)))
        return ActionApplyResult(
            action=kind,
            applied=True,
            bridge=BRIDGE_ID,
            detail={"impulse": (dx * gain, dy * gain), "vx": body.vx, "vy": body.vy},
        )
    # Unknown kinds: treat as non-intervention rather than inventing semantics.
    return ActionApplyResult(
        action=kind,
        applied=False,
        bridge="UNKNOWN_NOOP",
        detail={"reason": "unrecognized_action"},
    )
