"""Acanthostega-only, non-semantic material composition merge.

This module conserves anonymous component amounts, mass, and quantity.  It does
not assign recipes, item classes, effects, nutrition, toxicity, or utility.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any

from .resource_objects import MaterialComponent

MATERIAL_COMPOSITION_MERGE = "material_composition_merge"
COMBINE = "COMBINE"
CONSERVATION_TOLERANCE = 1e-12


@dataclass
class MaterialCompositionMergeConfig:
    """Fresh default OFF. Missing snapshot field preserves legacy behavior."""

    enabled: bool = False
    conservation_tolerance: float = CONSERVATION_TOLERANCE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "MaterialCompositionMergeConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        return cls(**payload)


def material_composition_merge_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "material_composition_merge", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_material_composition_merge(config: Any, enabled: bool) -> None:
    if config is None:
        return
    cfg = getattr(config, "material_composition_merge", None)
    if cfg is None:
        cfg = MaterialCompositionMergeConfig()
        config.material_composition_merge = cfg
    cfg.enabled = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def canonical_components(*groups: tuple[MaterialComponent, ...]) -> tuple[MaterialComponent, ...]:
    totals: dict[str, list[float]] = {}
    for group in groups:
        for component in group:
            cid = str(component.component_id)
            amount = float(component.amount)
            if not cid or not math.isfinite(amount) or amount < 0.0:
                raise ValueError("invalid material component")
            totals.setdefault(cid, []).append(amount)
    return tuple(
        MaterialComponent(cid, math.fsum(totals[cid]))
        for cid in sorted(totals)
        if math.fsum(totals[cid]) > 0.0
    )


def _object_material(obj: Any) -> dict[str, Any]:
    return {
        "object_id": str(obj.object_id),
        "mass": float(obj.mass),
        "quantity": float(obj.quantity),
        "composition": [c.to_dict() for c in obj.composition],
    }


def merge_held_materials(
    *, world: Any, config: Any, body_id: str, left: Any, right: Any,
    confirmed_contact: bool, tick: int,
) -> dict[str, Any]:
    """Atomically merge RIGHT into LEFT after previously confirmed contact."""
    base = {
        "event": "MATERIAL_COMBINE_REJECTED",
        "command": COMBINE,
        "tick": int(tick),
        "body_id": str(body_id),
        "researcher_only": True,
        "semantic_effects": False,
    }
    if not material_composition_merge_is_active(config):
        return {**base, "outcome": "MERGE_UNAVAILABLE"}
    if left is None or right is None:
        return {**base, "outcome": "MERGE_REQUIRES_TWO_HELD_OBJECTS"}
    if not confirmed_contact:
        return {**base, "outcome": "MERGE_REQUIRES_CONFIRMED_CONTACT"}
    if left is right or str(left.object_id) == str(right.object_id):
        return {**base, "outcome": "MERGE_REQUIRES_DISTINCT_OBJECTS"}

    # Validate and compute the complete replacement before mutating world state.
    try:
        mass_before = math.fsum((float(left.mass), float(right.mass)))
        quantity_before = math.fsum((float(left.quantity), float(right.quantity)))
        if not math.isfinite(mass_before) or not math.isfinite(quantity_before):
            raise ValueError("non-finite totals")
        components = canonical_components(tuple(left.composition), tuple(right.composition))
        component_total = math.fsum(float(c.amount) for c in components)
        if abs(component_total - quantity_before) > float(config.material_composition_merge.conservation_tolerance):
            raise ValueError("component/quantity mismatch")
    except (TypeError, ValueError) as exc:
        return {**base, "outcome": "MERGE_INVALID_INPUT", "reason": str(exc)}

    before_left = _object_material(left)
    before_right = _object_material(right)
    transformation_id = f"material-merge-{int(tick):09d}-{str(body_id)}-{str(left.object_id)}"
    provenance = dict(getattr(left, "provenance", None) or {})
    history = list(provenance.get("material_transformations") or [])
    history_row = {
        "transformation_id": transformation_id,
        "kind": "COMPOSITION_MERGE",
        "tick": int(tick),
        "command": COMBINE,
        "contact_required": True,
        "left_input": before_left,
        "right_input": before_right,
        "survivor_policy": "LEFT_OBJECT_SURVIVES",
    }
    property_record = None
    from .passive_material_properties import (
        passive_material_properties_is_active,
        transformation_property_record,
    )
    if passive_material_properties_is_active(config):
        property_record = transformation_property_record(
            tuple(left.composition), tuple(right.composition), components,
        )
        history_row["passive_material_properties"] = property_record
    history.append(history_row)

    from mechanistic_mind.physical_system.physical_surface_optical_coating import (
        mix_survivor_optical,
    )
    mix_survivor_optical(
        config, left, right, float(left.quantity), float(right.quantity),
    )
    left.mass = mass_before
    left.quantity = quantity_before
    left.composition = components
    left.provenance = {**provenance, "material_transformations": history, "last_transformation_id": transformation_id}
    world.resource_objects = [obj for obj in (getattr(world, "resource_objects", None) or []) if obj is not right]

    after = _object_material(left)
    component_residuals: dict[str, float] = {}
    for c in components:
        before = math.fsum(
            float(x.amount) for obj in (before_left, before_right)
            for x in [MaterialComponent.from_dict(row) for row in obj["composition"]]
            if str(x.component_id) == str(c.component_id)
        )
        component_residuals[str(c.component_id)] = float(c.amount) - before
    return {
        **base,
        "event": "MATERIAL_COMBINE_COMMITTED",
        "outcome": "MERGE_COMMITTED",
        "transformation_id": transformation_id,
        "left_input": before_left,
        "right_input": before_right,
        "output": after,
        "survivor_object_id": str(left.object_id),
        "removed_object_id": str(right.object_id),
        "freed_manipulator_id": "RIGHT",
        "mass_residual": float(after["mass"] - mass_before),
        "quantity_residual": float(after["quantity"] - quantity_before),
        "component_residuals": component_residuals,
        "conserved": True,
        "replacement_policy": "LEFT_OBJECT_SURVIVES_RIGHT_REMOVED",
        **({} if property_record is None else property_record),
    }


def material_composition_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MATERIAL_COMPOSITION_MERGE,
        "name": "Material composition merge",
        "enabled": bool(enabled),
        "scope": "ACANTHOSTEGA_ONLY",
        "description": "Explicit COMBINE conserves anonymous components, mass, and quantity after held-object contact.",
    }
