from __future__ import annotations

from typing import Any, Mapping


def _event_sentence(event: Mapping[str, Any]) -> str:
    tick, kind, evidence = event.get("tick"), event.get("type"), event.get("evidence", {})
    if kind == "MAJOR_PREDICTION_ERROR":
        return f"At tick {tick}, the run's largest absolute prediction error was {evidence.get('prediction_error')}, associated with {evidence.get('action') or 'an unrecorded action'}."
    if kind == "MODEL_REVISION":
        return f"At tick {tick}, the prediction for {evidence.get('action')} changed from {evidence.get('previous_prediction')} to {evidence.get('current_prediction')} after error at tick {evidence.get('error_tick')}."
    if kind == "HABIT_EMERGED":
        return f"By tick {tick}, {evidence.get('habit')} crossed the recorded habit threshold at strength {evidence.get('strength')}."
    if kind in {"PREFERENCE_ACQUIRED", "PREFERENCE_LOST"}:
        verb = "became positive" if kind == "PREFERENCE_ACQUIRED" else "became negative"
        return f"At tick {tick}, the recorded value of {evidence.get('action')} {verb}, changing from {evidence.get('previous_value')} to {evidence.get('current_value')}."
    if kind == "PHYSIOLOGICAL_TRANSITION":
        return f"At tick {tick}, {evidence.get('variable')} moved from {evidence.get('previous')} to {evidence.get('current')} (value {evidence.get('value')})."
    return f"At tick {tick}, telemetry recorded {kind.lower().replace('_', ' ')}."


def build_biography(summary: Mapping[str, Any], events: list[Mapping[str, Any]], epochs: list[Mapping[str, Any]]) -> dict[str, Any]:
    dynamics = summary.get("dynamics", {})
    agent_ids = (summary.get("metadata") or {}).get("agent_ids") or []
    agent = str(agent_ids[0]) if agent_ids else (str(events[0].get("agent")) if events else "the agent")
    paragraphs: list[dict[str, Any]] = []
    first_tick, last_tick = dynamics.get("first_tick"), dynamics.get("last_tick")
    paragraphs.append({
        "text": f"{agent}'s recorded life spans ticks {first_tick}–{last_tick}. The analyzer processed {dynamics.get('ticks_analyzed', 0)} tick records and found {len(epochs)} evidence-defined behavioral epoch(s).",
        "claims": ["recorded_span", "ticks_analyzed", "epoch_count"],
        "evidence_ticks": [value for value in (first_tick, last_tick) if value is not None],
        "source_lines": [],
    })
    for epoch in epochs:
        action = epoch.get("dominant_action") or "no consistently recorded action"
        error = epoch.get("mean_absolute_prediction_error")
        error_text = f" Mean absolute prediction error was {error:.3f}." if isinstance(error, (int, float)) else ""
        evidence = epoch.get("evidence", {})
        paragraphs.append({
            "text": f"From tick {epoch.get('start_tick')} to {epoch.get('end_tick')}, behavior formed a {epoch.get('label')} epoch. The dominant action was {action}; {epoch.get('visited_position_count', 0)} position-window observations were distinct.{error_text}",
            "claims": ["epoch_boundary", "epoch_label", "dominant_action", "prediction_error"],
            "evidence_ticks": list(evidence.get("ticks", [])),
            "source_lines": [line for line in evidence.get("source_lines", []) if line is not None],
            "epoch_id": epoch.get("epoch_id"),
        })
    notable_types = {"MAJOR_PREDICTION_ERROR", "MODEL_REVISION", "HABIT_EMERGED", "PREFERENCE_ACQUIRED", "PREFERENCE_LOST", "PHYSIOLOGICAL_TRANSITION"}
    for event in events:
        if event.get("type") not in notable_types:
            continue
        provenance = event.get("provenance") or {}
        paragraphs.append({
            "text": _event_sentence(event),
            "claims": [str(event.get("type"))],
            "evidence_ticks": [event.get("tick")],
            "source_lines": [provenance["source_line"]] if provenance.get("source_line") is not None else [],
            "event_type": event.get("type"),
        })
    return {
        "schema": "mechanistic-mind/psychology-biography-v0.2",
        "agent": agent,
        "title": f"Evidence-backed biography of {agent}",
        "paragraphs": paragraphs,
        "interpretation_boundary": summary.get("interpretation_boundary"),
    }
