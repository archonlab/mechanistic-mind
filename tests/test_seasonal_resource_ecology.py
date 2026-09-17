"""Spatiotemporal climate ecology: default OFF, world physics only, no cognition leak."""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from mechanistic_mind.planet.climate_ecology import (
    ClimateEcologyConfig,
    experimental_climate_planet_config,
    field_phase_row,
    latitude_axis,
    observer_climate_ground_truth,
)
from mechanistic_mind.planet.config import PlanetConfig
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.planet.runtime import restore_planet_state, serialize_planet_state
from mechanistic_mind.planet.state import initialize_planet
from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload


def _spin(cfg: PlanetConfig, *, seed: int = 17, ticks: int = 40):
    st = initialize_planet(cfg, seed=seed)
    for _ in range(ticks):
        step_planet(st, cfg, seed=seed)
    return st


def test_default_climate_ecology_off():
    cfg = PlanetConfig()
    assert cfg.climate_ecology.enabled is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.planet.climate_ecology.enabled is False
    snap = rt.mechanisms()
    states = {m["id"]: m["enabled"] for m in snap["mechanisms"]}
    assert states["spatiotemporal_climate_ecology"] is False


def test_default_planet_unchanged_when_climate_off():
    a = PlanetConfig(F_irregular_amp=0.0)
    b = PlanetConfig(F_irregular_amp=0.0, climate_ecology=ClimateEcologyConfig(enabled=False))
    sa, sb = initialize_planet(a, seed=17), initialize_planet(b, seed=17)
    for _ in range(25):
        step_planet(sa, a, seed=17)
        step_planet(sb, b, seed=17)
    assert float(np.max(np.abs(sa.T - sb.T))) < 1e-12


def test_latitudinal_temperature_gradient():
    cfg = experimental_climate_planet_config()
    st = initialize_planet(cfg, seed=17)
    north = float(st.T[:8].mean())
    south = float(st.T[24:].mean())
    assert north < south
    phi = latitude_axis(st.T.shape[0])
    assert phi[0] < 0
    assert phi[-1] > 0


def test_seasonal_temperature_and_resource_shift():
    cfg = experimental_climate_planet_config()
    st = initialize_planet(cfg, seed=17)
    period = cfg.climate_ecology.season_period
    rows = []
    for t in range(period + 1):
        if t % (period // 4) == 0:
            rows.append(field_phase_row(cfg.climate_ecology, st.tick, 17, st.T, st.R_A, st.R_B))
        step_planet(st, cfg, seed=17)
    t_max_ys = [r["T_max_y"] for r in rows]
    ra_ys = [r["R_A_max_y"] for r in rows]
    assert max(t_max_ys) - min(t_max_ys) >= 4
    assert max(ra_ys) - min(ra_ys) >= 3
    assert max(r["R_A_sum"] for r in rows) > 0
    assert max(r["R_B_sum"] for r in rows) > 0


def test_finite_stock_capacity_and_depletion():
    cfg = experimental_climate_planet_config()
    st = _spin(cfg, ticks=60)
    cap_a = cfg.climate_ecology.RA_capacity
    cap_b = cfg.climate_ecology.RB_capacity
    assert float(st.R_A.max()) <= cap_a + 1e-9
    assert float(st.R_B.max()) <= cap_b + 1e-9
    iy, ix = int(np.unravel_index(int(np.argmax(st.R_A)), st.R_A.shape)[0]), int(
        np.unravel_index(int(np.argmax(st.R_A)), st.R_A.shape)[1]
    )
    before = float(st.R_A[iy, ix])
    st.R_A[iy, ix] = 0.0
    step_planet(st, cfg, seed=17)
    after = float(st.R_A[iy, ix])
    assert after < before
    assert after < cap_a


def test_seed_reproducible_ecology_without_cognition():
    cfg = experimental_climate_planet_config()
    a = _spin(cfg, seed=41, ticks=90)
    b = _spin(cfg, seed=41, ticks=90)
    assert float(np.max(np.abs(a.T - b.T))) < 1e-12
    assert float(np.max(np.abs(a.R_A - b.R_A))) < 1e-12
    assert float(np.max(np.abs(a.R_B - b.R_B))) < 1e-12
    c = _spin(cfg, seed=59, ticks=90)
    assert float(np.max(np.abs(a.T - c.T))) > 1e-6


def test_snapshot_restore_preserves_climate_config():
    cfg = experimental_climate_planet_config()
    st = _spin(cfg, ticks=12)
    payload = serialize_planet_state(st, cfg)
    st2, cfg2 = restore_planet_state(payload)
    assert cfg2.climate_ecology.enabled is True
    assert cfg2.climate_ecology.season_period == cfg.climate_ecology.season_period
    assert float(np.max(np.abs(st2.T - st.T))) < 1e-12


def test_agent_observation_has_no_hidden_climate_tokens():
    cfg = PhysicalSystemConfig(planet=experimental_climate_planet_config())
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    for _ in range(8):
        rt.step()
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    blob = repr(obs)
    for tok in FORBIDDEN_TOKENS:
        assert tok not in blob
    for key in obs:
        assert "season" not in key.lower()
        assert "latitude" not in key.lower()
        assert "phase" not in key.lower()
        assert "migrat" not in key.lower()


def test_observer_ground_truth_is_not_cognition():
    cfg = experimental_climate_planet_config()
    st = initialize_planet(cfg, seed=17)
    gt = observer_climate_ground_truth(cfg.climate_ecology, 0, seed=17, T=st.T, R_A=st.R_A, R_B=st.R_B)
    assert gt["enabled"] is True
    assert "environmental_cycle_phase" in gt
    rt = PhysicalSystemRuntime(seed=17, config=PhysicalSystemConfig(planet=cfg))
    rt.step()
    assert "environmental_cycle_phase" not in (rt.last_agent_observation or {})


def test_mechanism_toggle_does_not_change_cognition_defaults():
    rt = PhysicalSystemRuntime(seed=17)
    before = deepcopy(rt.config.cognition.to_dict())
    rt.set_mechanism("spatiotemporal_climate_ecology", True)
    assert rt.config.planet.climate_ecology.enabled is True
    assert rt.config.cognition.to_dict() == before
    rt.set_mechanism("spatiotemporal_climate_ecology", False)
    assert rt.config.planet.climate_ecology.enabled is False
