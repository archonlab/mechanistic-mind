"""Isolated Analyzer job: subprocess worker + progress file.

Never writes into the source run directory. Observer remains a separate process.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PHASES = (
    "QUEUED",
    "READING",
    "RECONSTRUCTING",
    "EPISODES",
    "AGGREGATING",
    "WRITING",
    "COMPLETE",
    "FAILED",
    "CANCELLED",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_progress(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    payload.setdefault("updated_at", _now())
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def cancel_requested(out_dir: Path) -> bool:
    return (out_dir / "CANCEL").is_file()


def compact_http_result(payload: dict[str, Any], artifacts: dict[str, str] | None = None) -> dict[str, Any]:
    """Summary suitable for HTTP — no TickStory lists, no scientific_rows."""
    hist = payload.get("canonical_history") or {}
    unique = int(hist.get("unique_simulation_ticks") or payload.get("unique_simulation_ticks") or 0)
    stories_n = int(payload.get("tick_stories_count") or 0)
    consumed = unique > 0 and stories_n > 0
    tmin, tmax = hist.get("tick_min"), hist.get("tick_max")
    rng = payload.get("scientific_tick_range") or hist.get("scientific_tick_range") or [tmin, tmax]
    keep = (
        "section", "status", "evidence_version", "run_id", "analysis_cutoff_tick",
        "tick_stories_count", "complete_odmc_count", "complete_odmc",
        "unique_simulation_ticks", "scientific_tick_range", "canonical_history",
        "scientific_v3_core",
        "world_size", "join_summary", "legacy_scenario_selected_count",
        "decision_receipts", "agent_summaries", "episode_counts",
        "selected_episodes", "interesting_ticks", "open_questions",
        "relationship_graph_summary", "what_happened",
        "sensorimotor_steps_count", "motor_reversals_count",
        "sensorimotor_trend_reversals_count", "elapsed_s",
        "report_text", "sensorimotor_report_text",
        "action_conditioned_model_report_text",
        "historical_sensorimotor_selection_report_text",
        "signal_conditioned_report_text", "full_embodied_report_text",
        "beta31_vision_report_text", "beta31_vision_publication",
        "analyzer_version", "publication_gate",
    )
    out = {k: payload.get(k) for k in keep if k in payload}
    br_keys = (
        "section", "status", "evidence_version", "run_id", "analysis_cutoff_tick",
        "tick_stories_count", "complete_odmc_count", "complete_odmc",
        "episode_counts", "agent_summaries", "report_text",
        "sensorimotor_report_text", "action_conditioned_model_report_text",
        "selected_episodes", "join_summary", "canonical_history",
    )
    out["behavioral_reconstruction"] = {k: payload.get(k) for k in br_keys if k in payload}
    out["artifacts"] = artifacts or {}
    out["scientific_rows"] = []
    out["timeline"] = []
    out["events"] = []
    out["unique_simulation_ticks"] = unique
    out["scientific_tick_range"] = rng
    out["coverage"] = "FULL" if consumed else "INSUFFICIENT"
    out["complete_tick_level_reanalysis"] = bool(consumed)
    out["evidence_counts"] = {
        "tick_stories": stories_n,
        "scientific_rows": stories_n,
        "unique_simulation_ticks": unique,
        "events": int((payload.get("join_summary") or {}).get("event_ticks_indexed") or 0),
    }
    out["analyzer_version"] = payload.get("analyzer_version") or "1.2.0"
    vis = payload.get("beta31_vision") or {}
    out["beta31_vision_summary"] = (vis.get("vision_summary") if isinstance(vis, dict) else None)
    return out


def run_job(*, run_dir: Path, out_dir: Path, max_tick: int | None = None) -> dict[str, Any]:
    from mechanistic_mind.scientific_v3.analyzer_next.pipeline import build_behavioral_reconstruction

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    progress_path = out_dir / "progress.json"
    t0 = time.perf_counter()
    bytes_total = 0
    for name in (
        "scientific_spine.jsonl",
        "scientific_decisions.jsonl",
        "scientific_timeline.jsonl",
        "scientific_events.jsonl",
        "scientific_observations.jsonl",
        "scientific_motors.jsonl",
        "scientific_consequences.jsonl",
    ):
        p = Path(run_dir) / name
        if p.is_file():
            bytes_total += p.stat().st_size

    state: dict[str, Any] = {
        "phase": "READING",
        "status": "RUNNING",
        "run_dir": str(run_dir),
        "out_dir": str(out_dir),
        "records_processed": 0,
        "ticks_reconstructed": 0,
        "last_tick_processed": None,
        "bytes_total": bytes_total,
        "elapsed_s": 0.0,
        "error": None,
        "started_at": _now(),
    }
    write_progress(progress_path, state)
    if cancel_requested(out_dir):
        state["phase"] = "CANCELLED"
        state["status"] = "CANCELLED"
        write_progress(progress_path, state)
        return state

    def on_progress(phase: str, n: int, tick: int) -> None:
        if cancel_requested(out_dir):
            raise KeyboardInterrupt("CANCELLED")
        state["phase"] = phase
        state["ticks_reconstructed"] = int(n)
        state["records_processed"] = int(n)
        state["last_tick_processed"] = tick
        state["elapsed_s"] = round(time.perf_counter() - t0, 3)
        write_progress(progress_path, state)

    try:
        payload = build_behavioral_reconstruction(
            run_dir,
            max_tick=max_tick,
            write_artifacts=True,
            artifact_dir=out_dir,
            on_progress=on_progress,
        )
        compact = compact_http_result(payload)
        (out_dir / "analysis_http_summary.json").write_text(
            json.dumps(compact, indent=2, default=str), encoding="utf-8"
        )
        state["phase"] = "COMPLETE"
        state["status"] = "COMPLETE"
        state["elapsed_s"] = round(time.perf_counter() - t0, 3)
        state["tick_stories_count"] = payload.get("tick_stories_count")
        state["complete_odmc"] = payload.get("complete_odmc")
        state["episode_counts"] = payload.get("episode_counts")
        state["analysis_cutoff_tick"] = payload.get("analysis_cutoff_tick")
        write_progress(progress_path, state)
        return state
    except KeyboardInterrupt:
        state["phase"] = "CANCELLED"
        state["status"] = "CANCELLED"
        state["elapsed_s"] = round(time.perf_counter() - t0, 3)
        write_progress(progress_path, state)
        return state
    except Exception as exc:
        state["phase"] = "FAILED"
        state["status"] = "FAILED"
        state["error"] = str(exc)
        state["traceback"] = traceback.format_exc()
        state["elapsed_s"] = round(time.perf_counter() - t0, 3)
        write_progress(progress_path, state)
        (out_dir / "FAILED").write_text(str(exc), encoding="utf-8")
        return state


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--max-tick", type=int, default=None)
    args = p.parse_args(argv)
    st = run_job(run_dir=Path(args.run_dir), out_dir=Path(args.out_dir), max_tick=args.max_tick)
    return 0 if st.get("status") == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
