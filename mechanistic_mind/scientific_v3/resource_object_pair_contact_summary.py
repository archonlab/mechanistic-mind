"""Analyzer section: RESOURCE OBJECT PAIR CONTACT FACTS."""
from __future__ import annotations

from typing import Any


SECTION_TITLE = "RESOURCE OBJECT PAIR CONTACT FACTS"


def summarize_resource_object_pair_contact(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    begins = [e for e in rows if e.get("contact_phase") == "BEGIN" or e.get("phase") == "BEGIN"]
    ends = [e for e in rows if e.get("contact_phase") == "END" or e.get("phase") == "END"]
    persists = [
        e for e in rows
        if e.get("contact_phase") in ("PERSIST", "PERSIST_AGGREGATE") or e.get("phase") == "PERSIST"
    ]
    endpoint = sum(1 for e in rows if e.get("detection_mode") == "ENDPOINT_OVERLAP")
    swept = sum(1 for e in rows if e.get("detection_mode") == "SWEPT_CROSSING")
    unique_pairs = len({e.get("pair_key") for e in rows if e.get("pair_key")})
    candidates = sum(int(e.get("count") or 1) for e in rows if e.get("contact_phase") == "PERSIST_AGGREGATE")
    candidates += len(begins) + len(ends)
    response_ok = all(
        (not e.get("collision_response_applied"))
        and (not e.get("impulse_transferred"))
        and (not e.get("position_corrected"))
        and (not e.get("velocity_changed"))
        and (not e.get("sound_emitted"))
        and (not e.get("composition_changed"))
        for e in rows
    ) if rows else True
    strategy = next(
        (e.get("broad_phase_strategy") for e in rows if e.get("broad_phase_strategy")),
        "BROAD_PHASE_ALL_PAIRS_V1",
    )
    return {
        "section": SECTION_TITLE,
        "event_count": len(rows),
        "begin": len(begins),
        "persist": len(persists),
        "end": len(ends),
        "candidates": candidates,
        "unique_pairs": unique_pairs,
        "duplicate_pair_checks_prevented": 0,
        "endpoint_detections": endpoint,
        "swept_detections": swept,
        "broad_phase_strategy": strategy,
        "response_flags_all_false": response_ok,
        "contact_fact_only": True,
        "agent_accessible": False,
    }


def format_resource_object_pair_contact_section(s: dict[str, Any]) -> str:
    if not s:
        return f"{SECTION_TITLE}\n  (no receipts)"
    lines = [
        SECTION_TITLE,
        f"  events: {s.get('event_count')}  BEGIN={s.get('begin')} PERSIST={s.get('persist')} END={s.get('end')}",
        f"  candidates≈{s.get('candidates')}  unique_pairs={s.get('unique_pairs')}",
        f"  detection: endpoint={s.get('endpoint_detections')} swept={s.get('swept_detections')}",
        f"  broad_phase_strategy: {s.get('broad_phase_strategy')}",
        f"  response_flags_all_false: {s.get('response_flags_all_false')}",
        "  OBJECT/OBJECT CONTACT FACT ONLY · NO IMPULSE · NO RESPONSE · NO SOUND",
    ]
    return "\n".join(lines)


def resource_object_pair_contact_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
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
        if "RESOURCE_OBJECT_PAIR_CONTACT" in kind or kind == "resource_object_pair_contact":
            out.append(row)
        payload = row.get("resource_object_pair_contact") or row.get("receipt")
        if isinstance(payload, dict) and (
            payload.get("kind") == "RESOURCE_OBJECT_PAIR_CONTACT"
            or payload.get("receipt_kind") == "RESOURCE_OBJECT_PAIR_CONTACT"
        ):
            out.append(payload)
    return out
