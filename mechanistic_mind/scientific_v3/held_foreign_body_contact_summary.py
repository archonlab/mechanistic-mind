"""Analyzer section: HELD OBJECT / FOREIGN BODY CONTACT FACTS."""
from __future__ import annotations

from typing import Any


SECTION_TITLE = "HELD OBJECT / FOREIGN BODY CONTACT FACTS"


def summarize_held_foreign_body_contact(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    begins = [e for e in rows if e.get("contact_phase") == "BEGIN" or e.get("phase") == "BEGIN"]
    ends = [e for e in rows if e.get("contact_phase") == "END" or e.get("phase") == "END"]
    persists = [e for e in rows if e.get("contact_phase") == "PERSIST" or e.get("phase") == "PERSIST"]
    endpoint = sum(1 for e in rows if e.get("detection_mode") == "ENDPOINT_OVERLAP")
    swept = sum(1 for e in rows if e.get("detection_mode") == "SWEPT_CROSSING")
    by_policy: dict[str, int] = {}
    for e in rows:
        p = str(e.get("transition_policy") or "UNKNOWN")
        by_policy[p] = by_policy.get(p, 0) + 1
    response_ok = all(
        (not e.get("collision_response_applied"))
        and (not e.get("impulse_transferred"))
        and (not e.get("position_corrected"))
        and (not e.get("velocity_changed"))
        and (not e.get("sound_emitted"))
        and (not e.get("damage_applied"))
        and (not e.get("auto_release"))
        and (not e.get("holder_mediation"))
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
        "by_transition_policy": dict(sorted(by_policy.items())),
        "response_flags_all_false": response_ok,
        "contact_fact_only": True,
        "agent_accessible": False,
    }


def format_held_foreign_body_contact_section(s: dict[str, Any]) -> str:
    if not s:
        return f"{SECTION_TITLE}\n  (no receipts)"
    lines = [
        SECTION_TITLE,
        f"  events: {s.get('event_count')}  BEGIN={s.get('begin')} PERSIST={s.get('persist')} END={s.get('end')}",
        f"  detection: endpoint={s.get('endpoint_detections')} swept={s.get('swept_detections')}",
        f"  by transition_policy: {s.get('by_transition_policy')}",
        f"  response_flags_all_false: {s.get('response_flags_all_false')}",
        "  HELD OBJECT ↔ FOREIGN BODY CONTACT FACT · NO IMPULSE · NO DAMAGE · NO RELEASE · NO SOUND",
    ]
    return "\n".join(lines)


def held_foreign_body_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
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
        if "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT" in kind or kind == "held_resource_object_foreign_body_contact":
            out.append(row)
        payload = row.get("held_foreign_body_contact") or row.get("receipt")
        if isinstance(payload, dict) and (
            payload.get("kind") == "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT"
            or payload.get("receipt_kind") == "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT"
        ):
            out.append(payload)
    return out
