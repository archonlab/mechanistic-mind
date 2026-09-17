"""Acceptance study: environmental transferable_resource → work reservoir."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_system.body_orientation import oriented_site_cells
from mechanistic_mind.physical_system.cognition import CognitionConfig
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.environmental_resource import ensure_world_R, place_source
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime

SEEDS = (17, 23, 41, 59, 83)
OUT = Path("results/mm_environmental_work_resource")


def dump(name: str, value) -> None:
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8")


def make_rt(seed: int, **edits) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig(
        cognition=CognitionConfig(cognition_enabled=False),
        endogenous_motor=EndogenousMotorCouplingConfig(mode="OFF"),
    )
    cfg.complementary_resources.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.planet.flow_gain = 0.0
    cfg.body.flow_coupling = 0.0
    cfg.body.wave_coupling = 0.0
    cfg.deformation_work.reservoir_init = 0.0
    cfg.morphology_mechanics.local_material_enabled = False
    cfg.morphology_mechanics.internal_site_coupling = False
    for k, v in edits.items():
        obj, attr = k.split(".", 1)
        if obj == "res":
            setattr(cfg.environmental_resource, attr, v)
        elif obj == "work":
            setattr(cfg.deformation_work, attr, v)
        elif obj == "deform":
            setattr(cfg.body_deformation, attr, v)
        elif obj == "orient":
            setattr(cfg.body_orientation, attr, v)
        elif obj == "body":
            setattr(cfg.body, attr, v)
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.body.vx = rt.body.vy = 0.0
    rt.body.omega = 0.0
    ensure_B_site(rt.body, len(cfg.body.footprint))
    ensure_world_R(rt.world)
    rt.world.vx[:] = rt.world.vy[:] = rt.world.u[:] = 0.0
    return rt


def center(rt):
    return rt.body.cell(rt.config.planet.width, rt.config.planet.height)


def deform_norm(rt) -> float:
    d = getattr(rt.body, "deformation", None)
    if d is None:
        return 0.0
    return float(np.linalg.norm(np.asarray(d)))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    transfer, depletion, capacity, conversion = [], [], [], []
    ledger, traces, history, rotref, gates = [], [], [], [], []

    for seed in SEEDS:
        # 1 contact
        c = make_rt(seed)
        iy, ix = center(c)
        place_source(c.world, iy, ix, 1.0)
        env0 = float(c.world.R.sum())
        c.step()
        lg = c.last_resource_ledger
        contact_ok = lg["acquired_by_body"] > 0 and float(c.world.R.sum()) < env0 and abs(lg["transfer_residual"]) < 1e-9
        transfer.append({"seed": seed, "kind": "contact", **{k: lg[k] for k in (
            "removed_from_env", "acquired_by_body", "transfer_loss", "transfer_residual", "active_sites"
        )}, "pass": contact_ok})

        # 2 no contact
        nc = make_rt(seed)
        iy, ix = center(nc)
        place_source(nc.world, (iy + 12) % nc.world.T.shape[0], (ix + 12) % nc.world.T.shape[1], 1.0)
        e0 = float(nc.world.R.sum())
        nc.step()
        nlg = nc.last_resource_ledger
        nocontact_ok = nlg["acquired_by_body"] == 0 and abs(float(nc.world.R.sum()) - e0) < 1e-12
        transfer.append({"seed": seed, "kind": "no_contact", "acquired": nlg["acquired_by_body"], "pass": nocontact_ok})

        # 4 transfer OFF
        toff = make_rt(seed, **{"res.transfer_enabled": False})
        iy, ix = center(toff)
        place_source(toff.world, iy, ix, 1.0)
        e0 = float(toff.world.R.sum())
        toff.step()
        transfer_off_ok = toff.last_resource_ledger["acquired_by_body"] == 0 and abs(float(toff.world.R.sum()) - e0) < 1e-12

        # 3 depletion
        dep = make_rt(seed, **{"res.conversion_enabled": False, "res.transfer_rate": 0.2})
        iy, ix = center(dep)
        place_source(dep.world, iy, ix, 0.35)
        init_stock = 0.35
        acquired_sum = 0.0
        lost_sum = 0.0
        for _ in range(40):
            dep.step()
            acquired_sum += float(dep.last_resource_ledger["acquired_by_body"])
            lost_sum += float(dep.last_resource_ledger["transfer_loss"])
        remain = float(dep.world.R[iy, ix])
        tot = remain + float(np.sum(dep.body.R_site)) + lost_sum
        depletion_ok = remain < 1e-6 and abs(tot - init_stock) < 1e-6
        depletion.append({"seed": seed, "remain": remain, "acquired": acquired_sum, "lost": lost_sum, "budget": tot, "pass": depletion_ok})

        # 8/9 capacity
        cap = make_rt(seed, **{"res.site_capacity": 0.12, "res.transfer_rate": 0.2, "res.conversion_enabled": False})
        iy, ix = center(cap)
        place_source(cap.world, iy, ix, 3.0)
        for _ in range(25):
            cap.step()
        cap_ok = float(np.max(cap.body.R_site)) <= 0.12 + 1e-9 and float(cap.world.R[iy, ix]) > 1.0
        capacity.append({"seed": seed, "max_R_site": float(np.max(cap.body.R_site)), "env_left": float(cap.world.R[iy, ix]), "pass": cap_ok})

        # 5 conversion OFF after acquisition
        coff = make_rt(seed, **{"res.conversion_enabled": False})
        n = len(coff.config.body.footprint)
        coff.body.R_site = np.full(n, 0.5)
        w0 = coff.body.mechanical_work_reservoir
        coff.step()
        conv_off_ok = abs(coff.body.mechanical_work_reservoir - w0) < 1e-12

        # 11 conversion ON away from source
        conv = make_rt(seed, **{"res.transfer_enabled": False})
        conv.body.R_site = np.zeros(n)
        conv.body.R_site[0] = 0.4
        w0 = conv.body.mechanical_work_reservoir
        r0 = float(conv.body.R_site.sum())
        conv.step()
        clg = conv.last_resource_ledger
        conv_ok = conv.body.mechanical_work_reservoir > w0 and float(conv.body.R_site.sum()) < r0 and abs(clg["conversion_residual"]) < 1e-9
        conversion.append({"seed": seed, "work_credited": clg["work_credited"], "converted_R": clg["converted_R"], "loss_work": clg["conversion_loss_work"], "pass": conv_ok and conv_off_ok})

        # no source no work
        empty = make_rt(seed)
        empty.step()
        no_free = empty.last_resource_ledger["work_credited"] == 0.0

        # 13/18 end-to-end trace
        ee = make_rt(seed, **{"res.conversion_rate": 0.08})
        iy, ix = center(ee)
        place_source(ee.world, iy, ix, 0.8)
        stages = []
        for t in range(12):
            ee.step()
            stages.append({"stage": "acquire_convert", "tick": t, "env": float(ee.world.R.sum()), "body_R": float(np.sum(ee.body.R_site)), "W": ee.body.mechanical_work_reservoir, "d": deform_norm(ee), "lg": {
                "acq": ee.last_resource_ledger["acquired_by_body"],
                "cred": ee.last_resource_ledger["work_credited"],
                "sup": (ee.last_work_ledger or {}).get("reservoir_work_supplied"),
            }})
        ee.world.R[:] = 0.0
        for t in range(8):
            ee.step()
            stages.append({"stage": "convert_only", "tick": 12 + t, "env": float(ee.world.R.sum()), "body_R": float(np.sum(ee.body.R_site)), "W": ee.body.mechanical_work_reservoir, "d": deform_norm(ee)})
        # drive deformation with remaining W
        ee.body.B_site[:] = 0.2
        ee.body.B_site[3] = 1.8
        w_before_def = ee.body.mechanical_work_reservoir
        d_before = deform_norm(ee)
        for t in range(20):
            ee.step()
            stages.append({"stage": "deform", "tick": 20 + t, "W": ee.body.mechanical_work_reservoir, "d": deform_norm(ee), "supplied": (ee.last_work_ledger or {}).get("reservoir_work_supplied")})
        e2e_ok = w_before_def > 0 and deform_norm(ee) > d_before and ee.body.mechanical_work_reservoir <= w_before_def + 1e-9
        traces.append({"seed": seed, "stages": stages[-6:], "w_before_def": w_before_def, "d_after": deform_norm(ee), "pass": e2e_ok})

        # 16 more resource → more deformation
        lo = make_rt(seed)
        hi = make_rt(seed)
        lo.body.R_site = np.zeros(n)
        hi.body.R_site = np.zeros(n)
        lo.body.R_site[0] = 0.05
        hi.body.R_site[0] = 0.9
        lo.config.environmental_resource.transfer_enabled = False
        hi.config.environmental_resource.transfer_enabled = False
        for r in (lo, hi):
            r.body.B_site[:] = 0.2
            r.body.B_site[3] = 1.9
            for _ in range(15):
                r.step()
        more_ok = hi.body.mechanical_work_reservoir + 1e-9 >= lo.body.mechanical_work_reservoir and deform_norm(hi) + 1e-9 >= deform_norm(lo)
        # ablation conversion on hi copy
        hiA = make_rt(seed, **{"res.conversion_enabled": False, "res.transfer_enabled": False})
        hiA.body.R_site = np.zeros(n)
        hiA.body.R_site[0] = 0.9
        hiA.body.B_site[:] = 0.2
        hiA.body.B_site[3] = 1.9
        for _ in range(15):
            hiA.step()
        abl_ok = deform_norm(hiA) + 1e-6 < deform_norm(hi) and hiA.body.mechanical_work_reservoir < 1e-9

        # 24 history
        hist_a = make_rt(seed, **{"res.conversion_enabled": False})
        hist_b = make_rt(seed, **{"res.conversion_enabled": False})
        iy, ix = center(hist_a)
        place_source(hist_a.world, iy, ix, 1.5)
        for _ in range(10):
            hist_a.step()
        hist_a.world.R[:] = 0
        hist_a.config.environmental_resource.conversion_enabled = True
        hist_b.config.environmental_resource.conversion_enabled = True
        hist_a.config.environmental_resource.transfer_enabled = False
        hist_b.config.environmental_resource.transfer_enabled = False
        # match pose
        hist_b.body.x, hist_b.body.y = hist_a.body.x, hist_a.body.y
        hist_b.body.vx = hist_a.body.vx
        hist_b.body.vy = hist_a.body.vy
        hist_b.body.theta = hist_a.body.theta
        hist_a.body.B_site[:] = hist_b.body.B_site[:] = 0.25
        hist_a.body.B_site[3] = hist_b.body.B_site[3] = 1.8
        for _ in range(20):
            hist_a.step()
            hist_b.step()
        hist_ok = deform_norm(hist_a) > deform_norm(hist_b) + 1e-6
        history.append({"seed": seed, "exposed_d": deform_norm(hist_a), "naive_d": deform_norm(hist_b), "exposed_W": hist_a.body.mechanical_work_reservoir, "naive_W": hist_b.body.mechanical_work_reservoir, "pass": hist_ok})

        # 27 rotation / reflection of site acquisition
        r0 = make_rt(seed, **{"res.conversion_enabled": False, "res.transfer_rate": 0.5})
        cells0 = oriented_site_cells(r0.body, r0.config.planet.width, r0.config.planet.height, r0.config.body.footprint, theta=0.0)
        iy4, ix4 = cells0[4]
        place_source(r0.world, iy4, ix4, 0.5)
        r0.body.theta = 0.0
        r0.step()
        site4 = float(r0.body.R_site[4])
        rpi = make_rt(seed, **{"res.conversion_enabled": False, "res.transfer_rate": 0.5})
        rpi.body.theta = np.pi
        cells_pi = oriented_site_cells(rpi.body, rpi.config.planet.width, rpi.config.planet.height, rpi.config.body.footprint, theta=np.pi)
        # same world cell as original site 4
        place_source(rpi.world, iy4, ix4, 0.5)
        rpi.step()
        # after π rotation site 3 (XM) occupies former XP world cell
        gained_pi = [float(x) for x in rpi.body.R_site]
        rot_ok = site4 > 1e-6 and max(gained_pi) > 1e-6 and abs(gained_pi[4] - site4) > 1e-9
        # reflection: source at XM cell
        rf = make_rt(seed, **{"res.conversion_enabled": False, "res.transfer_rate": 0.5})
        cellsr = oriented_site_cells(rf.body, rf.config.planet.width, rf.config.planet.height, rf.config.body.footprint, theta=0.0)
        place_source(rf.world, cellsr[3][0], cellsr[3][1], 0.5)
        rf.step()
        ref_ok = float(rf.body.R_site[3]) > 1e-6 and float(rf.body.R_site[4]) < float(rf.body.R_site[3])
        rotref.append({"seed": seed, "theta0_site4": site4, "theta_pi_R": gained_pi, "reflect_site3": float(rf.body.R_site[3]), "pass": bool(rot_ok and ref_ok)})

        # motor_u remains 0
        motor_sep = abs(c.body.motor_ux) + abs(c.body.motor_uy) < 1e-15

        g = {
            "seed": seed,
            "contact": contact_ok,
            "no_contact": nocontact_ok,
            "transfer_off": transfer_off_ok,
            "depletion": depletion_ok,
            "capacity": cap_ok,
            "conversion": conv_ok,
            "conversion_off": conv_off_ok,
            "no_free_work": no_free,
            "end_to_end": e2e_ok,
            "more_resource_more_work": more_ok,
            "conversion_ablation": abl_ok,
            "history": hist_ok,
            "rotation_reflection": bool(rot_ok and ref_ok),
            "motor_separate": motor_sep,
        }
        gates.append(g)
        ledger.append({
            "seed": seed,
            "contact_ledger": lg,
            "conversion_ledger": clg,
        })

    dump("TRANSFER_RESULTS.json", transfer)
    dump("DEPLETION_RESULTS.json", depletion)
    dump("CAPACITY_RESULTS.json", capacity)
    dump("CONVERSION_RESULTS.json", conversion)
    dump("RESOURCE_WORK_LEDGER.json", ledger)
    dump("END_TO_END_TRACE.json", traces)
    dump("HISTORY_RESULTS.json", history)
    dump("ROTATION_REFLECTION_RESULTS.json", rotref)
    dump("GATE_TABLE.json", gates)

    def allk(k):
        return all(g[k] for g in gates)

    keys = [k for k in gates[0] if k != "seed"]
    promote = all(allk(k) for k in keys)
    gearbox = {
        "edges": [
            {"edge": "planet.R → site transfer → R_site", "level": 4 if allk("contact") and allk("transfer_off") and allk("no_contact") else 3, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "R_site → conversion → mechanical_work_reservoir", "level": 4 if allk("conversion") and allk("conversion_off") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "reservoir → deformation work → geometry", "level": 4 if allk("end_to_end") and allk("conversion_ablation") else 3, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "resource history → later deformation capacity", "level": 3 if allk("history") else 0, "level_name": "LEVEL 3 PERTURBATION"},
            {"edge": "seeking / food / metabolism", "level": 0, "level_name": "LEVEL 0 NOT DEMONSTRATED"},
        ]
    }
    dump("GEARBOX_UPDATE.json", gearbox)
    dump("PROMOTION.json", {"promote": promote, "gates": {k: allk(k) for k in keys}, "multi_body": "NOT TESTED"})
    print("PROMOTE" if promote else "HOLD", {k: allk(k) for k in keys})


if __name__ == "__main__":
    main()
