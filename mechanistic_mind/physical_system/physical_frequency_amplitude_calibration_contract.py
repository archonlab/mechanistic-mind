"""PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT_V1 — C0 abstract acoustic authority.

Metadata-only. Does not change physical numbers, LPS, stream records, probe samples,
or osc_l/r. Does not invent Hz, SPL, Pa, seconds, or metres.

Authority stage: C0_ABSTRACT_AUTHORITY
Profile: ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1
"""
from __future__ import annotations

from typing import Any

SCHEMA = "PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT_V1"
CONTRACT_ID = "physical_frequency_amplitude_calibration_contract"
PROFILE = "ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1"
AUTHORITY_STAGE = "C0_ABSTRACT_AUTHORITY"
INTERPRETATION_VERSION = "C0_V1"

NE = "NOT_ESTABLISHED"
LEGACY_UNAVAILABLE = "CALIBRATION_METADATA_NOT_AVAILABLE_LEGACY"
COMPAT_C0 = "C0_EXPLICIT"
COMPAT_LEGACY = "LEGACY_ANONYMOUS_COMPATIBLE"
COMPAT_FUTURE = "INCOMPATIBLE_FUTURE_PROFILE"
COMPAT_MISSING = "CALIBRATION_METADATA_NOT_AVAILABLE_LEGACY"

BAND_COUNT = 6
BAND_IDENTIFIERS = tuple(f"band_{i}" for i in range(BAND_COUNT))

NEXT_HONEST_LISTENING_MODE = "CANONICAL PHYSICAL-FIELD SONIFICATION"
ORIGINAL_HUMAN_AUDIBLE_AVAILABLE = False

# Immortal frozen payload — single backend authority for stream/probe/capture/Observer/Analyzer.
_C0_PAYLOAD: dict[str, Any] = {
    "schema": SCHEMA,
    "contract": CONTRACT_ID,
    "profile": PROFILE,
    "authority_stage": AUTHORITY_STAGE,
    "interpretation_version": INTERPRETATION_VERSION,
    "researcher_only": True,
    "agent_accessible": False,
    "physical_mechanism": False,
    "physical_preset": False,
    "playback_profile": False,
    "audio_playback": False,
    "compatibility_class": COMPAT_C0,
    "band_count": BAND_COUNT,
    "band_identifiers": list(BAND_IDENTIFIERS),
    "band_index_stability": "STABLE_ANONYMOUS_COORDINATES",
    "band_ordering_semantics": {
        "stable_ordered_indices": True,
        "osc_normalized_spectral_axis": "f_in_[0,1]_WHEN_OSC_PROFILE",
        "physical_frequency_order_hz": NE,
        "note": (
            "Indices are stable anonymous coordinates. OSC may use normalized spectral "
            "location f∈[0,1]. Impact UNIFORM_BROADBAND_V1 treats bands equally. "
            "Array index is not Hz."
        ),
    },
    "physical_frequency_mapping": NE,
    "band_centre_frequencies_hz": NE,
    "band_edge_frequencies_hz": NE,
    "time_authority": {
        "scientific_tick": "AUTHORITATIVE_SIMULATION_TIME_COORDINATE",
        "tick_duration_seconds": NE,
        "browser_frame_rate_is_physical_time": False,
        "audio_sample_rate_is_physical_time": False,
        "execution_modes_alter_scientific_timing": False,
        "impact_emission_duration": "ONE_SCIENTIFIC_TICK_UNDER_CURRENT_ABSTRACTION",
        "osc_duration_authority": "OSC_EMIT_REMAINING_TICKS",
    },
    "length_authority": {
        "world_xy_unit": "ABSTRACT_CELL",
        "cell_length_metres": NE,
        "propagation_speed_unit": "CELLS_PER_SCIENTIFIC_TICK",
        "distance_model": "XY_TOROIDAL_MINIMUM_IMAGE",
        "z_distance": "ABSENT",
        "occlusion": False,
        "reflection": False,
        "reverb": False,
    },
    "emission_amplitude_authority": {
        "quantity": "ANONYMOUS_SIMULATION_ACOUSTIC_ENERGY",
        "emission_energy_joules": NE,
        "spectral_allocation": "ANONYMOUS_PER_BAND_EMISSION_ENERGY",
        "source_coupling_authority": "SOURCE_MECHANISM",
        "mechanical_energy_withdrawn_default": False,
        "global_conservation_claim": False,
        "note": "Metadata does not upgrade absent conservation claims.",
    },
    "point_field_authority": {
        "quantity": "ANONYMOUS_ATTENUATED_BAND_ENERGY",
        "point_field_pressure_pa": NE,
        "attenuation": "EXISTING_DIMENSIONLESS_LPS_LAW",
        "zero_means": "NO_FIELD_ARRIVAL_UNDER_CURRENT_TRANSPORT_NOT_ZERO_DB",
        "not": [
            "pressure",
            "squared_pressure",
            "intensity",
            "power",
            "energy_density",
            "SPL",
            "loudness",
        ],
    },
    "organism_channel_boundary": {
        "channels": ["osc_l_k", "osc_r_k"],
        "quantity": "POST_PHENOTYPE_BOUNDED_ANONYMOUS_CHANNELS",
        "physical_pressure_samples": False,
        "agent_accessible": True,
        "c0_metadata_agent_accessible": False,
        "c0_changes_channel_values": False,
        "c0_changes_channel_interpretation_in_cognition": False,
    },
    "reference_pressure_pa": NE,
    "spl_mapping": NE,
    "human_loudness_model": NE,
    "human_audibility_filter": NE,
    "naming_restrictions": {
        "forbidden_presentations": [
            "ORIGINAL AUDIO",
            "HUMAN-AUDIBLE ORIGINAL",
            "PHYSICAL Hz",
            "SPL",
            "dB",
            "pressure waveform",
            "literal microphone recording",
        ],
        "original_human_audible_available": False,
        "next_honest_listening_mode": NEXT_HONEST_LISTENING_MODE,
        "next_mode_label_requirement": (
            "Deterministic playback transform of abstract physical state; not ORIGINAL"
        ),
    },
    "c1_handoff": {
        "next_slice": "CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1",
        "consumes": [
            "schema",
            "profile",
            "authority_stage",
            "interpretation_version",
            "band_count",
            "band_identifiers",
            "band_ordering_semantics",
            "time_authority",
            "length_authority",
            "emission_amplitude_authority.quantity",
            "point_field_authority.quantity",
            "naming_restrictions.next_honest_listening_mode",
        ],
        "constraints": [
            "C1_maps_anonymous_bands_deterministically_into_playback",
            "C1_is_explicit_sonification_transduction",
            "C1_output_not_authoritative_physical_state",
            "C1_cannot_be_called_ORIGINAL_HUMAN_AUDIBLE",
            "C1_gain_limiter_sample_rate_synthesis_buffering_are_playback_owned",
            "C1_state_never_enters_simulation_LPS_physics_snapshots_organism_perception_cognition",
            "C1_preserves_event_timing_and_relative_band_energy_as_declared_transform_allows",
            "C1_exports_record_transformation_profile",
        ],
    },
    "observer_status_lines": [
        f"Calibration: {PROFILE}",
        f"Bands: {BAND_COUNT} anonymous",
        "Time: scientific ticks",
        "Distance: XY cells",
        "Amplitude: anonymous band energy",
        "Hz: NOT ESTABLISHED",
        "SPL/dB: NOT ESTABLISHED",
        "Playback: NOT IMPLEMENTED",
        "Original / Human-Audible: NOT AVAILABLE",
        f"Next honest listening mode: {NEXT_HONEST_LISTENING_MODE}",
    ],
}


def c0_calibration_payload() -> dict[str, Any]:
    """Return a deep copy of the immutable C0 authority payload."""
    import copy

    return copy.deepcopy(_C0_PAYLOAD)


def c0_calibration_reference() -> dict[str, Any]:
    """Compact frame/run reference (constant size) derived from the same authority."""
    return {
        "schema": SCHEMA,
        "contract": CONTRACT_ID,
        "profile": PROFILE,
        "authority_stage": AUTHORITY_STAGE,
        "interpretation_version": INTERPRETATION_VERSION,
        "compatibility_class": COMPAT_C0,
        "band_count": BAND_COUNT,
        "band_identifiers": list(BAND_IDENTIFIERS),
        "physical_frequency_mapping": NE,
        "tick_duration_seconds": NE,
        "cell_length_metres": NE,
        "emission_energy_joules": NE,
        "point_field_pressure_pa": NE,
        "spl_mapping": NE,
        "original_human_audible_available": False,
        "next_honest_listening_mode": NEXT_HONEST_LISTENING_MODE,
        "audio_playback": False,
        "researcher_only": True,
        "agent_accessible": False,
    }


def classify_calibration_metadata(meta: dict[str, Any] | None) -> str:
    """Classify recorded calibration metadata for Analyzer/saved-run compatibility."""
    if not meta or not isinstance(meta, dict):
        return COMPAT_MISSING
    schema = str(meta.get("schema") or "")
    profile = str(meta.get("profile") or "")
    if schema == SCHEMA and profile == PROFILE:
        return COMPAT_C0
    if schema in ("", LEGACY_UNAVAILABLE) or profile in ("", LEGACY_UNAVAILABLE):
        return COMPAT_MISSING
    if schema.startswith("PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION") or profile:
        # Known foreign / future profile
        if schema != SCHEMA or profile != PROFILE:
            return COMPAT_FUTURE
    return COMPAT_LEGACY


def legacy_calibration_stub() -> dict[str, Any]:
    return {
        "schema": LEGACY_UNAVAILABLE,
        "profile": LEGACY_UNAVAILABLE,
        "compatibility_class": COMPAT_MISSING,
        "note": "Legacy acoustic evidence recorded without C0 metadata; not silently rewritten.",
        "physical_values_transformed": False,
    }


def observer_calibration_status() -> dict[str, Any]:
    ref = c0_calibration_reference()
    ref["status_lines"] = list(_C0_PAYLOAD["observer_status_lines"])
    ref["full_contract_available"] = True
    return ref


def assert_no_invented_si_numerics(payload: dict[str, Any] | None) -> list[str]:
    """Return list of violation messages if numeric SI fields appear (tests)."""
    if not isinstance(payload, dict):
        return ["payload_not_dict"]
    violations: list[str] = []
    forbidden_numeric_keys = (
        "band_centre_frequencies_hz",
        "band_edge_frequencies_hz",
        "tick_duration_seconds",
        "cell_length_metres",
        "emission_energy_joules",
        "point_field_pressure_pa",
        "reference_pressure_pa",
    )
    for key in forbidden_numeric_keys:
        val = payload.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            violations.append(f"{key}={val}")
        if isinstance(val, (list, tuple)) and any(isinstance(x, (int, float)) for x in val):
            violations.append(f"{key}_list_numeric")
    # Nested time/length authorities
    for nest_key in ("time_authority", "length_authority", "emission_amplitude_authority", "point_field_authority"):
        nest = payload.get(nest_key)
        if isinstance(nest, dict):
            violations.extend(assert_no_invented_si_numerics({**{k: nest.get(k) for k in forbidden_numeric_keys}}))
    return [v for v in violations if v != "payload_not_dict"]
