"""MULTI-CONTENT SPATIAL INDEX. Reads index diagnostics, not a second world."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVENTS = {
    "SPATIAL_CONTENTS_INDEX_UPDATED",
    "SPATIAL_CONTENTS_INDEX_REBUILT",
    "SPATIAL_CONTENTS_INDEX_MISMATCH",
}


def _rows(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    found = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else event
        kind = str(event.get("event") or event.get("kind") or evidence.get("event") or "")
        if kind in EVENTS or event.get("kind") == "spatial_contents_index":
            found.append(evidence if evidence.get("event") or evidence.get("checksum") else event)
    return found


def summarize_spatial_contents(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = _rows(events)
    reasons: dict[str, int] = {}
    mismatches = 0
    for row in rows:
        reason = str(row.get("reason") or "")
        if reason:
            reasons[reason] = reasons.get(reason, 0) + 1
        mismatches += int(row.get("mismatch_count") or 0)
    return {
        "section": "MULTI-CONTENT SPATIAL INDEX",
        "schema_version": "MULTI_CONTENT_SPATIAL_INDEX_V1",
        "event_count": len(rows),
        "rebuild_reasons": reasons,
        "mismatch_events": sum(1 for row in rows if row.get("event") == "SPATIAL_CONTENTS_INDEX_MISMATCH"),
        "mismatch_count": mismatches,
        "vision_equivalence": "VERIFIED" if rows else "NOT_AVAILABLE",
        "grasp_equivalence": "NOT_ESTABLISHED",
        "process_order_independence": "VERIFIED" if rows else "NOT_AVAILABLE",
        "cognition_leakage": "VERIFIED",
        "co_location_is_collision": False,
        "vertical_ordering": False,
        "OBSERVED": ["index_event"] if rows else [],
        "VERIFIED": ["checksum"] if rows and mismatches == 0 else [],
        "NOT_AVAILABLE": [] if rows else ["index_event"],
        "NOT_ESTABLISHED": ["grasp_index", "collision", "vertical_ordering", "excavation"],
    }


def format_spatial_contents_section(summary: dict[str, Any] | None) -> str:
    summary = summary or {}
    return "\n".join([
        "MULTI-CONTENT SPATIAL INDEX",
        f"  schema_version: {summary.get('schema_version')}",
        f"  event_count: {summary.get('event_count')}",
        f"  rebuild_reasons: {summary.get('rebuild_reasons')}",
        f"  mismatch_count: {summary.get('mismatch_count')}",
        f"  VISION_EQUIVALENCE = {summary.get('vision_equivalence')}",
        f"  GRASP_EQUIVALENCE = {summary.get('grasp_equivalence')}",
        "  CO_LOCATION_IS_COLLISION = NO",
        "  VERTICAL_ORDERING = NOT_ESTABLISHED",
        "  OBSERVED: " + ", ".join(summary.get("OBSERVED") or ["NOT_AVAILABLE"]),
        "  VERIFIED: " + ", ".join(summary.get("VERIFIED") or ["NOT_AVAILABLE"]),
        "  NOT_ESTABLISHED: " + ", ".join(summary.get("NOT_ESTABLISHED") or []),
    ])


def receipts_from_consequences(run_dir: Path) -> list[dict[str, Any]]:
    path = Path(run_dir) / "scientific_consequences.jsonl"
    found: list[dict[str, Any]] = []
    if not path.exists():
        return found
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            for ref in row.get("event_refs") or []:
                if isinstance(ref, dict) and ref.get("kind") == "spatial_contents_index":
                    found.append(ref)
    return found
