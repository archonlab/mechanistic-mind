"""Acanthostega procedural surface columns.

Storage, query and persistence foundation only. The untouched land under a
horizontal cell is a deterministic procedural baseline regenerated on demand
from (world_seed, cell_x, cell_y, generator_version, parameter checksum). A
modified cell carries one sparse persistent delta. Nothing here changes
terrain_potential, drag, forces, optical fields, traction, climate, ecology or
body integration. Nothing here is agent-accessible.

Authority (world simulation is the source of truth; Observer only reads it):
    procedural baseline column = authoritative physical world description
    surface_elevation          = authoritative geometry, no consequence kernel yet
    sparse delta               = authoritative persistent world mutation
    cache                      = derived, non-authoritative
    Observer representation    = researcher-only view

Flags: physical_effects_active = false, agent_accessible = false,
geometry_role = METADATA_ONLY.

resolved column = procedural baseline + sparse delta
"""
from __future__ import annotations

import hashlib
import json
import math
import struct
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.planet.topology import wrap_coord

MECHANISM_ID = "procedural_surface_columns"
GENERATOR_VERSION = "SURFACE_COLUMN_GENERATOR_V1"
SUPPORTED_GENERATOR_VERSIONS = frozenset({GENERATOR_VERSION})
SEED_NAMESPACE = "procedural_surface_columns"
# Seed authority: the canonical experiment/runtime seed (PhysicalSystemRuntime.seed,
# TwoAgentRuntime.seed). Never terrain_meta, never TerrainConfig.terrain_seed.
SEED_SOURCE = "EXPERIMENT_RUNTIME_SEED"
SEED_AUTHORITY = "EXPERIMENT_RUNTIME"
SEED_PROVENANCE_SCHEMA = "SURFACE_COLUMN_SEED_PROVENANCE_V1"
SNAPSHOT_SCHEMA = "PROCEDURAL_SURFACE_COLUMNS_SNAPSHOT_V1"
DELTA_SCHEMA = "SURFACE_COLUMN_DELTA_V1"
OPERATION_KIND = "SURFACE_COLUMN_SETUP_DELTA"
TRANSACTION_SCHEMA = "WORLD_MATERIAL_TRANSACTION_V1"
SURFACE_ELEVATION_STATUS = "GEOMETRY_METADATA_ONLY"
GEOMETRY_ROLE = "METADATA_ONLY"
AUTHORITY = "WORLD_SIMULATION_STATE"
PROVENANCE_KIND = "INTERVENTION_SETUP"

STATUS_MATERIAL = "MATERIAL"
STATUS_ABOVE_SURFACE = "ABOVE_SURFACE"
STATUS_NOT_MODELLED = "NOT_MODELLED"
BOUNDARY_POLICY = "HALF_OPEN_TOP_INCLUSIVE_BOTTOM_EXCLUSIVE"

EVENT_BASELINE_QUERIED = "SURFACE_COLUMN_BASELINE_QUERIED"
EVENT_DELTA_COMMITTED = "SURFACE_COLUMN_DELTA_COMMITTED"
EVENT_DELTA_RESTORED = "SURFACE_COLUMN_DELTA_RESTORED"
EVENT_VALIDATION_FAILED = "SURFACE_COLUMN_VALIDATION_FAILED"

TOLERANCE = 1e-12
HISTORY_LIMIT = 16
PROVENANCE_LIMIT = 4
MAX_DELTAS = 4096
MANIFEST_SAMPLE_SIZE = 16
DEPTH_BOUNDS = (0.5, 64.0)
CACHE_LIMIT_BOUNDS = (1, 4096)

# Anonymous component ids already used by passive material properties.
COMPONENT_IDS = ("component_0", "component_a", "component_b")
# Base composition weights per layer (surface downward). Anonymous; no semantic type.
BASE_COMPOSITION_WEIGHTS = (
    (0.60, 0.25, 0.15),
    (0.30, 0.50, 0.20),
    (0.15, 0.25, 0.60),
)

AUTHORITY_FLAGS = {
    "authority": AUTHORITY,
    "baseline_authority": "AUTHORITATIVE_PHYSICAL_WORLD_DESCRIPTION",
    "surface_elevation_authority": "AUTHORITATIVE_GEOMETRY_NO_CONSEQUENCE_KERNEL",
    "delta_authority": "AUTHORITATIVE_PERSISTENT_WORLD_MUTATION",
    "cache_authority": "DERIVED_NON_AUTHORITATIVE",
    "observer_role": "RESEARCHER_ONLY_READ_VIEW",
    "physical_effects_active": False,
    "geometry_role": GEOMETRY_ROLE,
}

EFFECT_FLAGS = {
    **AUTHORITY_FLAGS,
    "researcher_view": True,
    "agent_accessible": False,
    "physical_body_effect": False,
    "terrain_force_effect": False,
    "vision_effect": False,
    "traction_effect": False,
    "support_effect": False,
    "gravity_effect": False,
}


class SurfaceColumnValidationError(ValueError):
    """Raised when a column snapshot or delta cannot be applied honestly."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class ProceduralSurfaceColumnsConfig:
    """Fresh default OFF. Missing snapshot field keeps the mechanism OFF."""

    enabled: bool = False
    generator_version: str = GENERATOR_VERSION
    modelled_depth: float = 4.0
    thickness_fractions: tuple[float, ...] = (0.2, 0.3, 0.5)
    thickness_variation: float = 0.35
    base_densities: tuple[float, ...] = (1.4, 1.9, 2.5)
    density_variation: float = 0.08
    composition_variation: float = 0.10
    elevation_amplitude: float = 0.5
    noise_cell_scale: int = 8
    cache_limit: int = 256

    def generator_parameters(self) -> dict[str, Any]:
        return {
            "generator_version": str(self.generator_version),
            "modelled_depth": float(self.modelled_depth),
            "layer_count": len(self.thickness_fractions),
            "thickness_fractions": [float(v) for v in self.thickness_fractions],
            "thickness_variation": float(self.thickness_variation),
            "base_densities": [float(v) for v in self.base_densities],
            "density_variation": float(self.density_variation),
            "composition_variation": float(self.composition_variation),
            "elevation_amplitude": float(self.elevation_amplitude),
            "noise_cell_scale": int(self.noise_cell_scale),
            "component_ids": list(COMPONENT_IDS),
            "base_composition_weights": [list(row) for row in BASE_COMPOSITION_WEIGHTS],
        }

    def to_dict(self) -> dict[str, Any]:
        out = self.generator_parameters()
        out.pop("layer_count", None)
        out.pop("component_ids", None)
        out.pop("base_composition_weights", None)
        out["enabled"] = bool(self.enabled)
        out["cache_limit"] = int(self.cache_limit)
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProceduralSurfaceColumnsConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        cfg = cls(
            enabled=bool(data.get("enabled", False)),
            generator_version=str(data.get("generator_version") or GENERATOR_VERSION),
            modelled_depth=float(data.get("modelled_depth", 4.0)),
            thickness_fractions=tuple(float(v) for v in (data.get("thickness_fractions") or (0.2, 0.3, 0.5))),
            thickness_variation=float(data.get("thickness_variation", 0.35)),
            base_densities=tuple(float(v) for v in (data.get("base_densities") or (1.4, 1.9, 2.5))),
            density_variation=float(data.get("density_variation", 0.08)),
            composition_variation=float(data.get("composition_variation", 0.10)),
            elevation_amplitude=float(data.get("elevation_amplitude", 0.5)),
            noise_cell_scale=int(data.get("noise_cell_scale", 8)),
            cache_limit=int(data.get("cache_limit", 256)),
        )
        return cfg


def validate_config(cfg: ProceduralSurfaceColumnsConfig) -> None:
    if str(cfg.generator_version) not in SUPPORTED_GENERATOR_VERSIONS:
        raise SurfaceColumnValidationError(
            f"unsupported surface column generator version: {cfg.generator_version!r}"
        )
    depth = float(cfg.modelled_depth)
    if not (math.isfinite(depth) and DEPTH_BOUNDS[0] <= depth <= DEPTH_BOUNDS[1]):
        raise SurfaceColumnValidationError(f"modelled_depth out of bounds: {depth}")
    n = len(cfg.thickness_fractions)
    if n not in (2, 3) or len(cfg.base_densities) != n:
        raise SurfaceColumnValidationError("layer count must be 2 or 3 with one density per layer")
    if any(not (math.isfinite(v) and v > 0.0) for v in cfg.thickness_fractions):
        raise SurfaceColumnValidationError("thickness fractions must be finite and positive")
    if any(not (math.isfinite(v) and 0.1 <= v <= 20.0) for v in cfg.base_densities):
        raise SurfaceColumnValidationError("base densities must be finite and bounded")
    if not (0.0 <= float(cfg.thickness_variation) <= 0.9):
        raise SurfaceColumnValidationError("thickness_variation must be in [0, 0.9]")
    if not (0.0 <= float(cfg.density_variation) <= 0.5):
        raise SurfaceColumnValidationError("density_variation must be in [0, 0.5]")
    if not (0.0 <= float(cfg.composition_variation) <= 0.5):
        raise SurfaceColumnValidationError("composition_variation must be in [0, 0.5]")
    if not (0.0 <= float(cfg.elevation_amplitude) <= 8.0):
        raise SurfaceColumnValidationError("elevation_amplitude must be in [0, 8]")
    if not (1 <= int(cfg.noise_cell_scale) <= 64):
        raise SurfaceColumnValidationError("noise_cell_scale must be in [1, 64]")
    if not (CACHE_LIMIT_BOUNDS[0] <= int(cfg.cache_limit) <= CACHE_LIMIT_BOUNDS[1]):
        raise SurfaceColumnValidationError("cache_limit out of bounds")


def procedural_surface_columns_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "procedural_surface_columns", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_procedural_surface_columns(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "procedural_surface_columns", None)
    if cur is None:
        config.procedural_surface_columns = ProceduralSurfaceColumnsConfig(enabled=on)
    else:
        cur.enabled = on


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SurfaceMaterialLayer:
    """One anonymous material layer. Depth is measured down from local surface.

    composition holds (component_id, quantity_per_area) sorted by id; amounts sum
    to thickness. quantity_per_area == thickness (volume per unit area).
    mass_per_area == thickness * density. No semantic layer type.
    """

    top_depth: float
    bottom_depth: float
    thickness: float
    density: float
    composition: tuple[tuple[str, float], ...]
    material_property_derivation_version: str = "COMPOSITION_WEIGHTED_MEAN_V1"

    @property
    def quantity_per_area(self) -> float:
        return float(self.thickness)

    @property
    def mass_per_area(self) -> float:
        return float(self.thickness) * float(self.density)

    def as_dict(self) -> dict[str, Any]:
        return {
            "top_depth": float(self.top_depth),
            "bottom_depth": float(self.bottom_depth),
            "thickness": float(self.thickness),
            "density": float(self.density),
            "quantity_per_area": self.quantity_per_area,
            "mass_per_area": self.mass_per_area,
            "composition": [
                {"component_id": cid, "quantity_per_area": float(amount)} for cid, amount in self.composition
            ],
            "material_property_derivation_version": self.material_property_derivation_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SurfaceMaterialLayer":
        comp = tuple(
            (str(row["component_id"]), float(row.get("quantity_per_area", row.get("amount", 0.0))))
            for row in (data.get("composition") or [])
        )
        return cls(
            top_depth=float(data["top_depth"]),
            bottom_depth=float(data["bottom_depth"]),
            thickness=float(data["thickness"]),
            density=float(data["density"]),
            composition=comp,
            material_property_derivation_version=str(
                data.get("material_property_derivation_version") or "COMPOSITION_WEIGHTED_MEAN_V1"
            ),
        )


@dataclass(frozen=True)
class SurfaceColumnBaseline:
    cell_x: int
    cell_y: int
    surface_elevation: float
    layers: tuple[SurfaceMaterialLayer, ...]
    modelled_depth: float
    generator_version: str
    baseline_checksum: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "cell_x": int(self.cell_x),
            "cell_y": int(self.cell_y),
            "surface_elevation": float(self.surface_elevation),
            "surface_elevation_status": SURFACE_ELEVATION_STATUS,
            "geometry_role": GEOMETRY_ROLE,
            "authority": AUTHORITY,
            "modelled_depth": float(self.modelled_depth),
            "layers": [layer.as_dict() for layer in self.layers],
            "generator_version": self.generator_version,
            "baseline_checksum": self.baseline_checksum,
        }


@dataclass
class SurfaceColumnDelta:
    delta_id: str
    cell_x: int
    cell_y: int
    baseline_generator_version: str
    baseline_checksum: str
    resulting_surface_elevation: float
    resulting_layers: tuple[SurfaceMaterialLayer, ...]
    created_tick: int
    last_updated_tick: int
    revision: int
    source_transaction_ids: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: str = DELTA_SCHEMA

    def resolved_checksum(self) -> str:
        return _column_checksum(
            self.cell_x, self.cell_y, self.resulting_surface_elevation, self.resulting_layers,
            self.baseline_generator_version,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "delta_id": self.delta_id,
            "cell_x": int(self.cell_x),
            "cell_y": int(self.cell_y),
            "baseline_generator_version": self.baseline_generator_version,
            "baseline_checksum": self.baseline_checksum,
            "resulting_surface_elevation": _fhex(self.resulting_surface_elevation),
            "resulting_layers": [_layer_exact(layer) for layer in self.resulting_layers],
            "created_tick": int(self.created_tick),
            "last_updated_tick": int(self.last_updated_tick),
            "revision": int(self.revision),
            "source_transaction_ids": list(self.source_transaction_ids)[-PROVENANCE_LIMIT:],
            "provenance": dict(self.provenance),
            "resolved_checksum": self.resolved_checksum(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SurfaceColumnDelta":
        return cls(
            delta_id=str(data["delta_id"]),
            cell_x=int(data["cell_x"]),
            cell_y=int(data["cell_y"]),
            baseline_generator_version=str(data["baseline_generator_version"]),
            baseline_checksum=str(data["baseline_checksum"]),
            resulting_surface_elevation=_unfhex(data["resulting_surface_elevation"]),
            resulting_layers=tuple(_layer_from_exact(row) for row in data.get("resulting_layers") or []),
            created_tick=int(data.get("created_tick", 0)),
            last_updated_tick=int(data.get("last_updated_tick", 0)),
            revision=int(data.get("revision", 1)),
            source_transaction_ids=[str(v) for v in (data.get("source_transaction_ids") or [])][-PROVENANCE_LIMIT:],
            provenance=dict(data.get("provenance") or {}),
            schema_version=str(data.get("schema_version") or DELTA_SCHEMA),
        )


@dataclass
class SurfaceColumnState:
    """World-level column state. Only config, seed, manifest and sparse deltas are authority."""

    config: ProceduralSurfaceColumnsConfig
    world_seed: int
    width: int
    height: int
    parameter_checksum: str
    namespace_key: str
    manifest: dict[str, Any]
    transaction_sequence: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    baseline_query_count: int = 0
    recorded_query_count: int = 0
    validation_failure_count: int = 0
    restored_delta_count: int = 0
    restore_verification: dict[str, Any] = field(default_factory=dict)
    seed_source: str = SEED_SOURCE
    # Non-authoritative bounded cache; never serialized, never checksummed.
    cache: "OrderedDict[tuple[int, int], SurfaceColumnBaseline]" = field(default_factory=OrderedDict)
    cache_evictions: int = 0
    # Optional researcher-only transfer bookkeeping (conservative_surface_column_transfer);
    # None unless that mechanism is ON. Serialized only when present.
    transfer: Any = None


# ---------------------------------------------------------------------------
# Exact float helpers and checksums
# ---------------------------------------------------------------------------


def _fhex(value: float) -> str:
    return float(value).hex()


def _unfhex(value: Any) -> float:
    if isinstance(value, str):
        return float.fromhex(value)
    return float(value)


def _layer_exact(layer: SurfaceMaterialLayer) -> dict[str, Any]:
    return {
        "top_depth": _fhex(layer.top_depth),
        "bottom_depth": _fhex(layer.bottom_depth),
        "thickness": _fhex(layer.thickness),
        "density": _fhex(layer.density),
        "composition": [[cid, _fhex(amount)] for cid, amount in layer.composition],
        "material_property_derivation_version": layer.material_property_derivation_version,
    }


def _layer_from_exact(row: dict[str, Any]) -> SurfaceMaterialLayer:
    return SurfaceMaterialLayer(
        top_depth=_unfhex(row["top_depth"]),
        bottom_depth=_unfhex(row["bottom_depth"]),
        thickness=_unfhex(row["thickness"]),
        density=_unfhex(row["density"]),
        composition=tuple((str(cid), _unfhex(amount)) for cid, amount in row.get("composition") or []),
        material_property_derivation_version=str(
            row.get("material_property_derivation_version") or "COMPOSITION_WEIGHTED_MEAN_V1"
        ),
    )


def _sha16(payload: Any) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _column_checksum(
    cell_x: int, cell_y: int, elevation: float, layers: tuple[SurfaceMaterialLayer, ...], version: str
) -> str:
    return _sha16({
        "cell": [int(cell_x), int(cell_y)],
        "elevation": _fhex(elevation),
        "layers": [_layer_exact(layer) for layer in layers],
        "generator_version": str(version),
    })


def parameter_checksum(cfg: ProceduralSurfaceColumnsConfig) -> str:
    return _sha16(cfg.generator_parameters())


def namespace_key(world_seed: int, cfg: ProceduralSurfaceColumnsConfig) -> str:
    """Deterministic namespace key. No Python hash(), no RNG state."""
    material = f"{int(world_seed)}\0{SEED_NAMESPACE}\0{cfg.generator_version}\0{parameter_checksum(cfg)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _unit(key: str, tag: str, ix: int, iy: int) -> float:
    """Uniform float in [0, 1) from sha256 of (namespace key, tag, lattice address)."""
    digest = hashlib.sha256(f"{key}\0{tag}\0{int(ix)}\0{int(iy)}".encode("utf-8")).digest()
    (bits,) = struct.unpack(">Q", digest[:8])
    return (bits >> 11) * (1.0 / 9007199254740992.0)


def _smooth(t: float) -> float:
    return t * t * (3.0 - 2.0 * t)


def _value_noise(key: str, tag: str, cell_x: int, cell_y: int, width: int, height: int, scale: int) -> float:
    """Toroidally periodic value noise in [0, 1] from a hashed coarse lattice."""
    nx = max(1, int(width) // int(scale))
    ny = max(1, int(height) // int(scale))
    u = (float(cell_x) + 0.5) * nx / float(width)
    v = (float(cell_y) + 0.5) * ny / float(height)
    i0 = int(math.floor(u))
    j0 = int(math.floor(v))
    fu = _smooth(u - i0)
    fv = _smooth(v - j0)
    a = _unit(key, tag, i0 % nx, j0 % ny)
    b = _unit(key, tag, (i0 + 1) % nx, j0 % ny)
    c = _unit(key, tag, i0 % nx, (j0 + 1) % ny)
    d = _unit(key, tag, (i0 + 1) % nx, (j0 + 1) % ny)
    top = a + (b - a) * fu
    bottom = c + (d - c) * fu
    return top + (bottom - top) * fv


# ---------------------------------------------------------------------------
# Generator V1
# ---------------------------------------------------------------------------


def _canonical_composition(pairs: list[tuple[str, float]]) -> tuple[tuple[str, float], ...]:
    merged: dict[str, list[float]] = {}
    for cid, amount in pairs:
        merged.setdefault(str(cid), []).append(float(amount))
    out = []
    for cid in sorted(merged):
        total = math.fsum(merged[cid])
        if total > 0.0:
            out.append((cid, float(total)))
    return tuple(out)


def generate_baseline_v1(
    *, world_seed: int, cell_x: int, cell_y: int, width: int, height: int,
    cfg: ProceduralSurfaceColumnsConfig, key: str | None = None,
) -> SurfaceColumnBaseline:
    """Pure function of (seed, wrapped address, version, parameters)."""
    if str(cfg.generator_version) != GENERATOR_VERSION:
        raise SurfaceColumnValidationError(f"generator V1 cannot build {cfg.generator_version!r}")
    width = int(width)
    height = int(height)
    x = int(wrap_coord(int(cell_x), width))
    y = int(wrap_coord(int(cell_y), height))
    key = key or namespace_key(world_seed, cfg)
    scale = int(cfg.noise_cell_scale)
    depth = float(cfg.modelled_depth)
    n = len(cfg.thickness_fractions)

    raw = []
    for i, frac in enumerate(cfg.thickness_fractions):
        noise = _value_noise(key, f"thickness:{i}", x, y, width, height, scale)
        raw.append(float(frac) * (1.0 + float(cfg.thickness_variation) * (2.0 * noise - 1.0)))
    total = math.fsum(raw)
    layers: list[SurfaceMaterialLayer] = []
    top = 0.0
    for i in range(n):
        if i == n - 1:
            bottom = depth
        else:
            bottom = top + depth * raw[i] / total
        thickness = bottom - top
        dn = _value_noise(key, f"density:{i}", x, y, width, height, scale)
        density = float(cfg.base_densities[i]) * (1.0 + float(cfg.density_variation) * (2.0 * dn - 1.0))
        base = BASE_COMPOSITION_WEIGHTS[min(i, len(BASE_COMPOSITION_WEIGHTS) - 1)]
        weights = []
        for j, cid in enumerate(COMPONENT_IDS):
            cn = _unit(key, f"composition:{i}:{cid}", x, y)
            weights.append(float(base[j]) * (1.0 + float(cfg.composition_variation) * (2.0 * cn - 1.0)))
        wsum = math.fsum(weights)
        amounts = [thickness * w / wsum for w in weights[:-1]]
        amounts.append(thickness - math.fsum(amounts))
        layers.append(SurfaceMaterialLayer(
            top_depth=float(top),
            bottom_depth=float(bottom),
            thickness=float(thickness),
            density=float(density),
            composition=_canonical_composition(list(zip(COMPONENT_IDS, amounts))),
        ))
        top = bottom
    en = _value_noise(key, "elevation", x, y, width, height, scale)
    elevation = float(cfg.elevation_amplitude) * (2.0 * en - 1.0)
    layer_tuple = tuple(layers)
    return SurfaceColumnBaseline(
        cell_x=x,
        cell_y=y,
        surface_elevation=float(elevation),
        layers=layer_tuple,
        modelled_depth=depth,
        generator_version=GENERATOR_VERSION,
        baseline_checksum=_column_checksum(x, y, elevation, layer_tuple, GENERATOR_VERSION),
    )


GENERATORS = {GENERATOR_VERSION: generate_baseline_v1}


def resolved_modelled_depth_for(baseline: SurfaceColumnBaseline, elevation: float) -> float:
    """Resolved depth above the fixed lower datum (FIXED_LOWER_DATUM_V1).

    fixed_lower_datum = baseline_surface_elevation - baseline_modelled_depth
    resolved_depth    = resolved_surface_elevation - fixed_lower_datum
    Written as modelled_depth + (elevation - baseline_elevation) so an unchanged
    elevation returns exactly the baseline modelled_depth (bit-identical).
    """
    return float(baseline.modelled_depth) + (float(elevation) - float(baseline.surface_elevation))


# ---------------------------------------------------------------------------
# Validation and summaries
# ---------------------------------------------------------------------------


def validate_layers(layers: tuple[SurfaceMaterialLayer, ...], modelled_depth: float) -> dict[str, Any]:
    problems: list[str] = []
    if not layers:
        problems.append("no_layers")
    expected_top = 0.0
    for i, layer in enumerate(layers):
        vals = (layer.top_depth, layer.bottom_depth, layer.thickness, layer.density)
        if not all(math.isfinite(v) for v in vals):
            problems.append(f"layer{i}:non_finite")
            continue
        if layer.thickness <= 0.0:
            problems.append(f"layer{i}:thickness_not_positive")
        if layer.density <= 0.0:
            problems.append(f"layer{i}:density_not_positive")
        if abs(layer.top_depth - expected_top) > TOLERANCE:
            problems.append(f"layer{i}:gap_or_overlap")
        if abs((layer.bottom_depth - layer.top_depth) - layer.thickness) > TOLERANCE:
            problems.append(f"layer{i}:thickness_mismatch")
        ids = [cid for cid, _ in layer.composition]
        if ids != sorted(set(ids)) or any(not (math.isfinite(a) and a > 0.0) for _, a in layer.composition):
            problems.append(f"layer{i}:composition_not_canonical")
        if abs(math.fsum(a for _, a in layer.composition) - layer.thickness) > 1e-9:
            problems.append(f"layer{i}:composition_quantity_mismatch")
        expected_top = layer.bottom_depth
    if layers and abs(layers[-1].bottom_depth - float(modelled_depth)) > TOLERANCE:
        problems.append("total_depth_mismatch")
    return {
        "ordered": not any("gap_or_overlap" in p for p in problems),
        "contiguous_no_gaps": not any("gap_or_overlap" in p for p in problems),
        "finite_positive": not any(("non_finite" in p or "not_positive" in p) for p in problems),
        "composition_canonical": not any("composition" in p for p in problems),
        "total_depth_bounded": not any("total_depth" in p for p in problems),
        "problems": problems,
        "verified": not problems,
        "layer_count": len(layers),
        "boundary_policy": BOUNDARY_POLICY,
    }


def mass_summary(layers: tuple[SurfaceMaterialLayer, ...]) -> dict[str, Any]:
    comp: dict[str, list[float]] = {}
    for layer in layers:
        for cid, amount in layer.composition:
            comp.setdefault(cid, []).append(float(amount))
    return {
        "layers": [
            {
                "index": i,
                "quantity_per_area": layer.quantity_per_area,
                "mass_per_area": layer.mass_per_area,
            }
            for i, layer in enumerate(layers)
        ],
        "total_quantity_per_area": math.fsum(layer.quantity_per_area for layer in layers),
        "total_mass_per_area": math.fsum(layer.mass_per_area for layer in layers),
        "component_quantity_per_area": {cid: math.fsum(vals) for cid, vals in sorted(comp.items())},
        "total_depth": float(layers[-1].bottom_depth) if layers else 0.0,
        "units": "per unit horizontal area; quantity == layer volume per area",
    }


def _domain(before: float, after: float) -> dict[str, Any]:
    residual = float(after) - float(before)
    return {
        "before": float(before), "after": float(after), "residual": residual,
        "tolerance": TOLERANCE, "verified": bool(math.isfinite(residual) and abs(residual) <= TOLERANCE),
    }


def conservation_between(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    comp_b = before["component_quantity_per_area"]
    comp_a = after["component_quantity_per_area"]
    keys = sorted(set(comp_b) | set(comp_a))
    residuals = {k: float(comp_a.get(k, 0.0)) - float(comp_b.get(k, 0.0)) for k in keys}
    max_abs = max((abs(v) for v in residuals.values()), default=0.0)
    out = {
        "mass": _domain(before["total_mass_per_area"], after["total_mass_per_area"]),
        "quantity": _domain(before["total_quantity_per_area"], after["total_quantity_per_area"]),
        "total_depth": _domain(before["total_depth"], after["total_depth"]),
        "components": {
            "residuals": residuals, "residual_max_abs": float(max_abs), "tolerance": TOLERANCE,
            "verified": bool(math.isfinite(max_abs) and max_abs <= TOLERANCE),
        },
        "external_source_sink": False,
        "closed_column": True,
    }
    out["verified"] = all(out[k]["verified"] for k in ("mass", "quantity", "total_depth", "components"))
    return out


# ---------------------------------------------------------------------------
# World state
# ---------------------------------------------------------------------------


def _shape(world: Any) -> tuple[int, int]:
    grid = getattr(world, "T", None)
    if grid is None:
        return 32, 32
    return int(grid.shape[0]), int(grid.shape[1])


def state_of(world: Any) -> SurfaceColumnState | None:
    raw = getattr(world, "surface_columns", None)
    return raw if isinstance(raw, SurfaceColumnState) else None


def deltas_of(world: Any) -> dict[tuple[int, int], SurfaceColumnDelta]:
    raw = getattr(world, "surface_column_deltas", None)
    return raw if isinstance(raw, dict) else {}


def build_manifest(state: SurfaceColumnState) -> dict[str, Any]:
    """Bounded manifest: fixed canonical sample of addresses, no volume materialization."""
    w, h = state.width, state.height
    sample = []
    for k in range(MANIFEST_SAMPLE_SIZE):
        sample.append(((k * 7919 + 3) % w, (k * 104729 + 11) % h))
    sample = sorted(set(sample))
    checksums = [
        generate_baseline_v1(
            world_seed=state.world_seed, cell_x=x, cell_y=y, width=w, height=h,
            cfg=state.config, key=state.namespace_key,
        ).baseline_checksum
        for x, y in sample
    ]
    sample_checksum = _sha16({"sample": [list(a) for a in sample], "checksums": checksums})
    manifest = {
        "generator_version": state.config.generator_version,
        "world_seed": int(state.world_seed),
        "seed_namespace": SEED_NAMESPACE,
        "seed_source": state.seed_source,
        "width": int(w),
        "height": int(h),
        "modelled_depth": float(state.config.modelled_depth),
        "layer_count": len(state.config.thickness_fractions),
        "parameter_checksum": state.parameter_checksum,
        "sample_policy": f"FIXED_CANONICAL_SAMPLE_{len(sample)}",
        "sample_addresses": [list(a) for a in sample],
        "sample_checksum": sample_checksum,
    }
    manifest["manifest_checksum"] = _sha16({k: v for k, v in manifest.items()})
    return manifest


def initialize_surface_columns(
    world: Any, cfg: ProceduralSurfaceColumnsConfig, *, world_seed: int, seed_source: str = SEED_SOURCE
) -> SurfaceColumnState:
    validate_config(cfg)
    if world_seed is None or isinstance(world_seed, bool):
        raise SurfaceColumnValidationError("surface column seed authority missing")
    if seed_source != SEED_SOURCE:
        raise SurfaceColumnValidationError(f"unsupported surface column seed source {seed_source!r}")
    height, width = _shape(world)
    state = SurfaceColumnState(
        config=cfg,
        world_seed=int(world_seed),
        width=int(width),
        height=int(height),
        parameter_checksum=parameter_checksum(cfg),
        namespace_key=namespace_key(world_seed, cfg),
        manifest={},
        seed_source=seed_source,
    )
    state.manifest = build_manifest(state)
    world.surface_columns = state
    if not isinstance(getattr(world, "surface_column_deltas", None), dict):
        world.surface_column_deltas = {}
    return state


def ensure_surface_columns_for_runtime(
    world: Any, config: Any, *, experiment_seed: int | None = None
) -> SurfaceColumnState | None:
    """Mechanism ON: keep restored state or initialize the manifest. OFF: no column state."""
    if not procedural_surface_columns_is_active(config):
        if getattr(world, "surface_columns", None) is not None or getattr(world, "surface_column_deltas", None):
            world.surface_columns = None
            world.surface_column_deltas = {}
        return None
    if experiment_seed is None:
        raise SurfaceColumnValidationError(
            "surface column seed authority missing: pass the canonical experiment/runtime seed"
        )
    state = state_of(world)
    if state is not None:
        if int(state.world_seed) != int(experiment_seed):
            raise SurfaceColumnValidationError(
                f"{EVENT_VALIDATION_FAILED}: surface column world_seed {state.world_seed} does not match "
                f"runtime seed authority {int(experiment_seed)}"
            )
    else:
        cfg = getattr(config, "procedural_surface_columns", None)
        state = initialize_surface_columns(world, cfg, world_seed=int(experiment_seed), seed_source=SEED_SOURCE)
    from mechanistic_mind.physical_system.conservative_surface_column_transfer import (
        ensure_column_transfer_for_state,
    )

    ensure_column_transfer_for_state(state, config)
    return state


def seed_provenance(state: SurfaceColumnState) -> dict[str, Any]:
    """Enough to re-derive and audit the geology stream without trusting terrain state."""
    return {
        "schema": SEED_PROVENANCE_SCHEMA,
        "world_seed": int(state.world_seed),
        "authority": SEED_AUTHORITY,
        "seed_source": state.seed_source,
        "seed_namespace": SEED_NAMESPACE,
        "generator_version": state.config.generator_version,
        "parameter_checksum": state.parameter_checksum,
        "namespace_key_checksum": _sha16({"namespace_key": state.namespace_key}),
        "terrain_meta_used": False,
        "terrain_seed_used": False,
        "global_rng_used": False,
    }


def _require(world: Any) -> SurfaceColumnState:
    state = state_of(world)
    if state is None:
        raise SurfaceColumnValidationError("procedural surface columns are not active in this world")
    return state


def wrap_cell(state: SurfaceColumnState, x: Any, y: Any) -> tuple[int, int]:
    cx = int(math.floor(float(x)))
    cy = int(math.floor(float(y)))
    return int(wrap_coord(cx, state.width)), int(wrap_coord(cy, state.height))


def _remember(world: Any, state: SurfaceColumnState, event: dict[str, Any]) -> None:
    state.history.append(event)
    # Researcher-only capture hook (Scientific V3); never part of snapshot or cognition.
    try:
        world.last_surface_column_event = {**event, "world_tick": int(getattr(world, "tick", 0) or 0)}
    except Exception:  # pragma: no cover - defensive for frozen test doubles
        pass
    if len(state.history) > HISTORY_LIMIT:
        del state.history[: len(state.history) - HISTORY_LIMIT]


def _event(name: str, **payload: Any) -> dict[str, Any]:
    out = {"event": name}
    out.update(payload)
    out.update(EFFECT_FLAGS)
    return out


# ---------------------------------------------------------------------------
# Query API
# ---------------------------------------------------------------------------


def baseline_column_at(world: Any, x: Any, y: Any, *, record: bool = False, reason: str = "") -> SurfaceColumnBaseline:
    state = _require(world)
    cell = wrap_cell(state, x, y)
    state.baseline_query_count += 1
    cached = state.cache.get(cell)
    if cached is not None:
        state.cache.move_to_end(cell)
        column = cached
    else:
        gen = GENERATORS[state.config.generator_version]
        column = gen(
            world_seed=state.world_seed, cell_x=cell[0], cell_y=cell[1],
            width=state.width, height=state.height, cfg=state.config, key=state.namespace_key,
        )
        state.cache[cell] = column
        while len(state.cache) > int(state.config.cache_limit):
            state.cache.popitem(last=False)
            state.cache_evictions += 1
    if record:
        _record_query(world, state, column, reason=reason)
    return column


def resolved_column_at(world: Any, x: Any, y: Any, *, record: bool = False, reason: str = "") -> dict[str, Any]:
    state = _require(world)
    base = baseline_column_at(world, x, y, record=record, reason=reason)
    delta = deltas_of(world).get((base.cell_x, base.cell_y))
    if delta is None:
        layers = base.layers
        elevation = base.surface_elevation
        resolved_checksum = base.baseline_checksum
    else:
        layers = delta.resulting_layers
        elevation = delta.resulting_surface_elevation
        resolved_checksum = delta.resolved_checksum()
    return {
        "cell_x": base.cell_x,
        "cell_y": base.cell_y,
        "surface_elevation": float(elevation),
        "surface_elevation_status": SURFACE_ELEVATION_STATUS,
        "geometry_role": GEOMETRY_ROLE,
        "authority": AUTHORITY,
        "physical_effects_active": False,
        "agent_accessible": False,
        "modelled_depth": resolved_modelled_depth_for(base, elevation),
        "layers": layers,
        "generator_version": base.generator_version,
        "baseline_checksum": base.baseline_checksum,
        "resolved_checksum": resolved_checksum,
        "has_persistent_delta": delta is not None,
        "delta_id": None if delta is None else delta.delta_id,
        "delta_revision": 0 if delta is None else int(delta.revision),
        "source": "PROCEDURAL_BASELINE" if delta is None else "PROCEDURAL_BASELINE_PLUS_SPARSE_DELTA",
    }


def resolved_column_dict(column: dict[str, Any]) -> dict[str, Any]:
    out = dict(column)
    out["layers"] = [layer.as_dict() for layer in column["layers"]]
    return out


def material_at_depth(world: Any, x: Any, y: Any, depth: float) -> dict[str, Any]:
    """Depth measured downward from local surface. [top, bottom) per layer."""
    column = resolved_column_at(world, x, y)
    d = float(depth)
    base = {"cell_x": column["cell_x"], "cell_y": column["cell_y"], "depth": d, "boundary_policy": BOUNDARY_POLICY}
    if not math.isfinite(d):
        return {**base, "status": STATUS_NOT_MODELLED, "layer_index": None, "layer": None}
    if d < 0.0:
        return {**base, "status": STATUS_ABOVE_SURFACE, "material": False, "layer_index": None, "layer": None}
    for i, layer in enumerate(column["layers"]):
        if layer.top_depth <= d < layer.bottom_depth:
            return {**base, "status": STATUS_MATERIAL, "material": True, "layer_index": i, "layer": layer.as_dict()}
    return {**base, "status": STATUS_NOT_MODELLED, "material": False, "layer_index": None, "layer": None}


def column_mass_summary(world: Any, x: Any, y: Any) -> dict[str, Any]:
    column = resolved_column_at(world, x, y)
    out = mass_summary(column["layers"])
    out.update({"cell_x": column["cell_x"], "cell_y": column["cell_y"], "resolved_checksum": column["resolved_checksum"]})
    return out


def has_persistent_delta(world: Any, x: Any, y: Any) -> bool:
    state = _require(world)
    return wrap_cell(state, x, y) in deltas_of(world)


def _record_query(world: Any, state: SurfaceColumnState, column: SurfaceColumnBaseline, *, reason: str) -> None:
    state.recorded_query_count += 1
    delta = deltas_of(world).get((column.cell_x, column.cell_y))
    layers = column.layers if delta is None else delta.resulting_layers
    elevation = column.surface_elevation if delta is None else delta.resulting_surface_elevation
    summary = mass_summary(layers)
    _remember(world, state, _event(
        EVENT_BASELINE_QUERIED,
        cell=[column.cell_x, column.cell_y],
        generator_version=column.generator_version,
        baseline_checksum=column.baseline_checksum,
        resolved_checksum=column.baseline_checksum if delta is None else delta.resolved_checksum(),
        delta_id=None if delta is None else delta.delta_id,
        delta_revision=0 if delta is None else delta.revision,
        mass_per_area=summary["total_mass_per_area"],
        quantity_per_area=summary["total_quantity_per_area"],
        component_quantity_per_area=summary["component_quantity_per_area"],
        interval_validation=validate_layers(layers, resolved_modelled_depth_for(column, elevation))["verified"],
        reason=str(reason or "explicit_probe"),
        provenance="RESEARCHER_PROBE",
    ))


# ---------------------------------------------------------------------------
# Controlled setup delta (researcher/test only; not a motor command)
# ---------------------------------------------------------------------------


def _transfer_layers(
    layers: tuple[SurfaceMaterialLayer, ...], upper_index: int, quantity: float
) -> tuple[SurfaceMaterialLayer, ...]:
    """Move `quantity` of layer upper_index+1 material up into layer upper_index.

    The shared boundary moves down by `quantity`. The moved material keeps its
    composition fractions and mass per quantity, so total depth, total mass,
    total quantity and every component are conserved inside the column.
    """
    upper = layers[upper_index]
    lower = layers[upper_index + 1]
    q = float(quantity)
    frac = q / lower.thickness
    moved = [(cid, amount * frac) for cid, amount in lower.composition]
    remaining = [(cid, amount - m) for (cid, amount), (_, m) in zip(lower.composition, moved)]
    new_boundary = upper.bottom_depth + q
    upper_mass = upper.mass_per_area + q * lower.density
    upper_thickness = new_boundary - upper.top_depth
    new_upper = SurfaceMaterialLayer(
        top_depth=upper.top_depth,
        bottom_depth=new_boundary,
        thickness=upper_thickness,
        density=upper_mass / upper_thickness,
        composition=_canonical_composition(list(upper.composition) + moved),
        material_property_derivation_version=upper.material_property_derivation_version,
    )
    new_lower = SurfaceMaterialLayer(
        top_depth=new_boundary,
        bottom_depth=lower.bottom_depth,
        thickness=lower.bottom_depth - new_boundary,
        density=lower.density,
        composition=_canonical_composition(remaining),
        material_property_derivation_version=lower.material_property_derivation_version,
    )
    out = list(layers)
    out[upper_index] = new_upper
    out[upper_index + 1] = new_lower
    return tuple(out)


TRANSFER_PROVENANCE_KEYS = (
    "last_transfer_id", "transfer_role", "opposite_cell", "previous_delta_revision",
    "baseline_checksum", "transfer_refs", "net_exchange",
)


def net_exchange_verified(base: SurfaceColumnBaseline, delta: SurfaceColumnDelta, tol: float = 1e-9) -> bool:
    """resolved - baseline == recorded net exchange (mass, quantity, components, elevation)."""
    net = (delta.provenance or {}).get("net_exchange")
    if not isinstance(net, dict):
        return False
    sb, sa = mass_summary(base.layers), mass_summary(delta.resulting_layers)
    q = float(net.get("quantity_per_area", 0.0))
    res = [
        (sa["total_mass_per_area"] - sb["total_mass_per_area"]) - float(net.get("mass_per_area", 0.0)),
        (sa["total_quantity_per_area"] - sb["total_quantity_per_area"]) - q,
        (float(delta.resulting_surface_elevation) - float(base.surface_elevation)) - q,
    ]
    comps = net.get("component_quantity_per_area") or {}
    for cid in set(sb["component_quantity_per_area"]) | set(sa["component_quantity_per_area"]) | set(comps):
        res.append(float(sa["component_quantity_per_area"].get(cid, 0.0))
                   - float(sb["component_quantity_per_area"].get(cid, 0.0)) - float(comps.get(cid, 0.0)))
    return all(math.isfinite(v) and abs(v) <= tol for v in res)


def delta_id_for(cell_x: int, cell_y: int) -> str:
    return f"surface-column-delta-x{int(cell_x)}-y{int(cell_y)}"


def apply_surface_column_setup_delta(
    world: Any,
    x: Any,
    y: Any,
    *,
    upper_layer_index: int,
    transfer_quantity: float,
    expected_revision: int,
    tick: int,
    researcher_id: str = "researcher",
    reason: str = "controlled_setup",
) -> dict[str, Any]:
    """Researcher setup adapter. Preflight, atomic commit, revision, conservation.

    Not in motor vocabulary. Not cognition-accessible. Not an endogenous action.
    Returns a WORLD_MATERIAL_TRANSACTION-compatible receipt.
    """
    state = _require(world)
    cell = wrap_cell(state, x, y)
    sequence = state.transaction_sequence
    state.transaction_sequence = sequence + 1
    transaction_id = f"surface-column-tx-{int(tick):09d}-{sequence:04d}"
    deltas = deltas_of(world)
    current = deltas.get(cell)
    current_revision = 0 if current is None else int(current.revision)
    base = baseline_column_at(world, cell[0], cell[1], record=True, reason="delta_preflight")
    before_layers = base.layers if current is None else current.resulting_layers
    before_elevation = base.surface_elevation if current is None else current.resulting_surface_elevation
    before_checksum = base.baseline_checksum if current is None else current.resolved_checksum()
    receipt = {
        "event": EVENT_DELTA_COMMITTED,
        "transaction_event_schema": "WORLD_MATERIAL_TRANSACTION",
        "transaction_id": transaction_id,
        "schema_version": TRANSACTION_SCHEMA,
        "tick": int(tick),
        "sequence": int(sequence),
        "operation_kind": OPERATION_KIND,
        "command": None,
        "actor_body_id": None,
        "actor_agent_id": None,
        "researcher_id": str(researcher_id),
        "provenance_kind": PROVENANCE_KIND,
        "not_agent_action": True,
        "endogenous_action": False,
        "motor_vocabulary": False,
        "cell": [cell[0], cell[1]],
        "input_refs": [f"surface-column:x{cell[0]}-y{cell[1]}"],
        "output_refs": [delta_id_for(*cell)],
        "expected_revisions": {delta_id_for(*cell): int(expected_revision)},
        "generator_version": base.generator_version,
        "baseline_checksum": base.baseline_checksum,
        "resolved_checksum_before": before_checksum,
        "legacy_equivalence": True,
        "semantic_effects": False,
        "recipe_match": False,
        "reward_created": False,
        "reason": str(reason),
    }
    receipt.update(EFFECT_FLAGS)

    def reject(why: str) -> dict[str, Any]:
        receipt.update({"status": "REJECTED", "rejection_reason": why, "event": EVENT_VALIDATION_FAILED,
                        "resolved_checksum_after": before_checksum})
        state.validation_failure_count += 1
        _remember(world, state, dict(receipt))
        return receipt

    if int(expected_revision) != current_revision:
        return reject(f"stale_revision:expected={int(expected_revision)}:actual={current_revision}")
    i = int(upper_layer_index)
    if not (0 <= i < len(before_layers) - 1):
        return reject("invalid_layer_index")
    q = float(transfer_quantity)
    lower = before_layers[i + 1]
    if not (math.isfinite(q) and q > 0.0 and q < lower.thickness):
        return reject("invalid_transfer_quantity")
    if current is None and len(deltas) >= MAX_DELTAS:
        return reject("delta_capacity_exceeded")
    after_layers = _transfer_layers(before_layers, i, q)
    validation = validate_layers(after_layers, resolved_modelled_depth_for(base, before_elevation))
    before_summary = mass_summary(before_layers)
    after_summary = mass_summary(after_layers)
    conservation = conservation_between(before_summary, after_summary)
    receipt.update({
        "preconditions": {"revision_ok": True, "layer_index_ok": True, "quantity_ok": True},
        "interval_validation": validation,
        "conservation": conservation,
        "before": before_summary,
        "after": after_summary,
    })
    if not validation["verified"]:
        return reject("interval_validation_failed")
    if not conservation["verified"]:
        return reject("conservation_failed")
    # Atomic commit: build the full record, then publish with a single assignment.
    prev_prov = dict(current.provenance) if current is not None else {}
    tx_ids = (list(current.source_transaction_ids) if current is not None else []) + [transaction_id]
    record = SurfaceColumnDelta(
        delta_id=delta_id_for(*cell),
        cell_x=cell[0],
        cell_y=cell[1],
        baseline_generator_version=base.generator_version,
        baseline_checksum=base.baseline_checksum,
        resulting_surface_elevation=float(before_elevation),
        resulting_layers=after_layers,
        created_tick=int(current.created_tick if current is not None else tick),
        last_updated_tick=int(tick),
        revision=current_revision + 1,
        source_transaction_ids=tx_ids[-PROVENANCE_LIMIT:],
        provenance={
            "kind": PROVENANCE_KIND,
            "researcher_only": True,
            "not_agent_action": True,
            "researcher_id": str(researcher_id),
            "last_transaction_id": transaction_id,
            "creation_tick": int(prev_prov.get("creation_tick", tick)),
            "operation_kind": OPERATION_KIND,
            # Transfer provenance (only present on columns touched by a column transfer) is carried
            # over unchanged: a setup delta is internal to the column and exchanges nothing.
            **{k: prev_prov[k] for k in TRANSFER_PROVENANCE_KEYS if k in prev_prov},
        },
    )
    deltas[cell] = record
    world.surface_column_deltas = deltas
    receipt.update({
        "status": "COMMITTED",
        "rejection_reason": None,
        "delta_id": record.delta_id,
        "delta_revision": record.revision,
        "resolved_checksum_after": record.resolved_checksum(),
        "surface_elevation_changed": False,
    })
    _remember(world, state, dict(receipt))
    return receipt


# ---------------------------------------------------------------------------
# Snapshot / restore
# ---------------------------------------------------------------------------


def serialize_surface_columns(world: Any) -> dict[str, Any] | None:
    state = state_of(world)
    if state is None:
        return None
    deltas = deltas_of(world)
    out = {
        "schema": SNAPSHOT_SCHEMA,
        "config": state.config.to_dict(),
        "world_seed": int(state.world_seed),
        "seed_provenance": seed_provenance(state),
        "generator_version": state.config.generator_version,
        "width": int(state.width),
        "height": int(state.height),
        "parameter_checksum": state.parameter_checksum,
        "manifest": dict(state.manifest),
        "deltas": [deltas[key].as_dict() for key in sorted(deltas)],
        "transaction_sequence": int(state.transaction_sequence),
        "history": list(state.history)[-HISTORY_LIMIT:],
        "counters": {
            "baseline_query_count": int(state.baseline_query_count),
            "recorded_query_count": int(state.recorded_query_count),
            "validation_failure_count": int(state.validation_failure_count),
        },
    }
    if state.transfer is not None:
        from mechanistic_mind.physical_system.conservative_surface_column_transfer import serialize_transfer_state

        transfer = serialize_transfer_state(state)
        if transfer is not None:
            out["column_transfer"] = transfer
    return out


def restore_surface_columns(world: Any, data: dict[str, Any] | None, *, tick: int = 0) -> SurfaceColumnState | None:
    """Restore config/version/seed, then sparse deltas; validate every delta baseline."""
    if not isinstance(data, dict) or not data:
        world.surface_columns = None
        world.surface_column_deltas = {}
        return None
    version = str(data.get("generator_version") or (data.get("config") or {}).get("generator_version") or "")
    if version not in SUPPORTED_GENERATOR_VERSIONS:
        raise SurfaceColumnValidationError(
            f"{EVENT_VALIDATION_FAILED}: unknown surface column generator version {version!r}; "
            "refusing to apply sparse deltas to a different geology"
        )
    cfg = ProceduralSurfaceColumnsConfig.from_dict(data.get("config") or {})
    cfg.enabled = True
    if data.get("world_seed") is None or isinstance(data.get("world_seed"), bool):
        raise SurfaceColumnValidationError(f"{EVENT_VALIDATION_FAILED}: snapshot has no surface column world_seed")
    prov = data.get("seed_provenance")
    if not isinstance(prov, dict) or prov.get("schema") != SEED_PROVENANCE_SCHEMA:
        raise SurfaceColumnValidationError(f"{EVENT_VALIDATION_FAILED}: missing or unknown seed provenance")
    if prov.get("authority") != SEED_AUTHORITY or prov.get("seed_source") != SEED_SOURCE:
        raise SurfaceColumnValidationError(
            f"{EVENT_VALIDATION_FAILED}: unsupported seed source {prov.get('seed_source')!r}"
        )
    if int(prov.get("world_seed", -1)) != int(data["world_seed"]):
        raise SurfaceColumnValidationError(f"{EVENT_VALIDATION_FAILED}: seed provenance world_seed mismatch")
    state = initialize_surface_columns(world, cfg, world_seed=int(data["world_seed"]), seed_source=SEED_SOURCE)
    if seed_provenance(state) != prov:
        raise SurfaceColumnValidationError(f"{EVENT_VALIDATION_FAILED}: seed provenance does not re-derive")
    if (int(data.get("width", state.width)), int(data.get("height", state.height))) != (state.width, state.height):
        raise SurfaceColumnValidationError(f"{EVENT_VALIDATION_FAILED}: world shape mismatch")
    if str(data.get("parameter_checksum") or state.parameter_checksum) != state.parameter_checksum:
        raise SurfaceColumnValidationError(f"{EVENT_VALIDATION_FAILED}: generator parameter checksum mismatch")
    saved_manifest = data.get("manifest") or {}
    manifest_ok = str(saved_manifest.get("manifest_checksum") or "") == str(state.manifest["manifest_checksum"])
    if saved_manifest and not manifest_ok:
        raise SurfaceColumnValidationError(f"{EVENT_VALIDATION_FAILED}: baseline manifest checksum mismatch")
    deltas: dict[tuple[int, int], SurfaceColumnDelta] = {}
    restored_rows = []
    for row in data.get("deltas") or []:
        delta = SurfaceColumnDelta.from_dict(row)
        if delta.baseline_generator_version not in SUPPORTED_GENERATOR_VERSIONS:
            raise SurfaceColumnValidationError(
                f"{EVENT_VALIDATION_FAILED}: delta {delta.delta_id} references unknown generator "
                f"{delta.baseline_generator_version!r}"
            )
        base = generate_baseline_v1(
            world_seed=state.world_seed, cell_x=delta.cell_x, cell_y=delta.cell_y,
            width=state.width, height=state.height, cfg=state.config, key=state.namespace_key,
        )
        if base.baseline_checksum != delta.baseline_checksum:
            raise SurfaceColumnValidationError(
                f"{EVENT_VALIDATION_FAILED}: delta {delta.delta_id} baseline checksum mismatch"
            )
        validation = validate_layers(
            delta.resulting_layers, resolved_modelled_depth_for(base, delta.resulting_surface_elevation)
        )
        if not validation["verified"]:
            raise SurfaceColumnValidationError(
                f"{EVENT_VALIDATION_FAILED}: delta {delta.delta_id} layer validation failed {validation['problems']}"
            )
        saved_resolved = row.get("resolved_checksum")
        if saved_resolved and str(saved_resolved) != delta.resolved_checksum():
            raise SurfaceColumnValidationError(
                f"{EVENT_VALIDATION_FAILED}: delta {delta.delta_id} resolved checksum mismatch"
            )
        if isinstance((delta.provenance or {}).get("net_exchange"), dict):
            # Transfer-touched column: open system; verify against its recorded net exchange.
            conservation = {"verified": net_exchange_verified(base, delta)}
        else:
            conservation = conservation_between(mass_summary(base.layers), mass_summary(delta.resulting_layers))
        deltas[(delta.cell_x, delta.cell_y)] = delta
        restored_rows.append({
            "delta_id": delta.delta_id,
            "revision": delta.revision,
            "resolved_checksum": delta.resolved_checksum(),
            "baseline_checksum_verified": True,
            "conservation_vs_baseline_verified": bool(conservation["verified"]),
        })
    world.surface_column_deltas = deltas
    state.transaction_sequence = int(data.get("transaction_sequence", 0) or 0)
    state.history = [dict(item) for item in (data.get("history") or [])][-HISTORY_LIMIT:]
    counters = data.get("counters") or {}
    state.baseline_query_count = int(counters.get("baseline_query_count", 0) or 0)
    state.recorded_query_count = int(counters.get("recorded_query_count", 0) or 0)
    state.validation_failure_count = int(counters.get("validation_failure_count", 0) or 0)
    state.restored_delta_count = len(deltas)
    state.restore_verification = {
        "status": "VERIFIED",
        "manifest_checksum_verified": bool(manifest_ok or not saved_manifest),
        "seed_provenance_verified": True,
        "world_seed": int(state.world_seed),
        "delta_count": len(deltas),
        "deltas": restored_rows[:HISTORY_LIMIT],
    }
    for row in restored_rows[:4]:
        _remember(world, state, _event(
            EVENT_DELTA_RESTORED, tick=int(tick), delta_id=row["delta_id"], delta_revision=row["revision"],
            resolved_checksum=row["resolved_checksum"], baseline_checksum_verified=True,
            generator_version=state.config.generator_version, provenance="SNAPSHOT_RESTORE",
        ))
    transfer_data = data.get("column_transfer")
    if transfer_data:
        from mechanistic_mind.physical_system.conservative_surface_column_transfer import restore_transfer_state

        restore_transfer_state(world, state, transfer_data, tick=int(tick))
    return state


def copy_state(src: Any, dst: Any) -> None:
    """Used by PlanetState.copy(): deltas are immutable records; cache is not copied."""
    state = state_of(src)
    if state is None:
        return
    clone = SurfaceColumnState(
        config=ProceduralSurfaceColumnsConfig.from_dict(state.config.to_dict()),
        world_seed=state.world_seed,
        width=state.width,
        height=state.height,
        parameter_checksum=state.parameter_checksum,
        namespace_key=state.namespace_key,
        manifest=dict(state.manifest),
        transaction_sequence=state.transaction_sequence,
        history=[dict(item) for item in state.history],
        baseline_query_count=state.baseline_query_count,
        recorded_query_count=state.recorded_query_count,
        validation_failure_count=state.validation_failure_count,
        restored_delta_count=state.restored_delta_count,
        restore_verification=dict(state.restore_verification),
        seed_source=state.seed_source,
    )
    dst.surface_columns = clone
    dst.surface_column_deltas = {
        key: SurfaceColumnDelta.from_dict(delta.as_dict()) for key, delta in deltas_of(src).items()
    }
    if state.transfer is not None:
        from mechanistic_mind.physical_system.conservative_surface_column_transfer import copy_transfer_state

        copy_transfer_state(state, clone)


# ---------------------------------------------------------------------------
# Researcher summaries
# ---------------------------------------------------------------------------


def deltas_checksum(world: Any) -> str:
    deltas = deltas_of(world)
    return _sha16([deltas[key].as_dict() for key in sorted(deltas)])


def storage_summary(world: Any) -> dict[str, Any]:
    state = state_of(world)
    if state is None:
        return {"active": False}
    deltas = deltas_of(world)
    return {
        "active": True,
        "materialized_baseline_storage_count": len(state.cache),
        "cache_limit": int(state.config.cache_limit),
        "cache_evictions": int(state.cache_evictions),
        "sparse_delta_count": len(deltas),
        "modified_cell_count": len(deltas),
        "baseline_query_count": int(state.baseline_query_count),
        "recorded_query_count": int(state.recorded_query_count),
        "dense_volume_cells_if_materialized": int(state.width) * int(state.height) * len(state.config.thickness_fractions),
        "dense_3d_volume_allocated": False,
        "cache_serialized": False,
        "cache_authority": "DERIVED_NON_AUTHORITATIVE",
    }


def cell_inspection(world: Any, x: Any, y: Any) -> dict[str, Any] | None:
    """Researcher-only Observer cell summary. Emits one bounded query receipt."""
    if state_of(world) is None:
        return None
    column = resolved_column_at(world, x, y, record=True, reason="observer_cell_inspection")
    out = resolved_column_dict(column)
    out.update({
        "layer_count": len(column["layers"]),
        "persistent_delta": bool(column["has_persistent_delta"]),
        **EFFECT_FLAGS,
        "researcher_only_view": True,
        "not_agent_accessible": True,
        "geometry_metadata_only": True,
        "no_support_gravity_effect": True,
        "representation": "procedural baseline + sparse delta",
        "source_kind": "SURFACE_COLUMN_SUMMARY",
    })
    if state_of(world).transfer is not None:
        from mechanistic_mind.physical_system.conservative_surface_column_transfer import cell_transfer_view

        out["column_transfer"] = cell_transfer_view(world, x, y)
    return out


def researcher_payload(world: Any) -> dict[str, Any]:
    state = state_of(world)
    if state is None:
        return {}
    deltas = deltas_of(world)
    out = {
        "surface_columns": {
            "mechanism": MECHANISM_ID,
            "generator_version": state.config.generator_version,
            "modelled_depth": float(state.config.modelled_depth),
            "manifest_checksum": state.manifest.get("manifest_checksum"),
            "seed_provenance": seed_provenance(state),
            "sparse_delta_count": len(deltas),
            "delta_cells": [[k[0], k[1]] for k in sorted(deltas)][:64],
            "deltas_checksum": deltas_checksum(world),
            "surface_elevation_status": SURFACE_ELEVATION_STATUS,
            "receipts": list(state.history)[-HISTORY_LIMIT:],
            **EFFECT_FLAGS,
            "researcher_only_view": True,
            "not_agent_accessible": True,
            "geometry_metadata_only": True,
            "no_support_gravity_effect": True,
            "representation": "procedural baseline + sparse delta",
        }
    }
    if state.transfer is not None:
        from mechanistic_mind.physical_system.conservative_surface_column_transfer import researcher_summary

        out["column_transfer"] = researcher_summary(world)
    return out


def procedural_surface_columns_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "procedural_surface_columns.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "description": (
            "Authoritative world-simulation surface columns: deterministic procedural baseline "
            "plus sparse persistent deltas. physical_effects_active=false. not agent-accessible. "
            "geometry_role=METADATA_ONLY. no support/gravity effect. Observer view is researcher-only."
        ),
    }
