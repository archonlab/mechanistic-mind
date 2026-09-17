from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from copy import deepcopy
from typing import Any


Position = tuple[int, int]


@dataclass(frozen=True, slots=True)
class ContextualBodyEffect:
    """A numeric physical effect gated by objective body-state bounds."""

    minimum: dict[str, float] = field(default_factory=dict)
    maximum: dict[str, float] = field(default_factory=dict)
    body_effects: dict[str, float] = field(default_factory=dict)

    def matches(self, body_context: dict[str, Any]) -> bool:
        for key, threshold in self.minimum.items():
            value = body_context.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False
            if float(value) < float(threshold):
                return False
        for key, threshold in self.maximum.items():
            value = body_context.get(key)
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                return False
            if float(value) > float(threshold):
                return False
        return True

    def to_record(self) -> dict[str, Any]:
        return {
            "minimum": deepcopy(self.minimum),
            "maximum": deepcopy(self.maximum),
            "body_effects": deepcopy(self.body_effects),
        }


class ExogenousEventKind(str, Enum):
    RELOCATE_OBJECT = "RELOCATE_OBJECT"
    SET_OBJECT_ACTIVE = "SET_OBJECT_ACTIVE"
    SPAWN_OBJECT = "SPAWN_OBJECT"
    DAMAGE_ORGANISM = "DAMAGE_ORGANISM"
    SET_TERRAIN_FACTOR = "SET_TERRAIN_FACTOR"
    SET_OBSTACLE_ACTIVE = "SET_OBSTACLE_ACTIVE"


@dataclass(frozen=True, slots=True)
class ObjectiveObject:
    object_id: str
    position: Position
    affordance: str = "USE"
    hidden_role: str = "UNSPECIFIED"
    active: bool = True
    cue_signature: str = "GENERIC_OBJECT"
    cue_salience: float = 0.5
    cooldown_ticks: int = 0
    max_uses: int | None = None
    body_effects: dict[str, float] = field(default_factory=dict)
    world_effects: dict[str, float] = field(default_factory=dict)
    contextual_body_effects: tuple[ContextualBodyEffect, ...] = ()
    movable: bool = False
    mass_kg: float = 0.0
    directional_attenuation: float = 0.0
    size: float = 0.35
    shape: str = "circle"
    color: str = "#d89b45"
    opacity: float = 1.0
    friction: float = 0.25
    hardness: float = 0.5
    quantity: float = 1.0
    max_quantity: float | None = None
    durability: float = 1.0
    max_durability: float | None = None
    interaction_state_deltas: dict[str, float] = field(default_factory=dict)
    regeneration_rates: dict[str, float] = field(default_factory=dict)
    minimum_effect_state: dict[str, float] = field(default_factory=dict)
    effect_scale_state: str | None = None
    observable_state_fields: tuple[str, ...] = ()
    remove_when_exhausted: bool = False
    mobility: float | None = None
    blocks_movement: bool | None = None
    brightness: float = 0.5
    signal: str | None = None
    existence: dict[str, Any] | None = None
    autonomous: dict[str, Any] | None = None
    emission: dict[str, Any] | None = None
    # Generic world-side contact mechanics.  No field is cognition-facing
    # unless independently reflected by an ordinary perceptual property.
    interaction_physics: dict[str, Any] | None = None

    def to_record(self) -> dict[str, Any]:
        from .existence import initial_existence_state, normalize_existence
        from .autonomous import normalize_autonomous

        existence_config = normalize_existence(self.existence)
        autonomous_payload = (
            None if self.autonomous is None else normalize_autonomous(self.autonomous)
        )
        return {
            "id": self.object_id,
            "position": list(self.position),
            "affordance": self.affordance,
            "hidden_role": self.hidden_role,
            "active": bool(self.active),
            "cue_signature": self.cue_signature,
            "cue_salience": float(self.cue_salience),
            "cooldown_ticks": int(self.cooldown_ticks),
            "max_uses": (
                int(self.max_uses)
                if self.max_uses is not None
                else None
            ),
            "use_count": 0,
            "available_after_tick": 0,
            "body_effects": deepcopy(self.body_effects),
            "world_effects": deepcopy(self.world_effects),
            "contextual_body_effects": [
                effect.to_record() for effect in self.contextual_body_effects
            ],
            "movable": bool(self.movable),
            "mass_kg": float(self.mass_kg),
            "directional_attenuation": float(self.directional_attenuation),
            "size": float(self.size),
            "shape": str(self.shape),
            "color": str(self.color),
            "opacity": float(self.opacity),
            "friction": float(self.friction),
            "hardness": float(self.hardness),
            "quantity": float(self.quantity),
            "max_quantity": float(
                self.max_quantity
                if self.max_quantity is not None
                else self.quantity
            ),
            "durability": float(self.durability),
            "max_durability": float(
                self.max_durability
                if self.max_durability is not None
                else self.durability
            ),
            "mutable_state": {
                "quantity": float(self.quantity),
                "durability": float(self.durability),
            },
            "state_capacities": {
                "quantity": float(
                    self.max_quantity
                    if self.max_quantity is not None
                    else self.quantity
                ),
                "durability": float(
                    self.max_durability
                    if self.max_durability is not None
                    else self.durability
                ),
            },
            "interaction_state_deltas": deepcopy(
                self.interaction_state_deltas
            ),
            "regeneration_rates": deepcopy(self.regeneration_rates),
            "minimum_effect_state": deepcopy(self.minimum_effect_state),
            "effect_scale_state": self.effect_scale_state,
            "observable_state_fields": list(self.observable_state_fields),
            "remove_when_exhausted": bool(self.remove_when_exhausted),
            "mobility": float(
                self.mobility
                if self.mobility is not None
                else (1.0 if self.movable else 0.0)
            ),
            "blocks_movement": bool(
                self.blocks_movement
                if self.blocks_movement is not None
                else self.size >= 0.9
            ),
            "brightness": float(self.brightness),
            "signal": self.signal,
            "carried_by": None,
            "interaction_state": "FREE",
            "last_displacement": None,
            "existence": initial_existence_state(
                existence_config,
                position=self.position,
            ),
            "autonomous": autonomous_payload,
            "emission": (
                None if self.emission is None else deepcopy(self.emission)
            ),
            "interaction_physics": (
                None if self.interaction_physics is None else deepcopy(self.interaction_physics)
            ),
        }


@dataclass(frozen=True, slots=True)
class ObjectiveObstacle:
    """Objective traversable/non-traversable environmental feature.

    The agent may observe cue/position/traversability but never the hidden
    damage table or contact probability.
    """

    obstacle_id: str
    position: Position
    cue_signature: str = "GENERIC_OBSTACLE"
    cue_salience: float = 0.5
    traversable: bool = True
    active: bool = True
    terrain_factor: float = 1.0
    contact_probability: float = 1.0
    body_effects: dict[str, float] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "id": self.obstacle_id,
            "position": list(self.position),
            "cue_signature": self.cue_signature,
            "cue_salience": float(self.cue_salience),
            "traversable": bool(self.traversable),
            "active": bool(self.active),
            "terrain_factor": float(self.terrain_factor),
            "contact_probability": float(self.contact_probability),
            "body_effects": deepcopy(self.body_effects),
        }


@dataclass(frozen=True, slots=True)
class ScheduledExogenousEvent:
    event_id: str
    effective_tick: int
    kind: ExogenousEventKind
    parameters: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class WorldEngineConfig:
    width: int = 9
    height: int = 7
    vision_radius: int = 1
    blocked: tuple[Position, ...] = (
        (3, 1),
        (3, 2),
        (5, 4),
        (5, 5),
    )
    terrain_factors: dict[str, float] = field(default_factory=dict)
    # Update 4.9 — maintained local material_a availability (boundary condition).
    env_material_field: dict[str, float] = field(default_factory=dict)
    objects: tuple[ObjectiveObject, ...] = ()
    obstacles: tuple[ObjectiveObstacle, ...] = ()
    exogenous_events: tuple[ScheduledExogenousEvent, ...] = ()
    random_event_rate: float = 0.0
    random_event_kinds: tuple[ExogenousEventKind, ...] = (
        ExogenousEventKind.RELOCATE_OBJECT,
    )
    causal_reliability: float = 1.0
    outcome_delay_ticks: int = 0
    agent_carry_capacity_kg: float = 12.0
    agent_carry_size_capacity: float = 0.75
    agent_push_capacity: float = 18.0
    autonomous_dynamics_enabled: bool = False
    perception_mode: str = "CONTACT_ONLY"
    structural_radius: int = 8
    emit_radius: int = 5
    emit_strength: float = 1.0
    emit_energy_cost: float = 0.004
    emit_fatigue_cost: float = 0.003
    emit_enabled: bool = True
    # Update 4.19 — optional continuous physical background fields (researcher config).
    background_fields_spec: dict | None = None

    def validate(self) -> None:
        from .existence import normalize_existence, validate_existence_config

        if self.width < 1 or self.height < 1:
            raise ValueError("World dimensions must be positive")
        if self.vision_radius < 0:
            raise ValueError("vision_radius must be >= 0")
        if self.perception_mode not in {"CONTACT_ONLY", "MULTI_CHANNEL"}:
            raise ValueError("perception_mode must be CONTACT_ONLY or MULTI_CHANNEL")
        if self.structural_radius < 0:
            raise ValueError("structural_radius must be >= 0")
        if self.emit_radius < 0:
            raise ValueError("emit_radius must be >= 0")
        if not (0.0 <= self.random_event_rate <= 1.0):
            raise ValueError("random_event_rate must be in [0, 1]")
        if not (0.0 <= self.causal_reliability <= 1.0):
            raise ValueError("causal_reliability must be in [0, 1]")
        if self.outcome_delay_ticks < 0:
            raise ValueError("outcome_delay_ticks must be >= 0")
        if self.agent_carry_capacity_kg < 0.0:
            raise ValueError("agent_carry_capacity_kg must be >= 0")
        if self.agent_carry_size_capacity < 0.0:
            raise ValueError("agent_carry_size_capacity must be >= 0")
        if self.agent_push_capacity < 0.0:
            raise ValueError("agent_push_capacity must be >= 0")
        ids = [item.object_id for item in self.objects]
        if len(ids) != len(set(ids)):
            raise ValueError("Object IDs must be unique")
        obstacle_ids = [item.obstacle_id for item in self.obstacles]
        if len(obstacle_ids) != len(set(obstacle_ids)):
            raise ValueError("Obstacle IDs must be unique")
        for item in self.objects:
            if item.cooldown_ticks < 0:
                raise ValueError("Object cooldown_ticks must be >= 0")
            if item.max_uses is not None and item.max_uses < 1:
                raise ValueError("Object max_uses must be >= 1")
            if item.mass_kg < 0.0:
                raise ValueError("Object mass_kg must be >= 0")
            if not (0.0 <= item.directional_attenuation <= 1.0):
                raise ValueError("Object directional_attenuation must be in [0, 1]")
            if item.size <= 0.0:
                raise ValueError("Object size must be > 0")
            if item.friction < 0.0:
                raise ValueError("Object friction must be >= 0")
            if item.hardness < 0.0:
                raise ValueError("Object hardness must be >= 0")
            if item.quantity < 0.0:
                raise ValueError("Object quantity must be >= 0")
            if item.durability < 0.0:
                raise ValueError("Object durability must be >= 0")
            if item.max_quantity is not None and item.max_quantity < item.quantity:
                raise ValueError("Object max_quantity must be >= quantity")
            if item.max_durability is not None and item.max_durability < item.durability:
                raise ValueError("Object max_durability must be >= durability")
            state_fields = {"quantity", "durability"}
            for mapping_name, mapping in (
                ("interaction_state_deltas", item.interaction_state_deltas),
                ("regeneration_rates", item.regeneration_rates),
                ("minimum_effect_state", item.minimum_effect_state),
            ):
                unknown = set(mapping) - state_fields
                if unknown:
                    raise ValueError(
                        f"Object {mapping_name} has unsupported fields: {sorted(unknown)}"
                    )
                if not all(
                    isinstance(value, (int, float)) and not isinstance(value, bool)
                    for value in mapping.values()
                ):
                    raise ValueError(f"Object {mapping_name} must be numeric")
            if any(value < 0.0 for value in item.regeneration_rates.values()):
                raise ValueError("Object regeneration rates must be >= 0")
            if item.effect_scale_state not in {None, "quantity", "durability"}:
                raise ValueError("Object effect_scale_state is unsupported")
            if set(item.observable_state_fields) - state_fields:
                raise ValueError("Object observable_state_fields are unsupported")
            if item.mobility is not None and not (0.0 <= item.mobility <= 1.0):
                raise ValueError("Object mobility must be in [0, 1]")
            if not (0.0 <= item.opacity <= 1.0):
                raise ValueError("Object opacity must be in [0, 1]")
            if not (0.0 <= item.brightness <= 1.0):
                raise ValueError("Object brightness must be in [0, 1]")
            existence_config = normalize_existence(item.existence)
            validate_existence_config(
                existence_config,
                width=self.width,
                height=self.height,
                blocked=self.blocked,
                object_id=item.object_id,
            )

        for obstacle in self.obstacles:
            if not (0.0 <= obstacle.contact_probability <= 1.0):
                raise ValueError(
                    "Obstacle contact_probability must be in [0, 1]"
                )
            if obstacle.terrain_factor <= 0.0:
                raise ValueError("Obstacle terrain_factor must be > 0")
