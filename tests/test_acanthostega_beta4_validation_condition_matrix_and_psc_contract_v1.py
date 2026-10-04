"""Focused tests for condition-matrix uniqueness + PSC schedule/restore repair."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / "experiments" / "run_acanthostega_beta4_validation_condition_matrix_and_psc_contract_v1.py"


def _load():
    spec = importlib.util.spec_from_file_location("matrix_psc_v1", EXP)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _load()


def test_preregistration_has_no_ambiguous_phrases():
    text = (
        ROOT
        / "results/beta4_scientific_behavioral_validation_architecture/EXPERIMENTAL_CONDITIONS.md"
    ).read_text(encoding="utf-8")
    for phrase in ("As C2 or C1", "As C1/C2", "per contrast", "C1|C2", "either"):
        assert phrase not in text


def test_c8_manifest_bounded_and_excludes_ordinary(mod):
    m = mod.build_c8_manifest()
    assert m["c8_probe_manifest_complete"] is True
    assert m["c8_total_tick_budget"] == 180
    assert m["c8_ordinary_snippet_excluded"] is True
    assert m["c8_probes_enter_behavioral_inference"] is False
    ids = [p["probe_id"] for p in m["probes"]]
    assert "H_ORDINARY" not in ids
    assert any(p.startswith("C8.B_LEFT") for p in ids)
    assert any(p.startswith("C8.C_RIGHT") for p in ids)


def test_all_nine_digests_unique_where_required(mod):
    m = mod.build_c8_manifest()
    d = mod.digest_matrix(m["manifest_digest"])
    assert d["config_digests_complete"]
    assert d["checks"]["C1_C3_equal"]
    assert d["checks"]["C2_differs_C1"]
    assert d["checks"]["C4_differs_C1"]
    assert d["checks"]["C7_differs_C1"]
    assert None not in d["digest_by_condition"].values()


def test_psc_restore_999_1000_1001_and_off_twin(mod):
    # Uses a few simulated ticks; keep under remaining budget by resetting counter.
    mod.TICKS["n"] = 0
    psc = mod.psc_and_restore_probes()
    assert psc["RESTORE_AT_999_PASS"] is True
    assert psc["RESTORE_AT_1000_PASS"] is True
    assert psc["RESTORE_AT_1001_PASS"] is True
    assert psc["PSC_OFF_TWIN_COMPLETE"] is True
    assert psc["PSC_TRANSITION_EXACTLY_ONCE"] is True
    assert psc["WITHHOLD_TRANSITION_RECEIPT_AVAILABLE"] is True
    assert psc["PSC_OFF_TICKS_SNAPSHOT_PRESERVED"] is True
    assert mod.TICKS["n"] <= 40


def test_canonical_fingerprint_unchanged():
    from mechanistic_mind.physical_system.experiment_canonical import canonical_fingerprint
    import json

    man = json.loads(
        (
            ROOT
            / "results/beta4_release_equivalence_and_performance_gate_v1/RELEASE_CANDIDATE_MANIFEST.json"
        ).read_text()
    )
    cfp = canonical_fingerprint(
        {
            "public_preset": "ACANTHOSTEGA_BETA4",
            "seed": 17,
            "model_line": "ACANTHOSTEGA",
            "cognition_enabled": True,
        }
    )
    assert cfp == man["canonical_fingerprint"]
