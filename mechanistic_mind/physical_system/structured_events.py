"""Bounded structured causal events for Observer human-readable overview (no prose)."""
from __future__ import annotations
from collections import deque
from typing import Any
import time


EVENT_TYPES = (
    "BODY_ROTATED",
    "BODY_MOVED",
    "BODY_DEFORMED",
    "SITE_GEOMETRY_CHANGED",
    "LOCAL_MATERIAL_CHANGED",
    "INTERNAL_STATE_CHANGED",
    "ENVIRONMENT_EXPOSURE_CHANGED",
    "SCENARIO_SUPPORTED",
    "SCENARIO_SELECTED",
    "PREDICTION_MATCHED",
    "PREDICTION_VIOLATED",
    "OBJECT_CONTACT",
    "OBSERVATION_ACQUIRED",
    "WORK_TRANSFERRED",
    "DEFORMATION_POWERED",
    "DEFORMATION_EXTERNALLY_FORCED",
    "DEFORMATION_RELAXED",
    "DEFORMATION_WORK_LIMITED",
    "WORK_RESERVOIR_DEPLETED",
    "STORED_MECHANICAL_ENERGY_RELEASED",
    "RESOURCE_TRANSFER_STARTED",
    "RESOURCE_TRANSFERRED",
    "RESOURCE_SOURCE_DEPLETED",
    "BODY_RESOURCE_CAPACITY_REACHED",
    "RESOURCE_CONVERTED_TO_WORK",
    "WORK_RESERVOIR_REPLENISHED",
    "RESOURCE_A_TRANSFERRED",
    "RESOURCE_B_TRANSFERRED",
    "RESOURCE_A_CAPACITY_REACHED",
    "RESOURCE_B_CAPACITY_REACHED",
    "RESOURCE_A_LIMITING",
    "RESOURCE_B_LIMITING",
    "COMPLEMENTARY_CONVERSION",
    "COMPLEMENTARY_CONVERSION_STOPPED",
    "RESOURCE_A_DEPLETED",
    "RESOURCE_B_DEPLETED",
    "MOTOR_DRIVE_GENERATED",
    "MOTOR_WORK_REQUESTED",
    "MOTOR_WORK_REALIZED",
    "MOTOR_WORK_LIMITED",
    "MOTOR_WORK_UNAVAILABLE",
    "WORK_ALLOCATED_TO_MOTOR",
    "DISCRETE_ACTION_SELECTED",
    "ACTION_WORK_REQUESTED",
    "ACTION_WORK_ALLOCATED",
    "ACTION_WORK_REALIZED",
    "ACTION_WORK_LIMITED",
    "ACTION_WORK_UNAVAILABLE",
    "ACTION_PHYSICAL_REALIZATION",
    "PHYSICAL_SIGNAL_EMITTED",
    "PHYSICAL_SIGNAL_RECEIVED",
    "NECK_MOTOR_APPLIED",
    "PUSH_FORCE_APPLIED",
    "PUSH_NO_CONTACT",
)


class StructuredEventBuffer:
    def __init__(self, maxlen: int = 200):
        self._buf: deque[dict[str, Any]] = deque(maxlen=maxlen)

    def emit(self, event_type: str, *, tick: int, evidence: dict[str, Any] | None = None) -> None:
        if event_type not in EVENT_TYPES:
            event_type = str(event_type)
        self._buf.append({
            "schema": "mm.structured_event.v1",
            "type": event_type,
            "tick": int(tick),
            "evidence": evidence or {},
        })

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        items = list(self._buf)
        return items[-max(1, int(limit)):]

    def __len__(self) -> int:
        return len(self._buf)

    def clear(self) -> None:
        self._buf.clear()


EVENT_SCHEMA = {
    "schema": "mm.structured_event.v1",
    "types": list(EVENT_TYPES),
    "note": "Simulation emits structured events only; UI may later render prose.",
}
