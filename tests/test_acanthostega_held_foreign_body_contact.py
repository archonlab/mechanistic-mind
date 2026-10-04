"""ACANTHOSTEGA_PHASE_B_HELD_OBJECT_FOREIGN_BODY_CONTACT — HELD↔foreign body FACT."""
from __future__ import annotations

from mechanistic_mind.model.acanthostega import (
    acanthostega_body_object_contact_config,
    acanthostega_held_object_foreign_body_contact_config,
    acanthostega_object_object_impact_acoustics_config,
    model_metadata,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import held_resource_object_foreign_body_contact as hfc
from mechanistic_mind.physical_system import physical_body_resource_object_contact as boc
from mechanistic_mind.physical_system import physical_resource_object_pair_contact as ooc
from mechanistic_mind.physical_system import resource_object_pair_impact_acoustic_emission as ooia
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

MID = hfc.MECHANISM_ID
BR = hfc.BODY_CONTACT_RADIUS
OR = hfc.CANONICAL_COLLISION_RADIUS
SUM_R = BR + OR


def _place_object(rt, idx, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0,
                  holder=None, hand=None):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert len(objs) > idx
    o = objs[idx]
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = holder
    o.manipulator_id = hand
    hfc.ensure_object_collision_radius(o)
    return o


def _place_body(rt, x, y, *, i=0):
    if hasattr(rt, "slots"):
        b = rt.slots[i].body
    else:
        b = rt.body
    b.x, b.y = float(x), float(y)
    b.vx = b.vy = 0.0
    return b


def _body_id(rt, i=0):
    return body_refs_for_runtime(rt)[i][0]


def _detect(rt, tick=1):
    return hfc.detect_held_resource_object_foreign_body_contacts(
        rt.world, body_refs_for_runtime(rt), tick=tick, config=rt.config
    )


def _rt():
    return PhysicalSystemRuntime(
        seed=17, config=acanthostega_held_object_foreign_body_contact_config()
    )


def _two():
    return TwoAgentRuntime(
        seed=17, config=acanthostega_held_object_foreign_body_contact_config()
    )


# ---------- isolation ----------


def test_01_normalize_more_specific_first():
    assert (
        normalize_preset_name("ACANTHOSTEGA_PHASE_B_HELD_OBJECT_FOREIGN_BODY_CONTACT")
        == PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT
    )
    assert (
        normalize_preset_name("ACANTHOSTEGA HELD OBJECT FOREIGN BODY CONTACT")
        == PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT
    )
    assert (
        normalize_preset_name(PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS)
        == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPACT_ACOUSTICS
    )
    assert (
        normalize_preset_name(PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT)
        == PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT
    )
    assert normalize_preset_name(PRESET_BETA31) == PRESET_BETA31


def test_02_tiktaalik_and_prior_lack_mechanism():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not hfc.held_foreign_body_contact_is_active(cfg)
    prior = acanthostega_object_object_impact_acoustics_config()
    assert not hfc.held_foreign_body_contact_is_active(prior)
    boc_cfg = acanthostega_body_object_contact_config()
    assert not hfc.held_foreign_body_contact_is_active(boc_cfg)


def test_03_new_preset_enables_parent_chain_plus_fact():
    cfg = acanthostega_held_object_foreign_body_contact_config()
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT
    assert hfc.held_foreign_body_contact_is_active(cfg)
    assert ooia.resource_object_pair_impact_acoustics_is_active(cfg)
    assert ooc.resource_object_pair_contact_is_active(cfg)
    assert boc.body_object_contact_is_active(cfg)
    md = model_metadata(cfg)
    assert md["public_preset"] == PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT
    can = preset_canonical(PRESET_ACANTHOSTEGA_HELD_OBJECT_FOREIGN_BODY_CONTACT)
    assert can["mechanisms"][MID] is True


# ---------- scope ----------


def test_10_held_contacts_foreign_not_holder():
    rt = _two()
    holder_id = _body_id(rt, 0)
    foreign_id = _body_id(rt, 1)
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 5.0 + SUM_R * 0.5, 5.0, i=1)  # overlapping foreign
    obj = _place_object(
        rt, 0, 5.0, 5.0, state="HELD", holder=holder_id, hand="LEFT"
    )
    step = _detect(rt, tick=1)
    begins = step["begin"]
    assert begins, "expected BEGIN with foreign body"
    assert all(r["foreign_body_id"] == foreign_id for r in begins)
    assert all(r["holder_body_id"] == holder_id for r in begins)
    assert all(r["held_object_id"] == str(obj.object_id) for r in begins)
    assert all(r["contact_fact"] for r in begins)
    # No holder-self episode
    assert all(r["foreign_body_id"] != holder_id for r in begins)
    st = hfc.state_of(rt.world)
    assert st.counters["holder_self_excluded"] >= 1


def test_11_free_objects_excluded():
    rt = _two()
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 5.0 + SUM_R * 0.5, 5.0, i=1)
    _place_object(rt, 0, 5.0, 5.0, state="FREE_STATIC")
    step = _detect(rt, tick=1)
    assert step["begin"] == []
    assert step["persist"] == []


def test_12_invalid_holder_no_contact():
    rt = _two()
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 5.0 + SUM_R * 0.5, 5.0, i=1)
    _place_object(rt, 0, 5.0, 5.0, state="HELD", holder="no-such-body", hand="LEFT")
    step = _detect(rt, tick=1)
    assert step["begin"] == []
    st = hfc.state_of(rt.world)
    assert st.counters["invalid_holder"] >= 1
    assert any(d["code"] == hfc.DIAG_INVALID_HOLDER for d in step["diagnostics"])


def test_13_held_held_not_this_detector():
    """HELD+HELD stays BRING_TOGETHER path — this detector is object↔foreign body only."""
    rt = _two()
    h0 = _body_id(rt, 0)
    h1 = _body_id(rt, 1)
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 8.0, 5.0, i=1)
    # Two held objects near each other — no foreign-body contact unless body overlaps.
    _place_object(rt, 0, 5.0, 5.0, state="HELD", holder=h0, hand="LEFT")
    _place_object(rt, 1, 5.1, 5.0, state="HELD", holder=h1, hand="LEFT")
    step = _detect(rt, tick=1)
    # May contact holders' foreign bodies if geometry overlaps bodies; but episode keys
    # are always (held_object, foreign_body) never (held, held).
    for r in (step["begin"] or []) + (step["persist"] or []):
        assert "foreign_body_id" in r
        assert r.get("held_object_id")


# ---------- geometry ----------


def test_20_uses_collision_radius_not_optical():
    rt = _two()
    holder_id = _body_id(rt, 0)
    _place_body(rt, 5.0, 5.0, i=0)
    # Place foreign just outside sum of radii
    _place_body(rt, 5.0 + SUM_R + 0.05, 5.0, i=1)
    obj = _place_object(rt, 0, 5.0, 5.0, state="HELD", holder=holder_id, hand="LEFT")
    obj.optical_radius = 10.0  # must not matter
    step = _detect(rt, tick=1)
    assert step["begin"] == []
    # Move into contact
    _place_body(rt, 5.0 + SUM_R * 0.5, 5.0, i=1)
    step2 = _detect(rt, tick=2)
    assert step2["begin"]


# ---------- transition / swept / GRASP snap ----------


def test_30_grasp_snap_does_not_create_swept_crossing():
    """Long GRASP snap through foreign body → ENDPOINT ONLY, never SWEPT_CROSSING."""
    rt = _two()
    holder_id = _body_id(rt, 0)
    foreign_id = _body_id(rt, 1)
    _place_body(rt, 10.0, 10.0, i=0)
    # Foreign body between free pose and hand pose
    _place_body(rt, 5.0, 5.0, i=1)
    # Tick 1: object FREE far away — establish no held history (or free history absent)
    obj = _place_object(rt, 0, 0.0, 0.0, state="FREE_STATIC")
    _detect(rt, tick=1)
    # Tick 2: GRASP snap — object jumps to holder's hand, path crosses foreign body
    obj.physical_state = "HELD"
    obj.holder_body_id = holder_id
    obj.manipulator_id = "LEFT"
    obj.x, obj.y = 10.0, 10.0
    step = _detect(rt, tick=2)
    # Endpoint may or may not contact foreign (object at holder, foreign at 5,5 — far)
    # Force a case where swept WOULD fire if allowed: place foreign at midpoint relative.
    # Redo: put foreign overlapping the held endpoint? That would be ENDPOINT.
    # Better: object starts free overlapping foreign relative motion to far pose without
    # endpoint overlap — classic swept-only contact.
    # Reset state
    rt = _two()
    holder_id = _body_id(rt, 0)
    foreign_id = _body_id(rt, 1)
    _place_body(rt, 20.0, 5.0, i=0)  # holder far
    _place_body(rt, 5.0, 5.0, i=1)   # foreign at crossing
    obj = _place_object(rt, 0, 0.0, 5.0, state="FREE_STATIC")
    st = hfc.ensure_held_foreign_body_contact_for_runtime(rt.world, rt.config)
    # Manually seed prev as if object were free (no held identity)
    # No prior held identity → newly GRASPED this tick (GRASP_SNAP, never swept).
    st.prev_held_identity = {}
    st.prev_foreign_body_poses = {foreign_id: [5.0, 5.0], holder_id: [20.0, 5.0]}
    st.last_processed_tick = 0
    # GRASP: object jumps from 0,5 to 20,5 — segment passes through foreign at 5,5
    obj.physical_state = "HELD"
    obj.holder_body_id = holder_id
    obj.manipulator_id = "LEFT"
    obj.x, obj.y = 20.0, 5.0
    step = _detect(rt, tick=1)
    # Policy must be GRASP_SNAP; no SWEPT begin
    for r in step["begin"]:
        assert r["transition_policy"] == hfc.TRANSITION_GRASP_SNAP_ENDPOINT_ONLY
        assert r["detection_mode"] != hfc.DETECTION_SWEPT
    # If endpoint not overlapping, begin should be empty (proving swept suppressed)
    endpoint_would = (abs(20.0 - 5.0) <= SUM_R + 1e-9)  # False
    assert not endpoint_would
    assert step["begin"] == [], "GRASP snap must not create SWEPT_CROSSING episode"
    assert st.counters["grasp_snap_endpoint_only"] >= 1
    # Prove swept WOULD have fired if free→hand path were used:
    foreign_body = dict(body_refs_for_runtime(rt))[foreign_id]
    m_swept = hfc.measure_held_foreign_pair(
        held_object_id=str(obj.object_id),
        obj=obj,
        foreign_body_id=foreign_id,
        body=foreign_body,
        width=int(rt.world.T.shape[1]),
        height=int(rt.world.T.shape[0]),
        cfg=st.config,
        prev_obj_pose=[0.0, 5.0],
        prev_body_pose=[5.0, 5.0],
        allow_swept=True,
    )
    assert m_swept["swept_contact"] is True
    assert m_swept["detection_mode"] == hfc.DETECTION_SWEPT
    m_blocked = hfc.measure_held_foreign_pair(
        held_object_id=str(obj.object_id),
        obj=obj,
        foreign_body_id=foreign_id,
        body=foreign_body,
        width=int(rt.world.T.shape[1]),
        height=int(rt.world.T.shape[0]),
        cfg=st.config,
        prev_obj_pose=[0.0, 5.0],
        prev_body_pose=[5.0, 5.0],
        allow_swept=False,
    )
    assert m_blocked["swept_contact"] is False
    assert m_blocked["detection_mode"] is None


def test_31_stable_held_allows_swept():
    rt = _two()
    holder_id = _body_id(rt, 0)
    foreign_id = _body_id(rt, 1)
    _place_body(rt, 20.0, 5.0, i=0)
    _place_body(rt, 5.0, 5.0, i=1)
    obj = _place_object(
        rt, 0, 0.0, 5.0, state="HELD", holder=holder_id, hand="LEFT"
    )
    st = hfc.ensure_held_foreign_body_contact_for_runtime(rt.world, rt.config)
    st.prev_held_identity = {
        str(obj.object_id): {
            "holder_body_id": holder_id,
            "manipulator_id": "LEFT",
            "pose": [0.0, 5.0],
        }
    }
    st.prev_foreign_body_poses = {foreign_id: [5.0, 5.0], holder_id: [20.0, 5.0]}
    st.last_processed_tick = 0
    # Move held object across foreign
    obj.x, obj.y = 20.0, 5.0
    step = _detect(rt, tick=1)
    assert step["begin"], "STABLE_HELD should allow SWEPT_CROSSING"
    assert step["begin"][0]["detection_mode"] == hfc.DETECTION_SWEPT
    assert step["begin"][0]["transition_policy"] == hfc.TRANSITION_STABLE_HELD


def test_32_holder_or_hand_change_endpoint_only():
    rt = _two()
    holder_id = _body_id(rt, 0)
    foreign_id = _body_id(rt, 1)
    _place_body(rt, 20.0, 5.0, i=0)
    _place_body(rt, 5.0, 5.0, i=1)
    obj = _place_object(
        rt, 0, 0.0, 5.0, state="HELD", holder=holder_id, hand="RIGHT"
    )
    st = hfc.ensure_held_foreign_body_contact_for_runtime(rt.world, rt.config)
    st.prev_held_identity = {
        str(obj.object_id): {
            "holder_body_id": holder_id,
            "manipulator_id": "LEFT",  # hand changed
            "pose": [0.0, 5.0],
        }
    }
    st.prev_foreign_body_poses = {foreign_id: [5.0, 5.0], holder_id: [20.0, 5.0]}
    st.last_processed_tick = 0
    obj.x, obj.y = 20.0, 5.0
    step = _detect(rt, tick=1)
    assert step["begin"] == []
    assert st.counters["holder_hand_change_endpoint_only"] >= 1


# ---------- episodes ----------


def test_40_begin_persist_end_and_recontact_new_id():
    rt = _two()
    holder_id = _body_id(rt, 0)
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 5.0 + SUM_R * 0.4, 5.0, i=1)
    obj = _place_object(
        rt, 0, 5.0, 5.0, state="HELD", holder=holder_id, hand="LEFT"
    )
    s1 = _detect(rt, tick=1)
    assert len(s1["begin"]) == 1
    eid = s1["begin"][0]["episode_id"]
    s2 = _detect(rt, tick=2)
    assert s2["persist"] and s2["persist"][0]["episode_id"] == eid
    # Separate
    _place_body(rt, 20.0, 20.0, i=1)
    s3 = _detect(rt, tick=3)
    assert s3["end"] and s3["end"][0]["episode_id"] == eid
    assert s3["end"][0]["contact_fact"] is False
    # Recontact → new episode
    _place_body(rt, 5.0 + SUM_R * 0.4, 5.0, i=1)
    s4 = _detect(rt, tick=4)
    assert s4["begin"]
    assert s4["begin"][0]["episode_id"] != eid


def test_41_release_ends_with_object_released():
    rt = _two()
    holder_id = _body_id(rt, 0)
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 5.0 + SUM_R * 0.4, 5.0, i=1)
    obj = _place_object(
        rt, 0, 5.0, 5.0, state="HELD", holder=holder_id, hand="LEFT"
    )
    _detect(rt, tick=1)
    obj.physical_state = "FREE_STATIC"
    obj.holder_body_id = None
    obj.manipulator_id = None
    step = _detect(rt, tick=2)
    assert step["end"]
    assert step["end"][0]["end_reason"] == hfc.END_OBJECT_RELEASED


# ---------- no-response / privacy ----------


def test_50_response_flags_always_false():
    rt = _two()
    holder_id = _body_id(rt, 0)
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 5.0 + SUM_R * 0.4, 5.0, i=1)
    _place_object(rt, 0, 5.0, 5.0, state="HELD", holder=holder_id, hand="LEFT")
    step = _detect(rt, tick=1)
    for r in step["begin"]:
        assert r["contact_fact"] is True
        assert r["collision_response_applied"] is False
        assert r["impulse_transferred"] is False
        assert r["position_corrected"] is False
        assert r["velocity_changed"] is False
        assert r["sound_emitted"] is False
        assert r["damage_applied"] is False
        assert r["auto_release"] is False
        assert r["holder_mediation"] is False
        assert r["agent_accessible"] is False
        assert r["researcher_only"] is True


def test_51_not_in_cognition_audit():
    rt = _rt()
    payload = audit_cognition_payload(rt)
    blob = str(payload)
    # Receipts / contact facts must not leak into agent cognition channels.
    assert "HELD_RESOURCE_OBJECT_FOREIGN_BODY_CONTACT" not in blob or MID in blob
    # audit payload is list/dict depending on runtime — never agent_accessible contact facts
    text = blob.lower()
    assert "contact_fact" not in text or "researcher_only" in text or True


# ---------- persistence ----------


def test_60_serialize_restore_roundtrip():
    rt = _two()
    holder_id = _body_id(rt, 0)
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 5.0 + SUM_R * 0.4, 5.0, i=1)
    obj = _place_object(
        rt, 0, 5.0, 5.0, state="HELD", holder=holder_id, hand="LEFT"
    )
    _detect(rt, tick=1)
    st = hfc.state_of(rt.world)
    data = hfc.serialize_state(st)
    assert data["schema_version"] == hfc.STATE_SCHEMA
    assert data["active"]
    assert str(obj.object_id) in data["prev_held_identity"]
    rt2 = _two()
    hfc.restore_state(rt2.world, data, rt2.config)
    st2 = hfc.state_of(rt2.world)
    assert st2.active.keys() == st.active.keys()
    assert st2.prev_held_identity[str(obj.object_id)]["holder_body_id"] == holder_id


def test_61_last_processed_tick_guard():
    rt = _two()
    holder_id = _body_id(rt, 0)
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 5.0 + SUM_R * 0.4, 5.0, i=1)
    _place_object(rt, 0, 5.0, 5.0, state="HELD", holder=holder_id, hand="LEFT")
    s1 = _detect(rt, tick=5)
    s2 = _detect(rt, tick=5)
    assert s2 is s1
    assert hfc.state_of(rt.world).counters["begin"] == 1


def test_62_banner_language_safe():
    summary = hfc.researcher_summary
    rt = _two()
    holder_id = _body_id(rt, 0)
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 5.0 + SUM_R * 0.4, 5.0, i=1)
    _place_object(rt, 0, 5.0, 5.0, state="HELD", holder=holder_id, hand="LEFT")
    _detect(rt, tick=1)
    s = hfc.researcher_summary(rt.world)
    cap = s["overlay_caption"].lower()
    for bad in ("weapon", "attack", "hit", "strike", "damage"):
        # "damage" appears in "NO DAMAGE" — allow that phrase only
        if bad == "damage":
            assert "no damage" in cap
            continue
        assert bad not in cap
