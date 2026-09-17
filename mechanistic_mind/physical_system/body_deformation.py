"""Bounded material-driven deformation in body-local coordinates.

The deformation is radial with respect to the existing rest footprint.  It
changes geometry only; it never writes velocity, position, theta, or omega.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from mechanistic_mind.physical_body.state import PhysicalBodyState


@dataclass
class BodyDeformationConfig:
    mode: str = "EXPERIMENTAL"  # fresh CURRENT INTEGRATED default
    material_drive_enabled: bool = True  # B_site -> deformation ablation
    geometry_coupling_enabled: bool = True  # deformation -> geometry ablation
    max_displacement: float = 0.65
    max_rate: float = 0.06
    material_gain: float = 0.35
    neutral_B_norm: float = 0.35
    relaxation: float = 0.12

    @property
    def enabled(self) -> bool:
        return str(self.mode).upper() == "EXPERIMENTAL"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "BodyDeformationConfig":
        # Historical snapshots/configs did not deform their fixed footprint.
        if not data:
            return cls(mode="OFF")
        return cls(**{k: data[k] for k in cls.__dataclass_fields__ if k in data})


def rest_geometry(footprint: tuple[tuple[int, int], ...]) -> np.ndarray:
    """Return body-local (x,y) site vectors from stored (dy,dx) offsets."""
    return np.asarray([(float(dx), float(dy)) for dy, dx in footprint], dtype=np.float64)


def radial_axes(rest: np.ndarray) -> np.ndarray:
    radii = np.linalg.norm(rest, axis=1)
    axes = np.zeros_like(rest)
    nz = radii > 1e-12
    axes[nz] = rest[nz] / radii[nz, None]
    return axes


def ensure_deformation(body: PhysicalBodyState, n_sites: int) -> np.ndarray:
    current = getattr(body, "deformation", None)
    if current is None or np.asarray(current).shape != (n_sites, 2):
        body.deformation = np.zeros((n_sites, 2), dtype=np.float64)
    return np.asarray(body.deformation, dtype=np.float64)


def step_deformation(
    body: PhysicalBodyState,
    footprint: tuple[tuple[int, int], ...],
    cfg: BodyDeformationConfig,
    work_cfg: Any | None = None,
    *,
    env_force_body: np.ndarray | None = None,
    work_budget: float | None = None,
) -> dict[str, Any]:
    """Advance local shape state; no translational or angular writes."""
    if work_cfg is not None:
        from mechanistic_mind.physical_system.deformation_work import apply_deformation_work

        return apply_deformation_work(
            body, footprint, cfg, work_cfg, env_force_body=env_force_body, work_budget=work_budget
        )
    rest = rest_geometry(footprint)
    d = ensure_deformation(body, len(rest))
    before = d.copy()
    axes = radial_axes(rest)
    B_site = getattr(body, "B_site", None)
    norms = (
        np.linalg.norm(np.asarray(B_site, dtype=np.float64), axis=1)
        if B_site is not None and np.asarray(B_site).shape[0] == len(rest)
        else np.full(len(rest), float(cfg.neutral_B_norm), dtype=np.float64)
    )
    if cfg.enabled and cfg.material_drive_enabled:
        scalar_target = np.clip(
            cfg.material_gain * (norms - float(cfg.neutral_B_norm)),
            -cfg.max_displacement,
            cfg.max_displacement,
        )
        target = axes * scalar_target[:, None]
    else:
        target = np.zeros_like(d)
    # First-order bounded material response with an explicit rest tendency.
    desired_delta = (target - d) * max(0.0, min(1.0, cfg.relaxation))
    lengths = np.linalg.norm(desired_delta, axis=1)
    scale = np.ones_like(lengths)
    nz = lengths > cfg.max_rate
    scale[nz] = cfg.max_rate / lengths[nz]
    d = d + desired_delta * scale[:, None]
    mag = np.linalg.norm(d, axis=1)
    over = mag > cfg.max_displacement
    d[over] *= (cfg.max_displacement / mag[over])[:, None]
    body.deformation = d
    used = d if cfg.enabled and cfg.geometry_coupling_enabled else np.zeros_like(d)
    actual = rest + used
    return {
        "enabled": bool(cfg.enabled),
        "material_drive_enabled": bool(cfg.material_drive_enabled),
        "geometry_coupling_enabled": bool(cfg.geometry_coupling_enabled),
        "rest_geometry": rest.tolist(),
        "deformation_before": before.tolist(),
        "deformation": d.tolist(),
        "actual_geometry": actual.tolist(),
        "B_site_norms": norms.tolist(),
        "max_displacement": float(cfg.max_displacement),
        "max_rate": float(cfg.max_rate),
        "mechanical_energy_accounting": "NOT DEMONSTRATED",
    }
