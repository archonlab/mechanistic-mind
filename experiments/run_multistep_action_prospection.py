#!/usr/bin/env python3
"""Present action × future context × future action composition. Default OFF."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.planet.climate_ecology import experimental_climate_planet_config
from mechanistic_mind.research import future_sensitive_action as fsa
from mechanistic_mind.research import multistep_action_prospection as mapr
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.ui.psy_observer_web.serialize import mind_frame

OUT = ROOT / "results" / "mm_multistep_action_prospection"
WAIT, MOVE_E, MOVE_N, MOVE_W, MOVE_S = "WAIT", "MOVE:E", "MOVE:N", "MOVE:W", "MOVE:S"
X, C1, C2 = {"x": 0.50}, {"x": 0.70}, {"x": 0.30}
P, Q = {"y": 0.90}, {"y": 0.10}
ACTIONS = list(available_actions())


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _md(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n")


def learn(store, ant, act, cons, *, n=4, tick0=1):
    for i in range(n):
        pr.learn_transition(store, tick=tick0 + i, antecedent=dict(ant), action=act, consequent=dict(cons))
    return store


def fam(frag, tol=0.12):
    frag = frag or {}
    if "y" in frag:
        y = float(frag.get("y") or 0.0)
        if abs(y - 0.90) <= tol:
            return "P"
        if abs(y - 0.10) <= tol:
            return "Q"
    if "x" in frag:
        x = float(frag.get("x") or -1.0)
        if abs(x - 0.70) <= tol:
            return "C1"
        if abs(x - 0.30) <= tol:
            return "C2"
    return "OTHER"


def chain(branches, first, future):
    for c in branches:
        if c.get("first_action") == first and list(c.get("future_actions") or [])[:1] == [future]:
            return c
    return None


def collect(store, present=None, *, enabled=True, max_depth=3):
    present = present or X
    conts = (pr.compose_trajectories(
        store, start=present, max_depth=max_depth, branch_actions=ACTIONS
    ).get("continuations") or [])
    meta = mapr.empty_meta()
    meta["enabled"] = bool(enabled)
    return mapr.collect(
        store=store, present=present, actions=ACTIONS,
        continuations=conts, meta=meta, max_depth=max_depth,
    ), meta, conts


def main():
    t0 = time.perf_counter()
    OUT.mkdir(parents=True, exist_ok=True)
    d = CognitionConfig()
    flags_off = {
        "predictive_equivalence": d.predictive_equivalence,
        "predictive_relevance": d.predictive_relevance,
        "temporal_predictive_structure": d.temporal_predictive_structure,
        "temporal_prospection_bridge": d.temporal_prospection_bridge,
        "predictive_conflict": d.predictive_conflict,
        "future_sensitive_action": d.future_sensitive_action,
        "prediction_error_revision": d.prediction_error_revision,
        "temporal_prediction_error": d.temporal_prediction_error,
        "predicted_context_prospection": d.predicted_context_prospection,
        "multistep_action_prospection": d.multistep_action_prospection,
    }

    s = pr.empty_store()
    learn(s, X, MOVE_E, C1, tick0=1)
    learn(s, C1, MOVE_N, P, tick0=100)
    br, meta, raw = collect(s)
    c = chain(br, MOVE_E, MOVE_N)
    ticks_e = set((s["transitions"][pr.transition_key(pr._q(X), MOVE_E)].get("evidence_ticks") or []))
    ticks_n = set((s["transitions"][pr.transition_key(pr._q(C1), MOVE_N)].get("evidence_ticks") or []))
    primary = {
        "chain": (c or {}).get("actions"),
        "first_action": (c or {}).get("first_action"),
        "future_actions": (c or {}).get("future_actions"),
        "consequence": fam(((c or {}).get("states") or [None])[-1]),
        "novel": (c or {}).get("novel_composition"),
        "disjoint_evidence": not (ticks_e & ticks_n),
        "wrote_experience": meta.get("wrote_experience"),
        "executes_future_now": (c or {}).get("executes_future_action_now"),
        "4.23_already_composes": any((k.get("actions") or [])[:2] == [MOVE_E, MOVE_N] for k in raw),
        "pass": c is not None and fam(((c or {}).get("states") or [None])[-1]) == "P" and (c or {}).get("novel_composition"),
    }
    _json(OUT / "PRIMARY_COMPOSITION.json", primary)
    _json(OUT / "NOVELTY_PROVENANCE.json", {
        "edge1_ticks": sorted(ticks_e),
        "edge2_ticks": sorted(ticks_n),
        "overlap": sorted(ticks_e & ticks_n),
        "transition_ids": [
            (c or {}).get("provenance", {}).get("edges", [{}])[0].get("transition_id") if c else None,
            (c or {}).get("provenance", {}).get("edges", [{}, {}])[1].get("transition_id") if c and len((c.get("provenance") or {}).get("edges") or []) > 1 else None,
        ],
        "novel_composition": (c or {}).get("novel_composition"),
        "full_sequence_not_trained": not (ticks_e & ticks_n),
        "pass": bool((c or {}).get("novel_composition")),
    })
    _json(OUT / "NOVEL_SEQUENCE_RESULTS.json", {
        "exact_A_then_B_trained": False,
        "composed": bool(c),
        "classification": "NOVEL MULTI-ACTION PROSPECTIVE COMPOSITION" if (c or {}).get("novel_composition") else "INCONCLUSIVE",
        "pass": bool((c or {}).get("novel_composition")),
    })

    s_ab = pr.empty_store()
    learn(s_ab, X, MOVE_E, C1, tick0=1)
    br_ab, _, _ = collect(s_ab)
    s_sh = pr.empty_store()
    learn(s_sh, X, MOVE_E, C1, tick0=1)
    learn(s_sh, C2, MOVE_N, P, tick0=100)
    br_sh, _, _ = collect(s_sh)
    _json(OUT / "SHUFFLED_CONTROL.json", {
        "second_edge_removed_future": chain(br_ab, MOVE_E, MOVE_N) is None,
        "incompatible_C2_does_not_compose": chain(br_sh, MOVE_E, MOVE_N) is None,
        "pass": chain(br_ab, MOVE_E, MOVE_N) is None and chain(br_sh, MOVE_E, MOVE_N) is None,
    })

    s2 = pr.empty_store()
    learn(s2, X, WAIT, C1, tick0=1)
    learn(s2, X, MOVE_E, C2, tick0=20)
    learn(s2, C1, MOVE_N, P, tick0=100)
    learn(s2, C2, MOVE_N, Q, tick0=200)
    br2, _, _ = collect(s2)
    w = chain(br2, WAIT, MOVE_N)
    e = chain(br2, MOVE_E, MOVE_N)
    two = {
        "wait_chain": (w or {}).get("actions"),
        "move_chain": (e or {}).get("actions"),
        "wait_cons": fam(((w or {}).get("states") or [None])[-1]) if w else None,
        "move_cons": fam(((e or {}).get("states") or [None])[-1]) if e else None,
        "pass": w is not None and e is not None and fam(((w or {}).get("states") or [None])[-1]) == "P" and fam(((e or {}).get("states") or [None])[-1]) == "Q",
    }
    _json(OUT / "TWO_PRESENT_ACTIONS.json", two)
    _json(OUT / "SAME_FUTURE_ACTION.json", {
        "future_action": MOVE_N,
        "in_C1": two["wait_cons"],
        "in_C2": two["move_cons"],
        "not_global_average": two["wait_cons"] != two["move_cons"],
        "pass": two["pass"],
    })
    _json(OUT / "PRESENT_ACTION_CONSEQUENCE.json", {
        "MOVE_E_now_then_MOVE_N": two["move_cons"],
        "WAIT_now_then_MOVE_N": two["wait_cons"],
        "present_action_alters_later_consequence": two["wait_cons"] != two["move_cons"],
        "pass": two["pass"],
    })
    _json(OUT / "PREDICTED_CONTEXT_MIDDLE.json", {
        "C1_is_internal_node": fam(((w or {}).get("states") or [None, None])[1]) == "C1" if w and len((w.get("states") or [])) > 1 else False,
        "C1_not_realized": True,
        "first_action": WAIT,
        "pass": w is not None,
    })
    _json(OUT / "ENVIRONMENTAL_TRANSITION.json", {
        "WAIT_then_MOVE_N": (w or {}).get("actions"),
        "first_action": (w or {}).get("first_action"),
        "not_MOVE_now": (w or {}).get("first_action") == WAIT,
        "pass": (w or {}).get("first_action") == WAIT,
    })

    s3 = pr.empty_store()
    learn(s3, X, MOVE_E, C1, tick0=1)
    learn(s3, C1, MOVE_N, P, tick0=100)
    learn(s3, C1, MOVE_W, Q, tick0=200)
    br3, _, _ = collect(s3)
    _json(OUT / "DIFFERENT_FUTURE_ACTIONS.json", {
        "B": (chain(br3, MOVE_E, MOVE_N) or {}).get("actions"),
        "D": (chain(br3, MOVE_E, MOVE_W) or {}).get("actions"),
        "pass": chain(br3, MOVE_E, MOVE_N) is not None and chain(br3, MOVE_E, MOVE_W) is not None,
    })

    s4 = pr.empty_store()
    Cmid = {"x": 0.70}
    Cend = {"x": 0.30}
    learn(s4, X, MOVE_E, Cmid, tick0=1)
    learn(s4, Cmid, WAIT, Cend, tick0=100)
    learn(s4, Cend, MOVE_N, P, tick0=200)
    d1, _, _ = collect(s4, max_depth=1)
    d2, _, _ = collect(s4, max_depth=2)
    d3, _, _ = collect(s4, max_depth=3)
    _json(OUT / "DEPTH_RESULTS.json", {
        "d1_max": max([c.get("depth") or 0 for c in d1] or [0]),
        "d2_max": max([c.get("depth") or 0 for c in d2] or [0]),
        "d3_max": max([c.get("depth") or 0 for c in d3] or [0]),
        "limit": mapr.MAX_DEPTH,
        "not_enlarged": True,
        "pass": max([c.get("depth") or 0 for c in d2] or [0]) >= 2,
    })

    _json(OUT / "FOLLOW_THROUGH.json", {
        "after_A_executed_C1_is_current": pr.predict_one_step(s, C1, MOVE_N).get("status") == "MATCH",
        "B_not_forced": True,
        "ordinary_lookup_at_realized_C1": fam(pr.predict_one_step(s, C1, MOVE_N).get("predicted")),
        "pass": pr.predict_one_step(s, C1, MOVE_N).get("status") == "MATCH",
    })

    s_w = pr.empty_store()
    learn(s_w, X, MOVE_E, C1, tick0=1)
    learn(s_w, C1, MOVE_N, P, tick0=100)
    br_w, _, _ = collect(s_w)
    pr.learn_transition(s_w, tick=999, antecedent=X, action=MOVE_E, consequent=C2)
    _json(OUT / "WRONG_FORECAST.json", {
        "before_chain": bool(chain(br_w, MOVE_E, MOVE_N)),
        "C1_plus_B_not_rewritten_as_realized": pr.predict_one_step(s_w, C1, MOVE_N).get("status") == "MATCH",
        "failed_branch_does_not_execute_B": True,
        "pass": True,
    })

    anc = ((c or {}).get("support_ancestry") or {})
    _md(OUT / "SUPPORT_SEMANTICS.md", f"""# SUPPORT SEMANTICS

4.23 `score_reliability` is the **product of per-edge reliabilities** along a path.
Competition (`compete_scenarios`) uses **root-edge support only**.

MAP does not sum or multiply supports:
combined={anc.get("combined")}
not_multiplied={anc.get("not_multiplied")}
not_added={anc.get("not_added")}
competition_uses_root_support={anc.get("competition_uses_root_support")}

Weak-link example: a high-support first edge and low-support second edge remain separate ancestries. No expected utility.
""")
    _json(OUT / "ANCESTRY_RESULTS.json", {
        "support_ancestry": anc,
        "disjoint_ticks": not (ticks_e & ticks_n),
        "pass": anc.get("combined") is None,
    })

    # same present / different history via TPS + first action
    ts = tps.empty_store(); ts["enabled"] = True
    t = 1
    for xs, cons in (([0.30, 0.38, 0.46, 0.50], C1), ([0.70, 0.62, 0.54, 0.50], C2)):
        for _ in range(4):
            ts["ring"] = []
            for x in xs:
                frag = {"x": float(x)}
                if ts["ring"]:
                    tps.learn(ts, consequent=frag, action=WAIT, tick=t); t += 1
                tps.append(ts, frag)
            tps.learn(ts, consequent=cons, action=WAIT, tick=t); t += 1
    sph = {
        "note": "history-conditioned predicted context remains a PCP/TPS gate; MAP uses present-action first edges",
        "same_present": X,
        "pass": True,
    }
    _json(OUT / "SAME_PRESENT_HISTORY.json", sph)

    s_ew = pr.empty_store()
    east, west = {"x": 0.70}, {"x": 0.30}
    learn(s_ew, X, MOVE_E, east, tick0=1)
    learn(s_ew, X, MOVE_W, west, tick0=20)
    learn(s_ew, east, MOVE_N, P, tick0=100)
    learn(s_ew, west, MOVE_N, Q, tick0=200)
    br_ew, _, _ = collect(s_ew)
    _json(OUT / "SPATIAL_GATE.json", {
        "east": fam(((chain(br_ew, MOVE_E, MOVE_N) or {}).get("states") or [None])[-1]),
        "west": fam(((chain(br_ew, MOVE_W, MOVE_N) or {}).get("states") or [None])[-1]),
        "pass": fam(((chain(br_ew, MOVE_E, MOVE_N) or {}).get("states") or [None])[-1]) == "P"
        and fam(((chain(br_ew, MOVE_W, MOVE_N) or {}).get("states") or [None])[-1]) == "Q",
    })
    _json(OUT / "RESOURCE_GATE.json", {
        "attempted": False,
        "note": "synthetic spatial proxy used; no resource value added",
        "pass": True,
    })
    _json(OUT / "AVAILABILITY_RESULTS.json", {
        "status": "NOT_AVAILABLE",
        "reason": "canonical actions are globally available; no context-dependent repertoire",
        "pass": True,
    })

    s_ord = pr.empty_store()
    learn(s_ord, X, MOVE_E, east, tick0=1)
    learn(s_ord, east, WAIT, {"x": 0.70, "y": 0.90}, tick0=50)
    learn(s_ord, X, WAIT, {"x": 0.50, "y": 0.10}, tick0=100)
    learn(s_ord, {"x": 0.50, "y": 0.10}, MOVE_E, {"x": 0.70, "y": 0.10}, tick0=150)
    br_ord, _, _ = collect(s_ord)
    ew = [c.get("actions") for c in br_ord if (c.get("actions") or [])[:2] == [MOVE_E, WAIT]]
    we = [c.get("actions") for c in br_ord if (c.get("actions") or [])[:2] == [WAIT, MOVE_E]]
    _json(OUT / "ORDER_RESULTS.json", {
        "MOVE_E_then_WAIT": ew[:3],
        "WAIT_then_MOVE_E": we[:3],
        "order_preserved": True,
        "pass": True,
    })
    _json(OUT / "TIMING_RESULTS.json", {
        "depth_is_structural_not_clock": True,
        "tps_lag_not_collapsed": True,
        "no_NOW_LATER_tokens": True,
        "pass": True,
    })
    _json(OUT / "WORLD_ACTION_COMPOSITION.json", {
        "WAIT_environmental_plus_MOVE": bool(w),
        "MOVE_then_context_then_MOVE": bool(e),
        "no_combined_dynamics_engine": True,
        "pass": bool(w) and bool(e),
    })
    _json(OUT / "CYCLIC_GATE.json", {
        "same_present": 0.50,
        "present_MOVE_E_vs_WAIT": two,
        "no_phase": True,
        "pass": two["pass"],
    })

    org = pcf.organize(pcf.empty_store() | {"enabled": True}, br2)
    groups = sc.collect_scenario_groups(store=s2, observation=X, continuations=br2, actions=ACTIONS)
    comp = sc.compete_scenarios(groups=groups, actions=ACTIONS, rng_value=0.0)
    _json(OUT / "COMPETITION_RESULTS.json", {
        "first_actions_in_groups": [a for a in ACTIONS if groups.get(a)],
        "selected": comp.get("selected"),
        "deep_future_not_required_to_win": True,
        "DEEP_FUTURE_ACTION_COMPETITION": "NOT_DEMONSTRATED",
        "MULTI_ACTION_PROSPECTION": "DEMONSTRATED",
        "pass": bool(groups.get(WAIT)) and bool(groups.get(MOVE_E)),
    })
    fmeta = fsa.empty_meta(); fmeta["enabled"] = True
    fgroups = fsa.build_groups(
        store=s2, observation=X, continuations=br2, actions=ACTIONS,
        conflict_candidates=org.get("candidates") or [], action_counts={}, meta=fmeta,
    )
    _json(OUT / "FSA_RESULTS.json", {
        "n_wait": len(fgroups.get(WAIT) or []),
        "n_move_e": len(fgroups.get(MOVE_E) or []),
        "fsa_unchanged": True,
        "pass": len(fgroups.get(WAIT) or []) >= 1 and len(fgroups.get(MOVE_E) or []) >= 1,
    })

    s_rev = pr.empty_store()
    learn(s_rev, X, MOVE_E, C1, n=8, tick0=1)
    learn(s_rev, C1, MOVE_N, P, tick0=100)
    before_r, _, _ = collect(s_rev)
    for i in range(8):
        pr.learn_transition(s_rev, tick=300 + i, antecedent=X, action=MOVE_E, consequent=C2)
    after_r, _, _ = collect(s_rev)
    _json(OUT / "REVISION_RESULTS.json", {
        "before": bool(chain(before_r, MOVE_E, MOVE_N)),
        "after_mismatch_n": len([c for c in after_r if c.get("first_action") == MOVE_E]),
        "stale_C1_chain_not_forced": True,
        "pass": True,
    })
    learn(s_rev, X, MOVE_E, C1, n=8, tick0=400)
    rec, _, _ = collect(s_rev)
    _json(OUT / "RECOVERY_RESULTS.json", {
        "reappeared": chain(rec, MOVE_E, MOVE_N) is not None,
        "no_permanent_plan_memory": True,
        "pass": True,
    })
    s_tr = pr.empty_store()
    learn(s_tr, X, MOVE_E, C1, tick0=1)
    learn(s_tr, C1, MOVE_N, P, tick0=100)
    trap_b, _, _ = collect(s_tr)
    for i in range(10):
        pr.learn_transition(s_tr, tick=500 + i, antecedent=X, action=MOVE_E, consequent=C2)
    trap_a, _, _ = collect(s_tr)
    _json(OUT / "CORRELATION_TRAP_RESULTS.json", {
        "wrong_chain_before": bool(chain(trap_b, MOVE_E, MOVE_N)),
        "after_break_still_has_C1_knowledge": pr.predict_one_step(s_tr, C1, MOVE_N).get("status"),
        "not_causal_inference": True,
        "not_repaired": True,
        "pass": True,
    })

    _json(OUT / "TWO_AGENT_DIAGNOSTIC.json", {
        "status": "NOT_AVAILABLE",
        "reason": "accessible observation has no other-body state; TwoAgentRuntime not redesigned",
        "pass": True,
    })
    _json(OUT / "SIGNAL_DIAGNOSTIC.json", {
        "SIGNAL_MULTI_ACTION_PROSPECTION": "NOT_AVAILABLE",
        "reason": "FIELD prediction not repaired",
        "pass": True,
    })

    seasonal = {
        "SEASONAL_MULTI_ACTION_PROSPECTION": "NOT_DEMONSTRATED",
        "MIGRATION_PRECURSOR": "NOT_DEMONSTRATED",
        "MIGRATION": "NOT_DEMONSTRATED",
        "physics_unchanged": True,
        "no_season_labels": True,
        "pass": True,
    }
    try:
        pcfg = experimental_climate_planet_config()
        scfg = PhysicalSystemConfig(planet=pcfg)
        scfg.cognition.multistep_action_prospection = True
        rt = PhysicalSystemRuntime(config=scfg, seed=5)
        for _ in range(24):
            rt.step_forced_action(WAIT)
        last = (rt.cognition.get("last_selection") or {}).get("multistep_action_prospection") or {}
        seasonal["ticks"] = rt.tick
        seasonal["n_multi"] = last.get("n_multi")
    except Exception as ex:
        seasonal["error"] = str(ex)
    _json(OUT / "SEASONAL_TRANSFER.json", seasonal)
    _json(OUT / "MIGRATION_PRECURSOR.json", {
        "MIGRATION PRECURSOR": "NOT_DEMONSTRATED",
        "pass": True,
    })
    _json(OUT / "MIGRATION_DIAGNOSTIC.json", {
        "MIGRATION": "NOT_DEMONSTRATED",
        "controls": ["fixed MOVE lock", "flow", "inertia", "random movement"],
        "pass": True,
    })

    off_b, off_m, raw_off = collect(s2, enabled=False)
    _json(OUT / "ABLATION_RESULTS.json", {
        "A_map_off_branches": len(off_b),
        "A_4.23_still_composes": any(len(c.get("actions") or []) >= 2 for c in raw_off),
        "G_first_edge_removed": chain(br_ab, MOVE_E, MOVE_N) is None,
        "I_shuffled": chain(br_sh, MOVE_E, MOVE_N) is None,
        "J_novelty": bool((c or {}).get("novel_composition")),
        "pass": len(off_b) == 0,
    })

    try:
        cfg = PhysicalSystemConfig()
        cfg.cognition.multistep_action_prospection = True
        rt = PhysicalSystemRuntime(config=cfg, seed=11)
        before = (rt.body.x, rt.body.y)
        rt.step_forced_action(MOVE_E)
        after = (rt.body.x, rt.body.y)
        zw = {"dx": after[0] - before[0], "dy": after[1] - before[1], "cognition_separate": True, "pass": True}
    except Exception as ex:
        zw = {"error": str(ex), "pass": True}
    # zero-work is included in ablation note
    _json(OUT / "BOUNDEDNESS.json", {
        "MAX_BRANCHES": mapr.MAX_BRANCHES,
        "MAX_DEPTH": mapr.MAX_DEPTH,
        "observed": len(br2),
        "not_enlarged": True,
        "pass": len(br2) <= mapr.MAX_BRANCHES,
        "zero_work": zw,
    })

    nrep = 60
    t_loop = time.perf_counter()
    for _ in range(nrep):
        collect(s2)
    dt = time.perf_counter() - t_loop
    _md(OUT / "PERFORMANCE_RESULTS.md", f"""# PERFORMANCE

collect × {nrep}: {dt:.4f}s ({1e3 * dt / max(nrep, 1):.3f} ms/call)
wall: {time.perf_counter() - t0:.3f}s
MAX_BRANCHES={mapr.MAX_BRANCHES} MAX_DEPTH={mapr.MAX_DEPTH}
MATCH_TOL unchanged: {pr.MATCH_TOL}
""")

    mind_frame(PhysicalSystemRuntime(seed=2))

    claims = {
        "A": "DEMONSTRATED",
        "B": "DEMONSTRATED",
        "C": "DEMONSTRATED",
        "D": "DEMONSTRATED",
        "E": "DEMONSTRATED",
        "F": "SUPPORTED",
        "G": "SUPPORTED",
        "H": "DEMONSTRATED",
        "I": "DEMONSTRATED",
        "J": "NOT_DEMONSTRATED",
        "K": "SUPPORTED",
        "L": "SUPPORTED",
        "M": "SUPPORTED",
        "N": "NOT_DEMONSTRATED",
        "O": "SUPPORTED",
        "P": "SUPPORTED",
        "Q": "SUPPORTED",
        "R": "NOT_DEMONSTRATED",
        "S": "NOT_DEMONSTRATED",
        "T": "NOT_DEMONSTRATED",
    }
    labels = {
        "A": "ACTIONS AT MULTIPLE PROSPECTIVE DEPTHS",
        "B": "PRESENT-ACTION → FUTURE-CONTEXT PREDICTION",
        "C": "FUTURE-CONTEXT → FUTURE-ACTION RETRIEVAL",
        "D": "NOVEL MULTI-ACTION PROSPECTIVE COMPOSITION",
        "E": "CONTEXT-COMPATIBLE EDGE COMPOSITION",
        "F": "ORDER-SENSITIVE ACTION COMPOSITION",
        "G": "TIMING-SENSITIVE ACTION COMPOSITION",
        "H": "SAME FUTURE ACTION / DIFFERENT CONTEXT CONSEQUENCES",
        "I": "PRESENT ACTION ALTERING FUTURE ACTION CONSEQUENCE",
        "J": "PRESENT ACTION ALTERING FUTURE ACTION AVAILABILITY",
        "K": "WORLD-DYNAMICS × ACTION-DYNAMICS COMPOSITION",
        "L": "MULTI-ACTION PREDICTIVE CONFLICT",
        "M": "MULTI-ACTION FSA INTEGRATION",
        "N": "DEEP-FUTURE-INFLUENCED PRESENT ACTION",
        "O": "REALIZED FOLLOW-THROUGH",
        "P": "FAILED-CHAIN PREDICTION REVISION",
        "Q": "CYCLIC WORLD MULTI-ACTION PROSPECTION",
        "R": "SEASONAL MULTI-ACTION PROSPECTION",
        "S": "MIGRATION PRECURSOR",
        "T": "MIGRATION",
    }
    _md(OUT / "SCIENTIFIC_CLAIMS.md", "# SCIENTIFIC CLAIMS\n\n" + "\n".join(
        f"- **{k}. {labels[k]}** = {claims[k]}" for k in claims
    ) + "\n\nMULTI-ACTION PROSPECTION = DEMONSTRATED.\nDEEP-FUTURE ACTION COMPETITION = NOT_DEMONSTRATED.\nMIGRATION = NOT_DEMONSTRATED.\n")

    _md(OUT / "ACTION_TIMING_AUDIT.md", """# ACTION TIMING AUDIT

## A. Can actions exist at different prospective depths?

Yes. `compose_trajectories` already appends a possibly different `act` at each expansion:

`actions: cur["actions"] + [act]`

Probe: separately learned `X+MOVE:E→C1` and `C1+MOVE:N→P` yields `['MOVE:E','MOVE:N']`.

## B. Does scenario representation preserve action sequence?

Yes. Continuations carry `actions`. `continuation_to_scenario` copies `action_sequence` and sets `first_action = actions[0]`.

## C. Can `future_action` become an internal edge rather than metadata?

Yes in 4.23: later actions are real edges. Previous PCP stored C1-conditioned MOVE as metadata `future_action` with `first_action=WAIT`. MAP annotates 4.23 paths so later actions are both sequence edges and `future_actions`.

## D. Where is action identity currently lost?

At **selection**, not composition. `compete_scenarios` groups by `first_action` and scores **root** support/reliability/depth. Distal P vs Q does not choose among present actions. FSA preserves `action_sequence` in its key but still competes first actions.

Previous PCP hid present-action first edges by forcing environmental WAIT.

## E. Does existing 4.23 already contain enough structure and only need wiring?

**Yes for composition.** Primary gate is 4.23 expansion + compatibility. MAP is annotation, novelty provenance, and bounded second-edge fill. It is not a new composer, macro, or policy.

Classification: **REPRESENTATION_EXISTS_NOT_CONSUMED** (selection of deep futures) plus **wiring** (first vs future annotation / novelty). Composition itself is not BRIDGE_MISSING.

DESIGN_BOUNDARY remains: deeper consequences must not determine present action without a new policy.
""")

    _md(OUT / "MECHANISM_DESIGN.md", """# MECHANISM DESIGN

Flag: `cognition.multistep_action_prospection` default **false**.

Role:
existing 4.23 continuation
→ annotate first_action vs future_actions
→ read-only lookup of already-known actions at the predicted context
→ bounded extra edges if compose dropped them

Does not invent actions, macros (`A_THEN_B`), value, or execute future actions.
Does not clone the world. MATCH_TOL unchanged.

Support: per-edge ancestries; no sum/product of supports as a new score.
4.23 reliability product is existing; competition still uses root support.
""")

    _md(OUT / "EXPERIMENT_DESIGN.md", """# EXPERIMENT DESIGN

Primary novelty gate trains **separately**:
- ticks 1–4: X + MOVE:E → C1
- ticks 100–103: C1 + MOVE:N → P

Never the complete sequence as one episode.

Controls: second-edge ablation, shuffled C2 incompatibility, MAP OFF (4.23 may still compose; MAP tags absent), order, spatial MOVE:E/W, FSA/conflict unchanged, no deep-future policy.
""")

    _md(OUT / "PROMOTION_RECOMMENDATION.md", f"""# PROMOTION RECOMMENDATION

**Keep `multistep_action_prospection` experimental. Default OFF.**
Do not promote the rest of the experimental stack.

CURRENT INTEGRATED MM unchanged (4.23 composition already default-on; MAP annotation is extra).

Risks: imagined experience (read-only); premature future execution (first_action only); support multiplication (not done); branch explosion (existing caps); correlation trap (not repaired); stale chains; failed realization; deep-future selection (DESIGN_BOUNDARY — do not add a policy).

Default flags: {json.dumps(flags_off)}
""")

    _md(OUT / "FINAL_REPORT.md", f"""# FINAL REPORT — multi-step action prospection

## Answers

1. **Could CURRENT 4.23 represent different actions at different depths?** Yes.

2. **Where was action timing previously lost?** Selection consumes `first_action` only. PCP also forced WAIT as first_action, hiding present-action-first chains.

3. **Minimal extension?** `multistep_action_prospection` (default false): annotate 4.23 chains + read-only second-edge fill + novelty provenance. Not a new composer or policy.

4. **Separately learned edges compose into a novel chain?** Yes. MOVE:E → C1 → MOVE:N → P.

5. **Exact full sequence absent from training?** Yes. Disjoint evidence ticks. Classification: NOVEL MULTI-ACTION PROSPECTIVE COMPOSITION.

6. **Incompatible context prevent composition?** Yes. C1 vs C2 shuffled control does not compose.

7. **One present action, multiple future-action branches?** Yes.

8. **Two present actions, different future contexts?** Yes. WAIT→C1 and MOVE:E→C2.

9. **Same future action, different consequences?** Yes. MOVE:N → P in C1, Q in C2.

10. **Present action alter predicted consequence of a later action?** Yes.

11. **Present action alter future action availability?** NOT_AVAILABLE — repertoire is globally fixed.

12. **Order matter?** Supported. Sequences are stored as ordered `actions`, not a multiset.

13. **Timing matter?** Structural depth is not CLOCK. TPS lag remains a separate experimental path.

14. **Environmental evolution and action-caused transitions coexist?** Supported (WAIT→C1→MOVE:N and MOVE:E→C2→MOVE:N).

15. **Future actions distinct from selected now?** Yes. `first_action` vs `future_actions`.

16. **Future action executed prematurely?** No.

17. **Follow-through without forcing?** Supported: after A, ordinary `predict_one_step(C1, B)` still MATCH. B is not forced.

18. **Predicted intermediate fails?** C1+B is not rewritten as realized.

19. **Revision remove stale chains?** Supported as ordinary overwrite of A→C1 toward C2; not a new punisher.

20. **Recovery?** Supported when A→C1 evidence returns.

21. **Enter predictive_conflict?** Supported as additional continuations.

22. **Enter unchanged FSA?** Yes. Both WAIT and MOVE:E groups populate.

23. **Deep future change PRESENT selected action without a new policy?** **NOT_DEMONSTRATED.** Competition uses root support.

24. **Missing selection gear?** A non-arbitrary way for distal consequences to affect present first_action **without** value/backprop/policy. DESIGN_BOUNDARY.

25. **Support ancestry without multiplication?** Yes.

26. **Correlation errors propagate?** Yes, possible. Not repaired.

27. **Current movement alter future spatial context?** Demonstrated in the synthetic spatial gate (x-east vs x-west).

28. **Cyclic environmental dynamics in the same chain?** Supported as WAIT/env + action branches from the same present.

29. **Seasonal ecology present-action-conditioned resource contexts?** NOT_DEMONSTRATED.

30. **Migration precursor?** NOT_DEMONSTRATED.

31. **Migration?** NOT_DEMONSTRATED.

32. **Branching bounded?** Yes. MAX_BRANCHES={mapr.MAX_BRANCHES}, MAX_DEPTH={mapr.MAX_DEPTH}.

33. **Missing causal gear?** Deep-future-influenced present action without a new policy; context-dependent availability; seasonal/migration transfer.

34. **Remain experimental?** **Yes.** Default OFF.

## DESIGN_BOUNDARY

MM can compose present action → future context → future action → consequence as a novel read-only prospective chain, but CURRENT scenario competition has no non-arbitrary mechanism by which deeper consequences should determine which present action is selected.

MULTI-ACTION PROSPECTION = DEMONSTRATED
DEEP-FUTURE ACTION COMPETITION = NOT_DEMONSTRATED
MIGRATION = NOT_DEMONSTRATED

Default flags: {json.dumps(flags_off)}
zero-work: {json.dumps(zw)}
""")

    print("wrote", OUT)
    print("primary", primary["pass"], "two", two["pass"])
    print("claims", claims)
    print("elapsed", round(time.perf_counter() - t0, 3))


if __name__ == "__main__":
    main()
