from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .base import Observer
from .records import (
    TELEMETRY_SCHEMA_VERSION,
    RunMetadata,
    TickRecord,
)
from .serialization import append_jsonl, to_primitive


class PsychologyObserver(Observer):
    """Passive canonical telemetry observer.

    Despite the name, this layer does not infer psychological constructs.
    It records explicit simulation causes and consequences only.
    """

    def __init__(
        self,
        *,
        run_id: str,
        jsonl_path: str | Path | None = None,
    ) -> None:
        if not run_id.strip():
            raise ValueError("run_id must be a non-empty string")

        self.run_id = run_id
        self.jsonl_path = Path(jsonl_path) if jsonl_path else None
        self.metadata: RunMetadata | None = None
        self.records: list[TickRecord] = []

    def on_run_start(self, metadata: RunMetadata) -> None:
        self.metadata = deepcopy(metadata)
        self.records = []

        if self.jsonl_path is not None:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self.jsonl_path.write_text("", encoding="utf-8")
            append_jsonl(
                self.jsonl_path,
                {
                    "record_type": "run_metadata",
                    **to_primitive(self.metadata),
                },
            )

    def on_step(self, result: Any) -> None:
        if self.metadata is None:
            raise RuntimeError("Observer received a step before run start")

        record = TickRecord(
            schema_version=TELEMETRY_SCHEMA_VERSION,
            run_id=self.run_id,
            tick_before=result.state_before.tick,
            tick_after=result.state_after.tick,
            world_before=to_primitive(result.state_before.world.variables),
            world_after=to_primitive(result.state_after.world.variables),
            agent_state_before={
                agent_id: self._agent_state_to_dict(state)
                for agent_id, state in result.state_before.agents.items()
            },
            agent_state_after={
                agent_id: self._agent_state_to_dict(state)
                for agent_id, state in result.state_after.agents.items()
            },
            observations={
                agent_id: to_primitive(observation.data)
                for agent_id, observation in result.observations.items()
            },
            mechanism_outputs={
                agent_id: {
                    mechanism_id: to_primitive(output)
                    for mechanism_id, output in outputs.items()
                }
                for agent_id, outputs in result.mechanism_outputs.items()
            },
            signals=to_primitive(result.signals),
            actions={
                agent_id: to_primitive(action)
                for agent_id, action in result.actions.items()
            },
            action_sources=deepcopy(result.action_sources),
            action_decisions={
                agent_id: to_primitive(decision)
                for agent_id, decision in result.action_decisions.items()
            },
            applied_state_updates={
                agent_id: [
                    to_primitive(update)
                    for update in updates
                ]
                for agent_id, updates in result.applied_state_updates.items()
            },
        )

        self.records.append(record)

        if self.jsonl_path is not None:
            append_jsonl(
                self.jsonl_path,
                {
                    "record_type": "tick",
                    **to_primitive(record),
                },
            )

    def _agent_state_to_dict(self, state: Any) -> dict[str, Any]:
        return {
            "variables": to_primitive(state.variables),
            "mechanism_states": to_primitive(state.mechanism_states),
        }
