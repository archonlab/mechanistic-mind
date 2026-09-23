"""LIVE mechanism apply at tick boundary + runtime progress heartbeat."""
from __future__ import annotations

import threading
import time

from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _sess() -> ObserverSession:
    s = ObserverSession(SessionConfig(seed=17, execution_mode="LIVE", cognition_enabled=True))
    s.apply_experiment({
        "seed": 17,
        "agent_count": 1,
        "cognition_enabled": True,
        "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": {
            "physical_near_field_vision": True,
            "spatiotemporal_climate_ecology": False,
            "oscillatory_signaling": False,
        },
    })
    return s


def test_mechanism_toggle_deferred_while_tick_holds_lock():
    s = _sess()
    # Hold step_lock as if a long tick is in progress.
    assert s._step_lock.acquire(blocking=False)
    try:
        s.status = "RUNNING"
        t0 = time.perf_counter()
        out = s.set_mechanism("oscillatory_signaling", True)
        elapsed = time.perf_counter() - t0
        # Must return promptly — not wait for the lock.
        assert elapsed < 0.5, elapsed
        assert out["control_receipt"]["accepted"] is True
        assert out["control_receipt"]["reason"] == "WAITING_FOR_TICK_BOUNDARY"
        assert out.get("pending_live_apply")
        assert out.get("toggle_runtime_applied") is False
        # Runtime not yet flipped.
        snap = s.runtime.mechanisms()
        item = next(m for m in snap["mechanisms"] if m["id"] == "oscillatory_signaling")
        assert item["enabled"] is False
    finally:
        s._step_lock.release()

    # Drain at tick boundary.
    with s._step_lock:
        s._scientific_step_once_unlocked()
    snap = s.runtime.mechanisms()
    item = next(m for m in snap["mechanisms"] if m["id"] == "oscillatory_signaling")
    assert item["enabled"] is True
    prog = s.runtime_progress()
    assert prog.get("pending_live_apply") in (None, {})


def test_mechanism_toggle_immediate_when_lock_free():
    s = _sess()
    s.status = "PAUSED"
    out = s.set_mechanism("oscillatory_signaling", True)
    assert out["control_receipt"]["accepted"] is True
    assert out.get("toggle_runtime_applied") is True
    snap = s.runtime.mechanisms()
    item = next(m for m in snap["mechanisms"] if m["id"] == "oscillatory_signaling")
    assert item["enabled"] is True


def test_runtime_progress_reports_computing_tick():
    s = _sess()
    s.status = "RUNNING"
    s._tick_in_progress = True
    s._tick_started_mono = time.monotonic()
    prog = s.runtime_progress()
    assert prog["status"] == "RUNNING"
    assert prog["status_detail"] == "COMPUTING_TICK"
    assert prog["tick_in_progress"] is True


def test_fingerprint_unchanged_by_deferred_path_vs_direct():
    """Same toggle semantics whether applied sync or via queue drain."""
    a = _sess()
    b = _sess()
    a.set_mechanism("oscillatory_signaling", True)
    b.status = "RUNNING"
    assert b._step_lock.acquire(blocking=False)
    try:
        b.set_mechanism("oscillatory_signaling", True)
    finally:
        b._step_lock.release()
    with b._step_lock:
        b._drain_live_apply_queue_unlocked()
    en_a = a.runtime.mechanisms()["enabled"].get("oscillatory_signaling")
    en_b = b.runtime.mechanisms()["enabled"].get("oscillatory_signaling")
    assert en_a is True and en_b is True
