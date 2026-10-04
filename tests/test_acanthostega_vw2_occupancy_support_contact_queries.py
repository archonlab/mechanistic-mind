"""VW2_OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1 — targeted support/contact tests.

TOTAL_SIMULATED_TICKS budget: prefer short probes; report exact count.
"""
from __future__ import annotations

import copy
import json

import pytest

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cavity_world():
    """Build world with VW1+VW2 and a cavity column at (4,5)."""
    from mechanistic_mind.model.acanthostega import acanthostega_occupancy_support_contact_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        set_volumetric_column,
    )

    cfg = acanthostega_occupancy_support_contact_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=31, config=cfg)
    set_volumetric_column(
        rt.world,
        4,
        5,
        [
            OccupiedZInterval(0.0, 3.0, 1.0, (("soil", 3.0),)),
            OccupiedZInterval(6.0, 8.0, 1.2, (("rock", 2.0),)),
        ],
    )
    return rt


def test_A_legacy_flat_equivalence():
    from mechanistic_mind.model.acanthostega import acanthostega_occupancy_support_contact_config
    from mechanistic_mind.physical_system.procedural_surface_columns import resolved_column_at
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import surface_support_height

    cfg = acanthostega_occupancy_support_contact_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    x, y = 3.2, 4.1
    H = float(resolved_column_at(rt.world, x, y, record=False)["surface_elevation"])
    legacy = float(surface_support_height(rt.world, x, y, config=rt.config))
    # Body resting on surface
    r = query_vertical_support_at(rt.world, x, y, H, config=rt.config, record=False)
    assert r.boundary_z is not None
    assert abs(float(r.boundary_z) - H) < 1e-9
    assert abs(legacy - H) < 1e-9
    assert r.support_capable is True


def test_B_C_D_E_F_cavity_contradiction_and_selection():
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import (
        support_z_for_entity,
        surface_support_height,
    )

    rt = _cavity_world()
    x, y = 4.5, 5.5
    # PSC/CSG heightfield may still report ordinary column height; VW1 sparse
    # derived surface for this cell is the upper slab top (= 8.0).
    r = query_vertical_support_at(rt.world, x, y, 4.0, config=rt.config, record=False)
    assert r.boundary_z is not None
    assert abs(float(r.boundary_z) - 3.0) < 1e-9  # CASE C lower support
    assert abs(float(r.legacy_projected_surface) - 8.0) < 1e-9
    # Heightfield contradiction: VW2 support != legacy projected surface
    assert r.contradicts_legacy_projected_surface is True
    assert r.support_capable is False  # ABOVE_SUPPORT (clearance > 0)
    assert r.relation == "ABOVE_SUPPORT"
    # CASE D: upper material not selected as support
    assert float(r.source_interval["z_max"]) == 3.0

    # At rest on lower top
    r2 = query_vertical_support_at(rt.world, x, y, 3.0, config=rt.config, record=False)
    assert r2.support_capable is True and abs(float(r2.boundary_z) - 3.0) < 1e-9

    # CASE E: no support below (body under everything? body above void with only upper slab)
    # Place body at z=4 with ONLY upper interval — use different cell
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        set_volumetric_column,
    )

    set_volumetric_column(rt.world, 6, 6, [OccupiedZInterval(6.0, 8.0, 1.0, (("rock", 2.0),))])
    r3 = query_vertical_support_at(rt.world, 6.5, 6.5, 4.0, config=rt.config, record=False)
    assert r3.boundary_z is None and r3.relation == "NO_SUPPORT_BELOW"
    sz = float(support_z_for_entity(rt.world, rt.config, 6.5, 6.5, z=4.0))
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import NO_SUPPORT_SENTINEL

    assert sz <= NO_SUPPORT_SENTINEL * 0.5

    # CASE F: multiple below — nearest (highest) below wins
    set_volumetric_column(
        rt.world,
        7,
        7,
        [
            OccupiedZInterval(0.0, 1.0, 1.0, (("a", 1.0),)),
            OccupiedZInterval(2.0, 3.0, 1.0, (("b", 1.0),)),
            OccupiedZInterval(5.0, 6.0, 1.0, (("c", 1.0),)),
        ],
    )
    r4 = query_vertical_support_at(rt.world, 7.5, 7.5, 4.0, config=rt.config, record=False)
    assert abs(float(r4.boundary_z) - 3.0) < 1e-9
    assert r4.source_interval["composition"][0]["component_id"] == "b"


def test_G_H_body_extent_and_footprint():
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        sample_footprint_vertical_support,
    )
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import BODY_CONTACT_RADIUS

    rt = _cavity_world()
    fp = sample_footprint_vertical_support(
        rt.world, 4.5, 5.5, 4.0, BODY_CONTACT_RADIUS, config=rt.config
    )
    assert fp["authoritative_support_z"] is not None
    assert abs(float(fp["authoritative_support_z"]) - 3.0) < 1e-9
    assert len(fp["samples"]) == 9  # centre + 8 ring


def test_I_J_wrap_and_no_z_wrap():
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        OccupiedZInterval,
        set_volumetric_column,
        state_of,
    )

    rt = _cavity_world()
    st = state_of(rt.world)
    w, h = int(st.width), int(st.height)
    set_volumetric_column(rt.world, 0, 0, [OccupiedZInterval(1.0, 2.0, 1.0, (("soil", 1.0),))])
    r = query_vertical_support_at(rt.world, w + 0.2, 0.2, 2.0, config=rt.config, record=False)
    assert abs(float(r.boundary_z) - 2.0) < 1e-9
    r2 = query_vertical_support_at(rt.world, 0.2, 0.2, 2.0 + 1000.0, config=rt.config, record=False)
    # far above: still selects top 2.0 as candidate below
    assert abs(float(r2.boundary_z) - 2.0) < 1e-9
    r3 = query_vertical_support_at(rt.world, 0.2, 0.2, 0.5, config=rt.config, record=False)
    assert r3.boundary_z is None  # no wrap into [1,2]


def test_K_L_stable_rest_and_stale_legacy_cannot_hold():
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_vertical_entity, state_of as fgg_state
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity

    rt = _cavity_world()
    body = rt.body
    # Rest on lower cavity floor
    body.x, body.y = 4.5, 5.5
    body.z = 3.0
    body.vz = 0.0
    body.grounded = True
    z0 = float(body.z)
    cfg = rt.config.flat_ground_gravity
    for _ in range(5):
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
    assert abs(float(body.z) - z0) < 1e-6
    assert abs(float(body.vz)) < 1e-6

    # Body in cavity free space — VW2 must not hold at legacy 8.0
    body.z = 4.5
    body.vz = 0.0
    body.grounded = False
    sz = float(support_z_for_entity(rt.world, rt.config, body.x, body.y, z=float(body.z)))
    assert abs(sz - 3.0) < 1e-9
    r = query_vertical_support_at(rt.world, body.x, body.y, float(body.z), config=rt.config)
    assert r.contradicts_legacy_projected_surface is True
    assert not r.support_capable


def test_M_N_snapshot_restore_and_determinism():
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        query_vertical_support_at,
    )

    rt = _cavity_world()
    a = query_vertical_support_at(rt.world, 4.5, 5.5, 4.0, config=rt.config, record=False).as_dict()
    b = query_vertical_support_at(rt.world, 4.5, 5.5, 4.0, config=rt.config, record=False).as_dict()
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    snap = rt.snapshot()
    rt2 = _cavity_world()
    # rebuild same cavity via restore of volumetric state from snap
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
        restore_volumetric_occupancy,
        serialize_volumetric_occupancy,
    )

    vo = snap["world"].get("volumetric_occupancy") or serialize_volumetric_occupancy(rt.world)
    # fresh runtime then restore occupancy
    from mechanistic_mind.model.acanthostega import acanthostega_occupancy_support_contact_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    cfg = acanthostega_occupancy_support_contact_config()
    cfg.cognition.cognition_enabled = False
    rt3 = PhysicalSystemRuntime(seed=31, config=cfg)
    restore_volumetric_occupancy(rt3.world, vo)
    c = query_vertical_support_at(rt3.world, 4.5, 5.5, 4.0, config=rt3.config, record=False).as_dict()
    assert abs(float(c["boundary_z"]) - float(a["boundary_z"])) < 1e-12
    assert c["relation"] == a["relation"]


def test_O_P_Q_observer_data_passivity_contradiction():
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS
    from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
        observer_support_inspector_payload,
        state_of,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of as vo_state

    rt = _cavity_world()
    dig = vo_state(rt.world).digest()
    qc_before = int(state_of(rt.world).query_count) if state_of(rt.world) else 0
    insp = observer_support_inspector_payload(rt.world, 4.5, 5.5, 4.0, config=rt.config)
    assert insp is not None
    assert abs(float(insp["boundary_z"]) - 3.0) < 1e-9
    assert insp["contradicts_legacy_projected_surface"] is True
    assert insp["source_interval"]["z_max"] == 3.0
    assert vo_state(rt.world).digest() == dig
    # Observer inspection uses record=False — query_count unchanged
    assert int(state_of(rt.world).query_count) == qc_before
    for tok in (
        "VW2_OCCUPANCY_SUPPORT_AND_CONTACT_QUERIES_V1",
        "occupancy_support_contact",
        "AUTHORITATIVE_SUPPORT_CONTACT_FROM_VOLUMETRIC_OCCUPANCY",
        "boundary_z",
    ):
        assert tok in FORBIDDEN_TOKENS


def test_probe_cavity_falls_toward_lower_support():
    """Short probe: body in cavity free space falls toward lower interval, not held at legacy surface."""
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_vertical_entity

    rt = _cavity_world()
    body = rt.body
    body.x, body.y = 4.5, 5.5
    body.z = 5.0
    body.vz = 0.0
    body.grounded = False
    cfg = rt.config.flat_ground_gravity
    for _ in range(30):
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
        if body.grounded and abs(float(body.z) - 3.0) < 1e-6:
            break
    assert float(body.z) < 5.0 - 1e-6  # descended
    assert float(body.z) <= 3.0 + 0.05  # near/at lower support
    assert float(body.z) < 7.0  # never snapped to legacy upper surface


def test_tick_budget():
    assert TICKS["n"] <= 100
    print("TOTAL_SIMULATED_TICKS", TICKS["n"])
