"""Researcher summary for held deposition radius shrink transaction."""
from __future__ import annotations

from typing import Any


def summarize_held_deposition_radius_shrink(receipts: list[dict[str, Any]]) -> dict[str, Any]:
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
                "object_id": r.get("object_id") or r.get("source_id"),
                "transaction_id": r.get("transaction_id"),
                "radius_before": r.get("radius_before"),
                "radius_after": r.get("radius_after") or r.get("radius_proposed"),
                "released_pe_magnitude": r.get("released_pe_magnitude"),
                "resize_classification": cls,
                "committed": r.get("committed"),
            }
        )
        if r.get("impact_sound_emitted") is True:
            flags.append(f"unexpected_impact_sound:{r.get('object_id')}")
        if r.get("impulse_emitted") is True:
            flags.append(f"unexpected_impulse:{r.get('object_id')}")
        if r.get("released_pe_credited_to_agent") is True:
            flags.append(f"unexpected_pe_credit:{r.get('object_id')}")
        if r.get("combine_resize") is True:
            flags.append(f"unexpected_combine_resize:{r.get('object_id')}")
    return {
        "receipt_count": len(receipts),
        "classification_counts": class_counts,
        "timelines": timelines,
        "flags": flags,
        "causal_reconstruction": (
            "explicit APPLY_TO_SURFACE → WMT quantity transfer proposal → "
            "post-transfer radius shrink proposal → PE dissipation ledger → "
            "atomic commit or reject → partial survivor shrink or source exhaustion removal"
        ),
        "combine_resize": False,
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_held_deposition_radius_shrink_section(s: dict[str, Any]) -> str:
    lines = [
        "## Held deposition radius shrink transaction",
        f"receipts={s.get('receipt_count', 0)}",
        f"classifications={s.get('classification_counts')}",
        f"flags={s.get('flags')}",
        f"story={s.get('causal_reconstruction')}",
    ]
    return "\n".join(lines) + "\n"


def held_deposition_radius_shrink_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
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
            if "HELD_DEPOSITION_GEOMETRY_SHRINK" in kind or kind == "held_deposition_geometry_shrink":
                out.append(dict(e))
    return out
