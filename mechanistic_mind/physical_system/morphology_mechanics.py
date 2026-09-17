"""Experimental distributed body morphology -> mechanical susceptibility.

DEFAULT OFF. Does not alter baseline when mode=OFF.
Does not emit discrete MOVE or motor_u commands.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any

import numpy as np

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.state import PlanetState
from mechanistic_mind.planet.topology import wrap_coord


@dataclass
class MorphologyMechanicsConfig:
    mode: str = "EXPERIMENTAL"  # OFF | EXPERIMENTAL — CURRENT INTEGRATED default; from_dict({}) stays OFF
    strength: float = 0.35  # susceptibility contrast
    site_mechanics_enabled: bool = True
    local_material_enabled: bool = True
    internal_site_coupling: bool = True
    kappa_site: float = 0.01
    permeability_scale: float = 1.0  # relative to body permeability
    include_wave: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MorphologyMechanicsConfig":
        # Missing/empty dict = historical PRE-INTEGRATION (OFF). Explicit keys load as given.
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"


def ensure_B_site(body: PhysicalBodyState, n_sites: int) -> np.ndarray:
    B_site = getattr(body, "B_site", None)
    if B_site is None or np.asarray(B_site).shape != (n_sites, 3):
        base = np.asarray(body.B, dtype=np.float64)
        B_site = np.tile(base, (n_sites, 1))
        body.B_site = B_site
    return np.asarray(body.B_site, dtype=np.float64)


def susceptibility(B_row: np.ndarray, strength: float) -> float:
    return float(1.0 + strength * np.tanh(np.linalg.norm(B_row)))


def step_morphology_mechanics(
    body: PhysicalBodyState,
    planet: PlanetState,
    body_cfg: PhysicalBodyConfig,
    morph_cfg: MorphologyMechanicsConfig,
    *,
    internal_c: np.ndarray | None = None,
) -> dict[str, Any]:
    """Experimental tick fragment: local B_site exchange + site forces.

    Call instead of / around baseline mechanical material when enabled.
    Returns diagnostic receipt; mutates body/planet/internal_c as configured.
    """
    meta: dict[str, Any] = {"enabled": False}
    if not morph_cfg.enabled:
        return meta

    h, w = planet.T.shape
    cells = body.cells(w, h, body_cfg.footprint)
    n_sites = len(cells)
    B_site = ensure_B_site(body, n_sites)
    meta["enabled"] = True
    meta["n_sites"] = n_sites

    # --- local material <-> WORLD ---
    if morph_cfg.local_material_enabled and body_cfg.material_enabled:
        for si, (iy, ix) in enumerate(cells):
            M_loc = planet.M[:, iy, ix]
            for k, perm in enumerate(body_cfg.permeability):
                p = float(perm) * float(morph_cfg.permeability_scale)
                flux = p * (float(M_loc[k]) - float(B_site[si, k]))
                if flux > 0:
                    flux = min(flux, float(M_loc[k]))
                else:
                    flux = -min(-flux, float(B_site[si, k]))
                B_site[si, k] = float(np.clip(B_site[si, k] + flux, 0.0, body_cfg.B_max))
                if body_cfg.material_backreact and abs(flux) > 0:
                    planet.M[k, iy, ix] = float(max(0.0, float(planet.M[k, iy, ix]) - flux))

    # --- internal.c[i] <-> B_site[i] ---
    if morph_cfg.internal_site_coupling and internal_c is not None:
        c = np.asarray(internal_c, dtype=np.float64)
        ns = min(n_sites, c.shape[0])
        for i in range(ns):
            for k in range(min(3, c.shape[1])):
                js = float(morph_cfg.kappa_site) * (float(B_site[i, k]) - float(c[i, k]))
                c[i, k] = float(c[i, k] + js)
                B_site[i, k] = float(np.clip(B_site[i, k] - js, 0.0, body_cfg.B_max))
        # write back
        internal_c[:] = np.clip(c, 0.0, None)

    # keep lumped B as mean for compatibility/observer
    body.B = np.clip(B_site.mean(axis=0), 0.0, body_cfg.B_max)
    body.B_site = B_site

    site_forces = []
    Fx = Fy = 0.0
    if morph_cfg.site_mechanics_enabled and body_cfg.mechanical_enabled:
        for si, (iy, ix) in enumerate(cells):
            vx_i = float(planet.vx[iy, ix])
            vy_i = float(planet.vy[iy, ix])
            u_i = float(planet.u[iy, ix])
            susc = susceptibility(B_site[si], morph_cfg.strength)
            fx = susc * body_cfg.flow_coupling * vx_i
            fy = susc * body_cfg.flow_coupling * vy_i
            if morph_cfg.include_wave:
                # local wave drive into force direction of local flow, else isotropic null
                if abs(vx_i) + abs(vy_i) < 1e-12:
                    wx, wy = 0.0, 0.0
                else:
                    n = float(np.hypot(vx_i, vy_i))
                    wx, wy = vx_i / n, vy_i / n
                fx += susc * 0.15 * body_cfg.wave_coupling * u_i * wx
                fy += susc * 0.15 * body_cfg.wave_coupling * u_i * wy
            site_forces.append({"site": si, "cell": [iy, ix], "susc": susc, "fx": fx, "fy": fy, "B_norm": float(np.linalg.norm(B_site[si]))})
            Fx += fx
            Fy += fy
        Fx /= max(1, n_sites)
        Fy /= max(1, n_sites)
        # CoM drag (baseline-like)
        Fx += -body_cfg.drag * body.vx
        Fy += -body_cfg.drag * body.vy
        body.vx = float(np.clip(body.vx + Fx / body_cfg.mass, -body_cfg.v_max, body_cfg.v_max))
        body.vy = float(np.clip(body.vy + Fy / body_cfg.mass, -body_cfg.v_max, body_cfg.v_max))
        if body_cfg.displacement_enabled:
            body.x = float(wrap_coord(body.x + body.vx, w))
            body.y = float(wrap_coord(body.y + body.vy, h))

    meta.update({
        "site_forces": site_forces,
        "net_force": [Fx, Fy],
        "B_site_norms": [float(np.linalg.norm(B_site[i])) for i in range(n_sites)],
        "B_site_spread": float(np.std([np.linalg.norm(B_site[i]) for i in range(n_sites)])),
    })
    return meta
