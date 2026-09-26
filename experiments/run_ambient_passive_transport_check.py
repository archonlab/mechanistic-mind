#!/usr/bin/env python3
"""AMBIENT_PASSIVE_TRANSPORT_CHECK — MOVE vs WAIT with / without structured ambient.

STRUCTURED_WORLD ambient ON vs BASELINE ambient OFF.
Hard gate: MOVE path >> WAIT path for resting start; WAIT net displacement bounded.
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
    ECOLOGY_STRUCTURED_WORLD,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

OUT_ROOT = ROOT / "results" / "physics"
SEED = 17
MOVE_TICKS = 200
WAIT_TICKS = 400
WAIT_NET_BOUND = 2.0
MOVE_OVER_WAIT_RATIO = 10.0


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        path.write_text(obj, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _wrap_delta(a: float, b: float, size: int) -> float:
    d = float(b) - float(a)
    half = size / 2.0
    if d > half:
        d -= size
    elif d < -half:
        d += size
    return d


def _measure(ecology: str, mode: str, ticks: int) -> dict[str, Any]:
    cfg = make_ecology_config(ecology, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    rt.body.x = 16.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    if mode == "MOVE":
        rt.body.mechanical_work_reservoir = 5.0
    w = int(rt.config.planet.width)
    h = int(rt.config.planet.height)
    x0, y0 = float(rt.body.x), float(rt.body.y)
    path = 0.0
    for _ in range(ticks):
        xb, yb = float(rt.body.x), float(rt.body.y)
        rt.step_forced_action("MOVE:E" if mode == "MOVE" else "WAIT")
        path += math.hypot(
            _wrap_delta(xb, float(rt.body.x), w),
            _wrap_delta(yb, float(rt.body.y), h),
        )
    dx = _wrap_delta(x0, float(rt.body.x), w)
    dy = _wrap_delta(y0, float(rt.body.y), h)
    ambient_cfg = getattr(rt.config.planet, "ambient", None)
    return {
        "ecology": ecology,
        "mode": mode,
        "ticks": ticks,
        "path_distance": path,
        "net_displacement": math.hypot(dx, dy),
        "dx": dx,
        "dy": dy,
        "ambient_enabled": bool(getattr(ambient_cfg, "enabled", False)),
        "ambient_grids_present": rt.world.ambient_fx is not None and rt.world.ambient_fy is not None,
        "ambient_meta": getattr(rt.world, "ambient_meta", None),
    }


def main() -> int:
    out = OUT_ROOT / f"ambient_passive_transport_check_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    results = {
        "baseline_move": _measure(ECOLOGY_BASELINE, "MOVE", MOVE_TICKS),
        "baseline_wait": _measure(ECOLOGY_BASELINE, "WAIT", WAIT_TICKS),
        "world_move": _measure(ECOLOGY_STRUCTURED_WORLD, "MOVE", MOVE_TICKS),
        "world_wait": _measure(ECOLOGY_STRUCTURED_WORLD, "WAIT", WAIT_TICKS),
    }
    wm = results["world_move"]
    ww = results["world_wait"]
    bm = results["baseline_move"]
    bw = results["baseline_wait"]
    ratio = wm["path_distance"] / max(1e-9, ww["path_distance"])
    gates = {
        "baseline_ambient_off": bm["ambient_enabled"] is False and bm["ambient_grids_present"] is False,
        "world_ambient_on": wm["ambient_enabled"] is True and wm["ambient_grids_present"] is True,
        "world_move_path_gt_wait": wm["path_distance"] > MOVE_OVER_WAIT_RATIO * ww["path_distance"],
        "world_wait_net_bounded": ww["net_displacement"] < WAIT_NET_BOUND,
        "baseline_move_path_gt_wait": bm["path_distance"] > MOVE_OVER_WAIT_RATIO * max(1e-9, bw["path_distance"]),
    }
    summary = {
        "experiment": "AMBIENT_PASSIVE_TRANSPORT_CHECK",
        "elapsed_s": time.perf_counter() - t0,
        "move_over_wait_ratio_world": ratio,
        "results": results,
        "gates": gates,
        "all_passed": all(gates.values()),
        "note": (
            "PASSIVE_TRANSPORT-style resting-start MOVE vs WAIT. "
            "STRUCTURED_WORLD ambient ON; BASELINE ambient OFF."
        ),
    }
    _write(out / "summary.json", summary)
    _write(out / "metrics.json", results)
    report = f"""# AMBIENT_PASSIVE_TRANSPORT_CHECK

## Paths
- baseline MOVE: {bm['path_distance']:.4f}  WAIT: {bw['path_distance']:.4f}
- world MOVE: {wm['path_distance']:.4f}  WAIT: {ww['path_distance']:.4f}  (ratio={ratio:.1f})

## WAIT net
- baseline: {bw['net_displacement']:.4f}
- world: {ww['net_displacement']:.4f}

## Gates
{json.dumps(gates, indent=2)}

Overall: {'PASS' if summary['all_passed'] else 'FAIL'}
"""
    _write(out / "report.md", report)
    print(json.dumps({"out_dir": str(out), "gates": gates, "all_passed": summary["all_passed"], "ratio": ratio}, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
