"""P6 Analyzer streaming/reuse — contract tests (no long Analyzer jobs)."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
from mechanistic_mind.scientific_v3.analyzer_next.job import PROGRESS_PHASES


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "p6_analyzer_streaming_and_reuse_optimization_v1"


def test_01_progress_phases_unchanged():
    assert "DISCOVER_EVIDENCE" in PROGRESS_PHASES
    assert "NORMALIZE_RECORDS" in PROGRESS_PHASES
    assert "BUILD_TICK_STORIES" in PROGRESS_PHASES
    assert "RECONSTRUCT_PHYSICAL_CAUSALITY" in PROGRESS_PHASES
    assert "BUILD_SUMMARIES" in PROGRESS_PHASES
    assert "RENDER_EXPORT_PAYLOADS" in PROGRESS_PHASES
    assert "COMPLETE" in PROGRESS_PHASES


def test_02_artifacts_present():
    for name in (
        "PRE_OPTIMIZATION_PROFILE.md",
        "IMPLEMENTATION_DECISION.md",
        "EQUIVALENCE_REPORT.md",
        "BENCHMARK_RESULTS.json",
        "FINAL_REPORT.md",
        "return_block.json",
    ):
        assert (OUT / name).is_file(), name


def test_03_verdict_c_no_optimization():
    ret = json.loads((OUT / "return_block.json").read_text())
    assert ret["VERDICT"].startswith("C.")
    assert ret["OPTIMIZATION_IMPLEMENTED"] is False
    assert ret["FIRST_MEASURED_BOTTLENECK"] == "NO_MEANINGFUL_BOTTLENECK"
    assert ret["PROVISIONAL_TARGET_MET"] is True
    assert ret["TOTAL_SIMULATED_TICKS"] == 0


def test_04_benchmark_profiles_cover_required_fixtures():
    bench = json.loads((OUT / "BENCHMARK_RESULTS.json").read_text())
    profiles = bench["profiles"]
    for key in ("SAVED_2K_V3", "SAVED_BETA4_MAX80", "SAVED_BETA4_MAX200", "LEGACY_V2_ONLY", "MALFORMED"):
        assert key in profiles
    assert profiles["SAVED_2K_V3"]["total_s"]["p95"] < 120.0
    assert profiles["SAVED_BETA4_MAX200"]["total_s"]["p95"] < 120.0


def test_05_selector_untouched():
    assert len(public_model_selector_entries()) == 2


def test_06_docs_exist():
    assert (ROOT / "docs" / "ACANTHOSTEGA_P6_ANALYZER_STREAMING_AND_REUSE_OPTIMIZATION_V1.md").is_file()
