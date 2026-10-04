"""Analyzer section: FREE RESOURCE OBJECT STATIC TRACTION (FOGF twin)."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.free_resource_object_static_traction_threshold import (
    ANALYZER_SECTION,
    BANNER,
    MECHANISM_ID,
    RECEIPT_KIND,
    STATE_STATIC_BREAKAWAY,
    STATE_STATIC_HOLD,
    STATE_KINETIC_SLIDE,
    STATE_NO_SUPPORT,
    STATE_NOT_ELIGIBLE,
    STATE_RELEASE_TRANSITION_NOT_ELIGIBLE,
)


def summarize_free_resource_object_static_traction(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = [e for e in (events or []) if isinstance(e, dict)]
    return {
        "mechanism": MECHANISM_ID,
        "section": ANALYZER_SECTION,
        "banner": BANNER,
        "n_receipts": len(rows),
        "static_hold_steps": sum(1 for e in rows if e.get("state_class") == STATE_STATIC_HOLD),
        "static_breakaway_steps": sum(1 for e in rows if e.get("state_class") == STATE_STATIC_BREAKAWAY),
        "kinetic_slide_steps": sum(1 for e in rows if e.get("state_class") == STATE_KINETIC_SLIDE),
        "no_support_steps": sum(1 for e in rows if e.get("state_class") == STATE_NO_SUPPORT),
        "not_eligible_steps": sum(1 for e in rows if e.get("state_class") == STATE_NOT_ELIGIBLE),
        "release_transition_not_eligible_steps": sum(
            1 for e in rows if e.get("state_class") == STATE_RELEASE_TRANSITION_NOT_ELIGIBLE
        ),
        "legacy_object_damping_bypassed": True,
        "double_ground_friction": False,
        "NORMAL_PHYSICAL_EFFECTS_ACTIVE": False,
        "N_LAW": "N_EQUALS_OBJECT_MASS_G_NO_NZ",
        "researcher_only": True,
    }


def format_free_resource_object_static_traction_section(s: dict[str, Any]) -> str:
    return "\n".join([
        f"## {ANALYZER_SECTION}",
        f"  banner: {BANNER}",
        f"  receipts: {s.get('n_receipts', 0)}",
        f"  STATIC_HOLD: {s.get('static_hold_steps', 0)}",
        f"  STATIC_BREAKAWAY: {s.get('static_breakaway_steps', 0)}",
        f"  KINETIC_SLIDE: {s.get('kinetic_slide_steps', 0)}",
        f"  NO_SUPPORT: {s.get('no_support_steps', 0)}",
        f"  NOT_ELIGIBLE: {s.get('not_eligible_steps', 0)}",
        f"  RELEASE_TRANSITION_NOT_ELIGIBLE: {s.get('release_transition_not_eligible_steps', 0)}",
        f"  legacy_object_damping_bypassed: YES",
        f"  double_ground_friction: NO",
        f"  N_LAW: N=m·g (no n_z)",
        f"  NORMAL_PHYSICAL_EFFECTS_ACTIVE: NO",
    ])


def free_resource_object_static_traction_receipts_from_consequences(run_dir) -> list[dict[str, Any]]:
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
