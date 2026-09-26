"""Smoke: webui perf helpers are observational and importable."""
from mechanistic_mind.research.webui_perf_profile import StageTimer, percentile, window_stats


def test_stage_timer_and_stats():
    t = StageTimer()
    with t.stage("a"):
        pass
    t.record_tick(0.01)
    s = t.summary()
    assert s["stages"][0]["stage"] == "a"
    assert s["tick_ms"]["n"] == 1
    assert percentile([1.0, 2.0, 3.0], 50) == 2.0
    assert window_stats([10.0, 20.0])["n"] == 2
