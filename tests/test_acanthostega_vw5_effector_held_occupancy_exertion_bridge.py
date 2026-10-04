"""VW5_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1 — occupancy clearance/contact → VW3."""
from __future__ import annotations

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _rt(seed: int = 91):
    from mechanistic_mind.model.acanthostega import (
        acanthostega_effector_held_occupancy_exertion_bridge_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    cfg = acanthostega_effector_held_occupancy_exertion_bridge_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def _bid(rt) -> str:
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

    return body_refs_for_runtime(rt)[0][0]


def _set_cavity(world, x, y, *, lower=(0.0, 4.0), upper=(8.0, 10.0), dens_lo=1.0, dens_hi=1.2):
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        set_volumetric_column,
    )

    lo0, lo1 = lower
    up0, up1 = upper
    set_volumetric_column(
        world,
        x,
        y,
        [
            OccupiedZInterval(lo0, lo1, dens_lo, (("soil_a", lo1 - lo0),)),
            OccupiedZInterval(up0, up1, dens_hi, (("soil_b", up1 - up0),)),
        ],
        tick=0,
        reason="vw5_cavity_fixture",
    )


def _pose(rt, mid="LEFT"):
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import effector_world_pose

    w, h = int(rt.world.T.shape[1]), int(rt.world.T.shape[0])
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


def test_A_B_cavity_clearance_no_false_heightfield_contact():
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        occupancy_probe_geometry_at,
    )
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import clearance_at
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        compatibility_surface_elevation,
    )

    rt = _rt(11)
    cx, cy = int(rt.body.x), int(rt.body.y)
    _set_cavity(rt.world, cx, cy)
    # Probe inside cavity free space
    z_free = 6.0
    geom = occupancy_probe_geometry_at(rt.world, cx + 0.5, cy + 0.5, z_free, radius=0.0, config=rt.config)
    assert geom["in_contact"] is False
    assert abs(float(geom["boundary_z"]) - 4.0) < 1e-9
    assert float(geom["clearance"]) > 0.0
    legacy = compatibility_surface_elevation(rt.world, cx + 0.5, cy + 0.5)
    assert legacy is not None and abs(float(legacy) - 10.0) < 1e-9
    # Legacy max surface would claim contact (z - legacy < 0); VW5 must not.
    assert float(z_free) - float(legacy) < 0.0
    assert geom["false_heightfield_contact_prevented"] is True
    clr = clearance_at(rt.world, cx + 0.5, cy + 0.5, z_free, radius=0.0, config=rt.config)
    assert float(clr["clearance"]) > 0.0


def test_C_D_E_F_interval_contact_and_no_telekinetic():
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        contacted_occupancy_material_info,
        occupancy_probe_geometry_at,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval, set_volumetric_column

    rt = _rt(12)
    set_volumetric_column(
        rt.world,
        3,
        3,
        [
            OccupiedZInterval(0.0, 3.0, 1.0, (("mat_a", 3.0),)),
            OccupiedZInterval(7.0, 9.0, 1.5, (("mat_b", 2.0),)),
        ],
        tick=0,
        reason="vw5_multi",
    )
    # Lower contact
    g_lo = occupancy_probe_geometry_at(rt.world, 3.5, 3.5, 3.0, radius=0.0, config=rt.config)
    assert g_lo["in_contact"] is True
    assert abs(float(g_lo["boundary_z"]) - 3.0) < 1e-9
    mat_lo = contacted_occupancy_material_info(
        rt.world, [3.5, 3.5, float(g_lo["boundary_z"])], config=rt.config
    )
    assert mat_lo is not None
    assert mat_lo["composition"][0]["component_id"] == "mat_a"

    # Upper contact (probe at upper top)
    g_hi = occupancy_probe_geometry_at(rt.world, 3.5, 3.5, 9.0, radius=0.0, config=rt.config)
    assert g_hi["in_contact"] is True
    assert abs(float(g_hi["boundary_z"]) - 9.0) < 1e-9
    mat_hi = contacted_occupancy_material_info(
        rt.world, [3.5, 3.5, float(g_hi["boundary_z"])], config=rt.config
    )
    assert mat_hi["composition"][0]["component_id"] == "mat_b"

    # Free mid — no contact
    g_free = occupancy_probe_geometry_at(rt.world, 3.5, 3.5, 5.0, radius=0.0, config=rt.config)
    assert g_free["in_contact"] is False
    assert float(g_free["clearance"]) > 0.0


def test_G_H_I_J_K_physical_separation_bridge_critical():
    """Organism actuated path → contact → work → VW3. No direct researcher VW3 call."""
    from mechanistic_mind.physical_system.effector_bounded_actuator_effort import (
        drive_actuated_relative_z_to,
        request_actuated_relative_displacement,
    )
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        occupancy_probe_geometry_at,
        state_of as vw5_state,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import centre_z_of
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )
    from mechanistic_mind.physical_system.passive_material_properties import (
        SEPARATION_WORK_PER_QUANTITY_V1,
    )
    from mechanistic_mind.physical_system.surface_exertion_terrain_material_resistance import (
        researcher_set_cell_resistance_override,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        occupied_intervals_at,
        occupancy_at,
        wrap_cell,
        state_of as vo_state,
    )

    rt = _rt(13)
    bid = _bid(rt)
    # Authoritative interaction XY is the effector tip cell (not body floor).
    ex, ey, _ez = _pose(rt, "LEFT")
    st_vo = vo_state(rt.world)
    cell = wrap_cell(st_vo, int(ex), int(ey))
    cx, cy = int(cell[0]), int(cell[1])
    _set_cavity(rt.world, cx, cy)
    soft = float(SEPARATION_WORK_PER_QUANTITY_V1["component_b"])
    researcher_set_cell_resistance_override(
        rt.world, rt.config, cell_x=cx, cell_y=cy, separation_work_per_quantity=soft
    )

    # Drive tip onto lower floor (boundary 4) — not legacy max 10.
    rt.body.vx = rt.body.vy = rt.body.vz = 0.0
    cz = float(centre_z_of(rt.body, kind="body", config=rt.config))
    floor = 4.0
    target = float(floor - cz) - 0.15
    rows = drive_actuated_relative_z_to(
        rt.world,
        config=rt.config,
        body=rt.body,
        body_id=bid,
        effector_id="LEFT",
        target_z=target,
        tick_start=1,
        max_steps=60,
        runtime=rt,
    )
    _tick(len(rows))

    ints_before = occupied_intervals_at(rt.world, cx + 0.5, cy + 0.5)
    assert len(ints_before) >= 2
    n0 = len(list(rt.world.resource_objects or []))

    failed = any(r.get("material_failure") for r in rows)
    fail = getattr(rt.world, "last_surface_material_failure", None)
    if not failed and fail is None:
        for i in range(40):
            rec = request_actuated_relative_displacement(
                rt.world,
                config=rt.config,
                body=rt.body,
                body_id=bid,
                effector_id="LEFT",
                requested_delta_z=-0.05,
                tick=100 + i,
                runtime=rt,
            )
            _tick()
            if rec.get("material_failure") or getattr(rt.world, "last_surface_material_failure", None):
                failed = True
                break
    fail = getattr(rt.world, "last_surface_material_failure", None)
    assert failed or (fail is not None and fail.get("failure")), "expected physical material failure"
    assert fail is not None
    assert fail.get("wmt_invoked") is True
    assert fail.get("vw5_occupancy_material") is True
    wr = fail.get("wmt_receipt") or {}
    assert wr.get("status") == "COMMITTED"
    sid = str(wr.get("separation_id") or fail.get("separation_id") or "")
    assert sid.startswith("vw3-sep") or str(wr.get("schema") or "").startswith("VW3_")
    assert fail.get("vw5_routed_to_vw3") or wr.get("vw5_bridge") or sid.startswith("vw3-sep")
    # Failure must target the cavity cell we prepared
    assert list(wr.get("cell") or [fail.get("cell_x"), fail.get("cell_y")]) == [cx, cy]
    st5 = vw5_state(rt.world)
    assert st5 is not None and st5.last_exertion_bridge.get("vw3_receipt")

    objs = list(rt.world.resource_objects or [])
    assert len(objs) > n0
    # Upper interval survives
    ints_after = occupied_intervals_at(rt.world, cx + 0.5, cy + 0.5)
    assert any(abs(float(it.z_min) - 8.0) < 1e-9 and abs(float(it.z_max) - 10.0) < 1e-9 for it in ints_after)
    assert occupancy_at(rt.world, cx + 0.5, cy + 0.5, 9.0)
    # Lower contacted material changed
    lower_after = [it for it in ints_after if float(it.z_max) <= 4.0 + 1e-6]
    assert lower_after
    assert any(float(it.z_max) < 4.0 - 1e-9 for it in lower_after) or any(
        abs(float(it.thickness) - 4.0) > 1e-6 for it in lower_after
    )

    s = query_vertical_support_at(rt.world, cx + 0.5, cy + 0.5, 5.0, config=rt.config, record=False)
    assert s.boundary_z is not None
    g = occupancy_probe_geometry_at(rt.world, cx + 0.5, cy + 0.5, 5.0, radius=0.0, config=rt.config)
    assert g["boundary_z"] is not None
    assert abs(float(s.boundary_z) - float(g["boundary_z"])) < 1e-9


def test_L_VW2_agreement():
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        occupancy_probe_geometry_at,
    )
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )

    rt = _rt(14)
    _set_cavity(rt.world, 4, 4)
    z = 6.0
    g = occupancy_probe_geometry_at(rt.world, 4.5, 4.5, z, radius=0.0, config=rt.config)
    s = query_vertical_support_at(rt.world, 4.5, 4.5, z, config=rt.config, record=False)
    assert abs(float(g["boundary_z"]) - float(s.boundary_z)) < 1e-9
    assert g["in_contact"] is False
    assert s.relation in ("ABOVE_SUPPORT", "NO_SUPPORT_BELOW") or not s.contact_exists


def test_M_N_snapshot_determinism():
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        occupancy_probe_geometry_at,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        serialize_volumetric_occupancy,
        restore_volumetric_occupancy,
        state_of,
    )

    def once(tag: str):
        rt = _rt(15)
        _set_cavity(rt.world, 2, 2)
        g = occupancy_probe_geometry_at(rt.world, 2.5, 2.5, 6.0, radius=0.0, config=rt.config)
        snap = serialize_volumetric_occupancy(rt.world)
        dig = state_of(rt.world).digest()
        return dig, g["boundary_z"], g["in_contact"], snap

    a = once("a")
    b = once("b")
    assert a[0] == b[0]
    assert a[1] == b[1]
    assert a[2] == b[2]
    rt2 = _rt(15)
    restore_volumetric_occupancy(rt2.world, a[3])
    g2 = occupancy_probe_geometry_at(rt2.world, 2.5, 2.5, 6.0, radius=0.0, config=rt2.config)
    assert g2["boundary_z"] == a[1]
    assert g2["in_contact"] == a[2]


def test_O_P_Q_R_S_observer_and_passivity():
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        observer_bridge_inspector_payload,
        occupancy_probe_geometry_at,
        researcher_payload,
        state_of,
    )
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of as vo_state

    rt = _rt(16)
    _set_cavity(rt.world, 1, 1)
    occupancy_probe_geometry_at(rt.world, 1.5, 1.5, 6.0, radius=0.0, config=rt.config)
    dig = vo_state(rt.world).digest()
    payload = observer_bridge_inspector_payload(rt.world, rt.config)
    assert payload is not None
    assert payload["schema"].startswith("VW5_")
    assert payload["last_probe"]["boundary_z"] == 4.0
    assert "reintegration_blocker" in payload
    rp = researcher_payload(rt.world)
    assert "effector_held_occupancy_exertion_bridge" in rp
    observer_bridge_inspector_payload(rt.world, rt.config)
    assert vo_state(rt.world).digest() == dig
    for tok in (
        "VW5_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE_V1",
        "effector_held_occupancy_exertion_bridge",
        "AUTHORITATIVE_EFFECTOR_HELD_OCCUPANCY_EXERTION_BRIDGE",
    ):
        assert tok in FORBIDDEN_TOKENS
    assert state_of(rt.world) is not None


def test_T_held_occupancy_contact_no_vw4_trigger():
    from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
        REINTEGRATION_BLOCKER,
        held_object_occupancy_contact,
    )
    from mechanistic_mind.physical_system.resource_objects import (
        CANONICAL_INTERACTION_RADIUS,
        CANONICAL_OPTICAL_RADIUS,
        CANONICAL_OPTICAL_RESPONSE,
        MaterialComponent,
        PHYSICAL_STATE_FREE_STATIC,
        ResourceObject,
    )

    rt = _rt(17)
    _set_cavity(rt.world, 5, 5)
    obj = ResourceObject(
        object_id="resource-vw5-held-probe",
        x=5.5,
        y=5.5,
        mass=1.0,
        quantity=1.0,
        composition=(MaterialComponent("soil", 1.0),),
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        vx=0.0,
        vy=0.0,
        provenance={"source": "VW5_TEST"},
        optical_radius=float(CANONICAL_OPTICAL_RADIUS),
        optical_response=tuple(CANONICAL_OPTICAL_RESPONSE),
        interaction_radius=float(CANONICAL_INTERACTION_RADIUS),
        collision_radius=0.25,
        vertical_half_extent=0.25,
        z=6.0,
        vz=0.0,
        grounded=False,
    )
    rt.world.resource_objects = list(rt.world.resource_objects or []) + [obj]
    contact = held_object_occupancy_contact(rt.world, rt.config, object_id=obj.object_id)
    assert contact is not None
    assert contact["occupancy_contact"]["in_contact"] is False
    assert contact["reintegration_eligible"] is False
    assert contact["vw4_trigger"] is False
    assert REINTEGRATION_BLOCKER in contact["reintegration_blocker"]


def test_TOTAL_SIMULATED_TICKS_budget():
    assert TICKS["n"] <= 100
