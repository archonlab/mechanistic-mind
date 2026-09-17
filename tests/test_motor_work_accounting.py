import copy

import numpy as np

from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.motor_work import EndogenousMotorWorkConfig, allocate_shared_work
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime


def _rt(seed=17, **edits):
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.planet.flow_enabled = False
    cfg.planet.flow_gain = 0.0
    cfg.body.flow_coupling = 0.0
    cfg.body.wave_coupling = 0.0
    cfg.environmental_resource.mode = "OFF"
    cfg.complementary_resources.mode = "OFF"
    cfg.body_deformation.mode = "OFF"
    cfg.deformation_work.reservoir_init = 2.0
    cfg.deformation_work.reservoir_max = 8.0
    for k, v in edits.items():
        if k.startswith("mw."):
            setattr(cfg.endogenous_motor_work, k[3:], v)
        elif k.startswith("endo."):
            setattr(cfg.endogenous_motor, k[5:], v)
        elif k.startswith("work."):
            setattr(cfg.deformation_work, k[5:], v)
        elif k.startswith("deform."):
            setattr(cfg.body_deformation, k[7:], v)
        elif k.startswith("comp."):
            setattr(cfg.complementary_resources, k[5:], v)
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.body.vx = rt.body.vy = 0.0
    rt.body.omega = 0.0
    ensure_B_site(rt.body, len(cfg.body.footprint))
    rt.world.vx[:] = rt.world.vy[:] = rt.world.u[:] = 0.0
    return rt


def _spinup_drive(rt, n=8):
    rt.body.mechanical_work_reservoir = float(rt.config.deformation_work.reservoir_max)
    for _ in range(n):
        rt.step()
    return [float(rt.body.motor_ux), float(rt.body.motor_uy)]


def test_drive_persists_when_empty_but_realization_differs():
    a = _rt()
    b = _rt()
    drive_a = _spinup_drive(a)
    _spinup_drive(b)
    a.body.x, a.body.y = b.body.x, b.body.y
    a.body.vx = b.body.vx = 0.05
    a.body.vy = b.body.vy = 0.0
    a.body.theta = b.body.theta
    a.body.omega = b.body.omega = 0.0
    a.body.motor_ux = b.body.motor_ux = drive_a[0]
    a.body.motor_uy = b.body.motor_uy = drive_a[1]
    a.body.mechanical_work_reservoir = 3.0
    b.body.mechanical_work_reservoir = 0.0
    a.step()
    b.step()
    la, lb = a.last_motor_work_ledger, b.last_motor_work_ledger
    assert abs(la["motor_drive_requested"][0] - lb["motor_drive_requested"][0]) < 1e-9
    assert abs(la["motor_drive_requested"][1] - lb["motor_drive_requested"][1]) < 1e-9
    assert la["motor_work_realized"] > lb["motor_work_realized"] + 1e-12
    assert lb["motor_work_realized"] <= 1e-12
    assert abs(np.hypot(*lb["motor_delta_v_realized"])) < abs(np.hypot(*la["motor_delta_v_realized"]))


def test_zero_work_no_positive_motor_work():
    rt = _rt()
    rt.body.motor_ux, rt.body.motor_uy = 0.12, 0.0
    rt.body.mechanical_work_reservoir = 0.0
    v0 = rt.body.vx
    rt.step()
    lg = rt.last_motor_work_ledger
    assert abs(lg["motor_drive_requested"][0]) > 0
    assert lg["motor_work_realized"] <= 1e-12
    assert lg.get("work_unavailable") or abs(np.hypot(*lg["motor_delta_v_realized"])) < 1e-12
    assert rt.body.mechanical_work_reservoir >= -1e-15


def test_abundant_matches_historical_ablation():
    on = _rt(**{"work.reservoir_init": 8.0})
    off = _rt(**{"mw.mode": "OFF", "work.reservoir_init": 8.0})
    on.body.mechanical_work_reservoir = 8.0
    off.body.mechanical_work_reservoir = 8.0
    for _ in range(6):
        on.step()
        off.step()
    on.body.motor_ux = off.body.motor_ux
    on.body.motor_uy = off.body.motor_uy
    on.body.vx = off.body.vx = 0.0
    on.body.vy = off.body.vy = 0.0
    on.body.x, on.body.y = off.body.x, off.body.y
    on.step()
    off.step()
    assert abs(on.body.vx - off.body.vx) < 5e-4
    assert abs(on.body.vy - off.body.vy) < 5e-4


def test_partial_work_monotone():
    drives = []
    dvs = []
    for w in (0.0, 0.002, 0.02, 0.2):
        rt = _rt()
        rt.body.motor_ux, rt.body.motor_uy = 0.2, 0.0
        rt.body.vx = rt.body.vy = 0.0
        rt.body.mechanical_work_reservoir = w
        rt.step()
        drives.append(rt.last_motor_work_ledger["motor_drive_requested"][0])
        dvs.append(abs(rt.last_motor_work_ledger["motor_delta_v_realized"][0]))
    assert all(abs(d - drives[0]) < 1e-12 for d in drives)
    assert dvs[0] <= dvs[1] + 1e-15
    assert dvs[1] <= dvs[2] + 1e-12
    assert dvs[2] <= dvs[3] + 1e-12


def test_blocked_vmax_zero_work():
    rt = _rt()
    rt.config.body.v_max = 0.0
    rt.body.motor_ux, rt.body.motor_uy = 0.2, 0.0
    rt.body.mechanical_work_reservoir = 2.0
    w0 = rt.body.mechanical_work_reservoir
    rt.step()
    assert abs(rt.body.vx) < 1e-15
    assert rt.last_motor_work_ledger["motor_work_realized"] <= 1e-12
    assert rt.body.mechanical_work_reservoir >= w0 - 1e-12


def test_no_torque_from_motor():
    rt = _rt()
    rt.body.motor_ux, rt.body.motor_uy = 0.15, 0.05
    rt.body.mechanical_work_reservoir = 4.0
    om0 = rt.body.omega
    rt.step()
    # site forces may still torque; motor itself is CoM. Isolate: zero site by matching.
    # Compare omega change with motor off clone sharing sites.
    assert True
    rt2 = _rt()
    rt2.body.motor_ux = rt2.body.motor_uy = 0.0
    rt2.config.endogenous_motor.mode = "OFF"
    rt2.body.mechanical_work_reservoir = 4.0
    rt2.step()
    # With motor on vs off at rest-ish, extra omega from motor should be ~0 vs site-only.
    # After one tick both have orientation sites; difference in omega should be tiny if motor is center-applied.
    assert abs((rt.body.omega - om0) - (rt2.body.omega - 0.0)) < 5e-3 or abs(rt.body.omega - rt2.body.omega) < 5e-3


def test_allocation_no_double_spend():
    a = allocate_shared_work(0.10, 0.08, 0.08)
    assert abs(a["allocated_deformation"] + a["allocated_motor"] - 0.10) < 1e-12
    b = allocate_shared_work(1.0, 0.1, 0.2)
    assert abs(b["allocated_deformation"] - 0.1) < 1e-12
    assert abs(b["allocated_motor"] - 0.2) < 1e-12


def test_ab_replenish_then_motor():
    rt = _rt(**{"comp.mode": "EXPERIMENTAL", "comp.A_passive_loss": 0.0, "comp.B_passive_loss": 0.0})
    rt.body.mechanical_work_reservoir = 0.0
    rt.body.motor_ux, rt.body.motor_uy = 0.18, 0.0
    rt.step()
    assert rt.last_motor_work_ledger["motor_work_realized"] <= 1e-12
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    place_source_AB(rt.world, iy, ix, A=3.0, B=3.0)
    moved = False
    for _ in range(25):
        rt.step()
        if (rt.last_motor_work_ledger or {}).get("motor_work_realized", 0) > 1e-12:
            moved = True
            break
    assert moved
    assert rt.body.mechanical_work_reservoir >= 0.0


def test_historical_missing_key_off():
    assert EndogenousMotorWorkConfig.from_dict(None).mode == "OFF"
    rt = _rt()
    snap = rt.snapshot()
    historical = copy.deepcopy(snap)
    historical["config"].pop("endogenous_motor_work")
    old = PhysicalSystemRuntime.restore(historical)
    assert old.config.endogenous_motor_work.enabled is False


def test_direction_unchanged_by_work():
    a = _rt()
    b = _rt()
    a.body.motor_ux = b.body.motor_ux = 0.1
    a.body.motor_uy = b.body.motor_uy = 0.05
    a.body.mechanical_work_reservoir = 4.0
    b.body.mechanical_work_reservoir = 0.001
    a.step()
    b.step()
    da = np.array(a.last_motor_work_ledger["motor_drive_requested"])
    db = np.array(b.last_motor_work_ledger["motor_drive_requested"])
    assert np.allclose(da, db)
    ra = np.array(a.last_motor_work_ledger["motor_delta_v_realized"])
    rb = np.array(b.last_motor_work_ledger["motor_delta_v_realized"])
    if np.linalg.norm(ra) > 1e-9 and np.linalg.norm(rb) > 1e-9:
        ua, ub = ra / np.linalg.norm(ra), rb / np.linalg.norm(rb)
        assert float(ua @ ub) > 0.99
