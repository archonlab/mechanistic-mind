"""VS1–VS16 two-agent vision symmetry — wiring only, no equation retune."""
from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path

import pytest

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CALIBRATED_TEMPORAL,
    make_ecology_config,
)
from mechanistic_mind.physical_system.near_field_exteroception import (
    cognition_exo_fragments,
    sample_near_field,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.serialize import agents_views_frame, live_frame

OUT = Path("results/perception/two_agent_vision_symmetry")


def _calibrated(**kw):
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    for k, v in kw.items():
        setattr(cfg.near_field_exteroception, k, v)
    return cfg


def _face_to_face():
    ta = TwoAgentRuntime(seed=17, config=_calibrated(), starts=((16, 16), (17, 16)))
    ta.slots[0].body.x, ta.slots[0].body.y, ta.slots[0].body.theta = 16.5, 16.5, 0.0
    ta.slots[1].body.x, ta.slots[1].body.y, ta.slots[1].body.theta = 17.5, 16.5, math.pi
    return ta


def test_VS1_VS2_VS3_VS7_VS8_face_to_face_both_see():
    ta = _face_to_face()
    obs = ta.observations()
    assert "exo_0" in obs[0] and "exo_0" in obs[1]
    assert max(obs[0][k] for k in ("exo_0", "exo_1", "exo_2")) > 0
    assert max(obs[1][k] for k in ("exo_0", "exo_1", "exo_2")) > 0
    # Same code path: foreign_bodies_for
    assert len(ta.foreign_bodies_for(0)) == 1
    assert len(ta.foreign_bodies_for(1)) == 1
    assert ta.foreign_bodies_for(0)[0][0] is ta.slots[1].body
    assert ta.foreign_bodies_for(1)[0][0] is ta.slots[0].body
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "two_agent_face_to_face.json").write_text(
        json.dumps({"agent_0": obs[0], "agent_1": obs[1]}, indent=2, default=str),
        encoding="utf-8",
    )


def test_VS5_VS6_self_exclusion():
    ta = _face_to_face()
    for i, rt in enumerate(ta.slots):
        s = sample_near_field(
            world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, foreign_bodies=[]
        )
        assert s["n_body_optical_cells"] == 0


def test_VS9_independent_orientation():
    ta = _face_to_face()
    before = ta.observations()
    # Rotate only agent_1 away (face east, same as agent_0 — look away from body-0)
    ta.slots[1].body.theta = 0.0
    after = ta.observations()
    # agent_0 unchanged geometry → similar exo; agent_1 body contribution drops
    assert abs(after[0]["exo_1"] - before[0]["exo_1"]) < 1e-9
    assert after[1]["exo_1"] < before[1]["exo_1"]


def test_VS10_exo_only_no_leak():
    ta = _face_to_face()
    for o in ta.observations():
        assert set(k for k in o if k.startswith("exo_")) <= {"exo_0", "exo_1", "exo_2"}
        assert audit_cognition_payload(o) == []
        blob = repr(o).lower()
        assert "agent_0" not in blob and "undercover" not in blob and "experimenter" not in blob


def test_VS11_empty_fov_still_on():
    ta = TwoAgentRuntime(seed=17, config=_calibrated(), starts=((8, 8), (24, 24)))
    ta.world.surface_response[:] = 0.0
    ta.slots[0].body.x, ta.slots[0].body.y, ta.slots[0].body.theta = 8.5, 8.5, 0.0
    ta.slots[1].body.x, ta.slots[1].body.y, ta.slots[1].body.theta = 24.5, 24.5, math.pi
    obs = ta.observations()
    for i, o in enumerate(obs):
        assert "exo_0" in o and "exo_1" in o and "exo_2" in o
        assert o["exo_0"] == 0.0 and o["exo_1"] == 0.0 and o["exo_2"] == 0.0
        assert ta.slots[i].config.near_field_exteroception.vision_contributes is True
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "empty_fov.json").write_text(
        json.dumps({"obs": obs, "vision_on": True}, indent=2), encoding="utf-8"
    )


def test_VS14_live_toggle_both_slots():
    cfg = _calibrated(perception_enabled=False)
    ta = TwoAgentRuntime(seed=17, config=cfg, starts=((16, 16), (17, 16)))
    assert all(not rt.config.near_field_exteroception.vision_contributes for rt in ta.slots)
    assert all("exo_0" not in o for o in ta.observations())
    gen = id(ta.world)
    xy = [(rt.body.x, rt.body.y, rt.body.theta) for rt in ta.slots]
    ta.set_mechanism("physical_near_field_vision", True)
    assert all(rt.config.near_field_exteroception.vision_contributes for rt in ta.slots)
    assert id(ta.world) == gen
    for i, rt in enumerate(ta.slots):
        assert (rt.body.x, rt.body.y, rt.body.theta) == xy[i]
    ta.slots[0].body.x, ta.slots[0].body.y, ta.slots[0].body.theta = 16.5, 16.5, 0.0
    ta.slots[1].body.x, ta.slots[1].body.y, ta.slots[1].body.theta = 17.5, 16.5, math.pi
    obs = ta.observations()
    assert all("exo_0" in o for o in obs)
    assert all(max(o[k] for k in ("exo_0", "exo_1", "exo_2")) > 0 for o in obs)


def test_VS15_identity_swap_follows_geometry():
    ta = _face_to_face()
    o_before = ta.observations()
    # Swap geometry
    b0, b1 = ta.slots[0].body, ta.slots[1].body
    b0.x, b1.x = b1.x, b0.x
    b0.y, b1.y = b1.y, b0.y
    b0.theta, b1.theta = b1.theta, b0.theta
    o_after = ta.observations()
    # After swap, slot0 occupies former slot1 pose → matches former agent_1 exo (approx)
    for k in ("exo_0", "exo_1", "exo_2"):
        assert abs(o_after[0][k] - o_before[1][k]) < 1e-6
        assert abs(o_after[1][k] - o_before[0][k]) < 1e-6
    (OUT / "identity_swap.json").write_text(
        json.dumps({"before": o_before, "after": o_after}, indent=2), encoding="utf-8"
    )


def test_VS12_VS13_observer_selected_agent_frame():
    ta = _face_to_face()
    ta.selected_index = 0
    f0 = live_frame(ta, status="PAUSED", mode="LIVE", target_tick=None, previous_body=None, detail="full")
    ta.selected_index = 1
    f1 = live_frame(ta, status="PAUSED", mode="LIVE", target_tick=None, previous_body=None, detail="full")
    assert f0["observer"]["selected_agent_id"] == "agent_0"
    assert f1["observer"]["selected_agent_id"] == "agent_1"
    ao0 = f0.get("agent_observation") or {}
    ao1 = f1.get("agent_observation") or {}
    assert "exo_0" in ao0 and "exo_0" in ao1
    nf0 = (f0.get("physical") or {}).get("near_field_exteroception") or {}
    nf1 = (f1.get("physical") or {}).get("near_field_exteroception") or {}
    assert nf0.get("vision_contributes") is True
    assert nf1.get("vision_contributes") is True
    # Independent exo (may differ)
    assert ao0 != ao1 or nf0.get("body_theta") != nf1.get("body_theta")
    # Compact: selected keeps nf; peer keeps stub
    ta.selected_index = 1
    views = agents_views_frame(ta, previous_body=None, detail="compact")
    assert views["agent_1"]["physical"].get("near_field_exteroception")
    assert views["agent_0"]["physical"].get("near_field_exteroception")  # stub
    assert "exo_0" in (views["agent_1"].get("agent_observation") or {})
    (OUT / "observer_selected_agent.json").write_text(
        json.dumps(
            {
                "agent_0_obs": ao0,
                "agent_1_obs": ao1,
                "compact_peer_has_nf_stub": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_VS4_no_slot0_special_case_in_source():
    src = Path("mechanistic_mind/physical_system/two_agent.py").read_text(encoding="utf-8")
    # observations loop must not gate vision on agent_0 / slot 0
    assert "if agent_id == \"agent_0\"" not in src
    assert "foreign_bodies_for" in src


def test_undercover_same_optical_path():
    ta = _face_to_face()
    ta.world.surface_response[:] = 0.0
    # Single-cell foreign body with identical optical_response — role-agnostic path.
    opt = float(getattr(ta.slots[1].config.body, "optical_response", 0.65) or 0.65)
    bc = PhysicalBodyConfig(optical_response=opt, footprint=((0, 0),))
    tmp_a = PhysicalSystemRuntime(seed=1, config=PhysicalSystemConfig(body=bc))
    tmp_b = PhysicalSystemRuntime(seed=2, config=PhysicalSystemConfig(body=deepcopy(bc)))
    for b in (tmp_a.body, tmp_b.body):
        b.x, b.y, b.theta = 17.5, 16.5, 0.0
    s_ord = sample_near_field(
        world=ta.world, body=ta.slots[0].body, cfg=ta.slots[0].config.near_field_exteroception,
        foreign_bodies=[(tmp_a.body, bc)], tick=0,
    )
    s_uc = sample_near_field(
        world=ta.world, body=ta.slots[0].body, cfg=ta.slots[0].config.near_field_exteroception,
        foreign_bodies=[(tmp_b.body, bc)], tick=0,
    )
    assert s_ord["n_body_optical_cells"] == s_uc["n_body_optical_cells"] >= 1
    assert s_ord["fragments"] == s_uc["fragments"]
    assert audit_cognition_payload(s_ord["fragments"]) == []
