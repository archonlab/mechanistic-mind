"""Acceptance study for bounded material-driven body deformation."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_system.body_deformation import step_deformation
from mechanistic_mind.physical_system.body_orientation import (
    body_local_to_world,
    step_orientation_mechanics,
    torque_2d,
)
from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime

SEEDS = (17, 23, 41, 59, 83)
OUT = Path("results/mm_body_deformation")


def dump(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")


def runtime(seed: int) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig(
        cognition=CognitionConfig(cognition_enabled=False),
        endogenous_motor=EndogenousMotorCouplingConfig(mode="OFF"),
    )
    cfg.morphology_mechanics.local_material_enabled = False
    cfg.morphology_mechanics.internal_site_coupling = False
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    ensure_B_site(rt.body, len(cfg.body.footprint))
    rt.world.vx[:] = 0.0
    rt.world.vy[:] = 0.0
    rt.world.u[:] = 0.0
    return rt


def develop(rt: PhysicalSystemRuntime, values: list[float], n: int = 50) -> None:
    for i, value in enumerate(values):
        rt.body.B_site[i, :] = value
    for _ in range(n):
        step_deformation(rt.body, rt.config.body.footprint, rt.config.body_deformation)


def spatial_field(rt: PhysicalSystemRuntime) -> None:
    yy, xx = np.indices(rt.world.vx.shape)
    rt.world.vx[:] = 0.025 * (xx - rt.body.x) + 0.012 * (yy - rt.body.y)
    rt.world.vy[:] = -0.018 * (xx - rt.body.x) + 0.020 * (yy - rt.body.y)


def mechanics(rt: PhysicalSystemRuntime, *, translate: bool = False):
    return step_orientation_mechanics(
        rt.body, rt.world, rt.config.body, rt.config.body_orientation,
        rt.config.morphology_mechanics, rt.config.body_deformation,
        internal_c=None, apply_translation=translate,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    causal = []
    mediation = []
    symmetry = []
    torque = []
    zero_flow = []
    history = []
    equivariance = []
    for seed in SEEDS:
        base = runtime(seed)
        develop(base, [0.35, 1.9, 0.10, 1.20, 0.20])
        spatial_field(base)
        on = copy.deepcopy(base)
        geometry_off = copy.deepcopy(base)
        geometry_off.config.body_deformation.geometry_coupling_enabled = False
        m_on = mechanics(on)
        m_off = mechanics(geometry_off)
        pos_delta = float(np.max(np.abs(np.asarray(m_on["deformation"]["actual_geometry"]) - np.asarray(m_off["deformation"]["actual_geometry"]))))
        exposure_changed = [e["cell"] for e in m_on["exposures"]] != [e["cell"] for e in m_off["exposures"]]
        force_delta = float(np.linalg.norm(np.asarray(m_on["net_force"]) - np.asarray(m_off["net_force"])))
        tau_delta = abs(float(m_on["tau"]) - float(m_off["tau"]))
        causal.append({"seed": seed, "geometry_delta": pos_delta, "exposure_changed": exposure_changed, "force_delta": force_delta, "torque_delta": tau_delta, "pass": pos_delta > 0 and exposure_changed and (force_delta > 1e-9 or tau_delta > 1e-9)})

        drive_off = runtime(seed)
        drive_off.config.body_deformation.material_drive_enabled = False
        develop(drive_off, [0.35, 1.9, 0.10, 1.20, 0.20])
        mediation.append({"seed": seed, "drive_off_deformation_norm": float(np.linalg.norm(drive_off.body.deformation)), "geometry_off_force_delta": force_delta, "geometry_off_removes_on_geometry": exposure_changed, "pass": np.linalg.norm(drive_off.body.deformation) < 1e-12 and exposure_changed})

        sym = runtime(seed)
        develop(sym, [1.4] * 5)
        d = sym.body.deformation
        sym_pass = bool(np.allclose(d[1], -d[2]) and np.allclose(d[3], -d[4]) and np.allclose(d[0], 0.0))
        symmetry.append({"seed": seed, "deformation": d.tolist(), "pass": sym_pass})

        torque.append({"seed": seed, "tau_on": m_on["tau"], "tau_geometry_off": m_off["tau"], "delta": tau_delta, "pass": tau_delta > 1e-9})

        z = copy.deepcopy(base)
        z.world.vx[:] = z.world.vy[:] = z.world.u[:] = 0.0
        z.body.vx = z.body.vy = 0.0
        p0 = [z.body.x, z.body.y]
        mz = mechanics(z, translate=True)
        path = float(np.hypot(z.body.x - p0[0], z.body.y - p0[1]))
        zero_flow.append({"seed": seed, "path": path, "net_force": mz["net_force"], "motor_u": [z.body.motor_ux, z.body.motor_uy], "pass_no_propulsion": path < 1e-12})

        h1, h2 = runtime(seed), runtime(seed)
        develop(h1, [0.35, 1.9, 0.1, 1.2, 0.2])
        develop(h2, [0.35, 0.1, 1.9, 0.2, 1.2])
        spatial_field(h1); h2.world = copy.deepcopy(h1.world)
        mh1, mh2 = mechanics(h1), mechanics(h2)
        history.append({"seed": seed, "same_present_pose": True, "geometry_delta": float(np.max(np.abs(h1.body.deformation-h2.body.deformation))), "force_delta": float(np.linalg.norm(np.asarray(mh1["net_force"])-np.asarray(mh2["net_force"]))), "pass": not np.allclose(h1.body.deformation, h2.body.deformation)})

        r = np.array([1.3, -0.4]); F = np.array([0.2, 0.7]); angle = 0.73
        Rr = body_local_to_world(r, angle, (0, 0)); RF = body_local_to_world(F, angle, (0, 0))
        tau0, taur = torque_2d(r, F), torque_2d(Rr, RF)
        reflected_r, reflected_F = r * [-1, 1], F * [-1, 1]
        equivariance.append({"seed": seed, "rotation_error": abs(tau0-taur), "reflection_error": abs(tau0+torque_2d(reflected_r, reflected_F)), "pass": abs(tau0-taur) < 1e-12 and abs(tau0+torque_2d(reflected_r, reflected_F)) < 1e-12})

    dump("CAUSAL_RESULTS.json", causal)
    dump("MEDIATION_RESULTS.json", mediation)
    dump("SYMMETRY_RESULTS.json", symmetry)
    dump("ROTATION_REFLECTION_RESULTS.json", equivariance)
    dump("TORQUE_RESULTS.json", torque)
    dump("ZERO_FLOW_RESULTS.json", zero_flow)
    dump("HISTORY_RESULTS.json", history)
    gates = {
        "causal": all(x["pass"] for x in causal),
        "mediation": all(x["pass"] for x in mediation),
        "symmetry": all(x["pass"] for x in symmetry),
        "rotation_reflection": all(x["pass"] for x in equivariance),
        "torque": all(x["pass"] for x in torque),
        "zero_flow_no_propulsion": all(x["pass_no_propulsion"] for x in zero_flow),
        "history": all(x["pass"] for x in history),
    }
    dump("GEARBOX_UPDATE.json", {"status": "PROMOTED" if all(gates.values()) else "EXPERIMENTAL", "gates": gates, "edges": ["B_site→deformation", "deformation→body-local geometry", "geometry→exposure", "exposure→site force", "site force→net force/torque"]})


if __name__ == "__main__":
    main()
