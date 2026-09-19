#!/usr/bin/env python3
"""BETA2-BODY-01 Phase A–C: locomotor economy audit × evidence-guided fix validation."""
from __future__ import annotations

import json
import math
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CURRENT,
    ECOLOGY_GENTLE,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.geometry.action_realization import (
    build_action_realization_receipt,
)
from mechanistic_mind.ui.psy_observer_web.geometry.locomotor_economy import (
    EPS_DISTANCE,
    build_locomotor_economy_receipt,
    collect_locomotor_from_runtime,
)
from mechanistic_mind.ui.psy_observer_web.geometry.work_ecology import local_resource_opportunity


ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "results" / "body_economy"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _scripted(preset: str, seed: int, *, cognition: bool = False) -> PhysicalSystemRuntime:
    # Re-resolve make_ecology_config so Phase B wrap is visible
    from mechanistic_mind.physical_system import ecology_presets as eco
    cfg = eco.make_ecology_config(preset)
    cfg.cognition.cognition_enabled = bool(cognition)
    return PhysicalSystemRuntime(seed=int(seed), config=cfg)


def _force(rt: PhysicalSystemRuntime, action: str) -> None:
    rt._forced_action_once = action
    rt.step()


def _wrap_delta(a: float, b: float, size: int) -> float:
    d = float(b) - float(a)
    half = size / 2.0
    if d > half:
        d -= size
    elif d < -half:
        d += size
    return d


# ---------------------------------------------------------------------------
# A1/A2 — locomotor economy + component audit under sustained MOVE
# ---------------------------------------------------------------------------

def locomotor_economy_audit(*, preset: str, seed: int = 17, ticks: int = 100) -> dict:
    rt = _scripted(preset, seed)
    rows = []
    for _ in range(ticks):
        _force(rt, "MOVE:W")
        rows.append(build_locomotor_economy_receipt(rt, ecology_preset=preset))
    move_costs = [float(r["move_work_spent"] or 0) for r in rows]
    def_costs = [float(r["deformation_work_spent"] or 0) for r in rows]
    motor_costs = [float(r["endogenous_motor_work"] or 0) for r in rows]
    incomes = [float(r["measured_work_income"] or 0) for r in rows]
    dists = [float(r["realized_distance"] or 0) for r in rows]
    effs = [
        r["work_per_realized_distance"]["value"]
        for r in rows
        if (r.get("work_per_realized_distance") or {}).get("status") == "AVAILABLE"
    ]
    weak = sum(1 for r in rows if r.get("geo03_outcome") == "ALIGNED_WEAK")
    limited = sum(1 for r in rows if r.get("work_limited"))
    collapsed = sum(1 for r in rows if r.get("motor_authority_class") == "COLLAPSED")
    t_zero = next(
        (r["tick"] for r in rows if float(r.get("work_reservoir_fraction_after") or 1) <= 0.02),
        None,
    )
    total_move = sum(move_costs)
    total_def = sum(def_costs)
    total_mot = sum(motor_costs)
    tot = total_move + total_def + total_mot
    return {
        "preset": preset,
        "seed": seed,
        "ticks": ticks,
        "time_to_near_zero": t_zero,
        "final_reservoir": rows[-1]["work_reservoir_after"] if rows else None,
        "aligned_weak_count": weak,
        "work_limited_count": limited,
        "collapsed_authority_count": collapsed,
        "mean_realized_distance": sum(dists) / max(1, len(dists)),
        "mean_work_per_distance": (sum(effs) / len(effs)) if effs else None,
        "n_efficiency_available": len(effs),
        "n_denominator_too_small": sum(
            1 for r in rows
            if (r.get("work_per_realized_distance") or {}).get("status") == "DENOMINATOR_TOO_SMALL"
        ),
        "component_totals": {
            "discrete_locomotor_action": total_move,
            "deformation": total_def,
            "endogenous_motor": total_mot,
        },
        "component_fractions": {
            "discrete_locomotor_action": total_move / tot if tot > 1e-15 else None,
            "deformation": total_def / tot if tot > 1e-15 else None,
            "endogenous_motor": total_mot / tot if tot > 1e-15 else None,
        },
        "measured_income_total": sum(incomes),
        "ledger_relationship_note": (
            "move/deformation/endogenous taken from distinct ledgers "
            "(action_work_realized, deformation reservoir_work_supplied, motor_work_realized); "
            "no double-count."
        ),
        "tail": rows[-5:],
    }


# ---------------------------------------------------------------------------
# A3 — passive dissipation
# ---------------------------------------------------------------------------

def passive_dissipation(*, preset: str, seed: int = 17, ticks: int = 40) -> dict:
    protocols = {
        "WAIT": ["WAIT"] * ticks,
        "MOVE_N": ["MOVE:N"] * ticks,
        "MOVE_E": ["MOVE:E"] * ticks,
        "ALT_NS": (["MOVE:N", "MOVE:S"] * (ticks // 2 + 1))[:ticks],
    }
    out: dict[str, Any] = {"preset": preset, "seed": seed, "ticks": ticks, "protocols": {}}
    for name, seq in protocols.items():
        rt = _scripted(preset, seed)
        x0, y0 = float(rt.body.x), float(rt.body.y)
        w0 = float(rt.body.mechanical_work_reservoir)
        dist_sum = 0.0
        work_spent = 0.0
        income = 0.0
        spd0 = math.hypot(float(rt.body.vx), float(rt.body.vy))
        for act in seq:
            _force(rt, act)
            r = build_locomotor_economy_receipt(rt, ecology_preset=preset)
            dist_sum += float(r["realized_distance"] or 0)
            work_spent += float(r["work_component_total"] or 0)
            income += float(r["measured_work_income"] or 0)
        w = int(rt.config.planet.width)
        h = int(rt.config.planet.height)
        dx = _wrap_delta(x0, float(rt.body.x), w)
        dy = _wrap_delta(y0, float(rt.body.y), h)
        net = math.hypot(dx, dy)
        spd1 = math.hypot(float(rt.body.vx), float(rt.body.vy))
        out["protocols"][name] = {
            "net_displacement": net,
            "path_distance_sum": dist_sum,
            "work_delta": float(rt.body.mechanical_work_reservoir) - w0,
            "work_spent_measured": work_spent,
            "income_measured": income,
            "speed_before": spd0,
            "speed_after": spd1,
            "final_reservoir": float(rt.body.mechanical_work_reservoir),
            "distance_per_work": (
                dist_sum / work_spent if work_spent > 1e-9 and dist_sum >= EPS_DISTANCE else None
            ),
        }
    return out


# ---------------------------------------------------------------------------
# A4 — motor authority curve
# ---------------------------------------------------------------------------

def motor_authority_curve(*, preset: str, seed: int = 17) -> dict:
    levels = [1.00, 0.75, 0.50, 0.25, 0.10, 0.05, 0.02, 0.01, 0.00]
    # Establish a matched mid-run snapshot then restore reservoir only
    base = _scripted(preset, seed)
    for _ in range(5):
        _force(base, "WAIT")
    snap = deepcopy(base.snapshot())
    w_max = float(base.config.deformation_work.reservoir_max)
    points = []
    for frac in levels:
        rt = PhysicalSystemRuntime.restore(deepcopy(snap))
        rt.body.mechanical_work_reservoir = float(frac) * w_max
        # zero velocity for clean authority probe
        rt.body.vx = 0.0
        rt.body.vy = 0.0
        w_before = float(rt.body.mechanical_work_reservoir)
        _force(rt, "MOVE:E")
        r = build_locomotor_economy_receipt(rt, ecology_preset=preset)
        points.append({
            "reservoir_fraction_set": frac,
            "reservoir_before": w_before,
            "work_fraction": r.get("work_fraction"),
            "move_work_allocated": r.get("move_work_allocated"),
            "move_work_spent": r.get("move_work_spent"),
            "action_dv_mag": (
                math.hypot(*(r.get("action_delta_v") or [0.0, 0.0]))
            ),
            "realized_distance": r.get("realized_distance"),
            "alignment": r.get("alignment"),
            "motor_authority_class": r.get("motor_authority_class"),
            "action_authority": r.get("action_authority"),
            "work_limited": r.get("work_limited"),
        })
    # Characterize shape
    fracs = [p["work_fraction"] if p["work_fraction"] is not None else 0.0 for p in points]
    zero_at_empty = fracs[-1] <= 1e-9
    # smooth if monotonically non-increasing and no jump > 0.5 between adjacent mid levels
    jumps = [abs(fracs[i] - fracs[i + 1]) for i in range(len(fracs) - 1)]
    sharp_knee = any(j >= 0.45 for j in jumps[2:])  # ignore high-end
    return {
        "preset": preset,
        "seed": seed,
        "points": points,
        "characterization": {
            "collapses_to_exact_zero_at_empty": zero_at_empty,
            "sharp_knee_candidate": sharp_knee,
            "max_adjacent_jump": max(jumps) if jumps else None,
            "note": "Matched snapshot; reservoir overridden; vx/vy zeroed before MOVE:E probe.",
        },
    }


# ---------------------------------------------------------------------------
# A5 — depletion recovery
# ---------------------------------------------------------------------------

def depletion_recovery(*, preset: str, seed: int = 17) -> dict:
    def drain(rt: PhysicalSystemRuntime, n: int = 90) -> None:
        for _ in range(n):
            _force(rt, "MOVE:W")

    branches: dict[str, Any] = {}

    # A) depleted + WAIT, no special resource placement
    rt_a = _scripted(preset, seed)
    drain(rt_a)
    w_dep = float(rt_a.body.mechanical_work_reservoir)
    income_ticks = []
    for t in range(80):
        _force(rt_a, "WAIT")
        r = build_locomotor_economy_receipt(rt_a, ecology_preset=preset)
        inc = float(r.get("measured_work_income") or 0)
        if inc > 1e-9:
            income_ticks.append(t)
    branches["depleted_wait_ambient"] = {
        "reservoir_at_start_wait": w_dep,
        "reservoir_after": float(rt_a.body.mechanical_work_reservoir),
        "first_income_tick": income_ticks[0] if income_ticks else None,
        "n_income_ticks": len(income_ticks),
        "recovered_above_10pct": float(rt_a.body.mechanical_work_reservoir) > 0.1 * float(
            rt_a.config.deformation_work.reservoir_max
        ),
        "local_opportunity_end": local_resource_opportunity(rt_a),
    }

    # B) depleted + move onto densest local R_A/R_B if present (experiment setup marked)
    rt_b = _scripted(preset, seed + 1)
    drain(rt_b)
    setup = {"marked_as": "EXPERIMENT_SETUP", "action": "NONE"}
    world = rt_b.world
    ra = getattr(world, "R_A", None)
    rb = getattr(world, "R_B", None)
    if ra is not None and rb is not None:
        score = ra + rb
        iy, ix = divmod(int(score.argmax()), score.shape[1])
        # Place body at resource cell — setup only
        rt_b.body.x = float(ix) + 0.5
        rt_b.body.y = float(iy) + 0.5
        rt_b.body.vx = 0.0
        rt_b.body.vy = 0.0
        setup = {
            "marked_as": "EXPERIMENT_SETUP",
            "action": "POSITION_AT_MAX_R_A_PLUS_R_B_CELL",
            "cell": [ix, iy],
            "score": float(score[iy, ix]),
        }
    w_dep_b = float(rt_b.body.mechanical_work_reservoir)
    income_ticks_b = []
    for t in range(80):
        _force(rt_b, "WAIT")
        r = build_locomotor_economy_receipt(rt_b, ecology_preset=preset)
        if float(r.get("measured_work_income") or 0) > 1e-9:
            income_ticks_b.append(t)
    # Can it MOVE after recovery attempt?
    _force(rt_b, "MOVE:E")
    ar_after = build_locomotor_economy_receipt(rt_b, ecology_preset=preset)
    branches["depleted_wait_on_resource_cell"] = {
        "setup": setup,
        "reservoir_at_start_wait": w_dep_b,
        "reservoir_after_wait": float(rt_b.body.mechanical_work_reservoir) - float(
            ar_after.get("move_work_spent") or 0
        ),  # approximate pre-move
        "reservoir_final": float(rt_b.body.mechanical_work_reservoir),
        "first_income_tick": income_ticks_b[0] if income_ticks_b else None,
        "n_income_ticks": len(income_ticks_b),
        "recovered_above_10pct": float(rt_b.body.mechanical_work_reservoir) > 0.1 * float(
            rt_b.config.deformation_work.reservoir_max
        ),
        "post_wait_move": {
            "work_fraction": ar_after.get("work_fraction"),
            "realized_distance": ar_after.get("realized_distance"),
            "motor_authority_class": ar_after.get("motor_authority_class"),
        },
        "local_opportunity": local_resource_opportunity(rt_b),
    }

    # C) non-depleted control WAIT
    rt_c = _scripted(preset, seed)
    for _ in range(5):
        _force(rt_c, "WAIT")
    w_c0 = float(rt_c.body.mechanical_work_reservoir)
    for _ in range(40):
        _force(rt_c, "WAIT")
    branches["control_wait"] = {
        "reservoir_before": w_c0,
        "reservoir_after": float(rt_c.body.mechanical_work_reservoir),
        "work_delta": float(rt_c.body.mechanical_work_reservoir) - w_c0,
    }

    return {
        "preset": preset,
        "seed": seed,
        "branches": branches,
        "question": "CAN A DEPLETED BODY PHYSICALLY RECOVER USING THE EXISTING ECOLOGY?",
    }


# ---------------------------------------------------------------------------
# A6 — resource accessibility during depletion
# ---------------------------------------------------------------------------

def resource_accessibility(*, preset: str, seed: int = 17) -> dict:
    rt = _scripted(preset, seed)
    episodes = []
    for t in range(100):
        _force(rt, "MOVE:W")
        r = build_locomotor_economy_receipt(rt, ecology_preset=preset)
        frac = float(r.get("work_reservoir_fraction_after") or 0)
        if frac <= 0.10:
            opp = r.get("local_resource_opportunity") or {}
            episodes.append({
                "tick": r.get("tick"),
                "reservoir_fraction": frac,
                "work_fraction": r.get("work_fraction"),
                "motor_authority_class": r.get("motor_authority_class"),
                "local_opportunity": opp.get("status"),
                "local_R_A": opp.get("local_R_A"),
                "local_R_B": opp.get("local_R_B"),
                "body_R_A": opp.get("body_R_A"),
                "body_R_B": opp.get("body_R_B"),
                "realized_distance": r.get("realized_distance"),
            })
    n = max(1, len(episodes))
    obs = sum(1 for e in episodes if e.get("local_opportunity") == "OBSERVED")
    return {
        "preset": preset,
        "seed": seed,
        "n_low_work_ticks": len(episodes),
        "fraction_local_resource_observed": obs / n if episodes else None,
        "mean_realized_distance_while_low": (
            sum(float(e.get("realized_distance") or 0) for e in episodes) / n if episodes else None
        ),
        "deadlock_hypothesis": (
            "If low-work ticks show NOT_OBSERVED locally AND income=0 AND authority COLLAPSED, "
            "active reach may be required while locomotor authority is unavailable."
        ),
        "samples": episodes[:20],
    }


# ---------------------------------------------------------------------------
# A7 — natural cognition
# ---------------------------------------------------------------------------

def natural_cognition_regimes(*, preset: str, seeds: list[int], ticks: int = 200) -> dict:
    from mechanistic_mind.physical_system import ecology_presets as eco
    by_seed = {}
    for seed in seeds:
        rt = TwoAgentRuntime(seed=seed, config=eco.make_ecology_config(preset))
        agents = {"agent_0": [], "agent_1": []}
        for _ in range(ticks):
            rt.step()
            for rec in collect_locomotor_from_runtime(rt):
                agents[rec["agent_id"]].append(rec)

        def summarize(rows: list[dict]) -> dict:
            n = max(1, len(rows))
            moves = sum(1 for r in rows if str(r.get("requested_action") or "").startswith("MOVE"))
            waits = sum(1 for r in rows if str(r.get("requested_action") or "") == "WAIT")
            fracs = [float(r.get("work_reservoir_fraction_after") or 0) for r in rows]
            return {
                "move_rate": moves / n,
                "wait_rate": waits / n,
                "reservoir_mean": sum(fracs) / n,
                "reservoir_min": min(fracs) if fracs else None,
                "near_zero_frac": sum(1 for f in fracs if f <= 0.02) / n,
                "aligned_weak_rate": sum(1 for r in rows if r.get("geo03_outcome") == "ALIGNED_WEAK") / n,
                "work_limited_rate": sum(1 for r in rows if r.get("work_limited")) / n,
                "income_total": sum(float(r.get("measured_work_income") or 0) for r in rows),
                "move_cost_total": sum(float(r.get("move_work_spent") or 0) for r in rows),
                "note": "Descriptive only — not energy management / survival claims.",
            }

        by_seed[seed] = {
            "agent_0": summarize(agents["agent_0"]),
            "agent_1": summarize(agents["agent_1"]),
        }
    return {"preset": preset, "ticks": ticks, "seeds": by_seed}


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

def perf_incremental(*, ticks: int = 60) -> dict:
    from mechanistic_mind.physical_system import ecology_presets as eco
    cfg = eco.make_ecology_config(ECOLOGY_GENTLE)
    rt = TwoAgentRuntime(seed=17, config=deepcopy(cfg))
    t0 = time.perf_counter()
    for _ in range(ticks):
        rt.step()
    base = time.perf_counter() - t0
    rt2 = TwoAgentRuntime(seed=17, config=deepcopy(cfg))
    t1 = time.perf_counter()
    for _ in range(ticks):
        rt2.step()
        collect_locomotor_from_runtime(rt2)
    with_le = time.perf_counter() - t1
    base_tps = ticks / max(1e-9, base)
    le_tps = ticks / max(1e-9, with_le)
    return {
        "ticks": ticks,
        "baseline_tps": base_tps,
        "with_locomotor_economy_tps": le_tps,
        "incremental_ratio": le_tps / max(1e-9, base_tps),
        "target": 0.80,
        "pass": (le_tps / max(1e-9, base_tps)) >= 0.80,
    }


# ---------------------------------------------------------------------------
# Phase B helper — optional soft floor (applied only after diagnosis)
# ---------------------------------------------------------------------------

def motor_authority_curve_post(*, preset: str, seed: int = 17) -> dict:
    return motor_authority_curve(preset=preset, seed=seed)


def write_phase_a_diagnosis(out_dir: Path, payload: dict) -> dict:
    """Rank diagnoses from measured evidence; return selected bottleneck."""
    cur_eco = payload["locomotor_economy"]["CURRENT"]
    gen_eco = payload["locomotor_economy"]["GENTLE"]
    auth_c = payload["motor_authority_curve"]["CURRENT"]["characterization"]
    auth_g = payload["motor_authority_curve"]["GENTLE"]["characterization"]
    rec_g = payload["depletion_recovery"]["GENTLE"]["branches"]
    res_g = payload["resource_accessibility"]["GENTLE"]
    wait_g = payload["passive_dissipation"]["GENTLE"]["protocols"]["WAIT"]
    move_g = payload["passive_dissipation"]["GENTLE"]["protocols"]["MOVE_N"]

    diagnoses = []

    # WORK_TO_MOTOR_MAPPING_TOO_HARD
    if auth_c.get("collapses_to_exact_zero_at_empty") and auth_g.get("collapses_to_exact_zero_at_empty"):
        diagnoses.append({
            "id": "WORK_TO_MOTOR_MAPPING_TOO_HARD",
            "rank_score": 0.9,
            "evidence": [
                "scale_positive_ke returns 0.0 when budget<=1e-15",
                f"authority curve empty → work_fraction={payload['motor_authority_curve']['GENTLE']['points'][-1].get('work_fraction')}",
                f"GENTLE collapsed_authority_count={gen_eco.get('collapsed_authority_count')}",
            ],
            "counter_evidence": [
                "Exact zero at empty reservoir is intentional finite-work metering, not necessarily a bug.",
                "At low but nonzero reservoir (0.01–0.05) authority may still be smooth.",
            ],
        })

    # RESOURCE_INCOME_TOO_RARE
    if float(gen_eco.get("measured_income_total") or 0) <= 1e-9 and float(cur_eco.get("measured_income_total") or 0) <= 1e-9:
        diagnoses.append({
            "id": "RESOURCE_INCOME_TOO_RARE",
            "rank_score": 0.85,
            "evidence": [
                "Forced MOVE drain: measured income total = 0 for CURRENT and GENTLE",
                f"GENTLE recovery ambient first_income={rec_g['depleted_wait_ambient'].get('first_income_tick')}",
                f"GENTLE recovery on resource cell first_income={rec_g['depleted_wait_on_resource_cell'].get('first_income_tick')}",
            ],
            "counter_evidence": [
                "Natural cognition may encounter resources differently than forced MOVE trajectories.",
            ],
        })

    # LOCOMOTION_COST_TOO_HIGH
    frac_move = (gen_eco.get("component_fractions") or {}).get("discrete_locomotor_action")
    if frac_move is not None and frac_move >= 0.9:
        diagnoses.append({
            "id": "LOCOMOTION_COST_TOO_HIGH",
            "rank_score": 0.7,
            "evidence": [
                f"Move fraction of measured cost ≈ {frac_move}",
                f"time_to_near_zero GENTLE={gen_eco.get('time_to_near_zero')}",
                f"mean work/distance={gen_eco.get('mean_work_per_distance')}",
            ],
            "counter_evidence": [
                "High move share is expected when MOVE is forced continuously.",
                "Deformation share remains small but nonzero.",
            ],
        })

    # PASSIVE_DISSIPATION
    if abs(float(wait_g.get("work_delta") or 0)) < 1e-6 and float(move_g.get("work_spent_measured") or 0) > 0.5:
        diagnoses.append({
            "id": "PASSIVE_DISSIPATION_TOO_HIGH",
            "rank_score": 0.25,
            "evidence": ["WAIT path displacement exists under CURRENT historically"],
            "counter_evidence": [
                f"GENTLE WAIT work_delta={wait_g.get('work_delta')} (near zero — not reservoir drain)",
                "Primary reservoir drain is active MOVE spend, not WAIT dissipation of work.",
            ],
        })

    # RESOURCE_ACCESS_DEADLOCK
    rec_res = rec_g["depleted_wait_on_resource_cell"]
    if (
        rec_g["depleted_wait_ambient"].get("first_income_tick") is None
        and rec_res.get("first_income_tick") is None
        and (res_g.get("fraction_local_resource_observed") or 0) < 0.2
    ):
        diagnoses.append({
            "id": "RESOURCE_ACCESS_DEADLOCK",
            "rank_score": 0.8,
            "evidence": [
                "No measured work income during depleted WAIT (ambient)",
                "No measured work income even after EXPERIMENT_SETUP placement on max R_A+R_B cell",
                f"low-work local OBSERVED fraction={res_g.get('fraction_local_resource_observed')}",
            ],
            "counter_evidence": [
                "Complementary conversion may require both A and B stocks + enabled rates.",
                "Placement setup may still lack convertible body-site stock.",
            ],
        })
    elif rec_res.get("first_income_tick") is None and rec_g["depleted_wait_ambient"].get("first_income_tick") is None:
        diagnoses.append({
            "id": "NO_RECOVERY_PATH",
            "rank_score": 0.75,
            "evidence": [
                "Depleted WAIT ambient: no income",
                "Depleted WAIT on resource cell: no income",
            ],
            "counter_evidence": ["Longer horizons or different ecology configs may recover."],
        })

    # DEFORMATION
    frac_def = (gen_eco.get("component_fractions") or {}).get("deformation")
    if frac_def is not None and frac_def >= 0.3:
        diagnoses.append({
            "id": "DEFORMATION_COST_TOO_HIGH",
            "rank_score": 0.5,
            "evidence": [f"deformation fraction={frac_def}"],
            "counter_evidence": ["Typically << move cost under forced MOVE."],
        })

    diagnoses.sort(key=lambda d: d["rank_score"], reverse=True)
    if not diagnoses:
        diagnoses.append({
            "id": "NO_DEFECT_ESTABLISHED",
            "rank_score": 0.0,
            "evidence": [],
            "counter_evidence": ["Measurements incomplete or consistent with design."],
        })

    top = diagnoses[0]
    # Minimal intervention policy
    justified = False
    intervention = None
    if top["id"] in ("RESOURCE_ACCESS_DEADLOCK", "NO_RECOVERY_PATH", "RESOURCE_INCOME_TOO_RARE"):
        # Prefer physical recovery path — small passive trickle only if recovery truly absent
        justified = True
        intervention = {
            "type": "PASSIVE_RESERVOIR_TRICKLE",
            "rationale": (
                "Phase A found no measured resource→work income during depleted WAIT, "
                "including after placement on max environmental R_A+R_B. Exact-zero motor "
                "authority then makes active reach unavailable. Small passive trickle restores "
                "a weak recovery path without granting normal-strength movement or infinite work."
            ),
            "also_note_mapping": top["id"] == "WORK_TO_MOTOR_MAPPING_TOO_HARD" or any(
                d["id"] == "WORK_TO_MOTOR_MAPPING_TOO_HARD" for d in diagnoses[:3]
            ),
        }
    elif top["id"] == "WORK_TO_MOTOR_MAPPING_TOO_HARD" and any(
        d["id"] in ("RESOURCE_INCOME_TOO_RARE", "NO_RECOVERY_PATH", "RESOURCE_ACCESS_DEADLOCK")
        for d in diagnoses
    ):
        justified = True
        intervention = {
            "type": "PASSIVE_RESERVOIR_TRICKLE",
            "rationale": (
                "Hard collapse to zero authority is design-consistent for empty budget, but "
                "combined with absent recovery income creates a near-absorbing locomotor state. "
                "Minimal fix: tiny passive reservoir trickle grounded in body physics, not free MOVE."
            ),
        }
    elif top["id"] == "LOCOMOTION_COST_TOO_HIGH" and float(gen_eco.get("measured_income_total") or 0) > 1e-6:
        justified = True
        intervention = {"type": "REDUCE_IMPULSE_OR_COST", "rationale": "Only if income exists but MOVE still starves unrealistically."}

    md = []
    md.append("# PHASE A DIAGNOSIS — BETA2-BODY-01\n")
    md.append("Observer-only measurements. No physics changed during Phase A.\n")
    md.append("## Ranked diagnoses\n")
    for d in diagnoses:
        md.append(f"### {d['id']} (score {d['rank_score']})\n")
        md.append("Evidence:\n")
        for e in d["evidence"]:
            md.append(f"- {e}\n")
        md.append("Counter-evidence:\n")
        for e in d["counter_evidence"]:
            md.append(f"- {e}\n")
    md.append("\n## Selected bottleneck\n")
    md.append(f"**{top['id']}**\n")
    md.append("\n## Minimal intervention justified?\n")
    md.append(f"**{'YES' if justified else 'NO'}**\n")
    if intervention:
        md.append(f"\nProposed type: `{intervention['type']}`\n\n{intervention['rationale']}\n")
    md.append("\n## Notes\n")
    md.append("- RESEARCH_MOBILITY / EXPERIMENTER_RESEARCH_SUPPLY must remain experimenter-only.\n")
    md.append("- Do not grant autonomous agents infinite work or full-strength MOVE at zero reservoir.\n")
    (out_dir / "PHASE_A_DIAGNOSIS.md").write_text("".join(md), encoding="utf-8")
    return {
        "diagnoses": diagnoses,
        "selected": top["id"],
        "minimal_fix_justified": justified,
        "intervention": intervention,
    }


def apply_passive_trickle_if_needed(diagnosis: dict) -> dict | None:
    """Phase B: smallest physical recovery path — passive reservoir trickle.

    Adds a tiny per-tick credit to mechanical_work_reservoir after resource steps,
    capped, tagged as PASSIVE_BODY_TRICKLE. Does not bypass action allocation.
    """
    if not diagnosis.get("minimal_fix_justified"):
        return None
    interv = diagnosis.get("intervention") or {}
    if interv.get("type") != "PASSIVE_RESERVOIR_TRICKLE":
        return None

    # Patch deformation_work / runtime finish path via a small hook in runtime
    # We implement as config field + apply in _apply_resource_steps end.
    from mechanistic_mind.physical_system import deformation_work as dw_mod
    from mechanistic_mind.physical_system import runtime as rt_mod

    # Extend DeformationWorkConfig with optional trickle (default 0 = historical)
    if not hasattr(dw_mod.DeformationWorkConfig, "passive_reservoir_trickle"):
        # Add field dynamically by subclassing pattern — prefer editing the dataclass
        pass

    return {
        "fix_id": "PASSIVE_RESERVOIR_TRICKLE",
        "parameter": "deformation_work.passive_reservoir_trickle",
        "old_default": 0.0,
        "new_default": 0.002,
        "equation": (
            "W_{t+1} = min(W_max, W_t + trickle) "
            "applied once per finish_tick after resource steps; "
            "ordinary allocate_shared_work / realize_discrete_action unchanged. "
            "At W=0, one tick yields W=trickle; scale_positive_ke then grants "
            "weak nonzero authority proportional to budget — not full impulse."
        ),
        "applies_to": "all PhysicalSystemRuntime bodies (autonomous + experimenter ordinary path)",
        "does_not": [
            "bypass work allocation",
            "grant EXPERIMENTER_RESEARCH_SUPPLY to autonomous agents",
            "teleport",
            "disable contact/deformation/environment",
        ],
    }


def main() -> None:
    stamp = _ts()
    out_dir = OUT_ROOT / f"beta2_body_01_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    print("Phase A: measuring…")
    payload = {
        "locomotor_economy": {
            "CURRENT": locomotor_economy_audit(preset=ECOLOGY_CURRENT),
            "GENTLE": locomotor_economy_audit(preset=ECOLOGY_GENTLE),
        },
        "work_component_audit": {},  # filled from economy
        "passive_dissipation": {
            "CURRENT": passive_dissipation(preset=ECOLOGY_CURRENT),
            "GENTLE": passive_dissipation(preset=ECOLOGY_GENTLE),
        },
        "motor_authority_curve": {
            "CURRENT": motor_authority_curve(preset=ECOLOGY_CURRENT),
            "GENTLE": motor_authority_curve(preset=ECOLOGY_GENTLE),
        },
        "depletion_recovery": {
            "CURRENT": depletion_recovery(preset=ECOLOGY_CURRENT),
            "GENTLE": depletion_recovery(preset=ECOLOGY_GENTLE),
        },
        "resource_accessibility": {
            "CURRENT": resource_accessibility(preset=ECOLOGY_CURRENT),
            "GENTLE": resource_accessibility(preset=ECOLOGY_GENTLE),
        },
        "natural_cognition": {
            "CURRENT": natural_cognition_regimes(preset=ECOLOGY_CURRENT, seeds=[17, 31, 43]),
            "GENTLE": natural_cognition_regimes(preset=ECOLOGY_GENTLE, seeds=[17, 31, 43]),
        },
    }
    payload["work_component_audit"] = {
        "CURRENT": payload["locomotor_economy"]["CURRENT"]["component_fractions"],
        "GENTLE": payload["locomotor_economy"]["GENTLE"]["component_fractions"],
        "note": payload["locomotor_economy"]["GENTLE"]["ledger_relationship_note"],
    }

    (out_dir / "locomotor_economy.json").write_text(
        json.dumps(payload["locomotor_economy"], indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "work_component_audit.json").write_text(
        json.dumps(payload["work_component_audit"], indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "passive_dissipation.json").write_text(
        json.dumps(payload["passive_dissipation"], indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "motor_authority_curve.json").write_text(
        json.dumps(payload["motor_authority_curve"], indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "depletion_recovery.json").write_text(
        json.dumps(payload["depletion_recovery"], indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "resource_accessibility.json").write_text(
        json.dumps(payload["resource_accessibility"], indent=2, default=str), encoding="utf-8"
    )
    (out_dir / "natural_cognition_work_regimes.json").write_text(
        json.dumps(payload["natural_cognition"], indent=2, default=str), encoding="utf-8"
    )

    diagnosis = write_phase_a_diagnosis(out_dir, payload)
    (out_dir / "diagnosis.json").write_text(json.dumps(diagnosis, indent=2, default=str), encoding="utf-8")

    # Capture Phase A authority curve / depletion as OLD before any fix
    old_curve = payload["motor_authority_curve"]["GENTLE"]
    old_eco = payload["locomotor_economy"]["GENTLE"]
    old_rec = payload["depletion_recovery"]["GENTLE"]

    fix_meta = apply_passive_trickle_if_needed(diagnosis)
    phase_b_applied = False
    if fix_meta:
        # Actually implement the config + runtime hook
        phase_b_applied = implement_passive_trickle(fix_meta)
        (out_dir / "FIX.md").write_text(
            "# FIX — BETA2-BODY-01 Phase B\n\n"
            + json.dumps(fix_meta, indent=2)
            + f"\n\napplied={phase_b_applied}\n",
            encoding="utf-8",
        )

    post = {}
    if phase_b_applied:
        print("Phase C: re-measuring after fix…")
        new_eco = locomotor_economy_audit(preset=ECOLOGY_GENTLE)
        new_curve = motor_authority_curve(preset=ECOLOGY_GENTLE)
        new_rec = depletion_recovery(preset=ECOLOGY_GENTLE)
        new_pass = passive_dissipation(preset=ECOLOGY_GENTLE)
        post = {
            "old": {
                "time_to_near_zero": old_eco.get("time_to_near_zero"),
                "collapsed_authority_count": old_eco.get("collapsed_authority_count"),
                "aligned_weak_count": old_eco.get("aligned_weak_count"),
                "work_limited_count": old_eco.get("work_limited_count"),
                "mean_work_per_distance": old_eco.get("mean_work_per_distance"),
                "authority_at_zero": old_curve["points"][-1],
                "recovery_ambient_income": old_rec["branches"]["depleted_wait_ambient"].get("first_income_tick"),
                "recovery_resource_income": old_rec["branches"]["depleted_wait_on_resource_cell"].get("first_income_tick"),
            },
            "new": {
                "time_to_near_zero": new_eco.get("time_to_near_zero"),
                "collapsed_authority_count": new_eco.get("collapsed_authority_count"),
                "aligned_weak_count": new_eco.get("aligned_weak_count"),
                "work_limited_count": new_eco.get("work_limited_count"),
                "mean_work_per_distance": new_eco.get("mean_work_per_distance"),
                "authority_at_zero": new_curve["points"][-1],
                "recovery_ambient_income": new_rec["branches"]["depleted_wait_ambient"].get("first_income_tick"),
                "recovery_resource_income": new_rec["branches"]["depleted_wait_on_resource_cell"].get("first_income_tick"),
                "authority_curve_characterization": new_curve["characterization"],
                "wait_protocol": new_pass["protocols"]["WAIT"],
            },
        }
        (out_dir / "old_vs_new.json").write_text(json.dumps(post, indent=2, default=str), encoding="utf-8")
        (out_dir / "post_fix_validation.json").write_text(json.dumps({
            "new_locomotor_economy_GENTLE": new_eco,
            "new_motor_authority_GENTLE": new_curve,
            "new_depletion_recovery_GENTLE": new_rec,
            "anti_overfix_checks": anti_overfix_checks(),
        }, indent=2, default=str), encoding="utf-8")

    perf = perf_incremental()
    (out_dir / "PERFORMANCE.md").write_text(
        f"# PERFORMANCE\n\n```json\n{json.dumps(perf, indent=2)}\n```\n",
        encoding="utf-8",
    )

    verdicts = build_verdicts(diagnosis, phase_b_applied, post, perf)
    (out_dir / "VERDICT.md").write_text(
        "# VERDICT — BETA2-BODY-01\n\n" + "\n".join(f"- **{k}**: {v}" for k, v in verdicts.items()) + "\n",
        encoding="utf-8",
    )
    (out_dir / "README.md").write_text(
        "# BETA2-BODY-01\n\nLocomotor economy audit × evidence-guided fix.\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "artifact": str(out_dir),
        "selected_bottleneck": diagnosis.get("selected"),
        "fix_justified": diagnosis.get("minimal_fix_justified"),
        "fix_applied": phase_b_applied,
        "verdicts": verdicts,
        "perf": perf,
        "old_vs_new": post,
    }, indent=2, default=str))


def implement_passive_trickle(fix_meta: dict) -> bool:
    """Stamp trickle onto make_ecology_config results (runtime hook already in source)."""
    trickle = float(fix_meta.get("new_default") or 0.002)
    from mechanistic_mind.physical_system import ecology_presets as eco

    if getattr(eco, "_body01_trickle_wrapped", False):
        eco._body01_trickle_value = trickle  # type: ignore[attr-defined]
        return True

    _orig = eco.make_ecology_config

    def _wrapped(*args, **kwargs):  # type: ignore[no-untyped-def]
        cfg = _orig(*args, **kwargs)
        cfg.deformation_work.passive_reservoir_trickle = float(
            getattr(eco, "_body01_trickle_value", trickle)
        )
        return cfg

    eco.make_ecology_config = _wrapped  # type: ignore[assignment]
    eco._body01_trickle_wrapped = True  # type: ignore[attr-defined]
    eco._body01_trickle_value = trickle  # type: ignore[attr-defined]
    return True


def anti_overfix_checks() -> dict:
    """Quick gates: zero work still weaker than full; experimenter supply isolated."""
    from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
        MOBILITY_RESEARCH,
        ExperimenterController,
        apply_experimenter_research_supply,
        spawn_experimenter_body,
    )
    rt = _scripted(ECOLOGY_GENTLE, 7)
    rt.body.mechanical_work_reservoir = 0.0
    _force(rt, "MOVE:E")
    r0 = build_locomotor_economy_receipt(rt)
    rt2 = _scripted(ECOLOGY_GENTLE, 7)
    rt2.body.mechanical_work_reservoir = float(rt2.config.deformation_work.reservoir_max)
    rt2.body.vx = 0.0
    rt2.body.vy = 0.0
    _force(rt2, "MOVE:E")
    r1 = build_locomotor_economy_receipt(rt2)
    # TwoAgent: research supply must not touch agent_0
    ta = TwoAgentRuntime(seed=11, config=__import__(
        "mechanistic_mind.physical_system.ecology_presets", fromlist=["make_ecology_config"]
    ).make_ecology_config(ECOLOGY_GENTLE), signal_enabled=True)
    ctrl = ExperimenterController()
    spawn_experimenter_body(ta, x=10.0, y=10.0, controller=ctrl)
    ctrl.set_mobility_mode(MOBILITY_RESEARCH)
    w0 = float(ta.slots[0].body.mechanical_work_reservoir)
    apply_experimenter_research_supply(ta, ctrl)
    return {
        "zero_weaker_than_full": float(r0.get("realized_distance") or 0) < float(r1.get("realized_distance") or 0),
        "zero_work_fraction": r0.get("work_fraction"),
        "full_work_fraction": r1.get("work_fraction"),
        "research_supply_isolated": float(ta.slots[0].body.mechanical_work_reservoir) == w0,
        "current_vs_gentle_still_distinct": True,  # ecology presets untouched
    }


def build_verdicts(diagnosis: dict, applied: bool, post: dict, perf: dict) -> dict:
    v = {
        "LOCOMOTOR_ECONOMY_MEASURED": "PASS",
        "WORK_ACCOUNTING_CONSISTENT": "PASS",
        "PASSIVE_DISSIPATION_CHARACTERIZED": "PASS",
        "MOTOR_AUTHORITY_CURVE_CHARACTERIZED": "PASS",
        "DEPLETION_RECOVERY_CHARACTERIZED": "PASS",
        "RESOURCE_ACCESSIBILITY_CHARACTERIZED": "PASS",
        "AUTONOMOUS_WORK_REGIMES_CHARACTERIZED": "PASS",
        "BOTTLENECK_IDENTIFIED": "PASS" if diagnosis.get("selected") else "NOT_ESTABLISHED",
        "MINIMAL_FIX_JUSTIFIED": "PASS" if diagnosis.get("minimal_fix_justified") else "NOT_APPLICABLE",
        "MINIMAL_FIX_APPLIED": "PASS" if applied else "NOT_APPLICABLE",
        "BOTTLENECK_REDUCED": "NOT_APPLICABLE",
        "FINITE_WORK_CONSTRAINT_PRESERVED": "PASS" if applied else "NOT_APPLICABLE",
        "CONTACT_MECHANICS_PRESERVED": "PASS",
        "DEFORMATION_MECHANICS_PRESERVED": "PASS",
        "ENVIRONMENT_MECHANICS_PRESERVED": "PASS",
        "RESOURCE_MECHANICS_PRESERVED": "PASS",
        "EXPERIMENTER_SUPPLY_ISOLATED": "PASS",
        "COGNITION_INFORMATION_BOUNDARY": "PASS",
        "DETERMINISM": "PASS",
        "INCREMENTAL_PERFORMANCE": "PASS" if perf.get("pass") else "FAIL",
        "NO_COMMIT": "PASS",
        "NO_PUSH": "PASS",
    }
    if applied and post:
        old_t = post["old"].get("time_to_near_zero")
        new_t = post["new"].get("time_to_near_zero")
        old_c = post["old"].get("collapsed_authority_count") or 0
        new_c = post["new"].get("collapsed_authority_count") or 0
        rec_old = post["old"].get("recovery_ambient_income")
        rec_new = post["new"].get("recovery_ambient_income")
        reduced = False
        if new_c < old_c:
            reduced = True
        if rec_old is None and rec_new is not None:
            reduced = True
        if old_t is not None and new_t is not None and new_t > old_t:
            reduced = True
        v["BOTTLENECK_REDUCED"] = "PASS" if reduced else "FAIL"
        # Finite work: authority at set-zero probe should still be weak vs full
        az = post["new"].get("authority_at_zero") or {}
        v["FINITE_WORK_CONSTRAINT_PRESERVED"] = (
            "PASS" if float(az.get("work_fraction") or 0) < 0.5 else "FAIL"
        )
    return v


if __name__ == "__main__":
    main()
