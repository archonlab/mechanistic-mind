\
"""Update 4.2 LONG-RUN research telemetry with episode aggregation.

FULL TRACE: ordinary JSONLSink / PsychologyObserver.
LONG-RUN: this sink stores compact episode summaries + boundary/periodic snapshots.
"""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from mechanistic_mind.observer.models import RunMetadata, RunSummary, TickRecord, to_plain


def _action_kind(record: TickRecord) -> str:
    actions = record.actions or {}
    if isinstance(actions, dict) and actions:
        raw = next(iter(actions.values()))
        if isinstance(raw, dict):
            return str(raw.get("kind") or "UNKNOWN")
        return str(raw)
    return "UNKNOWN"


def _body(record: TickRecord, agent_id: str = "A001") -> dict[str, Any]:
    after = record.state_after if isinstance(record.state_after, dict) else {}
    bodies = {}
    # common layouts
    world = after.get("world") if isinstance(after.get("world"), dict) else {}
    variables = world.get("variables") if isinstance(world.get("variables"), dict) else after.get("variables") if isinstance(after.get("variables"), dict) else {}
    if isinstance(variables, dict):
        bodies = variables.get("bodies") if isinstance(variables.get("bodies"), dict) else {}
    row = bodies.get(agent_id) if isinstance(bodies, dict) else {}
    return row if isinstance(row, dict) else {}


def _psyche_working(record: TickRecord, agent_id: str = "A001") -> dict[str, Any]:
    after = record.state_after if isinstance(record.state_after, dict) else {}
    agents = after.get("agents") if isinstance(after.get("agents"), dict) else {}
    agent = agents.get(agent_id) if isinstance(agents, dict) else {}
    if not isinstance(agent, dict):
        return {}
    ms = agent.get("mechanism_states") if isinstance(agent.get("mechanism_states"), dict) else {}
    for st in ms.values():
        if not isinstance(st, dict):
            continue
        psyche = st.get("psyche") if isinstance(st.get("psyche"), dict) else st
        if isinstance(psyche, dict) and isinstance(psyche.get("working"), dict):
            return psyche["working"]
    return {}


def _extract_tick_metrics(record: TickRecord) -> dict[str, Any]:
    body = _body(record)
    working = _psyche_working(record)
    gen = working.get("sensorimotor_generation") if isinstance(working.get("sensorimotor_generation"), dict) else {}
    sel = working.get("last_selection") if isinstance(working.get("last_selection"), dict) else {}
    cue_summary = gen.get("cue_summary") if isinstance(gen.get("cue_summary"), dict) else {}
    retrieval = gen.get("retrieval_match") if isinstance(gen.get("retrieval_match"), dict) else {}
    return {
        "tick": int(record.tick),
        "action": _action_kind(record),
        "body": {
            "energy_reserve": body.get("energy_reserve"),
            "hydration": body.get("hydration"),
            "fatigue": body.get("fatigue"),
            "mass_kg": body.get("mass_kg"),
            "activity_load": body.get("activity_load"),
            "damage": body.get("damage"),
            "consecutive_wait_ticks": body.get("consecutive_wait_ticks"),
            "last_daily_metabolic_balance": body.get("last_daily_metabolic_balance"),
        },
        "cue_mode": gen.get("cue_mode"),
        "perceptual_token_count": cue_summary.get("perceptual_token_count"),
        "retrieval_match": retrieval,
        "cognitive_depth": gen.get("cognitive_depth"),
        "cognitive_depth_status": gen.get("cognitive_depth_status"),
        "local_experience_maturity": gen.get("local_experience_maturity"),
        "developmental_stage": gen.get("developmental_stage"),
        "developmental_gate_factor": gen.get("developmental_gate_factor"),
        "selection_reason": sel.get("reason"),
        "decision_source": sel.get("decision_source"),
        "selection_tie": sel.get("tie"),
        "selection_score": sel.get("score"),
        "provenance": "exact",
    }


@dataclass
class LongRunResearchSink:
    """Aggregates stable same-action stretches; keeps event-boundary detail."""

    path: Path
    snapshot_every: int = 50
    boundary_window: int = 2
    agent_id: str = "A001"

    _handle: Any = field(default=None, init=False, repr=False)
    _episode: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _last_metrics: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _tick_count: int = field(default=0, init=False)
    _bytes_written: int = field(default=0, init=False)
    _episodes_closed: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("w", encoding="utf-8")

    def write_run_metadata(self, metadata: RunMetadata) -> None:
        payload = {
            "record_type": "run_metadata",
            "telemetry_mode": "LONG_RUN",
            "snapshot_every": self.snapshot_every,
            "boundary_window": self.boundary_window,
            "payload": to_plain(metadata),
        }
        self._write(payload)

    def write_tick(self, record: TickRecord) -> None:
        metrics = _extract_tick_metrics(record)
        self._tick_count += 1
        action = metrics["action"]
        # threshold crossings / decision changes force snapshot
        boundary = False
        reasons: list[str] = []
        if self._last_metrics is None:
            boundary = True
            reasons.append("run_start")
        else:
            if action != self._last_metrics.get("action"):
                boundary = True
                reasons.append("action_transition")
            prev_b = self._last_metrics.get("body") or {}
            cur_b = metrics.get("body") or {}
            for key, label in (
                ("energy_reserve", "energy_zero"),
                ("hydration", "hydration_zero"),
            ):
                pv, cv = prev_b.get(key), cur_b.get(key)
                if isinstance(pv, (int, float)) and isinstance(cv, (int, float)):
                    if pv > 1e-12 and cv <= 1e-12:
                        boundary = True
                        reasons.append(label)
            if self._last_metrics.get("decision_source") != metrics.get("decision_source"):
                boundary = True
                reasons.append("decision_source_change")
            if self._last_metrics.get("developmental_stage") != metrics.get(
                "developmental_stage"
            ):
                boundary = True
                reasons.append("stage_change")

        if self._episode is None:
            self._episode = self._new_episode(metrics)
        elif action != self._episode["action"]:
            self._close_episode(end_metrics=self._last_metrics, reason="action_transition")
            self._episode = self._new_episode(metrics)

        self._update_episode(metrics)

        periodic = (int(metrics["tick"]) % self.snapshot_every) == 0
        if boundary or periodic:
            self._write(
                {
                    "record_type": "tick_snapshot",
                    "provenance": "exact" if boundary else "sampled",
                    "boundary_reasons": reasons,
                    "payload": metrics,
                }
            )
        self._last_metrics = metrics

    def write_run_summary(self, summary: RunSummary) -> None:
        if self._episode is not None and self._last_metrics is not None:
            self._close_episode(end_metrics=self._last_metrics, reason="run_end")
        self._write(
            {
                "record_type": "run_summary",
                "payload": to_plain(summary),
                "telemetry_stats": {
                    "ticks": self._tick_count,
                    "episodes_closed": self._episodes_closed,
                    "bytes_written": self._bytes_written,
                },
            }
        )
        self.close()

    def write_run_completed(self, payload: dict[str, Any] | None = None) -> None:
        if self._episode is not None and self._last_metrics is not None:
            self._close_episode(end_metrics=self._last_metrics, reason="run_end")
        self._write(
            {
                "record_type": "run_completed",
                "payload": payload or {},
                "telemetry_stats": {
                    "ticks": self._tick_count,
                    "episodes_closed": self._episodes_closed,
                    "bytes_written": self._bytes_written,
                },
            }
        )
        self.close()

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def _new_episode(self, metrics: dict[str, Any]) -> dict[str, Any]:
        body = metrics.get("body") or {}
        return {
            "action": metrics["action"],
            "start_tick": metrics["tick"],
            "end_tick": metrics["tick"],
            "duration": 1,
            "body_start": deepcopy(body),
            "body_end": deepcopy(body),
            "energy_min": body.get("energy_reserve"),
            "energy_max": body.get("energy_reserve"),
            "hydration_min": body.get("hydration"),
            "hydration_max": body.get("hydration"),
            "fatigue_min": body.get("fatigue"),
            "fatigue_max": body.get("fatigue"),
            "depth_start": metrics.get("cognitive_depth"),
            "depth_end": metrics.get("cognitive_depth"),
            "maturity_start": metrics.get("local_experience_maturity"),
            "maturity_end": metrics.get("local_experience_maturity"),
            "token_sum": float(metrics.get("perceptual_token_count") or 0),
            "retrieval_true": int(
                bool((metrics.get("retrieval_match") or {}).get("perceptual_features"))
            ),
            "selection_reasons": {str(metrics.get("selection_reason") or "UNKNOWN"): 1},
            "provenance": "aggregated",
        }

    def _update_episode(self, metrics: dict[str, Any]) -> None:
        assert self._episode is not None
        ep = self._episode
        body = metrics.get("body") or {}
        ep["end_tick"] = metrics["tick"]
        ep["duration"] = int(ep["end_tick"]) - int(ep["start_tick"]) + 1
        ep["body_end"] = deepcopy(body)
        for key, lo, hi in (
            ("energy_reserve", "energy_min", "energy_max"),
            ("hydration", "hydration_min", "hydration_max"),
            ("fatigue", "fatigue_min", "fatigue_max"),
        ):
            val = body.get(key)
            if isinstance(val, (int, float)):
                cur_lo = ep.get(lo)
                cur_hi = ep.get(hi)
                ep[lo] = val if cur_lo is None else min(float(cur_lo), float(val))
                ep[hi] = val if cur_hi is None else max(float(cur_hi), float(val))
        ep["depth_end"] = metrics.get("cognitive_depth")
        ep["maturity_end"] = metrics.get("local_experience_maturity")
        ep["token_sum"] += float(metrics.get("perceptual_token_count") or 0)
        if (metrics.get("retrieval_match") or {}).get("perceptual_features"):
            ep["retrieval_true"] += 1
        reason = str(metrics.get("selection_reason") or "UNKNOWN")
        ep["selection_reasons"][reason] = int(ep["selection_reasons"].get(reason, 0)) + 1

    def _close_episode(self, *, end_metrics: dict[str, Any], reason: str) -> None:
        assert self._episode is not None
        ep = dict(self._episode)
        ep["close_reason"] = reason
        ep["mean_perceptual_tokens"] = (
            ep["token_sum"] / ep["duration"] if ep["duration"] else 0.0
        )
        self._write({"record_type": "action_episode", "provenance": "aggregated", "payload": ep})
        self._episodes_closed += 1
        self._episode = None

    def _write(self, payload: dict[str, Any]) -> None:
        assert self._handle is not None
        line = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        self._handle.write(line + "\n")
        self._bytes_written += len(line) + 1
