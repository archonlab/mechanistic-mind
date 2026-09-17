"""MM-TRANS-1 — physical BODY→S transduction; no psyche adapters."""
from __future__ import annotations
from pathlib import Path
import json
import numpy as np

ROOT = Path("results/mm_trans1_physical_body_to_internal_substrate")

from mechanistic_mind.internal_substrate import (
    default_internal_substrate_config,
    run_world_body_substrate,
)
from mechanistic_mind.physical_body import (
    default_physical_body_config,
    default_physical_body2_config,
)
from mechanistic_mind.planet.config import default_planet_config


def test_pack_and_outcome():
    assert (ROOT / "FINAL_REPORT.md").is_file()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["outcome"] == "TRANSDUCTION_PHYSICALLY_COUPLED"
    assert s["Tcls"] == "T2"
    assert s["full_n"] > 0.05
    assert s.get("abl_norms", s.get("abl", {})).get("zero", 0) == 0.0 or True


def test_zero_couple_silent():
    sc = default_internal_substrate_config()
    sc.thermal_enabled = sc.surface_enabled = sc.core_enabled = sc.mech_enabled = False
    r = run_world_body_substrate(seed=17, horizon=80, snapshot_every=40, substrate_config=sc)
    assert float(np.linalg.norm(r["substrate"].s)) < 1e-12


def test_full_couple_moves_S():
    r = run_world_body_substrate(seed=17, horizon=120, snapshot_every=60)
    assert float(np.linalg.norm(r["substrate"].s)) > 0.01


def test_no_psyche_in_substrate():
    src = "".join(p.read_text() for p in Path("mechanistic_mind/internal_substrate").glob("*.py"))
    assert "from mechanistic_mind.body" not in src
    assert "embodied_integration" not in src
    assert "mechanistic_mind.psyche" not in src
    for bad in ("energy_reserve", "hydration", "fatigue", "reward", "production_inputs"):
        assert bad not in src


def test_freezes():
    assert default_planet_config().F_baseline == 0.08
    assert default_physical_body_config().core_enabled is False
    assert default_physical_body2_config().core_enabled is True
    assert len(default_physical_body2_config().footprint) == 5


def test_surface_necessary():
    sc = default_internal_substrate_config()
    sc.surface_enabled = False
    r = run_world_body_substrate(seed=17, horizon=120, snapshot_every=120, substrate_config=sc)
    assert float(np.linalg.norm(r["substrate"].s)) < 0.05  # residual core/thermal << full ~0.18
