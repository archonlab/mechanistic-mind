from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest

from mechanistic_mind.agent import Agent, AgentState, Observation
from mechanistic_mind.core import Engine
from mechanistic_mind.experiments import (
    CognitiveBudget,
    CompactEvidenceObserver,
    CompressionConfig,
    ExperienceCompressionMechanism,
    MemoryMode,
    build_retrieval_cue,
    structural_retrieval_probe,
)
from mechanistic_mind.mechanisms import MechanismContext, MechanismRegistry
from mechanistic_mind.world_engine import (
    ObjectiveObject,
    ObjectiveObstacle,
    ObjectiveWorldEngine,
    WorldEngineConfig,
)


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worlds"))
from reversal_yield import ReversalYieldWorld


SEPARATOR = "\u241f"


def _pattern(
    pattern_id: str,
    context: str,
    action: str,
    *,
    count: float = 10.0,
    expected: float = 1.0,
) -> dict:
    return {
        "pattern_id": pattern_id,
        "context_signature": context,
        "action_signature": action,
        "count": count,
        "expected_outcomes": {"scalar": expected},
        "m2": {"scalar": 0.0},
        "last_updated": 1,
        "representatives": [],
        "exceptions": [],
    }


def _indexed_pattern(memory: dict, context: str, action: str, record: dict) -> str:
    key = f"{context}{SEPARATOR}{action}"
    memory["patterns"][key] = record
    memory["pattern_index"][key] = [key]
    return key


def _run_compressed(
    *,
    ticks: int = 60,
    reversal: int = 30,
    **overrides,
):
    config = CompressionConfig(mode=MemoryMode.COMPRESSED, **overrides)
    mechanism = ExperienceCompressionMechanism(config)
    registry = MechanismRegistry()
    registry.register(mechanism)
    observer = CompactEvidenceObserver(checkpoint_interval=25)
    engine = Engine(
        world=ReversalYieldWorld(reversal_after=reversal),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
        observer=observer,
    )
    engine.run(ticks)
    engine.close()
    memory = engine.state.agents["A001"].mechanism_states[
        mechanism.mechanism_id
    ]["memory"]
    return observer, memory


def test_default_cognitive_budget_is_explicit_and_hard() -> None:
    assert CognitiveBudget() == CognitiveBudget(4, 4, 8, 12)


def test_pattern_lookup_precedes_fallback_and_sufficient_match_stops_it() -> None:
    mechanism = ExperienceCompressionMechanism()
    memory = mechanism._initial_memory()
    _indexed_pattern(memory, "CTX", "ACT", _pattern("PAT-1", "CTX", "ACT"))
    predictions, retrieval = mechanism._retrieve_bounded(
        memory, "CTX", {"ACT": "ACT"}, 2
    )
    assert retrieval["stage_trace"] == ["PATTERN"]
    assert retrieval["exception_candidates_inspected"] == 0
    assert retrieval["episode_candidates_inspected"] == 0
    assert predictions["ACT"]["source"] == "PATTERN"


def test_insufficient_pattern_uses_only_bounded_linked_fallback() -> None:
    mechanism = ExperienceCompressionMechanism()
    memory = mechanism._initial_memory()
    key = _indexed_pattern(
        memory,
        "CTX",
        "ACT",
        _pattern("PAT-LOW", "CTX", "ACT", count=1.0),
    )
    memory["exception_index"][key] = [
        {"outcome": {"scalar": 2.0}, "tick": index}
        for index in range(30)
    ]
    predictions, retrieval = mechanism._retrieve_bounded(
        memory, "CTX", {"ACT": "ACT"}, 2
    )
    assert retrieval["stage_trace"][0] == "PATTERN"
    assert 0 < retrieval["exception_candidates_inspected"] <= 4
    assert retrieval["episode_candidates_inspected"] <= 8
    assert predictions["ACT"]["evidence_status"] == "LOW_CONFIDENCE"


def test_index_miss_has_explicit_unknown_state() -> None:
    mechanism = ExperienceCompressionMechanism()
    predictions, retrieval = mechanism._retrieve_bounded(
        mechanism._initial_memory(), "MISSING", {"ACT": "ACT"}, 1
    )
    assert predictions["ACT"] == {
        "expected": {},
        "samples": 0,
        "source": "UNKNOWN",
        "confidence": 0.0,
        "evidence_status": "INSUFFICIENT_EVIDENCE",
    }
    assert retrieval["terminal_stage"] == "UNKNOWN"


def test_all_inspections_are_counted_and_never_exceed_any_budget() -> None:
    budget = CognitiveBudget(4, 4, 8, 12)
    mechanism = ExperienceCompressionMechanism(
        CompressionConfig(cognitive_budget=budget)
    )
    memory = mechanism._initial_memory()
    actions = {f"A{index}": f"S{index}" for index in range(20)}
    for index, signature in enumerate(actions.values()):
        key = _indexed_pattern(
            memory,
            "CTX",
            signature,
            _pattern(f"PAT-{index}", "CTX", signature, count=1.0),
        )
        memory["exception_index"][key] = [
            {"outcome": {"scalar": float(index)}} for _ in range(5)
        ]
        episode_ids = []
        for item in range(10):
            episode_id = f"EP-{index}-{item}"
            memory["episode_lookup"][episode_id] = {
                "outcome": {"scalar": float(index)}
            }
            episode_ids.append(episode_id)
        memory["episode_index"][key] = episode_ids
    _predictions, retrieval = mechanism._retrieve_bounded(
        memory, "CTX", actions, 2
    )
    assert retrieval["pattern_candidates_inspected"] <= 4
    assert retrieval["exception_candidates_inspected"] <= 4
    assert retrieval["episode_candidates_inspected"] <= 8
    assert retrieval["total_candidates_inspected"] <= 12
    assert retrieval["total_candidates_inspected"] == sum(
        retrieval[name]
        for name in (
            "pattern_candidates_inspected",
            "exception_candidates_inspected",
            "episode_candidates_inspected",
        )
    )


def test_structural_lookup_does_not_scan_biography_or_scale_candidate_bound() -> None:
    small = structural_retrieval_probe(100)
    large = structural_retrieval_probe(10_000)
    assert small["full_store_iterations"] == large["full_store_iterations"] == 0
    assert small["retrieval"]["total_candidates_inspected"] == 1
    assert large["retrieval"]["total_candidates_inspected"] == 1


def test_well_explained_experience_updates_patterns_and_compresses_detail() -> None:
    _observer, memory = _run_compressed(ticks=45, reversal=100)
    assert memory["patterns"]
    assert memory["total_compressions"] > 0
    assert len(memory["episodes"]) < memory["total_experiences"]
    assert memory["last_retention"]["reason"] in {
        "WELL_EXPLAINED_PATTERN_UPDATE",
        "UNEXPLAINED",
    }


def test_high_error_experience_is_retained_with_reason_and_can_invalidate() -> None:
    observer, memory = _run_compressed(
        ticks=60,
        reversal=14,
        high_error_threshold=0.2,
        invalidation_streak=2,
        episodic_capacity=5,
    )
    assert any(
        (row.get("prediction_error") or 0.0) >= 0.2
        for row in memory["episodes"]
    )
    assert any(row["type"] == "pattern_invalidated" for row in observer.events)
    assert any(
        row["agents"]["A001"].get("retention", {}).get("reason")
        == "HIGH_ERROR_EXCEPTION"
        for row in observer.continuous
    )


def test_novelty_is_not_a_value_term_or_forced_exploration_rule() -> None:
    mechanism = ExperienceCompressionMechanism()
    predictions = {
        "A": {"expected": {"scalar": 1.0}, "samples": 4, "novelty": 0.0},
        "B": {"expected": {"scalar": 0.0}, "samples": 4, "novelty": 999.0},
    }
    assert mechanism._select(("A", "B"), predictions, 0.5) == "A"
    assert "novelty_reward" not in CompressionConfig().to_dict()


def test_body_signal_directions_value_regulatory_change_not_raw_magnitude() -> None:
    mechanism = ExperienceCompressionMechanism()
    assert mechanism._outcome_value(
        {
            "energy_signal": -0.1,
            "hydration_signal": -0.05,
            "fatigue_signal": 0.2,
            "discomfort_signal": 0.1,
            "effort_signal": 0.3,
        }
    ) == pytest.approx(-0.75)
    assert mechanism._outcome_value(
        {"energy_delta": 0.2, "fatigue_delta": -0.1, "damage_delta": -0.05}
    ) == pytest.approx(0.35)


def test_partial_episode_and_pattern_fragments_exclude_hidden_world_state() -> None:
    _observer, memory = _run_compressed(ticks=18, reversal=100)
    encoded = repr({"episodes": memory["episodes"], "patterns": memory["patterns"]})
    for forbidden in (
        "pre_yield_A",
        "post_yield_A",
        "phase",
        "observer_history",
        "future_outcome",
    ):
        assert forbidden not in encoded


def test_representatives_and_exceptions_are_bounded() -> None:
    _observer, memory = _run_compressed(
        ticks=90,
        reversal=35,
        representative_capacity=1,
        exception_capacity=1,
        high_error_threshold=0.2,
    )
    assert all(len(row.get("representatives", [])) <= 1 for row in memory["patterns"].values())
    assert all(len(row.get("exceptions", [])) <= 1 for row in memory["patterns"].values())


def test_prepattern_candidate_store_is_finite() -> None:
    mechanism = ExperienceCompressionMechanism(
        CompressionConfig(candidate_capacity=3)
    )
    memory = mechanism._initial_memory()
    events = []
    for tick in range(8):
        pending = {
            "tick": tick,
            "cue": {},
            "context_signature": f"UNIQUE-{tick}",
            "action": "ACT",
            "action_signature": "ACT",
            "predicted_outcome": {},
            "retrieval_provenance": {},
            "body_state_signature": {},
            "perceived_identifiers": [],
            "position": None,
        }
        mechanism._retain_experience(
            memory, pending, {"scalar": float(tick)}, tick + 1, events
        )
    assert len(memory["candidates"]) == 3
    assert any(row["type"] == "candidate_evicted" for row in events)


def test_forgetful_control_keeps_fifo_not_novelty_priority() -> None:
    config = CompressionConfig(mode=MemoryMode.FORGETFUL, episodic_capacity=3)
    mechanism = ExperienceCompressionMechanism(config)
    registry = MechanismRegistry()
    registry.register(mechanism)
    engine = Engine(
        world=ReversalYieldWorld(reversal_after=100),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
    )
    engine.run(10)
    memory = engine.state.agents["A001"].mechanism_states[
        mechanism.mechanism_id
    ]["memory"]
    # The action at tick 9 is still pending until its outcome is observed.
    assert [row["tick"] for row in memory["episodes"]] == [6, 7, 8]
    assert memory["patterns"] == {}


def test_radius_two_vision_is_local_relative_and_physically_descriptive() -> None:
    engine = ObjectiveWorldEngine(
        WorldEngineConfig(
            width=7,
            height=7,
            vision_radius=2,
            blocked=(),
            objects=(
                ObjectiveObject(
                    "NEAR",
                    (3, 1),
                    cue_signature="MATTE-CIRCLE",
                    shape="circle",
                    color="#112233",
                    body_effects={"energy_delta": 99.0},
                    hidden_role="SECRET_RESOURCE",
                ),
                ObjectiveObject("FAR", (3, 6), cue_signature="FAR-CUE"),
            ),
            obstacles=(
                ObjectiveObstacle(
                    "EDGE", (2, 2), body_effects={"damage_delta": 8.0}
                ),
            ),
        )
    )
    observation = engine.local_observation(
        engine.initial_state(start_position=(3, 3)), agent_id="A001"
    )
    fragments = observation["visual_fragments"]
    assert observation["vision_horizon"] == 2
    assert {row["cue_signature"] for row in fragments} == {
        "MATTE-CIRCLE",
        "GENERIC_OBSTACLE",
    }
    near = next(row for row in fragments if row["kind"] == "OBJECT")
    assert near["relative_position"] == [0, -2]
    assert near["distance"] == 2
    encoded = repr(fragments)
    assert "SECRET_RESOURCE" not in encoded
    assert "energy_delta" not in encoded
    assert "damage_delta" not in encoded


def test_vision_enters_only_the_ordinary_versioned_retrieval_cue() -> None:
    fragment = {
        "kind": "OBJECT",
        "relative_position": [1, 0],
        "distance": 1,
        "cue_signature": "CUE-X",
        "shape": "circle",
        "size": 0.4,
    }
    cue = build_retrieval_cue(
        {
            "visual_fragments": [fragment],
            "available_actions": ("WAIT",),
            "hidden_object_effect": 50,
        }
    )
    assert cue["schema_version"] == "bounded-retrieval-cue-v1"
    assert cue["visual_fragments"] == [fragment]
    assert "hidden_object_effect" not in repr(cue)


def test_observer_only_fields_cannot_enter_agent_cue_or_pending_memory() -> None:
    mechanism = ExperienceCompressionMechanism()
    observation = Observation(
        {
            "available_actions": ("A", "B"),
            "observer_history": [{"future": 999}],
            "objective_world_truth": {"best_action": "B"},
        }
    )
    output = mechanism.process(
        MechanismContext(
            tick=0,
            agent_id="A001",
            observation=observation,
            agent_state=AgentState(),
            mechanism_state={},
            random_value=0.1,
        )
    )
    memory = deepcopy(output.state_updates[0].value)
    assert "observer_history" not in repr(memory["pending"]["cue"])
    assert "objective_world_truth" not in repr(memory["pending"]["cue"])
    assert output.telemetry["observer_history_access"] is False


def test_seeded_bounded_runs_keep_memory_and_scientific_telemetry_identical() -> None:
    first_observer, first_memory = _run_compressed(ticks=40, reversal=20)
    second_observer, second_memory = _run_compressed(ticks=40, reversal=20)
    assert first_memory == second_memory
    assert first_observer.continuous == second_observer.continuous
    assert all(
        "retrieval_time_ns" not in repr(row)
        for row in first_observer.continuous
    )


def test_observer_reports_bounded_retrieval_and_retention_aggregates() -> None:
    observer, _memory = _run_compressed(ticks=25, reversal=15)
    metrics = observer.storage_metrics["retrieval_metrics"]
    for name in (
        "pattern_candidates_inspected",
        "exception_candidates_inspected",
        "episode_candidates_inspected",
        "total_candidates_inspected",
        "index_probes",
        "pattern_lookup_time_ns",
        "episode_fallback_time_ns",
        "retrieval_time_ns",
        "decision_time_ns",
    ):
        assert {"mean", "max", "approx_p50", "approx_p95"} <= set(metrics[name])
    last = observer.continuous[-1]["agents"]["A001"]
    assert last["retrieval"]["budget"] == {
        "max_pattern_candidates": 4,
        "max_exception_candidates": 4,
        "max_episode_candidates": 8,
        "max_total_memory_candidates": 12,
    }
    assert {
        "selected_prediction_source",
        "selected_prediction_confidence",
        "selected_prediction_match_score",
        "selected_evidence_status",
    } <= set(last["retrieval"])
    assert "novel_fragment_count" in last["memory"]
    assert "reason" in last["retention"]
