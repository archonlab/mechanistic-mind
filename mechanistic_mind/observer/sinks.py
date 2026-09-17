from __future__ import annotations

from pathlib import Path
from typing import Protocol, Sequence

from .models import (
    RunMetadata,
    RunSummary,
    TickRecord,
    canonical_json,
)


class ObserverSink(Protocol):
    def write_run_metadata(self, metadata: RunMetadata) -> None: ...
    def write_tick(self, record: TickRecord) -> None: ...
    def write_run_summary(self, summary: RunSummary) -> None: ...


class InMemorySink:
    """Simple sink used for tests, notebooks, and short diagnostic runs."""

    def __init__(self) -> None:
        self.metadata: RunMetadata | None = None
        self.records: list[TickRecord] = []
        self.summary: RunSummary | None = None

    def write_run_metadata(self, metadata: RunMetadata) -> None:
        self.metadata = metadata

    def write_tick(self, record: TickRecord) -> None:
        self.records.append(record)

    def write_run_summary(self, summary: RunSummary) -> None:
        self.summary = summary


class CompositeSink:
    """Fan one canonical observer stream out to multiple sinks."""

    def __init__(self, sinks: Sequence[ObserverSink]) -> None:
        self.sinks = tuple(sinks)

    def write_run_metadata(self, metadata: RunMetadata) -> None:
        for sink in self.sinks:
            sink.write_run_metadata(metadata)

    def write_tick(self, record: TickRecord) -> None:
        for sink in self.sinks:
            sink.write_tick(record)

    def write_run_summary(self, summary: RunSummary) -> None:
        for sink in self.sinks:
            sink.write_run_summary(summary)


class JSONLSink:
    """Append-only deterministic JSONL telemetry sink."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _append(self, record_type: str, payload) -> None:
        envelope = {
            "record_type": record_type,
            "payload": payload,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(canonical_json(envelope) + "\n")

    def write_run_metadata(self, metadata: RunMetadata) -> None:
        self._append("run_metadata", metadata)

    def write_tick(self, record: TickRecord) -> None:
        self._append("tick", record)

    def write_run_summary(self, summary: RunSummary) -> None:
        self._append("run_summary", summary)
