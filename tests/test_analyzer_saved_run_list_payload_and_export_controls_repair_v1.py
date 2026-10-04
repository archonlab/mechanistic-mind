"""ANALYZER_SAVED_RUN_LIST_PAYLOAD_AND_EXPORT_CONTROLS_REPAIR_V1 — focused tests."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path


def test_reproduce_list_get_failure_on_derived_changes():
    """Pre-fix behavior: list-valued derived_changes must not crash after repair."""
    from mechanistic_mind.scientific_v3.analyzer_next.tick_stories import TickStory
    from mechanistic_mind.scientific_v3.analyzer_next.volumetric_physical_causal_reconstruction import (
        _body_xyz_from_story,
        classify_story_physical,
    )

    story = TickStory(
        run_id="t",
        tick=3,
        cognitive_agent_id="agent-0",
        physical_body_id="body-0",
        observation_id="o",
        decision_id="d",
        motor_id="m",
        consequence_id="c",
    )
    story.derived_changes = [
        {"kind": "POSE_STATE", "x": 1.0, "y": 2.0, "z": 0.5, "centre_z": 0.6},
        {"kind": "RESOURCE_STATE", "B_sum": 1.0},
    ]
    # Must not raise AttributeError
    xyz = _body_xyz_from_story(story)
    assert xyz["status"] in ("YES", "PARTIAL")
    assert xyz["body_base_xyz"][0] == 1.0

    ps = classify_story_physical(
        story,
        reach_traces=[],
        etc_contacts=[],
        work_rows=[],
        wmt_rows=[],
        model={"volumetric_physical_story": "APPLICABLE", "is_acanthostega_beta4": True},
    )
    assert ps.get("negative_cause") is not None


def test_normalize_list_dict_empty_jsonl_malformed(tmp_path: Path):
    from mechanistic_mind.scientific_v3.analyzer_next.evidence_payload_normalize import (
        load_and_normalize_json_file,
        normalize_evidence_payload,
    )

    assert normalize_evidence_payload([{"a": 1}, {"b": 2}])["record_count"] == 2
    assert normalize_evidence_payload({"schema": "X", "x": 1})["source_kind"] == "SINGLE_RECORD"
    assert normalize_evidence_payload({"records": [{"a": 1}]})["source_kind"] == "ENVELOPE_DICT"
    empty = normalize_evidence_payload([])
    assert empty["source_kind"] == "EMPTY_LIST"
    assert empty["record_count"] == 0
    null = normalize_evidence_payload(None)
    assert null["source_kind"] == "NULL"
    bad = normalize_evidence_payload([{"ok": 1}, "nope"])
    assert bad["record_count"] == 1
    assert any("not_dict" in e for e in bad["errors"])

    p = tmp_path / "x.jsonl"
    p.write_text('{"tick":1}\n{"tick":2}\n', encoding="utf-8")
    loaded = load_and_normalize_json_file(p)
    assert loaded["source_kind"] == "JSONL_STREAM"
    assert loaded["record_count"] == 2
    assert [r["tick"] for r in loaded["records"]] == [1, 2]


def test_normalize_derived_changes_shapes():
    from mechanistic_mind.scientific_v3.analyzer_next.volumetric_physical_causal_reconstruction import (
        _normalize_derived_changes,
        _pose_record_from_derived,
    )

    lst, w = _normalize_derived_changes([{"kind": "POSE_STATE", "x": 1}])
    assert len(lst) == 1
    assert _pose_record_from_derived(lst)["x"] == 1
    dct, w2 = _normalize_derived_changes({"kind": "POSE_STATE", "z": 0.2})
    assert len(dct) == 1
    empty, _ = _normalize_derived_changes(None)
    assert empty == []
    bad, warn = _normalize_derived_changes(42)
    assert bad == []
    assert warn


def test_failed_job_exposes_error_code(tmp_path: Path, monkeypatch):
    from mechanistic_mind.scientific_v3.analyzer_next import job as job_mod
    import mechanistic_mind.scientific_v3.analyzer_next.pipeline as pipe

    def boom(*_a, **_k):
        raise AttributeError("'list' object has no attribute 'get'")

    monkeypatch.setattr(pipe, "build_behavioral_reconstruction", boom)
    out = tmp_path / "out"
    out.mkdir()
    run = tmp_path / "run"
    run.mkdir()
    (run / "run.json").write_text("{}", encoding="utf-8")
    state = job_mod.run_job(run_dir=run, out_dir=out)
    assert state["status"] == "FAILED"
    assert state["error_code"] == "AttributeError"
    assert state["failed_phase"]
    assert state["status"] != "RUNNING"


def test_saved_run_volumetric_on_fixture_with_pose_list():
    """Mini reconstruction: list derived_changes must classify without crash."""
    from mechanistic_mind.scientific_v3.analyzer_next.tick_stories import TickStory
    from mechanistic_mind.scientific_v3.analyzer_next.volumetric_physical_causal_reconstruction import (
        build_volumetric_physical_causal_reconstruction,
    )

    stories = []
    for t in range(3):
        s = TickStory(
            run_id="fix",
            tick=t,
            cognitive_agent_id="a0",
            physical_body_id="b0",
            observation_id=f"o{t}",
            decision_id=f"d{t}",
            motor_id=f"m{t}",
            consequence_id=f"c{t}",
        )
        s.derived_changes = [{"kind": "POSE_STATE", "x": float(t), "y": 0.0, "z": 0.4}]
        stories.append(s)
    # run_dir may be missing receipts — still must not crash on derived_changes
    out = build_volumetric_physical_causal_reconstruction(stories, run_dir="/tmp/nonexistent-mm-run")
    assert out["physical_stories_count"] == 3
    assert out["status"] in ("AVAILABLE", "NOT_APPLICABLE")
