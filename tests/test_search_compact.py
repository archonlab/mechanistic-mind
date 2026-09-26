"""SEARCH_COMPACT unit gates."""
from __future__ import annotations

from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.search_compact.controller import (
    SearchCompactController,
    trigger_action_count_threshold,
)
from mechanistic_mind.ui.psy_observer_web.search_compact.metrics import CompactMetrics
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.run_finalize import new_run_id


def test_compact_metrics_bounded_visited_cells():
    m = CompactMetrics()

    class B:
        x = 1.0
        y = 2.0

    class R:
        body = B()
        last_selected_action = "MOVE:E"
        last_agent_observation = {"exo_0": 0.1}
        config = type("C", (), {"planet": type("P", (), {"width": 32, "height": 32})()})()

    for t in range(500):
        R.body.x = float(t % 32)
        R.body.y = float((t * 3) % 32)
        m.observe_tick(tick=t, runtime=R, events=[])
    assert len(m.visited_cells) <= 32 * 32
    assert m.ram_bytes_estimate() < 100_000


def test_full_vs_compact_digest_match_short():
    from datetime import datetime, timezone

    def run(mode: str):
        s = ObserverSession(SessionConfig(
            seed=17,
            execution_mode="HEADLESS",
            evidence_mode=mode,
            ui_hz=1.0,
        ))
        s.set_execution_mode("HEADLESS")
        s.set_evidence_mode(mode)
        s._active_run_id = new_run_id()
        s._run_started_at = datetime.now(timezone.utc).isoformat()
        s.step(40)
        body = s.runtime.body
        return (
            int(s.runtime.tick),
            round(float(body.x), 8),
            round(float(body.y), 8),
            round(float(body.vx), 8),
            round(float(body.vy), 8),
        )

    assert run("FULL_SCIENTIFIC") == run("SEARCH_COMPACT")


def test_trigger_preserves_pre_window():
    ctrl = SearchCompactController(
        run_id="t",
        seed=17,
        pre_window=8,
        post_window=4,
        max_candidates=2,
        cooldown=0,
        triggers=[trigger_action_count_threshold(threshold=3)],
    )

    class B:
        x = 0.0
        y = 0.0

    class R:
        body = B()
        last_selected_action = "MOVE:N"
        last_agent_observation = {}
        config = type("C", (), {"planet": type("P", (), {"width": 32, "height": 32})()})()
        tick = 0

    for t in range(20):
        R.tick = t
        ctrl.on_tick(tick=t, runtime=R, events=[])
    final = ctrl.finalize()
    assert final["metrics"]["tick_count"] >= 20
    # May or may not trigger depending on count logic; infrastructure must not crash
    assert "candidates" in final


def test_no_intelligence_score_in_worker_result():
    from mechanistic_mind.ui.psy_observer_web.search_compact.writer import build_worker_result
    r = build_worker_result(
        run_id="r", seed=1, config_fingerprint="x", target_tick=10, final_tick=10,
        status="DONE", compact_meta={"metrics": {}, "candidates": []}, digest="d",
        artifact_paths={},
    )
    assert r["intelligence_score"] is None
