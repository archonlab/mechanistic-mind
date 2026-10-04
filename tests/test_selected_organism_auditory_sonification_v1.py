"""SELECTED_ORGANISM_AUDITORY_SONIFICATION_V1 — backend profile + privacy tests."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.selected_organism_auditory_sonification import (
    FIXED_RECEPTOR_GAIN,
    PROFILE,
    SCHEMA,
    map_receptor_activation,
    sav2_profile_payload,
)
from mechanistic_mind.physical_system.canonical_physical_field_sonification import (
    CANONICAL_PLAYBACK_CARRIER_HZ,
    map_energy_to_amplitude,
)
from mechanistic_mind.scientific_v3.selected_organism_auditory_sonification_summary import (
    summarize_selected_organism_auditory_sonification,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "acanthostega_selected_organism_auditory_sonification_v1"


def test_sav2_profile_identity_and_carriers():
    p = sav2_profile_payload()
    assert p["schema"] == SCHEMA
    assert p["profile"] == PROFILE
    assert p["c1_sqrt_energy_mapping_used"] is False
    assert p["c1_and_sav2_simultaneous_audio"] is False
    assert p["canonical_playback_carrier_hz"] == list(CANONICAL_PLAYBACK_CARRIER_HZ)
    assert p["playback_is_literal_organism_sound"] is False
    assert p["consumes_probe_samples"] is False
    assert audit_cognition_payload(p)  # privacy tokens hit


def test_linear_mapping_not_sqrt():
    left = [0.0, 0.25, 0.5, 1.0, 0.0, 0.0]
    right = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    m = map_receptor_activation(left, right)
    assert m["left_amplitudes"][0] == 0.0
    assert abs(m["left_amplitudes"][1] - FIXED_RECEPTOR_GAIN * 0.25) < 1e-12
    assert abs(m["left_amplitudes"][2] - FIXED_RECEPTOR_GAIN * 0.5) < 1e-12
    assert abs(m["left_amplitudes"][3] - FIXED_RECEPTOR_GAIN * 1.0) < 1e-12
    c1 = map_energy_to_amplitude([0.25, 0, 0, 0, 0, 0])
    assert abs(m["left_amplitudes"][1] - c1["mapped_amplitudes"][0]) > 1e-9


def test_analyzer_legacy_and_progress():
    empty = summarize_selected_organism_auditory_sonification([])
    assert empty["available"] is False
    assert empty["progress"]["percent"] is None
    rec = {
        "availability": "AVAILABLE",
        "receipt_id": "soab:x",
        "scientific_tick": 1,
        "agent_id": "agent_0",
        "body_id": "b0",
        "section_a_organism_accessible": {
            "left_receptor_channels": [1, 0, 0, 0, 0, 0],
            "right_receptor_channels": [0, 0.5, 0, 0, 0, 0],
        },
        "section_b_researcher_provenance": {"should_not_matter": True},
    }
    s = summarize_selected_organism_auditory_sonification([rec])
    assert s["available"] is True
    assert s["progress"]["percent"] == 100.0
    assert s["mind_reading"] is False
    assert s["schedule_preview"][0]["left_amplitudes"][0] == FIXED_RECEPTOR_GAIN


def test_write_profile_artifact():
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "sav2_profile.json").write_text(
        json.dumps(sav2_profile_payload(), indent=2, sort_keys=True),
        encoding="utf-8",
    )


def test_sav1_to_sav2_integration_passivity():
    """≤10 ticks: SAV2 mapping consumes Section A only; osc unchanged; C1 sqrt unused."""
    from mechanistic_mind.model.acanthostega import acanthostega_local_signal_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt import (
        observer_payload,
        state_of,
    )

    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=401, config=cfg)
    rt.technical_id = "agent_0"
    for _ in range(5):
        rt.step()
    st = state_of(rt.world)
    assert st is not None and st.receipts
    latest = st.receipts[-1]
    a = latest["section_a_organism_accessible"]
    left = list(a["left_receptor_channels"])
    right = list(a["right_receptor_channels"])
    obs = dict(rt.last_agent_observation or {})
    mapped = map_receptor_activation(left, right)
    # Section A unchanged
    assert a["left_receptor_channels"] == left
    assert a["right_receptor_channels"] == right
    # osc unchanged
    for i in range(6):
        assert abs(float(obs[f"osc_l_{i}"]) - float(left[i])) < 1e-12
    # researcher provenance ignored (mapping does not read it)
    assert "section_b_researcher_provenance" in latest
    assert mapped["policy"] == "LINEAR_RECEPTOR_ACTIVATION_FIXED_REFERENCE_V1"
    # observer payload still works
    pay = observer_payload(rt.world, selected_agent_id="agent_0")
    assert pay is not None


def test_two_agent_selection_filter_for_sav2():
    """≤15 ticks: only selected agent vectors map; switching does not alter A5."""
    from mechanistic_mind.model.acanthostega import acanthostega_local_signal_config
    from mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt import (
        observer_payload,
        state_of,
    )
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    cfg = acanthostega_local_signal_config()
    tr = TwoAgentRuntime(seed=402, config=cfg)
    for _ in range(6):
        tr.step()
    st = state_of(tr.world)
    assert st is not None
    by_agent = {}
    for r in st.receipts:
        by_agent.setdefault(r["agent_id"], []).append(r)
    assert "agent_0" in by_agent and "agent_1" in by_agent
    # Fingerprints before selection flip
    fp0 = [
        (r["receipt_id"], tuple(r["section_a_organism_accessible"]["left_receptor_channels"]))
        for r in by_agent["agent_0"]
    ]
    fp1 = [
        (r["receipt_id"], tuple(r["section_a_organism_accessible"]["left_receptor_channels"]))
        for r in by_agent["agent_1"]
    ]
    p0 = observer_payload(tr.world, selected_agent_id="agent_0")
    p1 = observer_payload(tr.world, selected_agent_id="agent_1")
    assert p0["latest_for_selected"]["agent_id"] == "agent_0"
    assert p1["latest_for_selected"]["agent_id"] == "agent_1"
    m0 = map_receptor_activation(
        p0["latest_for_selected"]["section_a_organism_accessible"]["left_receptor_channels"],
        p0["latest_for_selected"]["section_a_organism_accessible"]["right_receptor_channels"],
    )
    m1 = map_receptor_activation(
        p1["latest_for_selected"]["section_a_organism_accessible"]["left_receptor_channels"],
        p1["latest_for_selected"]["section_a_organism_accessible"]["right_receptor_channels"],
    )
    # Receipts unchanged after selection display switch
    assert [
        (r["receipt_id"], tuple(r["section_a_organism_accessible"]["left_receptor_channels"]))
        for r in by_agent["agent_0"]
    ] == fp0
    assert [
        (r["receipt_id"], tuple(r["section_a_organism_accessible"]["left_receptor_channels"]))
        for r in by_agent["agent_1"]
    ] == fp1
    assert m0["authority_class"] == "PLAYBACK_DERIVED_TRANSLATED_RECEPTOR_MONITOR"
    assert m1["authority_class"] == "PLAYBACK_DERIVED_TRANSLATED_RECEPTOR_MONITOR"
