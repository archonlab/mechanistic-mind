from dataclasses import dataclass
from typing import Any


TELEMETRY_SCHEMA_VERSION = "psychology-observer-v0.1"


@dataclass(frozen=True, slots=True)
class RunMetadata:
    """Canonical metadata describing one observed simulation run."""

    schema_version: str
    run_id: str
    seed: int
    world_type: str
    agent_ids: tuple[str, ...]
    mechanism_manifest: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class TickRecord:
    """Canonical observer record for one completed simulation tick."""

    schema_version: str
    run_id: str
    tick_before: int
    tick_after: int

    world_before: dict[str, Any]
    world_after: dict[str, Any]

    agent_state_before: dict[str, dict[str, Any]]
    agent_state_after: dict[str, dict[str, Any]]

    observations: dict[str, dict[str, Any]]
    mechanism_outputs: dict[str, dict[str, dict[str, Any]]]
    signals: dict[str, dict[str, dict[str, Any]]]

    actions: dict[str, dict[str, Any]]
    action_sources: dict[str, str]
    action_decisions: dict[str, dict[str, Any]]

    applied_state_updates: dict[str, list[dict[str, Any]]]
