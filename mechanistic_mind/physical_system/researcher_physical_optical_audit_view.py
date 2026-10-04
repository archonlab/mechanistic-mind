"""Acanthostega O6 · Researcher physical optical audit / exposed-surface view V1.

Schema: RESEARCHER_PHYSICAL_OPTICAL_AUDIT_VIEW_V1
Capability: researcher_physical_optical_audit_view
Profile: EXPOSED_SURFACE_AND_DIRECT_LIGHT_DISPLAY_O6_V1
Authority: RESEARCHER_TRANSFORM_OVER_O2_O3_O3A_O4_O5_READ_ONLY

Passive scientific visualization over O2/O3/O3A/O4/O5. Not a physical mechanism.
Does not create geometry, lighting, perception, or physics.
Display RGB / camera / UI mode never enter simulation or cognition.
"""
from __future__ import annotations

import json
import time
from typing import Any

SCHEMA = "RESEARCHER_PHYSICAL_OPTICAL_AUDIT_VIEW_V1"
CAPABILITY = "researcher_physical_optical_audit_view"
PROFILE = "EXPOSED_SURFACE_AND_DIRECT_LIGHT_DISPLAY_O6_V1"
AUTHORITY = "RESEARCHER_TRANSFORM_OVER_O2_O3_O3A_O4_O5_READ_ONLY"
MECHANISM_ID = CAPABILITY  # display consumer id only

STATUS_READY = "READY"
STATUS_NO_O2 = "UNAVAILABLE_NO_O2"
STATUS_NO_O3 = "UNAVAILABLE_NO_O3"
STATUS_PARTIAL_O3A = "PARTIAL_NO_O3A"
STATUS_PARTIAL_O4 = "PARTIAL_NO_O4_TRACE"
STATUS_PARTIAL_O5 = "PARTIAL_NO_O5_TIMING"
STATUS_LEGACY = "LEGACY_EVIDENCE"
STATUS_INCOMPATIBLE = "INCOMPATIBLE_PROFILE"

DISPLAY_MODES = ("CAUSAL_STATE", "BAND_AUDIT", "COMPOSITE_FALSE_COLOR", "MATERIAL_REFLECTANCE")

LABELS = [
    "RESEARCHER TRANSFORM",
    "ABSTRACT NON-SI OPTICAL BANDS",
    "NOT HUMAN RGB",
    "NOT ORGANISM VISION",
]

# Fixed documented 6→display-RGB transform (researcher-only, not wavelength mapping).
# band0→R weight, band1→R, band2→G, band3→G, band4→B, band5→B (equal pairs).
COMPOSITE_TRANSFORM = {
    "id": "O6_FIXED_6_TO_DISPLAY_RGB_V1",
    "formula": "R=(b0+b1)/2, G=(b2+b3)/2, B=(b4+b5)/2, clipped [0,1]",
    "physical_authority": False,
    "human_color": False,
    "wavelength_mapping": False,
    "organism_perception": False,
}

CAUSAL_DISPLAY_COLORS = {
    "DIRECT_ILLUMINATED": "#f2d27a",
    "BACK_FACING_ZERO": "#4a5560",
    "OCCLUDED_ZERO": "#2a3544",
    "SOURCE_DISABLED_ZERO": "#1a2030",
    "UNKNOWN_MATERIAL_RESPONSE": "#c45c8a",
    "NOT_EVALUATED": "#666666",
    "UNAVAILABLE": "#333333",
}

WORLD_CACHE_ATTR = "_o6_display_cache"
WORLD_PERF_ATTR = "_o6_perf_counters"
# P3 split caches (researcher delivery only; never enter snapshots as physics).
STATIC_TERRAIN_CACHE_ATTR = "_o6_p3_static_terrain_cache"
OPTICAL_COLUMNS_CACHE_ATTR = "_o6_p3_optical_columns_cache"


def researcher_physical_optical_audit_view_catalog_item(*, available: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": False,  # not a physics mechanism
        "available": bool(available),
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "physical_mechanism": False,
        "researcher_only": True,
        "summary": "Researcher exposed-surface + direct-light audit display (O6).",
    }


def _facet_corners(facet: dict[str, Any]) -> list[list[float]]:
    """Derive display triangle/quad corners from O2 facet descriptors (render artifact only)."""
    face = str(facet.get("face_class") or "")
    cx = int(facet.get("cell_x", 0))
    cy = int(facet.get("cell_y", 0))
    z_lo = float(facet.get("span_lower", 0.0))
    z_hi = float(facet.get("span_upper", 0.0))
    if face == "FACE_TOP":
        z = float(facet.get("boundary_plane_coordinate", z_hi))
        return [[cx, cy, z], [cx + 1, cy, z], [cx + 1, cy + 1, z], [cx, cy + 1, z]]
    if face == "FACE_BOTTOM":
        z = float(facet.get("boundary_plane_coordinate", z_lo))
        return [[cx, cy, z], [cx, cy + 1, z], [cx + 1, cy + 1, z], [cx + 1, cy, z]]
    if face == "FACE_EAST":
        x = float(facet.get("boundary_plane_coordinate", cx + 1))
        return [[x, cy, z_lo], [x, cy + 1, z_lo], [x, cy + 1, z_hi], [x, cy, z_hi]]
    if face == "FACE_WEST":
        x = float(facet.get("boundary_plane_coordinate", cx))
        return [[x, cy, z_lo], [x, cy, z_hi], [x, cy + 1, z_hi], [x, cy + 1, z_lo]]
    if face == "FACE_SOUTH":
        y = float(facet.get("boundary_plane_coordinate", cy + 1))
        return [[cx, y, z_lo], [cx + 1, y, z_lo], [cx + 1, y, z_hi], [cx, y, z_hi]]
    if face == "FACE_NORTH":
        y = float(facet.get("boundary_plane_coordinate", cy))
        return [[cx, y, z_lo], [cx, y, z_hi], [cx + 1, y, z_hi], [cx + 1, y, z_lo]]
    c = facet.get("centre") or [0.0, 0.0, 0.0]
    return [[float(c[0]), float(c[1]), float(c[2])]]


def composite_false_color(bands: list[float] | None) -> list[float]:
    b = [float(x) for x in (bands or [0.0] * 6)]
    while len(b) < 6:
        b.append(0.0)
    r = max(0.0, min(1.0, 0.5 * (b[0] + b[1])))
    g = max(0.0, min(1.0, 0.5 * (b[2] + b[3])))
    bl = max(0.0, min(1.0, 0.5 * (b[4] + b[5])))
    return [r, g, bl]


def _illum_index(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        fid = str(r.get("facet_id") or r.get("sample_id") or "")
        if fid:
            out[fid] = r
    return out


def _pack_static_columnar(o2_facets: list[dict[str, Any]]) -> dict[str, Any]:
    """Terrain geometry + material refs only (VW1/O2 generation stable)."""
    col: dict[str, Any] = {
        "encoding": "O6_COLUMNAR_FACETS_STATIC_V1",
        "n": 0,
        "facet_id": [],
        "face_class": [],
        "cell_x": [],
        "cell_y": [],
        "interval_id": [],
        "centre": [],
        "normal": [],
        "area": [],
        "span_lower": [],
        "span_upper": [],
        "boundary_plane_coordinate": [],
        "o1_status": [],
        "reflectance": [],
    }
    for f in o2_facets:
        fid = str(f.get("facet_id"))
        refl = list(f.get("spectral_reflectance") or [0.0] * 6)
        while len(refl) < 6:
            refl.append(0.0)
        c = f.get("centre") or [0.0, 0.0, 0.0]
        nrm = f.get("outward_unit_normal") or [0.0, 0.0, 1.0]
        col["facet_id"].append(fid)
        col["face_class"].append(f.get("face_class"))
        col["cell_x"].append(int(f.get("cell_x", 0)))
        col["cell_y"].append(int(f.get("cell_y", 0)))
        col["interval_id"].append(f.get("interval_id"))
        col["centre"].extend([float(c[0]), float(c[1]), float(c[2])])
        col["normal"].extend([float(nrm[0]), float(nrm[1]), float(nrm[2])])
        col["area"].append(float(f.get("area") or 0.0))
        col["span_lower"].append(float(f.get("span_lower") or 0.0))
        col["span_upper"].append(float(f.get("span_upper") or 0.0))
        col["boundary_plane_coordinate"].append(float(f.get("boundary_plane_coordinate") or 0.0))
        col["o1_status"].append(f.get("o1_status"))
        col["reflectance"].extend(float(x) for x in refl[:6])
    col["n"] = len(col["facet_id"])
    return col


def _pack_optical_columnar(o2_facets: list[dict[str, Any]], illum_by_id: dict[str, dict[str, Any]], *, has_o3: bool) -> tuple[dict[str, Any], dict[str, int]]:
    """O3 band/causal columns aligned to O2 facet order."""
    col: dict[str, Any] = {
        "encoding": "O6_COLUMNAR_FACETS_OPTICAL_V1",
        "n": 0,
        "state_class": [],
        "incident": [],
        "reflected": [],
    }
    state_counts: dict[str, int] = {}
    for f in o2_facets:
        fid = str(f.get("facet_id"))
        ill = illum_by_id.get(fid) or {}
        bands_inc = list(ill.get("incident_spectrum") or [0.0] * 6)
        bands_ref = list(ill.get("reflected_spectral_exitance_proxy") or [0.0] * 6)
        while len(bands_inc) < 6:
            bands_inc.append(0.0)
        while len(bands_ref) < 6:
            bands_ref.append(0.0)
        state = str(ill.get("state_class") or ("NOT_EVALUATED" if has_o3 else "UNAVAILABLE"))
        state_counts[state] = state_counts.get(state, 0) + 1
        col["state_class"].append(state)
        col["incident"].extend(float(x) for x in bands_inc[:6])
        col["reflected"].extend(float(x) for x in bands_ref[:6])
    col["n"] = len(col["state_class"])
    return col, state_counts


def _merge_static_optical_columnar(static_col: dict[str, Any], optical_col: dict[str, Any]) -> dict[str, Any]:
    from mechanistic_mind.ui.psy_observer_web.observer_surface_incremental_payload import (
        merge_facets_columnar,
    )
    return merge_facets_columnar(static_col, optical_col)


def build_surface_display_payload(
    world: Any,
    config: Any,
    *,
    runtime: Any | None = None,
    selected_agent_id: str | None = None,
) -> dict[str, Any]:
    """Build researcher-only SURFACE/LIGHT display payload. Read-only over O2–O5.

    P3: static terrain geometry is cached by O2 generation identity; optical columns
    by O3 result checksum; entity samples always refreshed from O3A (pose-dynamic).
    """
    t0 = time.perf_counter()
    from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
        ensure_exposed_surface_cache,
        exposed_surface_optical_interaction_authority_is_active,
    )
    from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
        abstract_spectral_light_source_and_direct_transport_is_active,
        ensure_direct_light_cache,
    )
    from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
        ensure_entity_surface_cache,
        object_body_held_optical_surfaces_is_active,
    )
    from mechanistic_mind.physical_system.physical_optical_material_profile import REGISTRY_VERSION
    from mechanistic_mind.ui.psy_observer_web.observer_surface_incremental_payload import (
        KIND_FULL,
        build_incremental_envelope,
        build_surface_dynamic_block,
        build_surface_static_block,
        make_static_payload_id,
        p3_perf_bump,
    )

    labels = list(LABELS)
    if not exposed_surface_optical_interaction_authority_is_active(config):
        return {
            "schema": SCHEMA,
            "capability": CAPABILITY,
            "profile": PROFILE,
            "authority": AUTHORITY,
            "status": STATUS_NO_O2,
            "available": False,
            "labels": labels,
            "facets": [],
            "entity_samples": [],
            "researcher_only": True,
            "feeds_cognition": False,
            "physical_mechanism": False,
        }

    o2 = ensure_exposed_surface_cache(world, config)
    if o2 is None:
        return {
            "schema": SCHEMA,
            "capability": CAPABILITY,
            "profile": PROFILE,
            "authority": AUTHORITY,
            "status": STATUS_NO_O2,
            "available": False,
            "labels": labels,
            "facets": [],
            "entity_samples": [],
            "researcher_only": True,
            "feeds_cognition": False,
        }

    has_o3 = abstract_spectral_light_source_and_direct_transport_is_active(config)
    o3 = ensure_direct_light_cache(world, config) if has_o3 else None
    status = STATUS_READY if has_o3 and o3 is not None else STATUS_NO_O3

    runtime_generation = None
    if runtime is not None:
        try:
            runtime_generation = int(getattr(runtime, "_observer_runtime_generation", 0) or 0) or None
        except Exception:
            runtime_generation = None

    o1_reg = str(REGISTRY_VERSION)
    static_id = make_static_payload_id(
        o2_key_digest=str(o2.key_digest),
        o2_facet_checksum=str(o2.facet_checksum),
        o1_registry_version=o1_reg,
        runtime_generation=runtime_generation,
    )

    # ---- Static terrain geometry (survives entity motion) ----
    t_static0 = time.perf_counter()
    static_hit = False
    prev_static = getattr(world, STATIC_TERRAIN_CACHE_ATTR, None)
    if (
        isinstance(prev_static, dict)
        and prev_static.get("static_payload_id") == static_id
        and isinstance(prev_static.get("facets_columnar_static"), dict)
    ):
        static_col = prev_static["facets_columnar_static"]
        static_hit = True
        p3_perf_bump(world, static_hits=1)
    else:
        static_col = _pack_static_columnar(list(o2.facets))
        p3_perf_bump(world, static_misses=1, static_build_ms=(time.perf_counter() - t_static0) * 1000.0)
        setattr(
            world,
            STATIC_TERRAIN_CACHE_ATTR,
            {
                "static_payload_id": static_id,
                "facets_columnar_static": static_col,
                "o2_key_digest": o2.key_digest,
                "o2_facet_checksum": o2.facet_checksum,
                "o1_registry_version": o1_reg,
            },
        )
    static_ms = (time.perf_counter() - t_static0) * 1000.0

    # ---- Optical columns (exact O3; reuse when result checksum unchanged) ----
    t_opt0 = time.perf_counter()
    o3_ck = str(getattr(o3, "result_checksum", None) or "none")
    optical_hit = False
    prev_opt = getattr(world, OPTICAL_COLUMNS_CACHE_ATTR, None)
    if (
        isinstance(prev_opt, dict)
        and prev_opt.get("static_payload_id") == static_id
        and prev_opt.get("o3_result_checksum") == o3_ck
        and isinstance(prev_opt.get("facets_columnar_optical"), dict)
    ):
        optical_col = prev_opt["facets_columnar_optical"]
        state_counts = dict(prev_opt.get("state_counts") or {})
        optical_hit = True
        p3_perf_bump(world, optical_hits=1)
    else:
        illum_by_id = _illum_index(list(o3.results) if o3 is not None else [])
        optical_col, state_counts = _pack_optical_columnar(list(o2.facets), illum_by_id, has_o3=has_o3)
        p3_perf_bump(world, optical_misses=1, optical_build_ms=(time.perf_counter() - t_opt0) * 1000.0)
        setattr(
            world,
            OPTICAL_COLUMNS_CACHE_ATTR,
            {
                "static_payload_id": static_id,
                "o3_result_checksum": o3_ck,
                "facets_columnar_optical": optical_col,
                "state_counts": state_counts,
            },
        )
    optical_ms = (time.perf_counter() - t_opt0) * 1000.0

    facets_out = _merge_static_optical_columnar(static_col, optical_col)
    geom_ms = static_ms + optical_ms

    # ---- Entity samples ALWAYS refreshed (pose-dynamic; never stale from terrain cache) ----
    t_ent0 = time.perf_counter()
    entity_samples: list[dict[str, Any]] = []
    o3a_key = None
    prev_entity_ids: set[str] = set()
    legacy_combined = getattr(world, WORLD_CACHE_ATTR, None)
    if isinstance(legacy_combined, dict):
        prev_payload = legacy_combined.get("payload") or {}
        for e in prev_payload.get("entity_samples") or []:
            eid = str(e.get("entity_id") or e.get("sample_id") or "")
            if eid:
                prev_entity_ids.add(eid)

    if object_body_held_optical_surfaces_is_active(config):
        bodies = None
        if runtime is not None:
            try:
                from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime
                bodies = body_refs_for_runtime(runtime)
            except Exception:
                bodies = None
        o3a = ensure_entity_surface_cache(world, config, bodies=bodies)
        if o3a is not None:
            o3a_key = str(getattr(o3a, "key_digest", None) or "")
            ill_e = _illum_index(list(o3a.illuminations))
            for s in o3a.samples:
                sid = str(s.get("sample_id"))
                ill = ill_e.get(sid) or ill_e.get(str(s.get("facet_id") or "")) or {}
                state = str(ill.get("state_class") or "NOT_EVALUATED")
                bands_ref = ill.get("reflected_spectral_exitance_proxy")
                bands_inc = ill.get("incident_spectrum")
                entity_samples.append({
                    "kind": "O3A_ANALYTIC_SAMPLE",
                    "sample_id": sid,
                    "facet_id": s.get("facet_id"),
                    "entity_id": s.get("entity_id"),
                    "entity_class": s.get("entity_class"),
                    "held": bool(s.get("held")),
                    "centre": list(s.get("centre") or []),
                    "outward_unit_normal": list(s.get("outward_unit_normal") or []),
                    "geometry_profile": s.get("geometry_profile"),
                    "geometry_radius": s.get("geometry_radius"),
                    "entity_centre": list(s.get("entity_centre") or s.get("centre") or []),
                    "area_weight": s.get("area_weight"),
                    "analytic_physical_geometry": True,
                    "glyph_size_is_not_physical_size": True,
                    "optical_radius_not_used": True,
                    "state_class": state,
                    "incident_spectrum": list(bands_inc) if isinstance(bands_inc, (list, tuple)) else None,
                    "reflected_spectral_exitance_proxy": list(bands_ref) if isinstance(bands_ref, (list, tuple)) else None,
                    "spectral_reflectance": list(s.get("spectral_reflectance") or []) or None,
                    "display_artifact_only": True,
                })
        else:
            status = STATUS_PARTIAL_O3A if status == STATUS_READY else status
    else:
        if status == STATUS_READY:
            status = STATUS_PARTIAL_O3A
    p3_perf_bump(world, entity_rebuilds=1, entity_build_ms=(time.perf_counter() - t_ent0) * 1000.0)

    cur_entity_ids = {str(e.get("entity_id") or e.get("sample_id") or "") for e in entity_samples}
    cur_entity_ids.discard("")
    tombstones = [
        {"entity_id": eid, "tombstone": True, "reason": "REMOVED"}
        for eid in sorted(prev_entity_ids - cur_entity_ids)
    ]

    # Source inspection
    src_info: dict[str, Any] = {}
    vw1_digest = None
    if has_o3:
        cfg = getattr(config, "abstract_spectral_light_source_and_direct_transport", None)
        src = getattr(cfg, "source", None) if cfg is not None else None
        if src is not None:
            sd = src.to_dict() if hasattr(src, "to_dict") else {}
            src_info = {
                "source_id": sd.get("source_id") or getattr(src, "source_id", "abstract_directional_source_0"),
                "direction": list(sd.get("direction_toward_source") or getattr(src, "direction_toward_source", ()) or []),
                "band_values": list(sd.get("source_spectrum") or []),
                "enabled": bool(sd.get("enabled", True)),
                "source_version": sd.get("source_version"),
                "source_digest": src.digest() if hasattr(src, "digest") else None,
                "profile_version": PROFILE,
                "o3_key_digest": getattr(o3, "key_digest", None),
                "o3_result_checksum": getattr(o3, "result_checksum", None),
                "o2_facet_checksum": o2.facet_checksum,
                "physical_generation": {
                    "o2_key_digest": o2.key_digest,
                    "o3_key_digest": getattr(o3, "key_digest", None),
                },
            }
        vw1_digest = (getattr(o3, "key_parts", None) or {}).get("vw1_digest") if o3 is not None else None

    org = _organism_comparison(world, config, selected_agent_id)
    o5 = _o5_timing(world, config)
    if org.get("status") == STATUS_PARTIAL_O4 and status == STATUS_READY:
        status = STATUS_PARTIAL_O4

    tile_w, tile_h = 32, 32
    try:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of
        st = state_of(world)
        if st is not None:
            tile_w, tile_h = int(st.width), int(st.height)
            if vw1_digest is None:
                vw1_digest = str(st.digest())
    except Exception:
        pass

    tick = int(getattr(world, "tick", 0) or 0)
    dynamic_revision = hashlib_sha16(
        static_id, o3_ck, o3a_key or "", tick, len(entity_samples), len(tombstones)
    )

    surface_static = build_surface_static_block(
        static_payload_id=static_id,
        static_columnar=static_col,
        o2_key_digest=str(o2.key_digest),
        o2_facet_checksum=str(o2.facet_checksum),
        o1_registry_version=o1_reg,
        vw1_digest=vw1_digest,
        world_tile={"width": tile_w, "height": tile_h},
        counts_by_face=dict(o2.counts_by_face),
        runtime_generation=runtime_generation,
    )
    surface_dynamic = build_surface_dynamic_block(
        static_payload_id=static_id,
        dynamic_revision=dynamic_revision,
        tick=tick,
        optical_columnar=optical_col,
        entity_samples=entity_samples,
        entity_tombstones=tombstones,
        state_counts=state_counts,
        source=src_info,
        organism_comparison=org,
        o5_timing=o5,
        o3_result_checksum=getattr(o3, "result_checksum", None),
        o3a_key_digest=o3a_key,
    )
    incremental = build_incremental_envelope(
        kind=KIND_FULL,
        surface_static=surface_static,
        surface_dynamic=surface_dynamic,
        telemetry={
            "static_cache": "hit" if static_hit else "miss",
            "optical_cache": "hit" if optical_hit else "miss",
            "static_build_ms": round(static_ms, 3),
            "optical_build_ms": round(optical_ms, 3),
            "entity_build_ms": round((time.perf_counter() - t_ent0) * 1000.0, 3),
        },
    )

    build_ms = (time.perf_counter() - t0) * 1000.0
    payload = {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "status": status,
        "available": status not in (STATUS_NO_O2,),
        "labels": labels,
        "display_modes": list(DISPLAY_MODES),
        "composite_transform": COMPOSITE_TRANSFORM,
        "causal_display_colors": dict(CAUSAL_DISPLAY_COLORS),
        "world_tile": {"width": tile_w, "height": tile_h},
        "o2_facet_checksum": o2.facet_checksum,
        "o2_key_digest": o2.key_digest,
        "o3_result_checksum": getattr(o3, "result_checksum", None),
        "facet_count": int(facets_out.get("n", 0)) if isinstance(facets_out, dict) else len(facets_out),
        "entity_sample_count": len(entity_samples),
        "state_counts": state_counts,
        "counts_by_face": dict(o2.counts_by_face),
        "facets_columnar": facets_out,
        "facets": [],  # use facets_columnar; empty list preserves legacy key
        "entity_samples": entity_samples,
        "source": src_info,
        "organism_comparison": org,
        "o5_timing": o5,
        "internal_vw1_faces_rendered": False,
        "surface_uses_o2_exposed_facets": True,
        "surface_uses_o3a_entity_geometry": bool(entity_samples),
        "vw7_pixels_used_as_authority": False,
        "display_rgb_is_physical_authority": False,
        "hidden_display_ambient_alters_physical_light": False,
        "researcher_camera_used_as_organism_eye": False,
        "researcher_only": True,
        "feeds_cognition": False,
        "physical_mechanism": False,
        "static_payload_id": static_id,
        "dynamic_revision": dynamic_revision,
        "observer_surface_incremental": incremental,
        "performance": _perf_update(
            world,
            cache_hit=bool(static_hit and optical_hit),
            build_ms=build_ms,
            geom_ms=geom_ms,
            facet_n=int(facets_out.get("n", 0)) if isinstance(facets_out, dict) else len(facets_out),
            entity_n=len(entity_samples),
        ),
    }
    # Combined cache retains last payload for tombstone diffs; entities always refreshed above.
    cache_key = {
        "o2": str(o2.facet_checksum),
        "o3": o3_ck,
        "o2_key": str(o2.key_digest),
        "o3_key": str(getattr(o3, "key_digest", None) or "none"),
        "static_payload_id": static_id,
    }
    setattr(world, WORLD_CACHE_ATTR, {"cache_key": cache_key, "payload": payload})
    return payload


def hashlib_sha16(*parts: Any) -> str:
    import hashlib as _hl
    raw = "|".join(str(p) for p in parts)
    return _hl.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _merge_status(base: str, payload: dict[str, Any]) -> str:
    org = payload.get("organism_comparison") or {}
    if base == STATUS_READY and org.get("status") == STATUS_PARTIAL_O4:
        return STATUS_PARTIAL_O4
    return base


def _organism_comparison(world: Any, config: Any, selected_agent_id: str | None) -> dict[str, Any]:
    tr = getattr(world, "_o4_last_reception_trace", None)
    if not isinstance(tr, dict):
        return {
            "status": STATUS_PARTIAL_O4,
            "available": False,
            "uses_exact_o4_trace": False,
            "message": "UNAVAILABLE",
            "selected_agent_id": selected_agent_id,
            "chain": [
                "illuminated physical surface",
                "eye visibility",
                "raw receptor bands",
                "phenotype/fold",
                "cognition-accessible values",
            ],
            "researcher_camera_is_organism_eye": False,
            "conscious_recognition_claimed": False,
        }
    return {
        "status": "AVAILABLE",
        "available": True,
        "uses_exact_o4_trace": True,
        "selected_agent_id": selected_agent_id,
        "schema": tr.get("schema"),
        "receptor_sample_tick": tr.get("receptor_sample_tick"),
        "organism_observation_tick": tr.get("organism_observation_tick"),
        "visual_causal_delay_ticks": tr.get("visual_causal_delay_ticks"),
        "physical_signal_reached_receptor": tr.get("physical_signal_reached_receptor"),
        "accepted": tr.get("accepted"),
        "rejected": tr.get("rejected"),
        "post_clip_intensity": tr.get("post_clip_intensity"),
        "k_visual": tr.get("k_visual"),
        "chain": [
            "illuminated physical surface",
            "eye visibility",
            "raw receptor bands",
            "phenotype/fold",
            "cognition-accessible values",
        ],
        "current_world_substituted_for_historical_receptor": False,
        "researcher_camera_is_organism_eye": False,
        "conscious_recognition_claimed": False,
        "recomputed_from_camera": False,
    }


def _o5_timing(world: Any, config: Any) -> dict[str, Any]:
    try:
        from mechanistic_mind.physical_system.sensory_modality_temporal_alignment import (
            researcher_summary,
            sensory_modality_temporal_alignment_is_active,
        )
        if not sensory_modality_temporal_alignment_is_active(config):
            return {"status": STATUS_PARTIAL_O5, "available": False}
        return {"status": "AVAILABLE", "available": True, **researcher_summary(world, config)}
    except Exception:
        return {"status": STATUS_PARTIAL_O5, "available": False}


def _perf_update(
    world: Any,
    *,
    cache_hit: bool,
    build_ms: float,
    facet_n: int,
    entity_n: int,
    geom_ms: float = 0.0,
) -> dict[str, Any]:
    counters = getattr(world, WORLD_PERF_ATTR, None)
    if not isinstance(counters, dict):
        counters = {"cache_hits": 0, "cache_misses": 0, "builds": 0}
        setattr(world, WORLD_PERF_ATTR, counters)
    if cache_hit:
        counters["cache_hits"] = int(counters.get("cache_hits", 0)) + 1
    else:
        counters["cache_misses"] = int(counters.get("cache_misses", 0)) + 1
        counters["builds"] = int(counters.get("builds", 0)) + 1
    return {
        "facet_count": facet_n,
        "entity_sample_count": entity_n,
        "geometry_build_ms": round(geom_ms, 3),
        "payload_build_ms": round(build_ms, 3),
        "buffer_upload_ms": None,  # frontend fills
        "render_ms": None,  # frontend fills
        "cache_hits": counters["cache_hits"],
        "cache_misses": counters["cache_misses"],
        "cache_hit": cache_hit,
        "primitive_count_surface": facet_n + entity_n,
    }


def invalidate_o6_display_cache(world: Any) -> None:
    """Restore / generation change: clear derived render caches only."""
    if world is None:
        return
    if hasattr(world, WORLD_CACHE_ATTR):
        setattr(world, WORLD_CACHE_ATTR, None)
    if hasattr(world, STATIC_TERRAIN_CACHE_ATTR):
        setattr(world, STATIC_TERRAIN_CACHE_ATTR, None)
    if hasattr(world, OPTICAL_COLUMNS_CACHE_ATTR):
        setattr(world, OPTICAL_COLUMNS_CACHE_ATTR, None)
    try:
        from mechanistic_mind.ui.psy_observer_web.observer_surface_incremental_payload import (
            invalidate_p3_surface_caches,
        )
        invalidate_p3_surface_caches(world)
    except Exception:
        pass


def researcher_summary(
    world: Any,
    config: Any,
    *,
    runtime: Any | None = None,
    held_static_payload_id: str | None = None,
    prefer_incremental: bool = True,
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.beta4_performance_benchmark import (
        count as _b4p_count,
        is_enabled as _b4p_on,
        span as _b4p_span,
    )
    from mechanistic_mind.ui.psy_observer_web.observer_surface_incremental_payload import (
        KIND_DYNAMIC,
        KIND_FULL,
        KIND_RESET,
        build_incremental_envelope,
        build_surface_reset_block,
        p3_perf_bump,
    )

    static_warm = getattr(world, STATIC_TERRAIN_CACHE_ATTR, None) is not None
    cache_state = "warm" if static_warm else "cold"
    if _b4p_on():
        with _b4p_span("surface_o6_payload_build", parent="frame_payload_build", cache=cache_state):
            payload = build_surface_display_payload(world, config, runtime=runtime)
        _b4p_count("o2_facets", int(payload.get("facet_count") or 0))
        _b4p_count("surface_primitives", int((payload.get("performance") or {}).get("primitive_count_surface") or 0))
        if static_warm:
            _b4p_count("surface_static_cache_hit")
        else:
            _b4p_count("surface_static_cache_miss")
    else:
        payload = build_surface_display_payload(world, config, runtime=runtime)

    incremental = payload.get("observer_surface_incremental")
    static_id = str(payload.get("static_payload_id") or "")
    held = str(held_static_payload_id or "") if held_static_payload_id else ""

    display_out = payload
    wire_kind = KIND_FULL
    if not prefer_incremental:
        wire_kind = KIND_FULL
        display_out = payload
    elif prefer_incremental and held and static_id and held == static_id and isinstance(incremental, dict):
        # DYNAMIC wire: omit static geometry bytes; client merges with held base.
        dyn = incremental.get("surface_dynamic")
        wire_kind = KIND_DYNAMIC
        incremental = build_incremental_envelope(
            kind=KIND_DYNAMIC,
            surface_static=None,
            surface_dynamic=dyn,
            telemetry={
                **dict((incremental or {}).get("telemetry") or {}),
                "wire_kind": KIND_DYNAMIC,
                "omitted_static_geometry": True,
            },
        )
        # Slim display for wire: keep identity + dynamic fields, drop heavy static columns.
        slim_col = {
            "encoding": "O6_COLUMNAR_FACETS_V1",
            "n": int((payload.get("facets_columnar") or {}).get("n") or 0),
            "static_omitted": True,
            "static_payload_id": static_id,
        }
        # Keep optical columns in display for legacy clients that ignore incremental.
        for k in ("state_class", "incident", "reflected"):
            if k in (payload.get("facets_columnar") or {}):
                slim_col[k] = payload["facets_columnar"][k]
        display_out = {
            **payload,
            "facets_columnar": slim_col,
            "facets_columnar_static_omitted": True,
            "observer_surface_incremental": incremental,
        }
        p3_perf_bump(world, dynamic_wire=1)
    elif prefer_incremental and held and static_id and held != static_id:
        wire_kind = KIND_RESET
        reset = build_surface_reset_block(
            reason="HELD_STATIC_MISMATCH",
            static_payload_id=static_id,
            detail=f"held={held} current={static_id}",
        )
        incremental = build_incremental_envelope(
            kind=KIND_RESET,
            surface_static=(incremental or {}).get("surface_static") if isinstance(incremental, dict) else None,
            surface_dynamic=(incremental or {}).get("surface_dynamic") if isinstance(incremental, dict) else None,
            surface_reset=reset,
            telemetry={"wire_kind": KIND_RESET},
        )
        display_out = {**payload, "observer_surface_incremental": incremental}
        p3_perf_bump(world, resets=1)
    elif isinstance(incremental, dict):
        display_out = {**payload, "observer_surface_incremental": incremental}

    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "status": payload.get("status"),
        "available": payload.get("available"),
        "labels": payload.get("labels"),
        "facet_count": payload.get("facet_count"),
        "entity_sample_count": payload.get("entity_sample_count"),
        "state_counts": payload.get("state_counts"),
        "counts_by_face": payload.get("counts_by_face"),
        "source": payload.get("source"),
        "organism_comparison": payload.get("organism_comparison"),
        "o5_timing": payload.get("o5_timing"),
        "performance": payload.get("performance"),
        "composite_transform": COMPOSITE_TRANSFORM,
        "display_modes": list(DISPLAY_MODES),
        "internal_vw1_faces_rendered": False,
        "surface_uses_o2_exposed_facets": True,
        "vw7_pixels_used_as_authority": False,
        "display_rgb_is_physical_authority": False,
        "researcher_only": True,
        "feeds_cognition": False,
        "physical_mechanism": False,
        "static_payload_id": static_id,
        "dynamic_revision": payload.get("dynamic_revision"),
        "incremental_wire_kind": wire_kind,
        "observer_surface_incremental": incremental,
        # Full display data for SURFACE mode (bounded by O2 exposed set, not 3072 prisms)
        "display": display_out,
    }


def build_o6_analyzer_summary(evidence: dict[str, Any] | None = None, *, on_progress: Any = None) -> dict[str, Any]:
    ev = evidence if isinstance(evidence, dict) else {}
    if on_progress:
        on_progress("INDEX_O6_DISPLAY", 0, 1)
        on_progress("AGGREGATING", 1, 1)
    disp = ev.get("display") if isinstance(ev.get("display"), dict) else ev
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "section": "RESEARCHER PHYSICAL OPTICAL AUDIT (O6)",
        "exposed_facet_count": disp.get("facet_count") or (disp.get("facets_columnar") or {}).get("n") or len(disp.get("facets") or []),
        "analytic_entity_surface_count": disp.get("entity_sample_count") or len(disp.get("entity_samples") or []),
        "state_counts": disp.get("state_counts") or {},
        "organism_linked_trace": bool((disp.get("organism_comparison") or {}).get("uses_exact_o4_trace")),
        "timing_alignment_status": (disp.get("o5_timing") or {}).get("alignment_status"),
        "status": disp.get("status") or STATUS_LEGACY,
        "uses_rendered_pixels": False,
        "researcher_only": True,
        "labels": list(LABELS),
    }


def format_o6_section(summary: dict[str, Any] | None) -> str:
    s = summary or {}
    return "\n".join([
        "RESEARCHER PHYSICAL OPTICAL AUDIT (O6)",
        f"  status: {s.get('status')}",
        f"  exposed_facets: {s.get('exposed_facet_count')}",
        f"  entity_samples: {s.get('analytic_entity_surface_count')}",
        f"  organism_linked_trace: {s.get('organism_linked_trace')}",
        "  uses_rendered_pixels: False",
    ])


def derive_from_saved_evidence(evidence: dict[str, Any] | None) -> dict[str, Any]:
    ev = evidence if isinstance(evidence, dict) else {}
    if ev.get("schema") == SCHEMA and isinstance(ev.get("display") or ev.get("facets"), (dict, list)):
        return {**ev, "legacy_policy": "CURRENT_O6_EXACT", "authority_label": AUTHORITY}
    if ev.get("exposed_surface_optical_interaction_authority") or ev.get("o2_facet_checksum"):
        return {
            "schema": SCHEMA,
            "status": STATUS_LEGACY if not ev.get("abstract_spectral_light_source_and_direct_transport") else "PARTIAL",
            "legacy_policy": "COMPATIBLE_REDUCED_FROM_O2_O3",
            "available": True,
            "partial": True,
        }
    return {
        "schema": SCHEMA,
        "status": STATUS_LEGACY,
        "legacy_policy": "LEGACY_UNAVAILABLE",
        "available": False,
        "message": "UNAVAILABLE",
    }


PRIVACY_DENYLIST_TOKENS = (
    CAPABILITY,
    SCHEMA,
    PROFILE,
    AUTHORITY,
    "researcher_physical_optical_audit_view",
    "composite_display_rgb",
    "causal_display_color",
    "o6_display",
    "SURFACE_LIGHT",
)
