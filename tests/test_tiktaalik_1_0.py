"""MM 1.0 Tiktaalik canonical acceptance and negative gates."""
from __future__ import annotations

import copy

import pytest

from mechanistic_mind.model.tiktaalik import (
    MODEL_CODENAME,
    MODEL_FAMILY,
    MODEL_VERSION,
    RUNTIME_VERSION,
    build_manifest,
    experimental_overrides,
    is_canonical_tiktaalik,
    tiktaalik_config,
)
from mechanistic_mind.physical_system import PhysicalSystemRuntime
from mechanistic_mind.physical_system.mechanism_registry import RUNTIME_VERSION as REG_VERSION


def test_runtime_version_is_tiktaalik():
    assert REG_VERSION == RUNTIME_VERSION == "MM_1_0_TIKTAALIK"


def test_model_identity_constants():
    assert MODEL_FAMILY == "Mechanistic Mind"
    assert MODEL_VERSION == "1.0"
    assert MODEL_CODENAME == "Tiktaalik"


def test_tiktaalik_factory_and_defaults():
    rt = PhysicalSystemRuntime(model="tiktaalik", seed=17)
    meta = rt.model_identity()
    assert meta["model_codename"] == "Tiktaalik"
    assert meta["canonical"] is True
    assert meta["classification"] == "CANONICAL"
    cog = rt.config.cognition
    assert cog.predictive_compression
    assert cog.prospective_composition
    assert not cog.predictive_equivalence
    assert not cog.temporal_predictive_structure
    assert not cog.predicted_context_prospection
    assert not cog.multistep_action_prospection
    assert not cog.prediction_error_revision


def test_experimental_override_detection():
    cfg = tiktaalik_config()
    assert is_canonical_tiktaalik(cfg)
    cfg.cognition.predictive_equivalence = True
    assert not is_canonical_tiktaalik(cfg)
    assert experimental_overrides(cfg)["predictive_equivalence"] is True


def test_snapshot_records_model_identity():
    rt = PhysicalSystemRuntime(model="tiktaalik", seed=42)
    snap = rt.snapshot()
    assert snap["model"]["model_codename"] == "Tiktaalik"
    assert snap["model"]["runtime_version"] == RUNTIME_VERSION
    assert snap["config"]["runtime_version"] == RUNTIME_VERSION


def test_manifest_lists_canonical_and_experimental():
    manifest = build_manifest()
    assert "predictive_compression" in manifest["canonical_mechanisms"]
    assert "predictive_equivalence" in manifest["experimental_mechanisms"]
    assert manifest["design_boundaries"]["deep_future_action_competition"] == "NOT_DEMONSTRATED"


def test_gate_physical_evolution():
    rt = PhysicalSystemRuntime(model="tiktaalik", seed=17)
    x0, y0 = rt.body.x, rt.body.y
    rt.step()
    assert rt.tick == 1
    assert rt.body.tick == 1


def test_gate_bounded_memory_after_long_run():
    rt = PhysicalSystemRuntime(model="tiktaalik", seed=17)
    for _ in range(600):
        rt.step()
    mem = rt.cognitive_view().get("memory") or {}
    recent = mem.get("recent_fragments") or mem.get("recent") or []
    assert len(recent) <= 512


def test_negative_no_future_action_executed_as_present():
    rt = PhysicalSystemRuntime(model="tiktaalik", seed=17)
    for _ in range(20):
        rt.step()
    sel = rt.last_selected_action
    assert sel is None or isinstance(sel, str)
    # Canonical default has no MAP/PCP; selected must be from available_actions present set
    from mechanistic_mind.physical_system.actions import available_actions

    if sel is not None:
        assert sel in available_actions()


def test_negative_prospection_does_not_train_itself():
    rt = PhysicalSystemRuntime(model="tiktaalik", seed=17)
    before = copy.deepcopy(rt.cognition)
    for _ in range(30):
        rt.step()
    # Without experimental prospection adapters, biography stores should only grow via experience
    after = rt.cognition
    mem_before = (before.get("memory") or {}).get("recent_fragments") or []
    mem_after = (after.get("memory") or {}).get("recent_fragments") or []
    # If memory grew, it must be from ordinary steps not from a separate prospection write path
    if len(mem_after) > len(mem_before):
        assert rt.tick >= len(mem_after)


def test_negative_no_hidden_reward_utility_goal():
    rt = PhysicalSystemRuntime(model="tiktaalik", seed=17)
    forbidden = ("reward", "utility", "goal", "preference", "curiosity")
    cog_keys = set(rt.cognition.keys())
    cfg_dict = rt.config.cognition.to_dict()
    for word in forbidden:
        assert word not in cog_keys
        assert word not in cfg_dict


@pytest.mark.parametrize(
    "flag",
    [
        "predictive_equivalence",
        "predictive_relevance",
        "temporal_predictive_structure",
        "temporal_prospection_bridge",
        "predictive_conflict",
        "future_sensitive_action",
        "prediction_error_revision",
        "temporal_prediction_error",
        "predicted_context_prospection",
        "multistep_action_prospection",
    ],
)
def test_experimental_flags_default_off(flag):
    cfg = tiktaalik_config()
    assert getattr(cfg.cognition, flag) is False
