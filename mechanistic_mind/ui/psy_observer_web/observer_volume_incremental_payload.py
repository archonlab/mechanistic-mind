"""P2 Observer VOLUME incremental payload — researcher delivery only.

Schema: OBSERVER_VOLUME_INCREMENTAL_PAYLOAD_V1
Capability: volume_persistent_geometry_and_incremental_updates
Profile: VW1_GENERATION_KEYED_VOLUME_DELTA_P2_V1
Authority: RESEARCHER_DERIVED_DELIVERY_OPTIMIZATION_OVER_VW1_NO_PHYSICAL_EFFECT
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA = "OBSERVER_VOLUME_INCREMENTAL_PAYLOAD_V1"
CAPABILITY = "volume_persistent_geometry_and_incremental_updates"
PROFILE = "VW1_GENERATION_KEYED_VOLUME_DELTA_P2_V1"
AUTHORITY = "RESEARCHER_DERIVED_DELIVERY_OPTIMIZATION_OVER_VW1_NO_PHYSICAL_EFFECT"

KIND_FULL = "FULL"
KIND_DYNAMIC = "DYNAMIC"
KIND_RESET = "RESET"

# Representation: one prism instance per occupied VW1 interval (compact);
# frontend expands to faces for painter's algorithm. Not pre-expanded triangles.
REPRESENTATION = "COMPACT_INTERVAL_PRISM_LIST_FRONTEND_FACE_EXPAND"

STATIC_CACHE_ATTR = "_vw7_p2_static_volume_cache"
P2_PERF_ATTR = "_vw7_p2_perf_counters"

RESET_REASONS = frozenset({
    "FIRST_ACTIVATION",
    "MISSING_BASE",
    "RUNTIME_GENERATION_CHANGE",
    "RESTORE",
    "VW1_OCCUPANCY_CHANGE",
    "WORLD_TOPOLOGY_CHANGE",
    "SCHEMA_MISMATCH",
    "LEGACY_CLIENT",
    "HELD_STATIC_MISMATCH",
})


def make_static_payload_id(
    *,
    occupancy_digest: str,
    width: int,
    height: int,
    runtime_generation: int | None = None,
) -> str:
    raw = json.dumps(
        {
            "schema": SCHEMA,
            "representation": REPRESENTATION,
            "occupancy_digest": str(occupancy_digest),
            "width": int(width),
            "height": int(height),
            "runtime_generation": int(runtime_generation or 0),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def interval_id_for_prism(p: dict[str, Any]) -> str:
    return (
        f"I|{int(p.get('cell_x', 0))}|"
        f"{int(p.get('cell_y', 0))}|"
        f"{float(p.get('sim_z_min', 0.0)):.9g}|"
        f"{float(p.get('sim_z_max', 0.0)):.9g}|"
        f"{p.get('material_display_key') or 'unknown'}"
    )


def ensure_interval_ids(volumes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in volumes:
        row = dict(p)
        if not row.get("interval_id"):
            row["interval_id"] = interval_id_for_prism(row)
        out.append(row)
    return out


def build_volume_static_block(
    *,
    static_payload_id: str,
    occupancy_digest: str,
    width: int,
    height: int,
    occupancy_volumes: list[dict[str, Any]],
    coordinate_transform: dict[str, Any],
    runtime_generation: int | None = None,
) -> dict[str, Any]:
    vols = ensure_interval_ids(list(occupancy_volumes or []))
    return {
        "schema": SCHEMA,
        "part": "volume_static",
        "static_payload_id": static_payload_id,
        "representation": REPRESENTATION,
        "runtime_generation": runtime_generation,
        "occupancy_digest": occupancy_digest,
        "world_tile": {"width": int(width), "height": int(height), "domain": "CANONICAL_TILE"},
        "occupancy_volume_count": len(vols),
        "occupancy_volumes": vols,
        "coordinate_transform": dict(coordinate_transform or {}),
        "xy_periodic": True,
        "z_absolute": True,
        "internal_xray_occupancy_preserved": True,
        "researcher_only": True,
        "physical_mechanism": False,
    }


def build_volume_dynamic_block(
    *,
    static_payload_id: str,
    dynamic_revision: str,
    tick: int,
    bodies: list[dict[str, Any]],
    resource_objects: list[dict[str, Any]],
    entity_tombstones: list[dict[str, Any]] | None = None,
    occupancy_digest: str | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "part": "volume_dynamic",
        "static_payload_id": static_payload_id,
        "dynamic_revision": dynamic_revision,
        "scientific_tick": int(tick),
        "occupancy_digest": occupancy_digest,
        "bodies": list(bodies or []),
        "resource_objects": list(resource_objects or []),
        "entity_tombstones": list(entity_tombstones or []),
        "researcher_only": True,
        "physical_mechanism": False,
    }


def build_volume_reset_block(
    *,
    reason: str,
    static_payload_id: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    r = str(reason) if str(reason) in RESET_REASONS else "SCHEMA_MISMATCH"
    return {
        "schema": SCHEMA,
        "part": "volume_reset",
        "reason": r,
        "static_payload_id": static_payload_id,
        "detail": detail,
        "requires_full_base": True,
        "researcher_only": True,
    }


def build_incremental_envelope(
    *,
    kind: str,
    volume_static: dict[str, Any] | None,
    volume_dynamic: dict[str, Any] | None,
    volume_reset: dict[str, Any] | None = None,
    telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "kind": kind,
        "representation": REPRESENTATION,
        "volume_static": volume_static,
        "volume_dynamic": volume_dynamic,
        "volume_reset": volume_reset,
        "telemetry": telemetry or {},
        "note": (
            "Derived researcher VOLUME delivery optimization. "
            "Omitted static occupancy geometry is NOT scientific unavailability."
        ),
    }


def materialize_volume_from_incremental(
    envelope: dict[str, Any] | None,
    *,
    held_static: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Reconstruct a legacy VW7 render description from static + dynamic parts."""
    env = envelope if isinstance(envelope, dict) else None
    if env is None:
        return None
    kind = str(env.get("kind") or "")
    st = env.get("volume_static") if isinstance(env.get("volume_static"), dict) else None
    dyn = env.get("volume_dynamic") if isinstance(env.get("volume_dynamic"), dict) else None
    if kind == KIND_DYNAMIC:
        if held_static is None:
            return None
        if st is None:
            st = held_static
        held_id = str(held_static.get("static_payload_id") or "")
        dyn_id = str((dyn or {}).get("static_payload_id") or "")
        if held_id and dyn_id and held_id != dyn_id:
            return None
    if st is None or dyn is None:
        return None
    vols = list(st.get("occupancy_volumes") or [])
    tile = st.get("world_tile") or {"width": 32, "height": 32}
    return {
        "schema": "OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1",
        "authority": "RESEARCHER_CAMERA_OVER_AUTHORITATIVE_VOLUMETRIC_OCCUPANCY",
        "available": True,
        "occupancy_digest": st.get("occupancy_digest"),
        "occupancy_volume_count": len(vols),
        "occupancy_volumes": vols,
        "bodies": list(dyn.get("bodies") or []),
        "resource_objects": list(dyn.get("resource_objects") or []),
        "world_tile": tile,
        "coordinate_transform": dict(st.get("coordinate_transform") or {}),
        "static_payload_id": st.get("static_payload_id"),
        "dynamic_revision": dyn.get("dynamic_revision"),
        "incremental_materialized": True,
        "researcher_only": True,
        "camera_researcher_only": True,
        "drives_organism_vision": False,
        "label": "RESEARCHER PHYSICAL WORLD VOLUME VIEW · NOT ORGANISM VISION",
        "source": "VW1_SPARSE_AUTHORITY",
    }


def p2_perf_bump(world: Any, **kwargs: Any) -> dict[str, Any]:
    cur = getattr(world, P2_PERF_ATTR, None)
    if not isinstance(cur, dict):
        cur = {
            "static_hits": 0,
            "static_misses": 0,
            "entity_rebuilds": 0,
            "resets": 0,
            "static_build_ms_total": 0.0,
            "entity_build_ms_total": 0.0,
            "static_bytes_last": 0,
            "dynamic_bytes_last": 0,
        }
    for k, v in kwargs.items():
        if k.endswith("_ms"):
            key = k.replace("_ms", "_ms_total")
            cur[key] = float(cur.get(key, 0.0)) + float(v)
        elif k.endswith("_bytes"):
            cur[k + "_last"] = int(v)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            cur[k] = type(cur.get(k, 0))(cur.get(k, 0) + v) if k in cur else v
        else:
            cur[k] = v
    setattr(world, P2_PERF_ATTR, cur)
    return dict(cur)


def invalidate_p2_volume_caches(world: Any) -> None:
    if world is None:
        return
    if hasattr(world, STATIC_CACHE_ATTR):
        setattr(world, STATIC_CACHE_ATTR, None)
