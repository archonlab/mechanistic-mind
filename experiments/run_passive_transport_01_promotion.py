#!/usr/bin/env python3
"""PASSIVE_TRANSPORT_01 promotion validation — force_scale 1.0 → 0.15.

BASELINE_CLIMATE_DEFAULT already stamped with 0.15 in ecology_presets.
This runner measures post-promotion WAIT/MOVE controls and compares to
pre-promotion evidence from passive_transport_01_20260918T234435Z.
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

from mechanistic_mind.model.tiktaalik import tiktaalik_cognition_config, tiktaalik_config
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.ecology_presets import (
    BODY01_PASSIVE_RESERVOIR_TRICKLE,
    ECOLOGY_BASELINE,
    ECOLOGY_CURRENT_LEGACY,
    PASSIVE_TRANSPORT_FORCE_SCALE_PRE,
    PASSIVE_TRANSPORT_FORCE_SCALE_PROMOTED,
    PASSIVE_TRANSPORT_FORCE_SCALE_STRONG,
    ecology_metadata,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from experiments.run_passive_transport_01 import run_transport, _mean, _safe_div, _agg

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "results" / "physics"
PRE_EVIDENCE = ROOT / "results" / "physics" / "passive_transport_01_20260918T234435Z"
SEEDS = [17, 29, 41, 53, 67]


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, str):
        path.write_text(obj, encoding="utf-8")
    else:
        path.write_text(json.dumps(obj, indent=2, default=str) + "\n", encoding="utf-8")


def _promoted_cfg() -> PhysicalSystemConfig:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    return cfg


def _pre_cfg() -> PhysicalSystemConfig:
    """Reconstruct pre-promotion baseline (force_scale=1.0) for matched comparison."""
    cfg = _promoted_cfg()
    cfg.body_orientation.force_scale = float(PASSIVE_TRANSPORT_FORCE_SCALE_PRE)
    return cfg


def suite(cfg: PhysicalSystemConfig, ticks: int) -> dict[str, Any]:
    wait = [run_transport(seed=s, ticks=ticks, mode="WAIT", cfg=cfg) for s in SEEDS]
    move = [run_transport(seed=s, ticks=ticks, mode="MOVE_CYCLE", cfg=cfg) for s in SEEDS]
    return {
        "ticks": ticks,
        "WAIT_runs": wait,
        "MOVE_runs": move,
        "WAIT": _agg(wait),
        "MOVE": _agg(move),
        "ratios": {
            "path_MOVE_over_WAIT": _safe_div(_mean(move, "path_distance"), _mean(wait, "path_distance")),
            "path_WAIT_over_MOVE": _safe_div(_mean(wait, "path_distance"), _mean(move, "path_distance")),
            "unique_MOVE_over_WAIT": _safe_div(_mean(move, "unique_cells"), _mean(wait, "unique_cells")),
            "unique_WAIT_over_MOVE": _safe_div(_mean(wait, "unique_cells"), _mean(move, "unique_cells")),
            "coverage_MOVE_over_WAIT": _safe_div(
                _mean(move, "spatial_coverage_bins"), _mean(wait, "spatial_coverage_bins")
            ),
            "net_MOVE_over_WAIT": _safe_div(_mean(move, "net_displacement"), _mean(wait, "net_displacement")),
            "enc_AB_WAIT": _mean(wait, "resource_encounter_AB_fraction"),
            "enc_AB_MOVE": _mean(move, "resource_encounter_AB_fraction"),
        },
    }


def local_coupling_check(cfg: PhysicalSystemConfig) -> dict[str, Any]:
    """GATE 4: WAIT body still measurably responds to environment."""
    from experiments.run_passive_transport_01 import _wrap_delta

    rt = PhysicalSystemRuntime(seed=17, config=deepcopy(cfg))
    path = 0.0
    rot = 0.0
    th = float(rt.body.theta)
    speeds: list[float] = []
    env_force = 0.0
    t_series: list[float] = []

    for _ in range(200):
        x0, y0 = float(rt.body.x), float(rt.body.y)
        iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
        t_series.append(float(rt.world.T[iy, ix]))
        rt.step_forced_action("WAIT")
        dx = _wrap_delta(x0, rt.body.x, rt.config.planet.width)
        dy = _wrap_delta(y0, rt.body.y, rt.config.planet.height)
        path += math.hypot(dx, dy)
        speeds.append(math.hypot(float(rt.body.vx), float(rt.body.vy)))
        dth = float(rt.body.theta) - th
        while dth > math.pi:
            dth -= 2 * math.pi
        while dth < -math.pi:
            dth += 2 * math.pi
        rot += abs(dth)
        th = float(rt.body.theta)
        om = rt.last_orientation_meta or {}
        nf = om.get("net_force") or [0.0, 0.0]
        env_force += abs(float(nf[0])) + abs(float(nf[1]))

    t_std = float(np.std(t_series)) if t_series else 0.0
    coupled = (
        path > 1e-4
        or rot > 1e-4
        or float(np.mean(speeds)) > 1e-5
        or env_force > 1e-6
        or t_std > 1e-6
    )
    return {
        "path_200": path,
        "rotation_abs_200": rot,
        "mean_speed": float(np.mean(speeds)) if speeds else 0.0,
        "max_speed": float(np.max(speeds)) if speeds else 0.0,
        "env_site_force_impulse_proxy": env_force,
        "local_T_std": t_std,
        "measurably_coupled": coupled,
    }


def resource_regression() -> dict[str, Any]:
    cfg = _promoted_cfg()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    env_ok = float(np.sum(rt.world.R_A)) > 1.0 and float(np.sum(rt.world.R_B)) > 1.0

    # A+B conversion
    cfg2 = make_ecology_config(ECOLOGY_CURRENT_LEGACY, trickle=0.0)
    cfg2.cognition.cognition_enabled = False
    cfg2.endogenous_motor.mode = "OFF"
    cfg2.planet.flow_enabled = False
    rt2 = PhysicalSystemRuntime(seed=17, config=cfg2)
    rt2.body.mechanical_work_reservoir = 0.0
    rt2.world.R_A[:] = 0.0
    rt2.world.R_B[:] = 0.0
    n = len(rt2.config.body.footprint)
    rt2.body.R_A_site = np.zeros(n)
    rt2.body.R_B_site = np.zeros(n)
    iy, ix = rt2.body.cell(rt2.config.planet.width, rt2.config.planet.height)
    place_source_AB(rt2.world, iy, ix, A=2.0, B=2.0)
    w0 = float(rt2.body.mechanical_work_reservoir)
    rt2.step_forced_action("WAIT")
    conv_ok = float(rt2.body.mechanical_work_reservoir) > w0

    # no-resource WAIT
    cfg3 = make_ecology_config(ECOLOGY_CURRENT_LEGACY, trickle=0.0)
    cfg3.cognition.cognition_enabled = False
    cfg3.endogenous_motor.mode = "OFF"
    cfg3.planet.flow_enabled = False
    cfg3.planet.climate_ecology.enabled = False
    rt3 = PhysicalSystemRuntime(seed=11, config=cfg3)
    rt3.body.mechanical_work_reservoir = 0.0
    rt3.world.R_A[:] = 0.0
    rt3.world.R_B[:] = 0.0
    rt3.body.R_A_site = np.zeros(len(cfg3.body.footprint))
    rt3.body.R_B_site = np.zeros(len(cfg3.body.footprint))
    for _ in range(40):
        rt3.step_forced_action("WAIT")
    no_res_ok = float(rt3.body.mechanical_work_reservoir) == 0.0

    # naive encounters under promoted baseline
    enc = run_transport(seed=17, ticks=2000, mode="WAIT", cfg=cfg)
    enc_move = run_transport(seed=17, ticks=2000, mode="MOVE_CYCLE", cfg=cfg)

    return {
        "env_RA_RB_present": env_ok,
        "AB_conversion_credits_work": conv_ok,
        "no_resource_WAIT_no_work": no_res_ok,
        "passive_reservoir_trickle": float(cfg.deformation_work.passive_reservoir_trickle),
        "BODY01_PASSIVE_RESERVOIR_TRICKLE": float(BODY01_PASSIVE_RESERVOIR_TRICKLE),
        "naive_WAIT_enc_AB_frac_2000": enc["resource_encounter_AB_fraction"],
        "naive_MOVE_enc_AB_frac_2000": enc_move["resource_encounter_AB_fraction"],
        "naive_WAIT_conversion_2000": enc["resource_conversion"],
        "naive_MOVE_conversion_2000": enc_move["resource_conversion"],
        "force_scale": float(cfg.body_orientation.force_scale),
    }


def two_agent_sanity() -> dict[str, Any]:
    cfg = make_ecology_config(ECOLOGY_BASELINE, trickle=0.0)
    # normal cognition
    cfg.cognition = tiktaalik_cognition_config()
    cfg.cognition.cognition_enabled = True
    ta = TwoAgentRuntime(seed=17, config=cfg, signal_enabled=True)
    from experiments.run_passive_transport_01 import _wrap_delta

    paths = [0.0, 0.0]
    wait_paths = [0.0, 0.0]
    move_ticks = [0, 0]
    for _ in range(300):
        before = [(float(s.body.x), float(s.body.y)) for s in ta.slots]
        ta.step()
        for i, s in enumerate(ta.slots):
            dx = _wrap_delta(before[i][0], s.body.x, cfg.planet.width)
            dy = _wrap_delta(before[i][1], s.body.y, cfg.planet.height)
            d = math.hypot(dx, dy)
            paths[i] += d
            act = getattr(s, "last_selected_action", None) or "WAIT"
            if act == "WAIT":
                wait_paths[i] += d
            else:
                move_ticks[i] += 1
    return {
        "ticks": 300,
        "force_scale": float(cfg.body_orientation.force_scale),
        "path": paths,
        "wait_path": wait_paths,
        "non_wait_ticks": move_ticks,
        "env_RA_sum": float(np.sum(ta.world.R_A)),
        "env_RB_sum": float(np.sum(ta.world.R_B)),
        "note": "Sanity only — not social/communication/preference evidence.",
    }


def cognition_unchanged() -> dict[str, Any]:
    a = tiktaalik_cognition_config()
    b = tiktaalik_config().cognition
    keys = sorted(a.to_dict().keys()) if hasattr(a, "to_dict") else []
    # Compare dataclass fields
    from dataclasses import fields
    diffs = []
    for f in fields(a):
        if getattr(a, f.name) != getattr(b, f.name):
            diffs.append(f.name)
    return {"cognition_field_diffs_vs_fresh": diffs, "unchanged": len(diffs) == 0}


def gates(after_1k, after_5k, pre_1k_means, coupling, res, cog) -> dict[str, bool]:
    cfg = _promoted_cfg()
    wait_path_after = after_1k["WAIT"]["path_distance"]["mean"]
    wait_path_pre = pre_1k_means["WAIT_path"]
    move_path = after_1k["MOVE"]["path_distance"]["mean"]
    return {
        "GATE_1_force_scale_0_15": abs(float(cfg.body_orientation.force_scale) - 0.15) < 1e-12,
        "GATE_2_WAIT_exploration_reduced": wait_path_after < 0.5 * wait_path_pre,
        "GATE_3_MOVE_exceeds_WAIT": (after_1k["ratios"]["path_MOVE_over_WAIT"] or 0) >= 2.0,
        "GATE_4_local_coupling_retained": bool(coupling["measurably_coupled"]),
        "GATE_5_RA_RB_present": bool(res["env_RA_RB_present"]),
        "GATE_6_AB_to_work": bool(res["AB_conversion_credits_work"]),
        "GATE_7_trickle_zero": float(res["passive_reservoir_trickle"]) == 0.0,
        "GATE_8_cognition_unchanged": bool(cog["unchanged"]),
        "GATE_9_env_timescale_unchanged": (
            abs(cfg.planet.F_fast_period - 40) < 1e-9
            and abs(cfg.planet.flow_gain - 0.14) < 1e-12
            and abs(cfg.planet.climate_ecology.season_period - 80) < 1e-9
        ),
        "GATE_10_legacy_reproducible": make_ecology_config(ECOLOGY_CURRENT_LEGACY).planet.climate_ecology.enabled is False,
        "needs_fallback_0_10": (
            (after_5k["WAIT"]["unique_cells"]["mean"] or 0) >= 25
            and (after_5k["ratios"]["path_MOVE_over_WAIT"] or 0) < 2.5
        ),
    }


def main() -> None:
    out = OUT_ROOT / f"passive_transport_01_promotion_{_ts()}"
    out.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    cfg = _promoted_cfg()
    assert abs(cfg.body_orientation.force_scale - PASSIVE_TRANSPORT_FORCE_SCALE_PROMOTED) < 1e-12

    # Load pre-promotion metrics from authoritative evidence if present
    pre_1k = {"WAIT_path": 45.38976234664902, "WAIT_unique": 30.6, "MOVE_path": 78.24708616624179, "MOVE_unique": 31.6,
              "path_ratio": 1.7238928366413562, "enc_WAIT": 0.1684}
    pre_5k = {"WAIT_path": 173.7620112413594, "WAIT_unique": 31.8, "MOVE_path": 344.33280097633235, "MOVE_unique": 32.6}
    if PRE_EVIDENCE.exists():
        try:
            ps = json.loads((PRE_EVIDENCE / "per_seed_metrics.json").read_text())
            def m(runs, k):
                return sum(r[k] for r in runs) / len(runs)
            pre_1k = {
                "WAIT_path": m(ps["before"]["1000"]["WAIT"], "path_distance"),
                "WAIT_unique": m(ps["before"]["1000"]["WAIT"], "unique_cells"),
                "MOVE_path": m(ps["before"]["1000"]["MOVE"], "path_distance"),
                "MOVE_unique": m(ps["before"]["1000"]["MOVE"], "unique_cells"),
                "path_ratio": m(ps["before"]["1000"]["MOVE"], "path_distance") / m(ps["before"]["1000"]["WAIT"], "path_distance"),
                "enc_WAIT": m(ps["before"]["1000"]["WAIT"], "resource_encounter_AB_fraction"),
            }
            pre_5k = {
                "WAIT_path": m(ps["before"]["5000"]["WAIT"], "path_distance"),
                "WAIT_unique": m(ps["before"]["5000"]["WAIT"], "unique_cells"),
                "MOVE_path": m(ps["before"]["5000"]["MOVE"], "path_distance"),
                "MOVE_unique": m(ps["before"]["5000"]["MOVE"], "unique_cells"),
            }
        except Exception as e:
            pre_1k["load_note"] = str(e)

    print("Post-promotion 1k controls…", flush=True)
    after_1k = suite(cfg, 1000)
    print("Post-promotion 5k controls…", flush=True)
    after_5k = suite(cfg, 5000)

    # Matched live pre-reconstruction (force_scale=1.0) for side-by-side freshness
    print("Matched pre force_scale=1.0 @1k (fresh)…", flush=True)
    pre_fresh_1k = suite(_pre_cfg(), 1000)

    coupling = local_coupling_check(cfg)
    res = resource_regression()
    sanity = two_agent_sanity()
    cog = cognition_unchanged()
    g = gates(after_1k, after_5k, pre_1k, coupling, res, cog)

    fallback = None
    if g.get("needs_fallback_0_10"):
        print("0.15 still excessive — running 0.10 comparison…", flush=True)
        cfg10 = _promoted_cfg()
        cfg10.body_orientation.force_scale = float(PASSIVE_TRANSPORT_FORCE_SCALE_STRONG)
        fallback = {
            "force_scale": 0.10,
            "suite_1000": suite(cfg10, 1000),
            "coupling": local_coupling_check(cfg10),
            "note": "Comparison only — not silently promoted.",
        }

    effective = {
        "ecology_preset": ECOLOGY_BASELINE,
        "body_orientation.force_scale": {
            "old": PASSIVE_TRANSPORT_FORCE_SCALE_PRE,
            "new": PASSIVE_TRANSPORT_FORCE_SCALE_PROMOTED,
            "strong_candidate_not_promoted": PASSIVE_TRANSPORT_FORCE_SCALE_STRONG,
        },
        "metadata": ecology_metadata(cfg),
        "unchanged": {
            "flow_gain": cfg.planet.flow_gain,
            "flow_max": cfg.planet.flow_max,
            "F_fast_period": cfg.planet.F_fast_period,
            "F_slow_period": cfg.planet.F_slow_period,
            "climate.season_period": cfg.planet.climate_ecology.season_period,
            "body.flow_coupling": cfg.body.flow_coupling,
            "passive_reservoir_trickle": cfg.deformation_work.passive_reservoir_trickle,
            "climate_enabled": cfg.planet.climate_ecology.enabled,
        },
        "tiktaalik_config_force_scale": float(tiktaalik_config().body_orientation.force_scale),
    }

    comparison = {
        "pre_evidence_file": str(PRE_EVIDENCE),
        "pre_1k_from_evidence": pre_1k,
        "pre_5k_from_evidence": pre_5k,
        "pre_fresh_1k_force_scale_1_0": {
            "WAIT_path": pre_fresh_1k["WAIT"]["path_distance"]["mean"],
            "WAIT_unique": pre_fresh_1k["WAIT"]["unique_cells"]["mean"],
            "MOVE_path": pre_fresh_1k["MOVE"]["path_distance"]["mean"],
            "ratios": pre_fresh_1k["ratios"],
        },
        "after_1k": {
            "WAIT_path": after_1k["WAIT"]["path_distance"]["mean"],
            "WAIT_unique": after_1k["WAIT"]["unique_cells"]["mean"],
            "MOVE_path": after_1k["MOVE"]["path_distance"]["mean"],
            "MOVE_unique": after_1k["MOVE"]["unique_cells"]["mean"],
            "ratios": after_1k["ratios"],
        },
        "after_5k": {
            "WAIT_path": after_5k["WAIT"]["path_distance"]["mean"],
            "WAIT_unique": after_5k["WAIT"]["unique_cells"]["mean"],
            "MOVE_path": after_5k["MOVE"]["path_distance"]["mean"],
            "MOVE_unique": after_5k["MOVE"]["unique_cells"]["mean"],
            "ratios": after_5k["ratios"],
        },
        "WAIT_path_reduction_factor_1k": (
            after_1k["WAIT"]["path_distance"]["mean"] / pre_1k["WAIT_path"]
            if pre_1k["WAIT_path"] else None
        ),
    }

    summary = {
        "elapsed_s": time.perf_counter() - t0,
        "promoted": effective["body_orientation.force_scale"],
        "gates": g,
        "local_coupling": coupling,
        "comparison": comparison,
        "fallback_0_10": fallback is not None,
        "allowed_claim": (
            "Reducing body/environment force coupling reduces passive whole-body "
            "transport while preserving measurable environmental interaction."
        ),
    }

    _write(out / "effective_config.json", effective)
    _write(out / "wait_control_metrics.json", {
        "1000": {"agg": after_1k["WAIT"], "runs": after_1k["WAIT_runs"]},
        "5000": {"agg": after_5k["WAIT"], "runs": after_5k["WAIT_runs"]},
    })
    _write(out / "move_control_metrics.json", {
        "1000": {"agg": after_1k["MOVE"], "runs": after_1k["MOVE_runs"], "ratios": after_1k["ratios"]},
        "5000": {"agg": after_5k["MOVE"], "runs": after_5k["MOVE_runs"], "ratios": after_5k["ratios"]},
    })
    _write(out / "before_after_comparison.json", comparison)
    _write(out / "resource_regression.json", res)
    _write(out / "two_agent_sanity.json", sanity)
    if fallback:
        _write(out / "fallback_0_10_comparison.json", fallback)
    _write(out / "summary.json", summary)

    report = f"""# PASSIVE_TRANSPORT_01 Promotion Report

Physics promotion only. Not agency / navigation / learning / PSC.

## A. Promoted parameter

| parameter | old | new |
|--|--|--|
| `body_orientation.force_scale` | `{PASSIVE_TRANSPORT_FORCE_SCALE_PRE}` | **`{PASSIVE_TRANSPORT_FORCE_SCALE_PROMOTED}`** |

Stronger candidate `{PASSIVE_TRANSPORT_FORCE_SCALE_STRONG}` documented, not promoted.

## B. Why

PASSIVE_TRANSPORT_01 showed WAIT map traversal is dominated by site-path
`force_scale × flow`, not environmental temporal frequency.
Minimal change: scale whole-body advection without retuning climate timing,
flow gain/max, resources, or trickle.

## C. WAIT transport before vs after

| horizon | BEFORE WAIT path | AFTER WAIT path | BEFORE unique | AFTER unique |
|--|--|--|--|--|
| 1k | {pre_1k['WAIT_path']:.2f} | {after_1k['WAIT']['path_distance']['mean']:.2f} | {pre_1k['WAIT_unique']:.1f} | {after_1k['WAIT']['unique_cells']['mean']:.1f} |
| 5k | {pre_5k['WAIT_path']:.2f} | {after_5k['WAIT']['path_distance']['mean']:.2f} | {pre_5k['WAIT_unique']:.1f} | {after_5k['WAIT']['unique_cells']['mean']:.1f} |

Reduction factor (1k path): {comparison['WAIT_path_reduction_factor_1k']}

## D. MOVE after promotion

| horizon | MOVE path | MOVE unique |
|--|--|--|
| 1k | {after_1k['MOVE']['path_distance']['mean']:.2f} | {after_1k['MOVE']['unique_cells']['mean']:.1f} |
| 5k | {after_5k['MOVE']['path_distance']['mean']:.2f} | {after_5k['MOVE']['unique_cells']['mean']:.1f} |

## E. WAIT/MOVE ratios (after)

| horizon | path MOVE/WAIT | unique MOVE/WAIT | WAIT/MOVE path |
|--|--|--|--|
| 1k | {after_1k['ratios']['path_MOVE_over_WAIT']} | {after_1k['ratios']['unique_MOVE_over_WAIT']} | {after_1k['ratios']['path_WAIT_over_MOVE']} |
| 5k | {after_5k['ratios']['path_MOVE_over_WAIT']} | {after_5k['ratios']['unique_MOVE_over_WAIT']} | {after_5k['ratios']['path_WAIT_over_MOVE']} |

## F. Retained local coupling

```json
{json.dumps(coupling, indent=2)}
```

## G. Resource encounters

BEFORE 1k WAIT enc_AB ≈ {pre_1k.get('enc_WAIT')}
AFTER 1k WAIT enc_AB ≈ {after_1k['ratios']['enc_AB_WAIT']}
AFTER 1k MOVE enc_AB ≈ {after_1k['ratios']['enc_AB_MOVE']}

(Passive encounter reduction is expected — prior WAIT transport fed encounters.)

## H. Resource→work regression

```json
{json.dumps(res, indent=2)}
```

## I. TwoAgentRuntime sanity

```json
{json.dumps(sanity, indent=2)}
```

## J. Gates / tests

```json
{json.dumps(g, indent=2)}
```

See TESTS.md for pytest.

## K. Remaining confounds

- Controlled MOVE cycle ≠ learned navigation.
- Unique-cell ratios can lag path ratios under square MOVE patterns.
- ENVIRONMENTAL_TIMESCALE_01 remains a separate question (not changed here).
- No claim of agency, preference, habit, or PSC effects.

Fallback 0.10 run: {"YES — see fallback_0_10_comparison.json" if fallback else "NOT REQUIRED"}
"""
    _write(out / "report.md", report)
    _write(out / "README.md", "# PASSIVE_TRANSPORT_01 promotion\n\nforce_scale 1.0 → 0.15. No commit.\n")
    print(json.dumps({"out_dir": str(out), "gates": g, "after_1k_ratios": after_1k["ratios"],
                      "WAIT_reduction_1k": comparison["WAIT_path_reduction_factor_1k"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
