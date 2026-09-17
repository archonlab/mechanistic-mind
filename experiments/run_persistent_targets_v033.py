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
from persistent_targets_world_v033 import PersistentTargetsWorld


def run_condition(condition: str, *, ticks: int = 80, seed: int = 17) -> dict:
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    engine = Engine(
        world=PersistentTargetsWorld(condition=condition),
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
    )

    action_counts = Counter()
    completion_days = []
    stall_days = []
    anvil_days = []
    last_actions = []

    for _ in range(ticks):
        result = engine.step()
        history = result.state_after.world.variables["developmental_history"][-1]
        body = result.state_after.world.variables["bodies"]["A001"]
        receipt = history["world_action_receipt"]
        action = history["action"]
        action_counts[action] += 1
        last_actions.append(action)

        if action == "USE:TARGET-ANVIL":
            anvil_days.append(body["life_day"])
        if receipt.get("persistent_target_outcome") == "SUCCESS":
            completion_days.append(body["life_day"])
        if receipt.get("persistent_target_outcome") == "STALL":
            stall_days.append(body["life_day"])

    world_vars = engine.state.world.variables["world"]
    body = engine.state.world.variables["bodies"]["A001"]
    target = world_vars["objects"]["TARGET-ANVIL"]

    return {
        "condition": condition,
        "ticks": ticks,
        "seed": seed,
        "final": {
            "position": world_vars["agent_positions"]["A001"],
            "progress": world_vars["total_progress"],
            "energy": body["energy_reserve"],
            "hydration": body["hydration"],
            "fatigue": body["fatigue"],
            "damage": body["damage"],
        },
        "action_counts": dict(action_counts),
        "target_summary": {
            "attempt_count": target["attempt_count"],
            "success_count": target["success_count"],
            "latent_progress": target["latent_progress"],
            "last_outcome": target["last_outcome"],
            "anvil_use_days": anvil_days,
            "completion_days": completion_days,
            "stall_days": stall_days,
        },
        "last_20_actions": last_actions[-20:],
    }


def main() -> None:
    report = {
        "version": "0.3.3",
        "title": "Persistent Targets & Attractor Switching",
        "conditions": [
            run_condition(name)
            for name in ("WORKING", "BROKEN", "DEAD", "REVIVAL")
        ],
        "claim_boundary": (
            "This diagnostic compares world regimes with identical basic psyche "
            "architecture and different hidden target dynamics. It does not "
            "establish a general theory of persistence or compulsive repetition."
        ),
    }
    out = ROOT / "experiments/persistent_targets_v033_result.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
