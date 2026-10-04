"""Analyzer reconstruction for SELECTED_ORGANISM_PHYSICAL_FIELD_COMPARISON_SAV3_V1."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.selected_organism_physical_field_comparison import (
    AUTHORITY,
    CAPABILITY,
    LEGACY_UNAVAILABLE,
    PROFILE,
    SCHEMA,
    TITLE,
    WARNING,
    profile_reference,
)
from mechanistic_mind.scientific_v3.organism_auditory_transformation_trace_summary import (
    summarize_organism_auditory_transformation_traces,
)


def summarize_sav3_comparison(
    traces: list[dict[str, Any]] | None = None,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """SAV3 Analyzer view: interpretation over exact transformation traces."""
    base = summarize_organism_auditory_transformation_traces(traces, meta=meta)
    if not base.get("available"):
        return {
            "schema": SCHEMA,
            "capability": CAPABILITY,
            "profile": PROFILE,
            "authority": AUTHORITY,
            "title": TITLE,
            "warning_label": WARNING,
            "available": False,
            "status": LEGACY_UNAVAILABLE,
            "authoritative_input": "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1",
            "playback_affected_simulation": False,
            "mind_reading": False,
            "causal_reconstruction": (
                "legacy/missing transformation traces → SAV3 comparison unavailable "
                "(do not invert A5; do not use passive probe)"
            ),
            "progress": base.get("progress") or {
                "mode": "UNAVAILABLE",
                "completed": 0,
                "total": 0,
                "percent": None,
                "note": "No traces — do not fabricate progress",
            },
            "trace_summary": base,
        }

    total = int(base.get("trace_count") or 0)
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "title": TITLE,
        "warning_label": WARNING,
        "available": True,
        "status": "SAV3_TRACE_EVIDENCE_PRESENT",
        "authoritative_input": "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1",
        "profile_reference": profile_reference(),
        "agent_ids": base.get("agent_ids"),
        "body_ids": base.get("body_ids"),
        "trace_count": total,
        "linked_complete": base.get("linked_complete"),
        "mismatch_anomalies": base.get("mismatch_anomalies"),
        "observation_tick_range": base.get("observation_tick_range"),
        "reception_tick_range": base.get("reception_tick_range"),
        "causal_delay_note": "A3→A5 causal_delay_ticks recorded per trace (expect 0)",
        "a3_value_range": base.get("a3_value_range"),
        "a5_value_range": base.get("a5_value_range"),
        "clipping_count_sum": base.get("clipping_count_sum"),
        "max_transform_residual": base.get("max_transform_residual"),
        "history_evictions": base.get("history_evictions"),
        "orphaned_pending": base.get("orphaned_pending"),
        "authority_classes": base.get("authority_classes"),
        "a2_gate_status": "PARTIAL_METADATA",
        "contributor_decomposition": "NOT_AVAILABLE_AFTER_SUMMATION",
        "passive_probe_authority": False,
        "playback_affected_simulation": False,
        "mind_reading": False,
        "preview": base.get("preview"),
        "progress": {
            "mode": "FINITE_TRACE_SCAN",
            "completed": total,
            "total": total,
            "percent": 100.0 if total else None,
            "note": "processed traces / total traces",
        },
        "trace_summary": base,
    }


def format_sav3_comparison_section(summary: dict[str, Any]) -> str:
    if not summary.get("available"):
        return (
            f"## {TITLE}\n"
            f"Status: {summary.get('status')}\n"
            f"{summary.get('causal_reconstruction')}\n"
        )
    return (
        f"## {TITLE} ({SCHEMA})\n"
        f"Warning: {WARNING}\n"
        f"Traces: {summary.get('trace_count')} · linked: {summary.get('linked_complete')} · "
        f"mismatches: {summary.get('mismatch_anomalies')}\n"
        f"Agents: {summary.get('agent_ids')}\n"
        f"A3 range: {summary.get('a3_value_range')} · A5 range: {summary.get('a5_value_range')}\n"
        f"Max residual: {summary.get('max_transform_residual')} · "
        f"Clip sum: {summary.get('clipping_count_sum')}\n"
        f"Progress: {summary.get('progress')}\n"
        f"Authority: {AUTHORITY}\n"
        f"A2 gate: PARTIAL · contributor decomposition: UNAVAILABLE AFTER SUMMATION\n"
    )
