"""AMBIENT_HORIZONTAL_DYNAMICS_01 — ambient field / coupling validation."""
from __future__ import annotations

import math
from copy import deepcopy

import numpy as np
import pytest

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_BASELINE,
    ECOLOGY_STRUCTURED_TERRAIN,
    ECOLOGY_STRUCTURED_WORLD,
    make_ecology_config,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.planet.ambient import (
    AMBIENT_GENERATOR_VERSION,
    AmbientConfig,
    ambient_field_checksum,
    generate_ambient_fields,
    resolve_ambient_seed,
    set_uniform_ambient,
)
from mechanistic_mind.planet.runtime import restore_planet_state, serialize_planet_state
from mechanistic_mind.planet.terrain import TerrainConfig, set_linear_potential_ramp, set_uniform_terrain
from mechanistic_mind.ui.psy_observer_web.serialize import discover_world_fields, world_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _phys_cfg(*, ambient_enabled: bool = True, **ambient_kw) -> object:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.planet.climate_ecology.enabled = False
    cfg.planet.terrain = TerrainConfig(
        enabled=True,
        mode="FLAT",
        force_scale=0.12,
        drag_coupling=1.0,
        wait_force_scale=0.15,
        terrain_seed=17,
    )
    cfg.planet.ambient = AmbientConfig(
        enabled=ambient_enabled,
        amplitude=0.018,
        correlation_scale=8.0,
        wait_force_scale=0.15,
        kinetic_speed_threshold=0.025,
        max_component=0.045,
        ambient_seed=17,
        **ambient_kw,
    )
    return cfg


def _neighbor_delta_mean(field: np.ndarray) -> float:
    h, w = field.shape
    vals = [abs(float(field[y, x] - field[y, (x + 1) % w])) for y in range(h) for x in range(w)]
    vals += [abs(float(field[y, x] - field[(y + 1) % h, x])) for y in range(h) for x in range(w)]
    return float(np.mean(vals))


def test_determinism_same_seed():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    rt_a = PhysicalSystemRuntime(seed=17, config=deepcopy(cfg))
    rt_b = PhysicalSystemRuntime(seed=17, config=deepcopy(cfg))
    assert rt_a.world.ambient_fx is not None and rt_a.world.ambient_fy is not None
    assert np.allclose(rt_a.world.ambient_fx, rt_b.world.ambient_fx)
    assert np.allclose(rt_a.world.ambient_fy, rt_b.world.ambient_fy)
    assert rt_a.world.ambient_meta["checksum"] == rt_b.world.ambient_meta["checksum"]
    resolved, _ = resolve_ambient_seed(17, cfg.planet.ambient)
    fx, fy = generate_ambient_fields(
        height=rt_a.world.ambient_fx.shape[0],
        width=rt_a.world.ambient_fx.shape[1],
        ambient_seed=resolved,
        config=cfg.planet.ambient,
    )
    assert ambient_field_checksum(fx, fy) == rt_a.world.ambient_meta["checksum"]


def test_rng_independence_terrain_seed_does_not_change_ambient():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    cfg_a = deepcopy(cfg)
    cfg_b = deepcopy(cfg)
    cfg_a.planet.terrain.terrain_seed = 111
    cfg_b.planet.terrain.terrain_seed = 999
    # Keep ambient seed fixed via override.
    cfg_a.planet.ambient.ambient_seed = 42
    cfg_b.planet.ambient.ambient_seed = 42
    rt_a = PhysicalSystemRuntime(seed=17, config=cfg_a)
    rt_b = PhysicalSystemRuntime(seed=17, config=cfg_b)
    assert not np.allclose(rt_a.world.terrain_potential, rt_b.world.terrain_potential)
    assert np.allclose(rt_a.world.ambient_fx, rt_b.world.ambient_fx)
    assert np.allclose(rt_a.world.ambient_fy, rt_b.world.ambient_fy)


def test_rng_independence_ambient_seed_does_not_change_terrain():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    cfg_a = deepcopy(cfg)
    cfg_b = deepcopy(cfg)
    cfg_a.planet.terrain.terrain_seed = 55
    cfg_b.planet.terrain.terrain_seed = 55
    cfg_a.planet.ambient.ambient_seed = 7
    cfg_b.planet.ambient.ambient_seed = 7007
    rt_a = PhysicalSystemRuntime(seed=17, config=cfg_a)
    rt_b = PhysicalSystemRuntime(seed=17, config=cfg_b)
    assert np.allclose(rt_a.world.terrain_potential, rt_b.world.terrain_potential)
    assert not np.allclose(rt_a.world.ambient_fx, rt_b.world.ambient_fx)


def test_spatial_correlation_vs_independent_noise():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    rt = PhysicalSystemRuntime(seed=31, config=cfg)
    fx = np.asarray(rt.world.ambient_fx)
    nbr = _neighbor_delta_mean(fx)
    noise = np.random.default_rng(123).normal(0.0, float(np.std(fx)) + 1e-12, size=fx.shape)
    nbr_noise = _neighbor_delta_mean(noise)
    assert nbr < 0.92 * nbr_noise


def test_boundedness_components():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    bound = float(cfg.planet.ambient.max_component)
    assert float(np.max(np.abs(rt.world.ambient_fx))) <= bound + 1e-12
    assert float(np.max(np.abs(rt.world.ambient_fy))) <= bound + 1e-12


def test_zero_field_no_deflection():
    cfg = _phys_cfg()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=17)
    set_uniform_ambient(rt.world, fx=0.0, fy=0.0, experiment_seed=17, config=cfg.planet.ambient)
    rt.body.x = 8.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    rt.body.mechanical_work_reservoir = 5.0
    y0 = float(rt.body.y)
    for _ in range(60):
        rt.step_forced_action("MOVE:E")
    assert abs(float(rt.body.y) - y0) < 1e-9


def test_weak_deflection_ordering():
    def dy(fy: float) -> float:
        cfg = _phys_cfg()
        rt = PhysicalSystemRuntime(seed=17, config=cfg)
        set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=17)
        set_uniform_ambient(rt.world, fx=0.0, fy=fy, experiment_seed=17, config=cfg.planet.ambient)
        rt.body.x = 8.0
        rt.body.y = 16.0
        rt.body.vx = 0.0
        rt.body.vy = 0.0
        rt.body.mechanical_work_reservoir = 5.0
        y0 = float(rt.body.y)
        x0 = float(rt.body.x)
        for _ in range(80):
            rt.step_forced_action("MOVE:E")
        assert float(rt.body.x) - x0 > abs(float(rt.body.y) - y0)
        return abs(float(rt.body.y) - y0)

    assert dy(0.01) > dy(0.0) + 1e-4
    assert dy(0.03) > dy(0.01) + 1e-4


def test_resting_wait_bound_weak_ambient():
    cfg = _phys_cfg()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=17)
    set_uniform_ambient(rt.world, fx=0.0, fy=0.01, experiment_seed=17, config=cfg.planet.ambient)
    rt.body.x = 16.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    x0, y0 = float(rt.body.x), float(rt.body.y)
    for _ in range(1000):
        rt.step_forced_action("WAIT")
    w = int(rt.config.planet.width)
    dx = float(rt.body.x) - x0
    dy = float(rt.body.y) - y0
    if dx > w / 2:
        dx -= w
    if dx < -w / 2:
        dx += w
    h = int(rt.config.planet.height)
    if dy > h / 2:
        dy -= h
    if dy < -h / 2:
        dy += h
    net = math.hypot(dx, dy)
    assert net < 8.0
    assert net < 0.5 * w


def test_kinetic_wait_aligned_vs_opposing_and_crosswise():
    def finals(fx: float, fy: float) -> tuple[float, float]:
        cfg = _phys_cfg()
        cfg.body.drag = 0.15
        rt = PhysicalSystemRuntime(seed=17, config=cfg)
        set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=17)
        set_uniform_ambient(rt.world, fx=fx, fy=fy, experiment_seed=17, config=cfg.planet.ambient)
        rt.body.x = 8.0
        rt.body.y = 16.0
        rt.body.vx = 0.12
        rt.body.vy = 0.0
        for _ in range(80):
            rt.step_forced_action("WAIT")
        return float(rt.body.vx), float(rt.body.vy)

    vx_a, _ = finals(0.02, 0.0)
    vx_o, _ = finals(-0.02, 0.0)
    vx_z, vy_z = finals(0.0, 0.0)
    _, vy_c = finals(0.0, 0.02)
    assert vx_a > vx_o + 1e-4
    assert abs(vy_c) > abs(vy_z) + 1e-4


def test_composition_terrain_plus_ambient():
    def metrics(*, downhill: bool, ambient_fx: float = 0.0, ambient_fy: float = 0.0) -> dict[str, float]:
        cfg = _phys_cfg()
        rt = PhysicalSystemRuntime(seed=17, config=cfg)
        if downhill:
            set_linear_potential_ramp(rt.world, axis="x", amplitude=-2.0, drag=0.05, experiment_seed=17)
        else:
            set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=17)
        set_uniform_ambient(
            rt.world, fx=ambient_fx, fy=ambient_fy, experiment_seed=17, config=cfg.planet.ambient
        )
        rt.body.x = 8.0
        rt.body.y = 16.0
        rt.body.vx = 0.0
        rt.body.vy = 0.0
        rt.body.mechanical_work_reservoir = 5.0
        x0, y0 = float(rt.body.x), float(rt.body.y)
        for _ in range(80):
            rt.step_forced_action("MOVE:E")
        om = rt.last_orientation_meta or {}
        return {
            "dx": float(rt.body.x) - x0,
            "dy": float(rt.body.y) - y0,
            "terrain_fx": float((om.get("terrain") or {}).get("fx") or 0.0),
            "ambient_fy": float((om.get("ambient") or {}).get("fy") or 0.0),
        }

    flat_z = metrics(downhill=False, ambient_fy=0.0)
    flat_c = metrics(downhill=False, ambient_fy=0.02)
    dh_z = metrics(downhill=True, ambient_fy=0.0)
    dh_c = metrics(downhill=True, ambient_fy=0.02)
    dh_aligned = metrics(downhill=True, ambient_fx=0.02)
    dh_opposing = metrics(downhill=True, ambient_fx=-0.02)
    assert abs(flat_c["dy"]) > abs(flat_z["dy"]) + 1e-4
    assert abs(dh_c["dy"]) > abs(dh_z["dy"]) + 1e-4
    assert abs(dh_z["terrain_fx"]) > 1e-6
    assert abs(flat_c["ambient_fy"]) > 1e-6
    assert dh_aligned["dx"] > dh_opposing["dx"] + 1e-4


def test_snapshot_round_trip_preserves_ambient():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    snap = serialize_planet_state(rt.world, rt.config.planet)
    assert snap["ambient_fx"] is not None
    assert snap["ambient_meta"]["checksum"] is not None
    st2, _cfg2 = restore_planet_state(snap)
    assert np.allclose(rt.world.ambient_fx, st2.ambient_fx)
    assert np.allclose(rt.world.ambient_fy, st2.ambient_fy)
    assert st2.ambient_meta["checksum"] == rt.world.ambient_meta["checksum"]
    assert st2.ambient_meta["generator_version"] == AMBIENT_GENERATOR_VERSION

    # Full runtime snapshot / restore
    full = rt.snapshot()
    restored = PhysicalSystemRuntime.restore(full)
    assert np.allclose(rt.world.ambient_fx, restored.world.ambient_fx)
    assert restored.world.ambient_meta["checksum"] == rt.world.ambient_meta["checksum"]


def test_observer_gt_exposes_ambient():
    s = ObserverSession(SessionConfig(seed=0))
    frame = s.apply_experiment(
        {
            "seed": 17,
            "ecology_preset": ECOLOGY_STRUCTURED_WORLD,
            "cognition_enabled": False,
            "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
        }
    )
    gt = (frame.get("experiment") or {}).get("observer_ground_truth") or {}
    amb = gt.get("ambient") or {}
    assert amb.get("enabled") is True
    assert amb.get("checksum") == s.runtime.world.ambient_meta["checksum"]
    assert amb.get("generator_version") == s.runtime.world.ambient_meta["generator_version"]
    wf = world_frame(s.runtime, detail="compact")
    scalars = wf.get("scalars") or {}
    assert "ambient_fx" in scalars
    assert "ambient_fy" in scalars
    assert "ambient_magnitude" in scalars
    ids = {f["id"]: f for f in discover_world_fields(s.runtime)}
    assert ids["ambient_force"].get("observer_ground_truth") is True
    assert ids["ambient_magnitude"].get("observer_ground_truth") is True


def test_cognition_leak_forbidden():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    blob = repr(obs)
    assert "ambient_fx" not in blob
    assert "ambient_fy" not in blob
    assert "ambient_force" not in blob
    assert "ambient_seed" not in blob


def test_structured_terrain_ambient_off():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_TERRAIN, trickle=0.0)
    assert cfg.planet.ambient.enabled is False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert rt.world.ambient_fx is None
    assert rt.world.ambient_fy is None
    # When ambient stays disabled, grids are absent; meta may be unset or enabled=False.
    meta = rt.world.ambient_meta
    assert meta is None or meta.get("enabled") is False


def test_structured_world_ambient_on():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    assert cfg.planet.ambient.enabled is True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert rt.world.ambient_fx is not None
    assert rt.world.ambient_fy is not None
    assert rt.world.ambient_meta["enabled"] is True


def test_baseline_ambient_off():
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    assert cfg.planet.ambient.enabled is False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert rt.world.ambient_fx is None
