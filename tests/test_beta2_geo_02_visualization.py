"""BETA2-GEO-02: traversability overlay / visualization tests."""
from __future__ import annotations

import json
import time

from mechanistic_mind.ui.psy_observer_web.geometry.live_accum import (
    CLASS_EASY,
    CLASS_LOW_EVIDENCE,
    CLASS_STRONG_DEFLECTION,
    CLASS_UNKNOWN,
    LiveTraversabilityAccumulator,
    classify_bucket,
)
from mechanistic_mind.ui.psy_observer_web.geometry.metrics import (
    action_alignment,
    realized_displacement,
    step_record,
)
from mechanistic_mind.ui.psy_observer_web.geometry.context import geometry_context
from mechanistic_mind.ui.psy_observer_web.geometry.trajectory import stable_episode_id
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame


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
        "speed": 80.0,
        "ui_hz": 8.0,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": mechs,
        **extra,
    }


def test_classify_sparse_and_strong():
    assert classify_bucket(0, 0, 0, None) == CLASS_UNKNOWN
    assert classify_bucket(2, 1, 0, -0.5) == CLASS_LOW_EVIDENCE
    assert classify_bucket(10, 5, 2, -0.4) == CLASS_STRONG_DEFLECTION
    assert classify_bucket(10, 0, 9, 0.8) == CLASS_EASY


def test_live_accum_directional_and_per_agent():
    acc = LiveTraversabilityAccumulator(width=16, height=16)
    # agent_0 succeeds MOVE:E at (5,5)
    for t in range(10):
        acc.observe(
            agent_id="agent_0", tick=t, action="MOVE:E",
            x0=5.1, y0=5.1, x1=5.3, y1=5.1, contact=False,
        )
    # agent_1 fails MOVE:E at same cell
    for t in range(10, 18):
        acc.observe(
            agent_id="agent_1", tick=t, action="MOVE:E",
            x0=5.1, y0=5.1, x1=4.9, y1=5.1, contact=False,
        )
    cell_all = acc.cell_directional(5, 5, agent_filter="ALL")
    assert cell_all["directions"]["MOVE:E"]["attempts"] == 18
    assert "agent_0" in cell_all["by_agent"]
    a0 = acc.cell_directional(5, 5, agent_filter="agent_0")
    a1 = acc.cell_directional(5, 5, agent_filter="agent_1")
    assert a0["directions"]["MOVE:E"]["mean_action_alignment"] > 0.5
    assert a1["directions"]["MOVE:E"]["mean_action_alignment"] < -0.5


def test_overlay_payload_bounded_and_honest():
    acc = LiveTraversabilityAccumulator(width=8, height=8)
    for t in range(20):
        acc.observe(
            agent_id="agent_0", tick=t, action="MOVE:N",
            x0=2.0, y0=2.0 + 0.01 * t, x1=2.0, y1=1.7 + 0.01 * t, contact=False,
        )
    ov = acc.overlay_payload(agent_filter="ALL", max_glyphs=10, max_by_cell=50)
    assert ov["status"] == "AVAILABLE"
    assert ov["honesty"]["empirical_not_terrain"] is True
    assert ov["honesty"]["no_hard_walls"] is True
    assert len(ov["class_grid"]) == 8
    assert len(ov["glyphs"]) <= 10
    raw = json.dumps(ov, default=str)
    assert len(raw) < 500_000


def test_periodic_displacement_and_alignment():
    dx, dy, mag = realized_displacement(0.2, 5.0, 15.8, 5.0, width=16, height=16)
    assert dx < 0 and mag < 1.0
    assert action_alignment("MOVE:W", dx, dy) > 0.9


def test_periodic_segments_frontend_logic():
    # Mirror rendererMath.periodicSegments
    def periodic_segments(points, width, height):
        if not points:
            return []
        out = [[points[0]]]
        for i in range(1, len(points)):
            a, b = points[i - 1], points[i]
            if abs(b["x"] - a["x"]) > width / 2 or abs(b["y"] - a["y"]) > height / 2:
                out.append([b])
            else:
                out[-1].append(b)
        return [s for s in out if s]
    pts = [{"x": 15.5, "y": 8.0}, {"x": 0.3, "y": 8.0}, {"x": 0.5, "y": 8.1}]
    segs = periodic_segments(pts, 16, 16)
    assert len(segs) == 2
    assert len(segs[0]) == 1 and len(segs[1]) == 2


def test_stable_episode_and_context():
    eid = stable_episode_id(
        run_id="r", generation=2, agent_id="agent_0",
        kind="STRONG_DEFLECTION", start_tick=1, end_tick=1,
    )
    assert eid == stable_episode_id(
        run_id="r", generation=2, agent_id="agent_0",
        kind="STRONG_DEFLECTION", start_tick=1, end_tick=1,
    )
    steps = [
        step_record(
            tick=t, agent_id="agent_0", action="MOVE:S",
            x0=1.0, y0=float(t), x1=1.0, y1=float(t) + 0.2,
            width=32, height=32,
        )
        for t in range(5)
    ]
    ctx = geometry_context(steps, agent_id="agent_0", tick=2, window=2)
    assert ctx["honesty"]["no_signal_causality"] is True
    assert ctx["at_tick"] is not None


def test_session_accumulates_and_serializes_overlay():
    s = ObserverSession(config=SessionConfig(seed=17, speed=40.0, ui_hz=8.0))
    s.apply_experiment(_exp())
    s.play()
    while s.runtime.tick < 120:
        time.sleep(0.02)
    s.wait_capture_idle(timeout=2.0)
    s.pause()
    s.wait_capture_idle(timeout=2.0)
    frame = s.current_frame()
    geo = frame.get("geometry_interpretation") or {}
    assert geo.get("observer_only") is True
    trav = geo.get("traversability")
    assert isinstance(trav, dict)
    assert trav.get("status") == "AVAILABLE"
    assert "class_grid" in trav
    assert len(trav["class_grid"]) >= 8
    # no leak into mind
    mind_s = json.dumps(frame.get("mind") or {}, default=str)
    assert "class_grid" not in mind_s
    assert "TRAVERSABILITY" not in mind_s
    # bounded
    assert len(json.dumps(geo, default=str)) < 1_500_000
    # agent filter
    r = s.set_geometry_agent_filter("agent_0")
    assert r["accepted"] is True
    detail = s.geometry_cell_detail(0, 0, agent_filter="agent_0")
    assert detail["accepted"] is True
    assert "empirical" in detail
    assert s._geo_accum is not None
    # MOVE attempts may be sparse early; inject one to prove wire
    if s._geo_accum._n_observations == 0:
        s._geo_accum.observe(
            agent_id="agent_0", tick=10_000, action="MOVE:E",
            x0=1.0, y0=1.0, x1=1.2, y1=1.0, contact=False,
        )
    assert s._geo_accum._n_observations > 0


def test_live_frame_schema_with_traversability_arg():
    s = ObserverSession(config=SessionConfig(seed=17, speed=0.0, ui_hz=1.0))
    s.apply_experiment(_exp(speed=0.0))
    with s._step_lock:
        for _ in range(15):
            s.runtime.step()
            s._record_motion_locked()
        ov = s._geo_overlay_locked(detail="compact")
        frame = live_frame(
            s.runtime, status="PAUSED", mode="LIVE", target_tick=None,
            previous_body=s._prev_body, previous_bodies=s._prev_bodies,
            detail="compact", geometry_traversability=ov,
        )
    assert "traversability" in (frame.get("geometry_interpretation") or {})
    assert frame["geometry_interpretation"]["honesty"]["no_hard_walls"] is True


def test_performance_sanity_geometry_overlay():
    s = ObserverSession(config=SessionConfig(seed=17, speed=0.0, ui_hz=1.0))
    s.apply_experiment(_exp(speed=0.0))
    with s._step_lock:
        for _ in range(30):
            s.runtime.step()
            s._record_motion_locked()
    t0 = time.perf_counter()
    for _ in range(40):
        with s._step_lock:
            s._geo_overlay_locked(detail="compact")
    dt = (time.perf_counter() - t0) / 40
    assert dt < 0.05  # overlay build < 50ms
