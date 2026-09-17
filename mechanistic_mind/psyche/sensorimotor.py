"""Experience-structured sensorimotor generation.

One continuous generator. Endogenous variation does not turn off with age,
tick, or memory size. Learned contingencies may structure proposals only
through bounded retrieval. Unknown is not a reward.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from math import log1p
from typing import Any

from mechanistic_mind.agent import Action, Observation

from .contracts import (
    PsycheActionCandidate,
    PsycheContext,
    PsycheModule,
    PsycheOutput,
    PsycheSelection,
    PsycheStage,
    PsycheUpdate,
)


BUDGET_PATTERN = 4
BUDGET_EXCEPTION = 4
BUDGET_EPISODE = 8
BUDGET_TOTAL = 12

FORBIDDEN_SWITCH_KEYS = frozenset(
    {
        "exploration_mode",
        "exploitation_mode",
        "curiosity",
        "novelty_bonus",
        "information_gain_reward",
        "controllability_reward",
        "age_randomness",
    }
)


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _numeric(value: Any) -> dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): float(val)
        for key, val in value.items()
        if isinstance(val, (int, float)) and not isinstance(val, bool)
    }


def available_actions(observation: Observation | dict[str, Any]) -> tuple[str, ...]:
    data = observation.data if isinstance(observation, Observation) else observation
    raw = ()
    if isinstance(data, dict):
        raw = data.get("available_actions") or ()
        attended = data.get("perceptual_context")
        if not raw and isinstance(attended, dict):
            raw = attended.get("available_actions") or ()
    return tuple(str(item) for item in raw)


def visible_object_ids(observation: Observation | dict[str, Any]) -> frozenset[str]:
    data = observation.data if isinstance(observation, Observation) else observation
    if not isinstance(data, dict):
        return frozenset()
    visible = data.get("visible_objects") or ()
    ids = []
    if isinstance(visible, (list, tuple)):
        for item in visible:
            if isinstance(item, dict) and item.get("id"):
                ids.append(str(item["id"]))
    return frozenset(ids)


def interoception(observation: Observation | dict[str, Any]) -> dict[str, float]:
    data = observation.data if isinstance(observation, Observation) else observation
    if not isinstance(data, dict):
        return {}
    return _numeric(data.get("interoception"))


def context_cue(
    observation: Observation | dict[str, Any],
    *,
    cue_mode: str | None = None,
) -> dict[str, Any]:
    data = observation.data if isinstance(observation, Observation) else observation
    if not isinstance(data, dict):
        data = {}
    mode = str(cue_mode or data.get("cue_mode") or "LEGACY_CUE_ONLY")
    position = data.get("position")
    visible = []
    for item in data.get("visible_objects") or ():
        if not isinstance(item, dict):
            continue
        visible.append(
            (
                str(item.get("cue_signature") or item.get("id") or ""),
                tuple(item.get("relative_offset") or ()),
                str(item.get("interaction_state") or "FREE"),
            )
        )
    visible.sort()
    body = interoception(data)
    bands = {
        key: ("L" if val < 1 / 3 else "M" if val < 2 / 3 else "H")
        for key, val in sorted(body.items())
    }
    perceptual_features: tuple[str, ...] = ()
    if mode == "PERCEPTUAL_CUE_ENABLED":
        from .perceptual_cue import perceptual_feature_tokens

        pp = data.get("physical_perception")
        perceptual_features = perceptual_feature_tokens(
            pp if isinstance(pp, dict) else None
        )
    return {
        "position": list(position) if isinstance(position, (list, tuple)) else None,
        "visible": visible[:8],
        "body_bands": bands,
        "affordances": available_actions(data),
        "perceptual_features": perceptual_features,
        "cue_mode": mode,
    }


def cue_signature(cue: dict[str, Any]) -> str:
    return repr(
        (
            tuple(cue.get("position") or ()),
            tuple(cue.get("visible") or ()),
            tuple(sorted((cue.get("body_bands") or {}).items())),
            tuple(cue.get("affordances") or ()),
            tuple(cue.get("perceptual_features") or ()),
            str(cue.get("cue_mode") or "LEGACY_CUE_ONLY"),
        )
    )


def cue_bucket(cue: dict[str, Any]) -> str:
    visible = tuple(item[0] for item in (cue.get("visible") or ())[:4])
    bands = tuple(sorted((cue.get("body_bands") or {}).items()))
    percept = tuple(cue.get("perceptual_features") or ())[:12]
    return repr((visible, bands, percept))


def action_is_physical(action: str, available: set[str], visible: frozenset[str]) -> bool:
    if action not in available:
        return False
    if action.startswith(("USE:", "TAKE:", "PUSH:", "RELEASE:")):
        object_id = action.split(":", 2)[1] if ":" in action else ""
        if action.startswith("PUSH:"):
            object_id = action.split(":")[1]
        if object_id and object_id not in visible and not action.startswith("RELEASE:"):
            return False
    return True


def observed_transition(
    before: dict[str, Any],
    after: dict[str, Any],
    action: str,
) -> dict[str, Any]:
    before_objects = {
        str(item.get("id")): item
        for item in before.get("visible_objects") or ()
        if isinstance(item, dict) and item.get("id")
    }
    after_objects = {
        str(item.get("id")): item
        for item in after.get("visible_objects") or ()
        if isinstance(item, dict) and item.get("id")
    }
    displacements = []
    for object_id, record in after_objects.items():
        previous = before_objects.get(object_id)
        if not previous:
            continue
        pos_a = tuple(previous.get("position") or ())
        pos_b = tuple(record.get("position") or ())
        if pos_a and pos_b and pos_a != pos_b:
            displacements.append(
                {
                    "object_id": object_id,
                    "from": list(pos_a),
                    "to": list(pos_b),
                }
            )
    body_before = _numeric(before.get("interoception"))
    body_after = _numeric(after.get("interoception"))
    body_delta = {
        key: body_after.get(key, 0.0) - body_before.get(key, 0.0)
        for key in set(body_before) | set(body_after)
    }
    def _channel_sig(obs: dict[str, Any]) -> tuple:
        pp = obs.get("physical_perception")
        if not isinstance(pp, dict):
            return ()
        summary = pp.get("summary") or {}
        if not isinstance(summary, dict):
            return ()
        rows = []
        for name in (
            "DISTANT_STRUCTURAL",
            "PASSIVE_WAVE",
            "ACTIVE_RETURN",
            "NEAR_CONTACT",
        ):
            row = summary.get(name) or {}
            if not isinstance(row, dict):
                continue
            rows.append(
                (
                    name,
                    int(row.get("active_count", 0) or 0),
                    round(float(row.get("strength_sum", 0.0) or 0.0), 3),
                    int(row.get("feature_diversity", 0) or 0),
                )
            )
        return tuple(rows)

    before_ch = _channel_sig(before)
    after_ch = _channel_sig(after)
    return {
        "action": action,
        "displacements": displacements,
        "body_delta": body_delta,
        "visual_changed": before.get("visual_fragments") != after.get("visual_fragments"),
        "channel_changed": before_ch != after_ch,
        "channel_before": before_ch,
        "channel_after": after_ch,
    }


@dataclass
class SensorimotorConfig:
    endogenous_variation: bool = True
    learned_structuring: bool = True
    contingency_memory: bool = True
    max_endogenous_proposals: int = 6
    max_learned_proposals: int = 6
    max_total_proposals: int = 12
    min_confidence: float = 0.35
    min_support: float = 3.0
    contrast_min: float = 0.25
    # Optional developmental gating. DISABLED by default (prior behavior).
    developmental: object | None = None
    cue_mode: str = "LEGACY_CUE_ONLY"
    # Update 4.4: expose acquired MPs as ordinary candidates (no value bonus).
    motor_primitive_bridge: bool = True
    # Update 4.5: evaluate MP predicted physical deltas with ordinary target-gain.
    prospective_valuation: bool = True
    # Experiment E: retrieve MP but block prospective prediction use.
    prediction_ablated: bool = False
    # Update 4.10 — bounded temporal contingency (OFF by default).
    temporal_contingency_enabled: bool = False
    temporal_state_conditioning: bool = True
    temporal_lags: tuple = (0, 1, 2, 3)
    temporal_action_conditioning: bool = True
    temporal_context_conditioning: bool = True
    temporal_min_support: float = 3.0
    # Update 4.16: hard control over fresh trace construction only.  Existing
    # current_prospective_trace mechanism state is not erased by this switch.
    temporal_reconstruction_ablated: bool = False


@dataclass
class SensorimotorStore:
    contingencies: dict[str, dict[str, Any]] = field(default_factory=dict)
    index: dict[str, list[str]] = field(default_factory=dict)
    last_cue: dict[str, Any] | None = None
    last_observation: dict[str, Any] | None = None
    last_action: str | None = None
    selected_action: str | None = None
    executed_action: str | None = None
    execution_open_stash: dict[str, Any] | None = None
    temporal_contingency: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contingencies": deepcopy(self.contingencies),
            "index": deepcopy(self.index),
            "last_cue": deepcopy(self.last_cue),
            "last_observation": deepcopy(self.last_observation),
            "last_action": self.last_action,
            "selected_action": self.selected_action,
            "executed_action": self.executed_action,
            "execution_open_stash": deepcopy(self.execution_open_stash),
            "temporal_contingency": deepcopy(self.temporal_contingency),
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> "SensorimotorStore":
        data = raw or {}
        store = cls()
        store.contingencies = deepcopy(_mapping(data.get("contingencies")))
        store.index = {
            str(key): [str(item) for item in value]
            for key, value in _mapping(data.get("index")).items()
            if isinstance(value, list)
        }
        store.last_cue = data.get("last_cue") if isinstance(data.get("last_cue"), dict) else None
        store.last_observation = (
            data.get("last_observation")
            if isinstance(data.get("last_observation"), dict)
            else None
        )
        store.last_action = (
            str(data["last_action"]) if data.get("last_action") is not None else None
        )
        store.selected_action = (
            str(data["selected_action"]) if data.get("selected_action") is not None else None
        )
        store.executed_action = (
            str(data["executed_action"]) if data.get("executed_action") is not None else None
        )
        stash = data.get("execution_open_stash")
        store.execution_open_stash = deepcopy(stash) if isinstance(stash, dict) else None
        tc = data.get("temporal_contingency")
        store.temporal_contingency = deepcopy(tc) if isinstance(tc, dict) else None
        return store


def _contingency_key(bucket: str, action: str) -> str:
    return f"{bucket}||{action}"


def retrieve_evidence(
    store: SensorimotorStore,
    cue: dict[str, Any],
    *,
    available: set[str],
    developmental_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    bucket = cue_bucket(cue)
    keys = list(store.index.get(bucket, ()))
    if developmental_gate is not None:
        from .developmental import gated_retrieve_keys

        keys = gated_retrieve_keys(keys, developmental_gate)
    inspected = 0
    hits: list[dict[str, Any]] = []
    for key in keys:
        if inspected >= BUDGET_TOTAL:
            break
        record = store.contingencies.get(key)
        if not isinstance(record, dict):
            continue
        inspected += 1
        if record.get("action") not in available:
            continue
        hits.append(record)
        if len(hits) >= BUDGET_PATTERN:
            break
    stage = "PATTERN" if hits else "UNKNOWN"
    best = max(hits, key=lambda item: float(item.get("confidence", 0.0)), default=None)
    evidence_quality = 0.0
    if best is not None:
        evidence_quality = min(
            1.0,
            float(best.get("confidence", 0.0))
            * min(1.0, log1p(float(best.get("support", 0.0))) / log1p(8.0)),
        )
    return {
        "stage": stage,
        "inspected": inspected,
        "hits": hits,
        "best": best,
        "quality": evidence_quality,
        "unknown": not hits,
        "budget": {
            "max_pattern_candidates": BUDGET_PATTERN,
            "max_exception_candidates": BUDGET_EXCEPTION,
            "max_episode_candidates": BUDGET_EPISODE,
            "max_total_memory_candidates": BUDGET_TOTAL,
        },
    }


def _endogenous_order(actions: list[str], random_value: float) -> list[str]:
    if not actions:
        return []
    start = int(random_value * len(actions)) % len(actions)
    return actions[start:] + actions[:start]


def generate_proposals(
    *,
    observation: Observation | dict[str, Any],
    store: SensorimotorStore,
    config: SensorimotorConfig,
    random_value: float,
    values: dict[str, Any] | None = None,
    developmental_gate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    available = list(available_actions(observation))
    available_set = set(available)
    visible = visible_object_ids(observation)
    legal = [
        action
        for action in available
        if action_is_physical(action, available_set, visible)
    ]
    cue = context_cue(observation, cue_mode=config.cue_mode)
    evidence = retrieve_evidence(
        store,
        cue,
        available=available_set,
        developmental_gate=developmental_gate,
    )
    active_config = config
    if developmental_gate is not None:
        from .developmental import apply_gate_to_sensorimotor_config

        active_config = apply_gate_to_sensorimotor_config(config, developmental_gate)
        # Gate scales how strongly retrieved history may structure proposals.
        factor = float(developmental_gate.get("gate_factor", 1.0))
        evidence = {
            **evidence,
            "quality": float(evidence.get("quality", 0.0)) * factor,
        }
    quality = float(evidence["quality"]) if active_config.learned_structuring else 0.0
    if not active_config.contingency_memory:
        evidence = {**evidence, "hits": [], "best": None, "unknown": True, "quality": 0.0}
        quality = 0.0

    values = values or {}
    proposals: list[dict[str, Any]] = []
    learned_actions = set()
    if active_config.learned_structuring:
        ranked = sorted(
            evidence.get("hits") or [],
            key=lambda item: (
                -float(item.get("confidence", 0.0)),
                -float(item.get("support", 0.0)),
                str(item.get("action")),
            ),
        )
        budget = max(0, min(active_config.max_learned_proposals, active_config.max_total_proposals))
        # Stronger evidence → more of the budget may be filled by learned items,
        # but the generator itself is not replaced.
        learned_slots = int(round(quality * budget))
        if quality >= active_config.min_confidence and ranked and budget > 0:
            learned_slots = max(learned_slots, 1)
        for record in ranked[:learned_slots]:
            action = str(record.get("action"))
            if action not in available_set:
                continue
            if float(record.get("confidence", 0.0)) < active_config.min_confidence:
                continue
            if float(record.get("support", 0.0)) < active_config.min_support and quality < 0.6:
                continue
            learned_actions.add(action)
            proposals.append(
                _proposal(
                    action,
                    source="LEARNED_SENSORIMOTOR",
                    confidence=float(record.get("confidence", 0.0)),
                    support=float(record.get("support", 0.0)),
                    predicted=record.get("mean_transition") or {},
                    values=values,
                )
            )

    if active_config.endogenous_variation:
        remaining = [action for action in legal if action not in learned_actions]
        if "WAIT" in remaining:
            remaining = ["WAIT"] + [action for action in remaining if action != "WAIT"]
        ordered = _endogenous_order(remaining, random_value)
        # Evidence never disables endogenous generation. It only shrinks how
        # many additional weakly structured proposals are emitted.
        endogenous_slots = max(
            1 if ordered else 0,
            int(round((1.0 - quality) * active_config.max_endogenous_proposals)),
        )
        room = max(0, active_config.max_total_proposals - len(proposals))
        chosen_endogenous = ordered[: min(endogenous_slots, room)]
        if "WAIT" in remaining and "WAIT" not in chosen_endogenous and room > len(chosen_endogenous):
            chosen_endogenous.append("WAIT")
        elif "WAIT" in remaining and "WAIT" not in chosen_endogenous and chosen_endogenous:
            chosen_endogenous[-1] = "WAIT"
        for action in chosen_endogenous:
            proposals.append(
                _proposal(
                    action,
                    source="ENDOGENOUS_VARIATION",
                    confidence=0.0,
                    support=0.0,
                    predicted={},
                    values=values,
                )
            )
    elif not proposals:
        # Learned-only ablation: still propose legal actions with no extra value.
        for action in legal[: active_config.max_total_proposals]:
            proposals.append(
                _proposal(
                    action,
                    source="LEARNED_SENSORIMOTOR" if action in learned_actions else "ENDOGENOUS_VARIATION",
                    confidence=0.0,
                    support=0.0,
                    predicted={},
                    values=values,
                )
            )

    # Dual-source tag when the same action was both legal-endogenous and learned.
    by_action: dict[str, dict[str, Any]] = {}
    for item in proposals:
        existing = by_action.get(item["action"])
        if existing is None:
            by_action[item["action"]] = item
            continue
        existing["source"] = "BOTH"
        existing["confidence"] = max(float(existing["confidence"]), float(item["confidence"]))
        existing["support"] = max(float(existing["support"]), float(item["support"]))
    merged = list(by_action.values())
    merged.sort(key=lambda item: (item["action"], item["source"]))
    return {
        "cue": cue,
        "available": legal,
        "evidence": evidence,
        "proposals": merged[: active_config.max_total_proposals],
        "quality": quality,
        "developmental_gate": deepcopy(developmental_gate) if developmental_gate else None,
    }


def _proposal(
    action: str,
    *,
    source: str,
    confidence: float,
    support: float,
    predicted: dict[str, Any],
    values: dict[str, Any],
) -> dict[str, Any]:
    record = values.get(action, {}) if isinstance(values, dict) else {}
    total = 0.0
    components: dict[str, float] = {}
    if isinstance(record, dict):
        components = {
            str(key): float(val)
            for key, val in record.items()
            if isinstance(val, (int, float)) and not isinstance(val, bool) and key != "base_total"
        }
        total = float(record.get("base_total", 0.0))
    return {
        "action": action,
        "source": source,
        "confidence": float(confidence),
        "support": float(support),
        "predicted_transition": deepcopy(predicted),
        "ordinary_action_value": total,
        "components": components,
    }


def select_proposal(
    generated: dict[str, Any],
    *,
    body: dict[str, float],
    random_value: float,
) -> dict[str, Any]:
    proposals = list(generated.get("proposals") or [])
    if not proposals:
        return {
            "action": "WAIT",
            "reason": "NO_CANDIDATES",
            "score": 0.0,
            "selected": None,
            "candidates": [],
            "tie": False,
            "tie_break": None,
            "decision_source": "FALLBACK_WAIT",
        }
    energy = float(body.get("energy_signal", body.get("energy", 1.0)))
    hydration = float(body.get("hydration_signal", body.get("hydration", 1.0)))
    fatigue = float(body.get("fatigue_signal", body.get("fatigue", 0.0)))
    severe = energy < 0.18 or hydration < 0.18 or fatigue > 0.82

    def score(item: dict[str, Any]) -> float:
        value = float(item.get("ordinary_action_value", 0.0))
        action = str(item.get("action"))
        effort = 0.0
        if action.startswith(("PUSH:", "TAKE:", "USE:", "MOVE:")):
            effort = 0.04
        if severe and action != "WAIT":
            value -= 0.35 + effort
        # Learned structure may change which actions are proposed. It does not
        # add a controllability or novelty bonus to value.
        return value

    ranked = sorted(
        proposals,
        key=lambda item: (-score(item), str(item.get("action")), random_value),
    )
    selected = ranked[0]
    reason = "ORDINARY_VALUE"
    tie = False
    tie_break = None
    if len(ranked) >= 2 and abs(score(ranked[0]) - score(ranked[1])) < 1e-12:
        tie = True
        # Documented: secondary key is lexicographic action string, then RNG.
        if str(ranked[0].get("action")) != str(ranked[1].get("action")):
            tie_break = "LEXICOGRAPHIC_ACTION"
        else:
            tie_break = "RANDOM_VALUE"
        reason = "TIE_BREAK_" + tie_break
    if severe and selected["action"] != "WAIT" and any(item["action"] == "WAIT" for item in proposals):
        wait = next(item for item in proposals if item["action"] == "WAIT")
        if score(wait) >= score(selected):
            selected = wait
            reason = "PHYSIOLOGY_SUPPRESSION"
            tie = False
            tie_break = None
    candidates = []
    for item in ranked[:12]:
        conf = float(item.get("confidence", 0.0))
        supp = float(item.get("support", 0.0))
        # Update 4.3: expose epistemic absence explicitly (Observer/telemetry).
        # Does not alter score() or ranking.
        if supp <= 0.0 and conf <= 0.0 and not (item.get("predicted_transition") or {}):
            pred_status = "NO_EVIDENCE"
        elif supp < 3.0 or conf < 0.35:
            pred_status = "INSUFFICIENT_EVIDENCE"
        else:
            pred_status = "SUPPORTED"
        candidates.append(
            {
                "action": item.get("action"),
                "source": item.get("source"),
                "score": score(item),
                "ordinary_action_value": float(item.get("ordinary_action_value", 0.0)),
                "confidence": conf,
                "support": supp,
                "prediction_status": pred_status,
            }
        )
    return {
        "action": selected["action"],
        "reason": reason,
        "score": score(selected),
        "selected": selected,
        "candidates": candidates,
        "tie": tie,
        "tie_break": tie_break,
        "decision_source": str(selected.get("source") or "UNKNOWN"),
    }


def update_store(
    store: SensorimotorStore,
    *,
    observation: dict[str, Any],
    config: SensorimotorConfig,
) -> dict[str, Any] | None:
    if not config.contingency_memory:
        store.last_observation = deepcopy(observation)
        return None
    event = None
    if store.last_observation is not None and store.last_action:
        transition = observed_transition(
            store.last_observation,
            observation,
            store.last_action,
        )
        cue = store.last_cue or context_cue(
            store.last_observation, cue_mode=config.cue_mode
        )
        bucket = cue_bucket(cue)
        key = _contingency_key(bucket, store.last_action)
        record = store.contingencies.get(key)
        displaced = 1.0 if transition["displacements"] else 0.0
        if record is None:
            record = {
                "key": key,
                "bucket": bucket,
                "action": store.last_action,
                "support": 0.0,
                "displace_rate": 0.0,
                "confidence": 0.0,
                "mean_transition": {
                    "displace_rate": 0.0,
                    "visual_changed_rate": 0.0,
                    "channel_changed_rate": 0.0,
                },
                "without_action_displace_rate": None,
                "causal_confidence": 0.0,
            }
        support = float(record["support"]) + 1.0
        displace_rate = (
            float(record["displace_rate"]) * (support - 1.0) + displaced
        ) / support
        visual_rate = (
            float(record["mean_transition"].get("visual_changed_rate", 0.0)) * (support - 1.0)
            + (1.0 if transition["visual_changed"] else 0.0)
        ) / support
        channel_rate = (
            float(record["mean_transition"].get("channel_changed_rate", 0.0)) * (support - 1.0)
            + (1.0 if transition.get("channel_changed") else 0.0)
        ) / support
        # Contrast: other actions in same bucket.
        contrast_rates = [
            float(other.get("displace_rate", 0.0))
            for other_key, other in store.contingencies.items()
            if other_key != key and other.get("bucket") == bucket
        ]
        baseline = (
            sum(contrast_rates) / len(contrast_rates) if contrast_rates else None
        )
        causal = 0.0
        if baseline is None:
            causal = 0.0
        else:
            causal = max(0.0, displace_rate - baseline)
        confidence = min(1.0, displace_rate * min(1.0, support / 4.0))
        if causal > 0:
            confidence = min(1.0, 0.5 * confidence + 0.5 * min(1.0, causal / 0.5))
        error = abs(float(record["displace_rate"]) - displaced) if support > 1 else 0.0
        if error > 0.6 and support >= 3:
            confidence *= 0.55
            record["weakened"] = int(record.get("weakened", 0)) + 1
        if confidence < 0.08 and support >= 6 and displace_rate < 0.15:
            record["invalidated"] = True
            confidence = 0.0
        record.update(
            {
                "support": support,
                "displace_rate": displace_rate,
                "confidence": confidence,
                "causal_confidence": causal,
                "without_action_displace_rate": baseline,
                "mean_transition": {
                    "displace_rate": displace_rate,
                    "visual_changed_rate": visual_rate,
                    "channel_changed_rate": channel_rate,
                    "last_body_delta": transition["body_delta"],
                },
            }
        )
        store.contingencies[key] = record
        bucket_keys = store.index.setdefault(bucket, [])
        if key not in bucket_keys:
            bucket_keys.append(key)
            store.index[bucket] = bucket_keys[-BUDGET_TOTAL:]
        event = {
            "updated_key": key,
            "confidence": confidence,
            "support": support,
            "displace_rate": displace_rate,
            "causal_confidence": causal,
            "prediction_error": error,
            "invalidated": bool(record.get("invalidated", False)),
        }
    # Update 4.10: advance temporal contingency pending traces (opt-in).
    if bool(getattr(config, "temporal_contingency_enabled", False)):
        from mechanistic_mind.psyche.temporal_contingency import (
            ensure_temporal,
            settle_pending,
        )
        raw = store.to_dict()
        tc = ensure_temporal(raw)
        settle_pending(
            tc,
            observation=observation if isinstance(observation, dict) else {},
            lags=tuple(getattr(config, "temporal_lags", (0, 1, 2, 3))),
        )
        store.temporal_contingency = tc

    store.last_observation = deepcopy(observation)
    store.last_cue = context_cue(observation, cue_mode=config.cue_mode)
    return event


def remember_action(
    store: SensorimotorStore,
    action: str,
    observation: dict[str, Any],
    *,
    cue_mode: str | None = None,
    config: "SensorimotorConfig | None" = None,
) -> None:
    """Record policy-selected action and stash decision-time obs for execution commit.

    Update 4.10.2: do NOT open temporal pending here. Temporal / performed-action
    learning commits after the execution layer resolves the own executed action.
    """
    store.selected_action = str(action)
    store.last_cue = context_cue(observation, cue_mode=cue_mode)
    store.last_observation = deepcopy(observation)
    cfg = config
    cue = store.last_cue or context_cue(observation, cue_mode=cue_mode)
    bucket = "*"
    if cfg is not None and bool(getattr(cfg, "temporal_context_conditioning", True)):
        try:
            from mechanistic_mind.psyche.temporal_contingency import temporal_cue_bucket
            bucket = temporal_cue_bucket(cue)
        except Exception:
            bucket = "*"
    store.execution_open_stash = {
        "selected_action": str(action),
        "observation": deepcopy(observation) if isinstance(observation, dict) else {},
        "bucket": bucket,
        "cue_mode": cue_mode,
        "temporal_contingency_enabled": bool(
            cfg is not None and getattr(cfg, "temporal_contingency_enabled", False)
        ),
        "temporal_lags": tuple(getattr(cfg, "temporal_lags", (0, 1, 2, 3))) if cfg else (0, 1, 2, 3),
        "temporal_action_conditioning": bool(
            getattr(cfg, "temporal_action_conditioning", True) if cfg else True
        ),
        "temporal_context_conditioning": bool(
            getattr(cfg, "temporal_context_conditioning", True) if cfg else True
        ),
    }


def commit_executed_action(
    store: SensorimotorStore,
    executed_action: str,
    *,
    selected_action: str | None = None,
    config: "SensorimotorConfig | None" = None,
) -> dict[str, Any]:
    """Bind ordinary own-action learning to the execution-layer action token.

    Cognition-facing fields: selected_action, executed_action only.
    No intervention-source labels.
    """
    stash = store.execution_open_stash if isinstance(store.execution_open_stash, dict) else {}
    selected = str(
        selected_action
        if selected_action is not None
        else (stash.get("selected_action") or store.selected_action or "")
    )
    executed = str(executed_action)
    store.selected_action = selected or store.selected_action
    store.executed_action = executed
    store.last_action = executed  # performed-action consumers use executed
    evidence = {
        "selected_action": store.selected_action,
        "executed_action": executed,
    }
    opened = False
    temporal_key_action = None
    tc_enabled = bool(stash.get("temporal_contingency_enabled"))
    if config is not None:
        tc_enabled = bool(getattr(config, "temporal_contingency_enabled", False))
    if tc_enabled:
        from mechanistic_mind.psyche.temporal_contingency import (
            ensure_temporal,
            normalize_action,
            open_pending,
        )
        raw = store.to_dict()
        tc = ensure_temporal(raw)
        obs = stash.get("observation") if isinstance(stash.get("observation"), dict) else (
            deepcopy(store.last_observation) if isinstance(store.last_observation, dict) else {}
        )
        bucket = str(stash.get("bucket") or "*")
        lags = tuple(stash.get("temporal_lags") or (0, 1, 2, 3))
        if config is not None:
            lags = tuple(getattr(config, "temporal_lags", lags))
        open_pending(
            tc,
            action=executed,
            bucket=bucket,
            observation=obs,
            lags=lags,
            action_conditioning=bool(
                stash.get("temporal_action_conditioning", True)
                if config is None
                else getattr(config, "temporal_action_conditioning", True)
            ),
            context_conditioning=bool(
                stash.get("temporal_context_conditioning", True)
                if config is None
                else getattr(config, "temporal_context_conditioning", True)
            ),
        )
        store.temporal_contingency = tc
        opened = True
        temporal_key_action = normalize_action(executed)
    store.execution_open_stash = None
    return {
        "opened_temporal": opened,
        "temporal_action_key": temporal_key_action,
        "evidence": evidence,
    }


def evidence_bin(quality: float, unknown: bool) -> str:
    if unknown or quality <= 0.0:
        return "NO_RELEVANT_EVIDENCE"
    if quality < 0.25:
        return "WEAK_EVIDENCE"
    if quality < 0.60:
        return "MODERATE_EVIDENCE"
    return "STRONG_EVIDENCE"


class SensorimotorGenerationModule(PsycheModule):
    module_id = "PSY-SENSORIMOTOR-GENERATION-V05"
    version = "0.5.0"
    stage = PsycheStage.ACTION_GENERATION

    def __init__(self, config: SensorimotorConfig | None = None) -> None:
        self.config = config or SensorimotorConfig()

    def process(self, context: PsycheContext) -> PsycheOutput:
        store = SensorimotorStore.from_dict(context.state.memory.get("sensorimotor"))
        attended = _mapping(context.state.attention.get("current"))
        observation = context.observation
        payload = dict(observation.data)
        payload["cue_mode"] = self.config.cue_mode
        if attended.get("available_actions") and not available_actions(observation):
            payload["available_actions"] = attended.get("available_actions")
            payload.setdefault("visible_objects", attended.get("visible_objects", []))
            payload.setdefault("position", attended.get("position"))
        observation = Observation(data=payload)
        gate = context.state.working.get("developmental_gate")
        if not isinstance(gate, dict):
            gate = context.state.memory.get("developmental")
        if not isinstance(gate, dict):
            gate = None
        generated = generate_proposals(
            observation=observation,
            store=store,
            config=self.config,
            random_value=context.random_value,
            values=_mapping(context.state.values.get("by_action")),
            developmental_gate=gate,
        )
        candidates = []
        for item in generated["proposals"]:
            candidates.append(
                PsycheActionCandidate(
                    source_module=self.module_id,
                    action=Action(str(item["action"])),
                    total_value=float(item["ordinary_action_value"]),
                    components=dict(item.get("components") or {}),
                    metadata={
                        "proposal_source": item["source"],
                        "predictive_confidence": item["confidence"],
                        "support_count": item["support"],
                        "predicted_transition_summary": item.get("predicted_transition"),
                        "ordinary_action_value": item["ordinary_action_value"],
                        "local_interaction": str(item["action"]).startswith(
                            ("USE:", "TAKE:", "RELEASE:", "PUSH:")
                        ),
                        "movement": str(item["action"]).startswith("MOVE:"),
                    },
                )
            )
        cue = generated.get("cue") or context_cue(
            observation, cue_mode=self.config.cue_mode
        )
        from .perceptual_cue import cue_uptake_summary

        uptake = cue_uptake_summary(
            physical_perception=payload.get("physical_perception")
            if isinstance(payload.get("physical_perception"), dict)
            else None,
            cue=cue,
            mode=self.config.cue_mode,
        )
        # Mark retrieval match at channel-tag level when bucket used percept tokens.
        percept_tokens = set(cue.get("perceptual_features") or ())
        hits = generated["evidence"].get("hits") or []
        matched_percept = False
        matched_body_only = False
        matched_legacy_visible = False
        for hit in hits:
            bucket = str(hit.get("bucket") or "")
            if percept_tokens and any(tok in bucket for tok in list(percept_tokens)[:8]):
                matched_percept = True
            if "body_bands" in bucket or "'energy_signal'" in bucket:
                matched_body_only = True
            if "visible" in bucket or "GENERIC_" in bucket:
                matched_legacy_visible = True
        for name, row in uptake["channels"].items():
            if matched_percept and row["REPRESENTED_IN_CUE"] == "yes":
                row["MATCHED_IN_RETRIEVAL"] = "yes"
            elif self.config.cue_mode == "PERCEPTUAL_CUE_ENABLED":
                row["MATCHED_IN_RETRIEVAL"] = "no"
        diagnostics = {
            "physically_available_actions": generated["available"],
            "bounded_retrieval_stage": generated["evidence"]["stage"],
            "retrieved_predictive_evidence_count": len(hits),
            "retrieval_inspected": generated["evidence"]["inspected"],
            "evidence_quality": generated["quality"],
            "evidence_bin": evidence_bin(
                generated["quality"], bool(generated["evidence"].get("unknown"))
            ),
            "proposals": generated["proposals"],
            "budget": generated["evidence"]["budget"],
            "cue_mode": self.config.cue_mode,
            "cue_summary": {
                "perceptual_token_count": len(percept_tokens),
                "visible_count": len(cue.get("visible") or ()),
                "body_bands": cue.get("body_bands"),
                "affordance_count": len(cue.get("affordances") or ()),
            },
            "cue_uptake": uptake,
            "retrieval_match": {
                "perceptual_features": matched_percept,
                "legacy_visible_or_cue": matched_legacy_visible,
                "body_bands_present_in_bucket": matched_body_only,
            },
            "developmental_gate_factor": (
                float(gate.get("gate_factor")) if isinstance(gate, dict) else None
            ),
            "developmental_stage": (
                gate.get("developmental_stage") if isinstance(gate, dict) else None
            ),
            "cognitive_depth": (
                float(gate.get("cognitive_depth"))
                if isinstance(gate, dict) and gate.get("cognitive_depth") is not None
                else None
            ),
            "cognitive_depth_status": (
                "VALUE"
                if isinstance(gate, dict) and gate.get("cognitive_depth") is not None
                else ("NOT_APPLICABLE" if gate is None else "MISSING_TELEMETRY")
            ),
            "local_experience_maturity": (
                float(gate.get("local_experience_maturity"))
                if isinstance(gate, dict)
                and gate.get("local_experience_maturity") is not None
                else None
            ),
            "global_developmental_maturity": (
                float(gate.get("developmental_maturity"))
                if isinstance(gate, dict)
                and gate.get("developmental_maturity") is not None
                else None
            ),
            "depth_limitation_reason": (
                gate.get("depth_limitation_reason") if isinstance(gate, dict) else None
            ),
            "developmental": gate,
        }
        return PsycheOutput(
            candidates=tuple(candidates),
            updates=(
                PsycheUpdate("working", "sensorimotor_generation", diagnostics),
                PsycheUpdate("memory", "sensorimotor", store.to_dict()),
            ),
            signals=diagnostics,
        )


class SensorimotorSelectionModule(PsycheModule):
    module_id = "PSY-SENSORIMOTOR-SELECTION-V05"
    version = "0.5.0"
    stage = PsycheStage.ACTION_SELECTION

    def __init__(self, config: SensorimotorConfig | None = None) -> None:
        self.config = config or SensorimotorConfig()

    def process(self, context: PsycheContext) -> PsycheOutput:
        generated = _mapping(context.state.working.get("sensorimotor_generation"))
        proposals = []
        if context.candidates:
            for candidate in context.candidates:
                proposals.append(
                    {
                        "action": candidate.action.kind,
                        "source": candidate.metadata.get("proposal_source", "ENDOGENOUS_VARIATION"),
                        "confidence": float(candidate.metadata.get("predictive_confidence", 0.0)),
                        "support": float(candidate.metadata.get("support_count", 0.0)),
                        "ordinary_action_value": candidate.total_value,
                        "predicted_transition": candidate.metadata.get(
                            "predicted_transition_summary"
                        ),
                    }
                )
        payload = {
            "proposals": proposals,
            "available": generated.get("physically_available_actions", []),
        }
        body = interoception(context.observation)
        if not body:
            body = _numeric(context.state.internal.get("interoceptive_model"))
        chosen = select_proposal(payload, body=body, random_value=context.random_value)
        store = SensorimotorStore.from_dict(context.state.memory.get("sensorimotor"))
        obs = dict(context.observation.data)
        remember_action(store, str(chosen["action"]), obs, cue_mode=self.config.cue_mode, config=self.config)
        return PsycheOutput(
            updates=(
                PsycheUpdate("memory", "sensorimotor", store.to_dict()),
                PsycheUpdate(
                    "working",
                    "last_selection",
                    {
                        "action": chosen["action"],
                        "reason": chosen["reason"],
                        "score": chosen["score"],
                        "candidates": chosen.get("candidates") or [],
                        "tie": bool(chosen.get("tie")),
                        "tie_break": chosen.get("tie_break"),
                        "decision_source": chosen.get("decision_source"),
                    },
                ),
            ),
            selection=PsycheSelection(
                source_module=self.module_id,
                action=Action(str(chosen["action"])),
                reason=str(chosen["reason"]),
                score=float(chosen["score"]),
                metadata={
                    "proposal_source": (chosen.get("selected") or {}).get("source"),
                    "sensorimotor": True,
                },
            ),
            signals={
                "selected_action": chosen["action"],
                "reason": chosen["reason"],
                "score": chosen["score"],
                "selection_candidates": chosen.get("candidates") or [],
                "selection_tie": bool(chosen.get("tie")),
                "selection_tie_break": chosen.get("tie_break"),
                "decision_source": chosen.get("decision_source"),
            },
        )


class SensorimotorLearningModule(PsycheModule):
    module_id = "PSY-SENSORIMOTOR-LEARNING-V05"
    version = "0.5.0"
    stage = PsycheStage.LEARNING

    def __init__(self, config: SensorimotorConfig | None = None) -> None:
        self.config = config or SensorimotorConfig()

    def process(self, context: PsycheContext) -> PsycheOutput:
        store = SensorimotorStore.from_dict(context.state.memory.get("sensorimotor"))
        event = update_store(
            store,
            observation=dict(context.observation.data),
            config=self.config,
        )
        return PsycheOutput(
            updates=(PsycheUpdate("memory", "sensorimotor", store.to_dict()),),
            signals={"sensorimotor_update": event},
        )


def apply_consequence(store: SensorimotorStore, observation: dict[str, Any], config: SensorimotorConfig) -> dict[str, Any] | None:
    return update_store(store, observation=observation, config=config)
