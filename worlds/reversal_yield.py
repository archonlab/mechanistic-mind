from copy import deepcopy
from dataclasses import dataclass, field

from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.environment import World, WorldState


@dataclass(slots=True)
class ReversalYieldWorld(World):
    """Two-option world with an unannounced mid-run contingency reversal.

    Phase 1:
        A -> 1
        B -> 3

    Phase 2:
        A -> 4
        B -> 1

    The agent observes only its previous action and previous outcome.
    Reversal phase and hidden yields are never exposed in Observation.
    """

    reversal_after: int = 6
    state: WorldState = field(
        default_factory=lambda: WorldState(
            variables={
                "world_step": 0,
                "phase": "PRE_REVERSAL",
                "pre_yield_A": 1.0,
                "pre_yield_B": 3.0,
                "post_yield_A": 4.0,
                "post_yield_B": 1.0,
                "last_action": None,
                "last_outcome": None,
                "cumulative_outcome": 0.0,
                "count_A": 0,
                "count_B": 0,
                "pre_count_A": 0,
                "pre_count_B": 0,
                "post_count_A": 0,
                "post_count_B": 0,
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
                "ReversalYieldWorld currently requires exactly one agent"
            )

        next_state = deepcopy(state)
        action = next(iter(actions.values()))
        world_step = int(next_state.variables["world_step"])

        pre_reversal = world_step < self.reversal_after
        phase = "PRE_REVERSAL" if pre_reversal else "POST_REVERSAL"

        if pre_reversal:
            yield_a = float(next_state.variables["pre_yield_A"])
            yield_b = float(next_state.variables["pre_yield_B"])
        else:
            yield_a = float(next_state.variables["post_yield_A"])
            yield_b = float(next_state.variables["post_yield_B"])

        if action.kind == "CHOOSE_A":
            outcome = yield_a
            next_state.variables["count_A"] += 1
            next_state.variables[
                "pre_count_A" if pre_reversal else "post_count_A"
            ] += 1
        elif action.kind == "CHOOSE_B":
            outcome = yield_b
            next_state.variables["count_B"] += 1
            next_state.variables[
                "pre_count_B" if pre_reversal else "post_count_B"
            ] += 1
        elif action.kind == "WAIT":
            outcome = 0.0
        else:
            raise ValueError(
                f"Unsupported ReversalYieldWorld action: {action.kind}"
            )

        next_state.variables["phase"] = phase
        next_state.variables["last_action"] = action.kind
        next_state.variables["last_outcome"] = outcome
        next_state.variables["cumulative_outcome"] += outcome
        next_state.variables["world_step"] = world_step + 1
        return next_state
