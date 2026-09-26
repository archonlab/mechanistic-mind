"""Empirical cell×direction traversability from observed trajectories."""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable

from mechanistic_mind.ui.psy_observer_web.geometry.metrics import (
    evidence_class,
    step_record,
)


def _key(ix: int, iy: int, action: str) -> tuple[int, int, str]:
    return (int(ix), int(iy), str(action))


def accumulate_traversability(
    steps: Iterable[dict[str, Any]],
    *,
    move_only: bool = True,
) -> dict[tuple[int, int, str], dict[str, Any]]:
    """Build empirical stats keyed by (cell_x, cell_y, requested_action)."""
    buckets: dict[tuple[int, int, str], list[dict[str, Any]]] = defaultdict(list)
    for st in steps:
        action = st.get("action")
        if move_only and (action is None or str(action).upper().startswith("WAIT")):
            continue
        if action_direction_missing(action):
            continue
        cell = st.get("cell") or [0, 0]
        buckets[_key(cell[0], cell[1], str(action))].append(st)
    out: dict[tuple[int, int, str], dict[str, Any]] = {}
    for k, rows in buckets.items():
        out[k] = summarize_bucket(k[0], k[1], k[2], rows)
    return out


def action_direction_missing(action: str | None) -> bool:
    from mechanistic_mind.ui.psy_observer_web.geometry.metrics import action_direction_unit

    return action_direction_unit(action) is None


def summarize_bucket(ix: int, iy: int, action: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    aligns = [float(r["action_alignment"]) for r in rows if r.get("action_alignment") is not None]
    mags = [float(r["disp_mag"]) for r in rows]
    fwds = [float(r["forward_component"]) for r in rows if r.get("forward_component") is not None]
    outcomes: dict[str, int] = defaultdict(int)
    contact_n = 0
    contact_oppose = 0
    no_contact_oppose = 0
    for r in rows:
        outcomes[str(r.get("outcome") or "UNKNOWN")] += 1
        if r.get("contact"):
            contact_n += 1
            if r.get("outcome") == "OPPOSING_DISPLACEMENT":
                contact_oppose += 1
        elif r.get("outcome") == "OPPOSING_DISPLACEMENT":
            no_contact_oppose += 1

    def _mean(xs: list[float]) -> float | None:
        return (sum(xs) / len(xs)) if xs else None

    def _var(xs: list[float]) -> float | None:
        if len(xs) < 2:
            return None
        m = sum(xs) / len(xs)
        return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)

    aligned = outcomes.get("ALIGNED_TRAVERSAL", 0)
    opposing = outcomes.get("OPPOSING_DISPLACEMENT", 0)
    deflected = outcomes.get("DEFLECTED_DISPLACEMENT", 0)
    near_zero = outcomes.get("NEAR_ZERO_DISPLACEMENT", 0)
    return {
        "cell": [int(ix), int(iy)],
        "action": str(action),
        "attempts": n,
        "evidence_class": evidence_class(n),
        "aligned_traversals": aligned,
        "opposing_displacements": opposing,
        "deflected_displacements": deflected,
        "near_zero_displacements": near_zero,
        "aligned_rate": aligned / n if n else None,
        "opposing_rate": opposing / n if n else None,
        "mean_action_alignment": _mean(aligns),
        "var_action_alignment": _var(aligns),
        "mean_disp_mag": _mean(mags),
        "mean_forward_component": _mean(fwds),
        "contact_attempts": contact_n,
        "contact_opposing": contact_oppose,
        "no_contact_opposing": no_contact_oppose,
        "note": (
            "Empirical Observer rates from realized trajectories. "
            "Not a semantic terrain label."
        ),
    }


def steps_from_timeline_rows(
    rows: list[dict[str, Any]],
    *,
    width: int,
    height: int,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    """Convert scientific_timeline rows into consecutive step records per agent."""
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            continue
        aid = str(row.get("agent_id") or "agent_0")
        if agent_id is not None and aid != agent_id:
            continue
        by_agent[aid].append(row)
    steps: list[dict[str, Any]] = []
    for aid, seq in by_agent.items():
        seq = sorted(seq, key=lambda r: int(r.get("tick") or 0))
        for i in range(len(seq) - 1):
            a, b = seq[i], seq[i + 1]
            ta, tb = int(a.get("tick") or 0), int(b.get("tick") or 0)
            if tb != ta + 1:
                continue
            # Action at tick t produces displacement observed arriving at t+1 pose.
            steps.append(
                step_record(
                    tick=ta,
                    agent_id=aid,
                    action=a.get("action"),
                    x0=float(a.get("x") or 0.0),
                    y0=float(a.get("y") or 0.0),
                    x1=float(b.get("x") or 0.0),
                    y1=float(b.get("y") or 0.0),
                    width=width,
                    height=height,
                    contact=bool(a.get("contact")),
                    work=float(a["work"]) if a.get("work") is not None else None,
                )
            )
    return steps


def top_deflection_cells(
    stats: dict[tuple[int, int, str], dict[str, Any]],
    *,
    min_attempts: int = 8,
    limit: int = 40,
) -> list[dict[str, Any]]:
    """Cells/actions with highest opposing_rate among adequate samples."""
    rows = [
        v for v in stats.values()
        if int(v.get("attempts") or 0) >= min_attempts
        and float(v.get("opposing_rate") or 0.0) > 0.0
    ]
    rows.sort(key=lambda r: (float(r.get("opposing_rate") or 0.0), int(r["attempts"])), reverse=True)
    return rows[:limit]


def heatmap_opposing_rate(
    stats: dict[tuple[int, int, str], dict[str, Any]],
    *,
    width: int,
    height: int,
    action: str,
    min_attempts: int = 5,
) -> list[list[float | None]]:
    """Grid of opposing_rate for one action; None = insufficient samples."""
    grid: list[list[float | None]] = [[None for _ in range(width)] for _ in range(height)]
    for (ix, iy, act), v in stats.items():
        if act != action:
            continue
        if int(v.get("attempts") or 0) < min_attempts:
            continue
        if 0 <= iy < height and 0 <= ix < width:
            grid[iy][ix] = float(v.get("opposing_rate") or 0.0)
    return grid
