"""Analyzer section: SURFACE ELEVATION SUPPORT / ENERGY-ACCOUNTED MICRORELIEF."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.surface_elevation_support import (
    ANALYZER_SECTION,
    BANNER,
    MECHANISM_ID,
    RECEIPT_KIND,
)


def summarize_surface_elevation_support(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    kinds: dict[str, int] = {}
    for e in rows:
        for k in e.get("event_kinds") or ([e.get("event_kind")] if e.get("event_kind") else []):
            if k:
                kinds[str(k)] = kinds.get(str(k), 0) + 1
    accepted = sum(1 for e in rows if e.get("accepted") is True)
    blocked = sum(1 for e in rows if e.get("accepted") is False)
    work = sum(float(e.get("work_debit") or 0.0) for e in rows)
    kin = sum(float(e.get("kinetic_paid") or 0.0) for e in rows)
    return {
        "mechanism": MECHANISM_ID,
        "section": ANALYZER_SECTION,
        "banner": BANNER,
        "n_receipts": len(rows),
        "accepted": accepted,
        "blocked": blocked,
        "event_kind_counts": kinds,
        "work_debit_total": work,
        "kinetic_paid_total": kin,
        "physical_height_scale": 1.0,
        "free_pe_snap": False,
        "free_pe_gain": False,
        "researcher_only": True,
    }


def format_surface_elevation_support_section(s: dict[str, Any]) -> str:
    kinds = s.get("event_kind_counts") or {}
    kind_lines = [f"    {k}: {v}" for k, v in sorted(kinds.items())]
    return "\n".join([
        f"## {ANALYZER_SECTION}",
        f"  banner: {BANNER}",
        f"  receipts: {s.get('n_receipts', 0)}",
        f"  accepted: {s.get('accepted', 0)}",
        f"  blocked: {s.get('blocked', 0)}",
        f"  work debit total (body reservoir): {s.get('work_debit_total', 0.0)}",
        f"  kinetic paid total (FREE): {s.get('kinetic_paid_total', 0.0)}",
        f"  physical_height_scale: 1.0",
        f"  free_pe_snap: False",
        f"  free_pe_gain: False",
        "  event kinds:",
        *(kind_lines or ["    (none)"]),
    ])


def surface_elevation_support_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    from pathlib import Path
    import json
    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/*")):
        if path.suffix not in {".json", ".jsonl"}:
            continue
        try:
            text = path.read_text()
        except Exception:
            continue
        if RECEIPT_KIND not in text and MECHANISM_ID not in text:
            continue
        try:
            if path.suffix == ".jsonl":
                for line in text.splitlines():
                    if not line.strip():
                        continue
                    row = json.loads(line)
                    if isinstance(row, dict) and (
                        row.get("receipt_kind") == RECEIPT_KIND or row.get("mechanism") == MECHANISM_ID
                    ):
                        out.append(row)
            else:
                data = json.loads(text)
                if isinstance(data, dict) and (
                    data.get("receipt_kind") == RECEIPT_KIND or data.get("mechanism") == MECHANISM_ID
                ):
                    out.append(data)
                elif isinstance(data, list):
                    for row in data:
                        if isinstance(row, dict) and (
                            row.get("receipt_kind") == RECEIPT_KIND or row.get("mechanism") == MECHANISM_ID
                        ):
                            out.append(row)
        except Exception:
            continue
    return out
