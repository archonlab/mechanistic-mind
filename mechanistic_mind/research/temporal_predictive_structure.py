"""Experimental temporal predictive structure.

Default OFF. Trajectory-conditioned prediction from ordinary recent fragments.

Antecedent is a bounded window of successive accessible observations, represented
as successive differences (not CLOCK, not RISING/FALLING labels). Identical
presents with different recent histories yield different windows.

Reuses continuation-class grouping on the window (not snapshot SHA).
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import predictive_relevance as prl
from mechanistic_mind.research.predictive_compression import _sig
from mechanistic_mind.research.predictive_equivalence import _floats, bump_store_generation

WINDOW = 4
LAGS = (1, 2, 3, 4)
RING = 16
MIN_WINDOW = 2  # at least one successive difference

# BETA2-03: window fragments are flat float maps — dict() equals deepcopy.
_USE_FRAGMENT_DICT_COPY = True


def set_fragment_dict_copy(enabled: bool) -> None:
    global _USE_FRAGMENT_DICT_COPY
    _USE_FRAGMENT_DICT_COPY = bool(enabled)


def _copy_window_fragment(f: dict[str, float]) -> dict[str, float]:
    if not _USE_FRAGMENT_DICT_COPY:
        from copy import deepcopy as _dc

        return _dc(f)
    return dict(f)


def empty_store() -> dict[str, Any]:
    inner = pe.empty_store()
    inner["enabled"] = False
    return {
        "enabled": False,
        "ring": [],
        "window": WINDOW,
        "lags": list(LAGS),
        "inner": inner,
        "learns": 0,
        "retrieves": 0,
        "matches": 0,
        "conflicts": 0,
        "appends": 0,
        "relevance": prl.empty_meta(),
    }


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    inner = store.get("inner") or {}
    ring = store.get("ring") or []
    return {
        "enabled": bool(store.get("enabled")),
        "ring_n": len(ring),
        "window": store.get("window"),
        "lags": list(store.get("lags") or []),
        "learns": store.get("learns"),
        "matches": store.get("matches"),
        "conflicts": store.get("conflicts"),
        "classes": pe.snapshot(inner),
        "ring_cap": RING,
        "inner_caps": {
            "MAX_CLASSES": pe.MAX_CLASSES,
            "MAX_MEMBERS": pe.MAX_MEMBERS,
            "MAX_EPISODES": pe.MAX_EPISODES,
        },
        "note": "TEMPORAL_PREDICTIVE_STRUCTURE — not time perception, not a clock",
    }


def _cont_view(predicted: dict[str, Any], dfrag: dict[str, float]) -> dict[str, float]:
    """Continuation channels only (drop window-delta keys copied onto the prediction)."""
    return {
        str(k): float(v)
        for k, v in (predicted or {}).items()
        if k not in dfrag and isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def _window_deltas(frags: list[dict[str, float]]) -> dict[str, float]:
    """Successive differences across a short ordinary history. No tick/time keys."""
    rows = [_floats(f) for f in frags]
    if len(rows) < MIN_WINDOW:
        return {}
    out: dict[str, float] = {}
    keys = set()
    for r in rows:
        keys |= set(r)
    for i in range(1, len(rows)):
        for k in keys:
            out[f"d{i}_{k}"] = float(rows[i].get(k, 0.0)) - float(rows[i - 1].get(k, 0.0))
    return out


def append(store: dict[str, Any], fragment: dict[str, float]) -> None:
    if store.get("enabled") is False:
        return
    ring = store.setdefault("ring", [])
    ring.append(_floats(fragment))
    store["ring"] = ring[-RING:]
    store["appends"] = int(store.get("appends") or 0) + 1
    # Window identity changed → same-tick retrieve memo must not reuse prior results.
    bump_store_generation(store)


def current_window(store: dict[str, Any], present: dict[str, float] | None = None) -> list[dict[str, float]]:
    ring = list(store.get("ring") or [])
    w = int(store.get("window") or WINDOW)
    if present is not None:
        pf = _floats(present)
        if not ring or _sig(ring[-1]) != _sig(pf):
            ring = ring + [pf]
    return ring[-w:]


def learn(
    store: dict[str, Any],
    *,
    consequent: dict[str, float],
    action: str,
    tick: int = 0,
    raw_id: Any = None,
) -> dict[str, Any]:
    """Associate windows that ended `lag` steps ago with the current observation.

    `tick` is provenance only and never enters the trajectory fragment.
    """
    if store.get("enabled") is False:
        return {"status": "DISABLED"}
    inner = store.setdefault("inner", pe.empty_store())
    inner["enabled"] = True
    ring = store.get("ring") or []
    w = int(store.get("window") or WINDOW)
    lags = tuple(store.get("lags") or LAGS)
    n = len(ring)
    learned = []
    for lag in lags:
        end = n - int(lag)  # window ends lag steps before the not-yet-appended present
        # ring[-1] is previous observation; lag=1 → end = n-1
        if end < 0:
            continue
        start = end - w + 1
        if start < 0:
            continue
        window = ring[start : end + 1]
        if len(window) != w:
            continue
        dfrag = _window_deltas(window)
        if not dfrag:
            continue
        act = f"{action}|L{int(lag)}"
        got = pe.learn(
            inner,
            fragment=dfrag,
            action=act,
            consequent=_floats(consequent),
            tick=int(tick),
            raw_id=raw_id,
        )
        learned.append({"lag": int(lag), "status": got.get("status"), "class_id": got.get("class_id"), "n": len(window)})
        store["learns"] = int(store.get("learns") or 0) + 1
    bump_store_generation(store)
    return {"status": "LEARNED" if learned else "TOO_SHORT", "items": learned}


# Action-independent temporal query memo. One current payload per TPS store.
# Not a retrieval-result cache: action/lag matching still runs every call.
_USE_PREPARED_QUERY = True


def set_prepared_query_enabled(enabled: bool) -> None:
    """Test/bench switch. Production default is True. Does not alter formulas."""
    global _USE_PREPARED_QUERY
    _USE_PREPARED_QUERY = bool(enabled)


def prepared_query_enabled() -> bool:
    return bool(_USE_PREPARED_QUERY)


def _window_key(window: list[dict[str, float]]) -> tuple[str, ...]:
    return tuple(_sig(f) for f in window)


def _prepared_generation(store: dict[str, Any]) -> tuple[int, int, int]:
    return (
        int(store.get("_retrieve_cache_gen") or 0),
        int((store.get("inner") or {}).get("_ix_gen") or 0),
        int(store.get("window") or WINDOW),
    )


def _prepared_token(store: dict[str, Any], present: dict[str, float]) -> tuple[Any, ...]:
    ring = store.get("ring")
    n = len(ring or ())
    last_id = id(ring[-1]) if ring else 0
    return (
        _prepared_generation(store),
        id(ring) if ring is not None else 0,
        n,
        last_id,
        id(present),
    )


def build_prepared_query(store: dict[str, Any], present: dict[str, float]) -> dict[str, Any]:
    """Rebuild action-independent temporal query (oracle / miss path).

    Contains no action, bucket, match, support, or selected lag.
    """
    present_f = _floats(present)
    present_sig = _sig(present_f)
    window = current_window(store, present)
    wcfg = int(store.get("window") or WINDOW)
    too_short = len(window) < wcfg
    dfrag: dict[str, float] = {} if too_short else _window_deltas(window)
    empty_deltas = (not too_short) and (not dfrag)
    short = too_short or empty_deltas
    window_key = _window_key(window)
    recent = [
        {"index": i - len(window) + 1, "fragment": _copy_window_fragment(f)}
        for i, f in enumerate(window)
    ]
    return {
        "token": _prepared_token(store, present),
        "generation": _prepared_generation(store),
        "window": window,
        "window_key": window_key,
        "window_n": len(window),
        "dfrag": dfrag,
        "delta_sig": _sig({}) if short else _sig(dfrag),
        "present": present_f,
        "raw_present_sig": present_sig,
        "recent": recent,
        "too_short": short,
        "gate": "window_too_short" if short else "delta_window",
    }


def get_prepared_query(store: dict[str, Any], present: dict[str, float]) -> dict[str, Any]:
    """Return current prepared query, rebuilding when generation/window identity changes."""
    token = _prepared_token(store, present)
    cached = store.get("_prepared_query") if _USE_PREPARED_QUERY else None
    if isinstance(cached, dict) and cached.get("token") == token:
        store["_prepared_query_hits"] = int(store.get("_prepared_query_hits") or 0) + 1
        return cached
    store["_prepared_query_misses"] = int(store.get("_prepared_query_misses") or 0) + 1
    pq = build_prepared_query(store, present)
    store["_prepared_query_builds"] = int(store.get("_prepared_query_builds") or 0) + 1
    if _USE_PREPARED_QUERY:
        store["_prepared_query"] = pq
    return pq


def _retrieve_uncached(
    store: dict[str, Any],
    present: dict[str, float],
    action: str,
    *,
    lag: int | None,
    meta: dict[str, Any] | None,
    prepared: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Core TPS retrieve without counter side-effects or same-tick result memo."""
    inner = store.get("inner") or pe.empty_store()
    pq = prepared if prepared is not None else build_prepared_query(store, present)
    if pq.get("too_short"):
        return {"status": "NO_MATCH", "predicted": {}, "gate": "window_too_short"}
    dfrag = pq["dfrag"]
    lags = [int(lag)] if lag is not None else list(store.get("lags") or LAGS)
    use_rel = bool(meta is not None and meta.get("enabled"))
    hits = []
    conflicts = []
    for L in lags:
        act = f"{action}|L{int(L)}"
        if use_rel:
            got = prl.retrieve(inner, dfrag, act, meta=meta, count=False)
        else:
            got = pe.retrieve(inner, dfrag, act, count=False)
        if got.get("status") == "MATCH":
            got = dict(got)
            got["lag"] = int(L)
            got["predicted_continuation"] = _cont_view(got.get("predicted") or {}, dfrag)
            got["source"] = "temporal_predictive_structure"
            hits.append((int(L), got))
        elif got.get("status") in {"CONFLICT", "TEMPORAL_CONFLICT"}:
            conflicts.append((int(L), got))
    recent = list(pq["recent"])
    base = {
        "window_n": int(pq["window_n"]),
        "delta_sig": pq["delta_sig"],
        "source": "temporal_predictive_structure",
        "recent": recent,
        "not_clock": True,
        "raw_present_sig": pq["raw_present_sig"],
        "gate": "delta_window",
    }
    if not hits:
        if conflicts:
            return {
                **base,
                "status": "TEMPORAL_CONFLICT",
                "predicted": {},
                "gate": "inner_relevance_conflict",
                "next_gear_missing": True,
                "n_hits": 0,
            }
        return {**base, "status": "NO_MATCH", "predicted": {}, "gate": "no_temporal_class"}
    tau = float(inner.get("continuation_linf") or pe.CONTINUATION_LINF)
    conts = [h[1].get("predicted_continuation") or {} for h in hits]
    if len(hits) > 1 and any(pe._linf(conts[0], c) > tau for c in conts[1:]):
        return {
            **base,
            "status": "TEMPORAL_CONFLICT",
            "predicted": {},
            "gate": "conflicting_lag_or_class",
            "next_gear_missing": True,
            "n_hits": len(hits),
            "lags": [h[0] for h in hits],
            "candidates": [h[1] for h in hits],
        }
    L, got = max(hits, key=lambda t: int(t[1].get("support") or 0))
    return {
        **base,
        "status": "MATCH",
        "predicted": got.get("predicted") or {},
        "predicted_continuation": got.get("predicted_continuation") or {},
        "support": got.get("support"),
        "class_id": got.get("class_id"),
        "lag": L,
        "relevant": got.get("relevant"),
        "allowed_variation": got.get("allowed_variation"),
    }


def retrieve(
    store: dict[str, Any],
    present: dict[str, float],
    action: str,
    *,
    lag: int | None = None,
    count: bool = True,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if store.get("enabled") is False:
        return {"status": "DISABLED", "predicted": {}}
    if count:
        store["retrieves"] = int(store.get("retrieves") or 0) + 1
    use_rel = bool(meta is not None and meta.get("enabled"))
    # Same-tick result memo: identical trajectory window + action + lag + generation.
    # Prepared query (when enabled) supplies window_key without a second reconstruction.
    # Disabled path rebuilds window+signatures here and again in _retrieve_uncached (oracle).
    if _USE_PREPARED_QUERY:
        pq = get_prepared_query(store, present)
        window_key = pq["window_key"]
        prepared = pq
    else:
        window = current_window(store, present)
        window_key = _window_key(window)
        prepared = None
    gen = (
        int(store.get("_retrieve_cache_gen") or 0),
        int((store.get("inner") or {}).get("_ix_gen") or 0),
    )
    cache_key = (
        gen,
        window_key,
        str(action),
        None if lag is None else int(lag),
        use_rel,
    )
    cache = store.setdefault("_retrieve_cache", {})
    hit = cache.get(cache_key)
    if hit is not None:
        store["_retrieve_cache_hits"] = int(store.get("_retrieve_cache_hits") or 0) + 1
        result = hit
    else:
        store["_retrieve_cache_misses"] = int(store.get("_retrieve_cache_misses") or 0) + 1
        result = _retrieve_uncached(store, present, action, lag=lag, meta=meta, prepared=prepared)
        cache[cache_key] = result
    if count:
        if result.get("status") == "MATCH":
            store["matches"] = int(store.get("matches") or 0) + 1
        elif result.get("status") == "TEMPORAL_CONFLICT":
            store["conflicts"] = int(store.get("conflicts") or 0) + 1
    return result


def diagnostic(store: dict[str, Any], present: dict[str, float], action: str) -> dict[str, Any]:
    got = retrieve(store, present, action, count=False)
    window = current_window(store, present)
    return {
        "kind": "TEMPORAL_PREDICTIVE_STRUCTURE",
        "not_physical_ground_truth": True,
        "not_time_perception": True,
        "recent": got.get("recent") or [
            {"index": i - len(window) + 1, "fragment": _copy_window_fragment(f)}
            for i, f in enumerate(window)
        ],
        "retrieved": got,
        "raw_present": _floats(present),
        "matched_temporal_representation": {
            "delta_sig": got.get("delta_sig"),
            "lag": got.get("lag"),
            "class_id": got.get("class_id"),
            "gate": got.get("gate"),
        },
        "predicted_continuation": got.get("predicted_continuation") or {},
        "support": got.get("support"),
        "provenance": {
            "class_id": got.get("class_id"),
            "lag": got.get("lag"),
            "window_n": got.get("window_n"),
            "relevant": got.get("relevant"),
        },
    }


def refresh_relevance(store: dict[str, Any], *, tick: int = 0) -> dict[str, Any]:
    meta = store.setdefault("relevance", prl.empty_meta())
    if not store.get("enabled"):
        meta["enabled"] = False
        return {"status": "DISABLED"}
    meta["enabled"] = True
    inner = store.setdefault("inner", pe.empty_store())
    inner["enabled"] = True
    out = prl.refresh(inner, tick=int(tick), meta=meta)
    bump_store_generation(store)
    return out


def memory_usage(store: dict[str, Any]) -> dict[str, Any]:
    inner = store.get("inner") or {}
    classes = list((inner.get("classes") or {}).values())
    from mechanistic_mind.research import pe_cold_archive as cold

    n_cold = cold.archive_count(inner)
    n_members = sum(len(c.get("members") or {}) for c in classes)
    n_for = sum(1 for c in classes if c.get("status") == "FORGOTTEN") + n_cold
    return {
        "ring_n": len(store.get("ring") or []),
        "ring_cap": RING,
        "window": store.get("window") or WINDOW,
        "lags": list(store.get("lags") or LAGS),
        "active_classes": sum(1 for c in classes if c.get("status") == "ACTIVE"),
        "forgotten_classes": n_for,
        "members": n_members,
        "episodes": len(inner.get("episodes") or []),
        "learns": store.get("learns"),
        "retrieves": store.get("retrieves"),
        "matches": store.get("matches"),
        "conflicts": store.get("conflicts"),
        "caps": {
            "RING": RING,
            "WINDOW": WINDOW,
            "LAGS": list(LAGS),
            "MAX_CLASSES": pe.MAX_CLASSES,
            "MAX_MEMBERS": pe.MAX_MEMBERS,
            "MAX_EPISODES": pe.MAX_EPISODES,
        },
        "bounded": len(store.get("ring") or []) <= RING
        and n_members <= pe.MAX_CLASSES * pe.MAX_MEMBERS
        and len(inner.get("episodes") or []) <= pe.MAX_EPISODES,
    }
