"""Long-run performance architecture gates (presentation policy; science unchanged)."""
from __future__ import annotations

import hashlib
import json

from mechanistic_mind.ui.psy_observer_web.session import (
    EXECUTION_MODE_PRESETS,
    MAX_SPEED,
    ObserverSession,
    SessionConfig,
    observer_capture_period,
    tick_sleep_seconds,
)


def _fp(rt) -> str:
    slots = getattr(rt, "slots", None) or [rt]
    bodies = []
    for s in slots:
        bodies.append({
            "x": round(float(s.body.x), 8),
            "y": round(float(s.body.y), 8),
            "vx": round(float(s.body.vx), 8),
            "vy": round(float(s.body.vy), 8),
            "action": s.last_selected_action,
        })
    payload = {"bodies": bodies, "tick": int(rt.tick), "T": float(rt.world.T.sum())}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _sess(mode: str = "LIVE") -> ObserverSession:
    s = ObserverSession(SessionConfig(seed=19, execution_mode=mode))
    s.apply_experiment({
        "seed": 19,
        "agent_count": 2,
        "cognition_enabled": True,
        "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
    })
    s.set_execution_mode(mode)
    return s


def test_execution_mode_presets_exist():
    assert set(EXECUTION_MODE_PRESETS) >= {"LIVE", "FAST", "MAX", "HEADLESS"}
    assert float(EXECUTION_MODE_PRESETS["MAX"]["speed"]) == MAX_SPEED
    assert EXECUTION_MODE_PRESETS["HEADLESS"]["capture"] is False


def test_max_tick_sleep_is_zero():
    assert tick_sleep_seconds(MAX_SPEED) == 0.0
    assert tick_sleep_seconds(1.0) > 0.0


def test_observer_hz_independent_of_sim_speed():
    # High speed still samples at ~ui_hz wall clock, not per tick
    p1 = observer_capture_period(1.0, 5.0)
    p50 = observer_capture_period(50.0, 5.0)
    assert p1 == 0.2
    assert p50 >= 0.05


def test_modes_scientific_fingerprint_exact_match():
    digests = []
    for mode in ("LIVE", "FAST", "MAX", "HEADLESS"):
        s = _sess(mode)
        with s._step_lock:
            for _ in range(40):
                s._scientific_step_once_unlocked()
        digests.append(_fp(s.runtime))
    assert len(set(digests)) == 1


def test_headless_skips_presentation_capture_flag():
    s = _sess("HEADLESS")
    assert s.config.execution_mode == "HEADLESS"
    assert float(s.config.speed) == MAX_SPEED


def test_target_tick_settable():
    s = _sess("MAX")
    out = s.set_target_tick(5000)
    assert s.config.target_tick == 5000
    assert out.get("control_receipt", {}).get("accepted", True) is not False or "SET_TARGET_TICK" in str(out)


def test_observer_hz_settable():
    s = _sess("FAST")
    s.set_observer_hz(3.0)
    assert abs(s.config.ui_hz - 3.0) < 1e-9


def test_no_tick_skip_under_max():
    s = _sess("MAX")
    with s._step_lock:
        t0 = s.runtime.tick
        for _ in range(25):
            s._scientific_step_once_unlocked()
        assert s.runtime.tick - t0 == 25
