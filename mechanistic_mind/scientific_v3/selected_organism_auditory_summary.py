"""Analyzer reconstruction for SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1 / SAV1."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt import (
    BOUNDARY,
    LEGACY_PARTIAL,
    LEGACY_UNAVAILABLE,
    MODE_LABEL,
    PROFILE,
    SCHEMA,
    VIEW_SCHEMA,
    WARNING_LABEL,
    profile_reference,
)


def summarize_selected_organism_auditory(
    receipts: list[dict[str, Any]] | None = None,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    receipts = [r for r in (receipts or []) if isinstance(r, dict)]
    meta = dict(meta or {})
    if not receipts:
        return {
            "schema": VIEW_SCHEMA,
            "receipt_schema": SCHEMA,
            "profile": PROFILE,
            "boundary": BOUNDARY,
            "mode_label": MODE_LABEL,
            "warning_label": WARNING_LABEL,
            "available": False,
            "status": LEGACY_UNAVAILABLE,
            "playback_affected_simulation": False,
            "mind_reading": False,
            "progress": {
                "mode": "UNAVAILABLE",
                "completed": 0,
                "total": 0,
                "percent": None,
                "note": "No auditory-boundary receipts — do not fabricate progress",
            },
            "section_title": MODE_LABEL,
            "causal_reconstruction": (
                "legacy/missing A5 boundary receipts → SAV1 unavailable "
                "(not reconstructed from stream, probe, pixels, or cognition)"
            ),
        }

    agents = sorted({str(r.get("agent_id")) for r in receipts if r.get("agent_id")})
    ticks = [int(r.get("scientific_tick", -1)) for r in receipts]
    total = len(receipts)
    # Partial legacy: has left/right but missing V1 schema
    partial = sum(1 for r in receipts if r.get("schema") != SCHEMA)
    return {
        "schema": VIEW_SCHEMA,
        "receipt_schema": SCHEMA,
        "profile": PROFILE,
        "boundary": BOUNDARY,
        "mode_label": MODE_LABEL,
        "warning_label": WARNING_LABEL,
        "available": True,
        "status": "SAV1_RECEIPTS_PRESENT" if partial == 0 else LEGACY_PARTIAL,
        "profile_reference": profile_reference(),
        "agent_ids": agents,
        "receipt_count": total,
        "tick_range": [min(ticks), max(ticks)] if ticks else None,
        "preview": receipts[:16],
        "playback_affected_simulation": False,
        "mind_reading": False,
        "semantic_interpretation": False,
        "organism_accessible_fields": ["left_receptor_channels", "right_receptor_channels"],
        "researcher_only_fields": ["phenotype_clip_stamp", "observation_key", "limitations"],
        "progress": {
            "mode": "FINITE_RECEIPT_SCAN",
            "completed": total,
            "total": total,
            "percent": 100.0 if total else None,
            "note": "Progress = processed/total auditory-boundary receipts",
        },
        "section_title": MODE_LABEL,
        "causal_reconstruction": (
            "cognition-bound observation osc_l/r frozen as A5 receipt → "
            "Observer SAV1 visual · Analyzer reconstructs without subjective meaning"
        ),
        "meta": meta,
    }


def format_selected_organism_auditory_section(s: dict[str, Any]) -> str:
    prog = s.get("progress") or {}
    lines = [
        f"## {s.get('section_title') or MODE_LABEL}",
        "",
        str(s.get("causal_reconstruction") or ""),
        "",
        str(s.get("warning_label") or WARNING_LABEL),
        f"profile={s.get('profile')} · boundary={s.get('boundary')} · status={s.get('status')}",
        f"agents={s.get('agent_ids')} · receipts={s.get('receipt_count')} · ticks={s.get('tick_range')}",
        f"mind_reading={s.get('mind_reading')} · playback_affected_simulation={s.get('playback_affected_simulation')}",
        f"progress={prog.get('completed')}/{prog.get('total')} ({prog.get('percent')}%)",
        "",
    ]
    return "\n".join(lines)


def auditory_boundary_receipts_from_consequences(run_dir: Path | str) -> list[dict[str, Any]]:
    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    cons = root / "consequences.jsonl"
    if not cons.is_file():
        return out
    import json

    for line in cons.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        for ref in list(row.get("event_refs") or []):
            if not isinstance(ref, dict):
                continue
            if ref.get("kind") == "ORGANISM_AUDITORY_BOUNDARY_RECEIPT" or (
                str(ref.get("schema") or "") == SCHEMA
            ):
                out.append(dict(ref))
        # Full receipts may be nested under world snapshots in some packages
        emb = row.get("selected_organism_auditory_boundary_receipt")
        if isinstance(emb, dict):
            out.append(emb)
    return out
