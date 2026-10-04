"""OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1 — render description from VW1 occupancy."""
from __future__ import annotations

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _rt(seed: int = 71):
    from mechanistic_mind.model.acanthostega import (
        acanthostega_minimal_vision_3d_geometric_interface_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    cfg = acanthostega_minimal_vision_3d_geometric_interface_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def _set_col(world, x, y, intervals, tick=0):
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import set_volumetric_column

    set_volumetric_column(world, x, y, intervals, tick=tick, reason="vw7_fixture")


def test_A_B_C_interval_gap_isolated():
    from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
        build_occupancy_volume_primitives,
        build_observer_volume_render_description,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval

    rt = _rt(1)
    _set_col(
        rt.world,
        4,
        4,
        [
            OccupiedZInterval(0.0, 3.0, 1.0, (("A", 3.0),)),
            OccupiedZInterval(7.0, 10.0, 1.0, (("B", 3.0),)),
        ],
    )
    vols = build_occupancy_volume_primitives(rt.world, config=rt.config)
    cell = [v for v in vols if v["cell_x"] == 4 and v["cell_y"] == 4]
    assert len(cell) == 2
    assert abs(cell[0]["sim_z_min"] - 0.0) < 1e-12 and abs(cell[0]["sim_z_max"] - 3.0) < 1e-12
    assert abs(cell[1]["sim_z_min"] - 7.0) < 1e-12 and abs(cell[1]["sim_z_max"] - 10.0) < 1e-12
    # No solid fill of free gap
    assert not any(v["sim_z_min"] < 3.0 + 1e-9 and v["sim_z_max"] > 7.0 - 1e-9 for v in cell)

    _set_col(
        rt.world,
        5,
        5,
        [
            OccupiedZInterval(0.0, 2.0, 1.0, (("A", 2.0),)),
            OccupiedZInterval(5.0, 6.0, 1.0, (("B", 1.0),)),
            OccupiedZInterval(10.0, 12.0, 1.0, (("C", 2.0),)),
        ],
    )
    vols2 = [v for v in build_occupancy_volume_primitives(rt.world, config=rt.config) if v["cell_x"] == 5 and v["cell_y"] == 5]
    assert len(vols2) == 3
    desc = build_observer_volume_render_description(rt)
    assert desc["available"] is True
    assert desc["heightfield_is_volume_authority"] is False
    assert desc["semantic_cave_object"] is False
    assert desc["drives_organism_vision"] is False


def test_D_E_empty_override_and_material_identity():
    from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
        build_occupancy_volume_primitives,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        occupied_intervals_at,
    )

    rt = _rt(2)
    # Derived PSC may show material; authoritative empty sparse must render none.
    before = occupied_intervals_at(rt.world, 6.5, 6.5)
    assert before  # PSC-derived present before sparse override
    _set_col(rt.world, 6, 6, [])  # authoritative empty
    vols = [v for v in build_occupancy_volume_primitives(rt.world, config=rt.config) if v["cell_x"] == 6 and v["cell_y"] == 6]
    assert vols == []
    _set_col(rt.world, 7, 7, [OccupiedZInterval(1.0, 2.0, 1.1, (("soil_x", 1.0),))])
    v7 = [v for v in build_occupancy_volume_primitives(rt.world, config=rt.config) if v["cell_x"] == 7 and v["cell_y"] == 7][0]
    # Display key may be joined multi-component string; component_id authority is soil_x.
    assert "soil_x" in str(v7.get("material_display_key") or "") or v7["composition"][0]["component_id"] == "soil_x"
    assert v7["composition"][0]["component_id"] == "soil_x"


def test_F_G_H_I_J_body_and_object_xyz_in_cavity():
    from mechanistic_mind.physical_system.flat_ground_gravity import vertical_half_extent_of
    from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
        build_body_render_primitives,
        build_resource_object_render_primitives,
        COORDINATE_TRANSFORM,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval
    from mechanistic_mind.physical_system.resource_objects import ResourceObject, ensure_resource_object_state

    rt = _rt(3)
    _set_col(
        rt.world,
        2,
        2,
        [
            OccupiedZInterval(0.0, 3.0, 1.0, (("lo", 3.0),)),
            OccupiedZInterval(7.0, 10.0, 1.0, (("hi", 3.0),)),
        ],
    )
    he = float(vertical_half_extent_of(rt.body, kind="body", config=rt.config))
    rt.body.x = 2.5
    rt.body.y = 2.5
    rt.body.z = 5.0 - he  # centre_z = 5 inside cavity
    bodies = build_body_render_primitives(rt)
    assert abs(bodies[0]["sim_centre_z"] - 5.0) < 1e-9
    assert bodies[0]["surface_snapped"] is False
    assert bodies[0]["render_center"] == [2.5, 5.0, 2.5]  # x,z,y

    objs = ensure_resource_object_state(rt.world)
    objs.clear()
    objs.append(
        ResourceObject(
            object_id="resource-cavity",
            x=2.5,
            y=2.5,
            mass=1.0,
            quantity=1.0,
            composition=(),
            z=5.0 - 0.25,
            vertical_half_extent=0.25,
            physical_state="FREE_STATIC",
        )
    )
    ro = build_resource_object_render_primitives(rt.world, config=rt.config)
    assert abs(ro[0]["sim_centre_z"] - 5.0) < 1e-9
    assert ro[0]["surface_snapped"] is False
    # Held pose follows authoritative fields
    objs[0].physical_state = "HELD"
    objs[0].holder_body_id = "body-0"
    held = build_resource_object_render_primitives(rt.world, config=rt.config)[0]
    assert held["held"] is True
    assert COORDINATE_TRANSFORM["render_y"] == "simulation_z"


def test_K_L_vw3_vw4_update_render_description():
    from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
        build_occupancy_volume_primitives,
        build_resource_object_render_primitives,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
    )

    rt = _rt(4)
    _set_col(rt.world, 3, 3, [OccupiedZInterval(0.0, 6.0, 1.0, (("block", 6.0),))])
    before = [v for v in build_occupancy_volume_primitives(rt.world, config=rt.config) if v["cell_x"] == 3 and v["cell_y"] == 3]
    assert len(before) == 1
    sep = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=3, cell_y=3, z_remove_lo=0.0, z_remove_hi=6.0, tick=1
    )
    assert sep["receipt"]["status"] == "COMMITTED"
    after = [v for v in build_occupancy_volume_primitives(rt.world, config=rt.config) if v["cell_x"] == 3 and v["cell_y"] == 3]
    assert after == []
    objs = build_resource_object_render_primitives(rt.world, config=rt.config)
    assert any(o["object_id"].startswith("resource-") for o in objs)
    oid = sep["receipt"]["object_id"]
    rein = apply_volumetric_material_reintegration(
        rt.world, rt.config, object_id=oid, cell_x=3, cell_y=3, z_deposit_lo=0.0, z_deposit_hi=6.0, tick=2
    )
    assert rein["receipt"]["status"] == "COMMITTED"
    restored = [v for v in build_occupancy_volume_primitives(rt.world, config=rt.config) if v["cell_x"] == 3 and v["cell_y"] == 3]
    assert len(restored) == 1
    assert abs(restored[0]["sim_z_max"] - 6.0) < 1e-9


def test_M_N_vw5_vw6_agreement():
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        occupancy_probe_geometry_at,
    )
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        occupancy_line_of_sight,
    )
    from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
        build_occupancy_volume_primitives,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval

    rt = _rt(5)
    for x in (1, 2, 4):
        _set_col(rt.world, x, 3, [])
    _set_col(
        rt.world,
        3,
        3,
        [
            OccupiedZInterval(0.0, 3.0, 1.0, (("A", 3.0),)),
            OccupiedZInterval(7.0, 10.0, 1.0, (("B", 3.0),)),
        ],
    )
    geom = occupancy_probe_geometry_at(rt.world, 3.5, 3.5, 5.0, radius=0.0, config=rt.config)
    assert geom["in_contact"] is False
    vols = [v for v in build_occupancy_volume_primitives(rt.world, config=rt.config) if v["cell_x"] == 3 and v["cell_y"] == 3]
    assert not any(v["sim_z_min"] < 5.0 < v["sim_z_max"] or (v["sim_z_min"] < 5.0 <= v["sim_z_max"]) for v in vols)
    # gap (3,7] empty in render
    assert all(not (v["sim_z_min"] < 5.0 <= v["sim_z_max"]) for v in vols)

    los = occupancy_line_of_sight(rt.world, 1.5, 3.5, 5.0, 5.5, 3.5, 5.0, config=rt.config)
    assert los["visible"] is True
    # Blocker case
    _set_col(rt.world, 3, 3, [OccupiedZInterval(0.0, 10.0, 1.0, (("solid", 10.0),))])
    los2 = occupancy_line_of_sight(rt.world, 1.5, 3.5, 5.0, 5.5, 3.5, 5.0, config=rt.config)
    assert los2["occluded"] is True
    b = los2["blocker"]["interval"]
    vols2 = [v for v in build_occupancy_volume_primitives(rt.world, config=rt.config) if v["cell_x"] == 3 and v["cell_y"] == 3][0]
    assert abs(vols2["sim_z_min"] - b["z_min"]) < 1e-12
    assert abs(vols2["sim_z_max"] - b["z_max"]) < 1e-12


def test_O_P_Q_R_S_T_snapshot_determinism_passivity_old_session():
    from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
        build_observer_volume_render_description,
        COORDINATE_TRANSFORM,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        serialize_volumetric_occupancy,
        restore_volumetric_occupancy,
        state_of,
    )
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS
    from mechanistic_mind.model.acanthostega import acanthostega_gentle_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _rt(6)
    _set_col(rt.world, 1, 1, [OccupiedZInterval(0.0, 2.0, 1.0, (("m", 2.0),))])
    a = build_observer_volume_render_description(rt)
    b = build_observer_volume_render_description(rt)
    assert a["occupancy_volumes"] == b["occupancy_volumes"]
    assert a["coordinate_transform"] == COORDINATE_TRANSFORM
    snap = serialize_volumetric_occupancy(rt.world)
    dig = state_of(rt.world).digest()
    # Camera "move" is frontend-only — backend description unchanged
    c = build_observer_volume_render_description(rt)
    assert state_of(rt.world).digest() == dig
    assert c["occupancy_digest"] == dig

    rt2 = _rt(6)
    restore_volumetric_occupancy(rt2.world, snap)
    d = build_observer_volume_render_description(rt2)
    assert d["occupancy_volumes"] == a["occupancy_volumes"]

    # Old / non-VW session: unavailable, no fabricated volume
    legacy = PhysicalSystemRuntime(seed=9, config=acanthostega_gentle_config())
    legacy.config.cognition.cognition_enabled = False
    legacy_desc = build_observer_volume_render_description(legacy)
    assert legacy_desc["available"] is False
    assert legacy_desc["occupancy_volumes"] == []

    assert "OBSERVER_CAMERA_OCCUPANCY_CONSUMER_V1" in FORBIDDEN_TOKENS
    assert "OCCUPIED_INTERVAL_PRISM" in FORBIDDEN_TOKENS


def test_z_ticks():
    assert TICKS["n"] <= 30
