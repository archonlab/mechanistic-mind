import numpy as np
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime, PhysicalSystemConfig
from mechanistic_mind.physical_system.morphology_mechanics import MorphologyMechanicsConfig
from mechanistic_mind.physical_system.body_orientation import BodyOrientationConfig
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.deformation_work import DeformationWorkConfig
from mechanistic_mind.physical_system.environmental_resource import EnvironmentalResourceConfig
from mechanistic_mind.physical_system.complementary_resources import ComplementaryResourcesConfig
from mechanistic_mind.physical_system.motor_work import EndogenousMotorWorkConfig
from mechanistic_mind.physical_system.action_work import DiscreteActionWorkConfig
from mechanistic_mind.physical_system.mechanism_registry import RUNTIME_VERSION


def test_integrated_defaults_on():
    cfg = PhysicalSystemConfig()
    assert cfg.runtime_version == RUNTIME_VERSION
    assert cfg.morphology_mechanics.enabled
    assert cfg.body_orientation.enabled
    assert cfg.endogenous_motor.enabled
    assert cfg.body_deformation.enabled
    assert cfg.deformation_work.enabled
    assert cfg.environmental_resource.enabled
    assert cfg.environmental_resource.transfer_enabled
    assert cfg.environmental_resource.conversion_enabled
    assert cfg.complementary_resources.enabled
    assert cfg.complementary_resources.transfer_A_enabled
    assert cfg.complementary_resources.transfer_B_enabled
    assert cfg.complementary_resources.conversion_enabled
    assert cfg.endogenous_motor_work.enabled
    assert cfg.discrete_action_work.enabled


def test_historical_from_dict_off():
    assert MorphologyMechanicsConfig.from_dict(None).mode == "OFF"
    assert BodyOrientationConfig.from_dict({}).mode == "OFF"
    assert EndogenousMotorCouplingConfig.from_dict(None).mode == "OFF"
    assert DeformationWorkConfig.from_dict(None).mode == "OFF"
    assert EnvironmentalResourceConfig.from_dict(None).mode == "OFF"
    assert ComplementaryResourcesConfig.from_dict(None).mode == "OFF"
    assert EndogenousMotorWorkConfig.from_dict(None).mode == "OFF"
    assert DiscreteActionWorkConfig.from_dict(None).mode == "OFF"


def test_force_ledger_composes_endo_with_site_path():
    cfg = PhysicalSystemConfig()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    for _ in range(10):
        rt.step()
    fc = rt.last_force_contributions
    assert fc is not None
    assert "environmental_site" in fc and "endogenous_motor" in fc
    assert "discrete_action" in fc


def test_endo_ablation_independent():
    cfg = PhysicalSystemConfig()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    for _ in range(5):
        rt.step()
    rt.set_mechanism("endogenous_motor_coupling", False)
    rt.step()
    em = (rt.last_force_contributions or {}).get("endogenous_motor") or [0, 0]
    assert abs(em[0]) + abs(em[1]) < 1e-15


def test_zeroflow_composed_endo_moves_ablation_stops():
    cfg = PhysicalSystemConfig()
    cfg.planet.flow_enabled = False
    cfg.planet.flow_gain = 0.0
    cfg.body.flow_coupling = 0.0
    cfg.body.wave_coupling = 0.0
    rt = PhysicalSystemRuntime(seed=23, config=cfg)
    path = 0.0
    px, py = rt.body.x, rt.body.y
    for _ in range(50):
        rt.step()
        path += float(np.hypot(rt.body.x - px, rt.body.y - py))
        px, py = rt.body.x, rt.body.y
    assert path > 1e-6
    cfg2 = PhysicalSystemConfig()
    cfg2.endogenous_motor.mode = "OFF"
    cfg2.planet.flow_enabled = False
    cfg2.planet.flow_gain = 0.0
    cfg2.body.flow_coupling = 0.0
    cfg2.body.wave_coupling = 0.0
    rt2 = PhysicalSystemRuntime(seed=23, config=cfg2)
    path2 = 0.0
    px, py = rt2.body.x, rt2.body.y
    for _ in range(50):
        rt2.step()
        path2 += float(np.hypot(rt2.body.x - px, rt2.body.y - py))
        px, py = rt2.body.x, rt2.body.y
    assert path2 < 1e-9


def test_structured_events_emit():
    rt = PhysicalSystemRuntime(seed=17, config=PhysicalSystemConfig())
    for _ in range(8):
        rt.step()
    ev = rt.structured_events.list(50)
    assert isinstance(ev, list) and len(ev) > 0
