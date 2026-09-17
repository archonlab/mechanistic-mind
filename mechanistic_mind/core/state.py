from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.agent.action import Action
from mechanistic_mind.agent.observation import Observation
from mechanistic_mind.agent.state import AgentState
from mechanistic_mind.environment.state import WorldState


@dataclass(slots=True)
class SimulationState:
    """Complete explicit state of one simulation instant."""

    tick: int = 0
    world: WorldState = field(default_factory=WorldState)
    agents: dict[str, AgentState] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class StepResult:
    """Explicit causal trace for one engine step."""

    state_before: SimulationState
    observations: dict[str, Observation]
    mechanism_outputs: dict[str, dict[str, Any]]
    signals: dict[str, dict[str, dict[str, Any]]]
    action_decisions: dict[str, Any]
    actions: dict[str, Action]
    action_sources: dict[str, str]
    applied_state_updates: dict[str, tuple[Any, ...]]
    state_after: SimulationState
