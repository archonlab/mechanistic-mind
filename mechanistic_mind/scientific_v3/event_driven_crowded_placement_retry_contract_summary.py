"""Researcher summary for event-driven crowded placement retry contract."""
from __future__ import annotations

from typing import Any


def summarize_crowded_placement_retry(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    by_cell: dict[str, list[dict[str, Any]]] = {}
    results: dict[str, int] = {}
    timelines: list[dict[str, Any]] = []
    for r in receipts:
        res = str(r.get("result") or "UNKNOWN")
        results[res] = int(results.get(res, 0)) + 1
        cx, cy = r.get("cell_x"), r.get("cell_y")
        if cx is None or cy is None:
            continue
        key = f"{int(cx)}|{int(cy)}"
        by_cell.setdefault(key, []).append(dict(r))
    for key, rows in sorted(by_cell.items()):
        rows_sorted = sorted(
            rows,
            key=lambda x: (int(x.get("tick") or 0), str(x.get("exertion_event_id") or "")),
        )
        # Reconstruct causal story for Analyzer (researcher-only).
        story = []
        for row in rows_sorted:
            story.append(
                {
                    "tick": row.get("tick"),
                    "result": row.get("result"),
                    "exertion_event_id": row.get("exertion_event_id"),
                    "retry_event_id": row.get("retry_event_id"),
                    "object_id": row.get("object_id"),
                    "accumulator_disposition": row.get("accumulator_disposition"),
                    "blocker_ids": (row.get("candidate_summary") or {}).get("blocker_ids"),
                }
            )
        timelines.append({"cell": key, "events": story})
    return {
        "receipt_count": len(receipts),
        "result_counts": results,
        "per_cell_timelines": timelines,
        "causal_reconstruction": (
            "attempt A physical exertion → threshold → crowded rejection → "
            "no mutation/object/ID → retained work → physical blocker movement → "
            "no automatic retry → attempt B new exertion → bounded retry → "
            "success or repeated rejection"
        ),
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_crowded_placement_retry_section(s: dict[str, Any]) -> str:
    lines = [
        "## Event-driven crowded placement retry contract",
        f"receipts={s.get('receipt_count', 0)}",
        f"results={s.get('result_counts')}",
        f"cells={len(s.get('per_cell_timelines') or [])}",
        f"story={s.get('causal_reconstruction')}",
    ]
    return "\n".join(lines) + "\n"


def crowded_placement_retry_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
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
            if kind in {"crowded_placement_retry", "CROWDED_PLACEMENT_RETRY"}:
                out.append(dict(e))
    return out
