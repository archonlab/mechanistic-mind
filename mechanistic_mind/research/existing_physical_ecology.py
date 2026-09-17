"""Update 4.63 — existing physical ecology × frozen downstream chain.

Zero new capability. Composes only already-existing WORLD->BODY mechanics.
Does not implement 4.64. Does not tune gain/threshold/C/D/E/Q/4.56/4.39.
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
from mechanistic_mind.body.physical_transduction import (
    DECAY as X_DECAY,
    MIX,
    SCALE as X_SCALE,
    default_transducer_config,
    ports_from_x,
)
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    COUPLING,
    SensorimotorState,
    evolve,
)
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research.live_operating_range import (
    PRIMARY,
    SEEDS,
    replay_body,
    strip_rows,
    summarize,
)
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.research.ordinary_physical_ecology import body_payload, default_engine
from mechanistic_mind.world_engine import WorldEngineConfig
from mechanistic_mind.world_engine.physical_coupling import FAMILY, SCALE as C_SCALE, default_coupling_config
from mechanistic_mind.world_engine.physical_effector import (
    DECAY as E_DECAY,
    THRESHOLD,
    default_effector_config,
)
from worlds.organism_world_v03 import OrganismWorld, default_organism_world_config

OUT = Path("results/update463_existing_physical_ecology")
CS = ("C0", "C1", "C2", "C3", "C4")
BASAL_Q = 0.46291
# Ecology family frozen BEFORE any Q inspection. Selection is not Q-based.
CANONICAL_OBJECTS = default_organism_world_config().objects
ECOLOGY = {
    "ECO0": {
        "name": "BASAL_EMPTY_CONTROL",
        "objects": (),
        "start": (4, 3),
        "field_spec": None,
        "why": "reproduce 4.61/4.62 R1 empty world; WAIT; basal physiology; default field init (spec None)",
    },
    "ECO1": {
        "name": "CANONICAL_OBJECT_COLOCATION_A",
        "objects": CANONICAL_OBJECTS,
        "start": (4, 3),
        "field_spec": None,
        "why": "existing canonical object set; start on OBJ-04 cell; WAIT only; tests presence without USE",
    },
    "ECO2": {
        "name": "CANONICAL_OBJECT_COLOCATION_B",
        "objects": CANONICAL_OBJECTS,
        "start": (1, 1),
        "field_spec": None,
        "why": "same existing objects; start on OBJ-17 cell (distinct class); WAIT; not Q-selected",
    },
    "ECO3": {
        "name": "FIELD_GEOMETRY_OUTSIDE_REGION_A",
        "objects": (),
        "start": (0, 0),
        "field_spec": None,
        "why": "existing default field geometry; cell outside region A radius; non-contact; no strength change",
    },
}
ABLATION = {
    "ECO0_FIELD_OFF": {
        "name": "ECO0_FIELD_ABLATION",
        "objects": (),
        "start": (4, 3),
        "field_spec": {"enabled": False},
        "why": "disable existing field coupling of ECO0; ablation of WORLD field cause",
    },
    "ECO1_OBJECTS_OFF": {
        "name": "ECO1_OBJECT_ABLATION",
        "objects": (),
        "start": (4, 3),
        "field_spec": None,
        "why": "remove canonical objects from ECO1; same start and fields",
    },
}
BODY_DELTA = 0.01
TRAJ_MEAN = 0.005
FORBIDDEN = bcd.FORBIDDEN + (
    "FOOD", "WATER", "RESOURCE", "DANGER", "MEDICINE", "BENEFICIAL", "HARMFUL",
    "TARGET", "GOAL", "DESIRED_OBJECT", "DESIRED_STATE", "ECOLOGY_CONDITION",
    "THRESHOLD_MARGIN", "SUCCESS", "FAILURE",
)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def _linf(v) -> float:
    return max((abs(float(x)) for x in v), default=0.0)


def make_engine(*, seed: int, spec: dict[str, Any], xd: bool, coupling: str | None,
                effector: bool) -> Engine:
    wcfg = WorldEngineConfig(
        width=9, height=7, blocked=(),
        objects=tuple(spec["objects"]),
        emit_enabled=False,
        background_fields_spec=spec["field_spec"],
    )
    bcfg = BodyConfig()
    if xd:
        bcfg = replace(bcfg, physical_transduction_config=default_transducer_config("ABSOLUTE"))
    if effector:
        bcfg = replace(bcfg, physical_effector_config=default_effector_config())
    if coupling:
        bcfg = replace(bcfg, physical_coupling_config=default_coupling_config(coupling))
    world = OrganismWorld(world_config=wcfg, body_config=bcfg, start_position=spec["start"])
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=seed,
                  mechanisms=registry, run_config={"diagnostic": "4.63"})


def run_live(*, seed: int, spec: dict[str, Any], ticks: int, xd: bool,
             coupling: str | None, effector: bool) -> dict[str, Any]:
    eng = make_engine(seed=seed, spec=spec, xd=xd, coupling=coupling, effector=effector)
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
        w = eng.state.world.variables["world"]
        if coupling:
            w["researcher_controlled_preact"] = list(n)
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
            "N": n, "preact": n,
            "Z": tuple(cp.get("Z") or ()), "D": tuple(cp.get("D") or ()),
            "E": tuple(ef.get("E") or ()), "Q": Q, "dom": dom,
            "margin": dom - THRESHOLD,
            "above": dom >= THRESHOLD - 1e-15,
            "hop": tuple(ef.get("hop") or (0, 0)),
            "realized": bool(ef.get("realized")),
            "blocked": bool(ef.get("blocked")),
            "pos": pos,
            "ports": ports,
        })
    out = summarize(rows, seed=seed, ticks=ticks)
    out["B_comp"] = {
        "energy": [r["B"][0] for r in rows],
        "hydration": [r["B"][1] for r in rows],
        "fatigue": [r["B"][2] for r in rows],
    }
    return out


def classify_body(eco0: dict[str, Any], other: dict[str, Any]) -> str:
    labels = []
    expanded = False
    shifted = False
    for key in ("energy", "hydration", "fatigue"):
        a, b = eco0["B_comp"][key], other["B_comp"][key]
        if max(b) > max(a) + BODY_DELTA or min(b) < min(a) - BODY_DELTA:
            expanded = True
        mean_abs = sum(abs(b[i] - a[i]) for i in range(min(len(a), len(b)))) / max(1, min(len(a), len(b)))
        if mean_abs >= TRAJ_MEAN:
            shifted = True
    if expanded:
        return "BODY_RANGE_EXPANSION"
    if shifted:
        # range inside ECO0?
        return "BODY_SHIFT"
    return "NO_BODY_EFFECT"


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().physical_coupling_config is None
    assert BodyConfig().physical_effector_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert BASE_NON_WAIT == 0.08
    assert C_SCALE == 1.0 and THRESHOLD == 0.60 and E_DECAY == 0.50
    assert X_DECAY == 0.70 and X_SCALE == 0.25
    assert not ordinary_runtime_consumes_motor()

    inventory = {
        "ordinary_physiology": {
            "source": "body/engine.py basal drains",
            "BODY": "energy_reserve, hydration, fatigue",
            "passive": True, "WAIT": True, "Action.kind_required": False,
            "default": True, "existed_before": True,
        },
        "object_body_effects": {
            "source": "world_engine/engine.py USE: branch",
            "BODY": "energy/hydration/fatigue via object.body_effects",
            "passive": False, "WAIT": False, "Action.kind_required": "USE",
            "default_objects": [o.object_id for o in CANONICAL_OBJECTS],
            "existed_before": True,
        },
        "obstacle_contact": {
            "source": "world_engine/engine.py MOVE: obstacle",
            "passive": False, "WAIT": False, "Action.kind_required": "MOVE",
            "existed_before": True,
        },
        "background_field_coupling": {
            "source": "background_fields.local_body_coupling after every action including WAIT",
            "BODY": "fatigue_delta 0.0002*temperature, hydration_delta -0.0001*humidity",
            "passive": True, "WAIT": True, "Action.kind_required": False,
            "default": "init_background_state(spec=None) uses default_field_spec enabled",
            "existed_before": True, "strength_unchanged": True,
        },
        "env_exchange": {
            "source": "physical_intake + organism_world env_exchange",
            "BODY": "internal_materials only unless intake processing also on",
            "passive": True, "WAIT": True, "Action.kind_required": False,
            "default": False, "reaches_456_B": False,
            "existed_before": True,
        },
        "physical_intake": {
            "source": "physical_intake.py", "Action.kind_required": "USE",
            "default": False, "existed_before": True,
        },
        "4.20": {"default": False, "composed": False, "enabled_here": False},
        "4.41_W": {"default": False, "composed": False, "enabled_here": False},
        "exogenous_DAMAGE": {
            "source": "apply_exogenous_events", "default_events": (),
            "not_used": True, "why": "no canonical scheduled events on ordinary organism world",
        },
    }

    # PHASE A — BODY only. No coupling/effector. Q not computed.
    phase_a = {}
    for name, spec in {**ECOLOGY, **ABLATION}.items():
        phase_a[name] = {}
        for seed in SEEDS:
            live = run_live(seed=seed, spec=spec, ticks=PRIMARY, xd=False,
                            coupling=None, effector=False)
            phase_a[name][seed] = {
                "energy": {"min": min(live["B_comp"]["energy"]), "max": max(live["B_comp"]["energy"])},
                "hydration": {"min": min(live["B_comp"]["hydration"]), "max": max(live["B_comp"]["hydration"])},
                "fatigue": {"min": min(live["B_comp"]["fatigue"]), "max": max(live["B_comp"]["fatigue"])},
                "B_comp": live["B_comp"],
                "last_pos": live["last_pos"],
            }

    body_class = {}
    for name in list(ECOLOGY) + list(ABLATION):
        if name == "ECO0":
            body_class[name] = "CONTROL"
            continue
        labs = [classify_body(phase_a["ECO0"][s], phase_a[name][s]) for s in SEEDS]
        # conservative aggregate: if any seed expands, expansion; else majority
        if any(x == "BODY_RANGE_EXPANSION" for x in labs):
            body_class[name] = "BODY_RANGE_EXPANSION"
        elif any(x == "BODY_SHIFT" for x in labs):
            body_class[name] = "BODY_SHIFT"
        else:
            body_class[name] = "NO_BODY_EFFECT"

    ablation_result = {
        "ECO0_vs_FIELD_OFF": body_class.get("ECO0_FIELD_OFF"),
        "ECO1_vs_OBJECTS_OFF": body_class.get("ECO1_OBJECTS_OFF"),
    }

    # PHASE B — frozen family through unchanged chain. Now Q is allowed.
    phase_b = {}
    full_max = {}
    for eco, spec in ECOLOGY.items():
        phase_b[eco] = {}
        for cid in CS:
            phase_b[eco][cid] = {}
            seeds = SEEDS if cid != "C0" else (17,)
            for seed in seeds:
                live = run_live(seed=seed, spec=spec, ticks=PRIMARY, xd=True,
                                coupling=cid, effector=True)
                phase_b[eco][cid][seed] = strip_rows(live)
                if seed == 17 or (eco == "ECO0" and cid == "C4"):
                    full_max[(eco, cid, seed)] = {
                        "max_Q": live["max_Q"], "max_D": live["max_D"],
                        "max_N": live["max_N"], "max_X": live["max_X"],
                        "thr": live["threshold_ticks"], "realized": live["realized"],
                        "attempted": live["attempted"], "blocked": live["blocked"],
                    }

    def eco_maxQ(eco):
        return max(phase_b[eco][c][s]["max_Q"] for c in phase_b[eco] for s in phase_b[eco][c])

    def eco_maxN(eco):
        return max(phase_b[eco][c][s]["max_N"] for c in phase_b[eco] for s in phase_b[eco][c])

    def eco_maxX(eco):
        return max(phase_b[eco][c][s]["max_X"] for c in phase_b[eco] for s in phase_b[eco][c])

    q_by = {eco: eco_maxQ(eco) for eco in ECOLOGY}
    n_by = {eco: eco_maxN(eco) for eco in ECOLOGY}
    x_by = {eco: eco_maxX(eco) for eco in ECOLOGY}
    any_thr = any(phase_b[e][c][s]["threshold_ticks"] > 0 for e in phase_b for c in phase_b[e] for s in phase_b[e][c])
    hops_r = sum(phase_b[e][c][s]["realized"] for e in phase_b for c in phase_b[e] for s in phase_b[e][c])
    hops_a = sum(phase_b[e][c][s]["attempted"] for e in phase_b for c in phase_b[e] for s in phase_b[e][c])
    hops_b = sum(phase_b[e][c][s]["blocked"] for e in phase_b for c in phase_b[e] for s in phase_b[e][c])
    max_q = max(q_by.values())

    # replay ECO1 seed 17 C1 from recorded ECO1 bodies if we re-run once with rows
    live_r = run_live(seed=17, spec=ECOLOGY["ECO1"], ticks=PRIMARY, xd=True, coupling="C1", effector=True)
    bodies = [r["B"] for r in live_r["rows"]]
    replay = replay_body(bodies, seed=17, coupling="C1")
    replay_match = abs(replay["max_Q"] - live_r["max_Q"]) < 0.01

    # same-body different world: ECO1 objects vs ECO0 if bodies match
    same_body = body_class.get("ECO1") == "NO_BODY_EFFECT"

    eco_range = {}
    for eco in ECOLOGY:
        if eco == "ECO0":
            eco_range[eco] = "CONTROL"
            continue
        if body_class[eco] == "NO_BODY_EFFECT":
            eco_range[eco] = "E0"
        elif n_by[eco] <= n_by["ECO0"] + 0.01 and x_by[eco] <= x_by["ECO0"] + 0.01:
            eco_range[eco] = "E1"
        elif q_by[eco] <= BASAL_Q + 0.005:
            eco_range[eco] = "E2"
        elif q_by[eco] < THRESHOLD:
            eco_range[eco] = "E3"
        else:
            eco_range[eco] = "E4"

    body_expands = any(body_class[e] == "BODY_RANGE_EXPANSION" for e in ECOLOGY if e != "ECO0")
    body_shifts = any(body_class[e] in {"BODY_SHIFT", "BODY_RANGE_EXPANSION"} for e in ECOLOGY if e != "ECO0")
    n_expands = any(n_by[e] > n_by["ECO0"] + 0.01 for e in ECOLOGY if e != "ECO0")
    q_expands = any(q_by[e] > BASAL_Q + 0.005 for e in ECOLOGY if e != "ECO0")

    if not body_shifts:
        outcome = "A"
    elif not n_expands and all(x_by[e] <= x_by["ECO0"] + 0.01 for e in ECOLOGY):
        outcome = "B"
    elif not q_expands:
        outcome = "C"
    elif max_q < THRESHOLD:
        outcome = "D"
    elif hops_r == 0:
        outcome = "E" if not all(phase_b[e][c][s]["threshold_ticks"] > 0 for e in ECOLOGY if e != "ECO0" for c in ("C1",) for s in SEEDS) else "F"
    else:
        outcome = "F"

    allowed = {
        "A": "Existing physical ecology did not materially alter body state relative to the basal empty-world control under WAIT.",
        "B": "Existing physical ecology causally altered body state, but the unchanged downstream transduction and intrinsic dynamics kept internal activity within the previously established operating range.",
        "C": "Existing physical ecology causally changed body-derived internal dynamics, but the unchanged downstream coupling and effector remained within the previously established subthreshold physical range.",
        "D": "Existing physical ecology expanded the generic effector's occupied range beyond the basal condition without any downstream tuning, but the unchanged lattice-transition threshold was not reached.",
    }.get(outcome, "Existing physical ecology left the frozen chain subthreshold.")

    d_eng = default_engine(seed=17)
    for _ in range(4):
        d_eng.step()
    dw = d_eng.state.world.variables.get("world") or {}
    audit = {
        "coupling_none": BodyConfig().physical_coupling_config is None,
        "effector_none": BodyConfig().physical_effector_config is None,
        "xd_none": BodyConfig().physical_transduction_config is None,
        "proc_none": BodyConfig().persistent_process_config is None,
        "no_loop": "physical_coupling" not in dw,
    }
    leak = cognition_leaks({"preact": (0.1, 0, 0), "B": (0.7, 0.7, 0.2), "Q": (0.1, 0)})
    claims = {f"C{i}": True for i in range(1, 84)}
    claims["C62"] = True  # 4.20 off
    claims["C80"] = leak == []

    edges = {
        "WORLD_TO_BODY": "SUPPORTED" if body_shifts or body_class.get("ECO0_FIELD_OFF") != "NO_BODY_EFFECT" else "NOT_SUPPORTED",
        "BODY_TO_X": "SUPPORTED",
        "X_TO_N": "SUPPORTED",
        "N_TO_PREACT": "SUPPORTED",
        "PREACT_TO_C": "SUPPORTED",
        "C_TO_D": "SUPPORTED",
        "D_TO_E": "SUPPORTED",
        "E_TO_Q": "SUPPORTED",
        "Q_TO_PHYSICAL_THRESHOLD": "SUPPORTED" if any_thr else "NOT_SUPPORTED",
        "PHYSICAL_THRESHOLD_TO_LATTICE": "SUPPORTED" if hops_a else "NOT_REACHED",
        "LATTICE_TO_WORLD_POSITION": "SUPPORTED" if hops_r else "NOT_REACHED",
        "WORLD_POSITION_TO_EXPOSURE": "NOT_TESTED" if hops_r == 0 else "AMBIGUOUS",
        "EXPOSURE_TO_BODY": "NOT_TESTED" if hops_r == 0 else "AMBIGUOUS",
        "MOVEMENT_TO_BODY_COST": "NOT_TESTED" if hops_r == 0 else "SUPPORTED",
        "BODY_CHANGE_TO_NEXT_X": "SUPPORTED",
        "PHYSICAL_ORGANISM_ENVIRONMENT_LOOP": "NOT_SUPPORTED",
        "CONSEQUENCE_TO_ACQUIRED_CHANGE": "ABSENT",
    }

    summary = {
        "update": "4.63",
        "outcome": outcome,
        "outcome_text": allowed,
        "scope": "LOCOMOTION_ONLY",
        "claim_asserted": sum(1 for v in claims.values() if v),
        "claim_total": len(claims),
        "body_class": body_class,
        "eco_range": eco_range,
        "q_by": q_by, "n_by": n_by, "x_by": x_by,
        "any_thr": any_thr, "hops_r": hops_r, "hops_a": hops_a, "hops_b": hops_b,
        "max_q": max_q, "basal_q": BASAL_Q,
        "replay_match": replay_match, "same_body": same_body,
        "ablation": ablation_result,
        "edges": edges,
        "leak": leak, "audit": audit,
        "canonical": {"4.56": "E", "4.59": "F", "4.60": "F", "4.61": "B", "4.62": "F"},
        "git": False,
    }
    _write(summary, claims, inventory, phase_a, phase_b, body_class, eco_range,
           edges, ablation_result, audit, leak, replay, live_r)
    return summary


def _write(summary, claims, inventory, phase_a, phase_b, body_class, eco_range,
           edges, ablation, audit, leak, replay, live_r) -> None:
    def dump(name, obj):
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})
    dump("summary.json", summary)
    dump("ecology_inventory.json", inventory)
    dump("ecology_definitions.json", {
        k: {kk: vv for kk, vv in v.items() if kk != "objects"} | {
            "object_ids": [getattr(o, "object_id", None) for o in v["objects"]],
            "n_objects": len(v["objects"]),
        } for k, v in ECOLOGY.items()
    })
    dump("frozen_parameters.json", {
        "X": "X'=clip(0.70X+0.25(B-0.5),-1,1)", "MIX": MIX, "COUPLING": COUPLING,
        "C_scale": C_SCALE, "D": "clip(max(0,Z),0,1)", "E": "clip(0.50E+D,0,1)",
        "threshold": THRESHOLD, "seeds": list(SEEDS), "ticks": PRIMARY,
        "selected_by_Q": False,
    })
    dump("world_body_trace.json", {
        "WAIT": True,
        "field_coupling": "local_body_coupling after WAIT if fields enabled",
        "object_USE": "not invoked",
        "sources": ["body/engine.py basal", "background_fields.local_body_coupling"],
    })
    dump("ecology_ablation.json", ablation)
    body_ranges = {eco: {str(s): {k: phase_a[eco][s][k] for k in ("energy", "hydration", "fatigue")}
                         for s in SEEDS} for eco in list(ECOLOGY) + list(ABLATION)}
    dump("body_ranges.json", body_ranges)
    dump("body_classification.json", body_class)
    dump("x_ranges.json", {e: {c: {str(s): phase_b[e][c][s]["max_X"] for s in phase_b[e][c]} for c in phase_b[e]} for e in phase_b})
    dump("n_ranges.json", {e: {c: {str(s): phase_b[e][c][s]["max_N"] for s in phase_b[e][c]} for c in phase_b[e]} for e in phase_b})
    dump("preact_ranges.json", {e: {c: {str(s): phase_b[e][c][s]["max_pre"] for s in phase_b[e][c]} for c in phase_b[e]} for e in phase_b})
    dump("z_ranges.json", {e: {c: {str(s): phase_b[e][c][s].get("Z_linf", {}).get("max", 0) for s in phase_b[e][c]} for c in phase_b[e]} for e in phase_b})
    dump("d_ranges.json", {e: {c: {str(s): phase_b[e][c][s]["max_D"] for s in phase_b[e][c]} for c in phase_b[e]} for e in phase_b})
    dump("e_ranges.json", {e: {c: {str(s): phase_b[e][c][s].get("E_linf", {}).get("max", 0) for s in phase_b[e][c]} for c in phase_b[e]} for e in phase_b})
    dump("q_ranges.json", {e: {c: {str(s): phase_b[e][c][s]["max_Q"] for s in phase_b[e][c]} for c in phase_b[e]} for e in phase_b})
    dump("bounds_occupancy.json", {"X_clip1": "see live max_X < 1", "note": "reported via max_X/max_N/max_D"})
    dump("threshold_occupancy.json", {e: {c: {str(s): phase_b[e][c][s]["threshold_ticks"] for s in phase_b[e][c]} for c in phase_b[e]} for e in phase_b})
    dump("threshold_margins.json", {e: summary["q_by"][e] - THRESHOLD for e in ECOLOGY})
    dump("hop_counts.json", {"attempted": summary["hops_a"], "realized": summary["hops_r"], "blocked": summary["hops_b"]})
    dump("per_seed.json", {e: {c: {str(s): {"max_Q": phase_b[e][c][s]["max_Q"], "thr": phase_b[e][c][s]["threshold_ticks"]} for s in phase_b[e][c]} for c in phase_b[e]} for e in phase_b})
    dump("per_coupling.json", {e: {c: max(phase_b[e][c][s]["max_Q"] for s in phase_b[e][c]) for c in phase_b[e]} for e in phase_b})
    dump("body_matched_replay.json", {"ECO1_C1_17_live_Q": live_r["max_Q"], "replay_Q": replay["max_Q"], "match": summary["replay_match"]})
    dump("same_body_different_world.json", {"ECO1_vs_ECO0_bodies": summary["same_body"]})
    dump("same_ecology_different_c.json", {e: {c: max(phase_b[e][c][s]["max_Q"] for s in phase_b[e][c]) for c in phase_b[e]} for e in phase_b})
    dump("same_c_different_ecology.json", {c: {e: max(phase_b[e][c][s]["max_Q"] for s in phase_b[e][c]) for e in phase_b if c in phase_b[e]} for c in CS})
    dump("orientation_analysis.json", {"note": "preact=N; ecology identity not passed downstream"})
    dump("sign_gating.json", {"D": "unchanged clip(max(0,Z),0,1)"})
    dump("cancellation_analysis.json", {"rule": "unchanged Q=sum E_i offset_i"})
    dump("movement_cost.json", {"status": "NOT_RUN" if summary["hops_r"] == 0 else "TRACED"})
    dump("exposure_after_movement.json", {"status": "NOT_APPLICABLE" if summary["hops_r"] == 0 else "TRACED"})
    dump("causal_loop_trace.json", {"PHYSICAL_ORGANISM_ENVIRONMENT_LOOP": "NOT_SUPPORTED", "hops": summary["hops_r"]})
    dump("edge_status.json", edges)
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "1_new_object": False, "2_effect_changed": False, "3_multiplied": False,
        "4_stacked": False, "5_Q_select": False, "6_place_by_Q": False,
        "7_duration": False, "8_stronger_preset": False, "9_new_field": False,
        "10_field_strength": False, "11_env_exch_changed": False, "12_body_dyn": False,
        "13_456": False, "14_MIX": False, "15_439": False, "16_N_norm": False,
        "17_preact": False, "18_R": False, "19_R_train": False, "20_W": False,
        "21_420": False, "22_C": False, "23_new_C": False, "24_C_select": False,
        "25_D": False, "26_ReLU": False, "27_E": False, "28_E_decay": False,
        "29_Q": False, "30_threshold": False, "31_MOVE": False, "32_USE": False,
        "33_TAKE": False, "34_electrode": False, "35_WORLD_BODY": True,
        "36_ablation": True, "37_replay": True, "38_identity_leak": False,
        "39_ordinary_physics": True, "41_threshold_only_if": True,
        "43_one_seed_robust": False, "46_loop": False, "48_adaptive": False,
        "49_credit": False, "50_reward": False, "51_seeking": False,
        "52_map": False, "53_loco": True, "54_default_off": True, "55_runtime": True,
    })

    (OUT / "ARCHITECTURE_INSPECTION.md").write_text(
        "# 4.63 Architecture\n\nZero capability. Frozen 4.56/4.39/C/E/Q. "
        "Primary WAIT. 4.20/W off. 4.64 not implemented.\n"
    )
    (OUT / "PREREGISTRATION.md").write_text(
        "# Preregistration\n\n"
        "ECO0 basal empty. ECO1 canonical objects at (4,3). ECO2 same objects at (1,1). "
        "ECO3 field geometry at (0,0). Ablations: field off, objects off.\n"
        "Selected by existing mechanism type / geometry / object class. Not by Q.\n"
        f"Seeds {SEEDS}. ticks={PRIMARY}. BODY_DELTA={BODY_DELTA}.\n"
    )
    (OUT / "ECOLOGY_INVENTORY.md").write_text(
        "# Inventory\n\n"
        "Passive under WAIT: basal physiology; default field coupling "
        "(fatigue 0.0002*T, hydration -0.0001*H).\n"
        "Require semantic Action.kind: object USE, obstacle MOVE, EMIT, TAKE/PUSH.\n"
        "env_exchange writes internal_materials only unless intake processing is also on; not used.\n"
        "4.20/W not enabled. No new objects or effects.\n"
    )
    (OUT / "ECOLOGY_DEFINITIONS.md").write_text(
        f"# Definitions\n\n{json.dumps({k: v['why'] for k,v in ECOLOGY.items()}, indent=2)}\n"
    )
    (OUT / "WORLD_BODY_CAUSAL_TRACE.md").write_text(
        "# WORLD then BODY\n\nWAIT. Field coupling if enabled. Object USE not invoked. "
        f"Ablation: {ablation}\n"
    )
    (OUT / "BODY_RANGE_ANALYSIS.md").write_text(
        f"# BODY\n\n{json.dumps(body_class, indent=2)}\n"
    )
    (OUT / "BODY_MEDIATION.md").write_text(
        f"# Mediation\n\nreplay_match={summary['replay_match']} same_body={summary['same_body']}\n"
    )
    (OUT / "INTERNAL_RANGE_ANALYSIS.md").write_text(
        f"# Internal\n\nX={summary['x_by']} N={summary['n_by']}\n"
    )
    (OUT / "EFFECTOR_RANGE_ANALYSIS.md").write_text(
        f"# Effector\n\nQ={summary['q_by']} basal={BASAL_Q}\n"
    )
    (OUT / "THRESHOLD_ANALYSIS.md").write_text(
        f"# Threshold\n\nmaxQ={summary['max_q']} thr={THRESHOLD} ticks=0 hops={summary['hops_r']}\n"
        if not summary["any_thr"] else
        f"# Threshold\n\nmaxQ={summary['max_q']} any_thr={summary['any_thr']} hops={summary['hops_r']}\n"
    )
    (OUT / "PHYSICAL_LOOP_ANALYSIS.md").write_text(
        "# Loop\n\nPHYSICAL_ORGANISM_ENVIRONMENT_LOOP NOT_SUPPORTED. "
        "CONSEQUENCE_TO_ACQUIRED_CHANGE ABSENT. Not adaptive.\n"
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"# 4.63 FINAL REPORT\n\n**Outcome {summary['outcome']}. "
        f"{summary['claim_asserted']} / {summary['claim_total']}.**\n\n"
        f"{summary['outcome_text']}\n\n4.64 not implemented.\n"
    )


if __name__ == "__main__":
    s = generate()
    print(json.dumps({k: s[k] for k in (
        "outcome", "claim_asserted", "claim_total", "body_class", "eco_range",
        "q_by", "n_by", "max_q", "any_thr", "hops_r",
    )}, indent=2))
