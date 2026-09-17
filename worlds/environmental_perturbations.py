from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mechanistic_mind.agent import Observation
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.environment import WorldState

from single_agent_life import SingleAgentLifeWorld


class PerturbationKind(str, Enum):
    RELOCATE_OBJECT = "RELOCATE_OBJECT"
    SET_OBJECT_ACTIVE = "SET_OBJECT_ACTIVE"
    SET_OUTCOME_NOISE = "SET_OUTCOME_NOISE"
    SET_AMBIENT_LOAD = "SET_AMBIENT_LOAD"
    SHIFT_OBJECT_OUTCOME = "SHIFT_OBJECT_OUTCOME"


@dataclass(frozen=True, slots=True)
class ScheduledPerturbation:
    """One environmental intervention with explicit effective tick.

    ``effective_tick`` is the first world-state tick for which the perturbation
    is active. The intervention is applied between ``effective_tick - 1`` and
    ``effective_tick`` after the previous action has completed.
    """

    perturbation_id: str
    effective_tick: int
    kind: PerturbationKind
    parameters: dict[str, Any]

    def validate(self) -> None:
        if not self.perturbation_id.strip():
            raise ValueError("perturbation_id must be non-empty")
        if self.effective_tick < 1:
            raise ValueError("effective_tick must be >= 1")
        if not isinstance(self.parameters, dict):
            raise TypeError("parameters must be a mapping")


@dataclass(frozen=True, slots=True)
class EnvironmentalPerturbationPack:
    pack_id: str
    perturbations: tuple[ScheduledPerturbation, ...] = ()

    def __post_init__(self) -> None:
        if not self.pack_id.strip():
            raise ValueError("pack_id must be non-empty")
        ids: set[str] = set()
        for perturbation in self.perturbations:
            perturbation.validate()
            if perturbation.perturbation_id in ids:
                raise ValueError(
                    "duplicate perturbation_id: "
                    f"{perturbation.perturbation_id}"
                )
            ids.add(perturbation.perturbation_id)

    def for_tick(self, effective_tick: int) -> tuple[ScheduledPerturbation, ...]:
        return tuple(
            perturbation
            for perturbation in self.perturbations
            if perturbation.effective_tick == effective_tick
        )

    def manifest(self) -> dict[str, Any]:
        return {
            "pack_id": self.pack_id,
            "perturbations": [
                {
                    "perturbation_id": item.perturbation_id,
                    "effective_tick": item.effective_tick,
                    "kind": item.kind.value,
                    "parameters": deepcopy(item.parameters),
                }
                for item in self.perturbations
            ],
        }


@dataclass(slots=True)
class PerturbedSingleAgentLifeWorld(SingleAgentLifeWorld):
    """Life World with deterministic observer-visible interventions.

    Intervention receipts live only in world truth. The agent never receives
    the perturbation manifest or log through ``observe``.
    """

    perturbation_pack: EnvironmentalPerturbationPack = field(
        default_factory=lambda: EnvironmentalPerturbationPack(
            pack_id="CONTROL"
        )
    )

    def __post_init__(self) -> None:
        self.state = deepcopy(self.state)
        self.state.variables["perturbation_pack"] = (
            self.perturbation_pack.manifest()
        )
        self.state.variables["perturbation_log"] = []
        self.state.variables["ambient_load"] = {}
        self.state.variables["last_environment_effects"] = {}

    def observe(self, state: WorldState, agent_id: str) -> Observation:
        observation = SingleAgentLifeWorld.observe(self, state, agent_id)
        visible = observation.data.get("visible_objects")
        if not isinstance(visible, list):
            return observation

        objects = state.variables.get("objects", {})
        filtered = []
        for item in visible:
            if not isinstance(item, dict):
                continue
            object_id = str(item.get("id") or "")
            record = objects.get(object_id, {}) if isinstance(objects, dict) else {}
            if isinstance(record, dict) and record.get("active", True) is False:
                continue
            filtered.append(item)
        observation.data["visible_objects"] = filtered
        return observation

    def _available_actions(
        self,
        state: WorldState,
        position: tuple[int, int],
    ) -> list[str]:
        actions = SingleAgentLifeWorld._available_actions(self, state, position)
        objects = state.variables.get("objects", {})
        result = []
        for action in actions:
            if not action.startswith("USE:"):
                result.append(action)
                continue
            object_id = action.split(":", 1)[1]
            record = objects.get(object_id, {}) if isinstance(objects, dict) else {}
            if isinstance(record, dict) and record.get("active", True) is False:
                continue
            result.append(action)
        return result

    def transition(
        self,
        state: WorldState,
        actions: dict[str, Any],
        rng: DeterministicRandom,
    ) -> WorldState:
        source_tick = int(state.variables.get("tick", 0))
        action = next(iter(actions.values()))
        next_state = SingleAgentLifeWorld.transition(self, state, actions, rng)

        base_consequence = deepcopy(
            next_state.variables.get("last_consequence") or {}
        )
        consequence = dict(base_consequence)
        environment_effects: dict[str, Any] = {}

        ambient = state.variables.get("ambient_load", {})
        if isinstance(ambient, dict) and ambient:
            applied_ambient: dict[str, float] = {}
            for key, raw in ambient.items():
                if not isinstance(raw, (int, float)) or isinstance(raw, bool):
                    continue
                delta = float(raw)
                consequence[str(key)] = float(consequence.get(str(key), 0.0)) + delta
                applied_ambient[str(key)] = delta
            if applied_ambient:
                environment_effects["ambient_load"] = applied_ambient

        if action.kind.startswith("USE:"):
            object_id = action.kind.split(":", 1)[1]
            objects = state.variables.get("objects", {})
            record = objects.get(object_id, {}) if isinstance(objects, dict) else {}
            noise = record.get("outcome_noise", {}) if isinstance(record, dict) else {}
            if isinstance(noise, dict) and noise:
                draws: dict[str, float] = {}
                for key in sorted(noise):
                    amplitude_raw = noise[key]
                    if (
                        not isinstance(amplitude_raw, (int, float))
                        or isinstance(amplitude_raw, bool)
                    ):
                        continue
                    amplitude = abs(float(amplitude_raw))
                    draw = (rng.random() * 2.0 - 1.0) * amplitude
                    consequence[str(key)] = float(
                        consequence.get(str(key), 0.0)
                    ) + draw
                    draws[str(key)] = draw
                if draws:
                    environment_effects["outcome_noise"] = {
                        "object_id": object_id,
                        "draws": draws,
                    }

        old_progress = float(base_consequence.get("progress_delta", 0.0))
        new_progress = float(consequence.get("progress_delta", 0.0))
        if new_progress != old_progress:
            next_state.variables["total_progress"] = float(
                next_state.variables.get("total_progress", 0.0)
            ) + (new_progress - old_progress)

        next_state.variables["last_consequence"] = consequence
        next_state.variables["last_environment_effects"] = environment_effects

        effective_tick = source_tick + 1
        for perturbation in self.perturbation_pack.for_tick(effective_tick):
            self._apply_perturbation(
                next_state,
                perturbation,
                source_tick=source_tick,
            )

        return next_state

    def _apply_perturbation(
        self,
        state: WorldState,
        perturbation: ScheduledPerturbation,
        *,
        source_tick: int,
    ) -> None:
        before = self._receipt_snapshot(state, perturbation)
        parameters = perturbation.parameters

        if perturbation.kind is PerturbationKind.RELOCATE_OBJECT:
            object_id = self._required_object_id(parameters, state)
            position = self._required_position(parameters.get("position"))
            if not self._is_open(state, position):
                raise ValueError(
                    f"Relocation target is not open: {position}"
                )
            objects = state.variables["objects"]
            objects[object_id]["position"] = list(position)

        elif perturbation.kind is PerturbationKind.SET_OBJECT_ACTIVE:
            object_id = self._required_object_id(parameters, state)
            active = parameters.get("active")
            if not isinstance(active, bool):
                raise ValueError("SET_OBJECT_ACTIVE requires bool active")
            state.variables["objects"][object_id]["active"] = active

        elif perturbation.kind is PerturbationKind.SET_OUTCOME_NOISE:
            object_id = self._required_object_id(parameters, state)
            amplitudes = parameters.get("amplitudes")
            if not isinstance(amplitudes, dict):
                raise ValueError(
                    "SET_OUTCOME_NOISE requires amplitudes mapping"
                )
            clean: dict[str, float] = {}
            for key, value in amplitudes.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ValueError(
                        "noise amplitudes must be numeric"
                    )
                clean[str(key)] = abs(float(value))
            state.variables["objects"][object_id]["outcome_noise"] = clean

        elif perturbation.kind is PerturbationKind.SET_AMBIENT_LOAD:
            load = parameters.get("load")
            if not isinstance(load, dict):
                raise ValueError("SET_AMBIENT_LOAD requires load mapping")
            clean_load: dict[str, float] = {}
            for key, value in load.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ValueError("ambient load values must be numeric")
                clean_load[str(key)] = float(value)
            state.variables["ambient_load"] = clean_load

        elif perturbation.kind is PerturbationKind.SHIFT_OBJECT_OUTCOME:
            object_id = self._required_object_id(parameters, state)
            delta = parameters.get("delta")
            if not isinstance(delta, dict):
                raise ValueError(
                    "SHIFT_OBJECT_OUTCOME requires delta mapping"
                )
            outcome = state.variables["objects"][object_id].setdefault(
                "outcome", {}
            )
            for key, value in delta.items():
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    raise ValueError("outcome delta values must be numeric")
                outcome[str(key)] = float(outcome.get(str(key), 0.0)) + float(value)

        else:
            raise ValueError(
                f"Unsupported perturbation kind: {perturbation.kind}"
            )

        after = self._receipt_snapshot(state, perturbation)
        log = list(state.variables.get("perturbation_log", []))
        log.append(
            {
                "perturbation_id": perturbation.perturbation_id,
                "kind": perturbation.kind.value,
                "applied_after_tick": source_tick,
                "effective_tick": perturbation.effective_tick,
                "parameters": deepcopy(parameters),
                "before": before,
                "after": after,
            }
        )
        state.variables["perturbation_log"] = log

    def _required_object_id(
        self,
        parameters: dict[str, Any],
        state: WorldState,
    ) -> str:
        object_id = str(parameters.get("object_id") or "").strip()
        objects = state.variables.get("objects", {})
        if not object_id:
            raise ValueError("object_id is required")
        if object_id not in objects:
            raise ValueError(f"Unknown object_id: {object_id}")
        return object_id

    @staticmethod
    def _required_position(value: Any) -> tuple[int, int]:
        if (
            not isinstance(value, (list, tuple))
            or len(value) != 2
            or not all(isinstance(item, int) for item in value)
        ):
            raise ValueError("position must be [x, y] integers")
        return int(value[0]), int(value[1])

    def _receipt_snapshot(
        self,
        state: WorldState,
        perturbation: ScheduledPerturbation,
    ) -> dict[str, Any]:
        if perturbation.kind is PerturbationKind.SET_AMBIENT_LOAD:
            return {
                "ambient_load": deepcopy(
                    state.variables.get("ambient_load", {})
                )
            }

        object_id = str(
            perturbation.parameters.get("object_id") or ""
        ).strip()
        objects = state.variables.get("objects", {})
        record = objects.get(object_id, {}) if isinstance(objects, dict) else {}
        return {
            "object_id": object_id,
            "record": deepcopy(record),
        }


def canonical_environmental_conditions(
    *,
    effective_tick: int = 100,
) -> dict[str, EnvironmentalPerturbationPack]:
    """Matched-control intervention set for v0.2.2."""

    return {
        "CONTROL": EnvironmentalPerturbationPack(
            pack_id="EPP-CONTROL"
        ),
        "RELOCATION": EnvironmentalPerturbationPack(
            pack_id="EPP-RELOCATION",
            perturbations=(
                ScheduledPerturbation(
                    perturbation_id="RELOCATE-HYDRATION-01",
                    effective_tick=effective_tick,
                    kind=PerturbationKind.RELOCATE_OBJECT,
                    parameters={
                        "object_id": "OBJ-23",
                        "position": [1, 5],
                    },
                ),
            ),
        ),
        "DEPLETION": EnvironmentalPerturbationPack(
            pack_id="EPP-DEPLETION",
            perturbations=(
                ScheduledPerturbation(
                    perturbation_id="DEPLETE-RECOVERY-01",
                    effective_tick=effective_tick,
                    kind=PerturbationKind.SET_OBJECT_ACTIVE,
                    parameters={
                        "object_id": "OBJ-04",
                        "active": False,
                    },
                ),
            ),
        ),
        "OUTCOME_NOISE": EnvironmentalPerturbationPack(
            pack_id="EPP-OUTCOME-NOISE",
            perturbations=(
                ScheduledPerturbation(
                    perturbation_id="NOISE-PROGRESS-01",
                    effective_tick=effective_tick,
                    kind=PerturbationKind.SET_OUTCOME_NOISE,
                    parameters={
                        "object_id": "OBJ-31",
                        "amplitudes": {
                            "energy_delta": 0.05,
                            "hydration_delta": 0.05,
                            "fatigue_delta": 0.05,
                            "progress_delta": 0.25,
                        },
                    },
                ),
            ),
        ),
        "AMBIENT_PRESSURE": EnvironmentalPerturbationPack(
            pack_id="EPP-AMBIENT-PRESSURE",
            perturbations=(
                ScheduledPerturbation(
                    perturbation_id="DRY-LOAD-01",
                    effective_tick=effective_tick,
                    kind=PerturbationKind.SET_AMBIENT_LOAD,
                    parameters={
                        "load": {
                            "hydration_delta": -0.018,
                            "fatigue_delta": 0.004,
                        }
                    },
                ),
            ),
        ),
        "UTILITY_CONFLICT": EnvironmentalPerturbationPack(
            pack_id="EPP-UTILITY-CONFLICT",
            perturbations=(
                ScheduledPerturbation(
                    perturbation_id="PROGRESS-COST-SHIFT-01",
                    effective_tick=effective_tick,
                    kind=PerturbationKind.SHIFT_OBJECT_OUTCOME,
                    parameters={
                        "object_id": "OBJ-31",
                        "delta": {
                            "hydration_delta": -0.10,
                            "fatigue_delta": 0.10,
                        },
                    },
                ),
            ),
        ),
    }
