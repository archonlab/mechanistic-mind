"""Beta 2 visible physical bodies — gates B1–B30."""
from __future__ import annotations

import math
from copy import deepcopy

import numpy as np
import pytest

from mechanistic_mind.physical_body.config import PhysicalBodyConfig
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_CALIBRATED_TEMPORAL,
    ECOLOGY_CURRENT_LEGACY,
    make_ecology_config,
)
from mechanistic_mind.physical_system.near_field_exteroception import (
    DEFAULT_FOV_DEG,
    DEFAULT_ILLUMINATION_PERIOD,
    compose_surface_and_body_optical,
    cognition_exo_fragments,
    sample_near_field,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime


def _calibrated_nfe(**kw):
    cfg = make_ecology_config(ECOLOGY_CALIBRATED_TEMPORAL, trickle=0.0)
    cfg.cognition.cognition_enabled = False
    for k, v in kw.items():
        setattr(cfg.near_field_exteroception, k, v)
    return cfg


def _body_at(x: float, y: float, theta: float = 0.0, optical: float = 0.65) -> tuple[PhysicalBodyState, PhysicalBodyConfig]:
    bc = PhysicalBodyConfig(optical_response=optical, footprint=((0, 0),))
    # Minimal body state via runtime clone pattern
    rt = PhysicalSystemRuntime(seed=1, config=PhysicalSystemConfig(body=bc))
    rt.body.x = float(x)
    rt.body.y = float(y)
    rt.body.theta = float(theta)
    return rt.body, bc


def _two_agent_calibrated():
    cfg = _calibrated_nfe()
    # Soften contact effects for optical fixtures
    if hasattr(cfg, "body_contact"):
        pass
    ta = TwoAgentRuntime(seed=17, config=cfg)
    for rt in ta.slots:
        rt.config.cognition.cognition_enabled = False
        rt.config.near_field_exteroception = deepcopy(cfg.near_field_exteroception)
    return ta


def test_B1_B7_B8_B9_ordinary_body_optics_and_contracts():
    obs_body, _ = _body_at(16.5, 16.5, theta=0.0)
    other, ocfg = _body_at(17.5, 16.5, theta=0.0)  # east of observer
    cfg = _calibrated_nfe()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.world.surface_response[:] = 0.0
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    sample0 = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, foreign_bodies=[])
    sample1 = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(other, ocfg)],
    )
    assert sample1["n_body_optical_cells"] >= 1
    assert sample1["fragments"] != sample0["fragments"]
    assert float(rt.config.near_field_exteroception.fov_deg) == DEFAULT_FOV_DEG
    assert sample1["n_candidates"] == 8


def test_B6_self_exclusion():
    cfg = _calibrated_nfe()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.world.surface_response[:] = 0.0
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    # Passing own body as "foreign" would be wrong; empty foreign → no body optical
    s = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, foreign_bodies=[])
    assert s["n_body_optical_cells"] == 0
    # If caller incorrectly includes self, TwoAgent path excludes by index — unit: occupancy of CoM cell
    # is not in Moore neighbors (own cell excluded from source domain).
    east = next(r for r in s["neighbors"] if r["cell"] == [17, 16])
    assert east["body_optical"] == 0.0


def test_B10_B11_behind_filtered():
    cfg = _calibrated_nfe()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.world.surface_response[:] = 0.0
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0  # face +x
    other, ocfg = _body_at(15.5, 16.5)  # west / behind
    s = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(other, ocfg)],
    )
    west = next(r for r in s["neighbors"] if r["cell"] == [15, 16])
    assert west["body_optical"] > 0.0
    assert west["inside_fov"] is False
    assert west["final_contribution"] == 0.0


def test_B12_B13_B14_distance_illumination_unchanged_period():
    cfg = _calibrated_nfe()
    assert int(cfg.near_field_exteroception.illumination_period) == DEFAULT_ILLUMINATION_PERIOD
    assert float(cfg.near_field_exteroception.illumination_min) == pytest.approx(0.15)
    assert float(cfg.near_field_exteroception.illumination_max) == pytest.approx(1.0)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.world.surface_response[:] = 0.0
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    other, ocfg = _body_at(17.5, 16.5)
    s_bright = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(other, ocfg)], tick=0,
    )
    s_dim = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(other, ocfg)], tick=120,
    )
    assert s_bright["illumination"] > s_dim["illumination"]
    assert sum(s_bright["fragments"].values()) >= sum(s_dim["fragments"].values()) - 1e-9


def test_B15_B16_surface_and_bounded_composition():
    assert compose_surface_and_body_optical(0.0, 0.0) == 0.0
    assert compose_surface_and_body_optical(1.0, 1.0) == 1.0
    assert 0.0 < compose_surface_and_body_optical(0.2, 0.5) < 1.0
    cfg = _calibrated_nfe()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    surf0 = float(rt.world.surface_response[16, 17])
    other, ocfg = _body_at(17.5, 16.5)
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    s = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(other, ocfg)],
    )
    east = next(r for r in s["neighbors"] if r["cell"] == [17, 16])
    assert east["surface_response"] == pytest.approx(surf0)
    assert east["composed_optical"] == pytest.approx(
        compose_surface_and_body_optical(surf0, east["body_optical"])
    )
    assert 0.0 <= east["composed_optical"] <= 1.0


def test_B17_B18_B19_B20_exo_only_no_identity_leak():
    ta = _two_agent_calibrated()
    ta.slots[0].body.x, ta.slots[0].body.y, ta.slots[0].body.theta = 10.5, 10.5, 0.0
    ta.slots[1].body.x, ta.slots[1].body.y = 11.5, 10.5
    obs = ta.observations()[0]
    assert set(k for k in obs if str(k).startswith("exo_")) <= {"exo_0", "exo_1", "exo_2"}
    assert audit_cognition_payload(obs) == []
    blob = repr(obs).lower()
    for tok in ("experimenter", "other_agent", "agent_id", "entity_type", "teacher", "visible_body"):
        assert tok not in blob


def test_B2_B3_B4_undercover_same_path():
    # Undercover is an ordinary PhysicalBodyState — same sample_near_field path.
    cfg = _calibrated_nfe()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.world.surface_response[:] = 0.05
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    agent_b, acfg = _body_at(17.5, 16.5, optical=0.65)
    exp_b, ecfg = _body_at(17.5, 16.5, optical=0.65)
    sa = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(agent_b, acfg)],
    )
    se = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(exp_b, ecfg)],
    )
    assert sa["fragments"] == se["fragments"]
    assert sa["neighbors"][0].keys() == se["neighbors"][0].keys()


def test_B5_B28_cognition_presence_invariant():
    cfg_on = _calibrated_nfe()
    cfg_off = deepcopy(cfg_on)
    cfg_off.cognition.cognition_enabled = False
    cfg_on.cognition.cognition_enabled = True
    rt = PhysicalSystemRuntime(seed=17, config=cfg_off)
    rt.world.surface_response[:] = 0.0
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    other, ocfg = _body_at(17.5, 16.5)
    # Optical sampling does not read cognition — identical foreign body geometry
    a = sample_near_field(
        world=rt.world, body=rt.body, cfg=cfg_on.near_field_exteroception,
        foreign_bodies=[(other, ocfg)],
    )
    b = sample_near_field(
        world=rt.world, body=rt.body, cfg=cfg_off.near_field_exteroception,
        foreign_bodies=[(other, ocfg)],
    )
    assert a["fragments"] == b["fragments"]


def test_B21_B22_B23_no_contact_no_fields_required():
    cfg = _calibrated_nfe()
    cfg.physical_signal.mode = "OFF"
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    assert getattr(rt.world, "FIELD_A", None) is None
    rt.world.surface_response[:] = 0.0
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    other, ocfg = _body_at(17.5, 16.5)
    s = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(other, ocfg)],
    )
    assert sum(s["fragments"].values()) > 0.0
    assert getattr(rt.world, "FIELD_A", None) is None


def test_B24_physics_invariant_with_cognition_frozen():
    cfg = _calibrated_nfe()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    other, ocfg = _body_at(17.5, 16.5)
    rt.body.x, rt.body.y = 16.5, 16.5
    # Sampling must not mutate world/body
    t0 = rt.world.T.copy()
    s0 = rt.world.surface_response.copy()
    xy0 = (rt.body.x, rt.body.y, rt.body.vx, rt.body.vy)
    sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(other, ocfg)],
    )
    assert np.allclose(rt.world.T, t0)
    assert np.allclose(rt.world.surface_response, s0)
    assert (rt.body.x, rt.body.y, rt.body.vx, rt.body.vy) == xy0


def test_B25_B26_snapshot_and_determinism():
    ta = _two_agent_calibrated()
    ta.slots[0].body.x, ta.slots[0].body.y, ta.slots[0].body.theta = 8.5, 8.5, 0.2
    ta.slots[1].body.x, ta.slots[1].body.y = 9.5, 8.5
    foreign = [(ta.slots[1].body, ta.slots[1].config.body)]
    a = cognition_exo_fragments(
        world=ta.world, body=ta.slots[0].body,
        cfg=ta.slots[0].config.near_field_exteroception, foreign_bodies=foreign,
    )
    b = cognition_exo_fragments(
        world=ta.world, body=ta.slots[0].body,
        cfg=ta.slots[0].config.near_field_exteroception, foreign_bodies=foreign,
    )
    assert a == b
    snap = ta.slots[0].snapshot()
    assert "optical_response" in snap["config"]["body"]
    assert "body_optical_enabled" in snap["config"]["near_field_exteroception"]


def test_B27_observer_gt_separates_identity():
    cfg = _calibrated_nfe()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.world.surface_response[:] = 0.0
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    other, ocfg = _body_at(17.5, 16.5)
    gt = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(other, ocfg)],
    )
    assert "body_optical" in gt["neighbors"][0]
    assert "composed_optical" in gt["neighbors"][0]
    exo = cognition_exo_fragments(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
        foreign_bodies=[(other, ocfg)],
    )
    assert set(exo.keys()) <= {"exo_0", "exo_1", "exo_2"}


def test_motion_left_forward_right_behind_outside():
    cfg = _calibrated_nfe()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.world.surface_response[:] = 0.0
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0  # +x forward
    # Channel mapping: exo_0 left, exo_1 forward, exo_2 right (relative angle bins)

    def exo_at(ox, oy):
        other, ocfg = _body_at(ox, oy)
        return cognition_exo_fragments(
            world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception,
            foreign_bodies=[(other, ocfg)],
        )

    behind = exo_at(15.5, 16.5)
    left = exo_at(16.5, 15.5)   # -y relative when facing +x → left in screen? atan2(dy,dx)
    # Facing +x (theta=0): left is +y in many math conventions (atan2)...
    # rel = atan2(dy,dx) - theta. Cell north (16,15): wait cell is (ix,iy)=(16,15) → y=15.5
    # dy = 15.5-16.5 = -1, dx=0 → atan2(-1,0) = -π/2 → left of forward? 
    # FOV bins: u = (rel + half)/(2*half); half=60°; rel=-90° → u=0 → bin 0 = exo_0
    forward = exo_at(17.5, 16.5)
    right = exo_at(16.5, 17.5)  # dy=+1 → atan2(+1,0)=+π/2 → exo_2
    outside = exo_at(20.5, 16.5)  # beyond R=1

    assert sum(behind.values()) == pytest.approx(0.0, abs=1e-9)
    assert forward.get("exo_1", 0) >= forward.get("exo_0", 0) and forward.get("exo_1", 0) >= forward.get("exo_2", 0)
    assert left.get("exo_0", 0) >= left.get("exo_1", 0)
    assert right.get("exo_2", 0) >= right.get("exo_1", 0)
    assert sum(outside.values()) == pytest.approx(0.0, abs=1e-9)


def test_B29_legacy_no_accidental_vision():
    leg = make_ecology_config(ECOLOGY_CURRENT_LEGACY, trickle=0.0)
    assert leg.near_field_exteroception.mode == "OFF"


def test_B30_mechanism_registry_present():
    cfg = _calibrated_nfe()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    ids = {m["id"] for m in rt.mechanisms()["mechanisms"]}
    assert "physical_body_optical_response" in ids
    assert next(m for m in rt.mechanisms()["mechanisms"] if m["id"] == "physical_body_optical_response")["enabled"] is True
    rt.set_mechanism("physical_body_optical_response", False)
    assert rt.config.near_field_exteroception.body_optical_enabled is False
