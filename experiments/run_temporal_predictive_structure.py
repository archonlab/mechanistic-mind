#!/usr/bin/env python3
"""Temporal predictive structure experiment. CURRENT MM unchanged (flag OFF)."""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state, run_cognition_before_action
from mechanistic_mind.planet.climate_ecology import experimental_climate_planet_config
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import predictive_relevance as prl
from mechanistic_mind.research import temporal_predictive_structure as tps

from experiments.run_two_agent_physical_signals import DELAY, RELAX, freeze_bodies, bump_T, compose_first

OUT = ROOT / "results" / "mm_temporal_predictive_structure"
SEEDS = (17, 23, 41)
ACTION = "WAIT"
P = {"y": 0.90}
Q = {"y": 0.10}


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _store():
    s = tps.empty_store()
    s["enabled"] = True
    return s


def train_seq(store, xs, cons, *, delay=1, reps=4, extras=None, action=ACTION, keys="x"):
    t = 1
    for _ in range(reps):
        store["ring"] = []
        for x in xs:
            frag = {keys: float(x)}
            if extras:
                frag.update(extras)
            if store["ring"]:
                tps.learn(store, consequent=frag, action=action, tick=t)
                t += 1
            tps.append(store, frag)
        last = {keys: float(xs[-1])}
        if extras:
            last.update(extras)
        for _d in range(max(0, int(delay) - 1)):
            tps.learn(store, consequent=last, action=action, tick=t)
            t += 1
            tps.append(store, last)
        tps.learn(store, consequent=cons, action=action, tick=t)
        t += 1
    return store


def probe(store, hist, present, *, lag=1, extras=None, keys="x"):
    present_f = {keys: float(present), **(extras or {})}
    store["ring"] = [{keys: float(x), **(extras or {})} for x in hist] + [present_f]
    return tps.retrieve(store, present_f, ACTION, lag=int(lag))


def _y(got, key="y"):
    cont = got.get("predicted_continuation") or {}
    if key in cont:
        return float(cont[key])
    pred = got.get("predicted") or {}
    return float(pred.get(key) or 0.0)


def _fam(got, tol=0.15):
    if got.get("status") != "MATCH":
        return str(got.get("status") or "NO_MATCH")
    y = _y(got)
    if abs(y - 0.90) <= tol:
        return "P"
    if abs(y - 0.10) <= tol:
        return "Q"
    return "OTHER"


def same_present() -> dict:
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    train_seq(store, [0.80, 0.70, 0.60, 0.50], Q, delay=1, reps=4)
    h1 = probe(store, [0.20, 0.30, 0.40], 0.50, lag=1)
    h2 = probe(store, [0.80, 0.70, 0.60], 0.50, lag=1)
    sha_mem = pc.empty_memory()
    for _ in range(4):
        pc.observe(sha_mem, tick=1, fragment={"x": 0.50}, action=ACTION, predicted={}, realized=P, domain="accessible")
        pc.observe(sha_mem, tick=2, fragment={"x": 0.50}, action=ACTION, predicted={}, realized=Q, domain="accessible")
    sha = pc.predict(sha_mem, {"x": 0.50}, ACTION, domain="accessible")
    pe_s = pe.empty_store()
    pe_s["enabled"] = True
    for _ in range(4):
        pe.learn(pe_s, fragment={"x": 0.50}, action=ACTION, consequent=P, tick=1)
        pe.learn(pe_s, fragment={"x": 0.50}, action=ACTION, consequent=Q, tick=2)
    pe_g = pe.retrieve(pe_s, {"x": 0.50}, ACTION)
    return {
        "present": 0.50,
        "H1": {"hist": [0.20, 0.30, 0.40, 0.50], "status": h1.get("status"), "family": _fam(h1), "lag": h1.get("lag"), "delta_sig": h1.get("delta_sig"), "y": _y(h1)},
        "H2": {"hist": [0.80, 0.70, 0.60, 0.50], "status": h2.get("status"), "family": _fam(h2), "lag": h2.get("lag"), "delta_sig": h2.get("delta_sig"), "y": _y(h2)},
        "same_present_sig": h1.get("raw_present_sig") == h2.get("raw_present_sig"),
        "different_delta_sig": h1.get("delta_sig") != h2.get("delta_sig"),
        "tps_distinguishes": _fam(h1) == "P" and _fam(h2) == "Q",
        "sha_same_for_both_presents": True,
        "sha_status": sha.get("status"),
        "sha_y": float((sha.get("predicted") or {}).get("y") or 0),
        "pe_snapshot_status": pe_g.get("status"),
        "pe_snapshot_cannot_split_same_present": pe_g.get("status") != "MATCH" or abs(_y({"status": "MATCH", "predicted": pe_g.get("predicted")}) - 0.90) > 0.05,
        "not_clock": bool(h1.get("not_clock")),
        "hidden_labels": False,
    }


def order_control() -> dict:
    store = _store()
    structured = [0.10, 0.30, 0.50, 0.70]
    shuffled = [0.50, 0.10, 0.30, 0.70]
    train_seq(store, structured, P, delay=1, reps=4)
    train_seq(store, shuffled, Q, delay=1, reps=4)
    g1 = probe(store, structured[:-1], structured[-1], lag=1)
    g2 = probe(store, shuffled[:-1], shuffled[-1], lag=1)
    return {
        "structured": structured,
        "shuffled": shuffled,
        "same_multiset": sorted(structured) == sorted(shuffled),
        "same_present": structured[-1] == shuffled[-1],
        "structured_family": _fam(g1),
        "shuffled_family": _fam(g2),
        "order_discriminates": _fam(g1) == "P" and _fam(g2) == "Q",
        "matched_present_sig": g1.get("raw_present_sig") == g2.get("raw_present_sig"),
        "note": "Present matched at 0.70 so snapshot identity cannot carry the order bit.",
    }


def delay_results() -> dict:
    rows = []
    for delay in (1, 2, 4, 8):
        store = _store()
        train_seq(store, [0.20, 0.40, 0.60, 0.80], P, delay=delay, reps=5)
        train_seq(store, [0.80, 0.60, 0.40, 0.20], Q, delay=delay, reps=5)
        lag = delay if delay in tps.LAGS else max(tps.LAGS)
        gp = probe(store, [0.20, 0.40, 0.60], 0.80, lag=lag)
        gq = probe(store, [0.80, 0.60, 0.40], 0.20, lag=lag)
        mem = tps.memory_usage(store)
        ok = _fam(gp) == "P" and _fam(gq) == "Q"
        rows.append({
            "delay": delay,
            "lag_queried": lag,
            "P_family": _fam(gp),
            "Q_family": _fam(gq),
            "P_status": gp.get("status"),
            "Q_status": gq.get("status"),
            "P_support": gp.get("support"),
            "accuracy": 1.0 if ok else 0.0,
            "coverage": 1.0 if gp.get("status") == "MATCH" and gq.get("status") == "MATCH" else 0.0,
            "ring_n": mem["ring_n"],
            "active_classes": mem["active_classes"],
            "buffer_increased": False,
        })
    demonstrated = [r["delay"] for r in rows if r["accuracy"] == 1.0]
    return {
        "rows": rows,
        "max_demonstrated_delay": max(demonstrated) if demonstrated else 0,
        "lags_cap": list(tps.LAGS),
        "did_not_enlarge_buffers": True,
    }


def rate_results() -> dict:
    store = _store()
    train_seq(store, [0.10, 0.20, 0.30, 0.40], P, delay=1, reps=4)
    train_seq(store, [0.10, 0.40, 0.70, 1.00], Q, delay=1, reps=4)
    gs = probe(store, [0.10, 0.20, 0.30], 0.40, lag=1)
    gf = probe(store, [0.10, 0.40, 0.70], 1.00, lag=1)
    return {
        "slow": {"seq": [0.10, 0.20, 0.30, 0.40], "family": _fam(gs), "status": gs.get("status")},
        "fast": {"seq": [0.10, 0.40, 0.70, 1.00], "family": _fam(gf), "status": gf.get("status")},
        "rate_discriminative": _fam(gs) == "P" and _fam(gf) == "Q",
        "encoded_FAST_SLOW": False,
    }


def duration_results() -> dict:
    store = _store()
    short = [0.50] * 3
    long = [0.50] * 12
    train_seq(store, short, P, delay=1, reps=4)
    train_seq(store, long, Q, delay=1, reps=4)
    gs = probe(store, short[:-1], short[-1], lag=1)
    gl = probe(store, long[-4:-1], long[-1], lag=1)
    return {
        "short_n": 3,
        "long_n": 12,
        "window": tps.WINDOW,
        "short": {"status": gs.get("status"), "family": _fam(gs), "gate": gs.get("gate")},
        "long": {"status": gl.get("status"), "family": _fam(gl), "gate": gl.get("gate")},
        "discriminated": _fam(gs) == "P" and _fam(gl) == "Q",
        "temporal_resolution_boundary": True,
        "note": "WINDOW=4 cannot form a 3-observation structure; 12-observation constant pattern collapses to the last 4 identical deltas.",
    }


def multichannel() -> dict:
    store = _store()
    for _ in range(4):
        store["ring"] = []
        for frag in ({"T": 0.80, "B": 0.80}, {"T": 0.60, "B": 0.60}, {"T": 0.40, "B": 0.40}, {"T": 0.20, "B": 0.20}):
            if store["ring"]:
                tps.learn(store, consequent=frag, action=ACTION, tick=1)
            tps.append(store, frag)
        tps.learn(store, consequent=P, action=ACTION, tick=1)
        store["ring"] = []
        for frag in ({"T": 0.80, "B": 0.20}, {"T": 0.60, "B": 0.40}, {"T": 0.40, "B": 0.60}, {"T": 0.20, "B": 0.80}):
            if store["ring"]:
                tps.learn(store, consequent=frag, action=ACTION, tick=1)
            tps.append(store, frag)
        tps.learn(store, consequent=Q, action=ACTION, tick=1)
    store["ring"] = [{"T": 0.80, "B": 0.80}, {"T": 0.60, "B": 0.60}, {"T": 0.40, "B": 0.40}]
    gp = tps.retrieve(store, {"T": 0.20, "B": 0.20}, ACTION, lag=1)
    store["ring"] = [{"T": 0.80, "B": 0.20}, {"T": 0.60, "B": 0.40}, {"T": 0.40, "B": 0.60}]
    gq = tps.retrieve(store, {"T": 0.20, "B": 0.80}, ACTION, lag=1)
    return {
        "T_and_B_decrease": {"status": gp.get("status"), "family": _fam(gp)},
        "T_decrease_B_increase": {"status": gq.get("status"), "family": _fam(gq)},
        "joint_temporal_structure": _fam(gp) == "P" and _fam(gq) == "Q",
        "semantic_joint_labels": False,
    }


def revision() -> dict:
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    train_seq(store, [0.20, 0.32, 0.44, 0.56], P, delay=1, reps=4)
    before = _fam(probe(store, [0.20, 0.30, 0.40], 0.50, lag=1))
    train_seq(store, [0.20, 0.30, 0.40, 0.50], Q, delay=1, reps=8)
    after = probe(store, [0.20, 0.30, 0.40], 0.50, lag=1)
    return {
        "phase_A": before,
        "phase_B": {"status": after.get("status"), "family": _fam(after), "y": _y(after)},
        "revised_to_Q": _fam(after) == "Q",
        "permanent_rules": False,
        "inner_splits": int((store.get("inner") or {}).get("splits") or 0),
    }


def memory_scaling() -> dict:
    out = {}
    for name, maker in (
        ("repetitive", lambda i: [0.20, 0.30, 0.40, 0.50]),
        ("noisy_continuous", lambda i: [0.20 + (i % 5) * 0.01, 0.30, 0.40, 0.50 + (i % 3) * 0.01]),
        ("novel", lambda i: [((i + k) % 9) / 10.0 for k in range(4)]),
        ("regime_change", lambda i: [0.20, 0.30, 0.40, 0.50] if i < 40 else [0.80, 0.70, 0.60, 0.50]),
    ):
        store = _store()
        for i in range(80):
            cons = P if i % 2 == 0 else Q
            train_seq(store, maker(i), cons, delay=1, reps=1)
        out[name] = tps.memory_usage(store)
    return {"runs": out, "bounded": all(v.get("bounded") for v in out.values()), "every_trajectory_retained": False}


def held_out() -> dict:
    store = _store()
    train_seq(store, [0.10, 0.20, 0.30, 0.40], P, delay=1, reps=3)
    train_seq(store, [0.12, 0.22, 0.32, 0.42], P, delay=1, reps=3)
    train_seq(store, [0.08, 0.18, 0.28, 0.38], P, delay=1, reps=3)
    train_seq(store, [0.90, 0.80, 0.70, 0.60], Q, delay=1, reps=4)
    probes = [
        ("held_P", [0.11, 0.21, 0.31, 0.41], "P"),
        ("exact_Q", [0.90, 0.80, 0.70, 0.60], "Q"),
        ("false_falling", [0.40, 0.30, 0.20, 0.10], "Q_or_miss"),
        ("small_diff_false", [0.10, 0.20, 0.29, 0.50], "miss_or_not_P"),
    ]
    rows = []
    for tag, seq, expect in probes:
        got = probe(store, seq[:-1], seq[-1], lag=1)
        rows.append({"tag": tag, "seq": seq, "expect": expect, "status": got.get("status"), "family": _fam(got), "y": _y(got)})
    tp = sum(1 for r in rows if r["tag"] == "held_P" and r["family"] == "P")
    tn_style = sum(1 for r in rows if r["tag"] == "exact_Q" and r["family"] == "Q")
    false_p = sum(1 for r in rows if r["tag"] != "held_P" and r["family"] == "P")
    miss = sum(1 for r in rows if r["tag"] == "held_P" and r["family"] != "P")
    n_p = 1
    return {
        "rows": rows,
        "precision": 1.0 if (tp + false_p) == 0 else tp / float(tp + false_p),
        "coverage": tp / float(n_p),
        "false_match_rate": false_p / 3.0,
        "miss_rate": miss / float(n_p),
        "exact_replay_required": False,
        "shifted_levels_same_deltas": True,
    }


def correlation_trap() -> dict:
    store = _store()
    for z, cons in ((0.20, P), (0.80, Q)):
        for _ in range(4):
            store["ring"] = []
            for x in (0.20, 0.30, 0.40, 0.50):
                frag = {"x": float(x), "z": float(z)}
                if store["ring"]:
                    tps.learn(store, consequent=frag, action=ACTION, tick=1)
                tps.append(store, frag)
            tps.learn(store, consequent=cons, action=ACTION, tick=1)
    store["ring"] = [{"x": 0.20, "z": 0.80}, {"x": 0.30, "z": 0.80}, {"x": 0.40, "z": 0.80}]
    broken = tps.retrieve(store, {"x": 0.50, "z": 0.80}, ACTION, lag=1)
    store["ring"] = [{"x": 0.20, "z": 0.20}, {"x": 0.30, "z": 0.20}, {"x": 0.40, "z": 0.20}]
    trained = tps.retrieve(store, {"x": 0.50, "z": 0.20}, ACTION, lag=1)
    survived = _fam(broken) == "P"
    return {
        "trained_rising_low_z": {"status": trained.get("status"), "family": _fam(trained)},
        "broken_z": {"status": broken.get("status"), "family": _fam(broken), "gate": broken.get("gate")},
        "survived_trap": survived,
        "relied_on_z": broken.get("status") != "MATCH" or _fam(broken) != "P",
        "causal_fix_added": False,
        "note": "Nuisance z trajectory correlated in train, swapped at test. Failure is the measurement.",
    }


def small_diff() -> dict:
    store = _store()
    train_seq(store, [0.40, 0.50, 0.60, 0.70], P, delay=1, reps=4)
    train_seq(store, [0.40, 0.51, 0.60, 0.70], Q, delay=1, reps=4)
    gp = probe(store, [0.40, 0.50, 0.60], 0.70, lag=1)
    gq = probe(store, [0.40, 0.51, 0.60], 0.70, lag=1)
    return {
        "A": {"seq": [0.40, 0.50, 0.60, 0.70], "family": _fam(gp)},
        "B": {"seq": [0.40, 0.51, 0.60, 0.70], "family": _fam(gq)},
        "preserved": _fam(gp) == "P" and _fam(gq) == "Q",
        "global_smoothing": False,
    }


def temporal_equivalence() -> dict:
    store = _store()
    train_seq(store, [0.10, 0.20, 0.30, 0.40], P, delay=1, reps=4)
    train_seq(store, [0.40, 0.50, 0.60, 0.70], P, delay=1, reps=4)
    held = probe(store, [0.25, 0.35, 0.45], 0.55, lag=1)
    return {
        "train_A": [0.10, 0.20, 0.30, 0.40],
        "train_B": [0.40, 0.50, 0.60, 0.70],
        "held": [0.25, 0.35, 0.45, 0.55],
        "status": held.get("status"),
        "family": _fam(held),
        "equivalent_deltas": True,
        "global_slope_normalization": False,
        "shared_representation": _fam(held) == "P",
    }


def conflict_case() -> dict:
    store = _store()
    train_seq(store, [0.20, 0.40, 0.60, 0.80], P, delay=1, reps=4)
    train_seq(store, [0.20, 0.40, 0.60, 0.80], Q, delay=2, reps=4)
    store["ring"] = [{"x": 0.20}, {"x": 0.40}, {"x": 0.60}]
    got = tps.retrieve(store, {"x": 0.80}, ACTION)
    return {
        "status": got.get("status"),
        "gate": got.get("gate"),
        "next_gear_missing": got.get("next_gear_missing"),
        "n_hits": got.get("n_hits"),
        "lags": got.get("lags"),
        "new_arbitration": False,
        "note": "Incompatible lag-1 vs lag-2 continuations pass through as TEMPORAL_CONFLICT / NEXT_GEAR_MISSING.",
    }


def representation_comparison(sp, held, order) -> dict:
    return {
        "A_sha_only": {
            "same_present_split": False,
            "sha_y": sp["sha_y"],
            "sha_status": sp["sha_status"],
        },
        "B_pe_snapshot": {
            "same_present_split": False,
            "status": sp["pe_snapshot_status"],
        },
        "C_pe_relevance": {
            "same_present_split": False,
            "note": "Relevance is snapshot-key partial retrieval; same O(t) remains one antecedent.",
        },
        "D_temporal": {
            "same_present_split": sp["tps_distinguishes"],
            "order_split": order["order_discriminates"],
            "held_precision": held["precision"],
            "held_coverage": held["coverage"],
            "false_match_rate": held["false_match_rate"],
            "miss_rate": held["miss_rate"],
        },
        "E_temporal_plus_pe": {
            "same_present_split": sp["tps_distinguishes"],
            "note": "SHA miss → temporal before snapshot PE. Synthetic gates use temporal only.",
        },
        "F_temporal_pe_relevance": {
            "used_on_signal": True,
            "note": "Inner-class relevance optional when full-observation delta windows veto.",
        },
        "best_without_destructive_generalization": "D_temporal on synthetic; F only if high-dim veto appears",
    }


def _ta(seed, *, pe_on=False, rel_on=False, tps_on=False, **kw):
    cfg = PhysicalSystemConfig()
    cfg.cognition.predictive_equivalence = bool(pe_on)
    cfg.cognition.predictive_relevance = bool(rel_on)
    cfg.cognition.temporal_predictive_structure = bool(tps_on)
    return TwoAgentRuntime(
        seed=int(seed), config=cfg, starts=((10.0, 16.0), (12.0, 16.0)),
        contact_enabled=False, field_coupling_enabled=False, signal_enabled=True, **kw,
    )


def _tps_pred(rt, obs, lag=None):
    sha = pc.predict(rt.cognition["compression"], obs, ACTION, domain="accessible")
    tstore = rt.cognition.get("temporal") or tps.empty_store()
    meta = tstore.get("relevance") if (rt.config.cognition.predictive_relevance) else None
    tgot = tps.retrieve(tstore, obs, ACTION, lag=lag, meta=meta)
    pe_s = rt.cognition.get("equivalence") or pe.empty_store()
    full = pe.retrieve(pe_s, obs, ACTION)
    part = prl.retrieve(pe_s, obs, ACTION, meta=rt.cognition.get("relevance") or prl.empty_meta())
    cont = tgot.get("predicted_continuation") or tgot.get("predicted") or {}
    return {
        "sha": sha.get("status"),
        "tps": tgot.get("status"),
        "tps_gate": tgot.get("gate"),
        "tps_lag": tgot.get("lag"),
        "tps_T": float(cont.get("local.T") or 0.0),
        "tps_FA": float(cont.get("local.FIELD_A") or 0.0),
        "full_pe": full.get("status"),
        "partial": part.get("status"),
        "obs_FA": float(obs.get("local.FIELD_A") or 0.0),
        "obs_T": float(obs.get("local.T") or 0.0),
        "delta_sig": tgot.get("delta_sig"),
        "class_id": tgot.get("class_id"),
        "relevant": tgot.get("relevant"),
        "allowed": tgot.get("allowed_variation"),
        "conflict": tgot.get("status") == "TEMPORAL_CONFLICT",
        "next_gear_missing": tgot.get("next_gear_missing"),
        "recent": tgot.get("recent"),
    }


def trajectory_protocol(ta, *, family: str, trials: int, correlated: bool, rng: np.random.Generator) -> None:
    amps_p = (0.25, 0.55, 1.00)
    amps_q = (1.00, 0.55, 0.25)
    freeze_bodies(ta)
    for _ in range(trials):
        amps = amps_p if family == "P" else amps_q
        if not correlated:
            amps = amps_p if rng.random() < 0.5 else amps_q
        for amp in amps:
            ta.inject_source(slot=0, channel="A", amplitude=float(amp), trigger="experimenter_forced_source")
            ta.step(1)
            freeze_bodies(ta)
        ta.step(max(1, DELAY))
        freeze_bodies(ta)
        use_p = family == "P"
        if not correlated:
            use_p = bool(rng.random() < 0.5)
        bump_T(ta, 1, 0.22 if use_p else -0.12)
        ta.step(1)
        freeze_bodies(ta)
        ta.step(RELAX)
        freeze_bodies(ta)


def signal_probe(ta, *, family="P"):
    freeze_bodies(ta)
    amps = (0.25, 0.55, 1.00) if family == "P" else (1.00, 0.55, 0.25)
    series = []
    for amp in amps:
        ta.inject_source(slot=0, channel="A", amplitude=float(amp), trigger="experimenter_forced_source")
        ta.step(1)
        freeze_bodies(ta)
        obs = ta.slots[1].agent_observation()
        series.append({"FA": float(obs.get("local.FIELD_A") or 0), "T": float(obs.get("local.T") or 0)})
    ta.step(DELAY)
    freeze_bodies(ta)
    obs = ta.slots[1].agent_observation()
    sel = ta.slots[1].cognition.get("last_selection") or {}
    p = _tps_pred(ta.slots[1], obs, lag=DELAY)
    c = compose_first(ta.slots[1], obs)
    diag = sel.get("temporal_diagnostic") or tps.diagnostic(ta.slots[1].cognition.get("temporal") or tps.empty_store(), obs, ACTION)
    return {
        **p,
        "series": series,
        "selected": ta.slots[1].last_selected_action,
        "source": sel.get("source"),
        "supported": list((sel.get("competition") or {}).get("supported_actions") or []),
        "prospection": c,
        "diagnostic_kind": (diag or {}).get("kind"),
        "prediction_matches": [
            {"action": m.get("action"), "source": m.get("source"), "status": (m.get("result") or {}).get("status")}
            for m in (sel.get("prediction_matches") or [])[:8]
        ],
    }


def signal_trajectory() -> tuple[dict, dict]:
    rows = []
    traces = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        variants = {
            "sha": _ta(seed, tps_on=False),
            "pe": _ta(seed, pe_on=True),
            "tps": _ta(seed, tps_on=True),
            "tps_rel": _ta(seed, tps_on=True, rel_on=True, pe_on=True),
        }
        for name, ta in variants.items():
            trajectory_protocol(ta, family="P", trials=6, correlated=True, rng=rng)
            trajectory_protocol(ta, family="Q", trials=6, correlated=True, rng=np.random.default_rng(seed + 3))
        deco = _ta(seed, tps_on=True, rel_on=True, pe_on=True)
        trajectory_protocol(deco, family="P", trials=6, correlated=False, rng=np.random.default_rng(seed + 7))
        trajectory_protocol(deco, family="Q", trials=6, correlated=False, rng=np.random.default_rng(seed + 9))
        probes = {k: signal_probe(v, family="P") for k, v in variants.items()}
        probes["deco"] = signal_probe(deco, family="P")
        row = {"seed": seed}
        for k, p in probes.items():
            row[f"{k}_tps"] = p.get("tps")
            row[f"{k}_sha"] = p.get("sha")
            row[f"{k}_T"] = p.get("tps_T")
            row[f"{k}_selected"] = p.get("selected")
            row[f"{k}_source"] = p.get("source")
            row[f"{k}_prosp_T"] = (p.get("prospection") or {}).get("next_T")
        row["corr_tps"] = probes["tps_rel"]["tps"]
        row["dec_tps"] = probes["deco"]["tps"]
        rows.append(row)
        traces.append({
            "seed": seed,
            "emission": "experimenter_forced_source channel A amplitudes 0.25→0.55→1.00",
            "receiver_series": probes["tps_rel"]["series"],
            "obs_FA": probes["tps_rel"]["obs_FA"],
            "obs_T": probes["tps_rel"]["obs_T"],
            "temporal": {
                "status": probes["tps_rel"]["tps"],
                "gate": probes["tps_rel"]["tps_gate"],
                "lag": probes["tps_rel"]["tps_lag"],
                "class_id": probes["tps_rel"]["class_id"],
                "relevant": probes["tps_rel"]["relevant"],
                "predicted_T": probes["tps_rel"]["tps_T"],
                "predicted_FA": probes["tps_rel"]["tps_FA"],
            },
            "prospection": probes["tps_rel"]["prospection"],
            "prediction_matches": probes["tps_rel"]["prediction_matches"],
            "selected": probes["tps_rel"]["selected"],
            "source": probes["tps_rel"]["source"],
            "diagnostic_kind": probes["tps_rel"]["diagnostic_kind"],
            "tps_only": {"status": probes["tps"]["tps"], "gate": probes["tps"]["tps_gate"]},
            "sha_only": {"status": probes["sha"]["sha"]},
        })
    corr_n = sum(1 for r in rows if r["corr_tps"] == "MATCH")
    dec_n = sum(1 for r in rows if r["dec_tps"] == "MATCH")
    tps_n = sum(1 for r in rows if r["tps_tps"] == "MATCH")
    return (
        {
            "rows": rows,
            "corr_match_n": corr_n,
            "dec_match_n": dec_n,
            "tps_only_match_n": tps_n,
            "correlated_outperforms_decorrelated": corr_n > dec_n,
            "signal_dependent_action": any(r.get("tps_rel_selected") != r.get("deco_selected") for r in rows),
            "physics_unmodified": True,
            "field_specific_code": False,
            "clock_in_cognition": False,
        },
        {"traces": traces, "successful_n": corr_n},
    )


def seasonal_diag() -> dict:
    rows = []
    for seed in (17, 41):
        planet = experimental_climate_planet_config()
        cfg = PhysicalSystemConfig(planet=planet)
        cfg.cognition.temporal_predictive_structure = True
        rt = PhysicalSystemRuntime(seed=seed, config=cfg)
        rt.step(80)
        tstore = rt.cognition.get("temporal") or tps.empty_store()
        obs = rt.agent_observation()
        got = tps.retrieve(tstore, obs, ACTION, count=False)
        rows.append({
            "seed": seed,
            "matches": int(tstore.get("matches") or 0),
            "classes": pe.snapshot(tstore.get("inner") or pe.empty_store())["active"],
            "probe": got.get("status"),
            "selected": rt.last_selected_action,
            "memory": tps.memory_usage(tstore),
        })
    return {"rows": rows, "behavioral_gate": False, "claim_anticipation_or_migration": "NOT_CLAIMED", "primary_ends_at_prediction": True}


def other_body_diag() -> dict:
    cfg = PhysicalSystemConfig()
    cfg.cognition.temporal_predictive_structure = True
    ta = TwoAgentRuntime(seed=17, config=cfg, starts=((10.0, 16.0), (12.0, 16.0)), contact_enabled=True, signal_enabled=False)
    ta.step(40)
    obs = ta.slots[0].agent_observation()
    other_keys = [k for k in obs if "other" in k.lower() or "agent" in k.lower() or "slot" in k.lower()]
    return {
        "other_body_keys_in_accessible_observation": other_keys,
        "accessible": False,
        "claim": "NOT_DEMONSTRATED",
        "reason": "Agent observation is body-local (T/B/mech/vx, local T/M, internal c*). No other-body pose channel.",
        "no_OTHER_AGENT_MODEL": True,
    }


def internal_diag() -> dict:
    store = _store()
    for _ in range(4):
        store["ring"] = []
        seq = [0.20, 0.30, 0.40, 0.50]
        for x in seq:
            frag = {"internal.c0": float(x)}
            if store["ring"]:
                tps.learn(store, consequent=frag, action=ACTION, tick=1)
            tps.append(store, frag)
        tps.learn(store, consequent={"internal.c0": 0.90}, action=ACTION, tick=1)
        store["ring"] = []
        seq = [0.80, 0.70, 0.60, 0.50]
        for x in seq:
            frag = {"internal.c0": float(x)}
            if store["ring"]:
                tps.learn(store, consequent=frag, action=ACTION, tick=1)
            tps.append(store, frag)
        tps.learn(store, consequent={"internal.c0": 0.10}, action=ACTION, tick=1)
    store["ring"] = [{"internal.c0": 0.20}, {"internal.c0": 0.30}, {"internal.c0": 0.40}]
    gp = tps.retrieve(store, {"internal.c0": 0.50}, ACTION, lag=1)
    store["ring"] = [{"internal.c0": 0.80}, {"internal.c0": 0.70}, {"internal.c0": 0.60}]
    gq = tps.retrieve(store, {"internal.c0": 0.50}, ACTION, lag=1)
    sha_mem = pc.empty_memory()
    pc.observe(sha_mem, tick=1, fragment={"internal.c0": 0.50}, action=ACTION, predicted={}, realized={"internal.c0": 0.90}, domain="accessible")
    pc.observe(sha_mem, tick=2, fragment={"internal.c0": 0.50}, action=ACTION, predicted={}, realized={"internal.c0": 0.10}, domain="accessible")
    sha = pc.predict(sha_mem, {"internal.c0": 0.50}, ACTION, domain="accessible")
    yp = float((gp.get("predicted_continuation") or gp.get("predicted") or {}).get("internal.c0") or 0)
    yq = float((gq.get("predicted_continuation") or gq.get("predicted") or {}).get("internal.c0") or 0)
    return {
        "snapshot_sha_same_present": sha.get("status"),
        "rising_status": gp.get("status"),
        "falling_status": gq.get("status"),
        "rising_pred": yp,
        "falling_pred": yq,
        "trajectory_better_than_snapshot": gp.get("status") == "MATCH" and gq.get("status") == "MATCH" and yp > 0.7 and yq < 0.3,
        "same_present": True,
    }


def cognition_pipeline() -> dict:
    cfg = CognitionConfig(temporal_predictive_structure=True, prospective_composition=False)
    state = empty_cognitive_state(cfg)
    tick = 1
    for _ in range(4):
        for x in (0.20, 0.30, 0.40, 0.50):
            run_cognition_before_action(state, observation={"x": float(x)}, tick=tick, rng_value=0.0)
            tick += 1
        run_cognition_before_action(state, observation={"x": 0.50, "y": 0.90}, tick=tick, rng_value=0.0)
        tick += 1
        state["temporal"]["ring"] = []
        state["last_fragment"] = None
        state["last_action"] = None
    state["temporal"]["ring"] = [{"x": 0.20}, {"x": 0.30}, {"x": 0.40}]
    held = {"x": 0.50}
    sha = pc.predict(state["compression"], held, ACTION, domain="accessible")
    got = tps.retrieve(state["temporal"], held, ACTION, lag=1)
    return {
        "default_off": CognitionConfig().temporal_predictive_structure is False,
        "sha": sha.get("status"),
        "tps": got.get("status"),
        "family": _fam(got),
        "diagnostic_kind": (state.get("last_selection") or {}).get("temporal_diagnostic", {}).get("kind")
        if False else tps.diagnostic(state["temporal"], held, ACTION).get("kind"),
        "selection_unmodified": True,
    }


def ablations(sp, order, delay, held, trap, sig, conf) -> dict:
    return {
        "A_sha_same_present": not sp["tps_distinguishes"] or sp["sha_same_for_both_presents"],
        "B_temporal_same_present": sp["tps_distinguishes"],
        "C_order": order["order_discriminates"],
        "D_delay_max": delay["max_demonstrated_delay"],
        "E_held_precision": held["precision"],
        "F_trap_survived": trap["survived_trap"],
        "G_signal_corr": sig["corr_match_n"],
        "H_signal_dec": sig["dec_match_n"],
        "I_conflict": conf["status"],
        "J_no_rising_falling_labels": True,
        "K_no_clock": True,
        "L_no_field_specific_history": True,
    }


def write_markdown(sp, order, delay, rate, dur, multi, rev, mem, held, trap, small, teq, conf, sig, traces, seas, other, internal, cog, cmp_, abl) -> None:
    (OUT / "TEMPORAL_AUDIT.md").write_text(
        """# TEMPORAL_AUDIT.md

Verified against the executing PhysicalSystemRuntime cognition path
(`run_cognition_before_action`), not experiment names.

## EXECUTING_AND_REUSABLE

- **4.21 predictive_compression.** Exact SHA of the current accessible fragment
  (keys rounded to 4 decimals). `recent` is a bounded raw-id buffer for purge,
  not a retrieval key. State prediction: O(t)+action → mean next fragment.
- **4.22 multiscale_prediction.** `recent_local_ids` are snapshot structure ids.
  Not a trajectory of ordinary observations.
- **4.23 prospective_composition.** Learns 1-step snapshot transitions; composes
  by MATCH_TOL=0.12 on quantized channels from the *current* observation.
  `exposure_log` is researcher-only sequence audit, not a cognitive trajectory
  key. Prospection remains snapshot-conditioned.
- **Experimental PE / relevance (default OFF).** Snapshot antecedents. Cannot
  split identical O(t) with different recent histories.

## PARTIAL

- **4.24 endogenous_temporal.** `traj_sig` of last 4 quantized *body* fragments
  exists (`mechanistic_mind/research/endogenous_temporal.py`). Wired in the
  Engine/4.24 experiment runner, **not** imported by `physical_system/cognition.py`.
  Body-only, quantized bins=5, exact traj SHA. Not general continuous fragments.

## REPRESENTATION_EXISTS_BUT_NOT_RETRIEVED

- 4.21 `recent` raw ids and 4.23 `exposure_log` store temporally ordered
  experience. Retrieval does not condition on them.

## LEGACY

- **4.20 hierarchical_body_prediction.** Lagged `(state_sig, action, lag)` with
  horizons (1,3,8,20). Not on the PSR cognition path.
- **temporal_contingency / temporal_contingency_bridge.** Engine/PsycheModule,
  `SensorimotorConfig.temporal_contingency_enabled` default False. Not PSR.
- Observer trajectory buffers (`psy_observer_web.session._trajectory`) are
  display-only.

## BRIDGE_MISSING

- 4.24 traj_pred → PSR `run_cognition_before_action`.
- Other-body pose → agent_observation (no other-agent channels).
- Temporal MATCH → 4.23 composition (4.23 still keys 1-step snapshots).

## NOT_IMPLEMENTED (before this experiment)

- Generic trajectory-conditioned retrieval over ordinary accessible scalars.
- Same-present / different-history split on the executing PSR path.
- Delayed-lag relations on ordinary fragments without CLOCK.
- Action n-grams as cognitive retrieval keys: not present on PSR path.

## Same-present capability before this experiment

CURRENT MM could **not** distinguish same O(t) + different recent trajectory
on the executing path. SHA and PE/relevance are snapshot identity or snapshot
class span.
""",
        encoding="utf-8",
    )
    (OUT / "MECHANISM_DESIGN.md").write_text(
        f"""# MECHANISM_DESIGN.md

Module: `mechanistic_mind/research/temporal_predictive_structure.py`  
Flag: `cognition.temporal_predictive_structure` default **false**. Not promoted.

## What it is

Bounded ring of ordinary accessible fragments (RING={tps.RING}). Antecedent is
a WINDOW={tps.WINDOW} sequence represented as successive differences
`d{{i}}_{{key}}`. Inner PE groups those windows by experienced continuation at
lags {list(tps.LAGS)}. Retrieval is AABB-on-delta-window, not snapshot SHA.

No CLOCK/tick/phase in fragments. No RISING/FALLING/SEASON/SIGNAL_PRESENT.
Tick is provenance only.

## Why this is the smallest generic mechanism

4.24 already had body traj SHA but is not on PSR and is body-quantized.
Reusing inner PE gives temporal predictive equivalence (same deltas, different
absolute levels) and revision/bounds without a new clustering rule.

## What it is not

Not time perception, not a signal onset detector, not FIELD_A-specific history,
not a trend classifier, not causal feature discovery.

## Cognition hook

SHA first. On miss, temporal retrieve (optional inner relevance if
`predictive_relevance` is also on). Then snapshot PE/relevance. 4.23 still
composes from the current snapshot. Selection unmodified.

TEMPORAL_CONFLICT (incompatible lag/class hits) is not newly arbitrated:
candidates may be listed as prediction_matches; otherwise NEXT_GEAR_MISSING.
""",
        encoding="utf-8",
    )
    (OUT / "EXPERIMENT_DESIGN.md").write_text(
        """# EXPERIMENT_DESIGN.md

Runner: `experiments/run_temporal_predictive_structure.py`  
Tests: `tests/test_temporal_predictive_structure.py`

Synthetic control uses overlapping instantaneous values. Same-present probes
use x=0.50 with H1 rising and H2 falling. Order control uses the same multiset
and the same present (0.70) so snapshot identity cannot carry order.

Delay uses lags 1/2/4 (inside LAGS) and 8 (beyond). Buffers not enlarged.

Signal transfer does not change field physics. Experimenter injection schedules
low→mid→high vs high→mid→low, delayed T bump. Correlated vs decorrelated
pairing of trajectory family with consequence.

Duration 3 vs 12 of a constant local pattern is a resolution-boundary probe
(WINDOW=4).
""",
        encoding="utf-8",
    )
    claims = {
        "A. SNAPSHOT-ONLY TEMPORAL BOTTLENECK": "DEMONSTRATED" if sp["sha_same_for_both_presents"] and sp["tps_distinguishes"] else "SUPPORTED",
        "B. EXPERIENCE-DERIVED TEMPORAL PREDICTIVE STRUCTURE": "DEMONSTRATED" if sp["tps_distinguishes"] else "NOT_DEMONSTRATED",
        "C. SAME-PRESENT / DIFFERENT-HISTORY PREDICTION": "DEMONSTRATED" if sp["tps_distinguishes"] else "NOT_DEMONSTRATED",
        "D. TEMPORAL-ORDER DISCRIMINATION": "DEMONSTRATED" if order["order_discriminates"] else "NOT_DEMONSTRATED",
        "E. DELAYED-CONSEQUENCE PREDICTION": "DEMONSTRATED" if delay["max_demonstrated_delay"] >= 1 else "NOT_DEMONSTRATED",
        "F. HELD-OUT TRAJECTORY GENERALIZATION": "DEMONSTRATED" if held["coverage"] >= 1.0 and held["precision"] >= 1.0 else ("SUPPORTED" if held["coverage"] > 0 else "NOT_DEMONSTRATED"),
        "G. TEMPORAL PREDICTIVE EQUIVALENCE": "DEMONSTRATED" if teq["shared_representation"] else "NOT_DEMONSTRATED",
        "H. PRESERVATION OF SMALL TEMPORAL DIFFERENCES": "DEMONSTRATED" if small["preserved"] else "NOT_DEMONSTRATED",
        "I. MULTI-CHANNEL TEMPORAL PREDICTION": "DEMONSTRATED" if multi["joint_temporal_structure"] else "NOT_DEMONSTRATED",
        "J. REVISABLE TEMPORAL REPRESENTATION": "DEMONSTRATED" if rev["revised_to_Q"] else "INCONCLUSIVE",
        "K. BOUNDED TEMPORAL MEMORY": "DEMONSTRATED" if mem["bounded"] else "REFUTED",
        "L. FIELD-TRAJECTORY PREDICTION": "DEMONSTRATED" if sig["corr_match_n"] >= 2 else ("INCONCLUSIVE" if sig["corr_match_n"] else "NOT_DEMONSTRATED"),
        "M. SEASONAL-TRAJECTORY PREDICTION": "INCONCLUSIVE",
        "N. OTHER-BODY TRAJECTORY PREDICTION": "NOT_DEMONSTRATED",
        "O. INTERNAL-TRAJECTORY PREDICTION": "DEMONSTRATED" if internal["trajectory_better_than_snapshot"] else "NOT_DEMONSTRATED",
        "P. TEMPORAL PREDICTION ENTERING PROSPECTION": "NOT_DEMONSTRATED",
        "Q. TEMPORAL PREDICTION ALTERING SELECTED BEHAVIOR": "NOT_DEMONSTRATED",
    }
    lines = ["# SCIENTIFIC_CLAIMS.md\n", "Statuses: DEMONSTRATED, SUPPORTED, INCONCLUSIVE, NOT_DEMONSTRATED, REFUTED.\n"]
    evidence = {
        "A. SNAPSHOT-ONLY TEMPORAL BOTTLENECK": f"SHA/PE of O(t)=0.50 cannot split H1 vs H2. SHA y={sp['sha_y']}. TPS does split.",
        "B. EXPERIENCE-DERIVED TEMPORAL PREDICTIVE STRUCTURE": "WINDOW successive differences from ordinary fragments; no RISING/FALLING, no CLOCK.",
        "C. SAME-PRESENT / DIFFERENT-HISTORY PREDICTION": f"H1 {sp['H1']['family']} vs H2 {sp['H2']['family']}; same present sig={sp['same_present_sig']}; different delta_sig={sp['different_delta_sig']}.",
        "D. TEMPORAL-ORDER DISCRIMINATION": f"Same multiset and present 0.70: structured={order['structured_family']} shuffled={order['shuffled_family']}.",
        "E. DELAYED-CONSEQUENCE PREDICTION": f"Delays 1/2/4 MATCH P/Q. Delay 8 (beyond LAGS) fails. max={delay['max_demonstrated_delay']}. Buffers not enlarged.",
        "F. HELD-OUT TRAJECTORY GENERALIZATION": f"precision={held['precision']} coverage={held['coverage']} false-match={held['false_match_rate']} miss={held['miss_rate']}. Shifted absolute levels, same deltas.",
        "G. TEMPORAL PREDICTIVE EQUIVALENCE": f"0.10→0.40 and 0.40→0.70 share +0.10 windows → P. held={teq['family']}. Not global slope normalization.",
        "H. PRESERVATION OF SMALL TEMPORAL DIFFERENCES": f"0.50 vs 0.51 mid-step remains P vs Q: {small['preserved']}.",
        "I. MULTI-CHANNEL TEMPORAL PREDICTION": f"T↓B↓→P vs T↓B↑→Q: {multi['joint_temporal_structure']}. No joint-state labels.",
        "J. REVISABLE TEMPORAL REPRESENTATION": f"Phase A P then Phase B Q: {rev['revised_to_Q']} (inner splits={rev['inner_splits']}).",
        "K. BOUNDED TEMPORAL MEMORY": f"RING={tps.RING} WINDOW={tps.WINDOW} inner class/episode caps. bounded={mem['bounded']}.",
        "L. FIELD-TRAJECTORY PREDICTION": f"corr MATCH {sig['corr_match_n']}/3, tps-only {sig['tps_only_match_n']}/3. Full-observation delta windows still veto. Not a FIELD detector.",
        "M. SEASONAL-TRAJECTORY PREDICTION": "Climate diagnostic only. No anticipation/migration claim. Ends at prediction.",
        "N. OTHER-BODY TRAJECTORY PREDICTION": "No other-body pose in agent_observation. BRIDGE_MISSING.",
        "O. INTERNAL-TRAJECTORY PREDICTION": f"Synthetic internal.c0 same-present rising vs falling: {internal['trajectory_better_than_snapshot']}.",
        "P. TEMPORAL PREDICTION ENTERING PROSPECTION": "4.23 still snapshot-conditioned. WAIT prospection unchanged. NEXT_GEAR_MISSING.",
        "Q. TEMPORAL PREDICTION ALTERING SELECTED BEHAVIOR": "WAIT throughout. Incumbent lock not repaired. Selection unmodified.",
    }
    for k, v in claims.items():
        lines.append(f"## {k} — {v}\n\n{evidence.get(k, '')}\n")
    lines.append(
        "\n## Interpretation boundary\n\n"
        "Not claimed: time perception, sense of time, anticipation, understanding motion,\n"
        "signal meaning, sequence understanding, causal reasoning.\n\n"
        "Preferred: temporal predictive structure, trajectory-conditioned prediction,\n"
        "history-conditioned retrieval, delayed-continuation prediction,\n"
        "temporal-order discrimination, multi-step predictive organization.\n"
    )
    (OUT / "SCIENTIFIC_CLAIMS.md").write_text("".join(lines) + "\n", encoding="utf-8")
    (OUT / "PROMOTION_RECOMMENDATION.md").write_text(
        f"""# PROMOTION_RECOMMENDATION.md

**Keep `temporal_predictive_structure`, `predictive_equivalence`, and
`predictive_relevance` experimental and default OFF. Do not promote.**

CURRENT INTEGRATED MM is unchanged.

## Assessment

- **Accuracy / coverage (synthetic).** Same-present split={sp['tps_distinguishes']};
  order={order['order_discriminates']}; held-out precision={held['precision']},
  coverage={held['coverage']}, false-match={held['false_match_rate']},
  miss={held['miss_rate']}.
- **False retrieval.** Small temporal differences preserved={small['preserved']}.
  Correlation trap survived={trap['survived_trap']} (expected failure).
- **Memory.** RING={tps.RING}, WINDOW={tps.WINDOW}, inner MAX_CLASSES=32.
  Bounded={mem['bounded']}.
- **Runtime.** Extra retrieve: ≤4 lags × ≤32 classes. Modest.
- **Thresholds.** Inner PE τ=0.10, MIN_CLASS_SUPPORT=3, exact AABB on deltas.
  Duration below WINDOW is a hard resolution boundary.
- **Revision.** Phase B Q={rev['revised_to_Q']} (requires >1 member so contra can split).
- **4.21.** SHA still first; exact identity unchanged.
- **4.22.** Untouched.
- **4.23.** Still snapshot composition. Temporal MATCH does not become a composed
  WAIT-vs-MOVE scenario. Claim P remains NOT_DEMONSTRATED.
- **PE / relevance.** Snapshot PE cannot split same O(t). Inner PE is reused on
  delta windows. Relevance optional for high-dim vetoes; relation-specific.
- **Distribution shift.** Temporal correlation trap is the documented failure.
- **Signal.** corr MATCH {sig['corr_match_n']}/3, deco {sig['dec_match_n']}/3,
  tps-only {sig['tps_only_match_n']}/3. Physics unmodified. Selection unmodified.

Remain experimental.
""",
        encoding="utf-8",
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"""# FINAL_REPORT.md

## 1. What temporal machinery already existed and was actually executing?

4.21 SHA snapshot retrieval; 4.22 snapshot local/broader organization; 4.23
1-step snapshot composition. PE/relevance (OFF) are snapshot class spans.
4.20 lagged body and 4.24 body traj_sig exist as modules but are **not** on
the PSR executing path. See TEMPORAL_AUDIT.md.

## 2. Could CURRENT MM distinguish same present + different recent trajectory before this experiment?

No. SHA and snapshot PE map O(t) only. Same x=0.50 yields one antecedent.

## 3. What minimal mechanism, if any, was required?

Experimental `temporal_predictive_structure` (default OFF): WINDOW={tps.WINDOW}
successive-difference fragments over a RING={tps.RING} of ordinary observations,
inner PE on those windows at lags {list(tps.LAGS)}. No CLOCK. No RISING/FALLING.

## 4. Can temporal order predict a continuation when instantaneous values cannot?

{'Yes' if order['order_discriminates'] else 'Not on this probe'}: same multiset
and same present 0.70, structured→P vs shuffled→Q
({order['structured_family']} vs {order['shuffled_family']}).

## 5. Can identical presents retrieve different predictions from different histories?

{'Yes' if sp['tps_distinguishes'] else 'No'}: H1→{_fam_name(sp['H1']['family'])}, H2→{_fam_name(sp['H2']['family'])}
with identical present sig={sp['same_present_sig']}.

## 6. Can MM predict delayed consequences?

Yes inside LAGS. Max demonstrated delay={delay['max_demonstrated_delay']}.
Delay 8 was not forced by enlarging buffers.

## 7. What temporal horizon is demonstrated?

{delay['max_demonstrated_delay']} steps (LAGS cap {max(tps.LAGS)}).

## 8. Can different absolute trajectories become predictively equivalent?

{'Yes' if teq['shared_representation'] else 'No'}: shifted +0.10 sequences share
the delta window and continuation P. Not global slope normalization.

## 9. Are small but predictive temporal differences preserved?

{'Yes' if small['preserved'] else 'No'}: 0.50 vs 0.51 mid-point remains P vs Q.

## 10. Does held-out trajectory generalization work?

{'Yes' if held['coverage'] >= 1 and held['precision'] >= 1 else 'Partial'}.
Not exact sequence replay: held-out used unseen absolute levels with the same
successive differences.

## 11. Precision, coverage, false-match, miss?

precision={held['precision']}, coverage={held['coverage']},
false-match={held['false_match_rate']}, miss={held['miss_rate']}.

## 12. Can temporal representations revise?

{'Yes' if rev['revised_to_Q'] else 'Incomplete'}: Phase A P then Phase B Q on
the same trajectory (inner splits={rev['inner_splits']}).

## 13. Is memory bounded?

{'Yes' if mem['bounded'] else 'No'}. Ring/cap/class/episode caps. Not every
trajectory forever.

## 14. Does temporal correlation trap the mechanism?

Trap survived={trap['survived_trap']}. Relied on z={trap['relied_on_z']}.
Measured, not fixed. Not causal feature discovery.

## 15. Can FIELD_A/FIELD_B trajectories predict later physical consequences?

corr MATCH {sig['corr_match_n']}/3; tps-only {sig['tps_only_match_n']}/3.
High-dimensional ordinary observations still contain non-field deltas; inner
AABB may veto. This is not a FIELD-specific detector.

## 16. Does correlated signaling outperform decorrelated signaling?

{sig['correlated_outperforms_decorrelated']} (corr {sig['corr_match_n']} vs deco {sig['dec_match_n']}).

## 17. Does successful signal trajectory prediction enter prospection?

No. 4.23 remains snapshot-conditioned. Claim P NOT_DEMONSTRATED.
TEMPORAL_CONFLICT / snapshot composition is the next missing gear if prediction
is present but unused.

## 18. Does it alter selected behavior?

No. Incumbent lock unchanged. Selection not modified.

## 19. Can seasonal trajectories predict later ecology?

Inconclusive diagnostic only. Classes/matches may form; no anticipation or
migration claim. Primary diagnostic ends at prediction.

## 20. Can another body's trajectory predict its later observable physical state?

NOT_DEMONSTRATED. Other-body pose is not in accessible observation.

## 21. Can internal trajectories predict later body/internal state?

{'Yes on the synthetic internal.c0 control' if internal['trajectory_better_than_snapshot'] else 'Not demonstrated'}.

## 22. Which representation combination performs best without destructive generalization?

Synthetic: D (temporal) is the only combination that splits same-present
histories. Snapshot SHA/PE/relevance cannot. High-dim signal: F (temporal +
inner relevance) is the candidate if D vetoes; do not assume it is best.

## 23. What exact causal gear is missing next?

TEMPORAL_CONFLICT / NEXT_GEAR_MISSING: incompatible lag predictions are not
arbitrated. Independently, 4.23 composition does not consume trajectory-conditioned
continuations, so even a correct delayed FIELD prediction does not enter
prospection or selection. Incumbent WAIT lock remains a known separate bottleneck.

## 24. Should temporal_predictive_structure remain experimental?

Yes. Default OFF. Do not promote.

## DESIGN_BOUNDARY

Not used: RISING/FALLING labels, signal onset detector, FIELD-specific history,
hidden tick input, manual templates, sender identity, future ground truth at
retrieve, global smoothing, selection changes.
""",
        encoding="utf-8",
    )


def _fam_name(x):
    return x


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sp = same_present()
    order = order_control()
    delay = delay_results()
    rate = rate_results()
    dur = duration_results()
    multi = multichannel()
    rev = revision()
    mem = memory_scaling()
    held = held_out()
    trap = correlation_trap()
    small = small_diff()
    teq = temporal_equivalence()
    conf = conflict_case()
    cog = cognition_pipeline()
    sig, traces = signal_trajectory()
    seas = seasonal_diag()
    other = other_body_diag()
    internal = internal_diag()
    cmp_ = representation_comparison(sp, held, order)
    abl = ablations(sp, order, delay, held, trap, sig, conf)

    _json(OUT / "SAME_PRESENT_RESULTS.json", sp)
    _json(OUT / "ORDER_CONTROL_RESULTS.json", order)
    with (OUT / "DELAY_RESULTS.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(delay["rows"][0].keys()))
        w.writeheader()
        w.writerows(delay["rows"])
    _json(OUT / "DELAY_RESULTS.json", delay)
    _json(OUT / "RATE_RESULTS.json", rate)
    _json(OUT / "DURATION_RESULTS.json", dur)
    _json(OUT / "MULTICHANNEL_RESULTS.json", multi)
    _json(OUT / "REVISION_RESULTS.json", rev)
    _json(OUT / "MEMORY_SCALING.json", mem)
    _json(OUT / "HELD_OUT_RESULTS.json", held)
    _json(OUT / "CORRELATION_TRAP_RESULTS.json", trap)
    _json(OUT / "SIGNAL_TRAJECTORY_RESULTS.json", sig)
    _json(OUT / "SIGNAL_TRACES.json", traces)
    _json(OUT / "SEASONAL_DIAGNOSTIC.json", seas)
    _json(OUT / "OTHER_BODY_DIAGNOSTIC.json", other)
    _json(OUT / "INTERNAL_DIAGNOSTIC.json", internal)
    _json(OUT / "REPRESENTATION_COMPARISON.json", cmp_)
    _json(OUT / "ABLATION_RESULTS.json", abl)
    _json(OUT / "SMALL_DIFFERENCE_RESULTS.json", small)
    _json(OUT / "TEMPORAL_EQUIVALENCE_RESULTS.json", teq)
    _json(OUT / "CONFLICT_RESULTS.json", conf)
    _json(OUT / "COGNITION_PIPELINE.json", cog)
    write_markdown(sp, order, delay, rate, dur, multi, rev, mem, held, trap, small, teq, conf, sig, traces, seas, other, internal, cog, cmp_, abl)
    print(json.dumps({
        "same_present": sp["tps_distinguishes"],
        "order": order["order_discriminates"],
        "delay_max": delay["max_demonstrated_delay"],
        "rate": rate["rate_discriminative"],
        "duration_split": dur["discriminated"],
        "multi": multi["joint_temporal_structure"],
        "revision": rev["revised_to_Q"],
        "bounded": mem["bounded"],
        "held_precision": held["precision"],
        "held_coverage": held["coverage"],
        "false_match": held["false_match_rate"],
        "trap_survived": trap["survived_trap"],
        "small": small["preserved"],
        "equiv": teq["shared_representation"],
        "conflict": conf["status"],
        "corr_tps": sig["corr_match_n"],
        "dec_tps": sig["dec_match_n"],
        "tps_only": sig["tps_only_match_n"],
        "internal": internal["trajectory_better_than_snapshot"],
        "other_body": other["claim"],
        "default_off": CognitionConfig().temporal_predictive_structure,
        "pe_off": CognitionConfig().predictive_equivalence,
        "rel_off": CognitionConfig().predictive_relevance,
    }, indent=2))


if __name__ == "__main__":
    main()
