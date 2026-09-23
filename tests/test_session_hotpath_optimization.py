"""Session hot-path: HEADLESS skips LIVE bookkeeping; event tick drain equivalence."""
from __future__ import annotations

from mechanistic_mind.ui.psy_observer_web.serialize import (
    collect_observer_events,
    collect_observer_events_for_tick,
)
from mechanistic_mind.ui.psy_observer_web.session import MAX_SPEED, ObserverSession, SessionConfig


def _sess(mode: str = "HEADLESS", seed: int = 21) -> ObserverSession:
    s = ObserverSession(SessionConfig(seed=seed, speed=MAX_SPEED, execution_mode=mode))
    s.apply_experiment({
        "seed": seed,
        "agent_count": 2,
        "cognition_enabled": True,
        "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
    })
    s.set_execution_mode(mode)
    return s


def test_headless_skips_live_motion_rings():
    s = _sess("HEADLESS")
    assert s._live_presentation_bookkeeping_enabled() is False
    with s._step_lock:
        for _ in range(5):
            s._scientific_step_once_unlocked()
            with s._lock:
                s._accumulate_events_locked()
                s._record_motion_locked()
    assert len(s._trajectory) == 0
    assert len(s._telemetry) == 0


def test_live_still_records_motion_rings():
    s = _sess("LIVE")
    assert s._live_presentation_bookkeeping_enabled() is True
    s._trajectory.clear()
    with s._step_lock:
        for _ in range(5):
            s._scientific_step_once_unlocked()
            with s._lock:
                s._accumulate_events_locked()
                s._record_motion_locked()
    assert len(s._trajectory) == 5


def test_collect_for_tick_matches_filtered_full():
    s = _sess("HEADLESS", seed=33)
    with s._step_lock:
        for _ in range(40):
            s._scientific_step_once_unlocked()
            tick = int(s.runtime.tick)
            full = [e for e in collect_observer_events(s.runtime, limit=120) if int(e.get("tick") or -1) == tick]
            cur = collect_observer_events_for_tick(s.runtime, tick=tick, limit=120)

            def sig(lst):
                return [(int(e.get("tick") or -1), str(e.get("type") or ""), str(e.get("agent_id") or "")) for e in lst]

            assert sig(full) == sig(cur)


def test_headless_live_same_body_trajectory():
    digests = []
    for mode in ("HEADLESS", "LIVE"):
        s = _sess(mode, seed=41)
        with s._step_lock:
            for _ in range(80):
                s._scientific_step_once_unlocked()
                with s._lock:
                    s._accumulate_events_locked()
                    s._record_motion_locked()
        digests.append((
            round(s.runtime.slots[0].body.x, 8),
            round(s.runtime.slots[0].body.y, 8),
            s.runtime.slots[0].last_selected_action,
            int(s.runtime.tick),
        ))
    assert digests[0] == digests[1]
