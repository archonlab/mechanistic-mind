from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mechanistic_mind.observer import RunMetadata, RunSummary, TickRecord

from .models import (
    ARCHON_BRIDGE_SCHEMA,
    ArchonEventRecord,
    ArchonLauncherDescriptor,
    ArchonObservationRecord,
    ArchonRunManifest,
    ArchonRunSummaryRecord,
)


@dataclass(slots=True)
class ArchonAdapter:
    """Pure translation layer from Mechanistic Mind telemetry to ARCHON bridge records.

    This adapter deliberately has no dependency on ARCHON Python packages.
    The ARCHON side can consume the bridge schema through a file, pipe, socket,
    database writer, or launcher-specific transport later.
    """

    domain: str = "psychology"

    @property
    def descriptor(self) -> ArchonLauncherDescriptor:
        return ArchonLauncherDescriptor(domain=self.domain)

    def adapt_run_metadata(self, metadata: RunMetadata) -> ArchonRunManifest:
        return ArchonRunManifest(
            schema_version=ARCHON_BRIDGE_SCHEMA,
            domain=self.domain,
            source_run_id=metadata.run_id,
            engine_version=metadata.engine_version,
            seed=metadata.seed,
            world_type=metadata.world_type,
            agent_ids=metadata.agent_ids,
            mechanism_versions=dict(metadata.mechanism_versions),
            config=dict(metadata.config),
        )

    def adapt_tick(
        self,
        record: TickRecord,
    ) -> tuple[
        tuple[ArchonObservationRecord, ...],
        tuple[ArchonEventRecord, ...],
    ]:
        observations: list[ArchonObservationRecord] = []
        events: list[ArchonEventRecord] = []

        agent_ids = sorted(record.observations)

        for agent_id in agent_ids:
            state_before = (
                record.state_before.get("agents", {}).get(agent_id, {})
            )
            state_after = (
                record.state_after.get("agents", {}).get(agent_id, {})
            )
            signals = record.signals.get(agent_id, {})

            observations.append(
                ArchonObservationRecord(
                    schema_version=ARCHON_BRIDGE_SCHEMA,
                    domain=self.domain,
                    source_run_id=record.run_id,
                    tick=record.tick,
                    agent_id=agent_id,
                    observation=record.observations.get(agent_id, {}),
                    state_before=state_before,
                    state_after=state_after,
                    signals=signals,
                )
            )

            for mechanism_id in sorted(
                record.mechanism_outputs.get(agent_id, {})
            ):
                output = record.mechanism_outputs[agent_id][mechanism_id]
                events.append(
                    ArchonEventRecord(
                        schema_version=ARCHON_BRIDGE_SCHEMA,
                        domain=self.domain,
                        source_run_id=record.run_id,
                        tick=record.tick,
                        agent_id=agent_id,
                        event_type="MECHANISM_OUTPUT",
                        source=f"MECHANISM:{mechanism_id}",
                        payload=output,
                    )
                )

            events.append(
                ArchonEventRecord(
                    schema_version=ARCHON_BRIDGE_SCHEMA,
                    domain=self.domain,
                    source_run_id=record.run_id,
                    tick=record.tick,
                    agent_id=agent_id,
                    event_type="ACTION_EXECUTED",
                    source=record.action_sources.get(
                        agent_id,
                        "UNKNOWN",
                    ),
                    payload={
                        "action": record.actions.get(agent_id, {}),
                        "decision": record.action_decisions.get(
                            agent_id,
                            {},
                        ),
                    },
                )
            )

            for update in record.applied_state_updates.get(agent_id, []):
                events.append(
                    ArchonEventRecord(
                        schema_version=ARCHON_BRIDGE_SCHEMA,
                        domain=self.domain,
                        source_run_id=record.run_id,
                        tick=record.tick,
                        agent_id=agent_id,
                        event_type="STATE_UPDATE_APPLIED",
                        source=update.get(
                            "source_mechanism",
                            "UNKNOWN",
                        ),
                        payload=update,
                    )
                )

        return tuple(observations), tuple(events)

    def adapt_run_summary(
        self,
        summary: RunSummary,
    ) -> ArchonRunSummaryRecord:
        return ArchonRunSummaryRecord(
            schema_version=ARCHON_BRIDGE_SCHEMA,
            domain=self.domain,
            source_run_id=summary.run_id,
            ticks_recorded=summary.ticks_recorded,
            final_tick=summary.final_tick,
            completed=summary.completed,
        )
