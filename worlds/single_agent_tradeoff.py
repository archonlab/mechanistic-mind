from copy import deepcopy
from dataclasses import dataclass, field

from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.environment import World, WorldState


@dataclass(slots=True)
class SingleAgentTradeoffWorld(World):
    """Minimal world for a continuous single-agent psyche.

    Hidden world truth defines vector consequences for actions. The agent does
    not receive that table. It observes only available actions and the
    consequence of its previous action.
    """

    state: WorldState = field(
        default_factory=lambda: WorldState(
            variables={
                "action_outcomes": {
                    "REST": {
                        "energy_delta": 0.18,
                        "progress_delta": 0.0,
                    },
                    "WORK": {
                        "energy_delta": -0.14,
                        "progress_delta": 1.0,
                    },
                },
                "last_action": None,
                "last_consequence": None,
                "total_progress": 0.0,
                "action_counts": {
                    "REST": 0,
                    "WORK": 0,
                },
            }
        )
    )

    def observe(self, state: WorldState, agent_id: str) -> Observation:
        return Observation(
            data={
                "available_actions": ("REST", "WORK"),
                "last_action": state.variables.get("last_action"),
                "last_consequence": deepcopy(
                    state.variables.get("last_consequence")
                ),
                "context": "TRADEOFF_V01",
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
                "SingleAgentTradeoffWorld requires exactly one agent"
            )

        action = next(iter(actions.values()))
        if action.kind not in {"REST", "WORK", "WAIT"}:
            raise ValueError(
                f"Unsupported SingleAgentTradeoffWorld action: {action.kind}"
            )

        next_state = deepcopy(state)

        if action.kind == "WAIT":
            consequence = {
                "energy_delta": 0.0,
                "progress_delta": 0.0,
            }
        else:
            truth = next_state.variables["action_outcomes"]
            consequence = deepcopy(truth[action.kind])
            next_state.variables["action_counts"][action.kind] += 1

        next_state.variables["last_action"] = action.kind
        next_state.variables["last_consequence"] = consequence
        next_state.variables["total_progress"] += float(
            consequence.get("progress_delta", 0.0)
        )
        return next_state
