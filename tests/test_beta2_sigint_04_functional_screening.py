"""BETA2-SIGINT-04: repertoire, families, two-stage screen, fingerprints."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.signal_context.functional_screening import (
    ScreenConfig,
    build_downstream_candidates,
    build_repertoire,
    build_response_fingerprints_screen,
    classify_from_trials,
    family_key_from_features,
    group_into_families,
    measure_latency_persistence,
    physical_feature_vector,
    prioritize_candidates,
    run_stage_a,
    run_stage_b,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    audit_observation_no_intervention_leak,
    find_matched_s0,
    fingerprint_equal,
    make_signal_runtime,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.natural_replay import (
    NaturalSignalSpecimen,
    harvest_field_a_specimens,
    run_natural_replay_branch,
    queue_natural_replay,
)


def test_repertoire_extraction_and_families():
    cfg = ScreenConfig(
        max_specimens=10,
        max_families=6,
        harvest_seeds=(17, 19),
        harvest_steps=60,
    )
    rep = build_repertoire(cfg=cfg, harvest=True)
    assert rep["n_deduped"] >= 2
    assert rep["families"]
    specs = [NaturalSignalSpecimen.from_dict(d) for d in rep["specimens"]]
    feat0 = physical_feature_vector(specs[0])
    key0 = family_key_from_features(feat0)
    assert "ch" in key0 and "amp" in key0
    # Deterministic clustering
    fams1 = group_into_families(specs, max_families=6)
    fams2 = group_into_families(specs, max_families=6)
    assert [f["family_key"] for f in fams1] == [f["family_key"] for f in fams2]
    assert all("why_grouped" in f for f in fams1)
    assert len(group_into_families(specs, max_families=None)) >= len(fams1)


def test_candidate_prioritization_and_queue_bounds():
    cfg = ScreenConfig(max_specimens=8, harvest_seeds=(17,), harvest_steps=50)
    rep = build_repertoire(cfg=cfg)
    pri = prioritize_candidates(
        [NaturalSignalSpecimen.from_dict(d) for d in rep["specimens"]],
        rep["families"],
        limit=cfg.max_specimens,
    )
    assert len(pri) <= cfg.max_specimens
    assert pri[0]["priority_score"] >= pri[-1]["priority_score"]
    assert all("Scheduling heuristic" in (p.get("note") or "") for p in pri)


def test_stage_a_bounded_and_negative_preservation():
    cfg = ScreenConfig(
        max_specimens=4,
        stage_a_seeds=(17,),
        stage_a_horizon=20,
        max_s0_search=250,
        harvest_seeds=(17,),
        harvest_steps=50,
        max_stage_b_candidates=2,
    )
    rep = build_repertoire(cfg=cfg)
    stage_a = run_stage_a(rep, cfg=cfg)
    assert stage_a["n_tested"] <= cfg.max_specimens
    assert stage_a["n_tested"] >= 1
    # Inert / L1-only lists are first-class
    assert "inert" in stage_a
    for r in stage_a["results"]:
        assert "summary" in r
        assert r["summary"]["evidence_class"] in (
            "UNTESTED",
            "INERT_UNDER_TESTED_CONTEXTS",
            "LEVEL1_ONLY",
            "COGNITION_CANDIDATE",
            "ACTION_CANDIDATE",
            "TRAJECTORY_CANDIDATE",
            "DOWNSTREAM_MULTI",
        )


def test_latency_persistence_helpers():
    specs = harvest_field_a_specimens(seed=17, max_steps=80, max_specimens=1)
    sp = specs[0]
    s0 = find_matched_s0(
        seed=17, receiver="agent_1", pre_action="WAIT",
        pre_selection_source="RETAINED_PREDICTION", require_no_contact=True,
        max_search=300, min_age=25,
    )
    if s0 is None:
        return
    ctrl = run_natural_replay_branch(
        s0["snapshot"], sp, receiver_slot=s0["receiver_slot"], horizon=25,
        experiment_id="t", intervention_id="i", kind="CONTROL",
    )
    rep = run_natural_replay_branch(
        s0["snapshot"], sp, receiver_slot=s0["receiver_slot"], horizon=25,
        experiment_id="t", intervention_id="i", kind="NATURAL_REPLAY", target="PEER",
    )
    lat = measure_latency_persistence(ctrl, rep)
    assert "first_divergence" in lat
    assert "latency_markers_hit" in lat
    assert "1" in lat["latency_markers_hit"]
    assert "persistence" in lat


def test_stage_b_skipped_without_promotion_and_fingerprints():
    cfg = ScreenConfig(
        max_specimens=3,
        stage_a_seeds=(17,),
        stage_a_horizon=18,
        harvest_seeds=(17,),
        harvest_steps=40,
    )
    rep = build_repertoire(cfg=cfg)
    stage_a = run_stage_a(rep, cfg=cfg)
    # Force empty promotions to test skip path
    stage_a_empty = {**stage_a, "promoted_specimen_ids": []}
    stage_b = run_stage_b(rep, stage_a_empty, cfg=cfg)
    assert stage_b["results"] == []
    fps = build_response_fingerprints_screen(rep, stage_a, stage_b)
    assert fps
    assert all(fp["honesty"]["not_a_meaning_map"] for fp in fps)
    cands = build_downstream_candidates(stage_a, stage_b)
    # May be empty — that is valid
    assert isinstance(cands, list)


def test_cognition_boundary_and_determinism_screen():
    specs = harvest_field_a_specimens(seed=17, max_steps=60, max_specimens=1)
    sp = specs[0]
    rt = make_signal_runtime(seed=17)
    for _ in range(20):
        rt.step()
    queue_natural_replay(rt, sp, mode="EXACT", target="PEER", receiver_slot=1, observer_source_id="scr")
    rt.step()
    for slot in rt.slots:
        assert audit_observation_no_intervention_leak(slot.last_agent_observation) == []
    s0 = find_matched_s0(
        seed=17, receiver="agent_1", pre_action="WAIT",
        pre_selection_source="RETAINED_PREDICTION", require_no_contact=True,
        max_search=300, min_age=25,
    )
    if s0 is None:
        return
    c1 = run_natural_replay_branch(
        s0["snapshot"], sp, receiver_slot=s0["receiver_slot"], horizon=10,
        experiment_id="d", intervention_id="x", kind="CONTROL",
    )
    c2 = run_natural_replay_branch(
        s0["snapshot"], sp, receiver_slot=s0["receiver_slot"], horizon=10,
        experiment_id="d", intervention_id="x", kind="CONTROL",
    )
    assert all(
        fingerprint_equal(a["fingerprint"], b["fingerprint"])
        for a, b in zip(c1["traces"], c2["traces"])
    )


def test_classify_negative_result_label():
    s = classify_from_trials([])
    assert s["evidence_class"] == "UNTESTED"
    s2 = classify_from_trials([
        {"levels": {"L1_exposure": True, "L2_cognition": False, "L3_action": False, "L4_trajectory": False}},
        {"levels": {"L1_exposure": True, "L2_cognition": False, "L3_action": False, "L4_trajectory": False}},
    ])
    assert s2["evidence_class"] == "LEVEL1_ONLY"
    assert "MEANINGLESS" not in s2["evidence_class"]


def test_session_repertoire_api_shape():
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    r = sess.list_signal_repertoire(filter_name="ALL", limit=8)
    assert r["accepted"] is True
    assert "specimens" in r
    assert r.get("honesty", {}).get("on_demand_only") is True
