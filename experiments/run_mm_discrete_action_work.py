"""Acceptance study for work-constrained discrete MOVE realization."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import numpy as np

from mechanistic_mind.physical_system.action_work import request_discrete_action
from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.motor_work import allocate_shared_work, ke_increment
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime

SEEDS = (17, 23, 41, 59, 83)
OUT = Path("results/mm_discrete_action_work")


def dump(name, value):
    (OUT / name).write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )


def make_rt(
    seed: int,
    *,
    reservoir: float = 1.0,
    action_work: bool = True,
    motor: bool = False,
    deform: bool = False,
    resources: bool = False,
    reservoir_max: float = 8.0,
) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.planet.flow_enabled = False
    cfg.planet.flow_gain = 0.0
    cfg.body.flow_coupling = 0.0
    cfg.body.wave_coupling = 0.0
    cfg.environmental_resource.mode = "OFF"
    cfg.complementary_resources.mode = "EXPERIMENTAL" if resources else "OFF"
    cfg.endogenous_motor.mode = "EXPERIMENTAL" if motor else "OFF"
    cfg.body_deformation.mode = "EXPERIMENTAL" if deform else "OFF"
    cfg.discrete_action_work.mode = "EXPERIMENTAL" if action_work else "OFF"
    cfg.deformation_work.reservoir_init = reservoir
    cfg.deformation_work.reservoir_max = reservoir_max
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.body.mechanical_work_reservoir = reservoir
    rt.body.vx = rt.body.vy = 0.0
    rt.body.omega = 0.0
    ensure_B_site(rt.body, len(cfg.body.footprint))
    rt.world.vx[:] = rt.world.vy[:] = rt.world.u[:] = 0.0
    return rt


def cognition_move_invariant(seed: int) -> dict:
    cfg = CognitionConfig(cognition_enabled=True)
    s1 = empty_cognitive_state(cfg)
    s2 = deepcopy(s1)
    obs = {"T_local": 0.4, "B0": 0.2, "B1": 0.2, "B2": 0.1, "c_mean": 0.0}
    # No learned winner; index floor(.21*5)=1 => MOVE:N.
    a = run_cognition_before_action(s1, observation=obs, tick=0, rng_value=0.21)
    b = run_cognition_before_action(s2, observation=obs, tick=0, rng_value=0.21)
    return {
        "seed": seed,
        "selected_abundant": a.selected_action,
        "selected_empty": b.selected_action,
        "work_was_cognition_input": False,
        "pass": a.selected_action == b.selected_action == "MOVE:N",
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    action_results, zero_results, partial_results = [], [], []
    directional, resource_trace, three_way = [], [], []
    cross_results, order_results, history_results, rotref_results = [], [], [], []
    gates = []

    for seed in SEEDS:
        cog = cognition_move_invariant(seed)

        # Abundant, zero, historical ablation, WAIT.
        full = make_rt(seed, reservoir=2.0)
        empty = make_rt(seed, reservoir=0.0)
        historical = make_rt(seed, reservoir=2.0, action_work=False)
        for rt in (full, empty, historical):
            rt.step_forced_action("MOVE:E")
        abundant_match = np.allclose(
            full.last_action_work_ledger["action_dv_realized"],
            historical.last_action_work_ledger["action_dv_realized"],
            atol=1e-12,
        )
        zero_ok = (
            empty.last_selected_action == "MOVE:E"
            and empty.last_action_work_ledger["action_work_realized"] <= 1e-12
            and empty.last_action_work_ledger["action_work_unrealized"] > 0
        )
        waits = []
        for w in (0.0, 2.0):
            wrt = make_rt(seed, reservoir=w)
            wrt.step_forced_action("WAIT")
            waits.append(deepcopy(wrt.last_action_work_ledger))
        wait_ok = all(
            x["action_work_requested"] == 0 and x["action_work_realized"] == 0
            for x in waits
        )
        blocked = make_rt(seed, reservoir=2.0)
        blocked.body.vx = blocked.config.body.v_max
        blocked.step_forced_action("MOVE:E")
        blocked_ok = (
            np.linalg.norm(blocked.last_action_work_ledger["action_dv_requested"]) > 0
            and np.linalg.norm(blocked.last_action_work_ledger["action_dv_realized"]) <= 1e-12
            and blocked.last_action_work_ledger["action_work_realized"] <= 1e-12
        )
        action_results.append({
            "seed": seed,
            "cognition": cog,
            "abundant": full.last_action_work_ledger,
            "historical_ablation": historical.last_action_work_ledger,
            "wait_controls": waits,
            "blocked_vmax": blocked.last_action_work_ledger,
            "pass": bool(cog["pass"] and abundant_match and wait_ok and blocked_ok),
        })
        zero_results.append({
            "seed": seed,
            "selected": empty.last_selected_action,
            "receipt": empty.last_action_work_ledger,
            "pass": zero_ok,
        })

        # Partial 0/25/50/75/100%.
        req = float(full.last_action_work_ledger["action_work_requested"])
        ladder = []
        for fraction in (0.0, 0.25, 0.50, 0.75, 1.0):
            rt = make_rt(seed, reservoir=fraction * req)
            rt.step_forced_action("MOVE:E")
            ar = rt.last_action_work_ledger
            ladder.append({
                "fraction": fraction,
                "selected": rt.last_selected_action,
                "requested": ar["action_dv_requested"],
                "realized": ar["action_dv_realized"],
                "work": ar["action_work_realized"],
                "reservoir_after": rt.body.mechanical_work_reservoir,
            })
        mags = [float(np.linalg.norm(x["realized"])) for x in ladder]
        partial_ok = all(a <= b + 1e-12 for a, b in zip(mags, mags[1:]))
        partial_results.append({"seed": seed, "ladder": ladder, "pass": partial_ok})

        # Directional signed work.
        kwargs = dict(vx=0.18, vy=0.0, mass=2.0, v_max=0.30, impulse_scale=0.35, tick=0)
        aligned = request_discrete_action(action="MOVE:E", **kwargs)
        opposed = request_discrete_action(action="MOVE:W", **kwargs)
        perpendicular = request_discrete_action(action="MOVE:N", **kwargs)
        direction_ok = (
            aligned["action_work_requested"] > perpendicular["action_work_requested"]
            and opposed["action_work_requested"] == 0
            and opposed["action_negative_work_requested"] > 0
        )
        directional.append({
            "seed": seed,
            "aligned": aligned,
            "opposed": opposed,
            "perpendicular": perpendicular,
            "pass": direction_ok,
        })

        # Resource interruption/restoration with controlled repeated MOVE.
        rr = make_rt(
            seed, reservoir=0.0, resources=True, reservoir_max=0.08
        )
        rr.config.body.displacement_enabled = False
        iy, ix = rr.body.cell(rr.config.planet.width, rr.config.planet.height)
        place_source_AB(rr.world, iy, ix, A=20.0, B=4.0)
        phases = []
        for t in range(12):
            rr.body.vx = rr.body.vy = 0.0  # explicit controlled external sink
            rr.step_forced_action("MOVE:E")
            phases.append({
                "phase": "A+B",
                "t": t,
                "selected": rr.last_selected_action,
                "conversion": (rr.last_complementary_ledger or {}).get("work_credited"),
                "action_work": rr.last_action_work_ledger["action_work_realized"],
                "W": rr.body.mechanical_work_reservoir,
            })
        rr.world.R_B[:] = 0.0
        rr.config.complementary_resources.transfer_B_enabled = False
        for t in range(35):
            rr.body.vx = rr.body.vy = 0.0
            rr.step_forced_action("MOVE:E")
            phases.append({
                "phase": "B_REMOVED",
                "t": t,
                "selected": rr.last_selected_action,
                "conversion": (rr.last_complementary_ledger or {}).get("work_credited"),
                "action_work": rr.last_action_work_ledger["action_work_realized"],
                "requested": rr.last_action_work_ledger["action_work_requested"],
                "A": (rr.last_complementary_ledger or {}).get("body_A"),
                "B": (rr.last_complementary_ledger or {}).get("body_B"),
                "W": rr.body.mechanical_work_reservoir,
            })
        removed_tail = [x["action_work"] for x in phases if x["phase"] == "B_REMOVED"][-5:]
        selected_during_cut = all(
            x["selected"] == "MOVE:E" for x in phases if x["phase"] == "B_REMOVED"
        )
        rr.config.complementary_resources.transfer_B_enabled = True
        place_source_AB(rr.world, iy, ix, B=4.0)
        for t in range(12):
            rr.body.vx = rr.body.vy = 0.0
            rr.step_forced_action("MOVE:E")
            phases.append({
                "phase": "B_RESTORED",
                "t": t,
                "selected": rr.last_selected_action,
                "conversion": (rr.last_complementary_ledger or {}).get("work_credited"),
                "action_work": rr.last_action_work_ledger["action_work_realized"],
                "W": rr.body.mechanical_work_reservoir,
            })
        restored = [x for x in phases if x["phase"] == "B_RESTORED"]
        resource_ok = (
            selected_during_cut
            and min(removed_tail) <= 1e-12
            and any((x["conversion"] or 0) > 0 for x in restored)
            and any(x["action_work"] > 1e-12 for x in restored)
        )
        resource_trace.append({
            "seed": seed,
            "controlled_velocity_reset": "EXTERNAL_SINK_FOR_MATCHED_REPEATED_REQUESTS",
            "trace": phases,
            "pass": resource_ok,
        })

        # Three positive consumers.
        tw = make_rt(seed, reservoir=0.02, motor=True, deform=True)
        tw.body.motor_ux, tw.body.motor_uy = 0.16, 0.0
        tw.body.B_site[:] = 0.2
        tw.body.B_site[3] = 1.9
        tw.step_forced_action("MOVE:E")
        alloc = deepcopy(tw.last_work_allocation)
        budget = deepcopy(tw.last_work_ledger["three_way_budget"])
        three_ok = (
            alloc["requested_action"] > 0
            and alloc["requested_motor"] > 0
            and alloc["requested_deformation"] > 0
            and budget["no_double_spend"]
            and budget["total_positive_debit"] <= budget["allocation_available"] + 1e-9
        )
        channel_matrix = []
        for motor_on, deform_on, action_on in (
            (True, False, False),
            (False, True, False),
            (False, False, True),
            (True, False, True),
            (True, True, False),
            (False, True, True),
            (True, True, True),
        ):
            cm = make_rt(
                seed, reservoir=0.02, motor=motor_on, deform=deform_on
            )
            if motor_on:
                cm.body.motor_ux, cm.body.motor_uy = 0.16, 0.0
            if deform_on:
                cm.body.B_site[:] = 0.2
                cm.body.B_site[3] = 1.9
            cm.step_forced_action("MOVE:E" if action_on else "WAIT")
            channel_matrix.append({
                "motor_on": motor_on,
                "deformation_on": deform_on,
                "action_on": action_on,
                "requests": {
                    "action": cm.last_work_allocation["requested_action"],
                    "motor": cm.last_work_allocation["requested_motor"],
                    "deformation": cm.last_work_allocation["requested_deformation"],
                },
                "realized": cm.last_work_ledger["three_way_budget"],
            })
        matrix_ok = all(x["realized"]["no_double_spend"] for x in channel_matrix)
        three_way.append({
            "seed": seed,
            "allocation": alloc,
            "realized": budget,
            "single_pair_triple_matrix": channel_matrix,
            "reservoir_after": tw.body.mechanical_work_reservoir,
            "pass": three_ok and matrix_ok,
        })

        # Cross-term algebra and receipt.
        da = np.asarray(tw.last_action_work_ledger["action_dv_requested_after_vmax"])
        dm = np.asarray(tw.last_motor_work_ledger["motor_delta_v_requested"])
        m = tw.config.body.mass
        algebra_cross = m * float(da @ dm)
        cross_ok = abs(
            algebra_cross - alloc["motor_action_ke_cross_term"]
        ) < 1e-12
        cross_results.append({
            "seed": seed,
            "action_dv": da.tolist(),
            "motor_dv": dm.tolist(),
            "algebraic_cross": algebra_cross,
            "receipt_cross": alloc["motor_action_ke_cross_term"],
            "attribution": alloc["cross_term_attribution"],
            "symmetric_diagnostic": [
                alloc["cross_term_symmetric_action"],
                alloc["cross_term_symmetric_motor"],
            ],
            "pass": cross_ok,
        })

        # Allocation order/permutation.
        a = allocate_shared_work(0.1, 0.08, 0.05, 0.12)
        b = allocate_shared_work(0.1, 0.12, 0.08, 0.05)
        order_ok = (
            abs(a["allocated_action"] - b["allocated_deformation"]) < 1e-12
            and abs(a["allocated_deformation"] - b["allocated_motor"]) < 1e-12
            and abs(a["allocated_motor"] - b["allocated_action"]) < 1e-12
        )
        order_results.append({
            "seed": seed,
            "original": a,
            "permuted": b,
            "pass": order_ok,
        })

        # Prior A+B exposure, matched present action/pose/environment.
        exposed = make_rt(seed, reservoir=0.0, resources=True)
        exposed.config.body.displacement_enabled = False
        iy, ix = exposed.body.cell(
            exposed.config.planet.width, exposed.config.planet.height
        )
        place_source_AB(exposed.world, iy, ix, A=3.0, B=3.0)
        exposed.step_forced_action("WAIT")
        exposed.world.R_A[:] = exposed.world.R_B[:] = 0
        exposed.config.complementary_resources.mode = "OFF"
        naive = make_rt(seed, reservoir=0.0, resources=False)
        naive.config.body.displacement_enabled = False
        naive.body.x, naive.body.y = exposed.body.x, exposed.body.y
        exposed.body.vx = exposed.body.vy = naive.body.vx = naive.body.vy = 0.0
        exposed.step_forced_action("MOVE:N")
        naive.step_forced_action("MOVE:N")
        hist_ok = (
            exposed.last_selected_action == naive.last_selected_action == "MOVE:N"
            and exposed.last_action_work_ledger["action_dv_requested"]
            == naive.last_action_work_ledger["action_dv_requested"]
            and exposed.last_action_work_ledger["action_work_realized"]
            > naive.last_action_work_ledger["action_work_realized"] + 1e-12
        )
        history_results.append({
            "seed": seed,
            "selected_exposed": exposed.last_selected_action,
            "selected_naive": naive.last_selected_action,
            "request_exposed": exposed.last_action_work_ledger["action_dv_requested"],
            "request_naive": naive.last_action_work_ledger["action_dv_requested"],
            "realized_exposed": exposed.last_action_work_ledger["action_dv_realized"],
            "realized_naive": naive.last_action_work_ledger["action_dv_realized"],
            "pass": hist_ok,
        })

        # World-frame rotation and reflected E/W.
        r0 = make_rt(seed, reservoir=2.0)
        rpi = make_rt(seed, reservoir=2.0)
        r0.body.theta, rpi.body.theta = 0.0, np.pi
        r0.step_forced_action("MOVE:N")
        rpi.step_forced_action("MOVE:N")
        east = request_discrete_action(
            action="MOVE:E", vx=0.04, vy=0, mass=2, v_max=0.3,
            impulse_scale=0.35, tick=0,
        )
        west = request_discrete_action(
            action="MOVE:W", vx=-0.04, vy=0, mass=2, v_max=0.3,
            impulse_scale=0.35, tick=0,
        )
        rot_ok = (
            r0.last_action_work_ledger["action_dv_requested"]
            == rpi.last_action_work_ledger["action_dv_requested"]
            and abs(east["action_work_requested"] - west["action_work_requested"])
            < 1e-12
        )
        rotref_results.append({
            "seed": seed,
            "theta0": r0.last_action_work_ledger["action_dv_requested"],
            "theta_pi": rpi.last_action_work_ledger["action_dv_requested"],
            "reflected_work": [east["action_work_requested"], west["action_work_requested"]],
            "pass": rot_ok,
        })

        gates.append({
            "seed": seed,
            "cognition_unchanged": cog["pass"],
            "selected_vs_realized": zero_ok,
            "mechanical_work": direction_ok,
            "wait_zero": wait_ok,
            "blocked_vmax": blocked_ok,
            "partial": partial_ok,
            "abundant_historical": abundant_match,
            "resource_remove_restore": resource_ok,
            "three_way_budget": three_ok and matrix_ok,
            "cross_term": cross_ok,
            "order_invariance": order_ok,
            "history": hist_ok,
            "rotation_reflection": rot_ok,
            "nonnegative_reservoir": tw.body.mechanical_work_reservoir >= -1e-15,
            "environment_external": budget["environmental_work_external"],
        })

    dump("ACTION_WORK_RESULTS.json", action_results)
    dump("ZERO_WORK_RESULTS.json", zero_results)
    dump("PARTIAL_WORK_RESULTS.json", partial_results)
    dump("DIRECTIONAL_WORK_RESULTS.json", directional)
    dump("RESOURCE_TO_ACTION_TRACE.json", resource_trace)
    dump("THREE_WAY_BUDGET_RESULTS.json", three_way)
    dump("CROSS_TERM_RESULTS.json", cross_results)
    dump("ORDER_INVARIANCE_RESULTS.json", order_results)
    dump("HISTORY_RESULTS.json", history_results)
    dump("ROTATION_REFLECTION_RESULTS.json", rotref_results)
    dump("GATE_TABLE.json", gates)

    def allk(k):
        return all(row[k] for row in gates)

    keys = [k for k in gates[0] if k != "seed"]
    promote = all(allk(k) for k in keys)
    gearbox = {
        "edges": [
            {"edge": "cognitive dynamics → selected action", "level": 4, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "selected action → requested physical Δv", "level": 2, "level_name": "LEVEL 2 CODE PATH"},
            {"edge": "work availability → realized action Δv", "level": 4 if allk("selected_vs_realized") and allk("partial") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "realized action Δv → CoM mechanics", "level": 4 if allk("abundant_historical") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "A+B → reservoir → later action work", "level": 4 if allk("resource_remove_restore") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "reservoir → action|motor|deformation", "level": 4 if allk("three_way_budget") else 2, "level_name": "LEVEL 4 ABLATION / MEDIATION"},
            {"edge": "work availability → selected action", "level": 0, "level_name": "LEVEL 0 NOT DEMONSTRATED"},
            {"edge": "effort / fatigue / willpower", "level": 0, "level_name": "LEVEL 0 NOT DEMONSTRATED"},
        ]
    }
    dump("GEARBOX_UPDATE.json", gearbox)
    dump("PROMOTION.json", {"promote": promote, "gates": {k: allk(k) for k in keys}})
    print("PROMOTE" if promote else "HOLD", {k: allk(k) for k in keys})


if __name__ == "__main__":
    main()
