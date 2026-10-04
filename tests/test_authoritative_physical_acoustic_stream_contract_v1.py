"""AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_CONTRACT_V1 — focused contract tests.

Read-only scientific stream over existing physical acoustic emissions.
No playback / Hz / probe / new sources.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from mechanistic_mind.model.acanthostega import acanthostega_local_signal_config
from mechanistic_mind.physical_system import local_physical_signal_transport as lps
from mechanistic_mind.physical_system.authoritative_physical_acoustic_stream_contract import (
    CONTRACT_ID,
    HISTORY_CAPACITY_DEFAULT,
    LEGACY_OSC_BANDS_AUTHORITY,
    MECH_CONTACT,
    MECH_OSC_EMIT,
    RECORD_FAMILY,
    SCHEMA,
    collect_candidate_emissions,
    ensure_acoustic_stream_state,
    observer_payload,
    rebuild_stream_from_histories,
    restore_state,
    serialize_state,
    sort_key_for_record,
    state_of,
    sync_acoustic_stream,
)
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
    ContactAcousticState,
    ContactAcousticConfig,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.scientific_v3.authoritative_physical_acoustic_stream_summary import (
    summarize_authoritative_physical_acoustic_stream,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "acanthostega_authoritative_physical_acoustic_stream_contract_v1"
RESULTS.mkdir(parents=True, exist_ok=True)

# Global tick budget accounting for this module (reported in FINAL_REPORT).
TICKS_USED = 0


def _bump(n: int) -> None:
    global TICKS_USED
    TICKS_USED += int(n)


def _fake_emission(
    *,
    eid: str,
    tick: int,
    mechanism: str,
    energy: float = 1.0,
    x: float = 1.0,
    y: float = 2.0,
    bands: list[float] | None = None,
    **extra,
) -> dict:
    bands = bands or [energy / 6.0] * 6
    base = {
        "emission_id": eid,
        "emission_tick": tick,
        "emitted_energy": energy,
        "anonymous_band_vector": bands,
        "band_profile": "UNIFORM_BROADBAND_V1",
        "position": [x, y],
        "mechanism": mechanism,
        "lps_enqueue_status": "EMITTED",
    }
    base.update(extra)
    return base


class _World:
    pass


def test_01_schema_and_forbidden_tokens():
    assert SCHEMA == "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_V1"
    assert CONTRACT_ID == "authoritative_physical_acoustic_stream"
    assert RECORD_FAMILY == "PHYSICAL_ACOUSTIC_STREAM_RECORD"
    required = [
        "body_resource_object_impact_acoustic_emission",
        "resource_object_pair_impact_acoustic_emission",
        "vertical_impact_acoustic_emission",
        "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_V1",
        "PHYSICAL_ACOUSTIC_STREAM_RECORD",
        "authoritative_physical_acoustic_stream",
        "stream_record_id",
    ]
    for tok in required:
        assert tok in FORBIDDEN_TOKENS
    # Anonymous organism channels must remain allowed as channel names in cognition.
    assert "osc_l_0" not in FORBIDDEN_TOKENS
    assert "osc_r_0" not in FORBIDDEN_TOKENS


def test_02_deterministic_ordering_and_multi_source_same_tick():
    w = _World()
    st = ensure_acoustic_stream_state(w, capacity=32)
    # Plant mechanism histories directly (no physics).
    st_contact = ContactAcousticState(config=ContactAcousticConfig())
    st_contact.emission_history = [
        _fake_emission(eid="e-contact-a", tick=5, mechanism=MECH_CONTACT, energy=0.5, x=1, y=1,
                       canonical_body_pair=["a0", "a1"]),
        _fake_emission(eid="e-contact-b", tick=5, mechanism=MECH_CONTACT, energy=0.4, x=2, y=2,
                       canonical_body_pair=["a2", "a3"]),
    ]
    w.contact_acoustic_state = st_contact

    class _LPS:
        emission_history = [
            {
                "emission_id": "e-osc-1",
                "emission_tick": 5,
                "total_emitted_energy": 0.3,
                "anonymous_band_energies": [0.05] * 6,
                "selection_provenance": "ENDOGENOUS_MOTOR",
                "source_body_id": "a0",
                "physical_origin": {"x": 3.0, "y": 3.0},
                "motor_provenance": {"command_family": "OSC_EMIT", "emit_remaining_before": 2},
                "status": "EMITTED",
            }
        ]

    w.local_signal_transport = _LPS()
    w.OSC_BANDS = {"should": "be_ignored"}

    r1 = sync_acoustic_stream(w, scientific_tick=5)
    assert r1["new_records"] == 3
    ids = [r["source_receipt_event_id"] for r in st.records]
    assert ids == ["e-contact-a", "e-contact-b", "e-osc-1"]
    assert [r["source_mechanism_id"] for r in st.records] == [
        MECH_CONTACT,
        MECH_CONTACT,
        MECH_OSC_EMIT,
    ]
    # Idempotent re-sync (Observer polling / mode change).
    r2 = sync_acoustic_stream(w, scientific_tick=5)
    assert r2["new_records"] == 0
    assert len(st.records) == 3
    # Legacy OSC_BANDS never ingested as records.
    assert all(r["source_mechanism_id"] != "OSC_BANDS" for r in st.records)
    assert LEGACY_OSC_BANDS_AUTHORITY.startswith("NON_AUTHORITATIVE")


def test_03_silent_receipts_not_in_stream():
    w = _World()
    ensure_acoustic_stream_state(w, capacity=16)
    # Measurement-only / silent rows live in measurement_history, not emission_history.
    class _VIA:
        emission_history = []
        measurement_history = [
            {"emitted": False, "silence_reason": "PERSIST", "tick": 1},
        ]

    w.vertical_impact_acoustic_emission_state = _VIA()
    w.local_signal_transport = type("L", (), {"emission_history": []})()
    out = sync_acoustic_stream(w, scientific_tick=1)
    assert out["new_records"] == 0
    assert state_of(w).records == []


def test_04_bounded_eviction_and_serialize_restore():
    w = _World()
    st = ensure_acoustic_stream_state(w, capacity=8)
    ca = ContactAcousticState(config=ContactAcousticConfig())
    ca.emission_history = [
        _fake_emission(eid=f"e{i}", tick=i, mechanism=MECH_CONTACT, energy=0.1 * (i + 1),
                       canonical_body_pair=["a", "b"])
        for i in range(12)
    ]
    w.contact_acoustic_state = ca
    w.local_signal_transport = type("L", (), {"emission_history": []})()
    sync_acoustic_stream(w, scientific_tick=11)
    assert len(st.records) == 8
    assert st.evicted_count == 4
    assert [r["source_receipt_event_id"] for r in st.records] == [f"e{i}" for i in range(4, 12)]

    blob = serialize_state(st)
    w2 = _World()
    restore_state(w2, blob)
    st2 = state_of(w2)
    assert st2 is not None
    assert [r["stream_record_id"] for r in st2.records] == [r["stream_record_id"] for r in st.records]
    assert st2.evicted_count == 4
    # Re-sync must not duplicate after restore.
    w2.contact_acoustic_state = ca
    w2.local_signal_transport = type("L", (), {"emission_history": []})()
    again = sync_acoustic_stream(w2, scientific_tick=11)
    assert again["new_records"] == 0


def test_05_privacy_audit_stream_metadata():
    payload = {
        "schema": SCHEMA,
        "stream_record_id": "apas:e1",
        "source_mechanism_id": "body_resource_object_impact_acoustic_emission",
        "emitted_energy": 1.0,
    }
    hits = audit_cognition_payload(payload)
    assert hits, "researcher stream metadata must be forbidden in cognition"
    # Legitimate anonymous auditory channels alone are fine.
    clean = {"osc_l_0": 0.1, "osc_r_0": 0.05, "osc_l_1": 0.0}
    assert audit_cognition_payload(clean) == []


def test_06_observer_payload_no_playback_fields():
    w = _World()
    ensure_acoustic_stream_state(w)
    sync_acoustic_stream(w, scientific_tick=0)
    payload = observer_payload(w)
    assert payload is not None
    assert payload["audio_playback"] is False
    assert payload["human_hz_calibration"] == "NOT_ESTABLISHED"
    assert "Play Audio" not in str(payload)
    assert "volume" not in payload


def test_07_runtime_lps_osc_emit_enters_stream_once():
    global TICKS_USED
    cfg = acanthostega_local_signal_config()
    rt = PhysicalSystemRuntime(seed=11, config=cfg)
    body = rt.body
    body.osc_emit_remaining = 3
    body.osc_freq_u = 0.5
    body.osc_amp_u = 0.8
    before_hist_n = len(list(rt.world.local_signal_transport.emission_history or []))
    # Each step increments tick and runs LPS end-of-tick once.
    for _ in range(3):
        rt.step()
        _bump(1)
    st = state_of(rt.world)
    assert st is not None
    osc_rows = [r for r in st.records if r["source_mechanism_id"] == MECH_OSC_EMIT]
    assert len(osc_rows) >= 1
    # Duplicate emission_ids must not appear.
    eids = [r["lps_emission_id"] for r in st.records]
    assert len(eids) == len(set(eids))
    # Re-read observer payload repeatedly without growing.
    n0 = len(st.records)
    for _ in range(5):
        observer_payload(rt.world)
    assert len(st.records) == n0
    assert int(rt.tick) == 3
    after_hist = list(rt.world.local_signal_transport.emission_history)
    endogenous = [e for e in after_hist if e.get("selection_provenance") == "ENDOGENOUS_MOTOR"]
    assert len(osc_rows) == len(endogenous) or len(endogenous) >= len(osc_rows)
    assert len(after_hist) >= before_hist_n
    import json

    snap = json.loads(json.dumps(rt.snapshot()))
    n_before = len(st.records)
    ids_before = [r["stream_record_id"] for r in st.records]
    rt2 = PhysicalSystemRuntime.restore(snap)
    st2 = state_of(rt2.world)
    assert st2 is not None
    assert len(st2.records) == n_before
    assert [r["stream_record_id"] for r in st2.records] == ids_before


def test_08_analyzer_summary_progress_honest():
    records = [
        {
            "stream_record_id": "apas:e1",
            "stream_sequence": 0,
            "scientific_tick": 1,
            "source_mechanism_id": MECH_CONTACT,
            "source_receipt_event_id": "e1",
            "emitted_energy": 1.0,
            "lps_emission_id": "e1",
            "lps_admitted": True,
        }
    ]
    s = summarize_authoritative_physical_acoustic_stream(
        records, meta={"history_capacity": 96, "evicted_count": 0, "retained_count": 1}
    )
    assert s["record_count"] == 1
    assert s["audio_playback"] is False
    prog = s["progress"]
    assert prog["completed"] == 1
    assert prog["total"] == 1
    assert prog["percent"] == 100.0


def test_09_sort_key_stable_independent_of_insertion():
    a = _fake_emission(eid="z", tick=1, mechanism=MECH_CONTACT, canonical_body_pair=["b", "c"])
    b = _fake_emission(eid="a", tick=1, mechanism=MECH_CONTACT, canonical_body_pair=["a", "b"])
    pairs = [(MECH_CONTACT, a), (MECH_CONTACT, b)]
    pairs.sort(key=lambda p: sort_key_for_record(p[0], p[1]))
    assert pairs[0][1]["emission_id"] == "a" or pairs[0][1]["canonical_body_pair"][0] == "a"


def test_10_write_tick_budget_receipt(tmp_path=None):
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "TICK_BUDGET.txt").write_text(
        f"TOTAL_SIMULATED_TICKS_IN_STREAM_CONTRACT_TESTS={TICKS_USED}\n",
        encoding="utf-8",
    )
    assert TICKS_USED <= 40
