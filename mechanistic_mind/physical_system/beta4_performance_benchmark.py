"""Beta4 P0 performance benchmark telemetry — researcher-only, default OFF.

Schema: BETA4_PERFORMANCE_BENCHMARK_V1
Capability: beta4_performance_benchmark
Profile: COMPARABLE_SCIENTIFIC_SERVER_BROWSER_ANALYZER_TIMING_P0_V1
Authority: RESEARCHER_PERFORMANCE_TELEMETRY_NON_PHYSICAL

Must never enter cognition, physical fingerprints, or snapshots.
Disabled path is a boolean check only (no allocations in hot path beyond the check).
"""
from __future__ import annotations

import os
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

SCHEMA = "BETA4_PERFORMANCE_BENCHMARK_V1"
CAPABILITY = "beta4_performance_benchmark"
PROFILE = "COMPARABLE_SCIENTIFIC_SERVER_BROWSER_ANALYZER_TIMING_P0_V1"
AUTHORITY = "RESEARCHER_PERFORMANCE_TELEMETRY_NON_PHYSICAL"

ENABLED = os.environ.get("PSY_BETA4_PERF_BENCH", "").strip() in {"1", "true", "TRUE", "yes"}

_NS = time.perf_counter_ns
_tls = threading.local()
_lock = threading.Lock()

# Aggregates
_inc_ns: dict[str, int] = {}
_child_ns: dict[str, int] = {}
_calls: dict[str, int] = {}
_counters: dict[str, int] = {}
_samples: list[dict[str, Any]] = []
_meta: dict[str, Any] = {}
_MAX_RAW = 256  # bounded raw samples


def is_enabled() -> bool:
    return bool(ENABLED)


def enable(*, run_id: str | None = None, profile_id: str | None = None, **meta: Any) -> None:
    global ENABLED
    ENABLED = True
    with _lock:
        _meta.clear()
        _meta.update(meta)
        if run_id is not None:
            _meta["benchmark_run_id"] = str(run_id)
        if profile_id is not None:
            _meta["profile_id"] = str(profile_id)
        _meta["schema"] = SCHEMA
        _meta["capability"] = CAPABILITY
        _meta["profile"] = PROFILE
        _meta["authority"] = AUTHORITY


def disable() -> None:
    global ENABLED
    ENABLED = False


def reset() -> None:
    with _lock:
        _inc_ns.clear()
        _child_ns.clear()
        _calls.clear()
        _counters.clear()
        _samples.clear()
        _meta.clear()
    _tls.stack = []


def count(name: str, n: int = 1) -> None:
    if not ENABLED:
        return
    with _lock:
        _counters[name] = _counters.get(name, 0) + int(n)


def set_meta(**kwargs: Any) -> None:
    if not ENABLED:
        return
    with _lock:
        _meta.update(kwargs)


def _stack() -> list[tuple[str, int]]:
    s = getattr(_tls, "stack", None)
    if s is None:
        _tls.stack = []
        s = _tls.stack
    return s


@contextmanager
def span(name: str, *, parent: str | None = None, cache: str | None = None) -> Iterator[None]:
    """Hierarchical timing span. No-op when disabled."""
    if not ENABLED:
        yield
        return
    t0 = _NS()
    st = _stack()
    st.append((name, t0))
    err = None
    try:
        yield
    except Exception as e:
        err = e
        raise
    finally:
        dt = _NS() - t0
        st.pop()
        parent_name = parent
        if parent_name is None and st:
            parent_name = st[-1][0]
        with _lock:
            _inc_ns[name] = _inc_ns.get(name, 0) + dt
            _calls[name] = _calls.get(name, 0) + 1
            if parent_name is not None:
                _child_ns[parent_name] = _child_ns.get(parent_name, 0) + dt
            if len(_samples) < _MAX_RAW:
                _samples.append({
                    "stage": name,
                    "parent_stage": parent_name,
                    "duration_ns": int(dt),
                    "duration_ms": dt / 1e6,
                    "cache": cache,
                    "success": err is None,
                    "benchmark_run_id": _meta.get("benchmark_run_id"),
                    "profile_id": _meta.get("profile_id"),
                })


def snapshot() -> dict[str, Any]:
    with _lock:
        return {
            "schema": SCHEMA,
            "capability": CAPABILITY,
            "profile": PROFILE,
            "authority": AUTHORITY,
            "enabled": bool(ENABLED),
            "meta": dict(_meta),
            "inc_ms": {k: v / 1e6 for k, v in _inc_ns.items()},
            "calls": dict(_calls),
            "counters": dict(_counters),
            "child_ms": {k: v / 1e6 for k, v in _child_ns.items()},
            "raw_samples": list(_samples),
            "raw_sample_cap": _MAX_RAW,
        }


def stage_ms(name: str) -> float:
    with _lock:
        return float(_inc_ns.get(name, 0)) / 1e6


def calls_of(name: str) -> int:
    with _lock:
        return int(_calls.get(name, 0))


def percentiles_ms(name: str) -> dict[str, float]:
    with _lock:
        xs = [float(s["duration_ms"]) for s in _samples if s.get("stage") == name]
    if not xs:
        with _lock:
            total = float(_inc_ns.get(name, 0)) / 1e6
            n = max(1, int(_calls.get(name, 0)))
            mean = total / n if _calls.get(name) else 0.0
        return {"p50": mean, "p95": mean, "p99": mean, "min": mean, "max": mean, "n": 0}
    ys = sorted(xs)

    def pct(p: float) -> float:
        i = min(len(ys) - 1, max(0, int(round((p / 100.0) * (len(ys) - 1)))))
        return float(ys[i])

    return {
        "p50": pct(50),
        "p95": pct(95),
        "p99": pct(99),
        "min": float(ys[0]),
        "max": float(ys[-1]),
        "n": len(ys),
    }


# ---------------------------------------------------------------------------
# Canonical fingerprint (authoritative scientific state; excludes telemetry)
# ---------------------------------------------------------------------------


def canonical_tick_fingerprint(runtime: Any) -> dict[str, Any]:
    """Researcher fingerprint for OFF/ON identity. Not cognition-visible."""
    import hashlib
    import json
    import math

    body = runtime.body
    world = runtime.world
    cfg = runtime.config

    def _f(x: Any) -> float | None:
        try:
            v = float(x)
            return v if math.isfinite(v) else None
        except Exception:
            return None

    ro_rows = []
    for obj in list(getattr(world, "resource_objects", None) or []):
        ro_rows.append({
            "id": str(getattr(obj, "object_id", None)),
            "x": _f(getattr(obj, "x", None)),
            "y": _f(getattr(obj, "y", None)),
            "z": _f(getattr(obj, "z", None)),
            "mass": _f(getattr(obj, "mass", None)),
            "quantity": _f(getattr(obj, "quantity", None)),
            "state": str(getattr(obj, "physical_state", None)),
        })
    ro_rows.sort(key=lambda r: r["id"] or "")

    vw1 = None
    try:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

        st = state_of(world)
        if st is not None:
            vw1 = {"digest": str(st.digest()), "revision": getattr(st, "revision", None)}
    except Exception:
        vw1 = None

    obs = getattr(runtime, "last_agent_observation", None) or {}
    exo = {k: _f(obs[k]) for k in sorted(obs) if str(k).startswith("exo_")}
    osc = {k: _f(obs[k]) for k in sorted(obs) if str(k).startswith("osc_")}
    surf = {k: _f(obs[k]) for k in sorted(obs) if str(k).startswith("surface_c")}

    o4 = getattr(world, "_o4_last_reception_trace", None) or {}
    o4_compact = {
        "reached": bool(o4.get("physical_signal_reached_receptor")) if o4 else None,
        "accepted": o4.get("accepted"),
        "rejected": o4.get("rejected"),
    }

    lps = None
    try:
        from mechanistic_mind.physical_system.local_physical_signal_transport import state_of as lps_state

        st = lps_state(world)
        if st is not None:
            hist = list(getattr(st, "reception_history", None) or [])
            lps = {
                "last_processed_tick": getattr(st, "last_processed_tick", None),
                "reception_n": len(hist),
                "last_reception": (
                    {
                        "propagation_delay": hist[-1].get("propagation_delay"),
                        "arrival_tick": hist[-1].get("arrival_tick"),
                        "emission_tick": hist[-1].get("emission_tick"),
                    }
                    if hist
                    else None
                ),
            }
    except Exception:
        lps = None

    motor = getattr(runtime, "last_motor_output", None) or {}
    payload = {
        "tick": int(getattr(runtime, "tick", 0) or 0),
        "action": str(getattr(runtime, "last_selected_action", "") or ""),
        "motor": {
            "locomotion": motor.get("locomotion"),
            "effector_z_left": motor.get("effector_z_left"),
            "effector_z_right": motor.get("effector_z_right"),
            "manipulator": motor.get("manipulator"),
        },
        "body": {
            "x": _f(body.x),
            "y": _f(body.y),
            "z": _f(getattr(body, "z", 0.0)),
            "vx": _f(body.vx),
            "vy": _f(body.vy),
            "vz": _f(getattr(body, "vz", 0.0)),
            "grounded": bool(getattr(body, "grounded", False)),
            "theta": _f(getattr(body, "theta", 0.0)),
        },
        "resource_objects": ro_rows,
        "vw1": vw1,
        "exo": exo,
        "osc": osc,
        "surface_c": surf,
        "o4": o4_compact,
        "lps": lps,
        "public_preset": str(getattr(cfg, "public_preset", "") or ""),
        "model_line": str(getattr(cfg, "model_line", "") or ""),
    }
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return {
        "sha256": hashlib.sha256(blob).hexdigest(),
        "payload": payload,
    }


def fingerprints_equal(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return str(a.get("sha256")) == str(b.get("sha256"))
