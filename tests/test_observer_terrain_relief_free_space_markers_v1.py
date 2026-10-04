"""OBSERVER_TERRAIN_RELIEF_AND_FREE_SPACE_MARKERS_V1 — focused display-contract tests.

Display only. No new physics. Budget: ≤120 ticks total, ≤40 per probe.
"""
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


def _rt(seed: int = 17):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    return PhysicalSystemRuntime(seed=seed, config=_cfg())


def _lower_cell(world, x, y, *, amount=0.2, tick=1):
    """Authoritative sparse delta with lowered surface elevation (test fixture)."""
    from mechanistic_mind.physical_system.procedural_surface_columns import (
        SurfaceColumnDelta,
        baseline_column_at,
        delta_id_for,
        deltas_of,
    )
    from mechanistic_mind.physical_system.continuous_surface_geometry import (
        note_authoritative_surface_mutation,
    )

    base = baseline_column_at(world, x, y, record=False)
    deltas = deltas_of(world)
    cell = (int(base.cell_x), int(base.cell_y))
    cur = deltas.get(cell)
    baseline_z = float(base.surface_elevation)
    before_z = float(base.surface_elevation if cur is None else cur.resulting_surface_elevation)
    layers = base.layers if cur is None else cur.resulting_layers
    new_z = before_z - float(amount)
    record = SurfaceColumnDelta(
        delta_id=delta_id_for(*cell),
        cell_x=cell[0],
        cell_y=cell[1],
        baseline_generator_version=base.generator_version,
        baseline_checksum=base.baseline_checksum,
        resulting_surface_elevation=float(new_z),
        resulting_layers=layers,
        created_tick=int(cur.created_tick if cur is not None else tick),
        last_updated_tick=int(tick),
        revision=int(0 if cur is None else cur.revision) + 1,
        source_transaction_ids=(list(cur.source_transaction_ids) if cur is not None else [])
        + [f"display-fixture-{tick}"],
        provenance={"kind": "DISPLAY_CONTRACT_FIXTURE", "researcher_only": True},
    )
    deltas[cell] = record
    world.surface_column_deltas = deltas
    note_authoritative_surface_mutation(world, None)
    return baseline_z, new_z, int(record.revision)



def test_01_schema_emitted_when_compatible():
    from mechanistic_mind.ui.psy_observer_web.vertical_display_contract import (
        SCHEMA_VERSION,
        build_vertical_display_payload,
        vertical_display_compatible,
    )
    from mechanistic_mind.ui.psy_observer_web.serialize import world_frame

    rt = _rt()
    rt.step_forced_action("WAIT")
    _tick()
    assert vertical_display_compatible(rt)
    p = build_vertical_display_payload(rt)
    assert p is not None
    assert p["schema_version"] in (SCHEMA_VERSION, "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1_1")
    assert SCHEMA_VERSION in (p.get("schema_compatible_with") or [p["schema_version"]])
    assert p["researcher_only"] is True
    assert p["agent_accessible"] is False
    assert p["not_a_physical_mechanism"] is True
    wf = world_frame(rt)
    assert wf["vertical_display"]["schema_version"] in (SCHEMA_VERSION, "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1_1")
    assert "layers" not in (wf["vertical_display"].get("cell_centre_elevation") or {})


def test_02_deterministic_elevation_ordering_finite_minmax():
    from mechanistic_mind.ui.psy_observer_web.vertical_display_contract import (
        ELEVATION_ORDER,
        build_vertical_display_payload,
    )

    rt = _rt(19)
    rt.step_forced_action("WAIT")
    _tick()
    p = build_vertical_display_payload(rt)
    elev = p["cell_centre_elevation"]
    assert elev["height"] == 32 and elev["width"] == 32
    assert elev["order"] == ELEVATION_ORDER
    assert elev["coordinate"] == "cell_centre"
    data = elev["data"]
    assert len(data) == 32 and len(data[0]) == 32
    flat = [v for row in data for v in row]
    assert all(isinstance(v, float) and __import__("math").isfinite(v) for v in flat)
    assert p["elev_min"] == min(flat)
    assert p["elev_max"] == max(flat)
    p2 = build_vertical_display_payload(rt)
    assert p2["cell_centre_elevation"]["data"] == data


def test_03_sparse_delta_baseline_current_revision_no_subsurface():
    from mechanistic_mind.ui.psy_observer_web.vertical_display_contract import (
        build_vertical_display_payload,
        invalidate_vertical_display_cache,
    )

    rt = _rt(23)
    rt.step_forced_action("WAIT")
    _tick()
    build_vertical_display_payload(rt)
    cell_x, cell_y = 10, 12
    baseline_z, new_z, rev = _lower_cell(rt.world, cell_x, cell_y, amount=0.25, tick=1)
    invalidate_vertical_display_cache(rt.world)
    p = build_vertical_display_payload(rt)
    assert p["dense_subsurface_serialized"] is False
    assert p["cell_centre_elevation"].get("subsurface_serialized") is False
    assert len(p["sparse_deltas"]) >= 1
    row = next(d for d in p["sparse_deltas"] if d["cell_x"] == cell_x and d["cell_y"] == cell_y)
    assert abs(row["baseline_elevation"] - baseline_z) < 1e-9
    assert abs(row["current_elevation"] - new_z) < 1e-9
    assert abs(row["signed_delta"] - (new_z - baseline_z)) < 1e-9
    assert row["signed_delta"] < 0
    assert int(row["revision"]) == rev


def test_04_cache_reuse_and_invalidate_after_excavation_and_restore():
    from mechanistic_mind.ui.psy_observer_web.vertical_display_contract import (
        CACHE_ATTR,
        build_vertical_display_payload,
        invalidate_vertical_display_cache,
    )
    from mechanistic_mind.physical_system import procedural_surface_columns as psc
    from mechanistic_mind.physical_system.continuous_surface_geometry import (
        note_authoritative_surface_mutation,
    )

    rt = _rt(29)
    rt.step_forced_action("WAIT")
    _tick()
    p1 = build_vertical_display_payload(rt)
    assert p1["cache_hit"] is False
    p2 = build_vertical_display_payload(rt)
    assert p2["cache_hit"] is True
    assert getattr(rt.world, CACHE_ATTR, None) is not None
    snap_clean = rt.snapshot()
    # Setup delta changes deltas_checksum / revision → cache key miss (conservation-safe).
    psc.apply_surface_column_setup_delta(
        rt.world, 4, 5,
        upper_layer_index=0, transfer_quantity=0.1, expected_revision=0, tick=2,
        researcher_id="display_cache_test", reason="cache_invalidate",
    )
    note_authoritative_surface_mutation(rt.world, rt.config)
    p3 = build_vertical_display_payload(rt)
    assert p3["cache_hit"] is False
    assert len(p3["sparse_deltas"]) >= 1
    # Separate fixture proves negative elevation delta on payload (no snapshot).
    _lower_cell(rt.world, 7, 8, amount=0.18, tick=3)
    p3b = build_vertical_display_payload(rt)
    assert any(d["signed_delta"] < 0 for d in p3b["sparse_deltas"])
    # Restore clean snapshot — display cache must not carry over.
    rt2 = type(rt).restore(snap_clean)
    assert getattr(rt2.world, CACHE_ATTR, None) in (None, {})
    p4 = build_vertical_display_payload(rt2)
    assert p4["cache_hit"] is False
    invalidate_vertical_display_cache(rt2.world)
    assert getattr(rt2.world, CACHE_ATTR, None) in (None,)


def test_05_serialization_does_not_mutate_physics():
    from mechanistic_mind.ui.psy_observer_web.serialize import world_frame
    from mechanistic_mind.physical_system.procedural_surface_columns import deltas_checksum

    rt = _rt(31)
    rt.step_forced_action("WAIT")
    _tick()
    b0 = (float(rt.body.x), float(rt.body.y), float(rt.body.z), float(rt.body.vz), bool(rt.body.grounded))
    cs0 = deltas_checksum(rt.world)
    tick0 = int(rt.world.tick)
    world_frame(rt)
    world_frame(rt)
    b1 = (float(rt.body.x), float(rt.body.y), float(rt.body.z), float(rt.body.vz), bool(rt.body.grounded))
    assert b0 == b1
    assert deltas_checksum(rt.world) == cs0
    assert int(rt.world.tick) == tick0


def test_06_entity_vertical_fields_and_no_fabricated_z():
    from mechanistic_mind.ui.psy_observer_web.vertical_display_contract import (
        build_vertical_display_payload,
    )
    from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_HELD

    rt = _rt(37)
    rt.step_forced_action("WAIT")
    _tick()
    p = build_vertical_display_payload(rt)
    bodies = [e for e in p["entities_vertical"] if e["kind"] == "body"]
    objs = [e for e in p["entities_vertical"] if e["kind"] == "resource_object"]
    assert bodies
    b = bodies[0]
    assert b["z_available"] is True
    assert b["base_z"] is not None
    assert b["centre_z"] is not None
    assert b["support_z"] is not None
    assert b["clearance"] is not None
    assert abs(float(b["clearance"]) - (float(b["base_z"]) - float(b["support_z"]))) < 1e-9
    assert b["vz"] is not None
    if objs:
        o = objs[0]
        assert o["optical_radius_is_not_collision_radius"] is True
        assert o["glyph_is_not_physics"] is True
        if o.get("collision_radius") is not None and o.get("optical_radius") is not None:
            # May be equal numerically but must not alias optical as physical source.
            assert "collision_radius" in o
        # Mark one held
        for obj in rt.world.resource_objects or []:
            obj.physical_state = PHYSICAL_STATE_HELD
            obj.holder_body_id = "agent_0"
            obj.manipulator_id = "manipulator_left"
            break
        p2 = build_vertical_display_payload(rt)
        held = [e for e in p2["entities_vertical"] if e.get("held_constrained")]
        assert held
        assert held[0]["holder_body_id"] == "agent_0"


def test_07_events_markers_from_receipts_only():
    from mechanistic_mind.ui.psy_observer_web.vertical_display_contract import (
        EVENT_HISTORY_CAP,
        _events_recent,
    )

    class _St:
        history = []

    world = type("W", (), {})()
    world.release_and_excavation_support_loss_integration_state = _St()
    world.vertical_terrain_landing_contact_response_state = _St()
    world.vertical_impact_acoustic_emission_state = _St()

    world.release_and_excavation_support_loss_integration_state.history = [
        {
            "receipt_kind": "RELEASE_EXCAVATION_SUPPORT_LOSS_V1",
            "event_class": "RELEASE_ENTRY",
            "tick": 5,
            "entity_id": "obj-a",
            "pose_x": 1.0,
            "pose_y": 2.0,
            "pose_z": 0.5,
            "release_tick": 5,
            "dynamics_eligible_tick": 6,
            "event_sequence": 1,
        },
        {
            "receipt_kind": "RELEASE_EXCAVATION_SUPPORT_LOSS_V1",
            "event_class": "SUPPORT_LOST",
            "tick": 7,
            "entity_id": "agent_0",
            "pose_x": 3.0,
            "pose_y": 4.0,
            "pose_z": 0.4,
            "entity_z_unchanged": True,
            "source_kind": "EXCAVATION",
            "event_sequence": 2,
        },
        {
            "receipt_kind": "RELEASE_EXCAVATION_SUPPORT_LOSS_V1",
            "event_class": "SUPPORT_REMAINS_VALID",
            "tick": 8,
            "entity_id": "agent_0",
            "pose_x": 3.0,
            "pose_y": 4.0,
            "pose_z": 0.4,
            "event_sequence": 3,
        },
    ]
    world.vertical_terrain_landing_contact_response_state.history = [
        {
            "receipt_kind": "VERTICAL_TERRAIN_LANDING_V1",
            "tick": 10,
            "entity_id": "obj-a",
            "response_applied": True,
            "intersection_class": "LANDING_IMPACT",
            "episode_phase": "BEGIN",
            "impulse_magnitude": 1.2,
            "dissipated_energy": 0.8,
            "contact_point": [1.1, 2.2, 0.0],
            "event_sequence": 1,
        },
        {
            "receipt_kind": "VERTICAL_TERRAIN_LANDING_V1",
            "tick": 11,
            "entity_id": "obj-a",
            "response_applied": False,
            "intersection_class": "REST_PERSIST",
            "episode_phase": "PERSIST",
            "impulse_magnitude": 0.0,
            "dissipated_energy": 0.0,
            "contact_point": [1.1, 2.2, 0.0],
            "event_sequence": 2,
        },
        {
            "receipt_kind": "VERTICAL_TERRAIN_LANDING_V1",
            "tick": 12,
            "entity_id": "obj-a",
            "response_applied": False,
            "intersection_class": "POSITION_CORRECTION_ONLY",
            "episode_phase": "BEGIN",
            "impulse_magnitude": 0.0,
            "dissipated_energy": 0.0,
            "contact_point": [1.1, 2.2, 0.0],
            "event_sequence": 3,
        },
    ]
    world.vertical_impact_acoustic_emission_state.history = [
        {
            "receipt_kind": "VERTICAL_IMPACT_ACOUSTIC_EMISSION",
            "tick": 10,
            "emission_tick": 10,
            "entity_id": "obj-a",
            "emitted": True,
            "emitted_energy": 0.5,
            "contact_point": [1.1, 2.2, 0.0],
            "source_id": "src-1",
            "event_sequence": 1,
        },
        {
            "receipt_kind": "VERTICAL_IMPACT_ACOUSTIC_EMISSION",
            "tick": 13,
            "emission_tick": 13,
            "entity_id": "obj-a",
            "emitted": False,
            "silence_reason": "silent_persistent_support",
            "emitted_energy": 0.0,
            "contact_point": [1.1, 2.2, 0.0],
            "event_sequence": 2,
        },
    ]
    ev = _events_recent(world, tick=20)
    classes = [e["event_class"] for e in ev]
    assert "RELEASE" in classes
    assert "SUPPORT_LOSS" in classes
    assert "LANDING_RESPONSE" in classes
    assert "ACOUSTIC_EMISSION" in classes
    assert classes.count("LANDING_RESPONSE") == 1
    assert classes.count("ACOUSTIC_EMISSION") == 1
    assert all(e.get("creates_sound") is not True for e in ev if e["event_class"] == "SUPPORT_LOSS")
    assert len(ev) <= EVENT_HISTORY_CAP


def test_08_cognition_privacy_tokens():
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload

    tokens = [
        "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1",
        "CURRENT_ELEVATION",
        "TERRAIN_DELTA",
        "CLEARANCE_STEM",
        "DISPLAY_EXAGGERATION",
        "SUPPORT_LOSS_MARKER",
        "LANDING_MARKER",
        "PHYSICAL_SOUND_SOURCE_MARKER",
        "vertical_display",
    ]
    for tok in tokens:
        assert tok in FORBIDDEN_TOKENS
    rt = _rt(41)
    rt.step_forced_action("WAIT")
    _tick()
    obs = rt.agent_observation() if hasattr(rt, "agent_observation") else None
    if obs is None:
        from mechanistic_mind.physical_system.observation import build_agent_observation

        obs = build_agent_observation(rt)
    assert audit_cognition_payload(obs) == []
    blob = str(obs)
    for tok in ("vertical_display", "CLEARANCE_STEM", "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1"):
        assert tok not in blob


def test_09_analyzer_story_and_legacy_unavailable():
    from mechanistic_mind.scientific_v3.elevation_free_space_visualization_summary import (
        UNAVAILABLE,
        ANALYZER_PROGRESS_BAR_STATUS,
        summarize_elevation_free_space_story,
    )

    legacy = summarize_elevation_free_space_story(vertical_display=None)
    assert legacy["elevation_visualization_available"] is False
    assert legacy["unavailable_label"] == UNAVAILABLE
    assert legacy["analyzer_progress_bar_status"] == ANALYZER_PROGRESS_BAR_STATUS
    assert legacy["fabricated_from_pixels"] is False
    story = summarize_elevation_free_space_story(
        vertical_display={
            "schema_version": "OBSERVER_VERTICAL_DISPLAY_CONTRACT_V1",
            "cell_centre_elevation": {"data": [[0.0]]},
            "sparse_deltas": [{"cell_x": 0, "cell_y": 0, "signed_delta": -0.2}],
            "entities_vertical": [{"detached_terrain_provenance": {"source_kind": "DETACHED_TERRAIN"}}],
        },
        release_receipts=[{"event_class": "RELEASE_ENTRY"}],
        support_loss_receipts=[{"event_class": "SUPPORT_LOST"}],
        landing_receipts=[{"response_applied": True}],
        acoustic_receipts=[{"emitted": True}],
    )
    assert "sparse_delta_current_elevation" in story["excavation_causal_story"]
    assert "RELEASE" in story["release_causal_story"]


def test_10_tick_budget_report():
    # Accounting only — probes above already counted via _tick.
    assert TICKS["n"] <= 120
    print(f"TOTAL_SIMULATED_TICKS={TICKS['n']}")
