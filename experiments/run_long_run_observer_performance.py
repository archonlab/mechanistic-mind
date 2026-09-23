#!/usr/bin/env python3
"""Long-run Observer performance: early vs mature windows + root-cause attribution.

MEASURE FIRST. Does not change scientific equations.
Writes results/long_run_observer_performance/*.
"""
from __future__ import annotations

import json
import resource
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime  # noqa: E402
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig  # noqa: E402

OUT = Path("results/long_run_observer_performance")
OUT.mkdir(parents=True, exist_ok=True)


def rss_mb() -> float:
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


def pct(xs: list[float], p: float) -> float:
    s = sorted(xs)
    if not s:
        return float("nan")
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def window_stats(samples: list[float]) -> dict:
    if not samples:
        return {}
    return {
        "n": len(samples),
        "mean_ms": statistics.mean(samples) * 1000,
        "p50_ms": pct(samples, 50) * 1000,
        "p95_ms": pct(samples, 95) * 1000,
        "p99_ms": pct(samples, 99) * 1000 if len(samples) >= 20 else None,
        "tps": len(samples) / sum(samples),
        "rss_mb": rss_mb(),
    }


def measure_bare(to_tick: int, window: int = 100) -> dict:
    rt = PhysicalSystemRuntime(seed=17)
    while rt.tick < max(0, to_tick - window):
        rt.step(1)
    samples = []
    for _ in range(window):
        t0 = time.perf_counter()
        rt.step(1)
        samples.append(time.perf_counter() - t0)
    return {"mode": "BARE_RUNTIME", "tick_end": rt.tick, **window_stats(samples)}


def measure_session(to_tick: int, window: int = 100, *, agents: int = 1) -> dict:
    sess = ObserverSession(SessionConfig(seed=17, execution_mode="HEADLESS", cognition_enabled=True))
    sess.apply_experiment({
        "seed": 17,
        "agent_count": agents,
        "cognition_enabled": True,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": {
            "physical_near_field_vision": True,
            "spatiotemporal_climate_ecology": False,
        },
    })
    sess.set_execution_mode("HEADLESS")
    sess._active_run_id = "bench-long-run"
    sess._run_started_at = "bench"
    with sess._lock:
        sess._ensure_scientific_locked()
    while sess.runtime.tick < max(0, to_tick - window):
        with sess._step_lock:
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()
    samples = []
    with sess._step_lock:
        for _ in range(window):
            t0 = time.perf_counter()
            sess._scientific_step_once_unlocked()
            with sess._lock:
                sess._accumulate_events_locked()
                sess._record_motion_locked()
                sess._append_scientific_locked()
            samples.append(time.perf_counter() - t0)
    return {
        "mode": "HEADLESS_SESSION+SCI",
        "agents": agents,
        "tick_end": int(sess.runtime.tick),
        **window_stats(samples),
    }


def main() -> None:
    rows = []
    for target in (200, 1000, 5000):
        rows.append(measure_bare(target))
        rows.append(measure_session(target, agents=1))
        print("done", target, flush=True)
    # Two-agent short + 1k
    rows.append(measure_session(200, agents=2))
    rows.append(measure_session(1000, agents=2))

    bare = {r["tick_end"]: r for r in rows if r["mode"] == "BARE_RUNTIME"}
    early = bare.get(200) or bare.get(min(bare))
    late = bare.get(max(bare))
    ratio = (late["p50_ms"] / early["p50_ms"]) if early and late else None
    report = {
        "rows": rows,
        "bare_early_to_late_p50_slowdown": ratio,
        "notes": [
            "Bare runtime should approximately plateau after cognition stores saturate.",
            "Severe Observer STALE/PENDING is infrastructure (step_lock / packs I/O), not bare science.",
        ],
    }
    (OUT / "windows.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
