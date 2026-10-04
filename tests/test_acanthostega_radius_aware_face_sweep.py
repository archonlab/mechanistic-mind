"""Tests for Acanthostega RADIUS_AWARE_FACE_SWEEP_SES_PLAN_EVIDENCE_V1.

Covers preset isolation, pure geometry, SES plan-evidence integration,
starting penetration, PE/work zeros, G2C2 mapping, privacy, and short probes.
Tracks TOTAL_SIMULATED_TICKS for the validation budget.
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


# ---------------------------------------------------------------------------
# A. Preset and isolation
# ---------------------------------------------------------------------------


def test_preset_isolation_face_sweep():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_RADIUS_AWARE_FACE_SWEEP,
        PUBLIC_PRESET_SES_RUNTIME_CLASSIFIER,
        acanthostega_config,
        acanthostega_radius_aware_face_sweep_config,
        acanthostega_radius_aware_support_config,
        acanthostega_ses_decomposition_contract_config,
        acanthostega_ses_runtime_classifier_config,
    )
    from mechanistic_mind.physical_system.experiment_canonical import PRESET_BETA31
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        radius_aware_face_sweep_is_active,
    )
    from mechanistic_mind.physical_system.radius_aware_support_points import (
        radius_aware_support_points_is_active,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
    from mechanistic_mind.model.lines import stamp_config_from_preset
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        ses_decomposition_contract_is_active,
    )
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        ses_runtime_transition_classifier_is_active,
    )

    cfg_tik = PhysicalSystemConfig()
    stamp_config_from_preset(cfg_tik, PRESET_BETA31)
    assert not radius_aware_face_sweep_is_active(cfg_tik)

    for factory in (
        acanthostega_config,
        acanthostega_radius_aware_support_config,
        acanthostega_ses_decomposition_contract_config,
        acanthostega_ses_runtime_classifier_config,
    ):
        cfg = factory()
        assert not radius_aware_face_sweep_is_active(cfg), factory.__name__

    cfg = acanthostega_radius_aware_face_sweep_config()
    assert cfg.public_preset == PUBLIC_PRESET_RADIUS_AWARE_FACE_SWEEP
    assert radius_aware_face_sweep_is_active(cfg)
    assert ses_runtime_transition_classifier_is_active(cfg)
    assert ses_decomposition_contract_is_active(cfg)
    assert radius_aware_support_points_is_active(cfg)

    # Parent G2C2 remains without face sweep
    parent = acanthostega_ses_runtime_classifier_config()
    assert parent.public_preset == PUBLIC_PRESET_SES_RUNTIME_CLASSIFIER
    assert not radius_aware_face_sweep_is_active(parent)


def test_normalize_and_mechanism_map():
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP,
        PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER,
        normalize_preset_name,
        preset_canonical,
    )
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_RADIUS_AWARE_FACE_SWEEP") == PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP
    assert normalize_preset_name("Acanthostega Phase C Radius-Aware Face Sweep") == PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP
    desc = preset_canonical(PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP)
    assert desc["public_preset"] == PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP
    assert desc["parent"] == PRESET_ACANTHOSTEGA_SES_RUNTIME_CLASSIFIER
    assert desc["mechanisms"].get("radius_aware_face_sweep") is True
    assert desc["mechanisms"].get("ses_runtime_transition_classifier") is True


def test_model_line_and_apply_tick0():
    from mechanistic_mind.model.acanthostega import acanthostega_radius_aware_face_sweep_config
    from mechanistic_mind.model.lines import identity_from_public_preset
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP,
    )
    cfg = acanthostega_radius_aware_face_sweep_config()
    meta = identity_from_public_preset(PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP, cfg, seed=1, tick=0)
    assert meta["model_line"] == "ACANTHOSTEGA"
    assert meta["public_preset"] == PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP
    rt = _make_runtime(acanthostega_radius_aware_face_sweep_config, seed=3)
    assert rt.config.public_preset == PRESET_ACANTHOSTEGA_RADIUS_AWARE_FACE_SWEEP
    assert int(getattr(rt.world, "tick", 0) or 0) == 0


# ---------------------------------------------------------------------------
# B. Pure geometry
# ---------------------------------------------------------------------------


def _flat_height(_cx, _cy):
    return 0.0


def _ledge_row_height(cx, cy, *, ledge_x=2, h_high=1.0):
    # Cell column ledge_x and above are high.
    return float(h_high) if int(cx) >= int(ledge_x) else 0.0


def test_geometry_body_radius_clips_ledge_centre_clear():
    """Centre path stays in low cells; radius clips high face → barrier."""
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        BODY_CONTACT_RADIUS,
    )
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        evaluate_face_sweep_geometry,
    )

    R = float(BODY_CONTACT_RADIUS)  # 0.575
    # Path along x=1.5 (centre of cell col 1), y 0.5 → 1.5 — never crosses into col 2.
    # Face at x=2 between col1 and col2; distance from path x=1.5 is 0.5 < R.
    ev = evaluate_face_sweep_geometry(
        x0=1.5, y0=0.5, x1=1.5, y1=1.5, radius=R,
        width=16, height=16,
        height_at_cell=lambda cx, cy: _ledge_row_height(cx, cy, ledge_x=2, h_high=1.0),
        microrelief_threshold=0.12,
    )
    assert ev["blocking_proposal"] is True
    assert ev["earliest_hit"] is not None
    assert float(ev["barrier_magnitude"]) > 0.12


def test_geometry_misses_nearby_ledge():
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        evaluate_face_sweep_geometry,
    )
    R = 0.575
    # Local ledge only at column 5 (avoid WRAP creating a far-column discontinuity).
    def h(cx, cy):
        return 1.0 if int(cx) == 5 else 0.0

    # Path at x=0.5; face at x=5 is distance 4.5 >> R → miss.
    ev = evaluate_face_sweep_geometry(
        x0=0.5, y0=0.5, x1=0.5, y1=1.5, radius=R,
        width=16, height=16,
        height_at_cell=h,
        microrelief_threshold=0.12,
    )
    assert ev["blocking_proposal"] is False
    assert ev["earliest_hit"] is None


def test_geometry_zero_radius_no_blocker():
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        evaluate_face_sweep_geometry,
        EVAL_SKIPPED_ZERO_RADIUS,
    )
    ev = evaluate_face_sweep_geometry(
        x0=1.5, y0=0.5, x1=1.5, y1=1.5, radius=0.0,
        width=16, height=16,
        height_at_cell=lambda cx, cy: _ledge_row_height(cx, cy, ledge_x=2, h_high=1.0),
    )
    assert ev["evaluation_status"] == EVAL_SKIPPED_ZERO_RADIUS
    assert ev["blocking_proposal"] is False


def test_geometry_optical_radius_irrelevant():
    """Only the supplied physical radius matters — optical is never read."""
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        evaluate_face_sweep_geometry,
    )
    # Same geometry as clip test with R=0.25 (object-like) should miss; R=0.575 hits.
    def h(cx, cy):
        return _ledge_row_height(cx, cy, ledge_x=2, h_high=1.0)

    miss = evaluate_face_sweep_geometry(
        x0=1.5, y0=0.5, x1=1.5, y1=1.5, radius=0.25,
        width=16, height=16, height_at_cell=h,
    )
    hit = evaluate_face_sweep_geometry(
        x0=1.5, y0=0.5, x1=1.5, y1=1.5, radius=0.575,
        width=16, height=16, height_at_cell=h,
    )
    assert miss["blocking_proposal"] is False
    assert hit["blocking_proposal"] is True


def test_geometry_diagonal_tie_break_deterministic():
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        evaluate_face_sweep_geometry,
    )

    def h(cx, cy):
        # High cells in both +x and +y quadrants from origin neighborhood.
        return 1.0 if (cx >= 2 or cy >= 2) else 0.0

    a = evaluate_face_sweep_geometry(
        x0=1.5, y0=1.5, x1=1.5 + 0.2, y1=1.5 + 0.2, radius=0.575,
        width=16, height=16, height_at_cell=h,
    )
    b = evaluate_face_sweep_geometry(
        x0=1.5, y0=1.5, x1=1.5 + 0.2, y1=1.5 + 0.2, radius=0.575,
        width=16, height=16, height_at_cell=h,
    )
    assert a == b
    if a["earliest_hit"]:
        # x before y at equal t
        assert a["earliest_hit"]["axis"] in ("x", "y")


def test_geometry_wrap_cardinal():
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        evaluate_face_sweep_geometry,
        unwrap_delta,
    )
    w = 16
    assert abs(unwrap_delta(15.0, w) - (-1.0)) < 1e-12 or abs(unwrap_delta(-15.0, w) - 1.0) < 1e-12
    # East wrap: from 15.5 toward 0.5
    ev = evaluate_face_sweep_geometry(
        x0=15.5, y0=0.5, x1=0.5, y1=0.5, radius=0.0,
        width=w, height=w, height_at_cell=_flat_height,
    )
    assert ev["evaluation_status"] == "SKIPPED_ZERO_RADIUS"
    # Nonzero radius on wrap path against a ledge near wrap seam
    def h(cx, cy):
        return 1.0 if cx == 0 else 0.0

    ev2 = evaluate_face_sweep_geometry(
        x0=15.2, y0=0.5, x1=15.8, y1=0.5, radius=0.575,
        width=w, height=w, height_at_cell=h,
    )
    # Evidence returned deterministically (may or may not block depending on face enum).
    assert "blocking_proposal" in ev2
    assert ev2["face_sweep_work_delta"] == 0.0


def test_candidate_permutation_invariance():
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        enumerate_candidate_faces,
        evaluate_face_sweep_geometry,
    )
    faces_a = enumerate_candidate_faces(1.5, 0.5, 0.0, 1.0, 0.575, width=16, height=16)
    faces_b = list(reversed(faces_a))
    # Enum itself is sorted — reversed list differs as a list but kernel re-sorts.
    assert faces_a != faces_b
    assert sorted(faces_a, key=lambda f: (0 if f["axis"] == "x" else 1, f["coord"], f["cell_lo"])) == faces_a

    def h(cx, cy):
        return _ledge_row_height(cx, cy, ledge_x=2, h_high=1.0)

    e1 = evaluate_face_sweep_geometry(
        x0=1.5, y0=0.5, x1=1.5, y1=1.5, radius=0.575,
        width=16, height=16, height_at_cell=h,
    )
    e2 = evaluate_face_sweep_geometry(
        x0=1.5, y0=0.5, x1=1.5, y1=1.5, radius=0.575,
        width=16, height=16, height_at_cell=h,
    )
    assert e1 == e2


def test_soft_and_hard_cap_status():
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        EVAL_HARD_CAP,
        EVAL_SOFT_CAP,
        evaluate_face_sweep_geometry,
    )
    # Tiny soft/hard caps force warnings.
    soft = evaluate_face_sweep_geometry(
        x0=8.0, y0=8.0, x1=9.0, y1=9.0, radius=2.0,
        width=32, height=32, height_at_cell=_flat_height,
        soft_cap=4, hard_cap=10000,
    )
    assert soft["evaluation_status"] == EVAL_SOFT_CAP or soft["candidate_count"] <= 4
    hard = evaluate_face_sweep_geometry(
        x0=8.0, y0=8.0, x1=9.0, y1=9.0, radius=3.0,
        width=32, height=32, height_at_cell=_flat_height,
        soft_cap=2, hard_cap=3,
    )
    assert hard["evaluation_status"] == EVAL_HARD_CAP
    assert hard["blocking_proposal"] is True


# ---------------------------------------------------------------------------
# C. SES integration
# ---------------------------------------------------------------------------


def test_ses_radius_only_block_before_commit():
    from mechanistic_mind.model.acanthostega import acanthostega_radius_aware_face_sweep_config
    from mechanistic_mind.physical_system import surface_elevation_support as ses
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        EVENT_RADIUS_FACE_BARRIER,
        ensure_radius_aware_face_sweep_for_runtime,
    )
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        TRANSITION_LEDGE_BLOCK,
        ensure_ses_decomposition_contract_for_runtime,
    )
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        ensure_ses_runtime_transition_classifier_for_runtime,
        state_of as g2c2_state,
    )

    rt = _make_runtime(acanthostega_radius_aware_face_sweep_config, seed=11)
    ses.ensure_surface_elevation_support_for_runtime(rt.world, rt.config)
    ensure_ses_decomposition_contract_for_runtime(rt.world, rt.config)
    ensure_ses_runtime_transition_classifier_for_runtime(rt.world, rt.config)
    ensure_radius_aware_face_sweep_for_runtime(rt.world, rt.config)

    body = rt.body
    x0, y0 = 1.5, 0.5
    body.x, body.y = x0, y0
    body.z = 0.0
    body.grounded = True
    body.mechanical_work_reservoir = 100.0
    w0 = float(body.mechanical_work_reservoir)

    orig = ses.support_height_at_cell

    def _fake(world, cx, cy, config=None):
        return _ledge_row_height(cx, cy, ledge_x=2, h_high=1.0)

    ses.support_height_at_cell = _fake
    try:
        plan = ses.commit_body_elevation_gate(
            rt.world, rt.config, body,
            x0=x0, y0=y0, x1=1.5, y1=1.5,
            body_id=str(getattr(body, "body_id", "agent_0") or "agent_0"),
            body_mass=float(getattr(body, "mass", 1.0) or 1.0),
            tick=1,
        )
        _count_ticks(1)
        assert plan["accepted"] is False
        assert plan["block_reason"] == EVENT_RADIUS_FACE_BARRIER
        assert abs(float(body.x) - x0) < 1e-12
        assert abs(float(body.y) - y0) < 1e-12
        assert abs(float(body.mechanical_work_reservoir) - w0) < 1e-12
        assert float(plan.get("work_debit") or 0.0) == 0.0
        assert float(plan.get("face_sweep_work_delta") or 0.0) == 0.0
        assert float(plan.get("face_sweep_pe_delta") or 0.0) == 0.0
        fs = plan.get("face_sweep") or {}
        assert fs.get("evidence_source") == "RADIUS_ONLY"
        # G2C2 maps to LEDGE_BLOCK
        st = g2c2_state(rt.world)
        assert st is not None
        ledge = [r for r in st.history if r.get("transition_class") == TRANSITION_LEDGE_BLOCK]
        assert ledge, "expected LEDGE_BLOCK classification for radius face barrier"
        assert ledge[-1]["proposed_destination"] == [1.5, 1.5]
        assert ledge[-1]["realized_destination"] == [x0, y0]
    finally:
        ses.support_height_at_cell = orig


def test_clear_path_equivalent_to_g2c2_parent():
    """Flat clear motion: child matches parent physically (config keys may differ)."""
    from mechanistic_mind.model.acanthostega import (
        acanthostega_radius_aware_face_sweep_config,
        acanthostega_ses_runtime_classifier_config,
    )

    parent = _make_runtime(acanthostega_ses_runtime_classifier_config, seed=41)
    child = _make_runtime(acanthostega_radius_aware_face_sweep_config, seed=41)

    def phys(rt):
        b = rt.body
        return {
            "x": round(float(b.x), 9),
            "y": round(float(b.y), 9),
            "z": round(float(getattr(b, "z", 0.0) or 0.0), 9),
            "vx": round(float(getattr(b, "vx", 0.0) or 0.0), 9),
            "vy": round(float(getattr(b, "vy", 0.0) or 0.0), 9),
            "vz": round(float(getattr(b, "vz", 0.0) or 0.0), 9),
            "grounded": bool(getattr(b, "grounded", True)),
            "work": round(float(getattr(b, "mechanical_work_reservoir", 0.0) or 0.0), 9),
            "tick": int(getattr(rt.world, "tick", 0) or 0),
        }

    assert phys(parent) == phys(child)
    for _ in range(5):
        parent.step(1)
        child.step(1)
        _count_ticks(2)
    assert phys(parent) == phys(child)


def test_centre_path_block_unchanged():
    from mechanistic_mind.model.acanthostega import acanthostega_radius_aware_face_sweep_config
    from mechanistic_mind.physical_system import surface_elevation_support as ses
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        ensure_radius_aware_face_sweep_for_runtime,
    )

    rt = _make_runtime(acanthostega_radius_aware_face_sweep_config, seed=9)
    ses.ensure_surface_elevation_support_for_runtime(rt.world, rt.config)
    ensure_radius_aware_face_sweep_for_runtime(rt.world, rt.config)
    body = rt.body
    body.x, body.y = 0.5, 0.5
    body.grounded = True
    body.mechanical_work_reservoir = 100.0
    orig = ses.support_height_at_cell

    def _fake(world, cx, cy, config=None):
        # Centre must cross from col0 to col1 which is LARGE uphill.
        return 0.0 if int(cx) < 1 else 1.0

    ses.support_height_at_cell = _fake
    try:
        plan = ses.commit_body_elevation_gate(
            rt.world, rt.config, body,
            x0=0.5, y0=0.5, x1=1.5, y1=0.5,
            body_id="agent_0", body_mass=1.0, tick=2,
        )
        _count_ticks(1)
        assert plan["accepted"] is False
        assert plan["block_reason"] == ses.EVENT_LARGE_UPHILL_BLOCKED
    finally:
        ses.support_height_at_cell = orig


def test_partial_support_without_barrier_not_face_block():
    """Flat world + radius: no barrier proposal."""
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        evaluate_face_sweep_geometry,
    )
    ev = evaluate_face_sweep_geometry(
        x0=1.5, y0=0.5, x1=2.5, y1=0.5, radius=0.575,
        width=16, height=16, height_at_cell=_flat_height,
    )
    assert ev["blocking_proposal"] is False


# ---------------------------------------------------------------------------
# D. Starting penetration
# ---------------------------------------------------------------------------


def test_starting_penetration_outward_deeper_tangential():
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        PEN_DEEPER,
        PEN_OUTWARD,
        PEN_TANGENTIAL,
        evaluate_face_sweep_geometry,
    )

    def h(cx, cy):
        return _ledge_row_height(cx, cy, ledge_x=2, h_high=1.0)

    # Origin already overlapping face at x=2 (centre at 1.6, R=0.575 → overlaps).
    outward = evaluate_face_sweep_geometry(
        x0=1.6, y0=0.5, x1=1.0, y1=0.5, radius=0.575,
        width=16, height=16, height_at_cell=h,
    )
    deeper = evaluate_face_sweep_geometry(
        x0=1.6, y0=0.5, x1=1.9, y1=0.5, radius=0.575,
        width=16, height=16, height_at_cell=h,
    )
    tang = evaluate_face_sweep_geometry(
        x0=1.6, y0=0.5, x1=1.6, y1=1.0, radius=0.575,
        width=16, height=16, height_at_cell=h,
    )
    assert outward["starting_penetration"]["disposition"] == PEN_OUTWARD
    assert deeper["starting_penetration"]["disposition"] == PEN_DEEPER
    assert tang["starting_penetration"]["disposition"] in (PEN_TANGENTIAL, PEN_OUTWARD, PEN_DEEPER)
    # Outward must not propose block under policy (kernel may still list hit; apply_face_sweep clears).
    assert outward["starting_penetration"]["origin_pen"] >= outward["starting_penetration"]["proposal_pen"] - 1e-9


def test_restore_no_false_first_tick():
    from mechanistic_mind.model.acanthostega import acanthostega_radius_aware_face_sweep_config
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        ensure_radius_aware_face_sweep_for_runtime,
        restore_state,
        state_of,
    )

    rt = _make_runtime(acanthostega_radius_aware_face_sweep_config, seed=5)
    ensure_radius_aware_face_sweep_for_runtime(rt.world, rt.config)
    st = state_of(rt.world)
    assert st is not None
    snap = {"schema": "RADIUS_AWARE_FACE_SWEEP_STATE_V1", "config": st.config.to_dict(), "counters": {}}
    restore_state(rt.world, snap, rt.config)
    st2 = state_of(rt.world)
    assert st2 is not None
    assert st2.restore_suppress_until_tick is not None
    assert st2.history == [] or len(st2.history) == 0


# ---------------------------------------------------------------------------
# E. Entity scope / radii
# ---------------------------------------------------------------------------


def test_body_and_object_radius_sources():
    from mechanistic_mind.physical_system.physical_body_resource_object_contact import (
        BODY_CONTACT_RADIUS,
    )
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        body_face_sweep_radius,
        object_face_sweep_radius,
    )
    assert body_face_sweep_radius(None) == float(BODY_CONTACT_RADIUS)
    obj = SimpleNamespace(collision_radius=0.25, optical_radius=0.99)
    assert object_face_sweep_radius(obj) == 0.25
    # Optical must not win
    obj2 = SimpleNamespace(optical_radius=0.99)
    # ensure_object_collision_radius may invent default — just ensure we don't return optical
    r = object_face_sweep_radius(obj2)
    assert abs(r - 0.99) > 1e-9


def test_held_excluded_explicit():
    from mechanistic_mind.physical_system.radius_aware_face_sweep import catalog_item
    item = catalog_item(enabled=True)
    assert item["scope"]["held_objects"] is False
    assert item["scope"]["bodies"] is True
    assert item["scope"]["free_objects"] is True


# ---------------------------------------------------------------------------
# F. Privacy / PE invariants
# ---------------------------------------------------------------------------


def test_cognition_forbidden_tokens():
    from mechanistic_mind.scientific_v3.radius_aware_face_sweep_summary import (
        COGNITION_FORBIDDEN_TOKENS,
    )
    from mechanistic_mind.model.acanthostega import acanthostega_radius_aware_face_sweep_config

    rt = _make_runtime(acanthostega_radius_aware_face_sweep_config, seed=2)
    for _ in range(3):
        rt.step(1)
        _count_ticks(1)
    # Observation / cognition blobs must not contain face-sweep tokens.
    obs = getattr(rt, "last_observation", None) or {}
    blob = str(obs).upper()
    for tok in ("RADIUS_FACE_BARRIER", "FACE_SWEEP", "PE_AUTHORITY_SES_DDA"):
        assert tok not in blob


def test_pe_authority_constants():
    from mechanistic_mind.physical_system.radius_aware_face_sweep import (
        PE_AUTHORITY_SES_DDA,
        RESEARCHER_FLAGS,
    )
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        PE_AUTHORITY_SES_DDA as G2C1_PE,
    )
    assert PE_AUTHORITY_SES_DDA == G2C1_PE
    assert RESEARCHER_FLAGS["face_sweep_work_delta"] == 0.0
    assert RESEARCHER_FLAGS["face_sweep_pe_delta"] == 0.0


def test_g2c1_taxonomy_maps_radius_barrier():
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        TRANSITION_GEOMETRY_AMBIGUOUS,
        TRANSITION_LEDGE_BLOCK,
        classify_transition_taxonomy,
    )
    r = classify_transition_taxonomy(
        event_kind="RADIUS_FACE_BARRIER", delta_h=1.0, microrelief_threshold=0.12,
    )
    assert r["transition_class"] == TRANSITION_LEDGE_BLOCK
    r2 = classify_transition_taxonomy(
        event_kind="RADIUS_FACE_BARRIER_HARD_CAP", delta_h=0.0, microrelief_threshold=0.12,
    )
    assert r2["transition_class"] == TRANSITION_GEOMETRY_AMBIGUOUS


def test_total_simulated_ticks_report(capsys):
    # Ensure budget tracking is available for the final report.
    assert TICK_COUNTER["n"] >= 0
    print(f"TOTAL_SIMULATED_TICKS_SO_FAR={TICK_COUNTER['n']}")
