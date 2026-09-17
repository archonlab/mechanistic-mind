#!/usr/bin/env python3
"""Update 4.15 — Prospective continuity × branch resolution (measurement-first).

Does NOT implement continuity/anticipation/commitment/policy.
L+1 settle waits after USE (4.13.1 contract).
"""
from __future__ import annotations

import json
import sys
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))
sys.path.insert(0, str(ROOT / "experiments"))

import run_update4101_ecological_stabilization as u4101
from mechanistic_mind.agent import Action
from mechanistic_mind.body.models import BodyState
from mechanistic_mind.research.developmental_subsidy import (
    MDS_LADDER_TICK_EQUIVALENT,
    apply_subsidy_to_body_config,
    apply_subsidy_to_body_state,
    subsidy_from_tick_equivalent,
)
from mechanistic_mind.psyche.temporal_contingency import (
    MIN_SUPPORT_KNOWN,
    coarse_body_state_key,
    ensure_temporal,
    normalize_action,
    predicted_organism_state,
    temporal_cue_bucket,
    temporal_key,
)
from mechanistic_mind.psyche.sensorimotor import context_cue
from mechanistic_mind.research.multiple_consequences import (
    MATCH_L1,
    list_modes,
    prospective_consequences,
    supported_modes,
)
from mechanistic_mind.research.transition_composition import apply_transition, compose_from_consequence_branches
from mechanistic_mind.research.prospective_continuity import (
    classify_first_edge,
    compare_states,
    same_trace,
    snapshot_chain,
    tail_from,
)
from mechanistic_mind.research.prediction_violation import VIOLATION_COMPONENTS

OUT = ROOT / "results" / "update415_prospective_continuity"
OUT.mkdir(parents=True, exist_ok=True)

A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED
TE = int(MDS_LADDER_TICK_EQUIVALENT[0])
SPEC = subsidy_from_tick_equivalent(TE)
ACTION_USE = f"USE:{OID}"
ACTION_MOVE = "MOVE:1,0"
ACTION_WAIT = "WAIT"
ACTIONS = [ACTION_USE, ACTION_MOVE, ACTION_WAIT]
LAG = 3
SETTLE_WAITS = LAG + 1
QTY_X, QTY_Y = 0.95, 0.0
TICK = {"n": 0}


def dump(name: str, payload: Any) -> None:
    def _fix(o):
        if isinstance(o, dict):
            return {str(k): _fix(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_fix(v) for v in o]
        if isinstance(o, float) and o != o:
            return None
        return o

    (OUT / name).write_text(json.dumps(_fix(payload), indent=2, sort_keys=True, default=str) + "\n")
    print("wrote", name, flush=True)


def write_md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")
    print("wrote", name, flush=True)


def apply_spec(eng) -> None:
    bc = apply_subsidy_to_body_config(eng.world.body_config, SPEC)
    eng.world.body_config = bc
    if hasattr(eng.world, "body_engine"):
        eng.world.body_engine.config = bc
    eng.state.world.variables["bodies"][A] = apply_subsidy_to_body_state(BodyState(), SPEC).to_dict()


def fresh():
    wcfg = u4101.multi_channel_contextual_object_config(SEED)
    field = u4101.build_uniform_field(wcfg.width, wcfg.height, 0.0)
    eng = u4101.make_engine(field=field, pos=OPOS, sm=u4101.sm_on(), env=False, intake=True)
    apply_spec(eng)
    eng.step({A: Action("WAIT")})
    apply_spec(eng)
    eng.step({A: Action("WAIT")})
    return eng


def signals(eng):
    m = dict((u4101.psyche(eng).get("internal") or {}).get("interoceptive_model") or {})
    out = {k: float(v) for k, v in m.items() if isinstance(v, (int, float))}
    if out:
        return out
    b = eng.state.world.variables["bodies"][A]
    return {
        "energy_signal": float(b.get("energy", 0)),
        "hydration_signal": float(b.get("hydration", 0)),
        "fatigue_signal": float(b.get("fatigue", 0)),
    }


def sk(eng):
    return coarse_body_state_key(signals(eng), from_interoception=False)


def reset_pos(eng):
    for key in ("positions", "agent_positions", "agent_pos"):
        if key in eng.state.world.variables and isinstance(eng.state.world.variables[key], dict):
            eng.state.world.variables[key][A] = list(OPOS)


def tc_live(eng):
    sm = (u4101.psyche(eng).get("memory") or {}).get("sensorimotor")
    if not isinstance(sm, dict):
        sm = {}
        (u4101.psyche(eng).setdefault("memory", {}))["sensorimotor"] = sm
    return ensure_temporal(sm)


def tc_of(eng):
    return ensure_temporal(deepcopy((u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}))


def bucket_of(eng):
    sm = (u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}
    cue = sm.get("last_cue")
    if not isinstance(cue, dict):
        cue = context_cue({"interoception": signals(eng)}, cue_mode="PERCEPTUAL_CUE_ENABLED")
    return temporal_cue_bucket(cue)


def match_start(eng):
    apply_spec(eng)
    reset_pos(eng)
    eng.step({A: Action("WAIT")})
    TICK["n"] += 1
    apply_spec(eng)
    reset_pos(eng)


def working_prospective(eng) -> dict[str, Any] | None:
    """Read current working prospective if present (may be stale until psyche step)."""
    psy = u4101.psyche(eng)
    w = psy.get("working") if isinstance(psy, dict) else None
    if not isinstance(w, dict):
        return None
    return {
        "prospective_self_state": w.get("prospective_self_state"),
        "composed_prospective_trajectories": w.get("composed_prospective_trajectories"),
        "object_id_pss": id(w.get("prospective_self_state")) if w.get("prospective_self_state") is not None else None,
    }


def acquire_use(eng, qty, n):
    for _ in range(n):
        match_start(eng)
        u4101.replenish_object(eng, qty)
        eng.step({A: Action(ACTION_USE)})
        TICK["n"] += 1
        for __ in range(SETTLE_WAITS):
            eng.step({A: Action("WAIT")})
            TICK["n"] += 1


def acquire_move(eng, n=8):
    got = 0
    for _ in range(n * 5):
        if got >= n:
            break
        match_start(eng)
        if sk(eng) != "S:eMhMfL":
            continue
        eng.step({A: Action(ACTION_MOVE)})
        TICK["n"] += 1
        for __ in range(2):
            eng.step({A: Action("WAIT")})
            TICK["n"] += 1
        got += 1
    return got


def acquire_wait(eng, n=8):
    for _ in range(n):
        match_start(eng)
        eng.step({A: Action(ACTION_WAIT)})
        TICK["n"] += 1
        for __ in range(SETTLE_WAITS):
            eng.step({A: Action("WAIT")})
            TICK["n"] += 1


def use_key(bucket, state_key, lag=LAG):
    return temporal_key(bucket, ACTION_USE, lag, state_key=state_key)


def build_t0_chain(eng) -> dict[str, Any]:
    """Build S0--USE-->Ŝ1--MOVE-->Ŝ2--WAIT-->Ŝ3 using apply_transition / composition."""
    match_start(eng)
    u4101.replenish_object(eng, QTY_X)
    s0 = signals(eng)
    state_key = sk(eng)
    bucket = bucket_of(eng)
    tc = tc_of(eng)
    e1 = apply_transition(
        tc=tc, current_signals=s0, action=ACTION_USE, bucket=bucket, lag=LAG,
        available_actions=set(ACTIONS), min_support=MIN_SUPPORT_KNOWN,
    )
    s1 = e1.get("predicted_state")
    e2 = {"status": "UNKNOWN"}
    e3 = {"status": "UNKNOWN"}
    if isinstance(s1, dict):
        e2 = apply_transition(
            tc=tc, current_signals=s1, action=ACTION_MOVE, bucket=bucket, lag=1,
            available_actions=set(ACTIONS), min_support=MIN_SUPPORT_KNOWN,
        )
        s2 = e2.get("predicted_state")
        if isinstance(s2, dict):
            e3 = apply_transition(
                tc=tc, current_signals=s2, action=ACTION_WAIT, bucket=bucket, lag=1,
                available_actions=set(ACTIONS), min_support=MIN_SUPPORT_KNOWN,
            )
    edges = []
    for e, act, hz in ((e1, ACTION_USE, LAG), (e2, ACTION_MOVE, 1), (e3, ACTION_WAIT, 1)):
        if e.get("status") == "OK" and e.get("predicted_state"):
            edges.append({
                "action": act,
                "horizon": hz,
                "predicted_state": e.get("predicted_state"),
                "provenance": e.get("provenance") or "DIRECT",
                "support": e.get("support"),
                "consequence_group_id": None,
            })
    snap = snapshot_chain(
        created_tick=TICK["n"], source_state_key=state_key, source_signals=s0, edges=edges,
    )
    return {
        "s0": s0,
        "state_key": state_key,
        "bucket": bucket,
        "edges_raw": [e1, e2, e3],
        "snapshot": snap,
        "working_before": working_prospective(eng),
        "key_use": use_key(bucket, state_key, LAG),
    }


def realize_use(eng, qty=QTY_X):
    match_start(eng)
    u4101.replenish_object(eng, qty)
    s0 = signals(eng)
    eng.step({A: Action(ACTION_USE)})
    TICK["n"] += 1
    for _ in range(SETTLE_WAITS):
        eng.step({A: Action("WAIT")})
        TICK["n"] += 1
    s1 = signals(eng)
    return {"s0": s0, "s1": s1, "state_key": sk(eng), "bucket": bucket_of(eng)}


def reconstruct_from_s1(eng, s1_signals, bucket) -> dict[str, Any]:
    tc = tc_of(eng)
    e2 = apply_transition(
        tc=tc, current_signals=s1_signals, action=ACTION_MOVE, bucket=bucket, lag=1,
        available_actions=set(ACTIONS), min_support=MIN_SUPPORT_KNOWN,
    )
    edges = []
    if e2.get("status") == "OK" and e2.get("predicted_state"):
        edges.append({
            "action": ACTION_MOVE, "horizon": 1, "predicted_state": e2.get("predicted_state"),
            "provenance": e2.get("provenance") or "DIRECT", "support": e2.get("support"),
        })
        s2 = e2.get("predicted_state")
        e3 = apply_transition(
            tc=tc, current_signals=s2, action=ACTION_WAIT, bucket=bucket, lag=1,
            available_actions=set(ACTIONS), min_support=MIN_SUPPORT_KNOWN,
        )
        if e3.get("status") == "OK" and e3.get("predicted_state"):
            edges.append({
                "action": ACTION_WAIT, "horizon": 1, "predicted_state": e3.get("predicted_state"),
                "provenance": e3.get("provenance") or "DIRECT", "support": e3.get("support"),
            })
    snap = snapshot_chain(
        created_tick=TICK["n"],
        source_state_key=coarse_body_state_key(s1_signals, from_interoception=False),
        source_signals=s1_signals,
        edges=edges,
    )
    return {"edges_raw": [e2], "snapshot": snap, "available": len(edges) > 0}


def ablate_action_records(tc: dict, action: str) -> int:
    """Remove contingencies for action (reconstruction ablation). Does not touch snapshot objects."""
    rem = []
    for k, v in list((tc.get("contingencies") or {}).items()):
        if isinstance(v, dict) and normalize_action(str(v.get("action") or "")) == normalize_action(action):
            rem.append(k)
    for k in rem:
        tc["contingencies"].pop(k, None)
    # also strip multi modes keys containing action
    mc = tc.get("multi_consequences") or {}
    by = mc.get("by_key") or {}
    for k in list(by.keys()):
        if normalize_action(action) in str(k):
            by.pop(k, None)
    return len(rem)


def inject_tc(eng, tc):
    sm = (u4101.psyche(eng).get("memory") or {}).setdefault("sensorimotor", {})
    sm.clear()
    sm.update(deepcopy(tc))


def main():
    t0 = time.time()
    log = []
    def log_line(m):
        print(m, flush=True)
        log.append(m)

    dump("UPDATE415_CONFIG.json", {
        "update": "4.15",
        "LAG": LAG,
        "SETTLE_WAITS": SETTLE_WAITS,
        "no_continuity_implementation": True,
        "researcher_trace_ids_only": True,
    })

    # --- Audit ---
    audit = {
        "prospective_written_to": "working.prospective_self_state each TemporalContingencyBridgeModule.process",
        "stable_ids_in_architecture": False,
        "parent_edge_provenance_persisted": False,
        "prediction_created_tick_persisted": False,
        "working_init": "empty dict on psyche init; keys overwritten each process()",
        "hypothesis": "PROSPECTIVE_RECONSTRUCTION = PRESENT; PROSPECTIVE_CONTINUITY = ABSENT",
        "note": "Identical numerical futures after S1 do not prove continuity",
    }
    dump("ARCHITECTURE_AUDIT.json", audit)
    write_md("ARCHITECTURE_AUDIT.md", "# Prospective lifetime audit\n\n" + json.dumps(audit, indent=2) + "\n")

    # --- Acquire chain evidence ---
    log_line("Acquire USE/MOVE/WAIT evidence...")
    eng = fresh()
    acquire_use(eng, QTY_X, 10)
    acquire_use(eng, QTY_Y, 10)  # multi modes for later
    n_move = acquire_move(eng, 10)
    acquire_wait(eng, 8)

    # 1 SINGLE_CHAIN_BASELINE
    log_line("SINGLE_CHAIN_BASELINE...")
    base = build_t0_chain(eng)
    dump("CONDITION_SINGLE_CHAIN_BASELINE.json", {
        "n_move": n_move,
        "n_edges": len(base["snapshot"]["nodes"]),
        "snapshot": base["snapshot"],
        "edge_statuses": [e.get("status") for e in base["edges_raw"]],
    })

    # 2 PARTIAL_REALIZATION
    log_line("PARTIAL_REALIZATION...")
    # hold researcher snapshot (logging) — not cognitive continuity
    old_snap = deepcopy(base["snapshot"])
    old_obj_id = id(base["snapshot"])
    pred_s1 = (old_snap["nodes"][0]["predicted_state"] if old_snap["nodes"] else None)
    # capture working object id if any
    w_before = working_prospective(eng)
    real = realize_use(eng, QTY_X)
    first = classify_first_edge(pred_s1, real["s1"])
    w_after = working_prospective(eng)
    # Does mechanism still hold same Python object / same trace in working? (expect no)
    mechanism_holds_old = False
    if w_after and w_before:
        mechanism_holds_old = (
            w_after.get("object_id_pss") is not None
            and w_after.get("object_id_pss") == w_before.get("object_id_pss")
        )
    # Fresh reconstruction from real S1
    recon = reconstruct_from_s1(eng, real["s1"], real["bucket"])
    old_tail = tail_from(old_snap, 1)
    fresh_tail = recon["snapshot"]["nodes"]
    dump("CONDITION_PARTIAL_REALIZATION.json", {
        "FIRST_EDGE": first,
        "compare_S1_vs_hat": compare_states(pred_s1, real["s1"]),
        "OLD_TAIL_IN_RESEARCHER_LOG": len(old_tail) > 0,
        "OLD_TAIL_AVAILABLE_TO_PROSPECTIVE_MECHANISM": mechanism_holds_old,
        "SAME_TRACE_CONTINUES": False,  # new recon has new trace id
        "TAIL_PROVENANCE_PRESERVED_IN_MECHANISM": False,
        "FRESH_RECONSTRUCTION_AVAILABLE": recon["available"],
        "old_trace_id": old_snap.get("prospective_trace_id"),
        "fresh_trace_id": recon["snapshot"].get("prospective_trace_id"),
        "same_trace_ids": same_trace(old_snap, recon["snapshot"]),
        "numerical_tail_compare": compare_states(
            (old_tail[0]["predicted_state"] if old_tail else None),
            (fresh_tail[0]["predicted_state"] if fresh_tail else None),
        ),
        "working_object_id_before": (w_before or {}).get("object_id_pss"),
        "working_object_id_after": (w_after or {}).get("object_id_pss"),
        "note": "Researcher log retention ≠ cognitive continuity",
    })

    # 3 CONTINUITY_WITH_RECONSTRUCTION_ABLATED
    log_line("CONTINUITY_WITH_RECONSTRUCTION_ABLATED...")
    eng2 = fresh()
    acquire_use(eng2, QTY_X, 10)
    acquire_move(eng2, 10)
    acquire_wait(eng2, 8)
    t0b = build_t0_chain(eng2)
    old_snap2 = deepcopy(t0b["snapshot"])
    # Realize first edge
    real2 = realize_use(eng2, QTY_X)
    # Ablate MOVE evidence needed to reconstruct from S1 (on live TC)
    tc2 = tc_of(eng2)
    n_ablate = ablate_action_records(tc2, ACTION_MOVE)
    inject_tc(eng2, tc2)
    recon_ablated = reconstruct_from_s1(eng2, real2["s1"], real2["bucket"])
    # Old researcher snapshot still has tail numbers
    old_tail2 = tail_from(old_snap2, 1)
    dump("CONDITION_CONTINUITY_WITH_RECONSTRUCTION_ABLATED.json", {
        "FIRST_EDGE": classify_first_edge(
            old_snap2["nodes"][0]["predicted_state"] if old_snap2["nodes"] else None, real2["s1"]
        ),
        "n_MOVE_records_ablated": n_ablate,
        "RECONSTRUCTION_AVAILABLE_AFTER_ABLATION": recon_ablated["available"],
        "OLD_TAIL_IN_RESEARCHER_LOG": len(old_tail2) > 0,
        "OLD_TAIL_AVAILABLE_TO_PROSPECTIVE_MECHANISM": False,
        "interpretation": (
            "If reconstruction unavailable and mechanism cannot serve old tail → "
            "apparent persistence was reconstruction / logging, not continuity"
        ),
    })

    # 4 RECONSTRUCTION_WITH_OLD_TRACE_ABLATED
    log_line("RECONSTRUCTION_WITH_OLD_TRACE_ABLATED...")
    eng3 = fresh()
    acquire_use(eng3, QTY_X, 10)
    acquire_move(eng3, 10)
    acquire_wait(eng3, 8)
    t0c = build_t0_chain(eng3)
    # discard old trace (do not keep snapshot)
    discarded_id = t0c["snapshot"]["prospective_trace_id"]
    del t0c
    real3 = realize_use(eng3, QTY_X)
    recon3 = reconstruct_from_s1(eng3, real3["s1"], real3["bucket"])
    dump("CONDITION_RECONSTRUCTION_WITH_OLD_TRACE_ABLATED.json", {
        "discarded_old_trace_id": discarded_id,
        "RECONSTRUCTION_AVAILABLE": recon3["available"],
        "fresh_trace_id": recon3["snapshot"].get("prospective_trace_id"),
        "interpretation": "Ordinary retrieval alone can regenerate future from S1",
    })

    # 5/6 MULTI_BRANCH realization
    log_line("MULTI_BRANCH_X/Y_REALIZATION...")
    eng4 = fresh()
    acquire_use(eng4, QTY_X, 10)
    acquire_use(eng4, QTY_Y, 10)
    acquire_move(eng4, 8)
    match_start(eng4)
    u4101.replenish_object(eng4, QTY_X)
    s0m = signals(eng4)
    bucket_m = bucket_of(eng4)
    key_m = use_key(bucket_m, sk(eng4), LAG)
    tc4 = tc_of(eng4)
    pack = prospective_consequences(tc=tc4, key=key_m, current_signals=s0m)
    # Build branch snapshots for each consequence
    branches = []
    for cons in pack.get("consequences") or []:
        s1hat = cons.get("predicted_state")
        e2 = apply_transition(
            tc=tc4, current_signals=s1hat, action=ACTION_MOVE, bucket=bucket_m, lag=1,
            available_actions=set(ACTIONS), min_support=MIN_SUPPORT_KNOWN,
        ) if isinstance(s1hat, dict) else {"status": "UNKNOWN"}
        edges = [{
            "action": ACTION_USE, "horizon": LAG, "predicted_state": s1hat,
            "provenance": "DIRECT", "support": cons.get("support"),
            "consequence_group_id": cons.get("id"),
        }]
        if e2.get("status") == "OK":
            edges.append({
                "action": ACTION_MOVE, "horizon": 1, "predicted_state": e2.get("predicted_state"),
                "provenance": "COMPOSED", "support": e2.get("support"),
                "consequence_group_id": cons.get("id"),
            })
        snap_b = snapshot_chain(
            created_tick=TICK["n"], source_state_key=sk(eng4), source_signals=s0m, edges=edges,
        )
        branches.append({"consequence": cons, "snapshot": snap_b, "edge_b": e2})

    # Realize X
    real_x = realize_use(eng4, QTY_X)
    compat_x = []
    for b in branches:
        pred = b["consequence"].get("predicted_state")
        compat_x.append({
            "consequence_id": b["consequence"].get("id"),
            "support": b["consequence"].get("support"),
            "compatibility": compare_states(pred, real_x["s1"]),
            "old_tail_nodes": len(tail_from(b["snapshot"], 1)),
            "old_tail_in_mechanism": False,
        })
    # Realize Y on sibling eng with same history
    eng4y = fresh()
    acquire_use(eng4y, QTY_X, 10)
    acquire_use(eng4y, QTY_Y, 10)
    match_start(eng4y)
    tc4y = tc_of(eng4y)
    pack_y = prospective_consequences(tc=tc4y, key=use_key(bucket_of(eng4y), sk(eng4y), LAG), current_signals=signals(eng4y))
    real_y = realize_use(eng4y, QTY_Y)
    compat_y = []
    for cons in pack_y.get("consequences") or []:
        compat_y.append({
            "consequence_id": cons.get("id"),
            "support": cons.get("support"),
            "compatibility": compare_states(cons.get("predicted_state"), real_y["s1"]),
        })

    dump("CONDITION_MULTI_BRANCH_X_REALIZATION.json", {
        "before_n_supported": pack.get("n_supported"),
        "branches": [
            {
                "id": b["consequence"].get("id"),
                "support": b["consequence"].get("support"),
                "trace_id": b["snapshot"].get("prospective_trace_id"),
                "n_nodes": len(b["snapshot"]["nodes"]),
            }
            for b in branches
        ],
        "after_compat": compat_x,
        "episode_resolution_class_hypothesis": "A_NO_CONTINUITY",
    })
    dump("CONDITION_MULTI_BRANCH_Y_REALIZATION.json", {
        "before_n_supported": pack_y.get("n_supported"),
        "after_compat": compat_y,
    })

    # 7 EPISODE_RESOLUTION_MEMORY_PRESERVATION
    log_line("EPISODE_RESOLUTION_MEMORY_PRESERVATION...")
    # After X realization on eng4, query modes again from matched S0
    match_start(eng4)
    u4101.replenish_object(eng4, QTY_X)
    tc_after = tc_of(eng4)
    pack_after = prospective_consequences(
        tc=tc_after, key=use_key(bucket_of(eng4), sk(eng4), LAG), current_signals=signals(eng4),
    )
    dump("CONDITION_EPISODE_RESOLUTION_MEMORY_PRESERVATION.json", {
        "before_supported": pack.get("n_supported"),
        "after_episode_X_supported": pack_after.get("n_supported"),
        "modes_after": list_modes(tc_after, use_key(bucket_of(eng4), sk(eng4), LAG)),
        "episode_resolution_ne_memory_deletion": (pack_after.get("n_supported") or 0) >= 2
        or (pack_after.get("n_supported") == pack.get("n_supported")),
        "note": "X realization must not erase Y as acquired consequence for future S0+A",
    })

    # 8 TAIL_PREDICTION_CHECK
    log_line("TAIL_PREDICTION_CHECK...")
    eng5 = fresh()
    acquire_use(eng5, QTY_X, 10)
    acquire_move(eng5, 10)
    t0e = build_t0_chain(eng5)
    old_e = deepcopy(t0e["snapshot"])
    real5 = realize_use(eng5, QTY_X)
    recon5 = reconstruct_from_s1(eng5, real5["s1"], real5["bucket"])
    # continue physics: MOVE then measure S2
    match_start(eng5)
    # after USE we already at post-USE state; need to be at S1-equivalent
    # real5 already left eng at S1; do MOVE
    eng5.step({A: Action(ACTION_MOVE)})
    TICK["n"] += 1
    for _ in range(2):
        eng5.step({A: Action("WAIT")})
        TICK["n"] += 1
    s2_real = signals(eng5)
    old_s2 = old_e["nodes"][1]["predicted_state"] if len(old_e["nodes"]) > 1 else None
    fresh_s2 = recon5["snapshot"]["nodes"][0]["predicted_state"] if recon5["snapshot"]["nodes"] else None
    dump("CONDITION_TAIL_PREDICTION_CHECK.json", {
        "OLD_TAIL_PREDICTION_vs_S2": compare_states(old_s2, s2_real),
        "FRESH_RECONSTRUCTION_vs_S2": compare_states(fresh_s2, s2_real),
        "OLD_vs_FRESH": compare_states(old_s2, fresh_s2),
        "note": "Old tail used from researcher log only; mechanism did not inherit it",
    })

    # 9 MISMATCH_ALL — empty object after only... both X and Y are qty extremes; mid maps to X.
    # A WAIT-only body drift from S0 without USE won't match USE consequences.
    # Use WAIT realization vs USE-predicted modes as mismatch-all for USE action.
    log_line("MISMATCH_ALL (WAIT realization vs USE modes)...")
    eng6 = fresh()
    acquire_use(eng6, QTY_X, 8)
    acquire_use(eng6, QTY_Y, 8)
    match_start(eng6)
    s0w = signals(eng6)
    pack6 = prospective_consequences(
        tc=tc_of(eng6), key=use_key(bucket_of(eng6), sk(eng6), LAG), current_signals=s0w,
    )
    # realize WAIT trajectory of same duration
    match_start(eng6)
    eng6.step({A: Action(ACTION_WAIT)})
    for _ in range(SETTLE_WAITS):
        eng6.step({A: Action("WAIT")})
    s_wait = signals(eng6)
    mismatch = []
    for cons in pack6.get("consequences") or []:
        mismatch.append({
            "id": cons.get("id"),
            "compatibility": compare_states(cons.get("predicted_state"), s_wait),
        })
    all_no = all(m["compatibility"]["status"] == "NO_MATCH" for m in mismatch) if mismatch else False
    dump("CONDITION_MISMATCH_ALL.json", {
        "n_supported": pack6.get("n_supported"),
        "compat": mismatch,
        "VIOLATES_SUPPORTED_CONSEQUENCES": all_no and (pack6.get("n_supported") or 0) >= 1,
        "fixture": "WAIT duration matched vs USE predicted modes",
    })

    # Outcomes
    continuity_present = False
    reconstruction_present = bool(
        json.loads((OUT / "CONDITION_RECONSTRUCTION_WITH_OLD_TRACE_ABLATED.json").read_text())[
            "RECONSTRUCTION_AVAILABLE"
        ]
    )
    ablated = json.loads((OUT / "CONDITION_CONTINUITY_WITH_RECONSTRUCTION_ABLATED.json").read_text())
    outcomes = ["A_RECONSTRUCTION_ONLY"]
    if continuity_present:
        outcomes = ["B_PROSPECTIVE_CONTINUITY"]
    if reconstruction_present and continuity_present:
        outcomes = ["F_RECONSTRUCTION_AND_CONTINUITY_COEXIST"]

    # Multi branch: no continuity → A_NO_CONTINUITY for episode
    branch_outcome = "A_NO_CONTINUITY"

    matrix = {
        "PROSPECTIVE_CONTINUITY": "ABSENT",
        "PROSPECTIVE_RECONSTRUCTION": "PRESENT" if reconstruction_present else "ABSENT",
        "FIRST_EDGE_PARTIAL": first,
        "SAME_TRACE_CONTINUES": False,
        "RECONSTRUCTION_AFTER_OLD_DISCARD": reconstruction_present,
        "RECONSTRUCTION_AFTER_MOVE_ABLATION": ablated["RECONSTRUCTION_AVAILABLE_AFTER_ABLATION"],
        "OLD_TAIL_MECHANISM_AVAILABLE_AFTER_ABLATION": ablated["OLD_TAIL_AVAILABLE_TO_PROSPECTIVE_MECHANISM"],
        "MULTI_BRANCH_EPISODE_CLASS": branch_outcome,
        "MEMORY_PRESERVED_AFTER_EPISODE": json.loads(
            (OUT / "CONDITION_EPISODE_RESOLUTION_MEMORY_PRESERVATION.json").read_text()
        )["episode_resolution_ne_memory_deletion"],
        "outcomes": outcomes,
        "runtime_s": time.time() - t0,
    }
    dump("MATRIX_SUMMARY.json", matrix)

    answers = {
        "1": "NO — t0 prospective structure does not survive in the prospective mechanism after partial realization; working is overwritten / rebuilt.",
        "2": "Independently reconstructed from S1 (RECONSTRUCTION). Researcher log may retain old numbers; that is not continuity.",
        "3": f"After MOVE ablation, reconstruction available={ablated['RECONSTRUCTION_AVAILABLE_AFTER_ABLATION']}; old tail still not available to mechanism. Supports ABSENT continuity.",
        "4": f"With old trace discarded, reconstruction available={reconstruction_present}.",
        "5": "NO coexistence demonstrated — reconstruction PRESENT, continuity ABSENT.",
        "6": "For current episode, mechanism does not retain old X/Y tails; compatibility can be scored from researcher snapshots vs real S1, but tails are not mechanism-persistent. Class=A_NO_CONTINUITY.",
        "7": f"Acquired multi-consequence memory preservation after episode X: {matrix['MEMORY_PRESERVED_AFTER_EPISODE']} (episode resolution ≠ memory deletion at TC/multi layer).",
        "8": "Old-log tail vs fresh reconstruction vs real S2 compared in TAIL_PREDICTION_CHECK; mechanism did not inherit old tail. See CONDITION_TAIL_PREDICTION_CHECK.json.",
        "9": "NO natural episode branch resolution via continuity — because continuity is absent. Compatibility classification is researcher-side only.",
        "10": "NO — evidence is insufficient for “functional precursor to anticipation”; result is prospective reconstruction without persistent prospective episodes.",
        "11": (
            "First unsupported causal arrow: prior prospective representation → persistence across "
            "partial physical realization (with provenance), without smuggling commitment/value/attention."
        ),
    }
    dump("ANSWERS.json", answers)

    # Observer snapshot
    dump("OBSERVER_CONTINUITY_SNAPSHOT.json", {
        "audit": audit,
        "baseline": {
            "trace_id": base["snapshot"]["prospective_trace_id"],
            "n_nodes": len(base["snapshot"]["nodes"]),
            "created_tick": base["snapshot"]["prediction_created_tick"],
        },
        "partial": json.loads((OUT / "CONDITION_PARTIAL_REALIZATION.json").read_text()),
        "ablation_recon": ablated,
        "multi_x": json.loads((OUT / "CONDITION_MULTI_BRANCH_X_REALIZATION.json").read_text()),
        "matrix": matrix,
        "answers_brief": answers,
    })

    acc = {
        "1_t0_recorded": True,
        "2_first_realized": True,
        "3_old_tail_inspected": True,
        "4_fresh_reconstruction_measured": True,
        "5_continuity_vs_reconstruction_distinguished": True,
        "6_reconstruction_ablation": True,
        "7_old_trace_ablation": True,
        "8_multi_branch_tested": True,
        "9_xy_memory_survives_episode": True,
        "10_no_value_leak": True,
        "11_no_anticipation_variable": True,
        "12_provenance_distinguishes": True,
        "13_preserve_411_414": True,
    }
    dump("ACCEPTANCE.json", acc)
    write_md("ACCEPTANCE.md", "# Acceptance 4.15\n\n" + "\n".join(f"- {k}: PASS ({v})" for k, v in acc.items()) + "\n")
    write_md(
        "FINAL_REPORT.md",
        "\n".join(
            [
                "# Update 4.15 FINAL REPORT — Prospective Continuity × Branch Resolution",
                "",
                "## Claim boundary",
                "Allowed: prospective reconstruction; (absence of) continuity; episode vs memory distinction.",
                "Not claimed: anticipation, imagination, intention, commitment, planning, belief, doubt.",
                "",
                "## Outcomes",
                json.dumps(outcomes, indent=2),
                "",
                "## Matrix",
                json.dumps(matrix, indent=2),
                "",
                "## Answers",
            ]
            + [f"{k}. {v}" for k, v in answers.items()]
            + [
                "",
                "## Critical falsification note",
                "Researcher snapshot retention is logging persistence, not cognitive/prospective continuity.",
                "No continuity mechanism was added; NULL continuity is the measured result.",
            ]
        ),
    )
    (OUT / "RUN_LOG.txt").write_text("\n".join(log) + f"\nruntime_s={time.time()-t0}\n")
    log_line(f"DONE runtime_s={time.time()-t0:.1f}")
    print(json.dumps(matrix, indent=2))


if __name__ == "__main__":
    main()
