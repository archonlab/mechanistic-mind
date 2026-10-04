"""Targeted tests for slope-terrain PE-shadow validation fixture (diagnostic only)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

TICK_COUNTER = {"n": 0}


def _count(n: int) -> None:
    TICK_COUNTER["n"] += int(n)


def test_fixture_determinism():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import (
        run_validation_suite,
    )

    rows1, sum1, t1 = run_validation_suite(seed=17)
    rows2, sum2, t2 = run_validation_suite(seed=17)
    _count(t1 + t2)
    assert t1 == t2 == 8
    assert [r["comparison_class"] for r in rows1] == [r["comparison_class"] for r in rows2]
    assert [r["plan_accepted"] for r in rows1] == [r["plan_accepted"] for r in rows2]
    assert [r.get("delta_z_authoritative") for r in rows1] == [
        r.get("delta_z_authoritative") for r in rows2
    ]
    assert sum1["comparison_counts"] == sum2["comparison_counts"]


def test_natural_corpus_real_runtime_no_stubs():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import (
        CASE_FLAT,
        CASE_SMOOTH_DOWNHILL,
        CASE_SMOOTH_UPHILL,
        CASE_TOPO_CLIMB,
        CASE_TOPO_DESCENT,
        CASE_LEDGE_BLOCK,
        CASE_FACE_SWEEP_BLOCK,
        CASE_SMOOTH_CELL_BOUNDARY,
        run_validation_suite,
        write_corpus,
        RESULTS_DIR,
    )

    rows, summary, ticks = run_validation_suite(seed=17)
    _count(ticks)
    write_corpus(rows, summary, out_dir=RESULTS_DIR)

    assert summary["stubbed_ses_in_corpus"] is False
    assert summary["stubbed_pe_in_corpus"] is False
    assert all(not r.get("stubbed_ses") for r in rows)
    assert all(not r.get("stubbed_pe") for r in rows)
    assert summary["rejected_displacement_false_pe_evidence"] == 0

    by = {r["terrain_fixture_case"]: r for r in rows}

    flat = by[CASE_FLAT]
    assert flat["plan_accepted"] is True
    assert flat["comparison_class"] == "ZERO_BOTH"
    assert abs(float(flat["candidate_endpoint_delta_u"])) <= 1e-15

    up = by[CASE_SMOOTH_UPHILL]
    assert up["plan_accepted"] is True
    assert up["event_kind"] == "LEVEL"
    assert up["transition_class"] == "SMOOTH_PATCH_TRAVERSAL"
    assert float(up["delta_z_authoritative"]) > 0.0
    assert float(up["candidate_endpoint_delta_u"]) > 0.0
    assert abs(float(up["current_ses_gravitational_delta"])) <= 1e-15
    assert up["comparison_class"] == "CANDIDATE_ONLY"

    down = by[CASE_SMOOTH_DOWNHILL]
    assert down["plan_accepted"] is True
    assert down["event_kind"] == "LEVEL"
    assert float(down["delta_z_authoritative"]) < 0.0
    assert float(down["candidate_endpoint_delta_u"]) < 0.0
    assert abs(float(down["current_ses_gravitational_delta"])) <= 1e-15
    assert down["comparison_class"] == "CANDIDATE_ONLY"

    cell = by[CASE_SMOOTH_CELL_BOUNDARY]
    assert cell["plan_accepted"] is True
    assert "MICRO" in str(cell["plan_event_kinds"][0])
    assert cell["comparison_class"] == "MATCH"

    climb = by[CASE_TOPO_CLIMB]
    assert climb["plan_accepted"] is True
    assert climb["event_kind"] == "MICRO_UPHILL"
    assert climb["comparison_class"] == "MATCH"
    assert float(climb["candidate_endpoint_delta_u"]) == pytest.approx(
        float(climb["current_ses_gravitational_delta"])
    )

    desc = by[CASE_TOPO_DESCENT]
    assert desc["plan_accepted"] is True
    assert desc["event_kind"] == "MICRO_DOWNHILL_INELASTIC"
    assert desc["comparison_class"] == "MATCH"

    ledge = by[CASE_LEDGE_BLOCK]
    assert ledge["plan_accepted"] is False
    assert ledge["plan_block_reason"] == "LARGE_UPHILL_BLOCKED"
    assert ledge["candidate_endpoint_delta_u"] is None

    face = by[CASE_FACE_SWEEP_BLOCK]
    assert face["plan_accepted"] is False
    assert face["plan_block_reason"] == "RADIUS_FACE_BARRIER"
    assert face["candidate_endpoint_delta_u"] is None

    assert summary["natural_level_nonzero_ses_zero"] >= 2
    assert summary["candidate_only"] >= 2


def test_candidate_delta_u_sign_matches_delta_z():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import run_validation_suite

    rows, _, ticks = run_validation_suite(seed=17)
    _count(ticks)
    for r in rows:
        cu = r.get("candidate_endpoint_delta_u")
        dz = r.get("delta_z_authoritative")
        if cu is None or dz is None:
            continue
        if abs(float(dz)) <= 1e-15 and abs(float(cu)) <= 1e-15:
            continue
        assert float(cu) * float(dz) > 0.0


def test_physics_flags_unchanged():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
    )
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        CONTINUOUS_PE_ACTIVE,
        CURRENT_PE_AUTHORITY,
        PE_AUTHORITY_SES_DDA,
    )
    from mechanistic_mind.physical_system.continuous_gravitational_pe_diagnostic_shadow import (
        continuous_gravitational_pe_diagnostic_shadow_is_active,
    )
    from mechanistic_mind.physical_system.diagnostic_normal_load_shadow import (
        diagnostic_normal_load_shadow_is_active,
    )

    cfg = acanthostega_continuous_gravitational_pe_diagnostic_shadow_config()
    assert continuous_gravitational_pe_diagnostic_shadow_is_active(cfg)
    assert diagnostic_normal_load_shadow_is_active(cfg)
    assert CURRENT_PE_AUTHORITY == PE_AUTHORITY_SES_DDA
    assert CONTINUOUS_PE_ACTIVE is False


def test_parent_child_still_equivalent_after_fixture_module():
    """Fixture module must not alter production physics of parent vs child presets."""
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

    parent = PhysicalSystemRuntime(seed=41, config=acanthostega_diagnostic_normal_load_shadow_config())
    child = PhysicalSystemRuntime(
        seed=41, config=acanthostega_continuous_gravitational_pe_diagnostic_shadow_config()
    )
    dp, dc = [], []
    for _ in range(6):
        parent.step()
        child.step()
        dp.append(dig(parent))
        dc.append(dig(child))
    _count(12)
    assert dp == dc


def test_cognition_privacy():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_continuous_gravitational_pe_diagnostic_shadow_config,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.scientific_v3.continuous_gravitational_pe_diagnostic_shadow_summary import (
        COGNITION_FORBIDDEN_TOKENS,
    )

    rt = PhysicalSystemRuntime(
        seed=5, config=acanthostega_continuous_gravitational_pe_diagnostic_shadow_config()
    )
    rt.step()
    _count(1)
    blob = str(rt.last_agent_observation)
    for tok in COGNITION_FORBIDDEN_TOKENS:
        assert tok not in blob, tok


def test_snapshot_restore_fixture_case():
    """Restore a clean runtime, then run the same fixture case — results match."""
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import (
        build_cases,
        make_runtime,
        run_case,
    )
    from mechanistic_mind.physical_system import surface_elevation_support as ses
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = make_runtime(seed=19)
    ses.ensure_surface_elevation_support_for_runtime(rt.world, rt.config)
    snap = rt.snapshot()  # before terrain plant / movement
    rt2 = PhysicalSystemRuntime.restore(snap)
    ses.ensure_surface_elevation_support_for_runtime(rt2.world, rt2.config)

    case = [c for c in build_cases() if c.case_id == "B_SMOOTH_UPHILL"][0]
    row1 = run_case(rt, case, tick=200)
    row2 = run_case(rt2, case, tick=200)
    _count(2)
    assert row1["plan_accepted"] == row2["plan_accepted"] is True
    assert row1["comparison_class"] == row2["comparison_class"] == "CANDIDATE_ONLY"
    assert float(row1["delta_z_authoritative"]) == pytest.approx(
        float(row2["delta_z_authoritative"]), rel=0, abs=1e-12
    )
    assert float(row1["candidate_endpoint_delta_u"]) == pytest.approx(
        float(row2["candidate_endpoint_delta_u"]), rel=0, abs=1e-15
    )


def test_tick_budget():
    assert TICK_COUNTER["n"] <= 300


def test_corpus_file_machine_readable():
    from experiments.acanthostega_slope_terrain_pe_shadow_validation import (
        RESULTS_DIR,
        CORPUS_NAME,
        run_validation_suite,
        write_corpus,
    )

    rows, summary, ticks = run_validation_suite(seed=17)
    _count(ticks)
    path = write_corpus(rows, summary, out_dir=RESULTS_DIR)
    assert path.name == CORPUS_NAME
    loaded = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert len(loaded) == 8
    assert (RESULTS_DIR / "CORPUS_SUMMARY.json").is_file()
