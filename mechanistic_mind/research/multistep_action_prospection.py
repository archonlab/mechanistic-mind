"""Experimental adapter: present action → future context → future action.

Default OFF. Annotates existing 4.23 multi-action chains and, when a first-step
MATCH exists, performs a read-only second-edge lookup at the predicted context.

Does not invent actions, macros, value, or a selection policy. Future actions
remain prospective; only first_action is eligible for present selection.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.research import prospective_composition as pr
from mechanistic_mind.research.predictive_equivalence import _floats
from mechanistic_mind.research.predictive_compression import _sig

MAX_BRANCHES = 8
MAX_DEPTH = 3
MAX_SECOND = 4

# BETA2-03: ancestry antecedent/predicted are flat float maps.
_USE_ANCESTRY_DICT_COPY = True


def set_ancestry_dict_copy(enabled: bool) -> None:
    global _USE_ANCESTRY_DICT_COPY
    _USE_ANCESTRY_DICT_COPY = bool(enabled)


def _copy_frag_map(d: dict[str, Any] | None) -> dict[str, Any]:
    src = d or {}
    if not _USE_ANCESTRY_DICT_COPY:
        from copy import deepcopy as _dc

        return _dc(src)
    return dict(src)


def empty_meta() -> dict[str, Any]:
    return {
        "enabled": False,
        "annotated": 0,
        "filled": 0,
        "novel": 0,
        "skipped_disabled": 0,
        "wrote_experience": False,
        "support_incremented": False,
        "executed_future_now": False,
        "note": "MULTI-STEP ACTION PROSPECTION — composition of learned edges, not a plan",
    }


def snapshot(meta: dict[str, Any] | None) -> dict[str, Any]:
    m = meta or {}
    return {
        "enabled": bool(m.get("enabled")),
        "annotated": m.get("annotated"),
        "filled": m.get("filled"),
        "novel": m.get("novel"),
        "wrote_experience": bool(m.get("wrote_experience")),
        "support_incremented": bool(m.get("support_incremented")),
        "executed_future_now": bool(m.get("executed_future_now")),
        "note": "adapter; does not compose a new dynamics engine",
    }


def _row(store: dict[str, Any], edge: dict[str, Any] | None) -> dict[str, Any] | None:
    if not edge:
        return None
    key = edge.get("key")
    if key:
        row = (store.get("transitions") or {}).get(key)
        if row:
            return row
    tid = edge.get("transition_id")
    if tid:
        for r in (store.get("transitions") or {}).values():
            if r.get("transition_id") == tid:
                return r
    return None


def _edge_ancestry(store: dict[str, Any], edge: dict[str, Any]) -> dict[str, Any]:
    row = _row(store, edge)
    ticks = list((row or {}).get("evidence_ticks") or [])[-12:]
    return {
        "action": edge.get("action"),
        "key": edge.get("key"),
        "transition_id": edge.get("transition_id") or (row or {}).get("transition_id"),
        "support": int(edge.get("support") or (row or {}).get("support") or 0),
        "reliability": edge.get("reliability") if edge.get("reliability") is not None else (pr.reliability(row) if row else None),
        "evidence_ticks": ticks,
        "antecedent": _copy_frag_map((row or {}).get("antecedent") or {}),
        "predicted": _copy_frag_map(edge.get("predicted") or {}),
    }


def novel_pair(a: dict[str, Any], b: dict[str, Any]) -> bool:
    """True when two edges come from disjoint evidence (composition, not recall)."""
    if not a or not b:
        return False
    if a.get("transition_id") and b.get("transition_id") and a.get("transition_id") == b.get("transition_id"):
        return False
    t0 = set(a.get("evidence_ticks") or [])
    t1 = set(b.get("evidence_ticks") or [])
    if t0 and t1 and (t0 & t1):
        return False
    return a.get("transition_id") != b.get("transition_id")


def annotate(cont: dict[str, Any], store: dict[str, Any]) -> dict[str, Any]:
    """Label first vs future actions on an existing 4.23 continuation. Read-only."""
    out = dict(cont)
    actions = list(out.get("actions") or [])
    if not actions:
        return out
    first = str(actions[0])
    future = [str(a) for a in actions[1:]]
    ancestries = [_edge_ancestry(store, e) for e in (out.get("edges") or [])]
    novel = False
    if len(ancestries) >= 2:
        novel = novel_pair(ancestries[0], ancestries[1])
    out["first_action"] = first
    out["future_actions"] = future
    out["executes_future_action_now"] = False
    out["not_macro_action"] = True
    out["not_imagined_experience"] = True
    out["novel_composition"] = novel
    out["support_ancestry"] = {
        "edges": [
            {
                "action": a.get("action"),
                "transition_id": a.get("transition_id"),
                "support": a.get("support"),
                "reliability": a.get("reliability"),
            }
            for a in ancestries
        ],
        "combined": None,
        "not_multiplied": True,
        "not_added": True,
        "score_reliability_is_product_of_reliabilities": True,
        "competition_uses_root_support": True,
    }
    out["provenance"] = {
        "first_present_action": first,
        "future_actions": future,
        "edges": ancestries,
        "novel_composition": novel,
        "path": "multistep_action_prospection",
    }
    if "prediction_source" not in out:
        out["prediction_source"] = (out.get("edges") or [{}])[0].get("prediction_source") or "SNAPSHOT"
    return out


def _sig_path(cont: dict[str, Any]) -> tuple[Any, ...]:
    acts = tuple(str(a) for a in (cont.get("actions") or []))
    last = _floats((cont.get("states") or [{}])[-1] or {})
    return (acts, _sig(last))


def _extend(
    store: dict[str, Any],
    parent: dict[str, Any],
    action: str,
) -> dict[str, Any] | None:
    last = dict((parent.get("states") or [{}])[-1] or {})
    if not last:
        return None
    step = pr.predict_one_step(store, last, str(action))
    if step.get("status") != "MATCH":
        return None
    row = (store.get("transitions") or {}).get(step.get("key"))
    if row is None:
        return None
    if not pr._compatible(last, row.get("antecedent") or {}):
        return None
    child = {
        "actions": list(parent.get("actions") or []) + [str(action)],
        "states": list(parent.get("states") or []) + [dict(step.get("predicted") or {})],
        "edges": list(parent.get("edges") or []) + [dict(step)],
        "depth": int(parent.get("depth") or 1) + 1,
        "score_reliability": float(parent.get("score_reliability") or 0.0)
        * float(step.get("reliability") or 0.5),
        "prediction_source": parent.get("prediction_source") or "SNAPSHOT",
        "not_realized_experience": True,
    }
    return annotate(child, store)


def collect(
    *,
    store: dict[str, Any],
    present: dict[str, float],
    actions: list[str],
    continuations: list[dict[str, Any]] | None = None,
    meta: dict[str, Any] | None = None,
    max_depth: int = MAX_DEPTH,
) -> list[dict[str, Any]]:
    """Annotate existing 4.23 chains and fill missing compatible second edges.

    Never calls learn_transition. Never executes actions.
    """
    if meta is None:
        meta = empty_meta()
        meta["enabled"] = True
    if not meta.get("enabled"):
        meta["skipped_disabled"] = int(meta.get("skipped_disabled") or 0) + 1
        return []

    n_before = len(store.get("transitions") or {})
    supports_before = {
        k: int(v.get("support") or 0) for k, v in (store.get("transitions") or {}).items()
    }

    depth = min(int(max_depth), MAX_DEPTH)
    out: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for cont in continuations or []:
        tagged = annotate(cont, store)
        key = _sig_path(tagged)
        if key in seen:
            continue
        seen.add(key)
        out.append(tagged)
        meta["annotated"] = int(meta.get("annotated") or 0) + 1
        if tagged.get("novel_composition"):
            meta["novel"] = int(meta.get("novel") or 0) + 1
        if len(out) >= MAX_BRANCHES:
            break

    if depth >= 2:
        roots = [c for c in out if int(c.get("depth") or 0) == 1]
        for root in roots:
            if len(out) >= MAX_BRANCHES:
                break
            filled = 0
            for act in list(actions)[:MAX_SECOND]:
                if filled >= MAX_SECOND or len(out) >= MAX_BRANCHES:
                    break
                child = _extend(store, root, str(act))
                if child is None:
                    continue
                key = _sig_path(child)
                if key in seen:
                    continue
                seen.add(key)
                out.append(child)
                filled += 1
                meta["filled"] = int(meta.get("filled") or 0) + 1
                if child.get("novel_composition"):
                    meta["novel"] = int(meta.get("novel") or 0) + 1

        if depth >= 3:
            mids = [c for c in out if int(c.get("depth") or 0) == 2]
            for mid in mids:
                if len(out) >= MAX_BRANCHES:
                    break
                for act in list(actions)[:MAX_SECOND]:
                    if len(out) >= MAX_BRANCHES:
                        break
                    child = _extend(store, mid, str(act))
                    if child is None:
                        continue
                    key = _sig_path(child)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(child)
                    meta["filled"] = int(meta.get("filled") or 0) + 1

    meta["wrote_experience"] = len(store.get("transitions") or {}) != n_before
    meta["support_incremented"] = any(
        int(v.get("support") or 0) != int(supports_before.get(k) or 0)
        for k, v in (store.get("transitions") or {}).items()
    )
    meta["executed_future_now"] = any(c.get("executes_future_action_now") for c in out)
    return out[:MAX_BRANCHES]


def diagnostic(
    meta: dict[str, Any] | None,
    branches: list[dict[str, Any]] | None = None,
    present: dict[str, float] | None = None,
    selected: str | None = None,
) -> dict[str, Any]:
    conts = list(branches or [])
    premature = [
        c for c in conts
        if selected and selected in (c.get("future_actions") or []) and selected != c.get("first_action")
    ]
    return {
        "kind": "MULTI-STEP PROSPECTION",
        "not_planning": True,
        "not_macro_action": True,
        "not_value": True,
        "enabled": bool((meta or {}).get("enabled")),
        "n_branches": len(conts),
        "n_multi": sum(1 for c in conts if (c.get("future_actions") or [])),
        "n_novel": sum(1 for c in conts if c.get("novel_composition")),
        "first_actions": sorted({str(c.get("first_action") or "") for c in conts if c.get("first_action")}),
        "future_actions": sorted({
            str(a) for c in conts for a in (c.get("future_actions") or [])
        }),
        "executes_future_action_now": bool((meta or {}).get("executed_future_now")),
        "premature_future_selected": bool(premature),
        "wrote_experience": bool((meta or {}).get("wrote_experience")),
        "support_incremented": bool((meta or {}).get("support_incremented")),
        "annotated": (meta or {}).get("annotated"),
        "filled": (meta or {}).get("filled"),
        "current": _floats(present) if present is not None else {},
        "selected_now": selected,
        "note": "future_action is not first_action; deeper P/Q is not desirability",
    }


def observer_panel(
    *,
    present: dict[str, float] | None,
    branches: list[dict[str, Any]] | None,
    selected: str | None = None,
    realized: dict[str, float] | None = None,
) -> dict[str, Any]:
    rows = []
    for i, c in enumerate(list(branches or [])[:MAX_BRANCHES], start=1):
        states = list(c.get("states") or [])
        ctx = states[1] if len(states) > 1 else {}
        cons = states[-1] if states else {}
        rows.append({
            "branch": i,
            "NOW": c.get("first_action"),
            "PREDICTED CONTEXT": ctx,
            "FUTURE ACTION": c.get("future_actions"),
            "PREDICTED CONSEQUENCE": cons,
            "novel": c.get("novel_composition"),
            "not_selected_future": True,
        })
    return {
        "kind": "MULTI-STEP PROSPECTION",
        "CURRENT": present,
        "BRANCHES": rows,
        "CURRENT ACTION": selected,
        "REALIZED CONSEQUENCE": realized,
        "visual": {
            "CURRENT ACTION": "eligible for present selection",
            "FUTURE ACTION": "prospective only — not already selected",
            "PREDICTED CONTEXT": "internal chain node, not realized",
            "PREDICTED CONSEQUENCE": "learned continuation",
            "REALIZED CONSEQUENCE": "ordinary physics after execution",
        },
        "future_must_not_look_selected": True,
    }
