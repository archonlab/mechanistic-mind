from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.body import BodyEngine, BodyState
from mechanistic_mind.core import DeterministicRandom, Engine
from mechanistic_mind.agent import Agent
from mechanistic_mind.psyche import PsycheState
from mechanistic_mind.psyche.organism_modules import build_organism_modules
from mechanistic_mind.psyche.runtime import PsycheRuntime
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    physical_protocol_object_config,
)


def _compact_world(**kwargs):
    return ContextualObjectEcologyWorld(
        world_config=physical_protocol_object_config(),
        start_position=kwargs.pop("start_position", (2, 3)),
        **kwargs,
    )


def _step(world, state, action, seed=17):
    return world.transition(state, {"A001": Action(action)}, DeterministicRandom(seed))


def test_contextual_effect_depends_on_objective_body_state():
    low_world = _compact_world()
    low = _step(low_world, low_world.state, "USE:OBJ-29")
    low_delta = low.variables["developmental_history"][-1]["experienced_effects"]

    high_world = _compact_world()
    high_world.state.variables["bodies"]["A001"]["internal_loads"] = {
        "channel_1": 0.60
    }
    high = _step(high_world, high_world.state, "USE:OBJ-29")
    high_delta = high.variables["developmental_history"][-1]["experienced_effects"]

    assert high_delta["energy_signal"] - low_delta["energy_signal"] == pytest.approx(0.24)
    assert high_delta["fatigue_signal"] < low_delta["fatigue_signal"]


def test_repeated_exposure_accumulates_and_combination_is_emergent():
    world = _compact_world()
    first = _step(world, world.state, "USE:OBJ-12")
    second = _step(world, first, "USE:OBJ-12")
    loads = second.variables["bodies"]["A001"]["internal_loads"]
    assert loads["channel_1"] > 0.55

    combined = _step(world, second, "USE:OBJ-29")
    combined_effect = combined.variables["developmental_history"][-1]["experienced_effects"]

    control_world = _compact_world()
    control = _step(control_world, control_world.state, "WAIT")
    control = _step(control_world, control, "WAIT")
    control = _step(control_world, control, "USE:OBJ-29")
    control_effect = control.variables["developmental_history"][-1]["experienced_effects"]

    assert combined_effect["energy_signal"] > 0.0
    assert control_effect["energy_signal"] < 0.0


def test_take_move_release_is_legal_persistent_and_invalid_take_is_inert():
    world = _compact_world(start_position=(4, 2))
    initial = world.state
    assert "TAKE:OBJ-41" in world.observe(initial, "A001").data["available_actions"]

    taken = _step(world, initial, "TAKE:OBJ-41")
    moved = _step(world, taken, "MOVE:4,3")
    assert moved.variables["world"]["objects"]["OBJ-41"]["position"] == [4, 3]
    assert "RELEASE:OBJ-41" in world.observe(moved, "A001").data["available_actions"]
    released = _step(world, moved, "RELEASE:OBJ-41")
    record = released.variables["world"]["objects"]["OBJ-41"]
    assert record["position"] == [4, 3]
    assert record["carried_by"] is None

    other = _compact_world()
    invalid = _step(other, other.state, "TAKE:OBJ-41")
    receipt = invalid.variables["developmental_history"][-1]["world_action_receipt"]
    assert receipt["valid"] is False
    assert invalid.variables["world"]["objects"]["OBJ-41"]["position"] == [4, 2]


def test_carrying_has_body_cost_and_preserves_mass_invariant():
    engine = BodyEngine()
    body = BodyState(mass_kg=70.0)
    unloaded = engine.transition(body, action=Action.wait(), carried_mass_kg=0.0)
    loaded = engine.transition(body, action=Action.wait(), carried_mass_kg=11.0)
    assert loaded.state.energy_reserve < unloaded.state.energy_reserve
    assert loaded.state.fatigue > unloaded.state.fatigue
    assert loaded.state.mass_kg == pytest.approx(unloaded.state.mass_kg)
    assert loaded.objective_effects["carried_mass_kg"] == 11.0


def test_geometry_is_local_moves_with_objects_and_composes():
    world = _compact_world(start_position=(2, 2))
    truth = world.state.variables["world"]
    both = world.world_engine.directional_exposure(truth, position=(2, 2))
    assert both["exposure_multiplier"] == pytest.approx(0.175)

    truth["objects"]["OBJ-42"]["active"] = False
    first_only = world.world_engine.directional_exposure(truth, position=(2, 2))
    assert first_only["exposure_multiplier"] == pytest.approx(0.35)
    truth["objects"]["OBJ-42"]["active"] = True

    mover = _compact_world(start_position=(4, 2))
    before = mover.world_engine.directional_exposure(
        mover.state.variables["world"], position=(2, 2)
    )
    taken = _step(mover, mover.state, "TAKE:OBJ-41")
    moved = _step(mover, taken, "MOVE:4,3")
    after = mover.world_engine.directional_exposure(
        moved.variables["world"], position=(2, 2)
    )
    assert before["exposure_multiplier"] < after["exposure_multiplier"]


def test_short_action_history_prediction_is_generic_and_keeps_alternatives():
    state = PsycheState.initial_organism_v03()
    state.memory["episodes"] = [{"action": "WAIT"}]
    state.learning["action_history_models"] = {
        "WAIT\u241fUSE:OBJ-12": {
            "count": 2,
            "mean": {"energy_signal": -0.10},
            "contexts": {},
        },
        "WAIT\u241fUSE:OBJ-29\u241fUSE:OBJ-12": {
            "count": 1,
            "mean": {"energy_signal": 0.20},
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
                "energy_signal": 0.7,
                "hydration_signal": 0.72,
                "fatigue_signal": 0.2,
                "discomfort_signal": 0.05,
                "effort_signal": 0.0,
            },
            "last_action": "USE:OBJ-29",
            "last_experienced_effects": None,
            "context": "TEST",
        }
    )
    result = PsycheRuntime(build_organism_modules()).run(
        tick=2,
        agent_id="A001",
        observation=observation,
        state=state,
        random_value=0.5,
    )
    prediction = result.state.predictions["by_action"]["USE:OBJ-12"]
    assert prediction["energy_signal"] == pytest.approx(0.20)
    assert prediction["__history_length"] == 3
    assert len(result.state.learning["action_history_models"]) == 2


def test_serialization_determinism_and_reset_contracts():
    first = Engine(
        world=ContextualObjectEcologyWorld(),
        agents={"A001": Agent(agent_id="A001")},
        seed=23,
    )
    second = Engine(
        world=ContextualObjectEcologyWorld(),
        agents={"A001": Agent(agent_id="A001")},
        seed=23,
    )
    actions = ["USE:OBJ-12", "USE:OBJ-12", "USE:OBJ-29", "WAIT"]
    for action in actions:
        first.step({"A001": Action(action)})
        second.step({"A001": Action(action)})
    assert json.dumps(first.state.world.variables, sort_keys=True) == json.dumps(
        second.state.world.variables, sort_keys=True
    )
    first.reset()
    assert first.state.world.variables == ContextualObjectEcologyWorld().state.variables


def test_agent_observation_contains_no_privileged_combination_or_geometry_truth():
    observation = ContextualObjectEcologyWorld().observe(
        ContextualObjectEcologyWorld().state, "A001"
    ).data
    serialized = json.dumps(observation).lower()
    for forbidden in (
        "recipe",
        "craft",
        "shelter",
        "building",
        "settlement",
        "contextual_body_effects",
        "directional_attenuation",
        "internal_loads",
    ):
        assert forbidden not in serialized
