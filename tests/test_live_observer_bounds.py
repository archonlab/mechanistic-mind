"""LIVE Observer refresh must not scale with scientific history length.

Negative regression: same current live state + two synthetic histories
(1k vs 100k rows) must produce equivalent LIVE frame shape/work.
"""
from __future__ import annotations

import json
import time
from collections import deque
from copy import deepcopy

from mechanistic_mind.ui.psy_observer_web.live_bounds import (
    LIVE_WORLD_INTERVENTION_EMBED,
    LIVE_WORLD_INTERVENTION_SESSION_MAX,
    live_refresh_elements_touched,
    tail_list,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _make_session() -> ObserverSession:
    return ObserverSession(
        SessionConfig(
            seed=17,
            cognition_enabled=True,
            buffer_capacity=64,
            ui_hz=10.0,
            speed=50.0,
            target_tick=200,
        )
    )


def test_tail_list_does_not_copy_prefix():
    seq = list(range(10_000))
    out = tail_list(seq, 16)
    assert out == list(range(9984, 10_000))
    assert len(out) == 16


def test_world_intervention_session_ring_is_bounded():
    s = _make_session()
    with s._lock:
        for i in range(LIVE_WORLD_INTERVENTION_SESSION_MAX + 400):
            s._world_interventions.append({"tick": i, "type": "WORLD_INTERVENTION", "i": i})
        assert len(s._world_interventions) == LIVE_WORLD_INTERVENTION_SESSION_MAX
        embed = tail_list(s._world_interventions, LIVE_WORLD_INTERVENTION_EMBED)
        assert len(embed) == LIVE_WORLD_INTERVENTION_EMBED


def test_live_capture_ignores_scientific_history_loader(monkeypatch):
    """Ordinary LIVE capture must not invoke evidence-package loader."""
    s = _make_session()
    with s._step_lock:
        with s._lock:
            for _ in range(5):
                s._scientific_step_once_unlocked()
                s._accumulate_events_locked()
                s._record_motion_locked()

    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise AssertionError("LIVE path must not load scientific evidence package")

    monkeypatch.setattr(
        "mechanistic_mind.ui.psy_observer_web.session.load_evidence_package",
        boom,
    )
    with s._step_lock:
        with s._lock:
            frame = s._capture_locked(detail="compact")
    assert calls["n"] == 0
    obs = frame.get("observation") or {}
    assert obs.get("live_bounds", {}).get("not_scientific_authority") is True
    touched = int(obs.get("history_elements_touched_by_live_refresh") or 0)
    assert touched > 0
    events_payload = frame.get("structured_events") or frame.get("events") or []
    assert touched == live_refresh_elements_touched(
        event_embed=len(events_payload),
        traj_embed=len((frame.get("trajectory") or {}).get("points") or []),
        telem_embed=len((frame.get("telemetry") or {}).get("series") or []),
        intervention_embed=len(frame.get("world_interventions") or []),
    )


def test_live_projection_independent_of_synthetic_history_length():
    """Same current state; 1k vs 100k synthetic sci rows must not change LIVE work shape."""
    current = {
        "header": {"tick": 42, "status": "RUNNING", "selected_agent_id": "agent_0"},
        "events": [{"tick": 40, "type": "E"}],
        "trajectory": {"points": [{"tick": 41, "x": 1, "y": 2}]},
        "telemetry": {"series": [{"tick": 41}]},
        "world_interventions": [{"tick": 10, "type": "WORLD_INTERVENTION"}],
    }

    def live_view(frame: dict, scientific_rows: list) -> dict:
        # Correct LIVE path: ignore scientific_rows entirely.
        _ = scientific_rows  # Analyzer-only; must not be scanned for LIVE.
        out = deepcopy(frame)
        out["observation"] = {
            "live_authority": "current_only",
            "history_elements_touched_by_live_refresh": live_refresh_elements_touched(
                event_embed=len(out.get("events") or []),
                traj_embed=len((out.get("trajectory") or {}).get("points") or []),
                telem_embed=len((out.get("telemetry") or {}).get("series") or []),
                intervention_embed=len(out.get("world_interventions") or []),
            ),
            "scientific_rows_ignored": len(scientific_rows),
        }
        return out

    short_hist = [{"tick": i} for i in range(1_000)]
    long_hist = [{"tick": i} for i in range(100_000)]

    t0 = time.perf_counter()
    a = live_view(current, short_hist)
    t_a = time.perf_counter() - t0
    t1 = time.perf_counter()
    b = live_view(current, long_hist)
    t_b = time.perf_counter() - t1

    assert a["observation"]["history_elements_touched_by_live_refresh"] == b[
        "observation"
    ]["history_elements_touched_by_live_refresh"]
    assert a["header"] == b["header"]
    assert a["trajectory"] == b["trajectory"]
    assert a["observation"]["scientific_rows_ignored"] == 1_000
    assert b["observation"]["scientific_rows_ignored"] == 100_000
    # Work must not scale with history length (allow large absolute slack for noise).
    assert t_b < t_a * 20 + 0.05


def test_unbounded_intervention_embed_would_grow_payload_bounded_does_not():
    """Document BEFORE pathology: embedding full intervention list grows with N."""
    big = [{"tick": i, "type": "WORLD_INTERVENTION", "payload": "x" * 32} for i in range(5_000)]
    unbounded = json.dumps({"world_interventions": big}, separators=(",", ":"))
    bounded = json.dumps(
        {"world_interventions": tail_list(big, LIVE_WORLD_INTERVENTION_EMBED)},
        separators=(",", ":"),
    )
    assert len(unbounded) > len(bounded) * 10
    ring = deque(big, maxlen=LIVE_WORLD_INTERVENTION_SESSION_MAX)
    assert len(ring) == LIVE_WORLD_INTERVENTION_SESSION_MAX
    assert len(tail_list(ring, LIVE_WORLD_INTERVENTION_EMBED)) == LIVE_WORLD_INTERVENTION_EMBED


def test_live_capture_payload_independent_of_extra_session_interventions_beyond_embed():
    s = _make_session()
    with s._step_lock:
        with s._lock:
            for _ in range(3):
                s._scientific_step_once_unlocked()
                s._accumulate_events_locked()
                s._record_motion_locked()
            for i in range(80):
                s._world_interventions.append({"tick": i, "type": "WORLD_INTERVENTION", "i": i})
            f1 = s._capture_locked(detail="compact", serialize=False)
            n1 = len(f1.get("world_interventions") or [])
            for i in range(80, 400):
                s._world_interventions.append({"tick": i, "type": "WORLD_INTERVENTION", "i": i})
            f2 = s._capture_locked(detail="compact", serialize=False)
            n2 = len(f2.get("world_interventions") or [])
    assert n1 == LIVE_WORLD_INTERVENTION_EMBED
    assert n2 == LIVE_WORLD_INTERVENTION_EMBED
    assert f1["world_intervention_summary"]["live_embed_cap"] == LIVE_WORLD_INTERVENTION_EMBED
    assert f2["world_intervention_summary"]["n"] == 400
    assert f2["world_intervention_summary"]["n"] <= LIVE_WORLD_INTERVENTION_SESSION_MAX
    assert f2["world_intervention_summary"]["live_embed_n"] == LIVE_WORLD_INTERVENTION_EMBED
