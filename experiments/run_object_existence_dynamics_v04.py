from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Action
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.world_engine import (
    ObjectiveWorldEngine,
    observation_contains_forbidden,
)
from object_existence_dynamics_v04 import (
    random_relocation_config,
    route_relocation_config,
    scientific_acceptance_config,
    static_object_config,
)


def _drive(config, ticks: int = 24, seed: int = 17) -> dict:
    engine = ObjectiveWorldEngine(config)
    state = engine.initial_state(start_position=(1, 1))
    rng = DeterministicRandom(seed)
    for _ in range(ticks):
        observation = engine.local_observation(state, agent_id="A001")
        action = "USE:OBJ-A" if "USE:OBJ-A" in observation["available_actions"] else "WAIT"
        state = engine.transition_action(
            state,
            agent_id="A001",
            action=Action(action),
            rng=rng,
            body_context={},
        ).state
    events = list(state.get("existence_events") or [])
    observation = engine.local_observation(state, agent_id="A001")
    existence = config.objects[0].existence or {"mode": "STATIC"}
    return {
        "mode": existence.get("mode", "STATIC"),
        "ticks": ticks,
        "seed": seed,
        "final_present": bool(
            state["objects"]["OBJ-A"].get("existence", {}).get("present", True)
        ),
        "final_position": state["objects"]["OBJ-A"].get("position"),
        "event_kinds": [item.get("kind") for item in events],
        "regions": [
            item.get("new_region")
            for item in events
            if item.get("kind") == "OBJECT_REAPPEARED"
        ],
        "forbidden_observation_keys": observation_contains_forbidden(observation),
    }


def main() -> None:
    result = {
        "claim_boundary": (
            "Object existence dynamics are world properties. "
            "This record does not claim route learning, resource concepts, "
            "or semantic object categories."
        ),
        "presets": {
            "STATIC": _drive(static_object_config()),
            "RANDOM": _drive(random_relocation_config()),
            "ROUTE": _drive(route_relocation_config()),
            "SCIENTIFIC_ACCEPTANCE": _drive(scientific_acceptance_config()),
        },
    }
    out = ROOT / "experiments" / "object_existence_dynamics_v04_result.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
