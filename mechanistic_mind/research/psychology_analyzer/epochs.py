from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from statistics import fmean
from typing import Any, Mapping

from .extractor import numeric


def _dominant(counter: Mapping[str, int]) -> str | None:
    return max(counter, key=counter.get) if counter else None


def _distribution_distance(left: Mapping[str, int], right: Mapping[str, int]) -> float:
    left_total = sum(left.values()) or 1
    right_total = sum(right.values()) or 1
    keys = set(left) | set(right)
    return 0.5 * sum(abs(left.get(key, 0) / left_total - right.get(key, 0) / right_total) for key in keys)


@dataclass
class EpochWindow:
    start_tick: int
    start_line: int | None
    end_tick: int
    end_line: int | None
    samples: int = 0
    actions: Counter[str] = field(default_factory=Counter)
    objects: Counter[str] = field(default_factory=Counter)
    positions: set[str] = field(default_factory=set)
    uncertainty: list[float] = field(default_factory=list)
    prediction_error: list[float] = field(default_factory=list)
    body: dict[str, list[float]] = field(default_factory=dict)

    def observe(self, row: Mapping[str, Any]) -> None:
        self.samples += 1
        self.end_tick = int(row["tick"])
        self.end_line = (row.get("provenance") or {}).get("source_line")
        action = row.get("action")
        if isinstance(action, str):
            self.actions[action] += 1
        object_id = row.get("object_id")
        if isinstance(object_id, str):
            self.objects[object_id] += 1
        position = row.get("position")
        if isinstance(position, (list, tuple)):
            self.positions.add(",".join(str(part) for part in position))
        for target, value in ((self.uncertainty, row.get("selected_uncertainty")), (self.prediction_error, row.get("prediction_error"))):
            number = numeric(value)
            if number is not None:
                target.append(number)
        body = row.get("body_truth")
        if isinstance(body, Mapping):
            for key, value in body.items():
                number = numeric(value)
                if number is not None:
                    self.body.setdefault(str(key), []).append(number)

    def to_dict(self) -> dict[str, Any]:
        return {
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "samples": self.samples,
            "action_counts": dict(self.actions),
            "object_interaction_counts": dict(self.objects),
            "visited_position_count": len(self.positions),
            "mean_selected_uncertainty": fmean(self.uncertainty) if self.uncertainty else None,
            "mean_prediction_error": fmean(self.prediction_error) if self.prediction_error else None,
            "mean_absolute_prediction_error": fmean(abs(value) for value in self.prediction_error) if self.prediction_error else None,
            "body_means": {key: fmean(values) for key, values in self.body.items()},
            "evidence": {
                "source_lines": [self.start_line, self.end_line],
                "ticks": [self.start_tick, self.end_tick],
            },
            "window_count": 1,
        }


class BehavioralEpochDetector:
    """Streaming segmentation using several behavioral signals, not a single label."""

    def __init__(self, window_size: int = 100, change_threshold: float = 0.38):
        if window_size < 1:
            raise ValueError("window_size must be >= 1")
        self.window_size = window_size
        self.change_threshold = change_threshold
        self.current: EpochWindow | None = None
        self.windows: list[dict[str, Any]] = []

    def observe(self, row: Mapping[str, Any]) -> None:
        tick = row.get("tick")
        if not isinstance(tick, int):
            return
        if self.current is None:
            line = (row.get("provenance") or {}).get("source_line")
            self.current = EpochWindow(tick, line, tick, line)
        self.current.observe(row)
        if self.current.samples >= self.window_size:
            self.windows.append(self.current.to_dict())
            self.current = None

    def finish(self) -> list[dict[str, Any]]:
        if self.current is not None:
            self.windows.append(self.current.to_dict())
            self.current = None
        epochs: list[dict[str, Any]] = []
        for window in self.windows:
            if not epochs or self._distance(epochs[-1], window) >= self.change_threshold:
                epochs.append(dict(window))
            else:
                self._merge(epochs[-1], window)
        for index, epoch in enumerate(epochs, start=1):
            epoch["epoch_id"] = index
            epoch["label"] = self._label(epoch)
            epoch["dominant_action"] = _dominant(epoch["action_counts"])
            epoch["dominant_object"] = _dominant(epoch["object_interaction_counts"])
        return epochs

    @staticmethod
    def _distance(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
        action_distance = _distribution_distance(left["action_counts"], right["action_counts"])
        object_distance = _distribution_distance(left["object_interaction_counts"], right["object_interaction_counts"])
        scalar_distance = 0.0
        for key in ("mean_selected_uncertainty", "mean_absolute_prediction_error"):
            a, b = left.get(key), right.get(key)
            if isinstance(a, (int, float)) and isinstance(b, (int, float)):
                scalar_distance += min(1.0, abs(a - b))
        body_keys = set(left.get("body_means", {})) & set(right.get("body_means", {}))
        body_distance = 0.0
        if body_keys:
            body_distance = sum(min(1.0, abs(left["body_means"][key] - right["body_means"][key])) for key in body_keys) / len(body_keys)
        return 0.5 * action_distance + 0.2 * object_distance + 0.15 * min(1.0, scalar_distance) + 0.15 * body_distance

    @staticmethod
    def _merge(target: dict[str, Any], source: Mapping[str, Any]) -> None:
        old_samples, new_samples = target["samples"], source["samples"]
        total = old_samples + new_samples
        for field in ("action_counts", "object_interaction_counts"):
            combined = Counter(target[field])
            combined.update(source[field])
            target[field] = dict(combined)
        for field in ("mean_selected_uncertainty", "mean_prediction_error", "mean_absolute_prediction_error"):
            a, b = target.get(field), source.get(field)
            if a is not None and b is not None:
                target[field] = (a * old_samples + b * new_samples) / total
            elif b is not None:
                target[field] = b
        for key in set(target["body_means"]) | set(source["body_means"]):
            a, b = target["body_means"].get(key), source["body_means"].get(key)
            if a is not None and b is not None:
                target["body_means"][key] = (a * old_samples + b * new_samples) / total
            elif b is not None:
                target["body_means"][key] = b
        target["end_tick"] = source["end_tick"]
        target["samples"] = total
        target["visited_position_count"] += source["visited_position_count"]
        target["window_count"] += source["window_count"]
        target["evidence"]["source_lines"][1] = source["evidence"]["source_lines"][1]
        target["evidence"]["ticks"][1] = source["evidence"]["ticks"][1]

    @staticmethod
    def _label(epoch: Mapping[str, Any]) -> str:
        samples = epoch["samples"] or 1
        actions = epoch["action_counts"]
        dominant = _dominant(actions)
        dominance = (actions.get(dominant, 0) / samples) if dominant else 0.0
        object_rate = sum(epoch["object_interaction_counts"].values()) / samples
        body = epoch.get("body_means", {})
        depleted = body.get("energy_reserve", 1.0) <= 0.33 or body.get("hydration", 1.0) <= 0.33 or body.get("fatigue", 0.0) >= 0.67
        mobility = sum(count for action, count in actions.items() if str(action).startswith("MOVE:")) / samples
        if depleted and mobility < 0.2:
            return "physiologically constrained low-mobility regime"
        if object_rate >= 0.35:
            return "interaction-dense regime"
        if mobility >= 0.55:
            return "high-mobility regime"
        if mobility <= 0.2:
            return "low-mobility regime"
        if dominance >= 0.7:
            return "action-persistent regime"
        if (epoch.get("mean_absolute_prediction_error") or 0.0) >= 0.35:
            return "high-error adaptation"
        return "mixed-mobility regime"


PhaseDetector = BehavioralEpochDetector
