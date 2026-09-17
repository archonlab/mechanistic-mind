from __future__ import annotations

from dataclasses import dataclass, field
import random
from typing import Any

from mechanistic_mind.agent import Action
from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.world_engine import (
    ContextualBodyEffect,
    ObjectiveObject,
    WorldEngineConfig,
)

from organism_world_v03 import OrganismWorld


def todo4_calibrated_body_config() -> BodyConfig:
    """Finite toy physiology scaled to permit hundreds of ordinary actions."""
    return BodyConfig(
        basal_energy_drain_per_day=0.0008,
        basal_hydration_drain_per_day=0.0009,
        passive_fatigue_gain_per_day=0.0007,
        movement_energy_cost_per_cell=0.0008,
        movement_hydration_cost_per_cell=0.0003,
        movement_fatigue_cost_per_cell=0.0006,
        movement_metabolic_expenditure_per_effort=0.003,
        basal_metabolic_expenditure_per_day=0.008,
        internal_load_decay_per_day=0.01,
        carried_energy_cost_per_kg_day=0.00015,
        carried_hydration_cost_per_kg_day=0.00005,
        carried_fatigue_cost_per_kg_day=0.00010,
    )


def physical_protocol_object_config() -> WorldEngineConfig:
    """Compact geometry retained for the focused carry/push protocol."""
    return WorldEngineConfig(
        width=8,
        height=7,
        vision_radius=2,
        blocked=(),
        objects=(
            ObjectiveObject(
                "OBJ-12",
                (2, 3),
                cue_signature="CUE-MATTE-12",
                size=0.30,
                shape="circle",
                color="#64b5a7",
                opacity=0.88,
                interaction_state_deltas={"quantity": -0.18},
                minimum_effect_state={"quantity": 1e-9},
                effect_scale_state="quantity",
                observable_state_fields=("quantity",),
                body_effects={"internal_load:channel_1": 0.34},
            ),
            ObjectiveObject(
                "OBJ-29",
                (2, 3),
                cue_signature="CUE-MATTE-29",
                size=0.42,
                shape="triangle",
                color="#b58bd6",
                opacity=0.92,
                interaction_state_deltas={"quantity": -0.12},
                minimum_effect_state={"quantity": 1e-9},
                effect_scale_state="quantity",
                body_effects={"fatigue_delta": 0.01},
                contextual_body_effects=(
                    ContextualBodyEffect(
                        minimum={"internal_load:channel_1": 0.55},
                        body_effects={
                            "energy_delta": 0.24,
                            "fatigue_delta": -0.20,
                        },
                    ),
                ),
            ),
            ObjectiveObject(
                "OBJ-41",
                (4, 2),
                cue_signature="CUE-RIGID-41",
                movable=True,
                mass_kg=7.0,
                size=0.55,
                shape="circle",
                color="#55a9d6",
                friction=0.18,
                hardness=0.65,
                directional_attenuation=0.65,
            ),
            ObjectiveObject(
                "OBJ-42",
                (5, 2),
                cue_signature="CUE-RIGID-42",
                movable=True,
                mass_kg=15.0,
                size=1.0,
                shape="square",
                color="#d99545",
                friction=0.25,
                hardness=0.80,
                directional_attenuation=0.50,
            ),
            ObjectiveObject(
                "OBJ-73",
                (6, 4),
                cue_signature="CUE-DENSE-73",
                movable=True,
                mass_kg=80.0,
                size=1.15,
                shape="hexagon",
                color="#7f8792",
                friction=0.80,
                hardness=0.95,
                directional_attenuation=0.30,
            ),
        ),
    )


def default_contextual_object_config(seed: int = 17) -> WorldEngineConfig:
    """Generate a deterministic 32x32 heterogeneous object ecology."""
    rng = random.Random(int(seed))
    start = (15, 16)
    objects: list[ObjectiveObject] = [
        ObjectiveObject(
            "OBJ-12",
            (14, 16),
            cue_signature="CUE-MATTE-12",
            size=0.30,
            shape="circle",
            color="#64b5a7",
            opacity=0.88,
            quantity=0.90,
            max_quantity=0.90,
            interaction_state_deltas={"quantity": -0.18},
            minimum_effect_state={"quantity": 1e-9},
            effect_scale_state="quantity",
            observable_state_fields=("quantity",),
            body_effects={"internal_load:channel_1": 0.34},
        ),
        ObjectiveObject(
            "OBJ-29",
            (15, 16),
            cue_signature="CUE-MATTE-29",
            size=0.42,
            shape="triangle",
            color="#b58bd6",
            opacity=0.92,
            quantity=1.0,
            max_quantity=1.0,
            interaction_state_deltas={"quantity": -0.12},
            minimum_effect_state={"quantity": 1e-9},
            effect_scale_state="quantity",
            body_effects={"fatigue_delta": 0.01},
            contextual_body_effects=(
                ContextualBodyEffect(
                    minimum={"internal_load:channel_1": 0.55},
                    body_effects={
                        "energy_delta": 0.24,
                        "fatigue_delta": -0.20,
                    },
                ),
            ),
        ),
        ObjectiveObject(
            "OBJ-41",
            (18, 15),
            cue_signature="CUE-RIGID-41",
            movable=True,
            mass_kg=7.0,
            size=0.55,
            shape="circle",
            color="#55a9d6",
            friction=0.18,
            hardness=0.65,
            directional_attenuation=0.65,
        ),
        ObjectiveObject(
            "OBJ-42",
            (20, 15),
            cue_signature="CUE-RIGID-42",
            movable=True,
            mass_kg=15.0,
            size=1.0,
            shape="square",
            color="#d99545",
            friction=0.25,
            hardness=0.80,
            directional_attenuation=0.50,
        ),
        ObjectiveObject(
            "OBJ-73",
            (22, 17),
            cue_signature="CUE-DENSE-73",
            movable=True,
            mass_kg=80.0,
            size=1.15,
            shape="hexagon",
            color="#7f8792",
            friction=0.80,
            hardness=0.95,
            directional_attenuation=0.30,
        ),
    ]

    occupied = {item.position for item in objects}
    cluster_centers = ((5, 5), (26, 6), (7, 25), (25, 25), (16, 8))
    candidates: list[tuple[int, int]] = []
    for center_x, center_y in cluster_centers:
        offsets = [
            (dx, dy)
            for dy in range(-3, 4)
            for dx in range(-3, 4)
            if abs(dx) + abs(dy) <= 4
        ]
        rng.shuffle(offsets)
        for dx, dy in offsets[:7]:
            candidates.append((center_x + dx, center_y + dy))
    candidates.extend(((1, 16), (30, 16), (16, 30), (2, 29), (29, 2)))
    candidates = [
        position
        for position in candidates
        if 0 <= position[0] < 32
        and 0 <= position[1] < 32
        and position not in occupied
        and position != start
    ]
    rng.shuffle(candidates)

    effect_combinations = (
        {"energy_delta": 0.10, "internal_load:channel_2": 0.08},
        {"hydration_delta": 0.16, "fatigue_delta": 0.025},
        {"fatigue_delta": -0.11, "hydration_delta": -0.025},
        {"damage_delta": 0.018, "energy_delta": 0.07},
        {"internal_load:channel_1": 0.13, "fatigue_delta": 0.035},
        {"energy_delta": -0.04, "hydration_delta": 0.11},
        {"metabolic_energy_intake": 0.12, "energy_delta": 0.05},
    )
    shapes = ("circle", "square", "triangle", "diamond", "hexagon")

    for index, position in enumerate(candidates[:25]):
        quantity = round(rng.uniform(0.45, 1.50), 3)
        durability = round(rng.uniform(0.55, 1.0), 3)
        mode = index % 5
        state_deltas: dict[str, float] = {}
        regeneration: dict[str, float] = {}
        requirements: dict[str, float] = {}
        scale_state = None
        observable: tuple[str, ...] = ()
        if mode == 0:
            state_deltas = {"quantity": -round(rng.uniform(0.08, 0.22), 3)}
            requirements = {"quantity": 1e-9}
            scale_state = "quantity"
            observable = ("quantity",)
        elif mode == 1:
            state_deltas = {"durability": -round(rng.uniform(0.04, 0.12), 3)}
            requirements = {"durability": 1e-9}
            scale_state = "durability"
        elif mode == 2:
            state_deltas = {"quantity": -round(rng.uniform(0.12, 0.25), 3)}
            regeneration = {"quantity": round(rng.uniform(0.01, 0.04), 3)}
            requirements = {"quantity": 1e-9}
            scale_state = "quantity"
            observable = ("quantity",)
        elif mode == 3:
            # Update 4.6: replenishing effects must bind to a quantity reservoir.
            state_deltas = {"quantity": -round(rng.uniform(0.08, 0.22), 3)}
            regeneration = {"quantity": round(rng.uniform(0.01, 0.04), 3)}
            requirements = {"quantity": 1e-9}
            scale_state = "quantity"
            observable = ("quantity",)
        elif mode == 4:
            # Update 4.6: finite transfer via quantity scale (no infinite identical USE).
            state_deltas = {"quantity": -round(rng.uniform(0.10, 0.20), 3)}
            requirements = {"quantity": 1e-9}
            scale_state = "quantity"
            observable = ("quantity",)

        size = round(rng.uniform(0.24, 1.18), 3)
        mass = round(rng.uniform(0.5, 58.0), 3)
        movable = index % 4 != 0
        mobility = 0.0 if index % 11 == 0 else round(rng.uniform(0.35, 1.0), 3)
        if mobility == 0.0:
            movable = False
        color = "#" + "".join(f"{rng.randint(72, 210):02x}" for _ in range(3))
        contextual = (
            (
                ContextualBodyEffect(
                    minimum={"fatigue": 0.55},
                    body_effects={"energy_delta": 0.08, "fatigue_delta": -0.04},
                ),
            )
            if index % 6 == 0
            else ()
        )
        objects.append(
            ObjectiveObject(
                f"OBJ-{100 + index:03d}",
                position,
                cue_signature=f"CUE-{rng.randrange(16):02X}-{index:02d}",
                cue_salience=round(rng.uniform(0.2, 0.95), 3),
                body_effects=dict(effect_combinations[index % len(effect_combinations)]),
                contextual_body_effects=contextual,
                movable=movable,
                mobility=mobility,
                mass_kg=mass,
                size=size,
                shape=shapes[index % len(shapes)],
                color=color,
                opacity=round(rng.uniform(0.55, 1.0), 3),
                brightness=round(rng.uniform(0.2, 0.9), 3),
                friction=round(rng.uniform(0.08, 0.85), 3),
                hardness=round(rng.uniform(0.15, 0.98), 3),
                quantity=quantity,
                max_quantity=quantity,
                durability=durability,
                max_durability=durability,
                interaction_state_deltas=state_deltas,
                regeneration_rates=regeneration,
                minimum_effect_state=requirements,
                effect_scale_state=scale_state,
                observable_state_fields=observable,
                directional_attenuation=(
                    round(rng.uniform(0.15, 0.65), 3)
                    if index % 7 == 0
                    else 0.0
                ),
            )
        )
        occupied.add(position)

    # Update 4.6 safety net: any replenishing body_effects without a reservoir
    # get quantity-scaled depletion so USE cannot repeat identically forever.
    patched: list = []
    for item in objects:
        effects = dict(getattr(item, "body_effects", {}) or {})
        replenishing = any(
            (isinstance(v, (int, float)) and float(v) > 0.0)
            for k, v in effects.items()
            if str(k).endswith("_delta")
            or str(k) in {"metabolic_energy_intake", "energy_delta", "hydration_delta"}
        )
        scale = getattr(item, "effect_scale_state", None)
        deltas = dict(getattr(item, "interaction_state_deltas", {}) or {})
        if replenishing and not scale and not deltas:
            from dataclasses import replace as _replace
            qty = float(getattr(item, "quantity", 1.0) or 1.0)
            chunk = max(0.08, min(0.22, qty * 0.15))
            item = _replace(
                item,
                interaction_state_deltas={"quantity": -round(chunk, 3)},
                minimum_effect_state={"quantity": 1e-9},
                effect_scale_state="quantity",
                observable_state_fields=tuple(
                    dict.fromkeys(
                        list(getattr(item, "observable_state_fields", ()) or ())
                        + ["quantity"]
                    )
                ),
            )
        patched.append(item)
    objects = patched

    return WorldEngineConfig(
        width=32,
        height=32,
        vision_radius=2,
        blocked=(),
        objects=tuple(objects),
    )


@dataclass(slots=True)
class ContextualObjectEcologyWorld(OrganismWorld):
    """Persistent object motion, body context, and directional local physics."""

    world_config: WorldEngineConfig = field(
        default_factory=default_contextual_object_config
    )
    body_config: BodyConfig = field(default_factory=todo4_calibrated_body_config)
    start_position: tuple[int, int] = (15, 16)
    observation_context: str = "CONTEXTUAL_OBJECT_ECOLOGY_V035"
    exposure_source_direction: tuple[int, int] = (1, 0)
    exposure_reach: int = 3
    # TODO #4 calibrated rates. Legacy values remain available through the
    # explicit ``legacy_physiology`` constructor below for matched controls.
    ambient_energy_cost: float = 0.0008
    ambient_hydration_cost: float = 0.0007
    ambient_fatigue_cost: float = 0.0005

    def __post_init__(self) -> None:
        OrganismWorld.__post_init__(self)

    @classmethod
    def legacy_physiology(cls, **kwargs: Any) -> "ContextualObjectEcologyWorld":
        return cls(body_config=BodyConfig(), ambient_energy_cost=0.055, ambient_hydration_cost=0.012, ambient_fatigue_cost=0.035, **kwargs)

    def observe(self, state: Any, agent_id: str) -> Any:
        observation = OrganismWorld.observe(self, state, agent_id)
        truth = self._world_truth(state)
        position = self.world_engine.position(truth, agent_id)
        field = self.world_engine.directional_exposure(
            truth, position=position,
            source_direction=self.exposure_source_direction,
            reach=self.exposure_reach,
        )
        context = observation.data.get("perceptual_context", {})
        context.setdefault("modalities", {})["physical_field"] = True
        context.setdefault("fragments", []).append({
            "modality": "physical_field",
            "direction": list(self.exposure_source_direction),
            "magnitude": round(float(field["exposure_multiplier"]), 3),
        })
        observation.data["perceptual_context"] = context
        return observation

    def objective_context_effects(
        self,
        world_truth: dict[str, Any],
        *,
        body_before: BodyState,
        action: Action,
        agent_id: str | None = None,
    ) -> tuple[dict[str, float], dict[str, Any]]:
        target_id = agent_id or self.agent_id
        position = self.world_engine.position(world_truth, target_id)
        geometry = self.world_engine.directional_exposure(
            world_truth,
            position=position,
            source_direction=self.exposure_source_direction,
            reach=self.exposure_reach,
        )
        multiplier = float(geometry["exposure_multiplier"])
        effects = {
            "energy_delta": -self.ambient_energy_cost * multiplier,
            "hydration_delta": -self.ambient_hydration_cost * multiplier,
            "fatigue_delta": self.ambient_fatigue_cost * multiplier,
        }
        return effects, {
            "kind": "DIRECTIONAL_LOCAL_EXPOSURE",
            "position": list(position),
            "source_direction": list(self.exposure_source_direction),
            **geometry,
            "body_effects": dict(effects),
        }


@dataclass(slots=True)
class ObjectManipulationAcceptanceWorld(ContextualObjectEcologyWorld):
    """Small real-runtime acceptance world using the v0.3.4 object ecology."""

    start_position: tuple[int, int] = (3, 2)
    observation_context: str = "OBJECT_MANIPULATION_ACCEPTANCE_V035"
    world_config: WorldEngineConfig = field(
        default_factory=physical_protocol_object_config
    )


def dynamic_contextual_object_config(seed: int = 17):
    """Same ecology as default, with autonomous dynamics enabled on selected objects.

    Dynamics are physical/temporal only. No semantic resource labels.
    """
    from dataclasses import replace
    from mechanistic_mind.world_engine.models import ObjectiveObject

    base = default_contextual_object_config(seed)
    objects = []
    for index, item in enumerate(base.objects):
        autonomous = None
        # Nearby movable / clustered objects get structured motion; others may cycle state.
        if item.object_id in {"OBJ-41", "OBJ-42"}:
            x, y = item.position
            autonomous = {
                "enabled": True,
                "motion": {
                    "pattern": "PERIODIC_ROUTE",
                    "period_ticks": 3,
                    "route": [
                        [x, y],
                        [min(31, x + 2), y],
                        [min(31, x + 2), min(31, y + 2)],
                        [x, min(31, y + 2)],
                    ],
                    "phase": index,
                },
            }
        elif item.object_id == "OBJ-12":
            x, y = item.position
            autonomous = {
                "enabled": True,
                "motion": {
                    "pattern": "OSCILLATE",
                    "period_ticks": 4,
                    "route": [[x, y], [x - 1, y]],
                },
            }
        elif item.object_id == "OBJ-29":
            autonomous = {
                "enabled": True,
                "motion": {"pattern": "NONE", "period_ticks": 1, "route": []},
                "state_cycle": {
                    "field": "quantity",
                    "period_ticks": 8,
                    "amplitude": 0.08,
                    "center": float(item.quantity),
                },
            }
        elif index % 7 == 0 and item.movable:
            x, y = item.position
            autonomous = {
                "enabled": True,
                "motion": {
                    "pattern": "BOUNDED_WANDER",
                    "period_ticks": 5,
                    "bound_min": [max(0, x - 2), max(0, y - 2)],
                    "bound_max": [min(31, x + 2), min(31, y + 2)],
                    "step": 1,
                    "phase": index,
                },
            }
        if autonomous is None:
            objects.append(item)
        else:
            objects.append(replace(item, autonomous=autonomous))
    return replace(base, objects=tuple(objects), autonomous_dynamics_enabled=True)


def static_contextual_object_config(seed: int = 17):
    """Explicit STATIC_WORLD control: identical ecology, autonomous disabled."""
    from dataclasses import replace

    base = default_contextual_object_config(seed)
    return replace(base, autonomous_dynamics_enabled=False)


def multi_channel_contextual_object_config(seed: int = 17):
    """Canonical MULTI_CHANNEL + DYNAMIC ecology used by Updates 4.x / Observer.

    Restored after Update 4.7 sync accidentally dropped these helpers from an
    older extract. Science unchanged: sets perception_mode only.
    """
    from dataclasses import replace

    base = dynamic_contextual_object_config(seed)
    return replace(base, perception_mode="MULTI_CHANNEL", autonomous_dynamics_enabled=True)


def contact_only_contextual_object_config(seed: int = 17):
    """CONTACT_ONLY control ecology (same objects/dynamics, reduced perception)."""
    from dataclasses import replace

    base = dynamic_contextual_object_config(seed)
    return replace(base, perception_mode="CONTACT_ONLY", autonomous_dynamics_enabled=True)


def dynamic_sustaining_ecology_config(
    seed: int = 17, *, condition: str = "DYNAMIC_SIGNAL",
    resistance_mode: str = "OVERCOMEABLE",
):
    """Update 4.18.2 matched world-side ecology conditions.

    Names are researcher configuration only. Object records and perception
    retain generic physical quantities/cues; no usefulness or target field is
    exposed to cognition.
    """
    from dataclasses import replace

    condition = str(condition).upper()
    resistance_mode = str(resistance_mode).upper()
    base = multi_channel_contextual_object_config(seed)
    objects = []
    for item in base.objects:
        if item.object_id != "OBJ-12":
            objects.append(item); continue
        sustaining = condition not in {"POOR", "INERT_SIGNAL"}
        signaled = condition in {"DYNAMIC_SIGNAL", "DECORRELATED_SIGNAL", "INERT_SIGNAL"}
        decorrelated = condition == "DECORRELATED_SIGNAL"
        effects = {"energy_delta": 0.18, "hydration_delta": 0.12,
                   "fatigue_delta": -0.04} if sustaining else {}
        physics = None
        if resistance_mode != "OFF":
            table = {
                "LOW": (0.5, 0.8, 1.0),
                "OVERCOMEABLE": (2.0, 0.55, 1.0),
                "IMPOSSIBLE": (8.0, 0.15, 0.25),
                "DYNAMIC": (2.0, 0.55, 1.0),
                "STRUCTURED": (2.0, 0.55, 1.0),
                "RANDOM_CONTROL": (2.0, 0.55, 1.0),
            }
            resistance, rate, ceiling = table.get(resistance_mode, table["OVERCOMEABLE"])
            physics = {"enabled": True, "mode": resistance_mode,
                "resistance": resistance, "transformation_rate": rate,
                "interaction_magnitude": 1.0, "interaction_threshold": 1.0,
                "transformation_ceiling": ceiling,
                "resistance_amplitude": 0.8, "resistance_period": 24,
                "variability": 0.65, "transformation_recovery_rate": 0.002,
                "alternative_action_factor": 0.60}
        emission = {"enabled": signaled, "strength": 0.18, "frequency": 1.7,
            "radius": 9, "attenuation": 0.16, "state_field": "quantity",
            "state_gain": 2.0, "decorrelation_period": 17 if decorrelated else 0,
            "local_scalar_only": True, "directionality": 0.0}
        autonomous = {"enabled": True,
            "motion": {"pattern": "PERIODIC_ROUTE", "period_ticks": 5,
                "route": [[14,16],[14,13],[18,13],[18,16]], "phase": 0},
            "state_cycle": {"field": "quantity", "period_ticks": 20,
                "amplitude": 0.35, "center": 0.55}}
        objects.append(replace(item, body_effects=effects, quantity=0.55,
            max_quantity=0.90, interaction_state_deltas={"quantity": -0.12},
            regeneration_rates={"quantity": 0.015}, effect_scale_state="quantity",
            minimum_effect_state={"quantity": 1e-9}, autonomous=autonomous,
            emission=emission, interaction_physics=physics, movable=True,
            mobility=1.0, mass_kg=1.0))
    return replace(base, objects=tuple(objects), perception_mode="MULTI_CHANNEL",
                   autonomous_dynamics_enabled=True)
