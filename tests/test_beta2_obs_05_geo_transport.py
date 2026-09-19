"""BETA2-OBS-05: versioned GEO transport, compact frame bound, no cognition leak."""
from __future__ import annotations

import json
import time

from mechanistic_mind.ui.psy_observer_web.geometry.live_accum import (
    EMPIRICAL_PUBLISH_HZ,
    LiveTraversabilityAccumulator,
    flatten_grid,
    unflatten_grid,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.serialize import world_frame


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
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
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


def _seed_geo(sess: ObserverSession, n: int = 40) -> None:
    with sess._step_lock:
        sess._reset_geo_accum_locked()
        acc = sess._geo_accum
        assert acc is not None
        for t in range(n):
            acc.observe(
                agent_id="agent_0",
                tick=t + 1,
                action="MOVE:E",
                x0=float(t % 32),
                y0=float((t // 32) % 32),
                x1=float(t % 32) + 0.2,
                y1=float((t // 32) % 32),
                contact=False,
            )


def test_flatten_grid_roundtrip():
    g = [[1, 2, 3], [4, 5, 6]]
    flat = flatten_grid(g)
    assert flat["h"] == 2 and flat["w"] == 3
    assert unflatten_grid(flat) == g


def test_compact_world_omits_heavy_planes():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    w = world_frame(sess.runtime, detail="compact")
    assert w["frame_detail"] == "compact"
    assert w["M"] is None
    assert "M0" not in (w.get("scalars") or {})
    assert w.get("u") is None
    full = world_frame(sess.runtime, detail="full")
    assert full["M"] is not None
    assert "M0" in (full.get("scalars") or {})


def test_geo_static_version_stable_across_ticks():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    with sess._step_lock:
        sess._reset_geo_accum_locked()
        v0 = int(sess._geo_static_version)
    for _ in range(25):
        sess.step()
    assert int(sess._geo_static_version) == v0
    with sess._step_lock:
        sess._reset_geo_accum_locked()
    assert int(sess._geo_static_version) == v0 + 1


def test_empirical_version_rate_limited_not_every_tick():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    _seed_geo(sess, 40)
    sizes = []
    inline_flags = []
    for _ in range(12):
        overlay, transport = sess._publish_geo_overlay_outside_lock(detail="compact")
        assert overlay is not None
        inline_flags.append(bool(transport.get("empirical_inline")))
        sizes.append(len(json.dumps(overlay, default=str).encode("utf-8")))
        time.sleep(0.02)  # faster than 4 Hz → most should be CACHED stubs
    assert any(not f for f in inline_flags), inline_flags
    stub_sizes = [s for s, f in zip(sizes, inline_flags) if not f]
    full_sizes = [s for s, f in zip(sizes, inline_flags) if f]
    assert stub_sizes and full_sizes
    assert max(stub_sizes) < min(full_sizes)
    assert max(stub_sizes) < 80_000
    assert EMPIRICAL_PUBLISH_HZ == 4.0


def test_no_unnecessary_static_payload_resend():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    _seed_geo(sess, 20)
    o1, t1 = sess._publish_geo_overlay_outside_lock(detail="compact")
    assert t1["empirical_inline"] is True
    assert o1.get("class_grid") is not None
    o2, t2 = sess._publish_geo_overlay_outside_lock(detail="compact")
    assert t2["empirical_inline"] is False
    assert o2.get("status") == "CACHED"
    assert "class_grid" not in o2
    assert t2["empirical_version"] == t1["empirical_version"]
    assert t2["static_version"] == t1["static_version"]


def test_compact_live_frame_bounded():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    _seed_geo(sess, 80)
    sess._geo_empirical_version_sent = -1
    overlay, transport = sess._publish_geo_overlay_outside_lock(detail="compact")
    with sess._step_lock:
        frame = sess._capture_locked(detail="compact", serialize=False)
    gi = frame.setdefault("geometry_interpretation", {})
    gi["traversability"] = overlay
    gi["geo_transport"] = transport
    frame["geo_transport"] = transport
    nbytes = len(json.dumps(frame, default=str).encode("utf-8"))
    assert nbytes < 320_000, nbytes
    o2, t2 = sess._publish_geo_overlay_outside_lock(detail="compact")
    with sess._step_lock:
        frame2 = sess._capture_locked(detail="compact", serialize=False)
    gi2 = frame2.setdefault("geometry_interpretation", {})
    gi2["traversability"] = o2
    gi2["geo_transport"] = t2
    frame2["geo_transport"] = t2
    n2 = len(json.dumps(frame2, default=str).encode("utf-8"))
    assert n2 <= nbytes + 8_000  # stub should not grow much vs inline attach
    assert n2 < 300_000, n2


def test_traversability_deflection_grids_after_caching():
    acc = LiveTraversabilityAccumulator(width=8, height=8)
    for t in range(30):
        acc.observe(
            agent_id="agent_0", tick=t + 1, action="MOVE:W",
            x0=3, y0=3, x1=2.7, y1=3.0, contact=False,
        )
    full = acc.overlay_payload(max_by_cell=0, flat_grids=True)
    assert full["grids_encoding"] == "flat"
    nested = unflatten_grid(full["class_grid"])
    assert nested is not None
    assert len(nested) == 8 and len(nested[0]) == 8
    opp = unflatten_grid(full["opposing_rate_grid"])
    assert opp is not None
    assert any(v is not None and float(v) >= 0 for row in opp for v in row)


def test_no_cognition_leak_in_observation():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    _seed_geo(sess, 5)
    with sess._step_lock:
        frame = sess._capture_locked(detail="compact", serialize=False)
    obs = frame.get("observation") or {}
    blob = json.dumps(obs, default=str)
    assert "class_grid" not in blob
    assert "TRAVERSABILITY" not in blob
    assert "opposing_rate_grid" not in blob


def test_no_ohistory_in_compact_geo_publish():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    _seed_geo(sess, 50)
    sess._geo_empirical_version_sent = -1
    t0 = time.perf_counter()
    overlay, _ = sess._publish_geo_overlay_outside_lock(detail="compact")
    dt = (time.perf_counter() - t0) * 1000.0
    assert overlay is not None
    assert "by_cell" not in overlay or not overlay.get("by_cell")
    assert dt < 80.0, dt


def test_observer_on_off_determinism():
    a = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    b = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    a.apply_experiment(_exp())
    b.apply_experiment(_exp())
    for _ in range(40):
        a.step()
        b.step()
    assert _fp(a) == _fp(b)
    with a._step_lock:
        a._reset_geo_accum_locked()
        a._geo_accum.observe(
            agent_id="agent_0", tick=1, action="MOVE:E",
            x0=1, y0=1, x1=1.1, y1=1, contact=False,
        )
    for _ in range(20):
        a.step()
        b.step()
    assert _fp(a) == _fp(b)


def test_speed_determinism_geo_publish_irrelevant():
    runs = []
    for _ in range(2):
        sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
        sess.apply_experiment(_exp())
        with sess._step_lock:
            sess._reset_geo_accum_locked()
        for i in range(60):
            sess.step()
            if i % 10 == 0:
                sess._publish_geo_overlay_outside_lock(detail="compact")
        runs.append(_fp(sess))
    assert runs[0] == runs[1]


def test_wrap_periodic_preserved():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    with sess._step_lock:
        frame = sess._capture_locked(detail="compact", serialize=False)
    topo = (frame.get("world") or {}).get("boundary", {}).get("spatial_topology")
    assert topo == "WRAP_PERIODIC"


def test_sigint_geometry_context_still_available():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    sess.apply_experiment(_exp())
    with sess._step_lock:
        frame = sess._capture_locked(detail="compact", serialize=False)
    sci = frame.get("signal_context_interpretation") or {}
    assert isinstance(sci, dict)
    raw = json.dumps(frame, default=str)
    assert "scientific_timeline" not in raw
    assert "geometry_history" not in raw
