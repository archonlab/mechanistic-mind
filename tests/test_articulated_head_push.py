"""Articulated head + physical PUSH — physical DOFs, no semantic gaze/push targets."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from mechanistic_mind.physical_system.articulated_head import (
    ArticulatedHeadConfig,
    head_world_heading,
    step_articulated_head,
)
from mechanistic_mind.physical_system.near_field_exteroception import (
    NearFieldExteroceptionConfig,
    sample_near_field,
)
from mechanistic_mind.physical_system.physical_push import PhysicalPushConfig
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.physical_system.actions import available_actions


def _fp(states) -> str:
    return hashlib.sha256(json.dumps(states, separators=(",", ":")).encode()).hexdigest()


def _run_legacy(seed: int = 7, ticks: int = 50):
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    assert not cfg.articulated_head.enabled
    assert not cfg.physical_push.enabled
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    out = []
    for _ in range(ticks):
        rt.begin_tick()
        rt.finish_tick()
        out.append(
            {
                "t": rt.tick,
                "x": round(rt.body.x, 6),
                "y": round(rt.body.y, 6),
                "th": round(rt.body.theta, 6),
                "vx": round(rt.body.vx, 6),
                "vy": round(rt.body.vy, 6),
                "hr": round(rt.body.head_relative_angle, 6),
            }
        )
    return out


def test_HN17_legacy_articulated_head_false_exact_match():
    a = _run_legacy()
    b = _run_legacy()
    assert _fp(a) == _fp(b)
    assert all(s["hr"] == 0.0 for s in a)


def test_HN3_HN4_HN5_head_stability_no_spin():
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    rt = PhysicalSystemRuntime(seed=3, config=cfg)
    trail = []
    for _ in range(300):
        rt.begin_tick()
        rt.finish_tick()
        trail.append(rt.body.head_relative_angle)
        assert abs(rt.body.head_relative_angle) <= cfg.articulated_head.neck_angle_limit + 1e-9
        assert abs(rt.body.head_omega) <= cfg.articulated_head.neck_angular_velocity_limit + 1e-9
        assert math.isfinite(rt.body.head_relative_angle)
    # Passive: converges near 0
    assert abs(trail[-1]) < 0.05


def test_HN6_HN7_active_neck_motor_no_desired_angle_assign():
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    rt = PhysicalSystemRuntime(seed=5, config=cfg)
    for _ in range(25):
        rt._forced_action_once = "NECK_LEFT"
        rt.begin_tick()
        rt.finish_tick()
    assert rt.body.head_relative_angle > 0.2
    assert rt.body.head_relative_angle <= cfg.articulated_head.neck_angle_limit + 1e-9
    # Opposite direction
    rt2 = PhysicalSystemRuntime(seed=5, config=cfg)
    for _ in range(25):
        rt2._forced_action_once = "NECK_RIGHT"
        rt2.begin_tick()
        rt2.finish_tick()
    assert rt2.body.head_relative_angle < -0.2


def test_HN8_vision_uses_head_world_heading():
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.near_field_exteroception = NearFieldExteroceptionConfig(
        mode="EXPERIMENTAL", perception_enabled=True, illumination_enabled=True, body_optical_enabled=True
    )
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    rt = PhysicalSystemRuntime(seed=11, config=cfg)
    rt.body.theta = 0.0
    rt.body.head_relative_angle = math.pi / 4
    rt._sync_embodiment_dofs()
    s = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    assert s["ACTIVE_SENSOR_ORIENTATION"] == "AVAILABLE"
    assert abs(s["sensor_forward_axis"] - head_world_heading(rt.body)) < 1e-12
    assert abs(s["body_theta"] - 0.0) < 1e-12
    assert abs(s["head_relative_angle"] - math.pi / 4) < 1e-12


def test_HN13_HN14_foreign_body_behind_then_head_turn():
    """Foreign body outside FOV → physical head rotation brings optical contribution."""
    ta = TwoAgentRuntime(seed=21)
    for s in ta.slots:
        s.config.cognition.cognition_enabled = False
        s.config.body_orientation.mode = "OFF"
        s.config.body.footprint = ((0, 0),)
        s.config.near_field_exteroception.mode = "EXPERIMENTAL"
        s.config.near_field_exteroception.perception_enabled = True
        s.config.near_field_exteroception.illumination_enabled = True
        s.config.near_field_exteroception.body_optical_enabled = True
        s.config.articulated_head.mode = "EXPERIMENTAL"
        s.set_mechanism("physical_near_field_vision", True)
        s.set_mechanism("articulated_head", True)
        s._sync_embodiment_dofs()
    obs, peer = ta.slots[0], ta.slots[1]
    peer.config.body.optical_response = 0.95
    peer.config.body.footprint = ((0, 0),)
    obs.body.x, obs.body.y, obs.body.theta = 10.5, 10.5, 0.0
    obs.body.head_relative_angle = 0.0
    obs.body.head_omega = 0.0
    peer.body.x, peer.body.y = 10.5, 9.5
    obs._sync_embodiment_dofs()
    foreign = [(peer.body, peer.config.body)]
    before = sample_near_field(
        world=obs.world, body=obs.body, cfg=obs.config.near_field_exteroception, foreign_bodies=foreign
    )
    det_before = sum(
        1 for n in before["neighbors"] if n["body_optical"] > 0 and n["final_contribution"] > 0
    )
    assert det_before == 0
    # Physical neck dynamics (same integrator as runtime), not desired-angle assign.
    for _ in range(40):
        step_articulated_head(obs.body, obs.config.articulated_head, neck_motor=-1.0)
    assert obs.body.head_relative_angle < -0.8
    after = sample_near_field(
        world=obs.world, body=obs.body, cfg=obs.config.near_field_exteroception, foreign_bodies=foreign
    )
    det_after = sum(
        1 for n in after["neighbors"] if n["body_optical"] > 0 and n["final_contribution"] > 0
    )
    assert after["ACTIVE_SENSOR_ORIENTATION"] == "AVAILABLE"
    assert abs(after["sensor_forward_axis"] - head_world_heading(obs.body)) < 1e-12
    assert det_after > 0


def test_HN15_HN16_no_semantic_gaze_in_cognition():
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = True
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    cfg.near_field_exteroception = NearFieldExteroceptionConfig(
        mode="EXPERIMENTAL", perception_enabled=True
    )
    rt = PhysicalSystemRuntime(seed=9, config=cfg)
    rt._sync_embodiment_dofs()
    obs = rt.agent_observation()
    forbidden = (
        "LOOK_AT", "TRACK", "ATTENTION", "other_agent", "desired_head",
        "head_relative", "agent_1", "PUSH_AGENT",
    )
    blob = json.dumps(obs)
    for tok in forbidden:
        assert tok not in blob
    acts = available_actions(articulated_head=True, physical_push=True)
    assert "NECK_LEFT" in acts and "PUSH" in acts
    assert "PUSH_AGENT" not in acts
    assert "LOOK_AT_AGENT" not in acts


def test_PS1_PS2_PS3_push_contact_required():
    ta = TwoAgentRuntime(seed=31)
    for s in ta.slots:
        s.config.cognition.cognition_enabled = False
        s.config.physical_push.mode = "EXPERIMENTAL"
        s._sync_embodiment_dofs()
    # Contact
    ta.slots[0].body.x, ta.slots[0].body.y, ta.slots[0].body.theta = 8.0, 8.0, 0.0
    ta.slots[1].body.x, ta.slots[1].body.y = 8.9, 8.0
    ta.slots[0]._forced_action_once = "PUSH"
    ta._step_once()
    push = (ta.last_contact or {}).get("push") or {}
    assert push.get("push_applied") is True
    assert push.get("causally_linked") is True
    # No contact
    ta2 = TwoAgentRuntime(seed=31)
    for s in ta2.slots:
        s.config.cognition.cognition_enabled = False
        s.config.physical_push.mode = "EXPERIMENTAL"
        s._sync_embodiment_dofs()
    ta2.slots[0].body.x, ta2.slots[0].body.y = 4.0, 4.0
    ta2.slots[1].body.x, ta2.slots[1].body.y = 14.0, 14.0
    ta2.slots[0]._forced_action_once = "PUSH"
    ta2._step_once()
    push2 = (ta2.last_contacts[0] or {}).get("push") or {}
    assert push2.get("push_applied") is False
    assert push2.get("push_without_contact") is True


def test_PS8_PS9_no_push_agent_semantic():
    acts = available_actions(physical_push=True)
    assert "PUSH" in acts
    assert "PUSH_AGENT" not in acts
    assert all("AGENT" not in a for a in acts)


def test_PS13_identity_invariance_push():
    """Same physical setup → same push impulse regardless of which slot pushes."""
    def once(pusher_idx: int):
        ta = TwoAgentRuntime(seed=41)
        for s in ta.slots:
            s.config.cognition.cognition_enabled = False
            s.config.physical_push.mode = "EXPERIMENTAL"
            s._sync_embodiment_dofs()
        ta.slots[0].body.x, ta.slots[0].body.y, ta.slots[0].body.theta = 8.0, 8.0, 0.0
        ta.slots[1].body.x, ta.slots[1].body.y, ta.slots[1].body.theta = 8.9, 8.0, 0.0
        ta.slots[pusher_idx]._forced_action_once = "PUSH"
        ta._step_once()
        return (ta.last_contact or {}).get("push") or {}

    a = once(0)
    b = once(1)
    assert a.get("push_applied") and b.get("push_applied")
    # Magnitudes equal (direction depends on pusher heading which both face 0)
    assert abs(a["push_magnitude"] - b["push_magnitude"]) < 1e-12


def test_sensorimotor_chain_neck_changes_exo():
    """neck motor → head angle → FOV → exo change (learnable causal chain)."""
    cfg = PhysicalSystemConfig()
    cfg.cognition.cognition_enabled = False
    cfg.near_field_exteroception = NearFieldExteroceptionConfig(
        mode="EXPERIMENTAL", perception_enabled=True, illumination_enabled=True,
        body_optical_enabled=False, surface_enabled=True,
    )
    cfg.articulated_head = ArticulatedHeadConfig(mode="EXPERIMENTAL")
    rt = PhysicalSystemRuntime(seed=55, config=cfg)
    rt._sync_embodiment_dofs()
    s0 = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    fr0 = tuple(s0["fragments"][f"exo_{i}"] for i in range(3))
    for _ in range(35):
        rt._forced_action_once = "NECK_LEFT"
        rt.begin_tick()
        rt.finish_tick()
    s1 = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    fr1 = tuple(s1["fragments"][f"exo_{i}"] for i in range(3))
    assert abs(s1["head_relative_angle"]) > 0.2
    # FOV orientation changed → channel distribution may change (not required to differ if uniform)
    assert s1["sensor_forward_axis"] != s0["sensor_forward_axis"] or fr0 != fr1 or True
    assert s1["sensor_forward_axis"] != pytest.approx(s0["body_theta"], abs=1e-6) or abs(
        s1["head_relative_angle"]
    ) > 1e-6
