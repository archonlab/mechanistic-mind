import sys
from pathlib import Path

from mechanistic_mind.adapters.archon import (
    ArchonAdapterSink,
    InMemoryArchonSink,
)
from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import CompositeSink, InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import SingleAgentPsycheV01, build_foundation_modules

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from single_agent_tradeoff import SingleAgentTradeoffWorld


def make_engine(ticks=40):
    canonical = InMemorySink()
    archon = InMemoryArchonSink()
    observer = PsychologyObserver(
        CompositeSink((canonical, ArchonAdapterSink(archon)))
    )
    registry = MechanismRegistry()
    registry.register(SingleAgentPsycheV01())
    engine = Engine(
        world=SingleAgentTradeoffWorld(),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
        observer=observer,
    )
    engine.run(ticks)
    engine.close()
    return engine, canonical, archon


def test_world_truth_is_not_exposed_to_agent():
    world = SingleAgentTradeoffWorld()
    obs = world.observe(world.state, "A001")
    assert "action_outcomes" not in obs.data
    assert "available_actions" in obs.data


def test_single_agent_psyche_learns_and_uses_both_actions():
    engine, canonical, _archon = make_engine(40)

    actions = [
        record.actions["A001"]["kind"]
        for record in canonical.records
    ]
    assert "REST" in actions
    assert "WORK" in actions
    assert sum(a != b for a, b in zip(actions, actions[1:])) >= 2

    psyche = (
        engine.state.agents["A001"]
        .mechanism_states["PSYCHE-SINGLE-AGENT-V01"]["psyche"]
    )
    models = psyche["learning"]["action_models"]
    assert models["REST"]["count"] > 0
    assert models["WORK"]["count"] > 0
    assert 0.0 <= psyche["internal"]["energy"] <= 1.0
    assert psyche["internal"]["progress"] > 0.0


def test_whole_psyche_exposes_all_stage_trace_to_observer():
    _engine, canonical, archon = make_engine(12)

    assert len(canonical.records) == 12
    assert len(archon.observations) == 12

    signals = canonical.records[-1].signals["A001"][
        "PSYCHE-SINGLE-AGENT-V01"
    ]["whole_psyche"]
    trace = signals["stage_trace"]
    assert any(item.startswith("REGULATION:") for item in trace)
    assert any(item.startswith("PREDICTION:") for item in trace)
    assert any(item.startswith("VALUATION:") for item in trace)
    assert any(item.startswith("ACTION_SELECTION:") for item in trace)


def test_psyche_modules_are_ablatable_without_engine_changes():
    modules = build_foundation_modules(
        disabled={"PSY-HABIT-V01"}
    )
    psyche = SingleAgentPsycheV01(modules=modules)

    registry = MechanismRegistry()
    registry.register(psyche)
    engine = Engine(
        world=SingleAgentTradeoffWorld(),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
    )
    engine.run(8)

    state = (
        engine.state.agents["A001"]
        .mechanism_states["PSYCHE-SINGLE-AGENT-V01"]["psyche"]
    )
    assert "psyche" not in state
    assert "strength" in state["habits"]
