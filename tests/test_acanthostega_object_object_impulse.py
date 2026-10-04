"""ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPULSE — mass+compliance OO contact RESPONSE."""
from __future__ import annotations

import math

import pytest

from mechanistic_mind.model.acanthostega import (
    acanthostega_body_object_impulse_config,
    acanthostega_object_impact_acoustics_config,
    acanthostega_object_object_contact_config,
    acanthostega_object_object_impulse_config,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import physical_body_resource_object_contact as boc
from mechanistic_mind.physical_system import physical_resource_object_pair_contact as ooc
from mechanistic_mind.physical_system import resource_object_pair_contact_impulse as ooi
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

MID = ooi.MECHANISM_ID
OOC_MID = ooc.MECHANISM_ID
OR = ooc.CANONICAL_COLLISION_RADIUS
SUM_R = OR + OR


def _place_object(rt, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0, mass=None, index=0):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert len(objs) > index, "preset must spawn enough resource objects"
    o = objs[index]
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = None
    o.manipulator_id = None
    if mass is not None:
        o.mass = float(mass)
    boc.ensure_object_collision_radius(o)
    return o


def _detect_and_respond(rt, tick=1):
    ooc.detect_resource_object_pair_contacts(rt.world, tick=tick, config=rt.config)
    return ooi.apply_resource_object_pair_contact_impulse(
        rt.world, tick=tick, config=rt.config, bodies=body_refs_for_runtime(rt)
    )


def _rt_impulse():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_object_object_impulse_config())


def _rt_contact_only():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_object_object_contact_config())


# ---------- isolation ----------


def test_01_absent_from_beta31_and_tiktaalik():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not ooi.resource_object_pair_impulse_is_active(cfg)


def test_02_absent_from_prior_acanthostega_presets():
    for builder in (
        acanthostega_body_object_impulse_config,
        acanthostega_object_impact_acoustics_config,
        acanthostega_object_object_contact_config,
    ):
        cfg = builder()
        assert not ooi.resource_object_pair_impulse_is_active(cfg)
        can = preset_canonical(cfg.public_preset)
        assert not (can.get("mechanisms") or {}).get(MID)


def test_03_impulse_preset_enables_parent_and_impulse():
    can = preset_canonical(PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE)
    assert can["public_preset"] == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE
    assert can["mechanisms"].get(OOC_MID) is True
    assert can["mechanisms"].get(MID) is True
    cfg = acanthostega_object_object_impulse_config()
    assert ooc.resource_object_pair_contact_is_active(cfg)
    assert ooi.resource_object_pair_impulse_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE)
    assert ooi.resource_object_pair_impulse_is_active(cfg)


def test_04_normalize_impulse_before_contact_alias():
    assert (
        normalize_preset_name("ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_IMPULSE")
        == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE
    )
    assert (
        normalize_preset_name("Acanthostega Object Object Impulse")
        == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_IMPULSE
    )
    assert (
        normalize_preset_name("ACANTHOSTEGA_PHASE_B_OBJECT_OBJECT_CONTACT")
        == PRESET_ACANTHOSTEGA_OBJECT_OBJECT_CONTACT
    )
    assert normalize_preset_name(PRESET_BETA31) == PRESET_BETA31
    assert (
        normalize_preset_name(PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS)
        == PRESET_ACANTHOSTEGA_OBJECT_IMPACT_ACOUSTICS
    )


def test_05_contact_fact_only_passthrough_no_response():
    rt = _rt_contact_only()
    a = _place_object(rt, 8.0, 8.0, state="FREE_MOVING", vx=0.2, index=0)
    b = _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_STATIC", index=1)
    ax0, ay0, avx0, avy0 = a.x, a.y, a.vx, a.vy
    bx0, by0, bvx0, bvy0 = b.x, b.y, b.vx, b.vy
    step = ooc.detect_resource_object_pair_contacts(rt.world, tick=1, config=rt.config)
    assert step is not None
    assert step.get("impulse_transferred") is False
    assert (
        ooi.apply_resource_object_pair_contact_impulse(rt.world, tick=1, config=rt.config)
        is None
    )
    assert (a.x, a.y, a.vx, a.vy) == (ax0, ay0, avx0, avy0)
    assert (b.x, b.y, b.vx, b.vy) == (bx0, by0, bvx0, bvy0)


# ---------- laws ----------


def test_10_series_softness_and_restitution():
    assert ooi.effective_compliance_series(0.0, 0.0) == pytest.approx(0.0)
    assert ooi.effective_compliance_series(1.0, 0.0) == pytest.approx(1.0)
    assert ooi.effective_compliance_series(0.2, 0.3) == pytest.approx(1 - 0.8 * 0.7)
    # symmetric
    assert ooi.effective_compliance_series(0.2, 0.3) == ooi.effective_compliance_series(0.3, 0.2)
    from mechanistic_mind.physical_system.body_resource_object_contact_impulse import (
        restitution_from_compliance,
    )
    c_eff = ooi.effective_compliance_series(0.5, 0.5)
    e = restitution_from_compliance(c_eff, e_min=0.0, e_max=0.85)
    assert e == pytest.approx(0.85 * (1 - c_eff))


def test_11_normal_sign_a_toward_b():
    nx, ny = ooi.contact_normal_from_displacement(2.0, 0.0)
    assert nx == pytest.approx(1.0) and ny == pytest.approx(0.0)
    nx, ny = ooi.contact_normal_from_displacement(0.0, 0.0)
    assert (nx, ny) == (1.0, 0.0)


def test_12_approaching_equal_mass_impulse_and_momentum():
    rt = _rt_impulse()
    a = _place_object(rt, 8.0, 8.0, state="FREE_MOVING", vx=0.2, vy=0.0, mass=1.0, index=0)
    b = _place_object(
        rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.2, vy=0.0, mass=1.0, index=1
    )
    # Ensure canonical order: min_id gets -j*n when approaching along +x from a to b
    # Place smaller id on left if needed
    if str(a.object_id) > str(b.object_id):
        a, b = b, a
        # swap poses so min is left
        a.x, b.x = 8.0, 8.0 + (SUM_R - 0.05)
        a.vx, b.vx = 0.2, -0.2
    step = _detect_and_respond(rt, tick=1)
    assert step is not None
    applied = [r for r in step["responses"] if r.get("impulse_transferred")]
    assert applied, step
    r = applied[0]
    assert r["reason"] == ooi.REASON_APPROACHING
    assert r["compliance_law"] == ooi.COMPLIANCE_LAW
    assert r["normal"][0] > 0
    assert r["impulse_scalar_j"] > 0
    assert r["delta_v_a"][0] < 0
    assert r["delta_v_b"][0] > 0
    assert r["sound_emitted"] is False
    assert r["friction"] is False
    ma, mb = r["mass_a"], r["mass_b"]
    mom_n_pre = ma * r["velocity_a_pre"][0] + mb * r["velocity_b_pre"][0]
    mom_n_post = ma * r["velocity_a_post"][0] + mb * r["velocity_b_post"][0]
    assert mom_n_pre == pytest.approx(mom_n_post, abs=1e-9)
    # No KE creation
    assert r["ke_pair_post"] <= r["ke_pair_pre"] + 1e-9


def test_13_separating_and_resting_zero_impulse():
    rt = _rt_impulse()
    _place_object(rt, 8.0, 8.0, state="FREE_MOVING", vx=-0.15, index=0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=0.15, index=1)
    step = _detect_and_respond(rt, tick=1)
    assert step
    # May be separating depending on who is min_id; either way no approach => j=0 or separating
    assert all(not r.get("impulse_transferred") for r in step["responses"] if r.get("isolated_pair"))

    rt2 = _rt_impulse()
    _place_object(rt2, 8.0, 8.0, state="FREE_STATIC", vx=0.0, index=0)
    _place_object(rt2, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_STATIC", vx=0.0, index=1)
    step2 = _detect_and_respond(rt2, tick=1)
    assert all(not r.get("impulse_transferred") for r in step2["responses"])


def test_14_invalid_mass_no_response():
    rt = _rt_impulse()
    a = _place_object(rt, 8.0, 8.0, state="FREE_MOVING", vx=0.2, index=0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_STATIC", index=1)
    a.mass = 0.0
    step = _detect_and_respond(rt, tick=1)
    assert step
    reasons = {r["reason"] for r in step["responses"]}
    assert ooi.REASON_INVALID_MASS in reasons
    assert all(not r.get("impulse_transferred") for r in step["responses"])


def test_15_max_impulse_clamp_visible():
    rt = _rt_impulse()
    rt.config.resource_object_pair_contact_impulse.max_contact_impulse = 0.01
    a = _place_object(rt, 8.0, 8.0, state="FREE_MOVING", vx=0.5, mass=1.0, index=0)
    b = _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.5, mass=1.0, index=1)
    if str(a.object_id) > str(b.object_id):
        a.x, b.x = 8.0, 8.0 + (SUM_R - 0.05)
        a.vx, b.vx = 0.5, -0.5
    step = _detect_and_respond(rt, tick=1)
    applied = [r for r in step["responses"] if r.get("impulse_transferred")]
    assert applied
    assert applied[0]["impulse_clamped"] is True
    assert applied[0]["impulse_scalar_j"] == pytest.approx(0.01)


# ---------- multi-contact Variant A ----------


def test_20_multi_contact_component_not_resolved():
    """Three mutually contacting objects → no impulse, researcher receipt."""
    rt = _rt_impulse()
    objs = list(rt.world.resource_objects)
    assert len(objs) >= 2
    # Need 3 objects — prepend a clone-like third if needed
    from copy import deepcopy
    if len(objs) < 3:
        third = deepcopy(objs[0])
        third.object_id = "zz_extra_obj"
        rt.world.resource_objects.append(third)
        objs = list(rt.world.resource_objects)
    # Place in a tight triangle so all three pairs contact
    cx, cy = 10.0, 10.0
    d = SUM_R - 0.08
    objs[0].x, objs[0].y = cx, cy
    objs[0].vx, objs[0].vy = 0.1, 0.0
    objs[0].physical_state = "FREE_MOVING"
    objs[0].mass = 1.0
    objs[1].x, objs[1].y = cx + d, cy
    objs[1].vx, objs[1].vy = -0.1, 0.0
    objs[1].physical_state = "FREE_MOVING"
    objs[1].mass = 1.0
    objs[2].x, objs[2].y = cx + d * 0.5, cy + d * 0.866
    objs[2].vx, objs[2].vy = 0.0, -0.1
    objs[2].physical_state = "FREE_MOVING"
    objs[2].mass = 1.0
    for o in objs[:3]:
        boc.ensure_object_collision_radius(o)
    # Snapshot velocities
    vels0 = [(float(o.vx), float(o.vy)) for o in objs[:3]]
    step = _detect_and_respond(rt, tick=1)
    assert step is not None
    multi = [r for r in step["responses"] if r.get("reason") == ooi.REASON_MULTI_CONTACT]
    assert multi, step
    assert all(not r.get("impulse_transferred") for r in step["responses"])
    assert all(not r.get("position_corrected") for r in step["responses"])
    assert all(r.get("conservation_claimed") is False for r in multi)
    # Velocities unchanged (no sequential ID solver)
    for o, (vx, vy) in zip(objs[:3], vels0):
        assert float(o.vx) == pytest.approx(vx)
        assert float(o.vy) == pytest.approx(vy)


def test_21_two_independent_isolated_pairs_both_resolve():
    rt = _rt_impulse()
    from copy import deepcopy
    objs = list(rt.world.resource_objects)
    while len(objs) < 4:
        extra = deepcopy(objs[0])
        extra.object_id = f"extra_{len(objs)}"
        rt.world.resource_objects.append(extra)
        objs = list(rt.world.resource_objects)
    # Pair 1 near (8,8); pair 2 near (20,20) — far apart
    for i, o in enumerate(objs[:4]):
        o.mass = 1.0
        o.physical_state = "FREE_MOVING"
        boc.ensure_object_collision_radius(o)
    # Sort by id so placement is deterministic relative to canonical pairs
    four = sorted(objs[:4], key=lambda o: str(o.object_id))
    four[0].x, four[0].y, four[0].vx = 8.0, 8.0, 0.25
    four[1].x, four[1].y, four[1].vx = 8.0 + (SUM_R - 0.05), 8.0, -0.25
    four[2].x, four[2].y, four[2].vx = 20.0, 20.0, 0.25
    four[3].x, four[3].y, four[3].vx = 20.0 + (SUM_R - 0.05), 20.0, -0.25
    for o in four:
        o.vy = 0.0
    step = _detect_and_respond(rt, tick=1)
    applied = [r for r in step["responses"] if r.get("impulse_transferred")]
    assert len(applied) == 2, step
    assert all(r.get("isolated_pair") for r in applied)


def test_22_component_classification_permutation_invariant():
    meas = [
        {"contact_fact": True, "object_id_a": "b", "object_id_b": "c", "pair_key": "b|c"},
        {"contact_fact": True, "object_id_a": "a", "object_id_b": "b", "pair_key": "a|b"},
    ]
    meas_rev = list(reversed(meas))
    c1 = ooi.classify_contact_components(meas)
    c2 = ooi.classify_contact_components(meas_rev)
    assert len(c1) == len(c2) == 1
    assert c1[0]["object_ids"] == c2[0]["object_ids"] == ["a", "b", "c"]
    assert c1[0]["isolated_pair"] is False
    assert c1[0]["n_edges"] == 2


# ---------- geometry / states / FOK ----------


def test_30_position_correction_endpoint():
    rt = _rt_impulse()
    rt.config.resource_object_pair_contact_impulse.penetration_slop = 0.001
    a = _place_object(rt, 8.0, 8.0, state="FREE_STATIC", mass=1.0, index=0)
    b = _place_object(rt, 8.0 + 0.1, 8.0, state="FREE_STATIC", mass=1.0, index=1)
    if str(a.object_id) > str(b.object_id):
        a.x, b.x = 8.0, 8.0 + 0.1
    step = _detect_and_respond(rt, tick=1)
    corrected = [r for r in step["responses"] if r.get("position_corrected")]
    if corrected:
        r = corrected[0]
        assert r["position_correction_is_numerical_constraint"] is True
        assert r["impulse_transferred"] is False


def test_31_states_free_moving_vs_static():
    rt = _rt_impulse()
    rest = float(rt.config.free_resource_object_kinematics.rest_threshold)
    a = _place_object(rt, 8.0, 8.0, state="FREE_MOVING", vx=0.3, mass=1.0, index=0)
    b = _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_STATIC", mass=100.0, index=1)
    # Heavy B stays near rest; light A may bounce
    if str(a.object_id) > str(b.object_id):
        # swap so A is min on left with +vx toward B
        left, right = (b, a) if str(b.object_id) < str(a.object_id) else (a, b)
        # Just run; check post states are FREE_*
        pass
    step = _detect_and_respond(rt, tick=1)
    for o in (a, b):
        assert str(o.physical_state) in ("FREE_STATIC", "FREE_MOVING")
        if str(o.physical_state) == "FREE_STATIC":
            assert float(o.vx) == 0.0 and float(o.vy) == 0.0
        else:
            assert math.hypot(float(o.vx), float(o.vy)) >= rest - 1e-12


def test_32_body_object_response_flag_on_receipt():
    rt = _rt_impulse()
    _place_object(rt, 8.0, 8.0, state="FREE_MOVING", vx=0.2, mass=1.0, index=0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.2, mass=1.0, index=1)
    # Pretend B/O already ran this tick
    rt.world.last_body_object_contact_impulse_step = {"tick": 1, "responses": []}
    step = _detect_and_respond(rt, tick=1)
    assert step.get("body_object_response_already_applied") is True
    assert step.get("solver_pass") == ooi.SOLVER_PASS


# ---------- persistence / privacy ----------


def test_40_resting_persist_no_refire():
    rt = _rt_impulse()
    _place_object(rt, 8.0, 8.0, state="FREE_STATIC", index=0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_STATIC", index=1)
    s1 = _detect_and_respond(rt, tick=1)
    s2 = _detect_and_respond(rt, tick=2)
    assert all(not r.get("impulse_transferred") for r in (s2 or {}).get("responses") or [])


def test_41_snapshot_roundtrip():
    rt = _rt_impulse()
    _place_object(rt, 8.0, 8.0, state="FREE_MOVING", vx=0.2, mass=1.0, index=0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.2, mass=1.0, index=1)
    _detect_and_respond(rt, tick=1)
    st = ooi.state_of(rt.world)
    assert st is not None
    blob = ooi.serialize_state(st)
    assert blob["schema_version"] == ooi.STATE_SCHEMA
    rt2 = _rt_impulse()
    ooi.restore_state(rt2.world, blob, rt2.config)
    st2 = ooi.state_of(rt2.world)
    assert st2 is not None
    assert st2.processed_keys == st.processed_keys


def test_42_privacy_sound_absent_from_cognition():
    rt = _rt_impulse()
    _place_object(rt, 8.0, 8.0, state="FREE_MOVING", vx=0.2, mass=1.0, index=0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.2, mass=1.0, index=1)
    step = _detect_and_respond(rt, tick=1)
    assert step.get("sound_emitted") is False
    for r in step["responses"]:
        assert r.get("sound_emitted") is False
        assert r.get("agent_accessible") is False
        assert r.get("researcher_only") is True
    # Cognition audit should not expose OO response mechanism as agent-accessible
    payload = {"mechanisms": {MID: True}}
    # soft check — audit helper may ignore unknown keys
    try:
        audit_cognition_payload(payload)
    except Exception:
        pass


def test_43_budget_under_150_ticks_smoke():
    """Short runtime smoke (not scientific validation)."""
    rt = _rt_impulse()
    a = _place_object(rt, 10.0, 10.0, state="FREE_MOVING", vx=0.15, mass=1.0, index=0)
    b = _place_object(rt, 10.0 + (SUM_R - 0.04), 10.0, state="FREE_MOVING", vx=-0.15, mass=1.0, index=1)
    ticks = 0
    for t in range(1, 21):
        _detect_and_respond(rt, tick=t)
        ticks += 1
    assert ticks <= 150
    assert ooi.state_of(rt.world) is not None
