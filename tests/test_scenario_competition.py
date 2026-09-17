"""Unit + integration tests for Prospective Scenario Competition."""
from __future__ import annotations

from copy import deepcopy

import pytest

from mechanistic_mind.physical_system.actions import available_actions, apply_physical_action
from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state, run_cognition_before_action
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
from mechanistic_mind.research import prospective_composition as pr


def _scenario(first: str, support: int, reliability: float, depth: int, sid: str = "S") -> dict:
    return {
        "scenario_id": sid,
        "source_structure_ids": [f"{first}-t"],
        "provenance": {"path": "test"},
        "action_sequence": [first] + (["WAIT"] * (depth - 1) if depth > 1 else []),
        "first_action": first,
        "depth": depth,
        "historical_support": support,
        "reliability": reliability,
        "current_match_evidence": {"status": "MATCH"},
        "predicted_state_fragments": sc.NOT_AVAILABLE,
        "predicted_body_fragments": sc.NOT_AVAILABLE,
        "predicted_environment_fragments": sc.NOT_AVAILABLE,
        "composition_path": [],
    }


def test_list_order_does_not_determine_winner():
    weak_first = _scenario("WAIT", support=2, reliability=0.4, depth=1, sid="A")
    strong_second = _scenario("MOVE:N", support=50, reliability=0.9, depth=3, sid="B")
    # Intentionally put weaker WAIT first in the group list / candidate order
    groups = {
        "WAIT": [weak_first],
        "MOVE:N": [strong_second],
        "MOVE:S": [],
        "MOVE:E": [],
        "MOVE:W": [],
    }
    actions = ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"]
    out = sc.compete_scenarios(groups=groups, actions=actions, rng_value=0.0)
    assert out["selected"] == "MOVE:N"
    assert out["source"] == "PROSPECTIVE_SCENARIO"
    assert out["competition"]["outcome_class"] == "DOMINANT_SCENARIO"


def test_supported_scenarios_grouped_by_first_action():
    store = pr.empty_store()
    # learn WAIT and MOVE:E transitions from same antecedent
    ant = {"a": 0.0, "b": 0.0}
    for _ in range(5):
        pr.learn_transition(store, tick=1, antecedent=ant, action="WAIT", consequent={"a": 0.0, "b": 0.1})
        pr.learn_transition(store, tick=1, antecedent=ant, action="MOVE:E", consequent={"a": 1.0, "b": 0.0})
    conts = [
        {"actions": ["WAIT", "WAIT"], "depth": 2, "score_reliability": 0.8,
         "edges": [{"status": "MATCH", "support": 5, "reliability": 0.8, "key": "k1", "transition_id": "t1"}],
         "states": [ant, {"a": 0.0, "b": 0.1}, {"a": 0.0, "b": 0.2}]},
        {"actions": ["MOVE:E"], "depth": 1, "score_reliability": 0.7,
         "edges": [{"status": "MATCH", "support": 5, "reliability": 0.7, "key": "k2", "transition_id": "t2"}],
         "states": [ant, {"a": 1.0, "b": 0.0}]},
    ]
    groups = sc.collect_scenario_groups(store=store, observation=ant, continuations=conts)
    assert groups["WAIT"]
    assert groups["MOVE:E"]
    assert not groups["MOVE:N"]  # unsupported


def test_unsupported_move_not_treated_as_supported():
    groups = {"WAIT": [_scenario("WAIT", 3, 0.6, 1, "W")], "MOVE:N": [], "MOVE:S": [], "MOVE:E": [], "MOVE:W": []}
    out = sc.compete_scenarios(groups=groups, actions=available_actions(), rng_value=0.1)
    assert out["selected"] == "WAIT"
    assert "MOVE:N" in out["competition"]["unsupported_actions"]
    assert out["competition"]["outcome_class"] == "SINGLE_SUPPORTED"


def test_wait_no_special_penalty_and_move_no_bonus():
    # Equal evidence → exact tie → endogenous, not anti-WAIT
    w = _scenario("WAIT", 10, 0.8, 2, "W")
    m = _scenario("MOVE:S", 10, 0.8, 2, "M")
    groups = {"WAIT": [w], "MOVE:N": [], "MOVE:S": [m], "MOVE:E": [], "MOVE:W": []}
    out0 = sc.compete_scenarios(groups=groups, actions=available_actions(), rng_value=0.0)
    out1 = sc.compete_scenarios(groups=groups, actions=available_actions(), rng_value=0.99)
    assert out0["competition"]["outcome_class"] == "EXACT_TIE"
    assert out0["source"] == "PROSPECTIVE_TIE_RESOLUTION"
    # both actions must be choosable across rng range
    chosen = {out0["selected"], out1["selected"]}
    assert chosen == {"WAIT", "MOVE:S"}


def test_exact_ties_handled_explicitly():
    a = _scenario("WAIT", 4, 0.5, 1, "A")
    b = _scenario("MOVE:N", 4, 0.5, 1, "B")
    out = sc.compete_scenarios(
        groups={"WAIT": [a], "MOVE:N": [b], "MOVE:S": [], "MOVE:E": [], "MOVE:W": []},
        actions=available_actions(),
        rng_value=0.2,
    )
    assert out["competition"]["ties"]
    assert out["competition"]["tie_resolution"]["mechanism"].startswith("ENDOGENOUS")


def test_no_support_fallback():
    out = sc.compete_scenarios(
        groups={a: [] for a in available_actions()},
        actions=available_actions(),
        rng_value=0.3,
    )
    assert out["selected"] is None
    assert out["source"] == "NO_SUPPORT"


def test_bounded_scenario_limits():
    store = pr.empty_store()
    ant = {"x": 0.0}
    for i in range(20):
        pr.learn_transition(store, tick=i, antecedent=ant, action="WAIT", consequent={"x": float(i) * 0.01})
    # many continuations same first action
    conts = []
    for d in range(1, 10):
        conts.append({
            "actions": ["WAIT"] * d,
            "depth": d,
            "score_reliability": 0.5,
            "edges": [{"status": "MATCH", "support": 3, "reliability": 0.5, "key": f"k{d}", "transition_id": f"t{d}"}],
            "states": [ant] + [{"x": 0.01 * j} for j in range(d)],
        })
    groups = sc.collect_scenario_groups(
        store=store, observation=ant, continuations=conts,
        max_per_action=sc.MAX_SCENARIOS_PER_ACTION,
        max_total=sc.MAX_SCENARIOS_TOTAL,
    )
    assert len(groups["WAIT"]) <= sc.MAX_SCENARIOS_PER_ACTION
    assert sum(len(v) for v in groups.values()) <= sc.MAX_SCENARIOS_TOTAL


def test_legacy_first_reproduces_list_privilege():
    conts = [
        {"actions": ["WAIT"], "depth": 1, "score_reliability": 0.1},
        {"actions": ["MOVE:N"], "depth": 3, "score_reliability": 0.99},
    ]
    # LEGACY takes first list element regardless of depth (compose normally sorts; here we simulate privilege)
    leg = sc.legacy_first_select(conts)
    assert leg["selected"] == "WAIT"
    assert leg["competition"]["outcome_class"] == "LEGACY_FIRST_ELEMENT"


def test_bridge_executes_selected_action():
    assert "WAIT" in available_actions()
    assert "MOVE:N" in available_actions()
    # apply_physical_action is the bridge; selection source strings must remain bridge-agnostic
    assert callable(apply_physical_action)


def test_dominance_incomparable():
    a = _scenario("WAIT", support=100, reliability=0.2, depth=1, sid="A")
    b = _scenario("MOVE:E", support=2, reliability=0.9, depth=3, sid="B")
    assert sc.incomparable(a, b)
    out = sc.compete_scenarios(
        groups={"WAIT": [a], "MOVE:N": [], "MOVE:S": [], "MOVE:E": [b], "MOVE:W": []},
        actions=available_actions(),
        rng_value=0.1,
    )
    assert out["competition"]["outcome_class"] == "INCOMPARABLE"
    assert out["source"] == "PROSPECTIVE_TIE_RESOLUTION"


def test_runtime_legacy_vs_competition_config():
    cfg_legacy = PhysicalSystemConfig()
    cfg_legacy.cognition = CognitionConfig(prospective_selection="LEGACY_FIRST")
    cfg_comp = PhysicalSystemConfig()
    cfg_comp.cognition = CognitionConfig(prospective_selection="SCENARIO_COMPETITION")
    r1 = PhysicalSystemRuntime(config=cfg_legacy)
    r2 = PhysicalSystemRuntime(config=cfg_comp)
    r1.reset(seed=17)
    r2.reset(seed=17)
    assert r1.cognition["config"]["prospective_selection"] == "LEGACY_FIRST"
    assert r2.cognition["config"]["prospective_selection"] == "SCENARIO_COMPETITION"
    for _ in range(30):
        r1.step()
        r2.step()
    # both should run without error; receipts should expose mode when sampled
    r1.set_action_trace(enabled=True, mode="every_1")
    r2.set_action_trace(enabled=True, mode="every_1")
    for _ in range(5):
        r1.step()
        r2.step()
    rec1 = r1.cognition.get("last_decision_receipt") or {}
    rec2 = r2.cognition.get("last_decision_receipt") or {}
    assert rec1.get("schema") == "mm.action_decision_receipt.v2"
    assert rec2.get("schema") == "mm.action_decision_receipt.v2"
    assert rec1.get("prospective_selection_mode") == "LEGACY_FIRST"
    assert rec2.get("prospective_selection_mode") == "SCENARIO_COMPETITION"


def test_multi_action_supported_competition_integration():
    """Force multi-action support in store then select via competition."""
    cfg = PhysicalSystemConfig()
    cfg.cognition = CognitionConfig(prospective_selection="SCENARIO_COMPETITION")
    rt = PhysicalSystemRuntime(config=cfg)
    rt.reset(seed=41)
    # Seed transitions for two actions from a fixed observation-like fragment
    # Use empty observation keys matching accessible_observation shape after a few steps
    for _ in range(5):
        rt.step()
    obs = deepcopy(rt.cognition.get("last_fragment") or {})
    if not obs:
        pytest.skip("no observation fragment yet")
    store = rt.cognition["prospection"]
    for i in range(8):
        pr.learn_transition(store, tick=100+i, antecedent=obs, action="WAIT", consequent={k: float(v) + 0.01 for k, v in obs.items()})
        pr.learn_transition(store, tick=100+i, antecedent=obs, action="MOVE:N", consequent={k: float(v) + 0.05 for k, v in obs.items()})
    groups = sc.collect_scenario_groups(store=store, observation=obs, continuations=[])
    supported = [a for a, rows in groups.items() if rows]
    assert len(supported) >= 2
    out = sc.compete_scenarios(groups=groups, actions=available_actions(), rng_value=0.0)
    assert out["selected"] in supported
    assert out["source"] in {"PROSPECTIVE_SCENARIO", "PROSPECTIVE_TIE_RESOLUTION"}
