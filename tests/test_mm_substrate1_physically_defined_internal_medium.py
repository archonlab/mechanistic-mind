"""MM-SUBSTRATE-1 — physically defined internal medium contracts."""
from __future__ import annotations
from pathlib import Path
import json, hashlib
import numpy as np

ROOT = Path("results/mm_substrate1_physically_defined_internal_medium")

from mechanistic_mind.internal_medium import (
    default_internal_medium_config,
    initialize_internal_medium,
    step_internal_medium,
    compute_medium_fluxes,
    run_world_body_medium,
    EDGES,
)
from mechanistic_mind.physical_body import (
    default_physical_body2_config,
    initialize_physical_body,
)
from mechanistic_mind.planet.config import default_planet_config


def test_prereg_and_freeze_exist():
    for n in ("PREREGISTERED_DESIGN.md", "PHYSICAL_ACCEPTANCE_FREEZE.md", "FINAL_REPORT.md", "experiment_summary.json"):
        assert (ROOT / n).is_file()


def test_outcome_classes():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["M"] in ("M6", "M7")
    assert s["phys"]["gates"]["A"] == "PASS"
    assert s["old_S_zero"] == 0.0


def test_host_defaults_unchanged():
    assert default_planet_config().F_baseline == 0.08
    assert default_physical_body2_config().core_exchange == 0.015
    assert default_physical_body2_config().footprint == ((0, 0), (-1, 0), (1, 0), (0, -1), (0, 1))


def test_freeze_hashes():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    for path, hx in s["phys"]["freeze"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == hx


def test_accounting_and_reciprocity():
    cfg = default_internal_medium_config()
    cfg.diffusion_enabled = False
    cfg.dissipation_enabled = False
    m = initialize_internal_medium(cfg)
    m.c[:] = 0.1
    b = initialize_physical_body(default_physical_body2_config(), width=32, height=32)
    b.B[:] = 0.5
    b.B_core[:] = 0.4
    tot0 = float(m.c.sum() + b.B.sum() + b.B_core.sum())
    for _ in range(30):
        fr = step_internal_medium(m, b, cfg)
        assert abs(fr.material_residual) < 1e-12
    assert abs(float(m.c.sum() + b.B.sum() + b.B_core.sum()) - tot0) < 1e-9
    fr = compute_medium_fluxes(m, b, cfg)
    assert np.allclose(fr.dB, -fr.J_s.sum(axis=0))


def test_locality_no_opposite_edge():
    assert (1, 2) not in EDGES and (2, 1) not in EDGES
    cfg = default_internal_medium_config()
    cfg.coupling_enabled = False
    cfg.dissipation_enabled = False
    m = initialize_internal_medium(cfg)
    m.c[:] = 0.15
    m.c[1, 0] = 1.0
    b = initialize_physical_body(default_physical_body2_config(), width=32, height=32)
    before = float(m.c[2, 0])
    step_internal_medium(m, b, cfg)
    assert abs(float(m.c[2, 0]) - before) < 1e-15


def test_zero_coupling_body_baseline():
    cfg = default_internal_medium_config()
    cfg.coupling_enabled = False
    rz = run_world_body_medium(seed=17, horizon=40, snapshot_every=40, medium_config=cfg)
    rn = run_world_body_medium(seed=17, horizon=40, snapshot_every=40, with_medium=False)
    assert np.allclose(rz["body"].B, rn["body"].B)
    assert np.allclose(rz["body"].B_core, rn["body"].B_core)


def test_no_world_in_flux():
    src = Path("mechanistic_mind/internal_medium/flux.py").read_text()
    assert "Planet" not in src
    assert "step_planet" not in src
    for bad in ("receptor", "reward", "psyche", "memory_signal", "production_inputs"):
        assert bad not in src


def test_old_s_package_present():
    assert Path("mechanistic_mind/internal_substrate/dynamics.py").is_file()
