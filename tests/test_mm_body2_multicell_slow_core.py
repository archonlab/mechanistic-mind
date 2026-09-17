"""MM-BODY-2 tests — multi-cell + slow core; BODY-1 defaults preserved."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np
import pytest

ROOT = Path("results/mm_body2_multicell_slow_core")

from mechanistic_mind.physical_body import (
    default_physical_body_config,
    default_physical_body2_config,
    initialize_physical_body,
    step_physical_body,
    run_world_with_body,
)
from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.planet.config import PlanetConfig
from mechanistic_mind.planet.state import initialize_planet
from mechanistic_mind.planet.dynamics import step_planet


def test_pack_exists():
    for n in ("FINAL_REPORT.md", "NEXT_FRONTIER.md", "experiment_summary.json", "BODY1_VS_BODY2.md"):
        assert (ROOT / n).is_file()


def test_outcome_h4():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["outcome"] == "BODY_WITH_HISTORY_DEPENDENT_FUTURE"
    assert s["H"] == "H4"
    assert s["body2_matched_dB"] > 1e-2 or s["body2_hidden_dB"] > 1e-2
    assert s["body2_matched_dB"] > s["body1_matched_dB"] * 100
    assert s["body2_hidden_dB"] > 1e-2


def test_body1_defaults_unchanged():
    c = default_physical_body_config()
    assert c.footprint == ((0, 0),)
    assert c.core_enabled is False
    assert c.permeability == (0.12, 0.08, 0.04)
    assert c.heat_capacity == 2.5


def test_body2_has_footprint_and_core():
    c = default_physical_body2_config()
    assert len(c.footprint) == 5
    assert c.core_enabled is True
    assert c.core_exchange > 0


def test_no_psyche_imports():
    src = ""
    for p in Path("mechanistic_mind/physical_body").glob("*.py"):
        src += p.read_text()
    assert "from mechanistic_mind.body" not in src
    assert "embodied_integration" not in src
    for bad in ("energy_reserve", "hydration", "fatigue", "reward", "sensorimotor"):
        assert bad not in src


def test_core_persists_under_matched_world():
    from copy import deepcopy
    cfg = default_physical_body2_config()
    cfg.displacement_enabled = False
    pc = PlanetConfig(F_irregular_amp=0.0)
    p1 = initialize_planet(pc, seed=3)
    p2 = initialize_planet(pc, seed=3)
    b1 = initialize_physical_body(cfg, B0=(0.3, 0.2, 0.1), B_core0=(0.5, 0.4, 0.1), T0=0.5)
    b2 = initialize_physical_body(cfg, B0=(0.3, 0.2, 0.1), B_core0=(0.05, 0.05, 0.6), T0=0.5)
    b1.x = b2.x = 12.5
    b1.y = b2.y = 12.5
    for _ in range(150):
        step_planet(p1, pc, seed=3)
        step_planet(p2, pc, seed=3)
        p2.T[:] = p1.T
        p2.M[:] = p1.M
        step_physical_body(b1, p1, cfg)
        step_physical_body(b2, p2, cfg)
    d = float(np.linalg.norm(b1.B_core - b2.B_core))
    assert d > 0.05


def test_world1_planet_defaults_frozen():
    # structural sanity: default planet numbers from WORLD-1
    from mechanistic_mind.planet.config import default_planet_config
    p = default_planet_config()
    assert p.F_baseline == 0.08
    assert p.flow_gain == 0.55


def test_body1_still_runs():
    r = run_world_with_body(seed=17, horizon=40, snapshot_every=20)
    assert r["body"] is not None
    assert len(r["body"].B) == 3
