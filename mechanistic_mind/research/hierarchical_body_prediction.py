"""Update 4.20 — Multi-scale / hierarchical predictive evidence (label-free).

Does not create LEVEL_1/2/3 cognitive objects. Observer may analyze hierarchy.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha1
from typing import Any


MAX_LOCAL = 96
MAX_RELATIONS = 48
MIN_SUPPORT = 3


def _q(v: float, bins: int = 5) -> int:
    return int(max(0.0, min(0.999999, float(v))) * bins)


def state_sig(fragment: dict[str, float]) -> str:
    items = sorted((str(k), _q(v)) for k, v in fragment.items())
    return sha1("|".join(f"{k}:{q}" for k, q in items).encode()).hexdigest()[:14]


def empty_store() -> dict[str, Any]:
    return {
        "local": {},          # (state_sig, action, lag) -> stats
        "relations": {},      # (ctx_sig, local_key) -> stats  [higher-order candidate]
        "recent": [],         # bounded ring of {tick, sig, action, fragment}
        "horizons": (1, 3, 8, 20),
        "total": 0,
        "ablate_chaining": False,
        "ablate_compression": False,
        "ablate_long_horizon": False,
        "ablate_action_contingent": False,
        "pre_signal_events": 0,
        "deeper_hits": 0,
        "local_only_hits": 0,
    }


def ingest(
    store: dict[str, Any],
    *,
    tick: int,
    fragment: dict[str, float],
    action: str,
    realized_next: dict[str, float] | None = None,
    ctx_fragment: dict[str, float] | None = None,
) -> None:
    store["total"] = int(store.get("total") or 0) + 1
    sig = state_sig(fragment)
    recent = store.setdefault("recent", [])
    recent.append({"tick": tick, "sig": sig, "action": action, "fragment": dict(fragment),
                   "ctx": dict(ctx_fragment or {})})
    store["recent"] = recent[-64:]

    if store.get("ablate_compression"):
        return

    # Update pending local predictions when realized_next provided for lag matches
    if realized_next is not None:
        for lag in (store.get("horizons") or (1, 3, 8, 20)):
            if store.get("ablate_long_horizon") and int(lag) > 3:
                continue
            # find entry lag ticks ago with same... we match by position in recent
            if len(recent) <= lag:
                continue
            past = recent[-(lag + 1)]
            key = f"{past['sig']}||{past['action']}||L{lag}"
            if store.get("ablate_action_contingent") and past["action"] != "WAIT":
                # only allow WAIT associations under this ablation
                continue
            row = store.setdefault("local", {}).get(key)
            if row is None:
                if len(store["local"]) >= MAX_LOCAL:
                    victim = min(store["local"].items(), key=lambda kv: kv[1].get("support", 0))[0]
                    store["local"].pop(victim, None)
                row = {"key": key, "support": 0, "mean_delta": {}, "lag": lag, "action": past["action"], "sig": past["sig"]}
                store["local"][key] = row
            row["support"] = int(row["support"]) + 1
            mean = row.setdefault("mean_delta", {})
            for k, v in realized_next.items():
                d = float(v) - float((past.get("fragment") or {}).get(k, v))
                prev = float(mean.get(k, 0.0))
                mean[k] = prev + (d - prev) / float(row["support"])

            # relation: ctx -> relevance of this local key
            if not store.get("ablate_chaining") and past.get("ctx"):
                csig = state_sig(past["ctx"])
                rkey = f"{csig}=>{key}"
                rel = store.setdefault("relations", {}).get(rkey)
                if rel is None:
                    if len(store["relations"]) >= MAX_RELATIONS:
                        victim = min(store["relations"].items(), key=lambda kv: kv[1].get("support", 0))[0]
                        store["relations"].pop(victim, None)
                    rel = {"support": 0, "ctx": csig, "local_key": key}
                    store["relations"][rkey] = rel
                rel["support"] = int(rel["support"]) + 1


def predict_local(store: dict[str, Any], fragment: dict[str, float], action: str, lag: int) -> dict[str, Any]:
    sig = state_sig(fragment)
    key = f"{sig}||{action}||L{lag}"
    row = (store.get("local") or {}).get(key)
    if not row or int(row.get("support") or 0) < MIN_SUPPORT:
        return {"status": "NO_LOCAL", "key": key, "support": int((row or {}).get("support") or 0)}
    return {"status": "LOCAL", "key": key, "support": row["support"], "mean_delta": dict(row.get("mean_delta") or {}), "lag": lag}


def predict_with_context(
    store: dict[str, Any],
    fragment: dict[str, float],
    action: str,
    lag: int,
    ctx_fragment: dict[str, float] | None,
) -> dict[str, Any]:
    """Compare local-only vs context-conditioned candidate (deeper if adds power)."""
    local = predict_local(store, fragment, action, lag)
    if store.get("ablate_chaining") or not ctx_fragment:
        return {**local, "deeper": False, "mode": "LOCAL_ONLY"}
    csig = state_sig(ctx_fragment)
    # find relations that point to any local key with this action/lag and matching ctx
    candidates = []
    for rkey, rel in (store.get("relations") or {}).items():
        if rel.get("ctx") != csig:
            continue
        if int(rel.get("support") or 0) < MIN_SUPPORT:
            continue
        lkey = rel.get("local_key")
        row = (store.get("local") or {}).get(lkey)
        if not row:
            continue
        if row.get("action") != action or int(row.get("lag") or -1) != int(lag):
            continue
        candidates.append((int(rel["support"]), row, rel))
    if not candidates:
        store["local_only_hits"] = int(store.get("local_only_hits") or 0) + 1
        return {**local, "deeper": False, "mode": "NO_RELATION"}
    candidates.sort(key=lambda x: -x[0])
    _, row, rel = candidates[0]
    deeper = local.get("status") != "LOCAL" or abs(
        sum(abs(float(v)) for v in (row.get("mean_delta") or {}).values())
        - sum(abs(float(v)) for v in (local.get("mean_delta") or {}).values())
    ) > 1e-6
    if deeper and local.get("status") != "LOCAL":
        store["deeper_hits"] = int(store.get("deeper_hits") or 0) + 1
    return {
        "status": "CONTEXTUAL",
        "deeper": bool(deeper or local.get("status") != "LOCAL"),
        "mode": "RELATION",
        "support": row.get("support"),
        "relation_support": rel.get("support"),
        "mean_delta": dict(row.get("mean_delta") or {}),
        "local": local,
        "lag": lag,
    }


def action_contingency_stats(store: dict[str, Any]) -> dict[str, Any]:
    """Observer metric: support mass for action vs WAIT associations."""
    by_action = defaultdict(int)
    for row in (store.get("local") or {}).values():
        by_action[str(row.get("action"))] += int(row.get("support") or 0)
    total = sum(by_action.values()) or 1
    return {
        "by_action": dict(by_action),
        "action_share": {k: round(v / total, 4) for k, v in by_action.items()},
        "wait_share": round(by_action.get("WAIT", 0) / total, 4),
    }


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    return {
        "local_count": len(store.get("local") or {}),
        "relation_count": len(store.get("relations") or {}),
        "total": store.get("total"),
        "deeper_hits": store.get("deeper_hits"),
        "local_only_hits": store.get("local_only_hits"),
        "pre_signal_events": store.get("pre_signal_events"),
        "action_contingency": action_contingency_stats(store),
        "ablations": {
            "chaining": bool(store.get("ablate_chaining")),
            "compression": bool(store.get("ablate_compression")),
            "long_horizon": bool(store.get("ablate_long_horizon")),
            "action_contingent": bool(store.get("ablate_action_contingent")),
        },
        "top_local": sorted(
            (
                {"key": k, "support": v.get("support"), "lag": v.get("lag"), "action": v.get("action")}
                for k, v in (store.get("local") or {}).items()
            ),
            key=lambda r: (-int(r.get("support") or 0), str(r.get("key"))),
        )[:8],
        "top_relations": sorted(
            (
                {"ctx": v.get("ctx"), "local_key": v.get("local_key"), "support": v.get("support")}
                for v in (store.get("relations") or {}).values()
            ),
            key=lambda r: (-int(r.get("support") or 0), str(r.get("local_key"))),
        )[:8],
    }
