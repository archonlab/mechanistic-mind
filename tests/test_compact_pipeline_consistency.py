"""Compact RUNNING frames must keep live pipeline stages available."""
from __future__ import annotations

import time

from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


STAGES = ["WORLD", "PERCEPTION", "BODY", "INTERNAL", "PREDICTION", "ACTION", "CONSEQUENCE"]


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
        "ui_hz": 10.0,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": mechs,
        **extra,
    }


def _stage_status(frame: dict) -> dict[str, str]:
    stages = ((frame.get("causal_chain") or {}).get("stages") or {})
    return {name: str((stages.get(name) or {}).get("status") or "MISSING") for name in STAGES}


def test_compact_pipeline_stages_persist_across_speed_changes():
    s = ObserverSession(config=SessionConfig(seed=17, speed=50.0, ui_hz=10.0))
    s.apply_experiment(_exp())
    s.set_speed(50)
    s.play()
    while s.runtime.tick < 30:
        time.sleep(0.02)
    s.wait_capture_idle(timeout=2.0)

    # Several compact publishes while RUNNING
    statuses = []
    for _ in range(5):
        time.sleep(0.12)
        s.wait_capture_idle(timeout=1.0)
        frame = s.current_frame()
        assert frame["header"].get("frame_detail") == "compact"
        st = _stage_status(frame)
        statuses.append(st)
        for name, status in st.items():
            assert status == "AVAILABLE", f"{name}={status} in compact RUNNING frame"

    # SET_SPEED must not introduce a richer schema that later vanishes
    s.set_speed(1.0)
    after_speed = _stage_status(s.current_frame())
    for name, status in after_speed.items():
        assert status == "AVAILABLE", f"after SET_SPEED {name}={status}"

    s.play()
    for _ in range(6):
        time.sleep(0.12)
        s.wait_capture_idle(timeout=1.0)
        st = _stage_status(s.current_frame())
        for name, status in st.items():
            assert status == "AVAILABLE", f"post-speed compact {name}={status}"

    s.set_speed(0.25)
    for _ in range(4):
        time.sleep(0.15)
        s.wait_capture_idle(timeout=1.0)
        st = _stage_status(s.current_frame())
        for name, status in st.items():
            assert status == "AVAILABLE", f"0.25x compact {name}={status}"

    # Both agents' views carry stages
    with s._lock:
        frame = s._published
    views = frame.get("agents_views") or {}
    for aid in ("agent_0", "agent_1"):
        assert aid in views
        stages = ((views[aid].get("causal_chain") or {}).get("stages") or {})
        assert all(str((stages.get(n) or {}).get("status")) == "AVAILABLE" for n in STAGES)

    # Ordinary RUNNING must not produce full captures via async path
    assert int(s._capture_detail_counts.get("full", 0)) == 0
    s.pause()
    assert s.current_frame()["header"].get("frame_detail") == "full"


def test_set_speed_while_running_uses_compact_not_full():
    s = ObserverSession(config=SessionConfig(seed=17, speed=1.0))
    s.apply_experiment(_exp())
    s.status = "RUNNING"
    out = s.set_speed(2.0)
    assert out["header"]["frame_detail"] == "compact"
    assert all(v == "AVAILABLE" for v in _stage_status(out).values())
