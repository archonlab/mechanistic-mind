"""Analyzer section: BODY / RESOURCE OBJECT CONTACT FACTS."""
from __future__ import annotations

from typing import Any


SECTION_TITLE = "BODY / RESOURCE OBJECT CONTACT FACTS"


def summarize_body_object_contact(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    begins = [e for e in rows if e.get("contact_phase") == "BEGIN" or e.get("phase") == "BEGIN"]
    ends = [e for e in rows if e.get("contact_phase") == "END" or e.get("phase") == "END"]
    persists = [e for e in rows if e.get("contact_phase") == "PERSIST" or e.get("phase") == "PERSIST"]
    endpoint = sum(1 for e in rows if e.get("detection_mode") == "ENDPOINT_OVERLAP")
    swept = sum(1 for e in rows if e.get("detection_mode") == "SWEPT_CROSSING")
    by_state: dict[str, int] = {}
    for e in rows:
        st = str(e.get("object_physical_state") or "UNKNOWN")
        by_state[st] = by_state.get(st, 0) + 1
    seps = [float(e["separation"]) for e in rows if e.get("separation") is not None]
    pens = [float(e["penetration"]) for e in rows if e.get("penetration") is not None]
    response_ok = all(
        (not e.get("collision_response_applied"))
        and (not e.get("impulse_transferred"))
        and (not e.get("position_corrected"))
        and (not e.get("velocity_changed"))
        and (not e.get("sound_emitted"))
        for e in rows
    ) if rows else True
    return {
        "section": SECTION_TITLE,
        "event_count": len(rows),
        "begin": len(begins),
        "persist": len(persists),
        "end": len(ends),
        "endpoint_detections": endpoint,
        "swept_detections": swept,
        "by_object_physical_state": dict(sorted(by_state.items())),
        "separation_min": min(seps) if seps else None,
        "separation_max": max(seps) if seps else None,
        "penetration_min": min(pens) if pens else None,
        "penetration_max": max(pens) if pens else None,
        "response_flags_all_false": response_ok,
        "contact_fact_only": True,
        "agent_accessible": False,
    }


def format_body_object_contact_section(s: dict[str, Any]) -> str:
    if not s:
        return f"{SECTION_TITLE}\n  (no receipts)"
    lines = [
        SECTION_TITLE,
        f"  events: {s.get('event_count')}  BEGIN={s.get('begin')} PERSIST={s.get('persist')} END={s.get('end')}",
        f"  detection: endpoint={s.get('endpoint_detections')} swept={s.get('swept_detections')}",
        f"  by state: {s.get('by_object_physical_state')}",
        f"  separation range: {s.get('separation_min')} .. {s.get('separation_max')}",
        f"  penetration range: {s.get('penetration_min')} .. {s.get('penetration_max')}",
        f"  response_flags_all_false: {s.get('response_flags_all_false')}",
        "  CONTACT FACT ONLY · NO IMPULSE · NO RESPONSE · NO SOUND",
    ]
    return "\n".join(lines)


def body_object_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path
    import json
    path = Path(run_dir) / "consequences.jsonl"
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = str(row.get("kind") or row.get("event") or "")
        if "BODY_RESOURCE_OBJECT_CONTACT" in kind:
            out.append(row)
        payload = row.get("body_object_contact") or row.get("receipt")
        if isinstance(payload, dict) and payload.get("kind") == "BODY_RESOURCE_OBJECT_CONTACT":
            out.append(payload)
    return out
