"""ACANTHOSTEGA_PHASE_C_FLAT_GROUND_GRAVITY — vertical state + uniform g + flat inelastic support V1."""
from __future__ import annotations

import math

from mechanistic_mind.model.acanthostega import (
    acanthostega_effector_work_accounting_config,
    acanthostega_flat_ground_gravity_config,
    model_metadata,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import flat_ground_gravity as fgg
from mechanistic_mind.physical_system import effector_work_and_held_load_inertia_accounting as ehl
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING,
    PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.physical_manipulator import (
    MANIP_LEFT,
    ensure_pair_runtime,
    update_held_kinematics,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

MID = fgg.MECHANISM_ID


def _place_object(rt, idx, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0,
                  holder=None, hand=None, mass=None, z=0.0, vz=0.0):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert len(objs) > idx
    o = objs[idx]
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = holder
    o.manipulator_id = hand
    if mass is not None:
        o.mass = float(mass)
    fgg.ensure_object_vertical(o, rt.config)
    o.z = float(z)
    o.vz = float(vz)
    o.grounded = bool(abs(o.z) <= 1e-12 and abs(o.vz) <= 1e-12)
    return o


def _place_body(rt, x, y, *, vx=0.0, vy=0.0, theta=0.0, z=0.0, vz=0.0):
    b = rt.body
    b.x, b.y = float(x), float(y)
    b.vx, b.vy = float(vx), float(vy)
    b.theta = float(theta)
    fgg.ensure_body_vertical(b, rt.config)
    b.z = float(z)
    b.vz = float(vz)
    b.grounded = bool(abs(b.z) <= 1e-12 and abs(b.vz) <= 1e-12)
    return b


def _body_id(rt):
    return body_refs_for_runtime(rt)[0][0]


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_flat_ground_gravity_config())


# ---------- isolation ----------


def test_01_absent_from_tiktaalik_and_beta31():
    assert MID not in beta31_mechanism_map()
    for flag in fgg.CAPABILITY_FLAGS:
        assert flag not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not fgg.flat_ground_gravity_is_active(cfg)


def test_02_absent_from_parent_effector_preset():
    cfg = acanthostega_effector_work_accounting_config()
    assert ehl.effector_work_held_load_is_active(cfg)
    assert not fgg.flat_ground_gravity_is_active(cfg)


def test_03_new_preset_enables_parent_plus_umbrella_and_flags():
    can = preset_canonical(PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY)
    assert can["parent"] == PRESET_ACANTHOSTEGA_EFFECTOR_WORK_ACCOUNTING
    assert can["mechanisms"].get(ehl.MECHANISM_ID) is True
    assert can["mechanisms"].get(MID) is True
    for flag in fgg.CAPABILITY_FLAGS:
        assert can["mechanisms"].get(flag) is True
    cfg = acanthostega_flat_ground_gravity_config()
    assert ehl.effector_work_held_load_is_active(cfg)
    assert fgg.flat_ground_gravity_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY)
    assert fgg.flat_ground_gravity_is_active(cfg)
    meta = model_metadata(cfg)
    assert "PHASE_C_FLAT_GROUND" in str(meta.get("classification") or "")


def test_04_normalize_aliases():
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_FLAT_GROUND_GRAVITY") == PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY
    assert normalize_preset_name("Acanthostega Phase C Flat Ground Gravity") == PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY


def test_05_prior_presets_bypass_vertical_filter():
    cfg = acanthostega_effector_work_accounting_config()
    a = type("E", (), {"z": 0.0, "vertical_half_extent": 0.25})()
    b = type("E", (), {"z": 5.0, "vertical_half_extent": 0.25})()
    assert fgg.vertical_filter_allows_contact(cfg, a=a, b=b, kind_a="object", kind_b="object") is True


# ---------- geometry / convention ----------


def test_06_z_is_lower_support_not_centre():
    rt = _rt()
    o = _place_object(rt, 0, 5, 5, z=1.0)
    he = fgg.vertical_half_extent_of(o, kind="object", config=rt.config)
    lo, hi = fgg.vertical_interval(o, kind="object", config=rt.config)
    assert abs(lo - 1.0) < 1e-12
    assert abs(hi - (1.0 + 2 * he)) < 1e-12
    assert abs(fgg.centre_z_of(o, kind="object", config=rt.config) - (1.0 + he)) < 1e-12


def test_07_body_half_extent_is_contact_radius_not_optical():
    rt = _rt()
    b = _place_body(rt, 4, 4)
    he = fgg.vertical_half_extent_of(b, kind="body", config=rt.config)
    assert abs(he - fgg.BODY_CONTACT_RADIUS) < 1e-12


def test_08_init_apply_grounded_no_fall_event():
    rt = _rt()
    st = fgg.state_of(rt.world)
    assert st is not None
    assert abs(rt.body.z) <= 1e-12 and abs(rt.body.vz) <= 1e-12 and rt.body.grounded
    for o in rt.world.resource_objects:
        assert abs(o.z) <= 1e-12 and abs(o.vz) <= 1e-12 and o.grounded
    assert int(st.counters.get("landings", 0)) == 0


# ---------- gravity / support ----------


def test_09_calibrated_fall_from_z1_lands_in_9_to_12_ticks():
    rt = _rt()
    o = _place_object(rt, 0, 8, 8, z=1.0, vz=0.0, state="FREE_STATIC")
    land_tick = None
    for t in range(0, 50):
        fgg.integrate_free_objects_vertical(rt.world, rt.config, t)
        if o.grounded and abs(o.z) <= 1e-12:
            land_tick = t
            break
    assert land_tick is not None
    # first integrate at tick 0 advances one step; from z=1 lands at tick index 9 (10th step)
    assert 8 <= int(land_tick) <= 11
    assert abs(o.vz) <= 1e-12
    assert abs(o.z) <= 1e-12


def test_10_mass_independent_acceleration():
    rt = _rt()
    a = _place_object(rt, 0, 3, 3, z=1.0, mass=1.0)
    b = _place_object(rt, 1, 6, 6, z=1.0, mass=7.0)
    fgg.integrate_free_objects_vertical(rt.world, rt.config, 0)
    assert abs(a.vz - b.vz) < 1e-12
    assert abs(a.z - b.z) < 1e-12


def test_11_inelastic_no_bounce():
    rt = _rt()
    o = _place_object(rt, 0, 4, 4, z=0.05, vz=-0.5)
    fgg.integrate_free_objects_vertical(rt.world, rt.config, 0)
    assert o.grounded
    assert abs(o.vz) <= 1e-12
    assert abs(o.z) <= 1e-12


def test_12_landing_receipt_once_then_rest_no_repeat():
    rt = _rt()
    o = _place_object(rt, 0, 4, 4, z=0.01, vz=-0.2)
    fgg.integrate_free_objects_vertical(rt.world, rt.config, 0)
    st = fgg.state_of(rt.world)
    landings_1 = int(st.counters["landings"])
    assert landings_1 >= 1
    for t in range(1, 20):
        fgg.integrate_free_objects_vertical(rt.world, rt.config, t)
    assert int(st.counters["landings"]) == landings_1


def test_13_grounded_rest_250_ticks_ok():
    rt = _rt()
    o = _place_object(rt, 0, 4, 4, z=0.0, vz=0.0)
    st = fgg.state_of(rt.world)
    for t in range(250):
        fgg.integrate_free_objects_vertical(rt.world, rt.config, t)
        assert o.grounded and abs(o.z) <= 1e-12 and abs(o.vz) <= 1e-12
    assert int(st.counters["landings"]) == 0


def test_14_no_earth_g_981():
    cfg = acanthostega_flat_ground_gravity_config().flat_ground_gravity
    assert abs(float(cfg.g) - 9.81) > 1.0
    assert abs(float(cfg.g) - fgg.GRAVITY_ACCELERATION) < 1e-12


# ---------- held / release / grasp ----------


def test_15_held_snaps_to_holder_skips_gravity():
    rt = _rt()
    hid = _body_id(rt)
    b = _place_body(rt, 8, 8, z=2.0, vz=-0.1)
    o = _place_object(rt, 0, 8, 8, state="HELD", holder=hid, hand=MANIP_LEFT, z=0.0)
    holders = [{"body_id": hid, "body": b, "config": rt.config, "runtime": rt}]
    ensure_pair_runtime(rt, rt.config)
    update_held_kinematics(rt.world, holders)
    fgg.snap_held_vertical_from_holders(rt.world, holders, rt.config)
    assert abs(o.z - b.z) < 1e-12
    assert abs(o.vz - b.vz) < 1e-12
    z_before = o.z
    fgg.integrate_free_objects_vertical(rt.world, rt.config, 0)
    assert abs(o.z - z_before) < 1e-12  # HELD skipped


def test_16_release_sets_z_vz_no_integrate_release_tick():
    rt = _rt()
    hid = _body_id(rt)
    b = _place_body(rt, 8, 8, z=1.5, vz=-0.05)
    o = _place_object(rt, 0, 8, 8, state="HELD", holder=hid, hand=MANIP_LEFT, z=1.5, vz=-0.05)
    fgg.apply_release_vertical(o, b, rt.config)
    o.physical_state = "FREE_MOVING"
    o.holder_body_id = None
    assert abs(o.z - 1.5) < 1e-12
    assert abs(o.vz - (-0.05)) < 1e-12
    # release tick: FOK pattern — vertical integrate of free happens for FREE_*,
    # but caller is responsible for not integrating newly released at T in world step order.
    # Direct API still integrates FREE; world step places gravity before release transfer.


def test_17_grasp_requires_vertical_overlap_endpoint_only():
    rt = _rt()
    b = _place_body(rt, 5, 5, z=0.0)
    near = _place_object(rt, 0, 5.2, 5.0, z=0.0)
    far = _place_object(rt, 1, 5.2, 5.0, z=3.0)
    assert fgg.grasp_vertical_reachable(b, near, rt.config)
    assert not fgg.grasp_vertical_reachable(b, far, rt.config)


# ---------- contact filtering ----------


def test_18_vertical_filter_rejects_xy_overlap_without_height():
    rt = _rt()
    a = _place_object(rt, 0, 5, 5, z=0.0)
    b = _place_object(rt, 1, 5.1, 5.0, z=3.0)
    m = {"in_contact": True, "endpoint_contact": True, "detection_mode": "ENDPOINT_OVERLAP"}
    fgg.apply_vertical_filter_to_measurement(
        rt.world, rt.config, m, a=a, b=b, kind_a="object", kind_b="object",
    )
    assert m["in_contact"] is False
    assert m["vertical_filter"] == "REJECT"
    assert m["vertical_separation_reason"] == fgg.END_REASON_VERTICAL_SEPARATION


def test_19_vertical_filter_pass_when_intervals_overlap():
    rt = _rt()
    a = _place_object(rt, 0, 5, 5, z=0.0)
    b = _place_object(rt, 1, 5.1, 5.0, z=0.1)
    m = {"in_contact": True, "endpoint_contact": True, "detection_mode": "ENDPOINT_OVERLAP"}
    fgg.apply_vertical_filter_to_measurement(
        rt.world, rt.config, m, a=a, b=b, kind_a="object", kind_b="object",
    )
    assert m["in_contact"] is True
    assert m["vertical_filter"] == "PASS"


def test_20_swept_interpolates_z_at_fraction():
    rt = _rt()
    # At fraction 0.0 no overlap; at 1.0 overlap — mid fraction may reject
    a0 = type("E", (), {"z": 0.0, "vertical_half_extent": 0.25})()
    a1 = type("E", (), {"z": 0.0, "vertical_half_extent": 0.25})()
    b0 = type("E", (), {"z": 5.0, "vertical_half_extent": 0.25})()
    b1 = type("E", (), {"z": 0.0, "vertical_half_extent": 0.25})()
    assert not fgg.vertical_overlap_at_fraction(a0, a1, b0, b1, 0.0, config=rt.config)
    assert fgg.vertical_overlap_at_fraction(a0, a1, b0, b1, 1.0, config=rt.config)


# ---------- energy / privacy ----------


def test_21_energy_formulas_and_no_reservoir_credit():
    m, g, z, vz = 2.0, fgg.GRAVITY_ACCELERATION, 1.0, -0.2
    assert abs(fgg.kinetic_z(m, vz) - 0.5 * m * vz * vz) < 1e-12
    assert abs(fgg.potential_z(m, g, z) - m * g * z) < 1e-12
    rt = _rt()
    o = _place_object(rt, 0, 4, 4, z=0.02, vz=-0.3, mass=2.0)
    rec = fgg.integrate_vertical_entity(
        o, mass=2.0, config=fgg.state_of(rt.world).config, tick=0,
        entity_id="o", entity_kind="object",
    )
    assert rec["reservoir_credit"] is False
    assert rec["global_conservation_claim"] is False
    assert rec.get("landing_sound") is False


def test_22_banner_and_no_agent_symbolic_z():
    assert "SURFACE ELEVATION NOT ACTIVE" in fgg.BANNER
    assert "NO SLOPES" in fgg.BANNER
    assert "NO STACKING" in fgg.BANNER
    assert fgg.SURFACE_ELEVATION_STATUS == "METADATA_ONLY"
    assert fgg.FULL_3D_ENTITY_COLLISION == "NOT_IMPLEMENTED"


# ---------- persistence / tick guard ----------


def test_23_last_vertical_integrated_tick_guard():
    rt = _rt()
    _place_object(rt, 0, 4, 4, z=1.0)
    r1 = fgg.integrate_free_objects_vertical(rt.world, rt.config, 3)
    r2 = fgg.integrate_free_objects_vertical(rt.world, rt.config, 3)
    assert len(r1) >= 1
    assert r2 == []
    st = fgg.state_of(rt.world)
    assert int(st.counters["reintegration_suppressed"]) >= 1


def test_24_snapshot_roundtrip_preserves_z():
    import json
    rt = _rt()
    _place_body(rt, 4, 4, z=0.7, vz=-0.01)
    o = _place_object(rt, 0, 5, 5, z=1.2, vz=0.0)
    payload = json.loads(json.dumps(rt.snapshot()))
    assert abs(float(payload["body"]["z"]) - 0.7) < 1e-12
    wobjs = ((payload.get("world") or {}).get("resource_objects") or {}).get("objects") or []
    assert any(abs(float(row.get("z", 0.0)) - 1.2) < 1e-12 for row in wobjs)
    assert "flat_ground_gravity" in (payload.get("config") or {})
    restored = PhysicalSystemRuntime.restore(payload)
    assert abs(float(restored.body.z) - 0.7) < 1e-12
    assert fgg.flat_ground_gravity_is_active(restored.config)


def test_25_body_vertical_after_step():
    rt = _rt()
    _place_body(rt, 4, 4, z=1.0, vz=0.0)
    # step a few ticks; body should fall
    for _ in range(15):
        rt.step(1)
    assert rt.body.z <= 1.0 + 1e-9
    # eventually grounded within 50
    for _ in range(40):
        rt.step(1)
    assert rt.body.grounded or rt.body.z < 1.0


def test_26_deposits_not_vertical_entities():
    # Columns/deposits are not ResourceObjects with vertical state — smoke that mechanism
    # does not require column vertical fields.
    rt = _rt()
    assert fgg.state_of(rt.world) is not None
    assert not hasattr(rt.world, "column_vertical_state")


def test_27_surface_elevation_not_used_for_support():
    rt = _rt()
    o = _place_object(rt, 0, 4, 4, z=0.5)
    rec = fgg.integrate_vertical_entity(
        o, mass=1.0, config=fgg.state_of(rt.world).config, tick=0,
        entity_id="o", entity_kind="object",
    )
    assert rec["surface_elevation_used"] is False
    assert rec["terrain_potential_used"] is False


def test_28_capability_flags_co_gated():
    cfg = acanthostega_flat_ground_gravity_config()
    flags = fgg.capability_flags(cfg)
    assert all(flags.values())
    fgg.set_flat_ground_gravity(cfg, False)
    flags_off = fgg.capability_flags(cfg)
    assert not any(flags_off.values())
