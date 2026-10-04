"""Researcher summary for held COMBINE radius resize transaction."""
from __future__ import annotations

from typing import Any


def summarize_held_combine_radius_resize(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    class_counts: dict[str, int] = {}
    timelines: list[dict[str, Any]] = []
    flags: list[str] = []
    for r in receipts:
        cls = str(
            r.get("resize_classification")
            or r.get("classification")
            or r.get("result")
            or "UNKNOWN"
        )
        class_counts[cls] = int(class_counts.get(cls, 0)) + 1
        timelines.append(
            {
                "tick": r.get("tick"),
                "object_id": r.get("object_id") or r.get("survivor_id"),
                "transaction_id": r.get("transaction_id"),
                "radius_before": r.get("radius_before"),
                "radius_after": r.get("radius_after") or r.get("radius_proposed"),
                "work_debited": r.get("work_debited"),
                "resize_classification": cls,
                "committed": r.get("committed"),
            }
        )
        if r.get("impact_sound_emitted") is True:
            flags.append(f"unexpected_impact_sound:{r.get('object_id')}")
        if r.get("deposition_resize") is True:
            flags.append(f"unexpected_deposition_resize:{r.get('object_id')}")
    return {
        "receipt_count": len(receipts),
        "classification_counts": class_counts,
        "timelines": timelines,
        "flags": flags,
        "causal_reconstruction": (
            "held-held contact → explicit COMBINE → amount/composition proposal → "
            "radius proposal → PE/work admission → geometry conflict admission → "
            "atomic commit or reject → later ordinary contact consequences"
        ),
        "deposition_resize": False,
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_held_combine_radius_resize_section(s: dict[str, Any]) -> str:
    lines = [
        "## Held COMBINE radius resize transaction",
        f"receipts={s.get('receipt_count', 0)}",
        f"classifications={s.get('classification_counts')}",
        f"flags={s.get('flags')}",
        f"story={s.get('causal_reconstruction')}",
    ]
    return "\n".join(lines) + "\n"


def held_combine_radius_resize_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path
    import json

    out: list[dict[str, Any]] = []
    p = Path(run_dir)
    for path in sorted(p.glob("**/consequences*.json")):
        try:
            data = json.loads(path.read_text())
        except Exception:
            continue
        events = data.get("events") or data.get("event_refs") or []
        if not isinstance(events, list):
            continue
        for e in events:
            if not isinstance(e, dict):
                continue
            kind = str(e.get("kind") or e.get("receipt_kind") or "")
            if "HELD_COMBINE_GEOMETRY_RESIZE" in kind or kind == "held_combine_geometry_resize":
                out.append(dict(e))
    return out
