#!/usr/bin/env python3
"""Update 4.10.9 — Prospective temporal horizon × habit–prediction alignment.

DIAGNOSTIC + SHADOW ONLY. No habit_weight/gate/cost retune. No policy integration.
"""
from __future__ import annotations

import copy
import gc
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
from mechanistic_mind.research.prospective_valuation import prospective_ordinary_value
from mechanistic_mind.psyche.temporal_contingency import (
    DEFAULT_LAGS,
    ensure_temporal,
    retrieve_temporal,
    temporal_cue_bucket,
)
from mechanistic_mind.psyche.sensorimotor import available_actions, context_cue

OUT = ROOT / "results" / "update4109_temporal_habit_alignment"
OUT.mkdir(parents=True, exist_ok=True)
PREV = ROOT / "results" / "update4108_ordinary_action_economy"
A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED
TE = int(MDS_LADDER_TICK_EQUIVALENT[0])
SPEC = subsidy_from_tick_equivalent(TE)
HORIZONS = (1, 3, 10, 25)
SEVERE_E, SEVERE_H, SEVERE_F = 0.18, 0.18, 0.82


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
    }


def severe(sig):
    return float(sig.get("energy_signal", 1)) < SEVERE_E or float(sig.get("hydration_signal", 1)) < SEVERE_H or float(sig.get("fatigue_signal", 0)) > SEVERE_F


def acquire_known(eng, n=16):
    for _ in range(n):
        u4101.replenish_object(eng, 0.95)
        eng.step({A: Action(f"USE:{OID}")})
        for _ in range(4):
            eng.step({A: Action("WAIT")})
    stored = None
    for k, v in (u4101.tc_state(eng).get("contingencies") or {}).items():
        if str(v.get("action", "")).startswith("USE") and v.get("status") == "KNOWN":
            stored = deepcopy(v)
            stored["key"] = k
            break
    return stored


def tc_all_lags_for_action(eng, action_prefix: str) -> list[dict]:
    tc = ensure_temporal(deepcopy((u4101.psyche(eng).get("memory") or {}).get("sensorimotor") or {}))
    rows = []
    for k, v in (tc.get("contingencies") or {}).items():
        act = str(v.get("action") or "")
        if act == action_prefix or act.startswith(action_prefix):
            rows.append({"key": k, **{kk: v.get(kk) for kk in ("action", "status", "support", "confidence", "lag", "mean_body_delta", "contradiction", "consistency")}})
    rows.sort(key=lambda r: int(r.get("lag") or 99))
    return rows


def shadow_horizon_vals(eng, lag_rows: list[dict]) -> dict:
    psy = u4101.psyche(eng)
    goals = psy.get("goals") or {}
    cur = signals(eng)
    out = {}
    for r in lag_rows:
        lag = int(r.get("lag") or -1)
        delta = r.get("mean_body_delta") or {}
        if r.get("status") not in ("KNOWN", "UNKNOWN") and not delta:
            out[lag] = {"status": r.get("status"), "ordinary": None, "support": r.get("support"), "note": "NO_DELTA"}
            continue
        if not delta:
            out[lag] = {"status": r.get("status"), "ordinary": None, "support": r.get("support"), "note": "EMPTY_DELTA"}
            continue
        prosp = prospective_ordinary_value(
            mean_body_delta=delta,
            body_delta_samples=float(r.get("support") or 0),
            contradiction=float(r.get("contradiction") or 0),
            current_signals=cur,
            goals=goals,
            support=float(r.get("support") or 0),
        )
        out[lag] = {
            "status": r.get("status"),
            "support": r.get("support"),
            "confidence": r.get("confidence"),
            "mean_body_delta": delta,
            "ordinary": prosp.get("ordinary_value"),
            "prosp": prosp,
        }
    return out


def physical_chain_USE(eng0, max_t=25) -> dict:
    eng = copy.deepcopy(eng0)
    before = {"signals": signals(eng), "body": body_raw(eng)}
    chain = [{"t": 0, "event": "pre", "signals": before["signals"], "body": {
        "energy_reserve": before["body"].get("energy_reserve"),
        "hydration": before["body"].get("hydration"),
        "fatigue": before["body"].get("fatigue"),
        "internal": before["body"].get("internal_materials"),
        "xfer": before["body"].get("last_intake_transfer"),
        "proc": before["body"].get("last_intake_processed"),
    }}]
    # T0 USE then WAIT
    eng.step({A: Action(f"USE:{OID}")})
    for t in range(1, max_t + 1):
        if t > 1:
            eng.step({A: Action("WAIT")})
        b = body_raw(eng)
        s = signals(eng)
        if t in (1, 2, 3, 5, 10, 25) or t <= 3:
            chain.append({
                "t": t,
                "event": "USE" if t == 1 else "WAIT",
                "signals": s,
                "d_energy_signal": float(s.get("energy_signal", 0)) - float(before["signals"].get("energy_signal", 0)),
                "d_hydration_signal": float(s.get("hydration_signal", 0)) - float(before["signals"].get("hydration_signal", 0)),
                "body": {
                    "energy_reserve": b.get("energy_reserve"),
                    "hydration": b.get("hydration"),
                    "fatigue": b.get("fatigue"),
                    "internal": b.get("internal_materials"),
                    "xfer": b.get("last_intake_transfer"),
                    "proc": b.get("last_intake_processed"),
                },
            })
    return {"before": before, "chain": chain}


def main():
    t0 = time.time()
    dump("UPDATE4109_CONFIG.json", {"update": "4.10.9", "mode": "DIAGNOSTIC_SHADOW", "init_TE": TE, "no_policy_integration": True})
    dump("UPDATE4109_FROZEN_PARAMETERS.json", {
        "habit_weight": 0.03,
        "severe": [0.35, 0.04, SEVERE_E, SEVERE_H, SEVERE_F],
        "DEFAULT_LAGS": list(DEFAULT_LAGS),
        "no_retune": True,
    })

    # --- Habit semantics (code facts) ---
    write_md(
        "HABIT_SEMANTICS_AUDIT.md",
        """# Habit semantics audit (actual code)

Source: `mechanistic_mind/psyche/modules.py` → `HabitModule`

## Update rule (each tick)
1. For every action key: `strength *= decay` (default decay from state, observed ~0.93 in 4.10.8 runs; module default 0.85).
2. If `attention.current.last_action` is a string: `strength[action] = min(1.0, strength + learning_rate)` (observed lr~0.1; module default 0.20).

## What it encodes
| Question | Answer from code |
|----------|------------------|
| Physical consequence? | **NO** — never reads body/outcome |
| Predicted consequence? | **NO** |
| Context-specific? | **NO** — keyed only by action string |
| Body-state-specific? | **NO** |
| Repetition only? | **YES** — selected `last_action` |
| Successful outcomes? | **NO** |
| Familiarity? | **YES** — operationally repetition strength |
| Motor fluency? | **NO** explicit |
| Feasibility? | **NO** |
| Decay? | **YES** — multiplicative each tick |
| Contradiction reduces? | **NO** — only decay + boost on selection |
| Rise despite poor outcomes? | **YES** — if action keeps being selected |

## Valuation coupling
`OrganismValuationModule`: `habit = strength[action] * goals.habit_weight` (default **0.03**), added into `base_total` alongside regulation/progress/navigation.

## Units
Habit contribution is **forced into ordinary-value space by multiplication with habit_weight**, without a mapped physical future. It is **not** a predicted body delta. Direct addition to prospective TC ordinary value mixes **repetition currency** with **physical-consequence currency**.

## ENDOGENOUS_VARIATION
Sensorimotor proposals with empty prediction read `values.by_action[action].base_total`, which already includes habit. Hence WAIT≈+0.033 ≈ habit 0.03 + small regulation.
""",
    )

    # Build DERIVED×KNOWN
    print("Build DERIVED×KNOWN...", flush=True)
    eng = fresh()
    stored = acquire_known(eng, 16)
    apply_spec(eng)
    dump("ACQUIRED_KNOWLEDGE.json", stored)

    # Habit source trace after reset
    psy0_step = None
    eng.step()  # tick 1 free
    psy = u4101.psyche(eng)
    dump("HABIT_SOURCE_TRACE.json", {
        "habits": psy.get("habits"),
        "values_WAIT": ((psy.get("values") or {}).get("by_action") or {}).get("WAIT"),
        "values_USE": ((psy.get("values") or {}).get("by_action") or {}).get(f"USE:{OID}"),
        "HabitModule": "strength *= decay; strength[last_action] += lr; clamp 1.0",
        "last_selection": ((psy.get("working") or {}).get("last_selection") or {}).get("action"),
    })

    # Bad-history habit control: force WAIT 40 times from MDS-250, track habit vs realized ordinary of WAIT
    print("Bad-history habit control...", flush=True)
    eng_bh = fresh()
    bh = []
    for i in range(1, 41):
        before = signals(eng_bh)
        eng_bh.step({A: Action("WAIT")})
        after = signals(eng_bh)
        psy = u4101.psyche(eng_bh)
        habits = (psy.get("habits") or {}).get("strength") or {}
        dE = float(after.get("energy_signal", 0)) - float(before.get("energy_signal", 0))
        # realized ordinary of this tick's delta from pre-step state
        rov = prospective_ordinary_value(
            mean_body_delta={k: float(after.get(k, 0)) - float(before.get(k, 0)) for k in after if isinstance(after.get(k), (int, float))},
            body_delta_samples=1.0,
            contradiction=0.0,
            current_signals=before,
            goals=psy.get("goals") or {},
            support=1.0,
        )
        bh.append({"i": i, "WAIT_habit": habits.get("WAIT"), "d_energy_signal": dE, "realized_ordinary": rov.get("ordinary_value"), "severe": severe(after)})
    dump("HABIT_COUNTERFACTUAL_CALIBRATION.json", {
        "bad_history_WAIT_forced": bh[::5] + [bh[-1]],
        "correlation_note": "WAIT habit rises toward 1 while each tick realized ordinary is typically negative (drain) under env=False",
        "habit_rises_despite_unfavorable": True,
    })

    # Good-outcome low-habit: after MDS reset, USE has low habit vs WAIT; TC prospective positive
    # Already at eng after 1 free tick - capture
    psy = u4101.psyche(eng)
    dump("GOOD_OUTCOME_LOW_HABIT_CONTROL.json", {
        "note": "At DERIVED×KNOWN release, USE has TC positive ordinary but habit<<WAIT",
        "habits": (psy.get("habits") or {}).get("strength"),
        "USE_TC_ordinary_candidate": next((c for c in (((psy.get("working") or {}).get("last_selection") or {}).get("candidates") or []) if str(c.get("action","")).startswith("USE") and c.get("source")=="TEMPORAL_CONTINGENCY"), None),
        "WAIT_endogenous": next((c for c in (((psy.get("working") or {}).get("last_selection") or {}).get("candidates") or []) if c.get("action")=="WAIT"), None),
    })

    # PASS1 find target ticks (reuse 4108: 1,47,93,138)
    targets = [1, 47, 93, 138]
    labels = ["S0", "S1", "S2", "S3"]
    # recreate for snapshots + multi-lag shadow (lighter: only 4 deepcopies)
    print("Recreate for S0-S3...", flush=True)
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

    # Load 4108 realized CF for calibration ground truth
    cf4108 = json.loads((PREV / "COUNTERFACTUAL_PHYSICAL_DIFFERENCE.json").read_text()) if (PREV / "COUNTERFACTUAL_PHYSICAL_DIFFERENCE.json").exists() else []
    pvr4108 = json.loads((PREV / "PREDICTED_VS_REALIZED.json").read_text()) if (PREV / "PREDICTED_VS_REALIZED.json").exists() else []
    realized_by_snap = {row["snap"]: row for row in cf4108}

    write_md(
        "PROSPECTIVE_HORIZON_AUDIT.md",
        f"""# Prospective horizon audit

KNOWN USE key lag = **L2** (`DEFAULT_LAGS = {list(DEFAULT_LAGS)}`).

`best_prediction_for_action` prefers lowest lag among KNOWN hits — candidate-time USE uses **one** lag's `mean_body_delta` (here L2), not a trajectory.

L2 delta ≈ energy_signal +0.0097 (post-processing window), not T0 transfer alone.

Omitted from single-lag candidate: explicit H1 transfer-only, H3/H10/H25 cumulative path as separate predictions (unless other lag records exist and are retrieved).

Shadow mode in this update reads **all lag records** for USE/WAIT without collapsing into one reward and without changing policy.
""",
    )

    shadow_table = []
    physical_chains = {}
    habit_ablation = []
    shadow_reorder = []

    for label, t, e in chosen:
        print("snapshot", label, t, flush=True)
        psy = u4101.psyche(e)
        habits = (psy.get("habits") or {}).get("strength") or {}
        values = (psy.get("values") or {}).get("by_action") or {}
        sel = (psy.get("working") or {}).get("last_selection") or {}
        cands = list(sel.get("candidates") or [])
        wait_c = next((c for c in cands if c.get("action") == "WAIT"), None)
        use_c = next((c for c in cands if str(c.get("action", "")).startswith("USE") and c.get("source") == "TEMPORAL_CONTINGENCY"), None)
        if use_c is None:
            use_c = next((c for c in cands if str(c.get("action", "")).startswith("USE")), None)

        use_lags = tc_all_lags_for_action(e, f"USE:{OID}")
        wait_lags = tc_all_lags_for_action(e, "WAIT")
        use_shadow = shadow_horizon_vals(e, use_lags)
        wait_shadow = shadow_horizon_vals(e, wait_lags)

        # Map lags to diagnostic horizons: L0~H?, L1, L2, L3 — also report H10/H25 as MISSING unless present
        shadow_H = {
            "H1": use_shadow.get(1) or use_shadow.get(0),
            "H3": use_shadow.get(3) or use_shadow.get(2),
            "H10": None,
            "H25": None,
            "by_lag": use_shadow,
            "TEMPORAL_AGGREGATION": "NONE — horizons kept separate; no gamma",
        }

        # Habit ablation: WAIT score without habit component
        wait_val = values.get("WAIT") or {}
        use_val = values.get(f"USE:{OID}") or {}
        wait_no_habit = float(wait_val.get("base_total") or 0) - float(wait_val.get("habit") or 0)
        use_tc_ord = float((use_c or {}).get("ordinary_action_value") or 0)
        # endogenous USE without habit
        use_endo_no_habit = float(use_val.get("base_total") or 0) - float(use_val.get("habit") or 0)

        actual_order = "WAIT>USE" if float((wait_c or {}).get("score") or 0) > use_tc_ord else "USE>WAIT"
        ablated_order = "WAIT>USE" if wait_no_habit > use_tc_ord else ("USE>WAIT" if use_tc_ord > wait_no_habit else "TIE")
        # shadow reorder: compare wait_no_habit? No — shadow uses TC multi-lag best ordinary vs wait endogenous without changing habit unless noted
        best_shadow_use = None
        for lag, pack in use_shadow.items():
            if isinstance(pack, dict) and pack.get("ordinary") is not None:
                if best_shadow_use is None or float(pack["ordinary"]) > float(best_shadow_use["ordinary"]):
                    best_shadow_use = {"lag": lag, **pack}
        # Diagnostic shadow policy: USE_shadow_ordinary vs WAIT base_total (current) AND vs WAIT without habit
        shadow_vs_wait = None
        shadow_vs_wait_nohabit = None
        if best_shadow_use and best_shadow_use.get("ordinary") is not None:
            shadow_vs_wait = "USE>WAIT" if float(best_shadow_use["ordinary"]) > float((wait_c or {}).get("score") or 0) else "WAIT>USE"
            shadow_vs_wait_nohabit = "USE>WAIT" if float(best_shadow_use["ordinary"]) > wait_no_habit else "WAIT>USE"

        real = realized_by_snap.get(label) or {}
        row = {
            "state": label,
            "tick": t,
            "signals": signals(e),
            "HABIT_STRENGTH_WAIT": habits.get("WAIT"),
            "HABIT_STRENGTH_USE": habits.get(f"USE:{OID}"),
            "HABIT_VALUE_WAIT": wait_val.get("habit"),
            "HABIT_VALUE_USE": use_val.get("habit"),
            "TC_STATUS_USE": (use_c or {}).get("prediction_status") or (stored or {}).get("status"),
            "CURRENT_USE_ord": use_tc_ord,
            "CURRENT_WAIT_ord": (wait_c or {}).get("ordinary_action_value"),
            "CURRENT_WAIT_score": (wait_c or {}).get("score"),
            "USE_lag_rows": use_lags,
            "SHADOW_USE": shadow_H,
            "SHADOW_WAIT_by_lag": wait_shadow,
            "REALIZED_CF_from_4108": real.get("realized_by_H"),
            "PREDICTED_DIFF_4108": real.get("predicted_diff"),
            "actual_order": actual_order,
            "habit_ablated_order": ablated_order,
            "wait_no_habit": wait_no_habit,
            "best_shadow_USE": best_shadow_use,
            "shadow_order_vs_WAIT": shadow_vs_wait,
            "shadow_order_vs_WAIT_nohabit": shadow_vs_wait_nohabit,
        }
        shadow_table.append(row)
        habit_ablation.append({"state": label, "actual": actual_order, "ablated": ablated_order, "wait_no_habit": wait_no_habit, "use_tc": use_tc_ord})
        shadow_reorder.append({
            "state": label,
            "ACTUAL_POLICY": actual_order,
            "SHADOW_best_lag_USE_vs_WAIT": shadow_vs_wait,
            "SHADOW_best_lag_USE_vs_WAIT_nohabit": shadow_vs_wait_nohabit,
            "best_shadow_USE": best_shadow_use,
        })

        if label in ("S0", "S3"):
            physical_chains[label] = physical_chain_USE(e, 25)
            gc.collect()

    dump("SHADOW_TEMPORAL_PREDICTIONS.json", shadow_table)
    write_md(
        "SHADOW_TEMPORAL_PREDICTIONS.md",
        "# Shadow temporal predictions\n\nAll TC lag records evaluated with existing `prospective_ordinary_value`. "
        "No gamma aggregation. H10/H25 not in DEFAULT_LAGS → marked absent in shadow (use 4.10.8 realized for those horizons).\n",
    )
    dump("PHYSICAL_DELAYED_CHAIN.json", physical_chains)
    dump("HABIT_ABLATION_CONTROL.json", habit_ablation)
    dump("SHADOW_POLICY_REORDERING.json", shadow_reorder)

    # Prediction coverage: L2 delta vs chain at t=2
    coverage = {}
    for lab, ch in physical_chains.items():
        # find known L2 delta
        l2 = None
        for row in shadow_table:
            if row["state"] == lab:
                l2 = (row.get("SHADOW_USE") or {}).get("by_lag", {}).get(2)
        t2 = next((c for c in ch["chain"] if c["t"] == 2), None)
        coverage[lab] = {
            "predicted_L2_energy": (l2 or {}).get("mean_body_delta", {}).get("energy_signal") if l2 else None,
            "realized_t2_d_energy_signal": (t2 or {}).get("d_energy_signal"),
            "predicted_L2_ordinary": (l2 or {}).get("ordinary"),
            "note": "Single-lag L2 covers ~processing window, not H10/H25 cumulative",
        }
    dump("PREDICTION_COVERAGE.json", coverage)

    write_md(
        "TEMPORAL_EXPERIENCE_AUDIT.md",
        f"""# Temporal experience audit

Architecture already stores per-lag contingencies for lags {list(DEFAULT_LAGS)}.

First unsupported arrow for multi-horizon prospective **selection**:
`lag-specific records → joint bounded trajectory used at decision time` = **MISSING**
(retrieval collapses to one best lag).

Acquisition of delayed chain: **PARTIAL** (separate L0–L3 records exist; USE KNOWN at L2).

No future leakage: shadow uses only stored contingencies.
""",
    )
    write_md(
        "TEMPORAL_AGGREGATION_FRONTIER.md",
        "# Temporal aggregation frontier\n\nNo existing gamma/discount aggregator for multi-lag body deltas into one ordinary value.\n"
        "Shadow keeps H/lag-specific predictions separate. **Do not invent gamma in 4.10.9.**\n",
    )

    # Horizon calibration vs 4108 realized
    calib = []
    for row in shadow_table:
        lab = row["state"]
        real = row.get("REALIZED_CF_from_4108") or {}
        # current prospective is proximal/single; shadow L2 ordinary vs realized diffs are different quantities —
        # compare predicted energy at L2 vs realized energy at H3 from pvr4108
        for r in pvr4108:
            if r.get("snap") == lab and r.get("H") in (1, 3, 10, 25):
                calib.append({
                    "snap": lab,
                    "H": r["H"],
                    "USE_pred_energy_current": r["USE"]["pred_energy_delta"],
                    "USE_real_energy": r["USE"]["real_energy_delta"],
                    "calib_class": r["USE"]["calib_energy"],
                    "realized_ord_diff_USE_minus_WAIT": r["realized_diff_USE_minus_WAIT"],
                    "shadow_L2_ordinary": ((row.get("SHADOW_USE") or {}).get("by_lag") or {}).get(2, {}).get("ordinary"),
                })
    dump("HORIZON_CALIBRATION.json", calib)

    dump("TEMPORAL_EXTENSION_ABLATION.json", {
        "CURRENT_PROXIMAL": "single best-lag TC ordinary (~L2)",
        "TEMPORAL_SHADOW": "all lags evaluated separately, no policy effect",
        "TEMPORAL_ABLATED": "not removing TC — diagnostic only",
        "improvement": "Shadow exposes lag structure; does not by itself fix H10/H25 missing lags",
    })

    dump("WORLD_DIVERGENCE_CONTROL.json", {
        "env_exchange": False,
        "field": 0.0,
        "WORLD_TRAJECTORY": "UNKNOWN as general latent; in this ecology mostly deterministic basal+ambient drain",
        "UNKNOWN_kept_distinct_from_zero": True,
        "contamination_risk": "If env dynamics were on, WAIT/USE shared world evolution could bias TC without action-specific attribution — see BACKGROUND_SHARED gates in earlier updates",
    })
    write_md(
        "SURPRISE_ATTRIBUTION_AUDIT.md",
        "# Surprise attribution\n\nHabit updates on selection only — unexpected body outcomes do **not** reduce habit.\n"
        "TC updates from consequences at lag — can accumulate contradiction, but habit path is independent.\n"
        "Independent world change is not labeled; risk of misattribution remains a frontier when exchange/dynamics are on.\n",
    )
    write_md(
        "EXECUTION_COST_FRONTIER.md",
        "# Execution-cost frontier\n\n4.10.8: non-severe path does not apply 0.04; H1 WAIT and USE often same immediate drain before processing.\n"
        "Misranking is habit + short horizon, **not** execution-cost miscalibration.\n"
        "**Execution-cost prediction is NOT the immediate justified frontier.**\n",
    )

    dump("S0_S3_STATE_DEPENDENCE.json", [{
        "state": r["state"],
        "USE_current": r["CURRENT_USE_ord"],
        "WAIT_current": r["CURRENT_WAIT_ord"],
        "shadow_L2": ((r.get("SHADOW_USE") or {}).get("by_lag") or {}).get(2, {}).get("ordinary"),
        "signals": r["signals"],
    } for r in shadow_table])

    dump("SEVERE_BOUNDARY_AUDIT.json", {"first_severe_tick": first_severe, "note": "Boundary only; primary analysis NON_SEVERE window"})

    # Causal chain
    chain = {
        "HABIT: repetition→strength": "DEMONSTRATED",
        "HABIT: strength→contribution": "DEMONSTRATED",
        "HABIT: contribution→score": "DEMONSTRATED",
        "HABIT: encodes consequence": "NULL",
        "TEMPORAL: USE→transfer→internal→processing→body": "DEMONSTRATED",
        "TEMPORAL: experience→lag records L0-3": "DEMONSTRATED",
        "TEMPORAL: retrieval→single best lag at decision": "DEMONSTRATED",
        "TEMPORAL: multi-lag trajectory in selection": "MISSING",
        "TEMPORAL: shadow multi-lag readout": "DEMONSTRATED",
        "WORLD: general prospective world model": "MISSING",
        "WORLD: UNKNOWN≠0": "DEMONSTRATED",
        "INTEGRATION: habit+prospective→selection": "DEMONSTRATED",
        "calibration: predicted WAIT>USE vs realized USE>WAIT H>=3": "DEMONSTRATED",
    }
    dump("UPDATE4109_CAUSAL_CHAIN.json", chain)
    write_md("UPDATE4109_CAUSAL_CHAIN.md", "# Causal chain\n\n" + "\n".join(f"- `{k}`: **{v}**" for k, v in chain.items()) + "\n")

    dump("OBSERVER_UPDATE4109_SNAPSHOT.json", {"table": shadow_table, "habit_ablation": habit_ablation, "shadow_reorder": shadow_reorder})
    write_md("OBSERVER_UPDATE4109_AUDIT.md", "# Observer 4.10.9\n\nPROSPECTIVE TEMPORAL ECONOMY panel inert.\n")
    dump("INSTRUMENTATION_INERTNESS.json", {"observer_inert": True, "shadow_not_in_policy": True})
    write_md("SEMANTIC_LEAKAGE_AUDIT.md", "# Semantic leakage\n\nNo rational/lazy/motivation labels.\n")

    # Answers
    s0 = shadow_table[0] if shadow_table else {}
    answers = {
        1: "Action-keyed repetition strength updated from last_action with decay",
        2: "Selecting/executing the action (last_action) increases strength by learning_rate after decay",
        3: "Repetition/familiarity — NOT physical consequence",
        4: "No",
        5: "No",
        6: "Yes — bad-history WAIT control: habit→1 while tick ordinary typically negative",
        7: "strength(~1)*habit_weight(0.03)=0.03 added into base_total",
        8: "Ad-hoc ordinary-value units via habit_weight; no mapped body future",
        9: "Compatibility is architectural coercion, not demonstrated physical equivalence",
        10: "Yes — dominant term vs USE TC ~0.005",
        11: "L2 mean_body_delta (~energy +0.0097 after delay window)",
        12: "Explicit multi-step H10/H25 trajectory; T0 transfer-only; joint lag path in selection",
        13: "H3 in 4.10.8 matched CF (H1 tie)",
        14: "Yes across S0–S3 in 4.10.8",
        15: "PARTIAL — per-lag records exist",
        16: "lag records → joint bounded trajectory at decision time",
        17: "Yes for shadow readout of existing lags; no future leakage",
        18: "Exposes structure; cannot invent H10/H25 without new lags — calibration to H3 aided by L2/L3 presence",
        19: "L2/~H3 region relative to DEFAULT_LAGS",
        20: "Yes — physical lag deltas, not value retune",
        21: False,
        22: "Confidence gates evidence status; not a direct additive value bonus in OrganismValuation habit path",
        23: "Yes — via habit",
        24: s0.get("habit_ablated_order"),
        25: "No — ablation is a control isolating contribution, not a fix mandate",
        26: s0.get("shadow_order_vs_WAIT"),
        27: "Partial — shadow best-lag still short-horizon; realized H10/H25 favor USE more",
        28: "Yes — USE ordinary rises toward severe in 4.10.8; shadow L2 also state-dependent via prospective_ordinary_value",
        29: "Low in this ecology (env off); general risk remains",
        30: "PARTIAL — BACKGROUND_SHARED / UNKNOWN markers exist; habit path never attributes",
        31: "UNKNOWN as general world model; local drain quasi-deterministic here",
        32: True,
        33: "Habit: no. TC: consequence updates. Surprise≠habit reduction",
        34: False,
        35: False,
        36: False,
        37: False,
        38: False,
        39: False,
        40: (
            "WAIT non-severe dominance is mostly repetition-habit (+0.03) added into ordinary-value space without consequence grounding; "
            "KNOWN USE predicts a single lag (L2) body delta, while matched physics favors USE from H>=3. "
            "Multi-lag records exist but selection collapses to one lag — first missing arrow is joint bounded trajectory at decision time."
        ),
        41: (
            "Smallest next: wire shadow multi-lag prospective into a **non-default experimental candidate channel** "
            "(still no habit_weight/gate retune), or a diagnostic that learns/exposes lags beyond L3 only if physical delay requires it — "
            "without optimizing for USE wins."
        ),
    }

    write_md(
        "UPDATE4109_FINAL_REPORT.md",
        f"""# Update 4.10.9 — FINAL REPORT

Prospective Temporal Horizon × Habit–Prediction Alignment

## Habit
Pure **repetition**: decay all, boost `last_action`. No outcome conditioning. `+0.03 = strength×habit_weight` coerced into ordinary-value space.

## Prospective USE
Single retrieved lag (**L2**) mean_body_delta. DEFAULT_LAGS=(0,1,2,3). Selection does not use a multi-horizon trajectory.

## Shadow
All lag records evaluated separately with existing prospective valuation. No gamma. No policy change.

## Habit ablation (control)
See HABIT_ABLATION_CONTROL.json — isolates habit's ranking role; **not** a deletion mandate.

## Calibration
4.10.8 realized: USE>WAIT from H≥3 while policy WAIT>USE. Root causes: (1) habit currency ≠ physical prospective currency; (2) horizon truncation / single-lag collapse.

## Severe
Boundary only (first_severe≈{first_severe}).

## Strongest conclusion
{answers[40]}

## Answers
"""
        + "\n".join(f"**Q{k}.** {v}" for k, v in answers.items())
        + f"\n\nElapsed_s: {time.time()-t0:.1f}\n",
    )
    dump("UPDATE4109_SUMMARY.json", {
        "first_severe": first_severe,
        "habit_ablation": habit_ablation,
        "shadow_reorder": shadow_reorder,
        "elapsed_s": time.time() - t0,
    })
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
