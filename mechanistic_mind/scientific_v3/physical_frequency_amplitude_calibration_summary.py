"""Analyzer reconstruction for PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT_V1."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mechanistic_mind.physical_system.physical_frequency_amplitude_calibration_contract import (
    COMPAT_C0,
    COMPAT_FUTURE,
    COMPAT_MISSING,
    PROFILE,
    SCHEMA,
    c0_calibration_payload,
    c0_calibration_reference,
    classify_calibration_metadata,
    legacy_calibration_stub,
)


def summarize_acoustic_calibration(
    records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Summarize C0 calibration evidence from consequences or live authority."""
    records = list(records or [])
    classes: dict[str, int] = {}
    profiles: set[str] = set()
    for r in records:
        if not isinstance(r, dict):
            continue
        cls = classify_calibration_metadata(r)
        classes[cls] = int(classes.get(cls, 0)) + 1
        if r.get("profile"):
            profiles.add(str(r.get("profile")))
    if not records:
        # Live/default authority when analyzing current tip without legacy files.
        ref = c0_calibration_reference()
        classes[COMPAT_C0] = 1
        profiles.add(PROFILE)
        records = [ref]
    authority = c0_calibration_payload()
    return {
        "schema": SCHEMA,
        "profile": PROFILE,
        "researcher_only": True,
        "agent_accessible": False,
        "audio_playback": False,
        "physical_values_transformed": False,
        "active_authority": c0_calibration_reference(),
        "compatibility_counts": classes,
        "profiles_seen": sorted(profiles),
        "legacy_stub_example": legacy_calibration_stub(),
        "unavailable_semantics": {
            "physical_frequency_mapping": authority["physical_frequency_mapping"],
            "band_centre_frequencies_hz": authority["band_centre_frequencies_hz"],
            "tick_duration_seconds": authority["time_authority"]["tick_duration_seconds"],
            "cell_length_metres": authority["length_authority"]["cell_length_metres"],
            "spl_mapping": authority["spl_mapping"],
        },
        "original_human_audible_available": False,
        "next_honest_listening_mode": authority["naming_restrictions"]["next_honest_listening_mode"],
        "future_mismatch_explicit": COMPAT_FUTURE,
        "progress": {
            "mode": "DETERMINISTIC_METADATA_SCAN",
            "completed": len(records),
            "total": len(records),
            "percent": 100.0 if records else None,
            "note": "Progress equals scanned calibration metadata records",
        },
        "section_title": "PHYSICAL FREQUENCY / AMPLITUDE CALIBRATION (C0)",
        "causal_reconstruction": (
            "abstract acoustic numbers frozen as C0 metadata → stream/probe reference profile → "
            "Analyzer reports interpretation without transforming physical band energies"
        ),
    }


def format_acoustic_calibration_section(s: dict[str, Any]) -> str:
    lines = [
        "## PHYSICAL FREQUENCY / AMPLITUDE CALIBRATION (C0)",
        "",
        str(s.get("causal_reconstruction") or ""),
        "",
        f"profile={s.get('profile')} · schema={s.get('schema')}",
        f"compatibility={s.get('compatibility_counts')}",
        f"Hz={s.get('unavailable_semantics', {}).get('physical_frequency_mapping')} · "
        f"SPL={s.get('unavailable_semantics', {}).get('spl_mapping')}",
        f"ORIGINAL={s.get('original_human_audible_available')} · "
        f"next={s.get('next_honest_listening_mode')}",
        "physical_values_transformed=False · playback=NO",
        "",
    ]
    return "\n".join(lines)


def calibration_records_from_consequences(run_dir: Path | str) -> list[dict[str, Any]]:
    root = Path(run_dir)
    out: list[dict[str, Any]] = []
    cons = root / "consequences.jsonl"
    if not cons.is_file():
        for p in sorted(root.glob("**/*consequence*.jsonl"))[:4]:
            cons = p
            break
    if not cons.is_file():
        return out
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
                    kind = str(ref.get("kind") or ref.get("schema") or "")
                    if "PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION" in kind or str(
                        ref.get("schema") or ""
                    ).startswith("PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION"):
                        out.append(ref)
                    elif str(ref.get("compatibility_class") or "") == COMPAT_MISSING:
                        out.append(ref)
    return out
