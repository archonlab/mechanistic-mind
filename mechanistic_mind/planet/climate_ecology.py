"""Experimental spatiotemporal climate / resource ecology.

Default OFF. Hidden phase and latitude exist only inside world physics.
Cognition never receives season, latitude, biome, or cycle-phase labels.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any
import hashlib

import numpy as np

from mechanistic_mind.planet.topology import laplacian


def _unit_hash(seed: int, key: int) -> float:
    x = (int(seed) * 1000003 + int(key) * 9176 + 1) % 2147483647
    return (x % 1000000) / 1000000.0


@dataclass
class ClimateEcologyConfig:
    """Independently selectable experimental world. Missing/legacy → OFF."""

    enabled: bool = False
    # Long environmental cycle (hidden). Not a calendar and not an observation.
    season_period: int = 80
    cycle_mode: str = "periodic"  # periodic | aperiodic | stationary
    aperiodic_jitter: float = 0.35
    temperature_cycle_enabled: bool = True
    # Short independent cycle (hidden). Default OFF so primary seasonal tests stay clean.
    short_cycle_enabled: bool = False
    short_cycle_period: int = 8
    short_cycle_amp: float = 0.035
    # Continuous latitudinal climate. y=0 is the colder baseline edge.
    gradient_amp: float = 0.14
    belt_amp: float = 0.32
    belt_width: float = 0.40
    subsolar_amp: float = 0.70
    # Latitude bias for the moving thermal belt center. Default 0 = symmetric
    # N↔S sweep (two passages/cycle near equator). Nonzero bias prefers one
    # hemisphere so a local cell sees one dominant pulse per climate period.
    subsolar_bias: float = 0.0
    climate_baseline: float = 0.34
    insolation_gain: float = 0.18
    local_var_amp: float = 0.025
    # How often local_var spatial noise is redrawn (ticks). Default 11 preserves legacy.
    local_var_period: int = 11
    # Resource ecology — independently controllable from climate dynamics (Beta 2).
    # Legacy ``resources_enabled`` remains for serialization; prefer A/B flags.
    resources_enabled: bool = True
    resource_ecology_A_enabled: bool = True
    resource_ecology_B_enabled: bool = True
    resource_suitability_source: str = "local_T"  # local_T | independent_phase
    resource_phase_offset: float = 0.0
    resource_phase_mode: str = "coupled"  # coupled | independent | randomized
    RA_T_opt: float = 0.62
    RB_T_opt: float = 0.36
    RA_T_width: float = 0.11
    RB_T_width: float = 0.12
    RA_productivity: float = 0.055
    RB_productivity: float = 0.048
    RA_decay: float = 0.018
    RB_decay: float = 0.028
    RA_capacity: float = 1.40
    RB_capacity: float = 1.10
    resource_diffuse: float = 0.030
    resource_seed_frac: float = 0.08
    # Geography-conditioned suitability (static when terrain is static). Default OFF.
    # Physical response curves only — never semantic VALLEY=FOOD / HIGH=BAD.
    geography_resources_enabled: bool = False
    geography_mix: float = 0.55  # blend weight for geography vs T suitability
    # R_A prefers moderate-low potential basins with low gradient / moderate drag.
    RA_potential_center: float = -0.25
    RA_potential_width: float = 0.45
    RA_grad_penalty: float = 0.8
    RA_drag_center: float = 0.25
    RA_drag_width: float = 0.40
    # R_B prefers mid-slope / higher potential with different drag preference.
    RB_potential_center: float = 0.20
    RB_potential_width: float = 0.50
    RB_grad_penalty: float = 0.35
    RB_drag_center: float = 0.45
    RB_drag_width: float = 0.35
    geography_local_noise: float = 0.08  # seeded local variation (not terrain RNG)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Keep legacy flag coherent with A/B for older readers.
        d["resources_enabled"] = bool(self.resource_ecology_A_enabled or self.resource_ecology_B_enabled)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ClimateEcologyConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in cls.__dataclass_fields__ if k in data}
        # Legacy: only resources_enabled present → apply to both A and B.
        if "resource_ecology_A_enabled" not in data and "resource_ecology_B_enabled" not in data:
            both = bool(data.get("resources_enabled", True))
            payload["resource_ecology_A_enabled"] = both
            payload["resource_ecology_B_enabled"] = both
        return cls(**payload)


def resource_ecology_A_on(cfg: ClimateEcologyConfig | None) -> bool:
    if cfg is None:
        return False
    return bool(getattr(cfg, "resource_ecology_A_enabled", True))


def resource_ecology_B_on(cfg: ClimateEcologyConfig | None) -> bool:
    if cfg is None:
        return False
    return bool(getattr(cfg, "resource_ecology_B_enabled", True))


def resource_ecology_any(cfg: ClimateEcologyConfig | None) -> bool:
    return resource_ecology_A_on(cfg) or resource_ecology_B_on(cfg)


def experimental_climate_planet_kwargs() -> dict[str, Any]:
    """Preset for the experimental world. Does not alter CURRENT MM defaults."""
    return {
        "climate_ecology": ClimateEcologyConfig(
            enabled=True,
            resources_enabled=True,
            resource_ecology_A_enabled=True,
            resource_ecology_B_enabled=True,
        ),
        # Keep existing ambient machinery as bounded local variation, not a competing climate.
        "F_fast_amp": 0.08,
        "F_slow_amp": 0.10,
        "F_irregular_amp": 0.02,
        "T_ref": 0.40,
    }


def experimental_climate_planet_config(**overrides: Any):
    from mechanistic_mind.planet.config import PlanetConfig

    kw = experimental_climate_planet_kwargs()
    kw.update(overrides)
    return PlanetConfig(**kw)


def latitude_axis(height: int) -> np.ndarray:
    """Hidden north→south coordinate in [-1, +1]. y=0 is the colder baseline edge."""
    h = max(1, int(height))
    if h == 1:
        return np.zeros(1, dtype=np.float64)
    return (2.0 * np.arange(h, dtype=np.float64) / (h - 1)) - 1.0


def latitude_field(height: int, width: int) -> np.ndarray:
    phi = latitude_axis(height)
    return np.repeat(phi[:, None], int(width), axis=1)


def cycle_period_for_index(cfg: ClimateEcologyConfig, seed: int, cycle_index: int) -> int:
    base = max(8, int(cfg.season_period))
    if str(cfg.cycle_mode).lower() != "aperiodic":
        return base
    u = _unit_hash(int(seed) + 9041, int(cycle_index))
    jitter = float(np.clip(cfg.aperiodic_jitter, 0.0, 0.9))
    period = int(round(base * (1.0 + jitter * (2.0 * u - 1.0))))
    return max(8, period)


def season_phase_state(cfg: ClimateEcologyConfig, tick: int, seed: int) -> dict[str, Any]:
    """Hidden cycle phase in [0, 1). Never an agent observation."""
    tick = max(0, int(tick))
    mode = str(cfg.cycle_mode).lower()
    if mode == "stationary":
        return {"phase": 0.0, "cycle_index": 0, "period": int(cfg.season_period), "mode": mode}
    if mode != "aperiodic":
        period = max(8, int(cfg.season_period))
        return {
            "phase": (tick / period) % 1.0,
            "cycle_index": tick // period,
            "period": period,
            "mode": "periodic",
        }
    t0 = 0
    idx = 0
    while True:
        period = cycle_period_for_index(cfg, seed, idx)
        if tick < t0 + period:
            return {
                "phase": (tick - t0) / float(period),
                "cycle_index": idx,
                "period": period,
                "mode": "aperiodic",
            }
        t0 += period
        idx += 1
        if idx > 100000:
            return {"phase": 0.0, "cycle_index": idx, "period": period, "mode": "aperiodic"}


def resource_phase_state(cfg: ClimateEcologyConfig, tick: int, seed: int) -> dict[str, Any]:
    season = season_phase_state(cfg, tick, seed)
    mode = str(cfg.resource_phase_mode).lower()
    if mode == "coupled":
        phase = (float(season["phase"]) + float(cfg.resource_phase_offset)) % 1.0
        return {**season, "phase": phase, "resource_mode": mode}
    if mode == "independent":
        alt = ClimateEcologyConfig(
            **{
                **cfg.to_dict(),
                "cycle_mode": "periodic" if cfg.cycle_mode == "stationary" else cfg.cycle_mode,
                "season_period": max(8, int(round(cfg.season_period * 1.37))),
            }
        )
        other = season_phase_state(alt, tick, seed + 17)
        return {**other, "resource_mode": mode}
    # randomized: same mean period, phase offset hashed per cycle
    u = _unit_hash(int(seed) + 44027, int(season["cycle_index"]))
    phase = (float(season["phase"]) + u) % 1.0
    return {**season, "phase": phase, "resource_mode": "randomized"}


def _phi_sun(cfg: ClimateEcologyConfig, phase: float, *, force_cycle: bool = False) -> float:
    if not force_cycle:
        if not bool(cfg.temperature_cycle_enabled):
            return float(getattr(cfg, "subsolar_bias", 0.0) or 0.0)
        if str(cfg.cycle_mode).lower() == "stationary":
            return float(getattr(cfg, "subsolar_bias", 0.0) or 0.0)
    bias = float(getattr(cfg, "subsolar_bias", 0.0) or 0.0)
    return bias + float(cfg.subsolar_amp) * float(np.sin(2.0 * np.pi * phase))


def equilibrium_temperature(
    cfg: ClimateEcologyConfig,
    tick: int,
    height: int,
    width: int,
    *,
    seed: int = 17,
    phase: float | None = None,
    force_cycle: bool = False,
) -> np.ndarray:
    h, w = int(height), int(width)
    if phase is None:
        phase = float(season_phase_state(cfg, tick, seed)["phase"])
    phi = latitude_field(h, w)
    sun = _phi_sun(cfg, float(phase), force_cycle=force_cycle)
    width_b = max(1e-6, float(cfg.belt_width))
    belt = np.exp(-0.5 * ((phi - sun) / width_b) ** 2)
    T_eq = float(cfg.climate_baseline) + float(cfg.gradient_amp) * phi + float(cfg.belt_amp) * belt
    if cfg.short_cycle_enabled:
        p = max(2, int(cfg.short_cycle_period))
        T_eq = T_eq + float(cfg.short_cycle_amp) * np.sin(2.0 * np.pi * (tick % p) / p)
    if cfg.local_var_amp > 0.0:
        refresh = max(1, int(getattr(cfg, "local_var_period", 11) or 11))
        rng = np.random.default_rng((int(seed) * 100003 + (int(tick) // refresh) * 9176) & 0xFFFFFFFF)
        z = rng.standard_normal((h, w))
        z = (z + np.roll(z, 1, 0) + np.roll(z, -1, 0) + np.roll(z, 1, 1) + np.roll(z, -1, 1)) / 5.0
        z = (z - z.mean()) / (z.std() + 1e-8)
        T_eq = T_eq + float(cfg.local_var_amp) * z
    return np.clip(T_eq, 0.0, 1.0)


def climate_insolation(
    cfg: ClimateEcologyConfig,
    tick: int,
    height: int,
    width: int,
    *,
    seed: int = 17,
    phase: float | None = None,
) -> np.ndarray:
    """Non-negative energy flux from the moving climate belt. Not a DAY/NIGHT label."""
    if not cfg.enabled:
        return np.zeros((int(height), int(width)), dtype=np.float64)
    T_eq = equilibrium_temperature(cfg, tick, height, width, seed=seed, phase=phase)
    return np.clip(float(cfg.insolation_gain) * T_eq, 0.0, 1.5)


def _suitability(T: np.ndarray, opt: float, width: float) -> np.ndarray:
    w = max(1e-6, float(width))
    return np.exp(-0.5 * ((np.asarray(T, dtype=np.float64) - float(opt)) / w) ** 2)


def _geo_channel_suitability(
    *,
    potential: np.ndarray,
    grad_mag: np.ndarray,
    drag: np.ndarray,
    pot_center: float,
    pot_width: float,
    grad_penalty: float,
    drag_center: float,
    drag_width: float,
) -> np.ndarray:
    """Bounded physical response — not semantic terrain labels."""
    pot_s = np.exp(
        -0.5 * ((potential - float(pot_center)) / max(1e-6, float(pot_width))) ** 2
    )
    drag_s = np.exp(
        -0.5 * ((drag - float(drag_center)) / max(1e-6, float(drag_width))) ** 2
    )
    grad_s = np.exp(-float(grad_penalty) * np.asarray(grad_mag, dtype=np.float64))
    s = pot_s * drag_s * grad_s
    return np.clip(s, 0.0, 1.0)


def geography_resource_suitability(
    cfg: ClimateEcologyConfig,
    *,
    potential: np.ndarray,
    drag: np.ndarray,
    grad_x: np.ndarray,
    grad_y: np.ndarray,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Precomputable geography suitability for R_A / R_B (Observer may show; cognition must not)."""
    mag = np.hypot(np.asarray(grad_x, dtype=np.float64), np.asarray(grad_y, dtype=np.float64))
    pot = np.asarray(potential, dtype=np.float64)
    dr = np.asarray(drag, dtype=np.float64)
    suit_A = _geo_channel_suitability(
        potential=pot,
        grad_mag=mag,
        drag=dr,
        pot_center=cfg.RA_potential_center,
        pot_width=cfg.RA_potential_width,
        grad_penalty=cfg.RA_grad_penalty,
        drag_center=cfg.RA_drag_center,
        drag_width=cfg.RA_drag_width,
    )
    suit_B = _geo_channel_suitability(
        potential=pot,
        grad_mag=mag,
        drag=dr,
        pot_center=cfg.RB_potential_center,
        pot_width=cfg.RB_potential_width,
        grad_penalty=cfg.RB_grad_penalty,
        drag_center=cfg.RB_drag_center,
        drag_width=cfg.RB_drag_width,
    )
    # Independent resource geography noise stream (not terrain RNG).
    payload = f"{int(seed)}\0resource_geography\0v1".encode("utf-8")
    digest = hashlib.sha256(payload).digest()
    noise_seed = int.from_bytes(digest[:8], "big") & 0x7FFFFFFF
    rng = np.random.default_rng(noise_seed)
    amp = float(cfg.geography_local_noise)
    if amp > 0.0:
        nA = rng.standard_normal(pot.shape)
        nB = rng.standard_normal(pot.shape)
        suit_A = np.clip(suit_A * (1.0 + amp * nA), 0.0, 1.0)
        suit_B = np.clip(suit_B * (1.0 + amp * nB), 0.0, 1.0)
    return suit_A, suit_B


def resource_suitability_fields(
    cfg: ClimateEcologyConfig,
    T: np.ndarray,
    tick: int,
    *,
    seed: int = 17,
    geo_suit_A: np.ndarray | None = None,
    geo_suit_B: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    h, w = T.shape
    if str(cfg.resource_suitability_source).lower() == "independent_phase":
        phase = float(resource_phase_state(cfg, tick, seed)["phase"])
        T_use = equilibrium_temperature(cfg, tick, h, w, seed=seed, phase=phase, force_cycle=True)
    else:
        T_use = T
    suit_A, suit_B = _suitability(T_use, cfg.RA_T_opt, cfg.RA_T_width), _suitability(
        T_use, cfg.RB_T_opt, cfg.RB_T_width
    )
    if (
        bool(getattr(cfg, "geography_resources_enabled", False))
        and geo_suit_A is not None
        and geo_suit_B is not None
    ):
        mix = float(np.clip(getattr(cfg, "geography_mix", 0.55), 0.0, 1.0))
        suit_A = (1.0 - mix) * suit_A + mix * np.asarray(geo_suit_A, dtype=np.float64)
        suit_B = (1.0 - mix) * suit_B + mix * np.asarray(geo_suit_B, dtype=np.float64)
    return suit_A, suit_B


def step_climate_resources(
    T: np.ndarray,
    R_A: np.ndarray,
    R_B: np.ndarray,
    cfg: ClimateEcologyConfig,
    tick: int,
    *,
    seed: int = 17,
    hetero: np.ndarray | None = None,
    geo_suit_A: np.ndarray | None = None,
    geo_suit_B: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Step environmental R_A / R_B ecology.

    Independent of ``cfg.enabled`` (climate dynamics gate).
    When climate is OFF, suitability still uses the current physical T field
    (ordinary thermal state) — no substituted comfort constants.
    Disabling A or B freezes that field's environmental ecology without
    zeroing existing stock or touching body inventories.
    """
    a_on = resource_ecology_A_on(cfg)
    b_on = resource_ecology_B_on(cfg)
    if not a_on and not b_on:
        return R_A, R_B
    suit_A, suit_B = resource_suitability_fields(
        cfg, T, tick, seed=seed, geo_suit_A=geo_suit_A, geo_suit_B=geo_suit_B
    )
    het = np.ones_like(T) if hetero is None else np.clip(np.asarray(hetero, dtype=np.float64), 0.4, 1.8)
    het = 0.85 + 0.25 * (het - 1.0)
    RA = np.asarray(R_A, dtype=np.float64)
    RB = np.asarray(R_B, dtype=np.float64)
    cap_A = max(1e-6, float(cfg.RA_capacity))
    cap_B = max(1e-6, float(cfg.RB_capacity))
    if a_on:
        prod_A = float(cfg.RA_productivity) * suit_A * het * (1.0 - np.clip(RA, 0.0, cap_A) / cap_A)
        RA = RA + prod_A - float(cfg.RA_decay) * RA
        if cfg.resource_diffuse > 0.0:
            RA = RA + float(cfg.resource_diffuse) * laplacian(RA)
        RA = np.clip(RA, 0.0, cap_A)
    if b_on:
        prod_B = float(cfg.RB_productivity) * suit_B * het * (1.0 - np.clip(RB, 0.0, cap_B) / cap_B)
        RB = RB + prod_B - float(cfg.RB_decay) * RB
        if cfg.resource_diffuse > 0.0:
            RB = RB + float(cfg.resource_diffuse) * laplacian(RB)
        RB = np.clip(RB, 0.0, cap_B)
    return RA, RB


def initial_temperature_field(
    cfg: ClimateEcologyConfig,
    height: int,
    width: int,
    *,
    seed: int = 17,
) -> np.ndarray:
    return equilibrium_temperature(cfg, 0, height, width, seed=seed)


def initial_resource_fields(
    cfg: ClimateEcologyConfig,
    T: np.ndarray,
    *,
    seed: int = 17,
    geo_suit_A: np.ndarray | None = None,
    geo_suit_B: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    suit_A, suit_B = resource_suitability_fields(
        cfg, T, 0, seed=seed, geo_suit_A=geo_suit_A, geo_suit_B=geo_suit_B
    )
    RA = float(cfg.resource_seed_frac) * float(cfg.RA_capacity) * suit_A
    RB = float(cfg.resource_seed_frac) * float(cfg.RB_capacity) * suit_B
    return np.clip(RA, 0.0, cfg.RA_capacity), np.clip(RB, 0.0, cfg.RB_capacity)


def observer_climate_ground_truth(
    cfg: ClimateEcologyConfig,
    tick: int,
    *,
    seed: int = 17,
    T: np.ndarray | None = None,
    R_A: np.ndarray | None = None,
    R_B: np.ndarray | None = None,
) -> dict[str, Any]:
    """EXPERIMENT / WORLD GROUND TRUTH only. Forbidden in agent observation."""
    if not cfg.enabled:
        return {"enabled": False, "panel": "OBSERVER_GROUND_TRUTH_EXPERIMENT"}
    season = season_phase_state(cfg, tick, seed)
    resource = resource_phase_state(cfg, tick, seed)
    out: dict[str, Any] = {
        "enabled": True,
        "panel": "OBSERVER_GROUND_TRUTH_EXPERIMENT",
        "environmental_cycle_phase": float(season["phase"]),
        "environmental_cycle_index": int(season["cycle_index"]),
        "environmental_cycle_period": int(season["period"]),
        "environmental_cycle_mode": season["mode"],
        "phase_velocity_per_tick": (1.0 / max(1, int(season["period"]))),
        "ticks_per_full_cycle": int(season["period"]),
        "resource_cycle_phase": float(resource["phase"]),
        "short_cycle_enabled": bool(cfg.short_cycle_enabled),
        "temporal_calibration": {
            "season_period": int(season["period"]),
            "subsolar_bias": float(getattr(cfg, "subsolar_bias", 0.0) or 0.0),
            "local_var_period": int(getattr(cfg, "local_var_period", 11) or 11),
            "note": (
                "Observer temporal diagnostics only. Not agent-visible. "
                "BODY:CLIMATE ratio requires calibration harness output."
            ),
        },
        "note": "Hidden physical cycle phase. Not present in agent_observation or cognition.",
    }
    if T is not None:
        arr = np.asarray(T, dtype=np.float64)
        h = arr.shape[0]
        out["T_north_mean"] = float(arr[: max(1, h // 4)].mean())
        out["T_mid_mean"] = float(arr[h // 2 - 1 : h // 2 + 2].mean()) if h >= 3 else float(arr.mean())
        out["T_south_mean"] = float(arr[3 * h // 4 :].mean())
        out["T_max_y"] = int(np.unravel_index(int(np.argmax(arr)), arr.shape)[0])
    if R_A is not None:
        ra = np.asarray(R_A, dtype=np.float64)
        out["R_A_sum"] = float(ra.sum())
        out["R_A_max_y"] = int(np.unravel_index(int(np.argmax(ra)), ra.shape)[0]) if ra.size else 0
    if R_B is not None:
        rb = np.asarray(R_B, dtype=np.float64)
        out["R_B_sum"] = float(rb.sum())
        out["R_B_max_y"] = int(np.unravel_index(int(np.argmax(rb)), rb.shape)[0]) if rb.size else 0
    return out


def field_phase_row(cfg: ClimateEcologyConfig, tick: int, seed: int, T, R_A, R_B, vx=None, vy=None) -> dict[str, Any]:
    T = np.asarray(T, dtype=np.float64)
    RA = np.asarray(R_A, dtype=np.float64)
    RB = np.asarray(R_B, dtype=np.float64)
    h, w = T.shape
    north, mid, south = slice(0, max(1, h // 4)), slice(h // 2 - 1, h // 2 + 2), slice(3 * h // 4, h)
    season = season_phase_state(cfg, tick, seed)
    ra_idx = int(np.argmax(RA)) if RA.size else 0
    rb_idx = int(np.argmax(RB)) if RB.size else 0
    t_idx = int(np.argmax(T)) if T.size else 0
    row = {
        "tick": int(tick),
        "seed": int(seed),
        "phase": float(season["phase"]),
        "cycle_index": int(season["cycle_index"]),
        "T_mean": float(T.mean()),
        "T_min": float(T.min()),
        "T_max": float(T.max()),
        "T_north_mean": float(T[north].mean()),
        "T_mid_mean": float(T[mid].mean()) if h >= 3 else float(T.mean()),
        "T_south_mean": float(T[south].mean()),
        "T_max_y": int(np.unravel_index(t_idx, T.shape)[0]),
        "T_max_x": int(np.unravel_index(t_idx, T.shape)[1]),
        "R_A_sum": float(RA.sum()),
        "R_A_max": float(RA.max()),
        "R_A_max_y": int(np.unravel_index(ra_idx, RA.shape)[0]),
        "R_A_max_x": int(np.unravel_index(ra_idx, RA.shape)[1]),
        "R_B_sum": float(RB.sum()),
        "R_B_max": float(RB.max()),
        "R_B_max_y": int(np.unravel_index(rb_idx, RB.shape)[0]),
        "R_B_max_x": int(np.unravel_index(rb_idx, RB.shape)[1]),
        "R_A_north": float(RA[north].mean()),
        "R_A_south": float(RA[south].mean()),
        "R_B_north": float(RB[north].mean()),
        "R_B_south": float(RB[south].mean()),
        "flow_speed_mean": 0.0,
    }
    if vx is not None and vy is not None:
        row["flow_speed_mean"] = float(np.hypot(np.asarray(vx), np.asarray(vy)).mean())
    return row
