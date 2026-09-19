#!/usr/bin/env python3
"""Post-Optimization Pass 1 profile — decide Beta freeze vs small Pass 2.

Observational only. Does not retune mechanisms or introduce NumPy/Numba.
"""
from __future__ import annotations

import json
import resource
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.research.webui_perf_profile import (  # noqa: E402
    StageTimer,
    install_runtime_stage_timers,
    install_session_stage_timers,
    percentile,
    run_cprofile,
    window_stats,
    wrap_method,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig  # noqa: E402

OUT = Path("results/performance/post_opt_profile")
RAW = OUT / "raw"
BENCH = OUT / "benchmarks"
for d in (OUT, RAW, BENCH):
    d.mkdir(parents=True, exist_ok=True)

SEED = 17
ECOLOGY = "STRUCTURED_TERRAIN_EXPERIMENTAL"
WARMUP = 150
PROFILE = 400
WINDOWS = [(150, 250), (250, 350), (350, 450), (450, 550)]
MECHS = {
    "cognition_enabled": True,
    "experimental_physical_signal": True,
    "physical_near_field_vision": True,
    "illumination_cycle": True,
    "physical_body_optical_response": True,
}


def rss_mb() -> float:
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def make_session() -> ObserverSession:
    sess = ObserverSession(config=SessionConfig(seed=SEED, ui_hz=10.0, buffer_capacity=256))
    sess.apply_experiment({
        "seed": SEED,
        "ecology_preset": ECOLOGY,
        "agent_count": 2,
        "cognition_enabled": True,
        "mechanisms": dict(MECHS),
    })
    for mid, val in MECHS.items():
        if mid == "cognition_enabled":
            continue
        try:
            sess.set_mechanism(str(mid), bool(val))
        except Exception:
            pass
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
        samples.append((time.perf_counter() - t0) * 1000.0)
    return samples


def capture_compact(sess: ObserverSession) -> tuple[float, int]:
    t0 = time.perf_counter()
    with sess._step_lock:
        with sess._lock:
            frame = sess._capture_locked(detail="compact")
            payload = json.dumps(frame, default=str)
    return (time.perf_counter() - t0) * 1000.0, len(payload.encode("utf-8"))


def install_psc_timers(timer: StageTimer) -> list:
    """Wrap PSC/prospection/cognition module functions (restored after)."""
    restores = []
    import mechanistic_mind.physical_system.cognition as cog
    import mechanistic_mind.research.prospective_composition as pr
    import mechanistic_mind.physical_system.scenario_competition as sc
    import mechanistic_mind.research.predictive_compression as pc
    import mechanistic_mind.physical_system.diagnostics as diag
    import mechanistic_mind.integrated.causal_trace as ct
    import mechanistic_mind.physical_system.body_orientation as bo
    import mechanistic_mind.planet.dynamics as planet
    import mechanistic_mind.physical_system.near_field_exteroception as nfe
    import mechanistic_mind.physical_system.complementary_resources as cr

    pairs = [
        (cog, "run_cognition_before_action", "A.cognition_before_action"),
        (pr, "compose_trajectories", "C.compose_trajectories"),
        (pr, "predict_one_step", "B.predict_one_step"),
        (pr, "learn_transition", "C.learn_transition"),
        (pr, "_q", "C.quantize_fragment"),
        (pr, "transition_key", "C.transition_key"),
        (sc, "collect_scenario_groups", "D.collect_scenario_groups"),
        (sc, "compete_scenarios", "D.compete_scenarios"),
        (sc, "continuation_to_scenario", "D.continuation_to_scenario"),
        (sc, "one_step_scenario", "D.one_step_scenario"),
        (pc, "predict", "B.compression_predict"),
        (diag, "build_action_decision_receipt", "F.build_decision_receipt"),
        (diag, "counterfactual_candidate_probe", "F.counterfactual_probe"),
        (ct, "event", "F.causal_event"),
        (ct, "edge", "F.causal_edge"),
        (ct, "_trim", "F.causal_trim"),
        (bo, "step_orientation_mechanics", "G.orientation"),
        (planet, "step_planet", "I.step_planet"),
        (nfe, "sample_near_field", "M.sample_near_field"),
        (cr, "simultaneous_complementary_resources", "J.resources"),
    ]
    for mod, name, stage in pairs:
        if hasattr(mod, name):
            restores.append(wrap_method(mod, name, timer, stage))
    return restores


def store_sizes(sess: ObserverSession) -> dict:
    out = []
    for i, slot in enumerate(sess.runtime.slots):
        cog = slot.cognition or {}
        prosp = cog.get("prospection") or {}
        trans = prosp.get("transitions") or {}
        comp = cog.get("compression") or {}
        store = comp.get("store") or comp.get("entries") or {}
        trace = cog.get("trace") or {}
        metrics = cog.get("metrics") or {}
        out.append({
            "slot": i,
            "transitions": len(trans) if isinstance(trans, dict) else None,
            "compression_entries": len(store) if isinstance(store, dict) else None,
            "trace_events": len(trace.get("events") or []),
            "trace_edges": len(trace.get("edges") or []),
            "prospective_compositions": metrics.get("prospective_compositions"),
            "prediction_count": metrics.get("prediction_count"),
        })
    return {"agents": out}


def headless_control(n: int) -> dict:
    from mechanistic_mind.physical_system.ecology_presets import make_ecology_config
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    cfg = make_ecology_config(ECOLOGY)
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
    for _ in range(80):
        rt.step(1)
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        rt.step(1)
        samples.append((time.perf_counter() - t0) * 1000.0)
    return {"label": "HEADLESS_CONTROL", "tick_stats": window_stats(samples)}


def main() -> None:
    tracemalloc.start()
    print("=== config ===")
    sess = make_session()
    cfg = {
        "seed": SEED,
        "ecology": ECOLOGY,
        "runtime": type(sess.runtime).__name__,
        "agents": len(sess.runtime.slots),
        "mechanisms": MECHS,
        "note": "Post Opt Pass 1 profile — observational only",
    }
    (RAW / "config.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    print(json.dumps(cfg))

    mem0 = {"rss_mb": rss_mb(), "tracemalloc_mb": tracemalloc.get_traced_memory()[0] / (1024 * 1024)}

    print(f"warmup {WARMUP}...")
    warm = scientific_only(sess, WARMUP)
    (RAW / "warmup.json").write_text(json.dumps(window_stats(warm), indent=2), encoding="utf-8")

    # Instrumented profile
    timer = StageTimer()
    restores = []
    restores.append(install_runtime_stage_timers(sess.runtime, timer))
    restores.append(install_session_stage_timers(sess, timer))
    restores.extend(install_psc_timers(timer))

    print(f"profile {PROFILE} instrumented...")
    t0 = time.perf_counter()
    prof_samples = []
    for _ in range(PROFILE):
        t1 = time.perf_counter()
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()
        dt = time.perf_counter() - t1
        timer.record_tick(dt)
        prof_samples.append(dt * 1000.0)
    wall_instr = time.perf_counter() - t0
    stage_sum = timer.summary()
    stores_after_prof = store_sizes(sess)

    for r in restores:
        r()

    # Non-instrumented sample
    plain = scientific_only(sess, 200)
    plain_stats = window_stats(plain)
    instr_mean = window_stats(prof_samples)["mean_ms"] or 1.0
    overhead_pct = 100.0 * (instr_mean - (plain_stats["mean_ms"] or instr_mean)) / instr_mean

    # Captures
    caps = [capture_compact(sess) for _ in range(15)]
    cap_ms = [c[0] for c in caps]
    cap_bytes = [c[1] for c in caps]

    webui = {
        "label": "WEBUI_POST_OPT1",
        "config": cfg,
        "warmup": WARMUP,
        "profiled": PROFILE,
        "wall_instrumented_s": wall_instr,
        "tick_stats_instrumented": window_stats(prof_samples),
        "tick_stats_noninstrumented_200": plain_stats,
        "profiler_overhead_pct": overhead_pct,
        "stages": stage_sum,
        "store_sizes": stores_after_prof,
        "capture_compact": {
            "mean_ms": statistics.mean(cap_ms),
            "p95_ms": percentile(cap_ms, 95),
            "mean_bytes": statistics.mean(cap_bytes),
        },
        "memory_start": mem0,
        "memory_end": {
            "rss_mb": rss_mb(),
            "tracemalloc_mb": tracemalloc.get_traced_memory()[0] / (1024 * 1024),
        },
    }
    (BENCH / "webui.json").write_text(json.dumps(webui, indent=2), encoding="utf-8")
    (RAW / "timing_samples.json").write_text(json.dumps({
        "instrumented_ms": prof_samples,
        "noninstrumented_ms": plain,
    }, indent=2), encoding="utf-8")

    # cProfile
    print("cProfile 300 ticks...")
    def _cp():
        scientific_only(sess, 300)

    cprof = run_cprofile(_cp, limit=60)
    (RAW / "python_profile.txt").write_text(cprof["text"], encoding="utf-8")
    (RAW / "python_profile.json").write_text(json.dumps(cprof["top"], indent=2), encoding="utf-8")

    # Growth windows on fresh session
    print("growth windows...")
    sess_g = make_session()
    growth = []
    # advance to first window
    while int(sess_g.runtime.tick) < WINDOWS[0][0]:
        scientific_only(sess_g, 1)
    for a, b in WINDOWS:
        while int(sess_g.runtime.tick) < a:
            scientific_only(sess_g, 1)
        stores0 = store_sizes(sess_g)
        samples = scientific_only(sess_g, b - a)
        growth.append({
            "window": [a, b],
            "tick_stats": window_stats(samples),
            "stores_start": stores0,
            "stores_end": store_sizes(sess_g),
            "rss_mb": rss_mb(),
        })
    (RAW / "timing_windows.json").write_text(json.dumps(growth, indent=2), encoding="utf-8")

    # Headless control
    print("headless...")
    headless = headless_control(400)
    (BENCH / "headless.json").write_text(json.dumps(headless, indent=2), encoding="utf-8")

    # Call counts from stage timer
    call_counts = {
        s["stage"]: {"calls": s["calls"], "mean_ms": s["mean_ms"], "total_s": s["total_s"]}
        for s in stage_sum["stages"]
    }
    (RAW / "call_counts.json").write_text(json.dumps(call_counts, indent=2), encoding="utf-8")

    summary = {
        "webui_mean_ms": plain_stats["mean_ms"],
        "webui_tps": plain_stats["tps"],
        "webui_p95_ms": plain_stats["p95_ms"],
        "headless_mean_ms": headless["tick_stats"]["mean_ms"],
        "delta_webui_minus_headless_ms": (
            (plain_stats["mean_ms"] or 0) - (headless["tick_stats"]["mean_ms"] or 0)
        ),
        "capture_mean_ms": statistics.mean(cap_ms),
        "profiler_overhead_pct": overhead_pct,
        "top_stages": stage_sum["stages"][:15],
        "growth_means_ms": [g["tick_stats"]["mean_ms"] for g in growth],
    }
    (OUT / "run_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("DONE", OUT)


if __name__ == "__main__":
    main()
