"""BETA2-BODY-01: locomotor economy receipt + passive trickle isolation."""
from __future__ import annotations

from copy import deepcopy

import pytest

from mechanistic_mind.physical_system.ecology_presets import (
    BODY01_PASSIVE_RESERVOIR_TRICKLE,
    ECOLOGY_CURRENT,
    ECOLOGY_GENTLE,
    make_ecology_config,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
    MOBILITY_RESEARCH,
    ExperimenterController,
    apply_experimenter_research_supply,
    spawn_experimenter_body,
)
from mechanistic_mind.ui.psy_observer_web.geometry.locomotor_economy import (
    EPS_DISTANCE,
    build_locomotor_economy_receipt,
    motor_authority_class,
)


def _force(rt, action: str) -> None:
    rt._forced_action_once = action
    rt.step()


def test_locomotor_economy_receipt_fields():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    # Phase-A-like: disable trickle for pure spend measurement
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    _force(rt, "MOVE:W")
    r = build_locomotor_economy_receipt(rt, ecology_preset=ECOLOGY_GENTLE)
    assert r["schema"].startswith("mm.locomotor_economy")
    assert "move_work_spent" in r
    assert "work_components" in r
    assert "work_per_realized_distance" in r
    assert r["honesty"]["no_double_count"] is True


def test_no_double_counted_work_components():
    cfg = make_ecology_config(ECOLOGY_CURRENT)
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    rt = PhysicalSystemRuntime(seed=3, config=cfg)
    _force(rt, "MOVE:E")
    r = build_locomotor_economy_receipt(rt)
    comps = r["work_components"]
    assert abs(sum(comps.values()) - float(r["work_component_total"])) < 1e-12


def test_denominator_protection():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    rt = PhysicalSystemRuntime(seed=5, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    _force(rt, "MOVE:N")
    r = build_locomotor_economy_receipt(rt)
    if float(r["realized_distance"] or 0) < EPS_DISTANCE:
        assert r["work_per_realized_distance"]["status"] == "DENOMINATOR_TOO_SMALL"
        assert r["work_per_realized_distance"]["value"] is None


def test_motor_authority_curve_reproducible():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    points = []
    for frac in (1.0, 0.1, 0.0):
        rt = PhysicalSystemRuntime(seed=11, config=deepcopy(cfg))
        for _ in range(3):
            _force(rt, "WAIT")
        rt.body.vx = rt.body.vy = 0.0
        rt.body.mechanical_work_reservoir = frac * float(rt.config.deformation_work.reservoir_max)
        _force(rt, "MOVE:E")
        r = build_locomotor_economy_receipt(rt)
        points.append(r.get("work_fraction"))
    assert points[0] is not None and points[0] >= 0.85
    assert points[-1] is not None and points[-1] <= 1e-9
    assert motor_authority_class(0.0, True) == "COLLAPSED"


def test_passive_trickle_enables_recovery_income():
    # Trickle mechanism retained for controls; baseline stamps 0 — enable explicitly.
    cfg = make_ecology_config(ECOLOGY_GENTLE, trickle=0.002)
    assert float(cfg.deformation_work.passive_reservoir_trickle) == pytest.approx(0.002)
    rt = PhysicalSystemRuntime(seed=7, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    # Clear env stocks so income is trickle-only
    if rt.world.R_A is not None:
        rt.world.R_A[:] = 0.0
    if rt.world.R_B is not None:
        rt.world.R_B[:] = 0.0
    _force(rt, "WAIT")
    ledger = rt.last_passive_reservoir_trickle or {}
    assert ledger.get("enabled") is True
    assert float(ledger.get("credited") or 0) > 0.0
    assert float(rt.body.mechanical_work_reservoir) > 0.0


def test_promoted_baseline_trickle_is_zero():
    assert float(BODY01_PASSIVE_RESERVOIR_TRICKLE) == pytest.approx(0.0)
    from mechanistic_mind.physical_system.ecology_presets import ECOLOGY_BASELINE

    cfg = make_ecology_config(ECOLOGY_BASELINE)
    assert float(cfg.deformation_work.passive_reservoir_trickle) == pytest.approx(0.0)
    assert cfg.planet.climate_ecology.enabled is True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert float(rt.world.R_A.sum()) > 0.0
    assert float(rt.world.R_B.sum()) > 0.0


def test_historical_config_trickle_off():
    # Bare PhysicalSystemConfig (no ecology helper) stays at dataclass default 0
    # unless ecology stamp applied.
    cfg = PhysicalSystemConfig()
    assert float(cfg.deformation_work.passive_reservoir_trickle) == pytest.approx(0.0)


def test_research_mobility_isolated():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = TwoAgentRuntime(seed=19, config=cfg, signal_enabled=True)
    ctrl = ExperimenterController()
    spawn_experimenter_body(rt, x=10.0, y=10.0, controller=ctrl)
    ctrl.set_mobility_mode(MOBILITY_RESEARCH)
    w0 = float(rt.slots[0].body.mechanical_work_reservoir)
    apply_experimenter_research_supply(rt, ctrl)
    assert float(rt.slots[0].body.mechanical_work_reservoir) == pytest.approx(w0)


def test_cognition_boundary_no_locomotor_labels():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt = PhysicalSystemRuntime(seed=13, config=cfg)
    _force(rt, "MOVE:W")
    r = build_locomotor_economy_receipt(rt)
    obs = str(rt.last_agent_observation)
    for bad in ("LOCOMOTOR_ECONOMY", "MOTOR AUTHORITY", "COLLAPSED", "PASSIVE_BODY_TRICKLE"):
        assert bad not in obs
    assert r["honesty"]["not_cognition_input"] is True


def test_zero_weaker_than_full_with_trickle():
    cfg = make_ecology_config(ECOLOGY_GENTLE)
    rt0 = PhysicalSystemRuntime(seed=23, config=deepcopy(cfg))
    rt0.body.mechanical_work_reservoir = 0.0
    rt0.body.vx = rt0.body.vy = 0.0
    _force(rt0, "MOVE:E")
    r0 = build_locomotor_economy_receipt(rt0)
    rt1 = PhysicalSystemRuntime(seed=23, config=deepcopy(cfg))
    rt1.body.mechanical_work_reservoir = float(rt1.config.deformation_work.reservoir_max)
    rt1.body.vx = rt1.body.vy = 0.0
    _force(rt1, "MOVE:E")
    r1 = build_locomotor_economy_receipt(rt1)
    assert float(r0.get("work_fraction") or 0) < float(r1.get("work_fraction") or 1)
    assert float(r0.get("realized_distance") or 0) <= float(r1.get("realized_distance") or 0) + 1e-9
