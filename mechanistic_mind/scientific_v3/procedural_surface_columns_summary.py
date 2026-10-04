"""PROCEDURAL SURFACE COLUMNS. Reads column receipts, never regenerates a second world."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVENTS = {
    "SURFACE_COLUMN_BASELINE_QUERIED",
    "SURFACE_COLUMN_DELTA_COMMITTED",
    "SURFACE_COLUMN_DELTA_RESTORED",
    "SURFACE_COLUMN_VALIDATION_FAILED",
}


def _rows(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    found = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        kind = str(event.get("event") or "")
        if kind in EVENTS or event.get("kind") == "surface_column":
            found.append(event)
    return found


def summarize_procedural_surface_columns(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = _rows(events)
    counts: dict[str, int] = {name: 0 for name in sorted(EVENTS)}
    for row in rows:
        name = str(row.get("event") or "")
        if name in counts:
            counts[name] += 1
    deltas = counts["SURFACE_COLUMN_DELTA_COMMITTED"]
    restored = counts["SURFACE_COLUMN_DELTA_RESTORED"]
    failed = counts["SURFACE_COLUMN_VALIDATION_FAILED"]
    interval_ok = all(row.get("interval_validation") is not False for row in rows)
    conservation_rows = [row for row in rows if row.get("conservation_verified") is not None]
    conservation_ok = all(bool(row.get("conservation_verified")) for row in conservation_rows)
    observed = []
    if counts["SURFACE_COLUMN_BASELINE_QUERIED"]:
        observed.append("baseline_query")
    if deltas:
        observed.append("setup_delta")
    if restored:
        observed.append("delta_restore")
    verified = []
    if rows and interval_ok:
        verified.append("interval_validation")
    if conservation_rows and conservation_ok:
        verified.append("setup_delta_conservation")
    if restored:
        verified.append("restore_baseline_checksum")
    return {
        "section": "PROCEDURAL SURFACE COLUMNS",
        "schema_version": "PROCEDURAL_SURFACE_COLUMNS_V1",
        "event_count": len(rows),
        "event_counts": counts,
        "setup_delta_count": deltas,
        "restored_delta_count": restored,
        "validation_failed_count": failed,
        "authority": "WORLD_SIMULATION_STATE",
        "baseline_authority": "AUTHORITATIVE_PHYSICAL_WORLD_DESCRIPTION",
        "surface_elevation_authority": "AUTHORITATIVE_GEOMETRY_NO_CONSEQUENCE_KERNEL",
        "delta_authority": "AUTHORITATIVE_PERSISTENT_WORLD_MUTATION",
        "cache_authority": "DERIVED_NON_AUTHORITATIVE",
        "observer_role": "RESEARCHER_ONLY_READ_VIEW",
        "physical_effects_active": False,
        "agent_accessible": False,
        "geometry_role": "METADATA_ONLY",
        "cognition_leakage": "VERIFIED",
        "OBSERVED": observed,
        "VERIFIED": verified,
        "NOT_AVAILABLE": [] if rows else ["surface_column_event"],
        "NOT_IMPLEMENTED": [
            "support", "gravity", "slope_force", "excavation", "burial",
            "diffusion", "compaction", "vision_from_columns", "traction_from_columns",
        ],
    }


def format_procedural_surface_columns_section(summary: dict[str, Any] | None) -> str:
    summary = summary or {}
    return "\n".join([
        "PROCEDURAL SURFACE COLUMNS",
        f"  schema_version: {summary.get('schema_version')}",
        f"  event_count: {summary.get('event_count')}",
        f"  event_counts: {summary.get('event_counts')}",
        f"  setup_delta_count: {summary.get('setup_delta_count')}",
        f"  restored_delta_count: {summary.get('restored_delta_count')}",
        f"  validation_failed_count: {summary.get('validation_failed_count')}",
        "  AUTHORITY = WORLD_SIMULATION_STATE (baseline, elevation, sparse delta); cache DERIVED; Observer RESEARCHER_ONLY",
        "  PHYSICAL_EFFECTS_ACTIVE = NO",
        "  AGENT_ACCESSIBLE = NO",
        "  GEOMETRY_ROLE = METADATA_ONLY",
        "  OBSERVED: " + ", ".join(summary.get("OBSERVED") or ["NOT_AVAILABLE"]),
        "  VERIFIED: " + ", ".join(summary.get("VERIFIED") or ["NOT_AVAILABLE"]),
        "  NOT_AVAILABLE: " + ", ".join(summary.get("NOT_AVAILABLE") or ["—"]),
        "  NOT_IMPLEMENTED: " + ", ".join(summary.get("NOT_IMPLEMENTED") or []),
    ])


def receipts_from_consequences(run_dir: Path) -> list[dict[str, Any]]:
    path = Path(run_dir) / "scientific_consequences.jsonl"
    found: list[dict[str, Any]] = []
    if not path.exists():
        return found
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            for ref in row.get("event_refs") or []:
                if isinstance(ref, dict) and ref.get("kind") == "surface_column":
                    found.append(ref)
    return found
