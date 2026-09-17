"""Flux-first interaction + intrinsic dynamics. No mid-calc foreign mutation."""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np

from mechanistic_mind.internal_medium.config import InternalMediumConfig, adjacency, EDGES
from mechanistic_mind.internal_medium.state import InternalMediumState
from mechanistic_mind.physical_body.state import PhysicalBodyState


@dataclass
class MediumFluxRecord:
    dc: np.ndarray          # (sites, species)
    dB: np.ndarray          # (species,)
    dB_core: np.ndarray     # (species,)
    J_s: np.ndarray
    J_c: np.ndarray
    material_residual: float


def compute_medium_fluxes(
    medium: InternalMediumState,
    body: PhysicalBodyState,
    cfg: InternalMediumConfig,
) -> MediumFluxRecord:
    ns, nk = cfg.n_sites, cfg.n_species
    c = medium.c
    dc = np.zeros((ns, nk), dtype=np.float64)
    dB = np.zeros(nk, dtype=np.float64)
    dBc = np.zeros(nk, dtype=np.float64)
    J_s = np.zeros((ns, nk), dtype=np.float64)
    J_c = np.zeros((ns, nk), dtype=np.float64)

    if not cfg.medium_enabled:
        return MediumFluxRecord(dc, dB, dBc, J_s, J_c, 0.0)

    # intrinsic diffusion
    if cfg.diffusion_enabled:
        for a, b in EDGES:
            for k in range(nk):
                flux = cfg.D * (c[b, k] - c[a, k])
                dc[a, k] += flux
                dc[b, k] -= flux

    # dissipation
    if cfg.dissipation_enabled:
        dc -= cfg.gamma * c

    # BODY coupling (same law both sides)
    if cfg.coupling_enabled:
        B = body.B.astype(np.float64)
        Bc = body.B_core.astype(np.float64)
        for i in range(ns):
            for k in range(nk):
                js = cfg.kappa_s * (float(B[k]) - float(c[i, k]))
                jc = cfg.kappa_c * (float(Bc[k]) - float(c[i, k]))
                J_s[i, k] = js
                J_c[i, k] = jc
                dc[i, k] += js + jc
                dB[k] -= js
                dBc[k] -= jc

    # accounting residual for exchange part only (ignore diffusion/dissipation)
    exch_dc = J_s + J_c
    residual = float(np.sum(exch_dc) + np.sum(dB) + np.sum(dBc))
    return MediumFluxRecord(dc=dc, dB=dB, dB_core=dBc, J_s=J_s, J_c=J_c, material_residual=residual)


def apply_medium_fluxes(
    medium: InternalMediumState,
    body: PhysicalBodyState,
    fluxes: MediumFluxRecord,
    cfg: InternalMediumConfig,
) -> None:
    """Apply accumulated deltas synchronously; clip concentrations."""
    if not cfg.medium_enabled:
        medium.tick += 1
        return
    medium.c = medium.c + fluxes.dc
    # mass-safe nonnegativity + upper bound
    over = medium.c > cfg.C_max
    if np.any(over):
        medium.c = np.minimum(medium.c, cfg.C_max)
    neg = medium.c < 0.0
    if np.any(neg):
        created = float((-medium.c[neg]).sum())
        medium.c = np.maximum(medium.c, 0.0)
        pos = medium.c > 0.0
        pool = float(medium.c[pos].sum())
        if pool > 1e-12 and created > 0.0:
            medium.c[pos] *= max(0.0, 1.0 - created / pool)
    if cfg.coupling_enabled:
        body.B = np.clip(body.B + fluxes.dB, 0.0, cfg.C_max)
        body.B_core = np.clip(body.B_core + fluxes.dB_core, 0.0, cfg.C_max)
    medium.tick += 1


def step_internal_medium(
    medium: InternalMediumState,
    body: PhysicalBodyState,
    cfg: InternalMediumConfig,
) -> MediumFluxRecord:
    fluxes = compute_medium_fluxes(medium, body, cfg)
    apply_medium_fluxes(medium, body, fluxes, cfg)
    return fluxes
