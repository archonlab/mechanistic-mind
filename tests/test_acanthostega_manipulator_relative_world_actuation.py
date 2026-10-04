"""Manipulator relative world actuation — kinematic body-local vertical DOF."""
from __future__ import annotations

from copy import deepcopy

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_manipulator_relative_world_actuation_config,
    )

    cfg = acanthostega_manipulator_relative_world_actuation_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(seed: int = 17):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    return PhysicalSystemRuntime(seed=seed, config=_cfg())


def _bid(rt) -> str:
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

    return body_refs_for_runtime(rt)[0][0]


def _holders(rt):
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

    return [
        {"body_id": bid, "body": b, "config": rt.config, "runtime": rt}
        for bid, b in body_refs_for_runtime(rt)
    ]


def _detect(rt, tick: int):
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        detect_effector_terrain_contacts,
    )

    step = detect_effector_terrain_contacts(
        rt.world, _holders(rt), tick=tick, config=rt.config
    )
    _tick()
    return step


def _pose(rt, mid="LEFT"):
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
    )

    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    return effector_world_pose(
        rt.body,
        width=w,
        height=h,
        config=rt.config,
        manipulator_id=mid,
        runtime=rt,
        world=rt.world,
        body_id=_bid(rt),
    )


def test_preset_child_zero_offset_preserves_geometry():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_MANIPULATOR_RELATIVE_WORLD_ACTUATION,
        acanthostega_effector_terrain_contact_geometry_config,
        acanthostega_manipulator_relative_world_actuation_config,
    )
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        manipulator_relative_world_actuation_is_active,
        relative_z_of,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    child = acanthostega_manipulator_relative_world_actuation_config()
    parent = acanthostega_effector_terrain_contact_geometry_config()
    assert child.public_preset == PUBLIC_PRESET_MANIPULATOR_RELATIVE_WORLD_ACTUATION
    assert manipulator_relative_world_actuation_is_active(child) is True
    assert manipulator_relative_world_actuation_is_active(parent) is False

    rt_c = PhysicalSystemRuntime(seed=17, config=child)
    rt_p = PhysicalSystemRuntime(seed=17, config=parent)
    # Same seed/body → same tip when relative z = 0
    assert relative_z_of(rt_c.world, _bid(rt_c), "LEFT", config=rt_c.config) == 0.0
    pc = _pose(rt_c, "LEFT")
    # Parent pose without world/body_id path
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
    )

    w = int(rt_p.world.T.shape[1])
    h = int(rt_p.world.T.shape[0])
    pp = effector_world_pose(
        rt_p.body, width=w, height=h, config=rt_p.config, manipulator_id="LEFT", runtime=rt_p
    )
    assert abs(pc[0] - pp[0]) < 1e-12
    assert abs(pc[1] - pp[1]) < 1e-12
    assert abs(pc[2] - pp[2]) < 1e-12
    acts = list(rt_c.cognition.get("available_actions") or [])
    for forbidden in ("DIG", "REACH_GROUND", "TOUCH_GROUND", "EXCAVATE", "PUNCH"):
        assert forbidden not in acts


def test_single_effector_relative_motion_body_fixed():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        request_relative_effector_displacement,
        relative_z_of,
    )

    rt = _rt(19)
    bx, by, bz = rt.body.x, rt.body.y, rt.body.z
    z0 = _pose(rt, "LEFT")[2]
    zr0 = _pose(rt, "RIGHT")[2]
    bid = _bid(rt)
    rec = request_relative_effector_displacement(
        rt.world,
        config=rt.config,
        body_id=bid,
        effector_id="LEFT",
        requested_delta_z=-0.05,
        tick=1,
    )
    _tick()
    assert rec["status"] == "APPLIED"
    assert abs(rec["achieved_delta_z"] + 0.05) < 1e-12
    assert abs(relative_z_of(rt.world, bid, "LEFT", config=rt.config) + 0.05) < 1e-12
    assert abs(relative_z_of(rt.world, bid, "RIGHT", config=rt.config)) < 1e-12
    assert abs(rt.body.x - bx) < 1e-12 and abs(rt.body.y - by) < 1e-12
    assert abs(rt.body.z - bz) < 1e-12
    assert abs(_pose(rt, "LEFT")[2] - (z0 - 0.05)) < 1e-12
    assert abs(_pose(rt, "RIGHT")[2] - zr0) < 1e-12


def test_body_motion_only_relative_zero():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        relative_z_of,
    )

    rt = _rt(21)
    bid = _bid(rt)
    assert relative_z_of(rt.world, bid, "LEFT", config=rt.config) == 0.0
    p0 = _pose(rt, "LEFT")
    rt.body.x += 0.25
    p1 = _pose(rt, "LEFT")
    assert abs(p1[0] - p0[0] - 0.25) < 1e-9 or abs(
        ((p1[0] - p0[0] + 16) % 32) - 0.25
    ) < 1e-6
    assert relative_z_of(rt.world, bid, "LEFT", config=rt.config) == 0.0


def test_rate_and_reach_limits_kinematic():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        DEFAULT_MAX_DELTA_Z_PER_TICK,
        DEFAULT_MAX_RELATIVE_Z,
        request_relative_effector_displacement,
        relative_z_of,
    )

    rt = _rt(23)
    bid = _bid(rt)
    rec = request_relative_effector_displacement(
        rt.world,
        config=rt.config,
        body_id=bid,
        effector_id="LEFT",
        requested_delta_z=-10.0,
        tick=1,
    )
    _tick()
    assert rec["rate_clipped"] is True
    assert abs(abs(rec["achieved_delta_z"]) - DEFAULT_MAX_DELTA_Z_PER_TICK) < 1e-12
    # Drive to reach boundary
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        drive_relative_z_to,
    )

    rows = drive_relative_z_to(
        rt.world,
        config=rt.config,
        body_id=bid,
        effector_id="LEFT",
        target_z=-DEFAULT_MAX_RELATIVE_Z - 1.0,
        tick_start=2,
        max_steps=20,
    )
    _tick(len(rows))
    z = relative_z_of(rt.world, bid, "LEFT", config=rt.config)
    assert abs(z + DEFAULT_MAX_RELATIVE_Z) < 1e-12
    assert any(r.get("reach_clipped") for r in rows) or abs(z + DEFAULT_MAX_RELATIVE_Z) < 1e-12


def test_requested_vs_achieved():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        request_relative_effector_displacement,
    )

    rt = _rt(25)
    bid = _bid(rt)
    rec = request_relative_effector_displacement(
        rt.world,
        config=rt.config,
        body_id=bid,
        effector_id="LEFT",
        requested_delta_z=-0.5,
        tick=1,
    )
    _tick()
    assert rec["requested_delta_z"] == -0.5
    assert abs(rec["achieved_delta_z"]) < 0.5 - 1e-9  # rate clipped
    assert rec["rate_clipped"] is True


def test_terrain_contact_by_relative_actuation_body_fixed():
    """HARD GATE: stationary body; relative z lowers tip into terrain contact."""
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        PHASE_BEGIN,
        PHASE_END,
        PHASE_PERSIST,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        drive_relative_z_to,
        relative_z_of,
    )

    rt = _rt(27)
    bid = _bid(rt)
    # Freeze body
    rt.body.vx = rt.body.vy = rt.body.vz = 0.0
    bx, by = rt.body.x, rt.body.y
    ex, ey, ez0 = _pose(rt, "LEFT")
    h = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    # Need relative_z such that centre_z + z <= h  ⇒  z <= h - centre_z
    cz = float(centre_z_of(rt.body, kind="body", config=rt.config))
    target = float(h - cz)  # exact touch (clearance 0)
    assert target < -0.01  # must require lowering
    # No contact initially
    s0 = _detect(rt, tick=1)
    assert s0["begin"] == 0
    rows = drive_relative_z_to(
        rt.world,
        config=rt.config,
        body_id=bid,
        effector_id="LEFT",
        target_z=target,
        tick_start=2,
        max_steps=20,
    )
    _tick(len(rows))
    assert abs(rt.body.x - bx) < 1e-12 and abs(rt.body.y - by) < 1e-12
    assert abs(relative_z_of(rt.world, bid, "LEFT", config=rt.config) - target) < 1e-9
    s1 = _detect(rt, tick=50)
    left = [r for r in s1["receipts"] if r["effector_id"] == "LEFT" and r["phase"] == PHASE_BEGIN]
    assert len(left) == 1
    assert left[0]["contact_point"] is not None
    assert left[0]["normal"] is not None
    # Persist
    s2 = _detect(rt, tick=51)
    assert any(r["phase"] == PHASE_PERSIST and r["effector_id"] == "LEFT" for r in s2["receipts"])
    # Raise away
    drive_relative_z_to(
        rt.world,
        config=rt.config,
        body_id=bid,
        effector_id="LEFT",
        target_z=0.0,
        tick_start=52,
        max_steps=20,
    )
    s3 = _detect(rt, tick=80)
    assert any(r["phase"] == PHASE_END and r["effector_id"] == "LEFT" for r in s3["receipts"])


def test_left_right_independent():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        request_relative_effector_displacement,
        relative_z_of,
    )

    rt = _rt(29)
    bid = _bid(rt)
    request_relative_effector_displacement(
        rt.world, config=rt.config, body_id=bid, effector_id="LEFT", requested_delta_z=-0.04, tick=1
    )
    request_relative_effector_displacement(
        rt.world, config=rt.config, body_id=bid, effector_id="RIGHT", requested_delta_z=0.03, tick=1
    )
    _tick(2)
    assert abs(relative_z_of(rt.world, bid, "LEFT", config=rt.config) + 0.04) < 1e-12
    assert abs(relative_z_of(rt.world, bid, "RIGHT", config=rt.config) - 0.03) < 1e-12


def test_no_mass_force_work_impulse():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        request_relative_effector_displacement,
    )

    rt = _rt(31)
    rec = request_relative_effector_displacement(
        rt.world,
        config=rt.config,
        body_id=_bid(rt),
        effector_id="LEFT",
        requested_delta_z=-0.02,
        tick=1,
    )
    _tick()
    assert rec["mass"] is False
    assert rec["force"] is False
    assert rec["work"] is False
    assert rec["impulse"] is False


def test_snapshot_nonzero_offset():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        request_relative_effector_displacement,
        relative_z_of,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _rt(33)
    bid = _bid(rt)
    request_relative_effector_displacement(
        rt.world, config=rt.config, body_id=bid, effector_id="LEFT", requested_delta_z=-0.07, tick=1
    )
    _tick()
    snap = deepcopy(rt.snapshot())
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert abs(relative_z_of(rt2.world, bid, "LEFT", config=rt2.config) + 0.07) < 1e-12


def test_aperture_regression_zero_offset():
    """BRING_TOGETHER aperture still available; relative offsets stay 0."""
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        relative_z_of,
    )
    from mechanistic_mind.physical_system.physical_manipulator import bring_together_is_active

    rt = _rt(35)
    assert bring_together_is_active(rt.config) is True
    assert relative_z_of(rt.world, _bid(rt), "LEFT", config=rt.config) == 0.0


def test_separation_still_works():
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        apply_surface_material_separation,
    )

    rt = _rt(37)
    out = apply_surface_material_separation(
        rt.world, rt.config, cell_x=10, cell_y=10, requested_thickness=0.05, tick=1
    )
    assert out["receipt"]["status"] == "COMMITTED"
    _tick()


def test_tiktaalik_unchanged():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        manipulator_relative_world_actuation_is_active,
    )

    assert manipulator_relative_world_actuation_is_active(tiktaalik_config()) is False


def test_tick_budget():
    assert TICKS["n"] <= 100
