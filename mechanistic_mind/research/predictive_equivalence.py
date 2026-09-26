"""Experimental predictive equivalence over continuous observations.

Default OFF. Complements exact 4.21 SHA identity; does not replace raw fragments.

Training: antecedents that repeatedly produce similar *continuations* share a class.
Retrieval: a new observation MATCH-es a class only if it lies inside that class's
axis-aligned span of member antecedents (consequence-defined membership, then
span-based assignment). Not nearest-neighbor in observation space.

Not: global float rounding, FIELD_A bins, MATCH_TOL increase, or semantic labels.
"""
from __future__ import annotations

from array import array
from typing import Any

from mechanistic_mind.research.predictive_compression import _sig

MAX_CLASSES = 32
# Production default True. Tests may set False to force full-scan path.
_USE_CLASS_INDEX = True
# Dev-only: after index mutations, compare incremental payload to full rebuild.
# OFF in production. Toggle via set_index_validate().
_INDEX_VALIDATE = False


def set_class_index_enabled(enabled: bool) -> None:
    global _USE_CLASS_INDEX
    _USE_CLASS_INDEX = bool(enabled)


def class_index_enabled() -> bool:
    return bool(_USE_CLASS_INDEX)


def set_index_validate(enabled: bool) -> None:
    """Development-only index A/B. Must stay False in production."""
    global _INDEX_VALIDATE
    _INDEX_VALIDATE = bool(enabled)


def index_validate_enabled() -> bool:
    return bool(_INDEX_VALIDATE)
MAX_MEMBERS = 12
MAX_EPISODES = 256
MAX_PROV = 16
MIN_CLASS_SUPPORT = 3
# Compact immutable forgotten-member maps. ACTIVE classes keep full dict maps.
FORGOTTEN_REP_V1 = "pe.forgotten.pack.v1"
_COMPACT_FORGOTTEN = True
_PACK_KEY_INTERN: dict[tuple[str, ...], tuple[str, ...]] = {}
# Internal tolerance for comparing *continuation* statistics only (L-inf
# over consequent channels). Sensitivity-tested. Does not define observation identity.
CONTINUATION_LINF = 0.10

# BETA2-03: flat float maps use dict() instead of deepcopy (exact for dict[str,float]).
# Set False to restore BETA2-02 deepcopy path for equivalence harnesses.
_USE_FLOAT_MAP_DICT_COPY = True


def set_float_map_dict_copy(enabled: bool) -> None:
    global _USE_FLOAT_MAP_DICT_COPY
    _USE_FLOAT_MAP_DICT_COPY = bool(enabled)


def float_map_dict_copy_enabled() -> bool:
    return bool(_USE_FLOAT_MAP_DICT_COPY)


def set_forgotten_compaction(enabled: bool) -> None:
    """Test/bench switch. Production default True. Does not change forget victims."""
    global _COMPACT_FORGOTTEN
    _COMPACT_FORGOTTEN = bool(enabled)


def forgotten_compaction_enabled() -> bool:
    return bool(_COMPACT_FORGOTTEN)


def set_cold_archive(enabled: bool) -> None:
    from mechanistic_mind.research import pe_cold_archive as cold

    cold.set_cold_archive(enabled)


def cold_archive_enabled() -> bool:
    from mechanistic_mind.research import pe_cold_archive as cold

    return cold.cold_archive_enabled()


def set_cold_shadow(enabled: bool) -> None:
    from mechanistic_mind.research import pe_cold_archive as cold

    cold.set_cold_shadow(enabled)


def set_cold_eviction(enabled: bool, *, root=None) -> None:
    from mechanistic_mind.research import pe_cold_archive as cold

    cold.set_cold_eviction(enabled, root=root)

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
    from mechanistic_mind.research import pe_cold_archive as cold

    classes = list((store.get("classes") or {}).values())
    cold_n = cold.archive_count(store)
    preview = []
    for c in classes[:16]:
        preview.append(
            {
                "id": c.get("id"),
                "action": c.get("action"),
                "support": c.get("support"),
                "n_members": len(c.get("members") or {}),
                "aabb_keys": sorted((c.get("aabb") or {}).keys()),
                "status": c.get("status"),
                "revised_at": c.get("revised_at"),
            }
        )
    if len(preview) < 16 and cold_n:
        for rec in cold.iter_cold_records(store, reconstruct=False):
            if len(preview) >= 16:
                break
            preview.append(
                {
                    "id": rec.get("id"),
                    "action": rec.get("action"),
                    "support": rec.get("support"),
                    "n_members": rec.get("n_members"),
                    "aabb_keys": [],
                    "status": rec.get("status"),
                    "revised_at": rec.get("revised_at"),
                }
            )
    return {
        "class_count": len(classes) + cold_n,
        "active": sum(1 for c in classes if c.get("status") == "ACTIVE"),
        "episode_n": len(store.get("episodes") or []),
        "learns": store.get("learns"),
        "matches": store.get("matches"),
        "splits": store.get("splits"),
        "forgotten": store.get("forgotten"),
        "continuation_linf": store.get("continuation_linf", store.get("continuation_l1")),
        "classes": preview,
        "cold_n": cold_n,
    }


def _intern_pack_keys(keys: tuple[str, ...]) -> tuple[str, ...]:
    hit = _PACK_KEY_INTERN.get(keys)
    if hit is None:
        _PACK_KEY_INTERN[keys] = keys
        hit = keys
    return hit


def _bit_get(mask: array, i: int) -> bool:
    return bool(mask[i >> 3] & (1 << (i & 7)))


def _bit_set(mask: bytearray, i: int) -> None:
    mask[i >> 3] |= 1 << (i & 7)


def _as_darray(values: Any, n: int) -> array:
    if isinstance(values, array) and values.typecode == "d" and len(values) == n:
        return values
    out = array("d", [0.0] * n)
    if isinstance(values, (list, tuple, array)):
        for i, v in enumerate(values):
            if i >= n:
                break
            if v is None:
                continue
            out[i] = float(v)
    return out


def _as_mask(raw: Any, n: int) -> array:
    nbytes = (n + 7) >> 3
    if isinstance(raw, array) and raw.typecode == "B" and len(raw) == nbytes:
        return raw
    out = array("B", [0] * nbytes)
    if isinstance(raw, (bytes, bytearray, array, list, tuple)):
        for i, b in enumerate(raw):
            if i >= nbytes:
                break
            out[i] = int(b) & 255
    return out


def _pack_float_map(d: Any, keys: tuple[str, ...]) -> dict[str, array]:
    n = len(keys)
    if isinstance(d, dict) and "v" in d:
        return {
            "v": _as_darray(d.get("v"), n),
            "p": _as_mask(d.get("p"), n),
        }
    vals = array("d", [0.0] * n)
    mask = bytearray((n + 7) >> 3)
    if isinstance(d, dict):
        for i, k in enumerate(keys):
            if k in d:
                vals[i] = float(d[k])
                _bit_set(mask, i)
    return {"v": vals, "p": array("B", mask)}


def _unpack_float_map(packed: Any, keys: tuple[str, ...]) -> dict[str, float]:
    if isinstance(packed, dict) and packed and not ("v" in packed or "p" in packed):
        # Already a channel map (legacy full forgotten member).
        if all(not isinstance(v, (list, tuple, array)) for v in packed.values()):
            return {str(k): float(v) for k, v in packed.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
    n = len(keys)
    if not isinstance(packed, dict):
        return {}
    vals = _as_darray(packed.get("v"), n)
    mask = _as_mask(packed.get("p"), n)
    out: dict[str, float] = {}
    for i, k in enumerate(keys):
        if _bit_get(mask, i):
            out[k] = float(vals[i])
    return out


def forgotten_pack_keys(cls: dict[str, Any]) -> tuple[str, ...]:
    raw = cls.get("_pack_keys")
    if isinstance(raw, (list, tuple)):
        return tuple(str(k) for k in raw)
    return ()


def is_forgotten_packed(cls: dict[str, Any]) -> bool:
    return cls.get("_pe_forgotten_rep") == FORGOTTEN_REP_V1


def forgotten_member_fragment(cls: dict[str, Any], sig: str) -> dict[str, float]:
    """Lossless view of a forgotten (or live) member fragment for tests/forensics."""
    mem = (cls.get("members") or {}).get(sig) or {}
    frag = mem.get("fragment")
    if isinstance(frag, dict) and "v" not in frag:
        return dict(frag)
    return _unpack_float_map(frag, forgotten_pack_keys(cls))


def expand_forgotten_class(cls: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct full member dict maps from a packed forgotten class (copy)."""
    out = {
        k: v
        for k, v in cls.items()
        if k not in ("members", "_pack_keys", "_pe_forgotten_rep", "_mean_c_cached")
    }
    keys = forgotten_pack_keys(cls)
    members_out: dict[str, Any] = {}
    packed = is_forgotten_packed(cls)
    for sig, mem in (cls.get("members") or {}).items():
        if not isinstance(mem, dict):
            members_out[sig] = mem
            continue
        if packed:
            members_out[sig] = {
                "sig": mem.get("sig", sig),
                "fragment": _unpack_float_map(mem.get("fragment"), keys),
                "mean_c": _unpack_float_map(mem.get("mean_c"), keys),
                "last_abs": _unpack_float_map(mem.get("last_abs"), keys),
                "support": mem.get("support"),
                "contra": mem.get("contra"),
                "first_tick": mem.get("first_tick"),
                "last_tick": mem.get("last_tick"),
                "raw_ids": list(mem.get("raw_ids") or []),
            }
        else:
            members_out[sig] = dict(mem)
    out["members"] = members_out
    if packed:
        mc = cls.get("mean_c")
        if isinstance(mc, dict) and "v" in mc:
            out["mean_c"] = _unpack_float_map(mc, keys)
    return out


def compact_forgotten_class(cls: dict[str, Any]) -> dict[str, Any]:
    """Replace wide operational member maps with packed arrays. Identity preserved.

    Called at ACTIVE→FORGOTTEN and once on restore of legacy full forgotten rows.
    Does not change class id, support, AABB, class mean_c, provenance, or relevance.
    """
    if not isinstance(cls, dict) or cls.get("status") != "FORGOTTEN":
        return cls
    members = cls.get("members") or {}
    if not isinstance(members, dict):
        return cls
    if is_forgotten_packed(cls):
        keys = _intern_pack_keys(forgotten_pack_keys(cls))
        cls["_pack_keys"] = keys
        n = len(keys)
        mc = cls.get("mean_c")
        if isinstance(mc, dict) and "v" not in mc:
            cls["mean_c"] = _pack_float_map(mc, keys)
        elif isinstance(mc, dict) and "v" in mc:
            mc["v"] = _as_darray(mc.get("v"), n)
            mc["p"] = _as_mask(mc.get("p"), n)
        for mem in members.values():
            if not isinstance(mem, dict):
                continue
            for fld in ("fragment", "mean_c", "last_abs"):
                packed = mem.get(fld)
                if isinstance(packed, dict) and "v" in packed:
                    packed["v"] = _as_darray(packed.get("v"), n)
                    packed["p"] = _as_mask(packed.get("p"), n)
        cls.pop("_mean_c_cached", None)
        cls.pop("_mean_c_gen", None)
        return cls
    keyset: set[str] = set()
    for mem in members.values():
        if not isinstance(mem, dict):
            continue
        for fld in ("fragment", "mean_c", "last_abs"):
            mp = mem.get(fld)
            if isinstance(mp, dict) and "v" not in mp:
                keyset.update(str(k) for k in mp.keys())
    mc0 = cls.get("mean_c")
    if isinstance(mc0, dict) and "v" not in mc0:
        keyset.update(str(k) for k in mc0.keys())
    keys = _intern_pack_keys(tuple(sorted(keyset)))
    packed_members: dict[str, Any] = {}
    for sig, mem in members.items():
        if not isinstance(mem, dict):
            packed_members[sig] = mem
            continue
        packed_members[sig] = {
            "support": mem.get("support"),
            "contra": mem.get("contra"),
            "first_tick": mem.get("first_tick"),
            "last_tick": mem.get("last_tick"),
            "raw_ids": list(mem.get("raw_ids") or []),
            "fragment": _pack_float_map(mem.get("fragment"), keys),
            "mean_c": _pack_float_map(mem.get("mean_c"), keys),
            "last_abs": _pack_float_map(mem.get("last_abs"), keys),
        }
    cls["members"] = packed_members
    cls["_pack_keys"] = keys
    cls["_pe_forgotten_rep"] = FORGOTTEN_REP_V1
    if isinstance(cls.get("mean_c"), dict) and "v" not in (cls.get("mean_c") or {}):
        cls["mean_c"] = _pack_float_map(cls.get("mean_c"), keys)
    cls.pop("_mean_c_cached", None)
    cls.pop("_mean_c_gen", None)
    return cls


def compact_forgotten_in_store(store: dict[str, Any]) -> None:
    from mechanistic_mind.research import pe_cold_archive as cold

    cold.materialize_arrays(cold.get_archive(store))
    if cold.cold_archive_enabled():
        cold.migrate_forgotten_to_cold(store)
        return
    if not _COMPACT_FORGOTTEN:
        return
    for cls in (store.get("classes") or {}).values():
        if isinstance(cls, dict) and cls.get("status") == "FORGOTTEN":
            compact_forgotten_class(cls)


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
        frag = m.get("fragment") or {}
        if not isinstance(frag, dict) or "v" in frag:
            continue
        for k, v in frag.items():
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
    cons = []
    for m in (cls.get("members") or {}).values():
        mc = m.get("mean_c")
        if isinstance(mc, dict) and mc and "v" not in mc:
            cons.append(mc)
    return _mean(cons) if cons else (
        _unpack_float_map(cls.get("mean_c"), forgotten_pack_keys(cls))
        if isinstance(cls.get("mean_c"), dict) and "v" in (cls.get("mean_c") or {})
        else dict(cls.get("mean_c") or {})
    )


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
    compact_forgotten_in_store(store)
    # Indexes are rebuilt lazily; mark stale so restore/load cannot serve a ghost.
    invalidate_class_indexes(store)


def bump_store_generation(store: dict[str, Any]) -> None:
    """Mark derived indexes and same-tick retrieve caches stale after mutations."""
    store["_ix_gen"] = int(store.get("_ix_gen") or 0) + 1
    store["_retrieve_cache_gen"] = int(store.get("_retrieve_cache_gen") or 0) + 1
    store.pop("_retrieve_cache", None)
    store.pop("_prepared_query", None)


def invalidate_class_indexes(store: dict[str, Any]) -> None:
    """Drop action/member/active indexes (rebuild on next ensure)."""
    bump_store_generation(store)
    store.pop("_ix_action", None)
    store.pop("_ix_member", None)
    store.pop("_ix_built_gen", None)
    store.pop("_active_ids", None)
    store.pop("_active_count", None)


def _scan_active_ids(store: dict[str, Any]) -> list[str]:
    """Canonical ACTIVE id order: ``classes`` insertion order among ACTIVE rows."""
    out: list[str] = []
    for cid, cls in (store.get("classes") or {}).items():
        if isinstance(cls, dict) and cls.get("status") == "ACTIVE":
            out.append(str(cid))
    return out


def scan_active_class_count(store: dict[str, Any]) -> int:
    """Reference scan. Tests only — not a hot-path helper."""
    return len(_scan_active_ids(store))


def rebuild_class_indexes(store: dict[str, Any]) -> None:
    """Rebuild exact action → class-id lists (insertion order) and member-sig map.

    Only ACTIVE classes are indexed. Order of ids under each action matches
    ``classes`` dict insertion order among ACTIVE rows with that action — the
    same relative order the legacy full scan would encounter them.

    FORGOTTEN classes remain in ``classes`` (history/snapshot) but are absent
    from ``_ix_action``, ``_ix_member``, and ``_active_ids``. There is no
    FORGOTTEN→ACTIVE revival in learn/retrieve.
    """
    action_ix: dict[str, list[str]] = {}
    member_ix: dict[str, str] = {}
    active_ids: list[str] = []
    for cid, cls in (store.get("classes") or {}).items():
        if not isinstance(cls, dict):
            continue
        if cls.get("status") != "ACTIVE":
            continue
        sid = str(cid)
        act = str(cls.get("action") or "")
        action_ix.setdefault(act, []).append(sid)
        for sig in (cls.get("members") or {}):
            member_ix[f"{act}\0{sig}"] = sid
        active_ids.append(sid)
    store["_ix_action"] = action_ix
    store["_ix_member"] = member_ix
    store["_active_ids"] = active_ids
    store["_active_count"] = len(active_ids)
    store["_ix_built_gen"] = int(store.get("_ix_gen") or 0)


def ensure_class_indexes(store: dict[str, Any]) -> None:
    if (
        store.get("_ix_built_gen") != int(store.get("_ix_gen") or 0)
        or "_ix_action" not in store
        or "_active_ids" not in store
    ):
        rebuild_class_indexes(store)


def _mark_indexes_current(store: dict[str, Any]) -> None:
    """Keep live indexes; bump generation so TPS retrieve memos invalidate."""
    bump_store_generation(store)
    store["_ix_built_gen"] = int(store.get("_ix_gen") or 0)
    store["_active_count"] = len(store.get("_active_ids") or [])
    if _INDEX_VALIDATE:
        _validate_indexes_or_raise(store)


def capture_index_payload(store: dict[str, Any]) -> dict[str, Any]:
    """Actual derived index content (not merely counts)."""
    ensure_class_indexes(store)
    return {
        "action": {k: list(v) for k, v in (store.get("_ix_action") or {}).items()},
        "member": dict(store.get("_ix_member") or {}),
        "active_ids": list(store.get("_active_ids") or []),
        "active_count": int(store.get("_active_count") or 0),
    }


def rebuild_reference_index_payload(store: dict[str, Any]) -> dict[str, Any]:
    """Full-rebuild oracle over the same ``classes`` mapping."""
    tmp: dict[str, Any] = {
        "classes": store.get("classes") or {},
        "_ix_gen": int(store.get("_ix_gen") or 0),
    }
    rebuild_class_indexes(tmp)
    return {
        "action": {k: list(v) for k, v in (tmp.get("_ix_action") or {}).items()},
        "member": dict(tmp.get("_ix_member") or {}),
        "active_ids": list(tmp.get("_active_ids") or []),
        "active_count": int(tmp.get("_active_count") or 0),
    }


def _validate_indexes_or_raise(store: dict[str, Any]) -> None:
    got = capture_index_payload(store)
    ref = rebuild_reference_index_payload(store)
    if got != ref:
        raise AssertionError(f"PE incremental indexes diverged from rebuild: {got!r} vs {ref!r}")


def active_class_count(store: dict[str, Any]) -> int:
    """O(1) after indexes are current. Rebuilt from canonical ACTIVE rows if stale."""
    ensure_class_indexes(store)
    return int(store.get("_active_count") or 0)


def _index_remove_active(store: dict[str, Any], cid: str, cls: dict[str, Any]) -> None:
    """Drop one ACTIVE class from derived indexes. Canonical row is unchanged."""
    ensure_class_indexes(store)
    sid = str(cid)
    act = str(cls.get("action") or "")
    lst = (store.get("_ix_action") or {}).get(act)
    if lst:
        try:
            lst.remove(sid)
        except ValueError:
            pass
        if not lst:
            (store.get("_ix_action") or {}).pop(act, None)
    member_ix = store.setdefault("_ix_member", {})
    for sig in (cls.get("members") or {}):
        key = f"{act}\0{sig}"
        if member_ix.get(key) == sid:
            member_ix.pop(key, None)
    ids = store.setdefault("_active_ids", [])
    try:
        ids.remove(sid)
    except ValueError:
        pass
    store["_active_count"] = len(ids)


def _index_add_active(store: dict[str, Any], cid: str, cls: dict[str, Any]) -> None:
    """Append a newly ACTIVE class (insertion-order tail)."""
    ensure_class_indexes(store)
    sid = str(cid)
    ids = store.setdefault("_active_ids", [])
    if sid in ids:
        return
    act = str(cls.get("action") or "")
    store.setdefault("_ix_action", {}).setdefault(act, []).append(sid)
    member_ix = store.setdefault("_ix_member", {})
    for sig in (cls.get("members") or {}):
        member_ix[f"{act}\0{sig}"] = sid
    ids.append(sid)
    store["_active_count"] = len(ids)


def _index_refresh_members(store: dict[str, Any], cid: str, cls: dict[str, Any]) -> None:
    """Rewrite member-sig map for one ACTIVE class after join/split."""
    ensure_class_indexes(store)
    sid = str(cid)
    act = str(cls.get("action") or "")
    member_ix = store.setdefault("_ix_member", {})
    stale = [k for k, v in member_ix.items() if v == sid]
    for k in stale:
        member_ix.pop(k, None)
    for sig in (cls.get("members") or {}):
        member_ix[f"{act}\0{sig}"] = sid


def _forget_lowest_support_active(store: dict[str, Any], classes: dict[str, Any]) -> str | None:
    """ACTIVE→FORGOTTEN using only the ACTIVE id list (max MAX_CLASSES).

    Tie-break: first among minima in ``_active_ids`` order, which matches
    ``classes`` insertion order among ACTIVE rows (same as the old
    ``min(classes.items() if ACTIVE)``).
    """
    ensure_class_indexes(store)
    ids = list(store.get("_active_ids") or [])
    if len(ids) < MAX_CLASSES:
        return None
    victim = min(ids, key=lambda cid: int((classes.get(cid) or {}).get("support") or 0))
    cls = classes.get(victim)
    if not isinstance(cls, dict):
        return None
    _index_remove_active(store, victim, cls)
    cls["status"] = "FORGOTTEN"
    if _COMPACT_FORGOTTEN:
        compact_forgotten_class(cls)
    store["forgotten"] = int(store.get("forgotten") or 0) + 1
    from mechanistic_mind.research import pe_cold_archive as cold

    cold.maybe_archive_after_forget(store, classes, victim, cls)
    return victim


def iter_active_classes_for_action(store: dict[str, Any], action: str):
    """Yield ACTIVE classes for ``action`` in legacy full-scan relative order."""
    ensure_class_indexes(store)
    classes = store.get("classes") or {}
    act = str(action)
    for cid in (store.get("_ix_action") or {}).get(act) or ():
        cls = classes.get(cid)
        if cls is None:
            continue
        if cls.get("status") != "ACTIVE":
            continue
        if cls.get("action") != act:
            continue
        yield cls


def find_host_class_by_member_sig(store: dict[str, Any], action: str, sig: str) -> dict[str, Any] | None:
    """O(1) host lookup for learn; returns None if absent (same as scan miss)."""
    ensure_class_indexes(store)
    act = str(action)
    cid = (store.get("_ix_member") or {}).get(f"{act}\0{sig}")
    if not cid:
        return None
    cls = (store.get("classes") or {}).get(cid)
    if not isinstance(cls, dict):
        return None
    if cls.get("status") != "ACTIVE" or cls.get("action") != act:
        return None
    if sig not in (cls.get("members") or {}):
        return None
    return cls


def index_bucket_stats(store: dict[str, Any]) -> dict[str, Any]:
    """Debug/bench: bucket occupancy for the action index."""
    ensure_class_indexes(store)
    buckets = [len(v) for v in (store.get("_ix_action") or {}).values()]
    buckets_sorted = sorted(buckets)
    n = len(buckets_sorted)
    def pct(p: float) -> int:
        if not buckets_sorted:
            return 0
        i = min(n - 1, max(0, int(round(p * (n - 1)))))
        return int(buckets_sorted[i])
    return {
        "bucket_count": n,
        "class_count_active": sum(buckets),
        "mean_bucket": (sum(buckets) / n) if n else 0.0,
        "median_bucket": pct(0.5),
        "p95_bucket": pct(0.95),
        "max_bucket": max(buckets) if buckets else 0,
        "index_entries_member": len(store.get("_ix_member") or {}),
    }


def _inspect_counter_inc(store: dict[str, Any], n: int) -> None:
    """Optional bench instrumentation (no scientific effect)."""
    if store.get("_bench_inspect") is True:
        store["_bench_classes_inspected"] = int(store.get("_bench_classes_inspected") or 0) + int(n)


# Derived index / memo keys — never part of scientific identity.
_DERIVED_STORE_KEYS = frozenset({
    "_mean_c_cached",
    "_mean_c_gen",
    "_ix_action",
    "_ix_member",
    "_ix_gen",
    "_ix_built_gen",
    "_active_ids",
    "_active_count",
    "_retrieve_cache",
    "_retrieve_cache_gen",
    "_prepared_query",
    "_prepared_query_builds",
    "_prepared_query_hits",
    "_prepared_query_misses",
})


def strip_derived_fields(obj: Any) -> Any:
    """Deep-copy omitting cache-only keys for scientific structure compares."""
    if isinstance(obj, dict):
        return {
            k: strip_derived_fields(v)
            for k, v in obj.items()
            if k not in _DERIVED_STORE_KEYS
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
    host = find_host_class_by_member_sig(store, act, sig)
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
            _index_refresh_members(store, str(host.get("id")), host)
            host = None
        else:
            host["support"] = sum(int(m.get("support") or 0) for m in host["members"].values())
            host["aabb"] = _aabb(host["members"])
            # Same gen as mid-update recompute; reuse cached aggregation.
            host["mean_c"] = _class_mean_c(host)
            _add_prov(host, "support", sig, tick)
            _mark_indexes_current(store)
            return {"status": "UPDATED", "class_id": host.get("id")}

    # Find a class whose continuation matches this consequent.
    candidates = []
    scanned = 0
    for cls in iter_active_classes_for_action(store, act):
        scanned += 1
        if _linf(crep, _class_mean_c(cls)) <= tau:
            candidates.append(cls)
    _inspect_counter_inc(store, scanned)
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
        _index_refresh_members(store, str(cls.get("id")), cls)
        _mark_indexes_current(store)
        return {"status": "JOINED", "class_id": cls.get("id")}

    if active_class_count(store) >= MAX_CLASSES:
        _forget_lowest_support_active(store, classes)

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
    _index_add_active(store, cid, classes[cid])
    _mark_indexes_current(store)
    return {"status": "FORMED", "class_id": cid}


def _retrieve_collect_hits_full_scan(
    store: dict[str, Any],
    frag: dict[str, float],
    act: str,
) -> list[dict[str, Any]]:
    """Legacy full class scan (oracle / debug). Not used in production retrieve."""
    hits: list[dict[str, Any]] = []
    n = 0
    for cls in (store.get("classes") or {}).values():
        n += 1
        if cls.get("status") != "ACTIVE" or cls.get("action") != act:
            continue
        if int(cls.get("support") or 0) < MIN_CLASS_SUPPORT:
            continue
        aabb = cls.get("aabb") or {}
        if _in_aabb(frag, aabb):
            hits.append(cls)
    _inspect_counter_inc(store, n)
    return hits


def _retrieve_collect_hits_indexed(
    store: dict[str, Any],
    frag: dict[str, float],
    act: str,
) -> list[dict[str, Any]]:
    """Action-bucket candidate narrowing; same matcher as full scan."""
    hits: list[dict[str, Any]] = []
    n = 0
    for cls in iter_active_classes_for_action(store, act):
        n += 1
        if int(cls.get("support") or 0) < MIN_CLASS_SUPPORT:
            continue
        aabb = cls.get("aabb") or {}
        if _in_aabb(frag, aabb):
            hits.append(cls)
    _inspect_counter_inc(store, n)
    return hits


def _retrieve_from_hits(
    store: dict[str, Any],
    frag: dict[str, float],
    hits: list[dict[str, Any]],
    *,
    count: bool,
) -> dict[str, Any]:
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


def _retrieve_full_scan_reference(
    store: dict[str, Any],
    fragment: dict[str, float],
    action: str,
    *,
    count: bool = False,
) -> dict[str, Any]:
    """Private oracle: pre-index full-scan retrieve. Tests/debug only."""
    if store.get("enabled") is False:
        return {"status": "DISABLED", "predicted": {}}
    if count:
        store["retrieves"] = int(store.get("retrieves") or 0) + 1
    frag = _floats(fragment)
    act = str(action)
    hits = _retrieve_collect_hits_full_scan(store, frag, act)
    return _retrieve_from_hits(store, frag, hits, count=count)


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
    if _USE_CLASS_INDEX:
        hits = _retrieve_collect_hits_indexed(store, frag, act)
    else:
        hits = _retrieve_collect_hits_full_scan(store, frag, act)
    return _retrieve_from_hits(store, frag, hits, count=count)


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
