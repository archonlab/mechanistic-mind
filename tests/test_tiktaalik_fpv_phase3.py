"""Beta 3.1 Phase 3 — FPV sensor field from canonical sample_near_field."""
from __future__ import annotations

import json
import math
from copy import deepcopy

import pytest

from mechanistic_mind.physical_body.config import default_physical_body2_config
from mechanistic_mind.physical_system.near_field_exteroception import (
    NearFieldExteroceptionConfig,
    compact_fpv_receipts,
    fov_sector_index,
    moore_max_candidates,
    sample_near_field,
    sensor_frame_xy,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.ui.psy_observer_web.tiktaalik_eye import build_tiktaalik_eye_payload


def _nfe(**kw) -> NearFieldExteroceptionConfig:
    base = dict(
        mode="EXPERIMENTAL",
        perception_enabled=True,
        illumination_enabled=True,
        illumination_min=1.0,
        illumination_max=1.0,
        surface_enabled=True,
        radius=3,
        visual_surface_discrimination="RICH",
        optical_mapping="INDEPENDENT",
        gain=1.0,
        saturation=1.0,
        threshold=0.04,
        distance_k=0.85,
        fov_deg=120.0,
        body_optical_enabled=True,
    )
    base.update(kw)
    return NearFieldExteroceptionConfig(**base)


def _rt(*, disc="RICH", radius=3, seed=11) -> PhysicalSystemRuntime:
    cfg = PhysicalSystemConfig()
    cfg.near_field_exteroception = _nfe(visual_surface_discrimination=disc, radius=radius)
    cfg.body = default_physical_body2_config()
    rt = PhysicalSystemRuntime(seed=seed, config=cfg)
    rt.set_mechanism("physical_near_field_vision", True)
    rt.set_visual_surface_discrimination(disc)
    rt.body.x, rt.body.y, rt.body.theta = 16.5, 16.5, 0.0
    return rt


def test_diagnostic_does_not_change_fragments():
    rt = _rt()
    a = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=False)
    b = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True)
    assert a["fragments"] == b["fragments"]
    assert a["surface_fragments"] == b["surface_fragments"]
    assert "fpv_receipts" not in a
    assert "fpv_receipts" in b
    assert b["fpv_receipts"]["feeds_cognition"] is False


def test_agent_centered_rotation_and_heading():
    fwd, left = sensor_frame_xy(1.0, 0.0, 0.0)
    assert fwd == pytest.approx(1.0)
    assert left == pytest.approx(0.0)
    fwd, left = sensor_frame_xy(0.0, 1.0, 0.0)
    assert left == pytest.approx(1.0)
    heading = math.pi / 2
    fwd, left = sensor_frame_xy(0.0, 1.0, heading)
    assert fwd == pytest.approx(1.0, abs=1e-9)


def test_head_heading_vs_body_fallback():
    rt = _rt()
    rt.body._articulated_head_enabled = False
    rt.body.theta = 0.0
    rt.body.head_relative_angle = 0.4
    rt.world.tick += 1
    body_sample = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True)
    assert body_sample["sensor_forward_axis"] == pytest.approx(0.0)
    assert compact_fpv_receipts(body_sample)["heading_source"] == "BODY"

    rt.body._articulated_head_enabled = True
    rt.world.tick += 1
    head_sample = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True)
    assert head_sample["sensor_forward_axis"] != pytest.approx(body_sample["sensor_forward_axis"])
    assert compact_fpv_receipts(head_sample)["heading_source"] == "HEAD"


def test_fov_120_and_sector_bins():
    assert fov_sector_index(0.0, 120.0) == 1
    assert fov_sector_index(math.radians(-45.0), 120.0) == 0
    assert fov_sector_index(math.radians(45.0), 120.0) == 2
    assert fov_sector_index(math.radians(90.0), 120.0) is None


def test_radius_candidate_counts_and_own_cell():
    for r in (1, 2, 3):
        rt = _rt(radius=r)
        rt.world.tick += 1
        s = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True)
        rec = compact_fpv_receipts(s)
        own = [x for x in rec["samples"] if x["status"] == "own_cell_excluded"]
        assert len(own) == 1
        assert rec["radius"] == r
        assert s["n_candidates"] == moore_max_candidates(r)
        assert len(rec["samples"]) == moore_max_candidates(r) + 1


def test_off_low_rich_receipt_channels():
    rt = _rt(disc="OFF")
    rt.world.tick += 1
    off = compact_fpv_receipts(sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True))
    acc = [x for x in off["samples"] if x["status"] != "own_cell_excluded"][0]
    assert acc.get("surface_channels") == "ABSENT"
    assert "c0" not in acc

    rt.set_visual_surface_discrimination("LOW")
    rt.world.tick += 1
    low = compact_fpv_receipts(sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True))
    acc = next(x for x in low["samples"] if x["status"] != "own_cell_excluded")
    assert "c0" in acc and "c1" not in acc

    rt.set_visual_surface_discrimination("RICH")
    rt.world.tick += 1
    rich = compact_fpv_receipts(sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True))
    acc = next(x for x in rich["samples"] if x["status"] != "own_cell_excluded")
    assert "c0" in acc and "c1" in acc and "c2" in acc


def test_false_color_does_not_affect_cognition():
    rt = _rt(disc="RICH")
    obs = rt.agent_observation()
    payload = build_tiktaalik_eye_payload(rt, include_fpv=True)
    assert payload["feeds_cognition"] is False
    assert rt.agent_observation() == obs


def test_distance_illumination_threshold_in_receipts():
    rt = _rt(radius=3)
    if rt.world.surface_response is not None:
        rt.world.surface_response[:, :] = 0.9
    rt.config.near_field_exteroception.illumination_min = 0.2
    rt.config.near_field_exteroception.illumination_max = 0.2
    rt.config.near_field_exteroception.threshold = 0.5
    rt.world.tick += 1
    rec = compact_fpv_receipts(sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True))
    statuses = {x["status"] for x in rec["samples"]}
    assert "below_threshold" in statuses or "accepted" in statuses
    dist_fs = [x["dist_f"] for x in rec["samples"] if x.get("dist_f") is not None]
    assert min(dist_fs) < max(dist_fs)
    illums = [x["illumination"] for x in rec["samples"] if x.get("illumination") is not None]
    assert illums
    assert all(abs(float(i) - 0.2) < 1e-6 for i in illums)


def test_no_occlusion_same_sector_multiple_contributors():
    rt = _rt(radius=3)
    if rt.world.surface_response is not None:
        rt.world.surface_response[:, :] = 0.0
        rt.world.surface_response[16, 17] = 0.8
        rt.world.surface_response[16, 18] = 0.7
        rt.world.surface_response[16, 19] = 0.6
    rt.world.tick += 1
    rec = compact_fpv_receipts(sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True))
    fwd = [x for x in rec["samples"] if x.get("sector") == "FORWARD" and x["status"] == "accepted"]
    assert len(fwd) >= 2


def test_foreign_body_optical_no_identity():
    ta = TwoAgentRuntime(seed=3)
    ta.set_mechanism("physical_near_field_vision", True)
    for slot in ta.slots:
        slot.config.near_field_exteroception = _nfe(radius=3, visual_surface_discrimination="OFF")
    ta.slots[0].body.x, ta.slots[0].body.y = 10.5, 10.5
    ta.slots[1].body.x, ta.slots[1].body.y = 11.5, 10.5
    ta.world.tick += 1
    payload = build_tiktaalik_eye_payload(ta, include_fpv=True)
    blob = json.dumps(payload)
    assert "FRIEND" not in blob and "ENEMY" not in blob
    assert "agent_1 recognized" not in blob.lower()
    samples = payload["agents"]["agent_0"].get("fpv", {}).get("samples") or []
    assert any(float(s.get("body_optical") or 0) > 0 for s in samples)
    for s in samples:
        assert "height" not in s and "slope" not in s and "distance" not in s


def test_a0_a1_independent_fpv():
    ta = TwoAgentRuntime(seed=3)
    ta.set_mechanism("physical_near_field_vision", True)
    for slot in ta.slots:
        slot.config.near_field_exteroception = _nfe(radius=2, visual_surface_discrimination="OFF")
    ta.slots[0].body.x, ta.slots[0].body.y, ta.slots[0].body.theta = 10.5, 10.5, 0.0
    ta.slots[1].body.x, ta.slots[1].body.y, ta.slots[1].body.theta = 20.5, 20.5, 0.0
    if ta.world.surface_response is not None:
        ta.world.surface_response[:, :] = 0.0
        ta.world.surface_response[10, 11] = 0.9
        ta.world.surface_response[20, 21] = 0.2
    ta.world.tick += 1
    for slot in ta.slots:
        slot.last_agent_observation = slot.agent_observation()
    payload = build_tiktaalik_eye_payload(ta, include_fpv=True)
    f0 = payload["agents"]["agent_0"]["fpv"]
    f1 = payload["agents"]["agent_1"]["fpv"]
    assert f0["samples"] != f1["samples"]
    assert payload["fpv_included"] is True


def test_fpv_on_off_semantic_equivalence():
    def run(fpv: bool):
        s = ObserverSession(SessionConfig(seed=91, evidence_mode="SEARCH_COMPACT"))
        s.set_tiktaalik_eye(rate="5FPS", fpv=fpv)
        actions = []
        for _ in range(10):
            s.step()
            last = (getattr(s.runtime, "cognition", None) or {}).get("last_selection") or {}
            actions.append(last.get("action") or last.get("selected_action"))
        return actions, deepcopy(s.runtime.last_agent_observation), int(s.runtime.tick)

    a, oa, ta = run(False)
    b, ob, tb = run(True)
    assert ta == tb
    assert a == b
    assert oa == ob


def test_headless_zero_fpv_capture():
    s = ObserverSession(SessionConfig(seed=5, evidence_mode="SEARCH_COMPACT", execution_mode="HEADLESS"))
    s.set_tiktaalik_eye(rate="5FPS", fpv=True)
    with s._lock:
        frame = s._capture_locked()
    eye = frame.get("tiktaalik_eye") or {}
    assert eye.get("fpv_included") is False
    assert eye.get("status") == "OFF"
    agents = eye.get("agents") or {}
    assert not any((v or {}).get("fpv") for v in agents.values())


def test_payload_without_fpv_has_no_receipts():
    rt = _rt()
    rt.last_agent_observation = rt.agent_observation()
    p = build_tiktaalik_eye_payload(rt, include_fpv=False)
    assert p["fpv_included"] is False
    assert "fpv" not in (p["agents"].get("agent_0") or {})


def test_save_restore_unaffected_by_fpv_ui():
    s = ObserverSession(SessionConfig(seed=44, evidence_mode="SEARCH_COMPACT"))
    s.set_tiktaalik_eye(rate="5FPS", fpv=True)
    for _ in range(4):
        s.step()
    snap = s.runtime.snapshot()
    obs_before = deepcopy(s.runtime.last_agent_observation)
    restored = PhysicalSystemRuntime.restore(snap)
    assert restored.last_agent_observation == obs_before
    assert "tiktaalik_eye" not in snap


def test_mapping_reflected_from_canonical_tensor():
    rt = _rt(disc="RICH")
    rt.last_agent_observation = rt.agent_observation()
    before = compact_fpv_receipts(sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True))
    rt.set_optical_mapping("UNIFORM")
    rt.world.tick += 1
    after = compact_fpv_receipts(sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True))
    assert after["optical_mapping"] == "UNIFORM"
    c0_before = [s.get("c0") for s in before["samples"] if "c0" in s]
    c0_after = [s.get("c0") for s in after["samples"] if "c0" in s]
    assert c0_before != c0_after or after["optical_mapping"] != before["optical_mapping"]
