"""Update 4.45 — joint world/body temporal structure. Unchanged 4.41 rule. Researcher 'biography' is not a runtime label."""
from __future__ import annotations

import json
import random
import re
from typing import Any

from mechanistic_mind.body.adaptive_internal_coupling import (
    AdaptiveInternalState, ablate_weights, representation, step,
)
from mechanistic_mind.body.endogenous_signaling import EndogenousSignalState, evolve_signal
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve, motor_distribution
from mechanistic_mind.research import body_coupled_development as bcd

LOW, MID, HIGH = 0.25, 0.50, 0.75
XA_GAP = 2
TRIALS = 36
PAIRS_A = ((LOW, LOW), (MID, MID), (HIGH, HIGH))
PAIRS_B = ((LOW, HIGH), (MID, MID), (HIGH, LOW))
ZERO = (0.0, 0.0, 0.0)
FORBIDDEN = bcd.FORBIDDEN + (
    "SELF", "ME", "OLD_SELF", "BIOGRAPHY", "AUTOBIOGRAPHICAL", "IDENTITY",
    "BODY_OWNERSHIP", "CONTEXT", "VALENCE", "DESIRED_STATE", "WORLD_CHANGED",
    "BODY_CHANGED", "REMEMBER_SELF", "NOVELTY_VALUE",
)


def world_u(x: float) -> tuple[float, float, float]:
    return (float(x), 0.0, 0.0)


def body_u(b: float) -> tuple[float, float, float]:
    return (0.0, float(b), 0.0)


def _rest(s: AdaptiveInternalState, n: int, plasticity: bool) -> AdaptiveInternalState:
    for _ in range(n):
        s = step(s, physical_input=ZERO, plasticity=plasticity)
    return s


def _pair_events(x: float, b: float, *, world: bool, body: bool) -> list[tuple[float, ...]]:
    ev = []
    ev.append(world_u(x) if world else ZERO)
    ev.extend([ZERO] * XA_GAP)
    ev.append(body_u(b) if body else ZERO)
    return ev


def pair_list(history: str, *, seed: int) -> list[tuple[float, float]]:
    rng = random.Random(seed)
    base = list(PAIRS_A) * (TRIALS // 3)
    if history == "H_COUPLED_A":
        return base
    if history == "H_COUPLED_B":
        return list(PAIRS_B) * (TRIALS // 3)
    if history == "H_SHUFFLED":
        xs = [p[0] for p in base]
        bs = [p[1] for p in base]
        rng.shuffle(bs)
        return list(zip(xs, bs))
    if history == "H_WORLD_ONLY":
        return base
    if history == "H_BODY_ONLY":
        return base
    if history == "H_NAIVE":
        return [(0.0, 0.0)] * TRIALS
    if history == "H_DESC":
        xs = [LOW, MID, HIGH] * (TRIALS // 3)
        bs = [HIGH, MID, LOW] * (TRIALS // 3)
        return list(zip(xs, bs))
    if history == "H_ASC":
        xs = [LOW, MID, HIGH] * (TRIALS // 3)
        bs = [LOW, MID, HIGH] * (TRIALS // 3)
        return list(zip(xs, bs))
    if history == "H_STABLE":
        return [(MID, MID)] * TRIALS
    raise ValueError(history)


def develop(history: str, *, seed: int = 0, plasticity: bool = True,
            initial: AdaptiveInternalState | None = None,
            joint_world: bool | None = None, joint_body: bool | None = None,
            ) -> tuple[AdaptiveInternalState, list, dict[str, Any]]:
    use_w = True if joint_world is None else joint_world
    use_b = True if joint_body is None else joint_body
    if history == "H_WORLD_ONLY":
        use_b = False
        use_w = True
    if history == "H_BODY_ONLY":
        use_w = False
        use_b = True
    if history == "H_NAIVE":
        use_w = use_b = False
    s = initial or AdaptiveInternalState()
    pairs = pair_list(history, seed=seed)
    raw = []
    xs, bs = [], []
    for x, b in pairs:
        s = _rest(s, 3, plasticity)
        for u in _pair_events(x, b, world=use_w, body=use_b):
            s = step(s, physical_input=u, plasticity=plasticity)
        raw.append({"x": x, "b": b})
        xs.append(x)
        bs.append(b)
        s = _rest(s, 4, plasticity)
    s = _rest(s, 8, plasticity)
    stats = {
        "mode": history, "n": len(pairs),
        "x_counts": {str(v): xs.count(v) for v in (LOW, MID, HIGH, 0.0)},
        "b_counts": {str(v): bs.count(v) for v in (LOW, MID, HIGH, 0.0)},
        "x_mean": sum(xs) / len(xs), "b_mean": sum(bs) / len(bs),
        "joint_world": use_w, "joint_body": use_b,
    }
    return s, raw, stats


def probe(state: AdaptiveInternalState, *, seed: int, x: float = HIGH, b: float | None = None,
          reset_transient: bool = True, coupling_ablation: bool = False,
          I_to_N: bool = True, body_coupling: bool = True,
          n_steps: int = 8) -> dict[str, Any]:
    s = AdaptiveInternalState(weights=state.weights) if reset_transient else state
    if coupling_ablation:
        s = ablate_weights(s)
    I = EndogenousSignalState()
    N = SensorimotorState()
    body = {"internal_a": float(b if b is not None else MID), "load_c": 0.45}
    traj = []
    for t in range(n_steps):
        if t == 0:
            u = world_u(x)
        elif t == 1 + XA_GAP and b is not None:
            u = body_u(b)
        else:
            u = ZERO
        s = step(s, physical_input=u, plasticity=False)
        I = evolve_signal(I, perturbation=s.q)
        N = evolve(N, body=body, sensory=(0.5, 0.5),
                   random_value=((seed * 29 + t * 13) % 101) / 100.0,
                   endogenous=I.channels, endogenous_coupling=I_to_N,
                   body_coupling=body_coupling)
        traj.append({"q": s.q, "I": I.channels, "N": N.channels})
    motor = motor_distribution(N)
    return {
        "q": s.q, "I": I.to_dict(), "N": N.to_dict(), "motor": motor,
        "p_A": float(motor["probs"]["M1"]), "trajectory": traj,
        "ordinary_state_value": 0.0, "prediction_runtime_contribution": 0.0,
        "weights": s.weights, "representation": representation(s),
    }


def weight_l1(a: AdaptiveInternalState, b: AdaptiveInternalState) -> float:
    return bcd.weight_l1(a, b)


def traj_l1(p, q, key="q") -> float:
    return bcd.l1_traj(p["trajectory"], q["trajectory"], key)


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def marginals_match(sa: dict, sb: dict) -> bool:
    return sa["x_counts"] == sb["x_counts"] and sa["b_counts"] == sb["b_counts"]
