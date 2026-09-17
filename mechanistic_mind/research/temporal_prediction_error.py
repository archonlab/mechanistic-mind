"""Experimental bridge: ordinary prediction residuals into existing TPS.

Default OFF. Residual fragment is realized − predicted on predicted channels.
Does not detect DRIFT, invalidate relations, select actions, accumulate an
authored score, or know whether a signed residual is desirable.

Lag-1 and lag-4 residuals occupy separate TPS rings so they are not mixed.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research.predictive_equivalence import _floats
from mechanistic_mind.research import temporal_predictive_structure as tps

MAX_PENDING = 16
MAX_RECEIPTS = 24
MAX_PROV = 12
TAU = pe.CONTINUATION_LINF


def empty_store() -> dict[str, Any]:
    return {
        "enabled": False,
        "pending": [],
        "receipts": [],
        "lags": {},
        "ingests": 0,
        "skipped_shared_ancestry": 0,
        "tau": TAU,
        "note": "TEMPORAL_PREDICTION_ERROR — residual fragments, not drift detection",
    }


def _lag_tps(store: dict[str, Any], lag: int) -> dict[str, Any]:
    lags = store.setdefault("lags", {})
    key = str(max(1, int(lag or 1)))
    inner = lags.get(key)
    if not isinstance(inner, dict):
        inner = tps.empty_store()
        lags[key] = inner
    inner["enabled"] = True
    return inner


def residual_fragment(
    predicted: dict[str, Any] | None,
    realized: dict[str, Any] | None,
    *,
    relevant_keys: list[str] | None = None,
) -> dict[str, float]:
    pred = _floats(predicted)
    if relevant_keys:
        pred = {k: pred[k] for k in relevant_keys if k in pred} or pred
    if not pred:
        return {}
    real = _floats(realized)
    return {k: float(real.get(k, 0.0)) - float(v) for k, v in pred.items()}


def remember(
    store: dict[str, Any],
    *,
    action: str,
    predicted: dict[str, float] | None,
    tick: int,
    lag: int = 1,
    key: str | None = None,
    source: str = "SNAPSHOT",
    ancestry: list[str] | None = None,
) -> None:
    """Book an issued prediction. Residual exists only after tick+lag."""
    if store.get("enabled") is False:
        return
    pred = _floats(predicted)
    if not pred:
        return
    lag_i = max(1, int(lag or 1))
    evaluate_at = int(tick) + lag_i
    pending = store.setdefault("pending", [])
    k = str(key or f"{action}|{source}|{evaluate_at}")
    for p in pending:
        if p.get("key") == k and int(p.get("evaluate_at") or 0) == evaluate_at:
            return
    pending.append({
        "key": k,
        "action": str(action),
        "predicted": pred,
        "issued_at": int(tick),
        "lag": lag_i,
        "evaluate_at": evaluate_at,
        "source": str(source or "SNAPSHOT"),
        "ancestry": [str(x) for x in (ancestry or []) if x][:MAX_PROV],
    })
    store["pending"] = pending[-MAX_PENDING:]


def ingest(
    store: dict[str, Any],
    *,
    observation: dict[str, float],
    tick: int,
    last_action: str | None,
    relevant_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Score due predictions into residual fragments and feed existing TPS."""
    if store.get("enabled") is False:
        return {"status": "DISABLED", "receipts": []}
    store["ingests"] = int(store.get("ingests") or 0) + 1
    real = _floats(observation)
    pending = list(store.get("pending") or [])
    keep = []
    receipts = []
    seen_keys: set[str] = set()
    seen_anc: set[str] = set()
    for p in pending:
        if int(p.get("evaluate_at") or 0) > int(tick):
            keep.append(p)
            continue
        if last_action and str(p.get("action") or "") != str(last_action):
            keep.append(p)
            continue
        key = str(p.get("key") or "")
        anc = set(p.get("ancestry") or [])
        if key in seen_keys or (anc and anc & seen_anc):
            store["skipped_shared_ancestry"] = int(store.get("skipped_shared_ancestry") or 0) + 1
            continue
        seen_keys.add(key)
        seen_anc |= anc
        pred = dict(p.get("predicted") or {})
        frag = residual_fragment(pred, real, relevant_keys=relevant_keys)
        if not frag:
            continue
        lag_i = int(p.get("lag") or 1)
        inner = _lag_tps(store, lag_i)
        learned = tps.learn(
            inner,
            consequent=frag,
            action=str(p.get("action") or last_action or "WAIT"),
            tick=int(tick),
            raw_id=key,
        )
        tps.append(inner, frag)
        abs_linf = max(abs(v) for v in frag.values()) if frag else 0.0
        tau = float(store.get("tau") or TAU)
        receipts.append({
            "key": key,
            "action": p.get("action"),
            "lag": lag_i,
            "predicted": pred,
            "realized": {k: real.get(k) for k in pred},
            "residual": frag,
            "abs_linf": abs_linf,
            "formal_mismatch": bool(abs_linf > tau),
            "learn": learned.get("status"),
            "source": p.get("source"),
            "not_drift_label": True,
            "not_punishment": True,
        })
    store["pending"] = keep[-MAX_PENDING:]
    recs = store.setdefault("receipts", [])
    recs.extend(receipts)
    store["receipts"] = recs[-MAX_RECEIPTS:]
    return {"status": "INGESTED" if receipts else "NONE", "receipts": receipts}


def retrieve(
    store: dict[str, Any],
    residual: dict[str, float],
    action: str,
    *,
    lag: int = 1,
    source_lag: int = 1,
) -> dict[str, Any]:
    """TPS retrieve on residual fragments. Does not decide drift."""
    if store.get("enabled") is False:
        return {"status": "DISABLED", "predicted": {}}
    inner = _lag_tps(store, source_lag)
    if not inner.get("ring"):
        return {"status": "NO_MATCH", "predicted": {}, "gate": "empty_residual_ring"}
    return tps.retrieve(inner, residual, action, lag=int(lag))


def recent_residuals(store: dict[str, Any], *, source_lag: int = 1, n: int = 8) -> list[dict[str, float]]:
    inner = (store.get("lags") or {}).get(str(max(1, int(source_lag))))
    if not isinstance(inner, dict):
        return []
    return deepcopy((inner.get("ring") or [])[-n:])


def pending_from_selection(
    store: dict[str, Any],
    *,
    selected: str,
    continuations: list[dict[str, Any]],
    tick: int,
    predictions: list[dict[str, Any]] | None = None,
    entry_steps: list[dict[str, Any]] | None = None,
) -> None:
    if store.get("enabled") is False:
        return
    for c in continuations or []:
        acts = list(c.get("actions") or [])
        if not acts or str(acts[0]) != str(selected):
            continue
        root = (c.get("edges") or [{}])[0] or {}
        states = list(c.get("states") or [])
        pred = states[1] if len(states) >= 2 else root.get("predicted")
        anc = []
        for x in (root.get("transition_id"), root.get("key"), root.get("temporal_structure_id"),
                  (root.get("provenance") or {}).get("class_id") if isinstance(root.get("provenance"), dict) else None):
            if x:
                anc.append(str(x))
        remember(
            store,
            action=selected,
            predicted=pred,
            tick=tick,
            lag=int(root.get("lag") or 1),
            key=root.get("key") or root.get("transition_id"),
            source=str(root.get("prediction_source") or c.get("prediction_source") or "SNAPSHOT"),
            ancestry=anc,
        )
        return
    for step in entry_steps or []:
        if str(step.get("action") or "") != str(selected):
            continue
        remember(
            store,
            action=selected,
            predicted=step.get("predicted"),
            tick=tick,
            lag=int(step.get("lag") or 1),
            key=step.get("key") or step.get("transition_id"),
            source=str(step.get("prediction_source") or "TEMPORAL"),
            ancestry=[str(x) for x in (step.get("temporal_structure_id"), step.get("key")) if x],
        )
        return
    for row in predictions or []:
        if str(row.get("action") or "") != str(selected):
            continue
        res = row.get("result") or {}
        if res.get("status") != "MATCH":
            continue
        remember(
            store,
            action=selected,
            predicted=res.get("predicted") or res.get("predicted_continuation") or res.get("mean_predicted"),
            tick=tick,
            lag=int(res.get("lag") or 1),
            key=res.get("key") or res.get("class_id") or res.get("structure_id"),
            source=str(row.get("source") or "compression"),
            ancestry=[str(x) for x in (res.get("class_id"), res.get("structure_id"), res.get("key")) if x],
        )
        return


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    lags = store.get("lags") or {}
    return {
        "enabled": bool(store.get("enabled")),
        "n_pending": len(store.get("pending") or []),
        "n_receipts": len(store.get("receipts") or []),
        "ingests": store.get("ingests"),
        "skipped_shared_ancestry": store.get("skipped_shared_ancestry"),
        "lag_rings": {k: len((v or {}).get("ring") or []) for k, v in lags.items()},
        "note": "Observer labels only — not cognitive semantics",
    }


def observer_panel(
    store: dict[str, Any],
    *,
    predicted=None,
    realized=None,
    residual=None,
    retrieved=None,
    eligible=None,
    competition=None,
    selected=None,
) -> dict[str, Any]:
    last = (store.get("receipts") or [{}])[-1] if store.get("receipts") else {}
    got = retrieved or {}
    cont = got.get("predicted_continuation") or got.get("predicted") or {}
    return {
        "kind": "PREDICTION_ERROR_TRAJECTORY",
        "predicted": deepcopy(predicted if predicted is not None else last.get("predicted") or {}),
        "realized": deepcopy(realized if realized is not None else last.get("realized") or {}),
        "residual": deepcopy(residual if residual is not None else last.get("residual") or {}),
        "recent_residuals": recent_residuals(store, n=8),
        "temporal_match": got.get("status"),
        "predicted_continuation": deepcopy(cont),
        "formal_mismatch": last.get("formal_mismatch"),
        "relation_eligible": eligible,
        "competition": deepcopy(competition or {}),
        "selected": selected,
        "not_drift_label": True,
        "not_surprise": True,
    }


def diagnostic(store: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return {
        "kind": "TEMPORAL_PREDICTION_ERROR",
        "not_drift_detector": True,
        "not_reward": True,
        "not_policy": True,
        **snapshot(store),
        "panel": observer_panel(store, **kwargs),
    }


def memory_usage(store: dict[str, Any]) -> dict[str, Any]:
    lags = store.get("lags") or {}
    inner_mem = {k: tps.memory_usage(v) for k, v in lags.items() if isinstance(v, dict)}
    return {
        "pending": len(store.get("pending") or []),
        "receipts": len(store.get("receipts") or []),
        "pending_cap": MAX_PENDING,
        "receipts_cap": MAX_RECEIPTS,
        "lags": inner_mem,
        "bounded": (
            len(store.get("pending") or []) <= MAX_PENDING
            and len(store.get("receipts") or []) <= MAX_RECEIPTS
            and all(m.get("bounded") for m in inner_mem.values())
        ),
    }
