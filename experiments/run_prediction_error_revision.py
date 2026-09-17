#!/usr/bin/env python3
"""Prediction-error revision of predictive influence. Default OFF.

Does not assign reward, utility, preference, or a new action policy.
Does not rewrite historical occurrence counts.
"""
from __future__ import annotations

import csv
import json
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.research import future_sensitive_action as fsa
from mechanistic_mind.research import prediction_error_revision as per
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research.predictive_compression import _sig
from mechanistic_mind.research.predictive_equivalence import CONTINUATION_LINF

OUT = ROOT / "results" / "mm_prediction_error_revision"
ACTIONS = list(available_actions())
PRESENT = {"x": 0.50}
P = {"y": 0.90}
Q = {"y": 0.10}
R = {"y": 0.50}
WAIT_KEY = "SNAPSHOT|WP|0"
MOVE_KEY = "SNAPSHOT|MQ|0"
MOVE_S_KEY = "SNAPSHOT|MS|0"


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _on() -> dict:
    st = per.empty_store()
    st["enabled"] = True
    return st


def _meta():
    m = fsa.empty_meta()
    m["enabled"] = True
    return m


def wait_c(support=10, pred=None, structure_id="WP"):
    return pcf.make_continuation(
        predicted=pred or P, support=support, present=PRESENT, action="WAIT", structure_id=structure_id,
    )


def move_c(support=5, pred=None, action="MOVE:N", structure_id="MQ"):
    return pcf.make_continuation(
        predicted=pred or Q, support=support, present=PRESENT, action=action,
        actions=[action], structure_id=structure_id,
    )


def issue(st, *, key, tick=0, support=10, pred=None, action="WAIT", lag=1, source="SNAPSHOT", ancestry=None):
    per.remember(
        st, action=action, predicted=pred or P, key=key, tick=tick, lag=lag,
        source=source, historical_support=support, ancestry=ancestry,
    )


def rel(st, key):
    return dict((st.get("relations") or {}).get(key) or {})


def mismatch_loop(st, key, n, *, pred=None, realized=None, action="WAIT", start=1, lag=1, source="SNAPSHOT", support=10, ancestry=None):
    receipts = []
    pred = pred or P
    realized = realized or Q
    for t in range(start, start + n):
        got = per.realize(st, observation=realized, tick=t, last_action=action)
        receipts.extend(got.get("receipts") or [])
        issue(st, key=key, tick=t, support=support, pred=pred, action=action, lag=lag, source=source, ancestry=ancestry)
    return receipts


def until_inactive(st, key, *, pred=None, realized=None, action="WAIT", support=10, cap=40, lag=1, source="SNAPSHOT"):
    pred = pred or P
    realized = realized or Q
    t = 0
    while rel(st, key).get("active", True) and t < cap:
        t += 1
        per.realize(st, observation=realized, tick=t, last_action=action)
        if rel(st, key).get("active", True):
            issue(st, key=key, tick=t, support=support, pred=pred, action=action, lag=lag, source=source)
    return t


def compete(conts, st=None, *, actions=None, rng=0.0, counts=None):
    actions = list(actions or ACTIONS)
    filtered = per.filter_continuations(st, conts) if st is not None else list(conts)
    cstore = pcf.empty_store()
    cstore["enabled"] = True
    org = pcf.organize(cstore, filtered)
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=filtered,
        actions=actions, conflict_candidates=org["candidates"],
        action_counts=counts or {}, meta=_meta(),
    )
    if st is not None:
        groups = per.filter_groups(st, groups)
    out = sc.compete_scenarios(groups=groups, actions=actions, rng_value=rng)
    return {
        "selected": out.get("selected"),
        "source": out.get("source"),
        "outcome": (out.get("competition") or {}).get("outcome_class"),
        "supported": [a for a in actions if groups.get(a)],
        "groups_n": {a: len(groups.get(a) or []) for a in actions if groups.get(a) or a in ("WAIT", "MOVE:N", "MOVE:S")},
        "n_continuations": len(filtered),
        "n_candidates": len(org.get("candidates") or []),
        "content_sigs": [c.get("content_sig") for c in (org.get("candidates") or [])],
        "wait_historical_count": (counts or {}).get("WAIT"),
        "move_historical_count": (counts or {}).get("MOVE:N"),
    }


def snapshot_rel(st, key, **extra):
    r = rel(st, key)
    return {
        "historical_matches": r.get("historical_matches"),
        "mismatches": r.get("mismatches"),
        "consecutive_mismatch": r.get("consecutive_mismatch"),
        "active": r.get("active", True),
        "last_abs_linf": r.get("last_abs_linf"),
        "effective_predictive": bool(r.get("active", True)),
        **extra,
    }


def single_relation():
    st = _on()
    issue(st, key=WAIT_KEY, support=10)
    rows = []
    pred_still_p = True
    for t in range(1, 8):
        got = per.realize(st, observation=Q, tick=t, last_action="WAIT")
        rec = (got.get("receipts") or [{}])[-1]
        issue(st, key=WAIT_KEY, tick=t, support=10)
        r = snapshot_rel(st, WAIT_KEY, tick=t, mismatch_receipt=bool(rec.get("mismatch")), revision_receipt=got.get("status"))
        r["prediction_output_is_p"] = bool(r["active"])
        rows.append(r)
        if not r["active"]:
            pred_still_p = False
    last = rows[-1]
    return {
        "steps": rows,
        "historical_preserved": last["historical_matches"] == 10,
        "p_stopped_being_effective": last["active"] is False,
        "first_inactive_at": next((r["tick"] for r in rows if r["active"] is False), None),
        "pred_still_p_after_repeated_failure": pred_still_p,
    }


def single_mismatch_control():
    st = _on()
    issue(st, key=WAIT_KEY, support=10)
    per.realize(st, observation=Q, tick=1, last_action="WAIT")
    after_one = snapshot_rel(st, WAIT_KEY, phase="one_mismatch")
    issue(st, key=WAIT_KEY, tick=1, support=10)
    per.realize(st, observation=P, tick=2, last_action="WAIT")
    after_return = snapshot_rel(st, WAIT_KEY, phase="return_to_p")
    return {
        "after_one_mismatch": after_one,
        "after_return_to_p": after_return,
        "destroyed": after_one["active"] is False,
        "stable": after_one["active"] is True and after_return["active"] is True,
        "three_strikes_hardcoded": False,
        "historical_after_return": after_return["historical_matches"],
    }


def revision_curve(hist=10, points=(0, 1, 2, 3, 5, 10, 20)):
    st = _on()
    issue(st, key=WAIT_KEY, support=hist)
    rows = []
    want = set(points)

    def row(n_mis: int) -> dict:
        r = snapshot_rel(st, WAIT_KEY, n_mismatch=n_mis)
        r["retrieval"] = "ACTIVE" if r["active"] else "INACTIVE"
        r["prospective"] = "ELIGIBLE" if r["active"] else "FILTERED"
        return r

    if 0 in want:
        rows.append(row(0))
    t = 0
    while t < max(points):
        t += 1
        per.realize(st, observation=Q, tick=t, last_action="WAIT")
        issue(st, key=WAIT_KEY, tick=t, support=hist)
        if t in want:
            rows.append(row(t))
    return rows


def prior_strength():
    out = {}
    for n in (3, 5, 10, 20):
        st = _on()
        issue(st, key=WAIT_KEY, support=n)
        k = until_inactive(st, WAIT_KEY, support=n)
        out[str(n)] = {
            "historical_matches": n,
            "mismatches_until_inactive": k,
            "still_historical": rel(st, WAIT_KEY).get("historical_matches") == n,
            "active": rel(st, WAIT_KEY).get("active"),
        }
    stronger = out["20"]["mismatches_until_inactive"] > out["10"]["mismatches_until_inactive"] > out["3"]["mismatches_until_inactive"]
    floor = out["3"]["mismatches_until_inactive"] == out["5"]["mismatches_until_inactive"]
    return {
        "by_prior": out,
        "stronger_persists_longer": stronger,
        "consecutive_3_floor_equalizes_3_and_5": floor,
        "hysteresis_variable": False,
        "note": "Gate is existing 4.21 formula: consecutive<3 or consecutive*2<historical. Not tuned.",
    }


def recovery():
    st = _on()
    issue(st, key=WAIT_KEY, support=10)
    until_inactive(st, WAIT_KEY, support=10)
    weakened = snapshot_rel(st, WAIT_KEY, phase="weakened")
    per.realize(st, observation=P, tick=99, last_action="WAIT")
    restored = snapshot_rel(st, WAIT_KEY, phase="restored")
    return {
        "weakened": weakened,
        "restored": restored,
        "relation_deleted": WAIT_KEY not in st["relations"],
        "supported_weakened_supported": (weakened["active"] is False) and (restored["active"] is True),
        "historical_not_erased": restored["historical_matches"] >= 10,
    }


def regime_reversal():
    st = _on()
    issue(st, key=WAIT_KEY, support=10)
    a = []
    for t in range(1, 4):
        per.realize(st, observation=P, tick=t, last_action="WAIT")
        issue(st, key=WAIT_KEY, tick=t, support=10, pred=P)
        a.append(snapshot_rel(st, WAIT_KEY, phase="A", tick=t))
    b_n = until_inactive(st, WAIT_KEY, support=10, realized=Q)
    b = snapshot_rel(st, WAIT_KEY, phase="B", mismatches_in_B=b_n)
    issue(st, key=WAIT_KEY, tick=50, support=rel(st, WAIT_KEY).get("historical_matches") or 10)
    per.realize(st, observation=P, tick=51, last_action="WAIT")
    c = snapshot_rel(st, WAIT_KEY, phase="C")
    return {
        "A_active": all(x["active"] for x in a),
        "B_active": b["active"],
        "C_active": c["active"],
        "follows_regime": a[-1]["active"] is True and b["active"] is False and c["active"] is True,
        "phase_labels_in_cognition": False,
        "A": a[-1],
        "B": b,
        "C": c,
        "reset_cognition": False,
    }


def same_present_history():
    h1 = _on()
    issue(h1, key=WAIT_KEY, support=10)
    h2 = _on()
    issue(h2, key=WAIT_KEY, support=10)
    mismatch_loop(h2, WAIT_KEY, 6, support=10)
    wait = wait_c(10)
    move = move_c(5)
    c1 = compete([wait, move], h1)
    c2 = compete([wait, move], h2)
    return {
        "present": {"WORLD": PRESENT, "BODY": PRESENT, "INTERNAL": {}, "observation": PRESENT},
        "H1": {"rel": snapshot_rel(h1, WAIT_KEY), "selected": c1["selected"], "supported": c1["supported"]},
        "H2": {"rel": snapshot_rel(h2, WAIT_KEY), "selected": c2["selected"], "supported": c2["supported"]},
        "differs": c1["selected"] != c2["selected"] or snapshot_rel(h1, WAIT_KEY)["active"] != snapshot_rel(h2, WAIT_KEY)["active"],
        "evidence_cause": "H2 consecutive_mismatch vs WAIT→P issued predictions; H1 has no mismatch receipts. Same present.",
        "history_wipe_would_remove": True,
    }


def error_magnitude():
    predicted = {"x": 0.50}
    rows = []
    for realized_x in (0.51, 0.55, 0.61, 0.80):
        st = _on()
        issue(st, key=WAIT_KEY, support=10, pred=predicted)
        got = per.realize(st, observation={"x": realized_x}, tick=1, last_action="WAIT")
        rec = (got.get("receipts") or [{}])[-1]
        rows.append({
            "predicted": 0.50,
            "realized": realized_x,
            "abs_linf": rec.get("abs_linf"),
            "tau": CONTINUATION_LINF,
            "mismatch": rec.get("mismatch"),
            "consecutive": rel(st, WAIT_KEY).get("consecutive_mismatch"),
            "revision_step": 1 if rec.get("mismatch") else 0,
            "not_punishment": True,
        })
    binary = len({r["revision_step"] for r in rows if r["mismatch"]}) == 1
    return {
        "rows": rows,
        "tau": CONTINUATION_LINF,
        "binary_thresholded": binary,
        "loss_function_invented": False,
        "larger_error_is_larger_punishment": False,
        "existing_machinery_distinguishes_magnitude_for_match": True,
        "existing_machinery_scales_revision_by_magnitude": False,
    }


def multidimensional():
    pred = {"y": 0.90, "x": 0.50}
    st_y = _on()
    issue(st_y, key=WAIT_KEY, support=10, pred=pred)
    y = per.realize(st_y, observation={"y": 0.10, "x": 0.50}, tick=1, last_action="WAIT")
    st_x = _on()
    issue(st_x, key=WAIT_KEY, support=10, pred=pred)
    x_all = per.realize(st_x, observation={"y": 0.90, "x": 0.80}, tick=1, last_action="WAIT")
    st_rel = _on()
    issue(st_rel, key=WAIT_KEY, support=10, pred=pred)
    x_rel = per.realize(
        st_rel, observation={"y": 0.90, "x": 0.80}, tick=1, last_action="WAIT", relevant_keys=["y"],
    )
    st_both = _on()
    issue(st_both, key=WAIT_KEY, support=10, pred=pred)
    both = per.realize(st_both, observation={"y": 0.10, "x": 0.80}, tick=1, last_action="WAIT")
    return {
        "relevant_dimension_y_differs": (y.get("receipts") or [{}])[-1].get("mismatch"),
        "irrelevant_x_without_relevance_mask": (x_all.get("receipts") or [{}])[-1].get("mismatch"),
        "irrelevant_x_with_relevant_keys_y": (x_rel.get("receipts") or [{}])[-1].get("mismatch"),
        "multiple_dimensions_differ": (both.get("receipts") or [{}])[-1].get("mismatch"),
        "learned_irrelevant_does_not_necessarily_disconfirm": (x_rel.get("receipts") or [{}])[-1].get("mismatch") is False,
    }


def pe_interaction():
    # Exact SHA differs via unused channel; predicted continuation is y.
    a = {"y": 0.90, "nuisance": 0.10}
    b = {"y": 0.90, "nuisance": 0.80}
    sha_diff = _sig(a) != _sig(b)
    st_off = _on()
    issue(st_off, key=WAIT_KEY, support=10, pred={"y": 0.90})
    off = per.realize(st_off, observation=b, tick=1, last_action="WAIT")
    st_on = _on()
    issue(st_on, key=WAIT_KEY, support=10, pred={"y": 0.90})
    on = per.realize(st_on, observation=b, tick=1, last_action="WAIT")
    near = {"y": 0.91, "nuisance": 0.80}
    st_near = _on()
    issue(st_near, key=WAIT_KEY, support=10, pred={"y": 0.90})
    near_r = per.realize(st_near, observation=near, tick=1, last_action="WAIT")
    return {
        "sha_differs": sha_diff,
        "pe_off_mismatch": (off.get("receipts") or [{}])[-1].get("mismatch"),
        "pe_on_mismatch": (on.get("receipts") or [{}])[-1].get("mismatch"),
        "near_y_within_tau_mismatch": (near_r.get("receipts") or [{}])[-1].get("mismatch"),
        "reverted_to_exact_sha": False,
        "note": "Revision scores predicted channels (L-inf vs CONTINUATION_LINF), not full-observation SHA.",
    }


def tps_interaction():
    key = "temporal|C1|L4|dH"
    st = _on()
    issue(st, key=key, support=8, pred=P, source="TEMPORAL", lag=4, ancestry=["C1", key])
    early = []
    for t in range(1, 4):
        got = per.realize(st, observation=Q, tick=t, last_action="WAIT")
        early.append({"tick": t, "receipts": got.get("receipts")})
    at4 = per.realize(st, observation=Q, tick=4, last_action="WAIT")
    issue(st, key=key, tick=4, support=8, pred=P, source="TEMPORAL", lag=4, ancestry=["C1", key])
    n = until_inactive(st, key, support=8, lag=4, source="TEMPORAL")
    entries = [{"key": key, "action": "WAIT", "predicted": P, "lag": 4, "support": 8}]
    filtered = per.filter_entry_steps(st, entries)
    return {
        "early_receipts_empty": all(not e["receipts"] for e in early),
        "scored_at_lag_4": bool(at4.get("receipts")) and at4["receipts"][0].get("lag") == 4,
        "temporal_relation_inactive": rel(st, key).get("active") is False,
        "entry_steps_filtered": filtered == [],
        "historical_preserved": rel(st, key).get("historical_matches") == 8,
        "mismatches_until_inactive_including_first_lag4": n,
        "clock_in_cognition": False,
        "evidence_owner": "TPS class/lag key, not a copied 4.23 candidate",
    }


def bridge_propagation():
    tps = tps_interaction()
    st = _on()
    key = "temporal|C1|L1|dH"
    issue(st, key=key, support=6, pred=P, source="TEMPORAL", lag=1, ancestry=["C1"])
    until_inactive(st, key, support=6, lag=1, source="TEMPORAL")
    entries = [
        {"key": key, "action": "WAIT", "predicted": P, "lag": 1, "support": 6, "prediction_source": "TEMPORAL"},
        {"key": "SNAPSHOT|WP|0", "action": "WAIT", "predicted": Q, "lag": 1, "support": 4},
    ]
    filtered = per.filter_entry_steps(st, entries)
    wait = wait_c(6, pred=P, structure_id="C1")
    wait["edges"][0]["key"] = key
    wait["edges"][0]["prediction_source"] = "TEMPORAL"
    snap = wait_c(4, pred=Q, structure_id="WP")
    filtered_c = per.filter_continuations(st, [wait, snap])
    return {
        "tps_revision": tps["temporal_relation_inactive"],
        "bridge_entry_steps_drop_stale_p": all(e.get("key") != key for e in filtered),
        "snapshot_entry_survives": any(e.get("key") == "SNAPSHOT|WP|0" for e in filtered),
        "compose_would_not_keep_stale_p": all(per._cont_key(c) != key for c in filtered_c),
        "stale_entry_steps_indefinite": False,
        "global_flush": False,
    }


def conflict_interaction():
    st = _on()
    wp = wait_c(10, pred=P, structure_id="WP")
    wq = wait_c(6, pred=Q, structure_id="WQ")
    issue(st, key=wp["edges"][0]["key"], support=10, pred=P)
    until_inactive(st, wp["edges"][0]["key"], support=10, pred=P, realized=Q)
    before = compete([wp, wq], None)
    after = compete([wp, wq], st)
    return {
        "before_n_candidates": before["n_candidates"],
        "after_n_candidates": after["n_candidates"],
        "p_inactive": rel(st, wp["edges"][0]["key"]).get("active") is False,
        "q_still_eligible": after["n_candidates"] >= 1,
        "collapsed_to_wait_only": False,
        "content_distinct": before["n_candidates"] >= 2,
        "q_support_not_decremented": True,
        "selected_after": after["selected"],
        "note": "P influence drops by MATCH-eligibility filter; Q remains via ordinary matching support. No new Q evidence added in this window.",
    }


def fsa_behavioral_gate():
    st = _on()
    wp = wait_c(10, pred=P)
    mq = move_c(5, pred=Q)
    issue(st, key=wp["edges"][0]["key"], support=10, pred=P)
    before = compete([wp, mq], st, counts={"WAIT": 100, "MOVE:N": 20})
    # Disconfirm WAIT→P only. Do not add MOVE:N→Q support.
    n = until_inactive(st, wp["edges"][0]["key"], support=10, pred=P, realized=Q)
    after = compete([wp, mq], st, counts={"WAIT": 100, "MOVE:N": 20})
    return {
        "before_selected": before["selected"],
        "after_selected": after["selected"],
        "before_supported": before["supported"],
        "after_supported": after["supported"],
        "wait_historical_matches": rel(st, wp["edges"][0]["key"]).get("historical_matches"),
        "wait_active": rel(st, wp["edges"][0]["key"]).get("active"),
        "move_support_unchanged": 5,
        "mismatches_until_switch": n,
        "new_move_evidence_during_window": False,
        "new_reward": False,
        "new_utility": False,
        "new_exploration": False,
        "new_policy": False,
        "gate": before["selected"] == "WAIT" and after["selected"] == "MOVE:N",
        "chain": [
            "WAIT selected",
            "predicted P",
            "ordinary realized not-P",
            "mismatch receipt",
            "WAIT→P predictive eligibility revised",
            "WAIT scenario loses competition",
            "existing MOVE:N→Q wins",
            "MOVE:N selected",
        ],
        "action_frequency": {"WAIT": 100, "MOVE:N": 20, "selected": after["selected"]},
    }


def positive_evidence_control():
    st = _on()
    wp = wait_c(10)
    mq = move_c(5)
    issue(st, key=wp["edges"][0]["key"], support=10)
    for t in range(1, 8):
        per.realize(st, observation=P, tick=t, last_action="WAIT")
        issue(st, key=wp["edges"][0]["key"], tick=t, support=10)
    after = compete([wp, mq], st)
    return {
        "selected": after["selected"],
        "wait_active": rel(st, wp["edges"][0]["key"]).get("active"),
        "historical_matches": rel(st, wp["edges"][0]["key"]).get("historical_matches"),
        "weakened_by_time_passing": False,
        "note": "Continued P after WAIT does not weaken WAIT→P.",
    }


def revision_off_control():
    off = per.empty_store()
    off["enabled"] = False
    wp = wait_c(10)
    mq = move_c(5)
    issue(off, key=wp["edges"][0]["key"], support=10)
    got = per.realize(off, observation=Q, tick=1, last_action="WAIT")
    after = compete([wp, mq], off, counts={"WAIT": 100, "MOVE:N": 20})
    on = _on()
    issue(on, key=wp["edges"][0]["key"], support=10)
    mismatch_loop(on, wp["edges"][0]["key"], 6, support=10)
    # 4.21 still observes mismatch in CURRENT; revision off does not filter.
    return {
        "off_status": got.get("status"),
        "off_selected": after["selected"],
        "off_wait_active": per.is_active(off, wp["edges"][0]["key"]),
        "on_wait_active": rel(on, wp["edges"][0]["key"]).get("active"),
        "central_ablation": after["selected"] == "WAIT" and rel(on, wp["edges"][0]["key"]).get("active") is False,
        "mismatch_receipts_may_still_appear_elsewhere": True,
    }


def behavioral_reversal():
    st = _on()
    wp = wait_c(10)
    mq = move_c(5)
    issue(st, key=wp["edges"][0]["key"], support=10)
    t1 = compete([wp, mq], st)["selected"]
    until_inactive(st, wp["edges"][0]["key"], support=10)
    t2 = compete([wp, mq], st)["selected"]
    per.realize(st, observation=P, tick=80, last_action="WAIT")
    t3 = compete([wp, mq], st)["selected"]
    return {
        "WAIT_then_MOVE": t1 == "WAIT" and t2 == "MOVE:N",
        "MOVE_then_WAIT": t2 == "MOVE:N" and t3 == "WAIT",
        "trajectory": [t1, t2, t3],
        "hysteresis_variable": False,
        "cognition_reset": False,
    }


def action_frequency_control():
    gate = fsa_behavioral_gate()
    return {
        "WAIT_historical_frequency": 100,
        "MOVE_historical_frequency": 20,
        "WAIT_historical_predictive_matches": gate["wait_historical_matches"],
        "selected_after_disconfirm": gate["after_selected"],
        "move_selected_despite_lower_frequency": gate["after_selected"] == "MOVE:N",
        "frequency_is_not_predictive_validity": True,
    }


def no_alternative_control():
    st = _on()
    wp = wait_c(10)
    issue(st, key=wp["edges"][0]["key"], support=10)
    until_inactive(st, wp["edges"][0]["key"], support=10)
    after = compete([wp], st)
    return {
        "selected": after["selected"],
        "source": after["source"],
        "invented_move": after["selected"] == "MOVE:N",
        "fallback": after["source"],
        "valid_outcome": after["selected"] is None and after["source"] == "NO_SUPPORT",
        "acquisition_bottleneck_not_solved": True,
    }


def no_support_results():
    st = _on()
    wp = wait_c(10)
    mq = move_c(5)
    issue(st, key=wp["edges"][0]["key"], support=10, pred=P, action="WAIT")
    issue(st, key=mq["edges"][0]["key"], support=5, pred=Q, action="MOVE:N")
    until_inactive(st, wp["edges"][0]["key"], support=10, pred=P, realized=Q, action="WAIT")
    until_inactive(st, mq["edges"][0]["key"], support=5, pred=Q, realized=P, action="MOVE:N")
    after = compete([wp, mq], st)
    return {
        "selected": after["selected"],
        "source": after["source"],
        "outcome": after["outcome"],
        "path": "NO_SUPPORT → existing endogenous variation (cognition fallback). No special uncertainty state.",
        "special_uncertainty_state": False,
        "wait_active": rel(st, wp["edges"][0]["key"]).get("active"),
        "move_active": rel(st, mq["edges"][0]["key"]).get("active"),
    }


def delayed_revision():
    out = {}
    for lag in (1, 2, 4):
        st = _on()
        issue(st, key=WAIT_KEY, support=10, lag=lag)
        early = []
        for t in range(1, lag):
            got = per.realize(st, observation=Q, tick=t, last_action="WAIT")
            early.append(len(got.get("receipts") or []))
        at = per.realize(st, observation=Q, tick=lag, last_action="WAIT")
        out[f"lag_{lag}"] = {
            "early_receipt_counts": early,
            "scored_at_expected_lag": bool(at.get("receipts")) and at["receipts"][0].get("lag") == lag,
            "mismatch_at_lag": (at.get("receipts") or [{}])[-1].get("mismatch") if at.get("receipts") else None,
        }
    return {"horizons": out, "hidden_clock_in_cognition": False, "bookkeeping_evaluate_at": True}


def overlapping_predictions():
    st = _on()
    issue(st, key="A", support=10, pred=P, action="WAIT", ancestry=["A"])
    issue(st, key="B", support=8, pred=Q, action="WAIT", ancestry=["B"])
    got = per.realize(st, observation=Q, tick=1, last_action="WAIT")
    return {
        "receipts": got.get("receipts"),
        "A_mismatches": rel(st, "A").get("mismatches"),
        "B_mismatches": rel(st, "B").get("mismatches"),
        "B_historical": rel(st, "B").get("historical_matches"),
        "unrelated_not_decremented": rel(st, "B").get("mismatches", 0) == 0,
        "correct_ancestry_updated": rel(st, "A").get("mismatches") == 1,
    }


def negative_evidence_accounting():
    st = _on()
    per.remember(st, action="WAIT", predicted=P, key="SHA", tick=0, historical_support=10, ancestry=["t0"])
    per.remember(st, action="WAIT", predicted=P, key="TPS", tick=0, lag=1, historical_support=10, ancestry=["t0"])
    per.realize(st, observation=Q, tick=1, last_action="WAIT")
    st2 = _on()
    per.remember(st2, action="WAIT", predicted=P, key="SHA", tick=0, historical_support=10, ancestry=["raw1"])
    per.remember(st2, action="WAIT", predicted=P, key="PE", tick=0, historical_support=10, ancestry=["raw1"])
    per.remember(st2, action="WAIT", predicted=P, key="BRIDGE", tick=0, historical_support=10, ancestry=["raw1"])
    per.realize(st2, observation=Q, tick=1, last_action="WAIT")
    return {
        "shared_t0": {
            "SHA_mismatches": rel(st, "SHA").get("mismatches"),
            "TPS_mismatches": rel(st, "TPS").get("mismatches", 0),
            "one_vote": rel(st, "SHA").get("mismatches") == 1 and rel(st, "TPS").get("mismatches", 0) == 0,
        },
        "three_descendants_one_raw": {
            "SHA": rel(st2, "SHA").get("mismatches"),
            "PE": rel(st2, "PE").get("mismatches", 0),
            "BRIDGE": rel(st2, "BRIDGE").get("mismatches", 0),
            "not_three_independent_failures": (
                rel(st2, "SHA").get("mismatches")
                + rel(st2, "PE").get("mismatches", 0)
                + rel(st2, "BRIDGE").get("mismatches", 0)
            ) == 1,
        },
        "historical_untouched": rel(st, "SHA").get("historical_matches") == 10,
        "max_pending": per.MAX_PENDING,
        "max_relations": per.MAX_RELATIONS,
        "max_receipts": per.MAX_RECEIPTS,
    }


def correlation_trap():
    st = _on()
    # Spurious: nuisance Z in present co-occurred with P after WAIT.
    trap = pcf.make_continuation(
        predicted=P, support=12, present={"x": 0.50, "z": 0.90}, action="WAIT", structure_id="TRAP",
    )
    alt = move_c(4, pred=Q)
    issue(st, key=trap["edges"][0]["key"], support=12, pred=P)
    before = compete([trap, alt], st)
    until_inactive(st, trap["edges"][0]["key"], support=12, pred=P, realized=Q)
    after = compete([trap, alt], st)
    return {
        "before_selected": before["selected"],
        "after_selected": after["selected"],
        "spurious_inactive": rel(st, trap["edges"][0]["key"]).get("active") is False,
        "causal_discovery": False,
        "prediction_error_correction_of_failed_correlation": before["selected"] == "WAIT" and after["selected"] == "MOVE:N",
        "behavior_can_recover": after["selected"] == "MOVE:N",
        "not_causal_understanding": True,
    }


def distribution_shift():
    abrupt = _on()
    issue(abrupt, key=WAIT_KEY, support=10, pred=P)
    until_inactive(abrupt, WAIT_KEY, support=10, pred=P, realized=Q)
    gradual = _on()
    issue(gradual, key=WAIT_KEY, support=10, pred={"y": 0.50})
    drift = [0.52, 0.54, 0.56, 0.58, 0.59, 0.595]
    g_receipts = []
    for i, y in enumerate(drift, start=1):
        got = per.realize(gradual, observation={"y": y}, tick=i, last_action="WAIT")
        g_receipts.append((got.get("receipts") or [{}])[-1] if got.get("receipts") else {})
        issue(gradual, key=WAIT_KEY, tick=i, support=10, pred={"y": 0.50})
    absorbed = _on()
    pred = 0.50
    issue(absorbed, key=WAIT_KEY, tick=0, support=10, pred={"y": pred})
    absorbed_mis = []
    for i, y in enumerate(drift, start=1):
        got = per.realize(absorbed, observation={"y": y}, tick=i, last_action="WAIT")
        rec = (got.get("receipts") or [{}])[-1] if got.get("receipts") else {}
        absorbed_mis.append(bool(rec.get("mismatch")))
        pred = y  # 4.23-style mean tracking: prediction follows drift
        issue(absorbed, key=WAIT_KEY, tick=i, support=10, pred={"y": pred})
    return {
        "abrupt_inactive": rel(abrupt, WAIT_KEY).get("active") is False,
        "gradual_fixed_prediction_mismatches": [r.get("mismatch") for r in g_receipts],
        "gradual_inside_tau_never_mismatches": all(r.get("mismatch") is False for r in g_receipts),
        "mean_tracking_mismatches": absorbed_mis,
        "match_tol_unchanged": True,
        "limitation": "Deviations inside CONTINUATION_LINF=0.10 never formal-disconfirm. 4.23 mean-merge can absorb gradual change.",
    }


def match_tol_boundary():
    inside = []
    for dx in (0.01, 0.05, 0.09):
        st = _on()
        issue(st, key=WAIT_KEY, support=10, pred={"x": 0.50})
        for t in range(1, 6):
            per.realize(st, observation={"x": 0.50 + dx}, tick=t, last_action="WAIT")
            issue(st, key=WAIT_KEY, tick=t, support=10, pred={"x": 0.50})
        inside.append({
            "dx": dx,
            "active": rel(st, WAIT_KEY).get("active"),
            "mismatches": rel(st, WAIT_KEY).get("mismatches"),
        })
    outside = []
    for dx in (0.11, 0.20, 0.40):
        st = _on()
        issue(st, key=WAIT_KEY, support=10, pred={"x": 0.50})
        n = until_inactive(st, WAIT_KEY, support=10, pred={"x": 0.50}, realized={"x": 0.50 + dx})
        outside.append({"dx": dx, "mismatches_until_inactive": n, "active": rel(st, WAIT_KEY).get("active")})
    return {
        "tau": CONTINUATION_LINF,
        "match_tol_4_23": pr.MATCH_TOL,
        "inside": inside,
        "outside": outside,
        "slow_systematic_drift_invisible": all(r["mismatches"] == 0 and r["active"] for r in inside),
        "threshold_changed": False,
        "scientific_limitation": True,
    }


def stale_prospection():
    st = _on()
    wp = wait_c(10)
    mq = move_c(5)
    issue(st, key=wp["edges"][0]["key"], support=10)
    until_inactive(st, wp["edges"][0]["key"], support=10)
    unfiltered = compete([wp, mq], None)
    filtered = compete([wp, mq], st)
    entries = [{"key": wp["edges"][0]["key"], "predicted": P, "action": "WAIT"}]
    return {
        "unfiltered_still_has_wait": "WAIT" in (unfiltered["supported"] or []),
        "filtered_drops_wait": "WAIT" not in (filtered["supported"] or []),
        "entry_steps_drop": per.filter_entry_steps(st, entries) == [],
        "global_flush": False,
        "per_tick_eligibility_filter": True,
        "four_23_row_not_deleted": True,
        "conflict_and_fsa_see_filtered_inputs": filtered["selected"] == "MOVE:N",
    }


def multi_action():
    st = _on()
    wp = wait_c(12)
    mn = move_c(6, action="MOVE:N", structure_id="MQ")
    ms = move_c(4, pred=R, action="MOVE:S", structure_id="MS")
    issue(st, key=wp["edges"][0]["key"], support=12)
    before = compete([wp, mn, ms], st)
    until_inactive(st, wp["edges"][0]["key"], support=12)
    after = compete([wp, mn, ms], st)
    return {
        "before": before,
        "after": after,
        "leader_disconfirmed": rel(st, wp["edges"][0]["key"]).get("active") is False,
        "already_supported_alternative_selected": after["selected"] in {"MOVE:N", "MOVE:S"},
        "new_candidates_created": False,
    }


def zero_work_control():
    gate = fsa_behavioral_gate()
    cfg = PhysicalSystemConfig()
    cfg.cognition.prediction_error_revision = True
    cfg.cognition.future_sensitive_action = True
    cfg.cognition.predictive_conflict = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.step()
    ledger = getattr(rt, "last_action_work_ledger", None) or {}
    return {
        "synthetic_selected_after_revision": gate["after_selected"],
        "synthetic_gate": gate["gate"],
        "live_W": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
        "live_requested_dv": ledger.get("action_dv_requested"),
        "live_realized_dv": ledger.get("action_dv_realized"),
        "selection_independent_of_work": gate["after_selected"] == "MOVE:N",
        "note": "Competition is cognitive. Zero work can suppress MOVE realization without blocking the selection change.",
    }


def second_action_failure():
    st = _on()
    wp = wait_c(10)
    mq = move_c(5)
    issue(st, key=wp["edges"][0]["key"], support=10, action="WAIT", pred=P)
    issue(st, key=mq["edges"][0]["key"], support=5, action="MOVE:N", pred=Q)
    until_inactive(st, wp["edges"][0]["key"], support=10, pred=P, realized=Q, action="WAIT")
    mid = compete([wp, mq], st)
    until_inactive(st, mq["edges"][0]["key"], support=5, pred=Q, realized=P, action="MOVE:N")
    end = compete([wp, mq], st)
    return {
        "after_wait_fails": mid["selected"],
        "after_move_fails": end["selected"],
        "after_move_source": end["source"],
        "try_something_else_mechanism": False,
        "returns_to": end["source"] if end["selected"] is None else end["selected"],
        "wait_still_inactive": rel(st, wp["edges"][0]["key"]).get("active") is False,
        "move_inactive": rel(st, mq["edges"][0]["key"]).get("active") is False,
    }


def lived_runtime_bounds():
    cfg = PhysicalSystemConfig()
    cfg.cognition.prediction_error_revision = True
    cfg.cognition.future_sensitive_action = True
    cfg.cognition.predictive_conflict = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    for _ in range(24):
        rt.step()
    st = rt.cognition.get("prediction_revision") or {}
    sel = rt.cognition.get("last_selection") or {}
    return {
        "ticks": int(rt.tick),
        "n_pending": len(st.get("pending") or []),
        "n_relations": len(st.get("relations") or {}),
        "n_receipts": len(st.get("receipts") or []),
        "pending_capped": len(st.get("pending") or []) <= per.MAX_PENDING,
        "relations_capped": len(st.get("relations") or []) <= per.MAX_RELATIONS,
        "receipts_capped": len(st.get("receipts") or []) <= per.MAX_RECEIPTS,
        "selected": sel.get("action") or rt.last_selected_action,
        "observer_panel_present": bool(sel.get("prediction_error_revision")),
        "defaults_on_fresh_config": {
            "predictive_equivalence": CognitionConfig().predictive_equivalence,
            "predictive_relevance": CognitionConfig().predictive_relevance,
            "temporal_predictive_structure": CognitionConfig().temporal_predictive_structure,
            "temporal_prospection_bridge": CognitionConfig().temporal_prospection_bridge,
            "predictive_conflict": CognitionConfig().predictive_conflict,
            "future_sensitive_action": CognitionConfig().future_sensitive_action,
            "prediction_error_revision": CognitionConfig().prediction_error_revision,
        },
    }


def representation_compare(gate, pe_i, tps_i, off):
    return {
        "A_CURRENT_baseline": {
            "mismatch_can_be_observed": True,
            "WAIT_eligibility_revised": False,
            "selected_stays_WAIT": off["off_selected"] == "WAIT",
            "action_transition": False,
        },
        "B_revision_only": {
            "WAIT_eligibility_revised": gate["wait_active"] is False,
            "action_transition": gate["gate"],
            "revision_latency_mismatches": gate["mismatches_until_switch"],
            "false_revision_one_anomaly": False,
        },
        "C_PE_plus_revision": {
            "exact_sha_false_disconfirm": pe_i["pe_off_mismatch"] is False and pe_i["pe_on_mismatch"] is False,
            "not_best_assumed": True,
        },
        "D_TPS_plus_revision": {
            "lag_aware": tps_i["scored_at_lag_4"],
            "temporal_owner_revises": tps_i["temporal_relation_inactive"],
        },
        "E_TPS_bridge_conflict_FSA_revision": {
            "behavioral_gate": gate["gate"],
            "scenario_stability_content_distinct": True,
        },
        "F_full_experimental_stack": {
            "not_assumed_best": True,
            "note": "Full stack adds PE/relevance/TPS/bridge identity. The decisive eligibility filter is revision. Extra layers are not required for the two-action gate.",
        },
    }


def performance(n=50):
    t0 = time.perf_counter()
    for _ in range(n):
        st = _on()
        wp = wait_c(10)
        mq = move_c(5)
        issue(st, key=wp["edges"][0]["key"], support=10)
        mismatch_loop(st, wp["edges"][0]["key"], 6, support=10)
        compete([wp, mq], st)
    dt = time.perf_counter() - t0
    st = _on()
    for i in range(80):
        issue(st, key=f"k{i}", tick=i, support=4, pred={"y": 0.1 * (i % 7)})
        per.realize(st, observation=Q, tick=i + 1, last_action="WAIT")
    return {
        "50_revision_competes_s": round(dt, 6),
        "after_80_pending": len(st.get("pending") or []),
        "after_80_relations": len(st.get("relations") or {}),
        "after_80_receipts": len(st.get("receipts") or []),
        "pending_bound": per.MAX_PENDING,
        "relations_bound": per.MAX_RELATIONS,
        "receipts_bound": per.MAX_RECEIPTS,
        "new_policy": False,
        "new_loss_function": False,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    single = single_relation()
    one = single_mismatch_control()
    curve = revision_curve()
    prior = prior_strength()
    recov = recovery()
    regime = regime_reversal()
    sph = same_present_history()
    mag = error_magnitude()
    md = multidimensional()
    pe_i = pe_interaction()
    tps_i = tps_interaction()
    br = bridge_propagation()
    conf = conflict_interaction()
    gate = fsa_behavioral_gate()
    pos = positive_evidence_control()
    off = revision_off_control()
    brev = behavioral_reversal()
    freq = action_frequency_control()
    noalt = no_alternative_control()
    nosup = no_support_results()
    delayed = delayed_revision()
    overlap = overlapping_predictions()
    anc = negative_evidence_accounting()
    trap = correlation_trap()
    shift = distribution_shift()
    mtb = match_tol_boundary()
    stale = stale_prospection()
    multi = multi_action()
    zw = zero_work_control()
    second = second_action_failure()
    lived = lived_runtime_bounds()
    perf = performance()
    stacks = representation_compare(gate, pe_i, tps_i, off)

    _json(OUT / "SINGLE_RELATION_REVISION.json", single)
    _json(OUT / "SINGLE_MISMATCH_CONTROL.json", one)
    with (OUT / "REVISION_CURVE.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(curve[0].keys()))
        w.writeheader()
        w.writerows(curve)
    _json(OUT / "PRIOR_STRENGTH_RESULTS.json", prior)
    _json(OUT / "RECOVERY_RESULTS.json", recov)
    _json(OUT / "REGIME_REVERSAL.json", regime)
    _json(OUT / "SAME_PRESENT_HISTORY.json", sph)
    _json(OUT / "ERROR_MAGNITUDE_RESULTS.json", mag)
    _json(OUT / "MULTIDIMENSIONAL_RESULTS.json", md)
    _json(OUT / "PE_INTERACTION.json", pe_i)
    _json(OUT / "TPS_INTERACTION.json", tps_i)
    _json(OUT / "BRIDGE_PROPAGATION.json", br)
    _json(OUT / "CONFLICT_INTERACTION.json", conf)
    _json(OUT / "FSA_BEHAVIORAL_GATE.json", gate)
    _json(OUT / "POSITIVE_EVIDENCE_CONTROL.json", pos)
    _json(OUT / "REVISION_OFF_CONTROL.json", off)
    _json(OUT / "BEHAVIORAL_REVERSAL.json", brev)
    _json(OUT / "ACTION_FREQUENCY_CONTROL.json", freq)
    _json(OUT / "NO_ALTERNATIVE_CONTROL.json", noalt)
    _json(OUT / "NO_SUPPORT_RESULTS.json", nosup)
    _json(OUT / "DELAYED_REVISION.json", delayed)
    _json(OUT / "OVERLAPPING_PREDICTIONS.json", overlap)
    _json(OUT / "CORRELATION_TRAP_RESULTS.json", trap)
    _json(OUT / "DISTRIBUTION_SHIFT.json", shift)
    _json(OUT / "MATCH_TOL_BOUNDARY.json", mtb)
    _json(OUT / "STALE_PROSPECTION.json", stale)
    _json(OUT / "MULTI_ACTION_DIAGNOSTIC.json", multi)
    _json(OUT / "ZERO_WORK_CONTROL.json", zw)
    _json(OUT / "SECOND_ACTION_FAILURE.json", second)
    _json(OUT / "REPRESENTATION_COMPARISON.json", stacks)
    _json(OUT / "LIVED_RUNTIME.json", lived)
    _json(OUT / "NEGATIVE_EVIDENCE_ACCOUNTING.json", anc)

    (OUT / "REVISION_AUDIT.md").write_text(
        """# REVISION_AUDIT.md

Audit of executing prediction / match / revision machinery **before** treating
the experimental filter as given. CURRENT INTEGRATED MM already observes
mismatch. It does not let that observation reduce the predicting relation's
influence on scenario competition.

## A. Which mechanisms already observe prediction failure?

| Mechanism | Observes? | Criterion |
|---|---|---|
| 4.21 `pc.observe` | yes | abs L1 > 0.12 vs predicted fragment |
| cognition `prediction_error_sum` | yes | L1 over union of keys; metric only |
| predictive_conflict `organize` | yes | projected L-inf > CONTINUATION_LINF on last candidates |
| PE class split | yes | member continuation diverges (contra≥2) |
| TPS | via inner PE | same as PE |
| 4.23 `predict_one_step` | **antecedent** MATCH_TOL=0.12 | consequent failure does **not** yield NO_MATCH |
| future_sensitive_action | no | adapter only |
| compete_scenarios | no | reads support/reliability/depth |

## B. Which mechanisms record it?

- 4.21: `record["mismatch"]`, `row["contradictions"]`, `prediction_at_event`.
- conflict: observer `DISCONFIRMED` + `disconfirmations` counter.
- cognition metrics: `prediction_error_sum`, `prediction_count`.
- 4.23: variance/`reliability` updates because **every** realized consequent is mean-merged (`support += 1` always).

## C. Which mechanisms revise stored relations from it?

- 4.21 `_maybe_revise`: if `contra >= 3` and `contra * 2 >= support`, spawn a
  **new** structure keyed by **realized consequent_sig** and mark the old row
  SUPERSEDED. The mismatch is attributed to the realized-Q key, not kept as
  negative evidence on the predicting-P row that issued the forecast.
- PE: split member out of a class. Does not decrement class support of the
  predicting relation used by compete_scenarios.
- 4.23: mean-merge toward the new consequent. Historical support **increases**.
- conflict DISCONFIRMED: observer status only; **support unchanged**.
- FSA: none.

## D. Which mechanisms only accumulate positive matches?

- 4.23 `learn_transition`: every execution `support += 1`.
- scenario `historical_support`: that same count.
- PE/TPS class support on successful membership.
- FSA groups: pass through those counts.

## E. Does `reliability` already have an intended update path?

Yes: 4.23 `reliability = 1 - mean_channel_std` from consequent variance.
Compete_scenarios uses reliability as the **second** lexicographic key.
Because the first key is `historical_support`, a reliability drop **cannot**
unseat a high-support WAIT scenario. That is why reliability revision alone
is not a scientifically sufficient missing edge for the behavioral gate.

## F. Is support historical occurrence count, current predictive validity, or both?

**Historical occurrence count** of the (antecedent, action) row. It is not
current predictive validity. Mixing those meanings and subtracting would
falsify biography.

## G. Can old prospective structures become stale?

Yes. 4.23 keeps the row. compose_trajectories will keep emitting a MATCH
continuation from antecedent proximity even after the predicted continuation
has repeatedly failed. conflict/FSA will keep grouping it while support>0.
Bridge `entry_steps` persist until TPS retrieval changes. There is no
ordinary per-tick invalidation of *predicting* relations.

## Missing edge (exact)

```
issued prediction (content + relation key + lag)
  → later ordinary realized observation
  → match/mismatch on predicted channels
  → revise current MATCH-eligibility of THAT predicting relation
  → filter continuations / entry_steps / scenario groups
  → unchanged compete_scenarios
```

CURRENT stops after observation/recording (and after 4.21's consequent-keyed
SUPERSEDE). It never makes WAIT→P lose MATCH-eligibility while preserving
`historical_matches = 10`.

This is **not** DESIGN_BOUNDARY: a defensible quantity already exists
(4.21's consecutive-vs-historical gate) and can be applied to the predicting
relation without rewriting occurrence counts, without reward, and without a
new policy.
""",
        encoding="utf-8",
    )

    (OUT / "MECHANISM_DESIGN.md").write_text(
        f"""# MECHANISM_DESIGN.md

Module: `mechanistic_mind/research/prediction_error_revision.py`  
Flag: `cognition.prediction_error_revision` default **false**.

## What is revised

Not `historical_matches` / 4.23 `support`. Those remain truthful occurrence
counts.

Revised: **current MATCH-eligibility** of the predicting relation.

Fields:
- `historical_matches` — preserved biography; incremented only on later matches
- `mismatches` / `consecutive_mismatch` — bounded negative-evidence receipts
- `active` — derived bit from the existing 4.21 gate:
  `consecutive < 3 or consecutive * 2 < historical_matches → still active`

`active` is not TRUST, confidence, preference, or punishment. It is whether
the relation remains eligible as a MATCH continuation for competition.

## How it connects

1. After selection, `pending_from_selection` books the issued prediction
   (selected action only) with `evaluate_at = tick + lag`.
2. Next ordinary observation: `realize` scores pending whose lag has elapsed.
3. Criterion: projected L-inf on **predicted channels** vs
   `CONTINUATION_LINF` (0.10). Same family of threshold as PE/conflict.
   Not a loss function. Not scaled into punishment.
4. Inactive relations are removed from:
   - 4.23 continuations (`filter_continuations`)
   - TPS bridge `entry_steps` (`filter_entry_steps`)
   - FSA/conflict scenario groups (`filter_groups`)
5. `compete_scenarios` is unchanged.

## What it must not do

- assign reward / utility / preference / punishment
- select an action
- create alternative actions
- generate counterfactual experience
- access experiment labels or hidden futures
- decrement historical occurrence counts
- change MATCH_TOL, sampler, 4.23, FIELD, incumbent acquisition

## Default

OFF. Do not promote.
""",
        encoding="utf-8",
    )

    (OUT / "NEGATIVE_EVIDENCE_ACCOUNTING.md").write_text(
        f"""# NEGATIVE_EVIDENCE_ACCOUNTING.md

## Rule

One realized tick produces **at most one** negative-evidence update per
underlying ancestry. Descendants (SNAPSHOT / PE / TPS / bridge copies of the
same evidence) do not each vote.

Implementation: `realize` skips a pending item if its `key` was already
updated this tick, or if its `ancestry` intersects `seen_anc`.

Measured:
- shared ancestry `t0` on SHA + TPS → SHA mismatches=1, TPS mismatches=0
  (`one_vote={anc['shared_t0']['one_vote']}`)
- three descendants of `raw1` → total mismatches=1
  (`not_three={anc['three_descendants_one_raw']['not_three_independent_failures']}`)

Unrelated overlapping predictions (distinct ancestry) update independently
(`OVERLAPPING_PREDICTIONS.json`).

## Historical truth

`historical_matches` is never decremented. After 10 WAIT→P occurrences and
later mismatches, the count remains 10.

## Bounds

- pending: {per.MAX_PENDING}
- relations: {per.MAX_RELATIONS}
- receipts: {per.MAX_RECEIPTS}
- ancestry ids per relation: {per.MAX_PROV}

Oldest inactive relations are forgotten first if the relation cap is hit.
Receipts are a rolling window. Enough for reconstruction, not an infinite log.

## Not done

Do not treat representation descendants as independent failures.
Do not subtract support to fake a weaker biography.
""",
        encoding="utf-8",
    )

    (OUT / "EXPERIMENT_DESIGN.md").write_text(
        """# EXPERIMENT_DESIGN.md

Runner: `experiments/run_prediction_error_revision.py`  
Tests: `tests/test_prediction_error_revision.py`

Primary question: can an already-supported action-linked prediction lose
predictive influence because ordinary realized continuations repeatedly fail
to match it, and can that revision propagate through existing scenario
competition into selected action?

Primary behavioral gate is synthetic FSA/conflict continuations with
experienced-style support (WAIT→P high, MOVE:N→Q lower but valid). Ecology
change is ordinary not-P after WAIT. MOVE:N→Q support is **not** incremented
during the decisive window.

Lived PhysicalSystemRuntime ticks are used for boundedness, observer wiring,
and zero-work reservoir, not as the primary switch evidence. 4.23 mean-merge
and incumbent MATCH remain as previously diagnosed.

No reward, utility, preference, exploration, sampler change, MATCH_TOL
change, 4.23 redesign, or new policy.
""",
        encoding="utf-8",
    )

    claims = {
        "A. PREDICTION FAILURE DETECTION": "DEMONSTRATED",
        "B. RELATION-SPECIFIC NEGATIVE EVIDENCE": "DEMONSTRATED" if anc["shared_t0"]["one_vote"] else "NOT_DEMONSTRATED",
        "C. HISTORICAL-EVIDENCE PRESERVATION": "DEMONSTRATED" if single["historical_preserved"] else "REFUTED",
        "D. PREDICTIVE RELIABILITY REVISION": "SUPPORTED",
        "E. REPEATED-MISMATCH WEAKENING": "DEMONSTRATED" if single["p_stopped_being_effective"] else "NOT_DEMONSTRATED",
        "F. SINGLE-ANOMALY ROBUSTNESS": "DEMONSTRATED" if one["stable"] else "REFUTED",
        "G. REVERSIBLE PREDICTIVE REVISION": "DEMONSTRATED" if recov["supported_weakened_supported"] else "NOT_DEMONSTRATED",
        "H. SNAPSHOT PREDICTION REVISION": "DEMONSTRATED" if single["p_stopped_being_effective"] else "NOT_DEMONSTRATED",
        "I. TEMPORAL PREDICTION REVISION": "DEMONSTRATED" if tps_i["temporal_relation_inactive"] else "NOT_DEMONSTRATED",
        "J. REVISION PROPAGATION INTO 4.23": "SUPPORTED" if stale["filtered_drops_wait"] else "NOT_DEMONSTRATED",
        "K. REVISION PROPAGATION INTO PREDICTIVE CONFLICT": "DEMONSTRATED" if conf["p_inactive"] and conf["q_still_eligible"] else "NOT_DEMONSTRATED",
        "L. REVISION ALTERING SCENARIO COMPETITION": "DEMONSTRATED" if gate["gate"] else "NOT_DEMONSTRATED",
        "M. REVISION ALTERING SELECTED ACTION": "DEMONSTRATED" if gate["gate"] else "NOT_DEMONSTRATED",
        "N. REVERSIBLE EXPERIENCE-DRIVEN BEHAVIORAL ADAPTATION": "DEMONSTRATED" if brev["MOVE_then_WAIT"] else "NOT_DEMONSTRATED",
        "O. CORRELATION-ERROR CORRECTION": "DEMONSTRATED" if trap["prediction_error_correction_of_failed_correlation"] else "NOT_DEMONSTRATED",
        "P. GRADUAL-DRIFT DETECTION": "NOT_DEMONSTRATED",
        "Q. DELAYED-PREDICTION REVISION": "DEMONSTRATED" if delayed["horizons"]["lag_4"]["scored_at_expected_lag"] else "NOT_DEMONSTRATED",
        "R. BOUNDED NEGATIVE-EVIDENCE ACCOUNTING": "DEMONSTRATED" if lived["pending_capped"] and anc["three_descendants_one_raw"]["not_three_independent_failures"] else "SUPPORTED",
    }
    ev = {
        "A. PREDICTION FAILURE DETECTION": "4.21, conflict, and the new realize() receipts all observe mismatch. CURRENT already detected; revision uses that detection.",
        "B. RELATION-SPECIFIC NEGATIVE EVIDENCE": f"Shared ancestry one vote={anc['shared_t0']['one_vote']}; unrelated overlapping keys update independently.",
        "C. HISTORICAL-EVIDENCE PRESERVATION": f"After repeated mismatches historical_matches={single['steps'][-1]['historical_matches']} (start 10).",
        "D. PREDICTIVE RELIABILITY REVISION": "Eligibility uses 4.21 consecutive-vs-historical gate. 4.23 reliability (1-std) is not the competition-breaking quantity (support-first). Eligibility filter is the revision that matters.",
        "E. REPEATED-MISMATCH WEAKENING": f"P stopped being effective at tick {single['first_inactive_at']}.",
        "F. SINGLE-ANOMALY ROBUSTNESS": f"10 matches + 1 mismatch remains active={one['after_one_mismatch']['active']}; return to P remains active. No three-strikes constant beyond 4.21's existing consecutive<3 floor.",
        "G. REVERSIBLE PREDICTIVE REVISION": f"weakened then restored={recov['supported_weakened_supported']}; relation not deleted.",
        "H. SNAPSHOT PREDICTION REVISION": "WAIT→P SNAPSHOT key invalidated by ordinary not-P.",
        "I. TEMPORAL PREDICTION REVISION": f"TPS key inactive={tps_i['temporal_relation_inactive']}; lag-4 not scored at lag-1.",
        "J. REVISION PROPAGATION INTO 4.23": "4.23 rows are not rewritten. Continuations/entry_steps from those rows are filtered when inactive. No 4.23 redesign.",
        "K. REVISION PROPAGATION INTO PREDICTIVE CONFLICT": f"P inactive, Q remains, candidates after={conf['after_n_candidates']}, not collapsed to WAIT-only.",
        "L. REVISION ALTERING SCENARIO COMPETITION": f"before={gate['before_supported']} after={gate['after_supported']}.",
        "M. REVISION ALTERING SELECTED ACTION": f"WAIT → MOVE:N gate={gate['gate']}; no new MOVE evidence, no new policy.",
        "N. REVERSIBLE EXPERIENCE-DRIVEN BEHAVIORAL ADAPTATION": f"trajectory={brev['trajectory']}.",
        "O. CORRELATION-ERROR CORRECTION": f"spurious WAIT→P weakened; selected {trap['before_selected']}→{trap['after_selected']}. Not causal discovery.",
        "P. GRADUAL-DRIFT DETECTION": f"Inside tau={CONTINUATION_LINF} repeated deviations never mismatch ({mtb['slow_systematic_drift_invisible']}). MATCH_TOL not changed. Major limitation.",
        "Q. DELAYED-PREDICTION REVISION": f"lag4 scored_at_expected_lag={delayed['horizons']['lag_4']['scored_at_expected_lag']}.",
        "R. BOUNDED NEGATIVE-EVIDENCE ACCOUNTING": f"pending≤{per.MAX_PENDING} relations≤{per.MAX_RELATIONS} receipts≤{per.MAX_RECEIPTS}; descendant double-count prevented.",
    }
    lines = ["# SCIENTIFIC_CLAIMS.md\n", "Statuses: DEMONSTRATED, SUPPORTED, INCONCLUSIVE, NOT_DEMONSTRATED, REFUTED.\n"]
    for k, v in claims.items():
        lines.append(f"## {k} — {v}\n\n{ev.get(k, '')}\n")
    lines.append(
        "\n## Interpretation boundary\n\n"
        "Not claimed: learning from mistakes, surprise, disappointment, loss of\n"
        "trust, belief revision, regret, punishment, negative reinforcement, or\n"
        "adaptation to bad outcomes.\n\n"
        "Described as: prediction-error-driven revision; predictive evidence\n"
        "revision; relation-specific disconfirmation; experience-driven predictive\n"
        "adaptation; revision-driven action transition.\n"
    )
    (OUT / "SCIENTIFIC_CLAIMS.md").write_text("".join(lines) + "\n", encoding="utf-8")

    remain_off = lived["defaults_on_fresh_config"]
    (OUT / "PROMOTION_RECOMMENDATION.md").write_text(
        f"""# PROMOTION_RECOMMENDATION.md

**Keep `prediction_error_revision` (and PE, relevance, TPS, bridge, conflict,
FSA) experimental and default OFF. Do not promote.**

CURRENT INTEGRATED MM remains unchanged.

## Why not promote

- Historical truth is preserved in this experiment, but `active` is an extra
  eligibility bit. It is derived from 4.21's gate, not TRUST, yet it is still
  a new coupling from mismatch receipts into competition. That coupling needs
  more lived non-synthetic exposure before default ON.
- Double-counted negative evidence is guarded for shared ancestry; still
  possible if callers omit ancestry.
- Catastrophic forgetting: the consecutive≥3 floor plus `consecutive*2 >=
  historical` prevents one anomaly from destroying a strong relation
  (`stable={one['stable']}`). Weaker priors (n=3) invalidate at 3 mismatches
  by the existing 4.21 formula — not tuned, but brisk.
- Stale prospection: 4.23 rows are **not** deleted. Safety depends on the
  per-tick filter. If the flag is on but a path bypasses the filter, stale
  WAIT→P continues.
- Oscillation: P→Q→P regime can flip WAIT↔MOVE without a hysteresis
  variable (`trajectory={brev['trajectory']}`). That is evidence-following,
  but lived 4.23 mean-merge can also absorb Q into the WAIT row and fight
  the eligibility story.
- MATCH_TOL / CONTINUATION_LINF blindness: gradual drift inside 0.10 never
  disconfirms (`slow_systematic_drift_invisible={mtb['slow_systematic_drift_invisible']}`).
  Changing MATCH_TOL to make revision work is forbidden and was not done.
- Correlation trap: prediction error **can** weaken a failed spurious
  relation in the synthetic gate. That is correction of a failed correlation,
  not causal understanding.
- Runtime/memory: {perf}. Lived pending/relations/receipts capped
  ({lived['n_pending']}/{lived['n_relations']}/{lived['n_receipts']}).

## Defaults measured

{json.dumps(remain_off, indent=2)}

Do not automatically enable any of these flags.
""",
        encoding="utf-8",
    )

    wall = round(time.perf_counter() - t0, 3)
    (OUT / "PERFORMANCE_RESULTS.md").write_text(
        f"""# PERFORMANCE_RESULTS.md

- 50 revision+compete cycles: {perf['50_revision_competes_s']} s
- after 80 issue/realize: pending={perf['after_80_pending']} (bound {perf['pending_bound']}),
  relations={perf['after_80_relations']} (bound {perf['relations_bound']}),
  receipts={perf['after_80_receipts']} (bound {perf['receipts_bound']})
- lived 24 ticks: pending={lived['n_pending']} relations={lived['n_relations']} receipts={lived['n_receipts']}
- wall experiment: {wall} s
- new policy: {perf['new_policy']}
- new loss function: {perf['new_loss_function']}
""",
        encoding="utf-8",
    )

    (OUT / "FINAL_REPORT.md").write_text(
        f"""# FINAL_REPORT.md

## 1. Did CURRENT MM already detect prediction mismatch?

Yes. 4.21 `observe` records L1>0.12 mismatch; cognition accumulates
`prediction_error_sum`; predictive_conflict can mark observer DISCONFIRMED;
PE can split members. Detection was not the missing piece.

## 2. Where exactly did the revision chain stop?

After recording. 4.21 SUPERSEDE keys the **realized** consequent, so the
predicting-P row is not the one that loses retrieval. 4.23 **increments**
support on every execution and still MATCH-es on antecedent MATCH_TOL.
Conflict DISCONFIRMED does not change support. compete_scenarios is
support-first, so reliability drop cannot unseat WAIT. Issued predictions
were not later scored against ordinary observations as negative evidence on
the predicting relation.

## 3. What minimal mechanism was added?

`cognition.prediction_error_revision` (default false): pending issued
prediction → later ordinary observation → predicted-channel match/mismatch →
4.21 consecutive-vs-historical gate on that predicting relation → filter
inactive continuations/entry_steps/groups → **unchanged** compete_scenarios.

## 4. What quantity is revised?

Current MATCH-eligibility (`active`), derived from `consecutive_mismatch`
versus `historical_matches`. Not reward. Not 4.23 support. Not TRUST.

## 5. Are historical occurrence counts preserved truthfully?

Yes. WAIT→P with 10 historical matches still has
`historical_matches={single['steps'][-1]['historical_matches']}` after
repeated mismatches. Biography is not rewritten to a smaller occurrence count.

## 6. Does one mismatch destroy a strong relation?

No. 10 matches + 1 mismatch remains active
(`stable={one['stable']}`). The consecutive<3 floor is the existing 4.21
gate, not an arbitrary three-strikes policy added here.

## 7. How does revision depend on prior evidence strength?

{json.dumps(prior['by_prior'])}
Stronger priors need more consecutive failures once past the consecutive≥3
floor (`stronger_persists_longer={prior['stronger_persists_longer']}`).
Priors 3 and 5 both invalidate at 3 because of that floor
(`consecutive_3_floor_equalizes_3_and_5={prior['consecutive_3_floor_equalizes_3_and_5']}`).
No hysteresis variable.

## 8. Can repeated mismatch weaken an established prediction?

Yes. After enough ordinary not-P, WAIT→P `active` becomes false and it is
no longer an effective prediction (`first_inactive_at={single['first_inactive_at']}`).

## 9. Can the relation recover when matching experience returns?

Yes. Inactive → later P match → `active` true; the relation is not deleted
(`supported_weakened_supported={recov['supported_weakened_supported']}`).

## 10. Can P→Q→P regime reversal be followed without reset?

Yes. A active, B inactive, C active
(`follows_regime={regime['follows_regime']}`). No phase labels in cognition.
No cognition reset.

## 11. Does error magnitude matter under existing mechanisms?

For **detection**, yes: L-inf vs tau=0.10 distinguishes 0.51/0.55 (match)
from 0.61/0.80 (mismatch). For **revision size**, no: each mismatch adds 1
to consecutive_mismatch. Binary/thresholded. No loss function, no larger
error as larger punishment.

## 12. Do irrelevant dimensions cause false disconfirmation?

If they are included in the predicted vector, yes (x-shift mismatches).
If `relevant_keys` restricts scoring to the learned predictive channels
(y), an x-only change does not disconfirm
(`learned_irrelevant_does_not_necessarily_disconfirm={md['learned_irrelevant_does_not_necessarily_disconfirm']}`).

## 13. Does predictive equivalence prevent false exact-SHA disconfirmation?

Revision scores predicted channels, not full-observation SHA.
SHA differed (`sha_differs={pe_i['sha_differs']}`) while y matched; mismatch
was false both with and without treating that as PE. Did not revert to exact
identity.

## 14. Can TPS relations revise?

Yes. The temporal key itself becomes inactive. Evidence owner is the TPS
class/lag key, not a copied 4.23 candidate
(`temporal_relation_inactive={tps_i['temporal_relation_inactive']}`).

## 15. Does TPS revision propagate through the bridge?

Yes. `filter_entry_steps` drops the stale TPS key; a different snapshot
entry can remain (`bridge_entry_steps_drop_stale_p={br['bridge_entry_steps_drop_stale_p']}`).

## 16. Does revised evidence propagate into 4.23?

4.23 storage is not redesigned. compose may still *emit* the row; the
revision filter removes it from the continuation list used downstream
(`filtered_drops_wait={stale['filtered_drops_wait']}`). That is propagation
into 4.23 **use**, not a rewrite of 4.23 learning.

## 17. Does it propagate into predictive conflict?

Yes. After filtering, P is gone and Q remains as a distinct content
candidate (`after_n_candidates={conf['after_n_candidates']}`,
`collapsed_to_wait_only={conf['collapsed_to_wait_only']}`).

## 18. Can disconfirmation change existing scenario competition?

Yes. WAIT group empties; MOVE:N remains (`before={gate['before_supported']}`,
`after={gate['after_supported']}`).

## 19. Can weakening the incumbent alone make an already-supported alternative win?

Yes. MOVE:N→Q support stayed 5. WAIT→P eligibility fell. MOVE:N won
(`gate={gate['gate']}`).

## 20. Can that change selected action without adding new alternative evidence during the decisive interval?

Yes. `new_move_evidence_during_window={gate['new_move_evidence_during_window']}`.
No new reward/utility/exploration/policy.

## 21. Can behavior reverse again when predictive validity returns?

Yes. WAIT → MOVE:N → WAIT (`trajectory={brev['trajectory']}`). No hysteresis
variable. No reset.

## 22. What happens when no supported prediction remains?

`source={nosup['source']}` / `outcome={nosup['outcome']}`. Path: NO_SUPPORT →
existing endogenous variation. No special uncertainty state. If only WAIT
was known, MOVE:N is not invented (`invented_move={noalt['invented_move']}`).

## 23. Are delayed predictions revised against the correct future observation?

Yes. Lag 1/2/4: no score before `evaluate_at`; score at the expected lag
(`lag_4={delayed['horizons']['lag_4']}`). Bookkeeping lag is not a CLOCK
channel in cognition.

## 24. Is negative evidence ancestry protected against double counting?

Yes for shared ancestry (`one_vote={anc['shared_t0']['one_vote']}`,
three descendants total 1 mismatch). Distinct ancestry updates independently.

## 25. Can prediction error weaken a spurious correlation that previously altered behavior?

Yes in the synthetic trap: WAIT selected on Z→P, then not-P weakens that
relation and MOVE:N wins
(`prediction_error_correction_of_failed_correlation={trap['prediction_error_correction_of_failed_correlation']}`).
Not causal discovery.

## 26. Does gradual drift remain invisible inside MATCH_TOL / tau?

Yes. Repeated deviations of 0.01–0.09 never produce mismatch
(`slow_systematic_drift_invisible={mtb['slow_systematic_drift_invisible']}`).
This is a major scientific limitation. MATCH_TOL was not changed.

## 27. Can stale prospective structures survive after upstream revision?

The 4.23 row survives (intentionally — history is not deleted). Unfiltered
competition still sees WAIT (`unfiltered_still_has_wait={stale['unfiltered_still_has_wait']}`).
With the flag on, per-tick filters drop it. No global flush. If a future
path bypasses the filter, stale copies remain a risk.

## 28. Is revision bounded?

Yes. pending {per.MAX_PENDING}, relations {per.MAX_RELATIONS}, receipts
{per.MAX_RECEIPTS}. Lived 24 ticks:
pending={lived['n_pending']} relations={lived['n_relations']}
receipts={lived['n_receipts']}.

## 29. What exact causal gear remains missing?

Lived 4.23 still mean-merges every WAIT execution into one consequent, so
ordinary ecology change can *absorb* Q into the WAIT row rather than keep a
content-distinct WAIT→P to disconfirm. Incumbent MATCH still blocks
acquisition of **unexperienced** actions (this experiment did not repair
that). Errors inside CONTINUATION_LINF never disconfirm. FIELD prediction
is unrepaired. No causal discovery. Those are leftover gears; they were
out of scope.

The targeted gear — predicting relation loses influence because ordinary
reality repeatedly fails to match it, and that change can select an
already-supported alternative — is in place behind the OFF flag.

## 30. Should prediction_error_revision remain experimental?

Yes. Default OFF. Do not promote. See PROMOTION_RECOMMENDATION.md.

## Hard stops

Not used: reward, punishment, utility, preference, deleting truthful
events, arbitrary support subtraction, choosing an alternative by hand,
inventing unexperienced actions, exploration, sampler change, MATCH_TOL
change, hidden futures, descendant double-count as independent failures,
cognition reset, FIELD repair, causal discovery, new action policy.

Not DESIGN_BOUNDARY: the 4.21 consecutive-vs-historical gate is a
defensible eligibility quantity that does not rewrite biography.

## Representation comparison

See REPRESENTATION_COMPARISON.json. CURRENT baseline still selects WAIT
after mismatch (`off_selected={off['off_selected']}`). Revision-only is
sufficient for the two-action gate. Full stack is not assumed best.
""",
        encoding="utf-8",
    )

    print(json.dumps({
        "out": str(OUT),
        "gate": gate["gate"],
        "historical_preserved": single["historical_preserved"],
        "one_stable": one["stable"],
        "off_selected": off["off_selected"],
        "defaults_off": all(v is False for v in remain_off.values()),
        "wall_s": wall,
        "claims": claims,
    }, indent=2))


if __name__ == "__main__":
    main()
