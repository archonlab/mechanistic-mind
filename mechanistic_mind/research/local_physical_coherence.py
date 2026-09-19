"""LOCAL_PHYSICAL_COHERENCE_01 — trajectory wrap audit × passive locality.

Observer / experiment only. No cognition retune. No semantic vision.
Defines local sensory horizon contract (Moore R=1) as scale only.
"""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any, Literal

import numpy as np

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CALIBRATED_TEMPORAL,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.research.world_timescale import wrap_delta

# Predeclared PASSIVE_LOCALITY gates (before measurement). Horizon = 1 cell.
# T_region ≈ 25, T_history ≈ 80.
PASSIVE_LOCALITY_GATES = {
    "G1_SHORT_WAIT_LOCAL": {
        "window": 25,
        "metric": "median_max_excursion",
        "threshold": 0.75,
        "op": "<=",
        "note": "Over T_region, resting WAIT usually sub-cell / local",
    },
    "G2_HISTORY_WAIT_LOCAL": {
        "window": 80,
        "metric": "median_complete_neighborhood_replacements",
        "threshold": 1.0,
        "op": "<=",
        "note": "Over T_history, WAIT usually does not fully replace 3×3",
    },
    "G3_ACTIVE_CONTEXT_CONTROL": {
        "metric": "move_vs_wait_max_excursion_ratio",
        "threshold": 2.0,
        "op": ">=",
        "note": "Controlled MOVE replaces locality more effectively than WAIT",
    },
    "G4_NO_BACKGROUND_CONVEYOR": {
        "window": 800,
        "metric": "median_max_excursion",
        "threshold": 8.0,
        "op": "<=",
        "note": "Background climate must not routinely haul WAIT across many cells",
    },
    "G5_PHYSICAL_DRIFT_RETAINED": {
        "window": 800,
        "metric": "median_path_length",
        "threshold": 0.05,
        "op": ">=",
        "note": "WAIT displacement not forced to exactly zero",
    },
    "G6_KINETIC_CONTINUITY_RETAINED": {
        "metric": "kinetic_wait_path_gt_resting",
        "threshold": True,
        "op": "==",
        "note": "Bodies already moving may continue under WAIT (inertia)",
    },
    "G7_ENVIRONMENTAL_FORCE_RETAINED": {
        "metric": "thermal_or_ambient_measurable",
        "threshold": True,
        "op": "==",
        "note": "Thermal flow / ambient remain measurable",
    },
    "G8_CALIBRATED_WORLD_DYNAMIC": {
        "metric": "climate_dynamic",
        "threshold": True,
        "op": "==",
        "note": "Climate/resources remain dynamic",
    },
}

RESTING_SPEED_THRESHOLD = 0.02
KINETIC_SPEED_THRESHOLD = 0.05

LOCAL_SENSORY_HORIZON = {
    "name": "LOCAL_SENSORY_HORIZON_CONTRACT_V01",
    "moore_radius": 1,
    "neighbor_count": 8,
    "layout": [
        ["NW", "N", "NE"],
        ["W", "X", "E"],
        ["SW", "S", "SE"],
    ],
    "note": (
        "Spatial scale contract only. No semantic perception, terrain GT, "
        "ambient GT, resource GT, or obstacle/food labels exposed to cognition."
    ),
    "own_cell_vs_neighbor": {
        "OWN_CELL_BODY_LOCAL": (
            "Physical quantities already acting on/through the body may be "
            "sensed via existing physical channels where implemented."
        ),
        "NEIGHBOR_CELLS": (
            "Future exteroception must receive only physically observable "
            "signals that can propagate — never direct ground-truth properties."
        ),
        "future_chain": [
            "physical surface/object",
            "observable physical signal",
            "distance attenuation",
            "orientation / field of view",
            "sensor sensitivity",
            "sensory fragment",
            "cognition",
        ],
    },
}


def calibrated_cfg(
    *,
    cognition: bool = False,
    terrain: bool = True,
    ambient: bool = True,
    thermal_flow: bool = True,
) -> PhysicalSystemConfig:
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = bool(cognition)
    cfg.endogenous_motor.mode = "OFF"
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


def moore_neighborhood(cx: int, cy: int, width: int, height: int) -> list[tuple[int, int]]:
    """8-neighbor Moore + center, torus-wrapped cell identities."""
    out: list[tuple[int, int]] = []
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            out.append(((cx + dx) % width, (cy + dy) % height))
    return out


def neighborhood_identity(cx: int, cy: int, width: int, height: int) -> frozenset[tuple[int, int]]:
    return frozenset(moore_neighborhood(cx, cy, width, height))


def local_context_replacement_metrics(
    xs: list[float],
    ys: list[float],
    *,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Geometric Observer metric: how body translation replaces the 3×3 locality."""
    if not xs:
        return {
            "center_cell_changes": 0,
            "complete_neighborhood_replacements": 0,
            "mean_neighbor_retention": 1.0,
            "final_neighbor_retention": 1.0,
        }
    cells = [(int(math.floor(x)) % width, int(math.floor(y)) % height) for x, y in zip(xs, ys)]
    start = cells[0]
    start_nb = neighborhood_identity(start[0], start[1], width, height)
    start_ring = start_nb - {start}
    center_changes = 0
    complete_repl_events = 0
    ticks_full_repl = 0
    retentions: list[float] = []
    prev = cells[0]
    was_full = False
    for c in cells[1:]:
        if c != prev:
            center_changes += 1
        nb = neighborhood_identity(c[0], c[1], width, height)
        ring = nb - {c}
        retained = len(start_ring & ring) / 8.0
        retentions.append(retained)
        full = retained <= 0.0 and c != start
        if full:
            ticks_full_repl += 1
            if not was_full:
                complete_repl_events += 1
        was_full = full
        prev = c
    return {
        "center_cell_changes": int(center_changes),
        "complete_neighborhood_replacements": int(complete_repl_events),
        "ticks_with_full_neighborhood_replacement": int(ticks_full_repl),
        "mean_neighbor_retention": float(np.mean(retentions)) if retentions else 1.0,
        "final_neighbor_retention": float(retentions[-1]) if retentions else 1.0,
        "start_cell": list(start),
        "end_cell": list(cells[-1]),
    }


def trajectory_metrics_extended(
    xs: list[float],
    ys: list[float],
    *,
    width: int,
    height: int,
    speeds: list[float] | None = None,
    actions: list[str] | None = None,
) -> dict[str, Any]:
    """WRAP-aware unique-sample trajectory with locality and action attribution."""
    n = len(xs)
    if n < 1:
        return {"n_samples": 0, "path_length_euclidean": 0.0}
    path = 0.0
    path_man = 0.0
    path_wait = 0.0
    path_move = 0.0
    udx_w = udy_w = udx_m = udy_m = 0.0
    ux = [float(xs[0])]
    uy = [float(ys[0])]
    max_exc = 0.0
    bx = by = 0
    cell_cross = 0
    prev_cell = (int(math.floor(xs[0])) % width, int(math.floor(ys[0])) % height)
    for i in range(1, n):
        raw_dx = float(xs[i]) - float(xs[i - 1])
        raw_dy = float(ys[i]) - float(ys[i - 1])
        dx = wrap_delta(xs[i - 1], xs[i], width)
        dy = wrap_delta(ys[i - 1], ys[i], height)
        if abs(raw_dx - dx) > 1e-12:
            bx += 1
        if abs(raw_dy - dy) > 1e-12:
            by += 1
        step = math.hypot(dx, dy)
        path += step
        path_man += abs(dx) + abs(dy)
        act = actions[i] if actions and i < len(actions) else (actions[i - 1] if actions else None)
        if act == "WAIT":
            path_wait += step
            udx_w += dx
            udy_w += dy
        elif act and str(act).startswith("MOVE"):
            path_move += step
            udx_m += dx
            udy_m += dy
        ux.append(ux[-1] + dx)
        uy.append(uy[-1] + dy)
        exc = math.hypot(ux[-1] - ux[0], uy[-1] - uy[0])
        if exc > max_exc:
            max_exc = exc
        cell = (int(math.floor(xs[i])) % width, int(math.floor(ys[i])) % height)
        if cell != prev_cell:
            cell_cross += 1
            prev_cell = cell
    udx = ux[-1] - ux[0]
    udy = uy[-1] - uy[0]
    cells = {(int(math.floor(x)) % width, int(math.floor(y)) % height) for x, y in zip(xs, ys)}
    sp = [float(s) for s in (speeds or []) if s is not None]
    mean_sp = float(np.mean(sp)) if sp else (path / max(1, n - 1))
    max_sp = float(max(sp)) if sp else 0.0
    speed_path = mean_sp * max(1, n - 1)
    ratio = (path / speed_path) if speed_path > 1e-9 else None
    consistency = "NOT_AVAILABLE"
    if ratio is not None and speed_path > 0.05 and path > 0.05:
        consistency = "FLAG" if (ratio > 3.0 or ratio < 0.25) else "OK"
    loc = local_context_replacement_metrics(xs, ys, width=width, height=height)
    return {
        "n_samples": n,
        "path_length_euclidean": float(path),
        "path_length_manhattan_legacy": float(path_man),
        "unwrapped_dx": float(udx),
        "unwrapped_dy": float(udy),
        "unwrapped_net_displacement": float(math.hypot(udx, udy)),
        "max_excursion_from_start": float(max_exc),
        "bounding_box_unwrapped": [float(min(ux)), float(min(uy)), float(max(ux)), float(max(uy))],
        "unique_cells": len(cells),
        "boundary_crossings_x": int(bx),
        "boundary_crossings_y": int(by),
        "cell_boundary_crossings": int(cell_cross),
        "mean_realized_speed": mean_sp,
        "max_realized_speed": max_sp,
        "path_vs_velocity_consistency": consistency,
        "path_vs_velocity_ratio": float(ratio) if ratio is not None else None,
        "path_during_requested_WAIT": float(path_wait),
        "path_during_requested_MOVE": float(path_move),
        "unwrapped_displacement_during_WAIT": float(math.hypot(udx_w, udy_w)),
        "unwrapped_displacement_during_MOVE": float(math.hypot(udx_m, udy_m)),
        "local_context": loc,
        "start_wrapped": [float(xs[0]), float(ys[0])],
        "end_wrapped": [float(xs[-1]), float(ys[-1])],
    }


def window_excursion_probs(
    xs: list[float],
    ys: list[float],
    *,
    width: int,
    height: int,
    window: int,
    thresholds: tuple[float, ...] = (0.5, 1.0, 2.0, 5.0),
) -> dict[str, Any]:
    """Sliding-window max-excursion probabilities (unique ticks)."""
    n = len(xs)
    if n < 2 or window < 2:
        return {"n_windows": 0}
    max_excs: list[float] = []
    paths: list[float] = []
    nets: list[float] = []
    unique_cells: list[int] = []
    cell_cross: list[int] = []
    nbhd_changes: list[int] = []
    complete_repl: list[int] = []
    step = max(1, window // 4)
    for start in range(0, n - window + 1, step):
        wx = xs[start : start + window]
        wy = ys[start : start + window]
        m = trajectory_metrics_extended(wx, wy, width=width, height=height)
        max_excs.append(float(m["max_excursion_from_start"]))
        paths.append(float(m["path_length_euclidean"]))
        nets.append(float(m["unwrapped_net_displacement"]))
        unique_cells.append(int(m["unique_cells"]))
        cell_cross.append(int(m["cell_boundary_crossings"]))
        loc = m["local_context"]
        nbhd_changes.append(int(loc["center_cell_changes"]))
        complete_repl.append(int(loc["complete_neighborhood_replacements"]))
    out: dict[str, Any] = {
        "window": int(window),
        "n_windows": len(max_excs),
        "path_length": _dist_summary(paths),
        "net_displacement": _dist_summary(nets),
        "max_excursion": _dist_summary(max_excs),
        "unique_cells": _dist_summary([float(x) for x in unique_cells]),
        "cell_boundary_crossings": _dist_summary([float(x) for x in cell_cross]),
        "center_cell_changes": _dist_summary([float(x) for x in nbhd_changes]),
        "complete_neighborhood_replacements": _dist_summary([float(x) for x in complete_repl]),
    }
    for thr in thresholds:
        out[f"P_excursion_gt_{thr}"] = float(np.mean([1.0 if e > thr else 0.0 for e in max_excs])) if max_excs else 0.0
    return out


def _dist_summary(vals: list[float]) -> dict[str, float]:
    if not vals:
        return {"median": 0.0, "min": 0.0, "max": 0.0, "p10": 0.0, "p90": 0.0, "mean": 0.0}
    a = np.asarray(vals, dtype=np.float64)
    return {
        "median": float(np.median(a)),
        "min": float(np.min(a)),
        "max": float(np.max(a)),
        "p10": float(np.percentile(a, 10)),
        "p90": float(np.percentile(a, 90)),
        "mean": float(np.mean(a)),
    }


def run_forced_trace(
    cfg: PhysicalSystemConfig,
    *,
    seed: int,
    ticks: int,
    action: str = "WAIT",
    initial_impulse: tuple[float, float] | None = None,
) -> dict[str, Any]:
    """Controlled forced-action unique-tick trace."""
    rt = PhysicalSystemRuntime(seed=int(seed), config=deepcopy(cfg))
    w = int(rt.config.planet.width)
    h = int(rt.config.planet.height)
    if initial_impulse is not None:
        rt.body.vx = float(initial_impulse[0])
        rt.body.vy = float(initial_impulse[1])
    xs: list[float] = []
    ys: list[float] = []
    speeds: list[float] = []
    actions: list[str] = []
    for _ in range(int(ticks)):
        rt.step_forced_action(action)
        xs.append(float(rt.body.x))
        ys.append(float(rt.body.y))
        speeds.append(math.hypot(float(rt.body.vx), float(rt.body.vy)))
        actions.append(str(action))
    traj = trajectory_metrics_extended(xs, ys, width=w, height=h, speeds=speeds, actions=actions)
    initial_speed = float(speeds[0]) if speeds else 0.0
    wait_class: Literal["RESTING_WAIT", "KINETIC_WAIT", "MOVE", "OTHER"]
    if str(action).startswith("MOVE"):
        wait_class = "MOVE"
    elif action == "WAIT":
        wait_class = "RESTING_WAIT" if initial_speed < RESTING_SPEED_THRESHOLD else "KINETIC_WAIT"
    else:
        wait_class = "OTHER"
    return {
        "seed": int(seed),
        "ticks": int(ticks),
        "action": str(action),
        "wait_class": wait_class,
        "initial_speed": initial_speed,
        "trajectory": traj,
        "xs_end": [float(xs[-1]), float(ys[-1])] if xs else None,
        "windows": {
            str(win): window_excursion_probs(xs, ys, width=w, height=h, window=win)
            for win in (25, 80, 400, 800)
            if ticks >= win
        },
    }


def evaluate_passive_locality_gates(summary: dict[str, Any]) -> dict[str, Any]:
    """Evaluate predeclared G1–G8 against aggregated results."""
    results: dict[str, Any] = {}
    wait = summary.get("resting_wait") or {}
    move = summary.get("controlled_move") or {}
    kinetic = summary.get("kinetic_wait") or {}
    force = summary.get("force_retention") or {}

    def _pass(ok: bool, detail: Any) -> dict[str, Any]:
        return {"pass": bool(ok), "detail": detail}

    # G1
    g1 = ((wait.get("windows") or {}).get("25") or {}).get("max_excursion") or {}
    results["G1_SHORT_WAIT_LOCAL"] = _pass(
        float(g1.get("median", 99)) <= 0.75,
        g1,
    )
    # G2
    g2 = ((wait.get("windows") or {}).get("80") or {}).get("complete_neighborhood_replacements") or {}
    results["G2_HISTORY_WAIT_LOCAL"] = _pass(
        float(g2.get("median", 99)) <= 1.0,
        g2,
    )
    # G3
    w_exc = float((((wait.get("windows") or {}).get("80") or {}).get("max_excursion") or {}).get("median") or 0)
    m_exc = float((((move.get("windows") or {}).get("80") or {}).get("max_excursion") or {}).get("median") or 0)
    ratio = (m_exc / w_exc) if w_exc > 1e-9 else (99.0 if m_exc > 0 else 0.0)
    results["G3_ACTIVE_CONTEXT_CONTROL"] = _pass(ratio >= 2.0, {"ratio": ratio, "move": m_exc, "wait": w_exc})
    # G4
    g4 = ((wait.get("windows") or {}).get("800") or {}).get("max_excursion") or {}
    results["G4_NO_BACKGROUND_CONVEYOR"] = _pass(float(g4.get("median", 99)) <= 8.0, g4)
    # G5
    g5 = float((wait.get("trajectory") or {}).get("path_length_euclidean") or 0)
    results["G5_PHYSICAL_DRIFT_RETAINED"] = _pass(g5 >= 0.05, {"path": g5})
    # G6 — matched-duration kinetic vs resting (inertia retained)
    k_path = float((kinetic.get("trajectory") or {}).get("path_length_euclidean") or 0)
    r_matched = float((kinetic.get("resting_matched_path") or (wait.get("trajectory") or {}).get("path_length_euclidean")) or 0)
    results["G6_KINETIC_CONTINUITY_RETAINED"] = _pass(
        k_path > max(0.01, r_matched * 0.5),
        {"kinetic_path": k_path, "resting_matched_path": r_matched},
    )
    # G7
    results["G7_ENVIRONMENTAL_FORCE_RETAINED"] = _pass(
        bool(force.get("thermal_or_ambient_measurable")),
        force,
    )
    # G8
    results["G8_CALIBRATED_WORLD_DYNAMIC"] = _pass(
        bool(force.get("climate_dynamic")),
        force,
    )
    results["all_pass"] = all(v["pass"] for v in results.values() if isinstance(v, dict) and "pass" in v)
    results["gate_defs"] = PASSIVE_LOCALITY_GATES
    return results
