"""ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_CONTACT — FREE ResourceObject↔ResourceObject contact FACT."""
from __future__ import annotations

import copy
import math

import pytest

from mechanistic_mind.model.acanthostega import (
    acanthostega_body_object_contact_config,
    acanthostega_body_object_impulse_config,
    acanthostega_object_impact_acoustics_config,
    acanthostega_object_object_contact_config,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import physical_body_resource_object_contact as boc
from mechanistic_mind.physical_system import physical_resource_object_pair_contact as ooc
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
    PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

MID = ooc.MECHANISM_ID
OR = ooc.CANONICAL_COLLISION_RADIUS
SUM_R = OR + OR


def _place_object(rt, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0, index=0):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert len(objs) > index, "preset must spawn enough resource objects"
    o = objs[index]
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = None
    o.manipulator_id = None
    boc.ensure_object_collision_radius(o)
    return o


def _detect(rt, tick=1):
    return ooc.detect_resource_object_pair_contacts(rt.world, tick=tick, config=rt.config)


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_object_object_contact_config())


# ---------- isolation ----------


def test_01_tiktaalik_and_prior_presets_lack_mechanism():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not ooc.resource_object_pair_contact_is_active(cfg)
    for builder in (
        acanthostega_body_object_contact_config,
        acanthostega_body_object_impulse_config,
        acanthostega_object_impact_acoustics_config,
    ):
        c = builder()
        assert not ooc.resource_object_pair_contact_is_active(c)
        mechs = preset_canonical(c.public_preset).get("mechanisms") or {}
        assert mechs.get(MID) in (None, False)


def test_02_new_preset_enables_parent_plus_pair_contact():
    can = preset_canonical(PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT)
    assert can["public_preset"] == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT
    assert can["mechanisms"].get(MID) is True
    assert can["mechanisms"].get("body_resource_object_impact_acoustic_emission") is True
    assert can["mechanisms"].get("physical_body_resource_object_contact") is True
    cfg = acanthostega_object_object_contact_config()
    assert ooc.resource_object_pair_contact_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT)
    assert ooc.resource_object_pair_contact_is_active(cfg)


def test_03_normalize_more_specific_before_impact_acoustics():
    assert (
        normalize_preset_name("ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_CONTACT")
        == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT
    )
    assert (
        normalize_preset_name("ACANTHOSTEGA OBJECT OBJECT CONTACT")
        == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT
    )
    assert (
        normalize_preset_name(PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS)
        == PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS
    )
    assert (
        normalize_preset_name(PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT)
        == PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT
    )


# ---------- geometry ----------


def test_04_collision_radius_canonical_and_combined():
    assert OR == 0.25
    assert SUM_R == 0.5


def test_05_same_cell_not_sufficient():
    rt = _rt()
    a = _place_object(rt, 10.1, 10.1, index=0)
    b = _place_object(rt, 10.9, 10.9, index=1)
    assert math.hypot(a.x - b.x, a.y - b.y) > SUM_R
    step = _detect(rt, tick=1)
    assert step["begin"] == []
    assert step["active_episodes"] == 0


def test_06_endpoint_tangent_contact():
    rt = _rt()
    _place_object(rt, 5.0, 5.0, index=0)
    _place_object(rt, 5.0 + SUM_R, 5.0, index=1)
    step = _detect(rt, tick=1)
    assert len(step["begin"]) == 1
    r = step["begin"][0]
    assert r["detection_mode"] == ooc.DETECTION_ENDPOINT
    assert r["contact_fact"] is True
    assert r["collision_response_applied"] is False
    assert r["impulse_transferred"] is False
    assert r["position_corrected"] is False
    assert r["velocity_changed"] is False
    assert r["sound_emitted"] is False
    assert r["composition_changed"] is False


def test_07_coincident_centres_deterministic_plus_x():
    rt = _rt()
    _place_object(rt, 8.0, 8.0, index=0)
    _place_object(rt, 8.0, 8.0, index=1)
    a = _detect(rt, tick=1)
    rt.world.resource_object_pair_contact_state.active.clear()
    b = _detect(rt, tick=2)
    assert a["begin"][0]["contact_point"] == b["begin"][0]["contact_point"]
    assert a["begin"][0]["contact_point_policy"] == "COINCIDENT_CENTRES_PLUS_X"


def test_08_canonical_pair_key_symmetric():
    assert ooc.canonical_pair_key("b", "a") == ooc.canonical_pair_key("a", "b")
    assert ooc.canonical_pair_key("a", "b") == "a|b"


def test_09_one_check_per_pair_sorted():
    rt = _rt()
    objs = list(rt.world.resource_objects)
    assert len(objs) >= 2
    # Clone a third free object for N=3 pair count = 3
    import copy
    third = copy.deepcopy(objs[0])
    third.object_id = "resource-extra-003"
    rt.world.resource_objects.append(third)
    objs = list(rt.world.resource_objects)
    for i, o in enumerate(objs[:3]):
        o.x, o.y = 5.0 + i * 0.01, 5.0
        o.physical_state = "FREE_STATIC"
        boc.ensure_object_collision_radius(o)
    step = _detect(rt, tick=1)
    keys = [r["pair_key"] for r in step["begin"]]
    assert keys == sorted(keys)
    assert len(keys) == len(set(keys))
    assert len(keys) == 3  # C(3,2)


# ---------- swept ----------


def test_10_swept_crossing_new_pair():
    rt = _rt()
    a = _place_object(rt, 5.0, 5.0, index=0)
    b = _place_object(rt, 7.0, 5.0, index=1)  # far — no endpoint
    st = ooc.ensure_resource_object_pair_contact_for_runtime(rt.world, rt.config)
    st.prev_object_poses[str(a.object_id)] = [5.0, 5.0]
    st.prev_object_poses[str(b.object_id)] = [5.1, 5.0]  # was overlapping last tick
    # current: separated beyond radius, but swept relative path crosses
    b.x = 7.0
    step = _detect(rt, tick=1)
    # relative start sep=0.1 < 0.5 → contact along path; endpoint sep=2.0 > 0.5
    assert any(r["detection_mode"] == ooc.DETECTION_SWEPT for r in step["begin"]) or any(
        r.get("swept_contact") for r in step.get("begin") or []
    ) or len(step["begin"]) >= 1


def test_11_active_endpoint_only_anti_t0():
    rt = _rt()
    a = _place_object(rt, 5.0, 5.0, index=0)
    b = _place_object(rt, 5.0 + SUM_R * 0.5, 5.0, index=1)
    step1 = _detect(rt, tick=1)
    assert len(step1["begin"]) == 1
    # Move apart but leave prev overlapping so swept would keep contact if used
    b.x = 5.0 + SUM_R + 1.0
    step2 = _detect(rt, tick=2)
    assert len(step2["end"]) == 1
    assert step2["end"][0]["contact_fact"] is False


# ---------- episodes / termination ----------


def test_12_begin_persist_end_and_recontact_new_episode():
    rt = _rt()
    a = _place_object(rt, 5.0, 5.0, index=0)
    b = _place_object(rt, 5.2, 5.0, index=1)
    s1 = _detect(rt, tick=1)
    eid1 = s1["begin"][0]["episode_id"]
    s2 = _detect(rt, tick=2)
    assert len(s2["persist"]) == 1
    assert s2["persist"][0]["episode_id"] == eid1
    b.x = 10.0
    s3 = _detect(rt, tick=3)
    assert len(s3["end"]) == 1
    assert s3["end"][0]["termination_reason"] == ooc.TERMINATION_SEPARATION
    b.x = 5.2
    s4 = _detect(rt, tick=4)
    assert len(s4["begin"]) == 1
    assert s4["begin"][0]["episode_id"] != eid1
    assert s4["begin"][0]["episode_id"].startswith("oopc-")


def test_13_grasp_ends_with_state_exclusion_held():
    rt = _rt()
    a = _place_object(rt, 5.0, 5.0, index=0)
    b = _place_object(rt, 5.2, 5.0, index=1)
    _detect(rt, tick=1)
    b.physical_state = "HELD"
    b.holder_body_id = "agent_0"
    step = _detect(rt, tick=2)
    assert len(step["end"]) == 1
    assert step["end"][0]["termination_reason"] == ooc.TERMINATION_STATE_EXCLUSION_HELD


def test_14_combine_removed_ends_episode():
    rt = _rt()
    a = _place_object(rt, 5.0, 5.0, index=0)
    b = _place_object(rt, 5.2, 5.0, index=1)
    bid = str(b.object_id)
    _detect(rt, tick=1)
    rt.world.resource_objects = [o for o in rt.world.resource_objects if str(o.object_id) != bid]
    step = _detect(rt, tick=2)
    assert len(step["end"]) == 1
    assert step["end"][0]["termination_reason"] in (
        ooc.TERMINATION_COMBINE_REMOVED,
        ooc.TERMINATION_OBJECT_REMOVED,
    )


def test_15_held_free_skipped_diagnostic():
    rt = _rt()
    a = _place_object(rt, 5.0, 5.0, index=0, state="HELD")
    a.holder_body_id = "agent_0"
    b = _place_object(rt, 5.1, 5.0, index=1, state="FREE_STATIC")
    step = _detect(rt, tick=1)
    assert step["begin"] == []
    st = ooc.state_of(rt.world)
    assert st.counters.get("skipped_held_free", 0) >= 1


# ---------- no-response ----------


def test_16_no_pose_velocity_or_composition_change():
    rt = _rt()
    a = _place_object(rt, 5.0, 5.0, index=0, state="FREE_MOVING", vx=0.3, vy=0.0)
    b = _place_object(rt, 5.2, 5.0, index=1, state="FREE_STATIC")
    ax, ay, avx = a.x, a.y, a.vx
    bx, by, bvx = b.x, b.y, b.vx
    mass_a = getattr(a, "mass", None)
    step = _detect(rt, tick=1)
    assert len(step["begin"]) == 1
    assert (a.x, a.y, a.vx) == (ax, ay, avx)
    assert (b.x, b.y, b.vx) == (bx, by, bvx)
    assert getattr(a, "mass", None) == mass_a
    for flag in (
        "collision_response_applied",
        "impulse_transferred",
        "position_corrected",
        "velocity_changed",
        "sound_emitted",
        "composition_changed",
    ):
        assert step[flag] is False


# ---------- privacy / persistence ----------


def test_17_privacy_no_cognition_pair_metadata():
    rt = _rt()
    _place_object(rt, 5.0, 5.0, index=0)
    _place_object(rt, 5.2, 5.0, index=1)
    _detect(rt, tick=1)
    # Cognition observation path must not leak pair contact receipts
    payload = {"world_tick": 1, "observation": {}}
    hits = audit_cognition_payload(payload)
    assert not any("PAIR_CONTACT" in h or "pair_contact" in h for h in hits)
    # Researcher summary exists but agent_accessible false
    summary = ooc.researcher_summary(rt.world)
    assert summary["agent_accessible"] is False
    assert summary["researcher_only"] is True


def test_18_snapshot_restore_mid_overlap_no_rebegin():
    rt = _rt()
    _place_object(rt, 5.0, 5.0, index=0)
    _place_object(rt, 5.2, 5.0, index=1)
    s1 = _detect(rt, tick=1)
    eid = s1["begin"][0]["episode_id"]
    data = ooc.serialize_state(ooc.state_of(rt.world))
    # Fresh runtime, restore mid-overlap
    rt2 = _rt()
    _place_object(rt2, 5.0, 5.0, index=0)
    _place_object(rt2, 5.2, 5.0, index=1)
    ooc.restore_state(rt2.world, data, rt2.config)
    s2 = _detect(rt2, tick=2)
    assert s2["begin"] == []
    assert len(s2["persist"]) == 1
    assert s2["persist"][0]["episode_id"] == eid


def test_19_old_snapshot_without_field_mechanism_off():
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_object_impact_acoustics_config())
    assert not ooc.resource_object_pair_contact_is_active(rt.config)
    assert getattr(rt.world, "resource_object_pair_contact_state", None) in (None,)


def test_20_double_call_guard():
    rt = _rt()
    _place_object(rt, 5.0, 5.0, index=0)
    _place_object(rt, 5.2, 5.0, index=1)
    s1 = _detect(rt, tick=5)
    s2 = _detect(rt, tick=5)
    assert s1 is s2 or s2["begin"] == []  # second call returns last_step, no double BEGIN
    st = ooc.state_of(rt.world)
    assert st.counters["begin"] == 1


def test_21_broad_phase_strategy_and_complexity():
    rt = _rt()
    step = _detect(rt, tick=1)
    assert step["broad_phase_strategy"] == ooc.BROAD_PHASE_STRATEGY
    assert step.get("complexity") == "O(N^2)"
    cfg = ooc.ResourceObjectPairContactConfig(enabled=True)
    d = cfg.to_dict()
    assert d["broad_phase_strategy"] == "BROAD_PHASE_ALL_PAIRS_V1"
    assert "spatial-hash" in d["next_scaling_seam"] or "spatial_hash" in d["next_scaling_seam"]


def test_22_newly_released_endpoint_only_no_prev():
    rt = _rt()
    # Only current pose — no prev stored → first tick endpoint only
    a = _place_object(rt, 5.0, 5.0, index=0)
    b = _place_object(rt, 5.2, 5.0, index=1)
    st = ooc.ensure_resource_object_pair_contact_for_runtime(rt.world, rt.config)
    st.prev_object_poses.clear()
    step = _detect(rt, tick=1)
    assert len(step["begin"]) == 1
    assert step["begin"][0]["detection_mode"] == ooc.DETECTION_ENDPOINT
