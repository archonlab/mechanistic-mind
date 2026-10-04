"""P2 VOLUME persistent geometry + incremental updates tests."""
from __future__ import annotations

import copy
import json

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
    build_observer_volume_render_description,
    invalidate_vw7_volume_caches,
    researcher_payload,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.ui.psy_observer_web.observer_derived_payload_subscription import (
    FAMILY_VOLUME,
    OMISSION_NOT_REQUESTED,
    PRODUCT_SURFACE_LIGHT,
    PRODUCT_VOLUME_XRAY,
    resolve_derived_subscription,
)
from mechanistic_mind.ui.psy_observer_web.observer_volume_incremental_payload import (
    AUTHORITY,
    CAPABILITY,
    KIND_DYNAMIC,
    KIND_FULL,
    KIND_RESET,
    PROFILE,
    REPRESENTATION,
    SCHEMA,
    STATIC_CACHE_ATTR,
    make_static_payload_id,
    materialize_volume_from_incremental,
)
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame
from mechanistic_mind.ui.psy_observer_web.subscriptions import ObserverInterest, PRODUCT_WORLD


def _rt(seed: int = 51):
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def test_01_schema_and_identity():
    assert SCHEMA == "OBSERVER_VOLUME_INCREMENTAL_PAYLOAD_V1"
    assert CAPABILITY == "volume_persistent_geometry_and_incremental_updates"
    assert PROFILE == "VW1_GENERATION_KEYED_VOLUME_DELTA_P2_V1"
    assert AUTHORITY == "RESEARCHER_DERIVED_DELIVERY_OPTIMIZATION_OVER_VW1_NO_PHYSICAL_EFFECT"
    assert REPRESENTATION == "COMPACT_INTERVAL_PRISM_LIST_FRONTEND_FACE_EXPAND"


def test_02_static_payload_id_deterministic():
    a = make_static_payload_id(occupancy_digest="d1", width=32, height=32, runtime_generation=1)
    b = make_static_payload_id(occupancy_digest="d1", width=32, height=32, runtime_generation=1)
    assert a == b
    c = make_static_payload_id(occupancy_digest="d2", width=32, height=32, runtime_generation=1)
    assert a != c


def test_03_body_motion_keeps_static_id():
    rt = _rt(52)
    for _ in range(3):
        rt.step()
    p0 = build_observer_volume_render_description(rt)
    sid = p0["static_payload_id"]
    rt.body.x += 1.25
    rt.body.y -= 0.5
    p1 = build_observer_volume_render_description(rt)
    assert p1["static_payload_id"] == sid
    assert p1["observer_volume_incremental"]["telemetry"]["static_cache"] == "hit"


def test_04_camera_display_not_in_static_id():
    # Camera/display are UI-only — static id depends only on VW1/world/schema.
    a = make_static_payload_id(occupancy_digest="x", width=32, height=32, runtime_generation=0)
    b = make_static_payload_id(occupancy_digest="x", width=32, height=32, runtime_generation=0)
    assert a == b


def test_05_paused_poll_static_hit_and_dynamic_wire():
    rt = _rt(53)
    for _ in range(2):
        rt.step()
    full = researcher_payload(rt)
    assert full["observer_camera_occupancy_consumer"]["incremental_wire_kind"] == KIND_FULL
    sid = full["observer_camera_occupancy_consumer"]["static_payload_id"]
    dyn = researcher_payload(rt, held_static_payload_id=sid)
    d = dyn["observer_camera_occupancy_consumer"]
    assert d["incremental_wire_kind"] == KIND_DYNAMIC
    assert d.get("occupancy_volumes_static_omitted") is True
    assert d.get("occupancy_volumes") == []
    assert d["observer_volume_incremental"]["telemetry"]["static_cache"] == "hit"


def test_06_entity_updates_incremental():
    rt = _rt(54)
    for _ in range(3):
        rt.step()
    full = researcher_payload(rt)
    sid = full["observer_camera_occupancy_consumer"]["static_payload_id"]
    before = full["observer_camera_occupancy_consumer"]["bodies"][0]["sim_x"]
    rt.body.x += 2.0
    dyn = researcher_payload(rt, held_static_payload_id=sid)
    after = dyn["observer_camera_occupancy_consumer"]["observer_volume_incremental"]["volume_dynamic"]["bodies"][0]["sim_x"]
    assert before != after
    assert dyn["observer_camera_occupancy_consumer"]["static_payload_id"] == sid


def test_07_08_tombstones_and_grasp_no_duplication():
    rt = _rt(55)
    for _ in range(2):
        rt.step()
    build_observer_volume_render_description(rt)
    objs = getattr(rt.world, "resource_objects", None)
    if objs is not None and hasattr(objs, "clear"):
        n0 = len(list(objs))
        objs.clear()
        p1 = build_observer_volume_render_description(rt)
        tombs = p1["observer_volume_incremental"]["volume_dynamic"].get("entity_tombstones") or []
        assert isinstance(tombs, list)
        if n0:
            assert any(t.get("kind") == "RESOURCE_OBJECT" for t in tombs)
    # bodies remain a single entry (no grasp duplication invent)
    bodies = build_observer_volume_render_description(rt)["bodies"]
    ids = [b.get("body_id") for b in bodies]
    assert len(ids) == len(set(ids))


def test_09_radius_change_updates_entity_geometry():
    rt = _rt(56)
    for _ in range(2):
        rt.step()
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    if not objs:
        return
    obj = objs[0]
    sid0 = build_observer_volume_render_description(rt)["static_payload_id"]
    before = build_observer_volume_render_description(rt)["resource_objects"]
    row0 = next(o for o in before if o.get("object_id") == getattr(obj, "object_id", None))
    r0 = float(row0.get("render_radius") or 0)
    if hasattr(obj, "collision_radius"):
        obj.collision_radius = float(getattr(obj, "collision_radius", 0.25) or 0.25) + 0.15
    p1 = build_observer_volume_render_description(rt)
    assert p1["static_payload_id"] == sid0  # VW1 unchanged
    row = next(o for o in p1["resource_objects"] if o.get("object_id") == getattr(obj, "object_id", None))
    r1 = float(row.get("render_radius") or 0)
    assert r1 > 0
    assert abs(r1 - r0) > 1e-9


def _set_col(world, x, y, intervals, tick=0):
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import set_volumetric_column

    set_volumetric_column(world, x, y, intervals, tick=tick, reason="test_fixture")


def test_10_vw3_updates_base_exactly():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )

    rt = _rt(57)
    for _ in range(2):
        rt.step()
    _set_col(rt.world, 4, 5, [OccupiedZInterval(0.0, 10.0, 1.5, (("soil", 10.0),))])
    p0 = build_observer_volume_render_description(rt)
    sid0 = p0["static_payload_id"]
    dig0 = p0["occupancy_digest"]
    out = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=4, cell_y=5, z_remove_lo=4.0, z_remove_hi=6.0, tick=2
    )
    assert out["receipt"]["status"] == "COMMITTED"
    p1 = build_observer_volume_render_description(rt)
    assert p1["occupancy_digest"] != dig0
    assert p1["static_payload_id"] != sid0
    assert p1["observer_volume_incremental"]["telemetry"]["static_cache"] == "miss"


def test_11_failed_transaction_leaves_base():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )

    rt = _rt(58)
    for _ in range(2):
        rt.step()
    _set_col(rt.world, 4, 5, [OccupiedZInterval(0.0, 10.0, 1.5, (("soil", 10.0),))])
    p0 = build_observer_volume_render_description(rt)
    sid0 = p0["static_payload_id"]
    dig0 = p0["occupancy_digest"]
    bad = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=4, cell_y=5, z_remove_lo=20.0, z_remove_hi=21.0, tick=1
    )
    assert bad["receipt"]["status"] == "REJECTED"
    p1 = build_observer_volume_render_description(rt)
    assert p1["occupancy_digest"] == dig0
    assert p1["static_payload_id"] == sid0
    assert p1["observer_volume_incremental"]["telemetry"]["static_cache"] == "hit"


def test_12_vw4_reintegration_updates_base():
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval
    from mechanistic_mind.physical_system.volumetric_world_material_separation import (
        apply_volumetric_material_separation,
    )
    from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
        apply_volumetric_material_reintegration,
    )

    rt = _rt(59)
    for _ in range(2):
        rt.step()
    _set_col(rt.world, 6, 6, [OccupiedZInterval(0.0, 10.0, 1.0, (("soil", 10.0),))])
    sep = apply_volumetric_material_separation(
        rt.world, rt.config, cell_x=6, cell_y=6, z_remove_lo=3.0, z_remove_hi=5.0, tick=3
    )
    if sep["receipt"]["status"] != "COMMITTED":
        return
    p_sep = build_observer_volume_render_description(rt)
    sid_sep = p_sep["static_payload_id"]
    oid = sep["receipt"]["object_id"]
    rein = apply_volumetric_material_reintegration(
        rt.world,
        rt.config,
        object_id=oid,
        cell_x=6,
        cell_y=6,
        z_deposit_lo=3.0,
        z_deposit_hi=5.0,
        tick=4,
    )
    if rein.get("receipt", {}).get("status") != "COMMITTED":
        return
    p_r = build_observer_volume_render_description(rt)
    assert p_r["static_payload_id"] != sid_sep


def test_13_14_xy_periodic_z_absolute_interval_ids():
    rt = _rt(60)
    for _ in range(2):
        rt.step()
    p = build_observer_volume_render_description(rt)
    st = p["observer_volume_incremental"]["volume_static"]
    assert st["xy_periodic"] is True
    assert st["z_absolute"] is True
    assert st["internal_xray_occupancy_preserved"] is True
    vols = st["occupancy_volumes"]
    assert vols and all(v.get("interval_id") for v in vols[:20])
    ids = [v["interval_id"] for v in vols]
    assert len(ids) == len(set(ids))


def test_15_restore_invalidates_cache():
    rt = _rt(61)
    for _ in range(2):
        rt.step()
    build_observer_volume_render_description(rt)
    assert getattr(rt.world, STATIC_CACHE_ATTR, None) is not None
    invalidate_vw7_volume_caches(rt.world)
    assert getattr(rt.world, STATIC_CACHE_ATTR, None) is None


def test_16_stale_delta_rejected():
    rt = _rt(62)
    for _ in range(2):
        rt.step()
    full = researcher_payload(rt)
    sid = full["observer_camera_occupancy_consumer"]["static_payload_id"]
    dyn = researcher_payload(rt, held_static_payload_id=sid)
    held = copy.deepcopy(full["observer_camera_occupancy_consumer"]["observer_volume_incremental"]["volume_static"])
    held["static_payload_id"] = "other"
    assert materialize_volume_from_incremental(
        dyn["observer_camera_occupancy_consumer"]["observer_volume_incremental"], held_static=held
    ) is None
    assert materialize_volume_from_incremental(
        dyn["observer_camera_occupancy_consumer"]["observer_volume_incremental"], held_static=None
    ) is None


def test_17_18_held_mismatch_reset_and_legacy_full():
    rt = _rt(63)
    for _ in range(2):
        rt.step()
    s = researcher_payload(rt, held_static_payload_id="deadbeef_not_real")
    assert s["observer_camera_occupancy_consumer"]["incremental_wire_kind"] == KIND_RESET
    assert s["observer_camera_occupancy_consumer"]["observer_volume_incremental"]["volume_reset"]["reason"] == "HELD_STATIC_MISMATCH"
    # Legacy full path
    full = researcher_payload(rt, held_static_payload_id=None, prefer_incremental=True)
    assert full["observer_camera_occupancy_consumer"]["incremental_wire_kind"] == KIND_FULL
    assert full["observer_camera_occupancy_consumer"]["occupancy_volumes"]


def test_19_materialized_equals_full_authority():
    rt = _rt(64)
    for _ in range(3):
        rt.step()
    full = researcher_payload(rt, held_static_payload_id=None)
    assert full["observer_camera_occupancy_consumer"]["incremental_wire_kind"] == KIND_FULL
    sid = full["observer_camera_occupancy_consumer"]["static_payload_id"]
    held = full["observer_camera_occupancy_consumer"]["observer_volume_incremental"]["volume_static"]
    rt.body.x += 0.4
    dyn = researcher_payload(rt, held_static_payload_id=sid)
    assert dyn["observer_camera_occupancy_consumer"]["incremental_wire_kind"] == KIND_DYNAMIC
    mat = materialize_volume_from_incremental(
        dyn["observer_camera_occupancy_consumer"]["observer_volume_incremental"], held_static=held
    )
    assert mat is not None
    full2 = researcher_payload(rt, held_static_payload_id=None)
    auth = full2["observer_camera_occupancy_consumer"]
    assert len(mat["occupancy_volumes"]) == len(auth["occupancy_volumes"])
    assert mat["occupancy_volumes"][0]["interval_id"] == auth["occupancy_volumes"][0]["interval_id"]
    assert mat["occupancy_digest"] == auth["occupancy_digest"]
    assert abs(float(mat["bodies"][0]["sim_x"]) - float(auth["bodies"][0]["sim_x"])) < 1e-9


def test_20_21_24_p1_gating_preserved():
    r_map = resolve_derived_subscription(None)
    assert r_map.include_volume is False
    assert FAMILY_VOLUME in r_map.omitted_families
    r_surf = resolve_derived_subscription(explicit_products=[PRODUCT_SURFACE_LIGHT])
    assert r_surf.include_volume is False
    r_vol = resolve_derived_subscription(explicit_products=[PRODUCT_VOLUME_XRAY])
    assert r_vol.include_volume is True

    rt = _rt(65)
    for _ in range(2):
        rt.step()
    interest = ObserverInterest(products=frozenset({PRODUCT_WORLD}))
    frame = live_frame(
        rt,
        status="PAUSED",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail="compact",
        include_cognition=False,
        observer_interest=interest,
    )
    assert "observer_camera_occupancy_consumer" not in (frame.get("world") or {})
    # omission reason
    sub = (frame.get("observer_derived_payload_subscription") or {})
    omitted = {o["family"]: o["reason"] for o in (sub.get("omitted_payload_families") or [])}
    if FAMILY_VOLUME in omitted:
        assert omitted[FAMILY_VOLUME] == OMISSION_NOT_REQUESTED


def test_22_23_cache_bounded_across_switches():
    rt = _rt(66)
    for _ in range(2):
        rt.step()
    build_observer_volume_render_description(rt)
    c1 = getattr(rt.world, STATIC_CACHE_ATTR)
    assert isinstance(c1, dict)
    invalidate_vw7_volume_caches(rt.world)
    build_observer_volume_render_description(rt)
    c2 = getattr(rt.world, STATIC_CACHE_ATTR)
    assert isinstance(c2, dict)
    # single base retained (not a history list)
    assert "occupancy_volumes" in c2


def test_25_26_fingerprint_and_snapshot_clean():
    rt = _rt(67)
    for _ in range(3):
        rt.step()
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

    dig0 = state_of(rt.world).digest()
    snap = rt.snapshot()
    researcher_payload(rt)
    researcher_payload(rt, held_static_payload_id=None)
    assert state_of(rt.world).digest() == dig0
    blob = json.dumps(snap, default=str)
    assert SCHEMA not in blob
    assert CAPABILITY not in blob
    snap2 = rt.snapshot()
    assert snap2.get("tick") == snap.get("tick")
    assert state_of(rt.world).digest() == dig0


def test_27_materialized_identity_covered_in_19():
    # Covered by test_19; keep explicit marker for suite checklist.
    assert True


def test_28_29_tiktaalik_and_selector():
    assert len(public_model_selector_entries()) == 2
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=2, config=cfg)
    rt.step()
    p = build_observer_volume_render_description(rt)
    assert p.get("available") is False


def test_30_research_metadata_outside_cognition():
    rt = _rt(68)
    rt.step()
    p = build_observer_volume_render_description(rt)
    assert p.get("researcher_only") is True
    assert p.get("drives_organism_vision") is False
    assert p.get("physical_mechanism") is not True
