"""Deterministic re-render of complete Markdown/JSON from a completed Analyzer job.

Does not replay physics or recompute TickStories.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .export_bundle import write_validated_export
from .tick_normalize import normalize_story_tick


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_job_payload(job_dir: Path) -> dict[str, Any]:
    job_dir = Path(job_dir)
    http = _load_json(job_dir / "analysis_http_summary.json")
    behavioral = _load_json(job_dir / "analysis_behavioral_summary.json")
    if not http and not behavioral:
        raise FileNotFoundError(f"No analysis summary JSON in {job_dir}")

    payload: dict[str, Any] = dict(behavioral)
    payload.update(http)  # HTTP compact is the live export authority for identity/psc/layers

    # Prefer richer structured models from behavioral summary when HTTP omitted them.
    for key in (
        "signal_conditioned_sensorimotor_selection",
        "historical_sensorimotor_selection",
        "sensorimotor_report_text",
        "what_happened",
        "beta31_vision_report_text",
        "signal_conditioned_report_text",
        "volumetric_physical_causal_report_text",
        "historical_sensorimotor_selection_report_text",
        "development_fixture_section",
    ):
        if payload.get(key) in (None, "", [], {}) and behavioral.get(key) not in (None, "", [], {}):
            payload[key] = behavioral[key]
    if payload.get("volumetric_physical_causal_reconstruction") in (None, {}, []) and behavioral.get(
        "volumetric_physical_causal_reconstruction"
    ):
        payload["volumetric_physical_causal_reconstruction"] = behavioral[
            "volumetric_physical_causal_reconstruction"
        ]
    if payload.get("episode_counts") in (None, {}) and behavioral.get("episode_counts"):
        payload["episode_counts"] = behavioral["episode_counts"]

    progress = _load_json(job_dir / "progress.json")
    elapsed = progress.get("elapsed_s")
    if elapsed is None:
        elapsed = progress.get("elapsed_seconds")
    if elapsed is not None:
        payload["job_elapsed_s"] = float(elapsed)
        payload["elapsed_source"] = "job_progress"
    elif payload.get("elapsed_s") is not None:
        payload["elapsed_source"] = "analyzer_pipeline"

    vpc = payload.get("volumetric_physical_causal_reconstruction")
    if isinstance(vpc, dict) and isinstance(vpc.get("sample_story"), dict):
        t = normalize_story_tick(vpc["sample_story"])
        if t is not None:
            vpc = dict(vpc)
            ss = dict(vpc["sample_story"])
            ss["tick"] = t
            vpc["sample_story"] = ss
            payload["volumetric_physical_causal_reconstruction"] = vpc

    payload["_job_dir"] = str(job_dir)
    if not payload.get("signal_context") and payload.get("signal_conditioned_sensorimotor_selection"):
        payload["signal_context"] = payload["signal_conditioned_sensorimotor_selection"]
    return payload


def rerender_job(job_dir: Path, out_dir: Path | None = None) -> dict[str, Any]:
    job_dir = Path(job_dir)
    out_dir = Path(out_dir) if out_dir else job_dir
    payload = load_job_payload(job_dir)
    artifacts = {
        "analysis_tick_stories.jsonl": str(job_dir / "analysis_tick_stories.jsonl"),
    }
    return write_validated_export(out_dir, payload, artifacts=artifacts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Re-render complete Analyzer Markdown/JSON from a completed job")
    p.add_argument("--job-dir", required=True)
    p.add_argument("--out-dir", default=None)
    args = p.parse_args(argv)
    result = rerender_job(Path(args.job_dir), Path(args.out_dir) if args.out_dir else None)
    print(json.dumps({
        "md_path": result["md_path"],
        "json_path": result["json_path"],
        "bytes": result["bytes"],
        "lines": result["lines"],
        "markdown_sha256": result["markdown_sha256"],
        "markdown_body_hash": result["markdown_body_hash"],
        "validation_status": result["validation"]["status"],
        "error_count": result["validation"]["error_count"],
        "warning_count": result["validation"]["warning_count"],
        "errors": result["validation"]["errors"],
        "warnings": result["validation"]["warnings"],
    }, indent=2))
    return 0 if result["validation"]["error_count"] == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
