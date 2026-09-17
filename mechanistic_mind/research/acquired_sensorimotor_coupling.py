"""Update 4.46 — acquired N–M coupling from local temporal co-history.

Researcher labels (H_A, pairing) are not cognition-accessible.
"""
from __future__ import annotations

import json
import random
import re
from typing import Any

from mechanistic_mind.body.acquired_sensorimotor_coupling import (
    AcquiredCouplingState, apply_drive, l1, representation, reset_transient,
    reset_weights, row_col_norms, step,
)
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve, motor_distribution
from mechanistic_mind.research import body_coupled_development as bcd

AMP_N = 0.70
AMP_M = 1.00
TRIALS = 36
GAP = 2
REST_BEFORE = 3
REST_AFTER = 4
TAIL = 8
ZERO3 = (0.0, 0.0, 0.0)
MAP_A = (0, 1, 2)
MAP_B = (2, 0, 1)
FORBIDDEN = bcd.FORBIDDEN + (
    "PREFERRED", "TARGET_ACTION", "DESIRED_ACTION", "POLICY_TARGET",
    "CREDIT", "SELF", "BIOGRAPHY", "IMPORTANT_CHANNEL", "USEFUL_MOTOR",
    "DISTAL_B", "PREFERRED_ACTION",
)


def n_pulse(i: int | None) -> tuple[float, float, float]:
    if i is None:
        return ZERO3
    v = [0.0, 0.0, 0.0]
    v[int(i)] = AMP_N
    return tuple(v)


def m_pulse(j: int | None) -> tuple[float, float, float]:
    if j is None:
        return ZERO3
    v = [0.0, 0.0, 0.0]
    v[int(j)] = AMP_M
    return tuple(v)


def pair_list(history: str, *, seed: int) -> list[tuple[int | None, int | None]]:
    rng = random.Random(seed)
    ns = [0, 1, 2] * (TRIALS // 3)
    if history == "H_A":
        return [(i, MAP_A[i]) for i in ns]
    if history == "H_B":
        return [(i, MAP_B[i]) for i in ns]
    if history == "H_SHUFFLED":
        ms = [MAP_A[i] for i in ns]
        rng.shuffle(ms)
        return list(zip(ns, ms))
    if history == "H_N_ONLY":
        return [(i, None) for i in ns]
    if history == "H_M_ONLY":
        return [(None, MAP_A[i]) for i in ns]
    if history == "H_NAIVE":
        return [(None, None)] * TRIALS
    if history == "H_PARTIAL":
        return [(i, MAP_A[i] if i != 2 else None) for i in ns]
    raise ValueError(history)


def _rest(s: AcquiredCouplingState, n: int, *, plasticity: bool, eligibility: bool) -> AcquiredCouplingState:
    for _ in range(n):
        s = step(s, n=ZERO3, m=ZERO3, plasticity=plasticity, eligibility=eligibility)
    return s


def develop(history: str, *, seed: int = 0, plasticity: bool = True,
            eligibility: bool = True,
            initial: AcquiredCouplingState | None = None,
            ) -> tuple[AcquiredCouplingState, list, dict[str, Any]]:
    s = initial or AcquiredCouplingState()
    pairs = pair_list(history, seed=seed)
    raw = []
    n_counts = [0, 0, 0]
    m_counts = [0, 0, 0]
    n_sum = [0.0, 0.0, 0.0]
    m_sum = [0.0, 0.0, 0.0]
    co = [[0, 0, 0] for _ in range(3)]
    for ni, mj in pairs:
        s = _rest(s, REST_BEFORE, plasticity=plasticity, eligibility=eligibility)
        nv = n_pulse(ni)
        s = step(s, n=nv, m=ZERO3, plasticity=plasticity, eligibility=eligibility)
        s = _rest(s, GAP, plasticity=plasticity, eligibility=eligibility)
        mv = m_pulse(mj)
        s = step(s, n=ZERO3, m=mv, plasticity=plasticity, eligibility=eligibility)
        s = _rest(s, REST_AFTER, plasticity=plasticity, eligibility=eligibility)
        raw.append({"n": ni, "m": mj})
        if ni is not None:
            n_counts[ni] += 1
            n_sum[ni] += AMP_N
        if mj is not None:
            m_counts[mj] += 1
            m_sum[mj] += AMP_M
        if ni is not None and mj is not None:
            co[mj][ni] += 1
    s = _rest(s, TAIL, plasticity=plasticity, eligibility=eligibility)
    stats = {
        "mode": history, "n": len(pairs),
        "n_counts": n_counts, "m_counts": m_counts,
        "n_mean": [x / len(pairs) for x in n_sum],
        "m_mean": [x / len(pairs) for x in m_sum],
        "co_occurrence": co,
        "duration": len(pairs),
    }
    return s, raw, stats


def probe_n(state: AcquiredCouplingState, channel: int, *,
            use_acquired: bool = True, isolate_acquired: bool = False,
            reset: bool = True) -> dict[str, Any]:
    s = reset_transient(state) if reset else state
    N = SensorimotorState(channels=n_pulse(channel))
    motor = motor_distribution(N, acquired=s.weights, use_acquired=use_acquired,
                               isolate_acquired=isolate_acquired)
    return {
        "N": N.channels, "preact": motor["preact"], "extra": motor["acquired_extra"],
        "motor": motor, "probs": motor["probs"],
        "ordinary_state_value": 0.0, "prediction_runtime_contribution": 0.0,
        "weights": s.weights,
    }


def endogenous_n(*, seed: int, steps: int = 8) -> SensorimotorState:
    N = SensorimotorState()
    body = {"internal_a": 0.55, "load_c": 0.45}
    for t in range(steps):
        N = evolve(N, body=body, sensory=(0.5, 0.5),
                   random_value=((seed * 29 + t * 13) % 101) / 100.0)
    return N


def probe_endogenous(state: AcquiredCouplingState, N: SensorimotorState, *,
                     use_acquired: bool = True) -> dict[str, Any]:
    s = reset_transient(state)
    motor = motor_distribution(N, acquired=s.weights, use_acquired=use_acquired)
    return {"N": N.channels, "preact": motor["preact"], "motor": motor, "probs": motor["probs"]}


def prob_l1(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    return sum(abs(a.get(k, 0.0) - b.get(k, 0.0)) for k in keys)


def motor_jacobian(n: tuple[float, ...], weights, *, use_acquired: bool = True,
                   eps: float = 1e-4) -> list[list[float]]:
    def p_of(ch):
        d = motor_distribution(SensorimotorState(channels=ch), acquired=weights, use_acquired=use_acquired)
        return [d["probs"][f"M{j}"] for j in range(3)]
    base = p_of(n)
    J = []
    for i in range(3):
        ch = list(n)
        ch[i] += eps
        pert = p_of(tuple(ch))
        J.append([(pert[j] - base[j]) / eps for j in range(3)])
    return J


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def marginals_match(sa: dict, sb: dict) -> bool:
    return sa["n_counts"] == sb["n_counts"] and sa["m_counts"] == sb["m_counts"]
