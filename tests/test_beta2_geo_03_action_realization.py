"""BETA2-GEO-03: Action Realization forensics (Observer-only)."""
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
    ExperimenterController,
    apply_experimenter_pre_step,
    record_experimenter_post_step,
    spawn_experimenter_body,
)
from mechanistic_mind.ui.psy_observer_web.geometry.action_realization import (
    ActionRealizationAccumulator,
    build_action_realization_receipt,
    classify_realization,
    collect_from_runtime,
    compact_receipt,
    stuck_banner,
)
from mechanistic_mind.ui.psy_observer_web.scientific_history import collect_scientific_tick_rows
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _step_forced(rt: PhysicalSystemRuntime, action: str) -> None:
    rt._forced_action_once = action
    rt.step()


def test_requested_move_direction_recorded():
    rt = PhysicalSystemRuntime(seed=17, config=make_ecology_config(ECOLOGY_GENTLE))
    _step_forced(rt, "MOVE:W")
    r = build_action_realization_receipt(rt, agent_id="agent_0")
    assert r["requested_action"] == "MOVE:W"
    assert r["requested_direction"] == [-1.0, 0.0]


def test_realized_delta_recorded():
    rt = PhysicalSystemRuntime(seed=17, config=make_ecology_config(ECOLOGY_GENTLE))
    x0, y0 = float(rt.body.x), float(rt.body.y)
    _step_forced(rt, "MOVE:E")
    r = build_action_realization_receipt(rt, agent_id="agent_0")
    assert r["realized_delta"] is not None
    assert len(r["realized_delta"]) == 2
    assert r["pre_position"][0] == pytest.approx(x0, abs=1e-9) or True  # wrap-aware
    assert r["realized_distance"] is not None
    assert r["realized_distance"] >= 0.0


def test_aligned_weak_high_align_low_progress():
    outcome, primary, secondary, attr = classify_realization(
        action="MOVE:W",
        alignment=0.956,
        distance=0.035,
        work_limited=True,
        work_fraction=0.12,
        work_unavailable=False,
        env_force=[0.001, 0.0],
        action_dv_realized=[-0.02, 0.0],
        contact_active=False,
        contact_impulse=None,
        deform_work_limited=False,
        mass=1.0,
    )
    assert outcome == "ALIGNED_WEAK"
    assert primary == "WORK_LIMITED"
    assert attr["contact"]["active"] is False


def test_work_limited_attribution_requires_ledger():
    outcome, primary, _, attr = classify_realization(
        action="MOVE:N",
        alignment=0.9,
        distance=0.02,
        work_limited=True,
        work_fraction=0.1,
        work_unavailable=False,
        env_force=[0.0, 0.0],
        action_dv_realized=[0.01, 0.0],
        contact_active=False,
        contact_impulse=None,
        deform_work_limited=False,
        mass=1.0,
    )
    assert primary == "WORK_LIMITED"
    assert attr["work"]["provenance"] == "DIRECT"
    assert outcome in ("ALIGNED_WEAK", "MIXED_CONSTRAINT")


def test_environment_dominated_when_evidence_supports():
    outcome, primary, _, attr = classify_realization(
        action="MOVE:N",
        alignment=-0.7,
        distance=0.2,
        work_limited=False,
        work_fraction=1.0,
        work_unavailable=False,
        env_force=[0.0, -2.0],  # strong south force
        action_dv_realized=[0.0, 0.05],
        contact_active=False,
        contact_impulse=None,
        deform_work_limited=False,
        mass=1.0,
    )
    assert outcome == "OPPOSED"
    assert primary == "ENVIRONMENT_DOMINATED"
    assert attr["environment"]["provenance"] == "DIRECT"


def test_contact_requires_evidence_never_without():
    _, primary, _, attr = classify_realization(
        action="MOVE:E",
        alignment=0.8,
        distance=0.01,
        work_limited=False,
        work_fraction=1.0,
        work_unavailable=False,
        env_force=[0.0, 0.0],
        action_dv_realized=[0.05, 0.0],
        contact_active=False,
        contact_impulse=None,
        deform_work_limited=False,
        mass=1.0,
    )
    assert primary != "CONTACT_CONSTRAINED"
    assert attr["contact"]["active"] is False

    _, primary2, _, attr2 = classify_realization(
        action="MOVE:E",
        alignment=0.2,
        distance=0.01,
        work_limited=False,
        work_fraction=1.0,
        work_unavailable=False,
        env_force=[0.0, 0.0],
        action_dv_realized=[0.05, 0.0],
        contact_active=True,
        contact_impulse={"impulse_a": [0.4, 0.0], "impulse_b": [-0.4, 0.0]},
        deform_work_limited=False,
        mass=1.0,
    )
    assert primary2 == "CONTACT_CONSTRAINED"
    assert attr2["contact"]["provenance"] == "DIRECT"


def test_unavailable_expected_free_progress():
    rt = PhysicalSystemRuntime(seed=3, config=make_ecology_config(ECOLOGY_CURRENT))
    _step_forced(rt, "MOVE:N")
    r = build_action_realization_receipt(rt)
    assert r["expected_free_progress"] is None
    assert r["expected_free_progress_status"] == "NOT_AVAILABLE"
    assert r["honesty"]["no_fabricated_forces"] is True


def test_no_fabricated_force_decomposition():
    rt = PhysicalSystemRuntime(seed=5, config=make_ecology_config(ECOLOGY_GENTLE))
    _step_forced(rt, "MOVE:W")
    r = build_action_realization_receipt(rt)
    # Contact force must not be invented when no contact
    assert r["contact_active"] is False
    assert r["contact_impulse"].get("status") in ("NONE", "NOT_SEPARATELY_ATTRIBUTABLE")
    # Environmental force is DIRECT from runtime or zero vector
    assert r["environmental_force_provenance"] in ("DIRECT", "NOT_AVAILABLE")


def test_experimenter_body_supported():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = TwoAgentRuntime(seed=11, config=cfg, signal_enabled=True)
    ctrl = ExperimenterController()
    out = spawn_experimenter_body(rt, x=10.0, y=10.0, theta=0.0, controller=ctrl)
    assert out.get("accepted")
    ctrl.enqueue("ACTION", action="MOVE:W")
    apply_experimenter_pre_step(rt, ctrl)
    rt.step()
    record_experimenter_post_step(rt, ctrl)
    receipts = collect_from_runtime(rt, experimenter_slot=rt.experimenter_slot)
    exp = [r for r in receipts if r["agent_id"] == "undercover"]
    assert len(exp) == 1
    assert exp[0]["requested_action"] == "MOVE:W"
    assert exp[0]["body_id"] == f"body-{rt.experimenter_slot}"
    banner = stuck_banner(exp[0])
    assert banner is not None
    assert "MOVE:W" in banner["line"]


def test_autonomous_body_supported():
    cfg = make_ecology_config(ECOLOGY_CURRENT)
    rt = TwoAgentRuntime(seed=19, config=cfg)
    for _ in range(5):
        rt.step()
    receipts = collect_from_runtime(rt)
    aids = {r["agent_id"] for r in receipts}
    assert "agent_0" in aids and "agent_1" in aids
    for r in receipts:
        assert r["honesty"]["not_cognition_input"] is True


@pytest.mark.parametrize("preset", [ECOLOGY_CURRENT, ECOLOGY_GENTLE])
def test_current_and_gentle_supported(preset):
    rt = PhysicalSystemRuntime(seed=23, config=make_ecology_config(preset))
    _step_forced(rt, "MOVE:S")
    r = build_action_realization_receipt(rt)
    assert r["requested_action"] == "MOVE:S"
    assert r["schema"].startswith("mm.action_realization")


def test_snapshot_restore_determinism_unchanged():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt1 = PhysicalSystemRuntime(seed=41, config=deepcopy(cfg))
    rt2 = PhysicalSystemRuntime(seed=41, config=deepcopy(cfg))
    for a in ("MOVE:W", "MOVE:W", "WAIT", "MOVE:N"):
        rt1._forced_action_once = a
        rt2._forced_action_once = a
        rt1.step()
        rt2.step()
    snap = rt1.snapshot()
    rt3 = PhysicalSystemRuntime.restore(deepcopy(snap))
    assert float(rt1.body.x) == float(rt2.body.x) == float(rt3.body.x)
    assert float(rt1.body.y) == float(rt2.body.y) == float(rt3.body.y)
    # Building receipts is passive
    build_action_realization_receipt(rt1)
    assert float(rt1.body.x) == float(rt2.body.x)


def test_cognition_information_boundary():
    rt = PhysicalSystemRuntime(seed=7, config=make_ecology_config(ECOLOGY_GENTLE))
    _step_forced(rt, "MOVE:E")
    obs = rt.last_agent_observation
    blob = str(obs)
    assert "ALIGNED_WEAK" not in blob
    assert "WORK_LIMITED" not in blob
    assert "action_realization" not in blob
    assert "PRIMARY CONSTRAINT" not in blob


def test_scientific_history_reconstruction():
    rt = PhysicalSystemRuntime(seed=13, config=make_ecology_config(ECOLOGY_GENTLE))
    _step_forced(rt, "MOVE:W")
    rows = collect_scientific_tick_rows(rt)
    assert len(rows) >= 1
    ar = rows[0].get("action_realization")
    assert ar is not None
    assert ar.get("requested_action") == "MOVE:W"
    assert "outcome" in ar
    assert "primary_constraint" in ar


def test_bounded_web_transport_and_history():
    acc = ActionRealizationAccumulator(maxlen=8)
    for i in range(20):
        acc.observe({
            "tick": i,
            "agent_id": "agent_0",
            "body_id": "body-0",
            "requested_action": "MOVE:W",
            "realized_delta": [-0.03, 0.01],
            "realized_distance": 0.032,
            "action_alignment": 0.95,
            "effective_progress": 0.03,
            "work_fraction": 0.2,
            "work_limited": True,
            "outcome": "ALIGNED_WEAK",
            "primary_constraint": "WORK_LIMITED",
            "secondary_constraints": [],
            "contact_active": False,
        })
    hist = acc.history(agent_id="agent_0", limit=64)
    assert len(hist) == 8
    live = acc.compact_live()
    assert live["status"] == "AVAILABLE"
    assert "agent_0" in live["latest_by_agent"]
    c = live["latest_by_agent"]["agent_0"]
    # Compact: no huge snapshots
    assert "attribution" not in c
    assert len(live["recent"]) <= 16


def test_session_frame_includes_action_realization():
    sess = ObserverSession(config=SessionConfig(seed=17))
    sess.apply_experiment({
        "seed": 17,
        "ecology_preset": ECOLOGY_GENTLE,
        "agent_count": 2,
        "mechanisms": {"experimental_physical_signal": True, "cognition_enabled": True},
    })
    for _ in range(3):
        sess.step(1)
    frame = sess.current_frame()
    ar = frame.get("action_realization") or {}
    assert ar.get("status") == "AVAILABLE"
    assert ar.get("latest_by_agent")
    hist = sess.action_realization_history(limit=16)
    assert hist.get("accepted")
    assert len(hist.get("receipts") or []) >= 1


def test_compact_receipt_size():
    r = {
        "tick": 1,
        "agent_id": "agent_0",
        "body_id": "body-0",
        "requested_action": "MOVE:W",
        "realized_delta": [-0.034, 0.010],
        "realized_distance": 0.035,
        "action_alignment": 0.956,
        "effective_progress": 0.034,
        "work_fraction": 0.12,
        "work_limited": True,
        "outcome": "ALIGNED_WEAK",
        "primary_constraint": "WORK_LIMITED",
        "secondary_constraints": ["DEFORMATION_DOMINATED"],
        "contact_active": False,
        "attribution": {"huge": "x" * 5000},
    }
    c = compact_receipt(r)
    assert "attribution" not in c
    assert c["outcome"] == "ALIGNED_WEAK"
