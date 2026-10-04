"""Contiguous WAIT/MOVE streaks from ordered unique per-agent action ticks.

Analyzer-only. Does not replay physics or mutate evidence.
"""
from __future__ import annotations

from typing import Any, Iterable


WAIT_FAMILY = "WAIT"
MOVE_FAMILY = "MOVE"


def action_family(token: Any) -> str:
    s = str(token or "WAIT").strip().upper()
    if s in {"", "NONE", "NULL", "WAIT"} or s.startswith("WAIT"):
        return WAIT_FAMILY
    if s.startswith("MOVE"):
        return MOVE_FAMILY
    return s


def compute_agent_action_metrics(
    rows: Iterable[tuple[int, Any]],
    *,
    keep: str = "first",
) -> dict[str, Any]:
    """rows: (simulation_tick, locomotion_token). Dedupes exact duplicate ticks."""
    by_tick: dict[int, Any] = {}
    dup = 0
    for raw_tick, token in rows:
        try:
            tick = int(raw_tick)
        except (TypeError, ValueError):
            continue
        if tick in by_tick:
            dup += 1
            if keep != "last":
                continue
        by_tick[tick] = token
    if not by_tick:
        return {
            "canonical_ticks": 0,
            "wait_count": 0,
            "move_count": 0,
            "longest_wait_streak": 0,
            "longest_move_streak": 0,
            "action_transitions": 0,
            "gaps": [],
            "gap_ticks_missing": 0,
            "duplicates_ignored": dup,
            "sequence_coverage": "UNAVAILABLE",
            "tick_min": None,
            "tick_max": None,
        }
    ticks = sorted(by_tick)
    wait_n = move_n = 0
    longest_w = longest_m = 0
    cur_w = cur_m = 0
    transitions = 0
    gaps: list[dict[str, int]] = []
    missing = 0
    prev_fam: str | None = None
    prev_t: int | None = None
    for t in ticks:
        fam = action_family(by_tick[t])
        if fam == WAIT_FAMILY:
            wait_n += 1
        elif fam == MOVE_FAMILY:
            move_n += 1
        if prev_t is not None and t > prev_t + 1:
            hole = t - prev_t - 1
            missing += hole
            gaps.append({"after_tick": prev_t, "resume_tick": t, "missing_ticks": hole})
            cur_w = 0
            cur_m = 0
        if prev_fam is not None and fam != prev_fam:
            transitions += 1
        if fam == WAIT_FAMILY:
            cur_w += 1
            cur_m = 0
            longest_w = max(longest_w, cur_w)
        elif fam == MOVE_FAMILY:
            cur_m += 1
            cur_w = 0
            longest_m = max(longest_m, cur_m)
        else:
            cur_w = 0
            cur_m = 0
        prev_fam = fam
        prev_t = t
    tmin, tmax = ticks[0], ticks[-1]
    span = tmax - tmin + 1
    coverage = "CONTIGUOUS" if missing == 0 else "SPARSE"
    if span > 0 and len(ticks) < span and missing == 0:
        coverage = "PARTIAL"
    return {
        "canonical_ticks": len(ticks),
        "wait_count": wait_n,
        "move_count": move_n,
        "longest_wait_streak": longest_w,
        "longest_move_streak": longest_m,
        "action_transitions": transitions,
        "gaps": gaps[:32],
        "gap_ticks_missing": missing,
        "duplicates_ignored": dup,
        "sequence_coverage": coverage,
        "tick_min": tmin,
        "tick_max": tmax,
        "unit": "agent-ticks",
    }
