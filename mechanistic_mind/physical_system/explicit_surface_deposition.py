"""Acanthostega-only explicit transfer from a LEFT-held object onto one terrain cell.

Tick order inside the shared manipulator resolution:
GRASP / RELEASE → pair action / COMBINE → held-object kinematics → APPLY_TO_SURFACE.

SOURCE_MANIPULATOR is LEFT. The command is not an alias of RELEASE, COMBINE,
PUSH, locomotion, or WAIT. The resolved cell is the wrapped floor of the LEFT
effector pose (WORLD_XY_FLOOR_WRAP_V1), the same floor-and-wrap used for body
cells. The researcher probe sends only the motor command.

DEPOSITION_WORK_ACCOUNTING is NOT_IMPLEMENTED. The shared work reservoir debits
a partial amount and still completes other motor commands. Using that seam here
would either invent a debit or leave a partial deposit. This slice therefore
records no work number and never emits DEPOSITION_INSUFFICIENT_WORK.

Deposits do not change drag, traction, traversability, body state, vision, or
other objects.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any

from mechanistic_mind.physical_system.passive_material_properties import (
    DERIVATION_VERSION,
    derive_effective_properties,
    primitive_coefficient_reference,
)
from mechanistic_mind.physical_system.resource_objects import (
    PHYSICAL_STATE_HELD,
    MaterialComponent,
    objects_is_active,
)
from mechanistic_mind.planet.topology import wrap_coord

EXPLICIT_SURFACE_DEPOSITION = "explicit_surface_deposition"
APPLY_TO_SURFACE = "APPLY_TO_SURFACE"
SOURCE_MANIPULATOR = "LEFT"
CANONICAL_DEPOSIT_AMOUNT = 0.10
QUANTITY_EPSILON = 1e-9
CONSERVATION_TOLERANCE = 1e-9
CELL_POLICY = "WORLD_XY_FLOOR_WRAP_V1"
CAUSAL_REASON = "EXPLICIT_MOTOR_COMMAND"
DEPOSITION_WORK_ACCOUNTING = "NOT_IMPLEMENTED"
SOURCE_DEPLETED = "SOURCE_DEPLETED"

EVENT_COMMITTED = "SURFACE_DEPOSITION_COMMITTED"
EVENT_REJECTED = "SURFACE_DEPOSITION_REJECTED"

OUTCOME_UNAVAILABLE = "DEPOSITION_UNAVAILABLE"
OUTCOME_NO_LEFT = "DEPOSITION_NO_LEFT_HELD_OBJECT"
OUTCOME_NOT_HELD_AT_START = "DEPOSITION_SOURCE_NOT_HELD_AT_TICK_START"
OUTCOME_EMPTY = "DEPOSITION_EMPTY_SOURCE"
OUTCOME_INVALID = "DEPOSITION_INVALID_SOURCE"
OUTCOME_INSUFFICIENT_WORK = "DEPOSITION_INSUFFICIENT_WORK"
OUTCOME_COMMITTED = "DEPOSITION_COMMITTED"

REJECTION_OUTCOMES = (
    OUTCOME_UNAVAILABLE,
    OUTCOME_NO_LEFT,
    OUTCOME_NOT_HELD_AT_START,
    OUTCOME_EMPTY,
    OUTCOME_INVALID,
    OUTCOME_INSUFFICIENT_WORK,
)


@dataclass
class ExplicitSurfaceDepositionConfig:
    """Fresh default OFF. Missing snapshot field preserves legacy behavior."""

    enabled: bool = False
    canonical_deposit_amount: float = CANONICAL_DEPOSIT_AMOUNT
    quantity_epsilon: float = QUANTITY_EPSILON
    conservation_tolerance: float = CONSERVATION_TOLERANCE

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ExplicitSurfaceDepositionConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        cfg = cls(**payload)
        cfg.canonical_deposit_amount = CANONICAL_DEPOSIT_AMOUNT
        cfg.quantity_epsilon = QUANTITY_EPSILON
        cfg.conservation_tolerance = CONSERVATION_TOLERANCE
        return cfg


def explicit_surface_deposition_is_active(config: Any) -> bool:
    """ON only for Acanthostega with passive properties and resource objects."""
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "explicit_surface_deposition", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.passive_material_properties import (
        passive_material_properties_is_active,
    )

    return bool(passive_material_properties_is_active(config) and objects_is_active(config))


def set_explicit_surface_deposition(config: Any, enabled: bool) -> None:
    if config is None:
        return
    cfg = getattr(config, "explicit_surface_deposition", None)
    if cfg is None:
        cfg = ExplicitSurfaceDepositionConfig()
        config.explicit_surface_deposition = cfg
    acanthostega = str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cfg.enabled = bool(enabled) and acanthostega
    cfg.canonical_deposit_amount = CANONICAL_DEPOSIT_AMOUNT
    cfg.quantity_epsilon = QUANTITY_EPSILON
    cfg.conservation_tolerance = CONSERVATION_TOLERANCE


@dataclass
class SurfaceMaterialDeposit:
    """One canonical aggregate per wrapped terrain cell. Not a ResourceObject."""

    deposit_id: str
    cell_x: int
    cell_y: int
    mass: float
    quantity: float
    composition: tuple[MaterialComponent, ...]
    provenance: dict[str, Any]
    created_tick: int
    last_updated_tick: int
    optical_response: tuple[float, float, float] | None = None
    optical_source_event_ids: tuple[str, ...] = ()
    optical_derivation_version: str | None = None
    material_revision: int = 0

    def copy(self) -> "SurfaceMaterialDeposit":
        return SurfaceMaterialDeposit.from_dict(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        return {
            "deposit_id": str(self.deposit_id),
            "cell_x": int(self.cell_x),
            "cell_y": int(self.cell_y),
            "mass": float(self.mass),
            "quantity": float(self.quantity),
            "composition": [c.to_dict() for c in self.composition],
            "provenance": _flat_provenance(self.provenance),
            "created_tick": int(self.created_tick),
            "last_updated_tick": int(self.last_updated_tick),
            **({} if self.optical_response is None else {
                "optical_response": {
                    "c0": float(self.optical_response[0]),
                    "c1": float(self.optical_response[1]),
                    "c2": float(self.optical_response[2]),
                },
                "optical_source_event_ids": list(self.optical_source_event_ids or ())[:4],
                "optical_derivation_version": self.optical_derivation_version,
            }),
            **({} if int(getattr(self, "material_revision", 0) or 0) == 0 else {
                "material_revision": int(self.material_revision),
            }),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SurfaceMaterialDeposit":
        d = dict(data or {})
        comps = []
        for item in d.get("composition") or []:
            if isinstance(item, dict):
                comps.append(MaterialComponent.from_dict(item))
            elif isinstance(item, MaterialComponent):
                comps.append(MaterialComponent(item.component_id, float(item.amount)))
        return cls(
            deposit_id=str(d.get("deposit_id") or ""),
            cell_x=int(d.get("cell_x") or 0),
            cell_y=int(d.get("cell_y") or 0),
            mass=float(d.get("mass") or 0.0),
            quantity=float(d.get("quantity") or 0.0),
            composition=tuple(comps),
            provenance=_flat_provenance(d.get("provenance")),
            created_tick=int(d.get("created_tick") or 0),
            last_updated_tick=int(d.get("last_updated_tick") or 0),
            optical_response=_optional_optical(d.get("optical_response")),
            optical_source_event_ids=tuple(
                str(item) for item in (d.get("optical_source_event_ids") or []) if item
            )[:4],
            optical_derivation_version=(
                str(d["optical_derivation_version"]) if d.get("optical_derivation_version") else None
            ),
            material_revision=int(d.get("material_revision") or 0),
        )


def _optional_optical(raw: Any) -> tuple[float, float, float] | None:
    if raw is None:
        return None
    from mechanistic_mind.physical_system.resource_objects import clip_optical_triplet

    return clip_optical_triplet(raw)


def deposit_id_for_cell(cell_x: int, cell_y: int) -> str:
    return f"surface-deposit-x{int(cell_x)}-y{int(cell_y)}"


def resolve_deposit_cell(ex: float, ey: float, *, width: int, height: int) -> tuple[int, int]:
    """WORLD_XY_FLOOR_WRAP_V1. Returns (cell_x, cell_y)."""
    cell_x = int(wrap_coord(int(math.floor(float(ex))), int(width)))
    cell_y = int(wrap_coord(int(math.floor(float(ey))), int(height)))
    return cell_x, cell_y


def ensure_surface_deposits(planet: Any) -> dict[str, SurfaceMaterialDeposit]:
    raw = getattr(planet, "surface_material_deposits", None)
    if isinstance(raw, dict):
        return raw
    planet.surface_material_deposits = {}
    return planet.surface_material_deposits


def surface_deposits_copy(planet: Any) -> dict[str, SurfaceMaterialDeposit]:
    return {key: value.copy() for key, value in ensure_surface_deposits(planet).items()}


def serialize_surface_deposits(planet: Any) -> dict[str, Any] | None:
    deposits = ensure_surface_deposits(planet)
    if not deposits:
        return None
    rows = [deposits[key].to_dict() for key in sorted(deposits)]
    return {"deposits": rows}


def restore_surface_deposits(planet: Any, payload: Any) -> None:
    planet.surface_material_deposits = {}
    if not payload:
        return
    rows = payload.get("deposits") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        deposit = SurfaceMaterialDeposit.from_dict(row)
        if not deposit.deposit_id:
            continue
        planet.surface_material_deposits[str(deposit.deposit_id)] = deposit


def _flat_provenance(raw: Any) -> dict[str, Any]:
    data = dict(raw or {}) if isinstance(raw, dict) else {}
    refs = []
    for row in list(data.get("lineage_refs") or []):
        if isinstance(row, dict):
            refs.append({
                "event_id": row.get("event_id"),
                "tick": row.get("tick"),
                "body_id": row.get("body_id"),
                "command": row.get("command"),
                "source_object_id": row.get("source_object_id"),
                "source_transformation_id": row.get("source_transformation_id"),
                "cell_x": row.get("cell_x"),
                "cell_y": row.get("cell_y"),
                "mass": row.get("mass"),
                "quantity": row.get("quantity"),
                "components": list(row.get("components") or []),
            })
    return {"lineage_refs": refs}


def _material_view(obj: Any) -> dict[str, Any]:
    return {
        "object_id": str(obj.object_id),
        "mass": float(obj.mass),
        "quantity": float(obj.quantity),
        "composition": [c.to_dict() for c in obj.composition],
        "physical_state": str(obj.physical_state),
        "manipulator_id": obj.manipulator_id,
    }


def _deposit_view(deposit: SurfaceMaterialDeposit | None) -> dict[str, Any] | None:
    if deposit is None:
        return None
    view = deposit.to_dict()
    derived = derive_effective_properties(deposit.composition)
    view["effective_properties"] = {
        "compliance": derived["compliance"],
        "surface_affinity": derived["surface_affinity"],
        "derivation_version": DERIVATION_VERSION,
    }
    return view


def _components_from_totals(totals: dict[str, float]) -> tuple[MaterialComponent, ...]:
    return tuple(
        MaterialComponent(cid, float(amount))
        for cid, amount in sorted(totals.items())
        if float(amount) > QUANTITY_EPSILON
    )


def _proportion(transferred: float, totals: dict[str, float]) -> dict[str, float]:
    ids = [cid for cid, amount in sorted(totals.items()) if amount > QUANTITY_EPSILON]
    total = math.fsum(totals[cid] for cid in ids)
    if not ids or total <= QUANTITY_EPSILON:
        raise ValueError("empty composition")
    out: dict[str, float] = {}
    consumed = 0.0
    for index, cid in enumerate(ids):
        if index == len(ids) - 1:
            part = float(transferred) - consumed
        else:
            part = float(transferred) * float(totals[cid]) / total
            consumed += part
        if not math.isfinite(part) or part < -CONSERVATION_TOLERANCE:
            raise ValueError("non-finite component transfer")
        out[cid] = max(0.0, part)
    return out


def _reject(base: dict[str, Any], outcome: str) -> dict[str, Any]:
    return {
        **base,
        "event": EVENT_REJECTED,
        "outcome": outcome,
        "committed": False,
        "deposition_work_accounting": DEPOSITION_WORK_ACCOUNTING,
        "work_debit": None,
        "terrain_effects_applied": False,
        "body_effects_applied": False,
        "traversal_effects_applied": False,
        "material_reactions_applied": False,
        "semantic_effects": False,
    }


def apply_explicit_surface_deposition(
    *,
    world: Any,
    config: Any,
    body: Any,
    body_id: str,
    command_requested: bool,
    held_object_id_at_tick_start: str | None,
    tick: int,
    runtime: Any = None,
) -> dict[str, Any] | None:
    """Atomically deposit from the LEFT-held source. None when the command is absent."""
    if not command_requested:
        return None
    from mechanistic_mind.physical_system.physical_manipulator import (
        MANIP_LEFT,
        effector_world_xy,
        held_object_for_holder,
    )

    base = {
        "tick": int(tick),
        "body_id": str(body_id),
        "motor_command": APPLY_TO_SURFACE,
        "source_manipulator": SOURCE_MANIPULATOR,
        "causal_reason": CAUSAL_REASON,
        "source_held_at_tick_start": bool(held_object_id_at_tick_start),
        "researcher_only": True,
        "agent_accessible": False,
    }
    if not explicit_surface_deposition_is_active(config):
        return _reject(base, OUTCOME_UNAVAILABLE)

    source = held_object_for_holder(world, body_id, MANIP_LEFT)
    if source is None or str(source.physical_state) != PHYSICAL_STATE_HELD:
        return _reject(base, OUTCOME_NO_LEFT)
    if held_object_id_at_tick_start is None or str(source.object_id) != str(held_object_id_at_tick_start):
        return _reject(base, OUTCOME_NOT_HELD_AT_START)

    try:
        quantity_before = float(source.quantity)
        mass_before = float(source.mass)
        if (
            not math.isfinite(quantity_before)
            or not math.isfinite(mass_before)
            or quantity_before < 0.0
            or mass_before < 0.0
        ):
            raise ValueError("non-finite source")
        from mechanistic_mind.physical_system.passive_material_properties import canonical_amount_totals

        totals = canonical_amount_totals(source.composition)
        component_total = math.fsum(totals.values()) if totals else 0.0
        if not math.isfinite(component_total) or component_total < 0.0:
            raise ValueError("invalid composition")
    except (TypeError, ValueError):
        return _reject(base, OUTCOME_INVALID)

    if quantity_before <= QUANTITY_EPSILON:
        return _reject(base, OUTCOME_EMPTY)
    if component_total <= QUANTITY_EPSILON:
        return _reject(base, OUTCOME_INVALID)

    t = getattr(world, "T", None)
    height = int(t.shape[0]) if t is not None else 32
    width = int(t.shape[1]) if t is not None else 32
    ex, ey = effector_world_xy(
        body, width=width, height=height, config=config, manipulator_id=MANIP_LEFT, runtime=runtime,
    )
    cell_x, cell_y = resolve_deposit_cell(ex, ey, width=width, height=height)
    nominal = min(CANONICAL_DEPOSIT_AMOUNT, quantity_before)
    depleted = (quantity_before - nominal) <= QUANTITY_EPSILON
    transferred = quantity_before if depleted else nominal
    try:
        if depleted:
            component_delta = {cid: float(amount) for cid, amount in totals.items()}
            mass_transfer = mass_before
        else:
            component_delta = _proportion(transferred, totals)
            mass_transfer = mass_before * transferred / quantity_before
        if not math.isfinite(mass_transfer) or mass_transfer < -CONSERVATION_TOLERANCE:
            raise ValueError("invalid mass transfer")
        mass_transfer = max(0.0, float(mass_transfer))
    except (TypeError, ValueError):
        return _reject(base, OUTCOME_INVALID)

    deposits = ensure_surface_deposits(world)
    deposit_id = deposit_id_for_cell(cell_x, cell_y)
    existing = deposits.get(deposit_id)
    before_source = _material_view(source)
    before_deposit = _deposit_view(existing)
    source_transformation_id = None
    provenance = getattr(source, "provenance", None) or {}
    if isinstance(provenance, dict):
        source_transformation_id = provenance.get("last_transformation_id")

    new_totals = {cid: float(amount) for cid, amount in totals.items()}
    for cid, delta in component_delta.items():
        new_totals[cid] = float(new_totals.get(cid, 0.0)) - float(delta)
    source_after_mass = 0.0 if depleted else mass_before - mass_transfer
    source_after_quantity = 0.0 if depleted else quantity_before - transferred
    source_components = () if depleted else _components_from_totals(new_totals)

    old_totals: dict[str, float] = {}
    if existing is not None:
        from mechanistic_mind.physical_system.passive_material_properties import canonical_amount_totals

        old_totals = canonical_amount_totals(existing.composition)
    merged_totals = dict(old_totals)
    for cid, delta in component_delta.items():
        merged_totals[cid] = float(merged_totals.get(cid, 0.0)) + float(delta)
    deposit_components = _components_from_totals(merged_totals)
    deposit_mass = (0.0 if existing is None else float(existing.mass)) + mass_transfer
    deposit_quantity = (0.0 if existing is None else float(existing.quantity)) + transferred

    mass_residual = (source_after_mass + mass_transfer) - mass_before
    quantity_residual = (source_after_quantity + transferred) - quantity_before
    component_residuals = {
        cid: (float(new_totals.get(cid, 0.0)) + float(component_delta.get(cid, 0.0))) - float(totals.get(cid, 0.0))
        for cid in sorted(set(totals) | set(component_delta) | set(new_totals))
    }
    deposit_mass_residual = deposit_mass - ((0.0 if existing is None else float(existing.mass)) + mass_transfer)
    deposit_quantity_residual = deposit_quantity - (
        (0.0 if existing is None else float(existing.quantity)) + transferred
    )
    if (
        abs(mass_residual) > CONSERVATION_TOLERANCE
        or abs(quantity_residual) > CONSERVATION_TOLERANCE
        or abs(deposit_mass_residual) > CONSERVATION_TOLERANCE
        or abs(deposit_quantity_residual) > CONSERVATION_TOLERANCE
        or any(abs(value) > CONSERVATION_TOLERANCE for value in component_residuals.values())
        or not math.isfinite(source_after_mass)
        or not math.isfinite(deposit_mass)
    ):
        return _reject(base, OUTCOME_INVALID)

    event_id = f"surface-deposition-{int(tick):09d}-{body_id}-x{cell_x}-y{cell_y}"
    lineage_row = {
        "event_id": event_id,
        "tick": int(tick),
        "body_id": str(body_id),
        "command": APPLY_TO_SURFACE,
        "source_object_id": str(source.object_id),
        "source_transformation_id": source_transformation_id,
        "cell_x": int(cell_x),
        "cell_y": int(cell_y),
        "mass": float(mass_transfer),
        "quantity": float(transferred),
        "components": [
            {"component_id": cid, "amount": float(component_delta[cid])}
            for cid in sorted(component_delta)
        ],
    }
    prior_refs = list((_flat_provenance(existing.provenance).get("lineage_refs") if existing else []) or [])
    next_provenance = {"lineage_refs": prior_refs + [lineage_row]}
    created_tick = int(existing.created_tick) if existing is not None else int(tick)
    updated = SurfaceMaterialDeposit(
        deposit_id=deposit_id,
        cell_x=int(cell_x),
        cell_y=int(cell_y),
        mass=float(deposit_mass),
        quantity=float(deposit_quantity),
        composition=deposit_components,
        provenance=next_provenance,
        created_tick=created_tick,
        last_updated_tick=int(tick),
    )
    from mechanistic_mind.physical_system.physical_surface_optical_coating import (
        transfer_optical_on_deposition,
    )
    transfer_optical_on_deposition(
        config, world, updated, existing, source, float(transferred), event_id,
    )

    source_id = str(source.object_id)
    if depleted:
        world.resource_objects = [
            obj for obj in (getattr(world, "resource_objects", None) or []) if obj is not source
        ]
        source_after: Any = SOURCE_DEPLETED
        source_properties = None
    else:
        source.mass = float(source_after_mass)
        source.quantity = float(source_after_quantity)
        source.composition = source_components
        source.physical_state = PHYSICAL_STATE_HELD
        source.holder_body_id = str(body_id)
        source.manipulator_id = MANIP_LEFT
        source_after = _material_view(source)
        derived_source = derive_effective_properties(source.composition)
        source_properties = {
            "compliance": derived_source["compliance"],
            "surface_affinity": derived_source["surface_affinity"],
            "derivation_version": DERIVATION_VERSION,
            "property_derivation_verified": derived_source["property_derivation_verified"],
        }
    deposits[deposit_id] = updated
    derived_deposit = derive_effective_properties(updated.composition)
    return {
        **base,
        "event": EVENT_COMMITTED,
        "outcome": OUTCOME_COMMITTED,
        "committed": True,
        "event_id": event_id,
        "source_object_id": source_id,
        "deposit_id": deposit_id,
        "resolved_cell": {"cell_x": int(cell_x), "cell_y": int(cell_y), "policy": CELL_POLICY},
        "effector_xy": [float(ex), float(ey)],
        "source_state_before": before_source,
        "source_state_after": source_after,
        "deposit_state_before": before_deposit,
        "deposited_delta": {
            "mass": float(mass_transfer),
            "quantity": float(transferred),
            "components": lineage_row["components"],
            "primitive_coefficient_references": [
                primitive_coefficient_reference(cid) for cid in sorted(component_delta)
            ],
        },
        "deposit_state_after": _deposit_view(updated),
        "mass_residual": float(mass_residual),
        "quantity_residual": float(quantity_residual),
        "component_residuals": component_residuals,
        "deposit_mass_residual": float(deposit_mass_residual),
        "deposit_quantity_residual": float(deposit_quantity_residual),
        "derivation_version": DERIVATION_VERSION,
        "deposit_properties_after": {
            "compliance": derived_deposit["compliance"],
            "surface_affinity": derived_deposit["surface_affinity"],
            "property_derivation_verified": derived_deposit["property_derivation_verified"],
        },
        "source_properties_after": source_properties,
        "source_removed": bool(depleted),
        "left_hand_freed": bool(depleted),
        "deposit_created": existing is None,
        "deposit_updated": existing is not None,
        "source_transformation_id": source_transformation_id,
        "deposition_work_accounting": DEPOSITION_WORK_ACCOUNTING,
        "work_debit": None,
        "terrain_effects_applied": False,
        "body_effects_applied": False,
        "traversal_effects_applied": False,
        "material_reactions_applied": False,
        "semantic_effects": False,
    }


def command_requested_from_motor(motor: Any) -> bool:
    if motor is None:
        return False
    if isinstance(motor, dict):
        if bool(motor.get("apply_to_surface")):
            return True
        token = str(motor.get("legacy_token") or motor.get("display") or "")
        return token == APPLY_TO_SURFACE or token.endswith(APPLY_TO_SURFACE)
    return bool(getattr(motor, "apply_to_surface", False))


def explicit_surface_deposition_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": EXPLICIT_SURFACE_DEPOSITION,
        "config_path": "explicit_surface_deposition.enabled",
        "label": "EXPLICIT SURFACE DEPOSITION",
        "description": (
            "Acanthostega-only APPLY_TO_SURFACE moves a bounded portion of the "
            "LEFT-held object onto one wrapped terrain cell. No terrain, body, "
            "or material consequence."
        ),
        "validation": "Acanthostega Phase A Surface Deposition.",
        "provenance": "acanthostega_explicit_surface_deposition",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "PHYSICAL",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "dependencies": ["physical_resource_objects", "passive_material_properties"],
        "toggle_policy": "RESET_RECOMMENDED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key means deposition OFF and no deposits",
        "live_state_available": True,
        "receipts_available": True,
        "events_available": True,
        "terrain_consequence": "NOT_IMPLEMENTED",
        "deposition_work_accounting": DEPOSITION_WORK_ACCOUNTING,
    }


def researcher_deposit_readout(deposit: SurfaceMaterialDeposit | dict[str, Any]) -> dict[str, Any]:
    raw = deposit.to_dict() if isinstance(deposit, SurfaceMaterialDeposit) else dict(deposit)
    derived = derive_effective_properties(raw.get("composition"))
    return {
        **raw,
        "compliance": derived["compliance"],
        "surface_affinity": derived["surface_affinity"],
        "derivation_version": DERIVATION_VERSION,
        "access": "researcher-only",
        "status": "no terrain consequence yet",
        "researcher_only": True,
        "agent_accessible": False,
        "not_agent_accessible": True,
        "terrain_effects_applied": False,
        "optical_effect_applied": False,
    }
