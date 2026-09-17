"""Experimental adapter: predicted future context → read-only action lookup.

Default OFF. Uses an existing TPS predicted fragment as a 4.23 antecedent
and retrieves already-learned action-conditioned continuations.

Does not predict, invent actions, assign utility, write experience, increment
support, clone the world, or select. Predicted context never becomes realized
biography.

Action appropriate in a future context is recorded as a future_action. It is
not collapsed into a present first_action.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research import temporal_predictive_structure as tps
from mechanistic_mind.research.predictive_equivalence import _floats
from mechanistic_mind.research.predictive_compression import _sig

# Existing 4.23 bounds; do not enlarge to make examples pass.
MAX_CONTEXTS = 4
MAX_ACTIONS_PER_CONTEXT = 4
MAX_BRANCHES = 8
MAX_DEPTH = 3
ENV_ACTION = "WAIT"


def empty_meta() -> dict[str, Any]:
    return {
        "enabled": False,
        "predicted_contexts": 0,
        "lookups": 0,
        "matched": 0,
        "unmodeled": 0,
        "branches": 0,
        "skipped_no_tps": 0,
        "skipped_empty_context": 0,
        "skipped_disabled": 0,
        "wrote_experience": False,
        "support_incremented": False,
        "imagined_experience": False,
        "note": "PREDICTED_CONTEXT_PROSPECTION — read-only composition, not imagined experience",
    }


def snapshot(meta: dict[str, Any] | None) -> dict[str, Any]:
    m = meta or {}
    return {
        "enabled": bool(m.get("enabled")),
        "predicted_contexts": m.get("predicted_contexts"),
        "lookups": m.get("lookups"),
        "matched": m.get("matched"),
        "unmodeled": m.get("unmodeled"),
        "branches": m.get("branches"),
        "wrote_experience": bool(m.get("wrote_experience")),
        "support_incremented": bool(m.get("support_incremented")),
        "imagined_experience": bool(m.get("imagined_experience")),
        "note": "adapter; does not create predictions or evidence",
    }


def predicted_fragment(tps_result: dict[str, Any] | None) -> dict[str, float]:
    """Continuation channels of an existing TPS result. No new prediction."""
    got = tps_result or {}
    cont = got.get("predicted_continuation")
    if isinstance(cont, dict) and cont:
        return _floats(cont)
    pred = got.get("predicted") or {}
    if isinstance(pred, dict):
        out = {
            str(k): float(v)
            for k, v in pred.items()
            if isinstance(v, (int, float))
            and not isinstance(v, bool)
            and not str(k).startswith("d")
        }
        if out:
            return out
    return {}


def collect_predicted_contexts(
    tps_store: dict[str, Any] | None,
    present: dict[str, float],
    *,
    env_action: str = ENV_ACTION,
    predictions: list[dict[str, Any]] | None = None,
    tps_meta: dict[str, Any] | None = None,
    lag: int | None = None,
    meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Read existing TPS MATCH / TEMPORAL_CONFLICT candidates as future contexts.

    Does not generate a context if TPS cannot retrieve one.
    """
    if meta is not None and not meta.get("enabled"):
        meta["skipped_disabled"] = int(meta.get("skipped_disabled") or 0) + 1
        return []
    if not tps_store or tps_store.get("enabled") is False:
        if meta is not None:
            meta["skipped_no_tps"] = int(meta.get("skipped_no_tps") or 0) + 1
        return []

    lags = [int(lag)] if lag is not None else [1, 2, 4]
    by_lag: dict[int, dict[str, Any]] = {}
    for row in predictions or []:
        if row.get("source") != "temporal_predictive_structure":
            continue
        if str(row.get("action") or "") != str(env_action):
            continue
        L = int((row.get("result") or {}).get("lag") or 0)
        if L not in lags:
            continue
        by_lag.setdefault(L, {"candidates": []})
        if row.get("temporal_conflict"):
            by_lag[L]["status"] = "TEMPORAL_CONFLICT"
            by_lag[L]["candidates"].append(row.get("result") or {})
        else:
            by_lag[L]["got"] = row.get("result") or {}

    contexts: list[dict[str, Any]] = []
    seen: set[str] = set()
    for L in lags:
        packed = by_lag.get(L) or {}
        got = packed.get("got")
        if got is None:
            got = tps.retrieve(
                tps_store,
                present,
                env_action,
                lag=L,
                count=False,
                meta=tps_meta,
            )
        rows = []
        status = str(got.get("status") or packed.get("status") or "")
        if status == "MATCH":
            rows = [got]
        elif status == "TEMPORAL_CONFLICT":
            rows = list(got.get("candidates") or packed.get("candidates") or [])[:MAX_CONTEXTS]
        for cand in rows:
            c = dict(cand)
            if c.get("status") != "MATCH":
                c["status"] = "MATCH"
            c.setdefault("lag", L)
            row = _context_row(c, env_action=env_action, present=present)
            if row is None:
                continue
            sig = _sig(_floats(row.get("fragment") or {})) + f"|L{row.get('lag')}"
            if sig in seen:
                continue
            seen.add(sig)
            if status == "TEMPORAL_CONFLICT":
                row["temporal_conflict"] = True
            contexts.append(row)
            if len(contexts) >= MAX_CONTEXTS:
                break
        if len(contexts) >= MAX_CONTEXTS:
            break
    if meta is not None:
        if not contexts:
            meta["skipped_empty_context"] = int(meta.get("skipped_empty_context") or 0) + 1
        meta["predicted_contexts"] = int(meta.get("predicted_contexts") or 0) + len(contexts)
    return contexts


def _context_row(
    tps_result: dict[str, Any],
    *,
    env_action: str,
    present: dict[str, float],
) -> dict[str, Any] | None:
    frag = predicted_fragment(tps_result)
    if not frag:
        return None
    try:
        support_i = int(tps_result.get("support") or 0)
    except (TypeError, ValueError):
        support_i = 0
    if support_i <= 0:
        return None
    return {
        "fragment": dict(frag),
        "tps": dict(tps_result),
        "env_action": str(env_action),
        "lag": tps_result.get("lag"),
        "support": support_i,
        "class_id": tps_result.get("class_id"),
        "present": _floats(present),
        "context_kind": "PREDICTED",
        "not_realized_experience": True,
    }


def lookup_consequences(
    prospection: dict[str, Any],
    predicted_context: dict[str, float],
    actions: list[str],
    *,
    meta: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Read-only 4.23 predict_one_step from the predicted fragment.

    Never calls learn_transition. Never increments support.
    """
    matched: list[dict[str, Any]] = []
    unmodeled: list[dict[str, Any]] = []
    for act in list(actions)[:MAX_ACTIONS_PER_CONTEXT]:
        if meta is not None:
            meta["lookups"] = int(meta.get("lookups") or 0) + 1
        step = pr.predict_one_step(prospection, predicted_context, str(act))
        if step.get("status") == "MATCH":
            rec = dict(step)
            rec["prediction_source"] = "PREDICTED_CONTEXT"
            rec["context_kind"] = "PREDICTED"
            rec["context_role"] = "PREDICTED_CONTEXT"
            rec["not_realized_experience"] = True
            rec["future_action"] = str(act)
            rec["historical_action_consequence_support"] = int(step.get("support") or 0)
            matched.append(rec)
            if meta is not None:
                meta["matched"] = int(meta.get("matched") or 0) + 1
        else:
            unmodeled.append({
                "action": str(act),
                "status": "UNMODELED",
                "reason": step.get("status") or "NO_MATCH",
                "context_kind": "PREDICTED",
            })
            if meta is not None:
                meta["unmodeled"] = int(meta.get("unmodeled") or 0) + 1
    return matched, unmodeled


def as_continuation(
    present: dict[str, float],
    context_row: dict[str, Any],
    lookup: dict[str, Any],
    *,
    further: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compose present → predicted C → historical action consequence.

    first_action is the environmental TPS action (typically WAIT). The
    C-conditioned action is future_action, not a present command.
    """
    env_action = str(context_row.get("env_action") or ENV_ACTION)
    predicted_context = dict(context_row.get("fragment") or {})
    tps_result = context_row.get("tps") or {}
    try:
        tps_support = int(context_row.get("support") or tps_result.get("support") or 0)
    except (TypeError, ValueError):
        tps_support = 0
    hist_support = int(lookup.get("support") or 0)
    looked_action = str(lookup.get("action") or "")
    consequence = dict(lookup.get("predicted") or {})

    root_edge = {
        "status": "MATCH",
        "action": env_action,
        "predicted": dict(predicted_context),
        "support": tps_support,
        "reliability": None,
        "reliability_mapped": False,
        "depth": 1,
        "key": (
            f"predicted_context|{tps_result.get('class_id')}|L{tps_result.get('lag')}|"
            f"{tps_result.get('delta_sig')}"
        ),
        "transition_id": tps_result.get("class_id"),
        "prediction_source": "TEMPORAL",
        "context_kind": "PREDICTED",
        "context_role": "PREDICTED_CONTEXT",
        "not_snapshot_transition": True,
        "not_realized_experience": True,
        "lag": tps_result.get("lag"),
        "support_kind": "PREDICTED_CONTEXT",
        "provenance": {
            "source": "temporal_predictive_structure",
            "bridge": "predicted_context_prospection",
            "class_id": tps_result.get("class_id"),
            "lag": tps_result.get("lag"),
            "support": tps_support,
            "present": _floats(present),
            "predicted_context": dict(predicted_context),
        },
    }
    lookup_edge = dict(lookup)
    lookup_edge["prediction_source"] = "PREDICTED_CONTEXT"
    lookup_edge["context_kind"] = "PREDICTED"
    lookup_edge["context_role"] = "PREDICTED_CONTEXT"
    lookup_edge["not_realized_experience"] = True
    lookup_edge["future_action"] = looked_action
    lookup_edge["historical_action_consequence_support"] = hist_support
    lookup_edge["predicted_context_support"] = tps_support
    lookup_edge["supports_not_combined"] = True
    lookup_edge["supports_not_multiplied"] = True

    actions_seq = [env_action, looked_action]
    states = [dict(present), dict(predicted_context), dict(consequence)]
    edges = [root_edge, lookup_edge]
    future_actions = [looked_action]
    last = dict(consequence)
    for step in further or []:
        if step.get("status") != "MATCH":
            continue
        act = str(step.get("action") or "")
        pred = dict(step.get("predicted") or {})
        if not act or not pred:
            continue
        extra = dict(step)
        extra["prediction_source"] = extra.get("prediction_source") or "PREDICTED_CONTEXT"
        extra["context_kind"] = "PREDICTED"
        extra["not_realized_experience"] = True
        extra["future_action"] = act
        actions_seq.append(act)
        states.append(pred)
        edges.append(extra)
        future_actions.append(act)
        last = pred

    return {
        "actions": actions_seq,
        "states": states,
        "edges": edges,
        "depth": len(actions_seq),
        "score_reliability": float(lookup.get("reliability") or 0.0),
        "prediction_source": "PREDICTED_CONTEXT",
        "context_kind": "PREDICTED",
        "first_action": env_action,
        "future_actions": future_actions,
        "predicted_context": dict(predicted_context),
        "predicted_horizon": tps_result.get("lag"),
        "not_realized_experience": True,
        "not_imagined_experience": True,
        "executes_future_action_now": False,
        "support_ancestry": {
            "predicted_context_support": tps_support,
            "action_consequence_support": hist_support,
            "combined": None,
            "not_multiplied": True,
            "not_added": True,
        },
        "provenance": {
            "current_realized": _floats(present),
            "temporal_history_source": "temporal_predictive_structure",
            "predicted_context": dict(predicted_context),
            "prediction_source": "TPS",
            "predicted_horizon": tps_result.get("lag"),
            "historical_action_consequence": lookup.get("key"),
            "first_present_action": env_action,
            "future_action": looked_action,
            "prospective_continuation": dict(last),
            "context_kind": "PREDICTED",
            "realized_context": False,
        },
    }


def _expand_depth(
    prospection: dict[str, Any],
    lookup: dict[str, Any],
    actions: list[str],
    *,
    max_depth: int,
) -> list[dict[str, Any]]:
    """Optional further 4.23 steps from the looked-up consequence. Read-only."""
    further: list[dict[str, Any]] = []
    if max_depth < 3:
        return further
    last = dict(lookup.get("predicted") or {})
    if not last:
        return further
    for act in list(actions)[:MAX_ACTIONS_PER_CONTEXT]:
        step = pr.predict_one_step(prospection, last, str(act))
        if step.get("status") != "MATCH":
            continue
        row = (prospection.get("transitions") or {}).get(step.get("key"))
        if row is not None and not pr._compatible(last, row.get("antecedent") or {}):
            continue
        further.append(dict(step))
        break
    return further


def collect(
    *,
    tps_store: dict[str, Any] | None,
    prospection: dict[str, Any],
    present: dict[str, float],
    actions: list[str],
    predictions: list[dict[str, Any]] | None = None,
    tps_meta: dict[str, Any] | None = None,
    meta: dict[str, Any] | None = None,
    lag: int | None = None,
    max_depth: int = MAX_DEPTH,
    env_action: str = ENV_ACTION,
) -> list[dict[str, Any]]:
    """Predicted contexts → read-only action lookups → prospective branches.

    Does not write transitions, TPS, or biography. Does not execute actions.
    """
    if meta is None:
        meta = empty_meta()
        meta["enabled"] = True
    if not meta.get("enabled"):
        meta["skipped_disabled"] = int(meta.get("skipped_disabled") or 0) + 1
        return []

    n_before = len(prospection.get("transitions") or {})
    supports_before = {
        k: int(v.get("support") or 0)
        for k, v in (prospection.get("transitions") or {}).items()
    }

    contexts = collect_predicted_contexts(
        tps_store,
        present,
        env_action=env_action,
        predictions=predictions,
        tps_meta=tps_meta,
        lag=lag,
        meta=meta,
    )
    branches: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    unmodeled_all: list[dict[str, Any]] = []
    depth = min(int(max_depth), MAX_DEPTH)
    for ctx in contexts:
        frag = ctx.get("fragment") or {}
        matched, unmodeled = lookup_consequences(prospection, frag, actions, meta=meta)
        unmodeled_all.extend(unmodeled)
        for lu in matched:
            if len(branches) >= MAX_BRANCHES:
                break
            key = (
                _sig(_floats(frag)),
                str(lu.get("action") or ""),
                _sig(_floats(lu.get("predicted") or {})),
            )
            if key in seen:
                continue
            seen.add(key)
            further = _expand_depth(prospection, lu, actions, max_depth=depth)
            branches.append(as_continuation(present, ctx, lu, further=further))
        if len(branches) >= MAX_BRANCHES:
            break

    meta["branches"] = int(meta.get("branches") or 0) + len(branches)
    meta["unmodeled_actions"] = unmodeled_all[:16]
    meta["wrote_experience"] = False
    meta["support_incremented"] = False
    meta["imagined_experience"] = False
    # Hard audit: store must be bitwise-unchanged in support and membership.
    n_after = len(prospection.get("transitions") or {})
    if n_after != n_before:
        meta["wrote_experience"] = True
    for k, v in (prospection.get("transitions") or {}).items():
        if int(v.get("support") or 0) != int(supports_before.get(k) or 0):
            meta["support_incremented"] = True
            break
    return branches[:MAX_BRANCHES]


def diagnostic(
    meta: dict[str, Any] | None,
    branches: list[dict[str, Any]] | None = None,
    present: dict[str, float] | None = None,
) -> dict[str, Any]:
    conts = list(branches or [])
    future_now = [c for c in conts if c.get("executes_future_action_now")]
    firsts = sorted({str(c.get("first_action") or "") for c in conts if c.get("first_action")})
    futures = sorted({
        str(a)
        for c in conts
        for a in (c.get("future_actions") or [])
    })
    contexts = []
    for c in conts:
        pc = c.get("predicted_context") or {}
        if pc and pc not in contexts:
            contexts.append(dict(pc))
    return {
        "kind": "PREDICTED CONTEXT PROSPECTION",
        "not_planning": True,
        "not_imagined_experience": True,
        "not_anticipatory_policy": True,
        "enabled": bool((meta or {}).get("enabled")),
        "n_branches": len(conts),
        "n_predicted_contexts": len(contexts),
        "predicted_contexts": contexts[:MAX_CONTEXTS],
        "first_present_actions": firsts,
        "future_actions": futures,
        "executes_future_action_now": bool(future_now),
        "wrote_experience": bool((meta or {}).get("wrote_experience")),
        "support_incremented": bool((meta or {}).get("support_incremented")),
        "unmodeled_actions": list((meta or {}).get("unmodeled_actions") or [])[:16],
        "current_realized": _floats(present) if present is not None else {},
        "lookups": (meta or {}).get("lookups"),
        "matched": (meta or {}).get("matched"),
        "unmodeled": (meta or {}).get("unmodeled"),
        "note": "PREDICTED is not REALIZED; future_action is not first_action",
    }


def observer_panel(
    *,
    present: dict[str, float] | None,
    recent: list[Any] | None,
    branches: list[dict[str, Any]] | None,
    selected: str | None = None,
    realized_now: dict[str, float] | None = None,
    tps_diag: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Observer reconstruction. Predicted context must not look like world truth."""
    conts = list(branches or [])
    known: dict[str, list[dict[str, Any]]] = {}
    for c in conts:
        ctx = c.get("predicted_context") or {}
        sig = _sig(_floats(ctx)) if ctx else "_"
        known.setdefault(sig, [])
        for act, edge in zip(c.get("future_actions") or [], (c.get("edges") or [])[1:]):
            known[sig].append({
                "action": act,
                "consequence": (edge or {}).get("predicted"),
                "kind": "HISTORICAL",
                "support": (edge or {}).get("historical_action_consequence_support")
                or (edge or {}).get("support"),
            })
    predicted_rows = []
    for c in conts:
        predicted_rows.append({
            "kind": "PREDICTED",
            "horizon": c.get("predicted_horizon"),
            "fragment": c.get("predicted_context"),
            "source": "TPS",
            "not_realized": True,
        })
    return {
        "kind": "PREDICTED CONTEXT PROSPECTION",
        "CURRENT REALIZED": {"kind": "REALIZED", "T": (present or {}).get("x", (present or {}).get("local.T")), "fragment": present},
        "RECENT HISTORY": recent or (tps_diag or {}).get("recent") or [],
        "PREDICTED CONTEXT": predicted_rows[:MAX_CONTEXTS],
        "KNOWN CONSEQUENCES IN THAT CONTEXT": known,
        "PROSPECTIVE BRANCHES": [
            {
                "kind": "PROSPECTIVE",
                "actions": c.get("actions"),
                "first_present_action": c.get("first_action"),
                "future_actions": c.get("future_actions"),
                "continuation": (c.get("states") or [None])[-1],
                "support_ancestry": c.get("support_ancestry"),
                "not_realized": True,
            }
            for c in conts[:MAX_BRANCHES]
        ],
        "CURRENT FIRST ACTION": sorted({str(c.get("first_action") or "") for c in conts}),
        "FUTURE ACTIONS": sorted({
            str(a) for c in conts for a in (c.get("future_actions") or [])
        }),
        "SELECTED NOW": selected,
        "REALIZED NOW": {"kind": "REALIZED", "fragment": realized_now or present},
        "visual": {
            "REALIZED": "current observation / selected / realized now",
            "PREDICTED": "TPS future context — not world truth",
            "HISTORICAL": "already-experienced action-consequence rows",
            "PROSPECTIVE": "composed branches; not biography",
        },
        "not_current_world_truth": True,
        "predicted_must_not_masquerade_as_realized": True,
    }
