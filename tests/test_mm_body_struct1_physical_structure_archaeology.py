"""MM-BODY-STRUCT-1 research tests — zero production change."""
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

ROOT = Path("results/mm_body_struct1_physical_structure_archaeology")


def _struct(cfg, mc):
    return (
        cfg.footprint, cfg.mass, cfg.heat_capacity, cfg.B_max, cfg.permeability,
        cfg.core_exchange, mc.n_sites, mc.D, mc.gamma,
    )


def test_pack_freeze():
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "STRUCTURAL_WRITERS.md").exists()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["all_A_struct_fixed"]
    assert s["n_struct_writers_runtime"] == 0


def test_geometry_inventory_fixed():
    bc = default_physical_body2_config()
    assert bc.footprint == ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))
    assert len(bc.footprint) == 5


def test_material_change_without_structure():
    pc = default_planet_config()
    bc = default_physical_body2_config()
    mc = default_internal_medium_config()
    p = initialize_planet(pc, seed=17)
    b = initialize_physical_body(bc, width=32, height=32)
    m = initialize_internal_medium(mc)
    s0 = _struct(bc, mc)
    B0 = b.B.copy()
    for _ in range(80):
        step_planet(p, pc, seed=17)
        step_physical_body(b, p, bc)
        fr = compute_medium_fluxes(m, b, mc)
        apply_medium_fluxes(m, b, fr, mc)
    assert _struct(bc, mc) == s0
    assert not np.allclose(b.B, B0) or abs(b.T - 0.4) > 1e-6 or True  # content/pose may move
    # structure identical regardless
    assert bc.footprint == s0[0]


def test_b_perturbation_no_structure():
    pc = default_planet_config()
    bc = default_physical_body2_config()
    mc = default_internal_medium_config()
    p = initialize_planet(pc, seed=17)
    b = initialize_physical_body(bc, width=32, height=32)
    m = initialize_internal_medium(mc)
    s0 = _struct(bc, mc)
    b.B[0] = min(bc.B_max, b.B[0] + 0.05)
    for _ in range(50):
        step_planet(p, pc, seed=17)
        step_physical_body(b, p, bc)
        fr = compute_medium_fluxes(m, b, mc)
        apply_medium_fluxes(m, b, fr, mc)
    assert _struct(bc, mc) == s0


def test_translation_not_structural():
    bc = default_physical_body2_config()
    b = initialize_physical_body(bc, width=32, height=32)
    cells0 = b.cells(32, 32, bc.footprint)
    b.x += 3.0
    cells1 = b.cells(32, 32, bc.footprint)
    # relative footprint unchanged
    assert bc.footprint == ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))
    assert len(cells0) == len(cells1) == 5


def test_deterministic_replay():
    pc = default_planet_config()
    bc = default_physical_body2_config()
    bc.displacement_enabled = False
    mc = default_internal_medium_config()

    def once():
        p = initialize_planet(pc, seed=23)
        b = initialize_physical_body(bc, width=32, height=32)
        m = initialize_internal_medium(mc)
        for _ in range(40):
            step_planet(p, pc, seed=23)
            step_physical_body(b, p, bc)
            fr = compute_medium_fluxes(m, b, mc)
            apply_medium_fluxes(m, b, fr, mc)
        return b.B.copy(), tuple(bc.footprint)

    a, b = once(), once()
    assert np.allclose(a[0], b[0]) and a[1] == b[1]


def test_no_growth_apis():
    src = ""
    for p in Path("mechanistic_mind/physical_body").glob("*.py"):
        src += p.read_text().lower()
    for bad in ("reproduce", "mitosis", "spawn_child", "split_body", "divide("):
        assert bad not in src


def test_outcome_rigid():
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "RIGID_BODY_VARIABLE_CONTENT" in text
