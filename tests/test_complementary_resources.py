import copy

import numpy as np

from mechanistic_mind.physical_system.complementary_resources import (
    ComplementaryResourcesConfig,
    place_source_AB,
)
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.body_orientation import oriented_site_cells
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime


def _rt(seed=17, **edits):
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.endogenous_motor.mode = "OFF"
    cfg.planet.flow_enabled = False
    cfg.planet.flow_gain = 0.0
    cfg.body.flow_coupling = 0.0
    cfg.body.wave_coupling = 0.0
    cfg.deformation_work.reservoir_init = 0.0
    cfg.environmental_resource.mode = "OFF"
    for k, v in edits.items():
        setattr(cfg.complementary_resources, k, v)
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.body.mechanical_work_reservoir = 0.0
    rt.body.vx = rt.body.vy = 0.0
    rt.body.omega = 0.0
    ensure_B_site(rt.body, len(cfg.body.footprint))
    return rt


def _center(rt):
    return rt.body.cell(rt.config.planet.width, rt.config.planet.height)


def test_a_and_b_independent_fields():
    rt = _rt()
    iy, ix = _center(rt)
    place_source_AB(rt.world, iy, ix, A=1.0, B=0.0)
    assert float(rt.world.R_A[iy, ix]) == 1.0
    assert float(rt.world.R_B[iy, ix]) == 0.0
    place_source_AB(rt.world, iy, ix, A=0.0, B=0.4)
    assert float(rt.world.R_A[iy, ix]) == 1.0
    assert float(rt.world.R_B[iy, ix]) == 0.4


def test_local_transfer_and_source_depletion():
    rt = _rt(conversion_enabled=False)
    iy, ix = _center(rt)
    place_source_AB(rt.world, iy, ix, A=1.0, B=0.5)
    envA0, envB0 = float(rt.world.R_A.sum()), float(rt.world.R_B.sum())
    rt.step()
    cl = rt.last_complementary_ledger
    assert cl["A"]["acquired"] > 0
    assert cl["B"]["acquired"] > 0
    assert abs(cl["A"]["residual"]) < 1e-12
    assert abs(cl["B"]["residual"]) < 1e-12
    assert float(rt.world.R_A.sum()) < envA0
    assert float(rt.world.R_B.sum()) < envB0


def test_no_contact_no_transfer():
    rt = _rt(conversion_enabled=False)
    iy, ix = _center(rt)
    place_source_AB(rt.world, (iy + 10) % rt.world.T.shape[0], (ix + 10) % rt.world.T.shape[1], A=1.0, B=1.0)
    eA, eB = float(rt.world.R_A.sum()), float(rt.world.R_B.sum())
    rt.step()
    assert rt.last_complementary_ledger["A"]["acquired"] == 0.0
    assert rt.last_complementary_ledger["B"]["acquired"] == 0.0
    assert abs(float(rt.world.R_A.sum()) - eA) < 1e-12
    assert abs(float(rt.world.R_B.sum()) - eB) < 1e-12


def test_hard_complementarity_zero_b():
    rt = _rt(transfer_A_enabled=False, transfer_B_enabled=False)
    n = len(rt.config.body.footprint)
    rt.body.R_A_site = np.full(n, 5.0)
    rt.body.R_B_site = np.zeros(n)
    w0 = rt.body.mechanical_work_reservoir
    rt.step()
    assert rt.last_complementary_ledger["work_credited"] == 0.0
    assert abs(rt.body.mechanical_work_reservoir - w0) < 1e-12


def test_hard_complementarity_zero_a():
    rt = _rt(transfer_A_enabled=False, transfer_B_enabled=False)
    n = len(rt.config.body.footprint)
    rt.body.R_A_site = np.zeros(n)
    rt.body.R_B_site = np.full(n, 5.0)
    rt.step()
    assert rt.last_complementary_ledger["work_credited"] == 0.0


def test_both_present_converts():
    rt = _rt(transfer_A_enabled=False, transfer_B_enabled=False)
    n = len(rt.config.body.footprint)
    rt.body.R_A_site = np.zeros(n)
    rt.body.R_B_site = np.zeros(n)
    rt.body.R_A_site[0] = 0.4
    rt.body.R_B_site[0] = 0.4
    w0 = rt.body.mechanical_work_reservoir
    rt.step()
    cl = rt.last_complementary_ledger
    assert cl["work_credited"] > 0
    assert rt.body.mechanical_work_reservoir > w0
    assert cl["consumed_A"] > 0 and cl["consumed_B"] > 0
    assert abs(cl["conversion_residual"]) < 1e-12


def test_stoichiometry_b_limits():
    rt = _rt(transfer_A_enabled=False, transfer_B_enabled=False, conversion_rate=0.2, A_passive_loss=0.0, B_passive_loss=0.0)
    n = len(rt.config.body.footprint)
    rt.body.R_A_site = np.zeros(n)
    rt.body.R_B_site = np.zeros(n)
    rt.body.R_A_site[0] = 1.0
    rt.body.R_B_site[0] = 0.08
    for _ in range(20):
        rt.step()
    assert float(rt.body.R_B_site[0]) < 1e-9
    assert float(rt.body.R_A_site[0]) > 0.5
    assert rt.last_complementary_ledger["limiting_resource"] in {"B", "NONE"}


def test_stoichiometry_a_limits():
    rt = _rt(transfer_A_enabled=False, transfer_B_enabled=False, conversion_rate=0.2, A_passive_loss=0.0, B_passive_loss=0.0)
    n = len(rt.config.body.footprint)
    rt.body.R_A_site = np.zeros(n)
    rt.body.R_B_site = np.zeros(n)
    rt.body.R_A_site[0] = 0.08
    rt.body.R_B_site[0] = 1.0
    for _ in range(20):
        rt.step()
    assert float(rt.body.R_A_site[0]) < 1e-9
    assert float(rt.body.R_B_site[0]) > 0.5


def test_transfer_ablations_independent():
    aoff = _rt(transfer_A_enabled=False, conversion_enabled=False)
    iy, ix = _center(aoff)
    place_source_AB(aoff.world, iy, ix, A=1.0, B=1.0)
    aoff.step()
    assert aoff.last_complementary_ledger["A"]["acquired"] == 0.0
    assert aoff.last_complementary_ledger["B"]["acquired"] > 0
    boff = _rt(transfer_B_enabled=False, conversion_enabled=False)
    iy, ix = _center(boff)
    place_source_AB(boff.world, iy, ix, A=1.0, B=1.0)
    boff.step()
    assert boff.last_complementary_ledger["B"]["acquired"] == 0.0
    assert boff.last_complementary_ledger["A"]["acquired"] > 0


def test_conversion_ablation_no_debit():
    rt = _rt(conversion_enabled=False, transfer_A_enabled=False, transfer_B_enabled=False, A_passive_loss=0.0, B_passive_loss=0.0)
    n = len(rt.config.body.footprint)
    rt.body.R_A_site = np.full(n, 0.3)
    rt.body.R_B_site = np.full(n, 0.2)
    a0, b0, w0 = float(rt.body.R_A_site.sum()), float(rt.body.R_B_site.sum()), rt.body.mechanical_work_reservoir
    rt.step()
    assert abs(float(rt.body.R_A_site.sum()) - a0) < 1e-12
    assert abs(float(rt.body.R_B_site.sum()) - b0) < 1e-12
    assert abs(rt.body.mechanical_work_reservoir - w0) < 1e-12


def test_no_hidden_single_r_fallback():
    rt = _rt()
    n = len(rt.config.body.footprint)
    rt.body.R_site = np.full(n, 2.0)
    rt.body.R_A_site = np.zeros(n)
    rt.body.R_B_site = np.zeros(n)
    rt.config.environmental_resource.mode = "EXPERIMENTAL"
    rt.config.environmental_resource.conversion_enabled = True
    rt.config.environmental_resource.transfer_enabled = False
    r0 = float(np.sum(rt.body.R_site))
    w0 = rt.body.mechanical_work_reservoir
    rt.step()
    assert rt.last_resource_ledger.get("conversion_skipped_due_to_complementary") is True
    assert abs(rt.body.mechanical_work_reservoir - w0) < 1e-12
    assert abs(float(np.sum(rt.body.R_site)) - r0) < 1e-12


def test_passive_b_loss_accounted():
    rt = _rt(transfer_A_enabled=False, transfer_B_enabled=False, conversion_enabled=False, A_passive_loss=0.0, B_passive_loss=0.12)
    n = len(rt.config.body.footprint)
    rt.body.R_B_site = np.zeros(n)
    rt.body.R_B_site[0] = 0.2
    before = 0.2
    rt.step()
    lost = rt.last_complementary_ledger["B"]["passive_loss"]
    after = float(rt.body.R_B_site[0])
    assert abs(before - lost - after) < 1e-12
    assert lost > 0


def test_a_first_then_b_converts():
    rt = _rt(conversion_enabled=False, B_passive_loss=0.0, A_passive_loss=0.0)
    n = len(rt.config.body.footprint)
    iy, ix = _center(rt)
    place_source_AB(rt.world, iy, ix, A=1.0, B=0.0)
    for _ in range(8):
        rt.step()
    rt.world.R_A[:] = 0
    stored_A = float(np.sum(rt.body.R_A_site))
    assert stored_A > 0
    rt.config.complementary_resources.conversion_enabled = True
    rt.config.complementary_resources.transfer_A_enabled = False
    place_source_AB(rt.world, iy, ix, B=1.0)
    w0 = rt.body.mechanical_work_reservoir
    for _ in range(10):
        rt.step()
    assert rt.body.mechanical_work_reservoir > w0
    assert stored_A > float(np.sum(rt.body.R_A_site))


def test_capacity_leaves_env():
    rt = _rt(A_site_capacity=0.10, conversion_enabled=False, A_transfer_rate=0.2, A_passive_loss=0.0)
    iy, ix = _center(rt)
    place_source_AB(rt.world, iy, ix, A=3.0)
    for _ in range(20):
        rt.step()
    assert float(np.max(rt.body.R_A_site)) <= 0.10 + 1e-9
    assert float(rt.world.R_A[iy, ix]) > 1.0


def test_historical_missing_keys_off():
    assert ComplementaryResourcesConfig.from_dict(None).mode == "OFF"
    rt = _rt()
    snap = rt.snapshot()
    historical = copy.deepcopy(snap)
    historical["config"].pop("complementary_resources")
    old = PhysicalSystemRuntime.restore(historical)
    assert old.config.complementary_resources.enabled is False


def test_snapshot_preserves_ab():
    rt = _rt(conversion_enabled=False)
    iy, ix = _center(rt)
    place_source_AB(rt.world, iy, ix, A=0.6, B=0.3)
    rt.step()
    restored = PhysicalSystemRuntime.restore(rt.snapshot())
    assert np.allclose(restored.world.R_A, rt.world.R_A)
    assert np.allclose(restored.world.R_B, rt.world.R_B)
    assert np.allclose(restored.body.R_A_site, rt.body.R_A_site)
    assert np.allclose(restored.body.R_B_site, rt.body.R_B_site)


def test_rotation_site_local():
    r0 = _rt(conversion_enabled=False, A_transfer_rate=0.5)
    cells0 = oriented_site_cells(r0.body, r0.config.planet.width, r0.config.planet.height, r0.config.body.footprint, theta=0.0)
    iy4, ix4 = cells0[4]
    place_source_AB(r0.world, iy4, ix4, A=0.5)
    r0.body.theta = 0.0
    r0.step()
    site4 = float(r0.body.R_A_site[4])
    rpi = _rt(conversion_enabled=False, A_transfer_rate=0.5)
    rpi.body.theta = np.pi
    place_source_AB(rpi.world, iy4, ix4, A=0.5)
    rpi.step()
    gained = [float(x) for x in rpi.body.R_A_site]
    assert site4 > 1e-6
    assert max(gained) > 1e-6
    assert abs(gained[4] - site4) > 1e-9


def test_motor_u_untouched():
    rt = _rt()
    iy, ix = _center(rt)
    place_source_AB(rt.world, iy, ix, A=1.0, B=1.0)
    rt.step()
    assert abs(rt.body.motor_ux) + abs(rt.body.motor_uy) < 1e-15
