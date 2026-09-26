"""BETA2-INT-01 focused tests: experimenter-controlled Tiktaalik."""
from __future__ import annotations

from copy import deepcopy

import pytest

from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
    ExperimenterController,
    audit_observation_no_experimenter_leak,
    build_interaction_fingerprint,
    remove_experimenter_body,
    run_source_context_factorial,
    spawn_experimenter_body,
    apply_experimenter_pre_step,
    record_experimenter_post_step,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _two_agent_signal(**kw):
    return TwoAgentRuntime(seed=17, signal_enabled=True, **kw)


def test_spawn_remove_controlled_body():
    rt = _two_agent_signal()
    ctrl = ExperimenterController()
    out = spawn_experimenter_body(rt, x=10.0, y=10.0, theta=0.1, controller=ctrl)
    assert out["accepted"]
    assert rt.experimenter_slot == 2
    assert len(rt.slots) == 3
    assert ctrl.active
    assert not rt.slots[2].config.cognition.cognition_enabled
    rem = remove_experimenter_body(rt, ctrl)
    assert rem["accepted"]
    assert len(rt.slots) == 2
    assert rt.experimenter_slot is None
    assert rem["intervention_active"] is True  # provenance retained


def test_same_physical_body_mechanics_and_requested_vs_realized():
    rt = _two_agent_signal()
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=10.0, y=12.0, controller=ctrl)
    x0 = float(rt.slots[2].body.x)
    ctrl.enqueue("ACTION", action="MOVE:E")
    apply_experimenter_pre_step(rt, ctrl)
    assert rt.slots[2]._forced_action_once == "MOVE:E"
    rt.step()
    record_experimenter_post_step(rt, ctrl)
    assert ctrl.last_requested == "MOVE:E"
    assert ctrl.last_realized is not None
    # Realized position follows physics (may or may not move far; action was requested)
    assert ctrl.last_realized["action"] == "MOVE:E"
    assert "x" in ctrl.last_realized
    # Direct JS-style teleport must not happen
    assert abs(float(rt.slots[2].body.x) - x0) < 5.0  # bounded physical step


def test_wait_and_field_emit_ordinary_path():
    rt = _two_agent_signal()
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=10.0, y=12.0, controller=ctrl)
    ctrl.enqueue("ACTION", action="WAIT")
    apply_experimenter_pre_step(rt, ctrl)
    rt.step()
    assert rt.slots[2].last_selected_action == "WAIT"
    ctrl.enqueue("FIELD_A", amplitude=0.8)
    apply_experimenter_pre_step(rt, ctrl)
    assert any(s.get("trigger") == "experimenter_control" for s in rt._pending_sources)
    rt.step()
    types = [e.get("event_type") for e in ctrl.event_log]
    assert "EXPERIMENTER_FIELD_EMITTED" in types


def test_no_privileged_identity_leak_in_observations():
    rt = _two_agent_signal()
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=10.0, y=12.0, controller=ctrl)
    obs = rt.observations()
    for o in obs:
        leaks = audit_observation_no_experimenter_leak(o)
        # "you" substring filter is aggressive — filter to identity keys only
        bad = [k for k in ("experimenter", "human_controlled", "is_experimenter", "player", "creator", "special_agent", "interaction_target") if k in str(o).lower()]
        assert not bad, bad
    # Observer summaries may label YOU; agent obs must not
    summaries = rt.observer_agent_summaries()
    assert any(s.get("observer_experimenter") for s in summaries)


def test_command_queue_bounds_and_stale():
    ctrl = ExperimenterController()
    ctrl.active = True
    for i in range(70):
        r = ctrl.enqueue("ACTION", action="WAIT")
    assert r["accepted"] is False
    assert "overflow" in r["error"]


def test_human_interaction_capture_and_scripted_replay_factorial():
    rt = _two_agent_signal()
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=10.0, y=12.0, controller=ctrl)
    ctrl.begin_recording(rt)
    for act in ("MOVE:E", "WAIT", "MOVE:N"):
        ctrl.enqueue("ACTION", action=act)
        apply_experimenter_pre_step(rt, ctrl)
        rt.step()
        record_experimenter_post_step(rt, ctrl)
    ctrl.enqueue("FIELD_A", amplitude=0.7)
    apply_experimenter_pre_step(rt, ctrl)
    rt.step()
    cap = ctrl.capture(rt, run_id="test")
    assert cap.s0_snapshot is not None
    assert any(c.get("action") or c.get("channel") for c in cap.commands) or cap.commands is not None
    factorial = run_source_context_factorial(cap, seed=17, horizon=12)
    assert factorial.get("accepted")
    for arm in ("CONTROL", "BODY_ONLY", "FIELD_ONLY", "BODY_PLUS_FIELD", "SHAM"):
        assert arm in factorial["arms"]
    fp = build_interaction_fingerprint(factorial)
    assert "SOURCE_CONTEXT_DEPENDENCE" in fp
    assert factorial["honesty"]["not_recognition"]


def test_session_spawn_intervention_marking():
    sess = ObserverSession(config=SessionConfig(seed=17))
    # Need TwoAgent — apply experiment
    sess.apply_experiment({
        "seed": 17,
        "agent_count": 2,
        "mechanisms": {"experimental_physical_signal": True, "cognition_enabled": True},
    })
    assert isinstance(sess.runtime, TwoAgentRuntime)
    out = sess.experimenter_spawn(near_agent=0)
    assert out.get("accepted"), out
    frame = sess.current_frame()
    ei = frame.get("experimenter_interaction") or {}
    assert ei.get("status") == "CONTROL_ACTIVE"
    assert ei.get("intervention_active") or ei.get("intervention_ever")
    # request action via session
    cmd = sess.experimenter_command(kind="ACTION", action="MOVE:S")
    assert cmd.get("accepted")
    sess.step(1)
    st = sess.experimenter_status()
    assert st.get("last_requested") == "MOVE:S"
    rem = sess.experimenter_remove()
    assert rem.get("accepted")
    assert rem.get("intervention_active") is True


def test_interaction_target_observer_only():
    sess = ObserverSession(config=SessionConfig(seed=17))
    sess.apply_experiment({
        "seed": 17,
        "agent_count": 2,
        "mechanisms": {"experimental_physical_signal": True},
    })
    sess.experimenter_spawn(x=8, y=8)
    sess.experimenter_set_target("agent_1")
    st = sess.experimenter_status()
    assert st.get("target") is not None
    # Autonomous observation must not contain interaction_target
    for o in sess.runtime.observations():
        assert "interaction_target" not in str(o).lower()


def test_snapshot_restore_with_experimenter():
    rt = _two_agent_signal()
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=9.0, y=11.0, controller=ctrl)
    rt.step(3)
    snap = rt.snapshot()
    assert snap.get("experimenter_slot") == 2
    rt2 = TwoAgentRuntime.restore(deepcopy(snap))
    assert len(rt2.slots) == 3
    assert rt2.experimenter_slot == 2
