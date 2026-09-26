"""P0 cognition indexes: PE ACTIVE/FORGOTTEN, incremental PE, SMC loco, signature reuse."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system import observed_composite_psc as oc
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.physical_system.o_prime_history_bridge import query_history_on_o_prime
from mechanistic_mind.physical_system.psc_motor_resolution_shadow import (
    observed_composites_for_loco,
    observed_composites_for_loco_scan,
)
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import prospective_composition as pr


def _frag(n: float, **extra):
    d = {f"k{i}": float(n) + 0.01 * i for i in range(6)}
    d.update(extra)
    return d


def _store():
    s = pe.empty_store()
    s["enabled"] = True
    return s


def test_forgotten_does_not_participate_in_retrieve_or_host():
    s = _store()
    for i in range(pe.MAX_CLASSES + 8):
        pe.learn(
            s,
            fragment=_frag(float(i)),
            action=f"A{i % 5}",
            consequent={"out": float(i) * 10.0},
            tick=i,
        )
    forgotten = [c for c in s["classes"].values() if c.get("status") == "FORGOTTEN"]
    assert forgotten
    pe.ensure_class_indexes(s)
    for cls in forgotten:
        cid = str(cls["id"])
        assert cid not in (s.get("_active_ids") or [])
        act = str(cls.get("action") or "")
        assert cid not in (s.get("_ix_action") or {}).get(act, [])
        got = pe.retrieve(s, pe.forgotten_member_fragment(cls, next(iter(cls["members"]))), act, count=False)
        # Forgotten AABB must not win; class_id if MATCH cannot be forgotten id
        if got.get("status") == "MATCH":
            assert got.get("class_id") != cid


def test_active_count_o1_matches_scan_through_forget():
    s = _store()
    pe.set_index_validate(True)
    try:
        for i in range(pe.MAX_CLASSES + 12):
            pe.learn(
                s,
                fragment=_frag(float(i) * 0.17),
                action="WAIT" if i % 2 == 0 else "MOVE:N",
                consequent={"y": float(i)},
                tick=i,
            )
            assert pe.active_class_count(s) == pe.scan_active_class_count(s)
            assert pe.active_class_count(s) <= pe.MAX_CLASSES
            assert pe.capture_index_payload(s) == pe.rebuild_reference_index_payload(s)
    finally:
        pe.set_index_validate(False)


def test_forget_victim_matches_old_min_support_insertion_order():
    s = _store()
    # Fill 32 distinct classes with increasing support via extra updates on early ones.
    for i in range(pe.MAX_CLASSES):
        pe.learn(s, fragment=_frag(float(i)), action="WAIT", consequent={"y": float(i)}, tick=i)
    # Boost first class support
    for t in range(5):
        pe.learn(s, fragment=_frag(0.0), action="WAIT", consequent={"y": 0.0}, tick=100 + t)
    before = [cid for cid, c in s["classes"].items() if c.get("status") == "ACTIVE"]
    assert len(before) == pe.MAX_CLASSES
    # Next distinct continuation forces forget of lowest-support ACTIVE (not boosted E1)
    pe.learn(s, fragment=_frag(99.0), action="WAIT", consequent={"y": 99.0}, tick=200)
    forgotten = [cid for cid, c in s["classes"].items() if c.get("status") == "FORGOTTEN"]
    assert forgotten
    # Lowest original support among the un-boosted should go first (E2 formed at i=1, support 1)
    assert "E1" not in forgotten
    assert pe.active_class_count(s) == pe.MAX_CLASSES
    assert pe.capture_index_payload(s) == pe.rebuild_reference_index_payload(s)


def test_learn_trace_stable_class_assignment():
    s = _store()
    trace = []
    for i in range(40):
        r = pe.learn(
            s,
            fragment=_frag(0.01 * (i % 9), z=float(i % 3)),
            action="WAIT",
            consequent={"y": 0.9 if i % 9 < 5 else 0.1},
            tick=i,
        )
        trace.append((r.get("status"), r.get("class_id")))
    # Replay on a fresh store must match
    s2 = _store()
    trace2 = []
    for i in range(40):
        r = pe.learn(
            s2,
            fragment=_frag(0.01 * (i % 9), z=float(i % 3)),
            action="WAIT",
            consequent={"y": 0.9 if i % 9 < 5 else 0.1},
            tick=i,
        )
        trace2.append((r.get("status"), r.get("class_id")))
    assert trace == trace2
    assert pe.strip_derived_fields(s["classes"]) == pe.strip_derived_fields(s2["classes"])


def test_incremental_equals_rebuild_after_join_split_update():
    s = _store()
    pe.set_index_validate(True)
    try:
        for i in range(6):
            pe.learn(s, fragment={"x": 0.11}, action="WAIT", consequent={"y": 0.90}, tick=i)
            pe.learn(s, fragment={"x": 0.24}, action="WAIT", consequent={"y": 0.90}, tick=i)
        for i in range(8):
            pe.learn(s, fragment={"x": 0.24}, action="WAIT", consequent={"y": 0.10}, tick=100 + i)
        assert pe.capture_index_payload(s) == pe.rebuild_reference_index_payload(s)
        assert s["splits"] >= 1
    finally:
        pe.set_index_validate(False)


def test_retrieve_indexed_equals_full_scan_with_forgotten():
    s = _store()
    for i in range(pe.MAX_CLASSES + 10):
        pe.learn(
            s,
            fragment=_frag(float(i)),
            action=f"A{i % 4}",
            consequent={"out": float(i)},
            tick=i,
        )
    q = _frag(3.0)
    for act in ("A0", "A1", "A2", "A3", "WAIT"):
        assert pe.retrieve(s, q, act, count=False) == pe._retrieve_full_scan_reference(
            s, q, act, count=False
        )


def test_strip_derived_omits_active_index_keys():
    s = _store()
    pe.learn(s, fragment=_frag(0), action="WAIT", consequent=_frag(1), tick=0)
    pe.ensure_class_indexes(s)
    stripped = pe.strip_derived_fields(s)
    assert "_active_ids" not in stripped
    assert "_active_count" not in stripped
    assert "_ix_action" not in stripped


def test_smc_observed_composites_index_equals_scan():
    store = smc.empty_store(enabled=True)
    base = {k: 0.25 for k in smc.SENSORY_CHANNELS}
    motors = [
        {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {}, "push": False},
        {"locomotion": "MOVE:E", "neck": "NECK_RIGHT", "oscillator": {"emit_trigger": True}, "push": False},
        {"locomotion": "WAIT", "neck": "NONE", "oscillator": {}, "push": False},
        {"locomotion": "MOVE:N", "neck": "NONE", "oscillator": {}, "push": True},
    ]
    for t, m in enumerate(motors * 40):
        nxt = {**base, "exo_0": 0.1 * (t % 7)}
        smc.update(store, tick=t, observation_t=base, motor=m, observation_t1=nxt)
    assert len(store["records"]) <= store["capacity"]
    for loco in ("WAIT", "MOVE:E", "MOVE:N", "MOVE:S"):
        a = observed_composites_for_loco(store, loco)
        b = observed_composites_for_loco_scan(store, loco)
        assert [r["motor_signature"] for r in a] == [r["motor_signature"] for r in b]
        assert [r["support"] for r in a] == [r["support"] for r in b]


def test_observed_composite_selection_matches_scan_path():
    store = smc.empty_store(enabled=True)
    base = {k: 0.25 for k in smc.SENSORY_CHANNELS}
    m1 = {"locomotion": "MOVE:E", "neck": "NECK_LEFT", "oscillator": {}, "push": False}
    m2 = {"locomotion": "MOVE:E", "neck": "NECK_RIGHT", "oscillator": {}, "push": False}
    for i in range(6):
        smc.update(
            store, tick=i, observation_t=base, motor=m1,
            observation_t1={**base, "exo_0": 0.9},
        )
        smc.update(
            store, tick=20 + i, observation_t=base, motor=m2,
            observation_t1={**base, "exo_0": 0.1},
        )
    prosp = pr.empty_store()
    locos = ["WAIT", "MOVE:E"]
    c_idx = oc.collect_observed_candidates(
        observation=base, smc_store=store, loco_candidates=locos,
        prospection=prosp, compression=None, retrieval_enabled=False, tick=100,
    )
    # Force scan-backed candidate gen
    orig = oc.observed_composites_for_loco
    try:
        oc.observed_composites_for_loco = observed_composites_for_loco_scan  # type: ignore[method-assign]
        c_scan = oc.collect_observed_candidates(
            observation=base, smc_store=store, loco_candidates=locos,
            prospection=prosp, compression=None, retrieval_enabled=False, tick=100,
        )
    finally:
        oc.observed_composites_for_loco = orig  # type: ignore[method-assign]
    assert [c["motor_signature"] for c in c_idx] == [c["motor_signature"] for c in c_scan]
    sel_a = oc.select_observed_composite_motor(
        observation=base, smc_store=store, loco_candidates=locos,
        prospection=prosp, compression=None, retrieval_enabled=False, tick=100, rng_value=0.3,
    )
    sel_b = oc.select_observed_composite_motor(
        observation=base, smc_store=store, loco_candidates=locos,
        prospection=prosp, compression=None, retrieval_enabled=False, tick=100, rng_value=0.3,
    )
    assert sel_a["status"] == sel_b["status"]
    if sel_a.get("motor") is not None:
        assert sel_a["motor"].to_dict() == sel_b["motor"].to_dict()


def test_query_history_signature_reuse_same_result():
    mem = pc.empty_memory()
    o = {f"k{i}": 0.1 * i for i in range(8)}
    for i in range(5):
        pc.observe(
            mem, tick=i, fragment=o, action="WAIT",
            predicted={}, realized={**o, "k0": 0.9}, domain="accessible",
        )
    prosp = pr.empty_store()
    a = query_history_on_o_prime(
        prospection=prosp, compression=mem, o_prime=o,
        actions=["WAIT", "MOVE:N", "MOVE:S"], retrieval_enabled=True,
    )
    b = query_history_on_o_prime(
        prospection=prosp, compression=mem, o_prime=o,
        actions=["WAIT", "MOVE:N", "MOVE:S"], retrieval_enabled=True,
    )
    assert a == b
    direct = pc.predict(mem, o, "WAIT", domain="accessible")
    reused = pc.predict(mem, o, "WAIT", domain="accessible", antecedent_sig=pc._sig(o))
    assert direct == reused


def test_save_resume_reconstructs_pe_and_smc_indexes():
    cfg = tiktaalik_config()
    cfg.cognition.predictive_equivalence = True
    cfg.cognition.predictive_relevance = True
    cfg.cognition.temporal_predictive_structure = True
    cfg.cognition.sensorimotor_consequence_model = True
    rt = PhysicalSystemRuntime(seed=21, config=cfg)
    for _ in range(80):
        rt.step()
    pe.ensure_class_indexes(rt.cognition["equivalence"])
    before_eq = pe.strip_derived_fields(rt.cognition["equivalence"]["classes"])
    before_active = pe.scan_active_class_count(rt.cognition["equivalence"])
    smc.ensure_indexes(rt.cognition["sensorimotor_consequence"])
    snap = rt.snapshot()
    rest = PhysicalSystemRuntime.restore(snap)
    assert pe.strip_derived_fields(rest.cognition["equivalence"]["classes"]) == before_eq
    assert "_ix_action" not in rest.cognition["equivalence"] or rest.cognition["equivalence"].get(
        "_ix_built_gen"
    ) != rest.cognition["equivalence"].get("_ix_gen")
    pe.ensure_class_indexes(rest.cognition["equivalence"])
    assert pe.active_class_count(rest.cognition["equivalence"]) == before_active
    assert pe.capture_index_payload(rest.cognition["equivalence"]) == pe.rebuild_reference_index_payload(
        rest.cognition["equivalence"]
    )
    smc.ensure_indexes(rest.cognition["sensorimotor_consequence"])
    keys_a = set(rt.cognition["sensorimotor_consequence"]["records"])
    keys_b = set(rest.cognition["sensorimotor_consequence"]["records"])
    assert keys_a == keys_b
    rest.step()
    rt2 = PhysicalSystemRuntime.restore(snap)
    rt2.step()
    assert rest.last_selected_action == rt2.last_selected_action


def test_two_agent_save_resume_indexes():
    cfg = tiktaalik_config()
    cfg.cognition.predictive_equivalence = True
    cfg.cognition.temporal_predictive_structure = True
    cfg.cognition.sensorimotor_consequence_model = True
    rt = TwoAgentRuntime(seed=33, config=cfg)
    for _ in range(40):
        rt.step()
    snap = rt.snapshot()
    rest = TwoAgentRuntime.restore(snap)
    for slot in rest.slots:
        eq = slot.cognition["equivalence"]
        pe.ensure_class_indexes(eq)
        assert pe.active_class_count(eq) == pe.scan_active_class_count(eq)
        assert pe.capture_index_payload(eq) == pe.rebuild_reference_index_payload(eq)
    rest.step()
    rt2 = TwoAgentRuntime.restore(deepcopy(snap))
    rt2.step()
    assert [s.last_selected_action for s in rest.slots] == [s.last_selected_action for s in rt2.slots]
