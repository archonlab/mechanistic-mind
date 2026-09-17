"""Experimental prediction-error revision of predictive influence.

Default OFF. Connects an issued prediction to a later ordinary observation.
Revises whether that relation is currently MATCH-eligible. Does not rewrite
historical occurrence counts, assign reward/punishment, or select actions.

Invalidation reuses 4.21's existing evidence gate on the *predicting*
relation (not the realized-consequent row):
  consecutive_mismatch < 3 or consecutive * 2 < historical_matches → still active
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research.predictive_equivalence import _floats
from mechanistic_mind.research import prospective_composition as pr

MAX_PENDING = 16
MAX_RELATIONS = 64
MAX_RECEIPTS = 24
MAX_PROV = 12


def empty_store() -> dict[str, Any]:
    return {
        "enabled": False,
        "pending": [],
        "relations": {},
        "receipts": [],
        "realizes": 0,
        "mismatches": 0,
        "matches": 0,
        "invalidations": 0,
        "recoveries": 0,
        "tau": pe.CONTINUATION_LINF,
        "note": "PREDICTION_ERROR_REVISION — not punishment, not trust, not policy",
    }


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    rels = list((store.get("relations") or {}).values())
    return {
        "enabled": bool(store.get("enabled")),
        "n_relations": len(rels),
        "n_pending": len(store.get("pending") or []),
        "n_inactive": sum(1 for r in rels if not r.get("active", True)),
        "realizes": store.get("realizes"),
        "mismatches": store.get("mismatches"),
        "matches": store.get("matches"),
        "invalidations": store.get("invalidations"),
        "recoveries": store.get("recoveries"),
        "note": "Observer labels only — not cognitive semantics",
    }


def _projected_linf(pred: dict[str, float], realized: dict[str, float]) -> float | None:
    pred_f = _floats(pred)
    if not pred_f:
        return None
    real = _floats(realized)
    return max(abs(float(pred_f[k]) - float(real.get(k, 0.0))) for k in pred_f)


def _still_predictive(historical_matches: int, consecutive: int) -> bool:
    """4.21 _maybe_revise gate, applied to the predicting relation."""
    if int(consecutive) < 3:
        return True
    if int(consecutive) * 2 < max(int(historical_matches), 1):
        return True
    return False


def _relation(store: dict[str, Any], key: str) -> dict[str, Any]:
    rels = store.setdefault("relations", {})
    if key not in rels:
        if len(rels) >= MAX_RELATIONS:
            # forget oldest inactive, else oldest
            victim = min(
                rels.items(),
                key=lambda kv: (1 if kv[1].get("active", True) else 0, int(kv[1].get("last_tick") or 0)),
            )[0]
            rels.pop(victim, None)
        rels[key] = {
            "key": key,
            "historical_matches": 0,
            "mismatches": 0,
            "consecutive_mismatch": 0,
            "active": True,
            "last_tick": 0,
            "ancestry": [],
            "source": None,
            "action": None,
            "last_abs_linf": None,
            "last_predicted": None,
            "last_lag": 1,
        }
    return rels[key]


def remember(
    store: dict[str, Any],
    *,
    action: str,
    predicted: dict[str, float] | None,
    key: str | None,
    tick: int,
    lag: int = 1,
    source: str = "SNAPSHOT",
    historical_support: int = 0,
    ancestry: list[str] | None = None,
) -> None:
    """Bookkeeping of an issued prediction. Evaluated at tick+lag. Not a clock in cognition."""
    if store.get("enabled") is False:
        return
    pred = _floats(predicted)
    if not pred or not key:
        return
    lag_i = max(1, int(lag or 1))
    pending = store.setdefault("pending", [])
    ancestry_l = [str(x) for x in (ancestry or []) if x][:MAX_PROV]
    # Dedup same key+evaluate_tick (overlapping predictions of the same relation).
    evaluate_at = int(tick) + lag_i
    for p in pending:
        if p.get("key") == key and int(p.get("evaluate_at") or 0) == evaluate_at:
            return
    pending.append({
        "key": str(key),
        "action": str(action),
        "predicted": pred,
        "issued_at": int(tick),
        "lag": lag_i,
        "evaluate_at": evaluate_at,
        "source": str(source or "SNAPSHOT"),
        "historical_support": int(historical_support or 0),
        "ancestry": ancestry_l,
    })
    store["pending"] = pending[-MAX_PENDING:]
    rel = _relation(store, str(key))
    rel["action"] = str(action)
    rel["source"] = str(source or "SNAPSHOT")
    rel["last_predicted"] = pred
    rel["last_lag"] = lag_i
    if int(historical_support or 0) > int(rel.get("historical_matches") or 0):
        rel["historical_matches"] = int(historical_support)
    for a in ancestry_l:
        if a not in rel["ancestry"]:
            rel["ancestry"] = (rel.get("ancestry") or [])[-MAX_PROV:] + [a]
            rel["ancestry"] = rel["ancestry"][-MAX_PROV:]


def realize(
    store: dict[str, Any],
    *,
    observation: dict[str, float],
    tick: int,
    last_action: str | None,
    relevant_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Score pending predictions whose lag has elapsed against ordinary observation."""
    if store.get("enabled") is False:
        return {"status": "DISABLED", "receipts": []}
    store["realizes"] = int(store.get("realizes") or 0) + 1
    tau = float(store.get("tau") or pe.CONTINUATION_LINF)
    real = _floats(observation)
    if relevant_keys:
        real = {k: real[k] for k in relevant_keys if k in real} or real
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
            # Unselected action was not executed; do not score it.
            keep.append(p)
            continue
        key = str(p.get("key") or "")
        anc = set(p.get("ancestry") or [])
        # One realized tick: one update per relation; descendants of the same
        # ancestry do not get a second independent mismatch.
        if key in seen_keys or (anc and anc & seen_anc):
            continue
        seen_keys.add(key)
        seen_anc |= anc
        pred = dict(p.get("predicted") or {})
        if relevant_keys:
            pred = {k: pred[k] for k in relevant_keys if k in pred} or pred
        err = _projected_linf(pred, real)
        mismatch = err is not None and err > tau
        rel = _relation(store, key)
        rel["last_tick"] = int(tick)
        rel["last_abs_linf"] = err
        was_active = bool(rel.get("active", True))
        if mismatch:
            store["mismatches"] = int(store.get("mismatches") or 0) + 1
            rel["mismatches"] = int(rel.get("mismatches") or 0) + 1
            rel["consecutive_mismatch"] = int(rel.get("consecutive_mismatch") or 0) + 1
        else:
            store["matches"] = int(store.get("matches") or 0) + 1
            rel["consecutive_mismatch"] = 0
            rel["historical_matches"] = int(rel.get("historical_matches") or 0) + 1
        rel["active"] = _still_predictive(
            int(rel.get("historical_matches") or 0),
            int(rel.get("consecutive_mismatch") or 0),
        )
        if was_active and not rel["active"]:
            store["invalidations"] = int(store.get("invalidations") or 0) + 1
        if (not was_active) and rel["active"]:
            store["recoveries"] = int(store.get("recoveries") or 0) + 1
        receipts.append({
            "key": key,
            "action": p.get("action"),
            "mismatch": mismatch,
            "abs_linf": err,
            "lag": p.get("lag"),
            "historical_matches": rel.get("historical_matches"),
            "consecutive_mismatch": rel.get("consecutive_mismatch"),
            "mismatches": rel.get("mismatches"),
            "active": rel.get("active"),
            "source": p.get("source"),
            "not_punishment": True,
        })
    store["pending"] = keep[-MAX_PENDING:]
    pending_keys = {str(p.get("key") or "") for p in keep}
    # Executed action: if a stored predicting relation was not pending this
    # tick (just inactivated / filtered from compose), still compare the
    # ordinary next observation to last_predicted at lag 1 so matching
    # experience can restore eligibility. Lag>1 stays pending-only.
    if last_action:
        for rkey, rel0 in list((store.get("relations") or {}).items()):
            if str(rel0.get("action") or "") != str(last_action):
                continue
            if rkey in seen_keys or rkey in pending_keys:
                continue
            if int(rel0.get("last_lag") or 1) > 1:
                continue
            pred0 = dict(rel0.get("last_predicted") or {})
            if not pred0:
                continue
            anc = set(rel0.get("ancestry") or [])
            if anc and anc & seen_anc:
                continue
            seen_keys.add(rkey)
            seen_anc |= anc
            if relevant_keys:
                pred0 = {k: pred0[k] for k in relevant_keys if k in pred0} or pred0
            err = _projected_linf(pred0, real)
            mismatch = err is not None and err > tau
            rel = _relation(store, rkey)
            rel["last_tick"] = int(tick)
            rel["last_abs_linf"] = err
            was_active = bool(rel.get("active", True))
            if mismatch:
                store["mismatches"] = int(store.get("mismatches") or 0) + 1
                rel["mismatches"] = int(rel.get("mismatches") or 0) + 1
                rel["consecutive_mismatch"] = int(rel.get("consecutive_mismatch") or 0) + 1
            else:
                store["matches"] = int(store.get("matches") or 0) + 1
                rel["consecutive_mismatch"] = 0
                rel["historical_matches"] = int(rel.get("historical_matches") or 0) + 1
            rel["active"] = _still_predictive(
                int(rel.get("historical_matches") or 0),
                int(rel.get("consecutive_mismatch") or 0),
            )
            if was_active and not rel["active"]:
                store["invalidations"] = int(store.get("invalidations") or 0) + 1
            if (not was_active) and rel["active"]:
                store["recoveries"] = int(store.get("recoveries") or 0) + 1
            receipts.append({
                "key": rkey,
                "action": last_action,
                "mismatch": mismatch,
                "abs_linf": err,
                "lag": rel.get("last_lag") or 1,
                "historical_matches": rel.get("historical_matches"),
                "consecutive_mismatch": rel.get("consecutive_mismatch"),
                "mismatches": rel.get("mismatches"),
                "active": rel.get("active"),
                "source": rel.get("source"),
                "not_punishment": True,
                "from_stored_prediction": True,
            })
    recs = store.setdefault("receipts", [])
    recs.extend(receipts)
    store["receipts"] = recs[-MAX_RECEIPTS:]
    return {"status": "REVISED" if receipts else "NONE", "receipts": receipts}


def is_active(store: dict[str, Any], key: str | None) -> bool:
    if store.get("enabled") is False or not key:
        return True
    rel = (store.get("relations") or {}).get(str(key))
    if rel is None:
        return True
    return bool(rel.get("active", True))


def _cont_key(cont: dict[str, Any]) -> str | None:
    edges = list(cont.get("edges") or [])
    root = edges[0] if edges else {}
    return (
        root.get("key")
        or root.get("transition_id")
        or cont.get("key")
        or None
    )


def filter_continuations(store: dict[str, Any], continuations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if store.get("enabled") is False:
        return continuations
    out = []
    for c in continuations or []:
        k = _cont_key(c)
        if k is None or is_active(store, k):
            out.append(c)
    return out


def filter_entry_steps(store: dict[str, Any], entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if store.get("enabled") is False:
        return entries
    return [e for e in (entries or []) if is_active(store, e.get("key") or e.get("transition_id"))]


def filter_groups(store: dict[str, Any], groups: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    if store.get("enabled") is False:
        return groups
    out: dict[str, list[dict[str, Any]]] = {}
    for act, scns in (groups or {}).items():
        kept = []
        for s in scns or []:
            keys = []
            ev = s.get("current_match_evidence")
            if isinstance(ev, dict):
                keys.append(ev.get("key") or ev.get("transition_id"))
            elif isinstance(ev, list) and ev:
                keys.append((ev[0] or {}).get("key") if isinstance(ev[0], dict) else None)
            for kid in s.get("source_structure_ids") or []:
                keys.append(kid)
            keys.append((s.get("provenance") or {}).get("content_sig") if isinstance(s.get("provenance"), dict) else None)
            stale = False
            for k in keys:
                if k and not is_active(store, str(k)):
                    stale = True
                    break
            if not stale:
                kept.append(s)
        out[act] = kept
    return out


def pending_from_selection(
    store: dict[str, Any],
    *,
    selected: str,
    continuations: list[dict[str, Any]],
    tick: int,
    predictions: list[dict[str, Any]] | None = None,
    entry_steps: list[dict[str, Any]] | None = None,
) -> None:
    """Issue bounded pending predictions for the action actually selected."""
    if store.get("enabled") is False:
        return
    issued = False
    for c in continuations or []:
        acts = list(c.get("actions") or [])
        if not acts or str(acts[0]) != str(selected):
            continue
        root = (c.get("edges") or [{}])[0] or {}
        states = list(c.get("states") or [])
        pred = states[1] if len(states) >= 2 else root.get("predicted")
        lag = int(root.get("lag") or 1)
        anc = []
        for x in (root.get("transition_id"), root.get("key"), root.get("temporal_structure_id"),
                  (root.get("provenance") or {}).get("class_id") if isinstance(root.get("provenance"), dict) else None):
            if x:
                anc.append(str(x))
        remember(
            store,
            action=selected,
            predicted=pred,
            key=root.get("key") or root.get("transition_id"),
            tick=tick,
            lag=lag,
            source=str(root.get("prediction_source") or c.get("prediction_source") or "SNAPSHOT"),
            historical_support=int(root.get("support") or 0),
            ancestry=anc,
        )
        issued = True
        break
    if issued:
        return
    for step in entry_steps or []:
        if str(step.get("action") or "") != str(selected):
            continue
        remember(
            store,
            action=selected,
            predicted=step.get("predicted"),
            key=step.get("key") or step.get("transition_id"),
            tick=tick,
            lag=int(step.get("lag") or 1),
            source=str(step.get("prediction_source") or "TEMPORAL"),
            historical_support=int(step.get("support") or 0),
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
            key=res.get("key") or res.get("class_id") or res.get("structure_id"),
            tick=tick,
            lag=int(res.get("lag") or 1),
            source=str(row.get("source") or "compression"),
            historical_support=int(res.get("support") or 0),
            ancestry=[str(x) for x in (res.get("class_id"), res.get("structure_id"), res.get("key")) if x],
        )
        return
    # Inactive relations of the selected action remain scorable: WAIT may
    # still be executed (endogenous / only known action) after it lost
    # MATCH-eligibility. Do not invent a different action.
    for rel in (store.get("relations") or {}).values():
        if str(rel.get("action") or "") != str(selected):
            continue
        if not rel.get("last_predicted"):
            continue
        remember(
            store,
            action=selected,
            predicted=rel.get("last_predicted"),
            key=rel.get("key"),
            tick=tick,
            lag=int(rel.get("last_lag") or 1),
            source=str(rel.get("source") or "SNAPSHOT"),
            historical_support=int(rel.get("historical_matches") or 0),
            ancestry=list(rel.get("ancestry") or []),
        )


def observer_panel(store: dict[str, Any], *, competition_before=None, competition_after=None, selected=None) -> dict[str, Any]:
    rels = list((store.get("relations") or {}).values())[:8]
    last = (store.get("receipts") or [{}])[-1] if store.get("receipts") else {}
    return {
        "kind": "PREDICTION_REVISION",
        "relations": [
            {
                "key": r.get("key"),
                "action": r.get("action"),
                "historical_matches": r.get("historical_matches"),
                "mismatches": r.get("mismatches"),
                "consecutive_mismatch": r.get("consecutive_mismatch"),
                "active": r.get("active"),
                "last_abs_linf": r.get("last_abs_linf"),
            }
            for r in rels
        ],
        "last_receipt": last,
        "pending": deepcopy((store.get("pending") or [])[:8]),
        "competition_before": competition_before,
        "competition_after": competition_after,
        "selected": selected,
        "not_punishment": True,
        "not_trust": True,
    }


def diagnostic(store: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return {
        "kind": "PREDICTION_ERROR_REVISION",
        "not_punishment": True,
        "not_reward": True,
        "not_policy": True,
        **snapshot(store),
        "panel": observer_panel(store, **kwargs),
    }
