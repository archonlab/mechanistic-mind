"""PHYSICAL_PERCEPTION_01 — focused automated acceptance tests."""
from __future__ import annotations

import math
from copy import deepcopy

import numpy as np
import pytest

from mechanistic_mind.physical_system.near_field_exteroception import (
    ACTIVE_SENSOR_ORIENTATION,
    DEFAULT_FOV_DEG,
    DEFAULT_ILLUMINATION_PERIOD,
    NearFieldExteroceptionConfig,
    angular_sensitivity,
    cognition_exo_fragments,
    illumination_intensity,
    install_surface_on_planet,
    moore_neighbor_cells,
    sample_near_field,
    wrap_angle,
)
from mechanistic_mind.physical_system.observation import accessible_observation, audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_body.config import default_physical_body2_config


def _nfe_cfg(**kw) -> NearFieldExteroceptionConfig:
    base = dict(
        mode="EXPERIMENTAL",
        perception_enabled=True,
        fov_deg=DEFAULT_FOV_DEG,
        illumination_period=DEFAULT_ILLUMINATION_PERIOD,
        illumination_min=0.15,
        illumination_max=1.0,
        threshold=0.04,
        gain=1.0,
        surface_mode="INDEPENDENT",
    )
    base.update(kw)
    return NearFieldExteroceptionConfig(**base)


def _runtime_with_nfe(**kw) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.near_field_exteroception = _nfe_cfg(**kw)
    return PhysicalSystemRuntime(seed=17, config=cfg)


def test_moore_exactly_eight_and_no_own_cell():
    nb = moore_neighbor_cells(16, 16, 32, 32)
    assert len(nb) == 8
    assert (16, 16) not in nb
    assert len(set(nb)) == 8


def test_moore_wrap_boundaries_and_corner():
    for cx, cy in [(0, 0), (0, 16), (31, 0), (31, 31)]:
        nb = moore_neighbor_cells(cx, cy, 32, 32)
        assert len(nb) == 8
        assert all(0 <= x < 32 and 0 <= y < 32 for x, y in nb)
        assert (cx, cy) not in nb
    # corner (0,0) must include (31,31)
    assert (31, 31) in moore_neighbor_cells(0, 0, 32, 32)


def test_rear_blind_and_rotation_reveals():
    rt = _runtime_with_nfe()
    # Body at center; face +x (east). Place strong surface behind (west).
    rt.body.x = 16.5
    rt.body.y = 16.5
    rt.body.theta = 0.0  # forward = +x
    s = rt.world.surface_response
    assert s is not None
    s[:, :] = 0.0
    s[16, 15] = 1.0  # west neighbor cell (x=15)
    s[16, 17] = 0.0
    sample = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    west = next(r for r in sample["neighbors"] if r["cell"] == [15, 16])
    assert west["inside_fov"] is False
    assert west["final_contribution"] == 0.0
    assert sample["fragments"]["exo_0"] + sample["fragments"]["exo_1"] + sample["fragments"]["exo_2"] == 0.0

    # Rotate body 180° — west becomes forward.
    rt.body.theta = math.pi
    sample2 = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    west2 = next(r for r in sample2["neighbors"] if r["cell"] == [15, 16])
    assert west2["inside_fov"] is True
    assert west2["final_contribution"] > 0.0
    assert sum(sample2["fragments"].values()) > 0.0


def test_outside_fov_zero_and_angular_continuity():
    assert angular_sensitivity(math.pi, 120.0) == 0.0
    assert angular_sensitivity(0.0, 120.0) == pytest.approx(1.0)
    half = math.radians(60)
    vals = [angular_sensitivity(a, 120.0) for a in np.linspace(0, half, 20)]
    assert all(vals[i] >= vals[i + 1] - 1e-12 for i in range(len(vals) - 1))
    assert angular_sensitivity(half + 0.01, 120.0) == 0.0


def test_cardinal_vs_diagonal_distance():
    rt = _runtime_with_nfe()
    rt.body.x = 16.5
    rt.body.y = 16.5
    rt.body.theta = 0.0
    s = rt.world.surface_response
    s[:, :] = 1.0
    sample = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    east = next(r for r in sample["neighbors"] if r["cell"] == [17, 16])
    ne = next(r for r in sample["neighbors"] if r["cell"] == [17, 15])
    assert east["distance"] == pytest.approx(1.0, abs=0.05)
    assert ne["distance"] == pytest.approx(math.sqrt(2.0), abs=0.1)
    assert east["distance_factor"] > ne["distance_factor"]


def test_two_cell_distant_source_invisible():
    rt = _runtime_with_nfe(threshold=0.0, gain=100.0)
    rt.body.x = 16.5
    rt.body.y = 16.5
    rt.body.theta = 0.0
    s = rt.world.surface_response
    s[:, :] = 0.0
    s[16, 18] = 1.0  # two cells east — outside Moore R=1
    sample = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    assert all(r["cell"] != [18, 16] for r in sample["neighbors"])
    assert sum(sample["fragments"].values()) == 0.0


def test_illumination_causal_and_dark():
    rt = _runtime_with_nfe(illumination_min=0.15, illumination_max=1.0, threshold=0.08)
    rt.body.x = 16.5
    rt.body.y = 16.5
    rt.body.theta = 0.0
    s = rt.world.surface_response
    s[:, :] = 0.0
    s[16, 17] = 0.5
    hi_cfg = deepcopy(rt.config.near_field_exteroception)
    hi_cfg.illumination_min = 1.0
    hi_cfg.illumination_max = 1.0
    lo_cfg = deepcopy(hi_cfg)
    lo_cfg.illumination_min = 0.2
    lo_cfg.illumination_max = 0.2
    dark_cfg = deepcopy(hi_cfg)
    dark_cfg.illumination_min = 0.01
    dark_cfg.illumination_max = 0.01
    hi = sample_near_field(world=rt.world, body=rt.body, cfg=hi_cfg, tick=0)
    lo = sample_near_field(world=rt.world, body=rt.body, cfg=lo_cfg, tick=0)
    dark = sample_near_field(world=rt.world, body=rt.body, cfg=dark_cfg, tick=0)
    assert hi["aggregate_intensity"] > lo["aggregate_intensity"] >= dark["aggregate_intensity"]
    assert hi["n_detectable"] >= lo["n_detectable"] >= dark["n_detectable"]


def test_illumination_smooth_continuity():
    cfg = _nfe_cfg()
    vals = [illumination_intensity(t, cfg) for t in range(cfg.illumination_period)]
    diffs = [abs(vals[i + 1] - vals[i]) for i in range(len(vals) - 1)]
    # No jump larger than ~2π/P * amplitude
    assert max(diffs) < 0.05


def test_sensor_ablation_clean():
    rt = _runtime_with_nfe()
    rt.body.x = 16.5
    rt.body.y = 16.5
    rt.body.theta = 0.0
    rt.world.surface_response[:, :] = 0.8
    on = rt.agent_observation()
    assert any(k.startswith("exo_") for k in on)
    rt.config.near_field_exteroception.perception_enabled = False
    off = rt.agent_observation()
    assert not any(k.startswith("exo_") for k in off)
    # body-local keys remain
    assert "body.T" in off and "local.T" in off


def test_no_gt_leak_in_observation():
    rt = _runtime_with_nfe()
    obs = rt.agent_observation()
    hits = audit_cognition_payload(obs)
    assert hits == []
    banned = (
        "terrain", "potential", "drag", "gradient", "resource_A", "resource_B",
        "illumination_phase", "surface_response", "surface_seed", "world_x", "world_y",
        "DAY", "NIGHT", "obstacle", "food",
    )
    text = repr(obs)
    for b in banned:
        assert b not in text


def test_physics_invariant_sensor_on_off():
    cfg_off = PhysicalSystemConfig()
    cfg_off.cognition.cognition_enabled = False
    cfg_on = deepcopy(cfg_off)
    cfg_on.near_field_exteroception = _nfe_cfg()
    a = PhysicalSystemRuntime(seed=17, config=cfg_off)
    b = PhysicalSystemRuntime(seed=17, config=cfg_on)
    for _ in range(30):
        a.step_forced_action("WAIT")
        b.step_forced_action("WAIT")
    assert a.body.x == pytest.approx(b.body.x, abs=1e-9)
    assert a.body.y == pytest.approx(b.body.y, abs=1e-9)
    assert a.body.vx == pytest.approx(b.body.vx, abs=1e-9)
    assert float(a.body.mechanical_work_reservoir) == pytest.approx(
        float(b.body.mechanical_work_reservoir), abs=1e-9
    )


def test_deterministic_replay_and_snapshot():
    rt = _runtime_with_nfe()
    rt.body.x = 10.3
    rt.body.y = 12.7
    rt.body.theta = 0.4
    s1 = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    s2 = sample_near_field(world=rt2.world, body=rt2.body, cfg=rt2.config.near_field_exteroception)
    assert s1["fragments"] == s2["fragments"]
    assert s1["aggregate_intensity"] == pytest.approx(s2["aggregate_intensity"])
    assert (rt.world.surface_meta or {}).get("checksum") == (rt2.world.surface_meta or {}).get("checksum")


def test_sensor_has_no_memory():
    rt = _runtime_with_nfe()
    rt.body.x = 16.5
    rt.body.y = 16.5
    rt.body.theta = 0.0
    rt.world.surface_response[:, :] = 0.0
    rt.world.surface_response[16, 17] = 1.0
    a = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, tick=10)
    # Change world; no stored history in sensor
    rt.world.surface_response[16, 17] = 0.0
    b = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, tick=10)
    assert sum(a["fragments"].values()) > 0
    assert sum(b["fragments"].values()) == 0


def test_active_orientation_status_explicit():
    assert ACTIVE_SENSOR_ORIENTATION == "NOT_AVAILABLE"


def test_appearance_mechanics_separable_fragments():
    """Same surface → matched exo; different surface → different exo (mechanics unused)."""
    rt = _runtime_with_nfe()
    rt.body.x = 16.5
    rt.body.y = 16.5
    rt.body.theta = 0.0
    s = rt.world.surface_response
    s[:, :] = 0.0
    s[16, 17] = 0.7
    f1 = cognition_exo_fragments(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    s[16, 17] = 0.7  # identical
    f2 = cognition_exo_fragments(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    assert f1 == f2
    s[16, 17] = 0.2
    f3 = cognition_exo_fragments(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    assert f1 != f3


def test_own_cell_not_in_exteroception():
    rt = _runtime_with_nfe(threshold=0.0)
    rt.body.x = 16.5
    rt.body.y = 16.5
    rt.body.theta = 0.0
    s = rt.world.surface_response
    s[:, :] = 0.0
    s[16, 16] = 1.0  # own cell
    sample = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    assert all(r["cell"] != [16, 16] for r in sample["neighbors"])
    assert sum(sample["fragments"].values()) == 0.0


def test_rotation_sweep_360_returns():
    rt = _runtime_with_nfe()
    rt.body.x = 16.5
    rt.body.y = 16.5
    s = rt.world.surface_response
    s[:, :] = 0.3
    s[16, 17] = 1.0
    frags = []
    for deg in (0, 45, 90, 135, 180, 270, 360):
        rt.body.theta = math.radians(deg)
        frags.append(sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception))
    assert frags[0]["fragments"] == frags[-1]["fragments"]
    # rear at 0° invisible; at 180° visible
    assert frags[0]["n_detectable"] >= 0
    west0 = next(r for r in frags[0]["neighbors"] if r["cell"] == [15, 16])
    west180 = next(r for r in frags[4]["neighbors"] if r["cell"] == [15, 16])
    assert west0["inside_fov"] is False
    assert west180["inside_fov"] is True


def test_wrap_angle():
    assert wrap_angle(math.pi + 0.1) == pytest.approx(-math.pi + 0.1, abs=1e-9)
