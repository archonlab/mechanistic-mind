"""Analyzer section for surface-affinity traction. Separate from deposition counts."""
from __future__ import annotations

import math
from typing import Any

TRACTION_CAUSAL_EFFECT = "IMPLEMENTED"
AGENT_SYMBOLIC_TRACTION_SENSOR = "NOT_IMPLEMENTED"
RECIPE_SYSTEM = "NOT_IMPLEMENTED"
INSTRUMENTAL_USE = "NOT_ESTABLISHED"
LEARNING_FROM_TRACTION = "NOT_ESTABLISHED"

_EVENT = "SURFACE_TRACTION_APPLIED"


def _evidence(event: dict[str, Any]) -> dict[str, Any]:
    nested = event.get("evidence")
    if isinstance(nested, dict):
        return nested
    return event


def _mag(raw: Any) -> float:
    if not isinstance(raw, (list, tuple)) or len(raw) < 2:
        return 0.0
    return float(math.hypot(float(raw[0] or 0.0), float(raw[1] or 0.0)))


def summarize_surface_traction(events: list[dict[str, Any]] | None) -> dict[str, Any]:
    """SURFACE TRACTION CONSEQUENCES. Ignores RESOURCE_CHANGE, grasp, and deposition."""
    traversal = move_attempts = 0
    neutral = high = low = 0
    requested = scaled = realized = 0.0
    displacement = 0.0
    clamps = 0
    agents: set[str] = set()
    deposits: set[str] = set()
    cells: set[str] = set()
    latencies: list[int] = []
    per_deposit: dict[str, dict[str, Any]] = {}
    deposit_conserved = True
    saw_traction = False
    ratios: list[float] = []
    by_band: dict[str, list[float]] = {"low": [], "neutral": [], "high": []}
    rows: list[dict[str, Any]] = []

    for event in events or []:
        kind = str(event.get("type") or event.get("event") or event.get("kind") or "")
        evidence = _evidence(event)
        event_name = str(evidence.get("event") or kind)
        if event_name != _EVENT and kind != _EVENT:
            continue
        saw_traction = True
        eligible = bool(evidence.get("deposit_eligible_this_tick"))
        if eligible:
            traversal += 1
        command = str(evidence.get("selected_locomotor_command") or evidence.get("selected_command") or "")
        if command.startswith("MOVE"):
            move_attempts += 1
        multiplier = float(evidence.get("traction_multiplier") or 1.0)
        if multiplier > 1.0 + 1e-9:
            high += 1
            band = "high"
        elif multiplier < 1.0 - 1e-9:
            low += 1
            band = "low"
        else:
            neutral += 1
            band = "neutral"
        req = _mag(evidence.get("requested_locomotor_dv"))
        sc = _mag(evidence.get("traction_scaled_dv"))
        real = _mag(evidence.get("realized_dv"))
        disp = _mag(evidence.get("displacement_this_tick"))
        requested += req
        scaled += sc
        realized += real
        displacement += disp
        if req > 1e-12:
            ratio = real / req
            ratios.append(ratio)
            by_band[band].append(real)
        if evidence.get("v_max_clamped"):
            clamps += 1
        agent = str(evidence.get("body_id") or evidence.get("agent_id") or "")
        if agent:
            agents.add(agent)
        deposit_id = str(evidence.get("deposit_id") or "")
        if deposit_id and deposit_id != "NONE":
            deposits.add(deposit_id)
        cell = evidence.get("resolved_cell") if isinstance(evidence.get("resolved_cell"), dict) else {}
        if cell:
            cells.add(f"{cell.get('cell_x')},{cell.get('cell_y')}")
        created = evidence.get("deposit_created_tick")
        tick = evidence.get("tick", event.get("tick"))
        if eligible and created is not None and tick is not None:
            latencies.append(int(tick) - int(created))
        mass_before = evidence.get("deposit_mass_before")
        mass_after = evidence.get("deposit_mass_after")
        qty_before = evidence.get("deposit_quantity_before")
        qty_after = evidence.get("deposit_quantity_after")
        if mass_before is not None and mass_after is not None:
            if abs(float(mass_before) - float(mass_after)) > 1e-9:
                deposit_conserved = False
        if qty_before is not None and qty_after is not None:
            if abs(float(qty_before) - float(qty_after)) > 1e-9:
                deposit_conserved = False
        bucket = per_deposit.setdefault(deposit_id or "NONE", {
            "deposit_id": deposit_id or "NONE",
            "move_attempts": 0,
            "realized_dv": 0.0,
            "multipliers": [],
        })
        bucket["move_attempts"] += 1 if command.startswith("MOVE") else 0
        bucket["realized_dv"] = float(bucket["realized_dv"]) + real
        bucket["multipliers"].append(multiplier)
        rows.append({
            "tick": tick,
            "deposit_id": deposit_id,
            "multiplier": multiplier,
            "eligible": eligible,
            "requested_dv": req,
            "realized_dv": real,
        })

    matched = None
    if by_band["neutral"] and (by_band["low"] or by_band["high"]):
        neutral_mean = sum(by_band["neutral"]) / len(by_band["neutral"])
        matched = {
            "neutral_mean_realized_dv": neutral_mean,
            "low_minus_neutral": (
                (sum(by_band["low"]) / len(by_band["low"])) - neutral_mean
                if by_band["low"] else None
            ),
            "high_minus_neutral": (
                (sum(by_band["high"]) / len(by_band["high"])) - neutral_mean
                if by_band["high"] else None
            ),
        }

    return {
        "section": "SURFACE TRACTION CONSEQUENCES",
        "traversal_ticks_over_eligible_deposits": traversal,
        "move_attempts_on_deposited_cells": move_attempts,
        "neutral_multiplier_count": neutral,
        "high_multiplier_count": high,
        "low_multiplier_count": low,
        "requested_dv_sum": requested,
        "traction_scaled_dv_sum": scaled,
        "realized_dv_sum": realized,
        "realized_over_requested": (sum(ratios) / len(ratios)) if ratios else None,
        "displacement_per_move_sum": displacement,
        "v_max_clamp_count": clamps,
        "affected_agent_ids": sorted(agents),
        "deposit_ids": sorted(deposits),
        "cells_traversed": sorted(cells),
        "latency_deposition_to_first_affected_move": min(latencies) if latencies else None,
        "per_deposit": per_deposit,
        "deposit_state_conserved_across_traversal": bool(deposit_conserved) if saw_traction else None,
        "OBSERVED": {
            "motor_request": requested,
            "multiplier_counts": {"low": low, "neutral": neutral, "high": high},
            "realized_dv": realized,
            "displacement": displacement,
        },
        "DERIVED": {
            "requested_vs_realized": (sum(ratios) / len(ratios)) if ratios else None,
            "matched_control_difference": matched,
            "latency": min(latencies) if latencies else None,
            "repeated_exploitation_candidate": False,
        },
        "NOT_ESTABLISHED": [
            "recognition",
            "intention",
            "usefulness",
            "learning",
            "strategy",
            "instrumental exploitation",
        ],
        "TRACTION_CAUSAL_EFFECT": TRACTION_CAUSAL_EFFECT,
        "AGENT_SYMBOLIC_TRACTION_SENSOR": AGENT_SYMBOLIC_TRACTION_SENSOR,
        "RECIPE_SYSTEM": RECIPE_SYSTEM,
        "INSTRUMENTAL_USE": INSTRUMENTAL_USE,
        "LEARNING_FROM_TRACTION": LEARNING_FROM_TRACTION,
        "mixed_with_resource_change": False,
        "events": rows,
        "note": (
            "Observed motor request, deposit property, multiplier, and realized "
            "velocity. TRACTION_CAUSAL_EFFECT = IMPLEMENTED. "
            "INSTRUMENTAL_USE = NOT_ESTABLISHED."
        ),
    }
