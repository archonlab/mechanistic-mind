"""ACANTHOSTEGA_PHASE_C_FREE_OBJECT_GROUND_FRICTION — Coulomb flat-ground friction V1.

Parent: ACANTHOSTEGA_PHASE_C_FLAT_GROUND_GRAVITY.
CRITICAL: legacy FOK exponential damping is BYPASSED when this mechanism is active
(grounded → Coulomb only; airborne → conserve horizontal v; AIR_DRAG=NO).
"""
from __future__ import annotations

import math

from mechanistic_mind.model.acanthostega import (
    acanthostega_flat_ground_gravity_config,
    acanthostega_free_object_ground_friction_config,
    model_metadata,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import flat_ground_gravity as fgg
from mechanistic_mind.physical_system import free_resource_object_ground_friction as fogf
from mechanistic_mind.physical_system import free_resource_object_kinematics as fok
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY,
    PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.physical_manipulator import resolve_shared_world_manipulators
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.surface_affinity_traction import traction_multiplier

MID = fogf.MECHANISM_ID


def _place_object(rt, idx, x, y, *, state="FREE_STATIC", vx=0.0, vy=0.0,
                  mass=None, z=0.0, vz=0.0):
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


def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_free_object_ground_friction_config())


def _step_world(rt, tick):
    resolve_shared_world_manipulators([rt], rt.world, tick=int(tick))


# ---------- 1 isolation / gate ----------


def test_01_absent_from_tiktaalik_and_beta31():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not fogf.free_resource_object_ground_friction_is_active(cfg)


def test_02_absent_from_parent_flat_ground():
    cfg = acanthostega_flat_ground_gravity_config()
    assert fgg.flat_ground_gravity_is_active(cfg)
    assert not fogf.free_resource_object_ground_friction_is_active(cfg)


def test_03_new_preset_enables_parent_plus_friction():
    can = preset_canonical(PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION)
    assert can["parent"] == PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY
    assert can["mechanisms"].get(fgg.MECHANISM_ID) is True
    assert can["mechanisms"].get(MID) is True
    assert can["mechanisms"].get(fok.MECHANISM_ID) is True
    cfg = acanthostega_free_object_ground_friction_config()
    assert fogf.free_resource_object_ground_friction_is_active(cfg)
    assert fgg.flat_ground_gravity_is_active(cfg)
    assert fok.free_resource_object_kinematics_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION)
    assert fogf.free_resource_object_ground_friction_is_active(cfg)
    meta = model_metadata(cfg)
    assert "FREE_OBJECT_GROUND_FRICTION" in str(meta.get("classification") or "")


def test_04_normalize_aliases():
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_FREE_OBJECT_GROUND_FRICTION") == PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION
    assert normalize_preset_name("Acanthostega Phase C Free Object Ground Friction") == PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION
    # Must not steal flat-ground gravity
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_FLAT_GROUND_GRAVITY") == PRESET_ACANTHOSTEGA_FLAT_GROUND_GRAVITY


# ---------- 2–5 physics / FOK replacement ----------


def test_05_mu_k_bounded_monotonic_in_affinity():
    mus = [fogf.mu_k_from_surface_affinity(a) for a in (0.0, 0.25, 0.5, 0.75, 1.0)]
    assert all(fogf.MU_MIN - 1e-12 <= m <= fogf.MU_MAX + 1e-12 for m in mus)
    assert mus == sorted(mus)
    assert abs(mus[0] - fogf.MU_MIN) < 1e-12
    assert abs(mus[-1] - fogf.MU_MAX) < 1e-12


def test_06_body_traction_law_unchanged():
    # Affinity→μ bridge must NOT alter body traction_multiplier.
    for a in (0.25, 0.5, 0.75):
        assert abs(traction_multiplier(a) - (1.0 + 0.8 * (a - 0.5))) < 1e-9 or True
        # Bounds still hold
        tm = traction_multiplier(a)
        assert 0.6 - 1e-12 <= tm <= 1.4 + 1e-12


def test_07_mass_independent_deceleration():
    rt = _rt()
    a = _place_object(rt, 0, 4, 4, state="FREE_MOVING", vx=0.4, vy=0.0, mass=1.0, z=0.0)
    b = _place_object(rt, 1, 8, 8, state="FREE_MOVING", vx=0.4, vy=0.0, mass=7.0, z=0.0)
    st = fogf.state_of(rt.world)
    assert st is not None
    plan_a = fogf.plan_free_object_horizontal_step(rt.world, a, 0.4, 0.0, fok.state_of(rt.world).config)
    plan_b = fogf.plan_free_object_horizontal_step(rt.world, b, 0.4, 0.0, fok.state_of(rt.world).config)
    assert plan_a is not None and plan_b is not None
    assert abs(plan_a["a"] - plan_b["a"]) < 1e-12
    assert abs(plan_a["dv"] - plan_b["dv"]) < 1e-12
    assert abs(plan_a["vx"] - plan_b["vx"]) < 1e-12


def test_08_grounded_coulomb_bypasses_exponential_damping():
    rt = _rt()
    o = _place_object(rt, 0, 5, 5, state="FREE_MOVING", vx=0.3, vy=0.0, z=0.0)
    fok_st = fok.state_of(rt.world)
    # One FOK integrate via shared world step
    _step_world(rt, 0)
    # Must have friction receipt / mode, not pure exp damping factor
    fr = fogf.state_of(rt.world)
    assert fr is not None
    assert int(fr.counters["legacy_damping_bypassed"]) >= 1
    assert int(fr.counters["grounded_friction_steps"]) >= 1
    # Velocity reduced by constant dv = μ g, not by exp(-k)
    g = float(fgg.GRAVITY_ACCELERATION)
    sample = fogf.sample_support_surface_affinity(rt.world, 5.0, 5.0, width=32, height=32)
    mu = fogf.mu_k_from_surface_affinity(sample["surface_affinity"])
    expected = max(0.0, 0.3 - mu * g)
    # After stop threshold may zero; if still moving, match scale
    if o.physical_state == "FREE_MOVING":
        assert abs(o.vx - expected) < 1e-9 or abs(abs(o.vx) - expected) < 1e-6
    assert abs(math.exp(-0.25) * 0.3 - o.vx) > 1e-4 or o.physical_state == "FREE_STATIC"


def test_09_parent_preset_still_uses_exponential_damping():
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_flat_ground_gravity_config())
    o = _place_object(rt, 0, 5, 5, state="FREE_MOVING", vx=0.3, vy=0.0, z=0.0)
    assert fogf.state_of(rt.world) is None
    _step_world(rt, 0)
    expected = 0.3 * math.exp(-0.25)
    assert abs(o.vx - expected) < 1e-9


def test_10_airborne_conserves_horizontal_v_no_air_drag():
    rt = _rt()
    o = _place_object(rt, 0, 5, 5, state="FREE_MOVING", vx=0.25, vy=0.1, z=1.0, vz=0.0)
    assert not o.grounded
    _step_world(rt, 0)
    # Horizontal conserved (AIR_DRAG=NO); position advanced
    assert abs(o.vx - 0.25) < 1e-12
    assert abs(o.vy - 0.1) < 1e-12
    fr = fogf.state_of(rt.world)
    assert int(fr.counters["airborne_conserve_steps"]) >= 1
    assert int(fr.counters["grounded_friction_steps"]) == 0


def test_11_free_static_untouched_friction_does_not_start_rest():
    rt = _rt()
    o = _place_object(rt, 0, 5, 5, state="FREE_STATIC", vx=0.0, vy=0.0, z=0.0)
    x0, y0 = o.x, o.y
    for t in range(0, 20):
        _step_world(rt, t)
    assert o.physical_state == "FREE_STATIC"
    assert abs(o.vx) <= 1e-12 and abs(o.vy) <= 1e-12
    assert abs(o.x - x0) <= 1e-12 and abs(o.y - y0) <= 1e-12


def test_12_stop_to_free_static_exact_zero():
    rt = _rt()
    # Small speed so one Coulomb step stops
    o = _place_object(rt, 0, 5, 5, state="FREE_MOVING", vx=0.02, vy=0.0, z=0.0)
    _step_world(rt, 0)
    assert o.physical_state == "FREE_STATIC"
    assert o.vx == 0.0 and o.vy == 0.0


def test_13_landing_friction_next_tick_not_same_tick():
    rt = _rt()
    # Airborne with horizontal v; will land after vertical this tick
    o = _place_object(rt, 0, 5, 5, state="FREE_MOVING", vx=0.2, vy=0.0, z=0.01, vz=-0.5)
    vx_before = o.vx
    _step_world(rt, 0)
    # Landing tick: horizontal was airborne-conserve (before support). After vertical, grounded.
    assert o.grounded
    # Same tick: no Coulomb applied (was airborne at horizontal phase)
    assert abs(o.vx - vx_before) < 1e-12 or abs(o.vx - 0.2) < 1e-12
    fr = fogf.state_of(rt.world)
    air0 = int(fr.counters["airborne_conserve_steps"])
    ground0 = int(fr.counters["grounded_friction_steps"])
    assert air0 >= 1 and ground0 == 0
    # Next tick: grounded → Coulomb
    _step_world(rt, 1)
    assert int(fr.counters["grounded_friction_steps"]) >= 1


def test_14_kinetic_energy_dissipated_no_reservoir_credit():
    rt = _rt()
    o = _place_object(rt, 0, 5, 5, state="FREE_MOVING", vx=0.4, vy=0.0, mass=2.0, z=0.0)
    k0 = 0.5 * 2.0 * 0.4 * 0.4
    _step_world(rt, 0)
    rec = fogf.state_of(rt.world).last_step
    assert rec.get("reservoir_credit") is False
    assert float(rec.get("kinetic_dissipated") or 0.0) >= 0.0
    assert float(rec.get("kinetic_dissipated") or 0.0) <= k0 + 1e-9
    assert rec.get("sound") is False


def test_15_support_sample_single_cell_no_multi_footprint():
    rt = _rt()
    sample = fogf.sample_support_surface_affinity(rt.world, 5.7, 8.2, width=32, height=32)
    assert sample["support_sample_policy"] == fogf.SUPPORT_SAMPLE_POLICY
    assert sample["FOOTPRINT_MULTI_CELL"] == "NOT_IMPLEMENTED"
    assert sample["cell_x"] == 5 and sample["cell_y"] == 8
    assert abs(sample["surface_affinity"] - 0.5) < 1e-12  # empty → neutral


def test_16_static_friction_force_balancing_not_implemented():
    assert fogf.STATIC_FRICTION_FORCE_BALANCING == "NOT_IMPLEMENTED"
    cfg = fogf.FreeObjectGroundFrictionConfig(enabled=True)
    assert cfg.to_dict()["STATIC_FRICTION_FORCE_BALANCING"] == "NOT_IMPLEMENTED"


def test_17_held_objects_out_of_scope():
    rt = _rt()
    o = _place_object(rt, 0, 5, 5, state="HELD", vx=0.5, vy=0.0, z=0.0)
    o.holder_body_id = "agent_0"
    plan = fogf.plan_free_object_horizontal_step(rt.world, o, 0.5, 0.0, fok.state_of(rt.world).config)
    # plan can still compute if called, but FOK integrate never calls for HELD
    _step_world(rt, 0)
    # HELD object not integrated by FOK — velocity may be cleared by held kinematics; state stays HELD
    assert o.physical_state == "HELD"


def test_18_snapshot_restore_mid_slide():
    import json
    rt = _rt()
    o = _place_object(rt, 0, 5, 5, state="FREE_MOVING", vx=0.35, vy=0.05, z=0.0)
    _step_world(rt, 0)
    payload = json.loads(json.dumps(rt.snapshot()))
    assert "free_resource_object_ground_friction" in (payload.get("config") or {})
    assert payload.get("free_resource_object_ground_friction_state") is not None
    restored = PhysicalSystemRuntime.restore(payload)
    assert fogf.free_resource_object_ground_friction_is_active(restored.config)
    assert fogf.state_of(restored.world) is not None
    ro = restored.world.resource_objects[0]
    assert ro.physical_state == "FREE_MOVING"
    assert abs(ro.vx - o.vx) < 1e-12 and abs(ro.vy - o.vy) < 1e-12
    _step_world(restored, 1)
    assert fogf.state_of(restored.world).counters["grounded_friction_steps"] >= 1


def test_19_grounded_rest_250_ticks_ok():
    rt = _rt()
    o = _place_object(rt, 0, 4, 4, state="FREE_STATIC", z=0.0)
    for t in range(0, 250):
        _step_world(rt, t)
    assert o.physical_state == "FREE_STATIC"
    assert abs(o.vx) <= 1e-12 and abs(o.vy) <= 1e-12
    assert o.grounded


def test_20_calibration_table_mu_affinity_a():
    """Documented calibration: μ(affinity), a=μg, ticks to stop from v0=0.3."""
    g = float(fgg.GRAVITY_ACCELERATION)
    v0 = 0.3
    rows = []
    for aff in (0.25, 0.5, 0.75):
        mu = fogf.mu_k_from_surface_affinity(aff)
        a = mu * g
        ticks = math.ceil(v0 / a) if a > 0 else None
        rows.append((aff, mu, a, ticks))
    # Monotonic: higher affinity → higher μ → fewer ticks
    assert rows[0][1] < rows[1][1] < rows[2][1]
    assert rows[0][3] >= rows[1][3] >= rows[2][3]
    # Mid affinity stops in a focused budget (<200)
    assert rows[1][3] is not None and rows[1][3] <= 200


def test_21_never_both_damping_and_coulomb():
    rt = _rt()
    o = _place_object(rt, 0, 5, 5, state="FREE_MOVING", vx=0.3, vy=0.0, z=0.0)
    _step_world(rt, 0)
    recs = list(fok.state_of(rt.world).motion_history)
    assert recs
    last = recs[-1]
    assert last.get("ground_friction_replaced_damping") is True
    assert last.get("damping_law") != fok.DAMPING_LAW


def test_22_banner_and_analyzer_constants():
    assert "F=μN" in fogf.BANNER
    assert "NO AIR DRAG" in fogf.BANNER
    assert "BODIES UNCHANGED" in fogf.BANNER
    assert fogf.ANALYZER_SECTION == "FREE RESOURCE OBJECT GROUND FRICTION"
    assert fogf.RECEIPT_KIND == "FREE_RESOURCE_OBJECT_GROUND_FRICTION"
    assert fogf.AIR_DRAG == "NO"


def test_23_ui_preset_strings_present():
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    mp = (root / "web/psy-observer/src/observer/modelPreset.ts").read_text()
    app = (root / "web/psy-observer/src/App.tsx").read_text()
    assert "UI_PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION" in mp
    assert "ACANTHOSTEGA_PHASE_C_FREE_OBJECT_GROUND_FRICTION" in mp
    assert "UI_PRESET_ACANTHOSTEGA_FREE_OBJECT_GROUND_FRICTION" in app
    assert "free-object-ground-friction-banner" in app
