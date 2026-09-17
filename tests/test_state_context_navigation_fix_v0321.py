from __future__ import annotations

from mechanistic_mind.agent import Observation
from mechanistic_mind.psyche import PsycheState
from mechanistic_mind.psyche.organism_modules import build_organism_modules
from mechanistic_mind.psyche.runtime import PsycheRuntime


def _observation(
    *,
    interoception: dict[str, float],
    available_actions: tuple[str, ...],
    visible_objects: list[dict] | None = None,
    position: tuple[int, int] = (0, 0),
    last_action: str | None = None,
    last_effects: dict[str, float] | None = None,
) -> Observation:
    return Observation(
        data={
            "position": list(position),
            "visible_objects": visible_objects or [],
            "visible_obstacles": [],
            "available_actions": available_actions,
            "interoception": interoception,
            "last_action": last_action,
            "last_experienced_effects": last_effects,
            "context": "V0321_FIX_TEST",
        }
    )


def _signals(
    energy: float,
    hydration: float,
    fatigue: float,
    discomfort: float = 0.0,
) -> dict[str, float]:
    return {
        "energy_signal": energy,
        "hydration_signal": hydration,
        "fatigue_signal": fatigue,
        "discomfort_signal": discomfort,
        "effort_signal": 0.0,
    }


def test_same_resource_is_uncertain_again_in_a_new_body_state():
    runtime = PsycheRuntime(build_organism_modules())
    state = PsycheState.initial_organism_v03()

    resource = {
        "id": "RESOURCE",
        "position": [0, 0],
        "relative_offset": [0, 0],
        "affordance": "USE",
        "cue_signature": "CUE-RESOURCE",
        "cue_salience": 0.7,
        "available_now": True,
    }

    high = _signals(0.92, 0.92, 0.06)
    first = runtime.run(
        tick=0,
        agent_id="A001",
        observation=_observation(
            interoception=high,
            available_actions=("USE:RESOURCE", "WAIT"),
            visible_objects=[resource],
        ),
        state=state,
        random_value=0.5,
    )
    assert first.action.kind == "USE:RESOURCE"

    after_high_use = runtime.run(
        tick=1,
        agent_id="A001",
        observation=_observation(
            interoception=_signals(1.0, 1.0, 0.0),
            available_actions=("WAIT",),
            visible_objects=[
                {
                    **resource,
                    "available_now": False,
                }
            ],
            last_action="USE:RESOURCE",
            last_effects={
                "energy_signal": 0.08,
                "hydration_signal": 0.08,
                "fatigue_signal": -0.06,
                "discomfort_signal": 0.0,
                "effort_signal": 0.0,
                "progress_delta": 0.0,
            },
        ),
        state=first.state,
        random_value=0.5,
    )

    low = _signals(0.12, 0.18, 0.88, 0.12)
    low_probe = runtime.run(
        tick=2,
        agent_id="A001",
        observation=_observation(
            interoception=low,
            available_actions=("USE:RESOURCE", "WAIT"),
            visible_objects=[resource],
        ),
        state=after_high_use.state,
        random_value=0.5,
    )

    prediction = low_probe.state.predictions["by_action"][
        "USE:RESOURCE"
    ]

    # The old high-state sample remains a fallback expectation...
    assert prediction["energy_signal"] == 0.08
    assert prediction["__prediction_scope"] == "GLOBAL_FALLBACK"
    # ...but this body-state/action pairing is treated as untested.
    assert prediction["__context_sample_count"] == 0
    assert (
        low_probe.state.uncertainty["by_action"]["USE:RESOURCE"]
        == 1.0
    )
    assert (
        low_probe.selection.reason
        == "CONTEXT_NOVEL_AFFORDANCE_PROBE"
    )


def test_new_body_state_gets_its_own_outcome_model():
    runtime = PsycheRuntime(build_organism_modules())
    state = PsycheState.initial_organism_v03()

    resource = {
        "id": "RESOURCE",
        "position": [0, 0],
        "relative_offset": [0, 0],
        "affordance": "USE",
        "cue_signature": "CUE-RESOURCE",
        "cue_salience": 0.7,
        "available_now": True,
    }

    # High-state exposure.
    first = runtime.run(
        tick=0,
        agent_id="A001",
        observation=_observation(
            interoception=_signals(0.92, 0.92, 0.06),
            available_actions=("USE:RESOURCE",),
            visible_objects=[resource],
        ),
        state=state,
        random_value=0.5,
    )
    learned_high = runtime.run(
        tick=1,
        agent_id="A001",
        observation=_observation(
            interoception=_signals(1.0, 1.0, 0.0),
            available_actions=("WAIT",),
            last_action="USE:RESOURCE",
            last_effects={
                "energy_signal": 0.08,
                "hydration_signal": 0.08,
                "fatigue_signal": -0.06,
                "progress_delta": 0.0,
            },
        ),
        state=first.state,
        random_value=0.5,
    )

    # Same resource used from a low-state context.
    low_probe = runtime.run(
        tick=2,
        agent_id="A001",
        observation=_observation(
            interoception=_signals(0.12, 0.18, 0.88, 0.12),
            available_actions=("USE:RESOURCE",),
            visible_objects=[resource],
        ),
        state=learned_high.state,
        random_value=0.5,
    )
    learned_low = runtime.run(
        tick=3,
        agent_id="A001",
        observation=_observation(
            interoception=_signals(0.62, 0.68, 0.45, 0.06),
            available_actions=("WAIT",),
            last_action="USE:RESOURCE",
            last_effects={
                "energy_signal": 0.50,
                "hydration_signal": 0.50,
                "fatigue_signal": -0.40,
                "discomfort_signal": -0.06,
                "progress_delta": 0.0,
            },
        ),
        state=low_probe.state,
        random_value=0.5,
    )

    again_low = runtime.run(
        tick=4,
        agent_id="A001",
        observation=_observation(
            interoception=_signals(0.10, 0.16, 0.90, 0.13),
            available_actions=("USE:RESOURCE", "WAIT"),
            visible_objects=[resource],
        ),
        state=learned_low.state,
        random_value=0.5,
    )
    prediction = again_low.state.predictions["by_action"][
        "USE:RESOURCE"
    ]

    assert prediction["__prediction_scope"] == "CONTEXT"
    assert prediction["__context_sample_count"] == 1
    assert prediction["energy_signal"] == 0.50
    assert prediction["hydration_signal"] == 0.50
    assert prediction["fatigue_signal"] == -0.40


def test_reached_goal_does_not_reward_moving_away_to_return_again():
    runtime = PsycheRuntime(build_organism_modules())
    state = PsycheState.initial_organism_v03()

    state.memory["spatial"]["visited"] = {
        "5,2": 1,
        "6,2": 3,
    }
    state.memory["spatial"]["objects"] = {
        "GOAL": {
            "position": [6, 2],
            "affordance": "USE",
            "cue_signature": "CUE-GOAL",
            "cue_salience": 0.8,
        }
    }
    state.learning["action_models"] = {
        "USE:GOAL": {
            "count": 4,
            "mean": {
                "progress_delta": 1.0,
                "energy_signal": -0.02,
                "fatigue_signal": 0.02,
            },
        },
        "MOVE:5,2": {
            "count": 3,
            "mean": {
                "energy_signal": -0.02,
                "hydration_signal": -0.01,
                "fatigue_signal": 0.02,
            },
        },
        "WAIT": {
            "count": 3,
            "mean": {
                "energy_signal": -0.008,
                "hydration_signal": -0.009,
                "fatigue_signal": 0.006,
            },
        },
    }

    result = runtime.run(
        tick=50,
        agent_id="A001",
        observation=_observation(
            interoception=_signals(0.70, 0.72, 0.20, 0.05),
            position=(6, 2),
            available_actions=(
                "MOVE:5,2",
                "USE:GOAL",
                "WAIT",
            ),
            visible_objects=[
                {
                    "id": "GOAL",
                    "position": [6, 2],
                    "relative_offset": [0, 0],
                    "affordance": "USE",
                    "cue_signature": "CUE-GOAL",
                    "cue_salience": 0.8,
                    "available_now": True,
                }
            ],
        ),
        state=state,
        random_value=0.5,
    )

    move_prediction = result.state.predictions["by_action"][
        "MOVE:5,2"
    ]
    assert move_prediction["__navigation_value"] == 0.0
    assert (
        result.state.values["by_action"]["MOVE:5,2"]["navigation"]
        == 0.0
    )
    assert result.action.kind == "USE:GOAL"


def test_physiological_urgency_does_not_amplify_progress_only_navigation():
    runtime = PsycheRuntime(build_organism_modules())
    state = PsycheState.initial_organism_v03()
    state.memory["spatial"]["visited"] = {
        "0,0": 1,
        "1,0": 1,
        "2,0": 1,
    }
    state.memory["spatial"]["objects"] = {
        "PROGRESS": {
            "position": [2, 0],
            "affordance": "USE",
            "cue_signature": "CUE-PROGRESS",
            "cue_salience": 0.8,
        }
    }
    state.learning["action_models"] = {
        "USE:PROGRESS": {
            "count": 4,
            "mean": {
                "progress_delta": 1.0,
            },
        },
        "MOVE:1,0": {
            "count": 3,
            "mean": {
                "energy_signal": -0.02,
                "hydration_signal": -0.01,
                "fatigue_signal": 0.02,
            },
        },
    }

    normal = runtime.run(
        tick=20,
        agent_id="A001",
        observation=_observation(
            interoception=_signals(0.70, 0.72, 0.20, 0.05),
            position=(0, 0),
            available_actions=("MOVE:1,0", "WAIT"),
        ),
        state=state,
        random_value=0.5,
    )
    urgent = runtime.run(
        tick=20,
        agent_id="A001",
        observation=_observation(
            interoception=_signals(0.05, 0.08, 0.95, 0.20),
            position=(0, 0),
            available_actions=("MOVE:1,0", "WAIT"),
        ),
        state=state,
        random_value=0.5,
    )

    normal_nav = normal.state.values["by_action"]["MOVE:1,0"][
        "navigation_progress"
    ]
    urgent_nav = urgent.state.values["by_action"]["MOVE:1,0"][
        "navigation_progress"
    ]

    assert normal_nav > 0.0
    assert urgent_nav < normal_nav
