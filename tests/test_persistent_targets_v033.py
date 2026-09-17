from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action
from mechanistic_mind.core import DeterministicRandom
from persistent_targets_world_v033 import PersistentTargetsWorld



def _position_agent_on_target(world: PersistentTargetsWorld, target=(3, 1)) -> None:
    world.state.variables["world"]["agent_positions"]["A001"] = list(target)


def _tick_use(world: PersistentTargetsWorld, action: str = "USE:TARGET-ANVIL") -> dict:
    world.state = world.transition(
        world.state,
        {"A001": Action(action)},
        DeterministicRandom(17),
    )
    return world.state.variables["developmental_history"][-1]["world_action_receipt"]


def test_working_target_completes_after_threshold() -> None:
    world = PersistentTargetsWorld(condition="WORKING")
    _position_agent_on_target(world)

    outcomes = []
    for _ in range(2):
        receipt = _tick_use(world)
        outcomes.append(receipt["persistent_target_outcome"])

    assert outcomes == ["PARTIAL", "SUCCESS"]
    record = world.state.variables["world"]["objects"]["TARGET-ANVIL"]
    assert record["success_count"] == 1
    assert record["latent_progress"] == 0.0
    assert world.state.variables["world"]["total_progress"] > 1.0


def test_broken_target_stalls_after_switch_tick() -> None:
    world = PersistentTargetsWorld(condition="BROKEN")
    _position_agent_on_target(world)
    world.state.variables["world"]["tick"] = 44

    receipt = _tick_use(world)
    assert receipt["persistent_target_outcome"] == "STALL"
    assert receipt["target_operative"] is False

    record = world.state.variables["world"]["objects"]["TARGET-ANVIL"]
    assert record["success_count"] == 0
    assert record["latent_progress"] == 0.0


def test_revival_target_recovers_after_switch_tick() -> None:
    world = PersistentTargetsWorld(condition="REVIVAL")
    _position_agent_on_target(world)

    receipt = _tick_use(world)
    assert receipt["persistent_target_outcome"] == "STALL"

    world.state.variables["world"]["tick"] = 44
    receipts = [_tick_use(world) for _ in range(2)]
    assert [r["persistent_target_outcome"] for r in receipts] == ["PARTIAL", "SUCCESS"]


def test_dead_target_remains_visible_but_unproductive() -> None:
    world = PersistentTargetsWorld(condition="DEAD")
    _position_agent_on_target(world)

    receipt = _tick_use(world)
    assert receipt["valid"] is True
    assert receipt["persistent_target_outcome"] == "STALL"

    observation = world.observe(world.state, "A001")
    available = set(observation.data["available_actions"])
    assert "USE:TARGET-ANVIL" in available
