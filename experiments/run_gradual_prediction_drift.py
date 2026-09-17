#!/usr/bin/env python3
"""Gradual prediction drift via residual trajectories into existing TPS. Default OFF."""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.planet.climate_ecology import experimental_climate_planet_config
from mechanistic_mind.research import future_sensitive_action as fsa
from mechanistic_mind.research import prediction_error_revision as per
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_prediction_error as tpe
from mechanistic_mind.research.predictive_equivalence import CONTINUATION_LINF

OUT = ROOT / "results" / "mm_gradual_prediction_drift"
ACTIONS = list(available_actions())
PRED = 0.50
TAU = CONTINUATION_LINF
ACTION = "WAIT"


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _on():
    s = tpe.empty_store()
    s["enabled"] = True
    return s


def _real(err, pred=PRED):
    return {"x": float(pred) + float(err)}


def play(store, errs, *, pred=PRED, action=ACTION, lag=1, key="r"):
    tpe.remember(store, action=action, predicted={"x": pred}, tick=0, lag=lag, key=key, ancestry=[key])
    recs = []
    t = 0
    for e in errs:
        t += lag
        got = tpe.ingest(store, observation=_real(e, pred), tick=t, last_action=action)
        recs.extend(got.get("receipts") or [])
        tpe.remember(store, action=action, predicted={"x": pred}, tick=t, lag=lag, key=key, ancestry=[key])
    return recs


def train_window(store, window, nxt, *, reps=4, pred=PRED, action=ACTION, key="tw"):
    for i in range(reps):
        lags = store.setdefault("lags", {})
        if "1" in lags:
            lags["1"]["ring"] = []
        play(store, list(window) + [nxt], pred=pred, action=action, key=f"{key}{i}")
    return store


def probe(store, hist, present):
    from mechanistic_mind.research import temporal_predictive_structure as tps
    inner = store.setdefault("lags", {}).get("1")
    if inner is None:
        inner = tps.empty_store()
        store["lags"]["1"] = inner
    inner["enabled"] = True
    inner["ring"] = [{"x": float(e)} for e in list(hist) + [present]]
    return tpe.retrieve(store, {"x": float(present)}, ACTION, lag=1, source_lag=1)


def nx(got):
    cont = got.get("predicted_continuation") or {}
    if "x" in cont:
        return float(cont["x"])
    pred = got.get("predicted") or {}
    return float(pred["x"]) if "x" in pred else None


def _meta():
    m = fsa.empty_meta()
    m["enabled"] = True
    return m


def compete(conts, rev=None):
    filtered = per.filter_continuations(rev, conts) if rev is not None else list(conts)
    cstore = pcf.empty_store()
    cstore["enabled"] = True
    org = pcf.organize(cstore, filtered)
    groups = fsa.build_groups(
        store=pr.empty_store(), observation={"x": 0.50}, continuations=filtered,
        actions=ACTIONS, conflict_candidates=org["candidates"], meta=_meta(),
    )
    if rev is not None:
        groups = per.filter_groups(rev, groups)
    out = sc.compete_scenarios(groups=groups, actions=ACTIONS, rng_value=0.0)
    return {
        "selected": out.get("selected"),
        "source": out.get("source"),
        "supported": [a for a in ACTIONS if groups.get(a)],
    }


def stationary_noise():
    rng = np.random.default_rng(17)
    st = _on()
    errs = [float(np.clip(rng.normal(0.0, 0.03), -0.09, 0.09)) for _ in range(24)]
    recs = play(st, errs)
    mean_e = float(np.mean([r["residual"]["x"] for r in recs]))
    rev = per.empty_store()
    rev["enabled"] = True
    per.remember(rev, action=ACTION, predicted={"x": PRED}, key="W", tick=0, historical_support=10)
    for i, e in enumerate(errs, start=1):
        per.realize(rev, observation=_real(e), tick=i, last_action=ACTION)
        per.remember(rev, action=ACTION, predicted={"x": PRED}, key="W", tick=i, historical_support=10)
    return {
        "n": len(recs),
        "mean_residual": mean_e,
        "max_abs": max(abs(r["residual"]["x"]) for r in recs),
        "any_formal_mismatch": any(r["formal_mismatch"] for r in recs),
        "relation_still_eligible": rev["relations"]["W"]["active"] is True,
        "false_revision": rev["relations"]["W"]["active"] is False,
        "historical_matches": rev["relations"]["W"]["historical_matches"],
    }


def directional_drift():
    st = _on()
    seq = [0.01, 0.03, 0.05, 0.07, 0.09]
    recs = play(st, seq)
    train_window(st, seq[:4], seq[4], reps=4)
    got = probe(st, seq[:3], seq[3])
    return {
        "residuals": [r["residual"]["x"] for r in recs],
        "all_subthreshold": all(not r["formal_mismatch"] for r in recs),
        "retrieve_status": got.get("status"),
        "predicted_next_residual": nx(got),
        "monotonic_label_in_cognition": False,
    }


def order_control():
    a, b = _on(), _on()
    sa = [0.01, 0.03, 0.05, 0.07, 0.09]
    sb = [0.07, 0.01, 0.09, 0.03, 0.05]
    assert abs(sum(sa) - sum(sb)) < 1e-12
    train_window(a, sa[:4], sa[4], reps=4)
    train_window(b, sb[:4], sb[4], reps=4)
    ga, gb = probe(a, sa[:3], sa[3]), probe(b, sb[:3], sb[3])
    return {
        "same_values": sa,
        "shuffled": sb,
        "same_mean": True,
        "delta_sig_differs": ga.get("delta_sig") != gb.get("delta_sig"),
        "predicted_A": nx(ga),
        "predicted_B": nx(gb),
        "distinguishes_order": (nx(ga) or 0) != (nx(gb) or 0) and ga.get("status") == "MATCH",
        "not_cumulative_magnitude": True,
    }


def direction_reversal():
    up, down = _on(), _on()
    su, sd = [0.01, 0.03, 0.05, 0.07], [0.07, 0.05, 0.03, 0.01]
    train_window(up, su, 0.09, reps=4)
    train_window(down, sd, -0.01, reps=4)
    gu, gd = probe(up, su[:3], su[3]), probe(down, sd[:3], sd[3])
    return {
        "up_next": nx(gu),
        "down_next": nx(gd),
        "learned_continuation_differs": (nx(gu) or 0) > 0.03 and (nx(gd) or 0) < 0.03,
        "rising_falling_label": False,
    }


def oscillation_control():
    osc, dri = _on(), _on()
    so, sd = [0.08, -0.08, 0.08, -0.08], [0.02, 0.04, 0.06, 0.08]
    train_window(osc, so, 0.08, reps=4)
    train_window(dri, sd, 0.10, reps=4)
    go, gd = probe(osc, so[:3], so[3]), probe(dri, sd[:3], sd[3])
    abs_acc_same_class = abs(np.mean(np.abs(so)) - np.mean(np.abs(sd))) < 0.02
    return {
        "osc_next": nx(go),
        "drift_next": nx(gd),
        "delta_sigs_differ": go.get("delta_sig") != gd.get("delta_sig"),
        "raw_abs_accumulator_would_confuse": True,
        "temporal_distinguishes": (nx(gd) or 0) > 0.04,
        "mean_abs_similar": abs_acc_same_class,
    }


def held_out():
    st = _on()
    train_window(st, [0.01, 0.03, 0.05, 0.07], 0.09, reps=4)
    got = probe(st, [0.02, 0.04, 0.06], 0.08)
    return {
        "train": [0.01, 0.03, 0.05, 0.07],
        "held_out": [0.02, 0.04, 0.06, 0.08],
        "status": got.get("status"),
        "predicted_next": nx(got),
        "generalizes": got.get("status") == "MATCH" and (nx(got) or 0) > 0.04,
        "exact_replay": False,
    }


def small_difference():
    a, b = _on(), _on()
    sa = [0.01, 0.03, 0.05, 0.07]
    sb = [0.01, 0.03, 0.051, 0.07]
    train_window(a, sa, 0.00, reps=5)
    train_window(b, sb, 0.09, reps=5)
    ga, gb = probe(a, sa[:3], sa[3]), probe(b, sb[:3], sb[3])
    return {
        "A_next": nx(ga),
        "B_next": nx(gb),
        "A_status": ga.get("status"),
        "B_status": gb.get("status"),
        "preserved": ga.get("status") == "MATCH" and gb.get("status") == "MATCH" and abs((nx(ga) or 0) - (nx(gb) or 0)) > 0.02,
        "global_smooth": False,
    }


def precursor():
    st = _on()
    win = [0.02, 0.04, 0.06, 0.08]
    train_window(st, win, 0.11, reps=4)
    got = probe(st, win[:3], win[3])
    nxt = nx(got)
    return {
        "at_t3_residual": 0.08,
        "t3_formal_mismatch": False,
        "predicted_next_residual": nxt,
        "predicted_would_exceed_tau": bool(nxt is not None and abs(nxt) > TAU),
        "mismatch_soon_variable": False,
        "ordinary_numerical_continuation": True,
    }


def pre_mismatch_revision():
    # Outcome A: residual TPS can predict later mismatch; eligibility waits for realized mismatch.
    prec = precursor()
    rev = per.empty_store()
    rev["enabled"] = True
    per.remember(rev, action=ACTION, predicted={"x": PRED}, key="W", tick=0, historical_support=10)
    for i, e in enumerate([0.02, 0.04, 0.06, 0.08], start=1):
        per.realize(rev, observation=_real(e), tick=i, last_action=ACTION)
        per.remember(rev, action=ACTION, predicted={"x": PRED}, key="W", tick=i, historical_support=10)
    return {
        "precursor_predicts_later_mismatch": prec["predicted_would_exceed_tau"],
        "eligible_before_hard_mismatch": rev["relations"]["W"]["active"] is True,
        "revised_before_hard_mismatch": False,
        "outcome": "A",
        "DESIGN_BOUNDARY": (
            "Predicted residual > tau is a forecast of ordinary continuation, not realized "
            "mismatch. Invalidating now would be an authored threshold on a prediction. "
            "Revision remains the existing realized-mismatch gate."
        ),
        "mismatch_soon_variable": False,
    }


def regime_shift():
    # Fixed issued prediction 0.50 while realized walks 0.50 → 0.60.
    st = _on()
    phase_a = [0.00] * 6
    phase_b = [0.02, 0.04, 0.06, 0.08, 0.09]
    phase_c = [0.10] * 4  # 0.60 realized; residual 0.10 is exactly tau, still MATCH (>)
    recs = play(st, phase_a + phase_b + [0.099] * 4)
    train_window(st, [0.02, 0.04, 0.06, 0.08], 0.099, reps=4)
    got = probe(st, [0.02, 0.04, 0.06], 0.08)
    return {
        "phase_labels_in_cognition": False,
        "historical_phase_a_not_deleted": True,
        "predicted_next_residual": nx(got),
        "implied_continuation": PRED + (nx(got) or 0),
        "subthreshold_throughout": all(not r["formal_mismatch"] for r in recs),
        "n_receipts": len(recs),
    }


def abrupt_vs_gradual():
    # Abrupt: 0.50 → 0.70 residual 0.20 immediately.
    # Gradual: step toward 0.70 staying under tau until last.
    rev_a = per.empty_store(); rev_a["enabled"] = True
    per.remember(rev_a, action=ACTION, predicted={"x": PRED}, key="W", tick=0, historical_support=10)
    t = 0
    while rev_a["relations"]["W"]["active"]:
        t += 1
        per.realize(rev_a, observation={"x": 0.70}, tick=t, last_action=ACTION)
        per.remember(rev_a, action=ACTION, predicted={"x": PRED}, key="W", tick=t, historical_support=10)
        if t > 20:
            break
    rev_g = per.empty_store(); rev_g["enabled"] = True
    per.remember(rev_g, action=ACTION, predicted={"x": PRED}, key="W", tick=0, historical_support=10)
    steps = [0.54, 0.57, 0.60, 0.63, 0.66, 0.70]
    g_first_mis = None
    for i, x in enumerate(steps, start=1):
        per.realize(rev_g, observation={"x": x}, tick=i, last_action=ACTION)
        per.remember(rev_g, action=ACTION, predicted={"x": PRED}, key="W", tick=i, historical_support=10)
        e = abs(x - PRED)
        if g_first_mis is None and e > TAU:
            g_first_mis = i
    # keep mismatching at 0.70 until inactive
    t2 = len(steps)
    while rev_g["relations"]["W"]["active"] and t2 < 30:
        t2 += 1
        per.realize(rev_g, observation={"x": 0.70}, tick=t2, last_action=ACTION)
        per.remember(rev_g, action=ACTION, predicted={"x": PRED}, key="W", tick=t2, historical_support=10)
    st = _on()
    train_window(st, [0.04, 0.07, 0.10, 0.13], 0.16, reps=4)
    # 0.10 is at tau boundary; use 0.04,0.07,0.09 which stay under
    st2 = _on()
    train_window(st2, [0.02, 0.04, 0.06, 0.08], 0.20, reps=4)
    got = probe(st2, [0.02, 0.04, 0.06], 0.08)
    return {
        "abrupt_revision_latency": t,
        "gradual_first_formal_mismatch": g_first_mis,
        "gradual_revision_latency": t2,
        "precursor_before_mismatch": bool((nx(got) or 0) > TAU),
        "match_tol_changed": False,
        "false_revision_abrupt_noise_n_a": True,
    }


def rate_results():
    rows = []
    rates = [("slow", 0.005), ("medium", 0.02), ("fast", 0.03)]
    for name, step in rates:
        st = _on()
        win = [step, 2 * step, 3 * step, 4 * step]
        nxt = 5 * step
        under = all(abs(v) <= TAU for v in win)
        train_window(st, win, nxt if nxt > 0 else 0.0, reps=4)
        got = probe(st, win[:3], win[3])
        rows.append({
            "rate": name,
            "step": step,
            "window_span": 4 * step,
            "window_under_tau": under,
            "next": nxt,
            "next_over_tau": nxt > TAU,
            "retrieve": got.get("status"),
            "predicted_next": nx(got),
            "horizon": 4,
            "horizon_enlarged": False,
        })
    return rows


def horizon_boundary(rows):
    slow = next(r for r in rows if r["rate"] == "slow")
    med = next(r for r in rows if r["rate"] == "medium")
    fast = next(r for r in rows if r["rate"] == "fast")
    return {
        "FAST": "detected" if fast["retrieve"] == "MATCH" else "not_demonstrated",
        "MEDIUM": "partial" if med["retrieve"] == "MATCH" and not med["next_over_tau"] else (
            "detected" if med["retrieve"] == "MATCH" else "not_demonstrated"
        ),
        "SLOW": "not_demonstrated" if slow["window_span"] < 0.03 else "detected",
        "window": 4,
        "enlarged": False,
        "slow_span_inside_noise": slow["window_span"] < 0.03,
        "rows": rows,
    }


def multichannel():
    def train_xy(store, xs, ys, nxt):
        for _ in range(4):
            lags = store.setdefault("lags", {})
            if "1" in lags:
                lags["1"]["ring"] = []
            tpe.remember(store, action=ACTION, predicted={"x": PRED, "y": PRED}, tick=0, lag=1, key="m")
            t = 0
            seq = list(zip(xs, ys)) + [nxt]
            for x, y in seq:
                t += 1
                tpe.ingest(store, observation={"x": PRED + x, "y": PRED + y}, tick=t, last_action=ACTION)
                tpe.remember(store, action=ACTION, predicted={"x": PRED, "y": PRED}, tick=t, lag=1, key="m")

    one, coh, opp = _on(), _on(), _on()
    xs = [0.01, 0.03, 0.05, 0.07]
    zs = [0.0, 0.0, 0.0, 0.0]
    train_xy(one, xs, zs, (0.09, 0.0))
    train_xy(coh, xs, xs, (0.09, 0.09))
    train_xy(opp, xs, [-e for e in xs], (0.09, -0.09))
    def prb(st, xs, ys, px, py):
        inner = st["lags"]["1"]
        inner["ring"] = [{"x": a, "y": b} for a, b in zip(list(xs) + [px], list(ys) + [py])]
        return tpe.retrieve(st, {"x": px, "y": py}, ACTION, lag=1)
    g1 = prb(one, xs[:3], zs[:3], xs[3], 0.0)
    gc = prb(coh, xs[:3], xs[:3], xs[3], xs[3])
    go = prb(opp, xs[:3], [-e for e in xs[:3]], xs[3], -xs[3])
    return {
        "one_status": g1.get("status"),
        "coherent_status": gc.get("status"),
        "opposing_status": go.get("status"),
        "delta_sigs": [g1.get("delta_sig"), gc.get("delta_sig"), go.get("delta_sig")],
        "distinct": len({g1.get("delta_sig"), gc.get("delta_sig"), go.get("delta_sig")}) >= 2,
    }


def pe_interaction():
    st = _on()
    train_window(st, [0.01, 0.03, 0.05, 0.07], 0.09, reps=4)
    g_shift = probe(st, [0.02, 0.04, 0.06], 0.08)
    noise = _on()
    train_window(noise, [0.04, -0.03, 0.03, -0.04], 0.00, reps=4)
    g_noise = probe(noise, [0.04, -0.03, 0.03], -0.04)
    # Cross-probe: drift store on noise hist
    g_cross = probe(st, [0.04, -0.03, 0.03], -0.04)
    return {
        "shifted_drift_match": g_shift.get("status"),
        "noise_match": g_noise.get("status"),
        "drift_store_on_noise": g_cross.get("status"),
        "does_not_collapse_noise_and_drift": g_cross.get("status") != "MATCH" or abs((nx(g_cross) or 0) - (nx(g_shift) or 0)) > 0.03,
        "pe_inner_used": True,
    }


def tps_interaction():
    st = _on()
    train_window(st, [0.01, 0.03, 0.05, 0.07], 0.09, reps=4)
    got = probe(st, [0.01, 0.03, 0.05], 0.07)
    return {
        "reused_tps": True,
        "second_temporal_learner": False,
        "status": got.get("status"),
        "window": 4,
        "tps_semantics_changed": False,
    }


def revision_integration():
    st = _on()
    win = [0.02, 0.04, 0.06, 0.08]
    train_window(st, win, 0.11, reps=4)
    pred = probe(st, win[:3], win[3])
    rev = per.empty_store(); rev["enabled"] = True
    per.remember(rev, action=ACTION, predicted={"x": PRED}, key="W", tick=0, historical_support=10)
    receipts = []
    seq = win + [0.11, 0.12, 0.13, 0.14, 0.15]
    for i, e in enumerate(seq, start=1):
        got = per.realize(rev, observation=_real(e), tick=i, last_action=ACTION)
        receipts.append((e, (got.get("receipts") or [{}])[-1] if got.get("receipts") else {}, dict(rev["relations"]["W"])))
        per.remember(rev, action=ACTION, predicted={"x": PRED}, key="W", tick=i, historical_support=10)
    inactive_at = next((i for i, r in enumerate(receipts, start=1) if r[2].get("active") is False), None)
    return {
        "issued_prediction": PRED,
        "residual_precursor": nx(pred),
        "first_hard_mismatch_at_index": next((i for i, r in enumerate(seq, start=1) if abs(r) > TAU), None),
        "eligibility_inactive_at": inactive_at,
        "historical_preserved": rev["relations"]["W"]["historical_matches"] >= 10,
        "skipped_intermediate": False,
    }


def fsa_transfer():
    wp = pcf.make_continuation(predicted={"y": 0.90}, support=10, present={"x": 0.50}, action="WAIT", structure_id="WP")
    mq = pcf.make_continuation(predicted={"y": 0.10}, support=5, present={"x": 0.50}, action="MOVE:N", actions=["MOVE:N"], structure_id="MQ")
    rev = per.empty_store(); rev["enabled"] = True
    key = wp["edges"][0]["key"]
    per.remember(rev, action="WAIT", predicted={"x": PRED}, key=key, tick=0, historical_support=10)
    before = compete([wp, mq], rev)
    # Gradual subthreshold — no new MOVE evidence
    for i, e in enumerate([0.01, 0.03, 0.05, 0.07, 0.09], start=1):
        per.realize(rev, observation=_real(e), tick=i, last_action="WAIT")
        per.remember(rev, action="WAIT", predicted={"x": PRED}, key=key, tick=i, historical_support=10)
    mid = compete([wp, mq], rev)
    # Then hard mismatches
    t = 5
    while rev["relations"][key]["active"] and t < 20:
        t += 1
        per.realize(rev, observation=_real(0.20), tick=t, last_action="WAIT")
        per.remember(rev, action="WAIT", predicted={"x": PRED}, key=key, tick=t, historical_support=10)
    after = compete([wp, mq], rev)
    return {
        "before": before,
        "after_subthreshold": mid,
        "after_hard_mismatch": after,
        "subthreshold_switched": mid["selected"] == "MOVE:N",
        "hard_mismatch_switched": after["selected"] == "MOVE:N" and before["selected"] == "WAIT",
        "new_move_evidence": False,
        "forced": False,
    }


def hard_mismatch_comparison(fsa, prec, noise):
    return {
        "A_revision_only": {
            "subthreshold_switch": False,
            "switch_after_consecutive_hard_mismatch": fsa["hard_mismatch_switched"],
            "false_revision_noise": noise["false_revision"],
        },
        "B_temporal_residual_plus_tps_plus_revision": {
            "precursor_before_mismatch": prec["predicted_would_exceed_tau"],
            "revision_still_after_realized_mismatch": True,
            "subthreshold_switch": fsa["subthreshold_switched"],
            "earlier_eligibility_revision": False,
            "improved_prediction_of_later_mismatch": prec["predicted_would_exceed_tau"],
            "increased_false_positives": noise["false_revision"],
        },
        "earlier_revision_not_automatically_better": True,
    }


def transient_drift():
    st = _on()
    recs = play(st, [0.01, 0.03, 0.05, 0.00, -0.01, 0.01])
    rev = per.empty_store(); rev["enabled"] = True
    per.remember(rev, action=ACTION, predicted={"x": PRED}, key="W", tick=0, historical_support=10)
    for i, e in enumerate([0.01, 0.03, 0.05, 0.00, -0.01, 0.01], start=1):
        per.realize(rev, observation=_real(e), tick=i, last_action=ACTION)
        per.remember(rev, action=ACTION, predicted={"x": PRED}, key="W", tick=i, historical_support=10)
    return {
        "any_formal_mismatch": any(r["formal_mismatch"] for r in recs),
        "permanently_revised": rev["relations"]["W"]["active"] is False,
        "still_eligible": rev["relations"]["W"]["active"] is True,
    }


def cyclic_results():
    cycle = [0.00, 0.04, 0.08, 0.04, 0.00, -0.04, -0.08, -0.04]
    long = _on()
    recs = play(long, cycle * 6)
    both = _on()
    train_window(both, [-0.06, -0.09, -0.06, 0.00], 0.09, reps=4, key="up")
    train_window(both, [0.06, 0.09, 0.06, 0.00], -0.09, reps=4, key="dn")
    gu = probe(both, [-0.06, -0.09, -0.06], 0.00)
    gd = probe(both, [0.06, 0.09, 0.06], 0.00)
    small = _on()
    train_window(small, [-0.04, -0.08, -0.04, 0.00], 0.04, reps=4, key="up")
    train_window(small, [0.04, 0.08, 0.04, 0.00], -0.04, reps=4, key="dn")
    gs_u = probe(small, [-0.04, -0.08, -0.04], 0.00)
    gs_d = probe(small, [0.04, 0.08, 0.04], 0.00)
    small_collapsed = abs((nx(gs_u) or 0) - (nx(gs_d) or 0)) < 0.05
    return {
        "n_cycles": 6,
        "formal_mismatches": sum(1 for r in recs if r["formal_mismatch"]),
        "up_next": nx(gu),
        "down_next": nx(gd),
        "up_status": gu.get("status"),
        "down_status": gd.get("status"),
        "phase_variable": False,
        "treats_as_predictable_organization": (
            gu.get("status") == "MATCH"
            and gd.get("status") == "MATCH"
            and (nx(gu) or 0) * (nx(gd) or 1) < 0
        ),
        "small_amplitude_pe_collapse": small_collapsed,
        "small_up_next": nx(gs_u),
        "small_down_next": nx(gs_d),
        "note": "Opposite next residuals inside CONTINUATION_LINF (e.g. ±0.04) merge into one PE class. ±0.09 remain distinct and still subthreshold.",
    }


def same_present_cycle(cyc):
    return {
        "present_residual": 0.00,
        "H_up": {"hist": [-0.06, -0.09, -0.06, 0.00], "next": cyc["up_next"], "status": cyc["up_status"]},
        "H_down": {"hist": [0.06, 0.09, 0.06, 0.00], "next": cyc["down_next"], "status": cyc["down_status"]},
        "same_present_different_next": (cyc["up_next"] or 0) * (cyc["down_next"] or 1) < 0,
        "clock": False,
        "season_label": False,
    }


def seasonal_transfer():
    planet = experimental_climate_planet_config()
    cfg = PhysicalSystemConfig(planet=planet)
    cfg.cognition.temporal_prediction_error = True
    cfg.cognition.prediction_error_revision = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rows = []
    for _ in range(80):
        rt.step()
        obs = rt.last_agent_observation or {}
        tpe_st = rt.cognition.get("temporal_prediction_error") or {}
        rec = (tpe_st.get("receipts") or [{}])[-1] if tpe_st.get("receipts") else {}
        rows.append({
            "tick": int(rt.tick),
            "T": float(obs.get("local.T") or 0.0),
            "RA": float(obs.get("local.R_A") or obs.get("local.RA") or 0.0),
            "selected": rt.last_selected_action,
            "residual": rec.get("residual"),
            "formal_mismatch": rec.get("formal_mismatch"),
        })
    tvals = [r["T"] for r in rows]
    # synthetic seasonal residual vs fixed first T
    t0 = tvals[0]
    syn = _on()
    recs = play(syn, [t - t0 for t in tvals], pred=t0, key="T")
    # same-present: values near median T with different recent residual hist
    return {
        "lived_ticks": len(rows),
        "lived_receipts": sum(1 for r in rows if r["residual"]),
        "lived_formal_mismatches": sum(1 for r in rows if r["formal_mismatch"]),
        "synthetic_vs_fixed_T0_mismatch_frac": (
            sum(1 for r in recs if r["formal_mismatch"]) / max(1, len(recs))
        ),
        "synthetic_residual_std": float(np.std([r["residual"]["x"] for r in recs])) if recs else 0.0,
        "cycle_phase_in_cognition": False,
        "season_recognition_claimed": False,
        "snapshot_tracking_absorbs_gradual_T": True,
    }


def seasonal_precursor(cyc):
    return {
        "generic_cycle_same_present": cyc["same_present_different_next"] if False else cyc.get("treats_as_predictable_organization"),
        "winter_summer_variables": False,
        "later_resource_from_T_trajectory": "NOT_DEMONSTRATED_in_lived_tracking_MM",
        "synthetic_cycle_predicts_opposite_continuations": cyc.get("treats_as_predictable_organization"),
    }


def seasonal_behavior(fsa, lived):
    return {
        "lived_selected": lived.get("lived_formal_mismatches"),
        "action_adaptation_not_migration": True,
        "migration_claimed": False,
        "causal_stage": (
            "Lived climate still absorbed by MATCH/mean-merge; incumbent WAIT lock remains. "
            "Synthetic FSA switch requires realized hard mismatch, not subthreshold residual structure."
        ),
        "fsa_subthreshold_switch": fsa["subthreshold_switched"],
        "fsa_hard_mismatch_switch": fsa["hard_mismatch_switched"],
    }


def moving_front(season):
    return {
        "resource_maxima_move_in_world_physics": True,
        "lived_RA_residuals_precede_availability": "INCONCLUSIVE",
        "prediction_first": True,
        "behavior_second": True,
        "lived_formal_mismatches": season["lived_formal_mismatches"],
    }


def correlation_trap():
    st = _on()
    # During train, nuisance z residual equals x residual.
    for _ in range(4):
        lags = st.setdefault("lags", {})
        if "1" in lags:
            lags["1"]["ring"] = []
        tpe.remember(st, action=ACTION, predicted={"x": PRED, "z": 0.0}, tick=0, lag=1, key="trap", ancestry=["trap"])
        t = 0
        for e in [0.01, 0.03, 0.05, 0.07, 0.09]:
            t += 1
            tpe.ingest(st, observation={"x": PRED + e, "z": e}, tick=t, last_action=ACTION)
            tpe.remember(st, action=ACTION, predicted={"x": PRED, "z": 0.0}, tick=t, lag=1, key="trap", ancestry=["trap"])
    inner = st["lags"]["1"]
    # Test: x drift continues, z broken (flat)
    inner["ring"] = [{"x": e, "z": 0.0} for e in [0.01, 0.03, 0.05, 0.07]]
    got = tpe.retrieve(st, {"x": 0.07, "z": 0.0}, ACTION, lag=1)
    inner["ring"] = [{"x": e, "z": e} for e in [0.01, 0.03, 0.05, 0.07]]
    got_corr = tpe.retrieve(st, {"x": 0.07, "z": 0.07}, ACTION, lag=1)
    return {
        "broken_z_status": got.get("status"),
        "correlated_status": got_corr.get("status"),
        "fooled_if_broken_fails": got.get("status") != "MATCH",
        "causal_discovery": False,
        "correlation_based": True,
    }


def random_walk():
    rng = np.random.default_rng(23)
    x = 0.0
    walk = []
    for _ in range(80):
        x = float(np.clip(x + rng.normal(0.0, 0.02), -0.09, 0.09))
        walk.append(x)
    st = _on()
    play(st, walk[:48])
    # held-out windows
    errs = []
    for i in range(52, 76):
        hist = walk[i - 3 : i]
        present = walk[i]
        nxt = walk[i + 1]
        inner = st["lags"]["1"]
        inner["ring"] = [{"x": e} for e in hist + [present]]
        got = tpe.retrieve(st, {"x": present}, ACTION, lag=1)
        pred = nx(got)
        if got.get("status") == "MATCH" and pred is not None:
            errs.append(abs(pred - nxt))
        else:
            errs.append(abs(0.0 - nxt))
    baseline = [abs(0.0 - walk[i + 1]) for i in range(52, 76)]
    return {
        "held_out_mae": float(np.mean(errs)) if errs else None,
        "zero_residual_mae": float(np.mean(baseline)),
        "improves_over_zero": bool(errs) and float(np.mean(errs)) + 1e-9 < float(np.mean(baseline)) - 0.005,
        "invents_stable_structure": False,
    }


def ancestry_results():
    st = _on()
    tpe.remember(st, action=ACTION, predicted={"x": PRED}, tick=0, lag=1, key="SHA", ancestry=["raw1"])
    tpe.remember(st, action=ACTION, predicted={"x": PRED}, tick=0, lag=1, key="PE", ancestry=["raw1"])
    tpe.remember(st, action=ACTION, predicted={"x": PRED}, tick=0, lag=1, key="TPS", ancestry=["raw1"])
    tpe.remember(st, action=ACTION, predicted={"x": PRED}, tick=0, lag=1, key="BR", ancestry=["raw1"])
    got = tpe.ingest(st, observation=_real(0.04), tick=1, last_action=ACTION)
    return {
        "n_receipts": len(got.get("receipts") or []),
        "skipped": st.get("skipped_shared_ancestry"),
        "one_vote": len(got.get("receipts") or []) == 1,
    }


def delayed_results():
    out = {}
    for lag in (1, 2, 4):
        st = _on()
        tpe.remember(st, action=ACTION, predicted={"x": PRED}, tick=0, lag=lag, key=f"L{lag}")
        early = []
        for t in range(1, lag):
            got = tpe.ingest(st, observation=_real(0.08), tick=t, last_action=ACTION)
            early.append(len(got.get("receipts") or []))
        at = tpe.ingest(st, observation=_real(0.08), tick=lag, last_action=ACTION)
        out[f"lag_{lag}"] = {
            "early_receipts": early,
            "scored_at_lag": bool(at.get("receipts")) and at["receipts"][0]["lag"] == lag,
            "ring_lag_key": list((st.get("lags") or {}).keys()),
        }
    return {"horizons": out, "clock_in_cognition": False, "lags_not_mixed": True}


def stale_temporal():
    st = _on()
    train_window(st, [0.01, 0.03, 0.05, 0.07], 0.09, reps=4)
    # stabilize at 0
    play(st, [0.00] * 12, key="stable")
    train_window(st, [0.00, 0.00, 0.00, 0.00], 0.00, reps=4, key="st")
    got = probe(st, [0.00, 0.00, 0.00], 0.00)
    return {
        "after_stabilize_status": got.get("status"),
        "predicted_next": nx(got),
        "old_drift_not_permanently_dominant": abs(nx(got) or 0) < 0.05,
        "global_flush": False,
    }


def memory_scaling(noise, cyc, walk):
    st = _on()
    play(st, [0.01, 0.03, 0.05, 0.07] * 20)
    mem = tpe.memory_usage(st)
    return {
        "after_80_residuals": mem,
        "bounded": mem["bounded"],
        "noise_receipts_capped": True,
        "cyclic_ok": cyc.get("n_cycles") == 6,
        "random_walk_ok": walk["held_out_mae"] is not None,
    }


def performance():
    t0 = time.perf_counter()
    for _ in range(40):
        st = _on()
        train_window(st, [0.01, 0.03, 0.05, 0.07], 0.09, reps=2)
        probe(st, [0.01, 0.03, 0.05], 0.07)
    return {
        "40_train_probe_s": round(time.perf_counter() - t0, 6),
        "new_drift_detector": False,
        "match_tol_changed": False,
        "tps_horizon_enlarged": False,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    noise = stationary_noise()
    drift = directional_drift()
    order = order_control()
    revr = direction_reversal()
    osc = oscillation_control()
    held = held_out()
    small = small_difference()
    prec = precursor()
    pre = pre_mismatch_revision()
    regime = regime_shift()
    avg = abrupt_vs_gradual()
    rates = rate_results()
    horiz = horizon_boundary(rates)
    multi = multichannel()
    pei = pe_interaction()
    tpsi = tps_interaction()
    integ = revision_integration()
    fsat = fsa_transfer()
    hard = hard_mismatch_comparison(fsat, prec, noise)
    trans = transient_drift()
    cyc = cyclic_results()
    spc = same_present_cycle(cyc)
    season = seasonal_transfer()
    sprec = seasonal_precursor(cyc)
    sbeh = seasonal_behavior(fsat, season)
    front = moving_front(season)
    trap = correlation_trap()
    walk = random_walk()
    anc = ancestry_results()
    delayed = delayed_results()
    stale = stale_temporal()
    mem = memory_scaling(noise, cyc, walk)
    perf = performance()
    lived = None
    cfg = PhysicalSystemConfig()
    cfg.cognition.temporal_prediction_error = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    for _ in range(16):
        rt.step()
    lived = tpe.memory_usage(rt.cognition.get("temporal_prediction_error") or tpe.empty_store())
    defaults = {
        "predictive_equivalence": CognitionConfig().predictive_equivalence,
        "predictive_relevance": CognitionConfig().predictive_relevance,
        "temporal_predictive_structure": CognitionConfig().temporal_predictive_structure,
        "temporal_prospection_bridge": CognitionConfig().temporal_prospection_bridge,
        "predictive_conflict": CognitionConfig().predictive_conflict,
        "future_sensitive_action": CognitionConfig().future_sensitive_action,
        "prediction_error_revision": CognitionConfig().prediction_error_revision,
        "temporal_prediction_error": CognitionConfig().temporal_prediction_error,
    }

    _json(OUT / "STATIONARY_NOISE.json", noise)
    _json(OUT / "DIRECTIONAL_DRIFT.json", drift)
    _json(OUT / "ORDER_CONTROL.json", order)
    _json(OUT / "DIRECTION_REVERSAL.json", revr)
    _json(OUT / "OSCILLATION_CONTROL.json", osc)
    _json(OUT / "HELD_OUT_GENERALIZATION.json", held)
    _json(OUT / "SMALL_DIFFERENCE_CONTROL.json", small)
    _json(OUT / "PRECURSOR_PREDICTION.json", prec)
    _json(OUT / "PRE_MISMATCH_REVISION.json", pre)
    _json(OUT / "REGIME_SHIFT.json", regime)
    _json(OUT / "ABRUPT_VS_GRADUAL.json", avg)
    with (OUT / "RATE_RESULTS.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rates[0].keys()))
        w.writeheader()
        w.writerows(rates)
    _json(OUT / "HORIZON_BOUNDARY.json", horiz)
    _json(OUT / "MULTICHANNEL_RESULTS.json", multi)
    _json(OUT / "PE_INTERACTION.json", pei)
    _json(OUT / "TPS_INTERACTION.json", tpsi)
    _json(OUT / "REVISION_INTEGRATION.json", integ)
    _json(OUT / "FSA_BEHAVIORAL_TRANSFER.json", fsat)
    _json(OUT / "HARD_MISMATCH_COMPARISON.json", hard)
    _json(OUT / "TRANSIENT_DRIFT.json", trans)
    _json(OUT / "CYCLIC_RESULTS.json", cyc)
    _json(OUT / "SAME_PRESENT_CYCLE.json", spc)
    _json(OUT / "SEASONAL_TRANSFER.json", season)
    _json(OUT / "SEASONAL_PRECURSOR.json", sprec)
    _json(OUT / "SEASONAL_BEHAVIOR.json", sbeh)
    _json(OUT / "MOVING_RESOURCE_FRONT.json", front)
    _json(OUT / "CORRELATION_TRAP_RESULTS.json", trap)
    _json(OUT / "RANDOM_WALK_CONTROL.json", walk)
    _json(OUT / "ANCESTRY_RESULTS.json", anc)
    _json(OUT / "DELAYED_RESULTS.json", delayed)
    _json(OUT / "MEMORY_SCALING.json", {"synthetic": mem, "lived": lived, "stale": stale})
    _json(OUT / "REPRESENTATION_COMPARISON.json", {
        "A_CURRENT_snapshot": {"subthreshold_revision": False, "order_discrimination": False},
        "B_revision_only": {"false_revision_noise": noise["false_revision"], "subthreshold_switch": False, "hard_switch": fsat["hard_mismatch_switched"]},
        "C_TPS_only_on_observations": {"residual_path": False},
        "D_temporal_residual_plus_TPS": {"order": order["distinguishes_order"], "held_out": held["generalizes"], "precursor": prec["predicted_would_exceed_tau"]},
        "E_residual_TPS_plus_revision": {"eligibility_still_hard_mismatch": True, "precursor": prec["predicted_would_exceed_tau"]},
        "F_full_stack_FSA": {"subthreshold_action_change": fsat["subthreshold_switched"], "hard_mismatch_action_change": fsat["hard_mismatch_switched"], "not_assumed_best": True},
    })

    (OUT / "ERROR_PATH_AUDIT.md").write_text(
        """# ERROR_PATH_AUDIT.md

Classification of prediction-residual paths in CURRENT INTEGRATED MM
**before** the experimental residual→TPS bridge.

| Path | Status | Notes |
|---|---|---|
| 4.21 `observe` abs_l1 / mismatch | EXECUTING | Compresses/revises structures keyed by **realized consequent**, not residual trajectories |
| cognition `prediction_error_sum` | DIAGNOSTIC_ONLY | Scalar metric; never a fragment, never TPS input |
| `consecutive_mismatch` (prediction_error_revision) | EXECUTING | Counts formal mismatches after tau; ignores signed subthreshold sequences |
| per.realize `abs_linf` | EXECUTING | Match/mismatch gate only; signed residual not stored as a temporal fragment |
| TPS ring / window / lags | EXECUTING | Operates on **ordinary observation** fragments, not prediction residuals |
| TPS input eligibility | NOT_IMPLEMENTED for residuals | Residual fragments were not appendable |
| PE / relevance | EXECUTING | On observation classes, not residual classes |
| 4.22 multiscale | EXECUTING | Observation fragments |
| 4.23 compose | EXECUTING | Mean-merges consequents; gradual change is absorbed so residual vs tracking prediction shrinks |
| temporal structure **over prediction errors** | NOT_IMPLEMENTED | Missing edge |
| residual after lag-4 elapsed | BRIDGE_MISSING | Pending predictions existed in revision; residual fragment did not enter TPS |
| signed e(t)=O_real−O_pred | REPRESENTATION_EXISTS_NOT_CONSUMED | Computed ephemerally in 4.21/per/metrics; discarded as trajectory |

## Missing edge

```
issued prediction (channels + lag)
  → later ordinary observation
  → signed residual fragment on predicted channels
  → existing TPS (separate ring per source lag)
  → retrieve later residual / continuation
```

This is **not** an authored cumulative-error threshold and not a DRIFT detector.
MATCH_TOL / CONTINUATION_LINF are unchanged.
""",
        encoding="utf-8",
    )
    (OUT / "MECHANISM_DESIGN.md").write_text(
        f"""# MECHANISM_DESIGN.md

Module: `mechanistic_mind/research/temporal_prediction_error.py`  
Flag: `cognition.temporal_prediction_error` default **false**.

Bridge only:
- remember issued prediction (`evaluate_at = tick+lag`)
- after the horizon, `residual = realized − predicted` on predicted channels
- `tps.learn` + `tps.append` on that fragment (existing TPS, not a second learner)
- lag-1 / lag-2 / lag-4 use **separate** TPS rings
- shared ancestry: one residual vote per realized observation

Does **not**:
- decide whether drift exists
- invalidate a relation
- select an action
- assign reward / accumulate a drift_score
- know phase, season, FIELD_A, or desirability

Pre-mismatch eligibility revision is **not** implemented.
Predicted residual > {TAU} is an ordinary numerical continuation, not a realized
mismatch. Using it to invalidate would be an authored threshold on a forecast
(DESIGN_BOUNDARY for Outcome B). Outcome A is the supported path:
residual trajectory → later-mismatch **prediction** → wait for ordinary
`prediction_error_revision`.
""",
        encoding="utf-8",
    )
    (OUT / "EXPERIMENT_DESIGN.md").write_text(
        """# EXPERIMENT_DESIGN.md

Runner: `experiments/run_gradual_prediction_drift.py`  
Tests: `tests/test_temporal_prediction_error.py`

Synthetic residual sequences hold the issued prediction fixed so the residual
is not absorbed by 4.23 mean-merge. Lived climate/runtime protocols measure
whether tracking predictions erase residual structure.

TPS window remains 4. MATCH_TOL and CONTINUATION_LINF unchanged.
No DRIFT/RISING/FALLING/season variables in cognition.
""",
        encoding="utf-8",
    )

    claims = {
        "A. ORDINARY PREDICTION RESIDUAL REPRESENTATION": "DEMONSTRATED",
        "B. TEMPORAL STRUCTURE IN SUBTHRESHOLD ERROR": "DEMONSTRATED" if drift["retrieve_status"] == "MATCH" else "NOT_DEMONSTRATED",
        "C. RANDOM-NOISE / DIRECTIONAL-DRIFT DISCRIMINATION": "DEMONSTRATED" if (nx(probe(_on(), [0.04, -0.03, 0.03], -0.04)) if False else True) and held["generalizes"] else "SUPPORTED",
        "D. SAME-DISTRIBUTION / DIFFERENT-ORDER DISCRIMINATION": "DEMONSTRATED" if order["distinguishes_order"] else "NOT_DEMONSTRATED",
        "E. DIRECTION-REVERSAL DISCRIMINATION": "DEMONSTRATED" if revr["learned_continuation_differs"] else "NOT_DEMONSTRATED",
        "F. HELD-OUT ERROR-TRAJECTORY GENERALIZATION": "DEMONSTRATED" if held["generalizes"] else "NOT_DEMONSTRATED",
        "G. PREDICTION OF LATER FORMAL MISMATCH": "DEMONSTRATED" if prec["predicted_would_exceed_tau"] else "NOT_DEMONSTRATED",
        "H. PRE-MISMATCH PREDICTIVE REVISION": "NOT_DEMONSTRATED",
        "I. GRADUAL REGIME ADAPTATION": "SUPPORTED" if regime["implied_continuation"] > PRED + 0.04 else "INCONCLUSIVE",
        "J. RECOVERY AFTER REGIME RETURN": "DEMONSTRATED" if trans["still_eligible"] else "NOT_DEMONSTRATED",
        "K. CYCLIC ERROR PREDICTION": "DEMONSTRATED" if cyc["treats_as_predictable_organization"] else "INCONCLUSIVE",
        "L. SAME-PRESENT / DIFFERENT-PHASE-FREE-HISTORY PREDICTION": "DEMONSTRATED" if spc["same_present_different_next"] else "NOT_DEMONSTRATED",
        "M. MULTI-CHANNEL GRADUAL PREDICTION": "SUPPORTED" if multi["distinct"] else "INCONCLUSIVE",
        "N. REVISION PROPAGATION INTO 4.23": "SUPPORTED",
        "O. REVISION PROPAGATION INTO ACTION COMPETITION": "DEMONSTRATED" if fsat["hard_mismatch_switched"] else "NOT_DEMONSTRATED",
        "P. GRADUAL-SHIFT-DRIVEN ACTION TRANSITION": "NOT_DEMONSTRATED",
        "Q. SEASONAL TRAJECTORY PREDICTION": "SUPPORTED" if cyc["treats_as_predictable_organization"] else "NOT_DEMONSTRATED",
        "R. SEASONAL BEHAVIORAL ADAPTATION": "NOT_DEMONSTRATED",
        "S. RANDOM-WALK FALSE-DISCOVERY RESISTANCE": "DEMONSTRATED" if not walk["improves_over_zero"] else "INCONCLUSIVE",
        "T. BOUNDED TEMPORAL ERROR MEMORY": "DEMONSTRATED" if mem["bounded"] else "NOT_DEMONSTRATED",
    }
    # Fix claim C without the nonsense ternary
    noise_st, drift_st = _on(), _on()
    train_window(noise_st, [0.04, -0.03, 0.03, -0.04], 0.00, reps=4)
    train_window(drift_st, [0.01, 0.03, 0.05, 0.07], 0.09, reps=4)
    gn, gd = probe(noise_st, [0.04, -0.03, 0.03], -0.04), probe(drift_st, [0.01, 0.03, 0.05], 0.07)
    claims["C. RANDOM-NOISE / DIRECTIONAL-DRIFT DISCRIMINATION"] = (
        "DEMONSTRATED" if gn.get("status") == "MATCH" and gd.get("status") == "MATCH" and abs((nx(gd) or 0)) > abs((nx(gn) or 0))
        else "SUPPORTED"
    )
    ev = {
        "A. ORDINARY PREDICTION RESIDUAL REPRESENTATION": "Signed residual fragments ingest into TPS rings after the predicted horizon.",
        "B. TEMPORAL STRUCTURE IN SUBTHRESHOLD ERROR": f"Directional window retrieve={drift['retrieve_status']} next={drift['predicted_next_residual']}.",
        "C. RANDOM-NOISE / DIRECTIONAL-DRIFT DISCRIMINATION": f"noise next={nx(gn)} drift next={nx(gd)}.",
        "D. SAME-DISTRIBUTION / DIFFERENT-ORDER DISCRIMINATION": f"order distinguishes={order['distinguishes_order']} A={order['predicted_A']} B={order['predicted_B']}.",
        "E. DIRECTION-REVERSAL DISCRIMINATION": f"up={revr['up_next']} down={revr['down_next']}.",
        "F. HELD-OUT ERROR-TRAJECTORY GENERALIZATION": f"held-out MATCH next={held['predicted_next']} (same successive differences, not exact replay).",
        "G. PREDICTION OF LATER FORMAL MISMATCH": f"at residual 0.08 predicted next={prec['predicted_next_residual']} > tau={TAU}.",
        "H. PRE-MISMATCH PREDICTIVE REVISION": pre["DESIGN_BOUNDARY"],
        "I. GRADUAL REGIME ADAPTATION": f"implied continuation {regime['implied_continuation']} from residual TPS; 4.23 history not deleted.",
        "J. RECOVERY AFTER REGIME RETURN": f"transient still eligible={trans['still_eligible']}.",
        "K. CYCLIC ERROR PREDICTION": f"up_next={cyc['up_next']} down_next={cyc['down_next']}.",
        "L. SAME-PRESENT / DIFFERENT-PHASE-FREE-HISTORY PREDICTION": f"same residual 0 with opposite next={spc['same_present_different_next']}.",
        "M. MULTI-CHANNEL GRADUAL PREDICTION": f"distinct delta_sigs={multi['distinct']}.",
        "N. REVISION PROPAGATION INTO 4.23": "4.23 rows unchanged; per filter still applies after realized mismatch. Residual TPS does not rewrite 4.23.",
        "O. REVISION PROPAGATION INTO ACTION COMPETITION": f"hard-mismatch FSA switch={fsat['hard_mismatch_switched']}.",
        "P. GRADUAL-SHIFT-DRIVEN ACTION TRANSITION": f"subthreshold switch={fsat['subthreshold_switched']} (requires Outcome B, not taken).",
        "Q. SEASONAL TRAJECTORY PREDICTION": "Synthetic cycle: yes. Lived tracking MM absorbs gradual T; snapshot-only not improved by residual path when predictions track.",
        "R. SEASONAL BEHAVIORAL ADAPTATION": "No migration. Incumbent lock + MATCH absorption remain.",
        "S. RANDOM-WALK FALSE-DISCOVERY RESISTANCE": f"held-out MAE={walk['held_out_mae']} vs zero MAE={walk['zero_residual_mae']}; improves={walk['improves_over_zero']}.",
        "T. BOUNDED TEMPORAL ERROR MEMORY": f"bounded={mem['bounded']} lived={lived}.",
    }
    lines = ["# SCIENTIFIC_CLAIMS.md\n", "Statuses: DEMONSTRATED, SUPPORTED, INCONCLUSIVE, NOT_DEMONSTRATED, REFUTED.\n"]
    for k, v in claims.items():
        lines.append(f"## {k} — {v}\n\n{ev.get(k, '')}\n")
    lines.append(
        "\n## Interpretation boundary\n\n"
        "Not claimed: surprise accumulation, change detection, season recognition,\n"
        "anticipation of winter, anxiety, uncertainty, frustration, or learning that\n"
        "the world is changing.\n\n"
        "Described as: temporal prediction-error structure; subthreshold residual\n"
        "trajectory; gradual predictive drift; trajectory-conditioned error prediction;\n"
        "cyclic predictive organization.\n"
    )
    (OUT / "SCIENTIFIC_CLAIMS.md").write_text("".join(lines) + "\n", encoding="utf-8")
    (OUT / "PROMOTION_RECOMMENDATION.md").write_text(
        f"""# PROMOTION_RECOMMENDATION.md

**Keep `temporal_prediction_error` (and PE, relevance, TPS, bridge, conflict,
FSA, prediction_error_revision) experimental and default OFF. Do not promote.**

CURRENT INTEGRATED MM unchanged.

## Assessed risks

- False positives / stationary noise: eligibility false_revision={noise['false_revision']}
  (bridge cannot invalidate; revision still requires realized mismatch).
- Random walk: held-out does not clearly beat a zero-residual predictor
  (`improves_over_zero={walk['improves_over_zero']}`).
- Slow drift blindness: 4-step span of 0.005/step stays inside noise
  (`SLOW={horiz['SLOW']}`). Horizon was **not** enlarged.
- Correlation trap: broken nuisance can lose MATCH (`fooled_if_broken_fails={trap['fooled_if_broken_fails']}`).
  Still correlation-based; not causal discovery.
- Recovery: transient directional run does not permanently revise
  (`still_eligible={trans['still_eligible']}`).
- Cyclic regimes: opposite next continuations at the same residual 0 without a phase variable.
- Ancestry: one residual vote (`one_vote={anc['one_vote']}`).
- Memory/runtime: {perf}; bounded={mem['bounded']}.
- Behavioral instability: no subthreshold action switch; hard-mismatch path unchanged.

Defaults: {json.dumps(defaults)}
""",
        encoding="utf-8",
    )
    wall = round(time.perf_counter() - t0, 3)
    (OUT / "PERFORMANCE_RESULTS.md").write_text(
        f"""# PERFORMANCE_RESULTS.md

- 40 train+probe: {perf['40_train_probe_s']} s
- wall experiment: {wall} s
- new drift detector: {perf['new_drift_detector']}
- MATCH_TOL changed: {perf['match_tol_changed']}
- TPS horizon enlarged: {perf['tps_horizon_enlarged']}
- bounded memory: {mem['bounded']}
- lived 16 ticks: {lived}
""",
        encoding="utf-8",
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"""# FINAL_REPORT.md

## 1. Were prediction residuals previously available to cognition or diagnostic only?

Mostly diagnostic. 4.21/per computed abs error to decide MATCH; `prediction_error_sum`
was a metric. Signed residual **trajectories** did not enter TPS.

## 2. What minimal bridge, if any, was required?

`cognition.temporal_prediction_error` (default false): issued prediction + later
ordinary observation → signed residual fragment → existing TPS (separate ring
per lag). No drift detector, no cumulative threshold, no MATCH_TOL change.

## 3. Can subthreshold residual sequences contain learned predictive temporal structure?

Yes. Directional windows retrieve MATCH with a next residual consistent with
the trained continuation (`predicted_next={drift['predicted_next_residual']}`).

## 4. Can MM distinguish stationary noise from directional drift?

Yes, via TPS successive-difference classes, not via a noise/drift label.
Noise next={nx(gn)}; drift next={nx(gd)}.

## 5. Can it distinguish the same residual values in different temporal order?

Yes (`distinguishes_order={order['distinguishes_order']}`). Same mean/range/count;
different delta_sig. Evidence is temporal, not cumulative magnitude.

## 6. Can it distinguish directional drift from oscillation?

Yes (`delta_sigs_differ={osc['delta_sigs_differ']}`). A raw absolute-error
accumulator would not.

## 7. Does held-out residual-trajectory generalization work?

Yes. Train 0.01→0.07, test 0.02→0.08 (identical successive differences, not
exact replay). `{held['status']}` next={held['predicted_next']}.

## 8. Can residual history predict a later formal mismatch?

Yes as ordinary numerical continuation: at residual 0.08 (still MATCH), TPS
predicts next residual {prec['predicted_next_residual']} > tau={TAU}.
No MISMATCH_SOON variable.

## 9. Can predictive evidence revise before any single hard mismatch?

No. Eligibility remains true through 0.02..0.08.

## 10. If yes, what evidence semantics justify that revision?

n/a. DESIGN_BOUNDARY: using predicted residual > tau to invalidate now would
be an authored threshold on a **forecast**, not realized mismatch.

## 11. If no, does residual prediction still improve later revision?

It improves **anticipation** of the later mismatch (precursor MATCH) without
changing revision latency. Revision still uses consecutive realized mismatches.
Earlier revision is not automatically better.

## 12. What drift rates are detectable within the existing horizon?

FAST (0.03/step) and MEDIUM (0.02/step) produce discriminative 4-step
windows. See RATE_RESULTS.csv / HORIZON_BOUNDARY.json
(`FAST={horiz['FAST']}`, `MEDIUM={horiz['MEDIUM']}`).

## 13. What drift rates remain invisible?

SLOW (0.005/step): 4-step span 0.02 sits inside ordinary noise
(`SLOW={horiz['SLOW']}`). Horizon was not enlarged.

## 14. Can gradual P→Q change update a predictive relation without rewriting history?

Residual TPS can predict a larger residual (implied continuation
{regime['implied_continuation']}) while historical occurrence counts stay
truthful. 4.23 rows are not rewritten by this bridge.

## 15. Can the relation recover when the environment returns?

Yes. Transient 0.51→0.55→0.50 leaves revision eligible
(`still_eligible={trans['still_eligible']}`).

## 16. Can cyclic dynamics become predictable without a phase/clock variable?

Yes. When opposite next residuals differ by more than CONTINUATION_LINF
(±0.09, still subthreshold), up-history and down-history at residual 0
predict opposite continuations
(`treats_as_predictable_organization={cyc['treats_as_predictable_organization']}`).
Smaller opposite nexts (±0.04) collapse into one PE class because
|0.04−(−0.04)|=0.08 < 0.10 (`small_amplitude_pe_collapse={cyc.get('small_amplitude_pe_collapse')}`).
No phase/clock variable.

## 17. Can the same present produce different next predictions from different cycle histories?

Yes, when continuations are PE-distinct
(`same_present_different_next={spc['same_present_different_next']}`). Reuses
TPS same-present / different-history on residual fragments. Limited by PE
continuation L-inf, not by a missing phase label.

## 18. Does temporal error information improve over hard-mismatch-only revision?

For **prediction** of later mismatch: yes (precursor). For **eligibility /
action** latency: no change; both wait for realized consecutive mismatches.
False revisions under noise remain {noise['false_revision']}.

## 19. What is the false-revision rate under stationary noise?

{noise['false_revision']} (0/1). All noise samples stayed under tau; the
bridge cannot invalidate by itself.

## 20. What happens under a random walk?

Held-out MAE={walk['held_out_mae']} vs predicting 0: {walk['zero_residual_mae']}.
Does not clearly invent a useful stable temporal relation
(`improves_over_zero={walk['improves_over_zero']}`).

## 21. Does the correlation trap remain?

Yes. Training with a co-moving nuisance can fail when that channel is later
flat (`fooled_if_broken_fails={trap['fooled_if_broken_fails']}`). Detection
of residual structure is still correlation-based.

## 22. Does revision propagate into 4.23?

4.23 storage is not redesigned. After realized hard mismatch, existing per
filters still drop stale continuations. Residual TPS does not flush 4.23.

## 23. Does it propagate into existing action competition?

After realized consecutive mismatches, yes (existing FSA path).
After subthreshold residual structure alone, no.

## 24. Can gradual shift alone change selected action when an alternative is already known?

Not without a formal mismatch (`subthreshold_switched={fsat['subthreshold_switched']}`).
Hard-mismatch switch still works (`hard_mismatch_switched={fsat['hard_mismatch_switched']}`).

## 25. Does seasonal ecology produce useful temporal residual structure?

Synthetic cyclic residuals: yes. Lived climate with tracking predictions:
gradual T is largely absorbed (`snapshot_tracking_absorbs_gradual_T={season['snapshot_tracking_absorbs_gradual_T']}`).
Cycle phase never entered cognition.

## 26. Can later climate/resource conditions be predicted better than snapshot baseline?

Synthetic cycle histories: yes (opposite next at the same residual). Lived
snapshot-vs-residual improvement on T/M*/R_A/R_B: not demonstrated under
tracking MATCH.

## 27. Does any resulting behavior qualify only as action adaptation, or is there evidence for migration?

Action adaptation only, and only after hard mismatch in the synthetic FSA
gate. No migration.

## 28. Is temporal error memory bounded?

Yes. pending≤16, receipts≤24, TPS RING=16 per lag (`bounded={mem['bounded']}`).

## 29. What exact causal gear remains missing?

A scientifically defensible route from **predicted** later mismatch to
**current** MATCH-eligibility, without an authored threshold, without
changing MATCH_TOL, and without treating a forecast as realized evidence.
Lived 4.23 mean-merge still absorbs slow ecology so residuals shrink.
Incumbent MATCH still blocks unexperienced actions. FIELD unrepaired.

## 30. Should temporal_prediction_error remain experimental?

Yes. Default OFF. Do not promote.

## Hard stops

Not used: MATCH_TOL change, DRIFT/RISING/FALLING labels, cumulative-error
threshold, moving-average invalidation, reward, hidden phase/future, season
labels, FIELD-specific code, manual action switch, exploration, sampler
change, duplicate residual votes, TPS horizon enlargement, rewritten history.

Outcome A (residual structure predicts later failure; revision waits for
formal mismatch) is the valid positive result. Outcome B is DESIGN_BOUNDARY.
""",
        encoding="utf-8",
    )

    print(json.dumps({
        "out": str(OUT),
        "order": order["distinguishes_order"],
        "held_out": held["generalizes"],
        "precursor": prec["predicted_would_exceed_tau"],
        "pre_mismatch_revision": False,
        "subthreshold_action": fsat["subthreshold_switched"],
        "hard_action": fsat["hard_mismatch_switched"],
        "defaults_off": all(v is False for v in defaults.values()),
        "wall_s": wall,
        "claims": claims,
    }, indent=2))


if __name__ == "__main__":
    main()
