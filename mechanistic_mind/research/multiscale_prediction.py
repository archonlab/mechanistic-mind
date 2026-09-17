"""Update 4.22 — Emergent multi-scale predictive organization (label-free).

Local predictive structures may become evidence for further bounded predictive
structures. Researcher may describe local/broader/deeper; cognition must not
receive LEVEL_*/HIGH_LEVEL/REGIME/SEASON/CONTEXT_NAME or similar.

Does not tune Update 4.20 deeper-in-use NULLs or Update 4.21 same-present NULL
into acceptance targets. No hierarchy/abstraction/curiosity rewards.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha1
from typing import Any


# Explicit capacities (Category A).
MAX_LOCAL = 96
MAX_RELATIONS = 64
MAX_BROADER = 32
MAX_EVIDENCE_PER = 24
MAX_PROVENANCE = 24
MAX_DEPTH = 4  # safety cap only — not a semantic hierarchy
MIN_SUPPORT_LOCAL = 4
MIN_SUPPORT_REL = 3
MIN_SUPPORT_BROADER = 5
MIN_PREDICTIVE_DELTA = 1e-6  # researcher threshold; not a cognitive reward


FORBIDDEN_COGNITION_TOKENS = (
    "LEVEL_1", "LEVEL_2", "LEVEL_3", "HIGH_LEVEL", "LOW_LEVEL", "HIERARCHY",
    "META_PATTERN", "GLOBAL_CONTEXT", "SUPER_PATTERN", "ABSTRACT_CONTEXT",
    "DEEP_MODEL", "SHALLOW_MODEL", "HIGHER_ORDER", "LOWER_ORDER",
    "MACRO_STATE", "MICRO_STATE", "SEASON", "REGIME", "SITUATION", "SCENARIO",
    "CONTEXT_NAME", "PLACE_TYPE", "WORLD_MODE", "WORLD_STATE_LABEL",
    "CAUSE", "EXPLANATION", "UNDERSTANDING", "WHY", "THEORY_A", "THEORY_B",
    "BELIEF", "HYPOTHESIS", "G_PHASE", "WORLD_CHANGED", "CONTEXT_CHANGED",
)


def _sig(payload: dict[str, Any]) -> str:
    items = sorted(
        (
            str(k),
            round(float(v), 4) if isinstance(v, (int, float)) and not isinstance(v, bool) else str(v),
        )
        for k, v in payload.items()
    )
    raw = "|".join(f"{k}:{v}" for k, v in items)
    return sha1(raw.encode("utf-8")).hexdigest()[:12]


def _qfrag(fragment: dict[str, float], bins: int = 5) -> dict[str, float]:
    out = {}
    for k, v in fragment.items():
        q = int(max(0.0, min(0.999999, float(v))) * bins)
        out[str(k)] = (q + 0.5) / bins
    return out


def empty_org() -> dict[str, Any]:
    return {
        "local": {},  # key -> stats
        "relations": {},  # (id_a, id_b) -> stats
        "broader": {},  # bid -> candidate
        "recent_local_ids": [],
        "ticks": 0,
        "formation_events": 0,
        "revision_events": 0,
        "forgotten_broader": 0,
        "next_local": 1,
        "next_broader": 1,
        "ablate_broader": False,
        "ablate_local": False,
        "ablate_relations": False,
        "ablate_provenance": False,
        "random_cluster": False,
        "metrics_affect_cognition": False,
        "prediction_at_event": {},
        "pae_capacity": 64,
        "raw_refs": {},  # optional linkage to 4.21 raw ids
        "depth_cap": MAX_DEPTH,
    }


def audit_forbidden_in_cognition(payload: Any) -> list[str]:
    """Researcher leak audit — scans stringified agent-facing structures."""
    text = str(payload)
    return [tok for tok in FORBIDDEN_COGNITION_TOKENS if tok in text]


def _local_key(domain: str, antecedent: dict[str, float], action: str) -> str:
    return f"{domain}||{_sig(antecedent)}||{action}"


def ingest_local(
    org: dict[str, Any],
    *,
    tick: int,
    domain: str,
    fragment: dict[str, float],
    action: str,
    realized: dict[str, float],
    raw_id: int | None = None,
) -> str | None:
    """Learn/update a local predictive structure from ordinary evidence."""
    if org.get("ablate_local"):
        return None
    org["ticks"] = int(tick)
    ant = _qfrag(fragment)
    real = _qfrag(realized)
    key = _local_key(domain, ant, action)
    local = org.setdefault("local", {})
    row = local.get(key)
    if row is None:
        if len(local) >= MAX_LOCAL:
            # forget lowest support
            victim = min(local.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
            del local[victim]
            org["forgotten_broader"] = int(org.get("forgotten_broader") or 0)  # leave counter
        lid = f"L{int(org.get('next_local') or 1)}"
        org["next_local"] = int(org.get("next_local") or 1) + 1
        row = {
            "local_id": lid,
            "key": key,
            "domain": domain,
            "action": action,
            "antecedent": ant,
            "predicted_sum": {k: 0.0 for k in real},
            "predicted_n": 0,
            "support": 0,
            "evidence": [],
            "provenance": [],
            "status": "ACTIVE",
            "depth": 0,
        }
        local[key] = row
    # EMA-ish mean
    n = int(row["predicted_n"]) + 1
    for k, v in real.items():
        prev = float((row["predicted_sum"]).get(k, 0.0))
        # store running sum then mean at read
        row["predicted_sum"][k] = prev + float(v)
    row["predicted_n"] = n
    row["support"] = int(row["support"]) + 1
    ev = row.setdefault("evidence", [])
    ev.append({"tick": tick, "realized": real, "raw_id": raw_id})
    row["evidence"] = ev[-MAX_EVIDENCE_PER:]
    if not org.get("ablate_provenance"):
        prov = row.setdefault("provenance", [])
        prov.append({"tick": tick, "kind": "LOCAL_OBS", "raw_id": raw_id})
        row["provenance"] = prov[-MAX_PROVENANCE:]

    lid = row["local_id"]
    recent = org.setdefault("recent_local_ids", [])
    recent.append({"tick": tick, "local_id": lid, "domain": domain, "key": key})
    org["recent_local_ids"] = recent[-32:]

    _update_relations(org, lid, tick)
    _maybe_form_broader(org, tick)
    return lid


def _mean_pred(row: dict[str, Any]) -> dict[str, float]:
    n = max(1, int(row.get("predicted_n") or 1))
    return {k: float(v) / n for k, v in (row.get("predicted_sum") or {}).items()}


def _update_relations(org: dict[str, Any], lid: str, tick: int) -> None:
    if org.get("ablate_relations"):
        return
    recent = [r for r in (org.get("recent_local_ids") or []) if r.get("local_id") != lid]
    if not recent:
        return
    # co-occurrence with other domains in recent window
    rel = org.setdefault("relations", {})
    for other in recent[-8:]:
        oid = other["local_id"]
        if oid == lid:
            continue
        a, b = sorted([lid, oid])
        rkey = f"{a}||{b}"
        row = rel.get(rkey)
        if row is None:
            if len(rel) >= MAX_RELATIONS:
                victim = min(rel.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
                del rel[victim]
            row = {"ids": [a, b], "support": 0, "last_tick": tick, "evidence": []}
            rel[rkey] = row
        row["support"] = int(row["support"]) + 1
        row["last_tick"] = tick
        ev = row.setdefault("evidence", [])
        ev.append(tick)
        row["evidence"] = ev[-MAX_EVIDENCE_PER:]


def _cluster_outcome(pred: dict[str, float]) -> str:
    return _sig({k: round(float(v), 2) for k, v in sorted(pred.items())})


def _maybe_form_broader(org: dict[str, Any], tick: int) -> None:
    """Form candidate broader structure from repeated cross-domain co-occurrence.

    Persists only with bounded support. Random-cluster mode groups arbitrarily
    for control experiments.
    """
    if org.get("ablate_broader"):
        return
    local = org.get("local") or {}
    rel = org.get("relations") or {}
    # gather strongly supported relations
    strong = [r for r in rel.values() if int(r.get("support") or 0) >= MIN_SUPPORT_REL]
    if len(strong) < 1:
        return

    # Build co-active sets from recent multi-domain presence
    recent = org.get("recent_local_ids") or []
    by_tick: dict[int, set[str]] = {}
    for r in recent:
        by_tick.setdefault(int(r["tick"]), set()).add(r["local_id"])
    multi = [ids for ids in by_tick.values() if len(ids) >= 2]
    if not multi:
        return

    # Candidate key: frozenset of local_ids appearing together, plus outcome cluster
    # Use most recent multi set
    ids = frozenset(multi[-1])
    if len(ids) < 2:
        return

    if org.get("random_cluster"):
        # scramble membership for control
        all_ids = [row["local_id"] for row in local.values()]
        if len(all_ids) < 2:
            return
        # pseudo-random from tick
        pick = sorted(all_ids, key=lambda x: sha1(f"{tick}:{x}".encode()).hexdigest())[: max(2, len(ids))]
        ids = frozenset(pick)

    members = [local[k] for k in local if local[k]["local_id"] in ids]
    if len(members) < 2:
        # map by local_id
        members = [row for row in local.values() if row["local_id"] in ids]
    if len(members) < 2:
        return
    # domains should preferably differ for cross-domain claim (not required)
    domains = {m.get("domain") for m in members}
    outcome_parts = {}
    for m in members:
        for k, v in _mean_pred(m).items():
            outcome_parts[f"{m['domain']}:{k}"] = v
    ocluster = _cluster_outcome(outcome_parts)
    bkey = sha1(("|".join(sorted(ids)) + "||" + ocluster).encode()).hexdigest()[:14]

    broader = org.setdefault("broader", {})
    row = broader.get(bkey)
    if row is None:
        if len(broader) >= MAX_BROADER:
            victim = min(broader.items(), key=lambda kv: int(kv[1].get("support") or 0))[0]
            del broader[victim]
            org["forgotten_broader"] = int(org.get("forgotten_broader") or 0) + 1
        # depth = 1 + max member depth
        depth = 1 + max(int(m.get("depth") or 0) for m in members)
        if depth > int(org.get("depth_cap") or MAX_DEPTH):
            return
        bid = f"B{int(org.get('next_broader') or 1)}"
        org["next_broader"] = int(org.get("next_broader") or 1) + 1
        row = {
            "broader_id": bid,
            "key": bkey,
            "member_ids": sorted(ids),
            "domains": sorted(domains),
            "support": 0,
            "predicted_sum": {k: 0.0 for k in outcome_parts},
            "predicted_n": 0,
            "evidence": [],
            "provenance": [],
            "contradictions": 0,
            "revisions": 0,
            "status": "ACTIVE",
            "depth": depth,
            "formed_tick": tick,
            "predictive_delta_sum": 0.0,
            "predictive_delta_n": 0,
        }
        broader[bkey] = row
        org["formation_events"] = int(org.get("formation_events") or 0) + 1

    # update broader prediction from member means
    n = int(row["predicted_n"]) + 1
    for k, v in outcome_parts.items():
        row["predicted_sum"][k] = float(row["predicted_sum"].get(k, 0.0)) + float(v)
    row["predicted_n"] = n
    row["support"] = int(row["support"]) + 1
    ev = row.setdefault("evidence", [])
    ev.append({"tick": tick, "members": sorted(ids), "outcome": outcome_parts})
    row["evidence"] = ev[-MAX_EVIDENCE_PER:]
    if not org.get("ablate_provenance"):
        prov = row.setdefault("provenance", [])
        prov.append({"tick": tick, "kind": "BROADER_OBS", "members": sorted(ids)})
        row["provenance"] = prov[-MAX_PROVENANCE:]


def predict_local_only(
    org: dict[str, Any],
    *,
    domain: str,
    fragment: dict[str, float],
    action: str,
) -> dict[str, Any]:
    if org.get("ablate_local"):
        return {"status": "NO_LOCAL", "mode": "local_only"}
    key = _local_key(domain, _qfrag(fragment), action)
    row = (org.get("local") or {}).get(key)
    if not row or int(row.get("support") or 0) < MIN_SUPPORT_LOCAL:
        return {"status": "NO_LOCAL", "mode": "local_only", "key": key}
    return {
        "status": "MATCH",
        "mode": "local_only",
        "key": key,
        "local_id": row["local_id"],
        "support": row["support"],
        "predicted": _mean_pred(row),
        "depth": int(row.get("depth") or 0),
    }


def _active_broader_for_local(org: dict[str, Any], local_id: str) -> list[dict[str, Any]]:
    if org.get("ablate_broader"):
        return []
    out = []
    for row in (org.get("broader") or {}).values():
        if row.get("status") != "ACTIVE":
            continue
        if int(row.get("support") or 0) < MIN_SUPPORT_BROADER:
            continue
        if local_id in (row.get("member_ids") or []):
            out.append(row)
    out.sort(key=lambda r: (-int(r.get("support") or 0), r.get("broader_id")))
    return out


def predict_broader_conditioned(
    org: dict[str, Any],
    *,
    domain: str,
    fragment: dict[str, float],
    action: str,
    co_evidence_local_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Local evidence + acquired broader candidates (if any).

    Broader influence: if a supported broader candidate includes the matched
    local id and overlaps co-evidence ids, override/augment the predicted
    channels using the broader mean for this domain.
    """
    base = predict_local_only(org, domain=domain, fragment=fragment, action=action)
    if base.get("status") != "MATCH":
        return {**base, "mode": "broader_conditioned", "broader_used": None}

    lid = base["local_id"]
    candidates = _active_broader_for_local(org, lid)
    co = set(co_evidence_local_ids or [])
    chosen = None
    for row in candidates:
        members = set(row.get("member_ids") or [])
        if co and members.intersection(co):
            chosen = row
            break
        if not co and len(members) >= 2:
            chosen = row
            break
    if chosen is None:
        return {
            **base,
            "mode": "broader_conditioned",
            "broader_used": None,
            "predicted": dict(base["predicted"]),
            "note": "no_supported_broader",
        }

    # Extract domain-scoped prediction from broader mean
    bmean = _mean_pred(chosen)
    prefix = f"{domain}:"
    aug = {k[len(prefix):]: float(v) for k, v in bmean.items() if k.startswith(prefix)}
    if not aug:
        # fall back to blending all broader channels into local keys present
        aug = dict(base["predicted"])
        for k, v in bmean.items():
            if ":" in k:
                kk = k.split(":", 1)[1]
                if kk in aug:
                    aug[kk] = 0.5 * float(aug[kk]) + 0.5 * float(v)
    else:
        # merge: broader channels replace local where present
        merged = dict(base["predicted"])
        merged.update(aug)
        aug = merged

    return {
        "status": "MATCH",
        "mode": "broader_conditioned",
        "key": base["key"],
        "local_id": lid,
        "support": base["support"],
        "predicted": aug,
        "broader_used": chosen.get("broader_id"),
        "broader_support": chosen.get("support"),
        "broader_depth": chosen.get("depth"),
        "member_ids": list(chosen.get("member_ids") or []),
    }


def additional_predictive_value(
    local_pred: dict[str, float],
    broader_pred: dict[str, float],
    realized: dict[str, float],
) -> dict[str, float]:
    """Researcher-side: error(local) - error(broader). Positive => broader helps."""
    def l1(p: dict[str, float]) -> float:
        keys = set(p) | set(realized)
        return sum(abs(float(realized.get(k, 0.0)) - float(p.get(k, 0.0))) for k in keys)

    e_l = l1(local_pred)
    e_b = l1(broader_pred)
    return {
        "local_error": e_l,
        "broader_error": e_b,
        "predictive_delta": e_l - e_b,
    }


def record_pae(org: dict[str, Any], *, tick: int, predicted: dict[str, float], linked: str | None) -> None:
    pae = org.setdefault("prediction_at_event", {})
    if len(pae) >= int(org.get("pae_capacity") or 64):
        # drop oldest by tick
        oldest = min(pae.items(), key=lambda kv: int(kv[1].get("tick") or 0))[0]
        del pae[oldest]
    pid = f"PAE{tick}"
    pae[pid] = {
        "tick": tick,
        "predicted_frozen": deepcopy(predicted),
        "linked": linked,
    }


def revise_broader_on_mismatch(
    org: dict[str, Any],
    *,
    broader_id: str,
    tick: int,
    realized: dict[str, float],
    domain: str,
) -> dict[str, Any]:
    """Evidence-driven revision; preserves PAE (no retrodiction)."""
    for row in (org.get("broader") or {}).values():
        if row.get("broader_id") != broader_id:
            continue
        pred = _mean_pred(row)
        prefix = f"{domain}:"
        err = 0.0
        n = 0
        for k, v in realized.items():
            pk = prefix + k
            if pk in pred:
                err += abs(float(v) - float(pred[pk]))
                n += 1
        if n and err / n > 0.15:
            row["contradictions"] = int(row.get("contradictions") or 0) + 1
            # soft revise: fold realized into predicted_sum
            for k, v in realized.items():
                pk = prefix + k
                row["predicted_sum"][pk] = float(row["predicted_sum"].get(pk, 0.0)) + float(v)
            row["predicted_n"] = int(row["predicted_n"]) + 1
            row["revisions"] = int(row.get("revisions") or 0) + 1
            org["revision_events"] = int(org.get("revision_events") or 0) + 1
            if not org.get("ablate_provenance"):
                prov = row.setdefault("provenance", [])
                prov.append({"tick": tick, "kind": "REVISION", "error": err})
                row["provenance"] = prov[-MAX_PROVENANCE:]
            if int(row["contradictions"]) >= 8:
                row["status"] = "SUPERSEDED"
            return {"revised": True, "error": err, "status": row["status"]}
        return {"revised": False, "error": err, "status": row.get("status")}
    return {"revised": False, "error": None, "status": "MISSING"}


def snapshot(org: dict[str, Any]) -> dict[str, Any]:
    local = org.get("local") or {}
    rel = org.get("relations") or {}
    broader = org.get("broader") or {}
    depths = [int(r.get("depth") or 0) for r in broader.values()]
    dist: dict[str, int] = {}
    for d in depths:
        dist[str(d)] = dist.get(str(d), 0) + 1
    return {
        "local_structure_count": len(local),
        "relation_count": len(rel),
        "broader_candidate_count": len(broader),
        "retained_broader_count": sum(1 for r in broader.values() if r.get("status") == "ACTIVE"),
        "candidate_depth_distribution": dist,
        "formation_events": org.get("formation_events"),
        "revision_events": org.get("revision_events"),
        "forgotten_broader": org.get("forgotten_broader"),
        "ablations": {
            "broader": bool(org.get("ablate_broader")),
            "local": bool(org.get("ablate_local")),
            "relations": bool(org.get("ablate_relations")),
            "provenance": bool(org.get("ablate_provenance")),
            "random_cluster": bool(org.get("random_cluster")),
        },
        "metrics_affect_cognition": bool(org.get("metrics_affect_cognition")),
        "leak_tokens": audit_forbidden_in_cognition(
            {
                "local_keys": list(local.keys())[:20],
                "broader": [{k: r.get(k) for k in ("broader_id", "member_ids", "domains", "depth", "status")} for r in list(broader.values())[:10]],
            }
        ),
    }


def expand_broader(org: dict[str, Any], broader_id: str) -> dict[str, Any]:
    """Researcher-only expandable view."""
    for row in (org.get("broader") or {}).values():
        if row.get("broader_id") == broader_id:
            return {
                "RESEARCHER_ONLY": True,
                "row": deepcopy(row),
                "predicted_mean": _mean_pred(row),
                "members": [
                    deepcopy(r)
                    for r in (org.get("local") or {}).values()
                    if r.get("local_id") in (row.get("member_ids") or [])
                ],
            }
    return {"RESEARCHER_ONLY": True, "row": None}


def memory_bytes(org: dict[str, Any]) -> int:
    import json
    return len(json.dumps({
        "local": org.get("local"),
        "relations": org.get("relations"),
        "broader": org.get("broader"),
        "prediction_at_event": org.get("prediction_at_event"),
    }, sort_keys=True).encode("utf-8"))
