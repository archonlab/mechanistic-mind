"""Coupled physical update steps for MM-WORLD-1."""
from __future__ import annotations

import numpy as np

from mechanistic_mind.planet.boundary import step_external_material_boundary
from mechanistic_mind.planet.climate_ecology import (
    climate_insolation,
    equilibrium_temperature,
    step_climate_resources,
)
from mechanistic_mind.planet.config import PlanetConfig
from mechanistic_mind.planet.forcing import forcing_field
from mechanistic_mind.planet.state import PlanetState
from mechanistic_mind.planet.topology import gradient, laplacian, roll2


def _clip_count(arr: np.ndarray, lo: float, hi: float) -> tuple[np.ndarray, int]:
    clipped = np.clip(arr, lo, hi)
    n = int(np.sum((arr < lo) | (arr > hi)))
    return clipped, n


def step_thermal(
    state: PlanetState,
    F: np.ndarray,
    cfg: PlanetConfig,
    *,
    T_eq: np.ndarray | None = None,
) -> None:
    if not cfg.thermal_from_forcing:
        incoming = 0.0
        F_eff = np.zeros_like(state.T)
    else:
        F_eff = F
        incoming = float(F.sum())
    T_rest = cfg.T_ref if T_eq is None else T_eq
    # capacity slows response; conductivity scales diffusion
    dT = (
        cfg.heat_gain * F_eff / state.capacity
        - cfg.cool_rate * (state.T - T_rest)
        + cfg.kappa_base * state.conductivity * laplacian(state.T)
    )
    state.T = state.T + dT
    state.T, n = _clip_count(state.T, cfg.T_min, cfg.T_max)
    state.clip_counts["T"] += n
    state.energy_in_cum += incoming * cfg.heat_gain
    state.energy_diss_cum += float(np.sum(cfg.cool_rate * np.maximum(state.T - cfg.T_ref, 0.0)))


def step_flow(state: PlanetState, cfg: PlanetConfig) -> None:
    if not cfg.flow_enabled:
        state.vx *= 1.0 - cfg.flow_damp
        state.vy *= 1.0 - cfg.flow_damp
        return
    dTy, dTx = gradient(state.T)
    # pressure-like tendency ~ -grad T (warm rises conceptually as outflow from hot)
    ax = -cfg.flow_gain * dTx
    ay = -cfg.flow_gain * dTy
    state.vx = (1.0 - cfg.flow_damp) * state.vx + ax
    state.vy = (1.0 - cfg.flow_damp) * state.vy + ay
    speed = np.hypot(state.vx, state.vy)
    over = speed > cfg.flow_max
    if np.any(over):
        scale = np.ones_like(speed)
        scale[over] = cfg.flow_max / (speed[over] + 1e-12)
        state.vx *= scale
        state.vy *= scale
        state.clip_counts["v"] += int(np.sum(over))


def _advect_scalar(field: np.ndarray, vx: np.ndarray, vy: np.ndarray, strength: float) -> np.ndarray:
    """Donor-cell flux-form advection on torus (approx conservative)."""
    # horizontal fluxes on left edges of cells
    vx_face = 0.5 * (vx + roll2(vx, 0, 1))
    # donor from left if flow +x into cell from left neighbor
    flux_x = np.where(
        vx_face >= 0.0,
        vx_face * roll2(field, 0, 1),
        vx_face * field,
    )
    # divergence: flux_in_from_left - flux_out_to_right
    div_x = flux_x - roll2(flux_x, 0, -1)

    vy_face = 0.5 * (vy + roll2(vy, 1, 0))
    flux_y = np.where(
        vy_face >= 0.0,
        vy_face * roll2(field, 1, 0),
        vy_face * field,
    )
    div_y = flux_y - roll2(flux_y, -1, 0)
    out = field - strength * (div_x + div_y)
    return out


def step_matter(state: PlanetState, cfg: PlanetConfig) -> None:
    M = state.M
    if cfg.diffusion_enabled:
        if cfg.diff_M0 > 0:
            M[0] = M[0] + cfg.diff_M0 * laplacian(M[0])
        if cfg.n_materials > 1 and cfg.diff_M1 > 0:
            M[1] = M[1] + cfg.diff_M1 * laplacian(M[1])
    if cfg.advection_enabled and cfg.flow_enabled:
        M[0] = _advect_scalar(M[0], state.vx, state.vy, cfg.advect_M0)
    # reaction M0 + M1 -> M2
    if cfg.reaction_enabled and cfg.n_materials >= 3:
        rate = cfg.react_rate * np.clip(state.T, 0.0, 1.0)
        consumed = rate * np.minimum(M[0], M[1])
        M[0] = M[0] - consumed
        M[1] = M[1] - consumed
        M[2] = M[2] + consumed
        state.T = state.T + cfg.react_heat * consumed
        state.T, n = _clip_count(state.T, cfg.T_min, cfg.T_max)
        state.clip_counts["T"] += n
    # soft phase-like exchange M0 <-> M2 with T
    if cfg.phase_enabled and cfg.n_materials >= 3:
        hot = np.clip((state.T - cfg.phase_T_hi) / 0.2, 0.0, 1.0)
        cold = np.clip((cfg.phase_T_lo - state.T) / 0.2, 0.0, 1.0)
        to2 = cfg.phase_rate * hot * M[0]
        to0 = cfg.phase_rate * cold * M[2]
        M[0] = M[0] - to2 + to0
        M[2] = M[2] + to2 - to0
    # upper bound
    over = M > 2.0
    if np.any(over):
        state.clip_counts["M"] += int(np.sum(over))
        M = np.minimum(M, 2.0)
    # mass-safe nonnegativity: raise negatives to 0 and remove equal mass from positives
    neg = M < 0.0
    if np.any(neg):
        created = float((-M[neg]).sum())
        state.clip_counts["M"] += int(np.sum(neg))
        M = np.maximum(M, 0.0)
        pos = M > 0.0
        pool = float(M[pos].sum())
        if pool > 1e-12 and created > 0.0:
            M[pos] *= max(0.0, 1.0 - created / pool)
    state.M = M


def step_wave(state: PlanetState, cfg: PlanetConfig, *, impulse: np.ndarray | None = None) -> None:
    if not cfg.wave_enabled:
        return
    # discrete wave: u_new = 2u - u_prev + c2*Lap(u) - damp*(u-u_prev) + source
    lap = laplacian(state.u)
    source = cfg.wave_source_gain * (
        np.hypot(state.vx, state.vy) * 0.15
        + np.maximum(laplacian(state.T), 0.0) * 0.05
    )
    if impulse is not None:
        source = source + impulse
    u_new = (
        (2.0 - cfg.wave_damp) * state.u
        - (1.0 - cfg.wave_damp) * state.u_prev
        + cfg.wave_c2 * lap
        + source
    )
    u_new, n = _clip_count(u_new, -2.0, 2.0)
    state.clip_counts["u"] += n
    state.u_prev = state.u
    state.u = u_new


def step_planet(
    state: PlanetState,
    cfg: PlanetConfig,
    *,
    seed: int = 17,
    impulse: np.ndarray | None = None,
) -> PlanetState:
    """One autonomous world tick. Mutates and returns state."""
    h, w = state.T.shape
    F = forcing_field(cfg, state.tick, h, w, seed=seed)
    ce = getattr(cfg, "climate_ecology", None)
    T_eq = None
    # Climate dynamics only (T_eq / seasonal insolation). Independent of resource ecology.
    if ce is not None and bool(getattr(ce, "enabled", False)):
        T_eq = equilibrium_temperature(ce, int(state.tick), h, w, seed=seed)
        F = np.clip(F + climate_insolation(ce, int(state.tick), h, w, seed=seed), 0.0, 1.5)
    step_thermal(state, F, cfg, T_eq=T_eq)
    step_flow(state, cfg)
    step_matter(state, cfg)
    step_wave(state, cfg, impulse=impulse)
    # Resource ecology: independent of climate.enabled. Uses current physical T.
    if ce is not None:
        from mechanistic_mind.planet.climate_ecology import resource_ecology_any
        if resource_ecology_any(ce):
            ra = state.R_A if state.R_A is not None else np.zeros((h, w), dtype=np.float64)
            rb = state.R_B if state.R_B is not None else np.zeros((h, w), dtype=np.float64)
            state.R_A, state.R_B = step_climate_resources(
                state.T, ra, rb, ce, int(state.tick), seed=seed, hetero=state.capacity,
                geo_suit_A=getattr(state, "resource_geo_suit_A", None),
                geo_suit_B=getattr(state, "resource_geo_suit_B", None),
            )
    # OPEN-5: external material boundary after wave; skip entirely when OFF
    step_external_material_boundary(state)
    state.tick += 1
    return state
