"""Focused PSC schedule authority / boundary / TwoAgent readback tests."""
from __future__ import annotations

from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BETA4,
    acanthostega_beta4_mechanism_map,
    preset_canonical,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.tiktaalik_eye import psc_off_ticks_status


def _draft(*, psc_off_ticks=1000, agent_count=2):
    canon = preset_canonical(PRESET_ACANTHOSTEGA_BETA4, seed=17)
    mechs = acanthostega_beta4_mechanism_map()
    return {
        "load_preset": True,
        "public_preset": PRESET_ACANTHOSTEGA_BETA4,
        "seed": 17,
        "agent_count": agent_count,
        "ecology_preset": "BASELINE_CLIMATE_DEFAULT",
        "psc_off_ticks": psc_off_ticks,
        "psc_motor_resolution": "OBSERVED_COMPOSITE",
        "world": {"width": 8, "height": 8, "boundary_mode": "WRAP_PERIODIC"},
        "vision": dict(canon.get("vision") or {}),
        "mechanisms": dict(mechs),
    }


def test_apply_preserves_schedule_and_readback_armed():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=1000))
    assert sess.runtime.config.cognition.psc_off_ticks == 1000
    st = psc_off_ticks_status(sess.runtime)
    assert st["psc"] == "OFF"
    assert st["schedule"] == 1000
    assert st["armed"] is True
    assert st["activated_tick"] is None


def test_boundary_threshold_3_exactly_once():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=3, agent_count=2))
    while sess.runtime.tick < 2:
        sess.runtime.step()
    st2 = psc_off_ticks_status(sess.runtime)
    assert st2["psc"] == "OFF"
    assert st2["armed"] is True
    sess.runtime.step()  # → tick 3
    st3 = psc_off_ticks_status(sess.runtime)
    assert st3["psc"] == "ON"
    assert st3["activated_tick"] == 3
    assert st3["transition_count"] == 1
    assert st3["withhold_opened"] is True
    sess.runtime.step()
    st4 = psc_off_ticks_status(sess.runtime)
    assert st4["psc"] == "ON"
    assert st4["activated_tick"] == 3
    assert st4["transition_count"] == 1


def test_disabled_schedule_never_activates():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=None, agent_count=1))
    assert sess.runtime.config.cognition.psc_off_ticks is None
    for _ in range(5):
        sess.runtime.step()
    st = psc_off_ticks_status(sess.runtime)
    assert st["schedule"] == "MANUAL"
    assert st["psc"] == "OFF"
    assert st["activated_tick"] is None


def test_reset_preserves_schedule():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    d = _draft(psc_off_ticks=1000)
    sess.apply_experiment(d)
    sess.apply_experiment(dict(d))  # same-draft reset
    assert sess.runtime.config.cognition.psc_off_ticks == 1000
    st = psc_off_ticks_status(sess.runtime)
    assert st["armed"] is True
    assert st["schedule"] == 1000


def test_snapshot_restore_no_replay():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=3, agent_count=1))
    while sess.runtime.tick < 3:
        sess.runtime.step()
    assert psc_off_ticks_status(sess.runtime)["activated_tick"] == 3
    # Snapshot/restore via runtime payload when available
    snap = sess.runtime.snapshot() if hasattr(sess.runtime, "snapshot") else None
    if snap is None:
        return
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    restored = PhysicalSystemRuntime.restore(snap) if hasattr(PhysicalSystemRuntime, "restore") else None
    if restored is None:
        return
    st = psc_off_ticks_status(restored)
    assert st["psc"] == "ON"
    assert st["activated_tick"] == 3
    restored.step()
    st2 = psc_off_ticks_status(restored)
    assert st2["transition_count"] == 1
    assert st2["activated_tick"] == 3


def test_twoagent_canonical_ticks_999_1000_1001_exactly_once():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=1000, agent_count=2))
    while sess.runtime.tick < 999:
        sess.runtime.step()
    st = psc_off_ticks_status(sess.runtime)
    assert sess.runtime.tick == 999
    assert st["psc"] == "OFF"
    assert st["armed"] is True
    assert st["schedule"] == 1000
    assert st["activated_tick"] is None
    sess.runtime.step()
    st = psc_off_ticks_status(sess.runtime)
    assert sess.runtime.tick == 1000
    assert st["psc"] == "ON"
    assert st["activated_tick"] == 1000
    assert st["transition_count"] == 1
    assert st["withhold_opened"] is True
    assert st["armed"] is False
    sess.runtime.step()
    st = psc_off_ticks_status(sess.runtime)
    assert sess.runtime.tick == 1001
    assert st["psc"] == "ON"
    assert st["transition_count"] == 1
    assert st["activated_tick"] == 1000


def test_schedule_0_enables_at_tick_0_or_first_eligible():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=0, agent_count=2))
    st0 = psc_off_ticks_status(sess.runtime)
    if sess.runtime.tick >= 0 and st0["psc"] != "ON":
        sess.runtime.step()
        st0 = psc_off_ticks_status(sess.runtime)
    assert st0["psc"] == "ON"
    assert st0["transition_count"] == 1
    assert st0["schedule"] == 0


def test_schedule_5000_remains_armed_before_boundary():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=5000, agent_count=2))
    for _ in range(12):
        sess.runtime.step()
    st = psc_off_ticks_status(sess.runtime)
    assert st["psc"] == "OFF"
    assert st["armed"] is True
    assert st["schedule"] == 5000
    assert st["activated_tick"] is None


def test_restore_at_999_transitions_once_restore_at_1000_does_not_replay():
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=1000, agent_count=2))
    while sess.runtime.tick < 999:
        sess.runtime.step()
    snap999 = sess.runtime.snapshot()
    r999 = TwoAgentRuntime.restore(snap999)
    assert psc_off_ticks_status(r999)["psc"] == "OFF"
    r999.step()
    st = psc_off_ticks_status(r999)
    assert st["psc"] == "ON"
    assert st["transition_count"] == 1
    assert st["activated_tick"] == 1000
    snap1000 = r999.snapshot()
    r1000 = TwoAgentRuntime.restore(snap1000)
    assert psc_off_ticks_status(r1000)["psc"] == "ON"
    r1000.step()
    st2 = psc_off_ticks_status(r1000)
    assert st2["psc"] == "ON"
    assert st2["transition_count"] == 1
    assert st2["activated_tick"] == 1000


def test_frozen_apply_receipt_is_initial_not_current_runtime():
    from mechanistic_mind.ui.psy_observer_web.serialize import live_frame
    from mechanistic_mind.ui.psy_observer_web.subscriptions import ObserverInterest

    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=3, agent_count=2))
    while sess.runtime.tick < 3:
        sess.runtime.step()
    setattr(sess.runtime, "_observer_runtime_generation", 1)
    frame = live_frame(
        sess.runtime,
        status=sess.status,
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail="compact",
        observer_interest=ObserverInterest(),
    )
    live = frame["experiment"]["runtime"]["psc_schedule"]
    assert live["psc"] == "ON"
    receipt = sess.applied_configuration_receipt()
    requested = (receipt.get("requested") or {})
    mechs = requested.get("mechanisms") or {}
    initial = mechs.get("prospective_scenario_competition")
    assert initial in (False, 0, None) or initial is False or str(initial).lower() in ("false", "off")
    assert live["psc"] == "ON"
    assert live["transition_count"] == 1

