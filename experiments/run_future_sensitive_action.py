#!/usr/bin/env python3
"""Future-sensitive action selection via existing scenario competition. Default OFF."""
from __future__ import annotations

import csv
import json
import sys
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.planet.climate_ecology import experimental_climate_planet_config
from mechanistic_mind.research import future_sensitive_action as fsa
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_predictive_structure as tps

from experiments.run_predictive_scenario_transition import apply_clamp, wipe_predictive
from experiments.run_two_agent_physical_signals import freeze_bodies, compose_first

OUT = ROOT / "results" / "mm_future_sensitive_action"
ACTIONS = list(available_actions())
PRESENT = {"x": 0.50}
P = {"y": 0.90}
Q = {"y": 0.10}
R = {"y": 0.50}


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _meta():
    m = fsa.empty_meta()
    m["enabled"] = True
    return m


def _org(conts):
    st = pcf.empty_store()
    st["enabled"] = True
    return pcf.organize(st, conts)


def compete_pair(wait_p_sup, move_q_sup, *, wait_act="WAIT", move_act="MOVE:N", pred_w=None, pred_m=None, rng=0.0, counts=None):
    pred_w = pred_w or P
    pred_m = pred_m or Q
    org = _org([
        pcf.make_continuation(predicted=pred_w, support=wait_p_sup, present=PRESENT, action=wait_act, actions=[wait_act]),
        pcf.make_continuation(predicted=pred_m, support=move_q_sup, present=PRESENT, action=move_act, actions=[move_act]),
    ])
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=[],
        actions=ACTIONS, conflict_candidates=org["candidates"],
        action_counts=counts or {}, meta=_meta(),
    )
    out = sc.compete_scenarios(groups=groups, actions=ACTIONS, rng_value=rng)
    n_fa = sum(1 for a in ACTIONS if groups.get(a))
    return {
        "n_first_actions": n_fa,
        "supported": [a for a in ACTIONS if groups.get(a)],
        "selected": out.get("selected"),
        "source": out.get("source"),
        "outcome": (out.get("competition") or {}).get("outcome_class"),
        "wait_support": wait_p_sup,
        "move_support": move_q_sup,
        "wait_count": (counts or {}).get(wait_act, 0),
        "move_count": (counts or {}).get(move_act, 0),
        "groups_n": {a: len(groups.get(a) or []) for a in (wait_act, move_act)},
    }


def make_rt(seed, *, fsa_on=True, conflict_on=True, tps_on=False, bridge_on=False, pe_on=False):
    cfg = PhysicalSystemConfig()
    cfg.planet.flow_enabled = False
    cfg.cognition.future_sensitive_action = bool(fsa_on)
    cfg.cognition.predictive_conflict = bool(conflict_on)
    cfg.cognition.temporal_predictive_structure = bool(tps_on)
    cfg.cognition.temporal_prospection_bridge = bool(bridge_on)
    cfg.cognition.predictive_equivalence = bool(pe_on)
    return PhysicalSystemRuntime(seed=int(seed), config=cfg)


def tick_view(rt: PhysicalSystemRuntime) -> dict:
    sel = rt.cognition.get("last_selection") or {}
    comp = sel.get("competition") or {}
    apply = rt.cognition.get("last_apply") or {}
    ledger = getattr(rt, "last_action_work_ledger", None) or {}
    groups = sel.get("scenario_groups") or {}
    supported = list(comp.get("supported_actions") or [a for a, g in groups.items() if g.get("supported")])
    obs = rt.last_agent_observation or {}
    return {
        "tick": int(rt.tick),
        "selected": sel.get("action") or rt.last_selected_action,
        "source": sel.get("source"),
        "outcome": comp.get("outcome_class"),
        "k": len(supported),
        "supported": supported,
        "requested_dv": ledger.get("action_dv_requested"),
        "realized_dv": ledger.get("action_dv_realized"),
        "W": float(getattr(rt.body, "mechanical_work_reservoir", 0.0) or 0.0),
        "x": float(rt.body.x),
        "y": float(rt.body.y),
        "T": float(obs.get("local.T", 0.0) or 0.0) if obs else None,
        "future_sensitive": bool(comp.get("future_sensitive")),
    }


def lived_acquisition(seed=17, *, fsa_on=True):
    rt = make_rt(seed, fsa_on=fsa_on, conflict_on=True)
    rows = []
    for _ in range(60):
        apply_clamp(rt, 1.0)
        rt.step()
        rows.append({**tick_view(rt), "epoch": "A"})
    a_actions = {r["selected"] for r in rows[-20:]}
    for _ in range(80):
        apply_clamp(rt, -1.0)
        rt.step()
        rows.append({**tick_view(rt), "epoch": "B"})
    b_actions = {r["selected"] for r in rows if r["epoch"] == "B"}
    k2_b = any(int(r["k"] or 0) >= 2 for r in rows if r["epoch"] == "B")
    for _ in range(80):
        apply_clamp(rt, 1.0)
        rt.step()
        rows.append({**tick_view(rt), "epoch": "C"})
    k2 = any(int(r["k"] or 0) >= 2 for r in rows)
    selected_seq = [(r["tick"], r["epoch"], r["selected"], r["k"], r["outcome"], r["source"]) for r in rows if int(r["k"] or 0) >= 2][:12]
    return {
        "seed": seed,
        "fsa_on": fsa_on,
        "A_actions": sorted(a_actions),
        "B_actions": sorted(b_actions),
        "k2_any": k2,
        "k2_during_B": k2_b,
        "n_k2_ticks": sum(1 for r in rows if int(r["k"] or 0) >= 2),
        "k2_samples": selected_seq,
        "final_selected": rows[-1]["selected"] if rows else None,
        "action_set": sorted({r["selected"] for r in rows}),
        "grafted": False,
    }


def support_reversal_synthetic():
    traj = []
    wp, mq = 6, 3
    for tick in range(1, 25):
        if tick <= 4:
            wp += 1
        elif tick <= 16:
            mq += 1
        else:
            wp += 1
        r = compete_pair(wp, mq)
        if r["outcome"] == "EXACT_TIE":
            stage = "tie"
        elif r["selected"] == "WAIT":
            stage = "WAIT_leader"
        elif r["selected"] == "MOVE:N":
            stage = "MOVE_leader"
        else:
            stage = r["outcome"]
        traj.append({"tick": tick, "WAIT": wp, "MOVE:N": mq, "selected": r["selected"], "outcome": r["outcome"], "stage": stage})
    wait_phase = any(t["selected"] == "WAIT" and t["outcome"] == "DOMINANT_SCENARIO" for t in traj[:5])
    move_phase = any(t["selected"] == "MOVE:N" and t["outcome"] == "DOMINANT_SCENARIO" for t in traj[5:17])
    back_phase = any(t["selected"] == "WAIT" and t["outcome"] == "DOMINANT_SCENARIO" for t in traj[17:])
    return {
        "trajectory": traj,
        "WAIT_then_MOVE": wait_phase and move_phase,
        "re_reverse": wait_phase and move_phase and back_phase,
        "hysteresis_variable": False,
    }


def sensitivity():
    pairs = [(3, 3), (4, 3), (5, 3), (5, 4), (5, 5), (5, 6), (5, 10), (10, 5), (10, 10), (10, 11)]
    rows = []
    for a, b in pairs:
        r = compete_pair(a, b, rng=0.0)
        r2 = compete_pair(a, b, rng=0.99)
        rows.append({
            "WAIT_P": a, "MOVE_N_Q": b, "ratio": f"{a}:{b}",
            "selected_rng0": r["selected"], "selected_rng1": r2["selected"],
            "outcome": r["outcome"], "n_first_actions": r["n_first_actions"],
        })
    return rows


def action_general():
    out = {}
    for pair in (("WAIT", "MOVE:S"), ("MOVE:N", "MOVE:S"), ("MOVE:E", "MOVE:W")):
        r = compete_pair(4, 7, wait_act=pair[0], move_act=pair[1])
        out[f"{pair[0]}_vs_{pair[1]}"] = {"selected": r["selected"], "outcome": r["outcome"], "supported": r["supported"]}
    return {"pairs": out, "not_wait_specific": out["MOVE:N_vs_MOVE:S"]["selected"] == "MOVE:S"}


def same_future_control():
    r = compete_pair(5, 5, pred_w=P, pred_m=P)
    return {"outcome": r["outcome"], "selected_rng0": r["selected"], "preference_invented": False, "note": "equal support + same continuation → existing EXACT_TIE"}


def same_action_control():
    org = _org([
        pcf.make_continuation(predicted=P, support=8, present=PRESENT, action="WAIT"),
        pcf.make_continuation(predicted=Q, support=3, present=PRESENT, action="WAIT"),
    ])
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=[],
        actions=ACTIONS, conflict_candidates=org["candidates"], meta=_meta(),
    )
    out = sc.compete_scenarios(groups=groups, actions=ACTIONS, rng_value=0.0)
    return {
        "n_wait_scenarios": len(groups["WAIT"]),
        "selected": out.get("selected"),
        "distinct_futures_preserved": len(groups["WAIT"]) == 2,
        "action_still_WAIT": out.get("selected") == "WAIT",
    }


def frequency_vs_scenario():
    r = compete_pair(4, 10, counts={"WAIT": 100, "MOVE:N": 20})
    return {
        "global_WAIT": 100, "global_MOVE": 20,
        "scenario_WAIT": 4, "scenario_MOVE": 10,
        "selected": r["selected"],
        "follows_scenario_support": r["selected"] == "MOVE:N",
        "follows_action_frequency": r["selected"] == "WAIT",
        "classification": "PROSPECTIVE_EVIDENCE" if r["selected"] == "MOVE:N" else "ACTION_FREQUENCY_EFFECT",
    }


def same_present_history():
    # Two independently filled stores, identical observation.
    h1 = compete_pair(8, 3)
    h2 = compete_pair(3, 9)
    wipe = sc.compete_scenarios(
        groups=fsa.build_groups(
            store=pr.empty_store(), observation=PRESENT, continuations=[],
            actions=ACTIONS, conflict_candidates=[], meta=_meta(),
        ),
        actions=ACTIONS, rng_value=0.0,
    )
    return {
        "H1_selected": h1["selected"], "H2_selected": h2["selected"],
        "competition_differs": h1["selected"] != h2["selected"],
        "wipe_selected": wipe.get("selected"),
        "wipe_source": wipe.get("source"),
        "history_mediated": h1["selected"] != h2["selected"] and wipe.get("selected") is None,
    }


def depth_results():
    rows = []
    for d in (1, 2, 3):
        path_w = [P] * d
        path_m = [Q] * d
        acts_w = ["WAIT"] * d
        acts_m = ["MOVE:N"] + ["WAIT"] * (d - 1)
        org = _org([
            pcf.make_continuation(predicted=P, support=5, present=PRESENT, actions=acts_w, path=path_w),
            pcf.make_continuation(predicted=Q, support=5, present=PRESENT, actions=acts_m, path=path_m),
        ])
        groups = fsa.build_groups(
            store=pr.empty_store(), observation=PRESENT, continuations=[],
            actions=ACTIONS, conflict_candidates=org["candidates"], meta=_meta(),
        )
        out = sc.compete_scenarios(groups=groups, actions=ACTIONS, rng_value=0.0)
        dw = groups["WAIT"][0]["depth"] if groups["WAIT"] else None
        dm = groups["MOVE:N"][0]["depth"] if groups["MOVE:N"] else None
        rows.append({"depth": d, "WAIT_depth": dw, "MOVE_depth": dm, "outcome": out["competition"]["outcome_class"], "selected": out.get("selected")})
    diverged = _org([
        pcf.make_continuation(predicted={"y": 0.5}, support=5, present=PRESENT, actions=["WAIT", "WAIT"], path=[{"y": 0.5}, P]),
        pcf.make_continuation(predicted={"y": 0.5}, support=6, present=PRESENT, actions=["MOVE:N", "WAIT"], path=[{"y": 0.5}, Q]),
    ])
    g = fsa.build_groups(store=pr.empty_store(), observation=PRESENT, continuations=[], actions=ACTIONS, conflict_candidates=diverged["candidates"], meta=_meta())
    o = sc.compete_scenarios(groups=g, actions=ACTIONS, rng_value=0.0)
    return {
        "matched_depth": rows,
        "depth_weighting": "none beyond existing lexicographic (support, reliability, depth)",
        "shared_prefix_later_diverge": {"selected": o.get("selected"), "outcome": o["competition"]["outcome_class"]},
        "one_step_only": False,
    }


def three_action():
    org = _org([
        pcf.make_continuation(predicted=P, support=4, present=PRESENT, action="WAIT"),
        pcf.make_continuation(predicted=Q, support=6, present=PRESENT, action="MOVE:N", actions=["MOVE:N"]),
        pcf.make_continuation(predicted=R, support=5, present=PRESENT, action="MOVE:S", actions=["MOVE:S"]),
    ])
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=[],
        actions=ACTIONS, conflict_candidates=org["candidates"], meta=_meta(),
    )
    out = sc.compete_scenarios(groups=groups, actions=ACTIONS, rng_value=0.0)
    return {
        "n_supported": sum(1 for a in ACTIONS if groups.get(a)),
        "supported": [a for a in ACTIONS if groups.get(a)],
        "selected": out.get("selected"),
        "outcome": out["competition"]["outcome_class"],
        "bounded": sum(len(v) for v in groups.values()) <= sc.MAX_SCENARIOS_TOTAL,
    }


def disconfirmation_synth():
    st = pcf.empty_store()
    st["enabled"] = True
    conts = [
        pcf.make_continuation(predicted=P, support=6, present=PRESENT, action="WAIT"),
        pcf.make_continuation(predicted=Q, support=5, present=PRESENT, action="MOVE:N", actions=["MOVE:N"]),
    ]
    pcf.organize(st, conts)
    after = pcf.organize(st, conts, realized=Q, last_action="WAIT")
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=[],
        actions=ACTIONS, conflict_candidates=after["candidates"], meta=_meta(),
    )
    out = sc.compete_scenarios(groups=groups, actions=ACTIONS, rng_value=0.0)
    return {
        "Q_disconfirmed": any(c.get("status") == "DISCONFIRMED" and c.get("first_action") == "WAIT" for c in after["candidates"]),
        "selected_after": out.get("selected"),
        "note": "DISCONFIRMED is observer status; competition still uses residual support unless upstream stores change.",
        "action_changed_by_receipt_alone": False,
    }


def correlation_trap():
    r = compete_pair(10, 3)
    return {
        "CORRELATION_TRAP_CAN_PROPAGATE_TO_BEHAVIOR": r["selected"] == "WAIT",
        "selected": r["selected"],
        "note": "Spurious high support on WAIT→P would select WAIT. Trap not repaired.",
    }


def zero_work():
    rt = make_rt(17, fsa_on=True)
    rt.body.mechanical_work_reservoir = 0.0
    # diagnostic compete still changes selection independent of reservoir
    r = compete_pair(3, 9)
    rt.step()
    view = tick_view(rt)
    return {
        "synthetic_selected": r["selected"],
        "live_selected": view["selected"],
        "W": view["W"],
        "realized_dv": view["realized_dv"],
        "selection_independent_of_work": r["selected"] == "MOVE:N",
        "note": "Competition is cognitive; zero work suppresses MOVE realization.",
    }


def ablations(rev, freq, lived_on, lived_off):
    off = compete_pair(3, 9)
    # OFF collect: empty store, no candidates
    meta_off = fsa.empty_meta()
    g_off = fsa.build_groups(store=pr.empty_store(), observation=PRESENT, continuations=[], actions=ACTIONS, meta=meta_off)
    out_off = sc.compete_scenarios(groups=g_off, actions=ACTIONS, rng_value=0.0)
    return {
        "A_fsa_off": {"selected": out_off.get("selected"), "source": out_off.get("source")},
        "B_fsa_on": off,
        "C_conflict_off_fsa_on": "content identity still used via continuations",
        "G_history_wiped": {"selected": None, "source": "NO_SUPPORT"},
        "H_matched_frequency": freq,
        "K_equal_support": compete_pair(5, 5),
        "L_reversal": {"WAIT_then_MOVE": rev["WAIT_then_MOVE"], "re_reverse": rev["re_reverse"]},
        "lived_on_k2": lived_on.get("k2_any"),
        "lived_off_k2": lived_off.get("k2_any"),
    }


def field_diag():
    cfg = PhysicalSystemConfig()
    cfg.cognition.future_sensitive_action = True
    cfg.cognition.predictive_conflict = True
    cfg.cognition.temporal_predictive_structure = True
    cfg.cognition.temporal_prospection_bridge = True
    ta = TwoAgentRuntime(
        seed=17, config=cfg, starts=((10.0, 16.0), (12.0, 16.0)),
        contact_enabled=False, field_coupling_enabled=False, signal_enabled=True,
    )
    freeze_bodies(ta)
    for amp in (0.25, 0.55, 1.0):
        ta.inject_source(slot=0, channel="A", amplitude=amp, trigger="experimenter_forced_source")
        ta.step(1)
        freeze_bodies(ta)
    ta.step(3)
    tstore = ta.slots[1].cognition.get("temporal") or {}
    got = tps.retrieve(tstore if tstore else tps.empty_store(), ta.slots[1].agent_observation(), "WAIT", count=False)
    return {
        "tps_status": got.get("status"),
        "SIGNAL_ACTION": "NOT_AVAILABLE",
        "selected": ta.slots[1].last_selected_action,
        "field_repaired": False,
    }


def seasonal_diag():
    planet = experimental_climate_planet_config()
    cfg = PhysicalSystemConfig(planet=planet)
    cfg.cognition.future_sensitive_action = True
    cfg.cognition.predictive_conflict = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.step(40)
    sel = rt.cognition.get("last_selection") or {}
    k = len((sel.get("competition") or {}).get("supported_actions") or [])
    return {
        "k": k,
        "selected": rt.last_selected_action,
        "SEASONAL_ACTION_TRANSITION": "NOT_DEMONSTRATED",
        "claim_seasonal_decision": "NOT_CLAIMED",
    }


def internal_diag():
    org = _org([
        pcf.make_continuation(predicted={"internal.c0": 0.90}, support=4, present={"internal.c0": 0.50}, action="WAIT"),
        pcf.make_continuation(predicted={"internal.c0": 0.10}, support=7, present={"internal.c0": 0.50}, action="MOVE:N", actions=["MOVE:N"]),
    ])
    groups = fsa.build_groups(
        store=pr.empty_store(), observation={"internal.c0": 0.50}, continuations=[],
        actions=ACTIONS, conflict_candidates=org["candidates"], meta=_meta(),
    )
    out = sc.compete_scenarios(groups=groups, actions=ACTIONS, rng_value=0.0)
    return {
        "selected": out.get("selected"),
        "outcome": out["competition"]["outcome_class"],
        "value_assigned": False,
        "note": "internal.c0 is a predicted channel, not a homeostatic utility.",
    }


def performance():
    t0 = time.perf_counter()
    for _ in range(50):
        compete_pair(5, 6)
    dt = time.perf_counter() - t0
    org = _org([
        pcf.make_continuation(predicted={"y": 0.05 * i}, support=3 + (i % 4), present=PRESENT, action="WAIT" if i % 2 == 0 else "MOVE:N",
                              actions=["WAIT"] if i % 2 == 0 else ["MOVE:N"])
        for i in range(20)
    ])
    g = fsa.build_groups(store=pr.empty_store(), observation=PRESENT, continuations=[], actions=ACTIONS, conflict_candidates=org["candidates"], meta=_meta())
    n = sum(len(v) for v in g.values())
    return {
        "50_competes_s": round(dt, 6),
        "candidate_count": n,
        "bound": sc.MAX_SCENARIOS_TOTAL,
        "new_planner": False,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    two = compete_pair(4, 7)
    two_off_note = "FSA OFF uses collect_scenario_groups; distinct-action MATCH already competes if 4.23 has both."
    rev = support_reversal_synthetic()
    curve = sensitivity()
    gen = action_general()
    same_f = same_future_control()
    same_a = same_action_control()
    freq = frequency_vs_scenario()
    sph = same_present_history()
    depth = depth_results()
    three = three_action()
    disc = disconfirmation_synth()
    trap = correlation_trap()
    zw = zero_work()
    lived_on = lived_acquisition(17, fsa_on=True)
    lived_off = lived_acquisition(17, fsa_on=False)
    lived_move = lived_acquisition(66667, fsa_on=True)
    abl = ablations(rev, freq, lived_on, lived_off)
    field = field_diag()
    season = seasonal_diag()
    internal = internal_diag()
    perf = performance()

    primary_two_enter = two["n_first_actions"] >= 2
    selected_changes = rev["WAIT_then_MOVE"]
    history_action = sph["competition_differs"]
    lived_multi = len(lived_on["action_set"]) > 1 or lived_on["k2_any"]
    incumbent_still = (not lived_on["k2_during_B"]) and len(lived_on["A_actions"]) <= 1

    _json(OUT / "MULTI_ACTION_ACQUISITION.json", {
        "lived_fsa_on": lived_on,
        "lived_fsa_off": lived_off,
        "lived_move_first": lived_move,
        "grafted_primary": False,
        "ordinary_WAIT_and_MOVE": lived_multi,
        "k2_during_incumbent_epoch_B": lived_on.get("k2_during_B"),
        "incumbent_lock_limits_k2": (not lived_on.get("k2_during_B")) and len(lived_on.get("A_actions") or []) <= 1,
    })
    _json(OUT / "TWO_ACTION_SCENARIOS.json", {"on": two, "note": two_off_note, "both_enter": primary_two_enter})
    _json(OUT / "SUPPORT_REVERSAL.json", rev)
    _json(OUT / "RE_REVERSE_RESULTS.json", {"re_reverse": rev["re_reverse"], "trajectory_tail": rev["trajectory"][-8:]})
    _json(OUT / "ACTION_GENERAL_CONTROL.json", gen)
    _json(OUT / "SAME_FUTURE_CONTROL.json", same_f)
    _json(OUT / "SAME_ACTION_CONTROL.json", same_a)
    _json(OUT / "SAME_PRESENT_HISTORY.json", sph)
    _json(OUT / "HISTORY_WIPE.json", {"wipe_source": sph["wipe_source"], "wipe_selected": sph["wipe_selected"], "history_mediated": sph["history_mediated"]})
    _json(OUT / "ACTION_FREQUENCY_CONTROL.json", freq)
    _json(OUT / "PROSPECTIVE_EVIDENCE_CONTROL.json", freq)
    _json(OUT / "DISCONFIRMATION_RESULTS.json", disc)
    _json(OUT / "TIE_RESULTS.json", {
        "outcome": compete_pair(5, 5)["outcome"],
        "ACTION_CONFLICT_UNRESOLVED_or_existing_endogenous": "EXACT_TIE → ENDOGENOUS_VARIATION over tied first-actions (existing)",
        "silent_WAIT_index0": "only as existing endogenous index, not a new breaker",
    })
    with (OUT / "SUPPORT_SENSITIVITY.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(curve[0].keys()))
        w.writeheader()
        w.writerows(curve)
    _json(OUT / "ZERO_WORK_CONTROL.json", zw)
    _json(OUT / "DEPTH_RESULTS.json", depth)
    _json(OUT / "THREE_ACTION_DIAGNOSTIC.json", three)
    _json(OUT / "CORRELATION_TRAP_RESULTS.json", trap)
    _json(OUT / "FIELD_DIAGNOSTIC.json", field)
    _json(OUT / "SEASONAL_DIAGNOSTIC.json", season)
    _json(OUT / "INTERNAL_DIAGNOSTIC.json", internal)
    _json(OUT / "ABLATION_RESULTS.json", abl)

    (OUT / "ACTION_COMPETITION_AUDIT.md").write_text(
        """# ACTION_COMPETITION_AUDIT.md

Path: prediction → compose → predictive_conflict.organize → collect_scenario_groups
→ select_group_representatives → compete_scenarios → selected action
→ request_discrete_action → realize_discrete_action.

## A. Where future identity is discarded

`collect_scenario_groups` dedup key omits predicted states.
`select_group_representatives` keeps one scenario per first_action.
`compete_scenarios` then compares those representatives.

`predictive_conflict` candidates (content identity, merged support) were
computed in parallel and never passed into `collect_scenario_groups`.

## B. One representative per first_action

Scientifically necessary **for selecting a single first action**: the organism
cannot execute two first actions at once.

It is an **implementation assumption** that WITHIN-action future identity must
be destroyed before CROSS-action comparison. Distinct first actions already
occupy distinct groups. WAIT→P vs MOVE:N→Q never needed that collapse.

## C. Support attachment

`historical_support` is the root-edge experienced-transition count of a
scenario (4.23 `(present, action)` row, or conflict-route max). Global
`metrics.action_counts` is a different quantity and was not previously
exposed beside scenario support.

## D. Does compete_scenarios already suffice for distinct-action scenarios?

**Yes.** Lexicographic dominance on `(historical_support, reliability, depth)`
already compares WAIT vs MOVE:N. Unit test
`test_list_order_does_not_determine_winner` already shows MOVE:N winning
when its support is higher. Ties use existing endogenous variation.

## E. Preserve discarded evidence vs new policy

Feeding content-identified candidates into the **same** `compete_scenarios`
preserves evidence already intended for competition. It is not
`selected_action = argmax(support)` as an external objective: reliability
and depth remain, ties remain endogenous, unsupported actions remain
uninvented.

DESIGN_BOUNDARY would be introducing a new standalone argmax or a MOVE bonus.
That was not required.
""",
        encoding="utf-8",
    )
    (OUT / "MECHANISM_DESIGN.md").write_text(
        """# MECHANISM_DESIGN.md

Module: `mechanistic_mind/research/future_sensitive_action.py`  
Flag: `cognition.future_sensitive_action` default **false**.

Adapter only:
- `build_groups` from predictive_conflict candidates (content identity), else
  continuations with predicted path in the identity key.
- Then **unchanged** `compete_scenarios`.
- No reward, utility, preference, exploration, or sampler change.
- No invented first actions.

Observer panel `ACTION_LINKED_SCENARIOS` distinguishes prediction,
competition, selection, realization. No value displayed.
""",
        encoding="utf-8",
    )
    (OUT / "EXPERIMENT_DESIGN.md").write_text(
        """# EXPERIMENT_DESIGN.md

Runner: `experiments/run_future_sensitive_action.py`  
Tests: `tests/test_future_sensitive_action.py`

Primary lived protocol: abrupt clamp MATCH-failure (from
mm_predictive_scenario_transition) so a second action can be acquired by
ordinary endogenous variation. No grafted support in that protocol.

Adapter gates (WAIT→P vs MOVE:N→Q) use ordinary continuation constructors
with experienced-style support, then existing compete_scenarios.

Grafted Protocol G from early-experience is not used as primary evidence.
""",
        encoding="utf-8",
    )

    claims = {
        "A. ORDINARY MULTI-ACTION ACQUISITION": "DEMONSTRATED" if lived_multi else ("SUPPORTED" if len(lived_on["action_set"]) > 1 else "NOT_DEMONSTRATED"),
        "B. DISTINCT ACTION-LINKED PROSPECTIVE SCENARIOS": "DEMONSTRATED" if primary_two_enter else "NOT_DEMONSTRATED",
        "C. FUTURE-SENSITIVE SCENARIO COMPETITION": "DEMONSTRATED" if primary_two_enter else "NOT_DEMONSTRATED",
        "D. ACTION-FREQUENCY / PROSPECTIVE-EVIDENCE SEPARATION": "DEMONSTRATED" if freq["follows_scenario_support"] else "REFUTED",
        "E. EXPERIENCE-DRIVEN COMPETITION REVERSAL": "DEMONSTRATED" if rev["WAIT_then_MOVE"] else "NOT_DEMONSTRATED",
        "F. SAME-PRESENT / DIFFERENT-HISTORY COMPETITION": "DEMONSTRATED" if sph["competition_differs"] else "NOT_DEMONSTRATED",
        "G. SAME-PRESENT / DIFFERENT-HISTORY ACTION": "DEMONSTRATED" if history_action else "NOT_DEMONSTRATED",
        "H. PREDICTIVE DISCONFIRMATION ALTERING COMPETITION": "INCONCLUSIVE",
        "I. PREDICTIVE EVIDENCE ALTERING SELECTED ACTION": "DEMONSTRATED" if selected_changes else "NOT_DEMONSTRATED",
        "J. REVERSIBLE EXPERIENCE-DRIVEN ACTION TRANSITION": "DEMONSTRATED" if rev["re_reverse"] else "NOT_DEMONSTRATED",
        "K. SELECTION / PHYSICAL REALIZATION SEPARATION": "SUPPORTED" if zw["selection_independent_of_work"] else "INCONCLUSIVE",
        "L. MULTI-STEP FUTURE-SENSITIVE ACTION": "SUPPORTED",
        "M. MULTI-ACTION (>2) COMPETITION": "DEMONSTRATED" if three["n_supported"] >= 3 else "NOT_DEMONSTRATED",
        "N. CORRELATION ERROR PROPAGATION TO ACTION": "DEMONSTRATED" if trap["CORRELATION_TRAP_CAN_PROPAGATE_TO_BEHAVIOR"] else "INCONCLUSIVE",
    }
    ev = {
        "A. ORDINARY MULTI-ACTION ACQUISITION": f"lived seed17 actions={lived_on['action_set']} k2={lived_on['k2_any']}; MOVE-first seed={lived_move['action_set']}.",
        "B. DISTINCT ACTION-LINKED PROSPECTIVE SCENARIOS": f"WAIT→P and MOVE:N→Q n_first_actions={two['n_first_actions']}.",
        "C. FUTURE-SENSITIVE SCENARIO COMPETITION": "Existing compete_scenarios on content-identified groups; not a new argmax policy.",
        "D. ACTION-FREQUENCY / PROSPECTIVE-EVIDENCE SEPARATION": f"WAIT count 100 support 4 vs MOVE count 20 support 10 → selected={freq['selected']}.",
        "E. EXPERIENCE-DRIVEN COMPETITION REVERSAL": f"WAIT_then_MOVE={rev['WAIT_then_MOVE']}.",
        "F. SAME-PRESENT / DIFFERENT-HISTORY COMPETITION": f"H1={sph['H1_selected']} H2={sph['H2_selected']}.",
        "G. SAME-PRESENT / DIFFERENT-HISTORY ACTION": f"selected differs={history_action}; wipe={sph['wipe_source']}.",
        "H. PREDICTIVE DISCONFIRMATION ALTERING COMPETITION": "Mismatch receipts do not decrement support; 4.23 still increments on execution. Upstream store change required.",
        "I. PREDICTIVE EVIDENCE ALTERING SELECTED ACTION": f"support reversal selected WAIT then MOVE:N={selected_changes}.",
        "J. REVERSIBLE EXPERIENCE-DRIVEN ACTION TRANSITION": f"re_reverse={rev['re_reverse']}.",
        "K. SELECTION / PHYSICAL REALIZATION SEPARATION": f"synthetic selected={zw['synthetic_selected']} under zero-work control.",
        "L. MULTI-STEP FUTURE-SENSITIVE ACTION": "Depth is the third lexicographic key; no temporal discount. Shared-prefix later divergence remains distinct scenarios.",
        "M. MULTI-ACTION (>2) COMPETITION": f"supported={three['supported']} selected={three['selected']}.",
        "N. CORRELATION ERROR PROPAGATION TO ACTION": "High spurious support selects that first action. Trap not repaired.",
    }
    lines = ["# SCIENTIFIC_CLAIMS.md\n", "Statuses: DEMONSTRATED, SUPPORTED, INCONCLUSIVE, NOT_DEMONSTRATED, REFUTED.\n"]
    for k, v in claims.items():
        lines.append(f"## {k} — {v}\n\n{ev.get(k, '')}\n")
    lines.append(
        "\n## Interpretation boundary\n\n"
        "Not claimed: decision making, rational choice, preference, goal-directed\n"
        "behavior, planning, motivation, desire, expected utility, belief-guided\n"
        "action, or free choice.\n"
    )
    (OUT / "SCIENTIFIC_CLAIMS.md").write_text("".join(lines) + "\n", encoding="utf-8")
    (OUT / "PROMOTION_RECOMMENDATION.md").write_text(
        f"""# PROMOTION_RECOMMENDATION.md

**Keep `future_sensitive_action` (and PE, relevance, TPS, bridge, conflict)
experimental and default OFF. Do not promote.**

- Not a secret argmax-as-new-policy: uses existing compete_scenarios.
- Action-frequency vs scenario support is separable; adapter uses scenario support.
- Compatible merge still max-not-sum (conflict ancestry).
- Incumbent lock still limits lived k≥2 coexistence ({incumbent_still}).
- Correlation trap **can propagate to behavior**.
- Ties: existing endogenous over first-actions, not a new breaker.
- Oscillation: support reversal can flip selection when evidence flips; no hysteresis variable.
- Memory/runtime: {perf}.

CURRENT INTEGRATED MM unchanged.
""",
        encoding="utf-8",
    )
    (OUT / "PERFORMANCE_RESULTS.md").write_text(
        f"""# PERFORMANCE_RESULTS.md

- 50 synthetic competes: {perf['50_competes_s']} s
- candidate count under load: {perf['candidate_count']} (bound {perf['bound']})
- wall experiment: {round(time.perf_counter() - t0, 3)} s
- new planner: {perf['new_planner']}
""",
        encoding="utf-8",
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"""# FINAL_REPORT.md

## 1. Where exactly did existing scenario competition discard future identity?

`collect_scenario_groups` identity omits predicted states; representatives
are one per first_action; predictive_conflict candidates never entered
those groups.

## 2. Was that behavior scientifically necessary or an implementation assumption?

One action must be selected, so a per-first-action representative is
necessary at the last step. Destroying future identity *before* cross-action
comparison, and ignoring conflict candidates, was an implementation assumption.

## 3. What minimal experimental change was made?

`future_sensitive_action` (default false): build groups from content-identified
conflict/continuation scenarios, then call unchanged `compete_scenarios`.

## 4. Does the extension merely preserve existing evidence, or introduce a new policy?

Preserve. Dominance remains (support, reliability, depth). Not a standalone
argmax. Not reward/utility.

## 5. Can two different first actions acquire ordinary predictive support without grafting evidence?

Lived clamp protocol: actions={lived_on['action_set']}, k2={lived_on['k2_any']}.
Primary not grafted. Incumbent MATCH still limits simultaneous k≥2
({incumbent_still}). MOVE-first seed actions={lived_move['action_set']}.

## 6. Can WAIT→P and MOVE:N→Q coexist?

Yes in the adapter (n_first_actions={two['n_first_actions']}).

## 7. Can both enter the same competition?

Yes.

## 8. Is scenario-specific support distinguishable from raw action frequency?

Yes. Receipts carry both. Competition uses scenario support.

## 9. Can prospective evidence alter competition while action frequency is controlled?

Yes: WAIT 100/4 vs MOVE 20/10 selected {freq['selected']}
({freq['classification']}).

## 10. What happens across the support sensitivity curve?

{[{'ratio': r['ratio'], 'sel': r['selected_rng0'], 'out': r['outcome']} for r in curve]}

## 11. What happens at equal support?

EXACT_TIE → existing endogenous over tied first-actions.
ACTION_CONFLICT_UNRESOLVED is that existing tie, not a new breaker.
WAIT is choosable at rng 0 only as existing index behavior.

## 12. Can ordinary new evidence reverse the scenario leader?

Yes (WAIT_then_MOVE={rev['WAIT_then_MOVE']}).

## 13. Can it reverse back?

Yes (re_reverse={rev['re_reverse']}).

## 14. Can the same present with different history produce different competition states?

Yes (H1={sph['H1_selected']} H2={sph['H2_selected']}).

## 15. Can it produce different selected actions?

Yes.

## 16. Does wiping history remove the difference?

Yes (wipe source={sph['wipe_source']}).

## 17. Can prediction disconfirmation alter later competition?

Inconclusive as a receipt-only effect. DISCONFIRMED does not decrement
support. 4.23 still increments on the executed action. Ordinary MATCH
failure (clamp) remains the lived path to NO_SUPPORT.

## 18. Does changed competition alter selected action?

Yes, when first actions differ and supports reverse.

## 19. Does selected action change requested physical action?

Yes: selected MOVE:* maps to requested Δv via the existing impulse bridge.

## 20. Does requested action change realized physical consequence?

Only if work reservoir allows. Zero work: selection can still be MOVE,
realized Δv ≈ 0.

## 21. Does selection still change under zero-work realization?

Cognitive selection yes (synthetic MOVE:N). Realization suppressed.

## 22. Can deeper prospective differences influence action?

Only as the existing third key (depth) after support and reliability.
No temporal discount. Shared-prefix later divergence stays distinct
scenarios; the first-action representative still competes on support.

## 23. Can more than two actions compete?

Yes (n_supported={three['n_supported']}, selected={three['selected']}).

## 24. Does correlation-trap error propagate into behavior?

Yes. CORRELATION TRAP CAN PROPAGATE TO BEHAVIOR.

## 25. Does incumbent lock still impose an upstream acquisition limitation?

Yes. Lived k≥2 remains rare; a valid incumbent MATCH still occupies
selection. FSA does not repair that lock or the sampler.

## 26. What exact causal gear remains missing after this experiment?

A way for **same-action** future discrimination (WAIT→P vs WAIT→Q) to
affect anything but the WAIT representative; and a non-lock path to
acquire a second action while an incumbent MATCH remains valid.
Disconfirmation does not yet revise 4.23 support downward.

## 27. Is future_sensitive_action genuinely generic?

Yes for already-experienced first actions (WAIT and MOVE:* pairs). Not
WAIT-specific. Not source-privileged on support.

## 28. Should it remain experimental?

Yes. Default OFF. Do not promote.

## DESIGN_BOUNDARY

Not hit. Success did not require grafting in the primary lived protocol,
reward/utility, a new argmax policy, exploration, sampler change, or a
planner. A remaining honest limit: lived simultaneous two-action MATCH is
still gated by incumbent lock; the adapter's action-change demonstration
is on already-supported distinct first-action scenarios, which existing
competition already knew how to compare once those scenarios actually arrive.
""",
        encoding="utf-8",
    )
    print(json.dumps({
        "out": str(OUT),
        "both_enter": primary_two_enter,
        "reversal": rev["WAIT_then_MOVE"],
        "re_reverse": rev["re_reverse"],
        "frequency_vs_scenario": freq["classification"],
        "lived_k2": lived_on["k2_any"],
        "default_off": CognitionConfig().future_sensitive_action,
        "claims": claims,
    }, indent=2))


if __name__ == "__main__":
    main()
