"""Analyzer section: HELD-MEDIATED SURFACE EXERTION INTEGRATION."""
from __future__ import annotations

from typing import Any


SECTION_TITLE = "HELD-MEDIATED SURFACE EXERTION INTEGRATION"


def summarize_held_mediated_surface_exertion_integration(
    events: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    routed = [e for e in rows if e.get("setmr_routed")]
    failures = [e for e in rows if e.get("material_failure")]
    wmts = [e for e in rows if e.get("wmt_invoked")]
    coverage = "NOT_AVAILABLE"
    if rows:
        coverage = "FULL" if routed else "PARTIAL"
    return {
        "section": SECTION_TITLE,
        "evidence_coverage": coverage,
        "event_count": len(rows),
        "setmr_routed_count": len(routed),
        "material_failure_count": len(failures),
        "wmt_invoked_count": len(wmts),
        "same_accumulator": True,
        "held_specific_removal_path": False,
        "duplicate_accumulator": False,
        "agent_accessible": False,
        "researcher_only": True,
        "no_tool_inference": True,
    }


def format_held_mediated_surface_exertion_integration_section(s: dict[str, Any]) -> str:
    if not s:
        return f"{SECTION_TITLE}\n  (no receipts)"
    return "\n".join(
        [
            SECTION_TITLE,
            f"  evidence_coverage: {s.get('evidence_coverage')}",
            f"  events: {s.get('event_count')}  setmr_routed={s.get('setmr_routed_count')}",
            f"  failures={s.get('material_failure_count')}  wmt={s.get('wmt_invoked_count')}",
            f"  same_accumulator={s.get('same_accumulator')}  held_specific_path={s.get('held_specific_removal_path')}",
            "  agent_accessible: False",
        ]
    )


def held_mediated_surface_exertion_integration_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path
    import json

    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/consequences*.jsonl")) + sorted(root.glob("**/events*.jsonl")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if not isinstance(row, dict):
                continue
            kind = str(row.get("kind") or row.get("receipt_kind") or "")
            payload = (
                row.get("held_mediated_surface_exertion_integration")
                or row.get("receipt")
                or row
            )
            if not isinstance(payload, dict):
                continue
            if (
                kind == "held_mediated_surface_exertion_integration"
                or payload.get("receipt_kind") == "HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION"
                or payload.get("mechanism") == "held_mediated_surface_exertion_integration"
            ):
                out.append(dict(payload))
    return out
