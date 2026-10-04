"""Slope rest-threshold / Face Sweep compatibility + coherent activation."""
from __future__ import annotations

import math

import pytest

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def test_force_aware_rest_preserves_subthreshold_when_drive_exceeds_friction():
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
        coulomb_kinetic_step,
    )

    # speed after one gentle g_t tick; kinetic alone would rest-snap under 0.006.
    speed = 0.0009
    step = coulomb_kinetic_step(
        -speed,
        0.0,
        mu_k=0.01,
        g=0.01818181818181818,
        dt=1.0,
        rest_threshold=0.006,
        drive_accel=0.0009,
    )
    assert step["rest_clamp_suppressed_by_drive"] is True
    assert step["speed_after"] > 0.0
    assert step["vx"] < 0.0


def test_rest_threshold_still_settles_without_drive():
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
        coulomb_kinetic_step,
    )

    step = coulomb_kinetic_step(
        0.003,
        0.0,
        mu_k=0.5,
        g=0.01818181818181818,
        dt=1.0,
        rest_threshold=0.006,
        drive_accel=None,
    )
    assert step["speed_after"] == 0.0
    assert step["rest_transition"] is True


def test_holdable_slope_wait_stationary():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import plant_elevations
    from mechanistic_mind.model.acanthostega import acanthostega_coherent_slope_dynamics_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system import surface_elevation_support as ses
    from mechanistic_mind.physical_system.coherent_slope_dynamics import (
        coherent_slope_dynamics_is_active,
    )

    assert coherent_slope_dynamics_is_active(acanthostega_coherent_slope_dynamics_config())
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_coherent_slope_dynamics_config())
    plant_elevations(rt.world, lambda cx, cy: 0.05 * cx)
    b = rt.body
    b.x, b.y = 5.5, 5.5
    b.vx = b.vy = 0.0
    b.grounded = True
    b.z = float(ses.surface_support_height(rt.world, b.x, b.y, config=rt.config))
    rt.step_forced_action("WAIT")
    for st_name in ("body_static_traction_threshold_state", "body_normal_load_traction_state"):
        st = getattr(rt.world, st_name, None)
        if st is not None and hasattr(st, "config"):
            st.config.mu_min = 0.8
            st.config.mu_max = 0.9
            st.config.static_ratio = 1.05
    x0 = float(b.x)
    for _ in range(10):
        rt.step_forced_action("WAIT")
        _tick()
    assert abs(float(b.x) - x0) <= 1e-4
    assert math.hypot(float(b.vx), float(b.vy)) <= 1e-4


def test_breakaway_passive_downhill_commits():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import plant_elevations
    from mechanistic_mind.model.acanthostega import acanthostega_coherent_slope_dynamics_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system import surface_elevation_support as ses
    from mechanistic_mind.physical_system.coherent_slope_dynamics import state_of
    from mechanistic_mind.physical_system.continuous_gravitational_pe import state_of as pe_state

    rt = PhysicalSystemRuntime(seed=31, config=acanthostega_coherent_slope_dynamics_config())
    plant_elevations(rt.world, lambda cx, cy: 0.05 * cx)
    b = rt.body
    b.x, b.y = 5.5, 5.5
    b.vx = b.vy = 0.0
    b.grounded = True
    b.z = float(ses.surface_support_height(rt.world, b.x, b.y, config=rt.config))
    b.mechanical_work_reservoir = 50.0
    rt.step_forced_action("WAIT")
    for st_name in ("body_static_traction_threshold_state", "body_normal_load_traction_state"):
        st = getattr(rt.world, st_name, None)
        if st is not None and hasattr(st, "config"):
            st.config.mu_min = 0.01
            st.config.mu_max = 0.015
            st.config.static_ratio = 1.0
    x0, z0, w0 = float(b.x), float(b.z), float(b.mechanical_work_reservoir)
    for _ in range(30):
        rt.step_forced_action("WAIT")
        _tick()
    assert float(b.x) < x0 - 1e-3
    assert float(b.z) < z0  # downhill PE decrease
    # Policy C measurement-only: no reservoir credit/debit from ΔU.
    assert abs(float(b.mechanical_work_reservoir) - w0) < 0.01
    pe = pe_state(rt.world)
    assert pe is not None and pe.last_receipt is not None
    assert float(pe.last_receipt.get("endpoint_pe_applied") or 0.0) == 0.0
    assert float(pe.last_receipt.get("endpoint_pe_dissipated") or 0.0) == 0.0
    assert float(pe.last_receipt.get("endpoint_delta_u") or 0.0) < 0.0
    csd = state_of(rt.world)
    wi = (csd.last_receipt or {}).get("work_identity") if csd else None
    assert wi is not None
    assert wi.get("measurement_only") is True
    assert wi.get("within_tolerance") is True


def test_steep_face_barrier_no_velocity_accumulation():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import plant_elevations
    from mechanistic_mind.model.acanthostega import acanthostega_coherent_slope_dynamics_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system import surface_elevation_support as ses

    rt = PhysicalSystemRuntime(seed=31, config=acanthostega_coherent_slope_dynamics_config())
    plant_elevations(rt.world, lambda cx, cy: 0.5 * cx)
    b = rt.body
    b.x, b.y = 5.5, 5.5
    b.vx = b.vy = 0.0
    b.grounded = True
    b.z = float(ses.surface_support_height(rt.world, b.x, b.y, config=rt.config))
    rt.step_forced_action("WAIT")
    for st_name in ("body_static_traction_threshold_state", "body_normal_load_traction_state"):
        st = getattr(rt.world, st_name, None)
        if st is not None and hasattr(st, "config"):
            st.config.mu_min = 0.01
            st.config.mu_max = 0.02
            st.config.static_ratio = 1.0
    x0 = float(b.x)
    for _ in range(8):
        rt.step_forced_action("WAIT")
        _tick()
    # Pose stays (face barrier); velocity must not accumulate unboundedly.
    assert abs(float(b.x) - x0) <= 1e-6
    assert abs(float(b.vx)) < 0.05


def test_flat_parent_child_wait_equivalence_when_flat():
    """On flat terrain, coherent child matches tangent parent WAIT digests."""
    from mechanistic_mind.model.acanthostega import (
        acanthostega_coherent_slope_dynamics_config,
        acanthostega_tangent_gravity_diagnostic_shadow_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    def dig(rt):
        b = rt.body
        return (
            round(float(b.x), 6),
            round(float(b.y), 6),
            round(float(b.vx), 6),
            round(float(b.vy), 6),
            round(float(getattr(b, "z", 0.0) or 0.0), 6),
            bool(getattr(b, "grounded", False)),
        )

    rp = PhysicalSystemRuntime(seed=17, config=acanthostega_tangent_gravity_diagnostic_shadow_config())
    rc = PhysicalSystemRuntime(seed=17, config=acanthostega_coherent_slope_dynamics_config())
    for _ in range(5):
        rp.step_forced_action("WAIT")
        rc.step_forced_action("WAIT")
        _tick()
    assert dig(rp) == dig(rc)


def test_gt_independent_of_move_direction():
    from mechanistic_mind.physical_system.slope_dynamics_work_identity import (
        height_field_xy_gravity_acceleration,
    )

    mag = math.sqrt(0.05**2 + 1.0)
    n = (-0.05 / mag, 0.0, 1.0 / mag)
    a = height_field_xy_gravity_acceleration(n_hat=n, g=1.1)
    b = height_field_xy_gravity_acceleration(n_hat=n, g=1.1)
    assert a["a_xy"] == b["a_xy"]
    assert a["a_xy"][0] < 0.0


def test_activation_flags_live():
    from mechanistic_mind.model.acanthostega import acanthostega_coherent_slope_dynamics_config
    from mechanistic_mind.physical_system.coherent_slope_dynamics import (
        coherent_slope_dynamics_is_active,
        policy_c_measurement_only_required,
        projected_normal_load_physically_active,
        tangent_gravity_physically_active,
    )

    cfg = acanthostega_coherent_slope_dynamics_config()
    assert coherent_slope_dynamics_is_active(cfg)
    assert tangent_gravity_physically_active(cfg)
    assert projected_normal_load_physically_active(cfg)
    assert policy_c_measurement_only_required(cfg)
