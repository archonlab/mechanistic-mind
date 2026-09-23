"""Experimental relation-specific predictive relevance.

Default OFF. Lives on predictive-equivalence classes; not a global sensor mask.

For relation R (a continuation class):
- keys that vary across members with equivalent continuation may not veto R;
- keys whose class span does not overlap another class with a different
  continuation remain discriminative for R.

Not: attention, salience, FIELD_A special-case, hand-authored ignore lists.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.research.predictive_compression import _sig
from mechanistic_mind.research.predictive_equivalence import (
    CONTINUATION_LINF,
    MIN_CLASS_SUPPORT,
    _class_mean_c,
    _copy_float_map,
    _floats,
    _in_aabb,
    _inspect_counter_inc,
    _linf,
    _predict_from_delta,
    class_index_enabled,
    iter_active_classes_for_action,
)


VARY_EPS = 1e-12
MAX_REL_PROV = 12


def empty_meta() -> dict[str, Any]:
    return {
        "enabled": False,
        "refreshes": 0,
        "retrieves": 0,
        "matches": 0,
        "conflicts": 0,
        "insufficient": 0,
        "next_gear_missing": 0,
    }


def snapshot(eq_store: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta or {}
    rows = []
    for cls in (eq_store.get("classes") or {}).values():
        rel = cls.get("relevance") or {}
        rows.append({
            "class_id": cls.get("id"),
            "status": cls.get("status"),
            "support": cls.get("support"),
            "relevant": list(rel.get("relevant") or [])[:12],
            "allowed_variation": list(rel.get("allowed_variation") or [])[:12],
            "tight": list(rel.get("tight") or [])[:8],
            "revised_at": rel.get("revised_at"),
        })
    return {
        "enabled": bool(meta.get("enabled")),
        "class_n": len(rows),
        "refreshes": meta.get("refreshes"),
        "matches": meta.get("matches"),
        "conflicts": meta.get("conflicts"),
        "insufficient": meta.get("insufficient"),
        "next_gear_missing": meta.get("next_gear_missing"),
        "relations": rows[:16],
        "note": "LEARNED_RELEVANCE_STRUCTURE — not attention, not physical ground truth",
    }


def aabb_key_audit(aabb: dict[str, Any], fragment: dict[str, float]) -> dict[str, str]:
    """PASS/FAIL per AABB key for a query. Full-observation veto diagnostic."""
    frag = _floats(fragment)
    out: dict[str, str] = {}
    for k, span in (aabb or {}).items():
        lo, hi = float(span[0]), float(span[1])
        if k not in frag:
            out[k] = "FAIL_MISSING"
            continue
        x = float(frag[k])
        out[k] = "PASS" if (lo - 1e-12) <= x <= (hi + 1e-12) else "FAIL"
    return out


def refresh(eq_store: dict[str, Any], *, tick: int = 0, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    """Recompute per-class relevance from members vs other classes. Bounded, revisable."""
    if meta is not None:
        meta["refreshes"] = int(meta.get("refreshes") or 0) + 1
    classes = [c for c in (eq_store.get("classes") or {}).values() if c.get("status") == "ACTIVE"]
    tau = float(eq_store.get("continuation_linf") or eq_store.get("continuation_l1") or CONTINUATION_LINF)
    for cls in classes:
        others = [o for o in classes if o.get("id") != cls.get("id") and o.get("action") == cls.get("action")]
        cls["relevance"] = _relevance_for(cls, others, tau=tau, tick=int(tick))
    return {"status": "REFRESHED", "n": len(classes)}


def _relevance_for(cls: dict[str, Any], others: list[dict[str, Any]], *, tau: float, tick: int) -> dict[str, Any]:
    aabb = {k: (float(v[0]), float(v[1])) for k, v in (cls.get("aabb") or {}).items()}
    mean = _class_mean_c(cls)
    # Continuation L-inf vs other class means does not depend on AABB key.
    # Precompute the dissimilar-others list once (same membership / order as the
    # former inner-loop continue-on-_linf path) so we do not re-run _linf per key.
    distinct_others: list[dict[str, Any]] = []
    for other in others:
        if _linf(mean, _class_mean_c(other)) > tau:
            distinct_others.append(other)
    allowed: list[str] = []
    tight: list[str] = []
    discriminative: list[str] = []
    for k, (lo, hi) in aabb.items():
        if (hi - lo) > VARY_EPS:
            allowed.append(k)
        else:
            tight.append(k)
        for other in distinct_others:
            ospan = (other.get("aabb") or {}).get(k)
            if not ospan:
                continue
            olo, ohi = float(ospan[0]), float(ospan[1])
            if hi < olo - VARY_EPS or lo > ohi + VARY_EPS:
                discriminative.append(k)
                break
    # Retrieval constraints: discriminative keys (partition continuations)
    # plus tight keys that never varied inside this relation.
    # Keys that varied under equivalent continuation do not veto.
    relevant = sorted(set(discriminative) | set(tight))
    prev = cls.get("relevance") or {}
    changed = set(prev.get("relevant") or []) != set(relevant)
    prov = list(prev.get("provenance") or [])
    if changed:
        prov.append({
            "type": "relevance_revised" if prev else "relevance_formed",
            "tick": int(tick),
            "relevant": relevant[:8],
            "allowed_variation": allowed[:8],
        })
        prov = prov[-MAX_REL_PROV:]
    return {
        "relevant": relevant,
        "discriminative": sorted(set(discriminative)),
        "allowed_variation": sorted(allowed),
        "tight": sorted(tight),
        "support": int(cls.get("support") or 0),
        "revised_at": int(tick) if changed else prev.get("revised_at"),
        "provenance": prov,
    }


def _partial_in(fragment: dict[str, float], aabb: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    """Test query against a key subset. Missing relevant key → insufficient evidence."""
    if not keys:
        return {"ok": True, "gate": "no_discriminative_or_tight_keys"}
    for k in keys:
        if k not in fragment:
            return {"ok": False, "gate": "insufficient_evidence", "missing": k}
        span = aabb.get(k)
        if not span:
            return {"ok": False, "gate": "insufficient_evidence", "missing": k}
        lo, hi = float(span[0]), float(span[1])
        x = float(fragment[k])
        if x < lo - 1e-12 or x > hi + 1e-12:
            return {"ok": False, "gate": "relevant_key_out_of_span", "key": k, "x": x, "lo": lo, "hi": hi}
    return {"ok": True, "gate": "partial_span"}


def _retrieve_collect_hits_full_scan(
    eq_store: dict[str, Any],
    frag: dict[str, float],
    act: str,
    *,
    meta: dict[str, Any] | None,
    count: bool,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Legacy full class scan (oracle). Not used in production retrieve."""
    hits: list[tuple[dict[str, Any], dict[str, Any]]] = []
    n = 0
    for cls in (eq_store.get("classes") or {}).values():
        n += 1
        if cls.get("status") != "ACTIVE" or cls.get("action") != act:
            continue
        if int(cls.get("support") or 0) < MIN_CLASS_SUPPORT:
            continue
        rel = cls.get("relevance") or {}
        keys = list(rel.get("relevant") or [])
        aabb = cls.get("aabb") or {}
        gate = _partial_in(frag, aabb, keys)
        if gate.get("gate") == "insufficient_evidence":
            if count and meta is not None:
                meta["insufficient"] = int(meta.get("insufficient") or 0) + 1
            continue
        if gate.get("ok"):
            hits.append((cls, gate))
    _inspect_counter_inc(eq_store, n)
    return hits


def _retrieve_collect_hits_indexed(
    eq_store: dict[str, Any],
    frag: dict[str, float],
    act: str,
    *,
    meta: dict[str, Any] | None,
    count: bool,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Action-bucket narrowing; final authority remains _partial_in + support max."""
    hits: list[tuple[dict[str, Any], dict[str, Any]]] = []
    n = 0
    for cls in iter_active_classes_for_action(eq_store, act):
        n += 1
        if int(cls.get("support") or 0) < MIN_CLASS_SUPPORT:
            continue
        rel = cls.get("relevance") or {}
        keys = list(rel.get("relevant") or [])
        aabb = cls.get("aabb") or {}
        gate = _partial_in(frag, aabb, keys)
        if gate.get("gate") == "insufficient_evidence":
            if count and meta is not None:
                meta["insufficient"] = int(meta.get("insufficient") or 0) + 1
            continue
        if gate.get("ok"):
            hits.append((cls, gate))
    _inspect_counter_inc(eq_store, n)
    return hits


def _retrieve_from_hits(
    eq_store: dict[str, Any],
    frag: dict[str, float],
    hits: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    meta: dict[str, Any] | None,
    count: bool,
) -> dict[str, Any]:
    if not hits:
        return {"status": "NO_MATCH", "predicted": {}, "gate": "no_partial_class_span"}
    tau = float(eq_store.get("continuation_linf") or eq_store.get("continuation_l1") or CONTINUATION_LINF)
    means = [_class_mean_c(c) for c, _ in hits]
    if len(hits) > 1 and any(_linf(means[0], m) > tau for m in means[1:]):
        if count and meta is not None:
            meta["conflicts"] = int(meta.get("conflicts") or 0) + 1
            meta["next_gear_missing"] = int(meta.get("next_gear_missing") or 0) + 1
        return {
            "status": "CONFLICT",
            "predicted": {},
            "gate": "conflicting_partial_matches",
            "next_gear_missing": True,
            "n_hits": len(hits),
            "class_ids": [c.get("id") for c, _ in hits],
            "source": "predictive_relevance",
        }
    cls, gate = max(hits, key=lambda t: int(t[0].get("support") or 0))
    if count and meta is not None:
        meta["matches"] = int(meta.get("matches") or 0) + 1
    rel = cls.get("relevance") or {}
    full_aabb = cls.get("aabb") or {}
    full_ok = _in_aabb(frag, {k: (float(v[0]), float(v[1])) for k, v in full_aabb.items()}) if full_aabb else False
    return {
        "status": "MATCH",
        "predicted": _predict_from_delta(frag, _class_mean_c(cls)),
        "support": int(cls.get("support") or 0),
        "class_id": cls.get("id"),
        "n_members": len(cls.get("members") or {}),
        "source": "predictive_relevance",
        "raw_antecedent_sig": _sig(frag),
        "relevant": list(rel.get("relevant") or []),
        "allowed_variation": list(rel.get("allowed_variation") or []),
        "tight": list(rel.get("tight") or []),
        "discriminative": list(rel.get("discriminative") or []),
        "full_aabb_would_match": bool(full_ok),
        "gate": gate.get("gate") or "partial_span",
        "not_attention": True,
    }


def _retrieve_full_scan_reference(
    eq_store: dict[str, Any],
    fragment: dict[str, float],
    action: str,
    *,
    meta: dict[str, Any] | None = None,
    count: bool = False,
) -> dict[str, Any]:
    """Private oracle: pre-index full-scan retrieve. Tests/debug only."""
    if meta is not None and meta.get("enabled") is False:
        return {"status": "DISABLED", "predicted": {}}
    if eq_store.get("enabled") is False:
        return {"status": "DISABLED", "predicted": {}}
    if count and meta is not None:
        meta["retrieves"] = int(meta.get("retrieves") or 0) + 1
    frag = _floats(fragment)
    act = str(action)
    hits = _retrieve_collect_hits_full_scan(eq_store, frag, act, meta=meta, count=count)
    return _retrieve_from_hits(eq_store, frag, hits, meta=meta, count=count)


def retrieve(
    eq_store: dict[str, Any],
    fragment: dict[str, float],
    action: str,
    *,
    meta: dict[str, Any] | None = None,
    count: bool = True,
) -> dict[str, Any]:
    """Contextual partial retrieval over relation-specific relevant keys."""
    if meta is not None and meta.get("enabled") is False:
        return {"status": "DISABLED", "predicted": {}}
    if eq_store.get("enabled") is False:
        return {"status": "DISABLED", "predicted": {}}
    if count and meta is not None:
        meta["retrieves"] = int(meta.get("retrieves") or 0) + 1
    frag = _floats(fragment)
    act = str(action)
    if class_index_enabled():
        hits = _retrieve_collect_hits_indexed(eq_store, frag, act, meta=meta, count=count)
    else:
        hits = _retrieve_collect_hits_full_scan(eq_store, frag, act, meta=meta, count=count)
    return _retrieve_from_hits(eq_store, frag, hits, meta=meta, count=count)


def diagnostic(eq_store: dict[str, Any], fragment: dict[str, float], action: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    got = retrieve(eq_store, fragment, action, meta=meta, count=False)
    rel = {}
    cid = got.get("class_id")
    if cid:
        rel = ((eq_store.get("classes") or {}).get(cid) or {}).get("relevance") or {}
    aabb = {}
    if cid:
        aabb = ((eq_store.get("classes") or {}).get(cid) or {}).get("aabb") or {}
    return {
        "kind": "LEARNED_RELEVANCE_STRUCTURE",
        "not_physical_ground_truth": True,
        "not_attention": True,
        "raw_fragment": _floats(fragment),
        "raw_sig": _sig(_floats(fragment)),
        "action": action,
        "retrieved": got,
        "relation": {
            "id": cid,
            "relevant": list(rel.get("relevant") or got.get("relevant") or []),
            "allowed_variation": list(rel.get("allowed_variation") or got.get("allowed_variation") or []),
            "continuation": _copy_float_map(
                _class_mean_c((eq_store.get("classes") or {}).get(cid) or {}) if cid else {}
            ),
            "support": got.get("support"),
        },
        "full_aabb_audit": aabb_key_audit(aabb, fragment) if aabb else {},
    }
