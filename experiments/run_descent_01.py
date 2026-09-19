#!/usr/bin/env python3
"""DESCENT_01 — smooth descending potential, persistent kinetic speedup.

Uses set_profile_terrain with Φ decreasing in +x. Brief MOVE then WAIT
integration measures accumulated speed (true inertia), not a per-cell bonus.
"""
from __future__ import annotations

import csv
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

import numpy as np

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_BASELINE,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.planet.terrain import TerrainConfig, set_profile_terrain, set_uniform_terrain

OUT_ROOT = ROOT / "results" / "physics"

SEED = 17
N_MOVE = 3
N_INTEGRATE = 90


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
    cfg.complementary_resources.mode = "OFF"
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    cfg.body.drag = 0.12
    # Weak locomotor impulse so terrain force (not MOVE saturation) drives speed gain.
    cfg.discrete_action_work.impulse_scale = 0.08
    cfg.planet.terrain = TerrainConfig(
        enabled=True,
        mode="FLAT",
        force_scale=0.20,
        drag_coupling=1.0,
        wait_force_scale=0.20,
        kinetic_speed_threshold=0.025,
        max_gradient=4.0,
        terrain_seed=SEED,
    )
    return cfg


def _run(label: str, *, descending: bool) -> dict[str, Any]:
    cfg = _base_cfg()
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    w = int(rt.world.T.shape[1])
    if descending:
        xx = np.linspace(0.0, 1.0, w)
        row = 5.0 * (1.0 - xx)  # high left → low right; MOVE:E is downhill
        set_profile_terrain(
            rt.world,
            row,
            drag=0.0,
            experiment_seed=SEED,
            label="smooth_descent",
            max_gradient=4.0,
        )
    else:
        set_uniform_terrain(rt.world, potential=0.0, drag=0.0, experiment_seed=SEED)
    rt.config.planet.terrain.enabled = True
    rt.body.x = 2.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    rt.body.mechanical_work_reservoir = 5.0
    series: list[dict[str, Any]] = []
    for i in range(N_MOVE + N_INTEGRATE):
        phase = "MOVE" if i < N_MOVE else "WAIT"
        act = "MOVE:E" if phase == "MOVE" else "WAIT"
        rt.step_forced_action(act)
        tmeta = (rt.last_orientation_meta or {}).get("terrain") or {}
        gx = float((tmeta.get("mean_grad") or [0.0, 0.0])[0])
        gy = float((tmeta.get("mean_grad") or [0.0, 0.0])[1])
        series.append(
            {
                "tick": i,
                "phase": phase,
                "action": act,
                "x": float(rt.body.x),
                "y": float(rt.body.y),
                "vx": float(rt.body.vx),
                "vy": float(rt.body.vy),
                "speed": math.hypot(float(rt.body.vx), float(rt.body.vy)),
                "potential": float(tmeta.get("mean_potential") or 0.0),
                "grad_x": gx,
                "grad_y": gy,
                "grad_mag": math.hypot(gx, gy),
                "kinetic_wait": bool(tmeta.get("kinetic_wait")),
                "kappa": tmeta.get("kappa"),
            }
        )
    wait = series[N_MOVE:]
    # Measure gain during integration while still below locomotor plateau.
    early = wait[:8]
    mid = wait[20:35]
    late = wait[-15:]
    return {
        "label": label,
        "descending": descending,
        "n_move": N_MOVE,
        "n_integrate": N_INTEGRATE,
        "series": series,
        "metrics": {
            "speed_end_move": series[N_MOVE - 1]["speed"] if N_MOVE else 0.0,
            "speed_start_wait": early[0]["speed"] if early else 0.0,
            "mean_speed_early_wait": float(sum(r["speed"] for r in early) / max(1, len(early))),
            "mean_speed_mid_wait": float(sum(r["speed"] for r in mid) / max(1, len(mid))),
            "mean_speed_late_wait": float(sum(r["speed"] for r in late) / max(1, len(late))),
            "max_speed": max(r["speed"] for r in series),
            "final_x": series[-1]["x"],
            "dx_total": series[-1]["x"] - series[0]["x"],
            "speed_gain_mid_minus_early": (
                float(sum(r["speed"] for r in mid) / max(1, len(mid)))
                - float(sum(r["speed"] for r in early) / max(1, len(early)))
            ),
        },
    }


def _write_csv(path: Path, series: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "tick",
        "phase",
        "action",
        "x",
        "vx",
        "speed",
        "potential",
        "grad_x",
        "grad_mag",
        "kinetic_wait",
        "kappa",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in series:
            w.writerow(row)


def main() -> int:
    out = OUT_ROOT / f"descent_01_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    descent = _run("descent", descending=True)
    flat = _run("flat_control", descending=False)

    dm = descent["metrics"]
    fm = flat["metrics"]
    # Persistent kinetic: mid-wait speed exceeds early-wait on descent,
    # and exceeds flat control (not a vanishing per-cell impulse).
    speed_increases = dm["mean_speed_mid_wait"] > dm["mean_speed_early_wait"] + 1e-4
    exceeds_flat = dm["mean_speed_mid_wait"] > fm["mean_speed_mid_wait"] + 1e-3
    gates = {
        "speed_increases_across_descent": speed_increases,
        "descent_exceeds_flat_control": exceeds_flat,
        "persistent_kinetic_not_per_cell_bonus": speed_increases and exceeds_flat,
    }
    summary = {
        "experiment": "DESCENT_01",
        "elapsed_s": time.perf_counter() - t0,
        "seed": SEED,
        "descent_metrics": dm,
        "flat_metrics": fm,
        "gates": gates,
        "all_passed": all(gates.values()),
        "note": (
            "Smooth descending Φ across x; brief weak MOVE then kinetic WAIT. "
            "Speed growth on descent vs decaying flat control shows accumulated "
            "potential force into CoM velocity (true inertia), not a per-cell bonus."
        ),
    }
    _write(out / "summary.json", summary)
    _write(out / "descent_series.json", descent)
    _write(out / "flat_series.json", flat)
    _write_csv(out / "descent_timeseries.csv", descent["series"])

    print(f"out_dir={out}")
    n_pass = sum(1 for v in gates.values() if v)
    print(f"gates: {n_pass} PASS / {len(gates) - n_pass} FAIL")
    for g, ok in gates.items():
        print(f"  {'PASS' if ok else 'FAIL'}: {g}")
    print(
        json.dumps(
            {
                "descent_early": dm["mean_speed_early_wait"],
                "descent_mid": dm["mean_speed_mid_wait"],
                "flat_mid": fm["mean_speed_mid_wait"],
            },
            indent=2,
        )
    )
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
