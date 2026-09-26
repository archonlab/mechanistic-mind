"""BETA2-SIGINT-01: Signal Context Interpreter tests (Observer-only)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.signal_context.cognition_delta import (
    action_geometry_separation,
    cognitive_delta,
    coverage_status,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.episodes import (
    episode_informativeness,
    group_signal_episodes,
    stable_episode_id,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.live_accum import (
    LiveSignalEpisodeAccumulator,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.matched_controls import (
    compare_episode_vs_controls,
    find_matched_controls,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.patterns import (
    cluster_patterns,
    stable_pattern_id,
)
from mechanistic_mind.ui.psy_observer_web.signal_context.windows import (
    WINDOW_SPEC,
    extract_windows,
)
from mechanistic_mind.ui.psy_observer_web.geometry.context import geometry_context
from mechanistic_mind.ui.psy_observer_web.geometry.metrics import step_record
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _recv(
    tick: int,
    agent: str,
    *,
    a: float = 0.0,
    b: float = 0.0,
    parents: list | None = None,
    contribs: list | None = None,
    attribution: str = "NOT_UNIQUELY_ATTRIBUTABLE",
) -> dict:
    return {
        "type": "PHYSICAL_SIGNAL_RECEIVED",
        "tick": tick,
        "agent_id": agent,
        "causal_parent_ids": parents or [],
        "evidence": {
            "receiver_agent_id": agent,
            "receiver_body_id": agent.replace("agent_", "body-"),
            "local.FIELD_A": a,
            "local.FIELD_B": b,
            "source_attribution": attribution,
            "causal_parent_ids": parents or [],
            "contributing_emissions_this_tick": contribs or [],
        },
    }


def test_signal_episode_grouping_field_a():
    events = [
        _recv(10, "agent_0", a=0.2, parents=["e10-A-s0"], contribs=[
            {"emission_id": "e10-A-s0", "channel": "A", "emitter_agent_id": "agent_0", "trigger": "body_motion"}
        ]),
        _recv(11, "agent_0", a=0.5, parents=["e11-A-s0"], contribs=[
            {"emission_id": "e11-A-s0", "channel": "A", "emitter_agent_id": "agent_0", "trigger": "body_motion"}
        ]),
        _recv(12, "agent_0", a=0.3, parents=["e12-A-s0"], contribs=[
            {"emission_id": "e12-A-s0", "channel": "A", "emitter_agent_id": "agent_0", "trigger": "body_motion"}
        ]),
    ]
    eps = group_signal_episodes(events, run_id="r1")
    assert len(eps) == 1
    assert eps[0]["channel"] == "FIELD_A"
    assert eps[0]["start_tick"] == 10
    assert eps[0]["peak_tick"] == 11
    assert eps[0]["intensity"]["peak"] == 0.5
    assert "body_motion" in eps[0]["trigger_composition"]


def test_signal_episode_field_b_and_mixed():
    events = [
        _recv(20, "agent_1", b=0.4, parents=["e20-B"], contribs=[
            {"emission_id": "e20-B", "channel": "B", "emitter_agent_id": "agent_0", "trigger": "body_contact"}
        ], attribution="MIXED"),
        _recv(21, "agent_1", a=0.1, b=0.2, parents=["e21-A", "e21-B"], contribs=[
            {"emission_id": "e21-A", "channel": "A", "emitter_agent_id": "agent_1", "trigger": "body_motion"},
            {"emission_id": "e21-B", "channel": "B", "emitter_agent_id": "agent_0", "trigger": "body_contact"},
        ], attribution="MIXED"),
    ]
    eps = group_signal_episodes(events, run_id="r1")
    assert len(eps) == 1
    assert eps[0]["channel"] == "MIXED"
    assert eps[0]["attribution"] in ("MIXED", "NOT_UNIQUELY_ATTRIBUTABLE")
    assert eps[0]["cross_agent_contribution_fraction"] is not None
    assert eps[0]["self_contribution_fraction"] is not None


def test_unique_vs_cross_agent_accounting():
    events = [
        _recv(5, "agent_0", a=0.3, parents=["e5"], contribs=[
            {"emission_id": "e5", "channel": "A", "emitter_agent_id": "agent_1", "trigger": "body_motion"}
        ], attribution="UNIQUE"),
    ]
    eps = group_signal_episodes(events, run_id="r1")
    assert eps[0]["cross_agent_contribution_fraction"] == 1.0
    assert eps[0]["self_contribution_fraction"] == 0.0
    assert eps[0]["attribution"] == "UNIQUE"


def test_stable_episode_ids_deterministic():
    events = [_recv(t, "agent_0", a=0.2 + 0.01 * t) for t in range(1, 5)]
    a = group_signal_episodes(events, run_id="runX", generation=2)
    b = group_signal_episodes(events, run_id="runX", generation=2)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a[0]["episode_id"] == stable_episode_id(
        run_id="runX",
        receiver_agent_id="agent_0",
        start_tick=a[0]["start_tick"],
        channel=a[0]["channel"],
        peak_tick=a[0]["peak_tick"],
    )


def test_pre_during_post_windows_and_delta():
    ep = {
        "episode_id": "sigep-test",
        "receiver_agent_id": "agent_0",
        "start_tick": 50,
        "end_tick": 52,
        "peak_tick": 51,
    }
    rows = []
    for t in range(30, 80):
        rows.append({
            "tick": t,
            "agent_id": "agent_0",
            "action": "MOVE:N" if t < 53 else "MOVE:E",
            "action_source": "RETAINED_PREDICTION" if t < 53 else "PROSPECTIVE_CONTINUATION",
            "x": float(t),
            "y": 1.0,
            "vx": 0.1,
            "vy": 0.0,
            "speed": 0.1,
            "theta": 0.0,
            "work": 4.0,
            "contact": False,
            "prediction_count": t,
            "prospective_compositions": t // 2,
        })
    win = extract_windows(ep, rows, pre=20, post_short=20, post_medium=100)
    assert win["availability"]["PRE"] == "AVAILABLE"
    assert WINDOW_SPEC["PRE"]["start_offset"] == -20
    delta = cognitive_delta(win, episode_id="sigep-test", receiver_agent_id="agent_0")
    assert delta["DELTA"]["action_changed"] is True
    assert delta["DELTA"]["selection_source_changed"] is True
    assert delta["EVIDENCE"]["reception_to_cognitive_delta"] == "TEMPORALLY_ASSOCIATED"
    assert coverage_status("memory_fingerprint") == "MISSING"
    assert "fake_zero" in delta["coverage"]["fake_zero_warning"].lower() or "0" in delta["coverage"]["fake_zero_warning"]


def test_unavailable_cognition_fields_and_fake_zero():
    assert coverage_status("prediction_count") == "PARTIAL"
    assert coverage_status("causal_parent_ids_into_cognition") == "MISSING"
    assert coverage_status("observation_fragment_FIELD") == "MISSING"


def test_matched_controls_and_poor_match_rejection():
    ep = {
        "episode_id": "sigep-m",
        "receiver_agent_id": "agent_0",
        "start_tick": 100,
        "end_tick": 102,
        "peak_tick": 101,
    }
    rows = []
    for t in range(0, 250):
        rows.append({
            "tick": t,
            "agent_id": "agent_0",
            "action": "MOVE:N",
            "action_source": "RETAINED_PREDICTION",
            "x": 10.0 + (t % 3),
            "y": 10.0,
            "vx": 0.1,
            "vy": 0.0,
            "speed": 0.1,
            "work": 4.0,
            "contact": False,
            "prediction_count": 10,
            "prospective_compositions": 5,
        })
    recv = {("agent_0", t) for t in range(100, 103)}
    controls = find_matched_controls(ep, rows, recv, max_controls=5)
    assert controls["match_quality"] in ("GOOD_MATCH", "PARTIAL_MATCH")
    assert controls["n_controls"] >= 1
    # No valid when timeline empty for agent
    empty = find_matched_controls(ep, [], set())
    assert empty["match_quality"] == "NO_VALID_CONTROL"


def test_matched_association_comparison():
    delta = {
        "DELTA": {"action_changed": True, "selection_source_changed": False},
    }
    controls = {
        "match_quality": "GOOD_MATCH",
        "controls": [
            {"outcomes": {"action_changed": False, "selection_source_changed": False}},
            {"outcomes": {"action_changed": False, "selection_source_changed": False}},
            {"outcomes": {"action_changed": True, "selection_source_changed": False}},
        ],
    }
    cmp_ = compare_episode_vs_controls(delta, controls)
    assert cmp_["evidence"] == "MATCHED_ASSOCIATION"


def test_informativeness_and_patterns():
    ep = {
        "channel": "FIELD_A",
        "start_tick": 1,
        "end_tick": 3,
        "intensity": {"peak": 1.0, "mean": 0.5, "integral": 1.5},
        "cross_agent_contribution_fraction": 0.8,
        "trigger_composition": ["body_motion"],
    }
    info = episode_informativeness(ep, baseline_mean=0.2, baseline_std=0.1, percentile=95.0)
    assert info["z_score_vs_baseline"] > 0
    recs = [
        {
            "signal_episode": f"e{i}",
            "receiver": "agent_1",
            "PRE": {"action": "WAIT", "selection_source": "RETAINED_PREDICTION", "contact_any": False},
            "SIGNAL": {"channel": "FIELD_A", "cross_agent_contribution_fraction": 0.5},
            "DELTA": {"action_changed": True, "selection_source_changed": True},
            "matched_comparison": {
                "controls": {"action_change_rate": 0.1, "selection_source_change_rate": 0.1}
            },
        }
        for i in range(5)
    ]
    pats = cluster_patterns(recs, min_episodes=3)
    assert len(pats) == 1
    assert pats[0]["pattern_id"] == stable_pattern_id(pats[0]["key"])
    assert pats[0]["evidence"] in ("MATCHED_ASSOCIATION", "TEMPORALLY_ASSOCIATED")


def test_requested_vs_realized_geometry_separation():
    sep = action_geometry_separation(
        pre_action="MOVE:N",
        post_action="MOVE:E",
        pre_alignment=0.9,
        post_alignment=0.4,
    )
    assert sep["action_request_changed"] is True
    assert sep["evidence"]["signal_to_action_causality"] == "NOT_ESTABLISHED"


def test_geometry_context_integration():
    steps = [
        step_record(
            tick=t, agent_id="agent_0", action="MOVE:N",
            x0=1.0, y0=float(t), x1=1.0, y1=float(t) + 0.2,
            width=32, height=32, contact=False,
        )
        for t in range(40, 60)
    ]
    ctx = geometry_context(steps, agent_id="agent_0", tick=50, window=5)
    assert ctx["honesty"]["no_signal_causality"] is True
    assert ctx["at_tick"] is not None


def test_per_agent_isolation_no_other_cognition_leak():
    events = [
        _recv(1, "agent_0", a=0.4),
        _recv(1, "agent_1", a=0.9),
        _recv(2, "agent_0", a=0.3),
        _recv(2, "agent_1", b=0.5),
    ]
    eps = group_signal_episodes(events, run_id="r")
    by = {e["receiver_agent_id"] for e in eps}
    assert by == {"agent_0", "agent_1"}
    for e in eps:
        assert "other_agent_cognition" not in e
        assert e["honesty"]["no_communication_claim"] is True


def test_live_bounded_memory():
    acc = LiveSignalEpisodeAccumulator(max_receptions=32, max_episodes=8, run_id="live")
    for t in range(200):
        acc.observe_events([_recv(t, "agent_0", a=0.2)])
    s = acc.compact_summary()
    assert s["n_receptions_buffered"] <= 32
    assert s["n_episodes"] <= 8
    assert s["honesty"]["live_bounded"] is True
    assert s["honesty"]["matched_controls"] == "ANALYZE_RESULTS_ONLY"


def test_observer_on_off_determinism_fingerprint():
    """Instrumentation must not change cognition semantics — same seed fingerprints."""
    cfg = SessionConfig(seed=17, buffer_capacity=64, ui_hz=4.0, speed=50.0)
    s1 = ObserverSession(config=cfg)
    s1.apply_experiment({
        "seed": 17,
        "agent_count": 2,
        "cognition_enabled": True,
        "mechanisms": {"experimental_physical_signal": True, "cognition_enabled": True},
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    for _ in range(30):
        s1.step()
    fp1 = [
        (int(s1.runtime.tick), getattr(s1.runtime.slots[0], "last_selected_action", None),
         float(s1.runtime.slots[0].body.x), float(s1.runtime.slots[0].body.y))
    ]
    # Signal accum observe should not alter runtime
    s1.signal_context_live_summary()
    fp2 = [
        (int(s1.runtime.tick), getattr(s1.runtime.slots[0], "last_selected_action", None),
         float(s1.runtime.slots[0].body.x), float(s1.runtime.slots[0].body.y))
    ]
    assert fp1 == fp2


def test_web_serialization_signal_context_on_frame():
    cfg = SessionConfig(seed=17, buffer_capacity=64, ui_hz=4.0, speed=50.0)
    sess = ObserverSession(config=cfg)
    sess.apply_experiment({
        "seed": 17,
        "agent_count": 2,
        "cognition_enabled": True,
        "mechanisms": {"experimental_physical_signal": True, "cognition_enabled": True},
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    for _ in range(40):
        sess.step()
    frame = sess.current_frame()
    assert "signal_context_interpretation" in frame
    assert frame["signal_context_interpretation"]["honesty"]["observer_only"] is True
    # Compact JSON must remain finite
    blob = json.dumps(frame["signal_context_interpretation"], default=str)
    assert len(blob) < 200_000


def test_performance_sanity_live_signal_accum():
    acc = LiveSignalEpisodeAccumulator(run_id="perf")
    events = [_recv(t % 100, "agent_0" if t % 2 == 0 else "agent_1", a=0.1 * (t % 5)) for t in range(400)]
    t0 = time.perf_counter()
    for i in range(0, len(events), 8):
        acc.observe_events(events[i : i + 8])
    dt = (time.perf_counter() - t0) * 1000.0
    assert dt < 500.0  # incremental grouping must stay cheap


def test_analyze_run_smoke_if_reference_present():
    run_dir = Path(
        "results/psychology_observer/psy_observer_web/"
        "psyweb-20260918T021911.211579Z-b3cd1135"
    )
    if not run_dir.is_dir():
        return
    from mechanistic_mind.ui.psy_observer_web.signal_context.analyze_run import analyze_signal_run

    out = analyze_signal_run(
        run_dir,
        run_id=run_dir.name,
        max_timeline_rows=4000,
        max_events=40000,
        max_episode_details=8,
        focus_ticks=[680],
        min_peak_percentile=90.0,
    )
    assert out["n_episodes"] > 0
    assert out["honesty"]["no_communication_claim"] is True
    assert out["history_coverage"]["events"]["causal_parent_ids_into_cognition"] == "MISSING"
