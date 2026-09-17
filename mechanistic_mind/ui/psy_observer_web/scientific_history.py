"""Append-only full-run scientific evidence for Psy Observer Web.

Separates the bounded LIVE UI timeline buffer from the authoritative
scientific archive used for later Analyzer re-analysis.

Storage (per run / live staging):
  scientific_timeline.jsonl  — one compact row per (simulation_tick, agent_id)
  scientific_events.jsonl    — structured events with stable IDs (append-only)
  scientific_meta.json       — identity + counters (rewritten occasionally)

Does NOT alter runtime physics/cognition. Reads only.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .run_finalize import RUN_SUBDIR, agent_summaries, default_results_root

SCHEMA_TICK = "mm.psy_observer_web.scientific_tick.v1"
SCHEMA_EVENT = "mm.psy_observer_web.scientific_event.v1"
SCHEMA_META = "mm.psy_observer_web.scientific_meta.v1"
ANALYZER_VERSION = "1.1.0"

# Buffered append cadence: flush every N ticks or on close (O(1) amortized).
DEFAULT_FLUSH_EVERY = 32


def live_scientific_dir(results_root: Path | str, run_id: str) -> Path:
    base = Path(results_root) / RUN_SUBDIR
    return base / f".live-{run_id}"


def published_run_dir(results_root: Path | str, run_id: str) -> Path:
    return Path(results_root) / RUN_SUBDIR / run_id


def _jsonl_line(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _resource_sum(body: Any, attr: str) -> float | None:
    arr = getattr(body, attr, None)
    if arr is None:
        return None
    try:
        return float(arr.sum())
    except Exception:
        try:
            return float(sum(arr))
        except Exception:
            return None


def _contact_flag(runtime: Any) -> bool:
    lc = getattr(runtime, "last_contact", None)
    if isinstance(lc, dict):
        return bool(lc.get("contact"))
    return False


def collect_scientific_tick_rows(runtime: Any) -> list[dict[str, Any]]:
    """Compact per-(tick, agent) rows for analysis (not UI/render state)."""
    tick = int(runtime.tick)
    contact = _contact_flag(runtime)
    slots = getattr(runtime, "slots", None)
    rows: list[dict[str, Any]] = []
    if slots:
        for i, slot in enumerate(slots):
            rows.append(_row_for_slot(tick, i, slot, contact=contact))
        return rows
    rows.append(_row_for_slot(tick, 0, runtime, contact=contact))
    return rows


def _row_for_slot(tick: int, index: int, slot: Any, *, contact: bool) -> dict[str, Any]:
    body = slot.body
    sel = {}
    cog = getattr(slot, "cognition", None)
    if isinstance(cog, dict):
        sel = cog.get("last_selection") or {}
        metrics = cog.get("metrics") or {}
    else:
        metrics = {}
    work_alloc = getattr(slot, "last_work_allocation", None) or {}
    vx = float(getattr(body, "vx", 0.0) or 0.0)
    vy = float(getattr(body, "vy", 0.0) or 0.0)
    return {
        "schema": SCHEMA_TICK,
        "tick": tick,
        "agent_id": f"agent_{index}",
        "body_id": f"body-{index}",
        "action": getattr(slot, "last_selected_action", None),
        "action_source": sel.get("source"),
        "x": float(getattr(body, "x", 0.0) or 0.0),
        "y": float(getattr(body, "y", 0.0) or 0.0),
        "theta": float(getattr(body, "theta", 0.0) or 0.0),
        "vx": vx,
        "vy": vy,
        "speed": float((vx * vx + vy * vy) ** 0.5),
        "work": float(getattr(body, "mechanical_work_reservoir", 0.0) or 0.0),
        "resource_A": _resource_sum(body, "R_A_site"),
        "resource_B": _resource_sum(body, "R_B_site"),
        "contact": bool(contact),
        "prediction_count": metrics.get("prediction_count"),
        "prospective_compositions": metrics.get("prospective_compositions"),
        "work_action_allocated": float(work_alloc.get("allocated_action") or 0.0)
        if work_alloc
        else None,
        "agent_seed": int(getattr(slot, "seed", 0) or 0),
    }


def event_stable_key(ev: dict[str, Any]) -> str:
    evidence = ev.get("evidence") if isinstance(ev.get("evidence"), dict) else {}
    parts = (
        str(ev.get("event_id") or evidence.get("event_id") or ""),
        str(ev.get("emission_id") or evidence.get("emission_id") or ""),
        str(ev.get("receipt_id") or evidence.get("receipt_id") or ""),
        str(int(ev.get("tick") or -1)),
        str(ev.get("type") or ev.get("kind") or ""),
        str(ev.get("agent_id") or ev.get("actor_agent_id") or ""),
        str(ev.get("emitter_agent_id") or evidence.get("emitter_agent_id") or ""),
        str(ev.get("receiver_agent_id") or evidence.get("receiver_agent_id") or ""),
        str(evidence.get("selected_action") or evidence.get("action") or ""),
    )
    return "|".join(parts)


def scientific_rows_to_timeline_events(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group per-agent scientific rows into tick events compatible with Analyzer ingest."""
    by_tick: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            tick = int(row["tick"])
        except (KeyError, TypeError, ValueError):
            continue
        ev = by_tick.get(tick)
        if ev is None:
            ev = {
                "tick": tick,
                "contact": bool(row.get("contact")),
                "agent_id": row.get("agent_id") or "agent_0",
                "action": row.get("action"),
                "action_source": row.get("action_source"),
                "body_xy": {"x": row.get("x"), "y": row.get("y")},
                "bodies": [],
                "source": "scientific_timeline",
            }
            by_tick[tick] = ev
        else:
            ev["contact"] = bool(ev.get("contact")) or bool(row.get("contact"))
        ev["bodies"].append({
            "agent_id": row.get("agent_id") or "agent_0",
            "body_id": row.get("body_id"),
            "x": row.get("x"),
            "y": row.get("y"),
            "theta": row.get("theta"),
            "action": row.get("action"),
            "action_source": row.get("action_source"),
            "work": row.get("work"),
            "resource_A": row.get("resource_A"),
            "resource_B": row.get("resource_B"),
            "speed": row.get("speed"),
            "prediction_count": row.get("prediction_count"),
            "prospective_compositions": row.get("prospective_compositions"),
            "agent_seed": row.get("agent_seed"),
        })
    return [by_tick[t] for t in sorted(by_tick)]


def iter_jsonl(path: Path, *, max_tick: int | None = None) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(row, dict):
                continue
            if max_tick is not None and "tick" in row:
                try:
                    if int(row["tick"]) > int(max_tick):
                        continue
                except (TypeError, ValueError):
                    pass
            out.append(row)
    return out


def read_jsonl_range(path: Path) -> tuple[int | None, int | None, int]:
    """Return (min_tick, max_tick, row_count) without loading full payloads into analysis."""
    if not path.is_file():
        return None, None, 0
    mn: int | None = None
    mx: int | None = None
    n = 0
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                t = int(row["tick"])
            except (json.JSONDecodeError, KeyError, TypeError, ValueError):
                continue
            n += 1
            mn = t if mn is None else min(mn, t)
            mx = t if mx is None else max(mx, t)
    return mn, mx, n


class ScientificHistoryWriter:
    """Buffered append-only writer. Safe to flush while runtime continues."""

    def __init__(self, directory: Path, *, flush_every: int = DEFAULT_FLUSH_EVERY) -> None:
        self.directory = Path(directory)
        self.timeline_path = self.directory / "scientific_timeline.jsonl"
        self.events_path = self.directory / "scientific_events.jsonl"
        self.meta_path = self.directory / "scientific_meta.json"
        self.flush_every = max(1, int(flush_every))
        self._lock = threading.Lock()
        self._tl_buf: list[str] = []
        self._ev_buf: list[str] = []
        self._last_tick_written = -1
        self._rows_written = 0
        self._events_written = 0
        self._seen_event_keys: set[str] = set()
        self._identity: dict[str, Any] = {}
        self._opened = False

    def open(self, identity: dict[str, Any] | None = None) -> None:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._identity = dict(identity or {})
            self._identity.setdefault("schema", SCHEMA_META)
            self._identity.setdefault("analyzer_compatible_version", ANALYZER_VERSION)
            self._identity.setdefault("opened_at", datetime.now(timezone.utc).isoformat())
            # Resume counters if files already exist (Observer restart mid-run).
            if self.timeline_path.is_file():
                _mn, mx, n = read_jsonl_range(self.timeline_path)
                if mx is not None:
                    self._last_tick_written = mx
                self._rows_written = n
            if self.events_path.is_file():
                for row in iter_jsonl(self.events_path):
                    self._seen_event_keys.add(event_stable_key(row))
                    self._events_written += 1
            self._write_meta_unlocked(flush_bufs=False)
            self._opened = True

    def append_tick(self, runtime: Any) -> int:
        """Append scientific rows for current runtime.tick if not already written.

        Returns number of new rows appended (0 if duplicate tick).
        """
        rows = collect_scientific_tick_rows(runtime)
        if not rows:
            return 0
        tick = int(rows[0]["tick"])
        with self._lock:
            if not self._opened:
                self.open()
            if tick <= self._last_tick_written:
                return 0
            for row in rows:
                self._tl_buf.append(_jsonl_line(row))
            self._last_tick_written = tick
            self._rows_written += len(rows)
            if len(self._tl_buf) >= self.flush_every:
                self._flush_unlocked()
            return len(rows)

    def append_events(self, events: Iterable[dict[str, Any]]) -> int:
        added = 0
        with self._lock:
            if not self._opened:
                self.open()
            for ev in events:
                if not isinstance(ev, dict):
                    continue
                key = event_stable_key(ev)
                if key in self._seen_event_keys:
                    continue
                self._seen_event_keys.add(key)
                payload = dict(ev)
                payload.setdefault("schema", SCHEMA_EVENT)
                self._ev_buf.append(_jsonl_line(payload))
                self._events_written += 1
                added += 1
            if len(self._ev_buf) >= self.flush_every:
                self._flush_unlocked()
        return added

    def flush(self) -> None:
        with self._lock:
            self._flush_unlocked()

    def close(self) -> None:
        with self._lock:
            self._flush_unlocked()
            self._identity["closed_at"] = datetime.now(timezone.utc).isoformat()
            self._write_meta_unlocked(flush_bufs=False)
            self._opened = False

    def _flush_unlocked(self) -> None:
        if self._tl_buf:
            with self.timeline_path.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(self._tl_buf))
                fh.write("\n")
            self._tl_buf.clear()
        if self._ev_buf:
            with self.events_path.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(self._ev_buf))
                fh.write("\n")
            self._ev_buf.clear()
        self._write_meta_unlocked(flush_bufs=False)

    def _write_meta_unlocked(self, *, flush_bufs: bool) -> None:
        if flush_bufs:
            self._flush_unlocked()
            return
        meta = {
            **self._identity,
            "schema": SCHEMA_META,
            "timeline_path": self.timeline_path.name,
            "events_path": self.events_path.name,
            "rows_written": self._rows_written,
            "events_written": self._events_written,
            "last_tick_written": self._last_tick_written if self._last_tick_written >= 0 else None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        tmp = self.meta_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2, default=str), encoding="utf-8")
        os.replace(tmp, self.meta_path)


def copy_scientific_into(run_dir: Path, live_dir: Path | None) -> dict[str, Any]:
    """Copy scientific evidence files into a finalized run directory."""
    import shutil

    info: dict[str, Any] = {"copied": False, "files": []}
    if live_dir is None or not Path(live_dir).is_dir():
        return info
    live = Path(live_dir)
    for name in ("scientific_timeline.jsonl", "scientific_events.jsonl", "scientific_meta.json"):
        src = live / name
        if src.is_file():
            dst = Path(run_dir) / name
            shutil.copy2(src, dst)
            info["files"].append(name)
    info["copied"] = bool(info["files"])
    return info


def extract_cumulative_summaries(runtime: Any | None = None, *, snapshot: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Runtime cumulative counters — NOT tick-level history."""
    if runtime is not None:
        try:
            summaries = agent_summaries(runtime)
            out = []
            for s in summaries:
                out.append({
                    "agent_id": s.get("observer_id") or s.get("agent_id"),
                    "agent_seed": s.get("agent_seed"),
                    "action_counts": dict(s.get("action_counts") or {}),
                    "wait_count": s.get("wait_count"),
                    "move_count": s.get("move_count"),
                    "distance_travelled": s.get("distance_travelled"),
                    "unique_cells_visited": s.get("unique_cells_visited"),
                    "collision_count": s.get("collision_count"),
                    "cognition_ticks": s.get("cognition_ticks"),
                    "prediction_count": s.get("prediction_count"),
                    "prospective_compositions": s.get("prospective_compositions"),
                    "evidence_class": "CUMULATIVE_RUNTIME_SUMMARY",
                })
            return out
        except Exception:
            pass
    if snapshot and isinstance(snapshot, dict):
        # Best-effort from snapshot slots if present
        slots = snapshot.get("slots") or snapshot.get("agents") or []
        out = []
        for i, slot in enumerate(slots if isinstance(slots, list) else []):
            if not isinstance(slot, dict):
                continue
            cog = slot.get("cognition") or {}
            metrics = cog.get("metrics") if isinstance(cog, dict) else {}
            counts = (metrics or {}).get("action_counts") or {}
            out.append({
                "agent_id": f"agent_{i}",
                "action_counts": dict(counts),
                "evidence_class": "CUMULATIVE_RUNTIME_SUMMARY",
            })
        return out
    return []


def classify_evidence_coverage(
    *,
    scientific_tick_min: int | None,
    scientific_tick_max: int | None,
    scientific_row_count: int,
    agent_count: int,
    expected_start: int = 1,
    final_or_cutoff_tick: int | None,
    ui_timeline_min: int | None = None,
    ui_timeline_max: int | None = None,
    has_cumulative: bool = False,
) -> dict[str, Any]:
    """FULL iff scientific timeline covers [expected_start .. cutoff] without gaps in tick set size."""
    cutoff = final_or_cutoff_tick
    if scientific_row_count <= 0 or scientific_tick_min is None or scientific_tick_max is None:
        # Fall back to bounded UI timeline → always PARTIAL for full-run claims
        return {
            "coverage": "PARTIAL",
            "tick_level_reconstruction": "PARTIAL",
            "complete_tick_level_reanalysis": False,
            "scientific_timeline_available": (
                f"{ui_timeline_min}–{ui_timeline_max}"
                if ui_timeline_min is not None and ui_timeline_max is not None
                else "NONE"
            ),
            "full_runtime_cumulative_counters_available": bool(has_cumulative),
            "reason": (
                "No scientific_timeline.jsonl; only bounded session_timeline / buffers may exist. "
                "Cannot claim complete tick-level re-analysis."
            ),
            "evidence_source": "legacy_ui_buffers",
        }

    agents = max(1, int(agent_count or 1))
    # Unique ticks approximated: rows / agents (exact unique count preferred by callers when known)
    expected_ticks = None
    if cutoff is not None:
        expected_ticks = max(0, int(cutoff) - int(expected_start) + 1)
    # FULL if starts at/near run start and reaches cutoff, with enough rows
    starts_ok = scientific_tick_min <= expected_start + 1  # tick 0 or 1 both acceptable
    ends_ok = cutoff is None or scientific_tick_max >= int(cutoff)
    density_ok = True
    if expected_ticks is not None and expected_ticks > 0:
        # Allow tiny startup skew; require near-complete row count
        density_ok = scientific_row_count >= int(expected_ticks * agents * 0.98)

    if starts_ok and ends_ok and density_ok:
        return {
            "coverage": "FULL",
            "tick_level_reconstruction": "FULL",
            "complete_tick_level_reanalysis": True,
            "scientific_timeline_available": f"{scientific_tick_min}–{scientific_tick_max}",
            "full_runtime_cumulative_counters_available": bool(has_cumulative),
            "reason": "Complete scientific_timeline.jsonl from run start through analysis cutoff.",
            "evidence_source": "scientific_timeline",
        }

    return {
        "coverage": "PARTIAL",
        "tick_level_reconstruction": "PARTIAL",
        "complete_tick_level_reanalysis": False,
        "scientific_timeline_available": f"{scientific_tick_min}–{scientific_tick_max}",
        "full_runtime_cumulative_counters_available": bool(has_cumulative),
        "reason": (
            "Scientific timeline present but does not cover the full requested range "
            f"(start={scientific_tick_min}, end={scientific_tick_max}, cutoff={cutoff})."
        ),
        "evidence_source": "scientific_timeline",
    }


def load_evidence_package(
    *,
    evidence_dir: Path | None = None,
    runtime: Any | None = None,
    ui_timeline: list[dict[str, Any]] | None = None,
    ui_events: list[dict[str, Any]] | None = None,
    cutoff_tick: int | None = None,
    runtime_status: str = "UNKNOWN",
    run_id: str | None = None,
    identity: dict[str, Any] | None = None,
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Load scientific evidence for Analyzer (read-only).

    Prefer scientific_timeline.jsonl; fall back to bounded UI timeline as PARTIAL.
    """
    identity = dict(identity or {})
    sci_rows: list[dict[str, Any]] = []
    sci_events: list[dict[str, Any]] = []
    evidence_files: list[str] = []
    sci_dir = Path(evidence_dir) if evidence_dir else None

    if sci_dir and sci_dir.is_dir():
        tl_path = sci_dir / "scientific_timeline.jsonl"
        ev_path = sci_dir / "scientific_events.jsonl"
        if tl_path.is_file():
            sci_rows = iter_jsonl(tl_path, max_tick=cutoff_tick)
            evidence_files.append("scientific_timeline.jsonl")
        if ev_path.is_file():
            sci_events = iter_jsonl(ev_path, max_tick=cutoff_tick)
            evidence_files.append("scientific_events.jsonl")
        if (sci_dir / "scientific_meta.json").is_file():
            evidence_files.append("scientific_meta.json")

    agent_count = int(identity.get("agent_count") or 1)
    if sci_rows:
        agent_ids = {str(r.get("agent_id")) for r in sci_rows if r.get("agent_id")}
        if agent_ids:
            agent_count = max(agent_count, len(agent_ids))

    sci_ticks = [int(r["tick"]) for r in sci_rows if "tick" in r]
    sci_min = min(sci_ticks) if sci_ticks else None
    sci_max = max(sci_ticks) if sci_ticks else None

    ui_min = ui_max = None
    if ui_timeline:
        ut = []
        for ev in ui_timeline:
            try:
                t = int(ev["tick"])
            except (KeyError, TypeError, ValueError):
                continue
            if cutoff_tick is not None and t > int(cutoff_tick):
                continue
            ut.append(t)
        if ut:
            ui_min, ui_max = min(ut), max(ut)

    cumulative = extract_cumulative_summaries(runtime, snapshot=snapshot)
    # Also try snapshot file in evidence dir
    if not cumulative and sci_dir:
        snap_path = sci_dir / "physical_system_snapshot.json"
        if snap_path.is_file():
            try:
                snap = json.loads(snap_path.read_text(encoding="utf-8"))
                cumulative = extract_cumulative_summaries(snapshot=snap)
                if "physical_system_snapshot.json" not in evidence_files:
                    evidence_files.append("physical_system_snapshot.json")
            except Exception:
                pass

    effective_cutoff = cutoff_tick
    if effective_cutoff is None:
        effective_cutoff = sci_max if sci_max is not None else ui_max

    coverage = classify_evidence_coverage(
        scientific_tick_min=sci_min,
        scientific_tick_max=sci_max,
        scientific_row_count=len(sci_rows),
        agent_count=agent_count,
        expected_start=1,
        final_or_cutoff_tick=effective_cutoff,
        ui_timeline_min=ui_min,
        ui_timeline_max=ui_max,
        has_cumulative=bool(cumulative),
    )

    if sci_rows:
        timeline_events = scientific_rows_to_timeline_events(sci_rows)
        events = sci_events
        analyzed_start, analyzed_end = sci_min, sci_max
    else:
        # Legacy PARTIAL path — UI buffer only
        timeline_events = []
        if ui_timeline:
            for ev in ui_timeline:
                try:
                    t = int(ev["tick"])
                except (KeyError, TypeError, ValueError):
                    continue
                if cutoff_tick is not None and t > int(cutoff_tick):
                    continue
                timeline_events.append(ev)
            evidence_files.append("session_timeline.jsonl")
        events = list(ui_events or [])
        if events and "structured_events" not in "".join(evidence_files):
            evidence_files.append("structured_events.json")
        analyzed_start, analyzed_end = ui_min, ui_max
        coverage["evidence_source"] = "legacy_ui_buffers"

    return {
        "schema": "mm.psy_observer_web.evidence_package.v1",
        "analyzer_version": ANALYZER_VERSION,
        "run_id": run_id,
        "runtime_status": runtime_status,
        "analysis_cutoff_tick": effective_cutoff,
        "scientific_tick_range": [analyzed_start, analyzed_end],
        "coverage": coverage.get("coverage"),
        "coverage_detail": coverage,
        "complete_tick_level_reanalysis": coverage.get("complete_tick_level_reanalysis"),
        "evidence_files": evidence_files,
        "evidence_counts": {
            "scientific_rows": len(sci_rows),
            "timeline_events": len(timeline_events),
            "events": len(events),
            "cumulative_agent_summaries": len(cumulative),
        },
        "identity": identity,
        "timeline": timeline_events,
        "scientific_rows": sci_rows,
        "events": events,
        "cumulative_runtime_summaries": cumulative,
        "used_cumulative_runtime_summaries": bool(cumulative),
        "note": (
            "Cumulative runtime summaries are NOT tick-level history. "
            "They must not be presented as reconstructed transition timing or streak structure."
        ),
    }


def list_psyweb_runs(results_root: Path | str | None = None) -> list[dict[str, Any]]:
    root = Path(results_root) if results_root else default_results_root()
    base = root / RUN_SUBDIR
    if not base.is_dir():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(base.iterdir(), reverse=True):
        if not p.is_dir():
            continue
        name = p.name
        if name.startswith(".tmp-") or name.startswith(".live-"):
            continue
        if not name.startswith("psyweb-"):
            continue
        manifest = {}
        mj = p / "run.json"
        if mj.is_file():
            try:
                manifest = json.loads(mj.read_text(encoding="utf-8"))
            except Exception:
                manifest = {}
        sci = p / "scientific_timeline.jsonl"
        sci_min, sci_max, sci_n = read_jsonl_range(sci) if sci.is_file() else (None, None, 0)
        out.append({
            "run_id": name,
            "run_dir": str(p),
            "final_tick": manifest.get("final_tick"),
            "seed": manifest.get("seed"),
            "runtime_type": manifest.get("runtime_type") or manifest.get("runtime"),
            "agent_count": manifest.get("agent_count"),
            "termination_reason": manifest.get("termination_reason"),
            "has_scientific_timeline": sci.is_file(),
            "scientific_tick_range": [sci_min, sci_max] if sci_n else None,
            "scientific_row_count": sci_n,
            "has_session_timeline": (p / "session_timeline.jsonl").is_file(),
            "stopped_at": manifest.get("stopped_at") or manifest.get("finalized_at"),
        })
    return out


def save_analysis_output(
    run_dir: Path,
    *,
    report_text: str,
    report_json: dict[str, Any],
    stamp: datetime | None = None,
) -> Path:
    """Write versioned analysis output; never overwrite prior analyses."""
    ts = (stamp or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S.%fZ")
    out_dir = Path(run_dir) / "analysis" / ts
    out_dir.mkdir(parents=True, exist_ok=False)
    (out_dir / "report.txt").write_text(report_text, encoding="utf-8")
    (out_dir / "report.json").write_text(
        json.dumps(report_json, ensure_ascii=False, sort_keys=True, indent=2, default=str),
        encoding="utf-8",
    )
    return out_dir
