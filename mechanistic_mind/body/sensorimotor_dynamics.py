"""Generic bounded body-coupled sensorimotor dynamics for Update 4.39.

The state has no task semantics.  Actual physical inputs enter a fixed mixed
coupling matrix; predicted inputs have no port in this substrate.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, asdict
from typing import Any

CHANNELS = 3
DECAY = 0.72
NOISE_SCALE = 0.018
BASE_NON_WAIT = 0.08
COUPLING = (
    (0.22, -0.13),
    (-0.09, 0.20),
    (0.11, 0.08),
)


@dataclass
class SensorimotorState:
    channels: tuple[float, float, float] = (0.0, 0.0, 0.0)
    previous_output: tuple[float, float, float] = (0.0, 0.0, 0.0)
    tick: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _clip(value: float) -> float:
    return max(-1.0, min(1.0, float(value)))


def evolve(state: SensorimotorState, *, body: dict[str, float], sensory: tuple[float, ...] = (),
           random_value: float = .5, body_coupling: bool = True,
           dynamics_enabled: bool = True, endogenous: tuple[float, ...] = (),
           endogenous_coupling: bool = True,
           production_inputs: tuple[float, float] | None = None) -> SensorimotorState:
    """One bounded physical update; only actual body values are accepted.

    production_inputs: optional MM-INT-1 designed receptor interface (u0, u1 already
    centered). When set, bypasses historical internal_a/load_c sockets (E3D preserved).
    """
    if not dynamics_enabled:
        return SensorimotorState(tick=state.tick + 1)
    if production_inputs is not None:
        inputs = (float(production_inputs[0]), float(production_inputs[1] if len(production_inputs) > 1 else 0.0))
    else:
        inputs = (float(body.get("internal_a", 0.5)) - .5, float(body.get("load_c", 0.5)) - .5)
    centered_noise = (float(random_value) - .5) * 2.0 * NOISE_SCALE
    out = []
    for i in range(CHANNELS):
        body_term = sum(COUPLING[i][j] * inputs[j] for j in range(2)) if body_coupling else 0.0
        sensory_term = .03 * (float(sensory[i % len(sensory)]) - .5) if sensory else 0.0
        endogenous_term = .16 * float(endogenous[i % len(endogenous)]) if endogenous and endogenous_coupling else 0.0
        persistence = .08 * state.previous_output[i]
        out.append(_clip(DECAY * state.channels[i] + body_term + sensory_term + endogenous_term + persistence + centered_noise * (i + 1) / CHANNELS))
    return SensorimotorState(channels=tuple(out), previous_output=state.channels, tick=state.tick + 1)


def motor_distribution(state: SensorimotorState, *, stochastic_enabled: bool = True,
                       acquired: tuple[tuple[float, ...], ...] | None = None,
                       use_acquired: bool = False,
                       isolate_acquired: bool = False) -> dict[str, Any]:
    """Convert channel physics to a stochastic motor distribution, without ranking body states.

    acquired / use_acquired / isolate_acquired are the 4.46 gated path.
    Defaults (acquired unused) reproduce pre-4.46 behavior exactly.
    """
    channels = state.channels
    extra = (0.0, 0.0, 0.0)
    if use_acquired and acquired is not None:
        extra = tuple(sum(acquired[j][i] * channels[i] for i in range(CHANNELS)) for j in range(CHANNELS))
        channels = extra if isolate_acquired else tuple(channels[j] + extra[j] for j in range(CHANNELS))
    magnitude = math.sqrt(sum(x * x for x in channels) / CHANNELS)
    base = BASE_NON_WAIT if stochastic_enabled else 0.0
    non_wait = min(.70, max(0.0, base + .42 * magnitude))
    exps = [math.exp(x) for x in channels]
    total = sum(exps) or 1.0
    probs = {f"M{i}": non_wait * exps[i] / total for i in range(CHANNELS)}
    probs["WAIT"] = 1.0 - non_wait
    return {"probs": probs, "motor_magnitude": magnitude, "non_wait_probability": non_wait,
            "preact": channels, "acquired_extra": extra,
            "provenance": {"intrinsic_state": magnitude, "stochastic_baseline": base,
                           "ordinary_state_value": 0.0, "legacy_action_logits": 0.0,
                           "acquired_prediction": 0.0,
                           "acquired_coupling": 1.0 if (use_acquired and acquired is not None) else 0.0}}


def sample_motor(distribution: dict[str, Any], *, seed: int) -> str:
    rng = random.Random(seed); u = rng.random(); acc = 0.0
    for action, probability in distribution["probs"].items():
        acc += probability
        if u <= acc: return action
    return "WAIT"
