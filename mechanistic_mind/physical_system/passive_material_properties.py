"""Acanthostega-only passive material coefficients.

Primitive coefficients live in a versioned registry. Effective properties are
derived from composition and are not a stored substance. This slice does not
apply the coefficients to motion, contact, terrain, energy, vision, cognition,
mixing, or any other world process.

Unknown component IDs use NEUTRAL_MIDPOINT_V1 (compliance=0.5,
surface_affinity=0.5). The values are literals, not Python hash().
Empty or zero-total composition uses ZERO_VECTOR_V1 (0.0, 0.0) so the
weighted mean never divides by zero.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, fields
from typing import Any

PASSIVE_MATERIAL_PROPERTIES = "passive_material_properties"
REGISTRY_VERSION = "PRIMITIVE_COEFFICIENTS_V1"
DERIVATION_VERSION = "COMPOSITION_WEIGHTED_MEAN_V1"
UNKNOWN_COMPONENT_POLICY = "NEUTRAL_MIDPOINT_V1"
EMPTY_COMPOSITION_POLICY = "ZERO_VECTOR_V1"
DERIVATION_TOLERANCE = 1e-12

PROPERTY_NAMES = ("compliance", "surface_affinity")

# Canonical component_0 is the existing first-object component: neutral midpoint.
# component_a / component_b are anonymous primitives used by composition tests.
# These are coefficients, not item classes and not effects.
PRIMITIVE_COEFFICIENTS_V1: dict[str, dict[str, float]] = {
    "component_0": {"compliance": 0.5, "surface_affinity": 0.5},
    "component_a": {"compliance": 0.25, "surface_affinity": 0.75},
    "component_b": {"compliance": 0.75, "surface_affinity": 0.25},
}
UNKNOWN_COEFFICIENTS = {"compliance": 0.5, "surface_affinity": 0.5}

# Structural separation work per quantity (thickness at CELL_AREA=1).
# NOT clipped to [0,1] — absolute work units calibrated to actuator W_max≈0.00195.
# Soft (b): ~1 full-block tick → ~0.25 thickness; mid (0): ~2 ticks; hard (a): ~8 ticks.
# Spec: SEPARATION_WORK_PER_QUANTITY_V1 — STRUCTURAL MATERIAL PROPERTY.
SEPARATION_WORK_REGISTRY_VERSION = "SEPARATION_WORK_PER_QUANTITY_V1"
SEPARATION_WORK_PER_QUANTITY_V1: dict[str, float] = {
    "component_0": 0.015636363636363637,  # 2 * (W_max/0.25)
    "component_a": 0.06254545454545454,   # 8 * (W_max/0.25)
    "component_b": 0.007818181818181818,  # 1 * (W_max/0.25)
}
UNKNOWN_SEPARATION_WORK_PER_QUANTITY = 0.015636363636363637  # mid / unknown



@dataclass
class PassiveMaterialPropertiesConfig:
    """Fresh default OFF. Missing snapshot field preserves legacy behavior."""

    enabled: bool = False
    registry_version: str = REGISTRY_VERSION
    derivation_version: str = DERIVATION_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PassiveMaterialPropertiesConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        cfg = cls(**payload)
        if str(cfg.registry_version) != REGISTRY_VERSION:
            cfg.registry_version = REGISTRY_VERSION
        if str(cfg.derivation_version) != DERIVATION_VERSION:
            cfg.derivation_version = DERIVATION_VERSION
        return cfg


def passive_material_properties_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "passive_material_properties", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_passive_material_properties(config: Any, enabled: bool) -> None:
    if config is None:
        return
    cfg = getattr(config, "passive_material_properties", None)
    if cfg is None:
        cfg = PassiveMaterialPropertiesConfig()
        config.passive_material_properties = cfg
    acanthostega = str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cfg.enabled = bool(enabled) and acanthostega
    cfg.registry_version = REGISTRY_VERSION
    cfg.derivation_version = DERIVATION_VERSION


def primitive_coefficient_reference(component_id: str) -> dict[str, Any]:
    """Stable registry lookup. Unknown ids share one documented fallback."""
    cid = str(component_id)
    known = PRIMITIVE_COEFFICIENTS_V1.get(cid)
    if known is not None:
        return {
            "component_id": cid,
            "compliance": float(known["compliance"]),
            "surface_affinity": float(known["surface_affinity"]),
            "source": "REGISTRY",
            "registry_version": REGISTRY_VERSION,
        }
    return {
        "component_id": cid,
        "compliance": float(UNKNOWN_COEFFICIENTS["compliance"]),
        "surface_affinity": float(UNKNOWN_COEFFICIENTS["surface_affinity"]),
        "source": "FALLBACK",
        "fallback_policy": UNKNOWN_COMPONENT_POLICY,
        "registry_version": REGISTRY_VERSION,
    }


def _component_rows(composition: Any) -> list[tuple[str, float]]:
    rows: list[tuple[str, float]] = []
    if composition is None:
        return rows
    if isinstance(composition, dict):
        items = [{"component_id": k, "amount": v} for k, v in composition.items()]
    else:
        items = list(composition)
    for item in items:
        if isinstance(item, dict):
            cid = str(item.get("component_id") or "")
            raw = item.get("amount")
        else:
            cid = str(getattr(item, "component_id", "") or "")
            raw = getattr(item, "amount", None)
        if not cid:
            raise ValueError("missing component id")
        amount = float(raw)
        if not math.isfinite(amount) or amount < 0.0:
            raise ValueError("invalid component amount")
        rows.append((cid, amount))
    return rows


def canonical_amount_totals(composition: Any) -> dict[str, float]:
    """Sum duplicate component ids. Key order does not affect later means."""
    buckets: dict[str, list[float]] = {}
    for cid, amount in _component_rows(composition):
        buckets.setdefault(cid, []).append(amount)
    return {cid: float(math.fsum(buckets[cid])) for cid in sorted(buckets) if math.fsum(buckets[cid]) > 0.0}


def _clip01(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return float(max(0.0, min(1.0, value)))


def derive_effective_properties(composition: Any) -> dict[str, Any]:
    """Quantity-weighted mean of primitive coefficients.

    effective = clip(Σ(amount × coefficient) / Σ(amount), 0, 1)
    Mass is not an input. Optical response and interaction radius are not inputs.
    """
    base = {
        "compliance": 0.0,
        "surface_affinity": 0.0,
        "derivation": DERIVATION_VERSION,
        "derivation_version": DERIVATION_VERSION,
        "registry_version": REGISTRY_VERSION,
        "empty_composition": False,
        "property_derivation_verified": False,
        "property_derivation_residuals": {"compliance": 0.0, "surface_affinity": 0.0},
        "primitive_coefficient_references": [],
        "canonical_amounts": {},
    }
    try:
        totals = canonical_amount_totals(composition)
    except (TypeError, ValueError):
        return base
    total = float(math.fsum(totals.values())) if totals else 0.0
    if not totals or total <= 0.0 or not math.isfinite(total):
        return {
            **base,
            "empty_composition": True,
            "empty_policy": EMPTY_COMPOSITION_POLICY,
            "property_derivation_verified": True,
        }
    refs: list[dict[str, Any]] = []
    num = {name: [] for name in PROPERTY_NAMES}
    den: list[float] = []
    for cid, amount in totals.items():
        ref = primitive_coefficient_reference(cid)
        ref = {**ref, "amount": float(amount)}
        refs.append(ref)
        den.append(float(amount))
        for name in PROPERTY_NAMES:
            num[name].append(float(amount) * float(ref[name]))
    denom = float(math.fsum(den))
    residuals: dict[str, float] = {}
    values: dict[str, float] = {}
    verified = math.isfinite(denom) and denom > 0.0
    for name in PROPERTY_NAMES:
        raw = float(math.fsum(num[name])) / denom if verified else 0.0
        clipped = _clip01(raw)
        residual = float(clipped - raw) if math.isfinite(raw) else 0.0
        residuals[name] = residual
        values[name] = clipped
        if not math.isfinite(raw) or not math.isfinite(clipped) or abs(residual) > DERIVATION_TOLERANCE:
            verified = False
        if not (0.0 <= clipped <= 1.0):
            verified = False
    return {
        **base,
        **values,
        "property_derivation_verified": bool(verified),
        "property_derivation_residuals": residuals,
        "primitive_coefficient_references": refs,
        "canonical_amounts": {k: float(v) for k, v in totals.items()},
    }


def researcher_property_readout(composition: Any) -> dict[str, Any]:
    """Observer overlay. Not copied into agent observation."""
    report = derive_effective_properties(composition)
    sep = derive_separation_work_per_quantity(composition)
    return {
        "compliance": float(report["compliance"]),
        "surface_affinity": float(report["surface_affinity"]),
        "separation_work_per_quantity": float(sep["separation_work_per_quantity"]),
        "derivation": DERIVATION_VERSION,
        "derivation_version": DERIVATION_VERSION,
        "registry_version": REGISTRY_VERSION,
        "separation_work_registry_version": SEPARATION_WORK_REGISTRY_VERSION,
        "property_derivation_verified": bool(report["property_derivation_verified"]),
        "property_derivation_residuals": dict(report["property_derivation_residuals"]),
        "primitive_coefficient_references": list(report["primitive_coefficient_references"]),
        "researcher_only": True,
        "agent_accessible": False,
        "not_agent_accessible": True,
        "access": "researcher-only",
        "passive": True,
        "consequence_kernel": False,
        "status": "passive — no consequence kernel",
        "passive_properties_only": True,
        "world_effects_applied": False,
        "body_effects_applied": False,
        "material_interactions_applied": False,
        "semantic_effects": False,
    }


def derive_separation_work_per_quantity(composition: Any) -> dict[str, Any]:
    """Composition-weighted mean of structural separation work per quantity.

    Not clipped to [0,1]. Dimensions: simulation work units / quantity
    (quantity ≡ thickness at CELL_AREA=1). STRUCTURAL MATERIAL PROPERTY.
    Independent of surface_affinity / compliance reinterpretation.
    """
    base = {
        "separation_work_per_quantity": float(UNKNOWN_SEPARATION_WORK_PER_QUANTITY),
        "derivation": DERIVATION_VERSION,
        "registry_version": SEPARATION_WORK_REGISTRY_VERSION,
        "empty_composition": False,
        "property_derivation_verified": False,
        "canonical_amounts": {},
        "primitive_separation_references": [],
        "researcher_only": True,
        "agent_accessible": False,
    }
    try:
        totals = canonical_amount_totals(composition)
    except (TypeError, ValueError):
        return base
    total = float(math.fsum(totals.values())) if totals else 0.0
    if not totals or total <= 0.0 or not math.isfinite(total):
        return {
            **base,
            "separation_work_per_quantity": 0.0,
            "empty_composition": True,
            "empty_policy": EMPTY_COMPOSITION_POLICY,
            "property_derivation_verified": True,
        }
    refs: list[dict[str, Any]] = []
    num: list[float] = []
    den: list[float] = []
    for cid, amount in totals.items():
        w = float(
            SEPARATION_WORK_PER_QUANTITY_V1.get(cid, UNKNOWN_SEPARATION_WORK_PER_QUANTITY)
        )
        known = cid in SEPARATION_WORK_PER_QUANTITY_V1
        refs.append(
            {
                "component_id": cid,
                "amount": float(amount),
                "separation_work_per_quantity": w,
                "source": "REGISTRY" if known else "FALLBACK",
            }
        )
        num.append(float(amount) * w)
        den.append(float(amount))
    denom = float(math.fsum(den))
    verified = math.isfinite(denom) and denom > 0.0
    raw = float(math.fsum(num)) / denom if verified else float(UNKNOWN_SEPARATION_WORK_PER_QUANTITY)
    if not math.isfinite(raw) or raw < 0.0:
        verified = False
        raw = float(UNKNOWN_SEPARATION_WORK_PER_QUANTITY)
    return {
        **base,
        "separation_work_per_quantity": float(raw),
        "property_derivation_verified": bool(verified),
        "primitive_separation_references": refs,
        "canonical_amounts": {k: float(v) for k, v in totals.items()},
    }


def transformation_property_record(
    left_composition: Any,
    right_composition: Any,
    output_composition: Any,
) -> dict[str, Any]:
    left = derive_effective_properties(left_composition)
    right = derive_effective_properties(right_composition)
    output = derive_effective_properties(output_composition)
    return {
        "passive_properties_only": True,
        "world_effects_applied": False,
        "body_effects_applied": False,
        "material_interactions_applied": False,
        "semantic_effects": False,
        "derivation": DERIVATION_VERSION,
        "derivation_version": DERIVATION_VERSION,
        "registry_version": REGISTRY_VERSION,
        "property_derivation_verified": bool(output["property_derivation_verified"]),
        "property_derivation_residuals": dict(output["property_derivation_residuals"]),
        "effective_properties_before": {
            "left": {"compliance": left["compliance"], "surface_affinity": left["surface_affinity"]},
            "right": {"compliance": right["compliance"], "surface_affinity": right["surface_affinity"]},
        },
        "effective_properties_after": {
            "compliance": output["compliance"],
            "surface_affinity": output["surface_affinity"],
        },
        "primitive_coefficient_references": {
            "left": list(left["primitive_coefficient_references"]),
            "right": list(right["primitive_coefficient_references"]),
            "output": list(output["primitive_coefficient_references"]),
        },
    }


def passive_material_properties_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": PASSIVE_MATERIAL_PROPERTIES,
        "name": "Passive material properties",
        "enabled": bool(enabled),
        "scope": "ACANTHOSTEGA_ONLY",
        "description": (
            "Researcher-only composition-weighted coefficients "
            "(compliance, surface_affinity). Passive — no consequence kernel."
        ),
    }
