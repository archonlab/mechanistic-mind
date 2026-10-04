"""Analyzer section: SES RUNTIME TRANSITION CLASSIFICATIONS (G2C2).

Ingests researcher-only G2C2 receipts from V3 capture consequences (event_refs of kind
``ses_runtime_transition_classifier``), deduplicated by ``application_key``. Never emits.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

EVENT_REF_KIND = "ses_runtime_transition_classifier"

COGNITION_FORBIDDEN_TOKENS = (
    "SES_RUNTIME_TRANSITION",
    "SES_RUNTIME_CLASSIFIER",
    "PE_AUTHORITY",
    "SES_DDA",
    "SMOOTH_PATCH_TRAVERSAL",
    "MICRORELIEF_STEP",
    "LEDGE_BLOCK",
    "SUPPORT_DROP_LOS",
    "OCCUPANT_SUPPORT_RISE",
    "RADIUS_PARTIAL_CONTACT",
    "CLIFF_NZ_CUTOFF",
    "GEOMETRY_AMBIGUOUS",
    "classifier_version",
    "application_key",
    "proposed_destination",
    "realized_destination",
    "mutation_provenance",
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


def summarize_ses_runtime_transition_classifier_events(
    events: list[dict[str, Any]] | None,
    *,
    raw_events: list[dict[str, Any]] | None = None,
    observation_leaks: list[str] | None = None,
) -> dict[str, Any]:
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        ANALYZER_SECTION,
        BANNER,
        PE_AUTHORITY_SES_DDA,
        PRECEDENCE_ORDER,
        PROFILE_VERSION,
        TRANSITION_TAXONOMY,
    )

    rows = [e for e in (events or []) if isinstance(e, dict)]
    raw = [e for e in (raw_events if raw_events is not None else rows) if isinstance(e, dict)]
    by_class: dict[str, int] = {c: 0 for c in TRANSITION_TAXONOMY}
    accepted = 0
    blocked = 0
    first = None
    last = None
    entities: dict[str, int] = {}
    evidence_available = 0
    evidence_partial = 0
    for r in rows:
        cls = str(r.get("transition_class") or "GEOMETRY_AMBIGUOUS")
        by_class[cls] = int(by_class.get(cls, 0)) + 1
        if r.get("accepted"):
            accepted += 1
        if r.get("blocked") or (r.get("accepted") is False):
            blocked += 1
        ek = f"{r.get('entity_kind')}:{r.get('entity_id')}"
        entities[ek] = int(entities.get(ek, 0)) + 1
        if first is None:
            first = r
        last = r
        # Evidence coverage: continuous_height_delta / support heights may be NOT_AVAILABLE.
        cdelta = r.get("continuous_height_delta")
        if cdelta is None or cdelta == "NOT_AVAILABLE":
            evidence_partial += 1
        else:
            evidence_available += 1

    return {
        "mechanism": "ses_runtime_transition_classifier",
        "analyzer_section": ANALYZER_SECTION,
        "banner": BANNER,
        "profile_version": PROFILE_VERSION,
        "pe_authority": PE_AUTHORITY_SES_DDA,
        "classifier_controls_physics": False,
        "n_receipts": len(rows),
        "n_raw_receipts": len(raw),
        "n_duplicates_suppressed": max(0, len(raw) - len(rows)),
        "counts_by_class": by_class,
        "accepted": accepted,
        "blocked": blocked,
        "first_occurrence": first,
        "last_occurrence": last,
        "entities": dict(sorted(entities.items())),
        "precedence": list(PRECEDENCE_ORDER),
        "transition_taxonomy": list(TRANSITION_TAXONOMY),
        "evidence_coverage": {
            "continuous_height_available": evidence_available,
            "continuous_height_partial_or_unavailable": evidence_partial,
            "historical_completeness": "PARTIAL" if evidence_partial else ("COMPLETE" if rows else "EMPTY"),
            "note": "Do not imply historical completeness when evidence is partial.",
        },
        "observation_leaks": list(observation_leaks or []),
        "researcher_only": True,
    }


def format_ses_runtime_transition_classifier_section(s: dict[str, Any]) -> str:
    lines = [
        "SES RUNTIME TRANSITION CLASSIFICATIONS",
        f"PE AUTHORITY: {s.get('pe_authority')}",
        "CLASSIFICATION DOES NOT CONTROL PHYSICS",
        f"receipts={s.get('n_receipts', 0)} accepted={s.get('accepted', 0)} blocked={s.get('blocked', 0)}",
    ]
    counts = s.get("counts_by_class") or {}
    if any(counts.values()):
        parts = [f"{k}={v}" for k, v in counts.items() if v]
        lines.append("by_class: " + ", ".join(parts))
    cov = s.get("evidence_coverage") or {}
    lines.append(
        f"evidence: available={cov.get('continuous_height_available', 0)} "
        f"partial={cov.get('continuous_height_partial_or_unavailable', 0)} "
        f"completeness={cov.get('historical_completeness')}"
    )
    ents = s.get("entities") or {}
    if ents:
        lines.append("entities: " + ", ".join(f"{k}×{v}" for k, v in ents.items()))
    last = s.get("last_occurrence") or {}
    if last:
        lines.append(
            f"last: class={last.get('transition_class')} "
            f"accepted={last.get('accepted')} "
            f"origin={last.get('origin')} "
            f"proposed={last.get('proposed_destination')} "
            f"realized={last.get('realized_destination')}"
        )
    return "\n".join(lines)


def ses_runtime_transition_classifier_raw_receipts_from_consequences(
    run_dir: str | Path,
) -> list[dict[str, Any]]:
    run = Path(run_dir)
    path = run / "consequences.jsonl"
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            for ref in row.get("event_refs") or []:
                if isinstance(ref, dict) and ref.get("kind") == EVENT_REF_KIND:
                    out.append(ref)
    return out


def ses_runtime_transition_classifier_receipts_from_consequences(
    run_dir: str | Path,
) -> list[dict[str, Any]]:
    return dedup_receipts(ses_runtime_transition_classifier_raw_receipts_from_consequences(run_dir))


def summarize_ses_runtime_transition_classifier_run(run_dir: str | Path) -> dict[str, Any]:
    raw = ses_runtime_transition_classifier_raw_receipts_from_consequences(run_dir)
    return summarize_ses_runtime_transition_classifier_events(
        dedup_receipts(raw), raw_events=raw,
    )


def summarize_ses_runtime_transition_classifier(world: Any) -> dict[str, Any] | None:
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        state_of,
    )

    st = state_of(world)
    if st is None:
        return None
    history = list(getattr(st, "history", None) or [])
    return summarize_ses_runtime_transition_classifier_events(history)
