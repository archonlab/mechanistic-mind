"""P4B Observer canonical response encoding — derived transport only.

Schema: OBSERVER_CANONICAL_RESPONSE_ENCODING_V1
Capability: canonical_response_encoding_optimization
Profile: AUTHORITY_PRESERVING_JSON_RESPONSE_ENCODING_P4B_V1
Authority: DERIVED_TRANSPORT_OPTIMIZATION_NO_SCIENTIFIC_EFFECT

Same-tick complete encoded HTTP response cache. Does not alter frame contents,
P1–P5 protocol, physics, cognition, snapshots, or Analyzer exports.

Encoder matches Starlette JSONResponse.render (FastAPI HTTP JSON path) so serving
pre-encoded bytes is byte-identical to a fresh Response of the same object graph
without paying jsonable_encoder on every poll.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from typing import Any, Callable

SCHEMA = "OBSERVER_CANONICAL_RESPONSE_ENCODING_V1"
CAPABILITY = "canonical_response_encoding_optimization"
PROFILE = "AUTHORITY_PRESERVING_JSON_RESPONSE_ENCODING_P4B_V1"
AUTHORITY = "DERIVED_TRANSPORT_OPTIMIZATION_NO_SCIENTIFIC_EFFECT"

MEDIA_TYPE = "application/json"
# Starlette JSONResponse.render contract (fastapi/starlette HTTP JSON):
ENSURE_ASCII = False
ALLOW_NAN = False
SEPARATORS = (",", ":")
UNICODE_ESCAPING = "UTF8_ENSURE_ASCII_FALSE"
NONFINITE_POLICY = "REJECT_RAISE_VALUEERROR"
KEY_ORDER_POLICY = "PRESERVE_INSERTION_ORDER_NO_SORT"
FLOAT_POLICY = "PYTHON_JSON_DEFAULT_FINITE_ONLY"
NEGATIVE_ZERO_POLICY = "PRESERVED_BY_PYTHON_JSON"

DEFAULT_MAX_ENTRIES = 48
DEFAULT_MAX_BYTES = 48 * 1024 * 1024  # 48 MiB encoded body budget
_ENV_ENABLE = "PSY_OBSERVER_RESPONSE_ENCODING_CACHE"
_ENV_TELEM = "PSY_OBSERVER_RESPONSE_ENCODING_TELEM"

_lock = threading.RLock()
_enabled: bool | None = None
_telem_enabled: bool | None = None
_inflight: set[str] = set()
_cache: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
_bytes_est = 0
_counters: dict[str, Any] = {
    "hits": 0,
    "misses": 0,
    "encodes": 0,
    "evictions": 0,
    "invalidations": 0,
    "encode_failures": 0,
    "stale_prevented": 0,
    "inflight_waits": 0,
    "bytes_reused": 0,
    "bytes_encoded": 0,
    "encode_ms_total": 0.0,
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


def encode_canonical_json(obj: Any) -> bytes:
    """Encode Observer HTTP JSON body (Starlette JSONResponse-compatible).

    Raises ValueError on NaN/Inf (allow_nan=False). Does not use default=str —
    payload must already be JSON-native (live_frame / current_frame contract).
    """
    return json.dumps(
        obj,
        ensure_ascii=ENSURE_ASCII,
        allow_nan=ALLOW_NAN,
        indent=None,
        separators=SEPARATORS,
    ).encode("utf-8")


def authority_digest(parts: dict[str, Any]) -> str:
    raw = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def make_cache_key(authority_key: dict[str, Any]) -> str:
    return f"HTTP_STATE|{authority_digest(authority_key)}"


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
    _bytes_est = max(0, int(_bytes_est) - int(entry.get("nbytes") or 0))
    _counters["evictions"] = int(_counters["evictions"]) + 1


def _fit_locked(extra: int) -> None:
    global _bytes_est
    while _cache and (
        len(_cache) >= DEFAULT_MAX_ENTRIES or int(_bytes_est) + int(extra) > DEFAULT_MAX_BYTES
    ):
        _evict_one_locked()


def clear(*, reason: str = "CLEAR") -> None:
    with _lock:
        _cache.clear()
        global _bytes_est
        _bytes_est = 0
        _inflight.clear()
        _counters["invalidations"] = int(_counters["invalidations"]) + 1
        _bump_reason(reason)


def reset_counters() -> None:
    with _lock:
        for k in list(_counters.keys()):
            if k == "invalidation_reasons":
                _counters[k] = {}
            elif isinstance(_counters[k], float):
                _counters[k] = 0.0
            else:
                _counters[k] = 0


def _p2_p3_ids(frame: dict[str, Any]) -> dict[str, Any]:
    world = frame.get("world") if isinstance(frame.get("world"), dict) else {}
    vol = world.get("observer_camera_occupancy_consumer") if isinstance(world, dict) else None
    surf = world.get("observer_surface_light") if isinstance(world, dict) else None
    if not isinstance(vol, dict):
        vol = {}
    if not isinstance(surf, dict):
        # SURFACE may live under alternate researcher keys; keep tolerant.
        surf = world.get("surface_light_view") if isinstance(world, dict) else {}
    if not isinstance(surf, dict):
        surf = {}
    return {
        "volume_static_id": vol.get("static_payload_id") or vol.get("static_id"),
        "volume_dynamic_id": vol.get("dynamic_payload_id") or vol.get("dynamic_id"),
        "volume_mode": vol.get("payload_mode") or vol.get("mode"),
        "surface_static_id": surf.get("static_payload_id") or surf.get("static_id"),
        "surface_dynamic_id": surf.get("dynamic_payload_id") or surf.get("dynamic_id"),
        "surface_mode": surf.get("payload_mode") or surf.get("mode"),
    }


def authority_key_from_frame(
    frame: dict[str, Any],
    *,
    run_id: str | None,
    runtime_generation: int,
    selected_agent: Any = None,
    subscription_products: Any = None,
    evidence_mode: str | None = None,
    endpoint: str = "GET /api/state",
    schema_version: str = "1",
) -> dict[str, Any]:
    hdr = frame.get("header") if isinstance(frame.get("header"), dict) else {}
    obs = frame.get("observer") if isinstance(frame.get("observer"), dict) else {}
    interest = frame.get("observer_interest") if isinstance(frame.get("observer_interest"), dict) else {}
    products = subscription_products
    if products is None:
        products = hdr.get("observer_products") or interest.get("products")
    if isinstance(products, (list, tuple, set, frozenset)):
        products = sorted(str(p) for p in products)
    agent = selected_agent
    if agent is None:
        agent = (
            obs.get("selected_agent_id")
            or hdr.get("selected_agent_id")
            or hdr.get("selected_agent")
        )
    pids = _p2_p3_ids(frame)
    return {
        "endpoint": endpoint,
        "schema": SCHEMA,
        "schema_version": schema_version,
        "run_id": str(run_id or hdr.get("run_id") or "") or None,
        "runtime_generation": int(
            hdr.get("runtime_generation") if hdr.get("runtime_generation") is not None else runtime_generation
        ),
        "scientific_tick": int(hdr.get("frame_tick") or hdr.get("tick") or -1),
        "sim_tick": int(hdr.get("sim_tick") if hdr.get("sim_tick") is not None else hdr.get("live_runtime_tick") or -1),
        "status": str(hdr.get("status") or ""),
        "mode": str(hdr.get("mode") or ""),
        "evidence_mode": str(evidence_mode or hdr.get("evidence_mode") or ""),
        "selected_agent": str(agent) if agent is not None else None,
        "subscription_products": products,
        "observer_hz": hdr.get("observer_hz"),
        "target_tick": hdr.get("target_tick"),
        "display_frozen": hdr.get("display_frozen"),
        "p4_fragment_authority": "SESSION_SCOPED",
        **pids,
    }


def get_cached_bytes(authority_key: dict[str, Any]) -> bytes | None:
    if not is_enabled():
        return None
    key = make_cache_key(authority_key)
    with _lock:
        hit = _cache.get(key)
        if hit is None:
            return None
        _cache.move_to_end(key)
        _counters["hits"] = int(_counters["hits"]) + 1
        _counters["bytes_reused"] = int(_counters["bytes_reused"]) + int(hit.get("nbytes") or 0)
        return hit["body"]


def put_encoded_bytes(authority_key: dict[str, Any], body: bytes) -> bytes:
    """Store a successfully encoded body. Never stores failures."""
    if not is_enabled():
        return body
    key = make_cache_key(authority_key)
    nbytes = len(body)
    entry = {
        "schema": SCHEMA,
        "authority_key": dict(authority_key),
        "nbytes": nbytes,
        "body": body,
        "content_digest": hashlib.sha256(body).hexdigest()[:24],
    }
    with _lock:
        existing = _cache.get(key)
        if existing is not None:
            _cache.move_to_end(key)
            return existing["body"]
        _fit_locked(nbytes)
        _cache[key] = entry
        global _bytes_est
        _bytes_est = int(_bytes_est) + int(nbytes)
    return body


def encode_and_cache(obj: Any, authority_key: dict[str, Any]) -> bytes:
    """Encode once; on success store under authority key. Failures are not cached."""
    if not is_enabled():
        return encode_canonical_json(obj)

    key = make_cache_key(authority_key)
    with _lock:
        hit = _cache.get(key)
        if hit is not None:
            _cache.move_to_end(key)
            _counters["hits"] = int(_counters["hits"]) + 1
            _counters["bytes_reused"] = int(_counters["bytes_reused"]) + int(hit.get("nbytes") or 0)
            return hit["body"]
        if key in _inflight:
            _counters["inflight_waits"] = int(_counters["inflight_waits"]) + 1
        else:
            _inflight.add(key)

    t0 = time.perf_counter()
    try:
        body = encode_canonical_json(obj)
    except Exception:
        with _lock:
            _inflight.discard(key)
            _counters["encode_failures"] = int(_counters["encode_failures"]) + 1
            _counters["misses"] = int(_counters["misses"]) + 1
        raise
    encode_ms = (time.perf_counter() - t0) * 1000.0

    with _lock:
        _inflight.discard(key)
        existing = _cache.get(key)
        if existing is not None:
            _cache.move_to_end(key)
            _counters["hits"] = int(_counters["hits"]) + 1
            _counters["bytes_reused"] = int(_counters["bytes_reused"]) + int(existing.get("nbytes") or 0)
            return existing["body"]
        nbytes = len(body)
        _fit_locked(nbytes)
        _cache[key] = {
            "schema": SCHEMA,
            "authority_key": dict(authority_key),
            "nbytes": nbytes,
            "body": body,
            "content_digest": hashlib.sha256(body).hexdigest()[:24],
        }
        global _bytes_est
        _bytes_est = int(_bytes_est) + int(nbytes)
        _counters["misses"] = int(_counters["misses"]) + 1
        _counters["encodes"] = int(_counters["encodes"]) + 1
        _counters["bytes_encoded"] = int(_counters["bytes_encoded"]) + int(nbytes)
        _counters["encode_ms_total"] = float(_counters["encode_ms_total"]) + float(encode_ms)
    return body


def encode_with_builder(
    authority_key: dict[str, Any],
    builder: Callable[[], Any],
) -> bytes:
    """Build object then encode; used when builder side-effects are intentional."""
    cached = get_cached_bytes(authority_key)
    if cached is not None:
        return cached
    obj = builder()
    return encode_and_cache(obj, authority_key)


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
            "media_type": MEDIA_TYPE,
            "ensure_ascii": ENSURE_ASCII,
            "allow_nan": ALLOW_NAN,
            "separators": list(SEPARATORS),
            "unicode_escaping": UNICODE_ESCAPING,
            "nonfinite_policy": NONFINITE_POLICY,
            "key_order_policy": KEY_ORDER_POLICY,
            "float_policy": FLOAT_POLICY,
            "negative_zero_policy": NEGATIVE_ZERO_POLICY,
            "entries": len(_cache),
            "max_entries": DEFAULT_MAX_ENTRIES,
            "bytes_est": int(_bytes_est),
            "max_bytes": DEFAULT_MAX_BYTES,
            "hit_rate": (float(hits) / float(total)) if total else 0.0,
            "inflight": len(_inflight),
            "counters": dict(_counters),
        }


def contract_fixture() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "capability": CAPABILITY,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "media_type": MEDIA_TYPE,
        "ensure_ascii": ENSURE_ASCII,
        "allow_nan": ALLOW_NAN,
        "separators": list(SEPARATORS),
        "unicode_escaping": UNICODE_ESCAPING,
        "nonfinite_policy": NONFINITE_POLICY,
        "key_order_policy": KEY_ORDER_POLICY,
        "float_policy": FLOAT_POLICY,
        "negative_zero_policy": NEGATIVE_ZERO_POLICY,
        "content_encoding": "identity",
        "cache_default": "ON_AFTER_EQUIVALENCE",
        "telemetry_default": "OFF",
    }
