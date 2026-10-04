"""Analyzer section: RESOURCE OBJECT PAIR IMPACT ACOUSTICS."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SECTION_TITLE = "RESOURCE OBJECT PAIR IMPACT ACOUSTICS"
SCHEMA_VERSION = "RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC_SUMMARY_V1"
MEASUREMENT = "RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC_MEASUREMENT"
EMISSION = "RESOURCE_OBJECT_PAIR_IMPACT_ACOUSTIC_EMISSION"
RECEPTION = "LOCAL_PHYSICAL_SIGNAL_RECEPTION"

EXPLICIT = {
    "MATERIAL_DEPENDENT_ACOUSTICS": "NOT_IMPLEMENTED",
    "SEMANTIC_SOUND_CLASSES": "NOT_IMPLEMENTED",
    "MECHANICAL_ENERGY_WITHDRAWAL": "FALSE_V1_DIAGNOSTIC_ONLY",
    "MULTI_CONTACT_SOUND": "SILENT_BY_POLICY",
}


def _dedup(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    seen, out = set(), []
    for r in rows:
        k = r.get(key)
        if k in seen:
            continue
        seen.add(k)
        out.append(r)
    return out


def summarize_resource_object_pair_impact_acoustics(
    impact_events: list[dict[str, Any]] | None,
    signal_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ms = _dedup(
        [
            e
            for e in impact_events or []
            if isinstance(e, dict) and e.get("receipt_kind") == MEASUREMENT
        ],
        "measurement_id",
    )
    ems = _dedup(
        [
            e
            for e in impact_events or []
            if isinstance(e, dict) and e.get("receipt_kind") == EMISSION
        ],
        "emission_id",
    )
    recs = _dedup(
        [
            e
            for e in signal_events or []
            if isinstance(e, dict) and e.get("receipt_kind") == RECEPTION
        ],
        "reception_id",
    )
    em_ids = {e.get("emission_id") for e in ems}
    linked = [r for r in recs if r.get("emission_id") in em_ids and r.get("accepted")]
    silent = [m for m in ms if not m.get("emitted")]
    no_diss = [m for m in silent if m.get("silence_reason") in ("ZERO_DISSIPATION", "NO_DISSIPATED_ENERGY")]
    below = [m for m in silent if m.get("silence_reason") in ("BELOW_IMPULSE_THRESHOLD", "IMPULSE_BELOW_EPSILON")]
    unresolved = [m for m in silent if m.get("silence_reason") == "UNRESOLVED_PHYSICAL_RESPONSE"]
    return {
        "schema_version": SCHEMA_VERSION,
        "section": SECTION_TITLE,
        "event_count": len(ms) + len(ems),
        "measurements": len(ms),
        "emissions_created": len(ems),
        "silent_measurements": len(silent),
        "silent_no_dissipation": len(no_diss),
        "silent_below_epsilon": len(below),
        "silent_unresolved_multi_contact": len(unresolved),
        "linked_receptions": len(linked),
        "mechanical_energy_withdrawn": False,
        "explicit_not_implemented": dict(EXPLICIT),
        "researcher_only": True,
        "agent_accessible": False,
    }


def format_resource_object_pair_impact_acoustics_section(s: dict[str, Any]) -> str:
    lines = [
        SECTION_TITLE,
        (
            "measurements={m} emissions={e} silent={s} unresolved={u} linked_receptions={l}".format(
                m=s.get("measurements"),
                e=s.get("emissions_created"),
                s=s.get("silent_measurements"),
                u=s.get("silent_unresolved_multi_contact"),
                l=s.get("linked_receptions"),
            )
        ),
        "mechanical_energy_withdrawn=false · dissipation-only · neutral broadband",
        "NOT: material timbre / multi-contact sound / semantic classes",
    ]
    return "\n".join(lines)


def resource_object_pair_impact_acoustic_receipts_from_consequences(
    run_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return (impact_events, signal_events) from consequence JSONL if present."""
    impact: list[dict[str, Any]] = []
    signals: list[dict[str, Any]] = []
    run_dir = Path(run_dir)
    for name in ("consequences.jsonl", "events.jsonl", "receipts.jsonl"):
        path = run_dir / name
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            payload = row.get("payload") if isinstance(row, dict) else None
            kind = str((payload or row).get("receipt_kind") or row.get("kind") or "")
            src = payload if isinstance(payload, dict) else row
            if kind in (MEASUREMENT, EMISSION) or "resource_object_pair_impact" in kind.lower():
                impact.append(src if isinstance(src, dict) else row)
            if kind == RECEPTION:
                signals.append(src if isinstance(src, dict) else row)
            # Also pick capture event_refs style
            if isinstance(row, dict) and str(row.get("kind") or "") == "resource_object_pair_impact_acoustics":
                impact.append(row)
    return impact, signals
