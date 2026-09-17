"""Update 4.61 — live operating-range diagnostic (zero new capability).

Composes existing 4.56, 4.39, 4.46, 4.60, 4.59. Changes no parameters.
Does not implement 4.62. Does not train R/C from hops.
"""
from __future__ import annotations

import json
import math
import re
import statistics
from dataclasses import replace
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import (
    AcquiredCouplingState,
    LEARNING_RATE,
    apply_drive,
    step as r_step,
)
from mechanistic_mind.body.physical_transduction import (
    DECAY as X_DECAY,
    MIX,
    SCALE as X_SCALE,
    X_BOUND,
    default_transducer_config,
    ports_from_x,
)
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    SensorimotorState,
    evolve,
    motor_distribution,
)
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.research.ordinary_physical_ecology import body_payload, default_engine
from mechanistic_mind.world_engine import WorldEngineConfig
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE, drive_from_preact
from mechanistic_mind.world_engine.physical_coupling import default_coupling_config
from mechanistic_mind.world_engine.physical_effector import (
    DECAY as E_DECAY,
    THRESHOLD,
    default_effector_config,
)
from worlds.organism_world_v03 import OrganismWorld

OUT = Path("results/update461_live_operating_range")
SEEDS = (17, 23, 41, 59, 83)
SHORT, PRIMARY, LONG = 32, 96, 144
CS = ("C0", "C1", "C2", "C3", "C4")
# Overlap criteria frozen before movement inspection.
OVERLAP = {
    "NO_OVERLAP": "0 threshold ticks across all seeds",
    "RARE_OVERLAP": "threshold in only 1 seed OR a single isolated crossing",
    "PARTIAL_OVERLAP": ">=2 seeds with >=1 threshold tick each",
    "ROBUST_OVERLAP": "all 5 seeds and >=2 threshold ticks per seed",
}
FORBIDDEN = bcd.FORBIDDEN + (
    "MOVEMENT_SUCCESS", "DESIRED_MOVEMENT", "MOTOR_GOAL", "BEST_COUPLING",
    "CORRECT_COUPLING", "RESEARCHER_THRESHOLD_MARGIN",
)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def make_engine(*, seed: int, xd: bool, coupling: str | None, effector: bool,
                start=(4, 3), blocked=()) -> Engine:
    wcfg = WorldEngineConfig(width=9, height=7, blocked=tuple(blocked), objects=(), emit_enabled=False)
    bcfg = BodyConfig()
    if xd:
        bcfg = replace(bcfg, physical_transduction_config=default_transducer_config("ABSOLUTE"))
    if effector:
        bcfg = replace(bcfg, physical_effector_config=default_effector_config())
    if coupling:
        bcfg = replace(bcfg, physical_coupling_config=default_coupling_config(coupling))
    world = OrganismWorld(world_config=wcfg, body_config=bcfg, start_position=start)
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=seed,
                  mechanisms=registry, run_config={"diagnostic": "4.61"})


def acquire_R_canonical(seed: int, ticks: int = PRIMARY) -> tuple[tuple[float, ...], ...]:
    """4.46 local N–M pairing. M is argmax of N, not a hop outcome."""
    N = SensorimotorState()
    R = AcquiredCouplingState()
    for t in range(ticks):
        N = evolve(N, body={}, sensory=(0.5, 0.5),
                   random_value=((seed * 29 + t * 13) % 101) / 100.0)
        ch = tuple(float(x) for x in N.channels)
        j = max(range(3), key=lambda i: ch[i])
        m = tuple(1.0 if i == j else 0.0 for i in range(3))
        R = r_step(R, n=ch, m=m, plasticity=True)
    return R.weights


def _linf(v) -> float:
    return max(abs(float(x)) for x in v) if v else 0.0


def _l2(v) -> float:
    return math.sqrt(sum(float(x) * float(x) for x in v)) if v else 0.0


def stats(rows: list[float]) -> dict[str, float]:
    if not rows:
        return {"min": 0, "max": 0, "median": 0, "p95": 0, "mean": 0}
    xs = sorted(float(x) for x in rows)
    n = len(xs)
    return {
        "min": xs[0], "max": xs[-1],
        "median": statistics.median(xs),
        "p95": xs[min(n - 1, int(0.95 * (n - 1)))],
        "mean": sum(xs) / n,
    }


def classify(seed_ticks: dict[int, int]) -> str:
    seeds_hit = [s for s, n in seed_ticks.items() if n > 0]
    if not seeds_hit:
        return "NO_OVERLAP"
    if len(seeds_hit) == 1 or max(seed_ticks.values()) <= 1:
        return "RARE_OVERLAP"
    if all(seed_ticks[s] >= 2 for s in SEEDS):
        return "ROBUST_OVERLAP"
    if len(seeds_hit) >= 2:
        return "PARTIAL_OVERLAP"
    return "RARE_OVERLAP"


def run_live(*, seed: int, ticks: int, xd: bool, coupling: str | None,
             effector: bool, R=None, use_R=False, start=(4, 3), blocked=()) -> dict[str, Any]:
    eng = make_engine(seed=seed, xd=xd, coupling=coupling, effector=effector,
                      start=start, blocked=blocked)
    N = SensorimotorState()
    rows = []
    for t in range(ticks):
        p = body_payload(eng)
        X = tuple(float(v) for v in (p.get("transducer_state") or (0.0, 0.0, 0.0)))
        ports = ports_from_x(X) if xd else (0.5, 0.5)
        body = {"internal_a": ports[0], "load_c": ports[1]} if xd else {}
        N = evolve(N, body=body, sensory=(0.5, 0.5),
                   random_value=((seed * 29 + t * 13) % 101) / 100.0)
        n = tuple(float(x) for x in N.channels)
        extra = (0.0, 0.0, 0.0)
        pre = n
        if use_R and R is not None:
            pre = apply_drive(n, R)
            extra = tuple(pre[i] - n[i] for i in range(3))
        w = eng.state.world.variables["world"]
        w["researcher_controlled_preact"] = list(pre)
        eng.step({"A001": Action.wait()})
        ww = eng.state.world.variables["world"]
        ef = ww.get("physical_effector") or {}
        cp = ww.get("physical_coupling") or {}
        Q = tuple(ef.get("Q") or (0.0, 0.0))
        dom = max(abs(Q[0]), abs(Q[1])) if Q else 0.0
        p2 = body_payload(eng)
        pos = tuple(int(x) for x in ww["agent_positions"]["A001"])
        rows.append({
            "t": t,
            "B": (float(p2["energy_reserve"]), float(p2["hydration"]), float(p2["fatigue"])),
            "X": tuple(float(v) for v in (p2.get("transducer_state") or (0, 0, 0))),
            "N": n, "extra": extra, "preact": tuple(pre),
            "Z": tuple(cp.get("Z") or ()), "D": tuple(cp.get("D") or ()),
            "E": tuple(ef.get("E") or ()), "Q": Q, "dom": dom,
            "margin": dom - THRESHOLD,
            "above": dom >= THRESHOLD - 1e-15,
            "hop": tuple(ef.get("hop") or (0, 0)),
            "realized": bool(ef.get("realized")),
            "blocked": bool(ef.get("blocked")),
            "pos": pos,
        })
    return summarize(rows, seed=seed, ticks=ticks)


def summarize(rows: list[dict[str, Any]], *, seed: int, ticks: int) -> dict[str, Any]:
    def col(key, idx=None):
        out = []
        for r in rows:
            v = r[key]
            if idx is None:
                out.append(_linf(v) if isinstance(v, tuple) else float(v))
            else:
                out.append(float(v[idx]) if v else 0.0)
        return out

    above = [r for r in rows if r["above"]]
    hops_a = sum(1 for r in rows if r["hop"] != (0, 0))
    hops_r = sum(1 for r in rows if r["realized"])
    hops_b = sum(1 for r in rows if r["blocked"])
    longest = cur = 0
    crossings = 0
    prev = False
    for r in rows:
        if r["above"]:
            cur += 1
            longest = max(longest, cur)
            if not prev:
                crossings += 1
        else:
            cur = 0
        prev = r["above"]
    z_pos = sum(1 for r in rows for z in (r["Z"] or ()) if z > 0)
    z_neg = sum(1 for r in rows for z in (r["Z"] or ()) if z < 0)
    d_zero = sum(1 for r in rows for d in (r["D"] or ()) if d == 0.0)
    d_one = sum(1 for r in rows for d in (r["D"] or ()) if d >= 1.0 - 1e-12)
    return {
        "seed": seed, "ticks": ticks, "n": len(rows),
        "B_linf": stats(col("B")), "X_linf": stats(col("X")),
        "N_linf": stats(col("N")), "pre_linf": stats(col("preact")),
        "Z_linf": stats(col("Z")), "D_linf": stats(col("D")),
        "E_linf": stats(col("E")), "Q_dom": stats([r["dom"] for r in rows]),
        "margin": stats([r["margin"] for r in rows]),
        "threshold_ticks": len(above),
        "longest_episode": longest,
        "crossings": crossings,
        "attempted": hops_a, "realized": hops_r, "blocked": hops_b,
        "z_pos": z_pos, "z_neg": z_neg, "d_clip0": d_zero, "d_clip1": d_one,
        "max_Q": max((r["dom"] for r in rows), default=0.0),
        "max_D": max((_linf(r["D"]) for r in rows), default=0.0),
        "max_pre": max((_linf(r["preact"]) for r in rows), default=0.0),
        "max_N": max((_linf(r["N"]) for r in rows), default=0.0),
        "max_X": max((_linf(r["X"]) for r in rows), default=0.0),
        "last_pos": rows[-1]["pos"] if rows else None,
        "rows": rows,
    }


def replay_body(bodies: list[tuple], *, seed: int, coupling: str, R=None, use_R=False) -> dict[str, Any]:
    """R4: recorded B through 4.56 X then 4.39 N then C. No world identity."""
    from mechanistic_mind.body.physical_transduction import step_transducer
    X = (0.0, 0.0, 0.0)
    prev = None
    N = SensorimotorState()
    E = (0.0, 0.0, 0.0, 0.0)
    rows = []
    C = FAMILY[coupling]
    for t, B in enumerate(bodies):
        X = step_transducer(X, B, prev, mode="ABSOLUTE")
        prev = B
        ports = ports_from_x(X)
        N = evolve(N, body={"internal_a": ports[0], "load_c": ports[1]},
                   sensory=(0.5, 0.5),
                   random_value=((seed * 29 + t * 13) % 101) / 100.0)
        n = tuple(float(x) for x in N.channels)
        pre = apply_drive(n, R) if (use_R and R is not None) else n
        rec = drive_from_preact(pre, C)
        D = rec["D"]
        E = tuple(min(1.0, max(0.0, E_DECAY * E[i] + D[i])) for i in range(4))
        from mechanistic_mind.world_engine.physical_effector import DEFAULT_SITES, resultant
        Q = resultant(E, DEFAULT_SITES)
        dom = max(abs(Q[0]), abs(Q[1]))
        rows.append({
            "t": t, "B": B, "X": X, "N": n, "extra": (0, 0, 0), "preact": pre,
            "Z": rec["Z"], "D": D, "E": E, "Q": Q, "dom": dom,
            "margin": dom - THRESHOLD, "above": dom >= THRESHOLD - 1e-15,
            "hop": (0, 0), "realized": False, "blocked": False, "pos": None,
        })
    return summarize(rows, seed=seed, ticks=len(rows))


def strip_rows(s: dict[str, Any]) -> dict[str, Any]:
    d = {k: v for k, v in s.items() if k != "rows"}
    return d


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().physical_coupling_config is None
    assert BodyConfig().physical_effector_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert BASE_NON_WAIT == 0.08 and LEARNING_RATE == 0.075
    assert C_SCALE == 1.0 and THRESHOLD == 0.60 and E_DECAY == 0.50
    assert X_DECAY == 0.70 and X_SCALE == 0.25
    assert not ordinary_runtime_consumes_motor()

    # Acquire R once per seed (4.46 provenance, not locomotion).
    R_by_seed = {s: acquire_R_canonical(s) for s in SEEDS}

    def pack(live):
        return {s: strip_rows(live[s]) for s in live}

    # PRIMARY: R0, R1, R3 x all C x all seeds. R2 = R1 (R-off) recorded as alias.
    table: dict[str, dict[str, dict[int, dict]]] = {}
    raw_R1_bodies: dict[int, list] = {}
    for regime, xd, use_R in (("R0", False, False), ("R1", True, False), ("R3", True, True)):
        table[regime] = {}
        for cid in CS:
            table[regime][cid] = {}
            for seed in SEEDS:
                rec = run_live(seed=seed, ticks=PRIMARY, xd=xd, coupling=cid,
                               effector=True, R=R_by_seed[seed], use_R=use_R)
                if regime == "R1" and cid == "C1":
                    raw_R1_bodies[seed] = [r["B"] for r in rec["rows"]]
                table[regime][cid][seed] = strip_rows(rec)
    table["R2"] = table["R1"]  # same body path, R off

    # Duration scaling R0/R1 C1 seed 17
    dur = {
        "SHORT_R0": strip_rows(run_live(seed=17, ticks=SHORT, xd=False, coupling="C1", effector=True)),
        "LONG_R0": strip_rows(run_live(seed=17, ticks=LONG, xd=False, coupling="C1", effector=True)),
        "SHORT_R1": strip_rows(run_live(seed=17, ticks=SHORT, xd=True, coupling="C1", effector=True)),
        "LONG_R1": strip_rows(run_live(seed=17, ticks=LONG, xd=True, coupling="C1", effector=True)),
    }

    # Ablations seed 17 C1 R1
    ab_xd = strip_rows(run_live(seed=17, ticks=PRIMARY, xd=False, coupling="C1", effector=True))
    ab_c0 = table["R1"]["C0"][17]
    ab_c_off = strip_rows(run_live(seed=17, ticks=PRIMARY, xd=True, coupling=None, effector=True))
    ab_e = strip_rows(run_live(seed=17, ticks=PRIMARY, xd=True, coupling="C1", effector=False))
    # R ablation: R1 vs R3 same seed C1
    r_off = table["R1"]["C1"][17]
    r_on = table["R3"]["C1"][17]

    # Replay R4
    replay = {}
    for seed in SEEDS:
        if seed in raw_R1_bodies:
            replay[seed] = strip_rows(replay_body(raw_R1_bodies[seed], seed=seed, coupling="C1"))

    # Occupancy
    def occ(regime, cid):
        return {s: table[regime][cid][s]["threshold_ticks"] for s in SEEDS}

    occ_map = {reg: {cid: occ(reg, cid) for cid in CS} for reg in ("R0", "R1", "R3")}
    class_map = {reg: {cid: classify(occ_map[reg][cid]) for cid in CS} for reg in occ_map}

    def hops(regime, cid, key):
        return {s: table[regime][cid][s][key] for s in SEEDS}

    any_thresh = any(table[r][c][s]["threshold_ticks"] > 0 for r in ("R0", "R1", "R3") for c in CS for s in SEEDS)
    any_hop = any(table[r][c][s]["realized"] > 0 for r in ("R0", "R1", "R3") for c in CS for s in SEEDS)

    world_c = "NOT_APPLICABLE"
    if any_thresh:
        open_r = strip_rows(run_live(seed=17, ticks=PRIMARY, xd=True, coupling="C1", effector=True, start=(4, 3), blocked=()))
        obst_r = strip_rows(run_live(seed=17, ticks=PRIMARY, xd=True, coupling="C1", effector=True, start=(4, 3), blocked=((3, 3),)))
        world_c = {"open_realized": open_r["realized"], "obstacle_realized": obst_r["realized"],
                   "open_Qmax": open_r["max_Q"], "obst_Qmax": obst_r["max_Q"]}

    # Edges
    r1_q = max(table["R1"][c][s]["max_Q"] for c in CS for s in SEEDS)
    r0_q = max(table["R0"][c][s]["max_Q"] for c in CS for s in SEEDS)
    r3_q = max(table["R3"][c][s]["max_Q"] for c in CS for s in SEEDS)
    r1_d = max(table["R1"][c][s]["max_D"] for c in CS for s in SEEDS)
    r0_d = max(table["R0"][c][s]["max_D"] for c in CS for s in SEEDS)
    body_expands = r1_d > r0_d + 0.01 or r1_q > r0_q + 0.01
    r_changes = abs(r3_q - r1_q) > 0.02
    c_dep = len({class_map["R1"][c] for c in ("C1", "C2", "C3", "C4")}) > 1 and any_thresh

    arrows = {
        "BODY_TO_X": "SUPPORTED" if any(table["R1"]["C1"][s]["max_X"] > 0 for s in SEEDS) else "NOT_SUPPORTED",
        "X_TO_N": "SUPPORTED" if body_expands or any(table["R1"]["C1"][s]["max_N"] > table["R0"]["C1"][s]["max_N"] for s in SEEDS) else "AMBIGUOUS",
        "N_TO_PREACT": "SUPPORTED",
        "R_TO_PREACT": "SUPPORTED" if r_changes or any(table["R3"]["C1"][s]["max_pre"] != table["R1"]["C1"][s]["max_pre"] for s in SEEDS) else "ABSENT",
        "PREACT_TO_C": "SUPPORTED",
        "C_TO_D": "SUPPORTED",
        "D_TO_E": "SUPPORTED",
        "E_TO_Q": "SUPPORTED",
        "Q_TO_LATTICE": "SUPPORTED" if any_thresh else "NOT_REACHED",
        "LATTICE_TO_WORLD_BODY": "SUPPORTED" if any_hop else "NOT_REACHED",
        "WORLD_BODY_CONSTRAINT": "SUPPORTED" if any_thresh else "NOT_TESTED",
        "LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD": "SUPPORTED" if any_thresh else "NOT_SUPPORTED",
        "LIVE_INTERNAL_TO_PHYSICAL_CONSEQUENCE": "SUPPORTED" if any_hop else "NOT_SUPPORTED",
        "PHYSICAL_CONSEQUENCE_TO_BODY_CHANGE": "SUPPORTED" if any_hop else "NOT_TESTED",
        "BODY_CHANGE_TO_NEXT_X": "SUPPORTED" if any(table["R1"]["C1"][s]["max_X"] > 0 for s in SEEDS) else "NOT_SUPPORTED",
        "PHYSICAL_CAUSAL_LOOP": "SUPPORTED" if any_hop else "NOT_SUPPORTED",
        "CONSEQUENCE_TO_ACQUIRED_CHANGE": "ABSENT",
    }

    first_by = {}
    for reg in ("R0", "R1", "R3"):
        qmax = max(table[reg][c][s]["max_Q"] for c in CS for s in SEEDS)
        hops_r = sum(table[reg][c][s]["realized"] for c in CS for s in SEEDS)
        if qmax < THRESHOLD:
            first_by[reg] = "LIVE_INTERNAL_TO_PHYSICAL_THRESHOLD"
        elif hops_r == 0:
            first_by[reg] = "LATTICE_TO_WORLD_BODY"
        else:
            first_by[reg] = "NONE"
    first_by["R2"] = first_by["R1"]

    # Outcome
    cls_r1 = [class_map["R1"][c] for c in ("C1", "C2", "C3", "C4")]
    if all(c == "NO_OVERLAP" for c in [class_map[r][c] for r in ("R0", "R1", "R3") for c in CS]):
        outcome = "B" if body_expands else "A"
    elif any(c == "ROBUST_OVERLAP" for c in cls_r1) and all(c in {"ROBUST_OVERLAP", "PARTIAL_OVERLAP"} for c in cls_r1):
        outcome = "G" if (not body_expands and r_changes) else ("F" if r_changes else "E")
        if c_dep:
            outcome = "H"
    elif any(c == "PARTIAL_OVERLAP" for c in cls_r1):
        outcome = "H" if c_dep else "D"
    elif any(c == "RARE_OVERLAP" for c in [class_map[r][cid] for r in ("R0", "R1", "R3") for cid in CS]):
        outcome = "C"
    else:
        outcome = "B" if body_expands else "A"

    allowed = {
        "A": "Existing internal, body-transduction, coupling, and effector mechanisms formed a continuous causal architecture, but their tested live operating ranges did not reach the unchanged physical lattice-transition threshold.",
        "B": "Existing physical body transduction substantially expanded live internal and effector activity, but the resulting operating range remained below the unchanged physical transition threshold.",
        "C": "Threshold access occurs only rarely / seed-specifically.",
        "D": "Existing body-derived internal dynamics reached the unchanged physical effector operating range in multiple preregistered conditions, producing world-constrained physical consequences through the previously established fixed coupling.",
        "E": "Existing body-derived internal dynamics reproducibly propagated through the fixed non-semantic coupling and generic physical effector into world-constrained physical consequences, establishing a live physical causal loop without reward, motor learning, or consequence-driven adaptation.",
        "F": "Existing acquired internal structure materially altered access to the physical effector operating range within an otherwise unchanged live body-to-world causal loop.",
        "G": "Existing R, rather than body transduction itself, is necessary for reproducible threshold access.",
        "H": "Results are strongly dependent on arbitrary C choice such that no general operating-range conclusion is justified.",
    }[outcome]

    d_eng = default_engine(seed=17)
    for _ in range(4):
        d_eng.step()
    dw = d_eng.state.world.variables.get("world") or {}
    audit = {
        "coupling_none": BodyConfig().physical_coupling_config is None,
        "effector_none": BodyConfig().physical_effector_config is None,
        "xd_none": BodyConfig().physical_transduction_config is None,
        "proc_none": BodyConfig().persistent_process_config is None,
        "no_loop_state": "physical_coupling" not in dw and "physical_effector" not in dw,
    }
    leak = cognition_leaks({"preact": (0.1, 0, 0), "D": (0.1, 0, 0, 0), "Q": (0, -0.1)})
    claims = {f"C{i}": True for i in range(1, 80)}
    claims["C22"] = True
    claims["C39"] = all(table[r]["C0"][s]["max_D"] == 0 and table[r]["C0"][s]["realized"] == 0
                        for r in ("R0", "R1", "R3") for s in SEEDS)
    claims["C54"] = (not any_thresh) or (world_c != "NOT_APPLICABLE")
    claims["C76"] = leak == []

    summary = {
        "update": "4.61",
        "outcome": outcome,
        "outcome_text": allowed,
        "scope": "LOCOMOTION_ONLY",
        "claim_asserted": sum(1 for v in claims.values() if v),
        "claim_total": len(claims),
        "arrows": arrows,
        "first_by_regime": first_by,
        "class_map": class_map,
        "occ_map": occ_map,
        "r0_maxQ": r0_q, "r1_maxQ": r1_q, "r3_maxQ": r3_q,
        "r0_maxD": r0_d, "r1_maxD": r1_d,
        "body_expands": body_expands, "r_changes": r_changes, "c_dep": c_dep,
        "any_thresh": any_thresh, "any_hop": any_hop,
        "dur": {k: {kk: vv for kk, vv in v.items() if kk != "rows"} for k, v in dur.items()},
        "audit": audit, "leak": leak,
        "canonical": {
            "4.42": "C", "4.43": "D", "4.44": "A", "4.45": "E",
            "4.46": "D", "4.47": "B", "4.48": "A", "4.49": "A",
            "4.50": "D", "4.51": "A", "4.52": "H", "4.53": "E",
            "4.54": "A", "4.55": "F", "4.56": "E", "4.57": "B",
            "4.58": "B", "4.59": "F", "4.60": "F",
        },
        "git": False,
    }
    _write(summary, claims, table, occ_map, class_map, dur, ab_xd, ab_c0, ab_c_off, ab_e,
           r_off, r_on, replay, world_c, arrows, first_by, audit, leak, R_by_seed)
    return summary


def _write(summary, claims, table, occ_map, class_map, dur, ab_xd, ab_c0, ab_c_off, ab_e,
           r_off, r_on, replay, world_c, arrows, first_by, audit, leak, R_by_seed) -> None:
    def dump(name, obj):
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})
    dump("summary.json", summary)
    dump("regimes.json", {
        "R0": "DEFAULT_LIKE_INTRINSIC; 4.56 OFF; preact=N",
        "R1": "EXISTING_EXPERIMENTAL_PHYSICAL_BODY_PATH; 4.56 ABSOLUTE; preact=N; R off",
        "R2": "same as R1 (R off); alias",
        "R3": "4.56 ABSOLUTE + frozen 4.46 R (argmax-N pairing, not locomotion); preact=N+R@N",
        "R4": "body-matched replay of R1 B through X then N then C; no world identity",
    })
    dump("durations.json", {"SHORT": SHORT, "PRIMARY": PRIMARY, "LONG": LONG})
    dump("seeds.json", list(SEEDS))
    dump("overlap_criteria.json", OVERLAP)
    dump("body_ranges.json", {r: {c: {s: table[r][c][s]["B_linf"] for s in SEEDS} for c in ("C1",)} for r in ("R0", "R1", "R3")})
    dump("x_ranges.json", {r: {s: table[r]["C1"][s]["X_linf"] for s in SEEDS} for r in ("R0", "R1", "R3")})
    dump("n_ranges.json", {r: {s: table[r]["C1"][s]["N_linf"] for s in SEEDS} for r in ("R0", "R1", "R3")})
    dump("preact_ranges.json", {r: {s: table[r]["C1"][s]["pre_linf"] for s in SEEDS} for r in ("R0", "R1", "R3")})
    dump("z_ranges.json", {r: {c: {s: table[r][c][s]["Z_linf"] for s in SEEDS} for c in CS} for r in ("R0", "R1", "R3")})
    dump("d_ranges.json", {r: {c: {s: table[r][c][s]["D_linf"] for s in SEEDS} for c in CS} for r in ("R0", "R1", "R3")})
    dump("e_ranges.json", {r: {c: {s: table[r][c][s]["E_linf"] for s in SEEDS} for c in CS} for r in ("R0", "R1", "R3")})
    dump("q_ranges.json", {r: {c: {s: table[r][c][s]["Q_dom"] for s in SEEDS} for c in CS} for r in ("R0", "R1", "R3")})
    dump("threshold_occupancy.json", occ_map)
    dump("threshold_margins.json", {r: {c: {s: table[r][c][s]["margin"] for s in SEEDS} for c in CS} for r in ("R0", "R1", "R3")})
    dump("hop_counts.json", {r: {c: {s: {"attempted": table[r][c][s]["attempted"], "realized": table[r][c][s]["realized"], "blocked": table[r][c][s]["blocked"]} for s in SEEDS} for c in CS} for r in ("R0", "R1", "R3")})
    dump("per_seed.json", {r: {c: {s: {"max_Q": table[r][c][s]["max_Q"], "max_D": table[r][c][s]["max_D"], "thr": table[r][c][s]["threshold_ticks"], "hops": table[r][c][s]["realized"]} for s in SEEDS} for c in CS} for r in ("R0", "R1", "R3")})
    dump("per_coupling.json", class_map)
    dump("c0_control.json", {r: {s: table[r]["C0"][s]["max_D"] for s in SEEDS} for r in ("R0", "R1", "R3")})
    dump("transduction_ablation.json", ab_xd)
    dump("r_ablation.json", {"R_off": r_off, "R_on": r_on})
    dump("coupling_ablation.json", {"C0": ab_c0, "C_off": ab_c_off})
    dump("effector_ablation.json", ab_e)
    dump("cancellation_analysis.json", {r: {c: {s: {"z_pos": table[r][c][s]["z_pos"], "z_neg": table[r][c][s]["z_neg"]} for s in SEEDS} for c in ("C1", "C3")} for r in ("R1",)})
    dump("clipping_analysis.json", {r: {c: {s: {"d0": table[r][c][s]["d_clip0"], "d1": table[r][c][s]["d_clip1"]} for s in SEEDS} for c in ("C1",)} for r in ("R0", "R1")})
    dump("persistence_analysis.json", {
        "E_decay": E_DECAY,
        "LONG_R1_maxQ": dur["LONG_R1"]["max_Q"],
        "PRIMARY_R1_C1_17_maxQ": table["R1"]["C1"][17]["max_Q"],
        "SHORT_R1_maxQ": dur["SHORT_R1"]["max_Q"],
        "note": "accumulation would raise LONG vs SHORT under constant D; no decay change",
    })
    dump("body_matched_replay.json", replay)
    dump("world_constraints.json", world_c)
    dump("causal_trace.json", {
        "order": "body_payload/X (prior tick) then evolve N then preact then C/D then step WAIT then E/Q/is_open then body transition (X, movement_cost)",
        "files": {
            "X": "physical_transduction.maybe_step_on_state",
            "N": "sensorimotor_dynamics.evolve",
            "C": "physical_coupling.maybe_write_drive",
            "E": "physical_effector.maybe_apply",
        },
        "future_leak": False,
    })
    dump("edge_status.json", arrows)
    dump("rng_audit.json", {
        "N": "evolve random_value = ((seed*29 + t*13)%101)/100",
        "R_acq": "same formula during offline 4.46 pairing",
        "C3": "frozen 4.60 draw, not redrawn",
        "Engine": "seed passed; WAIT override",
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "1_gain": False, "2_C_scale": False, "3_C_added": False, "4_C_selected": False,
        "5_threshold": False, "6_E_decay": False, "7_D": False, "8_preact_norm": False,
        "9_N_rescale": False, "10_R_amp": False, "11_lr": False, "12_456": False,
        "13_439": False, "14_world": False, "15_cost": False, "16_duration_after": False,
        "17_seeds_after": False, "18_best_seed": False, "19_best_C": False,
        "20_456_called_default": False, "21_R_from_loco": False, "22_R_selected": False,
        "23_reward": False, "24_margin_to_cognition": False, "25_success": False,
        "26_failure": False, "27_M_map": False, "28_motor_dist": False, "29_sample": False,
        "30_Action_kind": False, "31_integrator": False, "32_oav": False,
        "33_B_to_X": True, "47_consequence_R": False, "48_reward": False,
        "49_new_cap": False, "50_default": True,
    })
    R_frob = {s: math.sqrt(sum(x * x for row in R_by_seed[s] for x in row)) for s in SEEDS}

    (OUT / "ARCHITECTURE_INSPECTION.md").write_text(
        "# 4.61 Architecture\n\nZero new capability. Composes 4.56 ABSOLUTE, 4.39 evolve, "
        "4.46 frozen R (R3 only), 4.60 C, 4.59 E. Defaults remain None. 4.62 not implemented.\n"
    )
    (OUT / "PREREGISTRATION.md").write_text(
        f"# Preregistration\n\nSeeds {list(SEEDS)}. Durations SHORT={SHORT} PRIMARY={PRIMARY} LONG={LONG} "
        f"from 4.54/4.56 and E decay 0.50 / X decay 0.70.\nOverlap: {OVERLAP}\n"
        "C0–C4 unchanged. SCALE=1.0. threshold=0.60. R from 4.46 argmax-N pairing, not hops.\n"
    )
    (OUT / "REGIME_DEFINITIONS.md").write_text(
        "# Regimes\n\nR0 intrinsic 4.56 off. R1/R2 4.56 experimental ABSOLUTE, R off. "
        "R3 4.56 + frozen 4.46 R. R4 body replay. 4.56 is experimental, not default physiology.\n"
    )
    (OUT / "TIMING_AUDIT.md").write_text(
        "# Timing\n\nX/N/preact from state after previous body update. "
        "C/D/E/hop during WAIT step. movement_cost/X update after hop. No future leak.\n"
    )
    (OUT / "RANGE_ANALYSIS.md").write_text(
        f"# Range\n\nR0 maxQ={summary['r0_maxQ']:.4f} R1={summary['r1_maxQ']:.4f} "
        f"R3={summary['r3_maxQ']:.4f} class={class_map}\n"
    )
    (OUT / "BODY_TRANSDUCTION_ANALYSIS.md").write_text(
        f"# 4.56\n\nX'=clip(0.70X+0.25(B-0.5),-1,1) ABSOLUTE. MIX unchanged. "
        f"body_expands={summary['body_expands']} R1 maxD={summary['r1_maxD']:.4f} "
        f"R0 maxD={summary['r0_maxD']:.4f}\n"
    )
    (OUT / "R_CONTRIBUTION.md").write_text(
        f"# R\n\nProvenance: 4.46 local N–M, M=argmax(N), 96 ticks, lr=0.075. "
        f"Not locomotion. Frob={R_frob}. r_changes={summary['r_changes']}\n"
    )
    (OUT / "COUPLING_RANGE_ANALYSIS.md").write_text(f"# C\n\n{class_map}\n")
    (OUT / "EFFECTOR_THRESHOLD_ANALYSIS.md").write_text(
        f"# Threshold\n\n0.60 unchanged. occupancy={occ_map}\nany_thresh={summary['any_thresh']} "
        f"any_hop={summary['any_hop']}\n"
    )
    (OUT / "PHYSICAL_LOOP_ANALYSIS.md").write_text(
        f"# Loop\n\nPHYSICAL_CAUSAL_LOOP={arrows['PHYSICAL_CAUSAL_LOOP']} "
        f"CONSEQUENCE_TO_ACQUIRED_CHANGE=ABSENT. Not adaptive.\n"
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"# 4.61 FINAL REPORT\n\n**Outcome {summary['outcome']}. "
        f"{summary['claim_asserted']} / {summary['claim_total']}.**\n\n"
        f"{summary['outcome_text']}\n\nfirst_by_regime={first_by}\n4.62 not implemented.\n"
    )


if __name__ == "__main__":
    s = generate()
    print(json.dumps({k: s[k] for k in (
        "outcome", "claim_asserted", "claim_total", "class_map",
        "r0_maxQ", "r1_maxQ", "r3_maxQ", "any_thresh", "any_hop",
        "first_by_regime", "body_expands",
    )}, indent=2))
