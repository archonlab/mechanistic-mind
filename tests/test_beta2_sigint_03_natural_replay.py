"""BETA2-SIGINT-03: natural signal specimen capture, replay, echo probes."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    TRIGGER_EXTERNAL,
    audit_observation_no_intervention_leak,
    find_matched_s0,
    fingerprint_equal,
    first_divergences,
    make_signal_runtime,
    receiver_local_fields,
    scientific_fingerprint,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
    NOT_RECORDED,
    TRIGGER_NATURAL_REPLAY,
    NaturalSignalLibrary,
    NaturalSignalSpecimen,
    build_response_fingerprint,
    capture_natural_emissions_from_runtime,
    harvest_field_a_specimens,
    queue_natural_replay,
    run_echo_experiment,
    run_fidelity_gate,
    run_natural_replay_branch,
    specimen_from_emission_evidence,
)


def test_natural_signal_capture_and_immutability():
    rt = make_signal_runtime(seed=17)
    lib = NaturalSignalLibrary(maxlen=32)
    found = []
    for _ in range(80):
        rt.step()
        found.extend(capture_natural_emissions_from_runtime(rt, run_id="t", library=lib))
    assert found, "expected natural emissions"
    sp = found[0]
    assert isinstance(sp, NaturalSignalSpecimen)
    assert sp.provenance == "NATURAL_EMISSION"
    with pytest.raises(FrozenInstanceError):
        sp.amplitude = 99  # type: ignore[misc]
    again = lib.add(sp)
    assert again.specimen_id == sp.specimen_id
    assert len([x for x in lib.list() if x["specimen_id"] == sp.specimen_id]) == 1


def test_specimen_physical_reconstruction_and_exact_replay():
    specs = harvest_field_a_specimens(seed=17, max_steps=120, max_specimens=3)
    assert specs
    sp = next(
        (s for s in specs if s.reconstruction_completeness == "CELLS_AND_AMPLITUDE"),
        specs[0],
    )
    assert sp.amplitude != NOT_RECORDED
    fid = run_fidelity_gate(sp, seed=17)
    assert fid["accepted"]
    assert fid["fidelity"] in (
        "EXACT_PHYSICAL_REPLAY",
        "APPROXIMATE_PHYSICAL_REPLAY",
    )
    rt = make_signal_runtime(seed=19)
    for _ in range(25):
        rt.step()
    before = receiver_local_fields(rt, 1)
    q = queue_natural_replay(
        rt, sp, mode="EXACT", target="PEER", receiver_slot=1,
        observer_source_id="unit",
    )
    assert q["accepted"]
    assert q["trigger"] == TRIGGER_NATURAL_REPLAY
    rt.step()
    after = receiver_local_fields(rt, 1)
    assert after["FIELD_A"] >= before["FIELD_A"]
    sources = (rt.last_signal_receipt or {}).get("sources") or []
    assert any(s.get("trigger") == TRIGGER_NATURAL_REPLAY for s in sources)


def test_cognition_metadata_boundary_on_natural_replay():
    specs = harvest_field_a_specimens(seed=17, max_steps=100, max_specimens=2)
    sp = specs[0]
    rt = make_signal_runtime(seed=17)
    for _ in range(30):
        rt.step()
    queue_natural_replay(
        rt, sp, mode="EXACT", target="PEER", receiver_slot=1,
        observer_source_id=f"specimen:{sp.specimen_id}",
    )
    rt.step()
    rt.step()
    for slot in rt.slots:
        obs = slot.last_agent_observation or {}
        assert audit_observation_no_intervention_leak(obs) == []
        blob = json.dumps(obs)
        assert sp.specimen_id not in blob
        assert "NATURAL_SIGNAL_REPLAY" not in blob
        assert "specimen:" not in blob


def test_control_control_and_sham_natural_replay():
    specs = harvest_field_a_specimens(seed=17, max_steps=100, max_specimens=2)
    sp = specs[0]
    s0 = find_matched_s0(
        seed=17, receiver="agent_1", pre_action="WAIT",
        pre_selection_source="RETAINED_PREDICTION", require_no_contact=True,
        max_search=500, min_age=30,
    )
    if s0 is None:
        pytest.skip("no matched S0")
    snap = s0["snapshot"]
    slot = s0["receiver_slot"]
    c1 = run_natural_replay_branch(
        snap, sp, receiver_slot=slot, horizon=12,
        experiment_id="e", intervention_id="i", kind="CONTROL",
    )
    c2 = run_natural_replay_branch(
        snap, sp, receiver_slot=slot, horizon=12,
        experiment_id="e", intervention_id="i", kind="CONTROL",
    )
    assert fingerprint_equal(c1["pre_fingerprint"], c2["pre_fingerprint"])
    assert all(
        fingerprint_equal(a["fingerprint"], b["fingerprint"])
        for a, b in zip(c1["traces"], c2["traces"])
    )
    sham = run_natural_replay_branch(
        snap, sp, receiver_slot=slot, horizon=12,
        experiment_id="e", intervention_id="i", kind="SHAM", target="PEER",
    )
    replay = run_natural_replay_branch(
        snap, sp, receiver_slot=slot, horizon=12,
        experiment_id="e", intervention_id="i", kind="NATURAL_REPLAY", target="PEER",
    )
    div_sham = first_divergences(c1, sham)
    div_rep = first_divergences(c1, replay)
    # Sham should not create FIELD exposure divergence on observation_field when amp=0
    # (may still be identical to control)
    assert div_sham.get("observation_field") is None or div_rep.get("observation_field") is not None


def test_self_peer_location_echo_and_fingerprint():
    specs = harvest_field_a_specimens(seed=17, max_steps=120, max_specimens=2)
    sp = specs[0]
    peer = run_echo_experiment(
        sp, echo_kind="PEER_ECHO", seeds=(17,), horizon=12, include_generic=True,
    )
    self_e = run_echo_experiment(
        sp, echo_kind="SELF_ECHO", seeds=(17,), horizon=12, include_generic=False,
    )
    assert peer["fidelity_gate"]["fidelity"] != "INSUFFICIENT_RECONSTRUCTION" or peer["trials"]
    fp = build_response_fingerprint(
        specimen=sp, echo_result=peer, context_label="unit",
    )
    assert fp["honesty"]["not_a_meaning_map"] is True
    assert "FIELD_exposure" in fp
    assert self_e["echo_kind"] == "SELF_ECHO"

    # LOCATION replay path
    rt = make_signal_runtime(seed=21)
    for _ in range(20):
        rt.step()
    q = queue_natural_replay(rt, sp, mode="EXACT", target="LOCATION")
    assert q["accepted"] or q.get("error") == "INSUFFICIENT_RECONSTRUCTION"


def test_altered_replay_provenance():
    specs = harvest_field_a_specimens(seed=17, max_steps=100, max_specimens=1)
    sp = specs[0]
    rt = make_signal_runtime(seed=17)
    for _ in range(20):
        rt.step()
    q_ch = queue_natural_replay(rt, sp, mode="ALTER_CHANNEL", target="PEER", receiver_slot=1)
    assert q_ch["accepted"]
    assert q_ch["channel"] != sp.channel
    rt2 = make_signal_runtime(seed=17)
    for _ in range(20):
        rt2.step()
    q_amp = queue_natural_replay(
        rt2, sp, mode="ALTER_AMPLITUDE", amplitude_scale=0.5, target="PEER", receiver_slot=1,
    )
    assert q_amp["accepted"]
    assert abs(float(q_amp["amplitude"]) - float(sp.amplitude) * 0.5) < 1e-6


def test_live_replay_marked_uncontrolled():
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment({
        "seed": 17,
        "agent_count": 2,
        "cognition_enabled": True,
        "speed": 50.0,
        "mechanisms": {"experimental_physical_signal": True},
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
    })
    specs = harvest_field_a_specimens(seed=17, max_steps=80, max_specimens=1)
    sp = specs[0]
    lib = sess._ensure_specimen_library()
    lib.add(sp)
    r = sess.replay_signal_specimen_live(sp.specimen_id, target="PEER", mode="EXACT")
    assert r.get("status") == "UNCONTROLLED_LIVE_REPLAY"
    assert r.get("accepted") is True


def test_specimen_from_incomplete_evidence():
    sp = specimen_from_emission_evidence(
        {"channel": "A", "emission_id": "e1"}, run_id="r", tick=1,
    )
    assert sp.amplitude == NOT_RECORDED
    assert sp.reconstruction_completeness in (
        NOT_RECORDED,
        "NOT_RECONSTRUCTABLE",
        "POSITION_ONLY",
    )


def test_sigint02_regression_external_still_works():
    rt = make_signal_runtime(seed=17)
    for _ in range(30):
        rt.step()
    before = receiver_local_fields(rt, 1)["FIELD_A"]
    from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
        receiver_footprint_cells,
    )
    rt.inject_source(
        channel="A", amplitude=1.0, cells=receiver_footprint_cells(rt, 1),
        trigger=TRIGGER_EXTERNAL, observer_source_id="reg",
    )
    rt.step()
    assert receiver_local_fields(rt, 1)["FIELD_A"] > before
