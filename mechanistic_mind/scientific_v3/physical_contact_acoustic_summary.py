"""PHYSICAL CONTACT ACOUSTIC EVENTS (Acanthostega Audio B). Researcher receipts only.

Links contact impulse measurement -> contact acoustic emission -> local-signal reception by
emission_id. Statuses: OBSERVED / VERIFIED / NOT_AVAILABLE. No progress bar. The result is a
physical provenance audit, not "understanding of impacts" and not communication.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SECTION = "PHYSICAL CONTACT ACOUSTIC EVENTS"
SCHEMA_VERSION = "PHYSICAL_CONTACT_ACOUSTIC_SUMMARY_V1"
MEASUREMENT = "PHYSICAL_CONTACT_IMPULSE_MEASUREMENT"
EMISSION = "PHYSICAL_CONTACT_ACOUSTIC_EMISSION"
RECEPTION = "LOCAL_PHYSICAL_SIGNAL_RECEPTION"

EXPLICIT = {
    "MATERIAL_DEPENDENT_ACOUSTICS": "NOT_IMPLEMENTED",
    "OBJECT_COLLISION_ACOUSTICS": "NOT_IMPLEMENTED",
    "SEMANTIC_SOUND_CLASSES": "NOT_IMPLEMENTED",
    "IMPACT_UNDERSTANDING": "NOT_ESTABLISHED",
    "COMMUNICATION": "NOT_ESTABLISHED",
}


def _dedup(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen, out = set(), []
    for r in rows:
        k = r.get(key)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def _rng(vals: list[float]) -> list[float] | None:
    return [min(vals), max(vals)] if vals else None


def summarize_physical_contact_acoustics(
    contact_events: list[dict[str, Any]] | None,
    signal_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ms = _dedup([e for e in contact_events or [] if isinstance(e, dict) and e.get("receipt_kind") == MEASUREMENT],
                "measurement_id")
    ems = _dedup([e for e in contact_events or [] if isinstance(e, dict) and e.get("receipt_kind") == EMISSION],
                 "emission_id")
    recs = _dedup([e for e in signal_events or [] if isinstance(e, dict) and e.get("receipt_kind") == RECEPTION],
                  "reception_id")
    em_ids = {e.get("emission_id") for e in ems}
    linked = [r for r in recs if r.get("emission_id") in em_ids and r.get("accepted")]
    silent = [m for m in ms if not m.get("emitted")]
    below = [m for m in silent if m.get("silence_reason") == "NEW_IMPULSE_BELOW_EPSILON"]
    resting = [m for m in silent if m.get("silence_reason") == "RESTING_CONTACT_NO_NEW_IMPULSE"]
    pairs_e = sorted(ems, key=lambda e: float(e.get("new_impulse_magnitude") or 0.0))
    monotone = all(
        float(b.get("emitted_energy") or 0.0) >= float(a.get("emitted_energy") or 0.0) - 1e-12
        for a, b in zip(pairs_e, pairs_e[1:])
    )
    # resting contact never re-emits: no emission whose measurement had zero new impulse
    by_mid = {m.get("measurement_id"): m for m in ms}
    resting_reemissions = sum(
        1 for e in ems
        if float((by_mid.get(e.get("contact_receipt_ref")) or {}).get("new_impulse_magnitude", 1.0) or 0.0) <= 0.0
        and not (by_mid.get(e.get("contact_receipt_ref")) or {}).get("push_applied")
    )
    per_tick_pair: dict[tuple, int] = {}
    for e in ems:
        k = (e.get("emission_tick"), tuple(e.get("canonical_body_pair") or ()))
        per_tick_pair[k] = per_tick_pair.get(k, 0) + 1
    duplicates = sum(v - 1 for v in per_tick_pair.values() if v > 1)
    chain_complete = sum(1 for e in ems if e.get("contact_receipt_ref") in by_mid)
    provenance_fields = ("emission_id", "canonical_body_pair", "position", "position_derivation",
                         "contact_receipt_ref", "new_impulse_magnitude", "acoustic_coupling",
                         "unclamped_energy", "emitted_energy", "anonymous_band_vector")
    complete = sum(1 for e in ems if all(e.get(f) is not None for f in provenance_fields)
                   and e.get("semantic_label") is False and e.get("agent_accessible") is False)
    rel_v_avail = sum(1 for e in ems if e.get("relative_normal_velocity_pre_contact") not in (None, "NOT_AVAILABLE"))
    dist_energy = sorted([[float(r.get("toroidal_distance") or 0.0), float(r.get("total_received_energy") or 0.0),
                           int(r.get("propagation_delay") or 0)] for r in linked])
    n_events = len(ms) + len(ems)
    status = "OBSERVED" if n_events else "NOT_AVAILABLE"
    return {
        "section": SECTION,
        "schema_version": SCHEMA_VERSION,
        "event_count": n_events,
        "status": status,
        "contact_impulses_measured": len(ms),
        "silent_measurements": len(silent),
        "silent_below_epsilon": len(below),
        "silent_resting_contact": len(resting),
        "emissions_created": len(ems),
        "impulse_magnitude_range": _rng([float(e.get("new_impulse_magnitude") or 0.0) for e in ems]),
        "measured_contact_impulse_range": _rng([float(m.get("contact_impulse_magnitude") or 0.0) for m in ms]),
        "acoustic_energy_range": _rng([float(e.get("emitted_energy") or 0.0) for e in ems]),
        "impulse_to_energy_monotone": ("VERIFIED" if monotone else "VIOLATED") if len(ems) >= 2 else "NOT_AVAILABLE",
        "linked_receptions": len(linked),
        "propagation_delays": sorted({int(r.get("propagation_delay") or 0) for r in linked}),
        "distance_energy_delay_samples": dist_energy[:64],
        "attenuation_by_distance": (
            "VERIFIED" if all(a[1] >= b[1] - 1e-9 for a, b in zip(
                [r for r in dist_energy], [r for r in dist_energy][1:])) else "OBSERVED_MIXED_SOURCES"
        ) if len(dist_energy) >= 2 else "NOT_AVAILABLE",
        "resting_contact_reemissions": resting_reemissions,
        "no_repeated_emission_in_resting_contact": "VERIFIED" if resting_reemissions == 0 and ms else "NOT_AVAILABLE",
        "duplicate_emissions_same_pair_same_tick": duplicates,
        "causal_links_contact_to_emission": chain_complete,
        "causal_links_emission_to_reception": len({r.get("emission_id") for r in linked}),
        "provenance_complete_emissions": complete,
        "provenance_quality": (
            "VERIFIED" if ems and complete == len(ems) and chain_complete == len(ems) else
            ("NOT_AVAILABLE" if not ems else "PARTIAL")
        ),
        "relative_velocity_available_emissions": rel_v_avail,
        "explicit_status": dict(EXPLICIT),
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_physical_contact_acoustic_section(s: dict[str, Any]) -> str:
    lines = [
        SECTION,
        "-" * len(SECTION),
        f"status: {s.get('status')}  (researcher-only; physical provenance audit, not impact understanding or communication)",
        f"contact impulses measured: {s.get('contact_impulses_measured')}  silent: {s.get('silent_measurements')} "
        f"(below epsilon {s.get('silent_below_epsilon')}, resting contact {s.get('silent_resting_contact')})",
        f"emissions created: {s.get('emissions_created')}  duplicates same pair/tick: {s.get('duplicate_emissions_same_pair_same_tick')}",
        f"impulse magnitude range: {s.get('impulse_magnitude_range')}  acoustic energy range: {s.get('acoustic_energy_range')}",
        f"impulse -> energy monotone: {s.get('impulse_to_energy_monotone')}",
        f"linked receptions: {s.get('linked_receptions')}  propagation delays: {s.get('propagation_delays')}  "
        f"attenuation by distance: {s.get('attenuation_by_distance')}",
        f"resting contact re-emissions: {s.get('resting_contact_reemissions')}  "
        f"({s.get('no_repeated_emission_in_resting_contact')})",
        f"causal links contact->emission: {s.get('causal_links_contact_to_emission')}  "
        f"emission->reception: {s.get('causal_links_emission_to_reception')}  provenance: {s.get('provenance_quality')}",
    ]
    for k, v in (s.get("explicit_status") or {}).items():
        lines.append(f"{k} = {v}")
    return "\n".join(lines)


def contact_receipts_from_consequences(run_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = Path(run_dir) / "scientific_consequences.jsonl"
    contact: list[dict[str, Any]] = []
    signal: list[dict[str, Any]] = []
    if not path.exists():
        return contact, signal
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            for ref in row.get("event_refs") or []:
                if not isinstance(ref, dict):
                    continue
                if ref.get("kind") == "physical_contact_acoustic":
                    contact.append(ref)
                elif ref.get("kind") == "local_physical_signal":
                    signal.append(ref)
    return contact, signal
