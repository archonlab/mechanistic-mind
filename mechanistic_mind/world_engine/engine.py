from __future__ import annotations

from copy import deepcopy
from mechanistic_mind.body.physical_intake import (

    compute_transfer,
    intake_params_from_body_config,
    material_composition,
    object_uses_intake,
    remaining_capacity,
    apply_bounded_object_intake,
)
from dataclasses import dataclass
from typing import Any

from mechanistic_mind.agent import Action
from mechanistic_mind.core import DeterministicRandom

from .autonomous import (
    AUTONOMOUS_FORBIDDEN_KEYS,
    advance_autonomous_dynamics,
)
from .existence import (
    COGNITIVE_FORBIDDEN_KEYS,
    ExistenceMode,
    append_existence_event,
    choose_position,
    initial_existence_state,
    is_present,
    is_static,
    normalize_existence,
    sample_delay,
    sample_residence,
)
from .models import (
    ExogenousEventKind,
    ObjectiveObject,
    ObjectiveObstacle,
    Position,
    ScheduledExogenousEvent,
    WorldEngineConfig,
)
from .perception import agent_facing_returns, build_perception_packet, compute_emit_returns
from .physical_effector import maybe_apply
from .physical_coupling import maybe_write_drive
from .background_fields import (
    advance_background_fields,
    init_background_state,
    local_body_coupling,
    sample_local_fields,
    schema_terrain_multiplier,
)


@dataclass(frozen=True, slots=True)
class WorldActionResult:
    state: dict[str, Any]
    distance: float
    terrain_factor: float
    external_body_effects: dict[str, float]
    progress_delta: float
    action_receipt: dict[str, Any]
    carried_mass_kg: float = 0.0


class ObjectiveWorldEngine:
    """Objective environment dynamics.

    This layer owns geometry, objects, affordances, objective causal rules, and
    exogenous events. It has no psychological state.
    """

    def __init__(self, config: WorldEngineConfig) -> None:
        config.validate()
        self.config = config

    def initial_state(
        self,
        *,
        agent_id: str = "A001",
        start_position: Position = (4, 3),
        agent_positions: dict[str, Position] | None = None,
    ) -> dict[str, Any]:
        if agent_positions is None:
            positions = {agent_id: list(start_position)}
        else:
            if not agent_positions:
                raise ValueError("agent_positions must be non-empty")
            positions = {
                str(aid): list(pos)
                for aid, pos in sorted(agent_positions.items())
            }
        return {
            "tick": 0,
            "width": self.config.width,
            "height": self.config.height,
            "agent_positions": positions,
            "blocked": [list(item) for item in self.config.blocked],
            "terrain_factors": deepcopy(self.config.terrain_factors),
            "env_material_field": deepcopy(getattr(self.config, "env_material_field", {}) or {}),
            "background_fields": init_background_state(
                width=int(self.config.width),
                height=int(self.config.height),
                spec=getattr(self.config, "background_fields_spec", None),
                seed=int(getattr(self, "_init_seed", 17) or 17),
            ),
            "objects": {
                item.object_id: item.to_record()
                for item in self.config.objects
            },
            "obstacles": {
                item.obstacle_id: item.to_record()
                for item in self.config.obstacles
            },
            "obstacle_contact_counts": {},
            "total_progress": 0.0,
            "action_log": [],
            "action_counts": {},
            "movement_count": 0,
            "interaction_count": 0,
            "wait_count": 0,
            "exogenous_event_log": [],
            "delayed_effects": [],
            "random_event_count": 0,
            "carried_objects": {},
            "existence_clock": 0,
            "existence_events": [],
            "autonomous_events": [],
            "causal_provenance_tick": {},
        }

    def local_observation(
        self,
        state: dict[str, Any],
        *,
        agent_id: str,
    ) -> dict[str, Any]:
        position = self.position(state, agent_id)
        visible_objects: list[dict[str, Any]] = []
        for object_id, record in sorted(
            self._objects(state).items()
        ):
            if not isinstance(record, dict):
                continue
            if not is_present(record):
                continue
            object_position = self._position(record.get("position"))
            if object_position is None:
                continue
            if self._manhattan(position, object_position) <= self.config.vision_radius:
                visible_objects.append(
                    {
                        "id": str(object_id),
                        "position": list(object_position),
                        "relative_offset": [
                            object_position[0] - position[0],
                            object_position[1] - position[1],
                        ],
                        "affordance": str(
                            record.get("affordance") or "USE"
                        ),
                        "cue_signature": str(
                            record.get("cue_signature")
                            or "GENERIC_OBJECT"
                        ),
                        "cue_salience": float(
                            record.get("cue_salience", 0.5)
                        ),
                        "available_now": self.object_available(
                            state,
                            str(object_id),
                        ),
                        "movable": bool(record.get("movable", False)),
                        "carried_by": record.get("carried_by"),
                        "interaction_state": str(
                            record.get("interaction_state") or "FREE"
                        ),
                        "size": float(record.get("size", 0.35)),
                        "shape": str(record.get("shape") or "circle"),
                        "color": str(record.get("color") or "#d89b45"),
                        "opacity": float(record.get("opacity", 1.0)),
                        "brightness": float(record.get("brightness", 0.5)),
                        "signal": record.get("signal"),
                        "observable_state": {
                            str(key): float(
                                self.object_mutable_state(record).get(key, 0.0)
                            )
                            for key in record.get("observable_state_fields", [])
                            if key in self.object_mutable_state(record)
                        },
                    }
                )
        visible_objects = [
            {
                key: value
                for key, value in item.items()
                if key not in COGNITIVE_FORBIDDEN_KEYS
                and key not in AUTONOMOUS_FORBIDDEN_KEYS
            }
            for item in visible_objects
        ]

        visible_obstacles: list[dict[str, Any]] = []
        for obstacle_id, record in sorted(
            self._obstacles(state).items()
        ):
            if not isinstance(record, dict):
                continue
            if record.get("active", True) is False:
                continue
            obstacle_position = self._position(
                record.get("position")
            )
            if obstacle_position is None:
                continue
            if (
                self._manhattan(
                    position,
                    obstacle_position,
                )
                <= self.config.vision_radius
            ):
                visible_obstacles.append(
                    {
                        "id": str(obstacle_id),
                        "position": list(obstacle_position),
                        "relative_offset": [
                            obstacle_position[0] - position[0],
                            obstacle_position[1] - position[1],
                        ],
                        "cue_signature": str(
                            record.get("cue_signature")
                            or "GENERIC_OBSTACLE"
                        ),
                        "cue_salience": float(
                            record.get("cue_salience", 0.5)
                        ),
                        "traversable": bool(
                            record.get("traversable", True)
                        ),
                    }
                )

        visual_fragments = [
            {
                "kind": "OBJECT",
                "relative_position": deepcopy(item["relative_offset"]),
                "distance": abs(item["relative_offset"][0])
                + abs(item["relative_offset"][1]),
                "cue_signature": item["cue_signature"],
                "size": item["size"],
                "shape": item["shape"],
                "color": item["color"],
                "opacity": item["opacity"],
                "brightness": item["brightness"],
                "signal": item["signal"],
            }
            for item in visible_objects
        ]
        visual_fragments.extend(
            {
                "kind": "OBSTACLE",
                "relative_position": deepcopy(item["relative_offset"]),
                "distance": abs(item["relative_offset"][0])
                + abs(item["relative_offset"][1]),
                "cue_signature": item["cue_signature"],
                "traversable": item["traversable"],
            }
            for item in visible_obstacles
        )
        visual_fragments.sort(
            key=lambda item: (
                int(item["distance"]),
                str(item["kind"]),
                str(item["cue_signature"]),
                tuple(item["relative_position"]),
            )
        )
        occupied_cells: list[dict[str, Any]] = []
        positions = state.get("agent_positions", {})
        if isinstance(positions, dict):
            for other_id, raw in sorted(positions.items()):
                if str(other_id) == agent_id:
                    continue
                other_pos = self._position(raw)
                if other_pos is None:
                    continue
                if self._manhattan(position, other_pos) <= self.config.vision_radius:
                    # Anonymous occupancy only — no agent IDs or social tags.
                    occupied_cells.append(
                        {
                            "relative_offset": [
                                other_pos[0] - position[0],
                                other_pos[1] - position[1],
                            ],
                            "kind": "OCCUPANT",
                        }
                    )
                    visual_fragments.append(
                        {
                            "kind": "OCCUPANT",
                            "relative_position": [
                                other_pos[0] - position[0],
                                other_pos[1] - position[1],
                            ],
                            "distance": abs(other_pos[0] - position[0])
                            + abs(other_pos[1] - position[1]),
                        }
                    )

        action_log = state.get("action_log") or []
        last_receipt = action_log[-1] if action_log and isinstance(action_log[-1], dict) else None
        ambient_scalars = sample_local_fields(
            state,
            position=position if isinstance(position, tuple) else tuple(position),
        )

        physical_perception = build_perception_packet(
            agent_position=position, objects=self._objects(state),
            visual_fragments=visual_fragments, visible_objects=visible_objects,
            action_receipt=last_receipt, clock=int(state.get("tick", 0)),
            mode=self.config.perception_mode, ambient_scalars=ambient_scalars,
            pending_returns=state.get("pending_active_returns") or [],
            structural_radius=self.config.structural_radius,
        )
        return {
            "position": list(position),
            "vision_horizon": int(self.config.vision_radius),
            "visual_fragments": visual_fragments,
            "visible_objects": visible_objects,
            "visible_obstacles": visible_obstacles,
            "occupied_cells": occupied_cells,
            "physical_perception": physical_perception,
            "available_actions": tuple(
                self.available_actions(
                    state,
                    agent_id=agent_id,
                )
            ),
        }

    def available_actions(
        self,
        state: dict[str, Any],
        *,
        agent_id: str,
    ) -> list[str]:
        position = self.position(state, agent_id)
        actions: list[str] = []
        for dx, dy in (
            (0, -1),
            (-1, 0),
            (1, 0),
            (0, 1),
        ):
            destination = (
                position[0] + dx,
                position[1] + dy,
            )
            if self.is_open(
                state,
                destination,
                ignore_agent_id=agent_id,
            ):
                actions.append(
                    f"MOVE:{destination[0]},{destination[1]}"
                )

        for object_id, record in sorted(
            self._objects(state).items()
        ):
            if not isinstance(record, dict):
                continue
            if not is_present(record):
                continue
            if not self.object_available(
                state,
                str(object_id),
            ):
                continue
            object_position = self._position(
                record.get("position")
            )
            if object_position == position:
                actions.append(f"USE:{object_id}")
                if (
                    self.can_carry(record)
                    and record.get("carried_by") is None
                    and not self._carried_object_id(state, agent_id)
                ):
                    actions.append(f"TAKE:{object_id}")

            if (
                record.get("carried_by") is None
                and object_position is not None
                and self._manhattan(position, object_position) == 1
            ):
                dx = object_position[0] - position[0]
                dy = object_position[1] - position[1]
                destination = (
                    object_position[0] + dx,
                    object_position[1] + dy,
                )
                if self.can_push(record) and self.is_open(
                    state,
                    destination,
                    ignore_object_id=str(object_id),
                    ignore_agent_id=agent_id,
                ):
                    actions.append(
                        f"PUSH:{object_id}:{destination[0]},{destination[1]}"
                    )

        carried_id = self._carried_object_id(state, agent_id)
        if carried_id is not None:
            actions.append(f"RELEASE:{carried_id}")

        if self.config.emit_enabled:
            actions.append("EMIT")

        actions.append("WAIT")
        return actions

    def transition_action(
        self,
        state: dict[str, Any],
        *,
        agent_id: str,
        action: Action,
        rng: DeterministicRandom,
        body_context: dict[str, Any] | None = None,
        advance_dynamics: bool = True,
    ) -> WorldActionResult:
        next_state = deepcopy(state)
        if advance_dynamics:
            regeneration_updates = self.advance_object_states(next_state)
            existence_updates = self.advance_existence_dynamics(
                next_state,
                rng=rng,
            )
            autonomous_updates = advance_autonomous_dynamics(
                next_state,
                rng=rng,
                enabled=bool(self.config.autonomous_dynamics_enabled),
            )
            background_updates = advance_background_fields(
                next_state,
                rng_uniform=float(rng.random()),
            )
        else:
            regeneration_updates = []
            existence_updates = []
            autonomous_updates = []
            background_updates = []
        position_before = self.position(next_state, agent_id)
        available = set(
            self.available_actions(
                next_state,
                agent_id=agent_id,
            )
        )

        distance = 0.0
        terrain_factor = 1.0
        external_body_effects: dict[str, float] = {}
        progress_delta = 0.0
        receipt: dict[str, Any] = {
            "action": action.kind,
            "valid": action.kind in available,
            "position_before": list(position_before),
            "environmental_object_updates": regeneration_updates,
            "existence_update_kinds": [
                str(item.get("kind"))
                for item in existence_updates
                if isinstance(item, dict)
            ],
            "autonomous_update_kinds": [
                str(item.get("kind"))
                for item in autonomous_updates
                if isinstance(item, dict)
            ],
            "background_field_update_kinds": [
                str(item.get("kind"))
                for item in background_updates
                if isinstance(item, dict)
            ],
            "causal_provenance_tick": deepcopy(
                next_state.get("causal_provenance_tick") or {}
            ),
        }

        if action.kind not in available:
            receipt["valid"] = False
            receipt["rejection_reason"] = self._rejection_reason(
                next_state,
                agent_id=agent_id,
                action=action.kind,
            )
        elif action.kind.startswith("MOVE:"):
            destination = self._parse_move(action.kind)
            if destination is None:
                raise ValueError(
                    f"Malformed movement action: {action.kind}"
                )
            distance = float(
                self._manhattan(
                    position_before,
                    destination,
                )
            )
            terrain_factor = self.terrain_factor(
                next_state,
                destination,
            )
            obstacle = self.obstacle_at(
                next_state,
                destination,
            )
            if obstacle is not None:
                obstacle_id, obstacle_record = obstacle
                terrain_factor *= float(
                    obstacle_record.get(
                        "terrain_factor",
                        1.0,
                    )
                )
                receipt["obstacle_id"] = obstacle_id
                receipt["obstacle_contact"] = True
                probability = float(
                    obstacle_record.get(
                        "contact_probability",
                        1.0,
                    )
                )
                if rng.random() <= probability:
                    obstacle_effects = self._numeric_mapping(
                        obstacle_record.get(
                            "body_effects"
                        )
                    )
                    self._merge_numeric(
                        external_body_effects,
                        obstacle_effects,
                    )
                    receipt["obstacle_effect_applied"] = True
                    receipt["obstacle_effects"] = deepcopy(
                        obstacle_effects
                    )
                else:
                    receipt["obstacle_effect_applied"] = False

                counts = dict(
                    next_state.get(
                        "obstacle_contact_counts",
                        {},
                    )
                )
                counts[obstacle_id] = int(
                    counts.get(obstacle_id, 0)
                ) + 1
                next_state[
                    "obstacle_contact_counts"
                ] = counts

            next_state["agent_positions"][agent_id] = list(
                destination
            )
            carried_id = self._carried_object_id(next_state, agent_id)
            if carried_id is not None:
                carried = self._objects(next_state).get(carried_id)
                if isinstance(carried, dict):
                    carried["position"] = list(destination)
                    carried["interaction_state"] = "CARRIED"
                    carried["last_displacement"] = {
                        "kind": "CARRIED",
                        "from": list(position_before),
                        "to": list(destination),
                    }
            receipt["position_after"] = list(destination)
        elif action.kind.startswith("USE:"):
            object_id = action.kind.split(":", 1)[1]
            record = self._objects(next_state).get(
                object_id,
                {},
            )
            if isinstance(record, dict):
                object_state_before = self.object_mutable_state(record)
                interaction_physics = self._apply_interaction_physics(
                    record, rng=rng, tick=int(next_state.get("tick", 0))
                )
                effect_available = self._effect_available(record) and bool(
                    interaction_physics.get("consequence_exposed", True)
                )
                effect_scale = self._effect_scale(record)
                if (
                    rng.random() <= self.config.causal_reliability
                    and effect_available
                ):
                    candidate_body_effects = self._numeric_mapping(
                        record.get("body_effects")
                    )
                    for rule in record.get("contextual_body_effects", []):
                        if not isinstance(rule, dict):
                            continue
                        minimum = self._numeric_mapping(rule.get("minimum"))
                        maximum = self._numeric_mapping(rule.get("maximum"))
                        objective_context = body_context or {}
                        matches = all(
                            isinstance(objective_context.get(key), (int, float))
                            and not isinstance(objective_context.get(key), bool)
                            and float(objective_context[key]) >= threshold
                            for key, threshold in minimum.items()
                        ) and all(
                            isinstance(objective_context.get(key), (int, float))
                            and not isinstance(objective_context.get(key), bool)
                            and float(objective_context[key]) <= threshold
                            for key, threshold in maximum.items()
                        )
                        if matches:
                            self._merge_numeric(
                                candidate_body_effects,
                                self._numeric_mapping(rule.get("body_effects")),
                            )
                    candidate_body_effects = {
                        key: value * effect_scale
                        for key, value in candidate_body_effects.items()
                    }
                    world_effects = self._numeric_mapping(
                        record.get("world_effects")
                    )
                    candidate_progress = float(
                        world_effects.get(
                            "progress_delta",
                            0.0,
                        )
                    ) * effect_scale
                    intake_effects = self._try_physical_intake_use(
                        record=record,
                        body_context=body_context,
                        effect_scale=effect_scale,
                        receipt=receipt,
                    )
                    if intake_effects is not None:
                        external_body_effects = intake_effects
                        progress_delta = 0.0
                    elif self.config.outcome_delay_ticks > 0:
                        delayed = list(
                            next_state.get(
                                "delayed_effects",
                                [],
                            )
                        )
                        delayed.append(
                            {
                                "due_tick": int(
                                    next_state.get(
                                        "tick",
                                        0,
                                    )
                                )
                                + self.config.outcome_delay_ticks
                                + 1,
                                "agent_id": agent_id,
                                "source_action": action.kind,
                                "object_id": object_id,
                                "body_effects": deepcopy(
                                    candidate_body_effects
                                ),
                                "progress_delta": (
                                    candidate_progress
                                ),
                            }
                        )
                        next_state["delayed_effects"] = delayed[-64:]
                        receipt["delayed"] = True
                        receipt["delay_ticks"] = (
                            self.config.outcome_delay_ticks
                        )
                    else:
                        external_body_effects = (
                            candidate_body_effects
                        )
                        progress_delta = candidate_progress
                        receipt["delayed"] = False
                    receipt["causal_effect_applied"] = True
                else:
                    receipt["causal_effect_applied"] = False
                if receipt.get("intake_mode"):
                    # Quantity already reduced by accepted_transfer.
                    state_deltas = {
                        "quantity": float(
                            (receipt.get("intake") or {}).get("accepted", 0.0)
                        )
                        * -1.0
                    }
                else:
                    state_deltas = (
                        self._apply_interaction_state(record)
                        if effect_available
                        else {}
                    )
                receipt["object_id"] = object_id
                receipt["object_state_before"] = object_state_before
                receipt["object_state_after"] = self.object_mutable_state(record)
                receipt["object_state_deltas"] = state_deltas
                receipt["effect_available"] = effect_available
                receipt["effect_scale"] = effect_scale
                receipt["interaction_physics"] = interaction_physics
                receipt["agent_body_context_before"] = deepcopy(body_context or {})
                use_count = int(record.get("use_count", 0)) + 1
                record["use_count"] = use_count
                cooldown = int(record.get("cooldown_ticks", 0))
                if cooldown > 0:
                    record["available_after_tick"] = (
                        int(next_state.get("tick", 0))
                        + cooldown
                        + 1
                    )
                max_uses = record.get("max_uses")
                depleted = False
                if (
                    isinstance(max_uses, int)
                    and use_count >= max_uses
                ):
                    depleted = True
                if (
                    not depleted
                    and not self._effect_available(record)
                    and self._existence_depletes_when_unavailable(record)
                ):
                    depleted = True
                if depleted:
                    transition = self.begin_local_depletion(
                        next_state,
                        object_id=object_id,
                        rng=rng,
                        reason="DEPLETED",
                    )
                    if transition is not None:
                        receipt["existence_transition"] = {
                            "kind": transition.get("kind"),
                            "reason": transition.get("reason"),
                            "present": transition.get("present", False),
                        }
                receipt["use_count"] = use_count
                receipt["cooldown_ticks"] = cooldown
        elif action.kind.startswith("TAKE:"):
            object_id = action.kind.split(":", 1)[1]
            record = self._objects(next_state).get(object_id)
            if isinstance(record, dict):
                record["carried_by"] = agent_id
                record["interaction_state"] = "CARRIED"
                record["last_displacement"] = None
                carried = dict(next_state.get("carried_objects", {}))
                carried[agent_id] = object_id
                next_state["carried_objects"] = carried
                receipt["object_id"] = object_id
                receipt["position_after"] = list(position_before)
        elif action.kind.startswith("RELEASE:"):
            object_id = action.kind.split(":", 1)[1]
            record = self._objects(next_state).get(object_id)
            if isinstance(record, dict):
                record["carried_by"] = None
                record["position"] = list(position_before)
                record["interaction_state"] = "DROPPED"
                record["last_displacement"] = {
                    "kind": "DROPPED",
                    "from": list(position_before),
                    "to": list(position_before),
                }
                carried = dict(next_state.get("carried_objects", {}))
                carried.pop(agent_id, None)
                next_state["carried_objects"] = carried
                receipt["object_id"] = object_id
                receipt["position_after"] = list(position_before)
        elif action.kind.startswith("PUSH:"):
            parsed = self._parse_push(action.kind)
            if parsed is None:
                raise ValueError(f"Malformed push action: {action.kind}")
            object_id, destination = parsed
            record = self._objects(next_state).get(object_id)
            if isinstance(record, dict):
                object_before = self._position(record.get("position"))
                if object_before is None:
                    raise ValueError(f"Object has invalid position: {object_id}")
                record["position"] = list(destination)
                record["interaction_state"] = "PUSHED"
                record["last_displacement"] = {
                    "kind": "PUSHED",
                    "from": list(object_before),
                    "to": list(destination),
                }
                distance = 1.0
                resistance = self.push_resistance(record)
                terrain_factor = max(1.0, resistance)
                receipt.update({
                    "object_id": object_id,
                    "object_position_before": list(object_before),
                    "object_position_after": list(destination),
                    "position_after": list(position_before),
                    "push_resistance": resistance,
                })
                physics = record.get("interaction_physics")
                if isinstance(physics, dict) and physics.get("enabled") and physics.get("alternative_action_factor") is not None:
                    before_r = float(physics.get("resistance", 1.0))
                    factor = max(0.0, float(physics.get("alternative_action_factor", 1.0)))
                    physics["resistance"] = before_r * factor
                    receipt["alternative_interaction_physics"] = {
                        "resistance_before": before_r,
                        "resistance_after": physics["resistance"],
                        "physical_action": "PUSH",
                    }
        elif action.kind == "EMIT":
            returns = compute_emit_returns(
                agent_position=position_before, objects=self._objects(next_state),
                emit_strength=self.config.emit_strength, emit_radius=self.config.emit_radius,
            )
            next_state["pending_active_returns"] = agent_facing_returns(returns)
            receipt["emit"] = {
                "return_count": len(returns),
                "returns": agent_facing_returns(returns),
                "energy_cost": self.config.emit_energy_cost,
                "fatigue_cost": self.config.emit_fatigue_cost,
            }
            external_body_effects = {
                "energy_delta": -float(self.config.emit_energy_cost),
                "fatigue_delta": float(self.config.emit_fatigue_cost),
            }
        elif action.kind == "WAIT":
            pass

        next_state["total_progress"] = float(
            next_state.get("total_progress", 0.0)
        ) + progress_delta

        log = list(next_state.get("action_log", []))
        log.append(deepcopy(receipt))
        next_state["action_log"] = log[-64:]

        counts = dict(next_state.get("action_counts", {}))
        counts[action.kind] = int(counts.get(action.kind, 0)) + 1
        next_state["action_counts"] = counts
        if action.kind.startswith("MOVE:"):
            next_state["movement_count"] = int(
                next_state.get("movement_count", 0)
            ) + 1
        elif action.kind.startswith("USE:"):
            next_state["interaction_count"] = int(
                next_state.get("interaction_count", 0)
            ) + 1
        elif action.kind.startswith(("TAKE:", "RELEASE:", "PUSH:")):
            next_state["interaction_count"] = int(
                next_state.get("interaction_count", 0)
            ) + 1
        elif action.kind == "WAIT":
            next_state["wait_count"] = int(
                next_state.get("wait_count", 0)
            ) + 1

        coupling_effects = local_body_coupling(
            next_state,
            position=self.position(next_state, agent_id),
        )
        if coupling_effects:
            for k, v in coupling_effects.items():
                external_body_effects[k] = float(external_body_effects.get(k, 0.0)) + float(v)
            receipt["background_body_coupling"] = dict(coupling_effects)
        # Schema override: movement cost multiplier (researcher phase only).
        mult = schema_terrain_multiplier(next_state)
        if mult != 1.0 and distance:
            terrain_factor = float(terrain_factor) * mult
            receipt["schema_movement_cost_multiplier"] = mult
        # Update 4.59: experimental generic effector. Default config None = no-op.
        # Does not read preact / N / R / motor_distribution. Does not emit Action.kind.
        effector_cfg = None
        if isinstance(body_context, dict):
            effector_cfg = body_context.get("physical_effector_config")
        coupling_cfg = None
        if isinstance(body_context, dict):
            coupling_cfg = body_context.get("physical_coupling_config")
        if isinstance(coupling_cfg, dict) and coupling_cfg.get("enabled", True):
            maybe_write_drive(next_state, coupling_cfg)
        if isinstance(effector_cfg, dict) and effector_cfg.get("enabled", True):
            next_state, effector_extra = maybe_apply(
                self, next_state, agent_id, effector_cfg
            )
            distance = float(distance) + float(effector_extra.get("distance", 0.0))
            receipt["physical_effector"] = {
                "applied": True,
                "realized": effector_extra.get("realized"),
                "blocked": effector_extra.get("blocked"),
                "rule": effector_extra.get("rule"),
                "hop": list(effector_extra.get("hop") or (0, 0)),
            }
        return WorldActionResult(
            state=next_state,
            distance=distance,
            terrain_factor=terrain_factor,
            external_body_effects=external_body_effects,
            progress_delta=progress_delta,
            action_receipt=receipt,
            carried_mass_kg=self.carried_mass(next_state, agent_id),
        )

    def _carried_object_id(
        self,
        state: dict[str, Any],
        agent_id: str,
    ) -> str | None:
        carried = state.get("carried_objects", {})
        value = carried.get(agent_id) if isinstance(carried, dict) else None
        return str(value) if value is not None else None

    def carried_mass(self, state: dict[str, Any], agent_id: str) -> float:
        object_id = self._carried_object_id(state, agent_id)
        if object_id is None:
            return 0.0
        record = self._objects(state).get(object_id)
        if not isinstance(record, dict):
            return 0.0
        return max(0.0, float(record.get("mass_kg", 0.0)))

    def can_carry(self, record: dict[str, Any]) -> bool:
        """Derive carry feasibility from mobility, mass, and size."""
        return (
            bool(record.get("movable", False))
            and float(record.get("mobility", 1.0)) > 0.0
            and float(record.get("mass_kg", 0.0))
            <= self.config.agent_carry_capacity_kg
            and float(record.get("size", 0.35))
            <= self.config.agent_carry_size_capacity
        )

    @staticmethod
    def push_resistance(record: dict[str, Any]) -> float:
        mass = max(0.0, float(record.get("mass_kg", 0.0)))
        friction = max(0.0, float(record.get("friction", 0.25)))
        mobility = max(0.01, float(record.get("mobility", 1.0)))
        return mass * (0.25 + friction) / mobility

    def can_push(self, record: dict[str, Any]) -> bool:
        """Derive push feasibility from objective resistance."""
        return (
            bool(record.get("movable", False))
            and record.get("carried_by") is None
            and self.push_resistance(record) <= self.config.agent_push_capacity
        )

    @staticmethod
    def object_mutable_state(record: dict[str, Any]) -> dict[str, float]:
        nested = record.get("mutable_state")
        source = nested if isinstance(nested, dict) else record
        return {
            key: max(0.0, float(source.get(key, record.get(key, default))))
            for key, default in (("quantity", 1.0), ("durability", 1.0))
        }

    @staticmethod
    def _set_object_mutable_state(
        record: dict[str, Any], state: dict[str, float]
    ) -> None:
        normalized = {
            str(key): max(0.0, float(value)) for key, value in state.items()
        }
        record["mutable_state"] = normalized
        for key, value in normalized.items():
            record[key] = value

    def _effect_available(self, record: dict[str, Any]) -> bool:
        state = self.object_mutable_state(record)
        requirements = self._numeric_mapping(record.get("minimum_effect_state"))
        return all(
            state.get(key, 0.0) >= threshold
            for key, threshold in requirements.items()
        )


    def _try_physical_intake_use(
        self,
        *,
        record: dict[str, Any],
        body_context: dict[str, Any] | None,
        effect_scale: float,
        receipt: dict[str, Any],
    ) -> dict[str, float] | None:
        """Update 4.8: if intake enabled, convert USE into bounded transfer.

        Returns external_body_effects dict with intake_transfer, or None to
        keep legacy immediate body_effects path.

        Physical transfer is delegated to apply_bounded_object_intake (shared
        with optional contact eligibility). effect_scale is unused by the
        transfer equations (retained for call-site compatibility).
        """
        from mechanistic_mind.body.models import BodyConfig

        _ = effect_scale  # intake equations do not scale by effect_scale
        ctx = body_context or {}
        params = ctx.get("_intake_params")
        if params is None:
            params = intake_params_from_body_config(
                BodyConfig(
                    physical_intake_enabled=bool(ctx.get("physical_intake_enabled", False)),
                    intake_transfer_enabled=bool(ctx.get("intake_transfer_enabled", True)),
                    intake_processing_enabled=bool(ctx.get("intake_processing_enabled", True)),
                    intake_per_interaction_capacity=float(
                        ctx.get("intake_per_interaction_capacity", 0.03)
                    ),
                    intake_internal_capacity=float(
                        ctx.get("intake_internal_capacity", 0.20)
                    ),
                )
            )
        else:
            from mechanistic_mind.body.physical_intake import coerce_intake_params
            params = coerce_intake_params(params)
        result = apply_bounded_object_intake(
            record,
            params=params,
            internal_materials=ctx.get("internal_materials") or {},
        )
        if not result.get("applied"):
            return None
        tr = result.get("transfer") or {}
        intake_transfer = dict(result.get("intake_transfer") or {})
        accepted = float(result.get("accepted", 0.0) or 0.0)
        receipt["intake"] = {
            **tr,
            "composition": result.get("composition") or {},
            "intake_transfer": intake_transfer,
        }
        receipt["intake_mode"] = True
        receipt["delayed"] = False
        receipt["causal_effect_applied"] = accepted > 0.0
        receipt["intake_source_eligibility"] = "USE"
        return {"intake_transfer": intake_transfer} if accepted > 0.0 else {}


    def _effect_scale(self, record: dict[str, Any]) -> float:
        key = record.get("effect_scale_state")
        if key not in {"quantity", "durability"}:
            return 1.0
        deltas = self._numeric_mapping(record.get("interaction_state_deltas"))
        requested = max(0.0, -float(deltas.get(str(key), 0.0)))
        if requested <= 0.0:
            return 1.0
        available = self.object_mutable_state(record).get(str(key), 0.0)
        return max(0.0, min(1.0, available / requested))

    def _apply_interaction_state(
        self, record: dict[str, Any]
    ) -> dict[str, float]:
        before = self.object_mutable_state(record)
        after = dict(before)
        capacities = self._numeric_mapping(record.get("state_capacities"))
        configured = self._numeric_mapping(record.get("interaction_state_deltas"))
        applied: dict[str, float] = {}
        for key, delta in configured.items():
            if key not in after:
                continue
            upper = capacities.get(key, float("inf"))
            updated = max(0.0, min(upper, after[key] + delta))
            applied[key] = updated - after[key]
            after[key] = updated
        self._set_object_mutable_state(record, after)
        requirements = self._numeric_mapping(record.get("minimum_effect_state"))
        if (
            record.get("remove_when_exhausted", False)
            and requirements
            and not self._effect_available(record)
        ):
            record["active"] = False
        return applied

    def _apply_interaction_physics(
        self, record: dict[str, Any], *, rng: DeterministicRandom, tick: int
    ) -> dict[str, Any]:
        """Apply generic resistance and persistent partial transformation.

        Legacy objects have no configuration and retain one-contact behavior.
        Random-control variability is world physics and never enters valuation.
        """
        cfg = record.get("interaction_physics")
        if not isinstance(cfg, dict) or not cfg.get("enabled", False):
            return {"enabled": False, "consequence_exposed": True}
        resistance = max(1e-9, float(cfg.get("resistance", 1.0)))
        mode = str(cfg.get("mode", "STRUCTURED")).upper()
        if mode == "DYNAMIC":
            amplitude = float(cfg.get("resistance_amplitude", 0.0))
            period = max(1, int(cfg.get("resistance_period", 20)))
            resistance = max(1e-9, resistance + amplitude * ((tick % period) / period * 2.0 - 1.0))
        elif mode == "RANDOM_CONTROL":
            variability = max(0.0, float(cfg.get("variability", 0.0)))
            resistance = max(1e-9, resistance * (1.0 + variability * (2.0 * rng.random() - 1.0)))
        magnitude = max(0.0, float(cfg.get("interaction_magnitude", 1.0)))
        rate = max(0.0, float(cfg.get("transformation_rate", 1.0)))
        increment = magnitude * rate / resistance
        before = max(0.0, float(record.get("accumulated_deformation", 0.0)))
        ceiling = max(0.0, float(cfg.get("transformation_ceiling", 1.0)))
        after = min(ceiling, before + increment)
        threshold = max(0.0, float(cfg.get("interaction_threshold", 1.0)))
        record["accumulated_deformation"] = after
        exposed = after >= threshold
        return {
            "enabled": True, "mode": mode, "resistance": resistance,
            "interaction_magnitude": magnitude, "transformation_delta": after - before,
            "transformation_before": before, "transformation_after": after,
            "threshold": threshold, "consequence_exposed": exposed,
            "partial_transformation": after > 0.0 and not exposed,
            "ineffective": after - before <= 1e-12,
        }

    def advance_object_states(
        self, state: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Apply deterministic per-tick regeneration to live object state."""
        updates: list[dict[str, Any]] = []
        for object_id, record in sorted(self._objects(state).items()):
            if not isinstance(record, dict):
                continue
            if not is_present(record):
                continue
            physics = record.get("interaction_physics")
            if isinstance(physics, dict) and physics.get("enabled"):
                recovery = max(0.0, float(physics.get("transformation_recovery_rate", 0.0)))
                before_deformation = max(0.0, float(record.get("accumulated_deformation", 0.0)))
                after_deformation = max(0.0, before_deformation - recovery)
                if after_deformation != before_deformation:
                    record["accumulated_deformation"] = after_deformation
                    updates.append({"object_id": str(object_id), "field": "accumulated_deformation",
                                    "before": before_deformation, "after": after_deformation,
                                    "kind": "OBJECT_STATE_REGENERATION"})
            rates = self._numeric_mapping(record.get("regeneration_rates"))
            if not rates:
                continue
            before = self.object_mutable_state(record)
            after = dict(before)
            capacities = self._numeric_mapping(record.get("state_capacities"))
            for key, rate in rates.items():
                if key not in after or rate <= 0.0:
                    continue
                after[key] = min(
                    capacities.get(key, after[key]),
                    after[key] + rate,
                )
            if after != before:
                self._set_object_mutable_state(record, after)
                updates.append(
                    {
                        "object_id": str(object_id),
                        "kind": "OBJECT_STATE_REGENERATION",
                        "before": before,
                        "after": after,
                    }
                )
        return updates

    def advance_existence_dynamics(
        self,
        state: dict[str, Any],
        *,
        rng: DeterministicRandom,
    ) -> list[dict[str, Any]]:
        clock = int(state.get("existence_clock", state.get("tick", 0))) + 1
        state["existence_clock"] = clock
        updates: list[dict[str, Any]] = []
        for object_id, record in sorted(self._objects(state).items()):
            if not isinstance(record, dict) or is_static(record):
                continue
            existence = self._ensure_existence(record)
            if existence.get("present", True) is False:
                scheduled = existence.get("scheduled_reappear_tick")
                if scheduled is None or int(scheduled) > clock:
                    continue
                event = self._reappear_object(
                    state, object_id=str(object_id), rng=rng, clock=clock
                )
                if event is not None:
                    updates.append(event)
                continue
            config = existence.get("config") or {}
            if (
                existence.get("residence_until_clock") is None
                and config.get("residence_ticks")
            ):
                residence = sample_residence(config, rng)
                existence["present_since_clock"] = clock
                existence["residence_until_clock"] = (
                    None if residence is None else clock + residence
                )
            if self._residence_elapsed(existence, clock):
                event = self.begin_local_depletion(
                    state,
                    object_id=str(object_id),
                    rng=rng,
                    reason="RESIDENCE_ELAPSED",
                )
                if event is not None:
                    updates.append(event)
        return updates

    def begin_local_depletion(
        self,
        state: dict[str, Any],
        *,
        object_id: str,
        rng: DeterministicRandom,
        reason: str,
    ) -> dict[str, Any] | None:
        record = self._objects(state).get(object_id)
        if not isinstance(record, dict):
            return None
        existence = self._ensure_existence(record)
        depleted_event = {
            "kind": "OBJECT_DEPLETED",
            "tick": int(state.get("existence_clock", state.get("tick", 0))),
            "object_id": object_id,
            "existence_mode": existence.get("mode"),
            "reason": reason,
            "region_id": existence.get("region_id"),
            "position": deepcopy(record.get("position")),
        }
        append_existence_event(state, depleted_event)
        if is_static(record):
            record["active"] = False
            existence["present"] = False
            existence["last_event"] = "OBJECT_DEPLETED"
            return depleted_event
        return self._begin_relocation(
            state, object_id=object_id, rng=rng, reason=reason
        )

    def _begin_relocation(
        self,
        state: dict[str, Any],
        *,
        object_id: str,
        rng: DeterministicRandom,
        reason: str,
    ) -> dict[str, Any]:
        record = self._objects(state)[object_id]
        existence = self._ensure_existence(record)
        config = existence.get("config") or normalize_existence(None)
        previous_region = existence.get("region_id")
        previous_position = deepcopy(record.get("position"))
        next_plan = self._plan_next_appearance(
            state, object_id=object_id, rng=rng
        )
        clock = int(state.get("existence_clock", state.get("tick", 0)))
        delay = sample_delay(config, rng)
        carried = dict(state.get("carried_objects", {}))
        carrier = record.get("carried_by")
        if carrier is not None and isinstance(carried, dict):
            carried.pop(str(carrier), None)
            state["carried_objects"] = carried
        record["carried_by"] = None
        record["active"] = False
        record["existence_last_position"] = previous_position
        record["position"] = None
        record["interaction_state"] = "ABSENT"
        existence["present"] = False
        existence["scheduled_reappear_tick"] = (
            None if next_plan is None else clock + max(0, delay)
        )
        if next_plan is None:
            existence["hidden_next_position"] = None
            existence["hidden_next_region_index"] = None
            existence["hidden_next_region_id"] = None
            existence["route_complete"] = True
        else:
            existence["hidden_next_position"] = list(next_plan["position"])
            existence["hidden_next_region_index"] = next_plan["region_index"]
            existence["hidden_next_region_id"] = next_plan["region_id"]
        existence["last_event"] = "OBJECT_DISAPPEARED"
        event = {
            "kind": "OBJECT_DISAPPEARED",
            "tick": clock,
            "object_id": object_id,
            "existence_mode": existence.get("mode"),
            "reason": reason,
            "previous_region": previous_region,
            "previous_position": previous_position,
            "new_region": existence.get("hidden_next_region_id"),
            "transition_delay_ticks": delay,
            "scheduled_reappear_tick": existence.get("scheduled_reappear_tick"),
            "present": False,
        }
        append_existence_event(state, event)
        if delay == 0 and existence.get("scheduled_reappear_tick") is not None:
            reappeared = self._reappear_object(
                state, object_id=object_id, rng=rng, clock=clock
            )
            if reappeared is not None:
                event["immediate_reappearance"] = reappeared
        return event

    def _reappear_object(
        self,
        state: dict[str, Any],
        *,
        object_id: str,
        rng: DeterministicRandom,
        clock: int,
    ) -> dict[str, Any] | None:
        record = self._objects(state).get(object_id)
        if not isinstance(record, dict):
            return None
        existence = self._ensure_existence(record)
        config = existence.get("config") or normalize_existence(None)
        planned = existence.get("hidden_next_position")
        position = self._position(planned)
        if position is None:
            plan = self._plan_next_appearance(
                state, object_id=object_id, rng=rng
            )
            if plan is None:
                return None
            position = plan["position"]
            existence["hidden_next_region_index"] = plan["region_index"]
            existence["hidden_next_region_id"] = plan["region_id"]
        if not self._existence_cell_legal(state, position, object_id=object_id):
            fallback = self._plan_next_appearance(
                state, object_id=object_id, rng=rng
            )
            if fallback is None:
                existence["scheduled_reappear_tick"] = clock + 1
                return {
                    "kind": "OBJECT_REAPPEARANCE_DEFERRED",
                    "tick": clock,
                    "object_id": object_id,
                    "reason": "NO_VALID_SPAWN",
                }
            position = fallback["position"]
            existence["hidden_next_region_index"] = fallback["region_index"]
            existence["hidden_next_region_id"] = fallback["region_id"]
        previous_region = existence.get("region_id")
        record["position"] = list(position)
        record["active"] = True
        record["interaction_state"] = "FREE"
        record["carried_by"] = None
        existence["present"] = True
        existence["region_index"] = existence.get("hidden_next_region_index")
        existence["region_id"] = existence.get("hidden_next_region_id")
        existence["scheduled_reappear_tick"] = None
        existence["hidden_next_position"] = None
        existence["appearance_count"] = int(existence.get("appearance_count", 0)) + 1
        existence["present_since_clock"] = clock
        residence = sample_residence(config, rng)
        existence["residence_until_clock"] = (
            None if residence is None else clock + residence
        )
        existence["last_event"] = "OBJECT_REAPPEARED"
        if config.get("reset_availability_on_appearance", True):
            record["use_count"] = 0
            record["available_after_tick"] = 0
            capacities = self._numeric_mapping(record.get("state_capacities"))
            restored = {
                key: float(capacities.get(key, value))
                for key, value in self.object_mutable_state(record).items()
            }
            self._set_object_mutable_state(record, restored)
        event = {
            "kind": "OBJECT_REAPPEARED",
            "tick": clock,
            "object_id": object_id,
            "existence_mode": existence.get("mode"),
            "previous_region": previous_region,
            "new_region": existence.get("region_id"),
            "position": list(position),
            "present": True,
            "reason": "SCHEDULED_REAPPEARANCE",
        }
        relocated = {
            "kind": "OBJECT_RELOCATED",
            "tick": clock,
            "object_id": object_id,
            "existence_mode": existence.get("mode"),
            "previous_region": previous_region,
            "new_region": existence.get("region_id"),
            "position": list(position),
            "present": True,
            "reason": "SCHEDULED_REAPPEARANCE",
        }
        append_existence_event(state, relocated)
        append_existence_event(state, event)
        return event

    def _plan_next_appearance(
        self,
        state: dict[str, Any],
        *,
        object_id: str,
        rng: DeterministicRandom,
    ) -> dict[str, Any] | None:
        record = self._objects(state)[object_id]
        existence = self._ensure_existence(record)
        config = existence.get("config") or normalize_existence(None)
        mode = str(existence.get("mode") or ExistenceMode.STATIC.value)
        randomize = bool(config.get("randomize_position_within_region", True))
        if mode == ExistenceMode.RELOCATING_ROUTE.value:
            route = list(config.get("route") or [])
            if not route:
                return None
            current_index = int(existence.get("region_index") or 0)
            next_index = current_index + 1
            if next_index >= len(route):
                if not bool(config.get("cycle", True)):
                    return None
                next_index = 0
            region = route[next_index]
            cells = [
                pos
                for pos in (self._position(cell) for cell in region.get("cells", []))
                if pos is not None
            ]
            chosen = choose_position(
                cells=cells,
                randomize=randomize,
                rng=rng,
                open_fn=lambda cell, oid: self._existence_cell_legal(
                    state, cell, object_id=oid
                ),
                object_id=object_id,
            )
            if chosen is None:
                return None
            return {
                "position": chosen,
                "region_index": next_index,
                "region_id": str(region.get("region_id") or f"R{next_index}"),
            }
        if mode == ExistenceMode.RELOCATING_RANDOM.value:
            regions = list(config.get("allowed_regions") or [])
            cells: list[Position] = []
            for region in regions:
                for raw in region.get("cells", []):
                    position = self._position(raw)
                    if position is not None:
                        cells.append(position)
            if not cells:
                cells = [
                    (x, y)
                    for x in range(self.config.width)
                    for y in range(self.config.height)
                    if self._existence_cell_legal(state, (x, y), object_id=object_id)
                ]
            chosen = choose_position(
                cells=cells,
                randomize=True,
                rng=rng,
                open_fn=lambda cell, oid: self._existence_cell_legal(
                    state, cell, object_id=oid
                ),
                object_id=object_id,
            )
            if chosen is None:
                return None
            return {"position": chosen, "region_index": 0, "region_id": "RANDOM"}
        return None

    def _existence_cell_legal(
        self,
        state: dict[str, Any],
        position: Position,
        *,
        object_id: str,
    ) -> bool:
        x, y = position
        if not (0 <= x < self.config.width and 0 <= y < self.config.height):
            return False
        blocked = {
            tuple(item)
            for item in state.get("blocked", [])
            if isinstance(item, list) and len(item) == 2
        }
        if position in blocked:
            return False
        obstacle = self.obstacle_at(state, position)
        if obstacle is not None:
            _obstacle_id, record = obstacle
            if record.get("active", True) and not bool(record.get("traversable", True)):
                return False
        return True

    def _ensure_existence(self, record: dict[str, Any]) -> dict[str, Any]:
        existence = record.get("existence")
        if isinstance(existence, dict) and "config" in existence:
            return existence
        position = self._position(record.get("position")) or (0, 0)
        initialized = initial_existence_state(
            normalize_existence(existence if isinstance(existence, dict) else None),
            position=position,
        )
        record["existence"] = initialized
        return initialized

    def _residence_elapsed(self, existence: dict[str, Any], clock: int) -> bool:
        until = existence.get("residence_until_clock")
        if until is None:
            config = existence.get("config") or {}
            if not config.get("residence_ticks"):
                return False
            trigger = (config.get("trigger") or {}).get("type")
            if trigger != "RESIDENCE_ELAPSED":
                return False
            present_since = int(existence.get("present_since_clock") or 0)
            low, _high = config.get("residence_ticks") or [0, 0]
            return clock - present_since >= int(low)
        return clock >= int(until)

    def _existence_depletes_when_unavailable(self, record: dict[str, Any]) -> bool:
        existence = record.get("existence")
        if not isinstance(existence, dict):
            return False
        config = existence.get("config") or {}
        return bool(config.get("deplete_when_effect_unavailable", False))

    def directional_exposure(
        self,
        state: dict[str, Any],
        *,
        position: Position,
        source_direction: Position = (1, 0),
        reach: int = 3,
    ) -> dict[str, Any]:
        """Return attenuation from ordinary object geometry.

        ``source_direction`` points from a cell toward the source. Objects on
        that ray independently attenuate the local scalar exposure. The method
        contains no semantic category for what the configuration represents.
        """
        dx, dy = source_direction
        if (dx, dy) == (0, 0) or abs(dx) + abs(dy) != 1:
            raise ValueError("source_direction must be one cardinal unit vector")
        factors: list[dict[str, Any]] = []
        multiplier = 1.0
        for distance in range(1, max(0, int(reach)) + 1):
            sample = (position[0] + dx * distance, position[1] + dy * distance)
            for object_id, record in sorted(self._objects(state).items()):
                if not isinstance(record, dict) or record.get("active", True) is False:
                    continue
                if self._position(record.get("position")) != sample:
                    continue
                attenuation = max(
                    0.0,
                    min(1.0, float(record.get("directional_attenuation", 0.0))),
                )
                if attenuation <= 0.0:
                    continue
                multiplier *= 1.0 - attenuation
                factors.append(
                    {
                        "object_id": str(object_id),
                        "position": list(sample),
                        "attenuation": attenuation,
                    }
                )
        return {
            "exposure_multiplier": multiplier,
            "attenuating_objects": factors,
        }


    def release_delayed_effects(
        self,
        state: dict[str, Any],
        *,
        effective_tick: int,
    ) -> tuple[
        dict[str, Any],
        dict[str, float],
        float,
        list[dict[str, Any]],
    ]:
        next_state = deepcopy(state)
        queue = list(
            next_state.get(
                "delayed_effects",
                [],
            )
        )
        remaining = []
        body_effects: dict[str, float] = {}
        progress_delta = 0.0
        receipts: list[dict[str, Any]] = []

        for row in queue:
            if not isinstance(row, dict):
                continue
            if int(row.get("due_tick", -1)) != effective_tick:
                remaining.append(row)
                continue
            self._merge_numeric(
                body_effects,
                self._numeric_mapping(
                    row.get("body_effects")
                ),
            )
            progress_delta += float(
                row.get(
                    "progress_delta",
                    0.0,
                )
            )
            receipts.append(
                {
                    "kind": "DELAYED_ENDOGENOUS_EFFECT",
                    "effective_tick": effective_tick,
                    "agent_id": row.get("agent_id"),
                    "source_action": row.get(
                        "source_action"
                    ),
                    "object_id": row.get(
                        "object_id"
                    ),
                    "body_effects": deepcopy(
                        row.get(
                            "body_effects",
                            {},
                        )
                    ),
                    "progress_delta": float(
                        row.get(
                            "progress_delta",
                            0.0,
                        )
                    ),
                }
            )

        next_state["delayed_effects"] = remaining[-64:]
        if progress_delta:
            next_state["total_progress"] = float(
                next_state.get(
                    "total_progress",
                    0.0,
                )
            ) + progress_delta
        return (
            next_state,
            body_effects,
            progress_delta,
            receipts,
        )

    def apply_exogenous_events(
        self,
        state: dict[str, Any],
        *,
        effective_tick: int,
        agent_id: str,
        rng: DeterministicRandom,
    ) -> tuple[dict[str, Any], dict[str, float], list[dict[str, Any]]]:
        next_state = deepcopy(state)
        body_effects: dict[str, float] = {}
        receipts: list[dict[str, Any]] = []

        scheduled = [
            item
            for item in self.config.exogenous_events
            if item.effective_tick == effective_tick
        ]
        for event in scheduled:
            receipt, effects = self._apply_event(
                next_state,
                event,
                agent_id=agent_id,
                rng=rng,
            )
            receipts.append(receipt)
            self._merge_numeric(body_effects, effects)

        if (
            self.config.random_event_rate > 0.0
            and self.config.random_event_kinds
            and rng.random() < self.config.random_event_rate
        ):
            index = min(
                len(self.config.random_event_kinds) - 1,
                int(
                    rng.random()
                    * len(self.config.random_event_kinds)
                ),
            )
            kind = self.config.random_event_kinds[index]
            event = self._generate_random_event(
                next_state,
                kind=kind,
                effective_tick=effective_tick,
                rng=rng,
            )
            if event is not None:
                receipt, effects = self._apply_event(
                    next_state,
                    event,
                    agent_id=agent_id,
                    rng=rng,
                )
                receipt["generated_randomly"] = True
                receipts.append(receipt)
                self._merge_numeric(
                    body_effects,
                    effects,
                )
                next_state["random_event_count"] = int(
                    next_state.get(
                        "random_event_count",
                        0,
                    )
                ) + 1

        if receipts:
            log = list(
                next_state.get(
                    "exogenous_event_log",
                    [],
                )
            )
            log.extend(deepcopy(receipts))
            next_state["exogenous_event_log"] = log[-64:]

        return next_state, body_effects, receipts

    def _apply_event(
        self,
        state: dict[str, Any],
        event: ScheduledExogenousEvent,
        *,
        agent_id: str,
        rng: DeterministicRandom,
    ) -> tuple[dict[str, Any], dict[str, float]]:
        params = event.parameters
        before = self._event_snapshot(state, event)
        body_effects: dict[str, float] = {}

        if event.kind is ExogenousEventKind.RELOCATE_OBJECT:
            object_id = self._require_object(state, params)
            destination = self._require_position(
                params.get("position")
            )
            if not self.is_open(
                state,
                destination,
                ignore_object_id=object_id,
            ):
                raise ValueError(
                    f"Exogenous relocation target blocked: {destination}"
                )
            self._objects(state)[object_id][
                "position"
            ] = list(destination)

        elif event.kind is ExogenousEventKind.SET_OBJECT_ACTIVE:
            object_id = self._require_object(
                state,
                params,
            )
            active = params.get("active")
            if not isinstance(active, bool):
                raise ValueError(
                    "SET_OBJECT_ACTIVE requires bool active"
                )
            self._objects(state)[object_id][
                "active"
            ] = active

        elif event.kind is ExogenousEventKind.SPAWN_OBJECT:
            payload = params.get("object")
            if not isinstance(payload, dict):
                raise ValueError(
                    "SPAWN_OBJECT requires object mapping"
                )
            object_id = str(
                payload.get("id") or ""
            ).strip()
            if not object_id:
                raise ValueError(
                    "Spawned object requires id"
                )
            if object_id in self._objects(state):
                raise ValueError(
                    f"Object already exists: {object_id}"
                )
            position = self._require_position(
                payload.get("position")
            )
            if not self.is_open(state, position):
                raise ValueError(f"Spawn target blocked: {position}")
            movable = bool(payload.get("movable", False))
            size = float(payload.get("size", 0.35))
            quantity = float(payload.get("quantity", 1.0))
            durability = float(payload.get("durability", 1.0))
            max_quantity = float(payload.get("max_quantity", quantity))
            max_durability = float(payload.get("max_durability", durability))
            self._objects(state)[object_id] = {
                "id": object_id,
                "position": list(position),
                "affordance": str(
                    payload.get("affordance") or "USE"
                ),
                "hidden_role": str(
                    payload.get("hidden_role") or "UNSPECIFIED"
                ),
                "active": bool(
                    payload.get("active", True)
                ),
                "cue_signature": str(
                    payload.get("cue_signature")
                    or "GENERIC_OBJECT"
                ),
                "cue_salience": float(
                    payload.get("cue_salience", 0.5)
                ),
                "cooldown_ticks": int(
                    payload.get("cooldown_ticks", 0)
                ),
                "max_uses": (
                    int(payload["max_uses"])
                    if payload.get("max_uses") is not None
                    else None
                ),
                "use_count": 0,
                "available_after_tick": 0,
                "body_effects": self._numeric_mapping(
                    payload.get("body_effects")
                ),
                "world_effects": self._numeric_mapping(
                    payload.get("world_effects")
                ),
                "contextual_body_effects": deepcopy(
                    payload.get("contextual_body_effects", [])
                ),
                "movable": movable,
                "mass_kg": float(payload.get("mass_kg", 0.0)),
                "directional_attenuation": float(
                    payload.get("directional_attenuation", 0.0)
                ),
                "size": size,
                "shape": str(payload.get("shape") or "circle"),
                "color": str(payload.get("color") or "#d89b45"),
                "opacity": float(payload.get("opacity", 1.0)),
                "friction": float(payload.get("friction", 0.25)),
                "hardness": float(payload.get("hardness", 0.5)),
                "quantity": quantity,
                "max_quantity": max_quantity,
                "durability": durability,
                "max_durability": max_durability,
                "mutable_state": {
                    "quantity": quantity,
                    "durability": durability,
                },
                "state_capacities": {
                    "quantity": max_quantity,
                    "durability": max_durability,
                },
                "interaction_state_deltas": self._numeric_mapping(
                    payload.get("interaction_state_deltas")
                ),
                "regeneration_rates": self._numeric_mapping(
                    payload.get("regeneration_rates")
                ),
                "minimum_effect_state": self._numeric_mapping(
                    payload.get("minimum_effect_state")
                ),
                "effect_scale_state": payload.get("effect_scale_state"),
                "observable_state_fields": list(
                    payload.get("observable_state_fields", [])
                ),
                "remove_when_exhausted": bool(
                    payload.get("remove_when_exhausted", False)
                ),
                "mobility": float(
                    payload.get("mobility", 1.0 if movable else 0.0)
                ),
                "blocks_movement": bool(
                    payload.get("blocks_movement", size >= 0.9)
                ),
                "brightness": float(payload.get("brightness", 0.5)),
                "signal": payload.get("signal"),
                "carried_by": None,
                "interaction_state": "FREE",
                "last_displacement": None,
            }

        elif event.kind is ExogenousEventKind.SET_OBSTACLE_ACTIVE:
            obstacle_id = self._require_obstacle(
                state,
                params,
            )
            active = params.get("active")
            if not isinstance(active, bool):
                raise ValueError(
                    "SET_OBSTACLE_ACTIVE requires bool active"
                )
            self._obstacles(state)[obstacle_id][
                "active"
            ] = active

        elif event.kind is ExogenousEventKind.DAMAGE_ORGANISM:
            body_effects["damage_delta"] = float(
                params.get("damage_delta", 0.1)
            )

        elif event.kind is ExogenousEventKind.SET_TERRAIN_FACTOR:
            position = self._require_position(
                params.get("position")
            )
            factor = float(
                params.get("factor", 1.0)
            )
            terrain = dict(
                state.get("terrain_factors", {})
            )
            terrain[
                f"{position[0]},{position[1]}"
            ] = factor
            state["terrain_factors"] = terrain

        else:
            raise ValueError(
                f"Unsupported exogenous event kind: {event.kind}"
            )

        after = self._event_snapshot(state, event)
        return (
            {
                "event_id": event.event_id,
                "kind": event.kind.value,
                "effective_tick": event.effective_tick,
                "parameters": deepcopy(params),
                "before": before,
                "after": after,
            },
            body_effects,
        )

    def _generate_random_event(
        self,
        state: dict[str, Any],
        *,
        kind: ExogenousEventKind,
        effective_tick: int,
        rng: DeterministicRandom,
    ) -> ScheduledExogenousEvent | None:
        if kind is ExogenousEventKind.RELOCATE_OBJECT:
            active = [
                (object_id, record)
                for object_id, record in sorted(
                    self._objects(state).items()
                )
                if isinstance(record, dict)
                and record.get("active", True)
            ]
            if not active:
                return None
            object_index = min(
                len(active) - 1,
                int(rng.random() * len(active)),
            )
            object_id, _record = active[object_index]
            open_positions = [
                (x, y)
                for y in range(self.config.height)
                for x in range(self.config.width)
                if self.is_open(state, (x, y))
            ]
            if not open_positions:
                return None
            pos_index = min(
                len(open_positions) - 1,
                int(
                    rng.random()
                    * len(open_positions)
                ),
            )
            return ScheduledExogenousEvent(
                event_id=(
                    f"RANDOM-RELOCATE-{effective_tick}-"
                    f"{object_id}"
                ),
                effective_tick=effective_tick,
                kind=kind,
                parameters={
                    "object_id": object_id,
                    "position": list(
                        open_positions[pos_index]
                    ),
                },
            )

        return None

    def position(
        self,
        state: dict[str, Any],
        agent_id: str,
    ) -> Position:
        positions = state.get(
            "agent_positions",
            {},
        )
        raw = (
            positions.get(agent_id)
            if isinstance(positions, dict)
            else None
        )
        position = self._position(raw)
        if position is None:
            raise ValueError(
                f"World has no valid position for {agent_id}"
            )
        return position

    def is_open(
        self,
        state: dict[str, Any],
        position: Position,
        *,
        ignore_object_id: str | None = None,
        ignore_agent_id: str | None = None,
    ) -> bool:
        x, y = position
        if not (
            0 <= x < self.config.width
            and 0 <= y < self.config.height
        ):
            return False
        blocked = {
            tuple(item)
            for item in state.get("blocked", [])
            if isinstance(item, list)
            and len(item) == 2
        }
        if position in blocked:
            return False

        obstacle = self.obstacle_at(
            state,
            position,
        )
        if obstacle is not None:
            _obstacle_id, record = obstacle
            if record.get("active", True) and not bool(
                record.get("traversable", True)
            ):
                return False

        for object_id, record in sorted(self._objects(state).items()):
            if str(object_id) == ignore_object_id:
                continue
            if not isinstance(record, dict) or not is_present(record):
                continue
            if record.get("carried_by") is not None:
                continue
            if not bool(record.get("blocks_movement", False)):
                continue
            if self._position(record.get("position")) == position:
                return False

        positions = state.get("agent_positions", {})
        if isinstance(positions, dict):
            for other_id, raw in positions.items():
                if str(other_id) == ignore_agent_id:
                    continue
                if self._position(raw) == position:
                    return False
        return True

    def terrain_factor(
        self,
        state: dict[str, Any],
        position: Position,
    ) -> float:
        terrain = state.get(
            "terrain_factors",
            {},
        )
        if not isinstance(terrain, dict):
            return 1.0
        return float(
            terrain.get(
                f"{position[0]},{position[1]}",
                1.0,
            )
        )

    def _event_snapshot(
        self,
        state: dict[str, Any],
        event: ScheduledExogenousEvent,
    ) -> dict[str, Any]:
        if event.kind in {
            ExogenousEventKind.RELOCATE_OBJECT,
            ExogenousEventKind.SET_OBJECT_ACTIVE,
        }:
            object_id = str(
                event.parameters.get("object_id")
                or ""
            )
            return {
                "object_id": object_id,
                "record": deepcopy(
                    self._objects(state).get(
                        object_id,
                        {},
                    )
                ),
            }
        if event.kind is ExogenousEventKind.SET_OBSTACLE_ACTIVE:
            obstacle_id = str(
                event.parameters.get("obstacle_id")
                or ""
            )
            return {
                "obstacle_id": obstacle_id,
                "record": deepcopy(
                    self._obstacles(state).get(
                        obstacle_id,
                        {},
                    )
                ),
            }
        if event.kind is ExogenousEventKind.SET_TERRAIN_FACTOR:
            position = self._position(
                event.parameters.get("position")
            )
            key = (
                f"{position[0]},{position[1]}"
                if position is not None
                else ""
            )
            return {
                "position": list(position)
                if position is not None
                else None,
                "factor": deepcopy(
                    state.get(
                        "terrain_factors",
                        {},
                    ).get(key)
                    if isinstance(
                        state.get(
                            "terrain_factors",
                            {},
                        ),
                        dict,
                    )
                    else None
                ),
            }
        if event.kind is ExogenousEventKind.DAMAGE_ORGANISM:
            return {"body_truth_not_owned_by_world_engine": True}
        return deepcopy(state)

    def _require_object(
        self,
        state: dict[str, Any],
        parameters: dict[str, Any],
    ) -> str:
        object_id = str(
            parameters.get("object_id") or ""
        ).strip()
        if not object_id:
            raise ValueError("object_id is required")
        if object_id not in self._objects(state):
            raise ValueError(
                f"Unknown object_id: {object_id}"
            )
        return object_id

    def object_available(
        self,
        state: dict[str, Any],
        object_id: str,
    ) -> bool:
        record = self._objects(state).get(object_id)
        if not isinstance(record, dict):
            return False
        if not is_present(record):
            return False
        max_uses = record.get("max_uses")
        if (
            isinstance(max_uses, int)
            and int(record.get("use_count", 0)) >= max_uses
        ):
            return False
        return int(state.get("tick", 0)) >= int(
            record.get("available_after_tick", 0)
        )

    def _require_obstacle(
        self,
        state: dict[str, Any],
        parameters: dict[str, Any],
    ) -> str:
        obstacle_id = str(
            parameters.get("obstacle_id") or ""
        ).strip()
        if not obstacle_id:
            raise ValueError("obstacle_id is required")
        if obstacle_id not in self._obstacles(state):
            raise ValueError(
                f"Unknown obstacle_id: {obstacle_id}"
            )
        return obstacle_id

    def obstacle_at(
        self,
        state: dict[str, Any],
        position: Position,
    ) -> tuple[str, dict[str, Any]] | None:
        for obstacle_id, record in sorted(
            self._obstacles(state).items()
        ):
            if not isinstance(record, dict):
                continue
            if record.get("active", True) is False:
                continue
            obstacle_position = self._position(
                record.get("position")
            )
            if obstacle_position == position:
                return str(obstacle_id), record
        return None

    @staticmethod
    def _require_position(
        value: Any,
    ) -> Position:
        position = ObjectiveWorldEngine._position(
            value
        )
        if position is None:
            raise ValueError(
                "position must be [x, y] integers"
            )
        return position

    @staticmethod
    def _position(
        value: Any,
    ) -> Position | None:
        if (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and all(
                isinstance(item, int)
                for item in value
            )
        ):
            return (
                int(value[0]),
                int(value[1]),
            )
        return None

    @staticmethod
    def _parse_move(
        action: str,
    ) -> Position | None:
        try:
            payload = action.split(":", 1)[1]
            x_text, y_text = payload.split(
                ",",
                1,
            )
            return int(x_text), int(y_text)
        except Exception:
            return None

    @staticmethod
    def _parse_push(action: str) -> tuple[str, Position] | None:
        try:
            _prefix, object_id, coordinate = action.split(":", 2)
            x_text, y_text = coordinate.split(",", 1)
            if not object_id:
                return None
            return object_id, (int(x_text), int(y_text))
        except Exception:
            return None

    def _rejection_reason(
        self,
        state: dict[str, Any],
        *,
        agent_id: str,
        action: str,
    ) -> str:
        if action.startswith("TAKE:"):
            object_id = action.split(":", 1)[1]
            record = self._objects(state).get(object_id)
            if not isinstance(record, dict):
                return "UNKNOWN_OBJECT"
            if self._position(record.get("position")) != self.position(state, agent_id):
                return "OBJECT_NOT_COLOCATED"
            if self._carried_object_id(state, agent_id):
                return "CARRIER_OCCUPIED"
            if not self.can_carry(record):
                return "CARRY_CAPACITY_EXCEEDED"
        if action.startswith("PUSH:"):
            parsed = self._parse_push(action)
            if parsed is None:
                return "MALFORMED_PUSH"
            object_id, destination = parsed
            record = self._objects(state).get(object_id)
            if not isinstance(record, dict):
                return "UNKNOWN_OBJECT"
            object_position = self._position(record.get("position"))
            agent_position = self.position(state, agent_id)
            if object_position is None or self._manhattan(agent_position, object_position) != 1:
                return "OBJECT_NOT_ADJACENT"
            expected = (
                object_position[0] + object_position[0] - agent_position[0],
                object_position[1] + object_position[1] - agent_position[1],
            )
            if destination != expected:
                return "NON_LOCAL_DISPLACEMENT"
            if not self.can_push(record):
                return "PUSH_CAPACITY_EXCEEDED"
            if not self.is_open(
                state,
                destination,
                ignore_object_id=object_id,
                ignore_agent_id=agent_id,
            ):
                return "PUSH_DESTINATION_BLOCKED"
        return "ACTION_NOT_AVAILABLE"

    @staticmethod
    def _manhattan(
        a: Position,
        b: Position,
    ) -> int:
        return abs(a[0] - b[0]) + abs(
            a[1] - b[1]
        )

    @staticmethod
    def _numeric_mapping(
        value: Any,
    ) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        return {
            str(key): float(item)
            for key, item in value.items()
            if isinstance(item, (int, float))
            and not isinstance(item, bool)
        }

    @staticmethod
    def _merge_numeric(
        target: dict[str, float],
        source: dict[str, float],
    ) -> None:
        for key, value in source.items():
            target[key] = (
                float(target.get(key, 0.0))
                + float(value)
            )

    def _obstacles(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        value = state.get("obstacles")
        if not isinstance(value, dict):
            raise ValueError(
                "Objective world state is missing obstacles"
            )
        return value

    def _objects(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        value = state.get("objects")
        if not isinstance(value, dict):
            raise ValueError(
                "Objective world state is missing objects"
            )
        return value
