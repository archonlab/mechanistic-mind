"""VW6_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1 — XYZ geometry + occupancy LOS."""
from __future__ import annotations

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _rt(seed: int = 61):
    from mechanistic_mind.model.acanthostega import (
        acanthostega_minimal_vision_3d_geometric_interface_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    cfg = acanthostega_minimal_vision_3d_geometric_interface_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def _set_col(world, x, y, intervals, tick=0):
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import set_volumetric_column

    set_volumetric_column(world, x, y, intervals, tick=tick, reason="vw6_fixture")


def _pose_eye(rt, x, y, z):
    from mechanistic_mind.physical_system.flat_ground_gravity import vertical_half_extent_of

    rt.body.x = float(x)
    rt.body.y = float(y)
    he = float(vertical_half_extent_of(rt.body, kind="body", config=rt.config))
    # sensor_eye_xyz uses centre_z = body.z + half_extent
    rt.body.z = float(z) - he
    rt.body.vz = 0.0
    rt.body.grounded = False


def test_A_B_relative_xyz_and_3d_distance():
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import relative_xyz

    rel_up = relative_xyz(1.0, 1.0, 2.0, 2.0, 1.0, 5.0, width=16, height=16)
    assert abs(rel_up["dx"] - 1.0) < 1e-12
    assert abs(rel_up["dz"] - 3.0) < 1e-12
    assert rel_up["distance_3d"] > rel_up["distance_xy"]
    assert rel_up["elevation_deg"] > 0.0

    rel_dn = relative_xyz(1.0, 1.0, 5.0, 2.0, 1.0, 2.0, width=16, height=16)
    assert rel_dn["dz"] < 0.0
    assert rel_dn["elevation_deg"] < 0.0
    assert abs(rel_dn["distance_3d"] - rel_up["distance_3d"]) < 1e-12


def test_C_xy_wrap_plus_absolute_z():
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import relative_xyz

    # width=8: eye at 0.5, target at 7.5 → wrapped dx = -1 (or +7 shortest is -1)
    rel = relative_xyz(0.5, 0.5, 1.0, 7.5, 0.5, 4.0, width=8, height=8)
    assert abs(abs(rel["dx"]) - 1.0) < 1e-9
    assert abs(rel["dz"] - 3.0) < 1e-12
    assert rel["z_wrap"] is False
    assert rel["xy_wrap"] is True
    assert abs(rel["distance_3d"] - (1.0**2 + 3.0**2) ** 0.5) < 1e-9


def test_D_E_F_G_cavity_and_interval_independence():
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        occupancy_line_of_sight,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval

    rt = _rt(11)
    # Mid column: (0,3] A, free (3,7], (7,10] B
    _set_col(
        rt.world,
        3,
        3,
        [
            OccupiedZInterval(0.0, 3.0, 1.0, (("A", 3.0),)),
            OccupiedZInterval(7.0, 10.0, 1.2, (("B", 3.0),)),
        ],
    )
    # Eye left, target right, ray through free gap z=5
    clear = occupancy_line_of_sight(
        rt.world, 1.5, 3.5, 5.0, 5.5, 3.5, 5.0, config=rt.config
    )
    assert clear["visible"] is True
    assert clear["legacy_max_surface_would_block"] is True  # max surface=10 > ray z=5

    # Ray through upper B at z=8
    up = occupancy_line_of_sight(
        rt.world, 1.5, 3.5, 8.0, 5.5, 3.5, 8.0, config=rt.config
    )
    assert up["occluded"] is True
    assert up["blocker"]["interval"]["z_min"] == 7.0

    # Ray through lower A at z=2
    lo = occupancy_line_of_sight(
        rt.world, 1.5, 3.5, 2.0, 5.5, 3.5, 2.0, config=rt.config
    )
    assert lo["occluded"] is True
    assert lo["blocker"]["interval"]["z_max"] == 3.0


def test_H_nearest_blocker_deterministic():
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        occupancy_line_of_sight,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval

    rt = _rt(12)
    _set_col(rt.world, 2, 2, [OccupiedZInterval(0.0, 4.0, 1.0, (("near", 4.0),))])
    _set_col(rt.world, 4, 2, [OccupiedZInterval(0.0, 4.0, 1.0, (("far", 4.0),))])
    a = occupancy_line_of_sight(rt.world, 0.5, 2.5, 2.0, 5.5, 2.5, 2.0, config=rt.config)
    b = occupancy_line_of_sight(rt.world, 0.5, 2.5, 2.0, 5.5, 2.5, 2.0, config=rt.config)
    assert a["occluded"] and b["occluded"]
    assert a["blocker"]["cell_x"] == 2
    assert a["blocker"] == b["blocker"]


def test_I_J_endpoint_no_false_occlusion():
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        occupancy_line_of_sight,
        sensor_eye_xyz,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval

    rt = _rt(13)
    # Eye cell and target cell occupied only at endpoints; open segment free.
    _set_col(rt.world, 1, 1, [OccupiedZInterval(4.5, 5.5, 1.0, (("eye", 1.0),))])
    _set_col(rt.world, 4, 1, [OccupiedZInterval(4.5, 5.5, 1.0, (("tgt", 1.0),))])
    # Clear mid columns
    for x in (2, 3):
        _set_col(rt.world, x, 1, [])
    _pose_eye(rt, 1.5, 1.5, 5.0)
    eye = sensor_eye_xyz(rt.body, rt.config)
    los = occupancy_line_of_sight(
        rt.world, eye[0], eye[1], eye[2], 4.5, 1.5, 5.0, config=rt.config
    )
    assert los["visible"] is True


def test_K_L_vw3_vw4_visibility_feedback():
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        occupancy_line_of_sight,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
    )

    rt = _rt(14)
    _set_col(rt.world, 3, 3, [OccupiedZInterval(0.0, 6.0, 1.0, (("block", 6.0),))])
    eye = (1.5, 3.5, 3.0)
    tgt = (5.5, 3.5, 3.0)
    before = occupancy_line_of_sight(rt.world, *eye, *tgt, config=rt.config)
    assert before["occluded"] is True

    sep = apply_volumetric_material_separation(
        rt.world,
        rt.config,
        cell_x=3,
        cell_y=3,
        z_remove_lo=0.0,
        z_remove_hi=6.0,
        tick=1,
    )
    assert sep["receipt"]["status"] == "COMMITTED"
    _tick(0)
    after_sep = occupancy_line_of_sight(rt.world, *eye, *tgt, config=rt.config)
    assert after_sep["visible"] is True

    # VW4: reintegrate detached object into path
    objs = list(rt.world.resource_objects or [])
    assert objs
    oid = str(objs[-1].object_id)
    rein = apply_volumetric_material_reintegration(
        rt.world,
        rt.config,
        object_id=oid,
        cell_x=3,
        cell_y=3,
        z_deposit_lo=0.0,
        z_deposit_hi=6.0,
        tick=2,
    )
    assert rein["receipt"]["status"] == "COMMITTED"
    after_rein = occupancy_line_of_sight(rt.world, *eye, *tgt, config=rt.config)
    assert after_rein["occluded"] is True


def test_M_vw5_geometry_agreement():
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        occupancy_probe_geometry_at,
    )
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        occupancy_line_of_sight,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval

    rt = _rt(15)
    _set_col(
        rt.world,
        2,
        2,
        [
            OccupiedZInterval(0.0, 3.0, 1.0, (("lo", 3.0),)),
            OccupiedZInterval(7.0, 10.0, 1.0, (("hi", 3.0),)),
        ],
    )
    geom = occupancy_probe_geometry_at(rt.world, 2.5, 2.5, 5.0, radius=0.0, config=rt.config)
    assert geom["in_contact"] is False
    # Same free volume must be traversable by vision
    los = occupancy_line_of_sight(
        rt.world, 0.5, 2.5, 5.0, 4.5, 2.5, 5.0, config=rt.config
    )
    assert los["visible"] is True


def test_N_O_P_fov_phenotype_no_omniscient_z():
    from mechanistic_mind.physical_system.near_field_exteroception import (
        sample_near_field,
        cognition_exo_fragments,
    )
    from mechanistic_mind.physical_system.observation import (
        accessible_observation,
        FORBIDDEN_TOKENS,
        audit_cognition_payload,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval

    rt = _rt(16)
    _pose_eye(rt, 2.5, 2.5, 5.0)
    _set_col(
        rt.world,
        4,
        2,
        [
            OccupiedZInterval(0.0, 3.0, 1.0, (("lo", 3.0),)),
            OccupiedZInterval(7.0, 10.0, 1.0, (("hi", 3.0),)),
        ],
    )
    nfe = rt.config.near_field_exteroception
    sample = sample_near_field(
        world=rt.world, body=rt.body, cfg=nfe, physical_config=rt.config, diagnostic=True
    )
    assert sample.get("vw6") is not None
    assert "eye_xyz" in sample
    # FOV semantics still present
    assert any("inside_fov" in (r or {}) for r in (sample.get("neighbors") or []))

    exo = cognition_exo_fragments(
        world=rt.world, body=rt.body, cfg=nfe, physical_config=rt.config
    )
    assert all(k.startswith("exo_") for k in exo)
    for tok in (
        "occupancy_los",
        "eye_xyz",
        "target_xyz",
        "elevation_deg",
        "OCCLUDED_BY_OCCUPANCY",
        "VW6_MINIMAL_VISION_3D_GEOMETRIC_INTERFACE_V1",
    ):
        assert tok in FORBIDDEN_TOKENS

    obs = accessible_observation(
        world=rt.world,
        body=rt.body,
        internal=rt.internal,
        planet_config=rt.config.planet,
        body_config=rt.config.body,
        near_field_cfg=nfe,
        physical_config=rt.config,
    )
    audit_cognition_payload(obs)
    blob = " ".join(f"{k}={v}" for k, v in obs.items())
    assert "occupancy_los" not in blob
    assert "target_xyz" not in blob
    assert "elevation_deg" not in blob


def test_Q_R_snapshot_restore_determinism():
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        occupancy_line_of_sight,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        serialize_volumetric_occupancy,
        restore_volumetric_occupancy,
    )

    rt = _rt(17)
    _set_col(
        rt.world,
        3,
        3,
        [
            OccupiedZInterval(0.0, 3.0, 1.0, (("A", 3.0),)),
            OccupiedZInterval(7.0, 10.0, 1.0, (("B", 3.0),)),
        ],
    )
    eye = (1.5, 3.5, 5.0)
    tgt = (5.5, 3.5, 5.0)
    a = occupancy_line_of_sight(rt.world, *eye, *tgt, config=rt.config)
    b = occupancy_line_of_sight(rt.world, *eye, *tgt, config=rt.config)
    assert a == b
    assert a["visible"] is True

    snap = serialize_volumetric_occupancy(rt.world)
    rt2 = _rt(17)
    restore_volumetric_occupancy(rt2.world, snap)
    c = occupancy_line_of_sight(rt2.world, *eye, *tgt, config=rt2.config)
    assert c["visible"] is a["visible"]
    assert c["occluded"] is a["occluded"]
    assert (c.get("blocker") is None) == (a.get("blocker") is None)


def test_S_T_U_V_W_observer_geometry_passivity():
    from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
        observer_vision_3d_inspector_payload,
        ensure_state,
        occupancy_line_of_sight,
        sensor_eye_xyz,
        cell_target_z,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        state_of,
    )
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS

    rt = _rt(18)
    ensure_state(rt.world, rt.config)
    _pose_eye(rt, 1.5, 3.5, 5.0)
    # Clear path; cavity mid-column; target column surface at z=5 for horizontal LOS.
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
    _set_col(rt.world, 5, 3, [OccupiedZInterval(0.0, 5.0, 1.0, (("tgt", 5.0),))])
    dig0 = state_of(rt.world).digest()
    bx0, by0 = float(rt.body.x), float(rt.body.y)
    assert abs(cell_target_z(rt.world, 5, 3, config=rt.config) - 5.0) < 1e-9
    eye = sensor_eye_xyz(rt.body, rt.config)
    assert occupancy_line_of_sight(
        rt.world, eye[0], eye[1], eye[2], 5.5, 3.5, 5.0, config=rt.config
    )["visible"] is True

    payload = observer_vision_3d_inspector_payload(
        rt.world, rt.config, body=rt.body, target_cell=(5, 3)
    )
    assert payload is not None
    live = payload["live"]
    assert live["eye_xyz"] is not None
    assert live["target_xyz"] is not None
    assert "distance_3d" in live
    assert live["occupancy_los"]["visible"] is True
    assert live["occupancy_los"]["legacy_max_surface_would_block"] is True
    # Blocker case
    _set_col(rt.world, 3, 3, [OccupiedZInterval(0.0, 10.0, 1.0, (("solid", 10.0),))])
    blocked = observer_vision_3d_inspector_payload(
        rt.world, rt.config, body=rt.body, target_cell=(5, 3)
    )
    assert blocked["live"]["occupancy_los"]["occluded"] is True
    assert blocked["live"]["occupancy_los"]["blocker"] is not None
    assert blocked["passive"] is True
    # Passivity of inspector itself
    dig1 = state_of(rt.world).digest()
    observer_vision_3d_inspector_payload(rt.world, rt.config, body=rt.body, target_cell=(5, 3))
    assert state_of(rt.world).digest() == dig1
    assert float(rt.body.x) == bx0 and float(rt.body.y) == by0
    assert dig0 != dig1  # fixture changed occupancy; inspector did not
    assert "VW6_VISION_3D_INSPECTION" in FORBIDDEN_TOKENS


def test_z_total_ticks_budget():
    assert TICKS["n"] <= 30
