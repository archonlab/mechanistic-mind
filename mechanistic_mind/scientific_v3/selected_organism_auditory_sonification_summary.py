"""Analyzer reconstruction for SELECTED_ORGANISM_AUDITORY_SONIFICATION_V1."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.selected_organism_auditory_sonification import (
    AMPLITUDE_MAPPING,
    BAND_COUNT,
    CARRIER_LABEL,
    CHANNEL_MODE,
    FIXED_RECEPTOR_GAIN,
    INPUT_BOUNDARY,
    LEGACY_UNAVAILABLE,
    LISTENING_MODE_OWNERSHIP,
    MODE_LABEL,
    PLAYBACK_AUTHORITY_CLASS,
    PROFILE,
    SCHEMA,
    WARNING_LABEL,
    map_receptor_activation,
    sav2_profile_reference,
)


def summarize_selected_organism_auditory_sonification(
    sav1_receipts: list[dict[str, Any]] | None = None,
    *,
    playback_provenance: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    receipts = [r for r in (sav1_receipts or []) if isinstance(r, dict)]
    prov = [p for p in (playback_provenance or []) if isinstance(p, dict)]
    meta = dict(meta or {})

    if not receipts and not prov:
        return {
            "schema": SCHEMA,
            "profile": PROFILE,
            "mode_label": MODE_LABEL,
            "warning_label": WARNING_LABEL,
            "available": False,
            "status": LEGACY_UNAVAILABLE,
            "authority_class": PLAYBACK_AUTHORITY_CLASS,
            "physical_evidence_affected": False,
            "playback_affected_simulation": False,
            "mind_reading": False,
            "progress": {
                "mode": "UNAVAILABLE",
                "completed": 0,
                "total": 0,
                "percent": None,
                "note": "No SAV1 receipts or SAV2 provenance — do not fabricate progress",
            },
            "section_title": MODE_LABEL,
            "causal_reconstruction": (
                "legacy/missing SAV1 A5 evidence → SAV2 unavailable "
                "(not reconstructed from stream/probe/cognition)"
            ),
        }

    schedule = []
    agents: set[str] = set()
    selection_changes = 0
    prev_agent = None
    for i, r in enumerate(receipts):
        if str(r.get("availability") or "") != "AVAILABLE":
            continue
        a = r.get("section_a_organism_accessible") or {}
        left = list(a.get("left_receptor_channels") or [])
        right = list(a.get("right_receptor_channels") or [])
        # Section B must not influence amplitudes
        mapped = map_receptor_activation(left, right)
        agent = str(r.get("agent_id") or "")
        if agent:
            agents.add(agent)
        if prev_agent is not None and agent and agent != prev_agent:
            selection_changes += 1
        if agent:
            prev_agent = agent
        schedule.append(
            {
                "index": i,
                "receipt_id": r.get("receipt_id"),
                "scientific_tick": r.get("scientific_tick"),
                "agent_id": agent,
                "body_id": r.get("body_id"),
                "left_input": left,
                "right_input": right,
                "left_amplitudes": mapped["left_amplitudes"],
                "right_amplitudes": mapped["right_amplitudes"],
                "authority_class": PLAYBACK_AUTHORITY_CLASS,
            }
        )

    total = len(prov) if prov else len(schedule)
    completed = total
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "mode_label": MODE_LABEL,
        "warning_label": WARNING_LABEL,
        "available": True,
        "status": "SAV2_SCHEDULE_RECONSTRUCTIBLE",
        "authority_class": PLAYBACK_AUTHORITY_CLASS,
        "input_boundary": INPUT_BOUNDARY,
        "sav2_reference": sav2_profile_reference(),
        "carrier_label": CARRIER_LABEL,
        "channel_mode": CHANNEL_MODE,
        "amplitude_mapping": AMPLITUDE_MAPPING,
        "fixed_receptor_gain": FIXED_RECEPTOR_GAIN,
        "band_count_per_side": BAND_COUNT,
        "listening_mode_ownership": LISTENING_MODE_OWNERSHIP,
        "c1_and_sav2_simultaneous_audio": False,
        "agent_ids": sorted(agents),
        "selection_changes": selection_changes,
        "sav1_receipt_count": len(receipts),
        "playback_provenance_count": len(prov),
        "schedule_preview": schedule[:32],
        "authoritative_a5_evidence": {
            "sav1_receipts": True,
            "section_a_only": True,
            "section_b_influences_playback": False,
            "probe_samples": False,
            "stream": False,
            "cognition": False,
        },
        "playback_derived": {
            "mapped_amplitude_schedule": True,
            "stereo_routing": "L→L R→R translated monitor",
            "carriers": True,
            "queue_drops": meta.get("dropped"),
            "limiter_activations": meta.get("limiter_activations"),
            "device_sample_rate": meta.get("device_sample_rate"),
            "human_binaural_model": False,
            "hrtf": False,
            "mind_reading": False,
        },
        "physical_evidence_affected": False,
        "playback_affected_simulation": False,
        "mind_reading": False,
        "progress": {
            "mode": "FINITE_PROVENANCE_SCAN" if total > 0 else "LIVE_INDEFINITE",
            "completed": completed,
            "total": total,
            "percent": (100.0 * completed / total) if total > 0 else None,
            "note": (
                f"processed SAV2 provenance items / total = {completed}/{total}"
                if total > 0
                else "indefinite live monitoring — no fabricated percentage"
            ),
        },
        "section_title": MODE_LABEL,
        "causal_reconstruction": (
            "selected organism SAV1 A5 Section A left/right → "
            "LINEAR_RECEPTOR_ACTIVATION_FIXED_REFERENCE_V1 → "
            "TRANSLATED_STEREO_LR_RECEPTOR_MONITOR_V1 schedule "
            "(playback-derived; not organism subjective sound)"
        ),
    }


def format_selected_organism_auditory_sonification_section(s: dict[str, Any]) -> str:
    lines = [
        f"## {s.get('section_title') or MODE_LABEL}",
        f"status: {s.get('status')}",
        f"warning: {s.get('warning_label')}",
        f"profile: {s.get('profile')}",
        f"authority: {s.get('authority_class')}",
        f"mapping: {s.get('amplitude_mapping')}",
        f"routing: {s.get('channel_mode')}",
        f"carriers: {s.get('carrier_label')}",
        f"agents: {s.get('agent_ids')}",
        f"selection_changes: {s.get('selection_changes')}",
        f"receipts: {s.get('sav1_receipt_count')} · provenance: {s.get('playback_provenance_count')}",
        f"progress: {s.get('progress')}",
        f"mind_reading: {s.get('mind_reading')}",
        f"playback_affected_simulation: {s.get('playback_affected_simulation')}",
        f"reconstruction: {s.get('causal_reconstruction')}",
    ]
    return "\n".join(lines)
