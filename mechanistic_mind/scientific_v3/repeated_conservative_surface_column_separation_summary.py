"""Researcher summary for repeated conservative surface-column separation."""
from __future__ import annotations

from typing import Any


def summarize_repeated_conservative_surface_column_separation(
    receipts: list[dict[str, Any]],
) -> dict[str, Any]:
    by_cell: dict[str, list[dict[str, Any]]] = {}
    classes: dict[str, int] = {}
    for r in receipts:
        cls = str(r.get("classification") or "UNKNOWN")
        classes[cls] = int(classes.get(cls, 0)) + 1
        cx, cy = r.get("cell_x"), r.get("cell_y")
        if cx is None or cy is None:
            continue
        key = f"{int(cx)}|{int(cy)}"
        by_cell.setdefault(key, []).append(dict(r))
    timelines = []
    for key, rows in sorted(by_cell.items()):
        rows_sorted = sorted(rows, key=lambda x: (int(x.get("tick") or 0), int(x.get("attempt_seq") or 0)))
        timelines.append({"cell": key, "events": rows_sorted})
    return {
        "receipt_count": len(receipts),
        "class_counts": classes,
        "per_cell_timelines": timelines,
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_repeated_conservative_surface_column_separation_section(s: dict[str, Any]) -> str:
    lines = [
        "## Repeated conservative surface-column separation",
        f"receipts={s.get('receipt_count', 0)}",
        f"classes={s.get('class_counts')}",
        f"cells={len(s.get('per_cell_timelines') or [])}",
    ]
    return "\n".join(lines) + "\n"


def repeated_conservative_surface_column_separation_receipts_from_consequences(
    run_dir,
) -> list[dict[str, Any]]:
    from pathlib import Path
    import json

    out: list[dict[str, Any]] = []
    p = Path(run_dir)
    for path in sorted(p.glob("**/consequences*.jsonl")):
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            for ev in row.get("event_refs") or row.get("events") or []:
                if not isinstance(ev, dict):
                    continue
                kind = str(ev.get("kind") or "")
                if (
                    kind == "repeated_conservative_surface_column_separation"
                    or ev.get("mechanism") == "repeated_conservative_surface_column_separation"
                    or ev.get("receipt_kind") == "REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION"
                ):
                    out.append(ev)
    return out
