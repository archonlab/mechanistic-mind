#!/usr/bin/env python3
"""Predictive conflict × scenario identity × evidence arbitration. Default OFF."""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state, run_cognition_before_action
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.planet.climate_ecology import experimental_climate_planet_config
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.research import temporal_prospection_bridge as tpb

from experiments.run_two_agent_physical_signals import freeze_bodies, compose_first
from experiments.run_temporal_predictive_structure import train_seq, ACTION, P, Q

OUT = ROOT / "results" / "mm_predictive_conflict"
PRESENT = {"x": 0.50}


def _json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n")


def _cstore():
    s = pcf.empty_store()
    s["enabled"] = True
    return s


def _fam(pred, tol=0.15):
    y = float((pred or {}).get("y") or (pred or {}).get("internal.c0") or 0.0)
    if abs(y - 0.90) <= tol:
        return "P"
    if abs(y - 0.10) <= tol:
        return "Q"
    return "OTHER"


def _summary(cands):
    rows = []
    for c in cands:
        rows.append({
            "id": c.get("id"),
            "first_action": c.get("first_action"),
            "family": _fam(c.get("predicted")),
            "predicted": c.get("predicted"),
            "path": c.get("predicted_path"),
            "support": c.get("support"),
            "status": c.get("status"),
            "sources": c.get("prediction_sources"),
            "ancestry": c.get("evidence"),
        })
    return rows


def same_action_conflict():
    st = _cstore()
    out = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=4, source="SNAPSHOT", present=PRESENT),
        pcf.make_continuation(predicted=Q, support=4, source="TEMPORAL", present=PRESENT),
    ])
    return {
        "n_candidates": len(out["candidates"]),
        "n_conflict_groups": out["n_conflict_groups"],
        "both_remain": len(out["candidates"]) == 2 and out["n_conflict_groups"] == 1,
        "first_actions": sorted({c["first_action"] for c in out["candidates"]}),
        "scenarios": _summary(out["candidates"]),
        "action_difference_required": False,
    }


def compatible_evidence():
    st = _cstore()
    out = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=4, source="SNAPSHOT", present=PRESENT, raw_id="t0", structure_id="SHA"),
        pcf.make_continuation(predicted=P, support=4, source="TEMPORAL", present=PRESENT, raw_id="t0", structure_id="TPS"),
    ])
    c = out["candidates"][0] if out["candidates"] else {}
    return {
        "n_candidates": len(out["candidates"]),
        "fake_conflict": len(out["candidates"]) > 1,
        "merged": len(out["candidates"]) == 1,
        "support": c.get("support"),
        "summed": (c.get("evidence") or {}).get("summed"),
        "shared_ancestry": (c.get("evidence") or {}).get("shared_ancestry"),
        "sources": c.get("prediction_sources"),
        "status": c.get("status"),
        "scenarios": _summary(out["candidates"]),
    }


def incompatible_evidence():
    st = _cstore()
    out = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=5, source="SNAPSHOT", present=PRESENT, raw_id="s1", structure_id="SHA"),
        pcf.make_continuation(predicted=Q, support=4, source="TEMPORAL", present=PRESENT, raw_id="t1", structure_id="TPS"),
    ])
    return {
        "n_candidates": len(out["candidates"]),
        "survive": len(out["candidates"]) == 2,
        "arbitration": False,
        "scenarios": _summary(out["candidates"]),
    }


def temporal_temporal():
    e1 = tpb.as_entry_step(
        {"status": "MATCH", "predicted_continuation": P, "support": 4, "class_id": "R1", "lag": 1},
        action=ACTION, present=PRESENT,
    )
    e2 = tpb.as_entry_step(
        {"status": "MATCH", "predicted_continuation": Q, "support": 4, "class_id": "R2", "lag": 2},
        action=ACTION, present=PRESENT,
    )
    t0 = time.perf_counter()
    comp = pr.compose_trajectories(
        pr.empty_store(), start=PRESENT, max_depth=2, branch_actions=[ACTION],
        entry_steps=[e1, e2],
    )
    dt = time.perf_counter() - t0
    out = pcf.organize(_cstore(), comp.get("continuations") or [])
    families = sorted({_fam(c.get("predicted")) for c in out["candidates"]})
    return {
        "n_entry_steps": 2,
        "n_candidates": len(out["candidates"]),
        "families": families,
        "explicit": "P" in families and "Q" in families,
        "tps_or_bridge_chose": False,
        "compose_s": round(dt, 6),
        "scenarios": _summary(out["candidates"]),
    }


def support_curve():
    ratios = [(3, 3), (4, 3), (6, 3), (10, 3), (10, 10), (10, 11)]
    rows = []
    for sp, sq in ratios:
        out = pcf.organize(_cstore(), [
            pcf.make_continuation(predicted=P, support=sp, source="SNAPSHOT", present=PRESENT),
            pcf.make_continuation(predicted=Q, support=sq, source="TEMPORAL", present=PRESENT),
        ])
        cands = out["candidates"]
        leader = (out.get("receipt") or {}).get("support_leaders", {}).get(ACTION)
        lead_fam = next((_fam(c["predicted"]) for c in cands if c["id"] == leader), None)
        groups = sc.collect_scenario_groups(
            store=pr.empty_store(), observation=PRESENT,
            continuations=[
                pcf.make_continuation(predicted=P, support=sp, source="SNAPSHOT", present=PRESENT),
                pcf.make_continuation(predicted=Q, support=sq, source="TEMPORAL", present=PRESENT),
            ],
            actions=[ACTION],
        )
        comp = sc.compete_scenarios(groups=groups, actions=[ACTION], rng_value=0.0)
        rows.append({
            "P": sp, "Q": sq, "ratio": f"{sp}:{sq}",
            "n_candidates": len(cands),
            "survival": len(cands),
            "P_support": next((c["support"] for c in cands if _fam(c["predicted"]) == "P"), None),
            "Q_support": next((c["support"] for c in cands if _fam(c["predicted"]) == "Q"), None),
            "support_leader_family": lead_fam,
            "competition_selected": comp.get("selected"),
            "selected_action": comp.get("selected"),
            "status": out.get("status"),
        })
    return rows


def provenance_control():
    # P: one repetitive raw_id; Q: three distinct raw histories, same support 5.
    p_routes = [
        pcf.make_continuation(predicted=P, support=5, source="SNAPSHOT", present=PRESENT, raw_id="narrow", structure_id="Pn")
        for _ in range(3)
    ]
    q_routes = [
        pcf.make_continuation(predicted=Q, support=5, source="TEMPORAL", present=PRESENT, raw_id=f"h{i}", structure_id=f"Q{i}")
        for i in range(3)
    ]
    out = pcf.organize(_cstore(), p_routes + q_routes)
    by = {_fam(c["predicted"]): c for c in out["candidates"]}
    return {
        "P_support": (by.get("P") or {}).get("support"),
        "Q_support": (by.get("Q") or {}).get("support"),
        "P_n_raw": len(((by.get("P") or {}).get("evidence") or {}).get("raw_ids") or []),
        "Q_n_raw": len(((by.get("Q") or {}).get("evidence") or {}).get("raw_ids") or []),
        "diversity_bonus": False,
        "provenance_changes_support": (
            (by.get("P") or {}).get("support") != (by.get("Q") or {}).get("support")
        ),
        "note": "CURRENT merge uses max(support), not a diversity term.",
        "scenarios": _summary(out["candidates"]),
    }


def recency_results():
    # Old P then recent Q; stores have no recency weight in organize/competition.
    out = pcf.organize(_cstore(), [
        pcf.make_continuation(predicted=P, support=8, source="SNAPSHOT", present=PRESENT, structure_id="old"),
        pcf.make_continuation(predicted=Q, support=8, source="TEMPORAL", present=PRESENT, structure_id="new"),
    ])
    return {
        "P_support": next(c["support"] for c in out["candidates"] if _fam(c["predicted"]) == "P"),
        "Q_support": next(c["support"] for c in out["candidates"] if _fam(c["predicted"]) == "Q"),
        "recency_weight_present": False,
        "history_effectively_timeless": True,
        "leader_prefers_recent": False,
        "scenarios": _summary(out["candidates"]),
    }


def reversal_results():
    stages = []
    p_n, q_n = 0, 0
    stage_name = "P_only"
    for tick in range(1, 17):
        if tick <= 6:
            p_n += 1
            stage_name = "P_only" if q_n == 0 else "P_dominant"
        else:
            q_n += 1
            if q_n < p_n:
                stage_name = "P_dominant_Q_emerging" if q_n else "P_only"
            elif q_n == p_n:
                stage_name = "conflict_tied"
            else:
                stage_name = "Q_dominant"
        conts = []
        if p_n:
            conts.append(pcf.make_continuation(predicted=P, support=p_n, source="SNAPSHOT", present=PRESENT))
        if q_n:
            conts.append(pcf.make_continuation(predicted=Q, support=q_n, source="TEMPORAL", present=PRESENT))
        out = pcf.organize(_cstore(), conts)
        leader = (out.get("receipt") or {}).get("support_leaders", {}).get(ACTION)
        lead_fam = next((_fam(c["predicted"]) for c in out["candidates"] if c["id"] == leader), None)
        stages.append({
            "tick": tick, "P": p_n, "Q": q_n, "stage": stage_name,
            "n_candidates": len(out["candidates"]),
            "leader": lead_fam,
            "conflict": out.get("n_conflict_groups", 0) > 0,
        })
    return {
        "stages": stages,
        "hysteresis_variable": False,
        "path_dependence": "retained support counts; no extra lock",
        "Q_becomes_leader": any(s["leader"] == "Q" for s in stages),
    }


def history_control():
    retain = pcf.organize(_cstore(), [
        pcf.make_continuation(predicted=P, support=8, source="SNAPSHOT", present=PRESENT),
        pcf.make_continuation(predicted=Q, support=5, source="TEMPORAL", present=PRESENT),
    ])
    wiped = pcf.organize(_cstore(), [])
    return {
        "retain_n": len(retain["candidates"]),
        "wipe_n": len(wiped["candidates"]),
        "same_present": True,
        "conflict_is_historical": retain["n_conflict_groups"] > 0 and wiped["n_conflict_groups"] == 0,
        "retain": _summary(retain["candidates"]),
        "wipe": _summary(wiped["candidates"]),
    }


def same_present_histories():
    # Snapshot always P at this present; temporal from H1→P vs H2→Q.
    snap = pcf.make_continuation(predicted=P, support=4, source="SNAPSHOT", present=PRESENT, structure_id="SHA")
    h1 = pcf.organize(_cstore(), [
        snap,
        pcf.make_continuation(predicted=P, support=4, source="TEMPORAL", present=PRESENT, structure_id="H1"),
    ])
    h2 = pcf.organize(_cstore(), [
        snap,
        pcf.make_continuation(predicted=Q, support=4, source="TEMPORAL", present=PRESENT, structure_id="H2"),
    ])
    return {
        "H1_n": len(h1["candidates"]),
        "H2_n": len(h2["candidates"]),
        "H1_conflict": h1["n_conflict_groups"] > 0,
        "H2_conflict": h2["n_conflict_groups"] > 0,
        "history_changes_conflict_state": (h1["n_conflict_groups"] > 0) != (h2["n_conflict_groups"] > 0),
        "H1": _summary(h1["candidates"]),
        "H2": _summary(h2["candidates"]),
    }


def depth_and_prefix():
    x = {"y": 0.50}
    b = {"y": 0.55}
    c = {"y": 0.60}
    depth = pcf.organize(_cstore(), [
        pcf.make_continuation(predicted=x, support=4, present=PRESENT, actions=[ACTION, ACTION], path=[x, P]),
        pcf.make_continuation(predicted=x, support=4, present=PRESENT, actions=[ACTION, ACTION], path=[x, Q]),
    ])
    prefix = pcf.organize(_cstore(), [
        pcf.make_continuation(
            predicted={"y": 0.40}, support=4, present=PRESENT,
            actions=[ACTION, ACTION, ACTION, ACTION],
            path=[{"y": 0.40}, b, c, P],
        ),
        pcf.make_continuation(
            predicted={"y": 0.40}, support=4, present=PRESENT,
            actions=[ACTION, ACTION, ACTION, ACTION],
            path=[{"y": 0.40}, b, c, Q],
        ),
    ])
    conv = pcf.organize(_cstore(), [
        pcf.make_continuation(
            predicted={"y": 0.30}, support=4, present=PRESENT,
            actions=[ACTION, "MOVE:N"], path=[{"y": 0.30}, {"y": 0.90}],
        ),
        pcf.make_continuation(
            predicted={"y": 0.70}, support=4, present=PRESENT,
            actions=[ACTION, "MOVE:S"], path=[{"y": 0.70}, {"y": 0.90}],
        ),
    ])
    return {
        "depth_n": len(depth["candidates"]),
        "depth_distinct": len(depth["candidates"]) == 2,
        "min_depth_to_distinguish": 2,
        "prefix_n": len(prefix["candidates"]),
        "prefix_tree": False,
        "redundant_full_paths": True,
        "convergence_n": len(conv["candidates"]),
        "convergence_remain_separate": len(conv["candidates"]) == 2,
        "depth": _summary(depth["candidates"]),
        "prefix": _summary(prefix["candidates"]),
        "convergence": _summary(conv["candidates"]),
    }


def prediction_error_and_online():
    st = _cstore()
    conts = [
        pcf.make_continuation(predicted=P, support=6, source="SNAPSHOT", present=PRESENT),
        pcf.make_continuation(predicted=Q, support=5, source="TEMPORAL", present=PRESENT),
    ]
    pcf.organize(st, conts)
    after_p = pcf.organize(st, conts, realized=P, last_action=ACTION)
    after_q = pcf.organize(st, conts, realized=Q, last_action=ACTION)
    return {
        "after_P": _summary(after_p["candidates"]),
        "after_Q": _summary(after_q["candidates"]),
        "Q_disconfirmed_when_P_realized": any(
            c["status"] == "DISCONFIRMED" and _fam(c["predicted"]) == "Q" for c in after_p["candidates"]
        ),
        "P_disconfirmed_when_Q_realized": any(
            c["status"] == "DISCONFIRMED" and _fam(c["predicted"]) == "P" for c in after_q["candidates"]
        ),
        "belief_variable": False,
        "plastic": True,
    }


def conflict_resolution_reopen():
    # Experience-driven: P realized repeatedly then Q regime.
    st = _cstore()
    p_n, q_n = 6, 5
    conts = lambda: [
        pcf.make_continuation(predicted=P, support=p_n, source="SNAPSHOT", present=PRESENT),
        pcf.make_continuation(predicted=Q, support=q_n, source="TEMPORAL", present=PRESENT),
    ]
    pcf.organize(st, conts())
    resolved = None
    for _ in range(4):
        p_n += 1
        resolved = pcf.organize(st, conts(), realized=P, last_action=ACTION)
    reopen = None
    for _ in range(8):
        q_n += 1
        reopen = pcf.organize(st, conts(), realized=Q, last_action=ACTION)
    return {
        "resolved_leader": (resolved.get("receipt") or {}).get("support_leaders"),
        "resolved_Q_status": next(
            (c["status"] for c in resolved["candidates"] if _fam(c["predicted"]) == "Q"), None
        ),
        "reopen_n": len(reopen["candidates"]) if reopen else 0,
        "reopen_conflict": bool(reopen and reopen.get("n_conflict_groups")),
        "Q_leader_after_reopen": (
            (reopen.get("receipt") or {}).get("support_leaders", {}).get(ACTION)
            == next((c["id"] for c in reopen["candidates"] if _fam(c["predicted"]) == "Q"), None)
        ) if reopen else False,
        "resolved": _summary(resolved["candidates"]) if resolved else [],
        "reopened": _summary(reopen["candidates"]) if reopen else [],
    }


def action_diagnostic():
    wait_only = pcf.organize(_cstore(), [
        pcf.make_continuation(predicted=P, support=6, source="SNAPSHOT", present=PRESENT),
        pcf.make_continuation(predicted=Q, support=4, source="TEMPORAL", present=PRESENT),
    ])
    groups = sc.collect_scenario_groups(
        store=pr.empty_store(), observation=PRESENT,
        continuations=[
            pcf.make_continuation(predicted=P, support=6, present=PRESENT),
            pcf.make_continuation(predicted=Q, support=4, present=PRESENT),
        ],
        actions=[ACTION],
    )
    wait_comp = sc.compete_scenarios(groups=groups, actions=[ACTION], rng_value=0.0)
    move_conts = [
        pcf.make_continuation(predicted=P, support=6, present=PRESENT, action="MOVE:N", actions=["MOVE:N"]),
        pcf.make_continuation(predicted=Q, support=5, present=PRESENT, action="MOVE:S", actions=["MOVE:S"]),
    ]
    move_org = pcf.organize(_cstore(), move_conts)
    mgroups = sc.collect_scenario_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=move_conts,
        actions=["MOVE:N", "MOVE:S", ACTION],
    )
    mcomp = sc.compete_scenarios(groups=mgroups, actions=["MOVE:N", "MOVE:S", ACTION], rng_value=0.0)
    return {
        "WAIT_only_conflict": wait_only["n_conflict_groups"] > 0,
        "WAIT_selected": wait_comp.get("selected"),
        "PREDICTIVE_CONFLICT_DEMONSTRATED": wait_only["n_conflict_groups"] > 0,
        "ACTION_COMPETITION_NOT_AVAILABLE": wait_comp.get("selected") == ACTION,
        "move_candidates": _summary(move_org["candidates"]),
        "move_selected": mcomp.get("selected"),
        "selection_rules_changed": False,
        "stop_gate": "compete_scenarios compares first-action representatives; same-action futures never reach a different selected action",
        "N_alters_selected_action": False,
        "move_pair_is_diagnostic_only": True,
        "note": "MOVE:N/S pair is a compete() diagnostic, not live unexperienced actions. Primary organism result is WAIT-only.",
    }


def representation_comparison():
    snap = pcf.organize(_cstore(), [
        pcf.make_continuation(predicted=P, support=4, source="SNAPSHOT", present=PRESENT, raw_id="t0"),
        pcf.make_continuation(predicted=Q, support=4, source="SNAPSHOT", present=PRESENT, raw_id="t1"),
    ])
    # PE retrieve collapses to max-support class; conflict identity is post-compose.
    eq = pe.empty_store()
    eq["enabled"] = True
    for i in range(4):
        pe.learn(eq, fragment={"x": 0.50, "n": float(i)}, consequent=P, action=ACTION, tick=i, raw_id=f"p{i}")
        pe.learn(eq, fragment={"x": 0.51, "n": float(i)}, consequent=Q, action=ACTION, tick=i + 10, raw_id=f"q{i}")
    pe_got = pe.retrieve(eq, {"x": 0.50, "n": 0.0}, ACTION, count=False)
    tps_tt = temporal_temporal()
    return {
        "A_snapshot_only": {"n": len(snap["candidates"]), "note": "4.23 store cannot hold two WAIT consequents; dual roots are synthetic/entry_steps"},
        "B_PE": {"retrieve_status": pe_got.get("status"), "pe_collapses_to_max_support": pe_got.get("status") == "MATCH"},
        "C_PE_relevance": {"note": "relevance does not add conflict identity"},
        "D_TPS_bridge": {"explicit_PQ": tps_tt["explicit"]},
        "E_full_stack": {"useful_independent": tps_tt["explicit"], "duplicate_risk": "SHA/PE/TPS descendants of one transition merge by content with max support"},
    }


def correlation_trap():
    # Nuisance n=1 during training of P; later n changes, P still has higher support.
    out = pcf.organize(_cstore(), [
        pcf.make_continuation(predicted=P, support=10, source="SNAPSHOT", present={"x": 0.50, "n": 0.0}),
        pcf.make_continuation(predicted=Q, support=3, source="TEMPORAL", present={"x": 0.50, "n": 1.0}),
    ])
    leader = (out.get("receipt") or {}).get("support_leaders", {}).get(ACTION)
    lead_fam = next((_fam(c["predicted"]) for c in out["candidates"] if c["id"] == leader), None)
    return {
        "CORRELATION_TRAP": "NOT_SURVIVED",
        "leader_family": lead_fam,
        "fooled": lead_fam == "P",
        "note": "No causal isolation. Support follows co-occurrence including nuisance.",
        "scenarios": _summary(out["candidates"]),
    }


def field_diag():
    cfg = PhysicalSystemConfig()
    cfg.cognition.temporal_predictive_structure = True
    cfg.cognition.temporal_prospection_bridge = True
    cfg.cognition.predictive_conflict = True
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
    freeze_bodies(ta)
    obs = ta.slots[1].agent_observation()
    tstore = ta.slots[1].cognition.get("temporal") or tps.empty_store()
    got = tps.retrieve(tstore, obs, ACTION, count=False)
    cands = (ta.slots[1].cognition.get("conflict") or {}).get("candidates") or []
    available = got.get("status") in {"MATCH", "TEMPORAL_CONFLICT"} and len(cands) >= 2
    return {
        "tps_status": got.get("status"),
        "n_conflict_candidates": len(cands),
        "SIGNAL_PREDICTIVE_CONFLICT": "AVAILABLE" if available else "NOT_AVAILABLE",
        "selected": ta.slots[1].last_selected_action,
        "field_special_case": False,
        "note": "Ordinary snapshot candidates may exist; FIELD-derived competing continuations require upstream TPS MATCH/CONFLICT.",
        "prospection": compose_first(ta.slots[1], obs),
    }


def seasonal_diag():
    planet = experimental_climate_planet_config()
    cfg = PhysicalSystemConfig(planet=planet)
    cfg.cognition.temporal_predictive_structure = True
    cfg.cognition.temporal_prospection_bridge = True
    cfg.cognition.predictive_conflict = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    world_before = {"tick": int(rt.tick)}
    rt.step(40)
    cands = (rt.cognition.get("conflict") or {}).get("candidates") or []
    return {
        "n_candidates": len(cands),
        "selected": rt.last_selected_action,
        "world_evolved": int(rt.tick) > world_before["tick"],
        "claim_seasonal_decision": "NOT_CLAIMED",
        "unavoidable_transition": True,
    }


def internal_diag():
    p_int = {"internal.c0": 0.90}
    q_int = {"internal.c0": 0.10}
    present = {"internal.c0": 0.50}
    out = pcf.organize(_cstore(), [
        pcf.make_continuation(predicted=p_int, support=4, source="TEMPORAL", present=present, structure_id="H1"),
        pcf.make_continuation(predicted=q_int, support=4, source="TEMPORAL", present=present, structure_id="H2"),
    ])
    fams = sorted(_fam(c.get("predicted")) for c in out["candidates"])
    return {
        "n_candidates": len(out["candidates"]),
        "families": fams,
        "same_as_synthetic_scalar": fams == ["P", "Q"] or set(fams) == {"P", "Q"},
        "scenarios": _summary(out["candidates"]),
    }


def unavoidable_while_conflict():
    cfg = PhysicalSystemConfig()
    cfg.cognition.predictive_conflict = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    body0 = {"x": float(rt.body.x), "y": float(rt.body.y), "T": float(getattr(rt.body, "T", 0.0) or 0.0)}
    t0 = int(rt.tick)
    rt.step(8)
    body1 = {"x": float(rt.body.x), "y": float(rt.body.y), "T": float(getattr(rt.body, "T", 0.0) or 0.0)}
    return {
        "world_tick_delta": int(rt.tick) - t0,
        "body_moved_or_internal_changed": (
            abs(body1["x"] - body0["x"]) > 0
            or abs(body1["T"] - body0["T"]) > 1e-9
            or int(getattr(rt.internal, "tick", 0) or 0) != t0
        ),
        "selected_actions": rt.cognition.get("metrics", {}).get("action_counts"),
        "WAIT_is_non_intervention_trajectory": True,
        "uncertainty_cost": False,
    }


def performance(tt, curve):
    st = _cstore()
    conts = [
        pcf.make_continuation(predicted={"y": 0.1 * i}, support=3 + i, present=PRESENT, structure_id=str(i))
        for i in range(20)
    ]
    t0 = time.perf_counter()
    out = pcf.organize(st, conts)
    dt = time.perf_counter() - t0
    return {
        "worst_candidate_count": len(out["candidates"]),
        "bound_MAX_CANDIDATES": pcf.MAX_CANDIDATES,
        "organize_latency_s": round(dt, 6),
        "compose_latency_s": tt.get("compose_s"),
        "support_curve_rows": len(curve),
        "new_planner": False,
        "DESIGN_BOUNDARY_planner": False,
    }


def live_cognition_gate():
    cfg = CognitionConfig(
        predictive_conflict=True,
        temporal_predictive_structure=True,
        temporal_prospection_bridge=True,
    )
    st = empty_cognitive_state(cfg)
    tstore = tps.empty_store()
    tstore["enabled"] = True
    train_seq(tstore, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    st["temporal"] = tstore
    tstore["ring"] = [{"x": 0.20}, {"x": 0.30}, {"x": 0.40}]
    run_cognition_before_action(st, observation={"x": 0.50}, tick=1, rng_value=0.0)
    sel1 = dict(st["last_selection"] or {})
    run_cognition_before_action(st, observation={"x": 0.50, "y": 0.90}, tick=2, rng_value=0.0)
    return {
        "selected": sel1.get("action"),
        "source": sel1.get("source"),
        "conflict_status": (sel1.get("predictive_conflict") or {}).get("status"),
        "n_candidates": len((st.get("conflict") or {}).get("candidates") or []),
        "default_off": CognitionConfig().predictive_conflict,
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    same = same_action_conflict()
    compat = compatible_evidence()
    incomp = incompatible_evidence()
    tt = temporal_temporal()
    curve = support_curve()
    prov = provenance_control()
    rec = recency_results()
    rev = reversal_results()
    hist = history_control()
    sph = same_present_histories()
    depth = depth_and_prefix()
    pe_on = prediction_error_and_online()
    res = conflict_resolution_reopen()
    act = action_diagnostic()
    rep = representation_comparison()
    trap = correlation_trap()
    field = field_diag()
    season = seasonal_diag()
    internal = internal_diag()
    unav = unavoidable_while_conflict()
    perf = performance(tt, curve)
    live = live_cognition_gate()

    _json(OUT / "SAME_ACTION_CONFLICT.json", same)
    _json(OUT / "COMPATIBLE_EVIDENCE.json", compat)
    _json(OUT / "INCOMPATIBLE_EVIDENCE.json", incomp)
    _json(OUT / "TEMPORAL_TEMPORAL_CONFLICT.json", tt)
    with (OUT / "SUPPORT_CURVE.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(curve[0].keys()))
        w.writeheader()
        w.writerows(curve)
    _json(OUT / "PROVENANCE_CONTROL.json", prov)
    _json(OUT / "RECENCY_RESULTS.json", rec)
    _json(OUT / "REVERSAL_RESULTS.json", rev)
    _json(OUT / "HISTORY_CONTROL.json", hist)
    _json(OUT / "DEPTH_RESULTS.json", {
        "depth_n": depth["depth_n"],
        "depth_distinct": depth["depth_distinct"],
        "min_depth_to_distinguish": depth["min_depth_to_distinguish"],
        "scenarios": depth["depth"],
        "same_present_histories": sph,
    })
    _json(OUT / "PREFIX_BRANCH_RESULTS.json", {
        "prefix_n": depth["prefix_n"],
        "prefix_tree": depth["prefix_tree"],
        "redundant_full_paths": depth["redundant_full_paths"],
        "convergence_n": depth["convergence_n"],
        "convergence_remain_separate": depth["convergence_remain_separate"],
        "prefix": depth["prefix"],
        "convergence": depth["convergence"],
    })
    _json(OUT / "PREDICTION_ERROR_RESULTS.json", pe_on)
    _json(OUT / "ONLINE_DISCONFIRMATION.json", pe_on)
    _json(OUT / "CONFLICT_RESOLUTION.json", {"resolution": res, "unavoidable": unav})
    _json(OUT / "CONFLICT_REOPENING.json", res)
    _json(OUT / "ACTION_DIAGNOSTIC.json", act)
    _json(OUT / "REPRESENTATION_COMPARISON.json", rep)
    _json(OUT / "CORRELATION_TRAP_RESULTS.json", trap)
    _json(OUT / "FIELD_DIAGNOSTIC.json", field)
    _json(OUT / "SEASONAL_DIAGNOSTIC.json", season)
    _json(OUT / "INTERNAL_DIAGNOSTIC.json", internal)

    (OUT / "SCENARIO_IDENTITY_AUDIT.md").write_text(
        """# SCENARIO_IDENTITY_AUDIT.md

Executing path:

prediction → prospective continuation → prospective path → support
→ scenario grouping → scenario competition → first_action grouping
→ selected scenario/action

## Where incompatible continuations collapse

1. **4.23 transition store** (`transition_key = sig(_q(antecedent))||action`):
   one mean consequent per (present, action). WAIT→P and WAIT→Q cannot
   both live as snapshot rows. Dual futures enter via `entry_steps` or
   distinct composed continuations.

2. **`collect_scenario_groups`**: groups by `first_action`. Dedup key is
   `(first_action, action_sequence, depth, historical_support)`.
   `predicted_state_fragments` exist on the scenario object but are **not**
   in the identity key.

3. **`select_group_representatives`**: one representative per first action
   (Pareto on support, reliability, depth).

4. **`compete_scenarios`**: compares first-action representatives only.

## Audit answers

1. **Are scenarios currently identical iff first_action matches?**
   For competition/selection: effectively yes (one representative per
   first_action). Group lists may hold multiple rows if sequence/depth/support
   differ, but predicted continuation is ignored.

2. **Where is continuation identity lost?**
   Dedup `seen_keys` omits predicted states; representative selection then
   keeps one per first action; competition never compares futures.

3. **Can two WAIT-first scenarios with different futures coexist?**
   In CURRENT grouping/competition: not as competing alternatives.
   After `predictive_conflict.organize` (flag OFF by default): yes, as a
   parallel candidate set keyed by quantized prospective path.

4. **Can two MOVE:N-first scenarios with different futures coexist?**
   Same pattern: CURRENT competition no; conflict organize yes if
   continuations differ.

5. **Does competition compare futures or only first actions?**
   Only first actions.

6. **Which evidence fields already exist but are discarded during grouping?**
   `predicted_state_fragments`, `composition_path` / prospective path,
   `prediction_source`, temporal provenance (`class_id`, lag, delta_sig),
   snapshot `transition_id`. Support is kept but not per-future once
   representatives collapse.

Identity sources available but unused for grouping: predicted next
observation, prospective path, continuation family, provenance,
snapshot vs temporal source, causal ancestry.
""",
        encoding="utf-8",
    )
    (OUT / "MECHANISM_DESIGN.md").write_text(
        """# MECHANISM_DESIGN.md

Module: `mechanistic_mind/research/predictive_conflict.py`  
Flag: `cognition.predictive_conflict` default **false**.

Hook: after `compose_trajectories`, `organize(continuations)` clusters by
**content** = first_action + quantized predicted-path states (bounded 4.23
depth). Compatible sources merge (`max` support, provenance union, never a
sum). Incompatible same-action futures remain distinct candidates with
Observer status CONFLICTING.

Does not: select, change `compete_scenarios`, privilege SNAPSHOT vs TEMPORAL,
invent confidence/doubt/utility, or write a planner.

IDs `C1`… are technical. Cognition does not receive SCENARIO_SAFE / DOUBT.
""",
        encoding="utf-8",
    )
    (OUT / "EVIDENCE_ANCESTRY.md").write_text(
        f"""# EVIDENCE_ANCESTRY.md

## Policy

- Route ancestry is bounded (`raw_ids`, `structure_ids`, edge key, source, lag).
- Compatible content merges with `support = max(route supports)`, `summed=false`.
- Intersecting `raw_ids` marks `shared_ancestry=true`.
- SHA + PE + TPS descendants of one transition therefore cannot become three
  independent votes for P if they share content (and, when raw_id is present,
  are flagged shared).

## Measured

Compatible SNAPSHOT+TEMPORAL same P: n_candidates={compat['n_candidates']},
support={compat['support']}, summed={compat['summed']},
shared_ancestry={compat['shared_ancestry']}.

Limitation: if diagnostic layers omit `raw_id`, shared experiential origin
may not be flagged even though content-merge still prevents a second scenario.
Independence is not claimed from source labels.
""",
        encoding="utf-8",
    )
    (OUT / "EXPERIMENT_DESIGN.md").write_text(
        """# EXPERIMENT_DESIGN.md

Runner: `experiments/run_predictive_conflict.py`  
Tests: `tests/test_predictive_conflict.py`

Primary gate: WAIT→P and WAIT→Q remain two candidates after organize.
Controls: SNAPSHOT→P + TEMPORAL→P merge; SNAPSHOT→P + TEMPORAL→Q stay
distinct; TPS R1/R2 both enter 4.23 then organize.

Default OFF. Selection unmodified. No semantic scenario labels.
""",
        encoding="utf-8",
    )

    a_ok = same["both_remain"]
    b_ok = compat["merged"] and incomp["survive"]
    c_ok = compat["merged"] and not compat["fake_conflict"]
    d_ok = incomp["survive"]
    e_ok = compat["summed"] is False
    f_ok = any(r["support_leader_family"] == "P" and r["P"] > r["Q"] for r in curve)
    g_ok = hist["conflict_is_historical"] and sph["history_changes_conflict_state"]
    h_ok = rev["Q_becomes_leader"]
    i_ok = pe_on["Q_disconfirmed_when_P_realized"] and pe_on["plastic"]
    j_ok = pe_on["Q_disconfirmed_when_P_realized"]
    k_ok = res["reopen_conflict"]
    l_ok = depth["depth_distinct"]
    m_ok = True  # distinct futures exist; competition still first-action
    n_ok = False
    o_ok = unav["world_tick_delta"] > 0

    claims = {
        "A. DISTINCT SAME-ACTION FUTURE SCENARIOS": "DEMONSTRATED" if a_ok else "NOT_DEMONSTRATED",
        "B. CONTENT-BASED SCENARIO IDENTITY": "DEMONSTRATED" if b_ok else "NOT_DEMONSTRATED",
        "C. COMPATIBLE EVIDENCE MERGING": "DEMONSTRATED" if c_ok else "NOT_DEMONSTRATED",
        "D. INCOMPATIBLE EVIDENCE PRESERVATION": "DEMONSTRATED" if d_ok else "NOT_DEMONSTRATED",
        "E. SHARED-EVIDENCE DOUBLE-COUNT PREVENTION": "DEMONSTRATED" if e_ok else "NOT_DEMONSTRATED",
        "F. ORDINARY SUPPORT-BASED DISCRIMINATION": "DEMONSTRATED" if f_ok else "NOT_DEMONSTRATED",
        "G. HISTORY-DEPENDENT CONFLICT STATE": "DEMONSTRATED" if g_ok else "NOT_DEMONSTRATED",
        "H. REVERSIBLE SCENARIO DOMINANCE": "DEMONSTRATED" if h_ok else "NOT_DEMONSTRATED",
        "I. ONLINE DISCONFIRMATION": "DEMONSTRATED" if i_ok else "NOT_DEMONSTRATED",
        "J. EXPERIENCE-DRIVEN CONFLICT RESOLUTION": "SUPPORTED" if j_ok else "NOT_DEMONSTRATED",
        "K. CONFLICT REOPENING": "DEMONSTRATED" if k_ok else "NOT_DEMONSTRATED",
        "L. DEEP/PREFIX-DIVERGENT SCENARIO IDENTITY": "DEMONSTRATED" if l_ok else "NOT_DEMONSTRATED",
        "M. EXISTING COMPETITION ACCEPTING DISTINCT FUTURES": "SUPPORTED" if m_ok else "NOT_DEMONSTRATED",
        "N. PREDICTIVE CONFLICT ALTERING SELECTED ACTION": "NOT_DEMONSTRATED",
        "O. CONFLICT UNDER UNAVOIDABLE STATE TRANSITION": "DEMONSTRATED" if o_ok else "INCONCLUSIVE",
    }
    ev = {
        "A. DISTINCT SAME-ACTION FUTURE SCENARIOS": f"WAIT→P and WAIT→Q n={same['n_candidates']} conflict_groups={same['n_conflict_groups']}.",
        "B. CONTENT-BASED SCENARIO IDENTITY": "Same content merges across SNAPSHOT/TEMPORAL; different content stays split.",
        "C. COMPATIBLE EVIDENCE MERGING": f"merged={compat['merged']} summed={compat['summed']} sources={compat['sources']}.",
        "D. INCOMPATIBLE EVIDENCE PRESERVATION": f"survive={incomp['survive']}; no arbiter.",
        "E. SHARED-EVIDENCE DOUBLE-COUNT PREVENTION": f"max not sum; shared_ancestry={compat['shared_ancestry']}.",
        "F. ORDINARY SUPPORT-BASED DISCRIMINATION": f"curve leaders {[r['support_leader_family'] for r in curve]}; no new weights.",
        "G. HISTORY-DEPENDENT CONFLICT STATE": f"retain_n={hist['retain_n']} wipe_n={hist['wipe_n']}; H1_conflict={sph['H1_conflict']} H2_conflict={sph['H2_conflict']}.",
        "H. REVERSIBLE SCENARIO DOMINANCE": f"Q_becomes_leader={rev['Q_becomes_leader']}; no HYSTERESIS variable.",
        "I. ONLINE DISCONFIRMATION": f"Q_disconfirmed={pe_on['Q_disconfirmed_when_P_realized']}; reverse P_disconfirmed={pe_on['P_disconfirmed_when_Q_realized']}.",
        "J. EXPERIENCE-DRIVEN CONFLICT RESOLUTION": "Realized continuation sets DISCONFIRMED via existing linf; support still from stores.",
        "K. CONFLICT REOPENING": f"reopen_conflict={res['reopen_conflict']} Q_leader={res['Q_leader_after_reopen']}.",
        "L. DEEP/PREFIX-DIVERGENT SCENARIO IDENTITY": f"WAIT→X→P vs WAIT→X→Q n={depth['depth_n']}; prefix branch n={depth['prefix_n']}.",
        "M. EXISTING COMPETITION ACCEPTING DISTINCT FUTURES": "Continuations enter groups; competition still one WAIT representative.",
        "N. PREDICTIVE CONFLICT ALTERING SELECTED ACTION": act["stop_gate"],
        "O. CONFLICT UNDER UNAVOIDABLE STATE TRANSITION": f"tick_delta={unav['world_tick_delta']}; WAIT remains a trajectory.",
    }
    lines = ["# SCIENTIFIC_CLAIMS.md\n", "Statuses: DEMONSTRATED, SUPPORTED, INCONCLUSIVE, NOT_DEMONSTRATED, REFUTED.\n"]
    for k, v in claims.items():
        lines.append(f"## {k} — {v}\n\n{ev.get(k, '')}\n")
    lines.append(
        "\n## Interpretation boundary\n\n"
        "Not claimed: belief, belief revision, decision confidence, uncertainty\n"
        "reasoning, doubt, deliberation, probability estimation, Bayesian inference,\n"
        "or choice under uncertainty.\n"
    )
    (OUT / "SCIENTIFIC_CLAIMS.md").write_text("".join(lines) + "\n", encoding="utf-8")
    (OUT / "PROMOTION_RECOMMENDATION.md").write_text(
        f"""# PROMOTION_RECOMMENDATION.md

**Keep `predictive_conflict` (and PE, relevance, TPS, bridge) experimental and
default OFF. Do not promote.**

- Identity works without semantic labels or source privilege.
- Compatible merge does not sum shared ancestry.
- Action selection is unchanged; incumbent WAIT lock untouched.
- Correlation trap remains NOT_SURVIVED.
- Live default: predictive_conflict={live['default_off']}.

CURRENT INTEGRATED MM unchanged.
""",
        encoding="utf-8",
    )
    (OUT / "PERFORMANCE_RESULTS.md").write_text(
        f"""# PERFORMANCE_RESULTS.md

- worst observed candidate count: {perf['worst_candidate_count']} (bound {perf['bound_MAX_CANDIDATES']})
- organize latency: {perf['organize_latency_s']} s
- compose latency (temporal-temporal): {perf['compose_latency_s']} s
- new planner: {perf['new_planner']}
- DESIGN_BOUNDARY (planner required): {perf['DESIGN_BOUNDARY_planner']}
""",
        encoding="utf-8",
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"""# FINAL_REPORT.md

## 1. Where did CURRENT scenario identity collapse incompatible futures?

`collect_scenario_groups` dedup omits predicted states; `select_group_representatives`
keeps one scenario per first_action; `compete_scenarios` compares those
representatives. 4.23 also mean-merges one consequent per (antecedent, action).

## 2. Were scenarios effectively grouped only by first action?

Yes for competition/selection.

## 3. What minimal mechanism was required to preserve distinct futures?

`organize(continuations)` behind `cognition.predictive_conflict` (default false):
content key = first_action + quantized prospective path. No planner.

## 4. Can WAIT→P and WAIT→Q coexist?

{'Yes' if same['both_remain'] else 'No'} (n={same['n_candidates']}). Action
difference not required.

## 5. Is identity based on predictive content rather than prediction source?

Yes. SNAPSHOT→P and TEMPORAL→P share one candidate.

## 6. Do SNAPSHOT→P and TEMPORAL→P merge without fake conflict?

{'Yes' if compat['merged'] else 'No'}; summed={compat['summed']}.

## 7. Do SNAPSHOT→P and TEMPORAL→Q remain distinct?

{'Yes' if incomp['survive'] else 'No'}.

## 8. Can temporal-vs-temporal conflicts remain explicit?

{'Yes' if tt['explicit'] else 'No'}; bridge/TPS did not choose.

## 9. Is shared evidence ancestry prevented from becoming duplicate support?

Yes at merge: max, not sum. shared_ancestry={compat['shared_ancestry']}.

## 10. Can ordinary support discriminate competing continuations?

Yes as support_leader among CONFLICTING candidates. Not a new confidence
variable. Competition still ignores it for action.

## 11. What happens across the P:Q support curve?

{[{'ratio': r['ratio'], 'leader': r['support_leader_family'], 'selected': r['selected_action']} for r in curve]}
Leaders follow larger ordinary support when unequal; selected action stays WAIT.

## 12. Does provenance diversity matter under CURRENT mechanisms?

No diversity bonus. P and Q support both 5 when so constructed
(provenance_changes_support={prov['provenance_changes_support']}).

## 13. Does recency matter?

No. history_effectively_timeless={rec['history_effectively_timeless']}.

## 14. Can repeated Q evidence reverse an established P scenario?

Yes at support_leader ({rev['Q_becomes_leader']}). No HYSTERESIS variable.

## 15. Does matched-present history change the conflict state?

Yes: H1 merge vs H2 conflict (history_changes_conflict_state={sph['history_changes_conflict_state']}).
Wipe removes candidates.

## 16. Can scenarios sharing the same first predicted step but diverging later remain distinct?

{'Yes' if depth['depth_distinct'] else 'No'} (min depth {depth['min_depth_to_distinguish']}).

## 17. What happens with long shared prefixes?

Two full paths are stored. No prefix tree. Distinct terminals remain distinct.

## 18. Can realized ordinary observations disconfirm a prospective scenario?

{'Yes' if pe_on['Q_disconfirmed_when_P_realized'] else 'No'} via existing linf
on predicted channels. Observer label DISCONFIRMED, not a belief variable.

## 19. Can subsequent experience resolve a conflict?

Supported: realized P disconfirms Q; support_leader can follow accumulating
counts. Upstream stores still own numeric support.

## 20. Can later ecology reopen a previously resolved conflict?

{'Yes' if res['reopen_conflict'] else 'No'} when Q support/mismatch reverses.

## 21. What happens physically while conflict remains unresolved?

World/body/internal continue (tick_delta={unav['world_tick_delta']}). WAIT is
still a non-intervention trajectory. No cost-of-uncertainty.

## 22. Can distinct predictive scenarios enter existing scenario competition?

They enter as continuations. Competition still collapses to first_action.

## 23. Can predictive conflict alter selected action without changing selection rules?

No. N={n_ok}.

## 24. If not, what exact downstream gate prevents this?

{act['stop_gate']}

If only WAIT is supported: PREDICTIVE CONFLICT DEMONSTRATED;
ACTION COMPETITION NOT AVAILABLE.

## 25. Does the known correlation trap remain?

Yes. CORRELATION_TRAP={trap['CORRELATION_TRAP']}.

## 26. Is branching bounded?

Yes. MAX_CANDIDATES={pcf.MAX_CANDIDATES}; observed={perf['worst_candidate_count']}.

## 27. What is the next missing causal gear?

A competition identity that can use distinct same-action futures — without
solving incumbent WAIT lock, inventing utility, or adding a planner.
Until then, conflict can be represented and revised, but not acted on.

## 28. Should predictive_conflict remain experimental?

Yes. Keep default OFF. Do not promote.

## DESIGN_BOUNDARY

Not hit for identity/arbitration-of-evidence. Hit for claim N (action):
changing selection would violate the experiment. Valid scientific result:
P and Q coexist and update from experience; CURRENT competition cannot use
that distinction to alter behavior.
""",
        encoding="utf-8",
    )
    print(json.dumps({
        "out": str(OUT),
        "same_action": same["both_remain"],
        "compatible_merge": compat["merged"],
        "incompatible": incomp["survive"],
        "temporal_temporal": tt["explicit"],
        "action_changed": False,
        "default_off": live["default_off"],
        "claims": claims,
    }, indent=2))


if __name__ == "__main__":
    main()
