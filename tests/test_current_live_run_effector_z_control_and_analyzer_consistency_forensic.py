"""Audit assertions for effector-Z vs Analyzer consistency (no live mutation).

Uses synthetic fixtures mirroring the live forensic findings so CI does not
depend on the user's live capture directory.
"""

from __future__ import annotations

from mechanistic_mind.scientific_v3.analyzer_next.volumetric_physical_causal_reconstruction import (
    build_volumetric_physical_causal_reconstruction,
    classify_story_physical,
    format_volumetric_physical_causal_section,
)


class _Story:
    def __init__(self, tick=1, agent="agent_0", body="body-0", motor=None):
        self.tick = tick
        self.cognitive_agent_id = agent
        self.physical_body_id = body
        self.agent_id = agent
        self.body_id = body
        self.observation_id = f"o:{tick}"
        self.decision_id = f"d:{tick}"
        self.motor_id = f"m:{tick}"
        self.consequence_id = f"c:{tick}"
        self.motor = motor or {
            "components": {
                "locomotion": "WAIT",
                "effector_z_left": 0,
                "effector_z_right": 0,
            }
        }
        self.derived_changes = []


def test_analyzer_evidence_derived_selectable_and_request_gated_actuation(tmp_path):
    """After repair: Z schema → AVAILABLE/YES; actuation needs request+evidence, not pose alone."""
    (tmp_path / "scientific_meta.json").write_text(
        '{"public_preset":"ACANTHOSTEGA_BETA4","model_line":"ACANTHOSTEGA","generation":5}'
    )
    story = _Story(
        motor={
            "components": {
                "locomotion": "MOVE:E",
                "effector_z_left": 1,
                "effector_z_right": 0,
            }
        }
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
            "research_actuator_path": "AVAILABLE",
            "agent_cognition_token": "PRESENT",
        }
    ]
    pose = {("5", "body-0", "LEFT"): [(0, 0.0), (1, 0.1075)]}
    ps = classify_story_physical(
        story,
        reach_traces=traces,
        etc_contacts=[],
        work_rows=[],
        wmt_rows=[],
        model={
            "public_preset": "ACANTHOSTEGA_BETA4",
            "model_line": "ACANTHOSTEGA",
            "volumetric_physical_story": "APPLICABLE",
            "is_acanthostega_beta4": True,
        },
        pose_by_key=pose,
        runtime_generation="5",
    )
    assert ps["control_repertoire"]["agent_selectable_motor_factor"] == "PRESENT"
    assert ps["control_availability"] == "AVAILABLE"
    assert ps["negative_cause"] == "ACTUATED_NO_GEOMETRIC_REACH"

    payload = build_volumetric_physical_causal_reconstruction([story], run_dir=tmp_path)
    assert payload["relative_z"]["agent_selectable"] == "YES"
    text = format_volumetric_physical_causal_section(payload)
    assert "agent-selectable NO → REQUIRED_CONTROL_NOT_IN_REPERTOIRE" not in text
    assert "control_availability=AVAILABLE" in text



def test_actuated_class_does_not_fire_on_pose_relative_z_without_z_request():
    """Persistent pose must classify NOT_SELECTED after taxonomy repair."""
    story = _Story(
        motor={
            "components": {
                "locomotion": "WAIT",
                "effector_z_left": 0,
                "effector_z_right": 0,
            }
        }
    )
    traces = [
        {
            "tick": 1,
            "body_id": "body-0",
            "relative_z": 0.1075,  # leftover pose
            "geometric_reach": False,
            "physical_relative_z_dof": "AVAILABLE",
            "agent_selectable_motor_factor": "PRESENT",
        }
    ]
    ps = classify_story_physical(
        story,
        reach_traces=traces,
        etc_contacts=[],
        work_rows=[],
        wmt_rows=[],
        model={
            "volumetric_physical_story": "APPLICABLE",
            "is_acanthostega_beta4": True,
            "model_line": "ACANTHOSTEGA",
        },
    )
    assert int(story.motor["components"]["effector_z_left"]) == 0
    assert ps["negative_cause"] == "NOT_SELECTED"
    assert ps["negative_cause"] != "ACTUATED_NO_GEOMETRIC_REACH"


def test_analyzer_summary_no_longer_hardcodes_agent_selectable_no(tmp_path):
    from mechanistic_mind.scientific_v3.analyzer_next.volumetric_physical_causal_reconstruction import (
        build_volumetric_physical_causal_reconstruction,
        format_volumetric_physical_causal_section,
    )
    from mechanistic_mind.scientific_v3.analyzer_next.tick_stories import TickStory

    (tmp_path / "scientific_meta.json").write_text(
        '{"public_preset":"ACANTHOSTEGA_BETA4","model_line":"ACANTHOSTEGA","generation":5}'
    )
    stories = [
        TickStory(
            run_id="t", tick=1, cognitive_agent_id="agent_0", physical_body_id="body-0",
            observation_id="o", decision_id="d", motor_id="m", consequence_id="c",
            observation={}, decision={},
            motor={"components": {"effector_z_left": 0, "effector_z_right": 0}},
            consequence={},
        )
    ]
    payload = build_volumetric_physical_causal_reconstruction(stories, run_dir=tmp_path)
    assert payload["relative_z"]["agent_selectable"] == "YES"
    text = format_volumetric_physical_causal_section(payload)
    assert "agent-selectable NO → REQUIRED_CONTROL_NOT_IN_REPERTOIRE" not in text

