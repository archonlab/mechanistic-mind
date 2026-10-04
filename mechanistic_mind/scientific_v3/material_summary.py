"""Analyzer summary for non-semantic Acanthostega material transformations."""
from __future__ import annotations

import math
from typing import Any

from mechanistic_mind.physical_system.passive_material_properties import (
    DERIVATION_VERSION,
    derive_effective_properties,
)

CAUSAL_MATERIAL_EFFECTS = "NOT_IMPLEMENTED"


def _max_residual(residuals: Any) -> float:
    if not isinstance(residuals, dict):
        return 0.0
    vals = []
    for value in residuals.values():
        try:
            number = abs(float(value))
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            vals.append(number)
    return max(vals, default=0.0)


def _composition_of(material: Any) -> Any:
    if not isinstance(material, dict):
        return None
    if "composition" in material:
        return material.get("composition")
    return None


def _vector(report: dict[str, Any] | None) -> dict[str, float] | None:
    if not isinstance(report, dict):
        return None
    if "compliance" not in report and "surface_affinity" not in report:
        return None
    return {
        "compliance": float(report.get("compliance") or 0.0),
        "surface_affinity": float(report.get("surface_affinity") or 0.0),
    }


def audit_derived_properties(objects: list[Any] | None) -> dict[str, int]:
    """Count objects whose live composition derives a finite in-range vector."""
    valid = invalid = 0
    for obj in objects or []:
        composition = obj.get("composition") if isinstance(obj, dict) else getattr(obj, "composition", None)
        report = derive_effective_properties(composition)
        if report.get("property_derivation_verified"):
            valid += 1
        else:
            invalid += 1
    return {
        "objects_with_valid_derived_properties": valid,
        "objects_with_invalid_derived_properties": invalid,
    }


def summarize_material_transformations(
    events: list[dict[str, Any]] | None,
    objects: list[Any] | None = None,
) -> dict[str, Any]:
    attempts = committed = rejected = 0
    rows: list[dict[str, Any]] = []
    max_mass_residual = 0.0
    max_quantity_residual = 0.0
    max_component_residual = 0.0
    max_derivation_residual = 0.0
    derivation_version = None
    for event in events or []:
        kind = str(event.get("type") or event.get("event") or "")
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else event
        if kind not in {"MATERIAL_COMBINE_COMMITTED", "MATERIAL_COMBINE_REJECTED"}:
            continue
        attempts += 1
        outcome = str(evidence.get("outcome") or kind)
        if outcome == "MERGE_COMMITTED":
            committed += 1
        else:
            rejected += 1
        mass_residual = abs(float(evidence.get("mass_residual") or 0.0))
        quantity_residual = abs(float(evidence.get("quantity_residual") or 0.0))
        component_residuals = dict(evidence.get("component_residuals") or {})
        component_max = max((abs(float(v)) for v in component_residuals.values()), default=0.0)
        max_mass_residual = max(max_mass_residual, mass_residual)
        max_quantity_residual = max(max_quantity_residual, quantity_residual)
        max_component_residual = max(max_component_residual, component_max)
        before = evidence.get("effective_properties_before") if isinstance(evidence.get("effective_properties_before"), dict) else {}
        after = _vector(evidence.get("effective_properties_after") if isinstance(evidence.get("effective_properties_after"), dict) else None)
        output_composition = _composition_of(evidence.get("output"))
        reconstructed = derive_effective_properties(output_composition) if output_composition is not None else None
        reconstructed_after = _vector(reconstructed) if reconstructed is not None else None
        receipt_residual = _max_residual(evidence.get("property_derivation_residuals"))
        reconstruct_residual = 0.0
        if after is not None and reconstructed_after is not None:
            reconstruct_residual = max(
                abs(after["compliance"] - reconstructed_after["compliance"]),
                abs(after["surface_affinity"] - reconstructed_after["surface_affinity"]),
            )
        derivation_residual = max(receipt_residual, reconstruct_residual)
        max_derivation_residual = max(max_derivation_residual, derivation_residual)
        if evidence.get("derivation_version") or evidence.get("derivation"):
            derivation_version = str(evidence.get("derivation_version") or evidence.get("derivation"))
        rows.append({
            "tick": evidence.get("tick", event.get("tick")),
            "transformation_id": evidence.get("transformation_id"),
            "outcome": outcome,
            "left_input": evidence.get("left_input"),
            "right_input": evidence.get("right_input"),
            "output": evidence.get("output"),
            "contact_required": True,
            "command": "COMBINE",
            "mass_residual": mass_residual,
            "quantity_residual": quantity_residual,
            "component_residuals": component_residuals,
            "effective_properties_before": before or None,
            "effective_properties_after": after,
            "reconstructed_effective_properties": reconstructed_after,
            "derivation_version": evidence.get("derivation_version") or evidence.get("derivation"),
            "property_derivation_residual": derivation_residual,
            "property_derivation_verified": evidence.get("property_derivation_verified"),
            "passive_properties_only": evidence.get("passive_properties_only"),
            "world_effects_applied": evidence.get("world_effects_applied"),
            "body_effects_applied": evidence.get("body_effects_applied"),
            "material_interactions_applied": evidence.get("material_interactions_applied"),
            "semantic_effects": evidence.get("semantic_effects"),
        })
    audited = audit_derived_properties(objects)
    from mechanistic_mind.physical_system.physical_optical_material_profile import (
        coverage_summary as o1_coverage_summary,
        resolve_optical_material_profile,
        STATUS_RESOLVED,
    )

    o1_tx_rows: list[dict[str, Any]] = []
    for row in rows:
        out_comp = _composition_of(row.get("output"))
        if out_comp is None:
            continue
        o1 = resolve_optical_material_profile(out_comp)
        o1_tx_rows.append({
            "tick": row.get("tick"),
            "transformation_id": row.get("transformation_id"),
            "outcome": row.get("outcome"),
            "o1_status": o1.get("status"),
            "spectral_reflectance": o1.get("spectral_reflectance"),
            "organism_saw_material": False,
        })
    o1_coverage = o1_coverage_summary(objects=objects)
    return {
        "combine_attempts": attempts,
        "combine_committed": committed,
        "combine_rejected": rejected,
        "transformations": rows,
        "max_abs_mass_residual": max_mass_residual,
        "max_abs_quantity_residual": max_quantity_residual,
        "max_abs_component_residual": max_component_residual,
        "max_abs_derivation_residual": max_derivation_residual,
        "derivation_version": derivation_version or (DERIVATION_VERSION if audited["objects_with_valid_derived_properties"] or audited["objects_with_invalid_derived_properties"] else None),
        "objects_with_valid_derived_properties": audited["objects_with_valid_derived_properties"],
        "objects_with_invalid_derived_properties": audited["objects_with_invalid_derived_properties"],
        "CAUSAL_MATERIAL_EFFECTS": CAUSAL_MATERIAL_EFFECTS,
        "semantic_recipes_present": False,
        "note": "Mechanical provenance only. CAUSAL_MATERIAL_EFFECTS = NOT_IMPLEMENTED.",
        "physical_optical_material_profile": {
            **o1_coverage,
            "transaction_inheritance": o1_tx_rows,
            "organism_saw_material": False,
            "exo_interpreted_as_o1": False,
            "label": "MATERIAL PROPERTY ONLY · NO PHYSICAL LIGHT TRANSPORT · NOT DISPLAY RGB",
            "resolved_ok": int(o1_coverage.get("status_counts", {}).get(STATUS_RESOLVED, 0)),
        },
    }
