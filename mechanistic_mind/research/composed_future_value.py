"""Update 4.18 — researcher-only composed future value measurements.

This module deliberately has no dependency on action selection.  It composes
supported, state-conditioned physical transitions and evaluates each resulting
state once with the ordinary organism target-error semantics.
"""
from __future__ import annotations

from typing import Any, Callable

from mechanistic_mind.research.multiple_consequences import (
    prospective_consequences,
    update_multi_consequence,
)
from mechanistic_mind.research.prospective_valuation import prospective_ordinary_value


def state_key(state: dict[str, float]) -> str:
    """Exact bounded fixture key; values are cognition-visible body signals."""
    return "|".join(f"{k}={float(state[k]):.6f}" for k in sorted(state))


def edge_key(state: dict[str, float], action: str) -> str:
    return f"{state_key(state)}::{action}"


def body_delta(before: dict[str, float], after: dict[str, float]) -> dict[str, float]:
    return {k: float(after.get(k, 0.0)) - float(before.get(k, 0.0)) for k in set(before) | set(after)}


def acquire_edge(
    store: dict[str, Any], before: dict[str, float], action: str,
    after: dict[str, float], *, observations: int = 4,
) -> dict[str, Any]:
    """Acquire one link through repeated ordinary transition observations."""
    key = edge_key(before, action)
    for _ in range(observations):
        update_multi_consequence(store, key, body_delta(before, after))
    return {"key": key, "action": action, "input_state_key": state_key(before),
            "output_state_key": state_key(after), "support": float(observations),
            "provenance": "ACQUIRED_INDEPENDENTLY"}


def compose_supported_chain(
    *, store: dict[str, Any], start: dict[str, float], actions: list[str],
    min_support: float = 3.0,
) -> dict[str, Any]:
    """Compose all supported branches. UNKNOWN is terminal and never interpolated."""
    branches = [{"state": dict(start), "edges": [], "branch_identity": "root"}]
    ladder: list[dict[str, Any]] = []
    for depth, action in enumerate(actions, 1):
        next_branches: list[dict[str, Any]] = []
        unknown: list[dict[str, Any]] = []
        for branch in branches:
            current = branch["state"]
            result = prospective_consequences(
                tc=store, key=edge_key(current, action), current_signals=current,
                min_support=min_support,
            )
            if not result["consequences"]:
                unknown.append({"input_state": current, "action": action,
                                "reason": result["reason"], "provenance": "UNKNOWN"})
                continue
            for consequence in result["consequences"]:
                edge = {
                    "action": action,
                    "input_state_key": state_key(current),
                    "predicted_state_key": state_key(consequence["predicted_state"]),
                    "predicted_state": consequence["predicted_state"],
                    "mean_body_delta": consequence["mean_body_delta"],
                    "support": consequence["support"],
                    "consequence_group_id": consequence["id"],
                    "provenance": "DIRECT" if depth == 1 else "COMPOSED",
                }
                next_branches.append({
                    "state": consequence["predicted_state"],
                    "edges": branch["edges"] + [edge],
                    "branch_identity": f"{branch['branch_identity']}/{consequence['id']}",
                })
        ladder.append({"depth": depth, "actions": actions[:depth],
                       "status": "COMPOSED_FUTURE_AVAILABLE" if next_branches else "COMPOSED_FUTURE_UNKNOWN",
                       "branches": next_branches, "unknown": unknown})
        branches = next_branches
        if not branches:
            break
    return {"start_state": dict(start), "start_state_key": state_key(start),
            "ladder": ladder, "complete": len(ladder) == len(actions) and bool(branches)}


def ordinary_state_value(
    *, start: dict[str, float], terminal: dict[str, float], goals: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate terminal physical state once; never sum edge/cumulative values."""
    return prospective_ordinary_value(
        mean_body_delta=body_delta(start, terminal), body_delta_samples=1.0,
        contradiction=0.0, current_signals=start, goals=goals, support=1.0,
    )


def value_ladder(
    composition: dict[str, Any], *, goals: dict[str, Any],
    wait_states: list[dict[str, float]] | None = None,
) -> dict[str, Any]:
    rows = []
    horizon = None
    for item in composition["ladder"]:
        valued = []
        for branch in item["branches"]:
            value = ordinary_state_value(start=composition["start_state"], terminal=branch["state"], goals=goals)
            wait = None
            if wait_states and len(wait_states) >= item["depth"]:
                wait = ordinary_state_value(start=composition["start_state"], terminal=wait_states[item["depth"] - 1], goals=goals)
            row = {**branch, "ordinary_valuation": value,
                   "matched_wait_state": wait_states[item["depth"] - 1] if wait else None,
                   "matched_wait_valuation": wait,
                   "relative_to_wait": (value["ordinary_value"] - wait["ordinary_value"]) if wait else None}
            valued.append(row)
            if horizon is None and value["ordinary_value"] > 0.0:
                horizon = item["depth"]
        rows.append({**item, "branches": valued})
    return {"depths": rows, "value_horizon": horizon,
            "classification": "POSITIVE_VALUE_HORIZON_PRESENT" if horizon else "POSITIVE_VALUE_HORIZON_ABSENT",
            "no_cumulative_double_counting": True,
            "method": "start-to-terminal physical delta evaluated exactly once"}


def realize(actions: list[str], start: dict[str, float], physics: Callable[[dict[str, float], str], dict[str, float]]) -> list[dict[str, float]]:
    states, current = [], dict(start)
    for action in actions:
        current = physics(current, action)
        states.append(current)
    return states


def prediction_errors(predicted: list[dict[str, float]], realized: list[dict[str, float]]) -> list[dict[str, Any]]:
    rows = []
    for depth, (pred, real) in enumerate(zip(predicted, realized), 1):
        diff = {k: float(pred.get(k, 0.0)) - float(real.get(k, 0.0)) for k in set(pred) | set(real)}
        rows.append({"depth": depth, "component_difference": diff,
                     "l1_error": sum(abs(v) for v in diff.values())})
    return rows
