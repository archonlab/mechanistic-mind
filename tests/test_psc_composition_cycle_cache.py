"""PSC composition — semantic key distinctness (no production cycle cache).

Documents measured equivalence properties after A/B showed cycle-cache
memoization of predict_one_step was net-negative end-to-end.
"""
from __future__ import annotations

from mechanistic_mind.research import prospective_composition as pr


def _filled_store():
    store = pr.empty_store()
    for tick, ant, act, cons in [
        (1, {"exo_0": 0.1, "a": 0.2}, "WAIT", {"exo_0": 0.2, "a": 0.3}),
        (2, {"exo_0": 0.1, "a": 0.2}, "WAIT", {"exo_0": 0.25, "a": 0.28}),
        (3, {"exo_0": 0.1, "a": 0.2}, "WAIT", {"exo_0": 0.22, "a": 0.31}),
        (4, {"exo_0": 0.1, "a": 0.2}, "MOVE:N", {"exo_0": 0.4, "a": 0.1}),
        (5, {"exo_0": 0.1, "a": 0.2}, "MOVE:N", {"exo_0": 0.41, "a": 0.12}),
        (6, {"exo_0": 0.1, "a": 0.2}, "MOVE:N", {"exo_0": 0.39, "a": 0.11}),
    ]:
        pr.learn_transition(store, tick=tick, antecedent=ant, action=act, consequent=cons)
    return store


def test_action_is_part_of_semantic_key():
    store = _filled_store()
    ant = {"exo_0": 0.1, "a": 0.2}
    w = pr.predict_one_step(store, ant, "WAIT")
    m = pr.predict_one_step(store, ant, "MOVE:N")
    assert w["action"] != m["action"]
    assert w.get("key") != m.get("key")


def test_adversarial_near_move_actions_distinct():
    store = _filled_store()
    ant = {"exo_0": 0.1, "a": 0.2}
    a = pr.predict_one_step(store, ant, "MOVE:N")
    b = pr.predict_one_step(store, ant, "MOVE:S")
    assert a["action"] == "MOVE:N"
    assert b["action"] == "MOVE:S"
    assert a != b


def test_compose_keeps_full_branch_order():
    store = _filled_store()
    acts = ["WAIT", "MOVE:N", "MOVE:S", "NECK_LEFT", "OSC_EMIT"]
    out = pr.compose_trajectories(
        store, start={"exo_0": 0.1, "a": 0.2}, max_depth=2, branch_actions=acts
    )
    assert out["expansion_count"] >= 1
    out2 = pr.compose_trajectories(
        store, start={"exo_0": 0.1, "a": 0.2}, max_depth=2, branch_actions=acts
    )
    assert out == out2
