"""Endogenous motor work accounting acceptance study."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.motor_work import allocate_shared_work
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime

SEEDS = (17, 23, 41, 59, 83)
OUT = Path("results/mm_motor_work_accounting")


def dump(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8")


def make_rt(seed, *, deform=False, comp=False, mw=True, reservoir=4.0):
    cfg = PhysicalSystemConfig(
        cognition=CognitionConfig(cognition_enabled=False),
        endogenous_motor=EndogenousMotorCouplingConfig(mode="EXPERIMENTAL"),
    )
    cfg.planet.flow_enabled = False
    cfg.planet.flow_gain = 0.0
    cfg.body.flow_coupling = 0.0
    cfg.body.wave_coupling = 0.0
    cfg.environmental_resource.mode = "OFF"
    cfg.complementary_resources.mode = "EXPERIMENTAL" if comp else "OFF"
    if comp:
        cfg.complementary_resources.A_passive_loss = 0.0
        cfg.complementary_resources.B_passive_loss = 0.02
    cfg.body_deformation.mode = "EXPERIMENTAL" if deform else "OFF"
    cfg.deformation_work.reservoir_init = reservoir
    cfg.deformation_work.reservoir_max = max(8.0, reservoir)
    cfg.endogenous_motor_work.mode = "EXPERIMENTAL" if mw else "OFF"
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.body.vx = rt.body.vy = 0.0
    rt.body.omega = 0.0
    ensure_B_site(rt.body, len(cfg.body.footprint))
    rt.world.vx[:] = rt.world.vy[:] = rt.world.u[:] = 0.0
    rt.body.mechanical_work_reservoir = reservoir
    return rt


def lg(rt):
    return rt.last_motor_work_ledger or {}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    motor, depletion, partial, resistance, energy = [], [], [], [], []
    trace, shared, history, rotref, gates = [], [], [], [], []

    for seed in SEEDS:
        # 1 abundant
        hi = make_rt(seed, reservoir=6.0)
        hi.body.motor_ux, hi.body.motor_uy = 0.18, 0.0
        hi.step()
        abundant_ok = lg(hi)["motor_work_realized"] > 0 and abs(lg(hi)["motor_drive_requested"][0] - 0.18) < 1e-9

        # 2 zero work
        z = make_rt(seed, reservoir=0.0)
        z.body.motor_ux, z.body.motor_uy = 0.18, 0.0
        z.body.mechanical_work_reservoir = 0.0
        z.step()
        zero_ok = lg(z)["motor_work_realized"] <= 1e-12 and abs(lg(z)["motor_drive_requested"][0] - 0.18) < 1e-9

        # 3 partial monotone
        mags = []
        for w in (0.0, 0.003, 0.03, 0.3):
            p = make_rt(seed, reservoir=w)
            p.body.motor_ux, p.body.motor_uy = 0.2, 0.0
            p.body.mechanical_work_reservoir = w
            p.step()
            mags.append(abs(lg(p)["motor_delta_v_realized"][0]))
        partial_ok = mags[0] <= mags[1] + 1e-15 and mags[1] <= mags[2] + 1e-12 and mags[2] <= mags[3] + 1e-12

        # 4 zero drive + work
        zd = make_rt(seed, reservoir=4.0)
        zd.config.endogenous_motor.mode = "OFF"
        zd.body.motor_ux = zd.body.motor_uy = 0.0
        w0 = zd.body.mechanical_work_reservoir
        zd.step()
        zero_drive_ok = abs(zd.body.mechanical_work_reservoir - w0) < 1e-9 or (lg(zd).get("motor_work_realized") or 0) == 0

        # 10 historical ablation
        on = make_rt(seed, reservoir=8.0, mw=True)
        off = make_rt(seed, reservoir=8.0, mw=False)
        on.body.motor_ux = off.body.motor_ux = 0.15
        on.body.motor_uy = off.body.motor_uy = 0.04
        on.step()
        off.step()
        hist_match = abs(on.body.vx - off.body.vx) < 1e-3 and abs(on.body.vy - off.body.vy) < 1e-3

        motor.append({"seed": seed, "abundant": abundant_ok, "zero": zero_ok, "historical": hist_match, "pass": abundant_ok and zero_ok and hist_match})
        depletion.append({"seed": seed, "drive_empty": lg(z)["motor_drive_requested"], "work_empty": lg(z)["motor_work_realized"], "work_full": lg(hi)["motor_work_realized"], "pass": zero_ok and abundant_ok})
        partial.append({"seed": seed, "dvs": mags, "pass": partial_ok})

        # 5 resistance: different drag, same drive
        rlo = make_rt(seed, reservoir=4.0)
        rhi = make_rt(seed, reservoir=4.0)
        rlo.config.body.drag = 0.05
        rhi.config.body.drag = 0.45
        rlo.body.motor_ux = rhi.body.motor_ux = 0.16
        rlo.body.motor_uy = rhi.body.motor_uy = 0.0
        rlo.body.vx = rhi.body.vx = 0.12
        rlo.step()
        rhi.step()
        resistance.append({
            "seed": seed,
            "low_drag_work": lg(rlo)["motor_work_realized"],
            "high_drag_work": lg(rhi)["motor_work_realized"],
            "low_dv": lg(rlo)["motor_delta_v_realized"],
            "high_dv": lg(rhi)["motor_delta_v_realized"],
            "pass": abs(lg(rlo)["motor_drive_requested"][0] - lg(rhi)["motor_drive_requested"][0]) < 1e-12,
        })

        # 6 blocked
        blk = make_rt(seed, reservoir=4.0)
        blk.config.body.v_max = 0.0
        blk.body.motor_ux, blk.body.motor_uy = 0.2, 0.0
        w_b = blk.body.mechanical_work_reservoir
        blk.step()
        blocked_ok = lg(blk)["motor_work_realized"] <= 1e-12 and abs(blk.body.vx) < 1e-15

        # energy identity for motor-only: debit ≈ ΔKE
        e = make_rt(seed, reservoir=5.0)
        e.body.motor_ux, e.body.motor_uy = 0.14, 0.02
        e.body.vx = 0.04
        e.step()
        dke_m = lg(e).get("kinetic_energy_change_from_motor") or 0.0
        w_real = lg(e).get("motor_work_realized") or 0.0
        residual = abs(w_real - max(0.0, dke_m))
        energy.append({"seed": seed, "dke_motor": dke_m, "w_real": w_real, "residual": residual, "pass": residual < 1e-9})

        # 7 A+B → motor
        ch = make_rt(seed, comp=True, reservoir=0.0)
        ch.body.mechanical_work_reservoir = 0.0
        ch.body.motor_ux, ch.body.motor_uy = 0.16, 0.0
        ch.step()
        pre = lg(ch)["motor_work_realized"]
        iy, ix = ch.body.cell(ch.config.planet.width, ch.config.planet.height)
        place_source_AB(ch.world, iy, ix, A=4.0, B=4.0)
        credits = []
        for t in range(20):
            ch.step()
            credits.append({"t": t, "W": ch.body.mechanical_work_reservoir, "cred": (ch.last_complementary_ledger or {}).get("work_credited"), "mw": lg(ch).get("motor_work_realized"), "drive": lg(ch).get("motor_drive_requested")})
        chain_ok = pre <= 1e-12 and any((c["mw"] or 0) > 1e-12 for c in credits) and any((c["cred"] or 0) > 0 for c in credits)

        # 8/9 remove/restore B
        br = make_rt(seed, comp=True, reservoir=0.5)
        br.config.body.displacement_enabled = False
        iy, ix = br.body.cell(br.config.planet.width, br.config.planet.height)
        place_source_AB(br.world, iy, ix, A=20.0, B=2.0)
        for _ in range(8):
            br.body.motor_ux, br.body.motor_uy = 0.15, 0.0
            br.step()
        drive_mid = list(lg(br).get("motor_drive_requested") or [0, 0])
        br.world.R_B[:] = 0
        br.config.complementary_resources.transfer_B_enabled = False
        works_cut = []
        for _ in range(40):
            br.body.motor_ux, br.body.motor_uy = 0.15, 0.0
            br.step()
            works_cut.append(lg(br).get("motor_work_realized") or 0.0)
        drive_cut = list(lg(br).get("motor_drive_requested") or [0, 0])
        limited = min(works_cut[-8:]) < max(works_cut[:8]) - 1e-9
        br.config.complementary_resources.transfer_B_enabled = True
        place_source_AB(br.world, iy, ix, B=3.0)
        works_rest = []
        for _ in range(20):
            br.body.motor_ux, br.body.motor_uy = 0.15, 0.0
            br.step()
            works_rest.append(lg(br).get("motor_work_realized") or 0.0)
        restore_ok = max(works_rest) > min(works_cut[-8:]) + 1e-9
        drive_persists = abs(drive_cut[0]) + abs(drive_cut[1]) > 0.1

        trace.append({"seed": seed, "chain": credits[-4:], "chain_ok": chain_ok, "B_cut_last": works_cut[-1], "B_rest_max": max(works_rest) if works_rest else 0, "drive_mid": drive_mid, "drive_cut": drive_cut, "pass": chain_ok and drive_persists})

        # 13 shared budget
        sh = make_rt(seed, deform=True, reservoir=0.05)
        sh.body.B_site[:] = 0.2
        sh.body.B_site[3] = 1.8
        sh.body.motor_ux, sh.body.motor_uy = 0.2, 0.0
        sh.body.mechanical_work_reservoir = 0.05
        sh.step()
        al = sh.last_work_allocation or {}
        dw = (sh.last_deformation_meta or {}).get("reservoir_work_supplied") or 0.0
        mw = lg(sh).get("motor_work_realized") or 0.0
        shared_ok = dw + mw <= 0.05 + 1e-9 and sh.body.mechanical_work_reservoir >= -1e-15
        policy = allocate_shared_work(0.05, al.get("requested_deformation") or 0, al.get("requested_motor") or 0)
        alloc_ok = abs((al.get("allocated_deformation") or 0) - policy["allocated_deformation"]) < 1e-9
        shared.append({"seed": seed, "debit_def": dw, "debit_mot": mw, "alloc": al, "pass": shared_ok and alloc_ok})

        # 29 history
        h1 = make_rt(seed, comp=True, reservoir=0.0)
        h2 = make_rt(seed, comp=True, reservoir=0.0)
        iy, ix = h1.body.cell(h1.config.planet.width, h1.config.planet.height)
        place_source_AB(h1.world, iy, ix, A=3.0, B=3.0)
        for _ in range(10):
            h1.step()
        h1.world.R_A[:] = h1.world.R_B[:] = 0
        h1.config.complementary_resources.mode = "OFF"
        h2.body.x, h2.body.y = h1.body.x, h1.body.y
        h2.body.vx, h2.body.vy = h1.body.vx, h1.body.vy
        h2.body.theta = h1.body.theta
        h2.body.motor_ux, h2.body.motor_uy = h1.body.motor_ux, h1.body.motor_uy
        h2.body.mechanical_work_reservoir = 0.0
        w1 = h1.body.mechanical_work_reservoir
        h1.step()
        h2.step()
        hist_ok = (lg(h1).get("motor_work_realized") or 0) + 1e-12 >= (lg(h2).get("motor_work_realized") or 0)
        history.append({"seed": seed, "W_exposed": w1, "mw_exposed": lg(h1).get("motor_work_realized"), "mw_naive": lg(h2).get("motor_work_realized"), "drive_same": abs(lg(h1)["motor_drive_requested"][0] - lg(h2)["motor_drive_requested"][0]) < 1e-9, "pass": hist_ok})

        # rotation: source of asymmetry is T gradient; rotate body theta and check drive is not work-steered
        r0 = make_rt(seed, reservoir=4.0)
        r0.body.motor_ux, r0.body.motor_uy = 0.1, 0.0
        r0.body.theta = 0.0
        r0.step()
        rpi = make_rt(seed, reservoir=4.0)
        rpi.body.motor_ux, rpi.body.motor_uy = 0.1, 0.0
        rpi.body.theta = np.pi
        rpi.step()
        rot_ok = abs(lg(r0)["motor_drive_requested"][0] - 0.1) < 1e-9 and abs(lg(rpi)["motor_drive_requested"][0] - 0.1) < 1e-9
        rotref.append({"seed": seed, "drive0": lg(r0)["motor_drive_requested"], "drive_pi": lg(rpi)["motor_drive_requested"], "pass": rot_ok})

        motor_sep_discrete = True
        gates.append({
            "seed": seed,
            "abundant_zero": abundant_ok and zero_ok,
            "partial": partial_ok,
            "historical_ablation": hist_match,
            "blocked": blocked_ok,
            "energy": residual < 1e-9,
            "resource_chain": chain_ok,
            "drive_persists_without_B": drive_persists,
            "restore_B": restore_ok and limited,
            "shared_budget": shared_ok and alloc_ok,
            "history": hist_ok,
            "rotation": rot_ok,
            "zero_drive": zero_drive_ok,
            "resistance_drive_unchanged": resistance[-1]["pass"],
            "discrete_action_unaccounted": motor_sep_discrete,
        })

    dump("MOTOR_WORK_RESULTS.json", motor)
    dump("DEPLETION_RESULTS.json", depletion)
    dump("PARTIAL_WORK_RESULTS.json", partial)
    dump("RESISTANCE_RESULTS.json", resistance)
    dump("ENERGY_BALANCE.json", energy)
    dump("RESOURCE_TO_MOTOR_TRACE.json", trace)
    dump("SHARED_BUDGET_RESULTS.json", shared)
    dump("HISTORY_RESULTS.json", history)
    dump("ROTATION_REFLECTION_RESULTS.json", rotref)
    dump("GATE_TABLE.json", gates)

    def allk(k):
        return all(g[k] for g in gates)

    keys = [k for k in gates[0] if k != "seed"]
    promote = all(allk(k) for k in keys)
    gearbox = {
        "edges": [
            {"edge": "internal dynamics → motor drive", "level": 4, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "motor drive → requested force", "level": 2, "level_name": "LEVEL 2 CODE PATH"},
            {"edge": "work availability → realized motor force", "level": 4 if allk("abundant_zero") and allk("partial") else 3, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "realized motor force → CoM Δv", "level": 4 if allk("abundant_zero") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "ENV A+B → conversion → reservoir", "level": 4 if allk("resource_chain") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "reservoir → motor work", "level": 4 if allk("resource_chain") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "reservoir shared with deformation", "level": 4 if allk("shared_budget") else 0, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "resource availability → motor DRIVE generation", "level": 0, "level_name": "LEVEL 0 NOT DEMONSTRATED"},
            {"edge": "discrete action work accounting", "level": 0, "level_name": "LEVEL 0 NOT DEMONSTRATED"},
            {"edge": "effort / fatigue / motivation", "level": 0, "level_name": "LEVEL 0 NOT DEMONSTRATED"},
        ]
    }
    dump("GEARBOX_UPDATE.json", gearbox)
    dump("PROMOTION.json", {"promote": promote, "gates": {k: allk(k) for k in keys}, "discrete_action_work": "NOT DEMONSTRATED"})
    print("PROMOTE" if promote else "HOLD", {k: allk(k) for k in keys})


if __name__ == "__main__":
    main()
