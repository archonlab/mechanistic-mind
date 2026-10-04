"""Analyzer section: RADIUS-AWARE FACE-SWEEP EVENTS.

Ingests researcher-only RADIUS_AWARE_FACE_SWEEP receipts from V3 capture consequences
(event_refs of kind ``radius_aware_face_sweep``), deduplicated by ``application_key``.
Never emits physics.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVENT_REF_KIND = "radius_aware_face_sweep"

COGNITION_FORBIDDEN_TOKENS = (
    "RADIUS_AWARE_FACE_SWEEP",
    "RADIUS_FACE_BARRIER",
    "FACE_SWEEP",
    "PE_AUTHORITY",
    "SES_DDA",
    "GEOMETRY_PROFILE",
    "earliest_hit",
    "candidate_count",
    "blocking_proposal",
    "starting_penetration",
    "face_sweep_work_delta",
    "face_sweep_pe_delta",
    "application_key",
    "HARD_CAP_CONSERVATIVE_BLOCK",
    "SOFT_CAP_WARNING",
)


def dedup_receipts(receipts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for r in receipts:
        if not isinstance(r, dict):
            continue
        key = str(r.get("application_key") or r.get("dedup_key") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        out.append(r)
    return out


def summarize_radius_aware_face_sweep_events(
    events: list[dict[str, Any]] | None,
    *,
    raw_events: list[dict[str, Any]] | None = None,
    observation_leaks: list[str] | None = None,
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        ANALYZER_SECTION,
        BANNER,
        PE_AUTHORITY_SES_DDA,
        PROFILE_VERSION,
        GEOMETRY_PROFILE,
    )

    rows = [e for e in (events or []) if isinstance(e, dict)]
    raw = [e for e in (raw_events if raw_events is not None else rows) if isinstance(e, dict)]
    accepted = 0
    blocked = 0
    radius_only = 0
    centre_and_radius = 0
    outward = 0
    deeper = 0
    soft_cap = 0
    hard_cap = 0
    first = None
    last = None
    entities: dict[str, int] = {}
    for r in rows:
        if r.get("ses_accepted"):
            accepted += 1
        else:
            blocked += 1
        src = str(r.get("evidence_source") or "")
        if src == "RADIUS_ONLY":
            radius_only += 1
        elif src == "CENTRE_AND_RADIUS":
            centre_and_radius += 1
        pen = (r.get("starting_penetration") or {}) if isinstance(r.get("starting_penetration"), dict) else {}
        disp = str(pen.get("disposition") or "")
        if disp == "OUTWARD_ALLOWED":
            outward += 1
        elif disp == "DEEPER_BLOCKED":
            deeper += 1
        st = str(r.get("evaluation_status") or "")
        if st == "SOFT_CAP_WARNING":
            soft_cap += 1
        if st == "HARD_CAP_CONSERVATIVE_BLOCK":
            hard_cap += 1
        ek = f"{r.get('entity_kind')}:{r.get('entity_id')}"
        entities[ek] = int(entities.get(ek, 0)) + 1
        if first is None:
            first = r
        last = r

    evidence_complete = len(raw) == 0 or len(rows) >= len(raw)
    return {
        "mechanism": "radius_aware_face_sweep",
        "analyzer_section": ANALYZER_SECTION,
        "banner": BANNER,
        "profile_version": PROFILE_VERSION,
        "geometry_profile": GEOMETRY_PROFILE,
        "pe_authority": PE_AUTHORITY_SES_DDA,
        "face_sweep_work_delta": 0.0,
        "face_sweep_pe_delta": 0.0,
        "attempts_evaluated": len(rows),
        "accepted": accepted,
        "blocked": blocked,
        "radius_only_blocks": radius_only,
        "centre_and_radius_blocks": centre_and_radius,
        "starting_penetration_outward": outward,
        "starting_penetration_deeper": deeper,
        "soft_cap_anomalies": soft_cap,
        "hard_cap_anomalies": hard_cap,
        "first_event": first,
        "last_event": last,
        "entities": entities,
        "evidence_coverage": "COMPLETE" if evidence_complete else "PARTIAL",
        "raw_count": len(raw),
        "dedup_count": len(rows),
        "observation_leaks": list(observation_leaks or []),
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_radius_aware_face_sweep_section(s: dict[str, Any]) -> str:
    lines = [
        str(s.get("analyzer_section") or "RADIUS-AWARE FACE-SWEEP EVENTS"),
        f"profile={s.get('profile_version')} · geometry={s.get('geometry_profile')}",
        f"attempts={s.get('attempts_evaluated')} · accepted={s.get('accepted')} · blocked={s.get('blocked')}",
        f"radius_only_blocks={s.get('radius_only_blocks')} · centre_and_radius={s.get('centre_and_radius_blocks')}",
        f"outward={s.get('starting_penetration_outward')} · deeper={s.get('starting_penetration_deeper')}",
        f"soft_cap={s.get('soft_cap_anomalies')} · hard_cap={s.get('hard_cap_anomalies')}",
        f"PE authority={s.get('pe_authority')} · face_sweep_work/PE=0 · coverage={s.get('evidence_coverage')}",
    ]
    last = s.get("last_event") or {}
    if last:
        lines.append(
            f"last: {last.get('entity_kind')}:{last.get('entity_id')} "
            f"R={last.get('physical_radius')} reason={last.get('ses_block_reason')} "
            f"src={last.get('evidence_source')}"
        )
    return "\n".join(lines)


def radius_aware_face_sweep_raw_receipts_from_consequences(
    run_dir: str | Path,
) -> list[dict[str, Any]]:
    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("**/consequences*.jsonl")) + sorted(root.glob("**/*consequence*.jsonl")):
        try:
            with path.open() as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    refs = row.get("event_refs") if isinstance(row, dict) else None
                    if not isinstance(refs, list):
                        continue
                    for ref in refs:
                        if isinstance(ref, dict) and str(ref.get("kind")) == EVENT_REF_KIND:
                            out.append(ref)
        except OSError:
            continue
    return out


def radius_aware_face_sweep_receipts_from_consequences(
    run_dir: str | Path,
) -> list[dict[str, Any]]:
    return dedup_receipts(radius_aware_face_sweep_raw_receipts_from_consequences(run_dir))


def summarize_radius_aware_face_sweep_run(run_dir: str | Path) -> dict[str, Any]:
    raw = radius_aware_face_sweep_raw_receipts_from_consequences(run_dir)
    return summarize_radius_aware_face_sweep_events(
        dedup_receipts(raw), raw_events=raw,
    )


def summarize_radius_aware_face_sweep(world: Any) -> dict[str, Any] | None:
    from mechanistic_mind.physical_system.radius_aware_face_sweep import state_of

    st = state_of(world)
    if st is None:
        return None
    history = list(st.history or [])
    return summarize_radius_aware_face_sweep_events(history)
