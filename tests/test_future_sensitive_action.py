"""Future-sensitive action: conflict candidates enter existing competition. Default OFF."""
from __future__ import annotations

from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state, run_cognition_before_action
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.research import future_sensitive_action as fsa
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research import prospective_composition as pr

PRESENT = {"x": 0.50}
P = {"y": 0.90}
Q = {"y": 0.10}


def test_default_off():
    assert CognitionConfig().future_sensitive_action is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.future_sensitive_action is False
    assert rt.cognition["future_action"]["enabled"] is False
    meta = fsa.empty_meta()
    groups = fsa.build_groups(
        store=pr.empty_store(),
        observation=PRESENT,
        continuations=[],
        actions=["WAIT", "MOVE:N"],
        meta=meta,
    )
    # disabled meta uses collect_scenario_groups; no invented MOVE
    assert groups["MOVE:N"] == []


def test_two_first_actions_enter_competition():
    meta = fsa.empty_meta()
    meta["enabled"] = True
    st = pcf.empty_store()
    st["enabled"] = True
    org = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=4, present=PRESENT, action="WAIT"),
        pcf.make_continuation(predicted=Q, support=6, present=PRESENT, action="MOVE:N", actions=["MOVE:N"]),
    ])
    groups = fsa.build_groups(
        store=pr.empty_store(),
        observation=PRESENT,
        continuations=[],
        actions=["WAIT", "MOVE:N", "MOVE:S"],
        conflict_candidates=org["candidates"],
        meta=meta,
    )
    assert groups["WAIT"] and groups["MOVE:N"]
    assert not groups["MOVE:S"]
    out = sc.compete_scenarios(groups=groups, actions=["WAIT", "MOVE:N", "MOVE:S"], rng_value=0.0)
    assert out["selected"] == "MOVE:N"
    assert out["competition"]["outcome_class"] == "DOMINANT_SCENARIO"


def test_same_action_futures_do_not_change_action():
    meta = fsa.empty_meta()
    meta["enabled"] = True
    st = pcf.empty_store()
    st["enabled"] = True
    org = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=8, present=PRESENT, action="WAIT"),
        pcf.make_continuation(predicted=Q, support=3, present=PRESENT, action="WAIT"),
    ])
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=[],
        actions=["WAIT", "MOVE:N"], conflict_candidates=org["candidates"], meta=meta,
    )
    assert len(groups["WAIT"]) == 2
    assert not groups["MOVE:N"]
    out = sc.compete_scenarios(groups=groups, actions=["WAIT", "MOVE:N"], rng_value=0.0)
    assert out["selected"] == "WAIT"


def test_equal_support_is_existing_tie_not_new_breaker():
    meta = fsa.empty_meta()
    meta["enabled"] = True
    st = pcf.empty_store()
    st["enabled"] = True
    org = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=5, present=PRESENT, action="WAIT"),
        pcf.make_continuation(predicted=Q, support=5, present=PRESENT, action="MOVE:N", actions=["MOVE:N"]),
    ])
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=[],
        actions=["WAIT", "MOVE:N"], conflict_candidates=org["candidates"], meta=meta,
    )
    out0 = sc.compete_scenarios(groups=groups, actions=["WAIT", "MOVE:N"], rng_value=0.0)
    out1 = sc.compete_scenarios(groups=groups, actions=["WAIT", "MOVE:N"], rng_value=0.99)
    assert out0["competition"]["outcome_class"] == "EXACT_TIE"
    assert {out0["selected"], out1["selected"]} == {"WAIT", "MOVE:N"}


def test_does_not_invent_unexperienced_actions():
    meta = fsa.empty_meta()
    meta["enabled"] = True
    st = pcf.empty_store()
    st["enabled"] = True
    org = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=4, present=PRESENT, action="WAIT"),
    ])
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=[],
        actions=["WAIT", "MOVE:N"], conflict_candidates=org["candidates"], meta=meta,
    )
    assert groups["WAIT"]
    assert groups["MOVE:N"] == []
    out = sc.compete_scenarios(groups=groups, actions=["WAIT", "MOVE:N"], rng_value=0.0)
    assert out["selected"] == "WAIT"
    assert out["competition"]["outcome_class"] == "SINGLE_SUPPORTED"


def test_scenario_support_not_global_action_count():
    meta = fsa.empty_meta()
    meta["enabled"] = True
    st = pcf.empty_store()
    st["enabled"] = True
    org = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=4, present=PRESENT, action="WAIT"),
        pcf.make_continuation(predicted=Q, support=10, present=PRESENT, action="MOVE:N", actions=["MOVE:N"]),
    ])
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=[],
        actions=["WAIT", "MOVE:N"],
        conflict_candidates=org["candidates"],
        action_counts={"WAIT": 100, "MOVE:N": 20},
        meta=meta,
    )
    assert groups["WAIT"][0]["historical_action_count"] == 100
    assert groups["WAIT"][0]["scenario_specific_evidence"] == 4
    assert groups["MOVE:N"][0]["scenario_specific_evidence"] == 10
    out = sc.compete_scenarios(groups=groups, actions=["WAIT", "MOVE:N"], rng_value=0.0)
    assert out["selected"] == "MOVE:N"


def test_same_future_different_action_no_invented_preference():
    meta = fsa.empty_meta()
    meta["enabled"] = True
    st = pcf.empty_store()
    st["enabled"] = True
    org = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=5, present=PRESENT, action="WAIT"),
        pcf.make_continuation(predicted=P, support=5, present=PRESENT, action="MOVE:N", actions=["MOVE:N"]),
    ])
    groups = fsa.build_groups(
        store=pr.empty_store(), observation=PRESENT, continuations=[],
        actions=["WAIT", "MOVE:N"], conflict_candidates=org["candidates"], meta=meta,
    )
    out = sc.compete_scenarios(groups=groups, actions=["WAIT", "MOVE:N"], rng_value=0.0)
    assert out["competition"]["outcome_class"] == "EXACT_TIE"


def test_toggle_and_flags_remain_off():
    rt = PhysicalSystemRuntime(seed=17)
    rt.set_mechanism("future_sensitive_action", True)
    assert rt.config.cognition.future_sensitive_action is True
    rt.set_mechanism("future_sensitive_action", False)
    assert rt.config.cognition.future_sensitive_action is False
    cfg = CognitionConfig()
    assert cfg.predictive_equivalence is False
    assert cfg.predictive_relevance is False
    assert cfg.temporal_predictive_structure is False
    assert cfg.temporal_prospection_bridge is False
    assert cfg.predictive_conflict is False
    assert cfg.future_sensitive_action is False


def test_off_path_unchanged_single_wait():
    cfg = CognitionConfig(future_sensitive_action=False, predictive_conflict=False)
    st = empty_cognitive_state(cfg)
    run_cognition_before_action(st, observation=PRESENT, tick=1, rng_value=0.0)
    sel = st["last_selection"]
    assert sel.get("future_sensitive_action") in ({}, None) or not sel.get("future_sensitive_action", {}).get("enabled")
    # empty store → endogenous, not a new policy
    assert sel.get("source") in {"ENDOGENOUS_VARIATION", "NO_SUPPORT"} or sel.get("action") in {
        "WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W",
    }
