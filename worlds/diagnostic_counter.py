from copy import deepcopy

from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.environment import World, WorldState


class CounterWorld(World):
    """Tiny diagnostic world used to test the causal loop."""

    def observe(self, state: WorldState, agent_id: str) -> Observation:
        return Observation(data={"counter": state.variables.get("counter", 0)})

    def transition(
        self,
        state: WorldState,
        actions: dict[str, Action],
        rng: DeterministicRandom,
    ) -> WorldState:
        next_state = deepcopy(state)
        counter = next_state.variables.get("counter", 0)

        for action in actions.values():
            if action.kind == "INCREMENT":
                counter += int(action.parameters.get("amount", 1))
            elif action.kind == "DECREMENT":
                counter -= int(action.parameters.get("amount", 1))
            elif action.kind == "WAIT":
                pass
            else:
                raise ValueError(f"Unsupported diagnostic action: {action.kind}")

        next_state.variables["counter"] = counter
        return next_state
