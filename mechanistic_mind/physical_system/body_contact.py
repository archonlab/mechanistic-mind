"""Experimental body-body contact. Physical overlap only. Not combat."""
from __future__ import annotations

from typing import Any

import numpy as np

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.planet.topology import wrap_coord
from mechanistic_mind.physical_system.body_deformation import rest_geometry
from mechanistic_mind.physical_system.body_orientation import oriented_site_cells


def footprint_cells(body: PhysicalBodyState, body_cfg: PhysicalBodyConfig, width: int, height: int) -> list[tuple[int, int]]:
    rest = rest_geometry(body_cfg.footprint)
    d = getattr(body, "deformation", None)
    r_body = rest + np.asarray(d, dtype=np.float64) if d is not None and np.asarray(d).shape == rest.shape else rest
    theta = float(getattr(body, "theta", 0.0) or 0.0)
    return oriented_site_cells(body, width, height, body_cfg.footprint, theta=theta, r_body=r_body)


def overlap_cells(
    a: PhysicalBodyState,
    b: PhysicalBodyState,
    cfg_a: PhysicalBodyConfig,
    cfg_b: PhysicalBodyConfig,
    width: int,
    height: int,
) -> list[tuple[int, int]]:
    sa = set(footprint_cells(a, cfg_a, width, height))
    sb = set(footprint_cells(b, cfg_b, width, height))
    return sorted(sa & sb)


def resolve_soft_contact(
    a: PhysicalBodyState,
    b: PhysicalBodyState,
    cfg_a: PhysicalBodyConfig,
    cfg_b: PhysicalBodyConfig,
    *,
    width: int,
    height: int,
    stiffness: float = 0.25,
    enabled: bool = True,
) -> dict[str, Any]:
    """Equal-and-opposite impulse from CoM overlap. No damage."""
    receipt = {
        "enabled": bool(enabled),
        "overlap_cells": [],
        "impulse_a": [0.0, 0.0],
        "impulse_b": [0.0, 0.0],
        "contact": False,
    }
    if not enabled:
        return receipt
    shared = overlap_cells(a, b, cfg_a, cfg_b, width, height)
    receipt["overlap_cells"] = [list(c) for c in shared]
    dx = float(b.x - a.x)
    dy = float(b.y - a.y)
    # toroidal shortest delta
    if abs(dx) > width / 2:
        dx -= np.sign(dx) * width
    if abs(dy) > height / 2:
        dy -= np.sign(dy) * height
    dist = float(np.hypot(dx, dy))
    contact = bool(shared) or dist < 1.15
    receipt["contact"] = contact
    receipt["com_distance"] = dist
    if not contact:
        return receipt
    if dist < 1e-9:
        nx, ny = 1.0, 0.0
        dist = 1e-9
    else:
        nx, ny = dx / dist, dy / dist
    overlap = max(0.0, 1.15 - dist) + 0.15 * len(shared)
    mag = float(stiffness) * overlap
    ma = max(1e-6, float(cfg_a.mass))
    mb = max(1e-6, float(cfg_b.mass))
    # equal-and-opposite momentum
    ix, iy = mag * nx, mag * ny
    a.vx = float(np.clip(a.vx - ix / ma, -cfg_a.v_max, cfg_a.v_max))
    a.vy = float(np.clip(a.vy - iy / ma, -cfg_a.v_max, cfg_a.v_max))
    b.vx = float(np.clip(b.vx + ix / mb, -cfg_b.v_max, cfg_b.v_max))
    b.vy = float(np.clip(b.vy + iy / mb, -cfg_b.v_max, cfg_b.v_max))
    # small positional separation so they do not remain nested
    sep = 0.08 * overlap
    a.x = float(wrap_coord(a.x - sep * nx, width))
    a.y = float(wrap_coord(a.y - sep * ny, height))
    b.x = float(wrap_coord(b.x + sep * nx, width))
    b.y = float(wrap_coord(b.y + sep * ny, height))
    receipt["impulse_a"] = [float(-ix / ma), float(-iy / ma)]
    receipt["impulse_b"] = [float(ix / mb), float(iy / mb)]
    return receipt
