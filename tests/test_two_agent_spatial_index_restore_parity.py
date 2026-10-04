"""TWO-AGENT SPATIAL INDEX RESTORE PARITY.

Contract: snapshot at tick T -> TwoAgentRuntime.restore -> immediate read-only spatial queries equal the
queries of the original runtime at tick T, with no extra scientific tick. Numbered 1-24 as in the spec
(+ 25: read-only diagnostic). Real TwoAgentRuntime / PhysicalSystemRuntime / ObserverSession.
"""
from __future__ import annotations

import json
import math

import pytest

from mechanistic_mind.model.acanthostega import (
    acanthostega_column_transfer_config,
    acanthostega_contact_acoustics_config,
    acanthostega_free_object_kinematics_config,
    acanthostega_world_material_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import free_resource_object_kinematics as fok
from mechanistic_mind.physical_system.near_field_exteroception import moore_neighbor_cells
from mechanistic_mind.physical_system.physical_manipulator import effector_world_xy
from mechanistic_mind.physical_system.resource_objects import ResourceObject, resource_object_optical_occupancy
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import (
    body_refs_for_runtime,
    checksum_of,
    contents_in_wrapped_cells,
    occupied_cell_summary,
    rebuild_after_restore,
    rebuild_from_world,
    reconcile_contents,
    spatial_index_consistency,
    world_cell,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

W = H = 32


# ---------------------------------------------------------------- helpers


def rt_json(x):
    return json.loads(json.dumps(x))


def restore(tr):
    return TwoAgentRuntime.restore(rt_json(tr.snapshot()))


def refs(w):
    """Every ref as stored in by_cell (duplicates would show). pose_tick excluded: see docs §8."""
    return sorted((r.entity_kind, r.entity_id, r.cell_x, r.cell_y, r.state_revision)
                  for b in w.spatial_contents.by_cell.values() for r in b)


def cells(w):
    return {c: sorted((r.entity_kind, r.entity_id) for r in b) for c, b in w.spatial_contents.by_cell.items() if b}


def entity_cells(w):
    out = {}
    for c, b in w.spatial_contents.by_cell.items():
        for r in b:
            out.setdefault((r.entity_kind, r.entity_id), []).append(c)
    return {k: sorted(v) for k, v in out.items()}


def bodies_in_index(w):
    return sorted(r.entity_id for b in w.spatial_contents.by_cell.values() for r in b if r.entity_kind == "BODY")


def kin(o):
    return (o.object_id, o.x, o.y, o.vx, o.vy, o.physical_state, o.holder_body_id, o.manipulator_id)


def clone_object(w, src, oid, x, y):
    d = dict(src.to_dict(), object_id=oid, x=float(x), y=float(y), physical_state="FREE_STATIC",
             holder_body_id=None, manipulator_id=None, vx=0.0, vy=0.0)
    o = ResourceObject.from_dict(d)
    w.resource_objects.append(o)
    # keep the world's id allocator coherent, as the real spawn path does
    w.resource_object_next_id = max(int(getattr(w, "resource_object_next_id", 1) or 1), int(oid.split("-")[-1]) + 1)
    return o


def rich():
    """Two-agent FOK world at tick T with: body-1 across the WRAP corner, a FREE_MOVING object at the
    x edge, an object HELD by agent_1, two objects in one cell, an object in body-0's cell."""
    tr = TwoAgentRuntime(seed=17, config=acanthostega_free_object_kinematics_config())
    tr.step(2)
    w = tr.world
    b0, b1 = tr.slots[0].body, tr.slots[1].body
    b1.x, b1.y = 31.95, 0.02
    o1, o2 = w.resource_objects[0], w.resource_objects[1]
    o1.x, o1.y, o1.physical_state, o1.vx, o1.vy = 31.99, 0.5, "FREE_MOVING", 0.3, 0.1
    s1 = tr.slots[1]
    ex, ey = effector_world_xy(b1, width=W, height=H, config=s1.config, manipulator_id="LEFT", runtime=s1)
    o2.x, o2.y, o2.physical_state, o2.holder_body_id, o2.manipulator_id = ex, ey, "HELD", "agent_1", "LEFT"
    clone_object(w, o1, "resource-000003", 5.2, 5.3)
    clone_object(w, o1, "resource-000004", 5.7, 5.8)
    clone_object(w, o1, "resource-000005", math.floor(b0.x) + 0.5, math.floor(b0.y) + 0.5)
    # end-of-tick invariant of the continuous run: the container reconcile over all bodies
    reconcile_contents(w, body_refs_for_runtime(tr), tick=int(tr.tick), reason="test_setup", config=tr.config)
    assert tr.spatial_index_consistency()["spatial_index_consistent_with_authoritative_state"]
    return tr


@pytest.fixture()
def pair():
    tr = rich()
    snap = rt_json(tr.snapshot())
    return tr, TwoAgentRuntime.restore(snap), snap


# ---------------------------------------------------------------- direct restore (1-5)


def test_01_02_03_both_bodies_immediately_exactly_once_no_tick(pair):
    tr, r2, snap = pair
    assert r2.tick == tr.tick == snap["tick"]                         # 2: no tick advanced
    assert bodies_in_index(r2.world) == ["body-0", "body-1"]          # 1: both present immediately
    ec = entity_cells(r2.world)
    assert ec[("BODY", "body-0")] == [world_cell(r2.slots[0].body.x, r2.slots[0].body.y, width=W, height=H)]
    assert ec[("BODY", "body-1")] == [(31, 0)]
    assert all(len(v) == 1 for v in ec.values())                      # 3: exactly once
    assert r2.spatial_index_consistency()["spatial_index_consistent_with_authoritative_state"]


def test_04_reverse_process_order_same_index():
    runs = []
    for order in ((0, 1), (1, 0)):
        tr = TwoAgentRuntime(seed=17, config=acanthostega_free_object_kinematics_config(), process_order=order)
        tr.step(2)
        r2 = restore(tr)
        assert refs(r2.world) == refs(tr.world)
        runs.append(r2)
    # body enumeration order does not matter for the rebuild
    r2 = runs[0]
    before = refs(r2.world)
    rebuild_from_world(r2.world, list(reversed(body_refs_for_runtime(r2))), tick=r2.tick, reason="t", config=r2.config)
    assert refs(r2.world) == before


def test_05_repeated_rebuild_or_reconcile_creates_no_duplicates(pair):
    _, r2, _ = pair
    before, gen = refs(r2.world), r2.world.spatial_contents.generation
    reconcile_contents(r2.world, body_refs_for_runtime(r2), tick=r2.tick, reason="t", config=r2.config)
    assert refs(r2.world) == before and r2.world.spatial_contents.generation == gen   # no change at all
    for _ in range(2):
        rebuild_after_restore(r2.world, body_refs_for_runtime(r2), tick=r2.tick, config=r2.config)
        assert refs(r2.world) == before
    assert r2.spatial_index_consistency()["duplicate_refs"] == []


# ---------------------------------------------------------------- resource objects (6-10)


def test_06_free_static_object_present_immediately(pair):
    tr, r2, _ = pair
    ec = entity_cells(r2.world)
    o = next(x for x in r2.world.resource_objects if x.object_id == "resource-000003")
    assert o.physical_state == "FREE_STATIC"
    assert ec[("RESOURCE_OBJECT", "resource-000003")] == [(5, 5)]


def test_07_free_moving_at_snapshot_pose_not_moved(pair):
    tr, r2, snap = pair
    a = next(o for o in tr.world.resource_objects if o.object_id == "resource-000001")
    b = next(o for o in r2.world.resource_objects if o.object_id == "resource-000001")
    assert kin(b) == kin(a) and b.physical_state == "FREE_MOVING" and (b.vx, b.vy) == (0.3, 0.1)
    assert entity_cells(r2.world)[("RESOURCE_OBJECT", "resource-000001")] == [(31, 0)]
    assert fok.state_of(r2.world).last_integrated_tick == fok.state_of(tr.world).last_integrated_tick
    assert fok.state_of(r2.world).counters == fok.state_of(tr.world).counters


def test_08_held_object_contract_and_holder_preserved(pair):
    """Contract (unchanged): a HELD object is an index entity at its authoritative world pose
    (= holder effector pose), exactly once, never duplicated as free. Holder/hand must survive restore
    (regression: slot-0 restore used to sanitize the shared world with {'agent_0'} only)."""
    tr, r2, _ = pair
    a = next(o for o in tr.world.resource_objects if o.object_id == "resource-000002")
    b = next(o for o in r2.world.resource_objects if o.object_id == "resource-000002")
    assert kin(b) == kin(a)
    assert (b.physical_state, b.holder_body_id, b.manipulator_id) == ("HELD", "agent_1", "LEFT")
    assert entity_cells(r2.world)[("RESOURCE_OBJECT", "resource-000002")] == \
        entity_cells(tr.world)[("RESOURCE_OBJECT", "resource-000002")] == [world_cell(b.x, b.y, width=W, height=H)]


def test_09_two_objects_one_cell_preserved(pair):
    _, r2, _ = pair
    assert cells(r2.world)[(5, 5)] == [("RESOURCE_OBJECT", "resource-000003"), ("RESOURCE_OBJECT", "resource-000004")]


def test_10_body_and_object_same_cell_distinct_refs(pair):
    tr, r2, _ = pair
    b0 = r2.slots[0].body
    c = world_cell(b0.x, b0.y, width=W, height=H)
    assert ("BODY", "body-0") in cells(r2.world)[c] and ("RESOURCE_OBJECT", "resource-000005") in cells(r2.world)[c]
    assert cells(r2.world)[c] == cells(tr.world)[c]
    assert occupied_cell_summary(r2.world) == occupied_cell_summary(tr.world)


# ---------------------------------------------------------------- WRAP (11-13)


def test_11_12_13_wrap_cells_no_mirror_or_repeated_refs(pair):
    tr, r2, _ = pair
    ec = entity_cells(r2.world)
    assert ec[("BODY", "body-1")] == [(31, 0)]                         # body across the corner
    assert ec[("RESOURCE_OBJECT", "resource-000001")] == [(31, 0)]     # object at the x edge
    assert all(len(v) == 1 for v in ec.values())
    assert all(0 <= cx < W and 0 <= cy < H for cx, cy in cells(r2.world))
    assert not any(("BODY", "body-1") in v for c, v in cells(r2.world).items() if c != (31, 0))


# ---------------------------------------------------------------- continuation (14-18)


def test_14_continuous_and_restored_index_equal_at_T(pair):
    tr, r2, _ = pair
    assert refs(r2.world) == refs(tr.world)
    assert cells(r2.world) == cells(tr.world)
    assert entity_cells(r2.world) == entity_cells(tr.world)
    assert r2.world.spatial_index_checksum == tr.world.spatial_index_checksum == checksum_of(r2.world.spatial_contents)
    assert r2.world.spatial_contents.generation == tr.world.spatial_contents.generation
    assert r2.world.spatial_contents.dirty is False


def test_15_16_next_tick_identical_and_free_moving_single_step(pair):
    tr, r2, _ = pair
    o_a = next(o for o in tr.world.resource_objects if o.object_id == "resource-000001")
    o_b = next(o for o in r2.world.resource_objects if o.object_id == "resource-000001")
    x0 = o_a.x
    for _ in range(3):
        tr.step()
        r2.step()
        assert refs(r2.world) == refs(tr.world)
        assert [kin(o) for o in r2.world.resource_objects] == [kin(o) for o in tr.world.resource_objects]
        assert [(s.body.x, s.body.y, s.body.theta) for s in r2.slots] == [(s.body.x, s.body.y, s.body.theta) for s in tr.slots]
    # first post-restore tick moved the FREE_MOVING object by exactly one damp-then-drift step
    ms = [m for m in fok.state_of(r2.world).motion_history if m["object_id"] == "resource-000001"]
    first = next(m for m in ms if m["start_position"][0] == x0)
    assert first["displacement"][0] == pytest.approx(0.3 * math.exp(-0.25))
    assert first["wrap_occurred"] is True
    assert o_b.x == o_a.x


def test_17_near_field_queries_equal_immediately(pair):
    tr, r2, _ = pair
    for i in (0, 1):
        for rt in (tr, r2):
            assert rt.slots[i].body.x == tr.slots[i].body.x
        b = tr.slots[i].body
        nb = moore_neighbor_cells(int(math.floor(b.x)) % W, int(math.floor(b.y)) % H, W, H)
        assert resource_object_optical_occupancy(r2.world, enabled=True, cells=nb) == \
            resource_object_optical_occupancy(tr.world, enabled=True, cells=nb)
        key = lambda rs: sorted((r.entity_kind, r.entity_id, r.cell_x, r.cell_y) for r in rs)  # noqa: E731
        assert key(contents_in_wrapped_cells(r2.world, nb)) == key(contents_in_wrapped_cells(tr.world, nb))
    # body-cell lookup (local signal transport seam) uses the index immediately, not the fallback
    from mechanistic_mind.physical_system.local_physical_signal_transport import _body_lookup
    c2: dict = {}
    look, mode = _body_lookup(r2.world, body_refs_for_runtime(r2), W, H, c2)
    assert mode == "MULTI_CONTENT_SPATIAL_INDEX" and c2 == {}
    assert look((31, 0)) == ["body-1"]
    # researcher serialization spatial summary (pose_tick = rebuild metadata, excluded; docs §8)
    from mechanistic_mind.ui.psy_observer_web.serialize import _spatial_contents_payload

    def strip(p):
        p = json.loads(json.dumps(p))
        for c in p["spatial_cell_contents"]:
            for r in c["refs"]:
                r.pop("pose_tick")
        return p
    assert strip(_spatial_contents_payload(r2.world)) == strip(_spatial_contents_payload(tr.world))


def test_18_contact_and_acoustic_state_unchanged_by_restore():
    from mechanistic_mind.physical_system import local_physical_signal_transport as lps
    from mechanistic_mind.physical_system import physical_contact_acoustic_emission as pca

    tr = TwoAgentRuntime(seed=17, config=acanthostega_contact_acoustics_config())
    tr.step(3)
    r2 = restore(tr)
    assert pca.serialize_state(pca.state_of(r2.world)) == pca.serialize_state(pca.state_of(tr.world))
    assert lps.serialize_state(lps.state_of(r2.world)) == lps.serialize_state(lps.state_of(tr.world))
    assert r2.last_contacts == [] and r2.last_contact is None
    assert bodies_in_index(r2.world) == ["body-0", "body-1"]
    tr.step()
    r2.step()
    assert pca.serialize_state(pca.state_of(r2.world)) == pca.serialize_state(pca.state_of(tr.world))
    # After a live step, LPS carries wall-clock cost telemetry (cost_max.step_us, perf_counter);
    # it is not physical state and differs between any two steps -> only *_us keys excluded.
    assert _no_wallclock(lps.serialize_state(lps.state_of(r2.world))) == _no_wallclock(
        lps.serialize_state(lps.state_of(tr.world))
    )


def _no_wallclock(x):
    if isinstance(x, dict):
        return {k: _no_wallclock(v) for k, v in x.items() if not str(k).endswith("_us")}
    if isinstance(x, list):
        return [_no_wallclock(v) for v in x]
    return x


# ---------------------------------------------------------------- compatibility (19-24)


def test_19_single_agent_restore_unchanged():
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_column_transfer_config())
    rt.step(2)
    o = rt.world.resource_objects[0]
    o.physical_state, o.holder_body_id, o.manipulator_id = "HELD", "agent_1", "LEFT"  # foreign holder
    snap = rt_json(rt.snapshot())
    back = PhysicalSystemRuntime.restore(snap)
    # single-agent policy unchanged: sanitize with {technical_id}, rebuild once, saved generation kept
    assert back.world.resource_objects[0].physical_state == "FREE_STATIC"
    hist = back.world.spatial_index_history
    assert [(e["event"], e["reason"]) for e in hist] == [("SPATIAL_CONTENTS_INDEX_REBUILT", "restore")]
    assert back.world.spatial_contents.generation == snap["world"]["spatial_index_generation"]
    assert spatial_index_consistency(back.world, body_refs_for_runtime(back))["spatial_index_consistent_with_authoritative_state"]


def _strip_private(x):
    if isinstance(x, dict):
        return {k: _strip_private(v) for k, v in x.items() if not str(k).startswith("_")}
    if isinstance(x, list):
        return [_strip_private(v) for v in x]
    return x


def test_20_tiktaalik_restore_unchanged():
    tr = TwoAgentRuntime(seed=17, config=tiktaalik_config())
    tr.step(3)
    snap = rt_json(tr.snapshot())
    r2 = TwoAgentRuntime.restore(snap)
    assert getattr(r2.world, "spatial_contents", None) is None
    assert _strip_private(rt_json(r2.snapshot())) == _strip_private(snap)
    rt = PhysicalSystemRuntime(seed=17, config=tiktaalik_config())
    rt.step(3)
    s1 = rt_json(rt.snapshot())
    b1 = PhysicalSystemRuntime.restore(s1)
    assert getattr(b1.world, "spatial_contents", None) is None
    assert _strip_private(rt_json(b1.snapshot())) == _strip_private(s1)


def test_21_old_snapshots_load():
    # (a) index-era two-agent snapshot without checksum/generation keys
    tr = rich()
    snap = rt_json(tr.snapshot())
    for wd in (snap["world"], snap["agents"][0]["world"]):
        for k in ("spatial_index_generation", "spatial_index_schema", "spatial_index_checksum"):
            wd.pop(k, None)
    r2 = TwoAgentRuntime.restore(snap)
    assert refs(r2.world) == refs(tr.world) and r2.world.spatial_contents.generation == 1
    # (b) Acanthostega two-agent snapshot from before the spatial index
    old = TwoAgentRuntime(seed=17, config=acanthostega_world_material_config())
    old.step(2)
    r3 = restore(old)
    assert getattr(r3.world, "spatial_contents", None) is None
    assert _strip_private(rt_json(r3.snapshot()))["agents"][1]["body"] == _strip_private(rt_json(old.snapshot()))["agents"][1]["body"]


def test_22_snapshot_checksum_policy():
    tr = rich()
    snap = rt_json(tr.snapshot())
    r2 = TwoAgentRuntime.restore(snap)
    # existing policy: checksum recomputed from the rebuilt index; for a consistent snapshot it matches
    assert r2.world.spatial_index_checksum == snap["world"]["spatial_index_checksum"] == checksum_of(r2.world.spatial_contents)
    assert r2.world.spatial_index_generation == snap["world"]["spatial_index_generation"]


def test_23_observer_session_restore_immediate_parity():
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS,
        preset_canonical,
    )
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession

    s = ObserverSession()
    s.apply_experiment(preset_canonical(PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS, seed=17))
    s.step(n=2)
    snap = s.snapshot()
    s2 = ObserverSession()
    frame = s2.restore(rt_json(snap))
    assert s2.runtime.tick == s.runtime.tick == snap["tick"]
    assert refs(s2.runtime.world) == refs(s.runtime.world)
    assert s2.runtime.spatial_index_consistency()["spatial_index_consistent_with_authoritative_state"]
    fw = frame["world"]
    listed = sorted((r["entity_kind"], r["entity_id"]) for c in fw["spatial_cell_contents"] for r in c["refs"])
    assert ("BODY", "body-0") in listed and ("BODY", "body-1") in listed
    assert {oid for k, oid in listed if k == "RESOURCE_OBJECT"} == {o.object_id for o in s.runtime.world.resource_objects}
    assert fw["spatial_index_checksum"] == s.runtime.world.spatial_index_checksum


def test_24_restore_adds_no_scientific_receipts(pair):
    tr, r2, snap = pair
    again = rt_json(r2.snapshot())
    # Only differences allowed: private derived cognition caches ("_"-prefixed) and the pre-existing
    # Column-Transfer restore-verification entry in surface_columns.history (unchanged policy).
    a, b = _strip_private(snap), _strip_private(again)
    for d in (a["world"], a["agents"][0]["world"], b["world"], b["agents"][0]["world"]):
        hist = (d.get("surface_columns") or {}).get("history")
        if hist is not None:
            d["surface_columns"]["history"] = [e for e in hist if e.get("event") != "SURFACE_COLUMN_TRANSFER_RESTORE_VERIFIED"]
    assert a == b
    st_a, st_b = fok.state_of(tr.world), fok.state_of(r2.world)
    assert fok.serialize_state(st_a) == fok.serialize_state(st_b)
    # last receipts of tick T are carried state, identical to the continuous runtime (none created)
    assert [rt_json(getattr(s, "last_manipulator_receipt", None)) for s in r2.slots] == \
        [rt_json(getattr(s, "last_manipulator_receipt", None)) for s in tr.slots]
    assert r2.world.spatial_index_history[-1]["reason"] == "restore"      # one derived rebuild record
    assert sum(1 for e in r2.world.spatial_index_history if e["event"] == "SPATIAL_CONTENTS_INDEX_REBUILT") == 1


# ---------------------------------------------------------------- diagnostic (25)


def test_25_consistency_diagnostic_is_read_only_and_detects_defects(pair):
    _, r2, _ = pair
    w = r2.world
    idx = w.spatial_contents
    hist_len, gen, epoch = len(w.spatial_index_history or []), idx.generation, idx.pose_epoch
    ok = r2.spatial_index_consistency()
    assert ok["spatial_index_consistent_with_authoritative_state"] and ok["checksum"] == ok["expected_checksum"]
    # corrupt a *copy* of the world view: drop body-1 (the historical defect), add a stale ref, duplicate one
    import copy
    wc = copy.deepcopy(w)
    from mechanistic_mind.physical_system.spatial_contents import SpatialEntityRef
    ix = wc.spatial_contents
    ref1 = ix.by_entity.pop(("BODY", "body-1"))
    ix.by_cell[(ref1.cell_x, ref1.cell_y)] = [r for r in ix.by_cell[(ref1.cell_x, ref1.cell_y)] if r.entity_id != "body-1"]
    ix.by_cell.setdefault((1, 1), []).append(SpatialEntityRef("RESOURCE_OBJECT", "ghost", 1, 1, 0, 0))
    dup = ix.by_entity[("RESOURCE_OBJECT", "resource-000003")]
    ix.by_cell.setdefault((2, 2), []).append(dup)
    rep = spatial_index_consistency(wc, body_refs_for_runtime(r2))
    assert not rep["spatial_index_consistent_with_authoritative_state"]
    assert ["BODY", "body-1"] in rep["missing_refs"]
    assert ["RESOURCE_OBJECT", "ghost"] in rep["stale_refs"]
    assert ["RESOURCE_OBJECT", "resource-000003"] in rep["duplicate_refs"]
    # read-only: nothing written to the real world
    assert (len(w.spatial_index_history or []), idx.generation, idx.pose_epoch) == (hist_len, gen, epoch)
    assert rep["researcher_only"] is True and rep["agent_accessible"] is False
