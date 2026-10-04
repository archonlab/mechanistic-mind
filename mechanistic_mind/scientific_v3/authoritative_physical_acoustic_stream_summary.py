"""Analyzer reconstruction for AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_V1."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def summarize_authoritative_physical_acoustic_stream(
    records: list[dict[str, Any]],
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = dict(meta or {})
    by_mech: dict[str, int] = {}
    timelines: list[dict[str, Any]] = []
    for r in records:
        if not isinstance(r, dict):
            continue
        mech = str(r.get("source_mechanism_id") or "UNKNOWN")
        by_mech[mech] = int(by_mech.get(mech, 0)) + 1
        timelines.append(
            {
                "stream_record_id": r.get("stream_record_id"),
                "stream_sequence": r.get("stream_sequence"),
                "scientific_tick": r.get("scientific_tick"),
                "source_mechanism_id": mech,
                "source_receipt_event_id": r.get("source_receipt_event_id"),
                "emitted_energy": r.get("emitted_energy"),
                "anonymous_band_energies": r.get("anonymous_band_energies"),
                "spectral_profile_id": r.get("spectral_profile_id"),
                "position": r.get("position"),
                "lps_emission_id": r.get("lps_emission_id"),
                "lps_admitted": r.get("lps_admitted"),
                "cause_provenance": r.get("cause_provenance"),
                "authority": r.get("authority"),
            }
        )
    return {
        "schema": "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_V1",
        "contract": "authoritative_physical_acoustic_stream",
        "researcher_only": True,
        "agent_accessible": False,
        "audio_playback": False,
        "human_hz_calibration": "NOT_ESTABLISHED",
        "record_count": len(timelines),
        "by_mechanism": by_mech,
        "history_capacity": meta.get("history_capacity"),
        "evicted_count": meta.get("evicted_count"),
        "retained_count": meta.get("retained_count"),
        "timelines": timelines,
        "causal_reconstruction": (
            "committed physical source/response → mechanism emission receipt (L1) → "
            "LPS enqueue reference (L2) → bounded scientific stream record → "
            "Observer/Analyzer (no playback, no Hz)"
        ),
        "layer_scope": "L1_SOURCE_PLUS_L2_LPS_REFERENCE",
        "legacy_osc_bands_authority": "NON_AUTHORITATIVE_WHEN_LPS_ACTIVE",
        "progress": {
            "mode": "DETERMINISTIC_RECEIPT_SCAN",
            "completed": len(timelines),
            "total": len(timelines),
            "percent": 100.0 if timelines else None,
            "note": "Progress equals scanned stream records; not wall-clock estimate",
        },
        "section_title": "AUTHORITATIVE PHYSICAL ACOUSTIC STREAM",
    }


def format_authoritative_physical_acoustic_stream_section(s: dict[str, Any]) -> str:
    lines = [
        "## AUTHORITATIVE PHYSICAL ACOUSTIC STREAM",
        "",
        str(s.get("causal_reconstruction") or ""),
        "",
        f"records={s.get('record_count', 0)} · capacity={s.get('history_capacity')} · "
        f"retained={s.get('retained_count')} · evicted={s.get('evicted_count')}",
        f"by_mechanism={s.get('by_mechanism')}",
        "playback=NO · hz_mapping=NOT_ESTABLISHED · researcher_only=YES",
        "",
    ]
    for row in list(s.get("timelines") or [])[:24]:
        lines.append(
            f"- tick={row.get('scientific_tick')} · mech={row.get('source_mechanism_id')} · "
            f"id={row.get('stream_record_id')} · E={row.get('emitted_energy')} · "
            f"lps={row.get('lps_emission_id')} · admitted={row.get('lps_admitted')}"
        )
    return "\n".join(lines)


def acoustic_stream_records_from_consequences(run_dir: Path | str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Extract PHYSICAL_ACOUSTIC_STREAM_RECORD rows from saved consequences."""
    import json

    root = Path(run_dir)
    records: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}
    cons = root / "consequences.jsonl"
    if not cons.is_file():
        # Alternate layout used by some captures
        for p in sorted(root.glob("**/*consequence*.jsonl"))[:4]:
            cons = p
            break
    if not cons.is_file():
        return records, meta
    with cons.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            for slot in obj.get("slots") or []:
                for ref in slot.get("event_refs") or []:
                    if not isinstance(ref, dict):
                        continue
                    kind = str(ref.get("kind") or ref.get("receipt_kind") or "")
                    if kind in (
                        "PHYSICAL_ACOUSTIC_STREAM_RECORD",
                        "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM_V1",
                        "authoritative_physical_acoustic_stream",
                    ):
                        records.append(ref)
                        if ref.get("history_capacity") is not None:
                            meta.setdefault("history_capacity", ref.get("history_capacity"))
                        if ref.get("evicted_count") is not None:
                            meta["evicted_count"] = ref.get("evicted_count")
    # Prefer explicit meta event if present
    for r in records:
        if r.get("meta_only"):
            meta.update({k: r.get(k) for k in ("history_capacity", "evicted_count", "retained_count") if r.get(k) is not None})
    records = [r for r in records if not r.get("meta_only")]
    meta.setdefault("retained_count", len(records))
    return records, meta
