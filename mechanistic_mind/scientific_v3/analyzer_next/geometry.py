"""Wrap-aware geometry and approach / orienting derivations."""
from __future__ import annotations

import math
from typing import Any


def wrap_delta(a: float, b: float, size: float) -> float:
    """Shortest signed delta from a → b on a torus of length size."""
    if size <= 0:
        return b - a
    d = (b - a) % size
    if d > size * 0.5:
        d -= size
    return d


def toroidal_distance(x0: float, y0: float, x1: float, y1: float, width: float, height: float) -> float:
    dx = wrap_delta(x0, x1, width)
    dy = wrap_delta(y0, y1, height)
    return math.hypot(dx, dy)


def bearing_rad(x0: float, y0: float, x1: float, y1: float, width: float, height: float) -> float:
    """Bearing from (x0,y0) to (x1,y1), radians, world frame (atan2 dy, dx)."""
    dx = wrap_delta(x0, x1, width)
    dy = wrap_delta(y0, y1, height)
    return math.atan2(dy, dx)


def angular_error(heading: float, target_bearing: float) -> float:
    """Signed smallest angle from heading to target_bearing, radians in (-pi, pi]."""
    d = (target_bearing - heading + math.pi) % (2 * math.pi) - math.pi
    return d


def deg(rad: float) -> float:
    return rad * 180.0 / math.pi


def approach_decomposition(
    *,
    agent_xy_t: tuple[float, float],
    agent_xy_t1: tuple[float, float],
    source_xy_t: tuple[float, float],
    source_xy_t1: tuple[float, float],
    width: float,
    height: float,
) -> dict[str, Any]:
    """Decompose distance change into agent vs source movement contributions.

    Counterfactual: hold one participant fixed at t while the other moves to t1.
    """
    d0 = toroidal_distance(*agent_xy_t, *source_xy_t, width, height)
    d1 = toroidal_distance(*agent_xy_t1, *source_xy_t1, width, height)
    d_agent_only = toroidal_distance(*agent_xy_t1, *source_xy_t, width, height)
    d_source_only = toroidal_distance(*agent_xy_t, *source_xy_t1, width, height)
    agent_contrib = d_agent_only - d0
    source_contrib = d_source_only - d0
    total = d1 - d0
    # residual from non-additivity of distance
    residual = total - (agent_contrib + source_contrib)
    if abs(agent_contrib) + abs(source_contrib) < 1e-12:
        dominant = "NEITHER"
    elif abs(agent_contrib) >= abs(source_contrib):
        dominant = "AGENT"
    else:
        dominant = "SOURCE"
    return {
        "distance_t": d0,
        "distance_t1": d1,
        "delta_distance": total,
        "agent_contribution": agent_contrib,
        "source_contribution": source_contrib,
        "residual_nonadditive": residual,
        "dominant_mover": dominant,
        "layer": "DERIVED",
    }


def orienting_error(
    *,
    agent_xy: tuple[float, float],
    source_xy: tuple[float, float],
    head_or_body_heading: float,
    width: float,
    height: float,
) -> dict[str, Any]:
    brg = bearing_rad(*agent_xy, *source_xy, width, height)
    err = angular_error(head_or_body_heading, brg)
    return {
        "bearing_to_source_rad": brg,
        "bearing_to_source_deg": deg(brg),
        "heading_rad": head_or_body_heading,
        "heading_deg": deg(head_or_body_heading),
        "angular_error_rad": err,
        "angular_error_deg": deg(err),
        "abs_angular_error_deg": abs(deg(err)),
        "layer": "DERIVED",
    }
