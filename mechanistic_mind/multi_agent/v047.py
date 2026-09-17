"""Update 4.7 factory: shared ecology, independent psyches."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "worlds") not in sys.path:
    sys.path.insert(0, str(ROOT / "worlds"))

from mechanistic_mind.agent import Agent
from mechanistic_mind.body import BodyState
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import PsychologyObserver
from mechanistic_mind.psyche import SingleOrganismPsycheV03

from contextual_object_ecology_v034 import (
    ContextualObjectEcologyWorld,
    default_contextual_object_config,
    physical_protocol_object_config,
)
from organism_world_v03 import OrganismWorld, default_organism_world_config


def derived_seed(world_seed: int, agent_id: str) -> int:
    """Independent endogenous seed per agent; world seed stays shared."""
    material = f"{int(world_seed)}|{agent_id}|v047".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], "big", signed=False) % (2**31 - 1)


def build_independent_psyche_stacks(
    agent_ids: tuple[str, ...] | list[str],
) -> dict[str, MechanismRegistry]:
    """Private mechanism stack per agent (no shared mutable psyche instance)."""
    stacks: dict[str, MechanismRegistry] = {}
    for agent_id in agent_ids:
        registry = MechanismRegistry()
        registry.register(SingleOrganismPsycheV03())
        stacks[str(agent_id)] = registry
    return stacks


def build_shared_ecology_world(
    *,
    agent_ids: tuple[str, ...] | list[str],
    start_positions: dict[str, tuple[int, int]],
    world_kind: str = "contextual",
    world_seed: int = 17,
    compact: bool = False,
    initial_bodies: dict[str, BodyState] | None = None,
) -> OrganismWorld:
    ids = tuple(str(aid) for aid in agent_ids)
    if set(ids) != set(start_positions):
        raise ValueError("start_positions keys must match agent_ids")

    bodies = initial_bodies or {aid: BodyState() for aid in ids}

    if world_kind == "organism":
        return OrganismWorld(
            world_config=default_organism_world_config(),
            agent_ids=ids,
            start_positions=start_positions,
            initial_bodies=bodies,
        )

    config = (
        physical_protocol_object_config()
        if compact
        else default_contextual_object_config(world_seed)
    )
    return ContextualObjectEcologyWorld(
        world_config=config,
        agent_ids=ids,
        start_positions=start_positions,
        initial_bodies=bodies,
    )


def build_multi_agent_engine(
    *,
    agent_ids: tuple[str, ...] | list[str],
    start_positions: dict[str, tuple[int, int]],
    world_seed: int = 17,
    world_kind: str = "contextual",
    compact: bool = False,
    observer: PsychologyObserver | None = None,
    run_config: dict[str, Any] | None = None,
) -> Engine:
    ids = tuple(str(aid) for aid in agent_ids)
    world = build_shared_ecology_world(
        agent_ids=ids,
        start_positions=start_positions,
        world_kind=world_kind,
        world_seed=world_seed,
        compact=compact,
    )
    agents = {aid: Agent(agent_id=aid) for aid in ids}
    stacks = build_independent_psyche_stacks(ids)
    # Shared registry mirrors agent A's stack for observer metadata only.
    primary = stacks[ids[0]]
    config = dict(run_config or {})
    config.setdefault("update", "4.7")
    config.setdefault("shared_ecology", True)
    config.setdefault("independent_psyches", True)
    config.setdefault("agent_ids", list(ids))
    config.setdefault(
        "derived_seeds",
        {aid: derived_seed(world_seed, aid) for aid in ids},
    )
    config.setdefault("no_social_semantics", True)
    return Engine(
        world=world,
        agents=agents,
        seed=world_seed,
        mechanisms=primary,
        mechanisms_by_agent=stacks,
        observer=observer,
        run_config=config,
    )
