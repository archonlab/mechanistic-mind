from copy import deepcopy
from dataclasses import dataclass, field

from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.environment import World, WorldState


@dataclass(slots=True)
class TwoChoiceYieldWorld(World):
    """Minimal partially-observed diagnostic world.

    Hidden world truth contains fixed yields for two actions. The agent never
    observes those values directly. It sees only the consequence of its most
    recent action.

    This world is intentionally single-agent in Foundation 0.0.7.
    """

    state: WorldState = field(
        default_factory=lambda: WorldState(
            variables={
                "yield_A": 1.0,
                "yield_B": 3.0,
                "last_action": None,
                "last_outcome": None,
                "cumulative_outcome": 0.0,
                "count_A": 0,
                "count_B": 0,
            }
        )
    )

    def observe(self, state: WorldState, agent_id: str) -> Observation:
        return Observation(
            data={
                "available_actions": ("CHOOSE_A", "CHOOSE_B"),
                "last_action": state.variables.get("last_action"),
                "last_outcome": state.variables.get("last_outcome"),
            }
        )

    def transition(
        self,
        state: WorldState,
        actions: dict[str, Action],
        rng: DeterministicRandom,
    ) -> WorldState:
        if len(actions) != 1:
            raise ValueError(
                "TwoChoiceYieldWorld currently requires exactly one agent"
            )

        action = next(iter(actions.values()))
        next_state = deepcopy(state)

        if action.kind == "CHOOSE_A":
            outcome = float(next_state.variables["yield_A"])
            next_state.variables["count_A"] += 1
        elif action.kind == "CHOOSE_B":
            outcome = float(next_state.variables["yield_B"])
            next_state.variables["count_B"] += 1
        elif action.kind == "WAIT":
            outcome = 0.0
        else:
            raise ValueError(
                f"Unsupported TwoChoiceYieldWorld action: {action.kind}"
            )

        next_state.variables["last_action"] = action.kind
        next_state.variables["last_outcome"] = outcome
        next_state.variables["cumulative_outcome"] += outcome
        return next_state
