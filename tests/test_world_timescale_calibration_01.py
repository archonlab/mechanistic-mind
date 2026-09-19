"""WORLD_TIMESCALE_CALIBRATION_01 regressions."""
from __future__ import annotations

import math

import numpy as np

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_BASELINE,
    ECOLOGY_CALIBRATED_TEMPORAL,
    ECOLOGY_STRUCTURED_WORLD,
    make_ecology_config,
)
from mechanistic_mind.physical_system.observation import (
    accessible_observation,
    audit_cognition_payload,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.planet.climate_ecology import season_phase_state
from mechanistic_mind.research.world_timescale import (
    run_wait_trace,
    structured_world_cfg,
    trajectory_metrics,
    wrap_delta,
)


def test_unique_tick_path_and_unwrapped_metrics():
    # Synthetic WRAP trajectory: step east across boundary once.
    xs = [30.0, 31.0, 0.5, 1.5]
    ys = [10.0, 10.0, 10.0, 10.0]
    m = trajectory_metrics(xs, ys, width=32, height=32)
    assert m["path_length"] > 3.0  # includes wrap step ~1.5
    assert m["unwrapped_dx"] > 3.0
    assert abs(m["unwrapped_dy"]) < 1e-9
    assert m["n_samples"] == 4


def test_wrap_delta_shortest():
    assert abs(wrap_delta(31.0, 0.5, 32) - 1.5) < 1e-9
    assert abs(wrap_delta(0.5, 31.0, 32) + 1.5) < 1e-9


def test_climate_period_determinism_and_continuous_phase():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    assert cfg.planet.climate_ecology.season_period == 800
    assert cfg.planet.F_fast_period == 320
    assert abs(float(cfg.planet.climate_ecology.subsolar_bias) - 0.35) < 1e-9
    assert int(cfg.planet.climate_ecology.local_var_period) == 80
    phases = [season_phase_state(cfg.planet.climate_ecology, t, 17)["phase"] for t in range(0, 40)]
    # Continuous (no large discrete jumps except wrap 1→0)
    jumps = [abs(phases[i + 1] - phases[i]) for i in range(len(phases) - 1)]
    assert max(jumps) < 0.05 or any(j > 0.9 for j in jumps)  # allow wrap
    rt1 = PhysicalSystemRuntime(seed=17, config=cfg)
    rt2 = PhysicalSystemRuntime(seed=17, config=make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0))
    for _ in range(30):
        rt1.step_forced_action("WAIT")
        rt2.step_forced_action("WAIT")
    assert abs(float(rt1.world.T.mean()) - float(rt2.world.T.mean())) < 1e-9
    assert rt1.world.terrain_meta["checksum"] == rt2.world.terrain_meta["checksum"]
    assert rt1.world.ambient_meta["checksum"] == rt2.world.ambient_meta["checksum"]


def test_baseline_unchanged_season_period():
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    assert cfg.planet.climate_ecology.season_period == 80


def test_terrain_ambient_static_under_calibrated_temporal():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    rt = PhysicalSystemRuntime(seed=29, config=cfg)
    cs_t0 = rt.world.terrain_meta["checksum"]
    cs_a0 = rt.world.ambient_meta["checksum"]
    for _ in range(100):
        rt.step_forced_action("WAIT")
    assert rt.world.terrain_meta["checksum"] == cs_t0
    assert rt.world.ambient_meta["checksum"] == cs_a0


def test_no_temporal_gt_leak_to_cognition():
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=3, config=cfg)
    rt.step_forced_action("WAIT")
    obs = accessible_observation(
        world=rt.world,
        body=rt.body,
        internal=rt.internal,
        planet_config=rt.config.planet,
        body_config=rt.config.body,
    )
    hits = audit_cognition_payload(obs)
    assert hits == []
    assert "environmental_cycle_phase" not in repr(obs)
    assert "temporal_panel" not in repr(obs)


def test_wait_force_decomposition_ordering():
    """Thermal flow dominates passive WAIT path vs terrain-alone (seed 17)."""
    a = run_wait_trace(
        structured_world_cfg(terrain=False, ambient=False, thermal_flow=False),
        seed=17, ticks=200, record_forces=True,
    )
    b = run_wait_trace(
        structured_world_cfg(terrain=True, ambient=False, thermal_flow=False),
        seed=17, ticks=200, record_forces=True,
    )
    d = run_wait_trace(
        structured_world_cfg(terrain=False, ambient=False, thermal_flow=True),
        seed=17, ticks=200, record_forces=True,
    )
    assert a["trajectory"]["path_length"] < 1e-6
    assert d["trajectory"]["path_length"] > b["trajectory"]["path_length"]


def test_history_window_stable_under_calibrated_world():
    """G3: lag-80 local T correlation >= 1/e after belt-bias calibration."""
    from mechanistic_mind.planet.dynamics import step_planet

    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    T = []
    for _ in range(2400):
        step_planet(rt.world, rt.config.planet, seed=17)
        T.append(float(rt.world.T[16, 16]))
    x = np.asarray(T, dtype=np.float64)
    x = x - x.mean()
    var = float(np.dot(x, x))
    lag = 80
    corr = float(np.dot(x[:-lag], x[lag:])) / var
    assert corr >= (1.0 / math.e), corr


def test_structured_world_still_period_80():
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    assert cfg.planet.climate_ecology.season_period == 80
    assert abs(float(cfg.planet.climate_ecology.subsolar_bias)) < 1e-12


def test_ui_exposes_calibrated_temporal_button():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "web/psy-observer/src/App.tsx").read_text(encoding="utf-8")
    assert "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL" in text
    assert "Calibrated World" in text
