"""Acanthostega bilateral bring-together — deterministic tests ≤250 ticks."""
from __future__ import annotations

import math
from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    acanthostega_bilateral_grasp_config,
    acanthostega_bring_together_config,
    acanthostega_gentle_config,
    acanthostega_material_vision_config,
    acanthostega_materials_config,
    acanthostega_single_grasp_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BILATERAL_GRASP,
    PRESET_ACANTHOSTEGA_BRING_TOGETHER,
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_ACANTHOSTEGA_MATERIAL_VISION,
    PRESET_ACANTHOSTEGA_MATERIALS,
    PRESET_ACANTHOSTEGA_SINGLE_GRASP,
    PRESET_BETA31,
    acanthostega_bilateral_grasp_mechanism_map,
    acanthostega_bring_together_mechanism_map,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.physical_manipulator import (
    BILATERAL_BRING_TOGETHER,
    BILATERAL_GRASP_RELEASE,
    CANONICAL_LATERAL_OFFSET,
    CANONICAL_OPEN_APERTURE,
    MANIP_LEFT,
    MANIP_RIGHT,
    bring_together_is_active,
    effector_world_xy,
)
from mechanistic_mind.physical_system.resource_objects import (
    CANONICAL_FIRST_OBJECT_ID,
    CANONICAL_INTERACTION_RADIUS,
    CANONICAL_OPTICAL_RADIUS,
    CANONICAL_SECOND_OBJECT_ID,
    PHYSICAL_STATE_FREE_STATIC,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.grasp_summary import summarize_pair_events
from mechanistic_mind.ui.psy_observer_web.serialize import world_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

FROZEN_BETA31_FP_SEED17 = "1621ef2c154864d1"
SEED = 17
HELD = "HELD"


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
    w = int(rt.world.T.shape[1])
    h = int(rt.world.T.shape[0])
    lx, ly = effector_world_xy(rt.body, width=w, height=h, config=rt.config, manipulator_id=MANIP_LEFT, runtime=rt)
    rx, ry = effector_world_xy(rt.body, width=w, height=h, config=rt.config, manipulator_id=MANIP_RIGHT, runtime=rt)
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


def _force(rt, **kw):
    payload = {"locomotion": "WAIT", "manipulator": "NONE", "manipulator_left": "NONE", "manipulator_right": "NONE", "manipulator_pair": "NONE"}
    payload.update(kw)
    rt._forced_motor_once = payload
    rt.step(1)


def _dual_grasp(rt):
    _place_exclusive(rt)
    _force(rt, manipulator_left="GRASP", manipulator_right="GRASP")


def test_preservation_and_preset_separation():
    m = beta31_mechanism_map()
    assert BILATERAL_BRING_TOGETHER not in m
    assert BILATERAL_GRASP_RELEASE not in m
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    assert normalize_preset_name("Acanthostega Phase A Bring Together") == PRESET_ACANTHOSTEGA_BRING_TOGETHER
    assert normalize_preset_name("Acanthostega Phase A Bilateral Grasp") == PRESET_ACANTHOSTEGA_BILATERAL_GRASP
    pb = preset_canonical(PRESET_ACANTHOSTEGA_BILATERAL_GRASP, seed=17)
    pt = preset_canonical(PRESET_ACANTHOSTEGA_BRING_TOGETHER, seed=17)
    assert BILATERAL_BRING_TOGETHER not in pb["mechanisms"]
    assert pt["mechanisms"][BILATERAL_BRING_TOGETHER] is True
    assert BILATERAL_BRING_TOGETHER not in acanthostega_bilateral_grasp_mechanism_map()
    assert acanthostega_bring_together_mechanism_map()[BILATERAL_BRING_TOGETHER] is True
    for name in (
        PRESET_ACANTHOSTEGA_GENTLE,
        PRESET_ACANTHOSTEGA_MATERIALS,
        PRESET_ACANTHOSTEGA_MATERIAL_VISION,
        PRESET_ACANTHOSTEGA_SINGLE_GRASP,
    ):
        assert BILATERAL_BRING_TOGETHER not in preset_canonical(name, seed=17)["mechanisms"]
    bg = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    assert bring_together_is_active(bg.config) is False
    assert "BRING_TOGETHER" not in (bg.cognition.get("available_actions") or [])
    bt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    assert bring_together_is_active(bt.config) is True
    assert "BRING_TOGETHER" in (bt.cognition.get("available_actions") or [])
    assert "SEPARATE" in (bt.cognition.get("available_actions") or [])
    tk = PhysicalSystemRuntime(seed=SEED, config=_off_cog(tiktaalik_config()))
    assert available_actions() == ("WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W")
    assert abs(float(bg.config.bilateral_physical_manipulators.lateral_offset) - CANONICAL_LATERAL_OFFSET) < 1e-12
    for cfg in (
        acanthostega_gentle_config(),
        acanthostega_materials_config(),
        acanthostega_material_vision_config(),
        acanthostega_single_grasp_config(),
    ):
        assert bring_together_is_active(cfg) is False


def test_interaction_radius_separation():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    _dual_grasp(rt)
    a, b = _objs(rt.world)
    a.optical_radius = 8.0
    b.optical_radius = 8.0
    a.interaction_radius = CANONICAL_INTERACTION_RADIUS
    b.interaction_radius = CANONICAL_INTERACTION_RADIUS
    _force(rt, manipulator_pair="NONE")
    assert rt.pair_contact is False
    a.interaction_radius = 0.43
    b.interaction_radius = 0.43
    _force(rt, manipulator_pair="NONE")
    assert rt.pair_contact is True
    bg = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bilateral_grasp_config()))
    _place_exclusive(bg)
    _force(bg, manipulator_left="GRASP", manipulator_right="GRASP")
    oa, ob = _objs(bg.world)
    oa.interaction_radius = 8.0
    ob.interaction_radius = 8.0
    _force(bg, locomotion="WAIT")
    assert getattr(bg, "pair_contact", False) is False
    assert bring_together_is_active(bg.config) is False


def test_empty_hands_bring_together():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    n0 = len(_objs(rt.world))
    ap0 = float(rt.pair_aperture)
    _force(rt, manipulator_pair="BRING_TOGETHER")
    assert float(rt.pair_aperture) < ap0
    rec = rt.last_pair_receipt or {}
    assert rec.get("outcome") == "PAIR_NO_DUAL_OBJECTS"
    assert rec.get("contact_after") is False
    assert len(_objs(rt.world)) == n0


def test_one_held_object_no_contact():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    _place_exclusive(rt)
    _force(rt, manipulator_left="GRASP")
    a = next(o for o in _objs(rt.world) if o.physical_state == HELD)
    cid = a.object_id
    comp = tuple((c.component_id, c.amount) for c in a.composition)
    for _ in range(8):
        _force(rt, manipulator_pair="BRING_TOGETHER")
    held = [o for o in _objs(rt.world) if o.physical_state == HELD]
    assert len(held) == 1
    assert held[0].object_id == cid
    assert tuple((c.component_id, c.amount) for c in held[0].composition) == comp
    assert rt.pair_contact is False


def test_two_held_gradual_contact_no_mixing():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    _dual_grasp(rt)
    ids = sorted(o.object_id for o in _objs(rt.world))
    comps = {o.object_id: tuple((c.component_id, c.amount) for c in o.composition) for o in _objs(rt.world)}
    aps = [float(rt.pair_aperture)]
    began = 0
    for _ in range(12):
        before = float(rt.pair_aperture)
        _force(rt, manipulator_pair="BRING_TOGETHER")
        after = float(rt.pair_aperture)
        aps.append(after)
        assert after <= before + 1e-12
        if str((rt.last_pair_receipt or {}).get("outcome")) == "OBJECT_CONTACT_BEGIN":
            began += 1
    assert aps[0] > aps[-1]
    assert rt.pair_contact is True
    assert began == 1
    assert sorted(o.object_id for o in _objs(rt.world)) == ids
    assert len(_objs(rt.world)) == 2
    for o in _objs(rt.world):
        assert o.physical_state == HELD
        assert tuple((c.component_id, c.amount) for c in o.composition) == comps[o.object_id]
    dist = math.hypot(
        min(abs(_objs(rt.world)[0].x - _objs(rt.world)[1].x), 32 - abs(_objs(rt.world)[0].x - _objs(rt.world)[1].x)),
        min(abs(_objs(rt.world)[0].y - _objs(rt.world)[1].y), 32 - abs(_objs(rt.world)[0].y - _objs(rt.world)[1].y)),
    )
    assert dist + 1e-9 >= 2 * CANONICAL_INTERACTION_RADIUS - 1e-6


def test_contact_persistence_none():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    _dual_grasp(rt)
    for _ in range(12):
        _force(rt, manipulator_pair="BRING_TOGETHER")
    assert rt.pair_contact is True
    ap = float(rt.pair_aperture)
    begins = 0
    for _ in range(5):
        _force(rt, manipulator_pair="NONE")
        kinds = [e.get("type") or e.get("event") for e in rt.structured_events.list(limit=20)]
        begins += sum(1 for k in kinds if k == "HELD_OBJECT_CONTACT_BEGIN")
        assert rt.pair_contact is True
        assert abs(float(rt.pair_aperture) - ap) < 1e-12
    assert begins == 0


def test_separate_reopens():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    _dual_grasp(rt)
    for _ in range(12):
        _force(rt, manipulator_pair="BRING_TOGETHER")
    ends = 0
    for _ in range(16):
        _force(rt, manipulator_pair="SEPARATE")
        if str((rt.last_pair_receipt or {}).get("outcome")) == "OBJECT_CONTACT_END":
            ends += 1
    assert ends == 1
    assert rt.pair_contact is False
    assert abs(float(rt.pair_aperture) - CANONICAL_OPEN_APERTURE) < 1e-9
    assert all(o.physical_state == HELD for o in _objs(rt.world))
    rec = rt.last_pair_receipt or {}
    _force(rt, manipulator_pair="SEPARATE")
    assert (rt.last_pair_receipt or {}).get("outcome") == "PAIR_AT_OPEN_LIMIT"
    assert float((rt.last_pair_receipt or {}).get("work_debit") or 0.0) == 0.0
    _ = rec


def test_independent_release_during_contact():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    _dual_grasp(rt)
    for _ in range(12):
        _force(rt, manipulator_pair="BRING_TOGETHER")
    _force(rt, manipulator_left="RELEASE")
    left = next(o for o in _objs(rt.world) if o.manipulator_id == MANIP_LEFT or (o.physical_state == PHYSICAL_STATE_FREE_STATIC and o.object_id == CANONICAL_FIRST_OBJECT_ID))
    free = [o for o in _objs(rt.world) if o.physical_state == PHYSICAL_STATE_FREE_STATIC]
    held = [o for o in _objs(rt.world) if o.physical_state == HELD]
    assert len(free) == 1
    assert len(held) == 1
    assert held[0].manipulator_id == MANIP_RIGHT
    assert rt.pair_contact is False
    _ = left


def test_locomotion_rotation_wrap():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    _pose(rt.body, 31.2, 16.0, 0.0)
    _dual_grasp(rt)
    for _ in range(6):
        _force(rt, manipulator_pair="BRING_TOGETHER")
    ap = float(rt.pair_aperture)
    ids = sorted(o.object_id for o in _objs(rt.world))
    _force(rt, locomotion="MOVE:E")
    rt.body.theta = 1.2
    _force(rt, locomotion="WAIT")
    assert abs(float(rt.pair_aperture) - ap) < 1e-12
    assert sorted(o.object_id for o in _objs(rt.world)) == ids
    assert len(_objs(rt.world)) == 2


def test_proprioception_anonymous():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    obs = rt.agent_observation()
    assert 0.99 <= float(obs["prop_pair_aperture"]) <= 1.0
    assert float(obs["prop_pair_contact"]) == 0.0
    hits = audit_cognition_payload(obs)
    assert not hits
    _dual_grasp(rt)
    for _ in range(12):
        _force(rt, manipulator_pair="BRING_TOGETHER")
    obs2 = rt.agent_observation()
    assert float(obs2["prop_pair_contact"]) == 1.0
    assert float(obs2["prop_pair_aperture"]) < 0.7
    assert "object_id" not in obs2
    blob = " ".join(f"{k}={v}" for k, v in obs2.items())
    assert CANONICAL_FIRST_OBJECT_ID not in blob


def test_work_proportional_to_delta():
    rt = PhysicalSystemRuntime(seed=SEED, config=_work_on(acanthostega_bring_together_config()))
    rt.body.mechanical_work_reservoir = 10.0
    _force(rt, manipulator_pair="NONE")
    _force(rt, manipulator_pair="BRING_TOGETHER")
    rec = rt.last_pair_receipt or {}
    d = abs(float(rec.get("delta_aperture") or 0.0))
    debit = float(rec.get("work_debit") or 0.0)
    assert abs(debit - 0.02 * d) < 1e-9
    for _ in range(20):
        _force(rt, manipulator_pair="BRING_TOGETHER")
    _force(rt, manipulator_pair="BRING_TOGETHER")
    assert float((rt.last_pair_receipt or {}).get("work_debit") or 0.0) == 0.0
    _force(rt, manipulator_pair="NONE")
    rec_n = rt.last_pair_receipt or {}
    assert float(rec_n.get("work_debit") or 0.0) == 0.0


def test_two_agents_independent_aperture():
    cfg = _off_cog(acanthostega_bring_together_config())
    two = TwoAgentRuntime(seed=SEED, config=cfg)
    a0, a1 = two.slots
    _pose(a0.body, 8.0, 8.0, 0.0)
    _pose(a1.body, 24.0, 24.0, 0.0)
    _place_exclusive(a0)
    a0._forced_motor_once = {"locomotion": "WAIT", "manipulator_left": "GRASP", "manipulator_right": "GRASP", "manipulator_pair": "NONE"}
    two.step(1)
    ap1 = float(a1.pair_aperture)
    for _ in range(6):
        a0._forced_motor_once = {"locomotion": "WAIT", "manipulator_pair": "BRING_TOGETHER"}
        two.step(1)
    assert float(a0.pair_aperture) < CANONICAL_OPEN_APERTURE
    assert abs(float(a1.pair_aperture) - ap1) < 1e-12
    two.process_order = (1, 0)
    ap0 = float(a0.pair_aperture)
    a0._forced_motor_once = {"locomotion": "WAIT", "manipulator_pair": "BRING_TOGETHER"}
    two.step(1)
    assert float(a0.pair_aperture) < ap0


def test_vision_anonymous_only():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    _dual_grasp(rt)
    o0 = rt.agent_observation()
    for _ in range(8):
        _force(rt, manipulator_pair="BRING_TOGETHER")
    o1 = rt.agent_observation()
    keys = set(o1)
    assert not any("mix" in k.lower() or "recipe" in k.lower() or "pair_contact_symbol" in k for k in keys)
    _ = o0


def test_snapshot_restore_roundtrip():
    rt = PhysicalSystemRuntime(seed=SEED, config=_off_cog(acanthostega_bring_together_config()))
    _dual_grasp(rt)
    for _ in range(5):
        _force(rt, manipulator_pair="BRING_TOGETHER")
    snap = rt.snapshot(persist=False)
    assert "pair_aperture" in snap
    rest = PhysicalSystemRuntime.restore(deepcopy(snap))
    assert abs(float(rest.pair_aperture) - float(rt.pair_aperture)) < 1e-12
    assert rest.pair_state == rt.pair_state
    ap = float(rest.pair_aperture)
    rest._forced_motor_once = {"locomotion": "WAIT", "manipulator_pair": "BRING_TOGETHER"}
    rest.step(1)
    assert float(rest.pair_aperture) < ap
    old = {"seed": snap["seed"], "tick": snap["tick"], "config": snap["config"], "world": snap["world"], "body": snap["body"], "internal": snap["internal"]}
    # missing pair fields
    payload = dict(snap)
    payload.pop("pair_aperture", None)
    payload.pop("pair_state", None)
    payload.pop("pair_contact", None)
    payload.pop("last_pair_receipt", None)
    cfg = dict(payload["config"])
    cfg.pop("bilateral_bring_together", None)
    payload["config"] = cfg
    legacy = PhysicalSystemRuntime.restore(payload)
    assert abs(float(legacy.pair_aperture) - CANONICAL_OPEN_APERTURE) < 1e-9
    _ = old


def test_observer_and_analyzer():
    sess = ObserverSession(SessionConfig(seed=SEED))
    sess.apply_experiment({"public_preset": PRESET_ACANTHOSTEGA_BRING_TOGETHER, "agent_count": 1, "cognition_enabled": False})
    frame = world_frame(sess.runtime)
    mans = frame.get("manipulators") or []
    assert any(m.get("kind") == "pair_state" for m in mans)
    assert any(o.get("interaction_radius") is not None for o in (frame.get("resource_objects") or []))
    mechs = {m["id"]: m["enabled"] for m in sess.runtime.mechanisms()["mechanisms"] if isinstance(m, dict) and m.get("id")}
    assert mechs.get(BILATERAL_BRING_TOGETHER) is True
    sess.apply_experiment({"public_preset": PRESET_ACANTHOSTEGA_BILATERAL_GRASP, "agent_count": 1, "cognition_enabled": False})
    mechs2 = {m["id"]: m["enabled"] for m in sess.runtime.mechanisms()["mechanisms"] if isinstance(m, dict) and m.get("id")}
    assert BILATERAL_BRING_TOGETHER not in mechs2 or mechs2.get(BILATERAL_BRING_TOGETHER) is False
    events = [
        {"type": "HELD_OBJECT_CONTACT_BEGIN", "tick": 4, "evidence": {"tick": 4}},
        {"type": "HELD_OBJECT_CONTACT_END", "tick": 9, "evidence": {"tick": 9}},
        {"type": "BODY_CONTACT", "tick": 5},
        {"type": "PAIR_CLOSING", "evidence": {"pair_command": "BRING_TOGETHER", "outcome": "PAIR_CLOSING", "work_debit": 0.001, "aperture_after": 0.7}},
    ]
    s = summarize_pair_events(events)
    assert s["held_object_contact_begin"] == 1
    assert s["held_object_contact_end"] == 1
    assert s["contact_episode_durations"] == [5]
    assert s["agent_body_contact_events"] == 1
    assert s["mixing_claimed"] is False
    assert summarize_pair_events([]).get("legacy_compatible") is True
    assert CANONICAL_OPTICAL_RADIUS != CANONICAL_INTERACTION_RADIUS
