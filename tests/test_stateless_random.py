from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.environment import World
from mechanistic_mind.mechanisms import (
    Mechanism,
    MechanismContext,
    MechanismOutput,
    MechanismRegistry,
)


class RandomRecorder(Mechanism):
    mechanism_id = "RANDOM-RECORDER"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        return MechanismOutput(
            signals={"random_value": context.random_value}
        )


def make(seed):
    registry = MechanismRegistry()
    registry.register(RandomRecorder())
    return Engine(
        world=World(),
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
    )


def test_same_seed_same_stateless_random_value():
    a = make(42).step()
    b = make(42).step()

    assert (
        a.signals["A001"]["RANDOM-RECORDER"]["random_value"]
        == b.signals["A001"]["RANDOM-RECORDER"]["random_value"]
    )


def test_different_seed_changes_stateless_random_value():
    a = make(42).step()
    b = make(43).step()

    assert (
        a.signals["A001"]["RANDOM-RECORDER"]["random_value"]
        != b.signals["A001"]["RANDOM-RECORDER"]["random_value"]
    )
