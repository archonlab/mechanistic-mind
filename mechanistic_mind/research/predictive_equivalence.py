"""Experimental predictive equivalence over continuous observations.

Default OFF. Complements exact 4.21 SHA identity; does not replace raw fragments.

Training: antecedents that repeatedly produce similar *continuations* share a class.
Retrieval: a new observation MATCH-es a class only if it lies inside that class's
axis-aligned span of member antecedents (consequence-defined membership, then
span-based assignment). Not nearest-neighbor in observation space.

Not: global float rounding, FIELD_A bins, MATCH_TOL increase, or semantic labels.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.research.predictive_compression import _sig

MAX_CLASSES = 32
MAX_MEMBERS = 12
MAX_EPISODES = 256
MAX_PROV = 16
MIN_CLASS_SUPPORT = 3
# Internal tolerance for comparing *continuation* statistics only (L-inf
# over consequent channels). Sensitivity-tested. Does not define observation identity.
CONTINUATION_LINF = 0.10

# Performance: flat float maps use dict() instead of deepcopy (exact for dict[str,float]).
# Set False to restore legacy deepcopy for A/B equivalence checks.
_USE_FLOAT_MAP_DICT_COPY = True


def set_float_map_dict_copy(enabled: bool) -> None:
    global _USE_FLOAT_MAP_DICT_COPY
    _USE_FLOAT_MAP_DICT_COPY = bool(enabled)


def float_map_dict_copy_enabled() -> bool:
    return bool(_USE_FLOAT_MAP_DICT_COPY)

# Lightweight cache diagnostics (test/bench). Not scientific state.
_CACHE_STATS = {
    "lookups": 0,
    "hits": 0,
    "misses": 0,
    "invalidations": 0,
    "recomputation": 0,
}
_USE_MEAN_CACHE = True


def cache_stats() -> dict[str, int]:
    return {k: int(v) for k, v in _CACHE_STATS.items()}


def reset_cache_stats() -> None:
    for k in _CACHE_STATS:
        _CACHE_STATS[k] = 0


def empty_store(*, continuation_linf: float | None = None, continuation_l1: float | None = None) -> dict[str, Any]:
    tau = CONTINUATION_LINF
    if continuation_linf is not None:
        tau = float(continuation_linf)
    elif continuation_l1 is not None:
        tau = float(continuation_l1)
    return {
        "classes": {},
        "episodes": [],
        "next_id": 1,
        "continuation_linf": float(tau),
        "continuation_l1": float(tau),  # alias kept for experiment dumps
        "learns": 0,
        "retrieves": 0,
        "matches": 0,
        "splits": 0,
        "forgotten": 0,
        "ambiguous": 0,
        "enabled": False,
    }


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    classes = list((store.get("classes") or {}).values())
    return {
        "class_count": len(classes),
        "active": sum(1 for c in classes if c.get("status") == "ACTIVE"),
        "episode_n": len(store.get("episodes") or []),
        "learns": store.get("learns"),
        "matches": store.get("matches"),
        "splits": store.get("splits"),
        "forgotten": store.get("forgotten"),
        "continuation_linf": store.get("continuation_linf", store.get("continuation_l1")),
        "classes": [
            {
                "id": c.get("id"),
                "action": c.get("action"),
                "support": c.get("support"),
                "n_members": len(c.get("members") or {}),
                "aabb_keys": sorted((c.get("aabb") or {}).keys()),
                "status": c.get("status"),
                "revised_at": c.get("revised_at"),
            }
            for c in classes[:16]
        ],
    }


def _linf(a: dict[str, float], b: dict[str, float]) -> float:
    """Max absolute channel difference. Used only on continuations, never as observation identity."""
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    return max(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys)


def _floats(d: dict[str, Any] | None) -> dict[str, float]:
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[str(k)] = float(v)
    return out


def _copy_float_map(d: dict[str, float]) -> dict[str, float]:
    """Independent copy of a flat float mapping (replaces deepcopy for dict[str, float]).

    Values are immutable floats; a shallow ``dict`` copy matches deepcopy semantics
    for these structures and avoids recursive copy dispatch.
    """
    if not _USE_FLOAT_MAP_DICT_COPY:
        from copy import deepcopy as _dc

        return _dc(d)
    return dict(d)


def _mean(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {}
    keys = set()
    for r in rows:
        keys |= set(r)
    n = float(len(rows))
    return {k: sum(float(r.get(k, 0.0)) for r in rows) / n for k in keys}


def _cont_rep(antecedent: dict[str, float], consequent: dict[str, float]) -> dict[str, float]:
    """Continuation used for grouping: delta on shared keys, absolute on new keys.

    Persistent channels that merely carry the antecedent forward do not split
    classes. Observation identity is not rounded or binned.
    """
    a = _floats(antecedent)
    c = _floats(consequent)
    out: dict[str, float] = {}
    for k, v in c.items():
        out[k] = float(v) - float(a[k]) if k in a else float(v)
    return out


def _predict_from_delta(query: dict[str, float], delta: dict[str, float]) -> dict[str, float]:
    q = _floats(query)
    out = dict(q)
    for k, d in (delta or {}).items():
        if k in q:
            out[k] = float(q[k]) + float(d)
        else:
            out[k] = float(d)
    return out


def _aabb(members: dict[str, dict[str, Any]]) -> dict[str, tuple[float, float]]:
    box: dict[str, list[float]] = {}
    for m in members.values():
        for k, v in (m.get("fragment") or {}).items():
            box.setdefault(k, [float(v), float(v)])
            box[k][0] = min(box[k][0], float(v))
            box[k][1] = max(box[k][1], float(v))
    return {k: (lo, hi) for k, (lo, hi) in box.items()}


def _in_aabb(fragment: dict[str, float], aabb: dict[str, tuple[float, float]]) -> bool:
    """Query must supply every class-span key and lie inside each interval.

    Span is defined by members already grouped via continuation similarity,
    not by Euclidean clustering of observations.
    """
    if not aabb:
        return False
    for k, (lo, hi) in aabb.items():
        if k not in fragment:
            return False
        x = float(fragment[k])
        if x < lo - 1e-12 or x > hi + 1e-12:
            return False
    return True


def set_class_mean_cache_enabled(enabled: bool) -> None:
    """Test/bench switch. Production default is True. Does not alter formulas."""
    global _USE_MEAN_CACHE
    _USE_MEAN_CACHE = bool(enabled)


def class_mean_cache_enabled() -> bool:
    return bool(_USE_MEAN_CACHE)


def _class_mean_c_uncached(cls: dict[str, Any]) -> dict[str, float]:
    """Exact pre-cache aggregation (same formula / member iteration as baseline)."""
    cons = [m.get("mean_c") or {} for m in (cls.get("members") or {}).values() if m.get("mean_c")]
    return _mean(cons) if cons else dict(cls.get("mean_c") or {})


def _invalidate_class_mean_c(cls: dict[str, Any]) -> None:
    """Bump derivation generation after membership / member mean_c mutation."""
    cls["_mean_c_gen"] = int(cls.get("_mean_c_gen") or 0) + 1
    cls.pop("_mean_c_cached", None)
    _CACHE_STATS["invalidations"] = int(_CACHE_STATS["invalidations"]) + 1


def _class_mean_c(cls: dict[str, Any]) -> dict[str, float]:
    """Aggregate member continuation means (identical formula to pre-cache baseline).

    Caches the exact aggregation keyed by ``_mean_c_gen``. ``learn`` invalidates
    before mid-update reads so recomputation sees the new members.
    """
    _CACHE_STATS["lookups"] = int(_CACHE_STATS["lookups"]) + 1
    if not _USE_MEAN_CACHE:
        _CACHE_STATS["misses"] = int(_CACHE_STATS["misses"]) + 1
        _CACHE_STATS["recomputation"] = int(_CACHE_STATS["recomputation"]) + 1
        return _class_mean_c_uncached(cls)
    gen = int(cls.get("_mean_c_gen") or 0)
    cached = cls.get("_mean_c_cached")
    if cached is not None and cached[0] == gen:
        _CACHE_STATS["hits"] = int(_CACHE_STATS["hits"]) + 1
        # Cached mapping is treated as read-only by callers (same values as baseline).
        return cached[1]
    _CACHE_STATS["misses"] = int(_CACHE_STATS["misses"]) + 1
    _CACHE_STATS["recomputation"] = int(_CACHE_STATS["recomputation"]) + 1
    result = _class_mean_c_uncached(cls)
    cls["_mean_c_cached"] = (gen, result)
    return result


def clear_derived_caches(store: dict[str, Any]) -> None:
    """Drop derived mean caches after restore/rebuild. Scientific fields untouched."""
    for cls in (store.get("classes") or {}).values():
        if isinstance(cls, dict):
            cls.pop("_mean_c_cached", None)
            # Keep _mean_c_gen if present so a later mutate still invalidates;
            # without a cached payload there is nothing stale to serve.


def strip_derived_fields(obj: Any) -> Any:
    """Deep-copy omitting cache-only keys for scientific structure compares."""
    if isinstance(obj, dict):
        return {
            k: strip_derived_fields(v)
            for k, v in obj.items()
            if k not in ("_mean_c_cached", "_mean_c_gen")
        }
    if isinstance(obj, list):
        return [strip_derived_fields(v) for v in obj]
    return obj


def learn(
    store: dict[str, Any],
    *,
    fragment: dict[str, float],
    action: str,
    consequent: dict[str, float],
    tick: int,
    raw_id: Any = None,
) -> dict[str, Any]:
    """Record one experienced transition. Group by continuation similarity."""
    if store.get("enabled") is False:
        return {"status": "DISABLED"}
    frag = _floats(fragment)
    cons = _floats(consequent)
    crep = _cont_rep(frag, cons)
    act = str(action)
    sig = _sig(frag)
    tau = float(store.get("continuation_linf") or store.get("continuation_l1") or CONTINUATION_LINF)
    store["learns"] = int(store.get("learns") or 0) + 1
    ep = store.setdefault("episodes", [])
    ep.append({"tick": int(tick), "sig": sig, "action": act, "fragment": frag, "consequent": cons, "cont_rep": crep, "raw_id": raw_id})
    store["episodes"] = ep[-MAX_EPISODES:]

    classes = store.setdefault("classes", {})
    # If this antecedent already belongs to a class, update / maybe split.
    host = None
    for cls in classes.values():
        if cls.get("status") != "ACTIVE":
            continue
        if act != cls.get("action"):
            continue
        if sig in (cls.get("members") or {}):
            host = cls
            break
    if host is not None:
        mem = host["members"][sig]
        mem["support"] = int(mem.get("support") or 0) + 1
        mem["last_tick"] = int(tick)
        mc = dict(mem.get("mean_c") or crep)
        n = float(mem["support"])
        for k, v in crep.items():
            mc[k] = float(mc.get(k, 0.0)) + (float(v) - float(mc.get(k, 0.0))) / n
        mem["mean_c"] = mc
        mem["last_abs"] = _copy_float_map(cons)
        mem.setdefault("raw_ids", []).append(raw_id)
        mem["raw_ids"] = mem["raw_ids"][-8:]
        # Member mean_c mutated: invalidate before mid-update class-mean read.
        _invalidate_class_mean_c(host)
        class_c = _class_mean_c(host)
        if _linf(mc, class_c) > tau:
            mem["contra"] = int(mem.get("contra") or 0) + 1
        else:
            mem["contra"] = 0
        if int(mem.get("contra") or 0) >= 2:
            host["members"].pop(sig, None)
            _invalidate_class_mean_c(host)
            host["support"] = sum(int(m.get("support") or 0) for m in host["members"].values())
            host["aabb"] = _aabb(host["members"])
            host["mean_c"] = _class_mean_c(host)
            host["revised_at"] = int(tick)
            store["splits"] = int(store.get("splits") or 0) + 1
            _add_prov(host, "split_member", sig, tick)
            host = None
        else:
            host["support"] = sum(int(m.get("support") or 0) for m in host["members"].values())
            host["aabb"] = _aabb(host["members"])
            # Same gen as mid-update recompute; reuse cached aggregation.
            host["mean_c"] = _class_mean_c(host)
            _add_prov(host, "support", sig, tick)
            return {"status": "UPDATED", "class_id": host.get("id")}

    # Find a class whose continuation matches this consequent.
    candidates = []
    for cls in classes.values():
        if cls.get("status") != "ACTIVE" or cls.get("action") != act:
            continue
        if _linf(crep, _class_mean_c(cls)) <= tau:
            candidates.append(cls)
    if candidates:
        cls = max(candidates, key=lambda c: int(c.get("support") or 0))
        members = cls.setdefault("members", {})
        if len(members) >= MAX_MEMBERS and sig not in members:
            weakest = min(members.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
            members.pop(weakest, None)
        members[sig] = {
            "sig": sig,
            "fragment": _copy_float_map(frag),
            "mean_c": _copy_float_map(crep),
            "last_abs": _copy_float_map(cons),
            "support": 1,
            "contra": 0,
            "first_tick": int(tick),
            "last_tick": int(tick),
            "raw_ids": [raw_id],
        }
        _invalidate_class_mean_c(cls)
        cls["support"] = sum(int(m.get("support") or 0) for m in members.values())
        cls["aabb"] = _aabb(members)
        cls["mean_c"] = _class_mean_c(cls)
        _add_prov(cls, "join", sig, tick)
        return {"status": "JOINED", "class_id": cls.get("id")}

    if len([c for c in classes.values() if c.get("status") == "ACTIVE"]) >= MAX_CLASSES:
        victim = min(
            (kv for kv in classes.items() if kv[1].get("status") == "ACTIVE"),
            key=lambda kv: int(kv[1].get("support") or 0),
        )[0]
        classes[victim]["status"] = "FORGOTTEN"
        store["forgotten"] = int(store.get("forgotten") or 0) + 1

    cid = f"E{int(store.get('next_id') or 1)}"
    store["next_id"] = int(store.get("next_id") or 1) + 1
    classes[cid] = {
        "id": cid,
        "action": act,
        "status": "ACTIVE",
        "support": 1,
        "members": {
            sig: {
                "sig": sig,
                "fragment": _copy_float_map(frag),
                "mean_c": _copy_float_map(crep),
                "last_abs": _copy_float_map(cons),
                "support": 1,
                "contra": 0,
                "first_tick": int(tick),
                "last_tick": int(tick),
                "raw_ids": [raw_id],
            }
        },
        "aabb": {},
        "mean_c": _copy_float_map(crep),
        "first_tick": int(tick),
        "revised_at": None,
        "provenance": [{"type": "formed", "target": sig, "tick": int(tick)}],
    }
    return {"status": "FORMED", "class_id": cid}


def retrieve(
    store: dict[str, Any],
    fragment: dict[str, float],
    action: str,
    *,
    count: bool = True,
) -> dict[str, Any]:
    """Map a (possibly never-exact) observation to a continuation via class span."""
    if store.get("enabled") is False:
        return {"status": "DISABLED", "predicted": {}}
    if count:
        store["retrieves"] = int(store.get("retrieves") or 0) + 1
    frag = _floats(fragment)
    act = str(action)
    hits = []
    for cls in (store.get("classes") or {}).values():
        if cls.get("status") != "ACTIVE" or cls.get("action") != act:
            continue
        if int(cls.get("support") or 0) < MIN_CLASS_SUPPORT:
            continue
        aabb = cls.get("aabb") or {}
        if _in_aabb(frag, aabb):
            hits.append(cls)
    if not hits:
        return {"status": "NO_MATCH", "predicted": {}, "gate": "not_in_any_class_span"}
    if len(hits) > 1:
        # Ambiguous if continuations disagree.
        means = [_class_mean_c(c) for c in hits]
        tau = float(store.get("continuation_linf") or store.get("continuation_l1") or CONTINUATION_LINF)
        if any(_linf(means[0], m) > tau for m in means[1:]):
            if count:
                store["ambiguous"] = int(store.get("ambiguous") or 0) + 1
            return {
                "status": "NO_MATCH",
                "predicted": {},
                "gate": "ambiguous_class_span",
                "n_hits": len(hits),
            }
    cls = max(hits, key=lambda c: int(c.get("support") or 0))
    if count:
        store["matches"] = int(store.get("matches") or 0) + 1
    return {
        "status": "MATCH",
        "predicted": _predict_from_delta(frag, _class_mean_c(cls)),
        "support": int(cls.get("support") or 0),
        "class_id": cls.get("id"),
        "n_members": len(cls.get("members") or {}),
        "source": "predictive_equivalence",
        "raw_antecedent_sig": _sig(frag),
        "member_sigs": list((cls.get("members") or {}).keys())[:8],
        "aabb": {k: list(v) for k, v in (cls.get("aabb") or {}).items()},
        "gate": "class_span",
    }


def _add_prov(cls: dict[str, Any], typ: str, target: Any, tick: int) -> None:
    prov = cls.setdefault("provenance", [])
    prov.append({"type": typ, "target": target, "tick": int(tick)})
    cls["provenance"] = prov[-MAX_PROV:]


def diagnostic(store: dict[str, Any], fragment: dict[str, float], action: str) -> dict[str, Any]:
    """Observer-facing: raw fragment vs learned representation. Not world truth."""
    got = retrieve(store, fragment, action, count=False)
    return {
        "kind": "LEARNED_PREDICTIVE_REPRESENTATION",
        "not_physical_ground_truth": True,
        "raw_fragment": _floats(fragment),
        "raw_sig": _sig(_floats(fragment)),
        "action": action,
        "retrieved": got,
    }
