"""Acanthostega VW1 · Volumetric world material occupancy authority.

Mechanism: volumetric_world_material_occupancy
Schema: VW1_VOLUMETRIC_OCCUPANCY_AUTHORITY_V1
Profile: SPARSE_ABSOLUTE_Z_OCCUPIED_INTERVALS_V1

VW1 replaces procedural surface columns as *geometry authority* with sparse
absolute-Z occupied intervals per wrapped XY cell. It does **not** migrate
support, contact, SES, FGG, or free-space PE authority — those remain on the
legacy heightfield path until VW2.

Free space is the complement of occupied intervals along Z (including cavities
between stacked intervals). Legacy ``surface_elevation`` is a **derived**
compatibility query (``compatibility_surface_elevation`` / ``derived_surface_elevation``),
not stored world truth.

Interval endpoints: ``INTERVAL_ENDPOINT_SEMANTICS`` =
``HALF_OPEN_LOWER_EXCLUSIVE_UPPER_INCLUSIVE`` — occupied iff ``z_min < z ≤ z_max``,
matching PSC depth ``[top, bottom)`` via ``z = H - depth`` where ``H`` is local
compatibility surface elevation.

No Z wrap; XY uses ``wrap_coord`` from ``mechanistic_mind.planet.topology``.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.planet.topology import wrap_coord

SCHEMA = "VW1_VOLUMETRIC_OCCUPANCY_AUTHORITY_V1"
CAPABILITY = "volumetric_world_material_occupancy"
PROFILE = "SPARSE_ABSOLUTE_Z_OCCUPIED_INTERVALS_V1"
AUTHORITY = "AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z"
MECHANISM_ID = "volumetric_world_material_occupancy"
SNAPSHOT_SCHEMA = "VOLUMETRIC_OCCUPANCY_SNAPSHOT_V1"
WORLD_ATTR = "volumetric_occupancy"
INTERVAL_ENDPOINT_SEMANTICS = "HALF_OPEN_LOWER_EXCLUSIVE_UPPER_INCLUSIVE"
TOLERANCE = 1e-12

HISTORY_LIMIT = 16
MAX_SPARSE_COLUMNS = 4096

DEFAULT_DERIVATION_VERSION = "COMPOSITION_WEIGHTED_MEAN_V1"

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "interval_endpoint_semantics": INTERVAL_ENDPOINT_SEMANTICS,
    "world_attribute": WORLD_ATTR,
    "physical_effects_active": False,
    "support_migrated": False,
    "contact_migrated": False,
    "agent_accessible": False,
    "researcher_only_view": True,
}

EFFECT_FLAGS = {
    **AUTHORITY_FLAGS,
    "geometry_role": "VOLUMETRIC_OCCUPANCY_AUTHORITY",
    "legacy_surface_elevation": "DERIVED_COMPATIBILITY_ONLY",
    "free_space_definition": "COMPLEMENT_OF_OCCUPIED_INTERVALS",
}


class VolumetricOccupancyValidationError(ValueError):
    """Raised when occupancy intervals or snapshots cannot be applied honestly."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class VolumetricWorldMaterialOccupancyConfig:
    """Fresh default OFF. Missing snapshot field keeps the mechanism OFF."""

    enabled: bool = False
    profile: str = PROFILE
    schema: str = SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "profile": str(self.profile),
            "schema": str(self.schema),
            **AUTHORITY_FLAGS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "VolumetricWorldMaterialOccupancyConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        profile = str(data.get("profile") or PROFILE)
        schema = str(data.get("schema") or SCHEMA)
        if profile != PROFILE:
            raise VolumetricOccupancyValidationError(f"unsupported volumetric occupancy profile: {profile!r}")
        if schema != SCHEMA:
            raise VolumetricOccupancyValidationError(f"unsupported volumetric occupancy schema: {schema!r}")
        return cls(enabled=bool(data.get("enabled", False)), profile=profile, schema=schema)


def validate_config(cfg: VolumetricWorldMaterialOccupancyConfig) -> None:
    if str(cfg.profile) != PROFILE:
        raise VolumetricOccupancyValidationError(f"profile must be {PROFILE!r}")
    if str(cfg.schema) != SCHEMA:
        raise VolumetricOccupancyValidationError(f"schema must be {SCHEMA!r}")


def volumetric_world_material_occupancy_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "volumetric_world_material_occupancy", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_volumetric_world_material_occupancy(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "volumetric_world_material_occupancy", None)
    if cur is None:
        config.volumetric_world_material_occupancy = VolumetricWorldMaterialOccupancyConfig(enabled=on)
    else:
        cur.enabled = on


# ---------------------------------------------------------------------------
# Interval types
# ---------------------------------------------------------------------------


def _fhex(value: float) -> str:
    return float(value).hex()


def _unfhex(value: Any) -> float:
    if isinstance(value, str):
        return float.fromhex(value)
    return float(value)


def _canonical_composition(pairs: Any) -> tuple[tuple[str, float], ...]:
    merged: dict[str, list[float]] = {}
    if pairs is None:
        return ()
    for row in pairs:
        if isinstance(row, (list, tuple)) and len(row) >= 2:
            cid, amount = str(row[0]), float(row[1])
        elif isinstance(row, dict):
            cid = str(row.get("component_id") or row.get("id") or "")
            amount = float(row.get("quantity_per_area", row.get("amount", 0.0)))
        else:
            continue
        if cid:
            merged.setdefault(cid, []).append(float(amount))
    out: list[tuple[str, float]] = []
    for cid in sorted(merged):
        total = math.fsum(merged[cid])
        if total > TOLERANCE:
            out.append((cid, float(total)))
    return tuple(out)


def _composition_equal(a: tuple[tuple[str, float], ...], b: tuple[tuple[str, float], ...]) -> bool:
    if len(a) != len(b):
        return False
    for (ca, qa), (cb, qb) in zip(a, b):
        if ca != cb or abs(float(qa) - float(qb)) > TOLERANCE:
            return False
    return True


@dataclass(frozen=True)
class OccupiedZInterval:
    """One occupied absolute-Z interval. Occupied iff z_min < z ≤ z_max."""

    z_min: float
    z_max: float
    density: float
    composition: tuple[tuple[str, float], ...]
    material_property_derivation_version: str = DEFAULT_DERIVATION_VERSION
    source_layer_index: int = -1

    def __post_init__(self) -> None:
        z0 = float(self.z_min)
        z1 = float(self.z_max)
        if not (math.isfinite(z0) and math.isfinite(z1)):
            raise VolumetricOccupancyValidationError("interval z bounds must be finite")
        if z1 <= z0 + TOLERANCE:
            raise VolumetricOccupancyValidationError("interval z_max must exceed z_min")
        if not (math.isfinite(float(self.density)) and float(self.density) > 0.0):
            raise VolumetricOccupancyValidationError("interval density must be finite and positive")

    @property
    def thickness(self) -> float:
        return float(self.z_max) - float(self.z_min)

    @property
    def quantity_per_area(self) -> float:
        return self.thickness

    @property
    def mass_per_area(self) -> float:
        return self.thickness * float(self.density)

    def contains(self, z: float) -> bool:
        zz = float(z)
        if not math.isfinite(zz):
            return False
        return float(self.z_min) + TOLERANCE < zz <= float(self.z_max) + TOLERANCE

    def as_dict(self) -> dict[str, Any]:
        return {
            "z_min": float(self.z_min),
            "z_max": float(self.z_max),
            "density": float(self.density),
            "thickness": self.thickness,
            "quantity_per_area": self.quantity_per_area,
            "mass_per_area": self.mass_per_area,
            "composition": [
                {"component_id": cid, "quantity_per_area": float(amount)} for cid, amount in self.composition
            ],
            "material_property_derivation_version": self.material_property_derivation_version,
            "source_layer_index": int(self.source_layer_index),
            "interval_endpoint_semantics": INTERVAL_ENDPOINT_SEMANTICS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OccupiedZInterval":
        comp = _canonical_composition(data.get("composition") or [])
        return cls(
            z_min=float(data["z_min"]),
            z_max=float(data["z_max"]),
            density=float(data["density"]),
            composition=comp,
            material_property_derivation_version=str(
                data.get("material_property_derivation_version") or DEFAULT_DERIVATION_VERSION
            ),
            source_layer_index=int(data.get("source_layer_index", -1)),
        )


def _intervals_compatible_merge(a: OccupiedZInterval, b: OccupiedZInterval) -> bool:
    return (
        abs(float(a.density) - float(b.density)) <= TOLERANCE
        and _composition_equal(a.composition, b.composition)
        and str(a.material_property_derivation_version) == str(b.material_property_derivation_version)
    )


def _interval_exact(it: OccupiedZInterval) -> dict[str, Any]:
    return {
        "z_min": _fhex(it.z_min),
        "z_max": _fhex(it.z_max),
        "density": _fhex(it.density),
        "composition": [[cid, _fhex(amount)] for cid, amount in it.composition],
        "material_property_derivation_version": it.material_property_derivation_version,
        "source_layer_index": int(it.source_layer_index),
    }


def _interval_from_exact(row: dict[str, Any]) -> OccupiedZInterval:
    return OccupiedZInterval(
        z_min=_unfhex(row["z_min"]),
        z_max=_unfhex(row["z_max"]),
        density=_unfhex(row["density"]),
        composition=tuple((str(cid), _unfhex(amount)) for cid, amount in row.get("composition") or []),
        material_property_derivation_version=str(
            row.get("material_property_derivation_version") or DEFAULT_DERIVATION_VERSION
        ),
        source_layer_index=int(row.get("source_layer_index", -1)),
    )


def canonicalize_intervals(
    intervals: tuple[OccupiedZInterval, ...] | list[OccupiedZInterval],
    *,
    merge_compatible_abutting: bool = False,
) -> tuple[OccupiedZInterval, ...]:
    """Sort by z_min, reject true overlaps, optionally merge abutting compatible intervals."""
    if not intervals:
        return ()
    ordered = sorted(intervals, key=lambda it: (float(it.z_min), float(it.z_max)))
    out: list[OccupiedZInterval] = []
    for it in ordered:
        if not out:
            out.append(it)
            continue
        prev = out[-1]
        if float(it.z_min) < float(prev.z_max) - TOLERANCE:
            raise VolumetricOccupancyValidationError(
                f"occupied intervals overlap: ({prev.z_min}, {prev.z_max}] vs ({it.z_min}, {it.z_max}]"
            )
        abutting = abs(float(it.z_min) - float(prev.z_max)) <= TOLERANCE
        if merge_compatible_abutting and abutting and _intervals_compatible_merge(prev, it):
            merged = OccupiedZInterval(
                z_min=float(prev.z_min),
                z_max=float(it.z_max),
                density=float(prev.density),
                composition=prev.composition,
                material_property_derivation_version=prev.material_property_derivation_version,
                source_layer_index=min(int(prev.source_layer_index), int(it.source_layer_index)),
            )
            out[-1] = merged
        else:
            if abutting and float(it.z_min) < float(prev.z_max) - TOLERANCE:
                raise VolumetricOccupancyValidationError("abutting intervals share interior")
            out.append(it)
    return tuple(out)


def intervals_from_legacy_column(
    H: float,
    layers: tuple[Any, ...] | list[Any],
    *,
    merge_compatible_adjacent: bool = False,
) -> tuple[OccupiedZInterval, ...]:
    """Convert PSC depth layers to absolute-Z intervals via z = H - depth."""
    h = float(H)
    if not math.isfinite(h):
        raise VolumetricOccupancyValidationError("legacy column H must be finite")
    built: list[OccupiedZInterval] = []
    for i, layer in enumerate(layers):
        if hasattr(layer, "top_depth"):
            top_depth = float(layer.top_depth)
            bottom_depth = float(layer.bottom_depth)
            density = float(layer.density)
            comp = getattr(layer, "composition", ())
            deriv = str(getattr(layer, "material_property_derivation_version", DEFAULT_DERIVATION_VERSION))
        elif isinstance(layer, dict):
            top_depth = float(layer["top_depth"])
            bottom_depth = float(layer["bottom_depth"])
            density = float(layer["density"])
            comp = layer.get("composition") or []
            deriv = str(layer.get("material_property_derivation_version") or DEFAULT_DERIVATION_VERSION)
        else:
            raise VolumetricOccupancyValidationError(f"unsupported legacy layer type: {type(layer)!r}")
        z_min = h - bottom_depth
        z_max = h - top_depth
        built.append(
            OccupiedZInterval(
                z_min=z_min,
                z_max=z_max,
                density=density,
                composition=_canonical_composition(comp),
                material_property_derivation_version=deriv,
                source_layer_index=int(i),
            )
        )
    return canonicalize_intervals(built, merge_compatible_abutting=merge_compatible_adjacent)


def free_gaps_between(intervals: tuple[OccupiedZInterval, ...]) -> list[tuple[float, float]]:
    """Derived free intervals strictly between occupied ones (not stored authority)."""
    if len(intervals) < 2:
        return []
    gaps: list[tuple[float, float]] = []
    for prev, nxt in zip(intervals, intervals[1:]):
        lo = float(prev.z_max)
        hi = float(nxt.z_min)
        if hi > lo + TOLERANCE:
            gaps.append((lo, hi))
    return gaps


def derived_surface_elevation_from(intervals: tuple[OccupiedZInterval, ...]) -> float | None:
    if not intervals:
        return None
    return max(float(it.z_max) for it in intervals)


# ---------------------------------------------------------------------------
# Column + world state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VolumetricColumn:
    cell_x: int
    cell_y: int
    occupied_intervals: tuple[OccupiedZInterval, ...]

    @property
    def derived_surface_elevation(self) -> float | None:
        return derived_surface_elevation_from(self.occupied_intervals)

    @property
    def free_gaps(self) -> list[tuple[float, float]]:
        return free_gaps_between(self.occupied_intervals)

    def as_dict(self) -> dict[str, Any]:
        return {
            "cell_x": int(self.cell_x),
            "cell_y": int(self.cell_y),
            "occupied_intervals": [it.as_dict() for it in self.occupied_intervals],
            "derived_surface_elevation": self.derived_surface_elevation,
            "free_gaps": [{"z_lo": lo, "z_hi": hi} for lo, hi in self.free_gaps],
            "interval_endpoint_semantics": INTERVAL_ENDPOINT_SEMANTICS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VolumetricColumn":
        intervals = tuple(OccupiedZInterval.from_dict(row) for row in (data.get("occupied_intervals") or []))
        intervals = canonicalize_intervals(intervals)
        return cls(cell_x=int(data["cell_x"]), cell_y=int(data["cell_y"]), occupied_intervals=intervals)


def _column_exact(col: VolumetricColumn) -> dict[str, Any]:
    return {
        "cell_x": int(col.cell_x),
        "cell_y": int(col.cell_y),
        "occupied_intervals": [_interval_exact(it) for it in col.occupied_intervals],
    }


def _column_from_exact(row: dict[str, Any]) -> VolumetricColumn:
    intervals = tuple(_interval_from_exact(r) for r in row.get("occupied_intervals") or [])
    intervals = canonicalize_intervals(intervals)
    return VolumetricColumn(cell_x=int(row["cell_x"]), cell_y=int(row["cell_y"]), occupied_intervals=intervals)


@dataclass
class VolumetricOccupancyState:
    config: VolumetricWorldMaterialOccupancyConfig
    width: int
    height: int
    columns: dict[tuple[int, int], VolumetricColumn] = field(default_factory=dict)
    history: list[dict[str, Any]] = field(default_factory=list)
    query_count: int = 0
    restored_column_count: int = 0
    restore_verification: dict[str, Any] = field(default_factory=dict)

    def digest(self) -> str:
        rows = [_column_exact(self.columns[key]) for key in sorted(self.columns)]
        raw = json.dumps(
            {"schema": SCHEMA, "profile": PROFILE, "columns": rows},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# World helpers
# ---------------------------------------------------------------------------


def _shape(world: Any) -> tuple[int, int]:
    grid = getattr(world, "T", None)
    if grid is None:
        return 32, 32
    return int(grid.shape[0]), int(grid.shape[1])


def state_of(world: Any) -> VolumetricOccupancyState | None:
    raw = getattr(world, WORLD_ATTR, None)
    return raw if isinstance(raw, VolumetricOccupancyState) else None


def _require(world: Any) -> VolumetricOccupancyState:
    state = state_of(world)
    if state is None:
        raise VolumetricOccupancyValidationError("volumetric occupancy state is not initialized")
    return state


def wrap_cell(state: VolumetricOccupancyState, x: Any, y: Any) -> tuple[int, int]:
    cx = int(math.floor(float(x)))
    cy = int(math.floor(float(y)))
    return int(wrap_coord(cx, state.width)), int(wrap_coord(cy, state.height))


def initialize_volumetric_occupancy(
    world: Any, cfg: VolumetricWorldMaterialOccupancyConfig
) -> VolumetricOccupancyState:
    validate_config(cfg)
    height, width = _shape(world)
    state = VolumetricOccupancyState(config=cfg, width=int(width), height=int(height), columns={})
    setattr(world, WORLD_ATTR, state)
    return state


def ensure_state(world: Any, config: Any) -> VolumetricOccupancyState | None:
    """Mechanism ON: keep restored state or initialize empty sparse map. OFF: clear state."""
    if not volumetric_world_material_occupancy_is_active(config):
        if getattr(world, WORLD_ATTR, None) is not None:
            setattr(world, WORLD_ATTR, None)
        return None
    state = state_of(world)
    if state is not None:
        return state
    cfg = getattr(config, "volumetric_world_material_occupancy", None)
    if cfg is None:
        cfg = VolumetricWorldMaterialOccupancyConfig(enabled=True)
    elif not isinstance(cfg, VolumetricWorldMaterialOccupancyConfig):
        cfg = VolumetricWorldMaterialOccupancyConfig.from_dict(cfg if isinstance(cfg, dict) else None)
        cfg.enabled = True
    return initialize_volumetric_occupancy(world, cfg)


def _remember(state: VolumetricOccupancyState, event: dict[str, Any]) -> None:
    state.history.append(event)
    if len(state.history) > HISTORY_LIMIT:
        del state.history[: len(state.history) - HISTORY_LIMIT]


# ---------------------------------------------------------------------------
# Mutations
# ---------------------------------------------------------------------------


def set_volumetric_column(
    world: Any,
    x: Any,
    y: Any,
    intervals: tuple[OccupiedZInterval, ...] | list[OccupiedZInterval],
    *,
    tick: int = 0,
    reason: str = "explicit_set",
) -> VolumetricColumn:
    state = _require(world)
    cell = wrap_cell(state, x, y)
    canonical = canonicalize_intervals(intervals)
    if len(state.columns) >= MAX_SPARSE_COLUMNS and cell not in state.columns:
        raise VolumetricOccupancyValidationError("sparse volumetric column capacity exceeded")
    col = VolumetricColumn(cell_x=cell[0], cell_y=cell[1], occupied_intervals=canonical)
    # Always store, including empty: empty means authoritative free column (not PSC fallback).
    state.columns[cell] = col
    try:
        from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
            invalidate_exposed_surface_cache,
        )

        invalidate_exposed_surface_cache(world)
    except Exception:
        pass
    try:
        from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
            invalidate_direct_light_cache,
        )

        invalidate_direct_light_cache(world)
    except Exception:
        pass
    try:
        from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
            invalidate_entity_surface_cache,
        )

        invalidate_entity_surface_cache(world)
    except Exception:
        pass
    _remember(
        state,
        {
            "event": "VOLUMETRIC_COLUMN_SET",
            "tick": int(tick),
            "cell": [cell[0], cell[1]],
            "interval_count": len(canonical),
            "reason": str(reason),
            "digest": state.digest(),
        },
    )
    return col


def clear_volumetric_column(world: Any, x: Any, y: Any, *, tick: int = 0, reason: str = "explicit_clear") -> None:
    state = _require(world)
    cell = wrap_cell(state, x, y)
    if cell in state.columns:
        del state.columns[cell]
    try:
        from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
            invalidate_exposed_surface_cache,
        )

        invalidate_exposed_surface_cache(world)
    except Exception:
        pass
    try:
        from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
            invalidate_direct_light_cache,
        )

        invalidate_direct_light_cache(world)
    except Exception:
        pass
    try:
        from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
            invalidate_entity_surface_cache,
        )

        invalidate_entity_surface_cache(world)
    except Exception:
        pass
    _remember(
        state,
        {
            "event": "VOLUMETRIC_COLUMN_CLEARED",
            "tick": int(tick),
            "cell": [cell[0], cell[1]],
            "reason": str(reason),
            "digest": state.digest(),
        },
    )


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def _legacy_intervals_at(world: Any, x: Any, y: Any) -> tuple[OccupiedZInterval, ...] | None:
    from mechanistic_mind.physical_system import procedural_surface_columns as psc

    if psc.state_of(world) is None:
        return None
    column = psc.resolved_column_at(world, x, y, record=False)
    h = float(column["surface_elevation"])
    layers = column["layers"]
    return intervals_from_legacy_column(h, layers, merge_compatible_adjacent=False)


def occupied_intervals_at(world: Any, x: Any, y: Any) -> tuple[OccupiedZInterval, ...]:
    """Sparse authority first; else derive from procedural surface columns when present."""
    state = state_of(world)
    if state is not None:
        cell = wrap_cell(state, x, y)
        col = state.columns.get(cell)
        if col is not None:
            state.query_count += 1
            return col.occupied_intervals
    legacy = _legacy_intervals_at(world, x, y)
    if legacy is not None:
        if state is not None:
            state.query_count += 1
        return legacy
    return ()


def column_view(world: Any, x: Any, y: Any) -> dict[str, Any]:
    state = state_of(world)
    cell_x = int(math.floor(float(x)))
    cell_y = int(math.floor(float(y)))
    if state is not None:
        cell = wrap_cell(state, x, y)
        cell_x, cell_y = cell
    intervals = occupied_intervals_at(world, x, y)
    col = VolumetricColumn(cell_x=cell_x, cell_y=cell_y, occupied_intervals=intervals)
    source = "SPARSE_AUTHORITY" if (state is not None and (cell_x, cell_y) in state.columns) else "DERIVED_OR_EMPTY"
    if source == "DERIVED_OR_EMPTY" and intervals and _legacy_intervals_at(world, x, y) is not None:
        source = "LEGACY_SURFACE_COLUMN_DERIVATION"
    return {
        **col.as_dict(),
        "source": source,
        "interval_endpoint_semantics": INTERVAL_ENDPOINT_SEMANTICS,
        **EFFECT_FLAGS,
    }


def occupancy_at(world: Any, x: Any, y: Any, z: float) -> bool:
    return any(it.contains(z) for it in occupied_intervals_at(world, x, y))


def interval_containing(world: Any, x: Any, y: Any, z: float) -> OccupiedZInterval | None:
    for it in occupied_intervals_at(world, x, y):
        if it.contains(z):
            return it
    return None


def material_at(world: Any, x: Any, y: Any, z: float) -> dict[str, Any]:
    it = interval_containing(world, x, y, z)
    base = {
        "cell_x": int(math.floor(float(x))),
        "cell_y": int(math.floor(float(y))),
        "z": float(z),
        "interval_endpoint_semantics": INTERVAL_ENDPOINT_SEMANTICS,
    }
    if state_of(world) is not None:
        cell = wrap_cell(state_of(world), x, y)
        base["cell_x"], base["cell_y"] = cell
    if it is None:
        return {**base, "occupied": False, "material": False, "interval": None}
    return {**base, "occupied": True, "material": True, "interval": it.as_dict()}


def nearest_occupied_interval_above(
    world: Any, x: Any, y: Any, z: float
) -> OccupiedZInterval | None:
    zz = float(z)
    best: OccupiedZInterval | None = None
    best_z_min = math.inf
    for it in occupied_intervals_at(world, x, y):
        z_min = float(it.z_min)
        if z_min + TOLERANCE >= zz and z_min < best_z_min:
            best = it
            best_z_min = z_min
    return best


def nearest_occupied_interval_below(
    world: Any, x: Any, y: Any, z: float
) -> OccupiedZInterval | None:
    zz = float(z)
    best: OccupiedZInterval | None = None
    best_z_max = -math.inf
    for it in occupied_intervals_at(world, x, y):
        z_max = float(it.z_max)
        if z_max <= zz + TOLERANCE and z_max > best_z_max:
            best = it
            best_z_max = z_max
    return best


def compatibility_surface_elevation(world: Any, x: Any, y: Any) -> float | None:
    """Legacy-compatible upper free-surface query: max occupied z_max at (x, y)."""
    return derived_surface_elevation_from(occupied_intervals_at(world, x, y))


# ---------------------------------------------------------------------------
# Snapshot / restore
# ---------------------------------------------------------------------------


def serialize_volumetric_occupancy(world: Any) -> dict[str, Any] | None:
    state = state_of(world)
    if state is None:
        return None
    return {
        "schema": SNAPSHOT_SCHEMA,
        "capability_schema": SCHEMA,
        "profile": PROFILE,
        "config": state.config.to_dict(),
        "width": int(state.width),
        "height": int(state.height),
        "interval_endpoint_semantics": INTERVAL_ENDPOINT_SEMANTICS,
        "columns": [_column_exact(state.columns[key]) for key in sorted(state.columns)],
        "digest": state.digest(),
        "history": list(state.history)[-HISTORY_LIMIT:],
        "counters": {"query_count": int(state.query_count)},
    }


def restore_volumetric_occupancy(
    world: Any, data: dict[str, Any] | None, *, tick: int = 0
) -> VolumetricOccupancyState | None:
    if not isinstance(data, dict) or not data:
        setattr(world, WORLD_ATTR, None)
        return None
    schema = str(data.get("schema") or "")
    if schema != SNAPSHOT_SCHEMA:
        raise VolumetricOccupancyValidationError(f"unknown volumetric occupancy snapshot schema: {schema!r}")
    cfg = VolumetricWorldMaterialOccupancyConfig.from_dict(data.get("config") or {})
    cfg.enabled = True
    height, width = _shape(world)
    if (int(data.get("width", width)), int(data.get("height", height))) != (width, height):
        raise VolumetricOccupancyValidationError("volumetric occupancy world shape mismatch")
    columns: dict[tuple[int, int], VolumetricColumn] = {}
    for row in data.get("columns") or []:
        col = _column_from_exact(row)
        cell = (int(col.cell_x), int(col.cell_y))
        columns[cell] = col
    state = VolumetricOccupancyState(
        config=cfg,
        width=int(width),
        height=int(height),
        columns=columns,
        history=[dict(item) for item in (data.get("history") or [])][-HISTORY_LIMIT:],
        query_count=int((data.get("counters") or {}).get("query_count", 0) or 0),
        restored_column_count=len(columns),
    )
    saved_digest = str(data.get("digest") or "")
    if saved_digest and saved_digest != state.digest():
        raise VolumetricOccupancyValidationError("volumetric occupancy snapshot digest mismatch")
    state.restore_verification = {
        "status": "VERIFIED",
        "digest_verified": bool(not saved_digest or saved_digest == state.digest()),
        "column_count": len(columns),
        "tick": int(tick),
    }
    setattr(world, WORLD_ATTR, state)
    _remember(
        state,
        {
            "event": "VOLUMETRIC_OCCUPANCY_RESTORED",
            "tick": int(tick),
            "column_count": len(columns),
            "digest": state.digest(),
        },
    )
    return state


def copy_state(src: Any, dst: Any) -> None:
    """Used by PlanetState.copy(): sparse columns only."""
    state = state_of(src)
    if state is None:
        return
    clone = VolumetricOccupancyState(
        config=VolumetricWorldMaterialOccupancyConfig.from_dict(state.config.to_dict()),
        width=int(state.width),
        height=int(state.height),
        columns={key: VolumetricColumn.from_dict(col.as_dict()) for key, col in state.columns.items()},
        history=[dict(item) for item in state.history],
        query_count=int(state.query_count),
        restored_column_count=int(state.restored_column_count),
        restore_verification=dict(state.restore_verification),
    )
    setattr(dst, WORLD_ATTR, clone)


# ---------------------------------------------------------------------------
# Passive researcher / observer payloads
# ---------------------------------------------------------------------------


def profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "mechanism_id": MECHANISM_ID,
        "snapshot_schema": SNAPSHOT_SCHEMA,
        "world_attribute": WORLD_ATTR,
        "interval_endpoint_semantics": INTERVAL_ENDPOINT_SEMANTICS,
        "tolerance": TOLERANCE,
        "support_migrated": False,
        "contact_migrated": False,
        "legacy_surface_elevation": "DERIVED_COMPATIBILITY_ONLY",
        "free_space": "COMPLEMENT_OF_OCCUPIED_INTERVALS",
    }


def researcher_payload(world: Any) -> dict[str, Any]:
    state = state_of(world)
    if state is None:
        return {}
    digest_before = state.digest()
    payload = {
        "volumetric_occupancy": {
            "mechanism": MECHANISM_ID,
            **profile_reference(),
            "sparse_column_count": len(state.columns),
            "column_cells": [[k[0], k[1]] for k in sorted(state.columns)][:64],
            "digest": digest_before,
            "query_count": int(state.query_count),
            "receipts": list(state.history)[-HISTORY_LIMIT:],
            **EFFECT_FLAGS,
        }
    }
    if state.digest() != digest_before:
        raise VolumetricOccupancyValidationError("researcher_payload mutated occupancy digest")
    return payload


def observer_column_inspector_payload(world: Any, x: Any, y: Any) -> dict[str, Any] | None:
    state = state_of(world)
    if state is None:
        return None
    digest_before = state.digest()
    view = column_view(world, x, y)
    out = {
        **view,
        "mechanism": MECHANISM_ID,
        "digest": digest_before,
        "researcher_only_view": True,
        "not_agent_accessible": True,
        "source_kind": "VOLUMETRIC_OCCUPANCY_COLUMN_INSPECTION",
    }
    if state.digest() != digest_before:
        raise VolumetricOccupancyValidationError("observer_column_inspector_payload mutated occupancy digest")
    return out


def volumetric_occupancy_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "volumetric_world_material_occupancy.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "schema": SCHEMA,
        "profile": PROFILE,
        "description": (
            "Authoritative sparse absolute-Z material occupancy per XY cell. "
            "Free space is complement of occupied intervals. Legacy surface elevation is "
            "derived compatibility only. VW1 does not migrate support/contact. "
            "physical_effects_active=false. not agent-accessible."
        ),
    }
