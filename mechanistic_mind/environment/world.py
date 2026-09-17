from copy import deepcopy
from dataclasses import dataclass, field

from mechanistic_mind.agent.action import Action
from mechanistic_mind.agent.observation import Observation
from mechanistic_mind.core.random import DeterministicRandom

from .state import WorldState


@dataclass(slots=True)
class World:
    """Base environment contract.

    The default world is deliberately inert. Diagnostic/research worlds should
    override ``observe`` and/or ``transition`` without changing the Engine.
    """

    state: WorldState = field(default_factory=WorldState)

    def observe(self, state: WorldState, agent_id: str) -> Observation:
        """Return an observation without handing out mutable world state.

        Foundation default: a pass-through copy of world variables.
        Research worlds can expose partial, noisy, delayed, or transformed data.
        """
        return Observation(data=deepcopy(state.variables))

    def transition(
        self,
        state: WorldState,
        actions: dict[str, Action],
        rng: DeterministicRandom,
    ) -> WorldState:
        """Apply actions and return the next world state.

        Foundation default: no-op. Subclasses define actual world dynamics.
        """
        return deepcopy(state)
