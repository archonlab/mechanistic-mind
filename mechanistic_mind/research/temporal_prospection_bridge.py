"""Experimental adapter: TPS MATCH → 4.23 entry step.

Default OFF. Transports existing trajectory-conditioned predictions into the
first-step contract already consumed by prospective composition.

Does not predict, invent actions, fabricate support, resolve conflicts,
override snapshot lookup, or select.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.research.predictive_equivalence import _floats


def empty_meta() -> dict[str, Any]:
    return {
        "enabled": False,
        "bridged": 0,
        "skipped_no_match": 0,
        "skipped_conflict_unresolved": 0,
        "skipped_empty_continuation": 0,
        "conflicts_passed": 0,
        "note": "TEMPORAL_PROSPECTION_BRIDGE — transport only, not a predictor",
    }


def snapshot(meta: dict[str, Any] | None) -> dict[str, Any]:
    m = meta or {}
    return {
        "enabled": bool(m.get("enabled")),
        "bridged": m.get("bridged"),
        "skipped_no_match": m.get("skipped_no_match"),
        "skipped_empty_continuation": m.get("skipped_empty_continuation"),
        "conflicts_passed": m.get("conflicts_passed"),
        "note": "adapter; does not create predictions",
    }


def as_entry_step(
    tps_result: dict[str, Any],
    *,
    action: str,
    present: dict[str, float] | None = None,
) -> dict[str, Any] | None:
    """Map a TPS MATCH (or MATCH-like candidate) onto a 4.23 first-step edge.

    Support is the TPS class support. Reliability is not invented (4.23
    reliability is snapshot-transition dispersion).
    """
    if tps_result.get("status") != "MATCH":
        return None
    cont = tps_result.get("predicted_continuation") or {}
    if not cont:
        # predicted may still hold continuation channels
        dfrag_keys = set()
        pred = tps_result.get("predicted") or {}
        cont = {
            str(k): float(v)
            for k, v in pred.items()
            if isinstance(v, (int, float)) and not isinstance(v, bool) and not str(k).startswith("d")
        }
    if not cont:
        return None
    support = tps_result.get("support")
    try:
        support_i = int(support or 0)
    except (TypeError, ValueError):
        support_i = 0
    if support_i <= 0:
        return None
    return {
        "status": "MATCH",
        "action": str(action),
        "predicted": dict(cont),
        "support": support_i,
        "reliability": None,
        "reliability_mapped": False,
        "depth": 1,
        "key": (
            f"temporal|{tps_result.get('class_id')}|L{tps_result.get('lag')}|"
            f"{tps_result.get('delta_sig')}"
        ),
        "transition_id": tps_result.get("class_id"),
        "prediction_source": "TEMPORAL",
        "temporal_structure_id": tps_result.get("class_id"),
        "history_span": tps_result.get("window_n"),
        "lag": tps_result.get("lag"),
        "not_snapshot_transition": True,
        "not_independent_of_tps": True,
        "provenance": {
            "source": "temporal_predictive_structure",
            "bridge": "temporal_prospection_bridge",
            "class_id": tps_result.get("class_id"),
            "lag": tps_result.get("lag"),
            "support": support_i,
            "delta_sig": tps_result.get("delta_sig"),
            "window_n": tps_result.get("window_n"),
            "recent": deepcopy(tps_result.get("recent") or []),
            "raw_present_sig": tps_result.get("raw_present_sig"),
            "present": _floats(present) if present is not None else {},
        },
    }


def collect_entry_steps(
    store: dict[str, Any],
    present: dict[str, float],
    actions: list[str],
    *,
    meta: dict[str, Any] | None = None,
    tps_meta: dict[str, Any] | None = None,
    predictions: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Build 4.23 entry steps from existing TPS retrieval. No new prediction.

    Reuses MATCH/CONFLICT already present in `predictions` when possible.
    TEMPORAL_CONFLICT candidates are passed through, not arbitrated.
    """
    if meta is None or not meta.get("enabled"):
        return []
    if store.get("enabled") is False:
        return []
    by_action: dict[str, dict[str, Any]] = {}
    for row in predictions or []:
        if row.get("source") != "temporal_predictive_structure":
            continue
        act = str(row.get("action") or "")
        if row.get("temporal_conflict"):
            by_action.setdefault(act, {"status": "TEMPORAL_CONFLICT", "candidates": []})
            by_action[act].setdefault("candidates", []).append(row.get("result") or {})
        else:
            by_action[act] = row.get("result") or {}
    entries: list[dict[str, Any]] = []
    for act in actions:
        got = by_action.get(act)
        if got is None:
            got = tps.retrieve(store, present, act, meta=tps_meta, count=False)
        if got.get("status") == "MATCH":
            step = as_entry_step(got, action=act, present=present)
            if step is None:
                meta["skipped_empty_continuation"] = int(meta.get("skipped_empty_continuation") or 0) + 1
                continue
            entries.append(step)
            meta["bridged"] = int(meta.get("bridged") or 0) + 1
        elif got.get("status") == "TEMPORAL_CONFLICT":
            meta["conflicts_passed"] = int(meta.get("conflicts_passed") or 0) + 1
            meta["skipped_conflict_unresolved"] = int(meta.get("skipped_conflict_unresolved") or 0) + 1
            for cand in got.get("candidates") or []:
                c = dict(cand)
                if c.get("status") != "MATCH":
                    c["status"] = "MATCH"
                step = as_entry_step(c, action=act, present=present)
                if step is None:
                    continue
                step["temporal_conflict"] = True
                step["next_gear_missing"] = True
                entries.append(step)
                meta["bridged"] = int(meta.get("bridged") or 0) + 1
        else:
            meta["skipped_no_match"] = int(meta.get("skipped_no_match") or 0) + 1
    return entries


def diagnostic(entries: list[dict[str, Any]], composition: dict[str, Any] | None = None) -> dict[str, Any]:
    conts = list((composition or {}).get("continuations") or [])
    temporal = [c for c in conts if (c.get("prediction_source") == "TEMPORAL") or any(
        (e or {}).get("prediction_source") == "TEMPORAL" for e in (c.get("edges") or [])
    )]
    snapshot = [c for c in conts if c.get("prediction_source") == "SNAPSHOT" or (
        (c.get("edges") or [{}])[0].get("prediction_source") == "SNAPSHOT"
    )]
    return {
        "kind": "TEMPORAL_PROSPECTION_BRIDGE",
        "not_planning": True,
        "not_time_awareness": True,
        "n_entry_steps": len(entries),
        "n_temporal_continuations": len(temporal),
        "n_snapshot_continuations": len(snapshot),
        "entry_lags": [e.get("lag") for e in entries],
        "entry_supports": [e.get("support") for e in entries],
        "prediction_sources": sorted({
            str(c.get("prediction_source") or ((c.get("edges") or [{}])[0].get("prediction_source")))
            for c in conts
        }),
    }
