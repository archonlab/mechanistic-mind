"""Tick normalization — tick 0 is valid and must never become -1."""
from __future__ import annotations

from typing import Any


def coerce_tick(value: Any, *, default: int | None = None) -> int | None:
    """Convert a tick field without treating 0 as missing.

    Falsey fallback (`value or -1`) is forbidden: tick 0 is a valid simulation tick.
    """
    if value is None:
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if value != value:  # NaN
            return default
        return int(value)
    s = str(value).strip()
    if not s:
        return default
    try:
        return int(s)
    except (TypeError, ValueError):
        return default


def tick_from_receipt_id(receipt_id: Any) -> int | None:
    """Parse tick from SCIENTIFIC_V3 receipt IDs like o:run:0:agent_0."""
    if receipt_id is None:
        return None
    parts = str(receipt_id).split(":")
    if len(parts) < 3:
        return None
    return coerce_tick(parts[2], default=None)


def normalize_story_tick(story: Any, *, receipt_keys: tuple[str, ...] = (
    "observation_id", "decision_id", "motor_id", "consequence_id",
)) -> int | None:
    """Prefer explicit tick; if -1/None, recover from receipt IDs."""
    raw = getattr(story, "tick", None)
    if isinstance(story, dict):
        raw = story.get("tick", story.get("_cons_tick"))
    tick = coerce_tick(raw, default=None)
    if tick is not None and tick >= 0:
        return tick
    src = story if isinstance(story, dict) else None
    for key in receipt_keys:
        rid = (src or {}).get(key) if src is not None else getattr(story, key, None)
        recovered = tick_from_receipt_id(rid)
        if recovered is not None and recovered >= 0:
            return recovered
    return tick
