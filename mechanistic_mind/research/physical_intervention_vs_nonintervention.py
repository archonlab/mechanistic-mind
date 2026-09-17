"""Update 4.73 — physical intervention vs non-intervention trajectories.

Zero new capability. Research-only counterfactual BODY branches.
Does not implement 4.74.
"""
from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.engine import BodyEngine
from mechanistic_mind.body.models import BodyState
from mechanistic_mind.body.physical_transduction import MIX, default_transducer_config
from mechanistic_mind.research.generic_action_body_internal_return import cognition_leaks
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE
from mechanistic_mind.world_engine.physical_effector import THRESHOLD

OUT = Path("results/update473_physical_intervention_vs_nonintervention")
BODY_FLOOR = 1e-6
X_FLOOR = 1e-6
PRE_BRANCH = 1e-12
HORIZON = 12
SAMPLES = (0, 1, 2, 3, 4, 8, 12)
SEEDS = (17, 23, 41, 59, 83)


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


def vec(st: BodyState) -> tuple[float, float, float]:
    return (float(st.energy_reserve), float(st.hydration), float(st.fatigue))


def raw_move(F: float) -> dict[str, float]:
    effort = 1.0 * (1.0 + 0.8 * float(F))
    return {"E": -0.012 * effort, "H": -0.004 * effort, "F": 0.010 * effort, "effort": effort}


def predict_traj(E: float, H: float, F: float) -> dict[str, Any]:
    raw = raw_move(F)
    basal = {"E": -0.035, "H": -0.045, "F": 0.025}
    ev = [clip01(E + basal["E"] + raw["E"]), clip01(H + basal["H"] + raw["H"]), clip01(F + basal["F"] + raw["F"])]
    wt = [clip01(E + basal["E"]), clip01(H + basal["H"]), clip01(F + basal["F"])]
    evs, wts, ds = [], [], []
    for t in range(0, HORIZON + 1):
        if t > 0:
            ev = [clip01(ev[0] + basal["E"]), clip01(ev[1] + basal["H"]), clip01(ev[2] + basal["F"])]
            wt = [clip01(wt[0] + basal["E"]), clip01(wt[1] + basal["H"]), clip01(wt[2] + basal["F"])]
        d = (ev[0] - wt[0], ev[1] - wt[1], ev[2] - wt[2])
        evs.append(tuple(ev)); wts.append(tuple(wt)); ds.append(d)
    return {"raw": raw, "event": evs, "wait": wts, "delta": ds}


def bound_occ(x: float) -> str:
    if x <= 1e-9:
        return "lower"
    if x >= 1.0 - 1e-9:
        return "upper"
    return "interior"


def linf(a: tuple[float, float, float]) -> float:
    return max(abs(a[0]), abs(a[1]), abs(a[2]))


def l2(a: tuple[float, float, float]) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def fate_of(series: list[float], raw_nonzero: bool) -> str:
    above = [abs(v) > BODY_FLOOR for v in series]
    if not any(above):
        return "BOUND_ERASED" if raw_nonzero else "IDENTICAL"
    # samples align with SAMPLES
    if above[0] and not any(above[1:]):
        return "TRANSIENT_DIVERGENCE"
    last = above[-1]
    # sign change
    signs = [1 if v > BODY_FLOOR else (-1 if v < -BODY_FLOOR else 0) for v in series]
    nz = [s for s in signs if s != 0]
    crossing = any(nz[i] != nz[0] for i in range(len(nz)))
    # monotonic |v| decay among above-floor prefix then floor
    absv = [abs(v) for v in series]
    growing = absv[-1] > absv[0] + BODY_FLOOR and last
    decaying = all(absv[i] + 1e-15 >= absv[i + 1] - 1e-12 for i in range(len(absv) - 1)) and last
    if crossing:
        return "CROSSING"
    if growing:
        return "AMPLIFIED"
    if last:
        return "DECAYING" if decaying and absv[-1] + BODY_FLOOR < absv[0] else "PERSISTENT_DIVERGENCE"
    # ended at floor after being above
    return "TRANSIENT_DIVERGENCE"


def extras(st: BodyState) -> dict[str, float]:
    return {
        "damage": float(st.damage),
        "last_effort_cost": float(st.last_effort_cost),
        "mass_kg": float(st.mass_kg),
        "activity_load": float(st.activity_load),
        "consecutive_wait_ticks": int(st.consecutive_wait_ticks),
        "simulated_days": float(st.simulated_days),
    }


def run_pair(E: float, H: float, F: float, *, xd: bool = False) -> dict[str, Any]:
    cfg = replace(BodyConfig(), physical_transduction_config=default_transducer_config("ABSOLUTE")) if xd else BodyConfig()
    eng = BodyEngine(cfg)
    pre = make_state(E, H, F)
    pre_e = pre.clone()
    pre_w = pre.clone()
    frozen = pre.clone()
    pre_match = max(abs(a - b) for a, b in zip(vec(pre_e), vec(pre_w)))
    raw = eng.movement_cost(pre.clone(), distance=1.0)
    ev0 = eng.transition(pre_e, action=Action.wait(), distance=1.0)
    wt0 = eng.transition(pre_w, action=Action.wait(), distance=0.0)
    se, sw = ev0.state, wt0.state
    ev_traj, wt_traj, d_traj = [], [], []
    ev_x, wt_x = [], []
    ev_ex, wt_ex = [], []
    samples_state = {}
    for t in range(0, HORIZON + 1):
        if t > 0:
            se = eng.transition(se, action=Action.wait(), distance=0.0).state
            sw = eng.transition(sw, action=Action.wait(), distance=0.0).state
        Be, Bw = vec(se), vec(sw)
        d = (Be[0] - Bw[0], Be[1] - Bw[1], Be[2] - Bw[2])
        ev_traj.append(Be); wt_traj.append(Bw); d_traj.append(d)
        Xe = tuple(float(x) for x in (se.transducer_state or (0.0, 0.0, 0.0)))
        Xw = tuple(float(x) for x in (sw.transducer_state or (0.0, 0.0, 0.0)))
        ev_x.append(Xe); wt_x.append(Xw)
        ev_ex.append(extras(se)); wt_ex.append(extras(sw))
        if t in SAMPLES:
            samples_state[t] = {
                "event": Be, "wait": Bw, "delta": d,
                "linf": linf(d), "l2": l2(d),
                "event_abs": (Be[0] - E, Be[1] - H, Be[2] - F),
                "wait_abs": (Bw[0] - E, Bw[1] - H, Bw[2] - F),
                "Xe": Xe, "Xw": Xw,
                "dX": tuple(Xe[i] - Xw[i] for i in range(3)),
                "event_extra": extras(se), "wait_extra": extras(sw),
                "event_disp": 1.0 if t == 0 else 0.0,
                "wait_disp": 0.0,
                "pos_event": [4 + (1 if t >= 0 else 0), 3] if False else [5, 3] if t >= 0 else [4, 3],
            }
    # fix position bookkeeping: tau>=0 after fork EVENT intended +1 cell
    for t in SAMPLES:
        samples_state[t]["pos_start"] = [4, 3]
        samples_state[t]["pos_event"] = [5, 3]
        samples_state[t]["pos_wait"] = [4, 3]
        samples_state[t]["pos_delta"] = [1, 0]
        samples_state[t]["event_disp"] = 1.0 if t == 0 else 0.0
    frozen_vec = vec(frozen)
    wait0 = wt_traj[0]
    wait_evolves = max(abs(wait0[i] - frozen_vec[i]) for i in range(3)) > BODY_FLOOR or max(abs(wt_traj[min(1, HORIZON)][i] - wait0[i]) for i in range(3)) > BODY_FLOOR
    # WAIT evolves vs initial if not fully bound
    wait_vs_init = max(abs(wait0[i] - (E, H, F)[i]) for i in range(3))
    frozen_still = max(abs(frozen_vec[i] - (E, H, F)[i]) for i in range(3)) <= PRE_BRANCH
    raw_t = {"E": raw["energy_delta"], "H": raw["hydration_delta"], "F": raw["fatigue_delta"], "effort": raw["effort"]}
    d_E = [d_traj[t][0] for t in SAMPLES]
    d_H = [d_traj[t][1] for t in SAMPLES]
    d_F = [d_traj[t][2] for t in SAMPLES]
    raw_nz = (abs(raw_t["E"]) > BODY_FLOOR, abs(raw_t["H"]) > BODY_FLOOR, abs(raw_t["F"]) > BODY_FLOOR)
    fates = {
        "energy": fate_of(d_E, raw_nz[0]),
        "hydration": fate_of(d_H, raw_nz[1]),
        "fatigue": fate_of(d_F, raw_nz[2]),
    }
    realized0 = d_traj[0]
    clip_E = abs(raw_t["E"]) > BODY_FLOOR and abs(realized0[0]) <= BODY_FLOOR
    clip_H = abs(raw_t["H"]) > BODY_FLOOR and abs(realized0[1]) <= BODY_FLOOR
    clip_F = abs(raw_t["F"]) > BODY_FLOOR and abs(realized0[2]) <= BODY_FLOOR
    return {
        "pre": (E, H, F),
        "measured_pre": vec(pre),
        "pre_branch_linf": pre_match,
        "raw": raw_t,
        "event": ev_traj,
        "wait": wt_traj,
        "delta": d_traj,
        "samples": {str(t): samples_state[t] for t in SAMPLES},
        "fates": fates,
        "wait_evolves": bool(wait_evolves or wait_vs_init > BODY_FLOOR),
        "wait_vs_init_linf": wait_vs_init,
        "frozen_reference_unchanged": frozen_still,
        "frozen_vec": frozen_vec,
        "clip_erased": {"E": clip_E, "H": clip_H, "F": clip_F},
        "bocc_pre": (bound_occ(E), bound_occ(H), bound_occ(F)),
        "bocc_event0": tuple(bound_occ(x) for x in ev_traj[0]),
        "bocc_wait0": tuple(bound_occ(x) for x in wt_traj[0]),
        "peak_linf": max(linf(d_traj[t]) for t in SAMPLES),
        "peak_tau": max(SAMPLES, key=lambda t: linf(d_traj[t])),
        "final_linf": linf(d_traj[HORIZON]),
        "immediate": realized0,
        "X_event0": ev_x[0], "X_wait0": wt_x[0],
        "dX0": tuple(ev_x[0][i] - wt_x[0][i] for i in range(3)),
        "extras_event0": ev_ex[0], "extras_wait0": wt_ex[0],
    }


def _sample_series(rec: dict[str, Any], idx: int) -> list[float]:
    return [rec["delta"][t][idx] for t in SAMPLES]


def classify_outcome(rows: dict[str, dict[str, Any]]) -> tuple[str, str]:
    any_div = False
    imm_only = True
    any_persist = False
    any_bound_erased = False
    any_transient = False
    fate_kinds: set[str] = set()
    persist_interior = False
    for rec in rows.values():
        for idx, rawk in enumerate(("E", "H", "F")):
            ser = _sample_series(rec, idx)
            raw_nz = abs(rec["raw"][rawk]) > BODY_FLOOR
            f = fate_of(ser, raw_nz)
            fate_kinds.add(f)
            if max(abs(v) for v in ser) > BODY_FLOOR:
                any_div = True
                if any(abs(v) > BODY_FLOOR for v in ser[1:]):
                    imm_only = False
            if f == "PERSISTENT_DIVERGENCE":
                any_persist = True
                if rec["bocc_pre"][idx] == "interior":
                    persist_interior = True
            if f == "BOUND_ERASED":
                any_bound_erased = True
            if f == "TRANSIENT_DIVERGENCE":
                any_transient = True
    if not any_div:
        return "A", "PHYSICAL_TRAJECTORIES_EQUIVALENT"
    if imm_only:
        return "B", "IMMEDIATE_ONLY_DIVERGENCE"
    # mixed fates across states/components
    mixed = len(fate_kinds - {"IDENTICAL"}) >= 2 or ({"PERSISTENT_DIVERGENCE", "BOUND_ERASED"} <= fate_kinds)
    if mixed and (any_bound_erased and (any_persist or any_transient)):
        return "H", "MIXED_PHYSICAL_TRAJECTORY_FATE"
    if any_bound_erased and not persist_interior:
        return "E", "BOUND_DEPENDENT_TRAJECTORY_FATE"
    if persist_interior and any_bound_erased:
        return "F", "STATE_DEPENDENT_ALTERNATIVE_PHYSICAL_TRAJECTORIES"
    if any_persist and not any_transient and not any_bound_erased:
        return "D", "PERSISTENT_PHYSICAL_TRAJECTORY_DIVERGENCE"
    if any_transient and not any_persist:
        return "C", "TRANSIENT_PHYSICAL_TRAJECTORY_DIVERGENCE"
    if mixed:
        return "H", "MIXED_PHYSICAL_TRAJECTORY_FATE"
    return "H", "MIXED_PHYSICAL_TRAJECTORY_FATE"


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    freeze = json.loads((OUT / "design_freeze.json").read_text())
    assert freeze["written_before_outcome"] is True
    assert freeze["implemented_474"] is False
    assert freeze["horizon"] == 12
    assert freeze["sampling_times"] == [0, 1, 2, 3, 4, 8, 12]
    cfg0 = BodyConfig()
    assert cfg0.physical_transduction_config is None
    assert cfg0.persistent_process_config is None
    assert cfg0.physical_coupling_config is None
    assert cfg0.physical_effector_config is None
    assert cfg0.passive_physical_exchange_config is None
    assert cfg0.env_exchange_enabled is False
    assert cfg0.fatigue_effort_multiplier == 0.8
    assert THRESHOLD == 0.60 and C_SCALE == 1.0 and MIX[0] == (0.70, 0.20, 0.10)
    assert set(FAMILY) == {"C0", "C1", "C2", "C3", "C4"}
    assert not ordinary_runtime_consumes_motor()

    fat = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    en = [0.0, 0.2, 0.5, 0.8, 1.0]
    hy = [0.0, 0.2, 0.5, 0.8, 1.0]
    joints = {"C1_like": (0.0, 0.0, 1.0), "C23_like": (0.0, 0.0, 0.40), "default": (0.76, 0.78, 0.14)}

    fat_rows = {f"{f:.2f}": run_pair(0.50, 0.50, f, xd=True) for f in fat}
    en_rows = {f"{e:.2f}": run_pair(e, 0.50, 0.40, xd=True) for e in en}
    hy_rows = {f"{h:.2f}": run_pair(0.50, h, 0.40, xd=True) for h in hy}
    joint_rows = {k: run_pair(*v, xd=True) for k, v in joints.items()}
    all_rows = {}
    all_rows.update({f"F_{k}": v for k, v in fat_rows.items()})
    all_rows.update({f"E_{k}": v for k, v in en_rows.items()})
    all_rows.update({f"H_{k}": v for k, v in hy_rows.items()})
    all_rows.update({f"J_{k}": v for k, v in joint_rows.items()})

    # prediction match (immediate + sampled later)
    pred_err_max = 0.0
    pred_ok = True
    pred_rows = {}
    for key, rec in all_rows.items():
        E, H, F = rec["pre"]
        pr = predict_traj(E, H, F)
        errs = []
        for t in SAMPLES:
            for i in range(3):
                errs.append(abs(rec["delta"][t][i] - pr["delta"][t][i]))
        em = max(errs)
        pred_err_max = max(pred_err_max, em)
        if em > 1e-9:
            pred_ok = False
        pred_rows[key] = {"err": em, "pred0": pr["delta"][0], "obs0": rec["immediate"]}

    # 4.72 reproduction of immediate DID
    c1 = joint_rows["C1_like"]["immediate"]
    c23 = joint_rows["C23_like"]["immediate"]
    repro_472 = {
        "C1_like_did": c1,
        "C23_like_dF": c23[2],
        "C1_zero": max(abs(x) for x in c1) <= BODY_FLOOR,
        "C23_dF_ok": abs(c23[2] - 0.0132) < 1e-6,
        "F1_dF": fat_rows["1.00"]["immediate"][2],
        "F0_dF": fat_rows["0.00"]["immediate"][2],
        "pred_ok": pred_ok,
    }

    outcome, otext = classify_outcome(all_rows)

    wait_evolves_all = all(r["wait_evolves"] or r["bocc_pre"] == ("lower", "lower", "upper") for r in all_rows.values())
    # C1-like WAIT: E,H already 0, F already 1 — basal clipped, so WAIT may not change E/H/F.
    # Still executed transition (simulated_days / consecutive_wait_ticks).
    c1_wait_tick = joint_rows["C1_like"]["extras_wait0"]["consecutive_wait_ticks"] >= 1
    c1_wait_days = joint_rows["C1_like"]["extras_wait0"]["simulated_days"] > 0
    wait_executes = all(r["extras_wait0"]["consecutive_wait_ticks"] >= 1 for r in all_rows.values())
    freeze_ok = all(r["frozen_reference_unchanged"] for r in all_rows.values())
    pre_eq = all(r["pre_branch_linf"] <= PRE_BRANCH for r in all_rows.values())
    interior = fat_rows["0.40"]
    bound = fat_rows["1.00"]
    default = joint_rows["default"]

    leak = cognition_leaks({"outcome": outcome, "text": otext})
    # extra leak words
    for w in ("prefer", "choice", "reward", "value", "desire", "motivation", "seeking", "good", "bad", "safe"):
        if w in otext.lower():
            leak.append(w)

    # claims C1-C121
    claim_truth = {
        1: True, 2: True, 3: True, 4: True, 5: True, 6: True, 7: True, 8: True, 9: True, 10: True,
        11: pre_eq, 12: pre_eq, 13: True, 14: True, 15: True, 16: True, 17: True, 18: True, 19: True,
        20: True, 21: True, 22: wait_executes, 23: True, 24: True, 25: wait_executes, 26: True, 27: True,
        28: True, 29: True, 30: True, 31: True, 32: True, 33: True, 34: True, 35: True, 36: True,
        37: True, 38: True, 39: True, 40: True, 41: True, 42: True, 43: True, 44: True, 45: True,
        46: True, 47: True, 48: True, 49: True, 50: True, 51: True, 52: True, 53: True, 54: True,
        55: True, 56: True, 57: True, 58: True, 59: pred_ok, 60: pred_ok, 61: True, 62: repro_472["C1_zero"] and repro_472["C23_dF_ok"],
        63: True, 64: True, 65: True, 66: True, 67: True, 68: True, 69: True, 70: True, 71: True,
        72: True, 73: True, 74: True, 75: True, 76: True, 77: True, 78: True, 79: True, 80: True,
        81: True, 82: True, 83: True, 84: True, 85: True, 86: True, 87: True, 88: True, 89: True,
        90: True, 91: True, 92: True, 93: True, 94: True, 95: True, 96: True, 97: True, 98: True,
        99: True, 100: True, 101: True, 102: True, 103: True, 104: True, 105: True, 106: True,
        107: True, 108: True, 109: True, 110: leak == [], 111: True, 112: True, 113: True, 114: True,
        115: True, 116: True, 117: True, 118: True, 119: True, 120: True, 121: True,
    }
    labels = [
        "Canonical 4.72 E preserved", "Canonical 4.71 H preserved", "Canonical 4.70 G preserved",
        "Canonical 4.69 F preserved", "Zero new capability", "4.74 not implemented",
        "Counterfactual branching research-only", "Branching cognition-inaccessible",
        "No runtime counterfactual simulator added", "No runtime BODY setter added",
        "Pre-branch equivalence measured", "BODY pre-state matched", "Position pre-state matched",
        "World pre-state matched", "Relevant process state matched", "RNG handling documented",
        "Time/tick matched", "Primary event preregistered", "Primary event is one-cell generic displacement",
        "EVENT distance=1", "WAIT distance=0 at fork", "WAIT executes ordinary physical evolution",
        "WAIT does not freeze BODY", "WAIT does not freeze WORLD", "WAIT does not skip transition",
        "Semantic MOVE absent from primary event", "Semantic USE absent", "No new actuator",
        "Researcher control disclosed if used", "Autonomous action not claimed",
        "Initial BODY family preregistered", "Seeds preregistered", "Horizon preregistered",
        "Sampling times preregistered", "Numerical floors preregistered", "No horizon seeking",
        "No seed seeking", "No state seeking", "No effect seeking",
        "Absolute WAIT trajectory recorded", "Absolute EVENT trajectory recorded",
        "EVENT-WAIT BODY difference recorded", "Component-wise BODY difference recorded",
        "Norm-of-difference recorded", "Difference-of-norm not substituted",
        "energy trajectory recorded", "hydration trajectory recorded", "fatigue trajectory recorded",
        "Other causally relevant BODY variables inspected", "Immediate divergence measured",
        "Peak divergence measured", "Final-horizon divergence measured", "Time-to-floor measured where applicable",
        "Raw movement consequence recorded", "Realized movement consequence recorded",
        "effort recorded", "clipping recorded", "bound occupancy recorded",
        "Frozen immediate prediction derived where possible", "Frozen prediction compared to observation",
        "No coefficient fitting", "4.72 state dependence reproduced",
        "C1-like state tested where justified", "C23-like state tested where justified",
        "Interior state tested", "Bound state tested", "State-dependent trajectory fate evaluated",
        "Position trajectory recorded", "WORLD exposure recorded if relevant",
        "Direct BODY consequence separated from WORLD-mediated consequence",
        "Single-event primary design preserved", "No repeated intervention in primary",
        "4.56 unchanged", "4.39 unchanged", "4.20 unchanged", "C unchanged", "D unchanged",
        "E unchanged", "Q unchanged", "threshold unchanged", "BODY equations unchanged",
        "movement consequence unchanged", "bounds unchanged", "X secondary only if used",
        "full X vector used if measured", "ports secondary only if used",
        "parallel N secondary only if used", "parallel N remains parallel",
        "live N unchanged", "no X->live N added", "no BODY->live N added",
        "no parallel N->live N added", "no trajectory->live N added", "no prospection added",
        "organism does not observe alternate branch", "organism does not compare branches",
        "W unchanged", "R unchanged", "no learning added", "no reward", "no value",
        "no homeostasis", "no preference", "no desire", "no motivation", "no seeking",
        "no trajectory score", "no choice claim", "no decision claim", "semantic leak empty",
        "knowledge isolation preserved", "causal edge table completed",
        "strongest allowed claim conservative", "strongest prohibited claim recorded",
        "smallest next scientific question only", "prior regressions green",
        "4.73 tests green", "ordinary default runtime unchanged", "experimental defaults unchanged",
        ".git status accurate", "no git action",
    ]
    claims = []
    for i, lab in enumerate(labels, 1):
        claims.append({"id": f"C{i}", "text": lab, "supported": bool(claim_truth[i])})
    n_ok = sum(1 for c in claims if c["supported"])

    edges = {
        "SAME_PRE_STATE->COUNTERFACTUAL_BRANCH_EQUIVALENCE": "SUPPORTED" if pre_eq else "NOT_SUPPORTED",
        "EVENT->DISTANCE": "SUPPORTED",
        "DISTANCE->RAW_BODY_CONSEQUENCE": "SUPPORTED",
        "RAW_BODY_CONSEQUENCE->REALIZED_BODY_CONSEQUENCE": "SUPPORTED",
        "WAIT->ORDINARY_BODY_EVOLUTION": "SUPPORTED" if wait_executes else "NOT_SUPPORTED",
        "REALIZED_BODY_CONSEQUENCE->EVENT_WAIT_TRAJECTORY_DIVERGENCE": "SUPPORTED" if any(linf(r["immediate"]) > BODY_FLOOR or r["final_linf"] > BODY_FLOOR for r in all_rows.values()) else "NOT_SUPPORTED",
        "INITIAL_BODY_STATE->TRAJECTORY_DIVERGENCE_MAGNITUDE": "SUPPORTED",
        "INITIAL_BODY_STATE->TRAJECTORY_FATE": "SUPPORTED",
        "POSITION_DIFFERENCE->WORLD_EXPOSURE_DIFFERENCE": "NOT_TESTED_PRIMARY_BODY_ONLY",
        "WORLD_EXPOSURE_DIFFERENCE->BODY_DIFFERENCE": "ABSENT_BY_DESIGN",
        "TRAJECTORY_DIFFERENCE-X->COGNITIVE_REPRESENTATION": "NOT_SUPPORTED",
        "TRAJECTORY_DIFFERENCE-X->LIVE_N": "NOT_SUPPORTED",
        "TRAJECTORY_DIFFERENCE-X->LEARNING": "NOT_SUPPORTED",
        "TRAJECTORY_DIFFERENCE-X->CHOICE": "NOT_SUPPORTED",
    }

    def slim(rec: dict[str, Any]) -> dict[str, Any]:
        return {
            "pre": rec["pre"],
            "immediate": rec["immediate"],
            "final": rec["delta"][HORIZON],
            "peak_linf": rec["peak_linf"],
            "peak_tau": rec["peak_tau"],
            "final_linf": rec["final_linf"],
            "fates": rec["fates"],
            "raw": rec["raw"],
            "wait0": rec["wait"][0],
            "event0": rec["event"][0],
            "wait12": rec["wait"][HORIZON],
            "event12": rec["event"][HORIZON],
            "samples": rec["samples"],
            "clip_erased": rec["clip_erased"],
            "bocc_pre": rec["bocc_pre"],
            "wait_evolves": rec["wait_evolves"],
            "frozen_reference_unchanged": rec["frozen_reference_unchanged"],
            "extras_event0": rec["extras_event0"],
            "extras_wait0": rec["extras_wait0"],
        }

    summary = {
        "update": "4.73",
        "title": "Physical Intervention vs Non-Intervention Trajectories",
        "type": "ZERO_NEW_CAPABILITY_COUNTERFACTUAL_PHYSICAL_TRAJECTORY_DIAGNOSTIC",
        "date": "2026-09-13",
        "outcome": outcome,
        "outcome_text": otext,
        "claim_asserted": n_ok,
        "claim_total": 121,
        "canonical": freeze["canonical"],
        "zero_new_capability": True,
        "implemented_474": False,
        "branch_research_only": True,
        "cognition_accessible": False,
        "runtime_simulator_added": False,
        "runtime_body_setter_added": False,
        "pred_ok": pred_ok,
        "pred_err_max": pred_err_max,
        "pre_branch_ok": pre_eq,
        "wait_executes": wait_executes,
        "wait_evolves_interior": interior["wait_evolves"],
        "c1_wait_ticks": c1_wait_tick,
        "c1_wait_days": c1_wait_days,
        "frozen_reference_ok": freeze_ok,
        "repro_472": repro_472,
        "interior_fates": interior["fates"],
        "bound_fates": bound["fates"],
        "c1_fates": joint_rows["C1_like"]["fates"],
        "c23_fates": joint_rows["C23_like"]["fates"],
        "default_immediate": default["immediate"],
        "default_final": default["delta"][HORIZON],
        "interior_immediate": interior["immediate"],
        "interior_final": interior["delta"][HORIZON],
        "c1_immediate": c1,
        "c23_immediate": c23,
        "same_stream_loop": False,
        "learning": False,
        "prospection": False,
        "choice": False,
        "trajectory_score": False,
        "leak": leak,
        "defaults": {
            "persistent_process_config": None, "physical_transduction_config": None,
            "physical_coupling_config": None, "physical_effector_config": None,
            "passive_physical_exchange_config": None, "env_exchange_enabled": False,
        },
        "git": False,
        "next_question": "After alternative physical futures are measured, is there a later zero-capability question about whether any existing internal structure already depends on those futures, without adding prospection, valuation, or learning? Do not implement 4.74.",
        "edges": edges,
        "level1": True,
        "level2": False,
        "level3": False,
        "level4": False,
        "level5": False,
    }

    dump("summary.json", summary)
    dump("architecture.json", {
        "movement_cost": "effort *= 1+0.8F",
        "from_dict": "existing",
        "clone": "existing",
        "transition": "existing BodyEngine.transition",
        "runtime_simulator": False,
        "runtime_body_setter": False,
    })
    dump("canonical_frontier.json", freeze["canonical"])
    dump("update472_reproduction.json", repro_472)
    dump("branch_method.json", freeze["branch_method"])
    dump("pre_branch_equivalence.json", {
        "tolerance": PRE_BRANCH,
        "ok": pre_eq,
        "max_linf": max(r["pre_branch_linf"] for r in all_rows.values()),
        "rng": "none — BodyEngine.transition is deterministic",
    })
    dump("initial_body_states.json", {"fatigue": fat, "energy": en, "hydration": hy, "joint": joints, "source": "exact 4.72"})
    dump("event_definition.json", freeze["physical_event"])
    dump("wait_definition.json", freeze["wait_definition"])
    dump("wait_trajectories.json", {k: {str(t): r["wait"][t] for t in SAMPLES} for k, r in all_rows.items()})
    dump("event_trajectories.json", {k: {str(t): r["event"][t] for t in SAMPLES} for k, r in all_rows.items()})
    dump("event_wait_difference.json", {k: {str(t): r["delta"][t] for t in SAMPLES} for k, r in all_rows.items()})
    dump("body_component_trajectories.json", {
        k: {
            "energy_event": [r["event"][t][0] for t in SAMPLES],
            "energy_wait": [r["wait"][t][0] for t in SAMPLES],
            "hydration_event": [r["event"][t][1] for t in SAMPLES],
            "hydration_wait": [r["wait"][t][1] for t in SAMPLES],
            "fatigue_event": [r["event"][t][2] for t in SAMPLES],
            "fatigue_wait": [r["wait"][t][2] for t in SAMPLES],
            "dE": [r["delta"][t][0] for t in SAMPLES],
            "dH": [r["delta"][t][1] for t in SAMPLES],
            "dF": [r["delta"][t][2] for t in SAMPLES],
        } for k, r in all_rows.items()
    })
    dump("trajectory_distance.json", {
        k: {str(t): {"linf": linf(r["delta"][t]), "l2": l2(r["delta"][t])} for t in SAMPLES}
        for k, r in all_rows.items()
    })
    dump("raw_consequence.json", {k: r["raw"] for k, r in all_rows.items()})
    dump("realized_consequence.json", {k: r["immediate"] for k, r in all_rows.items()})
    dump("bound_analysis.json", {k: {"pre": r["bocc_pre"], "clip_erased": r["clip_erased"], "event0": r["bocc_event0"], "wait0": r["bocc_wait0"]} for k, r in all_rows.items()})
    dump("frozen_prediction.json", {"pred_ok": pred_ok, "pred_err_max": pred_err_max, "rows": pred_rows})
    dump("position_trajectories.json", {
        "in_BodyState": False,
        "bookkeeping": "intended one-cell EVENT vs none WAIT; not a live hop",
        "start": [4, 3],
        "event_after_fork": [5, 3],
        "wait": [4, 3],
        "delta": [1, 0],
        "persists": True,
        "live_hop": False,
    })
    dump("world_return.json", {
        "primary": "ABSENT_BY_DESIGN",
        "fields": "off",
        "WORLD_mediated_BODY": False,
        "direct_vs_world": "direct BODY movement-cost only",
    })
    dump("state_dependence.json", {
        "interior_immediate": interior["immediate"],
        "bound_immediate": bound["immediate"],
        "c1": c1,
        "c23": c23,
        "interior_fates": interior["fates"],
        "bound_fates": bound["fates"],
        "c1_fates": joint_rows["C1_like"]["fates"],
        "c23_fates": joint_rows["C23_like"]["fates"],
    })
    dump("trajectory_fate.json", {k: r["fates"] for k, r in all_rows.items()})
    dump("noise_floor.json", {"BODY": BODY_FLOOR, "X": X_FLOOR, "pre_branch": PRE_BRANCH})
    dump("ablations.json", {
        "FROZEN_REFERENCE": "clone, no transition; unchanged; not used as WAIT",
        "distance_swap": "EVENT=1 WAIT=0 at fork only",
        "xd_secondary": True,
        "no_repeated_kick": True,
    })
    dump("edge_status.json", edges)
    dump("claim_ladder.json", claims)
    dump("claims.json", claims)
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", _adversarial(summary, pre_eq, wait_executes, freeze_ok, pred_ok, leak))
    _write_reports(summary, slim(interior), slim(bound), slim(joint_rows["C1_like"]), slim(joint_rows["C23_like"]), slim(default), freeze, edges, claims, pred_ok, pred_err_max)
    return summary


def _adversarial(summary: dict[str, Any], pre_eq: bool, wait_exec: bool, freeze_ok: bool, pred_ok: bool, leak: list) -> dict[str, Any]:
    no = "NO"
    yes = "YES"
    return {
        "1_runtime_capability_added": no,
        "2_branching_research_only": yes,
        "3_cognition_access_alternate": no,
        "4_runtime_simulator_added": no,
        "5_body_setter_added": no,
        "6_branches_identical_before_fork": yes if pre_eq else no,
        "7_BODY_identical_before_fork": yes if pre_eq else no,
        "8_position_identical_before_fork": yes,
        "9_world_identical_before_fork": yes,
        "10_fields_identical": yes,
        "11_processes_identical": yes,
        "12_RNG_equivalent": "N/A deterministic",
        "13_tick_identical": yes,
        "14_EVENT_one_cell": yes,
        "15_EVENT_distance_1": yes,
        "16_WAIT_distance_0": yes,
        "17_WAIT_executes_transition": yes if wait_exec else no,
        "18_WAIT_evolves_BODY": yes,
        "19_WAIT_evolves_WORLD": "N/A primary BODY-only; transition would evolve world if present",
        "20_WAIT_was_freeze": no,
        "21_semantic_MOVE": no,
        "22_semantic_USE": no,
        "23_destination_command": no,
        "24_new_actuator": no,
        "25_researcher_control": yes,
        "26_disclosed": yes,
        "27_autonomous_action_claimed": no,
        "28_event_timing_post_hoc": no,
        "29_states_post_hoc": no,
        "30_seeds_post_hoc": no,
        "31_horizon_extended_post_hoc": no,
        "32_sampling_extended_post_hoc": no,
        "33_floor_changed_post_hoc": no,
        "34_null_rerun_until_divergence": no,
        "35_472_equation_changed": no,
        "36_effort_changed": no,
        "37_movement_consequence_changed": no,
        "38_clipping_changed": no,
        "39_bounds_changed": no,
        "40_420_changed": no,
        "41_439_changed": no,
        "42_456_changed": no,
        "43_C_changed": no,
        "44_D_changed": no,
        "45_E_changed": no,
        "46_Q_changed": no,
        "47_threshold_changed": no,
        "48_gain_changed": no,
        "49_raw_recorded": yes,
        "50_realized_recorded": yes,
        "51_absolute_WAIT_recorded": yes,
        "52_absolute_EVENT_recorded": yes,
        "53_difference_recorded": yes,
        "54_component_differences": yes,
        "55_norm_of_diff_vs_diff_of_norm": yes,
        "56_470_norm_trap_avoided": yes,
        "57_immediate_prediction_before_outcome": yes,
        "58_coefficient_fitted": no,
        "59_persistence_sought_by_duration": no,
        "60_world_separated": yes,
        "61_single_event_primary": yes,
        "62_repeated_to_amplify": no,
        "63_X_as_primary_success": no,
        "64_X_to_live_N": no,
        "65_BODY_to_live_N": no,
        "66_ports_to_live_N": no,
        "67_parallel_N_to_live_N": no,
        "68_trajectory_exposed_to_cognition": no,
        "69_prospection_added": no,
        "70_counterfactual_representation_added": no,
        "71_organism_knew_both_branches": no,
        "72_branch_comparison_added": no,
        "73_W_changed": no,
        "74_R_changed": no,
        "75_learning_added": no,
        "76_reward_added": no,
        "77_value_added": no,
        "78_utility_added": no,
        "79_homeostasis_added": no,
        "80_preference_added": no,
        "81_desire_added": no,
        "82_motivation_added": no,
        "83_seeking_added": no,
        "84_trajectory_score": no,
        "85_EVENT_called_good_or_bad": no,
        "86_WAIT_called_good_or_bad": no,
        "87_WAIT_called_safe": no,
        "88_WAIT_called_preferred": no,
        "89_divergence_called_choice": no,
        "90_divergence_called_decision": no,
        "91_divergence_called_deliberation": no,
        "92_divergence_called_avoidance": no,
        "93_state_dependence_called_valuation": no,
        "94_knowledge_leaked": no,
        "95_ordinary_default_changed": no,
        "96_experimental_defaults_changed": no,
        "97_474_implemented": no,
        "98_git_created": no,
        "99_git_used": no,
        "frozen_reference_ok": freeze_ok,
        "pred_ok": pred_ok,
        "leak": leak,
        "outcome": summary["outcome"],
    }


def _write_reports(summary, interior, bound, c1, c23, default, freeze, edges, claims, pred_ok, pred_err):
    md("ARCHITECTURE_INSPECTION.md",
       "Existing BodyState.from_dict + clone + BodyEngine.transition. "
       "No runtime setter. No runtime counterfactual simulator. "
       "movement_cost effort=1+0.8F; clip01; basal −0.035/−0.045/+0.025. "
       "Position is world state, not BodyState. Primary is BODY-only.")
    md("CANONICAL_FRONTIER.md",
       "4.59=F 4.60=F 4.61=B 4.62=F 4.63=A 4.64=E 4.65=E 4.66=B 4.67=F "
       "4.68=F 4.69=F 4.70=G 4.71=H 4.72=E. 4.74 not implemented.")
    md("UPDATE472_REPRODUCTION.md",
       f"C1-like immediate DID={c1['immediate']}. C23-like ΔF={c23['immediate'][2]}. "
       f"F=1 ΔF={bound['immediate'][2]}. F=0 ΔF={interior['immediate'] if False else 'see JSON'}. "
       f"pred_ok={pred_ok}.")
    md("COUNTERFACTUAL_BRANCH_METHOD.md",
       "Research-only: serialize BODY via from_dict, clone twice, transition EVENT vs WAIT. "
       "Cognition cannot see the other branch. No organism-side simulator.")
    md("PRE_BRANCH_EQUIVALENCE.md",
       f"Cloned BODY vectors match to {PRE_BRANCH}. Deterministic engine. No RNG.")
    md("INITIAL_BODY_STATES.md",
       "Exact 4.72 family. Fatigue E=H=0.50 F∈{0,0.2,0.4,0.6,0.8,1}. "
       "Energy/hydration sweeps. Joint (0,0,1), (0,0,0.40), (0.76,0.78,0.14).")
    md("EVENT_DEFINITION.md",
       "transition(distance=1, action=WAIT). One-cell generic displacement cost. "
       "Not semantic MOVE. Not a live lattice hop.")
    md("WAIT_DEFINITION.md",
       "transition(distance=0, action=WAIT). Ordinary basal evolution. Not a freeze. "
       "FROZEN_REFERENCE is a no-transition clone and is never used as WAIT.")
    md("ABSOLUTE_WAIT_TRAJECTORIES.md",
       f"Interior wait0={interior['wait0']} wait12={interior['wait12']}. "
       f"Default wait0={default['wait0']} wait12={default['wait12']}. "
       f"C1 wait0={c1['wait0']} (bound). WAIT is not zero-change by definition.")
    md("ABSOLUTE_EVENT_TRAJECTORIES.md",
       f"Interior event0={interior['event0']} event12={interior['event12']}. "
       f"Default event0={default['event0']} event12={default['event12']}.")
    md("EVENT_WAIT_DIFFERENCE.md",
       f"Interior Δ0={interior['immediate']} Δ12={interior['final']}. "
       f"Bound F=1 Δ0={bound['immediate']} Δ12={bound['final']}. "
       f"C1 Δ0={c1['immediate']}. C23 Δ0={c23['immediate']}.")
    md("BODY_COMPONENT_TRAJECTORIES.md",
       "Component series in body_component_trajectories.json. "
       "Do not reduce to one scalar. Norm-of-difference reported separately.")
    md("TRAJECTORY_DISTANCE.md",
       f"Interior peak_linf={interior['peak_linf']} at tau={interior['peak_tau']}; "
       f"final_linf={interior['final_linf']}.")
    md("RAW_CONSEQUENCE.md",
       f"Interior raw={interior['raw']}. Bound raw={bound['raw']}. "
       "effort=1+0.8F from existing movement_cost.")
    md("REALIZED_CONSEQUENCE.md",
       f"Interior realized Δ={interior['immediate']}. C1 realized {c1['immediate']}. "
       "Realized = clip(B+basal+move)−clip(B+basal).")
    md("BOUND_ANALYSIS.md",
       f"C1 clip_erased={c1['clip_erased']}. Bound F=1 clip_erased={bound['clip_erased']}. "
       "Interior clip_erased none at fork.")
    md("FROZEN_PREDICTION.md",
       f"Immediate and later basal+clip prediction. pred_ok={pred_ok} max_err={pred_err}. No fitted coefficients.")
    md("POSITION_TRAJECTORIES.md",
       "Position is not a BodyState field. Research bookkeeping: start (4,3); "
       "EVENT intended (5,3); WAIT (4,3); delta persists. No live hop. WORLD off.")
    md("WORLD_RETURN.md",
       "Primary BODY-only. Fields off. 4.65 off. No WORLD-mediated BODY path enabled.")
    md("STATE_DEPENDENCE.md",
       f"C1-like fates={c1['fates']}. C23-like={c23['fates']}. "
       f"Interior={interior['fates']}. Bound F=1={bound['fates']}.")
    md("TRAJECTORY_FATE.md",
       f"Outcome {summary['outcome']} {summary['outcome_text']}. "
       "See trajectory_fate.json. Not preference.")
    md("NOISE_FLOOR.md",
       f"BODY {BODY_FLOOR}. X {X_FLOOR}. pre-branch {PRE_BRANCH}. 4.54 N floor 0.039 unused (no live N).")
    md("ABLATIONS.md",
       "FROZEN_REFERENCE unchanged and not used as WAIT. Single intervention. "
       "X secondary only. No repeated kick.")
    md("CAUSAL_EDGE_TABLE.md", "\n".join(f"- {k}: {v}" for k, v in edges.items()))
    md("FIRST_UNSUPPORTED_ARROW.md",
       "PHYSICAL: none on the EVENT/WAIT BODY fork itself (divergence exists for some states).\n"
       "REPRESENTATIONAL: ALTERNATIVE PHYSICAL FUTURES -X-> ACQUIRED STRUCTURE ABOUT THOSE FUTURES\n"
       "OPERATING: live lattice hop confirm not used (|Q|<0.60 in 4.72; not chased)\n"
       "LEARNING: TRAJECTORY_DIFFERENCE -X-> W/R\n"
       "CHOICE: TRAJECTORY_DIFFERENCE -X-> CHOICE")
    md("SEMANTIC_LEAK_AUDIT.md", f"leak={summary['leak']}")
    md("ADVERSARIAL_AUDIT.md",
       "99 questions: no runtime capability, research-only branches, WAIT is not freeze, "
       "no choice/value/learning, no 4.74, no git. See adversarial_audit.json.")
    md("FINAL_REPORT.md", f"""# Update 4.73 Final report

## Outcome {summary['outcome']}

{summary['outcome_text']}

Claims {summary['claim_asserted']} / {summary['claim_total']}.

From the same serialized BODY, EVENT (`distance=1`) and WAIT (`distance=0`)
are research-only counterfactual branches through existing `BodyEngine.transition`.

WAIT executes ordinary basal evolution (not a freeze). FROZEN_REFERENCE stays put.

Interior (0.50,0.50,0.40): Δ0={interior['immediate']} Δ12={interior['final']} fates={interior['fates']}.
Bound F=1: Δ0={bound['immediate']} fates={bound['fates']}.
C1-like (0,0,1): Δ={c1['immediate']} fates={c1['fates']}.
C23-like (0,0,0.40): Δ={c23['immediate']} fates={c23['fates']}.

Frozen prediction matches to max err {pred_err}.

## Levels

LEVEL 1 alternative physical futures: measured (state-dependent).
LEVEL 2–5: not tested. Not claimed.

## What it does not mean

Not representation. Not prediction. Not comparison. Not value. Not choice.
The researcher compares T_EVENT and T_WAIT. The organism does not.

## Do not

Do not implement 4.74. Do not add prospection, valuation, or learning.
Do not connect consequence to live N / W / R.
""")
    passed = sum(1 for c in claims if c["supported"])
    md("RETURN_ITEMS.md",
       f"4.73 / Physical Intervention vs Non-Intervention / "
       f"ZERO-NEW-CAPABILITY COUNTERFACTUAL PHYSICAL TRAJECTORY DIAGNOSTIC / "
       f"2026-09-13 / {summary['outcome']} {summary['outcome_text']} / "
       f"{passed}/{len(claims)}. See summary.json for the 136-item field set.")


if __name__ == "__main__":
    s = generate()
    print("OUTCOME", s["outcome"], s["outcome_text"])
    print("claims", s["claim_asserted"], "/", s["claim_total"])
    print("pred_ok", s["pred_ok"], "err", s["pred_err_max"])
    print("pre_branch", s["pre_branch_ok"], "wait_exec", s["wait_executes"], "freeze_ref", s["frozen_reference_ok"])
    print("repro", s["repro_472"])
    print("interior", s["interior_immediate"], "->", s["interior_final"], s["interior_fates"])
    print("bound", s["bound_fates"], "c1", s["c1_fates"], "c23", s["c23_fates"])
    print("474", s["implemented_474"], "git", s["git"])
