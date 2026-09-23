"""Configuration integrity: mechanism authority × preflight × defaults."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from mechanistic_mind.physical_system.mechanism_configuration import (
    CLIMATE_MECHANISM_ID,
    NEW_EXPERIMENT_VISION_RADIUS,
    apply_resolved_to_runtime,
    excluded_mechanism_catalog,
    fresh_experiment_default_map,
    mechanism_catalog,
    normal_mechanism_ids,
    resolve_mechanism_config,
    run_preflight,
    stamp_config_mechanisms,
    summarize_mechanism_integrity,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def test_CI_fresh_defaults_policy():
    d = fresh_experiment_default_map()
    assert d["physical_near_field_vision"] is True
    assert d["articulated_head"] is True
    assert d["physical_vestibular_sensing"] is True
    assert d["neck_proprioception"] is True
    assert d["physical_push"] is True
    assert d["experimental_physical_signal"] is True
    assert d["resource_ecology_A"] is True
    assert d["resource_ecology_B"] is True
    assert d[CLIMATE_MECHANISM_ID] is False
    assert d["terrain_geography"] is True
    assert d["ambient_physical_dynamics"] is True
    assert d["cognition"] is True
    assert d["illumination_cycle"] is True
    assert d["prospective_scenario_competition"] is False
    # Experimental cognition excluded / OFF
    assert d.get("predictive_equivalence") is False
    assert d.get("unknown_action_physical_probe") is False
    # Catalog drift guard: every NORMAL registry id (except climate and PSC) is ON
    for mid in normal_mechanism_ids():
        if mid == "prospective_scenario_competition":
            assert d[mid] is False, mid
            continue
        assert d[mid] is True, mid
    cat = mechanism_catalog()
    assert NEW_EXPERIMENT_VISION_RADIUS == 3
    assert any(e["id"] == CLIMATE_MECHANISM_ID for e in excluded_mechanism_catalog())


def test_vision_enabled_without_toggle_touch():
    """Original bug regression: Vision ON at start without OFF→ON."""
    s = ObserverSession(config=SessionConfig(seed=101))
    assert s._preflight_result and s._preflight_result["status"] == "READY"
    en = s.runtime.mechanisms()["enabled"]
    assert en["physical_near_field_vision"] is True
    nfe = s.runtime.config.near_field_exteroception
    assert nfe.vision_contributes is True
    assert int(nfe.radius) == 3
    assert s.runtime.world.surface_response is not None
    # Do NOT touch vision toggle — step and verify exo path
    out = s.step(3)
    assert out["control_receipt"]["accepted"] is True
    obs = s.runtime.last_agent_observation or {}
    assert "exo_0" in obs and "exo_1" in obs and "exo_2" in obs
    # Reset / new generation — still ON without toggle
    s.reset(seed=101)
    assert s.runtime.mechanisms()["enabled"]["physical_near_field_vision"] is True
    assert s.runtime.config.near_field_exteroception.vision_contributes is True
    assert s.runtime.world.surface_response is not None
    s.step(2)
    obs2 = s.runtime.last_agent_observation or {}
    assert "exo_0" in obs2


def test_climate_off_resource_on():
    s = ObserverSession(config=SessionConfig(seed=7))
    en = s.runtime.mechanisms()["enabled"]
    assert en[CLIMATE_MECHANISM_ID] is False
    assert en["resource_ecology_A"] is True
    assert en["resource_ecology_B"] is True
    ce = s.runtime.config.planet.climate_ecology
    assert ce.enabled is False
    assert ce.resource_ecology_A_enabled is True
    assert ce.resource_ecology_B_enabled is True
    assert ce.resources_enabled is True
    # R fields exist on planet
    w = s.runtime.world
    assert getattr(w, "R_A", None) is not None or getattr(w, "R", None) is not None


def test_explicit_override_vision_off():
    resolved = resolve_mechanism_config(
        {"physical_near_field_vision": False},
        source_hint="EXPLICIT",
    )
    assert resolved.mechanisms["physical_near_field_vision"] is False
    assert resolved.provenance["physical_near_field_vision"] == "EXPLICIT"
    cfg = PhysicalSystemConfig()
    stamp_config_mechanisms(cfg, resolved)
    rt = PhysicalSystemRuntime(seed=3, config=cfg)
    apply_resolved_to_runtime(rt, resolved)
    pf = run_preflight(rt, resolved)
    assert pf.status == "READY"
    row = next(r for r in pf.rows if r["mechanism"] == "physical_near_field_vision")
    assert row["configured"] is False and row["runtime"] is False


def test_explicit_climate_on():
    resolved = resolve_mechanism_config(
        {CLIMATE_MECHANISM_ID: True},
        source_hint="EXPLICIT",
    )
    assert resolved.mechanisms[CLIMATE_MECHANISM_ID] is True
    cfg = PhysicalSystemConfig()
    stamp_config_mechanisms(cfg, resolved)
    rt = PhysicalSystemRuntime(seed=4, config=cfg)
    apply_resolved_to_runtime(rt, resolved)
    pf = run_preflight(rt, resolved)
    assert pf.status == "READY"
    assert rt.config.planet.climate_ecology.enabled is True


def test_preflight_blocks_mismatch():
    resolved = resolve_mechanism_config(None)  # vision ON
    cfg = PhysicalSystemConfig()
    # Construct WITHOUT applying resolved → vision OFF at runtime
    rt = PhysicalSystemRuntime(seed=5, config=cfg)
    pf = run_preflight(rt, resolved)
    assert pf.status == "PREFLIGHT_FAILED"
    assert any(m["mechanism"] == "physical_near_field_vision" for m in pf.mismatches)


def test_apply_experiment_reapplies_mechanisms():
    s = ObserverSession(config=SessionConfig(seed=11))
    assert s.runtime.mechanisms()["enabled"]["physical_near_field_vision"] is True
    # APPLY without mechanisms map → fresh defaults again
    out = s.apply_experiment({
        "seed": 12,
        "cognition_enabled": True,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    assert out.get("preflight", {}).get("status") == "READY"
    assert s.runtime.mechanisms()["enabled"]["physical_near_field_vision"] is True
    assert int(s.runtime.config.near_field_exteroception.radius) == 3
    # APPLY with explicit vision OFF
    out2 = s.apply_experiment({
        "seed": 13,
        "mechanisms": {"physical_near_field_vision": False},
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    assert out2.get("preflight", {}).get("status") == "READY"
    assert s.runtime.mechanisms()["enabled"]["physical_near_field_vision"] is False


def test_live_toggle_updates_integrity():
    s = ObserverSession(config=SessionConfig(seed=21))
    assert s.runtime.mechanisms()["enabled"]["physical_near_field_vision"] is True
    out = s.set_mechanism("physical_near_field_vision", False)
    assert out["toggle_runtime_applied"] is True
    assert s.runtime.mechanisms()["enabled"]["physical_near_field_vision"] is False
    assert (out.get("preflight") or {}).get("status") == "READY"
    out2 = s.set_mechanism("physical_near_field_vision", True)
    assert s.runtime.mechanisms()["enabled"]["physical_near_field_vision"] is True
    assert s.runtime.world.surface_response is not None
    # Vestibular + PUSH
    s.set_mechanism("physical_vestibular_sensing", False)
    assert s.runtime.mechanisms()["enabled"]["physical_vestibular_sensing"] is False
    s.set_mechanism("physical_vestibular_sensing", True)
    assert s.runtime.mechanisms()["enabled"]["physical_vestibular_sensing"] is True
    s.set_mechanism("physical_push", False)
    s.set_mechanism("physical_push", True)
    assert s.runtime.mechanisms()["enabled"]["physical_push"] is True


def test_play_blocked_on_preflight_failed(monkeypatch):
    s = ObserverSession(config=SessionConfig(seed=31))
    # Force failed preflight
    s._preflight_result = {
        "status": "PREFLIGHT_FAILED",
        "mismatches": [{"mechanism": "physical_near_field_vision", "configured": True, "runtime": False}],
        "rows": [],
    }
    # Prevent auto-rebind repair in _require_preflight_ready
    def _no_bind(**kwargs):
        return {"preflight": s._preflight_result}
    s._bind_and_preflight_locked = _no_bind  # type: ignore
    out = s.play()
    assert out["control_receipt"]["accepted"] is False
    assert out["control_receipt"]["reason"] == "PREFLIGHT_FAILED"
    assert s.runtime.tick == 0


def test_legacy_explicit_off_preserved():
    resolved = resolve_mechanism_config(
        {"physical_near_field_vision": False, "articulated_head": False},
        apply_fresh_defaults=True,
    )
    assert resolved.mechanisms["physical_near_field_vision"] is False
    assert resolved.provenance["physical_near_field_vision"] == "EXPLICIT"
    # Missing new fields migrated
    assert resolved.mechanisms["physical_vestibular_sensing"] is True
    assert resolved.provenance["physical_vestibular_sensing"] == "MIGRATED"


def test_analyzer_manifest_not_available():
    s = summarize_mechanism_integrity(manifest=None, interventions=[])
    assert s["runtime_mechanism_manifest"] == "NOT_AVAILABLE"


def test_explicit_equivalent_fingerprint_match():
    """Fully explicit legacy-equivalent config: physics unchanged by integrity layer."""
    from mechanistic_mind.model.tiktaalik import tiktaalik_config

    cfg_a = tiktaalik_config()
    # Explicit OFF for all new sensors — match old BASELINE vision-off behavior
    resolved = resolve_mechanism_config(
        {
            "physical_near_field_vision": False,
            "illumination_cycle": False,
            "physical_body_optical_response": False,
            "articulated_head": False,
            "physical_vestibular_sensing": False,
            "neck_proprioception": False,
            "physical_push": False,
            "experimental_physical_signal": False,
            "terrain_geography": False,
            "ambient_physical_dynamics": False,
            CLIMATE_MECHANISM_ID: True,
            "resource_ecology_A": True,
            "resource_ecology_B": True,
        },
        vision_radius=1,
        apply_fresh_defaults=False,
    )
    # Without integrity stamp
    rt_legacy = PhysicalSystemRuntime(seed=99, config=tiktaalik_config())
    # With integrity stamp matching legacy
    cfg_b = tiktaalik_config()
    stamp_config_mechanisms(cfg_b, resolved)
    rt_new = PhysicalSystemRuntime(seed=99, config=cfg_b)
    apply_resolved_to_runtime(rt_new, resolved)
    for _ in range(20):
        rt_legacy.step(1)
        rt_new.step(1)
    assert abs(float(rt_legacy.body.x) - float(rt_new.body.x)) < 1e-9
    assert abs(float(rt_legacy.body.y) - float(rt_new.body.y)) < 1e-9
    assert abs(float(rt_legacy.body.theta) - float(rt_new.body.theta)) < 1e-9


def test_sensor_availability_allows_zero():
    s = ObserverSession(config=SessionConfig(seed=41))
    # Stationary — vest may be ~0 but available
    row = next(
        r for r in s._preflight_result["rows"]
        if r["mechanism"] == "physical_vestibular_sensing"
    )
    assert row["configured"] is True
    assert row["runtime"] is True
    assert row["available"] is True
    assert row["status"] == "READY"
