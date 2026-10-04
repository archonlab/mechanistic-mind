"""Analyzer reconstruction for OBSERVER_ACOUSTIC_PROBE_V1."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def summarize_observer_acoustic_probe(
    samples: list[dict[str, Any]],
    *,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = dict(meta or {})
    energies = []
    zero_ticks = 0
    for s in samples:
        if not isinstance(s, dict):
            continue
        e = float(s.get("total_received_energy") or 0.0)
        energies.append(e)
        if e <= 0.0 or s.get("zero_field"):
            zero_ticks += 1
    n = len(samples)
    return {
        "schema": "OBSERVER_ACOUSTIC_PROBE_V1",
        "contract": "observer_acoustic_probe",
        "researcher_only": True,
        "agent_accessible": False,
        "audio_playback": False,
        "human_hz_calibration": "NOT_ESTABLISHED",
        "sample_count": n,
        "zero_field_samples": zero_ticks,
        "history_capacity": meta.get("history_capacity"),
        "evicted_count": meta.get("evicted_count"),
        "probe_id": meta.get("probe_id") or (samples[0].get("probe_id") if samples else None),
        "sampling_mode": "POINT_MONO_V1",
        "timelines": [
            {
                "scientific_tick": s.get("scientific_tick"),
                "x": s.get("x"),
                "y": s.get("y"),
                "total_received_energy": s.get("total_received_energy"),
                "anonymous_band_energies": s.get("anonymous_band_energies"),
                "contributor_count_total": s.get("contributor_count_total"),
                "contributor_count_truncated": s.get("contributor_count_truncated"),
                "contributors": s.get("contributors"),
                "zero_field": s.get("zero_field"),
                "limitations": s.get("limitations"),
            }
            for s in samples
            if isinstance(s, dict)
        ],
        "causal_reconstruction": (
            "physical emission → LPS wavefront → pre-phenotype mono point field at probe XY → "
            "OBSERVER_ACOUSTIC_PROBE_SAMPLE (researcher-only) · distinct from organism L/R transduction · "
            "not a physical source · no playback"
        ),
        "progress": {
            "mode": "DETERMINISTIC_SAMPLE_SCAN",
            "completed": n,
            "total": n,
            "percent": 100.0 if n else None,
            "note": "Progress equals scanned probe samples",
        },
        "section_title": "OBSERVER ACOUSTIC PROBE",
    }


def format_observer_acoustic_probe_section(s: dict[str, Any]) -> str:
    lines = [
        "## OBSERVER ACOUSTIC PROBE",
        "",
        str(s.get("causal_reconstruction") or ""),
        "",
        f"samples={s.get('sample_count', 0)} · zero={s.get('zero_field_samples', 0)} · "
        f"capacity={s.get('history_capacity')} · evicted={s.get('evicted_count')}",
        "playback=NO · hz=NOT_ESTABLISHED · mass=NO · body=NO",
        "",
    ]
    for row in list(s.get("timelines") or [])[:24]:
        lines.append(
            f"- tick={row.get('scientific_tick')} · xy=({row.get('x')},{row.get('y')}) · "
            f"E={row.get('total_received_energy')} · contrib={row.get('contributor_count_total')} · "
            f"trunc={row.get('contributor_count_truncated')} · zero={row.get('zero_field')}"
        )
    return "\n".join(lines)


def probe_samples_from_consequences(run_dir: Path | str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    root = Path(run_dir)
    samples: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}
    cons = root / "consequences.jsonl"
    if not cons.is_file():
        for p in sorted(root.glob("**/*consequence*.jsonl"))[:4]:
            cons = p
            break
    if not cons.is_file():
        return samples, meta
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
                        "OBSERVER_ACOUSTIC_PROBE_SAMPLE",
                        "OBSERVER_ACOUSTIC_PROBE_V1",
                        "observer_acoustic_probe",
                    ):
                        if ref.get("meta_only"):
                            for k in ("history_capacity", "evicted_count", "probe_id"):
                                if ref.get(k) is not None:
                                    meta[k] = ref.get(k)
                        else:
                            samples.append(ref)
    meta.setdefault("retained_count", len(samples))
    return samples, meta
