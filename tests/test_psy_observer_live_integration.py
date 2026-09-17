from copy import deepcopy

from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.serialize import body_frame


def test_atomic_frame_and_step_receipt():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=16))
    f = s.step(1)
    assert f["control_receipt"]["accepted"]
    assert f["control_receipt"]["operation"] == "STEP"
    assert f["observation"]["tick_consistent"]
    ticks = f["observation"]["ticks"]
    assert set(ticks.values()) == {1}
    assert f["header"]["observation_frame_id"] == f["observation"]["observation_frame_id"]


def test_inspect_and_replay_never_mutate_live_runtime():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=16))
    s.step(4)
    tick = s.history()["ticks"][1]
    before = s.runtime.snapshot()
    inspected = s.frame_at_tick(tick)
    replayed = s.replay_frame(tick)
    after = s.runtime.snapshot()
    assert inspected["header"]["mode"] == "INSPECT"
    assert replayed["header"]["mode"] == "REPLAY"
    assert before == after


def test_confirmed_mechanism_toggle_changes_runtime_and_frame():
    s = ObserverSession(SessionConfig(seed=17))
    out = s.set_mechanism("discrete_action_work_accounting", False)
    assert out["control_receipt"]["accepted"]
    assert not s.runtime.config.discrete_action_work.enabled
    item = next(
        m for m in out["mechanism_result"]["mechanisms"]
        if m["id"] == "discrete_action_work_accounting"
    )
    assert item["enabled"] is False
    assert out["model_banner"]["mechanisms"]["enabled"][
        "discrete_action_work_accounting"
    ] is False


def test_mechanism_dependency_warning_no_hidden_cascade():
    s = ObserverSession(SessionConfig(seed=17))
    out = s.set_mechanism("complementary_resource_conversion", False)
    assert out["dependency_warnings"]
    assert s.runtime.config.complementary_resources.transfer_A_enabled
    assert s.runtime.config.complementary_resources.transfer_B_enabled


def test_reset_rebuilds_actual_runtime_and_generation():
    s = ObserverSession(SessionConfig(seed=17))
    s.step(2)
    g0 = s._runtime_generation
    f = s.apply_experiment({
        "seed": 23,
        "world": {"width": 24, "height": 20, "boundary_mode": "WRAP_PERIODIC"},
    })
    assert f["control_receipt"]["requires_reset"]
    assert f["header"]["tick"] == 0
    assert f["header"]["seed"] == 23
    assert f["world"]["width"] == 24 and f["world"]["height"] == 20
    assert f["header"]["runtime_generation"] == g0 + 1


def test_apply_experiment_cognition_flag_rebuilds_runtime():
    s = ObserverSession(SessionConfig(seed=17))
    f = s.apply_experiment({
        "seed": 17,
        "cognition_enabled": False,
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
    })
    assert f["control_receipt"]["accepted"]
    assert f["control_receipt"]["requires_reset"]
    assert not s.runtime.config.cognition.cognition_enabled
    assert f["experiment"]["runtime"]["cognition_enabled"] is False
    assert f["mind"]["status"] == "INACTIVE"


def test_inspect_missing_tick_does_not_invent_history():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.step(2)
    live = s.runtime.tick
    missing = s.frame_at_tick(999)
    assert missing["error"] == "NOT AVAILABLE"
    assert missing["reason"].startswith("NOT_RECORDED")
    assert missing["header"]["live_runtime_tick"] == live
    assert s.runtime.tick == live


def test_historical_compatibility_persists_until_reset():
    s = ObserverSession(SessionConfig(seed=17))
    payload = deepcopy(s.snapshot())
    payload["config"].pop("discrete_action_work")
    s.restore(payload)
    later = s.step(1)
    assert later["historical_compatibility"]["active"]
    reset = s.reset(seed=17)
    assert "historical_compatibility" not in reset or not reset.get("historical_compatibility", {}).get("active")


def test_body_sites_are_actual_oriented_deformed_geometry():
    s = ObserverSession(SessionConfig(seed=17))
    s.runtime.body.theta = 0.5
    f = body_frame(s.runtime)
    assert len(f["sites"]) == len(s.runtime.config.body.footprint)
    assert all("rest_local" in x and "deformed_local" in x and "world" in x for x in f["sites"])


def test_snapshot_meta_and_restore_schema_guard():
    s = ObserverSession(SessionConfig(seed=17))
    s.step(1)
    meta = s.snapshot_meta()
    assert meta["schema"] == "mm.physical_system.snapshot.v2"
    assert "world" not in meta
    assert "discrete_action_work" in meta["config_keys"]
    before = s.runtime.snapshot()
    rejected = s.restore({"tick": 0, "config": {}})
    assert rejected["control_receipt"]["accepted"] is False
    assert "schema" in (rejected["control_receipt"]["reason"] or "").lower()
    assert s.runtime.snapshot() == before


def test_buffers_remain_bounded():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    for _ in range(30):
        s.step(1)
    assert len(s._buffer) <= 8
    assert len(s._timeline) <= s._timeline.maxlen
    assert len(s._trajectory) <= s._trajectory.maxlen
    assert len(s._telemetry) <= s._telemetry.maxlen
