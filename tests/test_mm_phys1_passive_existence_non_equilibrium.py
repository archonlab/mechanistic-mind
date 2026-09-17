"""MM-PHYS-1 research tests — zero production change."""
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

ROOT = Path("results/mm_phys1_passive_existence_non_equilibrium")


def test_pack_and_freeze():
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "FREEZE_AUDIT.md").exists()
    assert (ROOT / "PASSIVE_PROCESS_INVENTORY.md").exists()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["freeze_ok"]


def test_passive_world_and_body_evolve():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    a = s["A"]["17"]
    assert a["world_changed"]
    assert a["body_changed"]
    assert a["inactive_ticks"] == 0


def test_gross_vs_net():
    a = json.loads((ROOT / "experiment_summary.json").read_text())["A"]["17"]
    assert a["gross_matter"] > a["net_B_change"] > 0


def test_static_differs_from_baseline():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["ext_maint"]["17"]["dB_A_vs_B"] > 1e-3


def test_hidden_state_replay():
    h3 = json.loads((ROOT / "experiment_summary.json").read_text())["H3"]
    assert h3["dB"] > 1e-3


def test_deterministic_replay_short():
    pc = default_planet_config()
    bc = default_physical_body2_config()
    bc.displacement_enabled = False
    mc = default_internal_medium_config()

    def once():
        p = initialize_planet(pc, seed=17)
        b = initialize_physical_body(bc, width=32, height=32)
        m = initialize_internal_medium(mc)
        for _ in range(40):
            step_planet(p, pc, seed=17)
            step_physical_body(b, p, bc)
            fr = compute_medium_fluxes(m, b, mc)
            apply_medium_fluxes(m, b, fr, mc)
        return b.B.copy(), b.B_core.copy(), b.T, m.c.copy()

    a, b = once(), once()
    assert np.allclose(a[0], b[0]) and np.allclose(a[1], b[1]) and a[2] == b[2]
    assert np.allclose(a[3], b[3])


def test_no_psyche_imports_body():
    src = "".join(p.read_text() for p in Path("mechanistic_mind/physical_body").glob("*.py"))
    assert "from mechanistic_mind.body" not in src
    for bad in ("energy_reserve", "hydration", "fatigue", "reward", "sensorimotor"):
        assert bad not in src


def test_semantic_firewall_summary():
    text = (ROOT / "FINAL_REPORT.md").read_text().lower()
    # claim answers must say no for life/metabolism/homeostasis as claims
    assert "metabolism claim? NO" in (ROOT / "FINAL_REPORT.md").read_text() or "81. metabolism claim? NO" in (ROOT / "FINAL_REPORT.md").read_text()
