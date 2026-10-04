"""Detached terrain material initial placement V1 — focused deterministic tests."""
from __future__ import annotations

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_detached_terrain_material_initial_placement_config,
    )

    cfg = acanthostega_detached_terrain_material_initial_placement_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(seed: int = 17):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=seed, config=_cfg())
    rt.body.x, rt.body.y = 2.5, 2.5
    rt.world.detached_placement_body_refs = [("body-0", rt.body)]
    return rt


def _sep(rt, cx=10, cy=10, t=0.05, tick=1, **kw):
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        apply_surface_material_separation,
    )

    out = apply_surface_material_separation(
        rt.world,
        rt.config,
        cell_x=cx,
        cell_y=cy,
        requested_thickness=t,
        tick=tick,
        body_refs=list(getattr(rt.world, "detached_placement_body_refs", None) or []),
        **kw,
    )
    _tick()
    return out


def test_preset_parent_isolation_and_tiktaalik():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT,
        PUBLIC_PRESET_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION,
        acanthostega_detached_terrain_material_initial_placement_config,
        acanthostega_held_mediated_surface_exertion_integration_config,
    )
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        detached_terrain_material_initial_placement_is_active,
        PLACEMENT_POLICY,
        MAX_CANDIDATES,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT,
        normalize_preset_name,
        preset_canonical,
    )

    child = acanthostega_detached_terrain_material_initial_placement_config()
    parent = acanthostega_held_mediated_surface_exertion_integration_config()
    assert child.public_preset == PUBLIC_PRESET_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
    assert parent.public_preset == PUBLIC_PRESET_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION
    assert detached_terrain_material_initial_placement_is_active(child) is True
    assert detached_terrain_material_initial_placement_is_active(parent) is False
    assert detached_terrain_material_initial_placement_is_active(tiktaalik_config()) is False
    assert MAX_CANDIDATES == 16
    assert PLACEMENT_POLICY == "DETACHED_TERRAIN_PLACEMENT_POST_MUTATION_SUPPORT_V1"
    assert (
        normalize_preset_name("DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT_V1")
        == PRESET_ACANTHOSTEGA_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_DETACHED_TERRAIN_MATERIAL_INITIAL_PLACEMENT)
    assert canon["builder"] == "acanthostega_detached_terrain_material_initial_placement_config"
    assert canon["mechanisms"]["detached_terrain_material_initial_placement"] is True
    assert canon["parent"] == PUBLIC_PRESET_HELD_MEDIATED_SURFACE_EXERTION_INTEGRATION


def test_flat_and_support_oracle_and_zero_velocity():
    from mechanistic_mind.physical_system.surface_elevation_support import surface_support_height

    rt = _rt(17)
    out = _sep(rt, 10, 10, 0.05, tick=5)
    rec = out["receipt"]
    assert rec["status"] == "COMMITTED"
    place = rec.get("placement") or {}
    assert place.get("status") == "PLACED"
    assert place.get("accepted") is True
    obj = next(o for o in rt.world.resource_objects if o.object_id == out["object_id"])
    h = surface_support_height(rt.world, obj.x, obj.y, config=rt.config)
    assert abs(float(obj.z) - float(h)) < 1e-9
    assert abs(float(place["support_z"]) - float(h)) < 1e-9
    assert float(obj.vx) == 0.0 and float(obj.vy) == 0.0 and float(obj.vz) == 0.0
    assert obj.physical_state == "FREE_STATIC"
    assert obj.grounded is True
    assert int(obj.creation_tick) == 5
    assert int(obj.dynamics_eligible_tick) == 6
    assert abs(float(obj.collision_radius) - 0.25) < 1e-15
    assert rec["conservation"]["verified"] is True


def test_body_overlap_rejects_candidate_then_fallback_or_fail():
    rt = _rt(19)
    # Park body on cell centre so candidate 0 fails; offset candidates may succeed.
    rt.body.x, rt.body.y = 10.5, 10.5
    rt.world.detached_placement_body_refs = [("body-0", rt.body)]
    out = _sep(rt, 10, 10, 0.05, tick=1)
    rec = out["receipt"]
    place = rec.get("placement") or {}
    if rec["status"] == "COMMITTED":
        assert int(place.get("candidate_index", 0)) >= 1
        obj = next(o for o in rt.world.resource_objects if o.object_id == out["object_id"])
        import math
        assert math.hypot(obj.x - rt.body.x, obj.y - rt.body.y) > 0.5
    else:
        assert rec["status"] == "REJECTED"
        assert rec.get("rejection_reason") == "UNSAFE_OBJECT_PLACEMENT"


def test_object_overlap_all_candidates_reject_no_id_no_mutation():
    from mechanistic_mind.physical_system.resource_objects import (
        ResourceObject,
        MaterialComponent,
        CANONICAL_COLLISION_RADIUS,
        PHYSICAL_STATE_FREE_STATIC,
    )
    from mechanistic_mind.physical_system.conservative_surface_column_transfer import _resolved
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        CANDIDATE_OFFSETS_V1,
    )

    rt = _rt(23)
    before = _resolved(rt.world, (10, 10))
    elev0 = float(before["elevation"])
    next_id0 = int(getattr(rt.world, "resource_object_next_id", 1) or 1)
    n0 = len(rt.world.resource_objects or [])
    blockers = []
    for i, (dx, dy) in enumerate(CANDIDATE_OFFSETS_V1):
        blockers.append(
            ResourceObject(
                object_id=f"resource-block-{i:03d}",
                x=10.5 + dx,
                y=10.5 + dy,
                mass=1.0,
                quantity=1.0,
                composition=(MaterialComponent("stone", 1.0),),
                physical_state=PHYSICAL_STATE_FREE_STATIC,
                collision_radius=CANONICAL_COLLISION_RADIUS,
                z=0.0,
                grounded=True,
            )
        )
    rt.world.resource_objects = list(rt.world.resource_objects or []) + blockers
    out = _sep(rt, 10, 10, 0.05, tick=2)
    rec = out["receipt"]
    assert rec["status"] == "REJECTED"
    assert rec.get("rejection_reason") == "UNSAFE_OBJECT_PLACEMENT"
    after = _resolved(rt.world, (10, 10))
    assert abs(float(after["elevation"]) - elev0) < 1e-12
    assert len(rt.world.resource_objects) == n0 + len(blockers)
    assert int(getattr(rt.world, "resource_object_next_id", 1) or 1) == next_id0


def test_same_tick_dynamics_ineligible_then_eligible():
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        object_dynamics_eligible,
    )
    from mechanistic_mind.physical_system.flat_ground_gravity import integrate_free_objects_vertical

    rt = _rt(29)
    out = _sep(rt, 10, 10, 0.05, tick=7)
    assert out["receipt"]["status"] == "COMMITTED"
    obj = next(o for o in rt.world.resource_objects if o.object_id == out["object_id"])
    assert object_dynamics_eligible(obj, 7) is False
    assert object_dynamics_eligible(obj, 8) is True
    # Force FGG integrate at creation tick — newborn skipped
    st = getattr(rt.world, "flat_ground_gravity_state", None)
    if st is not None:
        st.last_vertical_integrated_tick = 6
    rows = integrate_free_objects_vertical(rt.world, rt.config, tick=7)
    ids = {r.get("entity_id") for r in rows}
    assert obj.object_id not in ids


def test_snapshot_restore_preserves_eligibility():
    rt = _rt(31)
    out = _sep(rt, 12, 12, 0.05, tick=3)
    assert out["receipt"]["status"] == "COMMITTED"
    oid = out["object_id"]
    snap = rt.snapshot()
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt2 = PhysicalSystemRuntime.restore(snap)
    obj = next(o for o in rt2.world.resource_objects if o.object_id == oid)
    assert int(obj.dynamics_eligible_tick) == 4
    assert int(obj.creation_tick) == 3
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        object_dynamics_eligible,
        detached_terrain_material_initial_placement_is_active,
    )

    assert detached_terrain_material_initial_placement_is_active(rt2.config) is True
    assert object_dynamics_eligible(obj, 3) is False
    assert object_dynamics_eligible(obj, 4) is True


def test_multi_separation_deterministic_ids_and_same_tick_obstacles():
    rt = _rt(37)
    out1 = _sep(rt, 10, 10, 0.05, tick=9)
    out2 = _sep(rt, 14, 14, 0.05, tick=9)
    assert out1["receipt"]["status"] == "COMMITTED"
    assert out2["receipt"]["status"] == "COMMITTED"
    assert out1["object_id"] < out2["object_id"]
    assert out1["object_id"] != out2["object_id"]


def test_parent_legacy_placement_still_uses_elev_after():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_held_mediated_surface_exertion_integration_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.conservative_surface_material_separation import (
        apply_surface_material_separation,
    )
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        detached_terrain_material_initial_placement_is_active,
    )

    cfg = acanthostega_held_mediated_surface_exertion_integration_config()
    cfg.cognition.cognition_enabled = False
    assert detached_terrain_material_initial_placement_is_active(cfg) is False
    rt = PhysicalSystemRuntime(seed=41, config=cfg)
    rt.body.x, rt.body.y = 2.5, 2.5
    out = apply_surface_material_separation(
        rt.world, rt.config, cell_x=10, cell_y=10, requested_thickness=0.05, tick=1
    )
    assert out["receipt"]["status"] == "COMMITTED"
    assert out["receipt"].get("placement") is None
    obj = next(o for o in rt.world.resource_objects if o.object_id == out["object_id"])
    assert obj.dynamics_eligible_tick is None  # legacy immediate
