"""Finite experience memory, compact evidence capture, and measurements.

The mechanism sees only ``MechanismContext.observation`` and its own namespace.
The evidence observer is downstream of the engine and has no path back into it.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
from hashlib import sha256
from math import log2, sqrt
from pathlib import Path
import json
import resource
from time import perf_counter_ns
from typing import Any, Iterable

from mechanistic_mind.agent import Action
from mechanistic_mind.mechanisms import (
    ActionProposal,
    Mechanism,
    MechanismContext,
    MechanismOutput,
    StateUpdate,
)
from mechanistic_mind.observer import RunMetadata, RunSummary, canonical_json, to_plain


class MemoryMode(str, Enum):
    RAW = "RAW"
    COMPRESSED = "COMPRESSED"
    FORGETFUL = "FORGETFUL"


class RetrievalMode(str, Enum):
    HIERARCHICAL_BOUNDED = "HIERARCHICAL_BOUNDED"
    LEGACY_UNBOUNDED = "LEGACY_UNBOUNDED"


@dataclass(frozen=True, slots=True)
class CognitiveBudget:
    max_pattern_candidates: int = 4
    max_exception_candidates: int = 4
    max_episode_candidates: int = 8
    max_total_memory_candidates: int = 12

    def __post_init__(self) -> None:
        values = asdict(self)
        if any(int(value) < 0 for value in values.values()):
            raise ValueError("cognitive budget limits must be non-negative")
        if self.max_total_memory_candidates < 1:
            raise ValueError("total cognitive budget must be positive")


@dataclass(frozen=True, slots=True)
class CompressionConfig:
    mode: MemoryMode = MemoryMode.COMPRESSED
    episodic_capacity: int = 64
    raw_episodic_capacity: int = 5000
    pattern_capacity: int = 256
    candidate_capacity: int = 256
    min_pattern_observations: int = 3
    low_error_threshold: float = 0.08
    high_error_threshold: float = 0.35
    surprise_retention_ticks: int = 40
    invalidation_streak: int = 3
    pattern_decay: float = 0.9995
    confidence_scale: float = 4.0
    exploration_gain: float = 2.0
    retrieval_mode: RetrievalMode = RetrievalMode.HIERARCHICAL_BOUNDED
    cognitive_budget: CognitiveBudget = field(default_factory=CognitiveBudget)
    pattern_min_confidence: float = 0.45
    pattern_min_samples: float = 3.0
    representative_capacity: int = 2
    exception_capacity: int = 3
    episode_bucket_capacity: int = 16
    cue_schema_version: str = "bounded-retrieval-cue-v1"
    # Optional developmental gating of retrieval trust/budget. None/disabled
    # preserves prior architecture.
    developmental: dict | None = None
    perceptual_dynamics_enabled: bool = False
    perceptual_activation_decay: float = 0.86
    perceptual_activation_gain: float = 0.55
    perceptual_expectation_min_confidence: float = 0.45
    perceptual_feature_capacity: int = 24
    # Agent-accessible physiological signal directions. These describe the
    # numerical body interface, not semantic object value.
    outcome_directions: tuple[tuple[str, float], ...] = (
        ("energy_signal", 1.0),
        ("hydration_signal", 1.0),
        ("fatigue_signal", -1.0),
        ("discomfort_signal", -1.0),
        ("effort_signal", -1.0),
        ("energy_delta", 1.0),
        ("hydration_delta", 1.0),
        ("fatigue_delta", -1.0),
        ("damage_delta", -1.0),
        ("progress_delta", 1.0),
    )

    def __post_init__(self) -> None:
        if self.episodic_capacity < 1 or self.raw_episodic_capacity < 1:
            raise ValueError("episodic capacities must be positive")
        if (
            self.pattern_capacity < 1
            or self.candidate_capacity < 1
            or self.min_pattern_observations < 2
        ):
            raise ValueError("pattern capacities/thresholds are invalid")
        if not 0.0 <= self.low_error_threshold <= self.high_error_threshold:
            raise ValueError("prediction-error thresholds are inconsistent")
        if not 0.0 < self.pattern_decay <= 1.0:
            raise ValueError("pattern_decay must be in (0, 1]")
        if not 0.0 <= self.pattern_min_confidence <= 1.0:
            raise ValueError("pattern_min_confidence must be in [0, 1]")
        if min(
            self.representative_capacity,
            self.exception_capacity,
            self.episode_bucket_capacity,
        ) < 1:
            raise ValueError("bounded stores must have positive capacities")
        if not 0.0 <= self.perceptual_activation_decay <= 1.0:
            raise ValueError("perceptual_activation_decay must be in [0, 1]")
        if self.perceptual_activation_gain < 0.0:
            raise ValueError("perceptual_activation_gain must be non-negative")

    @property
    def active_episode_capacity(self) -> int:
        return (
            self.raw_episodic_capacity
            if self.mode is MemoryMode.RAW
            else self.episodic_capacity
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["mode"] = self.mode.value
        payload["retrieval_mode"] = self.retrieval_mode.value
        return payload


def _numeric(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): float(item)
        for key, item in value.items()
        if isinstance(item, (int, float)) and not isinstance(item, bool)
    }


def _position(value: Any) -> tuple[int, int] | None:
    if (
        isinstance(value, (list, tuple))
        and len(value) == 2
        and all(isinstance(item, int) for item in value)
    ):
        return int(value[0]), int(value[1])
    return None


def _band(value: float) -> str:
    if value < 1.0 / 3.0:
        return "L"
    if value < 2.0 / 3.0:
        return "M"
    return "H"


def _perceived_ids(observation: dict[str, Any]) -> tuple[str, ...]:
    result: list[str] = []
    for field_name in ("visible_objects", "visible_obstacles"):
        rows = observation.get(field_name, [])
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            cue = row.get("cue_signature") or row.get("id")
            if cue is not None:
                result.append(str(cue))
    return tuple(sorted(set(result)))


def build_retrieval_cue(
    observation: dict[str, Any],
    *,
    schema_version: str = "bounded-retrieval-cue-v1",
) -> dict[str, Any]:
    """Construct one compact cue exclusively from agent-facing values."""
    signals = _numeric(observation.get("interoception"))
    fragments = []
    raw_fragments = observation.get("visual_fragments", [])
    if isinstance(raw_fragments, list):
        for row in raw_fragments:
            if not isinstance(row, dict):
                continue
            fragments.append(
                {
                    key: deepcopy(row[key])
                    for key in (
                        "kind",
                        "relative_position",
                        "distance",
                        "cue_signature",
                        "shape",
                        "size",
                        "color",
                        "opacity",
                        "brightness",
                        "signal",
                        "traversable",
                    )
                    if key in row
                }
            )
    if not fragments:
        fragments = [{"cue_signature": value} for value in _perceived_ids(observation)]
    response = observed_outcome(observation)
    cue = {
        "schema_version": schema_version,
        "context": str(observation.get("context") or "GENERIC"),
        "body_bands": {key: _band(value) for key, value in sorted(signals.items())},
        "visual_fragments": sorted(fragments, key=canonical_json),
        "recent_action": observation.get("last_action"),
        "response_fragment": {
            key: round(value, 3) for key, value in sorted(response.items())
        },
    }
    multimodal = observation.get("perceptual_context")
    if isinstance(multimodal, dict):
        cue["modalities"] = deepcopy(multimodal.get("modalities", {}))
        cue["perceptual_fragments"] = deepcopy(multimodal.get("fragments", []))
    return cue


def perceptual_features(cue: dict[str, Any], capacity: int = 24) -> tuple[str, ...]:
    """Bounded atomic feature tokens; combinations are never enumerated."""
    rows: list[str] = []
    modalities = cue.get("modalities", {})
    if isinstance(modalities, dict):
        rows.extend(f"M:{key}" for key, active in sorted(modalities.items()) if active)
    fragments = cue.get("perceptual_fragments", [])
    if isinstance(fragments, list):
        for item in fragments:
            if isinstance(item, dict):
                rows.append("F:" + canonical_json(item))
    if not rows:
        rows.extend("V:" + canonical_json(item) for item in cue.get("visual_fragments", []))
    return tuple(sorted(set(rows))[: max(1, int(capacity))])


def perceptual_mismatch(expected: Iterable[str], observed: Iterable[str]) -> float:
    a, b = set(expected), set(observed)
    if not a and not b:
        return 0.0
    return 1.0 - len(a & b) / max(1, len(a | b))


def context_signature(
    observation: dict[str, Any],
    *,
    schema_version: str = "bounded-retrieval-cue-v1",
) -> str:
    cue = build_retrieval_cue(observation, schema_version=schema_version)
    return _cue_bucket_signature(cue)


def _cue_bucket_signature(cue: dict[str, Any]) -> str:
    """Index on pre-outcome context; retain response as ranking evidence."""
    indexed = {
        key: deepcopy(cue.get(key))
        for key in (
            "schema_version",
            "context",
            "body_bands",
            "visual_fragments",
            "recent_action",
        )
    }
    if "modalities" in cue:
        indexed["modalities"] = deepcopy(cue.get("modalities"))
        indexed["perceptual_fragments"] = deepcopy(cue.get("perceptual_fragments"))
    return sha256(canonical_json(indexed).encode("utf-8")).hexdigest()[:24]


def action_signature(action: str, observation: dict[str, Any]) -> str:
    position = _position(observation.get("position"))
    if action.startswith("MOVE:") and position is not None:
        destination = _position_from_action(action)
        if destination is not None:
            return f"MOVE_DELTA:{destination[0]-position[0]},{destination[1]-position[1]}"
    if ":" in action:
        family, object_id, *_rest = action.split(":")
        if family in {"USE", "TAKE", "RELEASE", "PUSH"}:
            for row in observation.get("visible_objects", []):
                if isinstance(row, dict) and str(row.get("id")) == object_id:
                    return f"{family}_CUE:{row.get('cue_signature') or 'GENERIC_OBJECT'}"
    return action


def _position_from_action(action: str) -> tuple[int, int] | None:
    try:
        coordinates = action.split(":")[-1]
        x_text, y_text = coordinates.split(",", 1)
        return int(x_text), int(y_text)
    except (ValueError, IndexError):
        return None


def observed_outcome(observation: dict[str, Any]) -> dict[str, float]:
    effects = _numeric(observation.get("last_experienced_effects"))
    if effects:
        return effects
    value = observation.get("last_outcome")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {"scalar": float(value)}
    return {}


def prediction_error(actual: dict[str, float], expected: dict[str, float]) -> float:
    keys = set(actual) | set(expected)
    return (
        sum(abs(actual.get(key, 0.0) - expected.get(key, 0.0)) for key in keys)
        / max(1, len(keys))
    )


def _update_aggregate(record: dict[str, Any], outcome: dict[str, float], percept: Iterable[str] = ()) -> None:
    old_count = float(record.get("count", 0.0))
    new_count = old_count + 1.0
    means = _numeric(record.get("expected_outcomes"))
    m2 = _numeric(record.get("m2"))
    for key in sorted(set(means) | set(outcome)):
        value = float(outcome.get(key, 0.0))
        prior = float(means.get(key, 0.0))
        delta = value - prior
        updated = prior + delta / new_count
        means[key] = updated
        m2[key] = float(m2.get(key, 0.0)) + delta * (value - updated)
    record["count"] = new_count
    record["expected_outcomes"] = means
    record["m2"] = m2
    counts = {str(key): float(value) for key, value in record.get("percept_feature_counts", {}).items()}
    for feature in percept:
        counts[str(feature)] = counts.get(str(feature), 0.0) + 1.0
    record["percept_feature_counts"] = dict(sorted(counts.items(), key=lambda row: (-row[1], row[0]))[:24])
    record["expected_percept_features"] = sorted(
        key for key, value in record["percept_feature_counts"].items()
        if value / new_count >= 0.5
    )


def _variance(record: dict[str, Any]) -> float:
    count = float(record.get("count", 0.0))
    values = _numeric(record.get("m2"))
    if count <= 1.0 or not values:
        return 0.0
    return sum(value / (count - 1.0) for value in values.values()) / len(values)


def _confidence(record: dict[str, Any], scale: float) -> float:
    count = float(record.get("count", 0.0))
    return (count / (count + scale)) / (1.0 + _variance(record))


@dataclass(slots=True)
class RetrievalAccounting:
    budget: CognitiveBudget
    pattern_candidates_inspected: int = 0
    exception_candidates_inspected: int = 0
    episode_candidates_inspected: int = 0
    index_probes: int = 0
    stage_trace: list[str] = field(default_factory=list)

    @property
    def total_candidates_inspected(self) -> int:
        return (
            self.pattern_candidates_inspected
            + self.exception_candidates_inspected
            + self.episode_candidates_inspected
        )

    def remaining(self, stage: str) -> int:
        total = self.budget.max_total_memory_candidates - self.total_candidates_inspected
        per_stage = {
            "PATTERN": self.budget.max_pattern_candidates - self.pattern_candidates_inspected,
            "EXCEPTION": self.budget.max_exception_candidates - self.exception_candidates_inspected,
            "EPISODE": self.budget.max_episode_candidates - self.episode_candidates_inspected,
        }[stage]
        return max(0, min(total, per_stage))

    def inspect(self, stage: str) -> bool:
        if self.remaining(stage) <= 0:
            return False
        field_name = {
            "PATTERN": "pattern_candidates_inspected",
            "EXCEPTION": "exception_candidates_inspected",
            "EPISODE": "episode_candidates_inspected",
        }[stage]
        setattr(self, field_name, getattr(self, field_name) + 1)
        self.stage_trace.append(stage)
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_candidates_inspected": self.pattern_candidates_inspected,
            "exception_candidates_inspected": self.exception_candidates_inspected,
            "episode_candidates_inspected": self.episode_candidates_inspected,
            "total_candidates_inspected": self.total_candidates_inspected,
            "index_probes": self.index_probes,
            "stage_trace": list(self.stage_trace),
            "budget": asdict(self.budget),
        }


class ExperienceCompressionMechanism(Mechanism):
    """Generic outcome memory whose only inputs are current agent observations."""

    mechanism_id = "EXPERIENCE-COMPRESSION-V01"
    version = "0.2.0"

    def __init__(self, config: CompressionConfig | None = None) -> None:
        self.config = config or CompressionConfig()

    def _initial_memory(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "mode": self.config.mode.value,
            "episodes": [],
            "patterns": {},
            "candidates": {},
            "pattern_index": {},
            "exception_index": {},
            "episode_index": {},
            "episode_lookup": {},
            "novel_fragment_ids": {},
            "episode_sizes": {},
            "pattern_sizes": {},
            "approx_episode_bytes": 2,
            "approx_pattern_bytes": 2,
            "pending": None,
            "total_experiences": 0,
            "total_evictions": 0,
            "total_compressions": 0,
            "last_prediction_error": None,
            "last_decision_source": "NONE",
            "last_pattern_id": None,
            "perceptual_activation": 0.0,
            "last_perceptual_dynamics": {},
        }

    def process(self, context: MechanismContext) -> MechanismOutput:
        observation = deepcopy(context.observation.data)
        # MechanismRuntime already supplies an isolated deep copy of this
        # namespace. Mutating that private copy avoids a second O(memory) copy
        # while preserving the runtime's no-shared-mutation contract.
        memory = context.mechanism_state.get("memory")
        if not isinstance(memory, dict) or memory.get("mode") != self.config.mode.value:
            memory = self._initial_memory()
        else:
            self._migrate_memory(memory)
        self._update_developmental_gate(memory, context.tick)
        events: list[dict[str, Any]] = []

        cue = build_retrieval_cue(
            observation,
            schema_version=self.config.cue_schema_version,
        )
        current_features = perceptual_features(cue, self.config.perceptual_feature_capacity)
        pending = memory.get("pending")
        outcome = observed_outcome(observation)
        if isinstance(pending, dict) and outcome:
            self._retain_experience(memory, pending, outcome, context.tick, events, current_features)

        prior_activation = float(memory.get("perceptual_activation", 0.0))
        supported = bool(
            self.config.perceptual_dynamics_enabled
            and isinstance(pending, dict)
            and float(pending.get("perceptual_expectation_confidence", 0.0))
            >= self.config.perceptual_expectation_min_confidence
            and pending.get("expected_percept_features")
        )
        mismatch = (
            perceptual_mismatch(pending.get("expected_percept_features", ()), current_features)
            if supported and isinstance(pending, dict) else None
        )
        activation = max(0.0, min(1.0,
            prior_activation * self.config.perceptual_activation_decay
            + (float(mismatch) * self.config.perceptual_activation_gain if mismatch is not None else 0.0)
        ))
        memory["perceptual_activation"] = activation
        memory["last_perceptual_dynamics"] = {
            "unknown": not supported,
            "expectation_supported": supported,
            "expectation_confidence": float(pending.get("perceptual_expectation_confidence", 0.0)) if isinstance(pending, dict) else 0.0,
            "mismatch": mismatch,
            "activation_before": prior_activation,
            "perceptual_activation": activation,
            "active_modalities": sorted(key for key, value in (cue.get("modalities") or {}).items() if value),
        }
        if mismatch is not None and mismatch >= self.config.high_error_threshold:
            events.append({"type": "expectation_violation", "tick": context.tick, "mismatch": mismatch})
        if abs(activation - prior_activation) >= 0.2:
            events.append({"type": "perceptual_activation_transition", "tick": context.tick, "before": prior_activation, "after": activation})

        actions = tuple(str(item) for item in observation.get("available_actions", ()))
        if not actions:
            actions = ("WAIT",)
        signature = _cue_bucket_signature(cue)
        action_signatures = {
            action: action_signature(action, observation) for action in actions
        }
        retrieval_started = perf_counter_ns()
        if self.config.retrieval_mode is RetrievalMode.HIERARCHICAL_BOUNDED:
            predictions, retrieval = self._retrieve_bounded(
                memory,
                signature,
                action_signatures,
                context.tick,
            )
        else:
            predictions, retrieval = self._retrieve_legacy(
                memory,
                signature,
                action_signatures,
                context.tick,
            )
        retrieval_time_ns = perf_counter_ns() - retrieval_started
        decision_started = perf_counter_ns()
        selected = self._select(actions, predictions, context.random_value)
        decision_time_ns = perf_counter_ns() - decision_started
        selected_prediction = predictions[selected]
        candidate_diagnostics = []
        directions = dict(self.config.outcome_directions)
        for candidate_action in actions:
            row = predictions[candidate_action]
            expected = _numeric(row.get("expected"))
            learned = self._outcome_value(expected)
            uncertainty = 1.0 / sqrt(float(row.get("samples", 0.0)) + 1.0)
            candidate_diagnostics.append({
                "action": candidate_action,
                "available": True,
                "predicted_consequence": expected,
                "confidence": float(row.get("confidence", 0.0)),
                "unknown": row.get("evidence_status") == "INSUFFICIENT_EVIDENCE",
                "uncertainty": uncertainty,
                "physiological_cost": sum(value * directions.get(key, 0.0) for key, value in expected.items()),
                "effort_cost": expected.get("effort_signal", 0.0) * directions.get("effort_signal", -1.0),
                "learned_contribution": learned,
                "internal_state_contribution": 0.0,
                "total_score": learned + self.config.exploration_gain * uncertainty,
                "selected": candidate_action == selected,
                "retrieval_stage": row.get("source", "UNKNOWN"),
            })
        retrieval.update(
            {
                "selected_prediction_source": selected_prediction.get("source"),
                "selected_prediction_confidence": float(
                    selected_prediction.get("confidence", 0.0)
                ),
                "selected_prediction_match_score": selected_prediction.get(
                    "match_score"
                ),
                "selected_prediction_value": self._outcome_value(
                    _numeric(selected_prediction.get("expected"))
                ),
                "selected_evidence_status": selected_prediction.get(
                    "evidence_status"
                ),
                "selected_pattern_id": selected_prediction.get("pattern_id"),
            }
        )
        memory["last_decision_source"] = selected_prediction["source"]
        memory["last_pattern_id"] = selected_prediction.get("pattern_id")
        memory["pending"] = {
            "tick": context.tick,
            "cue": cue,
            "context_signature": signature,
            "action": selected,
            "action_signature": action_signature(selected, observation),
            "predicted_outcome": deepcopy(selected_prediction.get("expected", {})),
            "expected_percept_features": list(selected_prediction.get("expected_percept_features", ())),
            "perceptual_expectation_confidence": float(selected_prediction.get("confidence", 0.0)),
            "retrieval_provenance": {
                "source": selected_prediction.get("source"),
                "confidence": selected_prediction.get("confidence"),
                "pattern_id": selected_prediction.get("pattern_id"),
            },
            "body_state_signature": {
                key: _band(value)
                for key, value in _numeric(observation.get("interoception")).items()
            },
            "perceived_identifiers": list(_perceived_ids(observation)),
            "position": list(_position(observation.get("position")))
            if _position(observation.get("position")) is not None
            else None,
        }

        episode_bytes = int(memory.get("approx_episode_bytes", 2))
        pattern_bytes = int(memory.get("approx_pattern_bytes", 2))
        summary = {
            "mode": self.config.mode.value,
            "episodic_count": len(memory["episodes"]),
            "episodic_capacity": self.config.active_episode_capacity,
            "pattern_count": len(memory["patterns"]),
            "candidate_count": len(memory["candidates"]),
            "novel_fragment_count": len(memory["novel_fragment_ids"]),
            "total_experiences": memory["total_experiences"],
            "total_evictions": memory["total_evictions"],
            "total_compressions": memory["total_compressions"],
            "compression_ratio": (
                memory["total_experiences"]
                / max(1, len(memory["episodes"]) + len(memory["patterns"]))
            ),
            "last_prediction_error": memory.get("last_prediction_error"),
            "perceptual_dynamics": deepcopy(memory.get("last_perceptual_dynamics", {})),
            "decision_source": selected_prediction["source"],
            "pattern_id": selected_prediction.get("pattern_id"),
            "episode_bytes": episode_bytes,
            "pattern_bytes": pattern_bytes,
            "agent_memory_bytes": episode_bytes + pattern_bytes,
            "retrieved_pattern_confidences": [
                float(row["confidence"])
                for row in predictions.values()
                if row.get("pattern_id") is not None
            ],
            "retrieval": {
                key: deepcopy(value)
                for key, value in retrieval.items()
                if not str(key).endswith("_time_ns")
            },
            "retention": deepcopy(memory.get("last_retention", {})),
            "index_stats": {
                "pattern_buckets": len(memory["pattern_index"]),
                "exception_buckets": len(memory["exception_index"]),
                "episode_buckets": len(memory["episode_index"]),
            },
        }
        return MechanismOutput(
            proposals=(
                ActionProposal(
                    source_mechanism=self.mechanism_id,
                    action=Action(selected),
                    priority=100,
                    metadata={
                        "memory_mode": self.config.mode.value,
                        "decision_source": selected_prediction["source"],
                        "pattern_id": selected_prediction.get("pattern_id"),
                    },
                ),
            ),
            state_updates=(StateUpdate.mechanism_state("memory", memory),),
            signals={
                "memory_summary": summary,
                "memory_events": events,
                "predictions": {selected: predictions[selected]},
                "selected_action": selected,
                "retrieval": {
                    **retrieval,
                    "retrieval_time_ns": retrieval_time_ns,
                    "decision_time_ns": decision_time_ns,
                },
                "retention": deepcopy(memory.get("last_retention", {})),
                "candidate_diagnostics": (
                    candidate_diagnostics
                    if context.tick % 50 == 0 or events
                    else []
                ),
            },
            telemetry={
                "memory_config": self.config.to_dict(),
                "observer_history_access": False,
            },
        )

    def _migrate_memory(self, memory: dict[str, Any]) -> None:
        """One-time deterministic migration for pre-index saved memories."""
        if int(memory.get("schema_version", 0)) >= 2:
            memory.setdefault("novel_fragment_ids", {})
            return
        memory.setdefault("patterns", {})
        memory.setdefault("episodes", [])
        memory["pattern_index"] = {
            str(key): [str(key)] for key in memory["patterns"]
        }
        memory["exception_index"] = {
            str(key): row.get("exceptions", [])
            for key, row in memory["patterns"].items()
            if isinstance(row, dict) and row.get("exceptions")
        }
        memory["episode_lookup"] = {}
        memory["episode_index"] = {}
        memory["novel_fragment_ids"] = {}
        for index, episode in enumerate(memory["episodes"]):
            episode_id = str(
                episode.get("episode_id")
                or f"MIGRATED-{int(episode.get('tick', 0)):08d}-{index:08d}"
            )
            episode["episode_id"] = episode_id
            memory["episode_lookup"][episode_id] = episode
            error = episode.get("prediction_error")
            if error is None or float(error) >= self.config.high_error_threshold:
                memory["novel_fragment_ids"][episode_id] = True
            key = (
                f"{episode.get('context_signature')}\u241f"
                f"{episode.get('action_signature')}"
            )
            memory["episode_index"].setdefault(key, []).append(episode_id)
        memory["episode_sizes"] = {
            str(row["episode_id"]): len(canonical_json(row))
            for row in memory["episodes"]
        }
        memory["pattern_sizes"] = {
            str(key): len(canonical_json(row))
            for key, row in memory["patterns"].items()
        }
        memory["approx_episode_bytes"] = 2 + sum(memory["episode_sizes"].values())
        memory["approx_pattern_bytes"] = 2 + sum(memory["pattern_sizes"].values())
        memory["schema_version"] = 2

    def _retain_experience(
        self,
        memory: dict[str, Any],
        pending: dict[str, Any],
        outcome: dict[str, float],
        tick: int,
        events: list[dict[str, Any]],
        observed_percept_features: Iterable[str] = (),
    ) -> None:
        memory["total_experiences"] = int(memory["total_experiences"]) + 1
        key = f"{pending['context_signature']}\u241f{pending['action_signature']}"
        pattern = memory["patterns"].get(key)
        expected = _numeric(pattern.get("expected_outcomes")) if isinstance(pattern, dict) else {}
        error = prediction_error(outcome, expected) if expected else None
        memory["last_prediction_error"] = error
        episode = {
            "episode_id": f"EP-{int(pending['tick']):08d}-{int(memory['total_experiences']):08d}",
            "tick": int(pending["tick"]),
            "cue": deepcopy(pending.get("cue", {})),
            "context_signature": pending["context_signature"],
            "action": pending["action"],
            "action_signature": pending["action_signature"],
            "body_state_signature": deepcopy(pending["body_state_signature"]),
            "perceived_identifiers": list(pending["perceived_identifiers"]),
            "position": deepcopy(pending["position"]),
            "outcome": deepcopy(outcome),
            "predicted_outcome": deepcopy(pending.get("predicted_outcome", {})),
            "retrieval_provenance": deepcopy(pending.get("retrieval_provenance", {})),
            "prediction_error": error,
            "observed_percept_features": list(observed_percept_features),
            "novelty": 1.0 / sqrt(float(memory["total_experiences"])),
            "protect_until": (
                tick + self.config.surprise_retention_ticks
                if error is not None and error >= self.config.high_error_threshold
                else tick
            ),
        }
        memory["episodes"].append(episode)
        episode_id = episode["episode_id"]
        # The list and lookup deliberately share the same private record. The
        # runtime's graph-aware deepcopy preserves that alias while avoiding a
        # second physical copy of every episode in the mechanism namespace.
        memory["episode_lookup"][episode_id] = episode
        if error is None or error >= self.config.high_error_threshold:
            memory["novel_fragment_ids"][episode_id] = True
        episode_size = len(canonical_json(episode))
        memory["episode_sizes"][episode_id] = episode_size
        memory["approx_episode_bytes"] = int(memory["approx_episode_bytes"]) + episode_size
        episode_bucket = memory["episode_index"].setdefault(key, [])
        episode_bucket.append(episode_id)
        if len(episode_bucket) > self.config.episode_bucket_capacity:
            del episode_bucket[0 : len(episode_bucket) - self.config.episode_bucket_capacity]
        retention_reason = "UNEXPLAINED"

        if self.config.mode is MemoryMode.COMPRESSED:
            if isinstance(pattern, dict):
                if error is not None and error >= self.config.high_error_threshold:
                    pattern["surprise_streak"] = int(pattern.get("surprise_streak", 0)) + 1
                    events.append({"type": "pattern_weakened", "pattern_id": pattern["pattern_id"], "tick": tick, "prediction_error": error})
                else:
                    pattern["surprise_streak"] = 0
                if int(pattern.get("surprise_streak", 0)) >= self.config.invalidation_streak:
                    events.append({"type": "pattern_invalidated", "pattern_id": pattern["pattern_id"], "tick": tick})
                    pattern.update({"count": 0.0, "expected_outcomes": {}, "m2": {}, "surprise_streak": 0, "first_seen": tick})
                _update_aggregate(pattern, outcome, observed_percept_features)
                pattern["last_updated"] = tick
                events.append({"type": "pattern_reinforced", "pattern_id": pattern["pattern_id"], "tick": tick, "prediction_error": error})
                if error is not None and error <= self.config.low_error_threshold:
                    retention_reason = "WELL_EXPLAINED_PATTERN_UPDATE"
                    representatives = list(pattern.get("representatives", []))
                    representatives.append(self._fragment(episode))
                    pattern["representatives"] = representatives[-self.config.representative_capacity :]
                    self._remove_episode(memory, episode)
                    memory["total_compressions"] = int(memory["total_compressions"]) + 1
                elif error is not None:
                    retention_reason = (
                        "HIGH_ERROR_EXCEPTION"
                        if error >= self.config.high_error_threshold
                        else "PARTIAL_ERROR_EXCEPTION"
                    )
                    exceptions = list(pattern.get("exceptions", []))
                    exceptions.append(self._fragment(episode))
                    exceptions.sort(
                        key=lambda row: (
                            -float(row.get("prediction_error") or 0.0),
                            -int(row.get("tick", 0)),
                        )
                    )
                    pattern["exceptions"] = exceptions[: self.config.exception_capacity]
                    memory["exception_index"][key] = pattern["exceptions"]
                self._refresh_pattern_size(memory, key)
            else:
                candidate = memory["candidates"].setdefault(
                    key,
                    {"count": 0.0, "expected_outcomes": {}, "m2": {}, "first_seen": tick},
                )
                _update_aggregate(candidate, outcome, observed_percept_features)
                candidate["last_updated"] = tick
                if candidate["count"] >= self.config.min_pattern_observations:
                    pattern_id = "PAT-" + sha256(key.encode("utf-8")).hexdigest()[:12].upper()
                    memory["patterns"][key] = {
                        **candidate,
                        "pattern_id": pattern_id,
                        "context_signature": pending["context_signature"],
                        "action_signature": pending["action_signature"],
                        "surprise_streak": 0,
                        "representatives": [],
                        "exceptions": [],
                    }
                    memory["pattern_index"][key] = [key]
                    self._refresh_pattern_size(memory, key)
                    del memory["candidates"][key]
                    memory["total_compressions"] = int(memory["total_compressions"]) + int(candidate["count"])
                    events.append({"type": "pattern_created", "pattern_id": pattern_id, "tick": tick, "observation_count": candidate["count"]})
                self._bound_candidates(memory, tick, events)

        memory["last_retention"] = {
            "tick": tick,
            "episode_id": episode_id,
            "decision": (
                "COMPRESSED"
                if episode_id not in memory["episode_lookup"]
                else "RETAINED"
            ),
            "reason": retention_reason,
            "prediction_error": error,
            "protect_until": episode["protect_until"],
        }
        self._evict(memory, tick, events)

    def _bound_candidates(
        self,
        memory: dict[str, Any],
        tick: int,
        events: list[dict[str, Any]],
    ) -> None:
        while len(memory["candidates"]) > self.config.candidate_capacity:
            key, removed = min(
                memory["candidates"].items(),
                key=lambda item: (
                    float(item[1].get("count", 0.0)),
                    int(item[1].get("last_updated", 0)),
                    str(item[0]),
                ),
            )
            del memory["candidates"][key]
            events.append(
                {
                    "type": "candidate_evicted",
                    "tick": tick,
                    "candidate_key": key,
                    "observation_count": removed.get("count", 0),
                }
            )

    @staticmethod
    def _fragment(episode: dict[str, Any]) -> dict[str, Any]:
        return {
            key: deepcopy(episode.get(key))
            for key in (
                "episode_id",
                "tick",
                "context_signature",
                "action_signature",
                "predicted_outcome",
                "outcome",
                "prediction_error",
                "perceived_identifiers",
            )
        }

    @staticmethod
    def _remove_episode(memory: dict[str, Any], episode: dict[str, Any]) -> None:
        episode_id = episode.get("episode_id")
        memory["episodes"] = [
            row for row in memory["episodes"] if row.get("episode_id") != episode_id
        ]
        memory["episode_lookup"].pop(episode_id, None)
        memory.get("novel_fragment_ids", {}).pop(episode_id, None)
        removed_size = int(memory.get("episode_sizes", {}).pop(episode_id, 0))
        memory["approx_episode_bytes"] = max(
            2, int(memory.get("approx_episode_bytes", 2)) - removed_size
        )
        key = f"{episode.get('context_signature')}\u241f{episode.get('action_signature')}"
        bucket = memory["episode_index"].get(key, [])
        memory["episode_index"][key] = [item for item in bucket if item != episode_id]

    @staticmethod
    def _refresh_pattern_size(memory: dict[str, Any], key: str) -> None:
        old_size = int(memory.get("pattern_sizes", {}).get(key, 0))
        new_size = len(canonical_json(memory["patterns"][key]))
        memory.setdefault("pattern_sizes", {})[key] = new_size
        memory["approx_pattern_bytes"] = max(
            2,
            int(memory.get("approx_pattern_bytes", 2)) - old_size + new_size,
        )

    def _evict(self, memory: dict[str, Any], tick: int, events: list[dict[str, Any]]) -> None:
        capacity = self.config.active_episode_capacity
        while len(memory["episodes"]) > capacity:
            eligible = [
                (index, row)
                for index, row in enumerate(memory["episodes"])
                if int(row.get("protect_until", 0)) <= tick
            ]
            candidates = eligible or list(enumerate(memory["episodes"]))
            if self.config.mode is MemoryMode.COMPRESSED:
                index = min(
                    candidates,
                    key=lambda item: (
                        float(item[1].get("prediction_error") or 0.0),
                        float(item[1].get("novelty") or 0.0),
                        int(item[1].get("tick", 0)),
                        str(item[1].get("episode_id", "")),
                    ),
                )[0]
            else:
                # RAW and FORGETFUL controls retain their original FIFO
                # semantics; only COMPRESSED receives information-sensitive
                # retention, keeping the manipulation scientifically isolated.
                index = candidates[0][0]
            removed = memory["episodes"].pop(index)
            self._remove_episode(memory, removed)
            memory["total_evictions"] = int(memory["total_evictions"]) + 1
            events.append({"type": "memory_evicted", "tick": tick, "episode_tick": removed["tick"], "prediction_error": removed.get("prediction_error")})
        while len(memory["patterns"]) > self.config.pattern_capacity:
            key, row = min(
                memory["patterns"].items(),
                key=lambda item: (_confidence(item[1], self.config.confidence_scale), item[1].get("last_updated", 0), item[0]),
            )
            del memory["patterns"][key]
            memory["pattern_index"].pop(key, None)
            memory["exception_index"].pop(key, None)
            removed_size = int(memory.get("pattern_sizes", {}).pop(key, 0))
            memory["approx_pattern_bytes"] = max(
                2,
                int(memory.get("approx_pattern_bytes", 2)) - removed_size,
            )
            events.append({"type": "pattern_evicted", "tick": tick, "pattern_id": row["pattern_id"]})

    def _lazy_decay(self, pattern: dict[str, Any], tick: int) -> None:
        last = int(pattern.get("last_decay_tick", pattern.get("last_updated", tick)))
        elapsed = max(0, tick - last)
        if elapsed:
            factor = self.config.pattern_decay ** elapsed
            pattern["count"] = max(1.0, float(pattern.get("count", 1.0)) * factor)
            pattern["m2"] = {
                key: value * factor
                for key, value in _numeric(pattern.get("m2")).items()
            }
            pattern["last_decay_tick"] = tick

    @staticmethod
    def _evidence_prediction(
        rows: list[dict[str, Any]],
        *,
        source: str,
        confidence_scale: float,
    ) -> dict[str, Any]:
        if not rows:
            return {
                "expected": {},
                "samples": 0,
                "source": "UNKNOWN",
                "confidence": 0.0,
                "evidence_status": "INSUFFICIENT_EVIDENCE",
            }
        keys = set().union(*(_numeric(row.get("outcome")).keys() for row in rows))
        expected = {
            key: sum(_numeric(row.get("outcome")).get(key, 0.0) for row in rows)
            / len(rows)
            for key in keys
        }
        confidence = len(rows) / (len(rows) + confidence_scale)
        percept_counts = Counter(
            tuple(row.get("observed_percept_features", ()))
            for row in rows if row.get("observed_percept_features")
        )
        return {
            "expected": expected,
            "samples": len(rows),
            "source": source,
            "confidence": confidence,
            "evidence_status": "LOW_CONFIDENCE",
            "expected_percept_features": list(percept_counts.most_common(1)[0][0]) if percept_counts else [],
        }

    def _update_developmental_gate(self, memory: dict[str, Any], tick: int) -> None:
        raw = self.config.developmental
        if not raw:
            memory.pop("developmental_gate", None)
            memory.pop("developmental", None)
            self._active_developmental_gate = None
            return
        from mechanistic_mind.psyche.developmental import (
            DevelopmentalCondition,
            DevelopmentalConfig,
            compute_developmental_gate,
            measure_experience_structure,
        )

        config = DevelopmentalConfig.from_dict(raw if isinstance(raw, dict) else {})
        if config.condition is DevelopmentalCondition.DISABLED:
            memory.pop("developmental_gate", None)
            memory["developmental"] = {
                "condition": "DISABLED",
                "gate_factor": 1.0,
                "matured": True,
            }
            self._active_developmental_gate = None
            return
        metrics = measure_experience_structure(
            episodes=list(memory.get("episodes") or []),
            action_models={
                str(key): {"count": float((value or {}).get("count", 0.0))}
                for key, value in (memory.get("patterns") or {}).items()
                if isinstance(value, dict)
            },
        )
        # Pattern diversity as transition proxy for compression memory.
        metrics["transition_diversity"] = max(
            int(metrics.get("transition_diversity", 0)),
            len(memory.get("patterns") or {}),
        )
        metrics["fragment_count"] = max(
            int(metrics.get("fragment_count", 0)),
            int(memory.get("total_experiences", 0)),
            len(memory.get("episodes") or {}),
        )
        gate = compute_developmental_gate(tick=int(tick), config=config, metrics=metrics)
        memory["developmental"] = gate
        memory["developmental_gate"] = {
            "gate_factor": gate["gate_factor"],
            "retrieval_recent_limit": gate["retrieval_recent_limit"],
            "max_learned_proposals_cap": gate["max_learned_proposals_cap"],
            "developmental_stage": gate["developmental_stage"],
            "developmental_maturity": gate["developmental_maturity"],
            "matured": gate["matured"],
            "condition": gate["condition"],
        }
        self._active_developmental_gate = memory["developmental_gate"]

    def _retrieve_bounded(
        self,
        memory: dict[str, Any],
        context: str,
        actions: dict[str, str],
        tick: int,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        budget = self.config.cognitive_budget
        gate = memory.get("developmental_gate") if isinstance(memory.get("developmental_gate"), dict) else None
        if gate is not None:
            factor = max(0.0, min(1.0, float(gate.get("gate_factor", 1.0))))
            # Shrink retrieval scope early; never expand beyond configured budget.
            budget = CognitiveBudget(
                max_pattern_candidates=max(1, int(round(budget.max_pattern_candidates * max(factor, 0.15)))),
                max_exception_candidates=max(0, int(round(budget.max_exception_candidates * factor))),
                max_episode_candidates=max(1, int(round(budget.max_episode_candidates * max(factor, 0.2)))),
                max_total_memory_candidates=max(1, int(round(budget.max_total_memory_candidates * max(factor, 0.25)))),
            )
        accounting = RetrievalAccounting(budget)
        predictions = {
            action: self._evidence_prediction(
                [], source="UNKNOWN", confidence_scale=self.config.confidence_scale
            )
            for action in actions
        }
        keys = {action: f"{context}\u241f{signature}" for action, signature in actions.items()}

        # Global stage 1: every permitted pattern probe precedes any fallback.
        pattern_started = perf_counter_ns()
        for action in actions:
            accounting.index_probes += 1
            for pattern_key in memory["pattern_index"].get(keys[action], [])[
                : accounting.remaining("PATTERN")
            ]:
                if not accounting.inspect("PATTERN"):
                    break
                pattern = memory["patterns"].get(pattern_key)
                if not isinstance(pattern, dict):
                    continue
                self._lazy_decay(pattern, tick)
                confidence = _confidence(pattern, self.config.confidence_scale)
                sufficient = (
                    confidence >= self.config.pattern_min_confidence
                    and float(pattern.get("count", 0.0)) >= self.config.pattern_min_samples
                )
                predictions[action] = {
                    "expected": _numeric(pattern.get("expected_outcomes")),
                    "samples": float(pattern.get("count", 0.0)),
                    "source": "PATTERN" if sufficient else "PATTERN_LOW_CONFIDENCE",
                    "pattern_id": pattern.get("pattern_id"),
                    "confidence": confidence,
                    "match_score": 1.0,
                    "evidence_status": "SUFFICIENT" if sufficient else "LOW_CONFIDENCE",
                    "expected_percept_features": list(pattern.get("expected_percept_features", ())),
                    "_pattern_key": pattern_key,
                }
        pattern_lookup_time_ns = perf_counter_ns() - pattern_started

        # Global stage 2: linked exceptions/representatives only for misses.
        exception_started = perf_counter_ns()
        fallback_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for action in actions:
            if predictions[action]["evidence_status"] == "SUFFICIENT":
                continue
            accounting.index_probes += 1
            pattern_key = predictions[action].get("_pattern_key")
            rows = list(memory["exception_index"].get(keys[action], []))
            pattern = memory["patterns"].get(pattern_key) if pattern_key else None
            if isinstance(pattern, dict):
                rows.extend(pattern.get("representatives", []))
            for row in rows[: accounting.remaining("EXCEPTION")]:
                if not accounting.inspect("EXCEPTION"):
                    break
                if isinstance(row, dict):
                    fallback_rows[action].append(row)
            if fallback_rows[action]:
                predictions[action] = self._evidence_prediction(
                    fallback_rows[action],
                    source="EXCEPTION_FALLBACK",
                    confidence_scale=self.config.confidence_scale,
                )
        exception_fallback_time_ns = perf_counter_ns() - exception_started

        # Global stage 3: bounded indexed episodes, never the biography list.
        episode_started = perf_counter_ns()
        for action in actions:
            if predictions[action]["evidence_status"] == "SUFFICIENT":
                continue
            accounting.index_probes += 1
            ids = list(memory["episode_index"].get(keys[action], []))
            rows = list(fallback_rows[action])
            for episode_id in reversed(ids):
                if not accounting.inspect("EPISODE"):
                    break
                row = memory["episode_lookup"].get(episode_id)
                if isinstance(row, dict):
                    rows.append(row)
            if rows:
                predictions[action] = self._evidence_prediction(
                    rows,
                    source="EPISODE_FALLBACK",
                    confidence_scale=self.config.confidence_scale,
                )
        episode_fallback_time_ns = perf_counter_ns() - episode_started

        for prediction in predictions.values():
            prediction.pop("_pattern_key", None)
        stages = accounting.stage_trace
        terminal = (
            "EPISODE_FALLBACK"
            if "EPISODE" in stages
            else "EXCEPTION_FALLBACK"
            if "EXCEPTION" in stages
            else "PATTERN"
            if "PATTERN" in stages
            else "UNKNOWN"
        )
        result = accounting.to_dict()
        result.update(
            {
                "retrieval_mode": self.config.retrieval_mode.value,
                "terminal_stage": terminal,
                "fallback_reason": (
                    "PATTERN_SUFFICIENT"
                    if terminal == "PATTERN"
                    and any(row["evidence_status"] == "SUFFICIENT" for row in predictions.values())
                    else "INSUFFICIENT_PATTERN_EVIDENCE"
                ),
                "cue_schema_version": self.config.cue_schema_version,
                "cue_dimensions": [
                    "context",
                    "body_bands",
                    "visual_fragments",
                    "recent_action",
                    "response_fragment",
                ],
                "pattern_lookup_time_ns": pattern_lookup_time_ns,
                "exception_fallback_time_ns": exception_fallback_time_ns,
                "episode_fallback_time_ns": episode_fallback_time_ns,
            }
        )
        return predictions, result

    def _retrieve_legacy(
        self,
        memory: dict[str, Any],
        context: str,
        actions: dict[str, str],
        tick: int,
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        predictions: dict[str, dict[str, Any]] = {}
        inspected = 0
        scan_started = perf_counter_ns()
        for action, signature in actions.items():
            key = f"{context}\u241f{signature}"
            pattern = memory["patterns"].get(key)
            if isinstance(pattern, dict):
                self._lazy_decay(pattern, tick)
                predictions[action] = {
                    "expected": _numeric(pattern.get("expected_outcomes")),
                    "samples": float(pattern.get("count", 0.0)),
                    "source": "PATTERN",
                    "pattern_id": pattern.get("pattern_id"),
                    "confidence": _confidence(pattern, self.config.confidence_scale),
                    "evidence_status": "SUFFICIENT",
                }
                inspected += 1
                continue
            rows = []
            for row in memory["episodes"]:
                inspected += 1
                if row.get("context_signature") == context and row.get("action_signature") == signature:
                    rows.append(row)
            predictions[action] = self._evidence_prediction(
                rows,
                source="LEGACY_EPISODE_SCAN",
                confidence_scale=self.config.confidence_scale,
            )
        episode_fallback_time_ns = perf_counter_ns() - scan_started
        return predictions, {
            "retrieval_mode": self.config.retrieval_mode.value,
            "pattern_candidates_inspected": 0,
            "exception_candidates_inspected": 0,
            "episode_candidates_inspected": inspected,
            "total_candidates_inspected": inspected,
            "index_probes": 0,
            "stage_trace": ["LEGACY_UNBOUNDED"],
            "terminal_stage": "LEGACY_UNBOUNDED",
            "fallback_reason": "ABLATION_FULL_SCAN",
            "cue_schema_version": self.config.cue_schema_version,
            "cue_dimensions": list(build_retrieval_cue({}).keys()),
            "pattern_lookup_time_ns": 0,
            "exception_fallback_time_ns": 0,
            "episode_fallback_time_ns": episode_fallback_time_ns,
        }

    def _select(self, actions: tuple[str, ...], predictions: dict[str, dict[str, Any]], random_value: float) -> str:
        scored = []
        # Developmental gating may shrink exploration_gain so sparse early
        # samples do not dominate selection; DISABLED leaves prior gain.
        gain = float(self.config.exploration_gain)
        gate = getattr(self, "_active_developmental_gate", None)
        if isinstance(gate, dict):
            gain = gain * float(gate.get("gate_factor", 1.0))
        for action in actions:
            prediction = predictions[action]
            expected = _numeric(prediction.get("expected"))
            outcome_value = self._outcome_value(expected)
            uncertainty = 1.0 / sqrt(float(prediction.get("samples", 0.0)) + 1.0)
            scored.append((outcome_value + gain * uncertainty, action))
        best = max(score for score, _action in scored)
        tied = sorted(action for score, action in scored if abs(score - best) <= 1e-12)
        return tied[min(len(tied) - 1, int(random_value * len(tied)))]

    def _outcome_value(self, expected: dict[str, float]) -> float:
        if "scalar" in expected:
            return float(expected["scalar"])
        directions = dict(self.config.outcome_directions)
        return sum(
            value * float(directions.get(key, 1.0))
            for key, value in expected.items()
        )


@dataclass(slots=True)
class CompactEvidenceObserver:
    """Event + telemetry + checkpoint observer; never participates in decisions."""

    checkpoint_interval: int = 250
    jsonl_path: Path | None = None
    retain_records: bool = True
    retain_runtime_timings: bool = False
    measure_legacy_full: bool = False
    forced_checkpoint_events: tuple[str, ...] = ("pattern_created", "pattern_invalidated", "perturbation")
    run_id: str | None = None
    _started: bool = False
    _ticks_recorded: int = 0
    continuous: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    byte_counts: Counter = field(default_factory=Counter)
    _last_action: dict[str, str] = field(default_factory=dict)
    _seen_positions: set[tuple[int, int]] = field(default_factory=set)
    _seen_objects: set[str] = field(default_factory=set)
    _retrieval_stats: dict[str, dict[str, Any]] = field(default_factory=dict)
    runtime_retrieval_timings: list[dict[str, int]] = field(default_factory=list)

    def start_run(self, *, engine_version: str, seed: int, mechanisms: Any, world_type: str, agent_ids: Iterable[str], config: dict[str, Any] | None = None, run_id: str | None = None) -> RunMetadata:
        if self.checkpoint_interval < 1:
            raise ValueError("checkpoint_interval must be positive")
        provenance_fingerprint = sha256(
            canonical_json(
                {
                    "seed": seed,
                    "world_type": world_type,
                    "mechanisms": [
                        (item.mechanism_id, item.version)
                        for item in mechanisms.ordered()
                    ],
                    "config": config or {},
                }
            ).encode("utf-8")
        ).hexdigest()[:12].upper()
        self.run_id = run_id or f"MM-EC-{provenance_fingerprint}"
        self._started = True
        if self.jsonl_path is not None:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            self.jsonl_path.write_text("", encoding="utf-8")
        metadata = RunMetadata(self.run_id, engine_version, seed, {item.mechanism_id: item.version for item in mechanisms.ordered()}, world_type, tuple(sorted(agent_ids)), deepcopy(config or {}))
        self._write("run_metadata", to_plain(metadata))
        return metadata

    def record_step(self, result: Any) -> dict[str, Any]:
        if not self._started or self.run_id is None:
            raise RuntimeError("Observer run has not been started")
        tick = int(result.state_after.tick)
        world_after = result.state_after.world.variables
        objective_scalars = {
            str(key): value
            for key, value in world_after.items()
            if isinstance(value, (str, int, float, bool)) or value is None
        }
        history = world_after.get("developmental_history", [])
        latest_history = history[-1] if isinstance(history, list) and history else {}
        memory_events: list[dict[str, Any]] = []
        summaries: dict[str, Any] = {}
        agents: dict[str, Any] = {}
        for agent_id, observation in result.observations.items():
            data = observation.data
            action = result.actions[agent_id].kind
            position = _position(data.get("position"))
            visible_ids = sorted(str(row.get("id")) for row in data.get("visible_objects", []) if isinstance(row, dict) and row.get("id") is not None)
            outputs = result.mechanism_outputs.get(agent_id, {})
            retrieval_record: dict[str, Any] = {}
            retention_record: dict[str, Any] = {}
            for output in outputs.values():
                candidate = output.signals.get("memory_summary")
                if isinstance(candidate, dict):
                    summaries[agent_id] = deepcopy(candidate)
                for event in output.signals.get("memory_events", []):
                    if isinstance(event, dict):
                        memory_events.append({"agent_id": agent_id, **deepcopy(event)})
                retrieval = output.signals.get("retrieval")
                if isinstance(retrieval, dict):
                    # Wall-clock timing is useful for a performance experiment but
                    # is not deterministic scientific evidence. Keep it out of the
                    # replayable telemetry and expose it through an explicit,
                    # opt-in runtime-only channel instead.
                    retrieval_record = {
                        str(key): deepcopy(value)
                        for key, value in retrieval.items()
                        if not str(key).endswith("_time_ns")
                    }
                    if self.retain_runtime_timings:
                        timing_row = {
                            str(key): int(value)
                            for key, value in retrieval.items()
                            if str(key).endswith("_time_ns")
                            and isinstance(value, int)
                        }
                        if timing_row:
                            self.runtime_retrieval_timings.append(
                                {"tick": tick, **timing_row}
                            )
                    for key in (
                        "pattern_candidates_inspected",
                        "exception_candidates_inspected",
                        "episode_candidates_inspected",
                        "total_candidates_inspected",
                        "index_probes",
                        "pattern_lookup_time_ns",
                        "exception_fallback_time_ns",
                        "episode_fallback_time_ns",
                        "retrieval_time_ns",
                        "decision_time_ns",
                    ):
                        value = retrieval.get(key)
                        if isinstance(value, (int, float)):
                            self._sample_retrieval_metric(key, float(value), tick)
                retention = output.signals.get("retention")
                if isinstance(retention, dict):
                    retention_record = deepcopy(retention)
            agents[agent_id] = {
                "position": list(position) if position is not None else None,
                "action": action,
                "context_signature": context_signature(data),
                "body_state": _numeric(data.get("interoception")),
                "perceived_ids": visible_ids,
                "visual_fragments": deepcopy(data.get("visual_fragments", [])),
                "memory": summaries.get(agent_id, {}),
                "retrieval": retrieval_record,
                "retention": retention_record,
                "agent_accessible_previous_outcome": observed_outcome(data),
                "objective_outcome_after_action": (
                    deepcopy(latest_history.get("experienced_effects"))
                    if isinstance(latest_history, dict)
                    and isinstance(latest_history.get("experienced_effects"), dict)
                    else world_after.get("last_outcome")
                ),
            }
            if self._last_action.get(agent_id) != action:
                self._event({"type": "action_changed", "tick": tick, "agent_id": agent_id, "from": self._last_action.get(agent_id), "to": action})
            self._last_action[agent_id] = action
            if position is not None and position not in self._seen_positions:
                self._seen_positions.add(position)
                self._event({"type": "novel_position", "tick": tick, "agent_id": agent_id, "position": list(position)})
            for object_id in visible_ids:
                if object_id not in self._seen_objects:
                    self._seen_objects.add(object_id)
                    self._event({"type": "object_encountered", "tick": tick, "agent_id": agent_id, "object_id": object_id})
            if action.startswith(("USE:", "TAKE:", "RELEASE:", "PUSH:")):
                self._event({"type": "object_interaction", "tick": tick, "agent_id": agent_id, "action": action})
        before_phase = result.state_before.world.variables.get("phase")
        after_phase = result.state_after.world.variables.get("phase")
        perturbation = before_phase != after_phase and before_phase is not None
        if perturbation:
            self._event({"type": "perturbation", "tick": tick, "before": before_phase, "after": after_phase})
        for event in memory_events:
            self._event(event)
        compact = {
            "run_id": self.run_id,
            "tick": tick,
            "agents": agents,
            "objective_world_scalars": objective_scalars,
            "world_digest": sha256(
                canonical_json(result.state_after.world).encode()
            ).hexdigest(),
        }
        self._write("telemetry", compact)
        if self.retain_records:
            self.continuous.append(compact)
        force = perturbation or any(event.get("type") in self.forced_checkpoint_events for event in memory_events)
        if tick == 1 or tick % self.checkpoint_interval == 0 or force:
            checkpoint = {"run_id": self.run_id, "tick": tick, "state": to_plain(result.state_after), "reason": "EVENT" if force else "INTERVAL"}
            self._write("checkpoint", checkpoint)
            if self.retain_records:
                self.checkpoints.append(checkpoint)
        if self.measure_legacy_full:
            legacy = {
                "tick": result.state_before.tick,
                "state_before": to_plain(result.state_before),
                "observations": to_plain(result.observations),
                "mechanism_outputs": to_plain(result.mechanism_outputs),
                "signals": to_plain(result.signals),
                "actions": to_plain(result.actions),
                "action_sources": to_plain(result.action_sources),
                "action_decisions": to_plain(result.action_decisions),
                "applied_state_updates": to_plain(result.applied_state_updates),
                "state_after": to_plain(result.state_after),
            }
            self.byte_counts["legacy_full"] += len(canonical_json(legacy)) + 1
        self._ticks_recorded += 1
        return compact

    def _sample_retrieval_metric(self, key: str, value: float, tick: int) -> None:
        record = self._retrieval_stats.setdefault(
            key, {"count": 0, "sum": 0.0, "max": 0.0, "samples": []}
        )
        record["count"] += 1
        record["sum"] += value
        record["max"] = max(float(record["max"]), value)
        samples = record["samples"]
        if len(samples) < 256:
            samples.append(value)
        else:
            samples[tick % 256] = value

    def _retrieval_metric_summary(self) -> dict[str, Any]:
        result = {}
        for key, record in self._retrieval_stats.items():
            samples = sorted(float(value) for value in record["samples"])
            def percentile(fraction: float) -> float:
                if not samples:
                    return 0.0
                return samples[min(len(samples) - 1, int((len(samples) - 1) * fraction))]
            result[key] = {
                "mean": record["sum"] / max(1, record["count"]),
                "max": record["max"],
                "approx_p50": percentile(0.50),
                "approx_p95": percentile(0.95),
                "sample_reservoir_size": len(samples),
            }
        return result

    def _event(self, event: dict[str, Any]) -> None:
        self._write("event", event)
        if self.retain_records:
            self.events.append(event)

    def _write(self, record_type: str, payload: Any) -> None:
        line = canonical_json({"record_type": record_type, "payload": payload}) + "\n"
        self.byte_counts[record_type] += len(line.encode("utf-8"))
        if self.jsonl_path is not None:
            self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
            with self.jsonl_path.open("a", encoding="utf-8") as handle:
                handle.write(line)

    def end_run(self, *, final_tick: int) -> RunSummary:
        summary = RunSummary(self.run_id or "UNKNOWN", self._ticks_recorded, final_tick, True)
        self._write("run_summary", to_plain(summary))
        self._started = False
        return summary

    @property
    def storage_metrics(self) -> dict[str, Any]:
        compact = sum(value for key, value in self.byte_counts.items() if key != "legacy_full")
        return {
            "ticks": self._ticks_recorded,
            "observer_history_bytes": compact,
            "bytes_per_tick": compact / max(1, self._ticks_recorded),
            "checkpoint_storage_bytes": self.byte_counts["checkpoint"],
            "event_storage_bytes": self.byte_counts["event"],
            "telemetry_storage_bytes": self.byte_counts["telemetry"],
            "legacy_full_history_bytes": self.byte_counts["legacy_full"],
            "reduction_ratio": (
                self.byte_counts["legacy_full"] / max(1, compact)
                if self.byte_counts["legacy_full"]
                else None
            ),
            "ram_peak_bytes": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024,
            "total_output_bytes": self.jsonl_path.stat().st_size if self.jsonl_path and self.jsonl_path.exists() else compact,
            "event_count": sum(1 for _event in self.events),
            "checkpoint_count": sum(1 for _checkpoint in self.checkpoints),
            "retrieval_metrics": self._retrieval_metric_summary(),
        }


def entropy(values: Iterable[str]) -> float:
    rows = list(values)
    if not rows:
        return 0.0
    counts = Counter(rows)
    return -sum((count / len(rows)) * log2(count / len(rows)) for count in counts.values())


def behavioral_metrics(records: list[dict[str, Any]], agent_id: str = "A001") -> dict[str, Any]:
    rows = [record["agents"][agent_id] for record in records if agent_id in record.get("agents", {})]
    actions = [str(row.get("action")) for row in rows]
    positions = [tuple(row["position"]) for row in rows if isinstance(row.get("position"), list)]
    transitions = [f"{a}->{b}" for a, b in zip(positions, positions[1:])]
    routes = ["|".join(map(str, positions[index:index + 4])) for index in range(max(0, len(positions) - 3))]
    route_counts = Counter(routes)
    contexts: dict[str, Counter] = defaultdict(Counter)
    object_uses: Counter = Counter()
    encountered: set[str] = set()
    for _record, row in zip(records, rows):
        context = str(row.get("context_signature", "GENERIC"))
        contexts[context][str(row.get("action"))] += 1
        encountered.update(str(item) for item in row.get("perceived_ids", []))
        if str(row.get("action")).startswith("USE:"):
            object_uses[str(row["action"]).split(":", 1)[1]] += 1
    consistency = sum(max(counts.values()) for counts in contexts.values() if counts) / max(1, len(actions))
    same = sum(a == b for a, b in zip(actions, actions[1:]))
    unique_positions = len(set(positions))
    return {
        "action_entropy": entropy(actions),
        "route_path_entropy": entropy(transitions),
        "repeated_route_frequency": max(route_counts.values(), default=0) / max(1, len(routes)),
        "object_preference": dict(sorted(object_uses.items())),
        "object_avoidance": sorted(encountered - set(object_uses)),
        "context_action_consistency": consistency,
        "behavioral_persistence": same / max(1, len(actions) - 1),
        "exploration_rate": unique_positions / max(1, len(positions)),
        "revisit_rate": 1.0 - unique_positions / max(1, len(positions)),
        "behavioral_diversity": len(set(actions)) / max(1, len(actions)),
    }


def memory_metrics(memory: dict[str, Any]) -> dict[str, Any]:
    episodes = memory.get("episodes", [])
    patterns = memory.get("patterns", {})
    confidences = [_confidence(row, 4.0) for row in patterns.values() if isinstance(row, dict)]
    episode_bytes = len(canonical_json(episodes))
    pattern_bytes = len(canonical_json(patterns))
    return {
        "pattern_count": len(patterns),
        "episodic_memory_size": len(episodes),
        "novel_fragment_count": len(memory.get("novel_fragment_ids", {})),
        "compressed_memory_size": pattern_bytes,
        "agent_memory_bytes": episode_bytes + pattern_bytes,
        "bytes_per_episode": episode_bytes / max(1, len(episodes)),
        "bytes_per_pattern": pattern_bytes / max(1, len(patterns)),
        "compression_ratio": int(memory.get("total_experiences", 0)) / max(1, len(episodes) + len(patterns)),
        "prediction_error": memory.get("last_prediction_error"),
        "pattern_confidence_distribution": confidences,
        "decision_source": memory.get("last_decision_source"),
        "total_evictions": int(memory.get("total_evictions", 0)),
        "total_compressions": int(memory.get("total_compressions", 0)),
    }


def structural_retrieval_probe(
    stored_representations: int,
    *,
    budget: CognitiveBudget | None = None,
) -> dict[str, Any]:
    """Populate a synthetic indexed store and issue one matched bounded query."""
    config = CompressionConfig(
        mode=MemoryMode.COMPRESSED,
        cognitive_budget=budget or CognitiveBudget(),
        pattern_capacity=max(1, stored_representations + 1),
    )
    mechanism = ExperienceCompressionMechanism(config)
    memory = mechanism._initial_memory()
    for index in range(max(0, int(stored_representations))):
        context = f"SYNTHETIC-{index:08d}"
        key = f"{context}\u241fACT"
        pattern = {
            "pattern_id": f"PAT-{index:08d}",
            "context_signature": context,
            "action_signature": "ACT",
            "count": 10.0,
            "expected_outcomes": {"scalar": 1.0},
            "m2": {"scalar": 0.0},
            "last_updated": 0,
            "last_decay_tick": 0,
            "representatives": [],
            "exceptions": [],
        }
        memory["patterns"][key] = pattern
        memory["pattern_index"][key] = [key]
    query_context = f"SYNTHETIC-{max(0, stored_representations - 1):08d}"
    started = perf_counter_ns()
    predictions, retrieval = mechanism._retrieve_bounded(
        memory,
        query_context,
        {"ACT": "ACT"},
        1,
    )
    elapsed = perf_counter_ns() - started
    return {
        "stored_representations": stored_representations,
        "retrieval": retrieval,
        "prediction": predictions["ACT"],
        "retrieval_time_ns": elapsed,
        "full_store_iterations": 0,
        "index_bucket_size": len(
            memory["pattern_index"].get(f"{query_context}\u241fACT", [])
        ),
    }
