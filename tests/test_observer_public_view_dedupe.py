"""Observer same-tick public-view dedupe — representation only, not science."""
from __future__ import annotations

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import TwoAgentRuntime
from mechanistic_mind.research import predictive_compression as pc
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame


def _runtime(seed: int = 111, ticks: int = 80) -> TwoAgentRuntime:
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = True
    cfg.planet.width = 16
    cfg.planet.height = 16
    rt = TwoAgentRuntime(seed=seed, config=cfg)
    for _ in range(ticks):
        rt.step()
    return rt


def test_full_live_frame_builds_one_cognitive_view_per_agent():
    rt = _runtime()
    n_agents = len(rt.slots)
    rt.reset_cognitive_view_cache_stats()
    frame = live_frame(
        rt,
        status="PAUSED",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail="full",
        include_cognition=True,
    )
    stats = rt.cognitive_view_cache_stats()
    assert stats["builds"] == n_agents, (
        f"expected one cognitive_view build per agent ({n_agents}), got {stats}"
    )
    # Panels receive the canonical cog= snapshot — they must not call cognitive_view again.
    # hits==0 is OK (and preferred): reuse is by argument, not by re-entering the cache.
    assert stats["hits"] == 0, f"panels must not re-enter cognitive_view, got {stats}"
    assert (frame.get("observer") or {}).get("frame_detail") == "full"
    perf = frame.get("observer_perf") or {}
    assert perf.get("captured_tick") == int(rt.tick)
    assert perf.get("frame_detail") == "full"


def test_compact_live_frame_avoids_cognitive_view_builds():
    rt = _runtime(ticks=40)
    rt.reset_cognitive_view_cache_stats()
    frame = live_frame(
        rt,
        status="RUNNING",
        mode="LIVE",
        target_tick=None,
        previous_body=None,
        detail="compact",
        include_cognition=True,
    )
    stats = rt.cognitive_view_cache_stats()
    assert stats["builds"] == 0, f"compact must not build cognition_public_view, got {stats}"
    assert (frame.get("observer") or {}).get("frame_detail") == "compact"
    assert (frame.get("observer_perf") or {}).get("frame_detail") == "compact"


def test_memory_cost_cache_is_stable():
    rt = _runtime(ticks=30)
    mem = rt.slots[0].cognition["compression"]
    a = pc.memory_cost(mem)
    b = pc.memory_cost(mem)
    assert a == b
    assert a.get("bytes_persistent") == b.get("bytes_persistent")
