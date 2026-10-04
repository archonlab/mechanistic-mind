"""Analyzer reconstruction for elevation / excavation / free-space visualization story.

Display-aware. Does not invent elevation from pixels. Does not implement Analyzer progress bar.
"""
from __future__ import annotations

from typing import Any


SECTION_TITLE = "ELEVATION / EXCAVATION / FREE-SPACE STORY"
TRAJECTORY_SECTION = "VERTICAL TRAJECTORIES"
UNAVAILABLE = "ELEVATION VISUALIZATION NOT AVAILABLE FOR THIS RUN"
TRAIL_UNAVAILABLE = "FULL VERTICAL TRAIL NOT AVAILABLE FOR THIS RUN"
ANALYZER_PROGRESS_BAR_STATUS = "TEXT_STATUS_ONLY"


def summarize_elevation_free_space_story(
    *,
    vertical_display: dict[str, Any] | None = None,
    release_receipts: list[dict[str, Any]] | None = None,
    support_loss_receipts: list[dict[str, Any]] | None = None,
    landing_receipts: list[dict[str, Any]] | None = None,
    acoustic_receipts: list[dict[str, Any]] | None = None,
    sparse_deltas: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    vd = vertical_display if isinstance(vertical_display, dict) else None
    elev_available = bool(
        vd
        and str(vd.get("schema_version") or "").startswith("OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1")
        and isinstance((vd.get("cell_centre_elevation") or {}).get("data"), list)
    )
    trail_segs = list((vd or {}).get("trail_segments") or [])
    trail_available = bool(trail_segs)
    releases = list(release_receipts or [])
    losses = list(support_loss_receipts or [])
    landings = list(landing_receipts or [])
    acoustics = list(acoustic_receipts or [])
    deltas = list(sparse_deltas or (vd.get("sparse_deltas") if vd else []) or [])

    excavation_story: list[str] = []
    if elev_available:
        excavation_story.append("terrain_baseline")
        if deltas:
            excavation_story.append("conservative_removal")
            excavation_story.append("sparse_delta_current_elevation")
        if any(
            (e or {}).get("detached_terrain_provenance")
            for e in (vd.get("entities_vertical") or [])
        ):
            excavation_story.append("detached_resource_object")
        if losses:
            excavation_story.append("support_loss_z_unchanged")
            excavation_story.append("later_descent_if_frames_present")
        if landings:
            excavation_story.append("v1b_landing")
        if acoustics:
            excavation_story.append("v1c_physical_signal")
    else:
        excavation_story.append("elevation_payload_unavailable")

    release_story: list[str] = []
    if releases:
        release_story.extend(
            ["HELD", "RELEASE", "T+1_eligibility", "unsupported_fall_if_frames", "landing_if_present", "physical_signal_if_present"]
        )
    elif not elev_available and not losses and not landings:
        release_story.append("unavailable")

    trajectory_summaries = []
    for seg in trail_segs[:8]:
        trajectory_summaries.append(
            {
                "entity_id": seg.get("entity_id"),
                "start_reason": seg.get("start_reason"),
                "start_tick": seg.get("start_tick"),
                "end_tick": seg.get("end_tick"),
                "end_reason": seg.get("end_reason"),
                "sample_count": seg.get("sample_count"),
                "z_min": seg.get("z_min"),
                "z_max": seg.get("z_max"),
                "clearance_min": seg.get("clearance_min"),
                "clearance_max": seg.get("clearance_max"),
                "release_tick": seg.get("release_tick"),
                "support_loss_tick": seg.get("support_loss_tick"),
                "landing_tick": seg.get("landing_tick"),
                "acoustic_tick": seg.get("acoustic_tick"),
                "full_trail_evidence": bool(seg.get("sample_count")),
            }
        )

    missing: list[str] = []
    if not elev_available:
        missing.append(UNAVAILABLE)
    if not trail_available:
        missing.append(TRAIL_UNAVAILABLE)
    if not releases:
        missing.append("RELEASE_RECEIPTS_UNAVAILABLE")
    if not losses:
        missing.append("SUPPORT_LOSS_RECEIPTS_UNAVAILABLE")
    if not landings:
        missing.append("LANDING_RECEIPTS_UNAVAILABLE")
    if not acoustics:
        missing.append("ACOUSTIC_RECEIPTS_UNAVAILABLE")

    return {
        "section": SECTION_TITLE,
        "trajectory_section": TRAJECTORY_SECTION,
        "elevation_visualization_available": elev_available,
        "vertical_trail_available": trail_available,
        "unavailable_label": None if elev_available else UNAVAILABLE,
        "trail_unavailable_label": None if trail_available else TRAIL_UNAVAILABLE,
        "excavation_causal_story": excavation_story,
        "release_causal_story": release_story,
        "vertical_trajectories": trajectory_summaries,
        "sparse_delta_count": len(deltas),
        "release_count": len(releases),
        "support_loss_count": len(losses),
        "landing_count": len(landings),
        "acoustic_count": len(acoustics),
        "missing_frame_evidence": missing,
        "analyzer_progress_bar_status": ANALYZER_PROGRESS_BAR_STATUS,
        "fabricated_from_pixels": False,
        "fabricated_trail_interpolation": False,
        "researcher_only": True,
    }


def format_elevation_free_space_section(summary: dict[str, Any]) -> str:
    lines = [SECTION_TITLE, TRAJECTORY_SECTION, f"progress_bar={ANALYZER_PROGRESS_BAR_STATUS}"]
    if not summary.get("elevation_visualization_available"):
        lines.append(UNAVAILABLE)
    if not summary.get("vertical_trail_available"):
        lines.append(TRAIL_UNAVAILABLE)
    lines.append("excavation: " + " → ".join(summary.get("excavation_causal_story") or []))
    lines.append("release: " + " → ".join(summary.get("release_causal_story") or []))
    for t in summary.get("vertical_trajectories") or []:
        lines.append(
            f"trail {t.get('entity_id')}: {t.get('start_reason')}@{t.get('start_tick')} → "
            f"{t.get('end_reason') or 'active'}@{t.get('end_tick')} n={t.get('sample_count')}"
        )
    missing = summary.get("missing_frame_evidence") or []
    if missing:
        lines.append("missing: " + "; ".join(missing))
    return "\n".join(lines)


def elevation_free_space_story_from_world(world: Any) -> dict[str, Any]:
    vd = getattr(world, "vertical_display", None)
    # Prefer live mechanism histories when present.
    v1d = getattr(world, "release_and_excavation_support_loss_integration_state", None)
    hist = list(getattr(v1d, "history", None) or []) if v1d is not None else []
    releases = [r for r in hist if str(r.get("event_class")) == "RELEASE_ENTRY"]
    losses = [r for r in hist if str(r.get("event_class")) == "SUPPORT_LOST"]
    v1b = getattr(world, "vertical_terrain_landing_contact_response_state", None)
    landings = [
        r for r in list(getattr(v1b, "history", None) or [])
        if isinstance(r, dict) and bool(r.get("response_applied"))
    ] if v1b is not None else []
    v1c = getattr(world, "vertical_impact_acoustic_emission_state", None)
    acoustics = [
        r for r in list(getattr(v1c, "history", None) or [])
        if isinstance(r, dict) and r.get("emitted") is not False and not r.get("silence_reason")
    ] if v1c is not None else []
    return summarize_elevation_free_space_story(
        vertical_display=vd if isinstance(vd, dict) else None,
        release_receipts=releases,
        support_loss_receipts=losses,
        landing_receipts=landings,
        acoustic_receipts=acoustics,
    )
