"""MM-ECO-1 RICH AUTONOMOUS SIGNAL ECOLOGY — world substrate only.

Does not modify MM-INT-1 organism parameters.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from mechanistic_mind.body import BodyConfig, BodyState
from mechanistic_mind.body.embodied_integration import (
    default_embodied_integration_config,
    default_mm_int2_integration_config,
    DRIVE_COUPLING_ANTAGONISTIC,
    DRIVE_COUPLING_LEGACY,
)
from mechanistic_mind.world_engine import ObjectiveObject, WorldEngineConfig
from mechanistic_mind.world_engine.physical_effector import default_effector_config
from worlds.organism_world_v03 import OrganismWorld

HORIZON = 400
SEEDS = (17, 23, 41, 59, 83)
ORGANISM_START = (4, 3)

SRC_A_ROUTE = ((2, 2), (6, 2), (6, 5), (1, 5))
SRC_B_ROUTE = ((7, 1), (0, 6))
OBJ_C_ROUTE = ((1, 3), (2, 3), (3, 3), (2, 3))


def _region(region_id: str, x: int, y: int) -> dict[str, Any]:
    return {"region": region_id, "cells": [[x, y]]}


def rich_ambient_spec() -> dict[str, Any]:
    return {
        "enabled": True,
        "keys": [
            "temperature",
            "humidity",
            "chemical_1",
            "illumination",
            "vibration",
        ],
        "noise": 0.01,
        "body_coupling": {
            "temperature": {"fatigue_delta": 0.0002},
            "humidity": {"hydration_delta": -0.0001},
        },
        "regions": {
            "A": {
                "center": [4, 3],
                "radius": 3,
                "base": {
                    "temperature": 0.62,
                    "humidity": 0.55,
                    "chemical_1": 0.70,
                    "illumination": 0.45,
                    "vibration": 0.15,
                },
            },
            "B": {
                "center": [7, 5],
                "radius": 2,
                "base": {
                    "temperature": 0.40,
                    "humidity": 0.70,
                    "chemical_1": 0.25,
                    "illumination": 0.65,
                    "vibration": 0.35,
                },
            },
        },
        "global_base": {
            "temperature": 0.50,
            "humidity": 0.50,
            "chemical_1": 0.40,
            "illumination": 0.50,
            "vibration": 0.20,
        },
        "temporal": {"period_ticks": 50, "amplitude": 0.08},
        "phase": "STABLE",
        "violations": {},
        "schema": {},
    }


def _relocating(route, residence: int, delay: int) -> dict[str, Any]:
    return {
        "mode": "RELOCATING_ROUTE",
        "trigger": {"type": "RESIDENCE_ELAPSED"},
        "residence_ticks": [residence, residence],
        "transition_delay_ticks": [delay, delay],
        "route": [
            _region(chr(ord("A") + i), x, y) for i, (x, y) in enumerate(route)
        ],
        "cycle": True,
        "randomize_position_within_region": False,
        "reset_availability_on_appearance": True,
    }


def rich_objects(
    *,
    emission_enabled: bool = True,
    relocating: bool = True,
    mover_enabled: bool = True,
) -> tuple[ObjectiveObject, ...]:
    src_a = ObjectiveObject(
        "SRC_A",
        SRC_A_ROUTE[0],
        hidden_role="UNSPECIFIED",
        cue_signature="GENERIC_OBJECT",
        cue_salience=0.85,
        quantity=1.0,
        max_quantity=1.0,
        effect_scale_state="quantity",
        body_effects={"energy_delta": 0.12, "hydration_delta": 0.04},
        emission={
            "enabled": bool(emission_enabled),
            "strength": 0.8,
            "radius": 4,
            "attenuation": 0.25,
            "local_scalar_only": True,
            "frequency": 1.0,
        },
        existence=_relocating(SRC_A_ROUTE, 25, 12) if relocating else {"mode": "STATIC"},
    )
    src_b = ObjectiveObject(
        "SRC_B",
        SRC_B_ROUTE[0],
        hidden_role="UNSPECIFIED",
        cue_signature="GENERIC_OBJECT",
        cue_salience=0.55,
        quantity=1.0,
        max_quantity=1.0,
        emission={
            "enabled": bool(emission_enabled),
            "strength": 0.5,
            "radius": 3,
            "attenuation": 0.30,
            "local_scalar_only": True,
            "frequency": 0.7,
        },
        existence=_relocating(SRC_B_ROUTE, 40, 15) if relocating else {"mode": "STATIC"},
    )
    obj_c = ObjectiveObject(
        "OBJ_C",
        OBJ_C_ROUTE[0],
        hidden_role="UNSPECIFIED",
        cue_signature="GENERIC_OBJECT",
        cue_salience=0.70,
        emission={
            "enabled": bool(emission_enabled),
            "strength": 0.35,
            "radius": 2,
            "attenuation": 0.35,
            "local_scalar_only": True,
            "frequency": 1.2,
        },
        existence={"mode": "STATIC"},
        autonomous={
            "enabled": bool(mover_enabled),
            "motion": {
                "pattern": "PERIODIC_ROUTE",
                "period_ticks": 5,
                "route": [list(p) for p in OBJ_C_ROUTE],
                "phase": 0,
            },
        }
        if mover_enabled
        else None,
    )
    obj_d = ObjectiveObject(
        "OBJ_D",
        (5, 5),
        hidden_role="UNSPECIFIED",
        cue_signature="GENERIC_OBJECT",
        cue_salience=0.95,
        existence={"mode": "STATIC"},
        emission={"enabled": False, "strength": 0.0, "radius": 0},
    )
    return (src_a, src_b, obj_c, obj_d)


def rich_world_config(
    *,
    emission_enabled: bool = True,
    relocating: bool = True,
    mover_enabled: bool = True,
    ambient_enabled: bool = True,
    autonomous_dynamics: bool = True,
) -> WorldEngineConfig:
    return WorldEngineConfig(
        width=9,
        height=7,
        vision_radius=1,
        objects=rich_objects(
            emission_enabled=emission_enabled,
            relocating=relocating,
            mover_enabled=mover_enabled,
        ),
        exogenous_events=(),
        random_event_rate=0.0,
        autonomous_dynamics_enabled=bool(autonomous_dynamics and mover_enabled),
        background_fields_spec=rich_ambient_spec() if ambient_enabled else {"enabled": False},
    )


def frozen_mm_int1_body_config(
    *,
    contact_transfer: bool = True,
    physical_intake: bool = True,
    ablate_memory: bool = False,
    ablate_reinstatement: bool = False,
    ablate_world_receptors: bool = False,
    ablate_body_receptors: bool = False,
    mm_int2: bool = False,
    drive_coupling: str | None = None,
) -> BodyConfig:
    integ = dict(
        default_mm_int2_integration_config()
        if mm_int2
        else default_embodied_integration_config()
    )
    if drive_coupling is not None:
        integ["drive_coupling"] = str(drive_coupling)
    if ablate_memory:
        integ["ablate_memory"] = True
    if ablate_reinstatement:
        integ["reinstatement_to_dynamics_enabled"] = False
    if ablate_world_receptors:
        integ["world_receptors_enabled"] = False
    if ablate_body_receptors:
        integ["body_receptors_enabled"] = False
    return BodyConfig(
        embodied_integration_config=integ,
        physical_effector_config=default_effector_config(),
        physical_intake_enabled=bool(physical_intake),
        contact_material_transfer_config={"enabled": True} if contact_transfer else None,
    )


def make_rich_ecology_world(
    *,
    emission_enabled: bool = True,
    relocating: bool = True,
    mover_enabled: bool = True,
    ambient_enabled: bool = True,
    contact_transfer: bool = True,
    physical_intake: bool = True,
    ablate_memory: bool = False,
    ablate_reinstatement: bool = False,
    ablate_world_receptors: bool = False,
    ablate_body_receptors: bool = False,
    mm_int2: bool = False,
    drive_coupling: str | None = None,
    start_position: tuple[int, int] = ORGANISM_START,
) -> OrganismWorld:
    return OrganismWorld(
        world_config=rich_world_config(
            emission_enabled=emission_enabled,
            relocating=relocating,
            mover_enabled=mover_enabled,
            ambient_enabled=ambient_enabled,
        ),
        body_config=frozen_mm_int1_body_config(
            contact_transfer=contact_transfer,
            physical_intake=physical_intake,
            ablate_memory=ablate_memory,
            ablate_reinstatement=ablate_reinstatement,
            ablate_world_receptors=ablate_world_receptors,
            ablate_body_receptors=ablate_body_receptors,
            mm_int2=mm_int2,
            drive_coupling=drive_coupling,
        ),
        initial_body=BodyState(),
        start_position=start_position,
    )


def object_record(state, object_id: str) -> dict[str, Any] | None:
    world = state.variables.get("world") if hasattr(state, "variables") else state
    if not isinstance(world, dict):
        return None
    rec = (world.get("objects") or {}).get(object_id)
    return rec if isinstance(rec, dict) else None


def object_present(state, object_id: str) -> bool:
    rec = object_record(state, object_id)
    if not rec:
        return False
    ex = rec.get("existence") or {}
    if isinstance(ex, dict) and ex.get("present") is False:
        return False
    return rec.get("active", True) is not False and rec.get("position") is not None
