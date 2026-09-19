"""BETA2-GEO-04 — Observer-only Work Budget / Work Ecology forensics.

Tracks measured work income/cost from existing runtime ledgers.
Does not alter autonomous physics or invent balancing categories.
"""
from __future__ import annotations

import math
from collections import deque
from typing import Any

SCHEMA = "mm.work_budget_receipt.v1"
HISTORY_MAX = 64

# Reservoir fraction thresholds (physical, not affective).
FRAC_LOW_25 = 0.25
FRAC_LOW_10 = 0.10
FRAC_NEAR_ZERO = 0.02


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _resource_sum(body: Any, attr: str) -> float:
    arr = getattr(body, attr, None)
    if arr is None:
        return 0.0
    try:
        return float(arr.sum())
    except Exception:
        try:
            return float(sum(arr))
        except Exception:
            return 0.0


def local_resource_opportunity(rt: Any) -> dict[str, Any]:
    """O(1)/O(footprint) local opportunity — not a map scan."""
    body = getattr(rt, "body", None)
    world = getattr(rt, "world", None)
    if body is None or world is None:
        return {"status": "NOT_AVAILABLE"}
    try:
        iy = int(float(body.y)) % int(world.T.shape[0])
        ix = int(float(body.x)) % int(world.T.shape[1])
    except Exception:
        return {"status": "NOT_AVAILABLE"}
    ra = getattr(world, "R_A", None)
    rb = getattr(world, "R_B", None)
    r_env = getattr(world, "R", None)
    local_a = float(ra[iy, ix]) if ra is not None else None
    local_b = float(rb[iy, ix]) if rb is not None else None
    local_r = float(r_env[iy, ix]) if r_env is not None else None
    body_a = _resource_sum(body, "R_A_site")
    body_b = _resource_sum(body, "R_B_site")
    body_r = _resource_sum(body, "R_site")
    observed = False
    for v in (local_a, local_b, local_r, body_a, body_b, body_r):
        if v is not None and float(v) > 1e-6:
            observed = True
            break
    return {
        "status": "OBSERVED" if observed else "NOT_OBSERVED",
        "cell": [ix, iy],
        "local_R_A": local_a,
        "local_R_B": local_b,
        "local_R": local_r,
        "body_R_A": body_a,
        "body_R_B": body_b,
        "body_R": body_r,
        "provenance": "DIRECT_SITE_SAMPLE",
    }


def build_work_budget_receipt(
    rt: Any,
    *,
    agent_id: str = "agent_0",
    body_id: str | None = None,
    action_realization: dict[str, Any] | None = None,
    reservoir_before_override: float | None = None,
) -> dict[str, Any]:
    """Build one Observer-only work budget receipt from post-tick ledgers."""
    body = getattr(rt, "body", None)
    cfg = getattr(rt, "config", None)
    w_max = _f(getattr(getattr(cfg, "deformation_work", None), "reservoir_max", 4.0), 4.0)
    w_after = _f(getattr(body, "mechanical_work_reservoir", 0.0))

    motion = getattr(rt, "last_motion_receipt", None) or {}
    before_body = (motion.get("before") or {}).get("body") or {}
    w_before = (
        float(reservoir_before_override)
        if reservoir_before_override is not None
        else _f(before_body.get("mechanical_work_reservoir"), w_after)
    )

    aw = getattr(rt, "last_action_work_ledger", None) or {}
    alloc = getattr(rt, "last_work_allocation", None) or {}
    mw = getattr(rt, "last_motor_work_ledger", None) or {}
    deform = getattr(rt, "last_deformation_meta", None) or {}
    comp = getattr(rt, "last_complementary_ledger", None) or {}
    eres = getattr(rt, "last_resource_ledger", None) or {}
    supply = getattr(rt, "last_experimenter_research_supply", None) or {}

    # Income (measured only)
    research_income = _f(supply.get("credited"))
    trickle_meta = getattr(rt, "last_passive_reservoir_trickle", None) or {}
    trickle_income = _f(trickle_meta.get("credited")) if trickle_meta.get("enabled") else 0.0
    comp_income = _f(comp.get("work_credited"))
    env_conv = _f(eres.get("work_credited") or eres.get("converted_work") or 0.0)
    if env_conv <= 0.0 and isinstance(eres, dict):
        env_conv = _f(eres.get("conversion_work") or eres.get("work_from_conversion"))

    income = {
        "experimenter_research_supply": research_income,
        "complementary_conversion": comp_income,
        "environmental_conversion": env_conv,
        "passive_body_trickle": trickle_income or 0.0,
    }
    measured_income = sum(income.values())

    # Costs (measured only)
    move_spent = _f(aw.get("action_work_realized"))
    move_req = _f(aw.get("action_work_requested"))
    move_alloc = _f(aw.get("action_work_allocated") or alloc.get("allocated_action"))
    def_spent = _f(deform.get("reservoir_work_supplied") or deform.get("work_realized"))
    def_req = _f(deform.get("work_requested") or alloc.get("requested_deformation"))
    def_alloc = _f(alloc.get("allocated_deformation"))
    motor_spent = _f(mw.get("motor_work_realized"))
    motor_req = _f(mw.get("motor_work_requested") or alloc.get("requested_motor"))

    costs = {
        "move": move_spent,
        "deformation": def_spent,
        "endogenous_motor": motor_spent,
    }
    measured_costs = sum(costs.values())

    # Residual: after should equal before + income - costs + unattributed
    # Chronology: research supply is income before spend; resources income after spend.
    expected_after = w_before + measured_income - measured_costs
    unattributed = w_after - expected_after

    ar = action_realization or {}
    resource_opp = local_resource_opportunity(rt)

    bid = body_id
    if not bid:
        if str(agent_id).startswith("agent_"):
            bid = f"body-{str(agent_id).replace('agent_', '')}"
        elif str(agent_id) == "undercover" or str(agent_id).startswith("experimenter"):
            bid = "body-2"
        else:
            bid = "body-0"

    return {
        "schema": SCHEMA,
        "tick": int(getattr(rt, "tick", 0) or 0),
        "agent_id": agent_id,
        "body_id": bid,
        "work_reservoir_before": w_before,
        "work_reservoir_after": w_after,
        "work_reservoir_max": w_max,
        "work_reservoir_fraction_after": (w_after / w_max) if w_max > 1e-12 else None,
        "work_generated": measured_income,  # alias: measured income this tick
        "work_received_from_resource_conversion": comp_income + env_conv,
        "work_other_income": research_income,
        "income": income,
        "move_work_requested": move_req,
        "move_work_allocated": move_alloc,
        "move_work_spent": move_spent,
        "deformation_work_requested": def_req,
        "deformation_work_allocated": def_alloc,
        "deformation_work_spent": def_spent,
        "endogenous_motor_work": motor_spent,
        "endogenous_motor_work_requested": motor_req,
        "other_measured_work_costs": 0.0,
        "costs": costs,
        "resource_A_after": _resource_sum(body, "R_A_site"),
        "resource_B_after": _resource_sum(body, "R_B_site"),
        "resource_A_before": "NOT_SEPARATELY_RECORDED",
        "resource_B_before": "NOT_SEPARATELY_RECORDED",
        "resource_transfer_events": {
            "A_transferred": _f((comp.get("A") or {}).get("transferred") or (comp.get("A") or {}).get("acquired")),
            "B_transferred": _f((comp.get("B") or {}).get("transferred") or (comp.get("B") or {}).get("acquired")),
            "provenance": "DIRECT" if comp else "NOT_RECORDED",
        },
        "resource_to_work_conversion_events": {
            "complementary_work_credited": comp_income,
            "environmental_work_credited": env_conv,
            "consumed_A": _f(comp.get("consumed_A")),
            "consumed_B": _f(comp.get("consumed_B")),
            "limiting_resource": comp.get("limiting_resource"),
            "provenance": "DIRECT" if (comp or eres) else "NOT_RECORDED",
        },
        "net_work_delta": w_after - w_before,
        "measured_income_total": measured_income,
        "measured_cost_total": measured_costs,
        "expected_after_from_measured": expected_after,
        "unattributed_work_delta": unattributed,
        "unattributed_note": (
            "UNATTRIBUTED_WORK_DELTA" if abs(unattributed) > 1e-6 else "BALANCED_WITHIN_TOLERANCE"
        ),
        "work_limited": bool(aw.get("work_limited") or aw.get("work_unavailable")),
        "deformation_work_limited": bool(deform.get("work_limited")) if isinstance(deform, dict) else False,
        "action": getattr(rt, "last_selected_action", None) or aw.get("selected_action"),
        "action_realization_outcome": ar.get("outcome"),
        "action_realization_primary_constraint": ar.get("primary_constraint"),
        "action_work_fraction": aw.get("action_work_limit_fraction"),
        "local_resource_opportunity": resource_opp,
        "experimenter_research_supply": supply if supply else {"status": "NONE"},
        "honesty": {
            "observer_only": True,
            "not_cognition_input": True,
            "no_fabricated_categories": True,
            "physical_language_only": True,
        },
    }


def compact_work_budget(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "tick": receipt.get("tick"),
        "agent_id": receipt.get("agent_id"),
        "body_id": receipt.get("body_id"),
        "work_reservoir_before": receipt.get("work_reservoir_before"),
        "work_reservoir_after": receipt.get("work_reservoir_after"),
        "work_reservoir_max": receipt.get("work_reservoir_max"),
        "work_reservoir_fraction_after": receipt.get("work_reservoir_fraction_after"),
        "measured_income_total": receipt.get("measured_income_total"),
        "measured_cost_total": receipt.get("measured_cost_total"),
        "income": receipt.get("income"),
        "costs": receipt.get("costs"),
        "unattributed_work_delta": receipt.get("unattributed_work_delta"),
        "work_limited": receipt.get("work_limited"),
        "deformation_work_limited": receipt.get("deformation_work_limited"),
        "action": receipt.get("action"),
        "action_realization_outcome": receipt.get("action_realization_outcome"),
        "action_realization_primary_constraint": receipt.get("action_realization_primary_constraint"),
        "local_resource_opportunity": {
            "status": (receipt.get("local_resource_opportunity") or {}).get("status"),
        },
        "low_work_episode_ticks": receipt.get("low_work_episode_ticks"),
        "episode_state": receipt.get("episode_state"),
    }


class WorkEcologyAccumulator:
    """Bounded per-agent work ecology rings + low-work episode tracking."""

    def __init__(self, maxlen: int = HISTORY_MAX) -> None:
        self._by_agent: dict[str, deque[dict[str, Any]]] = {}
        self._maxlen = int(maxlen)
        self.latest: dict[str, dict[str, Any]] = {}
        self._episode: dict[str, dict[str, Any]] = {}
        self._prev_w: dict[str, float] = {}
        self._series: dict[str, deque[float]] = {}  # reservoir after for sparkline

    def observe(self, receipt: dict[str, Any]) -> dict[str, Any]:
        aid = str(receipt.get("agent_id") or "agent_0")
        w_max = _f(receipt.get("work_reservoir_max"), 4.0)
        w_after = _f(receipt.get("work_reservoir_after"))
        frac = (w_after / w_max) if w_max > 1e-12 else 0.0

        ep = self._episode.setdefault(aid, {
            "active": False,
            "ticks": 0,
            "entered_tick": None,
            "recoveries": 0,
            "last_recovery_tick": None,
            "last_recovery_preceding": None,
        })
        was_active = bool(ep["active"])
        low = frac <= FRAC_LOW_10
        if low:
            if not was_active:
                ep["active"] = True
                ep["entered_tick"] = receipt.get("tick")
                ep["ticks"] = 1
            else:
                ep["ticks"] = int(ep["ticks"]) + 1
        else:
            if was_active:
                ep["active"] = False
                ep["recoveries"] = int(ep["recoveries"]) + 1
                ep["last_recovery_tick"] = receipt.get("tick")
                # Preceding measured event (income this tick or resource opportunity)
                income = receipt.get("income") or {}
                prec = []
                if _f(income.get("complementary_conversion")) > 1e-9:
                    prec.append("COMPLEMENTARY_CONVERSION")
                if _f(income.get("environmental_conversion")) > 1e-9:
                    prec.append("ENVIRONMENTAL_CONVERSION")
                if _f(income.get("experimenter_research_supply")) > 1e-9:
                    prec.append("EXPERIMENTER_RESEARCH_SUPPLY")
                opp = (receipt.get("local_resource_opportunity") or {}).get("status")
                if opp == "OBSERVED":
                    prec.append("LOCAL_RESOURCE_PRESENT")
                ep["last_recovery_preceding"] = prec or ["NOT_SEPARATELY_ATTRIBUTABLE"]
            ep["ticks"] = 0

        receipt = dict(receipt)
        receipt["episode_state"] = "LOW_WORK" if ep["active"] else "ABOVE_LOW_THRESHOLD"
        receipt["low_work_episode_ticks"] = int(ep["ticks"]) if ep["active"] else 0
        receipt["low_work_recoveries"] = int(ep["recoveries"])
        receipt["bins"] = {
            "leq_25pct": frac <= FRAC_LOW_25,
            "leq_10pct": frac <= FRAC_LOW_10,
            "near_zero": frac <= FRAC_NEAR_ZERO,
        }

        ring = self._by_agent.setdefault(aid, deque(maxlen=self._maxlen))
        if ring and int(ring[-1].get("tick") or -1) == int(receipt.get("tick") or -2):
            ring[-1] = receipt
        else:
            ring.append(receipt)
        self.latest[aid] = receipt
        self._prev_w[aid] = w_after
        series = self._series.setdefault(aid, deque(maxlen=48))
        series.append(w_after)
        return receipt

    def history(self, agent_id: str | None = None, limit: int = 48) -> list[dict[str, Any]]:
        if agent_id:
            return list(self._by_agent.get(agent_id, []))[-int(limit):]
        out: list[dict[str, Any]] = []
        for ring in self._by_agent.values():
            out.extend(ring)
        out.sort(key=lambda r: int(r.get("tick") or 0))
        return out[-int(limit):]

    def compact_live(self, *, history_limit: int = 16) -> dict[str, Any]:
        latest_c = {aid: compact_work_budget(r) for aid, r in self.latest.items()}
        spark = {aid: list(s) for aid, s in self._series.items()}
        episodes = {aid: dict(ep) for aid, ep in self._episode.items()}
        return {
            "status": "AVAILABLE",
            "latest_by_agent": latest_c,
            "recent": [compact_work_budget(r) for r in self.history(limit=history_limit)],
            "reservoir_sparkline": spark,
            "episodes": episodes,
            "honesty": {
                "observer_only": True,
                "physical_language_only": True,
                "not_hungry_tired_labels": True,
            },
        }

    def reset(self) -> None:
        self._by_agent.clear()
        self.latest.clear()
        self._episode.clear()
        self._prev_w.clear()
        self._series.clear()


def collect_work_budgets_from_runtime(
    runtime: Any,
    *,
    experimenter_slot: int | None = None,
    action_realization_latest: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """O(agents) collection after scientific tick."""
    slots = getattr(runtime, "slots", None)
    ar_map = action_realization_latest or {}
    out: list[dict[str, Any]] = []
    if slots:
        from mechanistic_mind.ui.psy_observer_web.undercover_identity import slot_agent_body_ids
        for i, rt in enumerate(slots):
            aid, bid = slot_agent_body_ids(i, experimenter_slot=experimenter_slot)
            out.append(build_work_budget_receipt(
                rt,
                agent_id=aid,
                body_id=bid,
                action_realization=ar_map.get(aid),
            ))
    else:
        out.append(build_work_budget_receipt(
            runtime,
            agent_id="agent_0",
            body_id="body-0",
            action_realization=ar_map.get("agent_0"),
        ))
    return out
