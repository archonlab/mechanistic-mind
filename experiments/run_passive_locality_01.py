"""PASSIVE_LOCALITY_01 — resting WAIT locality vs 1-cell Moore sensory horizon.

Uses CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL. No cognition retune.
Gates G1–G8 predeclared in local_physical_coherence.PASSIVE_LOCALITY_GATES.
"""
from __future__ import annotations

import json
import math
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mechanistic_mind.research.local_physical_coherence import (  # noqa: E402
    LOCAL_SENSORY_HORIZON,
    calibrated_cfg,
    evaluate_passive_locality_gates,
    run_forced_trace,
    trajectory_metrics_extended,
    window_excursion_probs,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime  # noqa: E402

OUT = ROOT / "results" / "physics" / "passive_locality_01"
SEEDS = (17, 23, 41, 59, 83)
WINDOWS = (25, 80, 400, 800)
TICKS = 800


def _median_merge(rows: list[dict], key_path: tuple[str, ...]) -> dict:
    vals = []
    for r in rows:
        cur: object = r
        ok = True
        for k in key_path:
            if not isinstance(cur, dict) or k not in cur:
                ok = False
                break
            cur = cur[k]  # type: ignore[index]
        if ok and isinstance(cur, dict) and "median" in cur:
            vals.append(float(cur["median"]))
        elif ok and isinstance(cur, (int, float)):
            vals.append(float(cur))
    if not vals:
        return {"median": 0.0, "min": 0.0, "max": 0.0, "p10": 0.0, "p90": 0.0}
    a = np.asarray(vals, dtype=np.float64)
    return {
        "median": float(np.median(a)),
        "min": float(np.min(a)),
        "max": float(np.max(a)),
        "p10": float(np.percentile(a, 10)),
        "p90": float(np.percentile(a, 90)),
        "mean": float(np.mean(a)),
        "n": len(vals),
    }


def force_channel_locality(seed: int = 17, ticks: int = 400) -> dict:
    """Matched force ablation on max excursion / neighborhood replacement."""
    channels = {
        "A_all_off": dict(terrain=False, ambient=False, thermal_flow=False),
        "B_terrain_only": dict(terrain=True, ambient=False, thermal_flow=False),
        "C_ambient_only": dict(terrain=False, ambient=True, thermal_flow=False),
        "D_thermal_only": dict(terrain=False, ambient=False, thermal_flow=True),
        "E_terrain_ambient": dict(terrain=True, ambient=True, thermal_flow=False),
        "F_terrain_thermal": dict(terrain=True, ambient=False, thermal_flow=True),
        "G_ambient_thermal": dict(terrain=False, ambient=True, thermal_flow=True),
        "H_full": dict(terrain=True, ambient=True, thermal_flow=True),
    }
    out = {}
    for name, kw in channels.items():
        cfg = calibrated_cfg(cognition=False, **kw)
        tr = run_forced_trace(cfg, seed=seed, ticks=ticks, action="WAIT")
        traj = tr["trajectory"]
        out[name] = {
            "max_excursion": traj["max_excursion_from_start"],
            "path": traj["path_length_euclidean"],
            "cell_crossings": traj["cell_boundary_crossings"],
            "center_cell_changes": traj["local_context"]["center_cell_changes"],
            "complete_neighborhood_replacements": traj["local_context"]["complete_neighborhood_replacements"],
            "mean_neighbor_retention": traj["local_context"]["mean_neighbor_retention"],
        }
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = calibrated_cfg(cognition=False)

    resting_rows = []
    for seed in SEEDS:
        tr = run_forced_trace(cfg, seed=seed, ticks=TICKS, action="WAIT")
        resting_rows.append(tr)

    # Aggregate windows across seeds
    wait_windows = {}
    for win in WINDOWS:
        wait_windows[str(win)] = {
            "max_excursion": _median_merge(resting_rows, ("windows", str(win), "max_excursion")),
            "path_length": _median_merge(resting_rows, ("windows", str(win), "path_length")),
            "net_displacement": _median_merge(resting_rows, ("windows", str(win), "net_displacement")),
            "unique_cells": _median_merge(resting_rows, ("windows", str(win), "unique_cells")),
            "cell_boundary_crossings": _median_merge(resting_rows, ("windows", str(win), "cell_boundary_crossings")),
            "complete_neighborhood_replacements": _median_merge(
                resting_rows, ("windows", str(win), "complete_neighborhood_replacements")
            ),
            "P_excursion_gt_0.5": float(np.median([
                float((r.get("windows") or {}).get(str(win), {}).get("P_excursion_gt_0.5") or 0)
                for r in resting_rows
            ])),
            "P_excursion_gt_1": float(np.median([
                float((r.get("windows") or {}).get(str(win), {}).get("P_excursion_gt_1.0") or 0)
                for r in resting_rows
            ])),
            "P_excursion_gt_2": float(np.median([
                float((r.get("windows") or {}).get(str(win), {}).get("P_excursion_gt_2.0") or 0)
                for r in resting_rows
            ])),
            "P_excursion_gt_5": float(np.median([
                float((r.get("windows") or {}).get(str(win), {}).get("P_excursion_gt_5.0") or 0)
                for r in resting_rows
            ])),
        }

    resting_wait = {
        "seeds": list(SEEDS),
        "ticks": TICKS,
        "per_seed": [
            {
                "seed": r["seed"],
                "path": r["trajectory"]["path_length_euclidean"],
                "max_excursion": r["trajectory"]["max_excursion_from_start"],
                "unique_cells": r["trajectory"]["unique_cells"],
                "local_context": r["trajectory"]["local_context"],
                "path_vs_velocity": r["trajectory"]["path_vs_velocity_consistency"],
            }
            for r in resting_rows
        ],
        "trajectory": {
            "path_length_euclidean": float(np.median([r["trajectory"]["path_length_euclidean"] for r in resting_rows])),
            "max_excursion_from_start": float(np.median([r["trajectory"]["max_excursion_from_start"] for r in resting_rows])),
        },
        "windows": wait_windows,
    }

    # Controlled MOVE reference (same seeds / duration)
    move_rows = []
    for seed in SEEDS:
        tr = run_forced_trace(cfg, seed=seed, ticks=TICKS, action="MOVE:E")
        move_rows.append(tr)
    move_windows = {}
    for win in WINDOWS:
        move_windows[str(win)] = {
            "max_excursion": _median_merge(move_rows, ("windows", str(win), "max_excursion")),
            "path_length": _median_merge(move_rows, ("windows", str(win), "path_length")),
            "complete_neighborhood_replacements": _median_merge(
                move_rows, ("windows", str(win), "complete_neighborhood_replacements")
            ),
            "cell_boundary_crossings": _median_merge(move_rows, ("windows", str(win), "cell_boundary_crossings")),
        }
    controlled_move = {
        "action": "MOVE:E",
        "trajectory": {
            "path_length_euclidean": float(np.median([r["trajectory"]["path_length_euclidean"] for r in move_rows])),
            "max_excursion_from_start": float(np.median([r["trajectory"]["max_excursion_from_start"] for r in move_rows])),
        },
        "windows": move_windows,
        "comparison": {
            "move_vs_wait_max_excursion_80": (
                float(move_windows["80"]["max_excursion"]["median"])
                / max(1e-9, float(wait_windows["80"]["max_excursion"]["median"]))
            ),
            "move_vs_wait_path_800": (
                float(np.median([r["trajectory"]["path_length_euclidean"] for r in move_rows]))
                / max(1e-9, float(np.median([r["trajectory"]["path_length_euclidean"] for r in resting_rows])))
            ),
        },
    }

    # KINETIC_WAIT: impulse then WAIT — compare to matched-duration resting WAIT
    kinetic_rows = []
    resting_matched = []
    for seed in SEEDS:
        tr = run_forced_trace(
            cfg, seed=seed, ticks=200, action="WAIT", initial_impulse=(0.35, 0.0)
        )
        kinetic_rows.append(tr)
        resting_matched.append(run_forced_trace(cfg, seed=seed, ticks=200, action="WAIT"))
    kinetic_wait = {
        "initial_impulse": [0.35, 0.0],
        "ticks": 200,
        "trajectory": {
            "path_length_euclidean": float(np.median([r["trajectory"]["path_length_euclidean"] for r in kinetic_rows])),
            "max_excursion_from_start": float(np.median([r["trajectory"]["max_excursion_from_start"] for r in kinetic_rows])),
        },
        "resting_matched_path": float(np.median([r["trajectory"]["path_length_euclidean"] for r in resting_matched])),
        "per_seed_wait_class": [r["wait_class"] for r in kinetic_rows],
    }

    # Force retention / climate dynamic checks (no param change)
    rt = PhysicalSystemRuntime(seed=17, config=deepcopy(cfg))
    temps = []
    for _ in range(100):
        rt.step_forced_action("WAIT")
        temps.append(float(np.mean(rt.world.T)))
    force_decomp = force_channel_locality(seed=17, ticks=400)
    force_retention = {
        "thermal_or_ambient_measurable": (
            force_decomp["D_thermal_only"]["path"] > 0.01
            or force_decomp["C_ambient_only"]["path"] > 0.01
            or force_decomp["H_full"]["path"] > 0.01
        ),
        "climate_dynamic": float(np.std(temps)) > 1e-6,
        "season_period": int(cfg.planet.climate_ecology.season_period),
        "force_decomp": force_decomp,
    }

    summary = {
        "experiment": "PASSIVE_LOCALITY_01",
        "preset": "CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL",
        "local_sensory_horizon": LOCAL_SENSORY_HORIZON,
        "resting_wait": resting_wait,
        "controlled_move": controlled_move,
        "kinetic_wait": kinetic_wait,
        "force_retention": force_retention,
        "parameters_changed": [],
    }
    gates = evaluate_passive_locality_gates(summary)
    summary["gates"] = gates

    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        "# PASSIVE_LOCALITY_01",
        "",
        f"all_pass={gates.get('all_pass')}",
        "",
        "## RESTING_WAIT window medians (max excursion)",
    ]
    for win in WINDOWS:
        me = wait_windows[str(win)]["max_excursion"]
        lines.append(f"- T={win}: median={me['median']:.4f} range=[{me['min']:.4f},{me['max']:.4f}]")
    lines.append("")
    lines.append("## Gates")
    for k, v in gates.items():
        if isinstance(v, dict) and "pass" in v:
            lines.append(f"- {k}: {'PASS' if v['pass'] else 'FAIL'} detail={v.get('detail')}")
    lines.append("")
    lines.append("## Force channel max_excursion (seed 17, 400 ticks WAIT)")
    for k, v in force_decomp.items():
        lines.append(f"- {k}: exc={v['max_excursion']:.4f} path={v['path']:.4f} nbhd_repl={v['complete_neighborhood_replacements']}")
    (OUT / "REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"all_pass": gates.get("all_pass"), "out": str(OUT), "gates": {
        k: v.get("pass") for k, v in gates.items() if isinstance(v, dict) and "pass" in v
    }}, indent=2))
    return 0 if gates.get("all_pass") else 1


if __name__ == "__main__":
    raise SystemExit(main())
