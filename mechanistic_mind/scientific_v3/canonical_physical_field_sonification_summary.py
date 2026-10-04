"""Analyzer reconstruction for CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.canonical_physical_field_sonification import (
    AUTHORITY_CLASS,
    CANONICAL_PLAYBACK_CARRIER_HZ,
    ENERGY_POLICY,
    FIXED_REFERENCE_GAIN,
    LEGACY_UNAVAILABLE,
    MODE_LABEL,
    PROFILE,
    SCHEMA,
    WARNING_LABEL,
    c1_profile_reference,
    map_energy_to_amplitude,
)


def summarize_canonical_sonification(
    probe_samples: list[dict[str, Any]] | None = None,
    *,
    playback_provenance: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    samples = [s for s in (probe_samples or []) if isinstance(s, dict)]
    prov = [p for p in (playback_provenance or []) if isinstance(p, dict)]
    meta = dict(meta or {})

    if not samples and not prov:
        return {
            "schema": SCHEMA,
            "profile": PROFILE,
            "mode_label": MODE_LABEL,
            "warning_label": WARNING_LABEL,
            "available": False,
            "status": LEGACY_UNAVAILABLE,
            "authority_class": AUTHORITY_CLASS,
            "physical_evidence_affected": False,
            "playback_affected_simulation": False,
            "progress": {
                "mode": "UNAVAILABLE",
                "completed": 0,
                "total": 0,
                "percent": None,
                "note": "No probe samples or C1 provenance — do not fabricate progress",
            },
            "section_title": MODE_LABEL,
            "causal_reconstruction": (
                "legacy/missing probe+C0 evidence → canonical sonification unavailable "
                "(not reconstructed from pixels or osc channels)"
            ),
        }

    schedule = []
    for i, s in enumerate(samples):
        energies = list(s.get("anonymous_band_energies") or [])
        mapped = map_energy_to_amplitude(energies)
        schedule.append(
            {
                "index": i,
                "sample_key": s.get("sample_key"),
                "scientific_tick": s.get("scientific_tick"),
                "mapped_amplitudes": mapped["mapped_amplitudes"],
                "authority_class": AUTHORITY_CLASS,
            }
        )

    total = len(schedule) if schedule else len(prov)
    completed = total
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "mode_label": MODE_LABEL,
        "warning_label": WARNING_LABEL,
        "available": True,
        "status": "C1_SCHEDULE_RECONSTRUCTIBLE",
        "authority_class": AUTHORITY_CLASS,
        "c1_reference": c1_profile_reference(),
        "carrier_label": "PLAYBACK CARRIERS — NOT PHYSICAL FREQUENCIES",
        "canonical_playback_carrier_hz": list(CANONICAL_PLAYBACK_CARRIER_HZ),
        "carrier_hz_are_physical": False,
        "energy_to_amplitude_policy": ENERGY_POLICY,
        "fixed_reference_gain": FIXED_REFERENCE_GAIN,
        "probe_sample_count": len(samples),
        "playback_provenance_count": len(prov),
        "schedule_preview": schedule[:32],
        "physical_evidence": {
            "probe_samples": True,
            "c0_required": True,
            "stream": "NOT_USED_FOR_DEFAULT_C1",
            "osc_channels": "NOT_USED",
        },
        "playback_derived": {
            "mapped_amplitude_schedule": True,
            "carriers": True,
            "queue_drops": meta.get("dropped"),
            "device_sample_rate": meta.get("device_sample_rate"),
        },
        "physical_evidence_affected": False,
        "playback_affected_simulation": False,
        "original_human_audible_available": False,
        "offline_rerender_ready": bool(samples),
        "progress": {
            "mode": "FINITE_SAMPLE_SCAN",
            "completed": completed,
            "total": total,
            "percent": (100.0 * completed / total) if total else None,
            "note": "Progress = processed/total probe samples for deterministic C1 schedule",
        },
        "section_title": MODE_LABEL,
        "causal_reconstruction": (
            "authoritative probe samples + C0 → deterministic C1 mapped-amplitude schedule "
            "→ Observer Web Audio monitoring (non-physical) · simulation untouched"
        ),
    }


def format_canonical_sonification_section(s: dict[str, Any]) -> str:
    prog = s.get("progress") or {}
    lines = [
        f"## {s.get('section_title') or MODE_LABEL}",
        "",
        str(s.get("causal_reconstruction") or ""),
        "",
        f"profile={s.get('profile')} · schema={s.get('schema')}",
        f"status={s.get('status')} · authority={s.get('authority_class')}",
        str(s.get("warning_label") or WARNING_LABEL),
        f"carriers(playback-only)={s.get('canonical_playback_carrier_hz')}",
        f"probe_samples={s.get('probe_sample_count')} · provenance={s.get('playback_provenance_count')}",
        f"playback_affected_simulation={s.get('playback_affected_simulation')}",
        f"ORIGINAL={s.get('original_human_audible_available')}",
        f"progress={prog.get('completed')}/{prog.get('total')} ({prog.get('percent')}%)",
        "",
    ]
    return "\n".join(lines)
