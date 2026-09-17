"""Update 4.42 body-coupled development probes — history→W→q→I→N→motor→A→future B.

No reward, setpoint, OSV-driven action, or X→A supervision. Local 4.41 plasticity only.
"""
from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any

from mechanistic_mind.body.adaptive_internal_coupling import (
    AdaptiveInternalState,
    ablate_weights,
    representation,
    step,
)
from mechanistic_mind.body.endogenous_signaling import EndogenousSignalState, evolve_signal
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve, motor_distribution, sample_motor

# Distinct numeric patterns (channel 0 precursor, channel 1 interaction, channel 2 distal body).
X = (0.70, 0.0, 0.0)
A_PAT = (0.0, 0.70, 0.0)
BODY_B1 = (0.0, 0.0, -0.55)
BODY_B2 = (0.0, 0.0, 0.55)
BODY_B3 = (0.0, -0.55, 0.15)
Y_WRONG = (-0.70, 0.0, 0.0)
ZERO = (0.0, 0.0, 0.0)

FUTURE_HORIZON = 12
PROBE_STEPS = 8
DISTAL_DELAY = 3
INTERACT_ACTION = "M1"  # A_PAT is channel 1; softmax of N maps that channel to M1

FORBIDDEN = (
    "HUNGER", "FOOD", "EAT", "THIRST", "PAIN", "PLEASURE", "FEAR", "ANXIETY",
    "WANT", "NEED", "DESIRE", "DRIVE", "MOTIVATION", "GOAL", "INTENTION",
    "REWARD", "PUNISHMENT", "GOOD", "BAD", "VALUE", "UTILITY", "SURVIVAL",
    "SELF_PRESERVATION", "HOMEOSTASIS", "SETPOINT", "CURIOSITY", "EXPLORATION",
    "NOVELTY", "INTEREST", "ATTENTION", "SALIENCE", "IMPORTANCE", "PREPARATION",
    "EXPECTATION", "BENEFICIAL", "HARMFUL", "SEEK", "AVOID", "SUCCESS", "FAILURE",
)


def architecture_inspection() -> dict[str, Any]:
    path = __import__("pathlib").Path("results/update442_body_coupled_regulation/architecture_inspection.json")
    if path.exists():
        return json.loads(path.read_text())
    return {"status": "MISSING"}


def initial_body(*, internal_a: float = 0.55, load_c: float = 0.45) -> dict[str, float]:
    return {"internal_a": float(internal_a), "load_c": float(load_c)}


def autonomous_drift(body: dict[str, float]) -> dict[str, float]:
    """Continuing physical dynamics under WAIT or any motor. No interaction semantics."""
    a = max(0.0, min(1.0, float(body["internal_a"]) - 0.018))
    c = max(0.0, min(1.0, float(body["load_c"]) + 0.016))
    return {"internal_a": a, "load_c": c}


def apply_distal_consequence(body: dict[str, float], consequence: str = "B2") -> dict[str, float]:
    """Delayed physical consequence of successful A. No GOOD/BAD encoding."""
    a = float(body["internal_a"])
    c = float(body["load_c"])
    if consequence == "B2":
        a = max(0.0, min(1.0, a + 0.085))
        c = max(0.0, min(1.0, c - 0.070))
    elif consequence == "B3":
        a = max(0.0, min(1.0, a - 0.085))
        c = max(0.0, min(1.0, c + 0.070))
    return {"internal_a": a, "load_c": c}


def evolve_body(body: dict[str, float], *, interacted: bool = False,
                consequence: str = "B2") -> dict[str, float]:
    """One developmental-tick update. Immediate = drift. Distal applied same tick only for bookkeeping of forced episodes."""
    out = autonomous_drift(body)
    if interacted and consequence in {"B2", "B3"}:
        out = apply_distal_consequence(out, consequence)
    return out


def immediate_vs_distal_control(body: dict[str, float] | None = None) -> dict[str, Any]:
    """C3: immediate body after A vs WAIT matched; distal after delay differs."""
    b0 = dict(body or initial_body())
    imm_wait = autonomous_drift(dict(b0))
    imm_A = autonomous_drift(dict(b0))
    late_no = dict(b0)
    late_A = dict(b0)
    for i in range(DISTAL_DELAY + 1):
        late_no = autonomous_drift(late_no)
        late_A = autonomous_drift(late_A)
        if i == DISTAL_DELAY:
            late_A = apply_distal_consequence(late_A, "B2")
    return {
        "immediate_l1": body_l1(imm_wait, imm_A),
        "distal_l1": body_l1(late_A, late_no),
        "matched_immediate": body_l1(imm_wait, imm_A) < 1e-12,
        "distal_differs": body_l1(late_A, late_no) > 0.05,
    }


def body_l1(a: dict[str, float], b: dict[str, float]) -> float:
    return abs(a["internal_a"] - b["internal_a"]) + abs(a["load_c"] - b["load_c"])


def _rest(state: AdaptiveInternalState, n: int = 6, plasticity: bool = True) -> AdaptiveInternalState:
    for _ in range(n):
        state = step(state, physical_input=ZERO, plasticity=plasticity)
    return state


def _seq(state: AdaptiveInternalState, events: list[tuple[float, ...]], *, plasticity: bool) -> AdaptiveInternalState:
    state = _rest(state, 4, plasticity)
    for i, pat in enumerate(events):
        state = step(state, physical_input=pat, plasticity=plasticity)
        if i < len(events) - 1:
            state = step(state, physical_input=ZERO, plasticity=plasticity)
            state = step(state, physical_input=ZERO, plasticity=plasticity)
    return _rest(state, 6, plasticity)


def develop(
    history: str,
    *,
    trials: int = 36,
    seed: int = 0,
    plasticity: bool = True,
    initial: AdaptiveInternalState | None = None,
    consequence: str = "B2",
) -> tuple[AdaptiveInternalState, list[dict[str, Any]], dict[str, Any]]:
    """Externally supplied developmental episodes. Agent does not choose A."""
    import random
    rng = random.Random(seed)
    state = initial or AdaptiveInternalState()
    raw: list[dict[str, Any]] = []
    body = initial_body()
    stats = {"forced_A": 0, "X_count": 0, "body_transitions": 0, "mode": history}
    use_plasticity = plasticity

    for t in range(trials):
        if history == "H1":
            events = [X, A_PAT, BODY_B2 if consequence == "B2" else BODY_B3]
            body = evolve_body(body, interacted=True, consequence=consequence)
            stats["forced_A"] += 1
            stats["X_count"] += 1
            stats["body_transitions"] += 1
        elif history == "H2":
            events = [X, ZERO, BODY_B1]
            body = evolve_body(body, interacted=False)
            stats["X_count"] += 1
            stats["body_transitions"] += 1
        elif history == "H3":
            events = [X, A_PAT, BODY_B2]
            rng.shuffle(events)
            body = evolve_body(body, interacted=True, consequence=consequence)
            stats["forced_A"] += 1
            stats["X_count"] += 1
            stats["body_transitions"] += 1
        elif history == "H4":
            if t % 3 == 0:
                events = [X, ZERO, ZERO]
                stats["X_count"] += 1
            elif t % 3 == 1:
                events = [A_PAT, ZERO, ZERO]
                stats["forced_A"] += 1
            else:
                events = [BODY_B2]
                body = evolve_body(body, interacted=True, consequence=consequence)
                stats["body_transitions"] += 1
        elif history == "H5":
            events = [X, A_PAT, BODY_B2]
            body = evolve_body(body, interacted=True, consequence=consequence)
            stats["forced_A"] += 1
            stats["X_count"] += 1
            stats["body_transitions"] += 1
            use_plasticity = False
        elif history == "H_A_REP":
            events = [X, A_PAT, ZERO]
            body = evolve_body(body, interacted=False)
            stats["forced_A"] += 1
            stats["X_count"] += 1
        elif history == "H_BODY":
            events = [X, ZERO, BODY_B2]
            body = evolve_body(body, interacted=True, consequence=consequence)
            stats["X_count"] += 1
            stats["body_transitions"] += 1
        elif history == "H_X_ONLY":
            events = [X, ZERO, ZERO]
            stats["X_count"] += 1
        elif history == "H_B1":
            events = [X, A_PAT, BODY_B1]
            body = evolve_body(body, interacted=True, consequence="NONE")
            stats["forced_A"] += 1
            stats["X_count"] += 1
            stats["body_transitions"] += 1
        else:
            events = [ZERO]
        state = _seq(state, events, plasticity=use_plasticity)
        raw.append({"t": t, "history": history, "events": [list(e) for e in events], "body": dict(body)})
    state = _rest(state, 10, use_plasticity)
    stats["final_body"] = body
    stats["raw_len"] = len(raw)
    return state, raw, stats


def matched_present_reset(state: AdaptiveInternalState) -> AdaptiveInternalState:
    """Keep learned W; reset q/trace for matched present."""
    return AdaptiveInternalState(weights=state.weights)


def autonomous_probe(
    state: AdaptiveInternalState,
    precursor: tuple[float, ...] = X,
    *,
    seed: int,
    body: dict[str, float] | None = None,
    coupling_ablation: bool = False,
    I_to_N: bool = True,
    motor_enabled: bool = True,
    prediction_enabled: bool = True,
    value_neutralized: bool = True,
    omit_future_event: bool = True,
    object_available: bool = True,
    consequence: str = "B2",
    n_samples: int = 48,
    horizon: int = FUTURE_HORIZON,
) -> dict[str, Any]:
    """Pre-event probe then optional future body evolution after sampled intervention."""
    base = matched_present_reset(state)
    s = ablate_weights(base) if coupling_ablation else base
    I = EndogenousSignalState()
    N = SensorimotorState()
    body0 = dict(body or initial_body())
    traj = []
    for t in range(PROBE_STEPS):
        s = step(s, physical_input=precursor if t == 0 else ZERO, plasticity=False)
        I = evolve_signal(I, perturbation=s.q)
        N = evolve(
            N,
            body=body0,
            sensory=(0.5, 0.5),
            random_value=((seed * 29 + t * 13) % 101) / 100.0,
            endogenous=I.channels,
            endogenous_coupling=I_to_N,
        )
        traj.append({"q": s.q, "I": I.channels, "N": N.channels, "body": dict(body0)})

    motor = motor_distribution(N) if motor_enabled else {
        "probs": {"WAIT": 1.0, "M0": 0.0, "M1": 0.0, "M2": 0.0},
        "motor_magnitude": 0.0,
        "non_wait_probability": 0.0,
        "provenance": {"stochastic_baseline": 0.0, "ordinary_state_value": 0.0,
                       "legacy_action_logits": 0.0, "acquired_prediction": 0.0},
    }
    p_A = float(motor["probs"].get(INTERACT_ACTION, 0.0)) if motor_enabled else 0.0

    samples = []
    for i in range(n_samples):
        act = sample_motor(motor, seed=seed * 1009 + i * 17) if motor_enabled else "WAIT"
        if not object_available and act == INTERACT_ACTION:
            attempted = True
            success = False
            act_rec = act
        else:
            attempted = act == INTERACT_ACTION
            success = attempted and object_available
            act_rec = act
        samples.append({"action": act_rec, "attempted_A": attempted, "success_A": success})

    p_A_emp = sum(1 for x in samples if x["success_A"]) / max(1, n_samples)
    p_attempt = sum(1 for x in samples if x["attempted_A"]) / max(1, n_samples)

    def future_path(do_A: bool) -> list[dict[str, float]]:
        b = dict(body0)
        path = [dict(b)]
        for h in range(horizon):
            b = autonomous_drift(b)
            if do_A and h == DISTAL_DELAY:
                b = apply_distal_consequence(b, consequence)
            path.append(dict(b))
        return path

    fut_A = future_path(True)
    fut_no = future_path(False)
    success_rate = 0.0 if not object_available else p_A
    fut_mix_end = {
        "internal_a": success_rate * fut_A[-1]["internal_a"] + (1 - success_rate) * fut_no[-1]["internal_a"],
        "load_c": success_rate * fut_A[-1]["load_c"] + (1 - success_rate) * fut_no[-1]["load_c"],
    }

    _ = prediction_enabled  # unused on runtime path; C13 compares on vs off identity
    return {
        "q": s.q,
        "I": I.to_dict(),
        "N": N.to_dict(),
        "motor": motor,
        "trajectory": traj,
        "weights": s.weights,
        "p_A": p_A,
        "p_A_empirical": p_A_emp,
        "p_attempt_A": p_attempt,
        "samples": samples,
        "body0": body0,
        "future_with_A": fut_A,
        "future_without_A": fut_no,
        "future_mixed_end": fut_mix_end,
        "future_divergence": body_l1(fut_A[-1], fut_no[-1]),
        "prediction_runtime_enabled": prediction_enabled,
        "prediction_runtime_contribution": 0.0,
        "ordinary_state_value": 0.0 if value_neutralized else None,
        "legacy_action_logits": 0.0 if value_neutralized else None,
        "event_present": not omit_future_event,
        "object_available": object_available,
        "representation": representation(s),
        "immediate_vs_distal": immediate_vs_distal_control(body0),
        "ablations": {
            "W": coupling_ablation,
            "I_to_N": not I_to_N,
            "motor": not motor_enabled,
            "prediction": not prediction_enabled,
            "value": value_neutralized,
        },
    }


def weight_l1(a: AdaptiveInternalState, b: AdaptiveInternalState) -> float:
    return sum(abs(x - y) for ra, rb in zip(a.weights, b.weights) for x, y in zip(ra, rb))


def l1_traj(a: list[dict], b: list[dict], key: str = "q") -> float:
    return sum(sum(abs(x - y) for x, y in zip(ra[key], rb[key])) for ra, rb in zip(a, b))


def purge_raw(raw: list) -> int:
    n = len(raw)
    raw.clear()
    return n


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def second_order_step(
    state: AdaptiveInternalState,
    *,
    seed: int,
    consequence: str = "B2",
    plasticity: bool = True,
) -> AdaptiveInternalState:
    """One autonomous A episode feeding local plasticity (no special self-train)."""
    probe = autonomous_probe(state, seed=seed, consequence=consequence, n_samples=1)
    act = probe["samples"][0]["action"]
    if act == INTERACT_ACTION:
        events = [X, A_PAT, BODY_B2 if consequence == "B2" else BODY_B3]
    else:
        events = [X, ZERO, BODY_B1]
    return _seq(state, events, plasticity=plasticity)
