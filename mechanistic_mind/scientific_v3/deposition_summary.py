"""Analyzer counts for explicit surface deposition. No causal or instrumental claims."""
from __future__ import annotations

import math
from typing import Any

TERRAIN_CONSEQUENCE = "NOT_IMPLEMENTED"
AGENT_DEPOSIT_PERCEPTION = "NOT_IMPLEMENTED"
INSTRUMENTAL_USE = "NOT_ESTABLISHED"

_COMMITTED = "SURFACE_DEPOSITION_COMMITTED"
_REJECTED = "SURFACE_DEPOSITION_REJECTED"


def _evidence(event: dict[str, Any]) -> dict[str, Any]:
    nested = event.get("evidence")
    if isinstance(nested, dict):
        return nested
    return event


def summarize_surface_depositions(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    attempts = committed = 0
    rejected_by_outcome: dict[str, int] = {}
    total_mass = 0.0
    total_quantity = 0.0
    created = updated = depleted = 0
    max_mass = max_quantity = max_component = 0.0
    cells: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for event in events or []:
        kind = str(event.get("type") or event.get("event") or event.get("kind") or "")
        evidence = _evidence(event)
        event_name = str(evidence.get("event") or kind)
        if event_name not in {_COMMITTED, _REJECTED}:
            continue
        attempts += 1
        outcome = str(evidence.get("outcome") or event_name)
        is_committed = event_name == _COMMITTED and evidence.get("committed") is not False
        if not is_committed:
            rejected_by_outcome[outcome] = rejected_by_outcome.get(outcome, 0) + 1
            rows.append({"tick": evidence.get("tick", event.get("tick")), "outcome": outcome, "committed": False})
            continue
        committed += 1
        delta = evidence.get("deposited_delta") if isinstance(evidence.get("deposited_delta"), dict) else {}
        mass = float(delta.get("mass") or 0.0)
        quantity = float(delta.get("quantity") or 0.0)
        total_mass += mass
        total_quantity += quantity
        if evidence.get("deposit_created"):
            created += 1
        if evidence.get("deposit_updated"):
            updated += 1
        if evidence.get("source_removed"):
            depleted += 1
        max_mass = max(max_mass, abs(float(evidence.get("mass_residual") or 0.0)))
        max_quantity = max(max_quantity, abs(float(evidence.get("quantity_residual") or 0.0)))
        residuals = evidence.get("component_residuals") if isinstance(evidence.get("component_residuals"), dict) else {}
        component_max = max((abs(float(v)) for v in residuals.values()), default=0.0)
        max_component = max(max_component, component_max)
        cell = evidence.get("resolved_cell") if isinstance(evidence.get("resolved_cell"), dict) else {}
        cell_key = str(evidence.get("deposit_id") or f"{cell.get('cell_x')},{cell.get('cell_y')}")
        after = evidence.get("deposit_state_after") if isinstance(evidence.get("deposit_state_after"), dict) else {}
        history = cells.setdefault(cell_key, {"deposit_id": evidence.get("deposit_id"), "cell": cell, "events": []})
        history["events"].append({
            "tick": evidence.get("tick", event.get("tick")),
            "composition": after.get("composition"),
            "effective_properties": after.get("effective_properties") or evidence.get("deposit_properties_after"),
            "derivation_version": evidence.get("derivation_version"),
            "mass": after.get("mass"),
            "quantity": after.get("quantity"),
        })
        rows.append({
            "tick": evidence.get("tick", event.get("tick")),
            "outcome": outcome,
            "committed": True,
            "source_object_id": evidence.get("source_object_id"),
            "deposit_id": evidence.get("deposit_id"),
            "resolved_cell": cell,
            "deposited_delta": delta,
            "source_state_after": evidence.get("source_state_after"),
            "deposit_properties_after": evidence.get("deposit_properties_after"),
            "derivation_version": evidence.get("derivation_version"),
            "causal_reason": evidence.get("causal_reason"),
            "terrain_effects_applied": evidence.get("terrain_effects_applied"),
        })
    finite_mass = total_mass if math.isfinite(total_mass) else 0.0
    finite_quantity = total_quantity if math.isfinite(total_quantity) else 0.0
    return {
        "deposition_attempts": attempts,
        "deposition_committed": committed,
        "deposition_rejected": attempts - committed,
        "rejected_by_outcome": rejected_by_outcome,
        "total_deposited_mass": finite_mass,
        "total_deposited_quantity": finite_quantity,
        "deposits_created": created,
        "deposits_updated": updated,
        "source_objects_depleted": depleted,
        "max_abs_mass_residual": max_mass,
        "max_abs_quantity_residual": max_quantity,
        "max_abs_component_residual": max_component,
        "cells_containing_deposits": len(cells),
        "per_cell_history": cells,
        "events": rows,
        "TERRAIN_CONSEQUENCE": TERRAIN_CONSEQUENCE,
        "AGENT_DEPOSIT_PERCEPTION": AGENT_DEPOSIT_PERCEPTION,
        "INSTRUMENTAL_USE": INSTRUMENTAL_USE,
        "mixed_with_resource_change": False,
        "note": "Transfer provenance only. TERRAIN_CONSEQUENCE = NOT_IMPLEMENTED.",
    }
