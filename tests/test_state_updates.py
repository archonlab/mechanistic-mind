import sys
from pathlib import Path

from mechanistic_mind.agent import Action, Agent, AgentState
from mechanistic_mind.core import Engine
from mechanistic_mind.environment import WorldState
from mechanistic_mind.mechanisms import (
    ActionProposal,
    Mechanism,
    MechanismContext,
    MechanismOutput,
    MechanismRegistry,
    StateConflictError,
    StateUpdate,
    StateValidationError,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from diagnostic_counter import CounterWorld


class StatefulMechanism(Mechanism):
    mechanism_id = "TEST-STATEFUL"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        invocations = context.mechanism_state.get("invocations", 0)

        return MechanismOutput(
            proposals=(
                ActionProposal(
                    source_mechanism=self.mechanism_id,
                    action=Action("INCREMENT", {"amount": 1}),
                    priority=5,
                ),
            ),
            state_updates=(
                StateUpdate.mechanism_state(
                    "invocations",
                    1,
                    operation="ADD",
                ),
                StateUpdate.agent_variable(
                    "activity",
                    0.5,
                    operation="ADD",
                ),
            ),
            signals={
                "prior_invocations": invocations,
                "counter_seen": context.observation.data["counter"],
            },
        )


class HiddenMutationMechanism(Mechanism):
    mechanism_id = "TEST-HIDDEN-MUTATION"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        context.agent_state.variables["secret_write"] = 999
        context.mechanism_state["secret_counter"] = 999
        return MechanismOutput(signals={"attempted_hidden_mutation": True})


class ConflictA(Mechanism):
    mechanism_id = "CONFLICT-A"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        return MechanismOutput(
            state_updates=(
                StateUpdate.agent_variable("shared", 1),
            )
        )


class ConflictB(Mechanism):
    mechanism_id = "CONFLICT-B"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        return MechanismOutput(
            state_updates=(
                StateUpdate.agent_variable("shared", 2),
            )
        )


class InvalidAdd(Mechanism):
    mechanism_id = "INVALID-ADD"
    version = "0.0.1"

    def process(self, context: MechanismContext) -> MechanismOutput:
        return MechanismOutput(
            state_updates=(
                StateUpdate.agent_variable(
                    "bad",
                    "not-a-number",
                    operation="ADD",
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
        agents={
            "A001": Agent(
                agent_id="A001",
                state=AgentState(
                    variables={},
                    mechanism_states={},
                ),
            )
        },
        seed=42,
        mechanisms=registry,
    )


def test_mechanism_internal_state_persists_across_ticks():
    engine = make_engine(StatefulMechanism())

    first = engine.step()
    second = engine.step()

    assert (
        first.signals["A001"]["TEST-STATEFUL"]["prior_invocations"]
        == 0
    )
    assert (
        second.signals["A001"]["TEST-STATEFUL"]["prior_invocations"]
        == 1
    )
    assert (
        engine.state.agents["A001"]
        .mechanism_states["TEST-STATEFUL"]["invocations"]
        == 2
    )


def test_agent_level_state_update_is_validated_and_persistent():
    engine = make_engine(StatefulMechanism())

    engine.run(3)

    assert engine.state.agents["A001"].variables["activity"] == 1.5


def test_state_update_provenance_is_recorded():
    engine = make_engine(StatefulMechanism())

    result = engine.step()
    records = result.applied_state_updates["A001"]

    assert len(records) == 2
    assert all(
        record.source_mechanism == "TEST-STATEFUL"
        for record in records
    )


def test_direct_context_mutation_cannot_escape_runtime_copy():
    engine = make_engine(HiddenMutationMechanism())

    result = engine.step()

    agent_state = result.state_after.agents["A001"]
    assert "secret_write" not in agent_state.variables
    assert (
        "TEST-HIDDEN-MUTATION"
        not in agent_state.mechanism_states
    )


def test_signals_are_observable_but_not_implicitly_persisted():
    engine = make_engine(HiddenMutationMechanism())

    result = engine.step()

    assert (
        result.signals["A001"]["TEST-HIDDEN-MUTATION"]
        ["attempted_hidden_mutation"]
        is True
    )
    assert (
        "attempted_hidden_mutation"
        not in result.state_after.agents["A001"].variables
    )


def test_same_tick_agent_variable_write_conflict_fails_closed():
    engine = make_engine(ConflictA(), ConflictB())

    try:
        engine.step()
    except StateConflictError:
        pass
    else:
        raise AssertionError("Expected StateConflictError")


def test_invalid_add_fails_closed():
    engine = make_engine(InvalidAdd())

    try:
        engine.step()
    except StateValidationError:
        pass
    else:
        raise AssertionError("Expected StateValidationError")


def test_mechanism_state_is_namespaced_by_emitter():
    engine = make_engine(StatefulMechanism())

    engine.step()

    states = engine.state.agents["A001"].mechanism_states
    assert set(states) == {"TEST-STATEFUL"}
    assert states["TEST-STATEFUL"]["invocations"] == 1
