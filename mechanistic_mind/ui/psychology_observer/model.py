"""Telemetry projection model for the Mechanistic Mind observer UI."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
import json
from typing import Any


ORGANISM_WORLD_PROFILE = "ORGANISM_X_WORLD"


@dataclass(frozen=True, slots=True)
class PsychologyTickView:
    tick: int
    agent_id: str
    action: str
    action_source: str
    mechanism_id: str
    profile: str

    # Decision-time information actually available to the agent.
    observation: dict[str, Any]
    accessible_signals: dict[str, float]
    last_experienced_effects: dict[str, float]

    # Observer-only objective state after the current action.
    objective_world: dict[str, Any]
    world_objects: dict[str, Any]
    world_obstacles: dict[str, Any]
    objective_position: tuple[int, int] | None
    body_truth: dict[str, float]
    body_truth_before: dict[str, float]
    body_truth_after: dict[str, float]
    current_experienced_effects: dict[str, float]
    world_action_receipt: dict[str, Any]
    objective_context_receipt: dict[str, Any]
    exogenous_event_receipts: tuple[dict[str, Any], ...]
    delayed_effect_receipts: tuple[dict[str, Any], ...]

    # Psyche state/model after the decision.
    mechanism_state: dict[str, Any]
    psyche_internal: dict[str, Any]
    attention: dict[str, Any]
    learning_models: dict[str, Any]
    memory_episode_count: int
    memory_capacity: int | None
    memory_mode: str
    memory_pattern_count: int
    memory_novel_fragment_count: int
    retrieval: dict[str, Any]
    retention: dict[str, Any]
    memory_events: tuple[dict[str, Any], ...]
    perceptual_dynamics: dict[str, Any]
    known_positions: dict[str, int]
    known_objects: dict[str, Any]
    known_obstacles: dict[str, Any]
    object_cue_models: dict[str, Any]
    obstacle_cue_models: dict[str, Any]
    predictions: dict[str, Any]
    prediction_error: dict[str, float]
    prediction_error_magnitude: float | None
    uncertainty: dict[str, float]
    goals: dict[str, Any]
    global_state: dict[str, Any]
    self_model: dict[str, Any]
    habits: dict[str, float]
    values: dict[str, Any]

    selected_action: str
    selection_reason: str
    selection_score: float | None
    selected_prediction: dict[str, float]
    selected_prediction_source: str
    selected_prediction_scope: str
    selected_context_sample_count: int | None
    physiology_context: str
    selected_uncertainty: float | None
    selected_value: float | None
    selected_habit: float | None

    stage_trace: tuple[str, ...]
    module_versions: dict[str, str]

    model_world_divergences: tuple[dict[str, Any], ...]
    unknown_world_objects: tuple[str, ...]

    @property
    def progress(self) -> float | None:
        return _float_or_none(self.objective_world.get("total_progress"))

    @property
    def random_event_count(self) -> int:
        return _int_or_none(
            self.objective_world.get("random_event_count")
        ) or 0

    @property
    def width(self) -> int:
        return _int_or_none(self.objective_world.get("width")) or 1

    @property
    def height(self) -> int:
        return _int_or_none(self.objective_world.get("height")) or 1

    @property
    def blocked(self) -> tuple[tuple[int, int], ...]:
        result = []
        for value in self.objective_world.get("blocked", []):
            position = _position(value)
            if position is not None:
                result.append(position)
        return tuple(result)

    @property
    def integrated_layers(self) -> dict[str, Any]:
        """Mechanistic integrated state; observer-only truth stays elsewhere."""
        value = self.mechanism_state.get("integrated")
        return deepcopy(value) if isinstance(value, dict) else {}

    @property
    def causal_trace(self) -> dict[str, Any]:
        value = self.integrated_layers.get("trace")
        return deepcopy(value) if isinstance(value, dict) else {"events": [], "edges": []}

    @property
    def mechanism_configuration(self) -> dict[str, Any]:
        value = self.integrated_layers.get("config")
        return deepcopy(value) if isinstance(value, dict) else {}


@dataclass(slots=True)
class PsychologyRunView:
    source_run_id: str | None = None
    engine_version: str | None = None
    seed: int | None = None
    world_type: str | None = None
    mechanism_versions: dict[str, str] = field(default_factory=dict)
    run_config: dict[str, Any] = field(default_factory=dict)
    ticks: list[PsychologyTickView] = field(default_factory=list)
    completed: bool = False
    final_tick: int | None = None

    @property
    def latest(self) -> PsychologyTickView | None:
        return self.ticks[-1] if self.ticks else None


class PsychologyTelemetryProjector:
    """Project canonical Mechanistic Mind v0.3 JSONL into UI state."""

    def __init__(self) -> None:
        self.view = PsychologyRunView()
        self._objective_objects: dict[str, Any] = {}
        self._objective_obstacles: dict[str, Any] = {}
        self.selected_agent_id: str | None = None
        self.available_agent_ids: list[str] = []

    def apply(self, envelope: dict[str, Any]) -> PsychologyRunView:
        record_type = envelope.get("record_type")
        payload = envelope.get("payload")
        if not isinstance(payload, dict):
            return self.view

        if record_type == "run_metadata":
            self.view.source_run_id = _text_or_none(payload.get("run_id"))
            self.view.engine_version = _text_or_none(payload.get("engine_version"))
            self.view.seed = _int_or_none(payload.get("seed"))
            self.view.world_type = _text_or_none(payload.get("world_type"))
            versions = payload.get("mechanism_versions")
            if isinstance(versions, dict):
                self.view.mechanism_versions = {
                    str(key): str(value) for key, value in versions.items()
                }
            config = payload.get("run_config", payload.get("config"))
            if isinstance(config, dict):
                self.view.run_config = deepcopy(config)
            return self.view

        if record_type == "tick":
            truth = payload.get("state_after", {}).get("world", {}).get("variables", {}).get("world", {})
            if isinstance(truth, dict):
                if not truth.get("object_delta"):
                    self._objective_objects = {}
                if not truth.get("obstacle_delta"):
                    self._objective_obstacles = {}
                self._objective_objects.update(_mapping(truth.get("objects")))
                self._objective_obstacles.update(_mapping(truth.get("obstacles")))
                truth["objects"] = deepcopy(self._objective_objects)
                truth["obstacles"] = deepcopy(self._objective_obstacles)
            actions = payload.get("actions")
            if isinstance(actions, dict) and actions:
                self.available_agent_ids = sorted(str(k) for k in actions)
            preferred = self.selected_agent_id
            if preferred is None and self.available_agent_ids:
                preferred = self.available_agent_ids[0]
            self.view.ticks.append(project_tick(payload, agent_id=preferred))
            return self.view

        if record_type == "run_summary":
            self.view.completed = bool(payload.get("completed", False))
            self.view.final_tick = _int_or_none(payload.get("final_tick"))
            return self.view

        return self.view


def _text_or_none(value: Any) -> str | None:
    text = str(value or "").strip()
    return text or None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _mapping(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _numeric_mapping(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): float(item)
        for key, item in value.items()
        if isinstance(item, (int, float)) and not isinstance(item, bool)
    }


def _position(value: Any) -> tuple[int, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(item, int) for item in value)
    ):
        return int(value[0]), int(value[1])
    return None


def _first_mapping(mapping: Any) -> tuple[str, dict[str, Any]]:
    if not isinstance(mapping, dict) or not mapping:
        return "", {}
    key = sorted(str(item) for item in mapping)[0]
    return key, _mapping(mapping.get(key))


def _state_variables(payload: dict[str, Any], state_key: str) -> dict[str, Any]:
    state = payload.get(state_key)
    if not isinstance(state, dict):
        return {}
    world = state.get("world")
    if not isinstance(world, dict):
        return {}
    return _mapping(world.get("variables"))


def _psyche_state(
    payload: dict[str, Any],
    *,
    agent_id: str,
    mechanism_id: str,
) -> dict[str, Any]:
    state_after = payload.get("state_after")
    if not isinstance(state_after, dict):
        return {}
    agents = state_after.get("agents")
    if not isinstance(agents, dict):
        return {}
    agent = agents.get(agent_id)
    if not isinstance(agent, dict):
        return {}
    mechanism_states = agent.get("mechanism_states")
    if not isinstance(mechanism_states, dict):
        return {}
    return _mapping(mechanism_states.get(mechanism_id))


def _last_history(
    outer_variables: dict[str, Any],
    *,
    agent_id: str | None = None,
) -> dict[str, Any]:
    rows = outer_variables.get("developmental_history")
    if not isinstance(rows, list) or not rows:
        return {}
    if agent_id is not None:
        for row in reversed(rows):
            if isinstance(row, dict) and row.get("agent_id") == agent_id:
                return _mapping(row)
        # Legacy single-agent rows omit agent_id.
        tagged = [
            row for row in rows
            if isinstance(row, dict) and row.get("agent_id") not in (None, "")
        ]
        if not tagged and isinstance(rows[-1], dict):
            return _mapping(rows[-1])
        return {}
    if isinstance(rows[-1], dict):
        return _mapping(rows[-1])
    return {}


def _selected_total(values: dict[str, Any], action: str) -> float | None:
    record = values.get(action)
    if not isinstance(record, dict):
        return None
    return _float_or_none(record.get("base_total"))


def _model_divergences(
    known_objects: dict[str, Any],
    world_objects: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for object_id, memory_record in sorted(known_objects.items()):
        if not isinstance(memory_record, dict):
            continue
        memory_position = _position(memory_record.get("position"))
        truth_record = world_objects.get(object_id)
        if not isinstance(truth_record, dict):
            rows.append(
                {
                    "entity_kind": "OBJECT",
                    "object_id": str(object_id),
                    "kind": "OBJECT_ABSENT_FROM_WORLD",
                    "memory_position": memory_position,
                    "world_position": None,
                }
            )
            continue
        world_position = _position(truth_record.get("position"))
        if truth_record.get("active", True) is False:
            rows.append(
                {
                    "entity_kind": "OBJECT",
                    "object_id": str(object_id),
                    "kind": "OBJECT_INACTIVE",
                    "memory_position": memory_position,
                    "world_position": world_position,
                }
            )
        elif memory_position != world_position:
            rows.append(
                {
                    "entity_kind": "OBJECT",
                    "object_id": str(object_id),
                    "kind": "POSITION_MISMATCH",
                    "memory_position": memory_position,
                    "world_position": world_position,
                }
            )
    return tuple(rows)


def _obstacle_divergences(
    known_obstacles: dict[str, Any],
    world_obstacles: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for obstacle_id, memory_record in sorted(known_obstacles.items()):
        if not isinstance(memory_record, dict):
            continue
        memory_position = _position(memory_record.get("position"))
        truth_record = world_obstacles.get(obstacle_id)
        if not isinstance(truth_record, dict):
            rows.append({
                "entity_kind": "OBSTACLE",
                "object_id": str(obstacle_id),
                "kind": "OBSTACLE_ABSENT_FROM_WORLD",
                "memory_position": memory_position,
                "world_position": None,
            })
            continue
        world_position = _position(truth_record.get("position"))
        if truth_record.get("active", True) is False:
            rows.append({
                "entity_kind": "OBSTACLE",
                "object_id": str(obstacle_id),
                "kind": "OBSTACLE_INACTIVE",
                "memory_position": memory_position,
                "world_position": world_position,
            })
        elif memory_position != world_position:
            rows.append({
                "entity_kind": "OBSTACLE",
                "object_id": str(obstacle_id),
                "kind": "OBSTACLE_POSITION_MISMATCH",
                "memory_position": memory_position,
                "world_position": world_position,
            })
    return tuple(rows)


def project_tick(
    payload: dict[str, Any],
    *,
    agent_id: str | None = None,
) -> PsychologyTickView:
    tick = int(payload.get("tick", 0))
    actions = payload.get("actions")
    if agent_id is not None and isinstance(actions, dict) and agent_id in actions:
        action_payload = actions.get(agent_id) or {}
        if not isinstance(action_payload, dict):
            action_payload = {"kind": str(action_payload)}
    else:
        agent_id, action_payload = _first_mapping(actions)
    action = str(action_payload.get("kind") or "WAIT")

    observations = payload.get("observations")
    observation_payload = (
        observations.get(agent_id, {})
        if isinstance(observations, dict)
        else {}
    )
    observation = _mapping(
        observation_payload.get("data")
        if isinstance(observation_payload, dict)
        else {}
    )

    signals_by_agent = payload.get("signals")
    agent_signals = (
        signals_by_agent.get(agent_id, {})
        if isinstance(signals_by_agent, dict)
        else {}
    )
    mechanism_id, raw_signals = _first_mapping(agent_signals)
    whole = _mapping(raw_signals.get("whole_psyche"))

    action_sources = payload.get("action_sources")
    action_source = (
        str(action_sources.get(agent_id) or "UNKNOWN")
        if isinstance(action_sources, dict)
        else "UNKNOWN"
    )

    outer_before = _state_variables(payload, "state_before")
    outer_after = _state_variables(payload, "state_after")
    objective_world = _mapping(outer_after.get("world"))
    world_objects = _mapping(objective_world.get("objects"))
    world_obstacles = _mapping(objective_world.get("obstacles"))

    bodies = _mapping(outer_after.get("bodies"))
    body_truth = _numeric_mapping(bodies.get(agent_id))

    history = _last_history(outer_after, agent_id=agent_id)
    body_truth_before = _numeric_mapping(history.get("body_truth_before"))
    body_truth_after = _numeric_mapping(history.get("body_truth_after"))
    current_experienced_effects = _numeric_mapping(
        history.get("experienced_effects")
    )
    action_receipt = _mapping(history.get("world_action_receipt"))
    context_receipt = _mapping(history.get("objective_context_receipt"))

    exogenous = tuple(
        _mapping(item)
        for item in history.get("exogenous_event_receipts", [])
        if isinstance(item, dict)
    )
    delayed = tuple(
        _mapping(item)
        for item in history.get("delayed_effect_receipts", [])
        if isinstance(item, dict)
    )

    mechanism_state = _psyche_state(
        payload,
        agent_id=agent_id,
        mechanism_id=mechanism_id,
    )
    persisted_psyche = _mapping(mechanism_state.get("psyche"))
    bounded_summary = _mapping(raw_signals.get("memory_summary"))
    bounded_retrieval = _mapping(raw_signals.get("retrieval"))
    bounded_retention = _mapping(raw_signals.get("retention"))
    bounded_mode = bool(bounded_summary)

    internal = _mapping(whole.get("internal"))
    attention = _mapping(whole.get("attention"))
    learning = _mapping(
        whole.get("learning")
        if isinstance(whole.get("learning"), dict)
        else persisted_psyche.get("learning")
    )
    if bounded_mode:
        memory = _mapping(mechanism_state.get("memory"))
    else:
        memory = _mapping(
            whole.get("memory")
            if isinstance(whole.get("memory"), dict)
            else persisted_psyche.get("memory")
        )
    predictions_container = _mapping(whole.get("predictions"))
    predictions = (
        _mapping(raw_signals.get("predictions"))
        if bounded_mode
        else _mapping(predictions_container.get("by_action"))
    )
    prediction_error_container = _mapping(whole.get("prediction_errors"))
    prediction_error = _numeric_mapping(prediction_error_container.get("last"))
    uncertainty = _numeric_mapping(
        _mapping(whole.get("uncertainty")).get("by_action")
    )
    goals = _mapping(whole.get("goals"))
    global_state = _mapping(whole.get("global_state"))
    self_model = _mapping(whole.get("self_model"))
    habits = _numeric_mapping(
        _mapping(whole.get("habits")).get("strength")
    )
    values = _mapping(
        _mapping(whole.get("values")).get("by_action")
    )

    spatial = _mapping(memory.get("spatial"))
    known_positions = {
        str(key): int(value)
        for key, value in _mapping(spatial.get("visited")).items()
        if isinstance(value, int)
    }
    known_objects = _mapping(spatial.get("objects"))
    known_obstacles = _mapping(spatial.get("obstacles"))
    object_cue_models = _mapping(learning.get("object_cue_models"))
    obstacle_cue_models = _mapping(learning.get("obstacle_cue_models"))

    selection = _mapping(whole.get("selection"))
    selected_action = str(
        raw_signals.get("selected_action")
        if bounded_mode
        else selection.get("action") or action
    )
    selected_prediction_raw = _mapping(predictions.get(selected_action))
    selected_prediction = _numeric_mapping(
        selected_prediction_raw.get("expected")
        if bounded_mode
        else selected_prediction_raw
    )
    selected_prediction_source = str(
        bounded_retrieval.get("selected_prediction_source")
        if bounded_mode
        else selected_prediction_raw.get("__prediction_source") or "UNKNOWN"
    )
    selected_prediction_scope = str(
        bounded_retrieval.get("selected_evidence_status")
        if bounded_mode
        else selected_prediction_raw.get("__prediction_scope") or "UNKNOWN"
    )
    selected_context_sample_count = _int_or_none(
        selected_prediction_raw.get("samples")
        if bounded_mode
        else selected_prediction_raw.get("__context_sample_count")
    )
    physiology_context = str(
        selected_prediction_raw.get("__physiology_context")
        or _mapping(whole.get("uncertainty")).get("physiology_context")
        or ""
    )
    selected_uncertainty = (
        1.0
        - float(bounded_retrieval.get("selected_prediction_confidence", 0.0))
        if bounded_mode
        else _float_or_none(uncertainty.get(selected_action))
    )
    selected_value = (
        _float_or_none(bounded_retrieval.get("selected_prediction_value"))
        if bounded_mode
        else _selected_total(values, selected_action)
    )
    selected_habit = _float_or_none(habits.get(selected_action))

    objective_position = _position(
        _mapping(objective_world.get("agent_positions")).get(agent_id)
    )
    divergences = (
        _model_divergences(known_objects, world_objects)
        + _obstacle_divergences(known_obstacles, world_obstacles)
    )
    unknown_world_objects = tuple(
        object_id
        for object_id in sorted(world_objects)
        if object_id not in known_objects
    )

    return PsychologyTickView(
        tick=tick,
        agent_id=agent_id,
        action=action,
        action_source=action_source,
        mechanism_id=mechanism_id,
        profile=ORGANISM_WORLD_PROFILE,
        observation=observation,
        accessible_signals=_numeric_mapping(observation.get("interoception")),
        last_experienced_effects=_numeric_mapping(
            observation.get("last_experienced_effects")
        ),
        objective_world=objective_world,
        world_objects=world_objects,
        world_obstacles=world_obstacles,
        objective_position=objective_position,
        body_truth=body_truth,
        body_truth_before=body_truth_before,
        body_truth_after=body_truth_after,
        current_experienced_effects=current_experienced_effects,
        world_action_receipt=action_receipt,
        objective_context_receipt=context_receipt,
        exogenous_event_receipts=exogenous,
        delayed_effect_receipts=delayed,
        mechanism_state=mechanism_state,
        psyche_internal=internal,
        attention=attention,
        learning_models=_mapping(learning.get("action_models")),
        memory_episode_count=(
            int(bounded_summary.get("episodic_count", 0))
            if bounded_mode
            else len(memory.get("episodes", []))
            if isinstance(memory.get("episodes"), list)
            else 0
        ),
        memory_capacity=_int_or_none(
            bounded_summary.get("episodic_capacity")
            if bounded_mode
            else memory.get("max_episodes")
        ),
        memory_mode=(
            str(bounded_summary.get("mode") or "BOUNDED")
            if bounded_mode
            else "LEGACY_PSYCHE_V03"
        ),
        memory_pattern_count=(
            int(bounded_summary.get("pattern_count", 0))
            if bounded_mode
            else 0
        ),
        memory_novel_fragment_count=(
            int(bounded_summary.get("novel_fragment_count", 0))
            if bounded_mode
            else 0
        ),
        retrieval=bounded_retrieval,
        retention=bounded_retention,
        memory_events=tuple(
            _mapping(item)
            for item in raw_signals.get("memory_events", [])
            if isinstance(item, dict)
        ),
        perceptual_dynamics=_mapping(bounded_summary.get("perceptual_dynamics")),
        known_positions=known_positions,
        known_objects=known_objects,
        known_obstacles=known_obstacles,
        object_cue_models=object_cue_models,
        obstacle_cue_models=obstacle_cue_models,
        predictions=predictions,
        prediction_error=prediction_error,
        prediction_error_magnitude=(
            _float_or_none(bounded_summary.get("last_prediction_error"))
            if bounded_mode
            else _float_or_none(prediction_error_container.get("magnitude"))
        ),
        uncertainty=uncertainty,
        goals=goals,
        global_state=global_state,
        self_model=self_model,
        habits=habits,
        values=values,
        selected_action=selected_action,
        selection_reason=(
            "BOUNDED_" + selected_prediction_source
            if bounded_mode
            else str(selection.get("reason") or "")
        ),
        selection_score=(
            selected_value
            if bounded_mode
            else _float_or_none(selection.get("score"))
        ),
        selected_prediction=selected_prediction,
        selected_prediction_source=selected_prediction_source,
        selected_prediction_scope=selected_prediction_scope,
        selected_context_sample_count=selected_context_sample_count,
        physiology_context=physiology_context,
        selected_uncertainty=selected_uncertainty,
        selected_value=selected_value,
        selected_habit=selected_habit,
        stage_trace=tuple(
            str(item)
            for item in (
                bounded_retrieval.get("stage_trace", ())
                if bounded_mode
                else whole.get("stage_trace", ())
            )
        ),
        module_versions={
            str(key): str(value)
            for key, value in _mapping(whole.get("module_versions")).items()
        },
        model_world_divergences=divergences,
        unknown_world_objects=unknown_world_objects,
    )


def read_jsonl_since(
    path: Path,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """Read complete JSONL records appended since byte offset."""
    path = Path(path)
    if not path.exists():
        return [], offset

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        handle.seek(offset)
        while True:
            before = handle.tell()
            line = handle.readline()
            if not line:
                return records, handle.tell()
            if not line.endswith("\n"):
                return records, before
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                records.append(value)
