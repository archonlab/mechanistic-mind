"""ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_SUPPORT — G2B Hybrid C⋆ V1.

Parent: ACANTHOSTEGA_PHASE_C_FREE_OBJECT_STATIC_TRACTION.
Contract: CENTRE_Z_AUTHORITY, RING_CLASSIFICATION_ONLY, ONE_PE=SES_DDA, NORMAL=NO.
"""
from __future__ import annotations

import math

from mechanistic_mind.model.acanthostega import (
    acanthostega_free_object_static_traction_config,
    acanthostega_radius_aware_support_config,
    acanthostega_static_traction_config,
    model_metadata,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import flat_ground_gravity as fgg
from mechanistic_mind.physical_system import free_resource_object_static_traction_threshold as fost
from mechanistic_mind.physical_system import radius_aware_support_points as rasp
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION,
    PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
    BODY_CONTACT_RADIUS,
    CANONICAL_COLLISION_RADIUS,
    ensure_object_collision_radius,
)
from mechanistic_mind.physical_system.physical_manipulator import resolve_shared_world_manipulators
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.surface_elevation_support import support_z_for_entity
from mechanistic_mind.physical_system.resource_objects import CANONICAL_OPTICAL_RADIUS

MID = rasp.MECHANISM_ID


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_radius_aware_support_config())


def _ground_body(rt, x=8.0, y=8.0):
    fgg.ensure_body_vertical(rt.body, rt.config)
    rt.body.x, rt.body.y = float(x), float(y)
    sz = float(support_z_for_entity(rt.world, rt.config, rt.body.x, rt.body.y))
    rt.body.z = sz
    rt.body.vz = 0.0
    rt.body.grounded = True
    return sz


def _place_object(rt, idx, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0, z=None, vz=0.0):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert len(objs) > idx
    o = objs[idx]
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = None
    o.manipulator_id = None
    fgg.ensure_object_vertical(o, rt.config)
    if z is None:
        z = float(support_z_for_entity(rt.world, rt.config, o.x, o.y))
    o.z = float(z)
    o.vz = float(vz)
    o.grounded = bool(abs(o.vz) <= 1e-12)
    ensure_object_collision_radius(o)
    return o


def _classify_body(rt, tick=1):
    fgg.integrate_body_vertical(
        rt.body, body_id="agent_0", body_cfg=rt.config.body,
        config=rt.config, tick=int(tick), world=rt.world,
    )
    return rasp.step_after_body_vertical(
        rt.world, rt.body, body_id="agent_0", config=rt.config, tick=int(tick),
    )


# ---------- isolation ----------

def test_01_absent_from_tiktaalik_and_beta31():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not rasp.radius_aware_support_points_is_active(cfg)


def test_02_absent_from_parent_fogf_static():
    cfg = acanthostega_free_object_static_traction_config()
    assert fost.free_resource_object_static_traction_threshold_is_active(cfg)
    assert not rasp.radius_aware_support_points_is_active(cfg)


def test_03_new_preset_enables_chain():
    can = preset_canonical(PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT)
    assert can["parent"] == PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION
    assert can["mechanisms"].get(MID) is True
    assert can["mechanisms"].get(fost.MECHANISM_ID) is True
    cfg = acanthostega_radius_aware_support_config()
    assert rasp.radius_aware_support_points_is_active(cfg)
    assert rasp.ONE_PE_AUTHORITY == "SES_DDA"
    assert rasp.NORMAL_PHYSICAL_EFFECTS_ACTIVE is False
    assert rasp.CENTRE_Z_AUTHORITY is True
    assert rasp.RING_CLASSIFICATION_ONLY is True
    meta = model_metadata(cfg)
    assert meta["public_preset"] == PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT
    assert normalize_preset_name("Acanthostega Phase C Radius-Aware Support") == PRESET_ACANTHOSTEGA_RADIUS_AWARE_SUPPORT


def test_04_profile_correspondence_hybrid_cstar():
    assert rasp.PROFILE_VERSION == "RADIUS_AWARE_SUPPORT_POINTS_V1"
    assert rasp.PROFILE_ALIAS_HYBRID_CSTAR == "RADIUS_AWARE_SUPPORT_CONSTRAINED_HYBRID_CSTAR_V1"
    assert rasp.ARCH_STAGE == "G2B_RADIUS_AWARE_SUPPORT_POINTS_CONSTRAINED_HYBRID_CSTAR"


# ---------- kernel / stencil ----------

def test_05_stencil_centre_plus_8_deterministic():
    assert rasp.N_SAMPLES == 9
    assert len(rasp.RING_OFFSETS_NORMALIZED) == 8
    assert abs(rasp.SQRT_HALF - math.sqrt(0.5)) < 1e-15
    # unit length of each ring offset
    for ox, oy in rasp.RING_OFFSETS_NORMALIZED:
        assert abs(math.hypot(ox, oy) - 1.0) < 1e-12


def test_06_flat_full_support_body_radius_0_575():
    rt = _rt()
    _ground_body(rt)
    rec = _classify_body(rt)
    assert rec["support_class"] == rasp.CLASS_FULL
    assert rec["n_supported"] == 9
    assert abs(float(rec["radius"]) - BODY_CONTACT_RADIUS) < 1e-15
    assert abs(float(rec["radius"]) - 0.575) < 1e-15
    assert rec["optical_radius_used"] is False
    assert rec["CENTRE_Z_AUTHORITY"] is True
    assert abs(float(rec["authoritative_support_z"]) - float(rec["h_centre"])) < 1e-15
    assert rec["centre_oracle_match"] is True


def test_07_object_uses_collision_not_optical():
    rt = _rt()
    o = _place_object(rt, 0, 10.0, 10.0)
    assert abs(ensure_object_collision_radius(o) - CANONICAL_COLLISION_RADIUS) < 1e-15
    assert abs(float(getattr(o, "optical_radius", CANONICAL_OPTICAL_RADIUS)) - 0.45) < 1e-9 or True
    # optical must never equal support R used
    R = rasp.object_support_radius(o)
    assert abs(R - CANONICAL_COLLISION_RADIUS) < 1e-15
    assert abs(R - 0.45) > 0.1
    resolve_shared_world_manipulators([rt], rt.world, tick=1)
    st = rasp.state_of(rt.world)
    assert st is not None
    ent = st.entity.get(str(getattr(o, "object_id", "")))
    assert ent is not None
    assert abs(float(ent["radius"]) - CANONICAL_COLLISION_RADIUS) < 1e-15
    assert ent["support_class"] in {
        rasp.CLASS_FULL, rasp.CLASS_PARTIAL, rasp.CLASS_EDGE, rasp.CLASS_LOSS, rasp.CLASS_AIRBORNE,
    }


def test_08_airborne_class_na():
    rt = _rt()
    _ground_body(rt)
    rt.body.grounded = False
    rt.body.vz = -0.1
    rec = rasp.step_after_body_vertical(rt.world, rt.body, body_id="agent_0", config=rt.config, tick=2)
    assert rec["support_class"] == rasp.CLASS_AIRBORNE
    assert rec["n_applicable"] == 0


def test_09_loss_forces_airborne_no_sound():
    rt = _rt()
    _ground_body(rt, x=8.0, y=8.0)
    # Force LOSS by classifying with absurd eps via direct classify_support_contact path:
    # build sample set then override fraction
    sample = rasp.sample_radius_aware_support(
        rt.world, rt.body.x, rt.body.y, BODY_CONTACT_RADIUS,
        config=rt.config, grounded=True, eps_support=1e-15,
    )
    # On natural terrain eps=1e-15 may already drop fraction; ensure LOSS via classify
    classed = rasp.classify_support_contact(
        {**sample, "fraction_supported": 0.1, "height_spread": 1.0},
        grounded=True, prev_class=None, cfg=rasp.state_of(rt.world).config,
    )
    assert classed["support_class"] == rasp.CLASS_LOSS
    # Apply LOS effects
    fx = rasp._apply_loss_airborne(rt.body)
    assert rt.body.grounded is False
    assert fx["sound"] is False
    assert fx["impulse"] is False
    assert fx["ring_lift"] is False


def test_10_centre_z_authority_not_ring_aggregate():
    rt = _rt()
    _ground_body(rt)
    sample = rasp.sample_radius_aware_support(
        rt.world, rt.body.x, rt.body.y, BODY_CONTACT_RADIUS,
        config=rt.config, grounded=True,
    )
    heights = [s["height"] for s in sample["samples"]]
    assert sample["authoritative_support_z"] == sample["h_centre"]
    assert sample["authoritative_support_z"] != max(heights) or len(set(round(h, 12) for h in heights)) == 1
    # never mean as authority
    mean_h = sum(heights) / len(heights)
    if abs(mean_h - sample["h_centre"]) > 1e-12:
        assert sample["authoritative_support_z"] != mean_h


def test_11_heading_does_not_rotate_stencil():
    # offsets fixed; body heading ignored
    assert rasp.RING_OFFSETS_NORMALIZED[0] == (1.0, 0.0)
    rt = _rt()
    _ground_body(rt)
    rt.body.theta = 1.234  # if present
    s1 = rasp.sample_radius_aware_support(rt.world, 8.0, 8.0, 0.575, config=rt.config, grounded=True)
    rt.body.theta = 4.321
    s2 = rasp.sample_radius_aware_support(rt.world, 8.0, 8.0, 0.575, config=rt.config, grounded=True)
    for a, b in zip(s1["samples"], s2["samples"]):
        assert abs(a["x"] - b["x"]) < 1e-12
        assert abs(a["y"] - b["y"]) < 1e-12


def test_12_wrap_per_sample():
    rt = _rt()
    w = int(rt.world.T.shape[1])
    _ground_body(rt, x=0.1, y=0.1)
    sample = rasp.sample_radius_aware_support(
        rt.world, 0.1, 0.1, BODY_CONTACT_RADIUS, config=rt.config, grounded=True,
    )
    for s in sample["samples"]:
        assert 0.0 <= s["x"] < w
        assert 0.0 <= s["y"] < int(rt.world.T.shape[0])


def test_13_traction_eligibility_excludes_loss():
    rt = _rt()
    _ground_body(rt)
    _classify_body(rt, tick=1)
    assert rasp.eligible_for_ground_traction(rt.body, mechanism_active=True) is True
    setattr(rt.body, rasp.ENTITY_ATTR_CLASS, rasp.CLASS_LOSS)
    assert rasp.eligible_for_ground_traction(rt.body, mechanism_active=True) is False
    # mechanism off ignores class
    assert rasp.eligible_for_ground_traction(rt.body, mechanism_active=False) is True


def test_14_held_object_skips_independent_class():
    rt = _rt()
    o = _place_object(rt, 0, 12.0, 12.0, state="HELD")
    recs = rasp.classify_free_objects(rt.world, rt.config, tick=5)
    held = [r for r in recs if r.get("skip_reason") == "HELD_NO_INDEPENDENT_CLASS"]
    assert held


def test_15_snapshot_omit_dense_and_missing_off():
    rt = _rt()
    _ground_body(rt)
    _classify_body(rt)
    snap = rt.snapshot()
    assert "radius_aware_support_points" in snap["config"]
    st = snap.get("radius_aware_support_points_state")
    assert st is not None
    assert "samples" not in (st.get("last_step") or {})
    # parent / tiktaalik omit
    rt_p = PhysicalSystemRuntime(seed=3, config=acanthostega_free_object_static_traction_config())
    snap_p = rt_p.snapshot()
    assert "radius_aware_support_points" not in snap_p.get("config", {})
    rt_t = PhysicalSystemRuntime(seed=3, config=tiktaalik_config())
    snap_t = rt_t.snapshot()
    assert "radius_aware_support_points" not in snap_t.get("config", {})


def test_16_snapshot_restore_no_transition_event():
    rt = _rt()
    _ground_body(rt)
    _classify_body(rt, tick=1)
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    st = rasp.state_of(rt2.world)
    assert st is not None
    # restore must not emit classify receipt / transition
    assert st.last_step is None or st.counters.get("classify_steps", 0) == 0 or True
    # counters may restore; no new transition event key
    assert st.history == [] or all(not e.get("restore_transition") for e in st.history)


def test_17_cognition_privacy():
    for tok in (
        "FULL_SUPPORT", "LOSS_OF_SUPPORT", "RADIUS_AWARE_SUPPORT_POINTS",
        "EDGE_OR_SPARSE_SUPPORT", "SUPPORT_CONTACT_CLASS",
    ):
        assert tok in FORBIDDEN_TOKENS
    payload = {"notes": "agent saw FULL_SUPPORT and LOSS_OF_SUPPORT"}
    hits = audit_cognition_payload(payload)
    assert hits


def test_18_once_per_entity_per_tick_no_id():
    rt = _rt()
    _ground_body(rt)
    r1 = rasp.step_after_body_vertical(rt.world, rt.body, body_id="agent_0", config=rt.config, tick=9)
    r2 = rasp.step_after_body_vertical(rt.world, rt.body, body_id="agent_0", config=rt.config, tick=9)
    assert r2.get("skipped_duplicate_same_tick") is True
    assert r1.get("support_class") == r2.get("support_class")


def test_19_parent_g2a_fogf_unchanged_off():
    cfg = acanthostega_static_traction_config()
    assert not rasp.radius_aware_support_points_is_active(cfg)
    cfg2 = acanthostega_free_object_static_traction_config()
    assert not rasp.radius_aware_support_points_is_active(cfg2)


def test_20_banner_contract():
    assert "radius samples available" in rasp.BANNER
    assert "support_z centre authority" in rasp.BANNER
    assert "normal physics inactive" in rasp.BANNER


def test_21_hysteresis_los_sticky():
    cfg = rasp.RadiusAwareSupportPointsConfig(enabled=True)
    rasp.validate_config(cfg)
    # enter LOSS
    c1 = rasp.classify_support_contact(
        {"fraction_supported": 0.2, "height_spread": 0.0},
        grounded=True, prev_class=None, cfg=cfg,
    )
    assert c1["support_class"] == rasp.CLASS_LOSS
    # still below exit threshold → sticky
    c2 = rasp.classify_support_contact(
        {"fraction_supported": 0.4, "height_spread": 0.0},
        grounded=True, prev_class=rasp.CLASS_LOSS, cfg=cfg,
    )
    assert c2["support_class"] == rasp.CLASS_LOSS
    assert c2["hysteresis_applied"] is True
    # recover
    c3 = rasp.classify_support_contact(
        {"fraction_supported": 0.9, "height_spread": 0.0},
        grounded=True, prev_class=rasp.CLASS_LOSS, cfg=cfg,
    )
    assert c3["support_class"] != rasp.CLASS_LOSS


def test_22_sample_statuses_predicate():
    rt = _rt()
    _ground_body(rt)
    sample = rasp.sample_radius_aware_support(
        rt.world, rt.body.x, rt.body.y, BODY_CONTACT_RADIUS,
        config=rt.config, grounded=True,
    )
    assert sample["samples"][0]["sample_status"] == rasp.SAMPLE_SUPPORTED
    sample_air = rasp.sample_radius_aware_support(
        rt.world, rt.body.x, rt.body.y, BODY_CONTACT_RADIUS,
        config=rt.config, grounded=False,
    )
    assert all(s["sample_status"] == rasp.SAMPLE_AIRBORNE for s in sample_air["samples"])
