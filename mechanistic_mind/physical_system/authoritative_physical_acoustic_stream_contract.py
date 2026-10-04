"""AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_CONTRACT_V1

Read-only scientific/display contract over committed physical acoustic emissions.
Not a physical preset. Not a playback layer. Never emits into LPS.

Authority layers (V1 streams L1 + L2 references):
  L1 — committed mechanism / LPS source emission receipts
  L2 — LPS emission_id / transport references
  L3 — body receiver field (not globally reconstructable here)
  L4 — organism anonymous osc_l/r (unchanged; not streamed as cognition)
  L5 — human playback (ABSENT)

When LPS is active, legacy OSC_BANDS is NON_AUTHORITATIVE compatibility data and
must not create duplicate stream records.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA = "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_V1"
CONTRACT_ID = "authoritative_physical_acoustic_stream"
RECORD_FAMILY = "PHYSICAL_ACOUSTIC_STREAM_RECORD"
STATE_SCHEMA = "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_STATE_V1"
DISPLAY_SLICE = "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_CONTRACT_V1"
WORLD_ATTR = "authoritative_physical_acoustic_stream_state"

# Align with per-mechanism history_limit (32) × five families, soft global cap.
HISTORY_CAPACITY_DEFAULT = 96
HISTORY_CAPACITY_MIN = 8
HISTORY_CAPACITY_MAX = 512

TRANSPORT_PROFILE = "LOCAL_PHYSICAL_SIGNAL_TRANSPORT_V1"
TRANSPORT_MEDIUM = "UNIFORM_SIGNAL_MEDIUM_V1"

MECH_CONTACT = "physical_contact_acoustic_emission"
MECH_BODY_OBJECT = "body_resource_object_impact_acoustic_emission"
MECH_OBJECT_OBJECT = "resource_object_pair_impact_acoustic_emission"
MECH_VERTICAL = "vertical_impact_acoustic_emission"
MECH_OSC_EMIT = "OSC_EMIT"
MECH_LPS_INTERVENTION = "local_physical_signal_transport_intervention"

# Within-tick physical emission sequence (two_agent / runtime order).
MECHANISM_RANK: dict[str, int] = {
    MECH_CONTACT: 0,
    MECH_BODY_OBJECT: 1,
    MECH_OBJECT_OBJECT: 2,
    MECH_VERTICAL: 3,
    MECH_OSC_EMIT: 4,
    MECH_LPS_INTERVENTION: 5,
}

LEGACY_OSC_BANDS_AUTHORITY = "NON_AUTHORITATIVE_WHEN_LPS_ACTIVE"
AUTHORITY_LABELS = {
    "stream": "RESEARCHER_AUTHORITATIVE_RECEIPT",
    "l1": "COMMITTED_PHYSICAL_SOURCE_RECEIPT",
    "l2": "LPS_TRANSPORT_REFERENCE",
    "l3": "NOT_GLOBALLY_RECONSTRUCTABLE_IN_V1",
    "l4": "ORGANISM_ANONYMOUS_CHANNELS_UNCHANGED",
    "l5": "HUMAN_PLAYBACK_ABSENT",
    "hz": "PHYSICAL_FREQUENCY_MAPPING_NOT_ESTABLISHED",
    "spl": "LOUDNESS_CALIBRATION_NOT_ESTABLISHED",
    "legacy_osc_bands": LEGACY_OSC_BANDS_AUTHORITY,
}

NA = "NOT_AVAILABLE_IN_LEGACY_RECORD"
NE = "NOT_ESTABLISHED"
NAP = "NOT_APPLICABLE"

_LPS_OSC_PROVENANCE = frozenset({
    "ENDOGENOUS_MOTOR",
    "INTERVENTION_EXPERIMENTER_BODY",
})
_LPS_INTERVENTION_PROVENANCE = frozenset({"INTERVENTION_SETUP"})


@dataclass
class AcousticStreamState:
    """Bounded researcher-only stream over committed physical acoustic emissions."""

    schema_version: str = STATE_SCHEMA
    capacity: int = HISTORY_CAPACITY_DEFAULT
    records: list[dict[str, Any]] = field(default_factory=list)
    seen_emission_ids: set[str] = field(default_factory=set)
    next_stream_sequence: int = 0
    evicted_count: int = 0
    dropped_invalid_count: int = 0
    last_sync_tick: int | None = None
    counters: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.counters:
            self.counters = {
                "ingested": 0,
                "skipped_duplicate": 0,
                "skipped_legacy_osc_bands": 0,
                "from_contact": 0,
                "from_body_object": 0,
                "from_object_object": 0,
                "from_vertical": 0,
                "from_osc_emit": 0,
                "from_lps_intervention": 0,
            }


def _clamp_capacity(n: int) -> int:
    return max(HISTORY_CAPACITY_MIN, min(HISTORY_CAPACITY_MAX, int(n)))


def ensure_acoustic_stream_state(world: Any, *, capacity: int | None = None) -> AcousticStreamState:
    st = getattr(world, WORLD_ATTR, None)
    if isinstance(st, AcousticStreamState):
        if capacity is not None:
            st.capacity = _clamp_capacity(capacity)
        return st
    st = AcousticStreamState(capacity=_clamp_capacity(capacity or HISTORY_CAPACITY_DEFAULT))
    setattr(world, WORLD_ATTR, st)
    return st


def state_of(world: Any) -> AcousticStreamState | None:
    st = getattr(world, WORLD_ATTR, None)
    return st if isinstance(st, AcousticStreamState) else None


def _band_vector(rec: dict[str, Any]) -> list[float] | str:
    bands = rec.get("anonymous_band_vector")
    if bands is None:
        bands = rec.get("anonymous_band_energies")
    if bands is None:
        return NA
    try:
        return [float(b) for b in bands]
    except (TypeError, ValueError):
        return NA


def _position(rec: dict[str, Any]) -> dict[str, Any]:
    cp = rec.get("contact_point")
    if isinstance(cp, (list, tuple)) and len(cp) >= 2:
        out: dict[str, Any] = {"x": float(cp[0]), "y": float(cp[1])}
        if len(cp) >= 3:
            out["z"] = float(cp[2])
        else:
            out["z"] = NE
        return out
    pos = rec.get("position")
    if isinstance(pos, (list, tuple)) and len(pos) >= 2:
        out = {"x": float(pos[0]), "y": float(pos[1]), "z": NE}
        if rec.get("source_z") is not None:
            try:
                out["z"] = float(rec["source_z"])
            except (TypeError, ValueError):
                pass
        return out
    origin = rec.get("physical_origin")
    if isinstance(origin, dict) and origin.get("x") is not None and origin.get("y") is not None:
        return {"x": float(origin["x"]), "y": float(origin["y"]), "z": NE}
    return {"x": NA, "y": NA, "z": NA}


def _entity_provenance(rec: dict[str, Any], mechanism: str) -> dict[str, Any]:
    if mechanism == MECH_CONTACT:
        return {
            "canonical_body_pair": rec.get("canonical_body_pair") or NA,
            "contact_receipt_ref": rec.get("contact_receipt_ref") or NA,
            "response_key": NAP,
        }
    if mechanism == MECH_BODY_OBJECT:
        return {
            "body_id": rec.get("body_id") or NA,
            "object_id": rec.get("object_id") or NA,
            "response_key": rec.get("response_key") or NA,
            "pair_key": rec.get("pair_key") or NA,
        }
    if mechanism == MECH_OBJECT_OBJECT:
        return {
            "object_id_a": rec.get("object_id_a") or rec.get("object_a") or NA,
            "object_id_b": rec.get("object_id_b") or rec.get("object_b") or NA,
            "response_key": rec.get("response_key") or NA,
        }
    if mechanism == MECH_VERTICAL:
        return {
            "entity_id": rec.get("entity_id") or NA,
            "entity_kind": rec.get("entity_kind") or NA,
            "response_key": rec.get("response_key") or NA,
            "source_id": rec.get("source_id") or NA,
            "episode_id": rec.get("episode_id") or NA,
        }
    if mechanism == MECH_OSC_EMIT:
        motor = rec.get("motor_provenance") if isinstance(rec.get("motor_provenance"), dict) else {}
        return {
            "source_body_id": rec.get("source_body_id") or NA,
            "selection_provenance": rec.get("selection_provenance") or NA,
            "command_family": (motor.get("command_family") if motor else None) or "OSC_EMIT",
            "emit_remaining_before": motor.get("emit_remaining_before", NA) if motor else NA,
        }
    return {
        "source_body_id": rec.get("source_body_id") or NA,
        "selection_provenance": rec.get("selection_provenance") or NA,
        "researcher_id": rec.get("researcher_id") or NA,
    }


def _source_identity(mechanism: str, rec: dict[str, Any]) -> str:
    if mechanism == MECH_CONTACT:
        pair = rec.get("canonical_body_pair") or []
        return f"contact:{pair[0]}|{pair[1]}" if len(pair) >= 2 else f"contact:{rec.get('emission_id')}"
    if mechanism == MECH_BODY_OBJECT:
        return f"bo:{rec.get('body_id')}|{rec.get('object_id')}|{rec.get('response_key') or ''}"
    if mechanism == MECH_OBJECT_OBJECT:
        a = rec.get("object_id_a") or rec.get("object_a")
        b = rec.get("object_id_b") or rec.get("object_b")
        return f"oo:{a}|{b}|{rec.get('response_key') or ''}"
    if mechanism == MECH_VERTICAL:
        return f"via:{rec.get('source_id') or rec.get('response_key') or rec.get('emission_id')}"
    if mechanism == MECH_OSC_EMIT:
        return f"osc:{rec.get('source_body_id')}|{rec.get('emission_id')}"
    return f"lps:{rec.get('selection_provenance')}|{rec.get('emission_id')}"


def _normalize_record(
    *,
    mechanism: str,
    rec: dict[str, Any],
    stream_sequence: int,
) -> dict[str, Any] | None:
    eid = rec.get("emission_id")
    if not eid:
        return None
    tick = rec.get("emission_tick")
    if tick is None:
        tick = rec.get("tick")
    if tick is None:
        return None
    energy = rec.get("emitted_energy")
    if energy is None:
        energy = rec.get("total_emitted_energy")
    bands = _band_vector(rec)
    band_profile = rec.get("band_profile")
    if band_profile is None and mechanism == MECH_OSC_EMIT:
        band_profile = "OSC_BAND_PROFILE_NORMALIZED_FREQ_V1"
    if band_profile is None and mechanism == MECH_LPS_INTERVENTION:
        band_profile = "RESEARCHER_CALIBRATION_BANDS_V1"
    if band_profile is None:
        band_profile = rec.get("band_profile") or "UNIFORM_BROADBAND_V1"

    duration: Any
    if mechanism == MECH_OSC_EMIT:
        motor = rec.get("motor_provenance") if isinstance(rec.get("motor_provenance"), dict) else {}
        duration = {
            "model": "FINITE_OSC_EMIT_TICK_INTERVAL",
            "emit_remaining_before": motor.get("emit_remaining_before", NA),
            "note": "One LPS emission per active OSC tick; not an audio clip",
        }
    elif mechanism in (MECH_CONTACT, MECH_BODY_OBJECT, MECH_OBJECT_OBJECT, MECH_VERTICAL):
        duration = {"model": "IMPULSIVE_SOURCE_TICK", "ticks": 1}
    else:
        duration = {"model": "IMPULSIVE_OR_QUEUED_INTERVENTION", "ticks": 1}

    lps_status = rec.get("lps_enqueue_status")
    if lps_status is None:
        # Mechanism receipts are only appended after successful EMITTED.
        lps_status = "EMITTED" if rec.get("status") in (None, "EMITTED") else rec.get("status")

    stream_id = f"apas:{eid}"
    return {
        "schema": SCHEMA,
        "receipt_kind": RECORD_FAMILY,
        "stream_record_id": stream_id,
        "stream_sequence": int(stream_sequence),
        "scientific_tick": int(tick),
        "source_mechanism_id": mechanism,
        "source_receipt_event_id": str(eid),
        "source_identity": _source_identity(mechanism, rec),
        "entity_provenance": _entity_provenance(rec, mechanism),
        "position": _position(rec),
        "emitted_energy": float(energy) if energy is not None else NA,
        "anonymous_band_energies": bands,
        "spectral_profile_id": band_profile,
        "duration_model": duration,
        "lps_emission_id": str(eid),
        "lps_enqueue_status": lps_status,
        "transport_profile": TRANSPORT_PROFILE,
        "transport_medium": TRANSPORT_MEDIUM,
        "transport_expiry_tick": rec.get("transport_expiry_tick", rec.get("expiry_tick", NA)),
        "emission_admitted": True,
        "lps_admitted": str(lps_status) == "EMITTED",
        "authority": {
            "layer_scope": "L1_SOURCE_PLUS_L2_LPS_REFERENCE",
            "classification": AUTHORITY_LABELS["stream"],
            "physical_frequency_mapping": NE,
            "human_loudness": NE,
            "waveform": NAP,
            "semantic_sound_class": NAP,
            "legacy_osc_bands": LEGACY_OSC_BANDS_AUTHORITY,
        },
        "cause_provenance": {
            "response_key": rec.get("response_key", NAP),
            "cause_receipt_ref": rec.get("cause_receipt_ref") or rec.get("contact_receipt_ref") or rec.get("measurement_id") or NA,
            "selection_provenance": rec.get("selection_provenance", NAP),
            "energy_law": rec.get("energy_law", NA),
        },
        "limitations": [
            "NO_HZ_MAPPING",
            "NO_SPL_CALIBRATION",
            "NO_WAVEFORM",
            "NO_PLAYBACK",
            "LPS_XY_ABSTRACTION",
            "L3_L4_NOT_STREAMED_AS_GLOBAL_FIELD",
        ],
        "researcher_only": True,
        "agent_accessible": False,
        "audio_playback": False,
    }


def _collect_mechanism_emissions(world: Any) -> list[tuple[str, dict[str, Any]]]:
    out: list[tuple[str, dict[str, Any]]] = []
    mapping = (
        ("contact_acoustic_state", MECH_CONTACT),
        ("body_object_impact_acoustic_state", MECH_BODY_OBJECT),
        ("resource_object_pair_impact_acoustic_state", MECH_OBJECT_OBJECT),
        ("vertical_impact_acoustic_emission_state", MECH_VERTICAL),
    )
    for attr, mech in mapping:
        st = getattr(world, attr, None)
        if st is None:
            continue
        hist = getattr(st, "emission_history", None) or []
        for rec in hist:
            if isinstance(rec, dict) and rec.get("emission_id"):
                out.append((mech, rec))
    return out


def _collect_lps_osc_emissions(world: Any) -> list[tuple[str, dict[str, Any]]]:
    """OSC_EMIT / experimenter-body / intervention emissions from LPS history only.

    Physical-contact LPS rows are excluded — they are captured from mechanism histories.
    Legacy OSC_BANDS is never read.
    """
    out: list[tuple[str, dict[str, Any]]] = []
    lps = getattr(world, "local_signal_transport", None)
    if lps is None:
        return out
    # Explicit non-authority: do not ingest world.OSC_BANDS.
    _ = getattr(world, "OSC_BANDS", None)  # referenced only to document exclusion
    for rec in list(getattr(lps, "emission_history", None) or []):
        if not isinstance(rec, dict) or not rec.get("emission_id"):
            continue
        prov = str(rec.get("selection_provenance") or "")
        if prov in _LPS_OSC_PROVENANCE:
            out.append((MECH_OSC_EMIT, rec))
        elif prov in _LPS_INTERVENTION_PROVENANCE:
            out.append((MECH_LPS_INTERVENTION, rec))
        # PHYSICAL_CONTACT_IMPULSE → skip (mechanism history owns L1)
    return out


def collect_candidate_emissions(world: Any) -> list[tuple[str, dict[str, Any]]]:
    return _collect_mechanism_emissions(world) + _collect_lps_osc_emissions(world)


def sort_key_for_record(mechanism: str, rec: dict[str, Any]) -> tuple:
    tick = rec.get("emission_tick")
    if tick is None:
        tick = rec.get("tick") or -1
    return (
        int(tick),
        int(MECHANISM_RANK.get(mechanism, 99)),
        str(_source_identity(mechanism, rec)),
        str(rec.get("emission_id") or ""),
    )


def sync_acoustic_stream(world: Any, *, scientific_tick: int | None = None) -> dict[str, Any]:
    """Ingest newly committed physical emissions into the bounded stream.

    Read-only w.r.t. physics/LPS. Idempotent for already-seen emission_ids.
    """
    if world is None:
        return {"status": "NO_WORLD"}
    st = ensure_acoustic_stream_state(world)
    candidates = collect_candidate_emissions(world)
    candidates.sort(key=lambda pair: sort_key_for_record(pair[0], pair[1]))

    # Legacy OSC_BANDS must never contribute records.
    if getattr(world, "OSC_BANDS", None) is not None and getattr(world, "local_signal_transport", None) is not None:
        st.counters["skipped_legacy_osc_bands"] = int(st.counters.get("skipped_legacy_osc_bands", 0)) + 1

    new_rows: list[dict[str, Any]] = []
    for mechanism, rec in candidates:
        eid = str(rec.get("emission_id") or "")
        if not eid:
            st.dropped_invalid_count += 1
            continue
        if eid in st.seen_emission_ids:
            st.counters["skipped_duplicate"] = int(st.counters.get("skipped_duplicate", 0)) + 1
            continue
        seq = int(st.next_stream_sequence)
        row = _normalize_record(mechanism=mechanism, rec=rec, stream_sequence=seq)
        if row is None:
            st.dropped_invalid_count += 1
            continue
        st.next_stream_sequence = seq + 1
        st.seen_emission_ids.add(eid)
        st.records.append(row)
        st.counters["ingested"] = int(st.counters.get("ingested", 0)) + 1
        counter_key = {
            MECH_CONTACT: "from_contact",
            MECH_BODY_OBJECT: "from_body_object",
            MECH_OBJECT_OBJECT: "from_object_object",
            MECH_VERTICAL: "from_vertical",
            MECH_OSC_EMIT: "from_osc_emit",
            MECH_LPS_INTERVENTION: "from_lps_intervention",
        }.get(mechanism)
        if counter_key:
            st.counters[counter_key] = int(st.counters.get(counter_key, 0)) + 1
        new_rows.append(row)

    cap = int(st.capacity)
    while len(st.records) > cap:
        evicted = st.records.pop(0)
        st.evicted_count += 1
        # Keep seen_emission_ids so restore/re-sync cannot resurrect duplicates.
        _ = evicted

    if scientific_tick is not None:
        st.last_sync_tick = int(scientific_tick)
    elif new_rows:
        st.last_sync_tick = int(new_rows[-1]["scientific_tick"])

    return {
        "status": "SYNCED",
        "schema": SCHEMA,
        "new_records": len(new_rows),
        "retained": len(st.records),
        "evicted_count": int(st.evicted_count),
        "capacity": int(st.capacity),
        "last_sync_tick": st.last_sync_tick,
    }


def rebuild_stream_from_histories(world: Any) -> dict[str, Any]:
    """Rebuild bounded stream from existing mechanism/LPS histories (restore fallback).

    Does not emit or enqueue. Clears prior stream state then syncs once.
    """
    st = ensure_acoustic_stream_state(world)
    cap = st.capacity
    setattr(
        world,
        WORLD_ATTR,
        AcousticStreamState(capacity=cap),
    )
    return sync_acoustic_stream(world)


def serialize_state(st: AcousticStreamState | None) -> dict[str, Any] | None:
    if st is None:
        return None
    return {
        "schema_version": STATE_SCHEMA,
        "stream_schema": SCHEMA,
        "contract": CONTRACT_ID,
        "capacity": int(st.capacity),
        "records": list(st.records),
        "seen_emission_ids": sorted(st.seen_emission_ids),
        "next_stream_sequence": int(st.next_stream_sequence),
        "evicted_count": int(st.evicted_count),
        "dropped_invalid_count": int(st.dropped_invalid_count),
        "last_sync_tick": st.last_sync_tick,
        "counters": dict(st.counters),
        "legacy_osc_bands_authority": LEGACY_OSC_BANDS_AUTHORITY,
        "authority_labels": dict(AUTHORITY_LABELS),
        "no_reemit_on_restore": True,
        "no_lps_enqueue_on_restore": True,
        "audio_playback": False,
    }


def restore_state(world: Any, data: dict[str, Any] | None) -> AcousticStreamState | None:
    if not data:
        return None
    if str(data.get("schema_version") or "") not in (STATE_SCHEMA, SCHEMA):
        # Soft accept stream_schema-only payloads by rebuilding.
        if str(data.get("stream_schema") or "") != SCHEMA:
            return None
    st = AcousticStreamState(
        schema_version=STATE_SCHEMA,
        capacity=_clamp_capacity(int(data.get("capacity") or HISTORY_CAPACITY_DEFAULT)),
        records=[dict(r) for r in (data.get("records") or []) if isinstance(r, dict)],
        seen_emission_ids=set(str(x) for x in (data.get("seen_emission_ids") or [])),
        next_stream_sequence=int(data.get("next_stream_sequence") or 0),
        evicted_count=int(data.get("evicted_count") or 0),
        dropped_invalid_count=int(data.get("dropped_invalid_count") or 0),
        last_sync_tick=data.get("last_sync_tick"),
        counters=dict(data.get("counters") or {}),
    )
    # Ensure seen covers restored records.
    for r in st.records:
        eid = r.get("lps_emission_id") or r.get("source_receipt_event_id")
        if eid:
            st.seen_emission_ids.add(str(eid))
    setattr(world, WORLD_ATTR, st)
    return st


def researcher_summary(world: Any) -> dict[str, Any] | None:
    st = state_of(world)
    if st is None:
        return None
    from mechanistic_mind.physical_system.physical_frequency_amplitude_calibration_contract import (
        c0_calibration_reference,
        observer_calibration_status,
    )

    recent = list(st.records[-16:])
    return {
        "schema": SCHEMA,
        "contract": CONTRACT_ID,
        "display_slice": DISPLAY_SLICE,
        "researcher_only": True,
        "agent_accessible": False,
        "audio_playback": False,
        "human_hz_calibration": NE,
        "loudness_calibration": NE,
        "waveform_synthesis": False,
        "legacy_osc_bands_authority": LEGACY_OSC_BANDS_AUTHORITY,
        "authority_labels": dict(AUTHORITY_LABELS),
        "layer_scope": "L1_SOURCE_PLUS_L2_LPS_REFERENCE",
        "transport_profile": TRANSPORT_PROFILE,
        "transport_medium": TRANSPORT_MEDIUM,
        "history_capacity": int(st.capacity),
        "retained_count": len(st.records),
        "evicted_count": int(st.evicted_count),
        "dropped_invalid_count": int(st.dropped_invalid_count),
        "next_stream_sequence": int(st.next_stream_sequence),
        "last_sync_tick": st.last_sync_tick,
        "counters": dict(st.counters),
        "recent_records": recent,
        "acoustic_calibration": c0_calibration_reference(),
        "acoustic_calibration_status": observer_calibration_status(),
        "banner": (
            "PHYSICAL ACOUSTIC EVENTS · RESEARCHER-ONLY · NO AUDIO PLAYBACK · NO HZ CALIBRATION"
        ),
        "labels": [
            "PHYSICAL ACOUSTIC EVENTS",
            "RESEARCHER-ONLY",
            "NO AUDIO PLAYBACK",
            "NO HZ CALIBRATION",
            "SIMULATION UNAFFECTED",
            "AGENT PERCEPTION UNAFFECTED",
        ],
    }


def observer_payload(world: Any) -> dict[str, Any] | None:
    """Compact Observer serialization (idempotent; does not sync)."""
    return researcher_summary(world)


def catalog_item() -> dict[str, Any]:
    return {
        "id": CONTRACT_ID,
        "schema": SCHEMA,
        "kind": "scientific_display_contract",
        "physical_preset": False,
        "physical_mechanism": False,
        "audio_playback": False,
        "description": (
            "Read-only bounded stream of committed physical acoustic source events "
            "with LPS transport references. Not a second acoustic reality."
        ),
    }
