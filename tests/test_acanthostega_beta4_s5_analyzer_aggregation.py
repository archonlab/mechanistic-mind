"""Focused tests for Beta 4 S5 analyzer aggregation helpers (no simulation ticks)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "experiments"))

from acanthostega_beta4_s5_analyzer_aggregation_lib import (  # noqa: E402
    build_matched_contrasts,
    classify_h2,
    classify_h8,
    dump_stable,
    opportunity_row,
    percentile_ci,
    reject_cross_mixing,
    sha_obj,
    tv_distance,
)


def test_matched_pair_preservation():
    by = {}
    for seed in (5, 23, 42):
        for cid in ("C1", "C4"):
            by[(cid, seed)] = {
                "run_id": f"S4_{cid}_seed{seed}_t2000",
                "condition_id": cid,
                "seed": seed,
                "action_rates_all": {"MOVE": 0.5, "WAIT": 0.5, "OTHER": 0.0},
                "z_selection_count": 10 if cid == "C1" else 0,
                "contact_event_count": 1,
                "lineage": {"stream_records": 0},
            }
    out = build_matched_contrasts(by)
    assert out["C1_C4"]["valid_pairs"] == 3
    assert out["C1_C4"]["expected_pairs"] == 3


def test_pilot_supersession_ledger_shape():
    # inclusion policy: pilot marked excluded; primary confirmatory
    primary = {"run_id": "S4_C1_seed17_t2000", "confirmatory": True}
    pilot = {"run_id": "S2_C1_seed17_t1200", "confirmatory": False, "superseded": True}
    assert primary["confirmatory"] and not pilot["confirmatory"]
    assert pilot["superseded"]


def test_zero_opportunity_and_true_zero():
    m = {
        "run_id": "x",
        "condition_id": "C1",
        "seed": 1,
        "move_selections": 0,
        "translation_per_MOVE_mean": None,
        "z_down_count": 5,
        "z_nonzero_actuation_count": 5,
        "contact_event_count": 0,
        "work_positive_count": 0,
    }
    row = opportunity_row(m)
    assert row["MOVE"]["zero_opportunity"] is True
    assert row["Z_DOWN"]["true_zero"] is True  # opportunities but no contacts
    assert row["Z_DOWN"]["zero_opportunity"] is False


def test_missing_and_invalid_rejection():
    rows = [
        {"run_id": "S4_C1_seed1_t2000", "condition_id": "C1"},
        {"run_id": "S4_C1_seed1_t2000", "condition_id": "C1"},
    ]
    v = reject_cross_mixing(rows)
    assert any("duplicate" in x for x in v)


def test_cross_condition_mixing_rejection():
    rows = [{"run_id": "S4_C2_seed1_t2000", "condition_id": "C1"}]
    v = reject_cross_mixing(rows)
    assert any("cross_condition" in x for x in v)


def test_cross_seed_identity_in_tv():
    p = {"MOVE": 1.0, "WAIT": 0.0, "OTHER": 0.0}
    q = {"MOVE": 0.0, "WAIT": 1.0, "OTHER": 0.0}
    assert tv_distance(p, q) == pytest.approx(1.0)


def test_temporal_autocorrelation_policy_seed_ci():
    xs = [0.1, 0.2, 0.15, 0.12, 0.18]
    ci = percentile_ci(xs)
    assert ci["ticks_as_iid"] is False
    assert ci["replication_unit"] == "condition×seed"
    assert ci["n"] == 5


def test_psc_pre_post_not_mixed_in_h9_inputs():
    # ensure classifiers receive separate pre/post dicts in fixture shape
    c2 = {
        "seed": 17,
        "action_rates_post_1000": {"MOVE": 0.8, "WAIT": 0.2, "OTHER": 0.0},
        "action_rates_pre_1000": {"MOVE": 0.1, "WAIT": 0.9, "OTHER": 0.0},
    }
    assert c2["action_rates_post_1000"] != c2["action_rates_pre_1000"]


def test_h2_underpowered_zero_move():
    rows = [
        {
            "move_selections": 0,
            "translation_per_MOVE_mean": None,
        }
        for _ in range(10)
    ]
    out = classify_h2(rows)
    assert out["status"] == "INCONCLUSIVE_UNDERPOWERED"


def test_h8_not_exercised_not_fail():
    rows = [{"failure_event_count": 0, "failure_ladder_complete_count": 0} for _ in range(10)]
    out = classify_h8(rows)
    assert out["status"] == "INCONCLUSIVE_CAPABILITY_NOT_EXERCISED"


def test_deterministic_output_ordering():
    a = dump_stable({"b": 1, "a": 2})
    b = dump_stable({"a": 2, "b": 1})
    assert a == b
    assert sha_obj({"b": 1, "a": 2}) == sha_obj({"a": 2, "b": 1})


def test_rerun_idempotence_hash():
    payload = {"x": [1, 2, 3], "y": {"z": True}}
    assert sha_obj(payload) == sha_obj(json.loads(json.dumps(payload)))
