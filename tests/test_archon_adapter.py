import json
import sys
from pathlib import Path

from mechanistic_mind.adapters.archon import (
    ARCHON_BRIDGE_SCHEMA,
    ArchonAdapter,
    ArchonAdapterSink,
    InMemoryArchonSink,
    JSONLArchonSink,
)
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
from mechanistic_mind.observer import PsychologyObserver

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from diagnostic_counter import CounterWorld


class BridgeTestMechanism(Mechanism):
    mechanism_id = "BRIDGE-TEST"
    version = "2.0.0"

    def process(self, context: MechanismContext) -> MechanismOutput:
        return MechanismOutput(
            proposals=(
                ActionProposal(
                    source_mechanism=self.mechanism_id,
                    action=Action("INCREMENT", {"amount": 2}),
                    priority=10,
                ),
            ),
            state_updates=(
                StateUpdate.mechanism_state(
                    "calls",
                    1,
                    operation="ADD",
                ),
            ),
            signals={"counter_seen": context.observation.data["counter"]},
            telemetry={"tick": context.tick},
        )


def registry():
    result = MechanismRegistry()
    result.register(BridgeTestMechanism())
    return result


def make_engine(target):
    observer = PsychologyObserver(
        ArchonAdapterSink(target)
    )
    return Engine(
        world=CounterWorld(
            state=WorldState(variables={"counter": 0})
        ),
        agents={"A001": Agent(agent_id="A001")},
        seed=123,
        mechanisms=registry(),
        observer=observer,
        run_config={"experiment": "bridge-smoke"},
    )


def test_launcher_descriptor_is_stable():
    descriptor = ArchonAdapter().descriptor

    assert descriptor.adapter_id == "mechanistic_mind"
    assert descriptor.domain == "psychology"
    assert descriptor.schema_version == ARCHON_BRIDGE_SCHEMA
    assert "causal_tick_trace" in descriptor.capabilities


def test_adapter_sink_emits_manifest_observation_events_and_summary():
    target = InMemoryArchonSink()
    engine = make_engine(target)

    engine.step()
    engine.close()

    assert target.manifest is not None
    assert target.manifest.seed == 123
    assert target.manifest.domain == "psychology"
    assert target.manifest.mechanism_versions == {
        "BRIDGE-TEST": "2.0.0"
    }

    assert len(target.observations) == 1
    obs = target.observations[0]
    assert obs.tick == 0
    assert obs.agent_id == "A001"
    assert obs.observation["data"]["counter"] == 0
    assert obs.state_after["mechanism_states"]["BRIDGE-TEST"]["calls"] == 1

    event_types = [event.event_type for event in target.events]
    assert event_types == [
        "MECHANISM_OUTPUT",
        "ACTION_EXECUTED",
        "STATE_UPDATE_APPLIED",
    ]

    assert target.summary is not None
    assert target.summary.ticks_recorded == 1
    assert target.summary.final_tick == 1


def test_external_override_survives_bridge_provenance():
    target = InMemoryArchonSink()
    engine = make_engine(target)

    engine.step(
        actions={"A001": Action("DECREMENT", {"amount": 3})}
    )

    action_event = next(
        event
        for event in target.events
        if event.event_type == "ACTION_EXECUTED"
    )

    assert action_event.source == "EXTERNAL_OVERRIDE"
    assert action_event.payload["action"]["kind"] == "DECREMENT"


def test_jsonl_archon_sink_is_canonical_and_ordered(tmp_path):
    path = tmp_path / "archon_bridge.jsonl"
    target = JSONLArchonSink(path)
    engine = make_engine(target)

    engine.run(2)
    engine.close()

    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
    ]

    record_types = [row["record_type"] for row in rows]

    assert record_types[0] == "archon_run_manifest"
    assert record_types[-1] == "archon_run_summary"
    assert record_types.count("archon_observation") == 2
    assert record_types.count("archon_event") == 6

    assert rows[0]["payload"]["schema_version"] == ARCHON_BRIDGE_SCHEMA


def test_adapter_does_not_require_archon_package_import():
    adapter = ArchonAdapter()
    assert adapter.descriptor.display_name == "Mechanistic Mind"
