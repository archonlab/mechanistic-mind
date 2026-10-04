"""Analyzer section: EFFECTOR WORK AND HELD-LOAD INERTIA."""
from __future__ import annotations

from typing import Any


def summarize_effector_work_held_load(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [
        e
        for e in (events or [])
        if isinstance(e, dict)
        and (
            e.get("kind") == "effector_work_and_held_load_inertia_accounting"
            or e.get("mechanism") == "effector_work_and_held_load_inertia_accounting"
            or e.get("receipt_kind") == "EFFECTOR_HELD_LOAD_WORK_ACCOUNTING"
        )
    ]
    limited = [r for r in rows if r.get("work_limited")]
    unavailable = [r for r in rows if r.get("work_unavailable")]
    debits = [float(r.get("work_debit") or 0.0) for r in rows]
    scales = [float(r.get("admission_scale")) for r in rows if r.get("admission_scale") is not None]
    return {
        "section": "EFFECTOR WORK AND HELD-LOAD INERTIA",
        "event_count": len(rows),
        "work_limited_count": len(limited),
        "work_unavailable_count": len(unavailable),
        "total_work_debit": float(sum(debits)),
        "admission_scales": scales,
        "work_debits": debits,
        "swing_impulse": sum(1 for r in rows if r.get("swing_impulse")),
        "damage": sum(1 for r in rows if r.get("damage_applied")),
        "sound": sum(1 for r in rows if r.get("sound_emitted")),
        "provenance_privacy_complete": all(
            r.get("agent_accessible") is False for r in rows
        )
        if rows
        else True,
    }


def format_effector_work_held_load_section(s: dict[str, Any]) -> str:
    lines = [
        "EFFECTOR WORK AND HELD-LOAD INERTIA",
        f"  event_count: {s.get('event_count')}",
        f"  work_limited_count: {s.get('work_limited_count')}",
        f"  work_unavailable_count: {s.get('work_unavailable_count')}",
        f"  total_work_debit: {s.get('total_work_debit')}",
        f"  swing_impulse: {s.get('swing_impulse')} (expect 0)",
        f"  damage: {s.get('damage')} (expect 0)",
        f"  sound: {s.get('sound')} (expect 0)",
        f"  provenance_privacy_complete: {s.get('provenance_privacy_complete')}",
    ]
    return "\n".join(lines)


def effector_work_held_load_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path as _P
    import json

    root = _P(run_dir)
    out: list[dict[str, Any]] = []
    for name in ("consequences.jsonl", "events.jsonl", "tick_events.jsonl"):
        fp = root / name
        if not fp.exists():
            continue
        try:
            with fp.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    if not isinstance(row, dict):
                        continue
                    if (
                        row.get("kind") == "effector_work_and_held_load_inertia_accounting"
                        or row.get("receipt_kind") == "EFFECTOR_HELD_LOAD_WORK_ACCOUNTING"
                        or row.get("mechanism") == "effector_work_and_held_load_inertia_accounting"
                    ):
                        out.append(row)
                    refs = row.get("event_refs") or row.get("events") or []
                    if isinstance(refs, list):
                        for r in refs:
                            if isinstance(r, dict) and (
                                r.get("kind") == "effector_work_and_held_load_inertia_accounting"
                                or r.get("receipt_kind") == "EFFECTOR_HELD_LOAD_WORK_ACCOUNTING"
                            ):
                                out.append(r)
        except Exception:
            continue
    return out
