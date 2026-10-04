"""OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1 — read-only Observer display payload.

Display-only. Never mutates physics. Never enters cognition.
Not a physical mechanism / not a public preset.

Slice: OBSERVER_TERRAIN_RELIEF_AND_FREE_SPACE_MARKERS_V1
"""
from __future__ import annotations

import math
from typing import Any

SCHEMA_VERSION = "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1"
SCHEMA_VERSION_V1_1 = "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1_1"
DISPLAY_SLICE = "OBSERVER_TERRAIN_RELIEF_AND_FREE_SPACE_MARKERS_V1"
DISPLAY_PROFILE_TRAILS = "OBSERVER_ENTITY_HEIGHT_FALL_TRAILS_V1"
ELEVATION_ORDER = "row_major_y_outer_x_inner"
ELEVATION_COORD = "cell_centre"
ELEVATION_SAMPLE = "resolved_column_at(x+0.5,y+0.5)"
DENSE_MAX_SIDE = 64
EVENT_HISTORY_CAP = 24
EVENT_DISPLAY_LIFETIME_TICKS = 32
MARKER_CLASSES = (
    "RELEASE",
    "SUPPORT_LOSS",
    "LANDING_RESPONSE",
    "ACOUSTIC_EMISSION",
)
CACHE_ATTR = "_observer_vertical_display_cache"
AUTHORITY_LABELS = {
    "elevation": "AUTHORITATIVE_SIMULATION_STATE",
    "sparse_delta": "AUTHORITATIVE_SIMULATION_STATE",
    "entity_vertical": "AUTHORITATIVE_SIMULATION_STATE",
    "events": "RESEARCHER_AUTHORITATIVE_RECEIPT",
    "packed_payload": "BACKEND_DERIVED_DISPLAY_CACHE",
    "min_max": "BACKEND_DERIVED_DISPLAY_CACHE",
    "trail_pack": "DERIVED_OBSERVER_CACHE_NON_AUTHORITATIVE",
}


def invalidate_vertical_display_cache(world: Any) -> None:
    """Drop non-authoritative Observer terrain display cache (restore/reset/apply)."""
    if world is None:
        return
    if hasattr(world, CACHE_ATTR):
        try:
            delattr(world, CACHE_ATTR)
        except Exception:
            setattr(world, CACHE_ATTR, None)
    try:
        from mechanistic_mind.ui.psy_observer_web.vertical_trail_contract import (
            invalidate_vertical_trail_cache,
        )

        invalidate_vertical_trail_cache(world)
    except Exception:
        pass


def vertical_display_compatible(runtime: Any) -> bool:
    """True when authoritative surface-column state exists for elevation display."""
    if runtime is None:
        return False
    cfg = getattr(runtime, "config", None)
    if str(getattr(cfg, "model_line", "") or "") != "ACANTHOSTEGA":
        return False
    psc = getattr(cfg, "procedural_surface_columns", None)
    if not bool(getattr(psc, "enabled", False)):
        return False
    world = getattr(runtime, "world", None)
    return world is not None and getattr(world, "surface_columns", None) is not None


def _dims(world: Any) -> tuple[int, int]:
    t = getattr(world, "T", None)
    if t is not None and getattr(t, "shape", None) is not None:
        return int(t.shape[0]), int(t.shape[1])  # height, width
    return 32, 32


def _surface_generation(world: Any) -> int:
    ras = getattr(world, "radius_aware_support_points_state", None)
    if ras is not None and hasattr(ras, "surface_generation"):
        return int(ras.surface_generation or 0)
    csg = getattr(world, "continuous_surface_geometry_state", None)
    if csg is not None and hasattr(csg, "surface_generation"):
        return int(getattr(csg, "surface_generation", 0) or 0)
    return 0


def _cache_key(world: Any, *, height: int, width: int, deltas_checksum: str | None) -> tuple:
    return (
        SCHEMA_VERSION,
        int(height),
        int(width),
        int(_surface_generation(world)),
        str(deltas_checksum or ""),
        str(getattr(getattr(world, "surface_columns", None), "config", None)
            and getattr(world.surface_columns.config, "generator_version", "") or ""),
    )


def _build_elevation_grid(world: Any, height: int, width: int) -> dict[str, Any]:
    from mechanistic_mind.physical_system.procedural_surface_columns import resolved_column_at

    data: list[list[float]] = []
    elev_min = math.inf
    elev_max = -math.inf
    for y in range(int(height)):
        row: list[float] = []
        for x in range(int(width)):
            col = resolved_column_at(world, float(x) + 0.5, float(y) + 0.5, record=False)
            z = float(col["surface_elevation"])
            if not math.isfinite(z):
                raise RuntimeError(
                    f"vertical_display: non-finite elevation at cell_centre ({x},{y})"
                )
            row.append(z)
            if z < elev_min:
                elev_min = z
            if z > elev_max:
                elev_max = z
        data.append(row)
    if not math.isfinite(elev_min) or not math.isfinite(elev_max):
        elev_min, elev_max = 0.0, 0.0
    return {
        "height": int(height),
        "width": int(width),
        "order": ELEVATION_ORDER,
        "coordinate": ELEVATION_COORD,
        "sample_policy": ELEVATION_SAMPLE,
        "data": data,
        "elev_min": float(elev_min),
        "elev_max": float(elev_max),
        "authority": AUTHORITY_LABELS["elevation"],
        "subsurface_serialized": False,
    }


def _sparse_deltas(world: Any) -> list[dict[str, Any]]:
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        baseline_column_at,
        deltas_of,
    )

    deltas = deltas_of(world)
    out: list[dict[str, Any]] = []
    for (cx, cy) in sorted(deltas.keys()):
        delta = deltas[(cx, cy)]
        base = baseline_column_at(world, cx, cy, record=False)
        baseline_z = float(base.surface_elevation)
        current_z = float(delta.resulting_surface_elevation)
        signed = float(current_z - baseline_z)
        if not all(math.isfinite(v) for v in (baseline_z, current_z, signed)):
            continue
        prov = dict(delta.provenance) if isinstance(getattr(delta, "provenance", None), dict) else {}
        out.append(
            {
                "cell_x": int(cx),
                "cell_y": int(cy),
                "baseline_elevation": baseline_z,
                "current_elevation": current_z,
                "signed_delta": signed,
                "revision": int(delta.revision),
                "delta_id": getattr(delta, "delta_id", None) or f"surface-column-delta-x{cx}-y{cy}",
                "baseline_checksum": getattr(base, "baseline_checksum", None),
                "resolved_checksum": delta.resolved_checksum() if hasattr(delta, "resolved_checksum") else None,
                "transaction_id": prov.get("transaction_id") or prov.get("material_transaction_id"),
                "source": "PROCEDURAL_BASELINE_PLUS_SPARSE_DELTA",
                "authority": AUTHORITY_LABELS["sparse_delta"],
            }
        )
    return out


def _half_extent(entity: Any, fallback: float | None = None) -> float | None:
    he = getattr(entity, "vertical_half_extent", None)
    if he is not None and math.isfinite(float(he)):
        return float(he)
    cr = getattr(entity, "collision_radius", None)
    if cr is not None and math.isfinite(float(cr)):
        return float(cr)
    if fallback is not None and math.isfinite(float(fallback)):
        return float(fallback)
    return None


def _entity_row(
    *,
    kind: str,
    entity_id: str,
    x: float,
    y: float,
    base_z: float | None,
    vz: float | None,
    grounded: bool | None,
    he: float | None,
    support_z: float | None,
    support_state: str | None,
    physical_state: str | None,
    collision_radius: float | None = None,
    optical_radius: float | None = None,
    holder_body_id: str | None = None,
    manipulator_id: str | None = None,
    dynamics_eligible_tick: int | None = None,
    detached_provenance: dict[str, Any] | None = None,
    z_available: bool = True,
) -> dict[str, Any]:
    centre_z = None
    clearance = None
    if z_available and base_z is not None and math.isfinite(float(base_z)):
        base_z = float(base_z)
        if he is not None and math.isfinite(float(he)):
            centre_z = float(base_z) + float(he)
        else:
            centre_z = float(base_z)
        if support_z is not None and math.isfinite(float(support_z)):
            clearance = float(base_z) - float(support_z)
    else:
        base_z = None  # never fabricate z=0
    held = str(physical_state or "") == "HELD"
    # Researcher-only honesty: negative clearance means feet below finite support
    # (SES_BELOW / start-penetration territory), not "on surface in MAP XY".
    below_support = bool(
        clearance is not None and math.isfinite(float(clearance)) and float(clearance) < -1e-9
    )
    return {
        "kind": kind,
        "id": str(entity_id),
        "x": float(x),
        "y": float(y),
        "base_z": base_z,
        "centre_z": centre_z,
        "vertical_half_extent": float(he) if he is not None and math.isfinite(float(he)) else None,
        "support_z": float(support_z) if support_z is not None and math.isfinite(float(support_z)) else None,
        "clearance": clearance,
        "below_support": below_support,
        "vertical_out_of_slice": below_support,
        "vx": None,  # filled by caller when authorized
        "vy": None,
        "vz": float(vz) if vz is not None and math.isfinite(float(vz)) else None,
        "grounded": grounded,
        "support_state": support_state,
        "physical_state": physical_state,
        "held_constrained": bool(held),
        "collision_radius": (
            float(collision_radius)
            if collision_radius is not None and math.isfinite(float(collision_radius))
            else None
        ),
        "optical_radius": (
            float(optical_radius)
            if optical_radius is not None and math.isfinite(float(optical_radius))
            else None
        ),
        "optical_radius_is_not_collision_radius": True,
        "glyph_is_not_physics": True,
        "holder_body_id": holder_body_id,
        "manipulator_id": manipulator_id,
        "dynamics_eligible_tick": dynamics_eligible_tick,
        "detached_terrain_provenance": detached_provenance,
        "z_available": bool(z_available and base_z is not None),
        "authority": AUTHORITY_LABELS["entity_vertical"],
    }


def _entities_vertical(runtime: Any) -> list[dict[str, Any]]:
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity
    from mechanistic_mind.physical_system.resource_objects import ensure_resource_object_state

    world = runtime.world
    cfg = runtime.config
    fs = getattr(world, "free_space_state_and_pe_authority_contract_state", None)
    last_by = dict(getattr(fs, "last_state_by_entity", {}) or {}) if fs is not None else {}
    out: list[dict[str, Any]] = []

    slots = list(getattr(runtime, "slots", None) or [runtime])
    for i, slot in enumerate(slots):
        body = getattr(slot, "body", None)
        if body is None:
            continue
        bid = str(getattr(body, "body_id", None) or getattr(slot, "agent_id", None) or f"agent_{i}")
        x = float(getattr(body, "x", 0.0) or 0.0)
        y = float(getattr(body, "y", 0.0) or 0.0)
        has_z = hasattr(body, "z")
        base_z = float(getattr(body, "z", 0.0) or 0.0) if has_z else None
        # Prefer exposing z when FGG / free-space / SES vertical path is live.
        vertical_on = (
            getattr(world, "flat_ground_gravity_state", None) is not None
            or fs is not None
            or getattr(world, "surface_elevation_support_state", None) is not None
        )
        z_available = bool(vertical_on and has_z)
        he = _half_extent(body)
        try:
            support_z = float(support_z_for_entity(world, cfg, x, y))
        except Exception:
            support_z = None
        row = _entity_row(
            kind="body",
            entity_id=bid,
            x=x,
            y=y,
            base_z=base_z if z_available else None,
            vz=float(getattr(body, "vz", 0.0) or 0.0) if z_available else None,
            grounded=bool(getattr(body, "grounded", True)) if z_available else None,
            he=he,
            support_z=support_z if z_available else None,
            support_state=last_by.get(bid),
            physical_state=None,
            z_available=z_available,
        )
        row["vx"] = float(getattr(body, "vx", 0.0) or 0.0)
        row["vy"] = float(getattr(body, "vy", 0.0) or 0.0)
        out.append(row)

    for obj in ensure_resource_object_state(world):
        oid = str(getattr(obj, "object_id", "") or "")
        x = float(getattr(obj, "x", 0.0) or 0.0)
        y = float(getattr(obj, "y", 0.0) or 0.0)
        has_z = hasattr(obj, "z")
        vertical_on = (
            getattr(world, "flat_ground_gravity_state", None) is not None
            or fs is not None
            or getattr(world, "free_object_kinematics_state", None) is not None
        )
        z_available = bool(vertical_on and has_z)
        base_z = float(getattr(obj, "z", 0.0) or 0.0) if z_available else None
        he = _half_extent(obj)
        try:
            support_z = float(support_z_for_entity(world, cfg, x, y))
        except Exception:
            support_z = None
        prov = getattr(obj, "provenance", None)
        detached = None
        if isinstance(prov, dict) and (
            prov.get("detached_terrain")
            or prov.get("source_kind") == "DETACHED_TERRAIN"
            or prov.get("detachment_transaction_id")
            or prov.get("size_geometry_profile")
        ):
            detached = {
                "source_kind": prov.get("source_kind") or prov.get("detached_terrain"),
                "transaction_id": prov.get("detachment_transaction_id") or prov.get("transaction_id"),
                "cell": prov.get("source_cell") or prov.get("cell"),
                "researcher_only": True,
            }
        row = _entity_row(
            kind="resource_object",
            entity_id=oid,
            x=x,
            y=y,
            base_z=base_z,
            vz=float(getattr(obj, "vz", 0.0) or 0.0) if z_available else None,
            grounded=bool(getattr(obj, "grounded", True)) if z_available else None,
            he=he,
            support_z=support_z if z_available else None,
            support_state=last_by.get(oid),
            physical_state=str(getattr(obj, "physical_state", "") or "") or None,
            collision_radius=float(getattr(obj, "collision_radius", 0.0) or 0.0) or None,
            optical_radius=float(getattr(obj, "optical_radius", 0.0) or 0.0) or None,
            holder_body_id=getattr(obj, "holder_body_id", None),
            manipulator_id=getattr(obj, "manipulator_id", None),
            dynamics_eligible_tick=getattr(obj, "dynamics_eligible_tick", None),
            detached_provenance=detached,
            z_available=z_available,
        )
        row["vx"] = float(getattr(obj, "vx", 0.0) or 0.0)
        row["vy"] = float(getattr(obj, "vy", 0.0) or 0.0)
        out.append(row)
    return out


def _event_marker(
    *,
    event_class: str,
    tick: int,
    entity_id: str | None,
    x: float | None,
    y: float | None,
    z: float | None,
    receipt_ref: dict[str, Any],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = {
        "event_class": event_class,
        "tick": int(tick),
        "entity_id": entity_id,
        "x": float(x) if x is not None and math.isfinite(float(x)) else None,
        "y": float(y) if y is not None and math.isfinite(float(y)) else None,
        "z": float(z) if z is not None and math.isfinite(float(z)) else None,
        "receipt_kind": receipt_ref.get("receipt_kind"),
        "receipt_ref": {
            "receipt_kind": receipt_ref.get("receipt_kind"),
            "event_sequence": receipt_ref.get("event_sequence"),
            "episode_id": receipt_ref.get("episode_id"),
            "response_key": receipt_ref.get("response_key"),
            "source_id": receipt_ref.get("source_id"),
            "material_transaction_id": receipt_ref.get("material_transaction_id"),
        },
        "authority": AUTHORITY_LABELS["events"],
        "display_lifetime_ticks": EVENT_DISPLAY_LIFETIME_TICKS,
        "display_metadata_class": "BACKEND_DERIVED_DISPLAY_HELPER",
        "researcher_only": True,
        "agent_accessible": False,
    }
    if extra:
        row.update(extra)
    return row


def _events_recent(world: Any, *, tick: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []

    v1d = getattr(world, "release_and_excavation_support_loss_integration_state", None)
    if v1d is not None:
        for rec in list(getattr(v1d, "history", None) or [])[-EVENT_HISTORY_CAP:]:
            if not isinstance(rec, dict):
                continue
            cls = str(rec.get("event_class") or "")
            if cls in ("RELEASE_ENTRY",):
                events.append(
                    _event_marker(
                        event_class="RELEASE",
                        tick=int(rec.get("tick") or 0),
                        entity_id=str(rec.get("entity_id") or "") or None,
                        x=rec.get("pose_x"),
                        y=rec.get("pose_y"),
                        z=rec.get("pose_z"),
                        receipt_ref=rec,
                        extra={
                            "release_tick": rec.get("release_tick"),
                            "dynamics_eligible_tick": rec.get("dynamics_eligible_tick"),
                            "support_classification": rec.get("support_classification"),
                            "creates_impact": False,
                            "creates_sound": False,
                            "same_tick_fall": False,
                        },
                    )
                )
            elif cls in ("SUPPORT_LOST",):
                events.append(
                    _event_marker(
                        event_class="SUPPORT_LOSS",
                        tick=int(rec.get("tick") or 0),
                        entity_id=str(rec.get("entity_id") or "") or None,
                        x=rec.get("pose_x"),
                        y=rec.get("pose_y"),
                        z=rec.get("pose_z"),
                        receipt_ref=rec,
                        extra={
                            "source_kind": rec.get("source_kind"),
                            "excavation_induced": True,
                            "entity_z_unchanged": bool(rec.get("entity_z_unchanged", True)),
                            "creates_impact": False,
                            "creates_sound": False,
                            "material_transaction_id": rec.get("material_transaction_id"),
                            "source_cell": rec.get("source_cell"),
                        },
                    )
                )

    v1b = getattr(world, "vertical_terrain_landing_contact_response_state", None)
    if v1b is not None:
        for rec in list(getattr(v1b, "history", None) or [])[-EVENT_HISTORY_CAP:]:
            if not isinstance(rec, dict):
                continue
            # Only committed landing response — not PERSIST continuity, not correction-only.
            if not bool(rec.get("response_applied")):
                continue
            cls = str(rec.get("intersection_class") or rec.get("response_classification") or "")
            phase = str(rec.get("episode_phase") or rec.get("phase") or "")
            if phase == "PERSIST":
                continue
            if cls and cls not in ("LANDING_IMPACT",) and not bool(rec.get("landed")):
                # correction-only / rest persist without impact energy
                if float(rec.get("impulse_magnitude") or 0.0) <= 0.0 and float(
                    rec.get("dissipated_energy") or 0.0
                ) <= 0.0:
                    continue
            cp = rec.get("contact_point")
            x = y = z = None
            if isinstance(cp, (list, tuple)) and len(cp) >= 3:
                x, y, z = float(cp[0]), float(cp[1]), float(cp[2])
            else:
                x = rec.get("x")
                y = rec.get("y")
                z = rec.get("base_z") or rec.get("z")
            events.append(
                _event_marker(
                    event_class="LANDING_RESPONSE",
                    tick=int(rec.get("tick") or 0),
                    entity_id=str(rec.get("entity_id") or "") or None,
                    x=x,
                    y=y,
                    z=z,
                    receipt_ref=rec,
                    extra={
                        "impulse_magnitude": rec.get("impulse_magnitude"),
                        "dissipated_energy": rec.get("dissipated_energy"),
                        "intersection_class": cls,
                        "episode_phase": phase,
                        "support_acquired": rec.get("support_acquired"),
                    },
                )
            )

    v1c = getattr(world, "vertical_impact_acoustic_emission_state", None)
    if v1c is not None:
        hist = getattr(v1c, "emission_history", None)
        if hist is None:
            hist = getattr(v1c, "history", None)
        for rec in list(hist or [])[-EVENT_HISTORY_CAP:]:
            if not isinstance(rec, dict):
                continue
            emitted = rec.get("emitted")
            if emitted is False:
                continue
            if emitted is None and not (
                rec.get("emitted_energy") is not None
                or rec.get("selected_acoustic_energy") is not None
                or str(rec.get("receipt_kind") or "") == "VERTICAL_IMPACT_ACOUSTIC_EMISSION"
            ):
                continue
            if rec.get("silence_reason"):
                continue
            energy = rec.get("emitted_energy")
            if energy is None:
                energy = rec.get("selected_acoustic_energy")
            if energy is not None and float(energy) <= 0.0:
                continue
            cp = rec.get("contact_point")
            x = y = z = None
            if isinstance(cp, (list, tuple)) and len(cp) >= 3:
                x, y, z = float(cp[0]), float(cp[1]), float(cp[2])
            eid = rec.get("emission_id")
            events.append(
                _event_marker(
                    event_class="ACOUSTIC_EMISSION",
                    tick=int(rec.get("emission_tick") or rec.get("tick") or 0),
                    entity_id=str(rec.get("entity_id") or "") or None,
                    x=x,
                    y=y,
                    z=z,
                    receipt_ref=rec,
                    extra={
                        "emitted_energy": energy,
                        "band_profile": rec.get("band_profile") or "UNIFORM_BROADBAND_V1",
                        "source_id": rec.get("source_id"),
                        "emission_id": eid,
                        "stream_record_id": (f"apas:{eid}" if eid else None),
                        "audio_playback": False,
                        "label": "PHYSICAL SIGNAL · NO AUDIO PLAYBACK",
                    },
                )
            )

    # Link ACOUSTIC_EMISSION markers to authoritative stream when present (display only).
    stream = getattr(world, "authoritative_physical_acoustic_stream_state", None)
    if stream is not None:
        by_eid = {
            str(r.get("lps_emission_id") or r.get("source_receipt_event_id")): r
            for r in list(getattr(stream, "records", None) or [])
            if isinstance(r, dict)
        }
        for ev in events:
            if ev.get("event_class") != "ACOUSTIC_EMISSION":
                continue
            extra = ev.get("extra") if isinstance(ev.get("extra"), dict) else {}
            eid = extra.get("emission_id")
            if eid and str(eid) in by_eid:
                row = by_eid[str(eid)]
                extra["stream_record_id"] = row.get("stream_record_id") or f"apas:{eid}"
                extra["source_mechanism_id"] = row.get("source_mechanism_id")
                ev["extra"] = extra

    events.sort(key=lambda e: (int(e.get("tick") or 0), str(e.get("event_class") or ""), str(e.get("entity_id") or "")))
    # Bound + drop stale beyond lifetime window relative to current tick.
    lo = int(tick) - int(EVENT_DISPLAY_LIFETIME_TICKS)
    bounded = [e for e in events if int(e.get("tick") or 0) >= lo][-EVENT_HISTORY_CAP:]
    return bounded


def build_vertical_display_payload(runtime: Any) -> dict[str, Any] | None:
    """Build OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1 or None if incompatible.

    Read-only. Uses a non-authoritative cache for dense elevation keyed by
    surface_generation + deltas_checksum + dims + schema.
    """
    if not vertical_display_compatible(runtime):
        return None
    world = runtime.world
    height, width = _dims(world)
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        deltas_checksum,
        state_of,
    )

    st = state_of(world)
    d_checksum = deltas_checksum(world) if st is not None else None
    topology = str(getattr(getattr(runtime.config, "planet", None), "spatial_topology", None) or "WRAP_PERIODIC")
    key = _cache_key(world, height=height, width=width, deltas_checksum=d_checksum)
    cache = getattr(world, CACHE_ATTR, None)
    terrain_part = None
    cache_hit = False
    if isinstance(cache, dict) and cache.get("key") == key and isinstance(cache.get("terrain"), dict):
        terrain_part = cache["terrain"]
        cache_hit = True
    else:
        if max(height, width) > DENSE_MAX_SIDE:
            elev = {
                "height": int(height),
                "width": int(width),
                "order": ELEVATION_ORDER,
                "coordinate": ELEVATION_COORD,
                "sample_policy": ELEVATION_SAMPLE,
                "data": None,
                "elev_min": None,
                "elev_max": None,
                "authority": AUTHORITY_LABELS["elevation"],
                "subsurface_serialized": False,
                "unavailable_reason": "WORLD_LARGER_THAN_DENSE_DISPLAY_LIMIT",
                "dense_max_side": DENSE_MAX_SIDE,
            }
        else:
            elev = _build_elevation_grid(world, height, width)
        sparse = _sparse_deltas(world)
        terrain_part = {
            "cell_centre_elevation": elev,
            "elev_min": elev.get("elev_min"),
            "elev_max": elev.get("elev_max"),
            "sparse_deltas": sparse,
            "surface_generation": int(_surface_generation(world)),
            "deltas_checksum": d_checksum,
            "manifest_checksum": (
                (st.manifest or {}).get("manifest_checksum") if st is not None else None
            ),
            "generator_version": getattr(getattr(st, "config", None), "generator_version", None) if st else None,
        }
        try:
            setattr(
                world,
                CACHE_ATTR,
                {"key": key, "terrain": terrain_part, "schema": SCHEMA_VERSION},
            )
        except Exception:
            pass

    tick = int(getattr(world, "tick", 0) or 0)
    entities = _entities_vertical(runtime)
    events = _events_recent(world, tick=tick)

    # Trails: display-only cache updated only on Observer serialization path.
    from mechanistic_mind.ui.psy_observer_web.vertical_trail_contract import (
        trail_payload_fragment,
    )

    gen = getattr(runtime, "runtime_generation", None)
    if gen is None:
        gen = getattr(getattr(runtime, "header", None), "runtime_generation", None)
    trail_frag = trail_payload_fragment(
        world,
        tick=tick,
        entities=entities,
        events=events,
        runtime_generation=int(gen) if gen is not None else None,
    )

    return {
        "schema_version": SCHEMA_VERSION_V1_1,
        "schema_compatible_with": [SCHEMA_VERSION, SCHEMA_VERSION_V1_1],
        "display_slice": DISPLAY_SLICE,
        "display_profiles": [DISPLAY_SLICE, DISPLAY_PROFILE_TRAILS],
        "display_contract": SCHEMA_VERSION_V1_1,
        "researcher_only": True,
        "agent_accessible": False,
        "not_a_physical_mechanism": True,
        "not_a_public_preset": True,
        "physics_authority": False,
        "width": int(width),
        "height": int(height),
        "topology": topology,
        "surface_generation": terrain_part.get("surface_generation"),
        "deltas_checksum": terrain_part.get("deltas_checksum"),
        "manifest_checksum": terrain_part.get("manifest_checksum"),
        "generator_version": terrain_part.get("generator_version"),
        "elev_min": terrain_part.get("elev_min"),
        "elev_max": terrain_part.get("elev_max"),
        "cell_centre_elevation": terrain_part.get("cell_centre_elevation"),
        "sparse_deltas": terrain_part.get("sparse_deltas"),
        "entities_vertical": entities,
        "events_recent": events,
        "event_history_cap": EVENT_HISTORY_CAP,
        "event_display_lifetime_ticks": EVENT_DISPLAY_LIFETIME_TICKS,
        "cache_hit": bool(cache_hit),
        "cache_class": AUTHORITY_LABELS["packed_payload"],
        "authority_labels": dict(AUTHORITY_LABELS),
        **trail_frag,
        "not_modelled": [
            "caves",
            "ceilings",
            "overhangs",
            "stacked_terrain",
            "volumetric_subsurface_cavities",
            "3d_acoustic_propagation",
        ],
        "dense_subsurface_serialized": False,
        "optical_radius_used_as_physical_radius": False,
        "classification": {
            "AUTHORITATIVE_SIMULATION_STATE": [
                "cell_centre_elevation",
                "sparse_deltas",
                "entities_vertical.x/y/z/vz",
                "collision_radius",
                "support_state",
                "trail sample field values (tick/x/y/z/vz/support)",
            ],
            "RESEARCHER_AUTHORITATIVE_RECEIPT": [
                "events_recent.RELEASE",
                "events_recent.SUPPORT_LOSS",
                "events_recent.LANDING_RESPONSE",
                "events_recent.ACOUSTIC_EMISSION",
            ],
            "BACKEND_DERIVED_DISPLAY_CACHE": [
                "packed elevation",
                "elev_min/max",
                "bounded event extraction",
                "cache checksum/key",
                "trail_segments packing/segmentation",
            ],
            "RENDER_DERIVED_NON_AUTHORITATIVE": [
                "false_color",
                "contours",
                "clearance_stems",
                "screen_space_offsets",
                "display_space_height",
                "marker_pulse_lifetime",
                "interpolation",
                "vertical_exaggeration",
                "trail line style/opacity",
            ],
            "AGENT_ACCESSIBLE_SENSOR": [],
        },
    }


def observer_vertical_display_payload(runtime: Any) -> dict[str, Any]:
    """World-frame fragment. Empty dict when unavailable (legacy-safe)."""
    payload = build_vertical_display_payload(runtime)
    if payload is None:
        return {}
    return {
        "vertical_display": payload,
        "vertical_display_researcher_only": True,
        "vertical_display_banner": (
            "RESEARCHER VIEW · NOT AGENT PERCEPTION · "
            "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1_1 · "
            "OBSERVER_ENTITY_HEIGHT_FALL_TRAILS_V1 · DISPLAY ONLY"
        ),
    }
