"""Researcher bridge from a realized MOVE to the next ordinary observation.

Does not change traction physics, add a sensor, or teach a material rule.
Cognition already receives body.vx / body.vy on the following tick. This module
only records that existing link for researchers, including whether prediction
error and bounded memory actually stored it.

Temporal order:
    action tick → physical realization → next-tick observation → attribution
A pending slot closes only when current_tick == action_tick + 1. A later tick
drops the slot instead of attaching the old consequence to a new action.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from typing import Any

SURFACE_TRACTION_EXPERIENCE_BRIDGE = "surface_traction_experience_bridge"
EVENT_EXPERIENCE = "TRACTION_EXPERIENCE"
CAUSAL_ORDER = "ACTION_THEN_NEXT_OBSERVATION"
HISTORY_LIMIT = 8
MOVE_COMMANDS = ("MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W")
INTERVENTION_SOURCES = frozenset({"FORCED_COMPOSITE", "FORCED_GATE"})
AGENT_VISIBLE_KEYS = (
    "body.vx",
    "body.vy",
    "body.mech",
    "vest_0",
    "vest_1",
    "prop_neck_0",
    "prop_neck_1",
)
RESEARCHER_ONLY_FIELDS = (
    "deposit_id",
    "surface_affinity",
    "traction_multiplier",
    "formula_version",
    "causal_source",
    "derivation_version",
)


@dataclass
class SurfaceTractionExperienceConfig:
    """Fresh default OFF. A missing snapshot field stays OFF."""

    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SurfaceTractionExperienceConfig":
        if not data:
            return cls()
        payload = {k: data[k] for k in (f.name for f in fields(cls)) if k in data}
        return cls(**payload)


def surface_traction_experience_is_active(config: Any) -> bool:
    """ON only for Acanthostega when traction itself is already active."""
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "surface_traction_experience", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.surface_affinity_traction import (
        surface_affinity_traction_is_active,
    )

    return bool(surface_affinity_traction_is_active(config))


def set_surface_traction_experience(config: Any, enabled: bool) -> None:
    if config is None:
        return
    cfg = getattr(config, "surface_traction_experience", None)
    if cfg is None:
        cfg = SurfaceTractionExperienceConfig()
        config.surface_traction_experience = cfg
    acanthostega = str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cfg.enabled = bool(enabled) and acanthostega


def note_physical(
    *,
    tick: int,
    body_id: str,
    command: str,
    plan: dict[str, Any],
    requested_dv: list[float],
    scaled_dv: list[float],
    after_vmax_dv: list[float],
    velocity_before: list[float],
    position_before: list[float],
) -> dict[str, Any]:
    """Bounded physical note. No cognition payload and no composition copy."""
    return {
        "action_tick": int(tick),
        "body_id": str(body_id),
        "agent_id": str(body_id),
        "selected_motor_command": str(command),
        "cell_before": {
            "cell_x": int(plan.get("cell_x") or 0),
            "cell_y": int(plan.get("cell_y") or 0),
            "policy": plan.get("cell_policy"),
        },
        "position_before": [float(position_before[0]), float(position_before[1])],
        "requested_locomotor_dv": [float(requested_dv[0]), float(requested_dv[1])],
        "traction_scaled_dv": [float(scaled_dv[0]), float(scaled_dv[1])],
        "after_vmax_dv": [float(after_vmax_dv[0]), float(after_vmax_dv[1])],
        "velocity_before": [float(velocity_before[0]), float(velocity_before[1])],
        "deposit_id": plan.get("deposit_id") or "NONE",
        "deposit_created_tick": plan.get("deposit_created_tick"),
        "deposit_last_updated_tick": plan.get("deposit_last_updated_tick"),
        "deposit_eligible_this_tick": bool(plan.get("deposit_eligible_this_tick")),
        "deposition_event_ids": list(plan.get("deposition_event_ids") or [])[:4],
        "surface_affinity": float(plan.get("surface_affinity") or 0.5),
        "traction_multiplier": float(plan.get("traction_multiplier") or 1.0),
        "formula_version": plan.get("formula_version"),
        "derivation_version": plan.get("derivation_version"),
        "causal_source": plan.get("causal_source"),
    }


def open_pending(
    physical: dict[str, Any],
    *,
    realized_dv: list[float],
    velocity_after: list[float],
    position_after: list[float],
    displacement: list[float],
    cell_after: dict[str, Any],
    work_request: float | None,
    work_realized: float | None,
    selection_source: str,
) -> dict[str, Any]:
    source = str(selection_source or "")
    provenance = "INTERVENTION" if source in INTERVENTION_SOURCES else "ENDOGENOUS"
    pending = dict(physical)
    pending.update({
        "realized_dv": [float(realized_dv[0]), float(realized_dv[1])],
        "velocity_after": [float(velocity_after[0]), float(velocity_after[1])],
        "position_after_action": [float(position_after[0]), float(position_after[1])],
        "displacement": [float(displacement[0]), float(displacement[1])],
        "cell_after_action": cell_after,
        "work_request": work_request,
        "work_realized": work_realized,
        "selection_source": source or None,
        "action_provenance": provenance,
        "setup_separated_from_agent_action": True,
    })
    return pending


def _memory_and_error(cognition: Any, *, command: str, tick: int) -> dict[str, Any]:
    empty = {
        "memory_status": "NOT_AVAILABLE",
        "memory_reference": None,
        "prediction_error_status": "NOT_AVAILABLE",
        "prediction_error_abs_l1": None,
    }
    if not isinstance(cognition, dict):
        return empty
    comp = cognition.get("compression")
    if not isinstance(comp, dict):
        return empty
    recent = comp.get("recent") or []
    if not recent:
        return empty
    rid = recent[-1]
    raw_log = comp.get("raw_log") or {}
    raw = raw_log.get(rid)
    if raw is None:
        raw = raw_log.get(str(rid))
    if not isinstance(raw, dict):
        return empty
    if int(raw.get("tick", -1)) != int(tick) or str(raw.get("action") or "") != str(command):
        return empty
    predicted = raw.get("predicted") or {}
    has_prediction = isinstance(predicted, dict) and len(predicted) > 0
    return {
        "memory_status": "OBSERVED",
        "memory_reference": {
            "raw_id": raw.get("raw_id"),
            "tick": raw.get("tick"),
            "action": raw.get("action"),
        },
        "prediction_error_status": "OBSERVED" if has_prediction else "NOT_AVAILABLE",
        "prediction_error_abs_l1": (
            float(raw.get("abs_l1") or 0.0) if has_prediction else None
        ),
    }


def close_pending(
    pending: dict[str, Any],
    *,
    tick: int,
    observation: dict[str, Any] | None,
    cognition: Any,
    cognition_enabled: bool,
    last_closed_action_tick: int | None,
) -> tuple[str, dict[str, Any] | None]:
    """Return ('emit', receipt), ('duplicate', None), or ('drop', None)."""
    action_tick = int(pending["action_tick"])
    if last_closed_action_tick is not None and int(last_closed_action_tick) == action_tick:
        return "duplicate", None
    if int(tick) != action_tick + 1:
        return "drop", None
    delivered = bool(cognition_enabled and isinstance(observation, dict))
    visible: dict[str, float] = {}
    if delivered:
        for key in AGENT_VISIBLE_KEYS:
            if key in observation:
                visible[key] = float(observation[key])
    link = (
        _memory_and_error(
            cognition,
            command=str(pending.get("selected_motor_command") or ""),
            tick=int(tick),
        )
        if delivered
        else {
            "memory_status": "NOT_AVAILABLE",
            "memory_reference": None,
            "prediction_error_status": "NOT_AVAILABLE",
            "prediction_error_abs_l1": None,
        }
    )
    receipt = {
        "event": EVENT_EXPERIENCE,
        "body_id": pending.get("body_id"),
        "agent_id": pending.get("agent_id"),
        "selected_motor_command": pending.get("selected_motor_command"),
        "action_tick": action_tick,
        "consequence_observation_tick": int(tick),
        "action_consequence_latency_ticks": 1,
        "causal_order": CAUSAL_ORDER,
        "cell_before": pending.get("cell_before"),
        "cell_after_action": pending.get("cell_after_action"),
        "position_before": list(pending.get("position_before") or []),
        "position_after_action": list(pending.get("position_after_action") or []),
        "requested_locomotor_dv": list(pending.get("requested_locomotor_dv") or []),
        "traction_scaled_dv": list(pending.get("traction_scaled_dv") or []),
        "realized_dv": list(pending.get("realized_dv") or []),
        "displacement": list(pending.get("displacement") or []),
        "velocity_before": list(pending.get("velocity_before") or []),
        "velocity_after": list(pending.get("velocity_after") or []),
        "work_request": pending.get("work_request"),
        "work_realized": pending.get("work_realized"),
        "prediction_error_status": link["prediction_error_status"],
        "prediction_error_abs_l1": link["prediction_error_abs_l1"],
        "memory_status": link["memory_status"],
        "memory_reference": link["memory_reference"],
        "action_provenance": pending.get("action_provenance"),
        "selection_source": pending.get("selection_source"),
        "setup_separated_from_agent_action": True,
        "cognition_delivered": delivered,
        "agent_visible_fields": visible,
        "agent_visible_field_names": sorted(visible),
        "researcher_only_fields": {
            "deposit_id": pending.get("deposit_id") or "NONE",
            "surface_affinity": pending.get("surface_affinity"),
            "traction_multiplier": pending.get("traction_multiplier"),
            "formula_version": pending.get("formula_version"),
            "derivation_version": pending.get("derivation_version"),
            "causal_source": pending.get("causal_source"),
            "deposit_created_tick": pending.get("deposit_created_tick"),
            "deposit_last_updated_tick": pending.get("deposit_last_updated_tick"),
            "deposit_eligible_this_tick": pending.get("deposit_eligible_this_tick"),
            "deposition_event_ids": list(pending.get("deposition_event_ids") or []),
        },
        "researcher_only": True,
        "agent_accessible": False,
        "recipe_match": False,
        "semantic_effect": False,
        "learning_established": False,
        "instrumental_use_established": False,
    }
    return "emit", receipt


def surface_traction_experience_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": SURFACE_TRACTION_EXPERIENCE_BRIDGE,
        "label": "Surface traction experience bridge",
        "enabled": bool(enabled),
        "scientific_status": "IMPLEMENTED" if enabled else "OFF",
        "promotion_class": "EXPERIMENTAL",
        "note": (
            "researcher-only. not agent-accessible. "
            "Records the existing body consequence of MOVE. Not a material sensor."
        ),
    }
