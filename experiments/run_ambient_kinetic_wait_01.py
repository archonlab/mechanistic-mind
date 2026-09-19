#!/usr/bin/env python3
"""AMBIENT_KINETIC_WAIT_01 — kinetic WAIT keeps full ambient force.

Identical initial vx, then WAIT under ZERO / aligned / opposing / crosswise ambient.
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
from mechanistic_mind.planet.ambient import AmbientConfig, set_uniform_ambient
from mechanistic_mind.planet.terrain import TerrainConfig, set_uniform_terrain

OUT_ROOT = ROOT / "results" / "physics"
SEED = 17
TICKS = 80
VX0 = 0.12
AMP = 0.02
CONDITIONS = {
    "ZERO": (0.0, 0.0),
    "ALIGNED": (AMP, 0.0),
    "OPPOSING": (-AMP, 0.0),
    "CROSSWISE": (0.0, AMP),
}


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


def _base_cfg() -> Any:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.planet.climate_ecology.enabled = False
    cfg.body.drag = 0.15
    cfg.planet.terrain = TerrainConfig(
        enabled=True,
        mode="FLAT",
        force_scale=0.12,
        drag_coupling=1.0,
        wait_force_scale=0.15,
        kinetic_speed_threshold=0.025,
        terrain_seed=SEED,
    )
    cfg.planet.ambient = AmbientConfig(
        enabled=True,
        wait_force_scale=0.15,
        kinetic_speed_threshold=0.025,
        ambient_seed=SEED,
    )
    return cfg


def _run(name: str, fx: float, fy: float) -> dict[str, Any]:
    cfg = _base_cfg()
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=SEED)
    set_uniform_ambient(rt.world, fx=fx, fy=fy, experiment_seed=SEED, config=cfg.planet.ambient)
    rt.config.planet.terrain.enabled = True
    rt.config.planet.ambient.enabled = True
    rt.body.x = 8.0
    rt.body.y = 16.0
    rt.body.vx = VX0
    rt.body.vy = 0.0
    w = int(rt.config.planet.width)
    h = int(rt.config.planet.height)
    x0, y0 = float(rt.body.x), float(rt.body.y)
    path = 0.0
    saw_kinetic = False
    for _ in range(TICKS):
        xb, yb = float(rt.body.x), float(rt.body.y)
        rt.step_forced_action("WAIT")
        am = (rt.last_orientation_meta or {}).get("ambient") or {}
        if am.get("kinetic_wait"):
            saw_kinetic = True
        path += math.hypot(
            _wrap_delta(xb, float(rt.body.x), w),
            _wrap_delta(yb, float(rt.body.y), h),
        )
    dx = _wrap_delta(x0, float(rt.body.x), w)
    dy = _wrap_delta(y0, float(rt.body.y), h)
    ameta = (rt.last_orientation_meta or {}).get("ambient") or {}
    return {
        "condition": name,
        "fx": fx,
        "fy": fy,
        "ticks": TICKS,
        "vx0": VX0,
        "final_vx": float(rt.body.vx),
        "final_vy": float(rt.body.vy),
        "dx": dx,
        "dy": dy,
        "path_distance": path,
        "saw_kinetic_wait": saw_kinetic,
        "ambient_scale_last": ameta.get("scale"),
        "kinetic_wait_last": ameta.get("kinetic_wait"),
    }


def main() -> int:
    out = OUT_ROOT / f"ambient_kinetic_wait_01_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    results = {name: _run(name, fx, fy) for name, (fx, fy) in CONDITIONS.items()}
    gates = {
        "aligned_preserves_higher_vx_than_opposing": (
            results["ALIGNED"]["final_vx"] > results["OPPOSING"]["final_vx"] + 1e-4
        ),
        "crosswise_changes_vy_more_than_zero": (
            abs(results["CROSSWISE"]["final_vy"]) > abs(results["ZERO"]["final_vy"]) + 1e-4
        ),
        "aligned_vx_positive": results["ALIGNED"]["final_vx"] > 0.05,
    }
    summary = {
        "experiment": "AMBIENT_KINETIC_WAIT_01",
        "elapsed_s": time.perf_counter() - t0,
        "conditions": results,
        "gates": gates,
        "all_passed": all(gates.values()),
        "note": "Kinetic WAIT (speed >= threshold) applies full ambient force.",
    }
    _write(out / "summary.json", summary)
    _write(out / "metrics.json", results)
    vels = {c: {"vx": results[c]["final_vx"], "vy": results[c]["final_vy"]} for c in CONDITIONS}
    report = f"""# AMBIENT_KINETIC_WAIT_01

Identical initial vx={VX0}, then WAIT.

## Final velocities
{json.dumps(vels, indent=2)}

## Gates
{json.dumps(gates, indent=2)}

Overall: {'PASS' if summary['all_passed'] else 'FAIL'}
"""
    _write(out / "report.md", report)
    print(json.dumps({"out_dir": str(out), "gates": gates, "all_passed": summary["all_passed"]}, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
