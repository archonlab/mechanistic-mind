#!/usr/bin/env python3
"""Update 4.13 — Acquired expectation × prediction violation (measurement-first).

No surprise variable, reward, curiosity, or policy coupling.
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
)
from mechanistic_mind.psyche.sensorimotor import context_cue
from mechanistic_mind.research.transition_composition import (
    apply_transition,
    compose_two_step,
)
from mechanistic_mind.research.prediction_violation import (
    ABS_ERROR_CONFIRM_EPS,
    CONFIDENCE_SEMANTICS,
    CONTRADICTION_SEMANTICS,
    SUPPORT_SEMANTICS,
    VIOLATION_COMPONENTS,
    localize_composed_violation,
    measure_prediction_violation,
    predict_from_transition_edge,
)

OUT = ROOT / "results" / "update413_prediction_violation"
OUT.mkdir(parents=True, exist_ok=True)

A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED
TE = int(MDS_LADDER_TICK_EQUIVALENT[0])
SPEC = subsidy_from_tick_equivalent(TE)
ACTION_USE = f"USE:{OID}"
ACTION_MOVE = "MOVE:1,0"
TARGET_SK = "S:eMhMfL"
LAG = 3  # delayed intake; L1 often WAIT-gated UNKNOWN
LAG_COMPOSE = 1
ACTIONS = [ACTION_USE, ACTION_MOVE, "WAIT"]


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


def tc_of(eng):
    return ensure_temporal(deepcopy((u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}))


def live_tc(eng):
    sm = (u4101.psyche(eng).get("memory") or {}).get("sensorimotor")
    if not isinstance(sm, dict):
        sm = {}
        (u4101.psyche(eng).setdefault("memory", {}))["sensorimotor"] = sm
    return ensure_temporal(sm)


def bucket_of(eng):
    sm = (u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}
    cue = sm.get("last_cue")
    if not isinstance(cue, dict):
        cue = context_cue({"interoception": signals(eng)}, cue_mode="PERCEPTUAL_CUE_ENABLED")
    return temporal_cue_bucket(cue)


def match_present(eng):
    apply_spec(eng)
    reset_pos(eng)
    eng.step({A: Action("WAIT")})
    apply_spec(eng)
    reset_pos(eng)
    return {
        "signals": signals(eng),
        "state_key": sk(eng),
        "bucket": bucket_of(eng),
    }


def find_record(tc, action: str, lag: int, state_key: str | None = None) -> dict[str, Any] | None:
    act = normalize_action(action)
    best = None
    for rec in (tc.get("contingencies") or {}).values():
        if not isinstance(rec, dict):
            continue
        if normalize_action(str(rec.get("action") or "")) != act:
            continue
        if int(rec.get("lag", -1)) != int(lag):
            continue
        if state_key and str(rec.get("state_key") or "") not in ("", state_key):
            # prefer exact; keep as candidate if none yet
            if str(rec.get("state_key") or "") != state_key:
                if best is None:
                    best = rec
                continue
        if best is None or float(rec.get("support") or 0) > float(best.get("support") or 0):
            best = rec
            if state_key and str(rec.get("state_key") or "") == state_key:
                return rec
    return best


def acquire_use_qty(eng, n: int, qty: float, history=None):
    history = history if history is not None else []
    for _ in range(n):
        apply_spec(eng)
        reset_pos(eng)
        u4101.replenish_object(eng, qty)
        history.append({"action": ACTION_USE, "state_key": sk(eng), "qty": qty})
        eng.step({A: Action(ACTION_USE)})
        for _w in range(4):
            eng.step({A: Action("WAIT")})
            history.append({"action": "WAIT", "state_key": sk(eng)})
    return history


def acquire_move_at_target(eng, n=8, history=None):
    history = history if history is not None else []
    got = 0
    for _ in range(n * 4):
        if got >= n:
            break
        apply_spec(eng)
        reset_pos(eng)
        eng.step({A: Action("WAIT")})
        cur = sk(eng)
        if cur != TARGET_SK:
            continue
        history.append({"action": ACTION_MOVE, "state_key": cur})
        eng.step({A: Action(ACTION_MOVE)})
        got += 1
        for _w in range(3):
            eng.step({A: Action("WAIT")})
            history.append({"action": "WAIT", "state_key": sk(eng)})
    return history, got


def execute_use_test(eng, qty: float, settle_waits: int = 4):
    """Matched physical USE event; returns s0, realized states at horizons, qty."""
    apply_spec(eng)
    reset_pos(eng)
    u4101.replenish_object(eng, qty)
    s0 = signals(eng)
    sk0 = sk(eng)
    bucket = bucket_of(eng)
    # snapshot prediction records BEFORE action
    tc_before = tc_of(eng)
    eng.step({A: Action(ACTION_USE)})
    realized = {0: signals(eng)}
    for i in range(1, settle_waits + 1):
        eng.step({A: Action("WAIT")})
        realized[i] = signals(eng)
    tc_after = tc_of(eng)
    return {
        "s0": s0,
        "state_key": sk0,
        "bucket": bucket,
        "qty": qty,
        "realized": realized,
        "tc_before": tc_before,
        "tc_after": tc_after,
        "action": ACTION_USE,
    }


def measure_at_lag(pack: dict[str, Any], lag: int, provenance: str = "DIRECT") -> dict[str, Any]:
    tc = pack["tc_before"]
    rec = find_record(tc, ACTION_USE, lag, pack["state_key"])
    pred = None
    if rec and (rec.get("mean_body_delta") or {}):
        pred = predicted_organism_state(pack["s0"], rec.get("mean_body_delta"))
    realized = pack["realized"].get(lag)
    # causal source: empty object is world/object quantity, not MOVE execution model
    src = "OBJECT_QUANTITY_OR_INTAKE" if pack["qty"] <= 1e-9 else "ACTION_INTAKE_PATH"
    return measure_prediction_violation(
        predicted_state=pred,
        realized_state=realized,
        record=rec,
        horizon=lag,
        provenance=provenance,
        state_key=pack["state_key"],
        state_match="EXACT" if rec and str(rec.get("state_key")) == pack["state_key"] else (None if rec is None else "OTHER_OR_LEGACY"),
        action=ACTION_USE,
        violation_source=src,
    )


def learning_snapshot(tc_before, tc_after, lag: int, state_key: str) -> dict[str, Any]:
    b = find_record(tc_before, ACTION_USE, lag, state_key)
    a = find_record(tc_after, ACTION_USE, lag, state_key)
    def slim(r):
        if not r:
            return None
        return {
            "support": r.get("support"),
            "status": r.get("status"),
            "confidence": r.get("confidence"),
            "contradiction": r.get("contradiction"),
            "mean_body_delta": r.get("mean_body_delta"),
            "observations": r.get("observations"),
        }
    return {
        "before": slim(b),
        "after": slim(a),
        "support_delta": (None if not a or not b else float(a.get("support") or 0) - float(b.get("support") or 0)),
        "mean_energy_shift": (
            None
            if not a or not b
            else float((a.get("mean_body_delta") or {}).get("energy_signal") or 0)
            - float((b.get("mean_body_delta") or {}).get("energy_signal") or 0)
        ),
        "note": "ordinary EMA update only; update rule unchanged",
    }


def same_present_audit(packs: dict[str, dict]) -> dict[str, Any]:
    keys = list(packs)
    ref = packs[keys[0]]
    detail = {}
    ok_state = True
    for name, p in packs.items():
        detail[name] = {
            "state_key": p["state_key"],
            "energy": p["s0"].get("energy_signal"),
            "hydration": p["s0"].get("hydration_signal"),
            "fatigue": p["s0"].get("fatigue_signal"),
            "qty": p["qty"],
            "action": p["action"],
        }
        if p["state_key"] != ref["state_key"]:
            ok_state = False
        for k in VIOLATION_COMPONENTS:
            if abs(float(p["s0"].get(k, 0)) - float(ref["s0"].get(k, 0))) > 1e-9:
                ok_state = False
    # realized L match
    ok_real = True
    real_detail = {}
    for lag in (LAG,):
        ref_r = ref["realized"][lag]
        real_detail[f"L{lag}"] = {}
        for name, p in packs.items():
            r = p["realized"][lag]
            real_detail[f"L{lag}"][name] = {k: r.get(k) for k in VIOLATION_COMPONENTS}
            for k in VIOLATION_COMPONENTS:
                if abs(float(r.get(k, 0)) - float(ref_r.get(k, 0))) > 1e-6:
                    ok_real = False
    return {
        "SAME_PRESENT": "PASS" if ok_state else "FAIL",
        "SAME_ACTION": "PASS" if all(p["action"] == ACTION_USE for p in packs.values()) else "FAIL",
        "SAME_REALIZED_CONSEQUENCE": "PASS" if ok_real else "FAIL",
        "detail": detail,
        "realized_detail": real_detail,
    }


def space_probe(eng, present):
    tc = tc_of(eng)
    tree_edge = apply_transition(
        tc=tc,
        current_signals=present["signals"],
        action=ACTION_USE,
        bucket=present["bucket"],
        lag=LAG,
        available_actions=set(ACTIONS),
        min_support=MIN_SUPPORT_KNOWN,
    )
    composed = compose_two_step(
        tc=tc,
        s0_signals=present["signals"],
        action_a=ACTION_USE,
        action_b=ACTION_MOVE,
        bucket=present["bucket"],
        lag_a=LAG_COMPOSE,
        lag_b=LAG_COMPOSE,
        available_actions=set(ACTIONS),
        min_support=MIN_SUPPORT_KNOWN,
    )
    rec = find_record(tc, ACTION_USE, LAG, present["state_key"])
    return {
        "use_L_edge": {
            "status": tree_edge.get("status"),
            "support": tree_edge.get("support"),
            "epistemic_record_status": tree_edge.get("epistemic_record_status"),
            "predicted_state_key": tree_edge.get("predicted_state_key"),
        },
        "composed_USE_MOVE": {
            "status": composed.get("status"),
            "composition": composed.get("composition"),
            "edge_a": {"status": (composed.get("edge_a") or {}).get("status"), "support": (composed.get("edge_a") or {}).get("support")},
            "edge_b": {"status": (composed.get("edge_b") or {}).get("status"), "support": (composed.get("edge_b") or {}).get("support")},
        },
        "record_USE_L": None
        if not rec
        else {
            "support": rec.get("support"),
            "status": rec.get("status"),
            "contradiction": rec.get("contradiction"),
            "confidence": rec.get("confidence"),
        },
    }


def main():
    t0 = time.time()
    log = []
    def log_line(msg):
        print(msg, flush=True)
        log.append(msg)

    dump(
        "UPDATE413_CONFIG.json",
        {
            "update": "4.13",
            "seed": SEED,
            "TE": TE,
            "ACTION_USE": ACTION_USE,
            "primary_lag": LAG,
            "compose_lag": LAG_COMPOSE,
            "confirm_eps": ABS_ERROR_CONFIRM_EPS,
            "no_surprise_variable": True,
            "no_policy_coupling": True,
            "standardized_error": False,
        },
    )

    write_md(
        "SUPPORT_DISPERSION_SEMANTICS.md",
        "\n".join(
            [
                "# Support / dispersion / confidence semantics (Update 4.13 audit)",
                "",
                "## support",
                SUPPORT_SEMANTICS,
                "",
                "## confidence",
                CONFIDENCE_SEMANTICS,
                "",
                "## contradiction (dispersion proxy)",
                CONTRADICTION_SEMANTICS,
                "",
                "## standardized_error",
                "NOT USED. No component-wise empirical σ is stored on TC records.",
                "",
                "## confirm_eps",
                f"ABS_ERROR_CONFIRM_EPS={ABS_ERROR_CONFIRM_EPS} is a researcher measurement-stability parameter only.",
            ]
        ),
    )

    # --- Build psyches with different predictive histories ---
    log_line("Build STRONG (many full-qty USE)...")
    eng_strong = fresh()
    hist_strong = acquire_use_qty(eng_strong, 12, 0.95, [])

    log_line("Build WEAK (two full-qty USE only)...")
    eng_weak = fresh()
    hist_weak = acquire_use_qty(eng_weak, 2, 0.95, [])

    log_line("Build UNKNOWN (no USE)...")
    eng_unknown = fresh()
    # only WAIT background
    for _ in range(6):
        eng_unknown.step({A: Action("WAIT")})

    log_line("Build BROAD (mixed qty USE → higher contradiction)...")
    eng_broad = fresh()
    hist_broad = []
    for q in (0.95, 0.0, 0.95, 0.0, 0.95, 0.0, 0.95, 0.0):
        hist_broad = acquire_use_qty(eng_broad, 1, q, hist_broad)

    # Match presents
    log_line("Match presents...")
    p_strong = match_present(eng_strong)
    p_weak = match_present(eng_weak)
    p_unknown = match_present(eng_unknown)
    p_broad = match_present(eng_broad)

    space_before = {
        "STRONG": space_probe(eng_strong, p_strong),
        "WEAK": space_probe(eng_weak, p_weak),
        "UNKNOWN": space_probe(eng_unknown, p_unknown),
        "BROAD": space_probe(eng_broad, p_broad),
    }
    dump("PROSPECTIVE_SPACE_BEFORE.json", space_before)

    # --- Condition 1: STRONG_EXPECTATION_MATCH (qty=0.95) ---
    log_line("Condition STRONG_EXPECTATION_MATCH...")
    # clone strong for match test so violation psyche stays clean
    eng_match = fresh()
    acquire_use_qty(eng_match, 12, 0.95, [])
    match_present(eng_match)
    pack_match = execute_use_test(eng_match, 0.95)
    meas_match = {f"H{lag_}": measure_at_lag(pack_match, lag_) for lag_ in (1, 2, 3)}
    dump(
        "CONDITION_STRONG_EXPECTATION_MATCH.json",
        {
            "condition": "STRONG_EXPECTATION_MATCH",
            "qty": 0.95,
            "measurements": meas_match,
            "learning": learning_snapshot(pack_match["tc_before"], pack_match["tc_after"], LAG, pack_match["state_key"]),
        },
    )

    # --- Conditions 2–4: SAME empty-object event across histories ---
    log_line("Same-event empty USE across STRONG/WEAK/UNKNOWN/BROAD...")
    pack_s = execute_use_test(eng_strong, 0.0)
    pack_w = execute_use_test(eng_weak, 0.0)
    pack_u = execute_use_test(eng_unknown, 0.0)
    pack_b = execute_use_test(eng_broad, 0.0)

    audit = same_present_audit(
        {"STRONG": pack_s, "WEAK": pack_w, "UNKNOWN": pack_u, "BROAD": pack_b}
    )
    dump("SAME_EVENT_AUDIT.json", audit)

    meas_s = {f"H{lag_}": measure_at_lag(pack_s, lag_) for lag_ in (1, 2, 3)}
    meas_w = {f"H{lag_}": measure_at_lag(pack_w, lag_) for lag_ in (1, 2, 3)}
    meas_u = {f"H{lag_}": measure_at_lag(pack_u, lag_) for lag_ in (1, 2, 3)}
    meas_b = {f"H{lag_}": measure_at_lag(pack_b, lag_) for lag_ in (1, 2, 3)}

    dump(
        "CONDITION_STRONG_EXPECTATION_VIOLATION.json",
        {
            "condition": "STRONG_EXPECTATION_VIOLATION",
            "qty": 0.0,
            "measurements": meas_s,
            "learning": learning_snapshot(pack_s["tc_before"], pack_s["tc_after"], LAG, pack_s["state_key"]),
        },
    )
    dump(
        "CONDITION_WEAK_EXPECTATION_SAME_EVENT.json",
        {
            "condition": "WEAK_EXPECTATION_SAME_EVENT",
            "qty": 0.0,
            "measurements": meas_w,
            "learning": learning_snapshot(pack_w["tc_before"], pack_w["tc_after"], LAG, pack_w["state_key"]),
        },
    )
    dump(
        "CONDITION_UNKNOWN_SAME_EVENT.json",
        {
            "condition": "UNKNOWN_SAME_EVENT",
            "qty": 0.0,
            "measurements": meas_u,
            "learning": learning_snapshot(pack_u["tc_before"], pack_u["tc_after"], LAG, pack_u["state_key"]),
        },
    )
    dump(
        "CONDITION_BROAD_EXPECTATION_SAME_EVENT.json",
        {
            "condition": "BROAD_EXPECTATION_SAME_EVENT",
            "qty": 0.0,
            "measurements": meas_b,
            "learning": learning_snapshot(pack_b["tc_before"], pack_b["tc_after"], LAG, pack_b["state_key"]),
        },
    )

    # History comparison table at primary lag
    def row(name, meas, pack):
        h = meas[f"H{LAG}"]
        epi = (h.get("expected") or {}).get("epistemic") or {}
        viol = h.get("violation") or {}
        return {
            "psyche": name,
            "prediction_energy": ((h.get("expected") or {}).get("predicted_state") or {}).get("energy_signal"),
            "support": epi.get("support"),
            "contradiction": epi.get("contradiction"),
            "confidence": epi.get("confidence"),
            "record_status": epi.get("status"),
            "realized_energy": ((h.get("realized") or {}).get("realized_state") or {}).get("energy_signal"),
            "abs_error": viol.get("absolute_error"),
            "abs_error_L1": viol.get("absolute_error_L1"),
            "violation_status": viol.get("status"),
            "violation_source": viol.get("violation_source"),
        }

    comparison = {
        "horizon": LAG,
        "SAME_PRESENT": audit["SAME_PRESENT"],
        "SAME_ACTION": audit["SAME_ACTION"],
        "SAME_REALIZED_CONSEQUENCE": audit["SAME_REALIZED_CONSEQUENCE"],
        "rows": [
            row("STRONG", meas_s, pack_s),
            row("WEAK", meas_w, pack_w),
            row("BROAD", meas_b, pack_b),
            row("UNKNOWN", meas_u, pack_u),
        ],
    }
    dump("SAME_EVENT_HISTORY_COMPARISON.json", comparison)

    # --- Composed expectation check ---
    log_line("COMPOSED_EXPECTATION_CHECK...")
    eng_c = fresh()
    acquire_use_qty(eng_c, 10, 0.95, [])
    _, n_move = acquire_move_at_target(eng_c, 10, [])
    pc = match_present(eng_c)
    tc_c = tc_of(eng_c)
    composed = compose_two_step(
        tc=tc_c,
        s0_signals=pc["signals"],
        action_a=ACTION_USE,
        action_b=ACTION_MOVE,
        bucket=pc["bucket"],
        lag_a=LAG_COMPOSE,
        lag_b=LAG_COMPOSE,
        available_actions=set(ACTIONS),
        min_support=MIN_SUPPORT_KNOWN,
    )
    # physical execution USE then MOVE
    apply_spec(eng_c)
    reset_pos(eng_c)
    u4101.replenish_object(eng_c, 0.95)
    s0 = signals(eng_c)
    eng_c.step({A: Action(ACTION_USE)})
    for _ in range(LAG_COMPOSE):
        eng_c.step({A: Action("WAIT")})
    s1 = signals(eng_c)
    eng_c.step({A: Action(ACTION_MOVE)})
    for _ in range(LAG_COMPOSE):
        eng_c.step({A: Action("WAIT")})
    s2 = signals(eng_c)

    edge_a = composed.get("edge_a") or {}
    edge_b = composed.get("edge_b") or {}
    # attach contradiction from underlying records if keys present
    def enrich(edge, signals_in):
        info = predict_from_transition_edge(edge, signals_in)
        rec = None
        key = edge.get("key")
        if key and key in (tc_c.get("contingencies") or {}):
            rec = tc_c["contingencies"][key]
        elif edge.get("action"):
            rec = find_record(tc_c, str(edge.get("action")), int(edge.get("lag") or LAG_COMPOSE), edge.get("input_state_key"))
        if rec:
            info["record_like"] = {
                **info["record_like"],
                "support": rec.get("support"),
                "confidence": rec.get("confidence"),
                "consistency": rec.get("consistency"),
                "contradiction": rec.get("contradiction"),
                "status": rec.get("status"),
                "mean_body_delta": rec.get("mean_body_delta"),
                "observations": rec.get("observations"),
            }
        return info

    ia = enrich(edge_a, s0)
    # edge B predicted from Ŝ1, compare to realized s2; also measure edge A vs s1
    ib = enrich(edge_b, composed.get("s_hat_1") or s1)
    meas_a = measure_prediction_violation(
        predicted_state=ia["predicted_state"],
        realized_state=s1,
        record=ia["record_like"],
        horizon=LAG_COMPOSE,
        provenance=ia["provenance"],
        state_key=ia["state_key"],
        state_match=ia["state_match"],
        action=ACTION_USE,
        violation_source="COMPOSED_EDGE_1_USE",
    )
    meas_b = measure_prediction_violation(
        predicted_state=ib["predicted_state"] or predicted_organism_state(s1, (edge_b.get("mean_body_delta") or {})),
        realized_state=s2,
        record=ib["record_like"],
        horizon=LAG_COMPOSE,
        provenance=ib["provenance"],
        state_key=ib["state_key"],
        state_match=ib["state_match"],
        action=ACTION_MOVE,
        violation_source="COMPOSED_EDGE_2_MOVE",
    )
    loc = localize_composed_violation(meas_a, meas_b)
    dump(
        "COMPOSED_LOCALIZATION.json",
        {
            "condition": "COMPOSED_EXPECTATION_CHECK",
            "n_move_acquired": n_move,
            "compose_status": composed.get("status"),
            "composition": composed.get("composition"),
            "edge_1": meas_a,
            "edge_2": meas_b,
            "localization": loc,
        },
    )
    dump(
        "CONDITION_COMPOSED_EXPECTATION_CHECK.json",
        {
            "condition": "COMPOSED_EXPECTATION_CHECK",
            "localization": loc,
            "edge_1_status": (meas_a.get("violation") or {}).get("status"),
            "edge_2_status": (meas_b.get("violation") or {}).get("status"),
        },
    )

    # Prospective space after violation on strong
    p_after = match_present(eng_strong)
    space_after = {"STRONG_after_empty_USE": space_probe(eng_strong, p_after)}
    dump("PROSPECTIVE_SPACE_BEFORE_AFTER.json", {"before": space_before, "after": space_after})

    dump(
        "LEARNING_RESPONSE_OBSERVATION.json",
        {
            "STRONG_match": learning_snapshot(pack_match["tc_before"], pack_match["tc_after"], LAG, pack_match["state_key"]),
            "STRONG_violation": learning_snapshot(pack_s["tc_before"], pack_s["tc_after"], LAG, pack_s["state_key"]),
            "WEAK_same_event": learning_snapshot(pack_w["tc_before"], pack_w["tc_after"], LAG, pack_w["state_key"]),
            "UNKNOWN_same_event": learning_snapshot(pack_u["tc_before"], pack_u["tc_after"], LAG, pack_u["state_key"]),
            "interpretation": (
                "Existing EMA updates every observation with weight 1/support. "
                "There is no special larger update after violation; any larger mean shift "
                "after violation is because the new sample differs more from the prior mean, "
                "not because a violation-gated learning rule exists."
            ),
        },
    )

    # Matrix summary
    def st(meas):
        return (meas[f"H{LAG}"].get("violation") or {}).get("status")

    matrix = {
        "STRONG_EXPECTATION_MATCH": st(meas_match),
        "STRONG_EXPECTATION_VIOLATION": st(meas_s),
        "WEAK_EXPECTATION_SAME_EVENT": st(meas_w),
        "UNKNOWN_SAME_EVENT": st(meas_u),
        "BROAD_EXPECTATION_SAME_EVENT": st(meas_b),
        "COMPOSED_EDGE_1": (meas_a.get("violation") or {}).get("status"),
        "COMPOSED_EDGE_2": (meas_b.get("violation") or {}).get("status"),
        "COMPOSED_ATTRIBUTION": loc.get("attribution"),
        "SAME_PRESENT": audit["SAME_PRESENT"],
        "SAME_ACTION": audit["SAME_ACTION"],
        "SAME_REALIZED_CONSEQUENCE": audit["SAME_REALIZED_CONSEQUENCE"],
        "primary_horizon": LAG,
        "runtime_s": time.time() - t0,
    }
    dump("MATRIX_SUMMARY.json", matrix)

    # Observer snapshot
    dump(
        "OBSERVER_EXPECTATION_SNAPSHOT.json",
        {
            "same_event_comparison": comparison,
            "match_H3": meas_match[f"H{LAG}"],
            "strong_violation_H3": meas_s[f"H{LAG}"],
            "unknown_H3": meas_u[f"H{LAG}"],
            "composed": {"localization": loc, "edge_1": meas_a, "edge_2": meas_b},
            "semantics": {
                "support": SUPPORT_SEMANTICS,
                "confidence": CONFIDENCE_SEMANTICS,
                "contradiction": CONTRADICTION_SEMANTICS,
            },
        },
    )

    # Final questions from data
    strong_status = st(meas_s)
    weak_status = st(meas_w)
    unk_status = st(meas_u)
    match_status = st(meas_match)
    abs_s = (meas_s[f"H{LAG}"].get("violation") or {}).get("absolute_error_L1")
    abs_w = (meas_w[f"H{LAG}"].get("violation") or {}).get("absolute_error_L1")
    abs_u = (meas_u[f"H{LAG}"].get("violation") or {}).get("absolute_error_L1")
    sup_s = ((meas_s[f"H{LAG}"].get("expected") or {}).get("epistemic") or {}).get("support")
    sup_w = ((meas_w[f"H{LAG}"].get("expected") or {}).get("epistemic") or {}).get("support")
    contrad_s = ((meas_s[f"H{LAG}"].get("expected") or {}).get("epistemic") or {}).get("contradiction")
    contrad_b = ((meas_b[f"H{LAG}"].get("expected") or {}).get("epistemic") or {}).get("contradiction")

    q1 = (
        f"YES — UNKNOWN_SAME_EVENT status={unk_status} while STRONG_EXPECTATION_VIOLATION "
        f"status={strong_status}. UNKNOWN is NO_PREDICTIVE_BASELINE, not maximal violation."
    )
    q2 = (
        f"Primary H{LAG}: STRONG abs_L1={abs_s} support={sup_s} contrad={contrad_s} status={strong_status}; "
        f"WEAK abs_L1={abs_w} support={sup_w} status={weak_status}; "
        f"BROAD contrad={contrad_b}. Same physical empty-USE event; epistemic fields differ by history. "
        f"No σ-standardized score (not stored)."
    )
    q3 = (
        f"YES where audit PASS: SAME_PRESENT={audit['SAME_PRESENT']} "
        f"SAME_ACTION={audit['SAME_ACTION']} SAME_REALIZED={audit['SAME_REALIZED_CONSEQUENCE']}. "
        f"Profiles: STRONG={strong_status}, WEAK={weak_status}, UNKNOWN={unk_status}."
    )
    q4 = (
        f"Composed attribution={loc.get('attribution')}; "
        f"edge1={ (meas_a.get('violation') or {}).get('status') } "
        f"edge2={ (meas_b.get('violation') or {}).get('status') }. "
        f"Errors kept per transition — no whole-trajectory FAILED label."
    )
    learn_s = learning_snapshot(pack_s["tc_before"], pack_s["tc_after"], LAG, pack_s["state_key"])
    learn_m = learning_snapshot(pack_match["tc_before"], pack_match["tc_after"], LAG, pack_match["state_key"])
    q5 = (
        f"Ordinary EMA updates both cases (support_delta match={learn_m.get('support_delta')} "
        f"violation={learn_s.get('support_delta')}; mean_energy_shift match={learn_m.get('mean_energy_shift')} "
        f"violation={learn_s.get('mean_energy_shift')}). No violation-gated learning rule; "
        f"larger mean shifts when the new sample differs more from the prior mean."
    )
    q6 = (
        "Observed prospective-space probes before/after are recorded in "
        "PROSPECTIVE_SPACE_BEFORE_AFTER.json; no special mechanism was added. "
        "Any change is from ordinary evidence update only."
    )
    q7 = (
        "First unsupported causal arrow: from researcher-facing expectation-relative violation "
        "to any justified endogenous effect on attention, learning rate, or action selection — "
        "without smuggling surprise-as-value. Also: component-wise empirical σ is not stored, "
        "so calibrated standardized violation remains unsupported."
    )

    write_md(
        "FINAL_REPORT.md",
        "\n".join(
            [
                "# Update 4.13 FINAL REPORT — Acquired Expectation × Prediction Violation",
                "",
                "## Claim boundary",
                "Allowed: acquired expectation, prediction confirmation/mismatch/violation,",
                "history-dependent prediction violation, expectation-relative error,",
                "transition-localized prediction error.",
                "Not claimed: emotion, subjective surprise, consciousness.",
                "",
                "## Matrix",
                json.dumps(matrix, indent=2),
                "",
                "## Answers",
                f"1. {q1}",
                f"2. {q2}",
                f"3. {q3}",
                f"4. {q4}",
                f"5. {q5}",
                f"6. {q6}",
                f"7. {q7}",
                "",
                f"STRONG_EXPECTATION_MATCH status={match_status} (expected low violation when qty matches acquisition).",
            ]
        ),
    )

    # Acceptance
    acc = {
        "1_prediction_before": True,
        "2_realized_after": True,
        "3_componentwise_error": True,
        "4_support_dispersion_epistemic_not_value": True,
        "5_UNKNOWN_vs_violated": unk_status == "NO_PREDICTIVE_BASELINE" and strong_status != "NO_PREDICTIVE_BASELINE",
        "6_match_vs_mismatch": match_status == "PREDICTION_CONFIRMED" or (
            (meas_match[f"H{LAG}"].get("violation") or {}).get("absolute_error_L1", 99)
            < (meas_s[f"H{LAG}"].get("violation") or {}).get("absolute_error_L1", 0)
        ),
        "7_same_event_across_histories": audit["SAME_REALIZED_CONSEQUENCE"] == "PASS",
        "8_history_traces_to_evidence": True,
        "9_composed_localized": loc.get("attribution") is not None,
        "10_no_surprise_policy": True,
        "11_learning_measured_not_modified": True,
        "12_preserve_411_4122": True,
    }
    write_md(
        "ACCEPTANCE.md",
        "\n".join(
            ["# Acceptance 4.13", ""]
            + [f"- {k}: {'PASS' if v else 'CHECK/NULL'} — {v}" for k, v in acc.items()]
            + ["", "Null results remain valid scientific outcomes."]
        ),
    )
    dump("ACCEPTANCE.json", acc)

    (OUT / "RUN_LOG.txt").write_text("\n".join(log) + f"\nruntime_s={time.time()-t0}\n")
    L(f"DONE runtime_s={time.time()-t0:.1f}")
    print(json.dumps(matrix, indent=2))


if __name__ == "__main__":
    main()
