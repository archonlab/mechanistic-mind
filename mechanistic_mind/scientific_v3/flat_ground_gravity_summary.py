"""Analyzer section: VERTICAL STATE / GRAVITY / FLAT SUPPORT (Phase C)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system.flat_ground_gravity import (
    ANALYZER_SECTION,
    BANNER,
    MECHANISM_ID,
    RECEIPT_FLAT_SUPPORT,
    RECEIPT_VERTICAL_STEP,
)


def summarize_flat_ground_gravity(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = list(events or [])
    steps = [e for e in rows if e.get("receipt_kind") == RECEIPT_VERTICAL_STEP or e.get("kind") == MECHANISM_ID]
    landings = [e for e in rows if e.get("receipt_kind") == RECEIPT_FLAT_SUPPORT or e.get("landed")]
    return {
        "section": ANALYZER_SECTION,
        "banner": BANNER,
        "mechanism": MECHANISM_ID,
        "event_count": len(steps),
        "landing_count": len(landings),
        "researcher_only": True,
        "agent_symbolic_z": False,
        "progress_bar": False,
    }


def format_flat_ground_gravity_section(s: dict[str, Any]) -> str:
    return "\n".join([
        f"## {ANALYZER_SECTION}",
        f"  banner: {BANNER}",
        f"  vertical_steps: {s.get('event_count')}",
        f"  landings: {s.get('landing_count')}",
        "  surface_elevation: METADATA_ONLY (not active)",
        "  slopes: NO",
        "  stacking: NO",
        "  agent_symbolic_z: NO",
    ])


def flat_ground_gravity_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/consequences*.json")) + sorted(root.glob("**/*receipt*.json")):
        try:
            import json
            data = json.loads(path.read_text())
        except Exception:
            continue
        rows = data if isinstance(data, list) else (data.get("events") or data.get("receipts") or [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            if (
                row.get("receipt_kind") in (RECEIPT_VERTICAL_STEP, RECEIPT_FLAT_SUPPORT)
                or row.get("kind") == MECHANISM_ID
                or row.get("mechanism") == MECHANISM_ID
            ):
                out.append(row)
    return out
