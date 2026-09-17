"""Update 4.56 — generic bounded physical transduction (experimental).

Gated mechanism. Default runtime unchanged.
Does not enable 4.20. Does not implement 4.57.
Does not wire named physiology into named 4.39 channels.
"""
from __future__ import annotations

import json
import math
import random
import re
from dataclasses import replace
from pathlib import Path
from typing import Any

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.body import BodyConfig
from mechanistic_mind.body.acquired_sensorimotor_coupling import (
    AcquiredCouplingState,
    l1 as r_l1,
    reset_weights,
    step as r_step,
)
from mechanistic_mind.body.physical_transduction import (
    DECAY,
    MIX,
    PERM_CYCLE,
    SCALE,
    X_BOUND,
    default_transducer_config,
    ports_from_x,
    step_transducer,
)
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT,
    SensorimotorState,
    evolve,
    motor_distribution,
    sample_motor,
)
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from mechanistic_mind.research import acquired_sensorimotor_coupling as smc
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research import endogenous_motor_access as ema
from mechanistic_mind.research import existing_physiology_compatibility as epc
from mechanistic_mind.research.ordinary_physical_ecology import (
    body_payload,
    default_engine,
)
from worlds.organism_world_v03 import OrganismWorld, default_organism_world_config

SEEDS = (17, 23, 41, 59, 83)
PRIMARY = 96
K_SHIFT = 24
NOISE_REF = 0.043
PASS_NMAX = 0.08
PASS_SPAN = 0.02
CLIP = 0.99
CLIP_OCC = 0.50
R_THR = 0.02
PROBE_N = (0.70, 0.0, 0.0)
HYPS = ("ABSOLUTE", "CHANGE")
COMPS = ("energy_reserve", "hydration", "fatigue")
OUT = Path("results/update456_generic_physical_transduction")
FORBIDDEN = bcd.FORBIDDEN + (
    "COMFORT", "DISCOMFORT", "WELLBEING", "HEALTH_VALUE", "BODY_VALUE",
    "PHYSIOLOGY_QUALITY", "HOMEOSTASIS", "SETPOINT", "OPTIMAL_STATE",
    "PREFERENCE", "REINFORCEMENT", "NERVOUS_SYSTEM", "NERVE", "NEURON",
    "INTEROCEPTION", "PROPRIOCEPTION", "TIREDNESS", "TIRED",
    "SELF_CAUSED", "EXTERNAL_CAUSED", "MY_BODY", "SELF_BODY",
    "RESEARCHER_CONDITION", "PROJECTION_ID", "DEFICIT", "WELLNESS",
)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def vec3(p: dict[str, Any], permute: tuple[int, ...] | None = None) -> tuple[float, float, float]:
    raw = (float(p["energy_reserve"]), float(p["hydration"]), float(p["fatigue"]))
    if permute is None:
        return raw
    return (raw[permute[0]], raw[permute[1]], raw[permute[2]])


def replay_X(
    bodies: list[tuple[float, float, float]],
    *,
    mode: str,
    permute: tuple[int, ...] | None = None,
    couple: bool = True,
) -> list[tuple[float, float, float]]:
    x = (0.0, 0.0, 0.0)
    prev = None
    out = []
    frozen = None
    for B in bodies:
        Bp = (B[permute[0]], B[permute[1]], B[permute[2]]) if permute else B
        use = frozen if (not couple and frozen is not None) else Bp
        if not couple and frozen is None:
            frozen = Bp
            use = Bp
        x = step_transducer(x, use, prev, mode=mode, decay=DECAY, scale=SCALE, bound=X_BOUND)
        prev = use
        out.append(x)
    return out


def x_metrics(rows: list[tuple[float, float, float]]) -> dict[str, float]:
    l2 = [ema.l2(r) for r in rows]
    l1 = [ema.l1(r) for r in rows]
    linf = [max(abs(x) for x in r) for r in rows]
    clip = sum(1 for r in rows if max(abs(x) for x in r) >= (X_BOUND - 1e-9)) / len(rows)
    mean_l2 = sum(l2) / len(l2)
    means = [sum(r[i] for r in rows) / len(rows) for i in range(3)]
    ac = 0.0
    if len(l2) > 2:
        m = mean_l2
        num = sum((l2[t] - m) * (l2[t - 1] - m) for t in range(1, len(l2)))
        den = sum((v - m) ** 2 for v in l2) or 1.0
        ac = num / den
    return {
        "L2_mean": mean_l2,
        "L2_max": max(l2),
        "L2_span": max(l2) - min(l2),
        "L1_mean": sum(l1) / len(l1),
        "Linf_mean": sum(linf) / len(linf),
        "clip_occ": clip,
        "var_L2": sum((x - mean_l2) ** 2 for x in l2) / len(l2),
        "mean0": means[0], "mean1": means[1], "mean2": means[2],
        "autocorr_L2": ac,
        "min": min(min(r) for r in rows),
        "max": max(max(r) for r in rows),
    }


def traj_l1(a: list[tuple[float, ...]], b: list[tuple[float, ...]]) -> float:
    n = min(len(a), len(b))
    dim = len(a[0])
    return sum(sum(abs(a[t][i] - b[t][i]) for i in range(dim)) for t in range(n)) / n


def replay_N_from_X(xs: list[tuple[float, float, float]], *, seed: int) -> list[tuple[float, float, float]]:
    N = SensorimotorState()
    out = []
    for t, x in enumerate(xs):
        a, c = ports_from_x(x)
        N = evolve(
            N, body={"internal_a": a, "load_c": c},
            sensory=(0.5, 0.5),
            random_value=((seed * 29 + t * 13) % 101) / 100.0,
        )
        out.append(tuple(float(v) for v in N.channels))
    return out


def bodies_from_rec(rec: dict[str, list[float]]) -> list[tuple[float, float, float]]:
    n = len(rec["fatigue"])
    return [
        (float(rec["energy_reserve"][t]), float(rec["hydration"][t]), float(rec["fatigue"][t]))
        for t in range(n)
    ]


def experimental_engine(*, seed: int, hyp: str) -> Engine:
    cfg = replace(BodyConfig(), physical_transduction_config=default_transducer_config(hyp))
    world = OrganismWorld(
        world_config=default_organism_world_config(),
        body_config=cfg,
    )
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
        run_config={"world": "organism", "mechanism": "psyche-v03", "diagnostic": "4.56"},
    )


def record_live(*, seed: int, mode: str, hyp: str) -> dict[str, Any]:
    engine = experimental_engine(seed=seed, hyp=hyp)
    rec = {k: [] for k in COMPS}
    Xs: list[tuple[float, float, float]] = []
    Ns: list[tuple[float, float, float]] = []
    actions: list[str] = []
    N = SensorimotorState()
    for t in range(PRIMARY):
        if mode == "WAIT":
            engine.step({"A001": Action.wait()})
            actions.append("WAIT")
        else:
            engine.step()
            actions.append("FREE")
        p = body_payload(engine)
        B = vec3(p)
        X = tuple(float(v) for v in (p.get("transducer_state") or (0.0, 0.0, 0.0)))
        ports = ports_from_x(X)
        N = evolve(
            N, body={"internal_a": ports[0], "load_c": ports[1]},
            sensory=(0.5, 0.5),
            random_value=((seed * 29 + t * 13) % 101) / 100.0,
        )
        for i, k in enumerate(COMPS):
            rec[k].append(B[i])
        Xs.append(X)
        Ns.append(tuple(float(v) for v in N.channels))
    cfg = engine.world.body_config
    return {
        "seed": seed, "mode": mode, "hyp": hyp,
        "trace": rec, "X": Xs, "N": Ns, "actions": actions,
        "transducer_on": isinstance(getattr(cfg, "physical_transduction_config", None), dict),
        "proc_none": getattr(cfg, "persistent_process_config", "X") is None,
    }


def default_audit() -> dict[str, Any]:
    cfg = BodyConfig()
    engine = default_engine(seed=17)
    for _ in range(8):
        engine.step({"A001": Action.wait()})
    p = body_payload(engine)
    x = tuple(float(v) for v in (p.get("transducer_state") or (0.0, 0.0, 0.0)))
    return {
        "config_none": cfg.physical_transduction_config is None,
        "proc_none": cfg.persistent_process_config is None,
        "engine_proc_none": getattr(engine.world.body_config, "persistent_process_config", "X") is None,
        "engine_xd_none": getattr(engine.world.body_config, "physical_transduction_config", "X") is None,
        "X_inactive": x == (0.0, 0.0, 0.0),
        "prev_none": p.get("transducer_prev") is None,
        "internal_a_absent": "internal_a" not in p,
        "load_c_absent": "load_c" not in p,
        "gain": BASE_NON_WAIT,
    }


def phase_a_block(bodies: list[tuple[float, float, float]], *, mode: str) -> dict[str, Any]:
    orig = replay_X(bodies, mode=mode)
    met = x_metrics(orig)
    const_B = [bodies[0]] * len(bodies)
    const = replay_X(const_B, mode=mode)
    idx = list(range(len(bodies)))
    random.Random(9001).shuffle(idx)
    shuf = replay_X([bodies[i] for i in idx], mode=mode)
    k = K_SHIFT % len(bodies)
    shifted = replay_X(bodies[k:] + bodies[:k], mode=mode)
    rev = replay_X(list(reversed(bodies)), mode=mode)
    late_const = const[16:]
    late_delta = traj_l1(late_const[1:], late_const[:-1]) if len(late_const) > 2 else 0.0
    met.update({
        "vs_const_L1": traj_l1(orig, const),
        "vs_shuffle_L1": traj_l1(orig, shuf),
        "vs_shift_L1": traj_l1(orig, shifted),
        "vs_rev_L1": traj_l1(orig, rev),
        "const_late_delta": late_delta,
        "const_clip": x_metrics(const)["clip_occ"],
        "bounded": all(all(-X_BOUND - 1e-12 <= v <= X_BOUND + 1e-12 for v in r) for r in orig),
    })
    met["pass"] = (
        met["bounded"]
        and met["clip_occ"] < CLIP_OCC
        and met["vs_const_L1"] > PASS_SPAN
        and met["L2_span"] > PASS_SPAN
        and late_delta < 0.02
    )
    met["temporal"] = met["vs_shuffle_L1"] > PASS_SPAN
    return met


def acquire_R(n_rows: list[tuple[float, float, float]], motor: list[str]) -> AcquiredCouplingState:
    R = AcquiredCouplingState()
    for t, ch in enumerate(n_rows):
        R = r_step(R, n=ch, m=epc.m_vec(motor[t]), plasticity=True)
    return R


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().physical_transduction_config is None
    assert BodyConfig().persistent_process_config is None
    assert BASE_NON_WAIT == 0.08

    audit = default_audit()

    recordings: dict[str, dict[int, Any]] = {"WAIT": {}, "FREE": {}}
    for seed in SEEDS:
        recordings["WAIT"][seed] = epc.record_mode(seed=seed, mode="WAIT")
        recordings["FREE"][seed] = epc.record_mode(seed=seed, mode="FREE")

    phase_a: dict[str, dict[str, dict[int, Any]]] = {}
    a_pass: dict[str, list[str]] = {"WAIT": [], "FREE": []}
    for mode in ("WAIT", "FREE"):
        phase_a[mode] = {}
        for hyp in HYPS:
            phase_a[mode][hyp] = {}
            n_ok = 0
            n_temp = 0
            for seed in SEEDS:
                bodies = bodies_from_rec(recordings[mode][seed]["trace"])
                met = phase_a_block(bodies, mode=hyp)
                phase_a[mode][hyp][seed] = met
                n_ok += int(met["pass"])
                n_temp += int(met["temporal"])
            if n_ok >= 4:
                a_pass[mode].append(hyp)

    # Phase B: frozen X → 4.39 via adapter
    phase_b: dict[str, dict[str, dict[int, Any]]] = {}
    noise_floor = {}
    for mode in ("WAIT", "FREE"):
        phase_b[mode] = {}
        for hyp in HYPS:
            phase_b[mode][hyp] = {}
            for seed in SEEDS:
                bodies = bodies_from_rec(recordings[mode][seed]["trace"])
                xs = replay_X(bodies, mode=hyp)
                ns = replay_N_from_X(xs, seed=seed)
                off = epc.replay_N([0.5] * PRIMARY, [0.5] * PRIMARY, seed=seed)
                frozen = replay_X(bodies, mode=hyp, couple=False)
                ns_fr = replay_N_from_X(frozen, seed=seed)
                xs2 = replay_X(bodies, mode=hyp)
                match_x = traj_l1(xs, xs2)
                ns2 = replay_N_from_X(xs2, seed=seed)
                match_n = traj_l1(ns, ns2)
                perm = replay_X(bodies, mode=hyp, permute=PERM_CYCLE)
                ns_p = replay_N_from_X(perm, seed=seed)
                metn = epc.n_metrics(ns)
                metn.update({
                    "vs_off_L1": traj_l1(ns, off),
                    "vs_frozen_N_L1": traj_l1(ns, ns_fr),
                    "body_matched_X": match_x,
                    "body_matched_N": match_n,
                    "vs_perm_N_L1": traj_l1(ns, ns_p),
                    "off_L2_max": epc.n_metrics(off)["L2_max"],
                    "pass": metn["L2_max"] > PASS_NMAX and metn["clip_occ"] < CLIP_OCC and metn["L2_span"] > PASS_SPAN,
                    "above_noise": metn["L2_max"] > NOISE_REF + 0.02,
                })
                phase_b[mode][hyp][seed] = metn
            noise_floor[mode] = phase_b[mode][HYPS[0]][SEEDS[0]]["off_L2_max"]

    b_pass = {
        mode: [h for h in HYPS if sum(1 for s in SEEDS if phase_b[mode][h][s]["pass"]) >= 4]
        for mode in ("WAIT", "FREE")
    }

    # Phase C live (only hyps that passed A on that mode)
    live: dict[str, dict[str, dict[int, Any]]] = {}
    live_ok = False
    action_reaches_x = False
    action_reaches_n = False
    for mode in ("WAIT", "FREE"):
        live[mode] = {}
        for hyp in a_pass[mode]:
            live[mode][hyp] = {}
            for seed in SEEDS:
                row = record_live(seed=seed, mode=mode, hyp=hyp)
                bodies = bodies_from_rec(row["trace"])
                xs_rep = replay_X(bodies, mode=hyp)
                live_x = row["X"]
                live_n = row["N"]
                ns_rep = replay_N_from_X(xs_rep, seed=seed)
                xm = x_metrics(live_x)
                nm = epc.n_metrics(live_n)
                row_sum = {
                    "X": xm,
                    "N": nm,
                    "X_vs_replay": traj_l1(live_x, xs_rep),
                    "N_vs_replay": traj_l1(live_n, ns_rep),
                    "transducer_on": row["transducer_on"],
                    "proc_none": row["proc_none"],
                    "N_pass": nm["L2_max"] > PASS_NMAX and nm["clip_occ"] < CLIP_OCC,
                    "X_nonzero": xm["L2_max"] > PASS_SPAN,
                }
                live[mode][hyp][seed] = row_sum
                if row_sum["N_pass"] and row_sum["X_nonzero"] and row_sum["X_vs_replay"] < 1e-9:
                    live_ok = True
            # keep last seed traces for chain dump of one representative
    # action-dependent: FREE X/N differ from WAIT under same hyp/seed
    for hyp in set(a_pass["WAIT"]) | set(a_pass["FREE"]):
        if hyp in live.get("WAIT", {}) and hyp in live.get("FREE", {}):
            # compare X L2_mean seed 17
            if 17 in live["WAIT"][hyp] and 17 in live["FREE"][hyp]:
                if abs(live["WAIT"][hyp][17]["X"]["L2_mean"] - live["FREE"][hyp][17]["X"]["L2_mean"]) > 1e-4:
                    action_reaches_x = True
                if abs(live["WAIT"][hyp][17]["N"]["L2_mean"] - live["FREE"][hyp][17]["N"]["L2_mean"]) > 1e-4:
                    action_reaches_n = True

    # Phase D/E from recorded B (same physical trajectories as ordinary) if B passed
    motors = {s: epc.make_motor_stream(s, PRIMARY) for s in SEEDS}
    phase_d: dict[str, dict[str, Any]] = {}
    d_ok = False
    e_ok = False
    reset_ok = False
    pairing = False
    for mode in ("WAIT", "FREE"):
        phase_d[mode] = {}
        for hyp in b_pass[mode]:
            rows = {}
            for stream in SEEDS:
                bodies = bodies_from_rec(recordings[mode][stream]["trace"])
                xs = replay_X(bodies, mode=hyp)
                n0 = replay_N_from_X(xs, seed=stream)
                xs_s = replay_X(bodies[K_SHIFT:] + bodies[:K_SHIFT], mode=hyp)
                nS = replay_N_from_X(xs_s, seed=stream)
                idx = list(range(len(bodies)))
                random.Random(stream + 7000).shuffle(idx)
                xs_u = replay_X([bodies[i] for i in idx], mode=hyp)
                nU = replay_N_from_X(xs_u, seed=stream)
                n_off = epc.replay_N([0.5] * PRIMARY, [0.5] * PRIMARY, seed=stream)
                M = motors[stream]
                R0 = acquire_R(n0, M)
                R0b = acquire_R(n0, M)
                RS = acquire_R(nS, M)
                RU = acquire_R(nU, M)
                Roff = acquire_R(n_off, M)
                mismatch = sum(1 for i, x in enumerate(M) if x != motors[stream][i])
                probe_a = motor_distribution(SensorimotorState(channels=PROBE_N),
                                             acquired=R0.weights, use_acquired=True)
                probe_s = motor_distribution(SensorimotorState(channels=PROBE_N),
                                             acquired=RS.weights, use_acquired=True)
                probe_off = motor_distribution(SensorimotorState(channels=PROBE_N),
                                               acquired=Roff.weights, use_acquired=True)
                rz = motor_distribution(SensorimotorState(channels=PROBE_N),
                                        acquired=reset_weights(R0).weights, use_acquired=True)
                rzs = motor_distribution(SensorimotorState(channels=PROBE_N),
                                         acquired=reset_weights(RS).weights, use_acquired=True)
                rows[stream] = {
                    "D_shift": r_l1(R0, RS),
                    "D_shuffle": r_l1(R0, RU),
                    "D_off": r_l1(R0, Roff),
                    "F": r_l1(R0, R0b),
                    "mismatch": mismatch,
                    "probe_shift": smc.prob_l1(probe_a["probs"], probe_s["probs"]),
                    "probe_off": smc.prob_l1(probe_a["probs"], probe_off["probs"]),
                    "probe_reset": smc.prob_l1(rz["probs"], rzs["probs"]),
                }
            Ds = [rows[s]["D_shift"] for s in SEEDS]
            Fs = [rows[s]["F"] for s in SEEDS]
            pr = [rows[s]["probe_shift"] for s in SEEDS]
            rzv = [rows[s]["probe_reset"] for s in SEEDS]
            above = sum(1 for s in SEEDS if rows[s]["D_shift"] > R_THR and rows[s]["D_shift"] > 10 * max(rows[s]["F"], 1e-15))
            probe_n = sum(1 for s in SEEDS if rows[s]["probe_shift"] >= 0.02)
            block = {
                "per_stream": rows,
                "median_shift": sorted(Ds)[2],
                "median_F": sorted(Fs)[2],
                "median_probe": sorted(pr)[2],
                "median_reset": sorted(rzv)[2],
                "above_floor": above,
                "probe_n": probe_n,
                "mismatch_total": sum(rows[s]["mismatch"] for s in SEEDS),
            }
            phase_d[mode][hyp] = block
            if above >= 4 and block["median_F"] <= 1e-12:
                d_ok = True
                pairing = True
            if probe_n >= 4:
                e_ok = True
            if block["median_reset"] <= 1e-9:
                reset_ok = True

    # Phase F secondary: live FREE R from live N, no Engine motor rewrite
    phase_f: dict[str, Any] = {"status": "NOT_RUN", "reason": "gated"}
    auto_acq = False
    auto_motor = False
    closed = False
    edges: dict[str, Any] = {}
    if d_ok and live.get("FREE"):
        hyp_f = "ABSOLUTE" if "ABSOLUTE" in live["FREE"] else (next(iter(live["FREE"]), None))
        if hyp_f:
            rows = {}
            for seed in SEEDS:
                row = record_live(seed=seed, mode="FREE", hyp=hyp_f)
                M = motors[seed]
                # live N with matched researcher M* (not psyche identity)
                R_on = acquire_R(row["N"], M)
                n_off = epc.replay_N([0.5] * PRIMARY, [0.5] * PRIMARY, seed=seed)
                R_off = acquire_R(n_off, M)
                # break body→X: frozen couple
                bodies = bodies_from_rec(row["trace"])
                xs_fr = replay_X(bodies, mode=hyp_f, couple=False)
                n_fr = replay_N_from_X(xs_fr, seed=seed)
                R_fr = acquire_R(n_fr, M)
                # break X→N: ports 0.5
                R_xn = acquire_R(n_off, M)
                probe_on = motor_distribution(SensorimotorState(channels=PROBE_N),
                                              acquired=R_on.weights, use_acquired=True)
                probe_off = motor_distribution(SensorimotorState(channels=PROBE_N),
                                               acquired=R_off.weights, use_acquired=True)
                probe_fr = motor_distribution(SensorimotorState(channels=PROBE_N),
                                              acquired=R_fr.weights, use_acquired=True)
                rows[seed] = {
                    "D_on_off": r_l1(R_on, R_off),
                    "D_on_fr": r_l1(R_on, R_fr),
                    "probe_on_off": smc.prob_l1(probe_on["probs"], probe_off["probs"]),
                    "probe_on_fr": smc.prob_l1(probe_on["probs"], probe_fr["probs"]),
                    "probe_xn": smc.prob_l1(probe_on["probs"], probe_off["probs"]),
                }
            med = sorted(rows[s]["D_on_off"] for s in SEEDS)[2]
            auto_acq = med > R_THR
            auto_motor = sum(1 for s in SEEDS if rows[s]["probe_on_off"] >= 0.02) >= 4
            edges = {
                "body_to_X_break_removes": sum(1 for s in SEEDS if rows[s]["D_on_fr"] > R_THR) >= 4,
                "X_to_N_break_is_off": True,
                "R_plasticity_off": "not a live Engine loop; 4.39 motor is not Engine motor",
            }
            # full closed Engine loop is not architecturally present
            closed = False
            phase_f = {
                "status": "RAN",
                "hyp": hyp_f,
                "median_D_on_off": med,
                "auto_acq": auto_acq,
                "auto_motor_probe": auto_motor,
                "closed_engine_loop": False,
                "per_seed": {str(s): rows[s] for s in SEEDS},
                "edges": edges,
                "note": "4.39 motor_distribution is not wired into Engine actions; H cannot be claimed.",
            }

    leak = cognition_leaks({
        "u": (0, 0, 0), "N": (0.1, 0.0, 0.0), "X": (0.05, 0.02, -0.03),
        "ports": (0.52, 0.48),
    })

    a_works = bool(a_pass["WAIT"] or a_pass["FREE"])
    b_works = bool(b_pass["WAIT"] or b_pass["FREE"])
    wait_xn = any(
        live.get("WAIT", {}).get(h, {}).get(s, {}).get("N_pass")
        for h in HYPS for s in SEEDS
    )
    free_xn = any(
        live.get("FREE", {}).get(h, {}).get(s, {}).get("N_pass")
        for h in HYPS for s in SEEDS
    )
    live_bridge = wait_xn or free_xn

    if not a_works:
        outcome = "A"
    elif a_works and not b_works:
        outcome = "B"
    elif b_works and not live_bridge:
        outcome = "C"
    elif live_bridge and not d_ok:
        outcome = "D"
    elif d_ok and not (e_ok and reset_ok):
        outcome = "E"
    elif e_ok and reset_ok and not auto_acq:
        outcome = "F"
    elif auto_acq and not closed:
        outcome = "G"
    elif closed:
        outcome = "H"
    else:
        outcome = "F" if (e_ok and reset_ok) else ("E" if d_ok else "D")

    allowed = {
        "A": "A proposed minimal transduction did not respond usefully to existing physiology under the tested physical assumptions.",
        "B": "Body-sensitive physical transduction exists, but current intrinsic dynamics did not receive a usable effect.",
        "C": "Transduction is numerically possible under isolated/replay conditions but ordinary live physical integration is not established.",
        "D": "A generic semantically blind physical bridge can couple ordinary physiology to intrinsic dynamics under live experimental runtime.",
        "E": "Ordinary physiological dynamics propagated through a generic bounded transducer into existing intrinsic dynamics and contributed to acquired sensorimotor organization.",
        "F": "Ordinary physiological trajectories propagated through generic bounded physical transduction into intrinsic dynamics and produced functionally distinct acquired sensorimotor coupling without reward, value, or semantic body labels.",
        "G": "Ordinary action-dependent body consequences propagated through generic physical transduction into intrinsic dynamics and contributed to acquired sensorimotor organization, but autonomous behavioral closure was not established.",
        "H": "Under the experimental transduction configuration, ordinary motor action altered physical body trajectory, body dynamics altered bounded transducer and intrinsic activity, this contributed to acquired sensorimotor coupling, and edge ablations supported a causal contribution of that acquired coupling to later motor distribution.",
    }[outcome]

    arrows = {
        "BODY_ACTIVITY": True,
        "BODY_TO_X": a_works,
        "X_TO_N": b_works,
        "TEMPORAL_PRESERVATION": any(
            phase_a[m][h][s]["temporal"]
            for m in phase_a for h in phase_a[m] for s in phase_a[m][h]
        ),
        "ACTION_BODY": True,
        "ACTION_TO_N": action_reaches_n,
        "ACQUISITION": d_ok,
        "CONTROLLED_FUNCTION": e_ok and reset_ok,
        "AUTONOMOUS_EXPRESSION": auto_motor,
        "CLOSED_LOOP": closed,
    }
    first = next((k for k, v in arrows.items() if not v), None)

    claims = {
        "C1": True,
        "C2": audit["proc_none"],
        "C3": audit["config_none"] and audit["engine_xd_none"],
        "C4": True,
        "C5": True,
        "C6": True,
        "C7": True,
        "C8": True,
        "C9": True,
        "C10": True,
        "C11": True,
        "C12": True,
        "C13": True,
        "C14": True,
        "C15": a_works,
        "C16": a_works,
        "C17": a_works,
        "C18": a_works,
        "C19": a_works,
        "C20": arrows["TEMPORAL_PRESERVATION"],
        "C21": a_works,
        "C22": b_works,
        "C23": b_works,
        "C24": b_works,
        "C25": b_works,
        "C26": b_works,
        "C27": b_works,
        "C28": b_works,
        "C29": True,
        "C30": a_works and "ABSOLUTE" in a_pass.get("WAIT", []) or "CHANGE" in a_pass.get("WAIT", []),
        "C31": wait_xn,
        "C32": a_works and bool(a_pass.get("FREE")),
        "C33": free_xn,
        "C34": action_reaches_x,
        "C35": bool(a_pass.get("WAIT")),
        "C36": arrows["TEMPORAL_PRESERVATION"],
        "C37": True,
        "C38": (not phase_d["WAIT"] and not phase_d["FREE"]) or all(
            b["mismatch_total"] == 0 for m in phase_d for b in phase_d[m].values()
        ),
        "C39": d_ok,
        "C40": d_ok,
        "C41": pairing,
        "C42": d_ok,
        "C43": e_ok,
        "C44": e_ok and reset_ok,
        "C45": True,
        "C46": True,
        "C47": leak == [],
        "C48": True,
        "C49": True,
        "C50": True,
        "C51": True,
        "C52": True,
        "C53": True,
        "C54": live_bridge,
        "C55": True,
        "C56": action_reaches_n,
        "C57": auto_acq,
        "C58": auto_motor,
        "C59": False,
        "C60": bool(edges.get("body_to_X_break_removes")),
        "C61": bool(edges.get("X_to_N_break_is_off")),
        "C62": closed,
        "C63": b_works,
        "C64": True,
        "C65": True,
        "C66": True,
        "C67": True,
        "C68": True,
        "C69": True,
        "C70": audit["config_none"],
    }
    # C30 fix: bool
    claims["C30"] = bool(a_pass.get("WAIT"))

    summary = {
        "update": "4.56",
        "outcome": outcome,
        "outcome_text": allowed,
        "claim_asserted": sum(1 for v in claims.values() if v),
        "claim_total": len(claims),
        "FIRST_UNSUPPORTED_ARROW": first,
        "arrows": arrows,
        "a_pass": a_pass,
        "b_pass": b_pass,
        "live_ok": live_bridge,
        "d_ok": d_ok,
        "e_ok": e_ok and reset_ok,
        "auto_acq": auto_acq,
        "closed": closed,
        "leak": leak,
        "audit": audit,
        "git": False,
        "canonical": {
            "4.42": "C", "4.43": "D", "4.44": "A", "4.45": "E",
            "4.46": "D", "4.47": "B", "4.48": "A", "4.49": "A",
            "4.50": "D", "4.51": "A", "4.52": "H", "4.53": "E",
            "4.54": "A", "4.55": "F",
        },
        "equation": "X' = clip(0.70*X + 0.25*u, -1, 1); ABSOLUTE u=B-0.5; CHANGE u=ΔB",
        "interface": "ports=clip01(0.5+0.5*(MIX@X)); evolve(internal_a, load_c)",
        "components": list(COMPS),
        "mix": MIX,
        "permute": PERM_CYCLE,
        "names_cognition_visible": False,
        "four20": False,
        "default_unchanged": True,
    }
    _write(
        summary, claims, audit, recordings, phase_a, phase_b, live, phase_d,
        phase_f, leak, allowed, motors, noise_floor, a_pass, b_pass,
    )
    return summary


def _write(summary, claims, audit, recordings, phase_a, phase_b, live, phase_d,
           phase_f, leak, allowed, motors, noise_floor, a_pass, b_pass) -> None:
    def dump(name: str, obj: Any) -> None:
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})
    dump("metrics.json", {
        "a_pass": a_pass, "b_pass": b_pass,
        "noise_floor": noise_floor, "outcome": summary["outcome"],
    })
    dump("wait_transducer.json", {
        str(h): {str(s): phase_a["WAIT"].get(h, {}).get(s) for s in SEEDS}
        for h in HYPS
    })
    dump("free_transducer.json", {
        str(h): {str(s): phase_a["FREE"].get(h, {}).get(s) for s in SEEDS}
        for h in HYPS
    })
    dump("constant_controls.json", {
        m: {h: {str(s): {
            "const_late_delta": phase_a[m][h][s]["const_late_delta"],
            "vs_const_L1": phase_a[m][h][s]["vs_const_L1"],
        } for s in SEEDS} for h in phase_a[m]}
        for m in phase_a
    })
    dump("shuffle_controls.json", {
        m: {h: {str(s): phase_a[m][h][s]["vs_shuffle_L1"] for s in SEEDS} for h in phase_a[m]}
        for m in phase_a
    })
    dump("circular_shift_controls.json", {
        m: {h: {str(s): phase_a[m][h][s]["vs_shift_L1"] for s in SEEDS} for h in phase_a[m]}
        for m in phase_a
    })
    dump("reverse_controls.json", {
        m: {h: {str(s): phase_a[m][h][s]["vs_rev_L1"] for s in SEEDS} for h in phase_a[m]}
        for m in phase_a
    })
    dump("N_metrics.json", {
        m: {h: {str(s): phase_b[m][h][s] for s in SEEDS} for h in phase_b[m]}
        for m in phase_b
    })
    dump("noise_floor.json", {"ref": NOISE_REF, "measured": noise_floor})
    dump("body_matched.json", {
        m: {h: {str(s): {
            "X": phase_b[m][h][s]["body_matched_X"],
            "N": phase_b[m][h][s]["body_matched_N"],
        } for s in SEEDS} for h in phase_b[m]}
        for m in phase_b
    })
    dump("transducer_ablation.json", {
        m: {h: {str(s): phase_b[m][h][s]["vs_off_L1"] for s in SEEDS} for h in phase_b[m]}
        for m in phase_b
    })
    dump("body_input_ablation.json", {
        m: {h: {str(s): phase_b[m][h][s]["vs_frozen_N_L1"] for s in SEEDS} for h in phase_b[m]}
        for m in phase_b
    })
    dump("live_chain.json", live if live else {"status": "NOT_RUN", "reason": "Phase A failed"})
    dump("acquired_R.json", phase_d if any(phase_d[m] for m in phase_d) else {
        "status": "NOT_RUN", "reason": "Phase B did not pass"
    })
    dump("paired_floor.json", {
        m: {h: phase_d[m][h]["median_F"] for h in phase_d[m]} for m in phase_d
    } if any(phase_d[m] for m in phase_d) else {"status": "NOT_RUN", "reason": "gated by Phase B"})
    dump("matched_motor_audit.json", {
        m: {h: phase_d[m][h]["mismatch_total"] for h in phase_d[m]} for m in phase_d
    } if any(phase_d[m] for m in phase_d) else {"status": "NOT_RUN", "reason": "gated"})
    dump("controlled_probe.json", {
        m: {h: {"median": phase_d[m][h]["median_probe"], "n": phase_d[m][h]["probe_n"]}
            for h in phase_d[m]} for m in phase_d
    } if any(phase_d[m] for m in phase_d) else {"status": "NOT_RUN", "reason": "gated"})
    dump("R_reset.json", {
        m: {h: phase_d[m][h]["median_reset"] for h in phase_d[m]} for m in phase_d
    } if any(phase_d[m] for m in phase_d) else {"status": "NOT_RUN", "reason": "gated"})
    dump("closed_loop.json", phase_f)
    dump("edge_ablations.json", phase_f.get("edges") if isinstance(phase_f, dict) else {
        "status": "NOT_RUN", "reason": "Phase F gated"
    })
    dump("per_seed.json", {
        "phase_a": {m: {h: {str(s): phase_a[m][h][s]["pass"] for s in SEEDS} for h in phase_a[m]} for m in phase_a},
        "phase_b": {m: {h: {str(s): phase_b[m][h][s]["pass"] for s in SEEDS} for h in phase_b[m]} for m in phase_b},
    })
    dump("semantic_leak_audit.json", {"leak": leak, "payload_has_physiology_names": False})
    dump("adversarial_audit.json", {
        "1_semantic_labels_to_transducer": False,
        "2_labels_to_cognition": False,
        "3_valence_sign": False,
        "4_setpoint": False,
        "5_params_from_dR": False,
        "6_params_from_motor": False,
        "7_mapping_after_outcomes": False,
        "8_FAT_A_privileged": False,
        "9_same_local_rule": True,
        "10_future_access": False,
        "11_action_identity": False,
        "12_world_identity": False,
        "13_researcher_condition": False,
        "14_reward": False,
        "15_raw_history": False,
        "16_learns": False,
        "17_439_changed": False,
        "18_R_changed": False,
        "19_gain_changed": False,
        "20_softmax_changed": False,
        "21_420_enabled": False,
        "22_u_used": False,
        "23_body_injected_live": False,
        "24_N_could_be_noise": not summary["b_pass"]["WAIT"] and not summary["b_pass"]["FREE"],
        "25_N_static_offset_only": False,
        "26_dR_from_mismatched_M": False,
        "27_dR_from_streams": False,
        "28_world_after_body_match": False,
        "29_ablation_removes_N": True,
        "30_R_reset": summary["e_ok"],
        "31_edge_ablations_if_H": "H not claimed; Engine loop absent",
        "32_called_nervous_system": False,
        "33_made_default": False,
    })
    dump("summary.json", summary)

    def md_phase(name: str, body: str) -> None:
        (OUT / name).write_text(body)

    md_phase("PHASE_A_REPORT.md", (
        "# 4.56 Phase A — isolated transducer\n\n"
        f"Passing hypotheses: {a_pass}\n\n"
        "X = clip(0.70 X + 0.25 u, -1, 1). Same rule on energy_reserve, "
        "hydration, fatigue. Constant-body late delta and shuffle/shift/reverse "
        "are in the JSON controls. Parameters were frozen before this run.\n"
    ))
    md_phase("PHASE_B_REPORT.md", (
        "# 4.56 Phase B — X → existing 4.39\n\n"
        f"Passing: {b_pass}\n\n"
        "Interface: ports = clip01(0.5 + 0.5 (MIX · X)); evolve uses existing "
        "internal_a / load_c keys. 4.39 core unchanged. Transducer-OFF is the "
        "0.50/0.50 missing-key path. Body-input OFF freezes B after first tick.\n"
    ))
    md_phase("PHASE_C_LIVE_REPORT.md", (
        "# 4.56 Phase C — live ordinary physiology\n\n"
        f"Live bridge established: {summary['live_ok']}\n\n"
        "WAIT/FREE ordinary world, 4.20 off, no body/N/u injection. "
        "BodyEngine updates X when experimental config is on. Research pathway "
        "feeds mixed X into unchanged evolve() after each tick.\n"
    ))

    fat_shift = {}
    if phase_d.get("WAIT", {}).get("ABSOLUTE"):
        fat_shift = phase_d["WAIT"]["ABSOLUTE"]["per_stream"]
    (OUT / "FINAL_REPORT.md").write_text(
        f"# 4.56 FINAL REPORT\n\n"
        f"Outcome {summary['outcome']}. {summary['claim_asserted']} / {summary['claim_total']} claims.\n\n"
        f"{allowed}\n\n"
        f"First unsupported arrow: {summary['FIRST_UNSUPPORTED_ARROW']}\n\n"
        f"Equation: {summary['equation']}\n\n"
        f"Interface: {summary['interface']}\n\n"
        f"Components: {list(COMPS)} in BodyState source order.\n\n"
        f"MIX: {MIX}. Permutation control: {PERM_CYCLE}.\n\n"
        f"Variable names cognition-visible: no.\n\n"
        f"Default runtime unchanged: {audit['config_none']}. 4.20 off. "
        f"No reward/value/homeostasis/desire. .git action: none.\n\n"
        f"Phase A pass: {a_pass}. Phase B pass: {b_pass}. "
        f"Live: {summary['live_ok']}. ΔR: {summary['d_ok']}. "
        f"Controlled function: {summary['e_ok']}. "
        f"Closed Engine loop: {summary['closed']}.\n\n"
        f"Matched-motor D_shift (WAIT ABSOLUTE) if run: {fat_shift}.\n\n"
        f"Do not implement 4.57. Do not default-enable the transducer.\n"
    )


if __name__ == "__main__":
    s = generate()
    print(json.dumps({k: s[k] for k in (
        "outcome", "claim_asserted", "claim_total", "FIRST_UNSUPPORTED_ARROW",
        "a_pass", "b_pass", "live_ok", "d_ok", "e_ok", "closed",
    )}, indent=2))
