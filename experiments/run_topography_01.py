#!/usr/bin/env python3
"""TOPOGRAPHY-01 — physics calibration for terrain drag / potential.

Not a cognition success test. Controlled MOVE vs WAIT under matched initial state.
"""
from __future__ import annotations

import json
import math
import sys
import time
from copy import deepcopy
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
    TERRAIN_GENERATOR_VERSION,
    TerrainConfig,
    set_linear_potential_ramp,
    set_uniform_terrain,
)

OUT_ROOT = ROOT / "results" / "physics"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        path.write_text(obj, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _base_cfg() -> Any:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    # Enable terrain coupling with synthetic fields installed per condition.
    cfg.planet.terrain = TerrainConfig(
        enabled=True,
        mode="FLAT",
        drag_base=0.0,
        drag_amplitude=0.0,
        potential_amplitude=0.0,
        force_scale=0.12,
        drag_coupling=1.0,
        max_gradient=0.5,
        wait_force_scale=0.15,
        terrain_seed=17,
    )
    # Reduce flow so terrain conditions dominate this calibration.
    cfg.planet.flow_enabled = False
    return cfg


def _install(rt: PhysicalSystemRuntime, condition: str) -> None:
    if condition == "FLAT":
        set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=rt.seed)
    elif condition == "HIGH_DRAG":
        set_uniform_terrain(rt.world, potential=0.0, drag=0.85, experiment_seed=rt.seed)
    elif condition == "UPHILL":
        # Move +x against increasing potential
        set_linear_potential_ramp(rt.world, axis="x", amplitude=2.0, drag=0.05, experiment_seed=rt.seed)
    elif condition == "DOWNHILL":
        set_linear_potential_ramp(rt.world, axis="x", amplitude=-2.0, drag=0.05, experiment_seed=rt.seed)
    else:
        raise ValueError(condition)
    # Ensure config marks terrain enabled for force sampling
    rt.config.planet.terrain.enabled = True


def _run(condition: str, *, mode: str, ticks: int = 200, seed: int = 17) -> dict[str, Any]:
    cfg = _base_cfg()
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    _install(rt, condition)
    # Matched start
    rt.body.x = 8.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    rt.body.mechanical_work_reservoir = 5.0
    x0, y0 = float(rt.body.x), float(rt.body.y)
    path = 0.0
    work_limited = 0
    w0 = float(rt.body.mechanical_work_reservoir)
    for _ in range(ticks):
        xb, yb = float(rt.body.x), float(rt.body.y)
        if mode == "WAIT":
            rt.step_forced_action("WAIT")
        else:
            rt.step_forced_action("MOVE:E")
        dx = float(rt.body.x) - xb
        # unwrap for path (no wrap expected on short runs from x=8)
        path += math.hypot(dx, float(rt.body.y) - yb)
        aw = rt.last_action_work_ledger or {}
        if aw.get("work_limited") or aw.get("reservoir_depleted"):
            work_limited += 1
    net = math.hypot(float(rt.body.x) - x0, float(rt.body.y) - y0)
    tmeta = (rt.last_orientation_meta or {}).get("terrain") or {}
    return {
        "condition": condition,
        "mode": mode,
        "ticks": ticks,
        "seed": seed,
        "path_distance": path,
        "net_displacement": net,
        "dx": float(rt.body.x) - x0,
        "dy": float(rt.body.y) - y0,
        "final_speed": math.hypot(float(rt.body.vx), float(rt.body.vy)),
        "work_delta": float(rt.body.mechanical_work_reservoir) - w0,
        "work_limited_events": work_limited,
        "mean_drag": tmeta.get("mean_drag"),
        "mean_potential": tmeta.get("mean_potential"),
        "mean_grad": tmeta.get("mean_grad"),
        "terrain_meta": rt.world.terrain_meta,
        "generator_version": TERRAIN_GENERATOR_VERSION,
    }


def main() -> None:
    out = OUT_ROOT / f"topography_01_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    conditions = ["FLAT", "HIGH_DRAG", "UPHILL", "DOWNHILL"]
    move = {c: _run(c, mode="MOVE") for c in conditions}
    wait = {c: _run(c, mode="WAIT", ticks=500) for c in conditions}

    summary = {
        "elapsed_s": time.perf_counter() - t0,
        "MOVE": move,
        "WAIT": wait,
        "comparisons": {
            "HIGH_DRAG_path_vs_FLAT": move["HIGH_DRAG"]["path_distance"] / max(1e-9, move["FLAT"]["path_distance"]),
            "UPHILL_path_vs_FLAT": move["UPHILL"]["path_distance"] / max(1e-9, move["FLAT"]["path_distance"]),
            "DOWNHILL_path_vs_UPHILL": move["DOWNHILL"]["path_distance"] / max(1e-9, move["UPHILL"]["path_distance"]),
            "WAIT_max_net": max(wait[c]["net_displacement"] for c in conditions),
            "WAIT_max_path": max(wait[c]["path_distance"] for c in conditions),
        },
        "gates": {
            "high_drag_less_or_costlier": (
                move["HIGH_DRAG"]["path_distance"] < 0.95 * move["FLAT"]["path_distance"]
                or move["HIGH_DRAG"]["work_delta"] < move["FLAT"]["work_delta"] - 1e-6
            ),
            "uphill_less_than_flat": move["UPHILL"]["path_distance"] < 0.98 * move["FLAT"]["path_distance"],
            "downhill_exceeds_uphill": move["DOWNHILL"]["path_distance"] > move["UPHILL"]["path_distance"],
            "wait_bounded": max(wait[c]["net_displacement"] for c in conditions) < 8.0,
            "no_free_work_from_terrain": all(wait[c]["work_delta"] <= 1e-9 for c in conditions),
        },
        "allowed_claim": (
            "Spatially heterogeneous drag/potential changes locomotor displacement "
            "and dissipative cost without semantic obstacles or free work credits."
        ),
    }
    _write(out / "summary.json", summary)
    _write(out / "move_metrics.json", move)
    _write(out / "wait_metrics.json", wait)
    report = f"""# TOPOGRAPHY-01

Physics calibration only. Not navigation / preference / planning.

## MOVE path distances
{json.dumps({c: move[c]['path_distance'] for c in conditions}, indent=2)}

## WAIT net displacement (500 ticks)
{json.dumps({c: wait[c]['net_displacement'] for c in conditions}, indent=2)}

## Gates
{json.dumps(summary['gates'], indent=2)}
"""
    _write(out / "report.md", report)
    print(json.dumps({"out_dir": str(out), "gates": summary["gates"], "comparisons": summary["comparisons"]}, indent=2))


if __name__ == "__main__":
    main()
