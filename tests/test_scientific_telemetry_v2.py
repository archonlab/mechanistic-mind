"""Scientific Telemetry V2 unit + equivalence smoke tests."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.scientific_history import (
    ScientificHistoryWriter,
    load_evidence_package,
)
from mechanistic_mind.ui.psy_observer_web.scientific_telemetry_v2 import (
    TELEMETRY_MODE_V1,
    TELEMETRY_MODE_V2,
    compact_event_v2,
    compact_tick_row_v2,
    detect_telemetry_schema,
    should_record_event_v2,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def test_compact_tick_drops_geo_nests():
    row = {
        "schema": "mm.psy_observer_web.scientific_tick.v1",
        "tick": 1,
        "agent_id": "agent_0",
        "body_id": "body-0",
        "action": "WAIT",
        "x": 1.0,
        "y": 2.0,
        "theta": 0.0,
        "vx": 0.0,
        "vy": 0.0,
        "speed": 0.0,
        "work": 1.0,
        "resource_A": 1.0,
        "resource_B": 1.0,
        "contact": False,
        "action_realization": {"huge": True},
        "work_ecology": {"huge": True},
        "locomotor_economy": {"huge": True},
        "vision_optical": {
            "available": True,
            "final_exo": {"exo_0": 0.1, "exo_1": 0.0, "exo_2": 0.0},
            "exo": {"exo_0": 0.1, "exo_1": 0.0, "exo_2": 0.0},
            "exo_without_foreign_bodies": {"exo_0": 0.1, "exo_1": 0.0, "exo_2": 0.0},
            "foreign_body_contribution": {"exo_0": 0.0, "exo_1": 0.0, "exo_2": 0.0},
            "foreign_body_total": 0.0,
            "body_exposure": False,
            "illumination": 1.0,
            "vision_enabled": True,
            "body_optics_enabled": True,
            "vision_radius": 1,
            "note": "long prose " * 20,
            "neighbors_optical": [],
        },
    }
    c = compact_tick_row_v2(row)
    assert "action_realization" not in c
    assert "work_ecology" not in c
    assert c["schema"].endswith(".v2")
    assert "note" not in (c.get("vision_optical") or {})
    assert c["vision_optical"]["final_exo"]["exo_0"] == 0.1


def test_scenario_event_compacted_not_dropped():
    big = {
        "type": "SCENARIO_SELECTED",
        "tick": 5,
        "actor_agent_id": "agent_0",
        "evidence": {
            "selected_action": "WAIT",
            "selected_scenario": {
                "action": "WAIT",
                "composition_path": [{"predicted": {"a": 1}}] * 20,
                "predicted_state_fragments": {"body.x": 1},
                "score": 0.5,
            },
        },
    }
    assert should_record_event_v2(big)
    c = compact_event_v2(big)
    assert c is not None
    assert c["evidence"]["selected_action"] == "WAIT"
    assert "composition_path" not in c["evidence"]
    assert len(json.dumps(c)) < len(json.dumps(big))


def test_body_moved_omitted_in_v2():
    assert not should_record_event_v2({"type": "BODY_MOVED", "tick": 1})
    assert compact_event_v2({"type": "BODY_MOVED", "tick": 1}) is None


def test_writer_v2_smaller_than_v1():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        s = ObserverSession(SessionConfig(seed=17, buffer_capacity=32, speed=50.0, results_root=str(tmp / "r")))
        s.apply_experiment({
            "seed": 17,
            "agent_count": 2,
            "cognition_enabled": True,
            "world": {"width": 16, "height": 16},
            "mechanisms": {
                "cognition_enabled": True,
                "experimental_physical_signal": True,
                "physical_near_field_vision": True,
                "prospective_scenario_competition": True,
            },
        })
        sizes = {}
        for mode in (TELEMETRY_MODE_V1, TELEMETRY_MODE_V2):
            d = tmp / mode
            d.mkdir()
            w = ScientificHistoryWriter(d, telemetry_mode=mode, checkpoint_every=0, flush_every=8)
            w.open({"run_id": mode, "seed": 17, "agent_count": 2})
            for _ in range(40):
                with s._step_lock:
                    s._scientific_step_once_unlocked()
                    with s._lock:
                        s._accumulate_events_locked()
                        fresh = list(s._event_ring)[-40:]
                        w.append_tick(s.runtime)
                        w.append_events(fresh)
            w.close()
            total = sum(p.stat().st_size for p in d.iterdir() if p.is_file())
            sizes[mode] = total
            pkg = load_evidence_package(evidence_dir=d, runtime_status="STOPPED")
            assert pkg["coverage"] in {"FULL", "PARTIAL", "COMPLETE"}
            if mode == TELEMETRY_MODE_V2:
                assert pkg["telemetry_schema"] == "V2_TIERED"
            else:
                assert pkg["telemetry_schema"] == "V1_FULL"
        assert sizes[TELEMETRY_MODE_V2] < sizes[TELEMETRY_MODE_V1] * 0.7


def test_detect_schema_v1_default():
    assert detect_telemetry_schema({}, None) == "V1_FULL"
    assert detect_telemetry_schema({"telemetry_mode": TELEMETRY_MODE_V2}, None) == "V2_TIERED"
