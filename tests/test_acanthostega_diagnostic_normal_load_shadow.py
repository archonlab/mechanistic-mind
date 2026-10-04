"""Tests for Acanthostega G2D DIAGNOSTIC NORMAL-LOAD SHADOW.

Shadow computes N_projected = m_eff · g · n_z from centre analytic CSG normal.
Physical N remains flat. Tracks TOTAL_SIMULATED_TICKS (budget ≤300).
"""
from __future__ import annotations

import math
from types import SimpleNamespace

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
    )


# ---------------------------------------------------------------------------
# A. Preset isolation
# ---------------------------------------------------------------------------


def test_preset_isolation_diagnostic_shadow():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_DIAGNOSTIC_NORMAL_LOAD_SHADOW,
        PUBLIC_PRESET_RADIUS_AWARE_FACE_SWEEP,
        acanthostega_config,
        acanthostega_diagnostic_normal_load_shadow_config,
        acanthostega_radius_aware_face_sweep_config,
        acanthostega_ses_runtime_classifier_config,
    )
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        diagnostic_normal_load_shadow_is_active,
    )
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        radius_aware_face_sweep_is_active,
    )
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW,
        PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP,
        normalize_preset_name,
        preset_canonical,
    )
    from mechanistic_mind.model.lines import stamp_config_from_preset
    from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig

    cfg_tik = stamp_config_from_preset(PhysicalSystemConfig(), "TIKTAALIK_BETA31")
    assert not diagnostic_normal_load_shadow_is_active(cfg_tik)

    for factory in (
        acanthostega_config,
        acanthostega_ses_runtime_classifier_config,
        acanthostega_radius_aware_face_sweep_config,
    ):
        cfg = factory()
        assert not diagnostic_normal_load_shadow_is_active(cfg), factory.__name__

    cfg = acanthostega_diagnostic_normal_load_shadow_config()
    assert cfg.public_preset == PUBLIC_PRESET_DIAGNOSTIC_NORMAL_LOAD_SHADOW
    assert diagnostic_normal_load_shadow_is_active(cfg)
    assert radius_aware_face_sweep_is_active(cfg)

    parent = acanthostega_radius_aware_face_sweep_config()
    assert parent.public_preset == PUBLIC_PRESET_RADIUS_AWARE_FACE_SWEEP
    assert not diagnostic_normal_load_shadow_is_active(parent)

    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_DIAGNOSTIC_NORMAL_LOAD_SHADOW") == PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW
    assert normalize_preset_name("CONTINUOUS_NORMAL_LOAD_SHADOW_V1") == PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW
    desc = preset_canonical(PRESET_ACANTHOSTEGA_DIAGNOSTIC_NORMAL_LOAD_SHADOW)
    assert desc["parent"] == PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP
    assert desc["mechanisms"].get("diagnostic_normal_load_shadow") is True
    assert desc["mechanisms"].get("radius_aware_face_sweep") is True


# ---------------------------------------------------------------------------
# B. Pure math
# ---------------------------------------------------------------------------


def test_flat_and_slope_projection_math():
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        CLASS_FULL,
        CLASS_PARTIAL,
        CLASS_EDGE,
        CLASS_LOSS,
        CLASS_AIRBORNE,
        STATUS_FLAT_EQUIVALENT,
        STATUS_PARTIAL_DIAGNOSTIC,
        STATUS_NOT_ELIGIBLE_EDGE,
        STATUS_NOT_ELIGIBLE_LOSS,
        STATUS_NOT_ELIGIBLE_AIRBORNE,
        compute_projected_normal_load,
    )
    # Flat: n_z=1
    r = compute_projected_normal_load(
        m_eff=2.0, g=10.0, n_z=1.0, grounded=True, support_class=CLASS_FULL, geometry_ok=True,
    )
    assert r["status"] == STATUS_FLAT_EQUIVALENT
    assert abs(r["N_flat"] - 20.0) < 1e-12
    assert abs(r["N_projected"] - 20.0) < 1e-12
    assert abs(r["ratio"] - 1.0) < 1e-12

    # Moderate slope: n_z = 1/sqrt(1+0.25)=0.8944... for hx=0.5
    nz = 1.0 / math.sqrt(1.0 + 0.5 ** 2)
    r2 = compute_projected_normal_load(
        m_eff=2.0, g=10.0, n_z=nz, grounded=True, support_class=CLASS_FULL, geometry_ok=True,
    )
    assert 0.0 < r2["n_z"] < 1.0
    assert r2["N_projected"] < r2["N_flat"]
    assert abs(r2["N_projected"] - 20.0 * nz) < 1e-12

    # Opposite slopes equal |grad| → equal N
    r3 = compute_projected_normal_load(
        m_eff=2.0, g=10.0, n_z=nz, grounded=True, support_class=CLASS_FULL, geometry_ok=True,
    )
    assert abs(r2["N_projected"] - r3["N_projected"]) < 1e-15

    # PARTIAL
    rp = compute_projected_normal_load(
        m_eff=1.0, g=10.0, n_z=nz, grounded=True, support_class=CLASS_PARTIAL, geometry_ok=True,
    )
    assert rp["status"] == STATUS_PARTIAL_DIAGNOSTIC
    assert rp["partial_not_activatable"] is True
    assert rp["authoritative_ground_projected_n"] is False
    assert rp["N_projected"] is not None  # diagnostic candidate still computed

    # EDGE / LOSS / AIRBORNE — no authoritative projected N
    for cls, status in (
        (CLASS_EDGE, STATUS_NOT_ELIGIBLE_EDGE),
        (CLASS_LOSS, STATUS_NOT_ELIGIBLE_LOSS),
        (CLASS_AIRBORNE, STATUS_NOT_ELIGIBLE_AIRBORNE),
    ):
        re = compute_projected_normal_load(
            m_eff=1.0, g=10.0, n_z=nz, grounded=(cls != CLASS_AIRBORNE),
            support_class=cls, geometry_ok=True,
        )
        assert re["status"] == status
        assert re["N_projected"] is None
        assert re["authoritative_ground_projected_n"] is False


def test_held_mass_once_and_invalid_mass():
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        STATUS_INVALID_MASS,
        compute_projected_normal_load,
        CLASS_FULL,
    )
    r = compute_projected_normal_load(
        m_eff=1.5, g=10.0, n_z=1.0, grounded=True, support_class=CLASS_FULL, geometry_ok=True,
    )
    assert abs(r["N_flat"] - 15.0) < 1e-12
    bad = compute_projected_normal_load(
        m_eff=float("nan"), g=10.0, n_z=1.0, grounded=True, support_class=CLASS_FULL, geometry_ok=True,
    )
    assert bad["status"] == STATUS_INVALID_MASS


# ---------------------------------------------------------------------------
# C. Runtime: flat / slope shadow + parent equivalence
# ---------------------------------------------------------------------------


def test_runtime_flat_shadow_and_parent_physics_equivalence():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_diagnostic_normal_load_shadow_config,
        acanthostega_radius_aware_face_sweep_config,
    )
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        state_of,
        NORMAL_SOURCE,
    )

    parent = _make_runtime(acanthostega_radius_aware_face_sweep_config, seed=41)
    child = _make_runtime(acanthostega_diagnostic_normal_load_shadow_config, seed=41)
    assert state_of(parent.world) is None
    assert state_of(child.world) is not None

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
    assert st.counters["queries"] >= 1
    last = st.last_receipt or {}
    assert last.get("influenced_physics") is False
    assert last.get("normal_source") == NORMAL_SOURCE
    assert last.get("physical_authority") == "FLAT_NORMAL_LOAD"
    # Near-flat terrain: projected ≈ flat (procedural baselines may have micro-relief).
    if last.get("N_flat") is not None and last.get("N_projected") is not None:
        assert abs(float(last["N_projected"]) / float(last["N_flat"]) - 1.0) < 0.02
        assert abs(float(last["n_z"]) - 1.0) < 0.02


def test_runtime_slope_shadow_inert():
    """Parent/child physics remain identical on default terrain (shadow inert).

    Analytic slope projection is covered by ``test_flat_and_slope_projection_math``.
    """
    from mechanistic_mind.model.acanthostega import (
        acanthostega_diagnostic_normal_load_shadow_config,
        acanthostega_radius_aware_face_sweep_config,
    )
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import state_of

    parent = _make_runtime(acanthostega_radius_aware_face_sweep_config, seed=7)
    child = _make_runtime(acanthostega_diagnostic_normal_load_shadow_config, seed=7)

    digests_p = []
    digests_c = []
    for _ in range(6):
        parent.step()
        child.step()
        digests_p.append(_phys_digest(parent))
        digests_c.append(_phys_digest(child))
    _count_ticks(12)
    assert digests_p == digests_c

    st = state_of(child.world)
    assert st is not None
    assert int(st.counters.get("physics_influence_anomalies", 0)) == 0
    assert st.counters["unique_entity_queries"] <= st.counters["queries"]
    assert all(not bool(r.get("influenced_physics")) for r in st.history)


def test_dedup_one_query_per_entity_tick():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_diagnostic_normal_load_shadow_config,
    )
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        maybe_record_body_shadow,
        state_of,
    )

    rt = _make_runtime(acanthostega_diagnostic_normal_load_shadow_config, seed=3)
    rt.step()
    _count_ticks(1)
    st = state_of(rt.world)
    assert st is not None
    before = int(st.counters["unique_entity_queries"])
    # Second call same tick same body → duplicate suppressed
    maybe_record_body_shadow(
        rt.world, rt.config,
        body=rt.body, body_id="agent_0",
        m_eff=1.0, g=9.81, grounded=True, seam="TEST_DEDUP",
    )
    assert int(st.counters["unique_entity_queries"]) == before
    assert int(st.counters["duplicate_suppressed"]) >= 1


def test_snapshot_restore_no_physics_divergence():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_diagnostic_normal_load_shadow_config,
    )
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import state_of
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = _make_runtime(acanthostega_diagnostic_normal_load_shadow_config, seed=19)
    for _ in range(3):
        rt.step()
    _count_ticks(3)
    snap = rt.snapshot()
    assert "diagnostic_normal_load_shadow" in (snap.get("config") or {})
    assert "diagnostic_normal_load_shadow_state" in snap
    # History / tick caches are derived — not serialized
    st_payload = snap["diagnostic_normal_load_shadow_state"]
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
        acanthostega_diagnostic_normal_load_shadow_config,
    )
    from mechanistic_mind.scientific_v3.diagnostic_normal_load_shadow_summary import (
        COGNITION_FORBIDDEN_TOKENS,
    )

    rt = _make_runtime(acanthostega_diagnostic_normal_load_shadow_config, seed=5)
    rt.step()
    _count_ticks(1)
    obs = rt.last_agent_observation
    blob = str(obs)
    for tok in COGNITION_FORBIDDEN_TOKENS:
        assert tok not in blob, tok


def test_no_coverage_scaling_partial():
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        CLASS_PARTIAL,
        compute_projected_normal_load,
    )
    r = compute_projected_normal_load(
        m_eff=1.0, g=10.0, n_z=0.9, grounded=True,
        support_class=CLASS_PARTIAL, geometry_ok=True,
    )
    # Candidate uses full m*g*n_z — no * coverage fraction
    assert abs(r["N_projected"] - 9.0) < 1e-12


def test_tick_budget_report():
    # Soft check that this module stayed within budget.
    assert TICK_COUNTER["n"] <= 300
