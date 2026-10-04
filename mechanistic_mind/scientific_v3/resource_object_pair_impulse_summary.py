"""Analyzer section: RESOURCE OBJECT PAIR CONTACT RESPONSE."""
from __future__ import annotations

from typing import Any


SECTION_TITLE = "RESOURCE OBJECT PAIR CONTACT RESPONSE"


def summarize_resource_object_pair_impulse(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    applied = [e for e in rows if e.get("impulse_transferred")]
    corrected = [e for e in rows if e.get("position_corrected")]
    multi = [e for e in rows if e.get("reason") == "MULTI_CONTACT_COMPONENT_NOT_RESOLVED"]
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
        "multi_contact_unresolved": len(multi),
        "by_reason": dict(sorted(by_reason.items())),
        "j_min": min(js) if js else None,
        "j_max": max(js) if js else None,
        "sound_emitted_all_false": sound_ok,
        "friction_all_false": friction_ok,
        "agent_accessible": False,
        "mass_compliance_normal_response": True,
        "multi_contact_policy": "VARIANT_A_ISOLATED_PAIRS_ONLY",
        "compliance_law": "SERIES_SOFTNESS_V1",
    }


def format_resource_object_pair_impulse_section(s: dict[str, Any]) -> str:
    if not s:
        return f"{SECTION_TITLE}\n  (no receipts)"
    lines = [
        SECTION_TITLE,
        f"  events: {s.get('event_count')}  impulses={s.get('impulses_applied')} corrections={s.get('position_corrections')} multi_unresolved={s.get('multi_contact_unresolved')}",
        f"  by reason: {s.get('by_reason')}",
        f"  j range: {s.get('j_min')} .. {s.get('j_max')}",
        f"  sound_emitted_all_false: {s.get('sound_emitted_all_false')}",
        f"  friction_all_false: {s.get('friction_all_false')}",
        "  OBJECT/OBJECT MASS + COMPLIANCE NORMAL RESPONSE · NO FRICTION · NO SOUND · MULTI-CONTACT: ISOLATED PAIRS ONLY",
    ]
    return "\n".join(lines)


def resource_object_pair_impulse_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
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
        if kind in (
            "resource_object_pair_contact_response",
            "RESOURCE_OBJECT_PAIR_CONTACT_RESPONSE",
        ):
            out.append(row)
            continue
        payload = row.get("resource_object_pair_contact_impulse") or row.get("receipt")
        if isinstance(payload, dict) and payload.get("receipt_kind") == "RESOURCE_OBJECT_PAIR_CONTACT_RESPONSE":
            out.append(payload)
        for ev in row.get("event_refs") or []:
            if isinstance(ev, dict) and str(ev.get("kind") or "") == "resource_object_pair_contact_response":
                out.append(ev)
    return out
