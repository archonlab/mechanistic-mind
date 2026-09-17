from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.body import BodyEngine, BodyState
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.psyche import PsycheState
from mechanistic_mind.psyche.organism_modules import build_organism_modules
from mechanistic_mind.psyche.runtime import PsycheRuntime
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    physical_protocol_object_config,
)


SEED = 17


def protocol_world(**kwargs):
    """Pin the v0.3.4 experiment to its original compact substrate."""
    kwargs.setdefault("start_position", (2, 3))
    return ContextualObjectEcologyWorld(
        world_config=physical_protocol_object_config(),
        **kwargs,
    )


def step(world, state, action):
    return world.transition(
        state,
        {"A001": Action(action)},
        DeterministicRandom(SEED),
    )


def effect(state):
    return deepcopy(
        state.variables["developmental_history"][-1]["experienced_effects"]
    )


def action_sequence(actions, *, initial_load=0.0):
    world = protocol_world()
    if initial_load:
        world.state.variables["bodies"]["A001"]["internal_loads"] = {
            "channel_1": initial_load
        }
    state = world.state
    rows = []
    for action in actions:
        state = step(world, state, action)
        rows.append(
            {
                "action": action,
                "effect": effect(state),
                "internal_loads": deepcopy(
                    state.variables["bodies"]["A001"]["internal_loads"]
                ),
            }
        )
    return rows


def history_diagnostic():
    state = PsycheState.initial_organism_v03()
    state.memory["episodes"] = [{"action": "WAIT"}]
    state.learning["action_history_models"] = {
        "WAIT\u241fUSE:OBJ-12": {
            "count": 3,
            "mean": {"energy_signal": -0.11},
            "contexts": {},
        },
        "WAIT\u241fUSE:OBJ-29\u241fUSE:OBJ-12": {
            "count": 1,
            "mean": {"energy_signal": 0.19},
            "contexts": {},
        },
    }
    observation = Observation(
        data={
            "position": [2, 3],
            "visible_objects": [],
            "visible_obstacles": [],
            "available_actions": ("USE:OBJ-12", "WAIT"),
            "interoception": {
                "energy_signal": 0.70,
                "hydration_signal": 0.72,
                "fatigue_signal": 0.20,
                "discomfort_signal": 0.05,
                "effort_signal": 0.0,
            },
            "last_action": "USE:OBJ-29",
            "last_experienced_effects": None,
            "context": "MATCHED_HISTORY_DIAGNOSTIC",
        }
    )
    result = PsycheRuntime(build_organism_modules()).run(
        tick=2,
        agent_id="A001",
        observation=observation,
        state=state,
        random_value=0.5,
    )
    return {
        "prediction": result.state.predictions["by_action"]["USE:OBJ-12"],
        "retained_model_keys": sorted(
            result.state.learning["action_history_models"]
        ),
    }


def main():
    low = action_sequence(["USE:OBJ-29"])
    high = action_sequence(["USE:OBJ-29"], initial_load=0.60)
    repeated = action_sequence(["USE:OBJ-12", "USE:OBJ-12"])
    only_a = action_sequence(["USE:OBJ-12", "USE:OBJ-12", "WAIT"])
    only_b = action_sequence(["WAIT", "WAIT", "USE:OBJ-29"])
    both = action_sequence(["USE:OBJ-12", "USE:OBJ-12", "USE:OBJ-29"])

    geometry_world = protocol_world(start_position=(2, 2))
    truth = geometry_world.state.variables["world"]
    both_geometry = geometry_world.world_engine.directional_exposure(
        truth, position=(2, 2)
    )
    truth_first = deepcopy(truth)
    truth_first["objects"]["OBJ-42"]["active"] = False
    first_geometry = geometry_world.world_engine.directional_exposure(
        truth_first, position=(2, 2)
    )
    truth_second = deepcopy(truth)
    truth_second["objects"]["OBJ-41"]["active"] = False
    second_geometry = geometry_world.world_engine.directional_exposure(
        truth_second, position=(2, 2)
    )

    mover = protocol_world(start_position=(4, 2))
    before_move = mover.world_engine.directional_exposure(
        mover.state.variables["world"], position=(2, 2)
    )
    moved_state = step(mover, mover.state, "TAKE:OBJ-41")
    moved_state = step(mover, moved_state, "MOVE:4,3")
    moved_state = step(mover, moved_state, "RELEASE:OBJ-41")
    after_move = mover.world_engine.directional_exposure(
        moved_state.variables["world"], position=(2, 2)
    )

    body_engine = BodyEngine()
    unloaded = body_engine.transition(
        BodyState(), action=Action.wait(), carried_mass_kg=0.0
    )
    loaded = body_engine.transition(
        BodyState(), action=Action.wait(), carried_mass_kg=11.0
    )

    result = {
        "release": "0.3.4",
        "seed": SEED,
        "matched_context": {
            "low_state_effect": low[-1]["effect"],
            "high_state_effect": high[-1]["effect"],
            "energy_difference": high[-1]["effect"]["energy_signal"]
            - low[-1]["effect"]["energy_signal"],
        },
        "accumulation": repeated,
        "composition": {
            "a_only_final_effect": only_a[-1]["effect"],
            "b_only_final_effect": only_b[-1]["effect"],
            "a_then_b_final_effect": both[-1]["effect"],
        },
        "geometry": {
            "first_only": first_geometry,
            "second_only": second_geometry,
            "both": both_geometry,
            "before_move": before_move,
            "after_move": after_move,
            "moved_object_position": moved_state.variables["world"]["objects"]["OBJ-41"]["position"],
        },
        "carried_load": {
            "unloaded": unloaded.state.to_dict(),
            "loaded": loaded.state.to_dict(),
            "loaded_objective_effects": loaded.objective_effects,
        },
        "short_history": history_diagnostic(),
        "claim_boundary": (
            "Controlled substrate checks only; no autonomous discovery or "
            "stable configuration reconstruction is demonstrated."
        ),
    }
    output = ROOT / "experiments" / "contextual_object_ecology_v034_result.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
