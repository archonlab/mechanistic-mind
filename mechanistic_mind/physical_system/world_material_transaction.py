"""Atomic material transactions for COMBINE and APPLY_TO_SURFACE.

The legacy functions remain the numerical authority. This module runs them on
detached copies, then replaces only the touched records. Optical coefficients
are intensive and are not a conserved stock.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any

MECHANISM_ID = "world_material_transactions"
EVENT_NAME = "WORLD_MATERIAL_TRANSACTION"
SCHEMA_VERSION = "WORLD_MATERIAL_TRANSACTION_V1"
TOLERANCE = 1e-12
HISTORY_LIMIT = 16
COMMITTED_ID_LIMIT = 64
PROVENANCE_LIMIT = 4


@dataclass
class WorldMaterialTransactionsConfig:
    """Fresh default OFF. Missing snapshot field keeps the legacy path."""

    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "WorldMaterialTransactionsConfig":
        if not data:
            return cls()
        payload = {key: data[key] for key in (f.name for f in fields(cls)) if key in data}
        return cls(**payload)


def world_material_transactions_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "world_material_transactions", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_world_material_transactions(config: Any, enabled: bool) -> None:
    if config is None:
        return
    cfg = getattr(config, "world_material_transactions", None)
    if cfg is None:
        cfg = WorldMaterialTransactionsConfig()
        config.world_material_transactions = cfg
    cfg.enabled = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def allocate_transaction_id(world: Any, tick: int) -> str:
    sequence = int(getattr(world, "material_transaction_sequence", 0) or 0)
    world.material_transaction_sequence = sequence + 1
    return f"material-tx-{int(tick):09d}-{sequence:04d}"


def _revision(entity: Any) -> int:
    return int(getattr(entity, "material_revision", 0) or 0)


def _find_object(world: Any, object_id: str) -> Any:
    for obj in getattr(world, "resource_objects", None) or []:
        if str(getattr(obj, "object_id", "")) == str(object_id):
            return obj
    return None


def _components(entity: Any) -> list[dict[str, float]]:
    rows = []
    for component in tuple(getattr(entity, "composition", ()) or ()):
        rows.append({
            "component_id": str(component.component_id),
            "amount": float(component.amount),
        })
    return rows


def _optical(entity: Any) -> dict[str, float] | None:
    optical = getattr(entity, "optical_response", None)
    if optical is None:
        return None
    return {"c0": float(optical[0]), "c1": float(optical[1]), "c2": float(optical[2])}


def material_summary(entity: Any, *, kind: str) -> dict[str, Any]:
    if entity is None:
        return {"entity_kind": kind, "entity_id": None}
    entity_id = str(getattr(entity, "deposit_id", None) or getattr(entity, "object_id", ""))
    return {
        "entity_kind": kind,
        "entity_id": entity_id,
        "mass": float(getattr(entity, "mass", 0.0) or 0.0),
        "quantity": float(getattr(entity, "quantity", 0.0) or 0.0),
        "composition": _components(entity),
        "optical_response": _optical(entity),
        "holder_body_id": getattr(entity, "holder_body_id", None),
        "manipulator_id": getattr(entity, "manipulator_id", None),
        "revision": _revision(entity),
    }


def _domain(before: float, after: float) -> dict[str, Any]:
    residual = float(after) - float(before)
    return {
        "before": float(before),
        "after": float(after),
        "residual": float(residual),
        "tolerance": TOLERANCE,
        "verified": bool(math.isfinite(residual) and abs(residual) <= TOLERANCE),
    }


def _component_domain(before: dict[str, float], after: dict[str, float]) -> dict[str, Any]:
    keys = sorted(set(before) | set(after))
    residuals = {key: float(after.get(key, 0.0)) - float(before.get(key, 0.0)) for key in keys}
    max_abs = max((abs(value) for value in residuals.values()), default=0.0)
    return {
        "before": {key: float(before.get(key, 0.0)) for key in keys},
        "after": {key: float(after.get(key, 0.0)) for key in keys},
        "residuals": residuals,
        "residual_max_abs": float(max_abs),
        "tolerance": TOLERANCE,
        "verified": bool(math.isfinite(max_abs) and max_abs <= TOLERANCE),
    }


def _totals(entity: Any) -> dict[str, float]:
    from mechanistic_mind.physical_system.passive_material_properties import canonical_amount_totals

    if entity is None:
        return {}
    return {str(key): float(value) for key, value in canonical_amount_totals(getattr(entity, "composition", ())).items()}


def _bound_provenance(previous: Any, *, transaction_id: str, source_ids: list[str], kind: str, tick: int) -> dict[str, Any]:
    prev = dict(previous or {}) if isinstance(previous, dict) else {}
    prev.pop("material_transformations", None)
    prev.pop("lineage_refs", None)
    transactions = [str(item) for item in (prev.get("source_transaction_ids") or []) if item]
    transactions.append(str(transaction_id))
    entities = [str(item) for item in (prev.get("source_entity_ids") or []) if item]
    entities.extend(str(item) for item in source_ids if item)
    created = prev.get("creation_tick")
    prev.update({
        "last_transaction_id": str(transaction_id),
        "source_transaction_ids": transactions[-PROVENANCE_LIMIT:],
        "source_entity_ids": entities[-PROVENANCE_LIMIT:],
        "transformation_kind": str(kind),
        "creation_tick": int(created if created is not None else tick),
    })
    return prev


def _remember(world: Any, receipt: dict[str, Any]) -> None:
    history = list(getattr(world, "material_transaction_history", None) or [])
    history.append(receipt)
    world.material_transaction_history = history[-HISTORY_LIMIT:]
    world.last_material_transaction_id = receipt.get("transaction_id")
    if receipt.get("status") == "COMMITTED":
        committed = list(getattr(world, "material_transaction_committed_ids", None) or [])
        committed.append(str(receipt.get("transaction_id")))
        world.material_transaction_committed_ids = committed[-COMMITTED_ID_LIMIT:]


def _base_receipt(plan: dict[str, Any], *, status: str, reason: str | None = None) -> dict[str, Any]:
    return {
        "event": EVENT_NAME,
        "transaction_id": plan.get("transaction_id"),
        "schema_version": SCHEMA_VERSION,
        "tick": plan.get("tick"),
        "sequence": plan.get("sequence"),
        "model_line": plan.get("model_line"),
        "public_preset": plan.get("public_preset"),
        "command": plan.get("command"),
        "actor_body_id": plan.get("actor_body_id"),
        "actor_agent_id": plan.get("actor_agent_id"),
        "selection_provenance": plan.get("selection_provenance"),
        "operation_kind": plan.get("operation_kind"),
        "input_refs": list(plan.get("input_refs") or []),
        "output_refs": list(plan.get("output_refs") or []),
        "preconditions": dict(plan.get("preconditions") or {}),
        "status": status,
        "rejection_reason": reason,
        "source_event_ids": list(plan.get("source_event_ids") or []),
        "expected_revisions": dict(plan.get("expected_revisions") or {}),
        "legacy_equivalence": True,
        "researcher_only": True,
        "agent_accessible": False,
        "semantic_effects": False,
        "recipe_match": False,
        "reward_created": False,
    }


def _stage(world: Any, objects: list[Any], deposits: dict[str, Any] | None = None) -> Any:
    stage = type("MaterialStage", (), {})()
    stage.resource_objects = list(objects)
    stage.surface_material_deposits = dict(deposits or {})
    stage.T = getattr(world, "T", None)
    stage.surface_optical_coating_generation = int(getattr(world, "surface_optical_coating_generation", 0) or 0)
    return stage


def _publish_generation(world: Any, stage: Any) -> None:
    world.surface_optical_coating_generation = int(getattr(stage, "surface_optical_coating_generation", 0) or 0)


def _stale(world: Any, expected: dict[str, int | None]) -> str | None:
    for key, revision in expected.items():
        if str(key).startswith("deposit:"):
            deposit_id = str(key).split(":", 1)[1]
            deposits = getattr(world, "surface_material_deposits", None) or {}
            current = deposits.get(deposit_id)
            actual = None if current is None else _revision(current)
            if revision is None and current is not None and _revision(current) != 0:
                return f"stale:{key}"
            if revision is not None and actual != int(revision):
                return f"stale:{key}"
            continue
        if str(key).startswith("column:"):
            # Surface column revisions (TRANSFER_SURFACE_COLUMN_SLICE); additive, other kinds untouched.
            from mechanistic_mind.physical_system.conservative_surface_column_transfer import (
                column_revision_for_key,
            )

            actual = column_revision_for_key(world, str(key))
            if actual is None:
                return f"missing:{key}"
            if actual != int(revision or 0):
                return f"stale:{key}"
            continue
        current = _find_object(world, key)
        if current is None:
            return f"missing:{key}"
        if _revision(current) != int(revision or 0):
            return f"stale:{key}"
    return None


def plan_combine(
    *,
    world: Any,
    config: Any,
    body_id: str,
    left: Any,
    right: Any,
    confirmed_contact: bool,
    tick: int,
    actor_agent_id: str | None = None,
    selection_provenance: str | None = None,
    actor_body: Any = None,
) -> dict[str, Any]:
    """Validate COMBINE without mutating authoritative state."""
    transaction_id = allocate_transaction_id(world, tick)
    sequence = int(getattr(world, "material_transaction_sequence", 1) or 1) - 1
    plan: dict[str, Any] = {
        "transaction_id": transaction_id,
        "sequence": sequence,
        "schema_version": SCHEMA_VERSION,
        "tick": int(tick),
        "model_line": str(getattr(config, "model_line", "") or ""),
        "public_preset": str(getattr(config, "public_preset", "") or ""),
        "command": "COMBINE",
        "operation_kind": "COMBINE",
        "actor_body_id": str(body_id),
        "actor_agent_id": actor_agent_id,
        "selection_provenance": selection_provenance,
        "status": "PLANNED",
        "input_refs": [],
        "output_refs": [],
        "source_event_ids": [],
        "expected_revisions": {},
        "preconditions": {},
        "config": config,
        "confirmed_contact": bool(confirmed_contact),
    }
    from mechanistic_mind.physical_system.material_composition import material_composition_merge_is_active

    checks = {
        "merge_active": bool(material_composition_merge_is_active(config)),
        "two_objects": left is not None and right is not None,
        "confirmed_contact": bool(confirmed_contact),
        "distinct": bool(left is not None and right is not None and left is not right and str(getattr(left, "object_id", "")) != str(getattr(right, "object_id", ""))),
    }
    plan["preconditions"] = checks
    if not all(checks.values()):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = "precondition"
        return plan
    try:
        mass = math.fsum((float(left.mass), float(right.mass)))
        quantity = math.fsum((float(left.quantity), float(right.quantity)))
        if not math.isfinite(mass) or not math.isfinite(quantity):
            raise ValueError("non-finite totals")
        from mechanistic_mind.physical_system.material_composition import canonical_components

        components = canonical_components(tuple(left.composition), tuple(right.composition))
        component_total = math.fsum(float(component.amount) for component in components)
        tolerance = float(getattr(config.material_composition_merge, "conservation_tolerance", TOLERANCE))
        if abs(component_total - quantity) > tolerance:
            raise ValueError("component/quantity mismatch")
    except (TypeError, ValueError) as exc:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = str(exc)
        return plan
    plan["input_refs"] = [str(left.object_id), str(right.object_id)]
    plan["output_refs"] = [str(left.object_id)]
    plan["expected_revisions"] = {
        str(left.object_id): _revision(left),
        str(right.object_id): _revision(right),
    }
    plan["left_id"] = str(left.object_id)
    plan["right_id"] = str(right.object_id)
    plan["mass_after"] = float(mass)
    plan["quantity_after"] = float(quantity)

    # Held COMBINE geometry resize admission (side-effect-free; may reject entire COMBINE).
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        held_combine_radius_resize_transaction_is_active,
        plan_held_combine_geometry_resize,
    )

    if held_combine_radius_resize_transaction_is_active(config):
        body = actor_body
        if body is None:
            for row in list(getattr(world, "detached_placement_body_refs", None) or []):
                if isinstance(row, (tuple, list)) and len(row) >= 2 and str(row[0]) == str(body_id):
                    body = row[1]
                    break
        geo = plan_held_combine_geometry_resize(
            world=world,
            config=config,
            left=left,
            right=right,
            body_id=str(body_id),
            actor_body=body,
            quantity_after=float(quantity),
            mass_after=float(mass),
        )
        geo["transaction_id"] = transaction_id
        geo["tick"] = int(tick)
        plan["held_combine_geometry_resize"] = geo
        if not geo.get("admitted", True) or str(geo.get("status") or "") == "REJECTED":
            plan["status"] = "REJECTED"
            plan["rejection_reason"] = str(
                geo.get("rejection_reason") or geo.get("resize_classification") or "geometry_resize"
            )
            return plan
    return plan


def plan_deposition(
    *,
    world: Any,
    config: Any,
    body: Any,
    body_id: str,
    held_object_id_at_tick_start: str | None,
    tick: int,
    runtime: Any = None,
    actor_agent_id: str | None = None,
    selection_provenance: str | None = None,
) -> dict[str, Any]:
    """Validate deposition without mutating authoritative state."""
    from mechanistic_mind.physical_system.explicit_surface_deposition import (
        explicit_surface_deposition_is_active,
    )
    from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT, held_object_for_holder
    from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_HELD

    transaction_id = allocate_transaction_id(world, tick)
    sequence = int(getattr(world, "material_transaction_sequence", 1) or 1) - 1
    source = held_object_for_holder(world, body_id, MANIP_LEFT)
    plan: dict[str, Any] = {
        "transaction_id": transaction_id,
        "sequence": sequence,
        "schema_version": SCHEMA_VERSION,
        "tick": int(tick),
        "model_line": str(getattr(config, "model_line", "") or ""),
        "public_preset": str(getattr(config, "public_preset", "") or ""),
        "command": "APPLY_TO_SURFACE",
        "operation_kind": "APPLY_TO_SURFACE",
        "actor_body_id": str(body_id),
        "actor_agent_id": actor_agent_id,
        "selection_provenance": selection_provenance,
        "status": "PLANNED",
        "input_refs": [],
        "output_refs": [],
        "source_event_ids": [],
        "expected_revisions": {},
        "preconditions": {},
        "config": config,
        "body": body,
        "runtime": runtime,
        "held_object_id_at_tick_start": held_object_id_at_tick_start,
    }
    held_ok = (
        source is not None
        and str(getattr(source, "physical_state", "")) == PHYSICAL_STATE_HELD
        and held_object_id_at_tick_start is not None
        and str(source.object_id) == str(held_object_id_at_tick_start)
    )
    checks = {
        "deposition_active": bool(explicit_surface_deposition_is_active(config)),
        "source_held_at_tick_start": bool(held_ok),
    }
    plan["preconditions"] = checks
    if not all(checks.values()):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = "precondition"
        return plan
    try:
        quantity = float(source.quantity)
        mass = float(source.mass)
        if not math.isfinite(quantity) or not math.isfinite(mass) or quantity < 0.0 or mass < 0.0:
            raise ValueError("non-finite source")
    except (TypeError, ValueError) as exc:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = str(exc)
        return plan
    from mechanistic_mind.physical_system.explicit_surface_deposition import deposit_id_for_cell

    cell = effector_cell_for_deposition(world, config, body, runtime)
    if cell is None:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = "cell"
        return plan
    deposit_id = deposit_id_for_cell(cell[0], cell[1])
    existing = (getattr(world, "surface_material_deposits", None) or {}).get(deposit_id)
    plan["input_refs"] = [str(source.object_id), deposit_id]
    plan["output_refs"] = [deposit_id]
    plan["source_id"] = str(source.object_id)
    plan["deposit_id"] = deposit_id
    plan["expected_revisions"] = {
        str(source.object_id): _revision(source),
        f"deposit:{deposit_id}": None if existing is None else _revision(existing),
    }

    # Held deposition geometry shrink admission (side-effect-free for material/geometry).
    from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import (
        held_deposition_radius_shrink_transaction_is_active,
        plan_held_deposition_geometry_shrink,
    )

    if held_deposition_radius_shrink_transaction_is_active(config):
        geo = plan_held_deposition_geometry_shrink(
            world=world,
            config=config,
            source=source,
            body_id=str(body_id),
            deposit_id=deposit_id,
        )
        geo["transaction_id"] = transaction_id
        geo["tick"] = int(tick)
        plan["held_deposition_geometry_shrink"] = geo
        if not geo.get("admitted", True) or str(geo.get("status") or "") == "REJECTED":
            plan["status"] = "REJECTED"
            plan["rejection_reason"] = str(
                geo.get("rejection_reason") or geo.get("resize_classification") or "geometry_shrink"
            )
            return plan
    return plan


def effector_cell_for_deposition(world: Any, config: Any, body: Any, runtime: Any) -> tuple[int, int] | None:
    from mechanistic_mind.physical_system.explicit_surface_deposition import resolve_deposit_cell
    from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT, effector_world_xy

    grid = getattr(world, "T", None)
    height = int(grid.shape[0]) if grid is not None else 32
    width = int(grid.shape[1]) if grid is not None else 32
    try:
        ex, ey = effector_world_xy(
            body, width=width, height=height, config=config, manipulator_id=MANIP_LEFT, runtime=runtime,
        )
    except (TypeError, ValueError):
        return None
    return resolve_deposit_cell(ex, ey, width=width, height=height)


def commit_material_transaction(world: Any, plan: dict[str, Any]) -> dict[str, Any]:
    """Apply one planned transaction, or reject it with authoritative state unchanged."""
    transaction_id = str(plan.get("transaction_id") or "")
    committed = list(getattr(world, "material_transaction_committed_ids", None) or [])
    if transaction_id and transaction_id in committed:
        receipt = _base_receipt(plan, status="REJECTED", reason="ALREADY_COMMITTED")
        _remember(world, receipt)
        # Remember appended it again only if status COMMITTED. Reject does not re-add.
        return {"legacy": None, "receipt": receipt}
    if plan.get("status") == "REJECTED":
        receipt = _base_receipt(plan, status="REJECTED", reason=str(plan.get("rejection_reason") or "precondition"))
        _remember(world, receipt)
        return {"legacy": None, "receipt": receipt}
    stale = _stale(world, dict(plan.get("expected_revisions") or {}))
    if stale is not None:
        receipt = _base_receipt(plan, status="REJECTED", reason=stale)
        _remember(world, receipt)
        return {"legacy": None, "receipt": receipt}
    kind = str(plan.get("operation_kind") or "")
    try:
        if kind == "COMBINE":
            return _commit_combine(world, plan)
        if kind == "APPLY_TO_SURFACE":
            return _commit_deposition(world, plan)
        if kind == "TRANSFER_SURFACE_COLUMN_SLICE":
            from mechanistic_mind.physical_system.conservative_surface_column_transfer import (
                commit_planned_transfer,
            )

            return commit_planned_transfer(world, plan)
        if kind == "SEPARATE_SURFACE_COLUMN_SLICE":
            from mechanistic_mind.physical_system.conservative_surface_material_separation import (
                commit_planned_separation,
            )

            return commit_planned_separation(world, plan)
        if kind == "SEPARATE_VOLUMETRIC_OCCUPANCY_INTERVAL":
            from mechanistic_mind.physical_system.volumetric_world_material_separation import (
                commit_planned_volumetric_separation,
            )

            return commit_planned_volumetric_separation(world, plan)
        if kind == "REINTEGRATE_VOLUMETRIC_OCCUPANCY_INTERVAL":
            from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
                commit_planned_volumetric_reintegration,
            )

            return commit_planned_volumetric_reintegration(world, plan)
    except Exception as exc:
        receipt = _base_receipt(plan, status="REJECTED", reason=type(exc).__name__)
        _remember(world, receipt)
        return {"legacy": None, "receipt": receipt}
    receipt = _base_receipt(plan, status="REJECTED", reason="unknown_operation")
    _remember(world, receipt)
    return {"legacy": None, "receipt": receipt}


def _commit_combine(world: Any, plan: dict[str, Any]) -> dict[str, Any]:
    from mechanistic_mind.physical_system.material_composition import merge_held_materials
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        apply_resize_on_commit,
        held_combine_radius_resize_transaction_is_active,
        validate_resize_commit_preconditions,
    )

    left = _find_object(world, plan["left_id"])
    right = _find_object(world, plan["right_id"])
    geo_plan = dict(plan.get("held_combine_geometry_resize") or {})
    actor_body = None
    body_id = str(plan.get("actor_body_id") or "")
    for row in list(getattr(world, "detached_placement_body_refs", None) or []):
        if isinstance(row, (tuple, list)) and len(row) >= 2 and str(row[0]) == body_id:
            actor_body = row[1]
            break
    if held_combine_radius_resize_transaction_is_active(plan.get("config")) and geo_plan:
        stale_reason = validate_resize_commit_preconditions(
            world=world,
            config=plan.get("config"),
            survivor=left,
            right=right,
            actor_body=actor_body,
            geometry_plan=geo_plan,
            body_id=body_id,
        )
        if stale_reason is not None:
            receipt = _base_receipt(plan, status="REJECTED", reason=str(stale_reason))
            receipt["held_combine_geometry_resize"] = {
                **geo_plan,
                "committed": False,
                "resize_classification": str(stale_reason),
                "rejection_reason": str(stale_reason),
                "work_debited": 0.0,
            }
            _remember(world, receipt)
            return {"legacy": None, "receipt": receipt}

    left_copy = left.copy()
    right_copy = right.copy()
    before_left = material_summary(left, kind="ResourceObject")
    before_right = material_summary(right, kind="ResourceObject")
    stage = _stage(world, [left_copy, right_copy])
    legacy = merge_held_materials(
        world=stage,
        config=plan["config"],
        body_id=plan["actor_body_id"],
        left=left_copy,
        right=right_copy,
        confirmed_contact=True,
        tick=int(plan["tick"]),
    )
    if legacy.get("outcome") != "MERGE_COMMITTED":
        receipt = _base_receipt(plan, status="REJECTED", reason=str(legacy.get("outcome") or "legacy_reject"))
        _remember(world, receipt)
        return {"legacy": legacy, "receipt": receipt}
    from mechanistic_mind.physical_system.passive_material_properties import derive_effective_properties

    properties = derive_effective_properties(left_copy.composition)
    left.mass = float(left_copy.mass)
    left.quantity = float(left_copy.quantity)
    left.composition = tuple(left_copy.composition)
    left.optical_response = tuple(left_copy.optical_response)
    left.material_revision = _revision(left) + 1
    left.provenance = _bound_provenance(
        getattr(left, "provenance", None),
        transaction_id=str(plan["transaction_id"]),
        source_ids=[str(left.object_id), str(right.object_id)],
        kind="COMBINE",
        tick=int(plan["tick"]),
    )
    # Geometry + work debit (exactly once) before source removal is observable.
    resize_receipt: dict[str, Any] | None = None
    if geo_plan and held_combine_radius_resize_transaction_is_active(plan.get("config")):
        resize_receipt = apply_resize_on_commit(
            world=world,
            config=plan.get("config"),
            survivor=left,
            actor_body=actor_body,
            geometry_plan=geo_plan,
        )
    world.resource_objects = [
        obj for obj in (getattr(world, "resource_objects", None) or []) if obj is not right
    ]
    _publish_generation(world, stage)
    mass_before = float(before_left["mass"]) + float(before_right["mass"])
    quantity_before = float(before_left["quantity"]) + float(before_right["quantity"])
    before_components: dict[str, float] = {}
    for row in before_left["composition"] + before_right["composition"]:
        before_components[row["component_id"]] = float(before_components.get(row["component_id"], 0.0)) + float(row["amount"])
    after_components = {row["component_id"]: float(row["amount"]) for row in _components(left)}
    receipt = _base_receipt(plan, status="COMMITTED")
    receipt.update({
        "touched_revisions": {str(left.object_id): _revision(left)},
        "removed_refs": [str(right.object_id)],
        "attachment_changes": [{"manipulator_id": "RIGHT", "freed": True, "object_id": str(right.object_id)}],
        "conservation": {
            "mass": _domain(mass_before, float(left.mass)),
            "quantity": _domain(quantity_before, float(left.quantity)),
            "components": _component_domain(before_components, after_components),
        },
        "optical_derivation": _optical_verification(plan["config"], before_left, before_right, left),
        "property_derivation": {
            "compliance": properties.get("compliance"),
            "surface_affinity": properties.get("surface_affinity"),
            "verified": bool(properties.get("property_derivation_verified", True)),
        },
        "before": [before_left, before_right],
        "after": [material_summary(left, kind="ResourceObject")],
    })
    if resize_receipt is not None:
        receipt["held_combine_geometry_resize"] = resize_receipt
        receipt["receipt_family"] = "HELD_COMBINE_GEOMETRY_RESIZE"
    _remember(world, receipt)
    _sync_spatial_index(world, plan)
    return {"legacy": legacy, "receipt": receipt}


def _sync_spatial_index(world: Any, plan: dict[str, Any]) -> None:
    from mechanistic_mind.physical_system.spatial_contents import (
        multi_content_spatial_index_is_active,
        reconcile_contents,
    )

    config = plan.get("config")
    if not multi_content_spatial_index_is_active(config):
        return
    reconcile_contents(
        world,
        tick=int(plan.get("tick") or 0),
        reason=str(plan.get("operation_kind") or "material_commit"),
        config=config,
        include_bodies=False,
    )


def _optical_verification(config: Any, before_a: dict[str, Any], before_b: dict[str, Any] | None, after: Any) -> dict[str, Any]:
    from mechanistic_mind.physical_system.physical_surface_optical_coating import (
        physical_surface_optical_coating_is_active,
        quantity_weighted_optical,
    )

    if not physical_surface_optical_coating_is_active(config):
        return {"verified": True, "active": False}
    parts = []
    for row in (before_a, before_b):
        if not row or row.get("optical_response") is None:
            continue
        optical = row["optical_response"]
        parts.append(((float(optical["c0"]), float(optical["c1"]), float(optical["c2"])), float(row.get("quantity") or 0.0)))
    expected = quantity_weighted_optical(parts) if parts else None
    actual = _optical(after)
    if expected is None or actual is None:
        return {"verified": expected is None and actual is None, "active": True}
    residual = max(abs(expected[index] - float(actual[key])) for index, key in enumerate(("c0", "c1", "c2")))
    return {
        "active": True,
        "expected": {"c0": expected[0], "c1": expected[1], "c2": expected[2]},
        "actual": actual,
        "residual_max_abs": float(residual),
        "verified": bool(residual <= 1e-9),
        "conserved_quantity": False,
    }


def _commit_deposition(world: Any, plan: dict[str, Any]) -> dict[str, Any]:
    from mechanistic_mind.physical_system.explicit_surface_deposition import (
        apply_explicit_surface_deposition,
        ensure_surface_deposits,
    )
    from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import (
        apply_shrink_on_commit,
        held_deposition_radius_shrink_transaction_is_active,
        validate_shrink_commit_preconditions,
    )
    from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT, held_object_for_holder

    source = held_object_for_holder(world, plan["actor_body_id"], MANIP_LEFT)
    deposits = ensure_surface_deposits(world)
    existing = deposits.get(plan["deposit_id"])
    geo_plan = dict(plan.get("held_deposition_geometry_shrink") or {})
    if held_deposition_radius_shrink_transaction_is_active(plan.get("config")) and geo_plan:
        stale_reason = validate_shrink_commit_preconditions(
            source=source,
            geometry_plan=geo_plan,
        )
        if stale_reason is not None:
            receipt = _base_receipt(plan, status="REJECTED", reason=str(stale_reason))
            receipt["held_deposition_geometry_shrink"] = {
                **geo_plan,
                "committed": False,
                "resize_classification": str(stale_reason),
                "rejection_reason": str(stale_reason),
            }
            _remember(world, receipt)
            return {"legacy": None, "receipt": receipt}

    source_copy = source.copy()
    existing_copy = existing.copy() if existing is not None else None
    before_source = material_summary(source, kind="ResourceObject")
    before_deposit = material_summary(existing, kind="SurfaceMaterialDeposit")
    stage_deposits = {}
    if existing_copy is not None:
        stage_deposits[plan["deposit_id"]] = existing_copy
    stage = _stage(world, [source_copy], stage_deposits)
    legacy = apply_explicit_surface_deposition(
        world=stage,
        config=plan["config"],
        body=plan["body"],
        body_id=plan["actor_body_id"],
        command_requested=True,
        held_object_id_at_tick_start=plan.get("held_object_id_at_tick_start"),
        tick=int(plan["tick"]),
        runtime=plan.get("runtime"),
    )
    if not isinstance(legacy, dict) or not legacy.get("committed"):
        receipt = _base_receipt(plan, status="REJECTED", reason=str((legacy or {}).get("outcome") or "legacy_reject"))
        _remember(world, receipt)
        return {"legacy": legacy, "receipt": receipt}
    updated = stage.surface_material_deposits.get(plan["deposit_id"])
    if updated is None:
        receipt = _base_receipt(plan, status="REJECTED", reason="missing_candidate")
        _remember(world, receipt)
        return {"legacy": legacy, "receipt": receipt}
    from mechanistic_mind.physical_system.passive_material_properties import derive_effective_properties

    properties = derive_effective_properties(updated.composition)
    removed = source_copy not in stage.resource_objects or bool(legacy.get("source_removed"))
    shrink_receipt: dict[str, Any] | None = None
    if removed:
        source.holder_body_id = None
        source.manipulator_id = None
        world.resource_objects = [
            obj for obj in (getattr(world, "resource_objects", None) or []) if obj is not source
        ]
        if geo_plan and held_deposition_radius_shrink_transaction_is_active(plan.get("config")):
            shrink_receipt = apply_shrink_on_commit(
                world=world,
                config=plan.get("config"),
                source=source,
                geometry_plan={**geo_plan, "depleted": True},
            )
    else:
        source.mass = float(source_copy.mass)
        source.quantity = float(source_copy.quantity)
        source.composition = tuple(source_copy.composition)
        source.optical_response = tuple(source_copy.optical_response)
        source.material_revision = _revision(source) + 1
        source.provenance = _bound_provenance(
            getattr(source, "provenance", None),
            transaction_id=str(plan["transaction_id"]),
            source_ids=[str(source.object_id)],
            kind="APPLY_TO_SURFACE",
            tick=int(plan["tick"]),
        )
        if geo_plan and held_deposition_radius_shrink_transaction_is_active(plan.get("config")):
            shrink_receipt = apply_shrink_on_commit(
                world=world,
                config=plan.get("config"),
                source=source,
                geometry_plan=geo_plan,
            )
    updated.material_revision = (0 if existing is None else _revision(existing)) + 1
    updated.provenance = _bound_provenance(
        getattr(existing, "provenance", None) if existing is not None else {},
        transaction_id=str(plan["transaction_id"]),
        source_ids=[str(plan["source_id"])],
        kind="APPLY_TO_SURFACE",
        tick=int(plan["tick"]),
    )
    deposits[plan["deposit_id"]] = updated
    _publish_generation(world, stage)
    mass_before = float(before_source["mass"]) + float(before_deposit.get("mass") or 0.0)
    quantity_before = float(before_source["quantity"]) + float(before_deposit.get("quantity") or 0.0)
    mass_after = float(updated.mass) + (0.0 if removed else float(source.mass))
    quantity_after = float(updated.quantity) + (0.0 if removed else float(source.quantity))
    before_components: dict[str, float] = {}
    for row in list(before_source.get("composition") or []) + list(before_deposit.get("composition") or []):
        before_components[row["component_id"]] = float(before_components.get(row["component_id"], 0.0)) + float(row["amount"])
    after_components = _totals(updated)
    if not removed:
        for key, value in _totals(source).items():
            after_components[key] = float(after_components.get(key, 0.0)) + float(value)
    source_after = None if removed else material_summary(source, kind="ResourceObject")
    deposit_after = material_summary(updated, kind="SurfaceMaterialDeposit")
    receipt = _base_receipt(plan, status="COMMITTED")
    receipt.update({
        "touched_revisions": {
            str(plan["source_id"]): None if removed else _revision(source),
            str(plan["deposit_id"]): _revision(updated),
        },
        "removed_refs": [str(plan["source_id"])] if removed else [],
        "attachment_changes": (
            [{"manipulator_id": "LEFT", "freed": True, "object_id": str(plan["source_id"])}] if removed else []
        ),
        "conservation": {
            "mass": _domain(mass_before, mass_after),
            "quantity": _domain(quantity_before, quantity_after),
            "components": _component_domain(before_components, after_components),
        },
        "optical_derivation": _deposition_optical_verification(plan["config"], before_source, before_deposit, updated),
        "property_derivation": {
            "compliance": properties.get("compliance"),
            "surface_affinity": properties.get("surface_affinity"),
            "verified": bool(properties.get("property_derivation_verified", True)),
        },
        "before": [before_source, before_deposit],
        "after": [row for row in (source_after, deposit_after) if row is not None],
    })
    if shrink_receipt is not None:
        receipt["held_deposition_geometry_shrink"] = shrink_receipt
        receipt["receipt_family"] = "HELD_DEPOSITION_GEOMETRY_SHRINK"
    _remember(world, receipt)
    _sync_spatial_index(world, plan)
    return {"legacy": legacy, "receipt": receipt}


def _deposition_optical_verification(config: Any, source: dict[str, Any], deposit: dict[str, Any], updated: Any) -> dict[str, Any]:
    from mechanistic_mind.physical_system.physical_surface_optical_coating import (
        physical_surface_optical_coating_is_active,
        quantity_weighted_optical,
    )

    if not physical_surface_optical_coating_is_active(config):
        return {"verified": True, "active": False}
    actual = _optical(updated)
    source_optical = source.get("optical_response")
    if source_optical is None:
        return {"verified": actual is None, "active": True, "conserved_quantity": False}
    prior = deposit.get("optical_response") if deposit.get("entity_id") else None
    if prior is None:
        expected = (float(source_optical["c0"]), float(source_optical["c1"]), float(source_optical["c2"]))
    else:
        mixed = quantity_weighted_optical([
            ((float(prior["c0"]), float(prior["c1"]), float(prior["c2"])), float(deposit.get("quantity") or 0.0)),
            ((float(source_optical["c0"]), float(source_optical["c1"]), float(source_optical["c2"])), float(updated.quantity) - float(deposit.get("quantity") or 0.0)),
        ])
        expected = mixed if mixed is not None else (float(source_optical["c0"]), float(source_optical["c1"]), float(source_optical["c2"]))
    if actual is None:
        return {"verified": False, "active": True, "conserved_quantity": False}
    residual = max(abs(expected[index] - float(actual[key])) for index, key in enumerate(("c0", "c1", "c2")))
    return {
        "active": True,
        "residual_max_abs": float(residual),
        "verified": bool(residual <= 1e-9),
        "conserved_quantity": False,
    }


def world_material_transaction_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "world_material_transactions.enabled",
        "label": "WORLD MATERIAL TRANSACTIONS",
        "description": (
            "COMBINE and APPLY_TO_SURFACE commit as one conservative transaction. "
            "researcher-only. not agent-accessible. not a recipe."
        ),
        "validation": "Acanthostega Phase B World Material Transactions.",
        "provenance": "acanthostega_world_material_transactions",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "PHYSICAL",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
    }
