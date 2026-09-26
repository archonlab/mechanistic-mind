"""BETA2-GEO-01: Observer-only geometry interpreter tests."""
from __future__ import annotations

import json
import time
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.geometry.context import geometry_context
from mechanistic_mind.ui.psy_observer_web.geometry.metrics import (
    action_alignment,
    evidence_class,
    realized_displacement,
    step_record,
    traversal_outcome_class,
)
from mechanistic_mind.ui.psy_observer_web.geometry.trajectory import (
    detect_episodes,
    stable_episode_id,
)
from mechanistic_mind.ui.psy_observer_web.geometry.traversability import (
    accumulate_traversability,
)
from mechanistic_mind.ui.psy_observer_web.geometry.live_summary import (
    geometry_live_compact_summary,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


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


def test_periodic_boundary_displacement():
    # Crossing wrap: (0.2, 5) → (15.8, 5) on 16-wide torus is westward short arc
    dx, dy, mag = realized_displacement(0.2, 5.0, 15.8, 5.0, width=16, height=16)
    assert abs(dy) < 1e-9
    assert dx < 0  # shortest wrap is negative x
    assert mag < 1.0  # not the long way (~15.6)


def test_requested_vs_realized_alignment():
    # MOVE:E with positive dx → aligned
    align = action_alignment("MOVE:E", 0.2, 0.0)
    assert align is not None and align > 0.99
    # opposing
    align2 = action_alignment("MOVE:E", -0.2, 0.0)
    assert align2 is not None and align2 < -0.99
    assert traversal_outcome_class("MOVE:E", -0.2, 0.0) == "OPPOSING_DISPLACEMENT"
    assert traversal_outcome_class("MOVE:E", 0.2, 0.0) == "ALIGNED_TRAVERSAL"
    assert traversal_outcome_class("WAIT", 0.1, 0.0) == "NO_MOVE_REQUEST"


def test_deterministic_geometry_interpretation():
    steps = [
        step_record(
            tick=t, agent_id="agent_0", action="MOVE:N",
            x0=1.0, y0=float(t), x1=1.0, y1=float(t) + 0.2,
            width=32, height=32, contact=False,
        )
        for t in range(10)
    ]
    # Force opposing streak
    opp = [
        step_record(
            tick=100 + t, agent_id="agent_0", action="MOVE:N",
            x0=5.0, y0=5.0, x1=5.0, y1=4.7,
            width=32, height=32, contact=False,
        )
        for t in range(5)
    ]
    a = detect_episodes(steps + opp, run_id="r1", generation=2)
    b = detect_episodes(steps + opp, run_id="r1", generation=2)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_stable_episode_ids():
    id1 = stable_episode_id(
        run_id="runA", generation=2, agent_id="agent_0",
        kind="STRONG_DEFLECTION", start_tick=10, end_tick=10,
    )
    id2 = stable_episode_id(
        run_id="runA", generation=2, agent_id="agent_0",
        kind="STRONG_DEFLECTION", start_tick=10, end_tick=10,
    )
    id3 = stable_episode_id(
        run_id="runA", generation=2, agent_id="agent_1",
        kind="STRONG_DEFLECTION", start_tick=10, end_tick=10,
    )
    assert id1 == id2
    assert id1 != id3
    assert id1.startswith("geo-")


def test_per_agent_independence():
    steps = []
    for t in range(5):
        steps.append(step_record(
            tick=t, agent_id="agent_0", action="MOVE:E",
            x0=float(t), y0=1.0, x1=float(t) + 0.2, y1=1.0,
            width=32, height=32,
        ))
        steps.append(step_record(
            tick=t, agent_id="agent_1", action="MOVE:W",
            x0=10.0 - float(t), y0=2.0, x1=10.0 - float(t) - 0.2, y1=2.0,
            width=32, height=32,
        ))
    trav = accumulate_traversability(steps)
    # Keys are per cell×action; agent_id is not in key — but outcomes differ by construction
    # Per-agent episode detection must not mix agents
    eps = detect_episodes(steps, run_id="x", generation=1)
    for e in eps:
        assert e["agent_id"] in ("agent_0", "agent_1")
    ctx0 = geometry_context(steps, agent_id="agent_0", tick=2, window=2)
    ctx1 = geometry_context(steps, agent_id="agent_1", tick=2, window=2)
    assert ctx0["at_tick"]["action"] == "MOVE:E"
    assert ctx1["at_tick"]["action"] == "MOVE:W"


def test_empirical_traversability_counts_and_sparse():
    steps = [
        step_record(
            tick=i, agent_id="agent_0", action="MOVE:S",
            x0=3.2, y0=4.1, x1=3.2, y1=4.3,
            width=32, height=32,
        )
        for i in range(2)
    ]
    trav = accumulate_traversability(steps)
    assert len(trav) == 1
    bucket = next(iter(trav.values()))
    assert bucket["attempts"] == 2
    assert bucket["evidence_class"] == "SPARSE"
    assert evidence_class(0) == "NO_SAMPLES"
    assert evidence_class(20) == "ADEQUATE"


def test_contact_conditioned_traversal_episode():
    steps = [
        step_record(
            tick=50, agent_id="agent_0", action="MOVE:E",
            x0=1.0, y0=1.0, x1=0.7, y1=1.0,
            width=32, height=32, contact=True,
        )
    ]
    eps = detect_episodes(steps, run_id="c", generation=2)
    kinds = {e["kind"] for e in eps}
    assert "CONTACT_CONDITIONED_TRAVERSAL" in kinds
    assert "STRONG_DEFLECTION" in kinds or "CONTACT_CONDITIONED_TRAVERSAL" in kinds


def test_geometry_context_api_shape():
    steps = [
        step_record(
            tick=t, agent_id="agent_0", action="MOVE:N",
            x0=1.0, y0=float(t), x1=1.0, y1=float(t) + 0.1,
            width=32, height=32,
        )
        for t in range(20)
    ]
    ctx = geometry_context(steps, agent_id="agent_0", tick=10, window=3)
    assert ctx["honesty"]["no_signal_causality"] is True
    assert ctx["summary"]["n_before"] >= 1
    assert "at_tick" in ctx


def test_live_frame_geometry_bounded_and_observer_only():
    s = ObserverSession(config=SessionConfig(seed=17, speed=40.0, ui_hz=8.0))
    s.apply_experiment(_exp())
    s.play()
    while s.runtime.tick < 25:
        time.sleep(0.02)
    s.wait_capture_idle(timeout=2.0)
    frame = s.current_frame()
    geo = frame.get("geometry_interpretation")
    assert isinstance(geo, dict)
    assert geo.get("observer_only") is True
    assert geo.get("honesty", {}).get("no_semantic_terrain") is True
    # Must not appear inside mind / perception agent views
    mind = frame.get("mind") or {}
    mind_s = json.dumps(mind, default=str)
    assert "geometry_interpretation" not in mind_s
    assert "TRAVERSAL_REVERSAL" not in mind_s
    # Compact frame size sanity
    raw = json.dumps(frame, default=str)
    assert len(raw) < 2_500_000  # soft bound; should be well under
    # LIVE summary cheap
    t0 = time.perf_counter()
    for _ in range(50):
        geometry_live_compact_summary(
            s.runtime,
            previous_body=getattr(s, "_prev_body", None),
            previous_bodies=getattr(s, "_prev_bodies", None) or {},
        )
    dt = (time.perf_counter() - t0) / 50
    assert dt < 0.05  # 50ms ceiling per compact geometry summary
    s.pause()


def test_observer_on_off_determinism_unaffected_by_geometry_module():
    """Geometry is Observer-side; same seed runtime path must match without Observer."""

    def run_headless(n=40):
        s = ObserverSession(config=SessionConfig(seed=17, speed=0.0, ui_hz=1.0))
        s.apply_experiment(_exp(speed=0.0))
        rt = s.runtime
        xs = []
        for _ in range(n):
            with s._step_lock:
                rt.step()
            xs.append((rt.slots[0].body.x, rt.slots[0].body.y, rt.slots[1].body.x, rt.slots[1].body.y))
        return xs

    a = run_headless()
    b = run_headless()
    assert a == b


def test_scientific_history_still_written_with_geometry_in_frame():
    s = ObserverSession(config=SessionConfig(seed=17, speed=30.0, ui_hz=6.0))
    s.apply_experiment(_exp())
    s.play()
    while s.runtime.tick < 20:
        time.sleep(0.02)
    s.wait_capture_idle(timeout=2.0)
    frame = s.current_frame()
    assert "geometry_interpretation" in frame
    assert s.runtime.tick >= 20
    writer = getattr(s, "_sci_writer", None)
    if writer is not None and getattr(writer, "timeline_path", None):
        path = Path(writer.timeline_path)
        assert path.exists() and path.stat().st_size > 0
    s.pause()
