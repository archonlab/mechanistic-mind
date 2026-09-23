"""SearchCompactWriter — disk artifacts for SEARCH_COMPACT runs."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .controller import SearchCompactController


class SearchCompactWriter:
    def __init__(self, directory: Path, controller: SearchCompactController) -> None:
        self.directory = Path(directory)
        self.controller = controller
        self.meta_path = self.directory / "search_compact_meta.json"
        self.metrics_path = self.directory / "search_compact_metrics.json"
        self.candidates_path = self.directory / "search_compact_candidates.jsonl"
        self._lock = threading.Lock()
        self._opened = False
        self._identity: dict[str, Any] = {}
        self._ticks = 0
        self._bytes_written = 0

    def open(self, identity: dict[str, Any] | None = None) -> None:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._identity = dict(identity or {})
            self._identity["evidence_mode"] = "SEARCH_COMPACT"
            self._identity["analyzer_compat"] = "COMPACT_ONLY"
            self._identity["note"] = (
                "Same runtime as FULL_SCIENTIFIC; retained evidence is bounded. "
                "Do not treat as full Scientific Telemetry V2."
            )
            self.meta_path.write_text(json.dumps(self._identity, indent=2, sort_keys=True) + "\n")
            self._opened = True

    def append_tick(self, runtime: Any, events: list[dict] | None = None) -> None:
        with self._lock:
            if not self._opened:
                return
            tick = int(getattr(runtime, "tick", 0) or 0)
            body = getattr(runtime, "body", None)
            frag = {}
            if body is not None:
                frag = {
                    "x": round(float(getattr(body, "x", 0.0)), 6),
                    "y": round(float(getattr(body, "y", 0.0)), 6),
                }
            self.controller.on_tick(
                tick=tick,
                runtime=runtime,
                events=events,
                digest_fragment=frag,
            )
            self._ticks += 1

    def append_events(self, events: list[dict]) -> None:
        # Events are consumed via append_tick; retained here for API parity.
        return

    def flush(self) -> None:
        return

    def close(self) -> dict[str, Any]:
        with self._lock:
            final = self.controller.finalize()
            self.metrics_path.write_text(json.dumps(final["metrics"], indent=2, sort_keys=True) + "\n")
            with self.candidates_path.open("w", encoding="utf-8") as f:
                for c in final["candidates"]:
                    line = json.dumps(c, sort_keys=True) + "\n"
                    f.write(line)
                    self._bytes_written += len(line.encode())
            meta = {
                **self._identity,
                **{k: final[k] for k in final if k != "candidates"},
                "candidates_n": len(final["candidates"]),
                "ticks_observed": self._ticks,
                "artifact_bytes_approx": self._bytes_written + self.metrics_path.stat().st_size,
            }
            self.meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True, default=str) + "\n")
            self._opened = False
            return meta


def build_worker_result(
    *,
    run_id: str,
    seed: int,
    config_fingerprint: str | None,
    target_tick: int,
    final_tick: int,
    status: str,
    compact_meta: dict[str, Any],
    digest: str | None,
    artifact_paths: dict[str, str],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "seed": seed,
        "config_fingerprint": config_fingerprint,
        "target_tick": target_tick,
        "final_tick": final_tick,
        "status": status,
        "metrics": compact_meta.get("metrics") or {},
        "triggers": [
            {"type": c.get("trigger_type"), "tick": c.get("trigger_tick")}
            for c in (compact_meta.get("candidates") or [])
        ],
        "candidates": compact_meta.get("candidates") or [],
        "digest": digest,
        "artifact_paths": artifact_paths,
        "evidence_mode": "SEARCH_COMPACT",
        "intelligence_score": None,  # explicitly absent
    }
