"""Bounded LIVE Observer retention — UI/display only.

These limits bound LIVE frame construction and display retention.
They must NEVER be used as scientific authority, agent memory, or Analyzer evidence.

Scientific history remains independently persisted (JSONL) and is loaded
intentionally by Analyze Current / evidence APIs.
"""
from __future__ import annotations

from collections.abc import Sequence
from itertools import islice
from typing import Any, TypeVar

T = TypeVar("T")

# --- LIVE embed tails (per captured Observer frame, RUNNING/compact) ---
# Why ~96: enough path context on the map without shipping the full ring.
LIVE_TRAJECTORY_EMBED = 96
# Why ~64: telemetry sparkline depth for LIVE panels.
LIVE_TELEMETRY_EMBED = 64
# Why ~16: recent structured events on compact LIVE frames.
LIVE_EVENT_EMBED = 16
# Why ~80: richer event tail when paused / inspecting (still not full history).
LIVE_EVENT_EMBED_FULL = 80
# Why ~64: intervention provenance strip on LIVE frames (full count in summary).
LIVE_WORLD_INTERVENTION_EMBED = 64

# --- Session rings (in-memory Observer buffers; not agent cognition) ---
LIVE_EVENT_RING_MAX = 2500
LIVE_WORLD_INTERVENTION_SESSION_MAX = 512
LIVE_TIMELINE_MIN = 1024
LIVE_TIMELINE_MULT = 8  # timeline maxlen = max(MIN, buffer_capacity * MULT)
LIVE_TRAJECTORY_RING_MULT = 4  # traj/telem maxlen = max(MIN, buffer_capacity * MULT)
# Why 2048: UI trajectory display target (~2k recent points); not agent memory.
LIVE_TRAJECTORY_RING_MIN = 2048
LIVE_TELEMETRY_RING_MIN = 2048

# --- Frontend / API poll caps (server already tails; FE should not accumulate) ---
LIVE_API_TIMELINE_LIMIT = 400
LIVE_API_EVENTS_LIMIT = 200
LIVE_FE_TRAJECTORY_DISPLAY_DEFAULT = 500
LIVE_FE_EVENTS_DISPLAY_MAX = 500
LIVE_FE_TIMELINE_DISPLAY_MAX = 400
LIVE_FE_SIGNAL_SAMPLES_MAX = 1000
LIVE_FE_COGNITION_CONTEXT_MAX = 200

# Scientific append still samples a small recent event window (not full ring).
SCI_APPEND_EVENT_TAIL = 40


def tail_list(seq: Sequence[T], n: int) -> list[T]:
    """Return last n elements without copying the prefix of a sequence/deque."""
    if n <= 0:
        return []
    length = len(seq)
    if length <= n:
        return list(seq)
    return list(islice(seq, length - n, None))


def live_refresh_elements_touched(
    *,
    event_embed: int,
    traj_embed: int,
    telem_embed: int,
    intervention_embed: int,
) -> int:
    """Count of historical-ish elements copied into one LIVE frame (diagnostic)."""
    return int(event_embed) + int(traj_embed) + int(telem_embed) + int(intervention_embed)


def live_bounds_snapshot() -> dict[str, Any]:
    return {
        "authority": "LIVE_OBSERVER_DISPLAY_ONLY",
        "not_scientific_authority": True,
        "not_agent_memory": True,
        "trajectory_embed": LIVE_TRAJECTORY_EMBED,
        "telemetry_embed": LIVE_TELEMETRY_EMBED,
        "event_embed_compact": LIVE_EVENT_EMBED,
        "event_embed_full": LIVE_EVENT_EMBED_FULL,
        "world_intervention_embed": LIVE_WORLD_INTERVENTION_EMBED,
        "world_intervention_session_max": LIVE_WORLD_INTERVENTION_SESSION_MAX,
        "event_ring_max": LIVE_EVENT_RING_MAX,
        "api_timeline_limit": LIVE_API_TIMELINE_LIMIT,
        "api_events_limit": LIVE_API_EVENTS_LIMIT,
    }
