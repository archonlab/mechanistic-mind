"""ORGANISM_RECEPTOR_GROUNDED_3D_FPV_V1 — researcher FPV over exact O4 evidence.

Not a new sensor. Displays authoritative O4 accepted contributions and
cognition-boundary values. Never VW7/renderer pixels. Never recomputes LOS/light.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

SCHEMA = "ORGANISM_RECEPTOR_GROUNDED_3D_FPV_V1"
CAPABILITY = "organism_receptor_grounded_3d_fpv"
PROFILE = "EXACT_O4_RECEPTOR_CONTRIBUTION_FIRST_PERSON_RECONSTRUCTION_V1"
AUTHORITY = "RESEARCHER_DISPLAY_OVER_AUTHORITATIVE_O4_RECEPTION"
CLASSIFICATION = "BETA4_REQUIRED_OBSERVABILITY_NOT_NEW_SENSOR"
STATE_SCHEMA = "ORGANISM_RECEPTOR_GROUNDED_3D_FPV_STATE_V1"
WORLD_ATTR = "organism_receptor_grounded_3d_fpv_state"
O4_SCHEMA = "ORGANISM_PHYSICAL_OPTICAL_RECEPTION_V1"

HISTORY_CAPACITY_DEFAULT = 64  # bounded FIFO; latest_exact is separate O(agents)

REASON_NO_O4_TRACE_YET = "NO_O4_TRACE_YET"
REASON_CURRENT_OBSERVATION_NOT_CAPTURED = "CURRENT_OBSERVATION_NOT_CAPTURED"
REASON_TRACE_EVICTED_HISTORICAL_SELECTION = "TRACE_EVICTED_HISTORICAL_SELECTION"
REASON_RUNTIME_GENERATION_MISMATCH = "RUNTIME_GENERATION_MISMATCH"
REASON_AGENT_BODY_IDENTITY_MISMATCH = "AGENT_BODY_IDENTITY_MISMATCH"
REASON_LEGACY_EVIDENCE = "LEGACY_EVIDENCE"
REASON_INCOMPATIBLE_PROFILE = "INCOMPATIBLE_PROFILE"

# Fixed researcher display transform (labelled NONPHYSICAL) — pair-mean 6→3 RGB.
DISPLAY_BAND_TRANSFORM = "PAIR_MEAN_6_TO_3_DISPLAY_RGB_NONPHYSICAL_V1"
DISPLAY_BAND_TRANSFORM_PHYSICAL_AUTHORITY = False

BANNER_LINES = (
    "RESEARCHER RECONSTRUCTION",
    "EXACT O4 RECEPTOR EVIDENCE",
    "NOT A CAMERA",
    "NOT HUMAN RGB",
    "NOT CONSCIOUS EXPERIENCE",
)

PRIVACY_DENYLIST = (
    CAPABILITY,
    SCHEMA,
    PROFILE,
    AUTHORITY,
    "contribution_id",
    "surface_id",
    "entity_id",
    "blocker",
    "display_rgb",
    "trace_id",
    "o4_trace",
    "accepted_raw_six_band",
    "contrib_bands",
)


@dataclass
class ReceptorGroundedFpvState:
    schema_version: str = STATE_SCHEMA
    capacity: int = HISTORY_CAPACITY_DEFAULT
    # Bounded history (may evict). latest_by_agent is NOT subject to FIFO eviction.
    history: list[dict[str, Any]] = field(default_factory=list)
    latest_by_agent: dict[str, dict[str, Any]] = field(default_factory=dict)
    evicted_count: int = 0
    capture_count: int = 0
    deduplicated_count: int = 0
    runtime_generation: int | None = None
    last_capture_tick: int | None = None


def ensure_state(world: Any) -> ReceptorGroundedFpvState:
    st = getattr(world, WORLD_ATTR, None)
    if isinstance(st, ReceptorGroundedFpvState):
        return st
    st = ReceptorGroundedFpvState()
    setattr(world, WORLD_ATTR, st)
    return st


def state_of(world: Any) -> ReceptorGroundedFpvState | None:
    st = getattr(world, WORLD_ATTR, None)
    return st if isinstance(st, ReceptorGroundedFpvState) else None


def _digest(parts: dict[str, Any]) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _bands_to_display_rgb(bands: list[float] | None) -> list[float]:
    b = [float(x) for x in (bands or [])]
    while len(b) < 6:
        b.append(0.0)
    r = 0.5 * (b[0] + b[1])
    g = 0.5 * (b[2] + b[3])
    bl = 0.5 * (b[4] + b[5])
    m = max(r, g, bl, 1e-15)
    # Normalize for display only; values remain proportional to exact bands.
    return [r / m, g / m, bl / m] if m > 0 else [0.0, 0.0, 0.0]


def _fold_intensity(bands: list[float] | None) -> float:
    return float(sum(float(x) for x in (bands or [])))


def build_exact_fpv_trace(
    *,
    o4_trace: dict[str, Any],
    agent_id: str,
    body_id: str,
    agent_slot: int | None,
    run_id: str,
    runtime_generation: int | None,
    decision_tick: int | None,
) -> dict[str, Any]:
    """Build researcher FPV trace from full O4 reception trace (exact values only)."""
    t = int(o4_trace.get("tick") or o4_trace.get("receptor_sample_tick") or 0)
    contributors_in = list(o4_trace.get("contributors") or [])
    accepted_rows: list[dict[str, Any]] = []
    for c in contributors_in:
        if not isinstance(c, dict):
            continue
        if str(c.get("visibility_status") or "ACCEPTED") != "ACCEPTED":
            continue
        bands = list(c.get("accepted_raw_six_band") or c.get("contrib_bands") or [])
        row = {
            "contribution_id": c.get("contribution_id"),
            "observation_tick": int(c.get("observation_tick") or t),
            "receptor_tick": int(c.get("receptor_tick") or t),
            "azimuth_rad": c.get("azimuth_rad"),
            "azimuth_deg": c.get("azimuth_deg"),
            "elevation_rad": c.get("elevation_rad"),
            "elevation_deg": c.get("elevation_deg"),
            "distance_3d": c.get("distance_3d"),
            "angular_bin": c.get("angular_bin", c.get("bin")),
            "accepted_raw_six_band": bands,
            "display_rgb_nonphysical": _bands_to_display_rgb(bands),
            "raw_intensity_sum": _fold_intensity(bands),
            "angular_weight": c.get("angular_weight", c.get("angular")),
            "area_weight": c.get("area_weight"),
            "represented_angular_area_weight": c.get("represented_angular_area_weight"),
            "visibility_status": "ACCEPTED",
            # Researcher provenance — never cognition
            "surface_id": c.get("surface_id"),
            "entity_id": c.get("entity_id"),
            "entity_class": c.get("entity_class"),
            "researcher_only": True,
        }
        accepted_rows.append(row)

    raw_bins = o4_trace.get("raw_bins_pre_phenotype") or []
    pre_clip = o4_trace.get("pre_clip_bins") or []
    post_clip = list(o4_trace.get("post_clip_intensity") or [])
    clipped = list(o4_trace.get("clipped_flags") or [])
    fragments = dict(o4_trace.get("fragments") or {})
    surface_fragments = dict(o4_trace.get("surface_fragments") or {})
    phenotype = dict(o4_trace.get("phenotype") or {})

    # Cognition FPV: only surviving exo / surface channels (no per-contribution restore)
    cognition_bins: list[dict[str, Any]] = []
    n_exo = int(o4_trace.get("n_exo_channels") or max(len(post_clip), 3))
    fov = float(o4_trace.get("fov_deg") or 120.0)
    half = fov / 2.0
    # Bin centres at −fov/3, 0, +fov/3 for 3 exo sectors (LEFT/FORWARD/RIGHT)
    for i in range(n_exo):
        if n_exo == 1:
            az = 0.0
        else:
            az = -half + (i + 0.5) * (fov / float(n_exo))
        intensity = float(post_clip[i]) if i < len(post_clip) else float(fragments.get(f"exo_{i}", 0.0) or 0.0)
        pre_bands = list(pre_clip[i]) if i < len(pre_clip) and isinstance(pre_clip[i], (list, tuple)) else []
        raw_b = list(raw_bins[i]) if i < len(raw_bins) and isinstance(raw_bins[i], (list, tuple)) else []
        cognition_bins.append({
            "angular_bin": i,
            "bin_label": {0: "LEFT", 1: "FORWARD", 2: "RIGHT"}.get(i, f"BIN_{i}"),
            "azimuth_deg": float(az),
            "elevation_deg": 0.0,  # cognition has no elevation resolution
            "post_clip_intensity": intensity,
            "clipped": bool(clipped[i]) if i < len(clipped) else False,
            "raw_bins_pre_phenotype": raw_b,
            "pre_clip_bands": pre_bands,
            "display_gray": intensity,
            "surface_c0": float(surface_fragments.get(f"surface_c0_{i}", 0.0) or 0.0),
            "surface_c1": float(surface_fragments.get(f"surface_c1_{i}", 0.0) or 0.0),
            "surface_c2": float(surface_fragments.get(f"surface_c2_{i}", 0.0) or 0.0),
        })

    tid = _digest({
        "schema": SCHEMA,
        "run_id": run_id,
        "tick": t,
        "agent_id": agent_id,
        "body_id": body_id,
        "runtime_generation": runtime_generation,
        "accepted": o4_trace.get("accepted"),
    })
    reached = bool(o4_trace.get("physical_signal_reached_receptor"))
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "classification": CLASSIFICATION,
        "availability": "AVAILABLE",
        "missing_reason": None,
        "trace_id": tid,
        "run_id": str(run_id),
        "runtime_generation": runtime_generation,
        "agent_id": str(agent_id),
        "body_id": str(body_id),
        "agent_slot": agent_slot,
        "observation_tick": t,
        "receptor_tick": int(o4_trace.get("receptor_sample_tick") or t),
        "decision_tick": int(decision_tick) if decision_tick is not None else t,
        "physical_source_tick": t,
        "field_tick": t,
        "o4_schema": o4_trace.get("schema") or O4_SCHEMA,
        "o4_profile": o4_trace.get("profile"),
        "fov_deg": fov,
        "vertical_half_angle_deg": 90.0,  # O4 has no pitch motor; display FOV label only
        "max_range": o4_trace.get("max_range"),
        "eye_xyz": list(o4_trace.get("eye_xyz") or []),
        "heading": o4_trace.get("heading"),
        "accepted_count": int(o4_trace.get("accepted") or len(accepted_rows)),
        "rejected_count": int(o4_trace.get("rejected") or 0),
        "physical_signal_reached_receptor": reached,
        "true_zero_exact_trace": bool(reached is False or (int(o4_trace.get("accepted") or 0) == 0)),
        "accepted_contributions": accepted_rows,
        "rejected_contributions_excluded_from_fpv": True,
        "cognition_fpv_bins": cognition_bins,
        "cognition_accessible": {
            "fragments": fragments,
            "surface_fragments": surface_fragments,
            "no_contribution_ids": True,
            "no_entity_ids": True,
        },
        "phenotype": phenotype,
        "band_fold_policy": o4_trace.get("band_fold_policy"),
        "display_band_transform": DISPLAY_BAND_TRANSFORM,
        "display_band_transform_physical_authority": DISPLAY_BAND_TRANSFORM_PHYSICAL_AUTHORITY,
        "projection": {
            "kind": "AZIMUTH_ELEVATION_CAMERA_LIKE_RECONSTRUCTION",
            "horizontal": "exact_o4_azimuth",
            "vertical": "exact_o4_elevation",
            "depth": "exact_o4_distance_3d",
            "blob_size": "angular_bin_support_not_object_size",
            "not_camera": True,
            "not_human_rgb": True,
            "smoothing_default": "OFF",
        },
        "banner": list(BANNER_LINES),
        "researcher_only": True,
        "cognition_exposed": False,
        "vw7_pixels_used": False,
        "frontend_raycast_forbidden": True,
        "capture_seam": "scientific_o4_reception_after_accept",
    }


def capture_from_o4_trace(
    world: Any,
    o4_trace: dict[str, Any] | None,
    *,
    diagnostic: bool = False,
) -> dict[str, Any] | None:
    """Update latest_exact_trace for the scientific capture context agent.

    Observer polling must not arm capture context and must not call this as a
    side effect of frame serialization.
    """
    if diagnostic:
        return None
    if not isinstance(o4_trace, dict):
        return None
    # Prefer SOVV scientific capture context (same arming as perception)
    try:
        from mechanistic_mind.physical_system.selected_organism_volumetric_vision_view import (
            capture_context,
        )

        ctx = capture_context(world)
    except Exception:
        ctx = None
    if not isinstance(ctx, dict):
        # No scientific arming → do not create FPV traces from polls
        return None

    agent_id = str(ctx.get("agent_id") or "agent_0")
    body_id = str(ctx.get("body_id") or agent_id)
    run_id = str(ctx.get("run_id") or "live")
    gen = ctx.get("runtime_generation")
    decision_tick = ctx.get("decision_tick")

    st = ensure_state(world)
    if st.runtime_generation is not None and gen is not None and int(st.runtime_generation) != int(gen):
        st.history.clear()
        st.latest_by_agent.clear()
        st.runtime_generation = int(gen)
    elif st.runtime_generation is None and gen is not None:
        st.runtime_generation = int(gen)

    tr = build_exact_fpv_trace(
        o4_trace=o4_trace,
        agent_id=agent_id,
        body_id=body_id,
        agent_slot=ctx.get("agent_slot"),
        run_id=run_id,
        runtime_generation=gen,
        decision_tick=int(decision_tick) if decision_tick is not None else None,
    )
    prev = st.latest_by_agent.get(agent_id)
    if (
        isinstance(prev, dict)
        and prev.get("trace_id") == tr.get("trace_id")
        and prev.get("observation_tick") == tr.get("observation_tick")
    ):
        st.deduplicated_count += 1
        return prev

    # latest_exact survives FIFO eviction
    st.latest_by_agent[agent_id] = tr
    st.history.append({
        "trace_id": tr.get("trace_id"),
        "agent_id": agent_id,
        "body_id": body_id,
        "observation_tick": tr.get("observation_tick"),
        "runtime_generation": gen,
        "accepted_count": tr.get("accepted_count"),
        "availability": "AVAILABLE",
    })
    st.capture_count += 1
    st.last_capture_tick = tr.get("observation_tick")
    while len(st.history) > int(st.capacity):
        st.history.pop(0)
        st.evicted_count += 1
    return tr


def latest_exact_trace(
    world: Any,
    agent_id: str,
    *,
    runtime_generation: int | None = None,
    body_id: str | None = None,
) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    tr = st.latest_by_agent.get(str(agent_id))
    if not isinstance(tr, dict):
        return None
    if runtime_generation is not None and tr.get("runtime_generation") is not None:
        if int(tr["runtime_generation"]) != int(runtime_generation):
            return None
    if body_id is not None and tr.get("body_id") is not None:
        if str(tr["body_id"]) != str(body_id):
            return None
    return tr


def _missing_payload(
    *,
    reason: str,
    agent_id: str,
    runtime_generation: int | None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out = {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "classification": CLASSIFICATION,
        "available": False,
        "missing_reason": reason,
        "selected_agent_id": str(agent_id),
        "runtime_generation": runtime_generation,
        "latest": None,
        "banner": list(BANNER_LINES),
        "researcher_only": True,
        "cognition_exposed": False,
        "render_as_darkness_forbidden": True,
        "true_zero_distinct_from_missing": True,
        "vw7_pixels_used": False,
    }
    if extra:
        out.update(extra)
    return out


def _latest_exact_by_agent_map(
    world: Any,
    *,
    runtime_generation: int | None = None,
    body_id: str | None = None,
) -> dict[str, Any]:
    """Read-only copies of existing per-agent latest traces. Never creates traces."""
    st = state_of(world)
    out: dict[str, Any] = {}
    if st is None:
        return out
    for aid in sorted(st.latest_by_agent.keys()):
        tr = latest_exact_trace(
            world, str(aid), runtime_generation=runtime_generation, body_id=body_id
        )
        if tr is not None:
            out[str(aid)] = copy.deepcopy(tr)
    return out


def observer_payload(
    world: Any,
    *,
    selected_agent_id: str | None = None,
    runtime_generation: int | None = None,
    body_id: str | None = None,
    historical_trace_id: str | None = None,
    include_latest_by_agent: bool = False,
) -> dict[str, Any]:
    """Read-only Observer payload. Never creates traces."""
    st = state_of(world)
    aid = str(selected_agent_id or "agent_0")
    if historical_trace_id:
        # Historical selection: search history index only (may be evicted)
        found = None
        if st is not None:
            for h in reversed(st.history):
                if h.get("trace_id") == historical_trace_id and str(h.get("agent_id")) == aid:
                    found = h
                    break
        if found is None:
            return _missing_payload(
                reason=REASON_TRACE_EVICTED_HISTORICAL_SELECTION,
                agent_id=aid,
                runtime_generation=runtime_generation,
                extra={"requested_trace_id": historical_trace_id},
            )

    tr = latest_exact_trace(world, aid, runtime_generation=runtime_generation, body_id=body_id)
    if tr is None:
        # Distinguish never captured vs generation mismatch vs body mismatch
        if st is not None and aid in st.latest_by_agent:
            other = st.latest_by_agent.get(aid)
            if isinstance(other, dict):
                if (
                    runtime_generation is not None
                    and other.get("runtime_generation") is not None
                    and int(other["runtime_generation"]) != int(runtime_generation)
                ):
                    miss = _missing_payload(
                        reason=REASON_RUNTIME_GENERATION_MISMATCH,
                        agent_id=aid,
                        runtime_generation=runtime_generation,
                    )
                    if include_latest_by_agent:
                        miss["latest_exact_by_agent"] = _latest_exact_by_agent_map(
                            world, runtime_generation=runtime_generation, body_id=body_id
                        )
                        miss["latest_exact_by_agent_included"] = True
                    else:
                        miss["latest_exact_by_agent_included"] = False
                    return miss
                if body_id is not None and str(other.get("body_id")) != str(body_id):
                    miss = _missing_payload(
                        reason=REASON_AGENT_BODY_IDENTITY_MISMATCH,
                        agent_id=aid,
                        runtime_generation=runtime_generation,
                    )
                    if include_latest_by_agent:
                        miss["latest_exact_by_agent"] = _latest_exact_by_agent_map(
                            world, runtime_generation=runtime_generation, body_id=body_id
                        )
                        miss["latest_exact_by_agent_included"] = True
                    else:
                        miss["latest_exact_by_agent_included"] = False
                    return miss
        # O4 may be inactive / not yet observed
        o4_last = getattr(world, "_o4_last_reception_trace", None)
        if not isinstance(o4_last, dict):
            miss = _missing_payload(
                reason=REASON_NO_O4_TRACE_YET,
                agent_id=aid,
                runtime_generation=runtime_generation,
                extra={
                    "capture_count": int(st.capture_count) if st else 0,
                    "evicted_count": int(st.evicted_count) if st else 0,
                },
            )
            if include_latest_by_agent:
                miss["latest_exact_by_agent"] = _latest_exact_by_agent_map(
                    world, runtime_generation=runtime_generation, body_id=body_id
                )
                miss["latest_exact_by_agent_included"] = True
            else:
                miss["latest_exact_by_agent_included"] = False
            return miss
        miss = _missing_payload(
            reason=REASON_CURRENT_OBSERVATION_NOT_CAPTURED,
            agent_id=aid,
            runtime_generation=runtime_generation,
            extra={
                "capture_count": int(st.capture_count) if st else 0,
                "evicted_count": int(st.evicted_count) if st else 0,
                "note": "O4 world stash exists but no scientific FPV capture for this agent",
            },
        )
        if include_latest_by_agent:
            miss["latest_exact_by_agent"] = _latest_exact_by_agent_map(
                world, runtime_generation=runtime_generation, body_id=body_id
            )
            miss["latest_exact_by_agent_included"] = True
        else:
            miss["latest_exact_by_agent_included"] = False
        return miss

    if tr.get("o4_schema") and str(tr.get("o4_schema")) not in (O4_SCHEMA, str(tr.get("o4_schema"))):
        return _missing_payload(
            reason=REASON_INCOMPATIBLE_PROFILE,
            agent_id=aid,
            runtime_generation=runtime_generation,
        )

    hist_idx = []
    if st is not None:
        for h in st.history:
            if str(h.get("agent_id")) != aid:
                continue
            if runtime_generation is not None and h.get("runtime_generation") is not None:
                if int(h["runtime_generation"]) != int(runtime_generation):
                    continue
            hist_idx.append(dict(h))

    out = {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "classification": CLASSIFICATION,
        "available": True,
        "missing_reason": None,
        "selected_agent_id": aid,
        "runtime_generation": runtime_generation if runtime_generation is not None else tr.get("runtime_generation"),
        "latest": tr,
        "latest_exact_trace_per_agent": True,
        "history_index": hist_idx[-16:],
        "capture_count": int(st.capture_count) if st else 0,
        "evicted_count": int(st.evicted_count) if st else 0,
        "deduplicated_count": int(st.deduplicated_count) if st else 0,
        "capacity": int(st.capacity) if st else HISTORY_CAPACITY_DEFAULT,
        "agents_with_latest": sorted(st.latest_by_agent.keys()) if st else [],
        "banner": list(BANNER_LINES),
        "display_band_transform": DISPLAY_BAND_TRANSFORM,
        "display_band_transform_physical_authority": DISPLAY_BAND_TRANSFORM_PHYSICAL_AUTHORITY,
        "researcher_only": True,
        "cognition_exposed": False,
        "render_as_darkness_forbidden": True,
        "true_zero_distinct_from_missing": True,
        "vw7_pixels_used": False,
        "frontend_raycast_forbidden": True,
        "smoothing_default_off": True,
        "latest_exact_by_agent_included": bool(include_latest_by_agent),
    }
    if include_latest_by_agent:
        # Researcher dual-monitor delivery only — copies existing latests; never captures.
        out["latest_exact_by_agent"] = _latest_exact_by_agent_map(
            world, runtime_generation=runtime_generation, body_id=body_id
        )
    return out


def profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "classification": CLASSIFICATION,
    }


def serialize_state(st: ReceptorGroundedFpvState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "researcher_configuration": True,
        "physical_state": False,
        "capacity": int(st.capacity),
        "history": list(st.history),
        "latest_by_agent": {k: copy.deepcopy(v) for k, v in st.latest_by_agent.items()},
        "evicted_count": int(st.evicted_count),
        "capture_count": int(st.capture_count),
        "deduplicated_count": int(st.deduplicated_count),
        "runtime_generation": st.runtime_generation,
        "last_capture_tick": st.last_capture_tick,
        "no_replay_into_cognition": True,
    }


def restore_state(world: Any, data: dict[str, Any] | None) -> ReceptorGroundedFpvState | None:
    """Restore researcher state only. Does not create a new observation/trace event."""
    if not data:
        return None
    if str(data.get("schema_version") or "") not in (STATE_SCHEMA, SCHEMA):
        return None
    latest = {}
    raw_latest = data.get("latest_by_agent") or {}
    if isinstance(raw_latest, dict):
        for k, v in raw_latest.items():
            if isinstance(v, dict):
                latest[str(k)] = dict(v)
    st = ReceptorGroundedFpvState(
        capacity=int(data.get("capacity") or HISTORY_CAPACITY_DEFAULT),
        history=[dict(h) for h in (data.get("history") or []) if isinstance(h, dict)],
        latest_by_agent=latest,
        evicted_count=int(data.get("evicted_count") or 0),
        capture_count=int(data.get("capture_count") or 0),
        deduplicated_count=int(data.get("deduplicated_count") or 0),
        runtime_generation=data.get("runtime_generation"),
        last_capture_tick=data.get("last_capture_tick"),
    )
    setattr(world, WORLD_ATTR, st)
    return st


def privacy_tokens() -> tuple[str, ...]:
    return PRIVACY_DENYLIST
