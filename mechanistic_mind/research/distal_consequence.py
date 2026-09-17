"""Update 4.43 — distal consequence vs proximal X→A. Unchanged 4.41 plasticity."""
from __future__ import annotations

import json
import random
import re
from typing import Any

from mechanistic_mind.body.adaptive_internal_coupling import (
    AdaptiveInternalState,
    ablate_weights,
    representation,
    step,
)
from mechanistic_mind.research import body_coupled_development as bcd

X = bcd.X
A_PAT = bcd.A_PAT
B1 = bcd.BODY_B2          # (0, 0, 0.55)
B2 = bcd.BODY_B1          # (0, 0, -0.55)
ZERO = bcd.ZERO
XA_GAP = 2
OUT_OF_WINDOW = 12
PRIMARY_DELAY = 2
DELAYS = {"D0": 0, "D1": 2, "D2": 5, "D3": 12}

FORBIDDEN = bcd.FORBIDDEN + ("CREDIT", "CREDIT_ASSIGNMENT", "CONSEQUENCE_VALUE", "ACTION_REASON", "FUTURE_BENEFIT")


def _rest(state: AdaptiveInternalState, n: int, plasticity: bool = True) -> AdaptiveInternalState:
    for _ in range(n):
        state = step(state, physical_input=ZERO, plasticity=plasticity)
    return state


def _pulse(state: AdaptiveInternalState, pat: tuple[float, ...], plasticity: bool) -> AdaptiveInternalState:
    return step(state, physical_input=pat, plasticity=plasticity)


def eligibility_snapshot(delay: int) -> dict[str, Any]:
    s = AdaptiveInternalState()
    s = _rest(s, 4)
    s = _pulse(s, X, True)
    at_x = s.trace
    s = _rest(s, XA_GAP)
    s = _pulse(s, A_PAT, True)
    at_a = s.trace
    s = _rest(s, delay)
    before_b = s.trace
    mag = sum(abs(0.075 * before_b[i] * B1[j]) for i in range(3) for j in range(3))
    s = _pulse(s, B1, True)
    return {
        "delay": delay,
        "eligibility_at_X": at_x,
        "eligibility_at_A": at_a,
        "eligibility_at_B": before_b,
        "update_mag_at_B": mag,
        "in_window": abs(before_b[1]) > 0.02,
    }


def develop(
    history: str,
    *,
    trials: int = 36,
    seed: int = 0,
    delay: int = PRIMARY_DELAY,
    b_pat: tuple[float, ...] = B1,
    plasticity: bool = True,
    a_pat: tuple[float, ...] = A_PAT,
) -> tuple[AdaptiveInternalState, list[dict[str, Any]], dict[str, Any]]:
    """Forced developmental episodes. No autonomous choice. No CREDIT variable."""
    rng = random.Random(seed)
    state = AdaptiveInternalState()
    raw: list[dict[str, Any]] = []
    stats = {"X": 0, "A": 0, "B": 0, "mode": history, "delay": delay, "ticks": 0}

    def emit(events: list[tuple[float, ...]]) -> None:
        nonlocal state
        state = _rest(state, 4, plasticity)
        for i, pat in enumerate(events):
            state = _pulse(state, pat, plasticity)
            stats["ticks"] += 1
            if pat == X:
                stats["X"] += 1
            elif pat == a_pat:
                stats["A"] += 1
            elif pat == b_pat or pat == B1 or pat == B2:
                if pat != ZERO and pat != X and pat != a_pat:
                    stats["B"] += 1
            if i < len(events) - 1:
                state = _rest(state, 0, plasticity)

    for t in range(trials):
        if history == "H0":
            events = [ZERO, ZERO, ZERO]
        elif history == "H1":
            # proximal only
            events = [X] + [ZERO] * XA_GAP + [a_pat]
        elif history == "H1B":
            # X→A then out-of-window B (matched B marginal, no A→B relation)
            events = [X] + [ZERO] * XA_GAP + [a_pat] + [ZERO] * OUT_OF_WINDOW + [b_pat]
        elif history == "H2":
            events = [X] + [ZERO] * XA_GAP + [a_pat] + [ZERO] * delay + [b_pat]
        elif history == "H3":
            # Matched X/A/B counts; B occurs first, far from A (decorrelated).
            events = [b_pat] + [ZERO] * OUT_OF_WINDOW + [X] + [ZERO] * XA_GAP + [a_pat]
        elif history == "H4":
            # matched marginals, broken chain: B then A then X
            events = [b_pat] + [ZERO] * delay + [a_pat] + [ZERO] * XA_GAP + [X]
        elif history == "H5":
            ev = [X, a_pat, b_pat]
            rng.shuffle(ev)
            events = ev
        else:
            events = [ZERO]
        # apply with recorded gaps already in events for H1/H1B/H2
        state = _rest(state, 3, plasticity)
        for pat in events:
            state = _pulse(state, pat, plasticity)
            if pat == X:
                stats["X"] += 1
            elif pat == a_pat:
                stats["A"] += 1
            elif pat in (b_pat, B1, B2) and pat not in (X, a_pat, ZERO):
                stats["B"] += 1
            stats["ticks"] += 1
        raw.append({"t": t, "events": [list(p) for p in events]})
        state = _rest(state, 4, plasticity)
    state = _rest(state, 8, plasticity)
    stats["raw_len"] = len(raw)
    return state, raw, stats


def probe(state: AdaptiveInternalState, *, seed: int, **kw) -> dict[str, Any]:
    return bcd.autonomous_probe(state, bcd.X, seed=seed, n_samples=kw.pop("n_samples", 48), **kw)


def weight_l1(a: AdaptiveInternalState, b: AdaptiveInternalState) -> float:
    return bcd.weight_l1(a, b)


def w_matrix(state: AdaptiveInternalState) -> list[list[float]]:
    return [list(row) for row in state.weights]


def cognition_leaks(payload: Any) -> list[str]:
    text = json.dumps(payload, sort_keys=True, default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])", text)]


def architecture_inspection() -> dict[str, Any]:
    path = __import__("pathlib").Path("results/update443_distal_consequence/architecture_inspection.json")
    return json.loads(path.read_text()) if path.exists() else {"status": "MISSING"}
