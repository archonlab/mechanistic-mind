"""WORLD_TIMESCALE_CALIBRATION_01 — shared measurement utilities.

Observer / experiment only. No cognition retuning. No semantic season labels
in runtime physics. Terrain and ambient remain static during this calibration.
"""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

import numpy as np

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_STRUCTURED_WORLD,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime


def wrap_delta(a: float, b: float, size: int) -> float:
    d = float(b) - float(a)
    half = size / 2.0
    if d > half:
        d -= size
    elif d < -half:
        d += size
    return d


def autocorr_time(series: np.ndarray, *, max_lag: int | None = None) -> float | None:
    """First lag where ACF < 1/e; 0 if flat; None if too short."""
    x = np.asarray(series, dtype=np.float64)
    if x.size < 8:
        return None
    x = x - x.mean()
    var = float(np.dot(x, x))
    if var <= 1e-18:
        return 0.0
    max_lag = int(max_lag or min(len(x) // 2, 2000))
    thr = 1.0 / math.e
    for lag in range(1, max_lag + 1):
        ac = float(np.dot(x[:-lag], x[lag:])) / var
        if ac < thr:
            return float(lag)
    return float(max_lag)


def structured_world_cfg(
    *,
    season_period: int | None = None,
    cognition: bool = False,
    terrain: bool = True,
    ambient: bool = True,
    thermal_flow: bool = True,
    freeze_climate: bool = False,
) -> PhysicalSystemConfig:
    """Structured World with optional channel toggles for matched WAIT decomp."""
    cfg = make_ecology_config(ECOLOGY_STRUCTURED_WORLD, trickle=0.0)
    cfg.cognition.cognition_enabled = bool(cognition)
    cfg.endogenous_motor.mode = "OFF"
    if season_period is not None:
        cfg.planet.climate_ecology.season_period = int(season_period)
    if freeze_climate:
        # Preserve fields; stop temporal climate envelope (terrain/ambient tests).
        cfg.planet.climate_ecology.cycle_mode = "stationary"
        cfg.planet.F_fast_amp = 0.0
        cfg.planet.F_slow_amp = 0.0
        cfg.planet.heat_gain = 0.0
        cfg.planet.cool_rate = 0.0
    if not terrain:
        cfg.planet.terrain.enabled = False
    if not ambient:
        cfg.planet.ambient.enabled = False
    if not thermal_flow:
        cfg.planet.flow_enabled = False
        cfg.planet.flow_gain = 0.0
        cfg.body.flow_coupling = 0.0
        cfg.body.wave_coupling = 0.0
    return cfg


def baseline_cfg(*, season_period: int | None = None, cognition: bool = False) -> PhysicalSystemConfig:
    from mechanistic_mind.physical_system.ecology_presets import ECOLOGY_BASELINE

    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = bool(cognition)
    cfg.endogenous_motor.mode = "OFF"
    if season_period is not None:
        cfg.planet.climate_ecology.season_period = int(season_period)
    return cfg


def trajectory_metrics(
    xs: list[float],
    ys: list[float],
    *,
    width: int,
    height: int,
    speeds: list[float] | None = None,
) -> dict[str, Any]:
    """Unique-sample trajectory: path length, unwrapped net, bbox, mean velocity."""
    if len(xs) < 2:
        return {
            "n_samples": len(xs),
            "path_length": 0.0,
            "net_displacement_wrapped": 0.0,
            "unwrapped_dx": 0.0,
            "unwrapped_dy": 0.0,
            "unwrapped_net_displacement": 0.0,
            "unique_cells": 0,
            "mean_speed": 0.0,
            "max_speed": 0.0,
            "bbox_unwrapped": [0.0, 0.0, 0.0, 0.0],
            "dominant_displacement_direction": None,
            "mean_velocity_vector": [0.0, 0.0],
            "start_wrapped": [xs[0], ys[0]] if xs else None,
            "end_wrapped": [xs[-1], ys[-1]] if xs else None,
        }
    path = 0.0
    ux = [float(xs[0])]
    uy = [float(ys[0])]
    for i in range(1, len(xs)):
        dx = wrap_delta(xs[i - 1], xs[i], width)
        dy = wrap_delta(ys[i - 1], ys[i], height)
        path += math.hypot(dx, dy)
        ux.append(ux[-1] + dx)
        uy.append(uy[-1] + dy)
    udx = ux[-1] - ux[0]
    udy = uy[-1] - uy[0]
    cells = {(int(math.floor(x)) % width, int(math.floor(y)) % height) for x, y in zip(xs, ys)}
    sp = [float(s) for s in (speeds or []) if s is not None]
    ang = math.atan2(udy, udx) if (abs(udx) + abs(udy)) > 1e-12 else None
    n_steps = max(1, len(xs) - 1)
    return {
        "n_samples": len(xs),
        "path_length": float(path),
        "net_displacement_wrapped": float(
            math.hypot(wrap_delta(xs[0], xs[-1], width), wrap_delta(ys[0], ys[-1], height))
        ),
        "unwrapped_dx": float(udx),
        "unwrapped_dy": float(udy),
        "unwrapped_net_displacement": float(math.hypot(udx, udy)),
        "unique_cells": len(cells),
        "mean_speed": float(np.mean(sp)) if sp else float(path / n_steps),
        "max_speed": float(max(sp)) if sp else 0.0,
        "bbox_unwrapped": [float(min(ux)), float(min(uy)), float(max(ux)), float(max(uy))],
        "dominant_displacement_direction": float(ang) if ang is not None else None,
        "mean_velocity_vector": [float(udx / n_steps), float(udy / n_steps)],
        "start_wrapped": [float(xs[0]), float(ys[0])],
        "end_wrapped": [float(xs[-1]), float(ys[-1])],
    }


def first_crossing(series: list[float], threshold: float, *, rising: bool = True) -> int | None:
    for i, v in enumerate(series):
        if rising and v >= threshold:
            return i
        if not rising and v <= threshold:
            return i
    return None


def run_wait_trace(
    cfg: PhysicalSystemConfig,
    *,
    seed: int,
    ticks: int,
    record_forces: bool = True,
) -> dict[str, Any]:
    """WAIT-only unique-tick trajectory with optional force channel accounting."""
    rt = PhysicalSystemRuntime(seed=int(seed), config=deepcopy(cfg))
    w = int(rt.config.planet.width)
    h = int(rt.config.planet.height)
    xs, ys, speeds = [], [], []
    force_rows: list[dict[str, float]] = []
    for _ in range(int(ticks)):
        rt.step_forced_action("WAIT")
        xs.append(float(rt.body.x))
        ys.append(float(rt.body.y))
        speeds.append(math.hypot(float(rt.body.vx), float(rt.body.vy)))
        if record_forces:
            ori = getattr(rt, "last_orientation_meta", None) or {}
            if not isinstance(ori, dict):
                ori = {}
            terr = ori.get("terrain") if isinstance(ori.get("terrain"), dict) else {}
            amb = ori.get("ambient") if isinstance(ori.get("ambient"), dict) else {}
            net = ori.get("net_force") or [0.0, 0.0]
            force_rows.append({
                "net_fx": float(net[0]) if len(net) > 0 else 0.0,
                "net_fy": float(net[1]) if len(net) > 1 else 0.0,
                "terrain_fx": float(terr.get("fx") or 0.0),
                "terrain_fy": float(terr.get("fy") or 0.0),
                "terrain_extra_drag": float(terr.get("extra_drag") or 0.0),
                "ambient_fx": float(amb.get("fx") or 0.0),
                "ambient_fy": float(amb.get("fy") or 0.0),
                "speed": speeds[-1],
            })
    traj = trajectory_metrics(xs, ys, width=w, height=h, speeds=speeds)
    out: dict[str, Any] = {
        "seed": int(seed),
        "ticks": int(ticks),
        "action": "WAIT",
        "trajectory": traj,
        "terrain_enabled": bool(getattr(cfg.planet.terrain, "enabled", False)),
        "ambient_enabled": bool(getattr(cfg.planet.ambient, "enabled", False)),
        "flow_enabled": bool(getattr(cfg.planet, "flow_enabled", True)) and float(getattr(cfg.planet, "flow_gain", 0) or 0) > 0,
        "season_period": int(cfg.planet.climate_ecology.season_period),
    }
    if force_rows:
        def _rms(key: str) -> float:
            return float(math.sqrt(np.mean([r[key] ** 2 for r in force_rows])))

        out["force_summary"] = {
            "terrain_fx_rms": _rms("terrain_fx"),
            "terrain_fy_rms": _rms("terrain_fy"),
            "ambient_fx_rms": _rms("ambient_fx"),
            "ambient_fy_rms": _rms("ambient_fy"),
            "net_fx_rms": _rms("net_fx"),
            "net_fy_rms": _rms("net_fy"),
            "mean_extra_drag": float(np.mean([r["terrain_extra_drag"] for r in force_rows])),
            "mean_speed": float(np.mean(speeds)),
            "max_speed": float(max(speeds)),
        }
        # Thermal-flow contribution ≈ residual of net after terrain+ambient (approx).
        terr_m = math.hypot(out["force_summary"]["terrain_fx_rms"], out["force_summary"]["terrain_fy_rms"])
        amb_m = math.hypot(out["force_summary"]["ambient_fx_rms"], out["force_summary"]["ambient_fy_rms"])
        net_m = math.hypot(out["force_summary"]["net_fx_rms"], out["force_summary"]["net_fy_rms"])
        out["force_summary"]["approx_thermal_flow_rms"] = float(max(0.0, net_m - terr_m - amb_m))
        out["force_summary"]["relative"] = {
            "terrain": terr_m,
            "ambient": amb_m,
            "approx_thermal_plus_other": float(max(0.0, net_m - terr_m - amb_m)),
            "net": net_m,
        }
    return out


def cognitive_horizon_inventory() -> dict[str, Any]:
    """Measurement-only inventory of existing temporal horizons (no retune)."""
    from mechanistic_mind.model.tiktaalik import BOUNDED_LIMITS

    return {
        "note": "Measurement only — cognition not modified.",
        "prospective_depth": int(BOUNDED_LIMITS.get("prospective_depth", 3)),
        "tps_WINDOW": int(BOUNDED_LIMITS.get("tps_WINDOW", 4)),
        "tps_RING": int(BOUNDED_LIMITS.get("tps_RING", 16)),
        "action_selection_interval_ticks": 1,
        "observation_cadence_ticks": 1,
        "DEFAULT_LAGS": [0, 1, 2, 3],
        "climate_season_period_default": 80,
        "F_fast_period_default": 40,
        "F_slow_period_default": 400,
        "forbidden_cognition_tokens_include": [
            "environmental_cycle_phase",
            "climate_phase",
            "terrain_potential",
            "ambient_fx",
        ],
    }


TEMPORAL_DEPENDENCY_GRAPH = {
    "verified": True,
    "nodes": {
        "climate_phase": "MEDIUM DYNAMIC / CLIMATE-COUPLED",
        "T_eq / insolation": "CLIMATE-COUPLED",
        "state.T": "FAST DYNAMIC",
        "planet.vx/vy (-grad T)": "FAST DYNAMIC / CLIMATE-COUPLED",
        "forcing F_fast/F_slow": "MEDIUM DYNAMIC",
        "terrain Φ/γ": "STATIC",
        "ambient Fx/Fy": "STATIC",
        "R_A / R_B": "CLIMATE-COUPLED + RESOURCE-COUPLED (+ AGENT under transfer)",
        "body pose/velocity": "AGENT-COUPLED + env forces",
    },
    "edges": [
        "season_phase(tick/period) -> T_eq -> step_thermal -> T",
        "T -> step_flow (-flow_gain*grad T) -> vx,vy",
        "vx,vy * flow_coupling * force_scale -> body force (always)",
        "terrain -κ∇Φ (+ WAIT attenuation) -> body force",
        "ambient Fx/Fy (+ WAIT attenuation) -> body force",
        "local T (+ optional geography) -> R_A/R_B productivity/decay",
    ],
    "season_period_field": "ClimateEcologyConfig.season_period",
    "season_period_default": 80,
}
