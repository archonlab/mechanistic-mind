from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.research.psychology_analyzer import PsychologyAnalyzer


def make_tick(tick: int, action: str = "USE:OBJ-29", *, error: float = 0.1, habit: float = 0.0, nested_action: bool = False) -> dict:
    decision_action = (
        {"type": action.split(":", 1)[0], "target": {"id": action.split(":", 1)[1]}}
        if nested_action and ":" in action else action
    )
    return {
        "tick": tick,
        "action_decisions": {"A001": {
            "selected_proposal": {"action": decision_action, "metadata": {"selection_reason": "TOP_RANKED_PROPOSAL"}},
        }},
        "observations": {"A001": {"data": {"position": [tick, tick % 2], "visible_objects": [{"id": "OBJ-29"}]}}},
        "signals": {"A001": {"PSYCHE-SINGLE-ORGANISM-V03": {"whole_psyche": {
            "predictions": {action: {"mean": 0.1 if tick < 3 else 0.7}},
            "uncertainty": {action: 0.9 if tick == 1 else 0.2},
            "values": {action: {"total": -0.2 if tick == 1 else 0.3}},
            "prediction_errors": {"magnitude": error, "action": decision_action},
            "habits": {action: {"strength": habit}},
            "learning": {"action_models": {action: {"contexts": {"BODY": {"mean": tick}}}}},
        }}}},
        "state_after": {"world": {"variables": {
            "bodies": {"A001": {"energy_reserve": 0.9 - tick * 0.1, "fatigue": tick * 0.1, "hydration": 0.8}},
            "last_experience": {"A001": {"experienced_effects": {"energy": -0.1}}},
            "developmental_history": {"A001": [{"world_action_receipt": {"action": decision_action, "success": True}}]},
        }}},
    }


def write_records(path: Path, records: list[object]) -> None:
    path.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_legacy_streaming_outputs_and_no_default_timeline(tmp_path: Path) -> None:
    source = tmp_path / "psychology_observer.jsonl"
    write_records(source, [
        {"type": "run_metadata", "run_id": "LEGACY", "agent_ids": ["A001"]},
        make_tick(1, error=0.8), make_tick(2, habit=0.8), make_tick(3),
    ])
    result = PsychologyAnalyzer(epoch_window=2).analyze(source)
    assert result.timeline is None
    assert not (result.output_dir / "timeline.jsonl").exists()
    assert all(path.exists() for path in (result.summary, result.meaningful_events, result.epochs, result.biography, result.report))
    summary = load(result.summary)
    assert summary["schema"].endswith("v0.2")
    assert summary["dynamics"]["ticks_analyzed"] == 3
    assert summary["dynamics"]["action_counts"]["USE:OBJ-29"] == 3
    assert summary["dynamics"]["object_interaction_counts"]["OBJ-29"] == 3


def test_production_envelope_extracts_nested_action_and_error_action(tmp_path: Path) -> None:
    source = tmp_path / "psychology_observer.jsonl"
    write_records(source, [
        {"record_type": "run_metadata", "payload": {"run_id": "PROD", "agent_ids": ["A001"]}},
        {"record_type": "tick", "payload": make_tick(1, "PUSH:OBJ-110", error=0.8325, nested_action=True)},
    ])
    result = PsychologyAnalyzer().analyze(source)
    summary = load(result.summary)
    assert summary["metadata"]["run_id"] == "PROD"
    assert summary["dynamics"]["action_counts"] == {"PUSH:OBJ-110": 1}
    assert summary["dynamics"]["object_interaction_counts"] == {"OBJ-110": 1}
    assert summary["dynamics"]["largest_prediction_error"]["action"] == "PUSH:OBJ-110"
    major = [event for event in load(result.meaningful_events) if event["type"] == "MAJOR_PREDICTION_ERROR"]
    assert major[0]["evidence"]["action"] == "PUSH:OBJ-110"


def test_production_action_type_parameters_shape(tmp_path: Path) -> None:
    tick = make_tick(1)
    action_object = {"action_type": "USE", "parameters": {"object_id": "OBJ-77"}}
    tick["action_decisions"]["A001"] = {"selected": {"chosen_proposal": {"action": action_object}}}
    psyche = tick["signals"]["A001"]["PSYCHE-SINGLE-ORGANISM-V03"]["whole_psyche"]
    psyche["prediction_errors"]["action"] = action_object
    source = tmp_path / "psychology_observer.jsonl"
    write_records(source, [{"record_type": "tick", "payload": tick}])
    summary = load(PsychologyAnalyzer().analyze(source).summary)
    assert summary["dynamics"]["action_counts"] == {"USE:OBJ-77": 1}
    assert summary["dynamics"]["object_interaction_counts"] == {"OBJ-77": 1}


def test_learning_is_direct_not_recursive_event_spam(tmp_path: Path) -> None:
    source = tmp_path / "psychology_observer.jsonl"
    write_records(source, [make_tick(1), make_tick(2), make_tick(3)])
    events = load(PsychologyAnalyzer().analyze(source).meaningful_events)
    learned = [event for event in events if event["type"] == "LEARNED_ACTION_EFFECT"]
    assert len(learned) == 1
    assert learned[0]["evidence"]["association"] == "USE:OBJ-29"
    assert not any("contexts" in json.dumps(event) for event in learned)


def test_behavioral_epochs_use_multi_signal_change(tmp_path: Path) -> None:
    source = tmp_path / "psychology_observer.jsonl"
    records = [make_tick(1, "MOVE:N"), make_tick(2, "MOVE:S"), make_tick(3, "PUSH:OBJ-9"), make_tick(4, "PUSH:OBJ-9")]
    write_records(source, records)
    result = PsychologyAnalyzer(epoch_window=2, epoch_change_threshold=0.2).analyze(source)
    epochs = load(result.epochs)
    assert len(epochs) == 2
    assert epochs[0]["dominant_action"].startswith("MOVE")
    assert epochs[1]["dominant_action"] == "PUSH:OBJ-9"
    assert all(epoch["evidence"]["source_lines"] for epoch in epochs)


def test_biography_claims_have_evidence_and_report_sections(tmp_path: Path) -> None:
    source = tmp_path / "psychology_observer.jsonl"
    write_records(source, [make_tick(1, error=0.8), make_tick(2)])
    result = PsychologyAnalyzer(epoch_window=1).analyze(source)
    biography = load(result.biography)
    assert biography["paragraphs"]
    assert all("evidence_ticks" in paragraph and "source_lines" in paragraph for paragraph in biography["paragraphs"])
    report = result.report.read_text(encoding="utf-8")
    assert "Evidence-backed biography" in report
    assert "Behavioral epochs" in report
    assert "Meaningful events" in report


def test_keep_timeline_and_invalid_json(tmp_path: Path) -> None:
    source = tmp_path / "psychology_observer.jsonl"
    source.write_text('{"broken":\n' + json.dumps(make_tick(1)) + "\n", encoding="utf-8")
    result = PsychologyAnalyzer().analyze(source, keep_timeline=True)
    assert result.timeline is not None and result.timeline.exists()
    assert len(result.timeline.read_text(encoding="utf-8").splitlines()) == 1
    assert load(result.summary)["invalid_json_lines"] == 1
