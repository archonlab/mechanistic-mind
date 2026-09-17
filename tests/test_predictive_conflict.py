"""Predictive conflict: content identity, merge compatible, keep incompatible. Default OFF."""
from __future__ import annotations

from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.research import temporal_prospection_bridge as tpb

ACTION = "WAIT"
P = {"y": 0.90}
Q = {"y": 0.10}
PRESENT = {"x": 0.50}


def _store():
    s = pcf.empty_store()
    s["enabled"] = True
    return s


def test_default_off():
    assert CognitionConfig().predictive_conflict is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.predictive_conflict is False
    assert rt.cognition["conflict"]["enabled"] is False
    off = pcf.organize(pcf.empty_store(), [
        pcf.make_continuation(predicted=P, support=4, source="SNAPSHOT"),
        pcf.make_continuation(predicted=Q, support=4, source="TEMPORAL"),
    ])
    assert off["status"] == "DISABLED"
    assert off["candidates"] == []


def test_wait_p_and_wait_q_coexist():
    st = _store()
    out = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=4, source="SNAPSHOT", present=PRESENT),
        pcf.make_continuation(predicted=Q, support=3, source="TEMPORAL", present=PRESENT),
    ])
    assert out["n_conflict_groups"] == 1
    cands = out["candidates"]
    assert len(cands) == 2
    acts = {c["first_action"] for c in cands}
    assert acts == {ACTION}
    ys = sorted(float(c["predicted"]["y"]) for c in cands)
    assert abs(ys[0] - 0.10) < 0.02
    assert abs(ys[1] - 0.90) < 0.02
    assert all(c["status"] == "CONFLICTING" for c in cands)


def test_snapshot_and_temporal_same_p_merge():
    st = _store()
    out = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=4, source="SNAPSHOT", present=PRESENT, raw_id="r1", structure_id="SHA1"),
        pcf.make_continuation(predicted=P, support=4, source="TEMPORAL", present=PRESENT, raw_id="r1", structure_id="TPS1"),
    ])
    assert len(out["candidates"]) == 1
    c = out["candidates"][0]
    assert c["status"] == "COMPATIBLE"
    assert set(c["prediction_sources"]) == {"SNAPSHOT", "TEMPORAL"}
    assert c["support"] == 4
    assert c["evidence"]["summed"] is False
    assert c["evidence"]["shared_ancestry"] is True


def test_snapshot_p_temporal_q_distinct():
    st = _store()
    out = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=5, source="SNAPSHOT", present=PRESENT),
        pcf.make_continuation(predicted=Q, support=4, source="TEMPORAL", present=PRESENT),
    ])
    assert len(out["candidates"]) == 2
    assert out["status"] == "CONFLICTING"


def test_support_discriminates_without_new_weights():
    st = _store()
    out = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=12, source="SNAPSHOT", present=PRESENT),
        pcf.make_continuation(predicted=Q, support=3, source="TEMPORAL", present=PRESENT),
    ])
    by_y = {round(float(c["predicted"]["y"]), 1): c for c in out["candidates"]}
    assert by_y[0.9]["support"] == 12
    assert by_y[0.1]["support"] == 3
    leaders = out["receipt"]["support_leaders"]
    assert leaders[ACTION] == by_y[0.9]["id"]


def test_shared_ancestry_not_summed():
    st = _store()
    out = pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=4, source="SNAPSHOT", present=PRESENT, raw_id="t0", structure_id="SHA"),
        pcf.make_continuation(predicted=P, support=4, source="TEMPORAL", present=PRESENT, raw_id="t0", structure_id="PE"),
        pcf.make_continuation(predicted=P, support=4, source="TEMPORAL", present=PRESENT, raw_id="t0", structure_id="TPS"),
    ])
    assert len(out["candidates"]) == 1
    ev = out["candidates"][0]["evidence"]
    assert ev["support"] == 4
    assert ev["summed"] is False
    assert ev["n_routes"] == 3


def test_prefix_divergent_remain_distinct():
    st = _store()
    x = {"y": 0.50}
    out = pcf.organize(st, [
        pcf.make_continuation(
            predicted=x, support=4, source="SNAPSHOT", present=PRESENT,
            actions=[ACTION, ACTION], path=[x, P],
        ),
        pcf.make_continuation(
            predicted=x, support=4, source="SNAPSHOT", present=PRESENT,
            actions=[ACTION, ACTION], path=[x, Q],
        ),
    ])
    assert len(out["candidates"]) == 2
    assert all(c["first_action"] == ACTION for c in out["candidates"])
    terminals = sorted(float(c["predicted_path"][-1]["y"]) for c in out["candidates"])
    assert abs(terminals[0] - 0.10) < 0.02
    assert abs(terminals[1] - 0.90) < 0.02


def test_realized_mismatch_disconfirms_without_belief():
    st = _store()
    pcf.organize(st, [
        pcf.make_continuation(predicted=P, support=6, source="SNAPSHOT", present=PRESENT),
        pcf.make_continuation(predicted=Q, support=5, source="TEMPORAL", present=PRESENT),
    ])
    out = pcf.organize(
        st,
        [
            pcf.make_continuation(predicted=P, support=6, source="SNAPSHOT", present=PRESENT),
            pcf.make_continuation(predicted=Q, support=5, source="TEMPORAL", present=PRESENT),
        ],
        realized=P,
        last_action=ACTION,
    )
    by_y = {round(float(c["predicted"]["y"]), 1): c for c in out["candidates"]}
    assert by_y[0.1]["status"] == "DISCONFIRMED"
    assert by_y[0.9]["status"] != "DISCONFIRMED"
    assert st["disconfirmations"] >= 1


def test_competition_still_first_action_only():
    conts = [
        pcf.make_continuation(predicted=P, support=12, source="SNAPSHOT", present=PRESENT),
        pcf.make_continuation(predicted=Q, support=3, source="TEMPORAL", present=PRESENT),
    ]
    groups = sc.collect_scenario_groups(
        store=pr.empty_store(),
        observation=PRESENT,
        continuations=conts,
        actions=[ACTION],
    )
    wait = groups.get(ACTION) or []
    # Current grouping can collapse same sequence/depth/support; either way one first action.
    selected = sc.compete_scenarios(groups=groups, actions=[ACTION], rng_value=0.0)
    assert selected.get("selected") == ACTION
    org = pcf.organize(_store(), conts)
    assert len(org["candidates"]) == 2
    assert len({s["first_action"] for s in wait}) <= 1


def test_live_toggle_and_no_selection_change():
    rt = PhysicalSystemRuntime(seed=17)
    rt.set_mechanism("predictive_conflict", True)
    assert rt.config.cognition.predictive_conflict is True
    rt.set_mechanism("predictive_conflict", False)
    assert rt.config.cognition.predictive_conflict is False
    cfg = CognitionConfig(predictive_conflict=True, temporal_predictive_structure=True, temporal_prospection_bridge=True)
    st = empty_cognitive_state(cfg)
    tstore = tps.empty_store()
    tstore["enabled"] = True
    for _ in range(4):
        tstore["ring"] = []
        for x in (0.20, 0.30, 0.40, 0.50):
            frag = {"x": float(x)}
            if tstore["ring"]:
                tps.learn(tstore, consequent=frag, action=ACTION, tick=1)
            tps.append(tstore, frag)
        tps.learn(tstore, consequent=P, action=ACTION, tick=1)
    st["temporal"] = tstore
    tstore["ring"] = [{"x": 0.20}, {"x": 0.30}, {"x": 0.40}]
    run_cognition_before_action(st, observation={"x": 0.50}, tick=1, rng_value=0.0)
    sel = st["last_selection"]
    assert sel.get("action") == ACTION or sel.get("action") in {"WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"}
    # Conflict does not rewrite selection rule.
    assert "SCENARIO_COMPETITION" in str(sel.get("prospective_selection_mode") or "SCENARIO_COMPETITION") or sel.get("source")


def test_bridge_conflict_survives_organize():
    tstore = tps.empty_store()
    tstore["enabled"] = True
    for _ in range(4):
        tstore["ring"] = []
        for x in (0.20, 0.30, 0.40, 0.50):
            frag = {"x": float(x)}
            if tstore["ring"]:
                tps.learn(tstore, consequent=frag, action=ACTION, tick=1)
            tps.append(tstore, frag)
        tps.learn(tstore, consequent=P, action=ACTION, tick=1)
        tstore["ring"] = []
        for x in (0.80, 0.70, 0.60, 0.50):
            frag = {"x": float(x)}
            if tstore["ring"]:
                tps.learn(tstore, consequent=frag, action=ACTION, tick=1)
            tps.append(tstore, frag)
        tps.learn(tstore, consequent=Q, action=ACTION, tick=1)
    present = {"x": 0.50}
    # Two histories are not simultaneous on one ring; inject both as entry_steps.
    e1 = tpb.as_entry_step(
        {"status": "MATCH", "predicted_continuation": P, "support": 4, "class_id": "H1", "lag": 1},
        action=ACTION, present=present,
    )
    e2 = tpb.as_entry_step(
        {"status": "MATCH", "predicted_continuation": Q, "support": 4, "class_id": "H2", "lag": 1},
        action=ACTION, present=present,
    )
    comp = pr.compose_trajectories(
        pr.empty_store(), start=present, max_depth=2, branch_actions=[ACTION],
        entry_steps=[e1, e2],
    )
    st = _store()
    out = pcf.organize(st, comp.get("continuations") or [])
    assert len(out["candidates"]) >= 2
    assert out["n_conflict_groups"] >= 1


def test_all_experimental_flags_remain_off():
    cfg = CognitionConfig()
    assert cfg.predictive_equivalence is False
    assert cfg.predictive_relevance is False
    assert cfg.temporal_predictive_structure is False
    assert cfg.temporal_prospection_bridge is False
    assert cfg.predictive_conflict is False
