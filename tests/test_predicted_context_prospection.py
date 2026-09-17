"""Predicted-context prospection: read-only Cfuture → action lookup. Default OFF."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.research import predicted_context_prospection as pcp
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_predictive_structure as tps

WAIT = "WAIT"
MOVE = "MOVE:N"
C0 = 0.50
C1 = 0.70
C2 = 0.30
P = {"y": 0.90}
Q = {"y": 0.10}
R = {"y": 0.70}
S = {"y": 0.30}
H_UP = [0.30, 0.38, 0.46, 0.50]
H_DOWN = [0.70, 0.62, 0.54, 0.50]
H_UP_HIST = H_UP[:-1]
H_DOWN_HIST = H_DOWN[:-1]


def _tps():
    s = tps.empty_store()
    s["enabled"] = True
    return s


def _pr():
    return pr.empty_store()


def train_tps(store, xs, cons, *, delay=1, reps=4, action=WAIT):
    t = 1
    for _ in range(reps):
        store["ring"] = []
        for x in xs:
            frag = {"x": float(x)}
            if store["ring"]:
                tps.learn(store, consequent=frag, action=action, tick=t)
                t += 1
            tps.append(store, frag)
        last = {"x": float(xs[-1])}
        for _d in range(max(0, int(delay) - 1)):
            tps.learn(store, consequent=last, action=action, tick=t)
            t += 1
            tps.append(store, last)
        tps.learn(store, consequent=cons, action=action, tick=t)
        t += 1
    return store


def probe_ring(store, hist, present):
    present_f = {"x": float(present)}
    store["ring"] = [{"x": float(x)} for x in hist] + [present_f]
    return present_f


def learn_ac(store, context, action, cons, *, n=4, tick0=1):
    for i in range(n):
        pr.learn_transition(
            store,
            tick=tick0 + i,
            antecedent={"x": float(context)},
            action=action,
            consequent=dict(cons),
        )
    return store


def fam(frag, tol=0.15):
    y = float((frag or {}).get("y") or 0.0)
    if abs(y - 0.90) <= tol:
        return "P"
    if abs(y - 0.10) <= tol:
        return "Q"
    if abs(y - 0.70) <= tol:
        return "R"
    if abs(y - 0.30) <= tol:
        return "S"
    return "OTHER"


def supports(store):
    return {k: int(v.get("support") or 0) for k, v in (store.get("transitions") or {}).items()}


def collect_at(tps_store, prosp, hist, present, *, actions=None, max_depth=2, lag=1):
    present_f = probe_ring(tps_store, hist, present)
    meta = pcp.empty_meta()
    meta["enabled"] = True
    return pcp.collect(
        tps_store=tps_store,
        prospection=prosp,
        present=present_f,
        actions=list(actions or [WAIT, MOVE]),
        meta=meta,
        max_depth=max_depth,
        lag=lag,
    ), meta, present_f


def test_default_off():
    assert CognitionConfig().predicted_context_prospection is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.predicted_context_prospection is False
    st = rt.cognition.get("predicted_context_prospection") or {}
    assert st.get("enabled") is False
    meta = pcp.empty_meta()
    assert meta["enabled"] is False
    branches = pcp.collect(
        tps_store=_tps(),
        prospection=_pr(),
        present={"x": C0},
        actions=[WAIT, MOVE],
        meta=meta,
    )
    assert branches == []


def test_primary_synthetic_gate():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1})
    learn_ac(ps, C1, WAIT, P)
    learn_ac(ps, C1, MOVE, Q)
    before = supports(ps)
    branches, meta, _ = collect_at(ts, ps, H_UP_HIST, C0)
    assert meta["wrote_experience"] is False
    assert meta["support_incremented"] is False
    assert supports(ps) == before
    futs = {(c.get("future_actions") or [None])[0]: fam((c.get("states") or [None])[-1]) for c in branches}
    assert futs.get(WAIT) == "P"
    assert futs.get(MOVE) == "Q"
    assert all(c.get("first_action") == WAIT for c in branches)
    assert all(c.get("context_kind") == "PREDICTED" for c in branches)
    assert all(c.get("not_realized_experience") for c in branches)
    assert all(not c.get("executes_future_action_now") for c in branches)


def test_bridge_off_isolates_new_path():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1})
    learn_ac(ps, C1, WAIT, P)
    learn_ac(ps, C1, MOVE, Q)
    present_f = probe_ring(ts, H_UP_HIST, C0)
    got = tps.retrieve(ts, present_f, WAIT, lag=1, count=False)
    assert got.get("status") == "MATCH"
    meta = pcp.empty_meta()
    meta["enabled"] = False
    branches = pcp.collect(
        tps_store=ts, prospection=ps, present=present_f, actions=[WAIT, MOVE], meta=meta
    )
    assert branches == []
    assert not any(c.get("prediction_source") == "PREDICTED_CONTEXT" for c in branches)


def test_tps_off_does_not_manufacture():
    ts, ps = _tps(), _pr()
    ts["enabled"] = False
    learn_ac(ps, C1, WAIT, P)
    learn_ac(ps, C1, MOVE, Q)
    branches, meta, _ = collect_at(ts, ps, H_UP_HIST, C0)
    assert branches == []
    assert int(meta.get("skipped_no_tps") or 0) >= 1


def test_same_present_different_history():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1})
    train_tps(ts, H_DOWN, {"x": C2})
    learn_ac(ps, C1, WAIT, P)
    learn_ac(ps, C1, MOVE, Q)
    learn_ac(ps, C2, WAIT, R)
    learn_ac(ps, C2, MOVE, S)
    up, _, _ = collect_at(ts, ps, H_UP_HIST, C0)
    down, _, _ = collect_at(ts, ps, H_DOWN_HIST, C0)
    up_map = {(c.get("future_actions") or [None])[0]: fam((c.get("states") or [None])[-1]) for c in up}
    down_map = {(c.get("future_actions") or [None])[0]: fam((c.get("states") or [None])[-1]) for c in down}
    assert up_map.get(WAIT) == "P" and up_map.get(MOVE) == "Q"
    assert down_map.get(WAIT) == "R" and down_map.get(MOVE) == "S"


def test_same_future_different_history_converges():
    ts, ps = _tps(), _pr()
    h1 = [0.28, 0.36, 0.44, 0.50]
    h2 = [0.32, 0.40, 0.46, 0.50]
    train_tps(ts, h1, {"x": C1})
    train_tps(ts, h2, {"x": C1})
    learn_ac(ps, C1, WAIT, P)
    learn_ac(ps, C1, MOVE, Q)
    a, _, _ = collect_at(ts, ps, h1[:-1], C0)
    b, _, _ = collect_at(ts, ps, h2[:-1], C0)
    a_map = {(c.get("future_actions") or [None])[0]: fam((c.get("states") or [None])[-1]) for c in a}
    b_map = {(c.get("future_actions") or [None])[0]: fam((c.get("states") or [None])[-1]) for c in b}
    assert a_map == b_map
    assert a_map.get(WAIT) == "P"


def test_predicted_vs_realized_provenance():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1})
    learn_ac(ps, C1, WAIT, P)
    branches, _, _ = collect_at(ts, ps, H_UP_HIST, C0)
    assert branches
    assert all(c.get("provenance", {}).get("context_kind") == "PREDICTED" for c in branches)
    assert all(c.get("provenance", {}).get("realized_context") is False for c in branches)
    realized = pr.predict_one_step(ps, {"x": C1}, WAIT)
    assert realized.get("status") == "MATCH"
    assert realized.get("prediction_source") in (None, "SNAPSHOT") or "PREDICTED_CONTEXT" not in str(
        realized.get("prediction_source")
    )
    assert fam(realized.get("predicted")) == "P"


def test_no_self_confirming_loop():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1})
    learn_ac(ps, C1, WAIT, P, n=4)
    learn_ac(ps, C1, MOVE, Q, n=4)
    inner = ts.get("inner") or {}
    class_n = len(inner.get("classes") or {})
    before_ps = deepcopy(supports(ps))
    before_tps_matches = int(ts.get("matches") or 0)
    for _ in range(5):
        collect_at(ts, ps, H_UP_HIST, C0)
    assert supports(ps) == before_ps
    assert len((ts.get("inner") or {}).get("classes") or {}) == class_n
    assert int(ts.get("matches") or 0) == before_tps_matches


def test_known_action_only():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1})
    learn_ac(ps, C1, WAIT, P)
    branches, meta, _ = collect_at(ts, ps, H_UP_HIST, C0, actions=[WAIT, MOVE])
    futs = [a for c in branches for a in (c.get("future_actions") or [])]
    assert WAIT in futs
    assert MOVE not in futs
    un = meta.get("unmodeled_actions") or []
    assert any(u.get("action") == MOVE and u.get("status") == "UNMODELED" for u in un)


def test_context_sensitive_same_action():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1})
    train_tps(ts, H_DOWN, {"x": C2})
    learn_ac(ps, C2, WAIT, P)
    learn_ac(ps, C1, WAIT, Q)
    up, _, _ = collect_at(ts, ps, H_UP_HIST, C0, actions=[WAIT])
    down, _, _ = collect_at(ts, ps, H_DOWN_HIST, C0, actions=[WAIT])
    assert fam((up[0].get("states") or [None])[-1]) == "Q"
    assert fam((down[0].get("states") or [None])[-1]) == "P"


def test_support_not_multiplied():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1}, reps=5)
    learn_ac(ps, C1, WAIT, P, n=10)
    branches, _, _ = collect_at(ts, ps, H_UP_HIST, C0, actions=[WAIT])
    assert branches
    anc = branches[0].get("support_ancestry") or {}
    assert anc.get("combined") is None
    assert anc.get("not_multiplied") is True
    assert anc.get("not_added") is True
    tps_s = int(anc.get("predicted_context_support") or 0)
    act_s = int(anc.get("action_consequence_support") or 0)
    assert tps_s > 0 and act_s >= 3
    root_support = int((branches[0].get("edges") or [{}])[0].get("support") or 0)
    lookup_support = int((branches[0].get("edges") or [{}, {}])[1].get("support") or 0)
    assert root_support == tps_s
    assert lookup_support == act_s
    assert root_support != tps_s * act_s or tps_s == 1


def test_action_timing_future_move_is_not_present():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1})
    learn_ac(ps, C1, MOVE, Q)
    branches, _, _present = collect_at(ts, ps, H_UP_HIST, C0, actions=[WAIT, MOVE])
    move_b = [c for c in branches if MOVE in (c.get("future_actions") or [])]
    assert move_b
    assert all(c.get("first_action") == WAIT for c in move_b)
    assert all(not c.get("executes_future_action_now") for c in move_b)
    cfg = CognitionConfig(
        predicted_context_prospection=True,
        temporal_predictive_structure=True,
        prospective_composition=True,
        predictive_equivalence=False,
        predictive_relevance=False,
        temporal_prospection_bridge=False,
        future_sensitive_action=False,
        cognition_enabled=True,
    )
    state = empty_cognitive_state(cfg)
    state["temporal"] = ts
    state["prospection"] = ps
    ts["ring"] = [{"x": float(x)} for x in H_UP_HIST]
    tick = run_cognition_before_action(state, observation={"x": C0}, tick=9, rng_value=0.1)
    assert tick.selected_action != MOVE or tick.selection_source == "ENDOGENOUS_VARIATION"
    sel = state.get("last_selection") or {}
    pcp_last = sel.get("predicted_context_prospection") or {}
    assert pcp_last.get("executes_future_action_now") is False


def test_wrong_forecast_does_not_rewrite_history():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1})
    learn_ac(ps, C1, WAIT, P)
    branches, _, present = collect_at(ts, ps, H_UP_HIST, C0, actions=[WAIT])
    assert branches
    before = deepcopy(ps)
    pr.learn_transition(ps, tick=99, antecedent=present, action=WAIT, consequent={"x": C2})
    keys_c1 = [
        k for k, v in (before.get("transitions") or {}).items()
        if abs(float((v.get("antecedent") or {}).get("x") or 0) - pr._q({"x": C1})["x"]) < 1e-9
    ]
    for k in keys_c1:
        assert int((ps["transitions"][k].get("support"))) == int((before["transitions"][k].get("support")))
    present_keys = [
        k for k, v in (ps.get("transitions") or {}).items()
        if abs(float((v.get("antecedent") or {}).get("x") or 0) - pr._q(present)["x"]) < 1e-9
    ]
    assert present_keys
    cons = pr.mean_cons(ps["transitions"][present_keys[0]])
    assert abs(float(cons.get("x") or 0.0) - pr._q({"x": C2})["x"]) <= 0.12


def test_cognition_tick_pcp_on_retrieves_without_writing():
    ts, ps = _tps(), _pr()
    train_tps(ts, H_UP, {"x": C1})
    learn_ac(ps, C1, WAIT, P)
    learn_ac(ps, C1, MOVE, Q)
    before = supports(ps)
    cfg = CognitionConfig(
        predicted_context_prospection=True,
        temporal_predictive_structure=True,
        prospective_composition=True,
        cognition_enabled=True,
        temporal_prospection_bridge=False,
        predictive_conflict=False,
        future_sensitive_action=False,
    )
    state = empty_cognitive_state(cfg)
    state["temporal"] = ts
    state["prospection"] = ps
    # cognition appends the present; ring must be history only
    ts["ring"] = [{"x": float(x)} for x in H_UP_HIST]
    run_cognition_before_action(state, observation={"x": C0}, tick=3, rng_value=0.0)
    assert supports(ps) == before
    sel = state.get("last_selection") or {}
    branches = sel.get("predicted_context_branches") or []
    assert branches
    futs = {(c.get("future_actions") or [None])[0]: fam((c.get("states") or [None])[-1]) for c in branches}
    assert futs.get(WAIT) == "P"
    assert futs.get(MOVE) == "Q"


def test_flags_remain_off():
    cfg = CognitionConfig()
    assert cfg.predicted_context_prospection is False
    assert cfg.temporal_predictive_structure is False
    assert cfg.temporal_prospection_bridge is False
    assert cfg.predictive_conflict is False
    assert cfg.future_sensitive_action is False
    assert cfg.prediction_error_revision is False
    assert cfg.temporal_prediction_error is False
    assert cfg.predictive_equivalence is False
    assert cfg.predictive_relevance is False
    rt = PhysicalSystemRuntime(seed=3)
    rt.set_mechanism("predicted_context_prospection", True)
    assert rt.config.cognition.predicted_context_prospection is True
    rt.set_mechanism("predicted_context_prospection", False)
    assert rt.config.cognition.predicted_context_prospection is False
