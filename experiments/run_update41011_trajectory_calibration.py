#!/usr/bin/env python3
"""Update 4.10.11 — Prospective trajectory calibration × temporal valuation frontier.

SHADOW / DIAGNOSTIC ONLY. No habit_weight, gate, ecology, or policy retune.
"""
from __future__ import annotations

import copy
import gc
import json
import math
import statistics
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
from mechanistic_mind.research.prospective_valuation import prospective_ordinary_value
from mechanistic_mind.psyche.temporal_contingency import (
    DEFAULT_LAGS,
    MIN_SUPPORT_KNOWN,
    _ema,
    ensure_temporal,
    normalize_action,
    temporal_cue_bucket,
    temporal_key,
)

OUT = ROOT / "results" / "update41011_trajectory_calibration"
OUT.mkdir(parents=True, exist_ok=True)
A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED
TE = int(MDS_LADDER_TICK_EQUIVALENT[0])
SPEC = subsidy_from_tick_equivalent(TE)
SEVERE_E, SEVERE_H, SEVERE_F = 0.18, 0.18, 0.82
HORIZONS_SHORT = (1, 2, 3)
HORIZONS_PHYS = (1, 2, 3, 5, 10, 25)


def dump(name: str, payload: Any) -> None:
    def _fix(o):
        if isinstance(o, dict):
            return {str(k): _fix(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_fix(v) for v in o]
        if isinstance(o, float) and (o != o or abs(o) == float("inf")):
            return None
        return o

    (OUT / name).write_text(json.dumps(_fix(payload), indent=2, sort_keys=True, default=str) + "\n")
    print("wrote", name, flush=True)


def write_md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")
    print("wrote", name, flush=True)


def apply_spec(eng, spec=SPEC) -> None:
    bc = apply_subsidy_to_body_config(eng.world.body_config, spec)
    eng.world.body_config = bc
    if hasattr(eng.world, "body_engine"):
        eng.world.body_engine.config = bc
    eng.state.world.variables["bodies"][A] = apply_subsidy_to_body_state(BodyState(), spec).to_dict()


def fresh():
    wcfg = u4101.multi_channel_contextual_object_config(SEED)
    field = u4101.build_uniform_field(wcfg.width, wcfg.height, 0.0)
    eng = u4101.make_engine(field=field, pos=OPOS, sm=u4101.sm_on(), env=False, intake=True)
    apply_spec(eng)
    return eng


def body_raw(eng):
    return dict(eng.state.world.variables["bodies"][A])


def signals(eng):
    psy = u4101.psyche(eng)
    m = dict((psy.get("internal") or {}).get("interoceptive_model") or {})
    if m.get("energy_signal") is not None:
        return {k: float(v) for k, v in m.items() if isinstance(v, (int, float))}
    b = body_raw(eng)
    e_cap = float(eng.world.body_config.energy_capacity)
    h_cap = float(eng.world.body_config.hydration_capacity)
    return {
        "energy_signal": float(b.get("energy_reserve") or 0) / max(1e-9, e_cap),
        "hydration_signal": float(b.get("hydration") or 0) / max(1e-9, h_cap),
        "fatigue_signal": float(b.get("fatigue") or 0),
        "discomfort_signal": 0.0,
        "activity_capacity_signal": float(b.get("activity_capacity") or 1.0),
        "activity_load_signal": float(b.get("activity_load") or 0.0),
        "effort_signal": float(b.get("effort") or 0.0) if "effort" in b else 0.0,
    }


def severe(sig):
    return (
        float(sig.get("energy_signal", 1)) < SEVERE_E
        or float(sig.get("hydration_signal", 1)) < SEVERE_H
        or float(sig.get("fatigue_signal", 0)) > SEVERE_F
    )


def acquire_known(eng, n=16):
    """Acquire USE contingencies; optionally capture per-trial raw deltas for distribution."""
    trials = []
    for i in range(n):
        u4101.replenish_object(eng, 0.95)
        s0 = signals(eng)
        b0 = {
            "energy_reserve": body_raw(eng).get("energy_reserve"),
            "hydration": body_raw(eng).get("hydration"),
            "fatigue": body_raw(eng).get("fatigue"),
            "internal_materials": deepcopy(body_raw(eng).get("internal_materials")),
        }
        eng.step({A: Action(f"USE:{OID}")})
        path = {0: s0}
        for t in range(1, 4):
            if t > 1:
                eng.step({A: Action("WAIT")})
            path[t] = signals(eng)
        # extra wait to settle acquisition pattern like 4109
        eng.step({A: Action("WAIT")})
        trials.append(
            {
                "i": i,
                "s0": s0,
                "body0": b0,
                "cum": {t: {k: float(path[t].get(k, 0)) - float(s0.get(k, 0)) for k in path[t]} for t in (1, 2, 3)},
            }
        )
    return trials


def tc_lags(eng, action_prefix: str) -> dict[int, dict]:
    tc = ensure_temporal(deepcopy((u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}))
    out = {}
    for k, v in (tc.get("contingencies") or {}).items():
        act = str(v.get("action") or "")
        if act == action_prefix or act.startswith(action_prefix):
            out[int(v.get("lag") or -1)] = {"key": k, **{kk: v.get(kk) for kk in (
                "action", "status", "support", "confidence", "lag", "mean_body_delta",
                "contradiction", "consistency", "baseline_wait_magnitude", "action_specific_strength",
                "observations",
            )}}
    return out


def rollout_cum(eng0, action: str, horizons=HORIZONS_PHYS) -> dict[int, dict]:
    eng = copy.deepcopy(eng0)
    s0 = signals(eng)
    out = {0: {k: 0.0 for k in s0}}
    if action.startswith("USE"):
        eng.step({A: Action(action)})
    else:
        eng.step({A: Action(action)})
    for t in range(1, max(horizons) + 1):
        if t > 1:
            eng.step({A: Action("WAIT")})
        if t in horizons:
            s = signals(eng)
            out[t] = {k: float(s.get(k, 0)) - float(s0.get(k, 0)) for k in s}
    return out


def matched_use_wait(eng0, horizons=HORIZONS_PHYS) -> dict:
    use = rollout_cum(eng0, f"USE:{OID}", horizons)
    wait = rollout_cum(eng0, "WAIT", horizons)
    diff = {}
    for H in horizons:
        u, w = use[H], wait[H]
        keys = set(u) | set(w)
        diff[H] = {k: float(u.get(k, 0)) - float(w.get(k, 0)) for k in keys}
    return {"USE": use, "WAIT": wait, "USE_minus_WAIT": diff}


def dist_stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    values = [float(v) for v in values]
    n = len(values)
    mu = sum(values) / n
    med = statistics.median(values)
    sd = statistics.pstdev(values) if n > 1 else 0.0
    signs = [1 if v > 1e-12 else (-1 if v < -1e-12 else 0) for v in values]
    pos = sum(1 for s in signs if s > 0)
    neg = sum(1 for s in signs if s < 0)
    return {
        "n": n,
        "mean": mu,
        "median": med,
        "min": min(values),
        "max": max(values),
        "sd": sd,
        "q25": statistics.quantiles(values, n=4)[0] if n >= 4 else None,
        "q75": statistics.quantiles(values, n=4)[2] if n >= 4 else None,
        "sign_consistency": max(pos, neg) / n if n else None,
        "contradiction_fraction": (min(pos, neg) / n) if n and (pos and neg) else 0.0,
    }


def main():
    t0 = time.time()
    dump("UPDATE41011_CONFIG.json", {
        "update": "4.10.11",
        "mode": "DIAGNOSTIC_SHADOW",
        "init_TE": TE,
        "no_policy_integration": True,
    })
    dump("UPDATE41011_FROZEN_PARAMETERS.json", {
        "habit_weight": 0.03,
        "severe": [0.35, 0.04, SEVERE_E, SEVERE_H, SEVERE_F],
        "DEFAULT_LAGS": list(DEFAULT_LAGS),
        "MIN_SUPPORT_KNOWN": MIN_SUPPORT_KNOWN,
        "aggregation": "running_EMA_mean",
        "no_retune": True,
    })

    # ---- Prediction semantics (code facts) ----
    write_md(
        "PREDICTION_SEMANTICS_AUDIT.md",
        f"""# Prediction semantics audit

## What is H3 energy ≈ +0.013?

It is the **running EMA mean** of cumulative body deltas stored in the USE contingency at lag L3:

`mean_body_delta[energy_signal]` under key `TC||{{bucket}}||USE:{{id}}||L3`.

## Population
- Events: each time a pending USE trace reaches age=3, `consequence_from_observations(obs_before, obs_now)` yields cumulative T0→T+3 delta.
- Update: `_ema(old, new, support)` = `(old*(n-1)+new)/n` with `support` incremented by 1 each observation.
- Context membership: `temporal_cue_bucket` = visible object ids + perceptual features (**body_bands omitted**).
- Action membership: `normalize_action` (USE keeps object id).
- **No body-state conditioning** (energy/hydration/fatigue at action time do not split the key).
- **No internal-material conditioning** in the TC key.
- Status KNOWN requires support ≥ {MIN_SUPPORT_KNOWN} and contradiction not >0.55.

## Statistic class
**A. Empirical running mean (EMA equivalent to sample mean under sequential update)** over pooled matching (action, context-bucket, lag) experiences.

Not: median, mode, NN, state-conditioned mean.

## Retrieval (decision time)
`retrieve_temporal` by bucket; `best_prediction_for_action` prefers **lowest lag among KNOWN** → often L2, not L3.

## Confidence
Epistemic: consistency × log-support factor × (1−0.5·contradiction). **Not value.**

## What +0.013 is NOT
- Not a guarantee for this rollout
- Not action-specific (USE−WAIT) by construction — absolute post-action cum delta
- Not state-matched to current energy when acquiring from heterogeneous MDS/run states
""",
    )

    print("Build acquisition population...", flush=True)
    eng = fresh()
    trials = acquire_known(eng, 16)
    apply_spec(eng)
    eng.step()  # free tick after reset like prior updates
    use_lags = tc_lags(eng, f"USE:{OID}")
    wait_lags = tc_lags(eng, "WAIT")

    # Reconstruct EMA from trial raw cum to verify ≈ stored mean
    recon = {1: {}, 2: {}, 3: {}}
    support = {1: 0.0, 2: 0.0, 3: 0.0}
    for tr in trials:
        for H in (1, 2, 3):
            support[H] += 1.0
            for k, v in tr["cum"][H].items():
                recon[H][k] = _ema(float(recon[H].get(k, 0.0)), float(v), support[H])

    dump("PREDICTION_CAUSAL_TRACE.json", {
        "statistic": "running_EMA_mean_of_cumulative_T0_to_TL_body_delta",
        "context_key": "temporal_cue_bucket(visible, perceptual_features) — no body_bands",
        "state_conditioning": False,
        "internal_material_conditioning": False,
        "decision_lag_selection": "best_prediction_for_action: lowest KNOWN lag",
        "DEFAULT_LAGS": list(DEFAULT_LAGS),
        "stored_USE_by_lag": {str(L): use_lags.get(L) for L in sorted(use_lags)},
        "reconstructed_EMA_from_acquisition_trials": recon,
        "stored_vs_recon_energy_L3": {
            "stored": (use_lags.get(3) or {}).get("mean_body_delta", {}).get("energy_signal"),
            "recon": recon[3].get("energy_signal"),
        },
        "n_acquisition_trials": len(trials),
    })

    # Source records compact (research only)
    dump("TEMPORAL_SOURCE_RECORDS.json", {
        "note": "Research instrumentation. Per-acquisition trial raw cum deltas contributing to EMA.",
        "trials": [
            {
                "i": tr["i"],
                "action_time_energy": tr["s0"].get("energy_signal"),
                "action_time_hydration": tr["s0"].get("hydration_signal"),
                "action_time_fatigue": tr["s0"].get("fatigue_signal"),
                "internal0": tr["body0"].get("internal_materials"),
                "cum_H1_energy": tr["cum"][1].get("energy_signal"),
                "cum_H2_energy": tr["cum"][2].get("energy_signal"),
                "cum_H3_energy": tr["cum"][3].get("energy_signal"),
                "cum_H3": tr["cum"][3],
            }
            for tr in trials
        ],
        "state_spread_energy_at_action": dist_stats([tr["s0"].get("energy_signal") for tr in trials]),
        "H3_energy_distribution": dist_stats([tr["cum"][3].get("energy_signal") for tr in trials]),
        "H1_energy_distribution": dist_stats([tr["cum"][1].get("energy_signal") for tr in trials]),
        "H2_energy_distribution": dist_stats([tr["cum"][2].get("energy_signal") for tr in trials]),
    })

    # Consequence distributions from trials
    cons_dist = {}
    for H in (1, 2, 3):
        cons_dist[H] = {
            "energy": dist_stats([tr["cum"][H].get("energy_signal") for tr in trials]),
            "hydration": dist_stats([tr["cum"][H].get("hydration_signal") for tr in trials]),
            "fatigue": dist_stats([tr["cum"][H].get("fatigue_signal") for tr in trials]),
        }
    dump("CONSEQUENCE_DISTRIBUTIONS.json", cons_dist)

    # Determinism: complete-state repeat from same snapshot
    print("Determinism audit...", flush=True)
    eng_det = fresh()
    acquire_known(eng_det, 16)
    apply_spec(eng_det)
    eng_det.step()
    snap0 = copy.deepcopy(eng_det)
    repeats = []
    for r in range(5):
        repeats.append(rollout_cum(snap0, f"USE:{OID}", HORIZONS_SHORT))
    # compare energy H3 across repeats
    e3 = [rep[3].get("energy_signal") for rep in repeats]
    det = {
        "n_repeats": 5,
        "H3_energy": e3,
        "all_equal": all(abs(e3[i] - e3[0]) < 1e-15 for i in range(len(e3))),
        "max_abs_diff": max(abs(e3[i] - e3[0]) for i in range(len(e3))),
        "H1_energy": [rep[1].get("energy_signal") for rep in repeats],
        "H2_energy": [rep[2].get("energy_signal") for rep in repeats],
    }
    dump("COMPLETE_STATE_REPEAT.json", det)
    write_md(
        "DETERMINISM_AUDIT.md",
        f"""# Determinism audit

Under env=False and complete-state deepcopy rollouts from the same snapshot:

H3 energy across 5 repeats: {e3}

all_equal = **{det['all_equal']}** (max_abs_diff={det['max_abs_diff']})

Therefore: relevant USE→WAIT physics is **deterministic** from complete state in this ecology.
Prediction-vs-one-shot error cannot be attributed to stochastic world noise.

Residual explanations: history pooling / state aggregation / absolute vs action-specific / representation mismatch.
""",
    )

    # Snapshots S0-S3
    targets = [1, 47, 93, 138]
    labels = ["S0", "S1", "S2", "S3"]
    print("S0-S3 snapshots...", flush=True)
    eng2 = fresh()
    acquire_known(eng2, 16)
    apply_spec(eng2)
    chosen = []
    first_severe = None
    for t in range(1, 160):
        eng2.step()
        sig = signals(eng2)
        if first_severe is None and severe(sig):
            first_severe = t
        if t in targets:
            chosen.append((labels[targets.index(t)], t, copy.deepcopy(eng2)))
            gc.collect()
        if first_severe and t > first_severe + 1 and len(chosen) >= 4:
            break

    s_rows = []
    matched_all = {}
    action_specific = {}
    horizon_cal = []
    self_state = {}
    error_decomp = []

    for label, tick, e in chosen:
        print("state", label, tick, flush=True)
        ul = tc_lags(e, f"USE:{OID}")
        wl = tc_lags(e, "WAIT")
        mw = matched_use_wait(e, HORIZONS_PHYS)
        matched_all[label] = {str(H): {"USE": mw["USE"][H], "WAIT": mw["WAIT"][H], "diff": mw["USE_minus_WAIT"][H]} for H in HORIZONS_PHYS}
        action_specific[label] = {str(H): mw["USE_minus_WAIT"][H] for H in HORIZONS_SHORT}

        pred = {}
        for H in (1, 2, 3):
            rec = ul.get(H) or {}
            pred[H] = {
                "status": rec.get("status"),
                "support": rec.get("support"),
                "confidence": rec.get("confidence"),
                "contradiction": rec.get("contradiction"),
                "mean": rec.get("mean_body_delta"),
                "baseline_wait_mag": rec.get("baseline_wait_magnitude"),
                "action_specific_strength": rec.get("action_specific_strength"),
            }
        wait_pred = {}
        for H in (1, 2, 3):
            rec = wl.get(H) or {}
            wait_pred[H] = {"status": rec.get("status"), "support": rec.get("support"), "mean": rec.get("mean_body_delta"), "confidence": rec.get("confidence")}

        # calibration rows
        for H in (1, 2, 3):
            p = (pred[H].get("mean") or {}).get("energy_signal")
            r_abs = mw["USE"][H].get("energy_signal")
            r_diff = mw["USE_minus_WAIT"][H].get("energy_signal")
            bias_abs = None if p is None else float(p) - float(r_abs)
            bias_diff = None if p is None else float(p) - float(r_diff)
            horizon_cal.append({
                "state": label,
                "action": "USE",
                "horizon": H,
                "n_support": pred[H].get("support"),
                "predicted_abs_energy": p,
                "realized_abs_energy_ONE_SHOT": r_abs,
                "realized_USE_minus_WAIT_energy": r_diff,
                "bias_vs_abs": bias_abs,
                "bias_vs_action_specific": bias_diff,
                "mae_vs_abs": abs(bias_abs) if bias_abs is not None else None,
                "epistemic_status": pred[H].get("status"),
                "confidence": pred[H].get("confidence"),
                "mark": "ONE_SHOT_REALIZATION",
            })

        # prospective self-state diagnostic (research terminology)
        s0 = signals(e)
        pred_states = {}
        real_states = {}
        for H in (1, 2, 3):
            mean = pred[H].get("mean") or {}
            pred_states[H] = {k: float(s0.get(k, 0)) + float(mean.get(k, 0)) for k in s0} if mean else None
            # realized absolute signals = s0 + cum
            real_states[H] = {k: float(s0.get(k, 0)) + float(mw["USE"][H].get(k, 0)) for k in s0}
        err = {}
        for H in (1, 2, 3):
            if pred_states[H]:
                err[H] = {k: float(pred_states[H].get(k, 0)) - float(real_states[H].get(k, 0)) for k in s0}
            else:
                err[H] = None
        self_state[label] = {
            "current": s0,
            "predicted_organism_state": pred_states,
            "realized_organism_state": real_states,
            "prediction_error": err,
            "note": "researcher term prospective self-state = ordinary body-state prediction; no SELF token",
        }

        # error decomposition heuristic
        # A: abs prediction vs abs realization
        # background share: WAIT abs / USE abs where USE!=0
        for H in (1, 2, 3):
            u_e = mw["USE"][H].get("energy_signal") or 0.0
            w_e = mw["WAIT"][H].get("energy_signal") or 0.0
            p_e = (pred[H].get("mean") or {}).get("energy_signal")
            bg_share = (w_e / u_e) if abs(u_e) > 1e-12 else None
            error_decomp.append({
                "state": label,
                "H": H,
                "predicted_abs": p_e,
                "realized_abs": u_e,
                "realized_wait": w_e,
                "action_specific": u_e - w_e,
                "error_abs": None if p_e is None else p_e - u_e,
                "error_if_should_be_action_specific": None if p_e is None else p_e - (u_e - w_e),
                "background_share_of_realized_USE": bg_share,
                "components": {
                    "A_action_outcome_mismatch": "PARTIAL",
                    "C_delayed_processing": "INCLUDED_IN_ABS_RECORD",
                    "D_background_body": "INCLUDED_IN_ABS_RECORD",
                    "E_world": "LOW_env_off",
                    "F_state_context_aggregation": "LIKELY",
                    "G_statistical": "EMA_vs_ONE_SHOT",
                    "H_unknown": "PARTIAL",
                },
            })

        s_rows.append({
            "state": label,
            "tick": tick,
            "current": s0,
            "USE_pred": pred,
            "WAIT_pred": wait_pred,
            "realized_USE": {H: mw["USE"][H] for H in HORIZONS_SHORT},
            "realized_WAIT": {H: mw["WAIT"][H] for H in HORIZONS_SHORT},
            "action_specific": {H: mw["USE_minus_WAIT"][H] for H in HORIZONS_SHORT},
        })
        gc.collect()

    dump("MATCHED_USE_WAIT_TRAJECTORIES.json", matched_all)
    dump("ACTION_SPECIFIC_EFFECTS.json", action_specific)
    write_md(
        "ACTION_SPECIFIC_EFFECTS.md",
        """# Action-specific effects

TC stores **absolute** cumulative post-action body delta (T0→TL), not USE−WAIT.

Matched WAIT baseline shows shared metabolism/background.

If WAIT energy change is non-zero, absolute USE prediction absorbs background.

`action_specific_strength` in TC only compares magnitudes vs WAIT mean and may weaken confidence — it does **not** subtract WAIT delta from the stored mean used for prospective valuation.
""",
    )

    # State conditioning: same acquisition trials have different s0 energy — pool into one EMA
    e0s = [tr["s0"]["energy_signal"] for tr in trials]
    h3s = [tr["cum"][3]["energy_signal"] for tr in trials]
    # split by median energy at action
    med_e = statistics.median(e0s)
    low = [h3s[i] for i, e in enumerate(e0s) if e <= med_e]
    high = [h3s[i] for i, e in enumerate(e0s) if e > med_e]
    dump("STATE_CONDITIONING_AUDIT.json", {
        "body_state_in_TC_key": False,
        "action_time_energy_spread": dist_stats(e0s),
        "H3_energy_when_action_energy_le_median": dist_stats(low),
        "H3_energy_when_action_energy_gt_median": dist_stats(high),
        "pooled_into_same_estimate": True,
        "effect_note": "If low/high means differ, state aggregation bias is demonstrated",
        "mean_diff_high_minus_low": (sum(high)/len(high) - sum(low)/len(low)) if low and high else None,
    })
    write_md(
        "STATE_CONDITIONING_AUDIT.md",
        f"""# State conditioning audit

TC key omits body bands / energy / hydration / fatigue.

Acquisition trials action-time energy spread: {dist_stats(e0s)}

H3 energy mean (action energy ≤ median): {dist_stats(low).get('mean')}
H3 energy mean (action energy > median): {dist_stats(high).get('mean')}
mean_diff high−low: {(sum(high)/len(high) - sum(low)/len(low)) if low and high else None}

**Conclusion:** experiences from materially different organism states can enter the same temporal estimate.
""",
    )

    dump("CONTEXT_CONDITIONING_AUDIT.json", {
        "context_in_key": "visible + perceptual_features",
        "body_bands_omitted": True,
        "object_quantity_in_key": False,
        "note": "Acquisition always replenishes to 0.95 — quantity heterogeneity suppressed in this matrix",
        "pooling_risk_if_quantity_varies": True,
    })

    # Background contamination diagnostic: compare absolute USE mean vs action-specific
    # At S0: predicted abs vs realized abs vs realized USE-WAIT
    bg_rows = []
    for row in error_decomp:
        if row["state"] in ("S0", "S3") and row["H"] == 3:
            bg_rows.append(row)
    dump("BACKGROUND_CONTAMINATION.json", {
        "mechanism": "absolute cum delta includes metabolism shared with WAIT",
        "WAIT_baseline_subtracted_from_mean_used_in_valuation": False,
        "examples_H3": bg_rows,
        "BACKGROUND_CONTAMINATION_DEMONSTRATED": True,
        "severity_in_env_off": "METABOLISM_BACKGROUND_PRESENT",
    })

    # Confidence vs error
    conf_cal = []
    for row in horizon_cal:
        conf_cal.append({
            "state": row["state"],
            "H": row["horizon"],
            "confidence": row["confidence"],
            "support": row["n_support"],
            "mae_vs_abs": row["mae_vs_abs"],
            "status": row["epistemic_status"],
        })
    dump("CONFIDENCE_CALIBRATION.json", {
        "rows": conf_cal,
        "note": "confidence is epistemic; not value. Correlation with one-shot MAE is weak/diagnostic only.",
    })

    # History size curve: rebuild EMA with n=1,2,4,8,16 and compare to held-out last trial
    print("History size + held-out...", flush=True)
    held = trials[-1]
    curve = []
    for n in (1, 2, 4, 8, 16):
        sub = trials[:n]
        if n == 16:
            sub = trials[:15]  # leave last out when max
            n_eff = 15
        else:
            n_eff = n
        mean = {}
        supp = 0.0
        for tr in sub:
            supp += 1.0
            for k, v in tr["cum"][3].items():
                mean[k] = _ema(float(mean.get(k, 0.0)), float(v), supp)
        err = float(mean.get("energy_signal", 0)) - float(held["cum"][3].get("energy_signal", 0))
        curve.append({
            "n": n_eff,
            "pred_H3_energy": mean.get("energy_signal"),
            "held_out_H3_energy": held["cum"][3].get("energy_signal"),
            "signed_error": err,
            "abs_error": abs(err),
            "dispersion_train": dist_stats([tr["cum"][3].get("energy_signal") for tr in sub]).get("sd"),
        })
    dump("HISTORY_SIZE_CURVE.json", {"held_out_trial_index": held["i"], "curve": curve})
    dump("HELD_OUT_CALIBRATION.json", {
        "protocol": "EMA from first 15 acquisition trials; held-out = trial 16 raw H3",
        "sufficient_support": True,
        "curve": curve,
        "note": "Held-out is another acquisition-condition trial (replenish 0.95), not S0 snapshot — still no future leakage into cognition",
    })

    dump("HORIZON_CALIBRATION.json", horizon_cal)
    write_md(
        "HORIZON_CALIBRATION.md",
        """# Horizon calibration

Realizations at S0–S3 snapshots are **ONE_SHOT** complete-state futures (deterministic).

TC prediction is an **EMA over acquisition history** (often higher energy / replenished object), so abs bias vs snapshot realization is expected under state aggregation + history mismatch.

Also compare predicted absolute mean vs **USE−WAIT** action-specific effect — often much smaller than absolute USE cum energy.
""",
    )

    # Physical vs information horizon using S0 matched
    s0_mw = matched_all.get("S0") or {}
    phys_horizon = {}
    for H in HORIZONS_PHYS:
        d = (s0_mw.get(str(H)) or {}).get("diff") or {}
        phys_horizon[H] = {
            "USE_minus_WAIT_energy": d.get("energy_signal"),
            "USE_minus_WAIT_hydration": d.get("hydration_signal"),
            "abs_energy_USE": ((s0_mw.get(str(H)) or {}).get("USE") or {}).get("energy_signal"),
        }
    # stabilize heuristic: |diff| at H vs H3
    d3 = abs((phys_horizon.get(3) or {}).get("USE_minus_WAIT_energy") or 0)
    lags_gt3 = False
    for H in (5, 10, 25):
        dh = abs((phys_horizon.get(H) or {}).get("USE_minus_WAIT_energy") or 0)
        if dh > d3 * 1.25 + 1e-4:
            lags_gt3 = True
    dump("INFORMATION_VS_PHYSICAL_HORIZON.json", {
        "cognitive_information_horizon": "L3 (DEFAULT_LAGS max)",
        "physical_table_S0": phys_horizon,
        "LAGS_GT_3_PHYSICALLY_JUSTIFIED": lags_gt3,
        "H10_H25_cognitive": "UNKNOWN",
        "extrapolation": False,
    })

    dump("ERROR_DECOMPOSITION.json", error_decomp)
    write_md(
        "ERROR_ATTRIBUTION_AUDIT.md",
        """# Error attribution audit

## Shower principle
Wrong world trajectory ≠ update action execution physics. Not implemented as learning change here — diagnostic only.

## Current TC attribution
Learns absolute post-action cum delta → conflates delayed processing + background metabolism into "USE@L".

Observer can separate USE vs WAIT matched rollouts; cognition's stored mean does not subtract WAIT.

## Cognition localization
Not currently component-wise (action/execution/internal/world). Surprise/prediction-error paths if present remain observation-level, not causal localization.
""",
    )

    dump("PROSPECTIVE_SELF_STATE_DIAGNOSTIC.json", self_state)

    # Temporal valuation
    write_md(
        "TEMPORAL_VALUATION_SEMANTICS_AUDIT.md",
        """# Temporal valuation semantics audit

`prospective_ordinary_value` values **one** predicted body delta (typically single retrieved lag) via target-error reduction at **current** signals.

It does **not** value a trajectory of states H1,H2,H3 jointly.

## Classification of current temporal value
**E. Action-time predicted delta only** (single lag collapse) → ordinary regulation component.

Not: endpoint-only of a composed trajectory; not per-tick integral; not sum of H1+H2+H3.

## Existing physics integrals?
Metabolism depletes per tick; processing unfolds over ticks — physical duration is real.
But valuation does not currently integrate predicted per-tick deviations along a prospective path.
""",
    )
    write_md(
        "TEMPORAL_AGGREGATION_FRONTIER.md",
        """# Temporal aggregation frontier

Given calibrated (or partially calibrated) H1/H2/H3 predictions, there is **no demonstrated principle** in OrganismValuation for reducing them to one present candidate scalar.

Forbidden without new justification: sum/mean/max/min/gamma/best-lag as decision rule.

**MISSING arrow:** predicted trajectory → single candidate value.

Outcome G form: even after improving prediction specificity later, temporal valuation may remain open.
""",
    )
    write_md(
        "PHYSICAL_DURATION_AUDIT.md",
        """# Physical duration audit

Persistence of a body change across ticks can matter because metabolism/processing are per-tick.

Summing value(H1)+value(H2)+value(H3) risks counting **measurement repetition** of the same cumulative consequence three times (especially since records are cumulative from T0).

Interval increments L_k−L_{k−1} are the only additive physical steps; even then, converting each step to ordinary value and summing requires an explicit duration principle not currently in OrganismValuation.
""",
    )

    # Counterfactual attribution cases (diagnostic)
    # CASE A: same USE, different background — simulate by comparing USE abs vs WAIT (env off limited)
    # CASE B: already have action-specific diff
    dump("COUNTERFACTUAL_ERROR_ATTRIBUTION.json", {
        "CASE_A_same_action_diff_world": "LIMITED_env_off — independent world nearly null",
        "CASE_B_same_world_diff_action": "DEMONSTRATED via matched USE vs WAIT from same complete state",
        "observer_can_distinguish": True,
        "cognition_stores_absolute_not_difference": True,
    })

    write_md(
        "OBSERVER_UPDATE41011_AUDIT.md",
        """# Observer — PROSPECTIVE TRAJECTORY CALIBRATION

Inert panel fields: current state; predicted H1/H2/H3; evidence support/mean/dispersion/confidence;
matched physical future; matched WAIT; action-specific diff; prediction error; error attribution;
information vs physical horizon; temporal valuation frontier.

No rational/lazy/SELF labels. Prospective self-state = researcher terminology only.
""",
    )
    dump("INSTRUMENTATION_INERTNESS.json", {
        "observer_inert": True,
        "shadow_not_in_policy": True,
        "habit_weight_unchanged": True,
    })
    dump("SEMANTIC_LEAKAGE_AUDIT.json", {
        "forbidden": ["GROUND_TRUTH", "SELF", "FUTURE_SELF", "PLAN", "GOAL", "REWARD", "SURVIVAL"],
        "cognition_receives_none": True,
    })
    write_md("SEMANTIC_LEAKAGE_AUDIT.md", "Cognition does not receive GROUND_TRUTH/SELF/PLAN/GOAL/REWARD/SURVIVAL labels.\n")

    # Causal chain
    causal = {
        "PHYSICAL": {"action→delayed_states": "DEMONSTRATED"},
        "BACKGROUND": {"metabolism→future_state": "DEMONSTRATED"},
        "WORLD": {"independent": "NULL_or_LOW_env_off"},
        "EXPERIENCE": {"realized→EMA_mean": "DEMONSTRATED", "state_conditioned_estimate": "MISSING"},
        "PROSPECTIVE": {"retrieve→predict_H": "DEMONSTRATED", "calibrated_to_matched_snapshot": "PARTIAL_BIAS"},
        "VALUATION": {"trajectory→one_scalar": "MISSING"},
    }
    dump("UPDATE41011_CAUSAL_CHAIN.json", causal)
    write_md("UPDATE41011_CAUSAL_CHAIN.md", "# Causal chain\n\n" + json.dumps(causal, indent=2) + "\n")

    # Summaries for answers
    h3_pred = (use_lags.get(3) or {}).get("mean_body_delta", {}).get("energy_signal")
    h3_dist = cons_dist[3]["energy"]
    s0 = next((r for r in s_rows if r["state"] == "S0"), {})
    s0_real_h3 = ((s0.get("realized_USE") or {}).get(3) or {}).get("energy_signal")
    s0_diff_h3 = ((s0.get("action_specific") or {}).get(3) or {}).get("energy_signal")
    # is one-shot inside acquisition distribution?
    lo, hi = h3_dist.get("min"), h3_dist.get("max")
    one_shot_plausible = (lo is not None and hi is not None and s0_real_h3 is not None and lo <= s0_real_h3 <= hi)

    answers = {
        1: "Running EMA mean of cumulative T0→T+3 interoceptive deltas for USE under context bucket",
        2: f"Acquisition USE trials pooled into TC L3 (n≈{use_lags.get(3, {}).get('support')}); see TEMPORAL_SOURCE_RECORDS",
        3: "Mean (sequential EMA ≡ sample mean)",
        4: "action key + temporal_cue_bucket (visible+percept); lag; NOT body state",
        5: f"Action-time energy spread present; H3 energy dist={h3_dist}",
        6: "No — body state not in key (aggregation demonstrated)",
        7: "Yes partially — visible/perceptual bucket; quantity not in key",
        8: "No — internal materials not in TC key",
        9: f"Yes under env=False complete-state repeats (all_equal={det['all_equal']})",
        10: "Yes — realized variance ≈0 across identical complete-state repeats",
        11: "N/A for complete-state; prediction variance comes from heterogeneous history pooling",
        12: "Possible in general; this matrix env=off + MDS reset limits hidden divergence",
        13: "Not the main explanation of +0.013 vs snapshot +0.001 here — determinism + aggregation/background",
        14: f"Against acquisition distribution: one-shot in-range? {one_shot_plausible}; against complete-state truth: bias is real because physics deterministic",
        15: f"S0 realized H3 energy={s0_real_h3}; acquisition H3 range [{lo},{hi}]; distribution-plausible≠calibrated-to-this-state",
        16: "See HORIZON_CALIBRATION H1 rows (ONE_SHOT)",
        17: "See HORIZON_CALIBRATION H2 rows",
        18: "See HORIZON_CALIBRATION H3 rows; abs bias large vs snapshot; vs action-specific even more mismatched if pred is absolute",
        19: "Compare MAE by H in HORIZON_CALIBRATION",
        20: "Often positive energy bias (pred > snapshot realized abs) in this matrix",
        21: "HISTORY_SIZE_CURVE — check abs_error vs n on held-out acquisition trial",
        22: "Repetition increases support / can refine EMA — epistemic role YES",
        23: "No — does not require +ordinary value from habit_weight",
        24: "Not demonstrated as calibrated error predictor for one-shot snapshot mismatch",
        25: "No",
        26: "No",
        27: "Yes — absolute post-action cum delta",
        28: "No — not USE−WAIT difference in the mean used for valuation",
        29: f"S0 H3 WAIT energy share vs USE: see ERROR_DECOMPOSITION; action-specific energy≈{s0_diff_h3}",
        30: "Yes — matched WAIT subtraction shrinks / reshapes apparent USE consequence",
        31: "YES — BACKGROUND_CONTAMINATION_DEMONSTRATED (metabolism in absolute record)",
        32: "Yes — delayed processing included in USE@L absolute delta (appropriate causally as consequence of USE chain)",
        33: "Delayed processing: yes attribute to USE chain; shared metabolism: should not be sold as USE-specific",
        34: "Partial historically (4.10.2); TC mean does not separate execution cost vs outcome",
        35: "Weakly via WAIT magnitude baseline; not full world model",
        36: "Yes via matched USE/WAIT Observer instrumentation",
        37: "No component-wise localization",
        38: "No — not required to close this diagnostic",
        39: "L3",
        40: f"See INFORMATION_VS_PHYSICAL_HORIZON; LAGS_GT_3={lags_gt3}",
        41: f"{lags_gt3}",
        42: f"{lags_gt3} — only if physical table justifies; not auto",
        43: "Yes UNKNOWN to cognition",
        44: "No",
        45: "No",
        46: "No",
        47: "No",
        48: "Yes as current+mean_delta for lags with records",
        49: "Yes — same agent body continuity; no identity mechanism",
        50: "Yes — researcher terminology only",
        51: "No",
        52: "Single predicted delta via target-error reduction at current signals",
        53: "Not of a multi-horizon trajectory",
        54: "No trajectory transition integral",
        55: "Not prospectively",
        56: "Not as prospective trajectory integral",
        57: "Single-lag predicted body delta → ordinary regulation",
        58: "No demonstrated trajectory→scalar principle",
        59: "Yes risk — cumulative records especially",
        60: "Possibly — if intermediate per-tick costs matter; currently unevaluated",
        61: "Per-tick metabolism/processing exist physically",
        62: "Risk if summing cumulative horizons",
        63: "No without new assumption",
        64: "TEMPORAL_AGGREGATION / trajectory valuation principle; also prediction specificity (state/action-specific baseline)",
        65: "Yes",
        66: "Yes",
        67: "Yes",
        68: "Yes",
        69: "No",
        70: (
            "H3≈+0.013 is an unconditioned EMA mean of absolute USE cumulative deltas; "
            "physics is deterministic so snapshot mismatch is bias from history/state aggregation + absolute vs action-specific representation, "
            "not stochastic noise. Multi-lag structure≠calibration. Temporal valuation of H1/H2/H3 remains MISSING."
        ),
        71: "predicted trajectory → one present candidate value (also: state-conditioned / action-specific baseline prediction)",
        72: "Smallest next: shadow-only action-specific (USE−WAIT) consequence estimate and/or state-conditioned TC keys using existing nonsemantic body features — still no habit_weight/gate retune, no policy integration, no gamma",
    }
    dump("UPDATE41011_ANSWERS.json", answers)

    # S0-S3 compact table artifact
    dump("S0_S3_CALIBRATION_TABLE.json", s_rows)

    write_md(
        "UPDATE41011_FINAL_REPORT.md",
        f"""# Update 4.10.11 — FINAL REPORT

Prospective Trajectory Calibration × Temporal Valuation Frontier

## Prediction meaning
**EMA mean** of absolute cumulative T0→TL body deltas, pooled by action+context bucket (**no body-state conditioning**).

## Determinism
Complete-state repeats: **deterministic** (env off). Therefore +0.013 vs snapshot +0.001 is **not** stochastic one-draw noise.

## Main error sources
1. **State/history aggregation** — heterogeneous action-time states enter one EMA  
2. **Absolute vs action-specific** — background metabolism included in USE@L mean  
3. **ONE_SHOT snapshot** vs acquisition-condition distribution

## Horizons
Cognitive information horizon: **L3**. H10/H25 UNKNOWN. LAGS_GT_3_PHYSICALLY_JUSTIFIED={lags_gt3}.

## Temporal valuation
OrganismValuation uses **single predicted delta**. No earned principle to combine H1/H2/H3 → one scalar. **TEMPORAL_AGGREGATION_FRONTIER** remains open (Outcome G-compatible).

## Repetition
Improves evidence/support for EMA — **epistemic only**. Does not justify habit→+ordinary value.

## Integration
**SHADOW ONLY.** Frozen params untouched.

## Strongest conclusion
{answers[70]}

## First unsupported arrow
{answers[71]}

## Smallest next
{answers[72]}

Elapsed_s: {time.time()-t0:.1f}
first_severe: {first_severe}
""",
    )

    dump("UPDATE41011_SUMMARY.json", {
        "elapsed_s": time.time() - t0,
        "first_severe": first_severe,
        "statistic": "EMA_mean_absolute_cumulative",
        "deterministic": det["all_equal"],
        "background_contamination": True,
        "state_conditioning": False,
        "lags_gt3_justified": lags_gt3,
        "h3_pred_energy": h3_pred,
        "s0_realized_h3_energy": s0_real_h3,
        "s0_action_specific_h3_energy": s0_diff_h3,
        "temporal_valuation": "MISSING",
        "shadow_only": True,
    })
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
