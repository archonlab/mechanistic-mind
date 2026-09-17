"""Canonical 2D toroidal spatial utilities for MM-WORLD-1."""
from __future__ import annotations

import numpy as np


def wrap_coord(x: float | int, size: int) -> float | int:
    """Wrap scalar coordinate into [0, size)."""
    s = int(size)
    if isinstance(x, (int, np.integer)):
        return int(x) % s
    return float(x) % float(s)


def toroidal_delta(a: float, b: float, size: int) -> float:
    """Signed shortest displacement from a to b on a circle of length size."""
    s = float(size)
    d = (float(b) - float(a) + 0.5 * s) % s - 0.5 * s
    return d


def toroidal_delta_xy(
    x1: float, y1: float, x2: float, y2: float, width: int, height: int
) -> tuple[float, float]:
    return toroidal_delta(x1, x2, width), toroidal_delta(y1, y2, height)


def toroidal_distance(
    x1: float, y1: float, x2: float, y2: float, width: int, height: int
) -> float:
    dx, dy = toroidal_delta_xy(x1, y1, x2, y2, width, height)
    return float(np.hypot(dx, dy))


def roll2(field: np.ndarray, shift_y: int, shift_x: int) -> np.ndarray:
    """Roll array with axes (y, x)."""
    return np.roll(np.roll(field, shift_y, axis=0), shift_x, axis=1)


def laplacian(field: np.ndarray) -> np.ndarray:
    """5-point discrete Laplacian with toroidal wrap. axes=(y,x)."""
    return (
        roll2(field, 1, 0)
        + roll2(field, -1, 0)
        + roll2(field, 0, 1)
        + roll2(field, 0, -1)
        - 4.0 * field
    )


def gradient(field: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Central differences on torus. Returns (d/dy, d/dx) to match (vy, vx) indexing."""
    dy = 0.5 * (roll2(field, -1, 0) - roll2(field, 1, 0))
    dx = 0.5 * (roll2(field, 0, -1) - roll2(field, 0, 1))
    return dy, dx


def translate_field(field: np.ndarray, dy: int, dx: int) -> np.ndarray:
    return roll2(field, dy, dx)
