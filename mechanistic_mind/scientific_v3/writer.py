\
"""Append-only SCIENTIFIC_V3 CORE writer — bounded buffer, fail closed."""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import EVIDENCE_MODE, EVIDENCE_TIER, SCHEMA_VERSION
from .capture import capture_v3_tick
from .coverage import empty_coverage
from .identity import IdentityMap

HEALTH_OK = "OK"
HEALTH_BACKPRESSURE = "EVIDENCE_BACKPRESSURE"
HEALTH_INCOMPLETE = "EVIDENCE_INCOMPLETE"
HEALTH_WRITE_FAILED = "EVIDENCE_WRITE_FAILED"


def _jsonl_line(obj: dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str)


class ScientificV3Writer:
    """Phase-1 CORE persistence. Does not run Analyzer. No silent drops."""

    def __init__(
        self,
        directory: Path,
        *,
        flush_every: int = 32,
        max_queue_lines: int = 50_000,
    ) -> None:
        self.directory = Path(directory)
        self.flush_every = max(1, int(flush_every))
        self.max_queue_lines = max(100, int(max_queue_lines))
        self._lock = threading.Lock()
        self._opened = False
        self._identity_map: IdentityMap | None = None
        self._run_id = ""
        self._generation = 0
        self._bufs: dict[str, list[str]] = {
            "spine": [],
            "observations": [],
            "decisions": [],
            "motors": [],
            "consequences": [],
        }
        self._paths = {
            "spine": self.directory / "scientific_spine.jsonl",
            "observations": self.directory / "scientific_observations.jsonl",
            "decisions": self.directory / "scientific_decisions.jsonl",
            "motors": self.directory / "scientific_motors.jsonl",
            "consequences": self.directory / "scientific_consequences.jsonl",
        }
        self.meta_path = self.directory / "scientific_v3_meta.json"
        self.identity_path = self.directory / "identity_map.json"
        self._counts = {k: 0 for k in self._bufs}
        self._last_decision_tick = -1
        self._health = HEALTH_OK
        self._health_detail: str | None = None
        self._peak_queue = 0
        self._coverage = empty_coverage(tier=EVIDENCE_TIER)
        self._ticks_captured = 0

    @property
    def health(self) -> dict[str, Any]:
        return {
            "state": self._health,
            "detail": self._health_detail,
            "peak_queue_lines": self._peak_queue,
            "ticks_captured": self._ticks_captured,
            "counts": dict(self._counts),
        }

    def open(self, *, run_id: str, generation: int = 0, extra_meta: dict[str, Any] | None = None) -> None:
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            self._run_id = str(run_id)
            self._generation = int(generation)
            self._identity_map = IdentityMap(run_id=self._run_id, generation=self._generation)
            self._opened = True
            self._health = HEALTH_OK
            self._health_detail = None
            meta = {
                "schema": SCHEMA_VERSION,
                "evidence_mode": EVIDENCE_MODE,
                "evidence_tier": EVIDENCE_TIER,
                "run_id": self._run_id,
                "generation": self._generation,
                "opened_at": datetime.now(timezone.utc).isoformat(),
                "compatibility": {
                    "scientific_v2_tiered": "preserved_separately",
                    "v3_additive": True,
                },
            }
            if extra_meta:
                meta.update(extra_meta)
            self._write_meta_unlocked(meta)

    def _queue_depth(self) -> int:
        return sum(len(v) for v in self._bufs.values())

    def _write_meta_unlocked(self, meta: dict[str, Any] | None = None) -> None:
        payload = meta or {}
        if self.meta_path.is_file() and not meta:
            try:
                payload = json.loads(self.meta_path.read_text())
            except Exception:
                payload = {}
        payload.update({
            "schema": SCHEMA_VERSION,
            "evidence_mode": EVIDENCE_MODE,
            "evidence_tier": EVIDENCE_TIER,
            "run_id": self._run_id,
            "generation": self._generation,
            "counts": dict(self._counts),
            "ticks_captured": self._ticks_captured,
            "health": self.health,
            "coverage": self._coverage,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        self.meta_path.write_text(json.dumps(payload, indent=2, default=str))
        if self._identity_map is not None:
            self.identity_path.write_text(
                json.dumps(self._identity_map.to_dict(), indent=2, default=str)
            )

    def _flush_unlocked(self) -> None:
        try:
            for key, path in self._paths.items():
                buf = self._bufs[key]
                if not buf:
                    continue
                with path.open("a", encoding="utf-8") as f:
                    f.write("\n".join(buf))
                    f.write("\n")
                self._bufs[key] = []
            self._write_meta_unlocked()
        except Exception as exc:
            self._health = HEALTH_WRITE_FAILED
            self._health_detail = str(exc)
            raise

    def append_runtime_tick(self, runtime: Any) -> int:
        """Capture + enqueue receipts for the just-completed decision tick(s).

        Returns number of autonomous spines written. Raises / sets health on
        backpressure — never silently drops.
        """
        with self._lock:
            if not self._opened or self._identity_map is None:
                self.open(run_id=str(getattr(runtime, "run_id", "unknown")))
            if self._health == HEALTH_WRITE_FAILED:
                raise RuntimeError(f"V3 writer failed: {self._health_detail}")

            package = capture_v3_tick(
                runtime,
                run_id=self._run_id,
                identity_map=self._identity_map,
                generation=self._generation,
            )
            spines = package["spines"]
            if not spines:
                return 0
            # Monotonic guard on max decision tick in package
            max_tick = max(int(s["tick"]) for s in spines)
            if max_tick <= self._last_decision_tick:
                return 0

            depth = self._queue_depth()
            incoming = (
                len(package["spines"])
                + len(package["observations"])
                + len(package["decisions"])
                + len(package["motors"])
                + len(package["consequences"])
            )
            if depth + incoming > self.max_queue_lines:
                self._health = HEALTH_BACKPRESSURE
                self._health_detail = (
                    f"queue depth {depth}+{incoming} exceeds max {self.max_queue_lines}"
                )
                # Fail closed: do not drop; attempt flush then re-check
                self._flush_unlocked()
                depth = self._queue_depth()
                if depth + incoming > self.max_queue_lines:
                    self._health = HEALTH_INCOMPLETE
                    raise RuntimeError(self._health_detail)

            def _enq(key: str, rows: list[dict[str, Any]]) -> None:
                for row in rows:
                    self._bufs[key].append(_jsonl_line(row))
                    self._counts[key] += 1

            _enq("spine", package["spines"])
            _enq("observations", package["observations"])
            _enq("decisions", package["decisions"])
            _enq("motors", package["motors"])
            _enq("consequences", package["consequences"])
            self._coverage = package["coverage"]
            self._last_decision_tick = max_tick
            self._ticks_captured += 1
            self._peak_queue = max(self._peak_queue, self._queue_depth())

            if self._queue_depth() >= self.flush_every:
                self._flush_unlocked()
            return len([s for s in spines if s.get("decision_id")])

    def flush(self) -> None:
        with self._lock:
            self._flush_unlocked()

    def close(self) -> None:
        with self._lock:
            try:
                self._flush_unlocked()
            finally:
                self._opened = False
