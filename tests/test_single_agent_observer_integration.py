"""Regression: single-agent Observer HUD action + experimenter spawn (N>=1)."""
from __future__ import annotations

from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
    ExperimenterController,
    promote_physical_to_two_agent_host,
    remove_experimenter_body,
    spawn_experimenter_body,
)
from mechanistic_mind.ui.psy_observer_web.serialize import _agents_observer_frame, live_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def test_agents_observer_single_agent_includes_action():
    rt = PhysicalSystemRuntime(seed=17)
    rt.step(3)
    rows = _agents_observer_frame(rt)
    assert isinstance(rows, list) and len(rows) == 1
    assert rows[0]["observer_id"] == "agent_0"
    assert rows[0].get("selected_action") is not None
    assert rows[0]["selected_action"] == rt.last_selected_action


def test_agents_observer_two_agent_preserves_both():
    rt = TwoAgentRuntime(seed=17, signal_enabled=True)
    rt.step(3)
    rows = _agents_observer_frame(rt)
    assert len(rows) >= 2
    assert rows[0]["observer_id"] == "agent_0"
    assert rows[1]["observer_id"] == "agent_1"
    assert rows[0].get("selected_action") == rt.slots[0].last_selected_action
    assert rows[1].get("selected_action") == rt.slots[1].last_selected_action


def test_capture_frame_single_agent_agents_observer_not_null():
    rt = PhysicalSystemRuntime(seed=23)
    rt.step(2)
    frame = live_frame(
        rt, status="PAUSED", mode="HEADLESS", target_tick=None, previous_body=None, detail="compact",
    )
    ao = frame.get("agents_observer")
    assert isinstance(ao, list) and len(ao) == 1
    assert ao[0]["observer_id"] == "agent_0"
    assert ao[0].get("selected_action") == rt.last_selected_action
    # Index 0 must remain valid (not treated as missing)
    assert ao[0]["observer_id"]


def test_promote_preserves_autonomous_agent_identity():
    rt = PhysicalSystemRuntime(seed=41)
    rt.step(5)
    cog_id = id(rt.cognition)
    body_id = id(rt.body)
    act = rt.last_selected_action
    host = promote_physical_to_two_agent_host(rt)
    assert isinstance(host, TwoAgentRuntime)
    assert len(host.slots) == 1
    assert host.slots[0] is rt
    assert id(host.slots[0].cognition) == cog_id
    assert id(host.slots[0].body) == body_id
    assert host.slots[0].last_selected_action == act
    assert host.world is rt.world


def test_session_spawn_controlled_tiktaalik_one_agent():
    sess = ObserverSession(SessionConfig(seed=17, cognition_enabled=True, execution_mode="HEADLESS"))
    sess.apply_experiment({
        "seed": 17,
        "agent_count": 1,
        "cognition_enabled": True,
        "vision_radius": 3,
        "mechanisms": {"physical_near_field_vision": True, "spatiotemporal_climate_ecology": False},
    })
    assert isinstance(sess.runtime, PhysicalSystemRuntime)
    # Advance so action is non-null
    with sess._step_lock:
        for _ in range(3):
            sess._scientific_step_once_unlocked()
    out = sess.experimenter_spawn()
    assert out.get("accepted") is True, out
    assert isinstance(sess.runtime, TwoAgentRuntime)
    assert sess.runtime.experimenter_slot is not None
    st = sess.experimenter_status()
    assert st.get("status") == "CONTROL_ACTIVE"
    assert st.get("body_id")
    # Autonomous agent still present as slot 0
    assert len(sess.runtime.slots) == 2
    assert not getattr(sess.runtime.slots[0], "_experimenter_controlled", False)
    assert sess.runtime.slots[1].config.cognition.cognition_enabled is False
    rem = sess.experimenter_remove()
    assert rem.get("accepted") is True
    # Respawn
    out2 = sess.experimenter_spawn(near_agent=0)
    assert out2.get("accepted") is True, out2


def test_session_spawn_still_works_two_agent():
    sess = ObserverSession(SessionConfig(seed=17, cognition_enabled=True, execution_mode="HEADLESS"))
    sess.apply_experiment({
        "seed": 17,
        "agent_count": 2,
        "cognition_enabled": True,
        "vision_radius": 3,
        "mechanisms": {"physical_near_field_vision": True, "spatiotemporal_climate_ecology": False},
    })
    assert isinstance(sess.runtime, TwoAgentRuntime)
    out = sess.experimenter_spawn(near_agent=0)
    assert out.get("accepted") is True, out
    assert len(sess.runtime.slots) == 3
    bad = sess.experimenter_spawn(near_agent=99)
    assert bad.get("accepted") is False
    assert "SPAWN_REJECTED" in str(bad.get("error") or "")


def test_spawn_near_invalid_target_rejected():
    rt = TwoAgentRuntime(seed=17)
    ctrl = ExperimenterController()
    # Direct spawn OK
    assert spawn_experimenter_body(rt, x=5.0, y=5.0, controller=ctrl)["accepted"]
    remove_experimenter_body(rt, ctrl)
