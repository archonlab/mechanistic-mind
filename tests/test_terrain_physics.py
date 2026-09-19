"""Terrain physics coupling (drag / potential / WAIT / no free energy)."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_BASELINE,
    ECOLOGY_STRUCTURED_TERRAIN,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.planet.terrain import TerrainConfig, set_linear_potential_ramp, set_uniform_terrain


def _phys_cfg(**terrain_kw) -> PhysicalSystemRuntime:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.planet.terrain = TerrainConfig(
        enabled=True,
        mode="FLAT",
        force_scale=0.12,
        drag_coupling=1.0,
        wait_force_scale=0.15,
        terrain_seed=17,
        **terrain_kw,
    )
    return cfg


def test_flat_baseline_move_works():
    cfg = _phys_cfg()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    set_uniform_terrain(rt.world, drag=0.0, experiment_seed=17)
    rt.body.x = 8.0
    rt.body.y = 16.0
    rt.body.mechanical_work_reservoir = 5.0
    x0 = float(rt.body.x)
    for _ in range(40):
        rt.step_forced_action("MOVE:E")
    assert float(rt.body.x) > x0 + 0.5


def test_high_drag_reduces_displacement():
    def path(drag: float) -> float:
        cfg = _phys_cfg()
        rt = PhysicalSystemRuntime(seed=17, config=cfg)
        set_uniform_terrain(rt.world, drag=drag, experiment_seed=17)
        rt.body.x = 8.0
        rt.body.y = 16.0
        rt.body.vx = 0.0
        rt.body.vy = 0.0
        rt.body.mechanical_work_reservoir = 5.0
        x0 = float(rt.body.x)
        for _ in range(80):
            rt.step_forced_action("MOVE:E")
        return abs(float(rt.body.x) - x0)

    assert path(0.9) < 0.9 * path(0.0)


def test_uphill_vs_downhill():
    def dx(amp: float) -> float:
        cfg = _phys_cfg()
        rt = PhysicalSystemRuntime(seed=17, config=cfg)
        set_linear_potential_ramp(rt.world, axis="x", amplitude=amp, drag=0.05, experiment_seed=17)
        rt.body.x = 8.0
        rt.body.y = 16.0
        rt.body.vx = 0.0
        rt.body.vy = 0.0
        rt.body.mechanical_work_reservoir = 5.0
        x0 = float(rt.body.x)
        for _ in range(80):
            rt.step_forced_action("MOVE:E")
        return float(rt.body.x) - x0

    assert dx(-2.0) > dx(2.0)  # downhill assist vs uphill


def test_wait_bounded_on_slope():
    cfg = _phys_cfg()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    set_linear_potential_ramp(rt.world, axis="x", amplitude=2.0, drag=0.1, experiment_seed=17)
    rt.body.x = 16.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    x0 = float(rt.body.x)
    for _ in range(400):
        rt.step_forced_action("WAIT")
    assert abs(float(rt.body.x) - x0) < 6.0


def test_terrain_does_not_credit_work_reservoir():
    cfg = _phys_cfg()
    cfg.planet.climate_ecology.enabled = False
    cfg.complementary_resources.mode = "OFF"
    cfg.complementary_resources.conversion_enabled = False
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    set_linear_potential_ramp(rt.world, axis="x", amplitude=-3.0, drag=0.0, experiment_seed=17)
    rt.body.mechanical_work_reservoir = 0.0
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    n = len(cfg.body.footprint)
    rt.body.R_A_site = np.zeros(n)
    rt.body.R_B_site = np.zeros(n)
    w0 = float(rt.body.mechanical_work_reservoir)
    for _ in range(100):
        rt.step_forced_action("WAIT")
        # Keep environment empty so conversion cannot credit work
        rt.world.R_A[:] = 0.0
        rt.world.R_B[:] = 0.0
    assert float(rt.body.mechanical_work_reservoir) <= w0 + 1e-12


def test_baseline_without_terrain_unchanged_default():
    cfg = make_ecology_config(ECOLOGY_BASELINE)
    assert cfg.planet.terrain.enabled is False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert rt.world.terrain_potential is None


def test_structured_terrain_preset_and_two_agent():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    assert cfg.planet.terrain.enabled is True
    assert float(cfg.deformation_work.passive_reservoir_trickle) == 0.0
    assert float(cfg.body_orientation.force_scale) == pytest.approx(0.15)
    ta = TwoAgentRuntime(seed=17, config=cfg, signal_enabled=False)
    assert ta.world.terrain_potential is not None
    assert float(np.min(ta.world.terrain_drag)) >= 0.0
    for _ in range(10):
        ta.step()


def test_climate_operates_with_terrain():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    t0 = rt.world.T.copy()
    pot0 = rt.world.terrain_potential.copy()
    for _ in range(50):
        rt.step_forced_action("WAIT")
    # Climate may change T; terrain stays static
    assert np.allclose(pot0, rt.world.terrain_potential)
    # T may or may not change depending on forcing — just ensure climate enabled
    assert cfg.planet.climate_ecology.enabled is True
    _ = t0
