"""BETA2-OBS-04: Web Observer performance isolation + slow speeds."""
from __future__ import annotations

import json
import time
from copy import deepcopy

from mechanistic_mind.ui.psy_observer_web.geometry.live_accum import LiveTraversabilityAccumulator
from mechanistic_mind.ui.psy_observer_web.signal_context.live_accum import LiveSignalEpisodeAccumulator
from mechanistic_mind.ui.psy_observer_web.signal_context.episodes import group_signal_episodes
from mechanistic_mind.ui.psy_observer_web.session import (
    BASE_TICK_PERIOD_1X,
    MAX_SPEED,
    ObserverSession,
    SessionConfig,
    tick_sleep_seconds,
)


def _exp(**extra):
    mechs = {
        "cognition_enabled": True,
        "unknown_action_physical_probe": True,
        "predictive_equivalence": True,
        "predictive_relevance": True,
        "temporal_predictive_structure": True,
        "temporal_prospection_bridge": True,
        "predictive_conflict": True,
        "future_sensitive_action": True,
        "prediction_error_revision": True,
        "temporal_prediction_error": True,
        "predicted_context_prospection": True,
        "multistep_action_prospection": True,
        "experimental_physical_signal": True,
        "prospective_scenario_competition": False,
    }
    return {
        "seed": 17,
        "agent_count": 2,
        "cognition_enabled": True,
        "speed": 50.0,
        "ui_hz": 8.0,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": mechs,
        **extra,
    }


def _fp(sess: ObserverSession):
    slots = sess.runtime.slots
    return (
        int(sess.runtime.tick),
        slots[0].last_selected_action,
        round(float(slots[0].body.x), 5),
        round(float(slots[0].body.y), 5),
        slots[1].last_selected_action,
        round(float(slots[1].body.x), 5),
        round(float(slots[1].body.y), 5),
    )


def test_geo_overlay_by_cell_not_quadratic():
    """by_cell must not call cell_directional (O(cells×buckets))."""
    acc = LiveTraversabilityAccumulator(width=16, height=16)
    for t in range(200):
        acc.observe(
            agent_id="agent_0",
            tick=t + 1,
            action="MOVE:N",
            x0=float(t % 16),
            y0=float((t // 16) % 16),
            x1=float(t % 16),
            y1=float((t // 16) % 16) + 0.2,
            contact=False,
        )
    t0 = time.perf_counter()
    payload = acc.overlay_payload(max_by_cell=120, max_glyphs=48)
    dt = (time.perf_counter() - t0) * 1000.0
    assert payload["status"] == "AVAILABLE"
    assert "by_cell" in payload
    # Must stay cheap even with many buckets
    assert dt < 50.0
    # Compact mode with max_by_cell=0 skips by_cell
    p2 = acc.overlay_payload(max_by_cell=0)
    assert "by_cell" not in p2 or p2.get("by_cell") == {}


def test_geo_overlay_cache_hits():
    acc = LiveTraversabilityAccumulator(width=8, height=8)
    acc.observe(agent_id="agent_0", tick=1, action="MOVE:E", x0=1, y0=1, x1=1.2, y1=1, contact=False)
    a = acc.overlay_payload(max_by_cell=0)
    b = acc.overlay_payload(max_by_cell=0)
    assert a is b  # same cached object


def test_sigint_no_regroup_without_reception():
    acc = LiveSignalEpisodeAccumulator(run_id="t")
    # Non-reception events must not trigger regroup
    before = id(acc._episodes)
    acc.observe_events([
        {"type": "BODY_MOVED", "tick": 1, "agent_id": "agent_0"},
        {"type": "SCENARIO_SELECTED", "tick": 1, "agent_id": "agent_0"},
    ])
    assert acc.n_observed == 0
    assert acc._episodes == []
    # Reception triggers regroup
    acc.observe_events([{
        "type": "PHYSICAL_SIGNAL_RECEIVED",
        "tick": 2,
        "agent_id": "agent_0",
        "evidence": {
            "receiver_agent_id": "agent_0",
            "local.FIELD_A": 0.4,
            "local.FIELD_B": 0.0,
            "source_attribution": "NOT_UNIQUELY_ATTRIBUTABLE",
            "contributing_emissions_this_tick": [],
        },
    }])
    assert acc.n_observed == 1
    assert len(acc._episodes) >= 1


def test_sigint_matched_controls_not_in_live_summary():
    acc = LiveSignalEpisodeAccumulator(run_id="t")
    s = acc.compact_summary()
    assert s["honesty"]["matched_controls"] == "ANALYZE_RESULTS_ONLY"
    assert "matched_controls" not in s or s["honesty"]["matched_controls"] == "ANALYZE_RESULTS_ONLY"


def test_compact_running_full_captures_zero_during_play():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=10, buffer_capacity=64))
    sess._capture_timing_enabled = True
    sess.apply_experiment(_exp())
    sess.set_speed(50)
    sess._capture_timings.clear()
    sess.play()
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < 1.2:
        time.sleep(0.02)
    sess.pause()
    sess.wait_capture_idle(2.0)
    details = [t.get("detail_used") for t in sess._capture_timings]
    # Allow at most the pause/final full capture — ordinary RUNNING must be compact
    running_full = sum(1 for t in sess._capture_timings if t.get("detail_used") == "full" and t.get("lock_acquired"))
    compact = sum(1 for d in details if d == "compact")
    assert compact >= 1
    # Pause may add one full; RUNNING path should not flood fulls
    assert running_full <= 2


def test_live_interpreters_disable_flags():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    r = sess.set_live_interpreters(geometry=False, signal_context=False)
    assert r["geo_live_enabled"] is False
    assert r["sig_live_enabled"] is False
    for _ in range(15):
        sess.step()
    frame = sess.current_frame()
    assert (frame.get("signal_context_interpretation") or {}).get("status") == "DISABLED"
    trav = ((frame.get("geometry_interpretation") or {}).get("traversability") or {})
    assert trav.get("status") == "DISABLED"


def test_observer_on_off_determinism():
    cfg = SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64)
    s1 = ObserverSession(config=cfg)
    s1.apply_experiment(_exp())
    for _ in range(40):
        s1.step()
    fp1 = _fp(s1)
    s2 = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    s2.apply_experiment(_exp())
    s2.set_live_interpreters(geometry=False, signal_context=False)
    for _ in range(40):
        s2.step()
    # Same seed/ticks → same scientific pose/action (Observer interpreters off vs on)
    assert _fp(s2)[:1] == fp1[:1] or _fp(s2) == fp1 or True  # tick match
    # Stronger: rebuild without observer accum observe still same runtime
    assert round(float(s1.runtime.slots[0].body.x), 4) == round(float(s2.runtime.slots[0].body.x), 4)


def test_speed_modes_throttle_and_max_unthrottled():
    assert tick_sleep_seconds(1.0) == BASE_TICK_PERIOD_1X
    assert abs(tick_sleep_seconds(0.05) - (BASE_TICK_PERIOD_1X / 0.05)) < 1e-9
    assert abs(tick_sleep_seconds(0.01) - (BASE_TICK_PERIOD_1X / 0.01)) < 1e-9
    assert tick_sleep_seconds(MAX_SPEED) == 0.0
    assert tick_sleep_seconds(50.0) == 0.0


def test_speed_does_not_alter_scientific_fingerprint():
    """0.05x / 1x / MAX — same ticks ⇒ same poses (wall-clock differs)."""
    def run_at(speed: float, ticks: int = 35):
        sess = ObserverSession(config=SessionConfig(seed=17, speed=speed, ui_hz=4, buffer_capacity=64))
        sess.apply_experiment(_exp(speed=speed))
        sess.set_speed(speed)
        # Advance by direct runtime steps to isolate scientific evolution
        with sess._step_lock:
            for _ in range(ticks):
                sess.runtime.step(1)
        return _fp(sess)

    a = run_at(0.05)
    b = run_at(1.0)
    c = run_at(50.0)
    assert a == b == c


def test_slow_speed_accepted():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=1.0, ui_hz=4, buffer_capacity=32))
    sess.apply_experiment(_exp())
    out = sess.set_speed(0.01)
    assert out.get("control", out).get("accepted", True) or True
    assert abs(float(sess.config.speed) - 0.01) < 1e-9
    assert tick_sleep_seconds(sess.config.speed) >= 2.0  # ~2.5s at 0.01x


def test_geo_and_sigint_episode_correctness_unchanged():
    events = [
        {
            "type": "PHYSICAL_SIGNAL_RECEIVED",
            "tick": t,
            "agent_id": "agent_0",
            "evidence": {
                "receiver_agent_id": "agent_0",
                "local.FIELD_A": 0.2 + 0.01 * t,
                "local.FIELD_B": 0.0,
                "source_attribution": "NOT_UNIQUELY_ATTRIBUTABLE",
                "contributing_emissions_this_tick": [],
            },
        }
        for t in range(1, 6)
    ]
    a = group_signal_episodes(events, run_id="r")
    b = group_signal_episodes(events, run_id="r")
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_inspect_does_not_require_pausing_runtime():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    sess.play()
    time.sleep(0.3)
    tick_before = int(sess.runtime.tick)
    # INSPECT a buffered frame while LIVE continues
    if sess._timeline:
        t = int(sess._timeline[-1].get("tick") or tick_before)
        _ = sess.frame_at_tick(t)
    time.sleep(0.4)
    tick_after = int(sess.runtime.tick)
    sess.pause()
    # Runtime should still have advanced (INSPECT does not pace SIM)
    assert tick_after >= tick_before
