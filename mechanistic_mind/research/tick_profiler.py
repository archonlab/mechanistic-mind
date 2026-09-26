"""Opt-in aged-run tick profiler. Timing only — not scientific state.

Enable with PSY_TICK_PROFILE=1 or tick_profiler.enable(). Disabled path is a
single boolean check and must not consume RNG or change control flow.

Play-thread and capture-thread use thread-local stacks so concurrent Observer
capture cannot nest under simulation tick spans.
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

ENABLED = os.environ.get("PSY_TICK_PROFILE", "").strip() in {"1", "true", "TRUE", "yes"}

_NS = time.perf_counter_ns
_tls = threading.local()
_agg_lock = threading.Lock()
_inc_ns: dict[str, int] = {}
_child_ns: dict[str, int] = {}
_calls: dict[str, int] = {}
_counters: dict[str, int] = {}
_tick_ns: list[int] = []
_window_ticks: list[dict[str, Any]] = []
_slow_ticks: list[dict[str, Any]] = []
WINDOW = 100
SLOW_KEEP = 80
SLOW_MS = float(os.environ.get("PSY_TICK_PROFILE_SLOW_MS") or 400.0)


def enable() -> None:
    global ENABLED
    ENABLED = True


def disable() -> None:
    global ENABLED
    ENABLED = False


def reset() -> None:
    with _agg_lock:
        _inc_ns.clear()
        _child_ns.clear()
        _calls.clear()
        _counters.clear()
        _tick_ns.clear()
        _window_ticks.clear()
        _slow_ticks.clear()
    _tls.stack = []
    _tls.tick_start_ns = 0
    _tls.current_inc = {}
    _tls.current_calls = {}


def count(name: str, n: int = 1) -> None:
    if not ENABLED:
        return
    with _agg_lock:
        _counters[name] = _counters.get(name, 0) + int(n)


def _stack() -> list[tuple[str, int]]:
    s = getattr(_tls, "stack", None)
    if s is None:
        _tls.stack = []
        s = _tls.stack
    return s


@contextmanager
def span(name: str) -> Iterator[None]:
    if not ENABLED:
        yield
        return
    t0 = _NS()
    st = _stack()
    st.append((name, t0))
    try:
        yield
    finally:
        dt = _NS() - t0
        st.pop()
        cur_inc = getattr(_tls, "current_inc", None)
        cur_calls = getattr(_tls, "current_calls", None)
        if cur_inc is not None:
            cur_inc[name] = cur_inc.get(name, 0) + dt
        if cur_calls is not None:
            cur_calls[name] = cur_calls.get(name, 0) + 1
        parent = st[-1][0] if st else None
        with _agg_lock:
            _inc_ns[name] = _inc_ns.get(name, 0) + dt
            _calls[name] = _calls.get(name, 0) + 1
            if parent is not None:
                _child_ns[parent] = _child_ns.get(parent, 0) + dt


def begin_tick() -> None:
    if not ENABLED:
        return
    _tls.tick_start_ns = _NS()
    _tls.current_inc = {}
    _tls.current_calls = {}
    _tls.stack = []


def end_tick(sim_tick: int) -> dict[str, Any] | None:
    if not ENABLED:
        return None
    start = int(getattr(_tls, "tick_start_ns", 0) or 0)
    wall = _NS() - start if start else 0
    inc = dict(getattr(_tls, "current_inc", {}) or {})
    calls = dict(getattr(_tls, "current_calls", {}) or {})
    rec = {
        "tick": int(sim_tick),
        "wall_ns": wall,
        "inc": inc,
        "calls": calls,
    }
    wall_ms = wall / 1e6
    with _agg_lock:
        _tick_ns.append(wall)
        n = len(_tick_ns)
        if n % WINDOW == 0:
            _window_ticks.append(_summarize_recent(WINDOW))
        if wall_ms >= SLOW_MS:
            top = sorted(inc.items(), key=lambda kv: -kv[1])[:8]
            _slow_ticks.append({
                "tick": int(sim_tick),
                "total_ms": round(wall_ms, 3),
                "sim_ms": round(inc.get("sim", 0) / 1e6, 3),
                "sci_ms": round(inc.get("sci", 0) / 1e6, 3),
                "cognition_ms": round(inc.get("cognition", 0) / 1e6, 3),
                "observer_ms": round(
                    (inc.get("observer_request", 0) + inc.get("observer_frame", 0)) / 1e6,
                    3,
                ),
                "persistence_ms": round(inc.get("checkpoint", 0) / 1e6, 3),
                "largest": [
                    {"name": k, "inclusive_ms": round(v / 1e6, 3)} for k, v in top
                ],
            })
            if len(_slow_ticks) > SLOW_KEEP:
                del _slow_ticks[: len(_slow_ticks) - SLOW_KEEP]
    return rec


def slow_ticks() -> list[dict[str, Any]]:
    with _agg_lock:
        return list(_slow_ticks)


def _pctile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    ys = sorted(xs)
    i = min(len(ys) - 1, max(0, int(round((p / 100.0) * (len(ys) - 1)))))
    return float(ys[i])


def _bucket_row(name: str, ticks: int, inc: int, child: int, calls: int) -> dict[str, Any]:
    inc_f = float(inc)
    self_ns = max(0.0, inc_f - float(child))
    ticks = max(1, ticks)
    return {
        "name": name,
        "inclusive_ms": inc_f / 1e6,
        "self_ms": self_ns / 1e6,
        "calls": calls,
        "calls_per_tick": calls / ticks,
        "mean_ms_per_tick": (inc_f / 1e6) / ticks,
        "self_ms_per_tick": (self_ns / 1e6) / ticks,
        "mean_us_per_call": (inc_f / 1e3) / calls if calls else 0.0,
    }


def snapshot_stats(*, ticks: int | None = None) -> dict[str, Any]:
    with _agg_lock:
        n = int(ticks if ticks is not None else len(_tick_ns)) or 1
        walls_ms = [x / 1e6 for x in _tick_ns]
        names = sorted(set(_inc_ns) | set(_calls))
        buckets = [
            _bucket_row(
                k,
                n,
                int(_inc_ns.get(k, 0)),
                int(_child_ns.get(k, 0)),
                int(_calls.get(k, 0)),
            )
            for k in names
        ]
        wall_ms = sum(walls_ms)
        tick_inc = float(_inc_ns.get("tick", 0)) / 1e6
        tick_child = float(_child_ns.get("tick", 0)) / 1e6
        tick_self = max(0.0, tick_inc - tick_child)
        windows = list(_window_ticks)
        counters = dict(_counters)
    if tick_inc > 0:
        accounted_pct = 100.0 * tick_child / tick_inc
    elif wall_ms > 0:
        accounted_pct = 0.0
    else:
        accounted_pct = 0.0
    top_excl = {}
    for name in (
        "sim",
        "sci",
        "session_events",
        "checkpoint",
        "yield_capture",
        "observer_request",
        "throttle",
        "experimenter_pre",
        "experimenter_post",
    ):
        row = next((b for b in buckets if b["name"] == name), None)
        if row:
            top_excl[name] = row["mean_ms_per_tick"]
    return {
        "ticks": n,
        "mean_ms_per_tick": (sum(walls_ms) / n) if walls_ms else 0.0,
        "p50_ms_per_tick": _pctile(walls_ms, 50),
        "p95_ms_per_tick": _pctile(walls_ms, 95),
        "max_ms_per_tick": max(walls_ms) if walls_ms else 0.0,
        "accounted_wall_time_percent": round(accounted_pct, 2),
        "tick_inclusive_ms_per_tick": tick_inc / n if n else 0.0,
        "tick_unattributed_self_ms_per_tick": tick_self / n if n else 0.0,
        "top_level_exclusive_ms_per_tick": top_excl,
        "buckets": buckets,
        "counters": counters,
        "windows": windows,
    }


def _summarize_recent(k: int) -> dict[str, Any]:
    xs = _tick_ns[-k:]
    walls_ms = [x / 1e6 for x in xs]
    return {
        "n": len(xs),
        "mean_ms": (sum(walls_ms) / len(walls_ms)) if walls_ms else 0.0,
        "p50_ms": _pctile(walls_ms, 50),
        "p95_ms": _pctile(walls_ms, 95),
        "max_ms": max(walls_ms) if walls_ms else 0.0,
    }


def slope_ms(series: list[float]) -> float:
    """Endpoint trend: (last - first) / (n-1)."""
    if len(series) < 2:
        return 0.0
    return (float(series[-1]) - float(series[0])) / float(len(series) - 1)
