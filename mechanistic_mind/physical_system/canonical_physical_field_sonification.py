"""CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1 — C1 playback transform profile.

Metadata / researcher-only. Does not render audio, mutate LPS, stream, probe
samples, organism hearing, or cognition. Frontend performs Web Audio playback.
"""
from __future__ import annotations

import copy
from typing import Any

SCHEMA = "CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1"
CONTRACT_ID = "canonical_physical_field_sonification"
PROFILE = "CANONICAL_ABSTRACT_BAND_SONIFICATION_C1_V1"
CAPABILITY = "canonical_physical_field_sonification"
MODE = "CANONICAL_PHYSICAL_FIELD_SONIFICATION"
MODE_LABEL = "CANONICAL PHYSICAL-FIELD SONIFICATION"
WARNING_LABEL = (
    "TRANSFORMED PLAYBACK OF ABSTRACT PHYSICAL FIELD · NOT PHYSICAL Hz · "
    "NOT SPL · NOT ORIGINAL HUMAN-AUDIBLE"
)
TRANSFORM = "SIX_FIXED_OSCILLATOR_CARRIERS"
ENERGY_POLICY = "SQRT_ENERGY_FIXED_REFERENCE"
AUTHORITY_CLASS = "PLAYBACK_DERIVED_NON_PHYSICAL"

REQUIRED_C0_PROFILE = "ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1"
REQUIRED_PROBE_SCHEMA = "OBSERVER_ACOUSTIC_PROBE_V1"

BAND_COUNT = 6
BAND_IDENTIFIERS = tuple(f"band_{i}" for i in range(BAND_COUNT))

# Playback coordinates only — NOT physical band centres / simulated Hz.
# Spaced for human distinguishability under mono monitoring; conservative
# mid-range to avoid uncomfortable extremes. Changing values ⇒ new profile.
CANONICAL_PLAYBACK_CARRIER_HZ = (120.0, 200.0, 320.0, 480.0, 720.0, 1000.0)

FIXED_REFERENCE_GAIN = 0.25
CANONICAL_SECONDS_PER_TICK = 0.05
CANONICAL_SECONDS_PER_TICK_IS_PHYSICAL = False
PLAYBACK_TIME_SCALE_DEFAULT = 1.0
PLAYBACK_TIME_SCALE_OPTIONS = (0.25, 0.5, 1.0, 2.0)
INPUT_QUEUE_CAPACITY = 64
SCHEDULED_HORIZON_SECONDS = 0.5
ENVELOPE_FRACTION_OF_TICK = 0.2  # linear ramp duration = fraction * tick_duration
MASTER_DEFAULT_VOLUME = 0.35
LIMITER_THRESHOLD = 0.95
MAX_POLICY = "MAX_PLAYBACK_MUTED_BY_POLICY"
FAST_POLICY = "FAST_PLAYBACK_LOSSY_MONITORING"
ORIGINAL_HUMAN_AUDIBLE_AVAILABLE = False
LEGACY_UNAVAILABLE = "CANONICAL_SONIFICATION_UNAVAILABLE_LEGACY_EVIDENCE"

CARRIER_RATIONALE = (
    "Six distinct mid-range playback carriers with roughly geometric spacing "
    "for band distinguishability. Values are device-Hz monitoring coordinates "
    "only; they are not physical frequency centres and do not imply Earth acoustics."
)

_C1_PAYLOAD: dict[str, Any] = {
    "schema": SCHEMA,
    "contract": CONTRACT_ID,
    "profile": PROFILE,
    "capability": CAPABILITY,
    "mode": MODE,
    "mode_label": MODE_LABEL,
    "warning_label": WARNING_LABEL,
    "researcher_only": True,
    "agent_accessible": False,
    "physical_mechanism": False,
    "physical_preset": False,
    "acoustic_source": False,
    "lps_receiver": False,
    "audio_renderer_location": "OBSERVER_FRONTEND_ONLY",
    "authority_class": AUTHORITY_CLASS,
    "required_c0_profile": REQUIRED_C0_PROFILE,
    "required_probe_schema": REQUIRED_PROBE_SCHEMA,
    "transform": TRANSFORM,
    "band_count": BAND_COUNT,
    "band_identifiers": list(BAND_IDENTIFIERS),
    "canonical_playback_carrier_hz": list(CANONICAL_PLAYBACK_CARRIER_HZ),
    "carrier_label": "PLAYBACK CARRIERS — NOT PHYSICAL FREQUENCIES",
    "carrier_hz_are_physical": False,
    "carrier_rationale": CARRIER_RATIONALE,
    "mono_or_stereo": "MONO",
    "energy_to_amplitude_policy": ENERGY_POLICY,
    "fixed_reference_gain": FIXED_REFERENCE_GAIN,
    "zero_field_is_silence": True,
    "per_event_normalization": False,
    "automatic_gain_control": False,
    "canonical_seconds_per_tick": CANONICAL_SECONDS_PER_TICK,
    "canonical_seconds_per_tick_is_physical": CANONICAL_SECONDS_PER_TICK_IS_PHYSICAL,
    "playback_time_scale_default": PLAYBACK_TIME_SCALE_DEFAULT,
    "playback_time_scale_options": list(PLAYBACK_TIME_SCALE_OPTIONS),
    "envelope": {
        "shape": "LINEAR_RAMP",
        "fraction_of_tick": ENVELOPE_FRACTION_OF_TICK,
        "note": "Suppresses clicks; derived from probe sequence only; no semantic branches.",
    },
    "input_queue_capacity": INPUT_QUEUE_CAPACITY,
    "scheduled_horizon_seconds": SCHEDULED_HORIZON_SECONDS,
    "drop_policy": "DROP_OLDEST_WITH_COUNTER",
    "master_default_volume": MASTER_DEFAULT_VOLUME,
    "limiter_threshold": LIMITER_THRESHOLD,
    "max_policy": MAX_POLICY,
    "fast_policy": FAST_POLICY,
    "realtime_policy": "BOUNDED_QUEUE_SCHEDULE",
    "pause_policy": "STOP_NEW_SCHEDULES_RAMP_SILENCE",
    "step_policy": "ONE_NEW_SAMPLE_ONCE",
    "enable_mid_run_policy": "NEXT_SAMPLE_ONLY",
    "restore_policy": "CLEAR_QUEUE_NO_HISTORICAL_REPLAY",
    "probe_move_policy": "CLEAR_OR_SEGMENT_QUEUE",
    "original_human_audible_available": ORIGINAL_HUMAN_AUDIBLE_AVAILABLE,
    "legacy_without_probe_policy": LEGACY_UNAVAILABLE,
    "deterministic_transform_schedule": True,
    "bit_identical_device_waveform_required": False,
    "playback_throttles_simulation": False,
    "consumes": {
        "probe_samples": True,
        "c0_metadata": True,
        "acoustic_stream_directly": False,
        "lps_directly_in_frontend": False,
        "organism_osc_channels": False,
        "pixels": False,
        "semantic_source_labels": False,
    },
}


def c1_profile_payload() -> dict[str, Any]:
    return copy.deepcopy(_C1_PAYLOAD)


def c1_profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "contract": CONTRACT_ID,
        "profile": PROFILE,
        "capability": CAPABILITY,
        "mode": MODE,
        "mode_label": MODE_LABEL,
        "warning_label": WARNING_LABEL,
        "authority_class": AUTHORITY_CLASS,
        "required_c0_profile": REQUIRED_C0_PROFILE,
        "required_probe_schema": REQUIRED_PROBE_SCHEMA,
        "transform": TRANSFORM,
        "band_count": BAND_COUNT,
        "canonical_playback_carrier_hz": list(CANONICAL_PLAYBACK_CARRIER_HZ),
        "carrier_label": "PLAYBACK CARRIERS — NOT PHYSICAL FREQUENCIES",
        "carrier_hz_are_physical": False,
        "energy_to_amplitude_policy": ENERGY_POLICY,
        "fixed_reference_gain": FIXED_REFERENCE_GAIN,
        "canonical_seconds_per_tick": CANONICAL_SECONDS_PER_TICK,
        "canonical_seconds_per_tick_is_physical": False,
        "mono_or_stereo": "MONO",
        "researcher_only": True,
        "agent_accessible": False,
        "original_human_audible_available": False,
    }


def observer_c1_status() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "mode_label": MODE_LABEL,
        "warning_label": WARNING_LABEL,
        "available": True,
        "implemented": True,
        "audio_playback_location": "OBSERVER_FRONTEND",
        "original_human_audible_available": False,
        "carrier_label": "PLAYBACK CARRIERS — NOT PHYSICAL FREQUENCIES",
        "status_lines": [
            f"Listening mode: {MODE_LABEL}",
            WARNING_LABEL,
            f"C1 profile: {PROFILE}",
            "Transform: SIX_FIXED_OSCILLATOR_CARRIERS · mono",
            "Energy→amplitude: SQRT_ENERGY_FIXED_REFERENCE",
            "ORIGINAL / HUMAN-AUDIBLE: NOT AVAILABLE",
        ],
    }


def map_energy_to_amplitude(
    energies: list[float] | tuple[float, ...] | None,
    *,
    reference_gain: float | None = None,
) -> dict[str, Any]:
    """Pure mapping. Does not mutate input. Playback-only."""
    g = float(FIXED_REFERENCE_GAIN if reference_gain is None else reference_gain)
    src = list(energies or [])
    amps: list[float] = []
    clamped = 0
    for i in range(BAND_COUNT):
        raw = src[i] if i < len(src) else 0.0
        try:
            v = float(raw)
        except (TypeError, ValueError):
            v = 0.0
            clamped += 1
        if v != v or v == float("inf") or v == float("-inf"):  # NaN/Inf
            v = 0.0
            clamped += 1
        if v < 0.0:
            v = 0.0
            clamped += 1
        a = g * (v ** 0.5)
        if a != a or a == float("inf"):
            a = 0.0
            clamped += 1
        if a < 0.0:
            a = 0.0
            clamped += 1
        amps.append(float(a))
    return {
        "mapped_amplitudes": amps,
        "invalid_clamped": clamped,
        "policy": ENERGY_POLICY,
        "fixed_reference_gain": g,
        "authority_class": AUTHORITY_CLASS,
    }


def c0_c1_compatible(c0_profile: str | None, probe_schema: str | None) -> bool:
    return (
        str(c0_profile or "") == REQUIRED_C0_PROFILE
        and str(probe_schema or "") == REQUIRED_PROBE_SCHEMA
    )
