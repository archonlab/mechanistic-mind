"""MM-CAPABILITY-1 research tests — zero production change."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np

from mechanistic_mind.physical_body import (
    default_physical_body2_config, initialize_physical_body, step_physical_body,
)
from mechanistic_mind.planet.config import default_planet_config
from mechanistic_mind.planet.state import initialize_planet
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.internal_medium import (
    default_internal_medium_config, initialize_internal_medium,
    compute_medium_fluxes, apply_medium_fluxes,
)

ROOT = Path("results/mm_capability1_physical_substrate_frontier")


def test_pack_freeze():
    assert (ROOT / "FINAL_REPORT.md").exists()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s.get("freeze_ok")


def test_spatial_feedback_reported():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["SFB"]["17"]["spatial_feedback"]


def test_hidden_affects_future():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["HID"]["affects_B"]
    assert s["HID"]["dBpeak"] > 1e-3


def test_low_effective_dim():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["EDIM"]["participation_ratio"] < 3.0


def test_deterministic_replay():
    pc = default_planet_config()
    bc = default_physical_body2_config()
    bc.displacement_enabled = False
    mc = default_internal_medium_config()

    def once():
        p = initialize_planet(pc, seed=17)
        b = initialize_physical_body(bc, width=32, height=32)
        m = initialize_internal_medium(mc)
        for _ in range(30):
            step_planet(p, pc, seed=17)
            step_physical_body(b, p, bc)
            fr = compute_medium_fluxes(m, b, mc)
            apply_medium_fluxes(m, b, fr, mc)
        return b.B.copy(), m.c.copy()

    a, b = once(), once()
    assert np.allclose(a[0], b[0]) and np.allclose(a[1], b[1])


def test_no_psyche_imports():
    src = "".join(p.read_text() for p in Path("mechanistic_mind/physical_body").glob("*.py"))
    assert "from mechanistic_mind.body" not in src


def test_outcome_sufficient():
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "CURRENT_SUBSTRATE_SUFFICIENT" in text
    assert "STOP" in text
