import copy

import numpy as np

from mechanistic_mind.physical_system.environmental_resource import (
    ensure_world_R,
    place_source,
)
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime


def _rt(seed=17, **res):
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.complementary_resources.mode = "OFF"
    cfg.deformation_work.reservoir_init = 0.0
    for k, v in res.items():
        setattr(cfg.environmental_resource, k, v)
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    ensure_B_site(rt.body, len(cfg.body.footprint))
    ensure_world_R(rt.world)
    return rt


def _center(rt):
    h, w = rt.world.T.shape
    return rt.body.cell(w, h)


def test_contact_transfers_and_source_depletes():
    rt = _rt()
    iy, ix = _center(rt)
    place_source(rt.world, iy, ix, 1.0)
    env0 = float(rt.world.R.sum())
    rt.step()
    lg = rt.last_resource_ledger
    assert lg["acquired_by_body"] > 0
    assert lg["removed_from_env"] > 0
    assert abs(lg["transfer_residual"]) < 1e-12
    assert float(rt.world.R.sum()) < env0
    assert float(np.sum(rt.body.R_site)) > 0
    assert abs(lg["removed_from_env"] - (lg["acquired_by_body"] + lg["transfer_loss"] + lg["transfer_residual"])) < 1e-12


def test_no_contact_no_transfer():
    rt = _rt()
    iy, ix = _center(rt)
    place_source(rt.world, (iy + 10) % rt.world.T.shape[0], (ix + 10) % rt.world.T.shape[1], 1.0)
    env0 = float(rt.world.R.sum())
    rt.step()
    assert rt.last_resource_ledger["acquired_by_body"] == 0.0
    assert abs(float(rt.world.R.sum()) - env0) < 1e-12
    assert float(np.sum(rt.body.R_site)) == 0.0


def test_no_source_does_not_create_work():
    rt = _rt()
    w0 = rt.body.mechanical_work_reservoir
    rt.step()
    assert abs(rt.body.mechanical_work_reservoir - w0) < 1e-12
    assert rt.last_resource_ledger["work_credited"] == 0.0


def test_conversion_credits_reservoir_and_debits_R():
    rt = _rt(conversion_enabled=True, transfer_enabled=False)
    n = len(rt.config.body.footprint)
    rt.body.R_site = np.zeros(n)
    rt.body.R_site[0] = 0.5
    w0 = rt.body.mechanical_work_reservoir
    rt.step()
    assert float(rt.body.R_site[0]) < 0.5
    assert rt.body.mechanical_work_reservoir > w0
    lg = rt.last_resource_ledger
    eta = rt.config.environmental_resource.conversion_efficiency
    k = rt.config.environmental_resource.conversion_coeff
    assert abs(lg["conversion_residual"]) < 1e-12
    assert abs(lg["work_credited"] + lg["conversion_loss_work"] - k * lg["converted_R"]) < 1e-12
    assert abs(lg["work_credited"] - eta * k * lg["converted_R"]) < 1e-12


def test_conversion_ablation_keeps_R_no_work():
    rt = _rt(conversion_enabled=False)
    n = len(rt.config.body.footprint)
    rt.body.R_site = np.full(n, 0.4)
    w0 = rt.body.mechanical_work_reservoir
    r0 = float(rt.body.R_site.sum())
    rt.step()
    assert abs(rt.body.mechanical_work_reservoir - w0) < 1e-12
    assert abs(float(rt.body.R_site.sum()) - r0) < 1e-12


def test_transfer_ablation_no_acquisition():
    rt = _rt(transfer_enabled=False)
    iy, ix = _center(rt)
    place_source(rt.world, iy, ix, 2.0)
    env0 = float(rt.world.R.sum())
    rt.step()
    assert rt.last_resource_ledger["acquired_by_body"] == 0.0
    assert abs(float(rt.world.R.sum()) - env0) < 1e-12


def test_capacity_stops_and_leaves_source():
    rt = _rt(site_capacity=0.15, transfer_rate=0.5)
    iy, ix = _center(rt)
    place_source(rt.world, iy, ix, 5.0)
    for _ in range(20):
        rt.step()
    assert float(np.max(rt.body.R_site)) <= 0.15 + 1e-12
    assert float(rt.world.R[iy, ix]) > 0.0


def test_historical_missing_resource_config_is_off():
    rt = _rt()
    snap = rt.snapshot()
    historical = copy.deepcopy(snap)
    historical["config"].pop("environmental_resource")
    old = PhysicalSystemRuntime.restore(historical)
    assert old.config.environmental_resource.enabled is False


def test_snapshot_preserves_R_and_R_site():
    rt = _rt()
    iy, ix = _center(rt)
    place_source(rt.world, iy, ix, 0.7)
    rt.step()
    snap = rt.snapshot()
    restored = PhysicalSystemRuntime.restore(snap)
    assert np.allclose(restored.world.R, rt.world.R)
    assert np.allclose(restored.body.R_site, rt.body.R_site)
