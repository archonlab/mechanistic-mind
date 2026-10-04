"""P4 Observer serialization fragment cache — derived researcher delivery only.

Schema: OBSERVER_SERIALIZATION_FRAGMENT_CACHE_V1
Capability: global_observer_serialization_cache
Profile: GENERATION_AND_TICK_SCOPED_CANONICAL_FRAME_FRAGMENT_CACHE_P4_V1
Authority: DERIVED_RESEARCHER_SERIALIZATION_NO_PHYSICAL_EFFECT

Stores deep-copied structured fragments only. Never simulation/snapshot/evidence authority.
Instrumentation/telemetry exposure is default OFF (counters always tracked cheaply).
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import threading
import time
from collections import OrderedDict
from typing import Any, Callable

SCHEMA = "OBSERVER_SERIALIZATION_FRAGMENT_CACHE_V1"
CAPABILITY = "global_observer_serialization_cache"
PROFILE = "GENERATION_AND_TICK_SCOPED_CANONICAL_FRAME_FRAGMENT_CACHE_P4_V1"
AUTHORITY = "DERIVED_RESEARCHER_SERIALIZATION_NO_PHYSICAL_EFFECT"

# Representation: pickled structured fragments; unpickle yields an independent object graph
# (avoids deepcopy cost on large WORLD/MECHANISM fragments while preventing aliasing).
REPRESENTATION = "PICKLED_STRUCTURED_FRAGMENT_INDEPENDENT_CLONE_V1"

FAMILY_MECHANISM_SNAPSHOT = "MECHANISM_SNAPSHOT"
FAMILY_EXPERIMENT_CONFIG = "EXPERIMENT_CONFIG"
FAMILY_HONESTY = "HONESTY"
FAMILY_BETA4_CAPABILITY = "BETA4_CAPABILITY"
FAMILY_WORLD_FRAME = "WORLD_FRAME"
FAMILY_MODEL_BANNER_MECH = "MODEL_BANNER_MECHANISMS"

STABLE_FAMILIES = frozenset({
    FAMILY_MECHANISM_SNAPSHOT,
    FAMILY_EXPERIMENT_CONFIG,
    FAMILY_HONESTY,
    FAMILY_BETA4_CAPABILITY,
    FAMILY_MODEL_BANNER_MECH,
})
DYNAMIC_FAMILIES = frozenset({
    FAMILY_WORLD_FRAME,  # tick-scoped; reuse only for identical tick authority
})

# Bounded memory policy
DEFAULT_MAX_ENTRIES = 64
DEFAULT_MAX_BYTES = 24 * 1024 * 1024  # 24 MiB structured estimate
_ENV_ENABLE = "PSY_OBSERVER_SERIALIZATION_CACHE"
_ENV_TELEM = "PSY_OBSERVER_SERIALIZATION_CACHE_TELEM"

_lock = threading.RLock()
_enabled: bool | None = None  # None → resolve from env (default ON)
_telem_enabled: bool | None = None
_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_bytes_est = 0
_counters: dict[str, Any] = {
    "hits": 0,
    "misses": 0,
    "builds": 0,
    "evictions": 0,
    "invalidations": 0,
    "stale_prevented": 0,
    "alias_guards": 0,
    "bytes_reused": 0,
    "bytes_built": 0,
    "build_ms_total": 0.0,
    "invalidation_reasons": {},
}


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or str(raw).strip() == "":
        return default
    return str(raw).strip().lower() in ("1", "true", "yes", "on")


def is_enabled() -> bool:
    global _enabled
    if _enabled is None:
        _enabled = _env_bool(_ENV_ENABLE, True)
    return bool(_enabled)


def set_enabled(flag: bool) -> None:
    global _enabled
    _enabled = bool(flag)


def telemetry_enabled() -> bool:
    global _telem_enabled
    if _telem_enabled is None:
        _telem_enabled = _env_bool(_ENV_TELEM, False)
    return bool(_telem_enabled)


def set_telemetry_enabled(flag: bool) -> None:
    global _telem_enabled
    _telem_enabled = bool(flag)


def authority_digest(parts: dict[str, Any]) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def make_cache_key(*, family: str, authority_key: dict[str, Any]) -> str:
    return f"{family}|{authority_digest(authority_key)}"


def _estimate_bytes(value: Any) -> int:
    try:
        return len(json.dumps(value, default=str, separators=(",", ":")).encode())
    except Exception:
        return 256


def _bump_reason(reason: str) -> None:
    reasons = _counters["invalidation_reasons"]
    if not isinstance(reasons, dict):
        reasons = {}
        _counters["invalidation_reasons"] = reasons
    reasons[reason] = int(reasons.get(reason, 0)) + 1


def _evict_one_locked() -> None:
    if not _cache:
        return
    _key, entry = _cache.popitem(last=False)
    global _bytes_est
    _bytes_est = max(0, int(_bytes_est) - int(entry.get("encoded_size") or 0))
    _counters["evictions"] = int(_counters["evictions"]) + 1


def _fit_locked(extra: int) -> None:
    global _bytes_est
    while _cache and (
        len(_cache) >= DEFAULT_MAX_ENTRIES or int(_bytes_est) + int(extra) > DEFAULT_MAX_BYTES
    ):
        _evict_one_locked()


def has_entry(*, family: str, authority_key: dict[str, Any]) -> bool:
    key = make_cache_key(family=family, authority_key=authority_key)
    with _lock:
        return key in _cache


def clear(*, reason: str = "CLEAR") -> None:
    with _lock:
        _cache.clear()
        global _bytes_est
        _bytes_est = 0
        _counters["invalidations"] = int(_counters["invalidations"]) + 1
        _bump_reason(reason)


def invalidate_generation(*, run_id: str | None = None, runtime_generation: int | None = None, reason: str = "RUNTIME_GENERATION") -> None:
    """Drop incompatible entries. Correctness priority: clear run-scoped or all."""
    with _lock:
        global _bytes_est
        if run_id is None:
            _cache.clear()
            _bytes_est = 0
            _counters["invalidations"] = int(_counters["invalidations"]) + 1
            _bump_reason(reason)
            return
        drop = [
            k
            for k, e in _cache.items()
            if str((e.get("authority_key") or {}).get("run_id") or "") in ("", str(run_id))
            or int((e.get("authority_key") or {}).get("runtime_generation") or -1) == int(runtime_generation or -2)
        ]
        for k in drop:
            entry = _cache.pop(k, None)
            if entry:
                _bytes_est = max(0, int(_bytes_est) - int(entry.get("encoded_size") or 0))
        if drop:
            _counters["invalidations"] = int(_counters["invalidations"]) + 1
            _bump_reason(reason)


def invalidate_run(run_id: str, *, reason: str = "RUN") -> None:
    with _lock:
        drop = [k for k, e in _cache.items() if str((e.get("authority_key") or {}).get("run_id") or "") == str(run_id)]
        global _bytes_est
        for k in drop:
            entry = _cache.pop(k, None)
            if entry:
                _bytes_est = max(0, int(_bytes_est) - int(entry.get("encoded_size") or 0))
        if drop:
            _counters["invalidations"] = int(_counters["invalidations"]) + 1
            _bump_reason(reason)


def get_or_build(
    *,
    family: str,
    authority_key: dict[str, Any],
    builder: Callable[[], Any],
    schema_version: str = "1",
) -> Any:
    """Return an independent clone of a cached fragment, or build/store one.

    Storage uses pickle bytes so get() does not alias live/cached object graphs
    and remains cheaper than deepcopy for large fragments.
    """
    if not is_enabled():
        return builder()

    key = make_cache_key(family=family, authority_key=authority_key)
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            _counters["hits"] = int(_counters["hits"]) + 1
            _counters["bytes_reused"] = int(_counters["bytes_reused"]) + int(hit.get("encoded_size") or 0)
            _counters["alias_guards"] = int(_counters["alias_guards"]) + 1
            return pickle.loads(hit["blob"])

    t0 = time.perf_counter()
    value = builder()
    build_ms = (time.perf_counter() - t0) * 1000.0
    blob = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
    size = len(blob)
    digest = hashlib.sha256(blob).hexdigest()[:24]
    entry = {
        "schema": SCHEMA,
        "family": family,
        "schema_version": schema_version,
        "authority_key": dict(authority_key),
        "content_digest": digest,
        "encoded_size": size,
        "run_id": authority_key.get("run_id"),
        "runtime_generation": authority_key.get("runtime_generation"),
        "scientific_tick": authority_key.get("scientific_tick"),
        "representation": REPRESENTATION,
        "blob": blob,
    }
    with _lock:
        existing = _cache.get(key)
        if existing is not None:
            _cache.move_to_end(key)
            _counters["hits"] = int(_counters["hits"]) + 1
            _counters["bytes_reused"] = int(_counters["bytes_reused"]) + int(existing.get("encoded_size") or 0)
            _counters["alias_guards"] = int(_counters["alias_guards"]) + 1
            return pickle.loads(existing["blob"])
        _fit_locked(size)
        _cache[key] = entry
        global _bytes_est
        _bytes_est = int(_bytes_est) + int(size)
        _counters["misses"] = int(_counters["misses"]) + 1
        _counters["builds"] = int(_counters["builds"]) + 1
        _counters["bytes_built"] = int(_counters["bytes_built"]) + int(size)
        _counters["build_ms_total"] = float(_counters["build_ms_total"]) + float(build_ms)
        _counters["alias_guards"] = int(_counters["alias_guards"]) + 1
    return pickle.loads(blob)


def stats() -> dict[str, Any]:
    with _lock:
        hits = int(_counters["hits"])
        misses = int(_counters["misses"])
        total = hits + misses
        return {
            "schema": SCHEMA,
            "capability": CAPABILITY,
            "profile": PROFILE,
            "authority": AUTHORITY,
            "enabled": is_enabled(),
            "telemetry_enabled": telemetry_enabled(),
            "representation": REPRESENTATION,
            "entries": len(_cache),
            "max_entries": DEFAULT_MAX_ENTRIES,
            "bytes_est": int(_bytes_est),
            "max_bytes": DEFAULT_MAX_BYTES,
            "hit_rate": (hits / total) if total else 0.0,
            "counters": dict(_counters),
            "families_present": sorted({str(e.get("family")) for e in _cache.values()}),
            "eviction_policy": "LRU_THEN_GENERATION_CLEAR",
            "note": "Derived Observer serialization only; not snapshot/evidence authority.",
        }


def reset_counters() -> None:
    with _lock:
        for k in list(_counters.keys()):
            if k == "invalidation_reasons":
                _counters[k] = {}
            elif isinstance(_counters[k], float):
                _counters[k] = 0.0
            else:
                _counters[k] = 0


def run_id_for_runtime(runtime: Any) -> str:
    seed = getattr(runtime, "seed", None)
    gen = getattr(runtime, "_observer_runtime_generation", 0)
    return f"seed{seed}|id{id(runtime)}|g{gen}"


def config_authority_token(runtime: Any) -> str:
    """Stable-enough config token for cache keys (not snapshot authority)."""
    cfg = getattr(runtime, "config", None)
    parts = {
        "model_line": str(getattr(cfg, "model_line", "") or ""),
        "public_preset": str(getattr(cfg, "public_preset", "") or ""),
        "seed": int(getattr(runtime, "seed", 0) or 0),
        "w": int(getattr(getattr(cfg, "planet", None), "width", 0) or 0),
        "h": int(getattr(getattr(cfg, "planet", None), "height", 0) or 0),
        "cog": bool(getattr(getattr(cfg, "cognition", None), "cognition_enabled", False)),
    }
    # Prefer mechanism fingerprint when available on session-bound runtime
    fp = getattr(runtime, "_p4_config_fingerprint", None)
    if fp:
        parts["fp"] = str(fp)
    return authority_digest(parts)


def vw1_digest_token(runtime: Any) -> str:
    try:
        from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

        st = state_of(getattr(runtime, "world", None))
        if st is None:
            return "none"
        return str(st.digest())
    except Exception:
        return "unavailable"


def entity_revision_token(runtime: Any) -> str:
    """Entity lifecycle + coarse pose revision for world-frame keys."""
    world = getattr(runtime, "world", None)
    objs = list(getattr(world, "resource_objects", None) or [])
    ids = sorted(str(getattr(o, "object_id", "") or "") for o in objs)
    poses = []
    for o in objs[:64]:
        poses.append((
            str(getattr(o, "object_id", "") or ""),
            round(float(getattr(o, "x", 0.0) or 0.0), 6),
            round(float(getattr(o, "y", 0.0) or 0.0), 6),
            str(getattr(o, "physical_state", "") or ""),
        ))
    body_poses = []
    slots = getattr(runtime, "slots", None)
    if slots:
        for i, slot in enumerate(slots):
            b = getattr(slot, "body", None)
            if b is None:
                continue
            body_poses.append((
                i,
                round(float(getattr(b, "x", 0.0) or 0.0), 6),
                round(float(getattr(b, "y", 0.0) or 0.0), 6),
                round(float(getattr(b, "theta", 0.0) or 0.0), 6),
            ))
    else:
        body = getattr(runtime, "body", None)
        if body is not None:
            body_poses.append((
                0,
                round(float(getattr(body, "x", 0.0) or 0.0), 6),
                round(float(getattr(body, "y", 0.0) or 0.0), 6),
                round(float(getattr(body, "theta", 0.0) or 0.0), 6),
            ))
    return authority_digest({
        "n_ro": len(ids),
        "ids": ids[:64],
        "ro_poses": poses,
        "bodies": body_poses,
        "world_tick": int(getattr(world, "tick", 0) or 0),
    })


def subscription_token(derived: Any) -> str:
    if derived is None:
        return "default_map"
    try:
        return authority_digest({
            "volume": bool(getattr(derived, "include_volume", False)),
            "surface": bool(getattr(derived, "include_surface", False)),
            "products": sorted(str(p) for p in (getattr(derived, "products", None) or [])),
        })
    except Exception:
        return "unknown"
