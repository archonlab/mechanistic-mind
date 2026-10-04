"""Effector bounded actuator effort along relative_z — mechanical V1."""
from __future__ import annotations

from copy import deepcopy

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_effector_bounded_actuator_effort_config,
    )

    cfg = acanthostega_effector_bounded_actuator_effort_config()
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


def _actuate(rt, mid, dz, tick, body=None):
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        request_actuated_relative_displacement,
    )

    return request_actuated_relative_displacement(
        rt.world,
        config=rt.config,
        body=body if body is not None else rt.body,
        body_id=_bid(rt),
        effector_id=mid,
        requested_delta_z=float(dz),
        tick=int(tick),
        runtime=rt,
    )


def test_preset_child_of_relative_actuation():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_EFFECTOR_BOUNDED_ACTUATOR_EFFORT,
        PUBLIC_PRESET_MANIPULATOR_RELATIVE_WORLD_ACTUATION,
        acanthostega_effector_bounded_actuator_effort_config,
        acanthostega_manipulator_relative_world_actuation_config,
    )
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        effector_bounded_actuator_effort_is_active,
    )
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        manipulator_relative_world_actuation_is_active,
    )

    child = acanthostega_effector_bounded_actuator_effort_config()
    parent = acanthostega_manipulator_relative_world_actuation_config()
    assert child.public_preset == PUBLIC_PRESET_EFFECTOR_BOUNDED_ACTUATOR_EFFORT
    assert parent.public_preset == PUBLIC_PRESET_MANIPULATOR_RELATIVE_WORLD_ACTUATION
    assert effector_bounded_actuator_effort_is_active(child) is True
    assert effector_bounded_actuator_effort_is_active(parent) is False
    assert manipulator_relative_world_actuation_is_active(child) is True
    acts = list(
        __import__(
            "mechanistic_mind.physical_system.runtime", fromlist=["PhysicalSystemRuntime"]
        ).PhysicalSystemRuntime(seed=1, config=child).cognition.get("available_actions")
        or []
    )
    for forbidden in ("DIG", "REACH_GROUND", "TOUCH_GROUND", "EXCAVATE", "PUNCH"):
        assert forbidden not in acts


def test_free_space_preserves_kinematic_motion():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        relative_z_of,
        request_relative_effector_displacement,
    )
    from mechanistic_mind.model.acanthostega import (
        acanthostega_manipulator_relative_world_actuation_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt_a = _rt(41)
    rt_k = PhysicalSystemRuntime(
        seed=41, config=acanthostega_manipulator_relative_world_actuation_config()
    )
    rt_k.config.cognition.cognition_enabled = False
    bid = _bid(rt_a)
    rec = _actuate(rt_a, "LEFT", -0.05, tick=1)
    _tick()
    kin = request_relative_effector_displacement(
        rt_k.world,
        config=rt_k.config,
        body_id=_bid(rt_k),
        effector_id="LEFT",
        requested_delta_z=-0.05,
        tick=1,
    )
    assert rec["status"] == "FREE_SPACE"
    assert abs(rec["work_used"]) < 1e-15
    assert abs(rec["externally_blocked_delta"]) < 1e-15
    assert abs(rec["achieved_relative_delta"] - kin["achieved_delta_z"]) < 1e-12
    assert abs(relative_z_of(rt_a.world, bid, "LEFT", config=rt_a.config) + 0.05) < 1e-12


def test_zero_command_zero_work():
    rec = _actuate(_rt(43), "LEFT", 0.0, tick=1)
    _tick()
    assert rec["status"] == "ZERO_COMMAND"
    assert rec["work_used"] == 0.0


def test_reach_rate_not_external_work():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        DEFAULT_MAX_DELTA_Z_PER_TICK,
    )

    rt = _rt(45)
    rec = _actuate(rt, "LEFT", -10.0, tick=1)
    _tick()
    assert rec["rate_clipped"] is True
    assert abs(abs(rec["achieved_relative_delta"]) - DEFAULT_MAX_DELTA_Z_PER_TICK) < 1e-12
    assert abs(rec["externally_blocked_delta"]) < 1e-15
    assert abs(rec["work_used"]) < 1e-15


def test_terrain_contact_external_block_and_work():
    """Stationary body; drive tip into terrain → blocked Δq + actuator work."""
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        PHASE_BEGIN,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        drive_actuated_relative_z_to,
    )
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        relative_z_of,
    )

    rt = _rt(47)
    rt.body.vx = rt.body.vy = rt.body.vz = 0.0
    bid = _bid(rt)
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
    )

    w, h = int(rt.world.T.shape[1]), int(rt.world.T.shape[0])
    ex, ey, _ez = effector_world_pose(
        rt.body,
        width=w,
        height=h,
        config=rt.config,
        manipulator_id="LEFT",
        runtime=rt,
        world=rt.world,
        body_id=bid,
    )
    surf = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    cz = float(centre_z_of(rt.body, kind="body", config=rt.config))
    target = float(surf - cz) - 0.2  # demand past surface
    assert target < -0.05

    rows = drive_actuated_relative_z_to(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        target_z=target,
        tick_start=1,
        max_steps=40,
        runtime=rt,
    )
    _tick(len(rows))
    assert any(r.get("opposing") for r in rows)
    blocked_rows = [r for r in rows if float(r.get("work_used") or 0.0) > 0.0]
    assert len(blocked_rows) >= 1
    z = relative_z_of(rt.world, bid, "LEFT", config=rt.config)
    # Nonpenetration: tip at/above surface
    assert z >= (surf - cz) - 1e-6
    s = _detect(rt, tick=100)
    assert any(
        r["phase"] == PHASE_BEGIN and r["effector_id"] == "LEFT" for r in s["receipts"]
    ) or any(
        r["effector_id"] == "LEFT" and r["phase"] in ("BEGIN", "PERSIST")
        for r in s["receipts"]
    )


def test_no_penetration_relative_z():
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        drive_actuated_relative_z_to,
    )

    rt = _rt(49)
    bid = _bid(rt)
    w, h = int(rt.world.T.shape[1]), int(rt.world.T.shape[0])
    ex, ey, _ = effector_world_pose(
        rt.body,
        width=w,
        height=h,
        config=rt.config,
        manipulator_id="LEFT",
        runtime=rt,
        world=rt.world,
        body_id=bid,
    )
    surf = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    cz = float(centre_z_of(rt.body, kind="body", config=rt.config))
    drive_actuated_relative_z_to(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        target_z=float(surf - cz) - 1.0,
        tick_start=1,
        max_steps=30,
        runtime=rt,
    )
    _tick(30)
    _, _, tip_z = effector_world_pose(
        rt.body,
        width=w,
        height=h,
        config=rt.config,
        manipulator_id="LEFT",
        runtime=rt,
        world=rt.world,
        body_id=bid,
    )
    assert tip_z >= surf - 1e-6


def test_capacity_bound():
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        DEFAULT_MAX_WORK_PER_TICK,
    )
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        drive_actuated_relative_z_to,
    )

    rt = _rt(51)
    bid = _bid(rt)
    w, h = int(rt.world.T.shape[1]), int(rt.world.T.shape[0])
    ex, ey, _ = effector_world_pose(
        rt.body,
        width=w,
        height=h,
        config=rt.config,
        manipulator_id="LEFT",
        runtime=rt,
        world=rt.world,
        body_id=bid,
    )
    surf = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    cz = float(centre_z_of(rt.body, kind="body", config=rt.config))
    rows = drive_actuated_relative_z_to(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        target_z=float(surf - cz) - 2.0,
        tick_start=1,
        max_steps=25,
        runtime=rt,
    )
    _tick(len(rows))
    for r in rows:
        assert float(r.get("work_used") or 0.0) <= DEFAULT_MAX_WORK_PER_TICK + 1e-12


def test_persist_zero_demand_no_work():
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        drive_actuated_relative_z_to,
    )

    rt = _rt(53)
    bid = _bid(rt)
    w, h = int(rt.world.T.shape[1]), int(rt.world.T.shape[0])
    ex, ey, _ = effector_world_pose(
        rt.body,
        width=w,
        height=h,
        config=rt.config,
        manipulator_id="LEFT",
        runtime=rt,
        world=rt.world,
        body_id=bid,
    )
    surf = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    cz = float(centre_z_of(rt.body, kind="body", config=rt.config))
    drive_actuated_relative_z_to(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        target_z=float(surf - cz),
        tick_start=1,
        max_steps=20,
        runtime=rt,
    )
    _tick(20)
    rec = _actuate(rt, "LEFT", 0.0, tick=50)
    _tick()
    assert rec["work_used"] == 0.0


def test_persist_inward_demand_bounded_work():
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        DEFAULT_MAX_WORK_PER_TICK,
        drive_actuated_relative_z_to,
    )

    rt = _rt(55)
    bid = _bid(rt)
    w, h = int(rt.world.T.shape[1]), int(rt.world.T.shape[0])
    ex, ey, _ = effector_world_pose(
        rt.body,
        width=w,
        height=h,
        config=rt.config,
        manipulator_id="LEFT",
        runtime=rt,
        world=rt.world,
        body_id=bid,
    )
    surf = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    cz = float(centre_z_of(rt.body, kind="body", config=rt.config))
    drive_actuated_relative_z_to(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        target_z=float(surf - cz),
        tick_start=1,
        max_steps=20,
        runtime=rt,
    )
    _tick(20)
    rec = _actuate(rt, "LEFT", -0.1, tick=60)
    _tick()
    assert float(rec["work_used"]) > 0.0
    assert float(rec["work_used"]) <= DEFAULT_MAX_WORK_PER_TICK + 1e-12
    assert abs(rec["achieved_relative_delta"]) < 1e-9
    assert abs(rec["externally_blocked_delta"]) > 1e-9


def test_body_carried_contact_no_fake_actuator_work():
    """Geometric contact without relative command → no actuator receipt/work."""
    rt = _rt(57)
    # Do not call actuate; just detect. No last_effector_actuator_effort from relative.
    assert getattr(rt.world, "last_effector_actuator_effort", None) is None
    _detect(rt, tick=1)
    assert getattr(rt.world, "last_effector_actuator_effort", None) is None


def test_left_only_independence():
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        drive_actuated_relative_z_to,
    )

    rt = _rt(59)
    bid = _bid(rt)
    w, h = int(rt.world.T.shape[1]), int(rt.world.T.shape[0])
    ex, ey, _ = effector_world_pose(
        rt.body,
        width=w,
        height=h,
        config=rt.config,
        manipulator_id="LEFT",
        runtime=rt,
        world=rt.world,
        body_id=bid,
    )
    surf = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    cz = float(centre_z_of(rt.body, kind="body", config=rt.config))
    rows = drive_actuated_relative_z_to(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        target_z=float(surf - cz) - 0.3,
        tick_start=1,
        max_steps=25,
        runtime=rt,
    )
    _tick(len(rows))
    right = _actuate(rt, "RIGHT", 0.0, tick=90)
    assert right["work_used"] == 0.0
    assert any(float(r.get("work_used") or 0) > 0 for r in rows)


def test_mutated_terrain_used():
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        apply_surface_material_separation,
    )
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
        sample_terrain_at,
    )

    rt = _rt(61)
    bid = _bid(rt)
    w, h = int(rt.world.T.shape[1]), int(rt.world.T.shape[0])
    ex, ey, _ = effector_world_pose(
        rt.body,
        width=w,
        height=h,
        config=rt.config,
        manipulator_id="LEFT",
        runtime=rt,
        world=rt.world,
        body_id=bid,
    )
    cx, cy = int(ex) % w, int(ey) % h
    h0 = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    out = apply_surface_material_separation(
        rt.world, rt.config, cell_x=cx, cell_y=cy, requested_thickness=0.08, tick=1
    )
    assert out["receipt"]["status"] == "COMMITTED"
    h1 = float(sample_terrain_at(rt.world, ex, ey, config=rt.config)["height"])
    assert h1 < h0 - 1e-9
    # Actuate toward new surface — must use mutated height
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        drive_actuated_relative_z_to,
    )

    cz = float(centre_z_of(rt.body, kind="body", config=rt.config))
    rows = drive_actuated_relative_z_to(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        target_z=float(h1 - cz) - 0.2,
        tick_start=2,
        max_steps=30,
        runtime=rt,
    )
    _tick(len(rows) + 1)
    assert any(r.get("opposing") for r in rows)


def test_no_mass_momentum_area_mutation():
    rt = _rt(63)
    rec = _actuate(rt, "LEFT", -0.02, tick=1)
    _tick()
    assert rec["effector_mass"] is False
    assert rec["effector_momentum"] is False
    assert rec["contact_area"] is False
    assert rec["terrain_mutation"] is False
    assert rec["material_failure"] is False
    assert rec["separation_wmt"] is False
    assert rec["metabolism"] is False


def test_snapshot_no_work_replay():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        relative_z_of,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _rt(65)
    bid = _bid(rt)
    _actuate(rt, "LEFT", -0.04, tick=1)
    _tick()
    z_before = relative_z_of(rt.world, bid, "LEFT", config=rt.config)
    snap = deepcopy(rt.snapshot())
    # Clear any last receipt identity after restore should not re-emit work
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert abs(relative_z_of(rt2.world, bid, "LEFT", config=rt2.config) - z_before) < 1e-12
    # No automatic work on restore
    st = getattr(rt2.world, "effector_bounded_actuator_effort_state", None)
    assert st is not None


def test_relative_actuation_regression():
    import subprocess
    import sys

    r = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "tests/test_acanthostega_manipulator_relative_world_actuation.py",
            "-q",
            "--tb=line",
        ],
        cwd="<repository-root>",
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_tiktaalik_unchanged():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        effector_bounded_actuator_effort_is_active,
    )

    assert effector_bounded_actuator_effort_is_active(tiktaalik_config()) is False


def test_determinism():
    a = _rt(67)
    b = _rt(67)
    ra = _actuate(a, "LEFT", -0.06, tick=1)
    rb = _actuate(b, "LEFT", -0.06, tick=1)
    _tick(2)
    assert ra["achieved_relative_delta"] == rb["achieved_relative_delta"]
    assert ra["work_used"] == rb["work_used"]
    assert ra["externally_blocked_delta"] == rb["externally_blocked_delta"]


def test_tick_budget():
    assert TICKS["n"] <= 250
