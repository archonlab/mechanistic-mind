from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worlds"))

from contextual_object_ecology_v034 import (  # noqa: E402
    ContextualObjectEcologyWorld,
    default_contextual_object_config,
    physical_protocol_object_config,
)
from mechanistic_mind.agent import Action, Agent  # noqa: E402
from mechanistic_mind.core import DeterministicRandom, Engine  # noqa: E402
from mechanistic_mind.observer import JSONLSink, PsychologyObserver  # noqa: E402
from mechanistic_mind.ui.psychology_observer.model import (  # noqa: E402
    PsychologyTelemetryProjector,
)
from mechanistic_mind.ui.psychology_observer.map_view import (  # noqa: E402
    quantity_fraction,
)
from mechanistic_mind.world_engine import (  # noqa: E402
    ObjectiveObject,
    ObjectiveWorldEngine,
    WorldEngineConfig,
)
from two_choice_yield import TwoChoiceYieldWorld  # noqa: E402


def _transition(engine, state, action="WAIT"):
    return engine.transition_action(
        state,
        agent_id="A001",
        action=Action(action),
        rng=DeterministicRandom(17),
        body_context={},
    )


def test_large_contextual_world_runs_and_has_distributed_objects() -> None:
    config = default_contextual_object_config(17)
    assert (config.width, config.height) == (32, 32)
    assert len(config.objects) == 30
    positions = [item.position for item in config.objects]
    assert len(set(positions)) == len(positions)

    start = (15, 16)
    distances = [abs(x - start[0]) + abs(y - start[1]) for x, y in positions]
    assert min(distances) == 0
    assert max(distances) >= 20
    assert any(distance <= 4 for distance in distances)
    assert any(8 <= distance <= 16 for distance in distances)
    quadrants = {(x < 16, y < 16) for x, y in positions}
    assert len(quadrants) == 4

    world = ContextualObjectEcologyWorld(world_config=config)
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
    )
    assert engine.run(3).tick == 3


def test_ecology_placement_is_seeded_and_properties_are_heterogeneous() -> None:
    first = default_contextual_object_config(17)
    replay = default_contextual_object_config(17)
    other = default_contextual_object_config(18)
    signature = lambda config: [item.to_record() for item in config.objects]
    assert signature(first) == signature(replay)
    assert signature(first) != signature(other)

    records = signature(first)
    assert len({item["shape"] for item in records}) >= 5
    assert len({item["mass_kg"] for item in records}) >= 10
    assert len({item["friction"] for item in records}) >= 10
    assert any(item["interaction_state_deltas"] for item in records)
    assert any(item["regeneration_rates"] for item in records)
    assert any(not item["interaction_state_deltas"] for item in records)
    assert any(item["directional_attenuation"] > 0 for item in records)


def test_finite_quantity_depletes_and_exhaustion_removes_effect() -> None:
    engine = ObjectiveWorldEngine(
        WorldEngineConfig(
            width=3,
            height=3,
            blocked=(),
            objects=(
                ObjectiveObject(
                    "OBJ-FINITE",
                    (1, 1),
                    quantity=0.25,
                    max_quantity=0.25,
                    interaction_state_deltas={"quantity": -0.10},
                    minimum_effect_state={"quantity": 1e-9},
                    effect_scale_state="quantity",
                    body_effects={"energy_delta": 0.30},
                ),
            ),
        )
    )
    state = engine.initial_state(start_position=(1, 1))
    outcomes = []
    quantities = []
    receipts = []
    for _ in range(4):
        result = _transition(engine, state, "USE:OBJ-FINITE")
        state = result.state
        outcomes.append(result.external_body_effects.get("energy_delta", 0.0))
        quantities.append(state["objects"]["OBJ-FINITE"]["quantity"])
        receipts.append(result.action_receipt)

    assert quantities == pytest.approx([0.15, 0.05, 0.0, 0.0])
    assert outcomes == pytest.approx([0.30, 0.30, 0.15, 0.0])
    assert receipts[-1]["effect_available"] is False
    assert receipts[-1]["object_state_before"]["quantity"] == 0.0
    assert receipts[-1]["object_state_after"]["quantity"] == 0.0
    assert state["objects"]["OBJ-FINITE"]["active"] is True


def test_reusable_object_does_not_deplete() -> None:
    engine = ObjectiveWorldEngine(
        WorldEngineConfig(
            width=2,
            height=2,
            blocked=(),
            objects=(
                ObjectiveObject(
                    "OBJ-REUSABLE",
                    (0, 0),
                    quantity=0.7,
                    max_quantity=0.7,
                    body_effects={"hydration_delta": 0.04},
                ),
            ),
        )
    )
    state = engine.initial_state(start_position=(0, 0))
    for _ in range(8):
        result = _transition(engine, state, "USE:OBJ-REUSABLE")
        state = result.state
        assert result.external_body_effects["hydration_delta"] == 0.04
    assert state["objects"]["OBJ-REUSABLE"]["quantity"] == 0.7


def test_regeneration_is_deterministic_bounded_and_persistent() -> None:
    config = WorldEngineConfig(
        width=2,
        height=2,
        blocked=(),
        objects=(
            ObjectiveObject(
                "OBJ-REGEN",
                (0, 0),
                quantity=0.2,
                max_quantity=0.5,
                regeneration_rates={"quantity": 0.1},
            ),
        ),
    )
    engine = ObjectiveWorldEngine(config)
    first = engine.initial_state(start_position=(1, 1))
    replay = engine.initial_state(start_position=(1, 1))
    observed = []
    for _ in range(5):
        a = _transition(engine, first)
        b = _transition(engine, replay)
        first, replay = a.state, b.state
        assert first == replay
        observed.append(first["objects"]["OBJ-REGEN"]["quantity"])
    assert observed == pytest.approx([0.3, 0.4, 0.5, 0.5, 0.5])


def test_movement_and_carry_preserve_mutable_object_state() -> None:
    world = ContextualObjectEcologyWorld(
        world_config=physical_protocol_object_config(),
        start_position=(2, 3),
    )
    first = world.transition(
        world.state,
        {"A001": Action("USE:OBJ-12")},
        DeterministicRandom(17),
    )
    quantity = first.variables["world"]["objects"]["OBJ-12"]["quantity"]

    # Move a stateful carryable clone using the same objective runtime.
    engine = ObjectiveWorldEngine(
        WorldEngineConfig(
            width=4,
            height=4,
            blocked=(),
            objects=(
                ObjectiveObject(
                    "OBJ-MOVE",
                    (1, 1),
                    movable=True,
                    mass_kg=2.0,
                    size=0.4,
                    quantity=quantity,
                    max_quantity=1.0,
                    interaction_state_deltas={"quantity": -0.1},
                ),
            ),
        )
    )
    state = engine.initial_state(start_position=(1, 1))
    state = _transition(engine, state, "TAKE:OBJ-MOVE").state
    state = _transition(engine, state, "MOVE:1,2").state
    record = state["objects"]["OBJ-MOVE"]
    assert record["position"] == [1, 2]
    assert record["quantity"] == quantity
    assert record["mutable_state"]["quantity"] == quantity


def test_observer_projects_current_state_without_agent_truth_leak(tmp_path: Path) -> None:
    path = tmp_path / "observer.jsonl"
    world = ContextualObjectEcologyWorld(
        world_config=physical_protocol_object_config(),
        start_position=(2, 3),
    )
    observer = PsychologyObserver(JSONLSink(path))
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        observer=observer,
    )
    engine.step({"A001": Action("USE:OBJ-29")})
    engine.close()

    projector = PsychologyTelemetryProjector()
    for line in path.read_text(encoding="utf-8").splitlines():
        projector.apply(json.loads(line))
    tick = projector.view.latest
    assert tick is not None
    assert tick.world_objects["OBJ-29"]["quantity"] == pytest.approx(0.88)
    assert quantity_fraction(tick.world_objects["OBJ-29"]) == pytest.approx(0.88)
    receipt = tick.world_action_receipt
    assert receipt["object_state_before"]["quantity"] == 1.0
    assert receipt["object_state_after"]["quantity"] == pytest.approx(0.88)
    assert "agent_body_context_before" in receipt

    visible = next(
        item for item in tick.observation["visible_objects"]
        if item["id"] == "OBJ-29"
    )
    forbidden = {
        "quantity",
        "max_quantity",
        "mutable_state",
        "regeneration_rates",
        "body_effects",
        "contextual_body_effects",
        "minimum_effect_state",
    }
    assert forbidden.isdisjoint(visible)
    assert visible["observable_state"] == {}


def test_old_world_contract_remains_compatible() -> None:
    engine = Engine(
        world=TwoChoiceYieldWorld(),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
    )
    assert engine.run(5).tick == 5
