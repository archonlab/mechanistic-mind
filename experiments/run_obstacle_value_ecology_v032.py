from __future__ import annotations

from collections import Counter
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Agent, Observation
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import PsycheState, SingleOrganismPsycheV03
from mechanistic_mind.psyche.organism_modules import build_organism_modules
from mechanistic_mind.psyche.runtime import PsycheRuntime
from obstacle_value_world_v032 import (
    HAZARD_CUE,
    VALUE_CUE,
    ObstacleValueWorld,
)


def _runtime() -> PsycheRuntime:
    return PsycheRuntime(build_organism_modules())


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
            "mean": {"progress_delta": 1.0},
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
            "context": "ROUTE_DIAGNOSTIC",
        }
    )
    return state, observation


def route_choice_diagnostic() -> dict:
    rows = {}
    for label, hazard in (
        ("SAME_ROUTE_SAFE_HISTORY", False),
        ("SAME_ROUTE_HARMFUL_HISTORY", True),
    ):
        state, observation = _route_state(hazard=hazard)
        result = _runtime().run(
            tick=20,
            agent_id="A001",
            observation=observation,
            state=state,
            random_value=0.5,
        )
        values = result.state.values["by_action"]
        rows[label] = {
            "selected_action": result.action.kind,
            "selection_reason": result.selection.reason,
            "direct_value": values["MOVE:3,2"]["base_total"],
            "detour_value": values["MOVE:2,1"]["base_total"],
            "direct_prediction": result.state.predictions[
                "by_action"
            ]["MOVE:3,2"],
            "detour_prediction": result.state.predictions[
                "by_action"
            ]["MOVE:2,1"],
        }
    return rows


def cue_navigation_diagnostic() -> dict:
    rows = {}
    for label, with_cue in (
        ("NO_LEARNED_CUE_VALUE", False),
        ("LEARNED_CUE_VALUE", True),
    ):
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
        if with_cue:
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
                "context": "CUE_NAVIGATION_DIAGNOSTIC",
            }
        )

        result = _runtime().run(
            tick=35,
            agent_id="A001",
            observation=observation,
            state=state,
            random_value=0.5,
        )
        rows[label] = {
            "selected_action": result.action.kind,
            "selection_reason": result.selection.reason,
            "move_to_decoy_prediction": result.state.predictions[
                "by_action"
            ]["MOVE:5,0"],
            "move_to_decoy_value": result.state.values[
                "by_action"
            ]["MOVE:5,0"],
        }
    return rows


def free_life(condition: str, ticks: int = 70) -> dict:
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    engine = Engine(
        world=ObstacleValueWorld(condition=condition),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
    )

    obstacle_contact_days = []
    use_actions = []
    first_decoy_navigation = None
    first_decoy_use = None

    for _ in range(ticks):
        result = engine.step()
        action = result.actions["A001"].kind
        variables = result.state_after.world.variables
        body = variables["bodies"]["A001"]
        history = variables["developmental_history"][-1]
        receipt = history["world_action_receipt"]

        if receipt.get("obstacle_contact"):
            obstacle_contact_days.append(body["life_day"])

        if action.startswith("USE:"):
            use_actions.append(action)

        whole = result.signals["A001"][
            "PSYCHE-SINGLE-ORGANISM-V03"
        ]["whole_psyche"]
        selected_prediction = whole["predictions"][
            "by_action"
        ].get(action, {})

        if (
            first_decoy_navigation is None
            and selected_prediction.get("__navigation_target")
            == "GOAL-DECOY"
        ):
            first_decoy_navigation = {
                "life_day": body["life_day"],
                "action": action,
                "selection_reason": whole["selection"]["reason"],
                "navigation_value": selected_prediction.get(
                    "__navigation_value"
                ),
            }

        if action == "USE:GOAL-DECOY" and first_decoy_use is None:
            first_decoy_use = {
                "life_day": body["life_day"],
                "prediction_source": selected_prediction.get(
                    "__prediction_source"
                ),
                "predicted_progress": selected_prediction.get(
                    "progress_delta"
                ),
                "actual_progress": history[
                    "experienced_effects"
                ].get("progress_delta"),
                "selection_reason": whole["selection"]["reason"],
            }

    world = engine.state.world.variables["world"]
    body = engine.state.world.variables["bodies"]["A001"]
    psyche = engine.state.agents["A001"].mechanism_states[
        "PSYCHE-SINGLE-ORGANISM-V03"
    ]["psyche"]

    return {
        "condition": condition,
        "ticks_days": ticks,
        "progress": world["total_progress"],
        "damage": body["damage"],
        "obstacle_contact_days": obstacle_contact_days,
        "uses": dict(Counter(use_actions)),
        "known_objects": sorted(
            psyche["memory"]["spatial"]["objects"]
        ),
        "known_obstacles": sorted(
            psyche["memory"]["spatial"]["obstacles"]
        ),
        "obstacle_cue_model": psyche["learning"][
            "obstacle_cue_models"
        ].get(HAZARD_CUE),
        "value_cue_model": psyche["learning"][
            "object_cue_models"
        ].get(VALUE_CUE),
        "decoy_direct_model": psyche["learning"][
            "action_models"
        ].get("USE:GOAL-DECOY"),
        "first_decoy_navigation": first_decoy_navigation,
        "first_decoy_use": first_decoy_use,
    }


def main() -> None:
    result = {
        "experiment": "OBSTACLE_LEARNING_VALUE_ECOLOGY_V032",
        "version": "0.3.2",
        "route_choice_diagnostic": route_choice_diagnostic(),
        "cue_navigation_diagnostic": cue_navigation_diagnostic(),
        "free_life": {
            "HAZARD": free_life("HAZARD"),
            "SHAM_CUE": free_life("SHAM_CUE"),
        },
        "interpretation": {
            "observation": (
                "With the same known goal/map, changing only the learned "
                "consequence of the direct obstacle cell can switch route "
                "selection from direct to detour. A learned value cue can also "
                "change exploration direction toward a novel look-alike."
            ),
            "integrated_free_life": (
                "The free-life run demonstrates real cue transfer to the "
                "spawned decoy and correction after direct experience. "
                "Obstacle contact counts in a short unconstrained run should "
                "not be interpreted as a complete avoidance phenotype."
            ),
            "not_claimed": (
                "No fear, avoidance trait, personality, perseverance, or "
                "human psychological mechanism is established by these toy "
                "diagnostics."
            ),
        },
    }

    output = (
        ROOT
        / "experiments/obstacle_value_ecology_v032_result.json"
    )
    output.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
