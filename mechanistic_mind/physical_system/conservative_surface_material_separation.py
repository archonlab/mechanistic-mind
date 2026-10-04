"""Acanthostega Beta 4 · Conservative surface material separation.

Operation: SEPARATE_SURFACE_COLUMN_SLICE
  SOURCE: authoritative surface column top slice (per-area material)
  DESTINATION: ordinary ResourceObject (cell footprint area = 1)

Atomic WMT path (plan without mutation → commit_material_transaction →
single publish of column delta + object insert).

NOT DIG / EXCAVATE / MINE. Researcher-only trigger for V1.
Future physical exertion will invoke the SAME plan/commit functions.

Geometry (FIXED_LOWER_DATUM_V1, same as column transfer):
  elevation -= t, resolved_depth -= t
Layer quantities (unchanged):
  quantity_per_area = thickness
  mass_per_area = thickness * density
Cell footprint convention:
  1 grid cell = 1 horizontal area unit
  ⇒ object.quantity = quantity_per_area, object.mass = mass_per_area

V1 policies:
  TOP_SLICE_ONLY / STOP_AT_TOP_LAYER_BOUNDARY (clamp to top thickness)
  OVER_REQUEST = CLAMP_TO_AVAILABLE_TOP
  never cross layer boundary in one transaction
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.physical_system import procedural_surface_columns as psc
from mechanistic_mind.physical_system.conservative_surface_column_transfer import (
    CONSERVATION_TOLERANCE,
    DATUM_POLICY,
    _candidate_delta,
    _resolved,
    column_revision_for_key,
    resolved_depth,
    split_top_slice,
)
from mechanistic_mind.physical_system.resource_objects import (
    CANONICAL_COLLISION_RADIUS,
    CANONICAL_INTERACTION_RADIUS,
    CANONICAL_OPTICAL_RADIUS,
    CANONICAL_OPTICAL_RESPONSE,
    MaterialComponent,
    PHYSICAL_STATE_FREE_STATIC,
    ResourceObject,
)

MECHANISM_ID = "conservative_surface_material_separation"
OPERATION_KIND = "SEPARATE_SURFACE_COLUMN_SLICE"
RECEIPT_KIND = "SURFACE_MATERIAL_SEPARATION"
RECEIPT_SCHEMA = "SURFACE_MATERIAL_SEPARATION_V1"
STATE_SCHEMA = "SURFACE_MATERIAL_SEPARATION_STATE_V1"
PROFILE_VERSION = "CONSERVATIVE_SURFACE_MATERIAL_SEPARATION_V1"
EVENT_COMMITTED = "SURFACE_MATERIAL_SEPARATION_COMMITTED"
EVENT_REJECTED = "SURFACE_MATERIAL_SEPARATION_REJECTED"

SELECTION_PROVENANCE = "INTERVENTION_SETUP"
CELL_AREA = 1.0  # horizontal area units per grid cell
CROSS_LAYER_POLICY = "STOP_AT_TOP_LAYER_BOUNDARY_CLAMP_V1"
OVER_REQUEST_POLICY = "CLAMP_TO_AVAILABLE_TOP_V1"
TRANSFER_POLICY = "CONTIGUOUS_TOP_SLICE_SINGLE_LAYER_V1"
FOOTPRINT_POLICY = "ONE_CELL_AREA_EQUALS_ONE_V1"

HISTORY_LIMIT = 32
COMMITTED_ID_LIMIT = 64

R_INACTIVE = "MECHANISM_INACTIVE"
R_COLUMNS_OFF = "PROCEDURAL_COLUMNS_INACTIVE"
R_NONFINITE = "NONFINITE_REQUEST"
R_ZERO = "ZERO_THICKNESS"
R_NEGATIVE = "NEGATIVE_THICKNESS"
R_NO_TOP = "NO_TOP_LAYER"
R_DEPTH = "SOURCE_DEPTH_BELOW_MINIMUM"
R_INTERVAL = "INTERVAL_VALIDATION_FAILED"
R_CONSERVATION = "CONSERVATION_FAILED"
R_CAPACITY = "DELTA_CAPACITY_EXCEEDED"
R_STALE = "STALE_COLUMN_REVISION"
R_BASE = "BASELINE_CHECKSUM_MISMATCH"
R_GENERATOR = "UNKNOWN_GENERATOR_VERSION"
R_PLACEMENT = "UNSAFE_OBJECT_PLACEMENT"
R_ID = "OBJECT_ID_COLLISION"
R_STATE_CHANGED = "COLUMN_STATE_CHANGED_SINCE_PLAN"
R_DUPLICATE = "ALREADY_COMMITTED"
R_WMT_OFF = "WORLD_MATERIAL_TRANSACTIONS_INACTIVE"

EFFECT_FLAGS = {
    "researcher_only": True,
    "agent_action": False,
    "agent_accessible": False,
    "physical_effects_active": True,  # column elevation change is physical geometry
    "resource_spawned": True,
    "recipe_match": False,
    "semantic_effect": False,
    "reward_created": False,
    "motor_vocabulary": False,
    "endogenous_action": False,
    "excavation_action": False,
    "dig_action": False,
}


@dataclass
class ConservativeSurfaceMaterialSeparationConfig:
    """Fresh default OFF. Missing snapshot field keeps mechanism OFF."""

    enabled: bool = False
    minimum_resolved_depth: float = 0.5
    maximum_slice_thickness: float = 0.25  # V1 object geometry bound
    history_limit: int = HISTORY_LIMIT
    # Placement offset from cell centre (world units); avoids cell-centre body spawn.
    placement_offset_x: float = 0.35
    placement_offset_y: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "minimum_resolved_depth": float(self.minimum_resolved_depth),
            "maximum_slice_thickness": float(self.maximum_slice_thickness),
            "history_limit": int(self.history_limit),
            "placement_offset_x": float(self.placement_offset_x),
            "placement_offset_y": float(self.placement_offset_y),
            "datum_policy": DATUM_POLICY,
            "cross_layer_policy": CROSS_LAYER_POLICY,
            "over_request_policy": OVER_REQUEST_POLICY,
            "transfer_policy": TRANSFER_POLICY,
            "footprint_policy": FOOTPRINT_POLICY,
            "cell_area": float(CELL_AREA),
            "operation_kind": OPERATION_KIND,
            "profile_version": PROFILE_VERSION,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ConservativeSurfaceMaterialSeparationConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        return cls(
            enabled=bool(data.get("enabled", False)),
            minimum_resolved_depth=float(data.get("minimum_resolved_depth", 0.5)),
            maximum_slice_thickness=float(data.get("maximum_slice_thickness", 0.25)),
            history_limit=int(data.get("history_limit", HISTORY_LIMIT)),
            placement_offset_x=float(data.get("placement_offset_x", 0.35)),
            placement_offset_y=float(data.get("placement_offset_y", 0.0)),
        )


def validate_config(cfg: ConservativeSurfaceMaterialSeparationConfig) -> None:
    lo = float(cfg.minimum_resolved_depth)
    mx = float(cfg.maximum_slice_thickness)
    if not (math.isfinite(lo) and lo > 0.0):
        raise ValueError("minimum_resolved_depth must be finite and > 0")
    if not (math.isfinite(mx) and 0.0 < mx <= 8.0):
        raise ValueError("maximum_slice_thickness must be in (0, 8]")


def _line_ok(config: Any) -> bool:
    return config is not None and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"


def conservative_surface_material_separation_is_active(config: Any) -> bool:
    if not _line_ok(config) or not psc.procedural_surface_columns_is_active(config):
        return False
    cfg = getattr(config, "conservative_surface_material_separation", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_conservative_surface_material_separation(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and _line_ok(config)
    cur = getattr(config, "conservative_surface_material_separation", None)
    if cur is None:
        if on:
            config.conservative_surface_material_separation = (
                ConservativeSurfaceMaterialSeparationConfig(enabled=True)
            )
        return
    cur.enabled = bool(on)


@dataclass
class SurfaceMaterialSeparationState:
    config: ConservativeSurfaceMaterialSeparationConfig
    schema: str = STATE_SCHEMA
    last_receipt: dict[str, Any] | None = None
    history: list[dict[str, Any]] = field(default_factory=list)
    committed_ids: list[str] = field(default_factory=list)
    counters: dict[str, int] = field(
        default_factory=lambda: {
            "planned": 0,
            "committed": 0,
            "rejected": 0,
            "clamped": 0,
        }
    )


def state_of(world: Any) -> SurfaceMaterialSeparationState | None:
    return getattr(world, "surface_material_separation_state", None)


def ensure_surface_material_separation_for_runtime(world: Any, config: Any) -> SurfaceMaterialSeparationState | None:
    if not conservative_surface_material_separation_is_active(config):
        return None
    st = state_of(world)
    cfg = getattr(config, "conservative_surface_material_separation", None)
    if not isinstance(cfg, ConservativeSurfaceMaterialSeparationConfig):
        cfg = ConservativeSurfaceMaterialSeparationConfig.from_dict(
            cfg.to_dict() if cfg is not None and hasattr(cfg, "to_dict") else cfg
        )
    validate_config(cfg)
    if st is None:
        st = SurfaceMaterialSeparationState(config=cfg)
        world.surface_material_separation_state = st
    else:
        st.config = cfg
    return st


def serialize_state(st: SurfaceMaterialSeparationState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema": STATE_SCHEMA,
        "config": st.config.to_dict(),
        "last_receipt": dict(st.last_receipt) if st.last_receipt else None,
        "history": [dict(r) for r in st.history[-HISTORY_LIMIT:]],
        "committed_ids": list(st.committed_ids[-COMMITTED_ID_LIMIT:]),
        "counters": dict(st.counters),
    }


def restore_state(world: Any, payload: dict[str, Any] | None) -> None:
    if not isinstance(payload, dict):
        world.surface_material_separation_state = None
        return
    cfg = ConservativeSurfaceMaterialSeparationConfig.from_dict(payload.get("config"))
    st = SurfaceMaterialSeparationState(config=cfg)
    st.last_receipt = dict(payload["last_receipt"]) if isinstance(payload.get("last_receipt"), dict) else None
    st.history = [dict(r) for r in (payload.get("history") or []) if isinstance(r, dict)]
    st.committed_ids = [str(x) for x in (payload.get("committed_ids") or [])]
    st.counters = dict(payload.get("counters") or st.counters)
    world.surface_material_separation_state = st


def _domain(before: float, after: float, tol: float = CONSERVATION_TOLERANCE) -> dict[str, Any]:
    residual = float(after) - float(before)
    return {
        "before": float(before),
        "after": float(after),
        "residual": residual,
        "tolerance": tol,
        "verified": bool(math.isfinite(residual) and abs(residual) <= tol),
    }


def _next_object_id(world: Any) -> str:
    n = int(getattr(world, "resource_object_next_id", 1) or 1)
    oid = f"resource-{n:06d}"
    world.resource_object_next_id = n + 1
    return oid


def _objects_list(world: Any) -> list[Any]:
    objs = getattr(world, "resource_objects", None)
    if objs is None:
        world.resource_objects = []
        return world.resource_objects
    return list(objs) if not isinstance(objs, list) else objs


def _placement_ok(world: Any, config: Any, x: float, y: float, radius: float) -> bool:
    """Reject obvious overlaps with bodies / existing objects (deterministic)."""
    r = float(radius)
    # Existing objects
    for o in _objects_list(world):
        ox = float(getattr(o, "x", 0.0) or 0.0)
        oy = float(getattr(o, "y", 0.0) or 0.0)
        orad = float(getattr(o, "collision_radius", CANONICAL_COLLISION_RADIUS) or CANONICAL_COLLISION_RADIUS)
        if math.hypot(x - ox, y - oy) < (r + orad) * 0.95:
            return False
    # Bodies (single-agent / multi via body_refs if available)
    bodies = []
    b = getattr(world, "body", None)
    if b is not None:
        bodies.append(b)
    # Two-agent: world may not hold bodies; caller may pass via config runtime — skip if absent.
    for body in bodies:
        bx = float(getattr(body, "x", 0.0) or 0.0)
        by = float(getattr(body, "y", 0.0) or 0.0)
        # Approximate body contact radius
        brad = 0.55
        if math.hypot(x - bx, y - by) < (r + brad) * 0.95:
            return False
    return True


def plan_surface_material_separation(
    world: Any,
    config: Any,
    *,
    cell_x: int,
    cell_y: int,
    requested_thickness: float,
    tick: int = 0,
    researcher_id: str = "researcher",
    expected_revision: int | None = None,
    object_x: float | None = None,
    object_y: float | None = None,
    body_refs: list | None = None,
    acting_body_id: str | None = None,
    transmitting_object_id: str | None = None,
) -> dict[str, Any]:
    """Plan only — no world mutation."""
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    st = ensure_surface_material_separation_for_runtime(world, config)
    plan: dict[str, Any] = {
        "operation_kind": OPERATION_KIND,
        "command": OPERATION_KIND,
        "receipt_kind": RECEIPT_KIND,
        "receipt_schema": RECEIPT_SCHEMA,
        "mechanism": MECHANISM_ID,
        "profile_version": PROFILE_VERSION,
        "status": "PLANNED",
        "tick": int(tick),
        "config": config,
        "researcher_id": str(researcher_id),
        "selection_provenance": SELECTION_PROVENANCE,
        "agent_action": False,
        "cell_x": int(cell_x),
        "cell_y": int(cell_y),
        "requested_thickness": float(requested_thickness),
        **EFFECT_FLAGS,
    }
    if st is None:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_INACTIVE
        return plan
    if not psc.procedural_surface_columns_is_active(config):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_COLUMNS_OFF
        return plan
    try:
        from mechanistic_mind.physical_system.world_material_transaction import (
            world_material_transactions_is_active,
        )
        if not world_material_transactions_is_active(config):
            plan["status"] = "REJECTED"
            plan["rejection_reason"] = R_WMT_OFF
            return plan
    except Exception:
        pass

    st.counters["planned"] = int(st.counters.get("planned", 0)) + 1
    transaction_id = wmt.allocate_transaction_id(world, int(tick))
    plan["transaction_id"] = transaction_id
    separation_id = f"sep-{transaction_id}"
    plan["separation_id"] = separation_id

    t_req = float(requested_thickness)
    if not math.isfinite(t_req):
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_NONFINITE
        return plan
    if t_req == 0.0:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_ZERO
        return plan
    if t_req < 0.0:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_NEGATIVE
        return plan

    cell = (int(cell_x), int(cell_y))
    col = _resolved(world, cell)
    if col["delta"] is not None and col["delta"].baseline_generator_version not in psc.SUPPORTED_GENERATOR_VERSIONS:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_GENERATOR
        return plan
    if col["delta"] is not None and col["delta"].baseline_checksum != col["baseline"].baseline_checksum:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_BASE
        return plan

    rev = int(col["revision"])
    exp = rev if expected_revision is None else int(expected_revision)
    plan["expected_revisions"] = {f"column:x{cell[0]}-y{cell[1]}": exp}
    if exp != rev:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_STALE
        return plan

    if not col["layers"]:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_NO_TOP
        return plan

    top = col["layers"][0]
    top_th = float(top.thickness)
    max_t = float(st.config.maximum_slice_thickness)
    # Depth floor: cannot remove past minimum_resolved_depth
    depth_cap = max(0.0, float(col["resolved_depth"]) - float(st.config.minimum_resolved_depth))
    available = min(top_th, max_t, depth_cap)
    clamped = False
    t = float(t_req)
    if t > available:
        t = float(available)
        clamped = True
        st.counters["clamped"] = int(st.counters.get("clamped", 0)) + 1
    plan["clamped"] = bool(clamped)
    plan["available_top_thickness"] = float(available)
    plan["applied_thickness"] = float(t)
    plan["cross_layer_policy"] = CROSS_LAYER_POLICY
    plan["over_request_policy"] = OVER_REQUEST_POLICY

    if t <= 0.0 or t > top_th + 1e-15:
        # Nothing removable (exhausted or depth floor)
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_DEPTH if depth_cap <= 0.0 else R_NO_TOP
        return plan

    sl, src_layers, whole = split_top_slice(col["layers"], t)
    elev_after = float(col["elevation"]) - t
    depth_after = resolved_depth(col["baseline"], elev_after)
    if depth_after < float(st.config.minimum_resolved_depth) - 1e-12:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_DEPTH
        return plan
    v_src = psc.validate_layers(src_layers, depth_after)
    plan["interval_validation"] = {"source": v_src}
    if not v_src["verified"]:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_INTERVAL
        plan["interval_problems"] = v_src.get("problems")
        return plan

    # Object materialization (totals = per-area × CELL_AREA)
    area = float(CELL_AREA)
    qty = float(sl.quantity_per_area) * area
    mass = float(sl.mass_per_area) * area
    composition = tuple(
        MaterialComponent(str(cid), float(a) * area) for cid, a in sl.composition
    )

    # Reserve provisional id for receipts only; real id allocated at commit.
    provisional_id = f"resource-pending-{transaction_id}"

    before_summary = psc.mass_summary(col["layers"])
    after_summary = psc.mass_summary(src_layers)
    # Conservation: column loss (per area × CELL_AREA) == object totals
    col_qty_loss = (before_summary["total_quantity_per_area"] - after_summary["total_quantity_per_area"]) * area
    col_mass_loss = (before_summary["total_mass_per_area"] - after_summary["total_mass_per_area"]) * area
    conservation = {
        "quantity": _domain(col_qty_loss, qty),
        "mass": _domain(col_mass_loss, mass),
        "components": {
            "column_loss": {
                k: (float(before_summary["component_quantity_per_area"].get(k, 0.0))
                    - float(after_summary["component_quantity_per_area"].get(k, 0.0))) * area
                for k in sorted(
                    set(before_summary["component_quantity_per_area"])
                    | set(after_summary["component_quantity_per_area"])
                )
            },
            "object": {c.component_id: float(c.amount) for c in composition},
        },
        "elevation": _domain(col["elevation"], elev_after),
        "thickness_vs_elevation": _domain(t, float(col["elevation"]) - elev_after),
        "cell_area": area,
        "verified": True,
    }
    # Component residuals
    cl = conservation["components"]["column_loss"]
    ob = conservation["components"]["object"]
    keys = sorted(set(cl) | set(ob))
    residuals = {k: float(ob.get(k, 0.0)) - float(cl.get(k, 0.0)) for k in keys}
    worst = max((abs(v) for v in residuals.values()), default=0.0)
    conservation["components"]["residuals"] = residuals
    conservation["components"]["residual_max_abs"] = float(worst)
    conservation["verified"] = bool(
        conservation["quantity"]["verified"]
        and conservation["mass"]["verified"]
        and conservation["thickness_vs_elevation"]["verified"]
        and worst <= CONSERVATION_TOLERANCE
    )
    plan["conservation"] = conservation
    if not conservation["verified"]:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_CONSERVATION
        return plan

    new_cells = 1 if col["delta"] is None else 0
    if len(psc.deltas_of(world)) + new_cells > psc.MAX_DELTAS:
        plan["status"] = "REJECTED"
        plan["rejection_reason"] = R_CAPACITY
        return plan

    src_delta = _candidate_delta(
        col,
        layers=src_layers,
        elevation=elev_after,
        tick=int(tick),
        transaction_id=transaction_id,
        provenance={
            "kind": "SURFACE_MATERIAL_SEPARATION",
            "researcher_only": True,
            "not_agent_action": True,
            "operation_kind": OPERATION_KIND,
            "last_transaction_id": transaction_id,
            "separation_id": separation_id,
            "researcher_id": str(researcher_id),
            "detached_object_provisional_id": provisional_id,
            "creation_tick": int(tick),
            "separation_exchange": {
                "quantity_per_area": -float(sl.quantity_per_area),
                "mass_per_area": -float(sl.mass_per_area),
                "component_quantity_per_area": {cid: -float(a) for cid, a in sl.composition},
            },
        },
    )

    # ---- Creation-time collision radius (amount-scaled V1 or canonical) ----
    # Radius must be known before DTIP conflict checks. Uses final planned quantity.
    collision_radius = float(CANONICAL_COLLISION_RADIUS)
    size_derivation_dict: dict[str, Any] | None = None
    vertical_half_extent = float(CANONICAL_COLLISION_RADIUS)
    try:
        from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
            DEFAULT_PROFILE,
            build_object_size_provenance,
            derive_detached_material_collision_radius,
            detached_material_amount_scaled_collision_radius_is_active,
            record_size_geometry_receipt,
        )

        if detached_material_amount_scaled_collision_radius_is_active(config):
            derivation = derive_detached_material_collision_radius(float(qty), DEFAULT_PROFILE)
            size_derivation_dict = derivation.to_dict()
            plan["size_geometry"] = size_derivation_dict
            if not derivation.valid:
                record_size_geometry_receipt(
                    world,
                    config,
                    derivation,
                    transaction_id=str(transaction_id),
                    source_cell=cell,
                    creation_tick=int(tick),
                    mass=float(mass),
                    committed=False,
                )
                plan["status"] = "REJECTED"
                plan["rejection_reason"] = derivation.rejection_reason or R_NONFINITE
                return plan
            collision_radius = float(derivation.final_radius)
            vertical_half_extent = float(derivation.final_radius)
            record_size_geometry_receipt(
                world,
                config,
                derivation,
                transaction_id=str(transaction_id),
                source_cell=cell,
                creation_tick=int(tick),
                mass=float(mass),
                vertical_half_extent=vertical_half_extent,
                optical_radius=float(CANONICAL_OPTICAL_RADIUS),
                committed=False,
            )
    except Exception:
        # Mechanism import/activation failure must not invent radius; keep canonical.
        collision_radius = float(CANONICAL_COLLISION_RADIUS)
        vertical_half_extent = float(CANONICAL_COLLISION_RADIUS)
        size_derivation_dict = None

    # ---- Placement (DTIP V1 or legacy) ----
    placement_rec: dict[str, Any] | None = None
    creation_tick = int(tick)
    dynamics_eligible_tick: int | None = None
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        detached_terrain_material_initial_placement_is_active,
        plan_detached_material_initial_placement,
        same_tick_newborn_obstacles,
        clear_same_tick_newborns_if_new_tick,
    )

    if detached_terrain_material_initial_placement_is_active(config):
        clear_same_tick_newborns_if_new_tick(world, int(tick))
        # Ignore legacy object_x/y overrides from tip contact — shared kernel.
        # DTIP uses the creation-time derived radius (or canonical when inactive).
        placement_rec = plan_detached_material_initial_placement(
            world,
            config,
            source_cell=cell,
            src_delta=src_delta,
            tick=int(tick),
            collision_radius=float(collision_radius),
            body_refs=body_refs,
            extra_obstacles=same_tick_newborn_obstacles(world, int(tick)),
            acting_body_id=acting_body_id,
            transmitting_object_id=transmitting_object_id,
        )
        plan["placement"] = placement_rec
        if not placement_rec.get("accepted"):
            plan["status"] = "REJECTED"
            plan["rejection_reason"] = R_PLACEMENT
            plan["placement_status"] = placement_rec.get("status")
            return plan
        ox = float(placement_rec["x"])
        oy = float(placement_rec["y"])
        oz = float(placement_rec["z"])
        dynamics_eligible_tick = int(placement_rec["dynamics_eligible_tick"])
        creation_tick = int(placement_rec.get("creation_tick") or tick)
    else:
        ox = float(object_x) if object_x is not None else float(cell[0]) + 0.5 + float(st.config.placement_offset_x)
        oy = float(object_y) if object_y is not None else float(cell[1]) + 0.5 + float(st.config.placement_offset_y)
        try:
            from mechanistic_mind.planet.topology import wrap_coord
            w = int(getattr(world, "T", [[]]) and world.T.shape[1] or 32)
            h = int(getattr(world, "T", [[]]) and world.T.shape[0] or 32)
            ox, oy = wrap_coord(ox, oy, width=w, height=h)
        except Exception:
            pass
        if not _placement_ok(world, config, ox, oy, float(collision_radius)):
            plan["status"] = "REJECTED"
            plan["rejection_reason"] = R_PLACEMENT
            return plan
        oz = float(elev_after)

    plan["candidates"] = {
        "source_delta": src_delta,
        "object": {
            "provisional_id": provisional_id,
            "x": float(ox),
            "y": float(oy),
            "z": float(oz),
            "mass": float(mass),
            "quantity": float(qty),
            "composition": [{"component_id": c.component_id, "amount": float(c.amount)} for c in composition],
            "physical_state": PHYSICAL_STATE_FREE_STATIC,
            "collision_radius": float(collision_radius),
            "vertical_half_extent": float(vertical_half_extent),
            "size_geometry": size_derivation_dict,
            "density": float(sl.density),
            "slice_thickness": float(t),
            "creation_tick": int(creation_tick),
            "dynamics_eligible_tick": dynamics_eligible_tick,
            "placement_policy": (
                placement_rec.get("placement_policy") if isinstance(placement_rec, dict) else None
            ),
            "candidate_index": (
                placement_rec.get("candidate_index") if isinstance(placement_rec, dict) else None
            ),
            "support_z": (
                placement_rec.get("support_z") if isinstance(placement_rec, dict) else None
            ),
            "centre_z": (
                float(oz) + float(collision_radius)
                if math.isfinite(float(oz))
                else None
            ),
        },
    }
    plan["before"] = {
        "source": {
            "cell": [int(cell[0]), int(cell[1])],
            "elevation": float(col["elevation"]),
            "resolved_depth": float(col["resolved_depth"]),
            "revision": int(col["revision"]),
            "checksum": col["checksum"],
            "quantity_per_area": float(before_summary["total_quantity_per_area"]),
            "mass_per_area": float(before_summary["total_mass_per_area"]),
            "top_thickness": float(top_th),
            "whole_layer_would_exhaust": bool(whole),
        }
    }
    plan["after"] = {
        "source": {
            "elevation": float(elev_after),
            "resolved_depth": float(depth_after),
            "revision": int(col["revision"]) + 1,
            "quantity_per_area": float(after_summary["total_quantity_per_area"]),
            "mass_per_area": float(after_summary["total_mass_per_area"]),
            "top_exhausted": bool(whole),
        },
        "object_quantity": float(qty),
        "object_mass": float(mass),
    }
    plan["slice"] = {
        "thickness": float(t),
        "quantity_per_area": float(sl.quantity_per_area),
        "mass_per_area": float(sl.mass_per_area),
        "density": float(sl.density),
        "composition": {cid: float(a) for cid, a in sl.composition},
        "whole_source_layer": bool(whole),
    }
    plan["input_refs"] = [f"column:x{cell[0]}-y{cell[1]}"]
    plan["output_refs"] = [f"column:x{cell[0]}-y{cell[1]}", provisional_id]
    plan["status"] = "PLANNED"
    return plan


def commit_planned_separation(world: Any, plan: dict[str, Any]) -> dict[str, Any]:
    """Atomic commit: column delta + ResourceObject. Called from WMT dispatch."""
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    st = state_of(world)
    if st is None:
        return _reject(world, plan, R_INACTIVE)
    sid = str(plan.get("separation_id") or "")
    if sid and sid in st.committed_ids:
        return _reject(world, plan, R_DUPLICATE)

    src_delta: psc.SurfaceColumnDelta = plan["candidates"]["source_delta"]
    cell = (src_delta.cell_x, src_delta.cell_y)
    deltas = psc.deltas_of(world)
    cur = deltas.get(cell)
    checksum = (
        psc.baseline_column_at(world, *cell).baseline_checksum
        if cur is None
        else cur.resolved_checksum()
    )
    if checksum != plan["before"]["source"]["checksum"]:
        return _reject(world, plan, R_STATE_CHANGED)

    obj_spec = plan["candidates"]["object"]
    oid = _next_object_id(world)
    # Ensure unique
    existing_ids = {str(getattr(o, "object_id", "")) for o in _objects_list(world)}
    if oid in existing_ids:
        return _reject(world, plan, R_ID)

    composition = tuple(
        MaterialComponent(str(row["component_id"]), float(row["amount"]))
        for row in obj_spec["composition"]
    )
    commit_radius = float(
        obj_spec.get("collision_radius")
        if obj_spec.get("collision_radius") is not None
        else CANONICAL_COLLISION_RADIUS
    )
    commit_vhe = float(
        obj_spec.get("vertical_half_extent")
        if obj_spec.get("vertical_half_extent") is not None
        else commit_radius
    )
    size_geo = obj_spec.get("size_geometry") if isinstance(obj_spec.get("size_geometry"), dict) else None
    provenance: dict[str, Any] = {
        "source": "SURFACE_MATERIAL_SEPARATION",
        "researcher_only": True,
        "not_agent_accessible_origin": True,
        "transaction_id": str(plan["transaction_id"]),
        "separation_id": sid,
        "source_cell": [int(cell[0]), int(cell[1])],
        "source_elevation_before": float(plan["before"]["source"]["elevation"]),
        "source_elevation_after": float(plan["after"]["source"]["elevation"]),
        "slice_thickness": float(plan["slice"]["thickness"]),
        "tick": int(plan.get("tick") or 0),
        "operation_kind": OPERATION_KIND,
        "creation_tick": obj_spec.get("creation_tick"),
        "dynamics_eligible_tick": obj_spec.get("dynamics_eligible_tick"),
        "placement_policy": obj_spec.get("placement_policy"),
        "candidate_index": obj_spec.get("candidate_index"),
        "support_z": obj_spec.get("support_z"),
        "centre_z": obj_spec.get("centre_z"),
    }
    if size_geo is not None:
        try:
            from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
                RadiusDerivation,
                build_object_size_provenance,
                record_size_geometry_receipt,
            )

            # Reconstruct derivation from planned size_geometry for provenance stamp.
            derivation = RadiusDerivation(
                quantity=float(size_geo.get("quantity") or obj_spec["quantity"]),
                quantity_ref=float(size_geo.get("quantity_ref") or 1.0),
                radius_ref=float(size_geo.get("radius_ref") or CANONICAL_COLLISION_RADIUS),
                exponent=float(size_geo.get("exponent") or (1.0 / 3.0)),
                raw_radius=float(size_geo.get("raw_radius") or commit_radius),
                radius_min=float(size_geo.get("radius_min") or 0.08),
                radius_max=float(size_geo.get("radius_max") or CANONICAL_COLLISION_RADIUS),
                final_radius=float(size_geo.get("final_radius") or commit_radius),
                clamp_status=str(size_geo.get("clamp_status") or "SCALED_FROM_QUANTITY"),
                profile_version=str(size_geo.get("profile_version") or ""),
                valid=True,
                geometry_model=str(size_geo.get("geometry_model") or ""),
                scope_classification=str(size_geo.get("scope_classification") or "SCALED_FROM_QUANTITY"),
            )
            provenance.update(build_object_size_provenance(derivation))
            record_size_geometry_receipt(
                world,
                plan.get("config"),
                derivation,
                object_id=oid,
                transaction_id=str(plan["transaction_id"]),
                source_cell=cell,
                creation_tick=int(plan.get("tick") or 0),
                mass=float(obj_spec["mass"]),
                vertical_half_extent=commit_vhe,
                optical_radius=float(CANONICAL_OPTICAL_RADIUS),
                committed=True,
            )
        except Exception:
            provenance["size_geometry"] = dict(size_geo)
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
        collision_radius=float(commit_radius),
        vertical_half_extent=float(commit_vhe),
        material_revision=0,
        z=float(obj_spec.get("z") or 0.0),
        vz=0.0,
        grounded=True,
        creation_tick=(
            int(obj_spec["creation_tick"]) if obj_spec.get("creation_tick") is not None else None
        ),
        dynamics_eligible_tick=(
            int(obj_spec["dynamics_eligible_tick"])
            if obj_spec.get("dynamics_eligible_tick") is not None
            else None
        ),
    )
    # Patch delta provenance with real object id
    prov = dict(src_delta.provenance or {})
    prov["detached_object_id"] = oid
    prov.pop("detached_object_provisional_id", None)
    src_delta = psc.SurfaceColumnDelta(
        delta_id=src_delta.delta_id,
        cell_x=src_delta.cell_x,
        cell_y=src_delta.cell_y,
        baseline_generator_version=src_delta.baseline_generator_version,
        baseline_checksum=src_delta.baseline_checksum,
        resulting_surface_elevation=src_delta.resulting_surface_elevation,
        resulting_layers=src_delta.resulting_layers,
        created_tick=src_delta.created_tick,
        last_updated_tick=src_delta.last_updated_tick,
        revision=src_delta.revision,
        provenance=prov,
        source_transaction_ids=list(src_delta.source_transaction_ids),
    )

    receipt = _build_receipt(plan, status="COMMITTED", object_id=oid)
    # ---- atomic publish ----
    new_deltas = dict(deltas)
    new_deltas[cell] = src_delta
    world.surface_column_deltas = new_deltas
    objs = _objects_list(world)
    objs = list(objs) + [obj]
    world.resource_objects = objs

    # Same-tick newborn obstacle for later separations this tick.
    try:
        from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
            detached_terrain_material_initial_placement_is_active,
            record_same_tick_newborn_obstacle,
        )

        if detached_terrain_material_initial_placement_is_active(plan.get("config")):
            place = plan.get("placement") if isinstance(plan.get("placement"), dict) else {}
            newborn_r = float(
                obj_spec.get("collision_radius")
                if obj_spec.get("collision_radius") is not None
                else place.get("collision_radius") or CANONICAL_COLLISION_RADIUS
            )
            record_same_tick_newborn_obstacle(
                world,
                {
                    **place,
                    "tick": int(plan.get("tick") or 0),
                    "collision_radius": float(newborn_r),
                },
                oid,
            )
    except Exception:
        pass

    # Spatial index
    try:
        wmt._sync_spatial_index(world, plan)
    except Exception:
        pass
    # SES occupants on lowered cell → airborne note
    try:
        from mechanistic_mind.physical_system.surface_elevation_support import (
            surface_elevation_support_is_active,
            apply_ground_lowered_to_occupants,
        )
        cfg = plan.get("config")
        if cfg is not None and surface_elevation_support_is_active(cfg):
            elev_before = None
            try:
                elev_before = float(plan["before"]["source"]["elevation"])
            except Exception:
                elev_before = None
            apply_ground_lowered_to_occupants(
                world,
                cfg,
                cell_x=int(cell[0]),
                cell_y=int(cell[1]),
                elevation_before=elev_before,
                elevation_after=float(src_delta.resulting_surface_elevation),
                tick=plan.get("tick"),
                transaction_id=str(sid) if sid is not None else None,
                sparse_revision=None,
            )
    except Exception:
        pass

    wmt._remember(world, receipt)
    st.last_receipt = receipt
    st.history.append(receipt)
    if len(st.history) > int(st.config.history_limit):
        st.history = st.history[-int(st.config.history_limit) :]
    st.committed_ids.append(sid)
    if len(st.committed_ids) > COMMITTED_ID_LIMIT:
        st.committed_ids = st.committed_ids[-COMMITTED_ID_LIMIT:]
    st.counters["committed"] = int(st.counters.get("committed", 0)) + 1
    return {"legacy": None, "receipt": receipt, "object_id": oid}


def _build_receipt(plan: dict[str, Any], *, status: str, object_id: str | None = None) -> dict[str, Any]:
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    receipt = wmt._base_receipt(plan, status=status, reason=None if status == "COMMITTED" else str(plan.get("rejection_reason")))
    receipt.update(
        {
            "receipt_kind": RECEIPT_KIND,
            "receipt_schema": RECEIPT_SCHEMA,
            "event": EVENT_COMMITTED if status == "COMMITTED" else EVENT_REJECTED,
            "mechanism": MECHANISM_ID,
            "operation_kind": OPERATION_KIND,
            "separation_id": plan.get("separation_id"),
            "cell_x": plan.get("cell_x"),
            "cell_y": plan.get("cell_y"),
            "requested_thickness": plan.get("requested_thickness"),
            "applied_thickness": plan.get("applied_thickness"),
            "clamped": plan.get("clamped"),
            "conservation": plan.get("conservation"),
            "before": plan.get("before"),
            "after": plan.get("after"),
            "slice": plan.get("slice"),
            "object_id": object_id,
            "placement": plan.get("placement"),
            "cross_layer_policy": CROSS_LAYER_POLICY,
            "over_request_policy": OVER_REQUEST_POLICY,
            "datum_policy": DATUM_POLICY,
            "footprint_policy": FOOTPRINT_POLICY,
            "researcher_only": True,
            "agent_accessible": False,
            "agent_action": False,
            "dig_action": False,
            "semantic_label": False,
        }
    )
    return receipt


def _reject(world: Any, plan: dict[str, Any], code: str) -> dict[str, Any]:
    from mechanistic_mind.physical_system import world_material_transaction as wmt

    plan = dict(plan)
    plan["rejection_reason"] = code
    receipt = _build_receipt(plan, status="REJECTED")
    wmt._remember(world, receipt)
    st = state_of(world)
    if st is not None:
        st.last_receipt = receipt
        st.counters["rejected"] = int(st.counters.get("rejected", 0)) + 1
    return {"legacy": None, "receipt": receipt}


def apply_surface_material_separation(
    world: Any,
    config: Any,
    *,
    cell_x: int,
    cell_y: int,
    requested_thickness: float,
    tick: int = 0,
    researcher_id: str = "researcher",
    expected_revision: int | None = None,
    object_x: float | None = None,
    object_y: float | None = None,
    body_refs: list | None = None,
    acting_body_id: str | None = None,
    transmitting_object_id: str | None = None,
) -> dict[str, Any]:
    """Researcher-only: plan + WMT commit. Not an agent action."""
    from mechanistic_mind.physical_system.world_material_transaction import (
        commit_material_transaction,
    )
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        CLS_CELL_TICK_CAP_FIRST_WINS,
        cell_already_committed_this_tick,
        mark_cell_committed,
        next_attempt_seq,
        record_step as record_repeated_sep_step,
        repeated_conservative_surface_column_separation_is_active,
        FIRST_WINS_ORDER,
    )

    if repeated_conservative_surface_column_separation_is_active(config):
        attempt_seq = next_attempt_seq(world, config)
        if cell_already_committed_this_tick(
            world, config, cell_x=int(cell_x), cell_y=int(cell_y), tick=int(tick)
        ):
            receipt = {
                "status": "REJECTED",
                "rejection_reason": "CELL_TICK_CAP_FIRST_WINS",
                "cell_x": int(cell_x),
                "cell_y": int(cell_y),
                "tick": int(tick),
                "first_wins_order": FIRST_WINS_ORDER,
                "attempt_seq": int(attempt_seq),
                "researcher_only": True,
            }
            record_repeated_sep_step(
                world,
                config,
                receipt={
                    "receipt_kind": "REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION",
                    "classification": CLS_CELL_TICK_CAP_FIRST_WINS,
                    "tick": int(tick),
                    "cell_x": int(cell_x),
                    "cell_y": int(cell_y),
                    "attempt_seq": int(attempt_seq),
                    "wmt_invoked": False,
                    "researcher_only": True,
                    "agent_accessible": False,
                },
            )
            return {"legacy": None, "receipt": receipt}

    plan = plan_surface_material_separation(
        world,
        config,
        cell_x=cell_x,
        cell_y=cell_y,
        requested_thickness=requested_thickness,
        tick=tick,
        researcher_id=researcher_id,
        expected_revision=expected_revision,
        object_x=object_x,
        object_y=object_y,
        body_refs=body_refs,
        acting_body_id=acting_body_id,
        transmitting_object_id=transmitting_object_id,
    )
    out = commit_material_transaction(world, plan)
    receipt = (out or {}).get("receipt") or {}
    if (
        repeated_conservative_surface_column_separation_is_active(config)
        and str(receipt.get("status") or "") == "COMMITTED"
    ):
        mark_cell_committed(
            world,
            config,
            cell_x=int(cell_x),
            cell_y=int(cell_y),
            tick=int(tick),
            meta={
                "transaction_id": receipt.get("transaction_id"),
                "detached_object_id": receipt.get("object_id"),
                "acting_body_id": acting_body_id,
                "researcher_id": researcher_id,
            },
        )
        record_repeated_sep_step(
            world,
            config,
            receipt={
                "receipt_kind": "REPEATED_CONSERVATIVE_SURFACE_COLUMN_SEPARATION",
                "classification": "COMMITTED_SEPARATION",
                "tick": int(tick),
                "cell_x": int(cell_x),
                "cell_y": int(cell_y),
                "transaction_id": receipt.get("transaction_id"),
                "detached_object_id": receipt.get("object_id"),
                "researcher_only": True,
                "agent_accessible": False,
            },
        )
    return out


def conservative_surface_material_separation_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "label": "Conservative surface material separation",
        "enabled": bool(enabled),
        "researcher_only": True,
        "agent_action": False,
        "operation_kind": OPERATION_KIND,
        "profile_version": PROFILE_VERSION,
    }
