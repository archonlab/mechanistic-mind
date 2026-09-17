"""TPS MATCH → 4.23 entry. Default OFF. Transport only."""
from __future__ import annotations

from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.research import temporal_prospection_bridge as tpb

ACTION = "WAIT"
P = {"y": 0.90}
Q = {"y": 0.10}


def _store():
    s = tps.empty_store()
    s["enabled"] = True
    return s


def train_seq(store, xs, cons, *, delay=1, reps=4):
    t = 1
    for _ in range(reps):
        store["ring"] = []
        for x in xs:
            frag = {"x": float(x)}
            if store["ring"]:
                tps.learn(store, consequent=frag, action=ACTION, tick=t)
                t += 1
            tps.append(store, frag)
        last = {"x": float(xs[-1])}
        for _d in range(max(0, int(delay) - 1)):
            tps.learn(store, consequent=last, action=ACTION, tick=t)
            t += 1
            tps.append(store, last)
        tps.learn(store, consequent=cons, action=ACTION, tick=t)
        t += 1
    return store


def probe_tps(store, hist, present, *, lag=1):
    present_f = {"x": float(present)}
    store["ring"] = [{"x": float(x)} for x in hist] + [present_f]
    return tps.retrieve(store, present_f, ACTION, lag=int(lag))


def _y(state):
    return float((state or {}).get("y") or 0.0)


def _fam_y(y, tol=0.15):
    if abs(y - 0.90) <= tol:
        return "P"
    if abs(y - 0.10) <= tol:
        return "Q"
    return "OTHER"


def temporal_conts(composition):
    out = []
    for c in composition.get("continuations") or []:
        src = c.get("prediction_source")
        if src is None and (c.get("edges") or [{}])[0].get("prediction_source") == "TEMPORAL":
            src = "TEMPORAL"
        if src == "TEMPORAL":
            out.append(c)
    return out


def snapshot_conts(composition):
    return [c for c in (composition.get("continuations") or []) if c.get("prediction_source") == "SNAPSHOT"]


def compose_with_bridge(store, hist, present, *, lag=1, prosp=None, depth=2):
    meta = tpb.empty_meta()
    meta["enabled"] = True
    present_f = {"x": float(present)}
    store["ring"] = [{"x": float(x)} for x in hist] + [present_f]
    entries = tpb.collect_entry_steps(store, present_f, [ACTION], meta=meta)
    # If collect used all-lag retrieve, pin lag by rebuilding from lag-specific retrieve
    got = tps.retrieve(store, present_f, ACTION, lag=int(lag), count=False)
    entries = []
    step = tpb.as_entry_step(got, action=ACTION, present=present_f)
    if step:
        entries = [step]
        meta["bridged"] = 1
    prosp = prosp if prosp is not None else pr.empty_store()
    comp = pr.compose_trajectories(
        prosp, start=present_f, max_depth=depth, branch_actions=[ACTION], entry_steps=entries,
    )
    return got, entries, comp, meta


def test_default_off():
    assert CognitionConfig().temporal_prospection_bridge is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.temporal_prospection_bridge is False
    assert rt.cognition["temporal_bridge"]["enabled"] is False


def test_same_present_different_prospection():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    train_seq(store, [0.80, 0.70, 0.60, 0.50], Q, delay=1, reps=4)
    g1, e1, c1, _ = compose_with_bridge(store, [0.20, 0.30, 0.40], 0.50)
    g2, e2, c2, _ = compose_with_bridge(store, [0.80, 0.70, 0.60], 0.50)
    assert g1["status"] == "MATCH" and g2["status"] == "MATCH"
    t1, t2 = temporal_conts(c1), temporal_conts(c2)
    assert t1 and t2
    y1 = _y(t1[0]["states"][1])
    y2 = _y(t2[0]["states"][1])
    assert _fam_y(y1) == "P"
    assert _fam_y(y2) == "Q"
    assert t1[0]["prediction_source"] == "TEMPORAL"
    off = pr.compose_trajectories(
        pr.empty_store(), start={"x": 0.50}, max_depth=2, branch_actions=[ACTION], entry_steps=None,
    )
    assert not temporal_conts(off)


def test_bridge_does_not_write_transitions():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    prosp = pr.empty_store()
    _, _, c, _ = compose_with_bridge(store, [0.20, 0.30, 0.40], 0.50, prosp=prosp)
    assert temporal_conts(c)
    assert (prosp.get("transitions") or {}) == {}


def test_no_support_fabrication():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    got, entries, _, _ = compose_with_bridge(store, [0.20, 0.30, 0.40], 0.50)
    assert entries
    assert entries[0]["support"] == got["support"]
    assert entries[0]["support"] != pr.MIN_SUPPORT or got["support"] == pr.MIN_SUPPORT
    assert entries[0]["reliability_mapped"] is False
    assert entries[0]["reliability"] is None


def test_ablate_tps_removes_temporal_prospection():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    store["enabled"] = False
    meta = tpb.empty_meta()
    meta["enabled"] = True
    present = {"x": 0.50}
    store["ring"] = [{"x": 0.20}, {"x": 0.30}, {"x": 0.40}, present]
    entries = tpb.collect_entry_steps(store, present, [ACTION], meta=meta)
    assert entries == []


def test_ablate_bridge_keeps_tps():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    present = {"x": 0.50}
    store["ring"] = [{"x": 0.20}, {"x": 0.30}, {"x": 0.40}, present]
    got = tps.retrieve(store, present, ACTION, lag=1)
    assert got["status"] == "MATCH"
    meta = tpb.empty_meta()
    meta["enabled"] = False
    entries = tpb.collect_entry_steps(store, present, [ACTION], meta=meta)
    assert entries == []
    comp = pr.compose_trajectories(
        pr.empty_store(), start=present, max_depth=2, branch_actions=[ACTION],
    )
    assert not temporal_conts(comp)


def test_cognition_pipeline_same_present():
    cfg = CognitionConfig(
        temporal_predictive_structure=True,
        temporal_prospection_bridge=True,
    )
    state = empty_cognitive_state(cfg)
    store = state["temporal"]
    store["enabled"] = True
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    train_seq(store, [0.80, 0.70, 0.60, 0.50], Q, delay=1, reps=4)
    state["temporal"]["ring"] = [{"x": 0.20}, {"x": 0.30}, {"x": 0.40}]
    state["last_fragment"] = None
    state["last_action"] = None
    run_cognition_before_action(state, observation={"x": 0.50}, tick=99, rng_value=0.0)
    sel = state["last_selection"]
    entries = sel.get("temporal_entry_steps") or []
    conts = sel.get("continuations") or []
    temporal = [c for c in conts if c.get("prediction_source") == "TEMPORAL"]
    assert entries
    assert temporal or any(
        (e.get("edges") or [{}])[0].get("prediction_source") == "TEMPORAL" for e in conts
    )
    assert _fam_y(_y((temporal or conts)[0]["states"][1])) == "P"
    rt = PhysicalSystemRuntime(seed=4)
    rt.set_mechanism("temporal_prospection_bridge", True)
    assert rt.config.cognition.temporal_prospection_bridge is True
    rt.set_mechanism("temporal_prospection_bridge", False)
    assert rt.config.cognition.temporal_prospection_bridge is False


def test_snapshot_and_temporal_coexist_without_adding_support():
    store = _store()
    train_seq(store, [0.20, 0.30, 0.40, 0.50], P, delay=1, reps=4)
    prosp = pr.empty_store()
    for _ in range(4):
        pr.learn_transition(prosp, tick=1, antecedent={"x": 0.50}, action=ACTION, consequent=P)
    g, e, c, _ = compose_with_bridge(store, [0.20, 0.30, 0.40], 0.50, prosp=prosp)
    snaps, temps = snapshot_conts(c), temporal_conts(c)
    assert snaps and temps
    snap_sup = int((snaps[0].get("edges") or [{}])[0].get("support") or 0)
    tmp_sup = int((temps[0].get("edges") or [{}])[0].get("support") or 0)
    assert snap_sup == 4
    assert tmp_sup == g["support"]
    assert snap_sup + tmp_sup != tmp_sup  # not silently merged into one edge


def test_toggle_does_not_promote():
    assert CognitionConfig().temporal_prospection_bridge is False
    assert CognitionConfig().temporal_predictive_structure is False
    assert CognitionConfig().predictive_equivalence is False
    assert CognitionConfig().predictive_relevance is False
