from __future__ import annotations

import sys
from pathlib import Path

from mechanistic_mind.agent import Action, Agent, Observation
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import PsycheState, SingleOrganismPsycheV03
from mechanistic_mind.psyche.organism_modules import build_organism_modules
from mechanistic_mind.psyche.runtime import PsycheRuntime

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "worlds"))
from obstacle_value_world_v032 import (
    HAZARD_CUE,
    VALUE_CUE,
    ObstacleValueWorld,
    obstacle_value_world_config,
)


def _engine(condition: str = "HAZARD") -> Engine:
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    return Engine(
        world=ObstacleValueWorld(condition=condition),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
    )


def _route_state(*, hazard: bool) -> tuple[PsycheState, Observation]:
    state = PsycheState.initial_organism_v03()

    state.memory["spatial"]["objects"] = {
        "GOAL": {
            "position": [6, 2],
            "cue_signature": "CUE-GOAL",
            "affordance": "USE",
        }
    }
    state.memory["spatial"]["obstacles"] = {
        "OBS": {
            "position": [3, 2],
            "cue_signature": HAZARD_CUE,
            "traversable": True,
        }
    }

    # The agent has already discovered both the direct corridor and a safe
    # detour. This isolates route choice from route discovery.
    for position in (
        (2, 2),
        (2, 1),
        (3, 1),
        (4, 1),
        (5, 1),
        (6, 1),
        (6, 2),
        (3, 2),
        (4, 2),
        (5, 2),
    ):
        state.memory["spatial"]["visited"][
            f"{position[0]},{position[1]}"
        ] = 1

    normal = {
        "energy_signal": -0.02,
        "hydration_signal": -0.01,
        "fatigue_signal": 0.02,
        "discomfort_signal": 0.0,
        "effort_signal": 0.03,
    }
    harmful = {
        "energy_signal": -0.09,
        "hydration_signal": -0.05,
        "fatigue_signal": 0.10,
        "discomfort_signal": 0.05,
        "effort_signal": 0.08,
    }

    state.learning["action_models"] = {
        "USE:GOAL": {
            "count": 5,
            "mean": {
                "progress_delta": 1.0,
            },
        },
        "WAIT": {
            "count": 3,
            "mean": {
                "energy_signal": -0.01,
                "hydration_signal": -0.01,
                "fatigue_signal": 0.01,
            },
        },
    }
    for position in (
        (2, 1),
        (3, 1),
        (4, 1),
        (5, 1),
        (6, 1),
        (6, 2),
        (3, 2),
        (4, 2),
        (5, 2),
    ):
        state.learning["action_models"][
            f"MOVE:{position[0]},{position[1]}"
        ] = {
            "count": 3,
            "mean": (
                harmful
                if position == (3, 2) and hazard
                else normal
            ),
        }

    observation = Observation(
        data={
            "position": [2, 2],
            "visible_objects": [],
            "visible_obstacles": [
                {
                    "id": "OBS",
                    "position": [3, 2],
                    "relative_offset": [1, 0],
                    "cue_signature": HAZARD_CUE,
                    "cue_salience": 0.85,
                    "traversable": True,
                }
            ],
            "available_actions": (
                "MOVE:2,1",
                "MOVE:3,2",
                "WAIT",
            ),
            "interoception": {
                "energy_signal": 0.70,
                "hydration_signal": 0.72,
                "fatigue_signal": 0.20,
                "discomfort_signal": 0.05,
                "effort_signal": 0.0,
            },
            "last_action": None,
            "last_experienced_effects": None,
            "context": "OBSTACLE_ROUTE_TEST",
        }
    )
    return state, observation


def test_obstacle_truth_is_hidden_from_agent_observation():
    world = ObstacleValueWorld(condition="HAZARD")
    observation = world.observe(world.state, "A001").data

    assert "visible_obstacles" in observation
    serialized = str(observation)
    assert "damage_delta" not in serialized
    assert "body_effects" not in serialized
    assert "contact_probability" not in serialized
    assert "hidden_role" not in serialized


def test_first_contact_can_physically_hurt_without_avoidance_label():
    engine = _engine("HAZARD")

    # External actions are an experimental intervention ensuring a clean
    # first exposure history.
    for action in (
        "MOVE:1,2",
        "MOVE:2,2",
        "MOVE:3,2",
    ):
        result = engine.step(
            actions={"A001": Action(action)}
        )

    variables = result.state_after.world.variables
    body = variables["bodies"]["A001"]
    receipt = variables["developmental_history"][-1][
        "world_action_receipt"
    ]

    assert receipt["obstacle_id"] == "OBS-ROUGH-1"
    assert receipt["obstacle_effect_applied"] is True
    assert body["damage"] > 0.0

    # No psychological avoidance/fear variable was inserted.
    psyche = result.state_after.agents["A001"].mechanism_states[
        "PSYCHE-SINGLE-ORGANISM-V03"
    ]["psyche"]
    serialized = str(psyche).lower()
    assert "avoidance" not in serialized
    assert "fear" not in serialized


def test_hazard_cue_is_learned_from_experienced_consequences():
    engine = _engine("HAZARD")
    for action in (
        "MOVE:1,2",
        "MOVE:2,2",
        "MOVE:3,2",
        "WAIT",
    ):
        result = engine.step(
            actions={"A001": Action(action)}
        )

    psyche = result.state_after.agents["A001"].mechanism_states[
        "PSYCHE-SINGLE-ORGANISM-V03"
    ]["psyche"]
    model = psyche["learning"]["obstacle_cue_models"][HAZARD_CUE]

    assert model["count"] >= 1
    assert model["mean"]["discomfort_signal"] > 0.0
    assert model["mean"]["fatigue_signal"] > 0.0


def test_known_harmful_short_route_can_be_replaced_by_safe_detour():
    runtime = PsycheRuntime(build_organism_modules())

    safe_state, observation = _route_state(hazard=False)
    safe = runtime.run(
        tick=20,
        agent_id="A001",
        observation=observation,
        state=safe_state,
        random_value=0.5,
    )
    assert safe.action.kind == "MOVE:3,2"

    hazard_state, observation = _route_state(hazard=True)
    hazard = runtime.run(
        tick=20,
        agent_id="A001",
        observation=observation,
        state=hazard_state,
        random_value=0.5,
    )

    # Same goal, same map, same basic psyche. Only learned consequence of
    # the direct cell differs.
    assert hazard.action.kind == "MOVE:2,1"
    assert (
        hazard.state.values["by_action"]["MOVE:3,2"]["base_total"]
        <
        hazard.state.values["by_action"]["MOVE:2,1"]["base_total"]
    )


def test_sham_visual_cue_does_not_create_damage_by_itself():
    engine = _engine("SHAM_CUE")
    for action in (
        "MOVE:1,2",
        "MOVE:2,2",
        "MOVE:3,2",
    ):
        result = engine.step(
            actions={"A001": Action(action)}
        )

    body = result.state_after.world.variables["bodies"]["A001"]
    assert body["damage"] == 0.0


def test_object_cue_can_make_novel_decoy_look_valuable_before_direct_experience():
    state = PsycheState.initial_organism_v03()
    state.learning["object_cue_models"][VALUE_CUE] = {
        "count": 4,
        "mean": {
            "progress_delta": 0.55,
            "energy_signal": -0.008,
            "fatigue_signal": 0.006,
        },
    }

    observation = Observation(
        data={
            "position": [5, 0],
            "visible_objects": [
                {
                    "id": "GOAL-DECOY",
                    "position": [5, 0],
                    "relative_offset": [0, 0],
                    "affordance": "USE",
                    "cue_signature": VALUE_CUE,
                    "cue_salience": 0.90,
                    "available_now": True,
                }
            ],
            "visible_obstacles": [],
            "available_actions": (
                "USE:GOAL-DECOY",
                "WAIT",
            ),
            "interoception": {
                "energy_signal": 0.70,
                "hydration_signal": 0.72,
                "fatigue_signal": 0.20,
                "discomfort_signal": 0.05,
                "effort_signal": 0.0,
            },
            "last_action": None,
            "last_experienced_effects": None,
            "context": "VALUE_CUE_TEST",
        }
    )

    result = PsycheRuntime(build_organism_modules()).run(
        tick=40,
        agent_id="A001",
        observation=observation,
        state=state,
        random_value=0.5,
    )

    prediction = result.state.predictions["by_action"][
        "USE:GOAL-DECOY"
    ]
    assert prediction["progress_delta"] == 0.55
    assert prediction["__prediction_source"] == (
        f"OBJECT_CUE:{VALUE_CUE}"
    )
    assert result.action.kind == "USE:GOAL-DECOY"


def test_direct_decoy_experience_overrides_generalized_cue_expectation():
    state = PsycheState.initial_organism_v03()
    state.learning["object_cue_models"][VALUE_CUE] = {
        "count": 5,
        "mean": {
            "progress_delta": 0.55,
        },
    }
    state.learning["action_models"]["USE:GOAL-DECOY"] = {
        "count": 1,
        "mean": {
            "progress_delta": 0.0,
            "energy_signal": -0.01,
            "fatigue_signal": 0.01,
        },
    }

    observation = Observation(
        data={
            "position": [5, 0],
            "visible_objects": [
                {
                    "id": "GOAL-DECOY",
                    "position": [5, 0],
                    "relative_offset": [0, 0],
                    "affordance": "USE",
                    "cue_signature": VALUE_CUE,
                    "cue_salience": 0.90,
                    "available_now": True,
                }
            ],
            "visible_obstacles": [],
            "available_actions": (
                "USE:GOAL-DECOY",
                "WAIT",
            ),
            "interoception": {
                "energy_signal": 0.70,
                "hydration_signal": 0.72,
                "fatigue_signal": 0.20,
                "discomfort_signal": 0.05,
                "effort_signal": 0.0,
            },
            "last_action": None,
            "last_experienced_effects": None,
            "context": "VALUE_CUE_CORRECTION_TEST",
        }
    )

    result = PsycheRuntime(build_organism_modules()).run(
        tick=41,
        agent_id="A001",
        observation=observation,
        state=state,
        random_value=0.5,
    )

    prediction = result.state.predictions["by_action"][
        "USE:GOAL-DECOY"
    ]
    assert prediction["progress_delta"] == 0.0
    assert prediction["__prediction_source"] == "ACTION_MODEL"


def test_value_ecology_has_temporal_access_cost_not_infinite_buttons():
    config = obstacle_value_world_config(condition="HAZARD")
    records = {
        item.object_id: item
        for item in config.objects
    }

    assert records["GOAL-TRAIN"].cooldown_ticks > 0
    assert records["GOAL-FAR"].cooldown_ticks > 0
    assert records["GOAL-SMALL"].cooldown_ticks > 0


def test_decoy_is_added_exogenously_after_value_cue_can_be_learned():
    config = obstacle_value_world_config(condition="HAZARD")
    assert "GOAL-DECOY" not in {
        item.object_id for item in config.objects
    }
    spawn = [
        event
        for event in config.exogenous_events
        if event.event_id == "SPAWN-VALUE-DECOY"
    ]
    assert len(spawn) == 1
    assert spawn[0].effective_tick == 30
    payload = spawn[0].parameters["object"]
    assert payload["cue_signature"] == VALUE_CUE
    assert payload["world_effects"]["progress_delta"] == 0.0


def test_removed_obstacle_disappears_from_perception_but_can_remain_in_memory():
    engine = _engine("REMOVAL")

    # Learn/remember the obstacle before its scheduled removal.
    for action in (
        "MOVE:1,2",
        "MOVE:2,2",
        "MOVE:3,2",
        "MOVE:2,2",
    ):
        result = engine.step(
            actions={"A001": Action(action)}
        )

    psyche = result.state_after.agents["A001"].mechanism_states[
        "PSYCHE-SINGLE-ORGANISM-V03"
    ]["psyche"]
    assert "OBS-ROUGH-1" in psyche["memory"]["spatial"]["obstacles"]

    # Advance world time to the observer-only removal event.
    while engine.clock.tick < 45:
        result = engine.step(
            actions={"A001": Action("WAIT")}
        )

    observation = engine.world.observe(
        result.state_after.world,
        "A001",
    ).data
    assert all(
        item["id"] != "OBS-ROUGH-1"
        for item in observation["visible_obstacles"]
    )

    psyche = result.state_after.agents["A001"].mechanism_states[
        "PSYCHE-SINGLE-ORGANISM-V03"
    ]["psyche"]
    assert "OBS-ROUGH-1" in psyche["memory"]["spatial"]["obstacles"]


def test_cooldown_removes_use_affordance_temporarily_without_erasing_object():
    world = ObstacleValueWorld(condition="HAZARD")
    engine = _engine("HAZARD")

    # HOME is available at t=0.
    first = engine.step(
        actions={"A001": Action("USE:HOME-RESOURCE")}
    )
    observation = world.observe(
        first.state_after.world,
        "A001",
    ).data

    visible_home = [
        item
        for item in observation["visible_objects"]
        if item["id"] == "HOME-RESOURCE"
    ]
    assert visible_home
    assert visible_home[0]["available_now"] is False
    assert "USE:HOME-RESOURCE" not in observation["available_actions"]


def test_learned_value_cue_can_guide_exploration_toward_novel_lookalike():
    def choose(with_cue_model: bool) -> str:
        state = PsycheState.initial_organism_v03()
        state.memory["spatial"]["objects"] = {
            "GOAL-DECOY": {
                "position": [5, 0],
                "affordance": "USE",
                "cue_signature": VALUE_CUE,
                "cue_salience": 0.90,
            }
        }
        state.memory["spatial"]["visited"] = {
            "4,0": 1,
        }
        if with_cue_model:
            state.learning["object_cue_models"][VALUE_CUE] = {
                "count": 4,
                "mean": {
                    "progress_delta": 0.55,
                    "energy_signal": -0.008,
                    "fatigue_signal": 0.006,
                },
            }

        observation = Observation(
            data={
                "position": [4, 0],
                "visible_objects": [
                    {
                        "id": "GOAL-DECOY",
                        "position": [5, 0],
                        "relative_offset": [1, 0],
                        "affordance": "USE",
                        "cue_signature": VALUE_CUE,
                        "cue_salience": 0.90,
                        "available_now": True,
                    }
                ],
                "visible_obstacles": [],
                "available_actions": (
                    "MOVE:4,1",
                    "MOVE:5,0",
                    "WAIT",
                ),
                "interoception": {
                    "energy_signal": 0.70,
                    "hydration_signal": 0.72,
                    "fatigue_signal": 0.20,
                    "discomfort_signal": 0.05,
                    "effort_signal": 0.0,
                },
                "last_action": None,
                "last_experienced_effects": None,
                "context": "VALUE_CUE_NAVIGATION_TEST",
            }
        )

        result = PsycheRuntime(build_organism_modules()).run(
            tick=35,
            agent_id="A001",
            observation=observation,
            state=state,
            random_value=0.5,
        )
        return result.action.kind

    assert choose(with_cue_model=False) == "MOVE:4,1"
    assert choose(with_cue_model=True) == "MOVE:5,0"
