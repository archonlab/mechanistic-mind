"""Canonical run finalization for Psy Observer Web.

Persists PhysicalSystemRuntime / TwoAgentRuntime snapshots without altering
scientific mechanisms. Ownership of finalize_run stays on the backend.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "mm.psychology_observer.physical_run.v1"
SNAPSHOT_SINGLE = "mm.physical_system.snapshot.v2"
SNAPSHOT_TWO = "mm.physical_system.two_agent.snapshot.v1"
RUN_SUBDIR = "psychology_observer/psy_observer_web"


def project_root() -> Path:
    env = os.environ.get("PSY_OBSERVER_PROJECT_ROOT")
    if env:
        return Path(env).expanduser().resolve()
    # mechanistic_mind/ui/psy_observer_web/run_finalize.py → repo root
    return Path(__file__).resolve().parents[3]


def default_results_root() -> Path:
    return project_root() / "results"


def new_run_id(*, now: datetime | None = None) -> str:
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"psyweb-{stamp}-{uuid.uuid4().hex[:8]}"


def _json_dump(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2, default=str),
        encoding="utf-8",
    )


def _row_ticks(rows: list[dict[str, Any]], key: str = "tick") -> list[int]:
    out: list[int] = []
    for row in rows:
        if not isinstance(row, dict) or key not in row:
            continue
        try:
            out.append(int(row[key]))
        except (TypeError, ValueError):
            continue
    return out


def collect_structured_events(runtime: Any) -> list[dict[str, Any]]:
    """Both agents for TwoAgentRuntime; selected proxy is not sufficient."""
    slots = getattr(runtime, "slots", None)
    if slots:
        out: list[dict[str, Any]] = []
        for i, slot in enumerate(slots):
            buf = getattr(slot, "structured_events", None)
            if buf is None:
                continue
            for ev in buf.list(limit=10_000):
                row = dict(ev)
                row.setdefault("agent_id", f"agent_{i}")
                out.append(row)
        return out
    buf = getattr(runtime, "structured_events", None)
    if buf is None:
        return []
    return [dict(ev) for ev in buf.list(limit=10_000)]


def agent_summaries(runtime: Any) -> list[dict[str, Any]]:
    if hasattr(runtime, "observer_agent_summaries"):
        return list(runtime.observer_agent_summaries() or [])
    slots = getattr(runtime, "slots", None)
    if slots:
        out = []
        for i, slot in enumerate(slots):
            out.append({
                "observer_id": f"agent_{i}",
                "tick": int(slot.tick),
                "x": float(slot.body.x),
                "y": float(slot.body.y),
                "selected_action": slot.last_selected_action,
            })
        return out
    return [{
        "observer_id": "agent_0",
        "tick": int(runtime.tick),
        "x": float(runtime.body.x),
        "y": float(runtime.body.y),
        "selected_action": runtime.last_selected_action,
    }]


def capabilities_for_snapshot(snapshot: dict[str, Any], *, has_timeline: bool) -> dict[str, Any]:
    schema = str(snapshot.get("schema") or "")
    resumable = schema in {SNAPSHOT_SINGLE, SNAPSHOT_TWO}
    return {
        "inspectable": True,
        "inspectable_scope": "final_snapshot_plus_bounded_session_buffers",
        "replay_available": bool(has_timeline),
        "replayable_scope": "session_timeline_ticks_recorded_at_stop" if has_timeline else "none",
        "resumable": resumable,
        "resumable_via": "POST /api/snapshot/restore with physical_system_snapshot.json" if resumable else None,
        "full_history_jsonl": False,
        "psychology_observer_jsonl": False,
        "snapshot_schema": schema,
    }


def validate_persistence_boundary(
    *,
    runtime: Any,
    snapshot: dict[str, Any],
    timeline: list[dict[str, Any]],
    telemetry: list[dict[str, Any]],
    events: list[dict[str, Any]],
    identity: dict[str, Any] | None = None,
) -> list[str]:
    """Return human-readable integrity errors; empty list means OK.

    Session buffers are bounded/sampled and may end earlier than the final tick;
    they must never exceed the captured runtime tick or belong to another generation.
    """
    errors: list[str] = []
    live_tick = int(runtime.tick)
    snap_tick = int(snapshot.get("tick", -1))
    if snap_tick != live_tick:
        errors.append(
            f"captured_live_tick={live_tick} != snapshot_tick={snap_tick}"
        )

    expected = identity or {}
    if "expected_final_tick" in expected and int(expected["expected_final_tick"]) != live_tick:
        errors.append(
            f"identity.expected_final_tick={expected['expected_final_tick']} != live_tick={live_tick}"
        )
    if "runtime_type" in expected and str(expected["runtime_type"]) != type(runtime).__name__:
        errors.append(
            f"identity.runtime_type={expected['runtime_type']} != {type(runtime).__name__}"
        )
    if "seed" in expected and int(expected["seed"]) != int(getattr(runtime, "seed", -1)):
        errors.append(
            f"identity.seed={expected['seed']} != runtime.seed={getattr(runtime, 'seed', None)}"
        )

    slots = getattr(runtime, "slots", None)
    agent_count = len(slots) if slots else 1
    if "agent_count" in expected and int(expected["agent_count"]) != agent_count:
        errors.append(
            f"identity.agent_count={expected['agent_count']} != {agent_count}"
        )
    if slots:
        agents = snapshot.get("agents") or []
        if len(agents) != len(slots):
            errors.append(
                f"two_agent snapshot agent slots {len(agents)} != runtime slots {len(slots)}"
            )
        for i, slot in enumerate(slots):
            if int(slot.tick) != live_tick:
                errors.append(f"agent_{i}.tick={slot.tick} != live_tick={live_tick}")
            if i < len(agents) and int(agents[i].get("tick", -1)) != live_tick:
                errors.append(
                    f"snapshot.agents[{i}].tick={agents[i].get('tick')} != live_tick={live_tick}"
                )

    for label, rows in (
        ("timeline", timeline),
        ("telemetry", telemetry),
        ("structured_events", events),
    ):
        ticks = _row_ticks(rows)
        if not ticks:
            continue
        mx = max(ticks)
        if mx > live_tick:
            errors.append(f"{label} max tick {mx} > snapshot/live tick {live_tick}")

    return errors


def _integrity_failure(
    *,
    error: str,
    live_tick: int,
    captured_tick: int | None,
    run_id: str,
    run_dir: Path | None,
    phases: list[str],
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "accepted": False,
        "saved": False,
        "error": error,
        "persistence_integrity_error": True,
        "live_tick": int(live_tick),
        "captured_tick": captured_tick,
        "persisted_tick": captured_tick,
        "run_id": run_id,
        "run_dir": str(run_dir) if run_dir is not None else None,
        "termination_reason": "SAVE_FAILED",
        "phases": phases,
        "final_tick": None,
    }
    if details:
        out["integrity"] = details
    return out


def write_finalized_run(
    *,
    results_root: Path,
    runtime: Any,
    session_meta: dict[str, Any],
    timeline: list[dict[str, Any]],
    telemetry: list[dict[str, Any]],
    termination_reason: str,
    run_id: str | None = None,
    identity: dict[str, Any] | None = None,
    scientific_live_dir: Path | None = None,
) -> dict[str, Any]:
    """Atomically persist one run directory after integrity validation.

    Existing run.json is only treated as a true idempotent hit when the
    persisted final_tick matches the *current* live runtime tick. A reused
    run_id with a later live tick is a persistence integrity failure — never
    reported as SAVED.
    """
    stopped_at = datetime.now(timezone.utc)
    rid = run_id or new_run_id(now=stopped_at)
    base = Path(results_root) / RUN_SUBDIR
    base.mkdir(parents=True, exist_ok=True)
    run_dir = base / rid
    live_tick = int(runtime.tick)
    identity = dict(identity or {})
    identity.setdefault("expected_final_tick", live_tick)
    identity.setdefault("runtime_type", type(runtime).__name__)
    identity.setdefault("seed", int(getattr(runtime, "seed", session_meta.get("seed", 0))))
    slots = getattr(runtime, "slots", None)
    identity.setdefault("agent_count", len(slots) if slots else 1)

    marker = run_dir / "run.json"
    if marker.is_file():
        existing = json.loads(marker.read_text(encoding="utf-8"))
        persisted = int(existing.get("final_tick", -1))
        if persisted != live_tick:
            return _integrity_failure(
                error=(
                    "persistence_integrity_error: run_id already finalized at a different tick "
                    f"(persisted={persisted}, live={live_tick}); refusing stale SAVE success"
                ),
                live_tick=live_tick,
                captured_tick=persisted,
                run_id=rid,
                run_dir=run_dir,
                phases=["integrity_reject_stale_run_id"],
                details={
                    "existing_termination_reason": existing.get("termination_reason"),
                    "existing_runtime_generation": existing.get("runtime_generation"),
                    "requested_runtime_generation": identity.get("runtime_generation"),
                },
            )
        # Same tick: genuine idempotent recovery / double-finalize
        return {
            "accepted": True,
            "idempotent": True,
            "verified": True,
            "run_id": rid,
            "run_dir": str(run_dir),
            "manifest": existing,
            "phases": ["already_saved"],
            "termination_reason": existing.get("termination_reason") or termination_reason,
            "final_tick": persisted,
            "seed": int(existing.get("seed", getattr(runtime, "seed", 0))),
            "runtime_generation": existing.get("runtime_generation", identity.get("runtime_generation")),
            "agent_count": int(existing.get("agent_count", identity.get("agent_count", 1))),
            "integrity": {
                "captured_live_tick": live_tick,
                "snapshot_tick": persisted,
                "run_json_final_tick": persisted,
                "matched_existing": True,
            },
        }

    tmp_dir = base / f".tmp-{rid}-{uuid.uuid4().hex[:6]}"
    tmp_dir.mkdir(parents=True, exist_ok=False)
    phases: list[str] = ["flushing_telemetry"]

    try:
        snapshot = runtime.snapshot()
        phases.append("saving_snapshot")
        events = collect_structured_events(runtime)
        integrity_errors = validate_persistence_boundary(
            runtime=runtime,
            snapshot=snapshot,
            timeline=timeline,
            telemetry=telemetry,
            events=events,
            identity=identity,
        )
        if integrity_errors:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return _integrity_failure(
                error="persistence_integrity_error: " + "; ".join(integrity_errors),
                live_tick=live_tick,
                captured_tick=int(snapshot.get("tick", -1)),
                run_id=rid,
                run_dir=None,
                phases=phases + ["integrity_validation_failed"],
                details={"errors": integrity_errors},
            )

        _json_dump(tmp_dir / "physical_system_snapshot.json", snapshot)
        _json_dump(tmp_dir / "structured_events.json", {
            "schema": "mm.psy_observer_web.structured_events.v1",
            "events": events,
            "agent_count": len(getattr(runtime, "slots", None) or [runtime]),
        })

        (tmp_dir / "session_timeline.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False, default=str) + "\n" for row in timeline),
            encoding="utf-8",
        )
        _json_dump(tmp_dir / "session_telemetry.json", {
            "schema": "mm.psy_observer_web.session_telemetry.v1",
            "series": list(telemetry),
            "count": len(telemetry),
        })

        # Promote append-only scientific evidence into the published run dir.
        from .scientific_history import copy_scientific_into, read_jsonl_range

        sci_info = copy_scientific_into(tmp_dir, scientific_live_dir)
        phases.append("scientific_history_copied" if sci_info.get("copied") else "scientific_history_absent")

        phases.append("saving_results")
        model = {}
        if hasattr(runtime, "model_identity"):
            try:
                model = runtime.model_identity()
            except Exception:
                model = {}
        planet = getattr(getattr(runtime, "config", None), "planet", None)
        width = int(getattr(planet, "width", 0) or 0)
        height = int(getattr(planet, "height", 0) or 0)
        agent_count = int(identity["agent_count"])
        caps = capabilities_for_snapshot(snapshot, has_timeline=bool(timeline))
        sci_path = tmp_dir / "scientific_timeline.jsonl"
        sci_min, sci_max, sci_n = read_jsonl_range(sci_path) if sci_path.is_file() else (None, None, 0)
        if sci_n > 0:
            caps = dict(caps)
            caps["full_history_jsonl"] = True
            caps["scientific_timeline"] = True
            caps["inspectable_scope"] = "final_snapshot_plus_scientific_timeline_plus_bounded_session_buffers"
        started_at = session_meta.get("started_at")
        tl_ticks = _row_ticks(timeline)
        tel_ticks = _row_ticks(telemetry)
        ev_ticks = _row_ticks(events)
        artifacts = {
            "physical_system_snapshot": "physical_system_snapshot.json",
            "session_timeline": "session_timeline.jsonl",
            "session_telemetry": "session_telemetry.json",
            "structured_events": "structured_events.json",
            "run_manifest": "run.json",
        }
        if sci_n > 0:
            artifacts["scientific_timeline"] = "scientific_timeline.jsonl"
            artifacts["scientific_events"] = "scientific_events.jsonl"
            artifacts["scientific_meta"] = "scientific_meta.json"
        manifest = {
            "schema": SCHEMA,
            "run_id": rid,
            "source": "psy_observer_web",
            "termination_reason": str(termination_reason),
            "stop_reason": str(termination_reason),  # desktop compatibility
            "started_at": started_at,
            "stopped_at": stopped_at.isoformat(),
            "seed": int(getattr(runtime, "seed", session_meta.get("seed", 0))),
            "final_tick": live_tick,
            "runtime_type": type(runtime).__name__,
            "runtime_kind": type(runtime).__name__,
            "runtime_generation": identity.get("runtime_generation"),
            "agent_count": agent_count,
            "agents": agent_summaries(runtime),
            "ecology_preset": (
                getattr(getattr(runtime, "config", None), "ecology_preset", None)
                or identity.get("ecology_preset")
                or "CURRENT"
            ),
            "model": model,
            "experiment_profile": session_meta.get("experiment_profile") or model.get("display_name"),
            "experimental_overrides": (model.get("experimental_overrides") or {}),
            "world": {
                "width": width,
                "height": height,
                "topology": "WRAP_PERIODIC",
            },
            "snapshot": "physical_system_snapshot.json",
            "snapshot_schema": snapshot.get("schema"),
            "artifacts": artifacts,
            "buffer": session_meta.get("buffer") or {},
            "buffer_bounds": {
                "timeline_max_tick": max(tl_ticks) if tl_ticks else None,
                "telemetry_max_tick": max(tel_ticks) if tel_ticks else None,
                "structured_events_max_tick": max(ev_ticks) if ev_ticks else None,
                "note": (
                    "Bounded session buffers may end earlier than final_tick; "
                    "they must never exceed final_tick or mix generations."
                ),
            },
            "scientific_history": {
                "present": sci_n > 0,
                "row_count": sci_n,
                "tick_range": [sci_min, sci_max] if sci_n else None,
                "files": sci_info.get("files") or [],
            },
            "capabilities": caps,
            "status": "STOPPED",
            "completed": termination_reason in {"COMPLETED", "USER_STOP_SAVED"},
        }
        _json_dump(tmp_dir / "run.json", manifest)

        # Re-read written boundary before publish (defense in depth)
        written_manifest = json.loads((tmp_dir / "run.json").read_text(encoding="utf-8"))
        written_snap = json.loads((tmp_dir / "physical_system_snapshot.json").read_text(encoding="utf-8"))
        if int(written_manifest.get("final_tick", -1)) != live_tick:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return _integrity_failure(
                error="persistence_integrity_error: written run.json final_tick mismatch",
                live_tick=live_tick,
                captured_tick=int(written_manifest.get("final_tick", -1)),
                run_id=rid,
                run_dir=None,
                phases=phases + ["post_write_validation_failed"],
            )
        if int(written_snap.get("tick", -1)) != live_tick:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return _integrity_failure(
                error="persistence_integrity_error: written snapshot tick mismatch",
                live_tick=live_tick,
                captured_tick=int(written_snap.get("tick", -1)),
                run_id=rid,
                run_dir=None,
                phases=phases + ["post_write_validation_failed"],
            )

        # Atomic publish only after validation
        os.rename(tmp_dir, run_dir)
        phases.append("saved")
        # Remove live staging after successful publish (evidence now in run_dir).
        if scientific_live_dir is not None:
            live = Path(scientific_live_dir)
            if live.is_dir() and live.name.startswith(".live-"):
                shutil.rmtree(live, ignore_errors=True)
                phases.append("scientific_live_staging_removed")
        return {
            "accepted": True,
            "saved": True,
            "idempotent": False,
            "verified": True,
            "run_id": rid,
            "run_dir": str(run_dir),
            "manifest": manifest,
            "phases": phases,
            "termination_reason": termination_reason,
            "capabilities": caps,
            "final_tick": live_tick,
            "seed": int(getattr(runtime, "seed", 0)),
            "runtime_generation": identity.get("runtime_generation"),
            "agent_count": agent_count,
            "scientific_history": manifest.get("scientific_history"),
            "integrity": {
                "captured_live_tick": live_tick,
                "snapshot_tick": live_tick,
                "run_json_final_tick": live_tick,
                "timeline_max_tick": max(tl_ticks) if tl_ticks else None,
                "telemetry_max_tick": max(tel_ticks) if tel_ticks else None,
                "structured_events_max_tick": max(ev_ticks) if ev_ticks else None,
            },
        }
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def read_run_manifest(run_dir: Path) -> dict[str, Any]:
    return json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8"))


def read_run_snapshot(run_dir: Path) -> dict[str, Any]:
    return json.loads((Path(run_dir) / "physical_system_snapshot.json").read_text(encoding="utf-8"))
