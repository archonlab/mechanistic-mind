"""Canonical run finalization for Psy Observer Web.

Persists PhysicalSystemRuntime / TwoAgentRuntime snapshots without altering
scientific mechanisms. Ownership of finalize_run stays on the backend.
"""
from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = "mm.psychology_observer.physical_run.v1"
SNAPSHOT_SINGLE = "mm.physical_system.snapshot.v2"
SNAPSHOT_TWO = "mm.physical_system.two_agent.snapshot.v1"
RUN_SUBDIR = "psychology_observer/psy_observer_web"
JSON_NONE_KEY = "null"


def json_key(k: Any) -> str:
    """JSON object keys must be strings. None is encoded as 'null' (json.dumps default)."""
    if k is None:
        return JSON_NONE_KEY
    if isinstance(k, bool):
        return "true" if k else "false"
    if isinstance(k, bytes):
        return k.decode("utf-8", "replace")
    return str(k)


def _sort_tiebreak(x: Any) -> tuple:
    if x is None:
        return (0, "")
    if isinstance(x, bool):
        return (1, int(x))
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        return (2, float(x))
    return (3, str(x))


def json_safe(obj: Any) -> Any:
    """Make a payload JSON-serializable without turning None *values* into 0.

    Mixed dict keys (int + None) make json.dumps(..., sort_keys=True) raise
    TypeError: '<' not supported between instances of 'int' and 'NoneType'.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            out[json_key(k)] = json_safe(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [json_safe(x) for x in obj]
    if isinstance(obj, set):
        items = [json_safe(x) for x in obj]
        try:
            items.sort(key=_sort_tiebreak)
        except TypeError:
            pass
        return items
    return _json_leaf(obj)


def json_prepare(obj: Any) -> Any:
    """Make ``obj`` JSON-serializable, mutating string-key dicts in place.

    Unlike ``json_safe`` this does not copy every mapping when keys are already
    strings (typical of ``runtime.snapshot()``). Used on the Save & Stop path
    so aged cognition is not triplicated in RAM.
    """
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        need_rekey = False
        for k in obj:
            if not isinstance(k, str):
                need_rekey = True
                break
        if need_rekey:
            return {json_key(k): json_prepare(v) for k, v in obj.items()}
        for k, v in list(obj.items()):
            nv = json_prepare(v)
            if nv is not v:
                obj[k] = nv
        return obj
    if isinstance(obj, (list, tuple)):
        if isinstance(obj, tuple):
            return [json_prepare(x) for x in obj]
        for i, v in enumerate(obj):
            nv = json_prepare(v)
            if nv is not v:
                obj[i] = nv
        return obj
    if isinstance(obj, set):
        items = [json_prepare(x) for x in obj]
        try:
            items.sort(key=_sort_tiebreak)
        except TypeError:
            pass
        return items
    return _json_leaf(obj)


def _json_leaf(obj: Any) -> Any:
    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        try:
            return json_safe(tolist())
        except Exception:
            pass
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            return json_safe(to_dict())
        except Exception:
            pass
    return str(obj)


# Reconstructible P0 / cache keys. Not canonical scientific history.
# Encoder skips them while walking live cognition so persist does not copy
# or mutate derived indexes.
DERIVED_PERSIST_SKIP = frozenset({
    "_ix_action",
    "_ix_member",
    "_ix_gen",
    "_ix_built_gen",
    "_active_ids",
    "_active_count",
    "_mean_c_cached",
    "_retrieve_cache",
    "_retrieve_cache_gen",
    "_prepared_query",
    "_prepared_query_builds",
    "_prepared_query_hits",
    "_prepared_query_misses",
    "_ix_motor",
    "_ix_loco",
})


def _cold_payload_skip_names() -> frozenset[str]:
    from mechanistic_mind.research.pe_cold_archive import PAYLOAD_KEYS

    return frozenset(PAYLOAD_KEYS)


def _is_cold_chunk_dict(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return bool(value.get("open_sidecar") or value.get("evicted") or value.get("disk_relpath"))


def _has_pe_cold(obj: Any, *, budget: int = 200000) -> bool:
    seen: set[int] = set()
    stack = [obj]
    n = 0
    while stack and n < budget:
        cur = stack.pop()
        n += 1
        if isinstance(cur, dict):
            oid = id(cur)
            if oid in seen:
                continue
            seen.add(oid)
            if "_pe_cold" in cur or cur.get("open_sidecar") or cur.get("rep") == "pe.forgotten.cold.v1":
                return True
            stack.extend(cur.values())
        elif isinstance(cur, (list, tuple)) and len(cur) < 64:
            stack.extend(cur)
    return False


def _persist_default(obj: Any) -> Any:
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, set):
        items = list(obj)
        try:
            items.sort(key=_sort_tiebreak)
        except TypeError:
            pass
        return items
    tolist = getattr(obj, "tolist", None)
    if callable(tolist):
        try:
            return tolist()
        except Exception:
            pass
    to_dict = getattr(obj, "to_dict", None)
    if callable(to_dict):
        try:
            return to_dict()
        except Exception:
            pass
    return str(obj)


def _has_non_str_keys(obj: Any, seen: set[int] | None = None) -> bool:
    if seen is None:
        seen = set()
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return False
    oid = id(obj)
    if oid in seen:
        return False
    if isinstance(obj, dict):
        seen.add(oid)
        for k, v in obj.items():
            if not isinstance(k, str):
                return True
            if _has_non_str_keys(v, seen):
                return True
        return False
    if isinstance(obj, (list, tuple)):
        seen.add(oid)
        return any(_has_non_str_keys(x, seen) for x in obj)
    return False


def dump_persist(obj: Any, fp: Any, *, compact: bool = True) -> None:
    """Stream JSON to ``fp`` without a full in-memory document string and without mutating ``obj``.

    Production path uses CPython ``json.dump`` (read-only walk). Mixed int/None keys
    fall back to a non-mutating walker that stringifies keys on the fly.
    ``json_prepare`` must not be aimed at live cognition.
    """
    indent: int | None = None if compact else 2
    separators = (",", ":") if compact else (", ", ": ")
    if not _has_non_str_keys(obj) and not _has_pe_cold(obj):
        json.dump(
            obj,
            fp,
            ensure_ascii=False,
            indent=indent,
            separators=separators,
            default=_persist_default,
        )
        return
    _dump_persist_walk(obj, fp, compact=compact)


def _dump_persist_walk(obj: Any, fp: Any, *, compact: bool) -> None:
    indent = None if compact else 2
    colon = ":" if compact else ": "
    comma = "," if compact else ", "
    default = str

    def encode_one(value: Any, level: int) -> None:
        if value is None:
            fp.write("null")
            return
        if value is True:
            fp.write("true")
            return
        if value is False:
            fp.write("false")
            return
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            fp.write(json.dumps(value, allow_nan=True))
            return
        if isinstance(value, str):
            fp.write(json.dumps(value, ensure_ascii=False))
            return
        if isinstance(value, dict):
            skip_payload = _is_cold_chunk_dict(value)
            payload_names = _cold_payload_skip_names() if skip_payload else frozenset()
            items = []
            for k, v in value.items():
                if k in DERIVED_PERSIST_SKIP:
                    continue
                if skip_payload and k in payload_names:
                    continue
                items.append((json_key(k), v))
            fp.write("{")
            if not items:
                fp.write("}")
                return
            nl = "\n" + (" " * (indent * (level + 1))) if indent else ""
            end = "\n" + (" " * (indent * level)) if indent else ""
            first = True
            for ks, v in items:
                if first:
                    first = False
                else:
                    fp.write(comma)
                if indent:
                    fp.write(nl)
                fp.write(json.dumps(ks, ensure_ascii=False))
                fp.write(colon)
                encode_one(v, level + 1)
            if indent:
                fp.write(end)
            fp.write("}")
            return
        if isinstance(value, (list, tuple)):
            fp.write("[")
            if not value:
                fp.write("]")
                return
            nl = "\n" + (" " * (indent * (level + 1))) if indent else ""
            end = "\n" + (" " * (indent * level)) if indent else ""
            first = True
            for v in value:
                if first:
                    first = False
                else:
                    fp.write(comma)
                if indent:
                    fp.write(nl)
                encode_one(v, level + 1)
            if indent:
                fp.write(end)
            fp.write("]")
            return
        if isinstance(value, set):
            items = list(value)
            try:
                items.sort(key=_sort_tiebreak)
            except TypeError:
                pass
            encode_one(items, level)
            return
        tolist = getattr(value, "tolist", None)
        if callable(tolist):
            try:
                encode_one(tolist(), level)
                return
            except Exception:
                pass
        fp.write(json.dumps(default(value), ensure_ascii=False))

    encode_one(obj, 0)


def _json_dump(path: Path, payload: Any, *, compact: bool = False) -> None:
    """Stream JSON to ``.part`` then ``os.replace``. Do not build a full in-memory string.

    Does not call ``json_prepare`` on ``payload`` (that mutates nested dicts).
    Compact mode is for aged runtime snapshots; small metadata may stay pretty.
    """
    tmp = path.with_name(path.name + ".part")
    from mechanistic_mind.research import pe_cold_archive as cold

    cold.write_open_sidecars(payload, path.parent / "pe_open")
    with tmp.open("w", encoding="utf-8") as fh:
        dump_persist(payload, fh, compact=compact)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


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
    from mechanistic_mind.ui.psy_observer_web.composite_action_display import (
        observer_applied_composite_action_display_for_runtime,
    )

    if hasattr(runtime, "observer_agent_summaries"):
        rows = list(runtime.observer_agent_summaries() or [])
        slots = getattr(runtime, "slots", None)
        out = []
        for i, row in enumerate(rows):
            r = dict(row)
            src = slots[i] if slots and i < len(slots) else runtime
            r["composite_action_display"] = observer_applied_composite_action_display_for_runtime(src)
            out.append(r)
        return out
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
                "composite_action_display": observer_applied_composite_action_display_for_runtime(slot),
            })
        return out
    return [{
        "observer_id": "agent_0",
        "tick": int(runtime.tick),
        "x": float(runtime.body.x),
        "y": float(runtime.body.y),
        "selected_action": runtime.last_selected_action,
        "composite_action_display": observer_applied_composite_action_display_for_runtime(runtime),
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
        t_cap0 = time.perf_counter()
        try:
            snapshot = runtime.snapshot(persist=True)  # type: ignore[call-arg]
        except TypeError:
            snapshot = runtime.snapshot()
        t_cap1 = time.perf_counter()
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

        t_dump0 = time.perf_counter()
        _json_dump(tmp_dir / "physical_system_snapshot.json", snapshot, compact=True)
        t_dump1 = time.perf_counter()
        _json_dump(tmp_dir / "structured_events.json", {
            "schema": "mm.psy_observer_web.structured_events.v1",
            "events": events,
            "agent_count": len(getattr(runtime, "slots", None) or [runtime]),
        }, compact=True)

        (tmp_dir / "session_timeline.jsonl").write_text(
            "".join(json.dumps(json_safe(row), ensure_ascii=False, default=str) + "\n" for row in timeline),
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
        # SCIENTIFIC_V3 CORE — record if present after copy
        for v3_key, v3_name in (
            ("scientific_v3_meta", "scientific_v3_meta.json"),
            ("identity_map", "identity_map.json"),
            ("scientific_spine", "scientific_spine.jsonl"),
            ("scientific_observations", "scientific_observations.jsonl"),
            ("scientific_decisions", "scientific_decisions.jsonl"),
            ("scientific_motors", "scientific_motors.jsonl"),
            ("scientific_consequences", "scientific_consequences.jsonl"),
        ):
            if (tmp_dir / v3_name).is_file():
                artifacts[v3_key] = v3_name
                caps = dict(caps)
                caps["scientific_v3_core"] = True
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

        # Re-read *small* run.json only. Do not json.loads the snapshot file
        # (that re-materialized the aged graph and contributed to the 14 GB OOM).
        written_manifest = json.loads((tmp_dir / "run.json").read_text(encoding="utf-8"))
        snap_path = tmp_dir / "physical_system_snapshot.json"
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
        if not snap_path.is_file() or snap_path.stat().st_size < 2:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return _integrity_failure(
                error="persistence_integrity_error: snapshot file missing or empty after write",
                live_tick=live_tick,
                captured_tick=int(snapshot.get("tick", -1)),
                run_id=rid,
                run_dir=None,
                phases=phases + ["post_write_validation_failed"],
            )
        if int(snapshot.get("tick", -1)) != live_tick:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return _integrity_failure(
                error="persistence_integrity_error: written snapshot tick mismatch",
                live_tick=live_tick,
                captured_tick=int(snapshot.get("tick", -1)),
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
            "persist_timings": {
                "capture_s": round(t_cap1 - t_cap0, 6),
                "snapshot_dump_s": round(t_dump1 - t_dump0, 6),
            },
            "integrity": {
                "captured_live_tick": live_tick,
                "snapshot_tick": live_tick,
                "run_json_final_tick": live_tick,
                "timeline_max_tick": max(tl_ticks) if tl_ticks else None,
                "telemetry_max_tick": max(tel_ticks) if tel_ticks else None,
                "structured_events_max_tick": max(ev_ticks) if ev_ticks else None,
            },
        }
    except MemoryError:
        # Leave tmp dir for forensics (Beta 3 OOM left an empty .tmp-* directory).
        raise
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def read_run_manifest(run_dir: Path) -> dict[str, Any]:
    return json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8"))


def read_run_snapshot(run_dir: Path) -> dict[str, Any]:
    return json.loads((Path(run_dir) / "physical_system_snapshot.json").read_text(encoding="utf-8"))
