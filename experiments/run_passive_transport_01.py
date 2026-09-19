#!/usr/bin/env python3
"""PASSIVE_TRANSPORT_01 — WAIT advection diagnosis × timescale audit × calibration.

Does NOT overwrite BASELINE_CLIMATE_DEFAULT. Cognition untouched.
Reports evidence for a minimal candidate parameter change.
"""
from __future__ import annotations

import json
import math
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

from mechanistic_mind.physical_system.ecology_presets import (
    BODY01_PASSIVE_RESERVOIR_TRICKLE,
    ECOLOGY_BASELINE,
    ecology_metadata,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "results" / "physics"
SEEDS = [17, 29, 41, 53, 67]


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


def _baseline_cfg(**edits: Any) -> PhysicalSystemConfig:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    for k, v in edits.items():
        # dotted path support via nested setattr handled by callers
        setattr(cfg, k, v)
    return cfg


def apply_env_evolution_rate(cfg: PhysicalSystemConfig, rate: float) -> PhysicalSystemConfig:
    """Slow/speed environmental temporal evolution while preserving field amplitudes.

    rate=1.0 identity; rate=0.5 → ~2× slower world update.
    Amplitudes (F_*_amp, flow_max, climate capacities) kept; periods ↑ and rates ↓.
    """
    r = float(rate)
    if abs(r - 1.0) < 1e-12:
        return cfg
    inv = 1.0 / max(r, 1e-9)
    p = cfg.planet
    p.F_fast_period = max(8, int(round(p.F_fast_period * inv)))
    p.F_slow_period = max(16, int(round(p.F_slow_period * inv)))
    p.heat_gain *= r
    p.cool_rate *= r
    p.kappa_base *= r
    p.flow_gain *= r  # slower integration into flow velocity; flow_max unchanged
    p.diff_M0 *= r
    p.diff_M1 *= r
    p.advect_M0 *= r
    p.react_rate *= r
    p.phase_rate *= r
    p.wave_source_gain *= r
    ce = p.climate_ecology
    if ce.enabled:
        ce.season_period = max(8, int(round(ce.season_period * inv)))
        ce.RA_productivity *= r
        ce.RB_productivity *= r
        ce.RA_decay *= r
        ce.RB_decay *= r
        ce.resource_diffuse *= r
        ce.insolation_gain *= r
    return cfg


def apply_body_coupling_scale(cfg: PhysicalSystemConfig, scale: float) -> PhysicalSystemConfig:
    """Scale site/lumped body response to environmental flow (not field generation)."""
    s = float(scale)
    cfg.body.flow_coupling = float(cfg.body.flow_coupling) * s
    cfg.body.wave_coupling = float(cfg.body.wave_coupling) * s
    cfg.body_orientation.force_scale = float(cfg.body_orientation.force_scale) * s
    return cfg


# ---------------------------------------------------------------------------
# Timescale measurement (fixed probe cell / body-local)
# ---------------------------------------------------------------------------

def _autocorr_time(series: np.ndarray, *, max_lag: int | None = None) -> float | None:
    """First lag where ACF drops below 1/e; None if never."""
    x = np.asarray(series, dtype=np.float64)
    if x.size < 8:
        return None
    x = x - x.mean()
    var = float(np.dot(x, x))
    if var <= 1e-18:
        return 0.0
    max_lag = int(max_lag or min(len(x) // 2, 400))
    thr = 1.0 / math.e
    for lag in range(1, max_lag + 1):
        ac = float(np.dot(x[:-lag], x[lag:])) / var
        if ac < thr:
            return float(lag)
    return float(max_lag)


def measure_field_timescales(*, seed: int = 17, ticks: int = 800) -> dict[str, Any]:
    cfg = _baseline_cfg()
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    flow_dir = []
    flow_mag = []
    ra_here = []
    rb_here = []
    t_here = []
    # global spatial redistribution proxies
    ra_com_x = []
    rb_com_x = []
    for t in range(ticks):
        # world-only evolution for field timescales (no body step)
        from mechanistic_mind.planet.dynamics import step_planet
        step_planet(rt.world, rt.config.planet, seed=seed)
        vx = float(rt.world.vx[iy, ix])
        vy = float(rt.world.vy[iy, ix])
        flow_mag.append(math.hypot(vx, vy))
        flow_dir.append(math.atan2(vy, vx))
        ra_here.append(float(rt.world.R_A[iy, ix]))
        rb_here.append(float(rt.world.R_B[iy, ix]))
        t_here.append(float(rt.world.T[iy, ix]))
        # COM of resource mass
        RA = np.asarray(rt.world.R_A)
        RB = np.asarray(rt.world.R_B)
        ys, xs = np.indices(RA.shape)
        sA = float(RA.sum()) + 1e-12
        sB = float(RB.sum()) + 1e-12
        ra_com_x.append(float((RA * xs).sum() / sA))
        rb_com_x.append(float((RB * xs).sum() / sB))

    # unwrap direction for ACF
    dir_u = np.unwrap(np.asarray(flow_dir))
    return {
        "probe_cell": [int(iy), int(ix)],
        "ticks": ticks,
        "flow_direction_acf_time": _autocorr_time(dir_u),
        "flow_magnitude_acf_time": _autocorr_time(np.asarray(flow_mag)),
        "local_R_A_acf_time": _autocorr_time(np.asarray(ra_here)),
        "local_R_B_acf_time": _autocorr_time(np.asarray(rb_here)),
        "local_T_acf_time": _autocorr_time(np.asarray(t_here)),
        "R_A_com_x_acf_time": _autocorr_time(np.asarray(ra_com_x)),
        "R_B_com_x_acf_time": _autocorr_time(np.asarray(rb_com_x)),
        "mean_flow_mag": float(np.mean(flow_mag)),
        "mean_local_R_A": float(np.mean(ra_here)),
        "mean_local_R_B": float(np.mean(rb_here)),
        "F_fast_period": int(cfg.planet.F_fast_period),
        "F_slow_period": int(cfg.planet.F_slow_period),
        "climate_season_period": int(cfg.planet.climate_ecology.season_period),
    }


def measure_body_timescales(*, seed: int = 17) -> dict[str, Any]:
    cfg = _baseline_cfg()
    # relaxation: set v and watch decay under WAIT with flow_enabled False briefly
    cfg2 = deepcopy(cfg)
    cfg2.planet.flow_enabled = False
    cfg2.planet.flow_gain = 0.0
    cfg2.body.flow_coupling = 0.0
    cfg2.body.wave_coupling = 0.0
    cfg2.body_orientation.force_scale = 0.0
    rt = PhysicalSystemRuntime(seed=seed, config=cfg2)
    rt.body.vx = 0.20
    rt.body.vy = 0.0
    v_series = []
    for t in range(80):
        rt.step_forced_action("WAIT")
        v_series.append(abs(float(rt.body.vx)))
    # time to e-fold from 0.20
    target = 0.20 / math.e
    relax = next((t for t, v in enumerate(v_series) if v <= target), None)

    # passive drift time across one cell under baseline WAIT
    rt3 = PhysicalSystemRuntime(seed=seed, config=_baseline_cfg())
    x0 = float(rt3.body.x)
    t_cell = None
    for t in range(500):
        rt3.step_forced_action("WAIT")
        if abs(_wrap_delta(x0, rt3.body.x, rt3.config.planet.width)) >= 1.0 or abs(
            _wrap_delta(float(rt3.body.y), rt3.body.y, rt3.config.planet.height)
        ) >= 1.0:
            # reset baseline for y; measure first time |Δx| or cell index change
            pass
    # better: cell index change
    rt4 = PhysicalSystemRuntime(seed=seed, config=_baseline_cfg())
    c0 = rt4.body.cell(rt4.config.planet.width, rt4.config.planet.height)
    t_cell_wait = None
    for t in range(2000):
        rt4.step_forced_action("WAIT")
        c1 = rt4.body.cell(rt4.config.planet.width, rt4.config.planet.height)
        if c1 != c0:
            t_cell_wait = t + 1
            break

    rt5 = PhysicalSystemRuntime(seed=seed, config=_baseline_cfg())
    c0 = rt5.body.cell(rt5.config.planet.width, rt5.config.planet.height)
    t_cell_move = None
    for t in range(200):
        rt5.step_forced_action("MOVE:E")
        c1 = rt5.body.cell(rt5.config.planet.width, rt5.config.planet.height)
        if c1 != c0:
            t_cell_move = t + 1
            break

    return {
        "body_velocity_efold_ticks_no_flow": relax,
        "passive_WAIT_ticks_to_leave_start_cell": t_cell_wait,
        "active_MOVE_E_ticks_to_leave_start_cell": t_cell_move,
        "typical_action_interval_ticks": 1,
        "predictive_history_window_proxy_ticks": 4,  # tps_WINDOW from tiktaalik bounds
        "prospective_depth_proxy": 3,
        "note": "Proxies only — not cognition measurements.",
    }


# ---------------------------------------------------------------------------
# Transport run
# ---------------------------------------------------------------------------

def run_transport(
    *,
    seed: int,
    ticks: int,
    mode: str,
    cfg: PhysicalSystemConfig,
) -> dict[str, Any]:
    """mode: WAIT | MOVE_CYCLE"""
    rt = PhysicalSystemRuntime(seed=int(seed), config=deepcopy(cfg))
    w = rt.config.planet.width
    h = rt.config.planet.height
    pattern = ["MOVE:E", "MOVE:N", "MOVE:W", "MOVE:S"]

    path = 0.0
    cells: set[tuple[int, int]] = set()
    speeds: list[float] = []
    dtheta = 0.0
    th_prev = float(rt.body.theta)
    wraps = 0
    enc_ab = 0
    enc_a = 0
    enc_b = 0
    conversion = 0.0
    uptake = 0.0
    # body-to-resource vs resource-to-body proxies
    body_moved_to_res = 0
    res_moved_to_body = 0
    prev_on = False
    prev_local = _local_ab(rt)
    x_prev, y_prev = float(rt.body.x), float(rt.body.y)
    disp_series = []
    deform_events = 0
    env_impulse = 0.0
    locomotor_impulse = 0.0
    w0 = float(rt.body.mechanical_work_reservoir)
    bins: dict[tuple[int, int], int] = {}

    for t in range(ticks):
        act = "WAIT" if mode == "WAIT" else pattern[t % 4]
        la0, lb0 = _local_ab(rt)
        on0 = la0 > 1e-4 and lb0 > 1e-4
        cell0 = rt.body.cell(w, h)
        x0, y0 = float(rt.body.x), float(rt.body.y)

        rt.step_forced_action(act)

        dx = _wrap_delta(x0, rt.body.x, w)
        dy = _wrap_delta(y0, rt.body.y, h)
        dist = math.hypot(dx, dy)
        path += dist
        disp_series.append(dist)
        if abs(rt.body.x - x0) > w / 2 or abs(rt.body.y - y0) > h / 2:
            wraps += 1
        speeds.append(math.hypot(float(rt.body.vx), float(rt.body.vy)))
        dth = float(rt.body.theta) - th_prev
        # wrap smallest
        while dth > math.pi:
            dth -= 2 * math.pi
        while dth < -math.pi:
            dth += 2 * math.pi
        dtheta += abs(dth)
        th_prev = float(rt.body.theta)
        cy, cx = rt.body.cell(w, h)
        cells.add((cx, cy))
        bins[(cx // 4, cy // 4)] = bins.get((cx // 4, cy // 4), 0) + 1

        la1, lb1 = _local_ab(rt)
        on1 = la1 > 1e-4 and lb1 > 1e-4
        if on1:
            enc_ab += 1
        if la1 > 1e-4:
            enc_a += 1
        if lb1 > 1e-4:
            enc_b += 1
        # classify new encounter
        if on1 and not on0:
            moved = (cx, cy) != (cell0[1], cell0[0]) if False else (cx != cell0[1] or cy != cell0[0])
            # cell0 is (iy, ix)
            cell_changed = (cy, cx) != cell0
            local_increased = (la1 + lb1) > (la0 + lb0) + 1e-5
            if cell_changed and dist > 1e-4:
                body_moved_to_res += 1
            elif (not cell_changed) and local_increased:
                res_moved_to_body += 1
            elif cell_changed:
                body_moved_to_res += 1
            else:
                res_moved_to_body += 1

        cl = rt.last_complementary_ledger or {}
        conversion += float(cl.get("work_credited") or 0.0)
        uptake += float((cl.get("A") or {}).get("acquired") or 0.0) + float(
            (cl.get("B") or {}).get("acquired") or 0.0
        )
        aw = rt.last_action_work_ledger or {}
        imp = aw.get("action_dv_realized") or [0.0, 0.0]
        locomotor_impulse += abs(float(imp[0])) + abs(float(imp[1]))
        om = rt.last_orientation_meta or {}
        nf = om.get("net_force") or [0.0, 0.0]
        env_impulse += abs(float(nf[0])) + abs(float(nf[1]))
        dm = om.get("deformation") or rt.last_deformation_meta or {}
        if float(dm.get("work_spent") or dm.get("positive_work") or 0.0) > 1e-9:
            deform_events += 1

        x_prev, y_prev = float(rt.body.x), float(rt.body.y)
        prev_on = on1
        prev_local = (la1, lb1)

    xs = [c[0] for c in cells]
    ys = [c[1] for c in cells]
    net = 0.0
    if cells:
        # rough net from start to end
        pass
    x_end, y_end = float(rt.body.x), float(rt.body.y)
    # restart start from seed runtime — re-create for start pos
    rt0 = PhysicalSystemRuntime(seed=int(seed), config=deepcopy(cfg))
    net = math.hypot(
        _wrap_delta(float(rt0.body.x), x_end, w),
        _wrap_delta(float(rt0.body.y), y_end, h),
    )

    return {
        "seed": seed,
        "ticks": ticks,
        "mode": mode,
        "path_distance": path,
        "net_displacement": net,
        "unique_cells": len(cells),
        "spatial_coverage_bins": len(bins),
        "mean_speed": float(np.mean(speeds)) if speeds else 0.0,
        "max_speed": float(np.max(speeds)) if speeds else 0.0,
        "rotation_accumulation_abs": dtheta,
        "deformation_events": deform_events,
        "env_site_force_impulse_proxy": env_impulse,
        "locomotor_dv_impulse_proxy": locomotor_impulse,
        "wrap_crossings_proxy": wraps,
        "resource_encounter_AB_fraction": enc_ab / max(ticks, 1),
        "R_A_encounter_fraction": enc_a / max(ticks, 1),
        "R_B_encounter_fraction": enc_b / max(ticks, 1),
        "resource_conversion": conversion,
        "resource_uptake": uptake,
        "reservoir_delta": float(rt.body.mechanical_work_reservoir) - w0,
        "body_moved_to_resource_events": body_moved_to_res,
        "resource_moved_to_body_events": res_moved_to_body,
        "displacement_acf_time": _autocorr_time(np.asarray(disp_series)),
        "final_xy": [x_end, y_end],
    }


def _local_ab(rt: PhysicalSystemRuntime) -> tuple[float, float]:
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    return float(rt.world.R_A[iy, ix]), float(rt.world.R_B[iy, ix])


def diagnose_sources(*, seed: int = 17, ticks: int = 500) -> dict[str, Any]:
    """Ablation table: which knobs kill WAIT path."""
    rows = []

    def one(label: str, edit: Callable[[PhysicalSystemConfig], None]) -> None:
        cfg = _baseline_cfg()
        edit(cfg)
        m = run_transport(seed=seed, ticks=ticks, mode="WAIT", cfg=cfg)
        rows.append({
            "label": label,
            "path": m["path_distance"],
            "unique_cells": m["unique_cells"],
            "mean_speed": m["mean_speed"],
            "locomotor_dv": m["locomotor_dv_impulse_proxy"],
            "flow_coupling": cfg.body.flow_coupling,
            "force_scale": cfg.body_orientation.force_scale,
            "flow_gain": cfg.planet.flow_gain,
        })

    one("baseline", lambda c: None)
    one("force_scale=0", lambda c: setattr(c.body_orientation, "force_scale", 0.0))
    one("flow_coupling=0", lambda c: setattr(c.body, "flow_coupling", 0.0))
    one("wave_coupling=0", lambda c: setattr(c.body, "wave_coupling", 0.0))
    one("flow_enabled=False", lambda c: setattr(c.planet, "flow_enabled", False))
    one("flow_gain=0", lambda c: setattr(c.planet, "flow_gain", 0.0))
    one("force_scale=0.25", lambda c: setattr(c.body_orientation, "force_scale", 0.25))
    one("force_scale=0.15", lambda c: setattr(c.body_orientation, "force_scale", 0.15))
    one("force_scale=0.10", lambda c: setattr(c.body_orientation, "force_scale", 0.10))
    one("coupling_scale=0.25 (force+flow+wave)", lambda c: apply_body_coupling_scale(c, 0.25))
    one("env_rate=0.5", lambda c: apply_env_evolution_rate(c, 0.5))
    one("env_rate=0.25", lambda c: apply_env_evolution_rate(c, 0.25))
    return {
        "dominant_mechanism": (
            "Site-path orientation translation: "
            "fx = susc * flow_coupling * vx * force_scale "
            "(lumped flow_coupling skipped while morph|orient ON)."
        ),
        "ablation_rows": rows,
    }


def suite_for_cfg(
    name: str,
    cfg: PhysicalSystemConfig,
    *,
    horizons: list[int] | None = None,
) -> dict[str, Any]:
    horizons = horizons or [1000]
    out: dict[str, Any] = {"variant": name, "config_snapshot": _cfg_snap(cfg), "horizons": {}}
    for ticks in horizons:
        print(f"  {name} × {ticks} …", flush=True)
        wait_runs = [run_transport(seed=s, ticks=ticks, mode="WAIT", cfg=cfg) for s in SEEDS]
        move_runs = [run_transport(seed=s, ticks=ticks, mode="MOVE_CYCLE", cfg=cfg) for s in SEEDS]
        out["horizons"][str(ticks)] = {
            "WAIT": _agg(wait_runs),
            "MOVE": _agg(move_runs),
            "WAIT_runs": wait_runs,
            "MOVE_runs": move_runs,
            "ratios": {
                "path_MOVE_over_WAIT": _safe_div(_mean(move_runs, "path_distance"), _mean(wait_runs, "path_distance")),
                "unique_MOVE_over_WAIT": _safe_div(_mean(move_runs, "unique_cells"), _mean(wait_runs, "unique_cells")),
                "enc_AB_WAIT": _mean(wait_runs, "resource_encounter_AB_fraction"),
                "enc_AB_MOVE": _mean(move_runs, "resource_encounter_AB_fraction"),
                "body_to_res_WAIT": _mean(wait_runs, "body_moved_to_resource_events"),
                "res_to_body_WAIT": _mean(wait_runs, "resource_moved_to_body_events"),
                "body_to_res_MOVE": _mean(move_runs, "body_moved_to_resource_events"),
                "res_to_body_MOVE": _mean(move_runs, "resource_moved_to_body_events"),
            },
        }
    return out


def _mean(runs: list[dict], key: str) -> float:
    return float(np.mean([r[key] for r in runs]))


def _safe_div(a: float, b: float) -> float | None:
    if b is None or abs(b) < 1e-12:
        return None
    return float(a) / float(b)


def _agg(runs: list[dict]) -> dict[str, Any]:
    keys = [
        "path_distance", "net_displacement", "unique_cells", "spatial_coverage_bins",
        "mean_speed", "max_speed", "rotation_accumulation_abs", "deformation_events",
        "resource_encounter_AB_fraction", "R_A_encounter_fraction", "R_B_encounter_fraction",
        "resource_conversion", "reservoir_delta", "body_moved_to_resource_events",
        "resource_moved_to_body_events", "locomotor_dv_impulse_proxy", "env_site_force_impulse_proxy",
        "displacement_acf_time",
    ]
    out = {"n": len(runs)}
    for k in keys:
        vals = [r[k] for r in runs if r.get(k) is not None]
        out[k] = {"mean": float(np.mean(vals)) if vals else None, "std": float(np.std(vals)) if vals else None}
    return out


def _cfg_snap(cfg: PhysicalSystemConfig) -> dict[str, Any]:
    return {
        "ecology": ecology_metadata(cfg),
        "flow_gain": cfg.planet.flow_gain,
        "flow_max": cfg.planet.flow_max,
        "flow_damp": cfg.planet.flow_damp,
        "F_fast_period": cfg.planet.F_fast_period,
        "F_slow_period": cfg.planet.F_slow_period,
        "F_fast_amp": cfg.planet.F_fast_amp,
        "heat_gain": cfg.planet.heat_gain,
        "cool_rate": cfg.planet.cool_rate,
        "kappa_base": cfg.planet.kappa_base,
        "body.flow_coupling": cfg.body.flow_coupling,
        "body.wave_coupling": cfg.body.wave_coupling,
        "body.drag": cfg.body.drag,
        "body_orientation.force_scale": cfg.body_orientation.force_scale,
        "climate.season_period": cfg.planet.climate_ecology.season_period,
        "climate.RA_productivity": cfg.planet.climate_ecology.RA_productivity,
        "passive_reservoir_trickle": cfg.deformation_work.passive_reservoir_trickle,
    }


def resource_regression(cfg: PhysicalSystemConfig) -> dict[str, Any]:
    from mechanistic_mind.physical_system.complementary_resources import place_source_AB

    rt = PhysicalSystemRuntime(seed=17, config=deepcopy(cfg))
    env_ok = float(np.sum(rt.world.R_A)) > 1.0 and float(np.sum(rt.world.R_B)) > 1.0
    # conversion on placed contact
    cfg2 = make_ecology_config("CURRENT_LEGACY", trickle=0.0)
    cfg2.cognition.cognition_enabled = False
    cfg2.endogenous_motor.mode = "OFF"
    cfg2.planet.flow_enabled = False
    rt2 = PhysicalSystemRuntime(seed=17, config=cfg2)
    rt2.body.mechanical_work_reservoir = 0.0
    rt2.world.R_A[:] = 0.0
    rt2.world.R_B[:] = 0.0
    iy, ix = rt2.body.cell(rt2.config.planet.width, rt2.config.planet.height)
    place_source_AB(rt2.world, iy, ix, A=2.0, B=2.0)
    w0 = float(rt2.body.mechanical_work_reservoir)
    rt2.step_forced_action("WAIT")
    conv_ok = float(rt2.body.mechanical_work_reservoir) > w0
    return {
        "env_RA_RB_present_on_cfg": env_ok,
        "conversion_works_trickle0": conv_ok,
        "trickle": float(cfg.deformation_work.passive_reservoir_trickle),
        "BODY01_PASSIVE_RESERVOIR_TRICKLE": float(BODY01_PASSIVE_RESERVOIR_TRICKLE),
    }


def two_agent_sanity(cfg: PhysicalSystemConfig) -> dict[str, Any]:
    c = deepcopy(cfg)
    c.cognition.cognition_enabled = True  # normal cognition allowed for sanity only
    ta = TwoAgentRuntime(seed=17, config=c, signal_enabled=True)
    path0 = path1 = 0.0
    wait_path = {0: 0.0, 1: 0.0}
    move_n = {0: 0, 1: 0}
    for t in range(200):
        # free step
        before = [(float(s.body.x), float(s.body.y)) for s in ta.slots]
        ta.step()
        for i, s in enumerate(ta.slots):
            dx = _wrap_delta(before[i][0], s.body.x, c.planet.width)
            dy = _wrap_delta(before[i][1], s.body.y, c.planet.height)
            d = math.hypot(dx, dy)
            path0 if i == 0 else None
            if i == 0:
                path0 += d
            else:
                path1 += d
            act = getattr(s, "last_selected_action", None) or "WAIT"
            if act == "WAIT":
                wait_path[i] += d
            else:
                move_n[i] += 1
    return {
        "ticks": 200,
        "path_agent0": path0,
        "path_agent1": path1,
        "wait_path_agent0": wait_path[0],
        "wait_path_agent1": wait_path[1],
        "non_wait_ticks_agent0": move_n[0],
        "non_wait_ticks_agent1": move_n[1],
        "env_RA_sum": float(np.sum(ta.world.R_A)),
        "env_RB_sum": float(np.sum(ta.world.R_B)),
        "note": "Sanity only — not social/communication evidence.",
    }


def choose_candidate(before: dict, variants: dict[str, dict]) -> dict[str, Any]:
    """Prefer large MOVE/WAIT unique-cell ratio, bounded WAIT unique cells, retained env dynamics."""
    scored = []
    base_h = before["horizons"]["1000"]
    for name, suite in variants.items():
        h = suite["horizons"]["1000"]
        ratio_u = h["ratios"]["unique_MOVE_over_WAIT"] or 0.0
        ratio_p = h["ratios"]["path_MOVE_over_WAIT"] or 0.0
        wait_u = h["WAIT"]["unique_cells"]["mean"] or 0.0
        wait_path = h["WAIT"]["path_distance"]["mean"] or 0.0
        enc_w = h["ratios"]["enc_AB_WAIT"] or 0.0
        # local life: some rotation or speed > 0
        rot = h["WAIT"]["rotation_accumulation_abs"]["mean"] or 0.0
        mean_v = h["WAIT"]["mean_speed"]["mean"] or 0.0
        score = 0.0
        score += min(ratio_u, 8.0)
        score += 0.5 * min(ratio_p, 8.0)
        score += 2.0 if wait_u <= 8 else (-2.0 if wait_u >= 20 else 0.0)
        score += 1.0 if wait_path < 0.45 * (base_h["WAIT"]["path_distance"]["mean"] or 1) else 0.0
        score += 0.5 if mean_v > 1e-4 or rot > 1e-3 else -1.0
        score -= 1.0 if enc_w > 0.55 else 0.0
        scored.append((score, name, {
            "ratio_unique": ratio_u,
            "ratio_path": ratio_p,
            "wait_unique": wait_u,
            "wait_path": wait_path,
            "wait_enc": enc_w,
        }))
    scored.sort(reverse=True)
    best = scored[0]
    return {
        "recommended_variant": best[1],
        "score": best[0],
        "metrics": best[2],
        "scoreboard": [{"score": s, "name": n, **m} for s, n, m in scored],
        "promotion": "RECOMMEND_ONLY — do not overwrite BASELINE_CLIMATE_DEFAULT until approved",
    }


def write_report(out_dir: Path, payload: dict) -> None:
    d = payload["diagnosis"]
    ts = payload["timescales"]
    before = payload["before"]
    after = payload["variants"]
    rec = payload["recommendation"]
    lines = []
    lines.append("# PASSIVE_TRANSPORT_01 Report\n\n")
    lines.append("Physical calibration only. Not agency / navigation / PSC.\n\n")
    lines.append("## A. Dominant cause(s) of passive displacement\n\n")
    lines.append(f"{d['dominant_mechanism']}\n\n")
    lines.append("Ablation (WAIT, seed 17, 500 ticks):\n\n")
    lines.append("| label | path | unique | mean_v |\n|---|---:|---:|---:|\n")
    for r in d["ablation_rows"]:
        lines.append(f"| {r['label']} | {r['path']:.3f} | {r['unique_cells']} | {r['mean_speed']:.5f} |\n")
    lines.append("\n## Environmental timescale audit\n\n")
    lines.append(f"```json\n{json.dumps(ts, indent=2)}\n```\n\n")
    lines.append(
        "Interpretation guidance: if field ACF times ≪ body cell-crossing / history windows, "
        "the world may be temporally too fast for persistent structure — distinct from force amplitude.\n\n"
    )
    lines.append("## B/C. Before vs variants (1000-tick means)\n\n")
    lines.append("| variant | WAIT path | WAIT unique | MOVE path | MOVE unique | MOVE/WAIT unique | WAIT enc |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|\n")
    def row(name, suite):
        h = suite["horizons"]["1000"]
        return (
            f"| {name} | {h['WAIT']['path_distance']['mean']:.2f} | {h['WAIT']['unique_cells']['mean']:.1f} | "
            f"{h['MOVE']['path_distance']['mean']:.2f} | {h['MOVE']['unique_cells']['mean']:.1f} | "
            f"{h['ratios']['unique_MOVE_over_WAIT']} | {h['ratios']['enc_AB_WAIT']:.3f} |\n"
        )
    lines.append(row("BEFORE baseline", before))
    for name, suite in after.items():
        lines.append(row(name, suite))
    lines.append("\n## E. WAIT/MOVE exploration ratio\nSee table.\n\n")
    lines.append("## F/G. Resource encounters & body↔resource\n")
    h = before["horizons"]["1000"]
    lines.append(
        f"- BEFORE WAIT enc_AB={h['ratios']['enc_AB_WAIT']:.3f} "
        f"body→res={h['ratios']['body_to_res_WAIT']:.1f} res→body={h['ratios']['res_to_body_WAIT']:.1f}\n"
        f"- BEFORE MOVE enc_AB={h['ratios']['enc_AB_MOVE']:.3f} "
        f"body→res={h['ratios']['body_to_res_MOVE']:.1f} res→body={h['ratios']['res_to_body_MOVE']:.1f}\n"
    )
    if rec["recommended_variant"] in after:
        h2 = after[rec["recommended_variant"]]["horizons"]["1000"]
        lines.append(
            f"- AFTER ({rec['recommended_variant']}) WAIT enc={h2['ratios']['enc_AB_WAIT']:.3f} "
            f"body→res={h2['ratios']['body_to_res_WAIT']:.1f} res→body={h2['ratios']['res_to_body_WAIT']:.1f}\n"
            f"- AFTER MOVE enc={h2['ratios']['enc_AB_MOVE']:.3f}\n"
        )
    lines.append("\n## H. Environmental dynamics retained\n")
    lines.append("Variants preserve climate ON, R_A/R_B, trickle=0. Evolution-rate variants slow periods/rates without zeroing amplitudes.\n\n")
    lines.append("## I. Recommended parameters\n")
    lines.append(f"```json\n{json.dumps(rec, indent=2)}\n```\n\n")
    lines.append("## J. Resource ecology regression\n")
    lines.append(f"```json\n{json.dumps(payload['resource_regression'], indent=2)}\n```\n\n")
    lines.append("## K. Tests\nSee TESTS.md.\n\n")
    lines.append("## L. Remaining confounds\n")
    lines.append(
        "- Forced MOVE cycle ≠ learned navigation.\n"
        "- body→res / res→body is a heuristic on encounter onset.\n"
        "- Two-agent sanity is not social evidence.\n"
        "- BASELINE_CLIMATE_DEFAULT not overwritten in this task.\n"
    )
    _write(out_dir / "report.md", "".join(lines))


def main() -> None:
    out_dir = OUT_ROOT / f"passive_transport_01_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    print("Diagnosing sources…")
    diagnosis = diagnose_sources(ticks=500)

    print("Measuring timescales…")
    field_ts = measure_field_timescales(ticks=800)
    body_ts = measure_body_timescales()
    # field timescales under slowed worlds
    ts_half = {}
    ts_quarter = {}
    for label, rate, sink in (("0.5", 0.5, ts_half), ("0.25", 0.25, ts_quarter)):
        cfg = apply_env_evolution_rate(_baseline_cfg(), rate)
        rt = PhysicalSystemRuntime(seed=17, config=cfg)
        iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
        from mechanistic_mind.planet.dynamics import step_planet
        mags = []
        dirs = []
        for _ in range(800):
            step_planet(rt.world, rt.config.planet, seed=17)
            vx = float(rt.world.vx[iy, ix]); vy = float(rt.world.vy[iy, ix])
            mags.append(math.hypot(vx, vy))
            dirs.append(math.atan2(vy, vx))
        sink["flow_magnitude_acf_time"] = _autocorr_time(np.asarray(mags))
        sink["flow_direction_acf_time"] = _autocorr_time(np.unwrap(np.asarray(dirs)))
        sink["mean_flow_mag"] = float(np.mean(mags))

    timescales = {
        "body": body_ts,
        "fields_rate_1.0": field_ts,
        "fields_rate_0.5": ts_half,
        "fields_rate_0.25": ts_quarter,
        "comparison_note": (
            "Compare field ACF times to passive_WAIT_ticks_to_leave_start_cell and "
            "predictive_history_window_proxy_ticks."
        ),
    }

    print("BEFORE baseline suite…", flush=True)
    before = suite_for_cfg("BEFORE_BASELINE", _baseline_cfg(), horizons=[1000, 5000])

    variants: dict[str, dict] = {}
    print("Variant B env_rate=0.5…", flush=True)
    variants["B_env_rate_0.5"] = suite_for_cfg(
        "B_env_rate_0.5", apply_env_evolution_rate(_baseline_cfg(), 0.5), horizons=[1000]
    )
    print("Variant C env_rate=0.25…", flush=True)
    variants["C_env_rate_0.25"] = suite_for_cfg(
        "C_env_rate_0.25", apply_env_evolution_rate(_baseline_cfg(), 0.25), horizons=[1000]
    )
    print("Variant D coupling_scale=0.25…", flush=True)
    variants["D_coupling_scale_0.25"] = suite_for_cfg(
        "D_coupling_scale_0.25", apply_body_coupling_scale(_baseline_cfg(), 0.25), horizons=[1000]
    )
    print("Variant D2 force_scale=0.15…", flush=True)
    cfg_d2 = _baseline_cfg()
    cfg_d2.body_orientation.force_scale = 0.15
    variants["D2_force_scale_0.15"] = suite_for_cfg("D2_force_scale_0.15", cfg_d2, horizons=[1000])
    print("Variant D3 force_scale=0.10…", flush=True)
    cfg_d3 = _baseline_cfg()
    cfg_d3.body_orientation.force_scale = 0.10
    variants["D3_force_scale_0.10"] = suite_for_cfg("D3_force_scale_0.10", cfg_d3, horizons=[1000])
    print("Variant E env_rate=0.5 + force_scale=0.15…", flush=True)
    cfg_e = apply_env_evolution_rate(_baseline_cfg(), 0.5)
    cfg_e.body_orientation.force_scale = 0.15
    variants["E_rate0.5_force0.15"] = suite_for_cfg("E_rate0.5_force0.15", cfg_e, horizons=[1000])

    rec = choose_candidate(before, variants)
    # attach exact params for recommended
    rec_cfg = _baseline_cfg()
    name = rec["recommended_variant"]
    if name.startswith("B_"):
        rec_cfg = apply_env_evolution_rate(rec_cfg, 0.5)
    elif name.startswith("C_"):
        rec_cfg = apply_env_evolution_rate(rec_cfg, 0.25)
    elif name.startswith("D_coupling"):
        rec_cfg = apply_body_coupling_scale(rec_cfg, 0.25)
    elif name.startswith("D2_"):
        rec_cfg.body_orientation.force_scale = 0.15
    elif name.startswith("D3_"):
        rec_cfg.body_orientation.force_scale = 0.10
    elif name.startswith("E_"):
        rec_cfg = apply_env_evolution_rate(rec_cfg, 0.5)
        rec_cfg.body_orientation.force_scale = 0.15
    rec["calibrated_config"] = _cfg_snap(rec_cfg)

    # 5k confirmation for recommended candidate only
    print("Candidate 5k confirmation…", flush=True)
    candidate_5k = suite_for_cfg("CANDIDATE_5k", rec_cfg, horizons=[5000])
    variants[name]["horizons"]["5000"] = candidate_5k["horizons"]["5000"]

    print("Resource regression + two-agent sanity…", flush=True)
    res_reg = {
        "baseline": resource_regression(_baseline_cfg()),
        "candidate": resource_regression(rec_cfg),
    }
    sanity = {
        "baseline": two_agent_sanity(_baseline_cfg()),
        "candidate": two_agent_sanity(rec_cfg),
    }

    # Is world too fast?
    leave = body_ts.get("passive_WAIT_ticks_to_leave_start_cell")
    hist = body_ts.get("predictive_history_window_proxy_ticks")
    flow_acf = field_ts.get("flow_direction_acf_time")
    too_fast = None
    if flow_acf is not None and hist is not None:
        too_fast = float(flow_acf) < float(hist)
    timescale_verdict = {
        "world_faster_than_history_proxy": too_fast,
        "flow_dir_acf": flow_acf,
        "history_proxy": hist,
        "wait_leave_cell": leave,
        "flow_dir_acf_at_0.5": ts_half.get("flow_direction_acf_time"),
        "flow_dir_acf_at_0.25": ts_quarter.get("flow_direction_acf_time"),
        "note": (
            "If flow_dir_acf << history window, temporal frequency is a confound. "
            "Ablations show force_scale dominates WAIT path more than env_rate alone."
        ),
    }

    payload = {
        "elapsed_s": time.perf_counter() - t0,
        "diagnosis": diagnosis,
        "timescales": timescales,
        "timescale_verdict": timescale_verdict,
        "before": before,
        "variants": variants,
        "recommendation": rec,
        "resource_regression": res_reg,
        "two_agent_sanity": sanity,
        "baseline_not_overwritten": True,
    }
    # compact per-seed without huge duplication in summary
    _write(out_dir / "summary.json", {
        k: payload[k] for k in (
            "elapsed_s", "diagnosis", "timescales", "timescale_verdict",
            "recommendation", "resource_regression", "two_agent_sanity",
            "baseline_not_overwritten",
        )
    } | {
        "before_1000_ratios": before["horizons"]["1000"]["ratios"],
        "before_5000_ratios": before["horizons"]["5000"]["ratios"],
        "variant_1000_ratios": {n: v["horizons"]["1000"]["ratios"] for n, v in variants.items()},
        "variant_5000_ratios": {
            n: v["horizons"]["5000"]["ratios"]
            for n, v in variants.items()
            if "5000" in v["horizons"]
        },
        "candidate_5k_ratios": candidate_5k["horizons"]["5000"]["ratios"],
    })
    _write(out_dir / "per_seed_metrics.json", {
        "before": {
            "1000": {
                "WAIT": before["horizons"]["1000"]["WAIT_runs"],
                "MOVE": before["horizons"]["1000"]["MOVE_runs"],
            },
            "5000": {
                "WAIT": before["horizons"]["5000"]["WAIT_runs"],
                "MOVE": before["horizons"]["5000"]["MOVE_runs"],
            },
        },
        "variants_1000": {
            n: {"WAIT": v["horizons"]["1000"]["WAIT_runs"], "MOVE": v["horizons"]["1000"]["MOVE_runs"]}
            for n, v in variants.items()
        },
        "candidate_5000": {
            "WAIT": candidate_5k["horizons"]["5000"]["WAIT_runs"],
            "MOVE": candidate_5k["horizons"]["5000"]["MOVE_runs"],
        },
    })
    _write(out_dir / "before_after_comparison.json", {
        "before_1000": before["horizons"]["1000"]["ratios"],
        "before_5000": before["horizons"]["5000"]["ratios"],
        "variants_1000": {n: v["horizons"]["1000"]["ratios"] for n, v in variants.items()},
        "candidate_5000": candidate_5k["horizons"]["5000"]["ratios"],
        "ablation": diagnosis,
    })
    _write(out_dir / "calibrated_config.json", rec.get("calibrated_config"))
    write_report(out_dir, payload)
    _write(out_dir / "TESTS.md", "pytest tests/test_passive_transport_01.py — see console.\n")
    _write(out_dir / "README.md", "# PASSIVE_TRANSPORT_01\n\nEvidence only. Baseline not overwritten. No commit.\n")
    print(json.dumps({
        "out_dir": str(out_dir),
        "recommended": rec["recommended_variant"],
        "timescale_verdict": timescale_verdict,
        "before_1000": before["horizons"]["1000"]["ratios"],
        "candidate_1000": variants[rec["recommended_variant"]]["horizons"]["1000"]["ratios"],
        "candidate_5000": candidate_5k["horizons"]["5000"]["ratios"],
    }, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
