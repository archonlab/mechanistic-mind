"""Policy C continuous gravitational PE — mutex, gates, and activation tests."""
from __future__ import annotations

import pytest

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def test_authority_mutex_rejects_dual_and_invalid():
    from mechanistic_mind.physical_system.continuous_gravitational_pe import (
        GRAV_PE_AUTH_ENDPOINT,
        GRAV_PE_AUTH_SES_DDA,
        validate_authority_selection,
    )

    assert validate_authority_selection(enabled=False, authority=GRAV_PE_AUTH_SES_DDA) == GRAV_PE_AUTH_SES_DDA
    assert validate_authority_selection(enabled=True, authority=GRAV_PE_AUTH_ENDPOINT) == GRAV_PE_AUTH_ENDPOINT
    with pytest.raises(ValueError, match="POLICY_C_ENABLED_REQUIRES_ENDPOINT"):
        validate_authority_selection(enabled=True, authority=GRAV_PE_AUTH_SES_DDA)
    with pytest.raises(ValueError, match="ENDPOINT_AUTHORITY_REQUIRES_MECHANISM"):
        validate_authority_selection(enabled=False, authority=GRAV_PE_AUTH_ENDPOINT)
    with pytest.raises(ValueError, match="MIXED_PE_AUTHORITY"):
        validate_authority_selection(enabled=True, authority="A|B")


def test_parent_remains_ses_dda_child_selects_endpoint():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
        acanthostega_continuous_pe_policy_c_config,
    )
    from mechanistic_mind.physical_system.continuous_gravitational_pe import (
        GRAV_PE_AUTH_ENDPOINT,
        GRAV_PE_AUTH_SES_DDA,
        active_gravitational_pe_authority,
        continuous_pe_active,
        endpoint_pe_physically_active,
        ses_gravitational_charge_suppressed,
    )

    parent = acanthostega_continuous_gravitational_pe_diagnostic_shadow_config()
    child = acanthostega_continuous_pe_policy_c_config()
    assert active_gravitational_pe_authority(parent) == GRAV_PE_AUTH_SES_DDA
    assert endpoint_pe_physically_active(parent) is False
    assert continuous_pe_active(parent) is False
    assert ses_gravitational_charge_suppressed(parent) is False

    assert active_gravitational_pe_authority(child) == GRAV_PE_AUTH_ENDPOINT
    assert endpoint_pe_physically_active(child) is True
    assert continuous_pe_active(child) is True
    assert ses_gravitational_charge_suppressed(child) is True
    assert child.public_preset == "ACANTHOSTEGA_PHASE_C_CONTINUOUS_PE_POLICY_C"


def _run_case(cfg_fn, case_id: str, *, tick: int, reservoir: float = 50.0):
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import build_cases, run_case
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system import surface_elevation_support as ses
    from mechanistic_mind.physical_system.continuous_gravitational_pe import state_of

    rt = PhysicalSystemRuntime(seed=17, config=cfg_fn())
    ses.ensure_surface_elevation_support_for_runtime(rt.world, rt.config)
    rt.body.mechanical_work_reservoir = float(reservoir)
    case = [c for c in build_cases() if c.case_id == case_id][0]
    w0 = float(rt.body.mechanical_work_reservoir)
    row = run_case(rt, case, tick=tick)
    _tick(1)
    st = state_of(rt.world)
    return row, rt, w0, float(rt.body.mechanical_work_reservoir), (st.last_receipt if st else None)


def test_smooth_uphill_policy_c_charges_endpoint_parent_misses():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config as parent_cfg,
        acanthostega_continuous_pe_policy_c_config as child_cfg,
    )

    p, _, pw0, pw1, _ = _run_case(parent_cfg, "B_SMOOTH_UPHILL", tick=401)
    c, _, cw0, cw1, crec = _run_case(child_cfg, "B_SMOOTH_UPHILL", tick=402)
    assert p["plan_accepted"] and c["plan_accepted"]
    assert p["event_kind"] == c["event_kind"] == "LEVEL"
    assert abs(float(p["current_ses_gravitational_delta"])) <= 1e-15
    assert float(p["candidate_endpoint_delta_u"]) > 0.0
    assert abs(pw1 - pw0) <= 1e-12  # parent: no SES charge on LEVEL
    assert float(crec["endpoint_pe_applied"]) == pytest.approx(
        float(c["candidate_endpoint_delta_u"]), rel=0, abs=1e-15
    )
    assert cw1 == pytest.approx(cw0 - float(crec["endpoint_pe_applied"]), rel=0, abs=1e-12)
    assert crec["ses_gravitational_charge_suppressed"] is True


def test_smooth_downhill_policy_c_dissipates_no_credit():
    from mechanistic_mind.model.acanthostega import acanthostega_continuous_pe_policy_c_config as child_cfg

    c, _, w0, w1, crec = _run_case(child_cfg, "C_SMOOTH_DOWNHILL", tick=403)
    assert c["plan_accepted"]
    assert float(c["delta_z_authoritative"]) < 0.0
    assert float(crec["endpoint_delta_u"]) < 0.0
    assert float(crec["endpoint_pe_applied"]) == 0.0
    assert float(crec["endpoint_pe_dissipated"]) == pytest.approx(
        abs(float(crec["endpoint_delta_u"])), rel=0, abs=1e-15
    )
    assert abs(w1 - w0) <= 1e-12  # no reservoir credit


def test_topo_climb_traversal_equivalent_no_double_charge():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config as parent_cfg,
        acanthostega_continuous_pe_policy_c_config as child_cfg,
    )

    p, _, pw0, pw1, _ = _run_case(parent_cfg, "E_TOPO_CLIMB", tick=404)
    c, _, cw0, cw1, crec = _run_case(child_cfg, "E_TOPO_CLIMB", tick=405)
    assert p["plan_accepted"] and c["plan_accepted"]
    assert p["event_kind"] == c["event_kind"] == "MICRO_UPHILL"
    assert float(p["candidate_endpoint_delta_u"]) == pytest.approx(
        float(c["candidate_endpoint_delta_u"]), rel=0, abs=1e-15
    )
    parent_debit = pw0 - pw1
    child_debit = cw0 - cw1
    assert parent_debit == pytest.approx(float(p["current_ses_gravitational_delta"]), rel=0, abs=1e-12)
    assert child_debit == pytest.approx(float(crec["endpoint_pe_applied"]), rel=0, abs=1e-12)
    assert child_debit == pytest.approx(parent_debit, rel=0, abs=1e-12)
    # One charge only under Policy C (SES suppressed; endpoint applied once).
    assert crec["ses_gravitational_charge_suppressed"] is True


def test_topo_descent_policy_c_dissipates_once():
    from mechanistic_mind.model.acanthostega import acanthostega_continuous_pe_policy_c_config as child_cfg

    c, _, w0, w1, crec = _run_case(child_cfg, "F_TOPO_DESCENT", tick=406)
    assert c["plan_accepted"]
    assert c["event_kind"] == "MICRO_DOWNHILL_INELASTIC"
    assert float(crec["endpoint_pe_dissipated"]) > 0.0
    assert float(crec["endpoint_pe_applied"]) == 0.0
    assert abs(w1 - w0) <= 1e-12


def test_blocked_cases_no_endpoint_pe_charge():
    from mechanistic_mind.model.acanthostega import acanthostega_continuous_pe_policy_c_config as child_cfg

    for cid, tick in (("G_LEDGE_BLOCK", 407), ("H_FACE_SWEEP_BLOCK", 408)):
        row, _, w0, w1, crec = _run_case(child_cfg, cid, tick=tick)
        assert row["plan_accepted"] is False
        assert abs(w1 - w0) <= 1e-12
        assert float(crec.get("endpoint_pe_applied") or 0.0) == 0.0
        assert float(crec.get("endpoint_pe_dissipated") or 0.0) == 0.0


def test_flat_zero_endpoint_pe():
    from mechanistic_mind.model.acanthostega import acanthostega_continuous_pe_policy_c_config as child_cfg

    row, _, w0, w1, crec = _run_case(child_cfg, "A_FLAT", tick=409)
    assert row["plan_accepted"]
    assert abs(float(crec["endpoint_delta_u"])) <= 1e-15
    assert abs(w1 - w0) <= 1e-12


def test_projected_n_tangent_slide_still_off():
    from mechanistic_mind.model.acanthostega import acanthostega_continuous_pe_policy_c_config
    from mechanistic_mind.physical_system.ses_decomposition_contract import CONTINUOUS_PE_ACTIVE

    cfg = acanthostega_continuous_pe_policy_c_config()
    pe = cfg.continuous_gravitational_pe.to_dict()
    assert pe["projected_normal_load_active"] is False
    assert pe["tangent_gravity_active"] is False
    assert pe["passive_slope_sliding_active"] is False
    # Module stamp for G2C1 remains False; Policy C queried via config.
    assert CONTINUOUS_PE_ACTIVE is False
    assert pe["continuous_pe_active"] is True


def test_cognition_privacy_policy_c():
    from mechanistic_mind.model.acanthostega import acanthostega_continuous_pe_policy_c_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.scientific_v3.continuous_gravitational_pe_diagnostic_shadow_summary import (
        COGNITION_FORBIDDEN_TOKENS,
    )

    rt = PhysicalSystemRuntime(seed=5, config=acanthostega_continuous_pe_policy_c_config())
    rt.step()
    _tick(1)
    blob = str(rt.last_agent_observation)
    for tok in COGNITION_FORBIDDEN_TOKENS:
        assert tok not in blob, tok
    for tok in ("ENDPOINT_DELTA_U", "POLICY_C", "gravitational_pe_authority", "CONTINUOUS_SUPPORT_HEIGHT"):
        assert tok not in blob, tok


def test_snapshot_restore_preserves_authority_no_duplicate_charge():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import build_cases, run_case
    from mechanistic_mind.model.acanthostega import acanthostega_continuous_pe_policy_c_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system import surface_elevation_support as ses
    from mechanistic_mind.physical_system.continuous_gravitational_pe import (
        active_gravitational_pe_authority,
        GRAV_PE_AUTH_ENDPOINT,
        state_of,
    )

    rt = PhysicalSystemRuntime(seed=19, config=acanthostega_continuous_pe_policy_c_config())
    ses.ensure_surface_elevation_support_for_runtime(rt.world, rt.config)
    assert active_gravitational_pe_authority(rt.config) == GRAV_PE_AUTH_ENDPOINT
    # Snapshot BEFORE terrain plant (column deltas not round-tripable via resulting_layers).
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert active_gravitational_pe_authority(rt2.config) == GRAV_PE_AUTH_ENDPOINT
    ses.ensure_surface_elevation_support_for_runtime(rt2.world, rt2.config)

    case = [c for c in build_cases() if c.case_id == "B_SMOOTH_UPHILL"][0]
    rt.body.mechanical_work_reservoir = 50.0
    rt2.body.mechanical_work_reservoir = 50.0
    run_case(rt, case, tick=500)
    run_case(rt2, case, tick=500)
    _tick(2)
    assert float(rt.body.mechanical_work_reservoir) == pytest.approx(
        float(rt2.body.mechanical_work_reservoir), rel=0, abs=1e-12
    )
    assert float(rt.body.mechanical_work_reservoir) < 50.0

    # Fresh restore of pre-plant snap: authority preserved; no pending charge to replay.
    rt3 = PhysicalSystemRuntime.restore(snap)
    assert active_gravitational_pe_authority(rt3.config) == GRAV_PE_AUTH_ENDPOINT
    st = state_of(rt3.world)
    assert st is None or st.tick_results == {}


def test_previous_presets_physically_unchanged_short_horizon():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
        acanthostega_diagnostic_normal_load_shadow_config,
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

    a = PhysicalSystemRuntime(seed=41, config=acanthostega_diagnostic_normal_load_shadow_config())
    b = PhysicalSystemRuntime(
        seed=41, config=acanthostega_continuous_gravitational_pe_diagnostic_shadow_config()
    )
    da, db = [], []
    for _ in range(4):
        a.step()
        b.step()
        da.append(dig(a))
        db.append(dig(b))
    _tick(8)
    assert da == db


def test_tick_budget():
    assert TICKS["n"] <= 350
