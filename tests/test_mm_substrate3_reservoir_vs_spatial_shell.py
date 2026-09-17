"""MM-SUBSTRATE-3 — reservoir vs spatial shell contracts."""
from __future__ import annotations
from pathlib import Path
import json, hashlib
import numpy as np

ROOT = Path("results/mm_substrate3_reservoir_vs_spatial_shell")
from mechanistic_mind.internal_medium import default_internal_medium_config, EDGES


def test_pack_outcome():
    assert (ROOT / "FINAL_REPORT.md").is_file()
    assert (ROOT / "PREREGISTERED_QUESTIONS.md").is_file()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["outcome"] == "RESERVOIR_IN_SPATIAL_SHELL"
    assert s["mean_nat_diff"] < 1e-6
    assert s["flux_diff_matters"] is False


def test_freeze():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    for path, hx in s["freeze"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == hx
    assert default_internal_medium_config().D == 0.08
    assert EDGES == ((0, 1), (0, 2), (0, 3), (0, 4))


def test_exchange_kernel_identity():
    # Σ J_s = κ_s * (n B - Σ c)
    from mechanistic_mind.internal_medium import initialize_internal_medium, compute_medium_fluxes
    from mechanistic_mind.physical_body import default_physical_body2_config, initialize_physical_body
    cfg = default_internal_medium_config()
    m = initialize_internal_medium(cfg)
    m.c[:] = 0.2
    m.c[:, 0] = [0.1, 0.3, 0.25, 0.15, 0.2]
    b = initialize_physical_body(default_physical_body2_config(), width=32, height=32)
    b.B[:] = 0.4
    fr = compute_medium_fluxes(m, b, cfg)
    n = 5
    expect = cfg.kappa_s * (n * b.B - m.c.sum(axis=0))
    assert np.allclose(-fr.dB, expect)  # dB = -Σ J_s ⇒ -dB = Σ J
