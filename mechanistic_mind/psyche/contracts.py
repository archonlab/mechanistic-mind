from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Literal

from mechanistic_mind.agent import Action, Observation


class PsycheStage(IntEnum):
    """Explicit causal order inside one psyche tick.

    Modules in the same stage see the same stage-start state. Their updates are
    integrated together after the stage, so same-stage execution order cannot
    silently change causality.
    """

    REGULATION = 10
    PERCEPTION = 20
    ATTENTION = 30
    LEARNING = 40
    MEMORY = 50
    PREDICTION = 60
    PREDICTION_ERROR = 70
    UNCERTAINTY = 80
    GOALS = 90
    GLOBAL_MODULATION = 100
    SELF_MODEL = 110
    HABIT = 120
    VALUATION = 130
    ACTION_GENERATION = 140
    ACTION_SELECTION = 150


PsycheOperation = Literal["SET", "ADD"]


@dataclass(frozen=True, slots=True)
class PsycheUpdate:
    compartment: str
    key: str
    value: Any
    operation: PsycheOperation = "SET"


@dataclass(frozen=True, slots=True)
class PsycheActionCandidate:
    source_module: str
    action: Action
    total_value: float
    components: dict[str, float] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PsycheSelection:
    source_module: str
    action: Action
    reason: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PsycheContext:
    tick: int
    agent_id: str
    stage: PsycheStage
    observation: Observation
    state: "PsycheState"
    candidates: tuple[PsycheActionCandidate, ...]
    random_value: float


@dataclass(frozen=True, slots=True)
class PsycheOutput:
    updates: tuple[PsycheUpdate, ...] = ()
    candidates: tuple[PsycheActionCandidate, ...] = ()
    selection: PsycheSelection | None = None
    signals: dict[str, Any] = field(default_factory=dict)


class PsycheModule(ABC):
    module_id: str = "UNASSIGNED"
    version: str = "0.0.0"
    stage: PsycheStage = PsycheStage.PERCEPTION

    @abstractmethod
    def process(self, context: PsycheContext) -> PsycheOutput:
        raise NotImplementedError


from .state import PsycheState  # noqa: E402
