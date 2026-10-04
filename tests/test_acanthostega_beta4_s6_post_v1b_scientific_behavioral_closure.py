"""Post-V1B S6 closure tests — zero simulation ticks."""
from __future__ import annotations

import json
from pathlib import Path

OUT = Path("results/acanthostega_beta4_s6_post_v1b_scientific_behavioral_closure")
HIST = Path("results/acanthostega_beta4_s6_scientific_behavioral_closure")
GENERATION = "GEN_POST_V1B_VERTICAL_SUPPORT_ESCAPE_REPAIR"
OVERALL = (
    "BETA4_PARTIALLY_VALIDATED_WITH_BOUNDED_SUPPORTED_CLAIMS_AND_EXPLICIT_UNRESOLVED_OR_FAILED_HYPOTHESES"
)


def test_required_artifacts():
    for name in (
        "INPUT_AUTHORITY_MANIFEST.json",
        "SCIENTIFIC_GENERATION_REGISTRY.json",
        "S5_REPRODUCTION.json",
        "FINAL_HYPOTHESIS_REGISTRY.json",
        "RELEASE_CLAIM_MATRIX.md",
        "RELEASE_CLAIM_MATRIX.json",
        "HISTORICAL_CLOSURE_COMPARISON.json",
        "SCIENTIFIC_DEBT_REGISTER.json",
        "RELEASE_READINESS_BOUNDARY.json",
        "FINAL_REPORT.md",
        "DETERMINISM_CHECK.json",
        "IMMUTABILITY_CHECK.json",
    ):
        assert (OUT / name).is_file(), name


def test_s5_reproduced():
    r = json.loads((OUT / "S5_REPRODUCTION.json").read_text())
    assert r["reproduced"] is True
    assert r["TOTAL_SIMULATED_TICKS"] == 0
    assert r["statuses"]["H9"] == "FAIL"


def test_final_status_counts():
    reg = json.loads((OUT / "FINAL_HYPOTHESIS_REGISTRY.json").read_text())
    assert reg["counts"]["PASS"] == 6
    assert reg["counts"]["FAIL"] == 1
    assert reg["counts"]["INCONCLUSIVE"] == 3


def test_h9_negative_preserved():
    h9 = json.loads((OUT / "PSC_H9_NEGATIVE_RESULT_AUDIT.json").read_text())
    assert h9["H9_NEGATIVE_RESULT_PRESERVED"] is True
    assert h9["H9_FINAL_STATUS"] == "FAIL"
    assert "universally useless" in h9["explicitly_not_claimed"][0]


def test_acoustic_c6_ablation():
    a = json.loads((OUT / "ACOUSTIC_LINEAGE_CLOSURE.json").read_text())
    assert a["OSC_LPS_A3_A5_GLOBAL_JOIN_RATE"] == 0.95
    assert a["OSC_LPS_A3_A5_ELIGIBLE_JOIN_RATE"] == 1.0
    assert len(a["missing_runs"]) == 2
    assert all(m["class"] == "LEGITIMATE_NO_SOURCE_ABLATION" for m in a["missing_runs"])
    assert a["h4_downgraded"] is False


def test_generation_registry_current():
    g = json.loads((OUT / "SCIENTIFIC_GENERATION_REGISTRY.json").read_text())
    pre = g["entries"][0]
    cur = g["entries"][1]
    assert pre["current_scientific_authority"] is False
    assert cur["generation"] == GENERATION
    assert cur["current_scientific_authority"] is True


def test_historical_s6_not_current_and_unchanged():
    cmp = json.loads((OUT / "HISTORICAL_CLOSURE_COMPARISON.json").read_text())
    assert cmp["historical_s6_current_authority"] is False
    assert cmp["OLD_CONCLUSIONS_REPRODUCED_UNDER_REPAIRED_PHYSICS"] is True
    assert cmp["HYPOTHESIS_STATUS_CHANGE_COUNT"] == 0
    assert cmp["ENTERS_CONFIRMATORY_COUNT"] is False
    imm = json.loads((OUT / "IMMUTABILITY_CHECK.json").read_text())
    assert imm["historical_s6_preserved"] is True
    assert (HIST / "FINAL_REPORT.md").is_file()


def test_claim_matrix_bounds():
    m = json.loads((OUT / "RELEASE_CLAIM_MATRIX.json").read_text())
    assert m["counts"]["ALLOWED"] >= 7
    assert m["counts"]["PROHIBITED"] >= 10
    assert any("Consciousness" in c["claim"] or "consciousness" in c["claim"].lower() for c in m["PROHIBITED"])
    assert all("fully scientifically validated for all H1–H10" not in c["claim"] for c in m["ALLOWED"])
    assert any("Causality Generator" in c["claim"] for c in m["PROHIBITED"])


def test_overall_not_fully_validated():
    st = json.loads((OUT / "BETA4_FINAL_SCIENTIFIC_STATUS.json").read_text())
    assert st["BETA4_FINAL_SCIENTIFIC_STATUS"] == OVERALL
    assert st["FULLY_SCIENTIFICALLY_VALIDATED"] is False
    assert "PARTIALLY_VALIDATED" in OVERALL


def test_zero_ticks_and_no_physics_replay():
    s = json.loads((OUT / "S6_CLOSURE_SUMMARY.json").read_text())
    assert s["footer"]["TOTAL_SIMULATED_TICKS"] == 0
    assert s["footer"]["ANALYZER_REPLAYS_PHYSICS"] is False
    assert s["footer"]["NEW_SIMULATION_REQUIRED"] is False
    assert s["footer"]["S6_COMPLETE"] is True


def test_docs_present():
    assert Path("docs/ACANTHOSTEGA_BETA4_S6_POST_V1B_SCIENTIFIC_BEHAVIORAL_CLOSURE.md").is_file()
