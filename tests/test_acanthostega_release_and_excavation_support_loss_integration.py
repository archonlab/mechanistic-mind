"""Free-Space V1D · RELEASE + excavation support-loss integration — focused tests."""
from __future__ import annotations

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_release_and_excavation_support_loss_integration_config,
    )

    cfg = acanthostega_release_and_excavation_support_loss_integration_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _parent_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_vertical_impact_acoustic_emission_config,
    )

    cfg = acanthostega_vertical_impact_acoustic_emission_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(cfg=None):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    return PhysicalSystemRuntime(seed=17, config=cfg or _cfg())


def test_01_preset_identity_parent_lineage():
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION,
        PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION,
        normalize_preset_name,
        preset_canonical,
    )
    from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
        MECHANISM_ID,
        PROFILE_VERSION,
        RECEIPT_KIND,
        release_and_excavation_support_loss_integration_is_active,
    )
    from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
        vertical_impact_acoustic_emission_is_active,
    )

    n = normalize_preset_name("RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1")
    assert n == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
    meta = preset_canonical(n)
    assert meta["parent"] == PRESET_ACANTHOSTEGA_VERTICAL_IMPACT_ACOUSTIC_EMISSION
    assert meta["model_line"] == "ACANTHOSTEGA"
    assert meta["mechanisms"][MECHANISM_ID] is True
    assert meta["mechanisms"]["vertical_impact_acoustic_emission"] is True
    assert meta["mechanisms"]["vertical_terrain_landing_contact_response"] is True
    assert meta["mechanisms"]["free_space_state_and_pe_authority_contract"] is True
    cfg = _cfg()
    assert release_and_excavation_support_loss_integration_is_active(cfg)
    assert vertical_impact_acoustic_emission_is_active(cfg)
    assert PROFILE_VERSION == "RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION_V1"
    assert RECEIPT_KIND == "RELEASE_EXCAVATION_SUPPORT_LOSS_V1"
    parent = _parent_cfg()
    assert not release_and_excavation_support_loss_integration_is_active(parent)
    assert vertical_impact_acoustic_emission_is_active(parent)


def test_02_conflicting_tiktaalik_ignored():
    from mechanistic_mind.model.lines import stamp_config_from_preset
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION,
    )

    cfg = _cfg()
    cfg.model_line = "TIKTAALIK"
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION)
    assert str(cfg.model_line).upper() == "ACANTHOSTEGA"
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION


def _obj(**kw):
    from mechanistic_mind.physical_system.resource_objects import MaterialComponent, ResourceObject

    base = dict(
        mass=1.0,
        quantity=1.0,
        composition=(MaterialComponent("component_0", 1.0),),
        physical_state="FREE_STATIC",
        collision_radius=0.25,
        vertical_half_extent=0.25,
    )
    base.update(kw)
    return ResourceObject(**base)


def _lower_cell(world, cx: int, cy: int, elev: float) -> None:
    from mechanistic_mind.physical_system import procedural_surface_columns as psc

    base = psc.baseline_column_at(world, int(cx), int(cy))
    tick = int(getattr(world, "tick", 0) or 0)
    psc.deltas_of(world)[(int(cx), int(cy))] = psc.SurfaceColumnDelta(
        delta_id=psc.delta_id_for(int(cx), int(cy)),
        cell_x=int(cx),
        cell_y=int(cy),
        baseline_generator_version=base.generator_version,
        baseline_checksum=base.baseline_checksum,
        resulting_surface_elevation=float(elev),
        resulting_layers=base.layers,
        created_tick=tick,
        last_updated_tick=tick,
        revision=1,
        provenance={"reason": "v1d_test_lower"},
    )
    try:
        from mechanistic_mind.physical_system.continuous_surface_geometry import (
            note_authoritative_surface_mutation,
        )

        note_authoritative_surface_mutation(world, None)
    except Exception:
        pass


def test_03_release_pose_velocity_eligibility_no_same_tick_integration():
    from mechanistic_mind.physical_system.flat_ground_gravity import apply_release_vertical
    from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
        CLASS_UNSUPPORTED,
        state_of,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        object_dynamics_eligible,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_free_objects_vertical

    rt = _rt()
    w = rt.world
    cfg = rt.config
    sz = float(support_z_for_entity(w, cfg, rt.body.x, rt.body.y))
    obj = _obj(object_id="rel_a", x=float(rt.body.x), y=float(rt.body.y))
    obj.z = float(sz) + 0.4
    obj.vz = 0.0
    obj.grounded = False
    w.resource_objects = list(getattr(w, "resource_objects", None) or []) + [obj]
    # Simulate held pose already at authoritative xyz before release.
    held_z = float(obj.z)
    rt.body.vz = -0.15
    apply_release_vertical(
        obj,
        rt.body,
        cfg,
        world=w,
        tick=5,
        holder_body_id="body-0",
        manipulator_id="hand",
    )
    _tick(1)
    assert float(obj.z) == held_z
    assert abs(float(obj.vz) - (-0.15)) < 1e-12
    assert int(obj.release_tick) == 5
    assert int(obj.dynamics_eligible_tick) == 6
    assert not object_dynamics_eligible(obj, 5)
    assert object_dynamics_eligible(obj, 6)
    st = state_of(w)
    assert st is not None
    assert any(r.get("event_class") in ("RELEASE_ENTRY", "ANOMALY") for r in st.history)
    rec = st.last_receipt
    assert rec["creates_impact"] is False
    assert rec["creates_sound"] is False
    assert rec["independent_integration_this_tick"] is False
    assert rec["support_classification"] in (CLASS_UNSUPPORTED, "UNSUPPORTED")
    # No free vertical integration on release tick.
    before_z = float(obj.z)
    integrate_free_objects_vertical(w, cfg, tick=5)
    assert float(obj.z) == before_z
    # T+1 falls via shared FGG.
    integrate_free_objects_vertical(w, cfg, tick=6)
    _tick(1)
    assert float(obj.z) < before_z or bool(getattr(obj, "grounded", False))


def test_04_release_at_support_no_impact_no_sound():
    from mechanistic_mind.physical_system.flat_ground_gravity import apply_release_vertical
    from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
        CLASS_SUPPORTED,
        state_of,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity
    from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
        process_vertical_impact_acoustic_emission,
        state_of as via_state,
    )

    rt = _rt()
    sz = float(support_z_for_entity(rt.world, rt.config, rt.body.x, rt.body.y))
    obj = _obj(object_id="rel_rest", x=float(rt.body.x), y=float(rt.body.y))
    obj.z = float(sz)
    obj.vz = 0.0
    obj.grounded = True
    rt.world.resource_objects = list(getattr(rt.world, "resource_objects", None) or []) + [obj]
    rt.body.vz = 0.0
    apply_release_vertical(
        obj, rt.body, rt.config, world=rt.world, tick=2, holder_body_id="body-0"
    )
    _tick(1)
    assert bool(obj.grounded) is True
    st = state_of(rt.world)
    assert st.last_receipt["support_classification"] == CLASS_SUPPORTED
    assert st.last_receipt["creates_impact"] is False
    assert st.last_receipt["creates_sound"] is False
    process_vertical_impact_acoustic_emission(rt.world, rt.config, emission_tick=2)
    via = via_state(rt.world)
    emissions = int((via.counters if via else {}).get("emissions", 0) or 0)
    assert emissions == 0


def test_05_excavation_refresh_body_and_object_no_snap():
    from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
        EVENT_SUPPORT_LOST,
        bilinear_corner_cells,
        refresh_support_after_terrain_mutation,
        state_of,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity

    rt = _rt()
    w, cfg = rt.world, rt.config
    bx, by = float(rt.body.x), float(rt.body.y)
    cell_x, cell_y = int(bx), int(by)
    sz0 = float(support_z_for_entity(w, cfg, bx, by))
    rt.body.z = sz0
    rt.body.vz = 0.0
    rt.body.grounded = True
    w.detached_placement_body_refs = [("body-0", rt.body)]
    obj = _obj(object_id="free_occ", x=bx + 0.1, y=by + 0.1)
    obj.z = sz0
    obj.vz = 0.0
    obj.grounded = True
    w.resource_objects = list(getattr(w, "resource_objects", None) or []) + [obj]

    # Prove bilinear dependency includes the floor cell under the body.
    corners = bilinear_corner_cells(bx, by, width=int(w.T.shape[1]), height=int(w.T.shape[0]))
    assert (cell_x, cell_y) in corners or any(
        abs(c[0] - cell_x) <= 1 and abs(c[1] - cell_y) <= 1 for c in corners
    )

    z_body = float(rt.body.z)
    z_obj = float(obj.z)
    _lower_cell(w, cell_x, cell_y, sz0 - 0.5)
    rows = refresh_support_after_terrain_mutation(
        w,
        cfg,
        cell_x=cell_x,
        cell_y=cell_y,
        elevation_before=sz0,
        elevation_after=sz0 - 0.5,
        tick=10,
        transaction_id="txn_test_1",
    )
    _tick(1)
    assert float(rt.body.z) == z_body
    assert float(obj.z) == z_obj
    assert bool(rt.body.grounded) is False
    assert bool(obj.grounded) is False
    st = state_of(w)
    lost = [r for r in st.history if r.get("event_class") == EVENT_SUPPORT_LOST]
    assert lost
    assert all(r.get("creates_impact") is False for r in lost)
    assert all(r.get("creates_sound") is False for r in lost)
    assert all(r.get("second_vertical_integration") is False for r in lost)
    assert rows


def test_06_refresh_dedup_one_per_entity_tick():
    from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
        EVENT_REFRESH_DEDUPLICATED,
        EVENT_SUPPORT_LOST,
        refresh_support_after_terrain_mutation,
        state_of,
    )

    rt = _rt()
    w, cfg = rt.world, rt.config
    bx, by = float(rt.body.x), float(rt.body.y)
    sz0 = 1.0
    rt.body.z = sz0
    rt.body.vz = 0.0
    rt.body.grounded = True
    w.detached_placement_body_refs = [("body-0", rt.body)]
    _lower_cell(w, int(bx), int(by), sz0 - 0.4)
    refresh_support_after_terrain_mutation(
        w, cfg, cell_x=int(bx), cell_y=int(by),
        elevation_before=sz0, elevation_after=sz0 - 0.4, tick=3, transaction_id="a",
    )
    _lower_cell(w, int(bx), int(by), sz0 - 0.8)
    refresh_support_after_terrain_mutation(
        w, cfg, cell_x=int(bx), cell_y=int(by),
        elevation_before=sz0 - 0.4, elevation_after=sz0 - 0.8, tick=3, transaction_id="b",
    )
    _tick(1)
    st = state_of(w)
    lost = [r for r in st.history if r.get("event_class") == EVENT_SUPPORT_LOST and r.get("entity_id") == "body-0"]
    dedup = [r for r in st.history if r.get("event_class") == EVENT_REFRESH_DEDUPLICATED and r.get("entity_id") == "body-0"]
    assert len(lost) == 1
    assert len(dedup) >= 1


def test_07_distant_entity_not_selected():
    from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
        EVENT_SUPPORT_LOST,
        refresh_support_after_terrain_mutation,
        state_of,
    )

    rt = _rt()
    w, cfg = rt.world, rt.config
    rt.body.x = 2.5
    rt.body.y = 2.5
    rt.body.z = 1.0
    rt.body.vz = 0.0
    rt.body.grounded = True
    w.detached_placement_body_refs = [("body-0", rt.body)]
    _lower_cell(w, 20, 20, 0.2)
    refresh_support_after_terrain_mutation(
        w, cfg, cell_x=20, cell_y=20,
        elevation_before=1.0, elevation_after=0.2, tick=4, transaction_id="far",
    )
    _tick(1)
    st = state_of(w)
    lost = [r for r in st.history if r.get("event_class") == EVENT_SUPPORT_LOST and r.get("entity_id") == "body-0"]
    assert lost == []
    assert bool(rt.body.grounded) is True


def test_08_snapshot_restore_no_replay():
    from copy import deepcopy
    from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
        refresh_support_after_terrain_mutation,
        serialize_state,
        restore_state,
        state_of,
    )

    rt = _rt()
    w, cfg = rt.world, rt.config
    rt.body.z = 1.0
    rt.body.vz = 0.0
    rt.body.grounded = True
    w.detached_placement_body_refs = [("body-0", rt.body)]
    _lower_cell(w, int(rt.body.x), int(rt.body.y), 0.3)
    refresh_support_after_terrain_mutation(
        w, cfg, cell_x=int(rt.body.x), cell_y=int(rt.body.y),
        elevation_before=1.0, elevation_after=0.3, tick=7, transaction_id="snap",
    )
    _tick(1)
    st = state_of(w)
    hist_len = len(st.history)
    counters = dict(st.counters)
    blob = deepcopy(serialize_state(st))
    w.release_and_excavation_support_loss_integration_state = None
    restore_state(w, blob, cfg)
    st2 = state_of(w)
    assert st2 is not None
    assert len(st2.history) == hist_len
    assert dict(st2.counters) == counters
    # Restore must not invent extra support-loss events.
    assert len(st2.history) == hist_len


def test_09_cognition_forbidden_tokens():
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS

    for tok in (
        "RELEASE_EXCAVATION_SUPPORT_LOSS_V1",
        "RELEASE_VERTICAL_ELIGIBILITY",
        "SUPPORT_LOST_TERRAIN_MUTATION",
        "AFFECTED_ENTITY_SELECTION",
        "CHANGED_REGION",
        "REFRESH_DEDUP",
        "TERRAIN_TRANSACTION_ID",
        "RELEASE_START_PENETRATION",
    ):
        assert tok in FORBIDDEN_TOKENS


def test_10_shared_chain_ids_unchanged():
    from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
        MECHANISM_ID as V1B,
        RECEIPT_KIND as V1B_R,
    )
    from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
        MECHANISM_ID as V1C,
        RECEIPT_KIND as V1C_R,
    )
    from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
        MECHANISM_ID as V1A,
    )

    assert V1A == "free_space_state_and_pe_authority_contract"
    assert V1B == "vertical_terrain_landing_contact_response"
    assert V1C == "vertical_impact_acoustic_emission"
    assert V1B_R == "VERTICAL_TERRAIN_LANDING_V1"
    assert V1C_R == "VERTICAL_IMPACT_ACOUSTIC_EMISSION"


def test_report_tick_budget():
    # Aggregate simulated ticks used by this module's probes.
    assert TICKS["n"] <= 350
    assert TICKS["n"] > 0
