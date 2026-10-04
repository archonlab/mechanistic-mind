"""Acanthostega VW7 · Observer camera occupancy consumer.

Mechanism: observer_camera_occupancy_consumer
Schema: OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1
Authority: RESEARCHER_CAMERA_OVER_AUTHORITATIVE_VOLUMETRIC_OCCUPANCY

Passive render description derived from VW1 occupancy + authoritative body/RO poses.
Never writes physics. Never drives organism vision. Camera is researcher-only.

Coordinate transform (simulation → renderer):
  render_x = simulation_x
  render_y = simulation_z   (vertical up)
  render_z = simulation_y   (depth)
XY displayed as one canonical tile (physical topology remains WRAP_PERIODIC).
Z is absolute and shared across occupancy / bodies / ResourceObjects.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1"
CAPABILITY = "researcher_3d_camera_over_authoritative_volumetric_world"
PROFILE = "OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1"
AUTHORITY = "RESEARCHER_CAMERA_OVER_AUTHORITATIVE_VOLUMETRIC_OCCUPANCY"
MECHANISM_ID = "observer_camera_occupancy_consumer"

# Explicit simulation → renderer axis mapping (single authority).
COORDINATE_TRANSFORM = {
    "render_x": "simulation_x",
    "render_y": "simulation_z",
    "render_z": "simulation_y",
    "vertical_axis": "render_y",
    "xy_domain": "CANONICAL_TILE_NO_INFINITE_REPEAT",
    "xy_topology_physical": "WRAP_PERIODIC",
    "z_wrap": False,
}

AUTHORITY_FLAGS = {
    "schema": SCHEMA,
    "capability": CAPABILITY,
    "profile": PROFILE,
    "authority": AUTHORITY,
    "occupancy_owner": "volumetric_world_material_occupancy",
    "renderer_writes_physics": False,
    "camera_researcher_only": True,
    "camera_enters_simulation": False,
    "render_lighting": "OBSERVER_RENDER_LIGHTING_ONLY",
    "render_materials_affect_physics": False,
    "drives_organism_vision": False,
    "semantic_cave_object": False,
    "heightfield_is_volume_authority": False,
    "agent_accessible": False,
    "researcher_only": True,
}


def observer_camera_occupancy_consumer_is_active(config: Any) -> bool:
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        volumetric_world_material_occupancy_is_active,
    )

    return bool(volumetric_world_material_occupancy_is_active(config))


def _material_display_key(interval: Any) -> str:
    comp = getattr(interval, "composition", None) or ()
    if not comp:
        return "unknown"
    parts = []
    for item in comp:
        if isinstance(item, tuple) and len(item) >= 1:
            parts.append(str(item[0]))
        elif hasattr(item, "component_id"):
            parts.append(str(item.component_id))
    return "+".join(parts) if parts else "unknown"


def _sim_to_render(x: float, y: float, z: float) -> list[float]:
    return [float(x), float(z), float(y)]


def build_occupancy_volume_primitives(world: Any, *, config: Any = None) -> list[dict[str, Any]]:
    """One prism per authoritative VW1 occupied interval over the canonical tile.

    Enumerates resolved intervals via occupied_intervals_at / column_view authority
    (sparse override OR legacy/procedural baseline derivation). Read-only; never
    writes physics. Empty-column overrides yield no prism. Free gaps = absence.
    """
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        state_of,
        occupied_intervals_at,
        column_view,
    )

    st = state_of(world)
    if st is None:
        return []
    width = int(getattr(st, "width", 0) or 0)
    height = int(getattr(st, "height", 0) or 0)
    if width <= 0 or height <= 0:
        T = getattr(world, "T", None)
        shape = getattr(T, "shape", None)
        if shape is not None and len(shape) >= 2:
            height = int(shape[0])
            width = int(shape[1])
    if width <= 0 or height <= 0 and config is not None:
        planet = getattr(config, "planet", None)
        width = int(getattr(planet, "width", 0) or 0)
        height = int(getattr(planet, "height", 0) or 0)
    if width <= 0 or height <= 0:
        cells = sorted(st.columns.keys())
    else:
        cells = [(x, y) for y in range(height) for x in range(width)]
    out: list[dict[str, Any]] = []
    for cx, cy in cells:
        intervals = occupied_intervals_at(world, int(cx), int(cy))
        if not intervals:
            continue
        cv = column_view(world, int(cx), int(cy)) or {}
        src = str(cv.get("source") or "VW1_RESOLVED")
        if src == "SPARSE_AUTHORITY" or "SPARSE" in src.upper():
            render_source = "VW1_SPARSE_AUTHORITY"
        elif "LEGACY" in src.upper() or "DERIV" in src.upper():
            render_source = "VW1_BASELINE_DERIVED_AUTHORITY"
        else:
            render_source = "VW1_RESOLVED_AUTHORITY"
        for it in intervals:
            z_min = float(getattr(it, "z_min", 0.0) if not isinstance(it, dict) else it.get("z_min", 0.0))
            z_max = float(getattr(it, "z_max", 0.0) if not isinstance(it, dict) else it.get("z_max", 0.0))
            if isinstance(it, dict):
                mat = "unknown"
                dens = float(it.get("density", 0.0) or 0.0)
                comp = it.get("composition") or []
                composition = [
                    {"component_id": str(c.get("component_id") if isinstance(c, dict) else c[0] if isinstance(c, (list, tuple)) else c),
                     "quantity_per_area": float(c.get("quantity_per_area") if isinstance(c, dict) else (c[1] if isinstance(c, (list, tuple)) and len(c) > 1 else 0.0))}
                    for c in comp
                ]
            else:
                mat = _material_display_key(it)
                dens = float(getattr(it, "density", 0.0) or 0.0)
                composition = [
                    {"component_id": str(a), "quantity_per_area": float(b)}
                    for a, b in (getattr(it, "composition", None) or ())
                ]
            out.append(
                {
                    "kind": "OCCUPIED_INTERVAL_PRISM",
                    "cell_x": int(cx),
                    "cell_y": int(cy),
                    "sim_x0": float(cx),
                    "sim_x1": float(cx) + 1.0,
                    "sim_y0": float(cy),
                    "sim_y1": float(cy) + 1.0,
                    "sim_z_min": z_min,
                    "sim_z_max": z_max,
                    "render_center": _sim_to_render(cx + 0.5, cy + 0.5, 0.5 * (z_min + z_max)),
                    "render_size": [1.0, float(z_max - z_min), 1.0],
                    "material_display_key": mat,
                    "density": dens,
                    "composition": composition,
                    "source": render_source,
                    "researcher_only": True,
                }
            )
    out.sort(
        key=lambda p: (
            int(p["cell_x"]),
            int(p["cell_y"]),
            float(p["sim_z_min"]),
            float(p["sim_z_max"]),
            str(p["material_display_key"]),
        )
    )
    return out


def build_body_render_primitives(runtime: Any) -> list[dict[str, Any]]:
    """Bodies at authoritative centre_z. No surface snap."""
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        centre_z_of,
        vertical_half_extent_of,
        flat_ground_gravity_is_active,
    )

    cfg = getattr(runtime, "config", None)
    slots = list(getattr(runtime, "slots", None) or [])
    bodies = []
    if slots:
        iterable = [(i, slot.body, getattr(slot, "config", cfg)) for i, slot in enumerate(slots)]
    else:
        iterable = [(0, getattr(runtime, "body", None), cfg)]
    for i, body, _bcfg in iterable:
        if body is None:
            continue
        x = float(getattr(body, "x", 0.0) or 0.0)
        y = float(getattr(body, "y", 0.0) or 0.0)
        if cfg is not None and flat_ground_gravity_is_active(cfg):
            cz = float(centre_z_of(body, kind="body", config=cfg))
            he = float(vertical_half_extent_of(body, kind="body", config=cfg))
        else:
            cz = float(getattr(body, "z", 0.0) or 0.0)
            he = float(getattr(body, "vertical_half_extent", None) or 0.5)
        bodies.append(
            {
                "kind": "BODY_SPHERE",
                "body_id": f"body-{i}",
                "agent_id": f"agent_{i}",
                "sim_x": x,
                "sim_y": y,
                "sim_centre_z": cz,
                "sim_half_extent": he,
                "render_center": _sim_to_render(x, y, cz),
                "render_radius": max(0.05, he),
                "surface_snapped": False,
                "researcher_only": True,
            }
        )
    bodies.sort(key=lambda b: (str(b["body_id"]), float(b["sim_x"]), float(b["sim_y"])))
    return bodies


def build_resource_object_render_primitives(world: Any, *, config: Any = None) -> list[dict[str, Any]]:
    """ResourceObjects at authoritative physical pose (incl. held). No surface snap."""
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        centre_z_of,
        vertical_half_extent_of,
        flat_ground_gravity_is_active,
    )
    from mechanistic_mind.physical_system.resource_objects import ensure_resource_object_state

    objs = ensure_resource_object_state(world)
    out: list[dict[str, Any]] = []
    for obj in objs:
        x = float(getattr(obj, "x", 0.0) or 0.0)
        y = float(getattr(obj, "y", 0.0) or 0.0)
        if config is not None and flat_ground_gravity_is_active(config):
            cz = float(centre_z_of(obj, kind="object", config=config))
            he = float(vertical_half_extent_of(obj, kind="object", config=config))
        else:
            cz = float(getattr(obj, "z", 0.0) or 0.0)
            he = float(getattr(obj, "vertical_half_extent", None) or 0.25)
        state = str(getattr(obj, "physical_state", "") or "")
        r = float(getattr(obj, "collision_radius", None) or he or 0.25)
        out.append(
            {
                "kind": "RESOURCE_OBJECT_SPHERE",
                "object_id": str(getattr(obj, "object_id", "")),
                "physical_state": state,
                "held": state == "HELD",
                "holder_body_id": getattr(obj, "holder_body_id", None),
                "sim_x": x,
                "sim_y": y,
                "sim_centre_z": cz,
                "sim_half_extent": he,
                "render_center": _sim_to_render(x, y, cz),
                "render_radius": max(0.05, r),
                "surface_snapped": False,
                "researcher_only": True,
            }
        )
    out.sort(key=lambda o: (str(o["object_id"]), float(o["sim_x"]), float(o["sim_y"])))
    return out


def build_observer_volume_render_description(runtime: Any) -> dict[str, Any]:
    """Deterministic researcher-only render description. PassivePassive.

    P2: VW1 occupancy prisms cached by occupancy_digest (static); bodies/ROs
    always refreshed (dynamic). Never writes physics.
    """
    import time

    world = getattr(runtime, "world", None)
    config = getattr(runtime, "config", None)
    active = observer_camera_occupancy_consumer_is_active(config)
    if not active or world is None:
        return {
            "schema": SCHEMA,
            "authority": AUTHORITY,
            "available": False,
            "reason": "VW1_OCCUPANCY_INACTIVE_OR_MISSING",
            "occupancy_volumes": [],
            "bodies": [],
            "resource_objects": [],
            "coordinate_transform": dict(COORDINATE_TRANSFORM),
            "researcher_only": True,
            "camera_researcher_only": True,
            "drives_organism_vision": False,
            "label": "RESEARCHER PHYSICAL WORLD VOLUME VIEW UNAVAILABLE",
            **AUTHORITY_FLAGS,
        }

    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of
    from mechanistic_mind.ui.psy_observer_web.observer_volume_incremental_payload import (
        KIND_FULL,
        STATIC_CACHE_ATTR,
        build_incremental_envelope,
        build_volume_dynamic_block,
        build_volume_static_block,
        ensure_interval_ids,
        make_static_payload_id,
        p2_perf_bump,
    )

    st = state_of(world)
    w = int(getattr(st, "width", 32) or 32) if st is not None else int(world.T.shape[1])
    h = int(getattr(st, "height", 32) or 32) if st is not None else int(world.T.shape[0])
    digest = st.digest() if st is not None else ""

    runtime_generation = None
    try:
        runtime_generation = int(getattr(runtime, "_observer_runtime_generation", 0) or 0) or None
    except Exception:
        runtime_generation = None

    static_id = make_static_payload_id(
        occupancy_digest=str(digest),
        width=w,
        height=h,
        runtime_generation=runtime_generation,
    )

    # ---- Static VW1 occupancy prisms ----
    t_static0 = time.perf_counter()
    static_hit = False
    prev = getattr(world, STATIC_CACHE_ATTR, None)
    if (
        isinstance(prev, dict)
        and prev.get("static_payload_id") == static_id
        and isinstance(prev.get("occupancy_volumes"), list)
    ):
        volumes = prev["occupancy_volumes"]
        static_hit = True
        p2_perf_bump(world, static_hits=1)
    else:
        volumes = ensure_interval_ids(build_occupancy_volume_primitives(world, config=config))
        p2_perf_bump(world, static_misses=1, static_build_ms=(time.perf_counter() - t_static0) * 1000.0)
        setattr(
            world,
            STATIC_CACHE_ATTR,
            {
                "static_payload_id": static_id,
                "occupancy_digest": digest,
                "occupancy_volumes": volumes,
                "width": w,
                "height": h,
            },
        )
    static_ms = (time.perf_counter() - t_static0) * 1000.0

    # ---- Dynamic entities always refreshed ----
    t_ent0 = time.perf_counter()
    prev_body_ids: set[str] = set()
    prev_obj_ids: set[str] = set()
    prev_dyn = getattr(world, "_vw7_p2_last_dynamic_ids", None)
    if isinstance(prev_dyn, dict):
        prev_body_ids = set(prev_dyn.get("bodies") or [])
        prev_obj_ids = set(prev_dyn.get("objects") or [])

    bodies = build_body_render_primitives(runtime)
    objects = build_resource_object_render_primitives(world, config=config)
    cur_body_ids = {str(b.get("body_id") or "") for b in bodies}
    cur_obj_ids = {str(o.get("object_id") or "") for o in objects}
    cur_body_ids.discard("")
    cur_obj_ids.discard("")
    tombstones = (
        [{"entity_id": eid, "kind": "BODY", "tombstone": True} for eid in sorted(prev_body_ids - cur_body_ids)]
        + [{"entity_id": oid, "kind": "RESOURCE_OBJECT", "tombstone": True} for oid in sorted(prev_obj_ids - cur_obj_ids)]
    )
    setattr(
        world,
        "_vw7_p2_last_dynamic_ids",
        {"bodies": sorted(cur_body_ids), "objects": sorted(cur_obj_ids)},
    )
    p2_perf_bump(world, entity_rebuilds=1, entity_build_ms=(time.perf_counter() - t_ent0) * 1000.0)

    tick = int(getattr(world, "tick", 0) or 0)
    import hashlib as _hl
    dynamic_revision = _hl.sha256(
        f"{static_id}|{tick}|{len(bodies)}|{len(objects)}|{bodies}|{objects}".encode("utf-8")
    ).hexdigest()[:16]

    volume_static = build_volume_static_block(
        static_payload_id=static_id,
        occupancy_digest=str(digest),
        width=w,
        height=h,
        occupancy_volumes=volumes,
        coordinate_transform=COORDINATE_TRANSFORM,
        runtime_generation=runtime_generation,
    )
    volume_dynamic = build_volume_dynamic_block(
        static_payload_id=static_id,
        dynamic_revision=dynamic_revision,
        tick=tick,
        bodies=bodies,
        resource_objects=objects,
        entity_tombstones=tombstones,
        occupancy_digest=str(digest),
    )
    incremental = build_incremental_envelope(
        kind=KIND_FULL,
        volume_static=volume_static,
        volume_dynamic=volume_dynamic,
        telemetry={
            "static_cache": "hit" if static_hit else "miss",
            "static_build_ms": round(static_ms, 3),
            "entity_build_ms": round((time.perf_counter() - t_ent0) * 1000.0, 3),
            "prism_count": len(volumes),
        },
    )

    return {
        "schema": SCHEMA,
        "authority": AUTHORITY,
        "available": True,
        "occupancy_digest": digest,
        "sparse_column_count": int(len(st.columns)) if st is not None else 0,
        "occupancy_volume_count": len(volumes),
        "occupancy_volumes": volumes,
        "bodies": bodies,
        "resource_objects": objects,
        "world_tile": {"width": w, "height": h, "domain": "CANONICAL_TILE"},
        "coordinate_transform": dict(COORDINATE_TRANSFORM),
        "lighting": "OBSERVER_RENDER_LIGHTING_ONLY",
        "label": "RESEARCHER PHYSICAL WORLD VOLUME VIEW · NOT ORGANISM VISION",
        "researcher_only": True,
        "camera_researcher_only": True,
        "drives_organism_vision": False,
        "semantic_cave_object": False,
        "heightfield_is_volume_authority": False,
        "source": "VW1_SPARSE_AUTHORITY",
        "static_payload_id": static_id,
        "dynamic_revision": dynamic_revision,
        "observer_volume_incremental": incremental,
        **AUTHORITY_FLAGS,
    }


def researcher_payload(
    runtime: Any,
    *,
    held_static_payload_id: str | None = None,
    prefer_incremental: bool = True,
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.beta4_performance_benchmark import (
        count as _b4p_count,
        is_enabled as _b4p_on,
        span as _b4p_span,
    )
    from mechanistic_mind.ui.psy_observer_web.observer_volume_incremental_payload import (
        KIND_DYNAMIC,
        KIND_FULL,
        KIND_RESET,
        build_incremental_envelope,
        build_volume_reset_block,
        p2_perf_bump,
    )

    world = getattr(runtime, "world", None)
    static_warm = world is not None and getattr(world, "_vw7_p2_static_volume_cache", None) is not None
    if _b4p_on():
        with _b4p_span("volume_payload_build", parent="frame_payload_build", cache="warm" if static_warm else "cold"):
            desc = build_observer_volume_render_description(runtime)
        _b4p_count("occupancy_volumes", int(desc.get("occupancy_volume_count") or 0))
        if static_warm:
            _b4p_count("volume_static_cache_hit")
        else:
            _b4p_count("volume_static_cache_miss")
    else:
        desc = build_observer_volume_render_description(runtime)

    incremental = desc.get("observer_volume_incremental")
    static_id = str(desc.get("static_payload_id") or "")
    held = str(held_static_payload_id or "") if held_static_payload_id else ""
    wire_kind = KIND_FULL
    out_desc = desc

    if prefer_incremental and held and static_id and held == static_id and isinstance(incremental, dict):
        wire_kind = KIND_DYNAMIC
        dyn = incremental.get("volume_dynamic")
        incremental = build_incremental_envelope(
            kind=KIND_DYNAMIC,
            volume_static=None,
            volume_dynamic=dyn,
            telemetry={
                **dict((desc.get("observer_volume_incremental") or {}).get("telemetry") or {}),
                "wire_kind": KIND_DYNAMIC,
                "omitted_static_geometry": True,
            },
        )
        out_desc = {
            **desc,
            "occupancy_volumes": [],
            "occupancy_volumes_static_omitted": True,
            "occupancy_volume_count": int(desc.get("occupancy_volume_count") or 0),
            "observer_volume_incremental": incremental,
            "incremental_wire_kind": wire_kind,
        }
        if world is not None:
            p2_perf_bump(world, dynamic_wire=1)
    elif prefer_incremental and held and static_id and held != static_id:
        wire_kind = KIND_RESET
        reset = build_volume_reset_block(
            reason="HELD_STATIC_MISMATCH",
            static_payload_id=static_id,
            detail=f"held={held} current={static_id}",
        )
        incremental = build_incremental_envelope(
            kind=KIND_RESET,
            volume_static=(incremental or {}).get("volume_static") if isinstance(incremental, dict) else None,
            volume_dynamic=(incremental or {}).get("volume_dynamic") if isinstance(incremental, dict) else None,
            volume_reset=reset,
            telemetry={"wire_kind": KIND_RESET},
        )
        out_desc = {**desc, "observer_volume_incremental": incremental, "incremental_wire_kind": wire_kind}
        if world is not None:
            p2_perf_bump(world, resets=1)
    else:
        out_desc = {**desc, "incremental_wire_kind": wire_kind}

    return {"observer_camera_occupancy_consumer": out_desc}


def invalidate_vw7_volume_caches(world: Any) -> None:
    """Clear derived VOLUME display caches (restore / generation)."""
    from mechanistic_mind.ui.psy_observer_web.observer_volume_incremental_payload import (
        invalidate_p2_volume_caches,
    )
    invalidate_p2_volume_caches(world)
    if world is not None and hasattr(world, "_vw7_p2_last_dynamic_ids"):
        setattr(world, "_vw7_p2_last_dynamic_ids", None)


def catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "config_path": "volumetric_world_material_occupancy.enabled",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED",
        "promotion_class": "EXPERIMENTAL",
        "schema": SCHEMA,
        "profile": PROFILE,
        "description": (
            "Researcher 3D camera consumes VW1 occupancy + authoritative body/RO XYZ. "
            "Never writes physics. Not organism vision."
        ),
    }
