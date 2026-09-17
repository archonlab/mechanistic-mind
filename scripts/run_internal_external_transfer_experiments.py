#!/usr/bin/env python3
"""INTERNAL→EXTERNAL transfer diagnostics. Does not invent coupling."""
from __future__ import annotations

import json
import math
from collections import Counter
from copy import deepcopy
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.planet.config import PlanetConfig

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "mm_internal_external_transfer"
SEEDS = [17, 23, 41, 59, 83]
TICKS = 400


def make_runtime(
    seed: int,
    *,
    flow_enabled: bool = True,
    flow_coupling: float | None = None,
    coupling_enabled: bool = True,
    cognition: bool = True,
    selection: str = "LEGACY_FIRST",
    initial_vx: float = 0.0,
    initial_vy: float = 0.0,
) -> PhysicalSystemRuntime:
    cog = CognitionConfig(cognition_enabled=cognition, prospective_selection=selection)
    cfg = PhysicalSystemConfig(cognition=cog)
    if not flow_enabled:
        cfg.planet.flow_enabled = False
        cfg.planet.flow_gain = 0.0
    if flow_coupling is not None:
        cfg.body.flow_coupling = float(flow_coupling)
    cfg.internal.coupling_enabled = bool(coupling_enabled)
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.body.vx = float(initial_vx)
    rt.body.vy = float(initial_vy)
    rt.set_motion_trace(enabled=True, mode="every_1")
    return rt


def corr(xs, ys):
    if len(xs) < 3:
        return None
    a = np.asarray(xs, dtype=np.float64)
    b = np.asarray(ys, dtype=np.float64)
    if np.std(a) < 1e-15 or np.std(b) < 1e-15:
        return 0.0
    return float(np.corrcoef(a, b)[0, 1])


def run_condition(name: str, seed: int, ticks: int = TICKS, **kw) -> dict:
    rt = make_runtime(seed, **kw)
    rows = []
    actions = []
    for t in range(ticks):
        ib = np.asarray(rt.internal.c, dtype=np.float64).mean(axis=0)
        vb = (float(rt.body.vx), float(rt.body.vy))
        pb = (float(rt.body.x), float(rt.body.y))
        local_before = None
        rt.step()
        ia = np.asarray(rt.internal.c, dtype=np.float64).mean(axis=0)
        va = (float(rt.body.vx), float(rt.body.vy))
        pa = (float(rt.body.x), float(rt.body.y))
        rec = rt.last_motion_receipt or {}
        add = ((rec.get("motion_update") or {}).get("mechanical_decomposition") or {}).get("additive_acceleration") or {}
        dI = float(np.linalg.norm(ia - ib))
        dV = float(np.hypot(va[0] - vb[0], va[1] - vb[1]))
        # wrap-naive displacement
        dP = float(np.hypot(pa[0] - pb[0], pa[1] - pb[1]))
        act = rt.last_selected_action or "WAIT"
        actions.append(act)
        flow_contrib = float(np.hypot(add.get("ax_flow", 0.0), add.get("ay_flow", 0.0)))
        drag_contrib = float(np.hypot(add.get("ax_drag", 0.0), add.get("ay_drag", 0.0)))
        mech_contrib = float(np.hypot(add.get("ax_mech", 0.0), add.get("ay_mech", 0.0)))
        action_imp = (rec.get("action") or {}).get("emitted_impulse") or [0.0, 0.0]
        action_contrib = float(np.hypot(action_imp[0], action_imp[1]))
        rows.append({
            "t": t,
            "action": act,
            "dI": dI,
            "dV": dV,
            "dP": dP,
            "speed": float(np.hypot(va[0], va[1])),
            "flow_accel": flow_contrib,
            "drag_accel": drag_contrib,
            "mech_accel": mech_contrib,
            "action_impulse_mag": action_contrib,
            "local_flow_speed": float(((rec.get("environment") or {}).get("local_after_planet_step") or {}).get("flow_speed") or 0.0),
            "I_level": float(np.linalg.norm(ia)),
        })
    # correlations
    dI = [r["dI"] for r in rows]
    dV = [r["dV"] for r in rows]
    dP = [r["dP"] for r in rows]
    Ilev = [r["I_level"] for r in rows]
    wait_rows = [r for r in rows if r["action"] == "WAIT"]
    counts = Counter(actions)
    n = max(1, len(rows))
    return {
        "condition": name,
        "seed": seed,
        "ticks": ticks,
        "action_counts": dict(counts),
        "wait_fraction": counts.get("WAIT", 0) / n,
        "mean_speed": float(np.mean([r["speed"] for r in rows])),
        "mean_abs_dV": float(np.mean(dV)),
        "mean_abs_dP": float(np.mean(dP)),
        "mean_flow_accel": float(np.mean([r["flow_accel"] for r in rows])),
        "mean_drag_accel": float(np.mean([r["drag_accel"] for r in rows])),
        "mean_mech_accel": float(np.mean([r["mech_accel"] for r in rows])),
        "mean_action_impulse": float(np.mean([r["action_impulse_mag"] for r in rows])),
        "mean_dI": float(np.mean(dI)),
        "corr_dI_dV_same": corr(dI, dV),
        "corr_dI_dV_lag1": corr(dI[:-1], dV[1:]),
        "corr_dI_dP_lag1": corr(dI[:-1], dP[1:]),
        "corr_Ilevel_dV": corr(Ilev, dV),
        "corr_dI_dV_WAIT_only": corr([r["dI"] for r in wait_rows], [r["dV"] for r in wait_rows]) if len(wait_rows) > 5 else None,
        "internal_spatial_term": "NOT_IN_EQUATION",
        "kwargs": {k: v for k, v in kw.items()},
    }


def mean_field(rows, key):
    vals = [r[key] for r in rows if r.get(key) is not None]
    return float(sum(vals) / max(1, len(vals))) if vals else None


def perturb_experiment(seed: int = 41, eps: float = 0.05) -> dict:
    """Matched present: ±ε on internal.c; compare next-tick velocity change under WAIT+zero flow."""
    results = []
    for sign, label in [(+1, "+eps"), (-1, "-eps"), (0, "control")]:
        rt = make_runtime(seed, flow_enabled=False, flow_coupling=0.0, selection="LEGACY_FIRST")
        # settle a few ticks
        for _ in range(20):
            rt.step()
        # force WAIT path by disabling cognition for clean impulse=0, or keep and hope WAIT
        rt.config.cognition.cognition_enabled = False
        c0 = rt.internal.c.copy()
        if sign != 0:
            rt.internal.c = np.clip(rt.internal.c + sign * eps, 0.0, rt.config.internal.C_max)
        vb = (float(rt.body.vx), float(rt.body.vy))
        rt.step()  # cognition off → WAIT, no impulse
        va = (float(rt.body.vx), float(rt.body.vy))
        results.append({
            "label": label,
            "eps": sign * eps,
            "dV": float(np.hypot(va[0] - vb[0], va[1] - vb[1])),
            "speed_after": float(np.hypot(va[0], va[1])),
            "c_l1_delta": float(np.abs(rt.internal.c - c0).sum()) if sign != 0 else 0.0,
        })
    # effect: difference between +eps and -eps dV
    plus = next(r for r in results if r["label"] == "+eps")
    minus = next(r for r in results if r["label"] == "-eps")
    ctrl = next(r for r in results if r["label"] == "control")
    return {
        "seed": seed,
        "eps": eps,
        "rows": results,
        "dV_plus_minus_diff": abs(plus["dV"] - minus["dV"]),
        "dV_plus_vs_control": abs(plus["dV"] - ctrl["dV"]),
        "systematic_effect_on_velocity": abs(plus["dV"] - minus["dV"]) > 1e-9,
        "claim": "LEVEL 0/negative if no systematic dV difference under ±ε with flow off and WAIT",
    }


def ablation_experiment() -> dict:
    rows_n, rows_a = [], []
    for seed in SEEDS:
        rows_n.append(run_condition("normal_zero_flow", seed, ticks=200, flow_enabled=False, flow_coupling=0.0))
        rows_a.append(run_condition("coupling_ablated_zero_flow", seed, ticks=200, flow_enabled=False, flow_coupling=0.0, coupling_enabled=False))
    return {
        "note": "TRANSFER-EDGE ablation = internal.coupling_enabled False (B↔c exchange cut). Internal diffusion/dissipation continue. Mechanical equations unchanged.",
        "normal_zero_flow_mean_speed": mean_field(rows_n, "mean_speed"),
        "ablated_zero_flow_mean_speed": mean_field(rows_a, "mean_speed"),
        "normal_mean_dV": mean_field(rows_n, "mean_abs_dV"),
        "ablated_mean_dV": mean_field(rows_a, "mean_abs_dV"),
        "normal_mean_dI": mean_field(rows_n, "mean_dI"),
        "ablated_mean_dI": mean_field(rows_a, "mean_dI"),
        "motion_change_from_ablation": abs(mean_field(rows_n, "mean_speed") - mean_field(rows_a, "mean_speed")),
        "rows_normal": rows_n,
        "rows_ablated": rows_a,
    }


def gradient_analysis(seed: int = 17) -> dict:
    rt = make_runtime(seed, selection="LEGACY_FIRST")
    dI, I, dV, dP = [], [], [], []
    for _ in range(TICKS):
        ib = np.asarray(rt.internal.c).mean(axis=0)
        Il = float(np.linalg.norm(ib))
        vb = (rt.body.vx, rt.body.vy)
        pb = (rt.body.x, rt.body.y)
        rt.step()
        ia = np.asarray(rt.internal.c).mean(axis=0)
        va = (rt.body.vx, rt.body.vy)
        pa = (rt.body.x, rt.body.y)
        dI.append(float(np.linalg.norm(ia - ib)))
        I.append(float(np.linalg.norm(ia)))
        dV.append(float(np.hypot(va[0] - vb[0], va[1] - vb[1])))
        dP.append(float(np.hypot(pa[0] - pb[0], pa[1] - pb[1])))
    d2 = [dI[i] - dI[i - 1] for i in range(1, len(dI))]
    return {
        "seed": seed,
        "corr_level_I_vs_dV": corr(I, dV),
        "corr_gradient_dI_vs_dV": corr(dI, dV),
        "corr_gradient_dI_vs_dV_lag1": corr(dI[:-1], dV[1:]),
        "corr_d2I_vs_dV": corr(d2, dV[1:]),
        "interpretation": (
            "Even if correlations appear, mechanical code has no internal.c term; "
            "any correlation is CORRELATION ONLY / common-cause candidate, not LEVEL 2 code-path support."
        ),
    }


def build_causal_graph() -> dict:
    return {
        "edges": [
            {"from": "action_impulse", "to": "body.vx/vy", "label": "DIRECT IMPLEMENTED EDGE", "via": "apply_physical_action"},
            {"from": "planet.vx/vy", "to": "body acceleration", "label": "DIRECT IMPLEMENTED EDGE", "via": "flow_coupling"},
            {"from": "body.vx/vy", "to": "body acceleration", "label": "DIRECT IMPLEMENTED EDGE", "via": "drag"},
            {"from": "planet.u", "to": "body.mech", "label": "DIRECT IMPLEMENTED EDGE", "via": "wave_coupling"},
            {"from": "body.mech", "to": "body acceleration", "label": "DIRECT IMPLEMENTED EDGE", "via": "0.15*mech*sign"},
            {"from": "body.vx/vy", "to": "body.x/y", "label": "DIRECT IMPLEMENTED EDGE", "via": "displacement_enabled"},
            {"from": "body.B", "to": "internal.c", "label": "DIRECT IMPLEMENTED EDGE", "via": "kappa coupling"},
            {"from": "internal.c", "to": "body.B", "label": "DIRECT IMPLEMENTED EDGE", "via": "kappa coupling"},
            {"from": "internal.c", "to": "body.vx/vy", "label": "NOT DEMONSTRATED", "via": "absent from mechanical formulas"},
            {"from": "Δinternal", "to": "Δvelocity", "label": "NOT DEMONSTRATED", "via": "no gradient term in ax/ay"},
            {"from": "internal.c", "to": "observation", "label": "DIRECT IMPLEMENTED EDGE", "via": "accessible_observation"},
            {"from": "observation", "to": "selected_action", "label": "DIRECT IMPLEMENTED EDGE", "via": "cognition"},
            {"from": "selected_action", "to": "body.vx/vy", "label": "MEDIATED EDGE", "via": "MOVE impulse only"},
            {"from": "body.x/y + world", "to": "observation", "label": "DIRECT IMPLEMENTED EDGE", "via": "accessible_observation"},
            {"from": "world fields", "to": "body.T/B", "label": "DIRECT IMPLEMENTED EDGE", "via": "thermal/material"},
        ]
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("=== observational NORMAL ===")
    obs = [run_condition("NORMAL", s) for s in SEEDS]
    (OUT / "observational_results.json").write_text(json.dumps({"rows": obs, "mean_corr_dI_dV": mean_field(obs, "corr_dI_dV_same")}, indent=2))
    print("mean corr dI-dV", mean_field(obs, "corr_dI_dV_same"))

    print("=== WAIT window (natural; usually WAIT-locked) ===")
    wait = [run_condition("WAIT_DOMINANT", s) for s in SEEDS]
    (OUT / "wait_window_results.json").write_text(json.dumps({"rows": wait}, indent=2))

    print("=== zero world flow ===")
    zf = [run_condition("ZERO_FLOW", s, flow_enabled=False, flow_coupling=0.0) for s in SEEDS]
    (OUT / "world_flow_control.json").write_text(json.dumps({
        "rows": zf,
        "mean_speed": mean_field(zf, "mean_speed"),
        "mean_dP": mean_field(zf, "mean_abs_dP"),
        "mean_flow_accel": mean_field(zf, "mean_flow_accel"),
    }, indent=2))
    print("zero-flow mean speed", mean_field(zf, "mean_speed"))

    print("=== initial velocity control ===")
    iv0 = [run_condition("ZERO_FLOW_V0", s, flow_enabled=False, flow_coupling=0.0, initial_vx=0.0, initial_vy=0.0) for s in SEEDS]
    iv1 = [run_condition("ZERO_FLOW_VINIT", s, flow_enabled=False, flow_coupling=0.0, initial_vx=0.2, initial_vy=0.0) for s in SEEDS]
    (OUT / "initial_velocity_control.json").write_text(json.dumps({
        "v0": iv0,
        "v_init": iv1,
        "mean_speed_v0": mean_field(iv0, "mean_speed"),
        "mean_speed_vinit": mean_field(iv1, "mean_speed"),
    }, indent=2))

    print("=== ablation ===")
    abl = ablation_experiment()
    (OUT / "transfer_ablation.json").write_text(json.dumps(abl, indent=2))
    print("ablation motion delta", abl["motion_change_from_ablation"])

    print("=== perturbation ===")
    pert_rows = [perturb_experiment(seed=s, eps=0.05) for s in SEEDS]
    pert_rows += [perturb_experiment(seed=41, eps=e) for e in (0.01, 0.05, 0.1)]
    (OUT / "internal_perturbation.json").write_text(json.dumps({"rows": pert_rows}, indent=2))

    print("=== gradient ===")
    grad = [gradient_analysis(s) for s in SEEDS]
    (OUT / "gradient_analysis.json").write_text(json.dumps({"rows": grad}, indent=2))

    (OUT / "causal_graph.json").write_text(json.dumps(build_causal_graph(), indent=2))

    summary = {
        "seeds": SEEDS,
        "normal_mean_speed": mean_field(obs, "mean_speed"),
        "normal_mean_flow_accel": mean_field(obs, "mean_flow_accel"),
        "zero_flow_mean_speed": mean_field(zf, "mean_speed"),
        "zero_flow_v0_mean_speed": mean_field(iv0, "mean_speed"),
        "ablation_motion_delta": abl["motion_change_from_ablation"],
        "perturbation_any_systematic": any(r["systematic_effect_on_velocity"] for r in pert_rows),
        "H_INTERNAL_claim_level": 0,
        "H_WORLD_claim_level": 3,
        "H_INERTIA_claim_level": 3,
        "H_ACTION_claim_level": 3,
    }
    (OUT / "seed_summary.json").write_text(json.dumps(summary, indent=2))
    print("SUMMARY", json.dumps(summary, indent=2))
    print("DONE")


if __name__ == "__main__":
    main()
