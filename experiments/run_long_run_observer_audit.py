#!/usr/bin/env python3
"""LONG-RUN PHASE 1 — Observer age profile + bounded LIVE audit.

Measures LIVE Observer cost vs tick age. Does not change science.
Writes results/performance/long_run_observer_audit/.
"""
from __future__ import annotations

import hashlib
import json
import os
import resource
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from mechanistic_mind.ui.psy_observer_web.live_bounds import (  # noqa: E402
    LIVE_WORLD_INTERVENTION_EMBED,
    live_bounds_snapshot,
    tail_list,
)
from mechanistic_mind.ui.psy_observer_web.session import (  # noqa: E402
    ObserverSession,
    SessionConfig,
)
from mechanistic_mind.ui.psy_observer_web.run_finalize import new_run_id  # noqa: E402

OUT = Path("results/performance/long_run_observer_audit")
SEED = 17
CHECKPOINTS = [500, 5_000, 10_000, 50_000]
WINDOW = 40  # ticks measured at each checkpoint


def rss_mb() -> float:
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def sci_fingerprint(rt) -> str:
    slots = getattr(rt, "slots", None) or [rt]
    bodies = []
    actions = []
    for s in slots:
        bodies.append({
            "x": round(float(s.body.x), 8),
            "y": round(float(s.body.y), 8),
            "vx": round(float(s.body.vx), 8),
            "vy": round(float(s.body.vy), 8),
            "seed": int(s.seed),
        })
        actions.append(getattr(s, "last_selected_action", None))
    payload = {
        "tick": int(rt.tick),
        "bodies": bodies,
        "actions": actions,
        "T_sum": round(float(rt.world.T.sum()), 6),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def make_session() -> ObserverSession:
    sess = ObserverSession(
        SessionConfig(
            seed=SEED,
            cognition_enabled=True,
            buffer_capacity=256,
            ui_hz=10.0,
            speed=50.0,
            target_tick=max(CHECKPOINTS),
            results_root=OUT / "runs",
        )
    )
    # Compact two-agent experiment (climate OFF to isolate Observer cost).
    sess.apply_experiment({
        "seed": SEED,
        "world": {"width": 24, "height": 24, "boundary_mode": "WRAP_PERIODIC"},
        "agent_count": 2,
        "cognition_enabled": True,
        "mechanisms": {
            "cognition_enabled": True,
            "experimental_physical_signal": True,
            "physical_near_field_vision": True,
            "illumination_cycle": True,
            "physical_body_optical_response": True,
            "spatiotemporal_climate_ecology": False,
        },
        "observer": {"ui_hz": 10, "buffer_capacity": 256, "speed": 50},
    })
    sess._run_started_at = datetime.now(timezone.utc).isoformat()
    sess._active_run_id = new_run_id()
    with sess._lock:
        sess._ensure_scientific_locked()
    return sess


def scientific_only(sess: ObserverSession, n: int) -> list[float]:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()
                sess._update_perf_locked(tick=True)
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def advance_to(sess: ObserverSession, tick: int) -> None:
    while int(sess.runtime.tick) < tick:
        remain = tick - int(sess.runtime.tick)
        chunk = min(remain, 100)
        scientific_only(sess, chunk)


def measure_live(sess: ObserverSession) -> dict:
    # Warm one compact capture
    with sess._step_lock:
        with sess._lock:
            sess._capture_locked(detail="compact", serialize=False)

    build_ms = []
    ser_ms = []
    payload_bytes = []
    touched = []
    for _ in range(5):
        t0 = time.perf_counter()
        with sess._step_lock:
            with sess._lock:
                frame = sess._capture_locked(detail="compact", serialize=False)
        build_ms.append((time.perf_counter() - t0) * 1000.0)
        t1 = time.perf_counter()
        raw = json.dumps(frame, default=str, separators=(",", ":"))
        ser_ms.append((time.perf_counter() - t1) * 1000.0)
        payload_bytes.append(len(raw.encode("utf-8")))
        obs = frame.get("observation") or {}
        touched.append(int(obs.get("history_elements_touched_by_live_refresh") or 0))

    # Undercover-like input: enqueue MOVE and measure until next compact frame.
    input_ms = None
    try:
        spawn = sess.experimenter_spawn()
        if spawn.get("accepted") or (sess._experimenter and sess._experimenter.active):
            t_in = time.perf_counter()
            sess.experimenter_command(kind="ACTION", action="MOVE:N")
            with sess._step_lock:
                sess._scientific_step_once_unlocked()
                with sess._lock:
                    sess._accumulate_events_locked()
                    sess._record_motion_locked()
                    frame = sess._capture_locked(detail="compact", serialize=False)
            input_ms = (time.perf_counter() - t_in) * 1000.0
            assert frame is not None
    except Exception as exc:  # noqa: BLE001
        input_ms = None
        spawn_err = str(exc)
    else:
        spawn_err = None

    geo_n = None
    try:
        if sess._geo_accum is not None:
            geo_n = int(getattr(sess._geo_accum, "compact_summary", lambda: {})().get("n_buckets") or 0)
            if geo_n == 0:
                summ = sess._geo_accum.compact_summary() if hasattr(sess._geo_accum, "compact_summary") else {}
                geo_n = int(summ.get("n_buckets") or 0)
    except Exception:
        geo_n = None

    history_rows = 0
    sci_bytes = 0
    live_dir = sess._sci_live_dir
    if live_dir and live_dir.exists():
        for p in live_dir.rglob("*"):
            if p.is_file():
                sci_bytes += p.stat().st_size
                if p.name.endswith(".jsonl"):
                    with p.open("rb") as fh:
                        history_rows += sum(1 for _ in fh)

    return {
        "runtime_tick_ms_mean": sum(scientific_only(sess, WINDOW)) / WINDOW,
        "live_frame_ms_mean": sum(build_ms) / len(build_ms),
        "api_serialize_ms_mean": sum(ser_ms) / len(ser_ms),
        "live_payload_bytes_mean": sum(payload_bytes) / len(payload_bytes),
        "history_elements_touched_by_live_refresh": sum(touched) / len(touched),
        "input_processing_ms": input_ms,
        "input_error": spawn_err,
        "rss_mb": rss_mb(),
        "history_rows": history_rows,
        "scientific_bytes_on_disk": sci_bytes,
        "geo_buckets": geo_n,
        "world_interventions_session": len(sess._world_interventions),
        "trajectory_ring": len(sess._trajectory),
        "event_ring": len(sess._event_ring),
        "sci_fingerprint": sci_fingerprint(sess.runtime),
    }


def intervention_pathology_bench() -> dict:
    """BEFORE vs AFTER for embedding interventions into LIVE JSON."""
    items = [
        {"tick": i, "type": "WORLD_INTERVENTION", "payload": {"k": i, "note": "x" * 24}}
        for i in range(5_000)
    ]
    t0 = time.perf_counter()
    unbounded = json.dumps({"world_interventions": items}, separators=(",", ":"))
    t_unbounded = (time.perf_counter() - t0) * 1000.0
    t1 = time.perf_counter()
    bounded = json.dumps(
        {"world_interventions": tail_list(items, LIVE_WORLD_INTERVENTION_EMBED)},
        separators=(",", ":"),
    )
    t_bounded = (time.perf_counter() - t1) * 1000.0
    return {
        "n_interventions": len(items),
        "unbounded_bytes": len(unbounded),
        "bounded_bytes": len(bounded),
        "unbounded_serialize_ms": t_unbounded,
        "bounded_serialize_ms": t_bounded,
        "ratio_bytes": len(unbounded) / max(1, len(bounded)),
    }


def scientific_equivalence() -> dict:
    """Paired short runs: LIVE capture frequency must not change science fingerprint."""
    def run(captures_every: int | None) -> str:
        s = make_session()
        for i in range(120):
            with s._step_lock:
                s._scientific_step_once_unlocked()
                with s._lock:
                    s._accumulate_events_locked()
                    s._record_motion_locked()
                    s._append_scientific_locked()
                    if captures_every and (i + 1) % captures_every == 0:
                        s._capture_locked(detail="compact", serialize=False)
        return sci_fingerprint(s.runtime)

    a = run(None)
    b = run(5)
    return {"no_capture": a, "capture_every_5": b, "exact_match": a == b}


def estimate_storage(bytes_at_tick: int, tick: int) -> dict:
    if tick <= 0:
        return {}
    per = bytes_at_tick / tick
    return {
        "bytes_per_tick": per,
        "est_10k_mb": per * 10_000 / (1024 * 1024),
        "est_100k_mb": per * 100_000 / (1024 * 1024),
        "est_1M_gb": per * 1_000_000 / (1024 ** 3),
        "est_10M_gb": per * 10_000_000 / (1024 ** 3),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    max_cp = int(os.environ.get("LR_AUDIT_MAX_TICK", str(max(CHECKPOINTS))))
    checkpoints = [c for c in CHECKPOINTS if c <= max_cp]
    if not checkpoints:
        checkpoints = [min(CHECKPOINTS)]

    print(f"[audit] checkpoints={checkpoints} cwd={ROOT}", flush=True)
    sess = make_session()
    rows = []
    for cp in checkpoints:
        print(f"[audit] advancing to {cp}…", flush=True)
        advance_to(sess, cp)
        print(f"[audit] measuring at tick={sess.runtime.tick}…", flush=True)
        m = measure_live(sess)
        m["tick_age"] = int(sess.runtime.tick)
        rows.append(m)
        print(
            f"  tick={m['tick_age']} tick_ms={m['runtime_tick_ms_mean']:.2f} "
            f"live_ms={m['live_frame_ms_mean']:.2f} ser_ms={m['api_serialize_ms_mean']:.2f} "
            f"bytes={m['live_payload_bytes_mean']:.0f} touched={m['history_elements_touched_by_live_refresh']:.0f} "
            f"rss={m['rss_mb']:.1f}",
            flush=True,
        )

    pathology = intervention_pathology_bench()
    equiv = scientific_equivalence()
    last = rows[-1] if rows else {}
    storage = estimate_storage(int(last.get("scientific_bytes_on_disk") or 0), int(last.get("tick_age") or 1))

    # Scaling verdict: live_frame_ms at last vs 5k (or earliest >=500)
    ref = next((r for r in rows if r["tick_age"] >= 5_000), rows[0] if rows else None)
    late = rows[-1] if rows else None
    live_independent = None
    if ref and late and ref["live_frame_ms_mean"] > 0:
        ratio = late["live_frame_ms_mean"] / ref["live_frame_ms_mean"]
        # Allow 2× noise / current-state complexity; flag if clearly age-linear.
        live_independent = ratio < 2.5

    profile = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_hint": "project root",
        "live_bounds": live_bounds_snapshot(),
        "checkpoints": rows,
        "intervention_pathology": pathology,
        "scientific_equivalence": equiv,
        "storage_estimate": storage,
        "live_refresh_age_independent": live_independent,
        "notes": {
            "frontend_projection_ms": "measured in node tests; not in this harness",
            "browser_retained": "FE liveBounds caps; see liveBounds.test.ts",
        },
    }
    (OUT / "observer_age_profile.json").write_text(json.dumps(profile, indent=2) + "\n")

    lines = [
        "# Observer age profile — LONG-RUN PHASE 1",
        "",
        f"Generated: {profile['generated_at']}",
        "",
        "## Table",
        "",
        "| tick_age | runtime_tick_ms | live_frame_ms | api_serialize_ms | live_payload_bytes | input_ms | rss_mb | history_rows | history_elements_touched |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in rows:
        lines.append(
            f"| {r['tick_age']} | {r['runtime_tick_ms_mean']:.2f} | {r['live_frame_ms_mean']:.2f} | "
            f"{r['api_serialize_ms_mean']:.2f} | {r['live_payload_bytes_mean']:.0f} | "
            f"{(r['input_processing_ms'] if r['input_processing_ms'] is not None else float('nan')):.2f} | "
            f"{r['rss_mb']:.1f} | {r['history_rows']} | {r['history_elements_touched_by_live_refresh']:.0f} |"
        )
    lines.extend([
        "",
        "## Does LIVE refresh complexity depend on historical run length?",
        "",
        f"**Answer:** `{'NO (within noise)' if live_independent else 'YES / INCONCLUSIVE'}` "
        f"(live_refresh_age_independent={live_independent})",
        "",
        "Touched historical-ish elements per LIVE refresh are bounded by named LIVE caps "
        "(trajectory/telemetry/events/interventions embeds), not by scientific_rows.",
        "",
        "## Intervention embed pathology (synthetic BEFORE vs AFTER)",
        "",
        f"- unbounded 5k interventions: {pathology['unbounded_bytes']} bytes / {pathology['unbounded_serialize_ms']:.2f} ms",
        f"- bounded embed ({LIVE_WORLD_INTERVENTION_EMBED}): {pathology['bounded_bytes']} bytes / {pathology['bounded_serialize_ms']:.2f} ms",
        f"- byte ratio: {pathology['ratio_bytes']:.1f}×",
        "",
        "## Scientific equivalence (capture vs no-capture)",
        "",
        f"- EXACT_MATCH: {equiv['exact_match']}",
        "",
        "## Storage estimate",
        "",
        "```json",
        json.dumps(storage, indent=2),
        "```",
        "",
    ])
    (OUT / "observer_age_profile.md").write_text("\n".join(lines) + "\n")
    print("[audit] wrote", OUT / "observer_age_profile.json", flush=True)
    return 0 if equiv["exact_match"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
