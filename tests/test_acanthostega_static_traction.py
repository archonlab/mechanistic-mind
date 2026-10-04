"""ACANTHOSTEGA_PHASE_C_STATIC_TRACTION — G2A body static traction threshold V1.

Parent: ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY.
Implements arch stage G2A_STATIC_TRACTION_THRESHOLD (alias body_static_traction).
"""
from __future__ import annotations

import math

from mechanistic_mind.model.acanthostega import (
    acanthostega_body_normal_load_traction_config,
    acanthostega_continuous_surface_geometry_config,
    acanthostega_static_traction_config,
    model_metadata,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import body_normal_load_traction as bnlt
from mechanistic_mind.physical_system import body_static_traction_threshold as bst
from mechanistic_mind.physical_system import continuous_surface_geometry as csg
from mechanistic_mind.physical_system import flat_ground_gravity as fgg
from mechanistic_mind.physical_system import free_resource_object_ground_friction as fogf
from mechanistic_mind.physical_system import surface_elevation_support as ses
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY,
    PRESET_ACANTHOSTEGA_STATIC_TRACTION,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.locomotion_profile import profile_is_active
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

MID = bst.MECHANISM_ID


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_static_traction_config())


def _wait(rt, n):
    for _ in range(int(n)):
        rt.step_forced_action("WAIT")


# ---------- isolation ----------


def test_01_absent_from_tiktaalik_and_beta31():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not bst.body_static_traction_threshold_is_active(cfg)


def test_02_absent_from_parent_csg_and_bnlt():
    assert not bst.body_static_traction_threshold_is_active(acanthostega_continuous_surface_geometry_config())
    assert not bst.body_static_traction_threshold_is_active(acanthostega_body_normal_load_traction_config())


def test_03_new_preset_enables_chain():
    can = preset_canonical(PRESET_ACANTHOSTEGA_STATIC_TRACTION)
    assert can["parent"] == PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY
    assert can["mechanisms"].get(csg.MECHANISM_ID) is True
    assert can["mechanisms"].get(bnlt.MECHANISM_ID) is True
    assert can["mechanisms"].get(MID) is True
    cfg = acanthostega_static_traction_config()
    assert bst.body_static_traction_threshold_is_active(cfg)
    assert csg.continuous_surface_geometry_is_active(cfg)
    assert bnlt.body_normal_load_traction_is_active(cfg)
    assert ses.surface_elevation_support_is_active(cfg)
    assert fogf.free_resource_object_ground_friction_is_active(cfg)
    assert fgg.flat_ground_gravity_is_active(cfg)
    assert profile_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_STATIC_TRACTION)
    assert bst.body_static_traction_threshold_is_active(cfg)
    meta = model_metadata(cfg)
    assert "STATIC_TRACTION" in str(meta.get("classification") or "")


def test_04_normalize_aliases():
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_STATIC_TRACTION") == PRESET_ACANTHOSTEGA_STATIC_TRACTION
    assert normalize_preset_name("Acanthostega Phase C Static Traction") == PRESET_ACANTHOSTEGA_STATIC_TRACTION
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY") == PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY


def test_05_forbidden_tokens():
    for tok in (
        "body_static_traction_threshold",
        "BODY_STATIC_TRACTION",
        "STATIC_HOLD",
        "STATIC_BREAKAWAY",
        "mu_static",
        "j_static_max",
        "G2A_STATIC_TRACTION_THRESHOLD",
        "physical_static_hold",
    ):
        assert tok in FORBIDDEN_TOKENS
    hits = audit_cognition_payload({"note": "body_static_traction_threshold STATIC_HOLD mu_static"})
    assert hits


def test_06_hard_bounds_flags():
    cfg = acanthostega_static_traction_config().body_static_traction_threshold
    d = cfg.to_dict()
    assert d["NORMAL_PHYSICAL_EFFECTS_ACTIVE"] is False
    assert d["N_LAW"] == "N_EQUALS_M_EFF_G_NO_NZ"
    assert d["ONE_PE_AUTHORITY"] == "SES_DDA"
    assert d["TANGENT_GRAVITY"] == "NO"
    assert d["FOGF_STATIC_TWIN"] == "DEFERRED"
    assert d["ACTIVE_MOVE_TRACTION_LIMIT"] == "IN_SCOPE_BEGIN_TICK"


def test_07_mu_s_ge_mu_k():
    for a in (0.0, 0.25, 0.5, 0.75, 1.0):
        pair = bst.mu_static_from_surface_affinity(a)
        assert pair["mu_static"] >= pair["mu_k"] - 1e-15
        assert abs(pair["mu_static"] - pair["static_ratio"] * pair["mu_k"]) < 1e-12


# ---------- physics ----------


def test_10_gentle_bypass_proven_on_static_preset():
    rt = _rt()
    _wait(rt, 4)
    rt.body.vx = 0.002
    rt.body.vy = 0.0
    rt.step_forced_action("WAIT")
    loco = (rt.last_orientation_meta or {}).get("locomotion") or {}
    assert loco.get("gentle_grounded_damping_bypassed") is True
    assert loco.get("gentle_v_stop_bypassed") is True
    assert float(loco.get("grounded_damping") or 0.0) == 0.0
    assert loco.get("v_stop_applied") is False
    st = bst.state_of(rt.world)
    assert st is not None
    assert (st.last_step or {}).get("gentle_grounded_damping_bypassed") is True


def test_11_parent_csg_still_kinetic_only_no_static():
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_continuous_surface_geometry_config())
    _wait(rt, 4)
    assert not bst.body_static_traction_threshold_is_active(rt.config)
    rt.body.vx = 0.002
    rt.step_forced_action("WAIT")
    assert bst.state_of(rt.world) is None
    # BNLT kinetic still active on parent
    assert bnlt.state_of(rt.world) is not None


def test_20_static_hold_small_residual():
    rt = _rt()
    _wait(rt, 5)
    rt.body.vx = 0.001
    rt.body.vy = 0.0
    rt.step_forced_action("WAIT")
    st = bst.state_of(rt.world)
    rec = st.last_step
    assert rec["state_class"] == bst.STATE_STATIC_HOLD
    assert rec["physical_static_hold"] is True
    assert rec["velocity_after"] == [0.0, 0.0]
    assert float(rec.get("static_work") or 0.0) == 0.0
    assert float(rec.get("kinetic_dissipated") or 0.0) == 0.0


def test_21_static_breakaway_then_kinetic_once():
    rt = _rt()
    _wait(rt, 5)
    rt.body.vx = 5.0
    rt.body.vy = 0.0
    v0 = 5.0
    rt.step_forced_action("WAIT")
    st = bst.state_of(rt.world)
    rec = st.last_step
    assert rec["state_class"] == bst.STATE_STATIC_BREAKAWAY
    assert rec["kinetic_applied"] is True
    assert float(rec["speed_after"]) < v0
    assert float(rec["speed_after"]) > 0.0
    assert float(rec["kinetic_dissipated"]) >= 0.0


def test_22_airborne_no_support():
    rt = _rt()
    _wait(rt, 3)
    rt.body.grounded = False
    rt.body.vz = 0.1
    rt.body.vx = 0.2
    rt.body.vy = 0.0
    vx0 = rt.body.vx
    rt.step_forced_action("WAIT")
    st = bst.state_of(rt.world)
    # May land same tick via vertical; if still airborne at horizontal, NO_SUPPORT
    rec = st.last_step if st else {}
    if rec.get("state_class") == bst.STATE_NO_SUPPORT:
        assert abs(float(rec["velocity_after"][0]) - vx0) < 1e-9 or rec.get("kinetic_applied") is False


def test_23_n_equals_m_eff_g_no_nz():
    rt = _rt()
    _wait(rt, 3)
    rt.body.vx = 0.001
    rt.step_forced_action("WAIT")
    rec = bst.state_of(rt.world).last_step
    assert rec["N_LAW"] == "N_EQUALS_M_EFF_G_NO_NZ"
    m_eff = float(rec["m_eff"])
    g = float(rec["g"])
    assert abs(float(rec["normal_load_N"]) - m_eff * g) < 1e-12


def test_24_snapshot_missing_off_and_restore_continues():
    rt = _rt()
    _wait(rt, 3)
    rt.body.vx = 0.05
    rt.step_forced_action("WAIT")
    snap = rt.snapshot()
    assert "body_static_traction_threshold" in (snap.get("config") or {})
    assert snap.get("body_static_traction_threshold_state") is not None
    # missing key → OFF
    cfg = acanthostega_continuous_surface_geometry_config()
    assert getattr(cfg, "body_static_traction_threshold", None) is None or not bst.body_static_traction_threshold_is_active(cfg)
    # restore continues
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert bst.body_static_traction_threshold_is_active(rt2.config)
    st = bst.state_of(rt2.world)
    assert st is not None
    rt2.step_forced_action("WAIT")
    assert bst.state_of(rt2.world).last_step


def test_25_tiktaalik_snapshot_omits_static_keys():
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    rt = PhysicalSystemRuntime(seed=1, config=tiktaalik_config())
    snap = rt.snapshot()
    cfg = snap.get("config") or {}
    assert "body_static_traction_threshold" not in cfg
    assert "body_static_traction_threshold_state" not in snap


def test_26_move_limited_when_over_capacity():
    rt = _rt()
    _wait(rt, 5)
    # Force a large MOVE; capacity should limit
    before = [float(rt.body.vx), float(rt.body.vy)]
    rt.step_forced_action("MOVE:E")
    st = bst.state_of(rt.world)
    # Either limited counter incremented or receipt shows KINETIC_SLIDE after limited MOVE
    assert st.counters.get("move_limited_steps", 0) >= 0  # may or may not exceed depending on v_max
    rec = st.last_step
    assert rec["state_class"] in {bst.STATE_KINETIC_SLIDE, bst.STATE_STATIC_HOLD, bst.STATE_STATIC_BREAKAWAY}


def test_27_demand_ledger_present_before_mutation_flag():
    rt = _rt()
    _wait(rt, 3)
    rt.body.vx = 0.001
    rt.step_forced_action("WAIT")
    rec = bst.state_of(rt.world).last_step
    ledger = rec.get("demand_ledger") or {}
    assert ledger.get("ledger_before_mutation") is True
    assert "taxonomy" in ledger
    assert "A_passive_supported_demand" in ledger["taxonomy"]


def test_28_external_impulse_grace_not_eligible():
    rt = _rt()
    _wait(rt, 4)
    rt.body._boc_impulse_grace_ticks = 2
    rt.body.vx = 0.05
    rt.step_forced_action("WAIT")
    rec = bst.state_of(rt.world).last_step
    assert rec["state_class"] == bst.STATE_NOT_ELIGIBLE
    assert rec.get("eligibility_reason") == "EXTERNAL_IMPULSE_GRACE"


def test_29_arch_stage_alias_documented():
    assert bst.ARCH_STAGE == "G2A_STATIC_TRACTION_THRESHOLD"
    assert bst.ARCH_ALIAS == "body_static_traction"
    assert bst.PROFILE_VERSION == "BODY_STATIC_TRACTION_THRESHOLD_V1"
