"""MM-EXP-2 research tests — zero production change."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("results/mm_exp2_physical_order_future_state")


def test_pack_freeze_det():
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "PREREGISTRATION.md").exists()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["freeze_ok"]
    assert s["DET"]["dup"] == 0.0


def test_dose_ok_all():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    for gap in s["RESULTS"]:
        for pname in s["RESULTS"][gap]:
            for seed, r in s["RESULTS"][gap][pname].items():
                assert r["dose_ok"]


def test_order_above_floor_same_mat():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    for seed, r in s["RESULTS"]["contig"]["SAME_MAT"].items():
        assert r["above_phys"]
        assert r["Om0"] > 0


def test_spaced_not_smaller():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    c = list(s["RESULTS"]["contig"]["SAME_MAT"].values())[0]["Om0"]
    sp = list(s["RESULTS"]["spaced"]["SAME_MAT"].values())[0]["Om0"]
    assert sp >= c


def test_outcome():
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "ROBUST_PHYSICAL_ORDER_DEPENDENCE" in text
    assert "STOP" in text
