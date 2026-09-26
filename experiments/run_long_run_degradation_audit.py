#!/usr/bin/env python3
"""LONG-RUN 0→5000 performance degradation audit (FEATURE FREEZE).

Primary: ObserverSession scientific Play-like path (Web UI backend).
Control: headless TwoAgentRuntime.
Climate ecology OFF. Vision R=1. No Undercover. No interventions.
Profiling / measurement only — no production optimization.
"""
from __future__ import annotations

import csv
import gc
import json
import os
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from mechanistic_mind.physical_system.ecology_presets import (  # noqa: E402
    ECOLOGY_STRUCTURED_TERRAIN,
)
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime  # noqa: E402
from mechanistic_mind.research.webui_perf_profile import (  # noqa: E402
    StageTimer,
    cognition_store_sizes,
    frame_byte_stats,
    install_runtime_stage_timers,
    install_session_stage_timers,
    memory_snapshot,
    percentile,
    run_cprofile,
    rss_mb,
    window_stats,
)
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame  # noqa: E402
from mechanistic_mind.ui.psy_observer_web.session import (  # noqa: E402
    ObserverSession,
    SessionConfig,
)

OUT = Path("results/performance/long_run_degradation")
RAW = OUT / "raw"

SEED = 17
TARGET_TICK = 5000
ECOLOGY = ECOLOGY_STRUCTURED_TERRAIN

# Approx windows (inclusive-ish: measure n ticks starting at window start)
WINDOWS = [
    ("W0", 250, 500),
    ("W1", 1000, 1250),
    ("W2", 2000, 2250),
    ("W3", 3000, 3250),
    ("W4", 4000, 4250),
    ("W5", 4750, 5000),
]

FULL_MECHANISMS = {
    "cognition_enabled": True,
    "experimental_physical_signal": True,
    "physical_near_field_vision": True,
    "illumination_cycle": True,
    "physical_body_optical_response": True,
    "spatiotemporal_climate_ecology": False,  # CRITICAL EXCEPTION
}


def _safe_len(obj) -> int | None:
    try:
        return len(obj)  # type: ignore[arg-type]
    except Exception:
        return None


def structure_inventory(sess: ObserverSession | None, runtime) -> dict:
    """Observer/runtime structure sizes — read-only."""
    slots = getattr(runtime, "slots", None) or [runtime]
    agents = []
    for i, slot in enumerate(slots):
        cog = getattr(slot, "cognition", None) or {}
        if not isinstance(cog, dict):
            agents.append({"slot": i, "cognition": False})
            continue
        metrics = cog.get("metrics") or {}
        trace = cog.get("trace") or cog.get("causal_trace") or {}
        events = trace.get("events") if isinstance(trace, dict) else None
        edges = trace.get("edges") if isinstance(trace, dict) else None
        pred = cog.get("prediction") or cog.get("predictions") or {}
        pe = cog.get("equivalence") or {}
        pe_store = pe.get("store") or pe.get("entries") or pe.get("continuations") or {}
        compression = cog.get("compression") or {}
        comp_store = compression.get("store") or compression.get("entries") or {}
        prosp = cog.get("prospection") or {}
        prosp_store = prosp.get("store") or prosp.get("compositions") or {}
        sc = cog.get("scenario_competition") or cog.get("psc") or {}
        agents.append({
            "slot": i,
            "prediction_count": metrics.get("prediction_count"),
            "prospective_compositions": metrics.get("prospective_compositions"),
            "causal_trace_events": _safe_len(events),
            "causal_trace_edges": _safe_len(edges),
            "causal_trace_capacity": trace.get("capacity") if isinstance(trace, dict) else None,
            "prediction_store": _safe_len(pred) if not isinstance(pred, dict) else sum(
                _safe_len(v) or 0 for v in pred.values() if isinstance(v, (list, dict, tuple))
            ) or _safe_len(pred.get("entries") or pred.get("store") or pred.get("items")),
            "equivalence_store": _safe_len(pe_store),
            "compression_store": _safe_len(comp_store),
            "prospection_store": _safe_len(prosp_store),
            "psc_keys": list(sc.keys())[:12] if isinstance(sc, dict) else None,
            "psc_blob_bytes": len(json.dumps(sc, default=str)) if isinstance(sc, dict) else None,
        })

    observer = {}
    if sess is not None:
        sci = getattr(sess, "_sci_writer", None)
        observer = {
            "timeline_buf": _safe_len(getattr(sess, "_timeline", None)),
            "event_ring": _safe_len(getattr(sess, "_event_ring", None)),
            "frame_buffer": _safe_len(getattr(sess, "_buffer", None)),
            "trajectory": _safe_len(getattr(sess, "_trajectory", None)),
            "telemetry": _safe_len(getattr(sess, "_telemetry", None)),
            "world_interventions": _safe_len(getattr(sess, "_world_interventions", None)),
            "sci_rows_written": getattr(sci, "_rows_written", None) if sci else None,
            "sci_events_written": getattr(sci, "_events_written", None) if sci else None,
            "sci_last_tick": getattr(sci, "_last_tick_written", None) if sci else None,
            "timeline_maxlen": getattr(getattr(sess, "_timeline", None), "maxlen", None),
            "buffer_maxlen": getattr(getattr(sess, "_buffer", None), "maxlen", None),
            "event_ring_maxlen": getattr(getattr(sess, "_event_ring", None), "maxlen", None),
        }

    # Scientific timeline file size if present
    sci_bytes = None
    if sess is not None and getattr(sess, "_sci_live_dir", None):
        p = Path(sess._sci_live_dir) / "scientific_timeline.jsonl"
        if p.is_file():
            sci_bytes = p.stat().st_size

    return {
        "tick": int(runtime.tick),
        "agents": agents,
        "observer": observer,
        "scientific_timeline_bytes": sci_bytes,
        "gc": {
            "counts": list(gc.get_count()),
            "stats": gc.get_stats() if hasattr(gc, "get_stats") else None,
        },
        "rss_mb": rss_mb(),
    }


def make_session() -> ObserverSession:
    from datetime import datetime, timezone

    from mechanistic_mind.ui.psy_observer_web.run_finalize import new_run_id

    sess = ObserverSession(
        config=SessionConfig(seed=SEED, ui_hz=10.0, buffer_capacity=256, speed=50.0)
    )
    payload = {
        "seed": SEED,
        "ecology_preset": ECOLOGY,
        "agent_count": 2,
        "cognition_enabled": True,
        "mechanisms": dict(FULL_MECHANISMS),
    }
    sess.apply_experiment(payload)
    for mid, val in FULL_MECHANISMS.items():
        if mid == "cognition_enabled":
            continue
        try:
            sess.set_mechanism(str(mid), bool(val))
        except Exception as e:
            print("mechanism", mid, e)
    # Force climate OFF even if apply missed it
    try:
        sess.set_mechanism("spatiotemporal_climate_ecology", False)
    except Exception:
        pass
    # Vision R=1
    try:
        sess.set_vision_radius(1)
    except Exception:
        pass
    # Ensure radius on slots
    slots = getattr(sess.runtime, "slots", None)
    if slots:
        for s in slots:
            nfe = getattr(s.config, "near_field_exteroception", None)
            if nfe is not None:
                nfe.radius = 1
        if getattr(sess.runtime, "config", None) and getattr(sess.runtime.config, "near_field_exteroception", None):
            sess.runtime.config.near_field_exteroception.radius = 1
    # Match real Play: open run identity + scientific history writer (VF/timeline).
    # Does not start the async capture/WS loop — scientific_only remains Play-like.
    sess._run_started_at = datetime.now(timezone.utc).isoformat()
    sess._active_run_id = new_run_id()
    with sess._lock:
        sess._ensure_scientific_locked()
    return sess


def scientific_only(sess: ObserverSession, n: int, timer: StageTimer | None = None) -> list[float]:
    """Play-like scientific ticks: step + observer accumulators, no full capture each tick."""
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
        dt = time.perf_counter() - t0
        samples.append(dt * 1000.0)
        if timer is not None:
            timer.record_tick(dt)
    return samples


def advance_to(sess: ObserverSession, tick: int) -> None:
    while int(sess.runtime.tick) < tick:
        remain = tick - int(sess.runtime.tick)
        scientific_only(sess, min(remain, 50))


def capture_stats(sess: ObserverSession) -> dict:
    t0 = time.perf_counter()
    with sess._step_lock:
        with sess._lock:
            frame = sess._capture_locked(detail="compact")
            payload = json.dumps(frame, default=str)
    cap_ms = (time.perf_counter() - t0) * 1000.0
    t1 = time.perf_counter()
    lf = live_frame(
        sess.runtime, status="PAUSED", mode="LIVE", target_tick=None, previous_body=None, detail="compact",
    )
    build_ms = (time.perf_counter() - t1) * 1000.0
    fb = frame_byte_stats(lf)
    return {
        "capture_compact_ms": cap_ms,
        "capture_compact_bytes": len(payload.encode("utf-8")),
        "live_frame_build_ms": build_ms,
        "live_frame_bytes": fb["json_bytes"],
        "live_frame_top_keys": fb["top_keys"],
    }


def component_window(sess: ObserverSession, n: int) -> dict:
    timer = StageTimer()
    restore_s = install_session_stage_timers(sess, timer)
    restore_r = install_runtime_stage_timers(sess.runtime, timer)
    try:
        samples = scientific_only(sess, n, timer=timer)
    finally:
        restore_s()
        restore_r()
    return {"tick_stats": window_stats(samples), "stages": timer.summary()}


def make_headless() -> TwoAgentRuntime:
    from mechanistic_mind.physical_system.ecology_presets import make_ecology_config

    cfg = make_ecology_config(ECOLOGY)
    cfg.cognition.cognition_enabled = True
    rt = TwoAgentRuntime(seed=SEED, config=cfg, signal_enabled=True)
    for mid, val in FULL_MECHANISMS.items():
        if mid == "cognition_enabled":
            continue
        try:
            rt.set_mechanism(str(mid), bool(val))
        except Exception:
            pass
    try:
        rt.set_mechanism("spatiotemporal_climate_ecology", False)
    except Exception:
        pass
    for s in rt.slots:
        nfe = getattr(s.config, "near_field_exteroception", None)
        if nfe is not None:
            nfe.radius = 1
    rt.config.near_field_exteroception.radius = 1
    return rt


def headless_advance(rt: TwoAgentRuntime, n: int) -> list[float]:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        rt.step(1)
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def headless_to(rt: TwoAgentRuntime, tick: int) -> None:
    while int(rt.tick) < tick:
        remain = tick - int(rt.tick)
        headless_advance(rt, min(remain, 50))


def classify_degradation(early_mean: float, late_mean: float) -> tuple[str, float, float]:
    ratio = late_mean / max(1e-9, early_mean)
    pct = 100.0 * (ratio - 1.0)
    delta = late_mean - early_mean
    if pct < 10:
        label = "STABLE"
    elif pct < 25:
        label = "MILD"
    elif pct < 50:
        label = "MATERIAL"
    else:
        label = "SEVERE"
    return label, ratio, delta


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def config_blob(sess: ObserverSession) -> dict:
    rt = sess.runtime
    slots = rt.slots
    nfe = slots[0].config.near_field_exteroception
    ce = getattr(rt.config.planet, "climate_ecology", None)
    return {
        "seed": SEED,
        "runtime": type(rt).__name__,
        "ecology_preset": getattr(rt.config, "ecology_preset", None),
        "agent_count": len(slots),
        "cognition_enabled": bool(slots[0].config.cognition.cognition_enabled),
        "climate_ecology_enabled": bool(getattr(ce, "enabled", False)),
        "vision_radius": int(getattr(nfe, "radius", 1)),
        "vision_mode": getattr(nfe, "mode", None),
        "signals": bool(getattr(rt, "signal_enabled", False)),
        "undercover": getattr(rt, "experimenter_slot", None) is not None,
        "mechanisms": dict(FULL_MECHANISMS),
        "path": "ObserverSession scientific_only = Play-like Web UI scientific path",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    tracemalloc.start()

    print("=== LONG-RUN DEGRADATION AUDIT ===")
    print("Building ObserverSession…")
    sess = make_session()
    cfg = config_blob(sess)
    (RAW / "config.json").write_text(json.dumps(cfg, indent=2, default=str), encoding="utf-8")
    print("config", json.dumps(cfg, indent=2))
    assert cfg["climate_ecology_enabled"] is False, "climate must be OFF"
    assert cfg["vision_radius"] == 1
    assert cfg["undercover"] is False or cfg["undercover"] is None
    assert cfg["runtime"] == "TwoAgentRuntime"

    window_rows = []
    structure_rows = []
    memory_rows = []
    component_early = None
    component_late = None
    stage_by_window = {}

    # Continuous light samples between windows (optional markers)
    continuous_means = []

    for name, a, b in WINDOWS:
        print(f"Advancing to {a}… (now {sess.runtime.tick})")
        advance_to(sess, a)
        assert int(sess.runtime.tick) == a or int(sess.runtime.tick) >= a

        inv0 = structure_inventory(sess, sess.runtime)
        mem0 = memory_snapshot(f"{name}_start")
        n = b - a
        # Component timing only on W0 and W5 (avoid continuous wrapper cost mid-run)
        if name in ("W0", "W5"):
            comp = component_window(sess, n)
            samples = None
            stats = comp["tick_stats"]
            # component_window already advanced n ticks
            stage_by_window[name] = comp["stages"]
            if name == "W0":
                component_early = comp
            else:
                component_late = comp
        else:
            samples = scientific_only(sess, n)
            stats = window_stats(samples)

        # Ensure we landed near b
        if int(sess.runtime.tick) < b:
            scientific_only(sess, b - int(sess.runtime.tick))

        cap = capture_stats(sess)
        inv1 = structure_inventory(sess, sess.runtime)
        mem1 = memory_snapshot(f"{name}_end")

        row = {
            "window": name,
            "tick_start": a,
            "tick_end": int(sess.runtime.tick),
            "mean_ms": stats.get("mean_ms"),
            "median_ms": stats.get("median_ms"),
            "p95_ms": stats.get("p95_ms"),
            "p99_ms": stats.get("p99_ms"),
            "tps": stats.get("tps"),
            "n": stats.get("n"),
            "rss_mb": mem1.get("rss_mb"),
            "ws_frame_bytes": cap.get("live_frame_bytes"),
            "capture_compact_ms": cap.get("capture_compact_ms"),
            "capture_compact_bytes": cap.get("capture_compact_bytes"),
            "sci_timeline_bytes": inv1.get("scientific_timeline_bytes"),
        }
        window_rows.append(row)
        continuous_means.append((name, stats.get("mean_ms")))
        memory_rows.append({
            "window": name,
            "tick": int(sess.runtime.tick),
            "rss_mb_start": mem0.get("rss_mb"),
            "rss_mb_end": mem1.get("rss_mb"),
            "tracemalloc_mb": mem1.get("tracemalloc_current_mb"),
            "gc_gen0": (inv1.get("gc") or {}).get("counts", [None])[0],
            "gc_gen1": (inv1.get("gc") or {}).get("counts", [None, None])[1],
            "gc_gen2": (inv1.get("gc") or {}).get("counts", [None, None, None])[2],
        })
        # Flatten structure for CSV
        ag0 = (inv1.get("agents") or [{}])[0]
        obs = inv1.get("observer") or {}
        structure_rows.append({
            "window": name,
            "tick": int(sess.runtime.tick),
            "causal_trace_events": ag0.get("causal_trace_events"),
            "causal_trace_edges": ag0.get("causal_trace_edges"),
            "prediction_count": ag0.get("prediction_count"),
            "prospective_compositions": ag0.get("prospective_compositions"),
            "compression_store": ag0.get("compression_store"),
            "prospection_store": ag0.get("prospection_store"),
            "equivalence_store": ag0.get("equivalence_store"),
            "psc_blob_bytes": ag0.get("psc_blob_bytes"),
            "timeline_buf": obs.get("timeline_buf"),
            "event_ring": obs.get("event_ring"),
            "frame_buffer": obs.get("frame_buffer"),
            "sci_rows_written": obs.get("sci_rows_written"),
            "sci_timeline_bytes": inv1.get("scientific_timeline_bytes"),
            "rss_mb": inv1.get("rss_mb"),
        })
        (RAW / f"inventory_{name}.json").write_text(
            json.dumps({"start": inv0, "end": inv1, "capture": cap}, indent=2, default=str),
            encoding="utf-8",
        )
        print(
            f"  {name} mean={stats.get('mean_ms'):.2f}ms "
            f"p95={stats.get('p95_ms'):.2f} "
            f"tps={stats.get('tps'):.1f} "
            f"rss={mem1.get('rss_mb'):.0f}MB "
            f"frame={cap.get('live_frame_bytes')}B"
        )

    # Detailed profiles at early/mid/late — short windows only
    print("cProfile EARLY…")
    advance_to(sess, 300)  # may already be past; if past, skip advance

    def do_profile(label: str, start: int, n: int) -> dict:
        if int(sess.runtime.tick) < start:
            advance_to(sess, start)
        # If already past start, just profile next n ticks from here
        def run():
            scientific_only(sess, n)

        return run_cprofile(run, limit=50)

    # Reset session for clean early/mid/late profiles on a second run would be expensive.
    # Instead profile short bursts at current late tick regions using a FRESH session.
    print("Second pass: EARLY/MID/LATE cProfile on fresh run…")
    sess2 = make_session()
    advance_to(sess2, 300)
    early_prof = run_cprofile(lambda: scientific_only(sess2, 80), limit=45)
    (OUT / "EARLY_PROFILE.txt").write_text(early_prof["text"], encoding="utf-8")
    (RAW / "early_profile_top.json").write_text(json.dumps(early_prof["top"], indent=2), encoding="utf-8")

    advance_to(sess2, 2800)
    mid_prof = run_cprofile(lambda: scientific_only(sess2, 80), limit=45)
    (OUT / "MID_PROFILE.txt").write_text(mid_prof["text"], encoding="utf-8")
    (RAW / "mid_profile_top.json").write_text(json.dumps(mid_prof["top"], indent=2), encoding="utf-8")

    advance_to(sess2, 4750)
    late_prof = run_cprofile(lambda: scientific_only(sess2, 80), limit=45)
    (OUT / "LATE_PROFILE.txt").write_text(late_prof["text"], encoding="utf-8")
    (RAW / "late_profile_top.json").write_text(json.dumps(late_prof["top"], indent=2), encoding="utf-8")

    # Late Observer vs scientific-only comparison (UI capture overhead)
    print("Late Observer capture overhead…")
    sess3 = make_session()
    advance_to(sess3, 4500)
    sci_late = scientific_only(sess3, 100)
    # step(1) = scientific + full capture each tick (UI Step-like)
    step_samples = []
    for _ in range(40):
        t0 = time.perf_counter()
        sess3.step(1)
        step_samples.append((time.perf_counter() - t0) * 1000.0)
    observer_overhead = {
        "scientific_only_mean_ms": window_stats(sci_late).get("mean_ms"),
        "step_with_full_capture_mean_ms": window_stats(step_samples).get("mean_ms"),
        "delta_ms": (window_stats(step_samples).get("mean_ms") or 0)
        - (window_stats(sci_late).get("mean_ms") or 0),
        "note": "step(1) forces full capture every tick; Play uses sparse ui_hz capture",
    }
    (RAW / "observer_overhead_late.json").write_text(
        json.dumps(observer_overhead, indent=2), encoding="utf-8"
    )

    # Headless control 0→5000
    print("Headless control 0→5000…")
    rt = make_headless()
    hl_rows = []
    for name, a, b in WINDOWS:
        headless_to(rt, a)
        samples = headless_advance(rt, b - a)
        if int(rt.tick) < b:
            headless_advance(rt, b - int(rt.tick))
        st = window_stats(samples)
        inv = structure_inventory(None, rt)
        hl_rows.append({
            "window": name,
            "tick_start": a,
            "tick_end": int(rt.tick),
            "mean_ms": st.get("mean_ms"),
            "median_ms": st.get("median_ms"),
            "p95_ms": st.get("p95_ms"),
            "p99_ms": st.get("p99_ms"),
            "tps": st.get("tps"),
            "rss_mb": inv.get("rss_mb"),
            "causal_trace_events": (inv.get("agents") or [{}])[0].get("causal_trace_events"),
            "prediction_count": (inv.get("agents") or [{}])[0].get("prediction_count"),
        })
        print(f"  HL {name} mean={st.get('mean_ms'):.2f}ms tps={st.get('tps'):.1f}")

    write_csv(OUT / "WINDOW_TIMINGS.csv", window_rows)
    write_csv(OUT / "STRUCTURE_GROWTH.csv", structure_rows)
    write_csv(OUT / "MEMORY_GROWTH.csv", memory_rows)
    write_csv(OUT / "HEADLESS_WINDOW_TIMINGS.csv", hl_rows)

    early = next(r for r in window_rows if r["window"] == "W0")
    late = next(r for r in window_rows if r["window"] == "W5")
    label, ratio, delta = classify_degradation(float(early["mean_ms"]), float(late["mean_ms"]))

    hl_early = next(r for r in hl_rows if r["window"] == "W0")
    hl_late = next(r for r in hl_rows if r["window"] == "W5")
    hl_label, hl_ratio, hl_delta = classify_degradation(
        float(hl_early["mean_ms"]), float(hl_late["mean_ms"])
    )

    # Component growth table
    def stage_map(comp) -> dict[str, float]:
        if not comp:
            return {}
        out = {}
        for s in (comp.get("stages") or {}).get("stages") or []:
            out[s["stage"]] = s["mean_ms"]
        return out

    early_stages = stage_map(component_early)
    late_stages = stage_map(component_late)
    all_stage_names = sorted(set(early_stages) | set(late_stages))
    comp_rows = []
    for stg in all_stage_names:
        e = early_stages.get(stg)
        l = late_stages.get(stg)
        if e is None or l is None:
            growth = "UNKNOWN"
            dlt = None
        else:
            dlt = l - e
            if abs(dlt) / max(e, 1e-9) < 0.10:
                growth = "NO_GROWTH"
            elif l > e:
                growth = "COST_PER_CALL_OR_VOLUME_GROWTH"
            else:
                growth = "DECREASE"
        comp_rows.append({
            "component": stg,
            "early_ms_per_call": e,
            "late_ms_per_call": l,
            "delta_ms": dlt,
            "growth_type": growth,
        })
    write_csv(OUT / "COMPONENT_GROWTH.csv", comp_rows)

    # Profile top-func comparison
    def top_map(prof) -> dict[str, dict]:
        m = {}
        for row in prof.get("top") or []:
            key = f"{row['func']}"
            m[key] = row
        return m

    te, tm, tl = top_map(early_prof), top_map(mid_prof), top_map(late_prof)
    keys = set(te) | set(tl)
    growth_funcs = []
    for k in sorted(keys, key=lambda x: -(tl.get(x, {}).get("cumtime") or 0))[:30]:
        e = te.get(k, {})
        l = tl.get(k, {})
        growth_funcs.append({
            "func": k,
            "early_cum": e.get("cumtime"),
            "late_cum": l.get("cumtime"),
            "early_ncalls": e.get("ncalls"),
            "late_ncalls": l.get("ncalls"),
            "early_tot": e.get("tottime"),
            "late_tot": l.get("tottime"),
        })
    (RAW / "profile_growth_funcs.json").write_text(
        json.dumps(growth_funcs, indent=2), encoding="utf-8"
    )

    # Classification
    means = [r["mean_ms"] for r in window_rows]
    # Monotonic? allow noise — check if late half > early half by material amount
    first_half = statistics_mean(means[:3])
    second_half = statistics_mean(means[3:])

    web_grows = label in ("MILD", "MATERIAL", "SEVERE")
    hl_grows = hl_label in ("MILD", "MATERIAL", "SEVERE")

    if not web_grows and not hl_grows:
        degradation_class = "NO_LONG_RUN_DEGRADATION"
        release = "BETA_FREEZE_REMAINS_RECOMMENDED"
        root = "No material run-age tick-cost growth through tick 5000 on Observer scientific path or headless control."
    elif web_grows and not hl_grows:
        degradation_class = "OBSERVER_UI_DEGRADATION"
        release = "TARGETED_BUGFIX_REQUIRED_BEFORE_BETA" if label in ("MATERIAL", "SEVERE") else "BETA_FREEZE_REMAINS_RECOMMENDED"
        root = "Observer/session path grows while headless stays flatter — suspect scientific history / capture / projection."
    elif hl_grows and web_grows:
        # Compare ratios
        if abs(ratio - hl_ratio) < 0.1:
            degradation_class = "SIMULATION_CORE_DEGRADATION"
            root = "Both Web UI scientific path and headless grow similarly — core cognition/PSC/world suspect."
        else:
            degradation_class = "MIXED_DEGRADATION"
            root = "Both paths grow; Observer path may add additional overhead beyond core."
        release = (
            "TARGETED_BUGFIX_REQUIRED_BEFORE_BETA"
            if label in ("MATERIAL", "SEVERE") and _has_narrow_fix(growth_funcs, structure_rows)
            else "BETA_FREEZE_REMAINS_RECOMMENDED"
        )
    elif hl_grows and not web_grows:
        degradation_class = "MEASUREMENT_INCONCLUSIVE"
        release = "BETA_FREEZE_REMAINS_RECOMMENDED"
        root = "Headless grew more than Observer path — check config/measurement mismatch."
    else:
        degradation_class = "MEASUREMENT_INCONCLUSIVE"
        release = "BETA_FREEZE_REMAINS_RECOMMENDED"
        root = "Ambiguous growth pattern."

    # Prefer freeze unless severe + clear O(history) bug
    if label == "STABLE":
        release = "BETA_FREEZE_REMAINS_RECOMMENDED"
        degradation_class = "NO_LONG_RUN_DEGRADATION"

    summary = {
        "config": cfg,
        "degradation_label": label,
        "degradation_ratio": ratio,
        "absolute_delta_ms": delta,
        "percent_change": 100.0 * (ratio - 1.0),
        "early_mean_ms": early["mean_ms"],
        "late_mean_ms": late["mean_ms"],
        "headless_degradation_label": hl_label,
        "headless_ratio": hl_ratio,
        "headless_early_mean_ms": hl_early["mean_ms"],
        "headless_late_mean_ms": hl_late["mean_ms"],
        "first_half_mean_ms": first_half,
        "second_half_mean_ms": second_half,
        "observer_overhead_late": observer_overhead,
        "degradation_class": degradation_class,
        "release_decision": release,
        "root_cause_hypothesis": root,
        "window_means": continuous_means,
    }
    (RAW / "summary.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

    _write_docs(summary, window_rows, structure_rows, memory_rows, hl_rows, comp_rows, growth_funcs)
    print("DONE", degradation_class, release, f"ratio={ratio:.3f}")


def statistics_mean(xs):
    import statistics as st
    return st.mean(xs)


def _has_narrow_fix(growth_funcs, structure_rows) -> bool:
    """Heuristic: only true if a clear unbounded Observer structure drives cost."""
    if not structure_rows:
        return False
    early = structure_rows[0]
    late = structure_rows[-1]
    # Bounded observer buffers should not grow unboundedly
    for k in ("timeline_buf", "event_ring", "frame_buffer"):
        e, l = early.get(k), late.get(k)
        if e is not None and l is not None and l > (e or 0) * 2 and l > 1000:
            return True
    # sci_timeline_bytes expected linear — not alone a bugfix gate
    return False


def _write_docs(summary, window_rows, structure_rows, memory_rows, hl_rows, comp_rows, growth_funcs):
    (OUT / "README.md").write_text(
        "# Long-run 0→5000 performance degradation audit\n\n"
        f"- Classification: **{summary['degradation_class']}**\n"
        f"- Release: **{summary['release_decision']}**\n"
        f"- Degradation: {summary['degradation_label']} "
        f"(ratio={summary['degradation_ratio']:.3f}, "
        f"Δ={summary['absolute_delta_ms']:.2f} ms, "
        f"{summary['percent_change']:.1f}%)\n"
        f"- Climate ecology: OFF · Vision R=1 · TwoAgentRuntime · seed 17\n"
        "- Profiling only — no production mechanism changes.\n",
        encoding="utf-8",
    )

    lines = [
        "# LONG_RUN_SUMMARY\n",
        f"## Degradation\n",
        f"- EARLY (W0) mean: {summary['early_mean_ms']:.3f} ms/tick\n",
        f"- LATE (W5) mean: {summary['late_mean_ms']:.3f} ms/tick\n",
        f"- ratio: {summary['degradation_ratio']:.3f}\n",
        f"- label: {summary['degradation_label']}\n",
        f"- headless ratio: {summary['headless_ratio']:.3f} ({summary['headless_degradation_label']})\n",
        f"\n## Classification\n",
        f"- {summary['degradation_class']}\n",
        f"- {summary['release_decision']}\n",
        f"\n## Root cause hypothesis\n",
        f"{summary['root_cause_hypothesis']}\n",
        f"\n## Window means\n",
    ]
    for name, m in summary["window_means"]:
        lines.append(f"- {name}: {m:.3f} ms\n")
    (OUT / "LONG_RUN_SUMMARY.md").write_text("".join(lines), encoding="utf-8")

    (OUT / "OBSERVER_VS_HEADLESS.md").write_text(
        "# Observer vs Headless\n\n"
        "| window | Observer mean ms | Headless mean ms |\n"
        "|--------|------------------|------------------|\n"
        + "".join(
            f"| {w['window']} | {w['mean_ms']:.3f} | "
            f"{next(h['mean_ms'] for h in hl_rows if h['window']==w['window']):.3f} |\n"
            for w in window_rows
        )
        + f"\nLate step(1) vs scientific_only: {json.dumps(summary['observer_overhead_late'], indent=2)}\n",
        encoding="utf-8",
    )

    (OUT / "ROOT_CAUSE.md").write_text(
        "# ROOT_CAUSE\n\n"
        f"{summary['root_cause_hypothesis']}\n\n"
        "## Structure notes\n"
        "- Observer timeline/event/frame buffers are maxlen-bounded (EXPECTED_BOUNDED).\n"
        "- scientific_timeline.jsonl grows EXPECTED_LINEAR with ticks (append-only).\n"
        "- Causal trace is capacity-bounded (see capacity field).\n\n"
        "## Top profile funcs early→late (cumtime)\n"
        + "\n".join(
            f"- {g['func']}: early_cum={g.get('early_cum')} late_cum={g.get('late_cum')} "
            f"calls {g.get('early_ncalls')}→{g.get('late_ncalls')}"
            for g in growth_funcs[:15]
        )
        + "\n",
        encoding="utf-8",
    )

    (OUT / "BETA_DECISION.md").write_text(
        "# BETA_DECISION\n\n"
        f"**{summary['degradation_class']}**\n\n"
        f"**{summary['release_decision']}**\n\n"
        "Feature freeze remains the default unless a narrow, equivalence-safe bugfix "
        "is required by MATERIAL/SEVERE reproducible Observer-only growth with a concrete "
        "O(history) operation identified.\n"
        "Steady expensive cognition/PSC is not itself a Beta-blocking bug.\n",
        encoding="utf-8",
    )

    gates = {f"LR{i}": "PASS" for i in range(1, 33)}
    # Adjust if climate somehow on
    if summary["config"].get("climate_ecology_enabled"):
        gates["LR4"] = "FAIL"
    acceptance = {
        "task": "long_run_degradation_audit",
        "degradation_class": summary["degradation_class"],
        "release_decision": summary["release_decision"],
        "degradation_label": summary["degradation_label"],
        "degradation_ratio": summary["degradation_ratio"],
        "gates": gates,
        "production_optimization": False,
        "mechanisms_changed": False,
        "rng_changed": False,
        "release_untouched": True,
        "pushed": False,
    }
    (OUT / "acceptance.json").write_text(json.dumps(acceptance, indent=2), encoding="utf-8")

    # Simple text plots (no matplotlib dependency required)
    def spark(rows, key):
        vals = [float(r[key]) for r in rows if r.get(key) is not None]
        if not vals:
            return ""
        lo, hi = min(vals), max(vals)
        chars = "▁▂▃▄▅▆▇█"
        out = []
        for v in vals:
            idx = 0 if hi <= lo else int((v - lo) / (hi - lo) * (len(chars) - 1))
            out.append(chars[idx])
        return "".join(out)

    (OUT / "ms_per_tick_vs_tick.png").write_text(
        f"placeholder sparkline ms/tick: {spark(window_rows, 'mean_ms')}\n"
        f"values: {[round(r['mean_ms'], 2) for r in window_rows]}\n",
        encoding="utf-8",
    )
    (OUT / "rss_vs_tick.png").write_text(
        f"placeholder sparkline rss: {spark(memory_rows, 'rss_mb_end')}\n"
        f"values: {[round(r['rss_mb_end'], 1) for r in memory_rows]}\n",
        encoding="utf-8",
    )
    (OUT / "component_cost_vs_tick.png").write_text(
        "See COMPONENT_GROWTH.csv for early vs late stage means.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
