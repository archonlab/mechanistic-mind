"""Slope dynamics work-identity + activation gate (live activation OFF)."""
from __future__ import annotations

import math

import pytest

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def test_height_field_reduction_coulomb_matched_flat_zero():
    from mechanistic_mind.physical_system.slope_dynamics_work_identity import (
        height_field_xy_gravity_acceleration,
    )

    r = height_field_xy_gravity_acceleration(n_hat=(0.0, 0.0, 1.0), g=1.1)
    assert abs(r["a_xy_magnitude"]) <= 1e-12
    assert r["flat"] is True


def test_height_field_coulomb_matched_equals_gt_mag():
    from mechanistic_mind.physical_system.slope_dynamics_work_identity import (
        height_field_xy_gravity_acceleration,
    )

    hx = 0.2
    mag = math.sqrt(hx * hx + 1.0)
    n = (-hx / mag, 0.0, 1.0 / mag)
    r = height_field_xy_gravity_acceleration(n_hat=n, g=1.1, mode="COULOMB_MATCHED")
    assert r["a_xy_magnitude"] == pytest.approx(
        r["candidate_tangent_gravity_magnitude"], rel=0, abs=1e-12
    )
    assert r["a_xy"][0] < 0.0


def test_work_identity_measurement_only_closes():
    from mechanistic_mind.physical_system.slope_dynamics_work_identity import (
        build_work_identity_receipt,
        classify_policy_c_mutation,
        POLICY_C_ROLE_ACTUATOR_MIXTURE,
        POLICY_C_ROLE_MEASUREMENT_ONLY,
    )

    mix = classify_policy_c_mutation(
        endpoint_delta_u=-0.5,
        endpoint_pe_applied=0.0,
        endpoint_pe_dissipated=0.5,
        measurement_only=False,
    )
    assert mix["policy_c_role"] == POLICY_C_ROLE_ACTUATOR_MIXTURE
    assert mix["policy_c_actuator_mutation"] == pytest.approx(0.5)

    pc = classify_policy_c_mutation(
        endpoint_delta_u=-0.5,
        endpoint_pe_applied=0.0,
        endpoint_pe_dissipated=0.0,
        measurement_only=True,
    )
    assert pc["policy_c_role"] == POLICY_C_ROLE_MEASUREMENT_ONLY
    assert pc["policy_c_actuator_mutation"] == 0.0

    wi = build_work_identity_receipt(
        tick=1,
        entity_id="a",
        entity_kind="body",
        k_start=0.0,
        k_end=0.4,
        z_start=1.0,
        z_end=0.5,
        m_eff=1.0,
        g=1.0,
        delta_u=-0.5,
        d_friction=0.1,
        w_motor=0.0,
        endpoint_pe_applied=0.0,
        endpoint_pe_dissipated=0.0,
        measurement_only=True,
    )
    assert wi["residual"] == pytest.approx(0.0, abs=1e-12)
    assert wi["within_tolerance"] is True


def test_policy_c_parent_still_actuator_mixture():
    from mechanistic_mind.physical_system.continuous_gravitational_pe import apply_endpoint_pe_to_body

    class _B:
        mechanical_work_reservoir = 50.0

    up = {"accepted": True, "endpoint_delta_u": 2.0}
    b = _B()
    apply_endpoint_pe_to_body(b, up, work_reservoir_before=50.0)
    assert b.mechanical_work_reservoir == pytest.approx(48.0)
    assert up["endpoint_pe_applied"] == pytest.approx(2.0)

    down = {"accepted": True, "endpoint_delta_u": -1.5}
    apply_endpoint_pe_to_body(_B(), down, work_reservoir_before=50.0)
    assert down["endpoint_pe_dissipated"] == pytest.approx(1.5)
    assert down["endpoint_pe_applied"] == 0.0


def test_preset_live_activation_on():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS,
        acanthostega_coherent_slope_dynamics_config,
        acanthostega_tangent_gravity_diagnostic_shadow_config,
    )
    from mechanistic_mind.physical_system.coherent_slope_dynamics import (
        coherent_slope_dynamics_is_active,
        tangent_gravity_physically_active,
        projected_normal_load_physically_active,
        policy_c_measurement_only_required,
    )

    child = acanthostega_coherent_slope_dynamics_config()
    parent = acanthostega_tangent_gravity_diagnostic_shadow_config()
    assert child.public_preset == PUBLIC_PRESET_COHERENT_SLOPE_DYNAMICS
    assert coherent_slope_dynamics_is_active(child) is True
    assert tangent_gravity_physically_active(child) is True
    assert projected_normal_load_physically_active(child) is True
    assert policy_c_measurement_only_required(child) is True
    assert coherent_slope_dynamics_is_active(parent) is False


def test_child_physically_equivalent_to_tangent_parent_on_flat_wait():
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


def test_previous_rest_threshold_blocker_resolved_by_force_aware_rest():
    """Former GATE 14: gentle |g_t| < rest_threshold but drive > friction Survives."""
    from mechanistic_mind.physical_system.body_static_traction_threshold import (
        REST_THRESHOLD_DEFAULT,
    )
    from mechanistic_mind.physical_system.slope_dynamics_work_identity import (
        height_field_xy_gravity_acceleration,
    )
    from mechanistic_mind.physical_system.free_resource_object_ground_friction import (
        coulomb_kinetic_step,
    )

    g = 0.01818181818181818
    mag = math.sqrt(0.05**2 + 1.0)
    n = (-0.05 / mag, 0.0, 1.0 / mag)
    soft = height_field_xy_gravity_acceleration(n_hat=n, g=g)
    gt = float(soft["candidate_tangent_gravity_magnitude"])
    assert gt < float(REST_THRESHOLD_DEFAULT)
    step = coulomb_kinetic_step(
        -gt,
        0.0,
        mu_k=0.01,
        g=g,
        dt=1.0,
        rest_threshold=float(REST_THRESHOLD_DEFAULT),
        drive_accel=gt,
    )
    assert step["speed_after"] > 0.0
    assert step["rest_clamp_suppressed_by_drive"] is True


def test_live_force_path_ready_when_enabled():
    """Infrastructure present with shipping preset enabled."""
    from mechanistic_mind.model.acanthostega import acanthostega_coherent_slope_dynamics_config
    from mechanistic_mind.physical_system.coherent_slope_dynamics import (
        coherent_slope_dynamics_is_active,
        query_body_slope_forces,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import plant_elevations
    from mechanistic_mind.physical_system import surface_elevation_support as ses

    cfg = acanthostega_coherent_slope_dynamics_config()
    assert coherent_slope_dynamics_is_active(cfg) is True
    rt = PhysicalSystemRuntime(seed=7, config=cfg)
    plant_elevations(rt.world, lambda cx, cy: 0.05 * cx)
    b = rt.body
    b.x, b.y = 5.5, 5.5
    b.grounded = True
    b.z = float(ses.surface_support_height(rt.world, b.x, b.y, config=rt.config))
    g = float(ses._read_g(rt.world))
    q = query_body_slope_forces(rt.world, rt.config, body=b, m_eff=2.0, g=g, grounded=True)
    assert q is not None
    assert q["g_t_magnitude"] > 0.0
    assert q["a_xy"][0] < 0.0
    _tick()
