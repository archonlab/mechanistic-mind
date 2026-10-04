"""Analyzer section: FREE RESOURCE OBJECT GROUND FRICTION."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
    ANALYZER_SECTION,
    BANNER,
    MECHANISM_ID,
    RECEIPT_KIND,
)


def summarize_free_object_ground_friction(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    grounded = sum(1 for e in rows if e.get("mode") == "GROUNDED_COULOMB")
    airborne = sum(1 for e in rows if e.get("mode") == "AIRBORNE_CONSERVE")
    rests = sum(1 for e in rows if e.get("rest_transition"))
    dissipated = sum(float(e.get("kinetic_dissipated") or 0.0) for e in rows)
    return {
        "mechanism": MECHANISM_ID,
        "section": ANALYZER_SECTION,
        "banner": BANNER,
        "n_receipts": len(rows),
        "grounded_coulomb_steps": grounded,
        "airborne_conserve_steps": airborne,
        "rest_transitions": rests,
        "kinetic_dissipated_total": dissipated,
        "legacy_fok_damping_when_active": "BYPASSED",
        "AIR_DRAG": "NO",
        "researcher_only": True,
    }


def format_free_object_ground_friction_section(s: dict[str, Any]) -> str:
    return "\n".join([
        f"## {ANALYZER_SECTION}",
        f"  banner: {BANNER}",
        f"  receipts: {s.get('n_receipts', 0)}",
        f"  grounded Coulomb steps: {s.get('grounded_coulomb_steps', 0)}",
        f"  airborne conserve steps: {s.get('airborne_conserve_steps', 0)}",
        f"  rest transitions: {s.get('rest_transitions', 0)}",
        f"  K dissipated (no reservoir credit): {s.get('kinetic_dissipated_total', 0.0)}",
        f"  legacy FOK damping when active: BYPASSED",
        f"  AIR_DRAG: NO",
    ])


def free_object_ground_friction_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
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
