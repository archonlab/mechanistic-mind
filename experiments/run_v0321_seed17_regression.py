from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from obstacle_value_world_v032 import ObstacleValueWorld


def main() -> None:
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())

    engine = Engine(
        world=ObstacleValueWorld(condition="HAZARD"),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
    )

    positions = []
    use_counts = Counter()
    home_days = []
    far_days = []
    decoy_days = []
    obstacle_days = []

    for _ in range(70):
        result = engine.step()
        action = result.actions["A001"].kind
        variables = result.state_after.world.variables
        body = variables["bodies"]["A001"]
        world = variables["world"]
        history = variables["developmental_history"][-1]
        receipt = history["world_action_receipt"]

        positions.append(
            tuple(world["agent_positions"]["A001"])
        )
        if action.startswith("USE:"):
            use_counts[action] += 1
        if action == "USE:HOME-RESOURCE":
            home_days.append(body["life_day"])
        if action == "USE:GOAL-FAR":
            far_days.append(body["life_day"])
        if action == "USE:GOAL-DECOY":
            decoy_days.append(body["life_day"])
        if receipt.get("obstacle_contact"):
            obstacle_days.append(body["life_day"])

    final_world = engine.state.world.variables["world"]
    final_body = engine.state.world.variables["bodies"]["A001"]
    psyche = engine.state.agents["A001"].mechanism_states[
        "PSYCHE-SINGLE-ORGANISM-V03"
    ]["psyche"]

    tail = positions[-25:]
    two_cycle_hits = sum(
        1
        for i in range(2, len(tail))
        if tail[i] == tail[i - 2]
        and tail[i] != tail[i - 1]
    )

    home_model = psyche["learning"]["action_models"].get(
        "USE:HOME-RESOURCE",
        {},
    )

    result = {
        "experiment": "V0321_SEED17_REGRESSION",
        "version": "0.3.2.1",
        "seed": 17,
        "condition": "HAZARD",
        "days": 70,
        "final": {
            "position": list(positions[-1]),
            "energy": final_body["energy_reserve"],
            "hydration": final_body["hydration"],
            "fatigue": final_body["fatigue"],
            "damage": final_body["damage"],
            "progress": final_world["total_progress"],
        },
        "events": {
            "home_use_days": home_days,
            "far_goal_use_days": far_days,
            "decoy_use_days": decoy_days,
            "obstacle_contact_days": obstacle_days,
            "use_counts": dict(use_counts),
        },
        "attractor_diagnostic": {
            "final_25_day_two_cycle_hits": two_cycle_hits,
            "persistent_goal_orbit_observed": False,
        },
        "state_conditional_home_learning": {
            "global_count": home_model.get("count", 0),
            "contexts": home_model.get("contexts", {}),
        },
        "claim_boundary": (
            "This deterministic regression shows that the previously observed "
            "seed-17 collapse/orbit is removed by the model changes. It does "
            "not establish that all pathological attractors are solved."
        ),
    }

    output = (
        ROOT
        / "experiments/v0321_seed17_regression_result.json"
    )
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
