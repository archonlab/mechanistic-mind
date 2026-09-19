"""Terrain seeding / reproducibility regressions."""
from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_STRUCTURED_TERRAIN,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.planet.runtime import restore_planet_state, serialize_planet_state
from mechanistic_mind.planet.terrain import (
    TERRAIN_GENERATOR_VERSION,
    TerrainConfig,
    deterministic_namespace_seed,
    generate_terrain_fields,
    resolve_terrain_seed,
    terrain_field_checksum,
)


def _terrain_cfg(**kw) -> TerrainConfig:
    base = dict(
        enabled=True,
        mode="CORRELATED",
        drag_base=0.02,
        drag_amplitude=0.4,
        potential_amplitude=0.7,
        correlation_scale=6.0,
        force_scale=0.08,
        drag_coupling=1.0,
        max_gradient=0.35,
    )
    base.update(kw)
    return TerrainConfig(**base)


def _fields(experiment_seed: int, cfg: TerrainConfig, *, h: int = 32, w: int = 32):
    resolved, src = resolve_terrain_seed(experiment_seed, cfg)
    pot, drag, gy, gx, _info = generate_terrain_fields(
        height=h, width=w, terrain_seed=resolved, config=cfg
    )
    return pot, drag, gy, gx, resolved, src


def test_namespace_seed_stable_and_versioned():
    a = deterministic_namespace_seed(17, "terrain")
    b = deterministic_namespace_seed(17, "terrain")
    c = deterministic_namespace_seed(18, "terrain")
    assert a == b
    assert a != c
    assert a != 17  # namespaced, not identity
    assert TERRAIN_GENERATOR_VERSION.startswith("terrain_")


def test_seed_17_reproduces_exactly():
    cfg = _terrain_cfg()
    p1, d1, *_ = _fields(17, cfg)
    p2, d2, *_ = _fields(17, cfg)
    assert np.allclose(p1, p2)
    assert np.allclose(d1, d2)
    assert terrain_field_checksum(p1, d1) == terrain_field_checksum(p2, d2)


def test_seed_17_differs_from_18():
    cfg = _terrain_cfg()
    p17, d17, *_ = _fields(17, cfg)
    p18, d18, *_ = _fields(18, cfg)
    assert not np.allclose(p17, p18)
    assert terrain_field_checksum(p17, d17) != terrain_field_checksum(p18, d18)


def test_agent_seed_does_not_change_terrain():
    """Runtime seed is the experiment seed for terrain; changing after install must not mutate fields."""
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    rt_a = PhysicalSystemRuntime(seed=17, config=deepcopy(cfg))
    pot_a = rt_a.world.terrain_potential.copy()
    # Advance cognition RNG / climate / steps — terrain must stay bit-identical.
    for _ in range(40):
        rt_a.step()
    assert np.allclose(pot_a, rt_a.world.terrain_potential)
    # Different agent runtime with same experiment seed → same terrain
    rt_b = PhysicalSystemRuntime(seed=17, config=deepcopy(cfg))
    assert np.allclose(pot_a, rt_b.world.terrain_potential)
    assert rt_a.world.terrain_meta["terrain_seed"] == rt_b.world.terrain_meta["terrain_seed"]


def test_cognition_rng_consumption_does_not_change_terrain():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    checksum0 = rt.world.terrain_meta["checksum"]
    pot0 = rt.world.terrain_potential.copy()
    for _ in range(80):
        rt.step()
    assert rt.world.terrain_meta["checksum"] == checksum0
    assert np.allclose(pot0, rt.world.terrain_potential)


def test_explicit_terrain_seed_override_matches_across_experiment_seeds():
    cfg = _terrain_cfg(terrain_seed=17)
    p_a, d_a, *_, resolved_a, src_a = _fields(99, cfg)
    p_b, d_b, *_, resolved_b, src_b = _fields(12345, cfg)
    assert src_a == src_b == "override"
    assert resolved_a == resolved_b == 17
    assert np.allclose(p_a, p_b)
    assert np.allclose(d_a, d_b)


def test_drag_never_negative():
    cfg = _terrain_cfg(mode="RUGGED", drag_amplitude=1.0)
    _, drag, *_ = _fields(17, cfg)
    assert float(np.min(drag)) >= 0.0


def test_snapshot_reload_preserves_terrain():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    snap = serialize_planet_state(rt.world, rt.config.planet)
    assert snap["terrain_meta"]["terrain_seed"] is not None
    assert snap["terrain_potential"] is not None
    st2, cfg2 = restore_planet_state(snap)
    assert np.allclose(rt.world.terrain_potential, st2.terrain_potential)
    assert np.allclose(rt.world.terrain_drag, st2.terrain_drag)
    assert st2.terrain_meta["checksum"] == rt.world.terrain_meta["checksum"]
    assert st2.terrain_meta["generator_version"] == TERRAIN_GENERATOR_VERSION


def test_terrain_absent_from_agent_observation():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    obs = rt.agent_observation()
    blob = repr(obs)
    assert "terrain_potential" not in blob
    assert "terrain_drag" not in blob
    assert "terrain_seed" not in blob
    assert "OBSTACLE" not in blob


def test_resources_independent_of_terrain_seed_when_geography_off():
    """Without geography_resources, terrain_seed must not alter R_A/R_B."""
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    cfg.planet.climate_ecology.geography_resources_enabled = False
    cfg_a = deepcopy(cfg)
    cfg_b = deepcopy(cfg)
    cfg_b.planet.terrain.terrain_seed = 999001
    rt_a = PhysicalSystemRuntime(seed=17, config=cfg_a)
    rt_b = PhysicalSystemRuntime(seed=17, config=cfg_b)
    assert not np.allclose(rt_a.world.terrain_potential, rt_b.world.terrain_potential)
    assert np.allclose(rt_a.world.R_A, rt_b.world.R_A)
    assert np.allclose(rt_a.world.R_B, rt_b.world.R_B)


def test_geography_resources_track_terrain_seed():
    """With geography_resources_enabled, terrain_seed conditions R_A/R_B via geo suitability."""
    cfg_a = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    cfg_b = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    cfg_b.planet.terrain.terrain_seed = 999001
    rt_a = PhysicalSystemRuntime(seed=17, config=cfg_a)
    rt_b = PhysicalSystemRuntime(seed=17, config=cfg_b)
    assert not np.allclose(rt_a.world.terrain_potential, rt_b.world.terrain_potential)
    assert not np.allclose(rt_a.world.resource_geo_suit_A, rt_b.world.resource_geo_suit_A)
    assert not np.allclose(rt_a.world.R_A, rt_b.world.R_A)


def test_observer_exposes_terrain_seed():
    from mechanistic_mind.ui.psy_observer_web.serialize import (
        _climate_observer_ground_truth,
        discover_world_fields,
    )

    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    gt = _climate_observer_ground_truth(rt)
    assert gt["terrain"]["enabled"] is True
    assert gt["terrain"]["terrain_seed"] == rt.world.terrain_meta["terrain_seed"]
    assert gt["terrain"]["experiment_seed"] == 17
    ids = {f["id"] for f in discover_world_fields(rt)}
    assert "terrain_potential" in ids
    assert "terrain_drag" in ids
    assert "terrain_grad_mag" in ids
