from __future__ import annotations

from copy import deepcopy
from math import sqrt
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


def _consequence(context: PsycheContext) -> dict[str, float] | None:
    value = context.observation.data.get("last_consequence")
    if not isinstance(value, dict):
        return None
    result = {}
    for key, item in value.items():
        if isinstance(item, (int, float)) and not isinstance(item, bool):
            result[str(key)] = float(item)
    return result


class InternalRegulationModule(PsycheModule):
    module_id = "PSY-REGULATION-V01"
    version = "0.1.0"
    stage = PsycheStage.REGULATION

    def __init__(self, passive_energy_drift: float = -0.02) -> None:
        self.passive_energy_drift = float(passive_energy_drift)

    def process(self, context: PsycheContext) -> PsycheOutput:
        energy = float(context.state.internal.get("energy", 0.75))
        progress = float(context.state.internal.get("progress", 0.0))
        consequence = _consequence(context)

        if consequence is not None:
            energy += consequence.get("energy_delta", 0.0)
            progress += consequence.get("progress_delta", 0.0)

        energy += self.passive_energy_drift
        energy = max(0.0, min(1.0, energy))

        setpoint = float(context.state.goals.get("energy_setpoint", 0.65))
        tension = abs(setpoint - energy)

        return PsycheOutput(
            updates=(
                PsycheUpdate("internal", "energy", energy),
                PsycheUpdate("internal", "progress", progress),
                PsycheUpdate("global_state", "tension", tension),
            ),
            signals={
                "energy": energy,
                "progress": progress,
                "tension": tension,
            },
        )


class PerceptionModule(PsycheModule):
    module_id = "PSY-PERCEPTION-V01"
    version = "0.1.0"
    stage = PsycheStage.PERCEPTION

    def process(self, context: PsycheContext) -> PsycheOutput:
        percept = deepcopy(context.observation.data)
        return PsycheOutput(
            updates=(PsycheUpdate("percept", "current", percept),),
            signals={"keys": sorted(percept)},
        )


class AttentionModule(PsycheModule):
    module_id = "PSY-ATTENTION-V01"
    version = "0.1.0"
    stage = PsycheStage.ATTENTION

    def __init__(self, capacity: int = 4) -> None:
        self.capacity = max(1, int(capacity))

    def process(self, context: PsycheContext) -> PsycheOutput:
        percept = context.state.percept.get("current", {})
        if not isinstance(percept, dict):
            percept = {}

        priority = (
            "available_actions",
            "last_action",
            "last_consequence",
            "context",
        )
        selected: dict[str, Any] = {}
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


class OutcomeLearningModule(PsycheModule):
    module_id = "PSY-LEARNING-V01"
    version = "0.1.0"
    stage = PsycheStage.LEARNING

    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = context.state.attention.get("current", {})
        if not isinstance(attended, dict):
            attended = {}

        action = attended.get("last_action")
        consequence = attended.get("last_consequence")
        models = deepcopy(context.state.learning.get("action_models", {}))

        if (
            action not in {"REST", "WORK"}
            or not isinstance(consequence, dict)
        ):
            return PsycheOutput(
                signals={"updated_action": None, "model_count": len(models)}
            )

        record = deepcopy(models.get(action, {"count": 0, "mean": {}}))
        count = int(record.get("count", 0)) + 1
        means = dict(record.get("mean", {}))

        for key, raw in consequence.items():
            if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                continue
            old = float(means.get(key, 0.0))
            value = float(raw)
            means[key] = old + (value - old) / count

        models[action] = {"count": count, "mean": means}

        return PsycheOutput(
            updates=(PsycheUpdate("learning", "action_models", models),),
            signals={
                "updated_action": action,
                "sample_count": count,
                "means": means,
            },
        )


class EpisodicMemoryModule(PsycheModule):
    module_id = "PSY-MEMORY-V01"
    version = "0.1.0"
    stage = PsycheStage.MEMORY

    def process(self, context: PsycheContext) -> PsycheOutput:
        episodes = list(deepcopy(context.state.memory.get("episodes", [])))
        max_episodes = int(context.state.memory.get("max_episodes", 32))
        attended = context.state.attention.get("current", {})

        if (
            isinstance(attended, dict)
            and attended.get("last_action") is not None
            and attended.get("last_consequence") is not None
        ):
            episodes.append(
                {
                    "tick": context.tick,
                    "action": attended.get("last_action"),
                    "consequence": deepcopy(attended.get("last_consequence")),
                }
            )
            episodes = episodes[-max_episodes:]

        return PsycheOutput(
            updates=(PsycheUpdate("memory", "episodes", episodes),),
            signals={"episode_count": len(episodes)},
        )


class PredictionModule(PsycheModule):
    module_id = "PSY-PREDICTION-V01"
    version = "0.1.0"
    stage = PsycheStage.PREDICTION

    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = context.state.attention.get("current", {})
        actions = (
            attended.get("available_actions", ())
            if isinstance(attended, dict)
            else ()
        )
        models = context.state.learning.get("action_models", {})
        predictions: dict[str, dict[str, float]] = {}

        for action in actions:
            model = models.get(action, {}) if isinstance(models, dict) else {}
            mean = model.get("mean", {}) if isinstance(model, dict) else {}
            predictions[str(action)] = {
                str(key): float(value)
                for key, value in mean.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }

        return PsycheOutput(
            updates=(PsycheUpdate("predictions", "by_action", predictions),),
            signals={"by_action": predictions},
        )


class PredictionErrorModule(PsycheModule):
    module_id = "PSY-PREDICTION-ERROR-V01"
    version = "0.1.0"
    stage = PsycheStage.PREDICTION_ERROR

    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = context.state.attention.get("current", {})
        previous = context.state.predictions.get("last_selected")
        errors: dict[str, float] = {}

        if (
            isinstance(attended, dict)
            and isinstance(previous, dict)
            and attended.get("last_action") == previous.get("action")
            and isinstance(attended.get("last_consequence"), dict)
        ):
            actual = attended["last_consequence"]
            expected = previous.get("prediction", {})
            keys = set(actual) | set(expected)
            for key in keys:
                a = actual.get(key, 0.0)
                e = expected.get(key, 0.0)
                if (
                    isinstance(a, (int, float))
                    and not isinstance(a, bool)
                    and isinstance(e, (int, float))
                    and not isinstance(e, bool)
                ):
                    errors[str(key)] = float(a) - float(e)

        magnitude = sum(abs(value) for value in errors.values())
        return PsycheOutput(
            updates=(
                PsycheUpdate("prediction_errors", "last", errors),
                PsycheUpdate("prediction_errors", "magnitude", magnitude),
            ),
            signals={"errors": errors, "magnitude": magnitude},
        )


class UncertaintyModule(PsycheModule):
    module_id = "PSY-UNCERTAINTY-V01"
    version = "0.1.0"
    stage = PsycheStage.UNCERTAINTY

    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = context.state.attention.get("current", {})
        actions = (
            attended.get("available_actions", ())
            if isinstance(attended, dict)
            else ()
        )
        models = context.state.learning.get("action_models", {})
        uncertainty = {}

        for action in actions:
            model = models.get(action, {}) if isinstance(models, dict) else {}
            count = int(model.get("count", 0)) if isinstance(model, dict) else 0
            uncertainty[str(action)] = 1.0 / sqrt(count + 1.0)

        return PsycheOutput(
            updates=(PsycheUpdate("uncertainty", "by_action", uncertainty),),
            signals={"by_action": uncertainty},
        )


class GoalMaintenanceModule(PsycheModule):
    module_id = "PSY-GOALS-V01"
    version = "0.1.0"
    stage = PsycheStage.GOALS

    def process(self, context: PsycheContext) -> PsycheOutput:
        return PsycheOutput(
            signals={
                "energy_setpoint": context.state.goals.get("energy_setpoint"),
                "homeostasis_weight": context.state.goals.get("homeostasis_weight"),
                "progress_weight": context.state.goals.get("progress_weight"),
            }
        )


class GlobalModulationModule(PsycheModule):
    module_id = "PSY-GLOBAL-MODULATION-V01"
    version = "0.1.0"
    stage = PsycheStage.GLOBAL_MODULATION

    def process(self, context: PsycheContext) -> PsycheOutput:
        tension = float(context.state.global_state.get("tension", 0.0))
        uncertainty = context.state.uncertainty.get("by_action", {})
        avg_uncertainty = (
            sum(float(v) for v in uncertainty.values()) / len(uncertainty)
            if isinstance(uncertainty, dict) and uncertainty
            else 0.0
        )

        # Exploration falls as homeostatic tension rises, while uncertainty
        # raises it. This is only a candidate modulation rule.
        exploration_gain = max(
            0.0,
            min(0.5, 0.05 + 0.30 * avg_uncertainty - 0.20 * tension),
        )

        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "global_state",
                    "exploration_gain",
                    exploration_gain,
                ),
            ),
            signals={
                "tension": tension,
                "average_uncertainty": avg_uncertainty,
                "exploration_gain": exploration_gain,
            },
        )


class SelfModelModule(PsycheModule):
    module_id = "PSY-SELF-MODEL-V01"
    version = "0.1.0"
    stage = PsycheStage.SELF_MODEL

    def process(self, context: PsycheContext) -> PsycheOutput:
        executed = int(context.state.self_model.get("executed_actions", 0))
        consequences = int(
            context.state.self_model.get("consequence_observations", 0)
        )
        attended = context.state.attention.get("current", {})

        if isinstance(attended, dict) and attended.get("last_action") is not None:
            executed += 1
        if (
            isinstance(attended, dict)
            and isinstance(attended.get("last_consequence"), dict)
        ):
            consequences += 1

        reliability = consequences / executed if executed else 0.0

        return PsycheOutput(
            updates=(
                PsycheUpdate("self_model", "executed_actions", executed),
                PsycheUpdate(
                    "self_model",
                    "consequence_observations",
                    consequences,
                ),
                PsycheUpdate(
                    "self_model",
                    "agency_reliability",
                    reliability,
                ),
            ),
            signals={"agency_reliability": reliability},
        )


class HabitModule(PsycheModule):
    module_id = "PSY-HABIT-V01"
    version = "0.1.0"
    stage = PsycheStage.HABIT

    def process(self, context: PsycheContext) -> PsycheOutput:
        strengths = dict(context.state.habits.get("strength", {}))
        decay = float(context.state.habits.get("decay", 0.85))
        rate = float(context.state.habits.get("learning_rate", 0.20))

        for key in list(strengths):
            strengths[key] = float(strengths[key]) * decay

        attended = context.state.attention.get("current", {})
        last_action = (
            attended.get("last_action")
            if isinstance(attended, dict)
            else None
        )
        if isinstance(last_action, str):
            strengths[last_action] = min(
                1.0,
                float(strengths.get(last_action, 0.0)) + rate,
            )

        return PsycheOutput(
            updates=(PsycheUpdate("habits", "strength", strengths),),
            signals={"strength": strengths},
        )


class ValuationModule(PsycheModule):
    module_id = "PSY-VALUATION-V01"
    version = "0.1.0"
    stage = PsycheStage.VALUATION

    def process(self, context: PsycheContext) -> PsycheOutput:
        energy = float(context.state.internal.get("energy", 0.75))
        target = float(context.state.goals.get("energy_setpoint", 0.65))
        homeostasis_weight = float(
            context.state.goals.get("homeostasis_weight", 2.0)
        )
        progress_weight = float(
            context.state.goals.get("progress_weight", 0.30)
        )
        habit_weight = float(
            context.state.goals.get("habit_weight", 0.06)
        )
        predictions = context.state.predictions.get("by_action", {})
        habits = context.state.habits.get("strength", {})

        values: dict[str, dict[str, float]] = {}
        current_error = abs(target - energy)

        if isinstance(predictions, dict):
            for action, prediction in predictions.items():
                prediction = prediction if isinstance(prediction, dict) else {}
                energy_delta = float(prediction.get("energy_delta", 0.0))
                progress_delta = float(prediction.get("progress_delta", 0.0))
                next_energy = max(0.0, min(1.0, energy + energy_delta))
                next_error = abs(target - next_energy)

                homeostatic_component = (
                    current_error - next_error
                ) * homeostasis_weight
                progress_component = progress_delta * progress_weight
                habit_component = (
                    float(habits.get(action, 0.0))
                    if isinstance(habits, dict)
                    else 0.0
                ) * habit_weight

                values[action] = {
                    "homeostasis": homeostatic_component,
                    "progress": progress_component,
                    "habit": habit_component,
                    "base_total": (
                        homeostatic_component
                        + progress_component
                        + habit_component
                    ),
                }

        return PsycheOutput(
            updates=(PsycheUpdate("values", "by_action", values),),
            signals={"by_action": values},
        )


class ActionGenerationModule(PsycheModule):
    module_id = "PSY-ACTION-GENERATION-V01"
    version = "0.1.0"
    stage = PsycheStage.ACTION_GENERATION

    def process(self, context: PsycheContext) -> PsycheOutput:
        attended = context.state.attention.get("current", {})
        actions = (
            attended.get("available_actions", ())
            if isinstance(attended, dict)
            else ()
        )
        values = context.state.values.get("by_action", {})
        uncertainty = context.state.uncertainty.get("by_action", {})
        candidates = []

        for action in actions:
            components = (
                dict(values.get(action, {}))
                if isinstance(values, dict)
                else {}
            )
            total = float(components.get("base_total", 0.0))
            candidates.append(
                PsycheActionCandidate(
                    source_module=self.module_id,
                    action=Action(str(action)),
                    total_value=total,
                    components={
                        key: float(value)
                        for key, value in components.items()
                        if key != "base_total"
                    },
                    metadata={
                        "uncertainty": (
                            float(uncertainty.get(action, 1.0))
                            if isinstance(uncertainty, dict)
                            else 1.0
                        )
                    },
                )
            )

        return PsycheOutput(
            candidates=tuple(candidates),
            signals={
                "candidate_count": len(candidates),
                "actions": [candidate.action.kind for candidate in candidates],
            },
        )


class ActionSelectionModule(PsycheModule):
    module_id = "PSY-ACTION-SELECTION-V01"
    version = "0.1.0"
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

        models = context.state.learning.get("action_models", {})
        counts = {
            candidate.action.kind: int(
                models.get(candidate.action.kind, {}).get("count", 0)
            )
            if isinstance(models, dict)
            else 0
            for candidate in context.candidates
        }

        unexplored = [
            candidate
            for candidate in context.candidates
            if counts.get(candidate.action.kind, 0) == 0
        ]

        if unexplored:
            selected = sorted(
                unexplored,
                key=lambda candidate: candidate.action.kind,
            )[0]
            reason = "UNCERTAINTY_PROBE"
            score = selected.total_value
        else:
            exploration_gain = float(
                context.state.global_state.get("exploration_gain", 0.0)
            )

            def adjusted(candidate: PsycheActionCandidate) -> float:
                return (
                    candidate.total_value
                    + exploration_gain
                    * float(candidate.metadata.get("uncertainty", 0.0))
                )

            selected = sorted(
                context.candidates,
                key=lambda candidate: (
                    -adjusted(candidate),
                    candidate.action.kind,
                ),
            )[0]
            reason = "MULTI_OBJECTIVE_VALUE_PLUS_UNCERTAINTY"
            score = adjusted(selected)

        prediction = context.state.predictions.get("by_action", {}).get(
            selected.action.kind,
            {},
        )

        selection = PsycheSelection(
            source_module=self.module_id,
            action=selected.action,
            reason=reason,
            score=score,
            metadata={
                "base_value": selected.total_value,
                "components": deepcopy(selected.components),
                "uncertainty": selected.metadata.get("uncertainty", 0.0),
            },
        )

        return PsycheOutput(
            updates=(
                PsycheUpdate(
                    "predictions",
                    "last_selected",
                    {
                        "action": selected.action.kind,
                        "prediction": deepcopy(prediction),
                    },
                ),
                PsycheUpdate(
                    "working",
                    "last_selection",
                    {
                        "action": selected.action.kind,
                        "reason": reason,
                        "score": score,
                    },
                ),
            ),
            selection=selection,
            signals={
                "selected_action": selected.action.kind,
                "reason": reason,
                "score": score,
            },
        )
