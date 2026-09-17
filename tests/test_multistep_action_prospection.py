"""Multi-step action prospection: present A → C1 → future B → P. Default OFF."""
from __future__ import annotations

from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.research import multistep_action_prospection as mapr
from mechanistic_mind.research import prospective_composition as pr

WAIT, MOVE_E, MOVE_N, MOVE_W = "WAIT", "MOVE:E", "MOVE:N", "MOVE:W"
X, C1, C2 = {"x": 0.50}, {"x": 0.70}, {"x": 0.30}
P, Q = {"y": 0.90}, {"y": 0.10}
ACTIONS = [WAIT, MOVE_N, "MOVE:S", MOVE_E, MOVE_W]


def _ps():
    return pr.empty_store()


def learn(store, ant, act, cons, *, n=4, tick0=1):
    for i in range(n):
        pr.learn_transition(store, tick=tick0 + i, antecedent=dict(ant), action=act, consequent=dict(cons))
    return store


def fam(frag, tol=0.12):
    frag = frag or {}
    if "y" in frag:
        y = float(frag.get("y") or 0.0)
        if abs(y - 0.90) <= tol:
            return "P"
        if abs(y - 0.10) <= tol:
            return "Q"
    if "x" in frag:
        x = float(frag.get("x") or -1.0)
        if abs(x - 0.70) <= tol:
            return "C1"
        if abs(x - 0.30) <= tol:
            return "C2"
    return "OTHER"


def chain(branches, first, future):
    for c in branches:
        if c.get("first_action") == first and list(c.get("future_actions") or [])[:1] == [future]:
            return c
    return None


def collect(store, present=None, continuations=None, *, enabled=True, max_depth=3):
    present = present or X
    if continuations is None:
        continuations = (pr.compose_trajectories(
            store, start=present, max_depth=max_depth, branch_actions=ACTIONS
        ).get("continuations") or [])
    meta = mapr.empty_meta()
    meta["enabled"] = bool(enabled)
    return mapr.collect(
        store=store, present=present, actions=ACTIONS,
        continuations=continuations, meta=meta, max_depth=max_depth,
    ), meta


def test_default_off():
    assert CognitionConfig().multistep_action_prospection is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.multistep_action_prospection is False
    st = rt.cognition.get("multistep_action_prospection") or {}
    assert st.get("enabled") is False
    meta = mapr.empty_meta()
    assert meta["enabled"] is False
    assert mapr.collect(store=_ps(), present=X, actions=ACTIONS, meta=meta) == []


def test_primary_composition_separately_learned():
    s = _ps()
    learn(s, X, MOVE_E, C1, tick0=1)
    learn(s, C1, MOVE_N, P, tick0=100)
    branches, meta = collect(s)
    c = chain(branches, MOVE_E, MOVE_N)
    assert c is not None
    assert fam((c.get("states") or [None])[-1]) == "P"
    assert fam((c.get("states") or [None, None])[1]) == "C1"
    assert c.get("first_action") == MOVE_E
    assert not c.get("executes_future_action_now")
    assert meta.get("wrote_experience") is False
    assert meta.get("support_incremented") is False
    # full sequence never in exposure_log as a single episode
    ticks_e = set((s["transitions"][pr.transition_key(pr._q(X), MOVE_E)].get("evidence_ticks") or []))
    ticks_n = set((s["transitions"][pr.transition_key(pr._q(C1), MOVE_N)].get("evidence_ticks") or []))
    assert not (ticks_e & ticks_n)
    assert c.get("novel_composition") is True


def test_second_edge_ablation_removes_future_branch():
    s = _ps()
    learn(s, X, MOVE_E, C1, tick0=1)
    branches, _ = collect(s)
    assert chain(branches, MOVE_E, MOVE_N) is None
    assert any(c.get("first_action") == MOVE_E and not (c.get("future_actions") or []) for c in branches) or any(
        c.get("actions") == [MOVE_E] for c in branches
    )


def test_shuffled_incompatible_context_does_not_compose():
    s = _ps()
    learn(s, X, MOVE_E, C1, tick0=1)
    learn(s, C2, MOVE_N, P, tick0=100)
    branches, _ = collect(s)
    assert chain(branches, MOVE_E, MOVE_N) is None


def test_two_present_actions_same_future_action_different_consequence():
    s = _ps()
    learn(s, X, WAIT, C1, tick0=1)
    learn(s, X, MOVE_E, C2, tick0=20)
    learn(s, C1, MOVE_N, P, tick0=100)
    learn(s, C2, MOVE_N, Q, tick0=200)
    branches, _ = collect(s)
    w = chain(branches, WAIT, MOVE_N)
    e = chain(branches, MOVE_E, MOVE_N)
    assert w is not None and e is not None
    assert fam((w.get("states") or [None])[-1]) == "P"
    assert fam((e.get("states") or [None])[-1]) == "Q"


def test_one_present_action_multiple_future_actions():
    s = _ps()
    learn(s, X, MOVE_E, C1, tick0=1)
    learn(s, C1, MOVE_N, P, tick0=100)
    learn(s, C1, MOVE_W, Q, tick0=200)
    branches, _ = collect(s)
    assert chain(branches, MOVE_E, MOVE_N) is not None
    assert chain(branches, MOVE_E, MOVE_W) is not None
    assert fam((chain(branches, MOVE_E, MOVE_N).get("states") or [None])[-1]) == "P"
    assert fam((chain(branches, MOVE_E, MOVE_W).get("states") or [None])[-1]) == "Q"


def test_support_not_multiplied():
    s = _ps()
    learn(s, X, MOVE_E, C1, n=10, tick0=1)
    learn(s, C1, MOVE_N, P, n=4, tick0=100)
    branches, _ = collect(s)
    c = chain(branches, MOVE_E, MOVE_N)
    anc = (c or {}).get("support_ancestry") or {}
    assert anc.get("combined") is None
    assert anc.get("not_multiplied") is True
    supports = [int(e.get("support") or 0) for e in (anc.get("edges") or [])]
    assert supports[0] >= 3 and supports[1] >= 3
    assert supports[0] * supports[1] != supports[0] or supports[1] == 1


def test_future_action_not_selected_now():
    s = _ps()
    learn(s, X, WAIT, C1, tick0=1)
    learn(s, C1, MOVE_N, P, tick0=100)
    cfg = CognitionConfig(
        multistep_action_prospection=True,
        prospective_composition=True,
        cognition_enabled=True,
        predicted_context_prospection=False,
        future_sensitive_action=False,
        predictive_conflict=False,
    )
    state = empty_cognitive_state(cfg)
    state["prospection"] = s
    tick = run_cognition_before_action(state, observation=X, tick=9, rng_value=0.0)
    assert tick.selected_action != MOVE_N
    sel = state.get("last_selection") or {}
    diag = sel.get("multistep_action_prospection") or {}
    assert diag.get("executes_future_action_now") is False
    assert diag.get("premature_future_selected") is False


def test_map_off_does_not_add_map_provenance():
    s = _ps()
    learn(s, X, MOVE_E, C1, tick0=1)
    learn(s, C1, MOVE_N, P, tick0=100)
    # 4.23 may still compose; MAP tags must be absent when disabled
    branches, meta = collect(s, enabled=False)
    assert branches == []
    assert int(meta.get("skipped_disabled") or 0) >= 1
    raw = pr.compose_trajectories(s, start=X, max_depth=2, branch_actions=ACTIONS)
    assert any((c.get("actions") or [])[:2] == [MOVE_E, MOVE_N] for c in (raw.get("continuations") or []))


def test_flags_remain_off():
    cfg = CognitionConfig()
    assert cfg.multistep_action_prospection is False
    assert cfg.predicted_context_prospection is False
    assert cfg.temporal_predictive_structure is False
    assert cfg.future_sensitive_action is False
    assert cfg.predictive_conflict is False
    rt = PhysicalSystemRuntime(seed=3)
    rt.set_mechanism("multistep_action_prospection", True)
    assert rt.config.cognition.multistep_action_prospection is True
    rt.set_mechanism("multistep_action_prospection", False)
    assert rt.config.cognition.multistep_action_prospection is False
