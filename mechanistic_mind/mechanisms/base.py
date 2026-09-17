from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Literal

from mechanistic_mind.agent import Action, AgentState, Observation


StateScope = Literal["AGENT_VARIABLE", "MECHANISM_STATE"]
StateOperation = Literal["SET", "ADD"]


@dataclass(frozen=True, slots=True)
class StateUpdate:
    """A requested state change."""

    scope: StateScope
    key: str
    value: Any
    operation: StateOperation = "SET"

    @classmethod
    def agent_variable(
        cls,
        key: str,
        value: Any,
        *,
        operation: StateOperation = "SET",
    ) -> "StateUpdate":
        return cls(
            scope="AGENT_VARIABLE",
            key=key,
            value=value,
            operation=operation,
        )

    @classmethod
    def mechanism_state(
        cls,
        key: str,
        value: Any,
        *,
        operation: StateOperation = "SET",
    ) -> "StateUpdate":
        return cls(
            scope="MECHANISM_STATE",
            key=key,
            value=value,
            operation=operation,
        )


@dataclass(frozen=True, slots=True)
class MechanismContext:
    """Isolated input for one mechanism invocation.

    ``random_value`` is a deterministic, stateless pseudo-random value in [0, 1)
    derived from run seed + tick + agent id + mechanism id. It does not depend
    on mechanism execution order.
    """

    tick: int
    agent_id: str
    observation: Observation
    agent_state: AgentState
    mechanism_state: dict[str, Any]
    random_value: float


@dataclass(frozen=True, slots=True)
class ActionProposal:
    """A mechanism's candidate action, not yet an executed action."""

    source_mechanism: str
    action: Action
    priority: int = 0
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MechanismOutput:
    """Observable result of one mechanism invocation."""

    proposals: tuple[ActionProposal, ...] = ()
    state_updates: tuple[StateUpdate, ...] = ()
    signals: dict[str, Any] = field(default_factory=dict)
    telemetry: dict[str, Any] = field(default_factory=dict)


class Mechanism(ABC):
    """Plug-in contract for candidate mechanisms."""

    mechanism_id: str = "UNASSIGNED"
    version: str = "0.0.0"

    @abstractmethod
    def process(self, context: MechanismContext) -> MechanismOutput:
        raise NotImplementedError
