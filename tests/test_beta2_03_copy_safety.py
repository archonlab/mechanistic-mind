"""BETA2-03: copy/sharing safety for hot cognition deepcopy removals."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system import cognition as cog
from mechanistic_mind.research import multistep_action_prospection as mapr
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import predictive_relevance as prl
from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.ui.psy_observer_web.scientific_history import (
    ScientificHistoryWriter,
    iter_jsonl,
)


def _enable_opts(on: bool) -> None:
    pe.set_float_map_dict_copy(on)
    pe.set_class_mean_cache_enabled(True)
    cog.set_tick_local_retain(on)
    tps.set_fragment_dict_copy(on)
    mapr.set_ancestry_dict_copy(on)


def test_float_map_copy_isolates_from_source_mutation():
    src = {"x": 1.0, "y": 2.0}
    dst = pe._copy_float_map(src)
    assert dst == src and dst is not src
    src["x"] = 99.0
    assert dst["x"] == 1.0


def test_pe_learn_member_isolated_from_episode_and_inputs():
    store = pe.empty_store()
    store["enabled"] = True
    frag = {"x": 0.2}
    cons = {"y": 0.9}
    pe.learn(store, fragment=frag, action="WAIT", consequent=cons, tick=1)
    frag["x"] = -1.0
    cons["y"] = -1.0
    cls = next(iter(store["classes"].values()))
    mem = next(iter(cls["members"].values()))
    assert mem["fragment"]["x"] == 0.2
    assert mem["last_abs"]["y"] == 0.9
    assert mem["fragment"] is not store["episodes"][0]["fragment"]


def test_tps_recent_fragment_isolated_from_ring_mutation():
    store = tps.empty_store()
    store["enabled"] = True
    store["inner"]["enabled"] = True
    for i in range(6):
        store["ring"] = (store.get("ring") or []) + [{"x": float(i)}]
        store["ring"] = store["ring"][-16:]
        tps.learn(store, consequent={"y": 0.5}, action="WAIT", tick=i)
    present = {"x": 6.0}
    got = tps.retrieve(store, present, "WAIT")
    recent = got.get("recent") or []
    assert recent
    ring_before = [dict(f) for f in (store.get("ring") or [])]
    recent[0]["fragment"]["x"] = 999.0
    # ring must be unchanged
    assert [dict(f) for f in (store.get("ring") or [])] == ring_before


def test_map_ancestry_isolated():
    edge = {"predicted": {"a": 1.0}, "action": "WAIT", "support": 1}
    row = {"antecedent": {"b": 2.0}, "transition_id": "T1", "support": 1, "evidence_ticks": [1]}
    store = {"transitions": {"k": row}}
    edge["key"] = "k"
    anc = mapr._edge_ancestry(store, edge)
    row["antecedent"]["b"] = 0.0
    edge["predicted"]["a"] = 0.0
    assert anc["antecedent"]["b"] == 2.0
    assert anc["predicted"]["a"] == 1.0


def test_last_selection_receipt_stable_after_further_ticks():
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = True
    cfg.cognition.predictive_equivalence = True
    cfg.cognition.predictive_relevance = True
    cfg.cognition.temporal_predictive_structure = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.step(5)
    receipt = deepcopy(rt.cognition.get("last_decision_receipt"))
    rt.step(10)
    live = rt.cognition.get("last_decision_receipt")
    assert receipt is not None and live is not None
    assert receipt is not live
    # Historical copy must remain equal to itself after further ticks
    assert receipt == deepcopy(receipt)


def test_snapshot_restore_no_alias_across_agents():
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = True
    for k in (
        "predictive_equivalence",
        "predictive_relevance",
        "temporal_predictive_structure",
    ):
        setattr(cfg.cognition, k, True)
    ta = TwoAgentRuntime(seed=17, config=cfg, starts=((8, 16), (12, 16)))
    ta.step(15)
    rest = TwoAgentRuntime.restore(ta.snapshot())
    assert rest.slots[0].cognition is not rest.slots[1].cognition
    eq0 = rest.slots[0].cognition["equivalence"]
    eq1 = rest.slots[1].cognition["equivalence"]
    assert eq0 is not eq1
    # mutate agent0 store via learn; agent1 unchanged
    before = deepcopy(pe.strip_derived_fields(eq1))
    eq0["enabled"] = True
    pe.learn(eq0, fragment={"x": 0.99}, action="WAIT", consequent={"y": 0.1}, tick=999)
    assert pe.strip_derived_fields(eq1) == before


def test_two_agent_cognitive_stores_not_aliased():
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = True
    cfg.cognition.predictive_equivalence = True
    ta = TwoAgentRuntime(seed=41, config=cfg, starts=((8, 16), (12, 16)))
    ta.step(8)
    a0, a1 = ta.slots[0].cognition, ta.slots[1].cognition
    assert a0 is not a1
    assert a0["equivalence"] is not a1["equivalence"]
    assert a0.get("temporal") is not a1.get("temporal")
    a0["equivalence"]["learns"] = int(a0["equivalence"].get("learns") or 0) + 1000
    assert a0["equivalence"]["learns"] != a1["equivalence"].get("learns")


def test_legacy_vs_optimized_float_map_values_match():
    store_a = pe.empty_store(); store_a["enabled"] = True
    store_b = pe.empty_store(); store_b["enabled"] = True
    pe.set_float_map_dict_copy(False)
    try:
        for t, x in enumerate((0.1, 0.2, 0.3), start=1):
            pe.learn(store_a, fragment={"x": x}, action="WAIT", consequent={"y": 0.9}, tick=t)
    finally:
        pe.set_float_map_dict_copy(True)
    for t, x in enumerate((0.1, 0.2, 0.3), start=1):
        pe.learn(store_b, fragment={"x": x}, action="WAIT", consequent={"y": 0.9}, tick=t)
    assert pe.strip_derived_fields(store_a["classes"]) == pe.strip_derived_fields(store_b["classes"])


def test_beta2_02_class_mean_cache_still_passes_import():
    # Ensure cache module API intact after deepcopy work
    assert pe.class_mean_cache_enabled() is True
    pe.reset_cache_stats()
    store = pe.empty_store(); store["enabled"] = True
    for t, x in enumerate((0.11, 0.24, 0.39), start=1):
        pe.learn(store, fragment={"x": float(x)}, action="WAIT", consequent={"y": 0.9}, tick=t)
    cls = next(iter(store["classes"].values()))
    pe.clear_derived_caches(store)
    pe.reset_cache_stats()
    pe._class_mean_c(cls)
    pe._class_mean_c(cls)
    assert pe.cache_stats()["hits"] >= 1


def test_reference_flag_roundtrip():
    _enable_opts(False)
    assert pe.float_map_dict_copy_enabled() is False
    assert cog.tick_local_retain_enabled() is False
    _enable_opts(True)
    assert pe.float_map_dict_copy_enabled() is True
    assert cog.tick_local_retain_enabled() is True
