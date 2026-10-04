"""Post-V1B S5 aggregation tests — zero simulation ticks."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path("results/acanthostega_beta4_s5_post_v1b_analyzer_aggregation")
HIST = Path("results/acanthostega_beta4_s5_analyzer_aggregation")
PRIMARY = Path("results/acanthostega_beta4_repaired_physics_primary_revalidation")
GENERATION = "GEN_POST_V1B_VERTICAL_SUPPORT_ESCAPE_REPAIR"


def test_artifacts_present():
    for name in (
        "INPUT_AUTHORITY_MANIFEST.json",
        "INCLUSION_EXCLUSION_REGISTRY.json",
        "PACKAGE_READABILITY_REPORT.json",
        "CONDITION_SEED_METRICS.json",
        "CONDITION_AGGREGATES.json",
        "MATCHED_SEED_COMPARISONS.json",
        "OPPORTUNITY_DENOMINATORS.json",
        "EXACT_LINEAGE_SUMMARY.json",
        "MISSINGNESS_REGISTRY.json",
        "HYPOTHESIS_RESULTS.json",
        "HISTORICAL_GENERATION_COMPARISON.json",
        "FINAL_REPORT.md",
        "DETERMINISM_CHECK.json",
        "S5_AGGREGATION_SUMMARY.json",
    ):
        assert (OUT / name).is_file(), name


def test_inclusion_contract():
    inc = json.loads((OUT / "INCLUSION_EXCLUSION_REGISTRY.json").read_text())
    assert inc["INCLUDED_GENERATION"] == GENERATION
    assert inc["INCLUDED_PRIMARY_PACKAGE_COUNT"] == 40
    assert inc["INCLUDED_PRIMARY_TICKS"] == 80000
    assert inc["PILOT_PACKAGES_INCLUDED"] is False
    assert inc["PRE_REPAIR_PRIMARY_PACKAGES_INCLUDED"] is False
    assert inc["C8_PROBES_INCLUDED_IN_BEHAVIORAL_INFERENCE"] is False
    assert inc["INVALID_PACKAGES_INCLUDED"] is False


def test_zero_ticks_and_no_s6():
    summary = json.loads((OUT / "S5_AGGREGATION_SUMMARY.json").read_text())
    assert summary["TOTAL_SIMULATED_TICKS"] == 0
    assert summary["footer"]["NEW_SIMULATION_EXECUTED"] is False
    assert summary["footer"]["S6_STARTED"] is False
    assert summary["footer"]["ANALYZER_REPLAYS_PHYSICS"] is False
    assert summary["footer"]["FPV_USED_AS_NUMERIC_AUTHORITY"] is False


def test_historical_s5_preserved():
    hist = json.loads((OUT / "HISTORICAL_GENERATION_COMPARISON.json").read_text())
    assert hist["historical_s5_preserved"] is True
    assert hist["historical_evidence_entered_new_confirmatory_pool"] is False
    assert hist["ENTERS_CONFIRMATORY_COUNT"] is False
    # fingerprint file proves pre/post match at run time
    fp = json.loads((OUT / "HISTORICAL_S5_PRE_RUN_FINGERPRINTS.json").read_text())
    assert fp["HYPOTHESIS_EVIDENCE_MATRIX.json"]
    assert (HIST / "HYPOTHESIS_EVIDENCE_MATRIX.json").is_file()


def test_determinism_pass():
    d = json.loads((OUT / "DETERMINISM_CHECK.json").read_text())
    assert d["pass"] is True
    assert d["TOTAL_SIMULATED_TICKS"] == 0


def test_join_rates_complete():
    j = json.loads((OUT / "EXACT_LINEAGE_SUMMARY.json").read_text())
    assert j["ACTUATION_ETC_EXACT_JOIN_RATE"] == 1.0
    assert j["O3_O4_EXACT_JOIN_RATE"] == 1.0
    assert 0.0 <= j["OSC_LPS_A3_A5_GLOBAL_JOIN_RATE"] <= 1.0
    assert 0.0 <= j["OSC_LPS_A3_A5_ELIGIBLE_JOIN_RATE"] <= 1.0


def test_sources_are_post_v1b_only():
    metrics = json.loads((OUT / "CONDITION_SEED_METRICS.json").read_text())
    for row in metrics["rows"]:
        assert "acanthostega_beta4_repaired_physics_primary_revalidation" in row["source_package"]
        assert "acanthostega_beta4_s4_primary_matched_seed_validation" not in row["source_package"]


def test_matrix_and_pairs():
    summary = json.loads((OUT / "S5_AGGREGATION_SUMMARY.json").read_text())
    assert summary["per_condition_counts"] == {
        "C1": 10,
        "C2": 10,
        "C3": 10,
        "C4": 3,
        "C5": 3,
        "C6": 2,
        "C7": 2,
    }
    assert summary["matched_pair_counts"] == {
        "C2_C3": 10,
        "C1_C4": 3,
        "C1_C5": 3,
        "C1_C6": 2,
        "C1_C7": 2,
    }


def test_primary_acceptance_still_present():
    assert (PRIMARY / "PRIMARY_EXECUTION_ACCEPTANCE.json").is_file()
    a = json.loads((PRIMARY / "PRIMARY_EXECUTION_ACCEPTANCE.json").read_text())
    assert a["footer"]["VERDICT"] == "POST_V1B_PRIMARY_EXECUTION_ACCEPTED"
