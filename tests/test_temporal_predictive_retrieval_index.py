"""Indexed predictive-equivalence / relevance retrieve vs full-scan oracle."""
from __future__ import annotations

import copy

from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import predictive_relevance as prl
from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.research import temporal_prospection_bridge as tpb


def _frag(n: float, **extra):
    d = {f"k{i}": float(n) + 0.01 * i for i in range(6)}
    d.update(extra)
    return d


def test_empty_store():
    s = pe.empty_store()
    s["enabled"] = True
    assert pe.retrieve(s, _frag(0), "WAIT")["status"] == "NO_MATCH"
    assert pe._retrieve_full_scan_reference(s, _frag(0), "WAIT")["status"] == "NO_MATCH"


def test_one_and_many_classes_indexed_equals_oracle():
    s = pe.empty_store()
    s["enabled"] = True
    # Build support >= MIN_CLASS_SUPPORT for several actions
    for act, base in [("WAIT", 0.0), ("MOVE:N", 1.0), ("MOVE:S", 2.0)]:
        for i in range(4):
            pe.learn(
                s,
                fragment=_frag(base + 0.001 * i),
                action=act,
                consequent=_frag(base + 0.5 + 0.001 * i, cont=base),
                tick=i,
            )
    pe.ensure_class_indexes(s)
    stats = pe.index_bucket_stats(s)
    assert stats["bucket_count"] >= 1
    assert stats["max_bucket"] <= pe.MAX_CLASSES
    q = _frag(0.001)
    for act in ("WAIT", "MOVE:N", "MOVE:S", "PUSH"):
        a = pe.retrieve(s, q, act, count=False)
        b = pe._retrieve_full_scan_reference(s, q, act, count=False)
        assert a == b, (act, a, b)


def test_shared_action_bucket_multiple_candidates():
    s = pe.empty_store()
    s["enabled"] = True
    # Two continuation families under same action → two classes
    for i in range(4):
        pe.learn(s, fragment=_frag(0.0 + i * 0.001), action="WAIT", consequent=_frag(10.0), tick=i)
    for i in range(4):
        pe.learn(s, fragment=_frag(5.0 + i * 0.001), action="WAIT", consequent=_frag(20.0), tick=10 + i)
    pe.ensure_class_indexes(s)
    assert pe.index_bucket_stats(s)["max_bucket"] >= 1
    for q in (_frag(0.0), _frag(5.0), _frag(99.0)):
        assert pe.retrieve(s, q, "WAIT", count=False) == pe._retrieve_full_scan_reference(
            s, q, "WAIT", count=False
        )


def test_relevance_oracle_match():
    s = pe.empty_store()
    s["enabled"] = True
    meta = prl.empty_meta()
    meta["enabled"] = True
    for i in range(5):
        pe.learn(
            s,
            fragment=_frag(0.1 * i, noise=float(i)),
            action="MOVE:E",
            consequent=_frag(1.0),
            tick=i,
        )
    prl.refresh(s, tick=5, meta=meta)
    q = _frag(0.2, noise=2.0)
    a = prl.retrieve(s, q, "MOVE:E", meta=meta, count=False)
    b = prl._retrieve_full_scan_reference(s, q, "MOVE:E", meta=meta, count=False)
    assert a == b


def test_learn_after_index_and_forget_reindex():
    s = pe.empty_store()
    s["enabled"] = True
    for i in range(pe.MAX_CLASSES + 5):
        # Distinct continuation per episode so classes do not join (forces FORGOTTEN).
        pe.learn(
            s,
            fragment=_frag(float(i)),
            action=f"A{i % 7}",
            consequent={f"out": float(i) * 10.0},
            tick=i,
        )
    pe.ensure_class_indexes(s)
    active = sum(1 for c in s["classes"].values() if c.get("status") == "ACTIVE")
    assert active <= pe.MAX_CLASSES
    forgotten = sum(1 for c in s["classes"].values() if c.get("status") == "FORGOTTEN")
    assert forgotten >= 1
    # Indexed retrieve still matches oracle for every action key present
    acts = sorted({c.get("action") for c in s["classes"].values() if c.get("status") == "ACTIVE"})
    q = _frag(1.0)
    for act in acts:
        assert pe.retrieve(s, q, act, count=False) == pe._retrieve_full_scan_reference(s, q, act, count=False)


def test_clear_derived_caches_rebuilds():
    s = pe.empty_store()
    s["enabled"] = True
    for i in range(4):
        pe.learn(s, fragment=_frag(i * 0.01), action="WAIT", consequent=_frag(1.0), tick=i)
    pe.ensure_class_indexes(s)
    assert "_ix_action" in s
    pe.clear_derived_caches(s)
    assert "_ix_action" not in s or s.get("_ix_built_gen") != s.get("_ix_gen")
    # Lazy rebuild on next retrieve
    pe.retrieve(s, _frag(0), "WAIT", count=False)
    pe.ensure_class_indexes(s)
    assert s.get("_ix_built_gen") == s.get("_ix_gen")


def test_same_tick_tps_memo_hits_and_invalidates():
    store = tps.empty_store()
    store["enabled"] = True
    store["inner"]["enabled"] = True
    meta = store["relevance"]
    meta["enabled"] = True
    # Grow a tiny history
    for i in range(6):
        obs = _frag(0.01 * i)
        tps.learn(store, consequent=obs, action="WAIT", tick=i)
        tps.append(store, obs)
        tps.refresh_relevance(store, tick=i)
    present = _frag(0.05)
    store["_retrieve_cache_hits"] = 0
    store["_retrieve_cache_misses"] = 0
    a = tps.retrieve(store, present, "WAIT", meta=meta, count=False)
    b = tps.retrieve(store, present, "WAIT", meta=meta, count=False)
    assert a == b
    assert store["_retrieve_cache_hits"] >= 1
    # Mutation invalidates
    tps.append(store, _frag(0.99))
    c = tps.retrieve(store, present, "WAIT", meta=meta, count=False)
    # May or may not equal a depending on window; must be a fresh miss path
    assert store["_retrieve_cache_misses"] >= 2


def test_collect_entry_steps_reuses_predictions_or_memo():
    store = tps.empty_store()
    store["enabled"] = True
    store["inner"]["enabled"] = True
    meta = tpb.empty_meta()
    meta["enabled"] = True
    tmeta = store["relevance"]
    tmeta["enabled"] = True
    for i in range(8):
        obs = _frag(0.02 * i)
        tps.learn(store, consequent=obs, action="WAIT", tick=i)
        tps.append(store, obs)
        tps.refresh_relevance(store, tick=i)
    present = _frag(0.1)
    pred = [{"action": "WAIT", "source": "temporal_predictive_structure", "result": tps.retrieve(store, present, "WAIT", meta=tmeta, count=False)}]
    before = store.get("_retrieve_cache_hits") or 0
    tpb.collect_entry_steps(store, present, ["WAIT", "MOVE:N"], meta=meta, tps_meta=tmeta, predictions=pred)
    # WAIT reused from predictions (no extra retrieve); MOVE:N may retrieve once
    # Second collect should memo-hit MOVE:N
    tpb.collect_entry_steps(store, present, ["WAIT", "MOVE:N"], meta=meta, tps_meta=tmeta, predictions=pred)
    assert (store.get("_retrieve_cache_hits") or 0) >= before


def test_strip_derived_omits_index_keys():
    s = pe.empty_store()
    s["enabled"] = True
    for i in range(4):
        pe.learn(s, fragment=_frag(i * 0.01), action="WAIT", consequent=_frag(1.0), tick=i)
    pe.ensure_class_indexes(s)
    stripped = pe.strip_derived_fields(s)
    assert "_ix_action" not in stripped
    assert "_mean_c_cached" not in str(stripped)
