from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action, Agent
from mechanistic_mind.core import DeterministicRandom, Engine
from mechanistic_mind.world_engine import (
    ObjectiveObject,
    ObjectiveWorldEngine,
    WorldEngineConfig,
    observation_contains_forbidden,
)
from object_existence_dynamics_v04 import (
    ObjectExistenceDynamicsWorld,
    random_relocation_config,
    route_relocation_config,
    scientific_acceptance_config,
    static_object_config,
)


def _engine(config: WorldEngineConfig) -> tuple[ObjectiveWorldEngine, dict]:
    world = ObjectiveWorldEngine(config)
    return world, world.initial_state(start_position=(1, 1))


def _step(world: ObjectiveWorldEngine, state: dict, action: str, seed: int = 17):
    return world.transition_action(
        state,
        agent_id="A001",
        action=Action(action),
        rng=DeterministicRandom(seed),
        body_context={},
    )


def _use_here(world: ObjectiveWorldEngine, state: dict, object_id: str = "OBJ-A"):
    record = state["objects"][object_id]
    target = record.get("position")
    if isinstance(target, list) and len(target) == 2:
        agent = list(state["agent_positions"]["A001"])
        while agent != target:
            nx = agent[0] + (0 if agent[0] == target[0] else (1 if target[0] > agent[0] else -1))
            ny = agent[1] if nx != agent[0] else agent[1] + (
                0 if agent[1] == target[1] else (1 if target[1] > agent[1] else -1)
            )
            state = _step(world, state, f"MOVE:{nx},{ny}").state
            agent = list(state["agent_positions"]["A001"])
    return _step(world, state, f"USE:{object_id}")


def _region_of(record: dict) -> str | None:
    existence = record.get("existence") or {}
    return existence.get("region_id")


def test_static_objects_preserve_existing_depletion_behavior() -> None:
    world, state = _engine(static_object_config())
    first = _step(world, state, "USE:OBJ-A")
    assert first.action_receipt["valid"] is True
    assert first.state["objects"]["OBJ-A"]["active"] is True
    second = _step(world, first.state, "USE:OBJ-A")
    record = second.state["objects"]["OBJ-A"]
    assert record["active"] is False
    assert record["existence"]["present"] is False
    assert record["existence"]["mode"] == "STATIC"
    third = _step(world, second.state, "USE:OBJ-A")
    assert third.action_receipt["valid"] is False


def test_effects_are_independent_of_existence_mode() -> None:
    static = static_object_config().objects[0].body_effects
    route = route_relocation_config().objects[0].body_effects
    random = random_relocation_config().objects[0].body_effects
    assert static == route == random
    assert static["energy_delta"] == 0.20


def test_finite_capacity_depletes_after_configured_uses() -> None:
    world, state = _engine(route_relocation_config())
    first = _step(world, state, "USE:OBJ-A")
    assert first.state["objects"]["OBJ-A"]["use_count"] == 1
    assert first.state["objects"]["OBJ-A"]["existence"]["present"] is True
    second = _step(world, first.state, "USE:OBJ-A")
    assert second.state["objects"]["OBJ-A"]["existence"]["present"] is False


def test_random_relocation_leaves_and_reappears_in_allowed_cells() -> None:
    world, state = _engine(random_relocation_config())
    depleted = _step(world, _step(world, state, "USE:OBJ-A").state, "USE:OBJ-A")
    record = depleted.state["objects"]["OBJ-A"]
    assert record["existence"]["present"] is False
    assert record["position"] is None
    allowed = {(1, 1), (3, 1), (5, 1), (7, 1)}
    current = depleted.state
    appeared = None
    for _ in range(6):
        current = _step(world, current, "WAIT").state
        record = current["objects"]["OBJ-A"]
        if record["existence"]["present"]:
            appeared = record
            break
    assert appeared is not None
    assert tuple(appeared["position"]) in allowed
    assert appeared["use_count"] == 0


def test_route_follows_configured_order_and_cycles() -> None:
    world, state = _engine(route_relocation_config())
    current = state
    regions = []
    for _expected in ("A", "B", "C", "A"):
        record = current["objects"]["OBJ-A"]
        assert record["existence"]["present"] is True
        regions.append(_region_of(record))
        current = _use_here(world, current).state
        current = _use_here(world, current).state
        assert current["objects"]["OBJ-A"]["existence"]["present"] is False
        for _ in range(3):
            current = _step(world, current, "WAIT").state
            if current["objects"]["OBJ-A"]["existence"]["present"]:
                break
    assert regions == ["A", "B", "C", "A"]


def test_non_cyclic_route_terminates_after_last_region() -> None:
    world, state = _engine(route_relocation_config(cycle=False))
    current = state
    for _ in range(3):
        current = _use_here(world, current).state
        current = _use_here(world, current).state
        for _ in range(4):
            current = _step(world, current, "WAIT").state
            if current["objects"]["OBJ-A"]["existence"]["present"]:
                break
    record = current["objects"]["OBJ-A"]
    assert record["existence"]["present"] is False
    assert record["existence"].get("route_complete") is True
    assert record["existence"]["scheduled_reappear_tick"] is None


def test_transition_delay_creates_absent_interval() -> None:
    world, state = _engine(route_relocation_config())
    current = _step(world, _step(world, state, "USE:OBJ-A").state, "USE:OBJ-A").state
    assert current["objects"]["OBJ-A"]["existence"]["present"] is False
    mid = _step(world, current, "WAIT").state
    assert mid["objects"]["OBJ-A"]["existence"]["present"] is False
    obs = world.local_observation(mid, agent_id="A001")
    assert obs["visible_objects"] == []
    assert "USE:OBJ-A" not in obs["available_actions"]


def test_capacity_resets_on_new_appearance() -> None:
    world, state = _engine(route_relocation_config())
    current = _step(world, _step(world, state, "USE:OBJ-A").state, "USE:OBJ-A").state
    for _ in range(4):
        current = _step(world, current, "WAIT").state
        if current["objects"]["OBJ-A"]["existence"]["present"]:
            break
    record = current["objects"]["OBJ-A"]
    assert record["existence"]["present"] is True
    assert record["use_count"] == 0
    used = _use_here(world, current)
    assert used.action_receipt["valid"] is True


def test_same_seed_replays_relocation_history() -> None:
    def history(seed: int) -> list[tuple]:
        world, state = _engine(route_relocation_config())
        current = state
        rows = []
        for tick in range(24):
            current = _step(
                world, current, "WAIT" if tick % 3 else "USE:OBJ-A", seed=seed
            ).state
            record = current["objects"]["OBJ-A"]
            rows.append(
                (
                    record["existence"]["present"],
                    tuple(record["position"]) if record.get("position") else None,
                    record["existence"].get("region_id"),
                    [event["kind"] for event in current.get("existence_events", [])],
                )
            )
        return rows

    assert history(17) == history(17)


def test_different_seeds_can_change_random_positions() -> None:
    def appear_positions(seed: int) -> list[tuple[int, int]]:
        world, state = _engine(random_relocation_config())
        current = state
        positions = []
        for index in range(20):
            action = "USE:OBJ-A" if index % 3 == 0 else "WAIT"
            current = _step(world, current, action, seed=seed).state
            record = current["objects"]["OBJ-A"]
            if record["existence"]["present"] and record.get("position"):
                positions.append(tuple(record["position"]))
        return positions

    assert appear_positions(17)[0] == appear_positions(23)[0]


def test_multiple_dynamic_objects_are_independent() -> None:
    config = WorldEngineConfig(
        width=9,
        height=7,
        vision_radius=8,
        blocked=(),
        objects=(
            ObjectiveObject(
                "OBJ-A",
                (1, 1),
                max_uses=1,
                body_effects={"energy_delta": 0.2},
                existence={
                    "mode": "RELOCATING_ROUTE",
                    "route": [
                        {"region": "A", "cells": [[1, 1]]},
                        {"region": "B", "cells": [[3, 1]]},
                    ],
                    "transition_delay_ticks": [1, 1],
                    "randomize_position_within_region": False,
                },
            ),
            ObjectiveObject(
                "OBJ-B",
                (1, 5),
                max_uses=1,
                body_effects={"hydration_delta": 0.2},
                existence={
                    "mode": "RELOCATING_ROUTE",
                    "route": [
                        {"region": "C", "cells": [[1, 5]]},
                        {"region": "D", "cells": [[3, 5]]},
                    ],
                    "transition_delay_ticks": [1, 1],
                    "randomize_position_within_region": False,
                },
            ),
        ),
    )
    world, state = _engine(config)
    after_a = _step(world, state, "USE:OBJ-A")
    assert after_a.state["objects"]["OBJ-A"]["existence"]["present"] is False
    assert after_a.state["objects"]["OBJ-B"]["existence"]["present"] is True


def test_effects_do_not_create_semantic_types() -> None:
    record = scientific_acceptance_config().objects[0].to_record()
    blob = str(record).lower()
    for banned in ("food", "water", "medicine", "predator", "prey", "migration"):
        assert banned not in blob


def test_observation_firewall_hides_route_and_future_state() -> None:
    world, state = _engine(scientific_acceptance_config())
    observation = world.local_observation(state, agent_id="A001")
    assert observation_contains_forbidden(observation) == []
    depleted = _step(world, state, "USE:OBJ-A")
    hidden = depleted.state["objects"]["OBJ-A"]["existence"]
    assert hidden.get("hidden_next_position") is not None
    observation_after = world.local_observation(depleted.state, agent_id="A001")
    assert observation_contains_forbidden(observation_after) == []
    assert observation_after["visible_objects"] == []
    assert str(hidden["hidden_next_position"]) not in str(observation_after)


def test_observer_ground_truth_reconstructs_relocation() -> None:
    world, state = _engine(scientific_acceptance_config())
    current = _step(world, state, "USE:OBJ-A").state
    for _ in range(4):
        current = _step(world, current, "WAIT").state
    kinds = [event["kind"] for event in current["existence_events"]]
    assert "OBJECT_DEPLETED" in kinds
    assert "OBJECT_DISAPPEARED" in kinds
    assert "OBJECT_REAPPEARED" in kinds
    assert "OBJECT_RELOCATED" in kinds
    regions = [
        event.get("new_region")
        for event in current["existence_events"]
        if event["kind"] == "OBJECT_REAPPEARED"
    ]
    assert regions[0] == "B"


def test_scientific_acceptance_route_and_firewall() -> None:
    world, state = _engine(scientific_acceptance_config())
    current = state
    seen_regions = []
    for _ in range(12):
        record = current["objects"]["OBJ-A"]
        if record["existence"]["present"]:
            seen_regions.append(record["existence"]["region_id"])
            result = _use_here(world, current)
            assert result.action_receipt.get("valid") is True
            current = result.state
        else:
            current = _step(world, current, "WAIT").state
        observation = world.local_observation(current, agent_id="A001")
        assert observation_contains_forbidden(observation) == []
    assert seen_regions[:4] == ["A", "B", "C", "A"]
    agent_world = ObjectExistenceDynamicsWorld()
    observation = agent_world.observe(agent_world.state, "A001").data
    assert observation_contains_forbidden(observation) == []
    truth = agent_world.state.variables["world"]["objects"]["OBJ-A"]["existence"]
    assert "mode" in truth


def test_malformed_region_fails_closed() -> None:
    with pytest.raises(ValueError):
        ObjectiveWorldEngine(
            WorldEngineConfig(
                width=5,
                height=5,
                objects=(
                    ObjectiveObject(
                        "OBJ-X",
                        (0, 0),
                        existence={
                            "mode": "RELOCATING_ROUTE",
                            "route": [{"region": "A", "cells": [[9, 9]]}],
                        },
                    ),
                ),
            )
        )


def test_single_region_route_is_legal() -> None:
    config = WorldEngineConfig(
        width=5,
        height=5,
        blocked=(),
        objects=(
            ObjectiveObject(
                "OBJ-X",
                (1, 1),
                max_uses=1,
                existence={
                    "mode": "RELOCATING_ROUTE",
                    "route": [{"region": "A", "cells": [[1, 1], [2, 1]]}],
                    "transition_delay_ticks": [0, 0],
                    "randomize_position_within_region": True,
                },
            ),
        ),
    )
    world, state = _engine(config)
    after = _step(world, state, "USE:OBJ-X")
    assert after.state["objects"]["OBJ-X"]["existence"]["present"] is True
    assert tuple(after.state["objects"]["OBJ-X"]["position"]) in {(1, 1), (2, 1)}
