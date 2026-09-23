"""Observer/Analyzer metrics for articulated head + physical push (no psychology labels)."""
from __future__ import annotations

from typing import Any


def summarize_active_sensor_orientation(
    scientific_rows: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Factual head/sensor orientation summary from scientific evidence."""
    head_active = 0
    decoupling = 0
    neck_events = 0
    for r in scientific_rows:
        hr = float(r.get("head_relative_angle") or 0.0)
        if abs(hr) > 1e-6:
            head_active += 1
        th = float(r.get("theta") or 0.0)
        hwh = float(r.get("head_world_heading") if r.get("head_world_heading") is not None else th)
        if abs(hwh - th) > 1e-4:
            decoupling += 1
    for ev in events:
        t = str(ev.get("type") or "")
        if t.startswith("NECK_"):
            neck_events += 1
    return {
        "section": "ACTIVE SENSOR ORIENTATION",
        "head_active_ticks": head_active,
        "head_body_angular_decoupling_ticks": decoupling,
        "neck_motor_events": neck_events,
        "semantics": {
            "not_attention": True,
            "not_tracking": True,
            "label": "SENSOR_ORIENTATION_ASSOCIATION_CANDIDATE_METRICS_ONLY",
        },
    }


def summarize_physical_force_actions(
    events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Factual PUSH / force exertion summary."""
    applied = 0
    no_contact = 0
    for ev in events:
        t = str(ev.get("type") or "")
        if t == "PUSH_FORCE_APPLIED":
            applied += 1
        elif t == "PUSH_NO_CONTACT":
            no_contact += 1
    return {
        "section": "PHYSICAL FORCE ACTIONS",
        "push_activations_applied": applied,
        "push_without_contact": no_contact,
        "causally_linked_displacement_events": applied,
        "semantics": {
            "not_aggression": True,
            "not_push_agent": True,
            "later_cognition_not_auto_causal": True,
        },
    }


def summarize_vestibular_proprioception(
    scientific_rows: list[dict[str, Any]],
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Factual vestibular / proprioceptive forensics. No psychology labels."""
    events = events or []
    n = len(scientific_rows)
    omega_nz = 0
    vest_nz = 0
    prop_active = 0
    omegas: list[float] = []
    alphas: list[float] = []
    head_rels: list[float] = []
    missing_vest = 0
    for r in scientific_rows:
        om = r.get("omega")
        if om is not None:
            omegas.append(float(om))
            if abs(float(om)) > 1e-9:
                omega_nz += 1
        al = r.get("body_alpha")
        if al is not None:
            alphas.append(float(al))
        hr = r.get("head_relative_angle")
        if hr is not None:
            head_rels.append(float(hr))
        v0 = r.get("vest_0")
        if v0 is None and r.get("vest_1") is None:
            missing_vest += 1
        elif abs(float(v0 or 0.0)) > 1e-9 or abs(float(r.get("vest_1") or 0.0)) > 1e-9:
            vest_nz += 1
        p0 = r.get("prop_neck_0")
        if p0 is not None and abs(float(p0)) > 1e-9:
            prop_active += 1
    neck_events = sum(1 for ev in events if str(ev.get("type") or "").startswith("NECK_"))
    return {
        "section": "VESTIBULAR / PROPRIOCEPTIVE FORENSICS",
        "n_rows": n,
        "ticks_nonzero_body_omega": omega_nz,
        "omega_mean": (sum(omegas) / len(omegas)) if omegas else None,
        "alpha_mean": (sum(alphas) / len(alphas)) if alphas else None,
        "vestibular_activation_ticks": vest_nz,
        "vestibular_fields_missing_rows": missing_vest,
        "vestibular_fields_status": (
            "NOT_AVAILABLE" if n > 0 and missing_vest == n else "PRESENT"
        ),
        "neck_motor_events": neck_events,
        "prop_neck_active_ticks": prop_active,
        "head_relative_angle_range": (
            [min(head_rels), max(head_rels)] if head_rels else None
        ),
        "semantics": {
            "not_balance": True,
            "not_gaze_stabilization": True,
            "not_self_awareness": True,
            "old_runs_without_fields": "NOT_AVAILABLE_not_zero",
        },
    }


def summarize_oscillatory_signaling(
    scientific_rows: list[dict[str, Any]],
    events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Factual oscillatory signaling forensics. PHYSICAL SIGNALS ≠ MESSAGES."""
    events = events or []
    n = len(scientific_rows)
    emit_ticks = 0
    recv_ticks = 0
    freqs: list[float] = []
    amps: list[float] = []
    missing = 0
    for r in scientific_rows:
        if r.get("osc_emit_active") is None and r.get("osc_frequency") is None and r.get("osc_l_energy") is None:
            missing += 1
            continue
        if r.get("osc_emit_active"):
            emit_ticks += 1
        if float(r.get("osc_l_energy") or 0.0) > 1e-9 or float(r.get("osc_r_energy") or 0.0) > 1e-9:
            recv_ticks += 1
        if r.get("osc_frequency") is not None:
            freqs.append(float(r["osc_frequency"]))
        if r.get("osc_amplitude") is not None:
            amps.append(float(r["osc_amplitude"]))
    osc_events = sum(
        1 for ev in events
        if "OSC" in str(ev.get("type") or "").upper()
        or "OSCILLAT" in str(ev.get("type") or "").upper()
    )
    # Neutral pattern IDs only — never word/message labels.
    patterns: list[dict[str, Any]] = []
    if len(freqs) >= 3:
        # Coarse spectral-temporal bins as SPECTROTEMPORAL_PATTERN_k
        bins = {}
        for f, a in zip(freqs, amps or [0.0] * len(freqs)):
            key = (round(f, 1), round(a, 1))
            bins[key] = bins.get(key, 0) + 1
        for i, ((f, a), c) in enumerate(sorted(bins.items(), key=lambda kv: -kv[1])[:5]):
            if c >= 2:
                patterns.append({
                    "id": f"SPECTROTEMPORAL_PATTERN_{i+1:03d}",
                    "frequency_bin": f,
                    "amplitude_bin": a,
                    "count": c,
                    "label_class": "PHYSICAL_PATTERN_ONLY",
                })
    return {
        "section": "OSCILLATORY SIGNAL FORENSICS",
        "n_rows": n,
        "emission_active_ticks": emit_ticks,
        "reception_energy_ticks": recv_ticks,
        "frequency_mean": (sum(freqs) / len(freqs)) if freqs else None,
        "amplitude_mean": (sum(amps) / len(amps)) if amps else None,
        "osc_fields_status": (
            "NOT_AVAILABLE" if n > 0 and missing == n else "PRESENT"
        ),
        "osc_related_events": osc_events,
        "physical_patterns": patterns,
        "legacy_field_ab": "ANALYZABLE_SEPARATELY",
        "evidence_labels": {
            "emission_to_field": "CAUSALLY_LINKED_when_receipts_present",
            "field_to_reception": "CAUSALLY_LINKED_when_receipts_present",
            "reception_to_cognition": "NOT_ESTABLISHED",
            "reception_to_meaning": "NOT_ESTABLISHED",
        },
        "semantics": {
            "not_language": True,
            "not_message": True,
            "not_dialogue": True,
            "not_word": True,
            "physical_signals_not_messages": True,
        },
    }
