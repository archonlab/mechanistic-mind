from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.environment import World
from mechanistic_mind.mechanisms import (
    ActionProposal,
    Mechanism,
    MechanismContext,
    MechanismContractError,
    MechanismOutput,
    MechanismRegistry,
)


class ForgedProvenanceMechanism(Mechanism):
    mechanism_id = "REAL-ID"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        return MechanismOutput(
            proposals=(
                ActionProposal(
                    source_mechanism="FAKE-ID",
                    action=Action.wait(),
                ),
            )
        )


def test_action_proposal_cannot_forge_mechanism_provenance():
    registry = MechanismRegistry()
    registry.register(ForgedProvenanceMechanism())

    engine = Engine(
        world=World(),
        agents={"A001": Agent(agent_id="A001")},
        mechanisms=registry,
    )

    try:
        engine.step()
    except MechanismContractError:
        pass
    else:
        raise AssertionError("Expected MechanismContractError")
