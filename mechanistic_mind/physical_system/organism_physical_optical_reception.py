"""Acanthostega O4 · Organism physical optical reception V1.

Schema: ORGANISM_PHYSICAL_OPTICAL_RECEPTION_V1
Capability: organism_physical_optical_reception
Profile: O3_SURFACE_TO_VW6_RECEPTOR_DIRECT_RECEPTION_O4_V1
Authority: PHYSICAL_ABSTRACT_OPTICAL_FIELD_TO_ORGANISM_RECEPTOR

Causal path:
  O3 source → O2/O3A surface → O1 reflectance → surface→eye direct return
  → VW1/entity occlusion → receptor bin accumulate → phenotype once → exo_*/surface_c*

Does not use illumination_intensity, CANONICAL_OPTICAL_RESPONSE, VW7 pixels, or optical_radius.
Abstract non-SI. No human RGB / wavelength / lux claims.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "ORGANISM_PHYSICAL_OPTICAL_RECEPTION_V1"
CAPABILITY = "organism_physical_optical_reception"
PROFILE = "O3_SURFACE_TO_VW6_RECEPTOR_DIRECT_RECEPTION_O4_V1"
AUTHORITY = "PHYSICAL_ABSTRACT_OPTICAL_FIELD_TO_ORGANISM_RECEPTOR"
MECHANISM_ID = CAPABILITY

OPTICAL_BAND_COUNT = 6
OPTICAL_BAND_IDENTIFIERS = tuple(f"optical_band_{i}" for i in range(OPTICAL_BAND_COUNT))
K_VISUAL = 0.15  # abstract; contribution ∝ 1/(1 + k_visual * d³d²); NOT SI inverse-square
VISUAL_CAUSAL_DELAY_TICKS = 0  # evaluated within observation tick (O5 not yet)
COGNITION_SCHEMA = "EXO3_PLUS_SURFACE_C3x3_ANONYMOUS_BAND_PAIR_FOLD_6_TO_3_V1"
BAND_FOLD_POLICY = "PAIR_MEAN_6_TO_3"  # surface_c0=(b0+b1)/2 …; exo = sum of 6 bands
MAX_TRACE_CONTRIBUTORS = 32
TOLERANCE = 1e-12
RAY_EPS = 1e-6

REASON_ACCEPTED = "ACCEPTED"
REASON_BACK_FACING = "BACK_FACING_ZERO"
REASON_OUTSIDE_FOV = "OUTSIDE_FOV"
REASON_OUT_OF_RANGE = "OUT_OF_RANGE"
REASON_OCCLUDED_VW1 = "OCCLUDED_VW1"
REASON_OCCLUDED_ENTITY = "OCCLUDED_ENTITY"
REASON_UNKNOWN_MATERIAL = "UNKNOWN_MATERIAL"
REASON_ZERO_REFLECTED = "PHYSICALLY_ILLUMINATED_ZERO"
REASON_SOURCE_DISABLED = "SOURCE_DISABLED_ZERO"
REASON_NO_REFLECTED = "NO_REFLECTED_PROXY"
REASON_INVALID = "INVALID_GEOMETRY"

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "optical_band_count": OPTICAL_BAND_COUNT,
    "optical_band_identifiers": list(OPTICAL_BAND_IDENTIFIERS),
    "si_wavelength_mapping": False,
    "si_radiometry": False,
    "k_visual": K_VISUAL,
    "distance_attenuation_law": "1/(1+k_visual*distance_3d^2)",
    "surface_facing_term": "max(0, n·V_to_eye)",
    "visual_causal_delay_ticks": VISUAL_CAUSAL_DELAY_TICKS,
    "cognition_schema": COGNITION_SCHEMA,
    "band_fold_policy": BAND_FOLD_POLICY,
    "legacy_illumination_double_counted": False,
    "legacy_optical_response_used_as_physical_material": False,
    "o4_authoritative_when_enabled": True,
    "organism_reception": True,
    "researcher_only_trace": True,
    "not_human_rgb": True,
    "vw7_pixels_not_used": True,
}


@dataclass
class OrganismPhysicalOpticalReceptionConfig:
    enabled: bool = False
    schema: str = SCHEMA
    profile: str = PROFILE
    k_visual: float = K_VISUAL
    max_trace_contributors: int = MAX_TRACE_CONTRIBUTORS

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.enabled),
            "schema": str(self.schema),
            "profile": str(self.profile),
            "k_visual": float(self.k_visual),
            "max_trace_contributors": int(self.max_trace_contributors),
            **AUTHORITY_FLAGS,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "OrganismPhysicalOpticalReceptionConfig":
        if not isinstance(data, dict) or not data:
            return cls(enabled=False)
        return cls(
            enabled=bool(data.get("enabled", False)),
            schema=str(data.get("schema") or SCHEMA),
            profile=str(data.get("profile") or PROFILE),
            k_visual=float(data.get("k_visual", K_VISUAL) or K_VISUAL),
            max_trace_contributors=int(data.get("max_trace_contributors", MAX_TRACE_CONTRIBUTORS) or MAX_TRACE_CONTRIBUTORS),
        )


def organism_physical_optical_reception_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "organism_physical_optical_reception", None)
    return bool(cfg is not None and getattr(cfg, "enabled", False))


def set_organism_physical_optical_reception(config: Any, enabled: bool) -> None:
    if config is None:
        return
    on = bool(enabled) and str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cur = getattr(config, "organism_physical_optical_reception", None)
    if cur is None:
        config.organism_physical_optical_reception = OrganismPhysicalOpticalReceptionConfig(enabled=on)
    else:
        cur.enabled = on
        cur.schema = SCHEMA
        cur.profile = PROFILE


def organism_physical_optical_reception_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": bool(enabled),
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "summary": "Physical O3/O3A surface→VW6 receptor direct reception (O4).",
        "agent_accessible_result": True,
        "researcher_trace": True,
    }


def _norm3(v: tuple[float, float, float]) -> tuple[float, float, float]:
    x, y, z = float(v[0]), float(v[1]), float(v[2])
    mag = math.sqrt(x * x + y * y + z * z)
    if not math.isfinite(mag) or mag <= TOLERANCE:
        return (0.0, 0.0, 1.0)
    return (x / mag, y / mag, z / mag)


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _zero6() -> list[float]:
    return [0.0] * OPTICAL_BAND_COUNT


def _fold_bands_to_3(bands: list[float]) -> list[float]:
    """Anonymous 6→3 pair-mean for RICH surface_c* cognition boundary."""
    b = list(bands) + [0.0] * OPTICAL_BAND_COUNT
    return [
        0.5 * (float(b[0]) + float(b[1])),
        0.5 * (float(b[2]) + float(b[3])),
        0.5 * (float(b[4]) + float(b[5])),
    ]


def _clip01(v: float) -> float:
    return float(max(0.0, min(1.0, v)))


def _heading_of(body: Any) -> float:
    if bool(getattr(body, "_articulated_head_enabled", False)):
        from mechanistic_mind.physical_system.near_field_exteroception import wrap_angle
        return float(wrap_angle(float(getattr(body, "theta", 0.0) or 0.0) + float(getattr(body, "head_relative_angle", 0.0) or 0.0)))
    return float(getattr(body, "theta", 0.0) or 0.0)


def _rel_bearing_xy(eye: tuple[float, float, float], target: tuple[float, float, float], heading: float, width: int, height: int) -> float:
    from mechanistic_mind.planet.topology import toroidal_delta
    from mechanistic_mind.physical_system.near_field_exteroception import wrap_angle

    dx = toroidal_delta(eye[0], target[0], width)
    dy = toroidal_delta(eye[1], target[1], height)
    bearing = math.atan2(dy, dx)
    return float(wrap_angle(bearing - heading))


def _distance3(eye: tuple[float, float, float], target: tuple[float, float, float], width: int, height: int) -> float:
    from mechanistic_mind.planet.topology import toroidal_delta

    dx = toroidal_delta(eye[0], target[0], width)
    dy = toroidal_delta(eye[1], target[1], height)
    dz = float(target[2]) - float(eye[2])
    return float(math.sqrt(dx * dx + dy * dy + dz * dz))


def _attenuation(distance: float, k_visual: float) -> float:
    d = max(0.0, float(distance))
    return float(1.0 / (1.0 + float(k_visual) * d * d))


def _eye_surface_visibility(
    world: Any,
    *,
    eye: tuple[float, float, float],
    target: tuple[float, float, float],
    exclude_entity_id: str | None,
    config: Any,
    bodies: list[tuple[str, Any]] | None,
    exclude_entity_ids: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """Physical eye→surface LOS: VW1 occupancy + O3A entity spheres.

    Excludes surface-owner entity ids and, when provided, the observing body so the
    organism does not occlude its own eye rays (integration wiring; not a new optical law).
    """
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        occupancy_line_of_sight,
    )

    excluded: set[str] = set()
    if exclude_entity_id is not None:
        excluded.add(str(exclude_entity_id))
    if exclude_entity_ids:
        for eid in exclude_entity_ids:
            if eid is not None:
                excluded.add(str(eid))

    los = occupancy_line_of_sight(
        world,
        float(eye[0]), float(eye[1]), float(eye[2]),
        float(target[0]), float(target[1]), float(target[2]),
        config=config,
    )
    clear = bool(los.get("visible", False)) and not bool(los.get("occluded", False))
    blocker = los.get("blocker")
    authority = "VW1_OCCUPANCY"
    # Entity occluders along eye→target (exclude owning entity of target surface + observer).
    try:
        from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
            collect_entity_occluders,
            object_body_held_optical_surfaces_is_active,
            ray_sphere_intersection_t,
        )

        if object_body_held_optical_surfaces_is_active(config):
            grid = getattr(world, "T", None)
            w = int(grid.shape[1]) if grid is not None else None
            h = int(grid.shape[0]) if grid is not None else None
            D = (
                float(target[0]) - float(eye[0]),
                float(target[1]) - float(eye[1]),
                float(target[2]) - float(eye[2]),
            )
            # Fix periodic: use toroidal unwrap for XY component of D
            if w is not None and h is not None:
                from mechanistic_mind.planet.topology import toroidal_delta
                D = (
                    toroidal_delta(eye[0], target[0], w),
                    toroidal_delta(eye[1], target[1], h),
                    float(target[2]) - float(eye[2]),
                )
            best_t = None
            best = None
            for occ in collect_entity_occluders(world, config, bodies=bodies):
                if str(occ["entity_id"]) in excluded:
                    continue
                t = ray_sphere_intersection_t(
                    eye, D, occ["centre"], float(occ["radius"]), width=w, height=h,
                )
                if t is None:
                    continue
                # Terminal surface: ignore hits extremely near t=1 (target itself)
                if t >= 1.0 - 1e-4:
                    continue
                if best_t is None or t < best_t:
                    best_t = t
                    best = {**occ, "t": float(t)}
            if best is not None:
                # Entity blocks if closer than VW1 (or VW1 clear)
                vw1_t = None
                if isinstance(blocker, dict) and blocker.get("t") is not None:
                    try:
                        vw1_t = float(blocker["t"])
                    except Exception:
                        vw1_t = None
                if (not clear) and vw1_t is not None and best_t is not None and best_t >= vw1_t:
                    pass  # VW1 nearer
                else:
                    clear = False
                    blocker = {
                        "t": float(best_t),
                        "entity_id": best["entity_id"],
                        "entity_class": best.get("entity_class"),
                        "authority": "ENTITY_RAY_SPHERE",
                    }
                    authority = "ENTITY_RAY_SPHERE"
    except Exception:
        pass
    return {
        "clear": bool(clear),
        "blocker": blocker,
        "authority": authority if not clear else "CLEAR",
        "kernel": "eye_surface_vw1_plus_entity_sphere",
        "vw6_los_numerics_unchanged_for_legacy_path": True,
    }


def _collect_candidate_surfaces(
    world: Any,
    config: Any,
    *,
    eye: tuple[float, float, float],
    max_range: float,
    bodies: list[tuple[str, Any]] | None,
) -> list[dict[str, Any]]:
    """Bounded O2 facet region + O3A samples within max_range."""
    from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
        exposed_surface_optical_interaction_authority_is_active,
        query_exposed_facets_region,
    )
    from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
        object_body_held_optical_surfaces_is_active,
        query_entity_surface_candidates,
        ensure_entity_surface_cache,
    )
    from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
        evaluate_facet_illumination,
        abstract_spectral_light_source_and_direct_transport_is_active,
    )

    out: list[dict[str, Any]] = []
    # Terrain O2 facets in XY bbox around eye
    if exposed_surface_optical_interaction_authority_is_active(config):
        r = float(max_range)
        reg = query_exposed_facets_region(
            world, config, x0=eye[0] - r, y0=eye[1] - r, x1=eye[0] + r, y1=eye[1] + r,
        )
        for f in reg.get("facets") or []:
            # Evaluate O3 illumination for this facet
            illum = None
            if abstract_spectral_light_source_and_direct_transport_is_active(config):
                illum = evaluate_facet_illumination(world, config, f)
            out.append({
                "surface_id": f.get("facet_id"),
                "entity_id": f"terrain:{f.get('cell_x')}:{f.get('cell_y')}",
                "entity_class": "TERRAIN_FACET",
                "centre": list(f.get("centre") or [0, 0, 0]),
                "outward_unit_normal": list(f.get("outward_unit_normal") or [0, 0, 1]),
                "area_weight": float(f.get("area") or 1.0),
                "spectral_reflectance": f.get("spectral_reflectance"),
                "o1_status": f.get("o1_status"),
                "illumination": illum,
                "exclude_entity_id": None,  # terrain: exclude by interval via LOS endpoint skip
            })
    # O3A entity samples
    if object_body_held_optical_surfaces_is_active(config):
        cache = ensure_entity_surface_cache(world, config, bodies=bodies)
        cand = query_entity_surface_candidates(
            world, config, point=eye, max_range=max_range, bodies=bodies,
        )
        illum_by_id = {}
        if cache is not None:
            for row in cache.illuminations:
                illum_by_id[str(row.get("sample_id"))] = row
        for s in cand.get("samples") or []:
            sid = str(s.get("sample_id"))
            out.append({
                "surface_id": sid,
                "entity_id": s.get("entity_id"),
                "entity_class": s.get("entity_class"),
                "centre": list(s.get("centre") or [0, 0, 0]),
                "outward_unit_normal": list(s.get("outward_unit_normal") or [0, 0, 1]),
                "area_weight": float(s.get("area_weight") or 1.0),
                "spectral_reflectance": s.get("spectral_reflectance"),
                "o1_status": s.get("o1_status"),
                "illumination": illum_by_id.get(sid),
                "exclude_entity_id": str(s.get("entity_id")),
            })
    out.sort(key=lambda s: (str(s.get("entity_class") or ""), str(s.get("surface_id") or "")))
    return out


def sample_physical_optical_reception(
    *,
    world: Any,
    body: Any,
    nfe_cfg: Any,
    physical_config: Any,
    tick: int | None = None,
    foreign_bodies: list[tuple[Any, Any]] | None = None,
    diagnostic: bool = False,
) -> dict[str, Any]:
    """Authoritative O4 visual sample — replaces legacy radiometry when enabled."""
    from mechanistic_mind.physical_system.near_field_exteroception import (
        N_EXO_CHANNELS,
        N_SURFACE_OPTICAL_CHANNELS,
        angular_sensitivity,
        clamp_surface_discrimination,
        clamp_vision_radius,
        fov_sector_index,
        moore_max_candidates,
    )
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        sensor_eye_xyz,
    )
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime
    from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
        attach_optical_body_refs,
    )

    o4_cfg = getattr(physical_config, "organism_physical_optical_reception", None)
    k_visual = float(getattr(o4_cfg, "k_visual", K_VISUAL) if o4_cfg is not None else K_VISUAL)
    max_trace = int(getattr(o4_cfg, "max_trace_contributors", MAX_TRACE_CONTRIBUTORS) if o4_cfg is not None else MAX_TRACE_CONTRIBUTORS)

    t = int(getattr(world, "tick", 0) if tick is None else tick)
    h, w = int(world.T.shape[0]), int(world.T.shape[1])
    eye = sensor_eye_xyz(body, physical_config)
    heading = _heading_of(body)
    radius = clamp_vision_radius(getattr(nfe_cfg, "radius", 1))
    max_range = float(radius) * math.sqrt(2.0) + 0.75  # Moore radius in cell units
    fov = float(getattr(nfe_cfg, "fov_deg", 120.0) or 120.0)
    gain = float(getattr(nfe_cfg, "gain", 1.0) or 1.0)
    saturation = float(getattr(nfe_cfg, "saturation", 1.0) or 1.0)
    threshold = float(getattr(nfe_cfg, "threshold", 0.04) or 0.04)
    disc_mode = clamp_surface_discrimination(getattr(nfe_cfg, "visual_surface_discrimination", "OFF"))
    n_surf = N_SURFACE_OPTICAL_CHANNELS if disc_mode in ("LOW", "RICH") else 0
    if disc_mode == "LOW":
        n_surf = 1

    # Body refs for entity samples / occlusion
    bodies: list[tuple[str, Any]] = []
    try:
        # Prefer foreign + self if available via runtime stash
        bodies = list(getattr(world, "_o3a_body_refs", None) or [])
    except Exception:
        bodies = []
    if not bodies:
        bid = f"body-{getattr(body, 'tick', 0)}"
        # Use stable self id
        bodies = [("body-0", body)]
        if foreign_bodies:
            for i, item in enumerate(foreign_bodies):
                fb = item[0] if isinstance(item, (list, tuple)) else item
                bodies.append((f"body-{i+1}", fb))
    attach_optical_body_refs(world, bodies)

    # Observing body must not occlude its own eye→surface rays (terrain exclude is None).
    observer_entity_id: str | None = None
    for bid, b in bodies:
        if b is body:
            observer_entity_id = str(bid)
            break
    if observer_entity_id is None and bodies:
        observer_entity_id = str(bodies[0][0])

    candidates = _collect_candidate_surfaces(
        world, physical_config, eye=eye, max_range=max_range, bodies=bodies,
    )

    # Per angular bin: accumulate 6 raw bands
    raw_bins = [[0.0] * OPTICAL_BAND_COUNT for _ in range(N_EXO_CHANNELS)]
    reason_counts: dict[str, int] = {}
    contributors: list[dict[str, Any]] = []
    accepted = 0
    rejected = 0
    unknown_kept = 0
    los_queries = 0

    # Per-ray nearest winner: group by sector then keep nearer accepted surfaces summing
    # (linear sum of all facing visible — nearer-blocker already in LOS)
    for surf in candidates:
        centre = surf["centre"]
        normal = _norm3(tuple(surf["outward_unit_normal"]))
        dist = _distance3(eye, (float(centre[0]), float(centre[1]), float(centre[2])), w, h)
        if dist > max_range + TOLERANCE:
            reason_counts[REASON_OUT_OF_RANGE] = reason_counts.get(REASON_OUT_OF_RANGE, 0) + 1
            rejected += 1
            continue
        rel = _rel_bearing_xy(eye, (float(centre[0]), float(centre[1]), float(centre[2])), heading, w, h)
        ang = angular_sensitivity(rel, fov)
        if ang <= 0.0:
            reason_counts[REASON_OUTSIDE_FOV] = reason_counts.get(REASON_OUTSIDE_FOV, 0) + 1
            rejected += 1
            continue
        bin_i = fov_sector_index(rel, fov)
        if bin_i is None:
            reason_counts[REASON_OUTSIDE_FOV] = reason_counts.get(REASON_OUTSIDE_FOV, 0) + 1
            rejected += 1
            continue

        # Vector surface → eye
        from mechanistic_mind.planet.topology import toroidal_delta
        V = _norm3((
            toroidal_delta(float(centre[0]), eye[0], w),
            toroidal_delta(float(centre[1]), eye[1], h),
            float(eye[2]) - float(centre[2]),
        ))
        facing = max(0.0, _dot(normal, V))
        if facing <= TOLERANCE:
            reason_counts[REASON_BACK_FACING] = reason_counts.get(REASON_BACK_FACING, 0) + 1
            rejected += 1
            continue

        # Offset target slightly along normal toward free side for LOS terminal
        tx = float(centre[0]) + RAY_EPS * normal[0]
        ty = float(centre[1]) + RAY_EPS * normal[1]
        tz = float(centre[2]) + RAY_EPS * normal[2]
        # Eye origin slightly offset along V from eye to avoid self
        ox = float(eye[0]) + RAY_EPS * V[0]
        oy = float(eye[1]) + RAY_EPS * V[1]
        oz = float(eye[2]) + RAY_EPS * V[2]
        los_queries += 1
        vis = _eye_surface_visibility(
            world,
            eye=(ox, oy, oz),
            target=(tx, ty, tz),
            exclude_entity_id=surf.get("exclude_entity_id"),
            config=physical_config,
            bodies=bodies,
            exclude_entity_ids=(observer_entity_id,) if observer_entity_id else (),
        )
        if not vis["clear"]:
            auth = str((vis.get("blocker") or {}).get("authority") or vis.get("authority") or "")
            key = REASON_OCCLUDED_ENTITY if "ENTITY" in auth else REASON_OCCLUDED_VW1
            reason_counts[key] = reason_counts.get(key, 0) + 1
            rejected += 1
            continue

        illum = surf.get("illumination") if isinstance(surf.get("illumination"), dict) else {}
        o1_status = str(illum.get("o1_status") or surf.get("o1_status") or "")
        reflected = illum.get("reflected_spectral_exitance_proxy")
        state = str(illum.get("state_class") or "")

        if o1_status and o1_status not in ("PROFILE_RESOLVED", "") and reflected is None:
            reason_counts[REASON_UNKNOWN_MATERIAL] = reason_counts.get(REASON_UNKNOWN_MATERIAL, 0) + 1
            unknown_kept += 1
            rejected += 1
            # Geometry visible but no fabricated bands
            continue
        if state == "SOURCE_DISABLED_ZERO" or (illum.get("source_enabled") is False):
            reason_counts[REASON_SOURCE_DISABLED] = reason_counts.get(REASON_SOURCE_DISABLED, 0) + 1
            rejected += 1
            continue
        if reflected is None:
            reason_counts[REASON_NO_REFLECTED] = reason_counts.get(REASON_NO_REFLECTED, 0) + 1
            rejected += 1
            continue
        Rlist = [float(reflected[b]) if b < len(reflected) else 0.0 for b in range(OPTICAL_BAND_COUNT)]
        if all(abs(v) <= TOLERANCE for v in Rlist):
            reason_counts[REASON_ZERO_REFLECTED] = reason_counts.get(REASON_ZERO_REFLECTED, 0) + 1
            rejected += 1
            continue

        att = _attenuation(dist, k_visual)
        area = max(0.0, float(surf.get("area_weight") or 0.0))
        # Angular FOV weight applied once here (phenotype angular part)
        scale = facing * area * att * ang
        contrib = [float(Rlist[b]) * scale for b in range(OPTICAL_BAND_COUNT)]
        for b in range(OPTICAL_BAND_COUNT):
            raw_bins[bin_i][b] += contrib[b]
        accepted += 1
        reason_counts[REASON_ACCEPTED] = reason_counts.get(REASON_ACCEPTED, 0) + 1
        if len(contributors) < max_trace:
            # Record already-computed geometry for researcher FPV (no LOS/light recompute).
            from mechanistic_mind.planet.topology import toroidal_delta as _td

            _dx = float(_td(eye[0], float(centre[0]), w))
            _dy = float(_td(eye[1], float(centre[1]), h))
            _dz = float(centre[2]) - float(eye[2])
            _horiz = float(math.hypot(_dx, _dy))
            elev_rad = float(math.atan2(_dz, max(_horiz, 1e-15)))
            contributors.append({
                "contribution_id": f"C{accepted:04d}_{surf.get('surface_id') or 's'}",
                "observation_tick": int(t),
                "receptor_tick": int(t),
                "surface_id": surf.get("surface_id"),
                "entity_id": surf.get("entity_id"),
                "entity_class": surf.get("entity_class"),
                "bin": int(bin_i),
                "angular_bin": int(bin_i),
                "azimuth_rad": float(rel),
                "azimuth_deg": float(math.degrees(rel)),
                "elevation_rad": elev_rad,
                "elevation_deg": float(math.degrees(elev_rad)),
                "distance_3d": float(dist),
                "facing": float(facing),
                "attenuation": float(att),
                "angular": float(ang),
                "angular_weight": float(ang),
                "area_weight": float(area),
                "represented_angular_area_weight": float(ang) * float(area),
                "contrib_bands": contrib,
                "accepted_raw_six_band": list(contrib),
                "visibility_status": "ACCEPTED",
                "o1_status": o1_status or "PROFILE_RESOLVED",
                "illum_state": state,
                "researcher_only": True,
            })

    # Phenotype once: gain → sat → threshold on band intensities; then clip once at cognition boundary
    pre_clip_bins = [[0.0] * OPTICAL_BAND_COUNT for _ in range(N_EXO_CHANNELS)]
    post_clip_intensity = [0.0] * N_EXO_CHANNELS
    post_clip_surface = [[0.0] * N_EXO_CHANNELS for _ in range(max(n_surf, 1))]
    clipped_flags = [False] * N_EXO_CHANNELS

    for i in range(N_EXO_CHANNELS):
        for b in range(OPTICAL_BAND_COUNT):
            pre = max(0.0, gain * raw_bins[i][b])
            sat = min(saturation, pre)
            pre_clip_bins[i][b] = sat
        intensity = sum(pre_clip_bins[i])
        if intensity < threshold:
            intensity = 0.0
            for b in range(OPTICAL_BAND_COUNT):
                pre_clip_bins[i][b] = 0.0
        # Clip once
        if intensity > 1.0:
            clipped_flags[i] = True
        post_clip_intensity[i] = _clip01(intensity)
        folded = _fold_bands_to_3(pre_clip_bins[i])
        for ck in range(n_surf):
            post_clip_surface[ck][i] = _clip01(folded[ck] if intensity > 0 else 0.0)

    fragments = {f"exo_{i}": float(post_clip_intensity[i]) for i in range(N_EXO_CHANNELS)}
    surface_fragments: dict[str, float] = {}
    if disc_mode == "LOW":
        for i in range(N_EXO_CHANNELS):
            surface_fragments[f"surface_c0_{i}"] = float(post_clip_surface[0][i])
    elif disc_mode == "RICH":
        for ck in range(N_SURFACE_OPTICAL_CHANNELS):
            for i in range(N_EXO_CHANNELS):
                surface_fragments[f"surface_c{ck}_{i}"] = float(post_clip_surface[ck][i])

    # Generations
    gens = {}
    try:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of
        st = state_of(world)
        gens["vw1_digest"] = str(st.digest()) if st is not None else None
    except Exception:
        pass
    try:
        from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
            query_source_state,
        )
        src = query_source_state(physical_config)
        gens["source_version"] = (src.get("source") or {}).get("source_version")
        gens["source_enabled"] = (src.get("source") or {}).get("enabled")
    except Exception:
        pass

    trace = {
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "label": "ORGANISM PHYSICAL OPTICAL RECEPTION",
        "labels": [
            "ORGANISM PHYSICAL OPTICAL RECEPTION",
            "ABSTRACT NON-SI BANDS",
            "NOT HUMAN RGB",
            "VW7/OBSERVER PIXELS NOT USED",
        ],
        "tick": t,
        "receptor_sample_tick": t,
        "organism_observation_tick": t,
        "decision_tick": t,
        "visual_causal_delay_ticks": VISUAL_CAUSAL_DELAY_TICKS,
        "eye_xyz": list(eye),
        "heading": float(heading),
        "fov_deg": fov,
        "max_range": max_range,
        "k_visual": k_visual,
        "attenuation_applied_count": 1,
        "phenotype_application_count": 1,
        "clipping_application_count": 1,
        "candidate_surfaces": len(candidates),
        "los_queries": los_queries,
        "accepted": accepted,
        "rejected": rejected,
        "unknown_material_count": unknown_kept,
        "reason_counts": reason_counts,
        "raw_bins_pre_phenotype": raw_bins,
        "pre_clip_bins": pre_clip_bins,
        "post_clip_intensity": post_clip_intensity,
        "clipped_flags": clipped_flags,
        "post_clip_surface": post_clip_surface,
        "contributors": contributors,
        "contributors_truncated": max(0, accepted - len(contributors)),
        "generations": gens,
        "cognition_schema": COGNITION_SCHEMA,
        "band_fold_policy": BAND_FOLD_POLICY,
        "phenotype": {
            "gain": float(gain),
            "saturation": float(saturation),
            "threshold": float(threshold),
            "disc_mode": disc_mode,
        },
        "n_exo_channels": int(N_EXO_CHANNELS),
        "n_surface_channels": int(n_surf),
        "fragments": dict(fragments),
        "surface_fragments": dict(surface_fragments),
        "legacy_illumination_used": False,
        "legacy_optical_response_used": False,
        "organism_saw_light": False,  # no conscious claim
        "physical_signal_reached_receptor": accepted > 0 and any(v > 0 for v in post_clip_intensity),
        "feeds_cognition": True,
        "researcher_only": True,
    }

    # Stash researcher trace on world (not cognition); bounded, not created by Observer poll if diagnostic
    if not diagnostic:
        try:
            hist = getattr(world, "_o4_reception_traces", None)
            if not isinstance(hist, list):
                hist = []
                setattr(world, "_o4_reception_traces", hist)
            hist.append({
                "tick": t,
                "accepted": accepted,
                "physical_signal_reached_receptor": trace["physical_signal_reached_receptor"],
                "fragments": dict(fragments),
            })
            if len(hist) > 64:
                del hist[:-64]
            setattr(world, "_o4_last_reception_trace", trace)
            by_body = getattr(world, "_o4_last_reception_by_body", None)
            if not isinstance(by_body, dict):
                by_body = {}
                setattr(world, "_o4_last_reception_by_body", by_body)
            by_body[id(body)] = trace
        except Exception:
            pass

    bx = float(getattr(body, "x", 0.0) or 0.0)
    by = float(getattr(body, "y", 0.0) or 0.0)
    cx, cy = int(math.floor(bx)) % w, int(math.floor(by)) % h

    out = {
        "tick": t,
        "body_xy": [bx, by],
        "body_cell": [cx, cy],
        "body_theta": float(getattr(body, "theta", 0.0) or 0.0),
        "head_relative_angle": float(getattr(body, "head_relative_angle", 0.0) or 0.0),
        "head_world_heading": float(heading),
        "sensor_forward_axis": float(heading),
        "fov_deg": fov,
        "vision_radius": int(radius),
        "radius": int(radius),
        "max_candidates": moore_max_candidates(radius),
        "illumination": None,  # legacy illumination not used
        "illumination_enabled": False,
        "perception_enabled": bool(getattr(nfe_cfg, "perception_enabled", True)),
        "vision_contributes": bool(getattr(nfe_cfg, "vision_contributes", True)),
        "n_candidates": len(candidates),
        "n_inside_fov": accepted + reason_counts.get(REASON_BACK_FACING, 0) + reason_counts.get(REASON_OCCLUDED_VW1, 0) + reason_counts.get(REASON_OCCLUDED_ENTITY, 0),
        "n_detectable": accepted,
        "aggregate_intensity": float(sum(post_clip_intensity)),
        "fragments": fragments,
        "surface_fragments": surface_fragments,
        "spatial_fragments": {},
        "visual_surface_discrimination": disc_mode,
        "spatial_vision": "LEGACY",
        "spatial_sectors": 5,
        "neighbors": [],  # physical surfaces are not Moore cell neighbors
        "eye_xyz": list(eye),
        "o4_physical_optical_reception": True,
        "o4_schema": SCHEMA,
        "o4_profile": PROFILE,
        "o4_authority": AUTHORITY,
        "o4_trace": trace if (diagnostic or True) else None,  # researcher sample always carries compact trace
        "optical_composition": (
            "O4: contribution[b]=reflected[b]*facing*area*attenuation(k_visual)*angular_fov; "
            "phenotype gain/sat/threshold once; clip once; no legacy illumination/optical_response"
        ),
        "ACTIVE_SENSOR_ORIENTATION": {
            "sensor_forward_axis": float(heading),
            "fov_deg": fov,
        },
        "resource_object_vision_enabled": False,
        "n_resource_object_optical_cells": 0,
        "n_body_optical_cells": 0,
        "n_occluded": int(reason_counts.get(REASON_OCCLUDED_VW1, 0) + reason_counts.get(REASON_OCCLUDED_ENTITY, 0)),
    }
    # Compact o4_trace on non-diagnostic to avoid huge cognition-adjacent payloads in SOVV
    if not diagnostic:
        out["o4_trace"] = {
            "schema": SCHEMA,
            "accepted": accepted,
            "rejected": rejected,
            "reason_counts": reason_counts,
            "physical_signal_reached_receptor": trace["physical_signal_reached_receptor"],
            "visual_causal_delay_ticks": VISUAL_CAUSAL_DELAY_TICKS,
            "k_visual": k_visual,
            "candidate_surfaces": len(candidates),
            "los_queries": los_queries,
            "cognition_schema": COGNITION_SCHEMA,
            "labels": trace["labels"],
            "contributors_count": len(contributors),
            "generations": gens,
        }
        setattr(world, "_o4_last_reception_trace", trace)
        by_body = getattr(world, "_o4_last_reception_by_body", None)
        if not isinstance(by_body, dict):
            by_body = {}
            setattr(world, "_o4_last_reception_by_body", by_body)
        by_body[id(body)] = trace
    return out


def researcher_summary(world: Any, config: Any) -> dict[str, Any]:
    tr = getattr(world, "_o4_last_reception_trace", None)
    if not isinstance(tr, dict):
        return {
            "enabled": organism_physical_optical_reception_is_active(config),
            "schema": SCHEMA,
            "label": "ORGANISM PHYSICAL OPTICAL RECEPTION",
            "has_trace": False,
        }
    return {
        "enabled": True,
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "label": "ORGANISM PHYSICAL OPTICAL RECEPTION",
        "labels": tr.get("labels"),
        "accepted": tr.get("accepted"),
        "rejected": tr.get("rejected"),
        "reason_counts": tr.get("reason_counts"),
        "physical_signal_reached_receptor": tr.get("physical_signal_reached_receptor"),
        "visual_causal_delay_ticks": VISUAL_CAUSAL_DELAY_TICKS,
        "k_visual": tr.get("k_visual"),
        "cognition_schema": COGNITION_SCHEMA,
        "organism_saw_light": False,
        "feeds_cognition": True,
        "legacy_illumination_used": False,
    }


def build_o4_analyzer_reconstruction(evidence: dict[str, Any] | None = None, *, on_progress: Any = None) -> dict[str, Any]:
    ev = evidence if isinstance(evidence, dict) else {}
    if on_progress:
        on_progress("INDEX_PHYSICAL_RECEIPTS", 0, 1)
        on_progress("AGGREGATING", 1, 1)
    reached = bool(ev.get("physical_signal_reached_receptor"))
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "section": "ORGANISM PHYSICAL OPTICAL RECEPTION (O4)",
        "causal_chain": [
            "physical_source",
            "illuminated_surface",
            "eye_visibility",
            "receptor_contribution",
            "phenotype",
            "cognition_boundary",
        ],
        "physical_signal_reached_receptor": reached,
        "conscious_seeing_claimed": False,
        "organism_saw_light": False,
        "accepted": ev.get("accepted"),
        "reason_counts": ev.get("reason_counts"),
        "researcher_only": True,
        "label": "ORGANISM PHYSICAL OPTICAL RECEPTION · ABSTRACT NON-SI · NOT HUMAN RGB",
    }


def format_o4_section(summary: dict[str, Any] | None) -> str:
    s = summary or {}
    return "\n".join([
        "ORGANISM PHYSICAL OPTICAL RECEPTION (O4)",
        f"  physical_signal_reached_receptor: {s.get('physical_signal_reached_receptor')}",
        f"  accepted: {s.get('accepted')}",
        f"  conscious_seeing_claimed: False",
        "  label: ORGANISM PHYSICAL OPTICAL RECEPTION · ABSTRACT NON-SI · NOT HUMAN RGB",
    ])


PRIVACY_DENYLIST_TOKENS = (
    CAPABILITY,
    SCHEMA,
    PROFILE,
    AUTHORITY,
    "organism_physical_optical_reception",
    "o4_trace",
    "reflected_spectral_exitance_proxy",
    "contrib_bands",
    "area_weight",
    "pose_digest",
    "k_visual",
    "contributors",
)
