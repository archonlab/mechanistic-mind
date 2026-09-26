"""Exact prepared-query reuse vs legacy TPS retrieve reconstruction."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.physical_system.cognition import clear_derived_indexes, empty_cognitive_state, CognitionConfig
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import temporal_predictive_structure as tps

from tests.test_temporal_predictive_structure import train_seq

ACTIONS = ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"]
ALT_ORDER = ["MOVE:E", "WAIT", "MOVE:W", "MOVE:N", "MOVE:S"]


def _trained():
    s = tps.empty_store()
    s["enabled"] = True
    train_seq(s, [0.0, 0.2, 0.4, 0.6], {"y": 0.90}, reps=6)
    return s


def _present(store):
    return dict((store.get("ring") or [{}])[-1])


def _pq_scientific(pq: dict) -> dict:
    return {
        "window": pq["window"],
        "window_key": pq["window_key"],
        "window_n": pq["window_n"],
        "dfrag": pq["dfrag"],
        "delta_sig": pq["delta_sig"],
        "present": pq["present"],
        "raw_present_sig": pq["raw_present_sig"],
        "recent": pq["recent"],
        "too_short": pq["too_short"],
        "gate": pq["gate"],
    }


def _assert_no_action(pq: dict) -> None:
    for k in pq:
        assert "action" not in k.lower()
        assert k not in {"support", "class_id", "lag", "predicted", "predicted_continuation", "relevant"}


def test_prepared_query_matches_legacy_fields():
    store = _trained()
    present = _present(store)
    tps.set_prepared_query_enabled(False)
    legacy = tps.build_prepared_query(store, present)
    tps.set_prepared_query_enabled(True)
    store.pop("_prepared_query", None)
    got = tps.get_prepared_query(store, present)
    _assert_no_action(got)
    assert _pq_scientific(got) == _pq_scientific(legacy)
    tps.set_prepared_query_enabled(True)


def test_action_burst_exact():
    store = _trained()
    present = _present(store)
    meta = store.get("relevance")
    meta["enabled"] = True
    tps.set_prepared_query_enabled(False)
    store.pop("_retrieve_cache", None)
    legacy = {a: deepcopy(tps.retrieve(deepcopy(store), present, a, meta=meta)) for a in ACTIONS}
    tps.set_prepared_query_enabled(True)
    opt_store = deepcopy(store)
    opt_store.pop("_retrieve_cache", None)
    opt_store.pop("_prepared_query", None)
    opt = {a: tps.retrieve(opt_store, present, a, meta=meta) for a in ACTIONS}
    for a in ACTIONS:
        assert opt[a] == legacy[a], a
    assert int(opt_store.get("_prepared_query_builds") or 0) == 1
    assert int(opt_store.get("_prepared_query_hits") or 0) == 4
    tps.set_prepared_query_enabled(True)


def test_alternate_action_order_exact():
    store = _trained()
    present = _present(store)
    tps.set_prepared_query_enabled(False)
    legacy = {a: deepcopy(tps.retrieve(deepcopy(store), present, a)) for a in ALT_ORDER}
    tps.set_prepared_query_enabled(True)
    opt_store = deepcopy(store)
    opt_store.pop("_retrieve_cache", None)
    opt = {a: tps.retrieve(opt_store, present, a) for a in ALT_ORDER}
    for a in ALT_ORDER:
        assert opt[a] == legacy[a], a
    tps.set_prepared_query_enabled(True)


def test_mutation_between_retrievals_invalidates():
    store = _trained()
    present = _present(store)
    tps.set_prepared_query_enabled(True)
    store.pop("_prepared_query", None)
    a = tps.retrieve(store, present, "WAIT")
    tps.append(store, {"x": 0.99, "y": 0.5})
    present_b = dict(store["ring"][-1])
    b = tps.retrieve(store, present_b, "MOVE:N")
    tps.set_prepared_query_enabled(False)
    store2 = _trained()
    a2 = tps.retrieve(store2, _present(store2), "WAIT")
    tps.append(store2, {"x": 0.99, "y": 0.5})
    b2 = tps.retrieve(store2, dict(store2["ring"][-1]), "MOVE:N")
    tps.set_prepared_query_enabled(True)
    assert a == a2
    assert b == b2
    assert int(store.get("_prepared_query_builds") or 0) >= 2


def test_learn_append_burst():
    store = tps.empty_store()
    store["enabled"] = True
    train_seq(store, [0.0, 0.2, 0.4, 0.6], {"y": 0.90}, reps=3)
    present = {"x": 0.6, "y": 0.90}
    tps.learn(store, consequent=present, action="WAIT", tick=99)
    tps.append(store, present)
    tps.set_prepared_query_enabled(False)
    legacy = {a: deepcopy(tps.retrieve(deepcopy(store), present, a)) for a in ACTIONS}
    tps.set_prepared_query_enabled(True)
    store.pop("_retrieve_cache", None)
    store.pop("_prepared_query", None)
    opt = {a: tps.retrieve(store, present, a) for a in ACTIONS}
    for a in ACTIONS:
        assert opt[a] == legacy[a], a
    assert int(store.get("_prepared_query_builds") or 0) == 1
    tps.set_prepared_query_enabled(True)


def test_restore_drops_prepared_query():
    cfg = CognitionConfig()
    state = empty_cognitive_state(cfg)
    temporal = state["temporal"]
    temporal["enabled"] = True
    train_seq(temporal, [0.0, 0.1, 0.2, 0.3], {"y": 0.1}, reps=2)
    present = _present(temporal)
    tps.retrieve(temporal, present, "WAIT")
    assert "_prepared_query" in temporal
    clear_derived_indexes(state)
    assert "_prepared_query" not in temporal
    tps.set_prepared_query_enabled(False)
    legacy = tps.retrieve(deepcopy(temporal), present, "WAIT")
    tps.set_prepared_query_enabled(True)
    got = tps.retrieve(temporal, present, "WAIT")
    assert got == legacy


def test_two_agent_isolation():
    a = _trained()
    b = tps.empty_store()
    b["enabled"] = True
    train_seq(b, [1.0, 1.2, 1.4, 1.6], {"y": 0.10}, reps=6)
    pa = _present(a)
    pb = _present(b)
    tps.set_prepared_query_enabled(True)
    ra = tps.retrieve(a, pa, "WAIT")
    rb = tps.retrieve(b, pb, "WAIT")
    qa = a["_prepared_query"]
    qb = b["_prepared_query"]
    assert qa is not qb
    assert qa["window_key"] != qb["window_key"]
    assert qa["dfrag"] != qb["dfrag"]
    assert ra != rb
    tps.set_prepared_query_enabled(True)


def test_inner_lags_unchanged():
    store = _trained()
    present = _present(store)
    tps.set_prepared_query_enabled(False)
    legacy = {L: deepcopy(tps.retrieve(deepcopy(store), present, "WAIT", lag=L)) for L in (1, 2, 3, 4)}
    tps.set_prepared_query_enabled(True)
    opt_store = deepcopy(store)
    opt_store.pop("_retrieve_cache", None)
    opt = {L: tps.retrieve(opt_store, present, "WAIT", lag=L) for L in (1, 2, 3, 4)}
    for L in (1, 2, 3, 4):
        assert opt[L] == legacy[L], L
    tps.set_prepared_query_enabled(True)


def test_strip_derived_omits_prepared_query():
    blob = {"_prepared_query": {"window": [1]}, "ring": []}
    assert pe.strip_derived_fields(blob) == {"ring": []}
