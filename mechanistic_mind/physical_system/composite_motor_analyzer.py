"""Analyzer helpers: control events vs effector-active ticks.

Old runs (LEGACY_SINGLE_SLOT) keep raw action_counts unchanged.
COMPOSITE_MOTOR_V1 reports component control counts separately from
emission-active / head-rotating ticks.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.composite_motor import LEGACY_SCHEMA, MOTOR_SCHEMA


def infer_motor_schema(history_meta: dict[str, Any] | None) -> str:
    if not history_meta:
        return LEGACY_SCHEMA
    s = str(history_meta.get("motor_control_schema") or history_meta.get("motor_schema") or "")
    if s == MOTOR_SCHEMA or s == "COMPOSITE_MOTOR_V1":
        return MOTOR_SCHEMA
    return LEGACY_SCHEMA


def analyze_motor_controls(
    *,
    action_counts: dict[str, int] | None,
    motor_component_counts: dict[str, int] | None,
    effector_ticks: dict[str, int] | None,
    schema: str,
) -> dict[str, Any]:
    """Distinguish CONTROL SELECTION COUNT from EFFECTOR ACTIVE TICKS."""
    ac = dict(action_counts or {})
    mc = dict(motor_component_counts or {})
    et = dict(effector_ticks or {})
    if schema == LEGACY_SCHEMA:
        return {
            "schema": LEGACY_SCHEMA,
            "note": "Legacy single-slot counts preserved; not reinterpreted as composite.",
            "action_counts": ac,
            "reinterpreted": False,
        }
    return {
        "schema": MOTOR_SCHEMA,
        "neck": {
            "left_commands": int(mc.get("NECK_LEFT", 0)),
            "right_commands": int(mc.get("NECK_RIGHT", 0)),
            "hold_commands": int(mc.get("NECK_HOLD", 0)),
            "active_torque_ticks": int(et.get("neck_torque_ticks", 0)),
            "head_rotating_ticks": int(et.get("head_rotating_ticks", 0)),
            "head_non_neutral_ticks": int(et.get("head_non_neutral_ticks", 0)),
        },
        "oscillator": {
            "emit_triggers": int(mc.get("OSC_EMIT", 0)),
            "frequency_adjustments": int(mc.get("osc_freq", 0)),
            "amplitude_adjustments": int(mc.get("osc_amp", 0)),
            "emission_active_ticks": int(et.get("osc_emission_active_ticks", 0)),
            "emission_episodes": int(et.get("osc_emission_episodes", mc.get("OSC_EMIT", 0))),
        },
        "locomotion": {
            "move_commands": sum(int(mc.get(k, 0)) for k in ("MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W")),
            "physical_movement_ticks": int(et.get("body_moved_ticks", 0)),
        },
        "legacy_primary_token_counts": ac,
        "note": "Control counts ≠ effector-active ticks.",
    }
