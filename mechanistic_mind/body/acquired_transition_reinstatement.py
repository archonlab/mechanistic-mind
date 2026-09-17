"""Bounded current reinstatement of a frozen 4.75 transition relation.

Update 4.76. Experimental. Default off. Research-only consumer.

R_L[j,k] = sum_i S[i] * L[i,j,k]
Shape 2 x 3. Instantaneous. Does not write L, N, preact, motor, D, E, Q, or BODY.
Does not select a response. Does not implement 4.77.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.body.internal_transition_acquisition import M_DIM, S_DIM, WEIGHT_BOUND

# Analytical: |S|<=1, |L|<=WEIGHT_BOUND, 3-term sum.
R_BOUND = float(S_DIM) * 1.0 * float(WEIGHT_BOUND)


def default_reinstatement_config() -> dict[str, Any]:
    return {"enabled": True, "bound": R_BOUND}


def reinstate(s: tuple[float, ...], weights) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """S-axis contraction of L. Preserves M and S_after axes. No clip, no gain."""
    sv = tuple(float(s[i]) if i < len(s) else 0.0 for i in range(S_DIM))
    rows = []
    for j in range(M_DIM):
        row = []
        for k in range(S_DIM):
            acc = 0.0
            for i in range(S_DIM):
                acc += sv[i] * float(weights[i][j][k])
            row.append(acc)
        rows.append((row[0], row[1], row[2]))
    return (rows[0], rows[1])


def frobenius_r(r) -> float:
    return sum(x * x for row in r for x in row) ** 0.5


def linf_r(a, b) -> float:
    m = 0.0
    for j in range(M_DIM):
        for k in range(S_DIM):
            m = max(m, abs(float(a[j][k]) - float(b[j][k])))
    return m


def scale_r(r, c: float):
    return tuple(tuple(c * float(x) for x in row) for row in r)


def negate_r(r):
    return scale_r(r, -1.0)


def permute_s_after(r, perm: tuple[int, int, int]):
    return tuple(tuple(float(row[perm[k]]) for k in range(S_DIM)) for row in r)


def permute_m_axis(r, perm_m: tuple[int, int]):
    return (r[perm_m[0]], r[perm_m[1]])


def representation(r) -> dict[str, Any]:
    flat = [float(x) for row in r for x in row]
    return {
        "shape": [M_DIM, S_DIM],
        "capacity": M_DIM * S_DIM,
        "max_abs": max(abs(x) for x in flat),
        "frobenius": frobenius_r(r),
        "bytes": 8 * M_DIM * S_DIM,
        "bound": R_BOUND,
        "persistent": False,
    }
