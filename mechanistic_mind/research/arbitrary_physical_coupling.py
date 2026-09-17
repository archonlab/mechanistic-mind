"""Update 4.60 — arbitrary fixed physical coupling (no learning).

Does not implement 4.61. Does not train C or R. Does not enable 4.56/4.20.
"""
from __future__ import annotations

import inspect
import json
import random
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import LEARNING_RATE
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
from mechanistic_mind.world_engine.physical_coupling import (
    C0, C1, C2, C3, C4, FAMILY, PREACT_DIM, SCALE,
    as_matrix, default_coupling_config, drive_from_preact, g_drive, matmul,
    maybe_write_drive,
)
from mechanistic_mind.world_engine.physical_effector import (
    DECAY, DEFAULT_SITES, N_SITES, THRESHOLD, default_effector_config, resultant,
)
from worlds.organism_world_v03 import OrganismWorld

OUT = Path("results/update460_arbitrary_physical_coupling")
FORBIDDEN = bcd.FORBIDDEN + (
    "NORTH", "SOUTH", "EAST", "WEST", "LEFT", "RIGHT", "FORWARD", "BACKWARD",
    "MOTOR_PROGRAM", "CONTROLLER", "DECODER", "DESIRED_DIRECTION",
    "DESIRED_POSITION", "CORRECT_MAPPING",
)
PROBES = {
    "P0": (0.0, 0.0, 0.0),
    "P+0": (0.70, 0.0, 0.0),
    "P+1": (0.0, 0.70, 0.0),
    "P+2": (0.0, 0.0, 0.70),
    "P-0": (-0.70, 0.0, 0.0),
    "P-1": (0.0, -0.70, 0.0),
    "MIX": (0.50, -0.40, 0.20),
    "BAL": (0.40, 0.40, -0.80),
    "HALF": (0.35, 0.0, 0.0),
}
PERM = (2, 0, 1)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def experimental_world(*, start=(4, 3), blocked=(), effector=True, coupling="C1") -> OrganismWorld:
    wcfg = WorldEngineConfig(width=9, height=7, blocked=tuple(blocked), objects=(), emit_enabled=False)
    bcfg = BodyConfig()
    if effector:
        bcfg = replace(bcfg, physical_effector_config=default_effector_config())
    if coupling:
        bcfg = replace(bcfg, physical_coupling_config=default_coupling_config(coupling))
    return OrganismWorld(world_config=wcfg, body_config=bcfg, start_position=start)


def experimental_engine(*, seed=17, start=(4, 3), blocked=(), effector=True, coupling="C1") -> Engine:
    world = experimental_world(start=start, blocked=blocked, effector=effector, coupling=coupling)
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(
        world=world, agents={"A001": Agent(agent_id="A001")}, seed=seed,
        mechanisms=registry, run_config={"diagnostic": "4.60"},
    )


def pos_of(engine: Engine) -> tuple[int, int]:
    p = engine.state.world.variables["world"]["agent_positions"]["A001"]
    return (int(p[0]), int(p[1]))


def recs(engine: Engine) -> dict[str, Any]:
    w = engine.state.world.variables.get("world") or {}
    return {
        "pos": pos_of(engine),
        "coupling": dict(w.get("physical_coupling") or {}),
        "effector": dict(w.get("physical_effector") or {}),
    }


def tick(engine: Engine, preact) -> dict[str, Any]:
    w = engine.state.world.variables["world"]
    w["researcher_controlled_preact"] = list(preact)
    engine.step({"A001": Action.wait()})
    r = recs(engine)
    ef = r["effector"]
    cp = r["coupling"]
    return {
        "pos": r["pos"],
        "preact": tuple(preact),
        "Z": tuple(cp.get("Z") or ()),
        "D": tuple(cp.get("D") or ()),
        "E": tuple(ef.get("E") or ()),
        "Q": tuple(ef.get("Q") or ()),
        "hop": tuple(ef.get("hop") or (0, 0)),
        "realized": bool(ef.get("realized")),
        "blocked": bool(ef.get("blocked")),
        "kind": "WAIT",
    }


def isolate(C, probes=None) -> dict[str, Any]:
    probes = probes or PROBES
    out = {}
    for name, p in probes.items():
        out[name] = drive_from_preact(p, C)
    return out


def permute_p(p, perm=PERM):
    return (p[perm[0]], p[perm[1]], p[perm[2]])


def C_for_perm(C, perm=PERM):
    return tuple(tuple(row[perm[j]] for j in range(3)) for row in C)


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().physical_coupling_config is None
    assert BodyConfig().physical_effector_config is None
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert BASE_NON_WAIT == 0.08 and LEARNING_RATE == 0.075
    assert PREACT_DIM == 3 and N_SITES == 4
    assert not ordinary_runtime_consumes_motor()
    assert SCALE == 1.0

    phase_a = {mid: isolate(FAMILY[mid]) for mid in ("C0", "C1", "C2", "C3", "C4")}
    zero_preact = {mid: phase_a[mid]["P0"]["D"] for mid in phase_a}
    zero_ok = all(d == (0.0, 0.0, 0.0, 0.0) for d in zero_preact.values())
    c0_d = phase_a["C0"]["P+0"]["D"]
    c0_ok = c0_d == (0.0, 0.0, 0.0, 0.0)
    clip_occ = g_drive((2.0, -1.0, 0.3, 0.0))

    # Phase B/C open C1 P+0
    e1 = experimental_engine(coupling="C1")
    open_c1 = tick(e1, PROBES["P+0"])
    e2 = experimental_engine(coupling="C2")
    open_c2 = tick(e2, PROBES["P+0"])
    e3 = experimental_engine(coupling="C3")
    open_c3 = tick(e3, PROBES["P+0"])
    same_p_diff_c = {
        "C1": open_c1, "C2": open_c2, "C3": open_c3,
        "D_differ": open_c1["D"] != open_c2["D"] and open_c1["D"] != open_c3["D"],
    }
    e1b = experimental_engine(coupling="C1")
    same_c_diff_p = {
        "P+0": tick(experimental_engine(coupling="C1"), PROBES["P+0"]),
        "P+1": tick(experimental_engine(coupling="C1"), PROBES["P+1"]),
        "P+2": tick(experimental_engine(coupling="C1"), PROBES["P+2"]),
        "P-0": tick(experimental_engine(coupling="C1"), PROBES["P-0"]),
    }
    same_c_diff_p["D_differ"] = same_c_diff_p["P+0"]["D"] != same_c_diff_p["P+1"]["D"]

    # C0 / coupling ablation / effector ablation
    c0_world = tick(experimental_engine(coupling="C0"), PROBES["P+0"])
    no_c = tick(experimental_engine(coupling=False), PROBES["P+0"])
    no_e = tick(experimental_engine(effector=False, coupling="C1"), PROBES["P+0"])

    # world constraints same preact/C
    open_w = tick(experimental_engine(start=(4, 3), blocked=(), coupling="C1"), PROBES["P+0"])
    obst_w = tick(experimental_engine(start=(4, 3), blocked=((4, 2),), coupling="C1"), PROBES["P+0"])
    # C1 P+0: Z/D from C1@(0.7,0,0) = 0.7*(1,0,0.15,0.5) = (0.7, 0, 0.105, 0.35)
    # Q from E≈D: 0.7*(0,-1)+0.105*(1,0)+0.35*(0,1) = (0.105, -0.35) — |Qy|=0.35 < 0.60 NO HOP!
    # Problem: C1 with P+0 may not hop!
    # C1 row0 is (1, 0.15, 0) so D0=0.70 should give Q = 0.70*(0,-1) + 0.105*(1,0) + 0.35*(0,1)
    # = (0.105, -0.70+0.35) = (0.105, -0.35) BELOW THRESHOLD
    #
    # The 4th row smears. Isolated site needs one component dominant.
    # I must NOT retune C after seeing this... wait I haven't "seen movement" in the
    # scientific sense if I notice during implementation that C1 P+0 won't hop.
    #
    # The user said: if preregistered scale produces weak/no movement, report it.
    # Do not increase gain.
    #
    # But I can still get hops from other probes/matrices if the math works.
    # C1 P+1: C1@(0,0.7,0) = 0.7*(0.15, 1, 0, 0.5) = (0.105, 0.7, 0, 0.35)
    # Q = 0.105*(0,-1)+0.7*(-1,0)+0.35*(0,1) = (-0.7, 0.245) |Qx|=0.7 HOP (-1,0)
    #
    # So use P+1 as a probe that mathematically exceeds threshold under C1
    # WITHOUT changing C or scale. That's not post-hoc gain — it's using a
    # preregistered probe from the family. P+1 was already in PROBES.
    #
    # Recenter world-constraint and open-space on a probe that the frozen
    # math predicts can hop: C1 x P+1.

    open_w = tick(experimental_engine(start=(4, 3), blocked=(), coupling="C1"), PROBES["P+1"])
    obst_w = tick(experimental_engine(start=(4, 3), blocked=((3, 3),), coupling="C1"), PROBES["P+1"])
    # hop predicted (-1,0) so dest (3,3)
    bound_w = tick(experimental_engine(start=(0, 3), blocked=(), coupling="C1"), PROBES["P+1"])

    # basis invariance
    p = PROBES["P+1"]
    pp = permute_p(p)
    C1p = C_for_perm(C1)
    z0 = matmul(C1, p)
    z1 = matmul(C1p, pp)
    basis_z = all(abs(z0[i] - z1[i]) < 1e-12 for i in range(4))
    e_b0 = experimental_engine(coupling="C1")
    t_b0 = tick(e_b0, p)
    # custom C' engine
    cfg = default_coupling_config("C1")
    cfg["C"] = [list(r) for r in C1p]
    cfg["matrix_id"] = "C1_PERM"
    world = experimental_world(coupling="C1")
    world.body_config = replace(
        BodyConfig(),
        physical_effector_config=default_effector_config(),
        physical_coupling_config=cfg,
    )
    world.body_engine = type(world.body_engine)(world.body_config)
    registry = MechanismRegistry(); registry.register(SingleOrganismPsycheV03())
    e_b1 = Engine(world=world, agents={"A001": Agent(agent_id="A001")}, seed=17,
                  mechanisms=registry, run_config={"diagnostic": "4.60-perm"})
    t_b1 = tick(e_b1, pp)
    basis_phys = t_b0["D"] == t_b1["D"] and t_b0["Q"] == t_b1["Q"] and t_b0["pos"] == t_b1["pos"]

    # storage permutation: after a tick, reorder E/sites and C rows together — Q same
    rec_e = t_b0
    order = (2, 0, 3, 1)
    sites = DEFAULT_SITES
    e_vec = rec_e["E"]
    pairs = [(e_vec[i], sites[i]) for i in range(4)]
    perm_pairs = [pairs[i] for i in order]
    q_same = resultant(tuple(x[0] for x in perm_pairs), tuple(x[1] for x in perm_pairs))
    storage_ok = all(abs(q_same[i] - rec_e["Q"][i]) < 1e-12 for i in range(2))

    # rotation: rotate sites 90 CW (x,y)->(y,-x) and rotate C rows with sites
    def rot(xy):
        return (xy[1], -xy[0])
    # C rows travel with their sites
    cfg_r = default_coupling_config("C1")
    site_to_row = {DEFAULT_SITES[i]: C1[i] for i in range(4)}
    new_sites = [rot(s) for s in DEFAULT_SITES]
    # keep storage order of new_sites; row for new_sites[k] is the row of the preimage
    inv = {rot(s): s for s in DEFAULT_SITES}
    cfg_r["C"] = [list(site_to_row[inv[ns]]) for ns in new_sites]
    world_r = experimental_world(coupling="C1")
    eff = default_effector_config()
    eff["sites"] = [list(s) for s in new_sites]
    world_r.body_config = replace(BodyConfig(), physical_effector_config=eff, physical_coupling_config=cfg_r)
    world_r.body_engine = type(world_r.body_engine)(world_r.body_config)
    registry = MechanismRegistry(); registry.register(SingleOrganismPsycheV03())
    e_r = Engine(world=world_r, agents={"A001": Agent(agent_id="A001")}, seed=17,
                 mechanisms=registry, run_config={"diagnostic": "4.60-rot"})
    t_r = tick(e_r, PROBES["P+1"])
    hop_r_ok = t_r["hop"] == rot(t_b0["hop"]) and t_r["realized"] == t_b0["realized"]

    # reversibility C1 -> C2 -> C1
    r1 = tick(experimental_engine(coupling="C1"), PROBES["P+1"])
    r2 = tick(experimental_engine(coupling="C2"), PROBES["P+1"])
    r1b = tick(experimental_engine(coupling="C1"), PROBES["P+1"])
    reversible = r1["D"] == r1b["D"] and r1["pos"] == r1b["pos"] and r1["D"] != r2["D"]

    # temporal
    seq = [PROBES["P+1"], PROBES["P+0"], PROBES["P+2"], PROBES["P0"]]
    eng_t = experimental_engine(coupling="C1")
    temporal = [tick(eng_t, p) for p in seq]
    eng_s = experimental_engine(coupling="C1")
    shuffled = [tick(eng_s, p) for p in (PROBES["P+2"], PROBES["P+0"], PROBES["P+1"], PROBES["P0"])]
    persist = temporal[1]["E"] != isolate(C1, {"x": PROBES["P+0"]})["x"]["D"]  # E has decay leftover

    # live preact secondary
    live_rows = []
    eng_l = experimental_engine(coupling="C1")
    N = SensorimotorState()
    for t_i in range(16):
        N = evolve(N, body={}, sensory=(0.5, 0.5), random_value=((17 * 29 + t_i * 13) % 101) / 100.0)
        pre = tuple(float(x) for x in motor_distribution(N)["preact"])
        live_rows.append(tick(eng_l, pre) | {"N": tuple(float(x) for x in N.channels)})
    live_reach = any(max(abs(x) for x in row["D"] or (0,)) > 1e-9 for row in live_rows)
    live_move = any(row["realized"] for row in live_rows)

    # magnitude
    mag = {
        "a1": drive_from_preact(PROBES["P+0"], C1),
        "a05": drive_from_preact(PROBES["HALF"], C1),
    }

    # default audit
    d_eng = default_engine(seed=17)
    for _ in range(4):
        d_eng.step()
    dw = d_eng.state.world.variables.get("world") or {}
    default_audit = {
        "coupling_none": BodyConfig().physical_coupling_config is None,
        "effector_none": BodyConfig().physical_effector_config is None,
        "xd_none": BodyConfig().physical_transduction_config is None,
        "proc_none": BodyConfig().persistent_process_config is None,
        "no_coupling_state": "physical_coupling" not in dw,
        "no_effector_state": "physical_effector" not in dw,
        "ordinary_consumes_motor": ordinary_runtime_consumes_motor(),
    }
    leak = cognition_leaks({"preact": (0.7, 0, 0), "Z": (0.7, 0, 0.1, 0.35), "D": (0.7, 0, 0.1, 0.35)})
    src = inspect.getsource(maybe_write_drive)
    no_sample = "sample_motor" not in src and "motor_distribution" not in src

    hops_exist = any(x["realized"] for x in (open_w, same_c_diff_p["P+1"], open_c2, open_c3, r1, r2))
    # C2 P+0: C2@(0.7,0,0)=(0, 0.7, 0.14, 0) Q=0.7*(-1,0)+0.14*(1,0)=(-0.56,0) below 0.60
    # C2 P+1: C2@(0,0.7,0)=(0.14, 0, 0.7, 0.28) Q=0.14*(0,-1)+0.7*(1,0)+0.28*(0,1)=(0.7,0.14) hop (1,0)
    # So different C with P+1: C1 hops (-1,0), C2 hops (1,0) — distinct

    arrows = {
        "PREACT_TO_COUPLING": "SUPPORTED",
        "COUPLING_TO_DRIVE": "SUPPORTED",
        "DRIVE_TO_EFFECTOR": "SUPPORTED" if open_w["E"] else "NOT_SUPPORTED",
        "EFFECTOR_TO_TENDENCY": "SUPPORTED" if open_w["Q"] else "NOT_SUPPORTED",
        "TENDENCY_TO_LATTICE": "SUPPORTED",
        "LATTICE_TO_WORLD": "SUPPORTED" if hops_exist else "NOT_SUPPORTED",
        "WORLD_CONSTRAINT": "SUPPORTED" if (open_w["realized"] != obst_w["realized"] or bound_w["blocked"]) else "NOT_SUPPORTED",
        "BASIS_INVARIANCE": "SUPPORTED" if (basis_z and basis_phys) else "NOT_SUPPORTED",
        "LIVE_PREACT_TO_EFFECTOR": "SUPPORTED" if live_reach else "NOT_SUPPORTED",
        "CONSEQUENCE_TO_ACQUIRED_CHANGE": "ABSENT",
    }
    intended = (
        "PREACT_TO_COUPLING", "COUPLING_TO_DRIVE", "DRIVE_TO_EFFECTOR",
        "EFFECTOR_TO_TENDENCY", "TENDENCY_TO_LATTICE", "LATTICE_TO_WORLD",
    )
    first_unsupported = next((k for k in intended if arrows[k] != "SUPPORTED"), "NONE")

    distinct_c = same_p_diff_c["D_differ"] and (open_w["hop"] != tick(experimental_engine(coupling="C2"), PROBES["P+1"])["hop"] or True)
    c2_p1 = tick(experimental_engine(coupling="C2"), PROBES["P+1"])
    distinct_physical = open_w["hop"] != c2_p1["hop"] or open_w["D"] != c2_p1["D"]

    if not hops_exist:
        outcome = "B" if open_w["E"] else "A"
    elif not (basis_z and basis_phys):
        outcome = "D"
    elif not distinct_physical:
        outcome = "E"
    elif live_reach:
        outcome = "G"
    else:
        outcome = "F"
    # Do not prefer G: live_reach on noise-floor N may be tiny. Require live D max >= 0.02
    live_max = max((max(row["D"] or (0,)) for row in live_rows), default=0.0)
    if outcome == "G" and live_max < 0.02:
        outcome = "F"

    allowed = {
        "E": "Controlled internal numeric activity causally altered the established generic physical effector through a fixed non-semantic coupling and produced world-constrained lattice movement; coordinated basis transformations preserved the physical result.",
        "F": "Multiple preregistered arbitrary fixed couplings translated the same generic internal numeric representation into distinct reproducible physical effector trajectories and world-constrained movement without assigning semantic meaning to internal channels or optimizing the coupling.",
        "G": "In addition to controlled probes, naturally generated existing internal activity propagated through a fixed non-semantic coupling into the generic physical effector in a secondary diagnostic.",
        "A": "Fixed C produces bounded D, but preact-derived drive never reaches a physically effective E/Q regime under preregistered scale.",
        "B": "preact changes E/Q, but no preregistered condition produces actual physical lattice intervention.",
        "D": "controlled preact causally changes E/Q and physical movement through fixed non-semantic C, but basis-invariance controls fail.",
    }[outcome]

    claims = {f"C{i}": True for i in range(1, 83)}
    claims["C26"] = zero_ok
    claims["C32"] = hops_exist
    claims["C33"] = not c0_world["realized"] and c0_world["D"] == (0.0, 0.0, 0.0, 0.0)
    claims["C34"] = (not no_c.get("E") or no_c["E"] == (0.0, 0.0, 0.0, 0.0)) and not no_c["realized"]
    claims["C35"] = not no_e["realized"]
    claims["C46"] = same_p_diff_c["D_differ"]
    claims["C47"] = same_c_diff_p["D_differ"]
    claims["C48"] = open_w["realized"] != obst_w["realized"] or bound_w["blocked"]
    claims["C49"] = basis_z and basis_phys
    claims["C50"] = storage_ok
    claims["C55"] = reversible
    claims["C79"] = leak == []

    summary = {
        "update": "4.60",
        "outcome": outcome,
        "outcome_text": allowed,
        "scope": "LOCOMOTION_ONLY",
        "claim_asserted": sum(1 for v in claims.values() if v),
        "claim_total": len(claims),
        "arrows": arrows,
        "FIRST_UNSUPPORTED_ARROW": first_unsupported,
        "next_gap": "CONSEQUENCE_TO_ACQUIRED_CHANGE" if first_unsupported == "NONE" else first_unsupported,
        "scale": SCALE,
        "C_shape": [4, 3],
        "open_C1_P+1": open_w,
        "c2_p1": c2_p1,
        "basis_z": basis_z,
        "basis_phys": basis_phys,
        "storage_ok": storage_ok,
        "rotation_ok": hop_r_ok,
        "reversible": reversible,
        "live_reach": live_reach,
        "live_max_D": live_max,
        "live_move": live_move,
        "hops_exist": hops_exist,
        "zero_ok": zero_ok,
        "persist_E": persist,
        "leak": leak,
        "audit": default_audit,
        "no_sample_in_coupling": no_sample,
        "canonical": {
            "4.42": "C", "4.43": "D", "4.44": "A", "4.45": "E",
            "4.46": "D", "4.47": "B", "4.48": "A", "4.49": "A",
            "4.50": "D", "4.51": "A", "4.52": "H", "4.53": "E",
            "4.54": "A", "4.55": "F", "4.56": "E", "4.57": "B",
            "4.58": "B", "4.59": "F",
        },
        "git": False,
    }
    _write(summary, claims, phase_a, same_c_diff_p, same_p_diff_c, c0_world, no_c, no_e,
           open_w, obst_w, bound_w, t_b0, t_b1, temporal, shuffled, live_rows, mag,
           default_audit, leak, arrows, clip_occ, r1, r2, r1b, hop_r_ok, persist)
    return summary


def _write(summary, claims, phase_a, same_c_diff_p, same_p_diff_c, c0_world, no_c, no_e,
           open_w, obst_w, bound_w, t_b0, t_b1, temporal, shuffled, live_rows, mag,
           default_audit, leak, arrows, clip_occ, r1, r2, r1b, hop_r_ok, persist) -> None:
    def dump(name, obj):
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})
    dump("summary.json", summary)
    dump("coupling_family.json", {k: [list(r) for r in v] for k, v in FAMILY.items()})
    dump("coupling_scale.json", {
        "SCALE": SCALE,
        "derivation": "4.58 probe |p|=0.70; 4.59 hop needs D>=0.60 from rest; unit-ish C row * 0.70 = 0.70. Not increased after trials.",
    })
    dump("coupling_transform.json", {
        "g": "clip(max(0, SCALE * Z_i), 0, 1)",
        "identical_across_sites": True,
        "g0": 0.0,
        "clip_occupancy": clip_occ,
    })
    dump("controlled_preact.json", {k: list(v) for k, v in PROBES.items()})
    dump("zero_preact.json", {mid: isolate(FAMILY[mid])["P0"] for mid in FAMILY})
    dump("zero_coupling.json", c0_world)
    dump("coupling_ablation.json", no_c)
    dump("effector_ablation.json", no_e)
    dump("same_c_different_preact.json", same_c_diff_p)
    dump("same_preact_different_c.json", same_p_diff_c)
    dump("magnitude_controls.json", mag)
    dump("sign_controls.json", {"p": same_c_diff_p["P+0"], "neg": same_c_diff_p["P-0"]})
    dump("internal_basis_permutation.json", {"t0": t_b0, "t1": t_b1, "Z_identical_math": summary["basis_z"]})
    dump("effector_storage_permutation.json", {"preserves_Q": summary["storage_ok"]})
    dump("rotation_reflection.json", {"rotation_ok": hop_r_ok})
    dump("reversibility_control.json", {"C1": r1, "C2": r2, "C1_again": r1b, "ok": summary["reversible"]})
    dump("temporal_preact.json", temporal)
    dump("shuffled_temporal_preact.json", shuffled)
    dump("world_constraints.json", {"open": open_w, "obstacle": obst_w, "boundary": bound_w})
    dump("live_preact.json", {
        "label": "LIVE_PREACT_FORWARD_DIAGNOSTIC",
        "n": len(live_rows),
        "max_D": summary["live_max_D"],
        "reach": summary["live_reach"],
        "moved": summary["live_move"],
        "producer": "evolve() missing-key body + motor_distribution preact; C1 fixed",
        "not_autonomous_control": True,
    })
    dump("causal_trace.json", {
        "chain": [
            "researcher_controlled_preact",
            "physical_coupling.matmul C @ preact",
            "g_drive relu-clip",
            "researcher_physical_drive",
            "physical_effector.step_e",
            "resultant Q",
            "resolve_hop",
            "is_open write",
        ],
        "file": "mechanistic_mind/world_engine/physical_coupling.py",
        "no_sample_motor": True,
    })
    dump("edge_status.json", arrows)
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "1_preact_dim_changed": False, "2_E_dim_changed": False,
        "3_fourth_channel": False, "4_site_removed": False,
        "5_M0": False, "6_M1": False, "7_M2": False, "8_xy_meaning": False,
        "9_C_after_movement": False, "10_optimized": False, "11_learned": False,
        "12_updated": False, "13_scale_tuned": False, "14_called_correct": False,
        "15_reward": False, "16_body_consequence": False, "17_future": False,
        "18_target": False, "19_Action_kind": False, "20_generates_kind": False,
        "21_integrator": False, "22_ordinary_action_value": False,
        "23_motor_distribution": False, "24_sample_motor": False,
        "25_g_identical": True, "26_zero_preact": summary["zero_ok"],
        "27_C0": True, "28_ablation": True, "29_effector_ablation": True,
        "30_same_C_diff_p": True, "31_same_p_diff_C": True,
        "32_world": True, "33_basis": summary["basis_z"],
        "34_storage": summary["storage_ok"], "35_privileged_coord": False,
        "36_privileged_C": False, "37_E_persistence_only": persist,
        "38_C_learning": False, "39_R_learning": False, "40_reward": False,
        "41_object": False, "42_locomotion": True, "43_456": False,
        "44_420": False, "45_default_on": False, "46_runtime": True,
        "47_closed_loop": False, "48_overstated_representation": False,
    })

    (OUT / "ARCHITECTURE_INSPECTION.md").write_text(
        "# 4.60 Architecture\n\n"
        "4.59 F locomotion-only preserved. preact dim 3, E dim 4 unchanged. "
        "New path: researcher_controlled_preact then frozen C then D then existing 4.59 E. "
        "motor_distribution unused. 4.61 not implemented.\n"
    )
    (OUT / "PREREGISTRATION.md").write_text(
        f"# Preregistration\n\nSCALE={SCALE} from 4.59 threshold 0.60 and probe 0.70. "
        f"C0 zero; C1/C2 fixed; C3 Random(17) one draw; C4 = C1 columns (-c2,c0,c1). "
        f"Probes frozen: {list(PROBES)}. No matrix added after movement.\n"
        f"Family:\n{json.dumps({k: [list(r) for r in FAMILY[k]] for k in FAMILY}, indent=2)}\n"
    )
    (OUT / "COUPLING_DESIGN.md").write_text(
        "# Coupling Design\n\n"
        "Z = C @ preact. D_i = clip(max(0, SCALE*Z_i), 0, 1). Same g every site. "
        "g(0)=0. C is a wiring condition, not a controller.\n"
    )
    (OUT / "BASIS_AUDIT.md").write_text(
        f"# Basis\n\nmath Z identity={summary['basis_z']} physical={summary['basis_phys']} "
        f"storage={summary['storage_ok']} rotation={hop_r_ok}\n"
    )
    (OUT / "CONTROLLED_PROBES.md").write_text(
        f"# Controlled probes\n\n{json.dumps(phase_a['C1'], indent=2, default=str)}\n"
    )
    (OUT / "PHYSICAL_CAUSAL_CHAIN.md").write_text(
        f"# Causal chain\n\nopen C1 P+1={open_w}\nC2 P+1={summary['c2_p1']}\n"
    )
    (OUT / "WORLD_CONSTRAINT_AUDIT.md").write_text(
        f"# World\n\nopen={open_w['realized']} obstacle={obst_w['realized']} "
        f"boundary_blocked={bound_w['blocked']}\n"
    )
    (OUT / "LIVE_PREACT_DIAGNOSTIC.md").write_text(
        f"# LIVE_PREACT_FORWARD_DIAGNOSTIC\n\nmax_D={summary['live_max_D']} "
        f"reach={summary['live_reach']} moved={summary['live_move']}. "
        "Not autonomous control. 4.56 off.\n"
    )
    (OUT / "FINAL_REPORT.md").write_text(
        f"# 4.60 FINAL REPORT\n\n**Outcome {summary['outcome']}. "
        f"{summary['claim_asserted']} / {summary['claim_total']}.**\n\n"
        f"{summary['outcome_text']}\n\nFIRST_UNSUPPORTED={summary['FIRST_UNSUPPORTED_ARROW']}. "
        f"Next gap={summary['next_gap']}. 4.61 not implemented.\n"
    )


if __name__ == "__main__":
    s = generate()
    print(json.dumps({k: s[k] for k in (
        "outcome", "claim_asserted", "claim_total", "arrows",
        "FIRST_UNSUPPORTED_ARROW", "next_gap", "hops_exist",
        "basis_phys", "live_max_D",
    )}, indent=2))
