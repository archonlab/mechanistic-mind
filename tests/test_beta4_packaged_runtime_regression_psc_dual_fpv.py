"""Packaged runtime regressions: PSC UI cache, Dual FPV map, fingerprints."""
from __future__ import annotations

from pathlib import Path

from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BETA4,
    acanthostega_beta4_mechanism_map,
    canonical_fingerprint,
    preset_canonical,
)
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.subscriptions import ObserverInterest
from mechanistic_mind.ui.psy_observer_web.tiktaalik_eye import psc_off_ticks_status

FROZEN_B31 = "1621ef2c154864d1"
FROZEN_B4 = "3666b58d67932821"


def _draft(*, psc_off_ticks=3, agent_count=2):
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


def _frame(sess: ObserverSession, interest: ObserverInterest | None = None) -> dict:
    return live_frame(
        sess.runtime,
        status=sess.status,
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail="compact",
        observer_interest=interest,
    )


def test_public_fingerprints_unchanged():
    from mechanistic_mind.physical_system.experiment_canonical import PRESET_BETA31

    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_B31
    assert canonical_fingerprint(preset_canonical(PRESET_ACANTHOSTEGA_BETA4, seed=17)) == FROZEN_B4


def test_psc_off_at_threshold_minus_one_on_at_and_beyond_without_sampling_exactly():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=3, agent_count=2))
    while sess.runtime.tick < 2:
        sess.runtime.step()
    assert psc_off_ticks_status(sess.runtime)["psc"] == "OFF"
    sess.runtime.step()  # 3
    sess.runtime.step()  # 4 sampled after crossing
    st = psc_off_ticks_status(sess.runtime)
    assert st["psc"] == "ON"
    assert st["transition_count"] == 1
    assert st["activated_tick"] == 3


def test_live_frame_psc_readback_not_stuck_on_cached_experiment_fragment():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=3, agent_count=2))
    setattr(sess.runtime, "_observer_runtime_generation", 1)
    f0 = _frame(sess)
    assert f0["experiment"]["runtime"]["psc_schedule"]["psc"] == "OFF"
    assert f0["experiment"]["runtime"]["psc_schedule"]["schedule"] == 3
    while sess.runtime.tick < 3:
        sess.runtime.step()
    f1 = _frame(sess)
    sched = f1["experiment"]["runtime"]["psc_schedule"]
    assert sched["psc"] == "ON"
    assert sched["activated_tick"] == 3
    assert sched["transition_count"] == 1
    f2 = _frame(sess)
    assert f2["experiment"]["runtime"]["psc_schedule"]["transition_count"] == 1


def test_dual_fpv_map_without_interest_two_agent():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=None, agent_count=2))
    for _ in range(3):
        sess.runtime.step()
    empty = ObserverInterest()
    empty.products.discard("eye_dock_dual_fpv")
    frame = _frame(sess, interest=empty)
    fpv = (frame.get("world") or {}).get("organism_receptor_grounded_3d_fpv") or {}
    by = fpv.get("latest_exact_by_agent") or {}
    assert fpv.get("latest_exact_by_agent_included") is True
    # Traces may be empty this early if O4 has not produced yet; keys must not
    # be selected-agent-only when both exist.
    if by:
        ids = {str((tr or {}).get("trace_id")) for tr in by.values() if tr}
        agents = set(by)
        assert "agent_0" in agents or "agent_1" in agents
        if "agent_0" in by and "agent_1" in by:
            assert str(by["agent_0"].get("agent_id")) == "agent_0"
            assert str(by["agent_1"].get("agent_id")) == "agent_1"
            if by["agent_0"].get("trace_id") and by["agent_1"].get("trace_id"):
                assert by["agent_0"]["trace_id"] != by["agent_1"]["trace_id"]
                assert len(ids) >= 2


def test_dual_fpv_map_with_interest_still_works():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=None, agent_count=2))
    for _ in range(3):
        sess.runtime.step()
    interest = ObserverInterest()
    interest.add("eye_dock_dual_fpv")
    frame = _frame(sess, interest=interest)
    fpv = (frame.get("world") or {}).get("organism_receptor_grounded_3d_fpv") or {}
    assert fpv.get("latest_exact_by_agent_included") is True


def test_manual_schedule_does_not_auto_enable():
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    sess.apply_experiment(_draft(psc_off_ticks=None, agent_count=2))
    for _ in range(5):
        sess.runtime.step()
    st = psc_off_ticks_status(sess.runtime)
    assert st["schedule"] == "MANUAL"
    assert st["psc"] == "OFF"


def test_package_scheduler_module_is_current_source():
    src = Path("mechanistic_mind/physical_system/runtime.py").read_text(encoding="utf-8")
    assert "if int(self.tick) < threshold" in src
    assert "_psc_auto_activated" in src
    two = Path("mechanistic_mind/physical_system/two_agent.py").read_text(encoding="utf-8")
    assert "rt._maybe_auto_enable_psc()" in two


def test_apply_makes_schedule_visible_and_local_draft_cannot_disarm_runtime():
    """Future-run: one Apply; schedule is on the live frame; mutating a local draft dict is inert."""
    sess = ObserverSession(SessionConfig(seed=17, buffer_capacity=8, ui_hz=10.0))
    applied = _draft(psc_off_ticks=3, agent_count=2)
    sess.apply_experiment(applied)
    setattr(sess.runtime, "_observer_runtime_generation", 1)
    f0 = _frame(sess)
    sched0 = f0["experiment"]["runtime"]["psc_schedule"]
    assert sched0["schedule"] == 3
    assert sched0["psc"] == "OFF"
    assert sched0["armed"] is True
    local_draft = dict(applied)
    local_draft["psc_off_ticks"] = None
    local_draft["mechanisms"] = dict(applied["mechanisms"])
    # Not sent to Apply — must not change the live runtime.
    assert sess.runtime.config.cognition.psc_off_ticks == 3
    while sess.runtime.tick < 3:
        sess.runtime.step()
    f1 = _frame(sess)
    assert f1["experiment"]["runtime"]["psc_schedule"]["psc"] == "ON"
    assert f1["experiment"]["runtime"]["psc_schedule"]["transition_count"] == 1
    sess.runtime.step()
    f2 = _frame(sess)
    assert f2["experiment"]["runtime"]["psc_schedule"]["psc"] == "ON"
    assert f2["experiment"]["runtime"]["psc_schedule"]["transition_count"] == 1
    assert psc_off_ticks_status(sess.runtime)["psc"] == "ON"
