"""SELECTED_ORGANISM_AUDITORY_SONIFICATION_V1 — SAV2 playback profile metadata.

Frontend renders audio. Does not mutate SAV1, osc_l/r, LPS, probe, C1 numerics, or cognition.
Carriers reference C1 canonical_playback_carrier_hz — not redefined.
"""
from __future__ import annotations

import copy
from typing import Any

from mechanistic_mind.physical_system.canonical_physical_field_sonification import (
    CANONICAL_PLAYBACK_CARRIER_HZ,
    CANONICAL_SECONDS_PER_TICK,
    ENVELOPE_FRACTION_OF_TICK,
    INPUT_QUEUE_CAPACITY,
    MASTER_DEFAULT_VOLUME,
    SCHEDULED_HORIZON_SECONDS,
)

SCHEMA = "SELECTED_ORGANISM_AUDITORY_SONIFICATION_V1"
CONTRACT_ID = "selected_organism_auditory_sonification"
PROFILE = "CANONICAL_ORGANISM_RECEPTOR_SONIFICATION_SAV2_V1"
CAPABILITY = "selected_organism_auditory_sonification"
MODE = "SELECTED_ORGANISM_AUDITORY_SONIFICATION"
MODE_LABEL = "SELECTED ORGANISM AUDITORY SONIFICATION"
WARNING_LABEL = (
    "TRANSLATED MONITOR OF ORGANISM RECEPTOR CHANNELS · POST-PHENOTYPE · "
    "PRE-COGNITION · NOT HUMAN HEARING · NOT MIND READING"
)
INPUT_BOUNDARY = "A5_OSC_LR_ACCESSIBLE_OBSERVATION_PRE_COGNITION"
PLAYBACK_AUTHORITY_CLASS = "PLAYBACK_DERIVED_TRANSLATED_RECEPTOR_MONITOR"
AMPLITUDE_MAPPING = "LINEAR_RECEPTOR_ACTIVATION_FIXED_REFERENCE_V1"
CHANNEL_MODE = "TRANSLATED_STEREO_LR_RECEPTOR_MONITOR_V1"
CARRIER_LABEL = "PLAYBACK CARRIERS — NOT PHYSICAL OR ORGANISM FREQUENCIES"
LISTENING_MODE_OWNERSHIP = "MUTUALLY_EXCLUSIVE_LISTENING_MODES"
REQUIRED_SAV1_PROFILE = "ORGANISM_AUDITORY_BOUNDARY_A5_V1"
REQUIRED_C0_PROFILE = "ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1"
FIXED_RECEPTOR_GAIN = 0.35
LIMITER_THRESHOLD = 0.95
LEGACY_UNAVAILABLE = "SELECTED_ORGANISM_AUDITORY_SONIFICATION_UNAVAILABLE_LEGACY_EVIDENCE"
BAND_COUNT = 6

_PAYLOAD: dict[str, Any] = {
    "schema": SCHEMA,
    "contract": CONTRACT_ID,
    "profile": PROFILE,
    "capability": CAPABILITY,
    "mode": MODE,
    "mode_label": MODE_LABEL,
    "warning_label": WARNING_LABEL,
    "input_boundary": INPUT_BOUNDARY,
    "authority_class": PLAYBACK_AUTHORITY_CLASS,
    "researcher_only": True,
    "agent_accessible": False,
    "physical_mechanism": False,
    "physical_preset": False,
    "audio_renderer_location": "OBSERVER_FRONTEND_ONLY",
    "required_sav1_profile": REQUIRED_SAV1_PROFILE,
    "required_c0_profile": REQUIRED_C0_PROFILE,
    "amplitude_mapping": AMPLITUDE_MAPPING,
    "fixed_receptor_gain": FIXED_RECEPTOR_GAIN,
    "c1_sqrt_energy_mapping_used": False,
    "channel_mode": CHANNEL_MODE,
    "left_to_left_routing": True,
    "right_to_right_routing": True,
    "human_binaural_model": False,
    "hrtf": False,
    "interaural_delay": False,
    "source_position_panning": False,
    "band_count_per_side": BAND_COUNT,
    "canonical_playback_carrier_hz": list(CANONICAL_PLAYBACK_CARRIER_HZ),
    "carrier_authority": "CANONICAL_ABSTRACT_BAND_SONIFICATION_C1_V1",
    "carrier_label": CARRIER_LABEL,
    "carrier_hz_are_physical": False,
    "carrier_hz_are_organism_frequencies": False,
    "canonical_seconds_per_tick": CANONICAL_SECONDS_PER_TICK,
    "canonical_seconds_per_tick_is_physical": False,
    "envelope_fraction_of_tick": ENVELOPE_FRACTION_OF_TICK,
    "input_queue_capacity": INPUT_QUEUE_CAPACITY,
    "scheduled_horizon_seconds": SCHEDULED_HORIZON_SECONDS,
    "master_default_volume": MASTER_DEFAULT_VOLUME,
    "limiter_threshold": LIMITER_THRESHOLD,
    "listening_mode_ownership": LISTENING_MODE_OWNERSHIP,
    "c1_and_sav2_simultaneous_audio": False,
    "consumes_sav1_section_a_only": True,
    "consumes_researcher_provenance": False,
    "consumes_probe_samples": False,
    "playback_is_literal_organism_sound": False,
    "original_human_audible_available": False,
    "legacy_without_sav1_policy": LEGACY_UNAVAILABLE,
    "zero_activation_is_silence": True,
    "per_event_normalization": False,
    "per_side_normalization": False,
    "automatic_gain_control": False,
}


def sav2_profile_payload() -> dict[str, Any]:
    return copy.deepcopy(_PAYLOAD)


def sav2_profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "capability": CAPABILITY,
        "mode_label": MODE_LABEL,
        "warning_label": WARNING_LABEL,
        "input_boundary": INPUT_BOUNDARY,
        "authority_class": PLAYBACK_AUTHORITY_CLASS,
        "amplitude_mapping": AMPLITUDE_MAPPING,
        "fixed_receptor_gain": FIXED_RECEPTOR_GAIN,
        "channel_mode": CHANNEL_MODE,
        "carrier_label": CARRIER_LABEL,
        "canonical_playback_carrier_hz": list(CANONICAL_PLAYBACK_CARRIER_HZ),
        "listening_mode_ownership": LISTENING_MODE_OWNERSHIP,
        "researcher_only": True,
        "agent_accessible": False,
        "playback_is_literal_organism_sound": False,
    }


def observer_sav2_status() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "mode_label": MODE_LABEL,
        "warning_label": WARNING_LABEL,
        "available": True,
        "implemented": True,
        "carrier_label": CARRIER_LABEL,
        "listening_mode_ownership": LISTENING_MODE_OWNERSHIP,
        "status_lines": [
            f"Listening mode: {MODE_LABEL}",
            WARNING_LABEL,
            f"SAV2 profile: {PROFILE}",
            "Mapping: LINEAR_RECEPTOR_ACTIVATION_FIXED_REFERENCE_V1",
            "Routing: organism L→monitor L · organism R→monitor R",
            CARRIER_LABEL,
            "ORIGINAL / HUMAN-AUDIBLE: NOT AVAILABLE",
        ],
    }


def map_receptor_activation(
    left: list[float] | None,
    right: list[float] | None,
    *,
    gain: float | None = None,
) -> dict[str, Any]:
    """Pure linear mapping. Does not mutate SAV1 evidence."""
    g = float(FIXED_RECEPTOR_GAIN if gain is None else gain)
    out_l: list[float] = []
    out_r: list[float] = []
    clamped = 0

    def one(src: list[float] | None, dest: list[float]) -> None:
        nonlocal clamped
        arr = list(src or [])
        for i in range(BAND_COUNT):
            raw = arr[i] if i < len(arr) else 0.0
            try:
                v = float(raw)
            except (TypeError, ValueError):
                v = 0.0
                clamped += 1
            if v != v or v in (float("inf"), float("-inf")):
                v = 0.0
                clamped += 1
            if v < 0.0 or v > 1.0:
                clamped += 1
            v = max(0.0, min(1.0, v))
            dest.append(g * v)

    one(left, out_l)
    one(right, out_r)
    return {
        "left_amplitudes": out_l,
        "right_amplitudes": out_r,
        "invalid_clamped": clamped,
        "policy": AMPLITUDE_MAPPING,
        "fixed_receptor_gain": g,
        "authority_class": PLAYBACK_AUTHORITY_CLASS,
    }
