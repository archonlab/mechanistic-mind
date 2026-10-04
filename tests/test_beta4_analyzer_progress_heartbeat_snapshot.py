"""BETA4 analyzer progress / heartbeat / frozen snapshot contract tests."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from mechanistic_mind.scientific_v3.analyzer_next.job import (
    LOG_BOUND,
    ProgressReporter,
    PROGRESS_SCHEMA,
    write_progress,
)
from mechanistic_mind.scientific_v3.analyzer_next.snapshot import (
    SCHEMA as SNAP_SCHEMA,
    build_evidence_snapshot,
    last_complete_jsonl_byte_end,
)
from mechanistic_mind.scientific_v3.api import RunEvidence


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _mini_run(tmp: Path, *, ticks: int = 5) -> Path:
    run = tmp / "psyweb-mini.live-test"
    run.mkdir(parents=True)
    spine = [{"tick": t, "schema": "scientific_spine", "agents": {}} for t in range(ticks)]
    _write_jsonl(run / "scientific_spine.jsonl", spine)
    _write_jsonl(run / "scientific_decisions.jsonl", [{"tick": t, "agent_id": "agent_0"} for t in range(ticks)])
    (run / "scientific_v3_meta.json").write_text(
        json.dumps({"run_id": "psyweb-mini", "evidence_version": "SCIENTIFIC_V3"}),
        encoding="utf-8",
    )
    return run


def test_snapshot_terminal_tick_fixed_while_runtime_appends(tmp_path: Path) -> None:
    run = _mini_run(tmp_path, ticks=4)
    snap = build_evidence_snapshot(run, run_id="psyweb-mini", job_id="j1", source="current")
    assert snap["schema"] == SNAP_SCHEMA
    term = snap["snapshot_terminal_tick"]
    assert term == 3
    # Append newer complete records (runtime continues).
    with (run / "scientific_spine.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"tick": 99, "schema": "scientific_spine", "agents": {}}) + "\n")
        f.write(json.dumps({"tick": 100, "schema": "scientific_spine", "agents": {}}) + "\n")
    # Snapshot boundary unchanged.
    assert snap["snapshot_terminal_tick"] == term
    ev = RunEvidence(run, snapshot=snap)
    ticks = [r["tick"] for r in ev.iter_spine() if "tick" in r]
    assert max(ticks) == term
    assert 99 not in ticks and 100 not in ticks
    ev.close()


def test_appended_and_partial_records_excluded(tmp_path: Path) -> None:
    run = _mini_run(tmp_path, ticks=3)
    spine = run / "scientific_spine.jsonl"
    # Append partial final record (no newline).
    with spine.open("ab") as f:
        f.write(b'{"tick": 50, "partial": tru')
    end = last_complete_jsonl_byte_end(spine)
    assert end < spine.stat().st_size
    snap = build_evidence_snapshot(run, run_id="psyweb-mini", job_id="j2")
    assert snap["files"]["scientific_spine.jsonl"]["truncated_partial_tail"] is True
    assert snap["files"]["scientific_spine.jsonl"]["byte_end"] == end
    ev = RunEvidence(run, snapshot=snap)
    ticks = [r["tick"] for r in ev.iter_spine()]
    assert 50 not in ticks
    assert max(ticks) == 2
    # Complete append after snapshot must still be excluded.
    with spine.open("ab") as f:
        f.write(b'e}\n')  # completes prior garbage — still past byte_end
        f.write(json.dumps({"tick": 77}).encode() + b"\n")
    ticks2 = [r["tick"] for r in RunEvidence(run, snapshot=snap).iter_spine()]
    assert 77 not in ticks2
    assert max(ticks2) == 2


def test_progress_monotonic_and_heartbeat_distinct(tmp_path: Path) -> None:
    out = tmp_path / "job"
    out.mkdir()
    path = out / "progress.json"
    t0 = time.perf_counter()
    state = {
        "job_id": "j3",
        "phase": "BUILD_SUMMARIES",
        "state": "RUNNING",
        "status": "RUNNING",
        "started_at": "2026-01-01T00:00:00+00:00",
        "completed_units": 0,
        "total_units": 100,
        "percent": 0.0,
        "recent_log": [],
    }
    rep = ProgressReporter(out_dir=out, state=state, progress_path=path, t0=t0)
    try:
        rep.emit("BUILD_SUMMARIES", n=10, total=100, status_text="start", operation="op_a")
        p1 = json.loads(path.read_text(encoding="utf-8"))
        lp1 = p1["last_progress_at"]
        hb1 = p1["worker_heartbeat_at"]
        assert p1["schema"] == PROGRESS_SCHEMA
        assert p1["phase_processed"] == 10
        time.sleep(2.2)  # allow heartbeat tick without meaningful progress
        p2 = json.loads(path.read_text(encoding="utf-8"))
        assert p2["last_progress_at"] == lp1
        assert p2["worker_heartbeat_at"] >= hb1 or p2["updated_at"] >= hb1
        assert p2["worker_heartbeat_at"] != p2["last_progress_at"] or p2["updated_at"] != lp1
        rep.emit("BUILD_SUMMARIES", n=20, total=100, status_text="more", operation="op_b")
        p3 = json.loads(path.read_text(encoding="utf-8"))
        assert p3["phase_processed"] == 20
        assert p3["phase_processed"] >= p1["phase_processed"]
        assert p3["phase_processed"] <= p3["phase_total"]
        assert p3["last_progress_at"] >= lp1
        # Flood log — must stay bounded.
        for i in range(LOG_BOUND + 20):
            rep.log(f"milestone {i}")
        p4 = json.loads(path.read_text(encoding="utf-8"))
        assert len(p4["recent_log"]) <= LOG_BOUND
        for entry in p4["recent_log"]:
            assert "/home/" not in str(entry.get("message") or "") or "…" in str(entry.get("message") or "")
    finally:
        rep.stop()


def test_nested_subop_does_not_regress_phase_processed(tmp_path: Path) -> None:
    out = tmp_path / "job_nested"
    out.mkdir()
    path = out / "progress.json"
    state = {
        "job_id": "jn",
        "state": "RUNNING",
        "status": "RUNNING",
        "recent_log": [],
        "percent": 0,
        "snapshot_record_count": 500,
    }
    rep = ProgressReporter(out_dir=out, state=state, progress_path=path, t0=time.perf_counter())
    try:
        rep.emit("BUILD_SUMMARIES", n=41, total=500, operation="contrasts")
        rep.emit("BUILD_SUMMARIES", n=1, total=1, operation="o5_temporal_alignment")
        d = json.loads(path.read_text(encoding="utf-8"))
        assert d["phase_processed"] >= 41
        assert d["phase_total"] >= d["phase_processed"]
        assert d["overall_processed"] >= 41
    finally:
        rep.stop()


def test_phase_index_monotonic_across_emits(tmp_path: Path) -> None:
    out = tmp_path / "job2"
    out.mkdir()
    path = out / "progress.json"
    state = {"job_id": "j4", "state": "RUNNING", "status": "RUNNING", "recent_log": [], "percent": 0}
    rep = ProgressReporter(out_dir=out, state=state, progress_path=path, t0=time.perf_counter())
    try:
        idxs = []
        for ph in ("LOAD_AND_VALIDATE", "BUILD_TICK_STORIES", "BUILD_SUMMARIES", "RENDER_EXPORT_PAYLOADS"):
            rep.emit(ph, n=1, total=10)
            idxs.append(json.loads(path.read_text())["phase_index"])
        assert idxs == sorted(idxs)
    finally:
        rep.stop()


def test_analyzer_endpoints_do_not_mutate_runtime_strings() -> None:
    """Static guard: analysis job routes must not call step/reset/apply."""
    server = Path("mechanistic_mind/ui/psy_observer_web/server.py").read_text(encoding="utf-8")
    start = server.index("def analysis_jobs_list")
    end = server.index("@app.post(\"/api/analysis/save\")")
    body = server[start:end]
    for banned in ("runtime.step(", "apply_experiment(", "create_scientific"):
        assert banned not in body
    assert "mutates_runtime\": False" in body or "mutates_runtime\":False" in body.replace(" ", "")


def test_write_progress_schema_fields(tmp_path: Path) -> None:
    p = tmp_path / "progress.json"
    write_progress(
        p,
        {
            "job_id": "x",
            "phase": "AGGREGATING",
            "state": "RUNNING",
            "completed_units": 3,
            "total_units": 9,
            "status_text": "Building summaries",
            "recent_log": [{"ts": "t", "message": "hi"}],
        },
    )
    d = json.loads(p.read_text(encoding="utf-8"))
    assert d["schema"] == PROGRESS_SCHEMA
    assert d["phase"] == "BUILD_SUMMARIES"
    assert d["phase_id"] == "BUILD_SUMMARIES"
    assert d["phase_processed"] == 3
    assert d["overall_total"] == 9
    assert "updated_at" in d
    assert "worker_heartbeat_at" in d
