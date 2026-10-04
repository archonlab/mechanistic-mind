"""Acanthostega O3 · Abstract spectral light source and direct transport V1.

Schema: ABSTRACT_SPECTRAL_LIGHT_SOURCE_AND_DIRECT_TRANSPORT_V1
Capability: abstract_spectral_light_source_and_direct_transport
Profile: DIRECT_OCCUPANCY_OCCLUDED_ANONYMOUS_SPECTRAL_LIGHT_O3_V1
Authority: PHYSICAL_ABSTRACT_NON_SI_DIRECT_LIGHT_FIELD

Causal chain (terrain O2 facets):
  directional source -> free-space ray (VW1 occupancy occlusion)
    -> incident_spectrum[b] = source[b] * max(0, n·L)
    -> reflected_spectral_exitance_proxy[b] = incident[b] * O1_R[b]

Does not feed organism receptors or change exo_*.
Does not use illumination_intensity, VW7 pixels, RGB, or SI radiometry.
No hidden ambient floor.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterable

SCHEMA = "ABSTRACT_SPECTRAL_LIGHT_SOURCE_AND_DIRECT_TRANSPORT_V1"
CAPABILITY = "abstract_spectral_light_source_and_direct_transport"
PROFILE = "DIRECT_OCCUPANCY_OCCLUDED_ANONYMOUS_SPECTRAL_LIGHT_O3_V1"
AUTHORITY = "PHYSICAL_ABSTRACT_NON_SI_DIRECT_LIGHT_FIELD"
MECHANISM_ID = CAPABILITY

OPTICAL_BAND_COUNT = 6
OPTICAL_BAND_IDENTIFIERS = tuple(f"optical_band_{i}" for i in range(OPTICAL_BAND_COUNT))
SOURCE_ID = "abstract_directional_source_0"
SOURCE_TYPE = "GLOBAL_DIRECTIONAL"
DIRECTION_CONVENTION = "DIRECTION_TOWARD_SOURCE_UNIT"
DEFAULT_DIRECTION_TOWARD_SOURCE = (0.0, 0.0, 1.0)
DEFAULT_SOURCE_SPECTRUM = (1.0, 1.0, 1.0, 1.0, 1.0, 1.0)
SOURCE_VERSION = "O3_DIRECTIONAL_SOURCE_V1"
RAY_ORIGIN_EPSILON = 1e-6
DIRECTIONAL_RAY_LENGTH = 64.0
TOLERANCE = 1e-12
REFLECTED_QUANTITY_NAME = "reflected_spectral_exitance_proxy"

STATE_DIRECT = "DIRECT_ILLUMINATED"
STATE_BACK = "BACK_FACING_ZERO"
STATE_OCCLUDED = "OCCLUDED_ZERO"
STATE_DISABLED = "SOURCE_DISABLED_ZERO"
STATE_UNKNOWN_MAT = "UNKNOWN_MATERIAL_RESPONSE"
STATE_NOT_EVAL = "NOT_EVALUATED"
STATE_INVALID = "INVALID_GEOMETRY"

OBJECT_BODY_EXTENSION_REQUIRED_BEFORE_O4 = False  # cleared by O3A; kept for legacy readers


def object_body_extension_required_before_o4(config: Any = None) -> bool:
    """True only when O3A is inactive — O3A supplies entity optical surfaces."""
    try:
        from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
            object_body_held_optical_surfaces_is_active,
        )

        if config is not None and object_body_held_optical_surfaces_is_active(config):
            return False
    except Exception:
        pass
    return False


AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "optical_band_count": OPTICAL_BAND_COUNT,
    "optical_band_identifiers": list(OPTICAL_BAND_IDENTIFIERS),
    "optical_bands_share_acoustic_authority": False,
    "si_wavelength_mapping": False,
    "si_radiometry": False,
    "brdf_claimed": False,
    "energy_conservation_claimed": False,
    "hidden_ambient_light": False,
    "explicit_diffuse_source": False,
    "organism_reception": False,
    "agent_accessible": False,
    "researcher_only": True,
    "behaviorally_dormant_for_organisms": True,
    "reflected_quantity_name": REFLECTED_QUANTITY_NAME,
    "direction_convention": DIRECTION_CONVENTION,
    "object_optical_surface_scope": "O3A_ANALYTIC_SAMPLES",
    "body_optical_surface_scope": "O3A_ANALYTIC_SAMPLES",
    "held_object_optical_surface_scope": "O3A_ANALYTIC_SAMPLES",
    "object_body_extension_required_before_o4": False,
    "not_illumination_intensity": True,
    "not_display_rgb": True,
    "not_organism_vision": True,
}


def _normalize3(v: tuple[float, float, float] | list[float]) -> tuple[float, float, float]:
    x, y, z = float(v[0]), float(v[1]), float(v[2])
    mag = math.sqrt(x * x + y * y + z * z)
    if not math.isfinite(mag) or mag <= TOLERANCE:
        raise ValueError("direction must be finite and non-zero")
    return (x / mag, y / mag, z / mag)


def _clip_spectrum(raw: Any) -> tuple[float, ...]:
    if raw is None:
        return DEFAULT_SOURCE_SPECTRUM
    seq = list(raw)
    out: list[float] = []
    for i in range(OPTICAL_BAND_COUNT):
        try:
            v = float(seq[i]) if i < len(seq) else 0.0
        except (TypeError, ValueError):
            v = 0.0
        if not math.isfinite(v) or v < 0.0:
            v = 0.0
        out.append(float(min(v, 1.0e6)))
    return tuple(out)


@dataclass
class AbstractDirectionalLightSource:
    source_id: str = SOURCE_ID
    enabled: bool = True
    direction_toward_source: tuple[float, float, float] = DEFAULT_DIRECTION_TOWARD_SOURCE
    source_spectrum: tuple[float, ...] = DEFAULT_SOURCE_SPECTRUM
    source_version: str = SOURCE_VERSION

    def to_dict(self) -> dict[str, Any]:
        d = _normalize3(self.direction_toward_source)
        s = _clip_spectrum(self.source_spectrum)
        return {
            "source_id": str(self.source_id),
            "source_type": SOURCE_TYPE,
            "enabled": bool(self.enabled),
            "direction_convention": DIRECTION_CONVENTION,
            "direction_toward_source": [float(d[0]), float(d[1]), float(d[2])],
            "source_spectrum": [float(x) for x in s],
            "optical_band_identifiers": list(OPTICAL_BAND_IDENTIFIERS),
            "source_version": str(self.source_version),
            "units": "ABSTRACT_NON_SI",
            "distance_attenuation": False,
            "si_radiometry": False,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AbstractDirectionalLightSource":
        if not isinstance(data, dict) or not data:
            return cls()
        direction = data.get("direction_toward_source") or DEFAULT_DIRECTION_TOWARD_SOURCE
        return cls(
            source_id=str(data.get("source_id") or SOURCE_ID),
            enabled=bool(data.get("enabled", True)),
            direction_toward_source=_normalize3(direction),
            source_spectrum=_clip_spectrum(data.get("source_spectrum")),
            source_version=str(data.get("source_version") or SOURCE_VERSION),
        )

    def digest(self) -> str:
        raw = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass
class AbstractSpectralLightSourceAndDirectTransportConfig:
    enabled: bool = False
    schema: str = SCHEMA
    profile: str = PROFILE
    source: AbstractDirectionalLightSource = field(default_factory=AbstractDirectionalLightSource)

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "schema": str(self.schema),
            "profile": str(self.profile),
            "source": self.source.to_dict(),
            **AUTHORITY_FLAGS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AbstractSpectralLightSourceAndDirectTransportConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        return cls(
            enabled=bool(data.get("enabled", False)),
            schema=str(data.get("schema") or SCHEMA),
            profile=str(data.get("profile") or PROFILE),
            source=AbstractDirectionalLightSource.from_dict(
                data.get("source") if isinstance(data.get("source"), dict) else None
            ),
        )


def abstract_spectral_light_source_and_direct_transport_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "abstract_spectral_light_source_and_direct_transport", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_abstract_spectral_light_source_and_direct_transport(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "abstract_spectral_light_source_and_direct_transport", None)
    if cur is None:
        config.abstract_spectral_light_source_and_direct_transport = (
            AbstractSpectralLightSourceAndDirectTransportConfig(enabled=on)
        )
    else:
        cur.enabled = on
        cur.schema = SCHEMA
        cur.profile = PROFILE


def abstract_spectral_light_source_and_direct_transport_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": bool(enabled),
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "researcher_only": True,
        "agent_accessible": False,
        "organism_reception": False,
        "summary": "Abstract directional spectral light + direct VW1-occluded transport (O3).",
    }


def _zero_bands() -> list[float]:
    return [0.0] * OPTICAL_BAND_COUNT


def _dot(a: Iterable[float], b: Iterable[float]) -> float:
    ax, ay, az = a
    bx, by, bz = b
    return float(ax) * float(bx) + float(ay) * float(by) + float(az) * float(bz)


def _interval_intersects_z_range(z_a: float, z_b: float, z_min: float, z_max: float) -> bool:
    lo, hi = (z_a, z_b) if z_a <= z_b else (z_b, z_a)
    # Occupied (z_min, z_max]; open at lower bound matching VW1.
    return hi > float(z_min) + TOLERANCE and lo < float(z_max) + TOLERANCE


def _source_visibility(
    world: Any,
    *,
    origin: tuple[float, float, float],
    direction_toward_source: tuple[float, float, float],
    config: Any,
    exclude_entity_id: str | None = None,
    entity_occlusion_bodies: list[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    """Directional occlusion via shared VW1 occupancy + optional O3A entity spheres.

    Does NOT call VW6 ``occupancy_line_of_sight`` (eye→target endpoint skips make
    same-column blockers invisible). Numerics of VW6 agent vision are unchanged.
    """
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        traverse_xy_columns,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        occupied_intervals_at,
    )

    L = direction_toward_source
    far = float(DIRECTIONAL_RAY_LENGTH)
    ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])
    dx, dy, dz = far * float(L[0]), far * float(L[1]), far * float(L[2])
    grid = getattr(world, "T", None)
    if grid is None:
        return {
            "clear": False,
            "blocker": None,
            "los_distance": None,
            "kernel": "directional_occupancy_occlusion",
            "ray_length": far,
            "origin_epsilon": RAY_ORIGIN_EPSILON,
            "reason": "missing_world_grid",
        }
    height = int(grid.shape[0])
    width = int(grid.shape[1])
    columns = traverse_xy_columns(ox, oy, dx, dy, width=width, height=height)
    blockers: list[dict[str, Any]] = []
    t_open = max(RAY_ORIGIN_EPSILON / max(far, TOLERANCE), 1e-9)
    for col in columns:
        t0 = float(col["t_enter"])
        t1 = float(col["t_exit"])
        ta = max(t0, t_open)
        tb = min(t1, 1.0)
        if tb <= ta + TOLERANCE:
            continue
        z_a = oz + ta * dz
        z_b = oz + tb * dz
        cx, cy = int(col["cell_x"]), int(col["cell_y"])
        intervals = occupied_intervals_at(world, cx + 0.5, cy + 0.5)
        for it in intervals:
            if not _interval_intersects_z_range(z_a, z_b, float(it.z_min), float(it.z_max)):
                continue
            if abs(dz) > TOLERANCE:
                candidates = []
                for z_bound in (float(it.z_min) + 1e-12, float(it.z_max)):
                    t_hit = (z_bound - oz) / dz
                    if ta - TOLERANCE <= t_hit <= tb + TOLERANCE:
                        zz = oz + t_hit * dz
                        if float(it.z_min) + TOLERANCE < zz <= float(it.z_max) + TOLERANCE:
                            candidates.append(t_hit)
                t_mid = 0.5 * (ta + tb)
                zz_mid = oz + t_mid * dz
                if float(it.z_min) + TOLERANCE < zz_mid <= float(it.z_max) + TOLERANCE:
                    candidates.append(t_mid)
                if not candidates:
                    continue
                t_hit = min(candidates)
            else:
                t_hit = ta
                zz_mid = oz
                if not (float(it.z_min) + TOLERANCE < zz_mid <= float(it.z_max) + TOLERANCE):
                    continue
            blockers.append(
                {
                    "t": float(t_hit),
                    "cell_x": cx,
                    "cell_y": cy,
                    "z_hit": float(oz + float(t_hit) * dz),
                    "interval": it.as_dict() if hasattr(it, "as_dict") else {
                        "z_min": float(it.z_min),
                        "z_max": float(it.z_max),
                    },
                    "authority": "VW1_OCCUPANCY",
                }
            )
    # O3A entity occluders (analytic ray–sphere); owning entity excluded.
    try:
        from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
            entity_source_occlusion,
            object_body_held_optical_surfaces_is_active,
        )

        if object_body_held_optical_surfaces_is_active(config):
            ent = entity_source_occlusion(
                world,
                origin=(ox, oy, oz),
                direction_toward_source=L,
                exclude_entity_id=exclude_entity_id,
                config=config,
                bodies=entity_occlusion_bodies,
            )
            if not ent.get("clear") and ent.get("blocker") is not None:
                blockers.append({**dict(ent["blocker"]), "authority": "ENTITY_RAY_SPHERE"})
    except Exception:
        pass
    blockers.sort(
        key=lambda b: (
            float(b["t"]),
            str(b.get("authority") or ""),
            str(b.get("entity_id") or ""),
            int(b.get("cell_x", 0) or 0),
            int(b.get("cell_y", 0) or 0),
            float((b.get("interval") or {}).get("z_min", 0.0)),
        )
    )
    clear = len(blockers) == 0
    nearest = blockers[0] if blockers else None
    return {
        "clear": clear,
        "blocker": nearest,
        "los_distance": far if clear else (far * float(nearest["t"]) if nearest else None),
        "kernel": "directional_occupancy_occlusion_plus_entity_sphere",
        "ray_length": far,
        "origin_epsilon": RAY_ORIGIN_EPSILON,
        "columns_traversed": len(columns),
        "shared_primitives": ["traverse_xy_columns", "occupied_intervals_at"],
        "vw6_los_numerics_unchanged": True,
        "exclude_entity_id": exclude_entity_id,
    }


def evaluate_facet_illumination(
    world: Any,
    config: Any,
    facet: dict[str, Any],
    *,
    source: AbstractDirectionalLightSource | None = None,
    exclude_entity_id: str | None = None,
    entity_occlusion_bodies: list[tuple[str, Any]] | None = None,
) -> dict[str, Any]:
    cfg = getattr(config, "abstract_spectral_light_source_and_direct_transport", None)
    src = source or (cfg.source if cfg is not None else AbstractDirectionalLightSource())
    base = {
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "facet_id": facet.get("facet_id"),
        "source_id": src.source_id,
        "optical_band_identifiers": list(OPTICAL_BAND_IDENTIFIERS),
        "units": "ABSTRACT_NON_SI",
        "reflected_quantity_name": REFLECTED_QUANTITY_NAME,
        "organism_saw_light": False,
        "feeds_cognition": False,
        "not_display_rgb": True,
        "direction_convention": DIRECTION_CONVENTION,
    }
    try:
        n = facet.get("outward_unit_normal") or [0.0, 0.0, 1.0]
        c = facet.get("centre") or [0.0, 0.0, 0.0]
        nx, ny, nz = float(n[0]), float(n[1]), float(n[2])
        cx, cy, cz = float(c[0]), float(c[1]), float(c[2])
        if not all(math.isfinite(v) for v in (nx, ny, nz, cx, cy, cz)):
            return {
                **base,
                "state_class": STATE_INVALID,
                "incident_spectrum": _zero_bands(),
                "reflected_spectral_exitance_proxy": None,
                "cosine": 0.0,
            }
    except Exception:
        return {
            **base,
            "state_class": STATE_INVALID,
            "incident_spectrum": _zero_bands(),
            "reflected_spectral_exitance_proxy": None,
            "cosine": 0.0,
        }

    if not bool(src.enabled):
        return {
            **base,
            "state_class": STATE_DISABLED,
            "incident_spectrum": _zero_bands(),
            "reflected_spectral_exitance_proxy": _zero_bands(),
            "cosine": 0.0,
            "source_enabled": False,
            "reason": "source_disabled",
        }

    L = _normalize3(src.direction_toward_source)
    cosine = _dot((nx, ny, nz), L)
    if cosine <= TOLERANCE:
        return {
            **base,
            "state_class": STATE_BACK,
            "incident_spectrum": _zero_bands(),
            "reflected_spectral_exitance_proxy": _zero_bands(),
            "cosine": float(max(0.0, cosine)),
            "direction_toward_source": list(L),
            "reason": "back_facing",
        }

    ox = cx + RAY_ORIGIN_EPSILON * nx
    oy = cy + RAY_ORIGIN_EPSILON * ny
    oz = cz + RAY_ORIGIN_EPSILON * nz
    excl = exclude_entity_id if exclude_entity_id is not None else facet.get("entity_id")
    vis = _source_visibility(
        world,
        origin=(ox, oy, oz),
        direction_toward_source=L,
        config=config,
        exclude_entity_id=(str(excl) if excl is not None else None),
        entity_occlusion_bodies=entity_occlusion_bodies,
    )
    if not vis["clear"]:
        reason = "occupancy_occluded"
        blk = vis.get("blocker") or {}
        if str(blk.get("authority") or "") == "ENTITY_RAY_SPHERE":
            reason = "entity_occluded"
        return {
            **base,
            "state_class": STATE_OCCLUDED,
            "incident_spectrum": _zero_bands(),
            "reflected_spectral_exitance_proxy": _zero_bands(),
            "cosine": float(cosine),
            "direction_toward_source": list(L),
            "visibility": vis,
            "reason": reason,
        }

    spectrum = _clip_spectrum(src.source_spectrum)
    incident = [float(spectrum[b]) * float(cosine) for b in range(OPTICAL_BAND_COUNT)]

    o1_status = str(facet.get("o1_status") or "")
    R = facet.get("spectral_reflectance")
    if R is None and facet.get("material_composition_reference") is not None:
        from mechanistic_mind.physical_system.physical_optical_material_profile import (
            STATUS_RESOLVED,
            resolve_optical_material_profile,
        )

        resolved = resolve_optical_material_profile(facet.get("material_composition_reference"))
        o1_status = str(resolved.get("status") or o1_status)
        R = resolved.get("spectral_reflectance")
        if o1_status != STATUS_RESOLVED:
            return {
                **base,
                "state_class": STATE_UNKNOWN_MAT,
                "incident_spectrum": incident,
                "reflected_spectral_exitance_proxy": None,
                "cosine": float(cosine),
                "direction_toward_source": list(L),
                "visibility": vis,
                "o1_status": o1_status,
                "reason": "unknown_material_profile",
                "geometry_visibility_reported": True,
            }
    elif o1_status and o1_status not in ("PROFILE_RESOLVED", ""):
        return {
            **base,
            "state_class": STATE_UNKNOWN_MAT,
            "incident_spectrum": incident,
            "reflected_spectral_exitance_proxy": None,
            "cosine": float(cosine),
            "direction_toward_source": list(L),
            "visibility": vis,
            "o1_status": o1_status,
            "reason": "unknown_material_profile",
            "geometry_visibility_reported": True,
        }

    if R is None or len(list(R)) < OPTICAL_BAND_COUNT:
        return {
            **base,
            "state_class": STATE_UNKNOWN_MAT,
            "incident_spectrum": incident,
            "reflected_spectral_exitance_proxy": None,
            "cosine": float(cosine),
            "direction_toward_source": list(L),
            "visibility": vis,
            "reason": "missing_reflectance",
            "geometry_visibility_reported": True,
        }

    reflected = [float(incident[b]) * float(R[b]) for b in range(OPTICAL_BAND_COUNT)]
    return {
        **base,
        "state_class": STATE_DIRECT,
        "incident_spectrum": incident,
        "reflected_spectral_exitance_proxy": reflected,
        "cosine": float(cosine),
        "direction_toward_source": list(L),
        "visibility": vis,
        "o1_status": o1_status or "PROFILE_RESOLVED",
        "reason": "direct_illuminated",
    }


@dataclass
class O3LightCache:
    key_digest: str
    key_parts: dict[str, str]
    results: tuple[dict[str, Any], ...]
    result_checksum: str
    state_counts: dict[str, int]
    build_count: int = 0
    hit_count: int = 0
    miss_count: int = 0
    occlusion_queries: int = 0
    evaluated: int = 0


WORLD_CACHE_ATTR = "_o3_direct_light_cache"


def _cache_key(world: Any, config: Any) -> dict[str, str]:
    from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
        ensure_exposed_surface_cache,
    )
    from mechanistic_mind.physical_system.physical_optical_material_profile import REGISTRY_VERSION
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

    cfg = getattr(config, "abstract_spectral_light_source_and_direct_transport", None)
    src = cfg.source if cfg is not None else AbstractDirectionalLightSource()
    o2 = ensure_exposed_surface_cache(world, config)
    st = state_of(world)
    return {
        "o3_schema": SCHEMA,
        "o3_profile": PROFILE,
        "source_digest": src.digest(),
        "vw1_digest": str(st.digest()) if st is not None else "vw1:absent",
        "o2_facet_checksum": str(o2.facet_checksum) if o2 is not None else "o2:absent",
        "o1_registry_version": str(REGISTRY_VERSION),
    }


def _key_digest(parts: dict[str, str]) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _results_checksum(rows: Iterable[dict[str, Any]]) -> str:
    payload = [
        {
            "facet_id": r.get("facet_id"),
            "state_class": r.get("state_class"),
            "incident": r.get("incident_spectrum"),
            "reflected": r.get("reflected_spectral_exitance_proxy"),
        }
        for r in rows
    ]
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def build_direct_light_field(world: Any, config: Any) -> O3LightCache:
    from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
        ensure_exposed_surface_cache,
    )
    from mechanistic_mind.physical_system.physical_optical_material_profile import (
        resolve_optical_material_profile,
    )

    key_parts = _cache_key(world, config)
    key_digest = _key_digest(key_parts)
    o2 = ensure_exposed_surface_cache(world, config)
    facets = list(o2.facets) if o2 is not None else []
    cfg = getattr(config, "abstract_spectral_light_source_and_direct_transport", None)
    src = cfg.source if cfg is not None else AbstractDirectionalLightSource()

    rows: list[dict[str, Any]] = []
    occlusion_q = 0
    for facet in facets:
        f = facet
        if f.get("spectral_reflectance") is None and f.get("material_composition_reference") is not None:
            resolved = resolve_optical_material_profile(f.get("material_composition_reference"))
            f = {
                **f,
                "spectral_reflectance": resolved.get("spectral_reflectance"),
                "o1_status": resolved.get("status"),
            }
        row = evaluate_facet_illumination(world, config, f, source=src)
        if row.get("visibility") is not None:
            occlusion_q += 1
        rows.append(row)

    rows.sort(key=lambda r: (str(r.get("facet_id") or ""), str(r.get("state_class") or "")))
    counts: dict[str, int] = {}
    for r in rows:
        st = str(r.get("state_class") or STATE_NOT_EVAL)
        counts[st] = counts.get(st, 0) + 1

    return O3LightCache(
        key_digest=key_digest,
        key_parts=key_parts,
        results=tuple(rows),
        result_checksum=_results_checksum(rows),
        state_counts=counts,
        build_count=1,
        hit_count=0,
        miss_count=1,
        occlusion_queries=occlusion_q,
        evaluated=len(rows),
    )


def ensure_direct_light_cache(world: Any, config: Any) -> O3LightCache | None:
    if not abstract_spectral_light_source_and_direct_transport_is_active(config):
        if hasattr(world, WORLD_CACHE_ATTR):
            setattr(world, WORLD_CACHE_ATTR, None)
        return None
    from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
        exposed_surface_optical_interaction_authority_is_active,
    )

    if not exposed_surface_optical_interaction_authority_is_active(config):
        return None

    key_parts = _cache_key(world, config)
    key_digest = _key_digest(key_parts)
    cached = getattr(world, WORLD_CACHE_ATTR, None)
    if isinstance(cached, O3LightCache) and cached.key_digest == key_digest:
        cached.hit_count += 1
        return cached
    built = build_direct_light_field(world, config)
    if isinstance(cached, O3LightCache):
        built.build_count = int(cached.build_count) + 1
        built.miss_count = int(cached.miss_count) + 1
        built.hit_count = int(cached.hit_count)
    setattr(world, WORLD_CACHE_ATTR, built)
    return built


def invalidate_direct_light_cache(world: Any) -> None:
    if hasattr(world, WORLD_CACHE_ATTR):
        setattr(world, WORLD_CACHE_ATTR, None)


def query_source_state(config: Any) -> dict[str, Any]:
    cfg = getattr(config, "abstract_spectral_light_source_and_direct_transport", None)
    if cfg is None:
        return {"enabled": False, "schema": SCHEMA}
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "capability_enabled": bool(cfg.enabled),
        "source": cfg.source.to_dict(),
        "source_static_v1": True,
        "label": "ABSTRACT NON-SI PHYSICAL LIGHT · DIRECT TRANSPORT ONLY · NOT ORGANISM VISION · NOT DISPLAY RGB",
    }


def query_facet_illumination(world: Any, config: Any, facet_id: str) -> dict[str, Any]:
    cache = ensure_direct_light_cache(world, config)
    if cache is None:
        return {"enabled": False, "state_class": STATE_NOT_EVAL, "facet_id": facet_id}
    for row in cache.results:
        if str(row.get("facet_id")) == str(facet_id):
            return {**row, "enabled": True, "cache_key_digest": cache.key_digest}
    return {
        "enabled": True,
        "state_class": STATE_NOT_EVAL,
        "facet_id": facet_id,
        "incident_spectrum": None,
        "reflected_spectral_exitance_proxy": None,
        "reason": "facet_not_in_evaluated_set",
        "distinct_from_zero": True,
    }


def query_illumination_region(
    world: Any, config: Any, *, x0: float, y0: float, x1: float, y1: float
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
        ensure_exposed_surface_cache,
    )

    cache = ensure_direct_light_cache(world, config)
    o2 = ensure_exposed_surface_cache(world, config)
    if cache is None or o2 is None:
        return {"enabled": False, "results": []}
    xa, xb = sorted((float(x0), float(x1)))
    ya, yb = sorted((float(y0), float(y1)))
    ids = {
        f["facet_id"]
        for f in o2.facets
        if xa - TOLERANCE <= float(f["centre"][0]) <= xb + TOLERANCE
        and ya - TOLERANCE <= float(f["centre"][1]) <= yb + TOLERANCE
    }
    rows = [r for r in cache.results if r.get("facet_id") in ids]
    return _payload(cache, rows)


def query_illumination_candidates(
    world: Any,
    config: Any,
    *,
    point: tuple[float, float, float],
    max_range: float,
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
        query_exposed_facets_candidates,
    )

    cache = ensure_direct_light_cache(world, config)
    if cache is None:
        return {"enabled": False, "results": []}
    cand = query_exposed_facets_candidates(world, config, point=point, max_range=max_range)
    ids = {f["facet_id"] for f in cand.get("facets") or []}
    rows = [r for r in cache.results if r.get("facet_id") in ids]
    return _payload(cache, rows)


def query_illumination_global(world: Any, config: Any) -> dict[str, Any]:
    cache = ensure_direct_light_cache(world, config)
    if cache is None:
        return {
            "enabled": False,
            "schema": SCHEMA,
            "label": "ABSTRACT NON-SI PHYSICAL LIGHT · DIRECT TRANSPORT ONLY · NOT ORGANISM VISION · NOT DISPLAY RGB",
            "results": [],
        }
    return _payload(cache, list(cache.results))


def _payload(cache: O3LightCache, rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "enabled": True,
        "label": "ABSTRACT NON-SI PHYSICAL LIGHT · DIRECT TRANSPORT ONLY · NOT ORGANISM VISION · NOT DISPLAY RGB",
        "organism_saw_light": False,
        "feeds_cognition": False,
        "reflected_quantity_name": REFLECTED_QUANTITY_NAME,
        "cache_key_digest": cache.key_digest,
        "cache_key_parts": dict(cache.key_parts),
        "result_checksum": _results_checksum(rows),
        "full_set_checksum": cache.result_checksum,
        "state_counts": dict(cache.state_counts),
        "evaluated": int(cache.evaluated),
        "occlusion_queries": int(cache.occlusion_queries),
        "cache_hits": int(cache.hit_count),
        "cache_misses": int(cache.miss_count),
        "cache_builds": int(cache.build_count),
        "object_body_extension_required_before_o4": OBJECT_BODY_EXTENSION_REQUIRED_BEFORE_O4,
        "result_count": len(rows),
        "results": rows,
    }


def researcher_summary(world: Any, config: Any) -> dict[str, Any]:
    src = query_source_state(config)
    cache = ensure_direct_light_cache(world, config)
    if cache is None:
        return {**src, "enabled": False, "evaluated_facet_count": 0}
    return {
        **src,
        "enabled": True,
        "evaluated_facet_count": int(cache.evaluated),
        "state_counts": dict(cache.state_counts),
        "result_checksum": cache.result_checksum,
        "cache_key_digest": cache.key_digest,
        "cache_hits": int(cache.hit_count),
        "cache_misses": int(cache.miss_count),
        "cache_builds": int(cache.build_count),
        "occlusion_queries": int(cache.occlusion_queries),
        "o1_o2_o3_versions": {
            "o3_schema": SCHEMA,
            "o3_profile": PROFILE,
            "o2_facet_checksum": cache.key_parts.get("o2_facet_checksum"),
            "o1_registry_version": cache.key_parts.get("o1_registry_version"),
            "vw1_digest": cache.key_parts.get("vw1_digest"),
        },
        "object_body_extension_required_before_o4": OBJECT_BODY_EXTENSION_REQUIRED_BEFORE_O4,
        "organism_saw_light": False,
        "label": "ABSTRACT NON-SI PHYSICAL LIGHT · DIRECT TRANSPORT ONLY · NOT ORGANISM VISION · NOT DISPLAY RGB",
    }


PRIVACY_DENYLIST_TOKENS = (
    CAPABILITY,
    SCHEMA,
    PROFILE,
    AUTHORITY,
    "abstract_spectral_light_source_and_direct_transport",
    "incident_spectrum",
    "reflected_spectral_exitance_proxy",
    "abstract_directional_source_0",
    "DIRECT_ILLUMINATED",
    "OCCLUDED_ZERO",
    "BACK_FACING_ZERO",
    "SOURCE_DISABLED_ZERO",
    "UNKNOWN_MATERIAL_RESPONSE",
    SOURCE_ID,
)


def build_abstract_spectral_light_causal_reconstruction(
    evidence: dict[str, Any] | None = None,
    *,
    on_progress: Any | None = None,
) -> dict[str, Any]:
    """Analyzer causal reconstruction for O3 (researcher-only; no organism-saw claim).

    Accepts a researcher query/summary payload or snapshot config fragment.
    Uses the repaired progress callback phases when provided.
    """
    ev = evidence if isinstance(evidence, dict) else {}
    if on_progress:
        on_progress("INDEX_PHYSICAL_RECEIPTS", 0, 1)
    src = ev.get("source") if isinstance(ev.get("source"), dict) else {}
    if not src and isinstance(ev.get("config"), dict):
        cfg = ev["config"].get("abstract_spectral_light_source_and_direct_transport")
        if isinstance(cfg, dict):
            src = cfg.get("source") if isinstance(cfg.get("source"), dict) else {}
            ev = {**ev, "source": src, "capability_enabled": cfg.get("enabled")}
    counts = ev.get("state_counts") if isinstance(ev.get("state_counts"), dict) else {}
    if on_progress:
        on_progress("CLASSIFY_NEGATIVE_CAUSES", 1, 1)
    illuminated = int(counts.get(STATE_DIRECT, 0) or 0)
    back = int(counts.get(STATE_BACK, 0) or 0)
    occluded = int(counts.get(STATE_OCCLUDED, 0) or 0)
    disabled = int(counts.get(STATE_DISABLED, 0) or 0)
    unknown = int(counts.get(STATE_UNKNOWN_MAT, 0) or 0)
    not_eval = int(counts.get(STATE_NOT_EVAL, 0) or 0)
    if on_progress:
        on_progress("AGGREGATING", 1, 1)
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "section": "ABSTRACT SPECTRAL LIGHT · DIRECT TRANSPORT (O3)",
        "causal_chain": [
            "source",
            "facet_orientation",
            "occupancy_visibility",
            "incident_bands",
            "o1_reflectance",
            "reflected_spectral_exitance_proxy",
        ],
        "source": {
            "source_id": src.get("source_id") or SOURCE_ID,
            "enabled": src.get("enabled"),
            "direction_toward_source": src.get("direction_toward_source"),
            "source_spectrum": src.get("source_spectrum"),
            "direction_convention": DIRECTION_CONVENTION,
            "static_v1": True,
        },
        "state_counts": {
            STATE_DIRECT: illuminated,
            STATE_BACK: back,
            STATE_OCCLUDED: occluded,
            STATE_DISABLED: disabled,
            STATE_UNKNOWN_MAT: unknown,
            STATE_NOT_EVAL: not_eval,
        },
        "illuminated_count": illuminated,
        "back_facing_count": back,
        "occluded_count": occluded,
        "unknown_material_count": unknown,
        "missing_vs_zero": {
            "not_evaluated_distinct_from_zero": True,
            "not_evaluated_count": not_eval,
            "physical_zero_classes": [STATE_BACK, STATE_OCCLUDED, STATE_DISABLED],
        },
        "generations": ev.get("o1_o2_o3_versions") or ev.get("cache_key_parts") or {},
        "result_checksum": ev.get("result_checksum"),
        "evaluated_facet_count": ev.get("evaluated_facet_count") or ev.get("evaluated"),
        "deterministic_query_coverage": True,
        "organism_saw_light": False,
        "organism_reception": False,
        "feeds_cognition": False,
        "hidden_ambient_light": False,
        "object_body_extension_required_before_o4": OBJECT_BODY_EXTENSION_REQUIRED_BEFORE_O4,
        "label": "ABSTRACT NON-SI PHYSICAL LIGHT · DIRECT TRANSPORT ONLY · NOT ORGANISM VISION · NOT DISPLAY RGB",
        "researcher_only": True,
    }


def format_abstract_spectral_light_section(summary: dict[str, Any] | None) -> str:
    s = summary or {}
    counts = s.get("state_counts") or {}
    return "\n".join([
        "ABSTRACT SPECTRAL LIGHT · DIRECT TRANSPORT (O3)",
        f"  source_id: {(s.get('source') or {}).get('source_id')}",
        f"  source_enabled: {(s.get('source') or {}).get('enabled')}",
        f"  illuminated: {s.get('illuminated_count', counts.get(STATE_DIRECT, 0))}",
        f"  back_facing_zero: {s.get('back_facing_count', counts.get(STATE_BACK, 0))}",
        f"  occluded_zero: {s.get('occluded_count', counts.get(STATE_OCCLUDED, 0))}",
        f"  unknown_material: {s.get('unknown_material_count', counts.get(STATE_UNKNOWN_MAT, 0))}",
        f"  not_evaluated: {(s.get('missing_vs_zero') or {}).get('not_evaluated_count', 0)}",
        "  organism_saw_light: False",
        "  organism_reception: NOT_IMPLEMENTED",
        f"  object_body_extension_required_before_o4: {s.get('object_body_extension_required_before_o4', True)}",
        "  label: ABSTRACT NON-SI PHYSICAL LIGHT · DIRECT TRANSPORT ONLY · NOT ORGANISM VISION · NOT DISPLAY RGB",
    ])

