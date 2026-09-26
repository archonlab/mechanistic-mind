"""Lossless PE forgotten-class packing: roundtrip, shadow, lifecycle, persist."""
from __future__ import annotations

from copy import deepcopy
from io import StringIO
from json import loads

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.ui.psy_observer_web.run_finalize import dump_persist


def _frag(n: float, width: int = 6, **extra):
    d = {f"k{i}": float(n) + 0.01 * i for i in range(width)}
    d.update(extra)
    return d


def _store():
    s = pe.empty_store()
    s["enabled"] = True
    return s


def _fill_until_forgotten(s, *, width=6, extra=8):
    for i in range(pe.MAX_CLASSES + extra):
        pe.learn(
            s,
            fragment=_frag(float(i), width=width),
            action=f"A{i % 5}",
            consequent={"out": float(i) * 10.0, "z": float(i) % 3},
            tick=i,
            raw_id=f"r{i}",
        )
    return [c for c in s["classes"].values() if c.get("status") == "FORGOTTEN"]


def test_roundtrip_small_and_wide_members_exact_floats():
    for width in (2, 6, 80):
        s = _store()
        pe.set_forgotten_compaction(False)
        try:
            forgotten = _fill_until_forgotten(s, width=width, extra=4)
            assert forgotten
            for cls in forgotten:
                original = deepcopy(cls)
                packed = pe.compact_forgotten_class(deepcopy(cls))
                assert pe.is_forgotten_packed(packed)
                expanded = pe.expand_forgotten_class(packed)
                om = original["members"]
                em = expanded["members"]
                assert set(om) == set(em)
                for sig in om:
                    assert om[sig]["fragment"] == em[sig]["fragment"]
                    assert om[sig]["mean_c"] == em[sig]["mean_c"]
                    assert om[sig]["last_abs"] == em[sig]["last_abs"]
                    assert om[sig]["support"] == em[sig]["support"]
                    assert om[sig]["contra"] == em[sig]["contra"]
                    assert om[sig]["first_tick"] == em[sig]["first_tick"]
                    assert om[sig]["last_tick"] == em[sig]["last_tick"]
                    assert list(om[sig].get("raw_ids") or []) == list(em[sig].get("raw_ids") or [])
                assert original["id"] == expanded["id"]
                assert original["support"] == expanded["support"]
                assert original["aabb"] == expanded["aabb"]
                assert original["mean_c"] == expanded["mean_c"]
                assert original["provenance"] == expanded["provenance"]
        finally:
            pe.set_forgotten_compaction(True)


def test_shadow_reads_match_after_forget():
    pe.set_forgotten_compaction(False)
    try:
        s = _store()
        forgotten = _fill_until_forgotten(s, extra=20)
        snap_full = pe.snapshot(s)
        q = _frag(3.0)
        retrieves = {act: pe.retrieve(s, q, act, count=False) for act in ("A0", "A1", "A2", "A3", "A4")}
        for cls in forgotten:
            pe.compact_forgotten_class(cls)
        assert pe.snapshot(s) == snap_full
        for act, got in retrieves.items():
            assert pe.retrieve(s, q, act, count=False) == got
        # Further learns must not revive forgotten ids.
        before_ids = {c["id"] for c in forgotten}
        pe.learn(s, fragment=_frag(999.0), action="A0", consequent={"out": 1.0}, tick=10_000)
        still = {cid: s["classes"][cid] for cid in before_ids}
        assert all(c.get("status") == "FORGOTTEN" for c in still.values())
        pe.ensure_class_indexes(s)
        for cid in before_ids:
            assert cid not in (s.get("_active_ids") or [])
    finally:
        pe.set_forgotten_compaction(True)


def test_forget_victim_unchanged_by_compaction_flag():
    traces = []
    for compact in (False, True):
        pe.set_forgotten_compaction(compact)
        s = _store()
        events = []
        for i in range(pe.MAX_CLASSES + 12):
            r = pe.learn(
                s,
                fragment=_frag(float(i)),
                action="WAIT",
                consequent={"y": float(i)},
                tick=i,
            )
            events.append((r.get("status"), r.get("class_id"), s["forgotten"]))
        forgotten = [cid for cid, c in s["classes"].items() if c.get("status") == "FORGOTTEN"]
        traces.append((events, forgotten, [c["id"] for c in s["classes"].values() if c.get("status") == "ACTIVE"]))
    pe.set_forgotten_compaction(True)
    assert traces[0] == traces[1]


def test_json_persist_roundtrip_packed_and_legacy_full():
    pe.set_forgotten_compaction(True)
    s = _store()
    forgotten = _fill_until_forgotten(s, extra=3)
    packed = deepcopy(forgotten[0])
    buf = StringIO()
    dump_persist({"classes": {"x": packed}}, buf)
    raw = buf.getvalue()
    loaded = loads(raw)["classes"]["x"]
    pe.compact_forgotten_class(loaded)
    expanded = pe.expand_forgotten_class(loaded)
    original_exp = pe.expand_forgotten_class(packed)
    assert expanded["members"] == original_exp["members"]

    pe.set_forgotten_compaction(False)
    try:
        s2 = _store()
        full_forgotten = _fill_until_forgotten(s2, extra=3)[0]
        assert not pe.is_forgotten_packed(full_forgotten)
        buf2 = StringIO()
        dump_persist({"classes": {"y": full_forgotten}}, buf2)
        loaded_full = loads(buf2.getvalue())["classes"]["y"]
        pe.set_forgotten_compaction(True)
        pe.compact_forgotten_class(loaded_full)
        assert pe.is_forgotten_packed(loaded_full)
        assert pe.expand_forgotten_class(loaded_full)["members"] == pe.expand_forgotten_class(
            pe.compact_forgotten_class(deepcopy(full_forgotten))
        )["members"]
    finally:
        pe.set_forgotten_compaction(True)


def test_runtime_restore_compacts_legacy_forgotten():
    pe.set_forgotten_compaction(False)
    try:
        cfg = tiktaalik_config()
        cfg.cognition.predictive_equivalence = True
        rt = PhysicalSystemRuntime(seed=21, config=cfg)
        for _ in range(120):
            rt.step()
        eq = rt.cognition["equivalence"]
        forgotten = [c for c in (eq.get("classes") or {}).values() if c.get("status") == "FORGOTTEN"]
        if not forgotten:
            pe.set_forgotten_compaction(True)
            return
        assert not pe.is_forgotten_packed(forgotten[0])
        snap = rt.snapshot()
        pe.set_forgotten_compaction(True)
        rest = PhysicalSystemRuntime.restore(snap)
        rest_eq = rest.cognition["equivalence"]
        rest_f = [c for c in (rest_eq.get("classes") or {}).values() if c.get("status") == "FORGOTTEN"]
        assert rest_f and pe.is_forgotten_packed(rest_f[0])
        rest.step()
        rt2 = PhysicalSystemRuntime.restore(snap)
        rt2.step()
        assert rest.last_selected_action == rt2.last_selected_action
    finally:
        pe.set_forgotten_compaction(True)


def test_two_agent_compact_vs_full_actions_match():
    actions = []
    pe_trace = []
    for compact in (False, True):
        pe.set_forgotten_compaction(compact)
        cfg = tiktaalik_config()
        cfg.cognition.predictive_equivalence = True
        cfg.cognition.predictive_relevance = True
        rt = TwoAgentRuntime(seed=21, config=cfg)
        acts = []
        for _ in range(220):
            rt.step()
            acts.append(tuple(slot.last_selected_action for slot in rt.slots))
        eq = rt.slots[0].cognition["equivalence"]
        forgotten_ids = sorted(
            cid for cid, c in (eq.get("classes") or {}).items() if c.get("status") == "FORGOTTEN"
        )
        active_ids = sorted(
            cid for cid, c in (eq.get("classes") or {}).items() if c.get("status") == "ACTIVE"
        )
        actions.append(acts)
        pe_trace.append((eq.get("forgotten"), forgotten_ids, active_ids, pe.snapshot(eq)))
    pe.set_forgotten_compaction(True)
    assert actions[0] == actions[1]
    assert pe_trace[0][0] == pe_trace[1][0]
    assert pe_trace[0][1] == pe_trace[1][1]
    assert pe_trace[0][2] == pe_trace[1][2]
    assert pe_trace[0][3] == pe_trace[1][3]


def test_dump_persist_arrays_are_json():
    s = _store()
    _fill_until_forgotten(s, extra=2)
    cls = next(c for c in s["classes"].values() if c.get("status") == "FORGOTTEN")
    buf = StringIO()
    dump_persist(cls, buf)
    loads(buf.getvalue())
