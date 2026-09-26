"""Beta 3.1 Phase 4 spatial vision. 2D only. No explicit depth."""
from __future__ import annotations

import math

import pytest

from mechanistic_mind.physical_system.near_field_exteroception import (
    NearFieldExteroceptionConfig,
    compact_fpv_receipts,
    sample_near_field,
    spatial_observation_keys,
)
from mechanistic_mind.physical_system.observation import accessible_observation
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_body.config import default_physical_body2_config
from mechanistic_mind.physical_system import sensorimotor_consequence as smc
from experiments.run_beta31_spatial_vision_phase4 import (
    leak_audit,
    run,
    smc_dimension_analysis,
    _rt,
    snf,
)


def test_legacy_no_new_keys():
    rt = _rt(spatial="LEGACY")
    s = snf(rt)
    assert not (s.get("spatial_fragments") or {})
    obs = accessible_observation(
        world=rt.world, body=rt.body, internal=rt.internal,
        planet_config=rt.config.planet, body_config=rt.config.body,
        near_field_cfg=rt.config.near_field_exteroception,
    )
    assert not any(k.startswith("spatial_") for k in obs)
    assert leak_audit(obs)["clean"]


def test_legacy_matches_angular_legacy_bins():
    a = _rt(spatial="LEGACY")
    b = _rt(spatial="ANGULAR")
    sa, sb = snf(a), snf(b)
    assert sa["fragments"] == sb["fragments"]
    assert sa["surface_fragments"] == sb["surface_fragments"]
    assert sb.get("spatial_fragments")


def test_angular_keys_and_no_depth():
    rt = _rt(spatial="ANGULAR")
    keys = spatial_observation_keys(spatial_mode="ANGULAR", discrimination="RICH", n_sectors=5)
    assert "spatial_exo_a0" in keys and "spatial_exo_a4" in keys
    assert len([k for k in keys if k.startswith("spatial_exo")]) == 5
    s = snf(rt)
    for bad in ("depth", "distance", "range_bin", "z"):
        assert bad not in (s.get("spatial_fragments") or {})
        assert bad not in s["fragments"]


def test_occlusion_zeros_farther_same_sector():
    leg = _rt(spatial="LEGACY")
    occ = _rt(spatial="OCCLUSION")
    for rt in (leg, occ):
        rt.world.surface_response[:, :] = 0.05
        rt.world.surface_response[16, 17] = 0.95
        rt.world.surface_response[16, 19] = 0.95
    sl, so = snf(leg), snf(occ)
    assert so.get("n_occluded", 0) >= 1
    assert sl.get("n_occluded", 0) == 0
    rec = compact_fpv_receipts(so)
    assert any(x.get("status") == "occluded" for x in rec["samples"])
    assert rec["feeds_cognition"] is False


def test_head_vs_body_heading():
    rt = _rt(spatial="ANGULAR")
    rt.set_mechanism("articulated_head", True)
    rt.body.theta = 0.0
    a = snf(rt).get("spatial_fragments")
    rt.body.head_relative_angle = 0.9
    b = snf(rt).get("spatial_fragments")
    assert a != b


def test_r_bounds_and_periodic():
    for r in (1, 2, 3):
        rt = _rt(spatial="ANGULAR", radius=r)
        s = snf(rt)
        assert s["vision_radius"] == r
        assert s["n_candidates"] <= (2 * r + 1) ** 2 - 1
    rt = _rt(spatial="ANGULAR")
    rt.body.x, rt.body.y = 0.2, 0.2
    s = snf(rt)
    assert s["n_candidates"] > 0


def test_smc_legacy_count_unchanged():
    dim = smc_dimension_analysis()
    assert dim["legacy_family_default_count"] == 48
    assert dim["old_channel_count"] == 48
    assert dim["new_channel_count_spatial_family_on"] == 68
    assert smc.SIM_THRESHOLD == 0.22


def test_save_restore_spatial_mode():
    rt = _rt(spatial="OCCLUSION")
    payload = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(payload)
    assert rt2.config.near_field_exteroception.spatial_vision_mode == "OCCLUSION"
    assert snf(rt)["fragments"] == snf(rt2)["fragments"]


def test_deterministic_sampling():
    rt = _rt(spatial="TEMPORAL_SPATIAL")
    a = snf(rt)
    b = snf(rt)
    assert a["fragments"] == b["fragments"]
    assert a.get("spatial_fragments") == b.get("spatial_fragments")


def test_phase4_harness_classifications():
    art = run()
    cl = art["classifications"]
    assert cl["WORLD_PHYSICS_DIMENSION"] == "2D"
    assert cl["EXPLICIT_DEPTH_CHANNEL_ADDED"] == "NO"
    assert cl["EXPLICIT_DISTANCE_CHANNEL_ADDED"] == "NO"
    assert cl["SPATIAL_ANGULAR_STRUCTURE_ADDED"] == "YES"
    assert cl["OCCLUSION_ADDED"] == "YES"
    assert cl["TEMPORAL_DERIVATIVE_CHANNELS_ADDED"] == "NO"
    assert art["legacy_angular_exo_equal"] is True
    assert art["leak"]["clean"] is True
    assert cl["SELF_MOTION_PRODUCES_RANGE_DEPENDENT_OPTICAL_TRANSFORMATION"] in {"YES", "NO", "PARTIAL"}
    assert cl["HEAD_MOTION_PRODUCES_SPATIAL_OPTICAL_TRANSFORMATION"] in {"YES", "NO", "PARTIAL"}
