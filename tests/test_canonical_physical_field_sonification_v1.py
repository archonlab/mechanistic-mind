"""CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1 — contract tests (≤40 ticks)."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.physical_system.canonical_physical_field_sonification import (
    BAND_COUNT,
    CANONICAL_PLAYBACK_CARRIER_HZ,
    CAPABILITY,
    ENERGY_POLICY,
    FIXED_REFERENCE_GAIN,
    MODE,
    MODE_LABEL,
    PROFILE,
    REQUIRED_C0_PROFILE,
    REQUIRED_PROBE_SCHEMA,
    SCHEMA,
    TRANSFORM,
    WARNING_LABEL,
    c0_c1_compatible,
    c1_profile_payload,
    map_energy_to_amplitude,
)
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.scientific_v3.canonical_physical_field_sonification_summary import (
    summarize_canonical_sonification,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "acanthostega_canonical_physical_field_sonification_v1"


def test_01_identity():
    p = c1_profile_payload()
    assert p["schema"] == SCHEMA == "CANONICAL_PHYSICAL_FIELD_SONIFICATION_V1"
    assert p["profile"] == PROFILE
    assert p["capability"] == CAPABILITY
    assert p["mode"] == MODE
    assert p["mode_label"] == MODE_LABEL
    assert p["transform"] == TRANSFORM
    assert p["required_c0_profile"] == REQUIRED_C0_PROFILE
    assert p["required_probe_schema"] == REQUIRED_PROBE_SCHEMA
    assert p["physical_mechanism"] is False
    assert p["physical_preset"] is False
    assert p["carrier_hz_are_physical"] is False
    assert p["band_count"] == BAND_COUNT == 6
    assert len(CANONICAL_PLAYBACK_CARRIER_HZ) == 6
    assert len(set(CANONICAL_PLAYBACK_CARRIER_HZ)) == 6
    assert WARNING_LABEL.startswith("TRANSFORMED PLAYBACK")


def test_02_amplitude_mapping():
    energies = [0.0, 1.0, 4.0, -2.0, float("nan"), 9.0]
    src = list(energies)
    m = map_energy_to_amplitude(energies)
    assert energies == src
    assert m["mapped_amplitudes"][0] == 0.0
    assert abs(m["mapped_amplitudes"][1] - FIXED_REFERENCE_GAIN * 1.0) < 1e-12
    assert abs(m["mapped_amplitudes"][2] - FIXED_REFERENCE_GAIN * 2.0) < 1e-12
    assert m["mapped_amplitudes"][3] == 0.0
    assert m["mapped_amplitudes"][4] == 0.0
    assert abs(m["mapped_amplitudes"][5] - FIXED_REFERENCE_GAIN * 3.0) < 1e-12
    assert m["policy"] == ENERGY_POLICY
    a = map_energy_to_amplitude([1, 0, 0, 0, 0, 0])
    b = map_energy_to_amplitude([4, 0, 0, 0, 0, 0])
    assert abs(b["mapped_amplitudes"][0] / a["mapped_amplitudes"][0] - 2.0) < 1e-12


def test_03_compatibility_and_privacy():
    assert c0_c1_compatible(REQUIRED_C0_PROFILE, REQUIRED_PROBE_SCHEMA)
    assert not c0_c1_compatible("X", REQUIRED_PROBE_SCHEMA)
    for tok in (
        SCHEMA,
        PROFILE,
        CAPABILITY,
        "canonical_playback_carrier_hz",
        "PLAYBACK_DERIVED_NON_PHYSICAL",
        MODE_LABEL,
    ):
        assert tok in FORBIDDEN_TOKENS
    assert audit_cognition_payload({"osc_l_0": 0.1}) == []
    assert audit_cognition_payload(c1_profile_payload())


def test_04_analyzer_progress():
    samples = [
        {"sample_key": "a", "scientific_tick": 1, "anonymous_band_energies": [1, 0, 0, 0, 0, 0]},
        {"sample_key": "b", "scientific_tick": 2, "anonymous_band_energies": [4, 0, 0, 0, 0, 0]},
    ]
    s = summarize_canonical_sonification(samples)
    assert s["available"] is True
    assert s["playback_affected_simulation"] is False
    assert s["progress"]["completed"] == 2
    assert s["progress"]["total"] == 2
    assert s["progress"]["percent"] == 100.0
    legacy = summarize_canonical_sonification([])
    assert legacy["status"] == "CANONICAL_SONIFICATION_UNAVAILABLE_LEGACY_EVIDENCE"
    assert legacy["progress"]["percent"] is None


def test_05_write_evidence():
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "C1_PAYLOAD.json").write_text(
        json.dumps(c1_profile_payload(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (RESULTS / "TICK_BUDGET.txt").write_text(
        "TOTAL_SIMULATED_TICKS=0\nVALIDATION_BUDGET_MAX=40\n",
        encoding="utf-8",
    )
