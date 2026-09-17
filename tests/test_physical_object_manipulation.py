from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worlds"))

from contextual_object_ecology_v034 import (  # noqa: E402
    ContextualObjectEcologyWorld,
    ObjectManipulationAcceptanceWorld,
)
from mechanistic_mind.agent import Action, Agent  # noqa: E402
from mechanistic_mind.core import DeterministicRandom, Engine  # noqa: E402
from mechanistic_mind.mechanisms import MechanismRegistry  # noqa: E402
from mechanistic_mind.research.physical_object_demo import (  # noqa: E402
    PhysicalObjectProtocol,
)
from mechanistic_mind.ui.psychology_observer.map_view import (  # noqa: E402
    MapCamera,
    object_visual_spec,
    selection_snapshot,
)
from mechanistic_mind.ui.psychology_observer.model import (  # noqa: E402
    PsychologyTelemetryProjector,
)
from mechanistic_mind.world_engine import (  # noqa: E402
    ObjectiveObject,
    ObjectiveWorldEngine,
    WorldEngineConfig,
)
from two_choice_yield import TwoChoiceYieldWorld  # noqa: E402


def _step(world, state, action):
    return world.transition(
        state,
        {"A001": Action(action)},
        DeterministicRandom(17),
    )


def _receipt(state):
    return state.variables["developmental_history"][-1][
        "world_action_receipt"
    ]


def test_position_persists_carry_follows_and_drop_stays() -> None:
    world = ObjectManipulationAcceptanceWorld(start_position=(4, 2))
    taken = _step(world, world.state, "TAKE:OBJ-41")
    assert taken.variables["world"]["objects"]["OBJ-41"][
        "interaction_state"
    ] == "CARRIED"

    moved = _step(world, taken, "MOVE:4,3")
    carried = moved.variables["world"]["objects"]["OBJ-41"]
    assert carried["position"] == [4, 3]
    assert carried["carried_by"] == "A001"

    dropped = _step(world, moved, "RELEASE:OBJ-41")
    record = dropped.variables["world"]["objects"]["OBJ-41"]
    assert record["position"] == [4, 3]
    assert record["interaction_state"] == "DROPPED"

    waited = _step(world, dropped, "WAIT")
    assert waited.variables["world"]["objects"]["OBJ-41"]["position"] == [4, 3]


def test_push_changes_live_position_and_geometry() -> None:
    world = ObjectManipulationAcceptanceWorld(start_position=(5, 3))
    truth = world.state.variables["world"]
    before = world.world_engine.directional_exposure(truth, position=(2, 2))
    pushed = _step(world, world.state, "PUSH:OBJ-42:5,1")
    record = pushed.variables["world"]["objects"]["OBJ-42"]
    after = world.world_engine.directional_exposure(
        pushed.variables["world"], position=(2, 2)
    )
    assert record["position"] == [5, 1]
    assert record["interaction_state"] == "PUSHED"
    assert record["last_displacement"]["from"] == [5, 2]
    assert before["exposure_multiplier"] < after["exposure_multiplier"]


def test_impossible_carry_and_push_are_rejected_consistently() -> None:
    carry_world = ObjectManipulationAcceptanceWorld(start_position=(6, 4))
    carry = _step(carry_world, carry_world.state, "TAKE:OBJ-73")
    assert _receipt(carry)["valid"] is False
    assert _receipt(carry)["rejection_reason"] == "CARRY_CAPACITY_EXCEEDED"
    assert carry.variables["world"]["objects"]["OBJ-73"]["position"] == [6, 4]

    push_world = ObjectManipulationAcceptanceWorld(start_position=(5, 4))
    push = _step(push_world, push_world.state, "PUSH:OBJ-73:7,4")
    assert _receipt(push)["valid"] is False
    assert _receipt(push)["rejection_reason"] == "PUSH_CAPACITY_EXCEEDED"
    assert push.variables["world"]["objects"]["OBJ-73"]["position"] == [6, 4]


def test_push_respects_boundaries_and_blocking_geometry() -> None:
    boundary = ObjectiveWorldEngine(
        WorldEngineConfig(
            width=8,
            height=3,
            blocked=(),
            objects=(
                ObjectiveObject(
                    "EDGE", (7, 1), movable=True, mass_kg=5.0, size=1.0
                ),
            ),
        )
    )
    state = boundary.initial_state(start_position=(6, 1))
    result = boundary.transition_action(
        state,
        agent_id="A001",
        action=Action("PUSH:EDGE:8,1"),
        rng=DeterministicRandom(1),
    )
    assert result.action_receipt["rejection_reason"] == "PUSH_DESTINATION_BLOCKED"
    assert result.state["objects"]["EDGE"]["position"] == [7, 1]

    collision = ObjectiveWorldEngine(
        WorldEngineConfig(
            width=5,
            height=3,
            blocked=(),
            objects=(
                ObjectiveObject(
                    "FIRST", (2, 1), movable=True, mass_kg=5.0, size=1.0
                ),
                ObjectiveObject("SECOND", (3, 1), size=1.0),
            ),
        )
    )
    state = collision.initial_state(start_position=(1, 1))
    result = collision.transition_action(
        state,
        agent_id="A001",
        action=Action("PUSH:FIRST:3,1"),
        rng=DeterministicRandom(1),
    )
    assert result.action_receipt["rejection_reason"] == "PUSH_DESTINATION_BLOCKED"
    assert result.state["objects"]["FIRST"]["position"] == [2, 1]


def _acceptance_state(seed: int):
    registry = MechanismRegistry()
    registry.register(PhysicalObjectProtocol())
    engine = Engine(
        world=ObjectManipulationAcceptanceWorld(),
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
    )
    return engine.run(9)


def test_acceptance_protocol_is_seed_reproducible() -> None:
    first = _acceptance_state(23)
    second = _acceptance_state(23)
    assert json.dumps(first.world.variables, sort_keys=True) == json.dumps(
        second.world.variables, sort_keys=True
    )
    assert first.world.variables["world"]["objects"]["OBJ-41"]["position"] == [4, 3]
    assert first.world.variables["world"]["objects"]["OBJ-42"]["position"] == [5, 1]


def test_camera_transform_is_resolution_independent_and_invertible() -> None:
    camera = MapCamera()
    camera.fit(viewport=(900, 600), world_size=(40, 25))
    screen = camera.world_to_screen(
        (17, 9), viewport=(900, 600), world_size=(40, 25)
    )
    world = camera.screen_to_world(
        screen, viewport=(900, 600), world_size=(40, 25)
    )
    assert world == (17.0, 9.0)
    old = camera.cell_px
    camera.change_zoom(
        1.5,
        anchor=screen,
        viewport=(900, 600),
        world_size=(40, 25),
    )
    assert camera.cell_px > old
    assert camera.world_to_screen(
        (17, 9), viewport=(900, 600), world_size=(40, 25)
    ) == screen


def test_observer_visual_and_inspection_use_live_separated_state(tmp_path: Path) -> None:
    psychology = tmp_path / "psychology.jsonl"
    bridge = tmp_path / "bridge.jsonl"
    from subprocess import run

    run(
        [
            sys.executable,
            str(ROOT / "observer_launcher.py"),
            "--world", "object-manipulation",
            "--mechanism", "physical-demo",
            "--ticks", "6",
            "--jsonl", str(psychology),
            "--archon-jsonl", str(bridge),
            "--no-signals",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    projector = PsychologyTelemetryProjector()
    for line in psychology.read_text(encoding="utf-8").splitlines():
        projector.apply(json.loads(line))
    tick = projector.view.latest
    assert tick is not None
    record = tick.world_objects["OBJ-42"]
    visual = object_visual_spec(record)
    assert visual["shape"] == "square"
    assert visual["interaction_state"] == "PUSHED"
    snapshot = selection_snapshot(tick, "object", "OBJ-42")
    assert snapshot["objective"]["position"] == [5, 1]
    assert "hidden_role" not in snapshot["objective"]
    assert set(snapshot) == {"entity", "objective", "perceived", "learned"}


def test_legacy_world_without_physical_objects_still_runs() -> None:
    engine = Engine(
        world=TwoChoiceYieldWorld(),
        agents={"A001": Agent(agent_id="A001")},
        seed=7,
    )
    assert engine.run(3).tick == 3
