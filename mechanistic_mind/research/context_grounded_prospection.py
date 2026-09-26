"""4.27 — Context-grounded prospection (label-free).

Prospective composition over higher-order contextual structures (4.26),
not only low-level immediate transitions.

A/B/C/D are analyzer labels only. No route/destination/goal variables.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
from typing import Any

from mechanistic_mind.research import contextual_predictive_organization as cpo


MAX_CTX_TRANSITIONS = 96
MAX_COMPOSE_DEPTH = 4
MAX_BRANCH = 4
MAX_EXPANSIONS = 48


def empty_store() -> dict[str, Any]:
    return {
        "transitions": {},  # key -> row
        "enabled": False,
        "ablate_composition": False,
        "shuffle_relations": False,
        "learn_events": 0,
        "compose_events": 0,
        "forgotten": 0,
        "last_composition": None,
        "note": "CONTEXT_GROUNDED_PROSPECTION — contextual transitions, not routes",
    }


def snapshot(store: dict[str, Any] | None) -> dict[str, Any]:
    s = store or {}
    return {
        "enabled": bool(s.get("enabled")),
        "n_transitions": len(s.get("transitions") or {}),
        "learn_events": s.get("learn_events"),
        "compose_events": s.get("compose_events"),
        "forgotten": s.get("forgotten"),
        "last_composition": deepcopy(s.get("last_composition")),
        "ablate_composition": bool(s.get("ablate_composition")),
        "capacities": {
            "MAX_CTX_TRANSITIONS": MAX_CTX_TRANSITIONS,
            "MAX_COMPOSE_DEPTH": MAX_COMPOSE_DEPTH,
        },
        "note": s.get("note"),
    }


def observer_compact(store: dict[str, Any] | None) -> dict[str, Any]:
    s = store or {}
    tr = s.get("transitions") or {}
    top = sorted(tr.values(), key=lambda r: (-int(r.get("support") or 0), str(r.get("id"))))[:6]
    return {
        "detail": "compact",
        "enabled": bool(s.get("enabled")),
        "n_transitions": len(tr),
        "top": [
            {
                "id": r.get("id"),
                "from": r.get("from_id"),
                "to": r.get("to_id"),
                "action": r.get("action"),
                "support": r.get("support"),
            }
            for r in top
        ],
        "last_depth": (s.get("last_composition") or {}).get("max_depth"),
    }


def _tid(from_id: str, action: str, to_id: str) -> str:
    return sha1(f"{from_id}|{action}|{to_id}".encode()).hexdigest()[:12]


def learn_context_transition(
    store: dict[str, Any],
    *,
    tick: int,
    from_id: str,
    to_id: str,
    action: str,
    from_pred: dict[str, float] | None = None,
    to_pred: dict[str, float] | None = None,
) -> str | None:
    if not store.get("enabled"):
        return None
    if not from_id or not to_id or from_id == to_id:
        return None
    act = str(action or "WAIT")
    if store.get("shuffle_relations"):
        # Break intermediate relational identity for controls.
        act = sha1(f"shuf:{tick}:{act}".encode()).hexdigest()[:8]
    key = _tid(str(from_id), act, str(to_id))
    tr = store.setdefault("transitions", {})
    row = tr.get(key)
    if row is None:
        if len(tr) >= MAX_CTX_TRANSITIONS:
            victim = min(tr.items(), key=lambda kv: (int(kv[1].get("support") or 0), str(kv[0])))[0]
            del tr[victim]
            store["forgotten"] = int(store.get("forgotten") or 0) + 1
        row = {
            "id": f"CT{key}",
            "key": key,
            "from_id": str(from_id),
            "to_id": str(to_id),
            "action": act,
            "support": 0,
            "formed_tick": int(tick),
            "last_tick": int(tick),
            "from_pred": dict(from_pred or {}),
            "to_pred": dict(to_pred or {}),
        }
        tr[key] = row
        store["learn_events"] = int(store.get("learn_events") or 0) + 1
    row["support"] = int(row.get("support") or 0) + 1
    row["last_tick"] = int(tick)
    return row.get("id")


def compose_context_trajectories(
    store: dict[str, Any],
    *,
    start_id: str,
    max_depth: int | None = None,
    broken_ids: set[str] | None = None,
) -> dict[str, Any]:
    """BFS over contextual transitions from start_id."""
    store["compose_events"] = int(store.get("compose_events") or 0) + 1
    if not store.get("enabled") or store.get("ablate_composition"):
        out = {"status": "ABLATED", "continuations": [], "max_depth": 0}
        store["last_composition"] = out
        return out
    if not start_id:
        out = {"status": "NO_START", "continuations": [], "max_depth": 0}
        store["last_composition"] = out
        return out
    depth_cap = min(int(max_depth or MAX_COMPOSE_DEPTH), MAX_COMPOSE_DEPTH)
    broken = broken_ids or set()
    # adjacency: from_id -> list of transition rows
    adj: dict[str, list[dict[str, Any]]] = {}
    for row in sorted((store.get("transitions") or {}).values(), key=lambda r: str(r.get("id"))):
        if row.get("id") in broken or row.get("key") in broken:
            continue
        if store.get("shuffle_relations"):
            continue  # no usable edges under shuffle ablation mode for compose
        adj.setdefault(str(row.get("from_id")), []).append(row)

    continuations: list[dict[str, Any]] = []
    frontier: list[dict[str, Any]] = [
        {"path_ids": [str(start_id)], "actions": [], "edges": [], "depth": 0}
    ]
    expansions = 0
    max_d = 0
    while frontier and expansions < MAX_EXPANSIONS:
        node = frontier.pop(0)
        expansions += 1
        cur = node["path_ids"][-1]
        if node["depth"] > 0:
            continuations.append({
                "start_id": str(start_id),
                "path_ids": list(node["path_ids"]),
                "actions": list(node["actions"]),
                "edges": list(node["edges"]),
                "depth": int(node["depth"]),
                "terminal_id": cur,
                "source": "context_grounded_prospection",
            })
            max_d = max(max_d, int(node["depth"]))
        if node["depth"] >= depth_cap:
            continue
        branched = 0
        for row in adj.get(cur, []):
            if branched >= MAX_BRANCH:
                break
            nxt = str(row.get("to_id"))
            if nxt in node["path_ids"]:
                continue
            frontier.append({
                "path_ids": node["path_ids"] + [nxt],
                "actions": node["actions"] + [str(row.get("action"))],
                "edges": node["edges"] + [row.get("id")],
                "depth": int(node["depth"]) + 1,
            })
            branched += 1
    # Prefer deeper novel compositions first
    continuations.sort(key=lambda c: (-int(c.get("depth") or 0), tuple(c.get("path_ids") or [])))
    out = {
        "status": "OK" if continuations else "EMPTY",
        "continuations": continuations[: max(MAX_BRANCH * 2, 8)],
        "max_depth": max_d,
        "expansions": expansions,
        "start_id": str(start_id),
    }
    store["last_composition"] = {
        "status": out["status"],
        "max_depth": max_d,
        "n": len(continuations),
        "start_id": str(start_id),
    }
    return out


def inject_as_prospection_continuations(
    composition: dict[str, Any],
    *,
    present: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """Map context compositions into the shape expected by PSC/continuations."""
    out: list[dict[str, Any]] = []
    for c in composition.get("continuations") or []:
        acts = list(c.get("actions") or [])
        if not acts:
            continue
        out.append({
            "actions": acts,
            "first_action": acts[0],
            "future_actions": acts[1:],
            "depth": int(c.get("depth") or len(acts)),
            "path_ids": list(c.get("path_ids") or []),
            "terminal_id": c.get("terminal_id"),
            "source": "context_grounded_prospection",
            "historical_support": float(c.get("depth") or 1),
            "reliability": 0.5 + 0.1 * float(c.get("depth") or 0),
            "present": dict(present or {}),
            "note": "CONTEXTUAL_COMPOSITION — not a semantic route",
        })
    return out
