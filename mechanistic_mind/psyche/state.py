from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class PsycheState:
    """Persistent state of one psyche.

    Compartments are deliberately generic computational stores. Conventional
    psychological labels are kept out of the engine-level state.
    """

    internal: dict[str, Any] = field(default_factory=dict)
    percept: dict[str, Any] = field(default_factory=dict)
    attention: dict[str, Any] = field(default_factory=dict)
    learning: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    predictions: dict[str, Any] = field(default_factory=dict)
    prediction_errors: dict[str, Any] = field(default_factory=dict)
    uncertainty: dict[str, Any] = field(default_factory=dict)
    goals: dict[str, Any] = field(default_factory=dict)
    global_state: dict[str, Any] = field(default_factory=dict)
    self_model: dict[str, Any] = field(default_factory=dict)
    habits: dict[str, Any] = field(default_factory=dict)
    values: dict[str, Any] = field(default_factory=dict)
    working: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def initial_v01(cls) -> "PsycheState":
        return cls(
            internal={
                "energy": 0.75,
                "progress": 0.0,
            },
            learning={
                "action_models": {},
            },
            memory={
                "episodes": [],
                "max_episodes": 32,
            },
            predictions={
                "by_action": {},
                "last_selected": None,
            },
            prediction_errors={
                "last": {},
            },
            uncertainty={
                "by_action": {},
            },
            goals={
                "energy_setpoint": 0.65,
                "homeostasis_weight": 2.0,
                "progress_weight": 0.30,
                "habit_weight": 0.06,
            },
            global_state={
                "tension": 0.0,
                "exploration_gain": 0.20,
            },
            self_model={
                "executed_actions": 0,
                "consequence_observations": 0,
                "agency_reliability": 0.0,
            },
            habits={
                "strength": {},
                "decay": 0.85,
                "learning_rate": 0.20,
            },
        )

    @classmethod
    def initial_life_v01(cls) -> "PsycheState":
        state = cls.initial_v01()
        state.internal = {"energy": 0.78, "hydration": 0.78, "fatigue": 0.15, "progress": 0.0}
        state.learning = {"action_models": {}}
        state.memory = {"episodes": [], "max_episodes": 64, "spatial": {"visited": {}, "objects": {}}}
        state.predictions = {"by_action": {}, "last_selected": None}
        state.prediction_errors = {"last": {}, "magnitude": 0.0}
        state.uncertainty = {"by_action": {}}
        state.goals = {
            "energy_setpoint": 0.68, "hydration_setpoint": 0.72, "fatigue_setpoint": 0.22,
            "energy_weight": 2.0, "hydration_weight": 2.2, "fatigue_weight": 1.5,
            "progress_weight": 0.42, "habit_weight": 0.035, "navigation_weight": 0.90,
            "energy_critical": 0.24, "hydration_critical": 0.28, "fatigue_critical": 0.78,
        }
        state.global_state = {"tension": 0.0, "exploration_gain": 0.20}
        state.self_model = {"executed_actions": 0, "consequence_observations": 0, "agency_reliability": 0.0}
        state.habits = {"strength": {}, "decay": 0.92, "learning_rate": 0.12}
        state.values = {"by_action": {}}
        state.working = {}
        return state


    @classmethod
    def initial_organism_v03(cls) -> "PsycheState":
        """Minimal-experience psyche for Organism × World foundation.

        No personality, trust, anxiety, avoidance, resource preference, body
        mass, age, or physiological equations are preloaded.
        """
        return cls(
            internal={
                "interoceptive_model": {},
                "need_pressure": {},
            },
            learning={
                "action_models": {},
                "object_cue_models": {},
                "obstacle_cue_models": {},
                "action_history_models": {},
            },
            memory={
                "episodes": [],
                "max_episodes": 48,
                "spatial": {
                    "visited": {},
                    "objects": {},
                    "obstacles": {},
                },
            },
            predictions={
                "by_action": {},
                "last_selected": None,
            },
            prediction_errors={
                "last": {},
                "magnitude": 0.0,
            },
            uncertainty={
                "by_action": {},
            },
            goals={
                "signal_targets": {
                    "energy_signal": 0.70,
                    "hydration_signal": 0.72,
                    "fatigue_signal": 0.20,
                    "discomfort_signal": 0.05,
                },
                "signal_weights": {
                    "energy_signal": 2.0,
                    "hydration_signal": 2.2,
                    "fatigue_signal": 1.5,
                    "discomfort_signal": 2.5,
                },
                "progress_weight": 0.30,
                "habit_weight": 0.03,
                "navigation_weight": 0.90,
            },
            global_state={
                "tension": 0.0,
                "exploration_gain": 0.20,
            },
            self_model={
                "executed_actions": 0,
                "consequence_observations": 0,
                "agency_reliability": 0.0,
            },
            habits={
                "strength": {},
                "decay": 0.93,
                "learning_rate": 0.10,
            },
            values={
                "by_action": {},
            },
            working={},
        )
    def clone(self) -> "PsycheState":
        return deepcopy(self)

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(asdict(self))

    @classmethod
    def from_dict(cls, payload: dict[str, Any] | None) -> "PsycheState":
        if not payload:
            return cls.initial_v01()
        defaults = cls.initial_v01()
        kwargs: dict[str, dict[str, Any]] = {}
        for name in cls.__dataclass_fields__:
            value = payload.get(name)
            if isinstance(value, dict):
                kwargs[name] = deepcopy(value)
            else:
                kwargs[name] = deepcopy(getattr(defaults, name))
        return cls(**kwargs)

    def compartment(self, name: str) -> dict[str, Any]:
        if name not in self.__dataclass_fields__:
            raise KeyError(f"Unknown psyche compartment: {name}")
        value = getattr(self, name)
        if not isinstance(value, dict):
            raise TypeError(f"Psyche compartment is not a mapping: {name}")
        return value
