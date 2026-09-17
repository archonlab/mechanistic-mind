from __future__ import annotations

import json
import sys
from collections import Counter
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    default_contextual_object_config,
)


SEED = 17
TICKS = 120


def mutable_state(record: dict) -> dict[str, float]:
    return {
        key: float(record[key])
        for key in ("quantity", "durability")
        if isinstance(record.get(key), (int, float))
    }


def autonomous_run() -> dict:
    config = default_contextual_object_config(SEED)
    world = ContextualObjectEcologyWorld(world_config=config)
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())
    engine = Engine(
        world=world,
        agents={"A001": Agent(agent_id="A001")},
        seed=SEED,
        mechanisms=registry,
        run_config={
            "experiment": "dynamic-object-ecology-v035",
            "world_seed": SEED,
        },
    )

    initial_objects = deepcopy(
        engine.state.world.variables["world"]["objects"]
    )
    actions: list[str] = []
    positions: list[tuple[int, int]] = []
    use_receipts: list[dict] = []
    for tick in range(1, TICKS + 1):
        result = engine.step()
        action = result.actions["A001"].kind
        actions.append(action)
        truth = result.state_after.world.variables["world"]
        positions.append(tuple(truth["agent_positions"]["A001"]))
        history = result.state_after.world.variables["developmental_history"]
        receipt = history[-1]["world_action_receipt"]
        if action.startswith("USE:"):
            use_receipts.append(
                {
                    "tick": tick,
                    "action": receipt.get("action"),
                    "object_id": receipt.get("object_id"),
                    "object_state_before": deepcopy(
                        receipt.get("object_state_before", {})
                    ),
                    "object_state_after": deepcopy(
                        receipt.get("object_state_after", {})
                    ),
                    "object_state_deltas": deepcopy(
                        receipt.get("object_state_deltas", {})
                    ),
                    "effect_available": receipt.get("effect_available"),
                    "effect_scale": receipt.get("effect_scale"),
                }
            )
    engine.close()

    final_truth = engine.state.world.variables["world"]
    final_objects = final_truth["objects"]
    state_changes = {
        object_id: {
            "before": mutable_state(initial_objects[object_id]),
            "after": mutable_state(record),
            "use_count": int(record.get("use_count", 0)),
        }
        for object_id, record in sorted(final_objects.items())
        if mutable_state(initial_objects[object_id]) != mutable_state(record)
        or int(record.get("use_count", 0)) > 0
    }

    longest_obj29 = 0
    current_obj29 = 0
    for action in actions:
        if action == "USE:OBJ-29":
            current_obj29 += 1
            longest_obj29 = max(longest_obj29, current_obj29)
        else:
            current_obj29 = 0

    action_families = Counter(
        action.split(":", 1)[0] for action in actions
    )
    return {
        "release": "0.3.5",
        "seed": SEED,
        "ticks": TICKS,
        "world": {
            "dimensions": [config.width, config.height],
            "object_count": len(config.objects),
            "unique_object_positions": len(
                {item.position for item in config.objects}
            ),
        },
        "behavior": {
            "action_families": dict(sorted(action_families.items())),
            "distinct_positions_visited": len(set(positions)),
            "object_uses": dict(
                sorted(
                    (key.split(":", 1)[1], value)
                    for key, value in Counter(actions).items()
                    if key.startswith("USE:")
                )
            ),
            "obj_29_longest_consecutive_use": longest_obj29,
        },
        "object_state_changes": state_changes,
        "use_receipts": use_receipts,
        "claim_boundary": (
            "Autonomous seeded observation of the real runtime. It does not "
            "assert that every available manipulation will be selected in one run."
        ),
    }


def main() -> None:
    result = autonomous_run()
    output = ROOT / "experiments" / "dynamic_object_ecology_v035_result.json"
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
