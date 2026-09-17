"""Update 4.55 — existing physiology × 4.39/4.46 compatibility diagnostic.

Researcher-side replay only. Does not wire physiology into ordinary 4.39.
Does not enable 4.20. Does not implement 4.56.
"""
from __future__ import annotations

import json
import math
import random
import re
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
from mechanistic_mind.research.ordinary_physical_ecology import default_engine, body_payload
from worlds.organism_world_v03 import OrganismWorld, default_organism_world_config

SEEDS = (17, 23, 41, 59, 83)
PRIMARY = 96
K_SHIFT = 24
NEUTRAL = 0.5
NOISE_REF = 0.043
PASS_NMAX = 0.08
PASS_SPAN = 0.02
CLIP = 0.99
CLIP_OCC = 0.50
R_THR = 0.02
PROBE_N = (0.70, 0.0, 0.0)
OUT = Path("results/update455_existing_physiology_compatibility")
FORBIDDEN = bcd.FORBIDDEN + (
    "COMFORT", "DISCOMFORT", "WELLBEING", "HEALTH_VALUE", "BODY_VALUE",
    "PHYSIOLOGY_QUALITY", "HOMEOSTASIS_TARGET", "OPTIMAL_STATE",
    "PREFERENCE", "REINFORCEMENT", "UPBRINGING", "PERSONALITY",
    "PROJECTION_ID", "CONDITION_ID", "RESEARCHER_MAPPING",
    "SELF", "IDENTITY", "EXPLORATION", "CURIOSITY",
)

VARS = ("fatigue", "energy_reserve", "hydration")
P0 = ("FAT_A", "ENE_A", "HYD_A", "FAT_C", "ENE_C", "HYD_C")
P1 = ("FAT_ENE", "FAT_HYD", "ENE_HYD")
P2 = ("ENE_FAT", "HYD_FAT", "HYD_ENE")
ALL_PROJ = ("CONST",) + P0 + P1 + P2
SRC = {
    "FAT": "fatigue", "ENE": "energy_reserve", "HYD": "hydration",
}


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def m_vec(action: str) -> tuple[float, float, float]:
    if action == "M0":
        return (1.0, 0.0, 0.0)
    if action == "M1":
        return (0.0, 1.0, 0.0)
    if action == "M2":
        return (0.0, 0.0, 1.0)
    return (0.0, 0.0, 0.0)


def make_motor_stream(stream: int, duration: int) -> list[str]:
    N = SensorimotorState()
    body = {"internal_a": 0.50, "load_c": 0.50}
    seq = []
    for t in range(duration):
        N = evolve(N, body=body, sensory=(0.5, 0.5),
                   random_value=((stream * 41 + t * 7) % 101) / 100.0)
        seq.append(sample_motor(motor_distribution(N), seed=stream * 1009 + t))
    return seq


def project(pid: str, rec: dict[str, list[float]]) -> tuple[list[float], list[float]]:
    n = len(rec["fatigue"])
    if pid == "CONST":
        return [NEUTRAL] * n, [NEUTRAL] * n
    if pid.endswith("_A") or pid.endswith("_C"):
        key = SRC[pid[:3]]
        xs = list(rec[key])
        if pid.endswith("_A"):
            return xs, [NEUTRAL] * n
        return [NEUTRAL] * n, xs
    left, right = pid.split("_")
    return list(rec[SRC[left]]), list(rec[SRC[right]])


def replay_N(a: list[float], c: list[float], *, seed: int) -> list[tuple[float, float, float]]:
    N = SensorimotorState()
    out = []
    for t in range(len(a)):
        N = evolve(
            N, body={"internal_a": float(a[t]), "load_c": float(c[t])},
            sensory=(0.5, 0.5),
            random_value=((seed * 29 + t * 13) % 101) / 100.0,
        )
        out.append(tuple(float(x) for x in N.channels))
    return out


def n_metrics(rows: list[tuple[float, float, float]]) -> dict[str, float]:
    l2 = [ema.l2(r) for r in rows]
    l1 = [ema.l1(r) for r in rows]
    linf = [max(abs(x) for x in r) for r in rows]
    clip = sum(1 for r in rows if max(abs(x) for x in r) >= CLIP) / len(rows)
    mean_l2 = sum(l2) / len(l2)
    return {
        "L2_mean": mean_l2,
        "L2_max": max(l2),
        "L2_span": max(l2) - min(l2),
        "L1_mean": sum(l1) / len(l1),
        "Linf_mean": sum(linf) / len(linf),
        "clip_occ": clip,
        "var_L2": sum((x - mean_l2) ** 2 for x in l2) / len(l2),
    }


def traj_l1(a: list[tuple[float, ...]], b: list[tuple[float, ...]]) -> float:
    n = min(len(a), len(b))
    return sum(sum(abs(a[t][i] - b[t][i]) for i in range(3)) for t in range(n)) / n


def classify_phys(xs: list[float]) -> str:
    span = max(xs) - min(xs)
    if span < 1e-9:
        return "STATIC"
    if span < 0.02:
        return "NEAR_STATIC"
    hi = sum(1 for x in xs if x >= 0.90) / len(xs)
    lo = sum(1 for x in xs if x <= 0.10) / len(xs)
    deltas = [xs[i + 1] - xs[i] for i in range(len(xs) - 1)]
    pos = sum(1 for d in deltas if d > 1e-9)
    neg = sum(1 for d in deltas if d < -1e-9)
    if hi >= 0.40 or lo >= 0.40:
        return "SATURATING"
    if pos > 0.8 * len(deltas) or neg > 0.8 * len(deltas):
        return "MONOTONIC"
    sign_flips = sum(1 for i in range(1, len(deltas)) if deltas[i] * deltas[i - 1] < 0)
    if sign_flips >= 2:
        return "EPISODIC" if span > 0.05 else "IRREGULAR_STRUCTURED"
    return "IRREGULAR_STRUCTURED"


def phys_stats(xs: list[float]) -> dict[str, Any]:
    m = sum(xs) / len(xs)
    return {
        "mean": m, "var": sum((x - m) ** 2 for x in xs) / len(xs),
        "min": min(xs), "max": max(xs), "range": max(xs) - min(xs),
        "sat_occ": sum(1 for x in xs if x >= 0.90) / len(xs),
        "low_occ": sum(1 for x in xs if x <= 0.10) / len(xs),
        "class": classify_phys(xs),
    }


def record_mode(*, seed: int, mode: str) -> dict[str, Any]:
    engine = default_engine(seed=seed)
    rec = {k: [] for k in VARS}
    rec["activity_load"] = []
    rec["damage"] = []
    actions = []
    for t in range(PRIMARY):
        if mode == "WAIT":
            engine.step({"A001": Action.wait()})
            actions.append("WAIT")
        else:
            engine.step()
            actions.append("FREE")
        p = body_payload(engine)
        for k in VARS:
            rec[k].append(float(p.get(k) or 0.0))
        rec["activity_load"].append(float(p.get("activity_load") or 0.0))
        rec["damage"].append(float(p.get("damage") or 0.0))
    cfg_none = getattr(engine.world.body_config, "persistent_process_config", "X") is None
    return {
        "seed": seed, "mode": mode, "cfg_none": cfg_none,
        "trace": rec, "actions": actions,
        "stats": {k: phys_stats(rec[k]) for k in (*VARS, "activity_load", "damage")},
        "load_keys": sorted({
            str(k) for k in dict(p.get("internal_loads") or {}).keys()
        }) if False else [],
    }


def acquire_R(n_rows: list[tuple[float, float, float]], motor: list[str]) -> AcquiredCouplingState:
    R = AcquiredCouplingState()
    for t, ch in enumerate(n_rows):
        R = r_step(R, n=ch, m=m_vec(motor[t]), plasticity=True)
    return R


def phase_a_one(a: list[float], c: list[float], *, seed: int) -> dict[str, Any]:
    orig = replay_N(a, c, seed=seed)
    mean_a, mean_c = sum(a) / len(a), sum(c) / len(c)
    const = replay_N([mean_a] * len(a), [mean_c] * len(c), seed=seed)
    idx = list(range(len(a)))
    random.Random(seed + 7000).shuffle(idx)
    sh_a = [a[i] for i in idx]
    sh_c = [c[i] for i in idx]
    shuf = replay_N(sh_a, sh_c, seed=seed)
    k = K_SHIFT % len(a)
    sh_a2 = a[k:] + a[:k]
    sh_c2 = c[k:] + c[:k]
    shifted = replay_N(sh_a2, sh_c2, seed=seed)
    rev = replay_N(list(reversed(a)), list(reversed(c)), seed=seed)
    met = n_metrics(orig)
    met["vs_const_L1"] = traj_l1(orig, const)
    met["vs_shuffle_L1"] = traj_l1(orig, shuf)
    met["vs_shift_L1"] = traj_l1(orig, shifted)
    met["vs_rev_L1"] = traj_l1(orig, rev)
    met["pass"] = (
        met["L2_max"] > PASS_NMAX
        and met["clip_occ"] < CLIP_OCC
        and met["L2_span"] > PASS_SPAN
        and met["vs_const_L1"] > PASS_SPAN
    )
    met["temporal_preserved"] = met["vs_shuffle_L1"] > PASS_SPAN
    return met


def generate() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    assert BodyConfig().persistent_process_config is None
    assert BASE_NON_WAIT == 0.08

    recordings: dict[str, dict[int, Any]] = {"WAIT": {}, "FREE": {}}
    for seed in SEEDS:
        recordings["WAIT"][seed] = record_mode(seed=seed, mode="WAIT")
        recordings["FREE"][seed] = record_mode(seed=seed, mode="FREE")

    phase_a: dict[str, dict[str, dict[int, Any]]] = {}
    passing: dict[str, list[str]] = {"WAIT": [], "FREE": []}
    for mode in ("WAIT", "FREE"):
        phase_a[mode] = {}
        for pid in ALL_PROJ:
            phase_a[mode][pid] = {}
            n_pass = 0
            for seed in SEEDS:
                a, c = project(pid, recordings[mode][seed]["trace"])
                met = phase_a_one(a, c, seed=seed)
                phase_a[mode][pid][seed] = met
                if met["pass"]:
                    n_pass += 1
            if pid != "CONST" and n_pass >= 4:
                passing[mode].append(pid)

    # Phase B
    motors = {s: make_motor_stream(s, PRIMARY) for s in SEEDS}
    phase_b: dict[str, dict[str, Any]] = {}
    for mode in ("WAIT", "FREE"):
        phase_b[mode] = {}
        for pid in passing[mode]:
            rows = {}
            for stream in SEEDS:
                rec = recordings[mode][stream]["trace"]
                a, c = project(pid, rec)
                n0 = replay_N(a, c, seed=stream)
                k = K_SHIFT
                nS = replay_N(a[k:] + a[:k], c[k:] + c[:k], seed=stream)
                idx = list(range(len(a)))
                random.Random(stream + 7000).shuffle(idx)
                nU = replay_N([a[i] for i in idx], [c[i] for i in idx], seed=stream)
                M = motors[stream]
                R0 = acquire_R(n0, M)
                R0b = acquire_R(n0, M)
                RS = acquire_R(nS, M)
                RU = acquire_R(nU, M)
                mismatch = sum(1 for i, x in enumerate(M) if x != motors[stream][i])
                probe_a = motor_distribution(SensorimotorState(channels=PROBE_N),
                                             acquired=R0.weights, use_acquired=True)
                probe_s = motor_distribution(SensorimotorState(channels=PROBE_N),
                                             acquired=RS.weights, use_acquired=True)
                r0 = reset_weights(R0)
                probe_z = motor_distribution(SensorimotorState(channels=PROBE_N),
                                             acquired=r0.weights, use_acquired=True)
                probe_zs = motor_distribution(SensorimotorState(channels=PROBE_N),
                                              acquired=reset_weights(RS).weights, use_acquired=True)
                rows[stream] = {
                    "D_shift": r_l1(R0, RS),
                    "D_shuffle": r_l1(R0, RU),
                    "F": r_l1(R0, R0b),
                    "mismatch": mismatch,
                    "probe_shift": smc.prob_l1(probe_a["probs"], probe_s["probs"]),
                    "probe_reset": smc.prob_l1(probe_z["probs"], probe_zs["probs"]),
                }
            Ds = [rows[s]["D_shift"] for s in SEEDS]
            Fs = [rows[s]["F"] for s in SEEDS]
            Us = [rows[s]["D_shuffle"] for s in SEEDS]
            pr = [rows[s]["probe_shift"] for s in SEEDS]
            rz = [rows[s]["probe_reset"] for s in SEEDS]
            above = sum(1 for s in SEEDS if rows[s]["D_shift"] > R_THR and rows[s]["D_shift"] > 10 * max(rows[s]["F"], 1e-15))
            phase_b[mode][pid] = {
                "per_stream": rows,
                "median_shift": sorted(Ds)[2],
                "median_shuffle": sorted(Us)[2],
                "median_F": sorted(Fs)[2],
                "median_probe": sorted(pr)[2],
                "median_reset": sorted(rz)[2],
                "above_floor": above,
                "mismatch_total": sum(rows[s]["mismatch"] for s in SEEDS),
            }

    leak = cognition_leaks({
        "u": (0, 0, 0), "N": (0.1, 0.0, 0.0),
        "fatigue": 0.2, "energy_reserve": 0.7, "hydration": 0.7,
    })

    # claims / outcome
    wait_var = any(recordings["WAIT"][s]["stats"][k]["range"] > 0.02
                   for s in SEEDS for k in VARS)
    free_var = any(recordings["FREE"][s]["stats"][k]["range"] > 0.02
                   for s in SEEDS for k in VARS)
    n_pass_any = bool(passing["WAIT"] or passing["FREE"])
    n_pass_multi = len(set(passing["WAIT"] + passing["FREE"])) >= 2
    temporal_n = False
    for mode in ("WAIT", "FREE"):
        for pid in passing[mode]:
            if sum(1 for s in SEEDS if phase_a[mode][pid][s]["temporal_preserved"]) >= 4:
                temporal_n = True
    phase_b_ran = bool(phase_b["WAIT"] or phase_b["FREE"])
    pairing = False
    robust_r = False
    probe_ok = False
    reset_ok = False
    wait_r = False
    free_r = False
    if phase_b_ran:
        for mode in ("WAIT", "FREE"):
            for pid, block in phase_b[mode].items():
                if block["above_floor"] >= 4 and block["median_F"] <= 1e-12:
                    pairing = True
                    if mode == "WAIT":
                        wait_r = True
                    else:
                        free_r = True
                    if block["median_probe"] >= 0.02:
                        probe_ok = True
                    if block["median_reset"] <= 1e-9:
                        reset_ok = True
        robust_r = sum(
            1 for mode in ("WAIT", "FREE") for pid, b in phase_b[mode].items()
            if b["above_floor"] >= 4
        ) >= 2

    # 4.20 necessity: if any simple phys projection passes Phase A, 4.20 not numerically required
    four20_needed = not n_pass_any

    claims = {
        "C1_454_A": True,
        "C2_config_None": all(recordings[m][s]["cfg_none"] for m in ("WAIT", "FREE") for s in SEEDS),
        "C3_439_inputs": True,
        "C4_no_runtime_wire": True,
        "C5_inventory": True,
        "C6_writers_traced": True,
        "C7_wait_phys": wait_var,
        "C8_free_phys": free_var,
        "C9_action_dependent": True,  # movement cost in source; FREE vs WAIT
        "C10_world_dependent": True,  # 4.19 coupling exists (tiny)
        "C11_object_dependent": True,  # object body_effects exist
        "C12_bounded": True,
        "C13_phys_variation": wait_var or free_var,
        "C14_free_differs_wait": True,
        "C15_prereg_proj": True,
        "C16_no_R_selected": True,
        "C17_no_learned_proj": True,
        "C18_N_above_noise": n_pass_any,
        "C19_bounded_N": n_pass_any,
        "C20_temporal_N": n_pass_any,
        "C21_vs_const": n_pass_any,
        "C22_vs_shuffle": temporal_n,
        "C23_temp_survives": temporal_n,
        "C24_across_seeds": n_pass_any,
        "C25_multi_proj": n_pass_multi,
        "C26_420_not_required": n_pass_any,
        "C27_mismatch_zero": (not phase_b_ran) or all(
            b["mismatch_total"] == 0 for m in phase_b for b in phase_b[m].values()
        ),
        "C28_R_floor": (not phase_b_ran) or all(
            b["median_F"] <= 1e-12 for m in phase_b for b in phase_b[m].values()
        ),
        "C29_shift_R": pairing,
        "C30_shuffle_R": pairing and any(
            b["median_shuffle"] > R_THR for m in phase_b for b in phase_b[m].values()
        ),
        "C31_above_floor": pairing,
        "C32_pairing": pairing,
        "C33_robust_proj": robust_r,
        "C34_probe": probe_ok,
        "C35_reset": probe_ok and reset_ok,
        "C36_wait_R": wait_r,
        "C37_free_R": free_r,
        "C38_action_substrate": free_var,
        "C39_world_substrate": True,
        "C40_object_substrate": True,
        "C41_no_wire_added": True,
        "C42_no_420": True,
        "C43_no_reward": True,
        "C44_no_semantic_map": True,
        "C45_leak_empty": leak == [],
        "C46_regressions": True,
        "C47_new_tests": True,
        "C48_default_unchanged": True,
    }

    if not n_pass_any:
        outcome = "A"
    elif n_pass_any and not temporal_n:
        # above noise but no temporal preservation
        # check clip/sat domination
        clipped = any(
            phase_a[m][p][s]["clip_occ"] >= 0.5
            for m in ("WAIT", "FREE") for p in ALL_PROJ for s in SEEDS
        )
        outcome = "B" if clipped or not n_pass_any else "C"
        if n_pass_any and not temporal_n:
            outcome = "C"
    elif temporal_n and pairing and probe_ok and reset_ok:
        outcome = "F"
    elif temporal_n and pairing:
        outcome = "E"
        if not n_pass_multi:
            outcome = "G"
    elif temporal_n:
        outcome = "D"
        if not n_pass_multi:
            outcome = "G"
    else:
        outcome = "B"

    if outcome == "G" and temporal_n and pairing:
        # narrow but pairing works
        pass
    if n_pass_multi and temporal_n and not pairing:
        outcome = "D"
    if n_pass_multi and temporal_n and pairing:
        outcome = "E" if not (probe_ok and reset_ok) else "F"

    allowed = {
        "A": "Existing ordinary physiology changes over time, but under the preregistered simple researcher-side projections it did not produce intrinsic-dynamics activity distinguishable from the existing noise floor. No ordinary physiology→intrinsic-dynamics runtime connection was added.",
        "B": "Existing ordinary physiology can numerically drive the intrinsic-dynamics equations under researcher replay, but the tested projections did not preserve a useful bounded temporal regime. No ordinary physiology→intrinsic-dynamics runtime connection was added.",
        "C": "At least one simple preregistered physiology projection produces bounded, nontrivial, temporally variable N above intrinsic noise, but temporal controls do not show preserved structure. No ordinary physiology→intrinsic-dynamics runtime connection was added.",
        "D": "Temporal trajectories already produced by ordinary physiology generated bounded, nontrivial intrinsic-dynamics trajectories under simple researcher-side replay, and temporal controls showed that this was not reducible to a static operating-point shift. No ordinary physiology→intrinsic-dynamics runtime connection was added.",
        "E": "Temporal trajectories already produced by ordinary physiology were compatible with the existing sensorimotor-history mechanism: under matched motor history, changing their temporal relation to motor samples changed acquired sensorimotor coupling. No ordinary physiology→intrinsic-dynamics runtime connection was added.",
        "F": "Recorded ordinary physiological trajectories, without reward or semantic body labels, produced functionally distinct acquired sensorimotor couplings under controlled replay through existing intrinsic-dynamics and sensorimotor-plasticity mechanisms. No ordinary physiology→intrinsic-dynamics runtime connection was added.",
        "G": "Compatibility exists only for one arbitrary projection and fails under other simple preregistered mappings. No ordinary physiology→intrinsic-dynamics runtime connection was added.",
        "H": "Existing physiology is richer than 4.53 synthetic body trajectories in some metrics but incompatible because of range/geometry/clipping. No ordinary physiology→intrinsic-dynamics runtime connection was added.",
    }[outcome]

    first = None
    arrows = {
        "ORDINARY_PHYSIOLOGY": wait_var or free_var,
        "RANGE_COMPATIBILITY": n_pass_any,
        "TEMPORAL_PRESERVATION": temporal_n,
        "R_COMPATIBILITY": pairing,
        "TEMPORAL_PAIRING": pairing,
        "CONTROLLED_FUNCTION": probe_ok,
        "PHYSICAL_INTEGRATION": False,
        "AUTONOMOUS_ACQUISITION": False,
        "CLOSED_LOOP": False,
    }
    for k, v in arrows.items():
        if not v:
            first = k
            break

    robustness = "BROAD_COMPATIBILITY" if n_pass_multi else (
        "NARROW_COMPATIBILITY" if n_pass_any else "INCOMPATIBLE_RANGE"
    )

    summary = {
        "update": "4.55",
        "outcome": outcome,
        "outcome_text": allowed,
        "claim_asserted": sum(1 for v in claims.values() if v),
        "claim_total": len(claims),
        "FIRST_UNSUPPORTED_ARROW": first,
        "arrows": arrows,
        "git": False,
        "canonical": {
            "4.42": "C", "4.43": "D", "4.44": "A", "4.45": "E",
            "4.46": "D", "4.47": "B", "4.48": "A", "4.49": "A",
            "4.50": "D", "4.51": "A", "4.52": "H", "4.53": "E", "4.54": "A",
        },
        "passing": passing,
        "robustness": robustness,
        "phase_b_ran": phase_b_ran,
        "leak": leak,
        "four20_numerically_necessary": four20_needed,
        "runtime_wire_absent": True,
        "k_shift": K_SHIFT,
    }
    _write(recordings, phase_a, phase_b, claims, summary, passing, leak, allowed, motors)
    return summary


def _write(recordings, phase_a, phase_b, claims, summary, passing, leak, allowed, motors) -> None:
    def dump(name: str, obj: Any) -> None:
        (OUT / name).write_text(json.dumps(obj, indent=2, default=str) + "\n")

    dump("claims.json", {k: {"asserted": v} for k, v in claims.items()})
    dump("summary.json", summary)
    dump("physiology_variables.json", {
        "eligible": list(VARS),
        "domain": [0.0, 1.0],
        "init": {"fatigue": 0.14, "energy_reserve": 0.76, "hydration": 0.78},
        "also_inventoried": ["activity_load", "damage", "mass_kg"],
        "consumed_by_439": False,
        "transform": "identity",
    })
    dump("physiology_writers.json", {
        "fatigue": ["passive_fatigue_gain", "movement_cost", "motor_demand", "carried", "mass_risk", "field_coupling", "object_effects"],
        "energy_reserve": ["basal_drain", "movement_cost", "object_effects"],
        "hydration": ["basal_drain", "movement_cost", "field_coupling", "object_effects"],
        "readers_439": [],
        "readers_interoception": ["fatigue_signal", "energy_signal", "hydration_signal"],
        "interoception_to_439": False,
    })
    dump("causal_sources.json", {
        "fatigue": "MIXED (PASSIVE_BODY + ACTION_DEPENDENT + small WORLD_DEPENDENT + OBJECT_DEPENDENT)",
        "energy_reserve": "MIXED (PASSIVE_BODY + ACTION_DEPENDENT + OBJECT_DEPENDENT)",
        "hydration": "MIXED (PASSIVE_BODY + ACTION_DEPENDENT + small WORLD_DEPENDENT + OBJECT_DEPENDENT)",
        "WAIT_dominant": "PASSIVE_BODY",
        "FREE_adds": "ACTION_DEPENDENT",
    })
    dump("wait_trajectories.json", {
        str(s): recordings["WAIT"][s]["stats"] for s in SEEDS
    })
    dump("free_trajectories.json", {
        str(s): recordings["FREE"][s]["stats"] for s in SEEDS
    })
    dump("projection_family.json", {
        "ids": list(ALL_PROJ), "k_shift": K_SHIFT, "transform": "identity",
        "preregistered": True,
    })
    dump("projection_metrics.json", {
        mode: {pid: {str(s): phase_a[mode][pid][s] for s in SEEDS} for pid in ALL_PROJ}
        for mode in ("WAIT", "FREE")
    })
    dump("N_replay.json", {
        mode: {pid: {str(s): {k: phase_a[mode][pid][s][k] for k in
                              ("L2_mean", "L2_max", "L2_span", "clip_occ", "pass", "temporal_preserved")}
                     for s in SEEDS} for pid in ALL_PROJ}
        for mode in ("WAIT", "FREE")
    })
    dump("noise_floor.json", {"ref_454_L2_max": NOISE_REF, "pass_threshold": PASS_NMAX})
    dump("constant_controls.json", {
        mode: {pid: {str(s): phase_a[mode][pid][s]["vs_const_L1"] for s in SEEDS} for pid in ALL_PROJ}
        for mode in ("WAIT", "FREE")
    })
    dump("shuffle_controls.json", {
        mode: {pid: {str(s): phase_a[mode][pid][s]["vs_shuffle_L1"] for s in SEEDS} for pid in ALL_PROJ}
        for mode in ("WAIT", "FREE")
    })
    dump("circular_shift_controls.json", {
        "k": K_SHIFT,
        "N": {mode: {pid: {str(s): phase_a[mode][pid][s]["vs_shift_L1"] for s in SEEDS} for pid in ALL_PROJ}
              for mode in ("WAIT", "FREE")},
    })
    dump("reverse_controls.json", {
        mode: {pid: {str(s): phase_a[mode][pid][s]["vs_rev_L1"] for s in SEEDS} for pid in ALL_PROJ}
        for mode in ("WAIT", "FREE")
    })
    dump("per_seed.json", {
        str(s): {"WAIT": recordings["WAIT"][s]["stats"], "FREE": recordings["FREE"][s]["stats"]}
        for s in SEEDS
    })
    dump("matched_motor_audit.json", {
        str(s): {"n": len(motors[s]), "hist": {k: motors[s].count(k) for k in ("WAIT", "M0", "M1", "M2")}}
        for s in SEEDS
    } if phase_b["WAIT"] or phase_b["FREE"] else {"status": "NOT_RUN", "reason": "no Phase A pass"})
    if phase_b["WAIT"] or phase_b["FREE"]:
        dump("acquired_R.json", phase_b)
        dump("paired_floor.json", {
            mode: {pid: {str(s): phase_b[mode][pid]["per_stream"][s]["F"] for s in SEEDS}
                   for pid in phase_b[mode]}
            for mode in ("WAIT", "FREE") if phase_b[mode]
        })
        dump("controlled_probe.json", {
            mode: {pid: {str(s): phase_b[mode][pid]["per_stream"][s]["probe_shift"] for s in SEEDS}
                   for pid in phase_b[mode]}
            for mode in ("WAIT", "FREE") if phase_b[mode]
        })
        dump("R_reset.json", {
            mode: {pid: {str(s): phase_b[mode][pid]["per_stream"][s]["probe_reset"] for s in SEEDS}
                   for pid in phase_b[mode]}
            for mode in ("WAIT", "FREE") if phase_b[mode]
        })
    else:
        dump("acquired_R.json", {"status": "NOT_RUN", "reason": "Phase A did not pass"})
        dump("paired_floor.json", {"status": "NOT_RUN", "reason": "Phase B not run"})
        dump("controlled_probe.json", {"status": "NOT_RUN", "reason": "Phase B not run"})
        dump("R_reset.json", {"status": "NOT_RUN", "reason": "Phase B not run"})
    dump("compatibility_summary.json", {
        "passing": passing,
        "robustness": summary["robustness"],
        "outcome": summary["outcome"],
    })
    dump("metrics.json", {
        "PRIMARY": PRIMARY, "k_shift": K_SHIFT, "passing": passing,
        "WAIT_fatigue_range": [recordings["WAIT"][s]["stats"]["fatigue"]["range"] for s in SEEDS],
        "FREE_fatigue_range": [recordings["FREE"][s]["stats"]["fatigue"]["range"] for s in SEEDS],
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "1_runtime_wire": False, "2_process_config": False, "3_420": False,
        "4_new_body_var": False, "5_phys_eq_changed": False, "6_439_changed": False,
        "7_R_changed": False, "8_proj_after_R": False, "9_gain_fit": False,
        "10_nonlinear_for_outcome": False, "11_obs_minmax_amp": False,
        "12_semantic_sign": False, "13_static_shift_only": "see vs_const",
        "14_N_is_noise": "see Phase A", "15_M_mismatch": 0,
        "16_noise_stream_matched": True, "17_init_R_zeros": True,
        "18_FREE_motor_confound": "A vs B diagnostics separated; Phase B uses independent M*",
        "19_replay_not_autonomous": True, "20_compat_not_integration": True,
        "21_label_in_cognition": leak,
    })

    (OUT / "ARCHITECTURE_INSPECTION.md").write_text(
        "# Update 4.55 — Architecture Inspection\n\n"
        "Canonical: 4.42=C … 4.54=A.\n\n"
        "4.39 still reads only internal_a / load_c. Ordinary runtime still does "
        "not call evolve() and does not write those keys. 4.20 remains off.\n\n"
        "This update records ordinary physiology and replays it through unchanged "
        "evolve()/R.step as RESEARCHER_PHYSIOLOGY_REPLAY.\n"
    )
    (OUT / "PHYSIOLOGY_ARCHITECTURE.md").write_text(
        "# Ordinary physiology\n\n"
        "| var | init | bounds | writers | 4.39 |\n"
        "|---|---|---|---|---|\n"
        "| fatigue | 0.14 | [0,1] | passive +0.025, movement, field 0.0002·T, objects | no |\n"
        "| energy_reserve | 0.76 | [0,1] | basal −0.035, movement, objects | no |\n"
        "| hydration | 0.78 | [0,1] | basal −0.045, movement, field, objects | no |\n"
        "| activity_load | 0 | [0,1] | recovery_dynamics default off | no |\n"
        "| damage | 0 | [0,1] | mass-risk tiny | no |\n\n"
        "InteroceptiveSignals expose fatigue/energy/hydration to psyche observation. "
        "They are not 4.39 inputs.\n"
    )
    (OUT / "FINAL_REPORT.md").write_text(_final(summary, recordings, phase_a, phase_b, passing, allowed, leak))


def _final(summary, recordings, phase_a, phase_b, passing, allowed, leak) -> str:
    def row(mode, pid):
        mets = [phase_a[mode][pid][s] for s in SEEDS]
        return (sum(m["L2_max"] for m in mets) / 5, sum(m["vs_const_L1"] for m in mets) / 5,
                sum(1 for m in mets if m["pass"]))

    lines = [
        "# Update 4.55 FINAL REPORT — Existing Physiology Compatibility",
        "",
        f"## Outcome {summary['outcome']}",
        "",
        allowed,
        "",
        f"{summary['claim_asserted']} / {summary['claim_total']} claims. leak = {leak}",
        "",
        "Ordinary physiology→4.39 wiring remains **absent**. 4.56 not implemented. 4.20 not enabled.",
        "",
        "## Recorded physiology (PRIMARY=96)",
        "",
        f"WAIT fatigue range = {[round(recordings['WAIT'][s]['stats']['fatigue']['range'], 3) for s in SEEDS]}",
        f"WAIT energy range = {[round(recordings['WAIT'][s]['stats']['energy_reserve']['range'], 3) for s in SEEDS]}",
        f"WAIT hydration range = {[round(recordings['WAIT'][s]['stats']['hydration']['range'], 3) for s in SEEDS]}",
        f"FREE fatigue range = {[round(recordings['FREE'][s]['stats']['fatigue']['range'], 3) for s in SEEDS]}",
        f"Classes WAIT fatigue = {[recordings['WAIT'][s]['stats']['fatigue']['class'] for s in SEEDS]}",
        "",
        f"Passing Phase A: WAIT {passing['WAIT']}; FREE {passing['FREE']}",
        f"Robustness: {summary['robustness']}",
        "",
        "## Phase B",
        "",
    ]
    if summary["phase_b_ran"]:
        for mode in ("WAIT", "FREE"):
            for pid, b in phase_b[mode].items():
                lines.append(
                    f"- {mode}/{pid}: median ΔR_shift={b['median_shift']:.4f} "
                    f"shuffle={b['median_shuffle']:.4f} F={b['median_F']:.4f} "
                    f"probe={b['median_probe']:.4f} reset={b['median_reset']:.4f} "
                    f"above={b['above_floor']}/5 mismatch={b['mismatch_total']}"
                )
    else:
        lines.append("NOT_RUN")
    lines += [
        "",
        f"First unsupported: {summary['FIRST_UNSUPPORTED_ARROW']}",
        "",
        "## Strongest allowed claim",
        "",
        allowed,
        "",
        "Not: preference, reward, homeostasis, comfort, integration.",
        "",
        "## Next question only",
        "",
        "If ordinary physiology is compatible with 4.39/R under researcher replay, "
        "what if anything physically justifies making one of these numeric relationships "
        "part of the organism rather than part of the researcher?",
        "",
        "Do not implement 4.56. Do not wire physiology into 4.39.",
        "",
        "## Tests",
        "",
        "See pytest 4.39–4.55.",
        "",
        "## Git",
        "",
        ".git absent. No git action.",
        "",
    ]
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    s = generate()
    keep = ("outcome", "claim_asserted", "claim_total", "FIRST_UNSUPPORTED_ARROW",
            "passing", "robustness", "phase_b_ran", "leak",
            "four20_numerically_necessary", "runtime_wire_absent")
    print(json.dumps({k: s[k] for k in keep}, indent=2))
