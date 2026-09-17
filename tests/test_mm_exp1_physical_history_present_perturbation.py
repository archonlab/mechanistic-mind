"""MM-EXP-1 research tests — zero production change."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("results/mm_exp1_physical_history_present_perturbation")


def test_pack_and_freeze():
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "PREREGISTRATION.md").exists()
    assert (ROOT / "DIFFERENCE_IN_DIFFERENCES.md").exists()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["freeze_ok"]
    assert s["DET"]["identical_input"] == 0.0
    assert s["DET"]["identical_none"] == 0.0


def test_pair_selection_three():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert len(s["pair_info"]) == 3


def test_thermal_null():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert all(r["cls"] == "BELOW_FLOOR" for r in s["RESULTS"]["EXT_THERMAL"])


def test_swap_follows_hidden():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["SWAP"]["follows_hidden"]
    assert s["SWAP"]["d_swapA_vs_B"] == 0.0


def test_no_post_selection_amendments():
    assert (ROOT / "AMENDMENTS.md").read_text().strip().startswith("NONE")


def test_outcome_in_report():
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "WEAK_NATURAL_HISTORY_INPUT_INTERACTION" in text
    assert "STOP" in text
