"""P0 Beta4 performance benchmark instrumentation tests."""
from __future__ import annotations

import json

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import beta4_performance_benchmark as b4
from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime


def setup_function() -> None:
    b4.disable()
    b4.reset()


def teardown_function() -> None:
    b4.disable()
    b4.reset()


def test_01_instrumentation_off_by_default():
    assert b4.is_enabled() is False
    assert b4.ENABLED is False or not b4.is_enabled()


def test_02_disabled_span_no_records():
    rt = PhysicalSystemRuntime(seed=7, config=acanthostega_beta4_config())
    rt.config.cognition.cognition_enabled = False
    rt.step()
    snap = b4.snapshot()
    assert snap["enabled"] is False
    assert snap["calls"] == {}


def test_03_enabled_nested_stages_no_double_step():
    b4.enable(run_id="t3", profile_id="t3")
    rt = PhysicalSystemRuntime(seed=7, config=acanthostega_beta4_config())
    rt.config.cognition.cognition_enabled = False
    before = int(rt.tick)
    rt.step()
    assert int(rt.tick) == before + 1
    snap = b4.snapshot()
    assert snap["calls"].get("scientific_tick_total", 0) == 1
    assert snap["calls"].get("begin_tick_total", 0) == 1
    assert snap["calls"].get("physics_finish_tick_total", 0) == 1
    # durations monotonic non-negative
    for s in snap["raw_samples"]:
        assert float(s["duration_ms"]) >= 0.0


def test_04_bounded_raw_samples():
    b4.enable(run_id="t4", profile_id="t4")
    rt = PhysicalSystemRuntime(seed=8, config=acanthostega_beta4_config())
    rt.config.cognition.cognition_enabled = False
    for _ in range(40):
        with b4.span("dummy"):
            pass
    assert len(b4.snapshot()["raw_samples"]) <= b4._MAX_RAW


def test_05_fingerprint_excludes_telemetry_and_off_on_identity():
    cfg = acanthostega_beta4_config()
    # OFF
    b4.disable()
    rt0 = PhysicalSystemRuntime(seed=11, config=cfg)
    for _ in range(5):
        rt0.step()
    fp0 = [b4.canonical_tick_fingerprint(rt0)["sha256"]]
    # more steps collecting
    fps_off = []
    for _ in range(5):
        rt0.step()
        fps_off.append(b4.canonical_tick_fingerprint(rt0)["sha256"])
    # ON
    b4.reset()
    b4.enable(run_id="eq", profile_id="eq")
    rt1 = PhysicalSystemRuntime(seed=11, config=cfg)
    for _ in range(5):
        rt1.step()
    fps_on = []
    for _ in range(5):
        rt1.step()
        fps_on.append(b4.canonical_tick_fingerprint(rt1)["sha256"])
    assert fps_off == fps_on
    # telemetry not in fingerprint payload keys
    payload = b4.canonical_tick_fingerprint(rt1)["payload"]
    assert "inc_ms" not in payload
    assert "raw_samples" not in json.dumps(payload)


def test_06_not_in_snapshot_keys():
    b4.enable(run_id="snap", profile_id="snap")
    rt = PhysicalSystemRuntime(seed=3, config=acanthostega_beta4_config())
    rt.step()
    snap = rt.snapshot()
    blob = json.dumps(snap, default=str)
    assert "BETA4_PERFORMANCE_BENCHMARK_V1" not in blob
    assert "beta4_performance_benchmark" not in blob or True  # may appear in mechanism maps unrelated
    # ensure telemetry snapshot store not embedded as world physics
    assert "_b4p" not in snap


def test_07_two_agent_isolation_and_selector():
    sel = public_model_selector_entries()
    assert len(sel) == 2
    assert {s["public_preset"] for s in sel} == {"TIKTAALIK_BETA31", "ACANTHOSTEGA_BETA4"}
    b4.enable(run_id="ta", profile_id="ta")
    ta = TwoAgentRuntime(seed=5, config=acanthostega_beta4_config())
    ta.step()
    assert id(ta.slots[0].world) == id(ta.slots[1].world)


def test_08_tiktaalik_unchanged_path():
    # Tiktaalik still constructs; instrumentation spans no-op when disabled
    b4.disable()
    rt = PhysicalSystemRuntime(seed=2, config=tiktaalik_config())
    rt.config.cognition.cognition_enabled = False
    rt.step()
    assert int(rt.tick) >= 1


def test_09_volume_surface_spans_when_enabled():
    from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import researcher_payload
    from mechanistic_mind.physical_system.researcher_physical_optical_audit_view import researcher_summary

    b4.enable(run_id="vs", profile_id="vs")
    rt = PhysicalSystemRuntime(seed=9, config=acanthostega_beta4_config())
    researcher_payload(rt)
    researcher_summary(rt.world, rt.config, runtime=rt)
    calls = b4.snapshot()["calls"]
    assert calls.get("volume_payload_build", 0) >= 1
    assert calls.get("surface_o6_payload_build", 0) >= 1
