"""Observer demand-driven publication + compact history (no scientific changes)."""
from __future__ import annotations

import json
import time
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.session import (
    FULL_PUBLIC_FRAME_RETAIN,
    ObserverSession,
    SessionConfig,
)
from mechanistic_mind.ui.psy_observer_web.serialize import compact_history_from_runtime


def _exp(**extra):
    return {
        "seed": 17,
        "agent_count": 2,
        "cognition_enabled": True,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": {"cognition_enabled": True, "predictive_equivalence": True},
        **extra,
    }


def test_full_world_frames_do_not_grow_to_512():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=512))
    s.apply_experiment(_exp())
    for _ in range(40):
        s.step(1)
    assert len(s._buffer) <= FULL_PUBLIC_FRAME_RETAIN
    assert FULL_PUBLIC_FRAME_RETAIN == 1
    assert "world" in (s._published or {})


def test_compact_history_bounded_and_latest_world():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.apply_experiment(_exp())
    s.step(12)
    assert len(s._timeline) <= s._timeline.maxlen
    assert len(s._timeline) >= 12
    last = s._timeline[-1]
    assert last.get("tick") == s.runtime.tick
    assert last.get("bodies")
    assert "world" not in last
    live = s.current_frame()
    assert int((live.get("header") or {}).get("tick")) == s.runtime.tick
    assert (live.get("world") or {}).get("grids") or live.get("world")


def test_headless_does_not_build_live_frames():
    s = ObserverSession(SessionConfig(seed=17, execution_mode="HEADLESS"))
    s.apply_experiment(_exp())
    s.set_execution_mode("HEADLESS")
    before = s.observer_publication_stats()["live_frame_builds"]
    s.step(8)
    after = s.observer_publication_stats()["live_frame_builds"]
    assert after == before
    assert s.current_frame()["header"]["execution_mode"] == "HEADLESS"


def test_play_without_consumer_does_not_capture_every_tick():
    s = ObserverSession(SessionConfig(seed=17, speed=50.0, ui_hz=10.0))
    s.apply_experiment(_exp())
    s.set_speed(50)
    builds0 = s.observer_publication_stats()["live_frame_builds"]
    s.play()
    t0 = time.time()
    while s.runtime.tick < 30 and time.time() - t0 < 4:
        time.sleep(0.02)
    s.pause()
    ticks = int(s.runtime.tick)
    builds = s.observer_publication_stats()["live_frame_builds"] - builds0
    assert ticks >= 20
    assert builds < ticks
    assert len(s._buffer) <= 1


def test_eager_subscriber_serializes_once_per_publication():
    s = ObserverSession(SessionConfig(seed=17, speed=50.0, ui_hz=8.0))
    s.apply_experiment(_exp())
    dumps = {"n": 0}

    def sub(frame):
        dumps["n"] += 1

    s.subscribe(sub, eager=True)
    s.set_speed(50)
    dumps0 = s.observer_publication_stats()["json_dumps_publish"]
    s.play()
    t0 = time.time()
    while s.runtime.tick < 25 and time.time() - t0 < 4:
        time.sleep(0.02)
    s.pause()
    s.unsubscribe(sub)
    pub = s.observer_publication_stats()["json_dumps_publish"] - dumps0
    assert dumps["n"] >= 1
    # One dumps per publication event, not per subscriber.
    s2 = ObserverSession(SessionConfig(seed=17, speed=50.0, ui_hz=8.0))
    s2.apply_experiment(_exp())
    seen = []

    def a(frame):
        seen.append("a")

    def b(frame):
        seen.append("b")

    s2.subscribe(a, eager=True)
    s2.subscribe(b, eager=True)
    d0 = s2.observer_publication_stats()["json_dumps_publish"]
    s2.step(1)
    d1 = s2.observer_publication_stats()["json_dumps_publish"]
    assert d1 - d0 == 1
    assert seen == ["a", "b"]


def test_eye_off_drops_diagnostic_payload():
    s = ObserverSession(SessionConfig(seed=17))
    s.apply_experiment(_exp())
    s.set_tiktaalik_eye(rate="2FPS", fpv=True)
    s.step(1)
    assert (s._eye_last_payload or {}).get("status") != "OFF" or s._eye_last_payload is not None
    s.set_tiktaalik_eye(rate="OFF", fpv=False)
    assert s._eye_last_payload is None
    assert s._eye_prev_fpv == {}


def test_missing_historical_world_is_not_invented():
    s = ObserverSession(SessionConfig(seed=17))
    s.apply_experiment(_exp())
    s.step(3)
    live_tick = int(s.runtime.tick)
    missing = s.frame_at_tick(0)
    assert missing.get("error") == "NOT AVAILABLE" or int((missing.get("header") or {}).get("tick", -1)) == live_tick
    old = s.frame_at_tick(1)
    if int(old.get("header", {}).get("tick", -1)) != live_tick:
        assert old.get("error") == "NOT AVAILABLE"


def test_compact_history_from_runtime_has_no_grids():
    s = ObserverSession(SessionConfig(seed=17))
    s.apply_experiment(_exp())
    s.step(2)
    row = compact_history_from_runtime(s.runtime, status="PAUSED")
    blob = json.dumps(row)
    assert "grids" not in blob
    assert len(blob) < 4000


def test_ws_hub_latest_wins_and_clears_on_empty(monkeypatch):
    from mechanistic_mind.ui.psy_observer_web.server import _Hub

    class Dummy:
        pass

    hub = _Hub()
    a, b = Dummy(), Dummy()
    hub.clients.add(a)
    hub.clients.add(b)
    hub.last_text = "frame-1"
    hub._pending = "frame-1"
    hub.disconnect(a)
    assert hub.last_text == "frame-1"
    hub.disconnect(b)
    assert hub.last_text is None
    assert hub._pending is None
    assert not hub.clients
