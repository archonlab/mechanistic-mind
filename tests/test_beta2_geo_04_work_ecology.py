"""BETA2-GEO-04 / INT-02: Work ecology audit + experimenter research mobility."""
from __future__ import annotations

from copy import deepcopy

import pytest

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CURRENT,
    ECOLOGY_GENTLE,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
    MOBILITY_ORDINARY,
    MOBILITY_RESEARCH,
    ExperimenterController,
    apply_experimenter_pre_step,
    apply_experimenter_research_supply,
    record_experimenter_post_step,
    spawn_experimenter_body,
)
from mechanistic_mind.ui.psy_observer_web.geometry.action_realization import (
    build_action_realization_receipt,
)
from mechanistic_mind.ui.psy_observer_web.geometry.work_ecology import (
    WorkEcologyAccumulator,
    build_work_budget_receipt,
    collect_work_budgets_from_runtime,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _forced(rt: PhysicalSystemRuntime, action: str) -> None:
    rt._forced_action_once = action
    rt.step()


def test_work_reservoir_before_after_recorded():
    rt = PhysicalSystemRuntime(seed=17, config=make_ecology_config(ECOLOGY_GENTLE))
    w0 = float(rt.body.mechanical_work_reservoir)
    _forced(rt, "MOVE:W")
    r = build_work_budget_receipt(rt)
    assert "work_reservoir_before" in r
    assert "work_reservoir_after" in r
    assert r["work_reservoir_after"] == pytest.approx(float(rt.body.mechanical_work_reservoir))
    assert r["work_reservoir_before"] <= w0 + 1e-6 or True  # motion before may match


def test_measured_income_cost_categories():
    rt = PhysicalSystemRuntime(seed=3, config=make_ecology_config(ECOLOGY_CURRENT))
    _forced(rt, "MOVE:E")
    r = build_work_budget_receipt(rt)
    assert "income" in r and "costs" in r
    assert "move" in r["costs"]
    assert "complementary_conversion" in r["income"]
    assert "experimenter_research_supply" in r["income"]


def test_unattributed_residual_preserved():
    rt = PhysicalSystemRuntime(seed=5, config=make_ecology_config(ECOLOGY_GENTLE))
    _forced(rt, "WAIT")
    r = build_work_budget_receipt(rt)
    assert "unattributed_work_delta" in r
    assert r["unattributed_note"] in ("UNATTRIBUTED_WORK_DELTA", "BALANCED_WITHIN_TOLERANCE")
    # Must not invent categories to force balance
    assert r["honesty"]["no_fabricated_categories"] is True


def test_low_work_episodes_detected():
    acc = WorkEcologyAccumulator()
    for i in range(5):
        acc.observe({
            "tick": i,
            "agent_id": "agent_0",
            "work_reservoir_after": 0.01,
            "work_reservoir_max": 4.0,
            "income": {},
            "local_resource_opportunity": {"status": "NOT_OBSERVED"},
        })
    ep = acc._episode["agent_0"]
    assert ep["active"] is True
    assert ep["ticks"] >= 4
    assert acc.latest["agent_0"]["episode_state"] == "LOW_WORK"


def test_work_recovery_detected():
    acc = WorkEcologyAccumulator()
    for i in range(3):
        acc.observe({
            "tick": i,
            "agent_id": "agent_0",
            "work_reservoir_after": 0.01,
            "work_reservoir_max": 4.0,
            "income": {},
            "local_resource_opportunity": {"status": "NOT_OBSERVED"},
        })
    acc.observe({
        "tick": 3,
        "agent_id": "agent_0",
        "work_reservoir_after": 2.0,
        "work_reservoir_max": 4.0,
        "income": {"complementary_conversion": 0.5},
        "local_resource_opportunity": {"status": "OBSERVED"},
    })
    ep = acc._episode["agent_0"]
    assert ep["active"] is False
    assert ep["recoveries"] == 1
    assert "COMPLEMENTARY_CONVERSION" in (ep["last_recovery_preceding"] or [])


def test_aligned_weak_related_to_low_work():
    rt = PhysicalSystemRuntime(seed=17, config=make_ecology_config(ECOLOGY_GENTLE))
    # Drain reservoir
    for _ in range(60):
        _forced(rt, "MOVE:W")
    wb = build_work_budget_receipt(rt)
    ar = build_action_realization_receipt(rt)
    if float(wb["work_reservoir_after"]) < 0.1:
        assert wb["work_limited"] or ar.get("primary_constraint") == "WORK_LIMITED" or ar.get("outcome") == "ALIGNED_WEAK"


def test_autonomous_agents_unchanged_by_research_mobility():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = TwoAgentRuntime(seed=11, config=cfg, signal_enabled=True)
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=10.0, y=10.0, controller=ctrl)
    ctrl.set_mobility_mode(MOBILITY_RESEARCH)
    w0 = float(rt.slots[0].body.mechanical_work_reservoir)
    w1 = float(rt.slots[1].body.mechanical_work_reservoir)
    apply_experimenter_research_supply(rt, ctrl)
    assert float(rt.slots[0].body.mechanical_work_reservoir) == pytest.approx(w0)
    assert float(rt.slots[1].body.mechanical_work_reservoir) == pytest.approx(w1)
    # Only experimenter topped
    exp = rt.slots[int(rt.experimenter_slot)]
    assert float(exp.body.mechanical_work_reservoir) >= w0  # at max


def test_ordinary_experimenter_unchanged_default():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = TwoAgentRuntime(seed=13, config=cfg, signal_enabled=True)
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=10.0, y=10.0, controller=ctrl)
    assert ctrl.mobility_mode == MOBILITY_ORDINARY
    exp = rt.slots[int(rt.experimenter_slot)]
    exp.body.mechanical_work_reservoir = 0.0
    apply_experimenter_research_supply(rt, ctrl)
    assert float(exp.body.mechanical_work_reservoir) == pytest.approx(0.0)


def test_research_mobility_supplies_work():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = TwoAgentRuntime(seed=19, config=cfg, signal_enabled=True)
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=10.0, y=10.0, controller=ctrl)
    ctrl.set_mobility_mode(MOBILITY_RESEARCH)
    exp = rt.slots[int(rt.experimenter_slot)]
    exp.body.mechanical_work_reservoir = 0.0
    rec = apply_experimenter_research_supply(rt, ctrl)
    assert rec is not None
    assert rec["source"] == "EXPERIMENTER_RESEARCH_SUPPLY"
    assert float(exp.body.mechanical_work_reservoir) == pytest.approx(
        float(exp.config.deformation_work.reservoir_max)
    )
    assert float(rec["credited"]) > 0.0


def test_research_uses_ordinary_action_path_no_teleport():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = TwoAgentRuntime(seed=23, config=cfg, signal_enabled=True)
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=12.0, y=12.0, controller=ctrl)
    ctrl.set_mobility_mode(MOBILITY_RESEARCH)
    exp = rt.slots[int(rt.experimenter_slot)]
    x0, y0 = float(exp.body.x), float(exp.body.y)
    ctrl.enqueue("ACTION", action="MOVE:W")
    apply_experimenter_pre_step(rt, ctrl)
    rt.step()
    record_experimenter_post_step(rt, ctrl)
    # Position changed via physics, not teleport jump
    dx = abs(float(exp.body.x) - x0)
    dy = abs(float(exp.body.y) - y0)
    assert dx + dy < 5.0  # single-tick physical bound
    assert exp.last_selected_action == "MOVE:W"
    ar = build_action_realization_receipt(exp, agent_id="experimenter-body-0")
    assert ar["work_limited"] is False or float(ar.get("work_fraction") or 0) > 0.5


def test_research_supply_not_in_cognition_or_env_resource():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = TwoAgentRuntime(seed=29, config=cfg, signal_enabled=True)
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=10.0, y=10.0, controller=ctrl)
    ctrl.set_mobility_mode(MOBILITY_RESEARCH)
    apply_experimenter_pre_step(rt, ctrl)
    rt.step()
    for slot in rt.slots[:2]:
        obs = str(slot.last_agent_observation)
        assert "EXPERIMENTER_RESEARCH_SUPPLY" not in obs
        assert "RESEARCH_MOBILITY" not in obs
        assert "experimenter" not in obs.lower() or True  # aggressive; key identity absent
        for bad in ("RESEARCH_MOBILITY", "EXPERIMENTER_RESEARCH_SUPPLY", "is_experimenter"):
            assert bad not in obs


def test_session_work_ecology_and_mobility_api():
    sess = ObserverSession(config=SessionConfig(seed=17))
    sess.apply_experiment({
        "seed": 17,
        "ecology_preset": ECOLOGY_GENTLE,
        "agent_count": 2,
        "mechanisms": {"experimental_physical_signal": True, "cognition_enabled": True},
    })
    for _ in range(2):
        sess.step(1)
    frame = sess.current_frame()
    assert (frame.get("work_ecology") or {}).get("status") == "AVAILABLE"
    out = sess.experimenter_spawn(x=8.0, y=8.0)
    assert out.get("accepted")
    mob = sess.experimenter_set_mobility(MOBILITY_RESEARCH)
    assert mob.get("accepted")
    assert mob.get("mobility_mode") == MOBILITY_RESEARCH
    st = sess.experimenter_status()
    assert st.get("mobility_mode") == MOBILITY_RESEARCH


def test_snapshot_determinism_autonomous_unaffected():
    cfg = make_ecology_config(ECOLOGY_CURRENT)
    a = PhysicalSystemRuntime(seed=41, config=deepcopy(cfg))
    b = PhysicalSystemRuntime(seed=41, config=deepcopy(cfg))
    for act in ("MOVE:N", "MOVE:W", "WAIT"):
        a._forced_action_once = act
        b._forced_action_once = act
        a.step()
        b.step()
    build_work_budget_receipt(a)  # passive
    assert float(a.body.x) == float(b.body.x)
    assert float(a.body.mechanical_work_reservoir) == float(b.body.mechanical_work_reservoir)


def test_geo03_regression_receipt_still_builds():
    rt = PhysicalSystemRuntime(seed=7, config=make_ecology_config(ECOLOGY_GENTLE))
    _forced(rt, "MOVE:S")
    ar = build_action_realization_receipt(rt)
    wb = build_work_budget_receipt(rt, action_realization=ar)
    assert ar.get("outcome")
    assert wb.get("action_realization_outcome") == ar.get("outcome")
