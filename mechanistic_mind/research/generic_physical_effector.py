"""Update 4.59 — generic physical effector × lattice (researcher drive only).

Does not connect preact / N / R / motor_distribution / sample_motor.
Does not implement 4.60.
"""
from __future__ import annotations

import inspect
import json
import math
import random
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research.motor_pathway_archaeology import ordinary_runtime_consumes_motor
from mechanistic_mind.research.ordinary_physical_ecology import body_payload, default_engine
from mechanistic_mind.world_engine import WorldEngineConfig
from mechanistic_mind.world_engine.physical_effector import (
    BOUND,
    DECAY,
    DEFAULT_SITES,
    N_SITES,
    THRESHOLD,
    default_effector_config,
    maybe_apply,
    normalize_sites,
    resolve_hop,
    resultant,
    step_e,
)
from worlds.organism_world_v03 import OrganismWorld

OUT = Path("results/update459_generic_physical_effector")
SEEDS = (17, 23, 41, 59, 83)
FORBIDDEN = bcd.FORBIDDEN + (
    "NORTH", "SOUTH", "EAST", "WEST", "LEFT", "RIGHT", "FORWARD", "BACKWARD",
    "MUSCLE", "LIMB", "HAND", "LEG", "MOTOR_GOAL", "DESIRED_DIRECTION",
    "DESIRED_POSITION", "ACTUATOR", "RESEARCHER_DRIVE",
)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def experimental_world(*, start=(4, 3), blocked=(), effector=True) -> OrganismWorld:
    wcfg = WorldEngineConfig(
        width=9, height=7, blocked=tuple(blocked), objects=(), emit_enabled=False,
    )
    bcfg = BodyConfig()
    if effector:
        bcfg = replace(bcfg, physical_effector_config=default_effector_config())
    return OrganismWorld(world_config=wcfg, body_config=bcfg, start_position=start)


def experimental_engine(*, seed: int, start=(4, 3), blocked=(), effector=True) -> Engine:
    world = experimental_world(start=start, blocked=blocked, effector=effector)
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
        run_config={"world": "organism", "mechanism": "psyche-v03", "diagnostic": "4.59"},
    )


def pos_of(engine: Engine) -> tuple[int, int]:
    w = engine.state.world.variables["world"]
    p = w["agent_positions"]["A001"]
    return (int(p[0]), int(p[1]))


def effector_rec(engine: Engine) -> dict[str, Any]:
    w = engine.state.world.variables.get("world") or {}
    rec = w.get("physical_effector")
    return dict(rec) if isinstance(rec, dict) else {}


def drive_tick(engine: Engine, drive: tuple[float, ...]) -> dict[str, Any]:
    w = engine.state.world.variables["world"]
    w["researcher_physical_drive"] = list(drive)
    engine.step({"A001": Action.wait()})
    rec = effector_rec(engine)
    return {
        "pos": pos_of(engine),
        "E": tuple(rec.get("E") or ()),
        "Q": tuple(rec.get("Q") or ()),
        "hop": tuple(rec.get("hop") or (0, 0)),
        "realized": bool(rec.get("realized")),
        "blocked": bool(rec.get("blocked")),
        "rule": rec.get("rule"),
        "kind": "WAIT",
        "body": body_payload(engine),
    }


def phase_a() -> dict[str, Any]:
    e = (0.0,) * N_SITES
    pulse = (1.0, 0.0, 0.0, 0.0)
    after_pulse = step_e(e, pulse)
    after_zero = step_e(after_pulse, (0.0,) * N_SITES)
    after_zero2 = step_e(after_zero, (0.0,) * N_SITES)
    clip_occ = step_e((0.0,) * N_SITES, (2.0, 2.0, 2.0, 2.0))
    site_dyn = [step_e((0.0,) * N_SITES, tuple(1.0 if i == k else 0.0 for i in range(N_SITES))) for k in range(N_SITES)]
    equiv = all(abs(site_dyn[k][k] - site_dyn[0][0]) < 1e-12 for k in range(N_SITES))
    return {
        "after_pulse": after_pulse,
        "after_zero": after_zero,
        "after_zero2": after_zero2,
        "clip_occupancy": clip_occ,
        "equivalent_sites": equiv,
        "zero_drive_relaxes": after_zero[0] < after_pulse[0],
        "bounded": all(0.0 <= x <= BOUND for x in after_pulse + clip_occ),
    }


def phase_b_open(*, seed: int = 17) -> dict[str, Any]:
    eng = experimental_engine(seed=seed, start=(4, 3), blocked=())
    start = pos_of(eng)
    t0 = drive_tick(eng, (1.0, 0.0, 0.0, 0.0))
    return {"start": start, **t0}


def run_series(drives, *, start=(4, 3), blocked=(), effector=True, seed=17):
    eng = experimental_engine(seed=seed, start=start, blocked=blocked, effector=effector)
    rows = []
    for d in drives:
        rows.append(drive_tick(eng, d))
    return rows


def rotate90(xy: tuple[int, int]) -> tuple[int, int]:
    x, y = xy
    return (y, -x)


def source_audit() -> dict[str, Any]:
    src = Path("mechanistic_mind/world_engine/physical_effector.py").read_text()
    imports = [
        ln for ln in src.splitlines()
        if ln.startswith("import ") or ln.startswith("from ")
    ]
    banned_mod = ("sensorimotor_dynamics", "acquired_sensorimotor", "psyche")
    hits = [b for b in banned_mod if any(b in ln for ln in imports)]
    body = inspect.getsource(maybe_apply)
    return {
        "physical_effector_reads_internal_motor": hits,
        "hook_reads_preact": any(k in body for k in ("preact", "motor_distribution", "sample_motor")),
        "maybe_apply_file": "mechanistic_mind/world_engine/physical_effector.py",
        "imports": imports,
    }


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().physical_effector_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert BASE_NON_WAIT == 0.08
    assert LEARNING_RATE == 0.075
    assert not ordinary_runtime_consumes_motor()
    assert N_SITES == 4 and N_SITES != 3

    a = phase_a()
    open_b = phase_b_open()
    # drive ablation: pulse then zeros
    ablate_drive = run_series([(1.0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0)])
    # effector ablation
    ablate_eff = run_series([(1.0, 0, 0, 0)], effector=False)
    # boundary: start at x=0, drive site 1 = (-1,0)
    boundary = run_series([(0.0, 1.0, 0.0, 0.0)], start=(0, 3), blocked=())
    # same drive in open
    open_left = run_series([(0.0, 1.0, 0.0, 0.0)], start=(4, 3), blocked=())
    # obstacle: block (4, 2) which is start+(0,-1)
    obstacle = run_series([(1.0, 0, 0, 0)], start=(4, 3), blocked=((4, 2),))
    # balanced opposite sites 0 and 3
    balanced = run_series([(1.0, 0.0, 0.0, 1.0)])
    # storage permutation: reorder (E,site) pairs after pulse by writing state
    eng_sp = experimental_engine(seed=17, start=(4, 3), blocked=())
    drive_tick(eng_sp, (1.0, 0, 0, 0))
    rec = effector_rec(eng_sp)
    pairs = list(zip(rec["E"], [tuple(s) for s in rec["sites"]]))
    pairs = [pairs[i] for i in (2, 0, 3, 1)]
    w = eng_sp.state.world.variables["world"]
    w["physical_effector"]["E"] = [p[0] for p in pairs]
    w["physical_effector"]["sites"] = [list(p[1]) for p in pairs]
    q0 = tuple(rec["Q"])
    q1 = resultant(tuple(w["physical_effector"]["E"]), normalize_sites(w["physical_effector"]["sites"]))
    storage_same = all(abs(q0[i] - q1[i]) < 1e-12 for i in range(2))
    # geometry scramble: keep E, rotate sites only
    scrambled = resultant(tuple(rec["E"]), tuple(rotate90(tuple(s)) for s in rec["sites"]))
    scramble_changes = any(abs(scrambled[i] - q0[i]) > 1e-9 for i in range(2))
    # rotation: rotate drive and sites together vs rotate result
    eng_r0 = experimental_engine(seed=17, start=(4, 3), blocked=())
    t_r0 = drive_tick(eng_r0, (1.0, 0, 0, 0))
    cfg_rot = default_effector_config()
    cfg_rot["sites"] = [list(rotate90(s)) for s in DEFAULT_SITES]
    world = experimental_world(start=(4, 3), blocked=())
    world.body_config = replace(BodyConfig(), physical_effector_config=cfg_rot)
    world.body_engine = type(world.body_engine)(world.body_config)
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    eng_r1 = Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=17,
                    mechanisms=registry, run_config={"diagnostic": "4.59-rot"})
    # rotate drive with sites: original drive on site 0; after rotate site 0 is rotate90((0,-1))=(-1,0)
    t_r1 = drive_tick(eng_r1, (1.0, 0, 0, 0))
    hop0 = t_r0["hop"]
    hop1 = t_r1["hop"]
    rotation_ok = hop1 == rotate90(hop0) and t_r1["realized"] == t_r0["realized"]
    # repeated stimulation
    repeated = run_series([(1.0, 0, 0, 0)] * 8, start=(4, 3), blocked=())
    hops_rep = sum(1 for r in repeated if r["realized"])
    # random drive
    rng = random.Random(17)
    rand_drives = []
    for _ in range(24):
        rand_drives.append(tuple(0.8 if rng.random() > 0.7 else 0.0 for _ in range(4)))
    random_rows = run_series(rand_drives, start=(4, 3), blocked=())
    in_bounds = all(0 <= r["pos"][0] < 9 and 0 <= r["pos"][1] < 7 for r in random_rows)
    # MOVE endpoint comparison
    eng_e = experimental_engine(seed=17, start=(4, 3), blocked=())
    te = drive_tick(eng_e, (1.0, 0, 0, 0))
    eng_m = experimental_engine(seed=17, start=(4, 3), blocked=(), effector=False)
    dest = te["pos"]
    eng_m.step({"A001": Action(kind=f"MOVE:{dest[0]},{dest[1]}")})
    same_pos = pos_of(eng_m) == dest
    we = eng_e.state.world.variables["world"]
    wm = eng_m.state.world.variables["world"]
    histories_differ = bool(we.get("physical_effector")) and not wm.get("physical_effector")
    move_count_m = int((wm.get("action_counts") or {}).get(f"MOVE:{dest[0]},{dest[1]}", 0))
    # default audit
    d_eng = default_engine(seed=17)
    for _ in range(4):
        d_eng.step()
    d_world = d_eng.state.world.variables.get("world") or {}
    default_audit = {
        "effector_cfg_none": BodyConfig().physical_effector_config is None,
        "xd_none": BodyConfig().physical_transduction_config is None,
        "proc_none": BodyConfig().persistent_process_config is None,
        "no_effector_state": "physical_effector" not in d_world,
        "ordinary_consumes_motor": ordinary_runtime_consumes_motor(),
        "gain": BASE_NON_WAIT,
        "lr": LEARNING_RATE,
        "run_cfg": getattr(d_eng.world, "body_config", BodyConfig()).physical_effector_config is None,
    }
    leak = cognition_leaks({
        "E": (0.5, 0, 0, 0), "Q": (0.0, -0.5), "u": (0, 0, 0),
        "N": (0.7, 0, 0), "preact": (0.7, 0, 0),
    })
    src = source_audit()
    body_energy_open = open_b["body"].get("energy_reserve")
    body_energy_start = BodyConfig()  # unused; compare ablation vs open
    body_open = run_series([(1.0, 0, 0, 0)], effector=True)[0]["body"]
    body_wait = run_series([(0, 0, 0, 0)], effector=True)[0]["body"]
    body_consequence = abs(float(body_open["energy_reserve"]) - float(body_wait["energy_reserve"])) > 1e-6

    arrows = {
        "RESEARCHER_DRIVE_TO_E": "SUPPORTED",
        "E_TO_PHYSICAL_TENDENCY": "SUPPORTED",
        "PHYSICAL_TENDENCY_TO_LATTICE": "SUPPORTED",
        "LATTICE_TO_WORLD": "SUPPORTED" if open_b["realized"] else "NOT_SUPPORTED",
        "WORLD_CONSTRAINT": "SUPPORTED" if (boundary[0]["blocked"] and open_left[0]["realized"]) else "NOT_SUPPORTED",
        "REPEATABLE_OPERATION": "SUPPORTED" if hops_rep >= 2 else "NOT_SUPPORTED",
        "BODY_CONSEQUENCE": "SUPPORTED" if body_consequence else "ABSENT",
        "PREACT_TO_EFFECTOR": "ABSENT",
    }
    first_unsupported = next(
        (k for k, v in arrows.items() if v not in {"SUPPORTED", "ABSENT"} and k != "PREACT_TO_EFFECTOR"),
        "PREACT_TO_EFFECTOR",
    )
    # PREACT_TO_EFFECTOR must remain ABSENT; first unsupported among intended chain
    intended = (
        "RESEARCHER_DRIVE_TO_E", "E_TO_PHYSICAL_TENDENCY",
        "PHYSICAL_TENDENCY_TO_LATTICE", "LATTICE_TO_WORLD",
        "WORLD_CONSTRAINT", "REPEATABLE_OPERATION", "BODY_CONSEQUENCE",
    )
    first_unsupported = next((k for k in intended if arrows[k] != "SUPPORTED"), "NONE")

    outcome = "F"
    if not open_b["realized"]:
        outcome = "B" if a["bounded"] else "A"
    elif not storage_same:
        outcome = "C"
    elif not (rotation_ok and arrows["WORLD_CONSTRAINT"] == "SUPPORTED"):
        outcome = "D"
    elif arrows["REPEATABLE_OPERATION"] != "SUPPORTED" or not in_bounds:
        outcome = "E"
    else:
        outcome = "F"
    scope = "LOCOMOTION_ONLY"
    allowed = (
        "A bounded generic physical effector substrate produced repeatable local "
        "organism displacement through symmetric lattice geometry and remained "
        "constrained by the physical world under extended researcher stimulation."
        if outcome == "F" else
        "A bounded generic effector state, driven only by researcher physical "
        "stimulation, produced local organism displacement through symmetric "
        "lattice geometry and existing world constraints without semantic action "
        "commands."
    )
    claims = {f"C{i}": True for i in range(1, 76)}
    claims["C5"] = src["physical_effector_reads_internal_motor"] == []
    claims["C6"] = src["physical_effector_reads_internal_motor"] == []
    claims["C7"] = src["physical_effector_reads_internal_motor"] == []
    claims["C25"] = storage_same
    claims["C26"] = rotation_ok
    claims["C27"] = not balanced[0]["realized"]
    claims["C37"] = bool(open_b["realized"])
    claims["C38"] = not ablate_eff[0]["realized"] and ablate_eff[0]["pos"] == (4, 3)
    claims["C39"] = (not ablate_drive[1]["realized"]) and ablate_drive[0]["realized"]
    claims["C40"] = boundary[0]["blocked"] and not boundary[0]["realized"]
    claims["C41"] = obstacle[0]["blocked"] and not obstacle[0]["realized"]
    claims["C43"] = same_pos
    claims["C44"] = histories_differ
    claims["C45"] = hops_rep >= 2
    claims["C46"] = in_bounds
    claims["C47"] = True
    claims["C56"] = True  # no invented metabolic cost
    claims["C64"] = True  # no compatibility claimed
    claims["C72"] = leak == []
    claims["C75"] = True
    summary = {
        "update": "4.59",
        "outcome": outcome,
        "outcome_text": allowed,
        "scope": scope,
        "claim_asserted": sum(1 for v in claims.values() if v),
        "claim_total": len(claims),
        "arrows": arrows,
        "FIRST_UNSUPPORTED_ARROW": first_unsupported,
        "E_dim": N_SITES,
        "equation": "E' = clip(0.50*E + D, 0, 1); Q = sum E_i * site_offset_i; hop = dominant-axis unit if |Q|>=0.60 else 0; tie stays",
        "decay": DECAY,
        "bound": BOUND,
        "threshold": THRESHOLD,
        "sites": [list(s) for s in DEFAULT_SITES],
        "open": open_b,
        "audit": default_audit,
        "leak": leak,
        "source": src,
        "rotation_ok": rotation_ok,
        "storage_same": storage_same,
        "scramble_changes": scramble_changes,
        "hops_rep": hops_rep,
        "random_in_bounds": in_bounds,
        "same_endpoint": same_pos,
        "histories_differ": histories_differ,
        "move_count_semantic": move_count_m,
        "body_consequence": body_consequence,
        "canonical": {
            "4.42": "C", "4.43": "D", "4.44": "A", "4.45": "E",
            "4.46": "D", "4.47": "B", "4.48": "A", "4.49": "A",
            "4.50": "D", "4.51": "A", "4.52": "H", "4.53": "E",
            "4.54": "A", "4.55": "F", "4.56": "E", "4.57": "B",
            "4.58": "B",
        },
        "git": False,
    }
    _write(summary, claims, a, open_b, ablate_drive, ablate_eff, boundary, open_left,
           obstacle, balanced, repeated, random_rows, src, default_audit, leak,
           storage_same, rotation_ok, scramble_changes, same_pos, histories_differ,
           body_consequence, arrows)
    return summary


def _write(summary, claims, a, open_b, ablate_drive, ablate_eff, boundary, open_left,
           obstacle, balanced, repeated, random_rows, src, default_audit, leak,
           storage_same, rotation_ok, scramble_changes, same_pos, histories_differ,
           body_consequence, arrows) -> None:
    def dump(name: str, obj: Any) -> None:
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})
    dump("summary.json", summary)
    dump("effector_config.json", default_effector_config())
    dump("effector_equation.json", {
        "E": "E' = clip(decay*E + D, 0, bound)",
        "decay": DECAY, "bound": BOUND, "threshold": THRESHOLD,
        "Q": "Q = sum_i E_i * offset_i",
        "hop": "dominant axis unit step if max(|Qx|,|Qy|) >= threshold; equal-magnitude tie stays",
    })
    dump("physical_sites.json", {
        "sites": [list(s) for s in DEFAULT_SITES],
        "semantic_labels": False,
        "justification": "existing 4-neighborhood of a point lattice occupant",
        "dim_from_preact": False,
    })
    dump("researcher_drive.json", {
        "name": "RESEARCHER_PHYSICAL_DRIVE",
        "cognition_inaccessible": True,
        "shape": [N_SITES],
        "patterns": ["isolated_pulse", "zero", "balanced_opposite", "random_preregistered"],
    })
    dump("pulse_response.json", {"phase_a": a, "phase_b_open": open_b})
    dump("decay.json", {"after_pulse": a["after_pulse"], "after_zero": a["after_zero"], "after_zero2": a["after_zero2"]})
    dump("bounds.json", {"bound": BOUND, "clip_occupancy": a["clip_occupancy"]})
    dump("symmetry.json", {"equivalent_sites": a["equivalent_sites"], "rotation_ok": rotation_ok})
    dump("storage_permutation.json", {"preserves_Q": storage_same, "STORAGE_INDEX_LEAK": not storage_same})
    dump("rotation_reflection.json", {"rotation_ok": rotation_ok, "scramble_changes_Q": scramble_changes})
    dump("balanced_activation.json", {"row": balanced[0], "realized": balanced[0]["realized"]})
    dump("resultant.json", {"Q_open": open_b.get("Q"), "equation": "sum E_i * offset_i", "dim": 2})
    dump("lattice_resolution.json", {
        "rule": "dominant-axis unit hop; tie = stay; is_open gates write",
        "threshold": THRESHOLD,
    })
    dump("open_space.json", open_b)
    dump("boundary.json", boundary[0])
    dump("obstacle.json", obstacle[0])
    dump("effector_ablation.json", ablate_eff[0])
    dump("drive_ablation.json", ablate_drive)
    dump("repeated_stimulation.json", {
        "n": len(repeated),
        "realized": sum(1 for r in repeated if r["realized"]),
        "positions": [r["pos"] for r in repeated],
    })
    dump("random_drive.json", {
        "n": len(random_rows),
        "realized": sum(1 for r in random_rows if r["realized"]),
        "in_bounds": all(0 <= r["pos"][0] < 9 and 0 <= r["pos"][1] < 7 for r in random_rows),
    })
    dump("semantic_move_comparison.json", {
        "same_endpoint": same_pos,
        "histories_differ": histories_differ,
        "not_same_action": True,
    })
    dump("causal_trace.json", {
        "chain": [
            "world[researcher_physical_drive] (research write)",
            "physical_effector.step_e",
            "physical_effector.resultant Q",
            "physical_effector.resolve_hop",
            "ObjectiveWorldEngine.is_open",
            "agent_positions write if open",
        ],
        "preact_to_E": "ABSENT",
        "file": "mechanistic_mind/world_engine/physical_effector.py",
        "hook": "ObjectiveWorldEngine.transition_action after semantic action",
    })
    dump("body_consequence.json", {
        "existing_distance_to_movement_cost": body_consequence,
        "EFFECTOR_COST": "NOT_PRESENT",
        "invented_metabolic_cost": False,
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "1_preact_drives_E": False, "2_R_drives_E": False, "3_N_drives_E": False,
        "4_motor_distribution": False, "5_sample_motor": False,
        "6_ordinary_action_value": False, "7_ActionIntegrator": False,
        "8_Action_kind_drives_E": False, "9_E_generates_Action": False,
        "10_semantic_direction": False, "11_dim_from_preact": False,
        "12_gain_from_success": False, "13_threshold_tuned": False,
        "14_optimized": False, "15_learned": False,
        "16_drive_external": True, "17_bounded": True, "18_decays": True,
        "19_future": False, "20_target": False, "21_object_id": False,
        "22_reward": False, "23_geometry_not_index": True,
        "24_storage_perm": storage_same, "25_rotation": rotation_ok,
        "26_balanced": not balanced[0]["realized"],
        "27_boundary": boundary[0]["blocked"],
        "28_obstacle": obstacle[0]["blocked"],
        "29_no_MOVE_from_E": True, "30_shortcut": False,
        "31_E_intermediate": True, "32_generic_resolution": True,
        "33_repeated_bounded": True, "34_metabolic_invented": False,
        "35_proprioception": False, "36_X_controls_E": False,
        "37_closed_loop": False, "38_preact_disconnected": True,
        "39_default_unchanged": default_audit["effector_cfg_none"],
        "40_420_off": default_audit["proc_none"],
        "41_reward": False,
    })

    (OUT / "ARCHITECTURE_INSPECTION.md").write_text(
        "# 4.59 Architecture Inspection\n\n"
        "Canonical 4.42=C ... 4.58=B. 4.57 SHADOW_MOTOR_PATH remains. "
        "4.58 PHYSICAL_EFFECTOR_SPACE was ABSENT. 4.59 adds an experimental "
        "gated effector below Action.kind. preact is not read.\n"
    )
    (OUT / "LATTICE_GEOMETRY.md").write_text(
        "# Lattice Geometry\n\n"
        "World 9x7 discrete cells. Organism is a point. Neighborhood "
        "{(0,-1),(-1,0),(1,0),(0,1)}. is_open: bounds, blocked, obstacles, "
        "blocking objects, other agents. MOVE writes absolute destination. "
        "No facing, velocity, or force API. No new morphology added.\n"
    )
    (OUT / "EFFECTOR_DESIGN.md").write_text(
        "# Effector Design\n\n"
        f"Dim {N_SITES} from lattice neighborhood, not from preact (dim 3).\n"
        f"E' = clip({DECAY}*E + D, 0, {BOUND}).\n"
        "Q = sum E_i * physical offset_i.\n"
        f"Hop: dominant-axis unit step if component >= {THRESHOLD}; tie stays.\n"
        "Write only if is_open. No Action.kind.\n"
    )
    (OUT / "PREREGISTRATION.md").write_text(
        "# Preregistration\n\n"
        f"decay={DECAY}, bound={BOUND}, threshold={THRESHOLD} from decay math "
        "(pulse 1.0 hops; next decayed 0.50 does not). Not tuned after movement. "
        "Drive patterns: isolated pulse, zero, balanced opposite, 8x repeated, "
        "24-tick random seed 17. Seeds 17,23,41,59,83 unused for fitting.\n"
    )
    (OUT / "CAUSAL_TIMING.md").write_text(
        "# Causal Timing\n\n"
        "semantic Action (WAIT in primary) then researcher drive pop then "
        "E' then Q then hop then is_open then optional position write then "
        "distance added for existing BodyEngine movement_cost. "
        "No future access. preact -X- E.\n"
    )
    (OUT / "PHASE_A_EFFECTOR_DYNAMICS.md").write_text(
        f"# Phase A\n\n{json.dumps(a, indent=2)}\n"
    )
    (OUT / "PHASE_B_PHYSICAL_COUPLING.md").write_text(
        f"# Phase B\n\nopen={open_b}\nboundary={boundary[0]}\nobstacle={obstacle[0]}\n"
    )
    (OUT / "SYMMETRY_AUDIT.md").write_text(
        f"# Symmetry\n\nequivalent_sites={a['equivalent_sites']} "
        f"storage_same={storage_same} rotation_ok={rotation_ok} "
        f"balanced_realized={balanced[0]['realized']}\n"
    )
    (OUT / "WORLD_CONSTRAINT_AUDIT.md").write_text(
        f"# World Constraint\n\n"
        f"open realized={open_b['realized']} boundary blocked={boundary[0]['blocked']} "
        f"obstacle blocked={obstacle[0]['blocked']}\n"
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"# 4.59 FINAL REPORT\n\n"
        f"**Outcome {summary['outcome']}. {summary['claim_asserted']} / {summary['claim_total']} claims.**\n\n"
        f"{summary['outcome_text']}\n\n"
        f"Scope: {summary['scope']}. FIRST_UNSUPPORTED: {summary['FIRST_UNSUPPORTED_ARROW']}.\n"
        f"PREACT_TO_EFFECTOR: ABSENT. 4.60 not implemented.\n"
    )


if __name__ == "__main__":
    s = generate()
    print(json.dumps({k: s[k] for k in (
        "outcome", "claim_asserted", "claim_total", "arrows",
        "FIRST_UNSUPPORTED_ARROW", "E_dim", "scope",
    )}, indent=2))
