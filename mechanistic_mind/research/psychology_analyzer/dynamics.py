from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Mapping

from .extractor import numeric


@dataclass
class NumericRange:
    minimum: float | None = None
    maximum: float | None = None

    def observe(self, value: Any) -> None:
        number = numeric(value)
        if number is None:
            return
        self.minimum = number if self.minimum is None else min(self.minimum, number)
        self.maximum = number if self.maximum is None else max(self.maximum, number)

    def to_dict(self) -> dict[str, float | None]:
        return {"min": self.minimum, "max": self.maximum}


@dataclass
class DynamicsAccumulator:
    ticks: int = 0
    first_tick: int | None = None
    last_tick: int | None = None
    actions: Counter[str] = field(default_factory=Counter)
    reasons: Counter[str] = field(default_factory=Counter)
    object_uses: Counter[str] = field(default_factory=Counter)
    body_ranges: dict[str, NumericRange] = field(default_factory=dict)
    largest_prediction_error: dict[str, Any] | None = None
    todo4_ranges: dict[str, NumericRange] = field(default_factory=dict)
    retrieval_stages: Counter[str] = field(default_factory=Counter)
    unknown_count: int = 0
    wait_count: int = 0
    move_count: int = 0
    interaction_count: int = 0
    positions: set[tuple[int, int]] = field(default_factory=set)

    def observe(self, row: Mapping[str, Any]) -> None:
        tick = row.get("tick")
        if not isinstance(tick, int):
            return
        self.ticks += 1
        self.first_tick = tick if self.first_tick is None else self.first_tick
        self.last_tick = tick
        action = row.get("action")
        if isinstance(action, str):
            self.actions[action] += 1
            self.wait_count += int(action == "WAIT")
            self.move_count += int(action.startswith("MOVE:"))
            self.interaction_count += int(not action.startswith("MOVE:") and action != "WAIT")
        position = row.get("position")
        if isinstance(position, (list, tuple)) and len(position) == 2:
            self.positions.add((int(position[0]), int(position[1])))
        if row.get("perceptual_unknown") is True:
            self.unknown_count += 1
        stage = row.get("retrieval_stage")
        if isinstance(stage, str):
            self.retrieval_stages[stage] += 1
        for key in ("perceptual_mismatch", "perceptual_activation", "retrieval_confidence", "inspected_candidates"):
            self.todo4_ranges.setdefault(key, NumericRange()).observe(row.get(key))
        object_id = row.get("object_id")
        if isinstance(object_id, str):
            self.object_uses[object_id] += 1
        reason = row.get("selection_reason")
        if isinstance(reason, str):
            self.reasons[reason] += 1
        body = row.get("body_truth")
        if isinstance(body, Mapping):
            for key, value in body.items():
                self.body_ranges.setdefault(str(key), NumericRange()).observe(value)
        error = numeric(row.get("prediction_error"))
        if error is not None and (
            self.largest_prediction_error is None
            or abs(error) > abs(self.largest_prediction_error["value"])
        ):
            self.largest_prediction_error = {
                "tick": tick,
                "value": error,
                "action": row.get("prediction_error_action") or action,
                "source_line": (row.get("provenance") or {}).get("source_line"),
            }

    def to_dict(self) -> dict[str, Any]:
        return {
            "ticks_analyzed": self.ticks,
            "first_tick": self.first_tick,
            "last_tick": self.last_tick,
            "action_counts": dict(self.actions.most_common()),
            "selection_reason_counts": dict(self.reasons.most_common()),
            "object_interaction_counts": dict(self.object_uses.most_common()),
            "body_ranges": {key: value.to_dict() for key, value in sorted(self.body_ranges.items())},
            "largest_prediction_error": self.largest_prediction_error,
            "todo4": {
                "ranges": {key: value.to_dict() for key, value in sorted(self.todo4_ranges.items())},
                "unknown_fraction": self.unknown_count / max(1, self.ticks),
                "retrieval_stage_distribution": dict(self.retrieval_stages.most_common()),
                "wait_fraction": self.wait_count / max(1, self.ticks),
                "move_fraction": self.move_count / max(1, self.ticks),
                "interaction_fraction": self.interaction_count / max(1, self.ticks),
                "spatial_coverage_unique_positions": len(self.positions),
            },
        }
