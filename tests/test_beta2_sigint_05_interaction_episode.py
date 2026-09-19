"""BETA2-SIGINT-05: interaction episode reconstruction, replay, coupling."""
from __future__ import annotations

from mechanistic_mind.ui.psy_observer_web.signal_context.interaction_episode import (
    DEFAULT_REF_RUN,
    EpisodeScreenConfig,
    discover_bidirectional_episodes,
    first_divergences_episode,
    group_episode_families,
    reconstruct_reference_episode_1554_1563,
    run_episode_branch,
    run_episode_trial_suite,
    run_partial_closed_loop_probe,
    schedule_for_mode,
    select_components,
    temporal_strip,
    trajectory_coupling_summary,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.intervention import (
    find_matched_s0,
    fingerprint_equal,
    make_signal_runtime,
)


def test_reference_episode_1554_1563_reconstruction():
    ep = reconstruct_reference_episode_1554_1563(DEFAULT_REF_RUN)
    assert ep.start_tick == 1554
    assert ep.end_tick == 1563
    assert ep.duration == 10
    assert len(ep.components) == 20  # both agents each tick
    assert ep.reconstruction in ("EXACT", "PARTIAL")
    # Temporal ordering
    dts = [c.delta_t for c in ep.components]
    assert dts == sorted(dts)
    assert min(dts) == 0 and max(dts) == 9
    # Simultaneous emissions present
    from collections import Counter
    by = Counter(c.delta_t for c in ep.components)
    assert by[0] == 2
    strip = temporal_strip(ep)
    assert len(strip["ticks"]) == 10
    assert any(strip["A"]) and any(strip["B"])


def test_component_selection_modes():
    ep = reconstruct_reference_episode_1554_1563(DEFAULT_REF_RUN)
    a_only = select_components(ep, "A_TO_B_ONLY")
    b_only = select_components(ep, "B_TO_A_ONLY")
    assert a_only and all(str(c.emitter_agent_id).endswith("0") for c in a_only)
    assert b_only and all(str(c.emitter_agent_id).endswith("1") for c in b_only)
    full = select_components(ep, "FULL_EPISODE")
    assert len(full) == len(ep.components)
    closed = select_components(ep, "PARTIAL_CLOSED_LOOP")
    assert all(c.delta_t == 0 for c in closed)
    shuf = schedule_for_mode(list(ep.components), "TIMING_SHUFFLED")
    rev = schedule_for_mode(list(ep.components), "ORDER_REVERSED")
    assert len(shuf) == len(ep.components)
    assert len(rev) == len(ep.components)
    # Reversed maps max to 0
    assert min(t for t, _ in rev) == 0


def test_full_episode_replay_control_sham_determinism():
    ep = reconstruct_reference_episode_1554_1563(DEFAULT_REF_RUN)
    s0 = find_matched_s0(
        seed=17, receiver="agent_1", pre_action="WAIT",
        pre_selection_source="RETAINED_PREDICTION", require_no_contact=True,
        max_search=300, min_age=25,
    )
    if s0 is None:
        return
    snap = s0["snapshot"]
    c1 = run_episode_branch(
        snap, ep, mode="CONTROL", horizon=20, experiment_id="t", intervention_id="c",
    )
    c2 = run_episode_branch(
        snap, ep, mode="CONTROL", horizon=20, experiment_id="t", intervention_id="c",
    )
    assert all(
        fingerprint_equal(a["fingerprint"], b["fingerprint"])
        for a, b in zip(c1["traces"], c2["traces"])
    )
    sham = run_episode_branch(
        snap, ep, mode="SHAM", horizon=20, experiment_id="t", intervention_id="s",
    )
    full = run_episode_branch(
        snap, ep, mode="FULL_EPISODE", horizon=20, experiment_id="t", intervention_id="f",
    )
    assert full["n_injected"] > 0
    assert sham["n_injected"] > 0  # machinery runs; amp 0
    # Cognition boundary
    for t in full["traces"]:
        for ag in t["agents"]:
            assert ag["observation_leaks"] == []
    div = first_divergences_episode(c1, full)
    assert "observation_field" in div
    coup = trajectory_coupling_summary(full["traces"], post_start=ep.duration + 1)
    assert "mean_distance" in coup


def test_directional_and_shuffled_replay():
    ep = reconstruct_reference_episode_1554_1563(DEFAULT_REF_RUN)
    s0 = find_matched_s0(
        seed=17, receiver="agent_1", pre_action="WAIT",
        pre_selection_source="RETAINED_PREDICTION", require_no_contact=True,
        max_search=300, min_age=25,
    )
    if s0 is None:
        return
    snap = s0["snapshot"]
    a = run_episode_branch(
        snap, ep, mode="A_TO_B_ONLY", horizon=15, experiment_id="t", intervention_id="a",
    )
    b = run_episode_branch(
        snap, ep, mode="B_TO_A_ONLY", horizon=15, experiment_id="t", intervention_id="b",
    )
    sh = run_episode_branch(
        snap, ep, mode="TIMING_SHUFFLED", horizon=15, experiment_id="t", intervention_id="sh",
    )
    rev = run_episode_branch(
        snap, ep, mode="ORDER_REVERSED", horizon=15, experiment_id="t", intervention_id="rv",
    )
    assert a["n_injected"] == 10  # 10 ticks × agent_0
    assert b["n_injected"] == 10
    assert sh["n_injected"] == 20
    assert rev["n_injected"] == 20


def test_episode_repertoire_and_families():
    eps = discover_bidirectional_episodes(
        DEFAULT_REF_RUN / "scientific_events.jsonl",
        run_id=DEFAULT_REF_RUN.name,
        max_episodes=8,
        min_both_ticks=3,
    )
    assert eps
    fams = group_episode_families(eps)
    assert fams
    assert all("why_grouped" in f for f in fams)


def test_trial_suite_and_closed_loop():
    ep = reconstruct_reference_episode_1554_1563(DEFAULT_REF_RUN)
    cfg = EpisodeScreenConfig(horizon=30, stage_a_seeds=(17,), max_s0_search=300, min_s0_age=25)
    trial = run_episode_trial_suite(
        ep, seed=17, cfg=cfg,
        modes=("CONTROL", "SHAM", "FULL_EPISODE", "ISOLATED_COMPONENTS"),
    )
    if not trial.get("accepted"):
        return
    assert trial["control_control_equal"] is True
    assert "levels" in trial
    assert trial.get("any_leak") is False
    cloop = run_partial_closed_loop_probe(ep, seed=17, cfg=cfg)
    assert cloop.get("accepted")
    assert "INTERACTION_CHAIN_CANDIDATE" in cloop


def test_session_episode_api():
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    r = sess.list_interaction_episodes(limit=8)
    assert r["accepted"] is True
    assert r.get("honesty", {}).get("on_demand_only") is True
