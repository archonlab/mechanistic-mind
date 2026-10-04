"""Anonymous optical coating of a terrain cell by a deposited material.

optical_response is an intensive (c0, c1, c2) coefficient. It is not derived
from surface_affinity, and traction is not derived from it. Coverage is the
clipped quantity fraction. The sampler mixes the cell's existing surface
optical triplet before illumination, distance, occlusion, and body composition.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

MECHANISM_ID = "physical_surface_optical_coating"
EVENT_OBSERVED = "SURFACE_OPTICAL_COATING_OBSERVED"
DERIVATION_VERSION = "SURFACE_OPTICAL_COATING_V1"
REFERENCE_QUANTITY = 1.0
HISTORY_LIMIT = 16
PROVENANCE_LIMIT = 4

# Spawn-table coefficients. Independent of affinity. Not names of surfaces.
OPTICAL_VARIANT_A = (0.12, 0.22, 0.84)
OPTICAL_VARIANT_B = (0.84, 0.22, 0.12)


@dataclass
class PhysicalSurfaceOpticalCoatingConfig:
    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": bool(self.enabled)}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "PhysicalSurfaceOpticalCoatingConfig":
        if not data:
            return cls(enabled=False)
        return cls(enabled=bool(data.get("enabled", False)))


def physical_surface_optical_coating_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "physical_surface_optical_coating", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_physical_surface_optical_coating(config: Any, enabled: bool) -> None:
    acanthostega = str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cfg = getattr(config, "physical_surface_optical_coating", None)
    if cfg is None:
        cfg = PhysicalSurfaceOpticalCoatingConfig()
        config.physical_surface_optical_coating = cfg
    cfg.enabled = bool(enabled) and acanthostega
    nfe = getattr(config, "near_field_exteroception", None)
    if nfe is not None and hasattr(nfe, "surface_optical_coating_enabled"):
        nfe.surface_optical_coating_enabled = bool(cfg.enabled)


def coverage_from_quantity(quantity: float, *, reference: float = REFERENCE_QUANTITY) -> float:
    ref = float(reference) if float(reference) > 0.0 else REFERENCE_QUANTITY
    try:
        value = float(quantity) / ref
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value):
        return 0.0
    return float(max(0.0, min(1.0, value)))


def mix_coating(
    base: tuple[float, float, float] | list[float],
    deposit_optical: tuple[float, float, float] | list[float],
    coverage: float,
) -> tuple[float, float, float]:
    """coated = base * (1 - coverage) + deposit_optical * coverage."""
    try:
        c = float(coverage)
    except (TypeError, ValueError):
        c = 0.0
    if not math.isfinite(c):
        c = 0.0
    c = float(max(0.0, min(1.0, c)))
    out = []
    for index in range(3):
        b = float(base[index]) if index < len(base) else 0.0
        d = float(deposit_optical[index]) if index < len(deposit_optical) else 0.0
        out.append(float(max(0.0, min(1.0, (1.0 - c) * b + c * d))))
    return (out[0], out[1], out[2])


def quantity_weighted_optical(
    parts: list[tuple[tuple[float, float, float], float]],
) -> tuple[float, float, float] | None:
    weights = []
    for _triplet, quantity in parts:
        try:
            weight = float(quantity)
        except (TypeError, ValueError):
            weight = 0.0
        if not math.isfinite(weight) or weight < 0.0:
            weight = 0.0
        weights.append(weight)
    total = math.fsum(weights)
    if total <= 0.0:
        return None
    out = []
    for index in range(3):
        acc = math.fsum(
            float(parts[i][0][index]) * weights[i]
            for i in range(len(parts))
        )
        out.append(float(max(0.0, min(1.0, acc / total))))
    return (out[0], out[1], out[2])


def bump_coating_generation(world: Any) -> int:
    generation = int(getattr(world, "surface_optical_coating_generation", 0) or 0) + 1
    world.surface_optical_coating_generation = generation
    return generation


def coat_cell_optical(
    world: Any,
    cell_x: int,
    cell_y: int,
    base: list[float] | tuple[float, float, float],
) -> tuple[tuple[float, float, float], dict[str, Any] | None]:
    """O(1) cell lookup. Does not mutate the deposit or the world tensor."""
    from mechanistic_mind.physical_system.explicit_surface_deposition import deposit_id_for_cell
    from mechanistic_mind.physical_system.resource_objects import clip_optical_triplet

    base_t = (
        float(base[0]) if len(base) > 0 else 0.0,
        float(base[1]) if len(base) > 1 else 0.0,
        float(base[2]) if len(base) > 2 else 0.0,
    )
    deposits = getattr(world, "surface_material_deposits", None) or {}
    deposit = deposits.get(deposit_id_for_cell(int(cell_x), int(cell_y)))
    optical = getattr(deposit, "optical_response", None) if deposit is not None else None
    if optical is None:
        return base_t, None
    coverage = coverage_from_quantity(getattr(deposit, "quantity", 0.0))
    if coverage <= 0.0:
        return base_t, None
    deposit_optical = clip_optical_triplet(optical)
    coated = mix_coating(base_t, deposit_optical, coverage)
    return coated, {
        "deposit_id": str(getattr(deposit, "deposit_id", "")),
        "coverage": coverage,
        "base_optical_response": {"c0": base_t[0], "c1": base_t[1], "c2": base_t[2]},
        "deposit_optical_response": {
            "c0": deposit_optical[0], "c1": deposit_optical[1], "c2": deposit_optical[2],
        },
        "final_coated_response": {"c0": coated[0], "c1": coated[1], "c2": coated[2]},
        "derivation_version": str(
            getattr(deposit, "optical_derivation_version", None) or DERIVATION_VERSION
        ),
        "source_deposition_event_ids": list(getattr(deposit, "optical_source_event_ids", ()) or ())[-PROVENANCE_LIMIT:],
        "cache_generation": int(getattr(world, "surface_optical_coating_generation", 0) or 0),
        "agent_symbolic_label": False,
        "traction_encoded_directly": False,
        "material_identity_exposed": False,
    }


def transfer_optical_on_deposition(
    config: Any,
    world: Any,
    deposit: Any,
    existing: Any,
    source: Any,
    transferred_quantity: float,
    event_id: str,
) -> None:
    """Intensive spectrum follows transferred quantity. Quantity itself is unchanged here."""
    if not physical_surface_optical_coating_is_active(config):
        return
    from mechanistic_mind.physical_system.resource_objects import clip_optical_triplet

    source_optical = clip_optical_triplet(getattr(source, "optical_response", None))
    try:
        added = float(transferred_quantity)
    except (TypeError, ValueError):
        added = 0.0
    if not math.isfinite(added) or added < 0.0:
        added = 0.0
    prior = getattr(existing, "optical_response", None) if existing is not None else None
    if prior is None or existing is None:
        mixed = source_optical
    else:
        mixed = quantity_weighted_optical([
            (clip_optical_triplet(prior), float(getattr(existing, "quantity", 0.0) or 0.0)),
            (source_optical, added),
        ]) or source_optical
    prior_ids = list(getattr(existing, "optical_source_event_ids", ()) or ()) if existing is not None else []
    deposit.optical_response = mixed
    deposit.optical_derivation_version = DERIVATION_VERSION
    deposit.optical_source_event_ids = tuple((prior_ids + [str(event_id)])[-PROVENANCE_LIMIT:])
    bump_coating_generation(world)


def mix_survivor_optical(config: Any, left: Any, right: Any, left_quantity: float, right_quantity: float) -> None:
    """COMBINE keeps a quantity-weighted intensive spectrum on the survivor."""
    if not physical_surface_optical_coating_is_active(config):
        return
    from mechanistic_mind.physical_system.resource_objects import clip_optical_triplet

    mixed = quantity_weighted_optical([
        (clip_optical_triplet(getattr(left, "optical_response", None)), float(left_quantity)),
        (clip_optical_triplet(getattr(right, "optical_response", None)), float(right_quantity)),
    ])
    if mixed is not None:
        left.optical_response = mixed


def surface_optical_spawn_objects() -> list[dict[str, Any]]:
    """Traction contrast objects with independent anonymous spectra.

    Component id is not consulted by the coating function. The numbers are
    spawn coefficients, orthogonal to surface_affinity.
    """
    from mechanistic_mind.physical_system.surface_affinity_traction import (
        traction_contrast_spawn_objects,
    )

    rows = traction_contrast_spawn_objects()
    spectra = (OPTICAL_VARIANT_A, OPTICAL_VARIANT_B)
    out = []
    for row, spectrum in zip(rows, spectra):
        copied = dict(row)
        copied["optical_c0"] = float(spectrum[0])
        copied["optical_c1"] = float(spectrum[1])
        copied["optical_c2"] = float(spectrum[2])
        out.append(copied)
    return out


def note_visible_coating(world: Any, row: dict[str, Any]) -> None:
    info = row.get("surface_optical_coating")
    if not isinstance(info, dict):
        return
    visibility = str(row.get("visibility") or "")
    contributed = float(row.get("visible_contribution") or row.get("final_contribution") or 0.0) > 0.0
    # Sampled contribution, or a cell the occlusion pass selected and then hid.
    # Outside-FOV and sub-threshold cells are not recorded.
    if visibility != "OCCLUDED" and not contributed:
        return
    bucket = getattr(world, "_surface_optical_coating_buffer", None)
    if not isinstance(bucket, list):
        bucket = []
        world._surface_optical_coating_buffer = bucket
    if len(bucket) >= HISTORY_LIMIT:
        return
    bucket.append({
        "cell": list(row.get("cell") or []),
        "visibility": visibility,
        "inside_fov": bool(row.get("inside_fov")),
        "distance": row.get("distance"),
        "angular_factor": row.get("angular_factor"),
        "distance_factor": row.get("distance_factor"),
        "illumination": row.get("illumination"),
        "occluded": visibility == "OCCLUDED",
        **info,
        "researcher_only": True,
        "agent_accessible": False,
    })


def coating_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "physical_surface_optical_coating.enabled",
        "label": "PHYSICAL SURFACE OPTICAL COATING",
        "description": (
            "A deposited quantity mixes into the cell's anonymous optical "
            "response. researcher-only. not a material identity. not a traction label. not a recipe."
        ),
        "validation": "Acanthostega Phase A Surface Optical.",
        "provenance": "acanthostega_physical_surface_optical_coating",
        "default_integrated": True,
        "ablatable": True,
        "enabled": bool(enabled),
        "state": "ON" if enabled else "OFF",
        "category": "SENSORS",
        "promotion_class": "EXPERIMENTAL",
        "scientific_status": "IMPLEMENTED",
        "model_line": "ACANTHOSTEGA",
        "historical_compatibility": "missing key leaves surface optical unchanged",
    }
