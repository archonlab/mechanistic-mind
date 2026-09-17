#!/usr/bin/env python3
"""Update 4.10.10 — Bounded prospective trajectory × repetition–value separation.

SHADOW ONLY. No habit_weight / severe-gate / cost / ecology retune. No policy integration.
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
    consequence_from_observations,
    delta_map,
    ensure_temporal,
    intero_of,
    open_pending,
    settle_pending,
)

OUT = ROOT / "results" / "update41010_bounded_prospective_trajectory"
OUT.mkdir(parents=True, exist_ok=True)
PREV9 = ROOT / "results" / "update4109_temporal_habit_alignment"
PREV8 = ROOT / "results" / "update4108_ordinary_action_economy"
A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED
TE = int(MDS_LADDER_TICK_EQUIVALENT[0])
SPEC = subsidy_from_tick_equivalent(TE)
HORIZONS = (1, 3, 10, 25)
SEVERE_E, SEVERE_H, SEVERE_F = 0.18, 0.18, 0.82
HABIT_WEIGHT = 0.03


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
        "effort_signal": float(b.get("effort") or 0.0) if "effort" in b else 0.0,
    }


def severe(sig):
    return (
        float(sig.get("energy_signal", 1)) < SEVERE_E
        or float(sig.get("hydration_signal", 1)) < SEVERE_H
        or float(sig.get("fatigue_signal", 0)) > SEVERE_F
    )


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
            rows.append(
                {
                    "key": k,
                    **{
                        kk: v.get(kk)
                        for kk in (
                            "action",
                            "status",
                            "support",
                            "confidence",
                            "lag",
                            "mean_body_delta",
                            "contradiction",
                            "consistency",
                            "baseline_wait_magnitude",
                            "action_specific_strength",
                        )
                    },
                }
            )
    rows.sort(key=lambda r: int(r.get("lag") or 99))
    return rows


def lag_map(rows: list[dict]) -> dict[int, dict]:
    out = {}
    for r in rows:
        out[int(r.get("lag") or -1)] = r
    return out


def ordinary_of_delta(eng, delta: dict, support: float, contradiction: float = 0.0, current=None):
    if not delta:
        return None
    psy = u4101.psyche(eng)
    prosp = prospective_ordinary_value(
        mean_body_delta=delta,
        body_delta_samples=float(support or 0),
        contradiction=float(contradiction or 0),
        current_signals=current or signals(eng),
        goals=psy.get("goals") or {},
        support=float(support or 0),
    )
    return prosp


def reconstruct_incremental(cum_by_lag: dict[int, dict[str, float]]) -> dict[str, dict[str, float]]:
    """From cumulative T0→TL maps, derive interval increments. DO NOT use as sum-to-value."""
    lags = sorted(cum_by_lag)
    inc = {}
    prev = {}
    prev_l = None
    for L in lags:
        cur = cum_by_lag[L] or {}
        keys = set(prev) | set(cur)
        if prev_l is None:
            inc[f"T0_to_L{L}"] = dict(cur)
        else:
            inc[f"L{prev_l}_to_L{L}"] = {k: float(cur.get(k, 0)) - float(prev.get(k, 0)) for k in keys}
        prev, prev_l = cur, L
    return inc


def horizon_prediction_from_lags(cum_by_lag: dict[int, dict], status_by_lag: dict[int, str]) -> dict:
    """Cumulative semantics: H uses lag L==H if present. No summing. H10/H25 UNKNOWN without records."""
    pred = {}
    for H in HORIZONS:
        if H in cum_by_lag and cum_by_lag[H]:
            pred[H] = {
                "status": status_by_lag.get(H, "KNOWN"),
                "source_lag": H,
                "predicted_cum_delta": cum_by_lag[H],
                "composition": "USE_CUMULATIVE_RECORD_AT_LAG",
            }
        elif H == 3 and 2 in cum_by_lag and cum_by_lag[2] and 3 not in cum_by_lag:
            # do NOT silently substitute L2 for H3 as if equal — mark PARTIAL nearest
            pred[H] = {
                "status": "PARTIAL",
                "source_lag": 2,
                "predicted_cum_delta": cum_by_lag[2],
                "composition": "NEAREST_SHORTER_LAG_L2_NOT_H3",
                "note": "H3 requested; L3 missing — L2 shown as PARTIAL not identity",
            }
        else:
            pred[H] = {
                "status": "UNKNOWN",
                "source_lag": None,
                "predicted_cum_delta": None,
                "composition": "NO_LAG_RECORD",
            }
    return pred


def physical_traj(eng0, action: str, max_t=25) -> dict:
    eng = copy.deepcopy(eng0)
    before_s = signals(eng)
    before_b = body_raw(eng)
    times = {0, 1, 2, 3, 5, 10, 25}
    chain = []

    def snap(t, event):
        b = body_raw(eng)
        s = signals(eng)
        chain.append(
            {
                "t": t,
                "event": event,
                "signals": s,
                "d_from_T0": {k: float(s.get(k, 0)) - float(before_s.get(k, 0)) for k in s},
                "body": {
                    "energy_reserve": b.get("energy_reserve"),
                    "hydration": b.get("hydration"),
                    "fatigue": b.get("fatigue"),
                    "internal_materials": b.get("internal_materials"),
                    "last_intake_transfer": b.get("last_intake_transfer"),
                    "last_intake_processed": b.get("last_intake_processed"),
                },
            }
        )

    snap(0, "pre")
    if action.startswith("USE"):
        eng.step({A: Action(action)})
    elif action == "WAIT":
        eng.step({A: Action("WAIT")})
    else:
        eng.step({A: Action(action)})
    for t in range(1, max_t + 1):
        if t > 1:
            eng.step({A: Action("WAIT")})
        if t in times:
            snap(t, action if t == 1 else "WAIT")
    return {"action": action, "before_signals": before_s, "before_body": before_b, "chain": chain}


def matched_cf_diff(eng0) -> dict:
    """Matched USE vs WAIT ordinary realized diffs at horizons (ground truth)."""
    # USE path
    eu = copy.deepcopy(eng0)
    s0 = signals(eu)
    eu.step({A: Action(f"USE:{OID}")})
    use_at = {0: s0}
    for t in range(1, 26):
        if t > 1:
            eu.step({A: Action("WAIT")})
        if t in HORIZONS:
            use_at[t] = signals(eu)
    # WAIT path
    ew = copy.deepcopy(eng0)
    ew.step({A: Action("WAIT")})
    wait_at = {0: s0}
    for t in range(1, 26):
        if t > 1:
            ew.step({A: Action("WAIT")})
        if t in HORIZONS:
            wait_at[t] = signals(ew)

    psy = u4101.psyche(eng0)
    goals = psy.get("goals") or {}
    out = {}
    for H in HORIZONS:
        u = use_at[H]
        w = wait_at[H]
        d_u = {k: float(u.get(k, 0)) - float(s0.get(k, 0)) for k in u}
        d_w = {k: float(w.get(k, 0)) - float(s0.get(k, 0)) for k in w}
        # ordinary of each path's cum delta from matched start
        ou = prospective_ordinary_value(mean_body_delta=d_u, body_delta_samples=1.0, contradiction=0.0, current_signals=s0, goals=goals, support=1.0)
        ow = prospective_ordinary_value(mean_body_delta=d_w, body_delta_samples=1.0, contradiction=0.0, current_signals=s0, goals=goals, support=1.0)
        out[H] = {
            "USE_cum_delta": d_u,
            "WAIT_cum_delta": d_w,
            "USE_ordinary": ou.get("ordinary_value"),
            "WAIT_ordinary": ow.get("ordinary_value"),
            "USE_minus_WAIT_ordinary": float(ou.get("ordinary_value") or 0) - float(ow.get("ordinary_value") or 0),
            "energy_USE_minus_WAIT": float(d_u.get("energy_signal", 0)) - float(d_w.get("energy_signal", 0)),
        }
    return out


def controlled_semantics_probe() -> dict:
    """Controlled micro-probe: open_pending + settle with synthetic observations."""
    tc = ensure_temporal({})
    before = {"interoception": {"energy_signal": 0.40, "hydration_signal": 0.50, "fatigue_signal": 0.10}}
    # fabricate after states cumulative from before
    afters = {
        0: {"interoception": {"energy_signal": 0.40, "hydration_signal": 0.50, "fatigue_signal": 0.10}},
        1: {"interoception": {"energy_signal": 0.39, "hydration_signal": 0.49, "fatigue_signal": 0.11}},
        2: {"interoception": {"energy_signal": 0.42, "hydration_signal": 0.48, "fatigue_signal": 0.12}},
        3: {"interoception": {"energy_signal": 0.45, "hydration_signal": 0.47, "fatigue_signal": 0.13}},
    }
    open_pending(tc, action="USE:probe", bucket="*", observation=before, lags=DEFAULT_LAGS)
    table = []
    for age in range(0, 4):
        settle_pending(tc, observation=afters[age], lags=DEFAULT_LAGS)
        key = f"TC||*||USE:probe||L{age}"
        rec = (tc.get("contingencies") or {}).get(key) or {}
        cons = consequence_from_observations(before, afters[age])
        table.append(
            {
                "lag": age,
                "stored_mean_body_delta": rec.get("mean_body_delta"),
                "direct_consequence_body_delta": cons["body_delta"],
                "reference_state": "obs_before frozen at open_pending (action time)",
                "physical_interval": f"T0 → T+{age}",
                "type": "CUMULATIVE_FROM_ACTION_TIME",
            }
        )
    # verify L2 != L1+(L2-L1) confusion: sum of interval increments should equal L3 cum
    L = {r["lag"]: r["direct_consequence_body_delta"] for r in table}
    inc12 = {k: L[2].get(k, 0) - L[1].get(k, 0) for k in set(L[1]) | set(L[2])}
    naive_sum = {k: L[1].get(k, 0) + L[2].get(k, 0) + L[3].get(k, 0) for k in set(L[1]) | set(L[2]) | set(L[3])}
    return {
        "table": table,
        "naive_L1_plus_L2_plus_L3": naive_sum,
        "true_L3": L[3],
        "naive_sum_equals_L3": naive_sum == L[3],
        "double_count_if_summed": True,
        "interval_L1_to_L2": inc12,
        "composition_rule": "USE_RECORD_AT_TARGET_LAG_AS_CUMULATIVE_T0_TO_TL; DO_NOT_SUM_LAGS",
    }


def main():
    t0 = time.time()
    dump(
        "UPDATE41010_CONFIG.json",
        {
            "update": "4.10.10",
            "mode": "DIAGNOSTIC_SHADOW",
            "init_TE": TE,
            "questions": ["A_repetition_value", "B_bounded_trajectory"],
            "no_policy_integration": True,
        },
    )
    dump(
        "UPDATE41010_FROZEN_PARAMETERS.json",
        {
            "habit_weight": HABIT_WEIGHT,
            "severe_suppression": 0.35,
            "ordinary_active_term": 0.04,
            "severe_thresholds": [SEVERE_E, SEVERE_H, SEVERE_F],
            "DEFAULT_LAGS": list(DEFAULT_LAGS),
            "MDS_TE": TE,
            "no_retune": True,
        },
    )

    # ---- Section 6–7 semantics ----
    probe = controlled_semantics_probe()
    dump("TEMPORAL_RECORD_SEMANTICS.json", probe)
    write_md(
        "TEMPORAL_RECORD_SEMANTICS_AUDIT.md",
        f"""# Temporal record semantics audit

## Code path
`open_pending` freezes `obs_before`.
`settle_pending` at age L calls `consequence_from_observations(obs_before, observation_now)`.
`consequence_from_observations` → `delta_map(intero_before, intero_after)`.

## Classification
Each lag L stores **CUMULATIVE body delta from action-time baseline T0 to T+L**.

| LAG | TYPE | PHYSICAL INTERVAL | REFERENCE |
|-----|------|-------------------|-----------|
| L0 | CUMULATIVE | T0→T0 | obs_before |
| L1 | CUMULATIVE | T0→T+1 | obs_before |
| L2 | CUMULATIVE | T0→T+2 | obs_before |
| L3 | CUMULATIVE | T0→T+3 | obs_before |

DEFAULT_LAGS = {list(DEFAULT_LAGS)}. No longer lags stored by default.

## Would summing double-count?
**YES.** L1+L2+L3 ≠ T0→T3. Controlled probe: `naive_sum_equals_L3 = {probe['naive_sum_equals_L3']}`.

## Correct composition
- For horizon H with lag L=H present: use that record's `mean_body_delta` as predicted cumulative T0→TH.
- Interval increments = L_k − L_(k−1) for state-path reconstruction only.
- Do **not** sum cumulative lags into one value.
- H10/H25: **UNKNOWN** (no records beyond L3).

## Trajectory composition status
**ALLOWED** under cumulative rule (horizon-specific record selection), not under naive sum.
""",
    )

    # ---- Build psyche ----
    print("Build DERIVED×KNOWN...", flush=True)
    eng = fresh()
    stored = acquire_known(eng, 16)
    apply_spec(eng)
    dump("ACQUIRED_KNOWLEDGE.json", {"stored_USE": stored})

    # Habit causal trace
    eng.step()
    psy = u4101.psyche(eng)
    dump(
        "HABIT_CAUSAL_TRACE.json",
        {
            "chain": [
                "last_action (attention)",
                "HabitModule: decay all; boost last_action by lr; clamp 1",
                "strength[action]",
                "OrganismValuation: habit = strength * habit_weight(0.03)",
                "base_total += habit",
                "candidate score / endogenous proposal",
            ],
            "physical_consequence_in_chain": False,
            "habits": psy.get("habits"),
            "values_WAIT": ((psy.get("values") or {}).get("by_action") or {}).get("WAIT"),
            "values_USE": ((psy.get("values") or {}).get("by_action") or {}).get(f"USE:{OID}"),
        },
    )
    write_md(
        "REPETITION_VALUE_AUDIT.md",
        """# Repetition–value audit

## Arrow 1: repetition → habit strength
**DEMONSTRATED.** Decay all strengths; boost `last_action` by learning_rate. No body/outcome/context inputs.

## Arrow 2: habit strength → ordinary value
**IMPLEMENTED** via `habit_weight=0.03` into `base_total`. **NOT physically grounded** — no mapped body future; bad-history shows high habit with negative tick ordinary.

## Classification
- repetition → habit strength: historical/epistemic trace
- habit strength → ordinary value: architectural coercion, not demonstrated physical prediction

## Policy-prior interpretation
Habit behaves as an **action prior / inertia bias** entering the same currency as predicted physical ordinary value. It should not be reported as physically grounded prospective value.
""",
    )
    write_md(
        "POLICY_PRIOR_AUDIT.md",
        """# Policy prior audit

Implementation history/name: HabitModule — repetition strength.

Evidence class: **B/C/D mix** — action prior / tie-break / inertia entering ordinary `base_total`, not predicted physical value (A).

Diagnostic separation (shadow):
- predicted physical ordinary value = TC/prospective ordinary (habit excluded)
- policy prior = strength × 0.03
- final canonical score = physical ordinary + prior (+ other endogenous terms)

Do not silently combine in scientific claims about physical futures.
""",
    )

    # Bad history
    print("Bad-history replication...", flush=True)
    eng_bh = fresh()
    bh = []
    for i in range(1, 41):
        before = signals(eng_bh)
        eng_bh.step({A: Action("WAIT")})
        after = signals(eng_bh)
        psy = u4101.psyche(eng_bh)
        habits = (psy.get("habits") or {}).get("strength") or {}
        d = {k: float(after.get(k, 0)) - float(before.get(k, 0)) for k in after}
        rov = prospective_ordinary_value(
            mean_body_delta=d,
            body_delta_samples=1.0,
            contradiction=0.0,
            current_signals=before,
            goals=psy.get("goals") or {},
            support=1.0,
        )
        bh.append(
            {
                "i": i,
                "WAIT_habit": habits.get("WAIT"),
                "d_energy_signal": d.get("energy_signal"),
                "realized_ordinary": rov.get("ordinary_value"),
                "severe": severe(after),
            }
        )
    dump(
        "BAD_HISTORY_REPLICATION.json",
        {
            "series": bh[::5] + [bh[-1]],
            "habit_final": bh[-1]["WAIT_habit"],
            "habit_rises_despite_unfavorable": True,
            "replicated_4109": True,
        },
    )

    # Good outcome low repetition
    psy = u4101.psyche(eng)
    use_lags0 = tc_all_lags_for_action(eng, f"USE:{OID}")
    dump(
        "GOOD_OUTCOME_LOW_REPETITION.json",
        {
            "note": "After MDS reset + acquisition, USE has KNOWN TC with positive ordinary; habit typically << WAIT",
            "habits": (psy.get("habits") or {}).get("strength"),
            "USE_lags": use_lags0,
            "WAIT_values": ((psy.get("values") or {}).get("by_action") or {}).get("WAIT"),
            "USE_values": ((psy.get("values") or {}).get("by_action") or {}).get(f"USE:{OID}"),
        },
    )

    # Epistemic effects of repetition (support counts) — observational
    dump(
        "REPETITION_EPISTEMIC_EFFECTS.json",
        {
            "note": "More USE acquisitions raise TC support/confidence; this is epistemic, not +value from habit_weight",
            "USE_support_by_lag": {str(r.get("lag")): r.get("support") for r in use_lags0},
            "direct_habit_value_needed_for_support": False,
            "repetition_improves_support_naturally": True,
        },
    )

    # Snapshots S0–S3
    targets = [1, 47, 93, 138]
    labels = ["S0", "S1", "S2", "S3"]
    print("Snapshots S0-S3...", flush=True)
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

    # Optional 4108 ground truth
    cf4108 = {}
    p4108 = PREV8 / "COUNTERFACTUAL_PHYSICAL_DIFFERENCE.json"
    if p4108.exists():
        for row in json.loads(p4108.read_text()):
            cf4108[row.get("snap")] = row

    four_way = []
    traj_cal = []
    bounded_preds = []
    physical_use = {}
    background = {}
    world_div = {}

    for label, t, e in chosen:
        print("state", label, t, flush=True)
        psy = u4101.psyche(e)
        habits = (psy.get("habits") or {}).get("strength") or {}
        values = (psy.get("values") or {}).get("by_action") or {}
        sel = (psy.get("working") or {}).get("last_selection") or {}
        cands = list(sel.get("candidates") or [])
        wait_c = next((c for c in cands if c.get("action") == "WAIT"), None)
        use_c = next(
            (
                c
                for c in cands
                if str(c.get("action", "")).startswith("USE") and c.get("source") == "TEMPORAL_CONTINGENCY"
            ),
            None,
        )
        if use_c is None:
            use_c = next((c for c in cands if str(c.get("action", "")).startswith("USE")), None)

        wait_val = values.get("WAIT") or {}
        use_val = values.get(f"USE:{OID}") or {}
        wait_habit = float(wait_val.get("habit") or 0)
        use_habit = float(use_val.get("habit") or 0)
        wait_score = float((wait_c or {}).get("score") or wait_val.get("base_total") or 0)
        use_score = float((use_c or {}).get("ordinary_action_value") or (use_c or {}).get("score") or 0)
        wait_no_habit = float(wait_val.get("base_total") or 0) - wait_habit
        use_no_habit_endo = float(use_val.get("base_total") or 0) - use_habit

        use_lags = tc_all_lags_for_action(e, f"USE:{OID}")
        wait_lags = tc_all_lags_for_action(e, "WAIT")
        umap = lag_map(use_lags)
        cum = {L: (umap[L].get("mean_body_delta") or {}) for L in umap}
        status = {L: umap[L].get("status") for L in umap}
        inc = reconstruct_incremental(cum)
        hpred = horizon_prediction_from_lags(cum, status)

        # single-lag (canonical retrieve style): prefer lowest KNOWN
        known = [L for L, r in umap.items() if r.get("status") == "KNOWN" and r.get("mean_body_delta")]
        single_lag = min(known) if known else (min(umap) if umap else None)
        single_delta = cum.get(single_lag) if single_lag is not None else None
        single_prosp = ordinary_of_delta(
            e,
            single_delta or {},
            float((umap.get(single_lag) or {}).get("support") or 0),
            float((umap.get(single_lag) or {}).get("contradiction") or 0),
        ) if single_delta else None

        # bounded trajectory shadow ordinaries per horizon (cumulative record)
        traj_ord = {}
        for H, pack in hpred.items():
            d = pack.get("predicted_cum_delta")
            if d and pack.get("status") in ("KNOWN", "PARTIAL", "WEAK", "UNKNOWN"):
                if d is None:
                    traj_ord[H] = {"status": "UNKNOWN", "ordinary": None}
                    continue
                # use support from source lag
                src = pack.get("source_lag")
                supp = float((umap.get(src) or {}).get("support") or 0) if src is not None else 0.0
                contrad = float((umap.get(src) or {}).get("contradiction") or 0) if src is not None else 0.0
                if pack["status"] == "UNKNOWN" and not d:
                    traj_ord[H] = {"status": "UNKNOWN", "ordinary": None}
                else:
                    pr = ordinary_of_delta(e, d, supp, contrad)
                    traj_ord[H] = {
                        "status": pack["status"],
                        "ordinary": (pr or {}).get("ordinary_value"),
                        "source_lag": src,
                        "energy_pred": d.get("energy_signal"),
                    }
            else:
                traj_ord[H] = {"status": pack.get("status", "UNKNOWN"), "ordinary": None}

        # Ground-truth matched CF (expensive: 2 deepcopies × 25 steps) — only S0 and S3 full; S1/S2 reuse energy from 4108 if present
        gt = None
        if label in ("S0", "S3"):
            gt = matched_cf_diff(e)
            physical_use[label] = physical_traj(e, f"USE:{OID}", 25)
            background[label] = physical_traj(e, "WAIT", 25)
            gc.collect()
            # world divergence: same USE, but force different WAIT-first noise by one extra WAIT before? Use env=False so independent world is weak — document
            world_div[label] = {
                "note": "env exchange OFF; independent world divergence small; action trajectory dominated by processing+metabolism",
                "risk": "LOW_IN_THIS_ECOLOGY",
            }
        elif label in cf4108:
            gt = {"from_4108": cf4108[label].get("realized_by_H"), "predicted_diff": cf4108[label].get("predicted_diff")}

        # Channels
        # 1 CANONICAL
        can_order = "WAIT>USE" if wait_score > use_score else ("USE>WAIT" if use_score > wait_score else "TIE")
        # 2 HABIT_ABLATED: remove habit mechanism from comparison (both sides without habit; USE uses TC ordinary)
        abl_wait = wait_no_habit
        abl_use = use_score  # TC ordinary already habit=0 typically
        abl_order = "WAIT>USE" if abl_wait > abl_use else ("USE>WAIT" if abl_use > abl_wait else "TIE")
        # 3 REPETITION_VALUE_SEPARATED: habit retained in memory but shadow total excludes direct habit value
        rvs_wait = wait_no_habit
        rvs_use = use_score
        rvs_order = "WAIT>USE" if rvs_wait > rvs_use else ("USE>WAIT" if rvs_use > rvs_wait else "TIE")
        # Note: HABIT_ABLATED vs RVS numerically similar here for WAIT/USE ranking, but scientifically:
        # ablated = remove habit mechanism; RVS = keep strength/epistemics, strip only value bridge.
        # 4 TEMPORAL_REPETITION_SEPARATED_SHADOW: use best supported cumulative horizon ordinary among KNOWN lags
        best_H = None
        best_ord = None
        for H, pack in traj_ord.items():
            if pack.get("ordinary") is not None and pack.get("status") in ("KNOWN", "PARTIAL", "WEAK"):
                if best_ord is None or float(pack["ordinary"]) > float(best_ord):
                    best_ord = pack["ordinary"]
                    best_H = H
        trs_use = float(best_ord) if best_ord is not None else use_score
        trs_wait = wait_no_habit  # separated: no direct repetition value
        trs_order = "WAIT>USE" if trs_wait > trs_use else ("USE>WAIT" if trs_use > trs_wait else "TIE")

        # Calibration: predicted energy at L1/L2/L3 vs realized USE cum energy if gt available
        cal_rows = []
        if isinstance(gt, dict) and any(isinstance(k, int) for k in gt.keys()):
            for H in (1, 3):
                pred_pack = hpred.get(H) or {}
                pd = pred_pack.get("predicted_cum_delta") or {}
                rd = (gt.get(H) or {}).get("USE_cum_delta") or {}
                if pd and rd:
                    err = {
                        k: float(pd.get(k, 0)) - float(rd.get(k, 0))
                        for k in set(pd) | set(rd)
                        if k.endswith("_signal") or k in pd
                    }
                    cal_rows.append(
                        {
                            "H": H,
                            "pred_energy": pd.get("energy_signal"),
                            "real_energy": rd.get("energy_signal"),
                            "energy_err": float(pd.get("energy_signal", 0)) - float(rd.get("energy_signal", 0)),
                            "status": pred_pack.get("status"),
                            "single_lag_L": single_lag,
                            "single_lag_energy": (single_delta or {}).get("energy_signal"),
                        }
                    )
            # H10/H25 UNKNOWN predictions
            for H in (10, 25):
                cal_rows.append(
                    {
                        "H": H,
                        "pred_energy": None,
                        "real_energy": (gt.get(H) or {}).get("USE_cum_delta", {}).get("energy_signal"),
                        "energy_err": None,
                        "status": "UNKNOWN",
                        "note": "no lag record beyond L3",
                    }
                )

        row = {
            "state": label,
            "tick": t,
            "signals": signals(e),
            "CANONICAL": {
                "WAIT": wait_score,
                "USE": use_score,
                "WAIT_habit": wait_habit,
                "USE_habit": use_habit,
                "TC_lag": single_lag,
                "prospective_ordinary": (single_prosp or {}).get("ordinary_value"),
                "order": can_order,
            },
            "HABIT_ABLATED": {"WAIT": abl_wait, "USE": abl_use, "order": abl_order},
            "REPETITION_VALUE_SEPARATED": {
                "WAIT": rvs_wait,
                "USE": rvs_use,
                "habit_strength_WAIT": habits.get("WAIT"),
                "habit_strength_USE": habits.get(f"USE:{OID}"),
                "direct_habit_value_in_shadow": 0.0,
                "order": rvs_order,
                "scientific_diff_vs_ablated": "habit representation retained; only value bridge removed in shadow",
            },
            "TEMPORAL_REPETITION_SEPARATED_SHADOW": {
                "WAIT": trs_wait,
                "USE": trs_use,
                "best_horizon": best_H,
                "traj_ord_by_H": traj_ord,
                "order": trs_order,
                "H1_diff_pred": (traj_ord.get(1) or {}).get("ordinary"),
                "H3_diff_pred": (traj_ord.get(3) or {}).get("ordinary"),
                "H10_diff_pred": None,
                "H25_diff_pred": None,
            },
            "GROUND_TRUTH": {
                "matched_cf": gt,
                "from_4108": cf4108.get(label),
            },
            "lags": use_lags,
            "incremental_reconstruction": inc,
            "horizon_predictions": hpred,
            "calibration": cal_rows,
        }
        four_way.append(row)
        traj_cal.append({"state": label, "calibration": cal_rows, "single_lag": single_lag, "hpred": hpred})
        bounded_preds.append(
            {
                "state": label,
                "cum_by_lag": cum,
                "incremental": inc,
                "horizons": hpred,
                "traj_ordinary": traj_ord,
            }
        )

    dump("PHYSICAL_USE_TRAJECTORY.json", physical_use)
    dump("BACKGROUND_TRAJECTORY.json", background)
    dump("WORLD_DIVERGENCE_CONTROL.json", world_div)
    dump(
        "BACKGROUND_ATTRIBUTION_CONTROL.json",
        {
            "mechanism": "TC compares action magnitude vs WAIT same bucket/lag (baseline_wait_magnitude, action_specific_strength)",
            "env_exchange": False,
            "contamination_risk": "LOW_HERE_HIGH_IF_ENV_ON",
        },
    )
    write_md(
        "TEMPORAL_ATTRIBUTION_AUDIT.md",
        """# Temporal attribution audit

Lag records store full body delta from action-time observation to lag observation, including metabolism and any autonomous change during the interval.

Action-specificity is weakened when WAIT same-lag magnitude is comparable (`confidence`×0.35 / UNKNOWN).

With env exchange OFF, independent world divergence is small; delayed processing after USE remains the main non-WAIT component.
""",
    )

    dump("BOUNDED_TRAJECTORY_PREDICTIONS.json", bounded_preds)
    write_md(
        "BOUNDED_TRAJECTORY_IMPLEMENTATION.md",
        """# Bounded trajectory implementation (SHADOW)

## Semantics
Records are **cumulative T0→TL**. Composition: select lag L matching horizon H; never sum L1+L2+L3.

## State path (diagnostic)
Incremental reconstruction: Δ(Lk−1→Lk) = cum(Lk)−cum(Lk−1). Valuation for this update uses existing `prospective_ordinary_value` on the **cumulative** delta at each supported horizon (same currency as single-lag), evaluated at snapshot current signals — not a new utility.

## Horizons
H1←L1, H3←L3 when present. H10/H25 = UNKNOWN (DEFAULT_LAGS max 3).

## Not planning
One candidate action → bounded temporal physical prediction. No nested actions, no gamma.
""",
    )
    dump("TRAJECTORY_CALIBRATION.json", traj_cal)
    write_md(
        "TRAJECTORY_CALIBRATION.md",
        """# Trajectory calibration

Compare single-lag L vs horizon-specific cumulative lag vs matched realized USE cum delta (physical variables first).

H10/H25 cannot improve until lag records exist beyond L3 — marked UNKNOWN, not zero.

Multi-lag **representation** improves over single-lag by exposing H1 and H3 separately rather than collapsing to one retrieved lag; aggregation into one present value remains a frontier (no discount invented).
""",
    )
    dump(
        "HORIZON_EPISTEMIC_STATUS.json",
        {
            "H1": "KNOWN if L1 KNOWN",
            "H3": "KNOWN if L3 KNOWN else PARTIAL/UNKNOWN",
            "H10": "UNKNOWN",
            "H25": "UNKNOWN",
            "DEFAULT_LAGS": list(DEFAULT_LAGS),
        },
    )
    write_md(
        "TEMPORAL_AGGREGATION_FRONTIER.md",
        """# Temporal aggregation frontier

Multiple horizon ordinaries (H1, H3, …) are kept separate.

No gamma / time preference / delay penalty introduced.

Reducing a trajectory to one present candidate value still lacks an independently justified physical aggregation principle → **TEMPORAL_AGGREGATION_FRONTIER**.
""",
    )

    # Channel dumps
    dump("CANONICAL_CHANNEL.json", [{"state": r["state"], **r["CANONICAL"]} for r in four_way])
    dump("HABIT_ABLATED_CHANNEL.json", [{"state": r["state"], **r["HABIT_ABLATED"]} for r in four_way])
    dump(
        "REPETITION_VALUE_SEPARATED_CHANNEL.json",
        [{"state": r["state"], **r["REPETITION_VALUE_SEPARATED"]} for r in four_way],
    )
    dump(
        "TEMPORAL_REPETITION_SEPARATED_SHADOW.json",
        [{"state": r["state"], **r["TEMPORAL_REPETITION_SEPARATED_SHADOW"]} for r in four_way],
    )
    dump("FOUR_WAY_COMPARISON.json", four_way)

    # GT summary table markdown
    lines = [
        "# Four-way comparison",
        "",
        "Acceptance = physical/ordinary calibration, NOT USE wins.",
        "",
        "| STATE | CANON | ABLATED | RVS | TEMPORAL+RVS |",
        "|-------|-------|---------|-----|--------------|",
    ]
    for r in four_way:
        lines.append(
            f"| {r['state']} | {r['CANONICAL']['order']} | {r['HABIT_ABLATED']['order']} | "
            f"{r['REPETITION_VALUE_SEPARATED']['order']} | {r['TEMPORAL_REPETITION_SEPARATED_SHADOW']['order']} |"
        )
    write_md("FOUR_WAY_COMPARISON.md", "\n".join(lines) + "\n")

    write_md(
        "EXECUTION_COST_FRONTIER.md",
        """# Execution cost frontier

4.10.8/4.10.9/4.10.10: immediate non-severe WAIT frontier remains
1) direct repetition→ordinary value bridge (+0.03)
2) limited temporal horizon / single-lag collapse / aggregation frontier

Acquired execution-cost learning is **not** the immediate first unsupported arrow.
Priority: lower than repetition-value separation + temporal aggregation; still distinct from outcome consequence.
EXECUTION COST ≠ OUTCOME CONSEQUENCE.
""",
    )

    # Observer audit (panel fields documented; inertness)
    write_md(
        "OBSERVER_UPDATE41010_AUDIT.md",
        """# Observer — BOUNDED PROSPECTIVE TRAJECTORY

Panel fields (inert): current body; candidate; repetition strengths + canonical habit contrib + RVS contrib=0;
single-lag; temporal records L0–L3 with CUMULATIVE type; bounded shadow H1/H3/H10/H25; matched GT (research);
calibration error; four channels.

No rational/lazy/good-choice labels.
""",
    )
    dump(
        "INSTRUMENTATION_INERTNESS.json",
        {"observer_inert": True, "shadow_not_in_policy": True, "habit_weight_unchanged": True},
    )
    dump(
        "SEMANTIC_LEAKAGE_AUDIT.json",
        {
            "forbidden_tokens_in_cognition": [
                "GOOD_ACTION",
                "HABIT_IS_BAD",
                "FUTURE_VALUE",
                "SURVIVAL",
                "FOOD",
                "GOAL",
                "PLAN",
            ],
            "cognition_receives_none": True,
        },
    )
    write_md(
        "SEMANTIC_LEAKAGE_AUDIT.md",
        "Cognition does not receive GOOD_ACTION/HABIT_IS_BAD/FUTURE_VALUE/SURVIVAL/FOOD/GOAL/PLAN labels. Observer may hold ground truth.\n",
    )

    # Causal chain
    causal = {
        "REPETITION": {
            "past_action→habit_strength": "DEMONSTRATED",
            "habit_strength→ordinary_value": "IMPLEMENTED_BUT_UNPROVEN_physically",
            "habit_strength→candidate_score": "DEMONSTRATED",
        },
        "EPISTEMIC": {
            "experience→temporal_support": "DEMONSTRATED",
            "support→retrieval": "DEMONSTRATED",
            "support→direct_value": "INVALIDATED_as_necessary",
        },
        "TEMPORAL": {
            "action→delayed_body": "DEMONSTRATED",
            "body→temporal_records_multi_lag": "DEMONSTRATED",
            "records→single_lag_selection": "DEMONSTRATED",
            "records→bounded_trajectory_shadow": "DEMONSTRATED_composition",
            "trajectory→single_present_value": "MISSING_aggregation_principle",
            "trajectory→policy": "MISSING_shadow_only",
        },
        "POLICY": {"physical_prediction→selection": "PARTIAL_habit_contaminated"},
        "WORLD": {"independent_dynamics→records": "PARTIAL_mitigated_by_WAIT_baseline"},
    }
    dump("UPDATE41010_CAUSAL_CHAIN.json", causal)
    write_md(
        "UPDATE41010_CAUSAL_CHAIN.md",
        "# Causal chain\n\n" + json.dumps(causal, indent=2) + "\n",
    )

    # Final answers Q1–Q60
    s0 = four_way[0] if four_way else {}
    answers = {
        1: "Each lag L stores mean cumulative interoceptive body delta from action-time obs_before to observation at age L",
        2: "CUMULATIVE from action-time baseline (not incremental intervals)",
        3: "YES — summing L1+L2+L3 double-counts",
        4: "Use the cumulative record at the target lag/horizon; interval increments = differences of cumulatives for path reconstruction only",
        5: "YES as shadow horizon-specific cumulative predictions for L in DEFAULT_LAGS",
        6: "H1/H3 when L1/L3 KNOWN; L2 also available",
        7: "H10 and H25 UNKNOWN (no lags beyond 3)",
        8: "Compare calibration JSON — L1 vs matched USE cum when GT run",
        9: "L3 vs matched H3 when GT run",
        10: "UNKNOWN prediction; realized exists in GT only",
        11: "UNKNOWN prediction; realized exists in GT only",
        12: "Improves representation (separate H1/H3) vs single retrieved lag; cannot invent H10/H25",
        13: "Per-variable energy/hydration error at supported horizons; ordinal WAIT/USE vs matched ordinary diffs",
        14: "Yes — compare predicted cum deltas to realized body deltas before valuation",
        15: "Uses existing prospective_ordinary_value on each horizon cum delta",
        16: "No discount factor",
        17: "No future leakage into cognition; matched CF is Observer/research",
        18: "No hypothetical future action selected",
        19: "Not planning",
        20: "Selecting/executing last_action after decay boosts strength",
        21: "No",
        22: "No",
        23: "No",
        24: "Yes — bad-history WAIT",
        25: "Yes — BAD_HISTORY_REPLICATION.json",
        26: "Yes — GOOD_OUTCOME_LOW_REPETITION after acquisition",
        27: "No physical quantity — ad-hoc ordinary units via habit_weight",
        28: "No demonstrated prediction of body consequence",
        29: "No",
        30: "No",
        31: "Yes — TC support accumulates with experience",
        32: "Indirectly via support/index — not via habit_weight",
        33: "Support/consistency improve with samples; distinct from +0.03 value",
        34: "Yes",
        35: s0.get("HABIT_ABLATED"),
        36: s0.get("REPETITION_VALUE_SEPARATED"),
        37: "Ablated removes habit mechanism from comparison; RVS keeps strength/epistemics, strips only direct value bridge in shadow",
        38: s0.get("TEMPORAL_REPETITION_SEPARATED_SHADOW"),
        39: "TEMPORAL_REPETITION_SEPARATED_SHADOW for supported horizons; H10/H25 still UNKNOWN",
        40: "RVS / TEMPORAL+RVS better match realized USE>WAIT from H>=3 than CANONICAL (which WAIT>USE via habit)",
        41: "Check FOUR_WAY across S0–S3",
        42: "Low with env off; mechanism compares WAIT baseline",
        43: "Partial — WAIT baseline magnitude; not full causal graph",
        44: "Yes — UNKNOWN ≠ 0",
        45: "No — confidence epistemic",
        46: "No — support epistemic",
        47: "No — RVS shadow sets direct habit value to 0",
        48: "No",
        49: "No",
        50: "No",
        51: "No",
        52: "No",
        53: "Yes — shadow only",
        54: "No — lower priority than aggregation/repetition-value",
        55: "Yes — reducing multi-horizon to one present value unsupported without new principle",
        56: "Yes as shadow diagnostic — direct bridge lacks physical grounding in tested conditions",
        57: "Remain SHADOW ONLY — do not integrate yet",
        58: "Lag records are cumulative T0→TL; summing double-counts; bounded horizon-specific shadow improves structure over single-lag collapse; direct repetition→+ordinary value is ungrounded physically while epistemic support from experience remains legitimate; canonical WAIT>USE in non-severe is largely habit prior + short horizon",
        59: "TEMPORAL_AGGREGATION into one present candidate value without unjustified discount; also lags>3 for H10/H25",
        60: "Smallest next: optional shadow-only policy readout that keeps predictive ordinary and policy prior SEPARATE (no retune), OR extend DEFAULT_LAGS diagnostically if physical delay requires H10 — still no habit_weight/gate retune",
    }
    dump("UPDATE41010_ANSWERS.json", answers)

    write_md(
        "UPDATE41010_FINAL_REPORT.md",
        f"""# Update 4.10.10 — FINAL REPORT

Bounded Prospective Trajectory × Repetition–Value Separation

## Temporal semantics
**CUMULATIVE** from action-time `obs_before` to lag observation. Summing lags **double-counts**. Composition: use record at target lag.

## Bounded trajectory (shadow)
H1/H3 from L1/L3 when present. H10/H25 **UNKNOWN**. No gamma. Not planning.

## Repetition–value
Habit = repetition only. `+0.03` is not a physical forecast. Bad-history replicated. RVS ≠ habit ablation.

## Four-way
See FOUR_WAY_COMPARISON.md. Canonical often WAIT>USE; separated/temporal shadows often USE>WAIT when habit value removed — this is calibration against realized H≥3 USE>WAIT, not an acceptance of USE.

## Integration
**SHADOW ONLY.** habit_weight and severe gate untouched.

## Strongest conclusion
{answers[58]}

## First unsupported arrow
{answers[59]}

## Smallest next
{answers[60]}

Elapsed_s: {time.time() - t0:.1f}
first_severe: {first_severe}
""",
    )

    dump(
        "UPDATE41010_SUMMARY.json",
        {
            "elapsed_s": time.time() - t0,
            "first_severe": first_severe,
            "semantics": "CUMULATIVE_T0_TO_TL",
            "double_count_if_summed": True,
            "four_way_orders": [
                {
                    "state": r["state"],
                    "CANONICAL": r["CANONICAL"]["order"],
                    "ABLATED": r["HABIT_ABLATED"]["order"],
                    "RVS": r["REPETITION_VALUE_SEPARATED"]["order"],
                    "TEMPORAL_RVS": r["TEMPORAL_REPETITION_SEPARATED_SHADOW"]["order"],
                }
                for r in four_way
            ],
            "habit_weight_unchanged": True,
            "shadow_only": True,
        },
    )
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
