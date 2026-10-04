"""Held ResourceObject ↔ terrain contact geometry — fact only."""
from __future__ import annotations

from copy import deepcopy

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_held_resource_object_terrain_contact_geometry_config,
    )

    cfg = acanthostega_held_resource_object_terrain_contact_geometry_config()
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
    from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
        detect_held_resource_object_terrain_contacts,
    )

    step = detect_held_resource_object_terrain_contacts(
        rt.world, _holders(rt), tick=tick, config=rt.config
    )
    _tick()
    return step


def _grasp_nearest(rt):
    """Force GRASP on LEFT for first free object near effector."""
    from mechanistic_mind.physical_system.physical_manipulator import (
        MANIP_GRASP,
        apply_bilateral_grasp_release_for_holder,
        update_held_kinematics,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        snap_held_vertical_from_holders,
    )
    from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_FREE_STATIC

    # Place a free object at LEFT effector
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
    objs = list(rt.world.resource_objects or [])
    assert objs, "expected spawn objects"
    obj = objs[0]
    obj.physical_state = PHYSICAL_STATE_FREE_STATIC
    obj.holder_body_id = None
    obj.manipulator_id = None
    obj.x = float(ex)
    obj.y = float(ey)
    obj.z = float(rt.body.z)
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
    return obj


def _force_held_terrain_contact(rt, obj):
    """Authoritative lower-support z below CSG height → sphere contacts terrain.

    Uses real object.z (not optical/glyph). Does not mutate terrain or collision_radius.
    """
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        evaluate_probe_contact,
        sample_terrain_at,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        ensure_object_collision_radius,
    )

    h = float(sample_terrain_at(rt.world, obj.x, obj.y, config=rt.config)["height"])
    # Lower support slightly below surface → clearance = z - h < 0
    obj.z = float(h) - 0.02
    r = float(ensure_object_collision_radius(obj))
    cz = float(centre_z_of(obj, kind="object", config=rt.config))
    m = evaluate_probe_contact(
        rt.world, x=obj.x, y=obj.y, z=cz, radius=r, epsilon=1e-9, config=rt.config
    )
    assert m["in_contact"], (m.get("clearance"), h, obj.z, cz, r)
    return obj


def test_preset_on_off_chain():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY,
        PUBLIC_PRESET_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE,
        acanthostega_held_resource_object_terrain_contact_geometry_config,
        acanthostega_surface_exertion_terrain_material_resistance_config,
        acanthostega_coherent_slope_dynamics_config,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
        held_resource_object_terrain_contact_geometry_is_active,
    )
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        surface_exertion_terrain_material_resistance_is_active,
    )

    child = acanthostega_held_resource_object_terrain_contact_geometry_config()
    parent = acanthostega_surface_exertion_terrain_material_resistance_config()
    phase_c = acanthostega_coherent_slope_dynamics_config()
    assert child.public_preset == PUBLIC_PRESET_HELD_RESOURCE_OBJECT_TERRAIN_CONTACT_GEOMETRY
    assert parent.public_preset == PUBLIC_PRESET_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE
    assert held_resource_object_terrain_contact_geometry_is_active(child) is True
    assert held_resource_object_terrain_contact_geometry_is_active(parent) is False
    assert held_resource_object_terrain_contact_geometry_is_active(phase_c) is False
    assert held_resource_object_terrain_contact_geometry_is_active(tiktaalik_config()) is False
    assert surface_exertion_terrain_material_resistance_is_active(child) is True


def test_held_above_no_contact():
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        request_relative_effector_displacement,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        snap_held_vertical_from_holders,
    )
    from mechanistic_mind.physical_system.physical_manipulator import update_held_kinematics
    from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
        PHASE_BEGIN,
    )

    rt = _rt(91)
    obj = _grasp_nearest(rt)
    # Lift hand so object clears flat ground (sphere radius 0.25)
    bid = _bid(rt)
    for i in range(8):
        request_relative_effector_displacement(
            rt.world,
            config=rt.config,
            body_id=bid,
            effector_id="LEFT",
            requested_delta_z=0.1,
            tick=10 + i,
        )
    holders = _holders(rt)
    update_held_kinematics(rt.world, holders)
    snap_held_vertical_from_holders(rt.world, holders, rt.config)
    assert float(obj.z) > 0.2
    s = _detect(rt, tick=20)
    assert not any(r["phase"] == PHASE_BEGIN and r["object_id"] == obj.object_id for r in s["receipts"])


def test_endpoint_begin_persist_end():
    from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
        PHASE_BEGIN,
        PHASE_END,
        PHASE_PERSIST,
    )
    from mechanistic_mind.physical_system.manipulator_relative_world_actuation import (
        request_relative_effector_displacement,
        drive_relative_z_to,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import (
        snap_held_vertical_from_holders,
    )
    from mechanistic_mind.physical_system.physical_manipulator import update_held_kinematics

    rt = _rt(93)
    obj = _grasp_nearest(rt)
    # First detect while resting on flat → BEGIN (clearance ~0)
    s0 = _detect(rt, tick=1)
    assert any(r["phase"] == PHASE_BEGIN and r["object_id"] == obj.object_id for r in s0["receipts"])
    # Persist
    s1 = _detect(rt, tick=2)
    assert any(r["phase"] == PHASE_PERSIST and r["object_id"] == obj.object_id for r in s1["receipts"])
    # Lift away
    bid = _bid(rt)
    drive_relative_z_to(
        rt.world,
        config=rt.config,
        body_id=bid,
        effector_id="LEFT",
        target_z=0.8,
        tick_start=3,
        max_steps=20,
    )
    holders = _holders(rt)
    update_held_kinematics(rt.world, holders)
    snap_held_vertical_from_holders(rt.world, holders, rt.config)
    s2 = _detect(rt, tick=30)
    assert any(r["phase"] == PHASE_END and r["object_id"] == obj.object_id for r in s2["receipts"])


def test_grasp_snap_no_fake_swept():
    from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
        DETECTION_SWEPT,
        PHASE_BEGIN,
        state_of,
    )

    rt = _rt(95)
    obj = _grasp_nearest(rt)
    s = _detect(rt, tick=1)
    begins = [r for r in s["receipts"] if r["phase"] == PHASE_BEGIN and r["object_id"] == obj.object_id]
    assert begins
    # First contact after grasp must be endpoint (no prior STABLE_HELD pose)
    assert begins[0]["detection_mode"] != DETECTION_SWEPT
    assert begins[0].get("transition_policy") in (
        "NO_PREVIOUS_HELD_POSE",
        "GRASP_SNAP",
        None,
    ) or begins[0]["detection_mode"] == "ENDPOINT_OVERLAP"
    st = state_of(rt.world)
    assert int(st.counters.get("grasp_snap_endpoint_only", 0)) >= 1


def test_non_effect_invariants():
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        resolved_column_at,
    )

    rt = _rt(97)
    obj = _grasp_nearest(rt)
    ox, oy, oz = float(obj.x), float(obj.y), float(obj.z)
    bx, by, bz = float(rt.body.x), float(rt.body.y), float(rt.body.z)
    elev0 = float(resolved_column_at(rt.world, ox, oy)["surface_elevation"])
    n0 = len(list(rt.world.resource_objects or []))
    s = _detect(rt, tick=1)
    assert s["work_transmission"] is False
    assert s["material_failure"] is False
    assert s["wmt_invoked"] is False
    assert s["impulse_transferred"] is False
    assert s["sound_emitted"] is False
    assert s["automatic_release"] is False
    assert abs(float(obj.x) - ox) < 1e-12
    assert abs(float(obj.y) - oy) < 1e-12
    assert abs(float(obj.z) - oz) < 1e-12
    assert abs(float(rt.body.x) - bx) < 1e-12
    assert abs(float(rt.body.z) - bz) < 1e-12
    elev1 = float(resolved_column_at(rt.world, ox, oy)["surface_elevation"])
    assert abs(elev1 - elev0) < 1e-12
    assert len(list(rt.world.resource_objects or [])) == n0


def test_optical_radius_irrelevant():
    rt = _rt(99)
    obj = _grasp_nearest(rt)
    _force_held_terrain_contact(rt, obj)
    obj.optical_radius = 9.0
    s0 = _detect(rt, tick=1)
    n0 = s0["n_begin"] + s0["n_persist"]
    obj.optical_radius = 0.01
    s1 = _detect(rt, tick=2)
    n1 = s1["n_begin"] + s1["n_persist"]
    # Still in contact either way (optical unused)
    assert n0 >= 1 and n1 >= 1


def test_release_ends_episode():
    from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
        END_OBJECT_RELEASED,
        PHASE_BEGIN,
        PHASE_END,
    )
    from mechanistic_mind.physical_system.physical_manipulator import (
        MANIP_RELEASE,
        apply_bilateral_grasp_release_for_holder,
    )

    rt = _rt(101)
    obj = _grasp_nearest(rt)
    _force_held_terrain_contact(rt, obj)
    s0 = _detect(rt, tick=1)
    assert any(r["phase"] == PHASE_BEGIN for r in s0["receipts"])
    apply_bilateral_grasp_release_for_holder(
        world=rt.world,
        body=rt.body,
        config=rt.config,
        body_id=_bid(rt),
        commands={"LEFT": MANIP_RELEASE, "RIGHT": "NONE"},
        tick=2,
        runtime=rt,
    )
    s1 = _detect(rt, tick=2)
    ends = [r for r in s1["receipts"] if r["phase"] == PHASE_END]
    assert ends
    assert ends[0]["end_reason"] == END_OBJECT_RELEASED


def test_snapshot_no_duplicate_begin():
    """Mechanism-state round-trip (HFC pattern).

    Full PhysicalSystemRuntime.restore sanitizes HELD via technical_id (agent_0)
    while grasp uses body-0 — pre-existing single-agent restore quirk. HOTC
    parity is proven by serialize_state/restore_state on a world that still
    holds the object.
    """
    from mechanistic_mind.physical_system.held_resource_object_terrain_contact_geometry import (
        PHASE_BEGIN,
        PHASE_PERSIST,
        restore_state,
        serialize_state,
        state_of,
    )

    rt = _rt(103)
    obj = _grasp_nearest(rt)
    _force_held_terrain_contact(rt, obj)
    _detect(rt, tick=1)
    _detect(rt, tick=2)
    st = state_of(rt.world)
    assert obj.object_id in st.active
    data = deepcopy(serialize_state(st))

    rt2 = _rt(103)
    obj2 = _grasp_nearest(rt2)
    _force_held_terrain_contact(rt2, obj2)
    assert obj2.object_id == obj.object_id
    restore_state(rt2.world, data, rt2.config)
    s = _detect(rt2, tick=3)
    assert any(r["phase"] == PHASE_PERSIST and r["object_id"] == obj.object_id for r in s["receipts"])
    assert not any(r["phase"] == PHASE_BEGIN and r["object_id"] == obj.object_id for r in s["receipts"])


def test_cognition_privacy():
    rt = _rt(105)
    _grasp_nearest(rt)
    _detect(rt, tick=1)
    acts = list(rt.cognition.get("available_actions") or [])
    for forbidden in ("DIG", "EXCAVATE", "TOOL", "MINE"):
        assert forbidden not in acts
    # Contact receipts not injected into cognition observation
    obs = getattr(rt, "last_observation", None) or {}
    blob = str(obs)
    assert "HELD_RESOURCE_OBJECT_TERRAIN_CONTACT" not in blob
    assert "hotc-" not in blob


def test_tick_budget():
    assert TICKS["n"] <= 300
