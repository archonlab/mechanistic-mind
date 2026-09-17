"""Bounded generic internal-signal substrate for Update 4.40.

It has no knowledge of predictions, body states, actions, or outcomes.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

DIMENSION = 3
DECAY = 0.68
PERSISTENCE = 0.12
AMPLITUDE_BOUND = 1.0


@dataclass
class EndogenousSignalState:
    channels: tuple[float, float, float] = (0.0, 0.0, 0.0)
    previous: tuple[float, float, float] = (0.0, 0.0, 0.0)
    tick: int = 0

    def to_dict(self) -> dict[str, Any]: return asdict(self)


def _clip(x: float) -> float: return max(-AMPLITUDE_BOUND, min(AMPLITUDE_BOUND, float(x)))


def evolve_signal(state: EndogenousSignalState, *, perturbation: tuple[float, ...] = ()) -> EndogenousSignalState:
    """Generic decay, persistence, and superposition."""
    out=[]
    for i in range(DIMENSION):
        external=float(perturbation[i]) if i < len(perturbation) else 0.0
        out.append(_clip(DECAY*state.channels[i] + PERSISTENCE*state.previous[i] + external))
    return EndogenousSignalState(tuple(out), state.channels, state.tick+1)


def memory_cost_bytes(state: EndogenousSignalState) -> int:
    return 8 * (DIMENSION * 2 + 1)
