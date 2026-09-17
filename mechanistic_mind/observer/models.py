from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


def to_primitive(value: Any) -> Any:
    """Convert runtime values into a strict JSON-safe canonical form.

    Unknown objects fail closed instead of being silently stringified.
    """
    if is_dataclass(value):
        return {
            str(k): to_primitive(v)
            for k, v in asdict(value).items()
        }

    if isinstance(value, dict):
        converted: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, (str, int, float, bool)):
                raise TypeError(
                    f"Unsupported mapping key type: {type(key).__name__}"
                )
            converted[str(key)] = to_primitive(item)
        return converted

    if isinstance(value, (list, tuple)):
        return [to_primitive(v) for v in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    raise TypeError(
        f"Unsupported telemetry value type: {type(value).__name__}"
    )


def canonical_json(value: Any) -> str:
    """Serialize a value to deterministic compact JSON."""
    return json.dumps(
        to_primitive(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


# Backward-compatible internal name used by the observer implementation.
to_plain = to_primitive


@dataclass(frozen=True, slots=True)
class RunMetadata:
    """Canonical metadata describing one deterministic simulation run."""

    run_id: str
    engine_version: str
    seed: int
    mechanism_versions: dict[str, str]
    world_type: str
    agent_ids: tuple[str, ...]
    config: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class TickRecord:
    """Canonical, interpretation-free causal record for one simulation tick."""

    run_id: str
    tick: int
    state_before: dict[str, Any]
    observations: dict[str, Any]
    mechanism_outputs: dict[str, Any]
    signals: dict[str, Any]
    action_decisions: dict[str, Any]
    actions: dict[str, Any]
    action_sources: dict[str, str]
    applied_state_updates: dict[str, Any]
    state_after: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return to_primitive(self)


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_id: str
    ticks_recorded: int
    final_tick: int
    completed: bool = True
