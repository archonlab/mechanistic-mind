from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


PSYCHE_MECHANISM = "PSYCHE-SINGLE-ORGANISM-V03"
BODY_FIELDS = ("energy_reserve", "fatigue", "hydration", "mass", "damage", "age")


def get(data: Any, *path: Any, default: Any = None) -> Any:
    current = data
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return default
        current = current[key]
    return current


def as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, Mapping):
        for key in ("magnitude", "value", "total", "mean", "score", "error"):
            found = numeric(value.get(key))
            if found is not None:
                return found
    return None


def detect_agent(record: Mapping[str, Any]) -> str | None:
    for root in ("action_decisions", "actions", "observations", "signals", "action_sources"):
        value = record.get(root)
        if isinstance(value, Mapping) and value:
            return str(next(iter(value)))
    bodies = get(record, "state_after", "world", "variables", "bodies", default={})
    return str(next(iter(bodies))) if isinstance(bodies, Mapping) and bodies else None


def _action_string(value: Any, depth: int = 0) -> str | None:
    """Normalize legacy strings and the nested action objects used in production."""
    if depth > 4:
        return None
    if isinstance(value, str) and value:
        return value
    if isinstance(value, (list, tuple)):
        for item in reversed(value):
            found = _action_string(item, depth + 1)
            if found:
                return found
        return None
    if not isinstance(value, Mapping):
        return None
    for key in (
        "selected_action", "executed_action", "world_action", "action",
        "selected", "chosen_action", "action_id", "action_name", "serialized", "name", "id",
    ):
        if key in value:
            found = _action_string(value[key], depth + 1)
            if found:
                return found
    verb = value.get("verb") or value.get("action_type") or value.get("type") or value.get("kind")
    parameters = value.get("parameters") if isinstance(value.get("parameters"), Mapping) else {}
    target = (
        value.get("target") or value.get("object_id") or value.get("object")
        or parameters.get("target") or parameters.get("object_id")
        or parameters.get("direction") or value.get("direction")
    )
    if isinstance(verb, str):
        target_string = _action_string(target, depth + 1)
        return f"{verb}:{target_string}" if target_string else verb
    for key in ("selected_proposal", "chosen_proposal", "proposal", "payload", "data", "spec"):
        if key in value:
            found = _action_string(value[key], depth + 1)
            if found:
                return found
    return None


def extract_last_history(record: Mapping[str, Any], agent: str) -> dict[str, Any]:
    history = get(record, "state_after", "world", "variables", "developmental_history", agent, default=[])
    if not isinstance(history, list) or not history:
        return {}
    return as_dict(history[-1])


def extract_world_receipt(record: Mapping[str, Any], agent: str) -> dict[str, Any]:
    history = extract_last_history(record, agent)
    for key in ("world_action_receipt", "objective_context_receipt", "action_receipt"):
        if isinstance(history.get(key), Mapping):
            return dict(history[key])
    direct = get(record, "applied_state_updates", agent, default={})
    return as_dict(direct)


def extract_action(record: Mapping[str, Any], agent: str) -> str | None:
    candidates = (
        get(record, "action_decisions", agent),
        get(record, "actions", agent),
        get(record, "action_sources", agent),
        extract_world_receipt(record, agent),
    )
    for candidate in candidates:
        found = _action_string(candidate)
        if found:
            return found
    return None


def extract_decision(record: Mapping[str, Any], agent: str) -> dict[str, Any]:
    decision = as_dict(get(record, "action_decisions", agent, default={}))
    metadata = as_dict(decision.get("proposal_metadata") or decision.get("metadata"))
    proposal = as_dict(decision.get("selected_proposal") or decision.get("proposal"))
    proposal_meta = as_dict(proposal.get("metadata") or proposal.get("proposal_metadata"))
    reason = (
        proposal_meta.get("selection_reason") or metadata.get("selection_reason")
        or decision.get("selection_reason") or decision.get("reason")
    )
    score = proposal_meta.get("selection_score", metadata.get("selection_score", decision.get("selection_score")))
    return {"reason": reason, "score": score}


def extract_observation(record: Mapping[str, Any], agent: str) -> dict[str, Any]:
    observation = get(record, "observations", agent, "data", default=None)
    if not isinstance(observation, Mapping):
        observation = get(record, "observations", agent, default={})
    observation = as_dict(observation)
    visible_objects: list[str] = []
    for item in as_list(observation.get("visible_objects")):
        if isinstance(item, str):
            visible_objects.append(item)
        elif isinstance(item, Mapping):
            object_id = item.get("id") or item.get("object_id") or item.get("name")
            if object_id is not None:
                visible_objects.append(str(object_id))
    return {
        "position": observation.get("position"),
        "context": observation.get("context"),
        "interoception": observation.get("interoception"),
        "available_actions": observation.get("available_actions"),
        "visible_objects": visible_objects,
        "vision_horizon": observation.get("vision_horizon"),
    }


def extract_whole_psyche(record: Mapping[str, Any], agent: str) -> dict[str, Any]:
    signals = get(record, "signals", agent, default={})
    if isinstance(signals, Mapping):
        ordered = [signals.get(PSYCHE_MECHANISM), *signals.values()]
        for value in ordered:
            if isinstance(value, Mapping):
                whole = value.get("whole_psyche") or value.get("psyche")
                if isinstance(whole, Mapping):
                    return dict(whole)
    states = get(record, "state_after", "agents", agent, "mechanism_states", default={})
    if isinstance(states, Mapping):
        ordered = [states.get(PSYCHE_MECHANISM), *states.values()]
        for value in ordered:
            if isinstance(value, Mapping):
                psyche = value.get("psyche") or value.get("whole_psyche")
                if isinstance(psyche, Mapping):
                    return dict(psyche)
    return {}


def extract_bounded_signals(record: Mapping[str, Any], agent: str) -> dict[str, Any]:
    signals = get(record, "signals", agent, default={})
    if not isinstance(signals, Mapping):
        return {}
    for value in signals.values():
        if isinstance(value, Mapping) and isinstance(value.get("memory_summary"), Mapping):
            return dict(value)
    return {}


def extract_body_truth(record: Mapping[str, Any], agent: str) -> dict[str, Any]:
    body = get(record, "state_after", "world", "variables", "bodies", agent, default={})
    if not isinstance(body, Mapping):
        return {}
    return {
        str(key): value for key, value in body.items()
        if key in BODY_FIELDS or "risk" in str(key).lower()
    }


def extract_experienced_effects(record: Mapping[str, Any], agent: str) -> dict[str, Any]:
    for root in (record.get("state_after"), record):
        effects = get(root, "world", "variables", "last_experience", agent, "experienced_effects", default=None)
        if isinstance(effects, Mapping):
            return dict(effects)
    return {}


def selected_from_action_map(mapping: Any, action: str | None) -> Any:
    if not isinstance(mapping, Mapping):
        return None
    if action and action in mapping:
        return mapping[action]
    for key in ("last_selected", "selected", "current"):
        if key in mapping:
            return mapping[key]
    return None


def extract_prediction_error(psyche: Mapping[str, Any]) -> tuple[Any, str | None]:
    errors = psyche.get("prediction_errors")
    if not isinstance(errors, Mapping):
        return errors, None
    error_action = _action_string(errors.get("action") or errors.get("selected_action"))
    for key in ("magnitude", "last", "current", "value", "error"):
        if key in errors:
            entry = errors[key]
            if isinstance(entry, Mapping):
                error_action = error_action or _action_string(entry.get("action"))
            return entry, error_action
    best: tuple[float, str, Any] | None = None
    for key, entry in errors.items():
        number = numeric(entry)
        if number is not None and (best is None or abs(number) > abs(best[0])):
            best = (number, str(key), entry)
    return (best[2], best[1]) if best else (errors, error_action)


def object_from_action(action: str | None, receipt: Mapping[str, Any] | None = None) -> str | None:
    if action and ":" in action:
        verb, target = action.split(":", 1)
        if verb.upper() in {"USE", "PUSH", "PULL", "TAKE", "DROP", "INTERACT", "INSPECT"}:
            return target
    if isinstance(receipt, Mapping):
        for key in ("object_id", "target_id", "target", "object"):
            value = receipt.get(key)
            found = _action_string(value)
            if found:
                return found
    return None


def extract_compact_tick(record: Mapping[str, Any], source_line: int) -> dict[str, Any] | None:
    tick = record.get("tick")
    if not isinstance(tick, int):
        return None
    agent = detect_agent(record)
    if agent is None:
        return None
    receipt = extract_world_receipt(record, agent)
    action = extract_action(record, agent)
    decision = extract_decision(record, agent)
    observation = extract_observation(record, agent)
    psyche = extract_whole_psyche(record, agent)
    bounded = extract_bounded_signals(record, agent)
    memory_summary = as_dict(bounded.get("memory_summary"))
    perceptual = as_dict(memory_summary.get("perceptual_dynamics"))
    retrieval = as_dict(bounded.get("retrieval"))
    error, error_action = extract_prediction_error(psyche)
    action = action or error_action
    predictions = psyche.get("predictions", {})
    uncertainty = psyche.get("uncertainty", {})
    values = psyche.get("values", {})
    return {
        "tick": tick,
        "agent": agent,
        "position": observation["position"],
        "action": action,
        "object_id": object_from_action(action, receipt),
        "selection_reason": decision["reason"],
        "selection_score": decision["score"],
        "context": observation["context"],
        "interoception": observation["interoception"],
        "available_actions": observation["available_actions"],
        "visible_objects": observation["visible_objects"],
        "body_truth": extract_body_truth(record, agent),
        "need_pressure": get(psyche, "internal", "need_pressure", default={}),
        "global_state": psyche.get("global_state", {}),
        "attention": psyche.get("attention"),
        "selected_prediction": selected_from_action_map(predictions, action),
        "selected_uncertainty": selected_from_action_map(uncertainty, action),
        "selected_value": selected_from_action_map(values, action),
        "prediction_error": error,
        "prediction_error_action": error_action or action,
        "habits": psyche.get("habits", {}),
        "learning_models": psyche.get("learning", {}),
        "self_model": psyche.get("self_model", {}),
        "experienced_effects": extract_experienced_effects(record, agent),
        "perceptual_mismatch": perceptual.get("mismatch"),
        "perceptual_activation": perceptual.get("perceptual_activation"),
        "perceptual_unknown": perceptual.get("unknown"),
        "retrieval_confidence": retrieval.get("selected_prediction_confidence"),
        "retrieval_stage": retrieval.get("terminal_stage"),
        "inspected_candidates": retrieval.get("total_candidates_inspected"),
        "memory_counts": {
            "episodes": memory_summary.get("episodic_count"),
            "patterns": memory_summary.get("pattern_count"),
            "novel_fragments": memory_summary.get("novel_fragment_count"),
        },
        "world_receipt": receipt,
        "provenance": {"source_line": source_line, "source_tick": tick},
    }


@dataclass(frozen=True)
class StreamRecord:
    line_number: int
    data: dict[str, Any]


def iter_jsonl_records(handle: Iterable[str]) -> Iterable[StreamRecord]:
    import json
    for line_number, line in enumerate(handle, start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            yield StreamRecord(line_number, value)
