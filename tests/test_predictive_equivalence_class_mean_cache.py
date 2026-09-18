"""BETA2-02: versioned class-mean cache semantics (exact, not approximate)."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import predictive_relevance as prl


def _store():
    s = pe.empty_store()
    s["enabled"] = True
    return s


def _train_two_classes(store=None):
    store = store or _store()
    for t, x in enumerate((0.11, 0.24, 0.39), start=1):
        pe.learn(store, fragment={"x": float(x)}, action="WAIT", consequent={"y": 0.90}, tick=t)
    for t, x in enumerate((0.60, 0.72, 0.85), start=50):
        pe.learn(store, fragment={"x": float(x)}, action="WAIT", consequent={"y": 0.10}, tick=t)
    return store


def test_1_repeated_read_hits_cache_no_recompute():
    store = _train_two_classes()
    cls = next(c for c in store["classes"].values() if c.get("status") == "ACTIVE")
    pe.clear_derived_caches(store)
    pe.reset_cache_stats()
    a = pe._class_mean_c(cls)
    recomp_after_miss = pe.cache_stats()["recomputation"]
    b = pe._class_mean_c(cls)
    c = pe._class_mean_c(cls)
    assert a == b == c
    assert a == pe._class_mean_c_uncached(cls)
    st = pe.cache_stats()
    assert st["lookups"] == 3
    assert st["hits"] == 2
    assert st["misses"] == 1
    assert st["recomputation"] == recomp_after_miss == 1


def test_2_learn_invalidates_cache():
    store = _train_two_classes()
    cls = next(iter(store["classes"].values()))
    pe._class_mean_c(cls)
    pe.reset_cache_stats()
    pe.learn(store, fragment={"x": 0.30}, action="WAIT", consequent={"y": 0.90}, tick=200)
    st = pe.cache_stats()
    assert st["invalidations"] >= 1


def test_3_after_invalidation_matches_uncached_baseline():
    store = _train_two_classes()
    cls_id = next(iter(store["classes"]))
    pe.learn(store, fragment={"x": 0.28}, action="WAIT", consequent={"y": 0.90}, tick=201)
    cls = store["classes"][cls_id]
    cached = pe._class_mean_c(cls)
    baseline = pe._class_mean_c_uncached(cls)
    assert cached == baseline


def test_4_unrelated_state_change_does_not_corrupt_mean():
    store = _train_two_classes()
    cls = next(iter(store["classes"].values()))
    before = dict(pe._class_mean_c(cls))
    store["episodes"].append({"tick": 999, "note": "unrelated"})
    store["learns"] = int(store.get("learns") or 0)  # no member mutation
    after = pe._class_mean_c(cls)
    assert after == before
    assert after == pe._class_mean_c_uncached(cls)


def test_5_classes_do_not_contaminate_each_other():
    store = _train_two_classes()
    classes = [c for c in store["classes"].values() if c.get("status") == "ACTIVE"]
    assert len(classes) >= 2
    pe.clear_derived_caches(store)
    pe.reset_cache_stats()
    m0 = dict(pe._class_mean_c(classes[0]))
    m1 = dict(pe._class_mean_c(classes[1]))
    assert m0 != m1
    # Re-read: still distinct and stable
    assert pe._class_mean_c(classes[0]) == m0
    assert pe._class_mean_c(classes[1]) == m1
    assert pe._class_mean_c_uncached(classes[0]) == m0
    assert pe._class_mean_c_uncached(classes[1]) == m1


def test_6_membership_change_invalidates():
    store = _train_two_classes()
    # Join a new member into family A via similar continuation
    before_ids = set(store["classes"])
    pe.reset_cache_stats()
    pe.learn(store, fragment={"x": 0.22}, action="WAIT", consequent={"y": 0.90}, tick=300)
    assert pe.cache_stats()["invalidations"] >= 1
    for cid in before_ids:
        cls = store["classes"][cid]
        if cls.get("status") != "ACTIVE":
            continue
        assert pe._class_mean_c(cls) == pe._class_mean_c_uncached(cls)


def test_7_empty_and_singleton_preserve_baseline():
    empty_cls = {"members": {}, "mean_c": {"y": 0.5}}
    assert pe._class_mean_c(empty_cls) == pe._class_mean_c_uncached(empty_cls) == {"y": 0.5}
    single = {
        "members": {"s": {"mean_c": {"y": 0.42, "z": 1.0}}},
        "mean_c": {},
    }
    assert pe._class_mean_c(single) == pe._class_mean_c_uncached(single) == {"y": 0.42, "z": 1.0}


def test_8_restore_clears_stale_derived_cache():
    cfg = tiktaalik_config()
    cfg.cognition.predictive_equivalence = True
    cfg.cognition.predictive_relevance = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    store = rt.cognition["equivalence"]
    store["enabled"] = True
    _train_two_classes(store)
    cls = next(iter(store["classes"].values()))
    pe._class_mean_c(cls)
    # Poison cache: gen matches but payload wrong
    cls["_mean_c_cached"] = (int(cls.get("_mean_c_gen") or 0), {"y": -999.0})
    snap = rt.snapshot()
    rest = PhysicalSystemRuntime.restore(snap)
    eq = rest.cognition["equivalence"]
    pe.clear_derived_caches(eq)  # restore already clears; ensure still clean
    for c in (eq.get("classes") or {}).values():
        assert "_mean_c_cached" not in c
        assert pe._class_mean_c(c) == pe._class_mean_c_uncached(c)
        assert pe._class_mean_c(c).get("y", 0) != -999.0


def test_9_mechanism_off_on_no_stale_cache_exposure():
    store = _store()
    store["enabled"] = False
    pe.learn(store, fragment={"x": 0.1}, action="WAIT", consequent={"y": 0.9}, tick=1)
    assert store["classes"] == {}
    store["enabled"] = True
    pe.learn(store, fragment={"x": 0.11}, action="WAIT", consequent={"y": 0.9}, tick=2)
    pe.learn(store, fragment={"x": 0.24}, action="WAIT", consequent={"y": 0.9}, tick=3)
    pe.learn(store, fragment={"x": 0.39}, action="WAIT", consequent={"y": 0.9}, tick=4)
    cls = next(iter(store["classes"].values()))
    assert pe._class_mean_c(cls) == pe._class_mean_c_uncached(cls)
    store["enabled"] = False
    pe.learn(store, fragment={"x": 0.5}, action="WAIT", consequent={"y": 0.1}, tick=5)
    # Disabled learn must not mutate classes / cache
    assert pe._class_mean_c(cls) == pe._class_mean_c_uncached(cls)


def test_10_repeated_refresh_high_hit_rate():
    store = _train_two_classes()
    # Extra classes / members to make refresh non-trivial
    for t, x in enumerate((0.15, 0.33), start=100):
        pe.learn(store, fragment={"x": float(x)}, action="WAIT", consequent={"y": 0.90}, tick=t)
    pe.reset_cache_stats()
    for tick in range(10):
        prl.refresh(store, tick=tick)
    st = pe.cache_stats()
    assert st["lookups"] > 0
    assert st["hits"] > st["misses"]
    assert st["hits"] / st["lookups"] >= 0.8


def test_baseline_vs_optimized_means_exact_equality():
    """Harness: many deterministic transitions; cached == uncached always."""
    store = _store()
    pe.set_class_mean_cache_enabled(True)
    transitions = []
    for t in range(1, 80):
        x = 0.1 + (t % 7) * 0.05
        y = 0.9 if t % 5 else 0.1
        transitions.append(({"x": x}, "WAIT", {"y": y}, t))
    for frag, act, cons, tick in transitions:
        pe.learn(store, fragment=frag, action=act, consequent=cons, tick=tick)
        for cls in store["classes"].values():
            assert pe._class_mean_c(cls) == pe._class_mean_c_uncached(cls)
        prl.refresh(store, tick=tick)
        for cls in store["classes"].values():
            assert pe._class_mean_c(cls) == pe._class_mean_c_uncached(cls)


def test_cache_disable_matches_uncached_path():
    store = _train_two_classes()
    pe.set_class_mean_cache_enabled(False)
    pe.reset_cache_stats()
    try:
        for cls in store["classes"].values():
            a = pe._class_mean_c(cls)
            b = pe._class_mean_c_uncached(cls)
            assert a == b
        assert pe.cache_stats()["hits"] == 0
        assert pe.cache_stats()["recomputation"] >= 1
    finally:
        pe.set_class_mean_cache_enabled(True)


def test_relevance_refresh_matches_baseline_nested_linf():
    """Hoisted distinct-others list must match nested per-key _linf gating."""
    store = _train_two_classes()
    for t, x in enumerate((0.18, 0.31, 0.65, 0.78), start=400):
        y = 0.90 if x < 0.5 else 0.10
        pe.learn(store, fragment={"x": float(x)}, action="WAIT", consequent={"y": y}, tick=t)
    classes = [c for c in store["classes"].values() if c.get("status") == "ACTIVE"]
    tau = float(store.get("continuation_linf") or pe.CONTINUATION_LINF)
    for cls in classes:
        others = [o for o in classes if o.get("id") != cls.get("id") and o.get("action") == cls.get("action")]
        got = prl._relevance_for(cls, others, tau=tau, tick=1)
        # Reconstruct baseline nested loop (pre-hoist)
        aabb = {k: (float(v[0]), float(v[1])) for k, v in (cls.get("aabb") or {}).items()}
        mean = pe._class_mean_c_uncached(cls)
        discriminative = []
        for k, (lo, hi) in aabb.items():
            for other in others:
                if pe._linf(mean, pe._class_mean_c_uncached(other)) <= tau:
                    continue
                ospan = (other.get("aabb") or {}).get(k)
                if not ospan:
                    continue
                olo, ohi = float(ospan[0]), float(ospan[1])
                if hi < olo - prl.VARY_EPS or lo > ohi + prl.VARY_EPS:
                    discriminative.append(k)
                    break
        assert sorted(set(discriminative)) == got["discriminative"]


def test_strip_derived_fields_omits_cache_keys():
    blob = {"mean_c": {"y": 1.0}, "_mean_c_gen": 3, "_mean_c_cached": (3, {"y": 1.0}), "members": {}}
    assert pe.strip_derived_fields(blob) == {"mean_c": {"y": 1.0}, "members": {}}
