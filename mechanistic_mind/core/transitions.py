from copy import deepcopy

from mechanistic_mind.agent.state import AgentState
from mechanistic_mind.environment.state import WorldState

from .state import SimulationState


def build_next_state(
    state: SimulationState,
    *,
    world: WorldState,
    agents: dict[str, AgentState] | None = None,
) -> SimulationState:
    """Construct the next explicit simulation snapshot."""
    return SimulationState(
        tick=state.tick + 1,
        world=deepcopy(world),
        agents=deepcopy(state.agents if agents is None else agents),
    )
