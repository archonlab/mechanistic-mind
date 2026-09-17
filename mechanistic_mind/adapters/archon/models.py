from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mechanistic_mind.observer import canonical_json, to_primitive


ARCHON_BRIDGE_SCHEMA = "mechanistic-mind.archon-bridge/0.1"


@dataclass(frozen=True, slots=True)
class ArchonLauncherDescriptor:
    """Discovery metadata for an ARCHON-side launcher integration."""

    adapter_id: str = "mechanistic_mind"
    display_name: str = "Mechanistic Mind"
    domain: str = "psychology"
    schema_version: str = ARCHON_BRIDGE_SCHEMA
    telemetry_format: str = "jsonl"
    capabilities: tuple[str, ...] = (
        "deterministic_seed",
        "mechanism_versions",
        "causal_tick_trace",
        "external_action_override",
        "state_update_provenance",
        "signals",
    )

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True, slots=True)
class ArchonRunManifest:
    """Run-level bridge record emitted before tick telemetry."""

    schema_version: str
    domain: str
    source_run_id: str
    engine_version: str
    seed: int
    world_type: str
    agent_ids: tuple[str, ...]
    mechanism_versions: dict[str, str]
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True, slots=True)
class ArchonObservationRecord:
    """Per-agent canonical observation record for one tick."""

    schema_version: str
    domain: str
    source_run_id: str
    tick: int
    agent_id: str
    observation: dict[str, Any]
    state_before: dict[str, Any]
    state_after: dict[str, Any]
    signals: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True, slots=True)
class ArchonEventRecord:
    """Explicit event derived from one causal component of a tick."""

    schema_version: str
    domain: str
    source_run_id: str
    tick: int
    agent_id: str
    event_type: str
    source: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True, slots=True)
class ArchonRunSummaryRecord:
    schema_version: str
    domain: str
    source_run_id: str
    ticks_recorded: int
    final_tick: int
    completed: bool

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)
