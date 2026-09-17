"""Update 4.16 — bounded, episode-specific persistent prospective traces.

The representation preserves an already generated trajectory across physical
realization.  It is deliberately not a plan, goal, value, policy input, or
long-term memory type.  Acquired transition evidence remains elsewhere.
"""
from __future__ import annotations

from copy import deepcopy
import json
from typing import Any

from mechanistic_mind.psyche.temporal_contingency import coarse_body_state_key, normalize_action
from mechanistic_mind.research.multiple_consequences import MATCH_L1, delta_l1
from mechanistic_mind.research.prediction_violation import VIOLATION_COMPONENTS

MAX_ACTIVE_TRACES = 1
MAX_BRANCHES_PER_TRACE = 4
MAX_EDGES_PER_BRANCH = 3
MAX_TRACE_LIFETIME_TICKS = 64

ACTIVE = "ACTIVE"
COMPLETED = "COMPLETED"
DIVERGED = "TRACE_DIVERGED"
ACTION_DIVERGED = "ACTION_DIVERGED"
BRANCH_ACTIVE = "UNREALIZED_COMPATIBLE"
BRANCH_INCOMPATIBLE = "REALIZED_INCOMPATIBLE"
BRANCH_COMPLETED = "COMPLETED"


def trace_id(counter: int) -> str:
    """Stable ID from a counter persisted with psyche working state."""
    return f"PPT-{int(counter):06d}"


def _numeric_state(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(k): float(v)
        for k, v in value.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool)
    }


def state_compatibility(predicted: Any, realized: Any, *, eps: float = MATCH_L1) -> dict[str, Any]:
    p, r = _numeric_state(predicted), _numeric_state(realized)
    if not p or not r:
        return {"status": "MISSING", "compatible": False, "l1": None, "component_abs": {}}
    distance = delta_l1(p, r)
    compatible = distance <= float(eps)
    return {
        "status": "MATCH" if compatible else "NO_MATCH",
        "compatible": compatible,
        "l1": distance,
        "component_abs": {
            key: abs(float(p.get(key, 0.0)) - float(r.get(key, 0.0)))
            for key in VIOLATION_COMPONENTS
        },
    }


def create_trace(
    *,
    counter: int,
    created_tick: int,
    origin_state_key: str,
    origin_signals: dict[str, float],
    branches: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Freeze prospective branches into one bounded mechanism-state object.

    ``branches`` entries contain ``edges``.  Each edge may contain action,
    horizon, predicted_state, provenance, parent/edge provenance, support, and
    consequence_group_id.  Values are copied exactly once here and are never
    replaced by :func:`advance_trace`.
    """
    frozen_branches: list[dict[str, Any]] = []
    tid = trace_id(counter)
    for branch_index, raw_branch in enumerate(branches[:MAX_BRANCHES_PER_TRACE]):
        nodes: list[dict[str, Any]] = []
        parent_node_id = None
        for edge_index, edge in enumerate((raw_branch.get("edges") or [])[:MAX_EDGES_PER_BRANCH]):
            predicted = _numeric_state(edge.get("predicted_state"))
            if not predicted:
                continue
            node_id = f"{tid}:B{branch_index + 1}:N{edge_index + 1}"
            consequence_id = edge.get("consequence_group_id", raw_branch.get("consequence_group_id"))
            nodes.append(
                {
                    "node_id": node_id,
                    "parent_node_id": parent_node_id,
                    "edge_index": edge_index,
                    "prediction_created_tick": int(created_tick),
                    "action": normalize_action(str(edge.get("action") or "WAIT")),
                    "horizon": int(edge.get("horizon") or 1),
                    "predicted_state": deepcopy(predicted),
                    "predicted_state_key": coarse_body_state_key(predicted, from_interoception=False),
                    "provenance": str(edge.get("provenance") or "DIRECT"),
                    "parent_edge_provenance": deepcopy(edge.get("parent_edge_provenance")),
                    "source_record_key": edge.get("source_record_key") or edge.get("key"),
                    "consequence_group_id": consequence_id,
                    "support": edge.get("support"),
                    "compatibility": "PENDING",
                    "realized_tick": None,
                }
            )
            parent_node_id = node_id
        if nodes:
            frozen_branches.append(
                {
                    "branch_id": f"{tid}:B{branch_index + 1}",
                    "consequence_group_id": raw_branch.get("consequence_group_id"),
                    "status": BRANCH_ACTIVE,
                    "current_position": 0,
                    "nodes": nodes,
                }
            )
    if not frozen_branches:
        return None
    result = {
        "version": "4.16",
        "trace_id": tid,
        "created_tick": int(created_tick),
        "origin_state_key": str(origin_state_key),
        "origin_signals": deepcopy(_numeric_state(origin_signals)),
        "status": ACTIVE,
        "branches": frozen_branches,
        "history": [{"tick": int(created_tick), "event": "CREATED"}],
        "last_update_tick": int(created_tick),
        "bounds": {
            "max_active_traces": MAX_ACTIVE_TRACES,
            "max_branches": MAX_BRANCHES_PER_TRACE,
            "max_edges_per_branch": MAX_EDGES_PER_BRANCH,
            "max_lifetime_ticks": MAX_TRACE_LIFETIME_TICKS,
        },
        "mechanism_state": True,
        "policy_coupled": False,
        "value_coupled": False,
    }
    result["cost"] = trace_cost(result, compatibility_checks=0)
    return result


def advance_trace(
    trace: dict[str, Any] | None,
    *,
    tick: int,
    realized_state: dict[str, float],
    actual_action: str | None,
    eps: float = MATCH_L1,
) -> dict[str, Any] | None:
    """Advance the frozen trace against reality without retrieving/rebuilding it."""
    if not isinstance(trace, dict):
        return None
    out = deepcopy(trace)
    if out.get("status") != ACTIVE or int(tick) <= int(out.get("created_tick", tick)):
        return out
    if int(tick) - int(out.get("created_tick", tick)) > MAX_TRACE_LIFETIME_TICKS:
        out["status"] = DIVERGED
        out["terminal_reason"] = "LIFETIME_BOUND_REACHED"
        out.setdefault("history", []).append({"tick": int(tick), "event": "LIFETIME_BOUND_REACHED"})
        out["cost"] = trace_cost(out, compatibility_checks=0)
        return out

    checks = 0
    action_mismatches = 0
    for branch in out.get("branches") or []:
        if branch.get("status") != BRANCH_ACTIVE:
            continue
        position = int(branch.get("current_position") or 0)
        nodes = branch.get("nodes") or []
        if position >= len(nodes):
            branch["status"] = BRANCH_COMPLETED
            continue
        node = nodes[position]
        expected_action = normalize_action(str(node.get("action") or ""))
        performed_action = normalize_action(str(actual_action or "")) if actual_action is not None else None
        if performed_action is not None and performed_action != expected_action:
            node["compatibility"] = "ACTION_INCOMPATIBLE"
            node["actual_action"] = performed_action
            node["realized_tick"] = int(tick)
            branch["status"] = BRANCH_INCOMPATIBLE
            branch["terminal_reason"] = ACTION_DIVERGED
            action_mismatches += 1
            out.setdefault("history", []).append(
                {"tick": int(tick), "event": "ACTION_INCOMPATIBLE", "branch_id": branch.get("branch_id"),
                 "expected_action": expected_action, "actual_action": performed_action}
            )
            continue
        comparison = state_compatibility(node.get("predicted_state"), realized_state, eps=eps)
        checks += 1
        node["comparison"] = comparison
        node["realized_tick"] = int(tick)
        if comparison["compatible"]:
            node["compatibility"] = "REALIZED_COMPATIBLE"
            branch["current_position"] = position + 1
            branch["status"] = BRANCH_COMPLETED if position + 1 >= len(nodes) else BRANCH_ACTIVE
            out.setdefault("history", []).append(
                {"tick": int(tick), "event": "EDGE_MATCHED", "branch_id": branch.get("branch_id"),
                 "edge_index": node.get("edge_index")}
            )
        else:
            node["compatibility"] = "NEXT_EDGE_INCOMPATIBLE"
            branch["status"] = BRANCH_INCOMPATIBLE
            branch["terminal_reason"] = "NEXT_EDGE_INCOMPATIBLE"
            out.setdefault("history", []).append(
                {"tick": int(tick), "event": "EDGE_INCOMPATIBLE", "branch_id": branch.get("branch_id"),
                 "edge_index": node.get("edge_index")}
            )

    statuses = [b.get("status") for b in out.get("branches") or []]
    if any(status == BRANCH_ACTIVE for status in statuses):
        out["status"] = ACTIVE
    elif any(status == BRANCH_COMPLETED for status in statuses):
        out["status"] = COMPLETED
        out["terminal_reason"] = "ALL_EDGES_REALIZED_ON_COMPATIBLE_BRANCH"
        out.setdefault("history", []).append({"tick": int(tick), "event": "COMPLETED"})
    else:
        out["status"] = ACTION_DIVERGED if action_mismatches and checks == 0 else DIVERGED
        out["terminal_reason"] = out["status"]
        out.setdefault("history", []).append({"tick": int(tick), "event": out["status"]})
    out["last_update_tick"] = int(tick)
    out["cost"] = trace_cost(out, compatibility_checks=checks)
    return out


def retained_tail(trace: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Return original, still-unrealized nodes from compatible branches."""
    if not isinstance(trace, dict):
        return []
    tail: list[dict[str, Any]] = []
    for branch in trace.get("branches") or []:
        if branch.get("status") != BRANCH_ACTIVE:
            continue
        position = int(branch.get("current_position") or 0)
        tail.extend(deepcopy((branch.get("nodes") or [])[position:]))
    return tail


def trace_cost(trace: dict[str, Any], *, compatibility_checks: int) -> dict[str, int]:
    branches = trace.get("branches") or []
    nodes = sum(len(branch.get("nodes") or []) for branch in branches)
    return {
        "active_trace_count": 1 if trace.get("status") == ACTIVE else 0,
        "branch_count": len(branches),
        "node_count": nodes,
        "edge_count": nodes,
        "compatibility_checks_this_cycle": int(compatibility_checks),
        "update_operations_upper_bound": len(branches),
        "serialized_bytes": len(json.dumps(trace, default=str, sort_keys=True)),
    }


def trace_from_composition(
    *, counter: int, created_tick: int, origin_signals: dict[str, float], composition: dict[str, Any]
) -> dict[str, Any] | None:
    """Freeze an existing 4.12 two-step composition; no new composition is done here."""
    edges = []
    for key in ("edge_a", "edge_b"):
        edge = composition.get(key) or {}
        if edge.get("status") == "OK" and edge.get("predicted_state"):
            edges.append(
                {
                    "action": edge.get("action"),
                    "horizon": edge.get("lag"),
                    "predicted_state": edge.get("predicted_state"),
                    "provenance": edge.get("provenance"),
                    "support": edge.get("support"),
                    "source_record_key": edge.get("key"),
                    "parent_edge_provenance": {
                        "composition": composition.get("composition"),
                        "input_state_key": edge.get("input_state_key"),
                    },
                }
            )
    return create_trace(
        counter=counter,
        created_tick=created_tick,
        origin_state_key=coarse_body_state_key(origin_signals, from_interoception=False),
        origin_signals=origin_signals,
        branches=[{"edges": edges}],
    )
