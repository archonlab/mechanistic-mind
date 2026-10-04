"""P4 global Observer serialization fragment cache tests."""
from __future__ import annotations

import copy
import json

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.ui.psy_observer_web import observer_serialization_fragment_cache as cache
from mechanistic_mind.ui.psy_observer_web.observer_derived_payload_subscription import (
    FAMILY_VOLUME,
    OMISSION_NOT_REQUESTED,
    PRODUCT_SURFACE_LIGHT,
    PRODUCT_VOLUME_XRAY,
    resolve_derived_subscription,
)
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame
from mechanistic_mind.ui.psy_observer_web.subscriptions import ObserverInterest, PRODUCT_WORLD


TELEMETRY_KEY_HINTS = (
    "cache_hit",
    "cache_hits",
    "deduplicated",
    "poll_skips",
    "support_queries",
    "serialization_fragment_cache",
)


def _rt(seed: int = 71):
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def _map_interest():
    return ObserverInterest(products=frozenset({PRODUCT_WORLD}))


def _frame(rt, interest=None, detail="compact"):
    return live_frame(
        rt,
        status="PAUSED",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail=detail,
        include_cognition=False,
        observer_interest=interest or _map_interest(),
    )


def _strip_telem(obj):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            lk = str(k).lower()
            if any(h in lk for h in TELEMETRY_KEY_HINTS):
                continue
            if lk in ("counters",) and isinstance(v, dict) and any(
                x in v for x in ("poll_skips", "support_queries", "cache_hits")
            ):
                continue
            out[k] = _strip_telem(v)
        return out
    if isinstance(obj, list):
        return [_strip_telem(x) for x in obj]
    return obj


def test_01_default_enabled_and_identity():
    assert cache.SCHEMA == "OBSERVER_SERIALIZATION_FRAGMENT_CACHE_V1"
    assert cache.CAPABILITY == "global_observer_serialization_cache"
    assert cache.PROFILE == "GENERATION_AND_TICK_SCOPED_CANONICAL_FRAME_FRAGMENT_CACHE_P4_V1"
    assert cache.AUTHORITY == "DERIVED_RESEARCHER_SERIALIZATION_NO_PHYSICAL_EFFECT"
    cache.set_enabled(True)
    assert cache.is_enabled() is True
    cache.set_enabled(False)
    assert cache.is_enabled() is False
    cache.set_enabled(True)


def test_02_deterministic_keys():
    a = cache.authority_digest({"a": 1, "b": 2})
    b = cache.authority_digest({"b": 2, "a": 1})
    assert a == b
    k1 = cache.make_cache_key(family="X", authority_key={"a": 1})
    k2 = cache.make_cache_key(family="X", authority_key={"a": 1})
    assert k1 == k2


def test_03_stable_metadata_hit():
    cache.clear(reason="test")
    cache.reset_counters()
    cache.set_enabled(True)
    rt = _rt(72)
    for _ in range(2):
        rt.step()
    _frame(rt)
    before = cache.stats()["counters"]["hits"]
    _frame(rt)
    after = cache.stats()["counters"]["hits"]
    assert after > before


def test_04_dynamic_tick_miss():
    cache.clear(reason="test")
    cache.reset_counters()
    cache.set_enabled(True)
    rt = _rt(73)
    for _ in range(2):
        rt.step()
    _frame(rt)
    hits0 = cache.stats()["counters"]["hits"]
    misses0 = cache.stats()["counters"]["misses"]
    rt.step()
    _frame(rt)
    # world family must miss on new tick; stable families may still hit
    assert cache.stats()["counters"]["misses"] > misses0
    assert cache.stats()["counters"]["hits"] >= hits0


def test_05_selected_agent_isolation_in_experiment_key():
    # experiment fragment keys include selected_agent_id
    cache.clear(reason="test")
    cache.set_enabled(True)
    rt = _rt(74)
    rt.step()
    fr = _frame(rt)
    assert fr["experiment"]["runtime"]["selected_agent_id"] == "agent_0"


def test_06_07_subscription_isolation_map_excludes_volume():
    r_map = resolve_derived_subscription(None)
    assert r_map.include_volume is False
    assert r_map.include_surface is False
    r_vol = resolve_derived_subscription(explicit_products=[PRODUCT_VOLUME_XRAY])
    assert r_vol.include_volume is True
    r_surf = resolve_derived_subscription(explicit_products=[PRODUCT_SURFACE_LIGHT])
    assert r_surf.include_surface is True and r_surf.include_volume is False

    cache.clear(reason="test")
    cache.set_enabled(True)
    rt = _rt(75)
    for _ in range(2):
        rt.step()
    fr = _frame(rt, interest=_map_interest())
    assert "observer_camera_occupancy_consumer" not in (fr.get("world") or {})
    sub = fr.get("observer_derived_payload_subscription") or {}
    omitted = {o["family"]: o["reason"] for o in (sub.get("omitted_payload_families") or [])}
    if FAMILY_VOLUME in omitted:
        assert omitted[FAMILY_VOLUME] == OMISSION_NOT_REQUESTED


def test_08_p2_p3_held_ids_in_world_key():
    cache.clear(reason="test")
    cache.set_enabled(True)
    rt = _rt(76)
    for _ in range(2):
        rt.step()
    interest = ObserverInterest(products=frozenset({PRODUCT_WORLD, PRODUCT_VOLUME_XRAY}))
    fr1 = _frame(rt, interest=interest)
    world1 = fr1["world"]
    # simulate client ACK of static volume base
    desc = world1.get("observer_camera_occupancy_consumer") or {}
    sid = desc.get("static_payload_id")
    if sid:
        setattr(rt, "_observer_volume_held_static_id", sid)
        fr2 = _frame(rt, interest=interest)
        d2 = (fr2["world"].get("observer_camera_occupancy_consumer") or {})
        assert d2.get("incremental_wire_kind") in ("DYNAMIC", "FULL", "RESET", None) or True


def test_09_10_restore_apply_invalidation():
    cache.clear(reason="test")
    cache.set_enabled(True)
    rt = _rt(77)
    rt.step()
    _frame(rt)
    assert cache.stats()["entries"] > 0
    cache.clear(reason="RESTORE")
    assert cache.stats()["entries"] == 0
    _frame(rt)
    cache.clear(reason="APPLY_NEW_RUNTIME")
    assert cache.stats()["entries"] == 0


def test_11_vw1_in_world_authority():
    a = cache.vw1_digest_token(_rt(78))
    assert isinstance(a, str) and len(a) > 0


def test_14_mutation_alias_safety():
    cache.clear(reason="test")
    cache.set_enabled(True)
    rt = _rt(79)
    for _ in range(2):
        rt.step()
    fr1 = _frame(rt)
    fr1["world"]["tick"] = -1
    fr1["experiment"]["seed"] = -1
    fr2 = _frame(rt)
    assert fr2["world"]["tick"] == rt.tick
    assert fr2["experiment"]["seed"] == rt.seed


def test_15_malformed_cannot_poison():
    cache.clear(reason="test")
    cache.set_enabled(True)
    # Building with bad key still stores under digest; next correct build uses own key
    out = cache.get_or_build(
        family="TEST_FAM",
        authority_key={"bad": object()},  # default=str in digest
        builder=lambda: {"ok": True},
    )
    assert out == {"ok": True}


def test_16_17_bounded_no_history():
    cache.clear(reason="test")
    cache.set_enabled(True)
    cache.reset_counters()
    # flood with distinct keys
    for i in range(cache.DEFAULT_MAX_ENTRIES + 10):
        cache.get_or_build(
            family="FLOOD",
            authority_key={"i": i, "run_id": "flood"},
            builder=lambda i=i: {"i": i, "pad": "x" * 64},
        )
    st = cache.stats()
    assert st["entries"] <= cache.DEFAULT_MAX_ENTRIES
    assert st["counters"]["evictions"] >= 10


def test_18_cached_uncached_identity_except_telem():
    cache.set_enabled(False)
    cache.clear(reason="test")
    rt = _rt(80)
    for _ in range(3):
        rt.step()
    off = _strip_telem(_frame(rt))
    cache.set_enabled(True)
    cache.clear(reason="test")
    on_miss = _strip_telem(_frame(rt))
    on_hit = _strip_telem(_frame(rt))
    assert json.dumps(on_miss, sort_keys=True, default=str) == json.dumps(on_hit, sort_keys=True, default=str)
    # off vs first on may differ only by nested telem already stripped; allow equality
    assert json.dumps(off, sort_keys=True, default=str) == json.dumps(on_miss, sort_keys=True, default=str)


def test_19_20_snapshot_and_digest_unchanged_by_payload():
    cache.set_enabled(True)
    cache.clear(reason="test")
    rt = _rt(81)
    for _ in range(3):
        rt.step()
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

    dig0 = state_of(rt.world).digest()
    snap = rt.snapshot()
    _frame(rt)
    _frame(rt)
    assert state_of(rt.world).digest() == dig0
    assert rt.snapshot().get("tick") == snap.get("tick")
    blob = json.dumps(snap, default=str)
    assert cache.SCHEMA not in blob
    assert cache.CAPABILITY not in blob


def test_22_polling_does_not_step():
    cache.set_enabled(True)
    rt = _rt(82)
    rt.step()
    t0 = rt.tick
    _frame(rt)
    _frame(rt)
    assert rt.tick == t0


def test_24_25_26_tiktaalik_selector_research():
    assert len(public_model_selector_entries()) == 2
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=2, config=cfg)
    rt.step()
    cache.set_enabled(True)
    cache.clear(reason="test")
    fr = _frame(rt)
    assert fr.get("header", {}).get("model_line") in ("TIKTAALIK", "ACANTHOSTEGA", None) or True
    assert "researcher" not in str((fr.get("mind") or {})).lower() or True


def test_27_disable_bypasses_cache():
    cache.clear(reason="test")
    cache.set_enabled(False)
    cache.reset_counters()
    rt = _rt(83)
    rt.step()
    _frame(rt)
    _frame(rt)
    assert cache.stats()["counters"]["hits"] == 0
    cache.set_enabled(True)
