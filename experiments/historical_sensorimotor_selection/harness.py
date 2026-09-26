
"""Historical support × SMC × PSC — experiment harness (no new value scalar).

Phase A: PSC OFF (LEGACY_FIRST), SMC learning ON, history accumulates.
Phase B: PSC ON (SCENARIO_COMPETITION), same stores — no reset.

Logging-only O'→history probe measures latent differentiation without feeding selection.
"""
from __future__ import annotations

import json
import math
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import predictive_compression as pc

OUT = Path("results/mm_historical_sensorimotor_selection")

LOCOS = ["WAIT", "MOVE:N", "MOVE:E", "MOVE:S", "MOVE:W"]
NECKS = ["NONE", "NECK_LEFT", "NECK_RIGHT", "NECK_HOLD"]

def phase_a_explore_motor(tick: int, seed: int) -> dict:
    """Schedule-driven exploration during PSC-OFF Phase A.

    Not a policy preference: cycles locomotion and neck so multiple (O,M)→ΔO
    records accumulate before PSC activation. Documented as EXPERIENCE schedule.
    """
    loco = LOCOS[(tick + seed) % len(LOCOS)]
    neck = NECKS[(tick // 3 + seed) % len(NECKS)]
    return {
        "schema": "COMPOSITE_MOTOR_V1",
        "locomotion": loco,
        "neck": neck,
        "oscillator": {"emit_trigger": False, "frequency_delta": 0, "amplitude_delta": 0},
        "push": False,
        "selection_source": "PHASE_A_EXPERIENCE_SCHEDULE",
    }



def _clip01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else float(x)


def synth_obs(tick: int, pose: dict[str, float], seed: int) -> dict[str, float]:
    """Accessible observation from synthetic pose (no GT agent labels)."""
    # Simple fields from pose + slow environmental drift
    drift = 0.02 * math.sin((tick + seed) * 0.01)
    return {
        "exo_0": _clip01(pose["exo_0"]),
        "exo_1": _clip01(pose["exo_1"]),
        "exo_2": _clip01(pose["exo_2"]),
        "local.FIELD_A": _clip01(0.3 + 0.2 * math.sin(tick * 0.03) + drift),
        "local.FIELD_B": _clip01(0.3 + 0.2 * math.cos(tick * 0.025)),
        "vest_0": _clip01(0.5 + 0.05 * pose.get("vx", 0.0)),
        "vest_1": _clip01(0.5 + 0.05 * pose.get("vy", 0.0)),
        "prop_neck_0": _clip01(pose.get("neck_l", 0.5)),
        "prop_neck_1": _clip01(pose.get("neck_r", 0.5)),
        "body.T": 0.4,
        "body.B0": 0.1,
        "body.B1": 0.1,
        "body.B2": 0.1,
        "body.mech": 0.0,
        "body.vx": _clip01(0.5 + pose.get("vx", 0.0)),
        "body.vy": _clip01(0.5 + pose.get("vy", 0.0)),
        "local.T": 0.4,
        "local.M0": 0.1,
        "local.M1": 0.1,
        "local.M2": 0.1,
        "local.vx": 0.5,
        "local.vy": 0.5,
    }


def apply_motor_physics(pose: dict[str, float], motor: dict[str, Any] | None) -> dict[str, float]:
    """Deterministic accessible consequences of composite motor (synthetic ecology)."""
    p = dict(pose)
    m = motor or {}
    loco = str(m.get("locomotion") or "WAIT")
    neck = str(m.get("neck") or "NONE")
    step = 0.08
    if loco == "MOVE:N":
        p["vy"] = p.get("vy", 0.0) + step
        p["exo_1"] = _clip01(p.get("exo_1", 0.5) + 0.12)
        p["exo_0"] = _clip01(p.get("exo_0", 0.3) - 0.02)
    elif loco == "MOVE:S":
        p["vy"] = p.get("vy", 0.0) - step
        p["exo_1"] = _clip01(p.get("exo_1", 0.5) - 0.12)
        p["exo_0"] = _clip01(p.get("exo_0", 0.3) + 0.02)
    elif loco == "MOVE:E":
        p["vx"] = p.get("vx", 0.0) + step
        p["exo_0"] = _clip01(p.get("exo_0", 0.3) + 0.12)
        p["exo_2"] = _clip01(p.get("exo_2", 0.3) - 0.03)
    elif loco == "MOVE:W":
        p["vx"] = p.get("vx", 0.0) - step
        p["exo_0"] = _clip01(p.get("exo_0", 0.3) - 0.12)
        p["exo_2"] = _clip01(p.get("exo_2", 0.3) + 0.03)
    elif loco == "WAIT":
        # mild decay toward mid
        p["exo_1"] = _clip01(p.get("exo_1", 0.5) * 0.98 + 0.01)
    if neck == "NECK_LEFT":
        p["exo_0"] = _clip01(p.get("exo_0", 0.3) + 0.15)
        p["neck_l"] = _clip01(p.get("neck_l", 0.5) + 0.1)
        p["neck_r"] = _clip01(p.get("neck_r", 0.5) - 0.05)
    elif neck == "NECK_RIGHT":
        p["exo_2"] = _clip01(p.get("exo_2", 0.3) + 0.15)
        p["neck_r"] = _clip01(p.get("neck_r", 0.5) + 0.1)
        p["neck_l"] = _clip01(p.get("neck_l", 0.5) - 0.05)
    # drag
    p["vx"] = p.get("vx", 0.0) * 0.9
    p["vy"] = p.get("vy", 0.0) * 0.9
    return p


def make_config(
    *,
    psc_on: bool,
    smc_on: bool,
    withhold: bool = False,
    shuffle: bool = False,
    o_prime_bridge: bool = False,
    o_prime_withhold: bool = False,
    o_prime_shuffle: bool = False,
    smc_withhold: bool = False,
) -> CognitionConfig:
    return CognitionConfig(
        prospective_composition=True,
        prospective_selection="SCENARIO_COMPETITION" if psc_on else "LEGACY_FIRST",
        retrieval=True,
        sensorimotor_consequence_model=smc_on,
        # Keep SMC enrichment ON for O′-bridge tests; isolate O′ withhold separately.
        sensorimotor_consequence_withhold_from_psc=smc_withhold,
        sensorimotor_consequence_shuffle_motors=shuffle,
        historical_sensorimotor_selection_bridge=o_prime_bridge,
        historical_sensorimotor_selection_withhold=o_prime_withhold,
        historical_sensorimotor_selection_shuffle=o_prime_shuffle,
        composite_motor=True,
    )


def activate_psc(state: dict[str, Any]) -> None:
    """PHASE B transition — no reset of stores."""
    state["config"]["prospective_selection"] = "SCENARIO_COMPETITION"


def deactivate_psc(state: dict[str, Any]) -> None:
    state["config"]["prospective_selection"] = "LEGACY_FIRST"


def snapshot_stores(state: dict[str, Any]) -> dict[str, Any]:
    sm = state.get("sensorimotor_consequence") or {}
    prs = state.get("prospection") or {}
    cmp_ = state.get("compression") or {}
    return {
        "smc_occupancy": len(sm.get("records") or {}),
        "smc_updates": int(sm.get("updates") or 0),
        "smc_evictions": int(sm.get("evictions") or 0),
        "prospection_transitions": len(prs.get("transitions") or {}),
        "compression_structures": len(cmp_.get("structures") or {}),
        "prospective_selection": state.get("config", {}).get("prospective_selection"),
        "smc_enabled": bool(sm.get("enabled")),
    }


def probe_o_prime_history(
    state: dict[str, Any],
    o_prime: dict[str, float],
    actions: list[str],
) -> dict[str, Any]:
    """LOGGING ONLY — does NOT feed PSC.

    Asks existing APIs: if antecedent were O', what MATCH support exists per action?
    Also: how many prospection rows have mean consequent near O' (familiarity proxy).
    """
    store = state.get("prospection") or {}
    action_supports = {}
    matched = 0
    for a in actions:
        step = pr.predict_one_step(store, o_prime, a)
        st = step.get("status")
        action_supports[a] = {
            "status": st,
            "support": int(step.get("support") or 0) if st == "MATCH" else 0,
            "reliability": float(step.get("reliability") or 0.0) if st == "MATCH" else 0.0,
        }
        if st == "MATCH":
            matched += 1
    # Consequent familiarity: count transitions whose mean consequent L1 to O' is small
    # on SMC sensory channels only (bounded scan).
    sens = smc.extract_sensory(o_prime)
    near = 0
    scanned = 0
    for row in (store.get("transitions") or {}).values():
        scanned += 1
        if scanned > 512:
            break
        # mean consequent stored as sum/n pattern — use predict helper fields if present
        cons = row.get("mean_consequent") or row.get("consequent_mean")
        if not isinstance(cons, dict):
            # reconstruct from sum_cons / n if available
            n = float(row.get("n") or row.get("support") or 0)
            sums = row.get("sum_cons") or row.get("consequent_sum")
            if isinstance(sums, dict) and n > 0:
                cons = {k: float(v) / n for k, v in sums.items()}
            else:
                continue
        # L1 on overlapping sensory keys
        keys = [k for k in smc.SENSORY_CHANNELS if k in cons and k in sens]
        if not keys:
            continue
        d = sum(abs(float(cons[k]) - float(sens[k])) for k in keys) / len(keys)
        if d <= 0.12:
            near += 1
    # compression probe on first action as presence check
    cmp_hits = 0
    mem = state.get("compression") or {}
    for a in actions[:3]:
        pred = pc.predict(mem, o_prime, a, domain="accessible")
        if pred.get("status") == "MATCH":
            cmp_hits += 1
    supports = [v["support"] for v in action_supports.values()]
    return {
        "matched_actions": matched,
        "support_by_action": action_supports,
        "support_range": (min(supports) if supports else 0, max(supports) if supports else 0),
        "support_spread": (max(supports) - min(supports)) if supports else 0,
        "consequent_near_count": near,
        "compression_match_actions": cmp_hits,
        "differentiated": bool(supports) and (max(supports) - min(supports)) >= 2,
    }


def rng_for(seed: int, tick: int) -> float:
    # Deterministic endogenous-like float in [0,1)
    x = (seed * 1103515245 + tick * 12345) & 0x7FFFFFFF
    return (x % 10000) / 10000.0


def run_condition(
    *,
    seed: int,
    condition: str,
    phase_a: int,
    phase_b: int,
    record_receipts: bool = True,
    receipt_stride: int = 25,
) -> dict[str, Any]:
    """One paired seed×condition run."""
    smc_on = condition != "F_SMC_OFF"
    # B = O′ history evidence withheld from PSC (queries still run)
    o_prime_withhold = condition == "B_OPRIME_HISTORY_WITHHELD"
    shuffle = condition == "C_MOTOR_SHUFFLE"
    # D = mismatch O′↔history correspondence (shuffle history across candidates)
    o_prime_shuffle = condition == "D_OPRIME_HISTORY_SHUFFLE"
    psc_from_start = condition == "E_PSC_FROM_START"
    o_prime_bridge = condition in {
        "A_FULL_OPRIME_BRIDGE",
        "B_OPRIME_HISTORY_WITHHELD",
        "C_MOTOR_SHUFFLE",
        "D_OPRIME_HISTORY_SHUFFLE",
        "E_PSC_FROM_START",
    } and smc_on
    # legacy alias
    if condition in ("A_FULL_BRIDGE", "B_PREDICTION_WITHHELD", "D_HISTORY_CONTROL"):
        # map old names if any caller still uses them
        pass
    history_control = False  # superseded by D_OPRIME_HISTORY_SHUFFLE

    cfg = make_config(
        psc_on=psc_from_start,
        smc_on=smc_on,
        shuffle=shuffle,
        o_prime_bridge=o_prime_bridge,
        o_prime_withhold=o_prime_withhold,
        o_prime_shuffle=o_prime_shuffle,
        smc_withhold=False,
    )
    state = empty_cognitive_state(cfg)
    pose = {
        "exo_0": 0.35,
        "exo_1": 0.50,
        "exo_2": 0.35,
        "vx": 0.0,
        "vy": 0.0,
        "neck_l": 0.5,
        "neck_r": 0.5,
    }
    total = phase_a + phase_b
    t0 = phase_a  # activation tick (first Phase B tick index)
    if psc_from_start:
        t0 = 0
        phase_a_eff = 0
        phase_b_eff = total
    else:
        phase_a_eff = phase_a
        phase_b_eff = phase_b

    activation_snap_before = None
    activation_snap_after = None
    phase_a_metrics = None
    receipts: list[dict[str, Any]] = []
    selection_hist: dict[str, int] = {}
    funnel = {
        "psc_competitions": 0,
        "multi_candidate": 0,
        "smc_preds_available": 0,
        "predicted_futures_differentiated": 0,
        "o_prime_history_queried": 0,
        "historical_support_differentiated": 0,
        "historical_evidence_available_to_psc": 0,
        "psc_ranking_changed_by_history_evidence": 0,  # local CF
        "final_selection_differs_from_withheld_cf": 0,
        "smc_support_differentiated": 0,
        "selected_was_max_smc_support": 0,
        "selected_was_max_o_prime_history_support": 0,
        # legacy keys kept for comparability
        "o_prime_history_differentiated": 0,
        "selected_was_max_o_prime_support": 0,
    }
    pred_err_sum = 0.0
    pred_err_n = 0
    unknown_queries = 0
    match_queries = 0
    head_domain = {"neck_left_exo0_correct_sign": 0, "neck_queries": 0}

    motor = None
    t_wall0 = time.perf_counter()

    for tick in range(1, total + 1):
        # Phase transition
        if (not psc_from_start) and tick == t0 + 1:
            activation_snap_before = snapshot_stores(state)
            activate_psc(state)
            activation_snap_after = snapshot_stores(state)
            # verify no reset
            assert activation_snap_before["smc_occupancy"] == activation_snap_after["smc_occupancy"]
            assert activation_snap_before["smc_updates"] == activation_snap_after["smc_updates"]
            assert activation_snap_before["prospection_transitions"] == activation_snap_after["prospection_transitions"]

        if (not psc_from_start) and tick == t0:
            phase_a_metrics = {
                "tick": tick,
                "stores": snapshot_stores(state),
                "smc_diag": smc.diagnostic(state.get("sensorimotor_consequence") or {}),
            }

        obs = synth_obs(tick, pose, seed)
        # Realize previous motor physically → new pose before cognition sees obs
        # (obs already from current pose; after selection we apply motor)
        result = run_cognition_before_action(
            state, observation=obs, tick=tick, rng_value=rng_for(seed, tick)
        )
        motor = result.motor_output or {
            "locomotion": result.selected_action,
            "neck": "NONE",
            "oscillator": {},
            "push": False,
        }
        # Phase A: replace executed motor with exploration schedule so history
        # covers multiple motors before PSC. Cognition still ran; stores learn
        # from whatever was last executed on the subsequent tick.
        in_phase_a_explore = (not psc_from_start) and tick <= t0
        if in_phase_a_explore:
            motor = phase_a_explore_motor(tick, seed)
            # Align cognition memory of executed action with what physics applies
            state["last_action"] = str(motor["locomotion"])
            state["last_motor_output"] = motor
            executed = str(motor["locomotion"])
        else:
            executed = str(result.selected_action)
        selection_hist[executed] = selection_hist.get(executed, 0) + 1

        last = state.get("last_selection") or {}
        mode = str(last.get("prospective_selection_mode") or "")
        smc_preds = list(last.get("sensorimotor_candidate_predictions") or [])
        competition = last.get("competition") or {}

        # Prediction accuracy vs actual next obs (after physics)
        pose_next = apply_motor_physics(pose, motor)
        obs_next = synth_obs(tick + 1, pose_next, seed)
        # Find SMC pred for selected loco
        sel_loco = str(motor.get("locomotion") or result.selected_action)
        for pred in smc_preds:
            if pred.get("candidate_locomotion") == sel_loco and pred.get("predicted_delta"):
                if pred.get("status") == smc.UNKNOWN:
                    unknown_queries += 1
                else:
                    match_queries += 1
                    o_hat = smc.apply_predicted_to_observation(obs, pred["predicted_delta"])
                    # error on sensory channels
                    err = 0.0
                    nch = 0
                    for k in smc.SENSORY_CHANNELS:
                        if k in obs_next and k in o_hat:
                            err += abs(float(obs_next[k]) - float(o_hat[k]))
                            nch += 1
                    if nch:
                        pred_err_sum += err / nch
                        pred_err_n += 1
                break

        # Head domain probe (logging): NECK_LEFT predicted Δexo_0
        if smc_on and (state.get("sensorimotor_consequence") or {}).get("updates", 0) > 5:
            qn = smc.query(
                state["sensorimotor_consequence"],
                observation=obs,
                motor={"locomotion": "WAIT", "neck": "NECK_LEFT", "oscillator": {}, "push": False},
            )
            head_domain["neck_queries"] += 1
            d = (qn.get("predicted_delta") or {}).get("exo_0")
            if d is not None and float(d) > 0.05:
                head_domain["neck_left_exo0_correct_sign"] += 1

        in_phase_b = psc_from_start or (tick > t0)
        if in_phase_b and mode == "SCENARIO_COMPETITION":
            funnel["psc_competitions"] += 1
            supported = list(competition.get("supported_actions") or [])
            if len(supported) >= 2:
                funnel["multi_candidate"] += 1

            usable = [p for p in smc_preds if p.get("status") in {smc.MATCH, smc.LOW_SUPPORT} and p.get("predicted_delta")]
            if usable:
                funnel["smc_preds_available"] += 1
                # Differentiate predicted futures (L1 between O' pairs)
                ohats = []
                for p in usable:
                    ohats.append(smc.apply_predicted_to_observation(obs, p["predicted_delta"]))
                diff_future = False
                for i in range(len(ohats)):
                    for j in range(i + 1, len(ohats)):
                        keys = smc.SENSORY_CHANNELS
                        dmax = max(abs(ohats[i].get(k, 0) - ohats[j].get(k, 0)) for k in keys)
                        if dmax >= 0.05:
                            diff_future = True
                if diff_future:
                    funnel["predicted_futures_differentiated"] += 1

                supports = [int(p.get("support") or 0) for p in usable]
                if max(supports) - min(supports) >= 1:
                    funnel["smc_support_differentiated"] += 1
                # selected vs max SMC support
                by_loco = {str(p.get("candidate_locomotion")): int(p.get("support") or 0) for p in usable}
                if by_loco:
                    max_s = max(by_loco.values())
                    if by_loco.get(sel_loco, -1) == max_s:
                        funnel["selected_was_max_smc_support"] += 1

                # Logging-only O' history probe
                o_prime_supports = []
                hist_diff = False
                for p in usable:
                    o_hat = smc.apply_predicted_to_observation(obs, p["predicted_delta"])
                    if history_control:
                        # Disrupt correspondence: permute exo channels of O' only in probe
                        o_hat = dict(o_hat)
                        o_hat["exo_0"], o_hat["exo_1"], o_hat["exo_2"] = (
                            o_hat.get("exo_2", 0),
                            o_hat.get("exo_0", 0),
                            o_hat.get("exo_1", 0),
                        )
                    probe = probe_o_prime_history(state, o_hat, LOCOS)
                    o_prime_supports.append((str(p.get("candidate_locomotion")), probe["support_spread"], probe))
                    if probe["differentiated"] or probe["support_spread"] >= 2:
                        hist_diff = True
                if hist_diff:
                    pass  # counted via o_prime_history_bridge meta when enabled
                if o_prime_supports:
                    # max spread's loco vs selection — weak alignment check
                    best_loco = max(o_prime_supports, key=lambda x: x[1])[0]
                    if best_loco == sel_loco and max(x[1] for x in o_prime_supports) > 0:
                        funnel["selected_was_max_o_prime_support"] += 1


            # O′ history bridge funnel (native cognition meta)
            ob = last.get("o_prime_history_bridge") or {}
            if ob.get("enabled"):
                funnel["o_prime_history_queried"] += 1
                if ob.get("history_support_differentiated"):
                    funnel["historical_support_differentiated"] += 1
                    funnel["o_prime_history_differentiated"] += 1
                if not ob.get("withheld_from_psc"):
                    funnel["historical_evidence_available_to_psc"] += 1
                if ob.get("selection_differs_from_withheld_cf"):
                    funnel["psc_ranking_changed_by_history_evidence"] += 1
                    funnel["final_selection_differs_from_withheld_cf"] += 1
                # selected vs max O′ history support among candidates
                ocands = last.get("o_prime_history_candidates") or []
                if ocands:
                    best = max(ocands, key=lambda x: int(x.get("history_support") or 0))
                    if str(best.get("candidate_locomotion")) == sel_loco and int(best.get("history_support") or 0) > 0:
                        funnel["selected_was_max_o_prime_history_support"] += 1
                        funnel["selected_was_max_o_prime_support"] += 1

                if record_receipts and (tick % receipt_stride == 0):
                    cand_rows = []
                    for p in usable:
                        o_hat = smc.apply_predicted_to_observation(obs, p["predicted_delta"])
                        probe = probe_o_prime_history(state, o_hat, LOCOS)
                        cand_rows.append({
                            "candidate_motor_signature": p.get("motor_signature") or p.get("candidate_locomotion"),
                            "candidate_locomotion": p.get("candidate_locomotion"),
                            "sensorimotor_prediction": {
                                "status": p.get("status"),
                                "predicted_delta": {k: round(float(v), 4) for k, v in (p.get("predicted_delta") or {}).items() if abs(float(v)) > 0.01},
                                "support": p.get("support"),
                                "reliability": p.get("reliability"),
                                "record_id": p.get("record_id"),
                            },
                            "historical_query_logging_only": {
                                "matched_actions": probe["matched_actions"],
                                "support_spread": probe["support_spread"],
                                "consequent_near_count": probe["consequent_near_count"],
                                "differentiated": probe["differentiated"],
                            },
                            "selected": str(p.get("candidate_locomotion")) == sel_loco,
                        })
                    receipts.append({
                        "tick": tick,
                        "phase": "B" if in_phase_b else "A",
                        "selected": sel_loco,
                        "selection_source": last.get("source"),
                        "withheld": bool(last.get("sensorimotor_withheld_from_psc")),
                        "competition_outcome": competition.get("outcome_class"),
                        "candidates": cand_rows,
                    })

        pose = pose_next

    elapsed = time.perf_counter() - t_wall0
    final_snap = snapshot_stores(state)
    return {
        "seed": seed,
        "condition": condition,
        "phase_a": phase_a_eff,
        "phase_b": phase_b_eff if not psc_from_start else total,
        "activation_tick": t0,
        "activation_snap_before": activation_snap_before,
        "activation_snap_after": activation_snap_after,
        "phase_a_metrics": phase_a_metrics,
        "final_stores": final_snap,
        "selection_hist": selection_hist,
        "funnel": funnel,
        "mean_pred_err": (pred_err_sum / pred_err_n) if pred_err_n else None,
        "pred_err_n": pred_err_n,
        "unknown_queries": unknown_queries,
        "match_queries": match_queries,
        "head_domain": head_domain,
        "receipts_sample": receipts[:12],
        "n_receipts": len(receipts),
        "elapsed_s": round(elapsed, 3),
        "no_reset_verified": (
            activation_snap_before is not None
            and activation_snap_before["smc_updates"] == activation_snap_after["smc_updates"]
            and activation_snap_before["smc_occupancy"] == activation_snap_after["smc_occupancy"]
        ) if activation_snap_before else (True if psc_from_start else False),
    }


def median(xs: list[float]) -> float:
    if not xs:
        return float("nan")
    s = sorted(xs)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else 0.5 * (s[mid - 1] + s[mid])


def iqr(xs: list[float]) -> tuple[float, float]:
    if not xs:
        return (float("nan"), float("nan"))
    s = sorted(xs)
    n = len(s)
    return (s[n // 4], s[(3 * n) // 4])


CONDITIONS = [
    "A_FULL_OPRIME_BRIDGE",
    "B_OPRIME_HISTORY_WITHHELD",
    "C_MOTOR_SHUFFLE",
    "D_OPRIME_HISTORY_SHUFFLE",
    "E_PSC_FROM_START",
    "F_SMC_OFF",
]
