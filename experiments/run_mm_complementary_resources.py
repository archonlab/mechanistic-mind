"""Complementary A/B resources → coupled conversion → work reservoir."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_system.body_orientation import oriented_site_cells
from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime

SEEDS = (17, 23, 41, 59, 83)
OUT = Path("results/mm_complementary_resources")


def dump(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8")


def make_rt(seed: int, **edits) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig(
        cognition=CognitionConfig(cognition_enabled=False),
        endogenous_motor=EndogenousMotorCouplingConfig(mode="OFF"),
    )
    cfg.planet.flow_enabled = False
    cfg.planet.flow_gain = 0.0
    cfg.body.flow_coupling = 0.0
    cfg.body.wave_coupling = 0.0
    cfg.deformation_work.reservoir_init = 0.0
    cfg.environmental_resource.mode = "OFF"
    cfg.morphology_mechanics.local_material_enabled = False
    cfg.morphology_mechanics.internal_site_coupling = False
    for k, v in edits.items():
        setattr(cfg.complementary_resources, k, v)
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.body.vx = rt.body.vy = 0.0
    rt.body.omega = 0.0
    ensure_B_site(rt.body, len(cfg.body.footprint))
    rt.world.vx[:] = rt.world.vy[:] = rt.world.u[:] = 0.0
    return rt


def center(rt):
    return rt.body.cell(rt.config.planet.width, rt.config.planet.height)


def deform_norm(rt) -> float:
    d = getattr(rt.body, "deformation", None)
    if d is None:
        return 0.0
    return float(np.linalg.norm(np.asarray(d)))


def preload(rt, A=0.0, B=0.0):
    n = len(rt.config.body.footprint)
    rt.body.R_A_site = np.zeros(n)
    rt.body.R_B_site = np.zeros(n)
    rt.body.R_A_site[0] = float(A)
    rt.body.R_B_site[0] = float(B)


def drive_deform(rt):
    rt.body.B_site[:] = 0.2
    rt.body.B_site[3] = 1.9


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    complementarity, stoichiometry, transfer_abl, temporal, retention = [], [], [], [], []
    supply, capacity, ledger, traces, rotref, gates = [], [], [], [], [], []

    for seed in SEEDS:
        n_sites = 0
        # 1 A only / 2 B only / 3 A+B
        a_only = make_rt(seed, transfer_A_enabled=False, transfer_B_enabled=False)
        preload(a_only, A=0.8, B=0.0)
        a_only.step()
        b_only = make_rt(seed, transfer_A_enabled=False, transfer_B_enabled=False)
        preload(b_only, A=0.0, B=0.8)
        b_only.step()
        both = make_rt(seed, transfer_A_enabled=False, transfer_B_enabled=False)
        preload(both, A=0.8, B=0.8)
        both.step()
        huge_a = make_rt(seed, transfer_A_enabled=False, transfer_B_enabled=False)
        preload(huge_a, A=8.0, B=0.0)
        huge_a.step()
        huge_b = make_rt(seed, transfer_A_enabled=False, transfer_B_enabled=False)
        preload(huge_b, A=0.0, B=8.0)
        huge_b.step()
        n_sites = len(both.config.body.footprint)
        c_ok = (
            a_only.last_complementary_ledger["work_credited"] == 0.0
            and b_only.last_complementary_ledger["work_credited"] == 0.0
            and both.last_complementary_ledger["work_credited"] > 0
            and huge_a.last_complementary_ledger["work_credited"] == 0.0
            and huge_b.last_complementary_ledger["work_credited"] == 0.0
        )
        complementarity.append({
            "seed": seed,
            "A_only": a_only.last_complementary_ledger["work_credited"],
            "B_only": b_only.last_complementary_ledger["work_credited"],
            "A_plus_B": both.last_complementary_ledger["work_credited"],
            "huge_A_zero_B": huge_a.last_complementary_ledger["work_credited"],
            "huge_B_zero_A": huge_b.last_complementary_ledger["work_credited"],
            "limiting_A_only": a_only.last_complementary_ledger["limiting_resource"],
            "limiting_B_only": b_only.last_complementary_ledger["limiting_resource"],
            "pass": c_ok,
        })

        # 4/5 stoichiometry
        abun_a = make_rt(seed, transfer_A_enabled=False, transfer_B_enabled=False, conversion_rate=0.2, A_passive_loss=0.0, B_passive_loss=0.0)
        preload(abun_a, A=1.0, B=0.07)
        for _ in range(25):
            abun_a.step()
        b_lim = float(abun_a.body.R_B_site[0]) < 1e-8 and float(abun_a.body.R_A_site[0]) > 0.4
        abun_b = make_rt(seed, transfer_A_enabled=False, transfer_B_enabled=False, conversion_rate=0.2, A_passive_loss=0.0, B_passive_loss=0.0)
        preload(abun_b, A=0.07, B=1.0)
        for _ in range(25):
            abun_b.step()
        a_lim = float(abun_b.body.R_A_site[0]) < 1e-8 and float(abun_b.body.R_B_site[0]) > 0.4
        stoichiometry.append({
            "seed": seed,
            "remain_A_when_B_gone": float(abun_a.body.R_A_site[0]),
            "remain_B_when_A_gone": float(abun_b.body.R_B_site[0]),
            "consumed_A_Bscarce": abun_a.last_complementary_ledger["consumed_A"],
            "pass": bool(b_lim and a_lim),
        })

        # 6/7 transfer ablations + local contact
        contact = make_rt(seed, conversion_enabled=False)
        iy, ix = center(contact)
        place_source_AB(contact.world, iy, ix, A=1.0, B=0.8)
        envA0, envB0 = float(contact.world.R_A.sum()), float(contact.world.R_B.sum())
        contact.step()
        cl = contact.last_complementary_ledger
        contact_ok = cl["A"]["acquired"] > 0 and cl["B"]["acquired"] > 0 and float(contact.world.R_A.sum()) < envA0
        aoff = make_rt(seed, transfer_A_enabled=False, conversion_enabled=False)
        place_source_AB(aoff.world, iy, ix, A=1.0, B=1.0)
        aoff.step()
        boff = make_rt(seed, transfer_B_enabled=False, conversion_enabled=False)
        place_source_AB(boff.world, iy, ix, A=1.0, B=1.0)
        boff.step()
        coff = make_rt(seed, conversion_enabled=False, transfer_A_enabled=False, transfer_B_enabled=False, A_passive_loss=0.0, B_passive_loss=0.0)
        preload(coff, A=0.4, B=0.4)
        w0 = coff.body.mechanical_work_reservoir
        coff.step()
        transfer_abl.append({
            "seed": seed,
            "contact": contact_ok,
            "A_off_Aacq": aoff.last_complementary_ledger["A"]["acquired"],
            "A_off_Bacd": aoff.last_complementary_ledger["B"]["acquired"],
            "B_off_Aacq": boff.last_complementary_ledger["A"]["acquired"],
            "B_off_Bacd": boff.last_complementary_ledger["B"]["acquired"],
            "conv_off_work": coff.last_complementary_ledger["work_credited"],
            "pass": (
                contact_ok
                and aoff.last_complementary_ledger["A"]["acquired"] == 0
                and aoff.last_complementary_ledger["B"]["acquired"] > 0
                and boff.last_complementary_ledger["B"]["acquired"] == 0
                and boff.last_complementary_ledger["A"]["acquired"] > 0
                and coff.last_complementary_ledger["work_credited"] == 0
                and abs(coff.body.mechanical_work_reservoir - w0) < 1e-12
            ),
        })

        # 9/10 temporal history
        a_first = make_rt(seed, conversion_enabled=False)
        iy, ix = center(a_first)
        place_source_AB(a_first.world, iy, ix, A=1.2, B=0.0)
        for _ in range(8):
            a_first.step()
        a_first.world.R_A[:] = 0
        a_after_wait_A = float(np.sum(a_first.body.R_A_site))
        for _ in range(12):
            a_first.step()
        a_after_delay = float(np.sum(a_first.body.R_A_site))
        a_first.config.complementary_resources.conversion_enabled = True
        a_first.config.complementary_resources.transfer_A_enabled = False
        place_source_AB(a_first.world, *center(a_first), B=1.0)
        for _ in range(12):
            a_first.step()
        w_a_first = a_first.body.mechanical_work_reservoir

        b_first = make_rt(seed, conversion_enabled=False)
        iy, ix = center(b_first)
        place_source_AB(b_first.world, iy, ix, A=0.0, B=1.2)
        for _ in range(8):
            b_first.step()
        b_first.world.R_B[:] = 0
        b_after_acq = float(np.sum(b_first.body.R_B_site))
        for _ in range(12):
            b_first.step()
        b_after_delay = float(np.sum(b_first.body.R_B_site))
        b_first.config.complementary_resources.conversion_enabled = True
        b_first.config.complementary_resources.transfer_B_enabled = False
        place_source_AB(b_first.world, *center(b_first), A=1.0)
        for _ in range(12):
            b_first.step()
        w_b_first = b_first.body.mechanical_work_reservoir
        hist_ok = w_a_first > 1e-6 and a_after_delay > 0.1 and b_after_delay < b_after_acq and w_a_first > w_b_first
        temporal.append({
            "seed": seed,
            "A_after_wait": a_after_delay,
            "B_after_wait": b_after_delay,
            "W_A_first": w_a_first,
            "W_B_first": w_b_first,
            "A_acquired": a_after_wait_A,
            "B_acquired": b_after_acq,
            "pass": bool(hist_ok),
        })

        # 15 short-lived B
        ret = make_rt(seed, transfer_A_enabled=False, transfer_B_enabled=False, conversion_enabled=False)
        preload(ret, A=1.0, B=0.18)
        b_trace = []
        for t in range(18):
            ret.step()
            b_trace.append(float(np.sum(ret.body.R_B_site)))
        ret.config.complementary_resources.conversion_enabled = True
        w_before = ret.body.mechanical_work_reservoir
        a_remain = float(np.sum(ret.body.R_A_site))
        for _ in range(8):
            ret.step()
        ret_ok = b_trace[-1] < b_trace[0] * 0.2 and a_remain > 0.4 and ret.last_complementary_ledger["work_credited"] <= 1e-9
        retention.append({
            "seed": seed,
            "B_trace": b_trace[::3],
            "A_remain": a_remain,
            "work_after_B_gone": ret.body.mechanical_work_reservoir - w_before,
            "pass": bool(ret_ok),
        })

        # 16–18 B field source interrupt/restore
        src = make_rt(seed, B_env_source_rate=0.002, conversion_enabled=True, A_passive_loss=0.0)
        iy, ix = center(src)
        place_source_AB(src.world, iy, ix, A=4.0, B=0.0)
        src.config.complementary_resources.transfer_A_enabled = True
        conv_on = []
        for t in range(20):
            src.step()
            conv_on.append(float(src.last_complementary_ledger["work_credited"]))
        src.config.complementary_resources.B_env_source_rate = 0.0
        src.world.R_B[:] = 0.0
        conv_off = []
        a_hold = []
        t_limit = None
        for t in range(25):
            src.step()
            cred = float(src.last_complementary_ledger["work_credited"])
            conv_off.append(cred)
            a_hold.append(float(np.sum(src.body.R_A_site)))
            if t_limit is None and cred <= 1e-9 and float(np.sum(src.body.R_B_site)) <= 1e-6:
                t_limit = t
        src.config.complementary_resources.B_env_source_rate = 0.002
        conv_rest = []
        for t in range(20):
            src.step()
            conv_rest.append(float(src.last_complementary_ledger["work_credited"]))
        interrupt_ok = max(conv_on) > 0 and min(conv_off[-5:]) <= 1e-9 and max(conv_rest) > 0 and a_hold[-1] > 0
        supply.append({
            "seed": seed,
            "max_credit_with_source": max(conv_on),
            "t_B_limiting": t_limit,
            "credit_after_cut": conv_off[-1],
            "A_remaining": a_hold[-1],
            "max_credit_restored": max(conv_rest),
            "B_source_input_label": "B_ENV_SOURCE",
            "pass": bool(interrupt_ok),
        })

        # 13/14 capacity
        capA = make_rt(seed, A_site_capacity=0.12, A_transfer_rate=0.25, conversion_enabled=False, A_passive_loss=0.0)
        iy, ix = center(capA)
        place_source_AB(capA.world, iy, ix, A=3.0)
        for _ in range(20):
            capA.step()
        capB = make_rt(seed, B_site_capacity=0.05, B_transfer_rate=0.25, conversion_enabled=False, B_passive_loss=0.0)
        place_source_AB(capB.world, iy, ix, B=3.0)
        for _ in range(20):
            capB.step()
        cap_ok = float(np.max(capA.body.R_A_site)) <= 0.12 + 1e-9 and float(capA.world.R_A[iy, ix]) > 1.0
        cap_ok = cap_ok and float(np.max(capB.body.R_B_site)) <= 0.05 + 1e-9 and float(capB.world.R_B[iy, ix]) > 1.0
        capacity.append({
            "seed": seed,
            "max_A": float(np.max(capA.body.R_A_site)),
            "env_A_left": float(capA.world.R_A[iy, ix]),
            "max_B": float(np.max(capB.body.R_B_site)),
            "env_B_left": float(capB.world.R_B[iy, ix]),
            "pass": bool(cap_ok),
        })

        # 25 deformation consequence
        hi = make_rt(seed, transfer_A_enabled=False, transfer_B_enabled=False, A_passive_loss=0.0, B_passive_loss=0.0)
        lo = make_rt(seed, transfer_A_enabled=False, transfer_B_enabled=False, A_passive_loss=0.0, B_passive_loss=0.0)
        preload(hi, A=0.9, B=0.9)
        preload(lo, A=0.9, B=0.0)
        drive_deform(hi)
        drive_deform(lo)
        for _ in range(18):
            hi.step()
            lo.step()
        deform_ok = deform_norm(hi) > deform_norm(lo) + 1e-6 and hi.body.mechanical_work_reservoir + 1e-9 >= lo.body.mechanical_work_reservoir

        # 24 end-to-end
        ee = make_rt(seed, conversion_enabled=False, A_passive_loss=0.0)
        iy, ix = center(ee)
        stages = []
        place_source_AB(ee.world, iy, ix, A=1.4, B=0.0)
        for t in range(6):
            ee.step()
            stages.append({"phase": 1, "tick": t, "body_A": float(np.sum(ee.body.R_A_site)), "body_B": float(np.sum(ee.body.R_B_site)), "W": ee.body.mechanical_work_reservoir})
        ee.world.R_A[:] = 0
        for t in range(4):
            ee.step()
            stages.append({"phase": "2-3", "tick": 6 + t, "body_A": float(np.sum(ee.body.R_A_site)), "W": ee.body.mechanical_work_reservoir})
        ee.config.complementary_resources.conversion_enabled = True
        ee.config.complementary_resources.transfer_A_enabled = False
        place_source_AB(ee.world, iy, ix, B=0.8)
        for t in range(8):
            ee.step()
            stages.append({"phase": "4-5", "tick": 10 + t, "body_A": float(np.sum(ee.body.R_A_site)), "body_B": float(np.sum(ee.body.R_B_site)), "W": ee.body.mechanical_work_reservoir, "cred": ee.last_complementary_ledger["work_credited"], "lim": ee.last_complementary_ledger["limiting_resource"]})
        drive_deform(ee)
        w_def = ee.body.mechanical_work_reservoir
        d0 = deform_norm(ee)
        for t in range(10):
            ee.step()
            stages.append({"phase": 6, "tick": 18 + t, "W": ee.body.mechanical_work_reservoir, "d": deform_norm(ee)})
        ee.world.R_B[:] = 0
        ee.config.complementary_resources.transfer_B_enabled = False
        for t in range(16):
            ee.step()
            stages.append({"phase": 7, "tick": 28 + t, "body_B": float(np.sum(ee.body.R_B_site)), "body_A": float(np.sum(ee.body.R_A_site)), "cred": ee.last_complementary_ledger["work_credited"]})
        ee.config.complementary_resources.transfer_B_enabled = True
        place_source_AB(ee.world, iy, ix, B=1.0)
        for t in range(8):
            ee.step()
            stages.append({"phase": "8-9", "tick": 44 + t, "body_B": float(np.sum(ee.body.R_B_site)), "cred": ee.last_complementary_ledger["work_credited"], "W": ee.body.mechanical_work_reservoir})
        e2e_ok = w_def > 0 and deform_norm(ee) >= d0 and any(s.get("cred", 0) or 0 > 0 for s in stages if s.get("phase") == "4-5")
        traces.append({"seed": seed, "stages": stages, "pass": bool(e2e_ok)})

        # rotation / reflection
        r0 = make_rt(seed, conversion_enabled=False, A_transfer_rate=0.5)
        cells0 = oriented_site_cells(r0.body, r0.config.planet.width, r0.config.planet.height, r0.config.body.footprint, theta=0.0)
        iy4, ix4 = cells0[4]
        place_source_AB(r0.world, iy4, ix4, A=0.5)
        r0.body.theta = 0.0
        r0.step()
        site4 = float(r0.body.R_A_site[4])
        rpi = make_rt(seed, conversion_enabled=False, A_transfer_rate=0.5)
        rpi.body.theta = np.pi
        place_source_AB(rpi.world, iy4, ix4, A=0.5)
        rpi.step()
        gained_pi = [float(x) for x in rpi.body.R_A_site]
        rf = make_rt(seed, conversion_enabled=False, A_transfer_rate=0.5)
        cellsr = oriented_site_cells(rf.body, rf.config.planet.width, rf.config.planet.height, rf.config.body.footprint, theta=0.0)
        place_source_AB(rf.world, cellsr[3][0], cellsr[3][1], A=0.5)
        rf.step()
        rot_ok = site4 > 1e-6 and max(gained_pi) > 1e-6 and abs(gained_pi[4] - site4) > 1e-9
        ref_ok = float(rf.body.R_A_site[3]) > 1e-6 and float(rf.body.R_A_site[4]) < float(rf.body.R_A_site[3])
        rotref.append({"seed": seed, "theta0_site4": site4, "theta_pi": gained_pi, "reflect_site3": float(rf.body.R_A_site[3]), "pass": bool(rot_ok and ref_ok)})

        motor_sep = abs(contact.body.motor_ux) + abs(contact.body.motor_uy) < 1e-15
        no_r_fallback = True
        fb = make_rt(seed)
        fb.body.R_site = np.full(n_sites or len(fb.config.body.footprint), 2.0)
        fb.config.environmental_resource.mode = "EXPERIMENTAL"
        fb.config.environmental_resource.conversion_enabled = True
        fb.config.environmental_resource.transfer_enabled = False
        wfb = fb.body.mechanical_work_reservoir
        fb.step()
        no_r_fallback = abs(fb.body.mechanical_work_reservoir - wfb) < 1e-12

        ledger.append({
            "seed": seed,
            "contact": {
                "env_A": cl["env_A"], "env_B": cl["env_B"],
                "A_removed": cl["A"]["removed"], "A_acquired": cl["A"]["acquired"], "A_loss": cl["A"]["loss"],
                "B_removed": cl["B"]["removed"], "B_acquired": cl["B"]["acquired"], "B_loss": cl["B"]["loss"],
                "A_passive": cl["A"]["passive_loss"], "B_passive": cl["B"]["passive_loss"],
            },
            "both_conversion": {
                "consumed_A": both.last_complementary_ledger["consumed_A"],
                "consumed_B": both.last_complementary_ledger["consumed_B"],
                "work": both.last_complementary_ledger["work_credited"],
                "loss": both.last_complementary_ledger["conversion_loss_work"],
                "residual": both.last_complementary_ledger["conversion_residual"],
            },
        })

        gates.append({
            "seed": seed,
            "independence_and_complementarity": c_ok,
            "stoichiometry": bool(b_lim and a_lim),
            "transfer_ablation": transfer_abl[-1]["pass"],
            "temporal_history": bool(hist_ok),
            "retention_B": bool(ret_ok),
            "supply_interrupt_restore": bool(interrupt_ok),
            "capacity": bool(cap_ok),
            "deformation": bool(deform_ok),
            "end_to_end": bool(e2e_ok),
            "rotation_reflection": bool(rot_ok and ref_ok),
            "motor_separate": motor_sep,
            "no_single_R_fallback": no_r_fallback,
        })

    dump("COMPLEMENTARITY_RESULTS.json", complementarity)
    dump("STOICHIOMETRY_RESULTS.json", stoichiometry)
    dump("TRANSFER_ABLATIONS.json", transfer_abl)
    dump("TEMPORAL_HISTORY_RESULTS.json", temporal)
    dump("RETENTION_RESULTS.json", retention)
    dump("SUPPLY_INTERRUPTION_RESULTS.json", supply)
    dump("CAPACITY_RESULTS.json", capacity)
    dump("RESOURCE_LEDGER.json", ledger)
    dump("END_TO_END_TRACE.json", traces)
    dump("ROTATION_REFLECTION_RESULTS.json", rotref)
    dump("GATE_TABLE.json", gates)

    def allk(k):
        return all(g[k] for g in gates)

    keys = [k for k in gates[0] if k != "seed"]
    promote = all(allk(k) for k in keys)
    gearbox = {
        "edges": [
            {"edge": "ENV_A → BODY_A (site-local)", "level": 4 if allk("transfer_ablation") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "ENV_B → BODY_B (site-local)", "level": 4 if allk("transfer_ablation") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "BODY_A + BODY_B → complementary conversion", "level": 4 if allk("independence_and_complementarity") and allk("stoichiometry") else 0, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "conversion → mechanical_work_reservoir", "level": 4 if allk("independence_and_complementarity") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "BODY_B → storage/loss", "level": 3 if allk("retention_B") else 0, "level_name": "LEVEL 3 PERTURBATION"},
            {"edge": "reservoir → deformation work", "level": 4 if allk("deformation") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "resource-history-dependent mechanical capacity", "level": 3 if allk("temporal_history") else 0, "level_name": "LEVEL 3 PERTURBATION"},
            {"edge": "hunger / oxygen / metabolism / seeking", "level": 0, "level_name": "LEVEL 0 NOT DEMONSTRATED"},
        ]
    }
    dump("GEARBOX_UPDATE.json", gearbox)
    dump("PROMOTION.json", {"promote": promote, "gates": {k: allk(k) for k in keys}, "multi_body": "NOT TESTED"})
    print("PROMOTE" if promote else "HOLD", {k: allk(k) for k in keys})


if __name__ == "__main__":
    main()
