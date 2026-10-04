"""ANALYZER_RELATIVE_Z_TAXONOMY_AND_PROGRESS_REPORTING_REPAIR_V1 — focused tests."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.scientific_v3.analyzer_next.tick_stories import TickStory
from mechanistic_mind.scientific_v3.analyzer_next.volumetric_physical_causal_reconstruction import (
    classify_story_physical,
    build_volumetric_physical_causal_reconstruction,
    format_volumetric_physical_causal_section,
)
from mechanistic_mind.scientific_v3.analyzer_next import job as analyzer_job


def _story(tick=1, agent="agent_0", body="body-0", motor=None, **kw):
    return TickStory(
        run_id="t",
        tick=tick,
        cognitive_agent_id=agent,
        physical_body_id=body,
        observation_id="o",
        decision_id="d",
        motor_id="m",
        consequence_id="c",
        observation={},
        decision={},
        motor=motor or {"components": {"locomotion": "WAIT"}},
        consequence={},
        **kw,
    )


BETA4 = {
    "public_preset": "ACANTHOSTEGA_BETA4",
    "model_line": "ACANTHOSTEGA",
    "is_acanthostega_beta4": True,
    "world_dimensionality": "VOLUMETRIC_XYZ",
    "described_as_2d": False,
    "volumetric_physical_story": "APPLICABLE",
}


def test_zero_z_fields_available_not_selected():
    story = _story(
        motor={
            "motor_schema": "COMPOSITE_MOTOR_V1",
            "components": {"locomotion": "WAIT", "effector_z_left": 0, "effector_z_right": 0},
        }
    )
    ps = classify_story_physical(
        story, reach_traces=[], etc_contacts=[], work_rows=[], wmt_rows=[], model=BETA4
    )
    assert ps["control_availability"] == "AVAILABLE"
    assert ps["negative_cause"] == "NOT_SELECTED"
    assert ps["control_repertoire"]["left_z_request"] == 0
    assert ps["control_repertoire"]["right_z_request"] == 0


def test_nonzero_left_without_ebae_selected_partial():
    story = _story(
        motor={"components": {"locomotion": "WAIT", "effector_z_left": 1, "effector_z_right": 0}}
    )
    ps = classify_story_physical(
        story, reach_traces=[], etc_contacts=[], work_rows=[], wmt_rows=[], model=BETA4
    )
    assert ps["control_repertoire"]["z_request_nonzero"] is True
    assert ps["negative_cause"] == "SELECTED_NOT_ACTUATED"
    assert "EBAE_EVENT_REF_ABSENT" in ps["control_repertoire"]["missing_evidence"]


def test_right_z_plus_aligned_displacement_no_contact():
    story = _story(
        tick=2,
        motor={"components": {"locomotion": "WAIT", "effector_z_left": 0, "effector_z_right": -1}},
    )
    traces = [
        {
            "tick": 2,
            "body_id": "body-0",
            "effector_id": "RIGHT",
            "relative_z": -0.1075,
            "geometric_reach": False,
            "physical_relative_z_dof": "AVAILABLE",
            "agent_selectable_motor_factor": "PRESENT",
        }
    ]
    pose = {("0", "body-0", "RIGHT"): [(1, 0.0), (2, -0.1075)]}
    ps = classify_story_physical(
        story,
        reach_traces=traces,
        etc_contacts=[],
        work_rows=[],
        wmt_rows=[],
        model=BETA4,
        pose_by_key=pose,
        runtime_generation="0",
    )
    assert ps["negative_cause"] == "ACTUATED_NO_GEOMETRIC_REACH"
    assert ps["control_repertoire"]["pose_relative_z_used_as_actuation"] is False


def test_persistent_nonzero_pose_zero_request_not_selected():
    story = _story(
        motor={"components": {"locomotion": "WAIT", "effector_z_left": 0, "effector_z_right": 0}}
    )
    traces = [
        {
            "tick": 1,
            "body_id": "body-0",
            "effector_id": "LEFT",
            "relative_z": 0.1075,
            "geometric_reach": False,
            "physical_relative_z_dof": "AVAILABLE",
            "agent_selectable_motor_factor": "PRESENT",
        }
    ]
    ps = classify_story_physical(
        story, reach_traces=traces, etc_contacts=[], work_rows=[], wmt_rows=[], model=BETA4
    )
    assert ps["negative_cause"] == "NOT_SELECTED"
    assert ps["negative_cause"] != "ACTUATED_NO_GEOMETRIC_REACH"


def test_accepted_ebae_zero_displacement():
    story = _story(
        motor={"components": {"locomotion": "WAIT", "effector_z_left": 1, "effector_z_right": 0}}
    )
    ebae = [
        {
            "kind": "effector_bounded_actuator_effort",
            "tick": 1,
            "body_id": "body-0",
            "effector_id": "LEFT",
            "status": "FULLY_BLOCKED",
            "achieved_relative_delta": 0.0,
            "work_used": 0.0,
        }
    ]
    ps = classify_story_physical(
        story,
        reach_traces=[],
        etc_contacts=[],
        work_rows=[],
        wmt_rows=[],
        model=BETA4,
        ebae_rows=ebae,
    )
    assert ps["negative_cause"] == "ACTUATED_NO_DISPLACEMENT"


def test_contact_insufficient_work():
    story = _story(
        motor={"components": {"locomotion": "WAIT", "effector_z_left": -1, "effector_z_right": 0}}
    )
    ps = classify_story_physical(
        story,
        reach_traces=[{"tick": 1, "body_id": "body-0", "relative_z": 0.0, "geometric_reach": True,
                       "physical_relative_z_dof": "AVAILABLE", "agent_selectable_motor_factor": "PRESENT"}],
        etc_contacts=[{"tick": 1, "body_id": "body-0", "contact_fact": True}],
        work_rows=[{"tick": 1, "work_used": 0.001}],
        wmt_rows=[],
        model=BETA4,
    )
    assert ps["negative_cause"] == "CONTACT_INSUFFICIENT_WORK"


def test_material_failure_and_detached():
    story = _story(motor={"components": {"effector_z_left": 0, "effector_z_right": 0}})
    ps_f = classify_story_physical(
        story, reach_traces=[], etc_contacts=[], work_rows=[],
        wmt_rows=[{"tick": 1, "material_failure": True}], model=BETA4,
    )
    assert ps_f["negative_cause"] == "MATERIAL_FAILURE"
    ps_d = classify_story_physical(
        story, reach_traces=[], etc_contacts=[], work_rows=[],
        wmt_rows=[{"tick": 1, "detached_object_id": "obj-1"}], model=BETA4,
    )
    assert ps_d["negative_cause"] == "DETACHED_MATERIAL_CREATED"


def test_legacy_missing_fields_not_established():
    story = _story(motor={"components": {"locomotion": "WAIT"}})  # no Z fields
    ps = classify_story_physical(
        story, reach_traces=[], etc_contacts=[], work_rows=[], wmt_rows=[],
        model={**BETA4, "is_acanthostega_beta4": False},
    )
    assert ps["control_availability"] == "NOT_ESTABLISHED"
    assert ps["negative_cause"] == "CONTROL_AVAILABILITY_NOT_ESTABLISHED"


def test_explicit_absence_control_not_available():
    story = _story(motor={"components": {"locomotion": "WAIT"}})
    ps = classify_story_physical(
        story,
        reach_traces=[{
            "tick": 1, "body_id": "body-0", "relative_z": 0.0, "geometric_reach": False,
            "physical_relative_z_dof": "AVAILABLE", "agent_selectable_motor_factor": "ABSENT",
        }],
        etc_contacts=[], work_rows=[], wmt_rows=[], model=BETA4,
    )
    assert ps["control_availability"] == "UNAVAILABLE"
    assert ps["negative_cause"] == "CONTROL_NOT_AVAILABLE"


def test_generation_boundary_blocks_false_pose_delta():
    story = _story(
        tick=5,
        motor={"components": {"effector_z_left": 1, "effector_z_right": 0}},
    )
    traces = [{
        "tick": 5, "body_id": "body-0", "effector_id": "LEFT", "relative_z": 0.2,
        "geometric_reach": False, "physical_relative_z_dof": "AVAILABLE",
        "agent_selectable_motor_factor": "PRESENT",
    }]
    # Prior pose only under a different generation key
    pose = {("1", "body-0", "LEFT"): [(4, 0.0), (5, 0.2)]}
    ps = classify_story_physical(
        story, reach_traces=traces, etc_contacts=[], work_rows=[], wmt_rows=[],
        model=BETA4, pose_by_key=pose, runtime_generation="0",
    )
    # No prior in gen 0 → no aligned displacement → SELECTED_NOT_ACTUATED
    assert ps["negative_cause"] == "SELECTED_NOT_ACTUATED"


def test_agents_isolated():
    s0 = _story(agent="agent_0", body="body-0",
                motor={"components": {"effector_z_left": 1, "effector_z_right": 0}})
    s1 = _story(agent="agent_1", body="body-1",
                motor={"components": {"effector_z_left": 0, "effector_z_right": 0}})
    ebae = [{"tick": 1, "body_id": "body-0", "status": "FREE_SPACE", "achieved_relative_delta": 0.1}]
    p0 = classify_story_physical(s0, reach_traces=[], etc_contacts=[], work_rows=[], wmt_rows=[],
                                 model=BETA4, ebae_rows=ebae)
    p1 = classify_story_physical(s1, reach_traces=[], etc_contacts=[], work_rows=[], wmt_rows=[],
                                 model=BETA4, ebae_rows=ebae)
    assert p0["negative_cause"] == "ACTUATED_NO_GEOMETRIC_REACH"
    assert p1["negative_cause"] == "NOT_SELECTED"


def test_dynamic_footer_not_hardcoded_no(tmp_path: Path):
    (tmp_path / "scientific_meta.json").write_text(json.dumps({
        "public_preset": "ACANTHOSTEGA_BETA4", "model_line": "ACANTHOSTEGA", "generation": 5,
    }))
    # Minimal consequences empty; stories with Z schema
    stories = [
        _story(motor={"components": {"effector_z_left": 0, "effector_z_right": 0}}),
        _story(tick=2, motor={"components": {"effector_z_left": 1, "effector_z_right": 0}}),
    ]
    payload = build_volumetric_physical_causal_reconstruction(stories, run_dir=tmp_path)
    assert payload["relative_z"]["agent_selectable"] == "YES"
    assert payload["relative_z"]["control_availability"] == "AVAILABLE"
    assert payload["relative_z"]["pose_relative_z_used_as_actuation"] is False
    text = format_volumetric_physical_causal_section(payload)
    assert "agent-selectable NO → REQUIRED_CONTROL_NOT_IN_REPERTOIRE" not in text
    assert "control_availability=AVAILABLE" in text


def test_progress_contract_phases_and_monotonic(tmp_path: Path):
    # Empty run dir → job should FAIL or COMPLETE with insufficient; exercise progress writer
    out = tmp_path / "out"
    out.mkdir()
    # Create minimal empty evidence so pipeline can run without crashing hard
    for name in (
        "scientific_spine.jsonl", "scientific_decisions.jsonl", "scientific_motors.jsonl",
        "scientific_observations.jsonl", "scientific_consequences.jsonl",
        "scientific_timeline.jsonl", "scientific_events.jsonl",
    ):
        (tmp_path / name).write_text("")
    (tmp_path / "scientific_meta.json").write_text(json.dumps({
        "public_preset": "ACANTHOSTEGA_BETA4", "model_line": "ACANTHOSTEGA", "generation": 1,
    }))
    percents = []

    # Monkeypatch write_progress capture via wrapping
    orig = analyzer_job.write_progress

    def wrap(path, payload):
        if payload.get("percent") is not None:
            percents.append(float(payload["percent"]))
        return orig(path, payload)

    analyzer_job.write_progress = wrap  # type: ignore
    try:
        st = analyzer_job.run_job(run_dir=tmp_path, out_dir=out, max_tick=0)
    finally:
        analyzer_job.write_progress = orig  # type: ignore
    assert st["status"] in ("COMPLETE", "FAILED")
    assert st["phase"] in ("COMPLETE", "FAILED")
    assert st.get("terminal") is True
    # Monotonic when present
    for a, b in zip(percents, percents[1:]):
        assert b + 1e-9 >= a


def test_ebae_capture_round_trip_not_cognition():
    from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.composite_motor import CompositeMotorOutput

    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=3, config=cfg)
    rt.step_forced_motor(CompositeMotorOutput(effector_z_left=-1, effector_z_right=0))
    act = getattr(rt, "last_agent_effector_z_actuation", None)
    assert isinstance(act, dict)
    assert act.get("status") in ("APPLIED", "NONE", "CAPABILITY_OFF") or act.get("left") is not None
    # Receipts are researcher-only; cognition_exposed must stay false on EBAE receipts.
    left = act.get("left")
    if isinstance(left, dict):
        assert left.get("cognition_exposed") is False
        assert left.get("researcher_only") is True
