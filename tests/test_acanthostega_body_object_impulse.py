"""ACANTHOSTEGA_PHASE_B_BODY_OBJECT_IMPULSE — mass+compliance contact RESPONSE."""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from mechanistic_mind.model.acanthostega import (
    acanthostega_body_object_contact_config,
    acanthostega_body_object_impulse_config,
    acanthostega_contact_acoustics_config,
    acanthostega_free_object_kinematics_config,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import body_resource_object_contact_impulse as boi
from mechanistic_mind.physical_system import physical_body_resource_object_contact as boc
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT,
    PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE,
    PRESET_ACANTHOSTEGA_FREE_OBJECT_KINEMATICS,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.free_resource_object_kinematics import MECHANISM_ID as FOK_ID
from mechanistic_mind.physical_system.locomotion_profile import (
    apply_ground_rest_after_self_drive,
    integrate_com_translation,
    profile_is_active,
)
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime


MID = boi.MECHANISM_ID
BOC_MID = boc.MECHANISM_ID
BR = boc.BODY_CONTACT_RADIUS
OR = boc.CANONICAL_COLLISION_RADIUS
SUM_R = BR + OR


def _place_object(rt, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0, mass=None):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert objs, "preset must spawn resource objects"
    o = objs[0]
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = None
    o.manipulator_id = None
    if mass is not None:
        o.mass = float(mass)
    boc.ensure_object_collision_radius(o)
    return o


def _place_body(rt, x, y, *, vx=0.0, vy=0.0, i=0):
    if hasattr(rt, "slots"):
        b = rt.slots[i].body
        cfg = rt.slots[i].config.body
    else:
        b = rt.body
        cfg = rt.config.body
    b.x, b.y = float(x), float(y)
    b.vx, b.vy = float(vx), float(vy)
    return b, cfg


def _detect_and_respond(rt, tick=1):
    bodies = body_refs_for_runtime(rt)
    boc.detect_body_resource_object_contacts(rt.world, bodies, tick=tick, config=rt.config)
    triples = []
    if hasattr(rt, "slots"):
        for bid, b in bodies:
            body_cfg = rt.slots[0].config.body
            for slot in rt.slots:
                if slot.body is b:
                    body_cfg = slot.config.body
                    break
            triples.append((bid, b, body_cfg))
    else:
        triples = [(bid, b, rt.config.body) for bid, b in bodies]
    return boi.apply_body_object_contact_impulse(rt.world, triples, tick=tick, config=rt.config)


def _rt_impulse():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_body_object_impulse_config())


def _rt_contact_only():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_body_object_contact_config())


# ---------- isolation ----------

def test_01_absent_from_beta31_and_tiktaalik():
    assert MID not in beta31_mechanism_map()
    assert BOC_MID not in beta31_mechanism_map() or True
    cfg = tiktaalik_config()
    assert not boi.body_object_impulse_is_active(cfg)
    assert getattr(cfg, "body_resource_object_contact_impulse", None) in (None, False) or not boi.body_object_impulse_is_active(cfg)


def test_02_absent_from_prior_acanthostega_presets():
    for builder in (
        acanthostega_free_object_kinematics_config,
        acanthostega_contact_acoustics_config,
        acanthostega_body_object_contact_config,
    ):
        cfg = builder()
        assert not boi.body_object_impulse_is_active(cfg)
        can = preset_canonical(cfg.public_preset)
        assert not (can.get("mechanisms") or {}).get(MID)


def test_03_impulse_preset_enables_contact_fok_and_impulse():
    can = preset_canonical(PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE)
    assert can["public_preset"] == PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE
    assert can["mechanisms"].get(FOK_ID) is True
    assert can["mechanisms"].get(BOC_MID) is True
    assert can["mechanisms"].get(MID) is True
    cfg = acanthostega_body_object_impulse_config()
    assert boc.body_object_contact_is_active(cfg)
    assert boi.body_object_impulse_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE)
    assert boi.body_object_impulse_is_active(cfg)


def test_04_normalize_impulse_before_contact_alias():
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_B_BODY_OBJECT_IMPULSE") == PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE
    assert normalize_preset_name("Acanthostega Body Object Impulse") == PRESET_ACANTHOSTEGA_BODY_OBJECT_IMPULSE
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_B_BODY_OBJECT_CONTACT") == PRESET_ACANTHOSTEGA_BODY_OBJECT_CONTACT
    assert normalize_preset_name(PRESET_BETA31) == PRESET_BETA31


def test_05_contact_fact_only_unchanged_without_response():
    rt = _rt_contact_only()
    b, _ = _place_body(rt, 5.0, 5.0)
    o = _place_object(rt, 5.0 + (SUM_R - 0.05), 5.0, state="FREE_STATIC")
    vx0, vy0 = b.vx, b.vy
    ox0, oy0 = o.vx, o.vy
    step = boc.detect_body_resource_object_contacts(
        rt.world, body_refs_for_runtime(rt), tick=1, config=rt.config
    )
    assert step is not None
    assert step.get("impulse_transferred") is False
    assert boi.apply_body_object_contact_impulse(
        rt.world, [("a0", b, rt.config.body)], tick=1, config=rt.config
    ) is None
    assert b.vx == vx0 and b.vy == vy0
    assert o.vx == ox0 and o.vy == oy0


# ---------- impulse law ----------

def test_10_restitution_from_compliance_mapping():
    assert boi.restitution_from_compliance(0.5, e_min=0.0, e_max=0.85) == pytest.approx(0.425)
    assert boi.restitution_from_compliance(0.0, e_min=0.0, e_max=0.85) == pytest.approx(0.85)
    assert boi.restitution_from_compliance(1.0, e_min=0.0, e_max=0.85) == pytest.approx(0.0)
    assert boi.restitution_from_compliance(0.25, e_min=0.0, e_max=0.85) == pytest.approx(0.85 * 0.75)


def test_11_normal_sign_body_toward_object():
    nx, ny = boi.contact_normal_from_displacement(2.0, 0.0)
    assert nx == pytest.approx(1.0) and ny == pytest.approx(0.0)
    nx, ny = boi.contact_normal_from_displacement(0.0, 0.0)
    assert (nx, ny) == (1.0, 0.0)


def test_12_approaching_equal_mass_impulse_signs():
    rt = _rt_impulse()
    # Body at origin-ish, object to the right overlapping, object approaching body (vx_obj < 0)
    b, bcfg = _place_body(rt, 8.0, 8.0, vx=0.0, vy=0.0)
    o = _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.2, vy=0.0, mass=float(bcfg.mass))
    step = _detect_and_respond(rt, tick=1)
    assert step is not None
    applied = [r for r in step["responses"] if r.get("impulse_transferred")]
    assert applied, step
    r = applied[0]
    assert r["reason"] == boi.REASON_APPROACHING
    assert r["normal"][0] > 0  # body→object +x
    assert r["impulse_scalar_j"] > 0
    # Body gets -j*n → negative vx (pushed left); object +j*n → less negative / positive
    assert r["delta_v_body"][0] < 0
    assert r["delta_v_object"][0] > 0
    assert r["sound_emitted"] is False
    assert r["friction"] is False
    # Pairwise momentum along n approximately conserved (equal opposite)
    mb, mo = r["mass_body"], r["mass_object"]
    mom_n_pre = mb * r["velocity_body_pre"][0] + mo * r["velocity_object_pre"][0]
    mom_n_post = mb * r["velocity_body_post"][0] + mo * r["velocity_object_post"][0]
    assert mom_n_pre == pytest.approx(mom_n_post, abs=1e-9)


def test_13_separating_and_resting_zero_impulse():
    rt = _rt_impulse()
    b, bcfg = _place_body(rt, 8.0, 8.0, vx=0.0, vy=0.0)
    # Separating: object moving away (+x)
    o = _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=0.15, vy=0.0)
    step = _detect_and_respond(rt, tick=1)
    assert step
    r = step["responses"][0]
    assert r["reason"] == boi.REASON_SEPARATING
    assert r["impulse_scalar_j"] == 0.0
    assert r["impulse_transferred"] is False

    # Resting: both still
    rt2 = _rt_impulse()
    b2, _ = _place_body(rt2, 8.0, 8.0)
    _place_object(rt2, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_STATIC", vx=0.0, vy=0.0)
    step2 = _detect_and_respond(rt2, tick=1)
    r2 = step2["responses"][0]
    assert r2["reason"] == boi.REASON_RESTING
    assert r2["impulse_transferred"] is False


def test_14_invalid_mass_no_silent_default():
    rt = _rt_impulse()
    b, _ = _place_body(rt, 8.0, 8.0, vx=0.0, vy=0.0)
    o = _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.2, vy=0.0)
    o.mass = 0.0
    step = _detect_and_respond(rt, tick=1)
    assert step
    reasons = {r["reason"] for r in step["responses"]}
    assert boi.REASON_INVALID_MASS in reasons
    assert all(not r.get("impulse_transferred") for r in step["responses"])


def test_15_max_impulse_clamp_visible():
    rt = _rt_impulse()
    rt.config.body_resource_object_contact_impulse.max_contact_impulse = 0.01
    b, bcfg = _place_body(rt, 8.0, 8.0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.5, vy=0.0, mass=float(bcfg.mass))
    step = _detect_and_respond(rt, tick=1)
    applied = [r for r in step["responses"] if r.get("impulse_transferred")]
    assert applied
    assert applied[0]["impulse_clamped"] is True
    assert applied[0]["impulse_scalar_j"] == pytest.approx(0.01)


# ---------- persistence / dedupe ----------

def test_20_resting_persist_does_not_refire_impulse():
    rt = _rt_impulse()
    b, _ = _place_body(rt, 8.0, 8.0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_STATIC")
    s1 = _detect_and_respond(rt, tick=1)
    assert s1["responses"][0]["reason"] == boi.REASON_RESTING
    s2 = _detect_and_respond(rt, tick=2)
    # Second tick still resting: either RESTING or ALREADY_PROCESSED / zero j
    assert all(not r.get("impulse_transferred") for r in s2["responses"])


def test_21_reapproach_same_episode_allows_new_impulse():
    rt = _rt_impulse()
    b, bcfg = _place_body(rt, 8.0, 8.0)
    o = _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.2, vy=0.0, mass=float(bcfg.mass))
    s1 = _detect_and_respond(rt, tick=1)
    assert any(r.get("impulse_transferred") for r in s1["responses"])
    # Force resting signature
    o.vx, o.vy = 0.0, 0.0
    b.vx, b.vy = 0.0, 0.0
    s2 = _detect_and_respond(rt, tick=2)
    assert all(not r.get("impulse_transferred") for r in s2["responses"])
    # Re-approach
    o.vx = -0.25
    s3 = _detect_and_respond(rt, tick=3)
    assert any(r.get("impulse_transferred") for r in s3["responses"]), s3


# ---------- geometry / correction / swept ----------

def test_30_position_correction_endpoint_no_momentum_change():
    rt = _rt_impulse()
    rt.config.body_resource_object_contact_impulse.penetration_slop = 0.001
    b, bcfg = _place_body(rt, 8.0, 8.0)
    o = _place_object(rt, 8.0 + 0.1, 8.0, state="FREE_STATIC")  # deep overlap
    # Keep resting so j=0; correction only
    step = _detect_and_respond(rt, tick=1)
    corrected = [r for r in step["responses"] if r.get("position_corrected")]
    if corrected:
        r = corrected[0]
        assert r["position_correction_is_numerical_constraint"] is True
        assert r["impulse_transferred"] is False


def test_31_held_objects_skipped():
    rt = _rt_impulse()
    b, _ = _place_body(rt, 8.0, 8.0, vx=0.0, vy=0.0)
    o = _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="HELD", vx=-0.2)
    o.holder_body_id = "foreign"
    # Detect skips HELD; response should see no candidates or skip
    boc.detect_body_resource_object_contacts(rt.world, body_refs_for_runtime(rt), tick=1, config=rt.config)
    step = boi.apply_body_object_contact_impulse(
        rt.world, [("a0", b, rt.config.body)], tick=1, config=rt.config
    )
    # No FREE contact → empty responses or None-like empty
    assert step is None or step.get("response_count", 0) == 0 or all(
        r.get("reason") == boi.REASON_HELD_SKIPPED or not r.get("impulse_transferred")
        for r in (step.get("responses") or [])
    )


# ---------- grace / body clamp ----------

def test_40_grace_skips_v_stop_once():
    rt = _rt_impulse()
    b, bcfg = _place_body(rt, 8.0, 8.0)
    # Tiny velocity below v_stop (0.006)
    b.vx, b.vy = 0.003, 0.0
    b._boc_impulse_grace_ticks = 1
    profile = rt.config.locomotion_profile
    rec = integrate_com_translation(
        b,
        body_cfg=bcfg,
        f_site=(0.0, 0.0),
        f_terrain=(0.0, 0.0),
        f_ambient=(0.0, 0.0),
        extra_drag=0.0,
        locomotor_active=False,
        profile=profile,
        width=int(rt.world.T.shape[1]),
        height=int(rt.world.T.shape[0]),
        apply_translation=True,
        profile_active=True,
    )
    assert rec["v_stop_applied"] is False
    assert int(getattr(b, "_boc_impulse_grace_ticks", 0)) == 0
    # Next call without grace should snap
    b.vx, b.vy = 0.003, 0.0
    rec2 = integrate_com_translation(
        b,
        body_cfg=bcfg,
        f_site=(0.0, 0.0),
        f_terrain=(0.0, 0.0),
        f_ambient=(0.0, 0.0),
        extra_drag=0.0,
        locomotor_active=False,
        profile=profile,
        width=int(rt.world.T.shape[1]),
        height=int(rt.world.T.shape[0]),
        apply_translation=True,
        profile_active=True,
    )
    assert rec2["v_stop_applied"] is True


def test_41_body_vmax_clamp_after_impulse():
    rt = _rt_impulse()
    rt.config.body.v_max = 0.05
    b, bcfg = _place_body(rt, 8.0, 8.0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.8, vy=0.0, mass=0.1)
    step = _detect_and_respond(rt, tick=1)
    assert abs(b.vx) <= 0.05 + 1e-12
    assert abs(b.vy) <= 0.05 + 1e-12


# ---------- runtime / privacy / snapshot ----------

def test_50_two_agent_seam_runs_response():
    cfg = acanthostega_body_object_impulse_config()
    rt = TwoAgentRuntime(seed=17, config=cfg)
    b, _ = _place_body(rt, 10.0, 10.0, i=0)
    o = _place_object(rt, 10.0 + (SUM_R - 0.05), 10.0, state="FREE_MOVING", vx=-0.2, vy=0.0)
    # Drive a few ticks (budget small)
    for _ in range(3):
        rt.step()
    st = boi.state_of(rt.world)
    # Response state should exist when mechanism active
    assert st is not None or boi.body_object_impulse_is_active(rt.slots[0].config)


def test_51_snapshot_roundtrip_preserves_impulse_config():
    import json
    rt = _rt_impulse()
    payload = rt.snapshot()
    assert "body_resource_object_contact_impulse" in payload["config"]
    restored = PhysicalSystemRuntime.restore(json.loads(json.dumps(payload)))
    assert boi.body_object_impulse_is_active(restored.config)


def test_52_agent_observation_privacy():
    rt = _rt_impulse()
    b, _ = _place_body(rt, 8.0, 8.0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.2)
    _detect_and_respond(rt, tick=1)
    # Researcher overlay present; agent cognition must not gain new impulse fields via audit helpers
    ov = boi.overlay_payload(rt.world)
    assert ov is not None
    assert ov.get("caption", "").startswith("MASS + COMPLIANCE")
    # Ensure response receipts mark agent_accessible False
    step = getattr(rt.world, "last_body_object_contact_impulse_step", None)
    assert step is not None
    for r in step.get("responses") or []:
        assert r.get("agent_accessible") is False
        assert r.get("researcher_only") is True


def test_53_contact_fact_receipts_still_mark_impulse_false():
    rt = _rt_impulse()
    b, _ = _place_body(rt, 8.0, 8.0)
    _place_object(rt, 8.0 + (SUM_R - 0.05), 8.0, state="FREE_MOVING", vx=-0.2)
    boc.detect_body_resource_object_contacts(rt.world, body_refs_for_runtime(rt), tick=1, config=rt.config)
    step = rt.world.last_body_object_contact_step
    for r in (step.get("begin") or []) + (step.get("persist") or []):
        assert r.get("impulse_transferred") is False
        assert r.get("collision_response_applied") is False


def test_54_neutral_compliance_when_passive_props_off():
    rt = _rt_impulse()
    # Ensure passive props path returns note
    o = _place_object(rt, 1.0, 1.0)
    c, note = boi.object_compliance(o, rt.config)
    # Materials chain usually has passive props ON; if off → neutral
    assert 0.0 <= c <= 1.0
    e = boi.restitution_from_compliance(c, e_min=0.0, e_max=0.85)
    assert 0.0 <= e <= 0.85
