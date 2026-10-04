"""WORLD MATERIAL TRANSACTIONS. Reads transaction receipts only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVENT = "WORLD_MATERIAL_TRANSACTION"


def _rows(events: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    found = []
    for event in events or []:
        if not isinstance(event, dict):
            continue
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else event
        kind = str(event.get("event") or event.get("kind") or evidence.get("event") or "")
        if kind != EVENT and event.get("kind") != "world_material_transaction":
            continue
        found.append(evidence if evidence.get("event") or evidence.get("status") else event)
    return found


def summarize_world_material(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    rows = _rows(events)
    committed = [row for row in rows if row.get("status") == "COMMITTED"]
    rejected = [row for row in rows if row.get("status") == "REJECTED"]
    operations: dict[str, int] = {}
    residual_max = 0.0
    stale = 0
    for row in rows:
        kind = str(row.get("operation_kind") or "")
        if kind:
            operations[kind] = operations.get(kind, 0) + 1
        if str(row.get("rejection_reason") or "").startswith("stale"):
            stale += 1
        conservation = row.get("conservation") if isinstance(row.get("conservation"), dict) else {}
        for domain in conservation.values():
            if not isinstance(domain, dict):
                continue
            if "residual_max_abs" in domain:
                residual_max = max(residual_max, abs(float(domain["residual_max_abs"])))
            elif "residual" in domain:
                residual_max = max(residual_max, abs(float(domain["residual"])))
    return {
        "section": "WORLD MATERIAL TRANSACTIONS",
        "planned_count": len(rows),
        "committed_count": len(committed),
        "rejected_count": len(rejected),
        "operation_counts": operations,
        "stale_conflicts": stale,
        "residual_max_abs": residual_max,
        "mass_conservation": "VERIFIED" if committed and residual_max <= 1e-9 else ("NOT_AVAILABLE" if not rows else "OBSERVED"),
        "material_created_without_source": "VERIFIED" if committed and residual_max <= 1e-9 else ("NOT_AVAILABLE" if not rows else "NOT_ESTABLISHED"),
        "material_removed_without_sink": "VERIFIED" if committed and residual_max <= 1e-9 else ("NOT_AVAILABLE" if not rows else "NOT_ESTABLISHED"),
        "endogenous_intervention_split": "NOT_AVAILABLE",
        "recipe_match": False,
        "OBSERVED": ["transaction_receipt"] if rows else [],
        "VERIFIED": ["mass", "quantity", "components"] if committed and residual_max <= 1e-9 else [],
        "REJECTED": [str(row.get("rejection_reason")) for row in rejected[:8]],
        "NOT_AVAILABLE": [] if rows else ["transaction_receipt"],
        "NOT_ESTABLISHED": ["recipe", "reward", "lifecycle", "excavation"],
    }


def format_world_material_section(summary: dict[str, Any] | None) -> str:
    summary = summary or {}
    return "\n".join([
        "WORLD MATERIAL TRANSACTIONS",
        f"  committed_count: {summary.get('committed_count')}",
        f"  rejected_count: {summary.get('rejected_count')}",
        f"  operation_counts: {summary.get('operation_counts')}",
        f"  stale_conflicts: {summary.get('stale_conflicts')}",
        f"  residual_max_abs: {summary.get('residual_max_abs')}",
        f"  MASS_CONSERVATION = {summary.get('mass_conservation')}",
        f"  MATERIAL_WITHOUT_SOURCE = {summary.get('material_created_without_source')}",
        f"  MATERIAL_WITHOUT_SINK = {summary.get('material_removed_without_sink')}",
        f"  ENDOGENOUS_INTERVENTION_SPLIT = {summary.get('endogenous_intervention_split')}",
        "  RECIPE = NOT_ESTABLISHED",
        "  EXCAVATION = NOT_ESTABLISHED",
        "  OBSERVED: " + ", ".join(summary.get("OBSERVED") or ["NOT_AVAILABLE"]),
        "  VERIFIED: " + ", ".join(summary.get("VERIFIED") or ["NOT_AVAILABLE"]),
        "  NOT_ESTABLISHED: " + ", ".join(summary.get("NOT_ESTABLISHED") or []),
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
                if isinstance(ref, dict) and ref.get("kind") == "world_material_transaction":
                    found.append(ref)
    return found
