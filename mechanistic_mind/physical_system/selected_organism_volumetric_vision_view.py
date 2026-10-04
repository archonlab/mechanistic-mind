"""SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1 — researcher reconstruction of VW6.

Observational only. Captures exact VW6 sample/LOS/receptor values from the
scientific perception pass. Does not recompute perception for Observer polling.
Does not alter cognition, VW6 numerics, or organism vision.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "SELECTED_ORGANISM_VOLUMETRIC_VISION_VIEW_V1"
CAPABILITY = "selected_organism_volumetric_vision_view"
PROFILE = "VW6_PHYSICAL_GEOMETRY_TO_ORGANISM_VISUAL_INPUT_AUDIT_V1"
AUTHORITY = "RESEARCHER_VISUALIZATION_OVER_EXISTING_VW6_PERCEPTION"
STATE_SCHEMA = "SELECTED_ORGANISM_VOLUMETRIC_VISION_STATE_V1"
WORLD_ATTR = "selected_organism_volumetric_vision_state"
CAPTURE_CTX_ATTR = "_sovv_capture_context"

HISTORY_CAPACITY_DEFAULT = 128  # total across agents (FIFO)
BANNER = (
    "SELECTED ORGANISM VOLUMETRIC VISION\n"
    "RESEARCHER RECONSTRUCTION OF AUTHORITATIVE VISUAL SAMPLES\n"
    "NOT A CAMERA · NOT RENDERER PIXELS · NOT MIND READING"
)
MODE_LABEL = "SELECTED ORGANISM VOLUMETRIC VISION"
WARNING_LABEL = BANNER
EXPERIMENTER_UNAVAILABLE = "EXPERIMENTER_VOLUMETRIC_VISION_BOUNDARY_NOT_AVAILABLE"
LEGACY_UNAVAILABLE = "SELECTED_ORGANISM_VOLUMETRIC_VISION_UNAVAILABLE_LEGACY_EVIDENCE"
RECEPTOR_ONLY_FALLBACK = "RECEPTOR_ONLY_FALLBACK_GEOMETRIC_TRACE_UNAVAILABLE"

LIMITATIONS = (
    "NO_ORGANISM_PITCH_MOTOR",
    "VERTICAL_HALF_ANGLE_DEFAULT_PM90",
    "TARGET_POINT_APPROXIMATION",
    "WORLD_OCCUPANCY_LOS_ONLY",
    "NO_BODY_OR_RESOURCE_OBJECT_RAY_OCCLUSION",
    "ANGULAR_PLOT_IS_RESEARCHER_RECONSTRUCTION",
    "FALSE_COLOR_NOT_PHOTOREAL",
    "BLANK_MAY_MEAN_UNSAMPLED",
    "NOT_VW7_CAMERA",
    "NOT_CONSCIOUSNESS",
)


@dataclass
class SelectedOrganismVolumetricVisionState:
    schema_version: str = STATE_SCHEMA
    capacity: int = HISTORY_CAPACITY_DEFAULT
    traces: list[dict[str, Any]] = field(default_factory=list)
    evicted_count: int = 0
    capture_count: int = 0
    deduplicated_count: int = 0
    last_trace_id: str | None = None
    last_capture_tick: int | None = None
    runtime_generation: int | None = None


def ensure_state(world: Any) -> SelectedOrganismVolumetricVisionState:
    st = getattr(world, WORLD_ATTR, None)
    if isinstance(st, SelectedOrganismVolumetricVisionState):
        return st
    st = SelectedOrganismVolumetricVisionState()
    setattr(world, WORLD_ATTR, st)
    return st


def state_of(world: Any) -> SelectedOrganismVolumetricVisionState | None:
    st = getattr(world, WORLD_ATTR, None)
    return st if isinstance(st, SelectedOrganismVolumetricVisionState) else None


def begin_scientific_capture(
    world: Any,
    *,
    agent_id: str,
    body_id: str,
    agent_slot: int | None = None,
    run_id: str = "live",
    runtime_generation: int | None = None,
    decision_tick: int | None = None,
    experimenter: bool = False,
) -> None:
    """Arm capture for the scientific perception pass only."""
    setattr(
        world,
        CAPTURE_CTX_ATTR,
        {
            "agent_id": str(agent_id),
            "body_id": str(body_id),
            "agent_slot": agent_slot,
            "run_id": str(run_id),
            "runtime_generation": runtime_generation,
            "decision_tick": decision_tick,
            "experimenter": bool(experimenter),
        },
    )


def end_scientific_capture(world: Any) -> None:
    if hasattr(world, CAPTURE_CTX_ATTR):
        try:
            delattr(world, CAPTURE_CTX_ATTR)
        except Exception:
            setattr(world, CAPTURE_CTX_ATTR, None)


def capture_context(world: Any) -> dict[str, Any] | None:
    ctx = getattr(world, CAPTURE_CTX_ATTR, None)
    return ctx if isinstance(ctx, dict) else None


def _f(v: Any) -> float | None:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x or x in (float("inf"), float("-inf")):
        return None
    return x


def _occupancy_digest(world: Any) -> str | None:
    try:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
            state_of as vo_state,
        )

        st = vo_state(world)
        if st is None:
            return None
        return str(st.digest())
    except Exception:
        return None


def _rejection_class(row: dict[str, Any]) -> str:
    vis = str(row.get("visibility") or "")
    if vis == "OUTSIDE_VERTICAL_ACCEPTANCE":
        return "OUTSIDE_VERTICAL_FOV"
    if vis == "OCCLUDED_BY_OCCUPANCY" or row.get("occluded_by_occupancy"):
        return "BLOCKED_BY_VW1_OCCUPANCY"
    if vis == "OCCLUDED":
        return "OCCLUDED_SPATIAL"
    if not bool(row.get("inside_fov")):
        return "OUTSIDE_HORIZONTAL_FOV"
    final = float(row.get("final_contribution") or 0.0)
    detectable = bool(row.get("detectable"))
    if not detectable or final <= 0.0:
        # Distinguish range vs threshold when possible
        dist = row.get("distance")
        radius = row.get("_vision_radius")
        if dist is not None and radius is not None and float(dist) > float(radius) + 1e-9:
            return "BEYOND_RANGE"
        return "BELOW_THRESHOLD_OR_UNDETECTABLE"
    return "VISIBLE"


def _compact_blocker(blocker: Any) -> dict[str, Any] | None:
    if not isinstance(blocker, dict):
        return None
    interval = blocker.get("interval") if isinstance(blocker.get("interval"), dict) else {}
    return {
        "t": _f(blocker.get("t")),
        "cell_x": blocker.get("cell_x"),
        "cell_y": blocker.get("cell_y"),
        "z_hit": _f(blocker.get("z_hit")),
        "z_min": _f(interval.get("z_min")),
        "z_max": _f(interval.get("z_max")),
        # Researcher-only; never cognition
        "researcher_only": True,
    }


def _compact_sample_row(row: dict[str, Any], *, index: int) -> dict[str, Any]:
    cell = row.get("cell") or [0, 0]
    cx = int(cell[0]) if isinstance(cell, (list, tuple)) and len(cell) >= 1 else 0
    cy = int(cell[1]) if isinstance(cell, (list, tuple)) and len(cell) >= 2 else 0
    los = row.get("occupancy_los") if isinstance(row.get("occupancy_los"), dict) else {}
    rejection = _rejection_class(row)
    visible = rejection == "VISIBLE"
    # Stable anonymized researcher target id (not sent to cognition)
    tid = f"T{index:03d}_{cx}_{cy}"
    spat = row.get("spatial_sector")
    spat_label = row.get("spatial_sector_label")
    sector = None
    rel = _f(row.get("relative_angle_rad"))
    # sector index 0/1/2 when inside FOV — stored as researcher link only
    if bool(row.get("inside_fov")):
        try:
            from mechanistic_mind.physical_system.near_field_exteroception import fov_sector_index

            fov = float(row.get("_fov_deg") or 120.0)
            si = fov_sector_index(float(rel or 0.0), fov)
            sector = {0: "LEFT", 1: "FORWARD", 2: "RIGHT"}.get(si) if si is not None else None
            sector_index = si
        except Exception:
            sector_index = None
    else:
        sector_index = None
    return {
        "sample_index": int(index),
        "target_id": tid,
        "target_class": "TERRAIN_OR_OPTICAL_CELL",
        "cell": [cx, cy],
        "dx": _f(row.get("dx")),
        "dy": _f(row.get("dy")),
        "dz": _f(row.get("dz")),
        "distance_xy": _f(row.get("distance_xy")),
        "distance_3d": _f(row.get("distance")),
        "azimuth_rad": rel,
        "azimuth_deg": _f(row.get("relative_angle_deg")),
        "elevation_rad": _f(row.get("elevation_rad")),
        "elevation_deg": _f(row.get("elevation_deg")),
        "eye_xyz": list(row.get("eye_xyz") or []) if isinstance(row.get("eye_xyz"), list) else None,
        "target_xyz": list(row.get("target_xyz") or [])
        if isinstance(row.get("target_xyz"), list)
        else None,
        "horizontal_fov": "INSIDE" if bool(row.get("inside_fov")) else "OUTSIDE",
        "vertical_fov": (
            "INSIDE"
            if bool(row.get("vertical_acceptance", True))
            else "OUTSIDE"
        ),
        "los_status": (
            "CLEAR"
            if bool(los.get("visible"))
            else ("OCCLUDED" if bool(los.get("occluded")) else "UNAVAILABLE")
        ),
        "blocker": _compact_blocker(los.get("blocker") or row.get("occluded_by_occupancy")),
        "rejection_class": rejection,
        "organism_visible": bool(visible),
        "receptor_sector": sector,
        "receptor_sector_index": sector_index,
        "spatial_bin": spat_label or (f"A{spat}" if spat is not None else None),
        "spatial_bin_index": spat,
        "raw_observable": _f(row.get("raw_observable")),
        "final_contribution": _f(row.get("final_contribution")),
        "visible_contribution": _f(row.get("visible_contribution")),
        "detectable": bool(row.get("detectable")),
        "vw6_geometry": bool(row.get("vw6_geometry")),
        "visibility_label": str(row.get("visibility") or ""),
    }


def trace_id(
    *,
    run_id: str,
    scientific_tick: int,
    agent_id: str,
    body_id: str,
    occupancy_digest: str | None,
    runtime_generation: int | None,
) -> str:
    raw = {
        "schema": SCHEMA,
        "run_id": str(run_id),
        "scientific_tick": int(scientific_tick),
        "agent_id": str(agent_id),
        "body_id": str(body_id),
        "occupancy_digest": occupancy_digest,
        "runtime_generation": runtime_generation,
    }
    return hashlib.sha256(
        json.dumps(raw, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:24]


def build_trace(
    *,
    sample: dict[str, Any],
    agent_id: str,
    body_id: str,
    agent_slot: int | None,
    run_id: str,
    runtime_generation: int | None,
    decision_tick: int | None,
    world: Any,
    experimenter: bool = False,
) -> dict[str, Any] | None:
    if experimenter:
        return {
            "schema": SCHEMA,
            "capability": CAPABILITY,
            "profile": PROFILE,
            "authority": AUTHORITY,
            "availability": EXPERIMENTER_UNAVAILABLE,
            "agent_id": str(agent_id),
            "body_id": str(body_id),
            "researcher_only": True,
            "cognition_exposed": False,
        }
    if not isinstance(sample, dict):
        return None
    vw6 = sample.get("vw6")
    if not isinstance(vw6, dict):
        # Receptor-only fallback when VW6 inactive
        return {
            "schema": SCHEMA,
            "capability": CAPABILITY,
            "profile": PROFILE,
            "authority": AUTHORITY,
            "availability": RECEPTOR_ONLY_FALLBACK,
            "agent_id": str(agent_id),
            "body_id": str(body_id),
            "perception_tick": int(sample.get("tick") or 0),
            "decision_tick": decision_tick,
            "cognition_accessible": {
                "fragments": dict(sample.get("fragments") or {}),
                "surface_fragments": dict(sample.get("surface_fragments") or {}),
                "spatial_fragments": dict(sample.get("spatial_fragments") or {}),
            },
            "samples": [],
            "geometric_trace_available": False,
            "researcher_only": True,
            "cognition_exposed": False,
            "banner": BANNER,
        }

    occ = _occupancy_digest(world)
    perception_tick = int(sample.get("tick") or 0)
    eye = list(sample.get("eye_xyz") or vw6.get("eye_xyz") or [])
    fov = float(sample.get("fov_deg") or 120.0)
    vhalf = float(vw6.get("vertical_half_angle_deg") or 90.0)
    rows_in = list(sample.get("neighbors") or [])
    samples: list[dict[str, Any]] = []
    for i, row in enumerate(rows_in):
        if not isinstance(row, dict):
            continue
        row = dict(row)
        row["_fov_deg"] = fov
        row["_vision_radius"] = sample.get("vision_radius") or sample.get("radius")
        samples.append(_compact_sample_row(row, index=i))

    visible = [s for s in samples if s.get("organism_visible")]
    blocked = [s for s in samples if s.get("rejection_class") == "BLOCKED_BY_VW1_OCCUPANCY"]
    rejected = [s for s in samples if not s.get("organism_visible")]

    tid = trace_id(
        run_id=str(run_id),
        scientific_tick=perception_tick,
        agent_id=str(agent_id),
        body_id=str(body_id),
        occupancy_digest=occ,
        runtime_generation=runtime_generation,
    )
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "availability": "AVAILABLE",
        "trace_id": tid,
        "run_id": str(run_id),
        "runtime_generation": runtime_generation,
        "agent_id": str(agent_id),
        "body_id": str(body_id),
        "agent_slot": agent_slot,
        "perception_tick": perception_tick,
        "decision_tick": int(decision_tick) if decision_tick is not None else perception_tick,
        "eye_pose_tick": perception_tick,
        "receptor_output_tick": perception_tick,
        "occupancy_digest": occ,
        "eye_xyz": eye,
        "sensor_forward_axis": _f(sample.get("sensor_forward_axis")),
        "heading_source": (
            "HEAD_WORLD_HEADING" if sample.get("articulated_head_enabled") else "BODY_THETA"
        ),
        "horizontal_fov_deg": fov,
        "vertical_half_angle_deg": vhalf,
        "vision_radius": sample.get("vision_radius") or sample.get("radius"),
        "target_geometry_approximation": vw6.get("target_geometry_approximation"),
        "xy_wrap_policy": "MINIMUM_IMAGE_PERIODIC",
        "z_wrap_policy": "NONE_ABSOLUTE_Z",
        "los_authority": "VW1_AUTHORITATIVE_OCCUPANCY",
        "projection": {
            "kind": "AZIMUTH_ELEVATION_DIAGNOSTIC",
            "horizontal_axis": "relative_azimuth_within_horizontal_fov",
            "vertical_axis": "elevation_within_vertical_fov",
            "depth_encoding": "exact_vw6_distance_3d",
            "not_perspective_camera": True,
            "notes": [
                "Angular coordinates are researcher reconstruction",
                "Colors are false-color mappings",
                "Glyph size is not physical size unless labelled",
                "Blank regions may mean unsampled/no receptor response",
            ],
        },
        "counts": {
            "candidates": len(samples),
            "visible": len(visible),
            "blocked": len(blocked),
            "rejected": len(rejected),
        },
        "samples": samples,
        "cognition_accessible": {
            "fragments": dict(sample.get("fragments") or {}),
            "surface_fragments": dict(sample.get("surface_fragments") or {}),
            "spatial_fragments": dict(sample.get("spatial_fragments") or {}),
            "no_z_tokens": True,
            "no_blocker_metadata": True,
            "no_target_ids": True,
        },
        "geometric_trace_available": True,
        "researcher_only": True,
        "cognition_exposed": False,
        "banner": BANNER,
        "limitations": list(LIMITATIONS),
        "capture_seam": "sample_near_field_after_vw6_and_assemble",
        "no_replay_into_cognition": True,
    }


def capture_from_near_field_sample(
    world: Any,
    sample: dict[str, Any],
    *,
    diagnostic: bool = False,
) -> dict[str, Any] | None:
    """Append at most one finalized trace per scientific perception identity.

    Observer/diagnostic polls must not call this with an armed context.
    """
    if diagnostic:
        return None
    ctx = capture_context(world)
    if not isinstance(ctx, dict):
        return None
    if not isinstance(sample, dict):
        return None

    st = ensure_state(world)
    # Separate runtime generations
    gen = ctx.get("runtime_generation")
    if st.runtime_generation is not None and gen is not None and int(st.runtime_generation) != int(gen):
        st.traces.clear()
        st.runtime_generation = int(gen)
        st.last_trace_id = None
        st.last_capture_tick = None
    elif st.runtime_generation is None and gen is not None:
        st.runtime_generation = int(gen)

    agent_id = str(ctx.get("agent_id") or "agent_0")
    body_id = str(ctx.get("body_id") or agent_id)
    run_id = str(ctx.get("run_id") or "live")
    decision_tick = ctx.get("decision_tick")
    perception_tick = int(sample.get("tick") or 0)
    occ = _occupancy_digest(world)
    rid = trace_id(
        run_id=run_id,
        scientific_tick=perception_tick,
        agent_id=agent_id,
        body_id=body_id,
        occupancy_digest=occ,
        runtime_generation=gen,
    )
    if st.traces and st.traces[-1].get("trace_id") == rid:
        st.deduplicated_count += 1
        return st.traces[-1]
    for t in st.traces:
        if t.get("trace_id") == rid:
            st.deduplicated_count += 1
            return t

    # At most one finalized trace per agent perception tick (latest wins within tick)
    for i in range(len(st.traces) - 1, -1, -1):
        tr = st.traces[i]
        if (
            str(tr.get("agent_id")) == agent_id
            and int(tr.get("perception_tick") or -1) == perception_tick
            and tr.get("runtime_generation") == gen
        ):
            st.traces.pop(i)
            break

    tr = build_trace(
        sample=sample,
        agent_id=agent_id,
        body_id=body_id,
        agent_slot=ctx.get("agent_slot"),
        run_id=run_id,
        runtime_generation=gen,
        decision_tick=int(decision_tick) if decision_tick is not None else perception_tick,
        world=world,
        experimenter=bool(ctx.get("experimenter")),
    )
    if tr is None:
        return None
    if "trace_id" not in tr:
        tr["trace_id"] = rid
    st.traces.append(tr)
    st.capture_count += 1
    st.last_trace_id = tr.get("trace_id")
    st.last_capture_tick = perception_tick
    while len(st.traces) > int(st.capacity):
        st.traces.pop(0)
        st.evicted_count += 1
    return tr


def latest_trace_for_agent(
    world: Any, agent_id: str, *, runtime_generation: int | None = None
) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    aid = str(agent_id)
    for tr in reversed(st.traces):
        if str(tr.get("agent_id")) != aid:
            continue
        if runtime_generation is not None and tr.get("runtime_generation") is not None:
            if int(tr.get("runtime_generation")) != int(runtime_generation):
                continue
        return tr
    return None


def observer_payload(
    world: Any,
    *,
    selected_agent_id: str | None = None,
    runtime_generation: int | None = None,
) -> dict[str, Any]:
    """Read-only Observer payload. Does not capture or recompute perception."""
    st = state_of(world)
    aid = str(selected_agent_id or "agent_0")
    latest = latest_trace_for_agent(world, aid, runtime_generation=runtime_generation)
    history_for_agent: list[dict[str, Any]] = []
    if st is not None:
        for tr in st.traces:
            if str(tr.get("agent_id")) != aid:
                continue
            if runtime_generation is not None and tr.get("runtime_generation") is not None:
                if int(tr.get("runtime_generation")) != int(runtime_generation):
                    continue
            history_for_agent.append(
                {
                    "trace_id": tr.get("trace_id"),
                    "perception_tick": tr.get("perception_tick"),
                    "counts": tr.get("counts"),
                    "availability": tr.get("availability"),
                }
            )
    available = latest is not None and latest.get("availability") == "AVAILABLE"
    geometric = bool(latest.get("geometric_trace_available")) if latest else False
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "banner": BANNER,
        "mode_label": MODE_LABEL,
        "warning": WARNING_LABEL,
        "researcher_only": True,
        "cognition_exposed": False,
        "selected_agent_id": aid,
        "available": bool(available),
        "geometric_trace_available": geometric,
        "fallback": None
        if available
        else (latest.get("availability") if latest else LEGACY_UNAVAILABLE),
        "latest": latest,
        "history_index": history_for_agent[-16:],
        "capture_count": int(st.capture_count) if st else 0,
        "evicted_count": int(st.evicted_count) if st else 0,
        "deduplicated_count": int(st.deduplicated_count) if st else 0,
        "capacity": int(st.capacity) if st else HISTORY_CAPACITY_DEFAULT,
        "limitations": list(LIMITATIONS),
        "rejected_candidates_audit_default": "OFF",
        "occluded_targets_hidden_by_default": True,
        "not_vw7_camera": True,
        "not_renderer_pixels": True,
        "frontend_must_not_raycast": True,
    }


def profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
    }


def serialize_state(st: SelectedOrganismVolumetricVisionState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "researcher_configuration": True,
        "physical_state": False,
        "capacity": int(st.capacity),
        "traces": list(st.traces),
        "evicted_count": int(st.evicted_count),
        "capture_count": int(st.capture_count),
        "deduplicated_count": int(st.deduplicated_count),
        "last_trace_id": st.last_trace_id,
        "last_capture_tick": st.last_capture_tick,
        "runtime_generation": st.runtime_generation,
        "no_replay_into_cognition": True,
    }


def restore_state(world: Any, data: dict[str, Any] | None) -> SelectedOrganismVolumetricVisionState | None:
    """Restore researcher history only. Does not create a perception event."""
    if not data:
        return None
    if str(data.get("schema_version") or "") not in (STATE_SCHEMA, SCHEMA):
        return None
    st = SelectedOrganismVolumetricVisionState(
        capacity=int(data.get("capacity") or HISTORY_CAPACITY_DEFAULT),
        traces=[dict(t) for t in (data.get("traces") or []) if isinstance(t, dict)],
        evicted_count=int(data.get("evicted_count") or 0),
        capture_count=int(data.get("capture_count") or 0),
        deduplicated_count=int(data.get("deduplicated_count") or 0),
        last_trace_id=data.get("last_trace_id"),
        last_capture_tick=data.get("last_capture_tick"),
        runtime_generation=data.get("runtime_generation"),
    )
    setattr(world, WORLD_ATTR, st)
    return st


def analyzer_causal_reconstruction(trace: dict[str, Any] | None) -> dict[str, Any]:
    """Finite causal reconstruction for Analyzer. No fake progress."""
    if not isinstance(trace, dict):
        return {
            "schema": SCHEMA,
            "available": False,
            "policy": LEGACY_UNAVAILABLE,
            "stages": [],
            "processed": 0,
            "total": 0,
        }
    if trace.get("availability") == RECEPTOR_ONLY_FALLBACK:
        stages = [
            "receptor_values_present",
            "volumetric_geometry_unavailable",
            "no_pixel_inference",
        ]
        return {
            "schema": SCHEMA,
            "available": True,
            "policy": RECEPTOR_ONLY_FALLBACK,
            "stages": stages,
            "processed": len(stages),
            "total": len(stages),
            "cognition_accessible": trace.get("cognition_accessible"),
        }
    if trace.get("availability") != "AVAILABLE" or not trace.get("geometric_trace_available"):
        return {
            "schema": SCHEMA,
            "available": False,
            "policy": str(trace.get("availability") or LEGACY_UNAVAILABLE),
            "stages": [],
            "processed": 0,
            "total": 0,
        }
    samples = list(trace.get("samples") or [])
    stages = [
        "eye_pose",
        "candidate_target_sample",
        "xyz_relative_geometry",
        "fov_range_gates",
        "vw1_occupancy_los",
        "receptor_bin_contribution",
        "phenotype_final_visual_value",
        "cognition_accessible_boundary",
    ]
    return {
        "schema": SCHEMA,
        "available": True,
        "policy": "EXACT_VW6_TRACE",
        "stages": stages,
        "processed": len(stages),
        "total": len(stages),
        "trace_id": trace.get("trace_id"),
        "perception_tick": trace.get("perception_tick"),
        "agent_id": trace.get("agent_id"),
        "counts": trace.get("counts"),
        "sample_count": len(samples),
        "visible_count": sum(1 for s in samples if s.get("organism_visible")),
        "cognition_accessible": trace.get("cognition_accessible"),
        "causal_links": [
            {
                "target_id": s.get("target_id"),
                "rejection_class": s.get("rejection_class"),
                "receptor_sector": s.get("receptor_sector"),
                "spatial_bin": s.get("spatial_bin"),
                "final_contribution": s.get("final_contribution"),
            }
            for s in samples
            if s.get("organism_visible")
        ][:64],
    }
