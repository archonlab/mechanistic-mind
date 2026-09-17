"""Experimental endogenous internal→motor coupling (default OFF).

NEW MECHANISM — not present in baseline PhysicalSystemRuntime diagnosis.
Does not emit discrete MOVE actions.

Magnitude: from temporal change in internal.c (gradient energy).
Direction: from existing local physical asymmetry (flow / T-gradient / velocity).
If no asymmetry exists, motor magnitude may accumulate but spatial acceleration
contribution is zero — no arbitrary compass invented.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

SITE_CENTER, SITE_YM, SITE_YP, SITE_XM, SITE_XP = 0, 1, 2, 3, 4


@dataclass
class EndogenousMotorCouplingConfig:
    mode: str = "EXPERIMENTAL"  # OFF | EXPERIMENTAL — CURRENT INTEGRATED default; from_dict({}) stays OFF
    type: str = "DELTA_ENERGY_TIMES_LOCAL_ASYMMETRY"
    strength: float = 0.08
    decay: float = 0.12
    saturation: float = 0.30
    use_delta: bool = True
    body_b_gain: bool = False
    # Prefer morphological site differential when it is nonzero; else env asymmetry.
    prefer_site_differential: bool = True
    site_diff_eps: float = 1e-9

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "EndogenousMotorCouplingConfig":
        # Missing/empty dict = historical PRE-INTEGRATION (OFF). Explicit keys load as given.
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"


def site_means(c: np.ndarray) -> np.ndarray:
    c = np.asarray(c, dtype=np.float64)
    if c.ndim != 2:
        return np.zeros(5, dtype=np.float64)
    return c.mean(axis=1)


def morphological_target(s: np.ndarray) -> tuple[float, float]:
    if s.shape[0] < 5:
        return 0.0, 0.0
    return float(s[SITE_XP] - s[SITE_XM]), float(s[SITE_YP] - s[SITE_YM])


def unit(x: float, y: float) -> tuple[float, float]:
    m = float(np.hypot(x, y))
    if m < 1e-15:
        return 0.0, 0.0
    return x / m, y / m


def update_motor_state(
    *,
    motor_ux: float,
    motor_uy: float,
    c_now: np.ndarray,
    c_prev: np.ndarray | None,
    body_B: np.ndarray | None,
    cfg: EndogenousMotorCouplingConfig,
    asym_x: float = 0.0,
    asym_y: float = 0.0,
) -> tuple[float, float, dict[str, Any]]:
    meta: dict[str, Any] = {
        "mode": cfg.mode,
        "type": cfg.type,
        "applied": False,
        "target": (0.0, 0.0),
        "magnitude_source": None,
        "direction_source": None,
        "gain": 1.0,
        "asymmetry": (float(asym_x), float(asym_y)),
    }
    if not cfg.enabled:
        return float(motor_ux), float(motor_uy), meta

    s_now = site_means(c_now)
    if cfg.use_delta:
        if c_prev is None:
            s_feat = np.zeros_like(s_now)
            c_energy = 0.0
        else:
            s_feat = s_now - site_means(c_prev)
            dc = np.asarray(c_now, dtype=np.float64) - np.asarray(c_prev, dtype=np.float64)
            c_energy = float(np.linalg.norm(dc))
    else:
        s_feat = s_now
        c_energy = float(np.linalg.norm(s_now))

    tx, ty = morphological_target(s_feat)
    site_mag = float(np.hypot(tx, ty))

    gain = 1.0
    if cfg.body_b_gain and body_B is not None:
        gain = float(np.tanh(np.linalg.norm(np.asarray(body_B, dtype=np.float64))))
        meta["gain"] = gain
    strength = float(cfg.strength) * gain

    if cfg.prefer_site_differential and site_mag > float(cfg.site_diff_eps):
        target_x, target_y = tx, ty
        meta["magnitude_source"] = "site_delta_differential"
        meta["direction_source"] = "footprint_registered_sites"
    else:
        # Magnitude from total internal change energy; direction from local asymmetry.
        dx, dy = unit(float(asym_x), float(asym_y))
        mag = c_energy if cfg.use_delta else float(np.linalg.norm(s_now))
        target_x, target_y = mag * dx, mag * dy
        meta["magnitude_source"] = "internal_delta_energy" if cfg.use_delta else "internal_level_energy"
        meta["direction_source"] = (
            "local_physical_asymmetry" if (abs(dx) + abs(dy)) > 0 else "NONE_NO_ARBITRARY_COMPASS"
        )

    ux = (1.0 - float(cfg.decay)) * float(motor_ux) + strength * target_x
    uy = (1.0 - float(cfg.decay)) * float(motor_uy) + strength * target_y
    mag = float(np.hypot(ux, uy))
    sat = float(cfg.saturation)
    if mag > sat and mag > 1e-15:
        ux *= sat / mag
        uy *= sat / mag
    meta.update({"applied": True, "target": (float(target_x), float(target_y)), "c_energy": c_energy, "site_mag": site_mag})
    return float(ux), float(uy), meta


def local_asymmetry_from_world(
    *,
    body_x: float,
    body_y: float,
    planet,
    body_vx: float = 0.0,
    body_vy: float = 0.0,
) -> tuple[float, float, str]:
    """Existing physical asymmetries only: local flow, else -grad T, else velocity."""
    h, w = planet.T.shape
    iy = int(np.floor(body_y)) % h
    ix = int(np.floor(body_x)) % w
    vx = float(planet.vx[iy, ix])
    vy = float(planet.vy[iy, ix])
    if abs(vx) + abs(vy) > 1e-12:
        return vx, vy, "local_planet_flow"
    # central differences on T (periodic)
    dTx = 0.5 * (float(planet.T[iy, (ix + 1) % w]) - float(planet.T[iy, (ix - 1) % w]))
    dTy = 0.5 * (float(planet.T[(iy + 1) % h, ix]) - float(planet.T[(iy - 1) % h, ix]))
    # force along -grad T (same pressure-like convention as planet flow)
    if abs(dTx) + abs(dTy) > 1e-12:
        return -dTx, -dTy, "local_minus_grad_T"
    if abs(body_vx) + abs(body_vy) > 1e-12:
        return float(body_vx), float(body_vy), "existing_velocity"
    return 0.0, 0.0, "NONE"
