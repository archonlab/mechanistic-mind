"""Acanthostega O3A · Object / body / held analytic optical surface samples V1.

Schema: OBJECT_BODY_HELD_OPTICAL_SURFACES_V1
Capability: object_body_held_optical_surfaces
Profile: ANALYTIC_PHYSICAL_SURFACE_SAMPLES_FOR_DIRECT_LIGHT_O3A_V1
Authority: DERIVED_FROM_AUTHORITATIVE_BODY_AND_RESOURCE_OBJECT_GEOMETRY

Samples from collision/vertical geometry (not optical_radius, not glyphs).
Illuminated via O3 directional source + VW1 occupancy + analytic entity occluders.
Does not feed organism receptors or change exo_*.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterable

SCHEMA = "OBJECT_BODY_HELD_OPTICAL_SURFACES_V1"
CAPABILITY = "object_body_held_optical_surfaces"
PROFILE = "ANALYTIC_PHYSICAL_SURFACE_SAMPLES_FOR_DIRECT_LIGHT_O3A_V1"
AUTHORITY = "DERIVED_FROM_AUTHORITATIVE_BODY_AND_RESOURCE_OBJECT_GEOMETRY"
MECHANISM_ID = CAPABILITY

GEOMETRY_PROFILE_OBJECT = "SPHERE_AT_CENTRE_Z_COLLISION_RADIUS_V1"
GEOMETRY_PROFILE_BODY = "VERTICAL_CAPSULE_CIRCLE_CO_M_BODY_CONTACT_RADIUS_V1"
SAMPLE_PATTERN_OBJECT = "SPHERE_AXIS6_V1"
SAMPLE_PATTERN_BODY = "CAPSULE_TOP_BOTTOM_EQ8_V1"
MAX_SAMPLES_PER_OBJECT = 6
MAX_SAMPLES_PER_BODY = 10
OPTICAL_RADIUS_USED_AS_PHYSICAL_GEOMETRY = False
ENTITY_ENTITY_LIGHT_OCCLUSION = "IMPLEMENTED_ANALYTIC_RAY_SPHERE"
RAY_ORIGIN_EPSILON = 1e-6
DIRECTIONAL_RAY_LENGTH = 64.0
TOLERANCE = 1e-12
BODY_PROFILE_POLICY = "UNKNOWN_PROFILE_NO_INVENTED_COLORATION"
LEGACY_OBJECT_PROFILE_POLICY = "RESOLVE_COMPOSITION_ELSE_UNKNOWN_OR_LEGACY"

CLASS_BODY = "BODY"
CLASS_FREE_OBJECT = "FREE_RESOURCE_OBJECT"
CLASS_HELD_OBJECT = "HELD_RESOURCE_OBJECT"
CLASS_DETACHED_OBJECT = "DETACHED_TERRAIN_RESOURCE_OBJECT"

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "geometry_profile_object": GEOMETRY_PROFILE_OBJECT,
    "geometry_profile_body": GEOMETRY_PROFILE_BODY,
    "sample_pattern_object": SAMPLE_PATTERN_OBJECT,
    "sample_pattern_body": SAMPLE_PATTERN_BODY,
    "max_samples_per_object": MAX_SAMPLES_PER_OBJECT,
    "max_samples_per_body": MAX_SAMPLES_PER_BODY,
    "optical_radius_used_as_physical_geometry": OPTICAL_RADIUS_USED_AS_PHYSICAL_GEOMETRY,
    "entity_entity_light_occlusion": ENTITY_ENTITY_LIGHT_OCCLUSION,
    "organism_reception": False,
    "agent_accessible": False,
    "researcher_only": True,
    "feeds_cognition": False,
    "not_display_rgb": True,
    "not_organism_vision": True,
    "body_profile_policy": BODY_PROFILE_POLICY,
    "legacy_object_profile_policy": LEGACY_OBJECT_PROFILE_POLICY,
}


@dataclass
class ObjectBodyHeldOpticalSurfacesConfig:
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
    def from_dict(cls, data: dict[str, Any] | None) -> "ObjectBodyHeldOpticalSurfacesConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        return cls(
            enabled=bool(data.get("enabled", False)),
            schema=str(data.get("schema") or SCHEMA),
            profile=str(data.get("profile") or PROFILE),
        )


def object_body_held_optical_surfaces_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "object_body_held_optical_surfaces", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_object_body_held_optical_surfaces(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "object_body_held_optical_surfaces", None)
    if cur is None:
        config.object_body_held_optical_surfaces = ObjectBodyHeldOpticalSurfacesConfig(enabled=on)
    else:
        cur.enabled = on
        cur.schema = SCHEMA
        cur.profile = PROFILE


def object_body_held_optical_surfaces_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": bool(enabled),
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "researcher_only": True,
        "agent_accessible": False,
        "organism_reception": False,
        "summary": "Analytic body/object/held optical surface samples for O3 direct light (O3A).",
    }


def attach_optical_body_refs(world: Any, bodies: list[tuple[str, Any]] | None) -> None:
    """Stash runtime body refs for researcher optical queries (not cognition)."""
    if world is None:
        return
    world._o3a_body_refs = list(bodies or [])


def optical_body_refs(world: Any) -> list[tuple[str, Any]]:
    return list(getattr(world, "_o3a_body_refs", None) or [])


def _norm3(v: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = float(v[0]), float(v[1]), float(v[2])
    mag = math.sqrt(x * x + y * y + z * z)
    if not math.isfinite(mag) or mag <= TOLERANCE:
        return (0.0, 0.0, 1.0)
    return (x / mag, y / mag, z / mag)


def _object_class(obj: Any) -> str:
    state = str(getattr(obj, "physical_state", "") or "")
    if state == "HELD":
        return CLASS_HELD_OBJECT
    prov = getattr(obj, "provenance", None) or {}
    if isinstance(prov, dict) and (
        prov.get("detached")
        or prov.get("source") in ("terrain", "surface_column", "volumetric_separation", "VW3")
        or "detached" in str(prov.get("kind", "")).lower()
        or "terrain" in str(prov.get("origin", "")).lower()
    ):
        return CLASS_DETACHED_OBJECT
    return CLASS_FREE_OBJECT


def _object_radius_and_centre(obj: Any, config: Any) -> tuple[float, float, float, float, float]:
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of, ensure_object_vertical
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        CANONICAL_COLLISION_RADIUS,
        ensure_object_collision_radius,
    )

    ensure_object_vertical(obj, config)
    ensure_object_collision_radius(obj)
    r = float(getattr(obj, "collision_radius", CANONICAL_COLLISION_RADIUS) or CANONICAL_COLLISION_RADIUS)
    x = float(getattr(obj, "x", 0.0) or 0.0)
    y = float(getattr(obj, "y", 0.0) or 0.0)
    cz = float(centre_z_of(obj, kind="object", config=config))
    return x, y, cz, r, r


def _body_radius_and_centre(body: Any, config: Any) -> tuple[float, float, float, float, float]:
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of, ensure_body_vertical
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import BODY_CONTACT_RADIUS

    ensure_body_vertical(body, config)
    x = float(getattr(body, "x", 0.0) or 0.0)
    y = float(getattr(body, "y", 0.0) or 0.0)
    cz = float(centre_z_of(body, kind="body", config=config))
    r = float(BODY_CONTACT_RADIUS)
    he = float(getattr(body, "vertical_half_extent", None) or BODY_CONTACT_RADIUS)
    return x, y, cz, r, he


def _resolve_object_material(obj: Any) -> dict[str, Any]:
    from mechanistic_mind.physical_system.physical_optical_material_profile import (
        resolve_resource_object_profile,
    )

    return resolve_resource_object_profile(obj)


def _resolve_body_material(body: Any) -> dict[str, Any]:
    """Bodies lack RO composition — explicit unknown; no invented coloration."""
    from mechanistic_mind.physical_system.physical_optical_material_profile import (
        OPTICAL_BAND_IDENTIFIERS,
        STATUS_UNKNOWN,
    )

    return {
        "status": STATUS_UNKNOWN,
        "spectral_reflectance": None,
        "optical_band_identifiers": list(OPTICAL_BAND_IDENTIFIERS),
        "resolution_target": "BODY",
        "body_profile_policy": BODY_PROFILE_POLICY,
        "compatibility": STATUS_UNKNOWN,
    }


def _pose_digest_object(obj: Any, config: Any) -> str:
    x, y, cz, r, _ = _object_radius_and_centre(obj, config)
    raw = {
        "id": str(getattr(obj, "object_id", "")),
        "x": round(x, 9),
        "y": round(y, 9),
        "cz": round(cz, 9),
        "r": round(r, 9),
        "state": str(getattr(obj, "physical_state", "")),
        "holder": getattr(obj, "holder_body_id", None),
        "manip": getattr(obj, "manipulator_id", None),
        "rev": int(getattr(obj, "material_revision", 0) or 0),
    }
    return hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def _pose_digest_body(body_id: str, body: Any, config: Any) -> str:
    x, y, cz, r, he = _body_radius_and_centre(body, config)
    raw = {
        "id": str(body_id),
        "x": round(x, 9),
        "y": round(y, 9),
        "cz": round(cz, 9),
        "r": round(r, 9),
        "he": round(he, 9),
        "theta": round(float(getattr(body, "theta", 0.0) or 0.0), 9),
        "tick": int(getattr(body, "tick", 0) or 0),
    }
    return hashlib.sha256(json.dumps(raw, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]


def build_object_surface_samples(obj: Any, config: Any) -> list[dict[str, Any]]:
    """SPHERE_AXIS6_V1: six axis samples on collision sphere at centre_z."""
    x, y, cz, r, _ = _object_radius_and_centre(obj, config)
    mat = _resolve_object_material(obj)
    eid = str(getattr(obj, "object_id", "object"))
    eclass = _object_class(obj)
    pose = _pose_digest_object(obj, config)
    area = 4.0 * math.pi * r * r
    w = area / float(MAX_SAMPLES_PER_OBJECT)
    axes = (
        (1.0, 0.0, 0.0),
        (-1.0, 0.0, 0.0),
        (0.0, 1.0, 0.0),
        (0.0, -1.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 0.0, -1.0),
    )
    out: list[dict[str, Any]] = []
    for i, n in enumerate(axes):
        nn = _norm3(n)
        px = x + r * nn[0]
        py = y + r * nn[1]
        pz = cz + r * nn[2]
        sid = f"o3a:{eid}:axis{i}"
        out.append({
            "sample_id": sid,
            "facet_id": sid,  # O3 evaluate compatibility
            "entity_id": eid,
            "entity_class": eclass,
            "held": eclass == CLASS_HELD_OBJECT,
            "centre": [px, py, pz],
            "outward_unit_normal": [nn[0], nn[1], nn[2]],
            "area_weight": float(w),
            "geometry_profile": GEOMETRY_PROFILE_OBJECT,
            "sample_pattern": SAMPLE_PATTERN_OBJECT,
            "geometry_radius": float(r),
            "entity_centre": [x, y, cz],
            "pose_digest": pose,
            "pose_tick": int(getattr(obj, "creation_tick", 0) or 0),
            "material_composition_reference": None,
            "spectral_reflectance": mat.get("spectral_reflectance"),
            "o1_status": mat.get("status"),
            "o1_profile": mat,
            "optical_radius_not_used": True,
            "schema": SCHEMA,
            "authority": AUTHORITY,
        })
    out.sort(key=lambda s: s["sample_id"])
    return out


def build_body_surface_samples(body_id: str, body: Any, config: Any) -> list[dict[str, Any]]:
    """CAPSULE_TOP_BOTTOM_EQ8_V1 on body contact circle + vertical extent."""
    x, y, cz, r, he = _body_radius_and_centre(body, config)
    mat = _resolve_body_material(body)
    pose = _pose_digest_body(body_id, body, config)
    # Approximate capsule surface area: 4πr² when he≈r (documented sphere-equivalent).
    area = 4.0 * math.pi * r * r
    w = area / float(MAX_SAMPLES_PER_BODY)
    samples: list[tuple[str, tuple[float, float, float], tuple[float, float, float]]] = []
    # Top / bottom at vertical ends of capsule (sphere caps when he≈r).
    samples.append(("top", (x, y, cz + he), (0.0, 0.0, 1.0)))
    samples.append(("bot", (x, y, cz - he), (0.0, 0.0, -1.0)))
    for i in range(8):
        ang = (2.0 * math.pi * i) / 8.0
        nx, ny = math.cos(ang), math.sin(ang)
        samples.append((f"eq{i}", (x + r * nx, y + r * ny, cz), (nx, ny, 0.0)))
    out: list[dict[str, Any]] = []
    for label, p, n in samples:
        nn = _norm3(n)
        sid = f"o3a:body:{body_id}:{label}"
        out.append({
            "sample_id": sid,
            "facet_id": sid,
            "entity_id": str(body_id),
            "entity_class": CLASS_BODY,
            "held": False,
            "centre": [float(p[0]), float(p[1]), float(p[2])],
            "outward_unit_normal": [nn[0], nn[1], nn[2]],
            "area_weight": float(w),
            "geometry_profile": GEOMETRY_PROFILE_BODY,
            "sample_pattern": SAMPLE_PATTERN_BODY,
            "geometry_radius": float(r),
            "vertical_half_extent": float(he),
            "entity_centre": [x, y, cz],
            "pose_digest": pose,
            "pose_tick": int(getattr(body, "tick", 0) or 0),
            "heading_theta": float(getattr(body, "theta", 0.0) or 0.0),
            "heading_rotates_samples": False,  # circular cross-section
            "spectral_reflectance": mat.get("spectral_reflectance"),
            "o1_status": mat.get("status"),
            "o1_profile": mat,
            "optical_radius_not_used": True,
            "schema": SCHEMA,
            "authority": AUTHORITY,
        })
    out.sort(key=lambda s: s["sample_id"])
    return out


def build_all_surface_samples(
    world: Any,
    config: Any,
    *,
    bodies: list[tuple[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    body_list = bodies if bodies is not None else optical_body_refs(world)
    rows: list[dict[str, Any]] = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        rows.extend(build_object_surface_samples(obj, config))
    for bid, body in body_list:
        if body is None:
            continue
        rows.extend(build_body_surface_samples(str(bid), body, config))
    rows.sort(key=lambda s: (str(s.get("entity_id") or ""), str(s.get("sample_id") or "")))
    return rows


# ---------------------------------------------------------------------------
# Analytic entity occlusion (ray–sphere); not a second collision solver.
# ---------------------------------------------------------------------------

def ray_sphere_intersection_t(
    origin: tuple[float, float, float],
    direction: tuple[float, float, float],
    centre: tuple[float, float, float],
    radius: float,
    *,
    width: int | None = None,
    height: int | None = None,
) -> float | None:
    """Minimal t in (eps, 1] for origin + t * direction hitting sphere (periodic XY)."""
    from mechanistic_mind.planet.topology import toroidal_delta

    ox, oy, oz = origin
    dx, dy, dz = direction
    cx, cy, cz = centre
    if width is not None and height is not None:
        ddx = toroidal_delta(ox, cx, int(width))
        ddy = toroidal_delta(oy, cy, int(height))
        rcx = ox + float(ddx)
        rcy = oy + float(ddy)
    else:
        rcx, rcy = cx, cy
    rcz = cz
    ocx = ox - rcx
    ocy = oy - rcy
    ocz = oz - rcz
    a = dx * dx + dy * dy + dz * dz
    if a <= TOLERANCE:
        return None
    b = 2.0 * (ocx * dx + ocy * dy + ocz * dz)
    c = ocx * ocx + ocy * ocy + ocz * ocz - float(radius) * float(radius)
    disc = b * b - 4.0 * a * c
    if disc < 0.0:
        return None
    sd = math.sqrt(disc)
    t0 = (-b - sd) / (2.0 * a)
    t1 = (-b + sd) / (2.0 * a)
    eps = RAY_ORIGIN_EPSILON / max(math.sqrt(a), TOLERANCE)
    hits = [t for t in (t0, t1) if eps < t <= 1.0 + TOLERANCE]
    if not hits:
        return None
    return float(min(hits))


def collect_entity_occluders(
    world: Any,
    config: Any,
    *,
    bodies: list[tuple[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """One occluder sphere per entity (held included once)."""
    body_list = bodies if bodies is not None else optical_body_refs(world)
    out: list[dict[str, Any]] = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        x, y, cz, r, _ = _object_radius_and_centre(obj, config)
        out.append({
            "entity_id": str(getattr(obj, "object_id", "")),
            "entity_class": _object_class(obj),
            "centre": (x, y, cz),
            "radius": float(r),
            "kind": "RESOURCE_OBJECT",
        })
    for bid, body in body_list:
        if body is None:
            continue
        x, y, cz, r, _ = _body_radius_and_centre(body, config)
        out.append({
            "entity_id": str(bid),
            "entity_class": CLASS_BODY,
            "centre": (x, y, cz),
            "radius": float(r),
            "kind": "BODY",
        })
    out.sort(key=lambda e: (str(e["kind"]), str(e["entity_id"])))
    return out


def entity_source_occlusion(
    world: Any,
    *,
    origin: tuple[float, float, float],
    direction_toward_source: tuple[float, float, float],
    exclude_entity_id: str | None,
    config: Any,
    bodies: list[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    grid = getattr(world, "T", None)
    width = int(grid.shape[1]) if grid is not None else None
    height = int(grid.shape[0]) if grid is not None else None
    L = _norm3(direction_toward_source)
    far = float(DIRECTIONAL_RAY_LENGTH)
    D = (far * L[0], far * L[1], far * L[2])
    blockers: list[dict[str, Any]] = []
    for occ in collect_entity_occluders(world, config, bodies=bodies):
        if exclude_entity_id is not None and str(occ["entity_id"]) == str(exclude_entity_id):
            continue
        t = ray_sphere_intersection_t(
            origin, D, occ["centre"], float(occ["radius"]), width=width, height=height,
        )
        if t is None:
            continue
        blockers.append({
            "t": float(t),
            "entity_id": occ["entity_id"],
            "entity_class": occ["entity_class"],
            "kind": occ["kind"],
            "authority": "ANALYTIC_RAY_SPHERE",
        })
    blockers.sort(key=lambda b: (float(b["t"]), str(b["kind"]), str(b["entity_id"])))
    nearest = blockers[0] if blockers else None
    return {
        "clear": nearest is None,
        "blocker": nearest,
        "kernel": "analytic_ray_sphere_entity_occlusion",
        "entity_entity_light_occlusion": ENTITY_ENTITY_LIGHT_OCCLUSION,
        "exclude_entity_id": exclude_entity_id,
        "blocker_count": len(blockers),
    }


WORLD_CACHE_ATTR = "_o3a_optical_surface_cache"


@dataclass
class O3ASurfaceCache:
    key_digest: str
    key_parts: dict[str, str]
    samples: tuple[dict[str, Any], ...]
    illuminations: tuple[dict[str, Any], ...]
    result_checksum: str
    state_counts: dict[str, int]
    class_counts: dict[str, int]
    o1_counts: dict[str, int]
    build_count: int = 0
    hit_count: int = 0
    miss_count: int = 0


def _cache_key(world: Any, config: Any, bodies: list[tuple[str, Any]] | None) -> dict[str, str]:
    from mechanistic_mind.physical_system.physical_optical_material_profile import REGISTRY_VERSION
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

    body_list = bodies if bodies is not None else optical_body_refs(world)
    pose_parts = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        pose_parts.append(_pose_digest_object(obj, config))
    for bid, body in body_list:
        if body is not None:
            pose_parts.append(_pose_digest_body(str(bid), body, config))
    pose_parts.sort()
    st = state_of(world)
    src = getattr(getattr(config, "abstract_spectral_light_source_and_direct_transport", None), "source", None)
    src_dig = src.digest() if src is not None and hasattr(src, "digest") else "src:absent"
    return {
        "o3a_schema": SCHEMA,
        "o3a_profile": PROFILE,
        "o1_registry_version": str(REGISTRY_VERSION),
        "vw1_digest": str(st.digest()) if st is not None else "vw1:absent",
        "source_digest": str(src_dig),
        "pose_digest": hashlib.sha256("|".join(pose_parts).encode()).hexdigest()[:16],
        "entity_count": str(len(pose_parts)),
    }


def _key_digest(parts: dict[str, str]) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _illum_checksum(rows: Iterable[dict[str, Any]]) -> str:
    payload = [
        {
            "sample_id": r.get("sample_id") or r.get("facet_id"),
            "state_class": r.get("state_class"),
            "incident": r.get("incident_spectrum"),
            "reflected": r.get("reflected_spectral_exitance_proxy"),
        }
        for r in rows
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_entity_light_field(
    world: Any,
    config: Any,
    *,
    bodies: list[tuple[str, Any]] | None = None,
) -> O3ASurfaceCache:
    from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
        evaluate_facet_illumination,
    )

    body_list = bodies if bodies is not None else optical_body_refs(world)
    if bodies is not None:
        attach_optical_body_refs(world, body_list)
    key_parts = _cache_key(world, config, body_list)
    samples = build_all_surface_samples(world, config, bodies=body_list)
    rows: list[dict[str, Any]] = []
    for sample in samples:
        row = evaluate_facet_illumination(
            world,
            config,
            sample,
            exclude_entity_id=str(sample.get("entity_id")),
            entity_occlusion_bodies=body_list,
        )
        row = {
            **row,
            "sample_id": sample.get("sample_id"),
            "entity_id": sample.get("entity_id"),
            "entity_class": sample.get("entity_class"),
            "area_weight": sample.get("area_weight"),
            "pose_digest": sample.get("pose_digest"),
            "pose_tick": sample.get("pose_tick"),
            "geometry_profile": sample.get("geometry_profile"),
            "o3a_schema": SCHEMA,
            "organism_saw_light": False,
        }
        rows.append(row)
    rows.sort(key=lambda r: (str(r.get("entity_id") or ""), str(r.get("sample_id") or "")))
    state_counts: dict[str, int] = {}
    class_counts: dict[str, int] = {}
    o1_counts: dict[str, int] = {}
    for s in samples:
        ec = str(s.get("entity_class") or "")
        class_counts[ec] = class_counts.get(ec, 0) + 1
        st = str(s.get("o1_status") or "UNKNOWN")
        o1_counts[st] = o1_counts.get(st, 0) + 1
    for r in rows:
        sc = str(r.get("state_class") or "NOT_EVALUATED")
        state_counts[sc] = state_counts.get(sc, 0) + 1
    return O3ASurfaceCache(
        key_digest=_key_digest(key_parts),
        key_parts=key_parts,
        samples=tuple(samples),
        illuminations=tuple(rows),
        result_checksum=_illum_checksum(rows),
        state_counts=state_counts,
        class_counts=class_counts,
        o1_counts=o1_counts,
        build_count=1,
        miss_count=1,
    )


def ensure_entity_surface_cache(
    world: Any,
    config: Any,
    *,
    bodies: list[tuple[str, Any]] | None = None,
) -> O3ASurfaceCache | None:
    if not object_body_held_optical_surfaces_is_active(config):
        if hasattr(world, WORLD_CACHE_ATTR):
            setattr(world, WORLD_CACHE_ATTR, None)
        return None
    body_list = bodies if bodies is not None else optical_body_refs(world)
    if bodies is not None:
        attach_optical_body_refs(world, body_list)
    key_parts = _cache_key(world, config, body_list)
    key_digest = _key_digest(key_parts)
    cached = getattr(world, WORLD_CACHE_ATTR, None)
    if isinstance(cached, O3ASurfaceCache) and cached.key_digest == key_digest:
        cached.hit_count += 1
        return cached
    built = build_entity_light_field(world, config, bodies=body_list)
    if isinstance(cached, O3ASurfaceCache):
        built.build_count = int(cached.build_count) + 1
        built.miss_count = int(cached.miss_count) + 1
        built.hit_count = int(cached.hit_count)
    setattr(world, WORLD_CACHE_ATTR, built)
    return built


def invalidate_entity_surface_cache(world: Any) -> None:
    if hasattr(world, WORLD_CACHE_ATTR):
        setattr(world, WORLD_CACHE_ATTR, None)


def query_entity_surfaces(
    world: Any,
    config: Any,
    entity_id: str,
    *,
    bodies: list[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    cache = ensure_entity_surface_cache(world, config, bodies=bodies)
    if cache is None:
        return {"enabled": False, "samples": [], "illuminations": []}
    samples = [s for s in cache.samples if str(s.get("entity_id")) == str(entity_id)]
    illum = [r for r in cache.illuminations if str(r.get("entity_id")) == str(entity_id)]
    return {
        "enabled": True,
        "schema": SCHEMA,
        "entity_id": str(entity_id),
        "sample_count": len(samples),
        "samples": samples,
        "illuminations": illum,
        "cache_key_digest": cache.key_digest,
        "result_checksum": _illum_checksum(illum),
        "organism_saw_light": False,
    }


def query_entity_surfaces_region(
    world: Any,
    config: Any,
    *,
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    bodies: list[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    cache = ensure_entity_surface_cache(world, config, bodies=bodies)
    if cache is None:
        return {"enabled": False, "samples": []}
    xa, xb = sorted((float(x0), float(x1)))
    ya, yb = sorted((float(y0), float(y1)))
    samples = [
        s for s in cache.samples
        if xa - TOLERANCE <= float(s["centre"][0]) <= xb + TOLERANCE
        and ya - TOLERANCE <= float(s["centre"][1]) <= yb + TOLERANCE
    ]
    ids = {s["sample_id"] for s in samples}
    illum = [r for r in cache.illuminations if r.get("sample_id") in ids]
    return {
        "enabled": True,
        "schema": SCHEMA,
        "sample_count": len(samples),
        "samples": samples,
        "illuminations": illum,
        "cache_key_digest": cache.key_digest,
        "organism_saw_light": False,
    }


def query_entity_surface_candidates(
    world: Any,
    config: Any,
    *,
    point: tuple[float, float, float],
    max_range: float,
    bodies: list[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    cache = ensure_entity_surface_cache(world, config, bodies=bodies)
    if cache is None:
        return {"enabled": False, "samples": []}
    px, py, pz = float(point[0]), float(point[1]), float(point[2])
    mr2 = float(max_range) * float(max_range)
    samples = []
    for s in cache.samples:
        c = s["centre"]
        d2 = (float(c[0]) - px) ** 2 + (float(c[1]) - py) ** 2 + (float(c[2]) - pz) ** 2
        if d2 <= mr2 + TOLERANCE:
            samples.append(s)
    ids = {s["sample_id"] for s in samples}
    illum = [r for r in cache.illuminations if r.get("sample_id") in ids]
    return {
        "enabled": True,
        "schema": SCHEMA,
        "sample_count": len(samples),
        "samples": samples,
        "illuminations": illum,
        "cache_key_digest": cache.key_digest,
        "organism_saw_light": False,
        "future_receptor_candidate_set": True,
    }


def researcher_summary(
    world: Any,
    config: Any,
    *,
    bodies: list[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    cache = ensure_entity_surface_cache(world, config, bodies=bodies)
    if cache is None:
        return {
            "enabled": False,
            "schema": SCHEMA,
            "label": "ANALYTIC PHYSICAL SURFACE SAMPLES · DIRECT LIGHT ONLY · NOT ORGANISM VISION",
        }
    return {
        "enabled": True,
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "label": "ANALYTIC PHYSICAL SURFACE SAMPLES · DIRECT LIGHT ONLY · NOT ORGANISM VISION",
        "sample_count": len(cache.samples),
        "class_counts": dict(cache.class_counts),
        "o1_status_counts": dict(cache.o1_counts),
        "state_counts": dict(cache.state_counts),
        "result_checksum": cache.result_checksum,
        "cache_key_digest": cache.key_digest,
        "cache_hits": int(cache.hit_count),
        "cache_misses": int(cache.miss_count),
        "cache_builds": int(cache.build_count),
        "entity_entity_light_occlusion": ENTITY_ENTITY_LIGHT_OCCLUSION,
        "optical_radius_used_as_physical_geometry": False,
        "max_samples_per_object": MAX_SAMPLES_PER_OBJECT,
        "max_samples_per_body": MAX_SAMPLES_PER_BODY,
        "sample_pattern_object": SAMPLE_PATTERN_OBJECT,
        "sample_pattern_body": SAMPLE_PATTERN_BODY,
        "organism_saw_light": False,
        "feeds_cognition": False,
        "generations": dict(cache.key_parts),
    }


def build_object_body_held_optical_causal_reconstruction(
    evidence: dict[str, Any] | None = None,
    *,
    on_progress: Any | None = None,
) -> dict[str, Any]:
    ev = evidence if isinstance(evidence, dict) else {}
    if on_progress:
        on_progress("INDEX_PHYSICAL_RECEIPTS", 0, 1)
    if on_progress:
        on_progress("CLASSIFY_NEGATIVE_CAUSES", 1, 1)
    if on_progress:
        on_progress("AGGREGATING", 1, 1)
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "section": "OBJECT/BODY/HELD OPTICAL SURFACES (O3A)",
        "causal_chain": [
            "entity_geometry",
            "surface_sample",
            "material_profile",
            "source_orientation",
            "occlusion",
            "reflected_spectral_exitance_proxy",
        ],
        "class_counts": ev.get("class_counts") or {},
        "state_counts": ev.get("state_counts") or {},
        "o1_status_counts": ev.get("o1_status_counts") or {},
        "entity_entity_light_occlusion": ENTITY_ENTITY_LIGHT_OCCLUSION,
        "sample_count": ev.get("sample_count"),
        "organism_saw_light": False,
        "organism_reception": False,
        "label": "ANALYTIC PHYSICAL SURFACE SAMPLES · DIRECT LIGHT ONLY · NOT ORGANISM VISION",
        "researcher_only": True,
    }


def format_object_body_held_optical_section(summary: dict[str, Any] | None) -> str:
    s = summary or {}
    return "\n".join([
        "OBJECT/BODY/HELD OPTICAL SURFACES (O3A)",
        f"  sample_count: {s.get('sample_count')}",
        f"  class_counts: {s.get('class_counts')}",
        f"  state_counts: {s.get('state_counts')}",
        f"  o1_status_counts: {s.get('o1_status_counts')}",
        f"  entity_entity_light_occlusion: {s.get('entity_entity_light_occlusion')}",
        "  organism_saw_light: False",
        "  label: ANALYTIC PHYSICAL SURFACE SAMPLES · DIRECT LIGHT ONLY · NOT ORGANISM VISION",
    ])


PRIVACY_DENYLIST_TOKENS = (
    CAPABILITY,
    SCHEMA,
    PROFILE,
    AUTHORITY,
    "object_body_held_optical_surfaces",
    "o3a:",
    SAMPLE_PATTERN_OBJECT,
    SAMPLE_PATTERN_BODY,
    "area_weight",
    "pose_digest",
    "entity_centre",
)
