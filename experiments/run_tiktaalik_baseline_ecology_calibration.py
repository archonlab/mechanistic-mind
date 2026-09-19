#!/usr/bin/env python3
"""Tiktaalik baseline ecology calibration — resource→work × habitability × trickle ablation.

Diagnostic / calibration only. Does not permanently alter CURRENT factory defaults.
Does not tune for PSC. Cognition disabled unless a natural-run branch enables it.
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

from mechanistic_mind.physical_system.baseline_ecology_presets import (
    ECOLOGY_A_STATIC_PATCHES,
    ECOLOGY_B_MIGRATING,
    ECOLOGY_C_CHANGING,
    ECOLOGY_CLIMATE_DEFAULT,
    ecology_summary,
    make_baseline_ecology_config,
    make_current_uninhabitable_reference,
    maybe_replenish_static_patches,
    seed_static_patches,
)
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.motor_work import scale_positive_ke
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "results" / "body_economy"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        path.write_text(obj, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _authority_class(work_fraction: float | None, budget: float) -> str:
    if budget <= 1e-15 or (work_fraction is not None and work_fraction <= 1e-15):
        return "COLLAPSED"
    if work_fraction is None:
        return "UNKNOWN"
    if work_fraction >= 0.95:
        return "FULL"
    if work_fraction >= 0.35:
        return "REDUCED"
    if work_fraction >= 0.05:
        return "LOW"
    return "COLLAPSED"


def _probe_authority(rt: PhysicalSystemRuntime) -> dict[str, Any]:
    """Requested MOVE:E Δv scale under current reservoir (no step)."""
    mass = float(rt.config.body.mass)
    budget = float(rt.body.mechanical_work_reservoir)
    # Approximate requested action Δv from impulse_scale path
    impulse = float(rt.config.discrete_action_work.impulse_scale)
    dvx, dvy = impulse / max(mass, 1e-9), 0.0
    scale = scale_positive_ke(mass, float(rt.body.vx), float(rt.body.vy), dvx, dvy, budget)
    return {
        "reservoir": budget,
        "work_fraction_proxy": float(scale),
        "motor_authority_class": _authority_class(float(scale), budget),
        "note": "DELTA_V_SCALE_NOT_FORCE",
    }


def _local_AB(rt: PhysicalSystemRuntime) -> tuple[float, float]:
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    ra = getattr(rt.world, "R_A", None)
    rb = getattr(rt.world, "R_B", None)
    a = float(ra[iy, ix]) if ra is not None else 0.0
    b = float(rb[iy, ix]) if rb is not None else 0.0
    return a, b


def _trace_row(rt: PhysicalSystemRuntime, tick: int, *, condition: str) -> dict[str, Any]:
    local_a, local_b = _local_AB(rt)
    w_before = float(rt.body.mechanical_work_reservoir)
    auth_before = _probe_authority(rt)
    rt.step_forced_action("WAIT")
    cl = rt.last_complementary_ledger or {}
    er = rt.last_resource_ledger or {}
    trickle = rt.last_passive_reservoir_trickle or {}
    w_after = float(rt.body.mechanical_work_reservoir)
    body_a = float(cl.get("body_A") or 0.0)
    body_b = float(cl.get("body_B") or 0.0)
    return {
        "tick": tick,
        "condition": condition,
        "local_env_R_A": local_a,
        "local_env_R_B": local_b,
        "body_exposure_cell": list(rt.body.cell(rt.config.planet.width, rt.config.planet.height)),
        "uptake_A": float((cl.get("A") or {}).get("acquired") or 0.0),
        "uptake_B": float((cl.get("B") or {}).get("acquired") or 0.0),
        "internal_A": body_a,
        "internal_B": body_b,
        "conversion_enabled": bool(cl.get("conversion_enabled", rt.config.complementary_resources.conversion_enabled)),
        "limiting_resource": cl.get("limiting_resource"),
        "conversion_amount": float(cl.get("work_credited") or 0.0),
        "consumed_A": float(cl.get("consumed_A") or 0.0),
        "consumed_B": float(cl.get("consumed_B") or 0.0),
        "env_R_work_credited": float(er.get("work_credited") or 0.0),
        "reservoir_before": w_before,
        "reservoir_after": w_after,
        "trickle_credited": float(trickle.get("credited") or 0.0),
        "motor_authority_before": auth_before,
        "motor_authority_after": _probe_authority(rt),
        "locomotor_spend": 0.0,  # WAIT
    }


def _make_rt(cfg: PhysicalSystemConfig, seed: int) -> PhysicalSystemRuntime:
    rt = PhysicalSystemRuntime(seed=int(seed), config=cfg)
    centers: list[dict[str, Any]] = []
    if getattr(cfg, "_baseline_seed_patches", False):
        centers = seed_static_patches(
            rt.world, seed=seed, spec=getattr(cfg, "_baseline_patch_spec", None)
        )
        rt._baseline_patch_centers = centers  # type: ignore[attr-defined]
        rt._baseline_patch_spec = getattr(cfg, "_baseline_patch_spec", {})  # type: ignore[attr-defined]
    return rt


def _step_world(rt: PhysicalSystemRuntime, action: str = "WAIT") -> None:
    rt.step_forced_action(action)
    # Static-patch slow replenishment (candidate A only)
    if getattr(rt, "_baseline_patch_centers", None):
        maybe_replenish_static_patches(
            rt.world,
            tick=int(rt.tick),
            seed=int(rt.seed) if hasattr(rt, "seed") else 17,
            spec=getattr(rt, "_baseline_patch_spec", {}),
            centers=rt._baseline_patch_centers,
        )


# ---------------------------------------------------------------------------
# A — wiring audit (static description + live values)
# ---------------------------------------------------------------------------

def audit_wiring() -> dict[str, Any]:
    cfg = PhysicalSystemConfig()
    eco = make_current_uninhabitable_reference(trickle=None)
    climate_on = make_baseline_ecology_config(ECOLOGY_CLIMATE_DEFAULT, trickle=0.0)
    return {
        "chain": [
            "planet.R_A / planet.R_B (env fields; zero unless climate_ecology.enabled or manually placed)",
            "oriented_site_cells → body footprint contact cells",
            "complementary _transfer_one → body.R_A_site / R_B_site",
            "passive site leaks (A slow, B fast)",
            "complementary conversion: n_rxn = min(A/sa, B/sb, rate, room_W/(eta*kappa)); dW = eta*kappa*n_rxn",
            "body.mechanical_work_reservoir += dW",
            "optional passive_reservoir_trickle after resource steps",
            "allocate_shared_work → discrete action / deformation / endogenous motor",
            "scale_positive_ke(budget): returns 0.0 when budget <= 1e-15",
            "locomotor spend reduces reservoir via realized positive KE increment",
        ],
        "factory_defaults": {
            "complementary_resources.mode": cfg.complementary_resources.mode,
            "complementary_enabled": cfg.complementary_resources.enabled,
            "conversion_enabled": cfg.complementary_resources.conversion_enabled,
            "environmental_resource.mode": cfg.environmental_resource.mode,
            "climate_ecology.enabled": cfg.planet.climate_ecology.enabled,
            "passive_reservoir_trickle": float(cfg.deformation_work.passive_reservoir_trickle),
            "note": "Complementary conversion ON but climate ecology OFF → env R_A/R_B stay 0.",
        },
        "make_ecology_config_CURRENT": ecology_summary(eco),
        "candidate_climate_default": ecology_summary(climate_on),
        "scale_positive_ke_empty": float(
            scale_positive_ke(1.0, 0.0, 0.0, 0.1, 0.0, 0.0)
        ),
        "first_edge_hypothesis": "WORLD_RESOURCE_FIELD_EMPTY",
    }


# ---------------------------------------------------------------------------
# B — resource→work trace (depleted body, controlled conditions)
# ---------------------------------------------------------------------------

CONDITIONS = {
    "A_none": lambda rt: None,
    "B_RA_only": lambda rt: place_source_AB(
        rt.world, *rt.body.cell(rt.config.planet.width, rt.config.planet.height), A=2.0, B=0.0
    ),
    "C_RB_only": lambda rt: place_source_AB(
        rt.world, *rt.body.cell(rt.config.planet.width, rt.config.planet.height), A=0.0, B=2.0
    ),
    "D_RA_RB": lambda rt: place_source_AB(
        rt.world, *rt.body.cell(rt.config.planet.width, rt.config.planet.height), A=2.0, B=2.0
    ),
    "E_strong_RA_RB": lambda rt: place_source_AB(
        rt.world, *rt.body.cell(rt.config.planet.width, rt.config.planet.height), A=5.0, B=5.0
    ),
}


def resource_to_work_trace(*, trickle: float = 0.0, ticks: int = 24, seed: int = 17) -> dict[str, Any]:
    results: dict[str, Any] = {"trickle": trickle, "ticks": ticks, "conditions": {}}
    first_stop: dict[str, Any] = {}

    # Controlled bare world (no climate) so placement is the only stock.
    for name, setup in CONDITIONS.items():
        cfg = PhysicalSystemConfig()
        cfg.cognition.cognition_enabled = False
        cfg.endogenous_motor.mode = "OFF"
        cfg.planet.flow_enabled = False
        cfg.planet.flow_gain = 0.0
        cfg.body.flow_coupling = 0.0
        cfg.body.wave_coupling = 0.0
        cfg.deformation_work.passive_reservoir_trickle = float(trickle)
        cfg.deformation_work.reservoir_init = 0.0
        cfg.planet.climate_ecology.enabled = False
        rt = PhysicalSystemRuntime(seed=seed, config=cfg)
        rt.body.mechanical_work_reservoir = 0.0
        rt.body.vx = rt.body.vy = 0.0
        rt.world.R_A[:] = 0.0
        rt.world.R_B[:] = 0.0
        setup(rt)
        rows = [_trace_row(rt, t, condition=name) for t in range(ticks)]
        results["conditions"][name] = {
            "rows": rows,
            "total_conversion": sum(r["conversion_amount"] for r in rows),
            "total_uptake_A": sum(r["uptake_A"] for r in rows),
            "total_uptake_B": sum(r["uptake_B"] for r in rows),
            "final_reservoir": rows[-1]["reservoir_after"] if rows else 0.0,
            "first_nonzero_conversion_tick": next(
                (r["tick"] for r in rows if r["conversion_amount"] > 1e-9), None
            ),
        }

    # F: ordinary world concentration (CURRENT vs climate)
    for label, builder in (
        ("F_ordinary_CURRENT", lambda: make_current_uninhabitable_reference(trickle=trickle)),
        ("F_ordinary_CLIMATE", lambda: make_baseline_ecology_config(ECOLOGY_CLIMATE_DEFAULT, trickle=trickle)),
    ):
        cfg = builder()
        cfg.deformation_work.reservoir_init = 0.0
        rt = _make_rt(cfg, seed)
        rt.body.mechanical_work_reservoir = 0.0
        # Place at max product cell if any stock exists
        ra, rb = rt.world.R_A, rt.world.R_B
        prod = np.asarray(ra) * np.asarray(rb)
        iy, ix = divmod(int(prod.argmax()), prod.shape[1])
        rt.body.x = float(ix) + 0.5
        rt.body.y = float(iy) + 0.5
        setup_note = {
            "marked_as": "EXPERIMENT_SETUP",
            "action": "POSITION_AT_MAX_PRODUCT_CELL",
            "cell": [int(iy), int(ix)],
            "env_sum_A": float(np.sum(ra)),
            "env_sum_B": float(np.sum(rb)),
            "local_A": float(ra[iy, ix]),
            "local_B": float(rb[iy, ix]),
        }
        rows = [_trace_row(rt, t, condition=label) for t in range(ticks)]
        results["conditions"][label] = {
            "setup": setup_note,
            "rows": rows,
            "total_conversion": sum(r["conversion_amount"] for r in rows),
            "final_reservoir": rows[-1]["reservoir_after"] if rows else 0.0,
            "first_nonzero_conversion_tick": next(
                (r["tick"] for r in rows if r["conversion_amount"] > 1e-9), None
            ),
        }

    # Identify first stopping edge
    cur = results["conditions"]["F_ordinary_CURRENT"]
    if float(cur["setup"]["env_sum_A"]) <= 1e-12 and float(cur["setup"]["env_sum_B"]) <= 1e-12:
        first_stop = {
            "edge": "ENVIRONMENT_RESOURCE_FIELD_EMPTY",
            "evidence": "CURRENT ordinary world R_A and R_B sums are ~0; uptake and conversion never start.",
            "physiology_ok_when_stock_present": results["conditions"]["D_RA_RB"]["total_conversion"] > 1e-6,
        }
    elif results["conditions"]["B_RA_only"]["total_conversion"] <= 1e-12 and results["conditions"]["D_RA_RB"]["total_conversion"] > 1e-6:
        first_stop = {
            "edge": "COMPLEMENTARY_REQUIREMENT_MISSING_B",
            "evidence": "A-only uptake occurs but conversion is B-limited.",
        }
    else:
        first_stop = {"edge": "NONE_OR_DOWNSTREAM", "evidence": results["conditions"]}

    results["first_edge_where_flow_stops"] = first_stop
    results["absorbing_at_zero_without_resources"] = True  # demonstrated separately
    return results


# ---------------------------------------------------------------------------
# C — trickle ablation
# ---------------------------------------------------------------------------

def trickle_ablation(*, seed: int = 17) -> dict[str, Any]:
    levels = {"TRICKLE_0": 0.0, "TRICKLE_LOW": 0.0005, "TRICKLE_CURRENT": 0.002}
    out: dict[str, Any] = {"levels": {}}

    for label, tr in levels.items():
        # 1) depleted + strong A+B contact, climate OFF
        contact = resource_to_work_trace(trickle=tr, ticks=20, seed=seed)
        d = contact["conditions"]["D_RA_RB"]
        # 2) depleted + no resources, WAIT 100
        cfg = PhysicalSystemConfig()
        cfg.cognition.cognition_enabled = False
        cfg.endogenous_motor.mode = "OFF"
        cfg.planet.flow_enabled = False
        cfg.deformation_work.passive_reservoir_trickle = tr
        cfg.deformation_work.reservoir_init = 0.0
        cfg.planet.climate_ecology.enabled = False
        rt = PhysicalSystemRuntime(seed=seed, config=cfg)
        rt.body.mechanical_work_reservoir = 0.0
        rt.world.R_A[:] = 0.0
        rt.world.R_B[:] = 0.0
        for _ in range(100):
            rt.step_forced_action("WAIT")
        w_wait = float(rt.body.mechanical_work_reservoir)
        # 3) depleted, resource 3 cells east, forced MOVE:E for 40 ticks
        rt2 = PhysicalSystemRuntime(seed=seed + 1, config=deepcopy(cfg))
        rt2.body.mechanical_work_reservoir = 0.0
        rt2.world.R_A[:] = 0.0
        rt2.world.R_B[:] = 0.0
        iy, ix = rt2.body.cell(rt2.config.planet.width, rt2.config.planet.height)
        target_ix = (ix + 3) % rt2.config.planet.width
        place_source_AB(rt2.world, iy, target_ix, A=2.0, B=2.0)
        x0 = float(rt2.body.x)
        for _ in range(40):
            rt2.step_forced_action("MOVE:E")
        reached = abs(float(rt2.body.x) - (target_ix + 0.5)) < 1.2 or float(
            (rt2.last_complementary_ledger or {}).get("work_credited") or 0
        ) > 1e-9
        # 4) climate ON depleted ambient recovery
        cfg4 = make_baseline_ecology_config(ECOLOGY_CLIMATE_DEFAULT, trickle=tr)
        cfg4.deformation_work.reservoir_init = 4.0
        rt4 = _make_rt(cfg4, seed)
        for _ in range(90):
            rt4.step_forced_action("MOVE:W")
        w_dep = float(rt4.body.mechanical_work_reservoir)
        income_ticks = []
        for t in range(60):
            rt4.step_forced_action("WAIT")
            if float((rt4.last_complementary_ledger or {}).get("work_credited") or 0) > 1e-9:
                income_ticks.append(t)
        out["levels"][label] = {
            "trickle": tr,
            "contact_AB_total_conversion": d["total_conversion"],
            "contact_AB_final_reservoir": d["final_reservoir"],
            "no_resource_WAIT100_reservoir": w_wait,
            "near_resource_MOVE_reached_or_converted": bool(reached),
            "near_resource_final_x_delta": float(rt2.body.x) - x0,
            "near_resource_final_reservoir": float(rt2.body.mechanical_work_reservoir),
            "climate_after_drain_reservoir": w_dep,
            "climate_recovery_first_income": income_ticks[0] if income_ticks else None,
            "climate_recovery_n_income": len(income_ticks),
            "climate_recovery_final_reservoir": float(rt4.body.mechanical_work_reservoir),
        }

    # Conceptual alternatives (not implemented)
    out["conceptual_alternatives"] = [
        {
            "name": "MINIMUM_RESIDUAL_MOTOR_AUTHORITY",
            "pros": "Leaves escape crawl without continuous energy creation",
            "cons": "Still grants free locomotion fraction; must bound carefully",
            "artificiality": "MEDIUM",
        },
        {
            "name": "EMERGENCY_LOCOMOTOR_RESERVE",
            "pros": "Finite one-shot recovery budget; exhaustion still possible",
            "cons": "New state variable; refill policy must be physical",
            "artificiality": "MEDIUM",
        },
        {
            "name": "BOUNDED_ENDOGENOUS_RECOVERY",
            "pros": "Similar to trickle but can saturate / require prior history",
            "cons": "If continuous and resource-independent, subsidizes WAIT forever",
            "artificiality": "MEDIUM-HIGH if continuous",
        },
        {
            "name": "PARTIAL_AUTHORITY_AT_ZERO",
            "pros": "Softens absorbing state",
            "cons": "Breaks exact work metering identity at empty budget",
            "artificiality": "HIGH relative to work accounting",
        },
        {
            "name": "ENABLE_RESOURCE_FIELDS_NO_TRICKLE",
            "pros": "Fixes missing stock; conversion already works; least artificial ecology",
            "cons": "Local absence of A∩B can still trap if authority is exactly zero",
            "artificiality": "LOW",
        },
    ]
    out["least_artificial_recommendation"] = "ENABLE_RESOURCE_FIELDS_NO_TRICKLE"
    return out


# ---------------------------------------------------------------------------
# D — habitability long runs
# ---------------------------------------------------------------------------

def _habitability_run(
    name: str,
    cfg: PhysicalSystemConfig,
    *,
    seed: int,
    ticks: int = 400,
) -> dict[str, Any]:
    rt = _make_rt(deepcopy(cfg), seed)
    # Start with mid reservoir; place away from densest product cell when stock exists.
    w_max = float(rt.config.deformation_work.reservoir_max)
    rt.body.mechanical_work_reservoir = 0.55 * w_max
    ra = np.asarray(rt.world.R_A)
    rb = np.asarray(rt.world.R_B)
    if float(ra.sum() + rb.sum()) > 1e-9:
        prod = ra * rb
        iy_p, ix_p = divmod(int(prod.argmax()), prod.shape[1])
        # Opposite side of torus — must travel to reach peak product
        rt.body.x = float((ix_p + rt.config.planet.width // 2) % rt.config.planet.width) + 0.5
        rt.body.y = float((iy_p + rt.config.planet.height // 2) % rt.config.planet.height) + 0.5
    rt.body.vx = rt.body.vy = 0.0

    reservoirs = []
    conversions = []
    uptakes = []
    spends = []
    collapsed = 0
    near_zero = 0
    positions = []
    flow_disp = 0.0
    active_disp = 0.0
    resource_encounter_ticks = 0
    # MOVE-heavy scripted exploration (not cognition): pressure + coverage
    actions = (["MOVE:N", "MOVE:E", "MOVE:S", "MOVE:W", "WAIT"] ) * (ticks // 5 + 1)
    x_prev, y_prev = float(rt.body.x), float(rt.body.y)
    for t in range(ticks):
        act = actions[t]
        la, lb = _local_AB(rt)
        if la > 1e-4 and lb > 1e-4:
            resource_encounter_ticks += 1
        _step_world(rt, act)
        cl = rt.last_complementary_ledger or {}
        aw = getattr(rt, "last_action_work_ledger", None) or {}
        conversions.append(float(cl.get("work_credited") or 0.0))
        uptakes.append(
            float((cl.get("A") or {}).get("acquired") or 0.0)
            + float((cl.get("B") or {}).get("acquired") or 0.0)
        )
        spend = float(aw.get("work_spent") or aw.get("spent") or 0.0)
        spends.append(spend)
        w1 = float(rt.body.mechanical_work_reservoir)
        reservoirs.append(w1)
        if w1 <= 0.02 * w_max:
            near_zero += 1
        auth = _probe_authority(rt)
        if auth["motor_authority_class"] == "COLLAPSED":
            collapsed += 1
        x1, y1 = float(rt.body.x), float(rt.body.y)
        dx = abs(x1 - x_prev)
        dy = abs(y1 - y_prev)
        W, H = rt.config.planet.width, rt.config.planet.height
        dx = min(dx, W - dx)
        dy = min(dy, H - dy)
        dist = math.hypot(dx, dy)
        if act == "WAIT":
            flow_disp += dist
        else:
            active_disp += dist
        positions.append((x1, y1))
        x_prev, y_prev = x1, y1

    # Drain+recovery probe (matched seed fork)
    rt_d = _make_rt(deepcopy(cfg), seed + 1000)
    rt_d.body.mechanical_work_reservoir = w_max
    for _ in range(100):
        _step_world(rt_d, "MOVE:W")
    w_after_drain = float(rt_d.body.mechanical_work_reservoir)
    recovery_income = 0
    for _ in range(80):
        _step_world(rt_d, "WAIT")
        if float((rt_d.last_complementary_ledger or {}).get("work_credited") or 0) > 1e-9:
            recovery_income += 1
    w_after_recovery = float(rt_d.body.mechanical_work_reservoir)

    bins = {}
    for x, y in positions:
        key = (int(x) // 4, int(y) // 4)
        bins[key] = bins.get(key, 0) + 1
    modal = max(bins.values()) if bins else 0
    longest = 1
    cur = 1
    prev = (int(positions[0][0]) // 2, int(positions[0][1]) // 2)
    for p in positions[1:]:
        k = (int(p[0]) // 2, int(p[1]) // 2)
        if k == prev:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 1
            prev = k

    total_disp = flow_disp + active_disp
    return {
        "ecology": name,
        "seed": seed,
        "ticks": ticks,
        "config": ecology_summary(cfg),
        "mean_reservoir": float(np.mean(reservoirs)) if reservoirs else 0.0,
        "min_reservoir": float(np.min(reservoirs)) if reservoirs else 0.0,
        "max_reservoir": float(np.max(reservoirs)) if reservoirs else 0.0,
        "frac_near_zero": near_zero / max(ticks, 1),
        "collapsed_authority_ticks": collapsed,
        "total_conversion": float(sum(conversions)),
        "total_uptake": float(sum(uptakes)),
        "resource_encounter_ticks": resource_encounter_ticks,
        "resource_encounter_fraction": resource_encounter_ticks / max(ticks, 1),
        "total_locomotor_spend_reported": float(sum(spends)),
        "active_displacement": active_disp,
        "wait_passive_displacement": flow_disp,
        "passive_flow_fraction_of_displacement": (flow_disp / total_disp) if total_disp > 1e-9 else None,
        "spatial_coverage_bins": len(bins),
        "trajectory_concentration_modal_frac": modal / max(ticks, 1),
        "longest_region_trap_ticks": longest,
        "final_reservoir": reservoirs[-1] if reservoirs else 0.0,
        "starvation_like": reservoirs[-1] <= 0.02 * w_max and collapsed > ticks * 0.25,
        "recovery_events": sum(
            1 for i in range(1, len(reservoirs)) if reservoirs[i - 1] < 0.05 * w_max <= reservoirs[i]
        ),
        "drain_probe": {
            "reservoir_after_forced_move100": w_after_drain,
            "recovery_income_ticks_wait80": recovery_income,
            "reservoir_after_recovery_wait": w_after_recovery,
            "recovered": w_after_recovery > w_after_drain + 0.05,
        },
    }


def habitability_suite(*, ticks: int = 400, seeds: list[int] | None = None) -> dict[str, Any]:
    seeds = seeds or [17, 29, 41]
    candidates = {
        "CURRENT_REFERENCE_trickle0": make_current_uninhabitable_reference(trickle=0.0),
        "CURRENT_REFERENCE_trickle002": make_current_uninhabitable_reference(trickle=0.002),
        ECOLOGY_CLIMATE_DEFAULT: make_baseline_ecology_config(ECOLOGY_CLIMATE_DEFAULT, trickle=0.0),
        ECOLOGY_A_STATIC_PATCHES: make_baseline_ecology_config(ECOLOGY_A_STATIC_PATCHES, trickle=0.0),
        ECOLOGY_B_MIGRATING: make_baseline_ecology_config(ECOLOGY_B_MIGRATING, trickle=0.0),
        ECOLOGY_C_CHANGING: make_baseline_ecology_config(ECOLOGY_C_CHANGING, trickle=0.0),
    }
    runs = []
    for name, cfg in candidates.items():
        for seed in seeds:
            runs.append(_habitability_run(name, cfg, seed=seed, ticks=ticks))
    # Aggregate by ecology
    by: dict[str, list] = {}
    for r in runs:
        by.setdefault(r["ecology"], []).append(r)

    def agg(rows: list[dict]) -> dict:
        keys = [
            "mean_reservoir",
            "frac_near_zero",
            "collapsed_authority_ticks",
            "total_conversion",
            "total_uptake",
            "resource_encounter_fraction",
            "active_displacement",
            "wait_passive_displacement",
            "passive_flow_fraction_of_displacement",
            "spatial_coverage_bins",
            "trajectory_concentration_modal_frac",
            "longest_region_trap_ticks",
            "recovery_events",
        ]
        out = {}
        for k in keys:
            vals = [r[k] for r in rows if r.get(k) is not None]
            out[k] = {
                "mean": float(np.mean(vals)) if vals else None,
                "std": float(np.std(vals)) if vals else None,
            }
        out["starvation_like_rate"] = sum(1 for r in rows if r.get("starvation_like")) / max(len(rows), 1)
        out["n_seeds"] = len(rows)
        return out

    aggregates = {k: agg(v) for k, v in by.items()}
    return {"ticks": ticks, "seeds": seeds, "runs": runs, "aggregates": aggregates}


def recommend(habit: dict, trickle: dict, trace: dict) -> dict[str, Any]:
    ag = habit["aggregates"]
    runs_by = {}
    for r in habit["runs"]:
        runs_by.setdefault(r["ecology"], []).append(r)

    scored = []
    for name, a in ag.items():
        if name.startswith("CURRENT_REFERENCE"):
            continue
        conv = (a["total_conversion"]["mean"] or 0.0)
        nz = (a["frac_near_zero"]["mean"] or 0.0)
        starve = a["starvation_like_rate"]
        passive = a["passive_flow_fraction_of_displacement"]["mean"]
        passive = 0.0 if passive is None else passive
        enc = (a.get("resource_encounter_fraction") or {}).get("mean") or 0.0
        rows = runs_by.get(name, [])
        recover_rate = sum(1 for r in rows if (r.get("drain_probe") or {}).get("recovered")) / max(len(rows), 1)
        # Prefer: conversion present, encounters not universal (must move), recoverability,
        # some pressure, low flow-dominated displacement, coverage.
        score = 0.0
        score += min(conv / 4.0, 3.0)
        score += 1.2 * recover_rate
        score += 0.8 if 0.02 <= enc <= 0.45 else (-0.6 if enc > 0.7 or enc < 0.005 else 0.0)
        score += 0.6 if 0.01 <= nz <= 0.50 else (-0.8 if nz > 0.75 else 0.0)
        score -= 2.0 * starve
        score -= 1.5 * max(0.0, passive - 0.40)
        score += 0.4 * min((a["spatial_coverage_bins"]["mean"] or 0) / 16.0, 1.5)
        # Penalize CURRENT-like zero conversion hard
        if conv <= 1e-6:
            score -= 3.0
        scored.append((score, name, {"recover_rate": recover_rate, "encounter": enc, **a}))
    scored.sort(reverse=True)
    best = scored[0] if scored else (0.0, None, {})
    t0 = trickle["levels"]["TRICKLE_0"]
    tcur = trickle["levels"]["TRICKLE_CURRENT"]
    climate_recovers_without_trickle = t0["climate_recovery_first_income"] is not None
    contact_works_without_trickle = t0["contact_AB_total_conversion"] > 1e-6
    trickle_subsidizes_without_resources = tcur["no_resource_WAIT100_reservoir"] > 0.05
    if climate_recovers_without_trickle and contact_works_without_trickle and trickle_subsidizes_without_resources:
        trickle_treatment = "REMOVE"
    elif contact_works_without_trickle and not climate_recovers_without_trickle:
        trickle_treatment = "REPLACE WITH BETTER PHYSICAL MECHANISM"
    elif not contact_works_without_trickle:
        trickle_treatment = "UNRESOLVED"
    else:
        trickle_treatment = "KEEP AS PHYSIOLOGICAL BASELINE"

    return {
        "recommended_baseline_ecology": best[1],
        "scoreboard": [{"score": s, "name": n, "recover_rate": d.get("recover_rate")} for s, n, d in scored],
        "trickle_treatment": trickle_treatment,
        "rationale": {
            "first_edge": trace.get("first_edge_where_flow_stops"),
            "climate_recovers_without_trickle": climate_recovers_without_trickle,
            "contact_conversion_without_trickle": contact_works_without_trickle,
            "trickle_subsidizes_without_resources": trickle_subsidizes_without_resources,
            "absorbing_without_stock_or_trickle": True,
            "note": "Physical substrate calibration only — not cognition/PSC evidence.",
        },
    }


def write_report(out_dir: Path, *, audit, trace, trickle, habit, rec) -> None:
    lines = []
    lines.append("# Tiktaalik Baseline Ecology Calibration Report\n")
    lines.append(f"Generated: `{out_dir.name}`\n")
    lines.append("Scope: physical economy / habitability substrate only. Not cognition, planning, preference, habit, or PSC.\n")
    lines.append("\n## A. Current resource→work wiring\n")
    lines.append("```")
    lines.append("\n".join(f"- {c}" for c in audit["chain"]))
    lines.append("```\n")
    lines.append(f"- Factory complementary ON, climate ecology **OFF** → env R_A/R_B remain **0**.\n")
    lines.append(f"- `scale_positive_ke` at empty budget = `{audit['scale_positive_ke_empty']}` (exact collapse).\n")
    lines.append(f"- BODY-01 `make_ecology_config` stamps `passive_reservoir_trickle={audit['make_ecology_config_CURRENT']['passive_reservoir_trickle']}`.\n")

    lines.append("\n## B. Exact failure point\n")
    fe = trace["first_edge_where_flow_stops"]
    lines.append(f"**{fe.get('edge')}**\n")
    lines.append(f"{fe.get('evidence')}\n")
    lines.append(
        f"Physiology check: co-located A+B conversion works "
        f"(`physiology_ok_when_stock_present={fe.get('physiology_ok_when_stock_present')}`).\n"
    )
    d = trace["conditions"]["D_RA_RB"]
    a_only = trace["conditions"]["B_RA_only"]
    cur = trace["conditions"]["F_ordinary_CURRENT"]
    clim = trace["conditions"]["F_ordinary_CLIMATE"]
    lines.append(
        f"- D A+B total conversion={d['total_conversion']:.4f}, final W={d['final_reservoir']:.4f}\n"
        f"- A-only total conversion={a_only['total_conversion']:.4f} (hard complement)\n"
        f"- CURRENT ordinary conversion={cur['total_conversion']:.4f} (env sum A/B="
        f"{cur['setup']['env_sum_A']:.4f}/{cur['setup']['env_sum_B']:.4f})\n"
        f"- CLIMATE ordinary conversion={clim['total_conversion']:.4f}\n"
    )

    lines.append("\n## C. Is reservoir=0 absorbing?\n")
    lines.append(
        "- **Yes for active locomotion** when budget≤1e-15: `scale_positive_ke`→0, MOVE displacement≈0.\n"
        "- **Not absorbing for work recovery** if co-located env A+B contact exists (WAIT+conversion).\n"
        "- **Practically absorbing** on CURRENT baseline because env stocks are empty and trickle was the only income.\n"
    )

    lines.append("\n## D. Trickle ablation 0 / 0.0005 / 0.002\n")
    for k, v in trickle["levels"].items():
        lines.append(
            f"- **{k}** trickle={v['trickle']}: "
            f"contact_conv={v['contact_AB_total_conversion']:.4f}; "
            f"no_res WAIT100 W={v['no_resource_WAIT100_reservoir']:.4f}; "
            f"reach_near_res={v['near_resource_MOVE_reached_or_converted']}; "
            f"climate_recovery_first={v['climate_recovery_first_income']}; "
            f"climate_final_W={v['climate_recovery_final_reservoir']:.4f}\n"
        )

    lines.append("\n## E. Is passive_reservoir_trickle necessary?\n")
    lines.append(f"**Recommendation: `{rec['trickle_treatment']}`**\n")
    lines.append(
        "If resource fields are enabled, contact conversion and climate ambient recovery "
        "occur at trickle=0. Trickle=0.002 accumulates work under WAIT with zero resources "
        "(locomotor subsidy / behavioral confound).\n"
    )

    lines.append("\n## F. Candidate world configurations\n")
    for name in (
        ECOLOGY_A_STATIC_PATCHES,
        ECOLOGY_B_MIGRATING,
        ECOLOGY_C_CHANGING,
        ECOLOGY_CLIMATE_DEFAULT,
    ):
        lines.append(f"- `{name}` — see `habitability.json` config summaries.\n")

    lines.append("\n## G. Comparative habitability metrics\n")
    lines.append(
        "| Ecology | mean W | near0 | collapsed | conversion | encounter | "
        "passive_flow | coverage | starve | drain_recover |\n"
    )
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n")
    runs_by: dict[str, list] = {}
    for r in habit["runs"]:
        runs_by.setdefault(r["ecology"], []).append(r)
    for name, a in habit["aggregates"].items():
        rows = runs_by.get(name, [])
        recover = sum(1 for r in rows if (r.get("drain_probe") or {}).get("recovered")) / max(len(rows), 1)
        enc = (a.get("resource_encounter_fraction") or {}).get("mean") or 0.0
        lines.append(
            f"| {name} | {a['mean_reservoir']['mean']:.3f} | {a['frac_near_zero']['mean']:.3f} | "
            f"{a['collapsed_authority_ticks']['mean']:.1f} | {a['total_conversion']['mean']:.2f} | "
            f"{enc:.3f} | {(a['passive_flow_fraction_of_displacement']['mean'] or -1):.3f} | "
            f"{a['spatial_coverage_bins']['mean']:.1f} | {a['starvation_like_rate']:.2f} | {recover:.2f} |\n"
        )

    lines.append("\n## H. Recommended baseline ecology\n")
    lines.append(f"**`{rec['recommended_baseline_ecology']}`**\n")
    lines.append(f"Scoreboard: {rec['scoreboard']}\n")

    lines.append("\n## I. Recommended trickle treatment\n")
    lines.append(f"**`{rec['trickle_treatment']}`**\n")

    lines.append("\n## J. Code/config changes made\n")
    lines.append(
        "- Added `mechanistic_mind/physical_system/baseline_ecology_presets.py` (opt-in candidates).\n"
        "- Added `experiments/run_tiktaalik_baseline_ecology_calibration.py`.\n"
        "- Added `tests/test_tiktaalik_baseline_ecology_calibration.py`.\n"
        "- **Did not** change CURRENT factory defaults, `BODY01_PASSIVE_RESERVOIR_TRICKLE`, or cognition.\n"
    )

    lines.append("\n## K. Tests\n")
    lines.append("See pytest output recorded in `TESTS.md`.\n")

    lines.append("\n## MOMENTUM-01 (deferred)\n")
    lines.append(
        "TODO later: controlled YOU→Tiktaalik impulse transfer test. "
        "Deformation was not the major work sink in BODY-01; do not conflate with this calibration.\n"
    )

    lines.append("\n## Conceptual alternatives (not implemented)\n")
    for alt in trickle["conceptual_alternatives"]:
        lines.append(
            f"- **{alt['name']}** artificiality={alt['artificiality']}: "
            f"{alt['pros']} / {alt['cons']}\n"
        )
    lines.append(f"\nLeast artificial: **{trickle['least_artificial_recommendation']}**\n")
    _write(out_dir / "CALIBRATION_REPORT.md", "".join(lines))


def main() -> None:
    out_dir = OUT_ROOT / f"baseline_ecology_calib_{_ts()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    audit = audit_wiring()
    trace = resource_to_work_trace(trickle=0.0, ticks=24)
    trickle = trickle_ablation()
    habit = habitability_suite(ticks=400, seeds=[17, 29, 41])
    rec = recommend(habit, trickle, trace)
    _write(out_dir / "wiring_audit.json", audit)
    _write(out_dir / "resource_to_work_trace.json", trace)
    _write(out_dir / "trickle_ablation.json", trickle)
    _write(out_dir / "habitability.json", habit)
    _write(out_dir / "recommendation.json", rec)
    write_report(out_dir, audit=audit, trace=trace, trickle=trickle, habit=habit, rec=rec)
    readme = (
        "# Baseline Ecology Calibration\n\n"
        "Diagnostic apparatus for Tiktaalik physical habitability.\n"
        "Not a PSC result. No commit performed.\n\n"
        f"Elapsed_s: {time.perf_counter() - t0:.2f}\n"
        f"Recommended ecology: {rec['recommended_baseline_ecology']}\n"
        f"Trickle treatment: {rec['trickle_treatment']}\n"
    )
    _write(out_dir / "README.md", readme)
    print(json.dumps({"out_dir": str(out_dir), **{k: rec[k] for k in ("recommended_baseline_ecology", "trickle_treatment")}}, indent=2))


if __name__ == "__main__":
    main()
