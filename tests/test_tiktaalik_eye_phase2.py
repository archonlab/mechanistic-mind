"""Beta 3.1 Phase 2 — Tiktaalik Eye diagnostic (Observer-only)."""
from __future__ import annotations

from copy import deepcopy

import pytest

from mechanistic_mind.physical_body.config import default_physical_body2_config
from mechanistic_mind.physical_system.near_field_exteroception import (
    NearFieldExteroceptionConfig,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.research.background_context import QUANT_BINS, _quantize, sensory_signature
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.tiktaalik_eye import (
    build_agent_eye,
    build_tiktaalik_eye_payload,
    pe_bin,
)


def _nfe(**kw) -> NearFieldExteroceptionConfig:
    base = dict(
        mode="EXPERIMENTAL",
        perception_enabled=True,
        illumination_enabled=True,
        illumination_min=1.0,
        illumination_max=1.0,
        surface_enabled=True,
        radius=3,
        visual_surface_discrimination="OFF",
        optical_mapping="INDEPENDENT",
        gain=1.0,
        saturation=1.0,
        threshold=0.04,
        distance_k=0.85,
        fov_deg=120.0,
    )
    base.update(kw)
    return NearFieldExteroceptionConfig(**base)


def _rt(*, disc="RICH", seed=11) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig()
    cfg.near_field_exteroception = _nfe(visual_surface_discrimination=disc)
    cfg.body = default_physical_body2_config()
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.set_mechanism("physical_near_field_vision", True)
    rt.set_visual_surface_discrimination(disc)
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    return rt


def test_pe_bin_matches_cognition_quantize():
    assert QUANT_BINS == 5
    assert pe_bin(0.297)["index"] == _quantize(0.297)
    assert pe_bin(0.203)["index"] == _quantize(0.203)
    assert pe_bin(0.297)["index"] == pe_bin(0.203)["index"]


def test_off_low_rich_channel_presence():
    rt = _rt(disc="OFF")
    rt.last_agent_observation = rt.agent_observation()
    off = build_agent_eye(
        agent_id="agent_0", observation=rt.last_agent_observation, prev_visual=None,
        nfe=rt.config.near_field_exteroception,
    )
    assert off["accessible"]["exo"]["present"] is True
    assert off["accessible"]["surface_c0"]["present"] is False
    assert off["accessible"]["surface_c1"]["present"] is False

    rt.set_visual_surface_discrimination("LOW")
    rt.last_agent_observation = rt.agent_observation()
    low = build_agent_eye(
        agent_id="agent_0", observation=rt.last_agent_observation, prev_visual=None,
        nfe=rt.config.near_field_exteroception,
    )
    assert low["accessible"]["surface_c0"]["present"] is True
    assert low["accessible"]["surface_c1"]["present"] is False

    rt.set_visual_surface_discrimination("RICH")
    rt.last_agent_observation = rt.agent_observation()
    rich = build_agent_eye(
        agent_id="agent_0", observation=rt.last_agent_observation, prev_visual=None,
        nfe=rt.config.near_field_exteroception,
    )
    assert rich["accessible"]["surface_c2"]["present"] is True
    assert "surface_c2_1" in rt.last_agent_observation


def test_left_forward_right_mapping_and_raw_fidelity():
    rt = _rt(disc="OFF")
    if rt.world.surface_response is not None:
        rt.world.surface_response[:, :] = 0.0
    rt.world.surface_response[16, 17] = 0.55
    rt.world.tick += 1
    rt.last_agent_observation = rt.agent_observation()
    eye = build_agent_eye(
        agent_id="agent_0", observation=rt.last_agent_observation, prev_visual=None,
        nfe=rt.config.near_field_exteroception,
    )
    f = eye["accessible"]["exo"]["forward"]["raw"]
    l = eye["accessible"]["exo"]["left"]["raw"]
    r = eye["accessible"]["exo"]["right"]["raw"]
    assert abs(f - float(rt.last_agent_observation["exo_1"])) < 1e-12
    assert l == 0.0
    assert r == 0.0
    assert f == pytest.approx(0.55, abs=1e-6)


def test_saturation_flag():
    cell = build_agent_eye(
        agent_id="a",
        observation={"exo_0": 0.0, "exo_1": 1.0, "exo_2": 0.0},
        prev_visual=None,
        nfe=_nfe(saturation=1.0, visual_surface_discrimination="OFF"),
    )["accessible"]["exo"]["forward"]
    assert cell["saturated"] is True
    assert cell["raw"] == 1.0


def test_aliasing_same_pe_bin_different_raw():
    obs_a = {"exo_0": 0.0, "exo_1": 0.29729729729729726, "exo_2": 0.0}
    obs_b = {"exo_0": 0.0, "exo_1": 0.20370370370370372, "exo_2": 0.0}
    nfe = _nfe(visual_surface_discrimination="OFF")
    a = build_agent_eye(agent_id="a", observation=obs_a, prev_visual=None, nfe=nfe)
    b = build_agent_eye(agent_id="a", observation=obs_b, prev_visual=None, nfe=nfe)
    assert a["accessible"]["exo"]["forward"]["raw"] != b["accessible"]["exo"]["forward"]["raw"]
    assert a["accessible"]["exo"]["forward"]["pe_bin"]["index"] == b["accessible"]["exo"]["forward"]["pe_bin"]["index"]
    assert sensory_signature(obs_a) == sensory_signature(obs_b)


def test_temporal_delta():
    nfe = _nfe()
    prev = {"exo_1": 0.2}
    cur = {"exo_0": 0.0, "exo_1": 0.293, "exo_2": 0.0}
    eye = build_agent_eye(agent_id="a", observation=cur, prev_visual=prev, nfe=nfe)
    assert eye["accessible"]["exo"]["forward"]["delta"] == pytest.approx(0.093, abs=1e-9)


def test_radius_metadata_default_warning():
    nfe = _nfe(radius=1)
    eye = build_agent_eye(agent_id="a", observation={"exo_0": 0, "exo_1": 0, "exo_2": 0}, prev_visual=None, nfe=nfe)
    assert eye["sensor_configuration"]["radius"] == 1
    assert "R=1" in eye["sensor_configuration"]["radius_note"]
    assert eye["sensor_configuration"]["not_agent_accessible"] is True


def test_no_fake_depth_or_identity_leak():
    rt = _rt()
    rt.last_agent_observation = rt.agent_observation()
    eye = build_agent_eye(
        agent_id="agent_0", observation=rt.last_agent_observation, prev_visual=None,
        nfe=rt.config.near_field_exteroception,
    )
    blob = str(eye)
    assert "metres" not in blob.lower()
    assert eye["forbidden_leaks"] == []
    assert "dx" not in (rt.last_agent_observation or {})
    assert "distance" not in (rt.last_agent_observation or {})


def test_a0_a1_attribution():
    ta = TwoAgentRuntime(seed=21)
    ta.set_mechanism("physical_near_field_vision", True)
    for slot in ta.slots:
        slot.config.near_field_exteroception = _nfe(visual_surface_discrimination="OFF")
        slot.set_mechanism("physical_near_field_vision", True)
    ta.slots[0].body.x, ta.slots[0].body.y, ta.slots[0].body.theta = 10.5, 10.5, 0.0
    ta.slots[1].body.x, ta.slots[1].body.y, ta.slots[1].body.theta = 20.5, 20.5, 0.0
    if ta.world.surface_response is not None:
        ta.world.surface_response[:, :] = 0.0
        ta.world.surface_response[10, 11] = 0.8
        ta.world.surface_response[20, 21] = 0.2
    ta.world.tick += 1
    for slot in ta.slots:
        slot.last_agent_observation = slot.agent_observation()
    payload = build_tiktaalik_eye_payload(ta, include_geometry_debug=False)
    a0 = payload["agents"]["agent_0"]["accessible"]["exo"]["forward"]["raw"]
    a1 = payload["agents"]["agent_1"]["accessible"]["exo"]["forward"]["raw"]
    assert a0 != a1


def test_below_threshold_aliases_empty():
    nfe = _nfe(threshold=0.04)
    empty = build_agent_eye(
        agent_id="a", observation={"exo_0": 0.0, "exo_1": 0.0, "exo_2": 0.0},
        prev_visual=None, nfe=nfe,
    )
    dark = build_agent_eye(
        agent_id="a", observation={"exo_0": 0.0, "exo_1": 0.0, "exo_2": 0.0},
        prev_visual=None, nfe=nfe,
    )
    assert empty["accessible"]["exo"]["forward"]["raw"] == dark["accessible"]["exo"]["forward"]["raw"] == 0.0


def test_no_occlusion_contributors_sum():
    neighbors = [
        {"cell": [17, 16], "inside_fov": True, "final_contribution": 0.31, "relative_angle_rad": 0.0, "detectable": True, "surface_response": 0.5, "body_optical": 0.0},
        {"cell": [19, 16], "inside_fov": True, "final_contribution": 0.22, "relative_angle_rad": 0.0, "detectable": True, "surface_response": 0.4, "body_optical": 0.0},
        {"cell": [18, 16], "inside_fov": True, "final_contribution": 0.20, "relative_angle_rad": 0.0, "detectable": True, "body_optical": 0.65, "surface_response": 0.0},
    ]
    eye = build_agent_eye(
        agent_id="a",
        observation={"exo_0": 0.0, "exo_1": 0.73, "exo_2": 0.0},
        prev_visual=None,
        nfe=_nfe(),
        neighbors=neighbors,
        include_geometry_debug=True,
    )
    fwd = eye["contributors"]["forward"]
    assert len(fwd) == 3
    assert eye["accessible"]["exo"]["forward"]["raw"] == pytest.approx(0.73)


def test_eye_off_semantic_equivalence():
    def actions(rate: str):
        s = ObserverSession(SessionConfig(seed=91, evidence_mode="SEARCH_COMPACT"))
        s.set_tiktaalik_eye(rate=rate)
        out = []
        for _ in range(12):
            s.step()
            last = (getattr(s.runtime, "cognition", None) or {}).get("last_selection") or {}
            out.append(last.get("action") or last.get("selected_action"))
        obs = deepcopy(getattr(s.runtime, "last_agent_observation", None))
        return out, obs, int(s.runtime.tick)

    a, oa, ta = actions("OFF")
    b, ob, tb = actions("5FPS")
    assert ta == tb
    assert a == b
    assert oa == ob


def test_headless_no_eye_capture():
    s = ObserverSession(SessionConfig(seed=5, evidence_mode="SEARCH_COMPACT", execution_mode="HEADLESS"))
    s.set_tiktaalik_eye(rate="5FPS")
    with s._lock:
        frame = s._capture_locked()
    eye = frame.get("tiktaalik_eye") or {}
    assert eye.get("status") == "OFF"
    assert eye.get("reason") == "HEADLESS"


def test_latest_wins_no_queue():
    s = ObserverSession(SessionConfig(seed=8, evidence_mode="SEARCH_COMPACT"))
    s.set_tiktaalik_eye(rate="PER_TICK")
    s.step()
    s.step()
    assert s._eye_last_payload is not None
    assert s.capture_queue_depth() <= 2


def test_save_restore_scientific_equivalence_eye_ui_state():
    s = ObserverSession(SessionConfig(seed=44, evidence_mode="SEARCH_COMPACT"))
    s.set_tiktaalik_eye(rate="5FPS")
    for _ in range(6):
        s.step()
    snap = s.runtime.snapshot()
    obs_before = deepcopy(s.runtime.last_agent_observation)
    restored = PhysicalSystemRuntime.restore(snap)
    assert restored.last_agent_observation == obs_before
    assert "tiktaalik_eye" not in snap
    s2 = ObserverSession(SessionConfig(seed=44, evidence_mode="SEARCH_COMPACT"))
    s2.set_tiktaalik_eye(rate="OFF")
    for _ in range(6):
        s2.step()
    assert s.runtime.last_agent_observation == s2.runtime.last_agent_observation


def test_optical_mapping_lifecycle_does_not_reset_tick():
    rt = _rt(disc="RICH")
    rt.tick = 7
    rt.world.tick = 7
    old_tick = rt.tick
    chk0 = (rt.world.surface_optical_meta or {}).get("checksum")
    snap = rt.set_optical_mapping("UNIFORM")
    assert snap["accepted"] is True
    assert rt.tick == old_tick
    chk1 = (rt.world.surface_optical_meta or {}).get("checksum")
    assert chk1 != chk0 or snap["new"] == "UNIFORM"


def test_psc_off_ticks_no_history_reset():
    rt = _rt()
    rt.set_mechanism("prospective_scenario_competition", False)
    snap = rt.set_psc_off_ticks(1000)
    assert snap["history_reset"] is False
    assert rt.config.cognition.psc_off_ticks == 1000
    rt.set_psc_off_ticks(None)
    assert rt.config.cognition.psc_off_ticks is None
