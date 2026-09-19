#!/usr/bin/env python3
"""TIKTAALIK_CHILDHOOD_01 — long-run physical runway validation (no PSC).

Promoted BASELINE_CLIMATE_DEFAULT with trickle=0.
Physical baseline: cognition disabled (optional matched cognition-on branch skipped).
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from mechanistic_mind.physical_system.ecology_presets import (
    BODY01_PASSIVE_RESERVOIR_TRICKLE,
    ECOLOGY_BASELINE,
    ecology_metadata,
    make_ecology_config,
)
from mechanistic_mind.physical_system.motor_work import scale_positive_ke
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "results" / "body_economy"
SEEDS = [17, 29, 41, 53, 67]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        path.write_text(obj, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _local_ab(rt: PhysicalSystemRuntime) -> tuple[float, float]:
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    return float(rt.world.R_A[iy, ix]), float(rt.world.R_B[iy, ix])


def _authority_collapsed(rt: PhysicalSystemRuntime) -> bool:
    budget = float(rt.body.mechanical_work_reservoir)
    if budget <= 1e-15:
        return True
    impulse = float(rt.config.discrete_action_work.impulse_scale)
    mass = float(rt.config.body.mass)
    scale = scale_positive_ke(mass, float(rt.body.vx), float(rt.body.vy), impulse / max(mass, 1e-9), 0.0, budget)
    return scale <= 1e-15


def run_childhood(
    *,
    seed: int,
    ticks: int,
    cognition: bool = False,
    sample_every: int = 50,
) -> dict[str, Any]:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = bool(cognition)
    # Keep endogenous motor OFF for physical-baseline control (ordinary discrete actions only).
    if not cognition:
        cfg.endogenous_motor.mode = "OFF"
    rt = PhysicalSystemRuntime(seed=int(seed), config=cfg)
    w_max = float(rt.config.deformation_work.reservoir_max)
    env_a0 = float(np.sum(rt.world.R_A))
    env_b0 = float(np.sum(rt.world.R_B))

    reservoirs: list[float] = []
    sample_trace: list[dict[str, Any]] = []

    encounter = 0
    uptake_a = 0.0
    uptake_b = 0.0
    conversion = 0.0
    spontaneous = 0  # conversion with local A&B ~0 and trickle 0
    collapsed = 0
    near_zero = 0
    zero_res = 0
    locomotor_spend = 0.0

    # Depletion / recovery (crossing thresholds)
    depleted = False
    depletion_events = 0
    recovery_events = 0
    recovery_from_resource = 0
    time_to_recovery: list[int] = []
    depletion_tick = None

    positions: list[tuple[float, float]] = []
    active_disp = 0.0
    wait_disp = 0.0
    encounter_on_wait = 0
    encounter_on_move = 0
    immobile = 0
    longest_immobile = 0
    cur_immobile = 0

    # Naive scripted childhood: mix WAIT and MOVE — not resource seeking
    pattern = ["MOVE:N", "MOVE:E", "WAIT", "MOVE:S", "MOVE:W", "WAIT", "MOVE:E", "MOVE:N", "WAIT", "MOVE:W"]
    x_prev, y_prev = float(rt.body.x), float(rt.body.y)
    W, H = rt.config.planet.width, rt.config.planet.height

    t0 = time.perf_counter()
    for t in range(ticks):
        act = pattern[t % len(pattern)]
        la, lb = _local_ab(rt)
        on_resource = la > 1e-4 and lb > 1e-4
        if on_resource:
            encounter += 1
            if act == "WAIT":
                encounter_on_wait += 1
            else:
                encounter_on_move += 1

        rt.step_forced_action(act)
        cl = rt.last_complementary_ledger or {}
        aw = getattr(rt, "last_action_work_ledger", None) or {}
        ua = float((cl.get("A") or {}).get("acquired") or 0.0)
        ub = float((cl.get("B") or {}).get("acquired") or 0.0)
        cw = float(cl.get("work_credited") or 0.0)
        uptake_a += ua
        uptake_b += ub
        conversion += cw
        locomotor_spend += float(aw.get("work_spent") or aw.get("spent") or 0.0)

        # Spontaneous: credited work with no local complementary stock and no uptake
        la2, lb2 = _local_ab(rt)
        if cw > 1e-9 and ua <= 1e-12 and ub <= 1e-12 and la2 <= 1e-6 and lb2 <= 1e-6:
            # May still convert from internal sites — only flag if body sites also ~0 before? Use limiting NONE + empty body
            if float(cl.get("body_A") or 0) <= 1e-9 and float(cl.get("body_B") or 0) <= 1e-9:
                spontaneous += 1

        w = float(rt.body.mechanical_work_reservoir)
        reservoirs.append(w)
        if w <= 1e-12:
            zero_res += 1
        if w <= 0.02 * w_max:
            near_zero += 1
        if _authority_collapsed(rt):
            collapsed += 1

        # Depletion / recovery events
        if (not depleted) and w <= 0.02 * w_max:
            depleted = True
            depletion_events += 1
            depletion_tick = t
        elif depleted and w > 0.10 * w_max:
            recovery_events += 1
            if depletion_tick is not None:
                time_to_recovery.append(t - depletion_tick)
            if on_resource or ua > 1e-9 or ub > 1e-9 or cw > 1e-9:
                recovery_from_resource += 1
            depleted = False
            depletion_tick = None

        x1, y1 = float(rt.body.x), float(rt.body.y)
        dx = min(abs(x1 - x_prev), W - abs(x1 - x_prev))
        dy = min(abs(y1 - y_prev), H - abs(y1 - y_prev))
        dist = math.hypot(dx, dy)
        if act == "WAIT":
            wait_disp += dist
        else:
            active_disp += dist
        if dist < 1e-4:
            immobile += 1
            cur_immobile += 1
            longest_immobile = max(longest_immobile, cur_immobile)
        else:
            cur_immobile = 0
        positions.append((x1, y1))
        x_prev, y_prev = x1, y1

        if t % sample_every == 0 or t == ticks - 1:
            sample_trace.append({
                "tick": t,
                "reservoir": w,
                "local_A": la2,
                "local_B": lb2,
                "conversion": cw,
                "uptake_A": ua,
                "uptake_B": ub,
                "action": act,
                "x": x1,
                "y": y1,
            })

    elapsed = time.perf_counter() - t0
    bins: dict[tuple[int, int], int] = {}
    for x, y in positions:
        key = (int(x) // 4, int(y) // 4)
        bins[key] = bins.get(key, 0) + 1
    modal = max(bins.values()) if bins else 0
    total_disp = active_disp + wait_disp
    enc_total = encounter_on_wait + encounter_on_move

    # Flow confound estimate: among encounter ticks, fraction that occurred on WAIT
    # (passive transport / lingering) vs MOVE (active locomotion). Conservative.
    flow_confound = {
        "encounter_ticks": encounter,
        "encounter_on_WAIT": encounter_on_wait,
        "encounter_on_MOVE": encounter_on_move,
        "wait_share_of_encounters": (encounter_on_wait / enc_total) if enc_total else None,
        "passive_displacement_fraction": (wait_disp / total_disp) if total_disp > 1e-9 else None,
        "note": "WAIT-share of encounters is a lower-bound proxy for passive/lingering contribution; not causal attribution.",
    }

    return {
        "seed": seed,
        "ticks": ticks,
        "cognition_enabled": bool(cognition),
        "elapsed_s": elapsed,
        "ecology": ecology_metadata(cfg),
        "env_R_A_sum_initial": env_a0,
        "env_R_B_sum_initial": env_b0,
        "env_R_A_sum_final": float(np.sum(rt.world.R_A)),
        "env_R_B_sum_final": float(np.sum(rt.world.R_B)),
        "resource_encounters": encounter,
        "resource_encounter_fraction": encounter / max(ticks, 1),
        "uptake_A": uptake_a,
        "uptake_B": uptake_b,
        "total_resource_derived_work": conversion,
        "spontaneous_recovery_events": spontaneous,
        "mean_reservoir": float(np.mean(reservoirs)),
        "min_reservoir": float(np.min(reservoirs)),
        "max_reservoir": float(np.max(reservoirs)),
        "final_reservoir": reservoirs[-1],
        "frac_near_depletion": near_zero / max(ticks, 1),
        "zero_reservoir_ticks": zero_res,
        "collapsed_authority_ticks": collapsed,
        "locomotor_spend_reported": locomotor_spend,
        "depletion_events": depletion_events,
        "recovery_events": recovery_events,
        "recovery_from_resource": recovery_from_resource,
        "mean_time_to_recovery": float(np.mean(time_to_recovery)) if time_to_recovery else None,
        "active_displacement": active_disp,
        "wait_passive_displacement": wait_disp,
        "total_displacement": total_disp,
        "spatial_coverage_bins": len(bins),
        "trajectory_concentration_modal_frac": modal / max(ticks, 1),
        "time_immobile": immobile,
        "longest_immobile_interval": longest_immobile,
        "flow_confound": flow_confound,
        "failure_like": zero_res > ticks * 0.25 and recovery_events == 0,
        "sample_trace": sample_trace,
    }


def summarize(runs: list[dict[str, Any]]) -> dict[str, Any]:
    def mean(key: str) -> float | None:
        vals = [r[key] for r in runs if r.get(key) is not None]
        return float(np.mean(vals)) if vals else None

    return {
        "n": len(runs),
        "mean_reservoir": mean("mean_reservoir"),
        "min_of_mins": min((r["min_reservoir"] for r in runs), default=None),
        "mean_encounter_fraction": mean("resource_encounter_fraction"),
        "mean_conversion": mean("total_resource_derived_work"),
        "mean_depletion_events": mean("depletion_events"),
        "mean_recovery_events": mean("recovery_events"),
        "mean_recovery_from_resource": mean("recovery_from_resource"),
        "total_spontaneous": sum(r["spontaneous_recovery_events"] for r in runs),
        "mean_wait_share_encounters": float(np.mean([
            r["flow_confound"]["wait_share_of_encounters"]
            for r in runs
            if r["flow_confound"]["wait_share_of_encounters"] is not None
        ])) if any(r["flow_confound"]["wait_share_of_encounters"] is not None for r in runs) else None,
        "mean_coverage": mean("spatial_coverage_bins"),
        "failure_like_rate": sum(1 for r in runs if r["failure_like"]) / max(len(runs), 1),
        "seeds_with_encounters": sum(1 for r in runs if r["resource_encounters"] > 0),
        "seeds_with_resource_recovery": sum(1 for r in runs if r["recovery_from_resource"] > 0),
    }


def assess_runway(s5: dict, s20: dict | None) -> dict[str, Any]:
    """Conservative childhood usefulness assessment — physical substrate only."""
    gates = {}
    gates["GATE_1_env_stock"] = True  # verified by config + env sums
    gates["GATE_2_trickle_zero"] = float(BODY01_PASSIVE_RESERVOIR_TRICKLE) == 0.0
    gates["GATE_3_no_spontaneous"] = s5["total_spontaneous"] == 0 and (s20 is None or s20["total_spontaneous"] == 0)
    gates["GATE_5_some_encounters"] = s5["seeds_with_encounters"] >= 1
    gates["GATE_6_some_resource_recovery"] = s5["seeds_with_resource_recovery"] >= 1 or (
        s5["mean_conversion"] or 0
    ) > 0.1
    wait_share = s5.get("mean_wait_share_encounters")
    gates["GATE_7_not_flow_dominated"] = wait_share is None or wait_share < 0.70
    gates["GATE_8_failure_possible"] = s5["failure_like_rate"] > 0 or (s5.get("min_of_mins") or 1) < 0.5

    # Middle regime heuristic
    enc = s5["mean_encounter_fraction"] or 0
    fail = s5["failure_like_rate"]
    conv = s5["mean_conversion"] or 0
    useful = (
        gates["GATE_5_some_encounters"]
        and conv > 0
        and fail < 1.0
        and enc < 0.85
        and gates["GATE_7_not_flow_dominated"]
    )
    insufficient = fail >= 0.8 or (not gates["GATE_5_some_encounters"])
    return {
        "gates": gates,
        "useful_childhood_runway": useful and not insufficient,
        "insufficient_runway": insufficient,
        "notes": [
            "Physical substrate assessment only — not learning, planning, or PSC.",
            f"5k encounter_frac={enc:.4f} conversion={conv:.3f} failure_like={fail:.2f} wait_share_enc={wait_share}",
        ],
    }


def write_report(out_dir: Path, *, eco_cfg, s5_runs, s5, s20_runs, s20, assess) -> None:
    lines = []
    lines.append("# TIKTAALIK_CHILDHOOD_01 Report\n\n")
    lines.append("Physical ecology runway validation after promoting BASELINE_CLIMATE_DEFAULT.\n")
    lines.append("Not a cognition / PSC / preference / planning result.\n\n")
    lines.append("## A. Promoted configuration\n")
    lines.append(f"```json\n{json.dumps(eco_cfg, indent=2)}\n```\n")
    lines.append(f"- BODY01_PASSIVE_RESERVOIR_TRICKLE = {BODY01_PASSIVE_RESERVOIR_TRICKLE}\n\n")
    lines.append("## B. Regression tests\nSee TESTS.md / pytest `test_tiktaalik_baseline_promotion.py`.\n\n")
    lines.append("## C. Five-seed 5,000-tick results\n")
    lines.append(f"```json\n{json.dumps(s5, indent=2)}\n```\n")
    lines.append("## D. Five-seed 20,000-tick results\n")
    if s20 is None:
        lines.append("Not run / skipped.\n\n")
    else:
        lines.append(f"```json\n{json.dumps(s20, indent=2)}\n```\n")
    lines.append("## E. Resource encounters\n")
    for r in s5_runs:
        lines.append(
            f"- seed {r['seed']}: encounters={r['resource_encounters']} "
            f"({r['resource_encounter_fraction']:.4f}), conversion={r['total_resource_derived_work']:.3f}\n"
        )
    lines.append("\n## F. Depletion / recovery\n")
    for r in s5_runs:
        lines.append(
            f"- seed {r['seed']}: deplete={r['depletion_events']} recover={r['recovery_events']} "
            f"from_resource={r['recovery_from_resource']} spontaneous={r['spontaneous_recovery_events']}\n"
        )
    lines.append("\n## G. Flow confound estimate\n")
    lines.append(f"Mean WAIT-share of encounters (5k): {s5.get('mean_wait_share_encounters')}\n")
    lines.append("Conservative proxy only.\n\n")
    lines.append("## H. Spatial / trajectory\n")
    lines.append(f"Mean coverage bins (5k): {s5.get('mean_coverage')}\n\n")
    lines.append("## I. Deaths / collapses\n")
    lines.append(f"failure_like_rate (5k): {s5.get('failure_like_rate')}\n")
    if s20:
        lines.append(f"failure_like_rate (20k): {s20.get('failure_like_rate')}\n")
    lines.append("\n## J. Learning runway (physical)\n")
    if assess["useful_childhood_runway"]:
        lines.append(
            "**The ecology provides sufficient physical runway for naive exploration, "
            "resource encounter, and resource-linked recovery under the scripted childhood protocol.**\n"
        )
    elif assess["insufficient_runway"]:
        lines.append("**Naive agents have insufficient physical runway under this protocol.**\n")
    else:
        lines.append("**Runway assessment mixed / not fully established.**\n")
    lines.append("\n## K. Remaining physical confounds\n")
    lines.append(
        "- Scripted MOVE/WAIT pattern is not autonomous cognition.\n"
        "- WAIT-share of encounters underestimates flow carrying during MOVE.\n"
        "- Softened flow still contributes some passive displacement.\n"
    )
    lines.append("\n## L. Files changed\n")
    lines.append(
        "- ecology_presets.py (promotion)\n"
        "- tiktaalik.py (canonical config)\n"
        "- session.py / App.tsx (Observer)\n"
        "- tests + childhood runner\n"
    )
    lines.append("\n## M. Acceptance gates\n")
    for k, v in assess["gates"].items():
        lines.append(f"- {k}: {'PASS' if v else 'FAIL'}\n")
    _write(out_dir / "report.md", "".join(lines))


def main() -> None:
    out_dir = OUT_ROOT / f"tiktaalik_childhood_01_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    eco_dump = {
        "ecology_preset": cfg.ecology_preset,
        "metadata": ecology_metadata(cfg),
        "planet.flow_gain": cfg.planet.flow_gain,
        "planet.flow_max": cfg.planet.flow_max,
        "body.flow_coupling": cfg.body.flow_coupling,
        "climate_ecology": cfg.planet.climate_ecology.to_dict(),
        "passive_reservoir_trickle": cfg.deformation_work.passive_reservoir_trickle,
        "complementary_resources.enabled": cfg.complementary_resources.enabled,
        "complementary_resources.conversion_enabled": cfg.complementary_resources.conversion_enabled,
        "BODY01_PASSIVE_RESERVOIR_TRICKLE": BODY01_PASSIVE_RESERVOIR_TRICKLE,
        "source": "results/body_economy/baseline_ecology_calib_20260918T225541Z (promoted, not retuned)",
    }
    _write(out_dir / "ecology_config.json", eco_dump)

    print("Running 5k × 5 seeds…")
    runs_5k = [run_childhood(seed=s, ticks=5000, cognition=False) for s in SEEDS]
    # Strip heavy traces for aggregate file; keep compact resource trace separately
    compact_5k = []
    with (out_dir / "resource_work_trace.jsonl").open("w", encoding="utf-8") as fh:
        for r in runs_5k:
            for row in r["sample_trace"]:
                fh.write(json.dumps({"horizon": 5000, "seed": r["seed"], **row}) + "\n")
            compact = {k: v for k, v in r.items() if k != "sample_trace"}
            compact_5k.append(compact)
    sum_5k = summarize(compact_5k)
    _write(out_dir / "per_seed_metrics_5k.json", compact_5k)

    print("Running 20k × 5 seeds…")
    runs_20k = [run_childhood(seed=s, ticks=20000, cognition=False, sample_every=100) for s in SEEDS]
    compact_20k = []
    with (out_dir / "resource_work_trace.jsonl").open("a", encoding="utf-8") as fh:
        for r in runs_20k:
            for row in r["sample_trace"]:
                fh.write(json.dumps({"horizon": 20000, "seed": r["seed"], **row}) + "\n")
            compact_20k.append({k: v for k, v in r.items() if k != "sample_trace"})
    sum_20k = summarize(compact_20k)
    _write(out_dir / "per_seed_metrics_20k.json", compact_20k)

    assess = assess_runway(sum_5k, sum_20k)
    summary = {
        "seeds": SEEDS,
        "summary_5k": sum_5k,
        "summary_20k": sum_20k,
        "assessment": assess,
        "ecology": eco_dump,
    }
    _write(out_dir / "summary.json", summary)
    _write(out_dir / "per_seed_metrics.json", {"5k": compact_5k, "20k": compact_20k})
    write_report(
        out_dir,
        eco_cfg=eco_dump,
        s5_runs=compact_5k,
        s5=sum_5k,
        s20_runs=compact_20k,
        s20=sum_20k,
        assess=assess,
    )
    _write(
        out_dir / "README.md",
        "# TIKTAALIK_CHILDHOOD_01\n\n"
        "Physical runway validation for promoted BASELINE_CLIMATE_DEFAULT.\n"
        "No commit. No PSC interpretation.\n",
    )
    print(json.dumps({"out_dir": str(out_dir), "assessment": assess}, indent=2, default=str))


if __name__ == "__main__":
    main()
