"""Acanthostega-only traction from a cell deposit's derived surface_affinity.

The law is continuous:

    traction_multiplier = clip(
        1 + traction_gain * (surface_affinity - 0.5),
        traction_min,
        traction_max,
    )

Neutral affinity 0.5 leaves the active locomotor Δv unchanged. The multiplier
scales only MOVE:N/S/E/W, before the existing v_max clip, inside the discrete
action request. Work accounting then sees that scaled request. WAIT, push,
contact, environmental force, and Gentle rest are not scaled.

BODY_COM_FLOOR_WRAP_V1 reads the body center at MOVE realization. A deposit
affects that cell only. last_updated_tick must be strictly earlier than the
current tick (NEXT_TICK). Same-tick deposition stays at multiplier 1.

ENERGY_INTERPRETATION is EFFECTIVE_MOTOR_COUPLING. The multiplier is a
transmission coefficient of motor effort into Δv. It is not an extra energy
source, and this module does not claim a new energy-conservation law.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any

from mechanistic_mind.physical_system.explicit_surface_deposition import (
    deposit_id_for_cell,
    ensure_surface_deposits,
)
from mechanistic_mind.physical_system.passive_material_properties import (
    DERIVATION_VERSION,
    derive_effective_properties,
)
from mechanistic_mind.planet.topology import wrap_coord

SURFACE_AFFINITY_TRACTION = "surface_affinity_traction"
FORMULA_VERSION = "SURFACE_AFFINITY_TRACTION_V1"
CELL_POLICY = "BODY_COM_FLOOR_WRAP_V1"
CAUSAL_LATENCY = "NEXT_TICK"
CAUSAL_SOURCE = "LOCAL_SURFACE_MATERIAL_PROPERTY"
ENERGY_INTERPRETATION = "EFFECTIVE_MOTOR_COUPLING"
EVENT_APPLIED = "SURFACE_TRACTION_APPLIED"

TRACTION_GAIN = 0.8
TRACTION_MIN = 0.6
TRACTION_MAX = 1.4
NEUTRAL_AFFINITY = 0.5
MOVE_COMMANDS = ("MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W")
HISTORY_LIMIT = 8


@dataclass
class SurfaceAffinityTractionConfig:
    """Fresh default OFF. A missing snapshot field stays OFF."""

    enabled: bool = False
    traction_gain: float = TRACTION_GAIN
    traction_min: float = TRACTION_MIN
    traction_max: float = TRACTION_MAX

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SurfaceAffinityTractionConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        cfg = cls(**payload)
        cfg.traction_gain = TRACTION_GAIN
        cfg.traction_min = TRACTION_MIN
        cfg.traction_max = TRACTION_MAX
        return cfg


def surface_affinity_traction_is_active(config: Any) -> bool:
    """ON only for Acanthostega with properties, deposition, and Gentle locomotion."""
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "surface_affinity_traction", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.explicit_surface_deposition import (
        explicit_surface_deposition_is_active,
    )
    from mechanistic_mind.physical_system.locomotion_profile import profile_is_active
    from mechanistic_mind.physical_system.passive_material_properties import (
        passive_material_properties_is_active,
    )

    return bool(
        passive_material_properties_is_active(config)
        and explicit_surface_deposition_is_active(config)
        and profile_is_active(config)
    )


def set_surface_affinity_traction(config: Any, enabled: bool) -> None:
    if config is None:
        return
    cfg = getattr(config, "surface_affinity_traction", None)
    if cfg is None:
        cfg = SurfaceAffinityTractionConfig()
        config.surface_affinity_traction = cfg
    acanthostega = str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cfg.enabled = bool(enabled) and acanthostega
    cfg.traction_gain = TRACTION_GAIN
    cfg.traction_min = TRACTION_MIN
    cfg.traction_max = TRACTION_MAX


def traction_multiplier(surface_affinity: float) -> float:
    """Continuous clip. Component identity is not an input."""
    raw = 1.0 + TRACTION_GAIN * (float(surface_affinity) - NEUTRAL_AFFINITY)
    if raw < TRACTION_MIN:
        return float(TRACTION_MIN)
    if raw > TRACTION_MAX:
        return float(TRACTION_MAX)
    return float(raw)


def resolve_body_com_cell(x: float, y: float, *, width: int, height: int) -> tuple[int, int]:
    """BODY_COM_FLOOR_WRAP_V1. Returns (cell_x, cell_y)."""
    cell_x = int(wrap_coord(int(math.floor(float(x))), int(width)))
    cell_y = int(wrap_coord(int(math.floor(float(y))), int(height)))
    return cell_x, cell_y


def _lineage_event_ids(provenance: Any) -> list[str]:
    if not isinstance(provenance, dict):
        return []
    refs = provenance.get("lineage_refs")
    if not isinstance(refs, list):
        return []
    out: list[str] = []
    for row in refs[-4:]:
        if isinstance(row, dict) and row.get("event_id"):
            out.append(str(row["event_id"]))
    return out


def plan_surface_traction(
    *,
    world: Any,
    x: float,
    y: float,
    tick: int,
    width: int,
    height: int,
) -> dict[str, Any]:
    """O(1) cell lookup. Does not mutate the deposit. No event when the cell is empty."""
    cell_x, cell_y = resolve_body_com_cell(x, y, width=width, height=height)
    deposit_id = deposit_id_for_cell(cell_x, cell_y)
    deposits = ensure_surface_deposits(world)
    deposit = deposits.get(deposit_id)
    base = {
        "tick": int(tick),
        "cell_x": int(cell_x),
        "cell_y": int(cell_y),
        "cell_policy": CELL_POLICY,
        "causal_latency": CAUSAL_LATENCY,
        "causal_source": CAUSAL_SOURCE,
        "formula_version": FORMULA_VERSION,
        "derivation_version": DERIVATION_VERSION,
        "traction_gain": TRACTION_GAIN,
        "traction_min": TRACTION_MIN,
        "traction_max": TRACTION_MAX,
        "energy_interpretation": ENERGY_INTERPRETATION,
        "deposit_id": "NONE",
        "emit_receipt": False,
        "deposit_eligible_this_tick": False,
        "surface_affinity": NEUTRAL_AFFINITY,
        "traction_multiplier": 1.0,
        "recipe_match": False,
        "semantic_effect": False,
        "body_effect": False,
        "material_reaction": False,
        "deposit_consumed": False,
    }
    if deposit is None:
        return base
    updated = int(deposit.last_updated_tick)
    eligible = updated < int(tick)
    derived = derive_effective_properties(deposit.composition)
    affinity = float(derived["surface_affinity"])
    multiplier = traction_multiplier(affinity) if eligible else 1.0
    base.update({
        "deposit_id": str(deposit.deposit_id),
        "emit_receipt": True,
        "deposit_created_tick": int(deposit.created_tick),
        "deposit_last_updated_tick": updated,
        "deposit_eligible_this_tick": bool(eligible),
        "surface_affinity": affinity,
        "traction_multiplier": float(multiplier),
        "deposition_event_ids": _lineage_event_ids(deposit.provenance),
        "deposit_mass": float(deposit.mass),
        "deposit_quantity": float(deposit.quantity),
    })
    return base


def traction_contrast_spawn_objects() -> list[dict[str, Any]]:
    """Two anonymous objects that differ only by primitive component.

    Quantity, mass, optical radius, interaction radius, and optical response match.
    Previous presets keep their own spawn lists.
    """
    from mechanistic_mind.physical_system.resource_objects import (
        CANONICAL_COMPONENT_AMOUNT,
        CANONICAL_FIRST_OBJECT_ID,
        CANONICAL_INTERACTION_RADIUS,
        CANONICAL_MASS,
        CANONICAL_OPTICAL_RADIUS,
        CANONICAL_OPTICAL_RESPONSE,
        CANONICAL_SECOND_OBJECT_ID,
        CANONICAL_SPAWN_X,
        CANONICAL_SPAWN_X2,
        CANONICAL_SPAWN_Y,
        CANONICAL_SPAWN_Y2,
    )

    c0, c1, c2 = CANONICAL_OPTICAL_RESPONSE
    shared = {
        "mass": CANONICAL_MASS,
        "component_amount": CANONICAL_COMPONENT_AMOUNT,
        "optical_radius": CANONICAL_OPTICAL_RADIUS,
        "interaction_radius": CANONICAL_INTERACTION_RADIUS,
        "optical_c0": c0,
        "optical_c1": c1,
        "optical_c2": c2,
    }
    return [
        {
            "object_id": CANONICAL_FIRST_OBJECT_ID,
            "x": CANONICAL_SPAWN_X,
            "y": CANONICAL_SPAWN_Y,
            "component_id": "component_a",
            **shared,
        },
        {
            "object_id": CANONICAL_SECOND_OBJECT_ID,
            "x": CANONICAL_SPAWN_X2,
            "y": CANONICAL_SPAWN_Y2,
            "component_id": "component_b",
            **shared,
        },
    ]


def surface_affinity_traction_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": SURFACE_AFFINITY_TRACTION,
        "config_path": "surface_affinity_traction.enabled",
        "label": "SURFACE AFFINITY TRACTION",
        "description": (
            "Acanthostega-only continuous traction from a cell deposit's "
            "derived surface_affinity. Scales active MOVE before v_max. "
            "Researcher-only. Not agent-accessible. Continuous physical law. "
            "Not a recipe."
        ),
        "validation": "Acanthostega Phase A Surface Traction.",
        "provenance": "acanthostega_surface_affinity_traction",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "PHYSICAL",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "dependencies": [
            "passive_material_properties",
            "explicit_surface_deposition",
            "gentle_terrain_locomotion",
        ],
        "toggle_policy": "RESET_RECOMMENDED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key means traction OFF",
        "live_state_available": True,
        "receipts_available": True,
        "events_available": True,
        "formula_version": FORMULA_VERSION,
        "energy_interpretation": ENERGY_INTERPRETATION,
        "causal_latency": CAUSAL_LATENCY,
        "cell_policy": CELL_POLICY,
    }
