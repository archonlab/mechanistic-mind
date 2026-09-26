"""Observer HUD label for the final applied CompositeMotorOutput.

Presentation only. Does not reconstruct cognition or invent motor tokens.
Uses CompositeMotorOutput.display_label() (via the persisted `display` field).
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.composite_motor import (
    CompositeMotorOutput,
    OscillatorMotorComponent,
)


def observer_applied_composite_action_display(
    last_motor_output: dict[str, Any] | None,
    *,
    fallback: str | None = None,
) -> str:
    """Human-readable final applied motor for bottom Observer badges.

    JOIN uses ` + ` (historical Observer HUD). Tokens and inclusion rules
    come from CompositeMotorOutput.display_label (NECK_HOLD visible; NECK_NONE
    / OSC_NONE / PUSH_NONE omitted).
    """
    label = None
    if isinstance(last_motor_output, dict) and last_motor_output:
        raw = last_motor_output.get("display")
        if raw:
            label = str(raw)
        else:
            osc = last_motor_output.get("oscillator") or {}
            if not isinstance(osc, dict):
                osc = {}
            motor = CompositeMotorOutput(
                locomotion=str(last_motor_output.get("locomotion") or "WAIT"),
                neck=str(last_motor_output.get("neck") or "NONE"),
                oscillator=OscillatorMotorComponent.from_dict(osc),
                push=bool(last_motor_output.get("push")),
                schema=str(last_motor_output.get("schema") or ""),
                legacy_token=str(last_motor_output.get("legacy_token") or "WAIT"),
                selection_source=str(last_motor_output.get("selection_source") or "COMPOSITE"),
            )
            label = motor.display_label()
    if not label:
        label = str(fallback or "WAIT")
    return label.replace(" | ", " + ")


def observer_applied_composite_action_display_for_runtime(runtime: Any) -> str:
    mo = getattr(runtime, "last_motor_output", None)
    fallback = getattr(runtime, "last_selected_action", None)
    return observer_applied_composite_action_display(mo, fallback=fallback)
