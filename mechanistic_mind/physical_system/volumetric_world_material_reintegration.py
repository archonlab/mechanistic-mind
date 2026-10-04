"""Acanthostega VW4 · Conservative volumetric deposition / reintegration.

Mechanism: volumetric_world_material_reintegration
Schema: VW4_CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1
Authority: AUTHORITATIVE_VOLUMETRIC_MATERIAL_REINTEGRATION_VIA_WMT

Inverse of VW3: detached ResourceObject material → WMT → VW1 occupancy.
Does not invent BUILD/PLACE/FILL. Does not own gravity/PE/landing.
Does not implement VW5 effector/held bridge.

Interval insertion uses VW1 ``(z_min, z_max]`` semantics.
Overlap with occupied matter is rejected atomically (no overwrite).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
    OccupiedZInterval,
    TOLERANCE,
    canonicalize_intervals,
    compatibility_surface_elevation,
    ensure_state as ensure_vw1_state,
    occupied_intervals_at,
    set_volumetric_column,
    state_of as vo_state,
    wrap_cell,
)

SCHEMA = "VW4_CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1"
CAPABILITY = "conservative_volumetric_material_reintegration"
PROFILE = "VOLUMETRIC_OCCUPANCY_INTERVAL_REINTEGRATION_V1"
AUTHORITY = "AUTHORITATIVE_VOLUMETRIC_MATERIAL_REINTEGRATION_VIA_WMT"
MECHANISM_ID = "volumetric_world_material_reintegration"
OPERATION_KIND = "REINTEGRATE_VOLUMETRIC_OCCUPANCY_INTERVAL"
WORLD_ATTR = "volumetric_material_reintegration_state"
HISTORY_LIMIT = 16
CELL_AREA = 1.0
CONSERVATION_TOLERANCE = 1e-9

R_INACTIVE = "VW4_INACTIVE"
R_VW1_OFF = "VW1_OCCUPANCY_INACTIVE"
R_WMT_OFF = "WMT_OFF"
R_BOUNDS = "INVALID_Z_BOUNDS"
R_OVERLAP = "DESTINATION_OCCUPIED_OVERLAP"
R_SOURCE = "SOURCE_OBJECT_MISSING"
R_SOURCE_STATE = "SOURCE_OBJECT_UNAVAILABLE"
R_QTY = "QUANTITY_DESTINATION_MISMATCH"
R_MASS = "NON_FINITE_MASS_OR_QUANTITY"
R_EMPTY = "ZERO_DEPOSITION"
R_PARTIAL = "PARTIAL_SOURCE_CONSUMPTION_NOT_IMPLEMENTED"
R_CONSERVATION = "CONSERVATION_FAILED"
R_DUPLICATE = "DUPLICATE_REINTEGRATION"
R_HELD = "SOURCE_HELD_NOT_SUPPORTED_IN_VW4"

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "operation_kind": OPERATION_KIND,
    "occupancy_owner": "volumetric_world_material_occupancy",
    "wmt_authority": "world_material_transactions",
    "source_kind": "ResourceObject",
    "semantic_build": False,
    "agent_accessible": False,
    "researcher_only": True,
    "partial_consumption": "NOT_IMPLEMENTED",
    "vw5_effector_bridge": False,
}


class VolumetricReintegrationValidationError(ValueError):
    """Raised when VW4 config or insertion geometry is invalid."""


@dataclass
class VolumetricWorldMaterialReintegrationConfig:
    enabled: bool = False
    profile: str = PROFILE
    schema: str = SCHEMA
    cell_area: float = CELL_AREA

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "profile": str(self.profile),
            "schema": str(self.schema),
            "cell_area": float(self.cell_area),
            **AUTHORITY_FLAGS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "VolumetricWorldMaterialReintegrationConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        profile = str(data.get("profile") or PROFILE)
        schema = str(data.get("schema") or SCHEMA)
        if profile != PROFILE:
            raise VolumetricReintegrationValidationError(f"unsupported VW4 profile: {profile!r}")
        if schema != SCHEMA:
            raise VolumetricReintegrationValidationError(f"unsupported VW4 schema: {schema!r}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            profile=profile,
            schema=schema,
            cell_area=float(data.get("cell_area", CELL_AREA)),
        )


def volumetric_world_material_reintegration_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "volumetric_world_material_reintegration", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        volumetric_world_material_occupancy_is_active,
    )
    from mechanistic_mind.physical_system.world_material_transaction import (
        world_material_transactions_is_active,
    )

    return bool(
        volumetric_world_material_occupancy_is_active(config)
        and world_material_transactions_is_active(config)
    )


def set_volumetric_world_material_reintegration(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "volumetric_world_material_reintegration", None)
    if cur is None:
        config.volumetric_world_material_reintegration = VolumetricWorldMaterialReintegrationConfig(enabled=on)
    else:
        cur.enabled = on
    if on:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            set_volumetric_world_material_occupancy,
        )
        from mechanistic_mind.physical_system.world_material_transaction import (
            set_world_material_transactions,
        )

        set_volumetric_world_material_occupancy(config, True)
        set_world_material_transactions(config, True)


@dataclass
class VolumetricMaterialReintegrationState:
    config: VolumetricWorldMaterialReintegrationConfig
    last_receipt: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    committed_ids: set[str] = field(default_factory=set)
    counters: dict[str, int] = field(default_factory=dict)


def state_of(world: Any) -> VolumetricMaterialReintegrationState | None:
    raw = getattr(world, WORLD_ATTR, None)
    return raw if isinstance(raw, VolumetricMaterialReintegrationState) else None


def ensure_state(world: Any, config: Any) -> VolumetricMaterialReintegrationState | None:
    if not volumetric_world_material_reintegration_is_active(config):
        if getattr(world, WORLD_ATTR, None) is not None:
            setattr(world, WORLD_ATTR, None)
        return None
    ensure_vw1_state(world, config)
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "volumetric_world_material_reintegration", None)
    cfg = (
        raw
        if isinstance(raw, VolumetricWorldMaterialReintegrationConfig)
        else VolumetricWorldMaterialReintegrationConfig.from_dict(raw if isinstance(raw, dict) else None)
    )
    cfg.enabled = True
    st = VolumetricMaterialReintegrationState(config=cfg)
    setattr(world, WORLD_ATTR, st)
    return st


# ---------------------------------------------------------------------------
# Pure interval insertion (VW1 endpoint semantics)
# ---------------------------------------------------------------------------


def destination_overlaps_occupied(
    intervals: tuple[OccupiedZInterval, ...] | list[OccupiedZInterval],
    z_lo: float,
    z_hi: float,
) -> bool:
    """True iff (z_lo, z_hi] intersects any occupied (z_min, z_max]."""
    lo = float(z_lo)
    hi = float(z_hi)
    for it in intervals:
        inter_lo = max(float(it.z_min), lo)
        inter_hi = min(float(it.z_max), hi)
        if inter_hi > inter_lo + TOLERANCE:
            return True
    return False


def insert_z_range_into_intervals(
    intervals: tuple[OccupiedZInterval, ...] | list[OccupiedZInterval],
    z_lo: float,
    z_hi: float,
    *,
    density: float,
    composition: tuple[tuple[str, float], ...],
    material_property_derivation_version: str = "v1",
    source_layer_index: int = -1,
    merge_compatible_abutting: bool = True,
) -> tuple[OccupiedZInterval, ...]:
    """Insert occupied matter into free (z_lo, z_hi]. Rejects overlap.

    Returns canonical intervals. Follows VW1 merge rules when
    ``merge_compatible_abutting`` is True (exact density + composition equality).
    """
    lo = float(z_lo)
    hi = float(z_hi)
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise VolumetricReintegrationValidationError(R_BOUNDS)
    if hi <= lo + TOLERANCE:
        raise VolumetricReintegrationValidationError(R_BOUNDS)
    if destination_overlaps_occupied(intervals, lo, hi):
        raise VolumetricReintegrationValidationError(R_OVERLAP)
    dens = float(density)
    if not (math.isfinite(dens) and dens > 0.0):
        raise VolumetricReintegrationValidationError(R_MASS)
    inserted = OccupiedZInterval(
        z_min=lo,
        z_max=hi,
        density=dens,
        composition=tuple(composition),
        material_property_derivation_version=str(material_property_derivation_version),
        source_layer_index=int(source_layer_index),
    )
    combined = list(intervals) + [inserted]
    return canonicalize_intervals(combined, merge_compatible_abutting=merge_compatible_abutting)


def _objects_list(world: Any) -> list[Any]:
    return list(getattr(world, "resource_objects", None) or [])


def _find_object(world: Any, object_id: str) -> Any | None:
    oid = str(object_id)
    for obj in _objects_list(world):
        if str(getattr(obj, "object_id", "")) == oid:
            return obj
    return None


def _object_composition_absolute(obj: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in getattr(obj, "composition", ()) or ():
        if hasattr(row, "component_id"):
            out.append({"component_id": str(row.component_id), "amount": float(row.amount)})
        elif isinstance(row, dict):
            out.append(
                {
                    "component_id": str(row.get("component_id") or row.get("id") or ""),
                    "amount": float(row.get("amount", 0.0)),
                }
            )
    return out


def _per_area_composition(
    absolute: list[dict[str, Any]], *, area: float
) -> tuple[tuple[str, float], ...]:
    if area <= TOLERANCE:
        raise VolumetricReintegrationValidationError(R_BOUNDS)
    out: list[tuple[str, float]] = []
    for row in absolute:
        cid = str(row["component_id"])
        amt = float(row["amount"]) / float(area)
        if cid and amt > TOLERANCE:
            out.append((cid, float(amt)))
    return tuple(sorted(out, key=lambda t: t[0]))


# ---------------------------------------------------------------------------
# Plan / commit
# ---------------------------------------------------------------------------


def plan_volumetric_material_reintegration(
    world: Any,
    config: Any,
    *,
    object_id: str,
    cell_x: int,
    cell_y: int,
    z_deposit_lo: float,
    z_deposit_hi: float,
    tick: int = 0,
    researcher_id: str = "researcher",
) -> dict[str, Any]:
    """Plan full-object reintegration into free occupancy. No mutation. Researcher/test-only."""
    from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_HELD
    from mechanistic_mind.physical_system.world_material_transaction import (
        allocate_transaction_id,
        world_material_transactions_is_active,
    )

    plan: dict[str, Any] = {
        "schema": SCHEMA,
        "operation_kind": OPERATION_KIND,
        "command": OPERATION_KIND,
        "capability": CAPABILITY,
        "authority": AUTHORITY,
        "researcher_only": True,
        "agent_accessible": False,
        "tick": int(tick),
        "researcher_id": str(researcher_id),
        "config": config,
        "status": "PLANNED",
        "object_id": str(object_id),
    }
    if not volumetric_world_material_reintegration_is_active(config):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_INACTIVE
        return plan
    if not world_material_transactions_is_active(config):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_WMT_OFF
        return plan
    ensure_vw1_state(world, config)
    st_vo = vo_state(world)
    if st_vo is None:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_VW1_OFF
        return plan

    try:
        lo = float(z_deposit_lo)
        hi = float(z_deposit_hi)
        if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo + TOLERANCE:
            plan["status"] = "REJECTED"
            plan["rejection_reason"] = R_BOUNDS
            return plan
    except (TypeError, ValueError):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_BOUNDS
        return plan

    obj = _find_object(world, object_id)
    if obj is None:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_SOURCE
        return plan
    ps = str(getattr(obj, "physical_state", "") or "")
    if ps == PHYSICAL_STATE_HELD:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_HELD
        return plan
    if "COMBINE" in ps or ps.endswith("_REMOVED"):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_SOURCE_STATE
        return plan

    try:
        qty = float(obj.quantity)
        mass = float(obj.mass)
        if not math.isfinite(qty) or not math.isfinite(mass) or qty < 0.0 or mass < 0.0:
            plan["status"] = "REJECTED"
            plan["rejection_reason"] = R_MASS
            return plan
    except (TypeError, ValueError):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_MASS
        return plan
    if qty <= TOLERANCE:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_EMPTY
        return plan

    area = float(
        getattr(getattr(config, "volumetric_world_material_reintegration", None), "cell_area", CELL_AREA)
        or CELL_AREA
    )
    thickness = hi - lo
    required_qty = thickness * area
    # Full-object reintegration only: quantity must match destination volume.
    if abs(qty - required_qty) > CONSERVATION_TOLERANCE:
        # Distinguish partial (qty < required) vs mismatch; partial not implemented.
        if qty + CONSERVATION_TOLERANCE < required_qty:
            plan["status"] = "REJECTED"
            plan["rejection_reason"] = R_PARTIAL
            return plan
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_QTY
        return plan

    density = mass / qty if qty > TOLERANCE else 0.0
    if not (math.isfinite(density) and density > 0.0):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_MASS
        return plan

    abs_comp = _object_composition_absolute(obj)
    per_area = _per_area_composition(abs_comp, area=area)
    deriv = str(getattr(obj, "material_property_derivation_version", None) or "v1")
    # Prefer provenance derivation if present on object provenance
    prov = getattr(obj, "provenance", None) or {}
    if isinstance(prov, dict) and prov.get("material_property_derivation_version"):
        deriv = str(prov["material_property_derivation_version"])

    cell = wrap_cell(st_vo, cell_x, cell_y)
    before = occupied_intervals_at(world, cell[0], cell[1])
    plan["cell"] = [int(cell[0]), int(cell[1])]
    plan["before"] = {
        "occupied_intervals": [it.as_dict() for it in before],
        "derived_surface_elevation": compatibility_surface_elevation(world, cell[0], cell[1]),
        "occupancy_digest": st_vo.digest(),
    }
    plan["deposition"] = {
        "z_lo": lo,
        "z_hi": hi,
        "endpoint_semantics": "HALF_OPEN_LOWER_EXCLUSIVE_UPPER_INCLUSIVE",
        "thickness": float(thickness),
    }
    plan["source_before"] = {
        "object_id": str(obj.object_id),
        "quantity": float(qty),
        "mass": float(mass),
        "composition": abs_comp,
        "physical_state": ps,
        "revision": int(getattr(obj, "material_revision", 0) or 0),
        "provenance": dict(prov) if isinstance(prov, dict) else {},
    }

    try:
        after_intervals = insert_z_range_into_intervals(
            before,
            lo,
            hi,
            density=density,
            composition=per_area,
            material_property_derivation_version=deriv,
            merge_compatible_abutting=True,
        )
    except VolumetricReintegrationValidationError as exc:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = str(exc) if str(exc) else R_OVERLAP
        return plan
    except Exception as exc:
        # VW1 overlap / validation
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = str(exc) if "overlap" in str(exc).lower() else R_OVERLAP
        return plan

    tid = allocate_transaction_id(world, tick)
    rid = f"vw4-reint-{tid}"
    after_surface = max((float(it.z_max) for it in after_intervals), default=None)
    plan["transaction_id"] = tid
    plan["reintegration_id"] = rid
    plan["after"] = {
        "occupied_intervals": [it.as_dict() for it in after_intervals],
        "derived_surface_elevation": after_surface,
        "inserted": {"z_lo": lo, "z_hi": hi, "density": float(density), "composition_per_area": [
            {"component_id": cid, "quantity_per_area": float(amt)} for cid, amt in per_area
        ]},
    }
    plan["candidates"] = {
        "after_intervals": after_intervals,
        "consume_object_id": str(obj.object_id),
        "inserted_interval": OccupiedZInterval(
            z_min=lo,
            z_max=hi,
            density=density,
            composition=per_area,
            material_property_derivation_version=deriv,
        ),
    }
    plan["conservation"] = {
        "cell_area": float(area),
        "source_quantity_before": float(qty),
        "source_mass_before": float(mass),
        "world_quantity_added": float(required_qty),
        "world_mass_added": float(density * thickness * area),
        "source_quantity_after": 0.0,
        "source_mass_after": 0.0,
        "full_consumption": True,
        "verified": abs(qty - required_qty) <= CONSERVATION_TOLERANCE
        and abs(mass - density * thickness * area) <= CONSERVATION_TOLERANCE,
        "tolerance": CONSERVATION_TOLERANCE,
    }
    plan["expected_occupancy_digest"] = plan["before"]["occupancy_digest"]
    plan["expected_revisions"] = {str(obj.object_id): int(getattr(obj, "material_revision", 0) or 0)}
    plan["input_refs"] = [str(obj.object_id), f"occupancy:x{cell[0]}-y{cell[1]}"]
    plan["output_refs"] = [f"occupancy:x{cell[0]}-y{cell[1]}", rid]
    return plan


def commit_planned_volumetric_reintegration(world: Any, plan: dict[str, Any]) -> dict[str, Any]:
    """Atomic commit: occupancy insertion + full ResourceObject consumption. Called from WMT."""
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    st = state_of(world)
    if st is None:
        cfg = plan.get("config")
        st = ensure_state(world, cfg) if cfg is not None else None
    if st is None:
        return _reject(world, plan, R_INACTIVE)

    rid = str(plan.get("reintegration_id") or "")
    if rid and rid in st.committed_ids:
        return _reject(world, plan, R_DUPLICATE)

    st_vo = vo_state(world)
    if st_vo is None:
        return _reject(world, plan, R_VW1_OFF)
    if str(plan.get("expected_occupancy_digest") or "") and st_vo.digest() != str(plan["expected_occupancy_digest"]):
        return _reject(world, plan, "OCCUPANCY_STATE_CHANGED")

    oid = str(plan["candidates"]["consume_object_id"])
    obj = _find_object(world, oid)
    if obj is None:
        return _reject(world, plan, R_SOURCE)
    expected_rev = (plan.get("expected_revisions") or {}).get(oid)
    if expected_rev is not None and int(getattr(obj, "material_revision", 0) or 0) != int(expected_rev):
        return _reject(world, plan, "SOURCE_REVISION_STALE")

    cons = plan.get("conservation") or {}
    if not cons.get("verified"):
        return _reject(world, plan, R_CONSERVATION)
    if abs(float(obj.quantity) - float(cons.get("source_quantity_before", -1))) > CONSERVATION_TOLERANCE:
        return _reject(world, plan, R_CONSERVATION)
    if abs(float(obj.mass) - float(cons.get("source_mass_before", -1))) > CONSERVATION_TOLERANCE:
        return _reject(world, plan, R_CONSERVATION)

    cell = plan.get("cell") or [0, 0]
    cx, cy = int(cell[0]), int(cell[1])
    after_intervals: tuple[OccupiedZInterval, ...] = plan["candidates"]["after_intervals"]
    dep = plan.get("deposition") or {}
    src_before = plan.get("source_before") or {}
    src_prov = dict(src_before.get("provenance") or {})

    provenance = {
        "source": "VOLUMETRIC_MATERIAL_REINTEGRATION",
        "researcher_only": True,
        "not_agent_accessible_origin": True,
        "transaction_id": str(plan.get("transaction_id")),
        "reintegration_id": rid,
        "operation_kind": OPERATION_KIND,
        "schema": SCHEMA,
        "destination_cell": [cx, cy],
        "destination_z_lo": float(dep.get("z_lo", 0.0)),
        "destination_z_hi": float(dep.get("z_hi", 0.0)),
        "consumed_object_id": oid,
        "source_quantity_consumed": float(cons.get("source_quantity_before", 0.0)),
        "source_mass_consumed": float(cons.get("source_mass_before", 0.0)),
        "before_intervals": list((plan.get("before") or {}).get("occupied_intervals") or []),
        "after_intervals": list((plan.get("after") or {}).get("occupied_intervals") or []),
        "inserted": (plan.get("after") or {}).get("inserted"),
        "prior_object_provenance": src_prov,
        "separation_transaction_id": src_prov.get("transaction_id"),
        "separation_id": src_prov.get("separation_id"),
        "tick": int(plan.get("tick") or 0),
    }

    receipt = {
        "status": "COMMITTED",
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "operation_kind": OPERATION_KIND,
        "transaction_id": str(plan.get("transaction_id")),
        "reintegration_id": rid,
        "object_id": oid,
        "source_consumed": True,
        "source_quantity_consumed": float(cons.get("source_quantity_before", 0.0)),
        "source_remaining_quantity": 0.0,
        "cell": [cx, cy],
        "deposition": dict(dep),
        "before": plan.get("before"),
        "after": plan.get("after"),
        "conservation": plan.get("conservation"),
        "provenance": provenance,
        "researcher_only": True,
        "agent_accessible": False,
        "tick": int(plan.get("tick") or 0),
    }

    # ---- atomic publish: occupancy then consume object ----
    set_volumetric_column(
        world,
        cx,
        cy,
        after_intervals,
        tick=int(plan.get("tick") or 0),
        reason="VW4_VOLUMETRIC_MATERIAL_REINTEGRATION",
    )
    world.resource_objects = [o for o in _objects_list(world) if str(getattr(o, "object_id", "")) != oid]
    try:
        wmt._sync_spatial_index(world, plan)
    except Exception:
        pass

    st.committed_ids.add(rid)
    st.last_receipt = receipt
    st.history.append(receipt)
    if len(st.history) > HISTORY_LIMIT:
        del st.history[: len(st.history) - HISTORY_LIMIT]
    st.counters["committed"] = int(st.counters.get("committed", 0)) + 1
    wmt._remember(world, receipt)
    return {"legacy": None, "receipt": receipt}


def _reject(world: Any, plan: dict[str, Any], code: str) -> dict[str, Any]:
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    receipt = {
        "status": "REJECTED",
        "rejection_reason": str(code),
        "schema": SCHEMA,
        "operation_kind": OPERATION_KIND,
        "transaction_id": plan.get("transaction_id"),
        "reintegration_id": plan.get("reintegration_id"),
        "object_id": plan.get("object_id"),
        "researcher_only": True,
        "tick": int(plan.get("tick") or 0),
    }
    wmt._remember(world, receipt)
    st = state_of(world)
    if st is not None:
        st.last_receipt = receipt
        st.counters["rejected"] = int(st.counters.get("rejected", 0)) + 1
    return {"legacy": None, "receipt": receipt}


def apply_volumetric_material_reintegration(
    world: Any,
    config: Any,
    *,
    object_id: str,
    cell_x: int,
    cell_y: int,
    z_deposit_lo: float,
    z_deposit_hi: float,
    tick: int = 0,
    researcher_id: str = "researcher",
) -> dict[str, Any]:
    """Researcher/test-only: plan + WMT commit. Not an organism action."""
    from mechanistic_mind.physical_system.world_material_transaction import commit_material_transaction

    ensure_state(world, config)
    plan = plan_volumetric_material_reintegration(
        world,
        config,
        object_id=object_id,
        cell_x=cell_x,
        cell_y=cell_y,
        z_deposit_lo=z_deposit_lo,
        z_deposit_hi=z_deposit_hi,
        tick=tick,
        researcher_id=researcher_id,
    )
    if plan.get("status") == "REJECTED":
        return _reject(world, plan, str(plan.get("rejection_reason") or "precondition"))
    return commit_material_transaction(world, plan)


def researcher_payload(world: Any) -> dict[str, Any]:
    st = state_of(world)
    if st is None:
        return {}
    return {
        "volumetric_material_reintegration": {
            "schema": SCHEMA,
            "capability": CAPABILITY,
            "authority": AUTHORITY,
            "mechanism_id": MECHANISM_ID,
            "last_receipt": dict(st.last_receipt) if st.last_receipt else None,
            "receipts": list(st.history)[-HISTORY_LIMIT:],
            "counters": dict(st.counters),
            **AUTHORITY_FLAGS,
        }
    }


def observer_reintegration_inspector_payload(world: Any, config: Any | None = None) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None or not st.last_receipt:
        return None
    rec = dict(st.last_receipt)
    return {
        "mechanism": MECHANISM_ID,
        "schema": SCHEMA,
        "authority_label": "AUTHORITATIVE VW4 VOLUMETRIC REINTEGRATION VIA WMT",
        "legacy_label": "LEGACY / DERIVED SURFACE PROJECTION (not deposition destination truth)",
        "receipt": rec,
        "researcher_only_view": True,
        "not_agent_accessible": True,
        "source_kind": "VW4_REINTEGRATION_INSPECTION",
    }


def volumetric_material_reintegration_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "volumetric_world_material_reintegration.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "schema": SCHEMA,
        "profile": PROFILE,
        "description": (
            "Conservative reintegration mutates VW1 volumetric occupancy via WMT from a "
            "ResourceObject source. Full consumption. No BUILD verb. No VW5 effector bridge."
        ),
    }
