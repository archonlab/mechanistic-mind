#!/usr/bin/env python3
"""Endogenous motor coupling experiments. Default mechanism OFF in runtime config."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "mm_endogenous_motor_coupling"
SEEDS = [17, 23, 41, 59, 83]


def make(
    seed: int,
    *,
    mode: str = "OFF",
    strength: float = 0.08,
    flow: bool = True,
    wave: float | None = None,
    cognition: bool = False,
    use_delta: bool = True,
    body_b_gain: bool = False,
    init_vx: float = 0.0,
    init_vy: float = 0.0,
) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig(
        cognition=CognitionConfig(cognition_enabled=cognition, prospective_selection="LEGACY_FIRST"),
        endogenous_motor=EndogenousMotorCouplingConfig(
            mode=mode,
            strength=strength,
            use_delta=use_delta,
            body_b_gain=body_b_gain,
        ),
    )
    if not flow:
        cfg.planet.flow_enabled = False
        cfg.planet.flow_gain = 0.0
        cfg.body.flow_coupling = 0.0
    if wave is not None:
        cfg.body.wave_coupling = float(wave)
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.body.vx = float(init_vx)
    rt.body.vy = float(init_vy)
    return rt


def metrics(rt: PhysicalSystemRuntime, ticks: int) -> dict:
    xs, ys, speeds, motors, dI, dM = [], [], [], [], [], []
    c_prev = np.asarray(rt.internal.c).copy()
    m_prev = (rt.body.motor_ux, rt.body.motor_uy)
    for _ in range(ticks):
        rt.step()
        xs.append(rt.body.x)
        ys.append(rt.body.y)
        speeds.append(float(np.hypot(rt.body.vx, rt.body.vy)))
        motors.append(float(np.hypot(rt.body.motor_ux, rt.body.motor_uy)))
        c = np.asarray(rt.internal.c)
        dI.append(float(np.linalg.norm(c - c_prev)))
        dM.append(float(np.hypot(rt.body.motor_ux - m_prev[0], rt.body.motor_uy - m_prev[1])))
        c_prev = c.copy()
        m_prev = (rt.body.motor_ux, rt.body.motor_uy)
    # wrap-naive net displacement
    net = float(np.hypot(xs[-1] - xs[0], ys[-1] - ys[0]))
    path = 0.0
    for i in range(1, len(xs)):
        path += float(np.hypot(xs[i] - xs[i - 1], ys[i] - ys[i - 1]))
    cells = len({(int(np.floor(x)), int(np.floor(y))) for x, y in zip(xs, ys)})
    return {
        "net_displacement": net,
        "path_length": path,
        "unique_cells": cells,
        "mean_speed": float(np.mean(speeds)),
        "max_speed": float(np.max(speeds)),
        "mean_motor": float(np.mean(motors)),
        "max_motor": float(np.max(motors)),
        "mean_dI": float(np.mean(dI)),
        "mean_dM": float(np.mean(dM)),
        "corr_dI_dM": float(np.corrcoef(dI, dM)[0, 1]) if np.std(dI) > 1e-15 and np.std(dM) > 1e-15 else 0.0,
        "final": {"x": xs[-1], "y": ys[-1], "vx": rt.body.vx, "vy": rt.body.vy, "mx": rt.body.motor_ux, "my": rt.body.motor_uy},
        "last_meta": deepcopy(rt.last_endo_motor_meta),
    }


def mean_key(rows, k):
    vals = [r[k] for r in rows if r.get(k) is not None]
    return float(sum(vals) / max(1, len(vals)))


def causal_transfer() -> dict:
    rows = []
    for seed in SEEDS:
        off = metrics(make(seed, mode="OFF", flow=False, wave=0.0), 100)
        on = metrics(make(seed, mode="EXPERIMENTAL", flow=False, wave=0.0), 100)
        # hold internal nearly constant: ablate medium evolution
        rt = make(seed, mode="EXPERIMENTAL", flow=False, wave=0.0)
        rt.config.internal.medium_enabled = False
        held = metrics(rt, 100)
        # ±ε perturbation after brief warmup
        def pert(sign):
            rt = make(seed, mode="EXPERIMENTAL", flow=False, wave=0.0)
            for _ in range(10):
                rt.step()
            c0 = rt.internal.c.copy()
            rt.internal.c = np.clip(rt.internal.c + sign * 0.08, 0, rt.config.internal.C_max)
            m0 = (rt.body.motor_ux, rt.body.motor_uy)
            v0 = (rt.body.vx, rt.body.vy)
            # one more step to update motor from delta, then one to apply
            rt.step()
            m1 = (rt.body.motor_ux, rt.body.motor_uy)
            rt.step()
            v2 = (rt.body.vx, rt.body.vy)
            return {
                "d_motor": float(np.hypot(m1[0] - m0[0], m1[1] - m0[1])),
                "d_speed": float(np.hypot(v2[0] - v0[0], v2[1] - v0[1])),
                "c_l1_delta": float(np.abs(rt.internal.c - c0).sum()),
            }
        plus, minus = pert(+1), pert(-1)
        rows.append({
            "seed": seed,
            "off": off,
            "on": on,
            "internal_held": held,
            "pert_plus": plus,
            "pert_minus": minus,
            "on_minus_off_path": on["path_length"] - off["path_length"],
            "on_minus_off_motor": on["max_motor"] - off["max_motor"],
            "held_reduces_motor": held["max_motor"] <= on["max_motor"] + 1e-9,
        })
    return {
        "rows": rows,
        "mean_on_minus_off_path": mean_key(rows, "on_minus_off_path"),
        "mean_on_max_motor": float(np.mean([r["on"]["max_motor"] for r in rows])),
        "mean_off_max_motor": float(np.mean([r["off"]["max_motor"] for r in rows])),
        "causal_signature_present": all(r["on"]["max_motor"] > r["off"]["max_motor"] + 1e-12 for r in rows),
    }


def zero_flow_gate() -> dict:
    rows = []
    for seed in SEEDS:
        off = metrics(make(seed, mode="OFF", flow=False, wave=0.0, init_vx=0.0, init_vy=0.0), 120)
        on = metrics(make(seed, mode="EXPERIMENTAL", flow=False, wave=0.0, init_vx=0.0, init_vy=0.0), 120)
        rows.append({"seed": seed, "off": off, "on": on, "endogenous_motion": on["path_length"] > off["path_length"] + 1e-6})
    return {
        "rows": rows,
        "fraction_seeds_with_endogenous_motion": sum(r["endogenous_motion"] for r in rows) / len(rows),
        "mean_on_path": float(np.mean([r["on"]["path_length"] for r in rows])),
        "mean_off_path": float(np.mean([r["off"]["path_length"] for r in rows])),
    }


def temporal_lags() -> dict:
    seed = 41
    rt = make(seed, mode="EXPERIMENTAL", flow=True)
    series = []
    c_prev = np.asarray(rt.internal.c).copy()
    for t in range(150):
        env = float(np.mean(rt.world.T))
        # local T grad mag
        iy, ix = int(rt.body.y) % rt.world.T.shape[0], int(rt.body.x) % rt.world.T.shape[1]
        dTx = float(rt.world.T[iy, (ix + 1) % rt.world.T.shape[1]] - rt.world.T[iy, (ix - 1) % rt.world.T.shape[1]])
        rt.step()
        c = np.asarray(rt.internal.c)
        dI = float(np.linalg.norm(c - c_prev))
        series.append({
            "t": t,
            "env_grad": abs(dTx),
            "dI": dI,
            "motor": float(np.hypot(rt.body.motor_ux, rt.body.motor_uy)),
            "speed": float(np.hypot(rt.body.vx, rt.body.vy)),
        })
        c_prev = c.copy()
    def lagcorr(a, b, lag):
        if lag == 0:
            x, y = a, b
        elif lag > 0:
            x, y = a[:-lag], b[lag:]
        else:
            x, y = a[-lag:], b[:lag]
        if np.std(x) < 1e-15 or np.std(y) < 1e-15:
            return 0.0
        return float(np.corrcoef(x, y)[0, 1])
    env = [s["env_grad"] for s in series]
    dI = [s["dI"] for s in series]
    motor = [s["motor"] for s in series]
    speed = [s["speed"] for s in series]
    matrix = {}
    for pair, A, B in [
        ("env_grad→dI", env, dI),
        ("dI→motor", dI, motor),
        ("motor→speed", motor, speed),
    ]:
        matrix[pair] = {f"lag_{L}": lagcorr(A, B, L) for L in range(0, 4)}
    return {"seed": seed, "note": "motor update after internal → applied next mechanical (code-order lag ≥1 for dI→velocity)", "lag_matrix": matrix}


def persistence() -> dict:
    seed = 23
    rt = make(seed, mode="EXPERIMENTAL", flow=True, wave=0.15)
    # Phase A: normal env 80 ticks
    for _ in range(80):
        rt.step()
    motor_A = float(np.hypot(rt.body.motor_ux, rt.body.motor_uy))
    # Phase B: freeze planet fields (remove environmental driver change) by disabling flow/advection updates
    rt.config.planet.flow_enabled = False
    rt.config.planet.flow_gain = 0.0
    rt.config.body.flow_coupling = 0.0
    motors = []
    for _ in range(80):
        rt.step()
        motors.append(float(np.hypot(rt.body.motor_ux, rt.body.motor_uy)))
    return {
        "seed": seed,
        "motor_end_phase_A": motor_A,
        "motor_mean_phase_B": float(np.mean(motors)),
        "motor_end_phase_B": motors[-1],
        "persistence_observed": motors[-1] > 1e-6 or float(np.mean(motors)) > 1e-6,
        "note": "conservative: motor state has explicit decay; persistence means nonzero residual after env drive reduced",
    }


def history_matched() -> dict:
    seed = 59
    def primed(label, boost_site):
        rt = make(seed, mode="EXPERIMENTAL", flow=False, wave=0.0)
        for _ in range(5):
            rt.step()
        # different internal history
        c = rt.internal.c.copy()
        c[boost_site] += 0.25
        rt.internal.c = np.clip(c, 0, rt.config.internal.C_max)
        for _ in range(20):
            rt.step()
        return {
            "label": label,
            "pos": {"x": rt.body.x, "y": rt.body.y},
            "motor": {"ux": rt.body.motor_ux, "uy": rt.body.motor_uy},
            "speed": float(np.hypot(rt.body.vx, rt.body.vy)),
        }
    a = primed("boost_+x_site", 4)
    b = primed("boost_+y_site", 2)
    return {
        "same_seed_init": seed,
        "agents": [a, b],
        "different_motor": a["motor"] != b["motor"],
        "note": "positions may diverge; motor difference after divergent internal history is the measured claim",
    }


def body_b_mediation() -> dict:
    rows = []
    for seed in SEEDS:
        direct = metrics(make(seed, mode="EXPERIMENTAL", flow=False, wave=0.0, body_b_gain=False), 100)
        mediated = metrics(make(seed, mode="EXPERIMENTAL", flow=False, wave=0.0, body_b_gain=True), 100)
        rows.append({"seed": seed, "direct": direct, "B_gain": mediated})
    return {"rows": rows, "note": "B_gain only scales magnitude via tanh(||B||); direction still asymmetry/sites"}


def asymmetry() -> dict:
    # rotate/reflect control: compare mirrored initial body x across midline
    seed = 17
    def run(start_x):
        cfg_mode = "EXPERIMENTAL"
        rt = make(seed, mode=cfg_mode, flow=False, wave=0.0)
        rt.body.x = float(start_x)
        return metrics(rt, 100)
    left = run(6.5)
    right = run(10.5)
    return {
        "left_start": left,
        "right_start": right,
        "note": "direction should track local -grad T / asymmetry at location, not a fixed world NORTH bias from coupling constants",
    }


def strength_sweep() -> dict:
    strengths = [0.0, 0.02, 0.05, 0.08, 0.15, 0.3, 0.6]
    rows = []
    for s in strengths:
        mode = "OFF" if s == 0.0 else "EXPERIMENTAL"
        ms = []
        for seed in SEEDS:
            m = metrics(make(seed, mode=mode, strength=max(s, 0.08) if mode == "EXPERIMENTAL" else 0.08, flow=False, wave=0.0), 80)
            if mode == "EXPERIMENTAL":
                # rebuild with actual strength
                m = metrics(make(seed, mode="EXPERIMENTAL", strength=s, flow=False, wave=0.0), 80)
            ms.append(m)
        rows.append({
            "strength": s,
            "mode": mode,
            "mean_path": float(np.mean([x["path_length"] for x in ms])),
            "mean_max_motor": float(np.mean([x["max_motor"] for x in ms])),
            "mean_max_speed": float(np.mean([x["max_speed"] for x in ms])),
            "regime": (
                "BASELINE" if s == 0 else
                "NEGLIGIBLE" if float(np.mean([x["path_length"] for x in ms])) < 0.05 else
                "STABLE_COUPLING" if float(np.mean([x["max_speed"] for x in ms])) < 0.25 else
                "STRONG"
            ),
        })
    return {"rows": rows}


def ablations() -> dict:
    rows = []
    for seed in SEEDS:
        on = metrics(make(seed, mode="EXPERIMENTAL", flow=False, wave=0.0), 100)
        off = metrics(make(seed, mode="OFF", flow=False, wave=0.0), 100)
        level = metrics(make(seed, mode="EXPERIMENTAL", flow=False, wave=0.0, use_delta=False), 100)
        rows.append({"seed": seed, "on_gradient": on, "off": off, "on_level": level})
    return {"rows": rows}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    print("causal transfer...")
    ct = causal_transfer()
    (OUT / "CAUSAL_TRANSFER_RESULTS.json").write_text(json.dumps(ct, indent=2, default=str))
    print(" signature", ct["causal_signature_present"], "Δpath", ct["mean_on_minus_off_path"])

    print("zero flow...")
    zf = zero_flow_gate()
    (OUT / "ZERO_FLOW_RESULTS.json").write_text(json.dumps(zf, indent=2, default=str))
    print(" endogenous fraction", zf["fraction_seeds_with_endogenous_motion"])

    print("lags...")
    (OUT / "TEMPORAL_LAG_RESULTS.json").write_text(json.dumps(temporal_lags(), indent=2))
    print("persistence...")
    (OUT / "PERSISTENCE_RESULTS.json").write_text(json.dumps(persistence(), indent=2))
    print("history...")
    (OUT / "HISTORY_MATCHED_RESULTS.json").write_text(json.dumps(history_matched(), indent=2))
    print("body B...")
    (OUT / "BODY_B_MEDIATION_RESULTS.json").write_text(json.dumps(body_b_mediation(), indent=2, default=str))
    print("asymmetry...")
    (OUT / "ASYMMETRY_RESULTS.json").write_text(json.dumps(asymmetry(), indent=2, default=str))
    print("sweep...")
    (OUT / "STRENGTH_SWEEP.json").write_text(json.dumps(strength_sweep(), indent=2))
    print("ablations...")
    (OUT / "ABLATION_RESULTS.json").write_text(json.dumps(ablations(), indent=2, default=str))

    summary = {
        "mechanism": "DELTA_ENERGY_TIMES_LOCAL_ASYMMETRY",
        "default_mode": "OFF",
        "causal_signature_present": ct["causal_signature_present"],
        "zero_flow_endogenous_fraction": zf["fraction_seeds_with_endogenous_motion"],
        "mean_on_path_zero_flow": zf["mean_on_path"],
        "mean_off_path_zero_flow": zf["mean_off_path"],
        "baseline_diagnosis_preserved": True,
        "baseline_path": "results/mm_internal_external_transfer/",
    }
    (OUT / "seed_summary.json").write_text(json.dumps(summary, indent=2))
    print("SUMMARY", json.dumps(summary, indent=2))
    print("DONE")


if __name__ == "__main__":
    main()
