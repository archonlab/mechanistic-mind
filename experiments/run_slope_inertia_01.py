#!/usr/bin/env python3
"""SLOPE_INERTIA_01 — FLAT / DOWNHILL / UPHILL MOVE then WAIT inertia.

Synthetic ramps via set_uniform_terrain / set_linear_potential_ramp.
True CoM velocity integration under terrain potential force.
"""
from __future__ import annotations

import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_BASELINE,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.planet.terrain import (
    TerrainConfig,
    set_linear_potential_ramp,
    set_uniform_terrain,
)

OUT_ROOT = ROOT / "results" / "physics"

N_MOVE = 40
N_WAIT = 80
SEED = 17


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _base_cfg() -> Any:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.planet.climate_ecology.enabled = False
    cfg.planet.terrain = TerrainConfig(
        enabled=True,
        mode="FLAT",
        force_scale=0.12,
        drag_coupling=1.0,
        wait_force_scale=0.20,
        kinetic_speed_threshold=0.025,
        max_gradient=0.5,
        terrain_seed=SEED,
    )
    return cfg


def _install(rt: PhysicalSystemRuntime, condition: str) -> None:
    if condition == "FLAT":
        set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=rt.seed)
    elif condition == "DOWNHILL":
        set_linear_potential_ramp(rt.world, axis="x", amplitude=-2.0, drag=0.05, experiment_seed=rt.seed)
    elif condition == "UPHILL":
        set_linear_potential_ramp(rt.world, axis="x", amplitude=2.0, drag=0.05, experiment_seed=rt.seed)
    else:
        raise ValueError(condition)
    rt.config.planet.terrain.enabled = True


def _run(condition: str, *, n_move: int = N_MOVE, n_wait: int = N_WAIT) -> dict[str, Any]:
    cfg = _base_cfg()
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    _install(rt, condition)
    rt.body.x = 8.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    rt.body.mechanical_work_reservoir = 5.0
    x0, y0 = float(rt.body.x), float(rt.body.y)
    series: list[dict[str, Any]] = []
    for i in range(n_move + n_wait):
        phase = "MOVE" if i < n_move else "WAIT"
        act = "MOVE:E" if phase == "MOVE" else "WAIT"
        rt.step_forced_action(act)
        sp = math.hypot(float(rt.body.vx), float(rt.body.vy))
        series.append(
            {
                "tick": i,
                "phase": phase,
                "action": act,
                "x": float(rt.body.x),
                "y": float(rt.body.y),
                "vx": float(rt.body.vx),
                "vy": float(rt.body.vy),
                "speed": sp,
                "dx_from_start": float(rt.body.x) - x0,
                "dy_from_start": float(rt.body.y) - y0,
            }
        )
    wait = series[n_move:]
    move = series[:n_move]
    speed_after_wait = wait[-1]["speed"] if wait else 0.0
    mean_wait_speed = float(sum(r["speed"] for r in wait) / max(1, len(wait)))
    # Decay: ratio of late-wait mean speed to early-wait mean speed
    early = wait[: max(1, len(wait) // 4)]
    late = wait[-max(1, len(wait) // 4) :]
    early_mean = float(sum(r["speed"] for r in early) / len(early))
    late_mean = float(sum(r["speed"] for r in late) / len(late))
    decay_ratio = late_mean / max(1e-12, early_mean)
    dx_wait = wait[-1]["x"] - move[-1]["x"] if wait and move else 0.0
    return {
        "condition": condition,
        "n_move": n_move,
        "n_wait": n_wait,
        "seed": SEED,
        "series": series,
        "metrics": {
            "speed_end_move": move[-1]["speed"] if move else 0.0,
            "speed_after_wait": speed_after_wait,
            "mean_wait_speed": mean_wait_speed,
            "early_wait_mean_speed": early_mean,
            "late_wait_mean_speed": late_mean,
            "decay_ratio_late_over_early": decay_ratio,
            "dx_during_wait": dx_wait,
            "net_displacement": math.hypot(series[-1]["x"] - x0, series[-1]["y"] - y0),
            "final_x": series[-1]["x"],
            "final_vx": series[-1]["vx"],
        },
    }


def _resting_flat_wait(ticks: int = 200) -> dict[str, Any]:
    cfg = _base_cfg()
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    _install(rt, "FLAT")
    rt.body.x = 8.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    x0, y0 = float(rt.body.x), float(rt.body.y)
    for _ in range(ticks):
        rt.step_forced_action("WAIT")
    net = math.hypot(float(rt.body.x) - x0, float(rt.body.y) - y0)
    return {
        "ticks": ticks,
        "net_displacement": net,
        "final_speed": math.hypot(float(rt.body.vx), float(rt.body.vy)),
        "map_transport": net > 0.05,
    }


def main() -> int:
    out = OUT_ROOT / f"slope_inertia_01_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    conditions = ["FLAT", "DOWNHILL", "UPHILL"]
    runs = {c: _run(c) for c in conditions}
    resting = _resting_flat_wait()

    m = {c: runs[c]["metrics"] for c in conditions}
    gates = {
        "downhill_wait_speed_gt_flat": (
            m["DOWNHILL"]["speed_after_wait"] > m["FLAT"]["speed_after_wait"] + 1e-6
            or m["DOWNHILL"]["mean_wait_speed"] > m["FLAT"]["mean_wait_speed"] + 1e-6
        ),
        "uphill_decays_faster_than_flat": (
            m["UPHILL"]["decay_ratio_late_over_early"]
            < m["FLAT"]["decay_ratio_late_over_early"] - 1e-6
            or m["UPHILL"]["mean_wait_speed"] < m["FLAT"]["mean_wait_speed"] - 1e-6
        ),
        "resting_wait_flat_no_map_transport": resting["net_displacement"] < 0.05,
    }
    summary = {
        "experiment": "SLOPE_INERTIA_01",
        "elapsed_s": time.perf_counter() - t0,
        "n_move": N_MOVE,
        "n_wait": N_WAIT,
        "metrics": m,
        "resting_flat_wait": resting,
        "gates": gates,
        "all_passed": all(gates.values()),
        "comparisons": {
            "downhill_over_flat_wait_speed": (
                m["DOWNHILL"]["speed_after_wait"] / max(1e-12, m["FLAT"]["speed_after_wait"])
            ),
            "uphill_vs_flat_decay_ratio": (
                m["UPHILL"]["decay_ratio_late_over_early"]
                / max(1e-12, m["FLAT"]["decay_ratio_late_over_early"])
            ),
        },
    }
    _write(out / "summary.json", summary)
    for c in conditions:
        _write(out / f"{c.lower()}_series.json", runs[c])

    print(f"out_dir={out}")
    n_pass = sum(1 for v in gates.values() if v)
    print(f"gates: {n_pass} PASS / {len(gates) - n_pass} FAIL")
    for g, ok in gates.items():
        print(f"  {'PASS' if ok else 'FAIL'}: {g}")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
