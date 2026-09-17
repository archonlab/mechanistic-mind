from __future__ import annotations

import json
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .biography import build_biography
from .dynamics import DynamicsAccumulator
from .epochs import BehavioralEpochDetector
from .extractor import extract_compact_tick
from .meaningful_events import MeaningfulEventDetector
from .report import write_html_report


@dataclass(frozen=True)
class AnalysisResult:
    source: Path
    output_dir: Path
    summary: Path
    meaningful_events: Path
    epochs: Path
    biography: Path
    report: Path
    timeline: Path | None = None

    @property
    def events(self) -> Path:
        return self.meaningful_events

    @property
    def phases(self) -> Path:
        return self.epochs


class PsychologyAnalyzer:
    def __init__(self, *, epoch_window: int = 100, phase_window: int | None = None, habit_threshold: float = 0.75, epoch_change_threshold: float = 0.38):
        self.epoch_window = phase_window if phase_window is not None else epoch_window
        self.habit_threshold = habit_threshold
        self.epoch_change_threshold = epoch_change_threshold

    @staticmethod
    def resolve_source(source: Path) -> Path:
        source = source.expanduser().resolve()
        if source.is_dir():
            candidate = source / "psychology_observer.jsonl"
            if not candidate.is_file():
                raise FileNotFoundError(f"Run directory does not contain psychology_observer.jsonl: {source}")
            return candidate
        if not source.is_file():
            raise FileNotFoundError(source)
        return source

    def analyze(self, source: str | Path, output_dir: str | Path | None = None, *, keep_timeline: bool = False) -> AnalysisResult:
        source_path = self.resolve_source(Path(source))
        output = source_path.parent / "analysis" if output_dir is None else Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        summary_path = output / "summary.json"
        events_path = output / "meaningful_events.json"
        epochs_path = output / "epochs.json"
        biography_path = output / "biography.json"
        report_path = output / "report.html"
        timeline_path = output / "timeline.jsonl" if keep_timeline else None
        dynamics = DynamicsAccumulator()
        event_detector = MeaningfulEventDetector(habit_threshold=self.habit_threshold)
        epoch_detector = BehavioralEpochDetector(self.epoch_window, self.epoch_change_threshold)
        invalid_json_lines = 0
        ignored_records = 0
        metadata: dict[str, Any] | None = None
        timeline_context = timeline_path.open("w", encoding="utf-8") if timeline_path else nullcontext(None)
        with source_path.open("r", encoding="utf-8") as source_handle, timeline_context as timeline_handle:
            for line_number, line in enumerate(source_handle, start=1):
                if not line.strip():
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    invalid_json_lines += 1
                    continue
                if not isinstance(record, dict):
                    ignored_records += 1
                    continue
                record_type = record.get("record_type")
                payload = record.get("payload")
                data = payload if isinstance(payload, dict) else record
                if record_type == "run_metadata" or data.get("type") == "run_metadata" or "run_metadata" in data:
                    if metadata is None:
                        metadata = dict(data)
                    continue
                if record_type is not None and record_type != "tick":
                    ignored_records += 1
                    continue
                compact = extract_compact_tick(data, line_number)
                if compact is None:
                    ignored_records += 1
                    continue
                if timeline_handle is not None:
                    timeline_handle.write(json.dumps(compact, ensure_ascii=False, separators=(",", ":")) + "\n")
                dynamics.observe(compact)
                event_detector.observe(compact)
                epoch_detector.observe(compact)
        epochs = epoch_detector.finish()
        events = event_detector.finish()
        summary = {
            "schema": "mechanistic-mind/psychology-analysis-v0.2",
            "source": str(source_path),
            "metadata": metadata,
            "invalid_json_lines": invalid_json_lines,
            "ignored_records": ignored_records,
            "timeline_kept": keep_timeline,
            "dynamics": dynamics.to_dict(),
            "meaningful_event_count": len(events),
            "epoch_count": len(epochs),
            "interpretation_boundary": {
                "status": "DESCRIPTIVE_EVIDENCE_ONLY",
                "statement": "Events, epochs, and biography summarize recorded computational evidence. They are not diagnoses and do not establish human psychological states.",
            },
        }
        biography = build_biography(summary, events, epochs)
        self._write_json(summary_path, summary)
        self._write_json(events_path, events)
        self._write_json(epochs_path, epochs)
        self._write_json(biography_path, biography)
        write_html_report(report_path, summary, events, epochs, biography)
        return AnalysisResult(source_path, output, summary_path, events_path, epochs_path, biography_path, report_path, timeline_path)

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
