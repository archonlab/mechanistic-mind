"""Bounded LIVE geometry summary for compact Observer frames."""
from __future__ import annotations

from typing import Any

from mechanistic_mind.ui.psy_observer_web.geometry.ground_truth import (
    flow_vector_grid,
    sample_force_contributions,
    sample_local_flow,
)
from mechanistic_mind.ui.psy_observer_web.geometry.metrics import (
    action_alignment,
    action_direction_unit,
    realized_displacement,
    traversal_outcome_class,
)


def geometry_live_compact_summary(
    runtime: Any,
    *,
    previous_body: dict[str, Any] | None = None,
    previous_bodies: dict[str, dict[str, Any]] | None = None,
    traversability_overlay: dict[str, Any] | None = None,
    include_flow_overlay: bool = False,
    flow_stride: int = 2,
) -> dict[str, Any]:
    """Cheap per-tick geometry facts for RUNNING compact frames.

    No full-world scans. No unbounded history. Observer-only.
    """
    world = getattr(runtime, "world", None)
    width = 32
    height = 32
    if world is not None:
        t = getattr(world, "T", None)
        if t is not None and hasattr(t, "shape") and len(t.shape) >= 2:
            height, width = int(t.shape[0]), int(t.shape[1])
        else:
            planet = getattr(getattr(runtime, "config", None), "planet", None)
            if planet is not None:
                width = int(planet.width)
                height = int(planet.height)
    slots = getattr(runtime, "slots", None)
    agents_out: list[dict[str, Any]] = []

    def one(slot: Any, aid: str, prev: dict[str, Any] | None) -> dict[str, Any]:
        body = slot.body
        x = float(body.x)
        y = float(body.y)
        action = getattr(slot, "last_selected_action", None)
        unit = action_direction_unit(action)
        flow = sample_local_flow(runtime, x=x, y=y)
        contact = None
        last_contact = getattr(runtime, "last_contact", None)
        if isinstance(last_contact, dict):
            contact = bool(last_contact.get("active") or last_contact.get("contact"))
        row: dict[str, Any] = {
            "agent_id": aid,
            "x": x,
            "y": y,
            "action": action,
            "requested_unit": list(unit) if unit else None,
            "local_flow": {
                "vx": flow.get("local_flow_vx"),
                "vy": flow.get("local_flow_vy"),
                "mag": flow.get("local_flow_mag"),
                "status": flow.get("status"),
            },
            "contact": contact,
        }
        if prev is not None and "x" in prev and "y" in prev:
            dx, dy, mag = realized_displacement(
                float(prev["x"]), float(prev["y"]), x, y, width=width, height=height,
            )
            align = action_alignment(action, dx, dy)
            outcome = traversal_outcome_class(action, dx, dy)
            row["since_prev_capture"] = {
                "dx": dx,
                "dy": dy,
                "mag": mag,
                "action_alignment": align,
                "outcome": outcome,
                "note": "vs previous Observer body snapshot; not necessarily 1-tick",
            }
            if outcome == "OPPOSING_DISPLACEMENT" and align is not None and align <= -0.7 and mag > 0.05:
                row["motion_class"] = "STRONG_DEFLECTION"
            elif outcome == "OPPOSING_DISPLACEMENT":
                row["motion_class"] = "REVERSAL"
            elif outcome == "ALIGNED_TRAVERSAL":
                row["motion_class"] = "ALIGNED"
            elif outcome == "DEFLECTED_DISPLACEMENT":
                row["motion_class"] = "DEFLECTED"
            else:
                row["motion_class"] = outcome
        return row

    if slots:
        prev_map = previous_bodies or {}
        sel = int(getattr(runtime, "selected_index", 0) or 0)
        for i, slot in enumerate(slots):
            aid = f"agent_{i}"
            prev = prev_map.get(aid)
            if prev is None and i == sel:
                prev = previous_body
            agents_out.append(one(slot, aid, prev))
    else:
        agents_out.append(one(runtime, "agent_0", previous_body))

    out: dict[str, Any] = {
        "detail": "compact",
        "observer_only": True,
        "tick": int(getattr(runtime, "tick", -1)),
        "world_size": {"width": width, "height": height},
        "agents": agents_out,
        "force_contributions": sample_force_contributions(runtime),
        "honesty": {
            "no_semantic_terrain": True,
            "not_agent_map": True,
            "structure": "emergent_flow_soft_contact",
            "physical_field": "runtime ground truth",
            "empirical_traversability": "historical observed movement outcomes",
            "trajectory": "realized agent motion",
            "no_hard_walls": True,
            "low_evidence_not_easy": True,
        },
    }
    if traversability_overlay is not None:
        out["traversability"] = traversability_overlay
    if include_flow_overlay:
        out["flow_overlay"] = flow_vector_grid(runtime, stride=flow_stride)
        out["detail"] = "full"
    return out
