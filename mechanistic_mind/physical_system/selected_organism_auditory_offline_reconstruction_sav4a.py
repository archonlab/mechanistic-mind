"""SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_SAV4A_V1.

Read-only saved-evidence normalization + deterministic SAV2-compatible schedule.
No audio playback, PCM, WAV, LPS replay, or physics restore.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable, Iterable

from mechanistic_mind.physical_system.canonical_physical_field_sonification import (
    CANONICAL_PLAYBACK_CARRIER_HZ,
    CANONICAL_SECONDS_PER_TICK,
    ENVELOPE_FRACTION_OF_TICK,
)
from mechanistic_mind.physical_system.selected_organism_auditory_sonification import (
    FIXED_RECEPTOR_GAIN,
    LIMITER_THRESHOLD,
    PROFILE as SAV2_PROFILE,
    SCHEMA as SAV2_SCHEMA,
    map_receptor_activation,
)

SCHEMA = "SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_SAV4A_V1"
CAPABILITY = "selected_organism_auditory_offline_reconstruction"
PROFILE = "SAVED_EVIDENCE_NORMALIZATION_AND_DETERMINISTIC_SCHEDULE_SAV4A_V1"
AUTHORITY = "RESEARCHER_DERIVED_READ_ONLY_OVER_SAVED_AUTHORITATIVE_EVIDENCE"
TITLE = "OFFLINE AUDITORY RECONSTRUCTION · SAV4A"
WARNING = (
    "READ-ONLY OVER SAVED EVIDENCE · GAPS ARE NOT SILENCE · "
    "0.05 s/tick IS CANONICAL PLAYBACK TIMING, NOT PHYSICAL TIME · "
    "NO AUDIO IN SAV4A · PLAYBACK BELONGS TO SAV4B"
)
LEGACY_UNAVAILABLE = (
    "SELECTED_ORGANISM_AUDITORY_OFFLINE_RECONSTRUCTION_UNAVAILABLE_LEGACY_EVIDENCE"
)

OATT_SCHEMA = "ORGANISM_AUDITORY_TRANSFORMATION_TRACE_V1"
OATT_PROFILE = "AUDITORY_A3_TO_A5_TRANSFORMATION_TRACE_V1"
SAV1_SCHEMA = "SELECTED_ORGANISM_AUDITORY_BOUNDARY_RECEIPT_V1"
SAV1_PROFILE = "ORGANISM_AUDITORY_BOUNDARY_A5_V1"
C0_PROFILE = "ABSTRACT_ACOUSTIC_AUTHORITY_C0_V1"

BAND_COUNT = 6
OSC_L_KEYS = tuple(f"osc_l_{i}" for i in range(BAND_COUNT))
OSC_R_KEYS = tuple(f"osc_r_{i}" for i in range(BAND_COUNT))

AUTH_OATT = "OATT_EXACT_TRACE"
AUTH_SAV1 = "SAV1_EXACT_A5"
AUTH_LEGACY = "LEGACY_OSC_A5_ONLY"
AUTH_UNAVAILABLE = "UNAVAILABLE"
AUTH_RANK = {AUTH_OATT: 3, AUTH_SAV1: 2, AUTH_LEGACY: 1, AUTH_UNAVAILABLE: 0}

PHASES = (
    "DISCOVER_FILES",
    "SCAN_RECORDS",
    "CLASSIFY_SCHEMAS",
    "PARTITION_IDENTITIES",
    "DEDUPLICATE",
    "DETECT_GAPS",
    "NORMALIZE",
    "BUILD_SCHEDULE",
)

ACCEPTED_CONSEQUENCE_FILES = (
    "scientific_consequences.jsonl",
    "consequences.jsonl",
)
ACCEPTED_OBSERVATION_FILES = (
    "scientific_observations.jsonl",
    "observations.jsonl",
)
ACCEPTED_META_FILES = (
    "scientific_meta.json",
    "scientific_v3_meta.json",
)

FORBIDDEN_A5_AUTHORITIES = (
    "authoritative_physical_acoustic_stream",
    "observer_acoustic_probe",
    "cognition",
    "pixels",
    "lps_replay",
    "receptor_recompute",
    "phenotype_recompute",
)

PREVIEW_LIMIT_DEFAULT = 64

ProgressCb = Callable[[dict[str, Any]], None]


def profile_reference() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "title": TITLE,
        "warning": WARNING,
        "researcher_only": True,
        "agent_accessible": False,
        "physical_mechanism": False,
        "physical_preset": False,
        "audio_playback_implemented": False,
        "pcm_rendering_implemented": False,
        "wav_export_implemented": False,
        "canonical_seconds_per_tick": CANONICAL_SECONDS_PER_TICK,
        "canonical_seconds_per_tick_is_physical": False,
        "canonical_seconds_per_tick_label": "CANONICAL_PLAYBACK_MAPPING_NON_PHYSICAL",
        "sav2_profile": SAV2_PROFILE,
        "sav2_schema": SAV2_SCHEMA,
        "required_sav1_profile": SAV1_PROFILE,
        "required_oatt_profile": OATT_PROFILE,
        "c0_profile": C0_PROFILE,
        "authoritative_input_hierarchy": [
            AUTH_OATT,
            AUTH_SAV1,
            AUTH_LEGACY,
            AUTH_UNAVAILABLE,
        ],
        "forbidden_a5_authorities": list(FORBIDDEN_A5_AUTHORITIES),
        "phases": list(PHASES),
        "accepted_consequence_files": list(ACCEPTED_CONSEQUENCE_FILES),
        "accepted_observation_files": list(ACCEPTED_OBSERVATION_FILES),
    }


def _emit(
    cb: ProgressCb | None,
    phase: str,
    *,
    processed: int = 0,
    total: int | None = None,
    **extra: Any,
) -> None:
    if cb is None:
        return
    payload: dict[str, Any] = {
        "phase": phase,
        "processed": int(processed),
        "total": total,
        "indeterminate": total is None,
        "percent": (
            100.0 * float(processed) / float(total)
            if total is not None and total > 0
            else None
        ),
    }
    payload.update(extra)
    cb(payload)


def _finite(x: Any) -> bool:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return False
    return math.isfinite(v)


def _vec6(src: Any) -> list[float] | None:
    if not isinstance(src, (list, tuple)) or len(src) != BAND_COUNT:
        return None
    out: list[float] = []
    for x in src:
        if not _finite(x):
            return None
        out.append(float(x))
    return out


def _stable_digest(obj: Any) -> str:
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _record_id(
    *,
    run_id: str,
    runtime_generation: str,
    agent_id: str,
    body_id: str,
    observation_tick: int,
    authority: str,
    source_schema: str,
    a5_left: list[float] | None = None,
    a5_right: list[float] | None = None,
) -> str:
    """Deterministic id from scientific identity + content (not file enumeration order)."""
    raw = "|".join(
        [
            SCHEMA,
            str(run_id),
            str(runtime_generation),
            str(agent_id),
            str(body_id),
            str(int(observation_tick)),
            str(authority),
            str(source_schema),
            json.dumps(a5_left, separators=(",", ":")),
            json.dumps(a5_right, separators=(",", ":")),
        ]
    )
    return "sav4a_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _identity_key(
    run_id: str, runtime_generation: str, agent_id: str, body_id: str
) -> tuple[str, str, str, str]:
    return (str(run_id), str(runtime_generation), str(agent_id), str(body_id))


def discover_evidence_files(run_dir: Path | str) -> dict[str, Any]:
    root = Path(run_dir)
    inventory: dict[str, Any] = {
        "run_dir": str(root),
        "accepted": [],
        "ignored_unknown": [],
        "missing_expected": [],
        "diagnostics": [],
    }
    if not root.is_dir():
        inventory["diagnostics"].append("RUN_DIR_MISSING")
        return inventory

    known = set(ACCEPTED_CONSEQUENCE_FILES + ACCEPTED_OBSERVATION_FILES + ACCEPTED_META_FILES)
    known_ignore_ok = {
        "scientific_decisions.jsonl",
        "scientific_motors.jsonl",
        "scientific_events.jsonl",
        "scientific_timeline.jsonl",
        "scientific_spine.jsonl",
        "scientific_checkpoints.jsonl",
        "physical_system_snapshot.json",
        "analysis.json",
        "README.md",
    }

    for name in ACCEPTED_CONSEQUENCE_FILES + ACCEPTED_OBSERVATION_FILES + ACCEPTED_META_FILES:
        p = root / name
        if p.is_file():
            inventory["accepted"].append(
                {
                    "filename": name,
                    "path": str(p),
                    "role": (
                        "consequences"
                        if name in ACCEPTED_CONSEQUENCE_FILES
                        else "observations"
                        if name in ACCEPTED_OBSERVATION_FILES
                        else "meta"
                    ),
                    "bytes": p.stat().st_size,
                }
            )
        else:
            inventory["missing_expected"].append(name)

    for p in sorted(root.iterdir(), key=lambda x: x.name):
        if not p.is_file():
            continue
        if p.name in known or p.name in known_ignore_ok:
            continue
        if p.suffix in {".png", ".jpg", ".wav", ".webm", ".log", ".txt"}:
            inventory["ignored_unknown"].append(
                {"filename": p.name, "reason": "NON_JSONL_MEDIA_OR_LOG_IGNORED"}
            )
            continue
        if p.suffix in {".jsonl", ".json"}:
            inventory["ignored_unknown"].append(
                {"filename": p.name, "reason": "UNKNOWN_EVIDENCE_FILENAME_NOT_PARSED"}
            )
            inventory["diagnostics"].append(f"IGNORED_UNKNOWN_FILE:{p.name}")
    return inventory


def _load_meta(root: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    for name in ACCEPTED_META_FILES:
        p = root / name
        if not p.is_file():
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict):
            meta[name] = data
    return meta


def _default_run_id(meta: dict[str, Any], fallback: str = "UNKNOWN_RUN") -> str:
    for key in ACCEPTED_META_FILES:
        d = meta.get(key) or {}
        rid = d.get("run_id")
        if rid not in (None, ""):
            return str(rid)
    return fallback


def _default_generation(meta: dict[str, Any]) -> str:
    for key in ACCEPTED_META_FILES:
        d = meta.get(key) or {}
        g = d.get("runtime_generation", d.get("generation"))
        if g is not None and str(g) != "":
            if isinstance(g, (int, float)) and float(g).is_integer():
                return str(int(g))
            return str(g)
    return "RUNTIME_GENERATION_UNKNOWN"


def _iter_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open("r", encoding="utf-8") as fh:
        for line_i, line in enumerate(fh):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except Exception:
                continue
            if isinstance(row, dict):
                yield line_i, row


def _extract_legacy_osc(
    accessible: dict[str, Any],
) -> tuple[list[float] | None, list[float] | None, str]:
    left: list[float] = []
    right: list[float] = []
    for k in OSC_L_KEYS:
        if k not in accessible:
            return None, None, "MISSING_CHANNEL"
        if not _finite(accessible[k]):
            return None, None, "NONFINITE"
        left.append(float(accessible[k]))
    for k in OSC_R_KEYS:
        if k not in accessible:
            return None, None, "MISSING_CHANNEL"
        if not _finite(accessible[k]):
            return None, None, "NONFINITE"
        right.append(float(accessible[k]))
    return left, right, "COMPLETE"


def _gen_str(gen: Any, default: str) -> str:
    if gen is None or gen == "":
        return default
    if isinstance(gen, (int, float)) and float(gen).is_integer():
        return str(int(gen))
    return str(gen)


def _candidate_from_oatt(
    ref: dict[str, Any],
    *,
    run_id: str,
    runtime_generation: str,
    source_file: str,
    source_index: int,
    consequence_tick: int | None,
) -> dict[str, Any] | None:
    left = _vec6(ref.get("a5_left"))
    right = _vec6(ref.get("a5_right"))
    a5 = ref.get("a5") if isinstance(ref.get("a5"), dict) else {}
    if left is None:
        left = _vec6(a5.get("left_receptor_channels"))
    if right is None:
        right = _vec6(a5.get("right_receptor_channels"))
    tick_raw = ref.get("observation_tick", ref.get("scientific_tick", consequence_tick))
    if tick_raw is None:
        return None
    try:
        tick = int(tick_raw)
    except (TypeError, ValueError):
        return None
    agent_id = str(ref.get("agent_id") or "")
    body_id = str(ref.get("body_id") or "")
    if not agent_id or not body_id:
        return {
            "ambiguous": True,
            "reason": "MISSING_IDENTITY",
            "source_file": source_file,
            "source_index": source_index,
            "observation_tick": tick,
        }
    a3_left = _vec6(
        ref.get("a3_left") or (ref.get("a3") or {}).get("left_receptor_band_energy")
    )
    a3_right = _vec6(
        ref.get("a3_right") or (ref.get("a3") or {}).get("right_receptor_band_energy")
    )
    a3_status = "PRESENT" if a3_left is not None and a3_right is not None else "UNAVAILABLE"
    a4_status = (
        "PRESENT"
        if ref.get("a4_sensor_scale") is not None or isinstance(ref.get("a4"), dict)
        else "UNAVAILABLE"
    )
    base = {
        "run_id": run_id,
        "runtime_generation": runtime_generation,
        "agent_id": agent_id,
        "body_id": body_id,
        "observation_tick": tick,
        "source_file": source_file,
        "source_index": source_index,
        "source_schema": OATT_SCHEMA,
        "source_profile": str(ref.get("profile") or OATT_PROFILE),
        "a3_status": a3_status,
        "a4_status": a4_status,
    }
    if left is None or right is None:
        return {
            **base,
            "authority": AUTH_UNAVAILABLE,
            "reason": "OATT_A5_INCOMPLETE",
            "a5_left": None,
            "a5_right": None,
        }
    true_zero = all(v == 0.0 for v in left + right)
    return {
        **base,
        "authority": AUTH_OATT,
        "source_record_ref": str(ref.get("trace_id") or f"oatt@{source_index}"),
        "a5_left": left,
        "a5_right": right,
        "a3_left": a3_left,
        "a3_right": a3_right,
        "a4_sensor_scale": (
            ref.get("a4_sensor_scale")
            if ref.get("a4_sensor_scale") is not None
            else (ref.get("a4") or {}).get("sensor_scale")
        ),
        "sav1_receipt_id": ref.get("sav1_receipt_id"),
        "true_zero": true_zero,
        "compatibility_class": (
            "CURRENT_COMPATIBLE"
            if str(ref.get("profile") or OATT_PROFILE) == OATT_PROFILE
            else "PROFILE_UNKNOWN_OR_INCOMPATIBLE"
        ),
    }


def _candidate_from_sav1(
    ref: dict[str, Any],
    *,
    run_id: str,
    runtime_generation: str,
    source_file: str,
    source_index: int,
    consequence_tick: int | None,
) -> dict[str, Any] | None:
    sec = ref.get("section_a_organism_accessible") or {}
    left = _vec6(sec.get("left_receptor_channels") if isinstance(sec, dict) else None)
    right = _vec6(sec.get("right_receptor_channels") if isinstance(sec, dict) else None)
    tick_raw = ref.get("scientific_tick", consequence_tick)
    if tick_raw is None:
        return None
    try:
        tick = int(tick_raw)
    except (TypeError, ValueError):
        return None
    agent_id = str(ref.get("agent_id") or "")
    body_id = str(ref.get("body_id") or "")
    if not agent_id or not body_id:
        return {
            "ambiguous": True,
            "reason": "MISSING_IDENTITY",
            "source_file": source_file,
            "source_index": source_index,
            "observation_tick": tick,
        }
    base = {
        "run_id": run_id,
        "runtime_generation": runtime_generation,
        "agent_id": agent_id,
        "body_id": body_id,
        "observation_tick": tick,
        "source_file": source_file,
        "source_index": source_index,
        "source_schema": SAV1_SCHEMA,
        "source_profile": str(ref.get("profile") or SAV1_PROFILE),
        "a3_status": "UNAVAILABLE",
        "a4_status": "UNAVAILABLE",
    }
    if left is None or right is None:
        return {
            **base,
            "authority": AUTH_UNAVAILABLE,
            "reason": "SAV1_A5_INCOMPLETE",
            "a5_left": None,
            "a5_right": None,
        }
    true_zero = all(v == 0.0 for v in left + right)
    prof = str(ref.get("profile") or SAV1_PROFILE)
    return {
        **base,
        "authority": AUTH_SAV1,
        "source_record_ref": str(ref.get("receipt_id") or f"sav1@{source_index}"),
        "a5_left": left,
        "a5_right": right,
        "true_zero": true_zero,
        "compatibility_class": (
            "CURRENT_COMPATIBLE"
            if prof == SAV1_PROFILE
            else "PROFILE_UNKNOWN_OR_INCOMPATIBLE"
        ),
    }


def _candidate_from_legacy_obs(
    row: dict[str, Any],
    *,
    run_id: str,
    runtime_generation: str,
    source_file: str,
    source_index: int,
) -> dict[str, Any] | None:
    accessible = row.get("accessible")
    if not isinstance(accessible, dict):
        return None
    if not any(k in accessible for k in OSC_L_KEYS + OSC_R_KEYS):
        return None
    tick_raw = row.get("tick", row.get("observation_tick"))
    if tick_raw is None:
        return None
    try:
        tick = int(tick_raw)
    except (TypeError, ValueError):
        return None
    agent_id = str(row.get("cognitive_agent_id") or row.get("agent_id") or "")
    body_id = str(row.get("physical_body_id") or row.get("body_id") or "")
    if not agent_id or not body_id:
        return {
            "ambiguous": True,
            "reason": "MISSING_IDENTITY",
            "source_file": source_file,
            "source_index": source_index,
            "observation_tick": tick,
        }
    left, right, st = _extract_legacy_osc(accessible)
    base = {
        "run_id": str(row.get("run_id") or run_id),
        "runtime_generation": runtime_generation,
        "agent_id": agent_id,
        "body_id": body_id,
        "observation_tick": tick,
        "source_file": source_file,
        "source_index": source_index,
        "source_schema": str(row.get("schema") or "LEGACY_OBSERVATION_OSC"),
        "source_profile": "LEGACY_OSC_A5_NO_PROFILE",
        "a3_status": "UNAVAILABLE",
        "a4_status": "UNAVAILABLE",
        "legacy_label": True,
        "never_upgraded_to_oatt_or_sav1": True,
    }
    if st != "COMPLETE" or left is None or right is None:
        return {
            **base,
            "authority": AUTH_UNAVAILABLE,
            "reason": f"LEGACY_OSC_{st}",
            "a5_left": None,
            "a5_right": None,
            "compatibility_class": "PROFILE_UNKNOWN_OR_INCOMPATIBLE",
        }
    true_zero = all(v == 0.0 for v in left + right)
    return {
        **base,
        "authority": AUTH_LEGACY,
        "source_record_ref": str(row.get("observation_id") or f"obs@{source_index}"),
        "a5_left": left,
        "a5_right": right,
        "true_zero": true_zero,
        "compatibility_class": "EXPLICITLY_COMPATIBLE_LEGACY_A5",
    }


def scan_candidates_from_run_dir(
    run_dir: Path | str,
    *,
    progress: ProgressCb | None = None,
) -> dict[str, Any]:
    root = Path(run_dir)
    _emit(progress, "DISCOVER_FILES", processed=0, total=None)
    inventory = discover_evidence_files(root)
    _emit(
        progress,
        "DISCOVER_FILES",
        processed=len(inventory["accepted"]),
        total=len(inventory["accepted"]),
    )

    meta = _load_meta(root)
    run_id = _default_run_id(meta, fallback=root.name)
    default_gen = _default_generation(meta)

    candidates: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    ignored_kinds: list[str] = []
    empty_event_refs_rows = 0
    scanned = 0

    seen_cons_paths: set[str] = set()
    for entry in [a for a in inventory["accepted"] if a["role"] == "consequences"]:
        path = Path(entry["path"])
        if str(path) in seen_cons_paths:
            continue
        seen_cons_paths.add(str(path))
        for line_i, row in _iter_jsonl(path):
            scanned += 1
            if scanned % 500 == 0:
                _emit(progress, "SCAN_RECORDS", processed=scanned, total=None)
            rid = str(row.get("run_id") or run_id)
            gen_s = _gen_str(row.get("runtime_generation", row.get("generation")), default_gen)
            tick = row.get("tick_to", row.get("tick_from", row.get("tick")))
            try:
                ctick = int(tick) if tick is not None else None
            except (TypeError, ValueError):
                ctick = None
            refs = row.get("event_refs")
            if refs is None or (isinstance(refs, list) and len(refs) == 0):
                empty_event_refs_rows += 1
                continue
            if not isinstance(refs, list):
                continue
            for ref in refs:
                if not isinstance(ref, dict):
                    continue
                kind = str(ref.get("kind") or "")
                schema = str(ref.get("schema") or "")
                if kind == "ORGANISM_AUDITORY_TRANSFORMATION_TRACE" or schema == OATT_SCHEMA:
                    cand = _candidate_from_oatt(
                        ref,
                        run_id=rid,
                        runtime_generation=gen_s,
                        source_file=entry["filename"],
                        source_index=line_i,
                        consequence_tick=ctick,
                    )
                    if cand and cand.get("ambiguous"):
                        ambiguous.append(cand)
                    elif cand:
                        candidates.append(cand)
                elif kind == "ORGANISM_AUDITORY_BOUNDARY_RECEIPT" or schema == SAV1_SCHEMA:
                    cand = _candidate_from_sav1(
                        ref,
                        run_id=rid,
                        runtime_generation=gen_s,
                        source_file=entry["filename"],
                        source_index=line_i,
                        consequence_tick=ctick,
                    )
                    if cand and cand.get("ambiguous"):
                        ambiguous.append(cand)
                    elif cand:
                        candidates.append(cand)
                elif (
                    kind
                    in {
                        "PHYSICAL_FREQUENCY_AMPLITUDE_CALIBRATION_CONTRACT",
                        "AUTHORITATIVE_PHYSICAL_ACOUSTIC_STREAM",
                        "OBSERVER_ACOUSTIC_PROBE",
                    }
                    or "ACOUSTIC_STREAM" in kind
                    or "PROBE" in kind
                ):
                    ignored_kinds.append(kind or schema)
            emb = row.get("selected_organism_auditory_boundary_receipt")
            if isinstance(emb, dict):
                cand = _candidate_from_sav1(
                    emb,
                    run_id=rid,
                    runtime_generation=gen_s,
                    source_file=entry["filename"],
                    source_index=line_i,
                    consequence_tick=ctick,
                )
                if cand and cand.get("ambiguous"):
                    ambiguous.append(cand)
                elif cand:
                    candidates.append(cand)

    seen_obs: set[str] = set()
    for entry in [a for a in inventory["accepted"] if a["role"] == "observations"]:
        path = Path(entry["path"])
        if str(path) in seen_obs:
            continue
        seen_obs.add(str(path))
        for line_i, row in _iter_jsonl(path):
            scanned += 1
            if scanned % 500 == 0:
                _emit(progress, "SCAN_RECORDS", processed=scanned, total=None)
            rid = str(row.get("run_id") or run_id)
            gen_s = _gen_str(row.get("runtime_generation", row.get("generation")), default_gen)
            cand = _candidate_from_legacy_obs(
                row,
                run_id=rid,
                runtime_generation=gen_s,
                source_file=entry["filename"],
                source_index=line_i,
            )
            if cand and cand.get("ambiguous"):
                ambiguous.append(cand)
            elif cand:
                candidates.append(cand)

    _emit(progress, "SCAN_RECORDS", processed=scanned, total=scanned)
    _emit(progress, "CLASSIFY_SCHEMAS", processed=len(candidates), total=len(candidates))

    return {
        "inventory": inventory,
        "run_id": run_id,
        "default_runtime_generation": default_gen,
        "candidates": candidates,
        "ambiguous": ambiguous,
        "ignored_non_a5_kinds": sorted(set(ignored_kinds)),
        "empty_event_refs_rows": empty_event_refs_rows,
        "empty_event_refs_means": "NO_REFERENCES_RECORDED_NOT_NO_AUDITORY_EVENTS",
        "scanned_record_count": scanned,
        "stream_used_as_a5_authority": False,
        "probe_used_as_a5_authority": False,
        "cognition_used_as_a5_authority": False,
        "pixels_used_as_a5_authority": False,
    }


def _a5_equal(a: list[float] | None, b: list[float] | None) -> bool:
    if a is None or b is None:
        return a is b
    if len(a) != len(b):
        return False
    return all(x == y for x, y in zip(a, b))


def normalize_and_schedule(
    scan: dict[str, Any],
    *,
    progress: ProgressCb | None = None,
    preview_limit: int = PREVIEW_LIMIT_DEFAULT,
    sav2_profile_override: str | None = None,
    force_incompatible_schedule: bool = False,
) -> dict[str, Any]:
    candidates = list(scan.get("candidates") or [])
    candidates.sort(
        key=lambda c: (
            str(c.get("runtime_generation") or ""),
            int(c.get("observation_tick") or 0),
            str(c.get("agent_id") or ""),
            str(c.get("body_id") or ""),
            -AUTH_RANK.get(str(c.get("authority") or AUTH_UNAVAILABLE), 0),
            str(c.get("source_file") or ""),
            int(c.get("source_index") or 0),
        )
    )
    _emit(progress, "PARTITION_IDENTITIES", processed=0, total=len(candidates))

    by_key: dict[tuple, list[dict[str, Any]]] = {}
    for c in candidates:
        ik = _identity_key(
            str(c.get("run_id") or ""),
            str(c.get("runtime_generation") or ""),
            str(c.get("agent_id") or ""),
            str(c.get("body_id") or ""),
        )
        tick = int(c.get("observation_tick") or 0)
        by_key.setdefault((ik, tick), []).append(c)

    normalized: list[dict[str, Any]] = []
    duplicate_count = 0
    conflict_count = 0
    superseded: list[dict[str, Any]] = []

    for (ik, tick), group in sorted(
        by_key.items(),
        key=lambda x: (x[0][0][1], x[0][1], x[0][0][2], x[0][0][3], x[0][0][0]),
    ):
        usable = [
            g
            for g in group
            if g.get("a5_left") is not None and g.get("a5_right") is not None
        ]
        if not usable:
            g0 = group[0]
            rid = _record_id(
                run_id=ik[0],
                runtime_generation=ik[1],
                agent_id=ik[2],
                body_id=ik[3],
                observation_tick=tick,
                authority=AUTH_UNAVAILABLE,
                source_schema=str(g0.get("source_schema") or "NONE"),
                a5_left=None,
                a5_right=None,
            )
            normalized.append(
                {
                    "schema": SCHEMA,
                    "profile": PROFILE,
                    "record_id": rid,
                    "run_id": ik[0],
                    "runtime_generation": ik[1],
                    "agent_id": ik[2],
                    "body_id": ik[3],
                    "observation_tick": tick,
                    "source_authority_class": AUTH_UNAVAILABLE,
                    "source_schema": g0.get("source_schema"),
                    "source_profile": g0.get("source_profile"),
                    "source_record_ref": g0.get("source_record_ref"),
                    "source_file": g0.get("source_file"),
                    "source_index": g0.get("source_index"),
                    "a5_left": None,
                    "a5_right": None,
                    "a3_status": g0.get("a3_status", "UNAVAILABLE"),
                    "a4_status": g0.get("a4_status", "UNAVAILABLE"),
                    "true_zero": False,
                    "duplicate_status": "NONE",
                    "conflict_status": "NONE",
                    "compatibility_class": g0.get(
                        "compatibility_class", "PROFILE_UNKNOWN_OR_INCOMPATIBLE"
                    ),
                    "legacy_label": bool(g0.get("legacy_label")),
                    "completeness_hint": "UNAVAILABLE",
                }
            )
            continue

        usable.sort(
            key=lambda g: (
                -AUTH_RANK.get(str(g.get("authority")), 0),
                str(g.get("source_file") or ""),
                int(g.get("source_index") or 0),
            )
        )
        winner = usable[0]
        local_dups = 0
        local_conflicts = 0
        for loser in usable[1:]:
            if AUTH_RANK.get(str(loser.get("authority")), 0) < AUTH_RANK.get(
                str(winner.get("authority")), 0
            ):
                superseded.append(
                    {
                        "tick": tick,
                        "identity": list(ik),
                        "winner_authority": winner.get("authority"),
                        "superseded_authority": loser.get("authority"),
                        "source_index": loser.get("source_index"),
                    }
                )
                continue
            if _a5_equal(winner.get("a5_left"), loser.get("a5_left")) and _a5_equal(
                winner.get("a5_right"), loser.get("a5_right")
            ):
                local_dups += 1
                duplicate_count += 1
            else:
                local_conflicts += 1
                conflict_count += 1
                winner = dict(winner)
                winner["_conflict"] = True

        auth = str(winner.get("authority"))
        rid = _record_id(
            run_id=ik[0],
            runtime_generation=ik[1],
            agent_id=ik[2],
            body_id=ik[3],
            observation_tick=tick,
            authority=auth,
            source_schema=str(winner.get("source_schema") or ""),
            a5_left=list(winner["a5_left"]),
            a5_right=list(winner["a5_right"]),
        )
        completeness_hint = {
            AUTH_OATT: "OATT_COMPLETE",
            AUTH_SAV1: "SAV1_A5_ONLY",
            AUTH_LEGACY: "LEGACY_A5_ONLY",
        }.get(auth, "UNAVAILABLE")
        if winner.get("_conflict"):
            completeness_hint = "CONFLICTING_DUPLICATE"
        normalized.append(
            {
                "schema": SCHEMA,
                "profile": PROFILE,
                "record_id": rid,
                "run_id": ik[0],
                "runtime_generation": ik[1],
                "agent_id": ik[2],
                "body_id": ik[3],
                "observation_tick": tick,
                "source_authority_class": auth,
                "source_schema": winner.get("source_schema"),
                "source_profile": winner.get("source_profile"),
                "source_record_ref": winner.get("source_record_ref"),
                "source_file": winner.get("source_file"),
                "source_index": winner.get("source_index"),
                "a5_left": list(winner["a5_left"]),
                "a5_right": list(winner["a5_right"]),
                "a3_left": winner.get("a3_left"),
                "a3_right": winner.get("a3_right"),
                "a3_status": winner.get("a3_status", "UNAVAILABLE"),
                "a4_status": winner.get("a4_status", "UNAVAILABLE"),
                "a4_sensor_scale": winner.get("a4_sensor_scale"),
                "true_zero": bool(winner.get("true_zero")),
                "duplicate_status": "KEPT_FIRST" if local_dups else "NONE",
                "duplicate_count_at_tick": local_dups,
                "conflict_status": (
                    "CONFLICT_VISIBLE_NO_AVERAGE" if winner.get("_conflict") else "NONE"
                ),
                "conflict_count_at_tick": local_conflicts,
                "compatibility_class": winner.get(
                    "compatibility_class", "CURRENT_COMPATIBLE"
                ),
                "legacy_label": bool(winner.get("legacy_label")),
                "never_upgraded_to_oatt_or_sav1": bool(
                    winner.get("never_upgraded_to_oatt_or_sav1")
                ),
                "completeness_hint": completeness_hint,
                "c0_profile": C0_PROFILE,
                "sav2_mapping_profile": sav2_profile_override or SAV2_PROFILE,
            }
        )

    _emit(
        progress,
        "DEDUPLICATE",
        processed=len(normalized),
        total=len(normalized),
        duplicate_count=duplicate_count,
        conflict_count=conflict_count,
    )

    segments: list[dict[str, Any]] = []
    by_identity: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    for rec in normalized:
        ik = _identity_key(
            rec["run_id"], rec["runtime_generation"], rec["agent_id"], rec["body_id"]
        )
        by_identity.setdefault(ik, []).append(rec)

    schedule_items: list[dict[str, Any]] = []
    gap_total = 0

    for ik, recs in sorted(
        by_identity.items(), key=lambda x: (x[0][1], x[0][2], x[0][3], x[0][0])
    ):
        recs.sort(
            key=lambda r: (
                int(r["observation_tick"]),
                str(r.get("source_file") or ""),
                int(r.get("source_index") or 0),
            )
        )
        ticks = [int(r["observation_tick"]) for r in recs if r.get("a5_left") is not None]
        if not ticks:
            seg_id = "seg_" + _stable_digest(list(ik))[:16]
            segments.append(
                {
                    "segment_id": seg_id,
                    "run_id": ik[0],
                    "runtime_generation": ik[1],
                    "agent_id": ik[2],
                    "body_id": ik[3],
                    "completeness": "UNAVAILABLE",
                    "authority_badge": AUTH_UNAVAILABLE,
                    "first_tick": None,
                    "last_tick": None,
                    "observed_tick_count": 0,
                    "expected_tick_span": 0,
                    "gap_count": 0,
                    "schedule_available": False,
                    "record_ids": [],
                }
            )
            continue

        contiguous: list[list[dict[str, Any]]] = []
        bucket: list[dict[str, Any]] = []
        usable_recs = [r for r in recs if r.get("a5_left") is not None]
        for r in usable_recs:
            if not bucket:
                bucket = [r]
                continue
            prev = int(bucket[-1]["observation_tick"])
            cur = int(r["observation_tick"])
            if cur - prev > 1:
                contiguous.append(bucket)
                bucket = [r]
            else:
                bucket.append(r)
        if bucket:
            contiguous.append(bucket)

        first_t, last_t = ticks[0], ticks[-1]
        expected_span = last_t - first_t + 1
        observed = len(set(ticks))
        gaps = max(0, expected_span - observed)
        gap_total += gaps

        for bi, bucket in enumerate(contiguous):
            bticks = [int(r["observation_tick"]) for r in bucket]
            b_first, b_last = bticks[0], bticks[-1]
            b_expected = b_last - b_first + 1
            b_obs = len(set(bticks))
            b_gaps = max(0, b_expected - b_obs)
            auths = {r["source_authority_class"] for r in bucket}
            if AUTH_OATT in auths:
                auth_badge = AUTH_OATT
                completeness = "OATT_COMPLETE" if b_gaps == 0 else "GAPPED"
            elif AUTH_SAV1 in auths:
                auth_badge = AUTH_SAV1
                completeness = "SAV1_A5_ONLY" if b_gaps == 0 else "GAPPED"
            elif AUTH_LEGACY in auths:
                auth_badge = AUTH_LEGACY
                completeness = "LEGACY_A5_ONLY" if b_gaps == 0 else "GAPPED"
            else:
                auth_badge = AUTH_UNAVAILABLE
                completeness = "UNAVAILABLE"

            schedule_ok = all(
                r.get("compatibility_class")
                in {"CURRENT_COMPATIBLE", "EXPLICITLY_COMPATIBLE_LEGACY_A5"}
                for r in bucket
            )
            schedule_block_reason = None
            if not schedule_ok and not force_incompatible_schedule:
                schedule_block_reason = "PROFILE_UNKNOWN_OR_INCOMPATIBLE"
                completeness = "PROFILE_UNKNOWN_OR_INCOMPATIBLE"
            elif force_incompatible_schedule:
                schedule_ok = True

            effective_sav2 = sav2_profile_override or SAV2_PROFILE
            seg_id = "seg_" + _stable_digest([list(ik), b_first, b_last, bi])[:16]
            for r in bucket:
                r["segment_id"] = seg_id

            if b_gaps > 0 and completeness not in {
                "PROFILE_UNKNOWN_OR_INCOMPATIBLE",
                "UNAVAILABLE",
            }:
                completeness = "GAPPED"

            segments.append(
                {
                    "segment_id": seg_id,
                    "run_id": ik[0],
                    "runtime_generation": ik[1],
                    "agent_id": ik[2],
                    "body_id": ik[3],
                    "completeness": completeness,
                    "authority_badge": auth_badge,
                    "first_tick": b_first,
                    "last_tick": b_last,
                    "observed_tick_count": b_obs,
                    "expected_tick_span": b_expected,
                    "gap_count": b_gaps,
                    "schedule_available": schedule_ok,
                    "schedule_block_reason": schedule_block_reason,
                    "source_schemas": sorted(
                        {str(r.get("source_schema")) for r in bucket}
                    ),
                    "source_profiles": sorted(
                        {str(r.get("source_profile")) for r in bucket}
                    ),
                    "c0_profile": C0_PROFILE,
                    "sav2_mapping_profile": effective_sav2 if schedule_ok else None,
                    "compatibility_class": (
                        "CURRENT_COMPATIBLE"
                        if all(
                            r.get("compatibility_class") == "CURRENT_COMPATIBLE"
                            for r in bucket
                        )
                        else (
                            "EXPLICITLY_COMPATIBLE_LEGACY_A5"
                            if auth_badge == AUTH_LEGACY and schedule_ok
                            else "PROFILE_UNKNOWN_OR_INCOMPATIBLE"
                        )
                    ),
                    "record_ids": [r["record_id"] for r in bucket],
                    "current_profile_silently_applied_to_legacy": False,
                    "span_gap_count_identity": gaps,
                }
            )

            if not schedule_ok:
                continue

            t0 = 0.0
            prev_tick: int | None = None
            for r in bucket:
                tick_i = int(r["observation_tick"])
                if prev_tick is not None:
                    delta = tick_i - prev_tick
                    t0 += CANONICAL_SECONDS_PER_TICK * max(0, delta - 1)
                mapped = map_receptor_activation(r["a5_left"], r["a5_right"])
                item_id = "sch_" + hashlib.sha256(
                    f"{seg_id}|{r['record_id']}|{tick_i}|{SAV2_PROFILE}".encode()
                ).hexdigest()[:20]
                schedule_items.append(
                    {
                        "schedule_item_id": item_id,
                        "source_normalized_record_id": r["record_id"],
                        "segment_id": seg_id,
                        "observation_tick": tick_i,
                        "canonical_start_seconds": t0,
                        "canonical_duration_seconds": CANONICAL_SECONDS_PER_TICK,
                        "envelope_fraction_of_tick": ENVELOPE_FRACTION_OF_TICK,
                        "envelope_ramp_seconds": max(
                            0.001, CANONICAL_SECONDS_PER_TICK * ENVELOPE_FRACTION_OF_TICK
                        ),
                        "left_input": list(r["a5_left"]),
                        "right_input": list(r["a5_right"]),
                        "left_amplitudes": list(mapped["left_amplitudes"]),
                        "right_amplitudes": list(mapped["right_amplitudes"]),
                        "fixed_receptor_gain": FIXED_RECEPTOR_GAIN,
                        "limiter_threshold": LIMITER_THRESHOLD,
                        "carriers_hz": list(CANONICAL_PLAYBACK_CARRIER_HZ),
                        "carrier_label": (
                            "PLAYBACK CARRIERS — NOT PHYSICAL OR ORGANISM FREQUENCIES"
                        ),
                        "carrier_hz_are_physical": False,
                        "carrier_hz_are_organism_frequencies": False,
                        "sav2_schema": SAV2_SCHEMA,
                        "sav2_profile": SAV2_PROFILE,
                        "amplitude_mapping": mapped["policy"],
                        "authority_class": r["source_authority_class"],
                        "compatibility_class": r.get("compatibility_class"),
                        "true_zero": bool(r.get("true_zero")),
                        "gap_boundary": False,
                        "canonical_seconds_per_tick": CANONICAL_SECONDS_PER_TICK,
                        "canonical_seconds_per_tick_is_physical": False,
                    }
                )
                t0 += CANONICAL_SECONDS_PER_TICK
                prev_tick = tick_i

    _emit(
        progress,
        "DETECT_GAPS",
        processed=len(segments),
        total=len(segments),
        gap_total=gap_total,
    )
    _emit(progress, "NORMALIZE", processed=len(normalized), total=len(normalized))
    _emit(
        progress, "BUILD_SCHEDULE", processed=len(schedule_items), total=len(schedule_items)
    )

    norm_digest = _stable_digest(
        [
            {
                "record_id": r["record_id"],
                "identity": [
                    r["run_id"],
                    r["runtime_generation"],
                    r["agent_id"],
                    r["body_id"],
                ],
                "tick": r["observation_tick"],
                "authority": r["source_authority_class"],
                "a5_left": r.get("a5_left"),
                "a5_right": r.get("a5_right"),
                "true_zero": r.get("true_zero"),
                "conflict": r.get("conflict_status"),
            }
            for r in normalized
        ]
    )
    sched_digest = _stable_digest(
        [
            {
                "schedule_item_id": s["schedule_item_id"],
                "record_id": s["source_normalized_record_id"],
                "tick": s["observation_tick"],
                "t0": s["canonical_start_seconds"],
                "left_amp": s["left_amplitudes"],
                "right_amp": s["right_amplitudes"],
                "carriers": s["carriers_hz"],
            }
            for s in schedule_items
        ]
    )

    auth_counts = {AUTH_OATT: 0, AUTH_SAV1: 0, AUTH_LEGACY: 0, AUTH_UNAVAILABLE: 0}
    for r in normalized:
        a = str(r.get("source_authority_class") or AUTH_UNAVAILABLE)
        auth_counts[a] = auth_counts.get(a, 0) + 1

    schedule_available = len(schedule_items) > 0
    pl = max(0, int(preview_limit))
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "title": TITLE,
        "warning": WARNING,
        "available": len(normalized) > 0,
        "researcher_only": True,
        "agent_accessible": False,
        "audio_playback_implemented": False,
        "pcm_rendering_implemented": False,
        "wav_export_implemented": False,
        "offline_playback_owner_created": False,
        "source_inventory": scan.get("inventory"),
        "run_id": scan.get("run_id"),
        "default_runtime_generation": scan.get("default_runtime_generation"),
        "identity_segments": segments,
        "authority_matrix": auth_counts,
        "completeness_and_authority_matrix": {
            "segments": [
                {
                    "segment_id": s["segment_id"],
                    "completeness": s["completeness"],
                    "authority_badge": s["authority_badge"],
                    "gap_count": s["gap_count"],
                    "schedule_available": s["schedule_available"],
                }
                for s in segments
            ]
        },
        "gap_count": gap_total,
        "duplicate_count": duplicate_count,
        "conflict_count": conflict_count,
        "superseded_lower_authority": superseded[:64],
        "superseded_total": len(superseded),
        "ambiguous_total": len(scan.get("ambiguous") or []),
        "empty_event_refs_rows": scan.get("empty_event_refs_rows"),
        "empty_event_refs_means": scan.get("empty_event_refs_means"),
        "schedule_available": schedule_available,
        "schedule_item_count": len(schedule_items),
        "normalized_record_count": len(normalized),
        "normalized_record_digest": norm_digest,
        "schedule_digest": sched_digest,
        "normalized_records_preview": normalized[:pl],
        "schedule_items_preview": schedule_items[:pl],
        "preview_limit": pl,
        "truncated": {
            "normalized": len(normalized) > pl,
            "schedule": len(schedule_items) > pl,
            "normalized_total": len(normalized),
            "schedule_total": len(schedule_items),
        },
        "progress": {
            "phases": list(PHASES),
            "completed_phases": list(PHASES),
            "status": "COMPLETE",
        },
        "limitations": [
            "NO_AUDIO_IN_SAV4A",
            "GAPS_ARE_NOT_SILENCE",
            "NO_ZERO_FILL_FOR_GAPS",
            "NO_A5_INTERPOLATION",
            "NO_RUNTIME_GENERATION_BRIDGING",
            "CANONICAL_SECONDS_PER_TICK_NON_PHYSICAL",
            "EMPTY_EVENT_REFS_NOT_NO_EVENTS",
            "STREAM_PROBE_COGNITION_PIXELS_FORBIDDEN_AS_A5",
            "LEGACY_NEVER_SILENTLY_UPGRADED",
            "SAV2_HISTORICAL_MONITORING_PROVENANCE_NOT_ON_DISK",
        ],
        "profile_compatibility": {
            "sav2_profile": SAV2_PROFILE,
            "c0_profile": C0_PROFILE,
            "current_profile_silently_applied_to_legacy": False,
            "legacy_schedule_policy": (
                "EXPLICITLY_COMPATIBLE_LEGACY_A5_USES_DOCUMENTED_SAV2_LINEAR_MAP"
            ),
        },
        "stream_used_as_a5_authority": False,
        "probe_used_as_a5_authority": False,
        "cognition_used_as_a5_authority": False,
        "pixels_used_as_a5_authority": False,
        "canonical_seconds_per_tick": CANONICAL_SECONDS_PER_TICK,
        "canonical_seconds_per_tick_is_physical": False,
        "sav2_mapping_reused": True,
        "bit_identical_pcm_claimed": False,
        "device_output_deterministic_claimed": False,
        "gaps_are_not_silence_warning": True,
        "no_audio_sav4a_warning": True,
    }
    if len(normalized) <= pl * 2:
        payload["normalized_records"] = normalized
    if len(schedule_items) <= pl * 2:
        payload["schedule_items"] = schedule_items
    return payload


def reconstruct_from_run_dir(
    run_dir: Path | str,
    *,
    progress: ProgressCb | None = None,
    preview_limit: int = PREVIEW_LIMIT_DEFAULT,
) -> dict[str, Any]:
    phases_log: list[dict[str, Any]] = []

    def _cb(ev: dict[str, Any]) -> None:
        phases_log.append(copy.deepcopy(ev))
        if progress is not None:
            progress(ev)

    scan = scan_candidates_from_run_dir(run_dir, progress=_cb)
    out = normalize_and_schedule(scan, progress=_cb, preview_limit=preview_limit)
    out["progress_events"] = phases_log
    out["causal_chain"] = [
        "saved evidence",
        "authority selection (OATT > SAV1 > LEGACY osc)",
        "identity/lifetime segmentation",
        "gap/duplicate handling",
        "normalized A5 timeline",
        "SAV2-compatible deterministic schedule",
    ]
    return out


def reconstruct_from_candidate_lists(
    *,
    oatt_traces: list[dict[str, Any]] | None = None,
    sav1_receipts: list[dict[str, Any]] | None = None,
    legacy_observations: list[dict[str, Any]] | None = None,
    run_id: str = "fixture",
    runtime_generation: str = "0",
    preview_limit: int = PREVIEW_LIMIT_DEFAULT,
    progress: ProgressCb | None = None,
    force_incompatible_schedule: bool = False,
) -> dict[str, Any]:
    _emit(progress, "DISCOVER_FILES", processed=0, total=0)
    candidates: list[dict[str, Any]] = []
    ambiguous: list[dict[str, Any]] = []
    idx = 0
    for tr in oatt_traces or []:
        cand = _candidate_from_oatt(
            tr,
            run_id=str(tr.get("run_id") or run_id),
            runtime_generation=str(tr.get("runtime_generation", runtime_generation)),
            source_file="fixture_oatt",
            source_index=idx,
            consequence_tick=None,
        )
        idx += 1
        if cand and cand.get("ambiguous"):
            ambiguous.append(cand)
        elif cand:
            candidates.append(cand)
    for rec in sav1_receipts or []:
        cand = _candidate_from_sav1(
            rec,
            run_id=str(rec.get("run_id") or run_id),
            runtime_generation=str(rec.get("runtime_generation", runtime_generation)),
            source_file="fixture_sav1",
            source_index=idx,
            consequence_tick=None,
        )
        idx += 1
        if cand and cand.get("ambiguous"):
            ambiguous.append(cand)
        elif cand:
            candidates.append(cand)
    for row in legacy_observations or []:
        cand = _candidate_from_legacy_obs(
            row,
            run_id=str(row.get("run_id") or run_id),
            runtime_generation=str(row.get("runtime_generation", runtime_generation)),
            source_file="fixture_obs",
            source_index=idx,
        )
        idx += 1
        if cand and cand.get("ambiguous"):
            ambiguous.append(cand)
        elif cand:
            candidates.append(cand)
    _emit(progress, "SCAN_RECORDS", processed=idx, total=idx)
    _emit(progress, "CLASSIFY_SCHEMAS", processed=len(candidates), total=len(candidates))
    scan = {
        "inventory": {
            "accepted": [{"filename": "fixture", "role": "fixture"}],
            "ignored_unknown": [],
            "missing_expected": [],
            "diagnostics": [],
        },
        "run_id": run_id,
        "default_runtime_generation": runtime_generation,
        "candidates": candidates,
        "ambiguous": ambiguous,
        "ignored_non_a5_kinds": [],
        "empty_event_refs_rows": 0,
        "empty_event_refs_means": "NO_REFERENCES_RECORDED_NOT_NO_AUDITORY_EVENTS",
        "scanned_record_count": idx,
        "stream_used_as_a5_authority": False,
        "probe_used_as_a5_authority": False,
        "cognition_used_as_a5_authority": False,
        "pixels_used_as_a5_authority": False,
    }
    return normalize_and_schedule(
        scan,
        progress=progress,
        preview_limit=preview_limit,
        force_incompatible_schedule=force_incompatible_schedule,
    )


def observer_sav4a_payload(
    world: Any,
    *,
    selected_agent_id: str | None = None,
    selected_body_id: str | None = None,
    run_id: str = "live",
    runtime_generation: str | int | None = None,
) -> dict[str, Any]:
    """Normalize live tip OATT/SAV1 histories (read-only). Not a saved-package substitute."""
    gen = str(
        runtime_generation
        if runtime_generation is not None
        else getattr(world, "runtime_generation", "0")
    )
    oatt_traces: list[dict[str, Any]] = []
    sav1_receipts: list[dict[str, Any]] = []
    try:
        from mechanistic_mind.physical_system.organism_auditory_transformation_trace import (
            state_of as oatt_state_of,
        )

        st = oatt_state_of(world)
        if st is not None:
            for tr in list(st.traces or []):
                if not isinstance(tr, dict):
                    continue
                if selected_agent_id and str(tr.get("agent_id") or "") not in (
                    "",
                    str(selected_agent_id),
                ):
                    continue
                if selected_body_id and str(tr.get("body_id") or "") not in (
                    "",
                    str(selected_body_id),
                ):
                    continue
                oatt_traces.append(dict(tr))
    except Exception:
        pass
    try:
        from mechanistic_mind.physical_system.selected_organism_auditory_boundary_receipt import (
            state_of as sav1_state_of,
        )

        st1 = sav1_state_of(world)
        if st1 is not None:
            for rec in list(getattr(st1, "receipts", None) or []):
                if not isinstance(rec, dict):
                    continue
                if selected_agent_id and str(rec.get("agent_id") or "") not in (
                    "",
                    str(selected_agent_id),
                ):
                    continue
                if selected_body_id and str(rec.get("body_id") or "") not in (
                    "",
                    str(selected_body_id),
                ):
                    continue
                sav1_receipts.append(dict(rec))
    except Exception:
        pass

    out = reconstruct_from_candidate_lists(
        oatt_traces=oatt_traces,
        sav1_receipts=sav1_receipts,
        legacy_observations=None,
        run_id=str(run_id),
        runtime_generation=gen,
        preview_limit=32,
    )
    out["evidence_scope"] = "LIVE_TIP_HISTORY_NOT_FULL_SAVED_PACKAGE"
    out["selected_agent_id"] = selected_agent_id
    out["selected_body_id"] = selected_body_id
    out["selection_filters_display_only"] = True
    out["selection_does_not_alter_reconstruction_contents_note"] = (
        "UI selection filters the live tip view; Analyzer saved reconstruction is independent"
    )
    if not out.get("available"):
        out["status"] = LEGACY_UNAVAILABLE
        out["availability"] = "UNAVAILABLE"
    else:
        out["status"] = "LIVE_TIP_NORMALIZED"
        out["availability"] = "AVAILABLE"
    return out
