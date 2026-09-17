"""MM-ECO-1 Living Signal Ecology — designed world substrate.

Does not modify MM-INT-1 organism parameters.
Does not implement reward/goal/seeking/preference.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.embodied_integration import default_embodied_integration_config
from mechanistic_mind.world_engine import ObjectiveObject, WorldEngineConfig
from mechanistic_mind.world_engine.physical_effector import default_effector_config

from worlds.organism_world_v03 import OrganismWorld


# --- frozen ecology constants (DESIGN_FREEZE) ---
SOURCE_ID = "SOURCE_A"
SOURCE_ROUTE = ((2, 2), (6, 2), (6, 5), (1, 5))
RESIDENCE_TICKS = 25
ABSENCE_DELAY_TICKS = 12
EMISSION = {
    "enabled": True,
    "strength": 0.8,
    "radius": 4,
    "attenuation": 0.25,
    "local_scalar_only": True,
    "frequency": 1.0,
}
HORIZON = 150
SEEDS = (20260913, 20260914, 20260915)
ORGANISM_START = (4, 3)


def _region(region_id: str, x: int, y: int) -> dict[str, Any]:
    return {"region": region_id, "cells": [[x, y]]}


def living_source_object(
    *,
    emission_enabled: bool = True,
    relocating: bool = True,
    initial_position: tuple[int, int] | None = None,
) -> ObjectiveObject:
    pos = initial_position or SOURCE_ROUTE[0]
    emission = dict(EMISSION)
    emission["enabled"] = bool(emission_enabled)
    if relocating:
        existence = {
            "mode": "RELOCATING_ROUTE",
            "trigger": {"type": "RESIDENCE_ELAPSED"},
            "residence_ticks": [RESIDENCE_TICKS, RESIDENCE_TICKS],
            "transition_delay_ticks": [ABSENCE_DELAY_TICKS, ABSENCE_DELAY_TICKS],
            "route": [
                _region(name, x, y)
                for name, (x, y) in zip(("A", "B", "C", "D"), SOURCE_ROUTE)
            ],
            "cycle": True,
            "randomize_position_within_region": False,
            "reset_availability_on_appearance": True,
        }
    else:
        existence = {"mode": "STATIC"}
    return ObjectiveObject(
        SOURCE_ID,
        pos,
        affordance="USE",
        hidden_role="UNSPECIFIED",
        cue_signature="GENERIC_OBJECT",
        cue_salience=0.85,
        quantity=1.0,
        max_quantity=1.0,
        effect_scale_state="quantity",
        body_effects={
            "energy_delta": 0.12,
            "hydration_delta": 0.04,
        },
        emission=emission,
        existence=existence,
        remove_when_exhausted=False,
    )


def living_ecology_world_config(
    *,
    emission_enabled: bool = True,
    relocating: bool = True,
    extra_objects: tuple[ObjectiveObject, ...] = (),
) -> WorldEngineConfig:
    objects = (living_source_object(emission_enabled=emission_enabled, relocating=relocating),) + tuple(
        extra_objects
    )
    return WorldEngineConfig(
        width=9,
        height=7,
        vision_radius=1,
        objects=objects,
        exogenous_events=(),
        random_event_rate=0.0,
    )


def frozen_mm_int1_body_config(
    *,
    contact_transfer: bool = True,
    physical_intake: bool = True,
    ablate_memory: bool = False,
) -> BodyConfig:
    """Exact MM-INT-1 organism + ecology-facing body physics switches only."""
    integ = default_embodied_integration_config()
    if ablate_memory:
        integ = dict(integ)
        integ["ablate_memory"] = True
    return BodyConfig(
        embodied_integration_config=integ,
        physical_effector_config=default_effector_config(),
        physical_intake_enabled=bool(physical_intake),
        contact_material_transfer_config={"enabled": bool(contact_transfer)}
        if contact_transfer
        else None,
    )


def make_living_ecology_world(
    *,
    emission_enabled: bool = True,
    relocating: bool = True,
    contact_transfer: bool = True,
    physical_intake: bool = True,
    ablate_memory: bool = False,
    start_position: tuple[int, int] = ORGANISM_START,
    initial_body: BodyState | None = None,
) -> OrganismWorld:
    return OrganismWorld(
        world_config=living_ecology_world_config(
            emission_enabled=emission_enabled,
            relocating=relocating,
        ),
        body_config=frozen_mm_int1_body_config(
            contact_transfer=contact_transfer,
            physical_intake=physical_intake,
            ablate_memory=ablate_memory,
        ),
        initial_body=initial_body or BodyState(),
        start_position=start_position,
    )


def source_record(state) -> dict[str, Any] | None:
    world = state.variables.get("world") if hasattr(state, "variables") else state
    if not isinstance(world, dict):
        return None
    objects = world.get("objects") or {}
    rec = objects.get(SOURCE_ID)
    return rec if isinstance(rec, dict) else None


def source_present(state) -> bool:
    rec = source_record(state)
    if not rec:
        return False
    ex = rec.get("existence") or {}
    if isinstance(ex, dict) and ex.get("present") is False:
        return False
    return rec.get("active", True) is not False and rec.get("position") is not None
