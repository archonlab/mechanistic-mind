from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Any, Mapping

from .extractor import numeric


LEARNING_EVENT_TYPES = {
    "action_models": "LEARNED_ACTION_EFFECT",
    "object_cue_models": "LEARNED_OBJECT_CUE",
    "action_history_models": "NOVEL_SEQUENCE_LEARNED",
    "sequence_models": "NOVEL_SEQUENCE_LEARNED",
}


def _strengths(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        return {}
    result: dict[str, float] = {}
    for key, child in value.items():
        number = numeric(child)
        if number is not None:
            result[str(key)] = number
    return result


def _direct_associations(value: Any) -> set[str]:
    """Return only direct model entries; never recursively expand contexts/means."""
    if isinstance(value, Mapping):
        return {str(key) for key, child in value.items() if child not in ({}, [], None)}
    if isinstance(value, (list, tuple)):
        return {str(index) for index, child in enumerate(value) if child is not None}
    return set()


def _body_mode(key: str, value: Any) -> str | None:
    number = numeric(value)
    if number is None:
        return None
    if number <= 0.33:
        return "LOW"
    if number >= 0.67:
        return "HIGH"
    return "MID"


@dataclass
class MeaningfulEventDetector:
    habit_threshold: float = 0.75
    model_revision_delta: float = 0.25
    preference_delta: float = 0.25
    return_gap: int = 20
    sequence_repetitions: int = 3
    max_events: int = 2000
    events: list[dict[str, Any]] = field(default_factory=list)
    seen_actions: set[str] = field(default_factory=set)
    seen_objects: set[str] = field(default_factory=set)
    seen_learning: dict[str, set[str]] = field(default_factory=dict)
    seen_habits: set[str] = field(default_factory=set)
    last_object_tick: dict[str, int] = field(default_factory=dict)
    last_prediction: dict[str, tuple[float, int]] = field(default_factory=dict)
    last_value: dict[str, tuple[float, int]] = field(default_factory=dict)
    recent_error: dict[str, tuple[float, int]] = field(default_factory=dict)
    body_modes: dict[str, str] = field(default_factory=dict)
    prior_action: str | None = None
    sequence_counts: Counter[tuple[str, str]] = field(default_factory=Counter)
    emitted_sequences: set[tuple[str, str]] = field(default_factory=set)
    action_window: deque[str] = field(default_factory=lambda: deque(maxlen=20))
    exploration_mode: str | None = None
    maximum_error: dict[str, Any] | None = None

    def emit(self, row: Mapping[str, Any], event_type: str, evidence: dict[str, Any], confidence: float = 1.0) -> None:
        if len(self.events) >= self.max_events:
            return
        self.events.append({
            "tick": row.get("tick"),
            "agent": row.get("agent"),
            "type": event_type,
            "confidence": round(max(0.0, min(1.0, confidence)), 3),
            "evidence": evidence,
            "provenance": row.get("provenance"),
        })

    def observe(self, row: Mapping[str, Any]) -> None:
        tick = row.get("tick")
        if not isinstance(tick, int):
            return
        action = row.get("action")
        if isinstance(action, str):
            if action not in self.seen_actions:
                self.seen_actions.add(action)
                self.emit(row, "FIRST_ACTION", {"action": action})
            self._observe_sequence(row, action)
            self._observe_exploration(row, action)
        object_id = row.get("object_id")
        if isinstance(object_id, str):
            if object_id not in self.seen_objects:
                self.seen_objects.add(object_id)
                self.emit(row, "FIRST_OBJECT_INTERACTION", {"action": action, "object_id": object_id})
            elif tick - self.last_object_tick.get(object_id, tick) >= self.return_gap:
                self.emit(row, "RETURN_TO_KNOWN", {
                    "object_id": object_id,
                    "action": action,
                    "ticks_since_last_interaction": tick - self.last_object_tick[object_id],
                }, 0.9)
            self.last_object_tick[object_id] = tick
        self._observe_learning(row)
        self._observe_prediction(row)
        self._observe_value(row)
        self._observe_habits(row)
        self._observe_body(row)

    def _observe_learning(self, row: Mapping[str, Any]) -> None:
        learning = row.get("learning_models")
        if not isinstance(learning, Mapping):
            return
        for category, model in learning.items():
            associations = _direct_associations(model)
            seen = self.seen_learning.setdefault(str(category), set())
            for association in sorted(associations - seen):
                event_type = LEARNING_EVENT_TYPES.get(str(category), "LEARNED_ASSOCIATION")
                self.emit(row, event_type, {
                    "model_category": str(category),
                    "association": association,
                    "granularity": "direct_model_entry",
                }, 0.9)
            seen.update(associations)

    def _observe_prediction(self, row: Mapping[str, Any]) -> None:
        tick = int(row["tick"])
        action = row.get("prediction_error_action") or row.get("action")
        error = numeric(row.get("prediction_error"))
        if error is not None:
            candidate = {
                "tick": tick,
                "agent": row.get("agent"),
                "action": action,
                "value": error,
                "provenance": row.get("provenance"),
                "experienced_effects": row.get("experienced_effects"),
            }
            if self.maximum_error is None or abs(error) > abs(self.maximum_error["value"]):
                self.maximum_error = candidate
            if isinstance(action, str):
                self.recent_error[action] = (error, tick)
        prediction = numeric(row.get("selected_prediction"))
        if not isinstance(action, str) or prediction is None:
            return
        previous = self.last_prediction.get(action)
        if previous is not None:
            delta = prediction - previous[0]
            causal_error = self.recent_error.get(action)
            if abs(delta) >= self.model_revision_delta and causal_error and tick - causal_error[1] <= 10:
                self.emit(row, "MODEL_REVISION", {
                    "action": action,
                    "previous_prediction": previous[0],
                    "current_prediction": prediction,
                    "delta": delta,
                    "preceding_prediction_error": causal_error[0],
                    "error_tick": causal_error[1],
                    "lag_ticks": tick - causal_error[1],
                }, 0.95)
        self.last_prediction[action] = (prediction, tick)

    def _observe_value(self, row: Mapping[str, Any]) -> None:
        action = row.get("action")
        current = numeric(row.get("selected_value"))
        if not isinstance(action, str) or current is None:
            return
        previous = self.last_value.get(action)
        if previous is not None and abs(current - previous[0]) >= self.preference_delta:
            if previous[0] <= 0 < current:
                event_type = "PREFERENCE_ACQUIRED"
            elif previous[0] >= 0 > current:
                event_type = "PREFERENCE_LOST"
            else:
                event_type = "VALUE_REVISION"
            self.emit(row, event_type, {
                "action": action,
                "previous_value": previous[0],
                "current_value": current,
                "delta": current - previous[0],
                "previous_tick": previous[1],
            }, 0.85)
        self.last_value[action] = (current, int(row["tick"]))

    def _observe_habits(self, row: Mapping[str, Any]) -> None:
        for habit, strength in _strengths(row.get("habits")).items():
            if strength >= self.habit_threshold and habit not in self.seen_habits:
                self.seen_habits.add(habit)
                self.emit(row, "HABIT_EMERGED", {
                    "habit": habit,
                    "strength": strength,
                    "threshold": self.habit_threshold,
                }, 0.95)

    def _observe_body(self, row: Mapping[str, Any]) -> None:
        body = row.get("body_truth")
        if not isinstance(body, Mapping):
            return
        for key, value in body.items():
            mode = _body_mode(str(key), value)
            previous = self.body_modes.get(str(key))
            if mode and previous and mode != previous:
                self.emit(row, "PHYSIOLOGICAL_TRANSITION", {
                    "variable": str(key), "previous": previous, "current": mode, "value": numeric(value),
                }, 1.0)
            if mode:
                self.body_modes[str(key)] = mode

    def _observe_sequence(self, row: Mapping[str, Any], action: str) -> None:
        if self.prior_action is not None:
            pair = (self.prior_action, action)
            self.sequence_counts[pair] += 1
            if self.sequence_counts[pair] >= self.sequence_repetitions and pair not in self.emitted_sequences:
                self.emitted_sequences.add(pair)
                self.emit(row, "REPEATED_ACTION_SEQUENCE", {
                    "sequence": list(pair), "observations": self.sequence_counts[pair],
                }, 0.8)
        self.prior_action = action

    def _observe_exploration(self, row: Mapping[str, Any], action: str) -> None:
        self.action_window.append(action)
        if len(self.action_window) < self.action_window.maxlen:
            return
        diversity = len(set(self.action_window)) / len(self.action_window)
        mode = "EXPLORATION" if diversity >= 0.35 else "EXPLOITATION"
        if self.exploration_mode and mode != self.exploration_mode:
            self.emit(row, "EXPLORATION_SHIFT", {
                "previous": self.exploration_mode, "current": mode,
                "window_ticks": len(self.action_window), "action_diversity": round(diversity, 3),
            }, 0.8)
        self.exploration_mode = mode

    def finish(self) -> list[dict[str, Any]]:
        if self.maximum_error is not None:
            item = self.maximum_error
            self.events.append({
                "tick": item["tick"], "agent": item["agent"],
                "type": "MAJOR_PREDICTION_ERROR", "confidence": 1.0,
                "evidence": {
                    "prediction_error": item["value"], "action": item["action"],
                    "experienced_effects": item["experienced_effects"], "scope": "run_maximum_absolute_error",
                },
                "provenance": item["provenance"],
            })
        return sorted(self.events, key=lambda event: (event.get("tick", -1), event["type"]))


# Compatibility name for code importing the v0.1 detector.
EventDetector = MeaningfulEventDetector
