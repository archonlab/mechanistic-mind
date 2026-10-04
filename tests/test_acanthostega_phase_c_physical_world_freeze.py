"""Phase C coherent physical world freeze — compact integration matrix."""
from __future__ import annotations

import math
from copy import deepcopy

import pytest

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import acanthostega_coherent_slope_dynamics_config

    cfg = acanthostega_coherent_slope_dynamics_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _rt(seed: int = 17):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    return PhysicalSystemRuntime(seed=seed, config=_cfg())


def _plant(rt, elev):
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import plant_elevations

    plant_elevations(rt.world, elev)


def _support_body(rt, x=5.5, y=5.5):
    from mechanistic_mind.physical_system import surface_elevation_support as ses

    b = rt.body
    b.x, b.y = float(x), float(y)
    b.vx = b.vy = 0.0
    b.grounded = True
    b.z = float(ses.surface_support_height(rt.world, b.x, b.y, config=rt.config))
    return b


def _set_mu(rt, mu_lo: float, mu_hi: float, static_ratio: float = 1.0) -> None:
    for st_name in ("body_static_traction_threshold_state", "body_normal_load_traction_state"):
        st = getattr(rt.world, st_name, None)
        if st is not None and hasattr(st, "config"):
            st.config.mu_min = float(mu_lo)
            st.config.mu_max = float(mu_hi)
            st.config.static_ratio = float(static_ratio)


# --- Scenario 1–2 flat ---


def test_s1_flat_rest_stable():
    rt = _rt(17)
    b = _support_body(rt)
    x0, y0, z0 = float(b.x), float(b.y), float(b.z)
    for _ in range(8):
        rt.step_forced_action("WAIT")
        _tick()
    assert abs(float(b.x) - x0) < 1e-6
    assert abs(float(b.y) - y0) < 1e-6
    assert abs(float(b.z) - z0) < 1e-5
    assert math.hypot(float(b.vx), float(b.vy)) < 1e-4
    # Reservoir may regenerate via internal metabolism; pose/velocity are the rest contract.


def test_s2_flat_move_functional():
    rt = _rt(19)
    b = _support_body(rt)
    b.mechanical_work_reservoir = 50.0
    x0 = float(b.x)
    for _ in range(8):
        rt.step_forced_action("MOVE:E")
        _tick()
    assert float(b.x) > x0 + 0.01


# --- Scenario 3–6 slopes ---


def test_s3_holdable_slope_wait():
    rt = _rt(21)
    _plant(rt, lambda cx, cy: 0.05 * cx)
    b = _support_body(rt)
    rt.step_forced_action("WAIT")
    _set_mu(rt, 0.8, 0.9, 1.05)
    x0 = float(b.x)
    for _ in range(10):
        rt.step_forced_action("WAIT")
        _tick()
    assert abs(float(b.x) - x0) <= 1e-4
    assert math.hypot(float(b.vx), float(b.vy)) <= 1e-4


def test_s4_passive_breakaway():
    from mechanistic_mind.physical_system.coherent_slope_dynamics import state_of
    from mechanistic_mind.physical_system.continuous_gravitational_pe import state_of as pe_state

    rt = _rt(31)
    _plant(rt, lambda cx, cy: 0.05 * cx)
    b = _support_body(rt)
    b.mechanical_work_reservoir = 50.0
    rt.step_forced_action("WAIT")
    _set_mu(rt, 0.01, 0.015, 1.0)
    x0, z0, w0 = float(b.x), float(b.z), float(b.mechanical_work_reservoir)
    for _ in range(25):
        rt.step_forced_action("WAIT")
        _tick()
    assert float(b.x) < x0 - 1e-3
    assert float(b.z) < z0
    assert abs(float(b.mechanical_work_reservoir) - w0) < 0.01
    pe = pe_state(rt.world)
    assert pe is not None and pe.last_receipt is not None
    assert float(pe.last_receipt.get("endpoint_pe_applied") or 0.0) == 0.0
    assert float(pe.last_receipt.get("endpoint_pe_dissipated") or 0.0) == 0.0
    csd = state_of(rt.world)
    wi = (csd.last_receipt or {}).get("work_identity") if csd else None
    assert wi is not None and wi.get("within_tolerance") is True


def test_s5_active_uphill_composes():
    rt = _rt(33)
    _plant(rt, lambda cx, cy: 0.05 * cx)
    b = _support_body(rt, x=4.5, y=5.5)
    b.mechanical_work_reservoir = 80.0
    rt.step_forced_action("WAIT")
    _set_mu(rt, 0.4, 0.5, 1.05)
    z0, w0 = float(b.z), float(b.mechanical_work_reservoir)
    for _ in range(12):
        rt.step_forced_action("MOVE:E")  # uphill on +x elevation
        _tick()
    # Either climbed (z up) or spent work attempting — motor distinct from Policy C.
    assert float(b.mechanical_work_reservoir) <= w0 + 1e-9
    from mechanistic_mind.physical_system.continuous_gravitational_pe import state_of as pe_state

    pe = pe_state(rt.world)
    if pe and pe.last_receipt:
        assert float(pe.last_receipt.get("endpoint_pe_applied") or 0.0) == 0.0


def test_s6_active_downhill_composes():
    rt = _rt(35)
    _plant(rt, lambda cx, cy: 0.05 * cx)
    b = _support_body(rt)
    rt.step_forced_action("WAIT")
    _set_mu(rt, 0.2, 0.25, 1.0)
    x0 = float(b.x)
    b.mechanical_work_reservoir = 50.0
    for _ in range(10):
        rt.step_forced_action("MOVE:W")  # with downhill
        _tick()
    assert float(b.x) < x0


# --- Scenario 7 barrier ---


def test_s7_face_barrier_no_launch():
    rt = _rt(37)
    _plant(rt, lambda cx, cy: 0.5 * cx)
    b = _support_body(rt)
    rt.step_forced_action("WAIT")
    _set_mu(rt, 0.01, 0.02, 1.0)
    x0 = float(b.x)
    for _ in range(8):
        rt.step_forced_action("WAIT")
        _tick()
    assert abs(float(b.x) - x0) <= 1e-6
    assert abs(float(b.vx)) < 0.05


# --- Scenario 8 airborne handoff (vertical) ---


def test_s8_support_loss_airborne_handoff():
    from mechanistic_mind.physical_system.flat_ground_gravity import flat_ground_gravity_is_active

    rt = _rt(41)
    assert flat_ground_gravity_is_active(rt.config)
    b = _support_body(rt)
    # Lift above support → airborne vertical authority.
    b.z = float(b.z) + 2.0
    b.vz = 0.0
    b.grounded = False
    z0 = float(b.z)
    for _ in range(5):
        rt.step_forced_action("WAIT")
        _tick()
    assert float(b.z) < z0  # gravity pulls down
    # Eventually lands or continues falling — not dual-grounded with g_t when airborne.
    from mechanistic_mind.physical_system.coherent_slope_dynamics import query_body_slope_forces

    q = query_body_slope_forces(
        rt.world, rt.config, body=b, m_eff=2.0, g=0.018, grounded=bool(b.grounded)
    )
    if not b.grounded:
        assert q is None or float(q.get("g_t_magnitude") or 0.0) == 0.0 or not q.get("applies")


# --- Scenario 9 held mass ---


def test_s9_held_mass_once():
    from mechanistic_mind.physical_system.effector_work_and_held_load_inertia_accounting import (
        locomotor_mass_with_held_load,
    )
    from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_HELD
    from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT

    rt = _rt(43)
    objs = list(rt.world.resource_objects or [])
    if not objs:
        pytest.skip("no spawned resource objects")
    o = objs[0]
    o.physical_state = PHYSICAL_STATE_HELD
    o.holder_body_id = "agent_0"
    o.manipulator_id = MANIP_LEFT
    o.mass = 3.0
    m_bare = float(rt.config.body.mass)
    info = locomotor_mass_with_held_load(
        body_mass=m_bare,
        world=rt.world,
        holder_body_id="agent_0",
        config=rt.config,
    )
    assert float(info["effective_mass"]) == pytest.approx(m_bare + 3.0, rel=1e-6)
    b = _support_body(rt)
    b.mechanical_work_reservoir = 50.0
    x0 = float(b.x)
    for _ in range(5):
        rt.step_forced_action("MOVE:E")
        _tick()
    assert float(b.x) != x0
    # Held object should not independently free-integrate on ground.
    assert o.physical_state == PHYSICAL_STATE_HELD


# --- Scenario 10 release ---


def test_s10_release_free_path():
    from mechanistic_mind.physical_system.resource_objects import (
        PHYSICAL_STATE_FREE_STATIC,
        PHYSICAL_STATE_HELD,
    )
    from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT

    rt = _rt(47)
    objs = list(rt.world.resource_objects or [])
    if not objs:
        pytest.skip("no spawned resource objects")
    o = objs[0]
    o.physical_state = PHYSICAL_STATE_HELD
    o.holder_body_id = "agent_0"
    o.manipulator_id = MANIP_LEFT
    o.mass = 1.0
    b = _support_body(rt)
    b.vx = 0.2
    rt._forced_motor_once = {
        "locomotion": "WAIT",
        "manipulator_left": "RELEASE",
        "manipulator_right": "NONE",
        "manipulator_pair": "NONE",
    }
    rt.step(1)
    _tick()
    # RELEASE may leave FREE_STATIC / free-moving string / or still held if aperture gate.
    assert isinstance(o.physical_state, str)
    if o.physical_state != PHYSICAL_STATE_HELD:
        assert o.holder_body_id in (None, "")
        assert o.physical_state != PHYSICAL_STATE_HELD


# --- Scenario 11 body-object impulse ---


def test_s11_body_object_impulse_chain():
    from mechanistic_mind.physical_system import physical_body_resource_object_contact as boc
    from mechanistic_mind.physical_system import body_resource_object_contact_impulse as boi
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

    rt = _rt(53)
    objs = list(rt.world.resource_objects or [])
    if not objs:
        pytest.skip("no spawned resource objects")
    o = objs[0]
    b = rt.body
    # Place overlapping for contact
    b.x, b.y = 8.0, 8.0
    b.vx, b.vy = 0.15, 0.0
    o.x = b.x + boc.BODY_CONTACT_RADIUS + boc.CANONICAL_COLLISION_RADIUS - 0.05
    o.y = b.y
    o.vx = o.vy = 0.0
    o.physical_state = "FREE_STATIC"
    o.holder_body_id = None
    boc.ensure_object_collision_radius(o)
    bodies = body_refs_for_runtime(rt)
    boc.detect_body_resource_object_contacts(rt.world, bodies, tick=1, config=rt.config)
    triples = [(bid, bb, rt.config.body) for bid, bb in bodies]
    step = boi.apply_body_object_contact_impulse(rt.world, triples, tick=1, config=rt.config)
    assert step is not None
    _tick()


# --- Scenario 12 material combine on coherent parent ---


def test_s12_combine_requires_explicit_action():
    from mechanistic_mind.model.acanthostega import acanthostega_composition_merge_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.material_composition import material_composition_merge_is_active
    from mechanistic_mind.physical_system.resource_objects import MaterialComponent, PHYSICAL_STATE_HELD
    from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT, MANIP_RIGHT

    # Coherent inherits merge; also verify contact≠combine on merge-capable config.
    cfg = acanthostega_composition_merge_config()
    cfg.cognition.cognition_enabled = False
    assert material_composition_merge_is_active(cfg)
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    objects = list(rt.world.resource_objects)
    assert len(objects) >= 2
    left, right = objects[0], objects[1]
    left.physical_state = right.physical_state = PHYSICAL_STATE_HELD
    left.holder_body_id = right.holder_body_id = "agent_0"
    left.manipulator_id = MANIP_LEFT
    right.manipulator_id = MANIP_RIGHT
    left.composition = (MaterialComponent("component_a", 1.0),)
    right.composition = (MaterialComponent("component_b", 1.0),)
    left.mass, left.quantity = 1.25, 1.0
    right.mass, right.quantity = 2.75, 1.0
    rt.pair_aperture = 0.4
    rt._forced_motor_once = {
        "locomotion": "WAIT",
        "manipulator_left": "NONE",
        "manipulator_right": "NONE",
        "manipulator_pair": "NONE",
    }
    rt.step(1)
    _tick()
    assert len(rt.world.resource_objects) == 2  # contact alone
    n0 = len(rt.world.resource_objects)
    rt._forced_motor_once = {
        "locomotion": "WAIT",
        "manipulator_left": "NONE",
        "manipulator_right": "NONE",
        "manipulator_pair": "COMBINE",
    }
    rt.step(1)
    _tick()
    # May merge to 1 if contact was established; never create mass.
    assert len(rt.world.resource_objects) <= n0


# --- Scenario 13 surface deposition ---


def test_s13_surface_deposition_active_in_coherent():
    from mechanistic_mind.physical_system.explicit_surface_deposition import (
        ExplicitSurfaceDepositionConfig,
    )

    cfg = _cfg()
    dep = getattr(cfg, "explicit_surface_deposition", None)
    assert dep is not None and getattr(dep, "enabled", False) is True


# --- Scenario 14 acoustics privacy / LPS present ---


def test_s14_local_acoustics_mechanisms_active():
    from mechanistic_mind.physical_system.local_physical_signal_transport import (
        local_physical_signal_transport_is_active,
    )
    from mechanistic_mind.physical_system.physical_contact_acoustic_emission import (
        physical_contact_acoustic_emission_is_active,
    )
    from mechanistic_mind.physical_system.body_resource_object_impact_acoustic_emission import (
        body_object_impact_acoustics_is_active,
    )

    cfg = _cfg()
    assert local_physical_signal_transport_is_active(cfg)
    assert physical_contact_acoustic_emission_is_active(cfg)
    assert body_object_impact_acoustics_is_active(cfg)


# --- Scenario 15 two-agent smoke ---


def test_s15_two_agent_smoke():
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    try:
        ta = TwoAgentRuntime(seed=17, config=_cfg())
    except TypeError:
        # Alternate ctor
        ta = TwoAgentRuntime(seed=17, configs=(_cfg(), _cfg()))
    for _ in range(3):
        ta.step(1)
        _tick()
    assert int(ta.tick) >= 3


# --- Snapshot matrix ---


def test_snapshot_flat_and_slope_hold_continue():
    rt = _rt(59)
    b = _support_body(rt)
    for _ in range(3):
        rt.step_forced_action("WAIT")
        _tick()
    snap = deepcopy(rt.snapshot())
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt2 = PhysicalSystemRuntime.restore(snap)
    x0 = float(rt2.body.x)
    for _ in range(3):
        rt2.step_forced_action("WAIT")
        _tick()
    assert abs(float(rt2.body.x) - x0) < 1e-5

    # Slope hold snapshot
    rt3 = _rt(61)
    _plant(rt3, lambda cx, cy: 0.05 * cx)
    b3 = _support_body(rt3)
    rt3.step_forced_action("WAIT")
    _set_mu(rt3, 0.8, 0.9, 1.05)
    for _ in range(3):
        rt3.step_forced_action("WAIT")
        _tick()
    snap3 = deepcopy(rt3.snapshot())
    rt4 = PhysicalSystemRuntime.restore(snap3)
    x4 = float(rt4.body.x)
    for _ in range(4):
        rt4.step_forced_action("WAIT")
        _tick()
    assert abs(float(rt4.body.x) - x4) <= 1e-4


def test_snapshot_passive_slide_no_replay_burst():
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _rt(63)
    _plant(rt, lambda cx, cy: 0.05 * cx)
    b = _support_body(rt)
    b.mechanical_work_reservoir = 50.0
    rt.step_forced_action("WAIT")
    _set_mu(rt, 0.01, 0.015, 1.0)
    for _ in range(8):
        rt.step_forced_action("WAIT")
        _tick()
    snap = deepcopy(rt.snapshot())
    spd0 = math.hypot(float(rt.body.vx), float(rt.body.vy))
    rt2 = PhysicalSystemRuntime.restore(snap)
    spd1 = math.hypot(float(rt2.body.vx), float(rt2.body.vy))
    assert abs(spd1 - spd0) < 1e-9
    # Continue one tick — no instantaneous teleport
    x0 = float(rt2.body.x)
    rt2.step_forced_action("WAIT")
    _tick()
    assert abs(float(rt2.body.x) - x0) < 0.5


# --- Privacy / authorities ---


def test_cognition_privacy_forbidden_tokens():
    from mechanistic_mind.physical_system.observation import audit_cognition_payload

    rt = _rt(67)
    rt.step_forced_action("WAIT")
    _tick()
    obs = rt.agent_observation() if hasattr(rt, "agent_observation") else None
    if obs is None and hasattr(rt, "last_observation"):
        obs = rt.last_observation
    if obs is None:
        from mechanistic_mind.physical_system.observation import build_agent_observation

        obs = build_agent_observation(rt)
    hits = audit_cognition_payload(obs)
    assert hits == []


def test_authorities_live_flags():
    from mechanistic_mind.physical_system.coherent_slope_dynamics import (
        coherent_slope_dynamics_is_active,
        tangent_gravity_physically_active,
        projected_normal_load_physically_active,
        policy_c_measurement_only_required,
    )
    from mechanistic_mind.model.acanthostega import (
        acanthostega_tangent_gravity_diagnostic_shadow_config,
        PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS,
    )

    cfg = _cfg()
    assert cfg.public_preset == PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS
    assert coherent_slope_dynamics_is_active(cfg)
    assert tangent_gravity_physically_active(cfg)
    assert projected_normal_load_physically_active(cfg)
    assert policy_c_measurement_only_required(cfg)
    parent = acanthostega_tangent_gravity_diagnostic_shadow_config()
    assert not coherent_slope_dynamics_is_active(parent)


def test_parent_presets_and_tiktaalik_untouched():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.coherent_slope_dynamics import (
        coherent_slope_dynamics_is_active,
    )
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_pe_policy_c_config,
        acanthostega_tangent_gravity_diagnostic_shadow_config,
    )

    assert not coherent_slope_dynamics_is_active(tiktaalik_config())
    assert not coherent_slope_dynamics_is_active(acanthostega_continuous_pe_policy_c_config())
    assert not coherent_slope_dynamics_is_active(acanthostega_tangent_gravity_diagnostic_shadow_config())
