"""Held-mediated surface exertion → existing SETMR / WMT integration V1."""
from __future__ import annotations

from copy import deepcopy

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_held_mediated_surface_exertion_integration_config,
    )

    cfg = acanthostega_held_mediated_surface_exertion_integration_config()
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
        read_z,
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
    assert objs
    objs.sort(key=lambda o: (float(o.x) - ex) ** 2 + (float(o.y) - ey) ** 2)
    obj = objs[0]
    obj.x = float(ex)
    obj.y = float(ey)
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
    assert held
    return held[0]


def _force_held_near_terrain(rt, *, penetration: float = 0.02):
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
    z = float(relative_z_of(rt.world, bid, "LEFT", config=rt.config))
    assert float(body_z + z) <= float(surf) + 1e-6
    return surf, z, ex, ey


def test_preset_on_off_chain():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION,
        PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION,
        acanthostega_held_mediated_surface_exertion_integration_config,
        acanthostega_held_resource_object_terrain_mechanical_transmission_config,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
        held_mediated_surface_exertion_integration_is_active,
    )
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        held_resource_object_terrain_mechanical_transmission_is_active,
    )

    child = acanthostega_held_mediated_surface_exertion_integration_config()
    parent = acanthostega_held_resource_object_terrain_mechanical_transmission_config()
    assert child.public_preset == PUBLIC_PRESET_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
    assert parent.public_preset == PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_MECHANICAL_TRANSMISSION
    assert held_mediated_surface_exertion_integration_is_active(child) is True
    assert held_mediated_surface_exertion_integration_is_active(parent) is False
    assert held_mediated_surface_exertion_integration_is_active(tiktaalik_config()) is False
    assert held_resource_object_terrain_mechanical_transmission_is_active(child) is True


def test_parent_transmission_still_blocks_setmr_without_integration():
    """Transmission-only preset must not feed SETMR (slice B lock)."""
    from mechanistic_mind.model.acanthostega import (
        acanthostega_held_resource_object_terrain_mechanical_transmission_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        request_actuated_relative_displacement,
    )
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        CONSTRAINT_KIND,
    )
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        state_of as setmr_state,
    )

    cfg = acanthostega_held_resource_object_terrain_mechanical_transmission_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    _grasp_nearest(rt)
    _force_held_near_terrain(rt, penetration=0.02)
    bid = _bid(rt)
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
    assert float(rec.get("work_used") or 0.0) > 1e-15
    assert float(rec.get("work_transmitted_to_terrain") or 0.0) > 1e-15
    st = setmr_state(rt.world)
    # SETMR may run but held kind must remain ineligible without integration.
    if st is not None and st.last_step is not None:
        assert float(st.last_step.get("eligible_work") or 0.0) == 0.0 or st.last_step.get(
            "exertion_source_kind"
        ) != "held_resource_object_mediated"


def test_held_transmitted_feeds_same_setmr_accumulator():
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        request_actuated_relative_displacement,
    )
    from mechanistic_mind.physical_system.held_resource_object_terrain_mechanical_transmission import (
        CONSTRAINT_KIND,
    )
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        state_of as col_state,
        wrap_cell,
    )
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        state_of as setmr_state,
    )

    rt = _rt(17)
    _grasp_nearest(rt)
    surf, _, ex, ey = _force_held_near_terrain(rt, penetration=0.02)
    del surf
    bid = _bid(rt)
    cx, cy = wrap_cell(col_state(rt.world), ex, ey)
    key = f"{int(cx)}|{int(cy)}"
    st0 = setmr_state(rt.world)
    before = float((st0.fracture_work if st0 else {}).get(key, 0.0))

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
    work = float(rec.get("work_transmitted_to_terrain") or 0.0)
    assert work > 1e-15

    st = setmr_state(rt.world)
    assert st is not None and st.last_step is not None
    assert st.last_step.get("exertion_source_kind") == "held_resource_object_mediated"
    assert float(st.last_step.get("eligible_work") or 0.0) > 1e-15
    assert abs(float(st.last_step.get("eligible_work") or 0.0) - work) < 1e-12
    after = float(st.fracture_work.get(key, 0.0))
    assert after >= before + work - 1e-12
    # Same failure gate / WMT path (may SUBTHRESHOLD or invoke WMT).
    assert st.last_step.get("status") in {
        "SUBTHRESHOLD",
        "FAILURE",
        "WMT_REJECTED",
        "COMMITTED",
        "SURFACE_MATERIAL_FAILURE",
    } or bool(st.last_step.get("fracture_work_applied"))

    integ = rt.world.last_held_mediated_surface_exertion_integration
    assert integ["setmr_routed"] is True
    assert integ["same_accumulator"] is True
    assert integ["held_specific_removal_path"] is False

    tx = rt.world.last_held_resource_object_terrain_mechanical_transmission
    assert tx["setmr_routed"] is True


def test_no_second_accumulator_or_tool_bonus():
    from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
        catalog_item,
    )

    item = catalog_item(enabled=True)
    assert item["duplicate_accumulator"] is False
    assert item["routes_to_setmr"] is True


def test_canonical_normalize():
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION,
        normalize_preset_name,
        preset_canonical,
    )

    assert (
        normalize_preset_name("Acanthostega Beta 4 Held-Mediated Surface Exertion Integration")
        == PRESET_ACANTHOSTEGA_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION)
    assert canon["builder"] == "acanthostega_held_mediated_surface_exertion_integration_config"
    assert canon["mechanisms"]["held_mediated_surface_exertion_integration"] is True
    assert canon["mechanisms"]["held_resource_object_terrain_mechanical_transmission"] is True
    assert canon["mechanisms"]["surface_exertion_terrain_material_resistance"] is True


def test_serialize_restore_roundtrip():
    from mechanistic_mind.physical_system.held_mediated_surface_exertion_integration import (
        restore_state,
        serialize_state,
        state_of,
    )
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        request_actuated_relative_displacement,
    )

    rt = _rt(29)
    _grasp_nearest(rt)
    _force_held_near_terrain(rt, penetration=0.01)
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
