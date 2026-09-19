"""Prospective Scenario Competition — selection stage after composition.

Separate from prospective composition. Does not invent novelty/anti-WAIT scores.
Evidence dimensions are taken only from existing transition/continuation fields.
"""
from __future__ import annotations

from mechanistic_mind.integrated.copy_opt import jsonish_copy
from typing import Any

from mechanistic_mind.research import prospective_composition as pr

from .actions import available_actions

# Bounded cognition
MAX_SCENARIOS_TOTAL = 32
MAX_SCENARIOS_PER_ACTION = 4
NOT_AVAILABLE = "NOT_AVAILABLE"


def _evidence_vector(scenario: dict[str, Any]) -> tuple[int, float, int]:
    """Lexicographic evidence: (historical_support, reliability, depth).

    Justification (mechanism-native, not utility weights):
    - support: count of ordinary experienced transitions for the root edge
    - reliability: existing transition reliability (1 - predictive dispersion)
    - depth: composed horizon length from matched edges only
    """
    return (
        int(scenario.get("historical_support") or 0),
        float(scenario.get("reliability") or 0.0),
        int(scenario.get("depth") or 0),
    )


def dominates(a: dict[str, Any], b: dict[str, Any]) -> bool:
    va, vb = _evidence_vector(a), _evidence_vector(b)
    return all(x >= y for x, y in zip(va, vb)) and any(x > y for x, y in zip(va, vb))


def incomparable(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return (not dominates(a, b)) and (not dominates(b, a)) and _evidence_vector(a) != _evidence_vector(b)


def exact_tie(a: dict[str, Any], b: dict[str, Any]) -> bool:
    return _evidence_vector(a) == _evidence_vector(b)


def continuation_to_scenario(cont: dict[str, Any], *, scenario_id: str) -> dict[str, Any] | None:
    actions = list(cont.get("actions") or [])
    if not actions:
        return None
    edges = list(cont.get("edges") or [])
    root = edges[0] if edges else {}
    if root.get("status") not in {None, "MATCH"} and root:
        # compose only adds MATCH edges; still guard
        if root.get("status") != "MATCH":
            return None
    support = root.get("support")
    reliability = root.get("reliability")
    if support is None:
        support = NOT_AVAILABLE
    if reliability is None:
        reliability = float(cont.get("score_reliability") or 0.0)
        # score_reliability is product along path; root reliability preferred when present
    predicted = None
    states = cont.get("states") or []
    if len(states) >= 2:
        predicted = jsonish_copy(states[1])
    return {
        "scenario_id": scenario_id,
        "source_structure_ids": [e.get("transition_id") or e.get("key") for e in edges if e],
        "provenance": {"edge_keys": [e.get("key") for e in edges], "path": "compose_continuation"},
        "action_sequence": actions,
        "first_action": str(actions[0]),
        "depth": int(cont.get("depth") or len(actions)),
        "historical_support": support if support != NOT_AVAILABLE else 0,
        "historical_support_raw": support,
        "reliability": float(reliability) if reliability != NOT_AVAILABLE else 0.0,
        "reliability_raw": reliability,
        "current_match_evidence": jsonish_copy(root) if root else NOT_AVAILABLE,
        "predicted_state_fragments": predicted if predicted is not None else NOT_AVAILABLE,
        "predicted_body_fragments": NOT_AVAILABLE,
        "predicted_environment_fragments": NOT_AVAILABLE,
        "composition_path": jsonish_copy(edges),
        "score_reliability_path": cont.get("score_reliability", NOT_AVAILABLE),
    }


def one_step_scenario(store: dict[str, Any], observation: dict[str, float], action: str, *, scenario_id: str) -> dict[str, Any] | None:
    step = pr.predict_one_step(store, observation, action)
    if step.get("status") != "MATCH":
        return None
    return {
        "scenario_id": scenario_id,
        "source_structure_ids": [step.get("transition_id") or step.get("key")],
        "provenance": {"edge_keys": [step.get("key")], "path": "one_step_match"},
        "action_sequence": [action],
        "first_action": str(action),
        "depth": 1,
        "historical_support": int(step.get("support") or 0),
        "historical_support_raw": step.get("support", NOT_AVAILABLE),
        "reliability": float(step.get("reliability") or 0.0),
        "reliability_raw": step.get("reliability", NOT_AVAILABLE),
        "current_match_evidence": jsonish_copy(step),
        "predicted_state_fragments": jsonish_copy(step.get("predicted")) if step.get("predicted") is not None else NOT_AVAILABLE,
        "predicted_body_fragments": NOT_AVAILABLE,
        "predicted_environment_fragments": NOT_AVAILABLE,
        "composition_path": [jsonish_copy(step)],
        "score_reliability_path": step.get("reliability", NOT_AVAILABLE),
    }


def collect_scenario_groups(
    *,
    store: dict[str, Any],
    observation: dict[str, float],
    continuations: list[dict[str, Any]],
    actions: list[str] | None = None,
    max_per_action: int = MAX_SCENARIOS_PER_ACTION,
    max_total: int = MAX_SCENARIOS_TOTAL,
) -> dict[str, list[dict[str, Any]]]:
    """Build scenarios grouped by first action. List order is not evidence."""
    actions = list(actions or available_actions())
    groups: dict[str, list[dict[str, Any]]] = {a: [] for a in actions}
    seen_keys: set[tuple[Any, ...]] = set()
    sid = 1

    def _add(sc: dict[str, Any] | None) -> None:
        nonlocal sid
        if sc is None:
            return
        fa = sc["first_action"]
        if fa not in groups:
            groups[fa] = []
        key = (fa, tuple(sc.get("action_sequence") or []), sc.get("depth"), sc.get("historical_support"))
        if key in seen_keys:
            return
        if len(groups[fa]) >= max_per_action:
            return
        total = sum(len(v) for v in groups.values())
        if total >= max_total:
            return
        seen_keys.add(key)
        groups[fa].append(sc)
        sid += 1

    # Independent one-step MATCH per action (avoids depending on compose list order)
    for act in actions:
        _add(one_step_scenario(store, observation, act, scenario_id=f"S{sid}"))

    # Composed continuations (may add deeper scenarios)
    for cont in continuations:
        _add(continuation_to_scenario(cont, scenario_id=f"S{sid}"))

    return groups


def _pareto_front(scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
    front: list[dict[str, Any]] = []
    for s in scenarios:
        if any(dominates(o, s) for o in scenarios if o is not s):
            continue
        front.append(s)
    return front


def select_group_representatives(groups: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Per first-action: pareto front; if multiple, mark within-action tie."""
    reps: dict[str, Any] = {}
    for act, scenarios in groups.items():
        if not scenarios:
            reps[act] = {"supported": False, "scenarios": [], "representative": None, "tie": None}
            continue
        front = _pareto_front(scenarios)
        tie = None
        if len(front) == 1:
            rep = front[0]
        else:
            # exact ties vs incomparable within action
            if all(exact_tie(front[0], x) for x in front[1:]):
                tie = "EXACT_TIE"
            elif any(incomparable(front[0], x) for x in front[1:]):
                tie = "INCOMPARABLE"
            else:
                tie = "PARTIAL_ORDER_TIE"
            rep = front[0]  # provisional; cross-action competition / endogenous resolves
        reps[act] = {
            "supported": True,
            "scenarios": scenarios,
            "front": front,
            "representative": rep,
            "tie": tie,
        }
    return reps


def compete_scenarios(
    *,
    groups: dict[str, list[dict[str, Any]]],
    actions: list[str],
    rng_value: float,
) -> dict[str, Any]:
    """Compete across first-action representatives. List order is not used as evidence."""
    reps = select_group_representatives(groups)
    supported_actions = [a for a in actions if reps.get(a, {}).get("supported")]
    candidates = [reps[a]["representative"] for a in supported_actions if reps[a].get("representative")]

    competition: dict[str, Any] = {
        "evidence_dimensions": ["historical_support", "reliability", "depth"],
        "evidence_order": "lexicographic_dominance (support, reliability, depth)",
        "candidates_considered": jsonish_copy(candidates),
        "supported_actions": supported_actions,
        "unsupported_actions": [a for a in actions if a not in supported_actions],
        "dominance_relations": [],
        "ties": [],
        "incomparable_candidates": [],
        "selected_scenario": None,
        "selected_action": None,
        "selection_reason": None,
        "tie_resolution": None,
        "outcome_class": None,
    }

    if not candidates:
        competition["outcome_class"] = "NO_SUPPORT"
        competition["selection_reason"] = "NO_SUPPORTED_PROSPECTIVE_SCENARIO"
        return {
            "selected": None,
            "source": "NO_SUPPORT",
            "selection_rule": "SCENARIO_COMPETITION: no MATCH scenarios; defer to fallback",
            "groups": reps,
            "competition": competition,
        }

    if len(candidates) == 1:
        win = candidates[0]
        competition["selected_scenario"] = jsonish_copy(win)
        competition["selected_action"] = win["first_action"]
        competition["selection_reason"] = "SINGLE_SUPPORTED"
        competition["outcome_class"] = "SINGLE_SUPPORTED"
        return {
            "selected": win["first_action"],
            "source": "PROSPECTIVE_SCENARIO",
            "selection_rule": "SCENARIO_COMPETITION: single supported first-action scenario",
            "groups": reps,
            "competition": competition,
        }

    # Dominance relations
    for i, a in enumerate(candidates):
        for j, b in enumerate(candidates):
            if i >= j:
                continue
            if dominates(a, b):
                competition["dominance_relations"].append({
                    "dominator": a["scenario_id"], "dominated": b["scenario_id"],
                    "dominator_action": a["first_action"], "dominated_action": b["first_action"],
                })
            elif dominates(b, a):
                competition["dominance_relations"].append({
                    "dominator": b["scenario_id"], "dominated": a["scenario_id"],
                    "dominator_action": b["first_action"], "dominated_action": a["first_action"],
                })
            elif exact_tie(a, b):
                competition["ties"].append({"a": a["scenario_id"], "b": b["scenario_id"], "kind": "EXACT_TIE"})
            elif incomparable(a, b):
                competition["incomparable_candidates"].append({
                    "a": a["scenario_id"], "b": b["scenario_id"], "kind": "INCOMPARABLE",
                })

    front = _pareto_front(candidates)
    if len(front) == 1:
        win = front[0]
        competition["selected_scenario"] = jsonish_copy(win)
        competition["selected_action"] = win["first_action"]
        competition["selection_reason"] = "DOMINANT_SCENARIO"
        competition["outcome_class"] = "DOMINANT_SCENARIO"
        return {
            "selected": win["first_action"],
            "source": "PROSPECTIVE_SCENARIO",
            "selection_rule": (
                "SCENARIO_COMPETITION: pareto-dominant under (support, reliability, depth); "
                "list order unused"
            ),
            "groups": reps,
            "competition": competition,
        }

    # Tie / incomparable among front → endogenous among their first actions
    if all(exact_tie(front[0], x) for x in front[1:]):
        competition["outcome_class"] = "EXACT_TIE"
        tie_kind = "EXACT_TIE"
    elif any(incomparable(front[0], x) for x in front[1:]):
        competition["outcome_class"] = "INCOMPARABLE"
        tie_kind = "INCOMPARABLE"
    else:
        competition["outcome_class"] = "PARTIAL_ORDER_TIE"
        tie_kind = "PARTIAL_ORDER_TIE"

    tie_actions = []
    for s in front:
        if s["first_action"] not in tie_actions:
            tie_actions.append(s["first_action"])
    idx = min(len(tie_actions) - 1, int(float(rng_value) * len(tie_actions)))
    chosen_action = tie_actions[idx]
    # pick a front scenario with that action (stable by scenario_id sort — display only after choice)
    tied = sorted([s for s in front if s["first_action"] == chosen_action], key=lambda s: s["scenario_id"])
    win = tied[0]
    competition["selected_scenario"] = jsonish_copy(win)
    competition["selected_action"] = chosen_action
    competition["selection_reason"] = tie_kind
    competition["tie_resolution"] = {
        "kind": tie_kind,
        "mechanism": "ENDOGENOUS_VARIATION over tied first-actions",
        "tied_actions": tie_actions,
        "rng_index": idx,
    }
    return {
        "selected": chosen_action,
        "source": "PROSPECTIVE_TIE_RESOLUTION",
        "selection_rule": (
            f"SCENARIO_COMPETITION: {tie_kind} on evidence front; "
            "endogenous index over tied first-actions (not list order of continuations)"
        ),
        "groups": reps,
        "competition": competition,
    }


def legacy_first_select(continuations: list[dict[str, Any]]) -> dict[str, Any]:
    """Reproduce diagnosis baseline: continuations[0].actions[0]."""
    if not continuations:
        return {
            "selected": None,
            "source": "NO_SUPPORT",
            "selection_rule": "LEGACY_FIRST: empty continuations",
            "competition": {"outcome_class": "NO_SUPPORT", "legacy": True},
        }
    selected = str(continuations[0]["actions"][0])
    return {
        "selected": selected,
        "source": "PROSPECTIVE_CONTINUATION",
        "selection_rule": (
            "LEGACY_FIRST: compose ranks (-depth,-reliability); "
            "select continuations[0]['actions'][0]"
        ),
        "competition": {
            "outcome_class": "LEGACY_FIRST_ELEMENT",
            "legacy": True,
            "selected_action": selected,
            "note": "List position constitutes selection privilege in this control mode",
        },
    }
