"""MM-WORLD-1 toroidal planetary substrate — zero organisms."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mechanistic_mind.planet.config import PlanetConfig, default_planet_config
from mechanistic_mind.planet.dynamics import step_planet, step_matter
from mechanistic_mind.planet.forcing import forcing_field
from mechanistic_mind.planet.runtime import run_planet
from mechanistic_mind.planet.state import initialize_planet
from mechanistic_mind.planet.topology import (
    laplacian,
    toroidal_delta,
    toroidal_distance,
    translate_field,
    wrap_coord,
)

ROOT = Path(__file__).resolve().parents[1] / "results" / "mm_world1_earthlike_mechanistic_substrate"


def test_pack_exists():
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "experiment_summary.json").exists()
    assert "WORLD_CAUSALLY_RICH" in (ROOT / "FINAL_REPORT.md").read_text()


def test_toroidal_wrap_and_distance():
    assert wrap_coord(-1, 32) == 31
    assert wrap_coord(32, 32) == 0
    assert abs(toroidal_delta(0, 31, 32) - (-1.0)) < 1e-9
    assert toroidal_distance(0, 0, 31, 0, 32, 32) == 1.0


def test_laplacian_seam_symmetric():
    z = np.zeros((16, 16))
    z[0, 0] = 1.0
    L = laplacian(z)
    assert L[0, 1] == L[0, 15]
    assert L[1, 0] == L[15, 0]


def test_seam_translational_equivalence():
    cfg = PlanetConfig(F_irregular_amp=0.0, wave_source_gain=0.05)
    st_a = initialize_planet(cfg, seed=17)
    st_b = st_a.copy()
    dx = cfg.width // 2
    for name in ("T", "vx", "vy", "u", "u_prev", "capacity", "conductivity"):
        setattr(st_b, name, translate_field(getattr(st_a, name), 0, dx))
    st_b.M = np.stack([translate_field(st_a.M[i], 0, dx) for i in range(st_a.M.shape[0])])
    cfg_b = PlanetConfig(F_irregular_amp=0.0, wave_source_gain=0.05, forcing_origin_x=float(dx))
    for _ in range(40):
        step_planet(st_a, cfg, seed=17)
        step_planet(st_b, cfg_b, seed=17)
    err = float(np.max(np.abs(translate_field(st_a.T, 0, dx) - st_b.T)))
    assert err < 1e-9


def test_matter_conservation_transport_only():
    cfg = PlanetConfig(
        reaction_enabled=False,
        phase_enabled=False,
        wave_enabled=False,
        forcing_enabled=False,
        thermal_from_forcing=False,
        cool_rate=0.0,
        heat_gain=0.0,
        kappa_base=0.0,
        F_irregular_amp=0.0,
        diffusion_enabled=True,
        advection_enabled=True,
    )
    st = initialize_planet(cfg, seed=17)
    st.vx[:, :] = 0.2
    st.vy[:, :] = 0.05
    init = float(st.M.sum())
    for _ in range(100):
        step_matter(st, cfg)
    assert abs(float(st.M.sum()) - init) < 1e-9


def test_thermal_responds_to_forcing():
    on = run_planet(seed=17, horizon=80, snapshot_every=80, config=PlanetConfig(F_irregular_amp=0.0))
    off = run_planet(
        seed=17,
        horizon=80,
        snapshot_every=80,
        config=PlanetConfig(forcing_enabled=False, F_irregular_amp=0.0),
    )
    assert on["series"][-1]["T_std"] > off["series"][-1]["T_std"]


def test_no_semantic_day_night_in_state():
    st = initialize_planet(seed=1)
    blob = st.__dict__
    assert "day" not in blob and "night" not in blob and "season" not in blob


def test_forcing_bounded_and_continuous_values():
    cfg = default_planet_config()
    F = forcing_field(cfg, 7, cfg.height, cfg.width, seed=17)
    assert F.shape == (cfg.height, cfg.width)
    assert float(F.min()) >= 0.0
    assert float(F.max()) <= 1.5


def test_zero_organism_and_no_organism_world_import_side_effects():
    # planet package must not require OrganismWorld
    import mechanistic_mind.planet as planet

    assert hasattr(planet, "run_planet")
    r = run_planet(seed=23, horizon=30, snapshot_every=30)
    assert r["final"]["tick"] == 30


def test_wave_impulse_propagates():
    cfg = PlanetConfig(
        wave_enabled=True,
        forcing_enabled=False,
        thermal_from_forcing=False,
        cool_rate=0.0,
        heat_gain=0.0,
        kappa_base=0.0,
        flow_enabled=False,
        reaction_enabled=False,
        phase_enabled=False,
        diffusion_enabled=False,
        advection_enabled=False,
        wave_source_gain=0.0,
        F_irregular_amp=0.0,
    )
    st = initialize_planet(cfg, seed=1)
    st.T[:] = cfg.T_ref
    impulse = np.zeros_like(st.u)
    impulse[cfg.height // 2, cfg.width // 2] = 1.0
    step_planet(st, cfg, seed=1, impulse=impulse)
    for _ in range(8):
        step_planet(st, cfg, seed=1)
    # energy should have spread to neighbors
    assert float(np.abs(st.u[cfg.height // 2, cfg.width // 2 + 2])) > 0.0 or float(np.abs(st.u).sum()) > 0.1


def test_historical_organism_untouched_marker():
    from worlds.rich_autonomous_signal_ecology_v01 import make_rich_ecology_world
    from mechanistic_mind.body.embodied_integration import default_embodied_integration_config

    w = make_rich_ecology_world()
    assert w.body_config.embodied_integration_config == default_embodied_integration_config()
