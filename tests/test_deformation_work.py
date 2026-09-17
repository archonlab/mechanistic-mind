import copy

import numpy as np

from mechanistic_mind.physical_system.body_deformation import BodyDeformationConfig, step_deformation
from mechanistic_mind.physical_system.deformation_work import DeformationWorkConfig, deformation_potential
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime


def _body():
    rt = PhysicalSystemRuntime(seed=17)
    ensure_B_site(rt.body, len(rt.config.body.footprint))
    return rt


def test_work_unlimited_matches_kinematic_when_no_env_load():
    a, b = _body(), _body()
    a.body.B_site[:] = b.body.B_site[:] = 0.2
    a.body.B_site[3] = b.body.B_site[3] = 1.8
    kin = step_deformation(a.body, a.config.body.footprint, BodyDeformationConfig())
    work_cfg = DeformationWorkConfig(reservoir_init=10.0, reservoir_max=10.0)
    b.body.mechanical_work_reservoir = 10.0
    met = step_deformation(b.body, b.config.body.footprint, BodyDeformationConfig(), work_cfg)
    assert np.allclose(a.body.deformation, b.body.deformation, atol=1e-9)
    assert met["mechanical_energy_accounting"] == "ACTIVE"
    assert abs(met["unexplained_residual"]) < 1e-9
    assert abs(met["deformation_residual"] - met["known_quadrature"]) < 1e-9
    assert kin["mechanical_energy_accounting"] == "NOT DEMONSTRATED"


def test_static_hold_does_not_drain_reservoir():
    rt = _body()
    rt.body.B_site[:] = 0.8
    cfg = BodyDeformationConfig()
    wcfg = DeformationWorkConfig(reservoir_init=2.0)
    rt.body.mechanical_work_reservoir = 2.0
    for _ in range(120):
        step_deformation(rt.body, rt.config.body.footprint, cfg, wcfg)
    d0 = rt.body.deformation.copy()
    w0 = rt.body.mechanical_work_reservoir
    for _ in range(15):
        meta = step_deformation(rt.body, rt.config.body.footprint, cfg, wcfg)
    assert np.max(np.abs(rt.body.deformation - d0)) < 1e-6
    assert abs(rt.body.mechanical_work_reservoir - w0) < 1e-6
    assert abs(meta["actuator_work"]) < 1e-8


def test_depletion_limits_internal_drive_but_env_can_deform():
    rt = _body()
    rt.body.B_site[:] = 0.35
    rt.body.B_site[1] = 1.9
    cfg = BodyDeformationConfig()
    empty = DeformationWorkConfig(reservoir_init=0.0, reservoir_max=0.0)
    rt.body.mechanical_work_reservoir = 0.0
    step_deformation(rt.body, rt.config.body.footprint, cfg, empty)
    assert np.linalg.norm(rt.body.deformation) < 1e-8

    loaded = _body()
    loaded.body.B_site[:] = 0.35
    loaded.body.mechanical_work_reservoir = 0.0
    loaded.body.deformation_env_force = np.zeros((5, 2))
    loaded.body.deformation_env_force[3] = [-0.8, 0.0]
    meta = step_deformation(
        loaded.body, loaded.config.body.footprint, BodyDeformationConfig(material_drive_enabled=False), empty
    )
    assert np.linalg.norm(loaded.body.deformation) > 1e-6
    assert meta["shape_change_source"] in {"ENVIRONMENTALLY_FORCED", "MIXED", "PASSIVE_RELAXATION"}
    assert float(meta["reservoir_work_supplied"]) == 0.0


def test_transfer_ablation_ignores_reservoir():
    low, high = _body(), _body()
    for rt, w in ((low, 0.0), (high, 4.0)):
        rt.body.B_site[:] = 1.8
        rt.body.mechanical_work_reservoir = w
        cfg = DeformationWorkConfig(transfer_enabled=False, reservoir_init=w)
        step_deformation(rt.body, rt.config.body.footprint, BodyDeformationConfig(), cfg)
    assert np.allclose(low.body.deformation, high.body.deformation)
    assert low.body.mechanical_work_reservoir == 0.0
    assert high.body.mechanical_work_reservoir == 4.0


def test_greater_env_resistance_costs_more_work_or_less_deformation():
    free, resist = _body(), _body()
    wcfg = DeformationWorkConfig(reservoir_init=4.0, reservoir_max=4.0)
    for rt in (free, resist):
        rt.body.B_site[:] = 0.2
        rt.body.B_site[3] = 1.8
        rt.body.mechanical_work_reservoir = 4.0
    resist.body.deformation_env_force = np.zeros((5, 2))
    resist.body.deformation_env_force[3] = [2.0, 0.0]
    mf = step_deformation(free.body, free.config.body.footprint, BodyDeformationConfig(), wcfg)
    # same wcfg object would share nothing but reservoir is on body
    wcfg2 = DeformationWorkConfig(reservoir_init=4.0, reservoir_max=4.0)
    mr = step_deformation(resist.body, resist.config.body.footprint, BodyDeformationConfig(), wcfg2)
    more_work = abs(mr["actuator_work"]) > abs(mf["actuator_work"]) + 1e-12
    less_def = np.linalg.norm(resist.body.deformation) + 1e-12 < np.linalg.norm(free.body.deformation)
    assert more_work or less_def


def test_historical_deformation_work_missing_is_off():
    rt = _body()
    snap = rt.snapshot()
    historical = copy.deepcopy(snap)
    historical["config"].pop("deformation_work")
    old = PhysicalSystemRuntime.restore(historical)
    assert old.config.deformation_work.enabled is False


def test_integrated_defaults_include_work_transfer():
    cfg = PhysicalSystemConfig()
    assert cfg.deformation_work.enabled
    assert cfg.body_deformation.enabled
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.config.cognition.cognition_enabled = False
    rt.config.endogenous_motor.mode = "OFF"
    assert rt.body.mechanical_work_reservoir == cfg.deformation_work.reservoir_init
    for _ in range(5):
        rt.step()
    assert rt.last_work_ledger is not None
    assert rt.last_deformation_meta["mechanical_energy_accounting"] in {"ACTIVE", "BYPASSED"}
