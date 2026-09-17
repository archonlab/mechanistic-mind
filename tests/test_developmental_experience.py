from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.experiments import (
    CompressionConfig,
    ExperienceCompressionMechanism,
    MemoryMode,
)
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    DevelopmentalStage,
    SingleOrganismPsycheV05,
    compute_developmental_gate,
    measure_experience_structure,
)
from mechanistic_mind.psyche.sensorimotor import (
    SensorimotorConfig,
    SensorimotorStore,
    generate_proposals,
)
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    default_contextual_object_config,
)
from reversal_yield import ReversalYieldWorld


def test_maturity_not_tick_only():
    cfg = DevelopmentalConfig(
        condition=DevelopmentalCondition.DEVELOPMENTAL,
        min_ticks=100,
        target_ticks=200,
        max_ticks=400,
        target_fragments=50,
        target_transition_diversity=20,
        target_interaction_diversity=5,
        target_repeated_consequences=10,
        target_predictive_evidence=10,
    )
    empty = measure_experience_structure()
    rich = measure_experience_structure(
        sensorimotor={
            "contingencies": {
                f"b{i}||MOVE:{i},0": {
                    "bucket": f"b{i}",
                    "action": f"MOVE:{i},0",
                    "support": 5.0,
                    "confidence": 0.8,
                }
                for i in range(30)
            }
        }
    )
    early_empty = compute_developmental_gate(tick=150, config=cfg, metrics=empty)
    early_rich = compute_developmental_gate(tick=150, config=cfg, metrics=rich)
    assert early_rich["gate_factor"] > early_empty["gate_factor"]
    assert early_empty["developmental_maturity"] < early_rich["developmental_maturity"]


def test_cannot_fully_mature_before_min_ticks():
    cfg = DevelopmentalConfig(
        condition=DevelopmentalCondition.DEVELOPMENTAL,
        min_ticks=1000,
        target_ticks=2000,
        max_ticks=5000,
    )
    rich = {
        "fragment_count": 10_000,
        "transition_diversity": 10_000,
        "interaction_diversity": 10_000,
        "repeated_consequences": 10_000,
        "predictive_evidence": 10_000,
    }
    gate = compute_developmental_gate(tick=100, config=cfg, metrics=rich)
    assert gate["gate_factor"] < 0.95
    assert gate["matured"] is False
    assert gate["developmental_stage"] != DevelopmentalStage.MATURE_COGNITION.value


def test_adult_from_tick_0_is_fully_open():
    cfg = DevelopmentalConfig(condition=DevelopmentalCondition.ADULT_FROM_TICK_0)
    gate = compute_developmental_gate(tick=0, config=cfg, metrics=measure_experience_structure())
    assert gate["gate_factor"] == 1.0
    assert gate["matured"] is True


def test_disabled_matches_open_access():
    cfg = DevelopmentalConfig(condition=DevelopmentalCondition.DISABLED)
    gate = compute_developmental_gate(tick=3, config=cfg, metrics=measure_experience_structure())
    assert gate["gate_factor"] == 1.0


def test_sensorimotor_gate_bounds_learned_proposals():
    store = SensorimotorStore()
    for i in range(6):
        key = f"bucket||MOVE:{i},0"
        store.contingencies[key] = {
            "key": key,
            "bucket": "bucket",
            "action": f"MOVE:{i},0",
            "support": 8.0,
            "confidence": 0.9,
            "mean_transition": {"displace_rate": 0.5},
        }
        store.index.setdefault("bucket", []).append(key)
    observation = {
        "position": [0, 0],
        "visible_objects": [],
        "available_actions": [f"MOVE:{i},0" for i in range(6)] + ["WAIT"],
        "interoception": {"energy_signal": 0.8, "hydration_signal": 0.8, "fatigue_signal": 0.1},
    }
    config = SensorimotorConfig()
    open_gate = {
        "gate_factor": 1.0,
        "retrieval_recent_limit": 10**9,
        "max_learned_proposals_cap": 10**9,
    }
    closed_gate = {
        "gate_factor": 0.05,
        "retrieval_recent_limit": 2,
        "max_learned_proposals_cap": 1,
    }
    open_props = generate_proposals(
        observation=observation,
        store=store,
        config=config,
        random_value=0.1,
        developmental_gate=open_gate,
    )
    closed_props = generate_proposals(
        observation=observation,
        store=store,
        config=config,
        random_value=0.1,
        developmental_gate=closed_gate,
    )
    open_learned = [
        p for p in open_props["proposals"] if p["source"] in ("LEARNED_SENSORIMOTOR", "BOTH")
    ]
    closed_learned = [
        p for p in closed_props["proposals"] if p["source"] in ("LEARNED_SENSORIMOTOR", "BOTH")
    ]
    assert len(closed_learned) <= len(open_learned)
    assert len(closed_learned) <= 1
    assert closed_props["evidence"]["inspected"] <= 2


def test_memory_forms_under_developmental_from_tick_1():
    cfg = DevelopmentalConfig(
        condition=DevelopmentalCondition.DEVELOPMENTAL,
        min_ticks=50,
        target_ticks=80,
        max_ticks=120,
        target_fragments=20,
        target_transition_diversity=8,
        target_interaction_diversity=3,
        target_repeated_consequences=4,
        target_predictive_evidence=3,
    )
    world = ContextualObjectEcologyWorld(
        world_config=default_contextual_object_config(17)
    )
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV05(developmental=cfg))
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
    )
    for _ in range(12):
        engine.step()
    psyche = engine.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"]
    memory = psyche["memory"]
    sensorimotor = memory.get("sensorimotor") or {}
    contingencies = sensorimotor.get("contingencies") or {}
    episodes = memory.get("episodes") or []
    assert len(contingencies) + len(episodes) >= 1
    developmental = memory["developmental"]
    assert developmental["condition"] == "DEVELOPMENTAL"
    assert developmental["gate_factor"] < 0.95
    assert "developmental_stage" in developmental
    engine.close()


def test_same_psyche_persists_and_no_memory_reset():
    cfg = DevelopmentalConfig(
        condition=DevelopmentalCondition.DEVELOPMENTAL,
        min_ticks=5,
        target_ticks=8,
        max_ticks=10,
        target_fragments=5,
        target_transition_diversity=3,
        target_interaction_diversity=2,
        target_repeated_consequences=2,
        target_predictive_evidence=2,
    )
    world = ContextualObjectEcologyWorld(
        world_config=default_contextual_object_config(23)
    )
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV05(developmental=cfg))
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=23,
        mechanisms=registry,
    )
    for _ in range(6):
        engine.step()
    mid = engine.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"]
    mid_store = dict((mid["memory"].get("sensorimotor") or {}).get("contingencies") or {})
    for _ in range(8):
        engine.step()
    late = engine.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"]
    late_store = (late["memory"].get("sensorimotor") or {}).get("contingencies") or {}
    # Developmental experience remains as historical foundation.
    for key in mid_store:
        assert key in late_store
    engine.close()


def test_compression_developmental_disabled_reproduces_budget():
    plain = ExperienceCompressionMechanism(CompressionConfig(mode=MemoryMode.COMPRESSED))
    gated = ExperienceCompressionMechanism(
        CompressionConfig(
            mode=MemoryMode.COMPRESSED,
            developmental={"condition": "DISABLED"},
        )
    )
    world = ReversalYieldWorld(reversal_after=20)
    for mechanism in (plain, gated):
        registry = MechanismRegistry()
        registry.register(mechanism)
        engine = Engine(
            world=world,
            agents={"A001": Agent(agent_id="A001")},
            seed=17,
            mechanisms=registry,
        )
        actions = [engine.step().actions["A001"].kind for _ in range(25)]
        engine.close()
        if mechanism is plain:
            plain_actions = actions
        else:
            gated_actions = actions
    assert plain_actions == gated_actions


def test_adult_and_developmental_share_seed_but_differ_in_gate():
    seed = 17
    results = {}
    for condition in (
        DevelopmentalCondition.DEVELOPMENTAL,
        DevelopmentalCondition.ADULT_FROM_TICK_0,
    ):
        cfg = DevelopmentalConfig(
            condition=condition,
            min_ticks=20,
            target_ticks=30,
            max_ticks=40,
        )
        world = ContextualObjectEcologyWorld(
            world_config=default_contextual_object_config(seed)
        )
        registry = MechanismRegistry()
        registry.register(SingleOrganismPsycheV05(developmental=cfg))
        engine = Engine(
            world=world,
            agents={"A001": Agent(agent_id="A001")},
            seed=seed,
            mechanisms=registry,
        )
        engine.step()
        psyche = engine.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"]
        results[condition.value] = psyche["memory"]["developmental"]["gate_factor"]
        engine.close()
    assert results["ADULT_FROM_TICK_0"] == 1.0
    assert results["DEVELOPMENTAL"] < 1.0


def test_contradictory_evidence_limits_local_maturity():
    from mechanistic_mind.psyche.developmental import local_experience_maturity

    cfg = DevelopmentalConfig(condition=DevelopmentalCondition.EXPERIENCE_GATED)
    inconsistent = {
        "current_bucket": "b",
        "relevant_fragments": 40,
        "relevant_diversity": 8,
        "repeated_consequences": 20,
        "predictive_evidence": 15,
        "related_weighted_fragments": 0.0,
        "evidence_consistency": 0.1,
        "related_consistency": 1.0,
        "effective_sample_size": 80.0,
        "inspected": 12,
    }
    consistent = dict(inconsistent)
    consistent["evidence_consistency"] = 0.95
    consistent["relevant_fragments"] = 12
    assert local_experience_maturity(consistent, cfg) > local_experience_maturity(inconsistent, cfg)


def test_mature_novel_context_reduces_depth_without_global_reset():
    cfg = DevelopmentalConfig(
        condition=DevelopmentalCondition.EXPERIENCE_GATED,
        min_ticks=10,
        target_ticks=20,
        max_ticks=30,
    )
    rich = {
        "fragment_count": 400,
        "transition_diversity": 80,
        "interaction_diversity": 15,
        "repeated_consequences": 60,
        "predictive_evidence": 40,
    }
    familiar = {
        "current_bucket": "fam",
        "relevant_fragments": 10,
        "relevant_diversity": 4,
        "repeated_consequences": 6,
        "predictive_evidence": 5,
        "related_weighted_fragments": 1.0,
        "evidence_consistency": 0.9,
        "related_consistency": 0.9,
        "effective_sample_size": 30.0,
        "inspected": 8,
    }
    novel = {
        "current_bucket": "nov",
        "relevant_fragments": 0,
        "relevant_diversity": 0,
        "repeated_consequences": 0,
        "predictive_evidence": 0,
        "related_weighted_fragments": 0.0,
        "evidence_consistency": 0.0,
        "related_consistency": 1.0,
        "effective_sample_size": 0.0,
        "inspected": 0,
    }
    g_fam = compute_developmental_gate(tick=1000, config=cfg, metrics=rich, local=familiar)
    g_nov = compute_developmental_gate(tick=1000, config=cfg, metrics=rich, local=novel)
    assert g_fam["global_ceiling"] == g_nov["global_ceiling"] == 1.0
    assert g_nov["cognitive_depth"] < g_fam["cognitive_depth"]
    assert g_nov["depth_limitation_reason"] == "INSUFFICIENT_LOCAL_EVIDENCE"
    assert g_nov["developmental_maturity"] == g_fam["developmental_maturity"]


def test_depth_not_memory_size_alone():
    cfg = DevelopmentalConfig(condition=DevelopmentalCondition.EXPERIENCE_GATED)
    huge_irrelevant = {
        "fragment_count": 10_000,
        "transition_diversity": 10_000,
        "interaction_diversity": 50,
        "repeated_consequences": 10_000,
        "predictive_evidence": 10_000,
    }
    local_empty = {
        "current_bucket": "x",
        "relevant_fragments": 0,
        "relevant_diversity": 0,
        "repeated_consequences": 0,
        "predictive_evidence": 0,
        "related_weighted_fragments": 0.0,
        "evidence_consistency": 0.0,
        "related_consistency": 1.0,
        "effective_sample_size": 0.0,
        "inspected": 0,
    }
    gate = compute_developmental_gate(tick=50_000, config=cfg, metrics=huge_irrelevant, local=local_empty)
    assert gate["developmental_maturity"] > 0.9
    assert gate["gate_factor"] < 0.2
    assert gate["cognitive_depth"] < 1.0


def test_experience_gated_condition_alias_runs():
    cfg = DevelopmentalConfig(
        condition=DevelopmentalCondition.EXPERIENCE_GATED,
        min_ticks=20,
        target_ticks=30,
        max_ticks=40,
    )
    world = ContextualObjectEcologyWorld(world_config=default_contextual_object_config(17))
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV05(developmental=cfg))
    engine = Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=17, mechanisms=registry)
    engine.step()
    psyche = engine.state.agents["A001"].mechanism_states["PSYCHE-SENSORIMOTOR-V05"]["psyche"]
    gate = psyche["memory"]["developmental"]
    assert gate["condition"] == "EXPERIENCE_GATED"
    assert "cognitive_depth" in gate
    assert "local_experience_maturity" in gate
    assert "depth_limitation_reason" in gate
    engine.close()


def test_previous_developmental_experiment_still_importable():
    import experiments.run_developmental_experience_v01 as legacy

    assert callable(legacy.main)
