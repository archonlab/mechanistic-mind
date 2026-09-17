"""Physical action bridge for Current MM on PhysicalSystemRuntime.

BRIDGE: body_velocity_impulse_v1

physical_body dynamics historically admit no psyche actions. The smallest
mechanistically continuous bridge reuses existing body velocity state that
`step_physical_body` already integrates under displacement_enabled.

WAIT  — no impulse (autonomous WORLD/BODY/INTERNAL continue).
MOVE:* — add a bounded impulse to body.vx / body.vy before the physical step.

TAKE / RELEASE / CONTACT / EMIT — no production PSR mapping (BRIDGE MISSING).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.physical_body.config import PhysicalBodyConfig

# Canonical Current MM physical action repertoire on PSR.
CANONICAL_ACTIONS = (
    "WAIT",
    "MOVE:N",
    "MOVE:S",
    "MOVE:E",
    "MOVE:W",
)

BRIDGE_ID = "body_velocity_impulse_v1"
BRIDGE_MISSING = ("TAKE", "RELEASE", "CONTACT", "EMIT")

_DIRS = {
    "MOVE:N": (0.0, -1.0),
    "MOVE:S": (0.0, 1.0),
    "MOVE:E": (1.0, 0.0),
    "MOVE:W": (-1.0, 0.0),
}


def action_direction(action: str) -> tuple[float, float] | None:
    """Existing canonical MOVE direction in the world frame."""
    return _DIRS.get(str(action))


@dataclass(frozen=True)
class ActionApplyResult:
    action: str
    applied: bool
    bridge: str
    detail: dict[str, Any]


def available_actions() -> tuple[str, ...]:
    return CANONICAL_ACTIONS


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
