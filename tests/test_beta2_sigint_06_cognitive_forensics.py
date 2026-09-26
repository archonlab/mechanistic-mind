"""BETA2-SIGINT-06: cognitive divergence forensics tests."""
from __future__ import annotations

from mechanistic_mind.ui.psy_observer_web.signal_context.cognitive_forensics import (
    DEFAULT_SIGINT05,
    build_pipeline_ladder,
    find_bottleneck,
    load_sigint05_level2_hits,
    persistence_profile,
    reproduce_level2_hit,
)


def test_load_exact_sigint05_level2_hits():
    hits = load_sigint05_level2_hits(DEFAULT_SIGINT05)
    assert len(hits) == 3
    ids = {h["episode_id"] for h in hits}
    assert "ep-35b351684b39" in ids
    assert "ep-353081e8a1ee" in ids
    assert "ep-12067434ac5a" in ids
    for h in hits:
        assert h.get("seed") == 17
        assert h.get("s0_tick") == 31
        assert (h.get("levels") or {}).get("L2_cognition") is True
        assert (h.get("levels") or {}).get("L3_action") is False
        assert h.get("episode") is not None


def test_reproduce_one_level2_hit_forensics():
    hits = load_sigint05_level2_hits(DEFAULT_SIGINT05)
    # Use the shortest episode for speed (46-56, 22 components)
    hit = min(hits, key=lambda h: int(h.get("end_tick") or 0) - int(h.get("start_tick") or 0))
    result = reproduce_level2_hit(hit, horizon=50, extended_horizons=())
    assert result.get("accepted")
    assert result.get("control_control_equal") is True
    assert result.get("any_leak") is False
    ladder = result.get("pipeline_ladder") or {}
    assert "selection_source" in ladder
    assert "requested_action" in ladder
    # If L2 reproduces: action should stay SAME
    if result.get("level2_reproduced"):
        assert ladder["requested_action"]["status"] == "SAME"
        assert ladder["selection_source"]["status"] == "DIVERGED"
        bn = result["bottleneck"]
        assert bn["classification"] == "ACTION_CONVERGENCE_WITH_INTERNAL_DIVERGENCE"
        persist = result["persistence"]
        assert persist["label"] in (
            "TRANSIENT", "PERSISTENT", "RECONVERGENT", "DELAYED", "SHORT_LIVED", "NONE", "NOT_ESTABLISHED",
        )


def test_pipeline_ladder_helpers():
    # Synthetic mini traces
    def ag(src, act, field=0.0, cands=None):
        return {
            "obs_FIELD_A": field,
            "local_fields": {"FIELD_A": field},
            "selection_source": src,
            "requested_action": act,
            "candidates": cands or ["WAIT"],
            "ranked_scenarios": [{"scenario_id": "C1", "first_action": act, "historical_support": 1}],
            "selected_scenario": {"scenario_id": "C1", "first_action": act},
            "action_selection_margin": None,
            "prediction_matches": None,
            "selection_reason": "X",
            "x": 0.0,
            "y": 0.0,
        }

    ctrl = [
        {"branch_tick": 1, "agents": [ag("A", "WAIT"), ag("A", "WAIT", 0.0)]},
        {"branch_tick": 2, "agents": [ag("A", "WAIT"), ag("A", "WAIT", 0.0)]},
        {"branch_tick": 3, "agents": [ag("A", "WAIT"), ag("A", "WAIT", 0.0)]},
    ]
    rep = [
        {"branch_tick": 1, "agents": [ag("A", "WAIT"), ag("A", "WAIT", 0.1)]},
        {"branch_tick": 2, "agents": [ag("A", "WAIT"), ag("B", "WAIT", 0.1)]},
        {"branch_tick": 3, "agents": [ag("A", "WAIT"), ag("A", "WAIT", 0.0)]},
    ]
    ladder = build_pipeline_ladder(ctrl, rep, slot=1)
    assert ladder["observation"]["first_divergence_tick"] == 1
    assert ladder["selection_source"]["first_divergence_tick"] == 2
    assert ladder["selection_source"]["reconvergence_tick"] == 3
    assert ladder["requested_action"]["status"] == "SAME"
    bn = find_bottleneck(ladder, ctrl, rep, slot=1)
    assert bn["classification"] == "ACTION_CONVERGENCE_WITH_INTERNAL_DIVERGENCE"
    assert bn["best_supported"]["code"] == "D"
    p = persistence_profile(ladder)
    assert p["label"] in ("TRANSIENT", "RECONVERGENT", "SHORT_LIVED")


def test_session_forensics_api_shape():
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    r = sess.list_cognitive_forensics(limit=4)
    assert r["accepted"] is True
    assert r.get("honesty", {}).get("on_demand_only") is True
