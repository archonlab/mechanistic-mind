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


# Test/oracle switch: "auto" uses matrix L1 when exact, else dict.
# "dict" forces the reference Python mapping loop.
# "matrix" / "numpy" are microbench-only; numpy is never the default.
_PACKED_L1_MODE = "auto"


def set_packed_l1_mode(mode: str) -> str:
    """Researcher/test control. Does not change MATCH_TOL or scan order."""
    global _PACKED_L1_MODE
    raw = str(mode or "auto").strip().lower()
    if raw not in {"auto", "dict", "matrix", "numpy"}:
        raise ValueError(f"unknown packed L1 mode: {mode!r}")
    _PACKED_L1_MODE = raw
    return _PACKED_L1_MODE


def packed_l1_mode() -> str:
    return _PACKED_L1_MODE


def _col_index(pa: dict[str, Any]) -> dict[str, int]:
    idx = pa.get("_col_index")
    if isinstance(idx, dict) and len(idx) == int(pa.get("m") or 0):
        return idx
    idx = {str(c): j for j, c in enumerate(pa.get("channels") or [])}
    pa["_col_index"] = idx
    return idx


def _query_schema_columns(
    pa: dict[str, Any],
    ant: dict[str, float],
) -> tuple[list[int], list[float]] | None:
    """Map query dict onto pack schema. None → matrix L1 is not exactly |A∪B|/|A∪B|.

    Exact when query key set equals the packed channel schema. Then every row's
    missing schema field is 0.0 in the matrix and is also 0.0 in ``_frag_distance``
    via ``.get(k, 0.0)``, and the denominator is ``m``.
    """
    channels = pa.get("channels") or []
    m = int(pa.get("m") or 0)
    if m == 0 or len(ant) != m or len(channels) != m:
        return None
    col = _col_index(pa)
    # Match _frag_distance key order: set(query)|set(row) == set(query) when
    # key sets are equal (second operand adds nothing).
    order = list(set(ant))
    if len(order) != m:
        return None
    cols: list[int] = [0] * m
    qvals: list[float] = [0.0] * m
    try:
        for t, k in enumerate(order):
            cols[t] = col[str(k)]
            qvals[t] = float(ant[k])
    except KeyError:
        return None
    return cols, qvals


def soft_match_packed_dict(
    rows: list[dict[str, Any]],
    ant: dict[str, float],
) -> tuple[dict[str, Any] | None, float]:
    """Reference oracle: per-row ``_frag_distance`` over dict antecedents.

    Scan order: ``pack.by_action[action]`` (transitions.values() insertion order
    filtered by action and MIN_SUPPORT). Ties: first minimum (``d < best_d``).
    """
    from mechanistic_mind.research.prospective_composition import _frag_distance

    best = None
    best_d = 1e9
    for r in rows:
        d = _frag_distance(ant, r.get("antecedent") or {})
        if d < best_d:
            best_d = d
            best = r
    return best, best_d


def soft_match_packed_matrix(
    pa: dict[str, Any],
    ant: dict[str, float],
) -> tuple[dict[str, Any] | None, float] | None:
    """L1 over prebuilt ``pa['ante']`` in query-key summation order.

    Returns None when the query/schema gate fails (caller must use dict oracle).
    """
    mapped = _query_schema_columns(pa, ant)
    if mapped is None:
        return None
    cols, qvals = mapped
    m = len(qvals)
    n = int(pa.get("n") or 0)
    ante = pa.get("ante") or []
    rows = pa.get("rows") or []
    if n == 0 or len(ante) != n or len(rows) != n:
        return None, 1e9
    best = None
    best_d = 1e9
    for i in range(n):
        ai = ante[i]
        d = sum(abs(qvals[t] - ai[cols[t]]) for t in range(m)) / m
        if d < best_d:
            best_d = d
            best = rows[i]
    return best, best_d


def soft_match_packed_numpy(
    pa: dict[str, Any],
    ant: dict[str, float],
) -> tuple[dict[str, Any] | None, float] | None:
    """Vectorized L1 for microbench only. Not the production default."""
    import numpy as np

    mapped = _query_schema_columns(pa, ant)
    if mapped is None:
        return None
    cols, qvals = mapped
    m = len(qvals)
    n = int(pa.get("n") or 0)
    if n == 0:
        return None, 1e9
    mat = pa.get("_ante_np")
    need = np.asarray(pa.get("ante") or [], dtype=np.float64)
    if need.ndim != 2 or need.shape[0] != n:
        return None
    if mat is None or getattr(mat, "shape", None) != need.shape:
        pa["_ante_np"] = need
        mat = need
    perm = np.fromiter(cols, dtype=np.intp, count=m)
    qv = np.fromiter(qvals, dtype=np.float64, count=m)
    dist = np.abs(mat[:, perm] - qv).sum(axis=1) / float(m)
    idx = int(dist.argmin())
    return pa["rows"][idx], float(dist[idx])


def soft_match_packed(
    pack: dict[str, Any],
    ant: dict[str, float],
    action: str,
) -> tuple[dict[str, Any] | None, float]:
    """Action-partitioned packed soft match. Default: matrix L1 when exact.

    Falls back to the dict oracle when the query key set is not identical to the
    packed channel schema (union-denominator / missing-key semantics).
    """
    rows = (pack.get("by_action") or {}).get(action) or []
    if not rows:
        return None, 1e9
    mode = _PACKED_L1_MODE
    if mode == "dict":
        return soft_match_packed_dict(rows, ant)
    pa = (pack.get("packed_actions") or {}).get(action)
    if not isinstance(pa, dict) or int(pa.get("n") or 0) != len(rows):
        return soft_match_packed_dict(rows, ant)
    if mode == "numpy":
        hit = soft_match_packed_numpy(pa, ant)
    else:
        hit = soft_match_packed_matrix(pa, ant)
    if hit is None:
        return soft_match_packed_dict(rows, ant)
    return hit


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
