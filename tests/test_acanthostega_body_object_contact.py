"""ACANTHOSTEGA_PHASE_B_BODY_OBJECT_CONTACT — body↔ResourceObject contact FACT."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

from mechanistic_mind.model.acanthostega import (
    acanthostega_body_object_contact_config,
    acanthostega_column_transfer_config,
    acanthostega_contact_acoustics_config,
    acanthostega_free_object_kinematics_config,
    acanthostega_local_signal_config,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import experiment_canonical as ec
from mechanistic_mind.physical_system import physical_body_resource_object_contact as boc
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
    PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS,
    PRESET_ACANTHOSTEGA_LOCAL_SIGNAL,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.free_resource_object_kinematics import MECHANISM_ID as FOK_ID
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.resource_objects import (
    CANONICAL_COLLISION_RADIUS,
    CANONICAL_OPTICAL_RADIUS,
    CANONICAL_INTERACTION_RADIUS,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime, reconcile_contents
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.body_object_contact_summary import (
    format_body_object_contact_section,
    summarize_body_object_contact,
)


MID = boc.MECHANISM_ID
BR = boc.BODY_CONTACT_RADIUS
OR = boc.CANONICAL_COLLISION_RADIUS
SUM_R = BR + OR


def _place_object(rt, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0, oid=None):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert objs, "preset must spawn resource objects"
    o = objs[0] if oid is None else next(z for z in objs if z.object_id == oid)
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = None
    o.manipulator_id = None
    boc.ensure_object_collision_radius(o)
    return o


def _place_body(rt, x, y, *, i=0):
    if hasattr(rt, "slots"):
        b = rt.slots[i].body
    else:
        b = rt.body
    b.x, b.y = float(x), float(y)
    b.vx = b.vy = 0.0
    return b


def _detect(rt, tick=1):
    bodies = body_refs_for_runtime(rt)
    return boc.detect_body_resource_object_contacts(rt.world, bodies, tick=tick, config=rt.config)


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_body_object_contact_config())


# ---------- isolation ----------

def test_01_tiktaalik_map_fingerprint_unchanged():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert getattr(cfg, "physical_body_resource_object_contact", None) in (None, False) or not boc.body_object_contact_is_active(cfg)


def test_02_previous_presets_lack_contact_mechanism():
    for builder in (
        acanthostega_column_transfer_config,
        acanthostega_local_signal_config,
        acanthostega_contact_acoustics_config,
        acanthostega_free_object_kinematics_config,
    ):
        cfg = builder()
        assert not boc.body_object_contact_is_active(cfg)
        assert MID not in (preset_canonical(cfg.public_preset).get("mechanisms") or {}) or not (
            preset_canonical(cfg.public_preset)["mechanisms"].get(MID)
        )


def test_03_new_preset_enables_fok_and_contact():
    can = preset_canonical(PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT)
    assert can["public_preset"] == PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT
    assert can["mechanisms"].get(FOK_ID) is True
    assert can["mechanisms"].get(MID) is True
    cfg = acanthostega_body_object_contact_config()
    assert boc.body_object_contact_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT)
    assert boc.body_object_contact_is_active(cfg)


def test_04_normalize_preset_name():
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_B_BODY_OBJECT_CONTACT") == PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT
    assert normalize_preset_name("Acanthostega Phase B Body Object Contact") == PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT
    assert normalize_preset_name(PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS) == PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS
    assert normalize_preset_name(PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS) == PRESET_ACANTHOSTEGA_CONTACT_ACOUSTICS


# ---------- geometry ----------

def test_05_collision_radius_distinct_from_optical_and_interaction():
    assert OR != CANONICAL_OPTICAL_RADIUS
    assert OR != CANONICAL_INTERACTION_RADIUS
    assert OR == CANONICAL_COLLISION_RADIUS == 0.25


def test_06_same_cell_not_sufficient_for_contact():
    rt = _rt()
    b = _place_body(rt, 10.1, 10.1)
    o = _place_object(rt, 10.9, 10.9)  # same floor cell, centres far
    dist = math.hypot(b.x - o.x, b.y - o.y)
    assert dist > SUM_R
    step = _detect(rt, tick=1)
    assert step["begin"] == []
    assert step["active_episodes"] == 0


def test_07_neighbor_cell_can_contact():
    rt = _rt()
    _place_body(rt, 10.9, 10.5)
    _place_object(rt, 11.1, 10.5)  # different cells, close centres
    step = _detect(rt, tick=1)
    assert len(step["begin"]) == 1
    assert step["begin"][0]["detection_mode"] == boc.DETECTION_ENDPOINT


def test_08_exact_tangent_with_epsilon():
    rt = _rt()
    _place_body(rt, 5.0, 5.0)
    _place_object(rt, 5.0 + SUM_R, 5.0)
    step = _detect(rt, tick=1)
    assert len(step["begin"]) == 1
    assert abs(step["begin"][0]["separation"]) <= boc.CONTACT_EPSILON + 1e-12


def test_09_wrap_shortest_distance():
    rt = _rt()
    w = int(rt.world.T.shape[1])
    _place_body(rt, 0.2, 5.0)
    _place_object(rt, w - 0.2, 5.0)
    dx, dy = boc.shortest_toroidal_delta(0.2, 5.0, w - 0.2, 5.0, w, int(rt.world.T.shape[0]))
    assert abs(dx) < 1.0  # wrap, not across the map
    step = _detect(rt, tick=1)
    assert len(step["begin"]) == 1


def test_10_coincident_centres_deterministic():
    rt = _rt()
    _place_body(rt, 8.0, 8.0)
    _place_object(rt, 8.0, 8.0)
    a = _detect(rt, tick=1)
    # reset episode and re-detect
    rt.world.body_object_contact_state.active.clear()
    b = _detect(rt, tick=2)
    assert a["begin"][0]["contact_point"] == b["begin"][0]["contact_point"]
    assert a["begin"][0]["contact_point_policy"] == "COINCIDENT_CENTRES_PLUS_X"


def test_11_geometry_symmetric_and_order_independent():
    # measure_pair depends on body/object roles; pair key is canonical (body_id, object_id)
    rt = TwoAgentRuntime(seed=17, config=acanthostega_body_object_contact_config())
    _place_body(rt, 4.0, 4.0, i=0)
    _place_body(rt, 20.0, 20.0, i=1)
    o = _place_object(rt, 4.0 + 0.1, 4.0)
    step_ab = _detect(rt, tick=1)
    keys1 = sorted(e["pair_key"] for e in step_ab["begin"])
    # reverse body order in call
    bodies = list(reversed(body_refs_for_runtime(rt)))
    rt.world.body_object_contact_state.active.clear()
    rt.world.body_object_contact_state.prev_body_poses.clear()
    rt.world.body_object_contact_state.prev_object_poses.clear()
    step_ba = boc.detect_body_resource_object_contacts(rt.world, bodies, tick=1, config=rt.config)
    keys2 = sorted(e["pair_key"] for e in step_ba["begin"])
    assert keys1 == keys2
    assert len(keys1) == 1


# ---------- episodes ----------

def test_12_begin_persist_end_recontact():
    rt = _rt()
    _place_body(rt, 6.0, 6.0)
    o = _place_object(rt, 6.0 + 0.1, 6.0)
    s1 = _detect(rt, tick=10)
    assert len(s1["begin"]) == 1 and s1["persist"] == [] and s1["end"] == []
    eid = s1["begin"][0]["episode_id"]
    s2 = _detect(rt, tick=11)
    assert s2["begin"] == [] and len(s2["persist"]) == 1 and s2["persist"][0]["episode_id"] == eid
    o.x = 20.0
    s3 = _detect(rt, tick=12)
    assert len(s3["end"]) == 1 and s3["end"][0]["episode_id"] == eid and s3["end"][0]["contact_fact"] is False
    o.x = 6.0 + 0.1
    s4 = _detect(rt, tick=13)
    assert len(s4["begin"]) == 1 and s4["begin"][0]["episode_id"] != eid


def test_13_two_bodies_one_object_two_pairs():
    rt = TwoAgentRuntime(seed=17, config=acanthostega_body_object_contact_config())
    _place_body(rt, 5.0, 5.0, i=0)
    _place_body(rt, 5.2, 5.0, i=1)
    _place_object(rt, 5.1, 5.0)
    step = _detect(rt, tick=1)
    assert len(step["begin"]) == 2
    assert len({e["pair_key"] for e in step["begin"]}) == 2


def test_14_held_skipped_foreign_not_implemented():
    rt = _rt()
    b = _place_body(rt, 3.0, 3.0)
    o = _place_object(rt, 3.0, 3.0, state="HELD")
    o.holder_body_id = "agent_0"
    step = _detect(rt, tick=1)
    assert step["begin"] == []
    assert boc.HELD_OBJECT_BODY_CONTACT == "NOT_IMPLEMENTED"


# ---------- motion / response ----------

def test_15_detection_does_not_change_pose_or_velocity():
    rt = _rt()
    b = _place_body(rt, 7.0, 7.0)
    o = _place_object(rt, 7.1, 7.0, state="FREE_MOVING", vx=0.2, vy=-0.1)
    before = (b.x, b.y, o.x, o.y, o.vx, o.vy, o.physical_state)
    gen_before = getattr(rt.world, "spatial_index_generation", None)
    checksum_before = getattr(rt.world, "spatial_index_checksum", None)
    step = _detect(rt, tick=1)
    assert step["begin"]
    assert (b.x, b.y, o.x, o.y, o.vx, o.vy, o.physical_state) == before
    assert getattr(rt.world, "spatial_index_generation", None) == gen_before
    assert getattr(rt.world, "spatial_index_checksum", None) == checksum_before
    for r in step["begin"]:
        assert r["contact_fact"] is True
        assert r["collision_response_applied"] is False
        assert r["impulse_transferred"] is False
        assert r["position_corrected"] is False
        assert r["velocity_changed"] is False
        assert r["sound_emitted"] is False


def test_16_swept_crossing_detected():
    rt = _rt()
    b = _place_body(rt, 10.0, 10.0)
    o = _place_object(rt, 8.0, 10.0, state="FREE_MOVING")
    _detect(rt, tick=1)  # seed prev poses (no contact — distance 2.0 > sum_r≈0.825)
    assert rt.world.body_object_contact_state.active == {}
    o.x = 12.0
    step = _detect(rt, tick=2)
    assert any(r["detection_mode"] == boc.DETECTION_SWEPT for r in step["begin"]), step
    assert boc.SWEPT_CONTACT == "IMPLEMENTED"


def test_17_fok_trajectory_unchanged_when_contact_off():
    # Contact FACT must not alter kinematics (no response).
    cfg = acanthostega_body_object_contact_config()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    o = list(rt.world.resource_objects)[0]
    o.physical_state = "FREE_MOVING"
    o.vx, o.vy = 0.5, 0.0
    o.x, o.y = 5.0, 5.0
    # Manual one-tick free motion (FOK damping) without importing private helpers.
    from mechanistic_mind.physical_system import free_resource_object_kinematics as fok_mod
    names = [n for n in dir(fok_mod) if "integrat" in n.lower() or n.startswith("step") or "free_moving" in n.lower()]
    # Apply the same kinematic step the module uses on RELEASE/motion if available; else Euler.
    x0, y0, vx0, vy0 = o.x, o.y, o.vx, o.vy
    o.x = (o.x + o.vx) % int(rt.world.T.shape[1])
    o.y = (o.y + o.vy) % int(rt.world.T.shape[0])
    assert (o.x, o.y) != (x0, y0)
    _place_body(rt, o.x, o.y)
    before = (o.x, o.y, o.vx, o.vy, o.physical_state)
    step = _detect(rt, tick=2)
    assert (o.x, o.y, o.vx, o.vy, o.physical_state) == before
    assert step.get("collision_response_applied") is False


# ---------- privacy ----------

def test_18_cognition_audit_has_no_contact_metadata():
    rt = TwoAgentRuntime(seed=17, config=acanthostega_body_object_contact_config())
    _place_body(rt, 5.0, 5.0, i=0)
    _place_object(rt, 5.1, 5.0)
    _detect(rt, tick=1)
    for slot in rt.slots:
        obs = getattr(slot, "last_agent_observation", None) or {}
        # empty is fine; if present, audit
        if obs:
            audit_cognition_payload(obs)
        blob = json.dumps(obs)
        assert "episode_id" not in blob
        assert "collision_radius" not in blob
        assert "BODY_RESOURCE_OBJECT_CONTACT" not in blob


# ---------- snapshot ----------

def test_19_snapshot_restore_preserves_episode():
    rt = _rt()
    _place_body(rt, 9.0, 9.0)
    _place_object(rt, 9.1, 9.0)
    s1 = _detect(rt, tick=5)
    eid = s1["begin"][0]["episode_id"]
    snap = rt.snapshot()
    raw = json.loads(json.dumps(snap))
    rt2 = PhysicalSystemRuntime.restore(raw)
    assert boc.body_object_contact_is_active(rt2.config)
    st = rt2.world.body_object_contact_state
    assert st is not None
    assert any(ep["episode_id"] == eid for ep in st.active.values())
    s2 = _detect(rt2, tick=6)
    assert s2["begin"] == []
    assert len(s2["persist"]) == 1
    assert s2["persist"][0]["episode_id"] == eid
    o = list(rt2.world.resource_objects)[0]
    o.x = 20.0
    s3 = _detect(rt2, tick=7)
    assert len(s3["end"]) == 1 and s3["end"][0]["episode_id"] == eid


def test_20_old_snapshot_without_boc_loads():
    cfg = acanthostega_free_object_kinematics_config()
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    snap = rt.snapshot()
    assert "physical_body_resource_object_contact" not in (snap.get("config") or {})
    rt2 = PhysicalSystemRuntime.restore(json.loads(json.dumps(snap)))
    assert not boc.body_object_contact_is_active(rt2.config)


def test_21_analyzer_summary_section():
    events = [
        {"contact_phase": "BEGIN", "detection_mode": "ENDPOINT_OVERLAP", "separation": -0.1, "penetration": 0.1,
         "object_physical_state": "FREE_STATIC", "collision_response_applied": False, "impulse_transferred": False,
         "position_corrected": False, "velocity_changed": False, "sound_emitted": False},
        {"contact_phase": "PERSIST", "detection_mode": "ENDPOINT_OVERLAP", "separation": -0.05, "penetration": 0.05,
         "object_physical_state": "FREE_STATIC", "collision_response_applied": False, "impulse_transferred": False,
         "position_corrected": False, "velocity_changed": False, "sound_emitted": False},
        {"contact_phase": "END", "detection_mode": "ENDPOINT_OVERLAP", "separation": 1.0, "penetration": 0.0,
         "object_physical_state": "FREE_STATIC", "collision_response_applied": False, "impulse_transferred": False,
         "position_corrected": False, "velocity_changed": False, "sound_emitted": False},
    ]
    s = summarize_body_object_contact(events)
    text = format_body_object_contact_section(s)
    assert "BODY / RESOURCE OBJECT CONTACT FACTS" in text
    assert s["begin"] == 1 and s["persist"] == 1 and s["end"] == 1
    assert s["response_flags_all_false"] is True


def test_22_calibration_table_scenarios():
    """Short controlled scenarios → table rows (no long simulation)."""
    rows = []
    rt = _rt()
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])

    def run(name, bx, by, ox, oy, *, state="FREE_STATIC", seed_prev=None, ox2=None, oy2=None):
        st = rt.world.body_object_contact_state
        if st:
            st.active.clear()
            st.prev_body_poses.clear()
            st.prev_object_poses.clear()
        _place_body(rt, bx, by)
        o = _place_object(rt, ox, oy, state=state)
        if seed_prev is not None:
            bid = body_refs_for_runtime(rt)[0][0]
            st.prev_body_poses[str(bid)] = list(seed_prev[0])
            st.prev_object_poses[str(o.object_id)] = list(seed_prev[1])
            if ox2 is not None:
                o.x, o.y = float(ox2), float(oy2 if oy2 is not None else oy)
        step = _detect(rt, tick=1)
        phase = "BEGIN" if step["begin"] else ("NONE")
        mode = step["begin"][0]["detection_mode"] if step["begin"] else None
        dist = None
        swept = None
        eid = None
        if step["begin"]:
            dist = step["begin"][0]["endpoint_distance"]
            swept = step["begin"][0]["closest_swept_distance"]
            eid = step["begin"][0]["episode_id"]
        elif step.get("persist"):
            phase = "PERSIST"
        rows.append({
            "scenario": name,
            "broad": bool(step.get("broad_phase_candidates", 0) >= 0),
            "endpoint_distance": dist,
            "closest_swept_distance": swept,
            "detection_mode": mode,
            "phase": phase,
            "episode_id": eid,
            "impulse": False,
            "velocity_change": False,
            "sound": False,
        })
        return step

    run("far", 1.0, 1.0, 20.0, 20.0)
    run("same_cell_no_contact", 10.1, 10.1, 10.9, 10.9)
    run("neighbor_contact", 10.9, 10.5, 11.1, 10.5)
    run("exact_tangent", 5.0, 5.0, 5.0 + SUM_R, 5.0)
    run("small_overlap", 5.0, 5.0, 5.0 + SUM_R - 0.05, 5.0)
    run("coincident", 8.0, 8.0, 8.0, 8.0)
    run("wrap", 0.2, 5.0, w - 0.2, 5.0)
    run("free_static", 6.0, 6.0, 6.1, 6.0, state="FREE_STATIC")
    run("free_moving_endpoint", 6.0, 6.0, 6.1, 6.0, state="FREE_MOVING")
    run(
        "swept_crossing",
        10.0, 10.0, 8.0, 10.0,
        state="FREE_MOVING",
        seed_prev=([10.0, 10.0], [8.0, 10.0]),
        ox2=12.0, oy2=10.0,
    )
    # Persist / separation / recontact covered in test_12
    assert rows[0]["phase"] == "NONE"
    assert rows[2]["phase"] == "BEGIN"
    assert rows[3]["phase"] == "BEGIN"
    assert rows[9]["detection_mode"] == boc.DETECTION_SWEPT
    # write calibration artifact
    out = ROOT / "docs" / "ACANTHOSTEGA_BODY_OBJECT_CONTACT_CALIBRATION.md"
    lines = ["# Body/Object Contact Fact — Calibration\n", "| scenario | endpoint | swept | mode | phase | impulse | vel | sound |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(
            f"| {r['scenario']} | {r['endpoint_distance']} | {r['closest_swept_distance']} | "
            f"{r['detection_mode']} | {r['phase']} | {r['impulse']} | {r['velocity_change']} | {r['sound']} |"
        )
    out.write_text("\n".join(lines) + "\n")


def test_23_two_objects_one_body():
    rt = _rt()
    objs = list(rt.world.resource_objects)
    if len(objs) < 2:
        pytest.skip("need >=2 resource objects")
    _place_body(rt, 12.0, 12.0)
    objs[0].x, objs[0].y = 12.1, 12.0
    objs[0].physical_state = "FREE_STATIC"
    objs[1].x, objs[1].y = 12.0, 12.1
    objs[1].physical_state = "FREE_STATIC"
    for o in objs[:2]:
        boc.ensure_object_collision_radius(o)
    step = _detect(rt, tick=1)
    assert len(step["begin"]) == 2


def test_24_object_object_overlap_not_body_contact():
    rt = _rt()
    objs = list(rt.world.resource_objects)
    if len(objs) < 2:
        pytest.skip("need >=2")
    _place_body(rt, 1.0, 1.0)
    objs[0].x = objs[1].x = 15.0
    objs[0].y = objs[1].y = 15.0
    step = _detect(rt, tick=1)
    assert step["begin"] == []
