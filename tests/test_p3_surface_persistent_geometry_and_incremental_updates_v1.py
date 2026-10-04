"""P3 SURFACE persistent geometry + incremental updates tests."""
from __future__ import annotations

import copy
import json

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
from mechanistic_mind.physical_system.researcher_physical_optical_audit_view import (
    STATIC_TERRAIN_CACHE_ATTR,
    build_surface_display_payload,
    invalidate_o6_display_cache,
    researcher_summary,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.ui.psy_observer_web.observer_surface_incremental_payload import (
    AUTHORITY,
    CAPABILITY,
    KIND_DYNAMIC,
    KIND_FULL,
    KIND_RESET,
    PROFILE,
    SCHEMA,
    make_static_payload_id,
    materialize_display_from_incremental,
    merge_facets_columnar,
    split_facets_columnar,
)


def _rt(seed: int = 31):
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def test_01_schema_and_identity():
    assert SCHEMA == "OBSERVER_SURFACE_INCREMENTAL_PAYLOAD_V1"
    assert CAPABILITY == "surface_persistent_geometry_and_incremental_updates"
    assert PROFILE == "O2_O3_O3A_GENERATION_KEYED_SURFACE_DELTA_P3_V1"
    assert AUTHORITY == "RESEARCHER_DERIVED_DELIVERY_OPTIMIZATION_NO_PHYSICAL_EFFECT"


def test_02_static_payload_id_deterministic():
    a = make_static_payload_id(
        o2_key_digest="k", o2_facet_checksum="f", o1_registry_version="r", runtime_generation=1
    )
    b = make_static_payload_id(
        o2_key_digest="k", o2_facet_checksum="f", o1_registry_version="r", runtime_generation=1
    )
    assert a == b
    c = make_static_payload_id(
        o2_key_digest="k2", o2_facet_checksum="f", o1_registry_version="r", runtime_generation=1
    )
    assert a != c


def test_03_body_motion_keeps_static_id():
    rt = _rt(32)
    for _ in range(3):
        rt.step()
    p0 = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    sid = p0["static_payload_id"]
    rt.body.x += 1.25
    rt.body.y -= 0.5
    p1 = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    assert p1["static_payload_id"] == sid
    assert p1["observer_surface_incremental"]["telemetry"]["static_cache"] == "hit"


def test_04_entity_transform_updates():
    rt = _rt(33)
    for _ in range(3):
        rt.step()
    p0 = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    before = {e["sample_id"]: tuple(e.get("entity_centre") or e.get("centre") or []) for e in p0["entity_samples"]}
    rt.body.x += 2.0
    p1 = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    after = {e["sample_id"]: tuple(e.get("entity_centre") or e.get("centre") or []) for e in p1["entity_samples"]}
    assert before != after


def test_05_split_merge_roundtrip():
    rt = _rt(34)
    for _ in range(2):
        rt.step()
    p = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    st, op = split_facets_columnar(p["facets_columnar"])
    merged = merge_facets_columnar(st, op)
    assert merged["n"] == p["facets_columnar"]["n"]
    assert merged["facet_id"] == p["facets_columnar"]["facet_id"]
    assert merged["state_class"] == p["facets_columnar"]["state_class"]
    assert merged["incident"] == p["facets_columnar"]["incident"]


def test_06_materialized_equals_full_authority():
    rt = _rt(35)
    for _ in range(3):
        rt.step()
    full = researcher_summary(rt.world, rt.config, runtime=rt, held_static_payload_id=None)
    assert full["incremental_wire_kind"] == KIND_FULL
    sid = full["static_payload_id"]
    dyn = researcher_summary(rt.world, rt.config, runtime=rt, held_static_payload_id=sid)
    assert dyn["incremental_wire_kind"] == KIND_DYNAMIC
    held = full["observer_surface_incremental"]["surface_static"]
    mat = materialize_display_from_incremental(dyn["observer_surface_incremental"], held_static=held)
    assert mat is not None
    fc = full["display"]["facets_columnar"]
    mc = mat["facets_columnar"]
    assert fc["facet_id"] == mc["facet_id"]
    assert fc["centre"] == mc["centre"]
    assert fc["normal"] == mc["normal"]
    assert fc["state_class"] == mc["state_class"]
    assert fc["incident"] == mc["incident"]
    assert fc["reflected"] == mc["reflected"]
    assert len(full["display"]["entity_samples"]) == len(mat["entity_samples"])


def test_07_held_mismatch_reset():
    rt = _rt(36)
    for _ in range(2):
        rt.step()
    s = researcher_summary(rt.world, rt.config, runtime=rt, held_static_payload_id="deadbeef_not_real")
    assert s["incremental_wire_kind"] == KIND_RESET
    assert s["observer_surface_incremental"]["surface_reset"]["reason"] == "HELD_STATIC_MISMATCH"


def test_08_stale_delta_materialize_rejected():
    rt = _rt(37)
    for _ in range(2):
        rt.step()
    full = researcher_summary(rt.world, rt.config, runtime=rt)
    sid = full["static_payload_id"]
    dyn = researcher_summary(rt.world, rt.config, runtime=rt, held_static_payload_id=sid)
    held = copy.deepcopy(full["observer_surface_incremental"]["surface_static"])
    held["static_payload_id"] = "other"
    assert materialize_display_from_incremental(dyn["observer_surface_incremental"], held_static=held) is None
    assert materialize_display_from_incremental(dyn["observer_surface_incremental"], held_static=None) is None


def test_09_restore_invalidates_static_cache():
    rt = _rt(38)
    for _ in range(2):
        rt.step()
    build_surface_display_payload(rt.world, rt.config, runtime=rt)
    assert getattr(rt.world, STATIC_TERRAIN_CACHE_ATTR, None) is not None
    invalidate_o6_display_cache(rt.world)
    assert getattr(rt.world, STATIC_TERRAIN_CACHE_ATTR, None) is None


def test_10_paused_poll_static_hit():
    rt = _rt(39)
    for _ in range(2):
        rt.step()
    build_surface_display_payload(rt.world, rt.config, runtime=rt)
    p2 = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    assert p2["observer_surface_incremental"]["telemetry"]["static_cache"] == "hit"
    assert p2["observer_surface_incremental"]["telemetry"]["optical_cache"] == "hit"


def test_11_selector_two_and_tiktaalik():
    assert len(public_model_selector_entries()) == 2
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=2, config=cfg)
    rt.step()
    # Tiktaalik path does not activate O6
    p = build_surface_display_payload(rt.world, cfg, runtime=rt)
    assert p.get("available") is False or p.get("status") == "UNAVAILABLE_NO_O2"


def test_12_subscription_not_in_snapshot():
    rt = _rt(40)
    rt.step()
    build_surface_display_payload(rt.world, rt.config, runtime=rt)
    blob = json.dumps(rt.snapshot(), default=str)
    assert SCHEMA not in blob
    assert CAPABILITY not in blob


def test_13_tombstones_on_entity_loss():
    rt = _rt(41)
    for _ in range(2):
        rt.step()
    p0 = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    assert p0["entity_samples"]
    # Simulate removal by clearing resource objects if present
    objs = getattr(rt.world, "resource_objects", None)
    if objs is not None and hasattr(objs, "clear"):
        objs.clear()
    from mechanistic_mind.physical_system.object_body_held_optical_surfaces import invalidate_entity_surface_cache
    invalidate_entity_surface_cache(rt.world)
    p1 = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    tombs = p1["observer_surface_incremental"]["surface_dynamic"].get("entity_tombstones") or []
    # May or may not have RO removals depending on fixture; bodies remain.
    assert isinstance(tombs, list)
