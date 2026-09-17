"""MM-SUBSTRATE-2 — frozen medium characterization contracts."""
from __future__ import annotations
from pathlib import Path
import json, hashlib
import numpy as np

ROOT = Path("results/mm_substrate2_spatial_modes_hidden_state")

from mechanistic_mind.internal_medium.config import EDGES, default_internal_medium_config


def test_pack_and_prereg():
    for n in ("CAUSAL_TEST_PREREGISTRATION.md", "FINAL_REPORT.md", "experiment_summary.json", "topology_spectrum.json"):
        assert (ROOT / n).is_file()


def test_outcome_h5_common_mode():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["MH"] == "MEDIUM_H5"
    assert s["P"] == "P4"
    assert s["natural_occ"]["λ0"] > 0.99
    assert s["mcaus"]["common"] > 0
    assert s["mcaus"]["diff"] == 0.0


def test_production_freeze():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    for path, hx in s["freeze"].items():
        assert hashlib.sha256(Path(path).read_bytes()).hexdigest() == hx
    assert default_internal_medium_config().D == 0.08
    assert default_internal_medium_config().gamma == 0.01


def test_laplacian_spectrum():
    s = json.loads((ROOT / "topology_spectrum.json").read_text())
    ev = np.array(s["evals"], float)
    assert abs(ev[0]) < 1e-10
    assert abs(ev[-1] - 5.0) < 1e-8
    assert np.allclose(sorted(ev), [0, 1, 1, 1, 5], atol=1e-8)


def test_causal_ablation_zero():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    for v in s["causal"].values():
        assert v["dBODY_abl"] == 0.0
        assert v["dBODY"] > 0.0
        assert v["dJ0"] > 0.0


def test_species_independent_in_equations():
    src = Path("mechanistic_mind/internal_medium/flux.py").read_text()
    # per-species loops only; no cross-species terms
    assert "for k in range(nk)" in src
    assert "c[i, k-1]" not in src


def test_no_topology_change():
    assert EDGES == ((0, 1), (0, 2), (0, 3), (0, 4))
