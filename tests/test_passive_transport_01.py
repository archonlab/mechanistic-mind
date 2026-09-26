"""PASSIVE_TRANSPORT_01 — promoted force_scale=0.15 regressions."""
from __future__ import annotations

import pytest

from mechanistic_mind.model.tiktaalik import tiktaalik_cognition_config, tiktaalik_config
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.ecology_presets import (
    BODY01_PASSIVE_RESERVOIR_TRICKLE,
    ECOLOGY_BASELINE,
    ECOLOGY_CURRENT_LEGACY,
    PASSIVE_TRANSPORT_FORCE_SCALE_PRE,
    PASSIVE_TRANSPORT_FORCE_SCALE_PROMOTED,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from experiments.run_passive_transport_01 import run_transport


def _cfg():
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    return cfg


def test_gate1_promoted_force_scale():
    cfg = _cfg()
    assert float(cfg.body_orientation.force_scale) == pytest.approx(PASSIVE_TRANSPORT_FORCE_SCALE_PROMOTED)
    assert float(tiktaalik_config().body_orientation.force_scale) == pytest.approx(0.15)


def test_A_forced_wait_no_locomotor_impulse():
    m = run_transport(seed=17, ticks=40, mode="WAIT", cfg=_cfg())
    assert m["locomotor_dv_impulse_proxy"] == pytest.approx(0.0)


def test_B_environment_may_move_wait_body():
    m = run_transport(seed=17, ticks=200, mode="WAIT", cfg=_cfg())
    assert m["path_distance"] > 0.0 or m["mean_speed"] > 0.0


def test_C_wait_passive_traversal_bounded_vs_pre():
    pre = _cfg()
    pre.body_orientation.force_scale = float(PASSIVE_TRANSPORT_FORCE_SCALE_PRE)
    base = run_transport(seed=17, ticks=500, mode="WAIT", cfg=pre)
    after = run_transport(seed=17, ticks=500, mode="WAIT", cfg=_cfg())
    assert after["unique_cells"] < base["unique_cells"]
    assert after["unique_cells"] <= 20
    assert after["path_distance"] < 0.5 * base["path_distance"]


def test_D_move_exceeds_wait_spatial_path():
    w = run_transport(seed=29, ticks=1000, mode="WAIT", cfg=_cfg())
    m = run_transport(seed=29, ticks=1000, mode="MOVE_CYCLE", cfg=_cfg())
    assert m["path_distance"] > w["path_distance"] * 2.0


def test_E_RA_RB_present():
    rt = PhysicalSystemRuntime(seed=17, config=_cfg())
    assert float(rt.world.R_A.sum()) > 1.0
    assert float(rt.world.R_B.sum()) > 1.0


def test_F_resource_to_work_still_works():
    cfg = make_ecology_config(ECOLOGY_CURRENT_LEGACY, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    place_source_AB(rt.world, iy, ix, A=2.0, B=2.0)
    w0 = float(rt.body.mechanical_work_reservoir)
    rt.step_forced_action("WAIT")
    assert float(rt.body.mechanical_work_reservoir) > w0


def test_G_no_resource_wait_no_work_and_trickle_zero():
    assert float(BODY01_PASSIVE_RESERVOIR_TRICKLE) == pytest.approx(0.0)
    assert float(_cfg().deformation_work.passive_reservoir_trickle) == pytest.approx(0.0)
    cfg = make_ecology_config(ECOLOGY_CURRENT_LEGACY, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.planet.climate_ecology.enabled = False
    rt = PhysicalSystemRuntime(seed=11, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    import numpy as np
    n = len(cfg.body.footprint)
    rt.body.R_A_site = np.zeros(n)
    rt.body.R_B_site = np.zeros(n)
    for _ in range(40):
        rt.step_forced_action("WAIT")
    assert float(rt.body.mechanical_work_reservoir) == pytest.approx(0.0)


def test_H_legacy_reproducible_empty_resources():
    cfg = make_ecology_config(ECOLOGY_CURRENT_LEGACY)
    assert cfg.planet.climate_ecology.enabled is False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert float(rt.world.R_A.sum()) == pytest.approx(0.0)


def test_I_env_timescale_unchanged():
    cfg = _cfg()
    assert cfg.planet.F_fast_period == 40
    assert cfg.planet.F_slow_period == 400
    assert float(cfg.planet.flow_gain) == pytest.approx(0.14)
    assert float(cfg.planet.flow_max) == pytest.approx(0.16)
    assert cfg.planet.climate_ecology.season_period == 80


def test_J_cognition_config_unchanged_by_ecology_stamp():
    a = tiktaalik_cognition_config()
    b = tiktaalik_config().cognition
    from dataclasses import fields
    for f in fields(a):
        assert getattr(a, f.name) == getattr(b, f.name)
