"""Deterministic acceptance protocol for objective object manipulation."""
from __future__ import annotations

from mechanistic_mind.agent import Action
from mechanistic_mind.mechanisms import (
    ActionProposal,
    Mechanism,
    MechanismContext,
    MechanismOutput,
)


class PhysicalObjectProtocol(Mechanism):
    """A reproducible action protocol, not a psychological policy.

    It exercises the real world transition layer so the Observer can display
    approach, carry, drop, push, and a rejected high-resistance push.
    """

    mechanism_id = "PHYSICAL-OBJECT-ACCEPTANCE-PROTOCOL"
    version = "0.1.0"

    ACTIONS = (
        "MOVE:4,2",
        "TAKE:OBJ-41",
        "MOVE:4,3",
        "RELEASE:OBJ-41",
        "MOVE:5,3",
        "PUSH:OBJ-42:5,1",
        "MOVE:5,4",
        "PUSH:OBJ-73:7,4",
        "WAIT",
    )

    def process(self, context: MechanismContext) -> MechanismOutput:
        action = self.ACTIONS[min(context.tick, len(self.ACTIONS) - 1)]
        return MechanismOutput(
            proposals=(
                ActionProposal(
                    source_mechanism=self.mechanism_id,
                    action=Action(action),
                    priority=100,
                    metadata={"protocol_tick": context.tick},
                ),
            ),
            signals={
                "protocol": "OBJECTIVE_OBJECT_MANIPULATION",
                "selected_action": action,
            },
        )
