"""Held ResourceObject ↔ terrain mechanical transmission V1."""
from __future__ import annotations

from copy import deepcopy

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_held_resource_object_terrain_mechanical_transmission_config,
    )

    cfg = acanthostega_held_resource_object_terrain_mechanical_transmission_config()
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


def _grasp_nearest(rt):
    from mechanistic_mind.physical_system.physical_manipulator import (
        MANIP_GRASP,
        apply_bilateral_grasp_release_for_holder,
        update_held_kinematics,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        snap_held_vertical_from_holders,
    )
    from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_FREE_STATIC
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
    )

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
    objs = [
        o
        for o in (rt.world.resource_objects or [])
        if str(getattr(o, "physical_state", "")) == PHYSICAL_STATE_FREE_STATIC
    ]
    assert objs, "need free objects"
    objs.sort(key=lambda o: (float(o.x) - ex) ** 2 + (float(o.y) - ey) ** 2)
    obj = objs[0]
    obj.x = float(ex)
    obj.y = float(ey)
    from mechanistic_mind.physical_system.flat_ground_gravity import read_z

    obj.z = float(read_z(rt.body))
    apply_bilateral_grasp_release_for_holder(
        world=rt.world,
        body=rt.body,
        config=rt.config,
        body_id=bid,
        commands={"LEFT": MANIP_GRASP, "RIGHT": "NONE"},
        tick=1,
        runtime=rt,
    )
    holders = _holders(rt)
    update_held_kinematics(rt.world, holders)
    snap_held_vertical_from_holders(rt.world, holders, rt.config)
    _tick()
    held = [
        o
        for o in (rt.world.resource_objects or [])
        if str(getattr(o, "physical_state", "")) == "HELD"
        and str(getattr(o, "holder_body_id", "") or "") == bid
        and str(getattr(o, "manipulator_id", "") or "") == "LEFT"
    ]
    assert held, "grasp failed"
    return held[0]


def _force_held_near_terrain(rt, obj, *, penetration: float = 0.05):
    """Drive relative_z so held lower support sits at/into terrain under effector xy."""
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        effector_world_pose,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        read_z,
        snap_held_vertical_from_holders,
    )
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        drive_relative_z_to,
        relative_z_of,
    )
    from mechanistic_mind.physical_system.physical_manipulator import update_held_kinematics

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
    body_z = float(read_z(rt.body))
    target_rel = float(surf - body_z - float(penetration))
    drive_relative_z_to(
        rt.world,
        config=rt.config,
        body_id=bid,
        effector_id="LEFT",
        target_z=target_rel,
        tick_start=10,
        max_steps=64,
    )
    update_held_kinematics(rt.world, _holders(rt))
    snap_held_vertical_from_holders(rt.world, _holders(rt), rt.config)
    # May not fully reach if tip/held blocked mid-drive — assert contact-ish.
    z = float(relative_z_of(rt.world, bid, "LEFT", config=rt.config))
    held_z = float(body_z + z)
    assert held_z <= float(surf) + 1e-6, (held_z, surf, z, target_rel)
    return surf, z


def test_preset_on_off_chain():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY,
        PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION,
        acanthostega_held_resource_object_terrain_contact_geometry_config,
        acanthostega_held_resource_object_terrain_mechanical_transmission_config,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        held_resource_object_terrain_mechanical_transmission_is_active,
    )
    from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
        held_resource_object_terrain_contact_geometry_is_active,
    )

    child = acanthostega_held_resource_object_terrain_mechanical_transmission_config()
    parent = acanthostega_held_resource_object_terrain_contact_geometry_config()
    assert child.public_preset == PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
    assert parent.public_preset == PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY
    assert held_resource_object_terrain_mechanical_transmission_is_active(child) is True
    assert held_resource_object_terrain_mechanical_transmission_is_active(parent) is False
    assert held_resource_object_terrain_mechanical_transmission_is_active(tiktaalik_config()) is False
    assert held_resource_object_terrain_contact_geometry_is_active(child) is True


def test_empty_hand_no_held_constraint_work():
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        request_actuated_relative_displacement,
    )
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        default_external_constraints,
    )
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        CONSTRAINT_KIND,
    )

    rt = _rt(19)
    bid = _bid(rt)
    cons = default_external_constraints(rt.config)
    kinds = [type(c).__name__ for c in cons]
    assert "HeldObjectTerrainRelativeZConstraint" in kinds
    rec = request_actuated_relative_displacement(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        requested_delta_z=-0.05,
        tick=1,
        runtime=rt,
    )
    _tick()
    # Empty hand: tip may or may not block; held kind must not win.
    assert rec.get("external_constraint") != CONSTRAINT_KIND or not rec.get("opposing")
    tx = getattr(rt.world, "last_held_resource_object_terrain_mechanical_transmission", None)
    if isinstance(tx, dict):
        assert float(tx.get("work_transmitted_to_terrain") or 0.0) == 0.0


def test_held_terrain_block_transmits_actuator_work():
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        request_actuated_relative_displacement,
        DEFAULT_MAX_WORK_PER_TICK,
    )
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        CONSTRAINT_KIND,
    )
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        state_of as setmr_state,
    )

    rt = _rt(17)
    obj = _grasp_nearest(rt)
    _force_held_near_terrain(rt, obj, penetration=0.02)
    bid = _bid(rt)

    # Attempt further lowering — held constraint should win before tip.
    rec = request_actuated_relative_displacement(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        requested_delta_z=-0.1,
        tick=2,
        runtime=rt,
    )
    _tick()
    assert rec.get("external_constraint") == CONSTRAINT_KIND
    assert rec.get("opposing") is True
    work = float(rec.get("work_used") or 0.0)
    assert work > 1e-15
    assert work <= float(DEFAULT_MAX_WORK_PER_TICK) + 1e-12
    assert abs(float(rec.get("work_transmitted_to_terrain") or 0.0) - work) < 1e-12
    assert abs(float(rec.get("work_partition_residual") or 0.0)) < 1e-12
    assert rec.get("held_terrain_transmission", {}).get("setmr_routed") is False

    tx = rt.world.last_held_resource_object_terrain_mechanical_transmission
    assert tx["setmr_routed"] is False
    assert tx["terrain_failure_coupling"] is False
    assert tx["wmt_invoked"] is False
    assert abs(float(tx["work_transmitted_to_terrain"]) - work) < 1e-12

    # SETMR must not consume held-kind work in this slice.
    st = setmr_state(rt.world)
    if st is not None and st.last_step is not None:
        assert str(st.last_step.get("external_constraint") or "") != CONSTRAINT_KIND or float(
            st.last_step.get("fracture_work_applied") or 0.0
        ) == 0.0


def test_no_double_debit_one_compose_winner():
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        request_actuated_relative_displacement,
        state_of as ebae_state,
    )

    rt = _rt(23)
    obj = _grasp_nearest(rt)
    _force_held_near_terrain(rt, obj, penetration=0.03)
    bid = _bid(rt)
    before = dict(ebae_state(rt.world).counters)
    rec = request_actuated_relative_displacement(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        requested_delta_z=-0.08,
        tick=3,
        runtime=rt,
    )
    _tick()
    after = dict(ebae_state(rt.world).counters)
    assert int(after.get("work_events", 0)) - int(before.get("work_events", 0)) <= 1
    assert float(rec.get("work_used") or 0.0) >= 0.0


def test_serialize_restore_roundtrip():
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        restore_state,
        serialize_state,
        state_of,
    )
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        request_actuated_relative_displacement,
    )

    rt = _rt(29)
    obj = _grasp_nearest(rt)
    _force_held_near_terrain(rt, obj, penetration=0.01)
    bid = _bid(rt)
    request_actuated_relative_displacement(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        requested_delta_z=-0.05,
        tick=4,
        runtime=rt,
    )
    st = state_of(rt.world)
    assert st is not None and st.last_step is not None
    data = deepcopy(serialize_state(st))
    rt2 = _rt(29)
    restore_state(rt2.world, data, rt2.config)
    st2 = state_of(rt2.world)
    assert st2 is not None
    assert st2.last_step is not None
    assert abs(
        float(st2.last_step.get("work_transmitted_to_terrain") or 0.0)
        - float(st.last_step.get("work_transmitted_to_terrain") or 0.0)
    ) < 1e-12


def test_canonical_normalize_and_map():
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION,
        normalize_preset_name,
        preset_canonical,
    )

    assert (
        normalize_preset_name("Acanthostega Beta 4 Held Object Terrain Mechanical Transmission")
        == PRESET_ACANTHOSTEGA_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
    )
    assert (
        normalize_preset_name(PRESET_ACANTHOSTEGA_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION)
        == PRESET_ACANTHOSTEGA_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION)
    assert canon["builder"] == "acanthostega_held_resource_object_terrain_mechanical_transmission_config"
    assert canon["mechanisms"]["held_resource_object_terrain_mechanical_transmission"] is True
    assert canon["mechanisms"]["held_resource_object_terrain_contact_geometry"] is True
