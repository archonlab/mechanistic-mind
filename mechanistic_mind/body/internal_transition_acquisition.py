"""Bounded local acquisition of response-conditioned internal transitions.

Update 4.75. Experimental. Default off. Research-only consumer.

L records a finite temporal relation (S_before, M, S_after).
It does not score outcomes, rank responses, or enter runtime dynamics.

Constants reused from 4.41 / 4.46. No new rates.
Does not implement 4.76.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

S_DIM = 3
M_DIM = 2
TRACE_DECAY = 0.62
WEIGHT_DECAY = 0.999
LEARNING_RATE = 0.075
WEIGHT_BOUND = 0.65
TRACE_BOUND = 1.0


def _clip(x: float, b: float) -> float:
    return max(-b, min(b, float(x)))


def _zero_L() -> tuple[tuple[tuple[float, float, float], ...], ...]:
    z = (0.0, 0.0, 0.0)
    return ((z, z), (z, z), (z, z))


@dataclass
class TransitionRelationState:
    weights: tuple[tuple[tuple[float, float, float], ...], ...] = _zero_L()
    trace_s: tuple[float, float, float] = (0.0, 0.0, 0.0)
    trace_m: tuple[float, float] = (0.0, 0.0)
    tick: int = 0
    update_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights": self.weights,
            "trace_s": self.trace_s,
            "trace_m": self.trace_m,
            "tick": self.tick,
            "update_count": self.update_count,
        }


def default_transition_acquisition_config() -> dict[str, Any]:
    return {
        "enabled": True,
        "trace_decay": TRACE_DECAY,
        "weight_decay": WEIGHT_DECAY,
        "learning_rate": LEARNING_RATE,
        "weight_bound": WEIGHT_BOUND,
        "trace_bound": TRACE_BOUND,
    }


def reset_traces(state: TransitionRelationState) -> TransitionRelationState:
    return TransitionRelationState(state.weights, (0.0, 0.0, 0.0), (0.0, 0.0), 0, state.update_count)


def record(
    state: TransitionRelationState,
    *,
    s: tuple[float, ...],
    m: tuple[float, ...],
    eligibility: bool = True,
) -> TransitionRelationState:
    """Write current S and M into traces. Does not change L."""
    sv = tuple(float(s[i]) if i < len(s) else 0.0 for i in range(S_DIM))
    mv = tuple(float(m[j]) if j < len(m) else 0.0 for j in range(M_DIM))
    if not eligibility:
        return TransitionRelationState(state.weights, (0.0, 0.0, 0.0), (0.0, 0.0), state.tick + 1, state.update_count)
    ts = tuple(_clip(TRACE_DECAY * state.trace_s[i] + sv[i], TRACE_BOUND) for i in range(S_DIM))
    tm = tuple(_clip(TRACE_DECAY * state.trace_m[j] + mv[j], TRACE_BOUND) for j in range(M_DIM))
    return TransitionRelationState(state.weights, ts, tm, state.tick + 1, state.update_count)


def acquire(
    state: TransitionRelationState,
    *,
    s_after: tuple[float, ...],
    plasticity: bool = True,
    use_trace_s: bool = True,
    use_trace_m: bool = True,
) -> TransitionRelationState:
    """Bounded local update: L += lr * trace_s * trace_m * S_after. Sign-symmetric."""
    av = tuple(float(s_after[k]) if k < len(s_after) else 0.0 for k in range(S_DIM))
    ts = state.trace_s if use_trace_s else (0.0, 0.0, 0.0)
    tm = state.trace_m if use_trace_m else (0.0, 0.0)
    w = [[[state.weights[i][j][k] for k in range(S_DIM)] for j in range(M_DIM)] for i in range(S_DIM)]
    n_upd = state.update_count
    for i in range(S_DIM):
        for j in range(M_DIM):
            for k in range(S_DIM):
                changed = w[i][j][k] * WEIGHT_DECAY
                if plasticity:
                    changed += LEARNING_RATE * ts[i] * tm[j] * av[k]
                w[i][j][k] = _clip(changed, WEIGHT_BOUND)
    if plasticity:
        n_upd += 1
    packed = tuple(tuple(tuple(w[i][j][k] for k in range(S_DIM)) for j in range(M_DIM)) for i in range(S_DIM))
    return TransitionRelationState(packed, state.trace_s, state.trace_m, state.tick, n_upd)


def readout(state: TransitionRelationState, *, s_before: tuple[float, ...], m: tuple[float, ...]) -> tuple[float, float, float]:
    """Neutral continuation from L. Research instrumentation only."""
    sv = tuple(float(s_before[i]) if i < len(s_before) else 0.0 for i in range(S_DIM))
    mv = tuple(float(m[j]) if j < len(m) else 0.0 for j in range(M_DIM))
    out = []
    for k in range(S_DIM):
        acc = 0.0
        for i in range(S_DIM):
            for j in range(M_DIM):
                acc += state.weights[i][j][k] * sv[i] * mv[j]
        out.append(_clip(acc, 1.0))
    return (out[0], out[1], out[2])


def frobenius(state: TransitionRelationState) -> float:
    return sum(x * x for row in state.weights for pair in row for x in pair) ** 0.5


def linf_weights(a: TransitionRelationState, b: TransitionRelationState) -> float:
    m = 0.0
    for i in range(S_DIM):
        for j in range(M_DIM):
            for k in range(S_DIM):
                m = max(m, abs(a.weights[i][j][k] - b.weights[i][j][k]))
    return m


def l1_weights(a: TransitionRelationState, b: TransitionRelationState) -> float:
    s = 0.0
    for i in range(S_DIM):
        for j in range(M_DIM):
            for k in range(S_DIM):
                s += abs(a.weights[i][j][k] - b.weights[i][j][k])
    return s


def permute_weights(weights, perm: tuple[int, int, int]):
    """Apply the same coordinate permutation to both S indices of L."""
    out = [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]] for _ in range(S_DIM)]
    for i in range(S_DIM):
        for j in range(M_DIM):
            for k in range(S_DIM):
                out[perm[i]][j][perm[k]] = float(weights[i][j][k])
    return tuple(tuple(tuple(out[i][j][k] for k in range(S_DIM)) for j in range(M_DIM)) for i in range(S_DIM))


def permute_m_weights(weights, perm_m: tuple[int, int]):
    out = [[[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]] for _ in range(S_DIM)]
    for i in range(S_DIM):
        for j in range(M_DIM):
            for k in range(S_DIM):
                out[i][perm_m[j]][k] = float(weights[i][j][k])
    return tuple(tuple(tuple(out[i][j][k] for k in range(S_DIM)) for j in range(M_DIM)) for i in range(S_DIM))


def representation(state: TransitionRelationState) -> dict[str, Any]:
    flat = [x for row in state.weights for pair in row for x in pair]
    cap = S_DIM * M_DIM * S_DIM
    return {
        "s_dim": S_DIM,
        "m_dim": M_DIM,
        "capacity": cap,
        "active": sum(abs(x) > 1e-9 for x in flat),
        "nonzero_fraction": sum(abs(x) > 1e-9 for x in flat) / cap,
        "max_abs": max(map(abs, flat)),
        "frobenius": frobenius(state),
        "trace_s_capacity": S_DIM,
        "trace_m_capacity": M_DIM,
        "bytes": 8 * (cap + S_DIM + M_DIM + 2),
        "update_count": state.update_count,
        "weight_bound": WEIGHT_BOUND,
        "trace_bound": TRACE_BOUND,
    }
