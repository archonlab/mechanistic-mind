"""Bounded locally adaptive N–M coupling for Update 4.46.

R[j,i] is physical coupling from internal channel i to motor drive j.
Update uses only local N eligibility and current M activity.
No reward, target, condition label, or future consequence.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

N_DIM = 3
M_DIM = 3
TRACE_DECAY = 0.62
WEIGHT_DECAY = 0.999
LEARNING_RATE = 0.075
WEIGHT_BOUND = 0.65
TRACE_BOUND = 1.0


def _clip(x: float, b: float) -> float:
    return max(-b, min(b, float(x)))


def _zero_R() -> tuple[tuple[float, float, float], ...]:
    return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0))


@dataclass
class AcquiredCouplingState:
    weights: tuple[tuple[float, float, float], ...] = _zero_R()
    trace: tuple[float, float, float] = (0.0, 0.0, 0.0)
    tick: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {"weights": self.weights, "trace": self.trace, "tick": self.tick}


def step(state: AcquiredCouplingState, *, n: tuple[float, ...] = (),
         m: tuple[float, ...] = (), plasticity: bool = True,
         eligibility: bool = True) -> AcquiredCouplingState:
    """One local update. n is internal activity; m is motor activity (3 channels)."""
    nv = tuple(float(n[i]) if i < len(n) else 0.0 for i in range(N_DIM))
    mv = tuple(float(m[j]) if j < len(m) else 0.0 for j in range(M_DIM))
    trace = state.trace if eligibility else (0.0, 0.0, 0.0)
    w = [list(row) for row in state.weights]
    for j in range(M_DIM):
        for i in range(N_DIM):
            changed = w[j][i] * WEIGHT_DECAY
            if plasticity:
                changed += LEARNING_RATE * trace[i] * mv[j]
            w[j][i] = _clip(changed, WEIGHT_BOUND)
    new_trace = tuple(_clip(TRACE_DECAY * state.trace[i] + nv[i], TRACE_BOUND) for i in range(N_DIM))
    if not eligibility:
        new_trace = (0.0, 0.0, 0.0)
    return AcquiredCouplingState(tuple(tuple(row) for row in w), new_trace, state.tick + 1)


def reset_weights(state: AcquiredCouplingState) -> AcquiredCouplingState:
    return AcquiredCouplingState(_zero_R(), state.trace, state.tick)


def reset_transient(state: AcquiredCouplingState) -> AcquiredCouplingState:
    return AcquiredCouplingState(state.weights, (0.0, 0.0, 0.0), 0)


def apply_drive(n: tuple[float, ...], weights: tuple[tuple[float, ...], ...],
                *, isolate: bool = False) -> tuple[float, float, float]:
    extra = tuple(sum(weights[j][i] * n[i] for i in range(N_DIM)) for j in range(M_DIM))
    if isolate:
        return extra
    return tuple(n[j] + extra[j] for j in range(N_DIM))


def l1(a: AcquiredCouplingState, b: AcquiredCouplingState) -> float:
    return sum(abs(a.weights[j][i] - b.weights[j][i]) for j in range(M_DIM) for i in range(N_DIM))


def frobenius(weights: tuple[tuple[float, ...], ...]) -> float:
    return sum(x * x for row in weights for x in row) ** 0.5


def row_col_norms(weights: tuple[tuple[float, ...], ...]) -> dict[str, Any]:
    rows = [sum(abs(x) for x in row) for row in weights]
    cols = [sum(abs(weights[j][i]) for j in range(M_DIM)) for i in range(N_DIM)]
    return {"row_l1": rows, "col_l1": cols, "max_abs": max(abs(x) for row in weights for x in row)}


def representation(state: AcquiredCouplingState) -> dict[str, Any]:
    flat = [x for row in state.weights for x in row]
    return {
        "dimension_n": N_DIM, "dimension_m": M_DIM,
        "capacity": N_DIM * M_DIM,
        "active_couplings": sum(abs(x) > 1e-9 for x in flat),
        "nonzero_fraction": sum(abs(x) > 1e-9 for x in flat) / (N_DIM * M_DIM),
        "max_abs_weight": max(map(abs, flat)),
        "trace_capacity": N_DIM,
        "bytes": 8 * (N_DIM * M_DIM + N_DIM + 1),
    }
