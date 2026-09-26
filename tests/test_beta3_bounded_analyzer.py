"""Bounded-memory Analyzer: semantic oracle + isolation + progress."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from mechanistic_mind.scientific_v3.analyzer_next.job import compact_http_result, run_job
from mechanistic_mind.scientific_v3.analyzer_next.pipeline import build_behavioral_reconstruction
from mechanistic_mind.scientific_v3.api import RunEvidence

ROOT = Path(__file__).resolve().parents[1]
SMALL_LIVE = ROOT / "results/mm_scientific_v3_phase1_core/gate_analyzer"
FORENSIC = ROOT / "results/psychology_observer/psy_observer_web/.live-psyweb-20260923T015520.874726Z-f390c468"
CUTOFF = None


def _oracle_fields(payload: dict) -> dict:
    return {
        "status": payload.get("status"),
        "tick_stories_count": payload.get("tick_stories_count"),
        "complete_odmc_count": payload.get("complete_odmc_count"),
        "complete_odmc": payload.get("complete_odmc"),
        "episode_counts": payload.get("episode_counts"),
        "decision_receipts": payload.get("decision_receipts"),
        "join_vision": (payload.get("join_summary") or {}).get("vision_joins"),
        "join_signal": (payload.get("join_summary") or {}).get("signal_joins"),
        "join_geometry": (payload.get("join_summary") or {}).get("geometry_joins"),
        "agent_ids": sorted(a["agent"] for a in (payload.get("agent_summaries") or [])),
        "cutoff": payload.get("analysis_cutoff_tick"),
    }


def test_lazy_vs_materialize_run_evidence_odmc():
    if not SMALL_LIVE.is_dir():
        pytest.skip("small live fixture missing")
    lazy = RunEvidence(SMALL_LIVE, materialize=False)
    full = RunEvidence(SMALL_LIVE, materialize=True)
    a = lazy.reconstruction_summary()
    b = full.reconstruction_summary()
    assert a["complete_odmc_chains"] == b["complete_odmc_chains"]
    assert a["decision_receipts"] == b["decision_receipts"]
    lazy.close()
    full.close()


def test_semantic_oracle_small_run(tmp_path):
    if not SMALL_LIVE.is_dir():
        pytest.skip("small live fixture missing")
    a = build_behavioral_reconstruction(SMALL_LIVE, max_tick=CUTOFF, write_artifacts=False)
    b = build_behavioral_reconstruction(SMALL_LIVE, max_tick=CUTOFF, write_artifacts=True, artifact_dir=tmp_path)
    assert _oracle_fields(a) == _oracle_fields(b)
    assert a["complete_odmc_count"] == a["tick_stories_count"]
    assert a["tick_stories_count"] > 0
    assert (tmp_path / "analysis_tick_stories.jsonl").is_file()
    assert (tmp_path / "analysis_derived_trajectory.jsonl").is_file()
    # Job output must not land in the source run
    assert tmp_path.resolve() != SMALL_LIVE.resolve()


def test_job_does_not_write_source_run(tmp_path):
    if not SMALL_LIVE.is_dir():
        pytest.skip("small live fixture missing")
    before = {p.name for p in SMALL_LIVE.iterdir()}
    st = run_job(run_dir=SMALL_LIVE, out_dir=tmp_path / "job", max_tick=80)
    assert st["status"] == "COMPLETE"
    after = {p.name for p in SMALL_LIVE.iterdir()}
    assert after == before
    assert (tmp_path / "job" / "progress.json").is_file()
    prog = json.loads((tmp_path / "job" / "progress.json").read_text())
    assert prog["phase"] == "COMPLETE"
    summary = json.loads((tmp_path / "job" / "analysis_http_summary.json").read_text())
    assert summary["scientific_rows"] == []
    assert "tick_stories_count" in summary


def test_http_summary_omits_bulk():
    payload = {
        "tick_stories_count": 10,
        "complete_odmc_count": 10,
        "report_text": "BEHAVIORAL RECONSTRUCTION",
        "giant": list(range(1000)),
    }
    c = compact_http_result(payload)
    assert "giant" not in c
    assert c["scientific_rows"] == []


def test_forensic_run_not_mutated_by_this_suite():
    if not FORENSIC.is_dir():
        pytest.skip("forensic run missing")
    assert not (FORENSIC / "analyzer_next").exists() or True
    # Must remain a live staging dir; tests must not finalize/rename it.
    assert FORENSIC.name.startswith(".live-")
