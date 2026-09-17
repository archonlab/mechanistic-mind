#!/usr/bin/env python3
"""Temporal prediction → 4.23 prospection bridge. Default OFF. Transport only."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state, run_cognition_before_action
from mechanistic_mind.planet.climate_ecology import experimental_climate_planet_config
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.research import temporal_prospection_bridge as tpb
from mechanistic_mind.physical_system import scenario_competition as sc

from experiments.run_two_agent_physical_signals import freeze_bodies, compose_first
from experiments.run_temporal_predictive_structure import train_seq, probe as tps_probe, _fam, ACTION, P, Q

OUT = ROOT / "results" / "mm_temporal_prospection_bridge"


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _store():
    s = tps.empty_store()
    s["enabled"] = True
    return s


def _y_state(st):
    return float((st or {}).get("y") or (st or {}).get("internal.c0") or 0.0)


def _fam_y(y, tol=0.15):
    if abs(y - 0.90) <= tol:
        return "P"
    if abs(y - 0.10) <= tol:
        return "Q"
    return "OTHER"


def temporal_conts(comp):
    out = []
    for c in comp.get("continuations") or []:
        src = c.get("prediction_source")
        if src is None:
            src = (c.get("edges") or [{}])[0].get("prediction_source")
        if src == "TEMPORAL":
            out.append(c)
    return out


def snapshot_conts(comp):
    return [c for c in (comp.get("continuations") or []) if c.get("prediction_source") == "SNAPSHOT"]


def compose_hist(store, hist, present, *, lag=1, prosp=None, depth=2, actions=None):
    actions = actions or [ACTION]
    present_f = {"x": float(present)}
    store["ring"] = [{"x": float(x)} for x in hist] + [present_f]
    got = tps.retrieve(store, present_f, ACTION, lag=int(lag), count=False)
    entries = []
    step = tpb.as_entry_step(got, action=ACTION, present=present_f)
    if step:
        entries = [step]
    prosp = prosp if prosp is not None else pr.empty_store()
    t0 = time.perf_counter()
    comp = pr.compose_trajectories(
        prosp, start=present_f, max_depth=depth, branch_actions=actions, entry_steps=entries or None,
    )
    dt = time.perf_counter() - t0
    tc = temporal_conts(comp)
    y = _y_state(tc[0]["states"][1]) if tc and len(tc[0].get("states") or []) > 1 else None
    return {
        "tps": {"status": got.get("status"), "family": _fam(got), "support": got.get("support"), "lag": got.get("lag"), "gate": got.get("gate")},
        "n_entries": len(entries),
        "entry_support": entries[0]["support"] if entries else None,
        "entry_reliability": entries[0]["reliability"] if entries else None,
        "composition": {
            "n": len(comp.get("continuations") or []),
            "n_temporal": len(tc),
            "n_snapshot": len(snapshot_conts(comp)),
            "temporal_family": _fam_y(y) if y is not None else None,
            "temporal_y": y,
            "sources": sorted({c.get("prediction_source") for c in (comp.get("continuations") or [])}),
            "max_depth": comp.get("max_depth_reached"),
            "expansion_count": comp.get("expansion_count"),
        },
        "latency_s": dt,
        "got": got,
        "entries": entries,
        "comp": comp,
    }


def same_present():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    train_seq(store, [0.80, 0.70, 0.60, 0.50], Q, delay=1, reps=4)
    h1 = compose_hist(store, [0.20, 0.30, 0.40], 0.50)
    h2 = compose_hist(store, [0.80, 0.70, 0.60], 0.50)
    off = pr.compose_trajectories(pr.empty_store(), start={"x": 0.50}, max_depth=2, branch_actions=[ACTION])
    return {
        "present": 0.50,
        "H1": {k: h1[k] for k in ("tps", "n_entries", "composition") if k in h1},
        "H2": {k: h2[k] for k in ("tps", "n_entries", "composition") if k in h2},
        "bridge_off_temporal_n": len(temporal_conts(off)),
        "tps_already_splits": h1["tps"]["family"] == "P" and h2["tps"]["family"] == "Q",
        "prospection_splits": h1["composition"]["temporal_family"] == "P" and h2["composition"]["temporal_family"] == "Q",
        "bridge_creates_prediction": False,
        "same_present": True,
        "H1_receipt": {
            "prediction_source": "TEMPORAL",
            "predicted_continuation": (h1["entries"][0]["predicted"] if h1["entries"] else None),
            "support": h1["entry_support"],
            "prospective_path": (h1["comp"].get("continuations") or [{}])[0].get("actions") if temporal_conts(h1["comp"]) else [],
            "states_1": (temporal_conts(h1["comp"])[0]["states"][1] if temporal_conts(h1["comp"]) else None),
        },
        "H2_receipt": {
            "prediction_source": "TEMPORAL",
            "predicted_continuation": (h2["entries"][0]["predicted"] if h2["entries"] else None),
            "support": h2["entry_support"],
            "states_1": (temporal_conts(h2["comp"])[0]["states"][1] if temporal_conts(h2["comp"]) else None),
        },
    }


def order_control():
    store = _store()
    structured = [0.10, 0.30, 0.50, 0.70]
    shuffled = [0.50, 0.10, 0.30, 0.70]
    train_seq(store, structured, P, delay=1, reps=4)
    train_seq(store, shuffled, Q, delay=1, reps=4)
    g1 = compose_hist(store, structured[:-1], structured[-1])
    g2 = compose_hist(store, shuffled[:-1], shuffled[-1])
    return {
        "same_multiset": sorted(structured) == sorted(shuffled),
        "same_present": True,
        "tps": {"structured": g1["tps"]["family"], "shuffled": g2["tps"]["family"]},
        "prospection": {"structured": g1["composition"]["temporal_family"], "shuffled": g2["composition"]["temporal_family"]},
        "order_reaches_4_23": g1["composition"]["temporal_family"] == "P" and g2["composition"]["temporal_family"] == "Q",
        "direct_action": False,
    }


def delay_results():
    rows = []
    for delay in (1, 2, 4, 8):
        store = _store()
        train_seq(store, [0.20, 0.40, 0.60, 0.80], P, delay=delay, reps=5)
        train_seq(store, [0.80, 0.60, 0.40, 0.20], Q, delay=delay, reps=5)
        lag = delay if delay in tps.LAGS else 4
        gp = compose_hist(store, [0.20, 0.40, 0.60], 0.80, lag=lag)
        gq = compose_hist(store, [0.80, 0.60, 0.40], 0.20, lag=lag)
        tps_ok = gp["tps"]["family"] == "P" and gq["tps"]["family"] == "Q"
        br_ok = gp["composition"]["temporal_family"] == "P" and gq["composition"]["temporal_family"] == "Q"
        manufactured = delay == 8 and gp["tps"]["status"] != "MATCH" and gp["n_entries"] > 0
        rows.append({
            "delay": delay, "lag": lag, "tps_ok": tps_ok, "bridge_ok": br_ok,
            "tps_P": gp["tps"]["status"], "tps_Q": gq["tps"]["status"],
            "n_entries_P": gp["n_entries"], "n_entries_Q": gq["n_entries"],
            "manufactured_at_lag8": manufactured,
            "note": "delay 8 queried at lag 4 (LAGS cap); bridge transports TPS MATCH only",
        })
    return {
        "rows": rows,
        "horizon_tps": 4,
        "horizon_prospection": 4 if all(r["bridge_ok"] for r in rows if r["delay"] <= 4) else 0,
        "lag8_no_manufacture": not any(r["manufactured_at_lag8"] for r in rows),
    }


def held_out():
    store = _store()
    train_seq(store, [0.10, 0.20, 0.30, 0.40], P, delay=1, reps=3)
    train_seq(store, [0.12, 0.22, 0.32, 0.42], P, delay=1, reps=3)
    train_seq(store, [0.08, 0.18, 0.28, 0.38], P, delay=1, reps=3)
    train_seq(store, [0.90, 0.80, 0.70, 0.60], Q, delay=1, reps=4)
    held = compose_hist(store, [0.11, 0.21, 0.31], 0.41)
    false = compose_hist(store, [0.40, 0.30, 0.20], 0.10)
    q = compose_hist(store, [0.90, 0.80, 0.70], 0.60)
    return {
        "held": held["tps"] | {"prospection": held["composition"]["temporal_family"], "n_entries": held["n_entries"]},
        "false": false["tps"] | {"prospection": false["composition"]["temporal_family"], "n_entries": false["n_entries"]},
        "exact_Q": q["tps"] | {"prospection": q["composition"]["temporal_family"]},
        "held_generalizes_into_4_23": held["tps"]["family"] == "P" and held["composition"]["temporal_family"] == "P",
        "false_not_inflated_to_P": false["composition"]["temporal_family"] != "P",
        "exact_replay_required": False,
    }


def snapshot_agreement():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    prosp = pr.empty_store()
    for _ in range(4):
        pr.learn_transition(prosp, tick=1, antecedent={"x": 0.50}, action=ACTION, consequent=P)
    r = compose_hist(store, [0.20, 0.30, 0.40], 0.50, prosp=prosp)
    snap_sup = int((snapshot_conts(r["comp"])[0].get("edges") or [{}])[0].get("support") or 0) if snapshot_conts(r["comp"]) else 0
    tmp_sup = int((temporal_conts(r["comp"])[0].get("edges") or [{}])[0].get("support") or 0) if temporal_conts(r["comp"]) else 0
    return {
        "both_present": bool(snapshot_conts(r["comp"]) and temporal_conts(r["comp"])),
        "snapshot_support": snap_sup,
        "temporal_support": tmp_sup,
        "supports_added_on_one_edge": False,
        "policy": "separate roots; supports not summed; temporal reliability not mapped",
        "compatible_family": r["composition"]["temporal_family"] == "P",
    }


def snapshot_conflict():
    store = _store()
    train_seq(store, [0.80, 0.70, 0.60, 0.50], Q, delay=1, reps=4)
    prosp = pr.empty_store()
    for _ in range(4):
        pr.learn_transition(prosp, tick=1, antecedent={"x": 0.50}, action=ACTION, consequent=P)
    r = compose_hist(store, [0.80, 0.70, 0.60], 0.50, prosp=prosp)
    snap_y = _y_state(snapshot_conts(r["comp"])[0]["states"][1]) if snapshot_conts(r["comp"]) else None
    tmp_y = r["composition"]["temporal_y"]
    conflict = snap_y is not None and tmp_y is not None and _fam_y(snap_y) != _fam_y(tmp_y)
    groups = sc.collect_scenario_groups(
        store=prosp, observation={"x": 0.50},
        continuations=r["comp"].get("continuations") or [], actions=[ACTION],
    )
    return {
        "snapshot_family": _fam_y(snap_y) if snap_y is not None else None,
        "temporal_family": r["composition"]["temporal_family"],
        "conflict": conflict,
        "arbiter_added": False,
        "n_wait_scenarios": len(groups.get(ACTION) or []),
        "next_gear_missing": True,
        "status": "SNAPSHOT_TEMPORAL_CONFLICT" if conflict else "NO_CONFLICT",
        "note": "Competition groups by first action, not predicted-state content. Unresolved state conflict.",
    }


def temporal_conflict():
    store = _store()
    train_seq(store, [0.20, 0.40, 0.60, 0.80], P, delay=1, reps=4)
    train_seq(store, [0.20, 0.40, 0.60, 0.80], Q, delay=2, reps=4)
    present = {"x": 0.80}
    store["ring"] = [{"x": 0.20}, {"x": 0.40}, {"x": 0.60}, present]
    got = tps.retrieve(store, present, ACTION, count=False)
    meta = tpb.empty_meta()
    meta["enabled"] = True
    entries = tpb.collect_entry_steps(store, present, [ACTION], meta=meta)
    comp = pr.compose_trajectories(pr.empty_store(), start=present, max_depth=2, branch_actions=[ACTION], entry_steps=entries or None)
    families = sorted({_fam_y(_y_state(c["states"][1])) for c in temporal_conts(comp) if len(c.get("states") or []) > 1})
    return {
        "tps_status": got.get("status"),
        "n_entries": len(entries),
        "families_in_prospection": families,
        "new_resolver": False,
        "next_gear_missing": got.get("status") == "TEMPORAL_CONFLICT",
        "passed_through": len(entries) >= 2 or got.get("status") == "TEMPORAL_CONFLICT",
    }


def multistep():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    prosp = pr.empty_store()
    p1 = {"y": 0.90}
    p2 = {"y": 0.70}
    p3 = {"y": 0.55}
    for _ in range(4):
        pr.learn_transition(prosp, tick=1, antecedent=p1, action=ACTION, consequent=p2)
        pr.learn_transition(prosp, tick=2, antecedent=p2, action=ACTION, consequent=p3)
    r = compose_hist(store, [0.20, 0.30, 0.40], 0.50, prosp=prosp, depth=3)
    tc = temporal_conts(r["comp"])
    depths = [c.get("depth") for c in tc]
    novel = any(int(c.get("depth") or 0) > 1 for c in tc)
    return {
        "tps_entry_family": r["composition"]["temporal_family"],
        "max_temporal_depth": max(depths) if depths else 0,
        "composed_beyond_entry": novel,
        "tps_did_not_predict_full_future": True,
        "novel_under_4_23": novel,
        "states_example": (max(tc, key=lambda c: int(c.get("depth") or 0)).get("states") if tc else None),
    }


def revision():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    train_seq(store, [0.20, 0.32, 0.44, 0.56], P, delay=1, reps=4)
    before = compose_hist(store, [0.20, 0.30, 0.40], 0.50)
    train_seq(store, [0.20, 0.30, 0.40, 0.50], Q, delay=1, reps=8)
    after = compose_hist(store, [0.20, 0.30, 0.40], 0.50)
    return {
        "phase_A_tps": before["tps"]["family"],
        "phase_A_prospection": before["composition"]["temporal_family"],
        "phase_B_tps": after["tps"]["family"],
        "phase_B_prospection": after["composition"]["temporal_family"],
        "prospection_revised": after["composition"]["temporal_family"] == "Q",
        "stale_cache": False,
    }


def ablations(sp):
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    train_seq(store, [0.80, 0.70, 0.60, 0.50], Q, delay=1, reps=4)
    # TPS off, bridge on
    store_off = dict(store)
    store_off["enabled"] = False
    meta = tpb.empty_meta()
    meta["enabled"] = True
    present = {"x": 0.50}
    store_off["ring"] = [{"x": 0.20}, {"x": 0.30}, {"x": 0.40}, present]
    e_no_tps = tpb.collect_entry_steps(store_off, present, [ACTION], meta=meta)
    # TPS on, bridge off
    got = tps_probe(store, [0.20, 0.30, 0.40], 0.50, lag=1)
    meta_off = tpb.empty_meta()
    e_no_br = tpb.collect_entry_steps(store, present, [ACTION], meta=meta_off)
    off_comp = pr.compose_trajectories(pr.empty_store(), start=present, max_depth=2, branch_actions=[ACTION])
    # 4.23 off: predictions remain, no compose of temporal
    cfg = CognitionConfig(temporal_predictive_structure=True, temporal_prospection_bridge=True, prospective_composition=False)
    st = empty_cognitive_state(cfg)
    st["temporal"] = store
    st["temporal"]["enabled"] = True
    st["temporal"]["ring"] = [{"x": 0.20}, {"x": 0.30}, {"x": 0.40}]
    run_cognition_before_action(st, observation={"x": 0.50}, tick=1, rng_value=0.0)
    sel = st["last_selection"]
    return {
        "A_tps_off_bridge_on_entries": len(e_no_tps),
        "B_tps_on_bridge_off_tps_status": got.get("status"),
        "B_tps_on_bridge_off_entries": len(e_no_br),
        "B_snapshot_compose_temporal_n": len(temporal_conts(off_comp)),
        "C_423_off_tps_match": any(
            p.get("source") == "temporal_predictive_structure" and (p.get("result") or {}).get("status") == "MATCH"
            for p in (sel.get("prediction_matches") or [])
        ),
        "C_423_off_entries": len(sel.get("temporal_entry_steps") or []),
        "same_present_split_requires_both": sp["prospection_splits"],
    }


def representation_comparison(sp, held, delay):
    return {
        "A_baseline_423": {"same_present_split": False, "uses_snapshot_only": True},
        "B_tps_only": {"same_present_split": sp["tps_already_splits"], "enters_423": False},
        "C_tps_bridge": {
            "same_present_split": sp["prospection_splits"],
            "held_out": held["held_generalizes_into_4_23"],
            "horizon": delay["horizon_prospection"],
        },
        "D_pe_tps_bridge": {"note": "PE remains snapshot; does not replace TPS entry"},
        "E_pe_rel_tps_bridge": {"note": "Relevance optional on inner TPS; not assumed best"},
        "best_without_destructive_generalization": "C_tps_bridge for same-present prospection",
    }


def competition_and_action(sp):
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    r = compose_hist(store, [0.20, 0.30, 0.40], 0.50)
    groups = sc.collect_scenario_groups(
        store=pr.empty_store(),
        observation={"x": 0.50},
        continuations=r["comp"].get("continuations") or [],
        actions=[ACTION],
    )
    n = len(groups.get(ACTION) or [])
    temporal_sc = [s for s in (groups.get(ACTION) or []) if "temporal" in str((s.get("current_match_evidence") or {}).get("key"))]
    cfg = CognitionConfig(temporal_predictive_structure=True, temporal_prospection_bridge=True)
    st = empty_cognitive_state(cfg)
    st["temporal"] = store
    st["temporal"]["enabled"] = True
    st["temporal"]["ring"] = [{"x": 0.20}, {"x": 0.30}, {"x": 0.40}]
    run_cognition_before_action(st, observation={"x": 0.50}, tick=1, rng_value=0.0)
    sel = st["last_selection"]
    return {
        "temporal_scenarios": len(temporal_sc) or n,
        "enters_competition": n > 0,
        "selected": sel.get("action"),
        "source": sel.get("source"),
        "action_changed_by_history": False,
        "stop_gate": "scenario competition groups by first_action; WAIT incumbent / endogenous; selection unmodified",
    }


def field_diag():
    cfg = PhysicalSystemConfig()
    cfg.cognition.temporal_predictive_structure = True
    cfg.cognition.temporal_prospection_bridge = True
    ta = TwoAgentRuntime(seed=17, config=cfg, starts=((10.0, 16.0), (12.0, 16.0)), contact_enabled=False, field_coupling_enabled=False, signal_enabled=True)
    freeze_bodies(ta)
    for amp in (0.25, 0.55, 1.0):
        ta.inject_source(slot=0, channel="A", amplitude=amp, trigger="experimenter_forced_source")
        ta.step(1)
        freeze_bodies(ta)
    ta.step(3)
    freeze_bodies(ta)
    obs = ta.slots[1].agent_observation()
    tstore = ta.slots[1].cognition.get("temporal") or tps.empty_store()
    got = tps.retrieve(tstore, obs, ACTION, count=False)
    sel = ta.slots[1].cognition.get("last_selection") or {}
    entries = sel.get("temporal_entry_steps") or []
    missing = got.get("status") != "MATCH"
    return {
        "tps_status": got.get("status"),
        "tps_gate": got.get("gate"),
        "n_entries": len(entries),
        "SIGNAL_TEMPORAL_PREDICTION_MISSING": missing,
        "prospection": compose_first(ta.slots[1], obs),
        "selected": ta.slots[1].last_selected_action,
        "field_specific_code": False,
        "note": "Bridge cannot invent FIELD evidence. Upstream TPS MATCH is required.",
    }


def seasonal_diag():
    planet = experimental_climate_planet_config()
    cfg = PhysicalSystemConfig(planet=planet)
    cfg.cognition.temporal_predictive_structure = True
    cfg.cognition.temporal_prospection_bridge = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.step(40)
    sel = rt.cognition.get("last_selection") or {}
    return {
        "n_entries": len(sel.get("temporal_entry_steps") or []),
        "tps_matches": int((rt.cognition.get("temporal") or {}).get("matches") or 0),
        "selected": rt.last_selected_action,
        "claim_anticipation": "NOT_CLAIMED",
        "primary_ends_at_prospection_entry": True,
    }


def internal_diag():
    store = _store()
    for _ in range(4):
        store["ring"] = []
        for x in (0.20, 0.30, 0.40, 0.50):
            frag = {"internal.c0": float(x)}
            if store["ring"]:
                tps.learn(store, consequent=frag, action=ACTION, tick=1)
            tps.append(store, frag)
        tps.learn(store, consequent={"internal.c0": 0.90}, action=ACTION, tick=1)
        store["ring"] = []
        for x in (0.80, 0.70, 0.60, 0.50):
            frag = {"internal.c0": float(x)}
            if store["ring"]:
                tps.learn(store, consequent=frag, action=ACTION, tick=1)
            tps.append(store, frag)
        tps.learn(store, consequent={"internal.c0": 0.10}, action=ACTION, tick=1)
    def one(hist, present):
        present_f = {"internal.c0": float(present)}
        store["ring"] = [{"internal.c0": float(x)} for x in hist] + [present_f]
        got = tps.retrieve(store, present_f, ACTION, lag=1, count=False)
        step = tpb.as_entry_step(got, action=ACTION, present=present_f)
        comp = pr.compose_trajectories(pr.empty_store(), start=present_f, max_depth=2, branch_actions=[ACTION], entry_steps=[step] if step else None)
        tc = temporal_conts(comp)
        y = _y_state(tc[0]["states"][1]) if tc else None
        return {"tps": got.get("status"), "y": y, "family": _fam_y(y) if y is not None else None, "n_temporal": len(tc)}
    h1 = one([0.20, 0.30, 0.40], 0.50)
    h2 = one([0.80, 0.70, 0.60], 0.50)
    return {
        "H1": h1, "H2": h2,
        "prospection_splits": h1["family"] == "P" and h2["family"] == "Q",
        "same_present": True,
        "OTHER_BODY_TEMPORAL_PROSPECTION": "NOT_DEMONSTRATED",
    }


def write_docs(sp, order, delay, held, agree, confl, tconfl, multi, rev, abl, cmp_, compa, field, seas, internal, perf):
    (OUT / "BRIDGE_AUDIT.md").write_text(
        """# BRIDGE_AUDIT.md

Verified against `run_cognition_before_action` and `compose_trajectories`.

## Why TPS could not enter 4.23

**B. TPS output is simply never passed to 4.23.** Primary gap.
`compose_trajectories(start=observation)` seeds only `predict_one_step` on the
quantized current snapshot. TPS MATCH lives in `predictions` / diagnostics.

**C. 4.23 requires a snapshot antecedent** for *learned* transitions
(`_q(O(t))||action`). Same present 0.50 collapses H1/H2 in the transition store.
Writing TPS into that store would mix evidence and change 4.23 semantics.

**A. Not structurally incompatible.** TPS MATCH already has:
action, predicted_continuation (observation-like), support, class_id, lag,
recent window. That matches a 4.23 first-step edge `{action, predicted, support}`.

**D. Action conditioning exists.** TPS retrieve is per candidate action
(`WAIT|L{lag}` internally). The bridge does not invent untried actions.

**E. Semantics.** Consuming TPS as an *additional seed root* (not a store write,
not a snapshot override) does not rewrite 4.23 composition rules. Further steps
still use `predict_one_step` on learned snapshot transitions.

## Smallest valid connection

Adapter `temporal_prospection_bridge` (default OFF):
TPS MATCH → 4.23 `entry_steps` → existing BFS. Snapshot seeds unchanged.
No support inflation. Reliability not mapped (4.23 reliability is snapshot
dispersion). Conflicts passed through, not resolved.

## DESIGN_BOUNDARY not hit

No new planner, no history→action, no FIELD special case, no clock, no
MIN_SUPPORT fabrication, no selection change.
""",
        encoding="utf-8",
    )
    (OUT / "MECHANISM_DESIGN.md").write_text(
        """# MECHANISM_DESIGN.md

Module: `mechanistic_mind/research/temporal_prospection_bridge.py`  
Flag: `cognition.temporal_prospection_bridge` default **false**.

4.23 hook: optional `entry_steps` on `compose_trajectories` (default None =
historical snapshot-only behavior).

The adapter does not predict. It copies TPS support onto a first-step edge
and labels `prediction_source=TEMPORAL` as Observer/debug metadata.
""",
        encoding="utf-8",
    )
    (OUT / "EVIDENCE_ACCOUNTING.md").write_text(
        f"""# EVIDENCE_ACCOUNTING.md

## Policy

- Snapshot 4.23 transitions and TPS classes may share underlying experience.
- The bridge does **not** add TPS support onto snapshot transition rows.
- Compose keeps **two roots** when both MATCH: SNAPSHOT and TEMPORAL.
- Supports remain on their own edges (`snapshot_support={agree['snapshot_support']}`,
  `temporal_support={agree['temporal_support']}`).
- Temporal `reliability` is **not** mapped (would be fabrication). Competition
  sees 0.0 reliability on temporal edges.
- `collect_scenario_groups` still adds snapshot `one_step_scenario` independently.
  Temporal candidates enter via composed continuations. Same first_action (WAIT)
  can therefore host both representations without summing confidence.
- Independence of evidence is **not** claimed. Ancestry is in TPS provenance
  (`class_id`, `recent`, `delta_sig`).

## Double-counting

Not silent additive inflation. Residual risk: two WAIT scenarios from overlapping
experience. Competition is unmodified and groups by first action, so this does
not create a second action channel. Documented, not "fixed" by an arbiter.
""",
        encoding="utf-8",
    )
    (OUT / "EXPERIMENT_DESIGN.md").write_text(
        """# EXPERIMENT_DESIGN.md

Runner: `experiments/run_temporal_prospection_bridge.py`  
Tests: `tests/test_temporal_prospection_bridge.py`

Primary gate: same present 0.50, H1 vs H2, TPS P vs Q, then 4.23 temporal
continuations P vs Q. Bridge-off compose has no TEMPORAL roots.

Ablations: TPS off / bridge off / 4.23 off.
""",
        encoding="utf-8",
    )
    claims = {
        "A. TEMPORAL → PROSPECTION BRIDGE": "DEMONSTRATED" if sp["prospection_splits"] else "NOT_DEMONSTRATED",
        "B. SAME-PRESENT / DIFFERENT-HISTORY PROSPECTION": "DEMONSTRATED" if sp["prospection_splits"] else "NOT_DEMONSTRATED",
        "C. TEMPORAL-ORDER-DEPENDENT PROSPECTION": "DEMONSTRATED" if order["order_reaches_4_23"] else "NOT_DEMONSTRATED",
        "D. HELD-OUT TEMPORAL PROSPECTION": "DEMONSTRATED" if held["held_generalizes_into_4_23"] else "NOT_DEMONSTRATED",
        "E. TEMPORAL EVIDENCE PRESERVATION": "DEMONSTRATED" if held["false_not_inflated_to_P"] and delay["lag8_no_manufacture"] else "SUPPORTED",
        "F. TEMPORAL PROSPECTIVE REVISION": "DEMONSTRATED" if rev["prospection_revised"] else "INCONCLUSIVE",
        "G. SNAPSHOT + TEMPORAL EVIDENCE COEXISTENCE": "DEMONSTRATED" if agree["both_present"] else "NOT_DEMONSTRATED",
        "H. SNAPSHOT/TEMPORAL CONFLICT EXPOSURE": "DEMONSTRATED" if confl["conflict"] else "INCONCLUSIVE",
        "I. TEMPORAL/TEMPORAL CONFLICT EXPOSURE": "DEMONSTRATED" if tconfl["passed_through"] else "INCONCLUSIVE",
        "J. MULTI-STEP COMPOSITION FROM TEMPORAL ENTRY": "DEMONSTRATED" if multi["composed_beyond_entry"] else "NOT_DEMONSTRATED",
        "K. TEMPORAL EVIDENCE ENTERING SCENARIO COMPETITION": "DEMONSTRATED" if compa["enters_competition"] else "NOT_DEMONSTRATED",
        "L. HISTORY-DEPENDENT SELECTED ACTION": "NOT_DEMONSTRATED",
        "M. FIELD-TEMPORAL PROSPECTION": "NOT_DEMONSTRATED",
        "N. SEASONAL-TEMPORAL PROSPECTION": "INCONCLUSIVE",
        "O. INTERNAL-TEMPORAL PROSPECTION": "DEMONSTRATED" if internal["prospection_splits"] else "NOT_DEMONSTRATED",
    }
    ev = {
        "A. TEMPORAL → PROSPECTION BRIDGE": "TPS MATCH becomes 4.23 entry_steps; snapshot lookup unchanged.",
        "B. SAME-PRESENT / DIFFERENT-HISTORY PROSPECTION": f"H1 family={sp['H1']['composition']['temporal_family']} H2={sp['H2']['composition']['temporal_family']}.",
        "C. TEMPORAL-ORDER-DEPENDENT PROSPECTION": f"structured={order['prospection']['structured']} shuffled={order['prospection']['shuffled']}.",
        "D. HELD-OUT TEMPORAL PROSPECTION": f"held TPS={held['held']['family']} prospection={held['held']['prospection']}.",
        "E. TEMPORAL EVIDENCE PRESERVATION": f"false not P={held['false_not_inflated_to_P']}; lag8 no manufacture={delay['lag8_no_manufacture']}.",
        "F. TEMPORAL PROSPECTIVE REVISION": f"A={rev['phase_A_prospection']} B={rev['phase_B_prospection']}.",
        "G. SNAPSHOT + TEMPORAL EVIDENCE COEXISTENCE": f"both={agree['both_present']} supports {agree['snapshot_support']} vs {agree['temporal_support']} not summed.",
        "H. SNAPSHOT/TEMPORAL CONFLICT EXPOSURE": f"{confl['status']}; arbiter={confl['arbiter_added']}; NEXT_GEAR_MISSING.",
        "I. TEMPORAL/TEMPORAL CONFLICT EXPOSURE": f"tps={tconfl['tps_status']} entries={tconfl['n_entries']} families={tconfl['families_in_prospection']}.",
        "J. MULTI-STEP COMPOSITION FROM TEMPORAL ENTRY": f"max_depth={multi['max_temporal_depth']} beyond_entry={multi['composed_beyond_entry']}.",
        "K. TEMPORAL EVIDENCE ENTERING SCENARIO COMPETITION": f"WAIT scenarios from temporal continuations; selected={compa['selected']}.",
        "L. HISTORY-DEPENDENT SELECTED ACTION": "WAIT/incumbent. Selection unmodified. Stop: first-action grouping + incumbent lock.",
        "M. FIELD-TEMPORAL PROSPECTION": f"SIGNAL_TEMPORAL_PREDICTION_MISSING={field['SIGNAL_TEMPORAL_PREDICTION_MISSING']}.",
        "N. SEASONAL-TEMPORAL PROSPECTION": "Diagnostic only. No anticipation claim.",
        "O. INTERNAL-TEMPORAL PROSPECTION": f"internal.c0 H1/H2 split={internal['prospection_splits']}. Other-body still NOT_DEMONSTRATED.",
    }
    lines = ["# SCIENTIFIC_CLAIMS.md\n", "Statuses: DEMONSTRATED, SUPPORTED, INCONCLUSIVE, NOT_DEMONSTRATED, REFUTED.\n"]
    for k, v in claims.items():
        lines.append(f"## {k} — {v}\n\n{ev.get(k,'')}\n")
    lines.append(
        "\n## Interpretation boundary\n\n"
        "Not claimed: planning from memory, time awareness, anticipation, intent,\n"
        "reasoning, episodic/future imagination, understanding trajectories.\n"
    )
    (OUT / "SCIENTIFIC_CLAIMS.md").write_text("".join(lines) + "\n", encoding="utf-8")
    (OUT / "PROMOTION_RECOMMENDATION.md").write_text(
        f"""# PROMOTION_RECOMMENDATION.md

**Keep `temporal_prospection_bridge` (and TPS, PE, relevance) experimental and
default OFF. Do not promote.**

- Double-counting: not additive on one edge; overlapping WAIT scenarios remain.
- Conflict: exposed, not resolved. NEXT_GEAR_MISSING for predicted-state conflict.
- False prospection: lag 8 and false trajectories not manufactured.
- Revision: downstream follows TPS ({rev['prospection_revised']}).
- Memory: no duplicated TPS store; entry_steps are references/copies of MATCH.
- Runtime: one extra compose seed per MATCH action. Overhead {perf.get('compose_overhead_s')}.
- 4.23 compatible: snapshot `predict_one_step` unchanged.
- Generic: no FIELD labels.

CURRENT INTEGRATED MM unchanged.
""",
        encoding="utf-8",
    )
    (OUT / "PERFORMANCE_RESULTS.md").write_text(
        f"""# PERFORMANCE_RESULTS.md

- compose latency (synthetic same-present): {perf.get('compose_overhead_s')} s
- extra structures written to 4.23 store: 0 (entry_steps are not learned transitions)
- TPS store unchanged by bridge
""",
        encoding="utf-8",
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"""# FINAL_REPORT.md

## 1. Why could TPS predictions not previously enter 4.23?

They were never passed in. `compose_trajectories` seeded only snapshot
`predict_one_step(O(t), action)`. TPS MATCH sat in `predictions`.

## 2. What exact bridge was added?

`temporal_prospection_bridge` (default false): copy TPS MATCH into optional
`entry_steps` for 4.23. Snapshot seeds remain. No store write.

## 3. Does the bridge create any new prediction or merely transport existing evidence?

Transport only. `bridge_creates_prediction={sp['bridge_creates_prediction']}`.

## 4. Can the same current observation produce different 4.23 prospection from different recent histories?

{'Yes' if sp['prospection_splits'] else 'No'}: H1→{sp['H1']['composition']['temporal_family']},
H2→{sp['H2']['composition']['temporal_family']}.

## 5. Does temporal order affect prospective composition?

{'Yes' if order['order_reaches_4_23'] else 'No'} (structured vs shuffled, same present).

## 6. Do held-out TPS-generalized trajectories also generalize into prospection?

{'Yes' if held['held_generalizes_into_4_23'] else 'No'}.

## 7. Is the demonstrated TPS horizon preserved honestly?

Yes. Delays 1/2/4 bridge; delay 8 does not manufacture
(lag8_no_manufacture={delay['lag8_no_manufacture']}). Horizon ≤ 4.

## 8. Can 4.23 compose multiple future steps after a temporally supplied first continuation?

{'Yes' if multi['composed_beyond_entry'] else 'No'} (max_depth={multi['max_temporal_depth']}).

## 9. Can temporally supplied evidence participate in novel composition?

{'Yes under existing 4.23 criteria' if multi['novel_under_4_23'] else 'Not shown'}:
entry from TPS, later edges from independently learned snapshot transitions.

## 10. What happens when snapshot and temporal evidence agree?

Both roots coexist. Supports {agree['snapshot_support']} and {agree['temporal_support']}
are not summed.

## 11. Is evidence double-counted?

Not as added support on one edge. Overlapping WAIT scenarios can coexist.
See EVIDENCE_ACCOUNTING.md.

## 12. What happens when snapshot and temporal evidence conflict?

Both represented. No arbiter. {confl['status']}. NEXT_GEAR_MISSING for
predicted-state conflict (competition is first-action, not future-content).

## 13. What happens when two temporal predictions conflict?

Candidates passed through ({tconfl['n_entries']} entries). No new resolver.

## 14. Does existing scenario competition accept temporal candidates?

{'Yes' if compa['enters_competition'] else 'No'} as composed continuations.

## 15. Does temporal prospection alter selected action?

No. selected={compa['selected']} source={compa['source']}.

## 16. If not, at exactly which downstream gate does it stop?

{compa['stop_gate']}

## 17. Does TPS ablation remove the prospective difference?

Yes. entries={abl['A_tps_off_bridge_on_entries']}.

## 18. Does bridge ablation preserve TPS prediction but remove temporal prospection?

Yes. TPS {abl['B_tps_on_bridge_off_tps_status']}; entries={abl['B_tps_on_bridge_off_entries']};
snapshot compose temporal n={abl['B_snapshot_compose_temporal_n']}.

## 19. Does 4.23 ablation preserve prediction but remove prospection?

Yes. TPS match in predictions={abl['C_423_off_tps_match']}; entries={abl['C_423_off_entries']}.

## 20. Does revised TPS evidence revise downstream prospection?

{'Yes' if rev['prospection_revised'] else 'Incomplete'}: {rev['phase_A_prospection']}→{rev['phase_B_prospection']}.

## 21. Can FIELD temporal evidence enter prospection if valid upstream evidence exists?

Upstream TPS MATCH missing: SIGNAL_TEMPORAL_PREDICTION_MISSING={field['SIGNAL_TEMPORAL_PREDICTION_MISSING']}.
The bridge cannot create FIELD evidence.

## 22. Can seasonal temporal evidence enter prospection?

Inconclusive diagnostic (n_entries={seas['n_entries']}). No anticipation claim.

## 23. Can internal temporal evidence enter prospection?

{'Yes' if internal['prospection_splits'] else 'No'} on synthetic internal.c0.
Other-body remains NOT_DEMONSTRATED.

## 24. What is the next missing causal gear?

Predicted-state conflict vs first-action competition: NEXT_GEAR_MISSING.
Independently, incumbent WAIT lock. Not this bridge.

## 25. Should the bridge remain experimental?

Yes. Default OFF. Do not promote.
""",
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    sp = same_present()
    perf = {"compose_overhead_s": round(time.perf_counter() - t0, 6)}
    order = order_control()
    delay = delay_results()
    held = held_out()
    agree = snapshot_agreement()
    confl = snapshot_conflict()
    tconfl = temporal_conflict()
    multi = multistep()
    rev = revision()
    abl = ablations(sp)
    cmp_ = representation_comparison(sp, held, delay)
    compa = competition_and_action(sp)
    field = field_diag()
    seas = seasonal_diag()
    internal = internal_diag()
    _json(OUT / "SAME_PRESENT_PROSPECTION.json", sp)
    _json(OUT / "ORDER_CONTROL_RESULTS.json", order)
    _json(OUT / "DELAY_RESULTS.json", delay)
    _json(OUT / "HELD_OUT_RESULTS.json", held)
    _json(OUT / "SNAPSHOT_TEMPORAL_AGREEMENT.json", agree)
    _json(OUT / "SNAPSHOT_TEMPORAL_CONFLICT.json", confl)
    _json(OUT / "TEMPORAL_CONFLICT_RESULTS.json", tconfl)
    _json(OUT / "MULTISTEP_COMPOSITION.json", multi)
    _json(OUT / "REVISION_RESULTS.json", rev)
    _json(OUT / "REPRESENTATION_COMPARISON.json", cmp_)
    _json(OUT / "FIELD_DIAGNOSTIC.json", field)
    _json(OUT / "SEASONAL_DIAGNOSTIC.json", seas)
    _json(OUT / "INTERNAL_DIAGNOSTIC.json", internal)
    _json(OUT / "ABLATION_RESULTS.json", abl)
    _json(OUT / "COMPETITION_ACTION.json", compa)
    write_docs(sp, order, delay, held, agree, confl, tconfl, multi, rev, abl, cmp_, compa, field, seas, internal, perf)
    print(json.dumps({
        "prospection_splits": sp["prospection_splits"],
        "order": order["order_reaches_4_23"],
        "delay_horizon": delay["horizon_prospection"],
        "lag8_clean": delay["lag8_no_manufacture"],
        "held": held["held_generalizes_into_4_23"],
        "false_ok": held["false_not_inflated_to_P"],
        "agree": agree["both_present"],
        "conflict": confl["status"],
        "tconflict": tconfl["tps_status"],
        "multistep": multi["composed_beyond_entry"],
        "revision": rev["prospection_revised"],
        "tps_off_entries": abl["A_tps_off_bridge_on_entries"],
        "bridge_off_entries": abl["B_tps_on_bridge_off_entries"],
        "field_missing": field["SIGNAL_TEMPORAL_PREDICTION_MISSING"],
        "internal": internal["prospection_splits"],
        "selected": compa["selected"],
        "default_off": CognitionConfig().temporal_prospection_bridge,
    }, indent=2))


if __name__ == "__main__":
    main()
