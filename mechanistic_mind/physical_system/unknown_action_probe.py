"""Unknown-action classification from existing prospective evidence.

Detection only. Does not select actions. No UNKNOWN / curiosity tokens.
"""
from __future__ import annotations

from typing import Any

from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.research import prospective_composition as pr


def classify_unmodeled_actions(
    *,
    store: dict[str, Any],
    observation: dict[str, float],
    supported_actions: list[str] | None = None,
    actions: list[str] | None = None,
) -> dict[str, Any]:
    """Derive unmodeled first-actions from MATCH/support absence only."""
    actions = list(actions or available_actions())
    supported = list(supported_actions or [])
    modeled: list[str] = []
    unmodeled: list[str] = []
    per: dict[str, Any] = {}
    for act in actions:
        one = pr.predict_one_step(store, observation, act)
        is_match = one.get("status") == "MATCH"
        is_supported = act in supported
        modeled_here = bool(is_match or is_supported)
        if modeled_here:
            modeled.append(act)
        else:
            unmodeled.append(act)
        per[act] = {
            "available": True,
            "one_step_status": one.get("status"),
            "one_step_support": int(one.get("support") or 0) if is_match else 0,
            "supported_scenario": is_supported,
            "unmodeled": not modeled_here,
        }
    return {
        "available_actions": actions,
        "modeled_first_actions": modeled,
        "supported_first_actions": supported,
        "unmodeled_first_actions": unmodeled,
        "probe_eligible": list(unmodeled),
        "per_action": per,
        "arbitration": "NOT_IMPLEMENTED_DESIGN_BOUNDARY",
        "selected_probe_action": None,
        "selection_effect": "NONE_DESIGN_BOUNDARY",
    }


def probe_receipt(*, enabled: bool, classification: dict[str, Any] | None = None) -> dict[str, Any]:
    if not enabled:
        return {
            "enabled": False,
            "selection_effect": "NONE",
            "arbitration": None,
            "selected_probe_action": None,
        }
    row = dict(classification or classify_unmodeled_actions(store=pr.empty_store(), observation={}))
    row["enabled"] = True
    return row
