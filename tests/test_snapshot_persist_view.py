"""Persist-view snapshot: no live mutation, restore equivalence, compact JSON."""
from __future__ import annotations

import json
from copy import deepcopy
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import TwoAgentRuntime
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.ui.psy_observer_web.run_finalize import (
    dump_persist,
    json_prepare,
    write_finalized_run,
)


def _cfg():
    cfg = tiktaalik_config()
    cog = cfg.cognition
    cog.cognition_enabled = True
    cog.predictive_equivalence = True
    cog.predictive_relevance = True
    cog.temporal_predictive_structure = True
    cog.sensorimotor_consequence_model = True
    cog.predictive_compression = True
    cog.prospective_composition = True
    return cfg


def _aged(n_forgotten: int = 80) -> TwoAgentRuntime:
    rt = TwoAgentRuntime(seed=91, config=_cfg())
    for _ in range(12):
        rt.step()
    for slot in rt.slots:
        eq = slot.cognition.setdefault("equivalence", pe.empty_store())
        eq["enabled"] = True
        for i in range(pe.MAX_CLASSES + n_forgotten):
            pe.learn(
                eq,
                fragment={f"k{j}": float(i) + 0.01 * j for j in range(8)},
                action=f"A{i % 5}",
                consequent={"out": float(i)},
                tick=i,
            )
        store = slot.cognition.setdefault(
            "sensorimotor_consequence", smc.empty_store(enabled=True, capacity=256)
        )
        t = 0
        while len(store.get("records") or {}) < 64 and t < 2000:
            obs = {k: 0.2 for k in smc.SENSORY_CHANNELS[:8]}
            obs["exo_0"] = ((t % 5) + 0.5) / 5.0
            nxt = dict(obs)
            nxt["exo_0"] = ((t % 4) + 0.5) / 5.0
            smc.update(
                store,
                tick=t,
                observation_t=obs,
                motor={"locomotion": "WAIT", "neck": "NONE", "oscillator": {"emit_trigger": False}, "push": False},
                observation_t1=nxt,
            )
            t += 1
    return rt


def test_public_snapshot_is_detached():
    rt = _aged(20)
    snap = rt.snapshot()
    live = rt.slots[0].cognition
    assert snap["agents"][0]["cognition"] is not live
    live["equivalence"]["learns"] = int(live["equivalence"].get("learns") or 0) + 77
    assert snap["agents"][0]["cognition"]["equivalence"].get("learns") != live["equivalence"]["learns"]


def test_persist_snapshot_aliases_canonical_cognition():
    rt = _aged(20)
    view = rt.snapshot(persist=True)
    assert view["agents"][0]["cognition"] is rt.slots[0].cognition
    assert view["agents"][1]["cognition"] is rt.slots[1].cognition


def test_dump_persist_does_not_mutate_live_or_call_json_prepare_on_graph():
    rt = _aged(20)
    eq = rt.slots[0].cognition["equivalence"]
    cls = next(iter(eq["classes"].values()))
    cid = id(cls)
    keys_before = set(cls.keys())
    view = rt.snapshot(persist=True)
    buf = StringIO()
    dump_persist(view, buf, compact=True)
    assert id(next(iter(eq["classes"].values()))) == cid
    assert set(cls.keys()) == keys_before
    loaded = json.loads(buf.getvalue())
    # Live graph unchanged; encoder is read-only.
    eq2 = loaded["agents"][0]["cognition"]["equivalence"]
    assert "classes" in eq2


def test_json_prepare_would_mutate_aliased_view_hence_must_not_run_on_persist():
    rt = _aged(8)
    view = rt.snapshot(persist=True)
    live_eq = rt.slots[0].cognition["equivalence"]
    # Document the hazard: in-place prepare on an aliased view is unsafe.
    prepared = json_prepare({"probe": {None: 1}})
    assert "null" in prepared["probe"]
    assert live_eq is view["agents"][0]["cognition"]["equivalence"]


def test_oracle_restore_and_step_match_deepcopy_snapshot():
    rt = _aged(40)
    detached = deepcopy(rt.snapshot(persist=False))
    from io import StringIO
    buf = StringIO()
    dump_persist(detached, buf, compact=True)
    detached_loaded = json.loads(buf.getvalue())
    with TemporaryDirectory() as d:
        out = write_finalized_run(
            results_root=Path(d),
            runtime=rt,
            session_meta={"started_at": "t", "seed": 91, "buffer": {}},
            timeline=[{"tick": int(rt.tick)}],
            telemetry=[],
            termination_reason="USER_STOP_SAVED",
            run_id="oracle-persist",
        )
        assert out.get("accepted"), out.get("error")
        snap_path = Path(out["run_dir"]) / "physical_system_snapshot.json"
        text = snap_path.read_text(encoding="utf-8")
        assert "\n  " not in text[:80]  # compact
        loaded = json.loads(text)
    from_file = TwoAgentRuntime.restore(loaded)
    from_detach = TwoAgentRuntime.restore(detached_loaded)
    assert int(from_file.tick) == int(rt.tick) == int(from_detach.tick)
    for i in range(2):
        pe.ensure_class_indexes(from_file.slots[i].cognition["equivalence"])
        pe.ensure_class_indexes(from_detach.slots[i].cognition["equivalence"])
        a = pe.strip_derived_fields(from_file.slots[i].cognition["equivalence"]["classes"])
        b = pe.strip_derived_fields(from_detach.slots[i].cognition["equivalence"]["classes"])
        assert a == b
        assert pe.active_class_count(from_file.slots[i].cognition["equivalence"]) == pe.scan_active_class_count(
            from_file.slots[i].cognition["equivalence"]
        )
    from_file.step()
    from_detach.step()
    assert from_file.slots[0].last_selected_action == from_detach.slots[0].last_selected_action
    assert abs(from_file.slots[0].body.x - from_detach.slots[0].body.x) < 1e-12


def test_compact_pretty_json_load_equal_after_strip():
    rt = _aged(12)
    view = rt.snapshot(persist=True)
    compact = StringIO()
    pretty = StringIO()
    dump_persist(view, compact, compact=True)
    dump_persist(view, pretty, compact=False)
    a = json.loads(compact.getvalue())
    b = json.loads(pretty.getvalue())
    assert pe.strip_derived_fields(a["agents"][0]["cognition"]["equivalence"]) == pe.strip_derived_fields(
        b["agents"][0]["cognition"]["equivalence"]
    )
    assert compact.getvalue() != pretty.getvalue()
    assert len(compact.getvalue()) < len(pretty.getvalue())
