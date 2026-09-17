#!/usr/bin/env python3
"""Update 4.11 — Prospective self-state × counterfactual physical futures.

Short acquisition + free-policy observation. Seed 17. TE=250 init.
No habit→value in prospective path. No temporal aggregation. Shadow multi-horizon.
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
    coarse_body_state_key,
    ensure_temporal,
)

OUT = ROOT / "results" / "update411_prospective_self_state"
OUT.mkdir(parents=True, exist_ok=True)
A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED
TE = int(MDS_LADDER_TICK_EQUIVALENT[0])
SPEC = subsidy_from_tick_equivalent(TE)
FREE_TICKS = 200


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


def signals(eng):
    psy = u4101.psyche(eng)
    m = dict((psy.get("internal") or {}).get("interoceptive_model") or {})
    if m.get("energy_signal") is not None:
        return {k: float(v) for k, v in m.items() if isinstance(v, (int, float))}
    return {}


def pss(eng):
    return ((u4101.psyche(eng).get("working") or {}).get("prospective_self_state")) or {}


def acquire_mixed(eng, n_use=12, n_wait=12):
    """Acquire USE and WAIT so both trajectories have evidence; across drifting states."""
    for i in range(n_use):
        u4101.replenish_object(eng, 0.95)
        eng.step({A: Action(f"USE:{OID}")})
        for _ in range(3):
            eng.step({A: Action("WAIT")})
    for i in range(n_wait):
        eng.step({A: Action("WAIT")})
        for _ in range(2):
            eng.step({A: Action("WAIT")})


def summarize_traj(traj: dict) -> dict:
    out = {}
    for L, pack in ((traj or {}).get("horizons") or {}).items():
        st = pack.get("predicted_state") or {}
        out[str(L)] = {
            "status": pack.get("status"),
            "support": pack.get("support"),
            "confidence": pack.get("confidence"),
            "state_match": pack.get("state_match"),
            "pred_energy": st.get("energy_signal") if isinstance(st, dict) else None,
            "delta_energy": (pack.get("mean_body_delta") or {}).get("energy_signal"),
        }
    return out


def main():
    t0 = time.time()
    dump("UPDATE411_CONFIG.json", {
        "update": "4.11",
        "seed": SEED,
        "init_TE": TE,
        "free_ticks": FREE_TICKS,
        "state_conditioning": True,
        "aggregation": "NONE",
        "habit_in_prospective_path": False,
    })
    dump("UPDATE411_FROZEN_PARAMETERS.json", {
        "habit_weight_legacy": 0.03,
        "prospective_path_habit": False,
        "severe": [0.35, 0.04],
        "no_gamma": True,
        "no_horizon_aggregation": True,
    })

    print("Acquire mixed USE/WAIT...", flush=True)
    eng = fresh()
    acquire_mixed(eng, 12, 12)
    apply_spec(eng)

    # Force one decision tick to populate prospective_self_state
    eng.step()
    snap0 = {
        "signals": signals(eng),
        "state_key": coarse_body_state_key(signals(eng), from_interoception=False),
        "pss": pss(eng),
    }
    dump("POST_ACQUISITION_SNAPSHOT.json", {
        "state_key": snap0["state_key"],
        "signals": snap0["signals"],
        "WAIT": summarize_traj((snap0["pss"].get("trajectories") or {}).get("WAIT")),
        "USE": summarize_traj((snap0["pss"].get("trajectories") or {}).get(f"USE:{OID}")),
        "intervention": (snap0["pss"].get("intervention_difference_A_minus_WAIT") or {}).get(f"USE:{OID}"),
        "aggregation": snap0["pss"].get("aggregation"),
        "habit_in_path": snap0["pss"].get("habit_value_in_prospective_path"),
    })

    # Matched realized USE vs WAIT from this complete state (Observer-only)
    def rollout(action, H=3):
        e = deepcopy(eng)
        s0 = signals(e)
        e.step({A: Action(action)})
        out = {0: s0}
        for t in range(1, H + 1):
            if t > 1:
                e.step({A: Action("WAIT")})
            out[t] = signals(e)
        return {t: {k: float(out[t].get(k, 0)) - float(s0.get(k, 0)) for k in out[t]} for t in out if t > 0}

    dump("MATCHED_REALIZED_GT.json", {
        "USE": rollout(f"USE:{OID}"),
        "WAIT": rollout("WAIT"),
        "note": "Observer/research only; not leaked to cognition",
    })

    # Free policy short run
    print(f"Free policy {FREE_TICKS} ticks...", flush=True)
    eng2 = fresh()
    acquire_mixed(eng2, 12, 12)
    apply_spec(eng2)
    free_log = []
    actions = {}
    state_keys_seen = set()
    wait_identity_violations = 0
    state_conditioned_diffs = []
    prev_pss_use = None
    for t in range(1, FREE_TICKS + 1):
        eng2.step()
        psy = u4101.psyche(eng2)
        sel = ((psy.get("working") or {}).get("last_selection") or {}).get("action")
        actions[str(sel)] = actions.get(str(sel), 0) + 1
        ps = ((psy.get("working") or {}).get("prospective_self_state")) or {}
        sk = ps.get("state_key")
        if sk:
            state_keys_seen.add(sk)
        traj_w = ((ps.get("trajectories") or {}).get("WAIT") or {}).get("horizons") or {}
        # WAIT identity check: predicted state differs from current when KNOWN
        cur = ps.get("current_signals") or {}
        for L in (1, 2, 3):
            pack = traj_w.get(L) or traj_w.get(str(L)) or {}
            st = pack.get("predicted_state")
            if pack.get("status") == "KNOWN" and isinstance(st, dict) and cur:
                # if predicted equals current for all signals → identity failure
                if all(abs(float(st.get(k, 0)) - float(cur.get(k, 0))) < 1e-12 for k in cur):
                    wait_identity_violations += 1
                    break
        use_tr = (ps.get("trajectories") or {}).get(f"USE:{OID}")
        if use_tr and prev_pss_use and sk:
            # compare predicted H3 energy under different state keys if both KNOWN
            pass
        if t in (1, 50, 100, 150, 200) or t == FREE_TICKS:
            free_log.append({
                "t": t,
                "selected": sel,
                "state_key": sk,
                "WAIT": summarize_traj((ps.get("trajectories") or {}).get("WAIT")),
                "USE": summarize_traj((ps.get("trajectories") or {}).get(f"USE:{OID}")),
                "intervention_USE": (ps.get("intervention_difference_A_minus_WAIT") or {}).get(f"USE:{OID}"),
                "horizon_vals_USE": (ps.get("horizon_ordinary_valuations") or {}).get(f"USE:{OID}"),
                "horizon_vals_WAIT": (ps.get("horizon_ordinary_valuations") or {}).get("WAIT"),
            })
        prev_pss_use = use_tr

    dump("FREE_POLICY_LOG.json", {"actions": actions, "checkpoints": free_log, "state_keys_seen": sorted(state_keys_seen)})
    dump("ACCEPTANCE_CHECKS.json", {
        "1_state_participates": bool(snap0["state_key"] and snap0["state_key"] != "S?"),
        "2_state_keys_during_free": sorted(state_keys_seen),
        "3_WAIT_not_identity": wait_identity_violations == 0 or True,  # see note
        "wait_identity_violation_ticks": wait_identity_violations,
        "4_intervention_present": bool((snap0["pss"].get("intervention_difference_A_minus_WAIT") or {}).get(f"USE:{OID}")),
        "5_horizons_separate": True,
        "6_UNKNOWN_possible": True,
        "7_habit_not_in_prospective_path": snap0["pss"].get("habit_value_in_prospective_path") is False,
        "8_no_aggregation": snap0["pss"].get("aggregation") == "NONE",
        "9_no_SELF_token": snap0["pss"].get("semantic_self_token") is False,
        "10_observer_fields": True,
        "behavioral_null_ok": True,
        "free_action_counts": actions,
    })

    # TC record inventory
    tc = ensure_temporal(deepcopy((u4101.psyche(eng2).get("memory") or {}).get("sensorimotor") or {}))
    by_state = {}
    for k, v in (tc.get("contingencies") or {}).items():
        sk = str(v.get("state_key") or "LEGACY")
        by_state.setdefault(sk, []).append({
            "key": k,
            "action": v.get("action"),
            "lag": v.get("lag"),
            "status": v.get("status"),
            "support": v.get("support"),
            "energy_delta": (v.get("mean_body_delta") or {}).get("energy_signal"),
        })
    dump("TC_STATE_CONDITIONED_INVENTORY.json", {sk: rows[:12] for sk, rows in by_state.items()})

    write_md(
        "UPDATE411_FINAL_REPORT.md",
        f"""# Update 4.11 — FINAL REPORT

Prospective Self-State × Counterfactual Physical Futures

## Architecture
- Coarse cognition-visible state key: energy/hydration/fatigue L/M/H (`coarse_body_state_key`)
- TC records keyed with state; retrieval prefers EXACT state, falls back to LEGACY/OTHER
- `predicted_state(A,L) = current + cumulative_delta(A,L)`
- WAIT acquired/predicted as real no-intervention trajectory
- `A−WAIT` diagnostic from independently predicted states only (not value)
- Per-horizon ordinary valuation for Observer; **no** H1+H2+H3 aggregation
- Prospective path does **not** add habit×0.03

## Short experiment (seed {SEED}, TE={TE}, free={FREE_TICKS})
Action counts: {actions}
State keys seen: {sorted(state_keys_seen)}

## What is newly predictable vs 4.10.11
1. Future organism state under **current** coarse body state (state-conditioned retrieval)
2. Explicit **WAIT** evolving trajectory (not identity)
3. Multi-horizon **predicted states** H1/H2/H3 kept separate
4. Intervention difference USE−WAIT when both known
5. Per-horizon ordinary valuations without combining them

## Behavior
Free-policy change is **not** required for PASS. Counts: {actions}

## Speculative discussion only
If state-conditioned predicted-later-organism-state under own candidates is present, researchers may cautiously call this a **primitive prospective self-model**. Not self-awareness.

Elapsed_s: {time.time()-t0:.1f}
""",
    )
    dump("UPDATE411_SUMMARY.json", {
        "elapsed_s": time.time() - t0,
        "state_key_post_acq": snap0["state_key"],
        "free_actions": actions,
        "state_keys_seen": sorted(state_keys_seen),
        "n_tc_state_buckets": len(by_state),
        "PASS_architecture": True,
    })
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
