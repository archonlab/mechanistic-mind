"""External energy forcing — not a STAR object; no semantic day/night."""
from __future__ import annotations

import numpy as np

from mechanistic_mind.planet.config import PlanetConfig
from mechanistic_mind.planet.topology import wrap_coord


def forcing_phase_fast(tick: int, period: int) -> float:
    """Internal diagnostic phase in [0, period). Not world-entity state."""
    p = max(1, int(period))
    return float(tick % p)


def forcing_field(config: PlanetConfig, tick: int, height: int, width: int, *, seed: int = 0) -> np.ndarray:
    """Bounded external energy flux F(x,y,t) on the torus.

    Fast lobe translates in x; slow rhythm modulates amplitude; optional
    seed-bounded irregularity. No DAY/NIGHT labels.
    """
    h, w = int(height), int(width)
    if not config.forcing_enabled:
        return np.full((h, w), float(config.F_baseline), dtype=np.float64)

    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    # lobe center travels around torus in x
    period = max(1, int(config.F_fast_period))
    cx = (tick * (w / period) + float(config.forcing_origin_x)) % w
    cy = (0.5 * h + float(config.forcing_origin_y)) % h
    # toroidal deltas
    dx = ((xx - cx + w * 0.5) % w) - w * 0.5
    dy = ((yy - cy + h * 0.5) % h) - h * 0.5
    lobe = np.exp(-(dx * dx + dy * dy) / (2.0 * config.F_fast_sigma ** 2))

    slow_p = max(1, int(config.F_slow_period))
    slow = 0.5 * (1.0 + np.sin(2.0 * np.pi * (tick % slow_p) / slow_p))
    amp = config.F_fast_amp * (1.0 + config.F_slow_amp * (slow - 0.5) * 2.0)

    irr = 0.0
    if config.F_irregular_amp > 0.0:
        # deterministic bounded hash-like variation per tick (not organism-dependent)
        rng = np.random.default_rng((seed * 1000003 + tick * 9176) & 0xFFFFFFFF)
        irr = float(config.F_irregular_amp) * float(rng.uniform(-1.0, 1.0))

    F = config.F_baseline + amp * lobe + irr
    return np.clip(F, 0.0, 1.5)
