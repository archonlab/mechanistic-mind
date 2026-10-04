"""Tests for Acanthostega CONTINUOUS GRAVITATIONAL PE DIAGNOSTIC SHADOW.

Shadow computes candidate Policy C endpoint ΔU = m_eff·g·(z_end−z_start).
Physical PE authority remains SES_DDA. Tracks TOTAL_SIMULATED_TICKS (budget ≤300).
"""
from __future__ import annotations

import math

import pytest

TICK_COUNTER = {"n": 0}


def _count_ticks(n: int) -> None:
    TICK_COUNTER["n"] += int(n)


def _make_runtime(cfg_factory, seed=17):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    return PhysicalSystemRuntime(seed=seed, config=cfg_factory())


def _phys_digest(rt):
    b = rt.body
    return (
        round(float(b.x), 9),
        round(float(b.y), 9),
        round(float(b.vx), 9),
        round(float(b.vy), 9),
        round(float(getattr(b, "z", 0.0) or 0.0), 9),
        round(float(getattr(b, "vz", 0.0) or 0.0), 9),
        bool(getattr(b, "grounded", False)),
        str(getattr(b, "_radius_support_class", None)),
        round(float(getattr(b, "mechanical_work_reservoir", 0.0) or 0.0), 9),
    )


# ---------------------------------------------------------------------------
# A. Preset isolation
# ---------------------------------------------------------------------------


def test_preset_isolation_cgpe_shadow():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
        PUBLIC_PRESET_DIAGNOSTIC_NORMAL_LOAD_SHADOW,
        acanthostega_config,
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
        acanthostega_diagnostic_normal_load_shadow_config,
        acanthostega_radius_aware_face_sweep_config,
    )
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        continuous_gravitational_pe_diagnostic_shadow_is_active,
    )
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        diagnostic_normal_load_shadow_is_active,
    )
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW,
        PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW,
        normalize_preset_name,
        preset_canonical,
    )
    from mechanistic_mind.model.lines import stamp_config_from_preset
    from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        CONTINUOUS_PE_ACTIVE,
        CURRENT_PE_AUTHORITY,
        PE_AUTHORITY_SES_DDA,
    )

    cfg_tik = stamp_config_from_preset(PhysicalSystemConfig(), "TIKTAALIK_BETA31")
    assert not continuous_gravitational_pe_diagnostic_shadow_is_active(cfg_tik)

    for factory in (
        acanthostega_config,
        acanthostega_radius_aware_face_sweep_config,
        acanthostega_diagnostic_normal_load_shadow_config,
    ):
        cfg = factory()
        assert not continuous_gravitational_pe_diagnostic_shadow_is_active(cfg), factory.__name__

    cfg = acanthostega_continuous_gravitational_pe_diagnostic_shadow_config()
    assert cfg.public_preset == PUBLIC_PRESET_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
    assert continuous_gravitational_pe_diagnostic_shadow_is_active(cfg)
    assert diagnostic_normal_load_shadow_is_active(cfg)
    assert CURRENT_PE_AUTHORITY == PE_AUTHORITY_SES_DDA
    assert CONTINUOUS_PE_ACTIVE is False

    parent = acanthostega_diagnostic_normal_load_shadow_config()
    assert parent.public_preset == PUBLIC_PRESET_DIAGNOSTIC_NORMAL_LOAD_SHADOW
    assert not continuous_gravitational_pe_diagnostic_shadow_is_active(parent)

    assert (
        normalize_preset_name("ACANTHOSTEGA_PHASE_C_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW")
        == PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
    )
    assert (
        normalize_preset_name("CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW_V1")
        == PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW
    )
    desc = preset_canonical(PRESET_ACANTHOSTEGA_CONTINUOUS_GRAVITATIONAL_PE_DIAGNOSTIC_SHADOW)
    assert desc["parent"] == PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW
    assert desc["mechanisms"].get("continuous_gravitational_pe_diagnostic_shadow") is True
    assert desc["mechanisms"].get("diagnostic_normal_load_shadow") is True


# ---------------------------------------------------------------------------
# B. Pure math
# ---------------------------------------------------------------------------


def test_endpoint_delta_u_and_comparison_classes():
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        CMP_CANDIDATE_ONLY,
        CMP_DIFFERENT_MAGNITUDE,
        CMP_DIFFERENT_SIGN,
        CMP_MATCH,
        CMP_ZERO_BOTH,
        compare_ses_vs_candidate,
        compute_endpoint_delta_u,
        ses_signed_gravitational_delta,
    )

    # Flat
    assert abs(compute_endpoint_delta_u(m_eff=2.0, g=10.0, z_start=1.0, z_end=1.0)) < 1e-15
    # Uphill
    assert abs(compute_endpoint_delta_u(m_eff=2.0, g=10.0, z_start=1.0, z_end=1.5) - 10.0) < 1e-12
    # Downhill opposite sign
    assert abs(compute_endpoint_delta_u(m_eff=2.0, g=10.0, z_start=1.5, z_end=1.0) + 10.0) < 1e-12

    assert compare_ses_vs_candidate(ses_delta=0.0, candidate_delta_u=0.0) == CMP_ZERO_BOTH
    assert compare_ses_vs_candidate(ses_delta=0.0, candidate_delta_u=1.0) == CMP_CANDIDATE_ONLY
    assert compare_ses_vs_candidate(ses_delta=1.0, candidate_delta_u=1.0) == CMP_MATCH
    assert compare_ses_vs_candidate(ses_delta=1.0, candidate_delta_u=2.0) == CMP_DIFFERENT_MAGNITUDE
    assert compare_ses_vs_candidate(ses_delta=1.0, candidate_delta_u=-1.0) == CMP_DIFFERENT_SIGN

    climb = {"work_debit": 3.0, "kinetic_paid": 0.0, "steps": []}
    assert abs(ses_signed_gravitational_delta(climb) - 3.0) < 1e-15
    down = {"work_debit": 0.0, "kinetic_paid": 0.0, "steps": [{"dissipated_pe": 2.5}]}
    assert abs(ses_signed_gravitational_delta(down) + 2.5) < 1e-15


def test_held_mass_once_in_formula():
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        compute_endpoint_delta_u,
    )
    # m_eff already includes held once — formula must not invent a second term.
    m_eff = 1.0 + 0.5
    du = compute_endpoint_delta_u(m_eff=m_eff, g=10.0, z_start=0.0, z_end=1.0)
    assert abs(du - 15.0) < 1e-12


# ---------------------------------------------------------------------------
# C. Runtime: parent equivalence + shadow receipts
# ---------------------------------------------------------------------------


def test_parent_child_physical_equivalence():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
        acanthostega_diagnostic_normal_load_shadow_config,
    )
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        state_of,
        PE_AUTHORITY_SES_DDA,
    )
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        state_of as dnls_state_of,
    )

    parent = _make_runtime(acanthostega_diagnostic_normal_load_shadow_config, seed=41)
    child = _make_runtime(acanthostega_continuous_gravitational_pe_diagnostic_shadow_config, seed=41)
    assert state_of(parent.world) is None
    assert state_of(child.world) is not None
    assert dnls_state_of(child.world) is not None  # G2D shadow still present

    digests_p = []
    digests_c = []
    for _ in range(8):
        parent.step()
        child.step()
        digests_p.append(_phys_digest(parent))
        digests_c.append(_phys_digest(child))
    _count_ticks(16)
    assert digests_p == digests_c

    st = state_of(child.world)
    assert st is not None
    assert st.counters["queries"] >= 0  # may be 0 if no SES path gate that tick
    last = st.last_receipt or {}
    if last:
        assert last.get("influenced_physics") is False
        assert last.get("candidate_influenced_physics") is False
        assert last.get("continuous_pe_active") is False
        assert last.get("current_pe_authority") == PE_AUTHORITY_SES_DDA
        assert last.get("projected_normal_load_active") is False
        assert last.get("tangent_gravity_active") is False
        assert last.get("current_and_candidate_both_physically_charged") is False


def test_shadow_emits_on_path_gate_and_blocked_has_no_candidate():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
    )
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        STATUS_BLOCKED_NO_COMMIT,
        compare_ses_vs_candidate,
        compute_endpoint_delta_u,
        observe_path_gate_pe_shadow,
        state_of,
    )

    rt = _make_runtime(acanthostega_continuous_gravitational_pe_diagnostic_shadow_config, seed=3)
    for _ in range(4):
        rt.step()
    _count_ticks(4)
    st = state_of(rt.world)
    assert st is not None

    # Synthetic blocked plan — no candidate PE
    plan = {
        "accepted": False,
        "block_reason": "LARGE_UPHILL_BLOCKED",
        "event_kinds": ["LARGE_UPHILL_BLOCKED"],
        "work_debit": 0.0,
        "kinetic_paid": 0.0,
        "steps": [],
        "support_lost": False,
        "x": float(rt.body.x),
        "y": float(rt.body.y),
        "z": float(getattr(rt.body, "z", 0.0) or 0.0),
        "grounded": True,
    }
    # Force new tick for dedup key
    rt.world.tick = int(getattr(rt.world, "tick", 0) or 0) + 100
    r = observe_path_gate_pe_shadow(
        rt.world, rt.config, plan=plan, entity=rt.body,
        entity_kind="body", entity_id="agent_0",
        x0=float(rt.body.x), y0=float(rt.body.y),
        z0=float(getattr(rt.body, "z", 0.0) or 0.0),
        grounded_before=True, m_eff=1.0, g=9.81, tick=int(rt.world.tick),
    )
    assert r is not None
    assert r["status"] == STATUS_BLOCKED_NO_COMMIT
    assert r["candidate_endpoint_delta_u"] is None
    assert r["physically_committed"] is False

    # Pure LEVEL-like candidate-only comparison (architecture key case)
    assert compare_ses_vs_candidate(ses_delta=0.0, candidate_delta_u=0.5) == "CANDIDATE_ONLY"
    assert abs(compute_endpoint_delta_u(m_eff=1.0, g=10.0, z_start=0.0, z_end=0.05) - 0.5) < 1e-12


def test_dedup_one_receipt_per_entity_tick():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
    )
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        observe_path_gate_pe_shadow,
        state_of,
    )

    rt = _make_runtime(acanthostega_continuous_gravitational_pe_diagnostic_shadow_config, seed=11)
    rt.step()
    _count_ticks(1)
    st = state_of(rt.world)
    assert st is not None
    tick = int(getattr(rt.world, "tick", 0) or 0) + 50
    rt.world.tick = tick
    plan = {
        "accepted": True,
        "event_kinds": ["LEVEL"],
        "work_debit": 0.0,
        "kinetic_paid": 0.0,
        "steps": [],
        "support_lost": False,
        "x": float(rt.body.x),
        "y": float(rt.body.y),
        "z": float(getattr(rt.body, "z", 0.0) or 0.0),
        "grounded": True,
    }
    kwargs = dict(
        plan=plan, entity=rt.body, entity_kind="body", entity_id="dedup_body",
        x0=float(rt.body.x), y0=float(rt.body.y),
        z0=float(getattr(rt.body, "z", 0.0) or 0.0),
        grounded_before=True, m_eff=1.0, g=9.81, tick=tick,
    )
    observe_path_gate_pe_shadow(rt.world, rt.config, **kwargs)
    before_unique = int(st.counters["unique_entity_queries"])
    before_dup = int(st.counters["duplicate_suppressed"])
    observe_path_gate_pe_shadow(rt.world, rt.config, **kwargs)
    assert int(st.counters["unique_entity_queries"]) == before_unique
    assert int(st.counters["duplicate_suppressed"]) == before_dup + 1


def test_snapshot_restore_no_physics_divergence():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
    )
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import state_of
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _make_runtime(acanthostega_continuous_gravitational_pe_diagnostic_shadow_config, seed=19)
    for _ in range(3):
        rt.step()
    _count_ticks(3)
    snap = rt.snapshot()
    assert "continuous_gravitational_pe_diagnostic_shadow" in (snap.get("config") or {})
    assert "continuous_gravitational_pe_diagnostic_shadow_state" in snap
    st_payload = snap["continuous_gravitational_pe_diagnostic_shadow_state"]
    assert "history" not in (st_payload or {})
    assert "tick_results" not in (st_payload or {})

    rt2 = PhysicalSystemRuntime.restore(snap)
    d1 = []
    d2 = []
    for _ in range(4):
        rt.step()
        rt2.step()
        d1.append(_phys_digest(rt))
        d2.append(_phys_digest(rt2))
    _count_ticks(8)
    assert d1 == d2
    assert state_of(rt2.world) is not None


def test_cognition_privacy():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
    )
    from mechanistic_mind.scientific_v3.continuous_gravitational_pe_diagnostic_shadow_summary import (
        COGNITION_FORBIDDEN_TOKENS,
    )

    rt = _make_runtime(acanthostega_continuous_gravitational_pe_diagnostic_shadow_config, seed=5)
    rt.step()
    _count_ticks(1)
    obs = rt.last_agent_observation
    blob = str(obs)
    for tok in COGNITION_FORBIDDEN_TOKENS:
        assert tok not in blob, tok


def test_g2d_shadow_still_inert_and_pe_flags():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
    )
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import state_of
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        state_of as dnls_state_of,
    )
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        CONTINUOUS_PE_ACTIVE,
        CURRENT_PE_AUTHORITY,
        PE_AUTHORITY_SES_DDA,
    )

    rt = _make_runtime(acanthostega_continuous_gravitational_pe_diagnostic_shadow_config, seed=7)
    for _ in range(5):
        rt.step()
    _count_ticks(5)
    assert CURRENT_PE_AUTHORITY == PE_AUTHORITY_SES_DDA
    assert CONTINUOUS_PE_ACTIVE is False
    dnls = dnls_state_of(rt.world)
    assert dnls is not None
    assert int(dnls.counters.get("physics_influence_anomalies", 0)) == 0
    st = state_of(rt.world)
    assert st is not None
    assert int(st.counters.get("physics_influence_anomalies", 0)) == 0
    assert all(not bool(r.get("influenced_physics")) for r in st.history)
    assert all(not bool(r.get("continuous_pe_active")) for r in st.history)


def test_analyzer_summary_shape():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
    )
    from mechanistic_mind.scientific_v3.continuous_gravitational_pe_diagnostic_shadow_summary import (
        summarize_continuous_gravitational_pe_diagnostic_shadow,
    )

    rt = _make_runtime(acanthostega_continuous_gravitational_pe_diagnostic_shadow_config, seed=13)
    for _ in range(3):
        rt.step()
    _count_ticks(3)
    s = summarize_continuous_gravitational_pe_diagnostic_shadow(rt.world)
    assert s is not None
    assert s["mode"] == "DIAGNOSTIC_SHADOW"
    assert s["continuous_pe_active"] is False
    assert s["influenced_physics"] is False
    assert s["possible_double_accounting_anomalies"] == 0
    assert "candidate_delta_u" in s
    assert "comparison_counts" in s


def test_level_nonzero_candidate_vs_ses_zero_with_stubbed_heights(monkeypatch):
    """Architecture key case: LEVEL + continuous Δz + SES gravitational charge 0 → CANDIDATE_ONLY."""
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
    )
    from mechanistic_mind.physical_system import continuous_gravitational_pe_diagnostic_shadow as cgpe
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        CMP_CANDIDATE_ONLY,
        observe_path_gate_pe_shadow,
        state_of,
    )

    rt = _make_runtime(acanthostega_continuous_gravitational_pe_diagnostic_shadow_config, seed=23)
    rt.step()
    _count_ticks(1)

    heights = {(0.0, 0.0): 1.0, (1.0, 0.0): 1.25}

    def _stub_height(world, x, y, *, config=None):
        # Quantize to stub keys for determinism
        key = (round(float(x), 0), round(float(y), 0))
        if key in heights:
            return float(heights[key])
        # Fallback linear ramp in x
        return 1.0 + 0.25 * float(x)

    monkeypatch.setattr(
        "mechanistic_mind.physical_system.surface_elevation_support.surface_support_height",
        _stub_height,
    )

    tick = int(getattr(rt.world, "tick", 0) or 0) + 77
    rt.world.tick = tick
    plan = {
        "accepted": True,
        "event_kinds": ["LEVEL"],
        "work_debit": 0.0,
        "kinetic_paid": 0.0,
        "steps": [],
        "support_lost": False,
        "x": 1.0,
        "y": 0.0,
        "z": 1.25,
        "grounded": True,
    }
    # Pose endpoint for entity
    rt.body.x = 1.0
    rt.body.y = 0.0
    rt.body.z = 1.25
    rt.body.grounded = True
    r = observe_path_gate_pe_shadow(
        rt.world, rt.config, plan=plan, entity=rt.body,
        entity_kind="body", entity_id="level_nz_probe",
        x0=0.0, y0=0.0, z0=1.0, grounded_before=True,
        m_eff=2.0, g=10.0, tick=tick,
    )
    assert r is not None
    assert r["event_kind"] == "LEVEL"
    assert abs(float(r["delta_z_authoritative"]) - 0.25) < 1e-12
    assert abs(float(r["candidate_endpoint_delta_u"]) - 5.0) < 1e-12  # 2*10*0.25
    assert abs(float(r["current_ses_gravitational_delta"])) < 1e-15
    assert r["comparison_class"] == CMP_CANDIDATE_ONLY
    assert r["candidate_influenced_physics"] is False
    assert int(state_of(rt.world).counters["level_nonzero_candidate"]) >= 1


def test_tick_budget_report():
    assert TICK_COUNTER["n"] <= 300
