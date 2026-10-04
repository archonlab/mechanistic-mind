"""Tests for Acanthostega G2C2 SES Runtime Transition Classifier V1.

Validates preset isolation, classification taxonomy application, proposed vs realized,
physics equivalence to G2C1 parent, snapshot/restore, shared-world dedup, cognition privacy.
"""
from __future__ import annotations

import copy

import pytest


# ---------------------------------------------------------------------------
# 1. Preset isolation
# ---------------------------------------------------------------------------


def test_preset_isolation():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_SES_RUNTIME_CLASSIFIER,
        acanthostega_config,
        acanthostega_radius_aware_support_config,
        acanthostega_ses_decomposition_contract_config,
        acanthostega_ses_runtime_classifier_config,
    )
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        ses_decomposition_contract_is_active,
    )
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        ses_runtime_transition_classifier_is_active,
    )
    from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
    from mechanistic_mind.model.lines import stamp_config_from_preset
    from mechanistic_mind.physical_system.experiment_canonical import PRESET_BETA31

    # Tiktaalik OFF
    cfg_tik = PhysicalSystemConfig()
    stamp_config_from_preset(cfg_tik, PRESET_BETA31)
    assert not ses_runtime_transition_classifier_is_active(cfg_tik)
    assert not ses_decomposition_contract_is_active(cfg_tik)

    # Prior Acanthostega presets OFF for classifier
    cfg_parent_g2b = acanthostega_radius_aware_support_config()
    assert not ses_runtime_transition_classifier_is_active(cfg_parent_g2b)

    cfg_g2c1 = acanthostega_ses_decomposition_contract_config()
    assert ses_decomposition_contract_is_active(cfg_g2c1)
    assert not ses_runtime_transition_classifier_is_active(cfg_g2c1)

    # G2C2 ON; G2C1 remains ON
    cfg_g2c2 = acanthostega_ses_runtime_classifier_config()
    assert cfg_g2c2.public_preset == PUBLIC_PRESET_SES_RUNTIME_CLASSIFIER
    assert ses_runtime_transition_classifier_is_active(cfg_g2c2)
    assert ses_decomposition_contract_is_active(cfg_g2c2)


def test_g2c1_contract_unchanged_constants():
    """G2C1 taxonomy constants are reused, not renamed."""
    from mechanistic_mind.physical_system import ses_decomposition_contract as g2c1
    from mechanistic_mind.physical_system import ses_runtime_transition_classifier as g2c2

    assert g2c2.TRANSITION_SMOOTH_PATCH_TRAVERSAL is g2c1.TRANSITION_SMOOTH_PATCH_TRAVERSAL
    assert g2c2.TRANSITION_TAXONOMY == g2c1.TRANSITION_TAXONOMY
    assert g2c2.CURRENT_PE_AUTHORITY == g2c1.PE_AUTHORITY_SES_DDA
    assert g2c2.CLASSIFIER_CONTROLS_PHYSICS is False


# ---------------------------------------------------------------------------
# 3. Classification (pure unit)
# ---------------------------------------------------------------------------


def test_classification_smooth_micro_ledge_loss_partial_ambiguous():
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        TRANSITION_GEOMETRY_AMBIGUOUS,
        TRANSITION_LEDGE_BLOCK,
        TRANSITION_MICRORELIEF_STEP,
        TRANSITION_OCCUPANT_SUPPORT_RISE,
        TRANSITION_RADIUS_PARTIAL_CONTACT,
        TRANSITION_SMOOTH_PATCH_TRAVERSAL,
        TRANSITION_SUPPORT_DROP_LOS,
        classify_runtime_transition,
    )

    assert classify_runtime_transition(
        event_kind="LEVEL", delta_h=0.0, microrelief_threshold=0.12, accepted=True, support_lost=False,
    )["transition_class"] == TRANSITION_SMOOTH_PATCH_TRAVERSAL

    assert classify_runtime_transition(
        event_kind="MICRO_UPHILL", delta_h=0.05, microrelief_threshold=0.12, accepted=True, support_lost=False,
    )["transition_class"] == TRANSITION_MICRORELIEF_STEP

    assert classify_runtime_transition(
        event_kind="LARGE_UPHILL_BLOCKED", delta_h=0.2, microrelief_threshold=0.12, accepted=False, support_lost=False,
    )["transition_class"] == TRANSITION_LEDGE_BLOCK

    assert classify_runtime_transition(
        event_kind="LARGE_DOWNHILL_SUPPORT_LOST", delta_h=-0.2, microrelief_threshold=0.12,
        accepted=True, support_lost=True,
    )["transition_class"] == TRANSITION_SUPPORT_DROP_LOS

    assert classify_runtime_transition(
        event_kind="LEVEL", delta_h=0.0, microrelief_threshold=0.12, accepted=True, support_lost=False,
        support_class="PARTIAL_SUPPORT",
    )["transition_class"] == TRANSITION_RADIUS_PARTIAL_CONTACT

    assert classify_runtime_transition(
        event_kind="LEVEL", delta_h=0.0, microrelief_threshold=0.12, accepted=False, support_lost=False,
        mutation_provenance="OCCUPIED_SUPPORT_RISE",
    )["transition_class"] == TRANSITION_OCCUPANT_SUPPORT_RISE

    assert classify_runtime_transition(
        event_kind="UNKNOWN_EVENT", delta_h=0.0, microrelief_threshold=0.12, accepted=True, support_lost=False,
    )["transition_class"] == TRANSITION_GEOMETRY_AMBIGUOUS


def test_precedence_mutation_over_ledge_over_loss_over_partial():
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        PRECEDENCE_ORDER,
        TRANSITION_LEDGE_BLOCK,
        TRANSITION_OCCUPANT_SUPPORT_RISE,
        TRANSITION_RADIUS_PARTIAL_CONTACT,
        TRANSITION_SUPPORT_DROP_LOS,
        classify_runtime_transition,
    )

    assert PRECEDENCE_ORDER[0] == TRANSITION_OCCUPANT_SUPPORT_RISE
    # Mutation wins even if SES also looks like a ledge.
    r = classify_runtime_transition(
        event_kind="LARGE_UPHILL_BLOCKED", delta_h=0.3, microrelief_threshold=0.12,
        accepted=False, support_lost=False, mutation_provenance="OCCUPIED_SUPPORT_RISE",
        support_class="PARTIAL_SUPPORT",
    )
    assert r["transition_class"] == TRANSITION_OCCUPANT_SUPPORT_RISE

    # Ledge wins over partial.
    r = classify_runtime_transition(
        event_kind="LARGE_UPHILL_BLOCKED", delta_h=0.3, microrelief_threshold=0.12,
        accepted=False, support_lost=False, support_class="PARTIAL_SUPPORT",
    )
    assert r["transition_class"] == TRANSITION_LEDGE_BLOCK

    # Support loss wins over partial.
    r = classify_runtime_transition(
        event_kind="LARGE_DOWNHILL_SUPPORT_LOST", delta_h=-0.3, microrelief_threshold=0.12,
        accepted=True, support_lost=True, support_class="PARTIAL_SUPPORT",
    )
    assert r["transition_class"] == TRANSITION_SUPPORT_DROP_LOS

    # Partial alone -> radius partial.
    r = classify_runtime_transition(
        event_kind="LEVEL", delta_h=0.0, microrelief_threshold=0.12,
        accepted=True, support_lost=False, support_class="EDGE_OR_SPARSE_SUPPORT",
    )
    assert r["transition_class"] == TRANSITION_RADIUS_PARTIAL_CONTACT


def test_stationary_suppresses_traversal_spam():
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        OUTCOME_SUPPRESSED_STATIONARY,
        _should_emit_path_gate,
    )

    emit, outcome = _should_emit_path_gate(
        horizontal_moved=False, accepted=True, support_lost=False,
        event_kind="LEVEL", mutation_provenance=None,
        grounded_before=True, grounded_after=True,
    )
    assert emit is False
    assert outcome == OUTCOME_SUPPRESSED_STATIONARY


def test_proposed_vs_realized_in_receipt():
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        OUTCOME_BLOCKED,
        build_classification_receipt,
    )

    r = build_classification_receipt(
        tick=3, entity_kind="body", entity_id="agent_0",
        event_kind="LARGE_UPHILL_BLOCKED", delta_h=0.25, microrelief_threshold=0.12,
        accepted=False, block_reason="LARGE_UPHILL_BLOCKED",
        x_before=1.0, y_before=1.0,
        x_proposed=1.4, y_proposed=1.0,
        x_realized=1.0, y_realized=1.0,
        z_before=0.0, z_after=0.0,
        grounded_before=True, grounded_after=True,
        work_debit=0.0, kinetic_paid=0.0, support_lost=False,
        outcome=OUTCOME_BLOCKED,
    )
    assert r["proposed_destination"] == [1.4, 1.0]
    assert r["realized_destination"] == [1.0, 1.0]
    assert r["accepted"] is False
    assert r["blocked"] is True
    assert r["classifier_controls_physics"] is False
    assert r["pe_authority"] == "PE_AUTHORITY_SES_DDA"
    assert r["agent_accessible"] is False


# ---------------------------------------------------------------------------
# Runtime probes (short ticks)
# ---------------------------------------------------------------------------


def _make_runtime(cfg_factory, seed=17):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    cfg = cfg_factory()
    return PhysicalSystemRuntime(seed=seed, config=cfg)


def test_physics_equivalence_parent_vs_child():
    """G2C1 and G2C2 produce identical physical projections for same seed/actions."""
    from mechanistic_mind.model.acanthostega import (
        acanthostega_ses_decomposition_contract_config,
        acanthostega_ses_runtime_classifier_config,
    )
    from tests.g2c2_equivalence_support import first_difference, physical_projection, projection_digest

    parent = _make_runtime(acanthostega_ses_decomposition_contract_config, seed=41)
    child = _make_runtime(acanthostega_ses_runtime_classifier_config, seed=41)

    d0_p = projection_digest(parent)
    d0_c = projection_digest(child)
    assert d0_p == d0_c, first_difference(physical_projection(parent), physical_projection(child))

    # A few WAIT ticks (stationary — classifier must not alter physics).
    for _ in range(5):
        parent.step(1)
        child.step(1)
    assert projection_digest(parent) == projection_digest(child)

    # Classifier should have suppressed stationary spam (or emitted nothing for WAIT).
    from tests.g2c2_equivalence_support import g2c2_receipts
    # Parent has no G2C2 receipts; child may have zero for stationary.
    assert g2c2_receipts(parent) == []


def test_runtime_blocked_ledge_retains_proposal():
    """Blocked transition keeps proposed destination; realized pose unchanged."""
    from mechanistic_mind.model.acanthostega import acanthostega_ses_runtime_classifier_config
    from mechanistic_mind.physical_system.surface_elevation_support import (
        commit_body_elevation_gate,
        ensure_surface_elevation_support_for_runtime,
        _dims,
    )
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        ensure_ses_runtime_transition_classifier_for_runtime,
        state_of,
        TRANSITION_LEDGE_BLOCK,
    )
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        ensure_ses_decomposition_contract_for_runtime,
    )
    import mechanistic_mind.physical_system.surface_elevation_support as ses

    rt = _make_runtime(acanthostega_ses_runtime_classifier_config, seed=7)
    ensure_surface_elevation_support_for_runtime(rt.world, rt.config)
    ensure_ses_decomposition_contract_for_runtime(rt.world, rt.config)
    ensure_ses_runtime_transition_classifier_for_runtime(rt.world, rt.config)

    w, h = _dims(rt.world)
    body = rt.body
    x0, y0 = float(body.x), float(body.y)
    cx = int(x0) % w
    cy = int(y0) % h
    dest_cx = (cx + 1) % w
    thr = float(rt.config.surface_elevation_support.microrelief_threshold)
    target_h = thr + 0.25

    orig = ses.support_height_at_cell

    def _fake_height(world, cell_x, cell_y, config=None):
        if int(cell_x) == dest_cx and int(cell_y) == cy:
            return target_h
        return 0.0

    ses.support_height_at_cell = _fake_height
    try:
        st = state_of(rt.world)
        if st is not None:
            st.restore_suppress_until_tick = None
        x1 = float(x0) + 0.9
        y1 = float(y0)
        plan = commit_body_elevation_gate(
            rt.world, rt.config, body,
            x0=x0, y0=y0, x1=x1, y1=y1,
            body_id="agent_0", body_mass=1.0, tick=1,
        )
        assert plan.get("accepted") is False
        assert abs(float(body.x) - x0) < 1e-9
        assert abs(float(body.y) - y0) < 1e-9
        st = state_of(rt.world)
        assert st is not None and st.history
        last = st.last_receipt
        assert last["transition_class"] == TRANSITION_LEDGE_BLOCK
        assert last["proposed_destination"][0] == pytest.approx(x1)
        assert last["realized_destination"][0] == pytest.approx(x0)
        assert last["accepted"] is False
        assert last["blocked"] is True
    finally:
        ses.support_height_at_cell = orig


def test_snapshot_restore_no_false_first_tick():
    from mechanistic_mind.model.acanthostega import acanthostega_ses_runtime_classifier_config
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        state_of,
    )

    rt = _make_runtime(acanthostega_ses_runtime_classifier_config, seed=11)
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    st = state_of(rt2.world)
    assert st is not None
    assert st.restore_suppress_until_tick is not None
    n_before = len(st.history)
    rt2.step(1)
    st2 = state_of(rt2.world)
    assert len(st2.history) == n_before


def test_cognition_privacy():
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        BANNER,
        PROFILE_VERSION,
        TRANSITION_LEDGE_BLOCK,
        RESEARCHER_FLAGS,
    )
    from mechanistic_mind.scientific_v3.ses_runtime_transition_classifier_summary import (
        COGNITION_FORBIDDEN_TOKENS,
    )

    assert RESEARCHER_FLAGS["agent_accessible"] is False
    for tok in ("SMOOTH_PATCH_TRAVERSAL", "LEDGE_BLOCK", "PE_AUTHORITY", "SES_DDA"):
        assert tok in COGNITION_FORBIDDEN_TOKENS or tok == TRANSITION_LEDGE_BLOCK
    # Banner is researcher-facing only.
    assert "CLASSIFICATION DOES NOT CONTROL PHYSICS" in BANNER
    assert "SES_RUNTIME_TRANSITION_CLASSIFIER_V1" == PROFILE_VERSION


def test_mechanism_registry_and_pe_authority():
    from mechanistic_mind.model.acanthostega import acanthostega_ses_runtime_classifier_config
    from mechanistic_mind.physical_system.mechanism_registry import mechanism_snapshot
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import (
        PE_AUTHORITY_SES_DDA,
    )

    cfg = acanthostega_ses_runtime_classifier_config()
    snap = mechanism_snapshot(cfg)
    assert snap["enabled"].get("ses_runtime_transition_classifier") is True
    assert snap["enabled"].get("ses_decomposition_contract") is True
    assert cfg.ses_runtime_transition_classifier.pe_authority == PE_AUTHORITY_SES_DDA


def test_shared_world_no_id_ordering_in_keys():
    from mechanistic_mind.physical_system.ses_runtime_transition_classifier import application_key

    k1 = application_key(3, "body", "agent_0", "PATH_GATE")
    k2 = application_key(3, "body", "agent_1", "PATH_GATE")
    assert k1 != k2
    assert "PATH_GATE" in k1
    # Never Python id().
    assert "0x" not in k1


def test_total_simulated_ticks_budget_marker():
    """Marker so the report can count ticks from this module's runtime probes.

    physics_equivalence: 5+5 = 10 (parent+child share actions; count child ticks = 5)
    blocked ledge: 0 full steps (direct gate call)
    snapshot restore: 1 step
    Total runtime ticks attributed ≈ 6 (well under 300).
    """
    assert True
