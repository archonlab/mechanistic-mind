"""MM-EXP-4 research tests — zero production change."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path("results/mm_exp4_gap_redistribution_second_exposure_flux")


def test_pack_and_replication():
    assert (ROOT / "FINAL_REPORT.md").exists()
    assert (ROOT / "PREREGISTRATION.md").exists()
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    assert s["freeze_ok"]
    r = s["RESULTS"]["spaced"]["23"]
    assert r["Om0"] > 0.015
    assert r["dose_ok"]
    assert s["RESULTS"]["spaced"]["23"]["Om0"] > s["RESULTS"]["contig"]["23"]["Om0"]


def test_budget_closed():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    r = s["RESULTS"]["spaced"]["23"]
    assert r["max_recon_err"] == 0.0
    assert r["R_full_norm"] < 1e-9
    assert r["actual_path_err"] == 0.0


def test_gap_contracts_not_rotates():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    r = s["RESULTS"]["spaced"]["23"]
    assert r["dB_pre2"] < r["dB_post1"]
    assert r["cos_theta"] > 0.99


def test_second_flux_not_larger():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    c = s["RESULTS"]["contig"]["23"]
    sp = s["RESULTS"]["spaced"]["23"]
    assert sp["dJ0"] < c["dJ0"]
    assert sp["dRecv2"] < c["dRecv2"]


def test_state_sufficiency_and_bswap():
    s = json.loads((ROOT / "experiment_summary.json").read_text())
    r = s["RESULTS"]["spaced"]["23"]
    assert r["match_self"] == 0.0
    assert r["matched_div"] == 0.0
    assert r["B_swap_follows"]


def test_outcome():
    text = (ROOT / "FINAL_REPORT.md").read_text()
    assert "GAP_AMPLIFICATION_MULTI_TERM" in text
    assert "PRIOR_FLUX_LEDGER_INCOMPLETE" in text
    assert "STOP" in text
