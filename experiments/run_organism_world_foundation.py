from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.psyche import SingleOrganismPsycheV03
from organism_world_v03 import (
    OrganismWorld,
    default_organism_world_config,
)


def run_case(
    *,
    case_id: str,
    resource_layout: str,
    seed: int,
    ticks: int,
    random_event_rate: float = 0.0,
) -> dict:
    registry = MechanismRegistry()
    registry.register(SingleOrganismPsycheV03())

    engine = Engine(
        world=OrganismWorld(
            world_config=default_organism_world_config(
                resource_layout=resource_layout,
                random_event_rate=random_event_rate,
            )
        ),
        agents={"A001": Agent(agent_id="A001")},
        seed=seed,
        mechanisms=registry,
        run_config={
            "experiment": "ORGANISM_WORLD_FOUNDATION_V03",
            "case_id": case_id,
            "resource_layout": resource_layout,
            "random_event_rate": random_event_rate,
            "ticks": ticks,
        },
    )
    engine.run(ticks)

    world = engine.state.world.variables["world"]
    body = engine.state.world.variables["bodies"]["A001"]
    psyche = (
        engine.state.agents["A001"]
        .mechanism_states["PSYCHE-SINGLE-ORGANISM-V03"]["psyche"]
    )
    action_counts = world.get("action_counts", {})

    return {
        "case_id": case_id,
        "resource_layout": resource_layout,
        "seed": seed,
        "ticks": ticks,
        "world": {
            "total_progress": world["total_progress"],
            "final_position": world["agent_positions"]["A001"],
            "movement_count": world.get("movement_count", 0),
            "interaction_count": world.get("interaction_count", 0),
            "wait_count": world.get("wait_count", 0),
            "random_event_count": world.get("random_event_count", 0),
            "exogenous_event_log": world.get("exogenous_event_log", []),
            "top_actions": sorted(
                action_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )[:10],
        },
        "body_truth": body,
        "psyche": {
            "internal_model": psyche["internal"],
            "known_positions": len(
                psyche["memory"]["spatial"]["visited"]
            ),
            "known_objects": psyche["memory"]["spatial"]["objects"],
            "learned_action_models": len(
                psyche["learning"]["action_models"]
            ),
            "habit_top": sorted(
                psyche["habits"]["strength"].items(),
                key=lambda item: (-item[1], item[0]),
            )[:10],
            "self_model": psyche["self_model"],
            "last_selection": psyche["working"].get("last_selection"),
            "preset_personality_fields": [],
        },
    }


def main() -> None:
    same_architecture_different_worlds = [
        run_case(
            case_id=f"LAYOUT-{layout.upper()}",
            resource_layout=layout,
            seed=17,
            ticks=90,
        )
        for layout in ("near", "distributed", "far")
    ]

    same_world_different_random_histories = [
        run_case(
            case_id=f"RANDOM-HISTORY-{seed}",
            resource_layout="distributed",
            seed=seed,
            ticks=60,
            random_event_rate=0.12,
        )
        for seed in (11, 29)
    ]

    result = {
        "experiment": "ORGANISM_WORLD_FOUNDATION_V03",
        "version": "0.3.0",
        "question": (
            "Can identical psyche architecture and initial body state diverge "
            "through different objective environments or stochastic histories?"
        ),
        "architecture_invariants": {
            "psyche_mechanism": "PSYCHE-SINGLE-ORGANISM-V03",
            "body_truth_agent_visible": False,
            "world_hidden_roles_agent_visible": False,
            "exogenous_event_receipts_agent_visible": False,
            "preset_personality": False,
        },
        "same_architecture_different_worlds": (
            same_architecture_different_worlds
        ),
        "same_world_different_random_histories": (
            same_world_different_random_histories
        ),
        "interpretation_rule": (
            "Behavioral divergence is an observation. It is not by itself "
            "evidence for a unique psychological mechanism; later matched "
            "experiments must identify which process produced the divergence."
        ),
    }

    output = ROOT / "experiments/organism_world_foundation_v03_result.json"
    output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
