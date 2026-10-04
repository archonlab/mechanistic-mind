"""SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1 — researcher comparison view.

Read-only presentation over ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1.
Does not capture, recompute LPS/phenotype, or alter A5/SAV1/playback.
"""
from __future__ import annotations

from typing import Any

SCHEMA = "SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1"
CAPABILITY = "selected_organism_physical_field_comparison"
PROFILE = "A3_TO_A5_CAUSAL_COMPARISON_SAV3_V1"
AUTHORITY = "RESEARCHER_COMPARISON_OVER_AUTHORITATIVE_TRACE"
TITLE = "PHYSICAL FIELD → ORGANISM RECEPTORS"
WARNING = (
    "RESEARCHER CAUSAL COMPARISON · ONLY A5 IS ORGANISM-ACCESSIBLE · "
    "NOT SUBJECTIVE EXPERIENCE"
)
LEGACY_UNAVAILABLE = "SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_UNAVAILABLE_LEGACY_EVIDENCE"
EXPERIMENTER_NA = "EXPERIMENTER_AUDITORY_COMPARISON_NOT_AVAILABLE"

STATUS_TRACE_AVAILABLE = "TRACE_AVAILABLE"
STATUS_NOT_YET = "TRACE_NOT_YET_AVAILABLE"
STATUS_MISMATCH = "TRACE_MISMATCH"
STATUS_A5_LINK_UNAVAILABLE = "A5_LINK_UNAVAILABLE"
STATUS_BODY_UNAVAILABLE = "SELECTED_BODY_UNAVAILABLE"
STATUS_LEGACY = "LEGACY_TRACE_UNAVAILABLE"
STATUS_INCOMPATIBLE = "INCOMPATIBLE_TRACE_PROFILE"

TRACE_SCHEMA = "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1"
TRACE_PROFILE = "AUDITORY_A3_TO_A5_TRANSFORMATION_TRACE_V1"

A3_BADGE = "AUTHORITATIVE PHYSICAL RECEPTOR STATE · RESEARCHER-ONLY"
A4_BADGE = "DETERMINISTIC RESEARCHER VERIFICATION"
A5_BADGE = "AUTHORITATIVE ORGANISM-ACCESSIBLE OBSERVATION"
RENDER_BADGE = "DISPLAY-DERIVED · NOT SCIENTIFIC STATE"


def profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "title": TITLE,
        "warning": WARNING,
        "authoritative_input": TRACE_SCHEMA,
        "trace_profile_required": TRACE_PROFILE,
        "playback": False,
        "physical_mechanism": False,
        "researcher_only": True,
        "agent_accessible": False,
        "badges": {
            "a3": A3_BADGE,
            "a4": A4_BADGE,
            "a5": A5_BADGE,
            "render": RENDER_BADGE,
        },
        "legacy_policy": LEGACY_UNAVAILABLE,
        "experimenter_policy": EXPERIMENTER_NA,
    }


def _classify_trace(tr: dict[str, Any] | None) -> str:
    if not isinstance(tr, dict):
        return STATUS_NOT_YET
    if str(tr.get("schema") or "") not in ("", TRACE_SCHEMA) and tr.get("schema"):
        if str(tr.get("schema")) != TRACE_SCHEMA:
            return STATUS_INCOMPATIBLE
    prof = tr.get("profile")
    if prof is not None and str(prof) != TRACE_PROFILE:
        return STATUS_INCOMPATIBLE
    status = str(tr.get("completion_status") or "")
    if status == "EXPERIMENTER_AUDITORY_TRANSFORMATION_TRACE_NOT_AVAILABLE":
        return EXPERIMENTER_NA
    if status == "A3_A4_A5_TRANSFORM_MISMATCH":
        return STATUS_MISMATCH
    if status == "A5_UNAVAILABLE":
        return STATUS_A5_LINK_UNAVAILABLE
    if status in ("LINKED_COMPLETE", "A3_A4_A5_TRANSFORM_MISMATCH"):
        return STATUS_TRACE_AVAILABLE if status == "LINKED_COMPLETE" else STATUS_MISMATCH
    if status == "LINKED_COMPLETE":
        return STATUS_TRACE_AVAILABLE
    if tr.get("a5") and tr.get("a3"):
        return STATUS_TRACE_AVAILABLE if status in ("", "LINKED_COMPLETE", "AVAILABLE") else status or STATUS_TRACE_AVAILABLE
    return STATUS_NOT_YET


def observer_comparison_payload(
    world: Any,
    *,
    selected_agent_id: str | None = None,
    selected_body_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Serialize selected-agent latest trace + history meta for SAV3 UI.

    Points at ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1 authority; does not copy
    a second scientific history store.
    """
    from mechanistic_mind.physical_system.organism_auditory_transformation_trace import (
        LEGACY_UNAVAILABLE as TRACE_LEGACY,
        state_of,
    )

    base = {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "title": TITLE,
        "warning_label": WARNING,
        "authoritative_input": TRACE_SCHEMA,
        "researcher_only": True,
        "agent_accessible": False,
        "playback": False,
        "mind_reading": False,
        "selected_agent_id": selected_agent_id,
        "selected_body_id": selected_body_id,
        "run_id_filter": run_id,
        "badges": {
            "a3": A3_BADGE,
            "a4": A4_BADGE,
            "a5": A5_BADGE,
            "render": RENDER_BADGE,
        },
        "a2_gate_status": "A2 BODY-CENTRE ACCEPTANCE GATE: PARTIAL METADATA",
        "contributor_decomposition_status": (
            "CONTRIBUTOR DECOMPOSITION NOT AVAILABLE AFTER SUMMATION"
        ),
        "passive_probe_note": (
            "PASSIVE PROBE IS AN INDEPENDENT RESEARCHER SAMPLE · NOT SAV3 AUTHORITY"
        ),
        "legacy_policy": LEGACY_UNAVAILABLE,
        "experimenter_policy": EXPERIMENTER_NA,
        "a5_scale_policy": "[0,1]_FIXED",
        "a3_scale_policy": "CLIP_BOUND_PLUS_OVERFLOW_MARK",
        "per_trace_normalization": False,
        "automatic_display_gain": False,
    }

    st = state_of(world)
    if st is None:
        return {
            **base,
            "status": STATUS_LEGACY,
            "availability": LEGACY_UNAVAILABLE,
            "latest_for_selected": None,
            "recent_for_selected": [],
            "history_capacity": 0,
            "retained_count": 0,
            "evicted_count": 0,
            "mismatch_count": 0,
            "completed_count": 0,
            "trace_active": False,
            "trace_legacy": TRACE_LEGACY,
        }

    traces = list(st.traces)
    by_agent: list[dict[str, Any]] = []
    for tr in traces:
        if not isinstance(tr, dict):
            continue
        if selected_agent_id is not None and str(tr.get("agent_id") or "") != str(selected_agent_id):
            continue
        if run_id is not None and tr.get("run_id") is not None and str(tr.get("run_id")) != str(run_id):
            continue
        by_agent.append(tr)

    # Prefer agent+body match when body identity is known; else agent-only (SAV1 parity).
    filtered = by_agent
    if selected_body_id and str(selected_body_id) not in ("", "null", "None"):
        body_hits = [
            tr for tr in by_agent
            if str(tr.get("body_id") or "") == str(selected_body_id)
        ]
        if body_hits:
            filtered = body_hits

    latest = filtered[-1] if filtered else None
    status = _classify_trace(latest) if latest else STATUS_NOT_YET
    if (
        selected_agent_id
        and str(selected_agent_id).lower() in ("experimenter", "exp")
        and latest is None
    ):
        status = EXPERIMENTER_NA

    return {
        **base,
        "status": status,
        "availability": status,
        "latest_for_selected": latest,
        "recent_for_selected": filtered[-12:],
        "history_capacity": int(st.capacity),
        "retained_count": len(traces),
        "selected_retained_count": len(filtered),
        "evicted_count": int(st.evicted_count),
        "mismatch_count": int(st.mismatch_count),
        "completed_count": int(st.completed_count),
        "orphaned_count": int(st.orphaned_count),
        "deduplicated_count": int(st.deduplicated_count),
        "last_trace_id": st.last_trace_id,
        "trace_active": True,
        "formula": "A5 = clip(A3 / sensor_scale, lower, upper)",
    }
