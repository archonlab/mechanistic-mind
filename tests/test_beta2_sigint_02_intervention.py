"""BETA2-SIGINT-02: controlled field intervention tests."""
from __future__ import annotations

import json
from copy import deepcopy

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    TRIGGER_EXTERNAL,
    BranchArm,
    FieldPattern,
    audit_observation_no_intervention_leak,
    find_matched_s0,
    fingerprint_equal,
    first_divergences,
    make_signal_runtime,
    receiver_footprint_cells,
    receiver_local_fields,
    run_branch,
    scientific_fingerprint,
    stable_id,
)


def test_snapshot_restore_exact_equivalence():
    rt = make_signal_runtime(seed=17)
    for _ in range(40):
        rt.step()
    snap = rt.snapshot()
    a = TwoAgentRuntime.restore(deepcopy(snap))
    b = TwoAgentRuntime.restore(deepcopy(snap))
    assert fingerprint_equal(scientific_fingerprint(a), scientific_fingerprint(b))
    assert a.tick == rt.tick
    assert float(a.world.FIELD_A.sum()) == float(rt.world.FIELD_A.sum())


def test_rng_and_cognition_restore():
    rt = make_signal_runtime(seed=19)
    for _ in range(55):
        rt.step()
    snap = rt.snapshot()
    r1 = TwoAgentRuntime.restore(deepcopy(snap))
    r2 = TwoAgentRuntime.restore(deepcopy(snap))
    for _ in range(10):
        r1.step()
        r2.step()
    assert fingerprint_equal(scientific_fingerprint(r1), scientific_fingerprint(r2))


def test_signal_field_restoration():
    rt = make_signal_runtime(seed=17)
    rt.inject_source(channel="A", amplitude=0.9, iy=10, ix=10, trigger="environmental")
    rt.step()
    assert float(rt.world.FIELD_A.sum()) > 0
    snap = rt.snapshot()
    r = TwoAgentRuntime.restore(deepcopy(snap))
    assert abs(float(r.world.FIELD_A.sum()) - float(rt.world.FIELD_A.sum())) < 1e-9
    assert len(r._pending_sources) == 0


def test_control_control_branch_equality_and_no_pre_divergence():
    rt = make_signal_runtime(seed=17)
    for _ in range(60):
        rt.step()
    snap = rt.snapshot()
    c1 = run_branch(
        snap, BranchArm("C1", "CONTROL"), receiver_slot=1, horizon=12,
        experiment_id="e", intervention_id="i",
    )
    c2 = run_branch(
        snap, BranchArm("C2", "CONTROL"), receiver_slot=1, horizon=12,
        experiment_id="e", intervention_id="i",
    )
    assert fingerprint_equal(c1["pre_fingerprint"], c2["pre_fingerprint"])
    assert all(
        fingerprint_equal(a["fingerprint"], b["fingerprint"])
        for a, b in zip(c1["traces"], c2["traces"])
    )


def test_external_field_enters_normal_path_and_exposure():
    rt = make_signal_runtime(seed=17)
    for _ in range(30):
        rt.step()
    cells = receiver_footprint_cells(rt, 1)
    before = receiver_local_fields(rt, 1)["FIELD_A"]
    rt.inject_source(
        channel="A", amplitude=1.0, cells=cells,
        trigger=TRIGGER_EXTERNAL, observer_source_id="test",
    )
    rt.step()
    after = receiver_local_fields(rt, 1)["FIELD_A"]
    assert after > before
    sources = (rt.last_signal_receipt or {}).get("sources") or []
    assert any(s.get("trigger") == TRIGGER_EXTERNAL for s in sources)


def test_cognition_receives_no_intervention_metadata():
    rt = make_signal_runtime(seed=17)
    for _ in range(25):
        rt.step()
    cells = receiver_footprint_cells(rt, 0)
    rt.inject_source(
        channel="A", amplitude=0.8, cells=cells,
        trigger=TRIGGER_EXTERNAL, observer_source_id="exp:secret",
    )
    rt.step()
    rt.step()
    for slot in rt.slots:
        obs = slot.last_agent_observation or {}
        assert audit_observation_no_intervention_leak(obs) == []
        assert "exp:secret" not in json.dumps(obs)
        assert "EXTERNAL" not in json.dumps(obs)


def test_field_a_b_sham_wrong_channel():
    rt = make_signal_runtime(seed=17)
    for _ in range(50):
        rt.step()
    snap = rt.snapshot()
    pat = FieldPattern(channel="A", amplitude=0.8, duration_ticks=3, temporal_profile=[1, 1, 1])
    control = run_branch(
        snap, BranchArm("CONTROL", "CONTROL"), receiver_slot=1, horizon=10,
        experiment_id="e", intervention_id="i",
    )
    inter = run_branch(
        snap, BranchArm("INTERVENTION", "INTERVENTION", pattern=deepcopy(pat)),
        receiver_slot=1, horizon=10, experiment_id="e", intervention_id="i",
    )
    sham = run_branch(
        snap, BranchArm("SHAM", "SHAM", pattern=deepcopy(pat)),
        receiver_slot=1, horizon=10, experiment_id="e", intervention_id="i",
    )
    wrong = run_branch(
        snap, BranchArm("WRONG_CHANNEL", "WRONG_CHANNEL", pattern=deepcopy(pat)),
        receiver_slot=1, horizon=10, experiment_id="e", intervention_id="i",
    )
    pat_b = FieldPattern(channel="B", amplitude=0.8, duration_ticks=2)
    inter_b = run_branch(
        snap, BranchArm("INT_B", "INTERVENTION", pattern=pat_b),
        receiver_slot=1, horizon=8, experiment_id="e", intervention_id="i",
    )
    assert max(t["local_fields"]["FIELD_A"] for t in inter["traces"]) >= max(
        t["local_fields"]["FIELD_A"] for t in sham["traces"]
    )
    assert max(t["local_fields"]["FIELD_B"] for t in inter_b["traces"]) >= max(
        t["local_fields"]["FIELD_B"] for t in control["traces"]
    )
    assert max(t["local_fields"]["FIELD_B"] for t in wrong["traces"]) >= max(
        t["local_fields"]["FIELD_B"] for t in control["traces"]
    )


def test_stable_ids_and_zero_amp_null_effect():
    a = stable_id("sexp", "x", 1)
    b = stable_id("sexp", "x", 1)
    assert a == b
    rt = make_signal_runtime(seed=21)
    for _ in range(40):
        rt.step()
    snap = rt.snapshot()
    pat = FieldPattern(channel="A", amplitude=0.0, duration_ticks=2)
    control = run_branch(
        snap, BranchArm("C", "CONTROL"), receiver_slot=0, horizon=6,
        experiment_id="e", intervention_id="i",
    )
    zero = run_branch(
        snap, BranchArm("Z", "INTERVENTION", pattern=pat), receiver_slot=0, horizon=6,
        experiment_id="e", intervention_id="i",
    )
    div = first_divergences(control, zero)
    assert div.get("observation_field") is None


def test_find_matched_s0_and_branch_determinism():
    s0 = find_matched_s0(
        seed=17,
        receiver="agent_1",
        pre_action="WAIT",
        pre_selection_source="RETAINED_PREDICTION",
        require_no_contact=True,
        max_search=500,
        min_age=20,
    )
    if s0 is None:
        s0 = find_matched_s0(
            seed=17,
            receiver="agent_0",
            pre_action="MOVE:E",
            pre_selection_source="ENDOGENOUS_VARIATION",
            require_no_contact=True,
            max_search=400,
            min_age=20,
        )
    assert s0 is not None
    snap = s0["snapshot"]
    c1 = run_branch(
        snap, BranchArm("C", "CONTROL"), receiver_slot=s0["receiver_slot"], horizon=8,
        experiment_id="e", intervention_id="i",
    )
    c2 = run_branch(
        snap, BranchArm("C", "CONTROL"), receiver_slot=s0["receiver_slot"], horizon=8,
        experiment_id="e", intervention_id="i",
    )
    assert fingerprint_equal(c1["traces"][-1]["fingerprint"], c2["traces"][-1]["fingerprint"])


def test_observer_harness_import_does_not_alter_physics():
    a = make_signal_runtime(seed=17)
    b = make_signal_runtime(seed=17)
    for _ in range(30):
        a.step()
        b.step()
    assert fingerprint_equal(scientific_fingerprint(a), scientific_fingerprint(b))
