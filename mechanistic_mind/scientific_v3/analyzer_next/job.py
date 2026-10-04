"""Isolated Analyzer job: subprocess worker + progress file.

Never writes into the source run directory. Observer remains a separate process.
Progress schema: ANALYZER_JOB_PROGRESS_V1 (heartbeat ≠ meaningful progress).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROGRESS_SCHEMA = "ANALYZER_JOB_PROGRESS_V1"
LOG_BOUND = 48
HEARTBEAT_INTERVAL_S = 2.0

# Canonical progress phases (user-facing contract). Internal pipeline phases map into these.
PROGRESS_PHASES = (
    "DISCOVER_EVIDENCE",
    "LOAD_AND_VALIDATE",
    "NORMALIZE_RECORDS",
    "BUILD_TICK_STORIES",
    "RECONSTRUCT_PHYSICAL_CAUSALITY",
    "BUILD_SUMMARIES",
    "RENDER_EXPORT_PAYLOADS",
    "COMPLETE",
    "FAILED",
    "CANCELLED",
)

# Legacy / pipeline phase → canonical
_PHASE_MAP = {
    "QUEUED": "DISCOVER_EVIDENCE",
    "READING": "LOAD_AND_VALIDATE",
    "RECONSTRUCTING": "BUILD_TICK_STORIES",
    "EPISODES": "RECONSTRUCT_PHYSICAL_CAUSALITY",
    "INDEX_PHYSICAL_RECEIPTS": "RECONSTRUCT_PHYSICAL_CAUSALITY",
    "LINK_REACH_CONTACT": "RECONSTRUCT_PHYSICAL_CAUSALITY",
    "CLASSIFY_NEGATIVE_CAUSES": "RECONSTRUCT_PHYSICAL_CAUSALITY",
    "AGGREGATING": "BUILD_SUMMARIES",
    "WRITING": "RENDER_EXPORT_PAYLOADS",
    "COMPLETE": "COMPLETE",
    "FAILED": "FAILED",
    "CANCELLED": "CANCELLED",
}

# Keep old PHASES export for callers that import it.
PHASES = (
    "QUEUED",
    "READING",
    "RECONSTRUCTING",
    "EPISODES",
    "AGGREGATING",
    "WRITING",
    "COMPLETE",
    "FAILED",
    "CANCELLED",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_phase(phase: str) -> str:
    p = str(phase or "")
    return _PHASE_MAP.get(p, p if p in PROGRESS_PHASES else "LOAD_AND_VALIDATE")


def _phase_index(canonical: str) -> int:
    try:
        return list(PROGRESS_PHASES).index(canonical)
    except ValueError:
        return 0


def write_progress(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    now = _now()
    payload["schema"] = PROGRESS_SCHEMA
    payload.setdefault("updated_at", now)
    payload.setdefault("worker_heartbeat_at", payload.get("updated_at"))
    # Ensure contract fields
    can = _canonical_phase(str(payload.get("phase") or ""))
    payload["phase"] = can
    payload["phase_id"] = can
    payload["phase_label"] = str(payload.get("phase_label") or can.replace("_", " ").title())
    payload["phase_index"] = int(payload.get("phase_index") if payload.get("phase_index") is not None else _phase_index(can))
    payload["phase_count"] = len([p for p in PROGRESS_PHASES if p not in ("FAILED", "CANCELLED")])
    terminal = can in ("COMPLETE", "FAILED", "CANCELLED")
    payload["terminal"] = bool(terminal)
    if "percent" not in payload:
        payload["percent"] = None
    # Alias fields for ANALYZER_JOB_PROGRESS_V1
    payload.setdefault("phase_processed", payload.get("completed_units"))
    payload.setdefault("phase_total", payload.get("total_units"))
    payload.setdefault("overall_processed", payload.get("completed_units"))
    payload.setdefault("overall_total", payload.get("total_units"))
    payload.setdefault("unit_label", payload.get("unit_label") or "units")
    payload.setdefault("message", payload.get("status_text"))
    payload.setdefault("recent_log", payload.get("recent_log") or [])
    if len(payload["recent_log"]) > LOG_BOUND:
        payload["recent_log"] = list(payload["recent_log"])[-LOG_BOUND:]
    tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def cancel_requested(out_dir: Path) -> bool:
    return (out_dir / "CANCEL").is_file()


class ProgressReporter:
    """Thread-safe progress + heartbeat + bounded operational log."""

    def __init__(self, *, out_dir: Path, state: dict[str, Any], progress_path: Path, t0: float) -> None:
        self.out_dir = Path(out_dir)
        self.state = state
        self.progress_path = Path(progress_path)
        self.t0 = float(t0)
        self._lock = threading.Lock()
        self._log: deque[dict[str, Any]] = deque(maxlen=LOG_BOUND)
        self._stop = threading.Event()
        self._last_progress_mono = time.perf_counter()
        self._last_n = 0
        self._thread = threading.Thread(target=self._heartbeat_loop, name="analyzer-heartbeat", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self._thread.join(timeout=2.0)
        except Exception:
            pass

    def log(self, message: str) -> None:
        msg = str(message or "").strip()
        if not msg:
            return
        # Never expose absolute developer home paths in operational log.
        msg = msg.replace(str(Path.home()), "~")
        if "/home/" in msg:
            msg = msg.split("/home/")[0] + "…/" + msg.rsplit("/", 1)[-1]
        entry = {"ts": _now(), "message": msg[:240]}
        with self._lock:
            self._log.append(entry)
            self.state["recent_log"] = list(self._log)
            self.state["updated_at"] = entry["ts"]
            self.state["worker_heartbeat_at"] = entry["ts"]
            write_progress(self.progress_path, dict(self.state))

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(HEARTBEAT_INTERVAL_S):
            with self._lock:
                if self.state.get("terminal"):
                    break
                now = _now()
                self.state["updated_at"] = now
                self.state["worker_heartbeat_at"] = now
                self.state["elapsed_seconds"] = round(time.perf_counter() - self.t0, 3)
                self.state["elapsed_s"] = self.state["elapsed_seconds"]
                # Do NOT bump last_progress_at — heartbeat ≠ meaningful progress.
                write_progress(self.progress_path, dict(self.state))

    def __call__(
        self,
        phase: str,
        n: int = 0,
        tick: int = 0,
        *,
        status_text: str | None = None,
        operation: str | None = None,
        unit_label: str | None = None,
        meaningful: bool = True,
        **_extra: Any,
    ) -> None:
        if cancel_requested(self.out_dir):
            raise KeyboardInterrupt("CANCELLED")
        total = None
        if isinstance(tick, int) and tick > 0 and int(n) <= int(tick):
            # Prefer tick as total when it looks like a bound (existing contract).
            if str(phase) in (
                "RECONSTRUCTING",
                "CLASSIFY_NEGATIVE_CAUSES",
                "INDEX_PHYSICAL_RECEIPTS",
                "LINK_REACH_CONTACT",
                "AGGREGATING",
                "BUILD_SUMMARIES",
                "WRITING",
                "EPISODES",
            ):
                total = int(tick)
        self.emit(
            phase,
            n=int(n),
            total=total,
            tick=tick if isinstance(tick, int) else None,
            status_text=status_text,
            operation=operation,
            unit_label=unit_label,
            meaningful=meaningful,
        )

    def emit(
        self,
        phase: str,
        *,
        n: int = 0,
        total: int | None = None,
        tick: int | None = None,
        status_text: str | None = None,
        operation: str | None = None,
        unit_label: str | None = None,
        meaningful: bool = True,
    ) -> None:
        can = _canonical_phase(phase)
        idx = _phase_index(can)
        phase_count = len([p for p in PROGRESS_PHASES if p not in ("FAILED", "CANCELLED")])
        with self._lock:
            last_percent = float(self.state.get("percent") or 0.0)
            prev_phase = _canonical_phase(str(self.state.get("phase_id") or self.state.get("phase") or ""))
            prev_idx = int(self.state.get("phase_index") or 0)
            # Nested callbacks must not regress the published phase ladder.
            if can not in ("FAILED", "CANCELLED") and idx < prev_idx:
                can = prev_phase
                idx = prev_idx
            prev_proc = int(self.state.get("phase_processed") or 0)
            prev_tot = self.state.get("phase_total")
            prev_overall = int(self.state.get("overall_processed") or 0)
            # Nested sub-ops may report a different unit scale; never regress within a phase.
            n_use = int(n)
            tot_use = None if total is None else int(total)
            if can == prev_phase and can not in ("COMPLETE", "FAILED", "CANCELLED"):
                n_use = max(prev_proc, n_use)
                if tot_use is not None and prev_tot is not None:
                    prev_tot_i = int(prev_tot)
                    if prev_tot_i >= n_use and tot_use < prev_tot_i and prev_proc > tot_use:
                        tot_use = prev_tot_i
                if tot_use is not None and n_use > tot_use:
                    tot_use = n_use
            elif tot_use is not None and n_use > tot_use:
                tot_use = n_use
            base = (100.0 * idx) / max(1, phase_count - 1)
            if can == "COMPLETE":
                pct: float | None = 100.0
            elif can in ("FAILED", "CANCELLED"):
                pct = last_percent
            elif tot_use is not None and int(tot_use) > 0:
                within = 100.0 * float(n_use) / float(tot_use)
                next_base = (100.0 * min(idx + 1, phase_count - 1)) / max(1, phase_count - 1)
                pct = min(next_base - 0.01, base + (next_base - base) * (within / 100.0))
            else:
                pct = None if tot_use is None and n_use == 0 and can in ("DISCOVER_EVIDENCE", "LOAD_AND_VALIDATE") else base
            if pct is not None:
                pct = max(last_percent, float(pct))
            now = _now()
            elapsed = time.perf_counter() - self.t0
            rate = None
            if meaningful and n_use > self._last_n and elapsed > 0:
                # Overall average rate since start (honest, not fabricated instantaneous spike).
                rate = round(float(n_use) / max(1e-6, elapsed), 2)
            if meaningful:
                self._last_progress_mono = time.perf_counter()
                self.state["last_progress_at"] = now
                self._last_n = max(self._last_n, int(n_use))
            overall_n = max(prev_overall, n_use)
            if can != prev_phase and can not in ("FAILED", "CANCELLED"):
                # Phase transitions always advance overall work by at least one unit.
                overall_n = max(overall_n, prev_overall + 1)
            snap_tot = self.state.get("snapshot_record_count")
            overall_tot = tot_use
            if snap_tot is not None:
                try:
                    overall_tot = max(int(snap_tot), int(tot_use or 0), overall_n)
                except (TypeError, ValueError):
                    overall_tot = tot_use
            op = operation or self.state.get("current_operation")
            text = status_text or (
                f"{can}"
                + (f" · {op}" if op else "")
                + f" · units={n_use}"
                + (f"/{tot_use}" if tot_use is not None else "")
            )
            self.state.update(
                {
                    "phase": can,
                    "phase_id": can,
                    "phase_label": can.replace("_", " ").title(),
                    "phase_index": idx,
                    "phase_count": phase_count,
                    "completed_units": int(n_use),
                    "total_units": None if tot_use is None else int(tot_use),
                    "phase_processed": int(n_use),
                    "phase_total": None if tot_use is None else int(tot_use),
                    "overall_processed": int(overall_n),
                    "overall_total": None if overall_tot is None else int(overall_tot),
                    "percent": None if pct is None else round(float(pct), 2),
                    "status_text": text,
                    "message": text,
                    "ticks_reconstructed": int(n_use),
                    "records_processed": int(n_use),
                    "last_tick_processed": tick,
                    "elapsed_s": round(elapsed, 3),
                    "elapsed_seconds": round(elapsed, 3),
                    "records_per_second": rate,
                    "unit_label": unit_label or self.state.get("unit_label") or "ticks",
                    "current_operation": op,
                    "updated_at": now,
                    "worker_heartbeat_at": now,
                    "terminal": can in ("COMPLETE", "FAILED", "CANCELLED"),
                    "recent_log": list(self._log),
                }
            )
            if can == "COMPLETE":
                self.state["state"] = "COMPLETED"
            elif can == "FAILED":
                self.state["state"] = "FAILED"
            elif can == "CANCELLED":
                self.state["state"] = "CANCELLED"
            elif self.state.get("state") == "QUEUED":
                self.state["state"] = "RUNNING"
            else:
                self.state.setdefault("state", "RUNNING")
                if self.state["state"] not in ("CANCEL_REQUESTED", "CANCELLED", "FAILED", "COMPLETED"):
                    self.state["state"] = "RUNNING"
            write_progress(self.progress_path, dict(self.state))
            if meaningful:
                # Bounded operational milestones (not per-record spam).
                prev_op = getattr(self, "_last_logged_op", None)
                should_log = can != prev_phase or (operation and operation != prev_op)
                if should_log and (operation or status_text or can != prev_phase):
                    self._last_logged_op = operation or can
                    msg = status_text or f"{can}" + (f" · {operation}" if operation else "")
                    if tot_use is not None:
                        msg = f"{msg} · {n_use:,}/{tot_use:,}"
                    entry = {"ts": now, "message": str(msg)[:240]}
                    self._log.append(entry)
                    self.state["recent_log"] = list(self._log)
                    write_progress(self.progress_path, dict(self.state))


def compact_http_result(payload: dict[str, Any], artifacts: dict[str, str] | None = None) -> dict[str, Any]:
    """Summary suitable for HTTP — no TickStory lists, no scientific_rows."""
    hist = payload.get("canonical_history") or {}
    unique = int(hist.get("unique_simulation_ticks") or payload.get("unique_simulation_ticks") or 0)
    stories_n = int(payload.get("tick_stories_count") or 0)
    consumed = unique > 0 and stories_n > 0
    tmin, tmax = hist.get("tick_min"), hist.get("tick_max")
    rng = payload.get("scientific_tick_range") or hist.get("scientific_tick_range") or [tmin, tmax]
    keep = (
        "section", "status", "evidence_version", "run_id", "analysis_cutoff_tick",
        "tick_stories_count", "complete_odmc_count", "complete_odmc",
        "unique_simulation_ticks", "scientific_tick_range", "canonical_history",
        "scientific_v3_core",
        "world_size", "join_summary", "legacy_scenario_selected_count",
        "decision_receipts", "agent_summaries", "episode_counts",
        "selected_episodes", "interesting_ticks", "open_questions",
        "relationship_graph_summary", "what_happened",
        "sensorimotor_steps_count", "motor_reversals_count",
        "sensorimotor_trend_reversals_count", "elapsed_s",
        "report_text", "sensorimotor_report_text",
        "action_conditioned_model_report_text",
        "historical_sensorimotor_selection_report_text",
        "signal_conditioned_report_text", "full_embodied_report_text",
        "beta31_vision_report_text", "beta31_vision_publication",
        "volumetric_physical_causal_report_text",
        "volumetric_physical_causal_reconstruction",
        "identity", "evidence_files", "metadata_authority", "psc_regime",
        "psc_regime_report_text", "layered_coverage", "report_consistency",
        "development_fixture_section", "decision_receipts_unit",
        "truthful_markdown", "signal_conditioned_sensorimotor_selection",
        "what_happened", "episode_counts", "export_validation",
        "abstract_spectral_light_causal_reconstruction",
        "abstract_spectral_light_causal_report_text",
        "object_body_held_optical_causal_reconstruction",
        "object_body_held_optical_causal_report_text",
        "organism_physical_optical_causal_reconstruction",
        "organism_physical_optical_causal_report_text",
        "analyzer_version", "publication_gate",
    )
    out = {k: payload.get(k) for k in keep if k in payload}
    vpc = out.get("volumetric_physical_causal_reconstruction")
    if isinstance(vpc, dict):
        stories = vpc.get("physical_stories") or []
        sample = stories[0] if stories else None
        out["volumetric_physical_causal_reconstruction"] = {
            "schema": vpc.get("schema"),
            "status": vpc.get("status"),
            "model_authority": vpc.get("model_authority"),
            "acanthostega_described_as_2d": vpc.get("acanthostega_described_as_2d"),
            "physical_stories_count": vpc.get("physical_stories_count"),
            "negative_cause_counts": vpc.get("negative_cause_counts"),
            "relative_z": vpc.get("relative_z"),
            "passive_reachability_trace_present": vpc.get("passive_reachability_trace_present"),
            "held_to_world_trigger_status": vpc.get("held_to_world_trigger_status"),
            "sample_story": sample,
            "researcher_only": True,
        }
    br_keys = (
        "section", "status", "evidence_version", "run_id", "analysis_cutoff_tick",
        "tick_stories_count", "complete_odmc_count", "complete_odmc",
        "episode_counts", "agent_summaries", "report_text",
        "sensorimotor_report_text", "action_conditioned_model_report_text",
        "selected_episodes", "join_summary", "canonical_history",
    )
    out["behavioral_reconstruction"] = {k: payload.get(k) for k in br_keys if k in payload}
    out["artifacts"] = artifacts or {}
    out["scientific_rows"] = []
    out["timeline"] = []
    out["events"] = []
    out["unique_simulation_ticks"] = unique
    out["scientific_tick_range"] = rng
    out["coverage"] = "CORE_FULL_AUX_PARTIAL" if consumed else "INSUFFICIENT"
    out["complete_tick_level_reanalysis"] = bool(consumed)
    layered = out.get("layered_coverage") or {}
    if layered.get("banner"):
        out["coverage_banner"] = layered.get("banner")
    out.setdefault("evidence_files", payload.get("evidence_files") or [])
    out["evidence_counts"] = {
        "tick_stories": stories_n,
        "scientific_rows": stories_n,
        "unique_simulation_ticks": unique,
        "events": int((payload.get("join_summary") or {}).get("event_ticks_indexed") or 0),
    }
    out["analyzer_version"] = payload.get("analyzer_version") or "1.2.0"
    vis = payload.get("beta31_vision") or {}
    out["beta31_vision_summary"] = (vis.get("vision_summary") if isinstance(vis, dict) else None)
    return out


def run_job(*, run_dir: Path, out_dir: Path, max_tick: int | None = None) -> dict[str, Any]:
    from mechanistic_mind.scientific_v3.analyzer_next.pipeline import build_behavioral_reconstruction
    from mechanistic_mind.scientific_v3.analyzer_next.snapshot import detect_snapshot_violation

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    progress_path = out_dir / "progress.json"
    t0 = time.perf_counter()
    snapshot: dict[str, Any] | None = None
    snap_path = out_dir / "snapshot.json"
    if snap_path.is_file():
        try:
            snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
        except Exception:
            snapshot = None
    if snapshot and max_tick is None and snapshot.get("snapshot_terminal_tick") is not None:
        max_tick = int(snapshot["snapshot_terminal_tick"])

    bytes_total = 0
    if snapshot and isinstance(snapshot.get("files"), dict):
        for row in snapshot["files"].values():
            if isinstance(row, dict):
                bytes_total += int(row.get("byte_end") or 0)
    else:
        for name in (
            "scientific_spine.jsonl",
            "scientific_decisions.jsonl",
            "scientific_timeline.jsonl",
            "scientific_events.jsonl",
            "scientific_observations.jsonl",
            "scientific_motors.jsonl",
            "scientific_consequences.jsonl",
        ):
            p = Path(run_dir) / name
            if p.is_file():
                bytes_total += p.stat().st_size

    phase_count = len([p for p in PROGRESS_PHASES if p not in ("FAILED", "CANCELLED")])
    state: dict[str, Any] = {
        "schema": PROGRESS_SCHEMA,
        "job_id": out_dir.name,
        "run_id": (snapshot or {}).get("run_id"),
        "phase": "DISCOVER_EVIDENCE",
        "phase_id": "DISCOVER_EVIDENCE",
        "state": "QUEUED",
        "status": "RUNNING",
        "run_dir": str(run_dir),
        "out_dir": str(out_dir),
        "records_processed": 0,
        "ticks_reconstructed": 0,
        "last_tick_processed": None,
        "bytes_total": bytes_total,
        "elapsed_s": 0.0,
        "elapsed_seconds": 0.0,
        "error": None,
        "error_code": None,
        "error_message": None,
        "started_at": _now(),
        "last_progress_at": None,
        "worker_heartbeat_at": _now(),
        "completed_units": 0,
        "total_units": (snapshot or {}).get("snapshot_record_count"),
        "percent": 0.0,
        "status_text": "Discovering evidence files",
        "message": "Discovering evidence files",
        "phase_index": 0,
        "phase_count": phase_count,
        "terminal": False,
        "unit_label": "ticks",
        "snapshot_terminal_tick": (snapshot or {}).get("snapshot_terminal_tick"),
        "snapshot_record_count": (snapshot or {}).get("snapshot_record_count"),
        "recent_log": [],
        "cancel_requested": False,
    }
    reporter = ProgressReporter(out_dir=out_dir, state=state, progress_path=progress_path, t0=t0)
    try:
        if cancel_requested(out_dir):
            state["phase"] = "CANCELLED"
            state["status"] = "CANCELLED"
            state["state"] = "CANCELLED"
            state["terminal"] = True
            write_progress(progress_path, state)
            return state

        if snapshot:
            issues = detect_snapshot_violation(run_dir, snapshot)
            if issues:
                raise RuntimeError("snapshot_violation: " + "; ".join(issues[:4]))
            reporter.log(
                f"Snapshot frozen through tick {snapshot.get('snapshot_terminal_tick')} "
                f"· records≈{snapshot.get('snapshot_record_count')}"
            )
        else:
            reporter.log("No snapshot.json — using live directory bound (legacy)")

        reporter.emit("LOAD_AND_VALIDATE", n=0, status_text="Loading and validating evidence")
        reporter.log("Phase 2/8 · Loading and validating evidence")
        state["state"] = "RUNNING"
        payload = build_behavioral_reconstruction(
            run_dir,
            max_tick=max_tick,
            write_artifacts=True,
            artifact_dir=out_dir,
            on_progress=reporter,
            snapshot=snapshot,
        )
        n_stories = int(payload.get("tick_stories_count") or 0)
        reporter.emit(
            "RENDER_EXPORT_PAYLOADS",
            n=n_stories,
            total=n_stories or None,
            status_text="Rendering export payloads",
            operation="write_http_summary",
            unit_label="stories",
        )
        reporter.log("Phase 7/8 · Rendering export payloads")
        compact = compact_http_result(payload)
        if snapshot:
            compact["analysis_snapshot"] = {
                "schema": snapshot.get("schema"),
                "snapshot_at": snapshot.get("snapshot_at"),
                "snapshot_terminal_tick": snapshot.get("snapshot_terminal_tick"),
                "snapshot_record_count": snapshot.get("snapshot_record_count"),
                "note": snapshot.get("note"),
            }
            compact["analysis_cutoff_tick"] = snapshot.get("snapshot_terminal_tick")
        (out_dir / "analysis_http_summary.json").write_text(
            json.dumps(compact, indent=2, default=str), encoding="utf-8"
        )
        from .export_bundle import write_validated_export

        export_payload = dict(payload)
        export_payload.setdefault("signal_context", payload.get("signal_conditioned_sensorimotor_selection"))
        export_payload["_job_dir"] = str(out_dir)
        export_result = write_validated_export(
            out_dir,
            export_payload,
            artifacts={"analysis_tick_stories.jsonl": str(out_dir / "analysis_tick_stories.jsonl")},
        )
        compact["export_validation"] = export_result.get("validation")
        compact["truthful_markdown"] = (out_dir / "analysis_report.md").read_text(encoding="utf-8")
        (out_dir / "analysis_http_summary.json").write_text(
            json.dumps(compact, indent=2, default=str), encoding="utf-8"
        )
        state["status"] = "COMPLETE"
        state["export_validation"] = export_result.get("validation")
        state["tick_stories_count"] = payload.get("tick_stories_count")
        state["complete_odmc"] = payload.get("complete_odmc")
        state["episode_counts"] = payload.get("episode_counts")
        state["analysis_cutoff_tick"] = payload.get("analysis_cutoff_tick")
        reporter.emit(
            "COMPLETE",
            n=n_stories,
            total=n_stories or None,
            status_text="COMPLETE — export payloads ready",
            unit_label="stories",
        )
        reporter.log("Completed")
        return state
    except KeyboardInterrupt:
        state["status"] = "CANCELLED"
        state["state"] = "CANCELLED"
        state["cancel_requested"] = True
        reporter.emit("CANCELLED", n=int(state.get("records_processed") or 0), status_text="CANCELLED")
        reporter.log("Cancelled")
        return state
    except Exception as exc:
        prior_phase = str(state.get("phase") or "BUILD_TICK_STORIES")
        if prior_phase in ("FAILED", "COMPLETE", "CANCELLED", "QUEUED", "DISCOVER_EVIDENCE"):
            prior_phase = "BUILD_TICK_STORIES"
        state["status"] = "FAILED"
        state["state"] = "FAILED"
        state["error"] = str(exc)
        state["error_code"] = type(exc).__name__
        state["error_message"] = str(exc)[:500]
        state["failed_phase"] = prior_phase
        # Bound traceback — do not put full paths-heavy dump into progress UI payload.
        tb = traceback.format_exc()
        state["traceback"] = tb[-4000:]
        state["partial_output_available"] = bool(
            (out_dir / "analysis_http_summary.json").is_file()
            or (out_dir / "tick_stories.jsonl").is_file()
        )
        reporter.emit(
            "FAILED",
            n=int(state.get("records_processed") or 0),
            status_text=f"FAILED [{state['error_code']}] {exc}",
        )
        reporter.log(f"Failed [{state['error_code']}]")
        (out_dir / "FAILED").write_text(
            json.dumps(
                {
                    "error": str(exc),
                    "error_code": state["error_code"],
                    "failed_phase": state["failed_phase"],
                    "records_processed": state.get("records_processed"),
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return state
    finally:
        reporter.stop()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--run-dir", required=True)
    p.add_argument("--out-dir", required=True)
    p.add_argument("--max-tick", type=int, default=None)
    args = p.parse_args(argv)
    st = run_job(run_dir=Path(args.run_dir), out_dir=Path(args.out_dir), max_tick=args.max_tick)
    return 0 if st.get("status") == "COMPLETE" else 1


if __name__ == "__main__":
    sys.exit(main())
