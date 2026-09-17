"""Update 4.17 researcher-only old-tail × fresh-prediction comparison.

This module classifies concurrently available representations.  It is not a
PsycheModule and writes no cognition state, value, policy, learning, or trace
lifecycle fields.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.psyche.temporal_contingency import normalize_action
from mechanistic_mind.research.multiple_consequences import MATCH_L1
from mechanistic_mind.research.persistent_prospective_trace import retained_tail, state_compatibility
from mechanistic_mind.research.prediction_violation import VIOLATION_COMPONENTS

RELATIONS = (
    "AGREEMENT",
    "OVERLAP",
    "INCOMPATIBLE",
    "NOT_COMPARABLE",
    "OLD_UNKNOWN",
    "FRESH_UNKNOWN",
)


def prospective_records(trace: dict[str, Any] | None, *, role: str) -> list[dict[str, Any]]:
    """Extract still-prospective nodes without changing either trace."""
    if not isinstance(trace, dict):
        return []
    records = []
    for node in retained_tail(trace):
        records.append(
            {
                "role": role,
                "trace_id": trace.get("trace_id"),
                "created_tick": trace.get("created_tick"),
                "prediction_created_tick": node.get("prediction_created_tick"),
                "prediction": deepcopy(node.get("predicted_state")),
                "prediction_state_key": node.get("predicted_state_key"),
                "action": node.get("action"),
                "horizon": node.get("horizon"),
                "node_provenance": node.get("provenance"),
                "generation_provenance": (
                    "PERSISTENT_T0_TRACE" if role == "OLD_EXPECTATION" else "FRESH_RECONSTRUCTION"
                ),
                "parent_edge_provenance": deepcopy(node.get("parent_edge_provenance")),
                "support": node.get("support"),
                "consequence_group_id": node.get("consequence_group_id"),
                "mechanistically_available": True,
            }
        )
    return records


def _target_dimensions(record: dict[str, Any]) -> tuple[str, ...]:
    prediction = record.get("prediction")
    if not isinstance(prediction, dict):
        return ()
    return tuple(key for key in VIOLATION_COMPONENTS if key in prediction)


def comparable(old: dict[str, Any], fresh: dict[str, Any]) -> tuple[bool, str]:
    if normalize_action(str(old.get("action") or "")) != normalize_action(str(fresh.get("action") or "")):
        return False, "DIFFERENT_ACTION"
    if int(old.get("horizon") or -1) != int(fresh.get("horizon") or -1):
        return False, "DIFFERENT_HORIZON"
    old_dims, fresh_dims = _target_dimensions(old), _target_dimensions(fresh)
    if not old_dims or old_dims != fresh_dims:
        return False, "DIFFERENT_TARGET_DIMENSIONS"
    return True, "SAME_ACTION_HORIZON_DIMENSIONS"


def compare_record_pair(
    old: dict[str, Any], fresh: dict[str, Any], *, threshold: float = MATCH_L1
) -> dict[str, Any]:
    is_comparable, reason = comparable(old, fresh)
    result = {
        "old": deepcopy(old),
        "fresh": deepcopy(fresh),
        "comparable": is_comparable,
        "comparability_reason": reason,
        "comparison_action": old.get("action") if is_comparable else None,
        "comparison_horizon": old.get("horizon") if is_comparable else None,
        "compatibility_threshold": float(threshold),
        "relation": "NOT_COMPARABLE",
        "component_signed_error_fresh_minus_old": None,
        "absolute_L1": None,
    }
    if not is_comparable:
        return result
    op, fp = old.get("prediction"), fresh.get("prediction")
    if not isinstance(op, dict):
        result["relation"] = "OLD_UNKNOWN"
        return result
    if not isinstance(fp, dict):
        result["relation"] = "FRESH_UNKNOWN"
        return result
    comparison = state_compatibility(op, fp, eps=threshold)
    result["component_signed_error_fresh_minus_old"] = {
        key: float(fp.get(key, 0.0)) - float(op.get(key, 0.0))
        for key in VIOLATION_COMPONENTS
    }
    result["absolute_L1"] = comparison.get("l1")
    result["relation"] = "AGREEMENT" if comparison.get("compatible") else "INCOMPATIBLE"
    return result


def compare_trace_sets(
    old_trace: dict[str, Any] | None,
    fresh_trace: dict[str, Any] | None,
    *,
    threshold: float = MATCH_L1,
) -> dict[str, Any]:
    """Conservative branch-set comparison with no averaging or resolution."""
    old_records = prospective_records(old_trace, role="OLD_EXPECTATION")
    fresh_records = prospective_records(fresh_trace, role="FRESH_PREDICTION")
    temporal_order = bool(
        old_trace and fresh_trace
        and int(old_trace.get("created_tick", -1)) < int(fresh_trace.get("created_tick", -1))
    )
    base = {
        "researcher_only": True,
        "cognition_visible_relation": False,
        "old_trace_id": (old_trace or {}).get("trace_id"),
        "fresh_trace_id": (fresh_trace or {}).get("trace_id"),
        "old_created_tick": (old_trace or {}).get("created_tick"),
        "fresh_created_tick": (fresh_trace or {}).get("created_tick"),
        "old_mechanistically_available": bool(old_records),
        "fresh_mechanistically_available": bool(fresh_records),
        "temporally_distinct_provenance": temporal_order,
        "old_supported_branches": old_records,
        "fresh_supported_branches": fresh_records,
        "compatible_pairs": [],
        "incompatible_pairs": [],
        "not_comparable_pairs": [],
        "shared_compatible_region": False,
        "relation": None,
        "PROSPECTIVE_CONFLICT": "ABSENT",
        "averaged_prediction": None,
        "resolution": None,
        "policy_coupling": "ABSENT",
        "value_coupling": "ABSENT",
    }
    if not old_records:
        base["relation"] = "OLD_UNKNOWN"
        return base
    if not fresh_records:
        base["relation"] = "FRESH_UNKNOWN"
        return base
    for old in old_records:
        for fresh in fresh_records:
            pair = compare_record_pair(old, fresh, threshold=threshold)
            if pair["relation"] == "AGREEMENT":
                base["compatible_pairs"].append(pair)
            elif pair["relation"] == "INCOMPATIBLE":
                base["incompatible_pairs"].append(pair)
            else:
                base["not_comparable_pairs"].append(pair)
    if base["compatible_pairs"]:
        base["relation"] = "OVERLAP" if len(old_records) > 1 or len(fresh_records) > 1 else "AGREEMENT"
        base["shared_compatible_region"] = True
    elif base["incompatible_pairs"]:
        base["relation"] = "INCOMPATIBLE"
        if temporal_order:
            base["PROSPECTIVE_CONFLICT"] = "PRESENT"
    else:
        base["relation"] = "NOT_COMPARABLE"
    return base
