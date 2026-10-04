"""Acanthostega single manipulator GRASP/RELEASE — deterministic tests ≤250 ticks."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    acanthostega_gentle_config,
    acanthostega_material_vision_config,
    acanthostega_materials_config,
    acanthostega_single_grasp_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_ACANTHOSTEGA_MATERIAL_VISION,
    PRESET_ACANTHOSTEGA_MATERIALS,
    PRESET_ACANTHOSTEGA_SINGLE_GRASP,
    PRESET_BETA31,
    acanthostega_mechanism_map,
    acanthostega_single_grasp_mechanism_map,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.locomotion_profile import GENTLE_TERRAIN_LOCOMOTION
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.physical_manipulator import (
    PHYSICAL_GRASP_RELEASE,
    PHYSICAL_STATE_HELD,
    SINGLE_PHYSICAL_MANIPULATOR,
    effector_world_xy,
    grasp_release_is_active,
    manipulator_is_active,
)
from mechanistic_mind.physical_system.resource_objects import (
    PHYSICAL_RESOURCE_OBJECT_VISION,
    PHYSICAL_RESOURCE_OBJECTS,
    PHYSICAL_STATE_FREE_STATIC,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.grasp_summary import summarize_grasp_events
from mechanistic_mind.ui.psy_observer_web.serialize import world_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

FROZEN_BETA31_FP_SEED17 = "1621ef2c154864d1"
SEED = 17


def _objs(world):
    return list(getattr(world, "resource_objects", None) or [])


def _off_cog(cfg):
    cfg = cfg.copy()
    cfg.cognition.cognition_enabled = False
    return cfg


def _place_in_reach(rt):
    obj = _objs(rt.world)[0]
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    ex, ey = effector_world_xy(rt.body, width=w, height=h, config=rt.config)
    obj.x, obj.y = ex, ey
    return obj


def test_tiktaalik_preservation_contract():
    m = beta31_mechanism_map()
    assert SINGLE_PHYSICAL_MANIPULATOR not in m
    assert PHYSICAL_GRASP_RELEASE not in m
    assert GENTLE_TERRAIN_LOCOMOTION not in m
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    rt = PhysicalSystemRuntime(seed=SEED, config=tiktaalik_config())
    acts = available_actions()
    assert "GRASP" not in acts and "RELEASE" not in acts
    assert manipulator_is_active(rt.config) is False
    assert acts == ("WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W")


def test_preset_separation():
    assert normalize_preset_name("Acanthostega Phase A Single Grasp") == PRESET_ACANTHOSTEGA_SINGLE_GRASP
    pg = preset_canonical(PRESET_ACANTHOSTEGA_GENTLE, seed=17)
    pm = preset_canonical(PRESET_ACANTHOSTEGA_MATERIALS, seed=17)
    pv = preset_canonical(PRESET_ACANTHOSTEGA_MATERIAL_VISION, seed=17)
    ps = preset_canonical(PRESET_ACANTHOSTEGA_SINGLE_GRASP, seed=17)
    assert SINGLE_PHYSICAL_MANIPULATOR not in pg["mechanisms"]
    assert SINGLE_PHYSICAL_MANIPULATOR not in pm["mechanisms"]
    assert SINGLE_PHYSICAL_MANIPULATOR not in pv["mechanisms"]
    assert ps["mechanisms"][SINGLE_PHYSICAL_MANIPULATOR] is True
    assert ps["mechanisms"][PHYSICAL_GRASP_RELEASE] is True
    assert ps["mechanisms"][PHYSICAL_RESOURCE_OBJECTS] is True
    assert ps["mechanisms"][PHYSICAL_RESOURCE_OBJECT_VISION] is True
    assert SINGLE_PHYSICAL_MANIPULATOR not in acanthostega_mechanism_map()
    assert acanthostega_single_grasp_mechanism_map()[PHYSICAL_GRASP_RELEASE] is True
    assert manipulator_is_active(acanthostega_material_vision_config()) is False
    assert grasp_release_is_active(acanthostega_single_grasp_config()) is True


def test_out_of_reach_failure():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    obj = _objs(rt.world)[0]
    x0, y0 = obj.x, obj.y
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    obj = _objs(rt.world)[0]
    assert obj.physical_state == PHYSICAL_STATE_FREE_STATIC
    assert abs(obj.x - x0) < 1e-12 and abs(obj.y - y0) < 1e-12
    rec = rt.last_manipulator_receipt or {}
    assert rec.get("event") == "GRASP_FAILED_OUT_OF_REACH"
    assert rec.get("object_id") is None


def test_successful_grasp_and_move_and_release():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    obj = _place_in_reach(rt)
    mass0, qty0, comp0 = obj.mass, obj.quantity, obj.composition[0].amount
    w0 = float(rt.body.mechanical_work_reservoir)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    obj = _objs(rt.world)[0]
    assert obj.physical_state == PHYSICAL_STATE_HELD
    assert obj.holder_body_id == "agent_0"
    assert obj.manipulator_id == "manipulator_0"
    assert (rt.last_manipulator_receipt or {}).get("event") == "GRASP_SUCCEEDED"
    assert float(rt.body.mechanical_work_reservoir) <= w0 + 1e-12
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    for _ in range(8):
        rt.step_forced_motor({"locomotion": "MOVE:E", "manipulator": "NONE"})
        obj = _objs(rt.world)[0]
        ex, ey = effector_world_xy(rt.body, width=w, height=h, config=rt.config)
        assert abs(obj.x - ex) < 1e-9
        assert abs(obj.y - ey) < 1e-9
        assert obj.physical_state == PHYSICAL_STATE_HELD
        assert abs(obj.mass - mass0) < 1e-12
        assert abs(obj.quantity - qty0) < 1e-12
        assert abs(obj.composition[0].amount - comp0) < 1e-12
        assert abs(obj.vx) < 1e-15 and abs(obj.vy) < 1e-15
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "RELEASE"})
    obj = _objs(rt.world)[0]
    rec = rt.last_manipulator_receipt or {}
    assert rec.get("event") == "RELEASE_SUCCEEDED"
    assert obj.physical_state == PHYSICAL_STATE_FREE_STATIC
    assert obj.holder_body_id is None
    assert obj.manipulator_id is None
    rel_x, rel_y = float(obj.x), float(obj.y)
    rel_xy = rec.get("release_xy") or [rel_x, rel_y]
    assert abs(obj.x - float(rel_xy[0])) < 1e-9 and abs(obj.y - float(rel_xy[1])) < 1e-9
    bx, by = rt.body.x, rt.body.y
    for _ in range(6):
        rt.step_forced_motor({"locomotion": "MOVE:N", "manipulator": "NONE"})
    obj = _objs(rt.world)[0]
    assert abs(obj.x - rel_x) < 1e-9 and abs(obj.y - rel_y) < 1e-9
    assert abs(rt.body.x - bx) > 1e-6 or abs(rt.body.y - by) > 1e-6
    assert abs(obj.vx) < 1e-15


def test_nearest_and_id_tiebreak():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    ex, ey = effector_world_xy(rt.body, width=w, height=h, config=rt.config)
    a = _objs(rt.world)[0]
    a.object_id = "resource-000002"
    a.x, a.y = ex, ey
    b = a.copy()
    b.object_id = "resource-000001"
    b.x, b.y = ex, ey
    rt.world.resource_objects = [a, b]
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    held = [o for o in _objs(rt.world) if o.physical_state == PHYSICAL_STATE_HELD]
    assert len(held) == 1
    assert held[0].object_id == "resource-000001"


def test_empty_and_occupied_commands():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "RELEASE"})
    assert (rt.last_manipulator_receipt or {}).get("event") == "RELEASE_NO_OBJECT"
    _place_in_reach(rt)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    oid = _objs(rt.world)[0].object_id
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    assert (rt.last_manipulator_receipt or {}).get("event") == "GRASP_FAILED_OCCUPIED"
    assert _objs(rt.world)[0].object_id == oid
    assert _objs(rt.world)[0].physical_state == PHYSICAL_STATE_HELD


def test_two_agent_contention_deterministic():
    cfg = _off_cog(acanthostega_single_grasp_config())
    results = []
    for order in ((0, 1), (1, 0)):
        ta = TwoAgentRuntime(seed=SEED, config=cfg, process_order=order, contact_enabled=False)
        obj = _objs(ta.world)[0]
        w = int(ta.world.T.shape[1])
        h = int(ta.world.T.shape[0])
        a0, a1 = ta.slots[0], ta.slots[1]
        a0.body.x, a0.body.y, a0.body.theta = 10.0, 10.0, 0.0
        a1.body.x, a1.body.y, a1.body.theta = 11.10, 10.0, 3.141592653589793
        a0.body.vx = a0.body.vy = a1.body.vx = a1.body.vy = 0.0
        ex, ey = effector_world_xy(a0.body, width=w, height=h, config=a0.config)
        obj.x, obj.y = ex, ey
        for slot in ta.slots:
            slot._forced_motor_once = {"locomotion": "WAIT", "manipulator": "GRASP"}
        ta.step(1)
        held = [o for o in _objs(ta.world) if o.physical_state == PHYSICAL_STATE_HELD]
        assert len(held) == 1
        results.append((held[0].holder_body_id, (ta.slots[0].last_manipulator_receipt or {}).get("event"),
                        (ta.slots[1].last_manipulator_receipt or {}).get("event")))
    assert results[0] == results[1]
    assert results[0][0] == "agent_0"
    assert "GRASP_SUCCEEDED" in results[0][1:]
    assert "GRASP_FAILED_OCCUPIED" in results[0][1:]


def test_vision_while_held_no_object_id():
    ta = TwoAgentRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    obj = _objs(ta.world)[0]
    w = int(ta.world.T.shape[1])
    h = int(ta.world.T.shape[0])
    a0 = ta.slots[0]
    a0.body.x, a0.body.y, a0.body.theta = 10.0, 10.0, 0.0
    ex, ey = effector_world_xy(a0.body, width=w, height=h, config=a0.config)
    obj.x, obj.y = ex, ey
    a0._forced_motor_once = {"locomotion": "WAIT", "manipulator": "GRASP"}
    ta.slots[1]._forced_motor_once = {"locomotion": "WAIT", "manipulator": "NONE"}
    ta.step(1)
    a1 = ta.slots[1]
    a1.body.x = ex
    a1.body.y = ey
    obs = a1.agent_observation(foreign_bodies=[a0.body])
    assert "prop_grip_0" in obs
    hits = audit_cognition_payload(obs)
    assert not hits
    assert "resource-000001" not in repr(obs)
    assert "object_id" not in obs


def test_proprioception_empty_occupied_tiktaalik_unchanged():
    g = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    empty = g.agent_observation()
    assert empty.get("prop_grip_0") == 0.0
    _place_in_reach(g)
    g.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    occ = g.agent_observation()
    assert occ.get("prop_grip_0") == 1.0
    assert "resource-000001" not in repr(occ)
    t0 = PhysicalSystemRuntime(seed=SEED, config=_off_cog(tiktaalik_config()))
    keys = set(t0.agent_observation())
    t1 = PhysicalSystemRuntime(seed=SEED, config=_off_cog(tiktaalik_config()))
    assert set(t1.agent_observation()) == keys
    assert "prop_grip_0" not in keys


def test_snapshot_roundtrip_held():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    _place_in_reach(rt)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    for _ in range(3):
        rt.step_forced_motor({"locomotion": "MOVE:E", "manipulator": "NONE"})
    snap = deepcopy(rt.snapshot())
    n_obj = len(_objs(rt.world))
    rest = PhysicalSystemRuntime.restore(snap)
    assert len(_objs(rest.world)) == n_obj
    obj = _objs(rest.world)[0]
    assert obj.physical_state == PHYSICAL_STATE_HELD
    assert obj.holder_body_id == "agent_0"
    rest.step_forced_motor({"locomotion": "MOVE:N", "manipulator": "NONE"})
    obj2 = _objs(rest.world)[0]
    w = int(rest.world.T.shape[1])
    h = int(rest.world.T.shape[0])
    ex, ey = effector_world_xy(rest.body, width=w, height=h, config=rest.config)
    assert abs(obj2.x - ex) < 1e-9
    rest.step_forced_motor({"locomotion": "WAIT", "manipulator": "RELEASE"})
    assert _objs(rest.world)[0].physical_state == PHYSICAL_STATE_FREE_STATIC


def test_work_not_created_and_old_presets_no_manipulator():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    w0 = float(rt.body.mechanical_work_reservoir)
    _place_in_reach(rt)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    assert float(rt.body.mechanical_work_reservoir) <= w0 + 1e-12
    for cfg in (tiktaalik_config(), acanthostega_gentle_config(), acanthostega_materials_config(), acanthostega_material_vision_config()):
        r = PhysicalSystemRuntime(seed=SEED, config=_off_cog(cfg))
        assert manipulator_is_active(r.config) is False
        assert "GRASP" not in (r.cognition.get("available_actions") or available_actions())


def test_observer_overlay_and_analyzer_counts():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    frame = world_frame(rt)
    assert frame["manipulators_researcher_only"] is True
    assert frame["manipulators"]
    assert frame["manipulators"][0]["researcher_only"] is True
    _place_in_reach(rt)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator": "RELEASE"})
    summary = summarize_grasp_events(rt.structured_events.list(limit=50))
    assert summary["grasp_successes"] == 1
    assert summary["release_successes"] == 1
    assert "intention" not in summary["note"].lower() or "not" in summary["note"].lower()
    sess = ObserverSession(SessionConfig(seed=SEED))
    sess.apply_experiment({"public_preset": PRESET_ACANTHOSTEGA_SINGLE_GRASP, "agent_count": 1, "cognition_enabled": False})
    snap = sess.runtime.mechanisms()
    ids = {m["id"] for m in snap["mechanisms"]}
    assert SINGLE_PHYSICAL_MANIPULATOR in ids
    assert PHYSICAL_GRASP_RELEASE in ids
    sess2 = ObserverSession(SessionConfig(seed=SEED))
    sess2.apply_experiment({"public_preset": PRESET_ACANTHOSTEGA_MATERIAL_VISION, "agent_count": 1})
    ids2 = {m["id"] for m in sess2.runtime.mechanisms()["mechanisms"]}
    assert SINGLE_PHYSICAL_MANIPULATOR not in ids2
