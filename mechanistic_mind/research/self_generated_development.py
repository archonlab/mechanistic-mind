"""Update 4.43 — self-generated development / recursive causal history.

Distinguishes researcher-forced development from endogenous action that
modifies W via ordinary local 4.41 plasticity (no reward / success gating).
"""
from __future__ import annotations

import json
import random
import re
from copy import deepcopy
from typing import Any

from mechanistic_mind.body.adaptive_internal_coupling import (
    AdaptiveInternalState,
    ablate_weights,
    representation,
    step,
)
from mechanistic_mind.research import body_coupled_development as bcd

FORBIDDEN = (
    "HUNGER", "FOOD", "EAT", "THIRST", "PAIN", "PLEASURE", "FEAR", "ANXIETY",
    "WANT", "NEED", "DESIRE", "DRIVE", "MOTIVATION", "GOAL", "INTENTION",
    "REWARD", "PUNISHMENT", "GOOD", "BAD", "VALUE", "UTILITY", "SURVIVAL",
    "SELF_PRESERVATION", "HOMEOSTASIS", "SETPOINT", "CURIOSITY", "EXPLORATION",
    "NOVELTY", "INTEREST", "ATTENTION", "SALIENCE", "IMPORTANCE", "URGENCY",
    "SEEK", "AVOID", "SUCCESS", "FAILURE",
)

ZERO = bcd.ZERO
X = bcd.X
A_PAT = bcd.A_PAT
BODY_B2 = bcd.BODY_B2
BODY_B1 = bcd.BODY_B1
INTERACT = bcd.INTERACT_ACTION


def architecture_inspection() -> dict[str, Any]:
    path = __import__("pathlib").Path(
        "results/update443_self_generated_development/architecture_inspection.json"
    )
    if path.exists():
        return json.loads(path.read_text())
    return {"status": "MISSING"}


def _rest(state: AdaptiveInternalState, n: int = 4, plasticity: bool = True) -> AdaptiveInternalState:
    for _ in range(n):
        state = step(state, physical_input=ZERO, plasticity=plasticity)
    return state


def apply_episode(
    state: AdaptiveInternalState,
    action: str,
    *,
    plasticity: bool = True,
    consequence: str = "B2",
    body: dict[str, float] | None = None,
    precursor: tuple[float, ...] = X,
) -> tuple[AdaptiveInternalState, dict[str, float], dict[str, Any]]:
    """Ordinary physical episode from an already-selected action (forced or endogenous)."""
    body = dict(body or bcd.initial_body())
    did_A = action == INTERACT
    if did_A:
        events = [precursor, A_PAT, BODY_B2 if consequence == "B2" else bcd.BODY_B3]
        body = bcd.evolve_body(body, interacted=True, consequence=consequence)
    else:
        events = [precursor, ZERO, BODY_B1]
        body = bcd.evolve_body(body, interacted=False)
    state = _rest(state, 3, plasticity)
    for i, pat in enumerate(events):
        state = step(state, physical_input=pat, plasticity=plasticity)
        if i < len(events) - 1:
            state = step(state, physical_input=ZERO, plasticity=plasticity)
            state = step(state, physical_input=ZERO, plasticity=plasticity)
    state = _rest(state, 4, plasticity)
    meta = {
        "action": action,
        "did_A": did_A,
        "events": events,
        "body": dict(body),
        "source": "unspecified",
    }
    return state, body, meta


def bootstrap_researcher(
    *,
    trials: int,
    seed: int,
    plasticity: bool = True,
) -> tuple[AdaptiveInternalState, list[dict[str, Any]]]:
    """Researcher-forced H1 episodes (4.42 style). Not counted as self-generated."""
    state, raw, stats = bcd.develop("H1", trials=trials, seed=seed, plasticity=plasticity)
    for r in raw:
        r["source"] = "researcher_forced"
    return state, raw


def autonomous_phase(
    state: AdaptiveInternalState,
    *,
    steps: int,
    seed: int,
    plasticity: bool = True,
    motor_enabled: bool = True,
    object_available: bool = True,
    consequence: str = "B2",
    yoked_actions: list[str] | None = None,
    force_actions: list[str] | None = None,
    precursor: tuple[float, ...] = X,
) -> tuple[AdaptiveInternalState, list[dict[str, Any]], dict[str, Any]]:
    """Free-run: actions from existing motor machinery unless yoked/forced override.

    Yoked: replay another run's action sequence (matched motor history, different W path origin).
    Force: researcher supplies actions during 'autonomous' window (negative control).
    """
    body = bcd.initial_body()
    log: list[dict[str, Any]] = []
    n_endogenous_A = 0
    n_forced_A = 0
    n_yoked_A = 0
    n_endogenous = 0

    for t in range(steps):
        probe = bcd.autonomous_probe(
            state,
            precursor=precursor,
            seed=seed * 10007 + t * 17,
            body=body,
            motor_enabled=motor_enabled,
            object_available=object_available,
            consequence=consequence,
            n_samples=1,
            I_to_N=True,
            prediction_enabled=False,
            value_neutralized=True,
        )
        if force_actions is not None:
            action = force_actions[t % len(force_actions)]
            source = "researcher_forced"
        elif yoked_actions is not None:
            action = yoked_actions[t % len(yoked_actions)]
            source = "yoked"
        else:
            action = probe["samples"][0]["action"]
            source = "endogenous"
            n_endogenous += 1
            if not object_available and action == INTERACT:
                # Attempt without physical success: experience as non-A body path
                action_for_physics = "WAIT"
            else:
                action_for_physics = action
            if action == INTERACT and object_available:
                n_endogenous_A += 1
            state, body, meta = apply_episode(
                state,
                action_for_physics if source == "endogenous" else action,
                plasticity=plasticity,
                consequence=consequence,
                body=body,
                precursor=precursor,
            )
            meta["source"] = source
            meta["p_A"] = probe["p_A"]
            meta["attempted"] = probe["samples"][0]["action"]
            meta["tick"] = t
            meta["w_l1_from_init"] = None
            log.append(meta)
            continue

        if source == "researcher_forced" and action == INTERACT:
            n_forced_A += 1
        if source == "yoked" and action == INTERACT:
            n_yoked_A += 1

        if not object_available and action == INTERACT:
            action_phys = "WAIT"
        else:
            action_phys = action
        state, body, meta = apply_episode(
            state,
            action_phys,
            plasticity=plasticity,
            consequence=consequence,
            body=body,
            precursor=precursor,
        )
        meta["source"] = source
        meta["p_A"] = probe["p_A"]
        meta["attempted"] = action
        meta["tick"] = t
        log.append(meta)

    stats = {
        "steps": steps,
        "n_endogenous": n_endogenous,
        "n_endogenous_A": n_endogenous_A,
        "n_forced_A": n_forced_A,
        "n_yoked_A": n_yoked_A,
        "final_body": body,
        "plasticity": plasticity,
        "motor_enabled": motor_enabled,
        "object_available": object_available,
    }
    return state, log, stats


def probe_snapshot(state: AdaptiveInternalState, *, seed: int) -> dict[str, Any]:
    body = bcd.initial_body()
    p = bcd.autonomous_probe(
        state,
        seed=seed,
        body=body,
        n_samples=64,
        prediction_enabled=False,
        value_neutralized=True,
    )
    return {
        "p_A": p["p_A"],
        "p_A_empirical": p["p_A_empirical"],
        "motor": p["motor"],
        "q": p["q"],
        "I": p["I"],
        "N": p["N"],
        "ordinary_state_value": p["ordinary_state_value"],
        "legacy_action_logits": p["legacy_action_logits"],
        "prediction_runtime_contribution": p["prediction_runtime_contribution"],
        "representation": representation(state),
        "weights": state.weights,
    }


def decay_only_baseline(
    state: AdaptiveInternalState,
    *,
    steps: int,
) -> AdaptiveInternalState:
    """Same number of rest steps as a typical episode, plasticity on but ZERO input only.

    Separates WEIGHT_DECAY from action-linked plasticity.
    """
    # Approximate episode length: rest3 + 3 events + 2 gaps*2 + rest4 ≈ 3+3+4+4 = 14 steps
    per = 14
    s = state
    for _ in range(steps * per):
        s = step(s, physical_input=ZERO, plasticity=True)
    return s


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def weight_l1(a: AdaptiveInternalState, b: AdaptiveInternalState) -> float:
    return bcd.weight_l1(a, b)
