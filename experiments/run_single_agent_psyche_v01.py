from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.adapters.archon import (
    ArchonAdapterSink,
    InMemoryArchonSink,
)
from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import (
    CompositeSink,
    InMemorySink,
    PsychologyObserver,
)
from mechanistic_mind.psyche import SingleAgentPsycheV01
from single_agent_tradeoff import SingleAgentTradeoffWorld


def main() -> None:
    ticks = 60
    canonical = InMemorySink()
    archon = InMemoryArchonSink()
    observer = PsychologyObserver(
        CompositeSink(
            (
                canonical,
                ArchonAdapterSink(archon),
            )
        )
    )

    registry = MechanismRegistry()
    registry.register(SingleAgentPsycheV01())

    engine = Engine(
        world=SingleAgentTradeoffWorld(),
        agents={"A001": Agent(agent_id="A001")},
        seed=17,
        mechanisms=registry,
        observer=observer,
        run_config={
            "experiment": "SINGLE_AGENT_PSYCHE_V01",
            "ticks": ticks,
        },
    )
    engine.run(ticks)
    engine.close()

    actions = [
        record.actions["A001"]["kind"]
        for record in canonical.records
    ]
    psyche_state = (
        engine.state.agents["A001"]
        .mechanism_states["PSYCHE-SINGLE-AGENT-V01"]["psyche"]
    )

    result = {
        "experiment": "SINGLE_AGENT_PSYCHE_V01",
        "ticks": ticks,
        "actions": {
            "REST": actions.count("REST"),
            "WORK": actions.count("WORK"),
            "switches": sum(
                1
                for before, after in zip(actions, actions[1:])
                if before != after
            ),
        },
        "world": {
            "total_progress": engine.state.world.variables["total_progress"],
        },
        "psyche": {
            "final_internal": psyche_state["internal"],
            "learned_action_models": psyche_state["learning"]["action_models"],
            "memory_episodes": len(psyche_state["memory"]["episodes"]),
            "self_model": psyche_state["self_model"],
            "habit_strength": psyche_state["habits"]["strength"],
        },
        "observer": {
            "ticks": len(canonical.records),
            "archon_observations": len(archon.observations),
            "archon_events": len(archon.events),
        },
        "interpretation": (
            "A single persistent agent alternates behavior as learned action "
            "consequences interact with internal regulation, goals, uncertainty, "
            "habit bias, and multi-objective valuation."
        ),
    }

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
