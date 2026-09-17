from __future__ import annotations

from copy import deepcopy
from math import sqrt
import heapq
from typing import Any

from mechanistic_mind.agent import Action
from .contracts import (
    PsycheActionCandidate,
    PsycheContext,
    PsycheModule,
    PsycheOutput,
    PsycheSelection,
    PsycheStage,
    PsycheUpdate,
)
from .modules import (
    GoalMaintenanceModule,
    HabitModule,
    PerceptionModule,
    SelfModelModule,
)


_SIGNAL_KEYS = (
    "energy_signal",
    "hydration_signal",
    "fatigue_signal",
    "discomfort_signal",
    "effort_signal",
)


def _mapping(value: Any) -> dict[str, Any]:
    return deepcopy(value) if isinstance(value, dict) else {}


def _numeric(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(k): float(v)
        for k, v in value.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def _position(value: Any) -> tuple[int, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(v, int) for v in value)
    ):
        return int(value[0]), int(value[1])
    return None


def _move_destination(action: str) -> tuple[int, int] | None:
    if not action.startswith("MOVE:"):
        return None
    try:
        x, y = action.split(":", 1)[1].split(",", 1)
        return int(x), int(y)
    except Exception:
        return None


def _manhattan(a: tuple[int, int], b: tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


_CONTEXT_SIGNAL_KEYS = (
    "energy_signal",
    "hydration_signal",
    "fatigue_signal",
    "discomfort_signal",
)


def _context_band(value: float) -> str:
    value = max(0.0, min(1.0, float(value)))
    if value < 1.0 / 3.0:
        return "LOW"
    if value < 2.0 / 3.0:
        return "MID"
    return "HIGH"


def _physiology_context(
    signals: dict[str, float],
) -> dict[str, Any]:
    snapshot = {
        key: float(signals.get(key, 0.0))
        for key in _CONTEXT_SIGNAL_KEYS
    }
    key = "|".join(
        f"{name}:{_context_band(snapshot[name])}"
        for name in _CONTEXT_SIGNAL_KEYS
    )
    return {
        "key": key,
        "signals": snapshot,
    }


def _context_record(
    record: dict[str, Any],
    context_key: str | None,
) -> dict[str, Any] | None:
    if not context_key:
        return None
    contexts = record.get("contexts")
    if not isinstance(contexts, dict):
        return None
    candidate = contexts.get(context_key)
    return candidate if isinstance(candidate, dict) else None


def _context_sample_count(
    record: dict[str, Any],
    context_key: str | None,
) -> int:
    contextual = _context_record(record, context_key)
    if contextual is not None:
        return int(contextual.get("count", 0))

    # Legacy v0.3.2 records had no context map. Treat them as known rather
    # than silently invalidating old saved states.
    if not isinstance(record.get("contexts"), dict):
        return int(record.get("count", 0))
    return 0


def _prediction_from_record(
    record: dict[str, Any],
    context_key: str | None,
) -> tuple[dict[str, float], str, int]:
    global_mean = _numeric(record.get("mean"))
    contextual = _context_record(record, context_key)
    if contextual is not None:
        contextual_mean = _numeric(contextual.get("mean"))
        if contextual_mean:
            return (
                contextual_mean,
                "CONTEXT",
                int(contextual.get("count", 0)),
            )
    return (
        global_mean,
        "GLOBAL_FALLBACK" if global_mean else "UNKNOWN",
        0 if isinstance(record.get("contexts"), dict) else int(
            record.get("count", 0)
        ),
    )



def _spatial_positions(spatial: dict[str, Any]) -> set[tuple[int, int]]:
    positions: set[tuple[int, int]] = set()
    visited = spatial.get("visited", {})
    if isinstance(visited, dict):
        for key in visited:
            try:
                x_text, y_text = str(key).split(",", 1)
                positions.add((int(x_text), int(y_text)))
            except Exception:
                continue
    for compartment in ("objects", "obstacles"):
        records = spatial.get(compartment, {})
        if isinstance(records, dict):
            for record in records.values():
                if isinstance(record, dict):
                    pos = _position(record.get("position"))
                    if pos is not None:
                        positions.add(pos)
    return positions


def _movement_regulatory_cost(
    destination: tuple[int, int],
    *,
    action_models: dict[str, Any],
    current_signals: dict[str, float],
    goals: dict[str, Any],
) -> float:
    record = action_models.get(
        f"MOVE:{destination[0]},{destination[1]}",
        {},
    )
    prediction = (
        _numeric(record.get("mean"))
        if isinstance(record, dict)
        else {}
    )
    if not prediction:
        return 0.0
    gain = _target_gain(
        prediction,
        current_signals,
        goals,
    )
    return max(0.0, -gain)


def _known_route_cost(
    start: tuple[int, int],
    target: tuple[int, int],
    *,
    known_positions: set[tuple[int, int]],
    action_models: dict[str, Any],
    current_signals: dict[str, float],
    goals: dict[str, Any],
) -> float | None:
    """Dijkstra on already known space.

    Learned adverse movement consequences are converted into an equivalent
    extra-path cost relative to ordinary learned movement. This lets a known
    safe detour compete with a shorter but previously harmful route.
    """

    if start == target:
        return 0.0

    known = set(known_positions)
    known.add(start)
    known.add(target)

    learned_costs = []
    for position in known:
        cost = _movement_regulatory_cost(
            position,
            action_models=action_models,
            current_signals=current_signals,
            goals=goals,
        )
        if cost > 1e-9:
            learned_costs.append(cost)

    # Typical movement cost anchors value units to "one extra step" without
    # inserting a psychological avoidance constant.
    baseline = (
        min(learned_costs)
        if learned_costs
        else 0.002
    )
    baseline = max(0.001, min(0.02, baseline))

    queue: list[tuple[float, tuple[int, int]]] = [(0.0, start)]
    best = {start: 0.0}

    while queue:
        cost_so_far, position = heapq.heappop(queue)
        if position == target:
            return cost_so_far
        if cost_so_far > best.get(position, float("inf")):
            continue

        x, y = position
        for neighbor in (
            (x + 1, y),
            (x - 1, y),
            (x, y + 1),
            (x, y - 1),
        ):
            if neighbor not in known:
                continue

            regulatory_cost = _movement_regulatory_cost(
                neighbor,
                action_models=action_models,
                current_signals=current_signals,
                goals=goals,
            )
            step_cost = 1.0 + regulatory_cost / baseline
            candidate = cost_so_far + step_cost
            if candidate < best.get(neighbor, float("inf")):
                best[neighbor] = candidate
                heapq.heappush(
                    queue,
                    (candidate, neighbor),
                )

    return None


def _target_gain(
    predicted: dict[str, float],
    current_signals: dict[str, float],
    goals: dict[str, Any],
) -> float:
    targets = _numeric(goals.get("signal_targets"))
    weights = _numeric(goals.get("signal_weights"))
    total = 0.0
    for key, target in targets.items():
        current = float(current_signals.get(key, target))
        delta_key = f"{key}_delta"
        predicted_delta = float(
            predicted.get(
                delta_key,
                predicted.get(key, 0.0),
            )
        )
        after = max(0.0, min(1.0, current + predicted_delta))
        before_error = (current - target) ** 2
        after_error = (after - target) ** 2
        total += (before_error - after_error) * float(weights.get(key, 1.0))
    return total


class OrganismRegulationModule(PsycheModule):
    module_id = "PSY-REGULATION-ORGANISM-V03"
    version = "0.3.2"
    stage = PsycheStage.REGULATION

    def process(self, context: PsycheContext) -> PsycheOutput:
        interoception = _numeric(context.observation.data.get("interoception"))
        targets = _numeric(context.state.goals.get("signal_targets"))
        pressure = {}
        weighted = []
        for key, target in targets.items():
            current = float(interoception.get(key, target))
            error = abs(current - target)
            pressure[key] = error
            weighted.append(error)
        tension = sum(weighted) / len(weighted) if weighted else 0.0

        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "internal",
                    "interoceptive_model",
                    interoception,
                ),
                PsycheUpdate(
                    "internal",
                    "need_pressure",
                    pressure,
                ),
                PsycheUpdate(
                    "global_state",
                    "tension",
                    tension,
                ),
            ),
            signals={
                "interoception": interoception,
                "need_pressure": pressure,
                "tension": tension,
            },
        )


class OrganismAttentionModule(PsycheModule):
    module_id = "PSY-ATTENTION-ORGANISM-V03"
    version = "0.3.2"
    stage = PsycheStage.ATTENTION

    def __init__(self, capacity: int = 8) -> None:
        self.capacity = max(1, int(capacity))

    def process(self, context: PsycheContext) -> PsycheOutput:
        percept = _mapping(context.state.percept.get("current"))
        priority = (
            "available_actions",
            "position",
            "visible_objects",
            "visible_obstacles",
            "interoception",
            "last_action",
            "last_experienced_effects",
            "context",
        )
        selected = {}
        for key in priority:
            if key in percept and len(selected) < self.capacity:
                selected[key] = deepcopy(percept[key])
        return PsycheOutput(
            updates=(
                PsycheUpdate("attention", "current", selected),
                PsycheUpdate("attention", "capacity", self.capacity),
            ),
            signals={
                "selected_keys": list(selected),
                "capacity": self.capacity,
            },
        )

class OrganismLearningModule(PsycheModule):
    module_id = "PSY-LEARNING-ORGANISM-V03"
    version = "0.3.4"
    stage = PsycheStage.LEARNING

    @staticmethod
    def _update_mean(
        record: dict[str, Any],
        effects: dict[str, float],
    ) -> tuple[int, dict[str, float]]:
        count = int(record.get("count", 0)) + 1
        means = _numeric(record.get("mean"))
        for effect_key, value in effects.items():
            old = float(means.get(effect_key, 0.0))
            means[effect_key] = old + (value - old) / count
        record["count"] = count
        record["mean"] = means
        return count, means

    @classmethod
    def _update_model(
        cls,
        models: dict[str, Any],
        key: str,
        effects: dict[str, float],
        *,
        state_context: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, float], int]:
        record = deepcopy(
            models.get(
                key,
                {
                    "count": 0,
                    "mean": {},
                    "contexts": {},
                },
            )
        )
        count, means = cls._update_mean(record, effects)

        contexts = record.get("contexts")
        if not isinstance(contexts, dict):
            contexts = {}

        context_count = 0
        if isinstance(state_context, dict):
            context_key = str(
                state_context.get("key") or ""
            ).strip()
            if context_key:
                contextual = deepcopy(
                    contexts.get(
                        context_key,
                        {
                            "count": 0,
                            "mean": {},
                            "state_context": deepcopy(
                                state_context
                            ),
                        },
                    )
                )
                context_count, _context_mean = cls._update_mean(
                    contextual,
                    effects,
                )
                contextual["state_context"] = deepcopy(
                    state_context
                )
                contexts[context_key] = contextual

        record["contexts"] = contexts
        models[key] = record
        return count, means, context_count

    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = _mapping(context.state.attention.get("current"))
        action = attended.get("last_action")
        effects = _numeric(attended.get("last_experienced_effects"))

        previous_selection = context.state.predictions.get(
            "last_selected"
        )
        state_context = None
        if (
            isinstance(previous_selection, dict)
            and previous_selection.get("action") == action
        ):
            raw_context = previous_selection.get("state_context")
            if isinstance(raw_context, dict):
                state_context = deepcopy(raw_context)

        action_models = deepcopy(
            context.state.learning.get("action_models", {})
        )
        object_cue_models = deepcopy(
            context.state.learning.get("object_cue_models", {})
        )
        obstacle_cue_models = deepcopy(
            context.state.learning.get("obstacle_cue_models", {})
        )
        history_models = deepcopy(
            context.state.learning.get("action_history_models", {})
        )

        if not isinstance(action, str) or not effects:
            return PsycheOutput(
                signals={
                    "updated_action": None,
                    "model_count": len(action_models),
                    "object_cue_model_count": len(object_cue_models),
                    "obstacle_cue_model_count": len(obstacle_cue_models),
                    "action_history_model_count": len(history_models),
                }
            )

        count, means, context_count = self._update_model(
            action_models,
            action,
            effects,
            state_context=state_context,
        )

        # Learn ordinary action n-grams up to length three. The keys contain
        # only experienced action symbols; there are no privileged sequence
        # names, completion flags, or hand-authored templates.
        episodes = context.state.memory.get("episodes", [])
        prior_actions = [
            str(row.get("action"))
            for row in episodes
            if isinstance(row, dict) and isinstance(row.get("action"), str)
        ] if isinstance(episodes, list) else []
        history_updates: list[str] = []
        for length in (2, 3):
            needed = length - 1
            if len(prior_actions) < needed:
                continue
            sequence = prior_actions[-needed:] + [action]
            sequence_key = "\u241f".join(sequence)
            self._update_model(
                history_models,
                sequence_key,
                effects,
                state_context=state_context,
            )
            history_updates.append(sequence_key)

        learned_object_cue = None
        learned_obstacle_cue = None

        if action.startswith("USE:"):
            object_id = action.split(":", 1)[1]
            visible_objects = attended.get("visible_objects")
            if isinstance(visible_objects, list):
                for item in visible_objects:
                    if (
                        isinstance(item, dict)
                        and str(item.get("id") or "") == object_id
                    ):
                        cue = str(
                            item.get("cue_signature")
                            or "GENERIC_OBJECT"
                        )
                        self._update_model(
                            object_cue_models,
                            cue,
                            effects,
                            state_context=state_context,
                        )
                        learned_object_cue = cue
                        break

        destination = _move_destination(action)
        current_position = _position(attended.get("position"))
        if (
            destination is not None
            and current_position == destination
        ):
            visible_obstacles = attended.get("visible_obstacles")
            if isinstance(visible_obstacles, list):
                for item in visible_obstacles:
                    if not isinstance(item, dict):
                        continue
                    obstacle_position = _position(
                        item.get("position")
                    )
                    if obstacle_position != current_position:
                        continue
                    cue = str(
                        item.get("cue_signature")
                        or "GENERIC_OBSTACLE"
                    )
                    self._update_model(
                        obstacle_cue_models,
                        cue,
                        effects,
                        state_context=state_context,
                    )
                    learned_obstacle_cue = cue
                    break

        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "learning",
                    "action_models",
                    action_models,
                ),
                PsycheUpdate(
                    "learning",
                    "object_cue_models",
                    object_cue_models,
                ),
                PsycheUpdate(
                    "learning",
                    "obstacle_cue_models",
                    obstacle_cue_models,
                ),
                PsycheUpdate(
                    "learning",
                    "action_history_models",
                    history_models,
                ),
            ),
            signals={
                "updated_action": action,
                "sample_count": count,
                "context_sample_count": context_count,
                "state_context": deepcopy(state_context),
                "means": means,
                "learned_object_cue": learned_object_cue,
                "learned_obstacle_cue": learned_obstacle_cue,
                "updated_action_histories": history_updates,
            },
        )

class OrganismSpatialMemoryModule(PsycheModule):
    module_id = "PSY-MEMORY-ORGANISM-V03"
    version = "0.3.2"
    stage = PsycheStage.MEMORY

    def process(self, context: PsycheContext) -> PsycheOutput:
        memory = context.state.memory
        episodes = list(deepcopy(memory.get("episodes", [])))
        max_episodes = int(memory.get("max_episodes", 48))
        spatial = deepcopy(
            memory.get(
                "spatial",
                {
                    "visited": {},
                    "objects": {},
                    "obstacles": {},
                },
            )
        )
        visited = dict(spatial.get("visited", {}))
        objects = dict(spatial.get("objects", {}))
        obstacles = dict(spatial.get("obstacles", {}))

        attended = _mapping(context.state.attention.get("current"))
        position = _position(attended.get("position"))
        if position is not None:
            key = f"{position[0]},{position[1]}"
            visited[key] = int(visited.get(key, 0)) + 1

        visible_objects = attended.get("visible_objects")
        if isinstance(visible_objects, list):
            for item in visible_objects:
                if not isinstance(item, dict):
                    continue
                object_id = str(item.get("id") or "").strip()
                object_position = _position(item.get("position"))
                if not object_id or object_position is None:
                    continue
                objects[object_id] = {
                    "position": list(object_position),
                    "affordance": str(item.get("affordance") or "USE"),
                    "cue_signature": str(
                        item.get("cue_signature")
                        or "GENERIC_OBJECT"
                    ),
                    "cue_salience": float(
                        item.get("cue_salience", 0.5)
                    ),
                    "size": float(item.get("size", 0.35)),
                    "shape": str(item.get("shape") or "circle"),
                    "color": str(item.get("color") or "#d89b45"),
                    "opacity": float(item.get("opacity", 1.0)),
                    "brightness": float(item.get("brightness", 0.5)),
                    "signal": item.get("signal"),
                    "observable_state": deepcopy(
                        item.get("observable_state", {})
                        if isinstance(item.get("observable_state"), dict)
                        else {}
                    ),
                    "interaction_state": str(
                        item.get("interaction_state") or "FREE"
                    ),
                    "carried_by": item.get("carried_by"),
                    "last_seen_tick": context.tick,
                }

        visible_obstacles = attended.get("visible_obstacles")
        if isinstance(visible_obstacles, list):
            for item in visible_obstacles:
                if not isinstance(item, dict):
                    continue
                obstacle_id = str(item.get("id") or "").strip()
                obstacle_position = _position(item.get("position"))
                if not obstacle_id or obstacle_position is None:
                    continue
                obstacles[obstacle_id] = {
                    "position": list(obstacle_position),
                    "cue_signature": str(
                        item.get("cue_signature")
                        or "GENERIC_OBSTACLE"
                    ),
                    "cue_salience": float(
                        item.get("cue_salience", 0.5)
                    ),
                    "traversable": bool(
                        item.get("traversable", True)
                    ),
                    "last_seen_tick": context.tick,
                }

        if (
            attended.get("last_action") is not None
            and attended.get("last_experienced_effects") is not None
        ):
            episodes.append(
                {
                    "tick": context.tick,
                    "position": (
                        list(position)
                        if position is not None
                        else None
                    ),
                    "action": attended.get("last_action"),
                    "experienced_effects": deepcopy(
                        attended.get("last_experienced_effects")
                    ),
                    "visible_objects": deepcopy(
                        visible_objects
                        if isinstance(visible_objects, list)
                        else []
                    ),
                    "visible_obstacles": deepcopy(
                        visible_obstacles
                        if isinstance(visible_obstacles, list)
                        else []
                    ),
                }
            )
            episodes = episodes[-max_episodes:]

        return PsycheOutput(
            updates=(
                PsycheUpdate("memory", "episodes", episodes),
                PsycheUpdate(
                    "memory",
                    "spatial",
                    {
                        "visited": visited,
                        "objects": objects,
                        "obstacles": obstacles,
                    },
                ),
            ),
            signals={
                "episode_count": len(episodes),
                "known_positions": len(visited),
                "known_objects": len(objects),
                "known_obstacles": len(obstacles),
            },
        )

class OrganismPredictionModule(PsycheModule):
    module_id = "PSY-PREDICTION-ORGANISM-V03"
    version = "0.3.4"
    stage = PsycheStage.PREDICTION

    @staticmethod
    def _cue_prediction(
        models: dict[str, Any],
        cue: str | None,
        context_key: str,
    ) -> tuple[dict[str, float], str, int]:
        if not cue:
            return {}, "UNKNOWN", 0
        record = models.get(cue, {})
        if not isinstance(record, dict):
            return {}, "UNKNOWN", 0
        return _prediction_from_record(
            record,
            context_key,
        )

    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = _mapping(context.state.attention.get("current"))
        actions = attended.get("available_actions", ())
        current_position = _position(attended.get("position"))

        action_models = context.state.learning.get(
            "action_models",
            {},
        )
        object_cue_models = context.state.learning.get(
            "object_cue_models",
            {},
        )
        obstacle_cue_models = context.state.learning.get(
            "obstacle_cue_models",
            {},
        )
        history_models = context.state.learning.get(
            "action_history_models",
            {},
        )
        episodes = context.state.memory.get("episodes", [])
        gate = context.state.working.get("developmental_gate")
        if not isinstance(gate, dict):
            gate = context.state.memory.get("developmental")
        gate_factor = (
            float(gate.get("gate_factor", 1.0))
            if isinstance(gate, dict)
            else 1.0
        )
        # Early development: only short recent episode fragments influence
        # prediction; n-gram history models stay dormant until gate rises.
        if isinstance(episodes, list) and gate_factor < 0.95:
            recent_horizon = max(1, int(round(2 + gate_factor * 14)))
            episodes = episodes[-recent_horizon:]
        if gate_factor < 0.55:
            history_models = {}
        elif gate_factor < 0.95 and isinstance(history_models, dict):
            # Keep only shortest n-grams while integrating.
            history_models = {
                key: value
                for key, value in history_models.items()
                if isinstance(key, str) and key.count(">") <= 0
            }
        recent_actions = [
            str(row.get("action"))
            for row in episodes
            if isinstance(row, dict) and isinstance(row.get("action"), str)
        ] if isinstance(episodes, list) else []
        attended_last = attended.get("last_action")
        if isinstance(attended_last, str):
            recent_actions.append(attended_last)

        spatial = context.state.memory.get("spatial", {})
        objects = (
            spatial.get("objects", {})
            if isinstance(spatial, dict)
            else {}
        )
        obstacles = (
            spatial.get("obstacles", {})
            if isinstance(spatial, dict)
            else {}
        )

        visible_objects = {
            str(item.get("id")): item
            for item in attended.get("visible_objects", [])
            if isinstance(item, dict) and item.get("id") is not None
        }
        visible_obstacles = {
            tuple(item.get("position")): item
            for item in attended.get("visible_obstacles", [])
            if (
                isinstance(item, dict)
                and isinstance(item.get("position"), list)
                and len(item["position"]) == 2
            )
        }

        current_signals = _numeric(
            context.state.internal.get("interoceptive_model")
        )
        physiology_context = _physiology_context(
            current_signals
        )
        context_key = str(physiology_context["key"])

        known_positions = (
            _spatial_positions(spatial)
            if isinstance(spatial, dict)
            else set()
        )
        for raw_action in actions:
            destination = _move_destination(str(raw_action))
            if destination is not None:
                known_positions.add(destination)
        if current_position is not None:
            known_positions.add(current_position)

        tension = max(
            0.0,
            min(
                1.0,
                float(
                    context.state.global_state.get(
                        "tension",
                        0.0,
                    )
                ),
            ),
        )
        urgency = min(1.0, tension * 2.5)
        progress_weight = float(
            context.state.goals.get(
                "progress_weight",
                0.30,
            )
        )

        predictions = {}

        for raw_action in actions:
            action = str(raw_action)
            model = (
                action_models.get(action, {})
                if isinstance(action_models, dict)
                else {}
            )

            prediction: dict[str, Any] = {}
            source = "UNKNOWN"
            context_count = 0

            # Prefer the longest experienced suffix when it exists. This can
            # represent useful, false, and overcomplete correlations alike.
            if isinstance(history_models, dict):
                for length in (3, 2):
                    needed = length - 1
                    if len(recent_actions) < needed:
                        continue
                    sequence_key = "\u241f".join(
                        recent_actions[-needed:] + [action]
                    )
                    sequence_record = history_models.get(sequence_key)
                    if not isinstance(sequence_record, dict):
                        continue
                    learned, scope, context_count = _prediction_from_record(
                        sequence_record,
                        context_key,
                    )
                    if learned:
                        prediction.update(learned)
                        source = f"ACTION_HISTORY_N{length}"
                        prediction["__prediction_scope"] = scope
                        prediction["__history_length"] = length
                        break

            if not prediction and isinstance(model, dict):
                learned, scope, context_count = (
                    _prediction_from_record(
                        model,
                        context_key,
                    )
                )
                prediction.update(learned)
                if learned:
                    source = "ACTION_MODEL"
                    prediction["__prediction_scope"] = scope

            if not prediction and action.startswith("USE:"):
                object_id = action.split(":", 1)[1]
                record = visible_objects.get(object_id)
                if record is None and isinstance(objects, dict):
                    record = objects.get(object_id)
                if isinstance(record, dict):
                    cue = str(
                        record.get("cue_signature")
                        or "GENERIC_OBJECT"
                    )
                    learned, scope, context_count = (
                        self._cue_prediction(
                            object_cue_models
                            if isinstance(object_cue_models, dict)
                            else {},
                            cue,
                            context_key,
                        )
                    )
                    prediction.update(learned)
                    if learned:
                        source = f"OBJECT_CUE:{cue}"
                        prediction["__prediction_scope"] = scope

            destination = _move_destination(action)
            if destination is not None and current_position is not None:
                if not prediction:
                    obstacle_record = visible_obstacles.get(destination)
                    if obstacle_record is None and isinstance(obstacles, dict):
                        for record in obstacles.values():
                            if (
                                isinstance(record, dict)
                                and _position(record.get("position"))
                                == destination
                            ):
                                obstacle_record = record
                                break
                    if isinstance(obstacle_record, dict):
                        cue = str(
                            obstacle_record.get("cue_signature")
                            or "GENERIC_OBSTACLE"
                        )
                        learned, scope, context_count = (
                            self._cue_prediction(
                                obstacle_cue_models
                                if isinstance(obstacle_cue_models, dict)
                                else {},
                                cue,
                                context_key,
                            )
                        )
                        prediction.update(learned)
                        if learned:
                            source = f"OBSTACLE_CUE:{cue}"
                            prediction["__prediction_scope"] = scope

                best_navigation_score = 0.0
                navigation_regulatory = 0.0
                navigation_progress = 0.0
                navigation_target = None

                for object_id, record in (
                    objects.items()
                    if isinstance(objects, dict)
                    else ()
                ):
                    if not isinstance(record, dict):
                        continue
                    object_position = _position(record.get("position"))
                    if object_position is None:
                        continue

                    use_model = (
                        action_models.get(f"USE:{object_id}", {})
                        if isinstance(action_models, dict)
                        else {}
                    )
                    use_prediction: dict[str, float] = {}

                    if isinstance(use_model, dict):
                        use_prediction, _scope, _count = (
                            _prediction_from_record(
                                use_model,
                                context_key,
                            )
                        )

                    if not use_prediction:
                        cue = str(
                            record.get("cue_signature")
                            or "GENERIC_OBJECT"
                        )
                        (
                            use_prediction,
                            _scope,
                            _count,
                        ) = self._cue_prediction(
                            object_cue_models
                            if isinstance(object_cue_models, dict)
                            else {},
                            cue,
                            context_key,
                        )

                    if not use_prediction:
                        continue

                    regulatory_benefit = max(
                        0.0,
                        _target_gain(
                            use_prediction,
                            current_signals,
                            context.state.goals,
                        ),
                    )
                    progress_benefit = max(
                        0.0,
                        progress_weight
                        * float(
                            use_prediction.get(
                                "progress_delta",
                                0.0,
                            )
                        ),
                    )
                    if (
                        regulatory_benefit <= 0.0
                        and progress_benefit <= 0.0
                    ):
                        continue

                    current_route_cost = _known_route_cost(
                        current_position,
                        object_position,
                        known_positions=known_positions,
                        action_models=(
                            action_models
                            if isinstance(action_models, dict)
                            else {}
                        ),
                        current_signals=current_signals,
                        goals=context.state.goals,
                    )
                    destination_route_cost = _known_route_cost(
                        destination,
                        object_position,
                        known_positions=known_positions,
                        action_models=(
                            action_models
                            if isinstance(action_models, dict)
                            else {}
                        ),
                        current_signals=current_signals,
                        goals=context.state.goals,
                    )

                    if (
                        current_route_cost is not None
                        and destination_route_cost is not None
                    ):
                        current_factor = 1.0 / (
                            1.0 + current_route_cost
                        )
                        destination_factor = 1.0 / (
                            1.0 + destination_route_cost
                        )
                        opportunity_delta = (
                            destination_factor
                            - current_factor
                        )
                    else:
                        before = _manhattan(
                            current_position,
                            object_position,
                        )
                        after = _manhattan(
                            destination,
                            object_position,
                        )
                        opportunity_delta = (
                            (before - after)
                            / max(1.0, float(before))
                            if before > 0
                            else 0.0
                        )

                    candidate_regulatory = (
                        regulatory_benefit
                        * opportunity_delta
                    )
                    candidate_progress = (
                        progress_benefit
                        * opportunity_delta
                    )

                    # Urgency should strengthen navigation toward regulatory
                    # opportunities, not make progress-only goals more magnetic.
                    candidate_score = (
                        candidate_regulatory
                        * (1.0 + 2.5 * urgency)
                        + candidate_progress
                        * (1.0 - 0.80 * urgency)
                    )

                    if candidate_score > best_navigation_score:
                        best_navigation_score = candidate_score
                        navigation_regulatory = (
                            candidate_regulatory
                        )
                        navigation_progress = candidate_progress
                        navigation_target = str(object_id)

                prediction["__navigation_regulatory_value"] = (
                    navigation_regulatory
                )
                prediction["__navigation_progress_value"] = (
                    navigation_progress
                )
                prediction["__navigation_value"] = (
                    navigation_regulatory
                    + navigation_progress
                )
                if navigation_target is not None:
                    prediction["__navigation_target"] = (
                        navigation_target
                    )

            prediction["__prediction_source"] = source
            prediction.setdefault(
                "__prediction_scope",
                "UNKNOWN",
            )
            prediction["__physiology_context"] = context_key
            prediction["__context_sample_count"] = context_count
            predictions[action] = prediction

        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "predictions",
                    "by_action",
                    predictions,
                ),
            ),
            signals={
                "by_action": predictions,
                "physiology_context": physiology_context,
            },
        )

class OrganismPredictionErrorModule(PsycheModule):
    module_id = "PSY-PREDICTION-ERROR-ORGANISM-V03"
    version = "0.3.2"
    stage = PsycheStage.PREDICTION_ERROR

    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = _mapping(context.state.attention.get("current"))
        previous = context.state.predictions.get("last_selected")
        errors = {}

        if (
            isinstance(previous, dict)
            and attended.get("last_action") == previous.get("action")
        ):
            actual = _numeric(
                attended.get("last_experienced_effects")
            )
            expected = _numeric(previous.get("prediction"))
            keys = set(actual) | set(expected)
            for key in keys:
                if key.startswith("__"):
                    continue
                errors[key] = float(actual.get(key, 0.0)) - float(
                    expected.get(key, 0.0)
                )

        magnitude = sum(abs(value) for value in errors.values())
        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "prediction_errors",
                    "last",
                    errors,
                ),
                PsycheUpdate(
                    "prediction_errors",
                    "magnitude",
                    magnitude,
                ),
            ),
            signals={
                "errors": errors,
                "magnitude": magnitude,
            },
        )


class OrganismUncertaintyModule(PsycheModule):
    module_id = "PSY-UNCERTAINTY-ORGANISM-V03"
    version = "0.3.2.1"
    stage = PsycheStage.UNCERTAINTY

    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = _mapping(context.state.attention.get("current"))
        actions = attended.get("available_actions", ())
        models = context.state.learning.get("action_models", {})
        current_signals = _numeric(
            context.state.internal.get("interoceptive_model")
        )
        context_key = str(
            _physiology_context(current_signals)["key"]
        )

        uncertainty = {}
        context_counts = {}

        for raw_action in actions:
            action = str(raw_action)
            record = (
                models.get(action, {})
                if isinstance(models, dict)
                else {}
            )
            count = (
                _context_sample_count(
                    record,
                    context_key,
                )
                if isinstance(record, dict)
                else 0
            )
            context_counts[action] = count
            uncertainty[action] = 1.0 / sqrt(count + 1.0)

        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "uncertainty",
                    "by_action",
                    uncertainty,
                ),
                PsycheUpdate(
                    "uncertainty",
                    "context_counts",
                    context_counts,
                ),
                PsycheUpdate(
                    "uncertainty",
                    "physiology_context",
                    context_key,
                ),
            ),
            signals={
                "by_action": uncertainty,
                "context_counts": context_counts,
                "physiology_context": context_key,
            },
        )

class OrganismGlobalModulationModule(PsycheModule):
    module_id = "PSY-GLOBAL-MODULATION-ORGANISM-V03"
    version = "0.3.2"
    stage = PsycheStage.GLOBAL_MODULATION

    def process(self, context: PsycheContext) -> PsycheOutput:
        tension = float(
            context.state.global_state.get("tension", 0.0)
        )
        uncertainty = context.state.uncertainty.get("by_action", {})
        average = (
            sum(float(v) for v in uncertainty.values())
            / len(uncertainty)
            if isinstance(uncertainty, dict) and uncertainty
            else 0.0
        )
        gain = max(
            0.0,
            min(
                0.60,
                0.07 + 0.34 * average - 0.30 * tension,
            ),
        )
        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "global_state",
                    "exploration_gain",
                    gain,
                ),
            ),
            signals={
                "tension": tension,
                "average_uncertainty": average,
                "exploration_gain": gain,
            },
        )


class OrganismSelfModelModule(PsycheModule):
    module_id = "PSY-SELF-MODEL-ORGANISM-V03"
    version = "0.3.2"
    stage = PsycheStage.SELF_MODEL

    def process(self, context: PsycheContext) -> PsycheOutput:
        executed = int(
            context.state.self_model.get("executed_actions", 0)
        )
        experienced = int(
            context.state.self_model.get(
                "consequence_observations",
                0,
            )
        )
        attended = _mapping(
            context.state.attention.get("current")
        )
        if attended.get("last_action") is not None:
            executed += 1
        if isinstance(
            attended.get("last_experienced_effects"),
            dict,
        ):
            experienced += 1

        reliability = (
            experienced / executed
            if executed
            else 0.0
        )
        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "self_model",
                    "executed_actions",
                    executed,
                ),
                PsycheUpdate(
                    "self_model",
                    "consequence_observations",
                    experienced,
                ),
                PsycheUpdate(
                    "self_model",
                    "agency_reliability",
                    reliability,
                ),
            ),
            signals={
                "agency_reliability": reliability,
            },
        )


class OrganismValuationModule(PsycheModule):
    module_id = "PSY-VALUATION-ORGANISM-V03"
    version = "0.3.2.1"
    stage = PsycheStage.VALUATION

    def process(self, context: PsycheContext) -> PsycheOutput:
        predictions = context.state.predictions.get("by_action", {})
        habits = context.state.habits.get("strength", {})
        current_signals = _numeric(
            context.state.internal.get("interoceptive_model")
        )
        goals = context.state.goals
        values = {}

        tension = max(
            0.0,
            min(
                1.0,
                float(
                    context.state.global_state.get(
                        "tension",
                        0.0,
                    )
                ),
            ),
        )
        urgency = min(1.0, tension * 2.5)
        navigation_weight = float(
            goals.get(
                "navigation_weight",
                0.90,
            )
        )

        for action, raw_prediction in (
            predictions.items()
            if isinstance(predictions, dict)
            else ()
        ):
            prediction = (
                raw_prediction
                if isinstance(raw_prediction, dict)
                else {}
            )
            numeric = {
                str(k): float(v)
                for k, v in prediction.items()
                if isinstance(v, (int, float))
                and not isinstance(v, bool)
                and not str(k).startswith("__")
            }

            regulation = _target_gain(
                numeric,
                current_signals,
                goals,
            )

            progress = (
                float(
                    numeric.get(
                        "progress_delta",
                        0.0,
                    )
                )
                * float(
                    goals.get(
                        "progress_weight",
                        0.30,
                    )
                )
                * (1.0 - 0.80 * urgency)
            )

            habit = (
                float(habits.get(action, 0.0))
                if isinstance(habits, dict)
                else 0.0
            ) * float(
                goals.get("habit_weight", 0.03)
            )

            nav_reg_raw = float(
                prediction.get(
                    "__navigation_regulatory_value",
                    0.0,
                )
            )
            nav_progress_raw = float(
                prediction.get(
                    "__navigation_progress_value",
                    0.0,
                )
            )

            # Backward compatibility for legacy prediction payloads.
            if (
                "__navigation_regulatory_value" not in prediction
                and "__navigation_progress_value" not in prediction
            ):
                nav_progress_raw = float(
                    prediction.get(
                        "__navigation_value",
                        0.0,
                    )
                )

            navigation_regulatory = (
                nav_reg_raw
                * navigation_weight
                * (1.0 + 2.5 * urgency)
            )
            navigation_progress = (
                nav_progress_raw
                * navigation_weight
                * (1.0 - 0.80 * urgency)
            )
            navigation = (
                navigation_regulatory
                + navigation_progress
            )

            values[str(action)] = {
                "regulation": regulation,
                "progress": progress,
                "habit": habit,
                "navigation_regulatory": (
                    navigation_regulatory
                ),
                "navigation_progress": (
                    navigation_progress
                ),
                "navigation": navigation,
                "base_total": (
                    regulation
                    + progress
                    + habit
                    + navigation
                ),
            }

        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "values",
                    "by_action",
                    values,
                ),
            ),
            signals={
                "by_action": values,
                "urgency": urgency,
            },
        )

class OrganismActionGenerationModule(PsycheModule):
    module_id = "PSY-ACTION-GENERATION-ORGANISM-V03"
    version = "0.3.2.1"
    stage = PsycheStage.ACTION_GENERATION

    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = _mapping(context.state.attention.get("current"))
        actions = attended.get("available_actions", ())
        values = context.state.values.get("by_action", {})
        uncertainty = context.state.uncertainty.get("by_action", {})
        candidates = []

        for raw_action in actions:
            action = str(raw_action)
            record = (
                values.get(action, {})
                if isinstance(values, dict)
                else {}
            )
            components = (
                dict(record)
                if isinstance(record, dict)
                else {}
            )
            total = float(
                components.pop("base_total", 0.0)
            )
            candidates.append(
                PsycheActionCandidate(
                    source_module=self.module_id,
                    action=Action(action),
                    total_value=total,
                    components={
                        str(k): float(v)
                        for k, v in components.items()
                        if isinstance(v, (int, float))
                        and not isinstance(v, bool)
                    },
                    metadata={
                        "uncertainty": float(
                            uncertainty.get(action, 1.0)
                            if isinstance(uncertainty, dict)
                            else 1.0
                        ),
                        "local_interaction": action.startswith(
                            ("USE:", "TAKE:", "RELEASE:", "PUSH:")
                        ),
                        "movement": action.startswith("MOVE:"),
                    },
                )
            )
        return PsycheOutput(
            candidates=tuple(candidates),
            signals={
                "candidate_count": len(candidates),
                "actions": [
                    item.action.kind
                    for item in candidates
                ],
            },
        )


class OrganismActionSelectionModule(PsycheModule):
    module_id = "PSY-ACTION-SELECTION-ORGANISM-V03"
    version = "0.3.2.1"
    stage = PsycheStage.ACTION_SELECTION

    def process(self, context: PsycheContext) -> PsycheOutput:
        if not context.candidates:
            return PsycheOutput(
                selection=PsycheSelection(
                    source_module=self.module_id,
                    action=Action.wait(),
                    reason="NO_CANDIDATES",
                    score=0.0,
                )
            )

        context_counts = context.state.uncertainty.get(
            "context_counts",
            {},
        )
        counts = {}
        for candidate in context.candidates:
            action = candidate.action.kind
            if isinstance(context_counts, dict):
                counts[action] = int(
                    context_counts.get(action, 0)
                )
            else:
                counts[action] = 0

        novel_interactions = [
            candidate
            for candidate in context.candidates
            if candidate.metadata.get("local_interaction")
            and counts.get(candidate.action.kind, 0) == 0
        ]

        if novel_interactions:
            selected = sorted(
                novel_interactions,
                key=lambda item: (
                    -item.total_value,
                    -float(
                        item.metadata.get(
                            "uncertainty",
                            0.0,
                        )
                    ),
                    item.action.kind,
                ),
            )[0]
            reason = "CONTEXT_NOVEL_AFFORDANCE_PROBE"
            score = selected.total_value
        else:
            gain = float(
                context.state.global_state.get(
                    "exploration_gain",
                    0.0,
                )
            )
            tension = float(
                context.state.global_state.get(
                    "tension",
                    0.0,
                )
            )

            def adjusted(candidate: PsycheActionCandidate) -> float:
                return (
                    candidate.total_value
                    + gain
                    * float(
                        candidate.metadata.get(
                            "uncertainty",
                            0.0,
                        )
                    )
                )

            unexplored_moves = [
                candidate
                for candidate in context.candidates
                if candidate.metadata.get("movement")
                and counts.get(candidate.action.kind, 0) == 0
            ]
            best_known = max(
                (
                    adjusted(candidate)
                    for candidate in context.candidates
                    if counts.get(candidate.action.kind, 0) > 0
                ),
                default=float("-inf"),
            )

            if (
                unexplored_moves
                and (
                    tension < 0.38
                    or best_known <= 0.0
                )
            ):
                selected = sorted(
                    unexplored_moves,
                    key=lambda item: (
                        -adjusted(item),
                        -float(
                            item.metadata.get(
                                "uncertainty",
                                0.0,
                            )
                        ),
                        item.action.kind,
                    ),
                )[0]
                reason = "SPATIAL_EXPLORATION"
                score = adjusted(selected)
            else:
                selected = sorted(
                    context.candidates,
                    key=lambda item: (
                        -adjusted(item),
                        item.action.kind,
                    ),
                )[0]
                reason = "MULTI_OBJECTIVE_VALUE_PLUS_UNCERTAINTY"
                score = adjusted(selected)

        prediction = (
            context.state.predictions.get("by_action", {})
            .get(selected.action.kind, {})
        )

        current_signals = _numeric(
            context.state.internal.get("interoceptive_model")
        )
        state_context = _physiology_context(
            current_signals
        )

        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "predictions",
                    "last_selected",
                    {
                        "action": selected.action.kind,
                        "prediction": deepcopy(prediction),
                        "state_context": deepcopy(
                            state_context
                        ),
                    },
                ),
                PsycheUpdate(
                    "working",
                    "last_selection",
                    {
                        "action": selected.action.kind,
                        "reason": reason,
                        "score": score,
                        "state_context": deepcopy(
                            state_context
                        ),
                    },
                ),
            ),
            selection=PsycheSelection(
                source_module=self.module_id,
                action=selected.action,
                reason=reason,
                score=score,
                metadata={
                    "base_value": selected.total_value,
                    "components": deepcopy(
                        selected.components
                    ),
                    "uncertainty": selected.metadata.get(
                        "uncertainty",
                        0.0,
                    ),
                    "physiology_context": state_context[
                        "key"
                    ],
                    "context_sample_count": counts.get(
                        selected.action.kind,
                        0,
                    ),
                },
            ),
            signals={
                "selected_action": selected.action.kind,
                "reason": reason,
                "score": score,
                "physiology_context": state_context,
                "context_sample_count": counts.get(
                    selected.action.kind,
                    0,
                ),
            },
        )

def build_organism_modules():
    """Alternative implementations of the same 15 candidate foundation roles."""
    return (
        OrganismRegulationModule(),
        PerceptionModule(),
        OrganismAttentionModule(),
        OrganismLearningModule(),
        OrganismSpatialMemoryModule(),
        OrganismPredictionModule(),
        OrganismPredictionErrorModule(),
        OrganismUncertaintyModule(),
        GoalMaintenanceModule(),
        OrganismGlobalModulationModule(),
        OrganismSelfModelModule(),
        HabitModule(),
        OrganismValuationModule(),
        OrganismActionGenerationModule(),
        OrganismActionSelectionModule(),
    )


def build_sensorimotor_modules(config=None, developmental=None):
    """Same foundation roles; generation/selection are experience-structured.

    Endogenous variation is not a phase and is not disabled by age.
    Optional developmental gating bounds early use of accumulated history.
    """
    from .developmental import DevelopmentalConfig, DevelopmentalGateModule
    from .sensorimotor import (
        SensorimotorConfig,
        SensorimotorGenerationModule,
        SensorimotorLearningModule,
        SensorimotorSelectionModule,
    )
    from mechanistic_mind.research.motor_primitive_bridge import (
        MotorPrimitiveBridgeModule,
    )
    from mechanistic_mind.research.temporal_contingency_bridge import (
        TemporalContingencyBridgeModule,
    )

    sensorimotor = config or SensorimotorConfig()
    if developmental is None:
        developmental = getattr(sensorimotor, "developmental", None)
    if developmental is None:
        developmental = DevelopmentalConfig()
    modules = [
        OrganismRegulationModule(),
        PerceptionModule(),
        OrganismAttentionModule(),
        SensorimotorLearningModule(sensorimotor),
        OrganismLearningModule(),
        OrganismSpatialMemoryModule(),
        DevelopmentalGateModule(developmental),
        OrganismPredictionModule(),
        OrganismPredictionErrorModule(),
        OrganismUncertaintyModule(),
        GoalMaintenanceModule(),
        OrganismGlobalModulationModule(),
        OrganismSelfModelModule(),
        HabitModule(),
        OrganismValuationModule(),
        SensorimotorGenerationModule(sensorimotor),
        # Update 4.4: MP availability bridge (no value bonus). Optional via attr.
        MotorPrimitiveBridgeModule(
            enabled=bool(getattr(sensorimotor, "motor_primitive_bridge", True)),
            prospective_valuation=bool(
                getattr(sensorimotor, "prospective_valuation", True)
            ),
            prediction_ablated=bool(
                getattr(sensorimotor, "prediction_ablated", False)
            ),
        ),
        # Update 4.10: temporal contingency → prediction → prospective valuation.
        TemporalContingencyBridgeModule(
            enabled=bool(getattr(sensorimotor, "temporal_contingency_enabled", False)),
            prospective_valuation=bool(
                getattr(sensorimotor, "prospective_valuation", True)
            ),
            prediction_ablated=bool(
                getattr(sensorimotor, "prediction_ablated", False)
            ),
            action_conditioning=bool(
                getattr(sensorimotor, "temporal_action_conditioning", True)
            ),
            context_conditioning=bool(
                getattr(sensorimotor, "temporal_context_conditioning", True)
            ),
            state_conditioning=bool(
                getattr(sensorimotor, "temporal_state_conditioning", True)
            ),
            reconstruction_ablated=bool(
                getattr(sensorimotor, "temporal_reconstruction_ablated", False)
            ),
            min_support=float(getattr(sensorimotor, "temporal_min_support", 3.0)),
            trajectory_lags=tuple(getattr(sensorimotor, "temporal_trajectory_lags", (1, 2, 3))),
        ),
        SensorimotorSelectionModule(sensorimotor),
    ]
    return tuple(modules)


def build_organism_modules_with_development(developmental=None):
    """V03 organism stack plus optional developmental gate (compatibility)."""
    from .developmental import DevelopmentalConfig, DevelopmentalGateModule

    developmental = developmental or DevelopmentalConfig()
    base = list(build_organism_modules())
    # Insert after spatial memory (index of OrganismSpatialMemoryModule).
    insert_at = 5
    base.insert(insert_at + 1, DevelopmentalGateModule(developmental))
    return tuple(base)
