#!/usr/bin/env python3
"""Update 4.5.1 — dynamic activity capacity / state-dependent motor cost diagnostics.

No MOVE/WAIT rewards. Compact JSON only.
"""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig, BodyEngine, BodyState
from mechanistic_mind.research.motor_control import MotorControlConfig, variation_body_cost
from contextual_object_ecology_v034 import todo4_calibrated_body_config

OUT = ROOT / "results" / "update451_activity_physiology_v0451"


def _cfg(recovery: bool = True) -> BodyConfig:
    base = todo4_calibrated_body_config()
    # Unpack via asdict-like fields
    d = {f: getattr(base, f) for f in base.__dataclass_fields__}
    d["recovery_dynamics_enabled"] = recovery
    return BodyConfig(**d)


def identical_demand_matrix(eng: BodyEngine) -> dict:
    demand = 1.0
    cases = {
        "A_fresh": BodyState(activity_load=0.0, fatigue=0.10, energy_reserve=0.80, hydration=0.78),
        "B_moderate": BodyState(activity_load=0.35, fatigue=0.20, energy_reserve=0.80, hydration=0.78),
        "C_sustained": BodyState(activity_load=0.80, fatigue=0.45, energy_reserve=0.80, hydration=0.78),
        "D_post_recovery": None,  # filled below
        "E_prolonged_inactivity": None,
        "F_low_reserve": BodyState(activity_load=0.20, fatigue=0.20, energy_reserve=0.25, hydration=0.40),
        "G_adequate_reserve": BodyState(activity_load=0.20, fatigue=0.20, energy_reserve=0.85, hydration=0.80),
    }
    # D: load then recover
    s = BodyState(activity_load=0.0, fatigue=0.10, energy_reserve=0.80, hydration=0.78)
    for _ in range(10):
        s = eng.transition(s, action=Action("WAIT"), distance=0.0, external_effects={"motor_demand_effort": 1.0}).state
    for _ in range(20):
        s = eng.transition(s, action=Action("WAIT"), distance=0.0).state
    cases["D_post_recovery"] = s
    # E: prolonged inactivity from moderate load
    s = BodyState(activity_load=0.5, fatigue=0.25, energy_reserve=0.80, hydration=0.78)
    for _ in range(40):
        s = eng.transition(s, action=Action("WAIT"), distance=0.0).state
    cases["E_prolonged_inactivity"] = s

    out = {}
    for name, state in cases.items():
        before = state.clone()
        tr = eng.transition(
            before,
            action=Action("WAIT"),
            distance=0.0,
            external_effects={"motor_demand_effort": demand},
        )
        after = tr.state
        out[name] = {
            "before": {
                "load": before.activity_load,
                "capacity": before.activity_capacity,
                "energy": before.energy_reserve,
                "hydration": before.hydration,
                "fatigue": before.fatigue,
            },
            "after": {
                "load": after.activity_load,
                "capacity": after.activity_capacity,
                "energy": after.energy_reserve,
                "hydration": after.hydration,
                "fatigue": after.fatigue,
            },
            "deltas": {
                "energy": after.energy_reserve - before.energy_reserve,
                "hydration": after.hydration - before.hydration,
                "fatigue": after.fatigue - before.fatigue,
                "load": after.activity_load - before.activity_load,
                "capacity": after.activity_capacity - before.activity_capacity,
            },
            "motor_demand": demand,
        }
    return out


def activity_cycle(eng: BodyEngine) -> dict:
    s = BodyState(activity_load=0.0, fatigue=0.10, energy_reserve=0.90, hydration=0.85)
    def probe(state):
        b = state.clone()
        a = eng.transition(b, action=Action("WAIT"), distance=0.0, external_effects={"motor_demand_effort": 1.0}).state
        return {
            "energy_delta": a.energy_reserve - b.energy_reserve,
            "fatigue_delta": a.fatigue - b.fatigue,
            "load_before": b.activity_load,
            "capacity_before": b.activity_capacity,
        }
    first = probe(s)
    # sustain activity
    for _ in range(12):
        s = eng.transition(s, action=Action("WAIT"), distance=0.0, external_effects={"motor_demand_effort": 1.0}).state
    mid = {"load": s.activity_load, "capacity": s.activity_capacity, "energy": s.energy_reserve, "fatigue": s.fatigue}
    mid_probe = probe(s)
    # reduced demand recovery
    for _ in range(25):
        s = eng.transition(s, action=Action("WAIT"), distance=0.0).state
    recovered = {"load": s.activity_load, "capacity": s.activity_capacity, "energy": s.energy_reserve, "fatigue": s.fatigue}
    final = probe(s)
    return {
        "first_identical_demand": first,
        "after_sustained": mid,
        "mid_identical_demand": mid_probe,
        "after_recovery": recovered,
        "final_identical_demand": final,
        "history_dependence": abs(first["energy_delta"] - mid_probe["energy_delta"]) > 1e-6,
        "recovery_restores_toward_first": abs(final["energy_delta"]) <= abs(mid_probe["energy_delta"]) + 1e-9,
    }


def conservation_tests(eng: BodyEngine) -> dict:
    # Prolonged WAIT: energy must not increase
    s = BodyState(activity_load=0.4, fatigue=0.3, energy_reserve=0.55, hydration=0.60)
    e0, h0 = s.energy_reserve, s.hydration
    for _ in range(50):
        s = eng.transition(s, action=Action("WAIT"), distance=0.0).state
    wait_ok = s.energy_reserve <= e0 + 1e-12 and s.hydration <= h0 + 1e-12
    # Activity/recovery cycles must not create metabolic resources
    s = BodyState(activity_load=0.0, fatigue=0.2, energy_reserve=0.70, hydration=0.70)
    e0, h0 = s.energy_reserve, s.hydration
    for _ in range(12):
        for _ in range(4):
            s = eng.transition(s, action=Action("WAIT"), distance=0.0, external_effects={"motor_demand_effort": 0.7}).state
        for _ in range(4):
            s = eng.transition(s, action=Action("WAIT"), distance=0.0).state
    cycle_ok = s.energy_reserve <= e0 + 1e-12 and s.hydration <= h0 + 1e-12
    return {
        "prolonged_wait_no_energy_creation": wait_ok,
        "wait_energy_final": s.energy_reserve if False else None,  # placeholder overwritten
        "cycle_no_metabolic_creation": cycle_ok,
        "cycle_energy_start": e0,
        "cycle_energy_final": s.energy_reserve,
        "cycle_hydration_final": s.hydration,
        "prolonged_wait_energy_ok": wait_ok,
    }


def move_accounting(eng: BodyEngine) -> dict:
    fresh = eng.movement_cost(BodyState(activity_load=0.0, fatigue=0.1), distance=1.0)
    loaded = eng.movement_cost(BodyState(activity_load=0.85, fatigue=0.1), distance=1.0)
    cfg = MotorControlConfig()
    mf = variation_body_cost([0.25, -0.1], cfg, activity_load=0.0, fatigue=0.1)
    ml = variation_body_cost([0.25, -0.1], cfg, activity_load=0.85, fatigue=0.45)
    return {
        "MOVE_fresh_energy_delta": fresh["energy_delta"],
        "MOVE_loaded_energy_delta": loaded["energy_delta"],
        "MOVE_state_dependent": abs(loaded["energy_delta"]) > abs(fresh["energy_delta"]),
        "micro_fresh": mf,
        "micro_loaded": ml,
        "micro_state_dependent": abs(ml["energy_delta"]) > abs(mf["energy_delta"]),
    }


def recovery_ablated_control() -> dict:
    eng_on = BodyEngine(_cfg(True))
    eng_off = BodyEngine(_cfg(False))
    def load_then_rest(eng):
        s = BodyState(activity_load=0.0, fatigue=0.15, energy_reserve=0.8)
        for _ in range(8):
            s = eng.transition(s, action=Action("WAIT"), distance=0.0, external_effects={"motor_demand_effort": 1.0}).state
        after_act = s.activity_load
        for _ in range(20):
            s = eng.transition(s, action=Action("WAIT"), distance=0.0).state
        return {"load_after_activity": after_act, "load_after_rest": s.activity_load, "fatigue": s.fatigue}
    return {"recovery_on": load_then_rest(eng_on), "recovery_off": load_then_rest(eng_off)}


def low_demand_non_wait(eng: BodyEngine) -> dict:
    """Recovery should follow low demand, not WAIT identity — USE if available as zero-distance."""
    s_wait = BodyState(activity_load=0.6, fatigue=0.35, energy_reserve=0.7)
    s_other = s_wait.clone()
    for _ in range(15):
        s_wait = eng.transition(s_wait, action=Action("WAIT"), distance=0.0).state
        # RELEASE as low-demand non-WAIT (no distance, low effort)
        s_other = eng.transition(s_other, action=Action("RELEASE"), distance=0.0).state
    return {
        "WAIT_load_after": s_wait.activity_load,
        "RELEASE_load_after": s_other.activity_load,
        "comparable_recovery": abs(s_wait.activity_load - s_other.activity_load) < 0.15,
        "note": "Both low motor demand; recovery not WAIT-symbolic",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", default="PHYSIO_CORE")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    eng = BodyEngine(_cfg(True))
    results = {
        "arm": args.arm,
        "identical_demand_matrix": identical_demand_matrix(eng),
        "activity_cycle": activity_cycle(eng),
        "conservation": conservation_tests(eng),
        "move_accounting": move_accounting(eng),
        "recovery_ablation": recovery_ablated_control(),
        "low_demand_non_wait": low_demand_non_wait(eng),
    }
    # Classify outcomes
    mat = results["identical_demand_matrix"]
    e_fresh = abs(mat["A_fresh"]["deltas"]["energy"])
    e_sust = abs(mat["C_sustained"]["deltas"]["energy"])
    results["outcome_flags"] = {
        "B_state_dependent_motor": e_sust > e_fresh * 1.05,
        "C_bounded_recovery": results["activity_cycle"]["recovery_restores_toward_first"],
        "conservation_ok": results["conservation"]["cycle_no_metabolic_creation"]
        and results["conservation"]["prolonged_wait_no_energy_creation"],
        "MOVE_and_micro_state_dependent": results["move_accounting"]["MOVE_state_dependent"]
        and results["move_accounting"]["micro_state_dependent"],
        "recovery_not_wait_only": results["low_demand_non_wait"]["comparable_recovery"],
    }
    path = OUT / "UPDATE451_ACTIVITY_PHYSIOLOGY.json"
    path.write_text(json.dumps(results, indent=2, default=str))
    (OUT / "UPDATE451_ACTIVITY_CYCLE.json").write_text(
        json.dumps(results["activity_cycle"], indent=2, default=str)
    )
    print(json.dumps({"wrote": str(path), "flags": results["outcome_flags"]}, indent=2))


if __name__ == "__main__":
    main()
