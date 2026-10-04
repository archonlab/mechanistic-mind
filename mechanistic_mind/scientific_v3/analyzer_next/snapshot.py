"""Frozen evidence snapshot for Analyzer jobs (read-only boundary).

Schema: ANALYZER_EVIDENCE_SNAPSHOT_V1
Does not copy evidence. Records immutable byte/record bounds so appended
runtime writes after job start are excluded. Partial final JSONL lines are
truncated to the last complete newline.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "ANALYZER_EVIDENCE_SNAPSHOT_V1"
CAPABILITY = "frozen_evidence_byte_boundary"
EVIDENCE_FILES = (
    "scientific_spine.jsonl",
    "scientific_decisions.jsonl",
    "scientific_timeline.jsonl",
    "scientific_events.jsonl",
    "scientific_observations.jsonl",
    "scientific_motors.jsonl",
    "scientific_consequences.jsonl",
)
META_FILES = (
    "scientific_v3_meta.json",
    "scientific_meta.json",
    "identity_map.json",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def last_complete_jsonl_byte_end(path: Path) -> int:
    """Return exclusive byte end of last complete newline-terminated record.

    Empty / missing → 0. Truncation mid-line is excluded (honest partial-record skip).
    """
    if not path.is_file():
        return 0
    size = int(path.stat().st_size)
    if size <= 0:
        return 0
    with path.open("rb") as f:
        # Find last newline within file.
        window = min(size, 1 << 20)
        f.seek(size - window)
        chunk = f.read(window)
        nl = chunk.rfind(b"\n")
        if nl < 0:
            # No complete line yet.
            return 0
        return (size - window) + nl + 1


def _spine_terminal_tick(path: Path, byte_end: int) -> int | None:
    if byte_end <= 0 or not path.is_file():
        return None
    mx: int | None = None
    with path.open("rb") as f:
        remaining = byte_end
        while remaining > 0:
            raw = f.readline()
            if not raw:
                break
            remaining -= len(raw)
            if remaining < 0:
                break
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(obj, dict) or "tick" not in obj:
                continue
            try:
                t = int(obj["tick"])
            except (TypeError, ValueError):
                continue
            mx = t if mx is None else max(mx, t)
    return mx


def build_evidence_snapshot(
    run_dir: Path | str,
    *,
    run_id: str | None = None,
    job_id: str | None = None,
    source: str = "current",
    runtime_generation: int | None = None,
) -> dict[str, Any]:
    """Build a frozen snapshot manifest for Analyzer. Never mutates evidence."""
    root = Path(run_dir)
    files: dict[str, Any] = {}
    for name in EVIDENCE_FILES:
        p = root / name
        size = int(p.stat().st_size) if p.is_file() else 0
        end = last_complete_jsonl_byte_end(p) if size else 0
        files[name] = {
            "path": name,
            "size_bytes": size,
            "byte_end": end,
            "truncated_partial_tail": bool(size > 0 and end < size),
            "present": p.is_file(),
        }
    meta_fingerprints: dict[str, Any] = {}
    for name in META_FILES:
        p = root / name
        if not p.is_file():
            continue
        try:
            meta_fingerprints[name] = {
                "size_bytes": int(p.stat().st_size),
                "mtime_ns": int(p.stat().st_mtime_ns),
            }
        except Exception:
            continue
    spine = files.get("scientific_spine.jsonl") or {}
    terminal = _spine_terminal_tick(root / "scientific_spine.jsonl", int(spine.get("byte_end") or 0))
    record_count_est = None
    # Cheap estimate: count newlines in spine within bound (bounded scan).
    sp = root / "scientific_spine.jsonl"
    be = int(spine.get("byte_end") or 0)
    if be > 0 and sp.is_file():
        n = 0
        with sp.open("rb") as f:
            read = 0
            while read < be:
                line = f.readline()
                if not line:
                    break
                read += len(line)
                if read <= be and line.strip():
                    n += 1
        record_count_est = n
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "snapshot_at": _now(),
        "job_id": job_id,
        "run_id": run_id or root.name,
        "source": source,
        "run_dir": str(root),
        "runtime_generation": runtime_generation,
        "snapshot_terminal_tick": terminal,
        "snapshot_record_count": record_count_est,
        "files": files,
        "meta_files": meta_fingerprints,
        "note": (
            "Operational snapshot boundary only — not a scientific result. "
            "Active analysis must not read past byte_end / snapshot_terminal_tick."
        ),
    }


def byte_limit_for(snapshot: dict[str, Any] | None, filename: str) -> int | None:
    if not snapshot:
        return None
    files = snapshot.get("files") or {}
    row = files.get(filename)
    if not isinstance(row, dict):
        return None
    if not row.get("present"):
        return 0
    return int(row.get("byte_end") or 0)


def detect_snapshot_violation(run_dir: Path | str, snapshot: dict[str, Any]) -> list[str]:
    """Return human-readable violations (truncation / replacement), if any."""
    root = Path(run_dir)
    issues: list[str] = []
    for name, row in (snapshot.get("files") or {}).items():
        if not isinstance(row, dict) or not row.get("present"):
            continue
        p = root / name
        if not p.is_file():
            issues.append(f"{name}: missing after snapshot")
            continue
        try:
            size = int(p.stat().st_size)
        except Exception:
            issues.append(f"{name}: unreadable")
            continue
        end = int(row.get("byte_end") or 0)
        # Shrink below frozen end = truncation/replacement.
        if size < end:
            issues.append(f"{name}: truncated below snapshot byte_end ({size}<{end})")
    return issues
