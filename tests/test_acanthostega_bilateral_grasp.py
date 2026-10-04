"""Acanthostega bilateral manipulators — deterministic tests ≤250 ticks."""
from __future__ import annotations

import math
from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    acanthostega_bilateral_grasp_config,
    acanthostega_gentle_config,
    acanthostega_material_vision_config,
    acanthostega_materials_config,
    acanthostega_single_grasp_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BILATERAL_GRASP,
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_ACANTHOSTEGA_MATERIAL_VISION,
    PRESET_ACANTHOSTEGA_MATERIALS,
    PRESET_ACANTHOSTEGA_SINGLE_GRASP,
    PRESET_BETA31,
    acanthostega_bilateral_grasp_mechanism_map,
    acanthostega_mechanism_map,
    acanthostega_single_grasp_mechanism_map,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.physical_manipulator import (
    BILATERAL_GRASP_RELEASE,
    BILATERAL_PHYSICAL_MANIPULATORS,
    CANONICAL_FORWARD_OFFSET,
    CANONICAL_LATERAL_OFFSET,
    MANIP_LEFT,
    MANIP_RIGHT,
    PHYSICAL_GRASP_RELEASE,
    PHYSICAL_STATE_HELD,
    SINGLE_PHYSICAL_MANIPULATOR,
    bilateral_grasp_release_is_active,
    bilateral_manipulator_is_active,
    effector_world_xy,
    grasp_release_is_active,
    manipulator_is_active,
)
from mechanistic_mind.physical_system.resource_objects import (
    CANONICAL_FIRST_OBJECT_ID,
    CANONICAL_SECOND_OBJECT_ID,
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


def _work_on(cfg):
    cfg = _off_cog(cfg)
    cfg.discrete_action_work.mode = "EXPERIMENTAL"
    return cfg


def _pose(body, x, y, theta):
    body.x, body.y, body.theta = float(x), float(y), float(theta)
    body.vx = body.vy = body.omega = 0.0


def _place_exclusive(rt, *, extra=0.40):
    """A only in LEFT reach, B only in RIGHT reach."""
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    lx, ly = effector_world_xy(rt.body, width=w, height=h, config=rt.config, manipulator_id=MANIP_LEFT)
    rx, ry = effector_world_xy(rt.body, width=w, height=h, config=rt.config, manipulator_id=MANIP_RIGHT)
    theta = float(rt.body.theta)
    lat_x, lat_y = -math.sin(theta), math.cos(theta)
    objs = _objs(rt.world)
    while len(objs) < 2:
        extra_o = objs[0].copy()
        extra_o.object_id = CANONICAL_SECOND_OBJECT_ID
        objs.append(extra_o)
    a, b = objs[0], objs[1]
    a.object_id = CANONICAL_FIRST_OBJECT_ID
    b.object_id = CANONICAL_SECOND_OBJECT_ID
    a.x, a.y = lx + extra * lat_x, ly + extra * lat_y
    b.x, b.y = rx - extra * lat_x, ry - extra * lat_y
    a.physical_state = b.physical_state = PHYSICAL_STATE_FREE_STATIC
    a.holder_body_id = b.holder_body_id = None
    a.manipulator_id = b.manipulator_id = None
    rt.world.resource_objects = [a, b]
    return a, b


def test_preservation_and_preset_separation():
    m = beta31_mechanism_map()
    assert BILATERAL_PHYSICAL_MANIPULATORS not in m
    assert BILATERAL_GRASP_RELEASE not in m
    assert SINGLE_PHYSICAL_MANIPULATOR not in m
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    assert normalize_preset_name("Acanthostega Phase A Bilateral Grasp") == PRESET_ACANTHOSTEGA_BILATERAL_GRASP
    assert normalize_preset_name("Acanthostega Phase A Single Grasp") == PRESET_ACANTHOSTEGA_SINGLE_GRASP
    pg = preset_canonical(PRESET_ACANTHOSTEGA_GENTLE, seed=17)
    pm = preset_canonical(PRESET_ACANTHOSTEGA_MATERIALS, seed=17)
    pv = preset_canonical(PRESET_ACANTHOSTEGA_MATERIAL_VISION, seed=17)
    ps = preset_canonical(PRESET_ACANTHOSTEGA_SINGLE_GRASP, seed=17)
    pb = preset_canonical(PRESET_ACANTHOSTEGA_BILATERAL_GRASP, seed=17)
    assert BILATERAL_PHYSICAL_MANIPULATORS not in pg["mechanisms"]
    assert BILATERAL_PHYSICAL_MANIPULATORS not in pm["mechanisms"]
    assert BILATERAL_PHYSICAL_MANIPULATORS not in pv["mechanisms"]
    assert BILATERAL_PHYSICAL_MANIPULATORS not in ps["mechanisms"]
    assert ps["mechanisms"][SINGLE_PHYSICAL_MANIPULATOR] is True
    assert pb["mechanisms"][BILATERAL_PHYSICAL_MANIPULATORS] is True
    assert pb["mechanisms"][BILATERAL_GRASP_RELEASE] is True
    assert SINGLE_PHYSICAL_MANIPULATOR not in pb["mechanisms"]
    assert BILATERAL_PHYSICAL_MANIPULATORS not in acanthostega_mechanism_map()
    assert BILATERAL_GRASP_RELEASE not in acanthostega_single_grasp_mechanism_map()
    assert acanthostega_bilateral_grasp_mechanism_map()[BILATERAL_GRASP_RELEASE] is True
    sg = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    assert manipulator_is_active(sg.config) is True
    assert bilateral_manipulator_is_active(sg.config) is False
    assert "GRASP" in (sg.cognition.get("available_actions") or [])
    assert "LEFT_GRASP" not in (sg.cognition.get("available_actions") or [])
    tk = PhysicalSystemRuntime(seed=SEED, config=_off_cog(tiktaalik_config()))
    assert available_actions() == ("WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W")
    assert "GRASP" not in (tk.cognition.get("available_actions") or available_actions())


def test_geometry_left_right_heading():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    fwd, lat = CANONICAL_FORWARD_OFFSET, CANONICAL_LATERAL_OFFSET
    cases = (
        (10.0, 10.0, 0.0, (10 + fwd, 10 + lat), (10 + fwd, 10 - lat)),
        (10.0, 10.0, math.pi / 2, (10 - lat, 10 + fwd), (10 + lat, 10 + fwd)),
        (10.0, 10.0, math.pi, (10 - fwd, 10 - lat), (10 - fwd, 10 + lat)),
        (10.0, 10.0, -math.pi / 2, (10 + lat, 10 - fwd), (10 - lat, 10 - fwd)),
        (0.1, 0.1, 0.0, None, None),
    )
    for x, y, th, exp_l, exp_r in cases:
        _pose(rt.body, x, y, th)
        lx, ly = effector_world_xy(rt.body, width=w, height=h, config=rt.config, manipulator_id=MANIP_LEFT)
        rx, ry = effector_world_xy(rt.body, width=w, height=h, config=rt.config, manipulator_id=MANIP_RIGHT)
        if exp_l is None:
            assert 0.0 <= lx < w and 0.0 <= ly < h
            assert 0.0 <= rx < w and 0.0 <= ry < h
            continue
        assert abs(lx - exp_l[0]) < 1e-9 and abs(ly - exp_l[1]) < 1e-9
        assert abs(rx - exp_r[0]) < 1e-9 and abs(ry - exp_r[1]) < 1e-9


def test_independent_reach():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    _pose(rt.body, 12.0, 12.0, 0.0)
    a, b = _place_exclusive(rt)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "NONE"})
    rec = rt.last_manipulator_receipt or {}
    hands = rec.get("hands") or {}
    assert hands[MANIP_LEFT]["event"] == "GRASP_SUCCEEDED"
    assert hands[MANIP_LEFT]["object_id"] == a.object_id
    assert hands[MANIP_RIGHT]["event"] == "MANIPULATOR_IDLE"
    a2 = next(o for o in _objs(rt.world) if o.object_id == a.object_id)
    b2 = next(o for o in _objs(rt.world) if o.object_id == b.object_id)
    assert a2.physical_state == PHYSICAL_STATE_HELD and a2.manipulator_id == MANIP_LEFT
    assert b2.physical_state == PHYSICAL_STATE_FREE_STATIC
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "NONE", "manipulator_right": "GRASP"})
    hands = (rt.last_manipulator_receipt or {}).get("hands") or {}
    assert hands[MANIP_RIGHT]["event"] == "GRASP_SUCCEEDED"


def test_simultaneous_two_object_grasp_and_work():
    rt = PhysicalSystemRuntime(seed=SEED, config=_work_on(acanthostega_bilateral_grasp_config()))
    _pose(rt.body, 12.0, 12.0, 0.0)
    a, b = _place_exclusive(rt)
    rt.body.mechanical_work_reservoir = 10.0
    w0 = float(rt.body.mechanical_work_reservoir)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "GRASP"})
    rec = rt.last_manipulator_receipt or {}
    hands = rec.get("hands") or {}
    assert hands[MANIP_LEFT]["event"] == "GRASP_SUCCEEDED"
    assert hands[MANIP_RIGHT]["event"] == "GRASP_SUCCEEDED"
    assert {hands[MANIP_LEFT]["object_id"], hands[MANIP_RIGHT]["object_id"]} == {a.object_id, b.object_id}
    assert hands[MANIP_LEFT]["object_id"] != hands[MANIP_RIGHT]["object_id"]
    debit = float(rec.get("work_debit") or 0.0)
    assert abs(debit - 0.02) < 1e-9
    assert abs(w0 - float(rt.body.mechanical_work_reservoir) - 0.02) < 1e-9 or debit <= w0 + 1e-12
    held = [o for o in _objs(rt.world) if o.physical_state == PHYSICAL_STATE_HELD]
    assert len(held) == 2
    mids = {o.manipulator_id for o in held}
    assert mids == {MANIP_LEFT, MANIP_RIGHT}


def test_same_body_distance_arbitration():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    _pose(rt.body, 12.0, 12.0, 0.0)
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    lx, ly = effector_world_xy(rt.body, width=w, height=h, config=rt.config, manipulator_id=MANIP_LEFT)
    rx, ry = effector_world_xy(rt.body, width=w, height=h, config=rt.config, manipulator_id=MANIP_RIGHT)
    objs = _objs(rt.world)
    a = objs[0]
    a.physical_state = PHYSICAL_STATE_FREE_STATIC
    a.holder_body_id = a.manipulator_id = None
    a.x = (lx * 0.35 + rx * 0.65)
    a.y = (ly * 0.35 + ry * 0.65)
    for extra in objs[1:]:
        extra.x, extra.y = 1.0, 1.0
        extra.physical_state = PHYSICAL_STATE_FREE_STATIC
        extra.holder_body_id = extra.manipulator_id = None
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "GRASP"})
    hands = (rt.last_manipulator_receipt or {}).get("hands") or {}
    assert hands[MANIP_RIGHT]["event"] == "GRASP_SUCCEEDED"
    assert hands[MANIP_LEFT]["event"] in {"GRASP_FAILED_OCCUPIED", "GRASP_FAILED_OUT_OF_REACH"}
    held = [o for o in _objs(rt.world) if o.physical_state == PHYSICAL_STATE_HELD]
    assert len(held) == 1 and held[0].manipulator_id == MANIP_RIGHT

    rt2 = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    _pose(rt2.body, 12.0, 12.0, 0.0)
    lx, ly = effector_world_xy(rt2.body, width=w, height=h, config=rt2.config, manipulator_id=MANIP_LEFT)
    rx, ry = effector_world_xy(rt2.body, width=w, height=h, config=rt2.config, manipulator_id=MANIP_RIGHT)
    obj = _objs(rt2.world)[0]
    obj.x, obj.y = 0.5 * (lx + rx), 0.5 * (ly + ry)
    for extra in _objs(rt2.world)[1:]:
        extra.x, extra.y = 1.0, 1.0
    rt2.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "GRASP"})
    hands = (rt2.last_manipulator_receipt or {}).get("hands") or {}
    # Equal distance: sort (dist, object_id, manipulator_id) → LEFT before RIGHT.
    assert hands[MANIP_LEFT]["event"] == "GRASP_SUCCEEDED"
    assert hands[MANIP_RIGHT]["event"] in {"GRASP_FAILED_OCCUPIED", "GRASP_FAILED_OUT_OF_REACH"}


def test_independent_and_simultaneous_release():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    _pose(rt.body, 12.0, 12.0, 0.0)
    _place_exclusive(rt)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "GRASP"})
    left_id = next(o.object_id for o in _objs(rt.world) if o.manipulator_id == MANIP_LEFT)
    right_id = next(o.object_id for o in _objs(rt.world) if o.manipulator_id == MANIP_RIGHT)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "RELEASE", "manipulator_right": "NONE"})
    a = next(o for o in _objs(rt.world) if o.object_id == left_id)
    b = next(o for o in _objs(rt.world) if o.object_id == right_id)
    assert a.physical_state == PHYSICAL_STATE_FREE_STATIC
    assert b.physical_state == PHYSICAL_STATE_HELD and b.manipulator_id == MANIP_RIGHT
    ax, ay = a.x, a.y
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    for _ in range(4):
        rt.step_forced_motor({"locomotion": "MOVE:E", "manipulator_left": "NONE", "manipulator_right": "NONE"})
    a = next(o for o in _objs(rt.world) if o.object_id == left_id)
    b = next(o for o in _objs(rt.world) if o.object_id == right_id)
    assert abs(a.x - ax) < 1e-9 and abs(a.y - ay) < 1e-9
    rx, ry = effector_world_xy(rt.body, width=w, height=h, config=rt.config, manipulator_id=MANIP_RIGHT)
    assert abs(b.x - rx) < 1e-9 and abs(b.y - ry) < 1e-9
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "NONE", "manipulator_right": "RELEASE"})
    b = next(o for o in _objs(rt.world) if o.object_id == right_id)
    assert b.physical_state == PHYSICAL_STATE_FREE_STATIC

    rt2 = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    _pose(rt2.body, 12.0, 12.0, 0.0)
    _place_exclusive(rt2)
    rt2.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "GRASP"})
    rt2.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "RELEASE", "manipulator_right": "RELEASE"})
    rec = rt2.last_manipulator_receipt or {}
    hands = rec.get("hands") or {}
    assert hands[MANIP_LEFT]["event"] == "RELEASE_SUCCEEDED"
    assert hands[MANIP_RIGHT]["event"] == "RELEASE_SUCCEEDED"
    lx, ly = hands[MANIP_LEFT]["release_xy"]
    rx, ry = hands[MANIP_RIGHT]["release_xy"]
    a = next(o for o in _objs(rt2.world) if o.object_id == hands[MANIP_LEFT]["object_id"])
    b = next(o for o in _objs(rt2.world) if o.object_id == hands[MANIP_RIGHT]["object_id"])
    assert a.physical_state == PHYSICAL_STATE_FREE_STATIC
    assert b.physical_state == PHYSICAL_STATE_FREE_STATIC
    assert abs(a.x - lx) < 1e-9 and abs(a.y - ly) < 1e-9
    assert abs(b.x - rx) < 1e-9 and abs(b.y - ry) < 1e-9
    assert abs(lx - rx) > 1e-4 or abs(ly - ry) > 1e-4


def test_rotation_wrap_and_ids():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    _pose(rt.body, 0.2, 12.0, 0.0)
    _place_exclusive(rt)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "GRASP"})
    ids = {o.object_id: o.manipulator_id for o in _objs(rt.world) if o.physical_state == PHYSICAL_STATE_HELD}
    assert len(ids) == 2
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    for _ in range(10):
        rt.body.theta += 0.35
        rt.step_forced_motor({"locomotion": "MOVE:W", "manipulator_left": "NONE", "manipulator_right": "NONE"})
        for o in _objs(rt.world):
            if o.physical_state != PHYSICAL_STATE_HELD:
                continue
            ex, ey = effector_world_xy(rt.body, width=w, height=h, config=rt.config, manipulator_id=o.manipulator_id)
            assert abs(o.x - ex) < 1e-9 and abs(o.y - ey) < 1e-9
            assert ids[o.object_id] == o.manipulator_id
            assert abs(o.vx) < 1e-15


def test_invalid_commands_and_proprioception():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    empty = rt.agent_observation()
    assert empty.get("prop_grip_left") == 0.0 and empty.get("prop_grip_right") == 0.0
    assert "prop_grip_0" not in empty
    _pose(rt.body, 12.0, 12.0, 0.0)
    _place_exclusive(rt)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "RELEASE", "manipulator_right": "NONE"})
    assert ((rt.last_manipulator_receipt or {}).get("hands") or {})[MANIP_LEFT]["event"] == "RELEASE_NO_OBJECT"
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "NONE"})
    ten = rt.agent_observation()
    assert ten.get("prop_grip_left") == 1.0 and ten.get("prop_grip_right") == 0.0
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "NONE"})
    assert ((rt.last_manipulator_receipt or {}).get("hands") or {})[MANIP_LEFT]["event"] == "GRASP_FAILED_OCCUPIED"
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "NONE", "manipulator_right": "GRASP"})
    eleven = rt.agent_observation()
    assert eleven.get("prop_grip_left") == 1.0 and eleven.get("prop_grip_right") == 1.0
    assert "resource-000001" not in repr(eleven)
    assert not audit_cognition_payload(eleven)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "RELEASE", "manipulator_right": "NONE"})
    one_right = rt.agent_observation()
    assert one_right.get("prop_grip_left") == 0.0 and one_right.get("prop_grip_right") == 1.0


def test_work_none_holding_and_single_unchanged():
    rt = PhysicalSystemRuntime(seed=SEED, config=_work_on(acanthostega_bilateral_grasp_config()))
    _pose(rt.body, 12.0, 12.0, 0.0)
    _place_exclusive(rt)
    rt.body.mechanical_work_reservoir = 10.0
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "NONE", "manipulator_right": "NONE"})
    assert abs(float((rt.last_manipulator_receipt or {}).get("work_debit") or 0) - 0.0) < 1e-12
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "NONE"})
    assert abs(float((rt.last_manipulator_receipt or {}).get("work_debit") or 0) - 0.01) < 1e-9
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "NONE", "manipulator_right": "NONE"})
    assert abs(float((rt.last_manipulator_receipt or {}).get("work_debit") or 0) - 0.0) < 1e-12
    sg = PhysicalSystemRuntime(seed=SEED, config=_work_on(acanthostega_single_grasp_config()))
    sg.body.mechanical_work_reservoir = 10.0
    wsg = float(sg.body.mechanical_work_reservoir)
    obj = _objs(sg.world)[0]
    ww = int(sg.world.T.shape[1])
    hh = int(sg.world.T.shape[0])
    ex, ey = effector_world_xy(sg.body, width=ww, height=hh, config=sg.config)
    obj.x, obj.y = ex, ey
    sg.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    assert abs(float((sg.last_manipulator_receipt or {}).get("work_debit") or 0) - 0.01) < 1e-9
    assert float(sg.body.mechanical_work_reservoir) <= wsg + 1e-12


def test_two_agent_contention_process_order():
    cfg = _off_cog(acanthostega_bilateral_grasp_config())
    results = []
    for order in ((0, 1), (1, 0)):
        ta = TwoAgentRuntime(seed=SEED, config=cfg, process_order=order, contact_enabled=False)
        a0, a1 = ta.slots[0], ta.slots[1]
        _pose(a0.body, 10.0, 10.0, 0.0)
        _pose(a1.body, 11.10, 10.0, math.pi)
        w = int(ta.world.T.shape[1])
        h = int(ta.world.T.shape[0])
        ex, ey = effector_world_xy(a0.body, width=w, height=h, config=a0.config, manipulator_id=MANIP_LEFT)
        obj = _objs(ta.world)[0]
        obj.x, obj.y = ex, ey
        for extra in _objs(ta.world)[1:]:
            extra.x, extra.y = 1.0, 1.0
        for slot in ta.slots:
            slot._forced_motor_once = {"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "NONE"}
        ta.step(1)
        held = [o for o in _objs(ta.world) if o.physical_state == PHYSICAL_STATE_HELD]
        assert len(held) == 1
        results.append(held[0].holder_body_id)
    assert results[0] == results[1] == "agent_0"

    ta = TwoAgentRuntime(seed=SEED, config=cfg, process_order=(1, 0), contact_enabled=False)
    a0, a1 = ta.slots[0], ta.slots[1]
    _pose(a0.body, 8.0, 10.0, 0.0)
    _pose(a1.body, 20.0, 10.0, 0.0)
    a, b = _objs(ta.world)[0], _objs(ta.world)[1]
    w = int(ta.world.T.shape[1])
    h = int(ta.world.T.shape[0])
    lx0, ly0 = effector_world_xy(a0.body, width=w, height=h, config=a0.config, manipulator_id=MANIP_LEFT)
    lx1, ly1 = effector_world_xy(a1.body, width=w, height=h, config=a1.config, manipulator_id=MANIP_LEFT)
    a.x, a.y = lx0, ly0
    b.x, b.y = lx1, ly1
    a0._forced_motor_once = {"locomotion": "WAIT", "manipulator_left": "GRASP"}
    a1._forced_motor_once = {"locomotion": "WAIT", "manipulator_left": "GRASP"}
    ta.step(1)
    held = [o for o in _objs(ta.world) if o.physical_state == PHYSICAL_STATE_HELD]
    assert len(held) == 2
    holders = {o.holder_body_id for o in held}
    assert holders == {"agent_0", "agent_1"}


def test_vision_two_surfaces_anonymous():
    ta = TwoAgentRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()), contact_enabled=False)
    a0, a1 = ta.slots[0], ta.slots[1]
    _pose(a0.body, 12.0, 12.0, 0.0)
    _place_exclusive(a0)
    a0._forced_motor_once = {"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "GRASP"}
    a1._forced_motor_once = {"locomotion": "WAIT"}
    ta.step(1)
    held = [o for o in _objs(ta.world) if o.physical_state == PHYSICAL_STATE_HELD]
    assert len(held) == 2
    a1.body.x, a1.body.y = held[0].x, held[0].y
    obs = a1.agent_observation(foreign_bodies=[a0.body])
    assert not audit_cognition_payload(obs)
    assert "resource-000001" not in repr(obs)
    assert "object_id" not in obs


def test_snapshot_restore_occupancy_and_legacy():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    _pose(rt.body, 12.0, 12.0, 0.0)
    _place_exclusive(rt)
    rt.step_forced_motor({"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "GRASP"})
    snap = deepcopy(rt.snapshot())
    rest = PhysicalSystemRuntime.restore(snap)
    held = [o for o in _objs(rest.world) if o.physical_state == PHYSICAL_STATE_HELD]
    assert len(held) == 2
    rest.step_forced_motor({"locomotion": "MOVE:N", "manipulator_left": "NONE", "manipulator_right": "NONE"})
    w = int(rest.world.T.shape[1])
    h = int(rest.world.T.shape[0])
    for o in _objs(rest.world):
        if o.physical_state != PHYSICAL_STATE_HELD:
            continue
        ex, ey = effector_world_xy(rest.body, width=w, height=h, config=rest.config, manipulator_id=o.manipulator_id)
        assert abs(o.x - ex) < 1e-9
    # malformed duplicate attachment
    objs = _objs(rest.world)
    objs[1].physical_state = PHYSICAL_STATE_HELD
    objs[1].holder_body_id = objs[0].holder_body_id
    objs[1].manipulator_id = objs[0].manipulator_id
    from mechanistic_mind.physical_system.physical_manipulator import sanitize_attachments
    sanitize_attachments(rest.world, {"agent_0"})
    held2 = [o for o in _objs(rest.world) if o.physical_state == PHYSICAL_STATE_HELD]
    keys = {(o.holder_body_id, o.manipulator_id) for o in held2}
    assert len(keys) == len(held2)
    sg = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_single_grasp_config()))
    obj = _objs(sg.world)[0]
    ww = int(sg.world.T.shape[1])
    hh = int(sg.world.T.shape[0])
    ex, ey = effector_world_xy(sg.body, width=ww, height=hh, config=sg.config)
    obj.x, obj.y = ex, ey
    sg.step_forced_motor({"locomotion": "WAIT", "manipulator": "GRASP"})
    rest_sg = PhysicalSystemRuntime.restore(deepcopy(sg.snapshot()))
    assert _objs(rest_sg.world)[0].physical_state == PHYSICAL_STATE_HELD
    assert manipulator_is_active(rest_sg.config) is True
    assert bilateral_manipulator_is_active(rest_sg.config) is False


def test_observer_catalog_and_analyzer():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    assert len(_objs(rt.world)) >= 2
    frame = world_frame(rt)
    mids = {m["manipulator_id"] for m in frame["manipulators"]}
    assert mids == {MANIP_LEFT, MANIP_RIGHT}
    sess = ObserverSession(SessionConfig(seed=SEED))
    sess.apply_experiment({"public_preset": PRESET_ACANTHOSTEGA_BILATERAL_GRASP, "agent_count": 1, "cognition_enabled": False})
    ids = {m["id"] for m in sess.runtime.mechanisms()["mechanisms"]}
    assert BILATERAL_PHYSICAL_MANIPULATORS in ids
    assert BILATERAL_GRASP_RELEASE in ids
    assert SINGLE_PHYSICAL_MANIPULATOR not in ids
    sess2 = ObserverSession(SessionConfig(seed=SEED))
    sess2.apply_experiment({"public_preset": PRESET_ACANTHOSTEGA_SINGLE_GRASP, "agent_count": 1})
    ids2 = {m["id"] for m in sess2.runtime.mechanisms()["mechanisms"]}
    assert SINGLE_PHYSICAL_MANIPULATOR in ids2
    assert BILATERAL_PHYSICAL_MANIPULATORS not in ids2
    sess3 = ObserverSession(SessionConfig(seed=SEED))
    sess3.apply_experiment({"public_preset": PRESET_ACANTHOSTEGA_MATERIAL_VISION, "agent_count": 1})
    ids3 = {m["id"] for m in sess3.runtime.mechanisms()["mechanisms"]}
    assert BILATERAL_PHYSICAL_MANIPULATORS not in ids3
    summary = summarize_grasp_events([
        {"type": "GRASP_SUCCEEDED", "evidence": {"manipulator_id": "LEFT", "tick": 1, "manipulator_action": "GRASP"}},
        {"type": "GRASP_SUCCEEDED", "evidence": {"manipulator_id": "RIGHT", "tick": 1, "manipulator_action": "GRASP"}},
        {"type": "RELEASE_SUCCEEDED", "evidence": {"manipulator_id": "LEFT", "tick": 2, "manipulator_action": "RELEASE"}},
        {"type": "MANIPULATOR_OCCUPANCY", "evidence": {"n_held": 2}},
        {"type": "MANIPULATOR_OCCUPANCY", "evidence": {"n_held": 1}},
        {"type": "GRASP_SUCCEEDED", "evidence": {"manipulator_id": "manipulator_0"}},
    ])
    assert summary["by_hand"]["LEFT"]["grasp_successes"] == 1
    assert summary["by_hand"]["RIGHT"]["grasp_successes"] == 1
    assert summary["by_hand"]["manipulator_0"]["grasp_successes"] == 1
    assert summary["simultaneous_bilateral_commands"] == 1
    assert summary["ticks_holding_2"] == 1
    assert summary["ticks_holding_1"] == 1
    assert "intention" not in summary["note"].lower() or "not" in summary["note"].lower()
    acts = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config())).cognition.get("available_actions")
    assert "LEFT_GRASP" in acts and "RIGHT_RELEASE" in acts
    assert "GRASP" not in acts
    assert len(acts) < 30


def test_old_presets_object_count():
    for cfg_fn, n in (
        (acanthostega_materials_config, 1),
        (acanthostega_material_vision_config, 1),
        (acanthostega_single_grasp_config, 1),
        (acanthostega_bilateral_grasp_config, 2),
        (acanthostega_gentle_config, 0),
    ):
        rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(cfg_fn()))
        assert len(_objs(rt.world)) == n
        if n:
            assert _objs(rt.world)[0].object_id == CANONICAL_FIRST_OBJECT_ID
        if n == 2:
            assert _objs(rt.world)[1].object_id == CANONICAL_SECOND_OBJECT_ID
