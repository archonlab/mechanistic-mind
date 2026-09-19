"""PHYSICAL_GEOGRAPHY_01 — unit/integration gates for structured terrain."""
from __future__ import annotations

import math
from copy import deepcopy

import numpy as np
import pytest
from scipy.stats import pearsonr, spearmanr

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_BASELINE,
    ECOLOGY_STRUCTURED_TERRAIN,
    make_ecology_config,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.planet.terrain import (
    TerrainConfig,
    generate_terrain_fields,
    resolve_terrain_seed,
    set_linear_potential_ramp,
    set_uniform_terrain,
    terrain_field_checksum,
)


def _structured(**kw):
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN, trickle=0.0)
    for k, v in kw.items():
        setattr(cfg.planet.terrain, k, v)
    return cfg


def _phys_cfg(**terrain_kw) -> object:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.planet.climate_ecology.enabled = False
    base = dict(
        enabled=True,
        mode="FLAT",
        force_scale=0.12,
        drag_coupling=1.0,
        wait_force_scale=0.20,
        kinetic_speed_threshold=0.025,
        terrain_seed=17,
    )
    base.update(terrain_kw)
    cfg.planet.terrain = TerrainConfig(**base)
    return cfg


def _neighbor_delta_mean(field: np.ndarray) -> float:
    h, w = field.shape
    vals = [abs(float(field[y, x] - field[y, (x + 1) % w])) for y in range(h) for x in range(w)]
    return float(np.mean(vals))


def test_reproducibility_attempt_and_checksum():
    cfg = _structured()
    rt_a = PhysicalSystemRuntime(seed=17, config=deepcopy(cfg))
    rt_b = PhysicalSystemRuntime(seed=17, config=deepcopy(cfg))
    assert rt_a.world.terrain_meta["checksum"] == rt_b.world.terrain_meta["checksum"]
    assert rt_a.world.terrain_meta["generation_attempt"] == rt_b.world.terrain_meta["generation_attempt"]
    assert np.allclose(rt_a.world.terrain_potential, rt_b.world.terrain_potential)

    resolved, _ = resolve_terrain_seed(17, cfg.planet.terrain)
    pot, drag, *_rest = generate_terrain_fields(
        height=rt_a.world.terrain_potential.shape[0],
        width=rt_a.world.terrain_potential.shape[1],
        terrain_seed=resolved,
        config=cfg.planet.terrain,
    )
    assert terrain_field_checksum(pot, drag) == rt_a.world.terrain_meta["checksum"]
    assert np.allclose(pot, rt_a.world.terrain_potential)


def test_neighbor_correlation_vs_independent_noise():
    cfg = _structured()
    rt = PhysicalSystemRuntime(seed=31, config=cfg)
    pot = np.asarray(rt.world.terrain_potential)
    nbr = _neighbor_delta_mean(pot)
    noise = np.random.default_rng(123).normal(0.0, float(np.std(pot)) + 1e-12, size=pot.shape)
    nbr_noise = _neighbor_delta_mean(noise)
    assert nbr < 0.92 * nbr_noise


def test_traversability_largest_component():
    for seed in (17, 43, 101):
        cfg = _structured()
        rt = PhysicalSystemRuntime(seed=seed, config=cfg)
        audit = rt.world.terrain_meta["traversability_audit"]
        assert audit["passed"] is True
        assert float(audit["largest_component_frac"]) >= 0.52
        assert float(audit["feasible_transition_frac"]) >= 0.58


def test_rng_independence_step_does_not_change_terrain():
    cfg = _structured()
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=71, config=cfg)
    pot0 = rt.world.terrain_potential.copy()
    cs0 = rt.world.terrain_meta["checksum"]
    for _ in range(50):
        rt.step()
    assert np.allclose(pot0, rt.world.terrain_potential)
    assert rt.world.terrain_meta["checksum"] == cs0


def test_resource_geography_correlation_and_no_cognition_leak():
    cfg = _structured()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    geo_A = rt.world.resource_geo_suit_A
    geo_B = rt.world.resource_geo_suit_B
    assert geo_A is not None and geo_B is not None
    sp_a = float(spearmanr(rt.world.R_A.ravel(), geo_A.ravel()).correlation)
    sp_b = float(spearmanr(rt.world.R_B.ravel(), geo_B.ravel()).correlation)
    pe_a = float(pearsonr(rt.world.R_A.ravel(), geo_A.ravel())[0])
    pe_b = float(pearsonr(rt.world.R_B.ravel(), geo_B.ravel())[0])
    assert sp_a > 0.15 and sp_b > 0.15
    assert pe_a > 0.10 and pe_b > 0.10
    assert float(np.mean(np.abs(rt.world.R_A - rt.world.R_B))) > 1e-4
    assert float(np.mean(np.abs(geo_A - geo_B))) > 1e-4

    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    blob = repr(obs)
    assert "resource_geo_suit" not in blob
    assert "terrain_potential" not in blob
    assert "terrain_seed" not in blob


def test_kinetic_wait_continues_downhill_more_than_resting():
    def dx(*, vx0: float) -> float:
        cfg = _phys_cfg()
        cfg.body.drag = 0.15
        rt = PhysicalSystemRuntime(seed=17, config=cfg)
        set_linear_potential_ramp(rt.world, axis="x", amplitude=-3.0, drag=0.0, experiment_seed=17)
        rt.config.planet.terrain.enabled = True
        rt.body.x = 8.0
        rt.body.y = 16.0
        rt.body.vx = vx0
        rt.body.vy = 0.0
        rt.body.mechanical_work_reservoir = 0.0
        x0 = float(rt.body.x)
        for _ in range(80):
            rt.step_forced_action("WAIT")
        return float(rt.body.x) - x0

    assert dx(vx0=0.12) > dx(vx0=0.0) + 0.5


def test_passive_transport_resting_wait_bounded_on_structured_terrain():
    cfg = _structured()
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.x = 16.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    x0, y0 = float(rt.body.x), float(rt.body.y)
    for _ in range(400):
        rt.step_forced_action("WAIT")
    net = math.hypot(float(rt.body.x) - x0, float(rt.body.y) - y0)
    assert net < 2.0


def test_topography_distinctions_via_synthetic_ramps():
    def path(condition: str) -> float:
        cfg = _phys_cfg()
        rt = PhysicalSystemRuntime(seed=17, config=cfg)
        if condition == "FLAT":
            set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=17)
        elif condition == "HIGH_DRAG":
            set_uniform_terrain(rt.world, potential=0.0, drag=0.85, experiment_seed=17)
        elif condition == "UPHILL":
            set_linear_potential_ramp(rt.world, axis="x", amplitude=2.0, drag=0.05, experiment_seed=17)
        elif condition == "DOWNHILL":
            set_linear_potential_ramp(rt.world, axis="x", amplitude=-2.0, drag=0.05, experiment_seed=17)
        else:
            raise ValueError(condition)
        rt.config.planet.terrain.enabled = True
        rt.body.x = 8.0
        rt.body.y = 16.0
        rt.body.vx = 0.0
        rt.body.vy = 0.0
        rt.body.mechanical_work_reservoir = 5.0
        x0 = float(rt.body.x)
        path_len = 0.0
        for _ in range(80):
            xb = float(rt.body.x)
            rt.step_forced_action("MOVE:E")
            path_len += abs(float(rt.body.x) - xb)
        return path_len

    flat = path("FLAT")
    high_drag = path("HIGH_DRAG")
    uphill = path("UPHILL")
    downhill = path("DOWNHILL")
    assert high_drag < 0.95 * flat
    assert uphill < flat
    assert downhill > uphill
