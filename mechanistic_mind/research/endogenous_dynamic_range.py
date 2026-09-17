"""Update 4.48 — researcher-side survey of existing N operating range.

No architecture change. Probe N is calibration only. 4.45 unused.
"""
from __future__ import annotations

import json
import math
import re
from typing import Any

import numpy as np

from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState, step as w_step
from mechanistic_mind.body.acquired_sensorimotor_coupling import AcquiredCouplingState
from mechanistic_mind.body.endogenous_signaling import EndogenousSignalState, evolve_signal
from mechanistic_mind.body.sensorimotor_dynamics import (
    CHANNELS, COUPLING, DECAY, NOISE_SCALE,
    SensorimotorState, evolve, motor_distribution,
)
from mechanistic_mind.research import acquired_internal_dynamics as aid
from mechanistic_mind.research import acquired_sensorimotor_coupling as smc
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research import endogenous_motor_access as ema
from mechanistic_mind.research import intrinsic_sensorimotor_dynamics as ism

PROBE_N = (0.70, 0.0, 0.0)
PROBE_DP = 0.06810829898844023
CANON_L2 = 0.0915
SUBST_L2 = 0.183
HIST_THR = 0.02
NAT_STEPS = 96
CTRL_STEPS = 32
FORBIDDEN = bcd.FORBIDDEN + (
    "PREFERRED", "URGENCY", "AROUSAL", "SALIENCE", "BOOST", "GAIN_UP",
    "BIOGRAPHY", "SELF", "IMPORTANCE",
)

BODIES = {
    "MID": (0.50, 0.50),
    "B447": (0.55, 0.45),
    "L444": (0.25, 0.70),
    "H444": (0.80, 0.25),
    "A439": (0.20, 0.80),
    "B439": (0.80, 0.20),
    "E439": (0.80, 0.30),
}


def _body(pair) -> dict[str, float]:
    return ism.body(pair[0], pair[1])


def _terms(N: SensorimotorState, body: dict, I, sensory, rv: float) -> dict[str, Any]:
    inputs = (body["internal_a"] - 0.5, body["load_c"] - 0.5)
    body_term = tuple(sum(COUPLING[i][j] * inputs[j] for j in range(2)) for i in range(3))
    I_term = tuple(0.16 * float(I[i]) for i in range(3)) if I is not None else (0.0, 0.0, 0.0)
    sensory_term = tuple(0.03 * (sensory[i % len(sensory)] - 0.5) for i in range(3))
    persist = tuple(0.08 * N.previous_output[i] for i in range(3))
    decayed = tuple(DECAY * N.channels[i] for i in range(3))
    noise = (rv - 0.5) * 2.0 * NOISE_SCALE
    return {
        "body_term": body_term, "I_term": I_term, "sensory_term": sensory_term,
        "persist": persist, "decayed": decayed, "noise": noise,
    }


def _tick(q, I, N, *, body, u, I_pert, sensory, rv, use_q, use_I, body_on):
    if use_q:
        q = w_step(q, physical_input=u, plasticity=False)
        I = evolve_signal(I, perturbation=q.q)
    elif I_pert is not None:
        I = evolve_signal(I, perturbation=I_pert)
    else:
        I = evolve_signal(I, perturbation=(0.0, 0.0, 0.0))
    endo = I.channels if use_I else ()
    N = evolve(N, body=body, sensory=sensory, random_value=rv,
               endogenous=endo, endogenous_coupling=use_I, body_coupling=body_on)
    return q, I, N


def run_episode(*, name: str, klass: str, seed: int, steps: int,
                body_pair, W=None, pulse_u=None, pulse_I=None,
                use_q=False, use_I=False, body_on=True,
                start_q=None) -> list[dict[str, Any]]:
    q = start_q or AdaptiveInternalState(weights=(W or AdaptiveInternalState().weights))
    if start_q is None and W is not None:
        q = AdaptiveInternalState(weights=W)
    I = EndogenousSignalState()
    N = SensorimotorState()
    body = _body(body_pair)
    sensory = (0.5, 0.5)
    rows = []
    for t in range(steps):
        rv = ((seed * 29 + t * 13) % 101) / 100.0
        u = pulse_u if (t == 0 and pulse_u is not None) else (0.0, 0.0, 0.0)
        ip = pulse_I if (t == 0 and pulse_I is not None and not use_q) else None
        q, I, N = _tick(q, I, N, body=body, u=u, I_pert=ip, sensory=sensory, rv=rv,
                        use_q=use_q, use_I=use_I or use_q, body_on=body_on)
        terms = _terms(N, body, I.channels if (use_I or use_q) else None, sensory, rv)
        rows.append({
            "t": t, "name": name, "klass": klass,
            "q": q.q if use_q else (0.0, 0.0, 0.0),
            "I": I.channels if (use_I or use_q) else (0.0, 0.0, 0.0),
            "N": N.channels, "body": body_pair,
            **terms,
        })
    return rows


def leftover_q(*, seed: int, steps: int = NAT_STEPS) -> list[dict[str, Any]]:
    acquired = aid.acquire([(aid.X, aid.Y)], trials=36, seed=seed)
    return run_episode(name="N_LEFTOVER_Q", klass="NATURAL_RUNTIME", seed=seed,
                       steps=steps, body_pair=BODIES["MID"], W=acquired.weights,
                       use_q=True, start_q=AdaptiveInternalState(q=acquired.q, weights=acquired.weights))


def grid_for_seed(seed: int) -> dict[str, list[dict[str, Any]]]:
    out = {}
    out["N_BASE_MID"] = run_episode(name="N_BASE_MID", klass="NATURAL_RUNTIME", seed=seed,
                                    steps=NAT_STEPS, body_pair=BODIES["MID"])
    out["N_BASE_447"] = run_episode(name="N_BASE_447", klass="NATURAL_RUNTIME", seed=seed,
                                    steps=NAT_STEPS, body_pair=BODIES["B447"])
    out["N_LEFTOVER_Q"] = leftover_q(seed=seed)
    W = aid.acquire([(aid.X, aid.Y)], trials=36, seed=seed).weights
    for key, pair in (("C_BODY_444L", BODIES["L444"]), ("C_BODY_444H", BODIES["H444"]),
                      ("C_BODY_439A", BODIES["A439"]), ("C_BODY_439B", BODIES["B439"]),
                      ("C_BODY_439E", BODIES["E439"])):
        out[key] = run_episode(name=key, klass="EXISTING_CONTROLLED_CONDITION", seed=seed,
                               steps=CTRL_STEPS, body_pair=pair)
    out["C_I_PULSE"] = run_episode(name="C_I_PULSE", klass="EXISTING_CONTROLLED_CONDITION",
                                   seed=seed, steps=CTRL_STEPS, body_pair=BODIES["MID"],
                                   pulse_I=aid.X, use_I=True)
    out["C_Q_PRESENT"] = run_episode(name="C_Q_PRESENT", klass="EXISTING_CONTROLLED_CONDITION",
                                     seed=seed, steps=CTRL_STEPS, body_pair=BODIES["MID"],
                                     W=W, pulse_u=aid.X, use_q=True)
    out["C_QI_BODY"] = run_episode(name="C_QI_BODY", klass="EXISTING_CONTROLLED_CONDITION",
                                   seed=seed, steps=CTRL_STEPS, body_pair=BODIES["H444"],
                                   W=W, pulse_u=aid.X, use_q=True)
    return out


def probe_sample() -> dict[str, Any]:
    return {"t": 0, "name": "P_N0", "klass": "PROBE_ONLY", "q": (0.0, 0.0, 0.0),
            "I": (0.0, 0.0, 0.0), "N": PROBE_N, "body": None}


def l1(v): return float(sum(abs(float(x)) for x in v))
def l2(v): return float(math.sqrt(sum(float(x) * float(x) for x in v)))
def linf(v): return float(max(abs(float(x)) for x in v))


def quantiles(xs: list[float]) -> dict[str, float]:
    if not xs:
        return {k: 0.0 for k in ("median", "p75", "p90", "p95", "p99", "max")}
    a = np.sort(np.array(xs, dtype=float))
    def q(p): return float(np.quantile(a, p))
    return {"median": q(0.50), "p75": q(0.75), "p90": q(0.90), "p95": q(0.95),
            "p99": q(0.99), "max": float(a[-1])}


def run_lengths(flags: list[bool]) -> list[int]:
    out, n = [], 0
    for f in flags:
        if f:
            n += 1
        elif n:
            out.append(n); n = 0
    if n:
        out.append(n)
    return out


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]
