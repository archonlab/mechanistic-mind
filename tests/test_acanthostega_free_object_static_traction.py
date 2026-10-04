"""ACANTHOSTEGA_PHASE_C_FREE_OBJECT_STATIC_TRACTION — FOGF static traction twin V1.

Parent: ACANTHOSTEGA_PHASE_C_STATIC_TRACTION.
Arch: FOGF_STATIC_TRACTION_TWIN.
"""
from __future__ import annotations

import math

from mechanistic_mind.model.acanthostega import (
    acanthostega_free_object_static_traction_config,
    acanthostega_static_traction_config,
    model_metadata,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import body_static_traction_threshold as bst
from mechanistic_mind.physical_system import free_resource_object_ground_friction as fogf
from mechanistic_mind.physical_system import free_resource_object_kinematics as fok
from mechanistic_mind.physical_system import free_resource_object_static_traction_threshold as fost
from mechanistic_mind.physical_system import flat_ground_gravity as fgg
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION,
    PRESET_ACANTHOSTEGA_STATIC_TRACTION,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.physical_manipulator import resolve_shared_world_manipulators
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

MID = fost.MECHANISM_ID


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_free_object_static_traction_config())


def _place_object(rt, idx, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0, mass=None, z=0.0, vz=0.0):
    objs = list(getattr(rt.world, "resource_objects", None) or [])
    assert len(objs) > idx
    o = objs[idx]
    o.x, o.y = float(x), float(y)
    o.vx, o.vy = float(vx), float(vy)
    o.physical_state = state
    o.holder_body_id = None
    o.manipulator_id = None
    if mass is not None:
        o.mass = float(mass)
    fgg.ensure_object_vertical(o, rt.config)
    o.z = float(z)
    o.vz = float(vz)
    o.grounded = bool(abs(o.z) <= 1e-12 and abs(o.vz) <= 1e-12)
    return o


def _step_world(rt, tick):
    resolve_shared_world_manipulators([rt], rt.world, tick=int(tick))


def _integrate_once(rt):
    tick = int(getattr(rt, "tick", 0) or 0) + 1
    rt.tick = tick
    _step_world(rt, tick)
    return tick


# ---------- isolation ----------


def test_01_absent_from_tiktaalik_and_beta31():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not fost.free_resource_object_static_traction_threshold_is_active(cfg)


def test_02_absent_from_parent_static_traction():
    cfg = acanthostega_static_traction_config()
    assert bst.body_static_traction_threshold_is_active(cfg)
    assert not fost.free_resource_object_static_traction_threshold_is_active(cfg)


def test_03_new_preset_enables_chain():
    can = preset_canonical(PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION)
    assert can["parent"] == PRESET_ACANTHOSTEGA_STATIC_TRACTION
    assert can["mechanisms"].get(bst.MECHANISM_ID) is True
    assert can["mechanisms"].get(MID) is True
    cfg = acanthostega_free_object_static_traction_config()
    assert fost.free_resource_object_static_traction_threshold_is_active(cfg)
    assert bst.body_static_traction_threshold_is_active(cfg)
    assert fogf.free_resource_object_ground_friction_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION)
    assert fost.free_resource_object_static_traction_threshold_is_active(cfg)
    meta = model_metadata(cfg)
    assert "FREE_OBJECT_STATIC_TRACTION" in str(meta.get("classification") or "")


def test_04_normalize_aliases():
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_FREE_OBJECT_STATIC_TRACTION") == PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION
    assert normalize_preset_name("FOGF_STATIC_TRACTION_TWIN") == PRESET_ACANTHOSTEGA_FREE_OBJECT_STATIC_TRACTION
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_STATIC_TRACTION") == PRESET_ACANTHOSTEGA_STATIC_TRACTION


def test_05_forbidden_tokens():
    for tok in (
        "free_resource_object_static_traction_threshold",
        "FREE_RESOURCE_OBJECT_STATIC_TRACTION",
        "FOGF_STATIC_TRACTION_TWIN",
        "RELEASE_TRANSITION_NOT_ELIGIBLE",
        "STATIC_HOLD",
        "mu_static",
    ):
        assert tok in FORBIDDEN_TOKENS
    hits = audit_cognition_payload({"note": "free_resource_object_static_traction_threshold STATIC_HOLD"})
    assert hits


def test_06_hard_bounds_flags():
    cfg = acanthostega_free_object_static_traction_config().free_resource_object_static_traction_threshold
    d = cfg.to_dict()
    assert d["NORMAL_PHYSICAL_EFFECTS_ACTIVE"] is False
    assert d["N_LAW"] == "N_EQUALS_OBJECT_MASS_G_NO_NZ"
    assert d["ONE_PE_AUTHORITY"] == "SES_DDA"
    assert d["TANGENT_GRAVITY"] == "NO"
    assert d["G2A_BODY_STATIC_TRACTION_CHANGED"] == "NO"
    assert d["legacy_object_damping_bypassed"] is True
    assert d["double_ground_friction"] is False


def test_07_shared_mu_s_helper_no_diverge():
    for a in (0.0, 0.25, 0.5, 0.75, 1.0):
        body_pair = bst.mu_static_from_surface_affinity(a)
        # FOST reuses same helper
        assert body_pair["mu_static"] >= body_pair["mu_k"] - 1e-15
        assert abs(body_pair["mu_static"] - 1.25 * body_pair["mu_k"]) < 1e-12


def test_08_g2a_body_unchanged_on_parent():
    """G2A_BODY_STATIC_TRACTION_CHANGED=NO — parent preset has no FOST."""
    cfg = acanthostega_static_traction_config()
    assert bst.body_static_traction_threshold_is_active(cfg)
    assert not fost.free_resource_object_static_traction_threshold_is_active(cfg)
    d = cfg.body_static_traction_threshold.to_dict()
    assert d.get("FOGF_STATIC_TWIN") == "DEFERRED"


def test_10_legacy_damp_bypassed_double_friction_false():
    rt = _rt()
    o = _place_object(rt, 0, 8.5, 8.5, state="FREE_MOVING", vx=0.05, vy=0.0, mass=1.0)
    _integrate_once(rt)
    st = fost.state_of(rt.world)
    assert st is not None
    assert int(st.counters.get("legacy_object_damping_bypassed", 0)) >= 1
    rec = st.last_step or {}
    assert rec.get("legacy_object_damping_bypassed") is True
    assert rec.get("double_ground_friction") is False


def test_20_static_hold_small_residual():
    rt = _rt()
    # Tiny residual: |m v| << μ_s N dt
    o = _place_object(rt, 0, 8.5, 8.5, state="FREE_MOVING", vx=0.002, vy=0.0, mass=1.0)
    x0, y0 = o.x, o.y
    _integrate_once(rt)
    assert str(o.physical_state) == "FREE_STATIC"
    assert abs(o.vx) < 1e-12 and abs(o.vy) < 1e-12
    assert abs(o.x - x0) < 1e-12 and abs(o.y - y0) < 1e-12
    rec = fost.state_of(rt.world).last_step
    assert rec["state_class"] == fost.STATE_STATIC_HOLD
    assert float(rec.get("work") or 0.0) == 0.0
    assert float(rec.get("static_work") or 0.0) == 0.0
    assert rec.get("ses_debit_from_twin") is False


def test_21_static_breakaway_then_kinetic_once():
    rt = _rt()
    # Large speed so |m v| > J_static_max
    o = _place_object(rt, 0, 8.5, 8.5, state="FREE_MOVING", vx=0.8, vy=0.0, mass=1.0)
    speed0 = abs(o.vx)
    _integrate_once(rt)
    rec = fost.state_of(rt.world).last_step
    assert rec["state_class"] == fost.STATE_STATIC_BREAKAWAY
    assert rec.get("kinetic_applied") is True
    assert math.hypot(o.vx, o.vy) < speed0  # kinetic dissipates


def test_22_airborne_no_support():
    rt = _rt()
    o = _place_object(rt, 0, 8.5, 8.5, state="FREE_MOVING", vx=0.05, vy=0.0, mass=1.0, z=0.5, vz=0.0)
    o.grounded = False
    _integrate_once(rt)
    rec = fost.state_of(rt.world).last_step
    assert rec["state_class"] == fost.STATE_NO_SUPPORT
    # airborne conserves horizontal under FOGF/FOST path
    assert abs(o.vx - 0.05) < 1e-9


def test_23_n_equals_m_g_no_nz():
    rt = _rt()
    o = _place_object(rt, 0, 8.5, 8.5, state="FREE_MOVING", vx=0.002, vy=0.0, mass=2.5)
    _integrate_once(rt)
    rec = fost.state_of(rt.world).last_step
    g = float(rec["g"])
    assert abs(float(rec["normal_load_N"]) - 2.5 * g) < 1e-12


def test_24_snapshot_omit_inactive_and_restore():
    # Parent/Tiktaalik snapshots omit FOST keys
    rt_tik = PhysicalSystemRuntime(seed=3, config=tiktaalik_config())
    snap = rt_tik.snapshot()
    assert "free_resource_object_static_traction_threshold" not in (snap.get("config") or {})
    assert "free_resource_object_static_traction_threshold_state" not in snap
    # FOST ON: snapshot has keys; restore continues
    rt = _rt()
    for _ in range(2):
        rt.step_forced_action("WAIT")
    o = _place_object(rt, 0, 8.5, 8.5, state="FREE_MOVING", vx=0.3, vy=0.0)
    rt.step_forced_action("WAIT")
    snap2 = rt.snapshot()
    assert "free_resource_object_static_traction_threshold" in snap2["config"]
    assert snap2.get("free_resource_object_static_traction_threshold_state") is not None
    rt2 = PhysicalSystemRuntime.restore(snap2)
    assert fost.free_resource_object_static_traction_threshold_is_active(rt2.config)
    assert fost.state_of(rt2.world) is not None
    rt2.step_forced_action("WAIT")


def test_25_tiktaalik_and_parent_omit_fost_keys():
    for cfg_fn in (tiktaalik_config, acanthostega_static_traction_config):
        rt = PhysicalSystemRuntime(seed=5, config=cfg_fn())
        snap = rt.snapshot()
        assert "free_resource_object_static_traction_threshold" not in (snap.get("config") or {})
        assert "free_resource_object_static_traction_threshold_state" not in snap


def test_26_release_transition_not_eligible():
    rt = _rt()
    o = _place_object(rt, 0, 8.5, 8.5, state="FREE_MOVING", vx=0.002, vy=0.0)
    # Simulate release episode: first integrate at release_tick+1
    st_fok = fok.state_of(rt.world)
    assert st_fok is not None
    tick = int(getattr(rt, "tick", 0) or 0)
    release_tick = tick
    st_fok.episodes[str(o.object_id)] = {
        "release_receipt_id": "test-rel",
        "release_tick": release_tick,
        "path_length": 0.0,
        "moving_ticks": 0,
        "wrap_count": 0,
        "speed_clamped": False,
        "invariant_fingerprint": fok.invariant_fingerprint(o),
        "initial_speed": 0.002,
    }
    rt.tick = release_tick
    # Force last_integrated so next call runs
    st_fok.last_integrated_tick = release_tick - 1
    _step_world(rt, release_tick + 1)
    rec = fost.state_of(rt.world).last_step
    assert rec["state_class"] == fost.STATE_RELEASE_TRANSITION_NOT_ELIGIBLE
    # inherited velocity not statically erased to hold when residual was small —
    # kinetic may rest, but class must be RELEASE_TRANSITION
    assert rec["eligibility_reason"] == "RELEASE_TRANSITION_NOT_ELIGIBLE"


def test_27_collision_grace_not_eligible():
    rt = _rt()
    o = _place_object(rt, 0, 8.5, 8.5, state="FREE_MOVING", vx=0.002, vy=0.0)
    fost.set_object_impulse_grace(o, 1)
    _integrate_once(rt)
    rec = fost.state_of(rt.world).last_step
    assert rec["state_class"] == fost.STATE_NOT_ELIGIBLE


def test_28_one_application_per_object_id_not_python_id():
    rt = _rt()
    o = _place_object(rt, 0, 8.5, 8.5, state="FREE_MOVING", vx=0.05, vy=0.0)
    oid = str(o.object_id)
    tick = _integrate_once(rt)
    st = fost.state_of(rt.world)
    assert st.applied_this_tick.get(oid) == tick
    # second plan same tick skipped
    plan = fost.plan_free_object_static_traction_step(
        rt.world, o, 0.05, 0.0, fok.state_of(rt.world).config, tick=tick, episode=None,
    )
    assert plan.get("skipped_duplicate_same_tick") is True


def test_29_arch_stage_documented():
    assert fost.ARCH_STAGE == "FOGF_STATIC_TRACTION_TWIN"
    assert fost.PROFILE_VERSION == "FREE_RESOURCE_OBJECT_STATIC_TRACTION_THRESHOLD_V1"
    assert fost.RECEIPT_KIND == "FREE_RESOURCE_OBJECT_STATIC_TRACTION"
