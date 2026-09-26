"""Observational Web-UI performance profiling for Mechanistic Mind / Tiktaalik.

Opt-in only. Does not alter scientific equations, RNG, or default configs.
Used by experiments/run_webui_performance_profile.py.
"""
from __future__ import annotations

import cProfile
import json
import pstats
import resource
import statistics
import time
import tracemalloc
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Callable


def percentile(xs: list[float], p: float) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    if len(s) == 1:
        return float(s[0])
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return float(s[f])
    return float(s[f] + (s[c] - s[f]) * (k - f))


def rss_mb() -> float:
    # Linux: ru_maxrss is kilobytes
    return float(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) / 1024.0


@dataclass
class StageTimer:
    """Accumulates wall time for named stages (observational only)."""

    totals: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    tick_samples: list[float] = field(default_factory=list)
    enabled: bool = True

    @contextmanager
    def stage(self, name: str):
        if not self.enabled:
            yield
            return
        t0 = time.perf_counter()
        try:
            yield
        finally:
            dt = time.perf_counter() - t0
            self.totals[name] += dt
            self.counts[name] += 1

    def record_tick(self, dt: float) -> None:
        self.tick_samples.append(float(dt))

    def summary(self) -> dict[str, Any]:
        wall = sum(self.totals.values()) or 1e-12
        stages = []
        for name, tot in sorted(self.totals.items(), key=lambda kv: -kv[1]):
            n = max(1, self.counts[name])
            stages.append({
                "stage": name,
                "total_s": tot,
                "calls": self.counts[name],
                "mean_ms": 1000.0 * tot / n,
                "pct_of_staged": 100.0 * tot / wall,
            })
        samples = self.tick_samples
        return {
            "stages": stages,
            "tick_ms": {
                "n": len(samples),
                "mean": statistics.mean(samples) * 1000 if samples else None,
                "median": statistics.median(samples) * 1000 if samples else None,
                "p50": percentile([x * 1000 for x in samples], 50),
                "p90": percentile([x * 1000 for x in samples], 90),
                "p95": percentile([x * 1000 for x in samples], 95),
                "p99": percentile([x * 1000 for x in samples], 99) if len(samples) >= 20 else None,
                "tps": (len(samples) / sum(samples)) if samples and sum(samples) > 0 else None,
            },
        }


def wrap_method(obj: Any, name: str, timer: StageTimer, stage: str) -> Callable[[], None]:
    """Temporarily wrap an instance method; returns restore callable."""
    orig = getattr(obj, name)

    def wrapped(*args, **kwargs):
        with timer.stage(stage):
            return orig(*args, **kwargs)

    setattr(obj, name, wrapped)

    def restore() -> None:
        setattr(obj, name, orig)

    return restore


def install_runtime_stage_timers(runtime: Any, timer: StageTimer) -> Callable[[], None]:
    """Wrap known runtime methods for stage attribution (no semantic change)."""
    restores: list[Callable[[], None]] = []
    slots = getattr(runtime, "slots", None) or [runtime]

    # TwoAgent orchestration
    if hasattr(runtime, "_step_once"):
        restores.append(wrap_method(runtime, "_step_once", timer, "ta._step_once_TOTAL"))
    if hasattr(runtime, "observations"):
        restores.append(wrap_method(runtime, "observations", timer, "ta.observations"))

    # Per-slot begin/finish (cognition + body physics)
    for i, slot in enumerate(slots):
        if hasattr(slot, "begin_tick"):
            restores.append(wrap_method(slot, "begin_tick", timer, f"slot[{i}].begin_tick"))
        if hasattr(slot, "finish_tick"):
            restores.append(wrap_method(slot, "finish_tick", timer, f"slot[{i}].finish_tick"))

    # Module-level planet / contact / signal if bound as methods on runtime
    # Prefer wrapping imported call sites via runtime helpers when present.
    def restore_all() -> None:
        for r in restores:
            r()

    return restore_all


def install_session_stage_timers(sess: Any, timer: StageTimer) -> Callable[[], None]:
    restores: list[Callable[[], None]] = []
    for method, stage in (
        ("_scientific_step_once_unlocked", "sess.scientific_step"),
        ("_accumulate_events_locked", "sess.accumulate_events"),
        ("_record_motion_locked", "sess.record_motion"),
        ("_append_scientific_locked", "sess.append_scientific"),
        ("_capture_locked", "sess.capture_locked"),
        ("_observe_action_realization_locked", "sess.action_realization"),
        ("_observe_work_ecology_locked", "sess.work_ecology"),
        ("_observe_locomotor_economy_locked", "sess.locomotor_economy"),
        ("_observe_geometry_tick_locked", "sess.geometry_observe"),
    ):
        if hasattr(sess, method):
            restores.append(wrap_method(sess, method, timer, stage))

    def restore_all() -> None:
        for r in restores:
            r()

    return restore_all


def cognition_store_sizes(runtime: Any) -> dict[str, Any]:
    """Observer-facing store size diagnostics (not cognition input)."""
    out: list[dict[str, Any]] = []
    slots = getattr(runtime, "slots", None) or [runtime]
    for i, slot in enumerate(slots):
        cog = getattr(slot, "cognition", None) or {}
        if not isinstance(cog, dict):
            out.append({"slot": i, "cognition": False})
            continue
        metrics = cog.get("metrics") or {}
        compression = cog.get("compression") or {}
        prospection = cog.get("prospection") or {}
        store = compression.get("store") or compression.get("entries") or {}
        n_comp = len(store) if isinstance(store, dict) else (
            len(store) if isinstance(store, (list, tuple)) else None
        )
        prosp_store = prospection.get("store") or prospection.get("compositions") or {}
        n_prosp = len(prosp_store) if isinstance(prosp_store, dict) else (
            len(prosp_store) if isinstance(prosp_store, (list, tuple)) else None
        )
        out.append({
            "slot": i,
            "prediction_count": metrics.get("prediction_count"),
            "prospective_compositions": metrics.get("prospective_compositions"),
            "compression_entries": n_comp,
            "prospection_entries": n_prosp,
            "action_counts": dict(metrics.get("action_counts") or {}),
        })
    return {"agents": out}


def frame_byte_stats(frame: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(frame, default=str)
    return {
        "json_bytes": len(raw.encode("utf-8")),
        "top_keys": sorted(
            ((k, len(json.dumps(v, default=str).encode("utf-8"))) for k, v in frame.items()),
            key=lambda kv: -kv[1],
        )[:12],
    }


def run_cprofile(fn: Callable[[], Any], sort: str = "cumulative", limit: int = 40) -> dict[str, Any]:
    pr = cProfile.Profile()
    pr.enable()
    fn()
    pr.disable()
    buf = StringIO()
    stats = pstats.Stats(pr, stream=buf).sort_stats(sort)
    stats.print_stats(limit)
    # Structured top rows
    rows = []
    for (filename, line, func), (cc, nc, tt, ct, callers) in sorted(
        stats.stats.items(), key=lambda item: -item[1][3]
    )[:limit]:
        rows.append({
            "file": filename,
            "line": line,
            "func": func,
            "ncalls": nc,
            "tottime": tt,
            "cumtime": ct,
        })
    return {"text": buf.getvalue(), "top": rows}


def window_stats(samples_ms: list[float]) -> dict[str, Any]:
    if not samples_ms:
        return {"n": 0}
    return {
        "n": len(samples_ms),
        "mean_ms": statistics.mean(samples_ms),
        "median_ms": statistics.median(samples_ms),
        "p50_ms": percentile(samples_ms, 50),
        "p90_ms": percentile(samples_ms, 90),
        "p95_ms": percentile(samples_ms, 95),
        "p99_ms": percentile(samples_ms, 99) if len(samples_ms) >= 20 else None,
        "tps": 1000.0 / statistics.mean(samples_ms) if statistics.mean(samples_ms) > 0 else None,
        "total_s": sum(samples_ms) / 1000.0,
    }


def memory_snapshot(label: str) -> dict[str, Any]:
    cur, peak = tracemalloc.get_traced_memory() if tracemalloc.is_tracing() else (0, 0)
    return {
        "label": label,
        "rss_mb": rss_mb(),
        "tracemalloc_current_mb": cur / (1024 * 1024),
        "tracemalloc_peak_mb": peak / (1024 * 1024),
    }
