"""Update 4.27 - Predictive generalization to novel physical instances.

No CATEGORY/CLASS/CONCEPT/THREAT semantics. Shared predictive structure is a
generic conjunction/co-occurrence of physical feature bins -> consequence.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
from typing import Any

FORBIDDEN = (
    "CATEGORY", "CLASS", "TYPE", "KIND", "CONCEPT", "ANGRY", "HOSTILE", "SAFE",
    "DANGEROUS", "THREAT", "PERSON_TYPE", "OBJECT_TYPE", "SIMILAR_PERSON",
    "GENERALIZE", "ANALOGY", "STEREOTYPE", "PROTOTYPE", "EXEMPLAR_CLASS",
    "SEMANTIC_FEATURE", "SHARED_MEANING", "PREJUDICE", "BELIEF", "EXCEPTION",
)

MAX_STRUCTURES = 64
MAX_EXACT = 96
MIN_SUPPORT = 3
BINS = 5


def audit_forbidden(payload: Any) -> list[str]:
    text = str(payload)
    return [t for t in FORBIDDEN if t in text]


def _q(v: float, bins: int = BINS) -> int:
    return int(max(0.0, min(0.999999, float(v))) * bins)


def feature_sig(features: dict[str, float], keys: list[str] | None = None) -> str:
    keys = keys or sorted(features.keys())
    parts = [f"{k}:{_q(features.get(k, 0.0))}" for k in keys]
    return sha1("|".join(parts).encode()).hexdigest()[:14]


def pairwise_keys(features: dict[str, float]) -> list[tuple[str, str]]:
    ks = sorted(features.keys())
    out = []
    for i, a in enumerate(ks):
        for b in ks[i + 1:]:
            out.append((a, b))
    return out


def empty_store() -> dict[str, Any]:
    return {
        "exact": {},          # full config sig -> future stats
        "single": {},         # single feature bin -> future stats
        "pair": {},           # two-feature conjunction -> future stats
        "exposure_exact": {}, # config sig -> count
        "feature_counts": {},
        "ablate_shared": False,
        "ablate_exact": False,
        "metrics_affect_cognition": False,
    }


def _update_row(table: dict, key: str, future: dict[str, float]) -> None:
    row = table.get(key)
    if row is None:
        if len(table) >= MAX_STRUCTURES and table is not None:
            # forget lowest support
            if len(table) >= MAX_EXACT:
                victim = min(table.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
                del table[victim]
        row = {"sum": {k: 0.0 for k in future}, "n": 0, "support": 0, "key": key}
        table[key] = row
    for k, v in future.items():
        row["sum"][k] = float(row["sum"].get(k, 0.0)) + float(v)
    row["n"] = int(row["n"]) + 1
    row["support"] = int(row["support"]) + 1


def _mean(row: dict[str, Any] | None) -> dict[str, float] | None:
    if not row or int(row.get("n") or 0) <= 0:
        return None
    n = float(row["n"])
    return {k: float(v) / n for k, v in (row.get("sum") or {}).items()}


def observe(store: dict[str, Any], features: dict[str, float], future: dict[str, float]) -> None:
    """Learn from one physical instance -> consequence. No category labels."""
    full = feature_sig(features)
    store.setdefault("exposure_exact", {})[full] = int(store["exposure_exact"].get(full, 0)) + 1
    for k, v in features.items():
        bk = f"{k}:{_q(v)}"
        store.setdefault("feature_counts", {})[bk] = int(store["feature_counts"].get(bk, 0)) + 1

    if not store.get("ablate_exact"):
        exact = store.setdefault("exact", {})
        if len(exact) >= MAX_EXACT and full not in exact:
            victim = min(exact.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
            del exact[victim]
        _update_row(exact, full, future)

    # singles
    single = store.setdefault("single", {})
    for k, v in features.items():
        _update_row(single, f"{k}:{_q(v)}", future)

    # pairs = shared structure candidates (conjunction of physical bins)
    if not store.get("ablate_shared"):
        pair = store.setdefault("pair", {})
        if len(pair) >= MAX_STRUCTURES:
            # prune later on insert
            pass
        for a, b in pairwise_keys(features):
            key = f"{a}:{_q(features[a])}|{b}:{_q(features[b])}"
            if key not in pair and len(pair) >= MAX_STRUCTURES:
                victim = min(pair.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
                del pair[victim]
            _update_row(pair, key, future)


def predict(store: dict[str, Any], features: dict[str, float]) -> dict[str, Any]:
    """Predict future for an instance. Prefer exact, else best supported pair, else single."""
    full = feature_sig(features)
    exact_row = None if store.get("ablate_exact") else (store.get("exact") or {}).get(full)
    if exact_row and int(exact_row.get("support") or 0) >= MIN_SUPPORT:
        return {
            "status": "EXACT",
            "source": "exact",
            "key": full,
            "support": exact_row["support"],
            "predicted": _mean(exact_row),
            "contributions": {"exact": 1.0, "pair": 0.0, "single": 0.0},
        }

    # shared pair structures
    best_pair = None
    best_sup = 0
    if not store.get("ablate_shared"):
        for a, b in pairwise_keys(features):
            key = f"{a}:{_q(features[a])}|{b}:{_q(features[b])}"
            row = (store.get("pair") or {}).get(key)
            if row and int(row.get("support") or 0) > best_sup:
                best_sup = int(row["support"])
                best_pair = (key, row)

    best_single = None
    best_ss = 0
    for k, v in features.items():
        key = f"{k}:{_q(v)}"
        row = (store.get("single") or {}).get(key)
        if row and int(row.get("support") or 0) > best_ss:
            best_ss = int(row["support"])
            best_single = (key, row)

    if best_pair and best_sup >= MIN_SUPPORT:
        # Require pair support to beat best single (conjunction not reducible to one feature)
        pair_pred = _mean(best_pair[1])
        single_pred = _mean(best_single[1]) if best_single else None
        return {
            "status": "SHARED",
            "source": "pair",
            "key": best_pair[0],
            "support": best_sup,
            "predicted": pair_pred,
            "single_support": best_ss,
            "single_predicted": single_pred,
            "contributions": {
                "exact": 0.0,
                "pair": 1.0,
                "single": float(best_ss) / float(best_sup + best_ss) if (best_sup + best_ss) else 0.0,
            },
        }

    if best_single and best_ss >= MIN_SUPPORT:
        return {
            "status": "SINGLE",
            "source": "single",
            "key": best_single[0],
            "support": best_ss,
            "predicted": _mean(best_single[1]),
            "contributions": {"exact": 0.0, "pair": 0.0, "single": 1.0},
        }

    return {"status": "NO_MATCH", "source": None, "predicted": None, "contributions": {"exact": 0.0, "pair": 0.0, "single": 0.0}}


def l1(a: dict[str, float] | None, b: dict[str, float] | None) -> float | None:
    if not a or not b:
        return None
    keys = set(a) | set(b)
    return sum(abs(float(a.get(k, 0.0)) - float(b.get(k, 0.0))) for k in keys)


def shared_structure_snapshot(store: dict[str, Any]) -> dict[str, Any]:
    pairs = store.get("pair") or {}
    strong = [r for r in pairs.values() if int(r.get("support") or 0) >= MIN_SUPPORT]
    return {
        "shared_structure_count": len(strong),
        "shared_structure_total": len(pairs),
        "exact_count": len(store.get("exact") or {}),
        "single_count": len(store.get("single") or {}),
        "top_pairs": sorted(
            [{"key": r["key"], "support": r["support"], "mean": _mean(r)} for r in strong],
            key=lambda x: -int(x["support"]),
        )[:8],
        "ablations": {"shared": bool(store.get("ablate_shared")), "exact": bool(store.get("ablate_exact"))},
        "leak_tokens": audit_forbidden({"pairs": list(pairs.keys())[:20]}),
    }


# Physical instance builders (Observer may label I1/I_NEW; cognition gets features only)
def F_MINUS() -> dict[str, float]:
    return {"energy_signal": 0.18, "fatigue_signal": 0.55, "hydration_signal": 0.60, "discomfort_signal": 0.22}


def F_PLUS() -> dict[str, float]:
    return {"energy_signal": 0.75, "fatigue_signal": 0.15, "hydration_signal": 0.72, "discomfort_signal": 0.04}


def F_OTHER() -> dict[str, float]:
    return {"energy_signal": 0.55, "fatigue_signal": 0.25, "hydration_signal": 0.65, "discomfort_signal": 0.08}


def instance(a: float, b: float, **extra) -> dict[str, float]:
    d = {"a": float(a), "b": float(b)}
    d.update({k: float(v) for k, v in extra.items()})
    return d
