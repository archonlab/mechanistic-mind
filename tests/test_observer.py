import json
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
    StateUpdate,
)
from mechanistic_mind.observer import (
    InMemorySink,
    JSONLSink,
    PsychologyObserver,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from diagnostic_counter import CounterWorld


class ObserverTestMechanism(Mechanism):
    mechanism_id = "OBS-TEST"
    version = "1.2.3"

    def process(self, context: MechanismContext) -> MechanismOutput:
        return MechanismOutput(
            proposals=(
                ActionProposal(
                    source_mechanism=self.mechanism_id,
                    action=Action("INCREMENT", {"amount": 2}),
                    priority=3,
                ),
            ),
            state_updates=(
                StateUpdate.mechanism_state(
                    "count",
                    1,
                    operation="ADD",
                ),
            ),
            signals={"seen_counter": context.observation.data["counter"]},
            telemetry={"tick_seen": context.tick},
        )


def make_registry():
    registry = MechanismRegistry()
    registry.register(ObserverTestMechanism())
    return registry


def test_observer_records_full_tick_causal_trace():
    sink = InMemorySink()
    observer = PsychologyObserver(sink)

    engine = Engine(
        world=CounterWorld(
            state=WorldState(variables={"counter": 0})
        ),
        agents={"A001": Agent(agent_id="A001")},
        seed=99,
        mechanisms=make_registry(),
        observer=observer,
        run_config={"test_mode": True},
    )

    result = engine.step()
    engine.close()

    assert sink.metadata is not None
    assert sink.metadata.seed == 99
    assert sink.metadata.mechanism_versions == {"OBS-TEST": "1.2.3"}
    assert sink.metadata.world_type == "CounterWorld"
    assert sink.metadata.config == {"test_mode": True}

    assert len(sink.records) == 1
    record = sink.records[0]

    assert record.tick == 0
    assert record.observations["A001"]["data"]["counter"] == 0
    assert (
        record.mechanism_outputs["A001"]["OBS-TEST"]["signals"]
        ["seen_counter"]
        == 0
    )
    assert record.actions["A001"]["kind"] == "INCREMENT"
    assert record.action_sources["A001"] == "MECHANISM:OBS-TEST"
    assert record.state_after["world"]["variables"]["counter"] == 2
    assert (
        record.state_after["agents"]["A001"]
        ["mechanism_states"]["OBS-TEST"]["count"]
        == 1
    )

    assert sink.summary is not None
    assert sink.summary.ticks_recorded == 1
    assert sink.summary.final_tick == 1


def test_observer_records_external_override_provenance():
    sink = InMemorySink()
    observer = PsychologyObserver(sink)

    engine = Engine(
        world=CounterWorld(
            state=WorldState(variables={"counter": 0})
        ),
        agents={"A001": Agent(agent_id="A001")},
        mechanisms=make_registry(),
        observer=observer,
    )

    engine.step(
        actions={"A001": Action("DECREMENT", {"amount": 5})}
    )

    assert sink.records[0].action_sources["A001"] == "EXTERNAL_OVERRIDE"
    assert sink.records[0].actions["A001"]["kind"] == "DECREMENT"


def test_jsonl_sink_writes_metadata_ticks_and_summary(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    sink = JSONLSink(path)
    observer = PsychologyObserver(sink)

    engine = Engine(
        world=CounterWorld(
            state=WorldState(variables={"counter": 0})
        ),
        agents={"A001": Agent(agent_id="A001")},
        seed=7,
        mechanisms=make_registry(),
        observer=observer,
    )

    engine.run(2)
    engine.close()

    lines = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]

    assert [line["record_type"] for line in lines] == [
        "run_metadata",
        "tick",
        "tick",
        "run_summary",
    ]
    assert lines[0]["payload"]["seed"] == 7
    assert lines[1]["payload"]["tick"] == 0
    assert lines[2]["payload"]["tick"] == 1
    assert lines[3]["payload"]["ticks_recorded"] == 2


def test_tick_record_is_snapshot_not_live_state_alias():
    sink = InMemorySink()
    observer = PsychologyObserver(sink)

    engine = Engine(
        world=CounterWorld(
            state=WorldState(variables={"counter": 0})
        ),
        agents={"A001": Agent(agent_id="A001")},
        mechanisms=make_registry(),
        observer=observer,
    )

    engine.step()
    first_counter_after = (
        sink.records[0].state_after["world"]["variables"]["counter"]
    )

    engine.step()

    assert first_counter_after == 2
    assert (
        sink.records[0].state_after["world"]["variables"]["counter"]
        == 2
    )
    assert engine.state.world.variables["counter"] == 4


def test_observer_must_start_before_recording():
    sink = InMemorySink()
    observer = PsychologyObserver(sink)

    try:
        observer.record_step(None)  # type: ignore[arg-type]
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError")
