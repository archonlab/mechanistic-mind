"""Predictive equivalence: consequence grouping, not float binning."""
from __future__ import annotations

from mechanistic_mind.physical_system.cognition import (
    CognitionConfig,
    empty_cognitive_state,
    run_cognition_before_action,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import predictive_equivalence as pe


def _store():
    s = pe.empty_store()
    s["enabled"] = True
    return s


def _train(store, xs, cons, action="WAIT", start=1, reps=4):
    t = start
    for _ in range(reps):
        for x in xs:
            pe.learn(store, fragment={"x": float(x)}, action=action, consequent=cons, tick=t)
            t += 1
    return t


def test_default_off_in_current_mm():
    assert CognitionConfig().predictive_equivalence is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.predictive_equivalence is False
    assert rt.cognition["equivalence"]["enabled"] is False
    pe.learn(rt.cognition["equivalence"], fragment={"x": 0.11}, action="WAIT", consequent={"y": 0.9}, tick=1)
    assert rt.cognition["equivalence"]["classes"] == {}


def test_grouping_by_continuation_not_proximity():
    store = _store()
    fam_a = {"y": 0.90}
    fam_b = {"y": 0.10}
    _train(store, (0.11, 0.24, 0.39), fam_a)
    _train(store, (0.40, 0.41), fam_b, start=50)
    a = pe.retrieve(store, {"x": 0.18}, "WAIT")
    b_near_a = pe.retrieve(store, {"x": 0.405}, "WAIT")
    b_mem = pe.retrieve(store, {"x": 0.40}, "WAIT")
    assert a["status"] == "MATCH"
    assert abs(float(a["predicted"]["y"]) - 0.90) < 0.05
    assert b_near_a["status"] == "MATCH"
    assert abs(float(b_near_a["predicted"]["y"]) - 0.10) < 0.05
    assert b_mem["class_id"] != a["class_id"]
    # 0.39 and 0.40 are numerically close but must stay in different families.
    r39 = pe.retrieve(store, {"x": 0.39}, "WAIT")
    r40 = pe.retrieve(store, {"x": 0.40}, "WAIT")
    assert abs(float(r39["predicted"]["y"]) - float(r40["predicted"]["y"])) > 0.5


def test_held_out_generalization_and_sha_miss():
    store = _store()
    _train(store, (0.11, 0.24, 0.39), {"y": 0.90})
    _train(store, (0.40, 0.41), {"y": 0.10}, start=40)
    for x in (0.18, 0.31):
        sha = pc.predict({"structures": {}}, {"x": x}, "WAIT")
        # empty compression → NO_MATCH; also check a trained compression
        assert sha["status"] == "NO_MATCH"
        got = pe.retrieve(store, {"x": x}, "WAIT")
        assert got["status"] == "MATCH"
        assert abs(float(got["predicted"]["y"]) - 0.90) < 0.05
        assert got["gate"] == "class_span"
        assert got["raw_antecedent_sig"] != got["member_sigs"][0] or True


def test_same_value_different_context_not_collapsed():
    store = _store()
    for _ in range(4):
        pe.learn(store, fragment={"x": 0.50, "ctx": 0.10}, action="WAIT", consequent={"y": 0.90}, tick=1)
        pe.learn(store, fragment={"x": 0.50, "ctx": 0.90}, action="WAIT", consequent={"y": 0.10}, tick=2)
    p = pe.retrieve(store, {"x": 0.50, "ctx": 0.10}, "WAIT")
    q = pe.retrieve(store, {"x": 0.50, "ctx": 0.90}, "WAIT")
    assert p["status"] == "MATCH" and q["status"] == "MATCH"
    assert abs(float(p["predicted"]["y"]) - 0.90) < 0.05
    assert abs(float(q["predicted"]["y"]) - 0.10) < 0.05
    assert p["class_id"] != q["class_id"]


def test_irrelevant_z_suppressed_relevant_x_kept():
    store = _store()
    zs = (0.02, 0.33, 0.71, 0.95)
    for _ in range(3):
        for z in zs:
            pe.learn(store, fragment={"x": 0.20, "z": z}, action="WAIT", consequent={"y": 0.90}, tick=1)
            pe.learn(store, fragment={"x": 0.80, "z": z}, action="WAIT", consequent={"y": 0.10}, tick=2)
    new_z = 0.48
    low = pe.retrieve(store, {"x": 0.20, "z": new_z}, "WAIT")
    high = pe.retrieve(store, {"x": 0.80, "z": new_z}, "WAIT")
    assert low["status"] == "MATCH" and high["status"] == "MATCH"
    assert abs(float(low["predicted"]["y"]) - 0.90) < 0.05
    assert abs(float(high["predicted"]["y"]) - 0.10) < 0.05


def test_tiny_causal_difference_preserved():
    store = _store()
    _train(store, (0.40,), {"y": 0.90})
    _train(store, (0.41,), {"y": 0.10}, start=20)
    r40 = pe.retrieve(store, {"x": 0.40}, "WAIT")
    r41 = pe.retrieve(store, {"x": 0.41}, "WAIT")
    mid = pe.retrieve(store, {"x": 0.405}, "WAIT")
    assert r40["status"] == "MATCH" and abs(float(r40["predicted"]["y"]) - 0.90) < 0.05
    assert r41["status"] == "MATCH" and abs(float(r41["predicted"]["y"]) - 0.10) < 0.05
    assert mid["status"] == "NO_MATCH"


def test_revision_splits_when_consequences_diverge():
    store = _store()
    for i in range(6):
        pe.learn(store, fragment={"x": 0.11}, action="WAIT", consequent={"y": 0.90}, tick=i)
        pe.learn(store, fragment={"x": 0.24}, action="WAIT", consequent={"y": 0.90}, tick=i)
    before = pe.retrieve(store, {"x": 0.24}, "WAIT")
    assert before["status"] == "MATCH"
    assert abs(float(before["predicted"]["y"]) - 0.90) < 0.05
    for i in range(8):
        pe.learn(store, fragment={"x": 0.24}, action="WAIT", consequent={"y": 0.10}, tick=100 + i)
    after24 = pe.retrieve(store, {"x": 0.24}, "WAIT")
    after11 = pe.retrieve(store, {"x": 0.11}, "WAIT")
    assert after24["status"] == "MATCH"
    assert abs(float(after24["predicted"]["y"]) - 0.10) < 0.08
    assert after11["status"] == "MATCH"
    assert abs(float(after11["predicted"]["y"]) - 0.90) < 0.08
    assert store["splits"] >= 1


def test_memory_bounded_under_boring_variation():
    store = _store()
    for i in range(400):
        pe.learn(store, fragment={"x": 0.01 * (i % 50)}, action="WAIT", consequent={"y": 0.90}, tick=i)
    snap = pe.snapshot(store)
    assert snap["episode_n"] <= pe.MAX_EPISODES
    assert snap["active"] <= pe.MAX_CLASSES
    for cls in (store["classes"] or {}).values():
        assert len(cls.get("members") or {}) <= pe.MAX_MEMBERS


def test_cognition_pipeline_fallback_on_sha_miss():
    cfg = CognitionConfig(predictive_equivalence=True)
    state = empty_cognitive_state(cfg)
    tick = 1
    for _ in range(4):
        for x in (0.11, 0.24, 0.39):
            state["last_fragment"] = {"x": float(x)}
            state["last_action"] = "WAIT"
            run_cognition_before_action(state, observation={"y": 0.90, "x": float(x)}, tick=tick, rng_value=0.0)
            tick += 1
    held = {"x": 0.18}
    sha = pc.predict(state["compression"], held, "WAIT", domain="accessible")
    got = pe.retrieve(state["equivalence"], held, "WAIT")
    assert sha["status"] == "NO_MATCH"
    assert got["status"] == "MATCH"
    assert abs(float(got["predicted"]["y"]) - 0.90) < 0.05
    # raw observation still present in PE provenance/members
    members = next(iter(state["equivalence"]["classes"].values()))["members"]
    assert any(abs(float(m["fragment"]["x"]) - 0.11) < 1e-9 for m in members.values())


def test_toggle_does_not_promote_default():
    rt = PhysicalSystemRuntime(seed=3)
    assert rt.config.cognition.predictive_equivalence is False
    rt.set_mechanism("predictive_equivalence", True)
    assert rt.config.cognition.predictive_equivalence is True
    assert rt.cognition["equivalence"]["enabled"] is True
    rt.set_mechanism("predictive_equivalence", False)
    assert rt.config.cognition.predictive_equivalence is False
    assert rt.cognition["equivalence"]["enabled"] is False
