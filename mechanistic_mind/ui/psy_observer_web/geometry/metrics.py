"""Wrap-aware motion metrics for Observer geometry interpretation."""
from __future__ import annotations

import math
from typing import Any

from mechanistic_mind.physical_system.actions import action_direction
from mechanistic_mind.planet.topology import toroidal_delta_xy

# Minimum |displacement| to treat as a meaningful move sample (world units).
EPS_DISP = 1e-4
# Alignment thresholds (cosine).
ALIGN_SUCCESS = 0.5
ALIGN_REVERSE = -0.3


def action_direction_unit(action: str | None) -> tuple[float, float] | None:
    """World-frame unit direction for MOVE:*; None for WAIT / unknown."""
    if action is None:
        return None
    d = action_direction(str(action))
    if d is None:
        return None
    mag = math.hypot(d[0], d[1])
    if mag <= 0.0:
        return None
    return (d[0] / mag, d[1] / mag)


def realized_displacement(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    *,
    width: int,
    height: int,
) -> tuple[float, float, float]:
    """Toroidal displacement (dx, dy, magnitude) from (x0,y0) → (x1,y1)."""
    dx, dy = toroidal_delta_xy(x0, y0, x1, y1, int(width), int(height))
    return float(dx), float(dy), float(math.hypot(dx, dy))


def action_alignment(
    action: str | None,
    dx: float,
    dy: float,
    *,
    min_disp: float = EPS_DISP,
) -> float | None:
    """Cosine(requested_direction, realized_displacement). None if undefined."""
    unit = action_direction_unit(action)
    if unit is None:
        return None
    mag = math.hypot(dx, dy)
    if mag < float(min_disp):
        return None
    return float((unit[0] * dx + unit[1] * dy) / mag)


def lateral_deflection(
    action: str | None,
    dx: float,
    dy: float,
    *,
    min_disp: float = EPS_DISP,
) -> float | None:
    """Signed component of displacement orthogonal to requested direction."""
    unit = action_direction_unit(action)
    if unit is None:
        return None
    mag = math.hypot(dx, dy)
    if mag < float(min_disp):
        return None
    # 2D perpendicular to unit: (-uy, ux)
    return float((-unit[1] * dx + unit[0] * dy))


def forward_component(
    action: str | None,
    dx: float,
    dy: float,
) -> float | None:
    """Projection of displacement onto requested unit direction."""
    unit = action_direction_unit(action)
    if unit is None:
        return None
    return float(unit[0] * dx + unit[1] * dy)


def traversal_outcome_class(
    action: str | None,
    dx: float,
    dy: float,
    *,
    min_disp: float = EPS_DISP,
) -> str:
    """Observer classification of one MOVE attempt. Not agent semantics."""
    if action is None or str(action).upper().startswith("WAIT"):
        return "NO_MOVE_REQUEST"
    unit = action_direction_unit(action)
    if unit is None:
        return "NON_MOVE_ACTION"
    mag = math.hypot(dx, dy)
    if mag < float(min_disp):
        return "NEAR_ZERO_DISPLACEMENT"
    align = action_alignment(action, dx, dy, min_disp=min_disp)
    if align is None:
        return "NEAR_ZERO_DISPLACEMENT"
    if align >= ALIGN_SUCCESS:
        return "ALIGNED_TRAVERSAL"
    if align <= ALIGN_REVERSE:
        return "OPPOSING_DISPLACEMENT"
    return "DEFLECTED_DISPLACEMENT"


def evidence_class(n: int, *, sparse: int = 3, moderate: int = 12) -> str:
    if n <= 0:
        return "NO_SAMPLES"
    if n < sparse:
        return "SPARSE"
    if n < moderate:
        return "MODERATE"
    return "ADEQUATE"


def bin_cell(x: float, y: float, *, width: int, height: int) -> tuple[int, int]:
    ix = int(math.floor(float(x))) % int(width)
    iy = int(math.floor(float(y))) % int(height)
    return ix, iy


def step_record(
    *,
    tick: int,
    agent_id: str,
    action: str | None,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    width: int,
    height: int,
    contact: bool | None = None,
    work: float | None = None,
    forces: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One Observer-side motion step with derived geometry metrics."""
    dx, dy, mag = realized_displacement(x0, y0, x1, y1, width=width, height=height)
    align = action_alignment(action, dx, dy)
    fwd = forward_component(action, dx, dy)
    lat = lateral_deflection(action, dx, dy)
    outcome = traversal_outcome_class(action, dx, dy)
    ix, iy = bin_cell(x0, y0, width=width, height=height)
    return {
        "tick": int(tick),
        "agent_id": str(agent_id),
        "action": action,
        "x0": float(x0),
        "y0": float(y0),
        "x1": float(x1),
        "y1": float(y1),
        "cell": [ix, iy],
        "dx": dx,
        "dy": dy,
        "disp_mag": mag,
        "action_alignment": align,
        "forward_component": fwd,
        "lateral_deflection": lat,
        "outcome": outcome,
        "contact": contact,
        "work": work,
        "forces": forces,
        "requested_unit": list(action_direction_unit(action) or ()),
    }
