#!/usr/bin/env python3
"""TERRAIN_AMBIENT_COMPOSITION_01 — additive composition of terrain + ambient.

Combinations: FLAT+ZERO, FLAT+CROSS, DOWNHILL+ZERO/ALIGNED/OPPOSING/CROSS, HIGH_DRAG+CROSS.
No special interaction rules — report force components from last_orientation_meta.
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
from mechanistic_mind.planet.terrain import (
    TerrainConfig,
    set_linear_potential_ramp,
    set_uniform_terrain,
)

OUT_ROOT = ROOT / "results" / "physics"
SEED = 17
TICKS = 80
AMB_AMP = 0.02

# (terrain_kind, ambient_kind) → (fx, fy) ambient
COMBOS: list[tuple[str, str, float, float]] = [
    ("FLAT", "ZERO", 0.0, 0.0),
    ("FLAT", "CROSS", 0.0, AMB_AMP),
    ("DOWNHILL", "ZERO", 0.0, 0.0),
    ("DOWNHILL", "ALIGNED", AMB_AMP, 0.0),
    ("DOWNHILL", "OPPOSING", -AMB_AMP, 0.0),
    ("DOWNHILL", "CROSS", 0.0, AMB_AMP),
    ("HIGH_DRAG", "CROSS", 0.0, AMB_AMP),
]


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


def _install_terrain(rt: PhysicalSystemRuntime, kind: str) -> None:
    if kind == "FLAT":
        set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=SEED)
    elif kind == "DOWNHILL":
        set_linear_potential_ramp(rt.world, axis="x", amplitude=-2.0, drag=0.05, experiment_seed=SEED)
    elif kind == "HIGH_DRAG":
        set_uniform_terrain(rt.world, potential=0.0, drag=0.85, experiment_seed=SEED)
    else:
        raise ValueError(kind)
    rt.config.planet.terrain.enabled = True


def _run(terrain: str, ambient: str, fx: float, fy: float) -> dict[str, Any]:
    cfg = _base_cfg()
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    _install_terrain(rt, terrain)
    set_uniform_ambient(rt.world, fx=fx, fy=fy, experiment_seed=SEED, config=cfg.planet.ambient)
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
    om = rt.last_orientation_meta or {}
    tmeta = om.get("terrain") or {}
    ameta = om.get("ambient") or {}
    net = om.get("net_force") or [0.0, 0.0]
    dx = float(rt.body.x) - x0
    dy = float(rt.body.y) - y0
    return {
        "terrain": terrain,
        "ambient": ambient,
        "ambient_fx_set": fx,
        "ambient_fy_set": fy,
        "dx": dx,
        "dy": dy,
        "path_distance": path,
        "net_displacement": math.hypot(dx, dy),
        "last_orientation_meta": {
            "net_force": net,
            "terrain_fx": tmeta.get("fx"),
            "terrain_fy": tmeta.get("fy"),
            "terrain_extra_drag": tmeta.get("extra_drag"),
            "ambient_fx": ameta.get("fx"),
            "ambient_fy": ameta.get("fy"),
            "ambient_scale": ameta.get("scale"),
            "ambient_enabled": ameta.get("enabled"),
            "terrain_enabled": tmeta.get("enabled"),
        },
    }


def main() -> int:
    out = OUT_ROOT / f"terrain_ambient_composition_01_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    results = {}
    for terrain, ambient, fx, fy in COMBOS:
        key = f"{terrain}+{ambient}"
        results[key] = _run(terrain, ambient, fx, fy)

    flat_zero = results["FLAT+ZERO"]
    flat_cross = results["FLAT+CROSS"]
    dh_zero = results["DOWNHILL+ZERO"]
    dh_aligned = results["DOWNHILL+ALIGNED"]
    dh_opposing = results["DOWNHILL+OPPOSING"]
    dh_cross = results["DOWNHILL+CROSS"]

    gates = {
        "flat_cross_more_dy_than_flat_zero": abs(flat_cross["dy"]) > abs(flat_zero["dy"]) + 1e-4,
        "downhill_aligned_dx_exceeds_opposing": dh_aligned["dx"] > dh_opposing["dx"] + 1e-4,
        "downhill_cross_more_dy_than_downhill_zero": abs(dh_cross["dy"]) > abs(dh_zero["dy"]) + 1e-4,
        "ambient_force_reported": all(
            r["last_orientation_meta"]["ambient_enabled"] is True for r in results.values()
        ),
        "terrain_force_reported_on_downhill": (
            abs(float(dh_zero["last_orientation_meta"]["terrain_fx"] or 0.0)) > 1e-6
        ),
        "high_drag_cross_reports_both": (
            results["HIGH_DRAG+CROSS"]["last_orientation_meta"]["ambient_enabled"] is True
            and abs(float(results["HIGH_DRAG+CROSS"]["last_orientation_meta"]["ambient_fy"] or 0.0)) > 1e-6
        ),
    }
    summary = {
        "experiment": "TERRAIN_AMBIENT_COMPOSITION_01",
        "elapsed_s": time.perf_counter() - t0,
        "conditions": results,
        "gates": gates,
        "all_passed": all(gates.values()),
        "note": (
            "Terrain and ambient add into the same CoM integrator; "
            "no special composition rules."
        ),
    }
    _write(out / "summary.json", summary)
    _write(out / "metrics.json", results)
    forces = {k: results[k]["last_orientation_meta"] for k in results}
    paths = {
        k: {"dx": results[k]["dx"], "dy": results[k]["dy"], "path": results[k]["path_distance"]}
        for k in results
    }
    report = f"""# TERRAIN_AMBIENT_COMPOSITION_01

Additive composition of terrain + ambient under MOVE:E.

## Force components (last_orientation_meta)
{json.dumps(forces, indent=2)}

## Path / displacement
{json.dumps(paths, indent=2)}

## Gates
{json.dumps(gates, indent=2)}

Overall: {'PASS' if summary['all_passed'] else 'FAIL'}
"""
    _write(out / "report.md", report)
    print(json.dumps({"out_dir": str(out), "gates": gates, "all_passed": summary["all_passed"]}, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
