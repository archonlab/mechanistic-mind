#!/usr/bin/env python3
"""AMBIENT_WAIT_01 — resting WAIT under uniform ambient (attenuated).

ZERO / WEAK / MODERATE ambient. Horizons 200, 1000 (+5000 if fast).
Gate: WEAK path/net at 1000 ticks remains bounded (not map-scale transport).
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
CONDITIONS = {"ZERO": 0.0, "WEAK": 0.01, "MODERATE": 0.03}
HORIZONS = (200, 1000, 5000)
# Map is typically 32 — "map-scale" means multi-cell transport approaching width.
BOUNDED_NET_AT_1000 = 8.0
BOUNDED_PATH_AT_1000 = 8.0


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


def _run(name: str, fy: float, ticks: int) -> dict[str, Any]:
    cfg = _base_cfg()
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=SEED)
    set_uniform_ambient(rt.world, fx=0.0, fy=fy, experiment_seed=SEED, config=cfg.planet.ambient)
    rt.config.planet.terrain.enabled = True
    rt.config.planet.ambient.enabled = True
    rt.body.x = 16.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    w = int(rt.config.planet.width)
    h = int(rt.config.planet.height)
    x0, y0 = float(rt.body.x), float(rt.body.y)
    path = 0.0
    for _ in range(ticks):
        xb, yb = float(rt.body.x), float(rt.body.y)
        rt.step_forced_action("WAIT")
        path += math.hypot(
            _wrap_delta(xb, float(rt.body.x), w),
            _wrap_delta(yb, float(rt.body.y), h),
        )
    dx = _wrap_delta(x0, float(rt.body.x), w)
    dy = _wrap_delta(y0, float(rt.body.y), h)
    ameta = (rt.last_orientation_meta or {}).get("ambient") or {}
    return {
        "condition": name,
        "fy": fy,
        "ticks": ticks,
        "seed": SEED,
        "dx": dx,
        "dy": dy,
        "path_distance": path,
        "net_displacement": math.hypot(dx, dy),
        "final_speed": math.hypot(float(rt.body.vx), float(rt.body.vy)),
        "ambient_scale_last": ameta.get("scale"),
        "kinetic_wait_last": ameta.get("kinetic_wait"),
        "map_width": w,
        "map_height": h,
    }


def main() -> int:
    out = OUT_ROOT / f"ambient_wait_01_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    results: dict[str, dict[str, Any]] = {}
    include_5000 = True
    for name, fy in CONDITIONS.items():
        results[name] = {}
        for ticks in HORIZONS:
            if ticks == 5000 and not include_5000:
                continue
            t_h = time.perf_counter()
            results[name][str(ticks)] = _run(name, fy, ticks)
            if ticks == 1000 and (time.perf_counter() - t_h) > 8.0:
                # Skip 5000 if 1000 already slow.
                include_5000 = False
    weak_1000 = results["WEAK"]["1000"]
    gates = {
        "weak_net_bounded_at_1000": weak_1000["net_displacement"] < BOUNDED_NET_AT_1000,
        "weak_path_bounded_at_1000": weak_1000["path_distance"] < BOUNDED_PATH_AT_1000,
        "weak_not_map_scale": weak_1000["net_displacement"] < 0.5 * float(weak_1000["map_width"]),
        "zero_still_at_rest": results["ZERO"]["1000"]["net_displacement"] < 1e-6,
    }
    summary = {
        "experiment": "AMBIENT_WAIT_01",
        "elapsed_s": time.perf_counter() - t0,
        "horizons": [h for h in HORIZONS if h != 5000 or include_5000 or "5000" in results["WEAK"]],
        "include_5000": "5000" in results["WEAK"],
        "conditions": results,
        "gates": gates,
        "all_passed": all(gates.values()),
        "bound_net_at_1000": BOUNDED_NET_AT_1000,
        "bound_path_at_1000": BOUNDED_PATH_AT_1000,
        "note": (
            "Resting WAIT attenuates ambient by wait_force_scale. "
            "WEAK at 1000 ticks must remain bounded (not map-scale transport)."
        ),
    }
    _write(out / "summary.json", summary)
    _write(out / "metrics.json", results)
    report = f"""# AMBIENT_WAIT_01

Resting WAIT under uniform ambient.

## WEAK metrics
{json.dumps(results['WEAK'], indent=2)}

## Gates
{json.dumps(gates, indent=2)}

Overall: {'PASS' if summary['all_passed'] else 'FAIL'}
"""
    _write(out / "report.md", report)
    print(json.dumps({"out_dir": str(out), "gates": gates, "all_passed": summary["all_passed"]}, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
