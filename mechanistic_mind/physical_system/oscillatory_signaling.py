"""Physical oscillatory signaling — banded spatial transduction.

OPTION B: new oscillatory band-energy fields alongside legacy FIELD_A / FIELD_B.
Legacy A/B remain unchanged (motion/contact continuum). This module adds:
  motor → persistent emission (freq/amp/duration) → band-weighted spatial deposit
  → decay/spread/superposition → L/R head-linked receptor sampling
  → anonymous osc_l_* / osc_r_* cognition channels.

No language, messages, source identity, source direction, or communication reward.
FINITE_PROPAGATION = NOT_IMPLEMENTED (same-tick spatial locality via attenuation
of deposits + emergent decay/spread; no delayed wavefront).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.state import PlanetState
from mechanistic_mind.planet.topology import wrap_coord
from mechanistic_mind.physical_system.articulated_head import head_world_heading
from mechanistic_mind.physical_system.near_field_exteroception import wrap_angle

N_BANDS_DEFAULT = 6
OSC_CHANNEL_PREFIX_L = "osc_l_"
OSC_CHANNEL_PREFIX_R = "osc_r_"

# Motor nudge actions (bounded continuous parameter control — not semantic tones).
OSC_FREQ_ACTIONS = ("OSC_FREQ_UP", "OSC_FREQ_DOWN")
OSC_AMP_ACTIONS = ("OSC_AMP_UP", "OSC_AMP_DOWN")
OSC_EMIT_ACTIONS = ("OSC_EMIT",)
OSC_ACTIONS = OSC_FREQ_ACTIONS + OSC_AMP_ACTIONS + OSC_EMIT_ACTIONS
BRIDGE_OSC = "oscillatory_emit_v1"

FREQ_STEP = 0.08
AMP_STEP = 0.08


@dataclass
class OscillatorySignalingConfig:
    """Oscillatory physical signaling. Factory default OFF; fresh experiments ON via integrity."""

    mode: str = "OFF"  # OFF | EXPERIMENTAL
    emission_enabled: bool = True
    propagation_enabled: bool = True
    perception_enabled: bool = True
    n_bands: int = N_BANDS_DEFAULT
    # Normalized frequency domain f ∈ [0, 1].
    f_min: float = 0.0
    f_max: float = 1.0
    # Band Gaussian half-width in normalized frequency (overlap).
    band_width: float = 0.22
    decay: float = 0.30
    spread: float = 0.18
    floor: float = 1e-4
    field_cap: float = 2.0
    source_cap: float = 1.0
    # Emission duration bounds (ticks).
    duration_min: int = 1
    duration_max: int = 48
    duration_base: int = 8
    # Lateral receptor offset in world cells (perpendicular to head heading).
    receptor_offset: float = 0.55
    # Motor control steps.
    freq_step: float = FREQ_STEP
    amp_step: float = AMP_STEP
    # Physical work debit per (amplitude × tick) while emitting; 0 = free.
    work_cost_per_amp_tick: float = 0.015
    # Search-facing schema knobs (documented; used by physics).
    atten_note: str = "deposit_local_plus_decay_spread"
    finite_propagation: str = "NOT_IMPLEMENTED"

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "OscillatorySignalingConfig":
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def band_centers(n_bands: int) -> np.ndarray:
    n = max(1, int(n_bands))
    if n == 1:
        return np.array([0.5], dtype=np.float64)
    return np.linspace(0.0, 1.0, n, dtype=np.float64)


def band_response(freq: float, *, n_bands: int, width: float) -> np.ndarray:
    """Overlapping Gaussian weights over normalized frequency. Sum not forced to 1."""
    f = float(max(0.0, min(1.0, freq)))
    centers = band_centers(n_bands)
    w = max(1e-6, float(width))
    weights = np.exp(-0.5 * ((centers - f) / w) ** 2)
    return weights.astype(np.float64)


def ensure_osc_fields(planet: PlanetState, cfg: OscillatorySignalingConfig) -> np.ndarray:
    """Allocate OSC_BANDS as (n_bands, H, W)."""
    h, w = planet.T.shape
    n = max(1, int(cfg.n_bands))
    arr = getattr(planet, "OSC_BANDS", None)
    if arr is None or np.asarray(arr).shape != (n, h, w):
        planet.OSC_BANDS = np.zeros((n, h, w), dtype=np.float64)
    else:
        planet.OSC_BANDS = np.asarray(arr, dtype=np.float64)
    return planet.OSC_BANDS


def clear_osc_fields(planet: PlanetState) -> None:
    planet.OSC_BANDS = None


def _propagate_bands(bands: np.ndarray, cfg: OscillatorySignalingConfig) -> None:
    decay = min(max(0.0, float(cfg.decay)), 1.0)
    bands *= (1.0 - decay)
    if cfg.propagation_enabled:
        sp = min(max(0.0, float(cfg.spread)), 1.0)
        for b in range(bands.shape[0]):
            field = bands[b]
            neigh = (
                np.roll(field, 1, 0) + np.roll(field, -1, 0)
                + np.roll(field, 1, 1) + np.roll(field, -1, 1)
            )
            field *= (1.0 - sp)
            field += (sp / 4.0) * neigh
    np.clip(bands, 0.0, float(cfg.field_cap), out=bands)
    bands[bands < float(cfg.floor)] = 0.0


def _deposit_band_energy(
    bands: np.ndarray,
    *,
    iy: int,
    ix: int,
    amp: float,
    freq: float,
    cfg: OscillatorySignalingConfig,
) -> float:
    amp = float(min(max(0.0, amp), float(cfg.source_cap)))
    if amp <= 0.0:
        return 0.0
    weights = band_response(freq, n_bands=int(cfg.n_bands), width=float(cfg.band_width))
    h, w = bands.shape[1], bands.shape[2]
    # Local 3×3 deposit (wrap) for spatial locality without full kernel.
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            dist = abs(dy) + abs(dx)
            scale = 1.0 if dist == 0 else (0.45 if dist == 1 else 0.20)
            jy = int(wrap_coord(iy + dy, h))
            jx = int(wrap_coord(ix + dx, w))
            for b, wt in enumerate(weights):
                if wt <= 1e-12:
                    continue
                bands[b, jy, jx] = float(
                    min(float(cfg.field_cap), float(bands[b, jy, jx]) + amp * float(wt) * scale)
                )
    return amp


def clamp_freq_u(u: float) -> float:
    return float(max(0.0, min(1.0, u)))


def clamp_amp_u(u: float) -> float:
    return float(max(0.0, min(1.0, u)))


def frequency_from_control(u: float, cfg: OscillatorySignalingConfig) -> float:
    u = clamp_freq_u(u)
    return float(cfg.f_min + (cfg.f_max - cfg.f_min) * u)


def duration_from_control(u_hold: float, cfg: OscillatorySignalingConfig) -> int:
    """Map optional hold factor to tick duration; default uses duration_base."""
    t = int(round(float(cfg.duration_base) * (0.5 + 0.5 * clamp_amp_u(u_hold))))
    return int(max(int(cfg.duration_min), min(int(cfg.duration_max), t)))


def receptor_world_positions(
    body: PhysicalBodyState,
    *,
    articulated_head: bool,
    offset: float,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Left/right receptor sites from head (or body) heading. No source angle to cognition."""
    if articulated_head:
        heading = head_world_heading(body)
    else:
        heading = float(getattr(body, "theta", 0.0) or 0.0)
    # Perpendicular to forward heading: left = heading - π/2.
    left_ang = wrap_angle(heading - 0.5 * math.pi)
    right_ang = wrap_angle(heading + 0.5 * math.pi)
    ox = float(offset)
    x = float(body.x)
    y = float(body.y)
    # World +x east, +y south (consistent with MOVE:E/S).
    lx = x + ox * math.cos(left_ang)
    ly = y + ox * math.sin(left_ang)
    rx = x + ox * math.cos(right_ang)
    ry = y + ox * math.sin(right_ang)
    return (lx, ly), (rx, ry)


def sample_bands_at(
    bands: np.ndarray,
    x: float,
    y: float,
    *,
    width: int,
    height: int,
) -> np.ndarray:
    """Bilinear-ish: sample nearest cell per band."""
    ix = int(wrap_coord(int(math.floor(x)), width))
    iy = int(wrap_coord(int(math.floor(y)), height))
    return np.asarray(bands[:, iy, ix], dtype=np.float64).copy()


def cognition_osc_fragments(
    body: PhysicalBodyState,
    world: PlanetState,
    cfg: OscillatorySignalingConfig,
    *,
    articulated_head: bool = False,
) -> dict[str, float]:
    """Anonymous L/R band channels. Empty when OFF / perception OFF / no fields."""
    if not cfg.enabled or not cfg.perception_enabled:
        return {}
    bands = getattr(world, "OSC_BANDS", None)
    if bands is None:
        return {}
    h, w = int(world.T.shape[0]), int(world.T.shape[1])
    (lx, ly), (rx, ry) = receptor_world_positions(
        body, articulated_head=articulated_head, offset=float(cfg.receptor_offset),
    )
    left = sample_bands_at(bands, lx, ly, width=w, height=h)
    right = sample_bands_at(bands, rx, ry, width=w, height=h)
    n = int(bands.shape[0])
    out: dict[str, float] = {}
    for i in range(n):
        out[f"{OSC_CHANNEL_PREFIX_L}{i}"] = float(max(0.0, min(1.0, left[i] / max(1e-9, float(cfg.field_cap)))))
        out[f"{OSC_CHANNEL_PREFIX_R}{i}"] = float(max(0.0, min(1.0, right[i] / max(1e-9, float(cfg.field_cap)))))
    return out


def apply_osc_motor_action(body: PhysicalBodyState, action: str, cfg: OscillatorySignalingConfig) -> dict[str, Any]:
    """Apply OSC_* discrete motor onto body continuous controls / emit gate."""
    kind = str(action)
    if not cfg.enabled:
        return {"applied": False, "reason": "oscillatory_signaling_off"}
    # Ensure motor state exists.
    if not hasattr(body, "osc_freq_u"):
        body.osc_freq_u = 0.5
    if not hasattr(body, "osc_amp_u"):
        body.osc_amp_u = 0.5
    if not hasattr(body, "osc_emit_remaining"):
        body.osc_emit_remaining = 0

    if kind == "OSC_FREQ_UP":
        body.osc_freq_u = clamp_freq_u(float(body.osc_freq_u) + float(cfg.freq_step))
        return {"applied": True, "osc_freq_u": float(body.osc_freq_u)}
    if kind == "OSC_FREQ_DOWN":
        body.osc_freq_u = clamp_freq_u(float(body.osc_freq_u) - float(cfg.freq_step))
        return {"applied": True, "osc_freq_u": float(body.osc_freq_u)}
    if kind == "OSC_AMP_UP":
        body.osc_amp_u = clamp_amp_u(float(body.osc_amp_u) + float(cfg.amp_step))
        return {"applied": True, "osc_amp_u": float(body.osc_amp_u)}
    if kind == "OSC_AMP_DOWN":
        body.osc_amp_u = clamp_amp_u(float(body.osc_amp_u) - float(cfg.amp_step))
        return {"applied": True, "osc_amp_u": float(body.osc_amp_u)}
    if kind == "OSC_EMIT":
        dur = duration_from_control(float(getattr(body, "osc_amp_u", 0.5) or 0.5), cfg)
        # Refresh / start persistent emission.
        body.osc_emit_remaining = int(max(int(body.osc_emit_remaining or 0), dur))
        body.osc_emit_active = 1.0
        return {
            "applied": True,
            "osc_emit_remaining": int(body.osc_emit_remaining),
            "frequency": frequency_from_control(float(body.osc_freq_u), cfg),
            "amplitude": clamp_amp_u(float(body.osc_amp_u)),
            "duration": dur,
        }
    return {"applied": False, "reason": "not_osc_action"}


def set_undercover_osc_params(
    body: PhysicalBodyState,
    *,
    frequency: float | None = None,
    amplitude: float | None = None,
    duration: int | None = None,
    cfg: OscillatorySignalingConfig,
    emit_now: bool = False,
) -> dict[str, Any]:
    """Undercover / experimenter sets same physical motor parameters as organisms."""
    if frequency is not None:
        # Map absolute normalized freq → control u.
        span = max(1e-9, float(cfg.f_max) - float(cfg.f_min))
        body.osc_freq_u = clamp_freq_u((float(frequency) - float(cfg.f_min)) / span)
    if amplitude is not None:
        body.osc_amp_u = clamp_amp_u(float(amplitude))
    if duration is not None and emit_now:
        d = int(max(int(cfg.duration_min), min(int(cfg.duration_max), int(duration))))
        body.osc_emit_remaining = d
        body.osc_emit_active = 1.0
    elif emit_now:
        return apply_osc_motor_action(body, "OSC_EMIT", cfg)
    return {
        "osc_freq_u": float(getattr(body, "osc_freq_u", 0.5)),
        "osc_amp_u": float(getattr(body, "osc_amp_u", 0.5)),
        "osc_emit_remaining": int(getattr(body, "osc_emit_remaining", 0) or 0),
    }


@dataclass
class OscEmitterRecord:
    """WORLD GT only — never cognition."""

    emission_id: str
    slot: int | None
    body_id: str
    x: float
    y: float
    frequency: float
    amplitude: float
    remaining: int
    self_body_index: int


def step_oscillatory_signaling(
    world: PlanetState,
    bodies: list[PhysicalBodyState],
    cfg: OscillatorySignalingConfig,
    *,
    tick: int,
    articulated_head: bool = False,
    body_ids: list[str] | None = None,
    slots: list[int | None] | None = None,
    apply_work_cost: bool = True,
) -> dict[str, Any]:
    """One tick: propagate bands, deposit from active emitters, sample receptors (GT)."""
    if not cfg.enabled:
        return {
            "enabled": False,
            "emitters": [],
            "receptions": [],
            "finite_propagation": cfg.finite_propagation,
        }
    bands = ensure_osc_fields(world, cfg)
    _propagate_bands(bands, cfg)

    emitters_gt: list[dict[str, Any]] = []
    h, w = int(world.T.shape[0]), int(world.T.shape[1])
    work_debits: list[dict[str, Any]] = []

    for i, body in enumerate(bodies):
        rem = int(getattr(body, "osc_emit_remaining", 0) or 0)
        if rem <= 0 or not cfg.emission_enabled:
            body.osc_emit_active = 0.0
            if rem < 0:
                body.osc_emit_remaining = 0
            continue
        freq_u = clamp_freq_u(float(getattr(body, "osc_freq_u", 0.5)))
        amp_u = clamp_amp_u(float(getattr(body, "osc_amp_u", 0.5)))
        freq = frequency_from_control(freq_u, cfg)
        amp = amp_u
        iy, ix = body.cell(w, h)
        deposited = _deposit_band_energy(bands, iy=iy, ix=ix, amp=amp, freq=freq, cfg=cfg)
        eid = f"osc-{tick}-{i}-{rem}"
        bid = (body_ids[i] if body_ids and i < len(body_ids) else f"body_{i}")
        slot = slots[i] if slots and i < len(slots) else i
        emitters_gt.append({
            "emission_id": eid,
            "slot": slot,
            "body_id": bid,
            "x": float(body.x),
            "y": float(body.y),
            "frequency": freq,
            "amplitude": amp,
            "remaining": rem,
            "deposited": deposited,
            "active": True,
        })
        if apply_work_cost and float(cfg.work_cost_per_amp_tick) > 0.0:
            cost = float(cfg.work_cost_per_amp_tick) * float(amp)
            res = float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0)
            paid = float(min(res, cost))
            body.mechanical_work_reservoir = res - paid
            work_debits.append({"body_id": bid, "requested": cost, "paid": paid})
            # If unpaid and cost required — still emit (physics first); cost is soft.
        body.osc_emit_remaining = rem - 1
        body.osc_emit_active = 1.0 if body.osc_emit_remaining > 0 else 0.0
        body.osc_frequency = freq  # WORLD GT cache
        body.osc_amplitude = amp

    receptions: list[dict[str, Any]] = []
    for i, body in enumerate(bodies):
        if not cfg.perception_enabled:
            continue
        (lx, ly), (rx, ry) = receptor_world_positions(
            body, articulated_head=articulated_head, offset=float(cfg.receptor_offset),
        )
        left = sample_bands_at(bands, lx, ly, width=w, height=h)
        right = sample_bands_at(bands, rx, ry, width=w, height=h)
        bid = (body_ids[i] if body_ids and i < len(body_ids) else f"body_{i}")
        # Self vs cross energy proxy: compare deposit cell of self vs total (Observer GT).
        self_amp = 0.0
        for em in emitters_gt:
            if em.get("body_id") == bid:
                self_amp += float(em.get("amplitude") or 0.0)
        total_l = float(left.sum())
        total_r = float(right.sum())
        receptions.append({
            "body_id": bid,
            "receptor_left_xy": [lx, ly],
            "receptor_right_xy": [rx, ry],
            "bands_left": [float(v) for v in left],
            "bands_right": [float(v) for v in right],
            "self_emission_active": self_amp > 0.0,
            "self_cross_note": "SELF/CROSS labels are Observer GT only; not cognition",
            "energy_left": total_l,
            "energy_right": total_r,
        })

    return {
        "enabled": True,
        "tick": int(tick),
        "n_bands": int(cfg.n_bands),
        "emitters": emitters_gt,
        "receptions": receptions,
        "work_debits": work_debits,
        "finite_propagation": cfg.finite_propagation,
        "band_energy_sum": float(bands.sum()),
    }


def oscillatory_world_gt(
    body: PhysicalBodyState,
    world: PlanetState,
    cfg: OscillatorySignalingConfig,
    *,
    articulated_head: bool = False,
    last_step: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Observer WORLD GT + AGENT-ACCESSIBLE split."""
    frags = cognition_osc_fragments(
        body, world, cfg, articulated_head=articulated_head,
    ) if cfg.enabled else {}
    (lx, ly), (rx, ry) = receptor_world_positions(
        body, articulated_head=articulated_head, offset=float(cfg.receptor_offset),
    ) if cfg.enabled else ((0.0, 0.0), (0.0, 0.0))
    return {
        "enabled": bool(cfg.enabled),
        "WORLD_GT": {
            "emit_active": float(getattr(body, "osc_emit_active", 0.0) or 0.0) > 0.0,
            "frequency": float(getattr(body, "osc_frequency", frequency_from_control(
                float(getattr(body, "osc_freq_u", 0.5) or 0.5), cfg
            ))),
            "amplitude": float(getattr(body, "osc_amplitude", getattr(body, "osc_amp_u", 0.0)) or 0.0),
            "remaining": int(getattr(body, "osc_emit_remaining", 0) or 0),
            "osc_freq_u": float(getattr(body, "osc_freq_u", 0.5) or 0.5),
            "osc_amp_u": float(getattr(body, "osc_amp_u", 0.5) or 0.5),
            "receptor_left_xy": [lx, ly],
            "receptor_right_xy": [rx, ry],
            "finite_propagation": cfg.finite_propagation,
            "last_step_emitters_n": len((last_step or {}).get("emitters") or []),
        },
        "AGENT_ACCESSIBLE": {
            **{k: frags.get(k) for k in frags},
            "status": "AVAILABLE" if (cfg.enabled and cfg.perception_enabled) else "NOT_AVAILABLE",
            "channels": sorted(frags.keys()),
        },
        "semantics": {
            "not_language": True,
            "not_message": True,
            "no_source_identity_to_cognition": True,
            "no_source_direction_to_cognition": True,
            "no_exact_frequency_to_cognition": True,
        },
    }
