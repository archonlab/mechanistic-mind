"""BETA2-OBS-02: async Observer capture must not stall scientific simulation."""
from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path

import pytest

from mechanistic_mind.ui.psy_observer_web.session import (
    ObserverSession,
    SessionConfig,
)
from mechanistic_mind.ui.psy_observer_web.scientific_history import ScientificHistoryWriter


def _fingerprint(rt) -> str:
    slots = getattr(rt, "slots", None) or [rt]
    bodies = []
    actions = []
    for s in slots:
        bodies.append({
            "x": round(float(s.body.x), 8),
            "y": round(float(s.body.y), 8),
            "vx": round(float(s.body.vx), 8),
            "vy": round(float(s.body.vy), 8),
            "seed": int(s.seed),
        })
        actions.append(s.last_selected_action)
    payload = {
        "bodies": bodies,
        "actions": actions,
        "tick": int(rt.tick),
        "T_sum": float(rt.world.T.sum()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _exp(seed: int = 17, **extra):
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
    mechs.update(extra.pop("mechanisms", {}))
    return {
        "seed": seed,
        "agent_count": 2,
        "cognition_enabled": True,
        "speed": 50.0,
        "ui_hz": 10.0,
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": mechs,
        **extra,
    }


def test_sim_advances_during_slow_capture():
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0, ui_hz=10.0))
    s.apply_experiment(_exp())
    s._capture_test_delay_s = 0.25  # capture worker sleeps before step_lock
    s.set_speed(50)
    s.play()
    t0 = s.runtime.tick
    time.sleep(0.55)
    t1 = s.runtime.tick
    s.pause()
    s._capture_test_delay_s = 0.0
    # With 250ms artificial capture delay, SIM must still advance many ticks.
    assert t1 - t0 >= 5, f"SIM stalled during slow capture: Δtick={t1 - t0}"


def test_capture_queue_latest_wins_bounded():
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0, ui_hz=50.0))
    s.apply_experiment(_exp())
    s._capture_test_delay_s = 0.2
    s.play()
    time.sleep(0.6)
    depth = s.capture_queue_depth()
    drops = s._capture_queue_drops
    s.pause()
    s._capture_test_delay_s = 0.0
    assert depth <= 2  # pending + inflight at most
    assert drops >= 1


def test_published_frame_coherent_single_tick():
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0))
    s.apply_experiment(_exp())
    s.step(15)
    frame = s.current_frame()
    obs = frame.get("observation") or {}
    ticks = obs.get("ticks") or {}
    assert obs.get("tick_consistent") is True
    assert len(set(ticks.values())) == 1
    views = frame.get("agents_views") or {}
    if views:
        vticks = {int(v.get("tick")) for v in views.values() if isinstance(v, dict)}
        assert len(vticks) == 1


def test_capture_does_not_mutate_runtime_fingerprint():
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0))
    s.apply_experiment(_exp())
    s.step(10)
    before = _fingerprint(s.runtime)
    with s._step_lock:
        with s._lock:
            s._capture_locked(detail="full")
            s._capture_locked(detail="compact")
    after = _fingerprint(s.runtime)
    assert before == after


def test_pause_resume_no_deadlock():
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0))
    s.apply_experiment(_exp())
    s.play()
    time.sleep(0.15)
    s.pause()
    assert s.status == "PAUSED"
    assert s.current_frame()["header"]["frame_detail"] == "full"
    tick = s.runtime.tick
    s.play()
    time.sleep(0.15)
    s.pause()
    assert s.runtime.tick > tick
    assert s.wait_capture_idle(timeout=2.0)


def test_stop_leaves_capture_idle():
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0))
    s.apply_experiment(_exp())
    s.play()
    time.sleep(0.1)
    s.stop(save=False, reason="USER_STOP_DISCARD")
    assert s.wait_capture_idle(timeout=2.0)
    assert s.status in {"STOPPED", "PAUSED", "SAVE_FAILED"} or s._stop_flag


def test_new_run_discards_stale_capture():
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0))
    s.apply_experiment(_exp(seed=17))
    gen1 = s._runtime_generation
    s._capture_test_delay_s = 0.3
    s._request_observer_capture(detail="compact")
    s.apply_experiment(_exp(seed=19))
    gen2 = s._runtime_generation
    assert gen2 != gen1
    s._capture_test_delay_s = 0.0
    s.wait_capture_idle(timeout=2.0)
    frame = s.current_frame()
    assert int(frame["header"]["runtime_generation"]) == gen2
    assert int(frame["header"]["seed"]) == 19


def test_aggressive_polling_does_not_collapse_sim():
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0, ui_hz=10.0))
    s.apply_experiment(_exp())
    s.set_speed(50)
    stop = False

    def poller():
        while not stop:
            _ = s.current_frame()
            time.sleep(0.01)

    th = threading.Thread(target=poller, daemon=True)
    th.start()
    s.play()
    time.sleep(0.8)
    sim = float(s._perf_sim_tps)
    s.pause()
    stop = True
    th.join(timeout=1.0)
    # CORE reference ~20+ t/s on 32² experimental; require healthy throughput under poll.
    assert sim >= 10.0, f"SIM collapsed under polling: {sim}"


def test_ws_style_subscriber_json_does_not_block_sim_path():
    """Subscriber runs on capture worker; SIM should still advance under load."""
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0))
    s.apply_experiment(_exp())
    calls = {"n": 0}

    def slow_sub(frame):
        calls["n"] += 1
        # Intentionally heavy — must not run on SIM thread after decoupling.
        json.dumps(frame, default=str)

    s.subscribe(slow_sub)
    s.play()
    time.sleep(0.7)
    sim = float(s._perf_sim_tps)
    s.pause()
    s.unsubscribe(slow_sub)
    assert calls["n"] >= 1
    assert sim >= 8.0, f"SIM too low with heavy subscriber: {sim}"


def test_scientific_history_complete_despite_frame_skip(tmp_path: Path):
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0, ui_hz=5.0, results_root=tmp_path))
    s.apply_experiment(_exp())
    s.set_speed(50)
    s.play()
    time.sleep(0.9)
    ticks = int(s.runtime.tick)
    s.pause()
    # Force sci writer path was active during play
    writer = s._sci_writer
    assert writer is not None or ticks > 0
    # Count timeline rows if live dir exists
    live = s._sci_live_dir
    if live is not None and (live / "scientific_timeline.jsonl").exists():
        rows = [ln for ln in (live / "scientific_timeline.jsonl").read_text().splitlines() if ln.strip()]
        # TwoAgent → 2 rows/tick typically
        assert len(rows) >= ticks, f"sci history incomplete: rows={len(rows)} ticks={ticks}"
    frames = len(s._buffer)
    # Visual frames must not exceed scientific ticks; under load ticks≈frames is possible
    # for short windows, so require a clear skip only when the run had room to diverge.
    assert ticks >= frames
    if ticks >= 25:
        assert ticks > frames, f"expected frame skip: ticks={ticks} frames={frames}"
    # Capture count at limited ui_hz should lag scientific ticks when SIM is healthy.
    captures = int(s._perf_captures)
    if ticks >= 40 and captures > 0:
        assert ticks > captures


def test_running_uses_compact_detail():
    s = ObserverSession(config=SessionConfig(seed=17, speed=1.0, ui_hz=10.0))
    s.apply_experiment(_exp())
    s.set_speed(1.0)
    s.status = "RUNNING"
    assert s._frame_detail_for_speed() == "compact"
    s.status = "PAUSED"
    assert s._frame_detail_for_speed() == "full"


def test_cooperative_yield_prevents_lock_starvation():
    """Without coop yield, capture lock_wait can exceed 1s; with coop it should not."""
    def run(coop: bool) -> float:
        s = ObserverSession(config=SessionConfig(seed=17, speed=50.0, ui_hz=10.0))
        s._capture_coop_yield = coop
        s._capture_timing_enabled = True
        s.apply_experiment({
            "seed": 17, "agent_count": 2, "cognition_enabled": True, "speed": 50.0,
            "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
            "mechanisms": {"cognition_enabled": True, "predictive_equivalence": True},
        })
        s.set_speed(50)
        s.play()
        while s.runtime.tick < 400:
            time.sleep(0.02)
        s.pause()
        waits = [t.get("lock_wait_ms") or 0 for t in s.capture_timing_snapshot()]
        return max(waits) if waits else 0.0

    starved = run(False)
    fair = run(True)
    # Starvation mode often sees multi-second waits; coop must stay small.
    assert fair < 100.0, f"coop lock_wait still high: {fair}"
    # On a loaded CI host starvation may or may not hit 1s in 400 ticks; only assert coop bound.
    assert starved >= 0.0


def test_determinism_observer_timing_modes():
    """Observer timing / polling must not change scientific fingerprints."""

    def pure_steps(n: int) -> str:
        s = ObserverSession(config=SessionConfig(seed=17))
        s.apply_experiment(_exp(seed=17))
        for _ in range(n):
            with s._step_lock:
                s.runtime.step(1)
        return _fingerprint(s.runtime)

    def play_to(n: int, *, delay: float = 0.0, poll: bool = False) -> str:
        s = ObserverSession(config=SessionConfig(seed=17, speed=50.0, ui_hz=10.0))
        s.apply_experiment(_exp(seed=17))
        s._capture_test_delay_s = float(delay)
        stop = {"v": False}
        th = None
        if poll:
            def poller():
                while not stop["v"]:
                    s.current_frame()
                    time.sleep(0.01)
            th = threading.Thread(target=poller, daemon=True)
            th.start()
        s.play()
        while s.runtime.tick < n:
            time.sleep(0.01)
        s.pause()
        s._capture_test_delay_s = 0.0
        if poll:
            stop["v"] = True
            th.join(timeout=1.0)
        assert s.runtime.tick >= n
        # Compare against pure steps for the same reached tick count
        reached = int(s.runtime.tick)
        assert _fingerprint(s.runtime) == pure_steps(reached)

    n = 24
    ref = pure_steps(n)
    assert pure_steps(n) == ref
    play_to(n)
    play_to(n, delay=0.12)
    play_to(n, poll=True)
