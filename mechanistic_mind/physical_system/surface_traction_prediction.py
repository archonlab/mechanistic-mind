"""Researcher bridge from an issued MOVE to the existing consequence model.

Reads the generic sensorimotor consequence mean. Does not train a material
model, does not read deposit identity into the prediction key, and does not
revise anything except by letting the existing update run on the next tick.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MECHANISM_ID = "surface_traction_prediction_adaptation"
EVENT_ADAPTATION = "TRACTION_PREDICTION_ADAPTATION"
CAUSAL_ORDER = "ACTION_PREDICTION_THEN_NEXT_OBSERVATION"
HISTORY_LIMIT = 24
ADAPTATION_K = 2
ADAPTATION_N = 4
SCORED_CHANNELS = ("body.vx", "body.vy")
INTERVENTION_SOURCES = {"FORCED_COMPOSITE", "FORCED_GATE"}

PREDICTION_NOT_AVAILABLE = "PREDICTION_NOT_AVAILABLE"
ADAPTATION_OBSERVED = "ADAPTATION_OBSERVED"
NO_ADAPTATION_OBSERVED = "NO_ADAPTATION_OBSERVED"
INSUFFICIENT_VALID_EPISODES = "INSUFFICIENT_VALID_EPISODES"


@dataclass
class SurfaceTractionPredictionConfig:
    enabled: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": bool(self.enabled)}

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SurfaceTractionPredictionConfig":
        if not data:
            return cls(enabled=False)
        return cls(enabled=bool(data.get("enabled", False)))


def surface_traction_prediction_is_active(config: Any) -> bool:
    """ON only for Acanthostega when the experience bridge is already active."""
    if config is None or str(getattr(config, "model_line", "") or "").upper() != "ACANTHOSTEGA":
        return False
    cfg = getattr(config, "surface_traction_prediction", None)
    if cfg is None or not bool(getattr(cfg, "enabled", False)):
        return False
    from mechanistic_mind.physical_system.surface_traction_experience import (
        surface_traction_experience_is_active,
    )

    return bool(surface_traction_experience_is_active(config))


def set_surface_traction_prediction(config: Any, enabled: bool) -> None:
    if config is None:
        return
    cfg = getattr(config, "surface_traction_prediction", None)
    if cfg is None:
        cfg = SurfaceTractionPredictionConfig()
        config.surface_traction_prediction = cfg
    acanthostega = str(getattr(config, "model_line", "") or "").upper() == "ACANTHOSTEGA"
    cfg.enabled = bool(enabled) and acanthostega


def _context_hash(signature: dict[str, float]) -> str:
    from mechanistic_mind.physical_system.sensorimotor_consequence import hash_stable

    parts = [f"{key}:{float(signature[key]):.3f}" for key in sorted(signature)]
    return hash_stable("|".join(parts))[:16]


def peek_issued_prediction(
    cognition: Any,
    observation: dict[str, Any] | None,
    motor: dict[str, Any] | None,
) -> dict[str, Any]:
    """Read the existing consequence mean. Does not increment query counters."""
    empty = {
        "prediction_availability": PREDICTION_NOT_AVAILABLE,
        "prediction_status": PREDICTION_NOT_AVAILABLE,
        "predicted_delta": {},
        "record_id": None,
        "support_before": 0,
        "context_signature": None,
        "motor_signature": None,
        "model_schema": None,
    }
    if not isinstance(cognition, dict) or not isinstance(observation, dict):
        return empty
    store = cognition.get("sensorimotor_consequence")
    if not isinstance(store, dict) or not store.get("enabled"):
        return empty
    from mechanistic_mind.physical_system.sensorimotor_consequence import (
        SCHEMA,
        _find_row,
        channels_for_store,
        extract_sensory,
        mean_delta,
        motor_signature_from_composite,
        sensory_signature,
    )

    channels = channels_for_store(store)
    signature = sensory_signature(extract_sensory(observation, channels), channels)
    motor_signature = motor_signature_from_composite(motor)
    row = _find_row(store, signature, motor_signature)
    out = {
        **empty,
        "context_signature": _context_hash(signature),
        "motor_signature": motor_signature,
        "model_schema": SCHEMA,
    }
    if not isinstance(row, dict):
        return out
    mean = mean_delta(row)
    predicted = {
        key: float(mean.get(key, 0.0))
        for key in SCORED_CHANNELS
        if key in observation
    }
    support = int(row.get("support") or 0)
    out.update({
        "prediction_availability": "OBSERVED" if predicted else PREDICTION_NOT_AVAILABLE,
        "prediction_status": "MATCH" if support >= 3 else "LOW_SUPPORT",
        "predicted_delta": predicted,
        "record_id": row.get("record_id"),
        "support_before": support,
    })
    return out


def _support_after(cognition: Any, record_id: str | None) -> tuple[int | None, dict[str, float]]:
    if not record_id or not isinstance(cognition, dict):
        return None, {}
    store = cognition.get("sensorimotor_consequence")
    if not isinstance(store, dict):
        return None, {}
    from mechanistic_mind.physical_system.sensorimotor_consequence import mean_delta

    for row in (store.get("records") or {}).values():
        if isinstance(row, dict) and row.get("record_id") == record_id:
            mean = mean_delta(row)
            return int(row.get("support") or 0), {
                key: float(mean.get(key, 0.0)) for key in SCORED_CHANNELS
            }
    return None, {}


def open_pending(
    experience: dict[str, Any],
    *,
    issued: dict[str, Any],
    observation: dict[str, Any] | None,
    phase: str,
    reservoir_before: float | None,
    v_max: float | None,
    push: bool,
    pair_contact: bool,
    heading: float,
) -> dict[str, Any]:
    visible = {}
    if isinstance(observation, dict):
        for key in SCORED_CHANNELS:
            if key in observation:
                visible[key] = float(observation[key])
    return {
        "action_tick": int(experience.get("action_tick") or 0),
        "body_id": experience.get("body_id"),
        "agent_id": experience.get("agent_id"),
        "selected_motor_command": experience.get("selected_motor_command"),
        "action_provenance": experience.get("action_provenance"),
        "selection_source": experience.get("selection_source"),
        "exposure_phase": str(phase or "UNSPECIFIED"),
        "velocity_before": list(experience.get("velocity_before") or [0.0, 0.0]),
        "reservoir_before": None if reservoir_before is None else float(reservoir_before),
        "v_max": None if v_max is None else float(v_max),
        "push": bool(push),
        "pair_contact": bool(pair_contact),
        "heading": float(heading),
        "cell_before": experience.get("cell_before"),
        "pre_action_visible": visible,
        "issued": {
            "prediction_availability": issued.get("prediction_availability"),
            "prediction_status": issued.get("prediction_status"),
            "predicted_delta": dict(issued.get("predicted_delta") or {}),
            "record_id": issued.get("record_id"),
            "support_before": int(issued.get("support_before") or 0),
            "context_signature": issued.get("context_signature"),
            "motor_signature": issued.get("motor_signature"),
            "model_schema": issued.get("model_schema"),
        },
        "researcher_only_fields": {
            "deposit_id": experience.get("deposit_id") or "NONE",
            "surface_affinity": experience.get("surface_affinity"),
            "traction_multiplier": experience.get("traction_multiplier"),
            "formula_version": experience.get("formula_version"),
            "causal_source": experience.get("causal_source"),
        },
    }


def close_pending(
    pending: dict[str, Any],
    *,
    tick: int,
    observation: dict[str, Any] | None,
    cognition: Any,
    cognition_enabled: bool,
    last_closed_action_tick: int | None,
    episode_index: int,
) -> tuple[str, dict[str, Any] | None]:
    action_tick = int(pending["action_tick"])
    if last_closed_action_tick is not None and int(last_closed_action_tick) == action_tick:
        return "duplicate", None
    if int(tick) != action_tick + 1:
        return "drop", None
    issued = pending.get("issued") or {}
    predicted = dict(issued.get("predicted_delta") or {})
    before = dict(pending.get("pre_action_visible") or {})
    observed_absolute = {}
    observed_delta = {}
    if cognition_enabled and isinstance(observation, dict):
        for key in SCORED_CHANNELS:
            if key in observation and key in before:
                observed_absolute[key] = float(observation[key])
                observed_delta[key] = float(observation[key]) - float(before[key])
    per_field = {}
    if predicted and observed_delta:
        for key in SCORED_CHANNELS:
            if key in predicted and key in observed_delta:
                per_field[key] = abs(float(observed_delta[key]) - float(predicted[key]))
    aggregate = sum(per_field.values()) if per_field else None
    availability = (
        "OBSERVED" if predicted and observed_delta else PREDICTION_NOT_AVAILABLE
    )
    support_after, mean_after = _support_after(cognition, issued.get("record_id"))
    support_before = int(issued.get("support_before") or 0)
    revision = False
    if support_after is not None and support_after > support_before:
        revision = True
    elif mean_after and predicted:
        revision = any(
            abs(float(mean_after.get(key, 0.0)) - float(predicted.get(key, 0.0))) > 1e-12
            for key in predicted
        )
    from mechanistic_mind.physical_system.surface_traction_experience import _memory_and_error

    memory = (
        _memory_and_error(
            cognition,
            command=str(pending.get("selected_motor_command") or ""),
            tick=int(tick),
        )
        if cognition_enabled
        else {
            "memory_status": "NOT_AVAILABLE",
            "memory_reference": None,
        }
    )
    velocity = list(pending.get("velocity_before") or [0.0, 0.0])
    command = str(pending.get("selected_motor_command") or "")
    exclusion = None
    if not command.startswith("MOVE:"):
        exclusion = "NOT_MOVE"
    elif abs(float(velocity[0])) > 1e-6 or abs(float(velocity[1])) > 1e-6:
        exclusion = "VELOCITY_NOT_CONTROLLED"
    elif bool(pending.get("push")) or bool(pending.get("pair_contact")):
        exclusion = "CONTACT_OR_PUSH"
    elif availability != "OBSERVED":
        exclusion = PREDICTION_NOT_AVAILABLE
    valid = exclusion is None
    receipt = {
        "event": EVENT_ADAPTATION,
        "body_id": pending.get("body_id"),
        "agent_id": pending.get("agent_id"),
        "selected_motor_command": command,
        "action_tick": action_tick,
        "consequence_observation_tick": int(tick),
        "prediction_issued_tick": action_tick,
        "action_consequence_latency_ticks": 1,
        "causal_order": CAUSAL_ORDER,
        "causal_sequence": "action → prediction → physical outcome → error → revision",
        "exposure_phase": pending.get("exposure_phase"),
        "episode_index": int(episode_index),
        "selection_source": pending.get("selection_source"),
        "action_provenance": pending.get("action_provenance"),
        "setup_separated_from_agent_action": True,
        "prediction_availability": availability,
        "prediction_status": issued.get("prediction_status"),
        "predicted_agent_visible_delta": predicted,
        "observed_agent_visible_absolute": observed_absolute,
        "observed_agent_visible_delta": observed_delta,
        "per_field_error": per_field,
        "aggregate_error": aggregate,
        "scored_channels": list(SCORED_CHANNELS),
        "revision_applied": bool(revision),
        "model_state_reference": {
            "schema": issued.get("model_schema"),
            "record_id": issued.get("record_id"),
            "support_before": support_before,
            "support_after": support_after,
        },
        "memory_status": memory.get("memory_status"),
        "memory_reference": memory.get("memory_reference"),
        "context_signature": issued.get("context_signature"),
        "motor_signature": issued.get("motor_signature"),
        "controlled_state": {
            "velocity_before": velocity,
            "reservoir_before": pending.get("reservoir_before"),
            "v_max": pending.get("v_max"),
            "heading": pending.get("heading"),
            "cell_before": pending.get("cell_before"),
            "push": bool(pending.get("push")),
            "pair_contact": bool(pending.get("pair_contact")),
        },
        "controlled_state_valid": valid,
        "exclusion_reason": exclusion,
        "entered_adaptation_statistics": bool(valid),
        "researcher_only_fields": dict(pending.get("researcher_only_fields") or {}),
        "agent_visible_field_names": sorted(set(before) | set(observed_absolute) | set(predicted)),
        "researcher_only": True,
        "agent_accessible": False,
        "material_specific_learner": False,
        "symbolic_material_sensor": False,
        "instrumental_use_established": False,
        "learning_established": False,
        "recipe_match": False,
    }
    return "emit", receipt


def surface_traction_prediction_catalog_item(*, enabled: bool) -> dict[str, Any]:
    return {
        "id": MECHANISM_ID,
        "enabled": bool(enabled),
        "note": (
            "researcher-only. not agent-accessible. "
            "Reads the existing sensorimotor consequence mean for MOVE. "
            "Not a material sensor and not a material learner."
        ),
    }
