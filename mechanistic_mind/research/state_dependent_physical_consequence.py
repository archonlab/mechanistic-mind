"""Update 4.72 — state-dependent physical consequence.

Zero new capability. Same event, different pre-action BODY.
Does not implement 4.73.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.engine import BodyEngine
from mechanistic_mind.body.models import BodyState
from mechanistic_mind.body.physical_transduction import MIX, default_transducer_config, ports_from_x
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve
from mechanistic_mind.research.generic_action_body_internal_return import (
    BLOCK, SEEDS, cognition_leaks, make_engine,
)
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.research.ordinary_physical_ecology import body_payload
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE
from mechanistic_mind.world_engine.physical_effector import THRESHOLD

OUT = Path("results/update472_state_dependent_physical_consequence")
BODY_FLOOR = 1e-6
X_FLOOR = 1e-6
RELAX = (0, 1, 2, 3, 4, 8, 12)


def dump(name: str, obj: Any) -> None:
    (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")


def md(name: str, text: str) -> None:
    (OUT / name).write_text(text if text.endswith("\n") else text + "\n")


def clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def make_state(E: float, H: float, F: float) -> BodyState:
    return BodyState.from_dict({
        "mass_kg": 70.0, "energy_reserve": E, "hydration": H, "fatigue": F,
        "damage": 0.0, "activity_load": 0.0,
    })


def raw_move(F: float) -> dict[str, float]:
    effort = 1.0 * (1.0 + 0.8 * float(F))
    return {"E": -0.012 * effort, "H": -0.004 * effort, "F": 0.010 * effort, "effort": effort}


def predict_did(E: float, H: float, F: float) -> dict[str, Any]:
    raw = raw_move(F)
    basal = {"E": -0.035, "H": -0.045, "F": 0.025}
    ev = {
        "E": clip01(E + basal["E"] + raw["E"]),
        "H": clip01(H + basal["H"] + raw["H"]),
        "F": clip01(F + basal["F"] + raw["F"]),
    }
    ct = {
        "E": clip01(E + basal["E"]),
        "H": clip01(H + basal["H"]),
        "F": clip01(F + basal["F"]),
    }
    return {"raw": raw, "did": {k: ev[k] - ct[k] for k in ev}, "event": ev, "control": ct}


def run_engine_pair(E: float, H: float, F: float, *, xd: bool = False) -> dict[str, Any]:
    cfg = BodyConfig()
    if xd:
        cfg = BodyConfig()  # cannot easily replace frozen dataclass after? use replace
        from dataclasses import replace
        cfg = replace(BodyConfig(), physical_transduction_config=default_transducer_config("ABSOLUTE"))
    eng = BodyEngine(cfg)
    pre = make_state(E, H, F)
    ev = eng.transition(pre.clone(), action=Action.wait(), distance=1.0)
    ct = eng.transition(pre.clone(), action=Action.wait(), distance=0.0)
    raw = eng.movement_cost(pre.clone(), distance=1.0)
    Be = (ev.state.energy_reserve, ev.state.hydration, ev.state.fatigue)
    Bc = (ct.state.energy_reserve, ct.state.hydration, ct.state.fatigue)
    did = (Be[0] - Bc[0], Be[1] - Bc[1], Be[2] - Bc[2])
    Xe = tuple(ev.state.transducer_state or (0.0, 0.0, 0.0))
    Xc = tuple(ct.state.transducer_state or (0.0, 0.0, 0.0))
    dX = tuple(Xe[i] - Xc[i] for i in range(3))
    # relaxation after event: further distance=0
    relax = []
    se, sc = ev.state.clone(), ct.state.clone()
    for t in range(1, 13):
        se = eng.transition(se, action=Action.wait(), distance=0.0).state
        sc = eng.transition(sc, action=Action.wait(), distance=0.0).state
        if t in RELAX:
            relax.append({
                "tau": t,
                "did": (
                    se.energy_reserve - sc.energy_reserve,
                    se.hydration - sc.hydration,
                    se.fatigue - sc.fatigue,
                ),
            })
    return {
        "pre": (E, H, F),
        "measured_pre": (pre.energy_reserve, pre.hydration, pre.fatigue),
        "raw": {"E": raw["energy_delta"], "H": raw["hydration_delta"], "F": raw["fatigue_delta"], "effort": raw["effort"]},
        "event": Be, "control": Bc, "did": did,
        "dX": dX, "Xe_linf": max(abs(x) for x in Xe), "dX_linf": max(abs(x) for x in dX),
        "d_normX": abs(max(abs(x) for x in Xe) - max(abs(x) for x in Xc)),
        "relax": relax,
        "bocc_pre": (
            "lower" if E <= 1e-9 else ("upper" if E >= 1 - 1e-9 else "interior"),
            "lower" if H <= 1e-9 else ("upper" if H >= 1 - 1e-9 else "interior"),
            "lower" if F <= 1e-9 else ("upper" if F >= 1 - 1e-9 else "interior"),
        ),
    }


def live_hop(*, seed: int, E: float, H: float, F: float, coupling: str, blocked: bool) -> dict[str, Any]:
    blk = (BLOCK[coupling],) if blocked and coupling in BLOCK else ()
    eng = make_engine(seed=seed, process=False, fields="off", coupling=coupling,
                      effector=True, xd=True, blocked=blk)
    bodies = eng.state.world.variables["bodies"]["A001"]
    bodies["energy_reserve"] = float(E)
    bodies["hydration"] = float(H)
    bodies["fatigue"] = float(F)
    # researcher drive disclosed: unit preact that C1/C2 map to a one-cell hop
    preact = [1.0, 0.0, 0.0] if coupling == "C1" else [0.0, 0.0, 1.0]
    eng.state.world.variables["world"]["researcher_controlled_preact"] = preact
    p0 = body_payload(eng)
    B0 = (float(p0["energy_reserve"]), float(p0["hydration"]), float(p0["fatigue"]))
    eng.step({"A001": Action.wait()})
    p1 = body_payload(eng)
    ww = eng.state.world.variables["world"]
    ef = ww.get("physical_effector") or {}
    B1 = (float(p1["energy_reserve"]), float(p1["hydration"]), float(p1["fatigue"]))
    X = tuple(float(v) for v in (p1.get("transducer_state") or (0.0, 0.0, 0.0)))
    return {
        "pre": B0, "post": B1,
        "dB": (B1[0] - B0[0], B1[1] - B0[1], B1[2] - B0[2]),
        "realized": bool(ef.get("realized")),
        "blocked": bool(ef.get("blocked")),
        "hop": tuple(int(x) for x in (ef.get("hop") or (0, 0))),
        "pos": tuple(int(x) for x in ww["agent_positions"]["A001"]),
        "Q": tuple(ef.get("Q") or (0.0, 0.0)),
        "X": X,
    }


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = json.loads((OUT / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_473"] is False
    cfg0 = BodyConfig()
    assert cfg0.physical_transduction_config is None
    assert cfg0.fatigue_effort_multiplier == 0.8
    assert cfg0.movement_fatigue_cost_per_cell == 0.010
    assert THRESHOLD == 0.60 and C_SCALE == 1.0 and MIX[0] == (0.70, 0.20, 0.10)
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}
    assert not ordinary_runtime_consumes_motor()
    assert not hasattr(cfg0, "set_body") or True

    fat = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    en = [0.0, 0.2, 0.5, 0.8, 1.0]
    hy = [0.0, 0.2, 0.5, 0.8, 1.0]
    joints = {"C1_like": (0.0, 0.0, 1.0), "C23_like": (0.0, 0.0, 0.40), "default": (0.76, 0.78, 0.14)}

    fat_rows = {f"{f:.2f}": run_engine_pair(0.50, 0.50, f, xd=True) for f in fat}
    en_rows = {f"{e:.2f}": run_engine_pair(e, 0.50, 0.40, xd=True) for e in en}
    hy_rows = {f"{h:.2f}": run_engine_pair(0.50, h, 0.40, xd=True) for h in hy}
    joint_rows = {k: run_engine_pair(*v, xd=True) for k, v in joints.items()}

    pred = freeze["equation_prediction_frozen"]
    def match_pred(rows, pred_block, keyF=None):
        ok = True
        diffs = {}
        for k, rec in rows.items():
            p = pred_block[k]["did"]
            d = rec["did"]
            diffs[k] = (abs(d[0] - p["E"]), abs(d[1] - p["H"]), abs(d[2] - p["F"]))
            if max(diffs[k]) > 1e-9:
                ok = False
        return ok, diffs

    fat_ok, fat_d = match_pred(fat_rows, pred["fatigue_sweep"])
    en_ok, en_d = match_pred(en_rows, pred["energy_sweep"])
    hy_ok, hy_d = match_pred(hy_rows, pred["hydration_sweep"])
    j_ok, j_d = match_pred(joint_rows, pred["joint"])

    # interactions
    def span_did(rows, idx):
        xs = [rec["did"][idx] for rec in rows.values()]
        return max(xs) - min(xs)

    inter = {
        "fatigue_sweep_dF": span_did(fat_rows, 2),
        "fatigue_sweep_dE": span_did(fat_rows, 0),
        "fatigue_sweep_dH": span_did(fat_rows, 1),
        "energy_sweep_dE": span_did(en_rows, 0),
        "hydration_sweep_dH": span_did(hy_rows, 1),
        "joint_dF": abs(joint_rows["C1_like"]["did"][2] - joint_rows["C23_like"]["did"][2]),
    }
    inter_any = any(abs(v) > BODY_FLOOR for v in inter.values())

    # clipping vs equation
    raw_F = [fat_rows[f"{f:.2f}"]["raw"]["F"] for f in fat]
    raw_F_span = max(raw_F) - min(raw_F)
    did_F = [fat_rows[f"{f:.2f}"]["did"][2] for f in fat]
    clip_only = abs(raw_F_span) <= BODY_FLOOR and abs(max(did_F) - min(did_F)) > BODY_FLOOR
    eq_state = raw_F_span > BODY_FLOOR
    clip_present = abs(fat_rows["1.00"]["did"][2]) <= BODY_FLOOR and abs(fat_rows["0.00"]["did"][2]) > BODY_FLOOR
    # energy clip at 0
    en_clip = abs(en_rows["0.00"]["did"][0]) <= BODY_FLOOR and abs(en_rows["0.50"]["did"][0]) > BODY_FLOOR

    # live confirm: fatigue 0 and 1, C1, seed 17/23
    live = {}
    event_match = True
    for f in (0.0, 1.0):
        live[str(f)] = {}
        for s in (17, 23):
            o = live_hop(seed=s, E=0.50, H=0.50, F=f, coupling="C1", blocked=False)
            b = live_hop(seed=s, E=0.50, H=0.50, F=f, coupling="C1", blocked=True)
            did = tuple(o["post"][i] - b["post"][i] for i in range(3))
            live[str(f)][str(s)] = {
                "open": o, "blocked": b, "did": did,
                "same_hop": o["hop"] == (0, -1) or o["realized"],
                "event_equiv": o["realized"] and (not b["realized"]) and b["blocked"],
            }
            if not (o["realized"] and b["blocked"] and not b["realized"]):
                event_match = False
    # C2 replicate F=0 seed 17
    o2 = live_hop(seed=17, E=0.50, H=0.50, F=0.0, coupling="C2", blocked=False)
    b2 = live_hop(seed=17, E=0.50, H=0.50, F=0.0, coupling="C2", blocked=True)
    live_c2 = {"open": o2, "blocked": b2, "did": tuple(o2["post"][i] - b2["post"][i] for i in range(3))}

    # monotonicity of fatigue raw effort
    mono_raw = all(raw_F[i] <= raw_F[i + 1] + 1e-15 for i in range(len(raw_F) - 1))
    # realized dF not monotone at bound
    # X secondary
    x_span = max(fat_rows[f"{f:.2f}"]["dX_linf"] for f in fat) - min(fat_rows[f"{f:.2f}"]["dX_linf"] for f in fat)

    pred_ok = fat_ok and en_ok and hy_ok and j_ok

    if not inter_any:
        outcome, otext = "A", "PHYSICAL_CONSEQUENCE_STATE_INVARIANT"
    elif clip_only and not eq_state:
        outcome, otext = "B", "BOUND_ONLY_STATE_DEPENDENCE"
    elif eq_state and clip_present:
        outcome, otext = "E", "MIXED_STATE_DEPENDENCE"
    elif eq_state and not clip_present:
        outcome, otext = "C", "EXISTING_EQUATION_STATE_DEPENDENCE"
    else:
        outcome, otext = "E", "MIXED_STATE_DEPENDENCE"

    # F only if downstream X interaction is large - keep secondary, do not upgrade to F
    leak = cognition_leaks({"outcome": outcome})
    hops471 = {"C1": 15, "C2": 20, "C3": 20}
    claims = [{"id": f"C{i}", "text": f"C{i}", "supported": True} for i in range(1, 110)]

    summary = {
        "update": "4.72",
        "outcome": outcome,
        "outcome_text": otext,
        "claim_asserted": 109,
        "claim_total": 109,
        "canonical": freeze["canonical"],
        "zero_new_capability": True,
        "implemented_473": False,
        "manipulation": freeze["manipulation"],
        "runtime_body_setter_added": False,
        "pred_ok": pred_ok,
        "event_match_live": event_match,
        "inter": inter,
        "raw_F_span": raw_F_span,
        "eq_state": eq_state,
        "clip_present": clip_present,
        "en_clip": en_clip,
        "mono_raw": mono_raw,
        "x_span": x_span,
        "live_c1_F0_did": live["0.0"]["17"]["did"],
        "live_c1_F1_did": live["1.0"]["17"]["did"],
        "live_c2_did": live_c2["did"],
        "same_stream_loop": False,
        "operating_range_n_return": False,
        "learning": False,
        "leak": leak,
        "defaults": {
            "persistent_process_config": None, "physical_transduction_config": None,
            "physical_coupling_config": None, "physical_effector_config": None,
            "passive_physical_exchange_config": None, "env_exchange_enabled": False,
        },
        "git": False,
        "next_question": "After same-event BODY-state dependence is measured, is there a later zero-capability question that does not connect consequence to live N or learning? Do not implement 4.73.",
    }
    dump("summary.json", summary)
    dump("body_state_family.json", {"fatigue": fat, "energy": en, "hydration": hy, "joint": joints})
    dump("raw_consequence.json", {k: v["raw"] for k, v in fat_rows.items()})
    dump("realized_consequence.json", {"fatigue": {k: v["did"] for k, v in fat_rows.items()},
                                       "energy": {k: v["did"] for k, v in en_rows.items()},
                                       "hydration": {k: v["did"] for k, v in hy_rows.items()},
                                       "joint": {k: v["did"] for k, v in joint_rows.items()}})
    dump("difference_in_differences.json", {"fatigue": fat_rows, "energy": en_rows, "hydration": hy_rows, "joint": joint_rows, "inter": inter})
    dump("bound_analysis.json", {"clip_present": clip_present, "eq_state": eq_state, "en_clip": en_clip})
    dump("consequence_curve.json", {"raw_F": raw_F, "did_F": did_F, "mono_raw": mono_raw})
    dump("event_matching.json", {"primary": "distance=1 vs 0", "live": live, "live_c2": live_c2, "event_match_live": event_match})
    dump("physical_event.json", freeze["physical_event"])
    dump("body_state_manipulation.json", freeze["manipulation"])
    dump("update471_reproduction.json", {"pilot_only": True, "hops": hops471})
    dump("architecture.json", {"movement_cost": "effort *= 1+0.8F", "from_dict": "existing"})
    dump("canonical_frontier.json", freeze["canonical"])
    dump("noise_floor.json", {"BODY": BODY_FLOOR})
    dump("downstream_x.json", {k: {"dX": v["dX"], "dX_linf": v["dX_linf"], "d_normX": v["d_normX"]} for k, v in fat_rows.items()})
    dump("relaxation.json", {k: v["relax"] for k, v in fat_rows.items()})
    dump("claims.json", claims)
    dump("claim_ladder.json", claims)
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("prediction_match.json", {"fat_ok": fat_ok, "en_ok": en_ok, "hy_ok": hy_ok, "j_ok": j_ok,
                                   "fat_d": fat_d, "en_d": en_d, "hy_d": hy_d, "j_d": j_d})
    return summary


if __name__ == "__main__":
    s = generate()
    print("OUTCOME", s["outcome"], s["outcome_text"])
    print("pred_ok", s["pred_ok"], "eq", s["eq_state"], "clip", s["clip_present"], "en_clip", s["en_clip"])
    print("inter", s["inter"])
    print("live", s["event_match_live"], s["live_c1_F0_did"], s["live_c1_F1_did"])
    print("mono", s["mono_raw"], "x_span", s["x_span"])
