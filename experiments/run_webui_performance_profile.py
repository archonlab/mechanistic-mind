#!/usr/bin/env python3
"""REAL Web-UI path performance profiling for Mechanistic Mind / Tiktaalik.

Primary subject: ObserverSession scientific step + capture path used by Psy Observer.
Headless TwoAgentRuntime.step is CONTROL ONLY.

Does not retune equations, RNG, cognition, vision, ecology, or defaults.
"""
from __future__ import annotations

import json
import os
import sys
import time
import tracemalloc
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from mechanistic_mind.physical_system.ecology_presets import (  # noqa: E402
    ECOLOGY_BASELINE,
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
    run_cprofile,
    window_stats,
)
from mechanistic_mind.ui.psy_observer_web.serialize import live_frame  # noqa: E402
from mechanistic_mind.ui.psy_observer_web.session import (  # noqa: E402
    ObserverSession,
    SessionConfig,
)

OUT = Path("results/performance/webui_profiling")
RAW = OUT / "raw"
BENCH = OUT / "benchmarks"
PROTO = OUT / "numpy_prototypes"

SEED = 17
WARMUP = 150
PROFILE_TICKS = 400  # short representative window
GROWTH_WINDOWS = [
    (100, 200),
    (200, 300),
    (300, 400),
    (450, 550),
]


FULL_MECHANISMS = {
    "cognition_enabled": True,
    "experimental_physical_signal": True,
    "physical_near_field_vision": True,
    "illumination_cycle": True,
    "physical_body_optical_response": True,
}


def _cfg_blob(sess: ObserverSession) -> dict:
    rt = sess.runtime
    slots = getattr(rt, "slots", None)
    nfe = None
    if slots:
        nfe = getattr(slots[0].config, "near_field_exteroception", None)
    else:
        nfe = getattr(rt.config, "near_field_exteroception", None)
    return {
        "seed": SEED,
        "runtime": type(rt).__name__,
        "ecology_preset": getattr(getattr(rt, "config", None), "ecology_preset", None)
        or (getattr(slots[0].config, "ecology_preset", None) if slots else None),
        "agent_count": len(slots) if slots else 1,
        "cognition_enabled": bool(
            (slots[0] if slots else rt).config.cognition.cognition_enabled
        ),
        "signal_enabled": bool(getattr(rt, "signal_enabled", False)),
        "near_field_mode": getattr(nfe, "mode", None),
        "vision_perception": getattr(nfe, "perception_enabled", None),
        "illumination": getattr(nfe, "illumination_enabled", None),
        "body_optics": getattr(nfe, "body_optical_enabled", None),
        "undercover": getattr(rt, "experimenter_slot", None) is not None,
        "ui_hz": float(sess.config.ui_hz),
        "speed": float(sess.config.speed),
        "note": "ObserverSession path = Web UI scientific step + observer accumulators",
    }


def make_session(
    *,
    ecology: str,
    agent_count: int = 2,
    mechanisms: dict | None = None,
    ui_hz: float = 10.0,
    undercover: bool = False,
) -> ObserverSession:
    sess = ObserverSession(config=SessionConfig(seed=SEED, ui_hz=ui_hz, buffer_capacity=256))
    payload = {
        "seed": SEED,
        "ecology_preset": ecology,
        "agent_count": agent_count,
        "cognition_enabled": True,
        "mechanisms": dict(mechanisms or FULL_MECHANISMS),
    }
    sess.apply_experiment(payload)
    # Ensure mechanisms applied (apply_experiment already does non_cog + set_mechanism)
    for mid, val in (mechanisms or FULL_MECHANISMS).items():
        if mid == "cognition_enabled":
            continue
        try:
            sess.set_mechanism(str(mid), bool(val))
        except Exception:
            pass
    if undercover:
        try:
            sess.experimenter_spawn(x=14.0, y=16.0)
        except Exception as e:
            print("undercover spawn skipped:", e)
    return sess


def step_n(sess: ObserverSession, n: int, *, capture_each: bool = False) -> list[float]:
    """Drive REAL Web UI step path (ObserverSession.step). Returns per-call wall ms.

    Note: sess.step(1) does one scientific tick + full capture (matches UI Step).
    For play-like scientific ticks without per-tick full capture, use scientific_only.
    """
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        sess.step(1)
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def scientific_only(sess: ObserverSession, n: int) -> list[float]:
    """Scientific tick + observer accumulators WITHOUT full live_frame capture.

    Matches the Play loop's per-tick scientific work more closely than step(1),
    which forces a full capture every call (UI Step button).
    """
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


def capture_once(sess: ObserverSession, *, detail: str = "compact") -> tuple[float, dict]:
    t0 = time.perf_counter()
    with sess._step_lock:
        with sess._lock:
            frame = sess._capture_locked(detail=detail)
            # Force serialize like capture worker
            payload = json.dumps(frame, default=str)
    ms = (time.perf_counter() - t0) * 1000.0
    return ms, {"json_bytes": len(payload.encode("utf-8")), **frame_byte_stats(frame)}


def headless_control(ecology: str, ticks: int) -> dict:
    """CONTROL ONLY — same seed/ecology/mechanisms, no ObserverSession."""
    from mechanistic_mind.physical_system.ecology_presets import make_ecology_config

    cfg = make_ecology_config(ecology)
    cfg.cognition.cognition_enabled = True
    rt = TwoAgentRuntime(seed=SEED, config=cfg, signal_enabled=True)
    for mid in (
        "physical_near_field_vision",
        "illumination_cycle",
        "physical_body_optical_response",
    ):
        try:
            rt.set_mechanism(mid, True)
        except Exception:
            pass
    # warm-up
    for _ in range(min(50, ticks // 4)):
        rt.step(1)
    samples = []
    t0 = time.perf_counter()
    for _ in range(ticks):
        t1 = time.perf_counter()
        rt.step(1)
        samples.append((time.perf_counter() - t1) * 1000.0)
    wall = time.perf_counter() - t0
    return {
        "label": "HEADLESS_CONTROL",
        "ecology": ecology,
        "ticks": ticks,
        "wall_s": wall,
        "tick_stats": window_stats(samples),
        "store_sizes": cognition_store_sizes(rt),
        "memory": memory_snapshot("headless_end"),
    }


def run_growth_windows(sess: ObserverSession) -> list[dict]:
    """Advance through windows on SAME run; measure scientific_only cost."""
    results = []
    # Ensure we start near tick 0 after apply
    cur = int(sess.runtime.tick)
    # Warm to first window start if needed
    target_start = GROWTH_WINDOWS[0][0]
    if cur < target_start:
        scientific_only(sess, target_start - cur)
    for a, b in GROWTH_WINDOWS:
        # Advance to window start
        while int(sess.runtime.tick) < a:
            scientific_only(sess, 1)
        n = b - a
        mem0 = memory_snapshot(f"win_{a}_{b}_start")
        stores0 = cognition_store_sizes(sess.runtime)
        samples = scientific_only(sess, n)
        # Capture cost sample (compact) at end of window
        cap_ms, cap_stats = capture_once(sess, detail="compact")
        # Serialization of live_frame alone
        t0 = time.perf_counter()
        frame = live_frame(
            sess.runtime, status="PAUSED", mode="LIVE", target_tick=None, previous_body=None, detail="compact",
        )
        ser_ms = (time.perf_counter() - t0) * 1000.0
        fb = frame_byte_stats(frame)
        results.append({
            "window": [a, b],
            "tick_stats": window_stats(samples),
            "memory_start": mem0,
            "memory_end": memory_snapshot(f"win_{a}_{b}_end"),
            "store_sizes": cognition_store_sizes(sess.runtime),
            "store_sizes_start": stores0,
            "capture_compact_ms": cap_ms,
            "capture_compact_bytes": cap_stats.get("json_bytes"),
            "live_frame_build_ms": ser_ms,
            "live_frame_bytes": fb["json_bytes"],
            "live_frame_top_keys": fb["top_keys"],
        })
    return results


def numpy_grid_microproto() -> dict:
    """Isolated micro-prototype: Python nested loops vs NumPy on a climate-like grid.

    NOT production code. Measures vectorization potential for regular fields only.
    """
    import numpy as np

    h, w = 32, 32
    rng = np.random.default_rng(17)
    A = rng.random((h, w))
    B = rng.random((h, w))
    alpha = 0.07

    def py_diffuse(src, dst, a):
        for y in range(h):
            for x in range(w):
                s = 0.0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        s += src[(y + dy) % h][(x + dx) % w]
                dst[y][x] = (1.0 - a) * src[y][x] + a * (s / 8.0)

    src_py = A.tolist()
    dst_py = [[0.0] * w for _ in range(h)]
    t0 = time.perf_counter()
    for _ in range(200):
        py_diffuse(src_py, dst_py, alpha)
        src_py, dst_py = dst_py, src_py
    py_s = time.perf_counter() - t0

    src = A.copy()
    t0 = time.perf_counter()
    for _ in range(200):
        rolled = (
            np.roll(src, 1, 0) + np.roll(src, -1, 0)
            + np.roll(src, 1, 1) + np.roll(src, -1, 1)
            + np.roll(np.roll(src, 1, 0), 1, 1)
            + np.roll(np.roll(src, 1, 0), -1, 1)
            + np.roll(np.roll(src, -1, 0), 1, 1)
            + np.roll(np.roll(src, -1, 0), -1, 1)
        )
        src = (1.0 - alpha) * src + alpha * (rolled / 8.0)
    np_s = time.perf_counter() - t0

    # Compare final py vs np (after same steps) — rebuild py reference
    src_py = A.tolist()
    dst_py = [[0.0] * w for _ in range(h)]
    for _ in range(200):
        py_diffuse(src_py, dst_py, alpha)
        src_py, dst_py = dst_py, src_py
    py_arr = np.array(src_py, dtype=float)
    abs_err = np.abs(py_arr - src)
    return {
        "operation": "8-neighbor diffusion 32x32 x200",
        "python_s": py_s,
        "numpy_s": np_s,
        "speedup": py_s / max(1e-12, np_s),
        "max_abs_error": float(abs_err.max()),
        "mean_abs_error": float(abs_err.mean()),
        "note": (
            "Isolated field kernel only. Not MM climate code. "
            "FP differences may accumulate in long trajectories."
        ),
        "recommendation_context": "Illustrates HIGH suitability for regular grid kernels IF they dominate wall time.",
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    BENCH.mkdir(parents=True, exist_ok=True)
    PROTO.mkdir(parents=True, exist_ok=True)

    tracemalloc.start()
    ecology = ECOLOGY_STRUCTURED_TERRAIN  # full: climate + terrain + calibrated vision

    # ---- A) REAL Web UI path: ObserverSession scientific + periodic capture ----
    print("=== A) Web UI path (STRUCTURED_TERRAIN, 2 agents, cognition+vision+signals) ===")
    sess = make_session(ecology=ecology, agent_count=2, ui_hz=10.0)
    cfg = _cfg_blob(sess)
    (RAW / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print("config:", json.dumps(cfg))

    mem_start = memory_snapshot("start")
    print(f"warmup {WARMUP} scientific ticks...")
    warm = scientific_only(sess, WARMUP)
    (RAW / "warmup_tick_ms.json").write_text(json.dumps(window_stats(warm), indent=2), encoding="utf-8")

    # Instrumented profiled interval
    timer = StageTimer()
    restore_rt = install_runtime_stage_timers(sess.runtime, timer)
    restore_sess = install_session_stage_timers(sess, timer)
    print(f"profile {PROFILE_TICKS} scientific ticks (instrumented)...")
    t0 = time.perf_counter()
    prof_samples = []
    for _ in range(PROFILE_TICKS):
        t1 = time.perf_counter()
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()
                sess._update_perf_locked(tick=True)
        dt = time.perf_counter() - t1
        timer.record_tick(dt)
        prof_samples.append(dt * 1000.0)
    # Periodic captures (like ui_hz-limited Play): ~every 10 ticks ≈ 1 capture / 10 sci ticks at high speed
    cap_samples = []
    for _ in range(20):
        ms, st = capture_once(sess, detail="compact")
        cap_samples.append({"ms": ms, **st})
    wall_instr = time.perf_counter() - t0
    stage_sum = timer.summary()
    restore_rt()
    restore_sess()

    # Non-instrumented wall-clock (profiler overhead estimate)
    print("non-instrumented wall sample (200 ticks)...")
    plain = scientific_only(sess, 200)
    plain_stats = window_stats(plain)
    instr_mean = window_stats(prof_samples)["mean_ms"] or 1.0
    overhead_pct = 100.0 * (instr_mean - (plain_stats["mean_ms"] or instr_mean)) / instr_mean

    webui_normal = {
        "label": "WEBUI_SCIENTIFIC_PATH",
        "primary": True,
        "config": cfg,
        "warmup_ticks": WARMUP,
        "profiled_ticks": PROFILE_TICKS,
        "wall_instrumented_s": wall_instr,
        "tick_stats_instrumented": window_stats(prof_samples),
        "tick_stats_noninstrumented_200": plain_stats,
        "profiler_overhead_pct_estimate": overhead_pct,
        "stages": stage_sum,
        "capture_compact_samples": {
            "n": len(cap_samples),
            "mean_ms": sum(c["ms"] for c in cap_samples) / len(cap_samples),
            "mean_json_bytes": sum(c["json_bytes"] for c in cap_samples) / len(cap_samples),
            "p95_ms": sorted(c["ms"] for c in cap_samples)[int(0.95 * (len(cap_samples) - 1))],
        },
        "memory_start": mem_start,
        "memory_end": memory_snapshot("webui_profile_end"),
        "store_sizes": cognition_store_sizes(sess.runtime),
        "note": (
            "Primary metric = ObserverSession scientific tick + observer accumulators "
            "(Play loop body). UI Step also does full capture each press; Play decouples "
            "capture to ui_hz. Capture costs reported separately."
        ),
    }
    (BENCH / "webui_normal.json").write_text(json.dumps(webui_normal, indent=2), encoding="utf-8")
    (RAW / "timing_samples.json").write_text(json.dumps({
        "instrumented_ms": prof_samples,
        "noninstrumented_ms": plain,
        "warmup_ms": warm,
    }, indent=2), encoding="utf-8")

    # cProfile on scientific path
    print("cProfile (300 ticks)...")
    def _run_cp():
        scientific_only(sess, 300)

    cprof = run_cprofile(_run_cp, limit=50)
    (RAW / "python_profile.txt").write_text(cprof["text"], encoding="utf-8")
    (RAW / "python_profile.json").write_text(json.dumps(cprof["top"], indent=2), encoding="utf-8")

    # ---- Growth windows on a fresh session ----
    print("=== Growth windows (fresh session) ===")
    sess_g = make_session(ecology=ecology, agent_count=2)
    growth = run_growth_windows(sess_g)
    (RAW / "growth_windows.json").write_text(json.dumps(growth, indent=2), encoding="utf-8")

    # ---- B) Render reduced: lower ui_hz, measure play-like capture rate ----
    print("=== B) Render-reduced (ui_hz=2) capture cadence ===")
    sess_r = make_session(ecology=ecology, agent_count=2, ui_hz=2.0)
    scientific_only(sess_r, 100)
    # Simulate: 300 sci ticks, capture every max(1, int(10/ui_hz))-style → at ui_hz=2 fewer captures
    # Play uses observer_capture_period; approximate: capture every 25 sci ticks at speed=1
    samples_sci = scientific_only(sess_r, 300)
    caps = []
    for i in range(12):  # fewer captures
        ms, st = capture_once(sess_r, detail="compact")
        caps.append({"ms": ms, "bytes": st["json_bytes"]})
    webui_render_reduced = {
        "label": "WEBUI_RENDER_REDUCED",
        "ui_hz": 2.0,
        "scientific_ticks": 300,
        "tick_stats": window_stats(samples_sci),
        "captures": len(caps),
        "capture_mean_ms": sum(c["ms"] for c in caps) / len(caps),
        "note": "Simulation unchanged; fewer Observer captures (display refresh reduced).",
    }
    (BENCH / "webui_render_reduced.json").write_text(
        json.dumps(webui_render_reduced, indent=2), encoding="utf-8"
    )

    # ---- C) Telemetry reduced: disable live GEO/SIGINT interpreters ----
    print("=== C) Telemetry-reduced (GEO/SIGINT off) ===")
    sess_t = make_session(ecology=ecology, agent_count=2)
    sess_t.set_live_interpreters(geometry=False, signal_context=False)
    scientific_only(sess_t, 100)
    tel_samples = scientific_only(sess_t, 300)
    webui_tel = {
        "label": "WEBUI_TELEMETRY_REDUCED",
        "geo_live": False,
        "sig_live": False,
        "tick_stats": window_stats(tel_samples),
        "vs_normal_mean_ms": {
            "normal": webui_normal["tick_stats_noninstrumented_200"]["mean_ms"],
            "reduced": window_stats(tel_samples)["mean_ms"],
        },
        "note": "Observer-only interpreters disabled; cognition/physics unchanged.",
    }
    (BENCH / "webui_telemetry_reduced.json").write_text(json.dumps(webui_tel, indent=2), encoding="utf-8")

    # ---- D) Headless control ----
    print("=== D) Headless CONTROL ===")
    headless = headless_control(ecology, 400)
    (BENCH / "headless_control.json").write_text(json.dumps(headless, indent=2), encoding="utf-8")

    # ---- Undercover comparison (optional) ----
    print("=== Undercover ON comparison ===")
    sess_u = make_session(ecology=ecology, agent_count=2, undercover=True)
    scientific_only(sess_u, 80)
    u_samples = scientific_only(sess_u, 200)
    undercover_bench = {
        "label": "WEBUI_WITH_UNDERCOVER",
        "config": _cfg_blob(sess_u),
        "bodies": len(getattr(sess_u.runtime, "slots", []) or []),
        "tick_stats": window_stats(u_samples),
        "vs_two_agent_mean_ms": webui_normal["tick_stats_noninstrumented_200"]["mean_ms"],
    }
    (BENCH / "webui_undercover.json").write_text(json.dumps(undercover_bench, indent=2), encoding="utf-8")

    # ---- UI Step path (full capture each tick) — shows Step-button cost ----
    print("=== UI Step path (full capture each tick) sample ===")
    sess_s = make_session(ecology=ecology, agent_count=2)
    scientific_only(sess_s, 50)
    step_samples = step_n(sess_s, 40)
    (BENCH / "webui_step_button.json").write_text(json.dumps({
        "label": "WEBUI_STEP_BUTTON",
        "ticks": 40,
        "tick_stats": window_stats(step_samples),
        "note": "ObserverSession.step(1) = scientific + FULL capture every call (UI Step).",
    }, indent=2), encoding="utf-8")

    # ---- NumPy micro-prototype ----
    print("=== NumPy micro-prototype ===")
    proto = numpy_grid_microproto()
    (PROTO / "grid_diffusion_microbench.json").write_text(json.dumps(proto, indent=2), encoding="utf-8")
    (PROTO / "README.md").write_text(
        "# NumPy micro-prototypes\n\nIsolated benchmarks only — not wired into production runtime.\n",
        encoding="utf-8",
    )

    # ---- Memory samples ----
    (RAW / "memory_samples.json").write_text(json.dumps({
        "start": mem_start,
        "after_profile": webui_normal["memory_end"],
        "growth_windows": [{"window": g["window"], "mem": g["memory_end"]} for g in growth],
    }, indent=2), encoding="utf-8")

    # ---- Telemetry profile from growth / captures ----
    tel_profile = {
        "events_note": "Structured event ring is bounded; scientific history appends per tick when writer open.",
        "compact_capture_mean_bytes": webui_normal["capture_compact_samples"]["mean_json_bytes"],
        "compact_capture_mean_ms": webui_normal["capture_compact_samples"]["mean_ms"],
        "growth_live_frame_bytes": [
            {"window": g["window"], "bytes": g["live_frame_bytes"], "build_ms": g["live_frame_build_ms"]}
            for g in growth
        ],
        "top_keys_last_window": growth[-1]["live_frame_top_keys"] if growth else [],
    }
    (RAW / "telemetry_samples.json").write_text(json.dumps(tel_profile, indent=2), encoding="utf-8")

    # ---- Frontend profile (backend-side of UI path; browser estimated) ----
    frontend = {
        "transport": "WebSocket /ws/live (latest-wins) + HTTP control",
        "display_refresh": "ui_hz-limited (default 10 Hz); NOT every simulation tick in Play",
        "capture_timings_available": True,
        "measured_compact_capture_ms": webui_normal["capture_compact_samples"]["mean_ms"],
        "measured_step_full_capture_ms": window_stats(step_samples)["mean_ms"],
        "browser_react_note": (
            "React/map redraw not instrumented in-process in this audit. "
            "Server already decouples sim tick from publish via ui_hz. "
            "If Play feels slow, wall time is dominated by scientific ticks "
            f"(~{plain_stats['mean_ms']:.1f} ms/tick), not 10 Hz capture."
        ),
        "frontend_profile_status": "BACKEND_MEASURED_BROWSER_INFERRED",
    }
    (RAW / "frontend_profile.json").write_text(json.dumps(frontend, indent=2), encoding="utf-8")

    summary = {
        "primary_path": "ObserverSession scientific tick + observer accumulators (Play body)",
        "config": cfg,
        "mean_ms_tick_noninstrumented": plain_stats["mean_ms"],
        "tps_noninstrumented": plain_stats["tps"],
        "headless_mean_ms": headless["tick_stats"]["mean_ms"],
        "headless_tps": headless["tick_stats"]["tps"],
        "overhead_webui_vs_headless_ms": (
            (plain_stats["mean_ms"] or 0) - (headless["tick_stats"]["mean_ms"] or 0)
        ),
        "step_button_mean_ms": window_stats(step_samples)["mean_ms"],
        "capture_compact_mean_ms": webui_normal["capture_compact_samples"]["mean_ms"],
        "profiler_overhead_pct_estimate": overhead_pct,
        "numpy_micro_speedup": proto["speedup"],
    }
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("DONE →", OUT)


if __name__ == "__main__":
    main()
