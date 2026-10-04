"""Tangent gravity diagnostic shadow — pure math, natural terrain, parent equivalence."""
from __future__ import annotations

import math

import pytest

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def test_decompose_flat_zero_and_orthogonality():
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
        EPS_FLAT,
        EPS_ORTH,
        decompose_gravity,
    )

    d = decompose_gravity(n_hat=(0.0, 0.0, 1.0), g=1.1)
    assert abs(d["candidate_tangent_gravity_magnitude"]) <= EPS_FLAT
    assert d["flat"] is True
    assert abs(d["tangent_normal_dot"]) <= EPS_ORTH
    gx, gy, gz = d["gravity_vector"]
    gnx, gny, gnz = d["candidate_normal_gravity_vector"]
    gtx, gty, gtz = d["candidate_tangent_gravity_vector"]
    assert abs(gx - (gnx + gtx)) <= EPS_FLAT
    assert abs(gy - (gny + gty)) <= EPS_FLAT
    assert abs(gz - (gnz + gtz)) <= EPS_FLAT


def test_decompose_slope_points_downhill_independent_of_motor():
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
        EPS_ORTH,
        decompose_gravity,
    )

    # Height increases in +x ⇒ downhill is −x ⇒ g_t_x < 0.
    mag = math.sqrt(0.25 + 1.0)
    n = (-0.5 / mag, 0.0, 1.0 / mag)
    d = decompose_gravity(n_hat=n, g=1.1)
    assert d["candidate_tangent_gravity_magnitude"] > 1e-9
    assert d["candidate_tangent_gravity_vector"][0] < 0.0
    assert abs(d["tangent_normal_dot"]) <= EPS_ORTH
    # Same geometry ⇒ same g_t regardless of any MOVE direction notion.
    d2 = decompose_gravity(n_hat=n, g=1.1)
    assert d["candidate_tangent_gravity_vector"] == d2["candidate_tangent_gravity_vector"]


def test_steeper_slope_larger_gt():
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import decompose_gravity

    def n_for(hx: float):
        mag = math.sqrt(hx * hx + 1.0)
        return (-hx / mag, 0.0, 1.0 / mag)

    soft = decompose_gravity(n_hat=n_for(0.1), g=1.1)
    steep = decompose_gravity(n_hat=n_for(0.5), g=1.1)
    assert steep["candidate_tangent_gravity_magnitude"] > soft["candidate_tangent_gravity_magnitude"]


def test_projected_n_matches_g2d_formula():
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        compute_projected_normal_load,
    )
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import decompose_gravity

    m, g = 1.0, 1.1
    mag = math.sqrt(0.04 + 1.0)
    nz = 1.0 / mag
    proj = compute_projected_normal_load(
        m_eff=m, g=g, n_z=nz, grounded=True, support_class=None, geometry_ok=True
    )
    assert proj["N_projected"] == pytest.approx(m * g * nz)
    # |g · n| = g * nz for g=(0,0,-g) and n_z>0 → N = m |g·n|
    d = decompose_gravity(n_hat=(-0.2 / mag, 0.0, nz), g=g)
    assert abs(d["g_dot_n"]) == pytest.approx(g * nz)


def test_parent_child_physical_equivalence():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_pe_policy_c_config,
        acanthostega_tangent_gravity_diagnostic_shadow_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    def dig(rt):
        b = rt.body
        return (
            round(float(b.x), 9),
            round(float(b.y), 9),
            round(float(b.vx), 9),
            round(float(b.vy), 9),
            round(float(getattr(b, "z", 0.0) or 0.0), 9),
            bool(getattr(b, "grounded", False)),
            round(float(getattr(b, "mechanical_work_reservoir", 0.0) or 0.0), 9),
        )

    parent = PhysicalSystemRuntime(seed=41, config=acanthostega_continuous_pe_policy_c_config())
    child = PhysicalSystemRuntime(seed=41, config=acanthostega_tangent_gravity_diagnostic_shadow_config())
    dp, dc = [], []
    for _ in range(6):
        parent.step()
        child.step()
        dp.append(dig(parent))
        dc.append(dig(child))
    _tick(12)
    assert dp == dc


def test_natural_fixture_flat_and_slope_gt():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import (
        build_cases,
        plant_elevations,
        make_runtime,
    )
    from mechanistic_mind.model.acanthostega import acanthostega_tangent_gravity_diagnostic_shadow_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system import surface_elevation_support as ses
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
        query_tangent_gravity_diagnostic_shadow,
        EPS_FLAT,
    )

    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_tangent_gravity_diagnostic_shadow_config())
    ses.ensure_surface_elevation_support_for_runtime(rt.world, rt.config)
    cases = {c.case_id: c for c in build_cases()}

    # Flat
    plant_elevations(rt.world, cases["A_FLAT"].elevations)
    r = query_tangent_gravity_diagnostic_shadow(
        rt.world, rt.config,
        entity_kind="body", entity_id="agent_0",
        x=10.5, y=10.5, m_eff=1.0, g=1.1, grounded=True, entity=rt.body, tick=10,
    )
    _tick(1)
    assert r is not None
    assert abs(float(r["candidate_tangent_gravity_magnitude"])) <= EPS_FLAT

    # Smooth uphill geometry: nonzero g_t, points downhill (−x for ramp_up)
    plant_elevations(rt.world, cases["B_SMOOTH_UPHILL"].elevations)
    r2 = query_tangent_gravity_diagnostic_shadow(
        rt.world, rt.config,
        entity_kind="body", entity_id="agent_0",
        x=10.5, y=10.5, m_eff=1.0, g=1.1, grounded=True, entity=rt.body, tick=11,
    )
    _tick(1)
    assert float(r2["candidate_tangent_gravity_magnitude"]) > EPS_FLAT
    assert float(r2["candidate_tangent_gravity_vector"][0]) < 0.0
    assert abs(float(r2["tangent_normal_dot"])) <= 1e-9


def test_gt_unchanged_when_displacement_reversed_same_pose():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import build_cases, plant_elevations
    from mechanistic_mind.model.acanthostega import acanthostega_tangent_gravity_diagnostic_shadow_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system import surface_elevation_support as ses
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
        query_tangent_gravity_diagnostic_shadow,
    )

    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_tangent_gravity_diagnostic_shadow_config())
    ses.ensure_surface_elevation_support_for_runtime(rt.world, rt.config)
    case = [c for c in build_cases() if c.case_id == "B_SMOOTH_UPHILL"][0]
    plant_elevations(rt.world, case.elevations)
    a = query_tangent_gravity_diagnostic_shadow(
        rt.world, rt.config, entity_kind="body", entity_id="a",
        x=10.5, y=10.5, m_eff=1.0, g=1.1, grounded=True, tick=20,
        displacement_xy=(0.5, 0.0), policy_c_delta_u=0.001,
    )
    b = query_tangent_gravity_diagnostic_shadow(
        rt.world, rt.config, entity_kind="body", entity_id="b",
        x=10.5, y=10.5, m_eff=1.0, g=1.1, grounded=True, tick=21,
        displacement_xy=(-0.5, 0.0), policy_c_delta_u=-0.001,
    )
    _tick(2)
    assert a["candidate_tangent_gravity_vector"] == b["candidate_tangent_gravity_vector"]
    assert a["pe_sign_consistency"] == "CONSISTENT"
    assert b["pe_sign_consistency"] == "CONSISTENT"


def test_policy_c_natural_pe_sign_consistency_on_fixture():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import build_cases, run_case
    from mechanistic_mind.model.acanthostega import acanthostega_tangent_gravity_diagnostic_shadow_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system import surface_elevation_support as ses
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
        query_tangent_gravity_diagnostic_shadow,
    )

    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_tangent_gravity_diagnostic_shadow_config())
    ses.ensure_surface_elevation_support_for_runtime(rt.world, rt.config)
    rt.body.mechanical_work_reservoir = 50.0
    for cid, tick in (("B_SMOOTH_UPHILL", 30), ("C_SMOOTH_DOWNHILL", 31)):
        case = [c for c in build_cases() if c.case_id == cid][0]
        row = run_case(rt, case, tick=tick)
        _tick(1)
        assert row["plan_accepted"]
        du = float(row["candidate_endpoint_delta_u"])
        dx = float(case.x1) - float(case.x0)
        dy = float(case.y1) - float(case.y0)
        mid_x = 0.5 * (float(case.x0) + float(case.x1))
        mid_y = 0.5 * (float(case.y0) + float(case.y1))
        tg = query_tangent_gravity_diagnostic_shadow(
            rt.world, rt.config,
            entity_kind="body", entity_id="agent_0",
            x=mid_x, y=mid_y, m_eff=float(row.get("m_eff") or 1.0),
            g=float(row.get("g") or 1.1), grounded=True, entity=rt.body,
            tick=tick + 1000,
            displacement_xy=(dx, dy), policy_c_delta_u=du,
        )
        assert tg["pe_sign_consistency"] == "CONSISTENT"


def test_airborne_no_ground_tangent():
    from mechanistic_mind.model.acanthostega import acanthostega_tangent_gravity_diagnostic_shadow_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
        query_tangent_gravity_diagnostic_shadow,
        STATUS_NOT_ELIGIBLE_AIRBORNE,
    )

    rt = PhysicalSystemRuntime(seed=3, config=acanthostega_tangent_gravity_diagnostic_shadow_config())
    rt.body.grounded = False
    r = query_tangent_gravity_diagnostic_shadow(
        rt.world, rt.config,
        entity_kind="body", entity_id="agent_0",
        x=float(rt.body.x), y=float(rt.body.y),
        m_eff=1.0, g=1.1, grounded=False, entity=rt.body, tick=40,
        support_class="AIRBORNE",
    )
    _tick(1)
    assert r["status"] == STATUS_NOT_ELIGIBLE_AIRBORNE
    assert r.get("candidate_tangent_gravity_magnitude") is None


def test_flags_inactive_and_cognition_privacy():
    from mechanistic_mind.model.acanthostega import acanthostega_tangent_gravity_diagnostic_shadow_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.scientific_v3.continuous_gravitational_pe_diagnostic_shadow_summary import (
        COGNITION_FORBIDDEN_TOKENS,
    )

    cfg = acanthostega_tangent_gravity_diagnostic_shadow_config()
    d = cfg.tangent_gravity_diagnostic_shadow.to_dict()
    assert d["tangent_gravity_active"] is False
    assert d["projected_normal_load_active"] is False
    assert d["passive_slope_sliding_active"] is False
    rt = PhysicalSystemRuntime(seed=5, config=cfg)
    rt.step()
    _tick(1)
    blob = str(rt.last_agent_observation)
    for tok in COGNITION_FORBIDDEN_TOKENS:
        assert tok not in blob
    for tok in ("g_t", "tangent_gravity", "BREAKAWAY_EXPECTED", "HOLD_CAPABLE", "n_hat"):
        assert tok not in blob, tok


def test_static_hold_diagnostic_classes():
    from mechanistic_mind.physical_system.tangent_gravity_diagnostic_shadow import (
        BREAKAWAY_EXPECTED,
        HOLD_CAPABLE,
        static_hold_diagnostic,
    )

    hold = static_hold_diagnostic(m_eff=1.0, g_t_xy_magnitude=0.01, mu_s=0.8, N_projected=1.0)
    assert hold["static_hold_classification"] == HOLD_CAPABLE
    brk = static_hold_diagnostic(m_eff=1.0, g_t_xy_magnitude=2.0, mu_s=0.1, N_projected=1.0)
    assert brk["static_hold_classification"] == BREAKAWAY_EXPECTED


def test_policy_c_unchanged_under_child():
    from mechanistic_mind.model.acanthostega import acanthostega_tangent_gravity_diagnostic_shadow_config
    from mechanistic_mind.physical_system.continuous_gravitational_pe import (
        GRAV_PE_AUTH_ENDPOINT,
        active_gravitational_pe_authority,
        endpoint_pe_physically_active,
    )

    cfg = acanthostega_tangent_gravity_diagnostic_shadow_config()
    assert endpoint_pe_physically_active(cfg) is True
    assert active_gravitational_pe_authority(cfg) == GRAV_PE_AUTH_ENDPOINT


def test_tick_budget():
    assert TICKS["n"] <= 300
