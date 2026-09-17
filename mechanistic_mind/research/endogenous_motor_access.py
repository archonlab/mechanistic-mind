"""Update 4.47 — researcher-side diagnostics of 4.46 endogenous vs probe motor access.

Does not change R, gain, readout, W, or q/I/N. Labels are not cognition-accessible.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

import numpy as np

from mechanistic_mind.body.acquired_sensorimotor_coupling import AcquiredCouplingState, reset_transient
from mechanistic_mind.body.endogenous_signaling import EndogenousSignalState, evolve_signal
from mechanistic_mind.body.sensorimotor_dynamics import (
    BASE_NON_WAIT, CHANNELS, COUPLING, DECAY, NOISE_SCALE,
    SensorimotorState, evolve, motor_distribution, sample_motor,
)
from mechanistic_mind.research import acquired_sensorimotor_coupling as smc
from mechanistic_mind.research import body_coupled_development as bcd

SWEEP = (0.25, 0.50, 0.75, 1.00, 1.25, 1.50)
JAC_EPS = 1e-4
PATH_TOL = 1e-12
SV_CUT = 0.05
HIST_ENDO_THR = 0.02
FORBIDDEN = bcd.FORBIDDEN + (
    "PREFERRED", "TARGET_ACTION", "DESIRED_ACTION", "BIOGRAPHY", "SELF",
    "IMPORTANT_CHANNEL", "USEFUL_CHANNEL", "BOOST", "GAIN_FOR_ENDOGENOUS",
    "ENDOGENOUS_BONUS",
)


def l1(v) -> float:
    return float(sum(abs(float(x)) for x in v))


def l2(v) -> float:
    return float(math.sqrt(sum(float(x) * float(x) for x in v)))


def unit(v) -> tuple[float, ...]:
    n = l2(v)
    if n < 1e-15:
        return tuple(0.0 for _ in v)
    return tuple(float(x) / n for x in v)


def scale_to(v, norm: float) -> tuple[float, ...]:
    u = unit(v)
    return tuple(x * norm for x in u)


def cosine(a, b) -> float:
    na, nb = l2(a), l2(b)
    if na < 1e-15 or nb < 1e-15:
        return 0.0
    return float(sum(float(x) * float(y) for x, y in zip(a, b)) / (na * nb))


def matvec(R, n) -> tuple[float, ...]:
    return tuple(sum(R[j][i] * n[i] for i in range(3)) for j in range(3))


def sub(A, B):
    return tuple(tuple(A[j][i] - B[j][i] for i in range(3)) for j in range(3))


def apply_motor(n, R, *, isolate: bool = False, use_acquired: bool = True) -> dict[str, Any]:
    st = SensorimotorState(channels=tuple(float(x) for x in n))
    m = motor_distribution(st, acquired=R, use_acquired=use_acquired, isolate_acquired=isolate)
    extra = m["acquired_extra"]
    logits = m["preact"]
    return {
        "N": tuple(float(x) for x in n),
        "extra": extra,
        "preact": m["preact"],
        "logits": logits,
        "mag": m["motor_magnitude"],
        "non_wait": m["non_wait_probability"],
        "probs": m["probs"],
        "ordinary_state_value": 0.0,
    }


def capture_endogenous_traj(seed: int, steps: int = 8) -> list[dict[str, Any]]:
    """Replay 4.46 endogenous_n, recording researcher-side evolve terms."""
    body = {"internal_a": 0.55, "load_c": 0.45}
    sensory = (0.5, 0.5)
    N = SensorimotorState()
    rows = []
    for t in range(steps):
        rv = ((seed * 29 + t * 13) % 101) / 100.0
        inputs = (body["internal_a"] - 0.5, body["load_c"] - 0.5)
        noise = (rv - 0.5) * 2.0 * NOISE_SCALE
        body_term = tuple(sum(COUPLING[i][j] * inputs[j] for j in range(2)) for i in range(3))
        sensory_term = tuple(0.03 * (sensory[i % 2] - 0.5) for i in range(3))
        endo_term = (0.0, 0.0, 0.0)
        N = evolve(N, body=body, sensory=sensory, random_value=rv)
        rows.append({
            "t": t, "q": (0.0, 0.0, 0.0), "I": (0.0, 0.0, 0.0),
            "N": N.channels, "body_term": body_term, "I_term": endo_term,
            "sensory_term": sensory_term, "noise_scale": noise,
            "previous": N.previous_output,
        })
    return rows


def capture_IN_traj(seed: int, steps: int = 8) -> list[dict[str, Any]]:
    """Secondary 4.40-style I→N. Not the 4.46 C28 path."""
    I = EndogenousSignalState()
    I = evolve_signal(I, perturbation=(0.25, 0.10, 0.05))
    body = {"internal_a": 0.55, "load_c": 0.45}
    N = SensorimotorState()
    rows = []
    for t in range(steps):
        rv = ((seed * 31 + t * 17) % 101) / 100.0
        I = evolve_signal(I, perturbation=(0.0, 0.0, 0.0))
        N = evolve(N, body=body, sensory=(0.5, 0.5), random_value=rv,
                   endogenous=I.channels, endogenous_coupling=True)
        rows.append({"t": t, "q": (0.0, 0.0, 0.0), "I": I.channels, "N": N.channels})
    return rows


def svd_delta(dR):
    U, S, Vt = np.linalg.svd(np.array(dR, dtype=float))
    return {
        "U": U.tolist(), "S": S.tolist(), "Vt": Vt.tolist(),
        "rank": int(sum(s > SV_CUT for s in S)),
        "max_sv": float(S[0]) if len(S) else 0.0,
    }


def subspace_energy(n, Vt, S) -> float:
    nrm2 = l2(n) ** 2
    if nrm2 < 1e-18:
        return 0.0
    proj = np.array(Vt) @ np.array(n, dtype=float)
    e = 0.0
    for i, s in enumerate(S):
        if s > SV_CUT:
            e += float(proj[i] ** 2)
    return e / nrm2


def jacobian(n, R, eps: float = JAC_EPS):
    return smc.motor_jacobian(tuple(n), R, use_acquired=True, eps=eps)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]
