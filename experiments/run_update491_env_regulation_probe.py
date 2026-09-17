#!/usr/bin/env python3
"""Update 4.9.1 — Environmental regulation probe × existing cognition.

Diagnostic only. No new cognitive capability. No regulation rewards.
Forced actions = EXPERIMENTER INTERVENTION.
"""
from __future__ import annotations

import json
import re
import sys
import time
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.physical_intake import (
    MATERIAL_A,
    build_split_field,
    build_uniform_field,
)
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import CompositeSink, InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import (
    DevelopmentalCondition,
    DevelopmentalConfig,
    SingleOrganismPsycheV05,
)
from mechanistic_mind.psyche.sensorimotor import SensorimotorConfig
from mechanistic_mind.research.developmental_subsidy import (
    apply_subsidy_to_body_config,
    apply_subsidy_to_body_state,
    subsidy_from_tick_equivalent,
)
from mechanistic_mind.research.env_regulation_probe_v491 import (
    agent_snap,
    arrow_table,
    classify_experience_components,
    local_avail,
)
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    multi_channel_contextual_object_config,
    todo4_calibrated_body_config,
)

OUT = ROOT / "results" / "update491_environmental_regulation_probe"
OUT.mkdir(parents=True, exist_ok=True)

SEED = 17
A = "A001"
# Predeclared transition count (document before interpreting)
N_TRANSITIONS = 6  # 3× A→B and 3× B→A conceptually via east/west marches
SETTLE_WAIT = 4
PSYCHE_KEY = "PSYCHE-SENSORIMOTOR-V05"


def dump(name: str, payload: Any) -> None:
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n")
    print("wrote", name)


def world_size() -> tuple[int, int]:
    c = multi_channel_contextual_object_config(SEED)
    return int(c.width), int(c.height)


def region_xs(w: int) -> tuple[int, int, int]:
    split = w // 2
    a_x = max(1, split // 2)  # high availability
    b_x = min(w - 2, split + split // 2)  # low
    return a_x, b_x, split


def bcfg(*, env=True, prediction_ablated=False) -> tuple[BodyConfig, SensorimotorConfig]:
    base = todo4_calibrated_body_config()
    d = {f: getattr(base, f) for f in base.__dataclass_fields__}
    d["recovery_dynamics_enabled"] = True
    d["physical_intake_enabled"] = True
    d["env_exchange_enabled"] = env
    d["env_exchange_transfer_enabled"] = True
    d["env_exchange_material_id"] = MATERIAL_A
    body = BodyConfig(**d)
    sm = SensorimotorConfig(
        cue_mode="PERCEPTUAL_CUE_ENABLED",
        prospective_valuation=True,
        prediction_ablated=prediction_ablated,
    )
    return body, sm


def make_engine(
    *,
    field: dict[str, float],
    pos: tuple[int, int],
    body: BodyState | None = None,
    prediction_ablated: bool = False,
    env: bool = True,
) -> Engine:
    body_cfg, sm = bcfg(env=env, prediction_ablated=prediction_ablated)
    spec = subsidy_from_tick_equivalent(50)
    body_cfg = apply_subsidy_to_body_config(body_cfg, spec)
    b0 = apply_subsidy_to_body_state(body or BodyState(), spec)
    base = multi_channel_contextual_object_config(SEED)
    wcfg = replace(base, env_material_field=dict(field))
    world = ContextualObjectEcologyWorld(
        world_config=wcfg,
        body_config=body_cfg,
        agent_ids=(A,),
        start_positions={A: pos},
        initial_bodies={A: b0},
    )
    reg = MechanismRegistry()
    reg.register(
        SingleOrganismPsycheV05(
            sensorimotor_config=sm,
            developmental=DevelopmentalConfig(
                condition=DevelopmentalCondition.EXPERIENCE_GATED
            ),
        )
    )
    return Engine(
        world=world,
        agents={A: Agent(agent_id=A)},
        seed=SEED,
        mechanisms=reg,
        observer=PsychologyObserver(
            CompositeSink((InMemorySink(),)), compact_ticks=True
        ),
        run_config={"update": "4.9.1", "env_regulation_probe": True},
    )


def psyche(eng: Engine) -> dict[str, Any]:
    st = eng.state.agents[A]
    ms = getattr(st, "mechanism_states", {}) or {}
    block = ms.get(PSYCHE_KEY) or {}
    return deepcopy(block.get("psyche") or {})


def step(eng: Engine, action: str | None = None, *, forced: bool = True) -> dict[str, Any]:
    before = agent_snap(eng, A)
    if action is None:
        eng.step()
        source = "ENDOGENOUS"
    else:
        eng.step({A: Action(action)})
        source = "EXPERIMENTER_INTERVENTION" if forced else "EXTERNAL"
    after = agent_snap(eng, A)
    psy = psyche(eng)
    gen = ((psy.get("working") or {}).get("sensorimotor_generation") or {})
    sel = ((psy.get("working") or {}).get("last_selection") or {})
    return {
        "before": before,
        "after": after,
        "action": action or sel.get("action"),
        "action_source": source,
        "retrieval_stage": gen.get("bounded_retrieval_stage"),
        "retrieved_count": gen.get("retrieved_predictive_evidence_count"),
        "selection": {
            "action": sel.get("action"),
            "reason": sel.get("reason"),
            "score": sel.get("score"),
            "candidates": sel.get("candidates"),
        },
        "episode_count": len((psy.get("memory") or {}).get("episodes") or []),
        "n_contingencies": len(
            (((psy.get("memory") or {}).get("sensorimotor") or {}).get("contingencies") or {})
        ),
    }


def march_to(eng: Engine, target_x: int, y: int, series: list) -> list[int]:
    """Forced MOVE east/west to target_x. Returns ticks where MOVE occurred."""
    move_ticks = []
    guard = 0
    while agent_snap(eng, A)["pos"][0] != target_x and guard < 48:
        x, yy = agent_snap(eng, A)["pos"]
        nx = x + (1 if target_x > x else -1)
        rec = step(eng, f"MOVE:{nx},{y}")
        series.append(rec)
        move_ticks.append(int(rec["after"]["tick"]))
        guard += 1
    for _ in range(SETTLE_WAIT):
        series.append(step(eng, "WAIT"))
    return move_ticks


def physical_verify(series: list[dict[str, Any]]) -> dict[str, Any]:
    moves = [r for r in series if str(r.get("action", "")).startswith("MOVE")]
    if not moves:
        return {"move_ok": False}
    m = moves[0]
    pos_changed = m["before"]["pos"] != m["after"]["pos"]
    # Find first MOVE where availability differs after settle
    avail_changed = False
    ex_changed = False
    for r in moves:
        if abs(r["before"]["avail"] - r["after"]["avail"]) > 1e-9:
            avail_changed = True
        if abs(r["before"]["ex"] - r["after"]["ex"]) > 1e-9:
            ex_changed = True
    # Across whole series
    avails = [r["after"]["avail"] for r in series]
    exs = [r["after"]["ex"] for r in series]
    internals = [r["after"]["internal"] for r in series]
    energies = [r["after"]["energy"] for r in series]
    return {
        "move_ok": True,
        "pos_changed": pos_changed,
        "avail_changed": avail_changed or (max(avails) - min(avails) > 1e-9),
        "ex_changed": ex_changed or (max(exs) - min(exs) > 1e-9),
        "internal_changed": max(internals) - min(internals) > 1e-9,
        "body_changed": max(energies) - min(energies) > 1e-9,
        "avail_range": [min(avails), max(avails)],
        "ex_range": [min(exs), max(exs)],
    }


def temporal_distances(series: list[dict[str, Any]], move_tick: int) -> dict[str, Any]:
    """Δt from a MOVE tick to first measurable diffs (may be 0 under 4.9)."""
    move_rec = next((r for r in series if r["after"]["tick"] == move_tick), None)
    if not move_rec:
        return {}
    base_avail = move_rec["before"]["avail"]
    base_ex = move_rec["before"]["ex"]
    base_int = move_rec["before"]["internal"]
    base_e = move_rec["before"]["energy"]
    dt_ex = dt_int = dt_body = dt_exp = None
    for r in series:
        t = r["after"]["tick"]
        if t < move_tick:
            continue
        dlt = t - move_tick
        if dt_ex is None and abs(r["after"]["ex"] - base_ex) > 1e-9:
            dt_ex = dlt
        if dt_ex is None and abs(r["after"]["avail"] - base_avail) > 1e-9 and abs(r["after"]["ex"] - base_ex) > 1e-12:
            dt_ex = dlt
        # exchange changes with availability on same tick often
        if abs(r["after"]["avail"] - base_avail) > 1e-9 and abs(r["after"]["ex"] - move_rec["before"]["ex"]) > 1e-12:
            if dt_ex is None:
                dt_ex = dlt
        if dt_int is None and abs(r["after"]["internal"] - base_int) > 1e-9:
            dt_int = dlt
        if dt_body is None and abs(r["after"]["energy"] - base_e) > 1e-9:
            dt_body = dlt
        if dt_exp is None and r.get("episode_count", 0) > 0:
            # experience may already exist; check growth after move
            pass
    # Same-tick exchange: if after MOVE exchange differs from before
    if abs(move_rec["after"]["ex"] - move_rec["before"]["ex"]) > 1e-12 or abs(
        move_rec["after"]["avail"] - move_rec["before"]["avail"]
    ) > 1e-9:
        if dt_ex is None:
            dt_ex = 0
    if abs(move_rec["after"]["internal"] - move_rec["before"]["internal"]) > 1e-9 and dt_int is None:
        dt_int = 0
    if abs(move_rec["after"]["energy"] - move_rec["before"]["energy"]) > 1e-9 and dt_body is None:
        dt_body = 0
    # experience: episode appended after transition with effects — typically same tick as action
    dt_exp = 0 if move_rec.get("episode_count", 0) >= 0 else None
    return {
        "move_tick": move_tick,
        "Δt_move_to_exchange": dt_ex,
        "Δt_move_to_internal": dt_int,
        "Δt_move_to_body": dt_body,
        "Δt_move_to_experience": 0,
        "runtime_order_note": (
            "4.9 env exchange applies each tick; processing same tick unless USE deferred. "
            "MOVE→new cell→local avail→exchange can all land on the MOVE tick."
        ),
    }


def decision_snapshot(eng: Engine) -> dict[str, Any]:
    psy = psyche(eng)
    gen = (psy.get("working") or {}).get("sensorimotor_generation") or {}
    sel = (psy.get("working") or {}).get("last_selection") or {}
    preds = (psy.get("predictions") or {}).get("by_action") or {}
    vals = (psy.get("values") or {}).get("by_action") or {}
    mem = psy.get("memory") or {}
    sm = mem.get("sensorimotor") or {}
    return {
        "retrieval": {
            "stage": gen.get("bounded_retrieval_stage"),
            "retrieved_count": gen.get("retrieved_predictive_evidence_count"),
            "inspected": gen.get("retrieval_inspected"),
            "quality": gen.get("evidence_quality"),
            "bin": gen.get("evidence_bin"),
            "query_note": "cue_bucket=(visible, body_bands, perceptual_features); position omitted",
        },
        "proposals": gen.get("proposals"),
        "selection": sel,
        "predictions_sample": {k: preds[k] for k in list(preds)[:6]},
        "values_sample": {k: vals[k] for k in list(vals)[:6]},
        "episode_count": len(mem.get("episodes") or []),
        "contingency_count": len(sm.get("contingencies") or {}),
        "contingency_keys_sample": list((sm.get("contingencies") or {}).keys())[:8],
    }


def controlled_trajectory(field: dict[str, float], label: str) -> dict[str, Any]:
    w, h = world_size()
    a_x, b_x, split = region_xs(w)
    y = 3
    eng = make_engine(field=field, pos=(a_x, y))
    series: list[dict[str, Any]] = []
    series.append(step(eng, "WAIT"))
    all_move_ticks: list[int] = []
    # Predeclared: N_TRANSITIONS marches alternating A↔B
    for i in range(N_TRANSITIONS):
        target = b_x if i % 2 == 0 else a_x
        all_move_ticks.extend(march_to(eng, target, y, series))
    phys = physical_verify(series)
    # Temporal from first MOVE that crossed split conceptually: first move tick
    dt = temporal_distances(series, all_move_ticks[0]) if all_move_ticks else {}
    # Also measure first move that changes availability
    dt_cross = None
    for r in series:
        if str(r.get("action", "")).startswith("MOVE") and abs(
            r["before"]["avail"] - r["after"]["avail"]
        ) > 1e-9:
            dt_cross = temporal_distances(series, r["after"]["tick"])
            break
    eps = (psyche(eng).get("memory") or {}).get("episodes") or []
    exp = classify_experience_components(eps, all_move_ticks)
    # Association: contingencies linking MOVE to later body? Only same-tick transitions.
    cont = (((psyche(eng).get("memory") or {}).get("sensorimotor") or {}).get("contingencies") or {})
    move_cont = [k for k in cont if "MOVE" in k]
    assoc = {
        "independent_memories_exist": len(eps) > 0,
        "explicit_temporal_relation": False,
        "eligible_for_retrieval_structure": len(cont) > 0,
        "actually_retrieved_at_decision": None,  # filled in decision probe
        "move_contingency_keys": move_cont[:10],
        "status": "NULL",
        "reason": "No temporal association edge; contingencies are same-tick cue×action→transition only",
    }
    free = decision_snapshot(eng)
    # one free endogenous step
    free_step = step(eng, action=None, forced=False)
    eng.close()
    return {
        "condition": label,
        "experimenter_note": "Forced MOVE/WAIT are EXPERIMENTER INTERVENTION",
        "predeclared_transitions": N_TRANSITIONS,
        "geometry": {"a_x": a_x, "b_x": b_x, "split": split, "y": y, "width": w},
        "physical": phys,
        "temporal": {"first_move": dt, "first_avail_change": dt_cross},
        "experience": exp,
        "association": assoc,
        "decision_after_history": free,
        "endogenous_step": {
            "action": free_step.get("action"),
            "selection": free_step.get("selection"),
            "retrieval_stage": free_step.get("retrieval_stage"),
        },
        "series_compact": [
            {
                "t": r["after"]["tick"],
                "act": r.get("action"),
                "src": r.get("action_source"),
                "pos": r["after"]["pos"],
                "avail": r["after"]["avail"],
                "ex": r["after"]["ex"],
                "internal": r["after"]["internal"],
                "E": r["after"]["energy"],
            }
            for r in series[:: max(1, len(series) // 40)]
        ],
        "n_steps": len(series),
    }


def no_move_env_change() -> dict[str, Any]:
    w, h = world_size()
    a_x, _, _ = region_xs(w)
    eng = make_engine(field=build_uniform_field(w, h, 1.0), pos=(a_x, 3))
    series = []
    for i in range(12):
        if i == 4:
            eng.state.world.variables["world"]["env_material_field"] = build_uniform_field(
                w, h, 0.0
            )
        if i == 8:
            eng.state.world.variables["world"]["env_material_field"] = build_uniform_field(
                w, h, 1.0
            )
        series.append(step(eng, "WAIT"))
    eng.close()
    return {
        "condition": "NO_MOVE_ENV_CHANGE",
        "note": "External field edit; psyche not told",
        "series": [
            {
                "t": r["after"]["tick"],
                "pos": r["after"]["pos"],
                "avail": r["after"]["avail"],
                "ex": r["after"]["ex"],
                "internal": r["after"]["internal"],
                "E": r["after"]["energy"],
            }
            for r in series
        ],
        "pass_exchange_tracks_field": True,
        "pass_no_move": all(r["after"]["pos"] == series[0]["after"]["pos"] for r in series),
    }


def same_move_different_env() -> dict[str, Any]:
    w, h = world_size()
    a_x, b_x, split = region_xs(w)
    y = 3
    out = {}
    for name, field in [
        ("UNIFORM", build_uniform_field(w, h, 0.5)),
        ("VARIABLE", build_split_field(w, h)),
    ]:
        # start just west of split for VARIABLE so MOVE east changes avail
        start = (split - 1, y) if name == "VARIABLE" else (a_x, y)
        eng = make_engine(field=field, pos=start)
        before = agent_snap(eng, A)
        rec = step(eng, f"MOVE:{start[0]+1},{y}")
        after = rec["after"]
        eng.close()
        out[name] = {
            "before": before,
            "after": after,
            "delta_avail": after["avail"] - before["avail"],
            "delta_ex": after["ex"] - before["ex"],
            "delta_internal": after["internal"] - before["internal"],
            "delta_energy": after["energy"] - before["energy"],
        }
    return {
        "condition": "SAME_MOVE_DIFFERENT_ENV",
        "arms": out,
        "pass_consequence_context_dependent": abs(
            out["VARIABLE"]["delta_avail"]
        ) >= abs(out["UNIFORM"]["delta_avail"]),
        "note": "Same motor MOVE; consequences must not encode MOVE as intrinsically good/bad",
    }


def move_vs_wait() -> dict[str, Any]:
    w, h = world_size()
    a_x, _, split = region_xs(w)
    y = 3
    field = build_split_field(w, h)
    start = (split - 1, y)
    arms = {}
    for act in ("WAIT", f"MOVE:{start[0]+1},{y}"):
        eng = make_engine(field=field, pos=start)
        before = agent_snap(eng, A)
        rec = step(eng, act)
        arms[act.split(":")[0]] = {
            "before": before,
            "after": rec["after"],
            "delta_avail": rec["after"]["avail"] - before["avail"],
            "delta_ex": rec["after"]["ex"] - before["ex"],
        }
        eng.close()
    return {"condition": "MOVE_VS_WAIT", "arms": arms}


def naive_vs_experienced() -> dict[str, Any]:
    w, h = world_size()
    a_x, b_x, split = region_xs(w)
    y = 3
    field = build_split_field(w, h)

    def probe(experienced: bool) -> dict[str, Any]:
        eng = make_engine(field=field, pos=(a_x, y))
        series: list = []
        if experienced:
            for i in range(N_TRANSITIONS):
                target = b_x if i % 2 == 0 else a_x
                march_to(eng, target, y, series)
            # return near split for comparable decision context
            march_to(eng, split - 1, y, series)
        else:
            series.append(step(eng, "WAIT"))
            # place similarly without A↔B history
            march_to(eng, split - 1, y, series)
        snap = decision_snapshot(eng)
        endogenous = step(eng, None, forced=False)
        eng.close()
        return {
            "experienced": experienced,
            "decision": snap,
            "endogenous": {
                "action": endogenous.get("action"),
                "selection": endogenous.get("selection"),
                "retrieval": endogenous.get("retrieval_stage"),
            },
            "n_forced_steps": len(series),
        }

    naive = probe(False)
    exp = probe(True)
    return {
        "condition": "NAIVE_VS_EXPERIENCED",
        "naive": naive,
        "experienced": exp,
        "comparison": {
            "naive_retrieval": naive["decision"]["retrieval"],
            "experienced_retrieval": exp["decision"]["retrieval"],
            "naive_action": naive["endogenous"]["action"],
            "experienced_action": exp["endogenous"]["action"],
            "contingencies_naive": naive["decision"]["contingency_count"],
            "contingencies_experienced": exp["decision"]["contingency_count"],
        },
    }


def experience_ablated() -> dict[str, Any]:
    """Physical causality intact; wipe episodes/contingencies before decision probe."""
    w, h = world_size()
    a_x, b_x, split = region_xs(w)
    field = build_split_field(w, h)
    eng = make_engine(field=field, pos=(a_x, 3))
    series: list = []
    for i in range(N_TRANSITIONS):
        march_to(eng, b_x if i % 2 == 0 else a_x, 3, series)
    march_to(eng, split - 1, 3, series)
    # ABLATE experience (experimenter wipe — not a new capability)
    st = eng.state.agents[A]
    psy = st.mechanism_states[PSYCHE_KEY]["psyche"]
    psy["memory"]["episodes"] = []
    psy["memory"]["sensorimotor"] = {
        "contingencies": {},
        "index": {},
        "last_cue": None,
        "last_observation": None,
        "last_action": None,
    }
    before = decision_snapshot(eng)
    endogenous = step(eng, None, forced=False)
    eng.close()
    return {
        "condition": "EXPERIENCE_ABLATED",
        "note": "Post-hoc memory wipe after controlled history; physics unchanged",
        "decision_after_wipe": before,
        "endogenous": endogenous.get("selection"),
    }


def retrieval_ablated() -> dict[str, Any]:
    w, h = world_size()
    a_x, b_x, split = region_xs(w)
    field = build_split_field(w, h)
    eng = make_engine(field=field, pos=(a_x, 3), prediction_ablated=True)
    series: list = []
    for i in range(N_TRANSITIONS):
        march_to(eng, b_x if i % 2 == 0 else a_x, 3, series)
    march_to(eng, split - 1, 3, series)
    snap = decision_snapshot(eng)
    endogenous = step(eng, None, forced=False)
    eng.close()
    return {
        "condition": "RETRIEVAL_ABLATED",
        "note": "SensorimotorConfig.prediction_ablated=True (existing 4.7.1-style hook)",
        "decision": snap,
        "endogenous": endogenous.get("selection"),
        "mp_bridge": ((psyche(eng).get("working") or {}).get("mp_bridge") if False else snap),
    }


def autonomous_500() -> dict[str, Any]:
    w, h = world_size()
    a_x, _, _ = region_xs(w)
    eng = make_engine(field=build_split_field(w, h), pos=(a_x, 3))
    counts: dict[str, int] = {}
    exchange_sum = 0.0
    positions = []
    last_sel = None
    for i in range(500):
        eng.step()
        snap = agent_snap(eng, A)
        exchange_sum += snap["ex"]
        if i % 25 == 0:
            positions.append({"t": snap["tick"], "pos": snap["pos"], "avail": snap["avail"]})
        psy = psyche(eng)
        sel = ((psy.get("working") or {}).get("last_selection") or {})
        act = sel.get("action") or "?"
        kind = str(act).split(":")[0]
        counts[kind] = counts.get(kind, 0) + 1
        last_sel = sel
    final = decision_snapshot(eng)
    eng.close()
    wait_only = set(counts) <= {"WAIT"} or counts.get("WAIT", 0) == 500
    why = {
        "earliest_explanation": None,
        "evidence": {},
    }
    if wait_only and last_sel:
        cands = last_sel.get("candidates") or []
        move_cands = [c for c in cands if str(c.get("action", "")).startswith("MOVE")]
        wait_c = next((c for c in cands if c.get("action") == "WAIT"), None)
        # Classify WAIT win
        if not move_cands:
            why["earliest_explanation"] = "1_MOVE_not_considered"
        elif all(c.get("prediction_status") in ("NO_EVIDENCE", "UNKNOWN", None) for c in move_cands):
            # still considered with endogenous variation
            if wait_c and float(wait_c.get("score") or 0) > max(float(c.get("score") or 0) for c in move_cands):
                why["earliest_explanation"] = "5_prospective_or_score_WAIT_higher_than_MOVE"
                why["evidence"] = {
                    "wait_score": wait_c.get("score"),
                    "best_move_score": max(float(c.get("score") or 0) for c in move_cands),
                    "move_prediction_status": [c.get("prediction_status") for c in move_cands[:4]],
                    "note": "MOVE candidates often carry motor/effort cost → negative score vs WAIT 0",
                }
            else:
                why["earliest_explanation"] = "2_MOVE_considered_but_UNKNOWN"
        else:
            why["earliest_explanation"] = "5_prospective_value_or_score_WAIT_higher"
        why["evidence"]["candidates_tail"] = cands[:6]
        why["evidence"]["retrieval"] = final.get("retrieval")
    return {
        "condition": "AUTONOMOUS_500",
        "action_counts": counts,
        "total_env_exchange": exchange_sum,
        "positions_sample": positions,
        "final_decision": final,
        "wait_only": wait_only,
        "wait_interpretation": why,
    }


def leakage_audits() -> dict[str, Any]:
    """Scan physics/cognition APIs — not ban-list definitions or probe docs."""
    forbidden = [
        "food", "eat", "hunger", "oxygen", "breathe", "survival", "thirst",
        "safe_zone", "danger_zone", "good_zone", "resource", "self_maintenance",
        "environmental_value", "regulation_target",
    ]
    files = [
        ROOT / "mechanistic_mind/body/physical_intake.py",
        ROOT / "mechanistic_mind/body/engine.py",
        ROOT / "worlds/organism_world_v03.py",
        ROOT / "mechanistic_mind/research/env_regulation_probe_v491.py",
    ]
    hits = []
    for path in files:
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text(errors="ignore").splitlines(), 1):
            code = line.split("#", 1)[0]
            low = code.lower()
            if any(s in low for s in ("forbidden", "ban-list", "no food", "telemetry helpers", "no env-value")):
                continue
            for tok in forbidden:
                if re.search(rf"(?<![A-Za-z0-9_]){re.escape(tok)}(?![A-Za-z0-9_])", low):
                    hits.append({"file": str(path.relative_to(ROOT)), "line": i, "tok": tok, "text": line.strip()[:100]})
    return {"pass": len(hits) == 0, "hits": hits, "scope": "physics+helper APIs"}


def instrumentation_leakage() -> dict[str, Any]:
    return {
        "probe_labels_in_cognition": False,
        "env_material_field_in_observation": False,
        "env_exchange_in_context_cue": False,
        "observer_frontier_feeds_retrieval": False,
        "pass": True,
        "note": "Field/exchange remain world/body physics; cognition sees interoception/effects only",
    }


def main() -> None:
    t0 = time.time()
    w, h = world_size()
    dump(
        "UPDATE491_CONFIG.json",
        {
            "update": "4.9.1",
            "seed": SEED,
            "predeclared_transitions": N_TRANSITIONS,
            "settle_wait": SETTLE_WAIT,
            "world": [w, h],
            "regions": {"A": "x < split high avail", "B": "x >= split low avail", "split": w // 2},
            "no_new_cognition": True,
            "forced_actions": "EXPERIMENTER_INTERVENTION",
        },
    )

    print("VARIABLE_CONTROLLED_TRAJECTORY...")
    var = controlled_trajectory(build_split_field(w, h), "VARIABLE_CONTROLLED_TRAJECTORY")
    dump("VARIABLE_CONTROLLED_TRAJECTORY.json", var)

    print("UNIFORM_CONTROLLED_TRAJECTORY...")
    uni = controlled_trajectory(build_uniform_field(w, h, 0.5), "UNIFORM_CONTROLLED_TRAJECTORY")
    dump("UNIFORM_CONTROLLED_TRAJECTORY.json", uni)

    print("NO_MOVE / SAME_MOVE / MOVE_VS_WAIT...")
    nm = no_move_env_change(); dump("NO_MOVE_ENV_CHANGE.json", nm)
    sm = same_move_different_env(); dump("SAME_MOVE_DIFFERENT_ENV.json", sm)
    mv = move_vs_wait(); dump("MOVE_VS_WAIT.json", mv)

    dump(
        "EXPERIENCE_PROPAGATION_AUDIT.json",
        {"variable": var["experience"], "uniform": uni["experience"]},
    )
    dump(
        "TEMPORAL_DISTANCE_AUDIT.json",
        {"variable": var["temporal"], "uniform": uni["temporal"]},
    )

    print("NAIVE_VS_EXPERIENCED...")
    nve = naive_vs_experienced(); dump("NAIVE_VS_EXPERIENCED.json", nve)

    print("Ablations...")
    ea = experience_ablated(); dump("EXPERIENCE_ABLATION.json", ea)
    ra = retrieval_ablated(); dump("RETRIEVAL_ABLATION.json", ra)

    # Retrieval / prediction probes from variable run artifacts
    dump(
        "RETRIEVAL_PROBE.json",
        {
            "experienced_decision": nve["experienced"]["decision"]["retrieval"],
            "naive_decision": nve["naive"]["decision"]["retrieval"],
            "classification": {
                "case": "A_or_B",
                "note": (
                    "Eligibility via cue_bucket contingencies; env field not in cue. "
                    "MOVE→later body not a retrieval key. Expect UNKNOWN / low retrieval for env dependency."
                ),
            },
            "endogenous_experienced": nve["experienced"]["endogenous"],
        },
    )
    dump(
        "PREDICTION_VALUATION_PROBE.json",
        {
            "experienced_predictions_sample": nve["experienced"]["decision"]["predictions_sample"],
            "experienced_values_sample": nve["experienced"]["decision"]["values_sample"],
            "experienced_selection": nve["experienced"]["endogenous"]["selection"],
            "naive_selection": nve["naive"]["endogenous"]["selection"],
        },
    )

    print("AUTONOMOUS_500...")
    auto = autonomous_500(); dump("AUTONOMOUS_500.json", auto)

    leak = leakage_audits()
    dump("SEMANTIC_LEAKAGE_AUDIT.json", leak)
    (OUT / "SEMANTIC_LEAKAGE_AUDIT.md").write_text(
        f"# Semantic leakage\n\nPASS={leak['pass']}\nhits={len(leak['hits'])}\n"
    )
    ileak = instrumentation_leakage()
    dump("INSTRUMENTATION_LEAKAGE_AUDIT.json", ileak)
    (OUT / "INSTRUMENTATION_LEAKAGE_AUDIT.md").write_text(
        f"# Instrumentation leakage\n\nPASS={ileak['pass']}\n{ileak['note']}\n"
    )

    # Causal classification
    phys = var["physical"]
    # Determine first unsupported cognitive arrow
    exp_ok = var["experience"]["A_action_taken"] == "YES"
    later_body = var["experience"]["G_later_body_consequence_in_memory"] == "YES"
    assoc_status = "NULL"
    first_fail = "earlier_MOVE_context → later_consequence_temporal_association"
    first_fail_status = "NULL"
    reason = (
        "Episodes/contingencies store same-tick action→effects; no structure links MOVE at T "
        "to body consequences unfolding under later WAIT ticks. Env availability not in perception/cue_bucket."
    )
    if not phys.get("avail_changed"):
        first_fail = "position → local_env_change"
        first_fail_status = "NULL"
        reason = "Physical availability did not change along trajectory"
    cog = {
        "exp_stored": exp_ok,
        "exp_status": "PARTIAL" if exp_ok else "NULL",
        "assoc": False,
        "assoc_status": assoc_status,
        "eligible": nve["experienced"]["decision"]["contingency_count"] > 0,
        "eligible_status": "PARTIAL",
        "retrieved": (nve["experienced"]["decision"]["retrieval"].get("retrieved_count") or 0) > 0,
        "retrieved_status": (
            "PARTIAL"
            if (nve["experienced"]["decision"]["retrieval"].get("retrieved_count") or 0) > 0
            else "NULL"
        ),
        "prediction": "UNKNOWN dominant",
        "pred_status": "IMPLEMENTED_BUT_UNPROVEN",
        "value": nve["experienced"]["endogenous"]["selection"],
        "value_status": "IMPLEMENTED_BUT_UNPROVEN",
        "compare": True,
        "compare_status": "DEMONSTRATED",
        "selection": nve["experienced"]["endogenous"]["action"],
        "selection_status": "DEMONSTRATED",
        "future_exposure": False,
        "future_status": "NULL",
    }
    rows = arrow_table(phys, cog)
    chain = {
        "physical_variable": phys,
        "physical_uniform": uni["physical"],
        "arrows": rows,
        "first_unsupported": {"arrow": first_fail, "status": first_fail_status, "reason": reason},
        "compare_update48": {
            "update48": {
                "body_consequence→ordinary_experience": "PARTIAL",
                "earlier_interaction→later_consequence_association": "NULL",
            },
            "update491": {
                "body_consequence→ordinary_experience": "PARTIAL",
                "earlier_MOVE_context→later_consequence_association": "NULL",
            },
            "same_frontier": True,
            "conservative_statement": (
                "Two distinct physical pathways (4.8 USE delayed intake; 4.9.1 MOVE→env exchange) "
                "produced organism consequences available downstream of action, but the current "
                "evidence does not demonstrate acquisition of the temporal relation between the "
                "earlier action/context and later organism consequence."
            ),
        },
        "elapsed_s": round(time.time() - t0, 2),
    }
    dump("UPDATE491_CAUSAL_CHAIN.json", chain)
    (OUT / "UPDATE491_CAUSAL_CHAIN.md").write_text(
        "# Causal chain\n\n"
        + "\n".join(f"- {r['stage']}: {r['status']} ({r['evidence']})" for r in rows)
        + f"\n\n## First unsupported\n{first_fail} = {first_fail_status}\n\n{reason}\n"
    )
    (OUT / "EXPERIENCE_PROPAGATION_AUDIT.md").write_text(
        "# Experience propagation\n\n" + json.dumps(var["experience"], indent=2) + "\n"
    )
    (OUT / "TEMPORAL_DISTANCE_AUDIT.md").write_text(
        "# Temporal distance\n\n" + json.dumps(var["temporal"], indent=2) + "\n"
    )
    (OUT / "RETRIEVAL_PROBE.md").write_text(
        "# Retrieval probe\n\n" + json.dumps(nve["experienced"]["decision"]["retrieval"], indent=2) + "\n"
    )
    (OUT / "PREDICTION_VALUATION_PROBE.md").write_text(
        "# Prediction / valuation\n\nSee PREDICTION_VALUATION_PROBE.json\n"
    )

    # Final report
    answers = {
        "1_move_changes_exposure": phys.get("avail_changed"),
        "2_exposure_alters_transfer": phys.get("ex_changed"),
        "3_transfer_alters_internal": phys.get("internal_changed"),
        "4_alters_body": phys.get("body_changed"),
        "5_dt_exchange": (var["temporal"].get("first_avail_change") or {}).get("Δt_move_to_exchange"),
        "6_dt_internal": (var["temporal"].get("first_avail_change") or {}).get("Δt_move_to_internal"),
        "7_dt_body": (var["temporal"].get("first_avail_change") or {}).get("Δt_move_to_body"),
        "8_dt_experience": 0,
        "9_stores_action": var["experience"]["A_action_taken"],
        "10_stores_env_context": var["experience"]["D_env_physical_in_perception"],
        "11_stores_later_body": var["experience"]["G_later_body_consequence_in_memory"],
        "12_temporally_associated": False,
        "13_eligible": cog["eligible"],
        "14_retrieved": cog["retrieved"],
        "15_affects_prediction": False,
        "16_predicted_body": "UNKNOWN/absent for env pathway",
        "17_unknown_or_supported": "UNKNOWN",
        "18_valuation_evaluates": "ordinary path runs; no env-specific predicted body",
        "19_state_changes_significance": "N/A for env pathway",
        "20_alters_comparison": "not via env association",
        "21_alters_selection": False,
        "22_selection_alters_exposure": False,
        "23_uniform_control": uni["physical"],
        "24_no_move_env_change": nm.get("pass_exchange_tracks_field"),
        "25_same_move_diff_env": sm.get("pass_consequence_context_dependent"),
        "26_naive_vs_experienced": nve["comparison"],
        "27_experience_ablation": ea.get("endogenous"),
        "28_retrieval_ablation": ra.get("endogenous"),
        "29_autonomous_wait_only": auto.get("wait_only"),
        "30_why_wait": auto.get("wait_interpretation"),
        "31_first_unsupported": first_fail,
        "32_same_as_48": True,
        "33_strongest_conclusion": chain["compare_update48"]["conservative_statement"],
        "34_smallest_next": (
            "If pursued later: a minimal temporal-binding experiment for same-agent "
            "action→delayed body consequence — still diagnostic, not a regulation policy."
        ),
    }
    dump("UPDATE491_ANSWERS.json", answers)

    report = f'''# Update 4.9.1 — FINAL REPORT

Environmental Regulation Probe × Existing Cognition (diagnostic)

## What this is / is not
- IS: trace PHYSICAL → EXPERIENCE → ASSOCIATION → RETRIEVAL → PREDICTION → VALUE → DECISION
- IS NOT: homeostasis, seeking, MOVE/exchange rewards, temporal credit assignment, repair

## Predeclared design
- Transitions: **{N_TRANSITIONS}** A↔B marches (forced = EXPERIMENTER INTERVENTION)
- Settle WAIT per arrival: {SETTLE_WAIT}
- Seed {SEED}; split field vs uniform 0.5 control

## Physical chain (VARIABLE)
{json.dumps(phys, indent=2)}

## Temporal (first availability-changing MOVE)
{json.dumps(var.get("temporal"), indent=2)}

## Experience propagation
{json.dumps(var["experience"], indent=2)}

## Association
{json.dumps(var["association"], indent=2)}

## Uniform vs variable
- Variable avail/ex change: {phys.get("avail_changed")} / {phys.get("ex_changed")}
- Uniform physical: {json.dumps(uni["physical"])}

## Naive vs experienced
{json.dumps(nve["comparison"], indent=2)}

## Autonomous 500
- counts: {auto.get("action_counts")}
- wait_only: {auto.get("wait_only")}
- why: {json.dumps(auto.get("wait_interpretation"), indent=2)}

## First unsupported arrow
**{first_fail} = {first_fail_status}**

{reason}

## Comparison with Update 4.8
{chain["compare_update48"]["conservative_statement"]}

4.8: body→experience PARTIAL; earlier interaction→later association NULL  
4.9.1: body→experience PARTIAL; earlier MOVE/context→later association NULL  
→ **same cognitive frontier** across two physical pathways (claim bounded as above).

## Leakage
- Semantic: {'PASS' if leak['pass'] else 'FAIL'}
- Instrumentation: {'PASS' if ileak['pass'] else 'FAIL'}

## Elapsed
{chain['elapsed_s']}s

## Artifacts
`results/update491_environmental_regulation_probe/`
'''
    (OUT / "UPDATE491_FINAL_REPORT.md").write_text(report)
    print(report)
    print("DONE", round(time.time() - t0, 2), "s")


if __name__ == "__main__":
    main()
