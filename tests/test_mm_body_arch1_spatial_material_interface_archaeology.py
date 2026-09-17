"""MM-BODY-ARCH-1 research tests — zero production change."""
from __future__ import annotations
import hashlib
from pathlib import Path
import numpy as np

from mechanistic_mind.physical_body import (
    default_physical_body2_config,
    initialize_physical_body,
    step_physical_body,
)
from mechanistic_mind.planet.config import default_planet_config
from mechanistic_mind.planet.state import initialize_planet
from mechanistic_mind.planet.dynamics import step_planet

ROOT = Path("results/mm_body_arch1_spatial_material_interface_archaeology")


def test_production_freeze():
    assert (ROOT / "FREEZE_AUDIT.md").exists()
    assert (ROOT / "PRODUCTION_FREEZE_AUDIT.md").exists()
    src = Path("mechanistic_mind/physical_body/dynamics.py").read_text()
    assert "step_physical_body" in src


def test_source_equation_mean_before_flux():
    src = Path("mechanistic_mind/physical_body/dynamics.py").read_text()
    assert "average local WORLD fields over footprint" in src
    assert "M_w /= ncell" in src
    assert "M_w[i]" in src


def test_body_state_inventory_lumped():
    b = initialize_physical_body(default_physical_body2_config(), width=32, height=32)
    assert b.B.shape == (3,)
    assert b.B_core.shape == (3,)


def test_contact_footprint_mapping():
    bc = default_physical_body2_config()
    b = initialize_physical_body(bc, width=32, height=32)
    b.x, b.y = 16.5, 16.5
    cells = b.cells(32, 32, bc.footprint)
    assert len(cells) == 5


def test_same_mean_different_geometry_identical_B():
    bc = default_physical_body2_config()
    bc.thermal_enabled = False
    bc.mechanical_enabled = False
    bc.reaction_enabled = False
    bc.core_enabled = False
    bc.displacement_enabled = False

    def run(Mcol0):
        p = initialize_planet(default_planet_config(), seed=0)
        p.M[:] = 0.2
        b = initialize_physical_body(bc, width=32, height=32, B0=(0.25, 0.20, 0.10))
        b.x = 16.5
        b.y = 16.5
        cells = b.cells(32, 32, bc.footprint)
        for j, (iy, ix) in enumerate(cells):
            p.M[:, iy, ix] = 0.25
            p.M[0, iy, ix] = Mcol0[j]
        step_physical_body(b, p, bc)
        return b.B.copy()

    A = [0.8, 0.3, 0.3, 0.3, 0.3]
    B = [0.4, 0.4, 0.4, 0.4, 0.4]
    assert abs(sum(A) / 5 - sum(B) / 5) < 1e-12
    assert np.allclose(run(A), run(B))


def test_footprint_scaling_independent_of_ncell():
    def run(fp):
        bc = default_physical_body2_config()
        bc.footprint = fp
        bc.thermal_enabled = False
        bc.mechanical_enabled = False
        bc.reaction_enabled = False
        bc.core_enabled = False
        bc.displacement_enabled = False
        p = initialize_planet(default_planet_config(), seed=1)
        b = initialize_physical_body(bc, width=32, height=32, B0=(0.1, 0.1, 0.1))
        b.x = 16.5
        b.y = 16.5
        for _ in range(20):
            p.M[:] = 0.6
            step_physical_body(b, p, bc)
        return b.B.copy()

    assert np.allclose(
        run(((0, 0),)),
        run(((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))),
    )


def test_deterministic_replay():
    bc = default_physical_body2_config()
    bc.displacement_enabled = False

    def once():
        p = initialize_planet(default_planet_config(), seed=17)
        b = initialize_physical_body(bc, width=32, height=32)
        b.x = 16.5
        b.y = 16.5
        pc = default_planet_config()
        for _ in range(30):
            step_planet(p, pc, seed=17)
            step_physical_body(b, p, bc)
        return b.B.copy(), b.B_core.copy(), b.T

    a, b = once(), once()
    assert np.allclose(a[0], b[0]) and np.allclose(a[1], b[1]) and a[2] == b[2]


def test_no_psyche_imports():
    src = ""
    for p in Path("mechanistic_mind/physical_body").glob("*.py"):
        src += p.read_text()
    assert "from mechanistic_mind.body" not in src
    assert "embodied_integration" not in src
    for bad in ("energy_reserve", "hydration", "fatigue", "reward", "sensorimotor"):
        assert bad not in src


def test_first_spatial_identity_loss_documented():
    assert (ROOT / "FIRST_SPATIAL_IDENTITY_LOSS.md").read_text().count("mean") >= 1


def test_result_pack_exists():
    for name in (
        "FINAL_REPORT.md",
        "ARCHITECTURAL_VERDICT.md",
        "FIRST_SPATIAL_IDENTITY_LOSS.md",
        "SAME_MEAN_DIFFERENT_GEOMETRY.md",
        "BODY_STATE_PROVENANCE.md",
        "AGGREGATION_BEFORE_AFTER_FLUX.md",
        "CROSS_PHYSICS_INTERFACE_COMPARISON.md",
        "NEXT_FRONTIER.md",
    ):
        assert (ROOT / name).exists()
