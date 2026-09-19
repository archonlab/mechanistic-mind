#!/usr/bin/env python3
"""AMBIENT_FORCE_01 — uniform ambient deflection under MOVE:E.

Flat terrain, flow off, cognition off.
Compare ZERO / WEAK (fy=0.01) / MODERATE (fy=0.03) via set_uniform_ambient.
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
CONDITIONS = {
    "ZERO": 0.0,
    "WEAK": 0.01,
    "MODERATE": 0.03,
}


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
    cfg.planet.flow_enabled = False
    cfg.planet.climate_ecology.enabled = False
    cfg.planet.terrain = TerrainConfig(
        enabled=True,
        mode="FLAT",
        force_scale=0.12,
        drag_coupling=1.0,
        wait_force_scale=0.15,
        terrain_seed=SEED,
    )
    cfg.planet.ambient = AmbientConfig(
        enabled=True,
        wait_force_scale=0.15,
        kinetic_speed_threshold=0.025,
        ambient_seed=SEED,
    )
    return cfg


def _run(name: str, fy: float) -> dict[str, Any]:
    cfg = _base_cfg()
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=SEED)
    set_uniform_ambient(rt.world, fx=0.0, fy=fy, experiment_seed=SEED, config=cfg.planet.ambient)
    rt.config.planet.terrain.enabled = True
    rt.config.planet.ambient.enabled = True
    rt.body.x = 8.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    rt.body.mechanical_work_reservoir = 5.0
    x0, y0 = float(rt.body.x), float(rt.body.y)
    path = 0.0
    for _ in range(TICKS):
        xb, yb = float(rt.body.x), float(rt.body.y)
        rt.step_forced_action("MOVE:E")
        path += math.hypot(float(rt.body.x) - xb, float(rt.body.y) - yb)
    dx = float(rt.body.x) - x0
    dy = float(rt.body.y) - y0
    ang = math.degrees(math.atan2(dy, dx)) if abs(dx) + abs(dy) > 1e-12 else 0.0
    ameta = (rt.last_orientation_meta or {}).get("ambient") or {}
    return {
        "condition": name,
        "fy": fy,
        "ticks": TICKS,
        "seed": SEED,
        "dx": dx,
        "dy": dy,
        "path_distance": path,
        "net_displacement": math.hypot(dx, dy),
        "deflection_angle_deg": ang,
        "abs_deflection_angle_deg": abs(ang),
        "eastward_dominant": dx > abs(dy),
        "ambient_meta_last": ameta,
    }


def main() -> int:
    out = OUT_ROOT / f"ambient_force_01_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    results = {name: _run(name, fy) for name, fy in CONDITIONS.items()}
    z = results["ZERO"]
    w = results["WEAK"]
    m = results["MODERATE"]
    gates = {
        "weak_deflects_more_than_zero": w["abs_deflection_angle_deg"] > z["abs_deflection_angle_deg"] + 1e-6
        and abs(w["dy"]) > abs(z["dy"]) + 1e-6,
        "moderate_deflects_more_than_weak": m["abs_deflection_angle_deg"] > w["abs_deflection_angle_deg"] + 1e-6
        and abs(m["dy"]) > abs(w["dy"]) + 1e-6,
        "move_eastward_dominant": all(results[c]["eastward_dominant"] for c in CONDITIONS),
    }
    summary = {
        "experiment": "AMBIENT_FORCE_01",
        "elapsed_s": time.perf_counter() - t0,
        "conditions": results,
        "gates": gates,
        "all_passed": all(gates.values()),
        "note": "Flat terrain; ambient via set_uniform_ambient; cognition OFF; flow OFF.",
    }
    _write(out / "summary.json", summary)
    _write(out / "metrics.json", results)
    dxdy = {c: {"dx": results[c]["dx"], "dy": results[c]["dy"]} for c in CONDITIONS}
    report = f"""# AMBIENT_FORCE_01

Uniform ambient deflection under MOVE:E (flat terrain).

## Deflection angles (deg)
{json.dumps({c: results[c]['deflection_angle_deg'] for c in CONDITIONS}, indent=2)}

## Net dx / dy
{json.dumps(dxdy, indent=2)}

## Gates
{json.dumps(gates, indent=2)}

Overall: {'PASS' if summary['all_passed'] else 'FAIL'}
"""
    _write(out / "report.md", report)
    print(json.dumps({"out_dir": str(out), "gates": gates, "all_passed": summary["all_passed"]}, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
