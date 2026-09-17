"""Experimental predictive conflict: content-based scenario identity.

Default OFF. Preserves incompatible supported continuations that share a first
action. Merges compatible continuations regardless of diagnostic source.

Does not select, prefer temporal vs snapshot, invent confidence/doubt, or
fabricate support.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.research import predictive_equivalence as pe
from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research.predictive_compression import _sig
from mechanistic_mind.research.predictive_equivalence import _floats

MAX_CANDIDATES = 16
MAX_ROUTES = 8
MAX_PROV = 12
MAX_LAST = 16


def empty_store() -> dict[str, Any]:
    return {
        "enabled": False,
        "candidates": [],
        "last_candidates": [],
        "receipts": [],
        "organizes": 0,
        "merges": 0,
        "conflicts": 0,
        "disconfirmations": 0,
        "tau": pe.CONTINUATION_LINF,
        "note": "PREDICTIVE_CONFLICT — not doubt, not belief, not choice",
    }


def snapshot(store: dict[str, Any]) -> dict[str, Any]:
    cands = list(store.get("candidates") or [])
    return {
        "enabled": bool(store.get("enabled")),
        "n_candidates": len(cands),
        "n_conflicting_groups": sum(1 for c in cands if c.get("status") == "CONFLICTING"),
        "organizes": store.get("organizes"),
        "merges": store.get("merges"),
        "conflicts": store.get("conflicts"),
        "disconfirmations": store.get("disconfirmations"),
        "candidates": [
            {
                "id": c.get("id"),
                "first_action": c.get("first_action"),
                "support": c.get("support"),
                "status": c.get("status"),
                "n_routes": len(c.get("routes") or []),
                "content_sig": c.get("content_sig"),
            }
            for c in cands[:MAX_CANDIDATES]
        ],
        "note": "Observer labels only — not cognitive semantics",
    }


def _qfrag(fragment: dict[str, Any] | None) -> dict[str, float]:
    return pr._q(_floats(fragment))


def content_sig(actions: list[str], states_after: list[dict[str, float]]) -> str:
    """Bounded prospective-path identity: actions + quantized predicted states."""
    parts = ["|".join(str(a) for a in actions)]
    for st in states_after[: pr.MAX_DEPTH]:
        parts.append(_sig(_qfrag(st)))
    return "||".join(parts)


def _predicted_from_cont(cont: dict[str, Any]) -> dict[str, float]:
    states = list(cont.get("states") or [])
    if len(states) >= 2:
        return _floats(states[1])
    edges = list(cont.get("edges") or [])
    if edges:
        return _floats(edges[0].get("predicted") or {})
    return {}


def _ancestry(cont: dict[str, Any], edge: dict[str, Any] | None = None) -> dict[str, Any]:
    e = edge or ((cont.get("edges") or [{}])[0] or {})
    prov = e.get("provenance") if isinstance(e.get("provenance"), dict) else {}
    ids = []
    for x in (
        e.get("transition_id"),
        e.get("class_id"),
        e.get("temporal_structure_id"),
        e.get("key"),
        prov.get("class_id"),
        prov.get("delta_sig"),
    ):
        if x:
            ids.append(str(x))
    raw = []
    for x in (prov.get("raw_id"), e.get("raw_id")):
        if x is not None:
            raw.append(str(x))
    return {
        "structure_ids": ids[:MAX_PROV],
        "raw_ids": raw[:MAX_PROV],
        "edge_key": e.get("key"),
        "source": e.get("prediction_source") or cont.get("prediction_source") or "SNAPSHOT",
        "lag": e.get("lag") or prov.get("lag"),
    }


def make_continuation(
    *,
    action: str = "WAIT",
    predicted: dict[str, float],
    support: int,
    source: str = "SNAPSHOT",
    present: dict[str, float] | None = None,
    path: list[dict[str, float]] | None = None,
    actions: list[str] | None = None,
    raw_id: str | None = None,
    structure_id: str | None = None,
) -> dict[str, Any]:
    """Observer/test constructor. Cognition never receives semantic scenario labels."""
    acts = [str(a) for a in (actions or [action])]
    after = [dict(s) for s in (path or [predicted])]
    start = dict(present or {})
    states = [start] + after
    edges = []
    for i, act in enumerate(acts):
        pred_i = after[i] if i < len(after) else after[-1]
        edges.append({
            "status": "MATCH",
            "action": act,
            "predicted": dict(pred_i),
            "support": int(support),
            "prediction_source": source,
            "key": f"{source}|{structure_id or act}|{i}",
            "transition_id": structure_id,
            "raw_id": raw_id,
            "provenance": {"raw_id": raw_id, "class_id": structure_id, "source": source},
        })
    return {
        "actions": acts,
        "states": states,
        "edges": edges,
        "depth": len(acts),
        "prediction_source": source,
    }


def _projected_linf(pred: dict[str, float], realized: dict[str, float]) -> float | None:
    """Match error on predicted channels only (ordinary linf, not a belief score)."""
    pred_f = _floats(pred)
    if not pred_f:
        return None
    real = _floats(realized)
    return max(abs(float(pred_f[k]) - float(real.get(k, 0.0))) for k in pred_f)


def continuation_to_route(cont: dict[str, Any]) -> dict[str, Any] | None:
    actions = list(cont.get("actions") or [])
    if not actions:
        return None
    states = [_floats(s) for s in (cont.get("states") or [])]
    after = states[1:] if len(states) > 1 else []
    if not after:
        pred = _predicted_from_cont(cont)
        if not pred:
            return None
        after = [pred]
        if states:
            states = [states[0], pred]
        else:
            states = [{}, pred]
    root = (cont.get("edges") or [{}])[0] or {}
    support = int(root.get("support") or 0)
    if support <= 0:
        return None
    return {
        "first_action": str(actions[0]),
        "actions": [str(a) for a in actions],
        "states": states,
        "predicted": dict(after[0]),
        "predicted_path": after,
        "depth": int(cont.get("depth") or len(actions)),
        "support": support,
        "reliability": root.get("reliability"),
        "prediction_source": root.get("prediction_source") or cont.get("prediction_source") or "SNAPSHOT",
        "content_sig": content_sig(actions, after),
        "ancestry": _ancestry(cont, root),
        "not_snapshot_transition": bool(root.get("not_snapshot_transition")),
    }


def _merge_routes(routes: list[dict[str, Any]]) -> dict[str, Any]:
    """Associate evidence routes for the same content. Do not sum shared ancestry."""
    ids: set[str] = set()
    raws: set[str] = set()
    sources: list[str] = []
    supports: list[int] = []
    shared = False
    seen_raw: set[str] = set()
    for r in routes:
        anc = r.get("ancestry") or {}
        rid = set(str(x) for x in (anc.get("raw_ids") or []) if x)
        sid = set(str(x) for x in (anc.get("structure_ids") or []) if x)
        if rid & seen_raw or (sid & ids and rid):
            shared = True
        seen_raw |= rid
        ids |= sid
        raws |= rid
        sources.append(str(r.get("prediction_source") or "SNAPSHOT"))
        supports.append(int(r.get("support") or 0))
    # Conservative ordinary support: max of routes, never a sum of descendants.
    support = max(supports) if supports else 0
    return {
        "support": support,
        "route_supports": supports,
        "sources": sorted(set(sources)),
        "structure_ids": sorted(ids)[:MAX_PROV],
        "raw_ids": sorted(raws)[:MAX_PROV],
        "shared_ancestry": shared,
        "summed": False,
        "n_routes": len(routes),
    }


def organize(
    store: dict[str, Any],
    continuations: list[dict[str, Any]],
    *,
    realized: dict[str, float] | None = None,
    last_action: str | None = None,
) -> dict[str, Any]:
    """Cluster continuations by predicted content, not by diagnostic source."""
    if store.get("enabled") is False:
        return {"status": "DISABLED", "candidates": []}
    store["organizes"] = int(store.get("organizes") or 0) + 1
    tau = float(store.get("tau") or pe.CONTINUATION_LINF)
    last = list(store.get("last_candidates") or [])
    realized_receipts = []
    if realized is not None and last:
        rf = _floats(realized)
        for c in last:
            if last_action and str(c.get("first_action") or "") != str(last_action):
                continue
            pred = _floats(c.get("predicted") or {})
            err = _projected_linf(pred, rf)
            mismatch = err is not None and err > tau
            if mismatch:
                store["disconfirmations"] = int(store.get("disconfirmations") or 0) + 1
            realized_receipts.append({
                "id": c.get("id"),
                "mismatch": mismatch,
                "abs_linf": err,
                "prior_support": c.get("support"),
                "predicted": pred,
                "content_sig": c.get("content_sig"),
                "first_action": c.get("first_action"),
            })

    buckets: dict[str, list[dict[str, Any]]] = {}
    for cont in continuations or []:
        route = continuation_to_route(cont)
        if route is None:
            continue
        buckets.setdefault(route["content_sig"], []).append(route)

    candidates = []
    next_id = 1
    for sig, routes in buckets.items():
        if len(candidates) >= MAX_CANDIDATES:
            break
        routes = routes[:MAX_ROUTES]
        if len(routes) > 1:
            store["merges"] = int(store.get("merges") or 0) + 1
        acc = _merge_routes(routes)
        head = routes[0]
        cid = f"C{next_id}"
        next_id += 1
        candidates.append({
            "id": cid,
            "first_action": head["first_action"],
            "actions": head["actions"],
            "predicted": head["predicted"],
            "predicted_path": head["predicted_path"],
            "depth": max(int(r.get("depth") or 1) for r in routes),
            "support": acc["support"],
            "reliability": head.get("reliability"),
            "content_sig": sig,
            "status": "COMPATIBLE",
            "routes": [
                {
                    "source": r.get("prediction_source"),
                    "support": r.get("support"),
                    "ancestry": r.get("ancestry"),
                }
                for r in routes
            ],
            "evidence": acc,
            "prediction_sources": acc["sources"],
        })

    by_act: dict[str, list[dict[str, Any]]] = {}
    for c in candidates:
        by_act.setdefault(c["first_action"], []).append(c)
    n_conflict_groups = 0
    for _act, group in by_act.items():
        if len(group) < 2:
            continue
        # Distinct content_sigs sharing a first action are incompatible futures.
        incompatible = len({c.get("content_sig") for c in group}) > 1
        if incompatible:
            n_conflict_groups += 1
            store["conflicts"] = int(store.get("conflicts") or 0) + 1
            for c in group:
                c["status"] = "CONFLICTING"

    last_map = {
        rec.get("content_sig"): rec
        for rec in realized_receipts
        if rec.get("content_sig")
    }
    for c in candidates:
        rec = last_map.get(c.get("content_sig"))
        if rec and rec.get("mismatch"):
            c["status"] = "DISCONFIRMED"
            c["realized_mismatch"] = rec

    leaders = {}
    for act, group in by_act.items():
        live = [c for c in group if c.get("status") != "DISCONFIRMED"]
        if not live:
            continue
        leaders[act] = max(live, key=lambda c: int(c.get("support") or 0))["id"]

    store["candidates"] = candidates
    store["last_candidates"] = deepcopy(candidates)[:MAX_LAST]
    receipt = {
        "n_candidates": len(candidates),
        "n_conflict_groups": n_conflict_groups,
        "first_actions": sorted(by_act),
        "support_leaders": leaders,
        "realized": realized_receipts[:MAX_CANDIDATES],
        "not_selected_action": True,
    }
    recs = store.setdefault("receipts", [])
    recs.append(receipt)
    store["receipts"] = recs[-24:]
    return {
        "status": "CONFLICTING" if n_conflict_groups else "ORGANIZED",
        "candidates": candidates,
        "receipt": receipt,
        "n_conflict_groups": n_conflict_groups,
    }


def diagnostic(store: dict[str, Any]) -> dict[str, Any]:
    cands = list(store.get("candidates") or [])
    return {
        "kind": "PREDICTIVE_SCENARIOS",
        "not_doubt": True,
        "not_belief": True,
        "not_choice": True,
        **snapshot(store),
        "last_receipt": (store.get("receipts") or [{}])[-1] if store.get("receipts") else {},
        "panel": observer_panel(cands),
    }


def observer_panel(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Observer scientific labels derived from receipts. Not cognitive semantics."""
    rows = []
    for c in candidates[:MAX_CANDIDATES]:
        rows.append({
            "scenario": c.get("id"),
            "first_action": c.get("first_action"),
            "predicted_continuation": c.get("predicted"),
            "prospective_path": c.get("predicted_path"),
            "support": c.get("support"),
            "evidence_ancestry": (c.get("evidence") or {}),
            "prediction_sources": c.get("prediction_sources"),
            "current_status": c.get("status"),
        })
    return rows
