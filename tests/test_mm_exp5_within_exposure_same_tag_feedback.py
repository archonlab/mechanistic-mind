"""MM-EXP-5 research tests — zero production change."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("results/mm_exp5_within_exposure_same_tag_feedback")


def test_pack():
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "PREREGISTRATION.md").exists()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["freeze_ok"]


def test_natural_rebuild_spaced():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    n = s["RESULTS"]["spaced"]["23"]["conditions"]["NATURAL"]
    assert n["rebuild"] > 0.01
    assert n["Om0"] > 0.015


def test_same_tag_no_rebuild():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    for key in ("SAME_MAT0", "SAME_MAT1"):
        c = s["RESULTS"]["spaced"]["23"]["conditions"][key]
        assert c["Mw_equal_all"]
        assert c["rebuild"] < 0
        assert c["grows_ticks"] == 0
        assert c["pred_err_max"] < 1e-12


def test_outcome():
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "WITHIN_EXPOSURE_REBUILD_REQUIRES_TAG_ASYMMETRY" in text
    assert "STOP" in text
