"""Acanthostega O2 · Exposed surface optical interaction authority V1.

Schema: EXPOSED_SURFACE_OPTICAL_INTERACTION_AUTHORITY_V1
Capability: exposed_surface_optical_interaction_authority
Profile: VW1_OCCUPIED_FREE_BOUNDARY_FACETS_O2_V1
Authority: AUTHORITATIVE_DERIVATION_FROM_VW1_OCCUPANCY_READ_ONLY

Derives read-only exposed facets where VW1 occupied volumes meet free space.
Links each facet to O1 material optical profile via owning interval composition.

Does **not** illuminate, shade, render brightness, or feed cognition.
Does **not** treat every occupied prism as exposed.
Does **not** invent dense voxels or use VW7 meshes as authority.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from mechanistic_mind.planet.topology import wrap_coord

SCHEMA = "EXPOSED_SURFACE_OPTICAL_INTERACTION_AUTHORITY_V1"
CAPABILITY = "exposed_surface_optical_interaction_authority"
PROFILE = "VW1_OCCUPIED_FREE_BOUNDARY_FACETS_O2_V1"
AUTHORITY = "AUTHORITATIVE_DERIVATION_FROM_VW1_OCCUPANCY_READ_ONLY"
MECHANISM_ID = CAPABILITY
TOLERANCE = 1e-12
CELL_EDGE = 1.0
CELL_AREA = 1.0

FACE_TOP = "TOP"
FACE_BOTTOM = "BOTTOM"
FACE_NORTH = "NORTH"
FACE_SOUTH = "SOUTH"
FACE_EAST = "EAST"
FACE_WEST = "WEST"
FACE_CLASSES = (FACE_TOP, FACE_BOTTOM, FACE_NORTH, FACE_SOUTH, FACE_EAST, FACE_WEST)
FACE_RANK = {
    FACE_TOP: 0,
    FACE_BOTTOM: 1,
    FACE_NORTH: 2,
    FACE_SOUTH: 3,
    FACE_EAST: 4,
    FACE_WEST: 5,
}
# Neighbor (d_cell_x, d_cell_y) and outward normal (nx, ny, nz)
FACE_NEIGHBOR = {
    FACE_EAST: (1, 0, 1.0, 0.0, 0.0),
    FACE_WEST: (-1, 0, -1.0, 0.0, 0.0),
    FACE_SOUTH: (0, 1, 0.0, 1.0, 0.0),
    FACE_NORTH: (0, -1, 0.0, -1.0, 0.0),
}

WORLD_Z_BOUNDARY_POLICY = {
    "z_periodic": False,
    "below_lowest_interval": "OPEN_FREE_SPACE",
    "above_highest_interval": "OPEN_FREE_SPACE",
    "note": "Bottoms of lowest and tops of highest intervals are exposed to open free space.",
}

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "vw1_occupancy_reused": True,
    "second_occupancy_representation": False,
    "dense_voxel_world": False,
    "light_transport": False,
    "organism_reception": False,
    "agent_accessible": False,
    "researcher_only": True,
    "behaviorally_dormant_without_light_consumer": True,
    "detached_object_surface_scope": "DEFERRED_PRE_O3_EXTENSION",
    "body_surface_scope": "DEFERRED_PRE_O3_EXTENSION",
    "held_object_surface_scope": "DEFERRED_PRE_O3_EXTENSION",
    "world_z_boundary_policy": WORLD_Z_BOUNDARY_POLICY,
}


@dataclass
class ExposedSurfaceOpticalInteractionAuthorityConfig:
    """Fresh default OFF. Missing snapshot keeps O2 OFF."""

    enabled: bool = False
    schema: str = SCHEMA
    profile: str = PROFILE

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "schema": str(self.schema),
            "profile": str(self.profile),
            **AUTHORITY_FLAGS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ExposedSurfaceOpticalInteractionAuthorityConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        return cls(
            enabled=bool(data.get("enabled", False)),
            schema=str(data.get("schema") or SCHEMA),
            profile=str(data.get("profile") or PROFILE),
        )


def exposed_surface_optical_interaction_authority_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "exposed_surface_optical_interaction_authority", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_exposed_surface_optical_interaction_authority(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "exposed_surface_optical_interaction_authority", None)
    if cur is None:
        config.exposed_surface_optical_interaction_authority = (
            ExposedSurfaceOpticalInteractionAuthorityConfig(enabled=on)
        )
    else:
        cur.enabled = on
        cur.schema = SCHEMA
        cur.profile = PROFILE


def exposed_surface_optical_interaction_authority_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": bool(enabled),
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "researcher_only": True,
        "agent_accessible": False,
        "light_transport": False,
        "summary": "VW1 occupied↔free exposed boundary facets (O2); dormant without light consumer.",
    }


def _fhex(value: float) -> str:
    return float(value).hex()


def _interval_id(cell_y: int, cell_x: int, z_min: float, z_max: float) -> str:
    return f"I|{int(cell_y)}|{int(cell_x)}|{_fhex(float(z_min))}|{_fhex(float(z_max))}"


def _facet_id(
    face: str,
    interval_id: str,
    span_lo: float,
    span_hi: float,
) -> str:
    return f"F|{face}|{interval_id}|{_fhex(float(span_lo))}|{_fhex(float(span_hi))}"


def _subtract_spans(
    spans: list[tuple[float, float]], cover_lo: float, cover_hi: float
) -> list[tuple[float, float]]:
    """Remove (cover_lo, cover_hi] coverage from spans [lo, hi] (exclusive-open style ends)."""
    out: list[tuple[float, float]] = []
    a = float(cover_lo)
    b = float(cover_hi)
    for lo, hi in spans:
        lo = float(lo)
        hi = float(hi)
        if hi <= lo + TOLERANCE:
            continue
        if b <= lo + TOLERANCE or a >= hi - TOLERANCE:
            out.append((lo, hi))
            continue
        if a > lo + TOLERANCE:
            out.append((lo, min(hi, a)))
        if b < hi - TOLERANCE:
            out.append((max(lo, b), hi))
    return [(lo, hi) for lo, hi in out if hi > lo + TOLERANCE]


def _exposed_side_spans(
    z_min: float, z_max: float, neighbor_intervals: tuple[Any, ...]
) -> list[tuple[float, float]]:
    spans = [(float(z_min), float(z_max))]
    for nit in neighbor_intervals:
        spans = _subtract_spans(spans, float(nit.z_min), float(nit.z_max))
    return spans


def _abuts(a_max: float, b_min: float) -> bool:
    return abs(float(a_max) - float(b_min)) <= TOLERANCE


def _intervals_at(world: Any, cx: int, cy: int) -> tuple[tuple[Any, ...], str]:
    """Read occupancy without relying on Observer mutation. Returns (intervals, provenance)."""
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        state_of,
        wrap_cell,
        _legacy_intervals_at,
    )

    state = state_of(world)
    if state is not None:
        cell = wrap_cell(state, cx, cy)
        col = state.columns.get(cell)
        if col is not None:
            return tuple(col.occupied_intervals), "VW1_SPARSE"
    legacy = _legacy_intervals_at(world, cx, cy)
    if legacy is not None:
        return tuple(legacy), "VW1_LEGACY_PSC_DERIVATION"
    return (), "EMPTY"


def _o1_link(interval: Any) -> dict[str, Any]:
    from mechanistic_mind.physical_system.physical_optical_material_profile import (
        PROFILE as O1_PROFILE,
        SCHEMA as O1_SCHEMA,
        resolve_occupied_interval_profile,
    )

    resolved = resolve_occupied_interval_profile(interval)
    return {
        "o1_schema": O1_SCHEMA,
        "o1_profile": O1_PROFILE,
        "o1_registry_version": resolved.get("registry_version"),
        "o1_status": resolved.get("status"),
        "o1_compatibility": resolved.get("compatibility"),
        "spectral_reflectance": resolved.get("spectral_reflectance"),
        "composition": [
            {"component_id": cid, "quantity_per_area": float(amt)}
            for cid, amt in (getattr(interval, "composition", ()) or ())
        ],
        "geometry_valid_if_profile_unknown": True,
    }


def _make_facet(
    *,
    face: str,
    cell_x: int,
    cell_y: int,
    interval: Any,
    interval_index: int,
    span_lo: float,
    span_hi: float,
    occupancy_digest: str,
    provenance: str,
    nx: float,
    ny: float,
    nz: float,
    cx: float,
    cy: float,
    cz: float,
    area: float,
    plane_coord: float,
    plane_axis: str,
) -> dict[str, Any]:
    z0 = float(interval.z_min)
    z1 = float(interval.z_max)
    iid = _interval_id(cell_y, cell_x, z0, z1)
    fid = _facet_id(face, iid, span_lo, span_hi)
    if not (math.isfinite(area) and area > TOLERANCE):
        raise ValueError("facet area must be positive and finite")
    for v in (nx, ny, nz, cx, cy, cz, plane_coord, span_lo, span_hi):
        if not math.isfinite(float(v)):
            raise ValueError("facet geometry must be finite")
    link = _o1_link(interval)
    return {
        "facet_id": fid,
        "vw1_occupancy_digest": str(occupancy_digest),
        "cell_x": int(cell_x),
        "cell_y": int(cell_y),
        "interval_id": iid,
        "interval_index": int(interval_index),
        "interval_z_min": z0,
        "interval_z_max": z1,
        "face_class": face,
        "face_rank": int(FACE_RANK[face]),
        "centre": [float(cx), float(cy), float(cz)],
        "outward_unit_normal": [float(nx), float(ny), float(nz)],
        "area": float(area),
        "boundary_plane_axis": plane_axis,
        "boundary_plane_coordinate": float(plane_coord),
        "span_lower": float(span_lo),
        "span_upper": float(span_hi),
        "material_composition_reference": link["composition"],
        "o1_schema": link["o1_schema"],
        "o1_profile": link["o1_profile"],
        "o1_registry_version": link["o1_registry_version"],
        "o1_status": link["o1_status"],
        "compatibility_state": link["o1_compatibility"],
        "provenance_class": provenance,
        "geometry_valid_if_profile_unknown": True,
        "not_display_rgb": True,
        "not_illumination": True,
        "not_agent_accessible": True,
        "researcher_only": True,
    }


def _geology_cache_token(world: Any) -> str:
    """Identity of PSC baseline+deltas that affect legacy-derived occupancy."""
    from mechanistic_mind.physical_system import procedural_surface_columns as psc

    st = psc.state_of(world)
    if st is None:
        return "psc:none"
    deltas = psc.deltas_of(world)
    delta_rows = []
    for key in sorted(deltas):
        d = deltas[key]
        delta_rows.append(
            {
                "cell": [int(key[0]), int(key[1])],
                "resolved": str(getattr(d, "resolved_checksum", lambda: "")()),
            }
        )
        # SurfaceColumnDelta has resolved_checksum method
        try:
            delta_rows[-1]["resolved"] = str(d.resolved_checksum())
        except Exception:
            delta_rows[-1]["resolved"] = str(getattr(d, "baseline_checksum", ""))
    payload = {
        "parameter_checksum": str(getattr(st, "parameter_checksum", "")),
        "world_seed": int(getattr(st, "world_seed", 0) or 0),
        "deltas": delta_rows,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def occupancy_cache_key(world: Any, *, o1_registry_version: str) -> dict[str, str]:
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

    state = state_of(world)
    if state is None:
        vw1 = "vw1:absent"
        shape = "0x0"
    else:
        vw1 = str(state.digest())
        shape = f"{int(state.width)}x{int(state.height)}"
    return {
        "o2_schema": SCHEMA,
        "o2_profile": PROFILE,
        "vw1_digest": vw1,
        "geology_token": _geology_cache_token(world),
        "world_shape": shape,
        "o1_registry_version": str(o1_registry_version),
    }


def _cache_key_digest(parts: dict[str, str]) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class ExposedSurfaceCache:
    key_digest: str
    key_parts: dict[str, str]
    facets: tuple[dict[str, Any], ...]
    facet_checksum: str
    counts_by_face: dict[str, int]
    o1_status_counts: dict[str, int]
    build_count: int = 0
    hit_count: int = 0
    miss_count: int = 0


WORLD_CACHE_ATTR = "_o2_exposed_surface_cache"


def _facet_set_checksum(facets: Iterable[dict[str, Any]]) -> str:
    ids = [str(f["facet_id"]) for f in facets]
    raw = json.dumps(ids, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _world_shape(world: Any) -> tuple[int, int]:
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

    state = state_of(world)
    if state is not None:
        return int(state.width), int(state.height)
    grid = getattr(world, "T", None)
    if grid is None:
        return 32, 32
    # T is (H, W) = (y, x)
    return int(grid.shape[1]), int(grid.shape[0])


def build_exposed_facets(world: Any, *, o1_registry_version: str | None = None) -> ExposedSurfaceCache:
    from mechanistic_mind.physical_system.physical_optical_material_profile import (
        REGISTRY_VERSION,
        STATUS_INVALID,
        STATUS_LEGACY,
        STATUS_RESOLVED,
        STATUS_UNKNOWN,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

    reg = str(o1_registry_version or REGISTRY_VERSION)
    key_parts = occupancy_cache_key(world, o1_registry_version=reg)
    key_digest = _cache_key_digest(key_parts)
    width, height = _world_shape(world)
    vw1_digest = key_parts["vw1_digest"]

    facets: list[dict[str, Any]] = []
    # Enumerate every cell; legacy or sparse. Equal neighbors suppress shared sides.
    for cy in range(height):
        for cx in range(width):
            intervals, provenance = _intervals_at(world, cx, cy)
            if not intervals:
                continue
            n_iv = len(intervals)
            for idx, it in enumerate(intervals):
                z0 = float(it.z_min)
                z1 = float(it.z_max)
                # TOP: exposed unless abutting next interval
                top_blocked = idx + 1 < n_iv and _abuts(z1, float(intervals[idx + 1].z_min))
                if not top_blocked:
                    facets.append(
                        _make_facet(
                            face=FACE_TOP,
                            cell_x=cx,
                            cell_y=cy,
                            interval=it,
                            interval_index=idx,
                            span_lo=z1,
                            span_hi=z1,
                            occupancy_digest=vw1_digest,
                            provenance=provenance,
                            nx=0.0,
                            ny=0.0,
                            nz=1.0,
                            cx=cx + 0.5,
                            cy=cy + 0.5,
                            cz=z1,
                            area=CELL_AREA,
                            plane_coord=z1,
                            plane_axis="z",
                        )
                    )
                # BOTTOM: exposed unless abutting previous
                bottom_blocked = idx > 0 and _abuts(float(intervals[idx - 1].z_max), z0)
                if not bottom_blocked:
                    facets.append(
                        _make_facet(
                            face=FACE_BOTTOM,
                            cell_x=cx,
                            cell_y=cy,
                            interval=it,
                            interval_index=idx,
                            span_lo=z0,
                            span_hi=z0,
                            occupancy_digest=vw1_digest,
                            provenance=provenance,
                            nx=0.0,
                            ny=0.0,
                            nz=-1.0,
                            cx=cx + 0.5,
                            cy=cy + 0.5,
                            cz=z0,
                            area=CELL_AREA,
                            plane_coord=z0,
                            plane_axis="z",
                        )
                    )
                # Side faces
                for face, (dx, dy, nx, ny, nz) in FACE_NEIGHBOR.items():
                    ncx = int(wrap_coord(cx + dx, width))
                    ncy = int(wrap_coord(cy + dy, height))
                    n_intervals, _ = _intervals_at(world, ncx, ncy)
                    for span_lo, span_hi in _exposed_side_spans(z0, z1, n_intervals):
                        height_span = float(span_hi) - float(span_lo)
                        area = height_span * CELL_EDGE
                        mid_z = 0.5 * (float(span_lo) + float(span_hi))
                        if face == FACE_EAST:
                            centre = (cx + 1.0, cy + 0.5, mid_z)
                            plane_coord = float(cx + 1)
                            plane_axis = "x"
                        elif face == FACE_WEST:
                            centre = (float(cx), cy + 0.5, mid_z)
                            plane_coord = float(cx)
                            plane_axis = "x"
                        elif face == FACE_SOUTH:
                            centre = (cx + 0.5, cy + 1.0, mid_z)
                            plane_coord = float(cy + 1)
                            plane_axis = "y"
                        else:  # NORTH
                            centre = (cx + 0.5, float(cy), mid_z)
                            plane_coord = float(cy)
                            plane_axis = "y"
                        facets.append(
                            _make_facet(
                                face=face,
                                cell_x=cx,
                                cell_y=cy,
                                interval=it,
                                interval_index=idx,
                                span_lo=span_lo,
                                span_hi=span_hi,
                                occupancy_digest=vw1_digest,
                                provenance=provenance,
                                nx=nx,
                                ny=ny,
                                nz=nz,
                                cx=centre[0],
                                cy=centre[1],
                                cz=centre[2],
                                area=area,
                                plane_coord=plane_coord,
                                plane_axis=plane_axis,
                            )
                        )

    facets.sort(
        key=lambda f: (
            int(f["cell_y"]),
            int(f["cell_x"]),
            float(f["interval_z_min"]),
            str(f["interval_id"]),
            int(f["face_rank"]),
            float(f["span_lower"]),
            float(f["span_upper"]),
            str(f["facet_id"]),
        )
    )
    counts = {fc: 0 for fc in FACE_CLASSES}
    o1_counts = {
        STATUS_RESOLVED: 0,
        STATUS_UNKNOWN: 0,
        STATUS_INVALID: 0,
        STATUS_LEGACY: 0,
    }
    for f in facets:
        counts[str(f["face_class"])] = counts.get(str(f["face_class"]), 0) + 1
        st = str(f.get("o1_status") or STATUS_INVALID)
        o1_counts[st] = o1_counts.get(st, 0) + 1

    return ExposedSurfaceCache(
        key_digest=key_digest,
        key_parts=key_parts,
        facets=tuple(facets),
        facet_checksum=_facet_set_checksum(facets),
        counts_by_face=counts,
        o1_status_counts=o1_counts,
        build_count=1,
        hit_count=0,
        miss_count=1,
    )


def ensure_exposed_surface_cache(world: Any, config: Any) -> ExposedSurfaceCache | None:
    if not exposed_surface_optical_interaction_authority_is_active(config):
        if hasattr(world, WORLD_CACHE_ATTR):
            setattr(world, WORLD_CACHE_ATTR, None)
        return None
    from mechanistic_mind.physical_system.physical_optical_material_profile import REGISTRY_VERSION
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        volumetric_world_material_occupancy_is_active,
    )

    if not volumetric_world_material_occupancy_is_active(config):
        return None

    key_parts = occupancy_cache_key(world, o1_registry_version=REGISTRY_VERSION)
    key_digest = _cache_key_digest(key_parts)
    cached = getattr(world, WORLD_CACHE_ATTR, None)
    if isinstance(cached, ExposedSurfaceCache) and cached.key_digest == key_digest:
        cached.hit_count += 1
        return cached
    built = build_exposed_facets(world, o1_registry_version=REGISTRY_VERSION)
    if isinstance(cached, ExposedSurfaceCache):
        built.build_count = int(cached.build_count) + 1
        built.miss_count = int(cached.miss_count) + 1
        built.hit_count = int(cached.hit_count)
    setattr(world, WORLD_CACHE_ATTR, built)
    return built


def invalidate_exposed_surface_cache(world: Any) -> None:
    if hasattr(world, WORLD_CACHE_ATTR):
        setattr(world, WORLD_CACHE_ATTR, None)


def query_exposed_facets_global(world: Any, config: Any) -> dict[str, Any]:
    cache = ensure_exposed_surface_cache(world, config)
    if cache is None:
        return {
            "schema": SCHEMA,
            "enabled": False,
            "facets": [],
            "label": "EXPOSED PHYSICAL BOUNDARIES · MATERIAL PROFILE ONLY · NO LIGHT/BRIGHTNESS",
        }
    return _query_payload(cache, cache.facets)


def query_exposed_facets_region(
    world: Any,
    config: Any,
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    z0: float | None = None,
    z1: float | None = None,
) -> dict[str, Any]:
    cache = ensure_exposed_surface_cache(world, config)
    if cache is None:
        return {"schema": SCHEMA, "enabled": False, "facets": []}
    xa, xb = sorted((float(x0), float(x1)))
    ya, yb = sorted((float(y0), float(y1)))
    out = []
    for f in cache.facets:
        cx, cy, cz = f["centre"]
        if not (xa - TOLERANCE <= cx <= xb + TOLERANCE and ya - TOLERANCE <= cy <= yb + TOLERANCE):
            continue
        if z0 is not None and cz < float(z0) - TOLERANCE:
            continue
        if z1 is not None and cz > float(z1) + TOLERANCE:
            continue
        out.append(f)
    return _query_payload(cache, out)


def query_exposed_facets_candidates(
    world: Any,
    config: Any,
    *,
    point: tuple[float, float, float],
    max_range: float,
    direction: tuple[float, float, float] | None = None,
) -> dict[str, Any]:
    """Candidate facets within range of a point; optional forward hemisphere filter."""
    cache = ensure_exposed_surface_cache(world, config)
    if cache is None:
        return {"schema": SCHEMA, "enabled": False, "facets": []}
    px, py, pz = (float(point[0]), float(point[1]), float(point[2]))
    r = float(max_range)
    r2 = r * r
    dir_v = None
    if direction is not None:
        dx, dy, dz = (float(direction[0]), float(direction[1]), float(direction[2]))
        mag = math.sqrt(dx * dx + dy * dy + dz * dz)
        if mag > TOLERANCE:
            dir_v = (dx / mag, dy / mag, dz / mag)
    out = []
    width, height = _world_shape(world)
    for f in cache.facets:
        cx, cy, cz = f["centre"]
        # Toroidal XY delta
        ddx = cx - px
        ddy = cy - py
        if abs(ddx) > width * 0.5:
            ddx -= math.copysign(width, ddx)
        if abs(ddy) > height * 0.5:
            ddy -= math.copysign(height, ddy)
        ddz = cz - pz
        dist2 = ddx * ddx + ddy * ddy + ddz * ddz
        if dist2 > r2 + TOLERANCE:
            continue
        if dir_v is not None:
            # Prefer facets whose outward normal faces the query (approx) or in forward half
            nx, ny, nz = f["outward_unit_normal"]
            if nx * dir_v[0] + ny * dir_v[1] + nz * dir_v[2] < -TOLERANCE:
                # still allow if centre is forward of point
                if ddx * dir_v[0] + ddy * dir_v[1] + ddz * dir_v[2] < -TOLERANCE:
                    continue
        out.append(f)
    return _query_payload(cache, out)


def _query_payload(cache: ExposedSurfaceCache, facets: Iterable[dict[str, Any]]) -> dict[str, Any]:
    fac = list(facets)
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "enabled": True,
        "researcher_only": True,
        "agent_accessible": False,
        "light_transport": False,
        "label": "EXPOSED PHYSICAL BOUNDARIES · MATERIAL PROFILE ONLY · NO LIGHT/BRIGHTNESS",
        "organism_saw_surface": False,
        "cache_key_digest": cache.key_digest,
        "cache_key_parts": dict(cache.key_parts),
        "facet_checksum": _facet_set_checksum(fac) if fac is not cache.facets else cache.facet_checksum,
        "full_set_facet_checksum": cache.facet_checksum,
        "facet_count": len(fac),
        "counts_by_face": dict(cache.counts_by_face) if fac is cache.facets or fac == list(cache.facets) else None,
        "o1_status_counts": dict(cache.o1_status_counts),
        "cache_hits": int(cache.hit_count),
        "cache_misses": int(cache.miss_count),
        "cache_builds": int(cache.build_count),
        "ordering": "(cell_y, cell_x, interval_z_min, interval_id, face_rank, span_lower, span_upper, facet_id)",
        "world_z_boundary_policy": WORLD_Z_BOUNDARY_POLICY,
        "detached_object_surface_scope": "DEFERRED_PRE_O3_EXTENSION",
        "facets": fac,
    }


def researcher_summary(world: Any, config: Any) -> dict[str, Any]:
    cache = ensure_exposed_surface_cache(world, config)
    if cache is None:
        return {
            "schema": SCHEMA,
            "enabled": False,
            "label": "EXPOSED PHYSICAL BOUNDARIES · MATERIAL PROFILE ONLY · NO LIGHT/BRIGHTNESS",
        }
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "enabled": True,
        "facet_count": len(cache.facets),
        "counts_by_face": dict(cache.counts_by_face),
        "o1_status_counts": dict(cache.o1_status_counts),
        "cache_key_digest": cache.key_digest,
        "facet_checksum": cache.facet_checksum,
        "cache_hits": int(cache.hit_count),
        "cache_misses": int(cache.miss_count),
        "cache_builds": int(cache.build_count),
        "label": "EXPOSED PHYSICAL BOUNDARIES · MATERIAL PROFILE ONLY · NO LIGHT/BRIGHTNESS",
        "organism_saw_surface": False,
        "light_or_brightness_view": False,
        "researcher_only": True,
        "agent_accessible": False,
    }


def coverage_for_analyzer(world: Any, config: Any) -> dict[str, Any]:
    summary = researcher_summary(world, config)
    summary["organism_saw_surface"] = False
    summary["exo_interpreted_as_o2"] = False
    return summary


PRIVACY_DENYLIST_TOKENS = (
    CAPABILITY,
    SCHEMA,
    PROFILE,
    AUTHORITY,
    "exposed_surface_optical_interaction_authority",
    "facet_id",
    "facet_checksum",
    "outward_unit_normal",
    "EXPOSED_SURFACE_OPTICAL",
    "VW1_OCCUPIED_FREE_BOUNDARY",
    "FACE_TOP",
    "FACE_BOTTOM",
)
