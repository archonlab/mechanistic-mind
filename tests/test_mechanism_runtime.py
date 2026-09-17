import sys
from pathlib import Path

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.environment import WorldState
from mechanistic_mind.mechanisms import (
    ActionProposal,
    Mechanism,
    MechanismContext,
    MechanismOutput,
    MechanismRegistry,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from diagnostic_counter import CounterWorld


class IncrementMechanism(Mechanism):
    mechanism_id = "TEST-INCREMENT"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        if context.observation.data["counter"] < 3:
            return MechanismOutput(
                proposals=(
                    ActionProposal(
                        source_mechanism=self.mechanism_id,
                        action=Action("INCREMENT", {"amount": 1}),
                        priority=10,
                        weight=1.0,
                    ),
                ),
                telemetry={"observed_counter": context.observation.data["counter"]},
            )
        return MechanismOutput()


class WeakDecrementMechanism(Mechanism):
    mechanism_id = "TEST-DECREMENT"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        return MechanismOutput(
            proposals=(
                ActionProposal(
                    source_mechanism=self.mechanism_id,
                    action=Action("DECREMENT", {"amount": 10}),
                    priority=1,
                    weight=1.0,
                ),
            )
        )


def make_engine(*mechanisms: Mechanism) -> Engine:
    registry = MechanismRegistry()
    for mechanism in mechanisms:
        registry.register(mechanism)

    return Engine(
        world=CounterWorld(
            state=WorldState(variables={"counter": 0})
        ),
        agents={"A001": Agent(agent_id="A001")},
        seed=42,
        mechanisms=registry,
    )


def test_mechanism_can_drive_action_without_external_input():
    engine = make_engine(IncrementMechanism())

    result = engine.step()

    assert result.observations["A001"].data["counter"] == 0
    assert result.actions["A001"].kind == "INCREMENT"
    assert result.action_sources["A001"] == "MECHANISM:TEST-INCREMENT"
    assert result.state_after.world.variables["counter"] == 1


def test_mechanism_sees_previous_state_not_future_state():
    engine = make_engine(IncrementMechanism())

    first = engine.step()
    second = engine.step()

    assert (
        first.mechanism_outputs["A001"]["TEST-INCREMENT"]
        .telemetry["observed_counter"]
        == 0
    )
    assert (
        second.mechanism_outputs["A001"]["TEST-INCREMENT"]
        .telemetry["observed_counter"]
        == 1
    )


def test_action_integrator_uses_priority_deterministically():
    engine = make_engine(
        WeakDecrementMechanism(),
        IncrementMechanism(),
    )

    result = engine.step()

    assert result.actions["A001"].kind == "INCREMENT"
    assert (
        result.action_decisions["A001"].selected_proposal.source_mechanism
        == "TEST-INCREMENT"
    )


def test_external_action_overrides_mechanism_action():
    engine = make_engine(IncrementMechanism())

    result = engine.step(
        actions={"A001": Action("DECREMENT", {"amount": 4})}
    )

    assert result.action_sources["A001"] == "EXTERNAL_OVERRIDE"
    assert result.actions["A001"].kind == "DECREMENT"
    assert result.state_after.world.variables["counter"] == -4


def test_no_proposals_falls_back_to_wait():
    engine = make_engine()

    result = engine.step()

    assert result.actions["A001"] == Action.wait()
    assert result.action_sources["A001"] == "DEFAULT_WAIT"


def test_mechanism_stops_proposing_when_condition_changes():
    engine = make_engine(IncrementMechanism())

    engine.run(4)

    assert engine.state.world.variables["counter"] == 3
