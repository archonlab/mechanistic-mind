"""Experience-gated cognitive depth — bounded use of history.

Update 1: global developmental gating for early life.
Update 2: local experience maturity + cognitive depth for the current context.

One continuous psyche. Development changes how much inference available
evidence can support. Does not prescribe actions or add curiosity rewards.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import Enum
from math import log1p, sqrt
from typing import Any


class DevelopmentalCondition(str, Enum):
    DISABLED = "DISABLED"
    DEVELOPMENTAL = "DEVELOPMENTAL"
    EXPERIENCE_GATED = "EXPERIENCE_GATED"
    ADULT_FROM_TICK_0 = "ADULT_FROM_TICK_0"


class DevelopmentalStage(str, Enum):
    SENSORIMOTOR_ACQUISITION = "SENSORIMOTOR_ACQUISITION"
    LOCAL_PREDICTIVE_INTEGRATION = "LOCAL_PREDICTIVE_INTEGRATION"
    EXPERIENCE_INTEGRATION = "EXPERIENCE_INTEGRATION"
    MATURE_COGNITION = "MATURE_COGNITION"


# Conceptual depth labels (continuous depth is primary).
DEPTH_IMMEDIATE = 0.0
DEPTH_LOCAL_ASSOCIATIVE = 1.0
DEPTH_PREDICTIVE = 2.0
DEPTH_COMPOSITIONAL = 3.0


@dataclass(frozen=True, slots=True)
class DevelopmentalConfig:
    """Configurable developmental / experience-gating bounds."""

    condition: DevelopmentalCondition = DevelopmentalCondition.DISABLED
    min_ticks: int = 3000
    target_ticks: int = 5000
    max_ticks: int = 10000
    # Global structural maturity targets (observation + early ceiling).
    target_fragments: int = 120
    target_transition_diversity: int = 40
    target_interaction_diversity: int = 12
    target_repeated_consequences: int = 30
    target_predictive_evidence: int = 20
    # Local maturity targets (current-context evidence structure).
    local_target_fragments: int = 8
    local_target_diversity: int = 4
    local_target_repeats: int = 4
    local_target_predictive: int = 3
    local_related_weight: float = 0.35
    # Early retrieval caps while depth is low.
    early_recent_fragment_limit: int = 8
    early_max_learned_proposals: int = 1
    maturity_weight_time: float = 0.35
    maturity_weight_structure: float = 0.65
    # Mix of local vs global ceiling under experience gating.
    # Effective gate uses min(global_ceiling, local) with optional soft blend.
    local_gate_weight: float = 1.0

    def __post_init__(self) -> None:
        if self.min_ticks < 1 or self.target_ticks < 1 or self.max_ticks < 1:
            raise ValueError("developmental tick bounds must be positive")
        if not (self.min_ticks <= self.target_ticks <= self.max_ticks):
            raise ValueError("require min_ticks <= target_ticks <= max_ticks")
        if self.early_recent_fragment_limit < 1:
            raise ValueError("early_recent_fragment_limit must be positive")
        if min(
            self.target_fragments,
            self.target_transition_diversity,
            self.target_interaction_diversity,
            self.target_repeated_consequences,
            self.target_predictive_evidence,
            self.local_target_fragments,
            self.local_target_diversity,
            self.local_target_repeats,
            self.local_target_predictive,
        ) < 1:
            raise ValueError("maturity targets must be positive")
        weight = self.maturity_weight_time + self.maturity_weight_structure
        if abs(weight - 1.0) > 1e-9:
            raise ValueError("maturity weights must sum to 1.0")
        if not 0.0 <= self.local_related_weight <= 1.0:
            raise ValueError("local_related_weight must be in [0, 1]")
        if not 0.0 <= self.local_gate_weight <= 1.0:
            raise ValueError("local_gate_weight must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["condition"] = self.condition.value
        return payload

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "DevelopmentalConfig":
        data = dict(raw or {})
        if "condition" in data:
            data["condition"] = DevelopmentalCondition(str(data["condition"]))
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def uses_experience_gating(self) -> bool:
        return self.condition in (
            DevelopmentalCondition.DEVELOPMENTAL,
            DevelopmentalCondition.EXPERIENCE_GATED,
        )


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _norm(count: float, target: float) -> float:
    return _clamp01(float(count) / max(1.0, float(target)))


def measure_experience_structure(
    *,
    sensorimotor: dict[str, Any] | None = None,
    episodes: list[Any] | None = None,
    action_models: dict[str, Any] | None = None,
    min_support: float = 3.0,
) -> dict[str, Any]:
    """Global structural metrics. No semantic success scoring."""
    sensorimotor = sensorimotor or {}
    contingencies = sensorimotor.get("contingencies", {})
    if not isinstance(contingencies, dict):
        contingencies = {}
    episodes = episodes if isinstance(episodes, list) else []
    action_models = action_models if isinstance(action_models, dict) else {}

    fragment_count = 0
    transition_keys: set[str] = set()
    interaction_keys: set[str] = set()
    repeated_consequences = 0
    predictive_evidence = 0

    for key, record in contingencies.items():
        if not isinstance(record, dict):
            continue
        fragment_count += 1
        action = str(record.get("action") or "")
        bucket = str(record.get("bucket") or key.split("||", 1)[0])
        transition_keys.add(f"{bucket}|{action}")
        if action.startswith(("USE:", "TAKE:", "RELEASE:", "PUSH:", "MOVE:")):
            interaction_keys.add(action.split(":", 1)[0])
        support = float(record.get("support", 0.0) or 0.0)
        if support > 1.0:
            repeated_consequences += 1
        if support >= min_support and float(record.get("confidence", 0.0) or 0.0) > 0.0:
            predictive_evidence += 1

    for row in episodes:
        if not isinstance(row, dict):
            continue
        fragment_count += 1
        action = str(row.get("action") or "")
        if action:
            transition_keys.add(f"episode|{action}")
            if action.startswith(("USE:", "TAKE:", "RELEASE:", "PUSH:", "MOVE:")):
                interaction_keys.add(action.split(":", 1)[0])

    for action, record in action_models.items():
        if not isinstance(record, dict):
            continue
        count = float(record.get("count", record.get("samples", 0.0)) or 0.0)
        if count <= 0:
            continue
        fragment_count += 1
        transition_keys.add(f"model|{action}")
        if str(action).startswith(("USE:", "TAKE:", "RELEASE:", "PUSH:", "MOVE:")):
            interaction_keys.add(str(action).split(":", 1)[0])
        if count > 1.0:
            repeated_consequences += 1
        if count >= min_support:
            predictive_evidence += 1

    return {
        "fragment_count": int(fragment_count),
        "transition_diversity": len(transition_keys),
        "interaction_diversity": len(interaction_keys),
        "repeated_consequences": int(repeated_consequences),
        "predictive_evidence": int(predictive_evidence),
    }


def structural_maturity(metrics: dict[str, Any], config: DevelopmentalConfig) -> float:
    parts = (
        _norm(metrics.get("fragment_count", 0), config.target_fragments),
        _norm(metrics.get("transition_diversity", 0), config.target_transition_diversity),
        _norm(metrics.get("interaction_diversity", 0), config.target_interaction_diversity),
        _norm(metrics.get("repeated_consequences", 0), config.target_repeated_consequences),
        _norm(metrics.get("predictive_evidence", 0), config.target_predictive_evidence),
    )
    return _clamp01(sum(parts) / len(parts))


def _visible_tokens_from_bucket(bucket: str) -> set[str]:
    """Best-effort parse of cue_bucket repr((visible, bands))."""
    try:
        parsed = eval(bucket, {"__builtins__": {}}, {})  # noqa: S307 — controlled store keys
    except Exception:
        return set()
    if not isinstance(parsed, tuple) or not parsed:
        return set()
    visible = parsed[0]
    if not isinstance(visible, tuple):
        return set()
    return {str(item) for item in visible if item}


def _consistency_from_records(records: list[dict[str, Any]]) -> float:
    """High when repeated outcomes agree; low when rates conflict."""
    if not records:
        return 0.0
    rates: list[float] = []
    weights: list[float] = []
    for record in records:
        support = float(record.get("support", 0.0) or 0.0)
        if support <= 0:
            continue
        rate = float(record.get("displace_rate", 0.0) or 0.0)
        mean = record.get("mean_transition")
        if isinstance(mean, dict) and "displace_rate" in mean:
            rate = float(mean.get("displace_rate", rate) or rate)
        rates.append(rate)
        weights.append(support)
    if len(rates) <= 1:
        # Single fragment: consistency from confidence/support only.
        conf = float(records[0].get("confidence", 0.0) or 0.0)
        return _clamp01(0.5 + 0.5 * conf)
    mean = sum(r * w for r, w in zip(rates, weights)) / max(1e-9, sum(weights))
    var = sum(w * (r - mean) ** 2 for r, w in zip(rates, weights)) / max(1e-9, sum(weights))
    # Map stdev in [0, 0.5+] to consistency in (0, 1].
    consistency = 1.0 / (1.0 + 4.0 * sqrt(max(0.0, var)))
    return _clamp01(consistency)


def measure_local_experience(
    *,
    sensorimotor: dict[str, Any] | None,
    current_bucket: str | None,
    min_support: float = 3.0,
    related_weight: float = 0.35,
    budget_total: int = 12,
) -> dict[str, Any]:
    """Bounded local evidence for the current cue. Not memory-size maturity."""
    sensorimotor = sensorimotor or {}
    contingencies = sensorimotor.get("contingencies", {})
    index = sensorimotor.get("index", {})
    if not isinstance(contingencies, dict):
        contingencies = {}
    if not isinstance(index, dict):
        index = {}

    if not current_bucket:
        return {
            "current_bucket": None,
            "relevant_fragments": 0,
            "relevant_diversity": 0,
            "repeated_consequences": 0,
            "predictive_evidence": 0,
            "related_fragments": 0,
            "evidence_consistency": 0.0,
            "effective_sample_size": 0.0,
            "inspected": 0,
            "records": [],
        }

    keys = list(index.get(current_bucket, ()))
    # Also allow direct contingency scan limited by budget (bounded).
    direct = [k for k, rec in contingencies.items() if isinstance(rec, dict) and rec.get("bucket") == current_bucket]
    for key in direct:
        if key not in keys:
            keys.append(key)
    keys = keys[: max(1, budget_total)]

    records: list[dict[str, Any]] = []
    inspected = 0
    for key in keys:
        record = contingencies.get(key)
        if not isinstance(record, dict):
            continue
        inspected += 1
        records.append(record)
        if inspected >= budget_total:
            break

    current_tokens = _visible_tokens_from_bucket(current_bucket)
    related_records: list[dict[str, Any]] = []
    related_inspected = 0
    if current_tokens and related_weight > 0:
        for key, record in contingencies.items():
            if related_inspected + inspected >= budget_total * 2:
                break
            if not isinstance(record, dict):
                continue
            bucket = str(record.get("bucket") or "")
            if bucket == current_bucket:
                continue
            tokens = _visible_tokens_from_bucket(bucket)
            if not tokens.intersection(current_tokens):
                continue
            related_inspected += 1
            related_records.append(record)

    def _stats(rows: list[dict[str, Any]], weight: float = 1.0) -> dict[str, float]:
        fragments = 0.0
        diversity: set[str] = set()
        repeats = 0.0
        predictive = 0.0
        sample = 0.0
        for record in rows:
            fragments += weight
            action = str(record.get("action") or "")
            diversity.add(action)
            support = float(record.get("support", 0.0) or 0.0)
            sample += weight * support
            if support > 1.0:
                repeats += weight
            if support >= min_support and float(record.get("confidence", 0.0) or 0.0) > 0.0:
                predictive += weight
        return {
            "fragments": fragments,
            "diversity": float(len(diversity)),
            "repeats": repeats,
            "predictive": predictive,
            "sample": sample,
        }

    primary = _stats(records, 1.0)
    related = _stats(related_records, related_weight)
    consistency = _consistency_from_records(records)
    # Contradictory related evidence should not inflate authority.
    related_consistency = _consistency_from_records(related_records) if related_records else 1.0

    return {
        "current_bucket": current_bucket,
        "relevant_fragments": int(round(primary["fragments"])),
        "relevant_diversity": int(primary["diversity"]),
        "repeated_consequences": int(round(primary["repeats"])),
        "predictive_evidence": int(round(primary["predictive"])),
        "related_fragments": int(round(related["fragments"] / max(related_weight, 1e-9))),
        "related_weighted_fragments": round(related["fragments"], 4),
        "evidence_consistency": round(consistency, 6),
        "related_consistency": round(related_consistency, 6),
        "effective_sample_size": round(primary["sample"] + related["sample"], 4),
        "inspected": inspected + related_inspected,
        "records": records,
    }


def local_experience_maturity(
    local: dict[str, Any],
    config: DevelopmentalConfig,
) -> float:
    """Confidence in local EXPERIENCE STRUCTURE, not success."""
    base = (
        _norm(local.get("relevant_fragments", 0), config.local_target_fragments)
        + _norm(local.get("relevant_diversity", 0), config.local_target_diversity)
        + _norm(local.get("repeated_consequences", 0), config.local_target_repeats)
        + _norm(local.get("predictive_evidence", 0), config.local_target_predictive)
        + _norm(local.get("effective_sample_size", 0), config.local_target_repeats * 3.0)
    ) / 5.0
    related_boost = _clamp01(
        float(local.get("related_weighted_fragments", 0.0))
        / max(1.0, float(config.local_target_fragments))
    ) * 0.15 * float(local.get("related_consistency", 1.0))
    consistency = float(local.get("evidence_consistency", 0.0) or 0.0)
    # Many inconsistent fragments must not yield high maturity.
    maturity = _clamp01(base + related_boost) * (0.35 + 0.65 * consistency)
    if int(local.get("relevant_fragments", 0)) == 0 and float(local.get("related_weighted_fragments", 0)) <= 0:
        maturity = 0.0
    return _clamp01(maturity)


def stage_for_gate(gate: float) -> DevelopmentalStage:
    if gate < 0.25:
        return DevelopmentalStage.SENSORIMOTOR_ACQUISITION
    if gate < 0.55:
        return DevelopmentalStage.LOCAL_PREDICTIVE_INTEGRATION
    if gate < 0.95:
        return DevelopmentalStage.EXPERIENCE_INTEGRATION
    return DevelopmentalStage.MATURE_COGNITION


def cognitive_depth_from_gate(gate: float) -> float:
    """Continuous depth in [0, 3]."""
    return round(3.0 * _clamp01(gate), 6)


def depth_limitation_reason(
    *,
    condition: DevelopmentalCondition,
    global_ceiling: float,
    local_maturity: float,
    effective: float,
) -> str:
    if condition is DevelopmentalCondition.DISABLED:
        return "DISABLED"
    if condition is DevelopmentalCondition.ADULT_FROM_TICK_0:
        return "ADULT_CONTROL_FULL_DEPTH"
    if effective >= 0.95:
        return "SUFFICIENT_LOCAL_EVIDENCE"
    if global_ceiling < local_maturity - 1e-9 and global_ceiling < 0.95:
        return "EARLY_GLOBAL_CEILING"
    if local_maturity < 0.25:
        return "INSUFFICIENT_LOCAL_EVIDENCE"
    if local_maturity < 0.55:
        return "PARTIAL_LOCAL_EVIDENCE"
    return "INTEGRATING_LOCAL_EVIDENCE"


def compute_global_ceiling(
    *,
    tick: int,
    config: DevelopmentalConfig,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    """Early-life ceiling from time + global structure. At/after max_ticks → 1.0."""
    structure = structural_maturity(metrics, config)
    developmental_tick = max(0, int(tick))
    time_progress = _clamp01(developmental_tick / max(1, config.target_ticks))
    blended = (
        config.maturity_weight_time * time_progress
        + config.maturity_weight_structure * structure
    )
    if developmental_tick < config.min_ticks:
        ceiling = 0.85 * _clamp01(developmental_tick / max(1, config.min_ticks))
        ceiling = min(blended, ceiling)
        matured = False
    elif developmental_tick >= config.max_ticks:
        ceiling = 1.0
        matured = True
    else:
        past_min = developmental_tick - config.min_ticks
        span = max(1, config.max_ticks - config.min_ticks)
        soft_floor = 0.25 + 0.55 * _clamp01(past_min / span)
        ceiling = _clamp01(max(soft_floor * structure, blended * 0.5 + structure * 0.5))
        matured = ceiling >= 0.95 and structure >= 0.5
    return {
        "global_ceiling": round(_clamp01(ceiling), 6),
        "developmental_maturity": round(structure, 6),
        "time_progress": round(time_progress, 6),
        "globally_matured": bool(matured),
        "developmental_tick": developmental_tick,
    }


def _caps_from_gate(gate: float, config: DevelopmentalConfig) -> tuple[int, int]:
    recent_limit = config.early_recent_fragment_limit
    if gate >= 0.95:
        recent_limit = 10**9
    elif gate >= 0.55:
        recent_limit = max(recent_limit * 4, recent_limit)
    elif gate >= 0.25:
        recent_limit = max(recent_limit * 2, recent_limit)
    learned_cap = config.early_max_learned_proposals
    if gate >= 0.95:
        learned_cap = 10**9
    else:
        learned_cap = max(0, int(round(learned_cap + gate * 8)))
    return int(recent_limit), int(learned_cap)


def compute_developmental_gate(
    *,
    tick: int,
    config: DevelopmentalConfig,
    metrics: dict[str, Any],
    local: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return gate state including local maturity and cognitive depth.

    Backward compatible: without `local`, falls back to global-only gate
    (Update 1 behavior for callers that omit context).
    """
    condition = config.condition
    developmental_tick = max(0, int(tick))
    global_info = compute_global_ceiling(tick=tick, config=config, metrics=metrics)
    structure = float(global_info["developmental_maturity"])
    local = local or {
        "relevant_fragments": 0,
        "relevant_diversity": 0,
        "repeated_consequences": 0,
        "predictive_evidence": 0,
        "related_weighted_fragments": 0.0,
        "evidence_consistency": 0.0,
        "related_consistency": 1.0,
        "effective_sample_size": 0.0,
        "inspected": 0,
        "current_bucket": None,
    }
    local_mat = local_experience_maturity(local, config)

    if condition is DevelopmentalCondition.DISABLED:
        gate = 1.0
        ceiling = 1.0
        matured = True
        time_progress = 1.0
    elif condition is DevelopmentalCondition.ADULT_FROM_TICK_0:
        gate = 1.0
        ceiling = 1.0
        matured = True
        time_progress = 1.0
        local_mat = 1.0  # control ignores local scarcity
    else:
        # EXPERIENCE_GATED and DEVELOPMENTAL: evidence-gated depth.
        ceiling = float(global_info["global_ceiling"])
        time_progress = float(global_info["time_progress"])
        # Effective accessibility cannot exceed early ceiling, and cannot
        # exceed local evidence support (novel contexts stay shallow).
        if local is not None and (
            local.get("current_bucket") is not None
            or int(local.get("relevant_fragments", 0)) > 0
            or float(local.get("related_weighted_fragments", 0)) > 0
            or True
        ):
            # Always prefer local under experience gating when computed.
            gated_local = (
                config.local_gate_weight * local_mat
                + (1.0 - config.local_gate_weight) * structure
            )
            gate = min(ceiling, _clamp01(gated_local))
        else:
            gate = ceiling
        matured = bool(global_info["globally_matured"]) and gate >= 0.95

    # If caller omitted local entirely (None passed explicitly as missing metrics
    # with empty default), Update-1-compatible path when condition is DEVELOPMENTAL
    # and no bucket: use ceiling alone for gate_factor legacy tests that don't
    # pass local — handled above with empty local → local_mat=0 → gate=0 early.
    # For legacy tests expecting global structure without local, detect empty bucket
    # and no fragments: blend toward ceiling*structure so old global tests still move.
    if (
        condition in (DevelopmentalCondition.DEVELOPMENTAL, DevelopmentalCondition.EXPERIENCE_GATED)
        and local.get("current_bucket") is None
        and int(local.get("relevant_fragments", 0)) == 0
        and float(local.get("related_weighted_fragments", 0)) == 0
        and float(local.get("inspected", 0)) == 0
    ):
        # No contextual probe provided: preserve Update-1 global gate.
        gate = float(global_info["global_ceiling"]) if condition is DevelopmentalCondition.DEVELOPMENTAL else min(
            float(global_info["global_ceiling"]), max(local_mat, structure * 0.0)
        )
        # EXPERIENCE_GATED without cue still uses ceiling (newborn-safe).
        if condition is DevelopmentalCondition.EXPERIENCE_GATED:
            gate = float(global_info["global_ceiling"]) * max(local_mat, 0.0)
            # With no local probe, treat as unsupported → low unless adult control.
            gate = min(float(global_info["global_ceiling"]), local_mat)
        else:
            # DEVELOPMENTAL without local → legacy global ceiling gate.
            gate = float(global_info["global_ceiling"])

    stage = stage_for_gate(gate)
    recent_limit, learned_cap = _caps_from_gate(gate, config)
    depth = cognitive_depth_from_gate(gate)
    reason = depth_limitation_reason(
        condition=condition,
        global_ceiling=float(global_info["global_ceiling"]),
        local_maturity=local_mat,
        effective=gate,
    )

    return {
        "condition": condition.value,
        "developmental_tick": developmental_tick,
        "developmental_stage": stage.value,
        "developmental_maturity": round(structure, 6),
        "local_experience_maturity": round(local_mat, 6),
        "global_ceiling": round(float(global_info["global_ceiling"]), 6),
        "gate_factor": round(_clamp01(gate), 6),
        "cognitive_depth": depth,
        "depth_limitation_reason": reason,
        "time_progress": round(time_progress, 6),
        "matured": bool(matured),
        "retrieval_recent_limit": int(recent_limit),
        "max_learned_proposals_cap": int(learned_cap),
        "retrieval_breadth": int(recent_limit if recent_limit < 10**8 else -1),
        "experience_metrics": dict(metrics),
        "local_metrics": {
            key: value
            for key, value in local.items()
            if key != "records"
        },
        "config": {
            "min_ticks": config.min_ticks,
            "target_ticks": config.target_ticks,
            "max_ticks": config.max_ticks,
        },
    }


def apply_gate_to_sensorimotor_config(base: Any, gate: dict[str, Any]) -> Any:
    from dataclasses import replace

    factor = float(gate.get("gate_factor", 1.0))
    cap = int(gate.get("max_learned_proposals_cap", 10**9))
    max_learned = int(getattr(base, "max_learned_proposals", 6))
    if factor >= 0.999 and cap >= max_learned:
        return base
    scaled = max(0, min(max_learned, int(round(max_learned * factor)), cap))
    return replace(
        base,
        max_learned_proposals=scaled,
        min_support=float(getattr(base, "min_support", 3.0)) * (1.0 + (1.0 - factor)),
    )


def gated_retrieve_keys(keys: list[str], gate: dict[str, Any] | None) -> list[str]:
    if not gate:
        return keys
    limit = int(gate.get("retrieval_recent_limit", 10**9))
    if limit >= len(keys):
        return keys
    return keys[-limit:]


from .contracts import PsycheModule, PsycheOutput, PsycheStage, PsycheUpdate


class DevelopmentalGateModule(PsycheModule):
    """Computes global + local experience gates for later retrieval stages.

    Memory formation is unchanged. Observer may read `memory.developmental`.
    Cognition only consumes retrieval caps implied by working.developmental_gate.
    """

    module_id = "PSY-DEVELOPMENTAL-GATE-V01"
    version = "0.2.0"
    stage = PsycheStage.MEMORY

    def __init__(self, config: DevelopmentalConfig | None = None) -> None:
        self.config = config or DevelopmentalConfig()

    def process(self, context) -> PsycheOutput:  # type: ignore[override]
        if self.config.condition is DevelopmentalCondition.DISABLED:
            return PsycheOutput(signals={"developmental_disabled": True})

        sensorimotor = context.state.memory.get("sensorimotor")
        if not isinstance(sensorimotor, dict):
            sensorimotor = {}
        episodes = context.state.memory.get("episodes")
        action_models = context.state.learning.get("action_models")
        metrics = measure_experience_structure(
            sensorimotor=sensorimotor,
            episodes=episodes if isinstance(episodes, list) else [],
            action_models=action_models if isinstance(action_models, dict) else {},
        )

        # Current context cue from attention/observation (already agent-visible).
        from .sensorimotor import context_cue, cue_bucket

        attended = context.state.attention.get("current")
        observation = context.observation
        cue_source = observation
        if isinstance(attended, dict) and attended:
            payload = dict(getattr(observation, "data", {}) or {})
            for key in ("position", "visible_objects", "available_actions", "interoception"):
                if key in attended and key not in payload:
                    payload[key] = attended[key]
            if attended.get("available_actions"):
                payload["available_actions"] = attended.get("available_actions")
            if attended.get("visible_objects") is not None:
                payload["visible_objects"] = attended.get("visible_objects")
            if attended.get("position") is not None:
                payload["position"] = attended.get("position")
            cue_source = payload
        cue_mode = None
        sm = context.state.memory.get("sensorimotor")
        # Prefer explicit observation cue_mode if present.
        if isinstance(cue_source, dict):
            cue_mode = cue_source.get("cue_mode")
        cue = context_cue(cue_source, cue_mode=cue_mode)
        bucket = cue_bucket(cue)
        local = measure_local_experience(
            sensorimotor=sensorimotor,
            current_bucket=bucket,
            related_weight=self.config.local_related_weight,
            budget_total=12,
        )
        gate = compute_developmental_gate(
            tick=int(context.tick),
            config=self.config,
            metrics=metrics,
            local=local,
        )
        prior = context.state.working.get("developmental_gate")
        prior_depth = (
            float(prior.get("cognitive_depth"))
            if isinstance(prior, dict) and prior.get("cognitive_depth") is not None
            else None
        )
        depth_delta = None if prior_depth is None else round(gate["cognitive_depth"] - prior_depth, 6)

        working_gate = {
            "gate_factor": gate["gate_factor"],
            "retrieval_recent_limit": gate["retrieval_recent_limit"],
            "max_learned_proposals_cap": gate["max_learned_proposals_cap"],
            "developmental_stage": gate["developmental_stage"],
            "developmental_maturity": gate["developmental_maturity"],
            "local_experience_maturity": gate["local_experience_maturity"],
            "cognitive_depth": gate["cognitive_depth"],
            "depth_limitation_reason": gate["depth_limitation_reason"],
            "global_ceiling": gate["global_ceiling"],
            "matured": gate["matured"],
            "condition": gate["condition"],
            "retrieval_breadth": gate["retrieval_breadth"],
            "relevant_evidence": gate["local_metrics"].get("relevant_fragments"),
            "evidence_consistency": gate["local_metrics"].get("evidence_consistency"),
            "depth_delta": depth_delta,
        }
        snapshot = deepcopy(gate)
        snapshot["depth_delta"] = depth_delta
        return PsycheOutput(
            updates=(
                PsycheUpdate("memory", "developmental", snapshot),
                PsycheUpdate("working", "developmental_gate", working_gate),
            ),
            signals={"developmental": snapshot},
        )
