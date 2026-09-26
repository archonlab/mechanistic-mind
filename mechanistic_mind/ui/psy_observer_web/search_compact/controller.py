"""Bounded rolling evidence window + factual triggers + candidate packages."""
from __future__ import annotations

import json
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque

from . import (
    ANALYZER_COMPAT_CANDIDATE,
    ANALYZER_COMPAT_COMPACT_ONLY,
    DEFAULT_MAX_CANDIDATES,
    DEFAULT_POST_WINDOW,
    DEFAULT_PRE_WINDOW,
    DEFAULT_TRIGGER_COOLDOWN,
)
from .metrics import CompactMetrics


TriggerFn = Callable[[int, Any, list[dict], CompactMetrics], dict[str, Any] | None]


@dataclass
class RollingEvidenceWindow:
    pre: int = DEFAULT_PRE_WINDOW
    post: int = DEFAULT_POST_WINDOW
    _buf: Deque[dict[str, Any]] = field(default_factory=deque)

    def __post_init__(self) -> None:
        self._buf = deque(maxlen=max(1, int(self.pre) + 1))

    def push(self, record: dict[str, Any]) -> None:
        self._buf.append(record)

    def snapshot_pre(self) -> list[dict[str, Any]]:
        return list(self._buf)

    def size(self) -> int:
        return len(self._buf)


@dataclass
class CandidateRecord:
    candidate_id: str
    run_id: str
    seed: int
    config_fingerprint: str | None
    trigger_type: str
    trigger_tick: int
    trigger_values: dict[str, Any]
    pre_window_range: tuple[int, int]
    post_window_range: tuple[int, int]
    metrics_at_trigger: dict[str, Any]
    evidence: list[dict[str, Any]]
    analyzer_compat: str = ANALYZER_COMPAT_CANDIDATE
    preserved: bool = True
    preserve_failure: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "run_id": self.run_id,
            "seed": self.seed,
            "config_fingerprint": self.config_fingerprint,
            "trigger_type": self.trigger_type,
            "trigger_tick": self.trigger_tick,
            "trigger_values": self.trigger_values,
            "pre_window_range": list(self.pre_window_range),
            "post_window_range": list(self.post_window_range),
            "metrics_at_trigger": self.metrics_at_trigger,
            "evidence_n": len(self.evidence),
            "evidence": self.evidence,
            "analyzer_compat": self.analyzer_compat,
            "preserved": self.preserved,
            "preserve_failure": self.preserve_failure,
        }


def trigger_action_count_threshold(
    *,
    action_prefix: str = "MOVE:",
    threshold: int = 5,
) -> TriggerFn:
    """Deterministic test trigger — not an intelligence detector."""

    def _fn(tick: int, runtime: Any, events: list[dict], metrics: CompactMetrics) -> dict | None:
        total = sum(v for k, v in metrics.action_counts.items() if str(k).startswith(action_prefix))
        if total >= threshold and total - threshold < 2:  # fire near crossing
            # Fire once when crossing: only if previous was below
            prev = total - 1
            if prev < threshold <= total:
                return {
                    "type": "ACTION_COUNT_THRESHOLD",
                    "action_prefix": action_prefix,
                    "threshold": threshold,
                    "value": total,
                    "tick": tick,
                }
        return None

    return _fn


def trigger_first_event_type(event_substr: str) -> TriggerFn:
    seen: set[str] = set()

    def _fn(tick: int, runtime: Any, events: list[dict], metrics: CompactMetrics) -> dict | None:
        for ev in events:
            et = str(ev.get("type") or ev.get("event_type") or "")
            if event_substr in et and et not in seen:
                seen.add(et)
                return {"type": "FIRST_EVENT_TYPE", "event_type": et, "tick": tick}
        return None

    return _fn


@dataclass
class SearchCompactController:
    """Observer-side compact evidence — never mutates runtime / RNG."""

    run_id: str
    seed: int
    config_fingerprint: str | None = None
    pre_window: int = DEFAULT_PRE_WINDOW
    post_window: int = DEFAULT_POST_WINDOW
    max_candidates: int = DEFAULT_MAX_CANDIDATES
    cooldown: int = DEFAULT_TRIGGER_COOLDOWN
    triggers: list[TriggerFn] = field(default_factory=list)
    metrics: CompactMetrics = field(default_factory=CompactMetrics)
    window: RollingEvidenceWindow | None = None
    candidates: list[CandidateRecord] = field(default_factory=list)
    candidates_dropped_by_cap: int = 0
    _active_post: list[dict[str, Any]] = field(default_factory=list)
    _last_trigger_tick: int = -10**9
    _pending_posts: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.window = RollingEvidenceWindow(pre=self.pre_window, post=self.post_window)
        if not self.triggers:
            self.triggers = [trigger_action_count_threshold(threshold=8)]

    def on_tick(
        self,
        *,
        tick: int,
        runtime: Any,
        events: list[dict] | None = None,
        digest_fragment: dict[str, Any] | None = None,
    ) -> None:
        evs = list(events or [])
        self.metrics.observe_tick(tick=tick, runtime=runtime, events=evs)
        rec = {
            "tick": int(tick),
            "events": [
                {
                    "type": e.get("type") or e.get("event_type"),
                    "agent_id": e.get("agent_id"),
                    "tick": e.get("tick", tick),
                }
                for e in evs[:32]
            ],
            "digest_fragment": digest_fragment or {},
        }
        assert self.window is not None
        self.window.push(rec)

        # Fill post-windows for open candidates
        still: list[dict[str, Any]] = []
        for pending in self._pending_posts:
            pending["evidence"].append(rec)
            if int(tick) >= int(pending["post_end"]):
                cand = pending["candidate"]
                cand.evidence = pending["evidence"]
                cand.post_window_range = (pending["post_start"], int(tick))
                self.candidates.append(cand)
            else:
                still.append(pending)
        self._pending_posts = still

        if int(tick) - self._last_trigger_tick < int(self.cooldown):
            return
        for trig in self.triggers:
            hit = trig(int(tick), runtime, evs, self.metrics)
            if not hit:
                continue
            self._last_trigger_tick = int(tick)
            if len(self.candidates) + len(self._pending_posts) >= int(self.max_candidates):
                self.candidates_dropped_by_cap += 1
                return
            pre = self.window.snapshot_pre()
            pre_ticks = [r["tick"] for r in pre] or [tick]
            cand = CandidateRecord(
                candidate_id=f"cand-{uuid.uuid4().hex[:12]}",
                run_id=self.run_id,
                seed=int(self.seed),
                config_fingerprint=self.config_fingerprint,
                trigger_type=str(hit.get("type")),
                trigger_tick=int(tick),
                trigger_values=dict(hit),
                pre_window_range=(min(pre_ticks), max(pre_ticks)),
                post_window_range=(int(tick), int(tick) + int(self.post_window)),
                metrics_at_trigger=self.metrics.snapshot(),
                evidence=list(pre),
                analyzer_compat=ANALYZER_COMPAT_CANDIDATE,
            )
            self._pending_posts.append({
                "candidate": cand,
                "evidence": list(pre),
                "post_start": int(tick),
                "post_end": int(tick) + int(self.post_window),
            })
            return  # one trigger evaluation burst per tick

    def finalize(self) -> dict[str, Any]:
        # Flush incomplete post windows as preserved-with-note
        for pending in self._pending_posts:
            cand: CandidateRecord = pending["candidate"]
            cand.evidence = pending["evidence"]
            cand.preserve_failure = "RUN_ENDED_BEFORE_POST_WINDOW_COMPLETE"
            cand.preserved = True
            self.candidates.append(cand)
        self._pending_posts.clear()
        return {
            "run_id": self.run_id,
            "seed": self.seed,
            "config_fingerprint": self.config_fingerprint,
            "metrics": self.metrics.snapshot(),
            "metrics_ram_bytes_estimate": self.metrics.ram_bytes_estimate(),
            "candidates": [c.to_dict() for c in self.candidates],
            "candidates_dropped_by_cap": self.candidates_dropped_by_cap,
            "max_candidates": self.max_candidates,
            "pre_window": self.pre_window,
            "post_window": self.post_window,
            "cooldown": self.cooldown,
            "analyzer_compat_default": ANALYZER_COMPAT_COMPACT_ONLY,
            "evidence_mode": "SEARCH_COMPACT",
        }
