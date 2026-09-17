"""Experimental adapter: conflict/content scenarios → existing competition.

Default OFF. Does not select, invent actions, or introduce reward/utility.
Preserves prospective identity already computed by predictive_conflict /
compose, then hands groups to unchanged compete_scenarios.

Justification: compete_scenarios already compares first-action representatives
on (historical_support, reliability, depth). Predicted continuation and
conflict candidates were computed then discarded before that comparison.
This adapter restores that evidence. It is not argmax-as-new-policy.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.physical_system import scenario_competition as sc
from mechanistic_mind.research import predictive_conflict as pcf
from mechanistic_mind.research.predictive_compression import _sig
from mechanistic_mind.research.predictive_equivalence import _floats
from mechanistic_mind.research import prospective_composition as pr

MAX_RECEIPTS = 24


def empty_meta() -> dict[str, Any]:
    return {
        "enabled": False,
        "builds": 0,
        "from_conflict": 0,
        "from_continuations": 0,
        "n_first_actions": 0,
        "note": "FUTURE_SENSITIVE_ACTION — not utility, not preference, not a new policy",
    }


def snapshot(meta: dict[str, Any] | None) -> dict[str, Any]:
    m = meta or {}
    return {
        "enabled": bool(m.get("enabled")),
        "builds": m.get("builds"),
        "from_conflict": m.get("from_conflict"),
        "from_continuations": m.get("from_continuations"),
        "n_first_actions": m.get("n_first_actions"),
        "note": "adapter into existing compete_scenarios; not a standalone policy",
    }


def _pred_sig(fragment: Any) -> str:
    if fragment in (None, sc.NOT_AVAILABLE):
        return ""
    return _sig(pr._q(_floats(fragment if isinstance(fragment, dict) else {})))


def candidate_to_scenario(
    cand: dict[str, Any],
    *,
    action_counts: dict[str, int] | None = None,
) -> dict[str, Any] | None:
    fa = str(cand.get("first_action") or "")
    if not fa:
        return None
    support = int(cand.get("support") or 0)
    if support <= 0:
        return None
    actions = list(cand.get("actions") or [fa])
    counts = action_counts or {}
    rel = cand.get("reliability")
    if rel is None:
        rel = 0.0
    return {
        "scenario_id": cand.get("id") or "C",
        "source_structure_ids": list((cand.get("evidence") or {}).get("structure_ids") or [])[: sc.MAX_SCENARIOS_PER_ACTION],
        "provenance": {
            "path": "predictive_conflict_candidate",
            "content_sig": cand.get("content_sig"),
            "sources": list(cand.get("prediction_sources") or []),
            "shared_ancestry": (cand.get("evidence") or {}).get("shared_ancestry"),
            "summed": (cand.get("evidence") or {}).get("summed"),
        },
        "action_sequence": actions,
        "first_action": fa,
        "depth": int(cand.get("depth") or len(actions) or 1),
        "historical_support": support,
        "historical_support_raw": support,
        "reliability": float(rel or 0.0),
        "reliability_raw": rel,
        "current_match_evidence": deepcopy(cand.get("routes") or []),
        "predicted_state_fragments": deepcopy(cand.get("predicted") or sc.NOT_AVAILABLE),
        "predicted_body_fragments": sc.NOT_AVAILABLE,
        "predicted_environment_fragments": sc.NOT_AVAILABLE,
        "composition_path": deepcopy(cand.get("predicted_path") or []),
        "score_reliability_path": rel if rel is not None else sc.NOT_AVAILABLE,
        "prediction_sources": list(cand.get("prediction_sources") or []),
        "evidence_ancestry": deepcopy(cand.get("evidence") or {}),
        "content_sig": cand.get("content_sig"),
        "scenario_specific_evidence": support,
        "historical_action_count": int(counts.get(fa) or 0),
        "conflict_status": cand.get("status"),
    }


def groups_from_candidates(
    candidates: list[dict[str, Any]],
    actions: list[str],
    *,
    action_counts: dict[str, int] | None = None,
    max_per_action: int = sc.MAX_SCENARIOS_PER_ACTION,
    max_total: int = sc.MAX_SCENARIOS_TOTAL,
) -> dict[str, list[dict[str, Any]]]:
    """Group content-identified candidates by first_action. No invented actions."""
    groups: dict[str, list[dict[str, Any]]] = {a: [] for a in actions}
    seen: set[str] = set()
    total = 0
    for cand in candidates or []:
        fa = str(cand.get("first_action") or "")
        if fa not in groups:
            continue
        sig = str(cand.get("content_sig") or "")
        if sig and sig in seen:
            continue
        scn = candidate_to_scenario(cand, action_counts=action_counts)
        if scn is None:
            continue
        if len(groups[fa]) >= max_per_action or total >= max_total:
            continue
        if sig:
            seen.add(sig)
        groups[fa].append(scn)
        total += 1
    return groups


def collect_with_content_identity(
    *,
    store: dict[str, Any],
    observation: dict[str, float],
    continuations: list[dict[str, Any]],
    actions: list[str],
    action_counts: dict[str, int] | None = None,
    max_per_action: int = sc.MAX_SCENARIOS_PER_ACTION,
    max_total: int = sc.MAX_SCENARIOS_TOTAL,
) -> dict[str, list[dict[str, Any]]]:
    """Like collect_scenario_groups but identity includes predicted path."""
    groups: dict[str, list[dict[str, Any]]] = {a: [] for a in actions}
    seen: set[tuple[Any, ...]] = set()
    sid = 1
    counts = action_counts or {}

    def _add(scn: dict[str, Any] | None) -> None:
        nonlocal sid
        if scn is None:
            return
        fa = scn["first_action"]
        if fa not in groups:
            return
        pred = scn.get("predicted_state_fragments")
        key = (
            fa,
            tuple(scn.get("action_sequence") or []),
            scn.get("depth"),
            scn.get("historical_support"),
            _pred_sig(pred),
        )
        if key in seen:
            return
        if len(groups[fa]) >= max_per_action:
            return
        if sum(len(v) for v in groups.values()) >= max_total:
            return
        seen.add(key)
        scn["scenario_specific_evidence"] = int(scn.get("historical_support") or 0)
        scn["historical_action_count"] = int(counts.get(fa) or 0)
        groups[fa].append(scn)
        sid += 1

    for act in actions:
        _add(sc.one_step_scenario(store, observation, act, scenario_id=f"S{sid}"))
    for cont in continuations or []:
        _add(sc.continuation_to_scenario(cont, scenario_id=f"S{sid}"))
    return groups


def build_groups(
    *,
    store: dict[str, Any],
    observation: dict[str, float],
    continuations: list[dict[str, Any]],
    actions: list[str],
    conflict_candidates: list[dict[str, Any]] | None = None,
    action_counts: dict[str, int] | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    if meta is None or not meta.get("enabled"):
        return sc.collect_scenario_groups(
            store=store, observation=observation, continuations=continuations, actions=actions,
        )
    meta["builds"] = int(meta.get("builds") or 0) + 1
    cands = [c for c in (conflict_candidates or []) if int(c.get("support") or 0) > 0]
    if cands:
        groups = groups_from_candidates(cands, actions, action_counts=action_counts)
        meta["from_conflict"] = int(meta.get("from_conflict") or 0) + 1
    else:
        groups = collect_with_content_identity(
            store=store,
            observation=observation,
            continuations=continuations,
            actions=actions,
            action_counts=action_counts,
        )
        meta["from_continuations"] = int(meta.get("from_continuations") or 0) + 1
    meta["n_first_actions"] = sum(1 for a in actions if groups.get(a))
    return groups


def observer_panel(
    groups: dict[str, list[dict[str, Any]]],
    competition: dict[str, Any] | None,
    *,
    selected: str | None = None,
    realized: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Observer labels only. Not cognitive semantics. No reward/value."""
    rows = []
    for act, scns in (groups or {}).items():
        if not scns:
            continue
        head = scns[0]
        rows.append({
            "first_action": act,
            "n_scenarios": len(scns),
            "prospective_path": head.get("composition_path") or head.get("predicted_state_fragments"),
            "scenario_support": head.get("historical_support"),
            "historical_action_count": head.get("historical_action_count"),
            "scenario_specific_evidence": head.get("scenario_specific_evidence"),
            "status": head.get("conflict_status") or ("SUPPORTED" if scns else "UNSUPPORTED"),
            "prediction_sources": head.get("prediction_sources"),
        })
    comp = competition or {}
    return {
        "kind": "ACTION_LINKED_SCENARIOS",
        "scenarios": rows[:16],
        "competition": {
            "outcome": comp.get("outcome_class"),
            "selected_action": comp.get("selected_action") or selected,
            "reason": comp.get("selection_reason"),
            "supported_actions": comp.get("supported_actions"),
        },
        "selected": selected,
        "realized": deepcopy(realized or {}),
        "not_reward": True,
        "not_utility": True,
    }


def diagnostic(meta: dict[str, Any], panel: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "kind": "FUTURE_SENSITIVE_ACTION",
        "not_policy": True,
        "not_utility": True,
        "not_preference": True,
        **snapshot(meta),
        "panel": panel or {},
    }
