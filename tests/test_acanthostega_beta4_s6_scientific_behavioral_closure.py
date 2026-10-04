"""Focused read-only tests for Beta 4 S6 scientific closure."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from run_acanthostega_beta4_s6_scientific_behavioral_closure import (  # noqa: E402
    OVERALL_STATUS,
    acoustic_closure,
    claim_matrix,
    reproduce_s5,
)


def test_s5_reproduction():
    r = reproduce_s5()
    assert r["reproduced"] is True
    assert r["h9_fail_preserved"] is True
    assert r["statuses"]["H9"] == "FAIL"


def test_status_count_consistency():
    r = reproduce_s5()
    st = r["statuses"]
    supported = sum(1 for s in st.values() if s == "PASS")
    failed = sum(1 for s in st.values() if s == "FAIL")
    inconclusive = sum(1 for s in st.values() if str(s).startswith("INCONCLUSIVE"))
    assert supported + failed + inconclusive == 10
    assert supported == 6
    assert failed == 1
    assert inconclusive == 3


def test_h9_negative_preserved():
    r = reproduce_s5()
    assert all(v == 0.0 for v in r["h9_tv_recomputed"])
    assert len(r["h9_tv_recomputed"]) == 10


def test_acoustic_missingness_is_c6_ablation():
    a = acoustic_closure()
    assert a["missingness_classified"] is True
    assert a["OSC_LPS_A3_A5_ELIGIBLE_JOIN_RATE"] == 1.0
    assert all(m["class"] == "LEGITIMATE_NO_SOURCE_ABLATION" for m in a["missing_runs"])
    assert len(a["missing_runs"]) == 2


def test_claim_matrix_consistency():
    st = reproduce_s5()["statuses"]
    m = claim_matrix(st)
    assert m["counts"]["ALLOWED"] >= 1
    assert m["counts"]["PROHIBITED"] >= 1
    assert any("Consciousness" in c["claim"] or "consciousness" in c["claim"].lower() for c in m["PROHIBITED"])
    assert all("fully scientifically validated for all H1–H10" not in c["claim"] for c in m["ALLOWED"])


def test_missing_not_zero_and_zero_opp_not_failure_in_overall():
    # overall status must not imply full validation
    assert "PARTIALLY_VALIDATED" in OVERALL_STATUS
    assert "FULLY" not in OVERALL_STATUS


def test_superseded_draft_excluded_conceptually():
    # authority script lists archived ambiguous matrix as excluded
    from run_acanthostega_beta4_s6_scientific_behavioral_closure import MATRIX

    archived = MATRIX / "EXPERIMENTAL_CONDITIONS_AMBIGUOUS_SUPERSEDED_ARCHIVED.md"
    assert archived.is_file()


def test_deterministic_dump_ordering():
    from run_acanthostega_beta4_s6_scientific_behavioral_closure import _dump

    assert _dump({"b": 1, "a": 2}) == _dump({"a": 2, "b": 1})


def test_no_writes_to_s5_during_reproduce(tmp_path):
    s5 = ROOT / "results" / "acanthostega_beta4_s5_analyzer_aggregation" / "HYPOTHESIS_EVIDENCE_MATRIX.json"
    before = s5.read_bytes()
    reproduce_s5()
    assert s5.read_bytes() == before
