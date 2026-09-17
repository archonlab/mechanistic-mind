from __future__ import annotations

from dataclasses import dataclass

from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.world_engine import (
    ExogenousEventKind,
    ObjectiveObject,
    ObjectiveObstacle,
    ScheduledExogenousEvent,
    WorldEngineConfig,
)
from organism_world_v03 import OrganismWorld


VALUE_CUE = "CUE-AMBER-VALUABLE"
NEUTRAL_CUE = "CUE-NEUTRAL"
HAZARD_CUE = "CUE-ROUGH-RED"


def obstacle_value_world_config(
    *,
    condition: str = "HAZARD",
) -> WorldEngineConfig:
    """Canonical v0.3.2 route/value ecology.

    The agent observes cue signatures but not hidden roles, body-effect tables,
    progress tables, or obstacle damage probability.
    """

    condition = condition.upper()
    if condition not in {
        "HAZARD",
        "SHAM_CUE",
        "NO_OBSTACLE",
        "REMOVAL",
    }:
        raise ValueError(f"Unsupported condition: {condition!r}")

    obstacles = ()
    exogenous: tuple[ScheduledExogenousEvent, ...] = ()

    if condition != "NO_OBSTACLE":
        hazard_effects = (
            {}
            if condition == "SHAM_CUE"
            else {
                "energy_delta": -0.025,
                "fatigue_delta": 0.055,
                "damage_delta": 0.035,
            }
        )
        obstacles = (
            ObjectiveObstacle(
                obstacle_id="OBS-ROUGH-1",
                position=(3, 2),
                cue_signature=HAZARD_CUE,
                cue_salience=0.85,
                traversable=True,
                terrain_factor=1.35,
                contact_probability=1.0,
                body_effects=hazard_effects,
            ),
        )

    events = [
        # The decoy does not exist at t=0. The agent first has an opportunity
        # to learn VALUE_CUE from GOAL-TRAIN, then a look-alike appears.
        ScheduledExogenousEvent(
            event_id="SPAWN-VALUE-DECOY",
            effective_tick=30,
            kind=ExogenousEventKind.SPAWN_OBJECT,
            parameters={
                "object": {
                    "id": "GOAL-DECOY",
                    "position": [5, 0],
                    "affordance": "USE",
                    "hidden_role": "DECOY_GOAL",
                    "cue_signature": VALUE_CUE,
                    "cue_salience": 0.90,
                    "cooldown_ticks": 8,
                    "body_effects": {
                        "energy_delta": -0.01,
                        "fatigue_delta": 0.01,
                    },
                    "world_effects": {
                        "progress_delta": 0.0,
                    },
                }
            },
        )
    ]

    if condition == "REMOVAL":
        events.append(
            ScheduledExogenousEvent(
                event_id="REMOVE-OBS-ROUGH-1",
                effective_tick=45,
                kind=ExogenousEventKind.SET_OBSTACLE_ACTIVE,
                parameters={
                    "obstacle_id": "OBS-ROUGH-1",
                    "active": False,
                },
            )
        )

    exogenous = tuple(events)

    objects = (
        ObjectiveObject(
            object_id="HOME-RESOURCE",
            position=(0, 2),
            hidden_role="HOME_RESOURCE",
            cue_signature=NEUTRAL_CUE,
            cue_salience=0.45,
            cooldown_ticks=2,
            body_effects={
                "energy_delta": 0.36,
                "hydration_delta": 0.40,
                "fatigue_delta": -0.22,
                "metabolic_energy_intake": 0.16,
            },
        ),
        # Early learnable source of genuinely positive cue value.
        ObjectiveObject(
            object_id="GOAL-TRAIN",
            position=(2, 0),
            hidden_role="TRAINING_VALUE_GOAL",
            cue_signature=VALUE_CUE,
            cue_salience=0.90,
            cooldown_ticks=7,
            body_effects={
                "energy_delta": -0.008,
                "fatigue_delta": 0.006,
            },
            world_effects={
                "progress_delta": 0.55,
            },
        ),
        # Larger objective goal across the obstacle corridor.
        ObjectiveObject(
            object_id="GOAL-FAR",
            position=(6, 2),
            hidden_role="HIGH_VALUE_GOAL",
            cue_signature="CUE-GREEN-FAR-GOAL",
            cue_salience=0.75,
            cooldown_ticks=9,
            body_effects={
                "energy_delta": -0.025,
                "hydration_delta": -0.015,
                "fatigue_delta": 0.02,
            },
            world_effects={
                "progress_delta": 1.0,
            },
        ),
        # Cheap lower-value alternative.
        ObjectiveObject(
            object_id="GOAL-SMALL",
            position=(1, 4),
            hidden_role="SMALL_VALUE_GOAL",
            cue_signature="CUE-BLUE-SMALL",
            cue_salience=0.55,
            cooldown_ticks=6,
            body_effects={
                "energy_delta": -0.005,
                "fatigue_delta": 0.005,
            },
            world_effects={
                "progress_delta": 0.12,
            },
        ),
    )

    return WorldEngineConfig(
        width=7,
        height=5,
        vision_radius=1,
        blocked=(),
        objects=objects,
        obstacles=obstacles,
        exogenous_events=exogenous,
        random_event_rate=0.0,
        causal_reliability=1.0,
    )


def obstacle_value_body_config() -> BodyConfig:
    """Diagnostic physiology that keeps route-learning trials interpretable.

    This changes only the canonical obstacle/value test world. The general
    v0.3.1 Body Engine defaults remain untouched.
    """
    return BodyConfig(
        basal_energy_drain_per_day=0.008,
        basal_hydration_drain_per_day=0.009,
        passive_fatigue_gain_per_day=0.006,
        basal_metabolic_expenditure_per_day=0.055,
    )


@dataclass(slots=True)
class ObstacleValueWorld(OrganismWorld):
    """Canonical v0.3.2 world: obstacles + goals with non-identical value."""

    condition: str = "HAZARD"

    def __post_init__(self) -> None:
        self.world_config = obstacle_value_world_config(
            condition=self.condition
        )
        self.body_config = obstacle_value_body_config()
        self.initial_body = BodyState(
            mass_kg=70.0,
            height_m=1.75,
            age_days=18.0 * 365.2425,
            energy_reserve=0.92,
            hydration=0.92,
            fatigue=0.06,
            damage=0.0,
        )
        self.start_position = (0, 2)
        self.observation_context = "OBSTACLE_VALUE_WORLD_V0321"
        OrganismWorld.__post_init__(self)
