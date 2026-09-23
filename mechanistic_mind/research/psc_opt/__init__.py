"""PSC prediction backends: LEGACY / PACKED / NUMBA (optional).

Scientific semantics of ``predict_one_step`` must remain EXACT_MATCH.
Backend is provenance only — never written into agent observation/cognition
payloads that the organism can observe.
"""
from __future__ import annotations

import math
import os
import time
from typing import Any

# Re-export constants used by kernels (mirrors prospective_composition)
MIN_SUPPORT = 3
MATCH_TOL = 0.12

_BACKEND_ENV = "MM_PSC_BACKEND"
_VALID = ("legacy", "packed", "numba")

# Process-local Numba state
_numba_fn = None
_numba_init_error: str | None = None
_numba_compile_s: float | None = None


def resolve_backend(explicit: str | None = None) -> str:
    # Default PACKED: transition stores now routinely fill toward MAX_TRANSITIONS
    # (128). Action-indexed soft-match preserves EXACT_MATCH vs legacy scan order
    # within each action while avoiding O(|transitions|) full-map scans per call.
    # Override with MM_PSC_BACKEND=legacy|numba when needed.
    raw = (explicit or os.environ.get(_BACKEND_ENV) or "packed").strip().lower()
    if raw not in _VALID:
        return "packed"
    if raw == "numba" and get_numba_kernel() is None:
        return "packed"
    return raw


def backend_provenance() -> dict[str, Any]:
    """Researcher/run metadata only — not organism-visible."""
    req = (os.environ.get(_BACKEND_ENV) or "packed").strip().lower()
    active = resolve_backend()
    label = {"legacy": "LEGACY_PYTHON", "packed": "PACKED", "numba": "NUMBA"}.get(active, active.upper())
    return {
        "psc_prediction_backend_requested": req,
        "psc_prediction_backend": label,
        "psc_numba_available": get_numba_kernel() is not None,
        "psc_numba_init_error": _numba_init_error,
        "psc_numba_compile_s": _numba_compile_s,
        "note": "provenance only; not part of agent observation",
    }


def _pack_version(store: dict[str, Any]) -> int:
    return int(store.get("_psc_pack_version") or 0)


def bump_pack_version(store: dict[str, Any]) -> None:
    """Call on any transition insert/update/delete."""
    store["_psc_pack_version"] = _pack_version(store) + 1
    store.pop("_psc_pack", None)


def ensure_pack(store: dict[str, Any]) -> dict[str, Any]:
    """Build/reuse action-indexed packed view. Explicit invalidation via version."""
    pack = store.get("_psc_pack")
    ver = _pack_version(store)
    if isinstance(pack, dict) and int(pack.get("version") or -1) == ver:
        return pack

    by_action: dict[str, list[dict[str, Any]]] = {}
    # Preserve transitions.values() insertion order within each action.
    for row in (store.get("transitions") or {}).values():
        if int(row.get("support") or 0) < MIN_SUPPORT:
            continue
        act = str(row.get("action") or "")
        by_action.setdefault(act, []).append(row)

    # Flat numeric arrays per action (for Numba / packed distance)
    packed_actions: dict[str, dict[str, Any]] = {}
    for act, rows in by_action.items():
        # Channel schema: sorted union of all antecedent keys (stable).
        chans: list[str] = []
        seen: set[str] = set()
        for r in rows:
            for k in (r.get("antecedent") or {}):
                sk = str(k)
                if sk not in seen:
                    seen.add(sk)
                    chans.append(sk)
        n = len(rows)
        m = len(chans)
        ante = [[0.0] * m for _ in range(n)]
        for i, r in enumerate(rows):
            ad = r.get("antecedent") or {}
            for j, c in enumerate(chans):
                ante[i][j] = float(ad.get(c, 0.0))
        packed_actions[act] = {
            "rows": rows,
            "channels": chans,
            "ante": ante,  # list[list[float]] — convertible to array
            "n": n,
            "m": m,
        }

    pack = {"version": ver, "by_action": by_action, "packed_actions": packed_actions}
    store["_psc_pack"] = pack
    return pack


def frag_distance_ordered(a: dict[str, float], b: dict[str, float]) -> float:
    """Exact equivalent of set(a)|set(b) iteration order used by legacy."""
    keys: list[str] = []
    seen: set[str] = set()
    for k in a:
        sk = str(k)
        if sk not in seen:
            seen.add(sk)
            keys.append(sk)
    for k in b:
        sk = str(k)
        if sk not in seen:
            seen.add(sk)
            keys.append(sk)
    if not keys:
        return 0.0
    return sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys) / len(keys)


def mean_cons_cached(row: dict[str, Any]) -> dict[str, float]:
    cached = row.get("_mean_cache")
    if cached is not None:
        return cached
    n = max(1e-9, float(row.get("n") or 1.0))
    out = {k: float(v) / n for k, v in (row.get("sum") or {}).items()}
    row["_mean_cache"] = out
    return out


def reliability_cached(row: dict[str, Any]) -> float:
    cached = row.get("_rel_cache")
    if cached is not None:
        return float(cached)
    n = max(1e-9, float(row.get("n") or 1.0))
    if n < 2:
        rel = 0.5
    else:
        vars_: list[float] = []
        for _k, vs in (row.get("var_sum") or {}).items():
            vars_.append(max(0.0, float(vs) / max(n - 1.0, 1e-9)))
        if not vars_:
            rel = 0.5
        else:
            std = sum(math.sqrt(v) for v in vars_) / len(vars_)
            rel = float(max(0.0, min(1.0, 1.0 - std)))
    row["_rel_cache"] = rel
    return rel


def invalidate_row_caches(row: dict[str, Any]) -> None:
    row.pop("_mean_cache", None)
    row.pop("_rel_cache", None)


def soft_match_legacy(
    transitions: dict[str, Any],
    ant: dict[str, float],
    action: str,
) -> tuple[dict[str, Any] | None, float]:
    """Original scan order: all transitions.values(), filter action."""
    from mechanistic_mind.research.prospective_composition import _frag_distance

    best = None
    best_d = 1e9
    for r in transitions.values():
        if r.get("action") != action:
            continue
        if int(r.get("support") or 0) < MIN_SUPPORT:
            continue
        d = _frag_distance(ant, r.get("antecedent") or {})
        if d < best_d:
            best_d = d
            best = r
    return best, best_d


def soft_match_packed(
    pack: dict[str, Any],
    ant: dict[str, float],
    action: str,
) -> tuple[dict[str, Any] | None, float]:
    from mechanistic_mind.research.prospective_composition import _frag_distance

    rows = (pack.get("by_action") or {}).get(action) or []
    best = None
    best_d = 1e9
    for r in rows:
        d = _frag_distance(ant, r.get("antecedent") or {})
        if d < best_d:
            best_d = d
            best = r
    return best, best_d


def get_numba_kernel():
    global _numba_fn, _numba_init_error, _numba_compile_s
    if _numba_fn is not None:
        return _numba_fn
    if _numba_init_error is not None and _numba_fn is None and "unavailable" in (_numba_init_error or ""):
        return None
    try:
        import numpy as np
        from numba import njit
    except Exception as exc:  # noqa: BLE001
        _numba_init_error = f"unavailable: {exc}"
        return None

    @njit(cache=False, fastmath=False)
    def soft_best(ante_mat, query, n, m):
        best_i = -1
        best_d = 1e9
        for i in range(n):
            s = 0.0
            for j in range(m):
                s += abs(query[j] - ante_mat[i, j])
            d = s / m if m > 0 else 0.0
            if d < best_d:
                best_d = d
                best_i = i
        return best_i, best_d

    t0 = time.perf_counter()
    # Warmup compile with tiny arrays
    a = np.zeros((1, 1), dtype=np.float64)
    q = np.zeros(1, dtype=np.float64)
    soft_best(a, q, 1, 1)
    _numba_compile_s = time.perf_counter() - t0
    _numba_fn = soft_best
    _numba_init_error = None
    return _numba_fn


def soft_match_numba(
    pack: dict[str, Any],
    ant: dict[str, float],
    action: str,
) -> tuple[dict[str, Any] | None, float]:
    """Numba soft match using fixed channel schema (sorted union).

    Distance uses channel schema of packed action group with missing=0.
    When query has extra keys not in schema, fall back to packed Python
    distance to preserve exact set-union semantics.
    """
    import numpy as np

    kernel = get_numba_kernel()
    pa = (pack.get("packed_actions") or {}).get(action)
    if kernel is None or not pa or int(pa.get("n") or 0) == 0:
        return soft_match_packed(pack, ant, action)

    channels: list[str] = pa["channels"]
    # Extra query keys not in schema → exact legacy distance path
    for k in ant:
        if str(k) not in channels and str(k) not in set(channels):
            # membership check
            pass
    chan_set = set(channels)
    for k in ant:
        if str(k) not in chan_set:
            return soft_match_packed(pack, ant, action)

    m = int(pa["m"])
    n = int(pa["n"])
    ante_mat = np.asarray(pa["ante"], dtype=np.float64)
    if ante_mat.ndim != 2:
        return soft_match_packed(pack, ant, action)
    # Cache np array on pack entry
    if pa.get("_ante_np") is None or pa.get("_ante_np").shape != ante_mat.shape:
        pa["_ante_np"] = ante_mat
    else:
        ante_mat = pa["_ante_np"]

    query = np.empty(m, dtype=np.float64)
    for j, c in enumerate(channels):
        query[j] = float(ant.get(c, 0.0))

    # Schema-only distance: sum over m channels / m
    # Legacy uses |A∪B|. If every row antecedent keys ⊆ channels and
    # query keys ⊆ channels and channels == union of all, and each row
    # may miss some channels (0.0), legacy union for (query, row) may be
    # smaller than full schema when both miss the same keys.
    # → Only use Numba when safe: all rows share identical key sets == channels
    rows = pa["rows"]
    for r in rows:
        rk = set(str(k) for k in (r.get("antecedent") or {}))
        if rk != chan_set:
            return soft_match_packed(pack, ant, action)
    if set(str(k) for k in ant) != chan_set:
        # query may be strict subset after _q — still OK if we use union order
        # Fall back to packed for exactness when key sets differ
        return soft_match_packed(pack, ant, action)

    idx, best_d = kernel(ante_mat, query, n, m)
    if idx < 0:
        return None, best_d
    return rows[int(idx)], float(best_d)
