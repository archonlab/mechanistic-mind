from __future__ import annotations

import sys
from pathlib import Path

from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.experiments import (
    CompactEvidenceObserver,
    CompressionConfig,
    ExperienceCompressionMechanism,
    MemoryMode,
    behavioral_metrics,
    memory_metrics,
)
from mechanistic_mind.mechanisms import MechanismRegistry

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worlds"))
from reversal_yield import ReversalYieldWorld


def run(mode: MemoryMode, ticks: int = 40, reversal: int = 20, **config_overrides):
    config = CompressionConfig(mode=mode, **config_overrides)
    mechanism = ExperienceCompressionMechanism(config)
    registry = MechanismRegistry()
    registry.register(mechanism)
    observer = CompactEvidenceObserver(checkpoint_interval=10, measure_legacy_full=True)
    engine = Engine(
        world=ReversalYieldWorld(reversal_after=reversal),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
        observer=observer,
        run_config={"memory_mode": mode.value, "memory_parameters": config.to_dict()},
    )
    initial_world = engine.state.world.variables.copy()
    engine.run(ticks)
    engine.close()
    memory = engine.state.agents["A001"].mechanism_states[mechanism.mechanism_id]["memory"]
    return engine, observer, memory, initial_world


def test_agent_episodes_contain_only_available_experience_not_world_truth():
    _engine, _observer, memory, _initial = run(MemoryMode.RAW, 8)
    assert memory["episodes"]
    encoded = str(memory["episodes"])
    assert "pre_yield_A" not in encoded
    assert "post_yield_A" not in encoded
    assert {"context_signature", "action", "outcome", "prediction_error"} <= set(memory["episodes"][0])


def test_compressed_patterns_form_and_are_used_for_decisions():
    _engine, observer, memory, _initial = run(MemoryMode.COMPRESSED, 30, reversal=100)
    assert memory["patterns"]
    assert memory["last_decision_source"] == "PATTERN"
    assert any(event["type"] == "pattern_created" for event in observer.events)
    assert memory["total_compressions"] > 0


def test_forgetful_has_equal_episode_pressure_but_no_patterns():
    _engine, _observer, forgetful, _initial = run(MemoryMode.FORGETFUL, 30, episodic_capacity=6)
    _engine, _observer, compressed, _initial = run(MemoryMode.COMPRESSED, 30, episodic_capacity=6)
    assert len(forgetful["episodes"]) <= 6
    assert len(compressed["episodes"]) <= 6
    assert forgetful["patterns"] == {}
    assert forgetful["last_decision_source"] != "PATTERN"


def test_surprise_is_protected_and_patterns_can_be_invalidated():
    _engine, observer, memory, _initial = run(
        MemoryMode.COMPRESSED,
        35,
        reversal=12,
        episodic_capacity=3,
        high_error_threshold=0.2,
        invalidation_streak=2,
    )
    assert any((row.get("prediction_error") or 0) >= 0.2 for row in memory["episodes"])
    assert any(event["type"] == "pattern_invalidated" for event in observer.events)


def test_matched_modes_have_identical_initial_world_and_agent_state():
    rows = [run(mode, 1) for mode in MemoryMode]
    assert all(row[3] == rows[0][3] for row in rows)
    assert all(row[0].state.agents["A001"].variables == {} for row in rows)


def test_compact_observer_uses_periodic_checkpoints_and_is_smaller():
    _engine, observer, _memory, _initial = run(MemoryMode.COMPRESSED, 60)
    assert len(observer.checkpoints) < 60
    assert observer.storage_metrics["reduction_ratio"] > 2.0
    assert observer.storage_metrics["checkpoint_storage_bytes"] > 0
    assert all("state" not in row for row in observer.continuous)


def test_behavior_and_memory_metrics_are_exposed():
    _engine, observer, memory, _initial = run(MemoryMode.COMPRESSED, 24)
    behavior = behavioral_metrics(observer.continuous)
    measured = memory_metrics(memory)
    assert {"action_entropy", "behavioral_persistence", "exploration_rate", "object_preference"} <= set(behavior)
    assert {"pattern_count", "compression_ratio", "agent_memory_bytes", "pattern_confidence_distribution"} <= set(measured)
    assert observer.continuous[-1]["agents"]["A001"]["objective_outcome_after_action"] is not None
    assert observer.continuous[-1]["agents"]["A001"]["agent_accessible_previous_outcome"]
    assert "decision_source" in observer.continuous[-1]["agents"]["A001"]["memory"]


def test_seeded_compact_runs_are_reproducible():
    first = run(MemoryMode.COMPRESSED, 25)
    second = run(MemoryMode.COMPRESSED, 25)
    assert first[2] == second[2]
    assert first[1].continuous == second[1].continuous
