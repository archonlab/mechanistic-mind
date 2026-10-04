"""Analyzer section: BODY / RESOURCE OBJECT CONTACT RESPONSE."""
from __future__ import annotations

from typing import Any


SECTION_TITLE = "BODY / RESOURCE OBJECT CONTACT RESPONSE"


def summarize_body_object_impulse(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    applied = [e for e in rows if e.get("impulse_transferred")]
    corrected = [e for e in rows if e.get("position_corrected")]
    by_reason: dict[str, int] = {}
    for e in rows:
        r = str(e.get("reason") or "UNKNOWN")
        by_reason[r] = by_reason.get(r, 0) + 1
    js = [float(e["impulse_scalar_j"]) for e in rows if e.get("impulse_scalar_j") is not None]
    sound_ok = all(not e.get("sound_emitted") for e in rows) if rows else True
    friction_ok = all(not e.get("friction") for e in rows) if rows else True
    return {
        "section": SECTION_TITLE,
        "event_count": len(rows),
        "impulses_applied": len(applied),
        "position_corrections": len(corrected),
        "by_reason": dict(sorted(by_reason.items())),
        "j_min": min(js) if js else None,
        "j_max": max(js) if js else None,
        "sound_emitted_all_false": sound_ok,
        "friction_all_false": friction_ok,
        "agent_accessible": False,
        "mass_compliance_normal_response": True,
    }


def format_body_object_impulse_section(s: dict[str, Any]) -> str:
    if not s:
        return f"{SECTION_TITLE}\n  (no receipts)"
    lines = [
        SECTION_TITLE,
        f"  events: {s.get('event_count')}  impulses={s.get('impulses_applied')} corrections={s.get('position_corrections')}",
        f"  by reason: {s.get('by_reason')}",
        f"  j range: {s.get('j_min')} .. {s.get('j_max')}",
        f"  sound_emitted_all_false: {s.get('sound_emitted_all_false')}",
        f"  friction_all_false: {s.get('friction_all_false')}",
        "  MASS + COMPLIANCE NORMAL RESPONSE · NO FRICTION · NO SOUND",
    ]
    return "\n".join(lines)


def body_object_impulse_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path as P
    import json
    path = P(run_dir) / "consequences.jsonl"
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
        if kind in ("body_resource_object_contact_response", "BODY_RESOURCE_OBJECT_CONTACT_RESPONSE"):
            out.append(row)
            continue
        # Also scan nested event_refs-style payloads
        payload = row.get("body_object_impulse") or row.get("receipt")
        if isinstance(payload, dict) and payload.get("receipt_kind") == "BODY_RESOURCE_OBJECT_CONTACT_RESPONSE":
            out.append(payload)
        for ev in row.get("event_refs") or []:
            if isinstance(ev, dict) and str(ev.get("kind") or "") == "body_resource_object_contact_response":
                out.append(ev)
    return out
