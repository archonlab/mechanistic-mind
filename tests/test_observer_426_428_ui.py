"""Observer UI wiring for 4.26–4.28 — compact LIVE, no science change."""
from __future__ import annotations

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import TwoAgentRuntime
from mechanistic_mind.physical_system.mechanism_registry import mechanism_snapshot, set_mechanism
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame


IDS = (
    "contextual_predictive_organization",
    "context_grounded_prospection",
    "persistent_prospective_control",
)


def test_mechanisms_registered_with_dependencies():
    cfg = tiktaalik_config()
    snap = mechanism_snapshot(cfg)
    by_id = {m["id"]: m for m in snap["mechanisms"]}
    for mid in IDS:
        assert mid in by_id
        assert by_id[mid]["enabled"] is False
    assert "contextual_predictive_organization" in by_id["context_grounded_prospection"]["dependencies"]
    assert "context_grounded_prospection" in by_id["persistent_prospective_control"]["dependencies"]


def test_toggle_wires_backend_flags():
    cfg = tiktaalik_config()
    set_mechanism(cfg, "contextual_predictive_organization", True)
    assert cfg.cognition.contextual_predictive_organization is True
    set_mechanism(cfg, "context_grounded_prospection", True)
    assert cfg.cognition.context_grounded_prospection is True
    set_mechanism(cfg, "persistent_prospective_control", True)
    assert cfg.cognition.persistent_prospective_control is True


def test_compact_live_includes_stack_without_cognitive_view_builds():
    cfg = tiktaalik_config()
    cfg.cognition.contextual_predictive_organization = True
    cfg.cognition.context_grounded_prospection = True
    cfg.cognition.persistent_prospective_control = True
    rt = TwoAgentRuntime(seed=111, config=cfg)
    for _ in range(5):
        rt.step()
    rt.reset_cognitive_view_cache_stats()
    frame = live_frame(
        rt, status="RUNNING", mode="LIVE", target_tick=None,
        previous_body=None, detail="compact", include_cognition=True,
    )
    stats = rt.cognitive_view_cache_stats()
    assert stats["builds"] == 0
    mind = (frame.get("agents_views") or {}).get("agent_0", {}).get("mind") or {}
    stack = mind.get("contextual_stack")
    assert stack is not None
    assert stack.get("detail") == "compact"
    assert "context" in stack and "prospection" in stack and "persistent_control" in stack


def test_full_mind_exposes_sections():
    cfg = tiktaalik_config()
    cfg.cognition.contextual_predictive_organization = True
    rt = TwoAgentRuntime(seed=17, config=cfg)
    for _ in range(3):
        rt.step()
    frame = live_frame(
        rt, status="PAUSED", mode="LIVE", target_tick=None,
        previous_body=None, detail="full", include_cognition=True,
    )
    mind = (frame.get("agents_views") or {}).get("agent_0", {}).get("mind") or {}
    assert "contextual_predictive_organization" in mind
    assert "contextual_stack" in mind
