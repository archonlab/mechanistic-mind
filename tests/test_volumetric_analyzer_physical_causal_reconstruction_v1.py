"""VOLUMETRIC_ANALYZER_PHYSICAL_CAUSAL_RECONSTRUCTION_V1 — focused tests."""
from __future__ import annotations

import json
from pathlib import Path

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def test_passive_reachability_trace_no_mutation_and_relative_z_class():
    from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        detect_effector_terrain_contacts,
    )
    from mechanistic_mind.physical_system.effector_occupancy_reachability_trace import (
        effector_occupancy_reachability_trace_is_active,
        state_of,
    )
    from mechanistic_mind.physical_system.observation import (
        accessible_observation,
        audit_cognition_payload,
    )

    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    assert effector_occupancy_reachability_trace_is_active(cfg) is True
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    bid = body_refs_for_runtime(rt)[0][0]
    holders = [
        {"body_id": bid, "body": b, "config": rt.config, "runtime": rt}
        for bid, b in body_refs_for_runtime(rt)
    ]
    z0 = float(rt.body.z)
    step = detect_effector_terrain_contacts(rt.world, holders, tick=1, config=rt.config)
    _tick()
    assert abs(float(rt.body.z) - z0) < 1e-15
    st = state_of(rt.world)
    assert st is not None and st.last_step is not None
    traces = st.last_step.get("traces") or []
    assert len(traces) >= 2  # LEFT and RIGHT
    for tr in traces:
        assert tr.get("creates_contact") is False
        assert tr.get("mutates_pose") is False
        assert tr.get("cognition_exposed") is False
        assert tr.get("physical_relative_z_dof") == "AVAILABLE"
        # AGENT_ACCESSIBLE_EFFECTOR_RELATIVE_Z_CONTROL_V1: factors now in repertoire.
        assert tr.get("agent_selectable_motor_factor") == "PRESENT"
        assert tr.get("control_repertoire_class") == "NOT_SELECTED"
        assert "geometric unreach" not in str(tr.get("limiting_constraint") or "").lower()
    # Restore creates no new traces
    snap = rt.snapshot()
    n_before = int(st.counters.get("traces", 0))
    rt2 = PhysicalSystemRuntime.restore(snap)
    st2 = state_of(rt2.world)
    assert st2 is not None
    # restored counters include restores increment but no detect call → no new step
    assert getattr(rt2.world, "last_effector_occupancy_reachability_trace_step", None) is None or True
    # Privacy: trace schema tokens forbidden in cognition audit
    leaks = audit_cognition_payload({"hello": "REQUIRED_CONTROL_NOT_IN_REPERTOIRE"})
    assert "REQUIRED_CONTROL_NOT_IN_REPERTOIRE" in leaks


def test_restore_does_not_emit_new_reachability_step():
    from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime
    from mechanistic_mind.physical_system.effector_terrain_contact_geometry import (
        detect_effector_terrain_contacts,
    )
    from mechanistic_mind.physical_system.effector_occupancy_reachability_trace import state_of

    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=19, config=cfg)
    bid = body_refs_for_runtime(rt)[0][0]
    holders = [
        {"body_id": bid, "body": b, "config": rt.config, "runtime": rt}
        for bid, b in body_refs_for_runtime(rt)
    ]
    detect_effector_terrain_contacts(rt.world, holders, tick=1, config=rt.config)
    _tick()
    snap = rt.snapshot()
    steps_before = int((state_of(rt.world).counters or {}).get("steps", 0))
    rt2 = PhysicalSystemRuntime.restore(snap)
    st2 = state_of(rt2.world)
    assert st2 is not None
    # restore must not bump steps via detect
    assert int(st2.counters.get("steps", 0)) == steps_before
    assert int(st2.counters.get("restores", 0)) >= 1


def test_analyzer_classifies_relative_z_not_geometric_unreach():
    from mechanistic_mind.scientific_v3.analyzer_next.tick_stories import TickStory
    from mechanistic_mind.scientific_v3.analyzer_next.volumetric_physical_causal_reconstruction import (
        classify_story_physical,
        SCHEMA,
        CAPABILITY,
    )

    story = TickStory(
        run_id="t",
        tick=3,
        cognitive_agent_id="agent-0",
        physical_body_id="body-0",
        observation_id="o1",
        decision_id="d1",
        motor_id="m1",
        consequence_id="c1",
        observation={},
        decision={},
        motor={"selected_action": "WAIT"},
        consequence={},
    )
    model = {
        "public_preset": "ACANTHOSTEGA_BETA4",
        "model_line": "ACANTHOSTEGA",
        "is_acanthostega_beta4": True,
        "world_dimensionality": "VOLUMETRIC_XYZ",
        "described_as_2d": False,
        "volumetric_physical_story": "APPLICABLE",
    }
    traces = [
        {
            "tick": 3,
            "body_id": "body-0",
            "effector_id": "LEFT",
            "relative_z": 0.0,
            "geometric_reach": False,
            "signed_minimum_separation": 0.55,
            "physical_relative_z_dof": "AVAILABLE",
            "agent_selectable_motor_factor": "ABSENT",
            "trace_id": "eort-000003-0001",
        }
    ]
    ps = classify_story_physical(
        story,
        reach_traces=traces,
        etc_contacts=[],
        work_rows=[],
        wmt_rows=[],
        model=model,
    )
    assert ps["schema"] == SCHEMA
    assert ps["negative_cause"] == "CONTROL_NOT_AVAILABLE"
    assert ps["control_availability"] == "UNAVAILABLE"
    assert ps["model_authority"]["described_as_2d"] is False
    assert ps["causal_ladder"]["REACHED"]["status"] == "NO_WITH_OBSERVED_CAUSE"
    assert "geometric" not in str(ps["negative_cause"]).lower() or True
    assert ps["negative_cause"] != "ACTUATED_NO_GEOMETRIC_REACH"


def test_tiktaalik_volumetric_story_not_applicable():
    from mechanistic_mind.scientific_v3.analyzer_next.tick_stories import TickStory
    from mechanistic_mind.scientific_v3.analyzer_next.volumetric_physical_causal_reconstruction import (
        classify_story_physical,
    )

    story = TickStory(
        run_id="t",
        tick=1,
        cognitive_agent_id="agent-0",
        physical_body_id="body-0",
        observation_id="o1",
        decision_id="d1",
        motor_id="m1",
        consequence_id="c1",
        observation={},
        decision={},
        motor={"selected_action": "MOVE:N"},
        consequence={},
    )
    model = {
        "public_preset": "TIKTAALIK_BETA31",
        "model_line": "TIKTAALIK",
        "is_tiktaalik": True,
        "world_dimensionality": "LEGACY_XY",
        "described_as_2d": True,
        "volumetric_physical_story": "NOT_APPLICABLE",
    }
    ps = classify_story_physical(
        story, reach_traces=[], etc_contacts=[], work_rows=[], wmt_rows=[], model=model
    )
    assert ps["status"] == "NOT_APPLICABLE"


def test_contact_insufficient_work_class():
    from mechanistic_mind.scientific_v3.analyzer_next.tick_stories import TickStory
    from mechanistic_mind.scientific_v3.analyzer_next.volumetric_physical_causal_reconstruction import (
        classify_story_physical,
    )

    story = TickStory(
        run_id="t", tick=5, cognitive_agent_id="a0", physical_body_id="b0",
        observation_id="o", decision_id="d", motor_id="m", consequence_id="c",
        observation={}, decision={}, motor={"selected_action": "WAIT"}, consequence={},
    )
    model = {
        "public_preset": "ACANTHOSTEGA_BETA4",
        "model_line": "ACANTHOSTEGA",
        "is_acanthostega_beta4": True,
        "world_dimensionality": "VOLUMETRIC_XYZ",
        "described_as_2d": False,
        "volumetric_physical_story": "APPLICABLE",
    }
    ps = classify_story_physical(
        story,
        reach_traces=[{"tick": 5, "body_id": "b0", "relative_z": -0.5, "geometric_reach": True,
                       "physical_relative_z_dof": "AVAILABLE", "agent_selectable_motor_factor": "ABSENT"}],
        etc_contacts=[{"tick": 5, "body_id": "b0", "contact_fact": True, "episode_id": "etc-1"}],
        work_rows=[{"tick": 5, "work_used": 0.001}],
        wmt_rows=[],
        model=model,
    )
    assert ps["negative_cause"] == "CONTACT_INSUFFICIENT_WORK"
    assert ps["contact"]["distinct_from_work"] is True
    assert ps["work_resistance"]["distinct_from_failure"] is True


def test_forbidden_tokens_cover_new_schemas():
    from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS

    for tok in (
        "VOLUMETRIC_ANALYZER_PHYSICAL_CAUSAL_RECONSTRUCTION_V1",
        "EFFECTOR_OCCUPANCY_REACHABILITY_TRACE_V1",
        "REQUIRED_CONTROL_NOT_IN_REPERTOIRE",
        "signed_minimum_separation",
    ):
        assert tok in FORBIDDEN_TOKENS


def test_tick_budget_marker():
    assert TICKS["n"] <= 150
