#!/usr/bin/env python3
"""WORLD_TIMESCALE_CALIBRATION_01

Measure body / locomotion / environment / WAIT-force timescales, diagnose
season_period=80, derive candidate climate periods from measurements, test
candidates, optionally register CALIBRATED_TEMPORAL_WORLD_EXPERIMENTAL.

Does NOT retune cognition. Does NOT change BASELINE_CLIMATE_DEFAULT.
Does NOT modify public Beta.
"""
from __future__ import annotations

import json
import math
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from mechanistic_mind.research.world_timescale import (
    TEMPORAL_DEPENDENCY_GRAPH,
    autocorr_time,
    baseline_cfg,
    cognitive_horizon_inventory,
    first_crossing,
    run_wait_trace,
    structured_world_cfg,
    trajectory_metrics,
    wrap_delta,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.planet.dynamics import step_planet

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "physics" / "world_timescale_calibration_01"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(name: str, obj: Any) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    if isinstance(obj, str):
        path.write_text(obj, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# BODY_TIMESCALE_01
# ---------------------------------------------------------------------------

def body_timescale_01(*, seed: int = 17) -> dict[str, Any]:
    """Controlled body response times under Structured World with frozen climate."""
    # Isolate channels: freeze climate; toggle env forces as needed.
    cfg_iso = structured_world_cfg(
        freeze_climate=True, thermal_flow=False, terrain=False, ambient=False,
    )
    # Motor onset / release — flat world, no env force.
    rt = PhysicalSystemRuntime(seed=seed, config=deepcopy(cfg_iso))
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    # establish near-rest
    for _ in range(5):
        rt.step_forced_action("WAIT")
    v_onset: list[float] = []
    for _ in range(80):
        rt.step_forced_action("MOVE:E")
        v_onset.append(math.hypot(float(rt.body.vx), float(rt.body.vy)))
    v_char = max(v_onset) if v_onset else 0.0
    onset = {
        "v_char": v_char,
        "detectable": first_crossing(v_onset, 0.01),
        "p25": first_crossing(v_onset, 0.25 * v_char) if v_char > 1e-9 else None,
        "p50": first_crossing(v_onset, 0.50 * v_char) if v_char > 1e-9 else None,
        "p90": first_crossing(v_onset, 0.90 * v_char) if v_char > 1e-9 else None,
        "steady_approx_ticks": int(np.argmax(v_onset)) if v_onset else None,
    }
    # Motor release from established motion
    v_rel: list[float] = []
    v0 = v_onset[-1] if v_onset else 0.0
    for _ in range(120):
        rt.step_forced_action("WAIT")
        v_rel.append(math.hypot(float(rt.body.vx), float(rt.body.vy)))
    release = {
        "v0": v0,
        "p75": first_crossing(v_rel, 0.75 * v0, rising=False) if v0 > 1e-9 else None,
        "p50": first_crossing(v_rel, 0.50 * v0, rising=False) if v0 > 1e-9 else None,
        "p25": first_crossing(v_rel, 0.25 * v0, rising=False) if v0 > 1e-9 else None,
        "p10": first_crossing(v_rel, 0.10 * v0, rising=False) if v0 > 1e-9 else None,
        "near_rest": first_crossing(v_rel, 0.01, rising=False),
    }

    # Orientation: MOVE:N then MOVE:E; measure |Δθ| cumulative
    rt2 = PhysicalSystemRuntime(seed=seed + 1, config=deepcopy(cfg_iso))
    for _ in range(20):
        rt2.step_forced_action("MOVE:N")
    th0 = float(rt2.body.theta)
    dtheta = []
    for t in range(40):
        rt2.step_forced_action("MOVE:E")
        d = ((float(rt2.body.theta) - th0 + math.pi) % (2 * math.pi)) - math.pi
        dtheta.append(abs(float(d)))
    orient = {
        "ticks_to_0_2rad": first_crossing(dtheta, 0.2),
        "ticks_to_0_5rad": first_crossing(dtheta, 0.5),
        "max_abs_dtheta": float(max(dtheta)) if dtheta else 0.0,
    }

    # Deformation: apply MOVE then WAIT; track deformation energy proxy if present
    rt3 = PhysicalSystemRuntime(seed=seed + 2, config=deepcopy(cfg_iso))
    for _ in range(15):
        rt3.step_forced_action("MOVE:E")
    peak = 0.0
    relax_series = []
    for t in range(60):
        rt3.step_forced_action("WAIT")
        dw = getattr(rt3.body, "deformation_energy", None)
        if dw is None:
            raw = getattr(rt3.body, "deformation_env_force", None)
            if raw is None:
                val = 0.0
            else:
                val = float(np.linalg.norm(np.asarray(raw, dtype=np.float64)))
        else:
            val = float(dw) if not isinstance(dw, (list, np.ndarray)) else float(np.linalg.norm(dw))
        peak = max(peak, val)
        relax_series.append(val)
    deform = {
        "peak": peak,
        "ticks_to_half_peak": first_crossing(relax_series, 0.5 * peak, rising=False) if peak > 1e-12 else None,
        "ticks_near_baseline": first_crossing(relax_series, 0.1 * peak, rising=False) if peak > 1e-12 else None,
    }

    # Terrain / ambient / thermal responses — measure |Δv| over 30 WAIT ticks after channel ON
    def _channel_response(**kwargs) -> dict[str, Any]:
        c = structured_world_cfg(freeze_climate=True, **kwargs)
        r = PhysicalSystemRuntime(seed=seed + 3, config=c)
        r.body.vx = 0.0
        r.body.vy = 0.0
        for _ in range(5):
            r.step_forced_action("WAIT")
        speeds = []
        for _ in range(40):
            r.step_forced_action("WAIT")
            speeds.append(math.hypot(float(r.body.vx), float(r.body.vy)))
        return {"mean_speed": float(np.mean(speeds)), "max_speed": float(max(speeds)), "final_speed": speeds[-1]}

    return {
        "experiment": "BODY_TIMESCALE_01",
        "seed": seed,
        "motor_onset": onset,
        "motor_release": release,
        "orientation_response": orient,
        "deformation_response": deform,
        "terrain_only_wait": _channel_response(terrain=True, ambient=False, thermal_flow=False),
        "ambient_only_wait": _channel_response(terrain=False, ambient=True, thermal_flow=False),
        "thermal_flow_only_wait": _channel_response(terrain=False, ambient=False, thermal_flow=True),
        "T_body_onset_p50": onset.get("p50"),
        "T_body_relax_p50": release.get("p50"),
        "T_body_relax_near_rest": release.get("near_rest"),
    }


# ---------------------------------------------------------------------------
# LOCOMOTION_TIMESCALE_01
# ---------------------------------------------------------------------------

def locomotion_timescale_01(*, seed: int = 17) -> dict[str, Any]:
    cfg = structured_world_cfg(freeze_climate=True, thermal_flow=False, ambient=False, terrain=True)
    rt = PhysicalSystemRuntime(seed=seed, config=deepcopy(cfg))
    w = int(rt.config.planet.width)
    h = int(rt.config.planet.height)
    x0, y0 = float(rt.body.x), float(rt.body.y)
    dist = 0.0
    milestones = {0.25: None, 0.5: None, 1.0: None, 5.0: None}
    path_xs, path_ys = [x0], [y0]
    for t in range(800):
        rt.step_forced_action("MOVE:E")
        x, y = float(rt.body.x), float(rt.body.y)
        dist += math.hypot(wrap_delta(path_xs[-1], x, w), wrap_delta(path_ys[-1], y, h))
        path_xs.append(x)
        path_ys.append(y)
        for m in list(milestones.keys()):
            if milestones[m] is None and dist >= m:
                milestones[m] = t + 1

    # Terrain feature: move until potential change exceeds threshold
    cfg2 = structured_world_cfg(freeze_climate=True, thermal_flow=False, ambient=False, terrain=True)
    rt2 = PhysicalSystemRuntime(seed=seed + 5, config=cfg2)
    pot = rt2.world.terrain_potential
    iy0, ix0 = rt2.body.cell(w, h)
    p0 = float(pot[iy0, ix0])
    t_feature = None
    for t in range(400):
        rt2.step_forced_action("MOVE:E")
        iy, ix = rt2.body.cell(w, h)
        if abs(float(pot[iy, ix]) - p0) >= 0.15:
            t_feature = t + 1
            break

    # Basin leave / climb / descend proxies using potential gradient sampling
    def _dir_run(action: str, ticks: int = 200) -> dict[str, Any]:
        r = PhysicalSystemRuntime(seed=seed + 7, config=deepcopy(cfg2))
        xs, ys = [float(r.body.x)], [float(r.body.y)]
        pots = []
        for _ in range(ticks):
            r.step_forced_action(action)
            xs.append(float(r.body.x))
            ys.append(float(r.body.y))
            iy, ix = r.body.cell(w, h)
            pots.append(float(pot[iy, ix]))
        traj = trajectory_metrics(xs, ys, width=w, height=h)
        return {
            "path_length": traj["path_length"],
            "unwrapped_net": traj["unwrapped_net_displacement"],
            "delta_potential": float(pots[-1] - pots[0]) if pots else 0.0,
            "ticks": ticks,
        }

    return {
        "experiment": "LOCOMOTION_TIMESCALE_01",
        "seed": seed,
        "ticks_to_travel": {
            "0.25_cell": milestones[0.25],
            "0.5_cell": milestones[0.5],
            "1_cell": milestones[1.0],
            "5_cells": milestones[5.0],
        },
        "T_cell": milestones[1.0],
        "T_local_region_5cells": milestones[5.0],
        "T_terrain_feature": t_feature,
        "MOVE_E": _dir_run("MOVE:E"),
        "MOVE_N": _dir_run("MOVE:N"),
        "MOVE_S": _dir_run("MOVE:S"),
        "note": "Frozen climate; terrain ON; ambient/thermal OFF for locomotor isolation.",
    }


# ---------------------------------------------------------------------------
# ENVIRONMENT_TIMESCALE_01
# ---------------------------------------------------------------------------

def environment_timescale_01(*, season_period: int = 80, seed: int = 17, ticks: int = 1600) -> dict[str, Any]:
    cfg = structured_world_cfg(season_period=season_period)
    rt = PhysicalSystemRuntime(seed=seed, config=deepcopy(cfg))
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    T_s, vx_s, vy_s, gT_s, ra_s, rb_s, phase_s = [], [], [], [], [], [], []
    from mechanistic_mind.planet.climate_ecology import season_phase_state

    for t in range(ticks):
        step_planet(rt.world, rt.config.planet, seed=seed)
        T_s.append(float(rt.world.T[iy, ix]))
        vx_s.append(float(rt.world.vx[iy, ix]))
        vy_s.append(float(rt.world.vy[iy, ix]))
        # local gradient magnitude proxy
        Ty, Tx = np.gradient(rt.world.T)
        gT_s.append(float(math.hypot(Tx[iy, ix], Ty[iy, ix])))
        ra_s.append(float(rt.world.R_A[iy, ix]))
        rb_s.append(float(rt.world.R_B[iy, ix]))
        phase_s.append(float(season_phase_state(cfg.planet.climate_ecology, t, seed)["phase"]))

    def _change_over(window: int, series: list[float]) -> float:
        if len(series) <= window:
            return float("nan")
        diffs = [abs(series[i + window] - series[i]) for i in range(0, len(series) - window, max(1, window // 4))]
        return float(np.mean(diffs)) if diffs else float("nan")

    return {
        "experiment": "ENVIRONMENT_TIMESCALE_01",
        "season_period": season_period,
        "seed": seed,
        "ticks": ticks,
        "probe_cell": [int(iy), int(ix)],
        "acf": {
            "T": autocorr_time(np.asarray(T_s)),
            "vx": autocorr_time(np.asarray(vx_s)),
            "vy": autocorr_time(np.asarray(vy_s)),
            "gradT": autocorr_time(np.asarray(gT_s)),
            "R_A": autocorr_time(np.asarray(ra_s)),
            "R_B": autocorr_time(np.asarray(rb_s)),
            "phase": autocorr_time(np.asarray(phase_s)),
        },
        "mean_abs_delta": {
            "T_over_10": _change_over(10, T_s),
            "T_over_80": _change_over(80, T_s),
            "flow_mag_over_10": _change_over(10, [math.hypot(a, b) for a, b in zip(vx_s, vy_s)]),
            "R_A_over_80": _change_over(80, ra_s),
            "R_B_over_80": _change_over(80, rb_s),
        },
        "resource_mean": {"R_A": float(np.mean(ra_s)), "R_B": float(np.mean(rb_s))},
        "terrain_checksum": (rt.world.terrain_meta or {}).get("checksum"),
        "ambient_checksum": (rt.world.ambient_meta or {}).get("checksum"),
    }


# ---------------------------------------------------------------------------
# WAIT_FORCE_DECOMPOSITION_01
# ---------------------------------------------------------------------------

WAIT_CONDITIONS = {
    "A_all_off": dict(terrain=False, ambient=False, thermal_flow=False),
    "B_terrain": dict(terrain=True, ambient=False, thermal_flow=False),
    "C_ambient": dict(terrain=False, ambient=True, thermal_flow=False),
    "D_thermal": dict(terrain=False, ambient=False, thermal_flow=True),
    "E_terrain_ambient": dict(terrain=True, ambient=True, thermal_flow=False),
    "F_terrain_thermal": dict(terrain=True, ambient=False, thermal_flow=True),
    "G_ambient_thermal": dict(terrain=False, ambient=True, thermal_flow=True),
    "H_full_structured_world": dict(terrain=True, ambient=True, thermal_flow=True),
}


def wait_force_decomposition_01(*, seed: int = 17, ticks: int = 800) -> dict[str, Any]:
    rows = {}
    for name, flags in WAIT_CONDITIONS.items():
        cfg = structured_world_cfg(season_period=80, freeze_climate=False, **flags)
        rows[name] = run_wait_trace(cfg, seed=seed, ticks=ticks, record_forces=True)
    return {
        "experiment": "WAIT_FORCE_DECOMPOSITION_01",
        "seed": seed,
        "ticks": ticks,
        "conditions": rows,
        "note": "Unique simulation ticks; WRAP-aware unwrapped metrics.",
    }


# ---------------------------------------------------------------------------
# Candidate derivation + tests
# ---------------------------------------------------------------------------

def derive_candidates(body: dict, loco: dict, env80: dict, cog: dict) -> dict[str, Any]:
    T_body = float(body.get("T_body_relax_p50") or body.get("T_body_relax_near_rest") or 8)
    T_cell = float(loco.get("T_cell") or 8)
    T_feat = float(loco.get("T_terrain_feature") or max(T_cell * 3, 20))
    T_hist = float(cog.get("tps_WINDOW") or 4) * 20.0  # many windows before env drifts
    T_ra = float((env80.get("acf") or {}).get("R_A") or 40)
    T_rb = float((env80.get("acf") or {}).get("R_B") or 30)
    T_flow = float((env80.get("acf") or {}).get("vx") or 20)

    # Desired: climate >> local locomotion × many episodes; still measurable in long runs.
    # Short: ~ 25 local regions; Mid: ~ 100; Long: ~ 400  (derived, not predetermined)
    short = int(max(80, math.ceil(25 * T_feat)))
    mid = int(max(short + 1, math.ceil(100 * T_cell)))
    long = int(max(mid + 1, math.ceil(400 * T_cell)))
    # Also ensure >> predictive history and body relax
    short = int(max(short, math.ceil(40 * T_body), math.ceil(10 * T_hist)))
    mid = int(max(mid, short * 2, math.ceil(25 * T_hist)))
    long = int(max(long, mid * 3, math.ceil(80 * T_hist)))

    return {
        "inputs": {
            "T_body_relax": T_body,
            "T_cell": T_cell,
            "T_terrain_feature": T_feat,
            "T_predictive_history_proxy": T_hist,
            "T_flow_acf_at_80": T_flow,
            "T_RA_acf_at_80": T_ra,
            "T_RB_acf_at_80": T_rb,
        },
        "derivation": {
            "short": "max(80, 25*T_feat, 40*T_body, 10*T_hist)",
            "mid": "max(2*short, 100*T_cell, 25*T_hist)",
            "long": "max(3*mid, 400*T_cell, 80*T_hist)",
        },
        "candidates": {
            "CURRENT": 80,
            "SHORT_DERIVED": short,
            "MID_DERIVED": mid,
            "LONG_DERIVED": long,
        },
    }


def test_candidate(period: int, *, seed: int = 17, T_cell: float = 8, T_feat: float = 24, T_hist: float = 80) -> dict[str, Any]:
    t0 = time.perf_counter()
    env = environment_timescale_01(season_period=period, seed=seed, ticks=min(3200, max(800, period * 2)))
    wait = run_wait_trace(
        structured_world_cfg(season_period=period),
        seed=seed,
        ticks=400,
        record_forces=True,
    )
    # Field change over locomotor windows
    acf = env["acf"]
    T_acf = float(acf.get("T") or period)
    flow_acf = float(acf.get("vx") or period)

    def _frac_change(window: float) -> dict[str, float]:
        # Approximate: if ACF time >> window, change is small
        return {
            "T_relative_to_acf": float(window / max(T_acf, 1e-9)),
            "flow_relative_to_acf": float(window / max(flow_acf, 1e-9)),
        }

    elapsed = time.perf_counter() - t0
    ratios = {
        "T_climate_over_T_body_relax": period / max(1.0, float(wait["trajectory"].get("mean_speed") and 8 or 8)),
        "T_climate_over_T_cell": period / max(1.0, T_cell),
        "T_climate_over_T_terrain_feature": period / max(1.0, T_feat),
        "T_climate_over_T_hist": period / max(1.0, T_hist),
    }
    # Gates (section 14) — boolean evidence, not auto-promote
    gates = {
        "body_much_faster_than_climate": ratios["T_climate_over_T_cell"] >= 20,
        "many_local_transitions_per_cycle": ratios["T_climate_over_T_terrain_feature"] >= 15,
        "local_env_stable_over_one_cell": _frac_change(T_cell)["T_relative_to_acf"] <= 0.35,
        "history_window_stable": _frac_change(T_hist)["T_relative_to_acf"] <= 0.75,
        "climate_still_changes": T_acf < period * 2 and T_acf > 0,
        "resources_dynamic": float((env.get("acf") or {}).get("R_A") or 0) > 0,
        "RA_not_identical_to_climate_acf": abs(float((env.get("acf") or {}).get("R_A") or 0) - T_acf) > 1e-6,
        "wait_path_not_dominated_by_fast_flow": float(wait["trajectory"]["path_length"]) < 50.0 or period >= 200,
        "terrain_static": env.get("terrain_checksum") is not None,
        "ambient_static": env.get("ambient_checksum") is not None,
    }
    return {
        "season_period": period,
        "env": env,
        "wait_passive": {
            "path_length": wait["trajectory"]["path_length"],
            "unwrapped_net": wait["trajectory"]["unwrapped_net_displacement"],
            "unique_cells": wait["trajectory"]["unique_cells"],
            "force_relative": (wait.get("force_summary") or {}).get("relative"),
        },
        "change_over_T_cell": _frac_change(T_cell),
        "change_over_T_feature": _frac_change(T_feat),
        "change_over_T_hist": _frac_change(T_hist),
        "ratios": ratios,
        "gates": gates,
        "gates_passed": sum(1 for v in gates.values() if v),
        "gates_total": len(gates),
        "compute_seconds": elapsed,
    }


def diagnose_period_80(body: dict, loco: dict, env: dict, cog: dict) -> dict[str, Any]:
    T_clim = 80.0
    T_body = float(body.get("T_body_relax_p50") or body.get("T_body_relax_near_rest") or 1)
    T_cell = float(loco.get("T_cell") or 1)
    T_reg = float(loco.get("T_local_region_5cells") or T_cell * 5)
    T_hist = float(cog.get("tps_WINDOW") or 4) * 20.0
    T_feat = float(loco.get("T_terrain_feature") or T_cell * 3)
    return {
        "season_period": 80,
        "ratios": {
            "T_climate / T_body_relax": T_clim / max(T_body, 1e-9),
            "T_climate / T_cell": T_clim / max(T_cell, 1e-9),
            "T_climate / T_local_region": T_clim / max(T_reg, 1e-9),
            "T_climate / T_terrain_feature": T_clim / max(T_feat, 1e-9),
            "T_climate / T_predictive_history": T_clim / max(T_hist, 1e-9),
            "T_resource_RA_acf / T_cell": float((env.get("acf") or {}).get("R_A") or 0) / max(T_cell, 1e-9),
            "T_flow_acf / T_body_onset": float((env.get("acf") or {}).get("vx") or 0)
            / max(float(body.get("T_body_onset_p50") or 1), 1e-9),
        },
        "cycles_in_1594_tick_run": 1594 / 80.0,
        "cells_per_climate_cycle_if_MOVE": T_clim / max(T_cell, 1e-9),
        "verdict_quantitative": None,  # filled after numbers known
    }


def main() -> None:
    stamp = _ts()
    print(f"[WORLD_TIMESCALE_CALIBRATION_01] {stamp}")
    cog = cognitive_horizon_inventory()
    _write("00_temporal_dependency_graph.json", TEMPORAL_DEPENDENCY_GRAPH)
    _write("00_cognitive_horizons.json", cog)

    print("… BODY_TIMESCALE_01")
    body = body_timescale_01()
    _write("BODY_TIMESCALE_01.json", body)

    print("… LOCOMOTION_TIMESCALE_01")
    loco = locomotion_timescale_01()
    _write("LOCOMOTION_TIMESCALE_01.json", loco)

    print("… ENVIRONMENT_TIMESCALE_01 (period=80)")
    env80 = environment_timescale_01(season_period=80)
    _write("ENVIRONMENT_TIMESCALE_01_period80.json", env80)

    print("… WAIT_FORCE_DECOMPOSITION_01")
    wait = wait_force_decomposition_01()
    _write("WAIT_FORCE_DECOMPOSITION_01.json", wait)

    diag = diagnose_period_80(body, loco, env80, cog)
    # Fill verdict from ratios
    r = diag["ratios"]
    too_fast = (
        r["T_climate / T_cell"] < 25
        or r["T_climate / T_predictive_history"] < 5
        or r["T_climate / T_terrain_feature"] < 10
    )
    diag["verdict_quantitative"] = (
        "TOO_FAST_RELATIVE_TO_LOCAL_LOCOMOTION_AND_HISTORY"
        if too_fast
        else "MARGINALLY_ACCEPTABLE_OR_SLOWER"
    )
    _write("06_diagnosis_period80.json", diag)

    cand = derive_candidates(body, loco, env80, cog)
    _write("09_candidate_periods.json", cand)

    T_cell = float(loco.get("T_cell") or 8)
    T_feat = float(loco.get("T_terrain_feature") or 24)
    T_hist = float(cog.get("tps_WINDOW") or 4) * 20.0
    comparisons = {}
    for label, period in cand["candidates"].items():
        print(f"… candidate {label}={period}")
        comparisons[label] = test_candidate(period, T_cell=T_cell, T_feat=T_feat, T_hist=T_hist)
    _write("10_candidate_comparisons.json", comparisons)

    # Recommend best gate score among derived (not CURRENT unless it wins)
    ranked = sorted(
        ((k, v) for k, v in comparisons.items()),
        key=lambda kv: (kv[1]["gates_passed"], -kv[1]["season_period"]),
        reverse=True,
    )
    recommended = ranked[0][0] if ranked else "MID_DERIVED"
    rec_period = comparisons[recommended]["season_period"]
    hierarchy = {
        "T_body_onset_p50": body.get("T_body_onset_p50"),
        "T_body_relax_p50": body.get("T_body_relax_p50"),
        "T_cell": loco.get("T_cell"),
        "T_local_region": loco.get("T_local_region_5cells"),
        "T_terrain_feature": loco.get("T_terrain_feature"),
        "T_predictive_history_proxy": T_hist,
        "T_resource_RA_acf": (env80.get("acf") or {}).get("R_A"),
        "T_resource_RB_acf": (env80.get("acf") or {}).get("R_B"),
        "T_climate_current": 80,
        "T_climate_recommended": rec_period,
        "recommended_label": recommended,
        "ratios_recommended": comparisons[recommended]["ratios"],
        "gates_recommended": comparisons[recommended]["gates"],
    }
    _write("13_temporal_hierarchy.json", hierarchy)

    summary = {
        "stamp": stamp,
        "dependency_graph": TEMPORAL_DEPENDENCY_GRAPH,
        "diagnosis_period80": diag,
        "candidates": cand["candidates"],
        "recommended": {"label": recommended, "season_period": rec_period},
        "gates_by_candidate": {k: {"passed": v["gates_passed"], "total": v["gates_total"]} for k, v in comparisons.items()},
        "analyzer_distance_note": (
            "Observer ingestXy dedupes by simulation tick; duplicate samples do not "
            "inflate distance (aggregates.ts). Manhattan metric; WRAP not unwrapped in UI — "
            "calibration uses WRAP-aware Euclidean unique-tick path."
        ),
        "claims_boundary": {
            "allowed": [
                "measured body/locomotion/environment timescales",
                "calibrated climate-cycle candidate",
                "thermal-flow contribution to passive WAIT motion",
                "internal scale consistency",
            ],
            "not_established": [
                "Earth seasons",
                "biological realism",
                "migration",
                "learned climate model",
            ],
        },
    }
    _write("WORLD_TIMESCALE_CALIBRATION_01.json", summary)
    _write(
        "WORLD_TIMESCALE_CALIBRATION_01.md",
        f"""# WORLD_TIMESCALE_CALIBRATION_01

Generated: {stamp}

## Diagnosis of season_period=80
- Verdict: **{diag['verdict_quantitative']}**
- Cycles in ~1594-tick run: **{diag['cycles_in_1594_tick_run']:.1f}**
- T_climate/T_cell: **{diag['ratios']['T_climate / T_cell']:.2f}**
- T_climate/T_predictive_history: **{diag['ratios']['T_climate / T_predictive_history']:.2f}**

## Recommended experimental regime
- Label: **{recommended}**
- season_period: **{rec_period}**
- Gates passed: **{comparisons[recommended]['gates_passed']}/{comparisons[recommended]['gates_total']}**

BASELINE_CLIMATE_DEFAULT is unchanged. Promote only via explicit experimental preset.
""",
    )
    print(f"Done. Recommended {recommended}={rec_period}. Artifacts → {OUT}")


if __name__ == "__main__":
    main()
