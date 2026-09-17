"""Update 4.19 — Background co-occurrence, compression, prediction, mismatch.

Measurement + bounded experience structures only. No semantic context labels,
curiosity, surprise reward, or WORLD_CHANGED signals.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha1
from typing import Any


QUANT_BINS = 5
MAX_PATTERNS = 64
MAX_SUPPORT_SAMPLES = 32
MIN_SUPPORT = 3
PARTIAL_MASK_KEEP = 4  # keep first K components as evidence; predict the rest


def _quantize(value: float, bins: int = QUANT_BINS) -> int:
    v = max(0.0, min(0.999999, float(value)))
    return int(v * bins)


def sensory_signature(fragment: dict[str, float], *, bins: int = QUANT_BINS) -> str:
    items = sorted((str(k), _quantize(v, bins)) for k, v in fragment.items())
    raw = "|".join(f"{k}:{q}" for k, q in items)
    return sha1(raw.encode("utf-8")).hexdigest()[:16]


def partial_signature(
    fragment: dict[str, float],
    *,
    keep_keys: list[str],
    bins: int = QUANT_BINS,
) -> str:
    items = sorted((k, _quantize(fragment.get(k, 0.0), bins)) for k in keep_keys)
    raw = "|".join(f"{k}:{q}" for k, q in items)
    return "P:" + sha1(raw.encode("utf-8")).hexdigest()[:14]


def empty_store(*, capacity: int = MAX_PATTERNS) -> dict[str, Any]:
    return {
        "patterns": {},  # signature -> stats
        "partial_index": {},  # partial_sig -> {full_sig: count}
        "capacity": int(capacity),
        "total_observations": 0,
        "compressions": 0,
        "prediction_events": 0,
        "mismatch_events": 0,
        "last_prediction": None,
        "last_mismatch": None,
        "evidence": {
            "support": 0,
            "consistency": 0.0,
            "conflict": 0.0,
            "quality": 0.0,
        },
        "ablate_compression": False,
        "ablate_prediction": False,
    }


def ingest_fragment(store: dict[str, Any], fragment: dict[str, float], *, tick: int) -> dict[str, Any]:
    """Update bounded co-occurrence structures from a local sensory fragment."""
    if not fragment:
        return {"status": "EMPTY"}
    store["total_observations"] = int(store.get("total_observations") or 0) + 1
    keys = sorted(fragment.keys())
    if store.get("ablate_compression"):
        # Raw-only path: keep a tiny ring of recent signatures, no partial index.
        recent = store.setdefault("raw_recent", [])
        sig = sensory_signature(fragment)
        recent.append({"tick": tick, "signature": sig, "fragment": dict(fragment)})
        store["raw_recent"] = recent[-MAX_SUPPORT_SAMPLES:]
        return {"status": "RAW_ONLY", "signature": sig}

    sig = sensory_signature(fragment)
    patterns = store.setdefault("patterns", {})
    row = patterns.get(sig)
    if row is None:
        if len(patterns) >= int(store.get("capacity") or MAX_PATTERNS):
            # Drop lowest-support pattern.
            victim = min(patterns.items(), key=lambda kv: (kv[1].get("support", 0), kv[0]))[0]
            patterns.pop(victim, None)
            # scrub partial index entries
            for pmap in store.get("partial_index", {}).values():
                if isinstance(pmap, dict):
                    pmap.pop(victim, None)
            store["compressions"] = int(store.get("compressions") or 0) + 1
        row = {
            "signature": sig,
            "support": 0,
            "mean": {k: 0.0 for k in keys},
            "keys": keys,
            "first_tick": tick,
            "last_tick": tick,
        }
        patterns[sig] = row
    row["support"] = int(row.get("support") or 0) + 1
    row["last_tick"] = tick
    mean = row.setdefault("mean", {})
    support = float(row["support"])
    for k, v in fragment.items():
        prev = float(mean.get(k, 0.0))
        mean[k] = prev + (float(v) - prev) / support

    # Partial co-occurrence index for background prediction.
    keep = keys[:PARTIAL_MASK_KEEP] if len(keys) > PARTIAL_MASK_KEEP else keys[:-1] or keys
    if keep and not store.get("ablate_prediction"):
        psig = partial_signature(fragment, keep_keys=keep)
        pmap = store.setdefault("partial_index", {}).setdefault(psig, {})
        pmap[sig] = int(pmap.get(sig) or 0) + 1
        # bound fan-out
        if len(pmap) > 8:
            drop = sorted(pmap.items(), key=lambda kv: kv[1])[0][0]
            pmap.pop(drop, None)

    return {"status": "INGESTED", "signature": sig, "support": row["support"]}


def predict_from_partial(store: dict[str, Any], fragment: dict[str, float]) -> dict[str, Any]:
    """Predict held-out components from partial sensory evidence."""
    if store.get("ablate_prediction") or not fragment:
        return {"status": "DISABLED_OR_EMPTY"}
    keys = sorted(fragment.keys())
    keep = keys[:PARTIAL_MASK_KEEP] if len(keys) > PARTIAL_MASK_KEEP else keys[:-1] or keys
    held_out = [k for k in keys if k not in keep]
    if not held_out:
        return {"status": "NO_HELD_OUT"}
    psig = partial_signature(fragment, keep_keys=keep)
    pmap = (store.get("partial_index") or {}).get(psig) or {}
    if not pmap:
        evidence = {"support": 0, "consistency": 0.0, "conflict": 0.0, "quality": 0.0}
        store["evidence"] = evidence
        return {"status": "NO_MATCH", "partial_signature": psig, "held_out": held_out, "evidence": evidence}

    # Retrieve top supporting full pattern(s).
    ranked = sorted(pmap.items(), key=lambda kv: (-kv[1], kv[0]))
    patterns = store.get("patterns") or {}
    top_sig, top_count = ranked[0]
    top = patterns.get(top_sig) or {}
    predicted = {k: float((top.get("mean") or {}).get(k, 0.0)) for k in held_out}
    realized = {k: float(fragment.get(k, 0.0)) for k in held_out}
    errors = {k: realized[k] - predicted[k] for k in held_out}
    abs_l1 = sum(abs(v) for v in errors.values())
    conflict = 0.0
    if len(ranked) > 1:
        alt_sig = ranked[1][0]
        alt = patterns.get(alt_sig) or {}
        alt_pred = {k: float((alt.get("mean") or {}).get(k, 0.0)) for k in held_out}
        conflict = sum(abs(predicted[k] - alt_pred[k]) for k in held_out) / max(1, len(held_out))
    support = int(top.get("support") or top_count)
    consistency = max(0.0, 1.0 - min(1.0, abs_l1 / max(1e-9, 0.25 * len(held_out))))
    quality = consistency * min(1.0, support / float(MIN_SUPPORT + 2)) * (1.0 - 0.5 * min(1.0, conflict))
    if support < MIN_SUPPORT:
        quality = 0.0
    mismatch = abs_l1 > 0.12
    evidence = {
        "support": support,
        "consistency": round(consistency, 5),
        "conflict": round(conflict, 5),
        "quality": round(quality, 5),
        "competing_patterns": len(ranked),
    }
    store["evidence"] = evidence
    store["prediction_events"] = int(store.get("prediction_events") or 0) + 1
    result = {
        "status": "PREDICTED",
        "partial_signature": psig,
        "retrieved_signature": top_sig,
        "held_out": held_out,
        "predicted": predicted,
        "realized": realized,
        "errors": errors,
        "abs_l1": round(abs_l1, 5),
        "mismatch": mismatch,
        "evidence": evidence,
    }
    store["last_prediction"] = result
    if mismatch:
        store["mismatch_events"] = int(store.get("mismatch_events") or 0) + 1
        store["last_mismatch"] = {"tick_ref": store.get("total_observations"), **result}
    return result


def evidence_quality(store: dict[str, Any]) -> dict[str, float]:
    ev = store.get("evidence") or {}
    return {
        "support": float(ev.get("support") or 0.0),
        "consistency": float(ev.get("consistency") or 0.0),
        "conflict": float(ev.get("conflict") or 0.0),
        "quality": float(ev.get("quality") or 0.0),
    }


def store_snapshot(store: dict[str, Any]) -> dict[str, Any]:
    patterns = store.get("patterns") or {}
    return {
        "pattern_count": len(patterns),
        "total_observations": store.get("total_observations"),
        "compressions": store.get("compressions"),
        "prediction_events": store.get("prediction_events"),
        "mismatch_events": store.get("mismatch_events"),
        "evidence": evidence_quality(store),
        "top_patterns": sorted(
            (
                {
                    "signature": sig,
                    "support": row.get("support"),
                    "last_tick": row.get("last_tick"),
                }
                for sig, row in patterns.items()
            ),
            key=lambda r: (-int(r.get("support") or 0), str(r.get("signature"))),
        )[:8],
        "last_prediction": store.get("last_prediction"),
        "ablate_compression": bool(store.get("ablate_compression")),
        "ablate_prediction": bool(store.get("ablate_prediction")),
    }
