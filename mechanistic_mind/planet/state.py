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
    if ce is not None and bool(getattr(ce, "enabled", False)) and bool(getattr(ce, "resources_enabled", True)):
        from mechanistic_mind.planet.climate_ecology import initial_resource_fields
        st.R_A, st.R_B = initial_resource_fields(ce, st.T, seed=seed)
    return st
