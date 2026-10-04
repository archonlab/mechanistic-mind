"""P3 Observer SURFACE incremental payload — researcher delivery only.

Schema: OBSERVER_SURFACE_INCREMENTAL_PAYLOAD_V1
Capability: surface_persistent_geometry_and_incremental_updates
Profile: O2_O3_O3A_GENERATION_KEYED_SURFACE_DELTA_P3_V1
Authority: RESEARCHER_DERIVED_DELIVERY_OPTIMIZATION_NO_PHYSICAL_EFFECT

Does not alter O2/O3/O3A/O4/O5 physical authorities or scientific evidence.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA = "OBSERVER_SURFACE_INCREMENTAL_PAYLOAD_V1"
CAPABILITY = "surface_persistent_geometry_and_incremental_updates"
PROFILE = "O2_O3_O3A_GENERATION_KEYED_SURFACE_DELTA_P3_V1"
AUTHORITY = "RESEARCHER_DERIVED_DELIVERY_OPTIMIZATION_NO_PHYSICAL_EFFECT"

KIND_FULL = "FULL"
KIND_DYNAMIC = "DYNAMIC"
KIND_RESET = "RESET"

STATIC_CACHE_ATTR = "_o6_p3_static_terrain_cache"
OPTICAL_CACHE_ATTR = "_o6_p3_optical_columns_cache"
P3_PERF_ATTR = "_o6_p3_perf_counters"

# Geometry columns that belong to surface_static (stable with O2 topology).
STATIC_COLUMN_KEYS = (
    "facet_id",
    "face_class",
    "cell_x",
    "cell_y",
    "interval_id",
    "centre",
    "normal",
    "area",
    "span_lower",
    "span_upper",
    "boundary_plane_coordinate",
    "o1_status",
    "reflectance",
)

# Optical columns that belong to surface_dynamic (O3 result keyed).
OPTICAL_COLUMN_KEYS = (
    "state_class",
    "incident",
    "reflected",
)

RESET_REASONS = frozenset({
    "FIRST_ACTIVATION",
    "MISSING_BASE",
    "RUNTIME_GENERATION_CHANGE",
    "RESTORE",
    "VW1_OR_O2_TOPOLOGY_CHANGE",
    "O1_PROFILE_VERSION_CHANGE",
    "O3_SOURCE_REQUIRES_FULL",
    "SCHEMA_MISMATCH",
    "LEGACY_CLIENT",
    "HELD_STATIC_MISMATCH",
})


def make_static_payload_id(
    *,
    o2_key_digest: str,
    o2_facet_checksum: str,
    o1_registry_version: str,
    runtime_generation: int | None = None,
) -> str:
    raw = json.dumps(
        {
            "schema": SCHEMA,
            "o2_key": str(o2_key_digest),
            "o2_facets": str(o2_facet_checksum),
            "o1": str(o1_registry_version),
            "runtime_generation": int(runtime_generation or 0),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def split_facets_columnar(col: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a legacy facets_columnar into static geometry + optical dynamic columns."""
    src = col if isinstance(col, dict) else {}
    n = int(src.get("n") or 0)
    static = {
        "encoding": "O6_COLUMNAR_FACETS_STATIC_V1",
        "n": n,
    }
    optical = {
        "encoding": "O6_COLUMNAR_FACETS_OPTICAL_V1",
        "n": n,
    }
    for k in STATIC_COLUMN_KEYS:
        if k in src:
            static[k] = src[k]
    for k in OPTICAL_COLUMN_KEYS:
        if k in src:
            optical[k] = src[k]
    return static, optical


def merge_facets_columnar(static: dict[str, Any] | None, optical: dict[str, Any] | None) -> dict[str, Any]:
    """Materialize authority-equivalent facets_columnar from static + optical parts."""
    st = static if isinstance(static, dict) else {}
    op = optical if isinstance(optical, dict) else {}
    n = int(st.get("n") or op.get("n") or 0)
    out: dict[str, Any] = {
        "encoding": "O6_COLUMNAR_FACETS_V1",
        "n": n,
    }
    for k in STATIC_COLUMN_KEYS:
        if k in st:
            out[k] = st[k]
    for k in OPTICAL_COLUMN_KEYS:
        if k in op:
            out[k] = op[k]
    return out


def build_surface_static_block(
    *,
    static_payload_id: str,
    static_columnar: dict[str, Any],
    o2_key_digest: str,
    o2_facet_checksum: str,
    o1_registry_version: str,
    vw1_digest: str | None,
    world_tile: dict[str, Any],
    counts_by_face: dict[str, Any] | None,
    runtime_generation: int | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "part": "surface_static",
        "static_payload_id": static_payload_id,
        "runtime_generation": runtime_generation,
        "generations": {
            "o2_key_digest": o2_key_digest,
            "o2_facet_checksum": o2_facet_checksum,
            "o1_registry_version": o1_registry_version,
            "vw1_digest": vw1_digest,
        },
        "world_tile": world_tile,
        "counts_by_face": dict(counts_by_face or {}),
        "facets_columnar_static": static_columnar,
        "transform_independent": True,
        "researcher_only": True,
        "physical_mechanism": False,
    }


def build_surface_dynamic_block(
    *,
    static_payload_id: str,
    dynamic_revision: str,
    tick: int,
    optical_columnar: dict[str, Any],
    entity_samples: list[dict[str, Any]],
    entity_tombstones: list[dict[str, Any]] | None,
    state_counts: dict[str, Any] | None,
    source: dict[str, Any] | None,
    organism_comparison: dict[str, Any] | None,
    o5_timing: dict[str, Any] | None,
    o3_result_checksum: str | None,
    o3a_key_digest: str | None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "part": "surface_dynamic",
        "static_payload_id": static_payload_id,
        "dynamic_revision": dynamic_revision,
        "scientific_tick": int(tick),
        "facets_columnar_optical": optical_columnar,
        "entity_samples": list(entity_samples or []),
        "entity_tombstones": list(entity_tombstones or []),
        "state_counts": dict(state_counts or {}),
        "source": source or {},
        "organism_comparison": organism_comparison or {},
        "o5_timing": o5_timing or {},
        "generations": {
            "o3_result_checksum": o3_result_checksum,
            "o3a_key_digest": o3a_key_digest,
        },
        "researcher_only": True,
        "physical_mechanism": False,
    }


def build_surface_reset_block(
    *,
    reason: str,
    static_payload_id: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    r = str(reason) if str(reason) in RESET_REASONS else "SCHEMA_MISMATCH"
    return {
        "schema": SCHEMA,
        "part": "surface_reset",
        "reason": r,
        "static_payload_id": static_payload_id,
        "detail": detail,
        "requires_full_base": True,
        "researcher_only": True,
    }


def build_incremental_envelope(
    *,
    kind: str,
    surface_static: dict[str, Any] | None,
    surface_dynamic: dict[str, Any] | None,
    surface_reset: dict[str, Any] | None = None,
    telemetry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "kind": kind,
        "surface_static": surface_static,
        "surface_dynamic": surface_dynamic,
        "surface_reset": surface_reset,
        "telemetry": telemetry or {},
        "note": (
            "Derived researcher display optimization. "
            "Omitted static geometry is NOT scientific unavailability."
        ),
    }


def materialize_display_from_incremental(
    envelope: dict[str, Any] | None,
    *,
    held_static: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Reconstruct a legacy O6 display payload from incremental parts + held static."""
    env = envelope if isinstance(envelope, dict) else None
    if env is None:
        return None
    kind = str(env.get("kind") or "")
    st = env.get("surface_static") if isinstance(env.get("surface_static"), dict) else None
    dyn = env.get("surface_dynamic") if isinstance(env.get("surface_dynamic"), dict) else None
    if kind == KIND_DYNAMIC:
        if held_static is None:
            return None  # missing base
        if st is None:
            st = held_static
        held_id = str(held_static.get("static_payload_id") or "")
        dyn_id = str((dyn or {}).get("static_payload_id") or "")
        if held_id and dyn_id and held_id != dyn_id:
            return None  # stale/mismatch
    if st is None or dyn is None:
        return None
    static_col = st.get("facets_columnar_static") or {}
    optical_col = dyn.get("facets_columnar_optical") or {}
    facets = merge_facets_columnar(static_col, optical_col)
    return {
        "schema": "RESEARCHER_PHYSICAL_OPTICAL_AUDIT_VIEW_V1",
        "available": True,
        "status": "READY",
        "world_tile": st.get("world_tile") or {"width": 32, "height": 32},
        "o2_facet_checksum": (st.get("generations") or {}).get("o2_facet_checksum"),
        "o2_key_digest": (st.get("generations") or {}).get("o2_key_digest"),
        "o3_result_checksum": (dyn.get("generations") or {}).get("o3_result_checksum"),
        "facet_count": int(facets.get("n") or 0),
        "entity_sample_count": len(dyn.get("entity_samples") or []),
        "state_counts": dyn.get("state_counts") or {},
        "counts_by_face": st.get("counts_by_face") or {},
        "facets_columnar": facets,
        "facets": [],
        "entity_samples": list(dyn.get("entity_samples") or []),
        "source": dyn.get("source") or {},
        "organism_comparison": dyn.get("organism_comparison") or {},
        "o5_timing": dyn.get("o5_timing") or {},
        "surface_uses_o2_exposed_facets": True,
        "researcher_only": True,
        "incremental_materialized": True,
        "static_payload_id": st.get("static_payload_id"),
        "dynamic_revision": dyn.get("dynamic_revision"),
    }


def p3_perf_bump(world: Any, **kwargs: Any) -> dict[str, Any]:
    cur = getattr(world, P3_PERF_ATTR, None)
    if not isinstance(cur, dict):
        cur = {
            "static_hits": 0,
            "static_misses": 0,
            "optical_hits": 0,
            "optical_misses": 0,
            "entity_rebuilds": 0,
            "resets": 0,
            "static_build_ms_total": 0.0,
            "optical_build_ms_total": 0.0,
            "entity_build_ms_total": 0.0,
            "encode_ms_total": 0.0,
            "static_bytes_last": 0,
            "dynamic_bytes_last": 0,
        }
    for k, v in kwargs.items():
        if k.endswith("_ms"):
            cur[k.replace("_ms", "_ms_total")] = float(cur.get(k.replace("_ms", "_ms_total"), 0.0)) + float(v)
        elif k.endswith("_bytes"):
            cur[k + "_last"] = int(v)
            cur[k.replace("_bytes", "_bytes_last")] = int(v)
        elif isinstance(v, (int, float)) and not isinstance(v, bool):
            if k in cur and isinstance(cur[k], (int, float)):
                cur[k] = type(cur[k])(cur[k] + v)
            else:
                cur[k] = v
        else:
            cur[k] = v
    setattr(world, P3_PERF_ATTR, cur)
    return dict(cur)


def invalidate_p3_surface_caches(world: Any) -> None:
    for attr in (STATIC_CACHE_ATTR, OPTICAL_CACHE_ATTR):
        if hasattr(world, attr):
            setattr(world, attr, None)
