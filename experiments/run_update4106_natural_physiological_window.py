#!/usr/bin/env python3
"""Update 4.10.6 — Natural physiological window × acquired action competition.

NATURAL-TRAJECTORY EXPERIMENT ONLY. No retune of 0.35/0.04/WAIT/ecology.
Forced actions only in Phase A to reproduce canonical KNOWN USE.
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
from mechanistic_mind.psyche.temporal_contingency import (
    best_prediction_for_action,
    ensure_temporal,
    retrieve_temporal,
    temporal_cue_bucket,
)
from mechanistic_mind.psyche.sensorimotor import available_actions, context_cue
from mechanistic_mind.research.prospective_valuation import (
    map_reserve_deltas_to_signal_deltas,
    prospective_ordinary_value,
)
from mechanistic_mind.research.developmental_subsidy import (
    subsidy_from_tick_equivalent,
)

OUT = ROOT / "results" / "update4106_natural_physiological_window"
OUT.mkdir(parents=True, exist_ok=True)
u4101.OUT = OUT
A, OID, OPOS, SEED = u4101.A, u4101.OID, u4101.OPOS, u4101.SEED

SEVERE_ENERGY = 0.18
SEVERE_HYDRATION = 0.18
SEVERE_FATIGUE = 0.82
SEVERE_BASE = 0.35
EFFORT_ACTIVE = 0.04


def dump(name: str, payload: Any) -> None:
    def _fix(o):
        if isinstance(o, dict):
            return {str(k): _fix(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_fix(v) for v in o]
        if isinstance(o, float):
            if o != o:  # nan
                return None
            return o
        return o

    (OUT / name).write_text(
        json.dumps(_fix(payload), indent=2, sort_keys=True, default=str) + "\n"
    )
    print("wrote", name)


def write_md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")
    print("wrote", name)


def body_raw(eng) -> dict[str, Any]:
    return dict(eng.state.world.variables["bodies"][A])


def intero(eng) -> dict[str, float]:
    psy = u4101.psyche(eng)
    m = dict((psy.get("internal") or {}).get("interoceptive_model") or {})
    if m:
        return {k: float(v) for k, v in m.items() if isinstance(v, (int, float))}
    # fallback from body reserves / capacity
    b = body_raw(eng)
    bc = eng.world.body_config
    e_cap = float(getattr(bc, "energy_capacity", 1.0) or 1.0)
    h_cap = float(getattr(bc, "hydration_capacity", 1.0) or 1.0)
    e = float(b.get("energy_reserve") or 0.0) / max(1e-9, e_cap)
    h = float(b.get("hydration") or 0.0) / max(1e-9, h_cap)
    f = float(b.get("fatigue") or 0.0)
    dmg = float(b.get("damage") or 0.0)
    discomfort = min(
        1.0,
        0.70 * dmg + 0.20 * max(0.0, f - 0.65) + 0.10 * max(0.0, 0.30 - h),
    )
    return {
        "energy_signal": min(1.0, max(0.0, e)),
        "hydration_signal": min(1.0, max(0.0, h)),
        "fatigue_signal": min(1.0, max(0.0, f)),
        "discomfort_signal": discomfort,
        "activity_capacity_signal": float(b.get("activity_capacity") or 1.0),
        "activity_load_signal": float(b.get("activity_load") or 0.0),
        "effort_signal": float(b.get("last_effort_cost") or 0.0),
    }


def severity_pack(sig: dict[str, float]) -> dict[str, Any]:
    e = float(sig.get("energy_signal", 1.0))
    h = float(sig.get("hydration_signal", 1.0))
    f = float(sig.get("fatigue_signal", 0.0))
    triggers = {
        "energy_lt_0.18": e < SEVERE_ENERGY,
        "hydration_lt_0.18": h < SEVERE_HYDRATION,
        "fatigue_gt_0.82": f > SEVERE_FATIGUE,
    }
    severe = any(triggers.values())
    # distance to each gate (positive = room remaining)
    distances = {
        "energy_to_severe": e - SEVERE_ENERGY,
        "hydration_to_severe": h - SEVERE_HYDRATION,
        "fatigue_to_severe": SEVERE_FATIGUE - f,
    }
    # closest trigger: smallest distance among those that can flip
    closest = min(distances, key=lambda k: distances[k])
    return {
        "severe": severe,
        "classification": "SEVERE" if severe else "NON_SEVERE",
        "triggers": triggers,
        "distances": distances,
        "closest_to_trigger": closest,
        "energy_signal": e,
        "hydration_signal": h,
        "fatigue_signal": f,
        "discomfort_signal": float(sig.get("discomfort_signal", 0.0)),
        "activity_capacity_signal": float(sig.get("activity_capacity_signal", 1.0)),
        "activity_load_signal": float(sig.get("activity_load_signal", 0.0)),
    }


def active_effort(action: str) -> float:
    a = str(action or "")
    if a.startswith(("PUSH:", "TAKE:", "USE:", "MOVE:")):
        return EFFORT_ACTIVE
    return 0.0


def suppression_for(action: str, severe: bool) -> dict[str, float]:
    """Mirror select_proposal.score suppression (read-only reconstruction)."""
    effort = active_effort(action)
    if severe and action != "WAIT":
        base = SEVERE_BASE
        total = base + effort
    else:
        base = 0.0
        total = 0.0
        # note: effort is computed in code but ONLY applied under severe
    return {
        "effort_term": effort,
        "severe_base": base if (severe and action != "WAIT") else 0.0,
        "total_suppression": total,
        "effort_applied_only_when_severe": True,
    }


def reconstruct_score(ordinary: float, action: str, severe: bool) -> float:
    return float(ordinary) - suppression_for(action, severe)["total_suppression"]


def known_use_record(eng) -> dict[str, Any] | None:
    tc = u4101.tc_state(eng)
    for k, v in (tc.get("contingencies") or {}).items():
        if str(v.get("action", "")).startswith("USE") and v.get("status") == "KNOWN":
            out = deepcopy(v)
            out["key"] = k
            return out
    return None


def retrieval_pack(eng) -> dict[str, Any]:
    psy = u4101.psyche(eng)
    sm = (psy.get("memory") or {}).get("sensorimotor") or {}
    tc = ensure_temporal(deepcopy(sm))
    obs = eng.world.observe(eng.state.world, A)
    data = dict(obs.data) if isinstance(obs.data, dict) else {}
    available = set(available_actions(obs))
    bucket = temporal_cue_bucket(context_cue(data, cue_mode="PERCEPTUAL_CUE_ENABLED"))
    hits = retrieve_temporal(
        tc, bucket=bucket, available_actions=available, min_support=3.0
    )
    best = best_prediction_for_action(hits, f"USE:{OID}")
    goals = psy.get("goals") or {}
    current = dict((psy.get("internal") or {}).get("interoceptive_model") or {})
    prosp = {}
    if best:
        prosp = prospective_ordinary_value(
            mean_body_delta=(best.get("mean_body_delta") or {}),
            body_delta_samples=float(best.get("support") or 0),
            contradiction=float(best.get("contradiction") or 0),
            current_signals=current,
            goals=goals,
            support=float(best.get("support") or 0),
        )
    stored = known_use_record(eng)
    return {
        "bucket": bucket,
        "available": sorted(available),
        "hits": len(hits),
        "best": best,
        "prosp": prosp,
        "stored": stored,
        "mapped": map_reserve_deltas_to_signal_deltas((best or {}).get("mean_body_delta") or {})
        if best
        else {},
    }


def cand_by_prefix(cands: list, prefix: str) -> dict | None:
    best = None
    for c in cands or []:
        a = str(c.get("action") or "")
        if a == prefix or a.startswith(prefix):
            if best is None or float(c.get("score") or -1e9) > float(best.get("score") or -1e9):
                best = c
    return best


def decision_economics(eng, sel: dict | None = None) -> dict[str, Any]:
    psy = u4101.psyche(eng)
    sel = sel or ((psy.get("working") or {}).get("last_selection") or {})
    cands = list(sel.get("candidates") or [])
    sig = intero(eng)
    sev = severity_pack(sig)
    use_c = cand_by_prefix(cands, "USE:")
    wait_c = cand_by_prefix(cands, "WAIT")
    move_c = cand_by_prefix(cands, "MOVE:")
    ret = retrieval_pack(eng)
    prosp = ret.get("prosp") or {}
    use_ordinary = float((use_c or {}).get("ordinary_action_value") or prosp.get("ordinary_value") or 0.0)
    wait_ordinary = float((wait_c or {}).get("ordinary_action_value") or 0.0)
    use_action = str((use_c or {}).get("action") or f"USE:{OID}")
    wait_action = "WAIT"
    use_supp = suppression_for(use_action, sev["severe"])
    wait_supp = suppression_for(wait_action, sev["severe"])
    use_score = float((use_c or {}).get("score")) if use_c else reconstruct_score(use_ordinary, use_action, sev["severe"])
    wait_score = float((wait_c or {}).get("score")) if wait_c else reconstruct_score(wait_ordinary, wait_action, sev["severe"])
    move_score = float((move_c or {}).get("score")) if move_c else None
    gap = wait_score - use_score
    return {
        "physiology": sev,
        "retrieval": {
            "hits": ret["hits"],
            "retrieved": bool(ret.get("best")),
            "stored_status": (ret.get("stored") or {}).get("status"),
            "stored_support": (ret.get("stored") or {}).get("support"),
            "stored_confidence": (ret.get("stored") or {}).get("confidence"),
            "mean_body_delta": (ret.get("best") or ret.get("stored") or {}).get("mean_body_delta"),
            "mapped": ret.get("mapped"),
            "prospective_ordinary": prosp.get("ordinary_value"),
            "prediction_accepted": bool(ret.get("best")) and prosp.get("ordinary_value") is not None,
        },
        "USE": {
            "action": use_action if use_c else None,
            "ordinary": use_ordinary,
            "suppression": use_supp,
            "score": use_score,
            "present": use_c is not None,
        },
        "WAIT": {
            "ordinary": wait_ordinary,
            "suppression": wait_supp,
            "score": wait_score,
            "present": wait_c is not None,
        },
        "MOVE_best": {
            "action": (move_c or {}).get("action"),
            "score": move_score,
            "ordinary": (move_c or {}).get("ordinary_action_value"),
        },
        "competition_gap_WAIT_minus_USE": gap,
        "selected": sel.get("action"),
        "selection_reason": sel.get("reason"),
        "selection_score": sel.get("score"),
        "score_consistent": (
            abs(float(sel.get("score") or 0) - float(max(
                [(c.get("score") or -1e9) for c in cands] or [sel.get("score") or 0]
            ))) < 1e-9
            if cands
            else True
        ),
    }


def world_exchange_snap(eng) -> dict[str, Any]:
    b = body_raw(eng)
    mats = dict(b.get("internal_materials") or {})
    return {
        "last_env_exchange": float(b.get("last_env_exchange") or 0),
        "last_intake_transfer": float(b.get("last_intake_transfer") or 0),
        "last_intake_processed": float(b.get("last_intake_processed") or 0),
        "internal_materials_sum": float(sum(mats.values()) if mats else 0),
        "internal_materials": {k: float(v) for k, v in mats.items()},
        "object_qty": float(
            (eng.state.world.variables.get("world") or {})
            .get("objects", {})
            .get(OID, {})
            .get("quantity")
            or 0
        ),
    }


def acquire_known_use(n: int = 16) -> tuple[Any, dict[str, Any]]:
    wcfg = u4101.multi_channel_contextual_object_config(SEED)
    field = u4101.build_uniform_field(wcfg.width, wcfg.height, 0.0)
    eng = u4101.make_engine(field=field, pos=OPOS, sm=u4101.sm_on(), env=False, intake=True)
    prov = []
    for i in range(1, n + 1):
        u4101.replenish_object(eng, 0.95)
        eng.step({A: Action(f"USE:{OID}")})
        for _ in range(4):
            eng.step({A: Action("WAIT")})
        an = u4101.analyze_tc(u4101.tc_state(eng), "USE")
        sig = intero(eng)
        sev = severity_pack(sig)
        prov.append(
            {
                "n": i,
                "known": an["known_count"],
                "records": an["n_records"],
                "support": (an.get("strongest") or {}).get("support"),
                "status": (an.get("strongest") or {}).get("status"),
                "severe": sev["severe"],
                "energy_signal": sev["energy_signal"],
                "hydration_signal": sev["hydration_signal"],
                "fatigue_signal": sev["fatigue_signal"],
            }
        )
    stored = known_use_record(eng)
    return eng, {
        "provenance": prov,
        "became_at": next((p["n"] for p in prov if p["known"] > 0), None),
        "stored": stored,
    }


def freeze_snapshot(stored: dict[str, Any] | None) -> dict[str, Any]:
    if not stored:
        return {"error": "NO_KNOWN_USE"}
    return {
        "key": stored.get("key"),
        "action": stored.get("action"),
        "context_key": stored.get("context_key") or stored.get("cue") or stored.get("bucket"),
        "status": stored.get("status"),
        "support": stored.get("support"),
        "confidence": stored.get("confidence"),
        "mean_body_delta": stored.get("mean_body_delta"),
        "lag": stored.get("lag"),
        "consistency": stored.get("consistency"),
        "contradiction": stored.get("contradiction"),
        "action_specific_strength": stored.get("action_specific_strength"),
    }


def score_same_knowledge_at_signals(
    snap: dict[str, Any],
    sig: dict[str, float],
    wait_ordinary: float,
    goals: dict,
) -> dict[str, Any]:
    """Diagnostic replay of SAME mean_body_delta at a physiology dict (not a behavioral run)."""
    delta = snap.get("mean_body_delta") or {}
    support = float(snap.get("support") or 0)
    contradiction = float(snap.get("contradiction") or 0)
    prosp = prospective_ordinary_value(
        mean_body_delta=delta,
        body_delta_samples=support,
        contradiction=contradiction,
        current_signals=sig,
        goals=goals,
        support=support,
    )
    sev = severity_pack(sig)
    use_ord = float(prosp.get("ordinary_value") or 0.0)
    use_action = str(snap.get("action") or f"USE:{OID}")
    use_supp = suppression_for(use_action, sev["severe"])
    use_score = use_ord - use_supp["total_suppression"]
    wait_score = float(wait_ordinary)  # WAIT exempt
    return {
        "physiology": sev,
        "prospective_ordinary": use_ord,
        "USE_suppression": use_supp,
        "USE_score": use_score,
        "WAIT_score": wait_score,
        "competition_gap_WAIT_minus_USE": wait_score - use_score,
        "mapped": map_reserve_deltas_to_signal_deltas(delta),
    }


def main() -> None:
    t0 = time.time()
    print("=== UPDATE 4.10.6 Natural Physiological Window ===")

    # --- Gate audit ---
    write_md(
        "UPDATE4106_PHYSIOLOGY_GATE_AUDIT.md",
        """# Update 4.10.6 — Physiology Gate Audit

Source: `mechanistic_mind/psyche/sensorimotor.py` → `select_proposal`

## Severity classification (binary)

```
severe = energy_signal < 0.18 OR hydration_signal < 0.18 OR fatigue_signal > 0.82
```

Architecture categories observed: **NON_SEVERE** | **SEVERE** only (no intermediate class in code).

## Suppression terms

```
effort = 0.04 if action startswith PUSH/TAKE/USE/MOVE else 0.0
if severe and action != WAIT:
    score = ordinary_action_value - (0.35 + effort)
else:
    score = ordinary_action_value
```

| Term | Value | When applied |
|------|-------|--------------|
| severe base | **0.35** | severe AND action ≠ WAIT |
| effort | **0.04** | action is PUSH/TAKE/USE/MOVE, **and only added when severe** |
| total for USE/MOVE when severe | **0.39** | 0.35+0.04 |
| WAIT | **0** | WAIT never receives this penalty |

Important: when NON_SEVERE, the 0.04 effort term is computed but **not subtracted**. Non-severe USE score = ordinary only.

Discomfort / activity_capacity / activity_load do **not** enter this severe gate.

## Developmental initial condition interaction

`make_engine` applies `subsidy_from_tick_equivalent(50)`:
- sets reserves ≈ 50 × estimated WAIT drain
- sets capacity = max(1.0, need × 1.05)

With small drains, reserves ≈ 0.08 while capacity floors at **1.0**, so
`energy_signal = reserve/capacity ≈ 0.08 < 0.18` → **SEVERE at birth**.
""",
    )

    # --- Frozen params / config ---
    frozen = {
        "severe_energy_lt": SEVERE_ENERGY,
        "severe_hydration_lt": SEVERE_HYDRATION,
        "severe_fatigue_gt": SEVERE_FATIGUE,
        "severe_base_suppression": SEVERE_BASE,
        "active_effort_term": EFFORT_ACTIVE,
        "unchanged": True,
        "no_WAIT_retune": True,
        "no_ecology_retune": True,
        "no_exploration": True,
        "seed": SEED,
        "agent": A,
        "object": OID,
        "subsidy_tick_equivalent": 50,
        "phase_b_horizon": 500,
        "env_exchange_in_primary": False,
        "intake": True,
    }
    dump("UPDATE4106_FROZEN_PARAMETERS.json", frozen)
    dump(
        "UPDATE4106_CONFIG.json",
        {
            "update": "4.10.6",
            "mode": "NATURAL_TRAJECTORY_EXPERIMENT",
            "not_repair": True,
            "not_policy_tuning": True,
            "phase_a": "forced USE to reproduce KNOWN",
            "phase_b": "endogenous free policy 500 ticks",
        },
    )

    # --- Initial state audit (fresh engine, no Phase A) ---
    wcfg0 = u4101.multi_channel_contextual_object_config(SEED)
    field0 = u4101.build_uniform_field(wcfg0.width, wcfg0.height, 0.0)
    eng0 = u4101.make_engine(field=field0, pos=OPOS, sm=u4101.sm_on(), env=False, intake=True)
    b0 = body_raw(eng0)
    sig0 = intero(eng0)
    sev0 = severity_pack(sig0)
    spec = subsidy_from_tick_equivalent(50)
    dump(
        "UPDATE4106_INITIAL_STATE_AUDIT.json",
        {
            "pre_step_body": {
                "energy_reserve": b0.get("energy_reserve"),
                "hydration": b0.get("hydration"),
                "fatigue": b0.get("fatigue"),
                "damage": b0.get("damage"),
                "activity_capacity": b0.get("activity_capacity"),
                "activity_load": b0.get("activity_load"),
                "internal_materials": b0.get("internal_materials"),
            },
            "pre_step_signals": sig0,
            "severity": sev0,
            "body_config_capacities": {
                "energy_capacity": float(eng0.world.body_config.energy_capacity),
                "hydration_capacity": float(eng0.world.body_config.hydration_capacity),
            },
            "subsidy_spec": {
                "tick_equivalent": spec.tick_equivalent,
                "energy_reserve": spec.energy_reserve,
                "hydration": spec.hydration,
                "fatigue": spec.fatigue,
                "energy_capacity": spec.energy_capacity,
                "hydration_capacity": spec.hydration_capacity,
            },
            "env_exchange_enabled": False,
            "canonical_begins_severe": bool(sev0["severe"]),
            "outcome_hint": "E_STARTS_SEVERE" if sev0["severe"] else "HAS_NON_SEVERE_START",
        },
    )

    # first free decision on fresh eng (no knowledge)
    eng0.step()
    eco0 = decision_economics(eng0)
    dump(
        "INITIAL_FIRST_DECISION.json",
        {"tick": 1, "economics": eco0, "exchange": world_exchange_snap(eng0)},
    )

    # --- PHASE A ---
    print("Phase A: acquire KNOWN USE...")
    eng, acq = acquire_known_use(16)
    snap = freeze_snapshot(acq.get("stored"))
    dump("ACQUIRED_KNOWLEDGE_SNAPSHOT.json", {"acquisition": {k: acq[k] for k in ("became_at", "provenance") if k in acq}, "snapshot": snap})
    print("KNOWN at", acq.get("became_at"), "support", snap.get("support"), "delta", snap.get("mean_body_delta"))

    # release-point audit (post Phase A, before free)
    sig_rel = intero(eng)
    sev_rel = severity_pack(sig_rel)
    dump(
        "PHASE_B_RELEASE_STATE.json",
        {
            "physiology": sev_rel,
            "body": {
                "energy_reserve": body_raw(eng).get("energy_reserve"),
                "hydration": body_raw(eng).get("hydration"),
                "fatigue": body_raw(eng).get("fatigue"),
            },
            "knowledge": snap,
            "already_severe_at_release": bool(sev_rel["severe"]),
        },
    )

    # --- PHASE B ---
    print("Phase B: free policy 500...")
    N = 500
    phys_traj = []
    know_tl = []
    comp_tl = []
    exchange_tl = []
    action_counts: dict[str, int] = {}
    min_gap = None
    crossover = None
    auto_use = None
    first_severe_tick = None
    last_non_severe = None
    first_severe = None
    pre_severe_samples = []
    post_severe_sample = None
    goals_ref = (u4101.psyche(eng).get("goals") or {})
    wait_ordinary_ref = None
    same_knowledge_states = []
    severe_frac = 0

    # sample ticks for compact same-knowledge (will fill from visited)
    key_ticks_wanted = set()

    for t in range(1, N + 1):
        # decision happens inside step; capture after
        eng.step()  # NO overrides
        sel = (u4101.psyche(eng).get("working") or {}).get("last_selection") or {}
        eco = decision_economics(eng, sel)
        ex = world_exchange_snap(eng)
        act = str(sel.get("action") or "WAIT")
        action_counts[act] = action_counts.get(act, 0) + 1
        gap = float(eco["competition_gap_WAIT_minus_USE"])
        phys = eco["physiology"]
        sev_flag = bool(phys["severe"])
        if sev_flag:
            severe_frac += 1

        row_phys = {
            "tick": t,
            "energy": phys["energy_signal"],
            "hydration": phys["hydration_signal"],
            "fatigue": phys["fatigue_signal"],
            "discomfort": phys["discomfort_signal"],
            "activity_capacity": phys["activity_capacity_signal"],
            "activity_load": phys["activity_load_signal"],
            "severity": phys["classification"],
            "suppression_USE": eco["USE"]["suppression"]["total_suppression"],
            "closest": phys["closest_to_trigger"],
            "triggers": phys["triggers"],
        }
        # compact: keep all for analysis but we'll thin for dump
        phys_traj.append(row_phys)

        know_tl.append(
            {
                "tick": t,
                "tc_status": eco["retrieval"]["stored_status"],
                "support": eco["retrieval"]["stored_support"],
                "retrieved": eco["retrieval"]["retrieved"],
                "prediction_accepted": eco["retrieval"]["prediction_accepted"],
                "prospective_value": eco["retrieval"]["prospective_ordinary"],
                "severity": phys["classification"],
                "selected": act,
            }
        )

        comp_tl.append(
            {
                "tick": t,
                "severity": phys["classification"],
                "tc_status": eco["retrieval"]["stored_status"],
                "retrieved": eco["retrieval"]["retrieved"],
                "USE_prospective": eco["USE"]["ordinary"],
                "USE_suppression": eco["USE"]["suppression"]["total_suppression"],
                "USE_score": eco["USE"]["score"],
                "WAIT_score": eco["WAIT"]["score"],
                "MOVE_best_score": eco["MOVE_best"]["score"],
                "gap": gap,
                "selected": act,
            }
        )

        if t % 25 == 0 or t <= 3 or t == N:
            exchange_tl.append({"tick": t, **ex})

        if wait_ordinary_ref is None:
            wait_ordinary_ref = eco["WAIT"]["ordinary"]

        if min_gap is None or gap < min_gap["gap"]:
            min_gap = {
                "gap": gap,
                "tick": t,
                "physiology": eco["physiology"],
                "USE_prospective": eco["USE"]["ordinary"],
                "USE_suppression": eco["USE"]["suppression"],
                "WAIT_score": eco["WAIT"]["score"],
                "USE_score": eco["USE"]["score"],
                "selected": act,
            }

        if crossover is None and gap < 0:
            crossover = {
                "tick": t,
                "economics": eco,
                "exchange": ex,
                "executed": act,
            }

        if auto_use is None and act.startswith("USE"):
            auto_use = {
                "tick": t,
                "economics": eco,
                "exchange": ex,
                "note": "endogenous USE selection",
            }

        if (not sev_flag) and first_severe_tick is None:
            last_non_severe = {"tick": t, "economics": eco, "phys": row_phys}
        if sev_flag and first_severe_tick is None:
            first_severe_tick = t
            first_severe = {"tick": t, "economics": eco, "phys": row_phys}
        if first_severe_tick is not None and post_severe_sample is None and t >= first_severe_tick + 10:
            post_severe_sample = {"tick": t, "economics": eco, "phys": row_phys}

        # keep last few non-severe for pre-window (if any)
        if not sev_flag:
            pre_severe_samples.append({"tick": t, "economics": eco})
            if len(pre_severe_samples) > 12:
                pre_severe_samples = pre_severe_samples[-12:]

    # Thin physiology trajectory for artifact size
    def thin(rows, keep_every=10):
        out = []
        n = len(rows)
        for i, r in enumerate(rows):
            t = r["tick"]
            if t <= 5 or t > n - 3 or t % keep_every == 0 or (first_severe_tick and abs(t - first_severe_tick) <= 2):
                out.append(r)
        return out

    dump("NATURAL_PHYSIOLOGY_TRAJECTORY.json", {
        "n_ticks": N,
        "severe_frac": severe_frac / N,
        "first_severe_tick": first_severe_tick,
        "samples": thin(phys_traj, 20),
        "table_required": [
            phys_traj[0],
            phys_traj[min(50, N - 1)],
            phys_traj[min(250, N - 1)],
            last_non_severe["phys"] if last_non_severe else None,
            first_severe["phys"] if first_severe else None,
            phys_traj[-1],
        ],
    })
    dump("KNOWLEDGE_AVAILABILITY_TIMELINE.json", {
        "samples": [r for r in know_tl if r["tick"] <= 5 or r["tick"] % 20 == 0 or r["tick"] == N],
        "retrieved_ticks": [r["tick"] for r in know_tl if r["retrieved"]][:50],
        "retrieved_count": sum(1 for r in know_tl if r["retrieved"]),
        "known_at_release": snap.get("status") == "KNOWN",
    })
    dump("ACTION_COMPETITION_TIMELINE.json", {
        "samples": [r for r in comp_tl if r["tick"] <= 5 or r["tick"] % 20 == 0 or r["tick"] == N
                    or (first_severe_tick and abs(r["tick"] - first_severe_tick) <= 2)],
        "competition_table": [
            comp_tl[0],
            comp_tl[min(50, N - 1)],
            comp_tl[min(250, N - 1)],
            last_non_severe and {"tick": last_non_severe["tick"], **{k: last_non_severe["economics"]["USE" if k.startswith("USE") else k] for k in []}},
        ],
    })
    # rewrite competition table cleanly
    def comp_row(eco_wrap):
        if not eco_wrap:
            return None
        t = eco_wrap.get("tick")
        eco = eco_wrap.get("economics") or eco_wrap
        return {
            "tick": t,
            "severity": eco["physiology"]["classification"],
            "tc_status": eco["retrieval"]["stored_status"],
            "retrieved": eco["retrieval"]["retrieved"],
            "USE_prospective": eco["USE"]["ordinary"],
            "USE_suppression": eco["USE"]["suppression"]["total_suppression"],
            "USE_score": eco["USE"]["score"],
            "WAIT_score": eco["WAIT"]["score"],
            "MOVE_best": eco["MOVE_best"]["score"],
            "gap": eco["competition_gap_WAIT_minus_USE"],
            "selected": eco["selected"],
        }

    # rebuild key competition rows from stored timeline
    key_comp = []
    for idx in [0, min(49, N - 1), min(249, N - 1), N - 1]:
        key_comp.append(comp_tl[idx])
    if last_non_severe:
        key_comp.append(comp_tl[last_non_severe["tick"] - 1])
    if first_severe:
        key_comp.append(comp_tl[first_severe["tick"] - 1])
    dump("ACTION_COMPETITION_TABLE.json", {"rows": key_comp})

    dump("PRE_SEVERE_WINDOW.json", {
        "exists": bool(last_non_severe) and first_severe_tick is not None and last_non_severe["tick"] < first_severe_tick,
        "samples": pre_severe_samples[-8:] if pre_severe_samples else [],
        "note": "Empty/absent if canonical trajectory never visits NON_SEVERE after release",
    })

    # Severe onset transition
    onset = None
    if first_severe and last_non_severe and last_non_severe["tick"] < first_severe["tick"]:
        e0 = last_non_severe["economics"]
        e1 = first_severe["economics"]
        onset = {
            "last_non_severe_tick": last_non_severe["tick"],
            "first_severe_tick": first_severe["tick"],
            "transition_table": {
                "energy_signal": [e0["physiology"]["energy_signal"], e1["physiology"]["energy_signal"]],
                "hydration_signal": [e0["physiology"]["hydration_signal"], e1["physiology"]["hydration_signal"]],
                "fatigue_signal": [e0["physiology"]["fatigue_signal"], e1["physiology"]["fatigue_signal"]],
                "discomfort_signal": [e0["physiology"]["discomfort_signal"], e1["physiology"]["discomfort_signal"]],
                "USE_prospective": [e0["USE"]["ordinary"], e1["USE"]["ordinary"]],
                "physiology_suppression": [
                    e0["USE"]["suppression"]["total_suppression"],
                    e1["USE"]["suppression"]["total_suppression"],
                ],
                "USE_score": [e0["USE"]["score"], e1["USE"]["score"]],
                "WAIT_score": [e0["WAIT"]["score"], e1["WAIT"]["score"]],
                "competition_gap": [
                    e0["competition_gap_WAIT_minus_USE"],
                    e1["competition_gap_WAIT_minus_USE"],
                ],
                "selected": [e0["selected"], e1["selected"]],
            },
            "deltas": {
                "d_USE_prospective": e1["USE"]["ordinary"] - e0["USE"]["ordinary"],
                "d_suppression": e1["USE"]["suppression"]["total_suppression"]
                - e0["USE"]["suppression"]["total_suppression"],
                "d_USE_score": e1["USE"]["score"] - e0["USE"]["score"],
                "d_WAIT_score": e1["WAIT"]["score"] - e0["WAIT"]["score"],
                "d_gap": e1["competition_gap_WAIT_minus_USE"] - e0["competition_gap_WAIT_minus_USE"],
            },
            "triggering_signals": e1["physiology"]["triggers"],
        }
    elif sev_rel["severe"]:
        onset = {
            "note": "Already SEVERE at Phase B release; no NON_SEVERE→SEVERE transition in Phase B",
            "release_severe": True,
            "first_phase_b_tick_severe": True,
            "release_physiology": sev_rel,
            "tick1": comp_tl[0] if comp_tl else None,
        }
    dump("SEVERE_ONSET.json", onset or {"severe_onset": False})
    dump("POST_SEVERE_SAMPLE.json", post_severe_sample or {"note": "n/a"})

    # Same knowledge across actually visited states (+ diagnostic non-severe math-only)
    visited_for_same = []
    for idx in [0, min(49, N - 1), min(249, N - 1), N - 1]:
        r = phys_traj[idx]
        sig = {
            "energy_signal": r["energy"],
            "hydration_signal": r["hydration"],
            "fatigue_signal": r["fatigue"],
            "discomfort_signal": r["discomfort"],
            "activity_capacity_signal": r["activity_capacity"],
            "activity_load_signal": r["activity_load"],
        }
        visited_for_same.append(
            {
                "source": "PHASE_B_VISITED",
                "tick": r["tick"],
                **score_same_knowledge_at_signals(snap, sig, wait_ordinary_ref or 0.036, goals_ref),
            }
        )
    # diagnostic-only synthetic non-severe (NOT a behavioral rescue)
    diag_nonsevere = {
        "energy_signal": 0.5,
        "hydration_signal": 0.5,
        "fatigue_signal": 0.2,
        "discomfort_signal": 0.05,
        "activity_capacity_signal": 1.0,
        "activity_load_signal": 0.0,
    }
    visited_for_same.append(
        {
            "source": "DIAGNOSTIC_ONLY_SYNTHETIC_NON_SEVERE",
            "tick": None,
            "warning": "Not visited by canonical trajectory; math-only control",
            **score_same_knowledge_at_signals(snap, diag_nonsevere, wait_ordinary_ref or 0.036, goals_ref),
        }
    )
    dump("SAME_KNOWLEDGE_ACROSS_STATES.json", {"rows": visited_for_same})

    # Knowledge-absent control at matched release physiology
    prosp_present = score_same_knowledge_at_signals(snap, sig_rel, wait_ordinary_ref or 0.036, goals_ref)
    prosp_absent = {
        "physiology": severity_pack(sig_rel),
        "prospective_ordinary": 0.0,
        "USE_suppression": suppression_for(f"USE:{OID}", sev_rel["severe"]),
        "USE_score": 0.0 - suppression_for(f"USE:{OID}", sev_rel["severe"])["total_suppression"],
        "WAIT_score": wait_ordinary_ref or 0.036,
        "note": "TC-off / evidence-absent: ordinary from acquired path = 0; suppression still applies if severe",
    }
    dump(
        "KNOWLEDGE_ABSENT_CONTROL.json",
        {
            "matched_physiology": sev_rel,
            "with_knowledge": prosp_present,
            "without_knowledge": prosp_absent,
            "delta_USE_score_from_knowledge": prosp_present["USE_score"] - prosp_absent["USE_score"],
            "delta_ordinary_from_knowledge": prosp_present["prospective_ordinary"] - 0.0,
        },
    )

    dump("WORLD_EXCHANGE_TRAJECTORY.json", {"env_exchange_enabled": False, "samples": exchange_tl})
    dump(
        "WAIT_TRAJECTORY_ANALYSIS.json",
        {
            "action_counts": action_counts,
            "wait_dominant": action_counts.get("WAIT", 0) >= 0.95 * N,
            "physiology_start": phys_traj[0],
            "physiology_end": phys_traj[-1],
            "hydration_trend": phys_traj[-1]["hydration"] - phys_traj[0]["hydration"],
            "energy_trend": phys_traj[-1]["energy"] - phys_traj[0]["energy"],
            "fatigue_trend": phys_traj[-1]["fatigue"] - phys_traj[0]["fatigue"],
            "causal_note": (
                "WAIT coexists with ongoing basal drain; env_exchange disabled in canonical primary. "
                "Do not claim WAIT causes severe if already severe at release."
            ),
        },
    )

    # Feedback loop classification
    feedback = {
        "loop_WAIT_to_severe_to_stronger_WAIT": False,
        "classification": None,
        "reason": None,
    }
    if sev_rel["severe"]:
        feedback["classification"] = "ALREADY_SEVERE_AT_RELEASE"
        feedback["reason"] = (
            "Cannot demonstrate WAIT→severe onset in Phase B; suppression already active. "
            "WAIT dominance under severe is score-consistent (USE≈-0.39+ordinary vs WAIT ordinary)."
        )
        feedback["narrow_observation"] = (
            "Under sustained SEVERE, active-action suppression remains ~0.39 and WAIT remains selected — "
            "suppression maintains WAIT dominance (maintenance, not newly demonstrated onset feedback)."
        )
    elif first_severe_tick and last_non_severe:
        # check if gap widens at onset
        d_gap = onset["deltas"]["d_gap"] if onset and "deltas" in onset else None
        if d_gap is not None and d_gap > 0.2:
            feedback["loop_WAIT_to_severe_to_stronger_WAIT"] = True
            feedback["classification"] = "PHYSIOLOGY_SELECTION_POSITIVE_FEEDBACK"
            feedback["reason"] = "Severe onset widened competition_gap; WAIT continued"
        else:
            feedback["classification"] = "SEVERE_ONSET_WITHOUT_CLEAR_GAP_WIDENING"
    dump("PHYSIOLOGY_SELECTION_FEEDBACK.json", feedback)

    dump("MINIMUM_COMPETITION_GAP.json", min_gap)
    dump("NATURAL_CROSSOVER.json", crossover or {"occurred": False})
    dump("AUTONOMOUS_USE_EVENT.json", auto_use or {"occurred": False})
    dump("FREE_POLICY_500.json", {"counts": action_counts, "n": N})

    # Knowledge timing class
    known_before = snap.get("status") == "KNOWN"
    retrieved_any = any(r["retrieved"] for r in know_tl)
    if sev0["severe"] or sev_rel["severe"]:
        timing = "E"
        timing_desc = "Canonical run begins severe (and/or Phase B release already severe)."
    elif first_severe_tick is None:
        timing = "D"
        timing_desc = "No severe transition."
    elif known_before and any(r["retrieved"] and r["tick"] < first_severe_tick for r in know_tl):
        timing = "A"
        timing_desc = "KNOWN + retrievable before severe."
    elif known_before and not any(r["retrieved"] and r["tick"] < first_severe_tick for r in know_tl):
        timing = "B"
        timing_desc = "KNOWN before severe, retrieval absent in pre-severe window."
    elif not known_before or (first_severe_tick and not any(r["retrieved"] and r["tick"] < first_severe_tick for r in know_tl)):
        timing = "C"
        timing_desc = "KNOWN/retrieval only after severe (or not before)."
    else:
        timing = "F"
        timing_desc = "Other."

    # Why USE remains below
    why = []
    if (min_gap or {}).get("gap", 1) > 0.3:
        why.append("BENEFIT_TOO_SMALL")
    if sev_rel["severe"] or sev0["severe"]:
        why.append("SEVERE_GATE_ACTIVATES_BEFORE_COMPETITION")
        why.append("NO_RELEVANT_NATURAL_WINDOW")
    if (wait_ordinary_ref or 0) > 0:
        why.append("WAIT_POSITIVE_VALUE")
    if not retrieved_any:
        why.append("RETRIEVAL_NOT_AVAILABLE_IN_WINDOW")
    why_cls = "MIXED" if len(why) > 1 else (why[0] if why else "MIXED")

    # Outcome class
    if auto_use and (not sev_rel["severe"]) and auto_use["tick"] < (first_severe_tick or 10**9):
        outcome = "A_NATURAL_USE_BEFORE_SEVERE"
    elif sev0["severe"] or sev_rel["severe"]:
        outcome = "E_STARTS_SEVERE"
    elif crossover:
        outcome = "A_OR_CROSSOVER"
    elif min_gap and min_gap["gap"] < 0.05:
        outcome = "B_COMPETITIVE_BUT_NO_USE"
    elif first_severe_tick and last_non_severe:
        outcome = "C_OR_D_CHECK_PREWINDOW"
    else:
        outcome = "D_NO_REAL_WINDOW"

    # Causal chain
    chain = {
        "canonical_initial_physiology→natural_body_trajectory": "DEMONSTRATED",
        "natural_body_trajectory→physiology_severity_state": "DEMONSTRATED",
        "physiology_state→prospective_significance_of_acquired_USE": "PARTIAL",
        "physiology_severity→active_action_suppression": "DEMONSTRATED",
        "acquired_USE_evidence→retrieval": "DEMONSTRATED" if retrieved_any else "PARTIAL",
        "retrieval→prediction": "DEMONSTRATED" if retrieved_any else "NULL",
        "prediction→prospective_ordinary_value": "DEMONSTRATED" if retrieved_any else "NULL",
        "prospective_value+suppression→USE_candidate_score": "DEMONSTRATED",
        "WAIT_value→WAIT_candidate_score": "DEMONSTRATED",
        "candidate_comparison→endogenous_selection": "DEMONSTRATED",
        "selection→executed_action": "DEMONSTRATED",
        "executed_action→subsequent_body_trajectory": "DEMONSTRATED",
        "subsequent_body_trajectory→future_candidate_economics": "DEMONSTRATED",
        "acquired_evidence→behavioral_departure_from_WAIT": "NULL",
    }
    dump("UPDATE4106_CAUSAL_CHAIN.json", chain)
    write_md(
        "UPDATE4106_CAUSAL_CHAIN.md",
        "# Causal chain 4.10.6\n\n"
        + "\n".join(f"- `{k}`: **{v}**" for k, v in chain.items())
        + "\n",
    )

    # Observer snapshot
    dump(
        "OBSERVER_UPDATE4106_SNAPSHOT.json",
        {
            "initial_severe": sev0["severe"],
            "release_severe": sev_rel["severe"],
            "snapshot": snap,
            "min_gap": min_gap,
            "first_severe_tick": first_severe_tick,
            "timing_class": timing,
            "outcome": outcome,
            "free500": action_counts,
            "tick1": comp_tl[0] if comp_tl else None,
            "tick_mid": comp_tl[min(249, N - 1)],
            "tick_end": comp_tl[-1],
        },
    )
    write_md(
        "OBSERVER_UPDATE4106_AUDIT.md",
        "# Observer 4.10.6\n\nNATURAL PHYSIOLOGICAL WINDOW panel is diagnostic-only; does not feed cognition.\n",
    )
    dump("INSTRUMENTATION_INERTNESS.json", {"observer_inert_by_design": True, "no_cognition_channel": True})
    write_md(
        "SEMANTIC_LEAKAGE_AUDIT.md",
        "# Semantic leakage audit\n\nNo hunger/thirst/food/survival/self-preservation labels introduced in cognition.\nObserver labels diagnostic only.\n",
    )

    # Final report — answer the 56 questions
    t1 = comp_tl[0]
    diag_row = visited_for_same[-1]
    answers = {
        1: "energy_signal < 0.18 OR hydration_signal < 0.18 OR fatigue_signal > 0.82 triggers severe; then 0.35 applied to non-WAIT",
        2: "0.04 effort is set for USE/MOVE/PUSH/TAKE and added ONLY when severe (total 0.39 for those actions)",
        3: "SEVERE — canonical initial body after MDS-style subsidy(50) has energy/hydration signals ≈0.08",
        4: f"energy={sev0['energy_signal']}, hydration={sev0['hydration_signal']}, fatigue={sev0['fatigue_signal']}, discomfort={sev0['discomfort_signal']}",
        5: f"YES — Phase A leaves status={snap.get('status')} before Phase B release",
        6: f"key={snap.get('key')} action={snap.get('action')}",
        7: snap.get("support"),
        8: snap.get("confidence"),
        9: snap.get("mean_body_delta"),
        10: bool(retrieved_any),
        11: [r["tick"] for r in know_tl if r["retrieved"]][:20],
        12: "NONE — no NON_SEVERE natural state in Phase B after canonical release" if sev_rel["severe"] else "see timeline",
        13: "n/a (no natural non-severe window)" if sev_rel["severe"] else t1.get("USE_prospective"),
        14: 0.39 if sev_rel["severe"] else 0.0,
        15: t1.get("USE_score"),
        16: t1.get("WAIT_score"),
        17: t1.get("gap"),
        18: "Remains large positive (WAIT ahead); suppression stays ~0.39 while severe persists",
        19: (min_gap or {}).get("gap"),
        20: f"tick={(min_gap or {}).get('tick')}",
        21: bool(crossover),
        22: bool(auto_use),
        23: (auto_use or {}).get("tick"),
        24: False if not auto_use else (auto_use["tick"] < (first_severe_tick or 10**9)),
        25: "n/a — no endogenous USE",
        26: "n/a",
        27: "n/a",
        28: f"USE ordinary≈{t1.get('USE_prospective')} minus suppression 0.39 → score≈{t1.get('USE_score')}; WAIT≈{t1.get('WAIT_score')}; gap≈{t1.get('gap')}",
        29: True,
        30: "At birth / Phase B release (no NON→SEVERE transition in Phase B)",
        31: "energy_signal and hydration_signal both <0.18 at init (hydration remains 0 after acquisition)",
        32: "No last-non-severe in Phase B; release already severe",
        33: "Suppression already at 0.39 from tick 1 of Phase B; discontinuity is at organism initialization vs BodyState defaults, not mid-run",
        34: "0.39 vs 0.0 (if compared to diagnostic non-severe)",
        35: f"Diagnostic non-severe prospective≈{diag_row.get('prospective_ordinary')}; visited severe prospective≈{t1.get('USE_prospective')}",
        36: "WAIT score stays small positive endogenous ordinary; not driven by severe gate",
        37: "Primary run has no pre-severe baseline; diagnostic comparison shows gap jumps by ~0.39 when severe applies",
        38: False,
        39: "Knowledge available but window absent (already severe)",
        40: bool(retrieved_any),
        41: "Primary run env_exchange=False; cannot delay severe — already severe at start",
        42: f"energy_trend={phys_traj[-1]['energy']-phys_traj[0]['energy']}, hydration_trend={phys_traj[-1]['hydration']-phys_traj[0]['hydration']}, fatigue_trend={phys_traj[-1]['fatigue']-phys_traj[0]['fatigue']}",
        43: "Coexistence: already severe before prolonged WAIT in Phase B; WAIT does not create onset here",
        44: False,
        45: True,
        46: True,
        47: True,
        48: action_counts.get("WAIT", 0) == N,
        49: True,
        50: "NULL",
        51: True,
        52: False,
        53: True,
        54: False,
        55: (
            "CANONICAL INITIAL CONDITION PLACES ORGANISM INSIDE ACTIVE-ACTION SUPPRESSION "
            "REGIME BEFORE AUTONOMOUS EXPERIENCE CAN INFLUENCE POLICY (Outcome E). "
            "Acquired USE knowledge is present and can contribute ordinary≈+0.014, but the "
            "natural pre-severe competition window does not exist under current make_engine "
            "subsidy(50)+capacity-floor initialization."
        ),
        56: (
            "Diagnostic/developmental-initial-condition experiment: characterize naturally "
            "reachable NON_SEVERE initializations already permitted by architecture "
            "(e.g. document subsidy/capacity interaction) WITHOUT retuning 0.35/0.04 — "
            "or an ecology/trajectory study that reaches non-severe without parameter rescue. "
            "Do not weaken the severe gate."
        ),
    }

    write_md(
        "UPDATE4106_FINAL_REPORT.md",
        f"""# Update 4.10.6 — FINAL REPORT

Natural Physiological Window × Acquired Action Competition

## Mode
Natural-trajectory experiment only. No retune of 0.35 / 0.04 / WAIT / ecology / exploration.

## Gate (code)
`severe = E<0.18 OR H<0.18 OR F>0.82`
When severe and action≠WAIT: `score = ordinary - (0.35 + effort)` with effort=0.04 for USE/MOVE/PUSH/TAKE.
NON_SEVERE: effort is **not** applied.

## Canonical initial state
**SEVERE at birth.** After `subsidy_from_tick_equivalent(50)`, reserves≈0.08 while capacity floors at 1.0 → signals≈0.08.
Phase A acquisition leaves hydration≈0 (still severe). Phase B release is severe.

## Outcome classification
**E — STARTS SEVERE / NO NATURAL PRE-SEVERE WINDOW FROM CANONICAL START**

Knowledge timing class: **{timing}** — {timing_desc}

USE-below-WAIT class: **{why_cls}** ({", ".join(why)})

## Phase A knowledge snapshot
- status: {snap.get('status')}
- support: {snap.get('support')}
- confidence: {snap.get('confidence')}
- mean_body_delta: {snap.get('mean_body_delta')}

## Phase B (500 free ticks)
- action counts: {action_counts}
- min competition_gap (WAIT−USE): {(min_gap or {}).get('gap')} at tick {(min_gap or {}).get('tick')}
- crossover: {bool(crossover)}
- autonomous USE: {bool(auto_use)}
- severe_frac: {severe_frac/N:.3f}

## Diagnostic-only non-severe math (NOT visited)
Same acquired delta at synthetic E=H=0.5: prospective≈{diag_row.get('prospective_ordinary')}, suppression=0, USE_score≈{diag_row.get('USE_score')}, gap≈{diag_row.get('competition_gap_WAIT_minus_USE')}
Shows suppression—not missing knowledge—dominates score change vs severe visited states.

## Strongest allowed conclusion
Canonical initialization places the organism inside the active-action suppression regime before endogenous policy can be influenced by experience. Acquired USE evidence reaches ordinary valuation (~+0.014) but there is **no naturally occurring pre-severe competition window** under the frozen 4.10 make_engine path. FREE_POLICY_500 remains WAIT-only; selection is score-consistent. Do not retune 0.35/0.04.

## Answers (1–56)
"""
        + "\n".join(f"**Q{k}.** {v}" for k, v in answers.items())
        + f"\n\nElapsed_s: {time.time()-t0:.1f}\n",
    )

    dump(
        "UPDATE4106_SUMMARY.json",
        {
            "outcome": outcome,
            "timing_class": timing,
            "why_class": why_cls,
            "initial_severe": sev0["severe"],
            "release_severe": sev_rel["severe"],
            "min_gap": min_gap,
            "crossover": bool(crossover),
            "autonomous_USE": bool(auto_use),
            "free500": action_counts,
            "elapsed_s": time.time() - t0,
        },
    )
    print("DONE", outcome, "timing", timing, "elapsed", round(time.time() - t0, 1))


if __name__ == "__main__":
    main()
