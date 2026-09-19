"""Locomotion ecology audit + ACTION AUTHORITY (physical, not psychological).

Scripted ordinary Tiktaalik bodies; cognition off. Measures how strongly
requested MOVE predicts realized displacement under a given ecology preset.
"""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

import numpy as np

from mechanistic_mind.physical_system.actions import action_direction
from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CURRENT,
    ECOLOGY_GENTLE,
    apply_ecology_preset,
    make_ecology_config,
    parameter_diff,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.ui.psy_observer_web.geometry.metrics import (
    ALIGN_REVERSE,
    ALIGN_SUCCESS,
    EPS_DISP,
    action_alignment,
)

MOVE_ACTIONS = ("MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W")


def _wrap_delta(a: float, b: float, size: int) -> float:
    """Shortest signed displacement on WRAP_PERIODIC torus."""
    d = float(b) - float(a)
    half = size / 2.0
    if d > half:
        d -= size
    elif d < -half:
        d += size
    return d


def _scripted_runtime(
    *,
    seed: int,
    preset: str,
    start_x: float,
    start_y: float,
    signal_enabled: bool = False,
) -> PhysicalSystemRuntime:
    cfg = make_ecology_config(preset)
    cfg.cognition.cognition_enabled = False
    if signal_enabled:
        from mechanistic_mind.physical_system.physical_signal import PhysicalSignalConfig
        cfg.physical_signal = PhysicalSignalConfig(mode="EXPERIMENTAL")
    cfg.body.start_x = int(start_x) % int(cfg.planet.width)
    cfg.body.start_y = int(start_y) % int(cfg.planet.height)
    rt = PhysicalSystemRuntime(seed=int(seed), config=cfg)
    rt.body.x = float(start_x)
    rt.body.y = float(start_y)
    return rt


def run_move_trials(
    *,
    preset: str,
    seeds: list[int],
    starts: list[tuple[float, float]],
    ticks_per_trial: int = 8,
) -> list[dict[str, Any]]:
    """Forced MOVE trials; ordinary physics realizes displacement."""
    rows = []
    for seed in seeds:
        for sx, sy in starts:
            for action in MOVE_ACTIONS:
                rt = _scripted_runtime(seed=seed, preset=preset, start_x=sx, start_y=sy)
                w, h = int(rt.config.planet.width), int(rt.config.planet.height)
                x0, y0 = float(rt.body.x), float(rt.body.y)
                work_limited = 0
                for _ in range(int(ticks_per_trial)):
                    rt._forced_action_once = action
                    rt.step()
                    al = rt.last_action_work_ledger or {}
                    if al.get("work_limited") or al.get("action_work_limited"):
                        work_limited += 1
                dx = _wrap_delta(x0, rt.body.x, w)
                dy = _wrap_delta(y0, rt.body.y, h)
                align = action_alignment(action, dx, dy)
                mag = math.hypot(dx, dy)
                rows.append({
                    "preset": preset,
                    "seed": int(seed),
                    "start": [sx, sy],
                    "action": action,
                    "dx": dx,
                    "dy": dy,
                    "disp_mag": mag,
                    "alignment": align,
                    "work_limited_ticks": work_limited,
                    "ticks": int(ticks_per_trial),
                })
    return rows


def run_wait_trials(
    *,
    preset: str,
    seeds: list[int],
    starts: list[tuple[float, float]],
    ticks_per_trial: int = 20,
) -> list[dict[str, Any]]:
    rows = []
    for seed in seeds:
        for sx, sy in starts:
            rt = _scripted_runtime(seed=seed, preset=preset, start_x=sx, start_y=sy)
            w, h = int(rt.config.planet.width), int(rt.config.planet.height)
            x0, y0 = float(rt.body.x), float(rt.body.y)
            for _ in range(int(ticks_per_trial)):
                rt._forced_action_once = "WAIT"
                rt.step()
            dx = _wrap_delta(x0, rt.body.x, w)
            dy = _wrap_delta(y0, rt.body.y, h)
            rows.append({
                "preset": preset,
                "seed": int(seed),
                "start": [sx, sy],
                "action": "WAIT",
                "dx": dx,
                "dy": dy,
                "disp_mag": math.hypot(dx, dy),
                "ticks": int(ticks_per_trial),
            })
    return rows


def run_coverage_trial(
    *,
    preset: str,
    seed: int = 17,
    start: tuple[float, float] = (8.0, 16.0),
    horizon: int = 400,
) -> dict[str, Any]:
    """Scripted exploration: hold each MOVE direction for a block of ticks."""
    rt = _scripted_runtime(seed=seed, preset=preset, start_x=start[0], start_y=start[1])
    w, h = int(rt.config.planet.width), int(rt.config.planet.height)
    cells: set[tuple[int, int]] = set()
    seq = list(MOVE_ACTIONS)
    block = 25  # persist direction so coverage reflects action authority, not thrash
    for i in range(int(horizon)):
        rt._forced_action_once = seq[(i // block) % len(seq)]
        rt.step()
        cells.add((int(rt.body.x) % w, int(rt.body.y) % h))
    # Cardinal reach: net cells traveled under sustained MOVE:E
    rt2 = _scripted_runtime(seed=seed, preset=preset, start_x=start[0], start_y=start[1])
    x0 = float(rt2.body.x)
    for _ in range(80):
        rt2._forced_action_once = "MOVE:E"
        rt2.step()
    east = abs(_wrap_delta(x0, rt2.body.x, w))
    y0 = float(rt2.body.y)
    for _ in range(80):
        rt2._forced_action_once = "MOVE:N"
        rt2.step()
    north = abs(_wrap_delta(y0, rt2.body.y, h))
    return {
        "preset": preset,
        "seed": seed,
        "horizon": horizon,
        "unique_cells": len(cells),
        "map_cells": w * h,
        "coverage_frac": len(cells) / max(1, w * h),
        "sustained_east_disp": east,
        "sustained_north_disp": north,
        "sustained_reach_score": east + north,
    }


def summarize_action_authority(
    move_rows: list[dict[str, Any]],
    wait_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Physical ACTION AUTHORITY summary — not agency / free will / intention."""
    aligns = [r["alignment"] for r in move_rows if r.get("alignment") is not None]
    mags = [float(r["disp_mag"]) for r in move_rows]
    wait_mags = [float(r["disp_mag"]) for r in wait_rows]
    opposing = sum(1 for a in aligns if a is not None and a <= ALIGN_REVERSE)
    strong_defl = sum(1 for a in aligns if a is not None and a <= -0.7)
    success = sum(1 for a in aligns if a is not None and a >= ALIGN_SUCCESS)
    work_lim = sum(int(r.get("work_limited_ticks") or 0) for r in move_rows)
    n = max(1, len(aligns))
    median_align = float(np.median(aligns)) if aligns else None
    mean_align = float(np.mean(aligns)) if aligns else None
    wait_median = float(np.median(wait_mags)) if wait_mags else None
    wait_mean = float(np.mean(wait_mags)) if wait_mags else None
    opposing_rate = opposing / n
    strong_rate = strong_defl / n
    # Compact coupling label from physical thresholds (not psychological)
    if (
        median_align is not None
        and median_align >= 0.75
        and opposing_rate < 0.05
        and (wait_median is None or wait_median < 0.5)
    ):
        coupling = "HIGH PHYSICAL COUPLING"
    elif median_align is not None and median_align >= 0.5:
        coupling = "MODERATE PHYSICAL COUPLING"
    else:
        coupling = "LOW PHYSICAL COUPLING"
    return {
        "metric": "ACTION_AUTHORITY",
        "note": (
            "Physical locomotion coupling: requested MOVE → realized displacement. "
            "Not agency, free will, intention, autonomy, or comfort."
        ),
        "n_move_trials": len(move_rows),
        "n_wait_trials": len(wait_rows),
        "move_alignment_median": median_align,
        "move_alignment_mean": mean_align,
        "move_success_rate": success / n,
        "opposing_rate": opposing_rate,
        "strong_deflection_rate": strong_rate,
        "move_disp_median": float(np.median(mags)) if mags else None,
        "wait_disp_median": wait_median,
        "wait_disp_mean": wait_mean,
        "work_limited_tick_total": work_lim,
        "work_limited_per_trial": work_lim / max(1, len(move_rows)),
        "coupling_label": coupling,
        "thresholds": {
            "ALIGN_SUCCESS": ALIGN_SUCCESS,
            "ALIGN_REVERSE": ALIGN_REVERSE,
            "target_median_align": 0.75,
            "target_opposing": 0.05,
        },
    }


def compare_presets(
    *,
    seeds: list[int] | None = None,
    starts: list[tuple[float, float]] | None = None,
    move_ticks: int = 8,
    wait_ticks: int = 20,
) -> dict[str, Any]:
    seeds = seeds or [17, 31, 43, 101, 211]
    starts = starts or [
        (8.0, 16.0), (16.0, 16.0), (24.0, 8.0), (4.0, 24.0), (20.0, 20.0),
    ]
    out: dict[str, Any] = {"seeds": seeds, "starts": starts, "presets": {}}
    for preset in (ECOLOGY_CURRENT, ECOLOGY_GENTLE):
        move = run_move_trials(
            preset=preset, seeds=seeds, starts=starts, ticks_per_trial=move_ticks,
        )
        wait = run_wait_trials(
            preset=preset, seeds=seeds, starts=starts, ticks_per_trial=wait_ticks,
        )
        cov = run_coverage_trial(preset=preset, seed=seeds[0], start=starts[0])
        auth = summarize_action_authority(move, wait)
        out["presets"][preset] = {
            "action_authority": auth,
            "coverage": cov,
            "n_move": len(move),
            "n_wait": len(wait),
        }
        out[f"move_rows_{preset}"] = move
        out[f"wait_rows_{preset}"] = wait

    cur = out["presets"][ECOLOGY_CURRENT]["action_authority"]
    gen = out["presets"][ECOLOGY_GENTLE]["action_authority"]

    def _f(d: dict, key: str, default: float) -> float:
        v = d.get(key)
        return float(default if v is None else v)

    out["comparison"] = {
        "MOVE_ALIGNMENT_IMPROVED": (
            _f(gen, "move_alignment_median", -1) > _f(cur, "move_alignment_median", -1)
        ),
        "PASSIVE_DRIFT_REDUCED": (
            _f(gen, "wait_disp_median", 1e9) < _f(cur, "wait_disp_median", 0)
        ),
        "STRONG_DEFLECTION_REDUCED": (
            _f(gen, "strong_deflection_rate", 1) < _f(cur, "strong_deflection_rate", 0)
        ),
        "OPPOSING_REDUCED": (
            _f(gen, "opposing_rate", 1) < _f(cur, "opposing_rate", 0)
        ),
        "OPPOSING_NOT_WORSE": (
            _f(gen, "opposing_rate", 1) <= _f(cur, "opposing_rate", 0) + 1e-12
        ),
        "BROAD_TRAVERSABILITY_SUPPORTED": (
            float(out["presets"][ECOLOGY_GENTLE]["coverage"].get("sustained_east_disp") or 0) >= 4.0
            or float(out["presets"][ECOLOGY_GENTLE]["coverage"]["coverage_frac"]) >= 0.08
        ),
        "ACTION_AUTHORITY_INCREASED": (
            _f(gen, "move_alignment_median", -1)
            >= _f(cur, "move_alignment_median", -1) - 1e-6
            and _f(gen, "wait_disp_median", 1e9) < _f(cur, "wait_disp_median", 0)
            and _f(gen, "opposing_rate", 1) <= _f(cur, "opposing_rate", 0) + 1e-12
        ),
        "gentle_targets": {
            "median_align_gt_0_75": _f(gen, "move_alignment_median", 0) > 0.75,
            "opposing_lt_0_05": _f(gen, "opposing_rate", 1) < 0.05,
            "wait_drift_lt_half_current": (
                _f(gen, "wait_disp_median", 1e9) < 0.5 * max(1e-9, _f(cur, "wait_disp_median", 1))
            ),
        },
    }
    cur_cfg = make_ecology_config(ECOLOGY_CURRENT)
    gen_cfg = make_ecology_config(ECOLOGY_GENTLE)
    out["parameter_diff"] = parameter_diff(cur_cfg, gen_cfg)
    return out


def assert_mechanisms_active(preset: str = ECOLOGY_GENTLE) -> dict[str, Any]:
    """Sanity: gentle world keeps ordinary mechanisms enabled."""
    cfg = make_ecology_config(preset)
    return {
        "deformation_enabled": bool(cfg.body_deformation.enabled),
        "deformation_work_enabled": bool(cfg.deformation_work.enabled),
        "orientation_enabled": bool(cfg.body_orientation.enabled),
        "morphology_enabled": bool(cfg.morphology_mechanics.enabled),
        "action_work_enabled": bool(cfg.discrete_action_work.enabled),
        "endo_motor_enabled": bool(cfg.endogenous_motor.mode.upper() != "OFF"),
        "cognition_unchanged_default": bool(cfg.cognition.cognition_enabled),
        "ecology_preset": cfg.ecology_preset,
    }


def determinism_check(preset: str = ECOLOGY_GENTLE, seed: int = 17) -> dict[str, Any]:
    def _trace():
        rt = _scripted_runtime(seed=seed, preset=preset, start_x=10.0, start_y=12.0)
        path = []
        for i, act in enumerate(["MOVE:E", "WAIT", "MOVE:N", "MOVE:W", "MOVE:S"] * 4):
            rt._forced_action_once = act
            rt.step()
            path.append((round(float(rt.body.x), 6), round(float(rt.body.y), 6), act))
        return path

    a, b = _trace(), _trace()
    return {
        "preset": preset,
        "seed": seed,
        "identical": a == b,
        "n_steps": len(a),
    }


def audit_no_ecology_in_observation(preset: str = ECOLOGY_GENTLE) -> dict[str, Any]:
    rt = _scripted_runtime(seed=17, preset=preset, start_x=8.0, start_y=8.0)
    rt.step()
    obs = rt.agent_observation()
    blob = str(obs).lower()
    needles = (
        "ecology_preset", "gentle", "free_movement", "action_authority",
        "traversability", "harsh", "current physical",
    )
    hits = [n for n in needles if n in blob]
    return {"leaks": hits, "held": len(hits) == 0, "obs_keys": list(obs.keys()) if isinstance(obs, dict) else None}
