"""Update #4 diagnostic worlds: effects independent of existence dynamics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.world_engine import ObjectiveObject, WorldEngineConfig

from organism_world_v03 import OrganismWorld


SHARED_EFFECTS = {
    "energy_delta": 0.20,
    "hydration_delta": 0.00,
    "fatigue_delta": 0.00,
}


def _region(region_id: str, x: int, y: int) -> dict[str, Any]:
    return {"region": region_id, "cells": [[x, y]]}


def static_object_config() -> WorldEngineConfig:
    return _config(
        ObjectiveObject(
            "OBJ-A",
            (1, 1),
            cue_signature="CUE-A",
            body_effects=dict(SHARED_EFFECTS),
            max_uses=2,
            existence={"mode": "STATIC"},
        )
    )


def random_relocation_config() -> WorldEngineConfig:
    return _config(
        ObjectiveObject(
            "OBJ-A",
            (1, 1),
            cue_signature="CUE-A",
            body_effects=dict(SHARED_EFFECTS),
            max_uses=2,
            existence={
                "mode": "RELOCATING_RANDOM",
                "trigger": {"type": "DEPLETED"},
                "transition_delay_ticks": [2, 2],
                "allowed_regions": [
                    _region("A", 1, 1),
                    _region("B", 3, 1),
                    _region("C", 5, 1),
                    _region("D", 7, 1),
                ],
                "reset_availability_on_appearance": True,
            },
        )
    )


def route_relocation_config(*, cycle: bool = True) -> WorldEngineConfig:
    return _config(
        ObjectiveObject(
            "OBJ-A",
            (1, 1),
            cue_signature="CUE-A",
            body_effects=dict(SHARED_EFFECTS),
            max_uses=2,
            existence={
                "mode": "RELOCATING_ROUTE",
                "trigger": {"type": "DEPLETED"},
                "route": [
                    _region("A", 1, 1),
                    _region("B", 3, 1),
                    _region("C", 5, 1),
                ],
                "cycle": cycle,
                "transition_delay_ticks": [2, 2],
                "randomize_position_within_region": False,
                "reset_availability_on_appearance": True,
            },
        )
    )


def scientific_acceptance_config() -> WorldEngineConfig:
    return _config(
        ObjectiveObject(
            "OBJ-A",
            (1, 1),
            cue_signature="CUE-A",
            body_effects={"energy_delta": 0.20},
            max_uses=1,
            existence={
                "mode": "RELOCATING_ROUTE",
                "trigger": {"type": "DEPLETED"},
                "route": [
                    _region("A", 1, 1),
                    _region("B", 3, 1),
                    _region("C", 5, 1),
                ],
                "cycle": True,
                "transition_delay_ticks": [2, 2],
                "randomize_position_within_region": False,
                "reset_availability_on_appearance": True,
            },
        )
    )


def _config(obj: ObjectiveObject) -> WorldEngineConfig:
    return WorldEngineConfig(
        width=9,
        height=7,
        vision_radius=8,
        blocked=(),
        objects=(obj,),
    )


@dataclass(slots=True)
class ObjectExistenceDynamicsWorld(OrganismWorld):
    world_config: WorldEngineConfig = field(default_factory=scientific_acceptance_config)
    start_position: tuple[int, int] = (1, 1)
    observation_context: str = "OBJECT_EXISTENCE_DYNAMICS_V04"
