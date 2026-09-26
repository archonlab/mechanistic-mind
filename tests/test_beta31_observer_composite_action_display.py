"""Observer HUD: final applied composite motor, not locomotor-only selected_action."""
from __future__ import annotations

from mechanistic_mind.physical_system.composite_motor import CompositeMotorOutput, OscillatorMotorComponent
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.composite_action_display import (
    observer_applied_composite_action_display,
)
from mechanistic_mind.ui.psy_observer_web.serialize import _agents_observer_frame, live_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _motor(**kwargs) -> dict:
    osc = kwargs.pop("oscillator", OscillatorMotorComponent())
    return CompositeMotorOutput(oscillator=osc, **kwargs).to_dict()


def test_full_composite_stable_order_once():
    mo = _motor(
        locomotion="MOVE:W",
        neck="NECK_RIGHT",
        oscillator=OscillatorMotorComponent(frequency_delta=1, amplitude_delta=-1, emit_trigger=True),
        push=True,
    )
    label = observer_applied_composite_action_display(mo, fallback="MOVE:W")
    assert label == "MOVE:W + NECK_RIGHT + OSC_FREQ_UP + OSC_AMP_DOWN + OSC_EMIT + PUSH"
    for tok in ("MOVE:W", "NECK_RIGHT", "OSC_EMIT", "OSC_FREQ_UP", "OSC_AMP_DOWN", "PUSH"):
        assert label.count(tok) == 1
    assert "NONE" not in label


def test_locomotor_only():
    mo = _motor(locomotion="MOVE:E", neck="NONE")
    assert observer_applied_composite_action_display(mo) == "MOVE:E"


def test_wait_plus_neck_hold():
    mo = _motor(locomotion="WAIT", neck="NECK_HOLD")
    assert observer_applied_composite_action_display(mo) == "WAIT + NECK_HOLD"
    assert "NECK_NONE" not in observer_applied_composite_action_display(mo)


def test_wait_plus_osc_emit():
    mo = _motor(locomotion="WAIT", neck="NONE", oscillator=OscillatorMotorComponent(emit_trigger=True))
    assert observer_applied_composite_action_display(mo) == "WAIT + OSC_EMIT"


def test_two_agent_compact_frame_independent_composites():
    rt = TwoAgentRuntime(seed=17, signal_enabled=True)
    rt.slots[0].last_selected_action = "MOVE:W"
    rt.slots[0].last_motor_output = _motor(
        locomotion="MOVE:W",
        neck="NECK_RIGHT",
        oscillator=OscillatorMotorComponent(frequency_delta=1, amplitude_delta=-1, emit_trigger=True),
        push=True,
    )
    rt.slots[1].last_selected_action = "MOVE:E"
    rt.slots[1].last_motor_output = _motor(locomotion="MOVE:E", neck="NECK_HOLD")
    frame = live_frame(
        rt, status="PAUSED", mode="HEADLESS", target_tick=None, previous_body=None, detail="compact",
    )
    rows = frame["agents_observer"]
    assert rows[0]["selected_action"] == "MOVE:W"
    assert rows[0]["composite_action_display"] == (
        "MOVE:W + NECK_RIGHT + OSC_FREQ_UP + OSC_AMP_DOWN + OSC_EMIT + PUSH"
    )
    assert rows[1]["selected_action"] == "MOVE:E"
    assert rows[1]["composite_action_display"] == "MOVE:E + NECK_HOLD"
    assert rows[0]["composite_action_display"] != rows[1]["composite_action_display"]


def test_minimal_session_compact_includes_composite_without_full_frame():
    s = ObserverSession(SessionConfig(seed=11, evidence_mode="SEARCH_COMPACT"))
    s.set_observer_detail_preset("MINIMAL")
    s.runtime.last_selected_action = "WAIT"
    s.runtime.last_motor_output = _motor(locomotion="WAIT", neck="NECK_HOLD")
    rows = _agents_observer_frame(s.runtime)
    assert rows[0]["composite_action_display"] == "WAIT + NECK_HOLD"
    frame = live_frame(
        s.runtime, status="RUNNING", mode="HEADLESS", target_tick=None, previous_body=None, detail="compact",
    )
    assert frame["observer"]["frame_detail"] == "compact"
    assert frame["agents_observer"][0]["composite_action_display"] == "WAIT + NECK_HOLD"


def test_single_agent_agents_observer_composite():
    rt = PhysicalSystemRuntime(seed=23)
    rt.last_selected_action = "MOVE:N"
    rt.last_motor_output = _motor(
        locomotion="MOVE:N",
        oscillator=OscillatorMotorComponent(emit_trigger=True),
    )
    rows = _agents_observer_frame(rt)
    assert rows[0]["observer_id"] == "agent_0"
    assert rows[0]["selected_action"] == "MOVE:N"
    assert rows[0]["composite_action_display"] == "MOVE:N + OSC_EMIT"
