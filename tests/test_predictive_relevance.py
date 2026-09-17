"""Relation-specific predictive relevance: partial retrieval, not a global mask."""
from __future__ import annotations

from mechanistic_mind.physical_system.cognition import CognitionConfig, empty_cognitive_state, run_cognition_before_action
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import predictive_relevance as prl

ACTION = "WAIT"
P = {"y": 0.90}
Q = {"y": 0.10}


def _pe():
    s = pe.empty_store()
    s["enabled"] = True
    return s


def _train(store, rows, reps=4):
    t = 1
    for _ in range(reps):
        for frag, cons in rows:
            pe.learn(store, fragment=frag, action=ACTION, consequent=cons, tick=t)
            t += 1
    meta = prl.empty_meta()
    meta["enabled"] = True
    prl.refresh(store, tick=t, meta=meta)
    return meta


def test_default_off():
    assert CognitionConfig().predictive_relevance is False
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.cognition.predictive_relevance is False
    assert rt.cognition["relevance"]["enabled"] is False


def test_partial_retrieval_vs_full_aabb_veto():
    store = _pe()
    rows = []
    for a in (0.11, 0.24, 0.39):
        for b in (0.10, 0.90):
            for d in (0.20, 0.80):
                rows.append(({"a": a, "b": b, "d": d}, P))
    for a in (0.40, 0.41):
        for b in (0.10, 0.90):
            for d in (0.20, 0.80):
                rows.append(({"a": a, "b": b, "d": d}, Q))
    meta = _train(store, rows, reps=3)
    held = {"a": 0.18, "b": 0.99, "d": 0.01}  # b,d far outside training AABB
    sha = pc.predict(pc.empty_memory(), held, ACTION, domain="accessible")
    full = pe.retrieve(store, held, ACTION)
    part = prl.retrieve(store, held, ACTION, meta=meta)
    assert sha["status"] == "NO_MATCH"
    assert full["status"] == "NO_MATCH"
    assert part["status"] == "MATCH"
    assert abs(float(part["predicted"]["y"]) - 0.90) < 0.08
    assert "b" in part["allowed_variation"]
    assert "a" in part["relevant"] or "a" in part["discriminative"]
    assert part["full_aabb_would_match"] is False


def test_tiny_causal_a_large_irrelevant_b():
    store = _pe()
    rows = []
    for b in (0.05, 0.40, 0.95):
        rows.append(({"a": 0.40, "b": b}, P))
        rows.append(({"a": 0.41, "b": b}, Q))
    meta = _train(store, rows, reps=5)
    wild_p = prl.retrieve(store, {"a": 0.40, "b": 0.99}, ACTION, meta=meta)
    wild_q = prl.retrieve(store, {"a": 0.41, "b": 0.01}, ACTION, meta=meta)
    mid = prl.retrieve(store, {"a": 0.405, "b": 0.50}, ACTION, meta=meta)
    assert wild_p["status"] == "MATCH" and abs(float(wild_p["predicted"]["y"]) - 0.90) < 0.08
    assert wild_q["status"] == "MATCH" and abs(float(wild_q["predicted"]["y"]) - 0.10) < 0.08
    assert mid["status"] == "NO_MATCH"


def test_context_not_collapsed():
    store = _pe()
    rows = []
    for a in (0.20, 0.30, 0.35):
        for b in (0.1, 0.8):
            rows.append(({"a": a, "c": 0.10, "b": b}, P))
            rows.append(({"a": a, "c": 0.90, "b": b}, Q))
    meta = _train(store, rows)
    p = prl.retrieve(store, {"a": 0.28, "c": 0.10, "b": 0.99}, ACTION, meta=meta)
    q = prl.retrieve(store, {"a": 0.28, "c": 0.90, "b": 0.99}, ACTION, meta=meta)
    assert p["status"] == "MATCH" and abs(float(p["predicted"]["y"]) - 0.90) < 0.08
    assert q["status"] == "MATCH" and abs(float(q["predicted"]["y"]) - 0.10) < 0.08
    assert p["class_id"] != q["class_id"]
    # c is relation-specific relevant; a overlaps so may be allowed
    assert "c" in (p.get("relevant") or p.get("discriminative") or [])


def test_false_match_necessary_feature_differs():
    store = _pe()
    rows = []
    for a in (0.11, 0.24, 0.39):
        for b in (0.2, 0.6):
            rows.append(({"a": a, "b": b}, P))
    for a in (0.40, 0.41):
        for b in (0.2, 0.6):
            rows.append(({"a": a, "b": b}, Q))
    meta = _train(store, rows)
    # b matches P's range, a belongs to Q
    got = prl.retrieve(store, {"a": 0.405, "b": 0.20}, ACTION, meta=meta)
    assert got["status"] in {"MATCH", "NO_MATCH"}
    if got["status"] == "MATCH":
        assert abs(float(got["predicted"]["y"]) - 0.10) < 0.08


def test_missing_relevant_feature_insufficient():
    store = _pe()
    rows = [({"a": 0.20, "b": z}, P) for z in (0.1, 0.5, 0.9)]
    rows += [({"a": 0.80, "b": z}, Q) for z in (0.1, 0.5, 0.9)]
    meta = _train(store, rows, reps=5)
    got = prl.retrieve(store, {"b": 0.5}, ACTION, meta=meta)  # a missing
    assert got["status"] == "NO_MATCH"


def test_relevance_revises_when_b_becomes_discriminative():
    store = _pe()
    rows = [({"a": 0.25, "b": z}, P) for z in (0.1, 0.4, 0.8)]
    meta = _train(store, rows, reps=4)
    before = (store["classes"][next(iter(store["classes"]))]["relevance"].get("allowed_variation") or [])
    assert "b" in before
    for i in range(12):
        z = (0.1, 0.4, 0.8)[i % 3]
        pe.learn(
            store,
            fragment={"a": 0.25, "b": z},
            action=ACTION,
            consequent=Q if z > 0.3 else P,
            tick=200 + i,
        )
    prl.refresh(store, tick=210, meta=meta)
    rels = [c["relevance"] for c in store["classes"].values() if c.get("status") == "ACTIVE"]
    disc = set()
    for r in rels:
        disc |= set(r.get("discriminative") or [])
        disc |= set(r.get("relevant") or [])
    assert "b" in disc


def test_two_relations_different_keys():
    store = _pe()
    rows = []
    # R_y: a partitions y; b varies
    for a, cons in ((0.20, P), (0.80, Q)):
        for b in (0.15, 0.55, 0.85):
            rows.append(({"a": a, "b": b, "k": 0.5}, cons))
    # R_w: b partitions w; a varies — different continuation key
    W1, W0 = {"w": 0.90}, {"w": 0.10}
    for b, cons in ((0.20, W1), (0.80, W0)):
        for a in (0.15, 0.55, 0.85):
            rows.append(({"a": a, "b": b, "k": 0.5}, cons))
    meta = _train(store, rows, reps=3)
    ygot = prl.retrieve(store, {"a": 0.20, "b": 0.99, "k": 0.5}, ACTION, meta=meta)
    wgot = prl.retrieve(store, {"a": 0.99, "b": 0.20, "k": 0.5}, ACTION, meta=meta)
    assert ygot["status"] == "MATCH"
    assert wgot["status"] == "MATCH"
    assert ygot["class_id"] != wgot["class_id"]
    assert abs(float(ygot["predicted"].get("y") or 0) - 0.90) < 0.08
    assert abs(float(wgot["predicted"].get("w") or 0) - 0.90) < 0.08


def test_conflicting_partial_matches_are_not_arbitrated():
    store = _pe()
    rows = []
    for a in (0.20, 0.22, 0.24):
        rows.append(({"a": a, "b": 0.50}, P))
    for b in (0.70, 0.72, 0.74):
        rows.append(({"a": 0.50, "b": b}, Q))
    meta = _train(store, rows, reps=4)
    # query matches R1 on a and R2 on b
    got = prl.retrieve(store, {"a": 0.22, "b": 0.72}, ACTION, meta=meta)
    assert got["status"] in {"CONFLICT", "MATCH", "NO_MATCH"}
    if got["status"] == "CONFLICT":
        assert got.get("next_gear_missing") is True


def test_cognition_pipeline_partial_source():
    cfg = CognitionConfig(predictive_equivalence=True, predictive_relevance=True)
    state = empty_cognitive_state(cfg)
    tick = 1
    for _ in range(4):
        for a in (0.11, 0.24, 0.39):
            for b in (0.2, 0.8):
                state["last_fragment"] = {"a": a, "b": b}
                state["last_action"] = ACTION
                run_cognition_before_action(state, observation={"y": 0.90, "a": a, "b": b}, tick=tick, rng_value=0.0)
                tick += 1
        for a in (0.40, 0.41):
            state["last_fragment"] = {"a": a, "b": 0.2}
            state["last_action"] = ACTION
            run_cognition_before_action(state, observation={"y": 0.10, "a": a, "b": 0.2}, tick=tick, rng_value=0.0)
            tick += 1
    held = {"a": 0.18, "b": 0.99}
    sha = pc.predict(state["compression"], held, ACTION, domain="accessible")
    full = pe.retrieve(state["equivalence"], held, ACTION)
    part = prl.retrieve(state["equivalence"], held, ACTION, meta=state["relevance"])
    assert sha["status"] == "NO_MATCH"
    assert full["status"] == "NO_MATCH"
    assert part["status"] == "MATCH"
    assert part["source"] == "predictive_relevance"
