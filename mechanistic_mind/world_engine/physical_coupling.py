"""Update 4.60 — fixed arbitrary physical coupling (experimental, default off).

C is 4x3, frozen before any movement result. Not learned. Not optimized.
Does not read motor_distribution or sample_motor.
Does not emit Action.kind.
"""
from __future__ import annotations

from typing import Any

# Scale frozen analytically before physical trials.
# |preact| typically <= 1; 4.58 probe uses 0.70.
# 4.59 hop needs E_i >= 0.60; from rest E'=D, so D>=0.60.
# A unit-ish C row * 0.70 = 0.70 > 0.60. SCALE=1.0. Not increased after.
SCALE = 1.0
PREACT_DIM = 3
DRIVE_DIM = 4

C0 = (
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
    (0.0, 0.0, 0.0),
)
C1 = (
    (1.00, 0.15, 0.00),
    (0.00, 1.00, 0.15),
    (0.15, 0.00, 1.00),
    (0.50, 0.50, 0.00),
)
C2 = (
    (0.00, 0.20, 1.00),
    (1.00, 0.00, 0.20),
    (0.20, 1.00, 0.00),
    (0.00, 0.40, 0.60),
)
# One draw Random(17), uniform[-1,1], frozen here. Not redrawn.
C3 = (
    (0.044, 0.6134, 0.921),
    (-0.4207, 0.5322, 0.4084),
    (0.3228, -0.7797, -0.9461),
    (-0.2317, 0.4928, -0.4952),
)
# Mechanical transform of C1: columns (-c2, c0, c1).
C4 = (
    (-0.00, 1.00, 0.15),
    (-0.15, 0.00, 1.00),
    (-1.00, 0.15, 0.00),
    (-0.00, 0.50, 0.50),
)

FAMILY = {"C0": C0, "C1": C1, "C2": C2, "C3": C3, "C4": C4}


def as_matrix(raw: Any) -> tuple[tuple[float, float, float], ...]:
    rows = []
    for row in raw:
        rows.append((float(row[0]), float(row[1]), float(row[2])))
    if len(rows) != DRIVE_DIM:
        raise ValueError("C must be 4x3")
    return tuple(rows)


def matmul(C: tuple[tuple[float, ...], ...], p: tuple[float, ...]) -> tuple[float, float, float, float]:
    z = []
    for i in range(DRIVE_DIM):
        z.append(sum(float(C[i][j]) * float(p[j]) for j in range(PREACT_DIM)))
    return (z[0], z[1], z[2], z[3])


def g_drive(z: tuple[float, ...], *, scale: float = SCALE) -> tuple[float, float, float, float]:
    """Identical componentwise map: clip(max(0, scale * z_i), 0, 1). g(0)=0."""
    out = []
    for i in range(len(z)):
        v = scale * float(z[i])
        if v < 0.0:
            v = 0.0
        if v > 1.0:
            v = 1.0
        out.append(v)
    return (out[0], out[1], out[2], out[3])


def drive_from_preact(
    preact: tuple[float, ...],
    C: tuple[tuple[float, ...], ...],
    *,
    scale: float = SCALE,
) -> dict[str, Any]:
    p = (float(preact[0]), float(preact[1]), float(preact[2]))
    z = matmul(C, p)
    d = g_drive(z, scale=scale)
    return {"preact": p, "Z": z, "D": d, "scale": scale}


def default_coupling_config(matrix_id: str = "C1") -> dict[str, Any]:
    if matrix_id not in FAMILY:
        raise ValueError(matrix_id)
    return {
        "enabled": True,
        "matrix_id": matrix_id,
        "C": [list(r) for r in FAMILY[matrix_id]],
        "scale": SCALE,
    }


def maybe_write_drive(state: dict[str, Any], config: Any) -> dict[str, Any]:
    """If experimental coupling is on, write researcher_physical_drive from preact.

    Reads only researcher_controlled_preact. Does not read motor_distribution.
    No-op if config missing/disabled or preact absent.
    """
    extra = {"applied": False}
    if not isinstance(config, dict) or not config.get("enabled", True):
        return extra
    raw = state.get("researcher_controlled_preact")
    if raw is None:
        return extra
    C = as_matrix(config.get("C") or FAMILY[str(config.get("matrix_id") or "C1")])
    scale = float(config.get("scale", SCALE))
    p = (float(raw[0]), float(raw[1]), float(raw[2]))
    rec = drive_from_preact(p, C, scale=scale)
    state["researcher_physical_drive"] = list(rec["D"])
    state["physical_coupling"] = {
        "matrix_id": config.get("matrix_id"),
        "Z": list(rec["Z"]),
        "D": list(rec["D"]),
        "preact": list(rec["preact"]),
        "scale": scale,
    }
    extra.update({"applied": True, **rec})
    return extra
