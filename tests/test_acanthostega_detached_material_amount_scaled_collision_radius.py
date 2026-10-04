"""Detached material amount-scaled collision radius V1 — focused deterministic tests."""
from __future__ import annotations

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_detached_material_amount_scaled_collision_radius_config,
    )

    cfg = acanthostega_detached_material_amount_scaled_collision_radius_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _parent_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_event_driven_crowded_placement_retry_contract_config,
    )

    cfg = acanthostega_event_driven_crowded_placement_retry_contract_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(cfg=None, seed: int = 17):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=seed, config=cfg or _cfg())
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


def test_preset_inherits_crowding_and_matrix():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS,
        PUBLIC_PRESET_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT,
        acanthostega_detached_material_amount_scaled_collision_radius_config,
        acanthostega_event_driven_crowded_placement_retry_contract_config,
        acanthostega_active_locomotion_traction_vs_sliding_friction_config,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        detached_material_amount_scaled_collision_radius_is_active,
        PROFILE_VERSION,
        QUANTITY_REFERENCE,
        RADIUS_REFERENCE,
        MIN_RADIUS,
        MAX_RADIUS,
        SCALING_EXPONENT,
    )
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        event_driven_crowded_placement_retry_contract_is_active,
    )
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        active_locomotion_traction_vs_sliding_friction_is_active,
    )
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        repeated_conservative_surface_column_separation_is_active,
    )
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        detached_terrain_material_initial_placement_is_active,
        CANDIDATE_OFFSETS_V1,
    )
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS,
        normalize_preset_name,
        preset_canonical,
    )

    child = acanthostega_detached_material_amount_scaled_collision_radius_config()
    parent = acanthostega_event_driven_crowded_placement_retry_contract_config()
    altvs = acanthostega_active_locomotion_traction_vs_sliding_friction_config()
    assert child.public_preset == PUBLIC_PRESET_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
    assert parent.public_preset == PUBLIC_PRESET_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
    assert detached_material_amount_scaled_collision_radius_is_active(child) is True
    assert detached_material_amount_scaled_collision_radius_is_active(parent) is False
    assert detached_material_amount_scaled_collision_radius_is_active(altvs) is False
    assert detached_material_amount_scaled_collision_radius_is_active(tiktaalik_config()) is False
    assert event_driven_crowded_placement_retry_contract_is_active(child) is True
    assert active_locomotion_traction_vs_sliding_friction_is_active(child) is True
    assert repeated_conservative_surface_column_separation_is_active(child) is True
    assert detached_terrain_material_initial_placement_is_active(child) is True
    assert PROFILE_VERSION == "DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1"
    assert QUANTITY_REFERENCE == 1.0
    assert RADIUS_REFERENCE == 0.25
    assert MIN_RADIUS == 0.08
    assert MAX_RADIUS == 0.25
    assert abs(SCALING_EXPONENT - (1.0 / 3.0)) < 1e-15
    assert len(CANDIDATE_OFFSETS_V1) == 16
    assert (
        normalize_preset_name("DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1")
        == PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS)
    assert canon["model_line"] == "ACANTHOSTEGA"
    assert canon["parent"] == PUBLIC_PRESET_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT
    assert canon["builder"] == "acanthostega_detached_material_amount_scaled_collision_radius_config"
    mmap = canon["mechanisms"]
    assert mmap["detached_material_amount_scaled_collision_radius"] is True
    assert mmap["event_driven_crowded_placement_retry_contract"] is True
    assert mmap["active_locomotion_traction_vs_sliding_friction"] is True
    parent_map = preset_canonical(PUBLIC_PRESET_EVENT_DRIVEN_CROWDED_PLACEMENT_RETRY_CONTRACT)[
        "mechanisms"
    ]
    assert parent_map.get("detached_material_amount_scaled_collision_radius") is not True


def test_formula_clamps_mass_independent_invalid():
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        derive_detached_material_collision_radius,
        CLAMP_MIN,
        CLAMP_MAX,
        CLAMP_REFERENCE,
        CLAMP_SCALED,
        INVALID_QUANTITY,
    )
    import math

    d_ref = derive_detached_material_collision_radius(1.0)
    assert d_ref.valid and abs(d_ref.final_radius - 0.25) < 1e-12
    assert d_ref.clamp_status == CLAMP_REFERENCE
    assert abs(d_ref.exponent - (1.0 / 3.0)) < 1e-15

    d_mid = derive_detached_material_collision_radius(0.125)
    assert d_mid.valid
    expected = 0.25 * (0.125 ** (1.0 / 3.0))
    assert abs(d_mid.raw_radius - expected) < 1e-12
    assert abs(d_mid.final_radius - expected) < 1e-12
    assert d_mid.clamp_status == CLAMP_SCALED

    d_tiny = derive_detached_material_collision_radius(1e-9)
    assert d_tiny.valid and abs(d_tiny.final_radius - 0.08) < 1e-12
    assert d_tiny.clamp_status == CLAMP_MIN

    d_big = derive_detached_material_collision_radius(27.0)
    assert d_big.valid and abs(d_big.final_radius - 0.25) < 1e-12
    assert d_big.clamp_status == CLAMP_MAX

    # Mass/composition do not enter the helper — quantity alone.
    assert derive_detached_material_collision_radius(0.2).final_radius == derive_detached_material_collision_radius(
        0.2
    ).final_radius

    for bad in (0.0, -1.0, float("nan"), float("inf")):
        d = derive_detached_material_collision_radius(bad)
        assert d.valid is False
        assert d.clamp_status == INVALID_QUANTITY
        assert not math.isfinite(d.final_radius)


def test_parent_keeps_fixed_radius_child_scales():
    parent = _rt(_parent_cfg(), seed=21)
    child = _rt(_cfg(), seed=21)
    out_p = _sep(parent, 10, 10, t=0.05, tick=1)
    out_c = _sep(child, 10, 10, t=0.05, tick=1)
    assert out_p["receipt"]["status"] == "COMMITTED"
    assert out_c["receipt"]["status"] == "COMMITTED"
    obj_p = next(o for o in parent.world.resource_objects if o.object_id == out_p["object_id"])
    obj_c = next(o for o in child.world.resource_objects if o.object_id == out_c["object_id"])
    assert abs(float(obj_p.collision_radius) - 0.25) < 1e-15
    assert float(obj_c.collision_radius) < 0.25 - 1e-6
    assert abs(float(obj_c.quantity) - float(obj_p.quantity)) < 1e-12
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        derive_detached_material_collision_radius,
    )

    d = derive_detached_material_collision_radius(float(obj_c.quantity))
    assert abs(float(obj_c.collision_radius) - d.final_radius) < 1e-12
    assert abs(float(obj_c.vertical_half_extent) - float(obj_c.collision_radius)) < 1e-12
    assert abs(float(obj_c.optical_radius) - float(obj_p.optical_radius)) < 1e-12


def test_vertical_extent_centre_z_no_free_lift_and_sticky():
    from mechanistic_mind.physical_system.flat_ground_gravity import ensure_object_vertical
    from mechanistic_mind.physical_system.surface_elevation_support import surface_support_height

    rt = _rt(seed=33)
    out = _sep(rt, 10, 10, t=0.05, tick=2)
    assert out["receipt"]["status"] == "COMMITTED"
    obj = next(o for o in rt.world.resource_objects if o.object_id == out["object_id"])
    support = surface_support_height(rt.world, obj.x, obj.y, config=rt.config)
    assert abs(float(obj.z) - float(support)) < 1e-9
    r = float(obj.collision_radius)
    assert abs(float(obj.vertical_half_extent) - r) < 1e-12
    # Lazy ensure must not reset to 0.25
    ensure_object_vertical(obj, rt.config)
    assert abs(float(obj.vertical_half_extent) - r) < 1e-12
    assert r < 0.25


def test_radius_stable_across_ticks_and_snapshot():
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _rt(seed=37)
    out = _sep(rt, 10, 10, t=0.08, tick=1)
    obj = next(o for o in rt.world.resource_objects if o.object_id == out["object_id"])
    r0 = float(obj.collision_radius)
    v0 = float(obj.vertical_half_extent)
    q0 = float(obj.quantity)
    m0 = float(obj.mass)
    for _ in range(3):
        rt.step()
        _tick()
    obj2 = next(o for o in rt.world.resource_objects if o.object_id == obj.object_id)
    assert abs(float(obj2.collision_radius) - r0) < 1e-15
    assert abs(float(obj2.vertical_half_extent) - v0) < 1e-15
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    obj3 = next(o for o in rt2.world.resource_objects if o.object_id == obj.object_id)
    assert abs(float(obj3.collision_radius) - r0) < 1e-15
    assert abs(float(obj3.vertical_half_extent) - v0) < 1e-15
    assert abs(float(obj3.quantity) - q0) < 1e-12
    assert abs(float(obj3.mass) - m0) < 1e-12
    # Restore must not recompute from quantity under a different formula
    assert abs(float(obj3.collision_radius) - r0) < 1e-15


def test_legacy_missing_radius_defaults_to_025():
    from mechanistic_mind.physical_system.resource_objects import ResourceObject

    obj = ResourceObject.from_dict(
        {
            "object_id": "resource-legacy-1",
            "x": 1.0,
            "y": 1.0,
            "mass": 1.0,
            "quantity": 0.05,
            "composition": [{"component_id": "stone", "amount": 0.05}],
            "physical_state": "FREE_STATIC",
            # collision_radius omitted
        }
    )
    assert abs(float(obj.collision_radius) - 0.25) < 1e-15


def test_placement_uses_derived_radius_smaller_fits():
    """Clearance where r=0.25 fails but smaller derived radius fits."""
    from mechanistic_mind.physical_system.resource_objects import (
        ResourceObject,
        MaterialComponent,
        PHYSICAL_STATE_FREE_STATIC,
        CANONICAL_COLLISION_RADIUS,
    )
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        CANDIDATE_OFFSETS_V1,
        OVERLAP_MARGIN,
    )
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        derive_detached_material_collision_radius,
    )

    d = derive_detached_material_collision_radius(0.05)
    small_r = float(d.final_radius)
    assert small_r < 0.25

    def _place_with(cfg_factory, seed=55):
        rt = _rt(cfg_factory(), seed=seed)
        thresh_parent = (0.25 + 0.25) * OVERLAP_MARGIN
        thresh_child = (small_r + 0.25) * OVERLAP_MARGIN
        assert thresh_child < thresh_parent
        dist = 0.5 * (thresh_child + thresh_parent)
        blockers = []
        for i, (dx, dy) in enumerate(CANDIDATE_OFFSETS_V1):
            if i == 0:
                bx, by = 10.5 + dist, 10.5
            else:
                bx, by = 10.5 + dx, 10.5 + dy
            blockers.append(
                ResourceObject(
                    object_id=f"resource-block-{i:03d}",
                    x=bx,
                    y=by,
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
        return _sep(rt, 10, 10, t=0.05, tick=1), rt

    out_p, _ = _place_with(_parent_cfg)
    out_c, rt_c = _place_with(_cfg)
    assert out_p["receipt"]["status"] == "REJECTED"
    assert out_c["receipt"]["status"] == "COMMITTED"
    obj = next(o for o in rt_c.world.resource_objects if o.object_id == out_c["object_id"])
    assert abs(float(obj.collision_radius) - small_r) < 1e-9
    place = out_c["receipt"].get("placement") or {}
    assert int(place.get("candidate_index", -1)) == 0


def test_failed_placement_atomic_and_non_resize_debt():
    from mechanistic_mind.physical_system.resource_objects import (
        ResourceObject,
        MaterialComponent,
        PHYSICAL_STATE_FREE_STATIC,
        CANONICAL_COLLISION_RADIUS,
        CANONICAL_OPTICAL_RADIUS,
    )
    from mechanistic_mind.physical_system.detached_terrain_material_initial_placement import (
        CANDIDATE_OFFSETS_V1,
    )
    from mechanistic_mind.physical_system.conservative_surface_column_transfer import _resolved

    rt = _rt(seed=61)
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
    before = _resolved(rt.world, (10, 10))
    elev0 = float(before["elevation"])
    next_id0 = int(getattr(rt.world, "resource_object_next_id", 1) or 1)
    n0 = len(rt.world.resource_objects or [])
    out = _sep(rt, 10, 10, t=0.05, tick=4)
    assert out["receipt"]["status"] == "REJECTED"
    after = _resolved(rt.world, (10, 10))
    assert abs(float(after["elevation"]) - elev0) < 1e-12
    assert len(rt.world.resource_objects) == n0
    assert int(getattr(rt.world, "resource_object_next_id", 1) or 1) == next_id0

    rt2 = _rt(seed=62)
    out2 = _sep(rt2, 12, 12, t=0.1, tick=1)
    assert out2["receipt"]["status"] == "COMMITTED"
    obj = next(o for o in rt2.world.resource_objects if o.object_id == out2["object_id"])
    r0 = float(obj.collision_radius)
    opt0 = float(obj.optical_radius)
    assert abs(opt0 - CANONICAL_OPTICAL_RADIUS) < 1e-15
    # Simulate quantity change without COMBINE (deposition-like amount edit) — radius sticky.
    obj.quantity = float(obj.quantity) * 0.5
    obj.mass = float(obj.mass) * 0.5
    assert abs(float(obj.collision_radius) - r0) < 1e-15
    assert abs(float(obj.optical_radius) - opt0) < 1e-15


def test_contact_uses_per_object_radius():
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        object_contact_geometry,
        ensure_object_collision_radius,
    )

    rt = _rt(seed=71)
    out = _sep(rt, 10, 10, t=0.05, tick=1)
    obj = next(o for o in rt.world.resource_objects if o.object_id == out["object_id"])
    r = float(ensure_object_collision_radius(obj))
    assert r < 0.25
    geom = object_contact_geometry(obj)
    assert abs(float(geom["radius"]) - r) < 1e-12


def test_cognition_privacy_banner_constants():
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        BANNER,
        RESEARCHER_FLAGS,
        RECEIPT_KIND,
        researcher_summary,
        ensure_detached_material_amount_scaled_collision_radius_for_runtime,
    )
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS

    assert "CREATION-TIME ONLY" in BANNER
    assert RESEARCHER_FLAGS["agent_accessible"] is False
    assert RECEIPT_KIND == "DETACHED_MATERIAL_SIZE_GEOMETRY"
    assert "detached_material_amount_scaled_collision_radius" in FORBIDDEN_TOKENS
    assert "DETACHED_MATERIAL_SIZE_GEOMETRY" in FORBIDDEN_TOKENS
    rt = _rt(seed=80)
    ensure_detached_material_amount_scaled_collision_radius_for_runtime(rt.world, rt.config)
    summ = researcher_summary(rt.world)
    assert summ is not None
    assert summ["agent_accessible"] is False
    assert summ["researcher_only"] is True
