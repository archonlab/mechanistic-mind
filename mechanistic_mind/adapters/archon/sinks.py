from __future__ import annotations

from pathlib import Path
from typing import Protocol

from mechanistic_mind.observer import (
    ObserverSink,
    RunMetadata,
    RunSummary,
    TickRecord,
    canonical_json,
)

from .adapter import ArchonAdapter
from .models import (
    ArchonEventRecord,
    ArchonObservationRecord,
    ArchonRunManifest,
    ArchonRunSummaryRecord,
)


class ArchonRecordSink(Protocol):
    def write_manifest(self, record: ArchonRunManifest) -> None: ...
    def write_observation(self, record: ArchonObservationRecord) -> None: ...
    def write_event(self, record: ArchonEventRecord) -> None: ...
    def write_summary(self, record: ArchonRunSummaryRecord) -> None: ...


class InMemoryArchonSink:
    def __init__(self) -> None:
        self.manifest: ArchonRunManifest | None = None
        self.observations: list[ArchonObservationRecord] = []
        self.events: list[ArchonEventRecord] = []
        self.summary: ArchonRunSummaryRecord | None = None

    def write_manifest(self, record: ArchonRunManifest) -> None:
        self.manifest = record

    def write_observation(self, record: ArchonObservationRecord) -> None:
        self.observations.append(record)

    def write_event(self, record: ArchonEventRecord) -> None:
        self.events.append(record)

    def write_summary(self, record: ArchonRunSummaryRecord) -> None:
        self.summary = record


class JSONLArchonSink:
    """Append-only bridge stream for ARCHON-side ingestion."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record_type: str, payload) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(
                canonical_json(
                    {
                        "record_type": record_type,
                        "payload": payload,
                    }
                )
                + "\n"
            )

    def write_manifest(self, record: ArchonRunManifest) -> None:
        self._append("archon_run_manifest", record)

    def write_observation(self, record: ArchonObservationRecord) -> None:
        self._append("archon_observation", record)

    def write_event(self, record: ArchonEventRecord) -> None:
        self._append("archon_event", record)

    def write_summary(self, record: ArchonRunSummaryRecord) -> None:
        self._append("archon_run_summary", record)


class ArchonAdapterSink:
    """ObserverSink implementation that translates telemetry on the fly."""

    def __init__(
        self,
        target: ArchonRecordSink,
        *,
        adapter: ArchonAdapter | None = None,
    ) -> None:
        self.target = target
        self.adapter = adapter or ArchonAdapter()

    def write_run_metadata(self, metadata: RunMetadata) -> None:
        self.target.write_manifest(
            self.adapter.adapt_run_metadata(metadata)
        )

    def write_tick(self, record: TickRecord) -> None:
        observations, events = self.adapter.adapt_tick(record)

        for observation in observations:
            self.target.write_observation(observation)

        for event in events:
            self.target.write_event(event)

    def write_run_summary(self, summary: RunSummary) -> None:
        self.target.write_summary(
            self.adapter.adapt_run_summary(summary)
        )
