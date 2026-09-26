"""PlanetState — full-grid toroidal physical substrate (no organism)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from mechanistic_mind.planet.boundary import ExternalMaterialBoundary, off_boundary
from mechanistic_mind.planet.config import PlanetConfig, default_planet_config
from mechanistic_mind.planet.topology import wrap_coord


@dataclass
class PlanetState:
    tick: int
    T: np.ndarray
    M: np.ndarray  # (3, H, W)
    vx: np.ndarray
    vy: np.ndarray
    u: np.ndarray
    u_prev: np.ndarray
    capacity: np.ndarray
    conductivity: np.ndarray
    # budgets
    matter_initial: float
    energy_in_cum: float
    energy_diss_cum: float
    clip_counts: dict[str, int]
    # OPEN-5 external material boundary (default OFF)
    external_material_boundary: ExternalMaterialBoundary
    R: np.ndarray | None = None  # transferable_resource (H,W); unused until env-resource mechanism ON
    R_A: np.ndarray | None = None  # complementary retained stock
    R_B: np.ndarray | None = None  # complementary volatile stock
    FIELD_A: np.ndarray | None = None  # experimental physical signal amplitude; default absent
    FIELD_B: np.ndarray | None = None
    # Oscillatory band energy (n_bands, H, W); Option B alongside FIELD_A/B. Default absent.
    OSC_BANDS: np.ndarray | None = None
    # Spatial terrain (optional). None when terrain disabled / legacy snapshots.
    terrain_potential: np.ndarray | None = None
    terrain_drag: np.ndarray | None = None  # always >= 0 when present
    terrain_grad_y: np.ndarray | None = None
    terrain_grad_x: np.ndarray | None = None
    terrain_meta: dict | None = None
    # Precomputed geography-conditioned resource suitability (Observer GT; not cognition).
    resource_geo_suit_A: np.ndarray | None = None
    resource_geo_suit_B: np.ndarray | None = None
    # Static ambient horizontal force (optional). None when disabled.
    ambient_fx: np.ndarray | None = None
    ambient_fy: np.ndarray | None = None
    ambient_meta: dict | None = None
    # Surface observable response (WORLD GT for near-field exteroception). Static.
    surface_response: np.ndarray | None = None
    surface_meta: dict | None = None
    # Last computed global illumination intensity (Observer cache; not cognition).
    illumination_intensity: float | None = None
    illumination_meta: dict | None = None
    # Multi-channel optical appearance (WORLD GT; FOV-gated surface_c* only).
    surface_optical: np.ndarray | None = None  # (3, H, W) when discrimination LOW/RICH
    surface_optical_meta: dict | None = None

    def copy(self) -> "PlanetState":
        return PlanetState(
            tick=self.tick,
            T=self.T.copy(),
            M=self.M.copy(),
            vx=self.vx.copy(),
            vy=self.vy.copy(),
            u=self.u.copy(),
            u_prev=self.u_prev.copy(),
            capacity=self.capacity.copy(),
            conductivity=self.conductivity.copy(),
            matter_initial=self.matter_initial,
            energy_in_cum=self.energy_in_cum,
            energy_diss_cum=self.energy_diss_cum,
            clip_counts=dict(self.clip_counts),
            external_material_boundary=self.external_material_boundary.copy(),
            R=None if getattr(self, "R", None) is None else np.asarray(self.R).copy(),
            R_A=None if getattr(self, "R_A", None) is None else np.asarray(self.R_A).copy(),
            R_B=None if getattr(self, "R_B", None) is None else np.asarray(self.R_B).copy(),
            FIELD_A=None if getattr(self, "FIELD_A", None) is None else np.asarray(self.FIELD_A).copy(),
            FIELD_B=None if getattr(self, "FIELD_B", None) is None else np.asarray(self.FIELD_B).copy(),
            OSC_BANDS=None if getattr(self, "OSC_BANDS", None) is None else np.asarray(self.OSC_BANDS).copy(),
            terrain_potential=(
                None if getattr(self, "terrain_potential", None) is None
                else np.asarray(self.terrain_potential).copy()
            ),
            terrain_drag=(
                None if getattr(self, "terrain_drag", None) is None
                else np.asarray(self.terrain_drag).copy()
            ),
            terrain_grad_y=(
                None if getattr(self, "terrain_grad_y", None) is None
                else np.asarray(self.terrain_grad_y).copy()
            ),
            terrain_grad_x=(
                None if getattr(self, "terrain_grad_x", None) is None
                else np.asarray(self.terrain_grad_x).copy()
            ),
            terrain_meta=(
                None if getattr(self, "terrain_meta", None) is None
                else dict(self.terrain_meta)
            ),
            resource_geo_suit_A=(
                None if getattr(self, "resource_geo_suit_A", None) is None
                else np.asarray(self.resource_geo_suit_A).copy()
            ),
            resource_geo_suit_B=(
                None if getattr(self, "resource_geo_suit_B", None) is None
                else np.asarray(self.resource_geo_suit_B).copy()
            ),
            ambient_fx=(
                None if getattr(self, "ambient_fx", None) is None
                else np.asarray(self.ambient_fx).copy()
            ),
            ambient_fy=(
                None if getattr(self, "ambient_fy", None) is None
                else np.asarray(self.ambient_fy).copy()
            ),
            ambient_meta=(
                None if getattr(self, "ambient_meta", None) is None
                else dict(self.ambient_meta)
            ),
            surface_response=(
                None if getattr(self, "surface_response", None) is None
                else np.asarray(self.surface_response).copy()
            ),
            surface_meta=(
                None if getattr(self, "surface_meta", None) is None
                else dict(self.surface_meta)
            ),
            illumination_intensity=getattr(self, "illumination_intensity", None),
            illumination_meta=(
                None if getattr(self, "illumination_meta", None) is None
                else dict(self.illumination_meta)
            ),
            surface_optical=(
                None if getattr(self, "surface_optical", None) is None
                else np.asarray(self.surface_optical).copy()
            ),
            surface_optical_meta=(
                None if getattr(self, "surface_optical_meta", None) is None
                else dict(self.surface_optical_meta)
            ),
        )


def _hetero(h: int, w: int, seed: int, amp: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    # smooth-ish: low-frequency random then blur by averaging neighbors once
    z = rng.standard_normal((h, w))
    z = (
        z
        + np.roll(z, 1, 0)
        + np.roll(z, -1, 0)
        + np.roll(z, 1, 1)
        + np.roll(z, -1, 1)
    ) / 5.0
    z = (z - z.mean()) / (z.std() + 1e-8)
    return np.clip(1.0 + amp * z, 0.4, 1.8)


def initialize_planet(config: PlanetConfig | None = None, *, seed: int = 17) -> PlanetState:
    cfg = config or default_planet_config()
    h, w = int(cfg.height), int(cfg.width)
    rng = np.random.default_rng(seed)
    T = np.full((h, w), cfg.T_ref, dtype=np.float64) + 0.02 * rng.standard_normal((h, w))
    T = np.clip(T, cfg.T_min, cfg.T_max)
    M = np.zeros((cfg.n_materials, h, w), dtype=np.float64)
    # initial matter blobs (physical, not resources)
    for k, (cy, cx, dens) in enumerate([(h // 3, w // 3, 0.55), (2 * h // 3, 2 * w // 3, 0.45), (h // 2, w // 5, 0.20)]):
        yy, xx = np.ogrid[:h, :w]
        # toroidal soft blob using wrapped deltas
        dy = ((yy - cy + h // 2) % h) - h // 2
        dx = ((xx - cx + w // 2) % w) - w // 2
        blob = dens * np.exp(-(dx * dx + dy * dy) / (2 * (4.0 ** 2)))
        M[min(k, cfg.n_materials - 1)] += blob
    M = np.clip(M, 0.0, 1.5)
    capacity = _hetero(h, w, seed + 101, cfg.hetero_amp_capacity)
    conductivity = _hetero(h, w, seed + 202, cfg.hetero_amp_conductivity)
    ce = getattr(cfg, "climate_ecology", None)
    if ce is not None and bool(getattr(ce, "enabled", False)):
        from mechanistic_mind.planet.climate_ecology import initial_temperature_field
        T = initial_temperature_field(ce, h, w, seed=seed)
    st = PlanetState(
        tick=0,
        T=T,
        M=M,
        vx=np.zeros((h, w), dtype=np.float64),
        vy=np.zeros((h, w), dtype=np.float64),
        u=np.zeros((h, w), dtype=np.float64),
        u_prev=np.zeros((h, w), dtype=np.float64),
        capacity=capacity,
        conductivity=conductivity,
        matter_initial=float(M.sum()),
        energy_in_cum=0.0,
        energy_diss_cum=0.0,
        clip_counts={"T": 0, "M": 0, "v": 0, "u": 0},
        external_material_boundary=off_boundary(cfg.n_materials),
        R=np.zeros((h, w), dtype=np.float64),
        R_A=np.zeros((h, w), dtype=np.float64),
        R_B=np.zeros((h, w), dtype=np.float64),
    )
    # Terrain first (static geography). Independent of climate/resource RNG.
    te = getattr(cfg, "terrain", None)
    if te is not None and bool(getattr(te, "enabled", False)):
        from mechanistic_mind.planet.terrain import install_terrain_on_planet
        install_terrain_on_planet(st, experiment_seed=seed, config=te)
    # Resources after terrain so geography suitability can be applied.
    # Independent of climate.enabled — A/B ecology gates only.
    from mechanistic_mind.planet.climate_ecology import resource_ecology_any
    if ce is not None and resource_ecology_any(ce):
        from mechanistic_mind.planet.climate_ecology import (
            geography_resource_suitability,
            initial_resource_fields,
            resource_ecology_A_on,
            resource_ecology_B_on,
        )
        geo_A = geo_B = None
        if (
            bool(getattr(ce, "geography_resources_enabled", False))
            and getattr(st, "terrain_potential", None) is not None
        ):
            geo_A, geo_B = geography_resource_suitability(
                ce,
                potential=st.terrain_potential,
                drag=st.terrain_drag,
                grad_x=st.terrain_grad_x,
                grad_y=st.terrain_grad_y,
                seed=seed,
            )
            st.resource_geo_suit_A = geo_A
            st.resource_geo_suit_B = geo_B
        ra0, rb0 = initial_resource_fields(
            ce, st.T, seed=seed, geo_suit_A=geo_A, geo_suit_B=geo_B
        )
        # Only seed channels whose ecology is enabled; leave zeros otherwise.
        st.R_A = ra0 if resource_ecology_A_on(ce) else np.zeros((h, w), dtype=np.float64)
        st.R_B = rb0 if resource_ecology_B_on(ce) else np.zeros((h, w), dtype=np.float64)
    # Ambient horizontal force (independent of terrain / climate / resource RNG).
    ae = getattr(cfg, "ambient", None)
    if ae is not None and bool(getattr(ae, "enabled", False)):
        from mechanistic_mind.planet.ambient import install_ambient_on_planet
        install_ambient_on_planet(st, experiment_seed=seed, config=ae)
    return st
