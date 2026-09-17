"""Scientific history persistence + Analyzer evidence package regression tests."""
from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path

import pytest

from mechanistic_mind.ui.psy_observer_web.scientific_history import (
    ScientificHistoryWriter,
    classify_evidence_coverage,
    collect_scientific_tick_rows,
    iter_jsonl,
    load_evidence_package,
    read_jsonl_range,
    scientific_rows_to_timeline_events,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _two_agent_session(tmp: Path, *, seed: int = 88) -> ObserverSession:
    s = ObserverSession(config=SessionConfig(
        seed=seed,
        results_root=str(tmp),
        buffer_capacity=64,  # UI timeline bound = 64*8 = 512
        speed=50.0,
        ui_hz=5.0,
    ))
    s.apply_experiment({
        "seed": seed,
        "agent_count": 2,
        "cognition_enabled": True,
        "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
        "buffer_capacity": 64,
    })
    return s


def test_1_scientific_history_exceeds_ui_buffer():
    """UI buffer stays bounded; scientific evidence is complete."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        s = _two_agent_session(tmp)
        n = 600  # > UI timeline maxlen (512)
        s.step(n)
        assert len(s._timeline) <= s._timeline.maxlen
        assert len(s._timeline) < n  # bounded / truncated relative to full run
        s._sci_writer.flush()
        live = s._sci_live_dir
        assert live is not None and (live / "scientific_timeline.jsonl").is_file()
        mn, mx, rows = read_jsonl_range(live / "scientific_timeline.jsonl")
        assert mn is not None and mx is not None
        assert mx - mn + 1 >= n - 1  # near-complete tick span
        assert rows >= (n - 1) * 2  # 2 agents
        pkg = s.scientific_evidence()
        assert pkg["coverage"] == "FULL"
        assert pkg["complete_tick_level_reanalysis"] is True
        assert pkg["evidence_counts"]["scientific_rows"] >= (n - 1) * 2


def test_2_two_agent_unique_tick_agent_rows_no_ui_dupes():
    with tempfile.TemporaryDirectory() as td:
        s = _two_agent_session(Path(td))
        n = 40
        s.step(n)
        # Force extra UI captures without new ticks
        with s._lock:
            s._capture_locked(detail="full")
            s._capture_locked(detail="full")
            s._capture_locked(detail="full")
        s._sci_writer.flush()
        rows = iter_jsonl(s._sci_live_dir / "scientific_timeline.jsonl")
        keys = [(int(r["tick"]), str(r["agent_id"])) for r in rows]
        assert len(keys) == len(set(keys))
        assert len(keys) == n * 2
        agents = {k[1] for k in keys}
        assert agents == {"agent_0", "agent_1"}


def test_3_running_analysis_cutoff():
    with tempfile.TemporaryDirectory() as td:
        s = _two_agent_session(Path(td))
        s.step(30)
        cutoff = int(s.runtime.tick)
        pkg = s.scientific_evidence(cutoff_tick=cutoff)
        assert pkg["analysis_cutoff_tick"] == cutoff
        assert pkg["runtime_status"] in {"PAUSED", "RUNNING"}
        # Continue beyond cutoff
        s.step(20)
        assert int(s.runtime.tick) > cutoff
        # Re-read with same cutoff — must not include later ticks
        pkg2 = s.scientific_evidence(cutoff_tick=cutoff)
        assert pkg2["analysis_cutoff_tick"] == cutoff
        for ev in pkg2["timeline"]:
            assert int(ev["tick"]) <= cutoff
        for row in pkg2.get("scientific_rows") or []:
            assert int(row["tick"]) <= cutoff
        assert pkg2["scientific_tick_range"][1] <= cutoff


def test_4_saved_full_run_coverage():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        s = _two_agent_session(tmp)
        s.step(25)
        result = s.finalize_run(reason="USER_STOP_SAVED")
        assert result.get("accepted"), result
        run_dir = Path(result["run_dir"])
        assert (run_dir / "scientific_timeline.jsonl").is_file()
        pkg = load_evidence_package(
            evidence_dir=run_dir,
            cutoff_tick=int(result["final_tick"]),
            runtime_status="STOPPED",
            run_id=result["run_id"],
            identity={"agent_count": 2, "seed": 88, "runtime_type": "TwoAgentRuntime"},
        )
        assert pkg["coverage"] == "FULL"
        assert pkg["complete_tick_level_reanalysis"] is True


def test_5_legacy_partial_run():
    """Legacy run with only bounded session_timeline → PARTIAL."""
    with tempfile.TemporaryDirectory() as td:
        run_dir = Path(td) / "legacy"
        run_dir.mkdir()
        # Mimic retained window 19875–19900 (tiny) without scientific_timeline
        lines = []
        for t in range(19875, 19901):
            lines.append(json.dumps({
                "tick": t,
                "agent_id": "agent_0",
                "action": "WAIT",
                "bodies": [
                    {"agent_id": "agent_0", "x": 1, "y": 1, "action": "WAIT"},
                    {"agent_id": "agent_1", "x": 2, "y": 2, "action": "WAIT"},
                ],
                "contact": False,
            }))
        (run_dir / "session_timeline.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (run_dir / "run.json").write_text(json.dumps({
            "final_tick": 23970,
            "seed": 88,
            "runtime_type": "TwoAgentRuntime",
            "agent_count": 2,
            "agents": [
                {"observer_id": "agent_0", "action_counts": {"WAIT": 10000, "MOVE:N": 5000}},
                {"observer_id": "agent_1", "action_counts": {"WAIT": 20000}},
            ],
        }), encoding="utf-8")
        ui = [json.loads(x) for x in lines]
        pkg = load_evidence_package(
            evidence_dir=run_dir,
            ui_timeline=ui,
            cutoff_tick=23970,
            runtime_status="STOPPED",
            run_id="psyweb-legacy",
            identity={"agent_count": 2},
            snapshot={"slots": [
                {"cognition": {"metrics": {"action_counts": {"WAIT": 10000}}}},
                {"cognition": {"metrics": {"action_counts": {"WAIT": 20000}}}},
            ]},
        )
        assert pkg["coverage"] == "PARTIAL"
        assert pkg["complete_tick_level_reanalysis"] is False
        detail = pkg["coverage_detail"]
        assert "19875" in str(detail.get("scientific_timeline_available")) or detail.get("evidence_source") == "legacy_ui_buffers"
        assert detail.get("full_runtime_cumulative_counters_available") is True or pkg["used_cumulative_runtime_summaries"]


def test_6_cumulative_not_as_tick_history():
    cov = classify_evidence_coverage(
        scientific_tick_min=None,
        scientific_tick_max=None,
        scientific_row_count=0,
        agent_count=2,
        final_or_cutoff_tick=100,
        ui_timeline_min=50,
        ui_timeline_max=100,
        has_cumulative=True,
    )
    assert cov["coverage"] == "PARTIAL"
    assert cov["complete_tick_level_reanalysis"] is False
    assert cov["full_runtime_cumulative_counters_available"] is True


def test_7_repeated_reanalysis_identical_core():
    with tempfile.TemporaryDirectory() as td:
        s = _two_agent_session(Path(td))
        s.step(20)
        result = s.finalize_run(reason="USER_STOP_SAVED")
        run_dir = Path(result["run_dir"])
        a = load_evidence_package(evidence_dir=run_dir, cutoff_tick=result["final_tick"], runtime_status="STOPPED")
        b = load_evidence_package(evidence_dir=run_dir, cutoff_tick=result["final_tick"], runtime_status="STOPPED")
        assert a["timeline"] == b["timeline"]
        assert a["scientific_rows"] == b["scientific_rows"]
        assert a["coverage"] == b["coverage"]
        assert a["evidence_counts"] == b["evidence_counts"]


def test_8_analysis_purity_evidence_unchanged():
    with tempfile.TemporaryDirectory() as td:
        s = _two_agent_session(Path(td))
        s.step(15)
        result = s.finalize_run(reason="USER_STOP_SAVED")
        run_dir = Path(result["run_dir"])
        paths = [
            run_dir / "scientific_timeline.jsonl",
            run_dir / "scientific_events.jsonl",
            run_dir / "session_timeline.jsonl",
            run_dir / "physical_system_snapshot.json",
        ]
        before = {}
        for p in paths:
            if p.is_file():
                before[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
        # "Analyze" — load only
        _ = load_evidence_package(evidence_dir=run_dir, cutoff_tick=result["final_tick"], runtime_status="STOPPED")
        for p, digest in before.items():
            assert hashlib.sha256(Path(p).read_bytes()).hexdigest() == digest


def test_9_live_offline_agreement_at_cutoff():
    with tempfile.TemporaryDirectory() as td:
        s = _two_agent_session(Path(td))
        s.step(35)
        cutoff = int(s.runtime.tick)
        live_pkg = s.scientific_evidence(cutoff_tick=cutoff)
        # Offline path: read same live dir files
        offline = load_evidence_package(
            evidence_dir=s._sci_live_dir,
            cutoff_tick=cutoff,
            runtime_status="PAUSED",
            identity={"agent_count": 2},
        )
        assert live_pkg["evidence_counts"]["scientific_rows"] == offline["evidence_counts"]["scientific_rows"]
        assert live_pkg["timeline"] == offline["timeline"]
        # Tick-level action tallies should match
        def counts(pkg):
            out = {}
            for row in pkg.get("scientific_rows") or []:
                aid = row["agent_id"]
                act = row.get("action") or "NONE"
                out.setdefault(aid, {})
                out[aid][act] = out[aid].get(act, 0) + 1
            return out
        assert counts(live_pkg) == counts(offline)


def test_10_growth_depends_on_ticks_not_ui_refreshes():
    with tempfile.TemporaryDirectory() as td:
        s = _two_agent_session(Path(td))
        s.step(10)
        s._sci_writer.flush()
        size1 = (s._sci_live_dir / "scientific_timeline.jsonl").stat().st_size
        rows1 = read_jsonl_range(s._sci_live_dir / "scientific_timeline.jsonl")[2]
        # Many UI captures, no new ticks
        for _ in range(50):
            with s._lock:
                s._capture_locked(detail="full")
        s._sci_writer.flush()
        size2 = (s._sci_live_dir / "scientific_timeline.jsonl").stat().st_size
        rows2 = read_jsonl_range(s._sci_live_dir / "scientific_timeline.jsonl")[2]
        assert rows2 == rows1
        assert size2 == size1
        # New ticks grow storage
        s.step(10)
        s._sci_writer.flush()
        rows3 = read_jsonl_range(s._sci_live_dir / "scientific_timeline.jsonl")[2]
        assert rows3 == rows1 + 20  # 10 ticks * 2 agents


def test_storage_bytes_per_tick_measurable():
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        # Two-agent
        s2 = _two_agent_session(tmp / "two")
        s2.step(100)
        s2._sci_writer.flush()
        sz2 = (s2._sci_live_dir / "scientific_timeline.jsonl").stat().st_size
        bytes_per_tick_two = sz2 / 100.0

        # Single-agent
        s1 = ObserverSession(config=SessionConfig(
            seed=17, results_root=str(tmp / "one"), buffer_capacity=64, speed=50.0,
        ))
        s1.apply_experiment({
            "seed": 17, "agent_count": 1, "cognition_enabled": True,
            "world": {"width": 12, "height": 12},
        })
        s1.step(100)
        s1._sci_writer.flush()
        sz1 = (s1._sci_live_dir / "scientific_timeline.jsonl").stat().st_size
        bytes_per_tick_one = sz1 / 100.0

        # Sanity: two-agent roughly ~2× single (compact rows)
        assert bytes_per_tick_one > 50
        assert bytes_per_tick_two > bytes_per_tick_one * 1.5
        # Record for human report via assert message
        assert bytes_per_tick_two < 5000, (bytes_per_tick_one, bytes_per_tick_two)


def test_runtime_not_advanced_by_evidence_load():
    with tempfile.TemporaryDirectory() as td:
        s = _two_agent_session(Path(td))
        s.step(12)
        tick = int(s.runtime.tick)
        fp = collect_scientific_tick_rows(s.runtime)
        _ = s.scientific_evidence(cutoff_tick=tick)
        assert int(s.runtime.tick) == tick
        assert collect_scientific_tick_rows(s.runtime) == fp


def test_scientific_rows_to_timeline_grouping():
    rows = [
        {"tick": 1, "agent_id": "agent_0", "x": 0, "y": 0, "action": "WAIT", "contact": False},
        {"tick": 1, "agent_id": "agent_1", "x": 1, "y": 1, "action": "MOVE:N", "contact": True},
        {"tick": 2, "agent_id": "agent_0", "x": 0, "y": 0, "action": "WAIT", "contact": False},
        {"tick": 2, "agent_id": "agent_1", "x": 1, "y": 2, "action": "WAIT", "contact": False},
    ]
    ev = scientific_rows_to_timeline_events(rows)
    assert len(ev) == 2
    assert ev[0]["contact"] is True
    assert len(ev[0]["bodies"]) == 2
