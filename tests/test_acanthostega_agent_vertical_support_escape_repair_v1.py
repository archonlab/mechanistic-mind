"""Regression: unsupported below-support recovery vs open-bottom free-fall.

Schema: ACANTHOSTEGA_AGENT_VERTICAL_SUPPORT_ESCAPE_REPAIR_V1
"""
from __future__ import annotations

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
    NO_SUPPORT_SENTINEL,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
    CLASS_SES_BELOW_SUPPORT,
    CLASS_START_PENETRATION,
    plan_landing,
)
from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
    set_volumetric_column,
    state_of,
    wrap_cell,
)


def _cfg():
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def test_fall_from_above_lands_on_authoritative_support():
    cfg = _cfg()
    rt = PhysicalSystemRuntime(seed=1794, config=cfg)
    sz = support_z_for_entity(rt.world, cfg, rt.body.x, rt.body.y, z=rt.body.z)
    rt.body.z = float(sz) + 1.5
    rt.body.vz = 0.0
    rt.body.grounded = False
    for _ in range(200):
        rt.step_forced_action("WAIT")
        if rt.body.grounded:
            break
    assert rt.body.grounded
    assert abs(rt.body.z - support_z_for_entity(rt.world, cfg, rt.body.x, rt.body.y, z=rt.body.z)) < 1e-5


def test_unsupported_deep_below_finite_support_recovers_via_start_penetration():
    cfg = _cfg()
    rt = PhysicalSystemRuntime(seed=1794, config=cfg)
    sz = support_z_for_entity(rt.world, cfg, rt.body.x, rt.body.y, z=rt.body.z)
    rt.body.z = float(sz) - 100.0
    rt.body.vz = -2.0
    rt.body.grounded = False
    rt.step_forced_action("WAIT")
    assert rt.body.grounded
    assert abs(rt.body.z - sz) < 0.05


def test_empty_vw1_column_preserves_open_bottom_free_fall():
    cfg = _cfg()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    st = state_of(rt.world)
    cell = wrap_cell(st, rt.body.x, rt.body.y)
    set_volumetric_column(rt.world, cell[0], cell[1], [], tick=0, reason="test_empty")
    z0 = float(rt.body.z)
    for _ in range(40):
        rt.step_forced_action("WAIT")
    support = support_z_for_entity(rt.world, cfg, rt.body.x, rt.body.y, z=rt.body.z)
    assert support <= float(NO_SUPPORT_SENTINEL) * 0.5
    assert not rt.body.grounded
    assert rt.body.z < z0 - 1.0


def test_empty_column_then_supported_cell_recovers():
    cfg = _cfg()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    st = state_of(rt.world)
    cell = wrap_cell(st, rt.body.x, rt.body.y)
    set_volumetric_column(rt.world, cell[0], cell[1], [], tick=0, reason="test_empty")
    for _ in range(40):
        rt.step_forced_action("WAIT")
    rt.body.x = (cell[0] + 3) % st.width + 0.4
    rt.body.y = (cell[1] + 1) % st.height + 0.4
    rt.step_forced_action("WAIT")
    sz = support_z_for_entity(rt.world, cfg, rt.body.x, rt.body.y, z=rt.body.z)
    assert sz > float(NO_SUPPORT_SENTINEL) * 0.5
    assert rt.body.grounded
    assert abs(rt.body.z - sz) < 1e-5


def test_xy_wrap_seam_retains_support():
    cfg = _cfg()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.x = 0.05
    rt.body.y = 16.0
    sz = support_z_for_entity(rt.world, cfg, rt.body.x, rt.body.y, z=rt.body.z)
    rt.body.z = float(sz)
    rt.body.vz = 0.0
    rt.body.grounded = True
    for _ in range(24):
        rt.step_forced_action("MOVE:W")
        assert rt.body.z > -1.0
        if rt.body.grounded:
            continue
        # brief airborne near microrelief is ok; must not enter SES_BELOW escape
        assert rt.body.z > support_z_for_entity(rt.world, cfg, rt.body.x, rt.body.y, z=rt.body.z) - 2.5


def test_two_agent_identical_recovery():
    cfg = _cfg()
    tar = TwoAgentRuntime(seed=1794, config=cfg)
    for slot in tar.slots:
        sz = support_z_for_entity(slot.world, cfg, slot.body.x, slot.body.y, z=slot.body.z)
        slot.body.z = float(sz) - 50.0
        slot.body.vz = -2.0
        slot.body.grounded = False
    tar.step()
    for slot in tar.slots:
        assert slot.body.grounded


def test_shallow_non_approaching_ses_free_lift_lock_preserved():
    plan = plan_landing(
        tick=1,
        entity_id="agent_0",
        entity_kind="body",
        body_slot="agent_0",
        x=1.0,
        y=1.0,
        z0=-0.05,
        vz0=0.0,
        z1_proposed=-0.05,
        vz1_proposed=0.0,
        support_z=0.0,
        half_extent=0.575,
        mass=2.0,
        mass_provenance="BODY_CONFIG_MASS",
        mass_valid=True,
        was_grounded=False,
        skip_gravity=False,
        gravity_applied=False,
        ses_below_support=True,
        max_vz=2.0,
        dt=1.0,
        cfg=__import__(
            "mechanistic_mind.physical_system.vertical_terrain_landing_contact_response",
            fromlist=["VerticalTerrainLandingContactResponseConfig"],
        ).VerticalTerrainLandingContactResponseConfig(enabled=True),
    )
    assert plan["classification"] == CLASS_SES_BELOW_SUPPORT
    assert plan["support_planned"] is False


def test_falling_start_penetration_classifies_recovery():
    plan = plan_landing(
        tick=1,
        entity_id="agent_1",
        entity_kind="body",
        body_slot="agent_1",
        x=1.0,
        y=1.0,
        z0=-10.0,
        vz0=-2.0,
        z1_proposed=-12.0,
        vz1_proposed=-2.0,
        support_z=-0.3,
        half_extent=0.575,
        mass=2.0,
        mass_provenance="BODY_CONFIG_MASS",
        mass_valid=True,
        was_grounded=False,
        skip_gravity=False,
        gravity_applied=True,
        ses_below_support=True,
        max_vz=2.0,
        dt=1.0,
        cfg=__import__(
            "mechanistic_mind.physical_system.vertical_terrain_landing_contact_response",
            fromlist=["VerticalTerrainLandingContactResponseConfig"],
        ).VerticalTerrainLandingContactResponseConfig(enabled=True),
    )
    assert plan["classification"] == CLASS_START_PENETRATION
    assert plan["support_planned"] is True
    assert abs(plan["z_after_planned"] - (-0.3)) < 1e-12
