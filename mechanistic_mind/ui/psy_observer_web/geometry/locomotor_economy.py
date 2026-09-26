"""BETA2-BODY-01 — Observer-only Locomotor Economy forensics.

Composes GEO-03 action realization + GEO-04 work budget into per-MOVE
efficiency / motor-authority receipts. Passive: no physics mutation.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Any

from mechanistic_mind.ui.psy_observer_web.geometry.action_realization import (
    build_action_realization_receipt,
    compact_receipt as compact_ar,
)
from mechanistic_mind.ui.psy_observer_web.geometry.work_ecology import (
    build_work_budget_receipt,
    compact_work_budget,
    local_resource_opportunity,
)

SCHEMA = "mm.locomotor_economy_receipt.v1"
HISTORY_MAX = 64
# Denominator protection for work/distance ratios (world units).
EPS_DISTANCE = 1e-3


def _f(v: Any, default: float | None = 0.0) -> float | None:
    if v is None:
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _mag(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(math.hypot(float(v[0]), float(v[1])))
    except (TypeError, IndexError, ValueError):
        return None


def _efficiency(cost: float | None, distance: float | None) -> dict[str, Any]:
    d = float(distance or 0.0)
    if d < EPS_DISTANCE:
        return {
            "status": "DENOMINATOR_TOO_SMALL",
            "epsilon": EPS_DISTANCE,
            "value": None,
        }
    if cost is None:
        return {"status": "NOT_AVAILABLE", "value": None}
    return {
        "status": "AVAILABLE",
        "value": float(cost) / d,
        "epsilon": EPS_DISTANCE,
    }


def motor_authority_class(work_fraction: float | None, work_limited: bool) -> str:
    if work_fraction is None:
        return "NOT_AVAILABLE"
    wf = float(work_fraction)
    if wf >= 0.85 and not work_limited:
        return "FULL"
    if wf >= 0.40:
        return "REDUCED"
    if wf > 1e-6:
        return "LOW"
    return "COLLAPSED"


def build_locomotor_economy_receipt(
    rt: Any,
    *,
    agent_id: str = "agent_0",
    body_id: str | None = None,
    ecology_preset: str | None = None,
) -> dict[str, Any]:
    """Observer-only per-tick locomotor economy from existing ledgers."""
    ar = build_action_realization_receipt(rt, agent_id=agent_id, body_id=body_id)
    wb = build_work_budget_receipt(rt, agent_id=agent_id, body_id=body_id, action_realization=ar)
    cfg = getattr(rt, "config", None)
    preset = ecology_preset or getattr(cfg, "ecology_preset", "CURRENT") or "CURRENT"

    move_spent = _f(wb.get("move_work_spent"))
    def_spent = _f(wb.get("deformation_work_spent"))
    motor_spent = _f(wb.get("endogenous_motor_work"))
    # Component audit: mutually exclusive ledger channels (no double-count)
    components = {
        "discrete_locomotor_action": move_spent or 0.0,
        "deformation": def_spent or 0.0,
        "endogenous_motor": motor_spent or 0.0,
    }
    total_cost = sum(components.values())
    fractions = {
        k: (v / total_cost if total_cost > 1e-15 else None)
        for k, v in components.items()
    }

    dist = _f(ar.get("realized_distance"))
    move_eff = _efficiency(move_spent, dist)
    total_eff = _efficiency(total_cost, dist)

    dv_req = _mag(ar.get("action_dv_requested_after_vmax") or ar.get("action_dv_requested"))
    dv_real = _mag(ar.get("action_dv_realized"))
    authority = None
    authority_status = "NOT_AVAILABLE"
    if dv_req is not None and dv_real is not None and dv_req > 1e-15:
        authority = dv_real / dv_req
        authority_status = "DIRECT_DELTA_V_RATIO"
    elif ar.get("work_fraction") is not None:
        authority = float(ar["work_fraction"])
        authority_status = "WORK_FRACTION_PROXY"

    wf = _f(ar.get("work_fraction") if ar.get("work_fraction") is not None else wb.get("action_work_fraction"))
    wl = bool(ar.get("work_limited") or wb.get("work_limited"))

    return {
        "schema": SCHEMA,
        "tick": ar.get("tick"),
        "agent_id": agent_id,
        "body_id": ar.get("body_id") or body_id,
        "ecology_preset": preset,
        "requested_action": ar.get("requested_action"),
        "requested_direction": ar.get("requested_direction"),
        "work_reservoir_before": wb.get("work_reservoir_before"),
        "work_reservoir_after": wb.get("work_reservoir_after"),
        "work_reservoir_max": wb.get("work_reservoir_max"),
        "work_reservoir_fraction_after": wb.get("work_reservoir_fraction_after"),
        "move_work_requested": wb.get("move_work_requested"),
        "move_work_allocated": wb.get("move_work_allocated"),
        "move_work_spent": move_spent,
        "deformation_work_requested": wb.get("deformation_work_requested"),
        "deformation_work_allocated": wb.get("deformation_work_allocated"),
        "deformation_work_spent": def_spent,
        "endogenous_motor_work": motor_spent,
        "measured_work_income": wb.get("measured_income_total"),
        "resource_conversion_income": wb.get("work_received_from_resource_conversion"),
        "realized_dx": (ar.get("realized_delta") or [None, None])[0],
        "realized_dy": (ar.get("realized_delta") or [None, None])[1],
        "realized_distance": dist,
        "pre_velocity": ar.get("pre_velocity"),
        "post_velocity": ar.get("post_velocity"),
        "action_delta_v": ar.get("action_dv_realized"),
        "action_delta_v_quantity": "DELTA_V_NOT_FORCE",
        "alignment": ar.get("action_alignment"),
        "environmental_force": ar.get("environmental_force"),
        "contact_active": ar.get("contact_active"),
        "contact_impulse": ar.get("contact_impulse"),
        "deformation": ar.get("deformation"),
        "work_fraction": wf,
        "work_limited": wl,
        "deformation_work_limited": wb.get("deformation_work_limited"),
        "geo03_outcome": ar.get("outcome"),
        "geo03_primary_constraint": ar.get("primary_constraint"),
        "geo03_secondary_constraints": ar.get("secondary_constraints") or [],
        "work_components": components,
        "work_component_fractions": fractions,
        "work_component_total": total_cost,
        "work_per_realized_distance": move_eff,
        "total_work_per_realized_distance": total_eff,
        "action_authority": authority,
        "action_authority_status": authority_status,
        "motor_authority_class": motor_authority_class(wf, wl),
        "local_resource_opportunity": wb.get("local_resource_opportunity") or local_resource_opportunity(rt),
        "unattributed_work_delta": wb.get("unattributed_work_delta"),
        "honesty": {
            "observer_only": True,
            "not_cognition_input": True,
            "no_fabricated_forces": True,
            "no_double_count": True,
            "physical_language_only": True,
        },
    }


def compact_locomotor_economy(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "tick": receipt.get("tick"),
        "agent_id": receipt.get("agent_id"),
        "ecology_preset": receipt.get("ecology_preset"),
        "requested_action": receipt.get("requested_action"),
        "work_reservoir_after": receipt.get("work_reservoir_after"),
        "work_reservoir_max": receipt.get("work_reservoir_max"),
        "work_reservoir_fraction_after": receipt.get("work_reservoir_fraction_after"),
        "move_work_requested": receipt.get("move_work_requested"),
        "move_work_allocated": receipt.get("move_work_allocated"),
        "move_work_spent": receipt.get("move_work_spent"),
        "work_fraction": receipt.get("work_fraction"),
        "work_limited": receipt.get("work_limited"),
        "realized_distance": receipt.get("realized_distance"),
        "alignment": receipt.get("alignment"),
        "work_per_realized_distance": receipt.get("work_per_realized_distance"),
        "motor_authority_class": receipt.get("motor_authority_class"),
        "geo03_outcome": receipt.get("geo03_outcome"),
        "geo03_primary_constraint": receipt.get("geo03_primary_constraint"),
        "action_authority": receipt.get("action_authority"),
    }


class LocomotorEconomyAccumulator:
    def __init__(self, maxlen: int = HISTORY_MAX) -> None:
        self._by_agent: dict[str, deque[dict[str, Any]]] = {}
        self._maxlen = int(maxlen)
        self.latest: dict[str, dict[str, Any]] = {}

    def observe(self, receipt: dict[str, Any]) -> None:
        aid = str(receipt.get("agent_id") or "agent_0")
        ring = self._by_agent.setdefault(aid, deque(maxlen=self._maxlen))
        if ring and int(ring[-1].get("tick") or -1) == int(receipt.get("tick") or -2):
            ring[-1] = receipt
        else:
            ring.append(receipt)
        self.latest[aid] = receipt

    def history(self, agent_id: str | None = None, limit: int = 48) -> list[dict[str, Any]]:
        if agent_id:
            return list(self._by_agent.get(agent_id, []))[-int(limit):]
        out: list[dict[str, Any]] = []
        for ring in self._by_agent.values():
            out.extend(ring)
        out.sort(key=lambda r: int(r.get("tick") or 0))
        return out[-int(limit):]

    def compact_live(self, *, history_limit: int = 12) -> dict[str, Any]:
        return {
            "status": "AVAILABLE",
            "latest_by_agent": {a: compact_locomotor_economy(r) for a, r in self.latest.items()},
            "recent": [compact_locomotor_economy(r) for r in self.history(limit=history_limit)],
            "honesty": {"observer_only": True, "physical_language_only": True},
        }

    def reset(self) -> None:
        self._by_agent.clear()
        self.latest.clear()


def collect_locomotor_from_runtime(
    runtime: Any,
    *,
    experimenter_slot: int | None = None,
) -> list[dict[str, Any]]:
    slots = getattr(runtime, "slots", None)
    preset = getattr(getattr(runtime, "config", None), "ecology_preset", "CURRENT")
    out: list[dict[str, Any]] = []
    if slots:
        from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids
        for i, rt in enumerate(slots):
            aid, bid = slot_agent_body_ids(i, experimenter_slot=experimenter_slot)
            out.append(build_locomotor_economy_receipt(
                rt, agent_id=aid, body_id=bid, ecology_preset=preset,
            ))
    else:
        out.append(build_locomotor_economy_receipt(
            runtime, agent_id="agent_0", body_id="body-0", ecology_preset=preset,
        ))
    return out
