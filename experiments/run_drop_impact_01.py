#!/usr/bin/env python3
"""DROP_IMPACT_01 — smooth approach, sharp drop discontinuity, high-drag landing.

Measures peak speed, acceleration through the drop, post-landing deceleration.
Terrain must not credit mechanical_work_reservoir. No semantic injury labels.
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
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.planet.terrain import TerrainConfig, set_profile_terrain

OUT_ROOT = ROOT / "results" / "physics"

SEED = 17
N_MOVE = 30
N_COAST = 100


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        path.write_text(obj, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _install_drop_profile(rt: PhysicalSystemRuntime) -> dict[str, Any]:
    w = int(rt.world.T.shape[1])
    xx = np.linspace(0.0, 1.0, w)
    # Gentle approach, sharp ledge near x≈0.45, then flat lowland.
    approach = 1.1 - 0.25 * xx
    ledge = 0.5 * (1.0 + np.tanh((xx - 0.45) / 0.012))
    row = approach - 1.6 * ledge
    # High drag after landing zone (x ≳ 0.55).
    drag = np.where(xx < 0.55, 0.02, 0.85)
    set_profile_terrain(
        rt.world,
        row,
        drag=drag,
        experiment_seed=SEED,
        label="drop_impact",
        max_gradient=6.0,
    )
    rt.config.planet.terrain.enabled = True
    return {
        "width": w,
        "drop_center_frac": 0.45,
        "landing_drag": 0.85,
        "approach_drag": 0.02,
        "potential_min": float(np.min(row)),
        "potential_max": float(np.max(row)),
        "max_abs_grad_x": float(np.max(np.abs(rt.world.terrain_grad_x))),
    }


def _base_cfg() -> Any:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.planet.climate_ecology.enabled = False
    cfg.complementary_resources.mode = "OFF"
    cfg.complementary_resources.conversion_enabled = False
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    cfg.planet.terrain = TerrainConfig(
        enabled=True,
        mode="FLAT",
        force_scale=0.16,
        drag_coupling=1.0,
        wait_force_scale=0.20,
        kinetic_speed_threshold=0.025,
        max_gradient=6.0,
        terrain_seed=SEED,
    )
    return cfg


def main() -> int:
    out = OUT_ROOT / f"drop_impact_01_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    cfg = _base_cfg()
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    profile_meta = _install_drop_profile(rt)
    rt.body.x = 2.0
    rt.body.y = 16.0
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    rt.body.mechanical_work_reservoir = 3.0
    w0 = float(rt.body.mechanical_work_reservoir)

    series: list[dict[str, Any]] = []
    for i in range(N_MOVE + N_COAST):
        phase = "MOVE" if i < N_MOVE else "WAIT"
        act = "MOVE:E" if phase == "MOVE" else "WAIT"
        prev_vx = float(rt.body.vx)
        prev_sp = math.hypot(float(rt.body.vx), float(rt.body.vy))
        rt.step_forced_action(act)
        tmeta = (rt.last_orientation_meta or {}).get("terrain") or {}
        sp = math.hypot(float(rt.body.vx), float(rt.body.vy))
        series.append(
            {
                "tick": i,
                "phase": phase,
                "action": act,
                "x": float(rt.body.x),
                "vx": float(rt.body.vx),
                "speed": sp,
                "dvx": float(rt.body.vx) - prev_vx,
                "dspeed": sp - prev_sp,
                "potential": float(tmeta.get("mean_potential") or 0.0),
                "mean_drag": float(tmeta.get("mean_drag") or 0.0),
                "accel_proxy": float(tmeta.get("accel_proxy") or 0.0),
                "work_reservoir": float(rt.body.mechanical_work_reservoir),
                "kinetic_wait": bool(tmeta.get("kinetic_wait")),
            }
        )

    speeds = [r["speed"] for r in series]
    peak_speed = max(speeds)
    peak_i = int(np.argmax(speeds))
    # Acceleration through drop: max positive dspeed near ledge crossing.
    accel_through_drop = max(r["dspeed"] for r in series)
    # Deceleration after peak (landing drag).
    post = series[peak_i : peak_i + 50]
    if len(post) >= 2:
        decel = post[0]["speed"] - post[-1]["speed"]
        min_dspeed_post = min(r["dspeed"] for r in post)
    else:
        decel = 0.0
        min_dspeed_post = 0.0

    work_final = float(rt.body.mechanical_work_reservoir)
    work_delta = work_final - w0
    # Terrain must never credit work; MOVE may spend work (delta <= 0).
    no_terrain_work_credit = work_delta <= 1e-9

    obs = rt.agent_observation()
    hits = audit_cognition_payload(obs)
    blob = repr(obs).upper()
    no_semantic_injury = (
        not hits
        and "INJURY" not in blob
        and "DAMAGE" not in blob
        and "HURT" not in blob
        and "FALL" not in blob
        and "CLIFF" not in blob
        and "TRAP" not in blob
        and "OBSTACLE" not in blob
    )

    gates = {
        "peak_speed_positive": peak_speed > 0.05,
        "accel_through_drop_positive": accel_through_drop > 1e-4,
        "deceleration_after_landing": decel > 0.02 or min_dspeed_post < -1e-4,
        "work_reservoir_unchanged_by_terrain_credit": no_terrain_work_credit,
        "no_semantic_injury": no_semantic_injury,
    }

    summary = {
        "experiment": "DROP_IMPACT_01",
        "elapsed_s": time.perf_counter() - t0,
        "seed": SEED,
        "profile": profile_meta,
        "metrics": {
            "peak_speed": peak_speed,
            "peak_tick": peak_i,
            "peak_x": series[peak_i]["x"],
            "accel_through_drop_max_dspeed": accel_through_drop,
            "deceleration_after_peak": decel,
            "min_dspeed_post_peak": min_dspeed_post,
            "work_initial": w0,
            "work_final": work_final,
            "work_delta": work_delta,
            "final_x": series[-1]["x"],
            "final_speed": series[-1]["speed"],
            "final_drag": series[-1]["mean_drag"],
        },
        "gates": gates,
        "all_passed": all(gates.values()),
        "allowed_claim": (
            "A sharp potential discontinuity produces a transient kinetic peak "
            "followed by high-drag deceleration without work-reservoir credits "
            "or semantic injury labels."
        ),
    }
    _write(out / "summary.json", summary)
    _write(out / "series.json", {"series": series})

    fields = [
        "tick",
        "phase",
        "x",
        "vx",
        "speed",
        "dvx",
        "dspeed",
        "potential",
        "mean_drag",
        "accel_proxy",
        "work_reservoir",
    ]
    with (out / "timeseries.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in series:
            writer.writerow(row)

    print(f"out_dir={out}")
    n_pass = sum(1 for v in gates.values() if v)
    print(f"gates: {n_pass} PASS / {len(gates) - n_pass} FAIL")
    for g, ok in gates.items():
        print(f"  {'PASS' if ok else 'FAIL'}: {g}")
    print(
        json.dumps(
            {
                "peak_speed": peak_speed,
                "accel_through_drop": accel_through_drop,
                "deceleration_after_peak": decel,
                "work_delta": work_delta,
            },
            indent=2,
        )
    )
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
