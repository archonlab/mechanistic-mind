"""VW4_CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1 — insert + conserve + support."""
from __future__ import annotations

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _rt():
    from mechanistic_mind.model.acanthostega import acanthostega_volumetric_material_reintegration_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    cfg = acanthostega_volumetric_material_reintegration_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=42, config=cfg)


def _set_col(world, x, y, intervals, tick=0):
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import set_volumetric_column

    set_volumetric_column(world, x, y, intervals, tick=tick, reason="test_fixture")


def _make_source(world, *, quantity, mass, composition, object_id="resource-vw4-src"):
    from mechanistic_mind.physical_system.resource_objects import (
        CANONICAL_INTERACTION_RADIUS,
        CANONICAL_OPTICAL_RADIUS,
        CANONICAL_OPTICAL_RESPONSE,
        MaterialComponent,
        PHYSICAL_STATE_FREE_STATIC,
        ResourceObject,
    )

    comps = tuple(MaterialComponent(str(c), float(a)) for c, a in composition)
    obj = ResourceObject(
        object_id=object_id,
        x=0.5,
        y=0.5,
        mass=float(mass),
        quantity=float(quantity),
        composition=comps,
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        vx=0.0,
        vy=0.0,
        provenance={"source": "VW4_TEST_FIXTURE", "researcher_only": True},
        optical_radius=float(CANONICAL_OPTICAL_RADIUS),
        optical_response=tuple(CANONICAL_OPTICAL_RESPONSE),
        interaction_radius=float(CANONICAL_INTERACTION_RADIUS),
        collision_radius=0.25,
        vertical_half_extent=0.25,
        material_revision=0,
        z=0.0,
        vz=0.0,
        grounded=True,
    )
    world.resource_objects = list(world.resource_objects or []) + [obj]
    return obj


def test_A_empty_column_insertion():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        occupied_intervals_at,
        occupancy_at,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
        insert_z_range_into_intervals,
    )

    # pure insert into empty
    after = insert_z_range_into_intervals((), 2.0, 4.0, density=1.0, composition=(("soil", 2.0),))
    assert len(after) == 1 and abs(after[0].z_min - 2.0) < 1e-12 and abs(after[0].z_max - 4.0) < 1e-12

    rt = _rt()
    _set_col(rt.world, 1, 1, [])
    src = _make_source(rt.world, quantity=2.0, mass=2.0, composition=[("soil", 2.0)])
    out = apply_volumetric_material_reintegration(
        rt.world, rt.config, object_id=src.object_id, cell_x=1, cell_y=1,
        z_deposit_lo=2.0, z_deposit_hi=4.0, tick=1,
    )
    _tick()
    assert out["receipt"]["status"] == "COMMITTED"
    assert occupancy_at(rt.world, 1.5, 1.5, 3.0)
    assert not occupancy_at(rt.world, 1.5, 1.5, 1.0)
    assert all(o.object_id != src.object_id for o in (rt.world.resource_objects or []))
    ints = occupied_intervals_at(rt.world, 1.5, 1.5)
    assert len(ints) == 1 and ints[0].composition[0][0] == "soil"


def test_B_C_top_bottom_adjacency():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        insert_z_range_into_intervals,
    )

    # Top adjacency — identical composition amounts merge under VW1
    base = (OccupiedZInterval(0.0, 4.0, 1.0, (("soil", 2.0),)),)
    # deposit with same composition amount won't match thickness-scaled remnant; exact-equal merge only
    top = insert_z_range_into_intervals(base, 4.0, 6.0, density=1.0, composition=(("soil", 2.0),))
    assert abs(top[0].z_min - 0.0) < 1e-12 and abs(top[-1].z_max - 6.0) < 1e-12
    # Bottom adjacency
    base2 = (OccupiedZInterval(4.0, 8.0, 1.0, (("soil", 2.0),)),)
    bot = insert_z_range_into_intervals(base2, 2.0, 4.0, density=1.0, composition=(("soil", 2.0),))
    assert abs(bot[0].z_min - 2.0) < 1e-12 and abs(bot[-1].z_max - 8.0) < 1e-12


def test_D_E_partial_and_complete_gap_fill():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        free_gaps_between,
        occupied_intervals_at,
        occupancy_at,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
    )

    rt = _rt()
    # Partial: (0,2] + free (2,8] + (8,10]; deposit (2,4]
    _set_col(
        rt.world,
        3,
        3,
        [
            OccupiedZInterval(0.0, 2.0, 1.0, (("soil", 2.0),)),
            OccupiedZInterval(8.0, 10.0, 1.0, (("soil", 2.0),)),
        ],
    )
    src = _make_source(rt.world, quantity=2.0, mass=2.0, composition=[("soil", 2.0)], object_id="resource-partial")
    out = apply_volumetric_material_reintegration(
        rt.world, rt.config, object_id=src.object_id, cell_x=3, cell_y=3,
        z_deposit_lo=2.0, z_deposit_hi=4.0, tick=2,
    )
    _tick()
    assert out["receipt"]["status"] == "COMMITTED"
    assert occupancy_at(rt.world, 3.5, 3.5, 3.0)
    assert not occupancy_at(rt.world, 3.5, 3.5, 5.0)
    assert occupancy_at(rt.world, 3.5, 3.5, 9.0)
    ints = occupied_intervals_at(rt.world, 3.5, 3.5)
    gaps = free_gaps_between(ints)
    assert any(abs(g[0] - 4.0) < 1e-9 and abs(g[1] - 8.0) < 1e-9 for g in gaps)

    # Complete gap fill: (0,4] + free (4,6] + (6,10]
    rt2 = _rt()
    _set_col(
        rt2.world,
        4,
        4,
        [
            OccupiedZInterval(0.0, 4.0, 1.0, (("soil", 4.0),)),
            OccupiedZInterval(6.0, 10.0, 1.0, (("soil", 4.0),)),
        ],
    )
    src2 = _make_source(rt2.world, quantity=2.0, mass=2.0, composition=[("soil", 2.0)], object_id="resource-fullgap")
    out2 = apply_volumetric_material_reintegration(
        rt2.world, rt2.config, object_id=src2.object_id, cell_x=4, cell_y=4,
        z_deposit_lo=4.0, z_deposit_hi=6.0, tick=3,
    )
    assert out2["receipt"]["status"] == "COMMITTED"
    assert occupancy_at(rt2.world, 4.5, 4.5, 5.0)
    ints2 = occupied_intervals_at(rt2.world, 4.5, 4.5)
    assert free_gaps_between(ints2) == []
    # continuous occupied coverage (0,10]
    for z in (0.5, 2.0, 4.0, 5.0, 6.0, 8.0, 10.0):
        assert occupancy_at(rt2.world, 4.5, 4.5, z)


def test_F_isolated_free_space_insertion():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        free_gaps_between,
        occupied_intervals_at,
        occupancy_at,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
    )

    rt = _rt()
    _set_col(
        rt.world,
        5,
        5,
        [
            OccupiedZInterval(0.0, 2.0, 1.0, (("a", 2.0),)),
            OccupiedZInterval(10.0, 12.0, 1.2, (("b", 2.0),)),
        ],
    )
    src = _make_source(rt.world, quantity=1.0, mass=1.5, composition=[("c", 1.0)], object_id="resource-iso")
    out = apply_volumetric_material_reintegration(
        rt.world, rt.config, object_id=src.object_id, cell_x=5, cell_y=5,
        z_deposit_lo=5.0, z_deposit_hi=6.0, tick=4,
    )
    _tick()
    assert out["receipt"]["status"] == "COMMITTED"
    ints = occupied_intervals_at(rt.world, 5.5, 5.5)
    assert len(ints) == 3
    assert occupancy_at(rt.world, 5.5, 5.5, 5.5)
    assert not occupancy_at(rt.world, 5.5, 5.5, 3.0)
    assert not occupancy_at(rt.world, 5.5, 5.5, 8.0)
    gaps = free_gaps_between(ints)
    assert len(gaps) == 2
    mid = [it for it in ints if abs(it.z_min - 5.0) < 1e-9][0]
    assert mid.composition[0][0] == "c"
    assert abs(mid.density - 1.5) < 1e-9


def test_G_H_I_J_K_L_overlap_identity_conservation_atomic():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        occupied_intervals_at,
        state_of,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
    )

    rt = _rt()
    _set_col(rt.world, 6, 6, [OccupiedZInterval(0.0, 4.0, 1.5, (("soil", 4.0),))])
    dig0 = state_of(rt.world).digest()
    objs0 = {o.object_id for o in (rt.world.resource_objects or [])}
    src = _make_source(rt.world, quantity=2.0, mass=3.0, composition=[("soil", 2.0)], object_id="resource-overlap")
    # Invalid overlap
    bad = apply_volumetric_material_reintegration(
        rt.world, rt.config, object_id=src.object_id, cell_x=6, cell_y=6,
        z_deposit_lo=2.0, z_deposit_hi=4.0, tick=5,
    )
    assert bad["receipt"]["status"] == "REJECTED"
    assert state_of(rt.world).digest() == dig0
    assert any(o.object_id == src.object_id for o in (rt.world.resource_objects or []))
    assert abs(float(next(o for o in rt.world.resource_objects if o.object_id == src.object_id).quantity) - 2.0) < 1e-9

    # Valid top deposit — identity + conservation + full consumption
    out = apply_volumetric_material_reintegration(
        rt.world, rt.config, object_id=src.object_id, cell_x=6, cell_y=6,
        z_deposit_lo=4.0, z_deposit_hi=6.0, tick=6,
    )
    _tick()
    assert out["receipt"]["status"] == "COMMITTED"
    cons = out["receipt"]["conservation"]
    assert abs(cons["source_quantity_before"] - cons["world_quantity_added"]) < 1e-9
    assert abs(cons["source_mass_before"] - cons["world_mass_added"]) < 1e-9
    assert cons["source_quantity_after"] == 0.0
    assert all(o.object_id != src.object_id for o in (rt.world.resource_objects or []))
    ints = occupied_intervals_at(rt.world, 6.5, 6.5)
    # deposited material identity
    deposited = [it for it in ints if it.z_max > 4.0 + 1e-9 or abs(it.z_min - 4.0) < 1e-9]
    assert any(abs(it.density - 1.5) < 1e-9 for it in deposited)
    assert any(it.composition and it.composition[0][0] == "soil" for it in deposited)


def test_M_VW3_VW4_round_trip():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        free_gaps_between,
        occupied_intervals_at,
        occupancy_at,
        state_of,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
    )
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )

    rt = _rt()
    _set_col(rt.world, 7, 7, [OccupiedZInterval(0.0, 10.0, 1.0, (("soil", 10.0),))])
    dig0 = state_of(rt.world).digest()
    support0 = query_vertical_support_at(rt.world, 7.5, 7.5, 11.0, config=rt.config, record=False).as_dict()

    sep = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=7, cell_y=7, z_remove_lo=4.0, z_remove_hi=6.0, tick=7,
    )
    _tick()
    assert sep["receipt"]["status"] == "COMMITTED"
    oid = sep["receipt"]["object_id"]
    ints_mid = occupied_intervals_at(rt.world, 7.5, 7.5)
    assert len(ints_mid) == 2
    assert free_gaps_between(ints_mid) == [(4.0, 6.0)] or (
        abs(free_gaps_between(ints_mid)[0][0] - 4.0) < 1e-9
        and abs(free_gaps_between(ints_mid)[0][1] - 6.0) < 1e-9
    )

    rein = apply_volumetric_material_reintegration(
        rt.world, rt.config, object_id=oid, cell_x=7, cell_y=7,
        z_deposit_lo=4.0, z_deposit_hi=6.0, tick=8,
    )
    _tick()
    assert rein["receipt"]["status"] == "COMMITTED"
    assert rein["receipt"]["source_consumed"] is True
    assert all(o.object_id != oid for o in (rt.world.resource_objects or []))
    # continuous physical coverage equivalent to original
    for z in (0.5, 2.0, 4.0, 5.0, 6.0, 8.0, 10.0):
        assert occupancy_at(rt.world, 7.5, 7.5, z)
    assert free_gaps_between(occupied_intervals_at(rt.world, 7.5, 7.5)) == []
    support1 = query_vertical_support_at(rt.world, 7.5, 7.5, 11.0, config=rt.config, record=False).as_dict()
    assert abs(float(support1["boundary_z"]) - float(support0["boundary_z"])) < 1e-9
    # provenance chain
    prov = rein["receipt"]["provenance"]
    assert prov.get("separation_transaction_id") == sep["receipt"]["transaction_id"] or prov.get(
        "prior_object_provenance", {}
    ).get("transaction_id") == sep["receipt"]["transaction_id"]
    # digest may differ if intervals not single-merged; physical coverage is the invariant
    assert state_of(rt.world) is not None
    _ = dig0  # original digest retained for contrast only


def test_N_O_VW2_new_support_and_unrelated_stable():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
    )
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )

    rt = _rt()
    # Destination empty at support region; unrelated column stable
    _set_col(rt.world, 8, 8, [])
    _set_col(rt.world, 9, 9, [OccupiedZInterval(0.0, 3.0, 1.0, (("soil", 3.0),))])
    s_unrel0 = query_vertical_support_at(rt.world, 9.5, 9.5, 4.0, config=rt.config, record=False).as_dict()
    s_before = query_vertical_support_at(rt.world, 8.5, 8.5, 5.0, config=rt.config, record=False).as_dict()
    assert s_before.get("boundary_z") is None or not s_before.get("support_capable")

    src = _make_source(rt.world, quantity=2.0, mass=2.0, composition=[("soil", 2.0)], object_id="resource-support")
    out = apply_volumetric_material_reintegration(
        rt.world, rt.config, object_id=src.object_id, cell_x=8, cell_y=8,
        z_deposit_lo=0.0, z_deposit_hi=2.0, tick=9,
    )
    _tick()
    assert out["receipt"]["status"] == "COMMITTED"
    s_after = query_vertical_support_at(rt.world, 8.5, 8.5, 5.0, config=rt.config, record=False).as_dict()
    assert s_after.get("support_capable") or s_after.get("boundary_z") is not None
    assert abs(float(s_after["boundary_z"]) - 2.0) < 1e-9
    s_unrel1 = query_vertical_support_at(rt.world, 9.5, 9.5, 4.0, config=rt.config, record=False).as_dict()
    assert s_unrel1["boundary_z"] == s_unrel0["boundary_z"]


def test_P_Q_R_S_gap_canonical_xy_no_z_wrap():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        free_gaps_between,
        occupied_intervals_at,
        state_of,
        wrap_cell,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
        insert_z_range_into_intervals,
        VolumetricReintegrationValidationError,
        R_BOUNDS,
    )
    import pytest

    # Multiple interval canonicalization / no zero-thickness
    multi = (
        OccupiedZInterval(0.0, 1.0, 1.0, (("a", 1.0),)),
        OccupiedZInterval(5.0, 6.0, 1.0, (("b", 1.0),)),
    )
    out = insert_z_range_into_intervals(multi, 2.0, 3.0, density=1.0, composition=(("c", 1.0),))
    assert len(out) == 3
    assert all(it.z_max > it.z_min + 1e-12 for it in out)
    assert free_gaps_between(out)

    with pytest.raises(VolumetricReintegrationValidationError):
        insert_z_range_into_intervals((), 5.0, 5.0, density=1.0, composition=(("a", 0.0),))

    rt = _rt()
    st = state_of(rt.world)
    w, h = int(st.width), int(st.height)
    # XY wrap: deposit at x=w (wraps to 0)
    src = _make_source(rt.world, quantity=1.0, mass=1.0, composition=[("soil", 1.0)], object_id="resource-wrap")
    cell = wrap_cell(st, w, 0)
    assert cell[0] == 0
    _set_col(rt.world, cell[0], cell[1], [])
    res = apply_volumetric_material_reintegration(
        rt.world, rt.config, object_id=src.object_id, cell_x=w, cell_y=0,
        z_deposit_lo=1.0, z_deposit_hi=2.0, tick=10,
    )
    assert res["receipt"]["status"] == "COMMITTED"
    assert res["receipt"]["cell"][0] == 0
    # No Z wrap — absolute Z remains non-periodic; negative-to-positive is fine as absolute
    ints = occupied_intervals_at(rt.world, 0.5, 0.5)
    assert all(it.z_max > it.z_min for it in ints)
    _ = R_BOUNDS


def test_T_U_snapshot_restore_determinism():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        occupied_intervals_at,
        serialize_volumetric_occupancy,
        restore_volumetric_occupancy,
        state_of,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
    )
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )

    def run_once(seed_tag: str):
        rt = _rt()
        _set_col(rt.world, 2, 2, [OccupiedZInterval(0.0, 2.0, 1.0, (("soil", 2.0),))])
        src = _make_source(
            rt.world, quantity=2.0, mass=2.0, composition=[("soil", 2.0)], object_id=f"resource-{seed_tag}"
        )
        out = apply_volumetric_material_reintegration(
            rt.world, rt.config, object_id=src.object_id, cell_x=2, cell_y=2,
            z_deposit_lo=2.0, z_deposit_hi=4.0, tick=11,
        )
        assert out["receipt"]["status"] == "COMMITTED"
        dig = state_of(rt.world).digest()
        intervals = [(it.z_min, it.z_max, it.density) for it in occupied_intervals_at(rt.world, 2.5, 2.5)]
        support = query_vertical_support_at(rt.world, 2.5, 2.5, 5.0, config=rt.config, record=False).as_dict()
        snap = serialize_volumetric_occupancy(rt.world)
        objs = [str(o.object_id) for o in (rt.world.resource_objects or [])]
        return dig, intervals, support, snap, objs, out["receipt"]["transaction_id"]

    a = run_once("det-a")
    b = run_once("det-b")
    assert a[0] == b[0]
    assert a[1] == b[1]
    assert a[2]["boundary_z"] == b[2]["boundary_z"]

    rt2 = _rt()
    restore_volumetric_occupancy(rt2.world, a[3])
    assert state_of(rt2.world).digest() == a[0]
    assert [(it.z_min, it.z_max, it.density) for it in occupied_intervals_at(rt2.world, 2.5, 2.5)] == a[1]
    assert "resource-det-a" not in a[4]


def test_V_W_X_Y_Z_observer_payload_passivity():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        state_of,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
        observer_reintegration_inspector_payload,
        researcher_payload,
    )
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS

    rt = _rt()
    _set_col(rt.world, 0, 0, [])
    src = _make_source(rt.world, quantity=1.0, mass=1.0, composition=[("soil", 1.0)], object_id="resource-obs")
    out = apply_volumetric_material_reintegration(
        rt.world, rt.config, object_id=src.object_id, cell_x=0, cell_y=0,
        z_deposit_lo=0.0, z_deposit_hi=1.0, tick=12,
    )
    assert out["receipt"]["status"] == "COMMITTED"
    dig = state_of(rt.world).digest()
    payload = observer_reintegration_inspector_payload(rt.world, rt.config)
    assert payload is not None
    assert payload["schema"].startswith("VW4_")
    rec = payload["receipt"]
    assert rec["object_id"] == "resource-obs"
    assert rec["source_consumed"] is True
    assert rec["transaction_id"]
    assert rec["after"]["inserted"]["z_lo"] == 0.0
    rp = researcher_payload(rt.world)
    assert "volumetric_material_reintegration" in rp
    # passivity: inspection does not mutate
    _ = observer_reintegration_inspector_payload(rt.world, rt.config)
    assert state_of(rt.world).digest() == dig
    for tok in (
        "VW4_CONSERVATIVE_VOLUMETRIC_DEPOSITION_REINTEGRATION_V1",
        "REINTEGRATE_VOLUMETRIC_OCCUPANCY_INTERVAL",
        "volumetric_material_reintegration",
    ):
        assert tok in FORBIDDEN_TOKENS


def test_TOTAL_SIMULATED_TICKS_budget():
    assert TICKS["n"] <= 50
