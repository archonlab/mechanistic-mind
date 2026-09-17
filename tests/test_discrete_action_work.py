import copy

import numpy as np

from mechanistic_mind.physical_system.action_work import (
    DiscreteActionWorkConfig,
    request_discrete_action,
)
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.motor_work import allocate_shared_work, ke_increment
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime


def _rt(seed=17, *, reservoir=1.0, action_work=True, motor=False, deform=False, resources=False):
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.planet.flow_enabled = False
    cfg.planet.flow_gain = 0.0
    cfg.body.flow_coupling = 0.0
    cfg.body.wave_coupling = 0.0
    cfg.environmental_resource.mode = "OFF"
    cfg.complementary_resources.mode = "EXPERIMENTAL" if resources else "OFF"
    cfg.endogenous_motor.mode = "EXPERIMENTAL" if motor else "OFF"
    cfg.endogenous_motor_work.mode = "EXPERIMENTAL"
    cfg.body_deformation.mode = "EXPERIMENTAL" if deform else "OFF"
    cfg.discrete_action_work.mode = "EXPERIMENTAL" if action_work else "OFF"
    cfg.deformation_work.reservoir_init = reservoir
    cfg.deformation_work.reservoir_max = 8.0
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.body.mechanical_work_reservoir = reservoir
    rt.body.vx = rt.body.vy = 0.0
    rt.body.omega = 0.0
    ensure_B_site(rt.body, len(cfg.body.footprint))
    rt.world.vx[:] = rt.world.vy[:] = rt.world.u[:] = 0.0
    return rt


def test_selected_move_survives_zero_work():
    full = _rt(reservoir=1.0)
    empty = _rt(reservoir=0.0)
    full.step_forced_action("MOVE:E")
    empty.step_forced_action("MOVE:E")
    assert full.last_selected_action == empty.last_selected_action == "MOVE:E"
    assert full.last_action_work_ledger["action_dv_requested"] == empty.last_action_work_ledger["action_dv_requested"]
    assert full.last_action_work_ledger["action_work_realized"] > 0
    assert empty.last_action_work_ledger["action_work_realized"] == 0
    assert empty.last_action_work_ledger["action_work_unrealized"] > 0


def test_wait_never_requests_or_debits_action_work():
    for w in (0.0, 2.0):
        rt = _rt(reservoir=w)
        rt.step_forced_action("WAIT")
        lg = rt.last_action_work_ledger
        assert lg["action_work_requested"] == 0.0
        assert lg["action_work_realized"] == 0.0


def test_partial_work_monotone():
    required = _rt(reservoir=2.0)
    required.step_forced_action("MOVE:E")
    w_req = required.last_action_work_ledger["action_work_requested"]
    fractions = (0.0, 0.25, 0.50, 0.75, 1.0)
    realized = []
    for f in fractions:
        rt = _rt(reservoir=f * w_req)
        rt.step_forced_action("MOVE:E")
        lg = rt.last_action_work_ledger
        assert lg["action_dv_requested"] == required.last_action_work_ledger["action_dv_requested"]
        realized.append(float(np.linalg.norm(lg["action_dv_realized"])))
        assert rt.body.mechanical_work_reservoir >= -1e-15
    assert all(a <= b + 1e-12 for a, b in zip(realized, realized[1:]))


def test_abundant_work_matches_historical_free_action():
    accounted = _rt(reservoir=2.0, action_work=True)
    historical = _rt(reservoir=2.0, action_work=False)
    accounted.body.vx = historical.body.vx = 0.03
    accounted.step_forced_action("MOVE:N")
    historical.step_forced_action("MOVE:N")
    assert np.allclose(
        accounted.last_action_work_ledger["action_dv_realized"],
        historical.last_action_work_ledger["action_dv_realized"],
        atol=1e-12,
    )


def test_direction_changes_actual_work_not_fixed_tax():
    m, vmax, gain = 2.0, 0.30, 0.35
    aligned = request_discrete_action(
        action="MOVE:E", vx=0.18, vy=0.0, mass=m, v_max=vmax,
        impulse_scale=gain, tick=0,
    )
    opposed = request_discrete_action(
        action="MOVE:W", vx=0.18, vy=0.0, mass=m, v_max=vmax,
        impulse_scale=gain, tick=0,
    )
    perpendicular = request_discrete_action(
        action="MOVE:N", vx=0.18, vy=0.0, mass=m, v_max=vmax,
        impulse_scale=gain, tick=0,
    )
    assert aligned["action_work_requested"] > perpendicular["action_work_requested"]
    assert opposed["action_work_requested"] == 0.0
    assert opposed["action_negative_work_requested"] > 0.0


def test_negative_action_work_not_recovered():
    rt = _rt(reservoir=0.4)
    rt.body.vx = 0.18
    w0 = rt.body.mechanical_work_reservoir
    rt.step_forced_action("MOVE:W")
    lg = rt.last_action_work_ledger
    assert lg["action_work_signed_realized"] < 0
    assert lg["action_negative_work_realized"] > 0
    assert lg["action_work_realized"] == 0
    # Resource conversion is disabled; action itself cannot raise reservoir.
    assert rt.body.mechanical_work_reservoir <= w0 + 1e-12


def test_blocked_vmax_keeps_nominal_request_but_zero_work():
    rt = _rt(reservoir=2.0)
    req = request_discrete_action(
        action="MOVE:E", vx=0.3, vy=0.0, mass=2.0, v_max=0.3,
        impulse_scale=0.35, tick=0,
    )
    rt.body.vx = 0.3
    from mechanistic_mind.physical_system.action_work import realize_discrete_action
    out = realize_discrete_action(
        rt.body, req, accounting_enabled=True, allocated_work=0.0,
        reservoir_max=8.0,
    )
    assert np.linalg.norm(out["action_dv_requested"]) > 0
    assert np.linalg.norm(out["action_dv_realized"]) == 0
    assert out["action_work_realized"] == 0


def test_three_way_allocator_and_runtime_no_double_spend():
    rt = _rt(reservoir=0.02, motor=True, deform=True)
    rt.body.motor_ux, rt.body.motor_uy = 0.16, 0.0
    rt.body.B_site[:] = 0.2
    rt.body.B_site[3] = 1.9
    rt.step_forced_action("MOVE:E")
    alloc = rt.last_work_allocation
    assert alloc["requested_action"] > 0
    assert alloc["requested_motor"] > 0
    assert alloc["requested_deformation"] > 0
    assert (
        alloc["allocated_action"]
        + alloc["allocated_motor"]
        + alloc["allocated_deformation"]
        <= alloc["available"] + 1e-12
    )
    budget = rt.last_work_ledger["three_way_budget"]
    assert budget["no_double_spend"]
    assert budget["total_positive_debit"] <= budget["allocation_available"] + 1e-9
    assert rt.body.mechanical_work_reservoir >= 0


def test_allocator_is_permutation_invariant():
    a = allocate_shared_work(0.1, 0.08, 0.05, 0.12)
    b = allocate_shared_work(0.1, 0.12, 0.08, 0.05)
    # Permuting channel labels permutes proportional shares, not priority.
    assert abs(a["allocated_action"] - b["allocated_deformation"]) < 1e-12
    assert abs(a["allocated_deformation"] - b["allocated_motor"]) < 1e-12
    assert abs(a["allocated_motor"] - b["allocated_action"]) < 1e-12


def test_motor_action_cross_term_is_explicit():
    rt = _rt(reservoir=2.0, motor=True)
    rt.body.motor_ux, rt.body.motor_uy = 0.10, 0.04
    rt.step_forced_action("MOVE:E")
    alloc = rt.last_work_allocation
    assert "motor_action_ke_cross_term" in alloc
    assert abs(
        alloc["cross_term_symmetric_action"]
        + alloc["cross_term_symmetric_motor"]
        - alloc["motor_action_ke_cross_term"]
    ) < 1e-12
    # Algebraic cross term for simultaneous increments.
    da = np.asarray(rt.last_action_work_ledger["action_dv_requested_after_vmax"])
    dm = np.asarray(rt.last_motor_work_ledger["motor_delta_v_requested"])
    expected = rt.config.body.mass * float(da @ dm)
    assert abs(expected - alloc["motor_action_ke_cross_term"]) < 1e-12


def test_resource_chain_can_power_later_selected_move():
    rt = _rt(reservoir=0.0, resources=True)
    rt.config.body.displacement_enabled = False
    rt.step_forced_action("MOVE:E")
    assert rt.last_action_work_ledger["action_work_realized"] == 0
    iy, ix = rt.body.cell(rt.config.planet.width, rt.config.planet.height)
    place_source_AB(rt.world, iy, ix, A=2.0, B=2.0)
    # Conversion occurs after this tick's allocator; work powers a later MOVE.
    rt.step_forced_action("WAIT")
    assert (rt.last_complementary_ledger or {})["work_credited"] > 0
    rt.step_forced_action("MOVE:E")
    assert rt.last_selected_action == "MOVE:E"
    assert rt.last_action_work_ledger["action_work_realized"] > 0


def test_snapshot_missing_key_preserves_historical_free_action():
    assert DiscreteActionWorkConfig.from_dict(None).mode == "OFF"
    rt = _rt()
    old_payload = copy.deepcopy(rt.snapshot())
    old_payload["config"].pop("discrete_action_work")
    old = PhysicalSystemRuntime.restore(old_payload)
    assert not old.config.discrete_action_work.enabled


def test_world_frame_rotation_and_reflection():
    a = _rt(reservoir=2.0)
    b = _rt(reservoir=2.0)
    a.body.theta = 0.0
    b.body.theta = np.pi
    a.step_forced_action("MOVE:N")
    b.step_forced_action("MOVE:N")
    assert a.last_action_work_ledger["action_dv_requested"] == b.last_action_work_ledger["action_dv_requested"]

    east = request_discrete_action(
        action="MOVE:E", vx=0.04, vy=0, mass=2, v_max=0.3,
        impulse_scale=0.35, tick=0,
    )
    west = request_discrete_action(
        action="MOVE:W", vx=-0.04, vy=0, mass=2, v_max=0.3,
        impulse_scale=0.35, tick=0,
    )
    assert abs(east["action_work_requested"] - west["action_work_requested"]) < 1e-12
