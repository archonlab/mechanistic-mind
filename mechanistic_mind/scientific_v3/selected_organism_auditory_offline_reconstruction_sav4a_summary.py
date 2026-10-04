"""Analyzer reconstruction for SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_SAV4A_V1."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system.selected_organism_auditory_offline_reconstruction_sav4a import (
    AUTHORITY,
    CAPABILITY,
    PHASES,
    PROFILE,
    SCHEMA,
    TITLE,
    WARNING,
    reconstruct_from_run_dir,
)


def summarize_sav4a_offline_reconstruction(
    run_dir: Path | str,
    *,
    preview_limit: int = 64,
) -> dict[str, Any]:
    """Run SAV4A over a saved package with genuine phase progress accounting."""
    progress_events: list[dict[str, Any]] = []

    def _cb(ev: dict[str, Any]) -> None:
        progress_events.append(dict(ev))

    payload = reconstruct_from_run_dir(
        run_dir, progress=_cb, preview_limit=preview_limit
    )
    # Phase summary: last event per phase with processed/total
    phase_summary: list[dict[str, Any]] = []
    last_by_phase: dict[str, dict[str, Any]] = {}
    for ev in progress_events:
        ph = str(ev.get("phase") or "")
        if ph:
            last_by_phase[ph] = ev
    for ph in PHASES:
        ev = last_by_phase.get(ph) or {}
        total = ev.get("total")
        processed = int(ev.get("processed") or 0)
        phase_summary.append(
            {
                "phase": ph,
                "processed": processed,
                "total": total,
                "indeterminate": total is None,
                "percent": (
                    100.0 * float(processed) / float(total)
                    if isinstance(total, (int, float)) and total > 0
                    else None
                ),
            }
        )

    payload["analyzer_progress"] = {
        "phases": phase_summary,
        "units": "records_or_files_per_phase",
        "fabricated_percent": False,
        "status": "COMPLETE",
    }
    payload["progress_events"] = progress_events
    payload["schema"] = SCHEMA
    payload["capability"] = CAPABILITY
    payload["profile"] = PROFILE
    payload["authority"] = AUTHORITY
    payload["title"] = TITLE
    payload["warning"] = WARNING
    return payload


def format_sav4a_section(summary: dict[str, Any]) -> str:
    prog = summary.get("analyzer_progress") or {}
    phases = prog.get("phases") or []
    lines = [
        f"## {TITLE}",
        f"Schema: {SCHEMA}",
        f"Profile: {PROFILE}",
        f"Authority: {AUTHORITY}",
        WARNING,
        (
            f"available={summary.get('available')} · records={summary.get('normalized_record_count')} · "
            f"schedule_items={summary.get('schedule_item_count')} · "
            f"schedule_available={summary.get('schedule_available')}"
        ),
        (
            f"authority_matrix={summary.get('authority_matrix')} · "
            f"gaps={summary.get('gap_count')} · dups={summary.get('duplicate_count')} · "
            f"conflicts={summary.get('conflict_count')}"
        ),
        (
            f"normalized_digest={summary.get('normalized_record_digest')} · "
            f"schedule_digest={summary.get('schedule_digest')}"
        ),
        "Causal chain: "
        + " → ".join(summary.get("causal_chain") or []),
        "Progress phases (genuine counts; no invented % when total unknown):",
    ]
    for p in phases:
        tot = p.get("total")
        if tot is None:
            lines.append(
                f"  - {p.get('phase')}: processed={p.get('processed')} (indeterminate)"
            )
        else:
            pct = p.get("percent")
            pct_s = f"{pct:.1f}%" if isinstance(pct, (int, float)) else "n/a"
            lines.append(
                f"  - {p.get('phase')}: {p.get('processed')}/{tot} ({pct_s})"
            )
    lines.append(
        "Limitations: " + ", ".join(summary.get("limitations") or [])
    )
    lines.append("")
    return "\n".join(lines)
