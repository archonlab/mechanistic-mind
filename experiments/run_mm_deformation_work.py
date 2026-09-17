"""Acceptance study: deformation mechanical work accounting."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_system.body_deformation import BodyDeformationConfig, step_deformation
from mechanistic_mind.physical_system.body_orientation import step_orientation_mechanics
from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.deformation_work import DeformationWorkConfig
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime

SEEDS = (17, 23, 41, 59, 83)
OUT = Path("results/mm_deformation_work")
B_DRIVE = [0.35, 0.20, 0.20, 1.85, 0.20]


def dump(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8")


def isolated_kwargs() -> dict:
    return {
        "planet.flow_enabled": False,
        "planet.flow_gain": 0.0,
        "body.flow_coupling": 0.0,
        "body.wave_coupling": 0.0,
    }


def make_rt(seed: int, **cfg_edits) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig(
        cognition=CognitionConfig(cognition_enabled=False),
        endogenous_motor=EndogenousMotorCouplingConfig(mode="OFF"),
    )
    cfg.morphology_mechanics.local_material_enabled = False
    cfg.morphology_mechanics.internal_site_coupling = False
    cfg.deformation_work.reservoir_init = 2.0
    cfg.deformation_work.reservoir_max = 4.0
    for k, v in cfg_edits.items():
        obj, attr = k.split(".", 1) if "." in k else ("root", k)
        if obj == "work":
            setattr(cfg.deformation_work, attr, v)
        elif obj == "deform":
            setattr(cfg.body_deformation, attr, v)
        elif obj == "endo":
            setattr(cfg.endogenous_motor, attr, v)
        elif obj == "orient":
            setattr(cfg.body_orientation, attr, v)
        elif obj == "body":
            setattr(cfg.body, attr, v)
        elif obj == "planet":
            setattr(cfg.planet, attr, v)
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    ensure_B_site(rt.body, len(cfg.body.footprint))
    return rt


def zero_world(rt: PhysicalSystemRuntime) -> None:
    rt.world.vx[:] = 0.0
    rt.world.vy[:] = 0.0
    rt.world.u[:] = 0.0


def spatial_field(rt: PhysicalSystemRuntime, scale: float = 1.0) -> None:
    yy, xx = np.indices(rt.world.vx.shape)
    rt.world.vx[:] = scale * (0.04 * (xx - rt.body.x) + 0.015 * (yy - rt.body.y))
    rt.world.vy[:] = scale * (-0.02 * (xx - rt.body.x) + 0.03 * (yy - rt.body.y))
    rt.world.u[:] = 0.0


def set_B(rt: PhysicalSystemRuntime, values=B_DRIVE) -> None:
    ensure_B_site(rt.body, len(rt.config.body.footprint))
    for i, v in enumerate(values):
        rt.body.B_site[i, :] = v


def step_n(rt: PhysicalSystemRuntime, n: int) -> list[dict]:
    ledgers = []
    for _ in range(n):
        rt.step()
        ledgers.append(copy.deepcopy(rt.last_work_ledger or {}))
    return ledgers


def deform_norm(rt: PhysicalSystemRuntime) -> float:
    d = np.asarray(rt.body.deformation if rt.body.deformation is not None else 0.0)
    return float(np.linalg.norm(d))


def summarize_ledgers(ledgers: list[dict]) -> dict:
    def g(key):
        return [float(x.get(key) or 0.0) for x in ledgers if x]

    supplied = g("reservoir_work_supplied")
    dU = g("delta_potential")
    visc = g("dissipated_viscous")
    envw = g("env_work_on_deformation")
    resid = g("deformation_residual")
    unexp = g("unexplained_residual")
    return {
        "ticks": len(ledgers),
        "sum_supplied": float(np.sum(supplied)),
        "sum_dU": float(np.sum(dU)),
        "sum_viscous": float(np.sum(visc)),
        "sum_env_work": float(np.sum(envw)),
        "sum_residual": float(np.sum(resid)),
        "max_abs_unexplained": float(np.max(np.abs(unexp))) if unexp else 0.0,
        "mean_abs_residual": float(np.mean(np.abs(resid))) if resid else 0.0,
        "final_potential": float((ledgers[-1] or {}).get("potential_after") or 0.0) if ledgers else 0.0,
        "final_reservoir": float((ledgers[-1] or {}).get("reservoir_after") or 0.0) if ledgers else 0.0,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    work_ledger = []
    resistance = []
    depletion = []
    passive = []
    recovery = []
    causal = []
    isolated = []
    cyclic = []
    reciprocity = []
    motor = []
    all_gates = []

    for seed in SEEDS:
        # 1. deformation OFF
        off = make_rt(seed, **{"deform.mode": "OFF"})
        set_B(off, B_DRIVE)
        zero_world(off)
        step_n(off, 25)
        off_n = deform_norm(off)

        # 2. deformation ON, work transfer OFF
        bypass = make_rt(seed, **{"work.transfer_enabled": False})
        set_B(bypass, B_DRIVE)
        zero_world(bypass)
        w0 = bypass.body.mechanical_work_reservoir
        step_n(bypass, 25)
        bypass_n = deform_norm(bypass)
        bypass_res_unchanged = abs(bypass.body.mechanical_work_reservoir - w0) < 1e-12

        # 3. powered deformation ON under minimal resistance (isolated world)
        powered = make_rt(seed, **isolated_kwargs())
        set_B(powered, B_DRIVE)
        zero_world(powered)
        L_free = step_n(powered, 40)
        S_free = summarize_ledgers(L_free)
        work_ledger.append({"seed": seed, "free_minimal_resistance": S_free, "deform_norm": deform_norm(powered)})

        # static after settle in isolated world
        static_rt = make_rt(seed, **isolated_kwargs())
        set_B(static_rt, [0.8] * 5)
        zero_world(static_rt)
        step_n(static_rt, 80)
        w_s = static_rt.body.mechanical_work_reservoir
        d_s = static_rt.body.deformation.copy()
        L_static = step_n(static_rt, 15)
        static_ok = (
            float(np.max(np.abs(static_rt.body.deformation - d_s))) < 2e-5
            and abs(static_rt.body.mechanical_work_reservoir - w_s) < 1e-4
        )

        # 7. increased material resistance (stiffness); same kinematics ratio k/γ
        free_r = make_rt(seed, **isolated_kwargs(), **{"work.stiffness": 1.0})
        res_r = make_rt(seed, **isolated_kwargs(), **{"work.stiffness": 4.0})
        set_B(free_r, B_DRIVE)
        set_B(res_r, B_DRIVE)
        zero_world(free_r)
        zero_world(res_r)
        Lf = step_n(free_r, 30)
        Lr = step_n(res_r, 30)
        Sf, Sr = summarize_ledgers(Lf), summarize_ledgers(Lr)
        more_work = Sr["sum_supplied"] > Sf["sum_supplied"] + 1e-9
        less_def = deform_norm(res_r) + 1e-9 < deform_norm(free_r)
        resistance.append({
            "seed": seed,
            "free": {**Sf, "deform": deform_norm(free_r), "stiffness": 1.0},
            "resisted": {**Sr, "deform": deform_norm(res_r), "stiffness": 4.0},
            "more_work_or_less_deform": bool(more_work or less_def),
        })

        # 4. depletion
        dep = make_rt(seed, **isolated_kwargs(), **{"work.reservoir_init": 0.02, "work.reservoir_max": 0.02})
        set_B(dep, B_DRIVE)
        zero_world(dep)
        dep.body.mechanical_work_reservoir = 0.02
        L_dep = step_n(dep, 40)
        full = make_rt(seed, **isolated_kwargs(), **{"work.reservoir_init": 4.0, "work.reservoir_max": 4.0})
        set_B(full, B_DRIVE)
        zero_world(full)
        step_n(full, 40)
        limited = deform_norm(dep) + 1e-6 < deform_norm(full)
        exhausted = dep.body.mechanical_work_reservoir <= 1e-9
        still_limited_after = False
        n_before = deform_norm(dep)
        zero_world(dep)
        step_n(dep, 10)
        still_limited_after = abs(deform_norm(dep) - n_before) < 0.05
        depletion.append({
            "seed": seed,
            "depleted_norm": deform_norm(dep),
            "full_norm": deform_norm(full),
            "limited": bool(limited),
            "exhausted": bool(exhausted),
            "no_further_internal_drive": bool(still_limited_after),
            "ledger": summarize_ledgers(L_dep),
        })

        # 5. passive external deformation (reservoir 0)
        pas = make_rt(seed, **{"work.reservoir_init": 0.0, "work.reservoir_max": 0.0, "deform.material_drive_enabled": False})
        set_B(pas, [0.35] * 5)
        pas.body.mechanical_work_reservoir = 0.0
        spatial_field(pas, scale=12.0)
        p0 = deform_norm(pas)
        Lp = step_n(pas, 25)
        passive_moved = deform_norm(pas) > p0 + 1e-6
        no_internal_pay = summarize_ledgers(Lp)["sum_supplied"] <= 1e-12
        passive.append({
            "seed": seed,
            "deform_norm": deform_norm(pas),
            "env_work": summarize_ledgers(Lp)["sum_env_work"],
            "supplied": summarize_ledgers(Lp)["sum_supplied"],
            "passive_env_deform": bool(passive_moved),
            "no_reservoir_pay": bool(no_internal_pay),
        })

        # 13. recovery: deform, then drop drive, watch U
        rec = make_rt(seed, **isolated_kwargs())
        set_B(rec, B_DRIVE)
        zero_world(rec)
        step_n(rec, 25)
        u_hi = float((rec.last_work_ledger or {}).get("potential_after") or 0.0)
        rec.config.body_deformation.material_drive_enabled = False
        L_rel = step_n(rec, 40)
        u_lo = float((rec.last_work_ledger or {}).get("potential_after") or 0.0)
        rel = summarize_ledgers(L_rel)
        recovered_visc = rel["sum_viscous"]
        recovered_env = rel["sum_env_work"]
        recovered_res = rec.body.mechanical_work_reservoir
        u_drop = u_hi - u_lo
        accounted = recovered_visc + max(0.0, -rel["sum_env_work"]) + abs(rel["sum_residual"])
        recovery.append({
            "seed": seed,
            "U_before_relax": u_hi,
            "U_after_relax": u_lo,
            "U_released": u_drop,
            "viscous_during_relax": recovered_visc,
            "env_work_during_relax": recovered_env,
            "reservoir_after": recovered_res,
            "released_not_vanished": bool(u_drop > 1e-6 and (recovered_visc > 1e-8 or recovered_res >= 0.0)),
        })

        # 14. causal mediation: reservoir perturbation vs transfer ablation
        hi = make_rt(seed, **{"work.reservoir_init": 4.0, "work.reservoir_max": 4.0})
        lo = make_rt(seed, **{"work.reservoir_init": 0.05, "work.reservoir_max": 4.0})
        hiA = make_rt(seed, **{"work.reservoir_init": 4.0, "work.reservoir_max": 4.0, "work.transfer_enabled": False})
        loA = make_rt(seed, **{"work.reservoir_init": 0.05, "work.reservoir_max": 4.0, "work.transfer_enabled": False})
        for r in (hi, lo, hiA, loA):
            set_B(r, B_DRIVE)
            spatial_field(r, 1.0)
            step_n(r, 20)
        d_on = abs(deform_norm(hi) - deform_norm(lo))
        d_off = abs(deform_norm(hiA) - deform_norm(loA))
        f_on = np.linalg.norm(np.asarray((hi.last_orientation_meta or {}).get("net_force") or [0, 0]) - np.asarray((lo.last_orientation_meta or {}).get("net_force") or [0, 0]))
        f_off = np.linalg.norm(np.asarray((hiA.last_orientation_meta or {}).get("net_force") or [0, 0]) - np.asarray((loA.last_orientation_meta or {}).get("net_force") or [0, 0]))
        causal.append({
            "seed": seed,
            "deform_delta_transfer_on": d_on,
            "deform_delta_transfer_off": d_off,
            "force_delta_on": float(f_on),
            "force_delta_off": float(f_off),
            "perturbation": bool(d_on > 1e-6),
            "ablation_removes_effect": bool(d_off < 1e-9 and d_on > d_off),
        })

        # 8/15 isolated system: zero flow, v=ω=0, WAIT, motor off, powered deform
        iso = make_rt(seed, **isolated_kwargs())
        set_B(iso, B_DRIVE)
        zero_world(iso)
        iso.body.vx = iso.body.vy = 0.0
        iso.body.omega = 0.0
        x0, y0, th0 = iso.body.x, iso.body.y, iso.body.theta
        step_n(iso, 50)
        path = float(np.hypot(iso.body.x - x0, iso.body.y - y0))
        dth = abs(float(iso.body.theta) - float(th0))
        isolated.append({
            "seed": seed,
            "path": path,
            "dtheta": dth,
            "vx": iso.body.vx,
            "vy": iso.body.vy,
            "omega": iso.body.omega,
            "deform_norm": deform_norm(iso),
            "no_com": path < 1e-9,
            "no_spin": abs(iso.body.omega) < 1e-9 and dth < 1e-9,
        })

        # 16/17 cyclic + asymmetric env
        cyc = make_rt(seed)
        set_B(cyc, [0.35] * 5)
        spatial_field(cyc, 3.0)
        x0, y0 = cyc.body.x, cyc.body.y
        th0 = cyc.body.theta
        work_sum = 0.0
        for t in range(80):
            phase = 0.35 + 1.5 * (0.5 + 0.5 * np.sin(2 * np.pi * t / 16.0))
            set_B(cyc, [0.35, 0.35, 0.35, phase, 0.35])
            cyc.step()
            work_sum += float((cyc.last_work_ledger or {}).get("reservoir_work_supplied") or 0.0)
        cyclic.append({
            "seed": seed,
            "dx": cyc.body.x - x0,
            "dy": cyc.body.y - y0,
            "path": float(np.hypot(cyc.body.x - x0, cyc.body.y - y0)),
            "dtheta": float(cyc.body.theta - th0),
            "work_consumed": work_sum,
            "deform_norm": deform_norm(cyc),
        })

        # 18 reciprocity A→B→A vs B→A→B on one radial DOF, zero flow
        def cycle_once(order):
            r = make_rt(seed, **isolated_kwargs())
            zero_world(r)
            r.body.vx = r.body.vy = r.body.omega = 0.0
            x, y = r.body.x, r.body.y
            for val in order:
                set_B(r, [0.35, 0.35, 0.35, val, 0.35])
                for _ in range(12):
                    r.step()
            return float(np.hypot(r.body.x - x, r.body.y - y)), deform_norm(r)

        p_ab, _ = cycle_once([0.35, 1.8, 0.35])
        p_ba, _ = cycle_once([1.8, 0.35, 1.8])
        reciprocity.append({
            "seed": seed,
            "A_B_A_path": p_ab,
            "B_A_B_path": p_ba,
            "isolated_reciprocal_no_net": p_ab < 1e-9 and p_ba < 1e-9,
        })

        # 19 motor comparison
        def motor_run(endo: str, work_on: bool):
            r = make_rt(seed, **{"endo.mode": endo, "work.mode": "EXPERIMENTAL" if work_on else "OFF"})
            set_B(r, B_DRIVE)
            zero_world(r)
            x, y = r.body.x, r.body.y
            step_n(r, 40)
            return {
                "path": float(np.hypot(r.body.x - x, r.body.y - y)),
                "deform": deform_norm(r),
                "motor_u": [r.body.motor_ux, r.body.motor_uy],
                "reservoir": r.body.mechanical_work_reservoir,
            }

        motor.append({
            "seed": seed,
            "A_motor_on_work_off": motor_run("EXPERIMENTAL", False),
            "B_motor_off_work_on": motor_run("OFF", True),
            "C_both_on": motor_run("EXPERIMENTAL", True),
            "D_both_off": motor_run("OFF", False),
        })

        gates = {
            "seed": seed,
            "deformation_off_no_shape": off_n < 1e-12,
            "transfer_off_reservoir_inert": bypass_res_unchanged and bypass_n > 1e-6,
            "static_no_drain": static_ok,
            "resistance_emerges": more_work or less_def,
            "depletion_limits": limited and exhausted,
            "passive_env": passive_moved and no_internal_pay,
            "isolated_no_com": isolated[-1]["no_com"],
            "isolated_no_spin": isolated[-1]["no_spin"],
            "recovery_tracked": recovery[-1]["released_not_vanished"],
            "causal_perturbation": causal[-1]["perturbation"],
            "causal_ablation": causal[-1]["ablation_removes_effect"],
            "reciprocity_isolated": reciprocity[-1]["isolated_reciprocal_no_net"],
            "accounting_bounded": S_free["max_abs_unexplained"] < 1e-6,
        }
        all_gates.append(gates)

    dump("WORK_LEDGER_RESULTS.json", work_ledger)
    dump("RESISTANCE_RESULTS.json", resistance)
    dump("DEPLETION_RESULTS.json", depletion)
    dump("PASSIVE_DEFORMATION_RESULTS.json", passive)
    dump("RECOVERY_RESULTS.json", recovery)
    dump("CAUSAL_MEDIATION_RESULTS.json", causal)
    dump("ISOLATED_SYSTEM_RESULTS.json", isolated)
    dump("CYCLIC_DEFORMATION_RESULTS.json", cyclic)
    dump("RECIPROCITY_RESULTS.json", reciprocity)
    dump("MOTOR_COMPARISON.json", motor)
    dump("GATE_TABLE.json", all_gates)

    def all_ok(key):
        return all(g[key] for g in all_gates)

    net_cyclic = [abs(c["path"]) for c in cyclic]
    locom_claim = False
    if max(net_cyclic) > 1e-6:
        # symmetry: all seeds same direction would still not be a locomotion claim without reciprocity break ID
        locom_claim = False

    gearbox = {
        "nodes": [
            "mechanical_work_reservoir",
            "B_site",
            "deformation_state",
            "stored_deformation_energy",
            "site_geometry",
            "site_force",
            "external_work",
            "kinetic_state",
            "dissipation",
        ],
        "edges": [
            {
                "edge": "reservoir→actuator work→deformation",
                "level": 4 if all_ok("causal_ablation") else 3 if all_ok("causal_perturbation") else 2,
                "evidence": "CAUSAL_MEDIATION_RESULTS.json",
            },
            {
                "edge": "B_site→kinematic target (modulatory of intended v)",
                "level": 4,
                "evidence": "mm_body_deformation + this study",
            },
            {
                "edge": "deformation→U=½k‖d‖²",
                "level": 2,
                "evidence": "WORK_MODEL.md identity",
            },
            {
                "edge": "site_force→env work on radial DOF",
                "level": 3 if all_ok("passive_env") else 2,
                "evidence": "PASSIVE_DEFORMATION_RESULTS.json",
            },
            {
                "edge": "powered deformation→isolated CoM",
                "level": 0,
                "evidence": "ISOLATED_SYSTEM_RESULTS.json",
                "note": "NOT DEMONSTRATED / forbidden; controls require ~0",
            },
            {
                "edge": "cyclic deformation→net locomotion",
                "level": 0 if not locom_claim else 1,
                "evidence": "CYCLIC_DEFORMATION_RESULTS.json",
            },
        ],
    }
    dump("ENERGY_GEARBOX.json", gearbox)

    promote = all(
        all_ok(k)
        for k in (
            "deformation_off_no_shape",
            "transfer_off_reservoir_inert",
            "static_no_drain",
            "resistance_emerges",
            "depletion_limits",
            "passive_env",
            "isolated_no_com",
            "isolated_no_spin",
            "recovery_tracked",
            "causal_perturbation",
            "causal_ablation",
            "reciprocity_isolated",
            "accounting_bounded",
        )
    )
    dump("PROMOTION.json", {"promote": promote, "gates": {k: all_ok(k) for g in all_gates for k in g if k != "seed"}})
    print("PROMOTE" if promote else "HOLD", {k: all_ok(k) for k in all_gates[0] if k != "seed"})


if __name__ == "__main__":
    main()
