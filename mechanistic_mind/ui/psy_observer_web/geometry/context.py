"""geometry_context(agent_id, tick, window) for future signal interpreters."""
from __future__ import annotations

from typing import Any


def geometry_context(
    steps: list[dict[str, Any]],
    *,
    agent_id: str,
    tick: int,
    window: int = 10,
) -> dict[str, Any]:
    """Bounded physical/trajectory context around a tick (Observer-only).

    Intended for future signal/no-signal matched comparisons.
    Does not implement signal semantics.
    """
    w = max(0, int(window))
    t0 = int(tick) - w
    t1 = int(tick) + w
    aid = str(agent_id)
    nearby = [
        s for s in steps
        if str(s.get("agent_id")) == aid and t0 <= int(s.get("tick") or -1) <= t1
    ]
    nearby.sort(key=lambda s: int(s.get("tick") or 0))
    at = next((s for s in nearby if int(s.get("tick") or -1) == int(tick)), None)
    before = [s for s in nearby if int(s.get("tick") or -1) < int(tick)]
    after = [s for s in nearby if int(s.get("tick") or -1) > int(tick)]
    return {
        "agent_id": aid,
        "tick": int(tick),
        "window": w,
        "at_tick": at,
        "before": before[-w:] if before else [],
        "after": after[:w] if after else [],
        "summary": {
            "n_before": len(before),
            "n_after": len(after),
            "opposing_before": sum(1 for s in before if s.get("outcome") == "OPPOSING_DISPLACEMENT"),
            "opposing_after": sum(1 for s in after if s.get("outcome") == "OPPOSING_DISPLACEMENT"),
            "aligned_before": sum(1 for s in before if s.get("outcome") == "ALIGNED_TRAVERSAL"),
            "aligned_after": sum(1 for s in after if s.get("outcome") == "ALIGNED_TRAVERSAL"),
            "contact_at": (at or {}).get("contact"),
            "action_at": (at or {}).get("action"),
            "alignment_at": (at or {}).get("action_alignment"),
        },
        "honesty": {
            "observer_only": True,
            "no_signal_causality": True,
            "note": "Geometry side only — does not claim signal→action effects.",
        },
    }
