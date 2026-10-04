"""PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT_V1 — metadata-only tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from mechanistic_mind.physical_system.physical_frequency_amplitude_calibration_contract import (
    AUTHORITY_STAGE,
    BAND_COUNT,
    BAND_IDENTIFIERS,
    COMPAT_C0,
    COMPAT_FUTURE,
    COMPAT_MISSING,
    CONTRACT_ID,
    NE,
    NEXT_HONEST_LISTENING_MODE,
    PROFILE,
    SCHEMA,
    assert_no_invented_si_numerics,
    c0_calibration_payload,
    c0_calibration_reference,
    classify_calibration_metadata,
    legacy_calibration_stub,
    observer_calibration_status,
)
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.authoritative_physical_acoustic_stream_contract import (
    researcher_summary as stream_summary,
    ensure_acoustic_stream_state,
)
from mechanistic_mind.physical_system.observer_acoustic_probe import (
    researcher_summary as probe_summary,
    ensure_probe_state,
)
from mechanistic_mind.scientific_v3.physical_frequency_amplitude_calibration_summary import (
    summarize_acoustic_calibration,
)

RESULTS = Path(__file__).resolve().parents[1] / "results" / "acanthostega_physical_frequency_amplitude_calibration_contract_v1"


def test_01_exact_schema_and_no_si_numerics():
    p = c0_calibration_payload()
    assert p["schema"] == SCHEMA == "PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT_V1"
    assert p["contract"] == CONTRACT_ID
    assert p["profile"] == PROFILE == "ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1"
    assert p["authority_stage"] == AUTHORITY_STAGE
    assert p["band_count"] == BAND_COUNT == 6
    assert tuple(p["band_identifiers"]) == BAND_IDENTIFIERS
    assert p["physical_frequency_mapping"] == NE
    assert p["band_centre_frequencies_hz"] == NE
    assert p["time_authority"]["tick_duration_seconds"] == NE
    assert p["length_authority"]["cell_length_metres"] == NE
    assert p["emission_amplitude_authority"]["emission_energy_joules"] == NE
    assert p["point_field_authority"]["point_field_pressure_pa"] == NE
    assert p["spl_mapping"] == NE
    assert p["naming_restrictions"]["original_human_audible_available"] is False
    assert p["naming_restrictions"]["next_honest_listening_mode"] == NEXT_HONEST_LISTENING_MODE
    assert assert_no_invented_si_numerics(p) == []
    # Deterministic copies
    assert c0_calibration_payload() == p
    assert c0_calibration_reference()["profile"] == PROFILE


def test_02_single_authority_stream_probe_share_reference():
    class W:
        pass

    w = W()
    ensure_acoustic_stream_state(w)
    ensure_probe_state(w)
    s = stream_summary(w)
    p = probe_summary(w)
    assert s is not None and p is not None
    assert s["acoustic_calibration"] == p["acoustic_calibration"] == c0_calibration_reference()
    assert s["acoustic_calibration_status"]["profile"] == PROFILE
    assert p["acoustic_calibration_status"]["status_lines"][0].startswith("Calibration:")


def test_03_legacy_and_future_classification():
    assert classify_calibration_metadata(None) == COMPAT_MISSING
    assert classify_calibration_metadata({}) == COMPAT_MISSING
    assert classify_calibration_metadata(c0_calibration_reference()) == COMPAT_C0
    assert classify_calibration_metadata({"schema": SCHEMA, "profile": "FUTURE_SI_V9"}) == COMPAT_FUTURE
    stub = legacy_calibration_stub()
    assert stub["compatibility_class"] == COMPAT_MISSING
    assert "not silently rewritten" in stub["note"].lower() or "not silently" in stub["note"]


def test_04_privacy():
    for tok in (
        SCHEMA,
        CONTRACT_ID,
        PROFILE,
        AUTHORITY_STAGE,
        "acoustic_calibration",
        "CANONICAL PHYSICAL-FIELD SONIFICATION",
    ):
        assert tok in FORBIDDEN_TOKENS
    assert audit_cognition_payload({"osc_l_0": 0.2, "osc_r_1": 0.1}) == []
    hits = audit_cognition_payload(c0_calibration_reference())
    assert hits


def test_05_analyzer_summary_no_transform():
    s = summarize_acoustic_calibration([c0_calibration_reference()])
    assert s["physical_values_transformed"] is False
    assert s["original_human_audible_available"] is False
    assert s["progress"]["completed"] == 1
    assert s["progress"]["percent"] == 100.0


def test_06_serialization_stable():
    a = json.dumps(c0_calibration_payload(), sort_keys=True)
    b = json.dumps(c0_calibration_payload(), sort_keys=True)
    assert a == b
    # Mutating a returned copy must not corrupt authority
    p = c0_calibration_payload()
    p["band_count"] = 99
    assert c0_calibration_payload()["band_count"] == 6


def test_07_write_evidence():
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "C0_PAYLOAD.json").write_text(
        json.dumps(c0_calibration_payload(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (RESULTS / "TICK_BUDGET.txt").write_text("TOTAL_SIMULATED_TICKS=0\n", encoding="utf-8")
