"""4.26 — Contextual predictive organization (label-free).

Higher-order predictive structures form from repeated co-activation of
lower-level compressed / multi-scale evidence under non-identical visits.

Scientist-facing words (place, familiar, novel, map, …) are analyzer labels
only. They must not appear as privileged cognition variables.

Does not replace Update 4.21 compression or 4.22 multiscale — layers on top.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
from typing import Any


MAX_CONTEXTS = 48
MAX_MEMBERS = 12
MAX_RECENT_COACTIVE = 64
MAX_PROVENANCE = 24
MIN_SUPPORT_FORM = 4
MIN_PARTIAL_OVERLAP = 1
PARTIAL_MIN_RATIO = 0.5  # fraction of members for PARTIAL reactivation


FORBIDDEN = (
    "PLACE", "LOCATION", "LANDMARK", "MAP", "ROUTE", "DESTINATION",
    "GOAL", "PLAN", "INTENTION", "FAMILIAR", "NOVEL", "HOME",
)


def _sig(parts: list[str]) -> str:
    raw = "|".join(sorted(str(p) for p in parts))
    return sha1(raw.encode("utf-8")).hexdigest()[:14]


def empty_store() -> dict[str, Any]:
    return {
        "contexts": {},
        "recent_coactive": [],
        "ticks": 0,
        "formation_events": 0,
        "revision_events": 0,
        "reactivation_events": 0,
        "forgotten": 0,
        "next_id": 1,
        "enabled": False,
        "ablate_higher_order": False,
        "ablate_predictive_use": False,
        "shuffle_members": False,
        "metrics_affect_cognition": False,
        "last_active": None,
        "last_reactivation": None,
        "prediction_events": 0,
        "prediction_hits": 0,
        "note": "CONTEXTUAL_PREDICTIVE_ORGANIZATION — relation co-activation, not place",
    }


def snapshot(store: dict[str, Any] | None) -> dict[str, Any]:
    s = store or {}
    ctxs = s.get("contexts") or {}
    return {
        "enabled": bool(s.get("enabled")),
        "n_contexts": len(ctxs),
        "formation_events": s.get("formation_events"),
        "revision_events": s.get("revision_events"),
        "reactivation_events": s.get("reactivation_events"),
        "forgotten": s.get("forgotten"),
        "prediction_events": s.get("prediction_events"),
        "prediction_hits": s.get("prediction_hits"),
        "last_active": deepcopy(s.get("last_active")),
        "last_reactivation": deepcopy(s.get("last_reactivation")),
        "capacities": {
            "MAX_CONTEXTS": MAX_CONTEXTS,
            "MAX_MEMBERS": MAX_MEMBERS,
            "MIN_SUPPORT_FORM": MIN_SUPPORT_FORM,
        },
        "ablate_higher_order": bool(s.get("ablate_higher_order")),
        "note": s.get("note"),
    }


def observer_compact(store: dict[str, Any] | None) -> dict[str, Any]:
    """LIVE-safe summary — no giant member dumps."""
    s = store or {}
    ctxs = s.get("contexts") or {}
    top = sorted(
        ctxs.values(),
        key=lambda r: (-int(r.get("support") or 0), str(r.get("context_id") or "")),
    )[:6]
    return {
        "detail": "compact",
        "enabled": bool(s.get("enabled")),
        "n_contexts": len(ctxs),
        "top": [
            {
                "context_id": r.get("context_id"),
                "support": r.get("support"),
                "n_members": len(r.get("members") or []),
                "reuse": r.get("reuse"),
            }
            for r in top
        ],
        "last_active_id": (s.get("last_active") or {}).get("context_id"),
        "formation_events": s.get("formation_events"),
        "reactivation_events": s.get("reactivation_events"),
    }


def audit_forbidden(payload: Any) -> list[str]:
    text = str(payload)
    return [t for t in FORBIDDEN if t in text]


def _member_ids_from_evidence(
    *,
    compression_hits: list[str] | None,
    multiscale_ids: list[str] | None,
    relation_keys: list[str] | None,
) -> list[str]:
    members: list[str] = []
    for src in (compression_hits or [], multiscale_ids or [], relation_keys or []):
        for m in src:
            sm = str(m)
            if sm and sm not in members:
                members.append(sm)
    return members[:MAX_MEMBERS]


def observe_coactivation(
    store: dict[str, Any],
    *,
    tick: int,
    members: list[str],
    continuation: dict[str, float] | None = None,
    action: str | None = None,
) -> dict[str, Any] | None:
    """Record co-active lower-level evidence; maybe form/update a context."""
    if not store.get("enabled") or store.get("ablate_higher_order"):
        return None
    store["ticks"] = int(store.get("ticks") or 0) + 1
    clean = [str(m) for m in members if m][:MAX_MEMBERS]
    if len(clean) < 2:
        return None
    if store.get("shuffle_members"):
        # Deterministic scramble control — breaks relational co-occurrence.
        clean = sorted(clean, key=lambda x: sha1(f"{tick}:{x}".encode()).hexdigest())
        # rotate so overlap with true set is low
        if len(clean) >= 2:
            clean = clean[1:] + clean[:1]
    key = _sig(clean)
    recent = store.setdefault("recent_coactive", [])
    recent.append({"tick": int(tick), "key": key, "members": list(clean), "action": action})
    if len(recent) > MAX_RECENT_COACTIVE:
        del recent[: len(recent) - MAX_RECENT_COACTIVE]

    contexts = store.setdefault("contexts", {})
    cont = {
        str(k): float(v)
        for k, v in (continuation or {}).items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }
    # Prefer merge into an existing context with high member overlap (variation-tolerant).
    row = contexts.get(key)
    if row is None and contexts:
        best_k, best_ratio, best_row = None, 0.0, None
        clean_set = set(clean)
        for ck, crow in contexts.items():
            mset = set(crow.get("members") or [])
            if not mset:
                continue
            ratio = len(clean_set & mset) / max(len(mset), len(clean_set))
            if ratio > best_ratio:
                best_k, best_ratio, best_row = ck, ratio, crow
        if best_row is not None and best_ratio >= PARTIAL_MIN_RATIO:
            row = best_row
            # Union members (bounded) so later partial evidence can reactivate
            merged = list(dict.fromkeys(list(row.get("members") or []) + clean))[:MAX_MEMBERS]
            row["members"] = merged
    if row is None:
        # Form after repeated similar co-activations in recent window (Jaccard).
        similar = 0
        clean_set = set(clean)
        for r in recent:
            mset = set(r.get("members") or [])
            if not mset:
                continue
            j = len(clean_set & mset) / max(1, len(clean_set | mset))
            if j >= PARTIAL_MIN_RATIO:
                similar += 1
        if similar < MIN_SUPPORT_FORM:
            return None
        if len(contexts) >= MAX_CONTEXTS:
            victim = min(
                contexts.items(),
                key=lambda kv: (int(kv[1].get("support") or 0), str(kv[0])),
            )[0]
            del contexts[victim]
            store["forgotten"] = int(store.get("forgotten") or 0) + 1
        cid = f"CX{int(store.get('next_id') or 1):04d}"
        store["next_id"] = int(store.get("next_id") or 1) + 1
        row = {
            "context_id": cid,
            "key": key,
            "members": list(clean),
            "support": 0,
            "reuse": 0,
            "predicted_sum": {k: 0.0 for k in cont},
            "predicted_n": 0,
            "actions": {},
            "provenance": [],
            "formed_tick": int(tick),
            "last_tick": int(tick),
        }
        contexts[key] = row
        store["formation_events"] = int(store.get("formation_events") or 0) + 1
    row["support"] = int(row.get("support") or 0) + 1
    row["reuse"] = int(row.get("reuse") or 0) + 1
    row["last_tick"] = int(tick)
    if action:
        acts = row.setdefault("actions", {})
        acts[str(action)] = int(acts.get(str(action)) or 0) + 1
    if cont:
        ps = row.setdefault("predicted_sum", {})
        for k, v in cont.items():
            ps[k] = float(ps.get(k) or 0.0) + float(v)
        row["predicted_n"] = int(row.get("predicted_n") or 0) + 1
    prov = row.setdefault("provenance", [])
    if len(prov) < MAX_PROVENANCE:
        prov.append({"tick": int(tick), "n_members": len(clean)})
    store["last_active"] = {
        "context_id": row.get("context_id"),
        "support": row.get("support"),
        "tick": int(tick),
    }
    return deepcopy(row)


def predicted_mean(row: dict[str, Any] | None) -> dict[str, float]:
    if not row:
        return {}
    n = max(1, int(row.get("predicted_n") or 0))
    return {k: float(v) / n for k, v in (row.get("predicted_sum") or {}).items()}


def reactivate(
    store: dict[str, Any],
    *,
    tick: int,
    evidence_members: list[str],
    mode: str = "PARTIAL",
) -> dict[str, Any]:
    """Score existing contexts against current member evidence.

    mode is analyzer-facing only (FULL/PARTIAL/NOVEL/SHUFFLED controls).
    """
    if not store.get("enabled") or store.get("ablate_higher_order"):
        return {"status": "DISABLED", "matches": []}
    members = [str(m) for m in evidence_members if m]
    member_set = set(members)
    if store.get("shuffle_members") and members:
        # Relational scramble control: replace with unrelated synthetic tokens.
        members = [f"shuf:{sha1(f'{tick}:{m}'.encode()).hexdigest()[:8]}" for m in members]
        member_set = set(members)
    matches: list[dict[str, Any]] = []
    for row in (store.get("contexts") or {}).values():
        mset = set(row.get("members") or [])
        if not mset:
            continue
        overlap = member_set & mset
        if not overlap:
            continue
        if len(overlap) < MIN_PARTIAL_OVERLAP:
            continue
        # Coverage of the *query* evidence (partial reactivation) and of the structure.
        evidence_coverage = len(overlap) / max(1, len(member_set))
        structure_coverage = len(overlap) / max(1, len(mset))
        ratio = evidence_coverage if mode in {"PARTIAL", "NOVEL", "SHUFFLED"} else min(evidence_coverage, structure_coverage)
        if mode == "FULL" and evidence_coverage < 0.999:
            continue
        if mode in {"PARTIAL", "NOVEL", "SHUFFLED"} and evidence_coverage < 0.25:
            continue
        score = evidence_coverage * (1.0 + 0.1 * float(row.get("support") or 0))
        # keep structure_coverage for diagnostics
        matches.append({
            "context_id": row.get("context_id"),
            "overlap": len(overlap),
            "ratio": round(float(evidence_coverage), 4),
            "structure_coverage": round(float(structure_coverage), 4),
            "support": row.get("support"),
            "score": round(score, 4),
            "predicted": predicted_mean(row),
            "members": list(row.get("members") or []),
        })
    matches.sort(key=lambda r: (-float(r["score"]), str(r["context_id"])))
    best = matches[0] if matches else None
    status = "MATCH" if best and float(best["ratio"]) >= PARTIAL_MIN_RATIO else (
        "WEAK" if best else "NO_MATCH"
    )
    if best and status in {"MATCH", "WEAK"}:
        store["reactivation_events"] = int(store.get("reactivation_events") or 0) + 1
        # bump reuse on the live row
        for row in (store.get("contexts") or {}).values():
            if row.get("context_id") == best.get("context_id"):
                row["reuse"] = int(row.get("reuse") or 0) + 1
                break
    out = {
        "status": status,
        "tick": int(tick),
        "mode": str(mode),
        "n_evidence": len(members),
        "best": best,
        "matches": matches[:8],
    }
    store["last_reactivation"] = {
        "status": status,
        "context_id": (best or {}).get("context_id"),
        "ratio": (best or {}).get("ratio"),
        "tick": int(tick),
    }
    return out


def predict_from_context(
    store: dict[str, Any],
    reactivation: dict[str, Any] | None,
) -> dict[str, Any]:
    """Use reactivated higher-order predicted continuation if allowed."""
    store["prediction_events"] = int(store.get("prediction_events") or 0) + 1
    if not store.get("enabled") or store.get("ablate_predictive_use"):
        return {"status": "ABLATED", "predicted": {}}
    best = (reactivation or {}).get("best")
    if not best or float(best.get("ratio") or 0) < PARTIAL_MIN_RATIO:
        return {"status": "NO_MATCH", "predicted": {}}
    pred = dict(best.get("predicted") or {})
    if not pred:
        return {"status": "EMPTY", "predicted": {}}
    store["prediction_hits"] = int(store.get("prediction_hits") or 0) + 1
    return {
        "status": "MATCH",
        "context_id": best.get("context_id"),
        "predicted": pred,
        "support": best.get("support"),
        "ratio": best.get("ratio"),
    }


def predictive_l1(predicted: dict[str, float], realized: dict[str, float]) -> float:
    keys = sorted(set(predicted) | set(realized))
    if not keys:
        return 0.0
    return sum(abs(float(predicted.get(k, 0.0)) - float(realized.get(k, 0.0))) for k in keys) / len(keys)


def collect_members_from_runtime_state(state: dict[str, Any]) -> list[str]:
    """Gather currently implicated structure IDs from cognition state (read-only)."""
    members: list[str] = []
    comp = state.get("compression") or {}
    for row in (comp.get("structures") or {}).values():
        if row.get("status") == "ACTIVE" and int(row.get("support") or 0) >= 2:
            sid = row.get("structure_id")
            if sid:
                members.append(str(sid))
    ms = state.get("multiscale") or {}
    for row in (ms.get("broader") or {}).values():
        bid = row.get("broader_id")
        if bid and int(row.get("support") or 0) >= 2:
            members.append(str(bid))
    for row in (ms.get("local") or {}).values():
        lid = row.get("local_id")
        if lid and int(row.get("support") or 0) >= MIN_SUPPORT_FORM:
            members.append(str(lid))
    # Deterministic order; cap
    return sorted(set(members))[:MAX_MEMBERS]
