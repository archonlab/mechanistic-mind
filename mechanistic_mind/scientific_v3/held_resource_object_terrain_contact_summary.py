"""Analyzer section: HELD RESOURCE OBJECT / TERRAIN CONTACT FACTS."""
from __future__ import annotations

from typing import Any


SECTION_TITLE = "HELD RESOURCE OBJECT / TERRAIN CONTACT FACTS"


def summarize_held_resource_object_terrain_contact(
    events: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    begins = [e for e in rows if e.get("phase") == "BEGIN" or e.get("contact_phase") == "BEGIN"]
    ends = [e for e in rows if e.get("phase") == "END" or e.get("contact_phase") == "END"]
    persists = [e for e in rows if e.get("phase") == "PERSIST" or e.get("contact_phase") == "PERSIST"]
    endpoint = sum(1 for e in rows if e.get("detection_mode") == "ENDPOINT_OVERLAP")
    swept = sum(1 for e in rows if e.get("detection_mode") == "SWEPT_CROSSING")
    episodes = sorted(
        {
            str(e.get("episode_id"))
            for e in rows
            if e.get("episode_id")
        }
    )
    end_reasons: dict[str, int] = {}
    for e in ends:
        r = str(e.get("end_reason") or "UNKNOWN")
        end_reasons[r] = end_reasons.get(r, 0) + 1
    objects = sorted({str(e.get("object_id")) for e in rows if e.get("object_id")})
    holders = sorted({str(e.get("holder_body_id")) for e in rows if e.get("holder_body_id")})
    coverage = "NOT_AVAILABLE"
    if rows:
        coverage = "FULL" if (begins or persists or ends) else "PARTIAL"
    response_ok = all(
        (not e.get("impulse_transferred"))
        and (not e.get("work_transmission"))
        and (not e.get("material_failure"))
        and (not e.get("wmt_invoked"))
        and (not e.get("sound_emitted"))
        and (not e.get("automatic_release"))
        and (not e.get("damage"))
        for e in rows
    ) if rows else True
    return {
        "section": SECTION_TITLE,
        "evidence_coverage": coverage,
        "event_count": len(rows),
        "begin": len(begins),
        "persist": len(persists),
        "end": len(ends),
        "unique_episodes": len(episodes),
        "episode_ids": episodes[:64],
        "object_ids": objects[:64],
        "holder_body_ids": holders[:64],
        "endpoint_detections": endpoint,
        "swept_detections": swept,
        "end_reasons": dict(sorted(end_reasons.items())),
        "response_flags_all_false": response_ok,
        "contact_fact_only": True,
        "work_transmission": False,
        "material_failure": False,
        "impulse": False,
        "sound": False,
        "agent_accessible": False,
        "no_tool_inference": True,
        "no_excavation_inference": True,
    }


def format_held_resource_object_terrain_contact_section(s: dict[str, Any]) -> str:
    if not s:
        return f"{SECTION_TITLE}\n  (no receipts)"
    lines = [
        SECTION_TITLE,
        f"  evidence_coverage: {s.get('evidence_coverage')}",
        f"  events: {s.get('event_count')}  BEGIN={s.get('begin')} PERSIST={s.get('persist')} END={s.get('end')}",
        f"  unique_episodes: {s.get('unique_episodes')}  objects={s.get('object_ids')}  holders={s.get('holder_body_ids')}",
        f"  detection: endpoint={s.get('endpoint_detections')} swept={s.get('swept_detections')}",
        f"  end_reasons: {s.get('end_reasons')}",
        f"  response_flags_all_false: {s.get('response_flags_all_false')}",
        "  HELD OBJECT ↔ TERRAIN CONTACT GEOMETRY · RESEARCHER-ONLY · GEOMETRY FACT ONLY",
        "  NO WORK TRANSMISSION · NO TERRAIN FAILURE · NO IMPULSE · NO SOUND",
        "  (no tool-use / digging / excavation inference)",
    ]
    return "\n".join(lines)


def held_resource_object_terrain_contact_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
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
        if (
            "HELD_RESOURCE_OBJECT_TERRAIN_CONTACT" in kind
            or kind == "held_resource_object_terrain_contact"
        ):
            out.append(row)
            continue
        payload = row.get("held_resource_object_terrain_contact") or row.get("receipt")
        if isinstance(payload, dict) and (
            "HELD_RESOURCE_OBJECT_TERRAIN_CONTACT" in str(payload.get("kind") or "")
            or payload.get("mechanism") == "held_resource_object_terrain_contact_geometry"
        ):
            out.append(payload)
    return out
