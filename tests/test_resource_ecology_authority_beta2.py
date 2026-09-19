"""Beta 2: RESOURCE_ECOLOGY_A/B decoupled from climate dynamics (E1–E20)."""
from __future__ import annotations

import numpy as np
import pytest

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CALIBRATED_TEMPORAL,
    make_ecology_config,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.research.climate_authority import (
    effective_world_configuration,
    effective_world_fingerprint,
)
from mechanistic_mind.ui.psy_observer_web.live_intervention import regimes_from_interventions
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession


def _calibrated():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    return cfg


def test_E1_calibrated_defaults_climate_and_resources_on():
    cfg = _calibrated()
    ce = cfg.planet.climate_ecology
    assert ce.enabled is True
    assert ce.resource_ecology_A_enabled is True
    assert ce.resource_ecology_B_enabled is True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert float(rt.world.R_A.max()) > 0.01
    assert float(rt.world.R_B.max()) > 0.01
    assert float(ce.RA_productivity) == pytest.approx(0.015)
    assert float(ce.RB_productivity) == pytest.approx(0.012)


def test_E2_E3_climate_off_resources_remain_and_evolve():
    cfg = _calibrated()
    cfg.planet.climate_ecology.enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    a0 = float(np.sum(rt.world.R_A))
    b0 = float(np.sum(rt.world.R_B))
    assert a0 > 0.01 and b0 > 0.01
    for _ in range(40):
        rt.step()
    a1 = float(np.sum(rt.world.R_A))
    b1 = float(np.sum(rt.world.R_B))
    assert a1 > 0.01 and b1 > 0.01
    assert abs(a1 - a0) + abs(b1 - b0) > 1e-6


def test_E4_A_off_B_on_independent():
    cfg = _calibrated()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    for _ in range(10):
        rt.step()
    a_before = rt.world.R_A.copy()
    b_before = rt.world.R_B.copy()
    rt.set_mechanism("resource_ecology_A", False)
    for _ in range(30):
        rt.step()
    assert np.allclose(rt.world.R_A, a_before)
    assert not np.allclose(rt.world.R_B, b_before)


def test_E5_A_on_B_off_independent():
    cfg = _calibrated()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    for _ in range(10):
        rt.step()
    a_before = rt.world.R_A.copy()
    b_before = rt.world.R_B.copy()
    rt.set_mechanism("resource_ecology_B", False)
    for _ in range(30):
        rt.step()
    assert np.allclose(rt.world.R_B, b_before)
    assert not np.allclose(rt.world.R_A, a_before)


def test_E6_both_resource_ecologies_off():
    cfg = _calibrated()
    cfg.planet.climate_ecology.resource_ecology_A_enabled = False
    cfg.planet.climate_ecology.resource_ecology_B_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert float(rt.world.R_A.max()) < 1e-9
    assert float(rt.world.R_B.max()) < 1e-9


def test_E7_transfer_independent():
    cfg = _calibrated()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    snap = rt.mechanisms()
    ids = {m["id"] for m in snap["mechanisms"]}
    assert "resource_A_transfer" in ids
    assert "resource_ecology_A" in ids
    rt.set_mechanism("resource_ecology_A", False)
    before = next(m for m in rt.mechanisms()["mechanisms"] if m["id"] == "resource_A_transfer")
    rt.set_mechanism("resource_A_transfer", not bool(before["enabled"]))
    after = next(m for m in rt.mechanisms()["mechanisms"] if m["id"] == "resource_A_transfer")
    assert bool(after["enabled"]) != bool(before["enabled"])


def test_E8_E9_conversion_wiring_and_trickle():
    cfg = _calibrated()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    ids = {m["id"] for m in rt.mechanisms()["mechanisms"]}
    assert "complementary_resource_conversion" in ids
    assert float(cfg.deformation_work.passive_reservoir_trickle) == 0.0


def test_E10_no_cognition_resource_semantics():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    blob = repr(obs).lower()
    assert "food" not in blob
    assert "resource_ecology" not in blob
    assert "climate_ablated" not in blob


def test_E11_E13_live_climate_preserves_agents_and_provenance():
    s = ObserverSession()
    s.apply_experiment({
        "seed": 17,
        "ecology_preset": "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL",
        "agent_count": 2,
        "world": {"width": 24, "height": 24, "boundary_mode": "WRAP_PERIODIC"},
    })
    s.step(n=5)
    tick0 = int(s.runtime.tick)
    gen0 = s._runtime_generation
    ids0 = [id(rt) for rt in s.runtime.slots]
    cog0 = [id(rt.cognition) for rt in s.runtime.slots]
    out = s.set_mechanism("spatiotemporal_climate_ecology", False)
    assert out["control_receipt"]["accepted"]
    assert int(s.runtime.tick) == tick0
    assert s._runtime_generation == gen0
    assert [id(rt) for rt in s.runtime.slots] == ids0
    assert [id(rt.cognition) for rt in s.runtime.slots] == cog0
    assert float(np.sum(s.runtime.world.R_A)) > 0.01
    assert len(s._world_interventions) >= 1
    ev = s._world_interventions[-1]
    assert ev["type"] == "WORLD_INTERVENTION"
    assert "mechanism.spatiotemporal_climate_ecology" in ev["changes"]
    assert ev["changes"]["mechanism.spatiotemporal_climate_ecology"]["old"] is True
    assert ev["changes"]["mechanism.spatiotemporal_climate_ecology"]["new"] is False


def test_E12_live_A_B_toggles_preserve_identity():
    s = ObserverSession()
    s.apply_experiment({
        "seed": 17,
        "ecology_preset": "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL",
        "agent_count": 2,
        "world": {"width": 24, "height": 24, "boundary_mode": "WRAP_PERIODIC"},
    })
    s.step(n=4)
    gen0 = s._runtime_generation
    cog0 = [id(rt.cognition) for rt in s.runtime.slots]
    s.set_mechanism("resource_ecology_A", False)
    s.step(n=2)
    s.set_mechanism("resource_ecology_A", True)
    assert s._runtime_generation == gen0
    assert [id(rt.cognition) for rt in s.runtime.slots] == cog0
    assert len(s._world_interventions) >= 2


def test_E14_analyzer_multi_regime():
    s = ObserverSession()
    s.apply_experiment({
        "seed": 17,
        "ecology_preset": "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL",
        "agent_count": 1,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    s.step(n=3)
    s.set_mechanism("spatiotemporal_climate_ecology", False)
    s.step(n=2)
    s.set_mechanism("resource_ecology_B", False)
    report = regimes_from_interventions(
        s._world_interventions,
        start_tick=0,
        end_tick=int(s.runtime.tick),
        initial_fingerprint=s._world_intervention_fp0,
    )
    assert report["configuration_history"] == "MULTI_REGIME"
    assert report["n_interventions"] >= 2


def test_E15_apply_reset_is_destructive_boundary():
    s = ObserverSession()
    s.apply_experiment({
        "seed": 17,
        "ecology_preset": "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL",
        "agent_count": 1,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    s.step(n=2)
    s.set_mechanism("resource_ecology_A", False)
    assert s._world_interventions
    gen0 = s._runtime_generation
    out = s.apply_experiment({
        "seed": 17,
        "ecology_preset": "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL",
        "agent_count": 1,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    assert out["control_receipt"]["operation"] == "APPLY_AND_RESET_WORLD"
    assert s._runtime_generation == gen0 + 1
    assert s._world_interventions == []


def test_E16_E17_fingerprint_and_effective_world():
    cfg = _calibrated()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    eff = effective_world_configuration(rt)
    assert eff["climate_ecology"]["enabled"] is True
    assert eff["climate_ecology"]["resource_ecology_A_enabled"] is True
    assert eff["climate_ecology"]["resource_ecology_B_enabled"] is True
    fp0 = effective_world_fingerprint(runtime=rt)
    rt.set_mechanism("resource_ecology_A", False)
    fp1 = effective_world_fingerprint(runtime=rt)
    assert fp0 != fp1
    eff2 = effective_world_configuration(rt)
    assert eff2["subsystems"]["resource_A_production"] is False
    assert eff2["subsystems"]["resource_B_production"] is True


def test_E19_habitability_params_unchanged():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    ce = cfg.planet.climate_ecology
    assert int(ce.season_period) == 800
    assert float(ce.RA_productivity) == pytest.approx(0.015)
    assert float(ce.RB_decay) == pytest.approx(0.070)
