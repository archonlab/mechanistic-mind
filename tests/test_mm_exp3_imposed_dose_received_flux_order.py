"""MM-EXP-3 research tests — zero production change."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("results/mm_exp3_imposed_dose_received_flux_order")


def test_pack_and_replication():
    assert (ROOT / "FINAL_REPORT.md").exists()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["freeze_ok"]
    assert s["DET"]["dup"] == 0.0
    r = s["RESULTS"]["spaced"]["SAME_MAT"]
    r23 = r["23"] if "23" in r else r[23]
    assert r23["Om0"] > 0.015
    assert r23["dose_ok"]


def test_recv_differs():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    r = s["RESULTS"]["spaced"]["SAME_MAT"]
    r23 = r["23"] if "23" in r else r[23]
    assert any(abs(x) > 1e-6 for x in r23["dRecv"])


def test_gap_shrinks_db_but_larger_om():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    c = s["RESULTS"]["contig"]["SAME_MAT"]
    sp = s["RESULTS"]["spaced"]["SAME_MAT"]
    c23 = c["23"] if "23" in c else c[23]
    s23 = sp["23"] if "23" in sp else sp[23]
    assert s23["dB_pre2"] < c23["dB_pre2"]
    assert s23["Om0"] > c23["Om0"]


def test_state_sufficiency_match_self():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    r = s["RESULTS"]["spaced"]["SAME_MAT"]
    r23 = r["23"] if "23" in r else r[23]
    assert r23["match_self"] == 0.0


def test_outcome():
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "PARTIAL_FLUX_MEDIATION" in text
    assert "STOP" in text
