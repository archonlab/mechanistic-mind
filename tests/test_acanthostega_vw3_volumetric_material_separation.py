"""VW3_VOLUMETRIC_MATERIAL_SEPARATION_V1 — interval mutation + conservation + support loss."""
from __future__ import annotations

import copy
import json

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _rt():
    from mechanistic_mind.model.acanthostega import acanthostega_volumetric_material_separation_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    cfg = acanthostega_volumetric_material_separation_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=41, config=cfg)


def _set_col(world, x, y, intervals, tick=0):
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import set_volumetric_column

    set_volumetric_column(world, x, y, intervals, tick=tick, reason="test_fixture")


def test_A_B_C_D_E_interval_subtraction_matrix():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        subtract_z_range_from_intervals,
    )

    base = (OccupiedZInterval(0.0, 10.0, 1.0, (("soil", 10.0),)),)
    # A top
    rem, pieces = subtract_z_range_from_intervals(base, 8.0, 10.0)
    assert len(rem) == 1 and abs(rem[0].z_max - 8.0) < 1e-12 and abs(pieces[0].z_min - 8.0) < 1e-12
    # B bottom
    rem, pieces = subtract_z_range_from_intervals(base, 0.0, 2.0)
    assert len(rem) == 1 and abs(rem[0].z_min - 2.0) < 1e-12 and abs(pieces[0].z_max - 2.0) < 1e-12
    # C middle
    rem, pieces = subtract_z_range_from_intervals(base, 4.0, 6.0)
    assert len(rem) == 2
    assert abs(rem[0].z_max - 4.0) < 1e-12 and abs(rem[1].z_min - 6.0) < 1e-12
    # D full
    rem, pieces = subtract_z_range_from_intervals(base, 0.0, 10.0)
    assert rem == () and len(pieces) == 1
    # E multi-interval: remove only upper
    multi = (
        OccupiedZInterval(0.0, 3.0, 1.0, (("a", 3.0),)),
        OccupiedZInterval(6.0, 8.0, 1.2, (("b", 2.0),)),
    )
    rem, pieces = subtract_z_range_from_intervals(multi, 6.0, 8.0)
    assert len(rem) == 1 and rem[0].composition[0][0] == "a"
    assert pieces[0].composition[0][0] == "b"


def test_F_G_H_I_J_apply_conservation_boundaries_invalid_atomic():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        occupancy_at,
        occupied_intervals_at,
        state_of,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )

    rt = _rt()
    _set_col(rt.world, 4, 5, [OccupiedZInterval(0.0, 10.0, 1.5, (("soil", 10.0),))])
    dig0 = state_of(rt.world).digest()
    objs0 = len(list(rt.world.resource_objects or []))
    # invalid free-space removal
    bad = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=4, cell_y=5, z_remove_lo=20.0, z_remove_hi=21.0, tick=1
    )
    assert bad["receipt"]["status"] == "REJECTED"
    assert state_of(rt.world).digest() == dig0
    assert len(list(rt.world.resource_objects or [])) == objs0

    out = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=4, cell_y=5, z_remove_lo=4.0, z_remove_hi=6.0, tick=2
    )
    assert out["receipt"]["status"] == "COMMITTED"
    cons = out["receipt"]["conservation"]
    oid = out["receipt"]["object_id"]
    obj = next(o for o in rt.world.resource_objects if o.object_id == oid)
    assert abs(float(obj.quantity) - float(cons["removed_quantity"])) < 1e-9
    assert abs(float(obj.mass) - float(cons["removed_mass"])) < 1e-9
    assert obj.composition[0].component_id == "soil"
    assert occupancy_at(rt.world, 4.5, 5.5, 3.0)
    assert not occupancy_at(rt.world, 4.5, 5.5, 5.0)
    assert occupancy_at(rt.world, 4.5, 5.5, 7.0)
    # boundary: at z=4 free (exclusive lower of upper remnant? rem[0] ends at 4 inclusive occupied)
    # (0,4] occupied at 4; (6,10] occupied at 6+; free at 5
    assert occupancy_at(rt.world, 4.5, 5.5, 4.0)
    assert not occupancy_at(rt.world, 4.5, 5.5, 6.0)  # exclusive lower of upper
    ints = occupied_intervals_at(rt.world, 4.5, 5.5)
    assert len(ints) == 2


def test_K_L_determinism_snapshot():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        occupied_intervals_at,
        serialize_volumetric_occupancy,
        restore_volumetric_occupancy,
        state_of,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )

    rt = _rt()
    _set_col(rt.world, 2, 3, [OccupiedZInterval(0.0, 10.0, 1.0, (("soil", 10.0),))])
    a = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=2, cell_y=3, z_remove_lo=4.0, z_remove_hi=6.0, tick=3
    )
    assert a["receipt"]["status"] == "COMMITTED"
    dig = state_of(rt.world).digest()
    intervals = [(it.z_min, it.z_max) for it in occupied_intervals_at(rt.world, 2.5, 3.5)]
    support = query_vertical_support_at(rt.world, 2.5, 3.5, 5.0, config=rt.config, record=False).as_dict()
    snap = serialize_volumetric_occupancy(rt.world)
    oid = a["receipt"]["object_id"]
    obj = next(o for o in rt.world.resource_objects if o.object_id == oid)
    obj_qty = float(obj.quantity)

    rt2 = _rt()
    restore_volumetric_occupancy(rt2.world, snap)
    assert state_of(rt2.world).digest() == dig
    assert [(it.z_min, it.z_max) for it in occupied_intervals_at(rt2.world, 2.5, 3.5)] == intervals
    s2 = query_vertical_support_at(rt2.world, 2.5, 3.5, 5.0, config=rt2.config, record=False).as_dict()
    assert s2["boundary_z"] == support["boundary_z"]
    assert abs(obj_qty - 2.0) < 1e-9  # thickness 2 * area 1


def test_M_N_O_support_removal_and_upper_survives():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        occupancy_at,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_vertical_entity

    rt = _rt()
    # Support at z=5
    _set_col(rt.world, 5, 5, [OccupiedZInterval(0.0, 5.0, 1.0, (("soil", 5.0),))])
    body = rt.body
    body.x, body.y = 5.5, 5.5
    body.z = 5.0
    body.vz = 0.0
    body.grounded = True
    r0 = query_vertical_support_at(rt.world, body.x, body.y, float(body.z), config=rt.config, record=False)
    assert r0.support_capable and abs(float(r0.boundary_z) - 5.0) < 1e-9

    # Remove support region (top slice of support)
    out = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=5, cell_y=5, z_remove_lo=4.0, z_remove_hi=5.0, tick=4
    )
    assert out["receipt"]["status"] == "COMMITTED"
    r1 = query_vertical_support_at(rt.world, body.x, body.y, float(body.z), config=rt.config, record=False)
    assert abs(float(r1.boundary_z) - 4.0) < 1e-9  # new top
    # Remove all remaining support under body
    out2 = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=5, cell_y=5, z_remove_lo=0.0, z_remove_hi=4.0, tick=5
    )
    assert out2["receipt"]["status"] == "COMMITTED"
    r2 = query_vertical_support_at(rt.world, body.x, body.y, 5.0, config=rt.config, record=False)
    assert r2.boundary_z is None and r2.relation == "NO_SUPPORT_BELOW"
    sz = float(support_z_for_entity(rt.world, rt.config, body.x, body.y, z=5.0))
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import NO_SUPPORT_SENTINEL

    assert sz <= NO_SUPPORT_SENTINEL * 0.5

    # Short gravity probe — body not told to fall; unsupported path applies
    body.z = 5.0
    body.vz = 0.0
    body.grounded = False
    z0 = float(body.z)
    cfg = rt.config.flat_ground_gravity
    for _ in range(15):
        integrate_vertical_entity(
            body,
            mass=1.0,
            config=cfg,
            tick=int(rt.tick),
            entity_id="agent_0",
            entity_kind="body",
            world=rt.world,
            runtime_config=rt.config,
        )
        _tick(1)
    assert float(body.z) < z0 - 1e-6

    # O: middle removal upper survives
    rt3 = _rt()
    _set_col(rt3.world, 1, 1, [OccupiedZInterval(0.0, 10.0, 1.0, (("soil", 10.0),))])
    apply_volumetric_material_separation(
        rt3.world, rt3.config, cell_x=1, cell_y=1, z_remove_lo=4.0, z_remove_hi=6.0, tick=1
    )
    assert occupancy_at(rt3.world, 1.5, 1.5, 7.0)
    assert occupancy_at(rt3.world, 1.5, 1.5, 3.0)
    assert not occupancy_at(rt3.world, 1.5, 1.5, 5.0)


def test_P_Q_wrap_no_z_wrap():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        occupancy_at,
        state_of,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )

    rt = _rt()
    st = state_of(rt.world)
    w = int(st.width)
    _set_col(rt.world, 0, 0, [OccupiedZInterval(1.0, 5.0, 1.0, (("soil", 4.0),))])
    out = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=w, cell_y=0, z_remove_lo=3.0, z_remove_hi=5.0, tick=1
    )
    assert out["receipt"]["status"] == "COMMITTED"
    assert occupancy_at(rt.world, 0.2, 0.2, 2.0)
    assert not occupancy_at(rt.world, 0.2, 0.2, 4.0)
    # Z non-wrap: removal far above does nothing useful / reject
    bad = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=0, cell_y=0, z_remove_lo=100.0, z_remove_hi=101.0, tick=2
    )
    assert bad["receipt"]["status"] == "REJECTED"


def test_R_S_T_U_V_observer_passivity():
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        state_of as vo_state,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
        observer_separation_inspector_payload,
        state_of,
    )
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        observer_support_inspector_payload,
    )

    rt = _rt()
    _set_col(rt.world, 3, 3, [OccupiedZInterval(0.0, 10.0, 1.0, (("soil", 10.0),))])
    apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=3, cell_y=3, z_remove_lo=4.0, z_remove_hi=6.0, tick=1
    )
    dig = vo_state(rt.world).digest()
    hist_len = len(state_of(rt.world).history)
    sep = observer_separation_inspector_payload(rt.world, rt.config)
    assert sep is not None
    assert sep["receipt"]["status"] == "COMMITTED"
    assert sep["receipt"]["object_id"]
    assert len(sep["receipt"]["after"]["occupied_intervals"]) == 2
    assert len(sep["receipt"]["removed_pieces"]) == 1
    support = observer_support_inspector_payload(rt.world, 3.5, 3.5, 5.0, config=rt.config)
    assert support is not None
    assert abs(float(support["boundary_z"]) - 4.0) < 1e-9
    assert vo_state(rt.world).digest() == dig
    assert len(state_of(rt.world).history) == hist_len
    for tok in (
        "VW3_VOLUMETRIC_MATERIAL_SEPARATION_V1",
        "volumetric_material_separation",
        "SEPARATE_VOLUMETRIC_OCCUPANCY_INTERVAL",
        "AUTHORITATIVE_VOLUMETRIC_MATERIAL_SEPARATION_VIA_WMT",
    ):
        assert tok in FORBIDDEN_TOKENS


def test_tick_budget():
    assert TICKS["n"] <= 100
    print("TOTAL_SIMULATED_TICKS", TICKS["n"])
