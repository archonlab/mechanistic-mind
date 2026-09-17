"""Update 4.4 — bounded generic motor channels + endogenous variation.

OBSERVER/cognition boundary: this module produces physical actuator state and
deltas. It does NOT implement curiosity, novelty, exploration reward, or
destination seeking. Deterministic under (seed, tick, state).
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from hashlib import blake2b
from typing import Any


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _unit_float(seed: int, tick: int, channel: int, salt: bytes = b"m") -> float:
    h = blake2b(
        f"{seed}:{tick}:{channel}".encode() + salt,
        digest_size=8,
    ).digest()
    # [0, 1)
    return int.from_bytes(h, "big") / float(2**64)


@dataclass
class MotorControlConfig:
    n_channels: int = 2
    range_min: float = -1.0
    range_max: float = 1.0
    max_abs_delta: float = 0.15
    # Physiological cost scale for |delta| effort (body hook).
    energy_cost_per_abs_delta: float = 0.002
    hydration_cost_per_abs_delta: float = 0.0006
    fatigue_cost_per_abs_delta: float = 0.0015
    # Update 4.5.1 state-dependent scaling (physiology, not reward).
    activity_load_cost_gain: float = 1.5
    fatigue_cost_gain: float = 0.8
    low_capacity_cost_gain: float = 1.0
    # Map motor vector to attempted cell displacement threshold.
    displace_threshold: float = 0.55
    endogenous_variation: bool = True
    # If False: Experiment E ablation — freeze actuators.
    enabled: bool = True


@dataclass
class MotorControlState:
    channels: list[float] = field(default_factory=lambda: [0.0, 0.0])
    last_delta: list[float] = field(default_factory=lambda: [0.0, 0.0])
    last_load: list[float] = field(default_factory=lambda: [0.0, 0.0])
    last_resistance: float = 0.0
    last_contact: float = 0.0
    last_displacement: tuple[int, int] | None = None
    last_attempted_step: tuple[int, int] | None = None
    last_effect_kind: str = "NONE"  # NONE|NO_DISPLACE|DISPLACED|BLOCKED|RESISTED
    tick: int = -1

    def to_dict(self) -> dict[str, Any]:
        return {
            "channels": list(self.channels),
            "last_delta": list(self.last_delta),
            "last_load": list(self.last_load),
            "last_resistance": float(self.last_resistance),
            "last_contact": float(self.last_contact),
            "last_displacement": list(self.last_displacement)
            if self.last_displacement
            else None,
            "last_attempted_step": list(self.last_attempted_step)
            if self.last_attempted_step
            else None,
            "last_effect_kind": self.last_effect_kind,
            "tick": int(self.tick),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None, n: int = 2) -> "MotorControlState":
        data = raw or {}
        st = cls()
        ch = data.get("channels") or [0.0] * n
        st.channels = [float(x) for x in ch][:n]
        while len(st.channels) < n:
            st.channels.append(0.0)
        ld = data.get("last_delta") or [0.0] * n
        st.last_delta = [float(x) for x in ld][:n]
        while len(st.last_delta) < n:
            st.last_delta.append(0.0)
        ll = data.get("last_load") or [0.0] * n
        st.last_load = [float(x) for x in ll][:n]
        while len(st.last_load) < n:
            st.last_load.append(0.0)
        st.last_resistance = float(data.get("last_resistance") or 0.0)
        st.last_contact = float(data.get("last_contact") or 0.0)
        disp = data.get("last_displacement")
        st.last_displacement = tuple(disp) if isinstance(disp, (list, tuple)) and len(disp) == 2 else None
        att = data.get("last_attempted_step")
        st.last_attempted_step = tuple(att) if isinstance(att, (list, tuple)) and len(att) == 2 else None
        st.last_effect_kind = str(data.get("last_effect_kind") or "NONE")
        st.tick = int(data.get("tick", -1))
        return st


def endogenous_motor_delta(
    *,
    config: MotorControlConfig,
    seed: int,
    tick: int,
    state: MotorControlState,
) -> list[float]:
    """Bounded endogenous actuator variation. Not exploration/curiosity."""
    if not config.enabled or not config.endogenous_variation:
        return [0.0] * config.n_channels
    deltas = []
    for i in range(config.n_channels):
        # Signed delta in [-max_abs_delta, +max_abs_delta]
        u = _unit_float(seed, tick, i, b"delta")
        signed = (u * 2.0 - 1.0) * config.max_abs_delta
        # Softly shrink near range walls
        cur = state.channels[i] if i < len(state.channels) else 0.0
        if cur + signed > config.range_max:
            signed = config.range_max - cur
        if cur + signed < config.range_min:
            signed = config.range_min - cur
        deltas.append(float(signed))
    return deltas


def apply_motor_delta_to_state(
    state: MotorControlState,
    delta: list[float],
    *,
    config: MotorControlConfig,
    tick: int,
) -> MotorControlState:
    out = MotorControlState.from_dict(state.to_dict(), n=config.n_channels)
    out.tick = tick
    out.last_delta = [float(d) for d in delta[: config.n_channels]]
    while len(out.last_delta) < config.n_channels:
        out.last_delta.append(0.0)
    new_ch = []
    for i in range(config.n_channels):
        cur = out.channels[i] if i < len(out.channels) else 0.0
        d = out.last_delta[i]
        new_ch.append(_clamp(cur + d, config.range_min, config.range_max))
    out.channels = new_ch
    # Load ~ |channel| after update (generic effort proxy)
    out.last_load = [abs(c) for c in out.channels]
    return out


def motor_attempted_step(channels: list[float], *, threshold: float) -> tuple[int, int] | None:
    """Map actuator vector to at most one cardinal step without semantic labels.

    Uses motor_0 ~ axis-0, motor_1 ~ axis-1 magnitude. No LEFT/RIGHT tokens.
    """
    if len(channels) < 2:
        return None
    a0, a1 = float(channels[0]), float(channels[1])
    if abs(a0) < threshold and abs(a1) < threshold:
        return None
    if abs(a0) >= abs(a1):
        return (1 if a0 > 0 else -1, 0)
    return (0, 1 if a1 > 0 else -1)


def proprioceptive_bundle(state: MotorControlState) -> dict[str, Any]:
    """Physically plausible self signals — no world-truth labels."""
    return {
        "actuator_state": list(state.channels),
        "actuator_delta": list(state.last_delta),
        "actuator_load": list(state.last_load),
        "resistance": float(state.last_resistance),
        "contact": float(state.last_contact),
        "movement_magnitude": float(sum(abs(x) for x in state.last_delta)),
        "effect_kind_physical": state.last_effect_kind,  # physical outcome code, not semantic success
    }


def variation_body_cost(
    delta: list[float],
    config: MotorControlConfig,
    *,
    activity_load: float = 0.0,
    fatigue: float = 0.0,
    activity_capacity: float | None = None,
) -> dict[str, float]:
    """Physical cost of motor microvariation; scales with activity load/fatigue.

    Same motor delta can yield different consequences under different capacity.
    Does NOT encode MOVE=good/bad.
    """
    effort = sum(abs(float(x)) for x in delta)
    load = max(0.0, min(1.0, float(activity_load)))
    fat = max(0.0, min(1.0, float(fatigue)))
    if activity_capacity is None:
        cap = max(0.0, 1.0 - load)
    else:
        cap = max(0.0, min(1.0, float(activity_capacity)))
    scale = (
        1.0
        + float(config.activity_load_cost_gain) * load
        + float(config.fatigue_cost_gain) * fat
        + float(config.low_capacity_cost_gain) * max(0.0, 0.35 - cap)
    )
    return {
        "energy_delta": -config.energy_cost_per_abs_delta * effort * scale,
        "hydration_delta": -config.hydration_cost_per_abs_delta * effort * scale,
        "fatigue_delta": config.fatigue_cost_per_abs_delta * effort * scale,
        "motor_effort": float(effort),
        "cost_scale": float(scale),
        "activity_load": load,
        "activity_capacity": cap,
    }



def config_to_dict(cfg: MotorControlConfig) -> dict[str, Any]:
    return asdict(cfg)
