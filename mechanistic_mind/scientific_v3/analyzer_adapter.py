"""Minimal Analyzer adapter — SCIENTIFIC_V3 CORE RECONSTRUCTION section only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .api import RunEvidence


SECTION_TITLE = "SCIENTIFIC_V3 CORE RECONSTRUCTION"


def build_v3_core_reconstruction(run_dir: str | Path) -> dict[str, Any]:
    run_dir = Path(run_dir)
    version = RunEvidence.detect_evidence_version(run_dir)
    if version != "SCIENTIFIC_V3":
        return {
            "section": SECTION_TITLE,
            "evidence_version": version,
            "status": "NOT_RECORDED",
            "note": "No SCIENTIFIC_V3 CORE package in this run directory.",
        }
    ev = RunEvidence(run_dir)
    summary = ev.reconstruction_summary()
    cov = (summary.get("coverage") or {}).get("dimensions") or {}
    expected = int(summary.get("ticks_expected_autonomous") or 0)
    complete = int(summary.get("complete_odmc_chains") or 0)
    incomplete = max(0, expected - complete)
    pct = round(100.0 * complete / expected, 1) if expected else 0.0
    identity = ev.identity_map or {}
    tmin = tmax = None
    for s in ev.iter_spine():
        if s.get("decision_id") is None:
            continue
        try:
            t = int(s["tick"])
        except (KeyError, TypeError, ValueError):
            continue
        tmin = t if tmin is None else min(tmin, t)
        tmax = t if tmax is None else max(tmax, t)
    tick_range = [tmin, tmax] if tmin is not None else None
    ev.close()
    return {
        "section": SECTION_TITLE,
        "evidence_version": "SCIENTIFIC_V3",
        "status": "AVAILABLE",
        "schema_version": summary.get("schema_version"),
        "evidence_tier": summary.get("evidence_tier"),
        "identity_coverage": cov.get("identity", "NOT_RECORDED"),
        "observation_coverage": cov.get("observation", "NOT_RECORDED"),
        "decision_coverage": cov.get("decision", "NOT_RECORDED"),
        "motor_coverage": cov.get("composite_motor", "NOT_RECORDED"),
        "consequence_coverage": cov.get("consequence", "NOT_RECORDED"),
        "ticks_expected": expected,
        "observation_receipts": summary.get("observation_receipts"),
        "decision_receipts": summary.get("decision_receipts"),
        "motor_receipts": summary.get("motor_receipts"),
        "consequence_receipts": summary.get("consequence_receipts"),
        "complete_odmc_chains": summary.get("complete_odmc_over_expected"),
        "complete_odmc_count": complete,
        "incomplete_odmc_chains": incomplete,
        "chain_completeness_pct": pct,
        "tick_range": tick_range,
        "broken_chains_by_reason": summary.get("broken_chains_by_reason"),
        "health": summary.get("health"),
        "identity_bodies": summary.get("identity_bodies"),
        "identity_mapping": identity.get("bodies") or [],
    }


def write_v3_core_reconstruction(run_dir: str | Path, output: str | Path | None = None) -> Path:
    run_dir = Path(run_dir)
    payload = build_v3_core_reconstruction(run_dir)
    out = Path(output) if output else (run_dir / "scientific_v3_core_reconstruction.json")
    out.write_text(json.dumps(payload, indent=2, default=str))
    txt = run_dir / "SCIENTIFIC_V3_CORE_RECONSTRUCTION.txt"
    lines = [SECTION_TITLE, "=" * len(SECTION_TITLE)]
    for k, v in payload.items():
        if k == "section":
            continue
        lines.append(f"{k}: {v}")
    txt.write_text("\n".join(lines) + "\n")
    return out


def format_reconstruction_text(payload: dict[str, Any]) -> str:
    lines = [payload.get("section", SECTION_TITLE), ""]
    for k, v in payload.items():
        if k == "section":
            continue
        lines.append(f"{k}: {v}")
    return "\n".join(lines) + "\n"
