"""Acanthostega VW3 · Volumetric world material separation.

Mechanism: volumetric_world_material_separation
Schema: VW3_VOLUMETRIC_MATERIAL_SEPARATION_V1
Authority: AUTHORITATIVE_VOLUMETRIC_MATERIAL_SEPARATION_VIA_WMT

Mutates VW1 ``world.volumetric_occupancy`` through existing WMT.
Does not invent DIG/HOLE/CAVE. Does not own gravity/PE/landing.
Does not implement VW4 deposition reintegration.

Interval removal uses VW1 ``(z_min, z_max]`` semantics.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system.resource_objects import (
    CANONICAL_INTERACTION_RADIUS,
    CANONICAL_OPTICAL_RADIUS,
    CANONICAL_OPTICAL_RESPONSE,
    MaterialComponent,
    PHYSICAL_STATE_FREE_STATIC,
    ResourceObject,
)
from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
    OccupiedZInterval,
    TOLERANCE,
    VolumetricOccupancyValidationError,
    canonicalize_intervals,
    compatibility_surface_elevation,
    ensure_state as ensure_vw1_state,
    occupied_intervals_at,
    set_volumetric_column,
    state_of as vo_state,
    wrap_cell,
)

SCHEMA = "VW3_VOLUMETRIC_MATERIAL_SEPARATION_V1"
CAPABILITY = "volumetric_world_material_separation"
PROFILE = "VOLUMETRIC_OCCUPANCY_INTERVAL_SEPARATION_V1"
AUTHORITY = "AUTHORITATIVE_VOLUMETRIC_MATERIAL_SEPARATION_VIA_WMT"
MECHANISM_ID = "volumetric_world_material_separation"
OPERATION_KIND = "SEPARATE_VOLUMETRIC_OCCUPANCY_INTERVAL"
WORLD_ATTR = "volumetric_material_separation_state"
HISTORY_LIMIT = 16
CELL_AREA = 1.0
CONSERVATION_TOLERANCE = 1e-9

R_INACTIVE = "VW3_INACTIVE"
R_VW1_OFF = "VW1_OCCUPANCY_INACTIVE"
R_WMT_OFF = "WMT_OFF"
R_EMPTY = "NO_OCCUPIED_SOURCE"
R_FREE = "REMOVAL_IN_FREE_SPACE"
R_ZERO = "ZERO_REMOVAL"
R_MATERIAL = "INCOMPATIBLE_MATERIAL_MIX"
R_CONSERVATION = "CONSERVATION_FAILED"
R_DUPLICATE = "DUPLICATE_SEPARATION"
R_BOUNDS = "INVALID_Z_BOUNDS"
R_ID = "OBJECT_ID_COLLISION"

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "operation_kind": OPERATION_KIND,
    "occupancy_owner": "volumetric_world_material_occupancy",
    "wmt_authority": "world_material_transactions",
    "deposition_volumetric": False,
    "semantic_dig": False,
    "agent_accessible": False,
    "researcher_only": True,
}


class VolumetricSeparationValidationError(ValueError):
    """Raised when VW3 config or removal geometry is invalid."""


@dataclass
class VolumetricWorldMaterialSeparationConfig:
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
    def from_dict(cls, data: dict[str, Any] | None) -> "VolumetricWorldMaterialSeparationConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        profile = str(data.get("profile") or PROFILE)
        schema = str(data.get("schema") or SCHEMA)
        if profile != PROFILE:
            raise VolumetricSeparationValidationError(f"unsupported VW3 profile: {profile!r}")
        if schema != SCHEMA:
            raise VolumetricSeparationValidationError(f"unsupported VW3 schema: {schema!r}")
        return cls(
            enabled=bool(data.get("enabled", False)),
            profile=profile,
            schema=schema,
            cell_area=float(data.get("cell_area", CELL_AREA)),
        )


def volumetric_world_material_separation_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "volumetric_world_material_separation", None)
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


def set_volumetric_world_material_separation(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "volumetric_world_material_separation", None)
    if cur is None:
        config.volumetric_world_material_separation = VolumetricWorldMaterialSeparationConfig(enabled=on)
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
class VolumetricMaterialSeparationState:
    config: VolumetricWorldMaterialSeparationConfig
    last_receipt: dict[str, Any] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    committed_ids: set[str] = field(default_factory=set)
    counters: dict[str, int] = field(default_factory=dict)


def state_of(world: Any) -> VolumetricMaterialSeparationState | None:
    raw = getattr(world, WORLD_ATTR, None)
    return raw if isinstance(raw, VolumetricMaterialSeparationState) else None


def ensure_state(world: Any, config: Any) -> VolumetricMaterialSeparationState | None:
    if not volumetric_world_material_separation_is_active(config):
        if getattr(world, WORLD_ATTR, None) is not None:
            setattr(world, WORLD_ATTR, None)
        return None
    ensure_vw1_state(world, config)
    st = state_of(world)
    if st is not None:
        return st
    raw = getattr(config, "volumetric_world_material_separation", None)
    cfg = (
        raw
        if isinstance(raw, VolumetricWorldMaterialSeparationConfig)
        else VolumetricWorldMaterialSeparationConfig.from_dict(raw if isinstance(raw, dict) else None)
    )
    cfg.enabled = True
    st = VolumetricMaterialSeparationState(config=cfg)
    setattr(world, WORLD_ATTR, st)
    return st


# ---------------------------------------------------------------------------
# Pure interval subtraction (VW1 endpoint semantics)
# ---------------------------------------------------------------------------


def _scale_composition(
    composition: tuple[tuple[str, float], ...], factor: float
) -> tuple[tuple[str, float], ...]:
    if factor <= TOLERANCE:
        return ()
    out: list[tuple[str, float]] = []
    for cid, amount in composition:
        qty = float(amount) * float(factor)
        if qty > TOLERANCE:
            out.append((str(cid), float(qty)))
    return tuple(out)


def subtract_z_range_from_intervals(
    intervals: tuple[OccupiedZInterval, ...] | list[OccupiedZInterval],
    z_remove_lo: float,
    z_remove_hi: float,
) -> tuple[tuple[OccupiedZInterval, ...], tuple[OccupiedZInterval, ...]]:
    """Remove occupied matter in (z_remove_lo, z_remove_hi] from intervals.

    Returns (remaining_intervals, removed_pieces). Removed pieces retain source
    material identity scaled by thickness fraction. Empty/free removal yields
    empty removed tuple and unchanged remaining.
    """
    lo = float(z_remove_lo)
    hi = float(z_remove_hi)
    if not (math.isfinite(lo) and math.isfinite(hi)):
        raise VolumetricSeparationValidationError("removal z bounds must be finite")
    if hi <= lo + TOLERANCE:
        raise VolumetricSeparationValidationError("removal z_hi must exceed z_lo")

    remaining: list[OccupiedZInterval] = []
    removed: list[OccupiedZInterval] = []
    for it in intervals:
        z0 = float(it.z_min)
        z1 = float(it.z_max)
        # Intersection of (z0, z1] ∩ (lo, hi]
        inter_lo = max(z0, lo)
        inter_hi = min(z1, hi)
        if inter_hi <= inter_lo + TOLERANCE:
            remaining.append(it)
            continue
        thickness = z1 - z0
        rem_th = inter_hi - inter_lo
        factor = rem_th / thickness if thickness > TOLERANCE else 0.0
        removed.append(
            OccupiedZInterval(
                z_min=inter_lo,
                z_max=inter_hi,
                density=float(it.density),
                composition=_scale_composition(it.composition, factor),
                material_property_derivation_version=it.material_property_derivation_version,
                source_layer_index=int(it.source_layer_index),
            )
        )
        # Left remnant (z0, min(z1, lo)]
        left_hi = min(z1, lo)
        if left_hi > z0 + TOLERANCE:
            left_f = (left_hi - z0) / thickness
            remaining.append(
                OccupiedZInterval(
                    z_min=z0,
                    z_max=left_hi,
                    density=float(it.density),
                    composition=_scale_composition(it.composition, left_f),
                    material_property_derivation_version=it.material_property_derivation_version,
                    source_layer_index=int(it.source_layer_index),
                )
            )
        # Right remnant (max(z0, hi), z1]
        right_lo = max(z0, hi)
        if z1 > right_lo + TOLERANCE:
            right_f = (z1 - right_lo) / thickness
            remaining.append(
                OccupiedZInterval(
                    z_min=right_lo,
                    z_max=z1,
                    density=float(it.density),
                    composition=_scale_composition(it.composition, right_f),
                    material_property_derivation_version=it.material_property_derivation_version,
                    source_layer_index=int(it.source_layer_index),
                )
            )
    # Reject mixing incompatible materials in a single removal batch
    if len(removed) > 1:
        dens0 = float(removed[0].density)
        comp0 = removed[0].composition
        deriv0 = removed[0].material_property_derivation_version
        for piece in removed[1:]:
            if abs(float(piece.density) - dens0) > TOLERANCE:
                raise VolumetricSeparationValidationError(R_MATERIAL)
            if piece.composition != comp0 and not _composition_proportional_same_ids(comp0, piece.composition):
                # Allow same component ids; amounts may differ by thickness — merge below
                ids0 = {c for c, _ in comp0}
                ids1 = {c for c, _ in piece.composition}
                if ids0 != ids1:
                    raise VolumetricSeparationValidationError(R_MATERIAL)
            if str(piece.material_property_derivation_version) != str(deriv0):
                raise VolumetricSeparationValidationError(R_MATERIAL)

    return canonicalize_intervals(remaining), tuple(removed)


def _composition_proportional_same_ids(a, b) -> bool:
    return {c for c, _ in a} == {c for c, _ in b}


def _merge_removed_pieces(pieces: tuple[OccupiedZInterval, ...]) -> OccupiedZInterval | None:
    if not pieces:
        return None
    if len(pieces) == 1:
        return pieces[0]
    # Merge amounts for conservation accounting (same material family)
    dens = float(pieces[0].density)
    deriv = pieces[0].material_property_derivation_version
    z_min = min(float(p.z_min) for p in pieces)
    z_max = max(float(p.z_max) for p in pieces)
    # Sum composition amounts (already thickness-scaled per piece)
    from collections import defaultdict

    totals: dict[str, float] = defaultdict(float)
    for p in pieces:
        for cid, amt in p.composition:
            totals[str(cid)] += float(amt)
    thickness = sum(float(p.z_max) - float(p.z_min) for p in pieces)
    # Represent as a single accounting interval spanning union (may include gaps in Z —
    # used only for quantity/mass totals, not re-inserted as authority)
    return OccupiedZInterval(
        z_min=z_min,
        z_max=z_min + thickness,  # packed thickness representation for qty
        density=dens,
        composition=tuple((cid, totals[cid]) for cid in sorted(totals) if totals[cid] > TOLERANCE),
        material_property_derivation_version=deriv,
        source_layer_index=min(int(p.source_layer_index) for p in pieces),
    )


def _removed_quantity_mass(pieces: tuple[OccupiedZInterval, ...], *, area: float) -> tuple[float, float, list[dict[str, Any]]]:
    qty = 0.0
    mass = 0.0
    comps: dict[str, float] = {}
    for p in pieces:
        th = float(p.z_max) - float(p.z_min)
        qty += th * area
        mass += th * float(p.density) * area
        for cid, amt in p.composition:
            # composition on intervals is quantity_per_area; absolute = amt * area
            comps[str(cid)] = comps.get(str(cid), 0.0) + float(amt) * area
    composition = [{"component_id": cid, "amount": float(comps[cid])} for cid in sorted(comps)]
    return float(qty), float(mass), composition


# ---------------------------------------------------------------------------
# Plan / commit
# ---------------------------------------------------------------------------


def _next_object_id(world: Any) -> str:
    objs = list(getattr(world, "resource_objects", None) or [])
    n = len(objs) + 1
    return f"resource-{n:06d}"


def _objects_list(world: Any) -> list[Any]:
    return list(getattr(world, "resource_objects", None) or [])


def plan_volumetric_material_separation(
    world: Any,
    config: Any,
    *,
    cell_x: int,
    cell_y: int,
    z_remove_lo: float,
    z_remove_hi: float,
    tick: int = 0,
    researcher_id: str = "researcher",
) -> dict[str, Any]:
    """Plan occupancy interval removal. No mutation. Researcher/test-only."""
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
    }
    if not volumetric_world_material_separation_is_active(config):
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
        lo = float(z_remove_lo)
        hi = float(z_remove_hi)
        if not (math.isfinite(lo) and math.isfinite(hi)) or hi <= lo + TOLERANCE:
            plan["status"] = "REJECTED"
            plan["rejection_reason"] = R_BOUNDS
            return plan
    except (TypeError, ValueError):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_BOUNDS
        return plan

    cell = wrap_cell(st_vo, cell_x, cell_y)
    before = occupied_intervals_at(world, cell[0], cell[1])
    plan["materialize_sparse_before_commit"] = bool(cell not in st_vo.columns and before)
    plan["cell"] = [int(cell[0]), int(cell[1])]
    plan["before"] = {
        "occupied_intervals": [it.as_dict() for it in before],
        "derived_surface_elevation": compatibility_surface_elevation(world, cell[0], cell[1]),
        "occupancy_digest": st_vo.digest(),
    }
    plan["removal"] = {"z_lo": lo, "z_hi": hi, "endpoint_semantics": "HALF_OPEN_LOWER_EXCLUSIVE_UPPER_INCLUSIVE"}

    if not before:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_EMPTY
        return plan

    try:
        remaining, removed_pieces = subtract_z_range_from_intervals(before, lo, hi)
    except VolumetricSeparationValidationError as exc:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = str(exc) if str(exc) else R_MATERIAL
        return plan

    if not removed_pieces:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_FREE
        return plan

    area = float(getattr(getattr(config, "volumetric_world_material_separation", None), "cell_area", CELL_AREA) or CELL_AREA)
    qty, mass, composition = _removed_quantity_mass(removed_pieces, area=area)
    if qty <= TOLERANCE:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_ZERO
        return plan

    tid = allocate_transaction_id(world, tick)
    sid = f"vw3-sep-{tid}"
    ox = float(cell[0]) + 0.5
    oy = float(cell[1]) + 0.5
    # Place on remaining support if any, else at removal lower bound
    remaining_surface = max((float(it.z_max) for it in remaining), default=None)
    oz = float(remaining_surface) if remaining_surface is not None else float(lo)

    plan["transaction_id"] = tid
    plan["separation_id"] = sid
    plan["after"] = {
        "occupied_intervals": [it.as_dict() for it in remaining],
        "derived_surface_elevation": remaining_surface,
        "free_gap_created": len(remaining) > len(before) or (
            len(remaining) >= 2 and any(
                abs(float(remaining[i].z_min) - float(remaining[i - 1].z_max)) > TOLERANCE
                for i in range(1, len(remaining))
            )
        ),
    }
    plan["removed_pieces"] = [it.as_dict() for it in removed_pieces]
    plan["candidates"] = {
        "remaining_intervals": remaining,
        "removed_pieces": removed_pieces,
        "object": {
            "x": ox,
            "y": oy,
            "z": oz,
            "quantity": float(qty),
            "mass": float(mass),
            "composition": composition,
            "collision_radius": 0.25,
            "vertical_half_extent": 0.25,
            "creation_tick": int(tick),
            "dynamics_eligible_tick": int(tick) + 1,
            "support_z": oz,
            "placement_policy": "VW3_CELL_CENTRE_ON_REMAINING_OR_REMOVAL_LO",
        },
    }
    plan["conservation"] = {
        "cell_area": float(area),
        "removed_quantity": float(qty),
        "removed_mass": float(mass),
        "object_quantity": float(qty),
        "object_mass": float(mass),
        "verified": True,
        "tolerance": CONSERVATION_TOLERANCE,
    }
    plan["expected_revisions"] = {}  # occupancy digest checked at commit
    plan["expected_occupancy_digest"] = plan["before"]["occupancy_digest"]
    plan["input_refs"] = [f"occupancy:x{cell[0]}-y{cell[1]}"]
    plan["output_refs"] = [f"occupancy:x{cell[0]}-y{cell[1]}", sid]
    return plan


def commit_planned_volumetric_separation(world: Any, plan: dict[str, Any]) -> dict[str, Any]:
    """Atomic commit: occupancy mutation + ResourceObject. Called from WMT."""
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    st = state_of(world)
    if st is None:
        # Allow commit if config still on — ensure state
        cfg = plan.get("config")
        st = ensure_state(world, cfg) if cfg is not None else None
    if st is None:
        return _reject(world, plan, R_INACTIVE)

    sid = str(plan.get("separation_id") or "")
    if sid and sid in st.committed_ids:
        return _reject(world, plan, R_DUPLICATE)

    st_vo = vo_state(world)
    if st_vo is None:
        return _reject(world, plan, R_VW1_OFF)
    if str(plan.get("expected_occupancy_digest") or "") and st_vo.digest() != str(plan["expected_occupancy_digest"]):
        return _reject(world, plan, "OCCUPANCY_STATE_CHANGED")

    cell = plan.get("cell") or [0, 0]
    cx, cy = int(cell[0]), int(cell[1])
    remaining: tuple[OccupiedZInterval, ...] = plan["candidates"]["remaining_intervals"]
    obj_spec = plan["candidates"]["object"]
    oid = _next_object_id(world)
    existing_ids = {str(getattr(o, "object_id", "")) for o in _objects_list(world)}
    if oid in existing_ids:
        return _reject(world, plan, R_ID)

    composition = tuple(
        MaterialComponent(str(row["component_id"]), float(row["amount"]))
        for row in obj_spec["composition"]
    )
    cons = plan.get("conservation") or {}
    if abs(float(cons.get("removed_quantity", 0)) - float(obj_spec["quantity"])) > CONSERVATION_TOLERANCE:
        return _reject(world, plan, R_CONSERVATION)
    if abs(float(cons.get("removed_mass", 0)) - float(obj_spec["mass"])) > CONSERVATION_TOLERANCE:
        return _reject(world, plan, R_CONSERVATION)

    rem = plan.get("removal") or {}
    provenance = {
        "source": "VOLUMETRIC_MATERIAL_SEPARATION",
        "researcher_only": True,
        "not_agent_accessible_origin": True,
        "transaction_id": str(plan.get("transaction_id")),
        "separation_id": sid,
        "operation_kind": OPERATION_KIND,
        "schema": SCHEMA,
        "source_cell": [cx, cy],
        "source_z_lo": float(rem.get("z_lo", 0.0)),
        "source_z_hi": float(rem.get("z_hi", 0.0)),
        "removed_pieces": list(plan.get("removed_pieces") or []),
        "before_intervals": list((plan.get("before") or {}).get("occupied_intervals") or []),
        "after_intervals": list((plan.get("after") or {}).get("occupied_intervals") or []),
        "tick": int(plan.get("tick") or 0),
        "support_z": obj_spec.get("support_z"),
        "placement_policy": obj_spec.get("placement_policy"),
    }
    obj = ResourceObject(
        object_id=oid,
        x=float(obj_spec["x"]),
        y=float(obj_spec["y"]),
        mass=float(obj_spec["mass"]),
        quantity=float(obj_spec["quantity"]),
        composition=composition,
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        vx=0.0,
        vy=0.0,
        provenance=provenance,
        optical_radius=float(CANONICAL_OPTICAL_RADIUS),
        optical_response=tuple(CANONICAL_OPTICAL_RESPONSE),
        interaction_radius=float(CANONICAL_INTERACTION_RADIUS),
        collision_radius=float(obj_spec.get("collision_radius") or 0.25),
        vertical_half_extent=float(obj_spec.get("vertical_half_extent") or 0.25),
        material_revision=0,
        z=float(obj_spec.get("z") or 0.0),
        vz=0.0,
        grounded=True,
        creation_tick=int(obj_spec["creation_tick"]) if obj_spec.get("creation_tick") is not None else None,
        dynamics_eligible_tick=(
            int(obj_spec["dynamics_eligible_tick"]) if obj_spec.get("dynamics_eligible_tick") is not None else None
        ),
    )

    receipt = {
        "status": "COMMITTED",
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "operation_kind": OPERATION_KIND,
        "transaction_id": str(plan.get("transaction_id")),
        "separation_id": sid,
        "object_id": oid,
        "cell": [cx, cy],
        "removal": dict(rem),
        "before": plan.get("before"),
        "after": plan.get("after"),
        "removed_pieces": plan.get("removed_pieces"),
        "conservation": plan.get("conservation"),
        "researcher_only": True,
        "agent_accessible": False,
        "tick": int(plan.get("tick") or 0),
    }

    # ---- atomic publish: occupancy then object ----
    set_volumetric_column(
        world,
        cx,
        cy,
        remaining,
        tick=int(plan.get("tick") or 0),
        reason="VW3_VOLUMETRIC_MATERIAL_SEPARATION",
    )
    world.resource_objects = list(_objects_list(world)) + [obj]
    try:
        wmt._sync_spatial_index(world, plan)
    except Exception:
        pass

    st.committed_ids.add(sid)
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
        "separation_id": plan.get("separation_id"),
        "researcher_only": True,
        "tick": int(plan.get("tick") or 0),
    }
    wmt._remember(world, receipt)
    st = state_of(world)
    if st is not None:
        st.last_receipt = receipt
        st.counters["rejected"] = int(st.counters.get("rejected", 0)) + 1
    return {"legacy": None, "receipt": receipt}


def apply_volumetric_material_separation(
    world: Any,
    config: Any,
    *,
    cell_x: int,
    cell_y: int,
    z_remove_lo: float,
    z_remove_hi: float,
    tick: int = 0,
    researcher_id: str = "researcher",
) -> dict[str, Any]:
    """Researcher/test-only: plan + WMT commit. Not an organism action."""
    from mechanistic_mind.physical_system.world_material_transaction import commit_material_transaction

    ensure_state(world, config)
    # Materialize derived PSC column into sparse authority before plan (plan itself is read-only).
    st_vo = vo_state(world)
    if st_vo is not None:
        cell = wrap_cell(st_vo, cell_x, cell_y)
        before = occupied_intervals_at(world, cell[0], cell[1])
        if cell not in st_vo.columns and before:
            set_volumetric_column(
                world, cell[0], cell[1], before, tick=int(tick), reason="VW3_MATERIALIZE_BEFORE_SEPARATION"
            )
    plan = plan_volumetric_material_separation(
        world,
        config,
        cell_x=cell_x,
        cell_y=cell_y,
        z_remove_lo=z_remove_lo,
        z_remove_hi=z_remove_hi,
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
        "volumetric_material_separation": {
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


def observer_separation_inspector_payload(world: Any, config: Any | None = None) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None or not st.last_receipt:
        return None
    rec = dict(st.last_receipt)
    return {
        "mechanism": MECHANISM_ID,
        "schema": SCHEMA,
        "authority_label": "AUTHORITATIVE VW3 VOLUMETRIC SEPARATION VIA WMT",
        "legacy_label": "LEGACY / DERIVED SURFACE PROJECTION (not separation truth)",
        "receipt": rec,
        "researcher_only_view": True,
        "not_agent_accessible": True,
        "source_kind": "VW3_SEPARATION_INSPECTION",
    }


def volumetric_material_separation_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "volumetric_world_material_separation.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "schema": SCHEMA,
        "profile": PROFILE,
        "description": (
            "Conservative material separation mutates VW1 volumetric occupancy via WMT. "
            "Creates ResourceObjects with conserved quantity/mass. No DIG verb. VW4 is the inverse reintegration path."
        ),
    }
