"""PRE / DURING / POST context windows for SignalEpisodes."""
from __future__ import annotations

from typing import Any

# Documented defaults (tick offsets relative to episode).
WINDOW_SPEC = {
    "PRE": {"start_offset": -20, "end_offset": -1, "note": "ticks before episode start"},
    "DURING": {"start_offset": 0, "end_offset": 0, "note": "episode interval inclusive"},
    "POST_SHORT": {"start_offset": 1, "end_offset": 20, "note": "relative to episode end"},
    "POST_MEDIUM": {"start_offset": 21, "end_offset": 100, "note": "relative to episode end"},
}


def _index_timeline(rows: list[dict[str, Any]]) -> dict[tuple[str, int], dict[str, Any]]:
    idx: dict[tuple[str, int], dict[str, Any]] = {}
    for r in rows:
        try:
            tick = int(r["tick"])
            aid = str(r.get("agent_id") or "")
        except (KeyError, TypeError, ValueError):
            continue
        idx[(aid, tick)] = r
    return idx


def _slice_range(
    idx: dict[tuple[str, int], dict[str, Any]],
    *,
    agent_id: str,
    t0: int,
    t1: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for t in range(int(t0), int(t1) + 1):
        row = idx.get((agent_id, t))
        if row is not None:
            out.append(row)
    return out


def _compact_row(row: dict[str, Any]) -> dict[str, Any]:
    """Compact physical/cognitive fingerprint — no huge snapshots."""
    return {
        "tick": row.get("tick"),
        "agent_id": row.get("agent_id"),
        "action": row.get("action"),
        "action_source": row.get("action_source"),
        "x": row.get("x"),
        "y": row.get("y"),
        "vx": row.get("vx"),
        "vy": row.get("vy"),
        "speed": row.get("speed"),
        "theta": row.get("theta"),
        "work": row.get("work"),
        "contact": row.get("contact"),
        "prediction_count": row.get("prediction_count"),
        "prospective_compositions": row.get("prospective_compositions"),
        "resource_A": row.get("resource_A"),
        "resource_B": row.get("resource_B"),
    }


def extract_windows(
    episode: dict[str, Any],
    timeline_rows: list[dict[str, Any]],
    *,
    pre: int = 20,
    post_short: int = 20,
    post_medium: int = 100,
) -> dict[str, Any]:
    """Bounded PRE/DURING/POST windows for one episode (receiver only)."""
    aid = str(episode["receiver_agent_id"])
    start = int(episode["start_tick"])
    end = int(episode["end_tick"])
    idx = _index_timeline(timeline_rows)

    pre_rows = _slice_range(idx, agent_id=aid, t0=start - pre, t1=start - 1)
    during_rows = _slice_range(idx, agent_id=aid, t0=start, t1=end)
    post_s = _slice_range(idx, agent_id=aid, t0=end + 1, t1=end + post_short)
    post_m = _slice_range(
        idx, agent_id=aid, t0=end + post_short + 1, t1=end + post_medium
    )

    return {
        "window_spec": {
            "PRE": f"-{pre}..-1 relative to start={start}",
            "DURING": f"{start}..{end}",
            "POST_SHORT": f"+1..+{post_short} relative to end={end}",
            "POST_MEDIUM": f"+{post_short + 1}..+{post_medium} relative to end={end}",
        },
        "PRE": [_compact_row(r) for r in pre_rows],
        "DURING": [_compact_row(r) for r in during_rows],
        "POST_SHORT": [_compact_row(r) for r in post_s],
        "POST_MEDIUM": [_compact_row(r) for r in post_m],
        "availability": {
            "PRE": "AVAILABLE" if pre_rows else "MISSING",
            "DURING": "AVAILABLE" if during_rows else "MISSING",
            "POST_SHORT": "AVAILABLE" if post_s else "MISSING",
            "POST_MEDIUM": "AVAILABLE" if post_m else "PARTIAL" if post_s else "MISSING",
        },
    }


def window_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Scalar summary of a window for matching / delta."""
    if not rows:
        return {
            "n": 0,
            "action": None,
            "action_source": None,
            "mean_x": None,
            "mean_y": None,
            "contact_any": False,
            "prediction_count": None,
            "prospective_compositions": None,
            "status": "MISSING",
        }
    last = rows[-1]
    first = rows[0]
    xs = [float(r["x"]) for r in rows if r.get("x") is not None]
    ys = [float(r["y"]) for r in rows if r.get("y") is not None]
    return {
        "n": len(rows),
        "action_first": first.get("action"),
        "action_last": last.get("action"),
        "action_source_first": first.get("action_source"),
        "action_source_last": last.get("action_source"),
        "mean_x": sum(xs) / len(xs) if xs else None,
        "mean_y": sum(ys) / len(ys) if ys else None,
        "contact_any": any(bool(r.get("contact")) for r in rows),
        "prediction_count_first": first.get("prediction_count"),
        "prediction_count_last": last.get("prediction_count"),
        "prospective_first": first.get("prospective_compositions"),
        "prospective_last": last.get("prospective_compositions"),
        "status": "AVAILABLE",
    }
