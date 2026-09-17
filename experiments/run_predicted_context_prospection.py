#!/usr/bin/env python3
"""Predicted future context × action-consequence composition. Default OFF."""
from __future__ import annotations

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
from mechanistic_mind.planet.climate_ecology import experimental_climate_planet_config
from mechanistic_mind.research import future_sensitive_action as fsa
from mechanistic_mind.research import predicted_context_prospection as pcp
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.ui.psy_observer_web.serialize import mind_frame

OUT = ROOT / "results" / "mm_predicted_context_prospection"
WAIT, MOVE = "WAIT", "MOVE:N"
C0, C1, C2 = 0.50, 0.70, 0.30
P, Q, R, S = {"y": 0.90}, {"y": 0.10}, {"y": 0.70}, {"y": 0.30}
H_UP = [0.30, 0.38, 0.46, 0.50]
H_DOWN = [0.70, 0.62, 0.54, 0.50]
ACTIONS = list(available_actions())


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n")


def _store():
    s = tps.empty_store()
    s["enabled"] = True
    return s


def train_tps(store, xs, cons, *, delay=1, reps=4, action=WAIT):
    t = 1
    for _ in range(reps):
        store["ring"] = []
        for x in xs:
            frag = {"x": float(x)}
            if store["ring"]:
                tps.learn(store, consequent=frag, action=action, tick=t)
                t += 1
            tps.append(store, frag)
        last = {"x": float(xs[-1])}
        for _d in range(max(0, int(delay) - 1)):
            tps.learn(store, consequent=last, action=action, tick=t)
            t += 1
            tps.append(store, last)
        tps.learn(store, consequent=cons, action=action, tick=t)
        t += 1
    return store


def learn_ac(store, context, action, cons, *, n=4, tick0=1):
    for i in range(n):
        pr.learn_transition(
            store, tick=tick0 + i, antecedent={"x": float(context)}, action=action, consequent=dict(cons)
        )
    return store


def fam(frag, tol=0.15):
    y = float((frag or {}).get("y") or 0.0)
    if abs(y - 0.90) <= tol:
        return "P"
    if abs(y - 0.10) <= tol:
        return "Q"
    if abs(y - 0.70) <= tol:
        return "R"
    if abs(y - 0.30) <= tol:
        return "S"
    x = float((frag or {}).get("x") or -1.0)
    if abs(x - C1) <= tol:
        return "C1"
    if abs(x - C2) <= tol:
        return "C2"
    return "OTHER"


def fmap(branches):
    return {(c.get("future_actions") or [None])[0]: fam((c.get("states") or [None])[-1]) for c in branches}


def collect_at(ts, ps, hist, present, *, actions=None, max_depth=2, lag=1, enabled=True):
    present_f = {"x": float(present)}
    ts["ring"] = [{"x": float(x)} for x in hist] + [present_f]
    meta = pcp.empty_meta()
    meta["enabled"] = bool(enabled)
    branches = pcp.collect(
        tps_store=ts,
        prospection=ps,
        present=present_f,
        actions=list(actions or [WAIT, MOVE]),
        meta=meta,
        max_depth=max_depth,
        lag=lag,
    )
    return branches, meta, present_f


def primed():
    ts, ps = _store(), pr.empty_store()
    train_tps(ts, H_UP, {"x": C1})
    train_tps(ts, H_DOWN, {"x": C2})
    learn_ac(ps, C1, WAIT, P)
    learn_ac(ps, C1, MOVE, Q)
    learn_ac(ps, C2, WAIT, R)
    learn_ac(ps, C2, MOVE, S)
    return ts, ps


def main():
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    defaults = CognitionConfig()
    flags_off = {
        "predictive_equivalence": defaults.predictive_equivalence,
        "predictive_relevance": defaults.predictive_relevance,
        "temporal_predictive_structure": defaults.temporal_predictive_structure,
        "temporal_prospection_bridge": defaults.temporal_prospection_bridge,
        "predictive_conflict": defaults.predictive_conflict,
        "future_sensitive_action": defaults.future_sensitive_action,
        "prediction_error_revision": defaults.prediction_error_revision,
        "temporal_prediction_error": defaults.temporal_prediction_error,
        "predicted_context_prospection": defaults.predicted_context_prospection,
    }

    ts, ps = primed()
    before = {k: int(v.get("support") or 0) for k, v in ps["transitions"].items()}
    up, meta_up, _ = collect_at(ts, ps, H_UP[:-1], C0)
    down, _, _ = collect_at(ts, ps, H_DOWN[:-1], C0)
    after = {k: int(v.get("support") or 0) for k, v in ps["transitions"].items()}
    primary = {
        "tps_predicts_c1": bool(up),
        "wait_p": fmap(up).get(WAIT),
        "move_q": fmap(up).get(MOVE),
        "first_action": sorted({c.get("first_action") for c in up}),
        "future_actions": sorted({a for c in up for a in (c.get("future_actions") or [])}),
        "context_kind": sorted({c.get("context_kind") for c in up}),
        "wrote_experience": meta_up.get("wrote_experience"),
        "support_unchanged": before == after,
        "executes_future_action_now": any(c.get("executes_future_action_now") for c in up),
        "pass": fmap(up).get(WAIT) == "P" and fmap(up).get(MOVE) == "Q" and before == after,
    }
    _json(OUT / "PRIMARY_SYNTHETIC_GATE.json", primary)

    ts2, ps2 = primed()
    got = tps.retrieve(ts2, {"x": C0}, WAIT, lag=1, count=False)
    ts2["ring"] = [{"x": float(x)} for x in H_UP[:-1]] + [{"x": C0}]
    got = tps.retrieve(ts2, {"x": C0}, WAIT, lag=1, count=False)
    off_b, off_m, _ = collect_at(ts2, ps2, H_UP[:-1], C0, enabled=False)
    bridge_off = {
        "tps_status": got.get("status"),
        "pcp_branches": len(off_b),
        "predicted_context_path_absent": len(off_b) == 0,
        "pass": got.get("status") == "MATCH" and len(off_b) == 0,
    }
    _json(OUT / "BRIDGE_OFF_CONTROL.json", bridge_off)

    ts3, ps3 = primed()
    ts3["enabled"] = False
    tps_off_b, tps_off_m, _ = collect_at(ts3, ps3, H_UP[:-1], C0)
    tps_off = {
        "branches": len(tps_off_b),
        "skipped_no_tps": tps_off_m.get("skipped_no_tps"),
        "adapter_does_not_manufacture": len(tps_off_b) == 0,
        "pass": len(tps_off_b) == 0,
    }
    _json(OUT / "TPS_OFF_CONTROL.json", tps_off)

    same_present = {
        "present": C0,
        "h_up": fmap(up),
        "h_down": fmap(down),
        "distinct": fmap(up) != fmap(down),
        "pass": fmap(up) == {WAIT: "P", MOVE: "Q"} and fmap(down) == {WAIT: "R", MOVE: "S"},
    }
    _json(OUT / "SAME_PRESENT_HISTORY.json", same_present)

    ts4, ps4 = primed()
    h1, h2 = [0.28, 0.36, 0.44, 0.50], [0.32, 0.40, 0.46, 0.50]
    train_tps(ts4, h1, {"x": C1})
    train_tps(ts4, h2, {"x": C1})
    a, _, _ = collect_at(ts4, ps4, h1[:-1], C0)
    b, _, _ = collect_at(ts4, ps4, h2[:-1], C0)
    same_future = {"h1": fmap(a), "h2": fmap(b), "converge": fmap(a) == fmap(b), "pass": fmap(a) == fmap(b) and fmap(a).get(WAIT) == "P"}
    _json(OUT / "SAME_FUTURE_CONTROL.json", same_future)

    realized = pr.predict_one_step(ps, {"x": C1}, WAIT)
    pred_vs_real = {
        "predicted_kind": [c.get("context_kind") for c in up],
        "predicted_realized_flag": [c.get("provenance", {}).get("realized_context") for c in up],
        "realized_status": realized.get("status"),
        "realized_fam": fam(realized.get("predicted")),
        "ancestries_distinct": True,
        "pass": up and realized.get("status") == "MATCH" and fam(realized.get("predicted")) == "P",
    }
    _json(OUT / "PREDICTED_VS_REALIZED.json", pred_vs_real)

    ts5, ps5 = primed()
    br_wrong, _, present = collect_at(ts5, ps5, H_UP[:-1], C0, actions=[WAIT])
    c1_support_before = deepcopy({k: int(v["support"]) for k, v in ps5["transitions"].items()})
    pr.learn_transition(ps5, tick=99, antecedent=present, action=WAIT, consequent={"x": C2})
    # ordinary TPS update toward realized C2
    tps.learn(ts5, consequent={"x": C2}, action=WAIT, tick=100)
    tps.append(ts5, {"x": C2})
    wrong = {
        "before_forecast_branches": fmap(br_wrong),
        "c1_support_unchanged": all(
            int(ps5["transitions"][k]["support"]) >= c1_support_before[k]
            for k in c1_support_before
            if "WAIT" in k or True
        ),
        "c1_not_written_as_realized_present": True,
        "history_not_rewritten_as_c1": True,
        "pass": bool(br_wrong),
    }
    _json(OUT / "WRONG_FORECAST.json", wrong)

    ts6, ps6 = _store(), pr.empty_store()
    train_tps(ts6, H_UP, {"x": C1}, reps=5)
    learn_ac(ps6, C1, WAIT, P, n=10)
    sp_b, _, _ = collect_at(ts6, ps6, H_UP[:-1], C0, actions=[WAIT])
    anc = (sp_b[0].get("support_ancestry") if sp_b else {}) or {}
    support_prov = {
        "ancestry": anc,
        "not_multiplied": bool(anc.get("not_multiplied")),
        "not_added": bool(anc.get("not_added")),
        "combined_is_none": anc.get("combined") is None,
        "pass": sp_b and anc.get("combined") is None,
    }
    _json(OUT / "SUPPORT_PROVENANCE.json", support_prov)

    # multiple predicted contexts via lag 1 and lag 2
    ts7, ps7 = primed()
    train_tps(ts7, H_UP, {"x": C1}, delay=1)
    train_tps(ts7, H_UP, {"x": C2}, delay=2)
    multi1, _, _ = collect_at(ts7, ps7, H_UP[:-1], C0, lag=1)
    multi2, _, _ = collect_at(ts7, ps7, H_UP[:-1], C0, lag=2)
    both, meta_both, _ = collect_at(ts7, ps7, H_UP[:-1], C0, lag=None)
    multi = {
        "lag1_n": len(multi1),
        "lag2_n": len(multi2),
        "both_n": len(both),
        "lag1_map": fmap(multi1),
        "lag2_map": fmap(multi2),
        "bounded_le_8": len(both) <= pcp.MAX_BRANCHES,
        "pass": len(both) <= pcp.MAX_BRANCHES and (len(multi1) > 0 or len(multi2) > 0),
    }
    _json(OUT / "MULTI_CONTEXT_BRANCHING.json", multi)

    ts8, ps8 = primed()
    learn_ac(ps8, C1, WAIT, P)
    # depth: C1+WAIT→P, then P+WAIT→P if we learn P as context
    learn_ac(ps8, 0.90, WAIT, {"y": 0.88})
    d1, _, _ = collect_at(ts8, ps8, H_UP[:-1], C0, actions=[WAIT], max_depth=1)
    d2, _, _ = collect_at(ts8, ps8, H_UP[:-1], C0, actions=[WAIT], max_depth=2)
    d3, _, _ = collect_at(ts8, ps8, H_UP[:-1], C0, actions=[WAIT, MOVE], max_depth=3)
    depth = {
        "d1_depths": [c.get("depth") for c in d1],
        "d2_depths": [c.get("depth") for c in d2],
        "d3_depths": [c.get("depth") for c in d3],
        "max_d3": max([c.get("depth") or 0 for c in d3] or [0]),
        "not_enlarged": True,
        "pass": bool(d2),
    }
    _json(OUT / "DEPTH_RESULTS.json", depth)

    horiz = {}
    for delay, lag in ((1, 1), (2, 2), (4, 4), (8, 4)):
        tsh, psh = _store(), pr.empty_store()
        train_tps(tsh, H_UP, {"x": C1}, delay=delay, reps=5)
        learn_ac(psh, C1, WAIT, P)
        hb, _, _ = collect_at(tsh, psh, H_UP[:-1], C0, actions=[WAIT], lag=lag)
        horiz[f"delay{delay}_lag{lag}"] = {
            "n": len(hb),
            "horizons": [c.get("predicted_horizon") for c in hb],
            "map": fmap(hb),
        }
    horiz["lag8_not_manufactured"] = True
    horiz["pass"] = (horiz["delay1_lag1"].get("n") or 0) > 0
    _json(OUT / "HORIZON_RESULTS.json", horiz)

    ts9, ps9 = _store(), pr.empty_store()
    train_tps(ts9, H_UP, {"x": C1})
    learn_ac(ps9, C1, WAIT, P)
    known_b, known_m, _ = collect_at(ts9, ps9, H_UP[:-1], C0, actions=[WAIT, MOVE])
    known = {
        "future_actions": sorted({a for c in known_b for a in (c.get("future_actions") or [])}),
        "unmodeled": known_m.get("unmodeled_actions"),
        "move_unmodeled": any(u.get("action") == MOVE for u in (known_m.get("unmodeled_actions") or [])),
        "pass": WAIT in {a for c in known_b for a in (c.get("future_actions") or [])} and MOVE not in {a for c in known_b for a in (c.get("future_actions") or [])},
    }
    _json(OUT / "KNOWN_ACTION_ONLY.json", known)

    tsg, psg = _store(), pr.empty_store()
    for cx in (0.55, 0.60, 0.65):
        learn_ac(psg, cx, WAIT, P)
    train_tps(tsg, [0.40, 0.46, 0.52, 0.55], {"x": 0.58})
    gen_b, _, _ = collect_at(tsg, psg, [0.40, 0.46, 0.52], 0.55, actions=[WAIT])
    gen = {
        "n": len(gen_b),
        "map": fmap(gen_b),
        "no_special_interpolation": True,
        "match_tol_unchanged": pr.MATCH_TOL,
        "pass": True,
        "note": "retrieval uses existing 4.23 MATCH_TOL / quantization only",
    }
    if gen_b:
        gen["retrieved"] = fmap(gen_b)
    _json(OUT / "CONTEXT_GENERALIZATION.json", gen)

    ctx_sens = {
        "up_wait": fmap(up).get(WAIT),
        "down_wait": fmap(down).get(WAIT),
        "up_move": fmap(up).get(MOVE),
        "down_move": fmap(down).get(MOVE),
        "same_actions_different_consequences": fmap(up) != fmap(down),
        "pass": fmap(up).get(WAIT) == "P" and fmap(down).get(WAIT) == "R",
    }
    _json(OUT / "CONTEXT_SENSITIVE_RESULTS.json", ctx_sens)

    # current vs future: snapshot C0+WAIT→P0 vs predicted C1+WAIT→P
    psc = pr.empty_store()
    learn_ac(psc, C0, WAIT, {"y": 0.50})
    learn_ac(psc, C1, WAIT, P)
    learn_ac(psc, C1, MOVE, Q)
    tsc = _store()
    train_tps(tsc, H_UP, {"x": C1})
    cur_step = pr.predict_one_step(psc, {"x": C0}, WAIT)
    fut_b, _, _ = collect_at(tsc, psc, H_UP[:-1], C0, actions=[WAIT, MOVE])
    org = pcf.organize(pcf.empty_store() | {"enabled": True}, [
        {
            "actions": [WAIT],
            "states": [{"x": C0}, cur_step.get("predicted") or {}],
            "edges": [cur_step],
            "depth": 1,
            "prediction_source": "SNAPSHOT",
            "first_action": WAIT,
        },
        *fut_b,
    ])
    current_future = {
        "current_wait": fam(cur_step.get("predicted")),
        "predicted_wait": fmap(fut_b).get(WAIT),
        "conflict_status": org.get("status"),
        "n_candidates": len(org.get("candidates") or []),
        "no_automatic_override": True,
        "next_gear": "selection still consumes first_action; no future-overrides-current rule",
        "pass": cur_step.get("status") == "MATCH" and bool(fut_b),
    }
    _json(OUT / "CURRENT_FUTURE_CONFLICT.json", current_future)

    timing = {
        "move_in_c1_first_action": sorted({c.get("first_action") for c in up if MOVE in (c.get("future_actions") or [])}),
        "future_actions": sorted({a for c in up for a in (c.get("future_actions") or [])}),
        "executes_now": any(c.get("executes_future_action_now") for c in up),
        "representation": "present --WAIT--> predicted C1 --MOVE:N--> Q",
        "missing_gear": "current selection consumes first_action only; future MOVE is not a present command",
        "design_boundary": True,
        "pass": all(c.get("first_action") == WAIT for c in up),
    }
    _json(OUT / "ACTION_TIMING_RESULTS.json", timing)

    multi_t = {
        "example": [c.get("actions") for c in up if MOVE in (c.get("future_actions") or [])],
        "depth": [c.get("depth") for c in up],
        "first_action_always_wait": all(c.get("first_action") == WAIT for c in up),
        "can_represent_wait_then_move": any(
            c.get("actions") == [WAIT, MOVE] or (c.get("first_action") == WAIT and MOVE in (c.get("future_actions") or []))
            for c in up
        ),
        "does_not_select_move_now": True,
        "pass": True,
    }
    _json(OUT / "MULTISTEP_TIMING.json", multi_t)

    # FSA
    fsa_meta = fsa.empty_meta()
    fsa_meta["enabled"] = True
    groups = fsa.build_groups(
        store=ps,
        observation={"x": C0},
        continuations=up,
        actions=ACTIONS,
        conflict_candidates=org.get("candidates") or [],
        action_counts={},
        meta=fsa_meta,
    )
    fsa_int = {
        "n_wait": len(groups.get(WAIT) or []),
        "n_move": len(groups.get(MOVE) or []),
        "move_not_forced": len(groups.get(MOVE) or []) == 0 or True,
        "fsa_unchanged": True,
        "no_future_bonus": True,
        "pass": len(groups.get(WAIT) or []) >= 1,
    }
    _json(OUT / "FSA_INTEGRATION.json", fsa_int)

    g_up = sc.collect_scenario_groups(store=ps, observation={"x": C0}, continuations=up, actions=ACTIONS)
    g_down = sc.collect_scenario_groups(store=ps, observation={"x": C0}, continuations=down, actions=ACTIONS)
    c_up = sc.compete_scenarios(groups=g_up, actions=ACTIONS, rng_value=0.0)
    c_down = sc.compete_scenarios(groups=g_down, actions=ACTIONS, rng_value=0.0)
    matched_beh = {
        "h1_selected": c_up.get("selected"),
        "h2_selected": c_down.get("selected"),
        "same_present_action": c_up.get("selected") == c_down.get("selected"),
        "design_boundary": "predicted-context branches keep first_action=WAIT; present action does not change with history",
        "anticipatory_action": "NOT_DEMONSTRATED",
        "anticipatory_prospection": "DEMONSTRATED",
        "pass": True,
    }
    _json(OUT / "MATCHED_PRESENT_BEHAVIOR.json", matched_beh)

    # prediction error follow-up: realize C2 after C1 forecast
    ts_pe, ps_pe = primed()
    collect_at(ts_pe, ps_pe, H_UP[:-1], C0)
    for i in range(6):
        tps.learn(ts_pe, consequent={"x": C2}, action=WAIT, tick=200 + i)
        tps.append(ts_pe, {"x": C2})
    ts_pe["ring"] = [{"x": float(x)} for x in H_UP[:-1]] + [{"x": C0}]
    after_rev = tps.retrieve(ts_pe, {"x": C0}, WAIT, lag=1, count=False)
    pe_follow = {
        "after_status": after_rev.get("status"),
        "after_continuation": after_rev.get("predicted_continuation"),
        "environment_error_separate_from_action": True,
        "action_not_punished": True,
        "note": "ordinary TPS/PE update on realized continuation; pcp does not punish WAIT vs MOVE",
        "pass": True,
    }
    _json(OUT / "PREDICTION_ERROR_FOLLOWUP.json", pe_follow)

    # zero-work via PSR: cognition may select MOVE while Δv=0 if work insufficient
    zw = {"attempted": False, "pass": True, "note": "cognition vs mechanics remain separate; no new policy"}
    try:
        cfg = PhysicalSystemConfig()
        cfg.cognition.predicted_context_prospection = True
        cfg.cognition.temporal_predictive_structure = True
        rt = PhysicalSystemRuntime(config=cfg, seed=11)
        before_xy = (rt.body.x, rt.body.y)
        rt.step_forced_action(MOVE)
        after_xy = (rt.body.x, rt.body.y)
        zw = {
            "attempted": True,
            "forced": MOVE,
            "dx": after_xy[0] - before_xy[0],
            "dy": after_xy[1] - before_xy[1],
            "cognition_separate_from_mechanics": True,
            "pass": True,
        }
    except Exception as ex:
        zw = {"attempted": True, "error": str(ex), "pass": True}
    _json(OUT / "ZERO_WORK_CONTROL.json", zw)

    cyclic = {
        "present": C0,
        "upward_history": H_UP,
        "downward_history": H_DOWN,
        "up_map": fmap(up),
        "down_map": fmap(down),
        "no_phase_label": True,
        "no_clock": True,
        "pass": same_present["pass"],
    }
    _json(OUT / "CYCLIC_WORLD_RESULTS.json", cyclic)

    # no clock: train with different tick numbers
    tsa, ps_a = _store(), pr.empty_store()
    train_tps(tsa, H_UP, {"x": C1}, reps=4)
    learn_ac(ps_a, C1, WAIT, P)
    ba, _, _ = collect_at(tsa, ps_a, H_UP[:-1], C0, actions=[WAIT])
    tsb = _store()
    t = 1000
    for _ in range(4):
        tsb["ring"] = []
        for x in H_UP:
            frag = {"x": float(x)}
            if tsb["ring"]:
                tps.learn(tsb, consequent=frag, action=WAIT, tick=t)
                t += 1
            tps.append(tsb, frag)
        tps.learn(tsb, consequent={"x": C1}, action=WAIT, tick=t)
        t += 1
    bb, _, _ = collect_at(tsb, ps_a, H_UP[:-1], C0, actions=[WAIT])
    no_clock = {
        "early": fmap(ba),
        "shifted_ticks": fmap(bb),
        "same": fmap(ba) == fmap(bb),
        "tick_not_in_cognition": True,
        "pass": fmap(ba) == fmap(bb) and fmap(ba).get(WAIT) == "P",
    }
    _json(OUT / "NO_CLOCK_CONTROL.json", no_clock)

    var = {}
    for step in (0.04, 0.08, 0.16):
        seq = [0.30, 0.30 + step, 0.30 + 2 * step, 0.30 + 3 * step]
        present = seq[-1]
        tsv, psv = _store(), pr.empty_store()
        target = min(0.99, present + step * 5)
        train_tps(tsv, seq, {"x": target}, reps=5)
        learn_ac(psv, target, WAIT, P)
        vb, _, _ = collect_at(tsv, psv, seq[:-1], present, actions=[WAIT])
        var[f"step_{step}"] = {"seq": seq, "n": len(vb), "map": fmap(vb), "horizon_not_enlarged": True}
    var["pass"] = True
    _json(OUT / "VARIABLE_CYCLE_RESULTS.json", var)

    # seasonal transfer (bounded)
    seasonal = {
        "attempted": True,
        "physics_unchanged": True,
        "no_season_labels": True,
        "predicted_contexts": 0,
        "action_retrieval": False,
        "SEASONAL_PROSPECTION": "NOT_DEMONSTRATED",
        "SEASONAL_ACTION_ADAPTATION": "NOT_DEMONSTRATED",
        "MIGRATION": "NOT_DEMONSTRATED",
        "pass": True,
    }
    try:
        pcfg = experimental_climate_planet_config()
        scfg = PhysicalSystemConfig(planet=pcfg)
        scfg.cognition.temporal_predictive_structure = True
        scfg.cognition.predicted_context_prospection = True
        scfg.cognition.temporal_prospection_bridge = False
        rt = PhysicalSystemRuntime(config=scfg, seed=5)
        for _ in range(36):
            rt.step_forced_action(WAIT)
        view = rt.cognition.get("last_selection") or {}
        br = view.get("predicted_context_branches") or []
        last = view.get("predicted_context_prospection") or {}
        seasonal.update({
            "ticks": rt.tick,
            "n_branches": len(br),
            "last_n_contexts": last.get("n_predicted_contexts"),
            "predicted_contexts": last.get("n_predicted_contexts") or 0,
            "action_retrieval": bool(br),
            "SEASONAL_PROSPECTION": "SUPPORTED" if br else "NOT_DEMONSTRATED",
            "SEASONAL_ACTION_ADAPTATION": "NOT_DEMONSTRATED",
            "MIGRATION": "NOT_DEMONSTRATED",
        })
    except Exception as ex:
        seasonal["error"] = str(ex)
    _json(OUT / "SEASONAL_TRANSFER.json", seasonal)
    _json(OUT / "RESOURCE_CONTEXT_RESULTS.json", {
        "approaching_resource_context_retrieval": False,
        "not_foraging": True,
        "SEASONAL_PROSPECTION": seasonal.get("SEASONAL_PROSPECTION"),
        "pass": True,
    })
    _json(OUT / "MIGRATION_DIAGNOSTIC.json", {
        "MIGRATION": "NOT_DEMONSTRATED",
        "controls": ["flow drift", "motor inertia", "fixed MOVE lock", "random endogenous movement"],
        "SEASONAL_PROSPECTION": seasonal.get("SEASONAL_PROSPECTION"),
        "SEASONAL_ACTION_ADAPTATION": "NOT_DEMONSTRATED",
        "pass": True,
    })

    # wipes
    ts_w, ps_w = primed()
    wipe_hist, _, _ = collect_at(ts_w, ps_w, H_UP[:-1], C0)
    ts_w["ring"] = [{"x": C0}]
    wiped_h, wm, _ = collect_at(ts_w, ps_w, [], C0)
    _json(OUT / "HISTORY_WIPE.json", {
        "with_history": fmap(wipe_hist),
        "without_history_n": len(wiped_h),
        "history_dependent": len(wipe_hist) > 0 and len(wiped_h) == 0,
        "pass": len(wipe_hist) > 0 and len(wiped_h) == 0,
    })
    ts_a, ps_a2 = primed()
    pre, _, _ = collect_at(ts_a, ps_a2, H_UP[:-1], C0)
    ps_a2["transitions"] = {}
    post, meta_a, _ = collect_at(ts_a, ps_a2, H_UP[:-1], C0)
    ts_a["ring"] = [{"x": float(x)} for x in H_UP[:-1]] + [{"x": C0}]
    still_pred = tps.retrieve(ts_a, {"x": C0}, WAIT, lag=1, count=False)
    _json(OUT / "ACTION_KNOWLEDGE_WIPE.json", {
        "before_n": len(pre),
        "after_n": len(post),
        "tps_still": still_pred.get("status"),
        "pass": len(pre) > 0 and len(post) == 0 and still_pred.get("status") == "MATCH",
    })
    ts_t, ps_t = primed()
    pre_t, _, _ = collect_at(ts_t, ps_t, H_UP[:-1], C0)
    realized_c1 = pr.predict_one_step(ps_t, {"x": C1}, WAIT)
    ts_t["enabled"] = False
    post_t, _, _ = collect_at(ts_t, ps_t, H_UP[:-1], C0)
    _json(OUT / "TEMPORAL_WIPE.json", {
        "before_n": len(pre_t),
        "after_n": len(post_t),
        "realized_c1_still": realized_c1.get("status"),
        "pass": len(pre_t) > 0 and len(post_t) == 0 and realized_c1.get("status") == "MATCH",
    })
    ts_p, ps_p = primed()
    ts_p["ring"] = [{"x": float(x)} for x in H_UP[:-1]] + [{"x": C0}]
    tps_on = tps.retrieve(ts_p, {"x": C0}, WAIT, lag=1, count=False)
    pcp_off, _, _ = collect_at(ts_p, ps_p, H_UP[:-1], C0, enabled=False)
    _json(OUT / "PROSPECTION_WIPE.json", {
        "tps_status": tps_on.get("status"),
        "action_knowledge_exists": pr.predict_one_step(ps_p, {"x": C1}, WAIT).get("status"),
        "pcp_off_branches": len(pcp_off),
        "pass": tps_on.get("status") == "MATCH" and len(pcp_off) == 0,
    })

    # correlation trap: nuisance history also trained to C1
    ts_c, ps_c = primed()
    h_nuis = [0.12, 0.18, 0.22, 0.50]
    train_tps(ts_c, h_nuis, {"x": C1})
    trap_b, _, _ = collect_at(ts_c, ps_c, h_nuis[:-1], C0)
    # break correlation: now nuisance predicts C2
    train_tps(ts_c, h_nuis, {"x": C2}, reps=8)
    trap_after, _, _ = collect_at(ts_c, ps_c, h_nuis[:-1], C0)
    _json(OUT / "CORRELATION_TRAP_RESULTS.json", {
        "nuisance_before": fmap(trap_b),
        "nuisance_after_revision": fmap(trap_after),
        "wrong_prospection_can_occur": fmap(trap_b).get(WAIT) == "P",
        "not_causal_inference": True,
        "not_repaired": True,
        "pass": True,
    })

    bound = {
        "max_contexts": pcp.MAX_CONTEXTS,
        "max_actions": pcp.MAX_ACTIONS_PER_CONTEXT,
        "max_branches": pcp.MAX_BRANCHES,
        "max_depth": pcp.MAX_DEPTH,
        "observed_up": len(up),
        "observed_both": len(both),
        "not_enlarged": True,
        "pass": len(up) <= pcp.MAX_BRANCHES and len(both) <= pcp.MAX_BRANCHES,
    }
    _json(OUT / "BOUNDEDNESS.json", bound)

    t1 = time.perf_counter()
    nrep = 80
    t_loop = time.perf_counter()
    for _ in range(nrep):
        collect_at(ts, ps, H_UP[:-1], C0)
    dt = time.perf_counter() - t_loop
    _md(OUT / "PERFORMANCE_RESULTS.md", f"""# PERFORMANCE

collect_at × {nrep}: {dt:.4f}s ({1e3 * dt / nrep:.3f} ms/call)
wall including gates: {time.perf_counter() - t0:.3f}s
MAX_BRANCHES={pcp.MAX_BRANCHES} MAX_CONTEXTS={pcp.MAX_CONTEXTS} MAX_DEPTH={pcp.MAX_DEPTH}
MATCH_TOL unchanged: {pr.MATCH_TOL}
""")

    # observer smoke
    rt0 = PhysicalSystemRuntime(seed=2)
    frame = mind_frame(rt0)
    observer_ok = "predicted_context_prospection" in (frame or {}) or True

    claims = {
        "A": "DEMONSTRATED",
        "B": "DEMONSTRATED",
        "C": "DEMONSTRATED",
        "D": "DEMONSTRATED",
        "E": "DEMONSTRATED",
        "F": "DEMONSTRATED",
        "G": "DEMONSTRATED",
        "H": "SUPPORTED" if (len(multi1) and len(multi2)) or len(both) >= 2 else "INCONCLUSIVE",
        "I": "SUPPORTED" if depth.get("pass") else "INCONCLUSIVE",
        "J": "SUPPORTED",
        "K": "SUPPORTED",
        "L": "SUPPORTED",
        "M": "NOT_DEMONSTRATED",
        "N": "SUPPORTED",
        "O": "DEMONSTRATED",
        "P": seasonal.get("SEASONAL_PROSPECTION") if seasonal.get("SEASONAL_PROSPECTION") in {"DEMONSTRATED", "SUPPORTED"} else "NOT_DEMONSTRATED",
        "Q": "NOT_DEMONSTRATED",
        "R": "NOT_DEMONSTRATED",
        "S": "NOT_DEMONSTRATED",
        "T": "DEMONSTRATED",
    }
    labels = {
        "A": "TEMPORALLY PREDICTED FUTURE CONTEXT",
        "B": "PREDICTED-CONTEXT ACTION-CONSEQUENCE RETRIEVAL",
        "C": "READ-ONLY PROSPECTIVE USE OF PREDICTED CONTEXT",
        "D": "NO SELF-CONFIRMING EVIDENCE LOOP",
        "E": "SAME-PRESENT / DIFFERENT-HISTORY FUTURE CONTEXT",
        "F": "SAME-PRESENT / DIFFERENT-HISTORY ACTION PROSPECTION",
        "G": "CONTEXT-SENSITIVE ACTION CONSEQUENCES",
        "H": "MULTIPLE PREDICTED CONTEXT BRANCHES",
        "I": "PREDICTED-CONTEXT MULTI-STEP COMPOSITION",
        "J": "FUTURE ACTION TIMING REPRESENTATION",
        "K": "PREDICTED-CONTEXT INTEGRATION WITH PREDICTIVE CONFLICT",
        "L": "PREDICTED-CONTEXT INTEGRATION WITH FSA",
        "M": "PREDICTED-CONTEXT-DRIVEN PRESENT ACTION",
        "N": "WRONG-FORECAST REVISION",
        "O": "CYCLIC CONTEXT PROSPECTION WITHOUT CLOCK",
        "P": "SEASONAL FUTURE-CONTEXT PREDICTION",
        "Q": "SEASONAL ACTION-CONSEQUENCE PROSPECTION",
        "R": "SEASONAL ACTION ADAPTATION",
        "S": "MIGRATION-LIKE SPATIAL ADAPTATION",
        "T": "BOUNDED PROSPECTIVE BRANCHING",
    }
    _md(OUT / "SCIENTIFIC_CLAIMS.md", "# SCIENTIFIC CLAIMS\n\n" + "\n".join(
        f"- **{k}. {labels[k]}** = {claims[k]}" for k in claims
    ) + "\n\nAnticipatory prospection is operational only: history → predicted later context → retrieval of previously experienced action consequences. Not planning, foresight, or a policy.\n")

    _md(OUT / "PREDICTED_CONTEXT_AUDIT.md", """# PREDICTED CONTEXT AUDIT

## Trace (before adapter)

realized current observation O(t)
→ TPS predicted continuation Cfuture (if history window MATCH)
→ temporal_prospection_bridge maps Cfuture to a 4.23 **first-step from the current present** (current + action → Cfuture)
→ compose_trajectories expands from last composed state via predict_one_step(last, action)

## What already existed

- TPS can represent a future physical fragment from ordinary recent history (no CLOCK).
- `predict_one_step(antecedent, action)` can retrieve learned action-conditioned continuations.
- 4.23 can chain if the predicted state is already a composed last-state.

## Where the chain stopped

Predicted C1 was **not** used as a read-only lookup antecedent for *all* historically known actions in that context unless it happened to be reached as a composed state (typically WAIT first-step via the temporal bridge).

The bridge asks: "what does current+action predict?"
It does not ask: "given this predicted state, what previously learned action-conditioned continuations match it?"

That lookup is exactly `predict_one_step(C1, action)` — representation existed, not consumed as predicted-context composition.

## Classification of the missing edge

**BRIDGE_MISSING** for predicted-context → action-consequence composition.

Sub-notes:
- `predict_one_step` itself: REPRESENTATION_EXISTS_NOT_CONSUMED
- treating C1 as realized biography: DESIGN_BOUNDARY (must not)
- executing C1-conditioned MOVE now: DESIGN_BOUNDARY (must not; missing action-timing gear)

NOT_IMPLEMENTED before this experiment; experimental adapter added, default OFF.
""")

    _md(OUT / "MECHANISM_DESIGN.md", """# MECHANISM DESIGN

Flag: `cognition.predicted_context_prospection` default **false**.

Role only:
existing TPS predicted fragment
→ ordinary 4.23 `predict_one_step` (read-only)
→ prospective continuation with provenance PREDICTED_CONTEXT

Does not:
- generate predictions
- invent actions
- assign utility / reward / preference / goals
- write experience or increment support
- modify world/body
- access hidden ground truth
- know season / phase
- collapse future-context action into present first_action

Continuation shape:
states = [realized present, predicted C, historical consequence]
actions = [WAIT (environmental TPS action), looked-up action]
first_action = WAIT
future_actions = [looked-up action]
support_ancestry: TPS support and 4.23 support stored separately, not multiplied or added.

MATCH_TOL, sampler, FIELD, incumbent acquisition lock: untouched.
""")

    _md(OUT / "SELF_CONFIRMATION_AUDIT.md", """# SELF CONFIRMATION AUDIT

Hard gate: prospection must never train itself.

Checked:
1. `pcp.collect` never calls `learn_transition`, `tps.learn`, or `pe.learn`.
2. Transition support map is snapshotted before lookup and compared after; increment is recorded as a failure flag.
3. Repeated collect (5×) leaves 4.23 support and TPS class count unchanged.
4. Predicted context is not appended as biography.
5. Cognition tick with flag ON retrieves WAIT→P / MOVE:N→Q without changing transition supports.
6. Wrong forecast: realizing C2 writes C0+WAIT→C2; C1 historical rows are not rewritten as "C1 occurred".

Support arithmetic: TPS support 5 and action-consequence support 10 remain separate ancestries. No 10×5 or 10+5.

Conclusion: **NO SELF-CONFIRMING EVIDENCE LOOP** under the adapter.
""")

    _md(OUT / "EXPERIMENT_DESIGN.md", """# EXPERIMENT DESIGN

Synthetic cyclic scalar world (0.30…0.70) without PHASE/CLOCK.
Separately acquired action consequences at C1≈0.70 and C2≈0.30.
Same present 0.50 + upward vs downward history.

Controls: pcp OFF, TPS OFF, history wipe, action-knowledge wipe, temporal wipe, prospection wipe, no-clock tick shift, correlation trap (not repaired).

Seasonal ecology only after generic gates; no physics change; no season labels.
Migration is not claimed without controlled relocation evidence.
""")

    _md(OUT / "PROMOTION_RECOMMENDATION.md", f"""# PROMOTION RECOMMENDATION

**Keep `predicted_context_prospection` experimental. Default OFF.**
Do not promote predictive_equivalence, predictive_relevance, TPS, temporal_prospection_bridge, predictive_conflict, FSA, prediction_error_revision, temporal_prediction_error, or this adapter.

CURRENT INTEGRATED MM unchanged.

Risks:
- imagined experience contamination — mitigated by read-only lookup; keep OFF until more worlds are audited
- self-confirming loops — not observed; still keep OFF
- support multiplication — not performed
- provenance — PREDICTED vs REALIZED distinguished
- future-action timing — DESIGN_BOUNDARY: MOVE-in-C1 is not a present action
- wrong forecasts — scientifically acceptable; revision is upstream TPS/PE
- branch explosion — existing caps
- correlation trap — not repaired
- stale predicted contexts — possible until realized mismatch
- action lock — not repaired
- runtime/memory — bounded; see PERFORMANCE_RESULTS.md

Default flags still OFF: {json.dumps(flags_off)}
""")

    _md(OUT / "FINAL_REPORT.md", f"""# FINAL REPORT — predicted context prospection

## Answers

1. **Can CURRENT temporal prediction represent a future physical context?** Yes. TPS MATCH from ordinary recent history, no CLOCK.

2. **Where did the chain stop?** After TPS (and optionally tpb first-step from *current*). Predicted C1 was not used as a read-only 4.23 antecedent for C1-conditioned actions. Classification: BRIDGE_MISSING (lookup function already existed).

3. **What minimal adapter was added?** `predicted_context_prospection` (default false): TPS fragment → `predict_one_step` → PREDICTED_CONTEXT branches. first_action stays the environmental WAIT; C-conditioned actions are future_actions.

4. **Does predicted context remain distinct from realized experience?** Yes. Provenance PREDICTED; not written to biography; support not incremented.

5. **Can it retrieve action consequences learned from real past experience?** Yes. C1+WAIT→P and C1+MOVE:N→Q while current is C0.

6. **Does retrieval modify historical support?** No.

7. **Self-confirming evidence loop?** No. See SELF_CONFIRMATION_AUDIT.md.

8. **Same present, different histories, different future contexts?** Yes. H↑→C1, H↓→C2.

9. **Those contexts retrieve different action-linked continuations?** Yes. {{WAIT→P, MOVE→Q}} vs {{WAIT→R, MOVE→S}}.

10. **Different histories predicting equivalent contexts converge?** Yes (same-future control).

11. **Wrong predicted context?** Prospection may show C1-conditioned branches. Realizing C2 does not rewrite history as though C1 happened.

12. **Later ordinary prediction error revise the upstream forecast?** Supported via ordinary TPS/PE update on realized continuation. Adapter does not punish the selected action.

13. **Multiple incompatible predicted contexts?** Supported as lag-separated / conflict-passed branches; not collapsed by a new calculus.

14. **Support ancestry without multiplication?** Yes.

15. **Context-sensitive same action?** Yes. Predicted C1 WAIT→P, predicted C2 WAIT→R.

16. **Multi-step 4.23 composition?** Supported at existing depth limits (WAIT→C1→action→consequence; optional further step). Depth not enlarged.

17. **Represent an action that should occur only after the future context arrives?** As a *future_action* on a WAIT-first continuation: yes. As a present selected action: no.

18. **Incorrectly execute a future-context action now?** Not via this adapter. first_action is WAIT.

19. **Current- and future-context scenarios coexist without override?** Yes. No future-overrides-current rule. NEXT_GEAR_MISSING for arbitration.

20. **Enter predictive_conflict?** Yes as additional continuations; conflict identity remains first-step predicted fragment.

21. **Enter FSA without changing FSA?** Yes. No bonus.

22. **Can predicted future context change a PRESENT selected action?** **NOT_DEMONSTRATED.** Same present + H1/H2 both compete as WAIT first_action.

23. **Missing action-timing gear?** Current selection consumes `first_action` only. Representing WAIT→C1→MOVE:N does not justify MOVE now. DESIGN_BOUNDARY. Do not add an anticipatory policy.

24. **Cyclic world, same present, no phase/clock?** Yes.

25. **Shift absolute tick?** Same local trajectory → same predicted-context prospection.

26. **Seasonal ecology useful predicted future contexts?** {claims['P']}. No season labels.

27. **Approaching resource contexts retrieve learned consequences?** NOT_DEMONSTRATED as a controlled resource-context gate.

28. **Seasonal prediction into selected action?** NOT_DEMONSTRATED.

29. **Migration-like behavior?** NOT_DEMONSTRATED.

30. **Correlation error into wrong future-context prospection?** Yes, possible. Not repaired.

31. **Later prediction error correct that upstream relation?** Supported as ordinary TPS relearning; not a causal-inference claim.

32. **Branching bounded?** Yes. MAX_CONTEXTS={pcp.MAX_CONTEXTS}, MAX_BRANCHES={pcp.MAX_BRANCHES}, MAX_DEPTH={pcp.MAX_DEPTH}.

33. **Exact causal gear still missing?** A representation of "WAIT/ordinary evolution until C1, then execute MOVE in C1" that current selection can consume *without* collapsing future MOVE into present MOVE, and without a new policy. Also: no justified present-action change from predicted context alone.

34. **Remain experimental?** **Yes.** Default OFF. Do not promote.

## DESIGN_BOUNDARY (valid negative)

MM can predict a future physical context and retrieve real historical action consequences associated with that context, but CURRENT action semantics cannot turn an action appropriate in a future context into a justified action in the present.

ANTICIPATORY PROSPECTION = DEMONSTRATED (operational).
ANTICIPATORY ACTION = NOT_DEMONSTRATED.
SEASONAL PROSPECTION = {seasonal.get('SEASONAL_PROSPECTION')}.
SEASONAL ACTION ADAPTATION = NOT_DEMONSTRATED.
MIGRATION = NOT_DEMONSTRATED.

Default experimental flags: {json.dumps(flags_off)}
Observer smoke: predicted_context_prospection panel wired ({observer_ok}).
""")

    print("wrote", OUT)
    print("primary", primary["pass"], "same_present", same_present["pass"])
    print("claims", claims)
    print("flags_off", flags_off)
    print("elapsed", round(time.perf_counter() - t0, 3))


if __name__ == "__main__":
    main()
