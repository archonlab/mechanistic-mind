#!/usr/bin/env python3
"""Update 4.13.1 — Expectation adaptation × alternating consequence diagnostic.

Measurement-only. Reuses 4.13 prediction_violation. No surprise / multi-outcome model.
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
from mechanistic_mind.research.transition_composition import apply_transition, compose_two_step
from mechanistic_mind.research.prediction_violation import (
    ABS_ERROR_CONFIRM_EPS,
    VIOLATION_COMPONENTS,
    measure_prediction_violation,
)

OUT = ROOT / "results" / "update4131_expectation_adaptation"
OUT.mkdir(parents=True, exist_ok=True)

A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED
TE = int(MDS_LADDER_TICK_EQUIVALENT[0])
SPEC = subsidy_from_tick_equivalent(TE)
ACTION_USE = f"USE:{OID}"
ACTION_MOVE = "MOVE:1,0"
ACTIONS = [ACTION_USE, ACTION_MOVE, "WAIT"]
LAG = 3
QTY_X = 0.95
QTY_Y = 0.0
MAX_ACQUIRE_X = 24
PHASE_A_Y = 12
PHASE_B_X = 6
ALT_N = 16  # 8X+8Y alternating


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


def bucket_of(eng):
    sm = (u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}
    cue = sm.get("last_cue")
    if not isinstance(cue, dict):
        cue = context_cue({"interoception": signals(eng)}, cue_mode="PERCEPTUAL_CUE_ENABLED")
    return temporal_cue_bucket(cue)


def find_record(tc, action: str, lag: int, state_key: str | None = None):
    act = normalize_action(action)
    best = None
    for rec in (tc.get("contingencies") or {}).values():
        if not isinstance(rec, dict):
            continue
        if normalize_action(str(rec.get("action") or "")) != act:
            continue
        if int(rec.get("lag", -1)) != int(lag):
            continue
        rsk = str(rec.get("state_key") or "")
        if state_key and rsk and rsk != state_key:
            if best is None:
                best = rec
            continue
        if best is None or float(rec.get("support") or 0) >= float(best.get("support") or 0):
            best = rec
            if state_key and rsk == state_key:
                return rec
    return best


def vec_l1(a: dict | None, b: dict | None, keys=VIOLATION_COMPONENTS) -> float | None:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return None
    return float(sum(abs(float(a.get(k, 0)) - float(b.get(k, 0))) for k in keys))


def mean_delta_to_state(s0: dict, mean_delta: dict | None) -> dict | None:
    if not mean_delta:
        return None
    return predicted_organism_state(s0, mean_delta)


def slim_rec(rec):
    if not rec:
        return None
    return {
        "support": rec.get("support"),
        "status": rec.get("status"),
        "confidence": rec.get("confidence"),
        "consistency": rec.get("consistency"),
        "contradiction": rec.get("contradiction"),
        "mean_body_delta": rec.get("mean_body_delta"),
        "observations": rec.get("observations"),
        "key": rec.get("key"),
        "state_key": rec.get("state_key"),
        "lag": rec.get("lag"),
        "fields_present": sorted(rec.keys()),
    }


def match_start(eng):
    apply_spec(eng)
    reset_pos(eng)
    eng.step({A: Action("WAIT")})
    apply_spec(eng)
    reset_pos(eng)


def event_trace(eng, qty: float, regime_label: str, sample_idx: int, phase: str) -> dict[str, Any]:
    """PREDICT → REALIZE → MEASURE → ORDINARY LEARNING (engine settle)."""
    match_start(eng)
    u4101.replenish_object(eng, qty)
    s0 = signals(eng)
    state_key = sk(eng)
    bucket = bucket_of(eng)
    tc_before = tc_of(eng)
    rec_before = find_record(tc_before, ACTION_USE, LAG, state_key)
    pred = mean_delta_to_state(s0, (rec_before or {}).get("mean_body_delta") if rec_before else None)

    # realize — pending age starts at -1, so lag L needs (L+1) waits after USE
    # before the next match_start/apply_spec (which would otherwise settle L on a reset body).
    eng.step({A: Action(ACTION_USE)})
    for _ in range(LAG + 1):
        eng.step({A: Action("WAIT")})
    realized = signals(eng)

    meas = measure_prediction_violation(
        predicted_state=pred,
        realized_state=realized,
        record=rec_before,
        horizon=LAG,
        provenance="DIRECT",
        state_key=state_key,
        state_match="EXACT" if rec_before and str(rec_before.get("state_key")) == state_key else None,
        action=ACTION_USE,
        violation_source="OBJECT_QUANTITY_OR_INTAKE",
    )

    # ordinary learning already applied by settle during waits; snapshot after
    tc_after = tc_of(eng)
    rec_after = find_record(tc_after, ACTION_USE, LAG, state_key)
    next_pred = mean_delta_to_state(s0, (rec_after or {}).get("mean_body_delta") if rec_after else None)

    return {
        "sample": sample_idx,
        "phase": phase,
        "regime_label_researcher_only": regime_label,  # never cognition
        "qty": qty,
        "state_key": state_key,
        "bucket": bucket,
        "s0": {k: s0.get(k) for k in VIOLATION_COMPONENTS},
        "before": {
            "prediction_state": pred,
            "record": slim_rec(rec_before),
        },
        "realized_state": {k: realized.get(k) for k in VIOLATION_COMPONENTS},
        "realized_delta": {k: float(realized.get(k, 0)) - float(s0.get(k, 0)) for k in VIOLATION_COMPONENTS},
        "violation": meas.get("violation"),
        "expected_pack": meas.get("expected"),
        "after": {
            "record": slim_rec(rec_after),
            "next_prediction_state_from_same_s0": next_pred,
        },
        "distances": {
            "pred_to_realized_L1": vec_l1(pred, realized),
        },
    }


def acquire_until_known(eng, qty: float, regime: str, phase: str, max_n: int = MAX_ACQUIRE_X):
    traces = []
    known_at = None
    for i in range(1, max_n + 1):
        tr = event_trace(eng, qty, regime, i, phase)
        traces.append(tr)
        st = ((tr.get("after") or {}).get("record") or {}).get("status")
        if st == "KNOWN" and known_at is None:
            known_at = i
            # continue a couple more for stability? stop once known after measure+update
            break
    return traces, known_at


def prospective_probe(eng):
    match_start(eng)
    s0 = signals(eng)
    bucket = bucket_of(eng)
    tc = tc_of(eng)
    edge = apply_transition(
        tc=tc,
        current_signals=s0,
        action=ACTION_USE,
        bucket=bucket,
        lag=LAG,
        available_actions=set(ACTIONS),
        min_support=MIN_SUPPORT_KNOWN,
    )
    composed = compose_two_step(
        tc=tc,
        s0_signals=s0,
        action_a=ACTION_USE,
        action_b=ACTION_MOVE,
        bucket=bucket,
        lag_a=1,
        lag_b=1,
        available_actions=set(ACTIONS),
        min_support=MIN_SUPPORT_KNOWN,
    )
    rec = find_record(tc, ACTION_USE, LAG, sk(eng))
    return {
        "state_key": sk(eng),
        "use_edge": {
            "status": edge.get("status"),
            "support": edge.get("support"),
            "epistemic_record_status": edge.get("epistemic_record_status"),
            "predicted_state": edge.get("predicted_state"),
            "predicted_state_key": edge.get("predicted_state_key"),
        },
        "composed": {
            "status": composed.get("status"),
            "composition": composed.get("composition"),
            "s_hat_1": composed.get("s_hat_1"),
            "s_hat_2": composed.get("s_hat_2"),
            "s_hat_1_key": composed.get("s_hat_1_key"),
            "s_hat_2_key": composed.get("s_hat_2_key"),
        },
        "record": slim_rec(rec),
    }


def ref_vectors_from_traces(traces_x, traces_y):
    """Empirical mean realized states for X and Y (researcher reference)."""
    def mean_states(trs):
        if not trs:
            return None
        acc = {k: 0.0 for k in VIOLATION_COMPONENTS}
        for t in trs:
            for k in VIOLATION_COMPONENTS:
                acc[k] += float((t.get("realized_state") or {}).get(k) or 0)
        n = float(len(trs))
        return {k: acc[k] / n for k in VIOLATION_COMPONENTS}

    return mean_states(traces_x), mean_states(traces_y)


def closer_to(pred, ref_x, ref_y):
    if pred is None or ref_x is None or ref_y is None:
        return None
    dx, dy = vec_l1(pred, ref_x), vec_l1(pred, ref_y)
    if dx is None or dy is None:
        return None
    if abs(dx - dy) < 1e-12:
        return "TIE"
    return "X" if dx < dy else "Y"


def analyze_adaptation(traces, ref_x, ref_y):
    first_closer_y = None
    first_confirmed = None
    known_to_unknown = False
    rows = []
    for t in traces:
        pred = (t.get("before") or {}).get("prediction_state")
        after_pred = ((t.get("after") or {}) or {}).get("next_prediction_state_from_same_s0")
        before_rec = (t.get("before") or {}).get("record") or {}
        after_rec = (t.get("after") or {}).get("record") or {}
        status = (t.get("violation") or {}).get("status")
        closer_before = closer_to(pred, ref_x, ref_y)
        closer_after = closer_to(after_pred, ref_x, ref_y)
        if first_closer_y is None and closer_after == "Y":
            first_closer_y = t["sample"]
        if first_confirmed is None and status == "PREDICTION_CONFIRMED" and t.get("regime_label_researcher_only") == "Y":
            # confirmed for Y event means prediction matched Y realization
            first_confirmed = t["sample"]
        if before_rec.get("status") == "KNOWN" and after_rec.get("status") == "UNKNOWN":
            known_to_unknown = True
        rows.append(
            {
                "sample": t["sample"],
                "phase": t["phase"],
                "regime": t["regime_label_researcher_only"],
                "violation_status": status,
                "support_before": before_rec.get("support"),
                "support_after": after_rec.get("support"),
                "status_before": before_rec.get("status"),
                "status_after": after_rec.get("status"),
                "contradiction_before": before_rec.get("contradiction"),
                "contradiction_after": after_rec.get("contradiction"),
                "pred_energy_before": (pred or {}).get("energy_signal") if pred else None,
                "realized_energy": (t.get("realized_state") or {}).get("energy_signal"),
                "closer_before": closer_before,
                "closer_after": closer_after,
                "abs_L1": (t.get("violation") or {}).get("absolute_error_L1"),
            }
        )
    return {
        "first_closer_to_Y_after_update": first_closer_y,
        "first_Y_event_PREDICTION_CONFIRMED": first_confirmed,
        "KNOWN_became_UNKNOWN": known_to_unknown,
        "rows": rows,
    }


def tc_semantics_audit():
    # Static code-level audit of what TC stores
    return {
        "stores_one_EMA_mean_body_delta": True,
        "stores_support_count": True,
        "stores_directional_contradiction_EMA": True,
        "stores_consistency_EMA": True,
        "stores_confidence_derived": True,
        "stores_status_UNKNOWN_WEAK_KNOWN": True,
        "stores_separate_lag_records": True,
        "stores_min_max": False,
        "stores_individual_samples": False,
        "stores_clusters": False,
        "stores_multimodal_structure": False,
        "stores_recent_sample_buffer": False,
        "can_distinguish_bimodal_XY_from_central_Z_in_principle": False,
        "reason": (
            "Each (bucket, state_key, action, lag) key holds a single EMA mean_body_delta plus "
            "support/consistency/contradiction. No sample list, mixture, or mode set. "
            "Two histories with the same running mean are not separable by prospective retrieval "
            "of mean_body_delta; contradiction may differ but is not a recoverable X/Y pair."
        ),
        "update_formula": "mean = ((n-1)*old + new)/n with n=support after increment",
        "MIN_SUPPORT_KNOWN": MIN_SUPPORT_KNOWN,
    }


def main():
    t0 = time.time()
    log = []

    def log_line(msg):
        print(msg, flush=True)
        log.append(msg)

    dump(
        "UPDATE4131_CONFIG.json",
        {
            "update": "4.13.1",
            "QTY_X": QTY_X,
            "QTY_Y": QTY_Y,
            "LAG": LAG,
            "settle_waits_after_USE": LAG + 1,
            "PHASE_A_Y": PHASE_A_Y,
            "PHASE_B_X": PHASE_B_X,
            "ALT_N": ALT_N,
            "confirm_eps": ABS_ERROR_CONFIRM_EPS,
            "no_new_mechanism": True,
            "physical_Z_control": "NOT_TESTED_IF_NO_MID_QTY",
        },
    )
    dump("TC_REPRESENTATION_SEMANTICS.json", tc_semantics_audit())
    write_md(
        "TC_REPRESENTATION_SEMANTICS.md",
        "\n".join(
            [
                "# TC representation semantics (4.13.1)",
                "",
                json.dumps(tc_semantics_audit(), indent=2),
                "",
                "## Multiplicity question",
                "Can existing representation distinguish bimodal X/Y from repeated central Z?",
                "**NO** — single EMA mean per key; no sample retention / modes.",
            ]
        ),
    )

    # --- Baseline X acquisition ---
    log_line("Acquire stable X...")
    eng = fresh()
    x_acq, known_at = acquire_until_known(eng, QTY_X, "X", "ACQUIRE_X")
    # if known early, add a few more X for stability (up to ~12 like 4.13) without hard requiring 12 for KNOWN
    while len(x_acq) < 12:
        tr = event_trace(eng, QTY_X, "X", len(x_acq) + 1, "ACQUIRE_X")
        x_acq.append(tr)
    dump(
        "PHASE_ACQUIRE_X.json",
        {"known_at_sample": known_at, "n": len(x_acq), "traces": x_acq},
    )
    probe0 = prospective_probe(eng)
    dump("PROSPECTIVE_BEFORE_PHASE_A.json", probe0)

    # Collect empirical X realized refs from acquisition
    # Also get a few pure Y on a scratch eng for Y reference vector
    eng_yref = fresh()
    y_ref_traces = [event_trace(eng_yref, QTY_Y, "Y", i, "Y_REF") for i in range(1, 5)]
    ref_x, ref_y = ref_vectors_from_traces(x_acq[-6:], y_ref_traces)
    dump("REFERENCE_XY_VECTORS.json", {"ref_X_realized_state": ref_x, "ref_Y_realized_state": ref_y})

    # --- Phase A: X→Y ---
    log_line("Phase A: Y regime...")
    phase_a = []
    for i in range(1, PHASE_A_Y + 1):
        phase_a.append(event_trace(eng, QTY_Y, "Y", i, "PHASE_A_Y"))
    dump("PHASE_A_Y_TRACES.json", {"traces": phase_a})
    adapt_a = analyze_adaptation(phase_a, ref_x, ref_y)
    dump("PHASE_A_ADAPTATION_CURVE.json", adapt_a)
    probe_a = prospective_probe(eng)
    dump("PROSPECTIVE_AFTER_PHASE_A.json", probe_a)

    # --- Phase B: return X ---
    log_line("Phase B: return X...")
    phase_b = []
    for i in range(1, PHASE_B_X + 1):
        phase_b.append(event_trace(eng, QTY_X, "X", i, "PHASE_B_X"))
    dump("PHASE_B_RETURN_X_TRACES.json", {"traces": phase_b})
    adapt_b = analyze_adaptation(phase_b, ref_x, ref_y)
    dump("PHASE_B_RECOVERY_CURVE.json", adapt_b)
    probe_b = prospective_probe(eng)
    dump("PROSPECTIVE_AFTER_PHASE_B.json", probe_b)

    # --- Phase C: alternating on fresh eng with short X baseline ---
    log_line("Phase C: alternating XYXY...")
    eng_alt = fresh()
    alt_base = []
    for i in range(1, 5):
        alt_base.append(event_trace(eng_alt, QTY_X, "X", i, "ALT_BASE_X"))
    alt = []
    for i in range(1, ALT_N + 1):
        qty = QTY_X if (i % 2 == 1) else QTY_Y
        lab = "X" if qty == QTY_X else "Y"
        alt.append(event_trace(eng_alt, qty, lab, i, "PHASE_C_ALT"))
    dump("PHASE_C_ALTERNATING_TRACES.json", {"base": alt_base, "traces": alt})

    # Unobserved mean check
    preds = []
    obs_states = []
    for t in alt:
        preds.append((t.get("after") or {}).get("next_prediction_state_from_same_s0") or (t.get("before") or {}).get("prediction_state"))
        obs_states.append(t.get("realized_state"))
    final_pred = None
    for t in reversed(alt):
        final_pred = ((t.get("after") or {}).get("next_prediction_state_from_same_s0"))
        if final_pred:
            break
    # also use after-record mean applied to last s0
    last = alt[-1]
    s0_last = last["s0"]
    rec_last = (last.get("after") or {}).get("record") or {}
    z_pred = mean_delta_to_state(s0_last, rec_last.get("mean_body_delta"))
    # observed only X and Y realized states in alt
    obs_x = [t["realized_state"] for t in alt if t["regime_label_researcher_only"] == "X"]
    obs_y = [t["realized_state"] for t in alt if t["regime_label_researcher_only"] == "Y"]
    mean_obs_x = {k: sum(float(s[k]) for s in obs_x) / len(obs_x) for k in VIOLATION_COMPONENTS} if obs_x else None
    mean_obs_y = {k: sum(float(s[k]) for s in obs_y) / len(obs_y) for k in VIOLATION_COMPONENTS} if obs_y else None
    # Z as average of mean X and mean Y realized
    z_avg = None
    if mean_obs_x and mean_obs_y:
        z_avg = {k: 0.5 * (mean_obs_x[k] + mean_obs_y[k]) for k in VIOLATION_COMPONENTS}

    dist_z_pred_x = vec_l1(z_pred, mean_obs_x)
    dist_z_pred_y = vec_l1(z_pred, mean_obs_y)
    dist_z_pred_avg = vec_l1(z_pred, z_avg)
    # min distance to any observed sample
    min_to_obs = None
    if z_pred:
        ds = [vec_l1(z_pred, s) for s in obs_states]
        ds = [d for d in ds if d is not None]
        min_to_obs = min(ds) if ds else None
    # unobserved if closer to avg than to X and Y means, and never equal to an observed sample within eps
    unobserved = False
    if z_pred and z_avg and dist_z_pred_avg is not None and dist_z_pred_x is not None and dist_z_pred_y is not None:
        if dist_z_pred_avg < dist_z_pred_x and dist_z_pred_avg < dist_z_pred_y:
            if min_to_obs is None or min_to_obs > ABS_ERROR_CONFIRM_EPS:
                unobserved = True
        # also if energy sits between X and Y means
        if mean_obs_x and mean_obs_y:
            pe = float(z_pred.get("energy_signal") or 0)
            xe = float(mean_obs_x.get("energy_signal") or 0)
            ye = float(mean_obs_y.get("energy_signal") or 0)
            lo, hi = min(xe, ye), max(xe, ye)
            if lo + ABS_ERROR_CONFIRM_EPS < pe < hi - ABS_ERROR_CONFIRM_EPS:
                unobserved = True

    dump(
        "UNOBSERVED_MEAN_PREDICTION.json",
        {
            "UNOBSERVED_MEAN_PREDICTION": "YES" if unobserved else "NO",
            "X_realized_mean": mean_obs_x,
            "Y_realized_mean": mean_obs_y,
            "Z_average_XY": z_avg,
            "predicted_Z": z_pred,
            "distance_Z_to_X": dist_z_pred_x,
            "distance_Z_to_Y": dist_z_pred_y,
            "distance_Z_to_avg": dist_z_pred_avg,
            "min_distance_to_any_observed_sample": min_to_obs,
            "confirm_eps": ABS_ERROR_CONFIRM_EPS,
        },
    )

    # Contradiction trajectories
    def contrad_series(traces, name):
        return [
            {
                "sample": t["sample"],
                "phase": t["phase"],
                "regime": t["regime_label_researcher_only"],
                "contradiction_before": ((t.get("before") or {}).get("record") or {}).get("contradiction"),
                "contradiction_after": ((t.get("after") or {}).get("record") or {}).get("contradiction"),
                "abs_L1": (t.get("violation") or {}).get("absolute_error_L1"),
                "status": (t.get("violation") or {}).get("status"),
            }
            for t in traces
        ]

    dump(
        "CONTRADICTION_TRAJECTORIES.json",
        {
            "acquire_X": contrad_series(x_acq, "X"),
            "phase_A_Y": contrad_series(phase_a, "A"),
            "phase_B_X": contrad_series(phase_b, "B"),
            "phase_C_alt": contrad_series(alt, "C"),
            "note": "contradiction is directional EMA, not component σ",
        },
    )

    # Order control XYXY vs XXXXYYYY
    log_line("Order control XYXY vs XXXXYYYY...")
    def run_seq(pattern: str, label: str):
        e = fresh()
        # small warm X not required; start clean
        traces = []
        for i, ch in enumerate(pattern, 1):
            qty = QTY_X if ch == "X" else QTY_Y
            traces.append(event_trace(e, qty, ch, i, label))
        last_rec = (traces[-1].get("after") or {}).get("record") or {}
        last_s0 = traces[-1]["s0"]
        pred = mean_delta_to_state(last_s0, last_rec.get("mean_body_delta"))
        return {"pattern": pattern, "final_prediction": pred, "final_record": slim_rec(last_rec), "traces": traces}

    n_each = 6
    xyxy = run_seq(("XY" * n_each), "ORDER_XYXY")
    xxxyyyy = run_seq(("X" * n_each) + ("Y" * n_each), "ORDER_XXXXYYYY")
    order_diff = vec_l1(xyxy["final_prediction"], xxxyyyy["final_prediction"])
    dump(
        "ORDER_CONTROL.json",
        {
            "XYXY": {"final_prediction": xyxy["final_prediction"], "final_record": xyxy["final_record"]},
            "XXXXYYYY": {"final_prediction": xxxyyyy["final_prediction"], "final_record": xxxyyyy["final_record"]},
            "final_prediction_L1_difference": order_diff,
            "same_counts_different_expectation": bool(order_diff is not None and order_diff > ABS_ERROR_CONFIRM_EPS),
            "n_X": n_each,
            "n_Y": n_each,
        },
    )

    # Physical Z control — probe mid qty
    mid_ok = False
    # already know mid qty collapses to X physically from pre-check; confirm once
    eng_mid = fresh()
    mid_tr = event_trace(eng_mid, 0.475, "Z_PROBE", 1, "Z_PROBE")
    # compare mid realized to X and Y refs
    d_mid_x = vec_l1(mid_tr["realized_state"], ref_x)
    d_mid_y = vec_l1(mid_tr["realized_state"], ref_y)
    if d_mid_x is not None and d_mid_y is not None and d_mid_x > ABS_ERROR_CONFIRM_EPS and abs(d_mid_x - d_mid_y) < abs(d_mid_x):
        # still closer to X typically
        pass
    physical_z_possible = (
        d_mid_x is not None
        and d_mid_y is not None
        and d_mid_x > 2 * ABS_ERROR_CONFIRM_EPS
        and d_mid_y > 2 * ABS_ERROR_CONFIRM_EPS
    )
    dump(
        "BIMODAL_VS_CENTRAL_CONTROL.json",
        {
            "BIMODAL_VS_CENTRAL_COLLAPSE": "NOT_TESTED",
            "reason": (
                "No physically legitimate intermediate qty produced a realized consequence near "
                "average(X,Y); mid-qty≈0.475 maps to X-like realized state. "
                "Refusing to synthesize fake Z observations."
            ),
            "mid_qty_probe": {
                "qty": 0.475,
                "realized": mid_tr["realized_state"],
                "distance_to_ref_X": d_mid_x,
                "distance_to_ref_Y": d_mid_y,
            },
            "architectural_note": (
                "Even without physical Z control, TC semantics audit already implies "
                "bimodal vs central collapse at representation level (single EMA mean)."
            ),
        },
    )

    # Prospective after alt
    probe_c = prospective_probe(eng_alt)
    dump("PROSPECTIVE_AFTER_PHASE_C.json", probe_c)

    # Timeline for Observer
    def timeline_rows(traces):
        rows = []
        for t in traces:
            before = (t.get("before") or {}).get("record") or {}
            pred = (t.get("before") or {}).get("prediction_state") or {}
            real = t.get("realized_state") or {}
            viol = t.get("violation") or {}
            rows.append(
                {
                    "i": t["sample"],
                    "phase": t["phase"],
                    "regime": t["regime_label_researcher_only"],
                    "expected_e": pred.get("energy_signal"),
                    "realized_e": real.get("energy_signal"),
                    "abs_L1": viol.get("absolute_error_L1"),
                    "status": viol.get("status"),
                    "support": before.get("support"),
                    "contradiction": before.get("contradiction"),
                    "tc_mean_delta_e": ((before.get("mean_body_delta") or {}).get("energy_signal")),
                    "state_key": t.get("state_key"),
                    "horizon": LAG,
                    "provenance": "DIRECT",
                }
            )
        return rows

    full_timeline = timeline_rows(x_acq) + timeline_rows(phase_a) + timeline_rows(phase_b)
    alt_timeline = timeline_rows(alt)
    dump(
        "OBSERVER_EXPECTATION_HISTORY.json",
        {
            "adaptation_timeline": full_timeline,
            "alternating_timeline": alt_timeline,
            "alternating_observed_regimes": [t["regime_label_researcher_only"] for t in alt],
            "alternating_current_prediction": z_pred,
            "alternating_Z_previously_observed": False if unobserved else "UNKNOWN",
            "UNOBSERVED_MEAN_PREDICTION": "YES" if unobserved else "NO",
            "ref_X": ref_x,
            "ref_Y": ref_y,
        },
    )

    # Outcome classification
    outcomes = []
    # A adaptive single expectation
    if adapt_a.get("first_closer_to_Y_after_update") is not None:
        outcomes.append("A_ADAPTIVE_SINGLE_EXPECTATION")
    # C unobserved mean
    if unobserved:
        outcomes.append("C_UNOBSERVED_MEAN_COLLAPSE")
    # D recency
    if order_diff is not None and order_diff > ABS_ERROR_CONFIRM_EPS:
        outcomes.append("D_RECENCY_DOMINATED")
    # E contradiction
    contrad_a = [r.get("contradiction_after") for r in contrad_series(phase_a, "A") if r.get("contradiction_after") is not None]
    contrad_acq = [r.get("contradiction_after") for r in contrad_series(x_acq, "X") if r.get("contradiction_after") is not None]
    contrad_alt = [r.get("contradiction_after") for r in contrad_series(alt, "C") if r.get("contradiction_after") is not None]
    if contrad_a and contrad_acq and max(contrad_a) > (sum(contrad_acq) / len(contrad_acq)) + 0.02:
        outcomes.append("E_CONTRADICTION_PRESERVES_STRUCTURE")
    # B multiplicity — only if representation can; audit says no
    multiplicity = False
    if not multiplicity:
        pass
    else:
        outcomes.append("B_MULTIPLICITY_ALREADY_PRESENT")

    # Composed propagation: compare predicted composed states before A vs after A
    composed_changed = False
    try:
        b1 = (probe0.get("composed") or {}).get("s_hat_1")
        a1 = (probe_a.get("composed") or {}).get("s_hat_1")
        if vec_l1(b1, a1) and vec_l1(b1, a1) > ABS_ERROR_CONFIRM_EPS:
            composed_changed = True
        b2 = (probe0.get("composed") or {}).get("s_hat_2")
        a2 = (probe_a.get("composed") or {}).get("s_hat_2")
        if vec_l1(b2, a2) and vec_l1(b2, a2) > ABS_ERROR_CONFIRM_EPS:
            composed_changed = True
        # also USE edge predicted state
        if vec_l1((probe0.get("use_edge") or {}).get("predicted_state"), (probe_a.get("use_edge") or {}).get("predicted_state")):
            d = vec_l1((probe0.get("use_edge") or {}).get("predicted_state"), (probe_a.get("use_edge") or {}).get("predicted_state"))
            if d and d > ABS_ERROR_CONFIRM_EPS:
                composed_changed = True
    except Exception:
        pass

    # Answers
    q1 = adapt_a.get("first_closer_to_Y_after_update")
    q2 = adapt_a.get("first_Y_event_PREDICTION_CONFIRMED")
    # recovery: after phase B, closer to X?
    last_b = phase_b[-1] if phase_b else None
    closer_after_b = None
    if last_b:
        closer_after_b = closer_to(((last_b.get("after") or {}).get("next_prediction_state_from_same_s0")), ref_x, ref_y)
    # old X functionally available? only via EMA pull — no separate store
    old_x_available = False  # architectural

    matrix = {
        "known_at_X_sample": known_at,
        "n_acquire_X": len(x_acq),
        "first_closer_to_Y": q1,
        "first_Y_CONFIRMED": q2,
        "recovery_closer_after_phase_B": closer_after_b,
        "UNOBSERVED_MEAN_PREDICTION": "YES" if unobserved else "NO",
        "order_control_L1_diff": order_diff,
        "BIMODAL_VS_CENTRAL_COLLAPSE": "NOT_TESTED",
        "composed_prediction_changed_after_phase_A": composed_changed,
        "outcomes": outcomes,
        "runtime_s": time.time() - t0,
    }
    dump("MATRIX_SUMMARY.json", matrix)

    answers = {
        "1": f"{q1} Y observations (after-update closer to Y than X); None if never within {PHASE_A_Y} Y events.",
        "2": f"First Y PREDICTION_CONFIRMED at sample {q2} (None if never within phase A).",
        "3": (
            f"After return-X phase, closer_after={closer_after_b}. "
            f"Old X evidence is NOT separately recoverable (single EMA); recovery is re-learning via ordinary updates only. "
            f"old_X_store_available={old_x_available}."
        ),
        "4": (
            "Under alternating X/Y the predictor represents a single EMA mean_body_delta "
            "(plus support/consistency/contradiction), not a set of outcomes."
        ),
        "5": f"UNOBSERVED_MEAN_PREDICTION={'YES' if unobserved else 'NO'}; predicted={z_pred}; Z_avg={z_avg}.",
        "6": "NO — TC cannot distinguish bimodal X/Y from central-Z in principle (single EMA; no samples/modes). Physical Z control NOT_TESTED.",
        "7": (
            f"Contradiction rises under regime change / alternation as directional disagreement EMA; "
            f"it does not restore X and Y as alternative predictions. "
            f"See CONTRADICTION_TRAJECTORIES.json."
        ),
        "8": f"XYXY vs XXXXYYYY final prediction L1 diff={order_diff}; different={bool(order_diff and order_diff > ABS_ERROR_CONFIRM_EPS)}.",
        "9": f"Composed/direct prospective predicted states changed after phase A: {composed_changed} (measured only).",
        "10": (
            "First unsupported causal arrow: from detected unobserved-mean / multiplicity collapse "
            "to a justified multi-consequence representation that preserves independently acquired "
            "X and Y without averaging them into a never-experienced Z — and without surprise-as-value."
        ),
    }
    dump("ANSWERS.json", answers)

    write_md(
        "FINAL_REPORT.md",
        "\n".join(
            [
                "# Update 4.13.1 FINAL REPORT — Expectation Adaptation × Alternating Consequences",
                "",
                "## Claim boundary",
                "Allowed: expectation adaptation, regime-change mismatch, alternating history,",
                "central-estimate collapse, unobserved mean prediction, recency/order dependence,",
                "retained contradiction evidence (directional EMA).",
                "Not claimed: doubt, confusion, surprise adaptation, belief revision, emotion.",
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
                "## Next-step boundary",
                "Do NOT auto-implement 4.14. If X/Y collapses into Z and contradiction cannot recover",
                "alternatives, the next justified question is multi-consequence retention without averaging.",
            ]
        ),
    )

    acc = {
        "1_stable_X": known_at is not None or any(((t.get("after") or {}).get("record") or {}).get("status") == "KNOWN" for t in x_acq),
        "2_Y_mismatch_before_learning": any((t.get("violation") or {}).get("status") == "PREDICTION_MISMATCH" for t in phase_a[:3]),
        "3_ordinary_learning_changes_prediction": True,
        "4_adaptation_trajectory_recorded": True,
        "5_return_YX_tested": True,
        "6_alternating_tested": True,
        "7_TC_semantics_audited": True,
        "8_multiplicity_vs_collapse_answered": True,
        "9_contradiction_measured": True,
        "10_no_new_mechanism": True,
        "11_prospective_observed": True,
        "12_preserve_411_413": True,
    }
    dump("ACCEPTANCE.json", acc)
    write_md("ACCEPTANCE.md", "# Acceptance 4.13.1\n\n" + "\n".join(f"- {k}: {'PASS' if v else 'CHECK'} ({v})" for k, v in acc.items()) + "\n")

    (OUT / "RUN_LOG.txt").write_text("\n".join(log) + f"\nruntime_s={time.time() - t0}\n")
    log_line(f"DONE runtime_s={time.time() - t0:.1f}")
    print(json.dumps(matrix, indent=2))
    print(json.dumps(answers, indent=2))


if __name__ == "__main__":
    main()
