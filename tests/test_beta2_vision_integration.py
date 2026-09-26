"""Beta 2 vision integration — gates V1–V24."""
from __future__ import annotations

import math
import time
from copy import deepcopy

import numpy as np
import pytest

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_BASELINE,
    ECOLOGY_CALIBRATED_TEMPORAL,
    ECOLOGY_CURRENT_LEGACY,
    ECOLOGY_GENTLE,
    ECOLOGY_STRUCTURED_WORLD,
    make_ecology_config,
)
from mechanistic_mind.physical_system.near_field_exteroception import (
    ACTIVE_SENSOR_ORIENTATION,
    DEFAULT_FOV_DEG,
    DEFAULT_ILLUMINATION_PERIOD,
    angular_sensitivity,
    cognition_exo_fragments,
    distance_attenuation,
    illumination_intensity,
    moore_neighbor_cells,
    sample_near_field,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.research.climate_authority import effective_world_configuration
from mechanistic_mind.ui.psy_observer_web.live_intervention import regimes_from_interventions
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession


def _calibrated(**kw):
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    for k, v in kw.items():
        setattr(cfg.near_field_exteroception, k, v)
    return cfg


def test_V1_V2_V3_moore_r1_eight_no_own():
    nb = moore_neighbor_cells(10, 10, 32, 32)
    assert len(nb) == 8
    assert (10, 10) not in nb
    assert len(set(nb)) == 8


def test_V4_fov_120():
    cfg = _calibrated()
    assert float(cfg.near_field_exteroception.fov_deg) == pytest.approx(DEFAULT_FOV_DEG)
    assert DEFAULT_FOV_DEG == 120.0


def test_V5_V6_orientation_and_rear_blind():
    rt = PhysicalSystemRuntime(seed=17, config=_calibrated())
    rt.body.x = 16.5
    rt.body.y = 16.5
    rt.body.theta = 0.0
    s = rt.world.surface_response
    s[:, :] = 0.0
    s[16, 15] = 1.0  # west / behind
    sample = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    west = next(r for r in sample["neighbors"] if r["cell"] == [15, 16])
    assert west["inside_fov"] is False
    assert west["final_contribution"] == 0.0
    rt.body.theta = math.pi  # face west
    sample2 = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    west2 = next(r for r in sample2["neighbors"] if r["cell"] == [15, 16])
    assert west2["inside_fov"] is True


def test_V7_V8_angular_distance_match_validated():
    assert angular_sensitivity(0.0, 120.0, 2.0) == pytest.approx(1.0)
    assert angular_sensitivity(math.radians(61.0), 120.0, 2.0) == 0.0
    assert distance_attenuation(1.0, 0.85) == pytest.approx(1.0)
    assert distance_attenuation(math.sqrt(2.0), 0.85) < 1.0


def test_V9_V10_illumination_modulates_not_cognition_direct():
    cfg = _calibrated()
    assert int(cfg.near_field_exteroception.illumination_period) == DEFAULT_ILLUMINATION_PERIOD
    i0 = illumination_intensity(0, cfg.near_field_exteroception)
    i_mid = illumination_intensity(120, cfg.near_field_exteroception)
    assert i0 > i_mid
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    obs = rt.agent_observation()
    blob = repr(obs).lower()
    assert "is_day" not in blob and "is_night" not in blob and "darkness" not in blob
    assert audit_cognition_payload(obs) == []


def test_V11_anonymous_exo_only():
    rt = PhysicalSystemRuntime(seed=17, config=_calibrated())
    obs = rt.agent_observation()
    exo = {k: v for k, v in obs.items() if str(k).startswith("exo_")}
    assert set(exo.keys()) <= {"exo_0", "exo_1", "exo_2"}
    assert ACTIVE_SENSOR_ORIENTATION == "NOT_AVAILABLE"


def test_V12_V13_V14_no_gt_leaks():
    rt = PhysicalSystemRuntime(seed=17, config=_calibrated())
    for _ in range(5):
        rt.step()
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    blob = repr(obs).lower()
    for tok in ("r_a", "r_b", "terrain_potential", "terrain_drag", "food", "obstacle", "experimenter"):
        assert tok not in blob


def test_V15_vision_off_no_physics_change():
    cfg = _calibrated()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    for _ in range(8):
        rt.step()
    t0 = rt.world.T.copy()
    ra0 = rt.world.R_A.copy()
    surf0 = rt.world.surface_response.copy()
    body0 = (rt.body.x, rt.body.y, rt.body.theta)
    rt.set_mechanism("physical_near_field_vision", False)
    assert cognition_exo_fragments(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception) == {}
    assert np.allclose(rt.world.T, t0)
    assert np.allclose(rt.world.R_A, ra0)
    assert np.allclose(rt.world.surface_response, surf0)
    assert (rt.body.x, rt.body.y, rt.body.theta) == body0


def test_V16_V17_live_toggle_provenance():
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
    out = s.set_mechanism("physical_near_field_vision", False)
    assert out["control_receipt"]["accepted"]
    assert s._runtime_generation == gen0
    assert [id(rt.cognition) for rt in s.runtime.slots] == cog0
    s.set_mechanism("physical_near_field_vision", True)
    assert len(s._world_interventions) >= 2
    ev = s._world_interventions[-2]
    assert "mechanism.physical_near_field_vision" in ev["changes"]


def test_V18_V19_preset_defaults_explicit():
    cal = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    assert cal.near_field_exteroception.mode == "EXPERIMENTAL"
    assert cal.near_field_exteroception.perception_enabled is True
    assert cal.near_field_exteroception.illumination_enabled is True
    sw = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    assert sw.near_field_exteroception.mode == "EXPERIMENTAL"
    leg = make_ecology_config(ECOLOGY_CURRENT_LEGACY, trickle=0.0)
    assert leg.near_field_exteroception.mode == "OFF"
    gent = make_ecology_config(ECOLOGY_GENTLE, trickle=0.0)
    assert gent.near_field_exteroception.mode == "OFF"
    base = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    assert base.near_field_exteroception.mode == "OFF"


def test_V20_snapshot_reload_preserves_perception():
    rt = PhysicalSystemRuntime(seed=17, config=_calibrated())
    for _ in range(12):
        rt.step()
    rt.body.theta = 0.4
    exo0 = cognition_exo_fragments(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    exo1 = cognition_exo_fragments(world=rt2.world, body=rt2.body, cfg=rt2.config.near_field_exteroception)
    assert exo0 == exo1
    assert rt2.config.near_field_exteroception.mode == "EXPERIMENTAL"
    assert rt2.config.near_field_exteroception.illumination_period == 240


def test_V21_deterministic_exo():
    cfg = _calibrated()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.x = 12.5
    rt.body.y = 14.5
    rt.body.theta = 0.7
    a = cognition_exo_fragments(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    b = cognition_exo_fragments(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    assert a == b


def test_V22_observer_sample_does_not_mutate():
    rt = PhysicalSystemRuntime(seed=17, config=_calibrated())
    t0 = rt.world.T.copy()
    s0 = rt.world.surface_response.copy()
    sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    assert np.allclose(rt.world.T, t0)
    assert np.allclose(rt.world.surface_response, s0)


def test_V23_undercover_no_semantic_identity():
    s = ObserverSession()
    s.apply_experiment({
        "seed": 17,
        "ecology_preset": "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL",
        "agent_count": 1,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    s.step(n=3)
    obs = s.runtime.slots[0].agent_observation() if hasattr(s.runtime, "slots") else s.runtime.agent_observation()
    blob = repr(obs).lower()
    for tok in ("experimenter", "sergey", "teacher", "other_agent", "demonstration"):
        assert tok not in blob
    assert audit_cognition_payload(obs) == []


def test_V24_physical_perception_acceptance_still_valid():
    # Re-assert core P-family invariants under calibrated promotion.
    rt = PhysicalSystemRuntime(seed=17, config=_calibrated())
    assert rt.world.surface_response is not None
    assert float(rt.config.near_field_exteroception.fov_deg) == 120.0
    assert int(rt.config.near_field_exteroception.illumination_period) == 240
    eff = effective_world_configuration(rt)
    assert eff["subsystems"]["physical_near_field_vision"] is True
    assert eff["subsystems"]["illumination_cycle"] is True


def test_illumination_live_freeze():
    rt = PhysicalSystemRuntime(seed=17, config=_calibrated())
    for _ in range(30):
        rt.step()
    before = float(rt.world.illumination_intensity)
    rt.set_mechanism("illumination_cycle", False)
    frozen = float(rt.config.near_field_exteroception.illumination_frozen)
    assert abs(frozen - before) < 1e-9 or abs(frozen - float(rt.world.illumination_intensity)) < 1e-6
    for _ in range(40):
        rt.step()
    assert float(rt.world.illumination_intensity) == pytest.approx(frozen, abs=1e-9)
    rt.set_mechanism("illumination_cycle", True)
    for _ in range(40):
        rt.step()
    assert abs(float(rt.world.illumination_intensity) - frozen) > 1e-6


def test_analyzer_multi_regime_vision():
    s = ObserverSession()
    s.apply_experiment({
        "seed": 17,
        "ecology_preset": "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL",
        "agent_count": 1,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    s.step(n=2)
    s.set_mechanism("physical_near_field_vision", False)
    s.step(n=2)
    s.set_mechanism("physical_near_field_vision", True)
    report = regimes_from_interventions(
        s._world_interventions,
        start_tick=0,
        end_tick=int(s.runtime.tick),
        initial_fingerprint=s._world_intervention_fp0,
    )
    assert report["configuration_history"] == "MULTI_REGIME"
