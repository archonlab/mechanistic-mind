"""Analyzer summary for ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system.organism_auditory_transformation_trace import (
    A3_BOUNDARY,
    A4_TRANSFORM,
    AUTHORITY,
    LEGACY_UNAVAILABLE,
    PROFILE,
    SCHEMA,
    TARGET_A5_SCHEMA,
    profile_reference,
)


def summarize_organism_auditory_transformation_traces(
    traces: list[dict[str, Any]] | None = None,
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    traces = [t for t in (traces or []) if isinstance(t, dict)]
    meta = dict(meta or {})
    if not traces:
        return {
            "schema": SCHEMA,
            "profile": PROFILE,
            "a3_boundary": A3_BOUNDARY,
            "a4_transform": A4_TRANSFORM,
            "target_a5_schema": TARGET_A5_SCHEMA,
            "authority": AUTHORITY,
            "available": False,
            "status": LEGACY_UNAVAILABLE,
            "playback_affected_simulation": False,
            "mind_reading": False,
            "progress": {
                "mode": "UNAVAILABLE",
                "completed": 0,
                "total": 0,
                "percent": None,
                "note": "No transformation traces — do not fabricate progress",
            },
            "causal_reconstruction": (
                "legacy/missing A3 traces → A3/A4 comparison unavailable "
                "(A5/SAV1 may still exist; do not invert A5→A3)"
            ),
        }

    total = len(traces)
    agents = sorted({str(t.get("agent_id")) for t in traces if t.get("agent_id")})
    bodies = sorted({str(t.get("body_id")) for t in traces if t.get("body_id")})
    obs_ticks = [int(t.get("observation_tick", -1)) for t in traces]
    recv_ticks = [int(t.get("reception_tick", -1)) for t in traces]
    linked = sum(1 for t in traces if t.get("completion_status") == "LINKED_COMPLETE")
    mismatch = sum(
        1 for t in traces if t.get("completion_status") == "A3_A4_A5_TRANSFORM_MISMATCH"
    )
    max_res = 0.0
    clip_total = 0
    a3_vals: list[float] = []
    a5_vals: list[float] = []
    for t in traces:
        a3 = t.get("a3") or {}
        a4 = t.get("a4") or {}
        a5 = t.get("a5") or {}
        for v in list(a3.get("left_receptor_band_energy") or []) + list(
            a3.get("right_receptor_band_energy") or []
        ):
            a3_vals.append(float(v))
        for v in list(a5.get("left_receptor_channels") or []) + list(
            a5.get("right_receptor_channels") or []
        ):
            a5_vals.append(float(v))
        clip_total += int(a4.get("clipping_count") or 0)
        resid = (a4.get("transform_residual") or {}).get("max_abs_residual")
        if resid is not None:
            max_res = max(max_res, float(resid))

    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "a3_boundary": A3_BOUNDARY,
        "a4_transform": A4_TRANSFORM,
        "target_a5_schema": TARGET_A5_SCHEMA,
        "authority": AUTHORITY,
        "available": True,
        "status": "TRACES_PRESENT",
        "profile_reference": profile_reference(),
        "agent_ids": agents,
        "body_ids": bodies,
        "trace_count": total,
        "linked_complete": linked,
        "mismatch_anomalies": mismatch,
        "observation_tick_range": [min(obs_ticks), max(obs_ticks)] if obs_ticks else None,
        "reception_tick_range": [min(recv_ticks), max(recv_ticks)] if recv_ticks else None,
        "a3_value_range": [min(a3_vals), max(a3_vals)] if a3_vals else None,
        "a5_value_range": [min(a5_vals), max(a5_vals)] if a5_vals else None,
        "clipping_count_sum": clip_total,
        "max_transform_residual": max_res,
        "history_evictions": int(meta.get("evicted_count", 0) or 0),
        "orphaned_pending": int(meta.get("orphaned_count", 0) or 0),
        "authority_classes": {
            "a3": "AUTHORITATIVE_PHYSICAL_RECEPTOR_STATE_RESEARCHER_ONLY",
            "a4": "DETERMINISTIC_RESEARCHER_DERIVATION",
            "a5": "AUTHORITATIVE_ORGANISM_ACCESSIBLE_OBSERVATION",
            "provenance": "RESEARCHER_ONLY",
        },
        "preview": traces[:16],
        "playback_affected_simulation": False,
        "mind_reading": False,
        "progress": {
            "mode": "FINITE_TRACE_SCAN",
            "completed": total,
            "total": total,
            "percent": 100.0 if total else None,
            "note": "processed traces / total traces",
        },
    }


def format_organism_auditory_transformation_trace_section(summary: dict[str, Any]) -> str:
    if not summary.get("available"):
        return (
            f"## Organism auditory transformation trace\n"
            f"Status: {summary.get('status')}\n"
            f"{summary.get('causal_reconstruction')}\n"
        )
    return (
        f"## Organism auditory transformation trace ({SCHEMA})\n"
        f"Traces: {summary.get('trace_count')} · linked: {summary.get('linked_complete')} · "
        f"mismatches: {summary.get('mismatch_anomalies')}\n"
        f"Agents: {summary.get('agent_ids')}\n"
        f"Obs ticks: {summary.get('observation_tick_range')} · "
        f"Recv ticks: {summary.get('reception_tick_range')}\n"
        f"Max residual: {summary.get('max_transform_residual')} · "
        f"Clip sum: {summary.get('clipping_count_sum')}\n"
        f"Progress: {summary.get('progress')}\n"
        f"Authority: {AUTHORITY}\n"
    )


def transformation_traces_from_consequences(run_dir: Path | str) -> list[dict[str, Any]]:
    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    cons = root / "consequences.jsonl"
    if not cons.is_file():
        return out
    import json

    for line in cons.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if not isinstance(row, dict):
            continue
        for ref in list(row.get("event_refs") or []):
            if not isinstance(ref, dict):
                continue
            if ref.get("kind") == "ORGANISM_AUDITORY_TRANSFORMATION_TRACE" or (
                str(ref.get("schema") or "") == SCHEMA
            ):
                out.append(dict(ref))
    return out
