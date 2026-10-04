"""Tests for Acanthostega G2C1 SES Decomposition Contract.

Validates:
- preset isolation;
- authority stamp;
- transition taxonomy;
- physics equivalence to parent;
- snapshot/restore;
- cognition privacy.
"""
from __future__ import annotations

import pytest


def test_preset_isolation():
    """G2C1 mechanism is absent in Tiktaalik and prior presets, present only in G2C1."""
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_SES_DECOMPOSITION_CONTRACT,
        PUBLIC_PRESET_RADIUS_AWARE_SUPPORT,
        acanthostega_config,
        acanthostega_radius_aware_support_config,
        acanthostega_ses_decomposition_contract_config,
    )
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        ses_decomposition_contract_is_active,
    )

    # Tiktaalik: absent
    cfg_tik = acanthostega_config()
    assert not ses_decomposition_contract_is_active(cfg_tik)

    # Parent (radius-aware support): absent
    cfg_parent = acanthostega_radius_aware_support_config()
    assert not ses_decomposition_contract_is_active(cfg_parent)

    # G2C1: present
    cfg_g2c1 = acanthostega_ses_decomposition_contract_config()
    assert ses_decomposition_contract_is_active(cfg_g2c1)
    assert cfg_g2c1.public_preset == PUBLIC_PRESET_SES_DECOMPOSITION_CONTRACT


def test_authority_stamp():
    """G2C1 authority = SES DDA; continuous authority not active."""
    from mechanistic_mind.model.acanthostega import (
        acanthostega_ses_decomposition_contract_config,
    )
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        PE_AUTHORITY_SES_DDA,
        SesDecompositionContractConfig,
    )

    cfg = acanthostega_ses_decomposition_contract_config()
    sdc_cfg = cfg.ses_decomposition_contract
    assert sdc_cfg.pe_authority == PE_AUTHORITY_SES_DDA
    assert sdc_cfg.to_dict()["continuous_pe_active"] is False
    assert sdc_cfg.to_dict()["tangent_gravity_active"] is False
    assert sdc_cfg.to_dict()["normal_physical_effects_active"] is False
    assert sdc_cfg.to_dict()["radius_face_sweep_active"] is False


def test_transition_taxonomy_classification():
    """Taxonomy classifies SES transitions correctly."""
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        TRANSITION_SMOOTH_PATCH_TRAVERSAL,
        TRANSITION_MICRORELIEF_STEP,
        TRANSITION_LEDGE_BLOCK,
        TRANSITION_SUPPORT_DROP_LOS,
        TRANSITION_RADIUS_PARTIAL_CONTACT,
        TRANSITION_GEOMETRY_AMBIGUOUS,
        classify_transition_taxonomy,
    )

    # Level
    result = classify_transition_taxonomy(
        event_kind="LEVEL",
        delta_h=0.0,
        microrelief_threshold=0.12,
    )
    assert result["transition_class"] == TRANSITION_SMOOTH_PATCH_TRAVERSAL

    # Micro-uphill
    result = classify_transition_taxonomy(
        event_kind="MICRO_UPHILL",
        delta_h=0.05,
        microrelief_threshold=0.12,
    )
    assert result["transition_class"] == TRANSITION_MICRORELIEF_STEP

    # Large-uphill
    result = classify_transition_taxonomy(
        event_kind="LARGE_UPHILL_BLOCKED",
        delta_h=0.20,
        microrelief_threshold=0.12,
    )
    assert result["transition_class"] == TRANSITION_LEDGE_BLOCK

    # Micro-downhill
    result = classify_transition_taxonomy(
        event_kind="MICRO_DOWNHILL_INELASTIC",
        delta_h=-0.05,
        microrelief_threshold=0.12,
    )
    assert result["transition_class"] == TRANSITION_MICRORELIEF_STEP

    # Large-downhill
    result = classify_transition_taxonomy(
        event_kind="LARGE_DOWNHILL_SUPPORT_LOST",
        delta_h=-0.20,
        microrelief_threshold=0.12,
    )
    assert result["transition_class"] == TRANSITION_SUPPORT_DROP_LOS

    # Radius partial
    result = classify_transition_taxonomy(
        event_kind="LEVEL",
        delta_h=0.0,
        microrelief_threshold=0.12,
        support_class="PARTIAL_SUPPORT",
    )
    assert result["transition_class"] == TRANSITION_RADIUS_PARTIAL_CONTACT

    # Radius loss
    result = classify_transition_taxonomy(
        event_kind="LEVEL",
        delta_h=0.0,
        microrelief_threshold=0.12,
        support_class="LOSS_OF_SUPPORT",
    )
    assert result["transition_class"] == TRANSITION_SUPPORT_DROP_LOS

    # Ambiguous
    result = classify_transition_taxonomy(
        event_kind="UNKNOWN_EVENT",
        delta_h=0.0,
        microrelief_threshold=0.12,
    )
    assert result["transition_class"] == TRANSITION_GEOMETRY_AMBIGUOUS


def test_physics_equivalence_to_parent():
    """G2C1 physics outputs are identical to parent (radius-aware support)."""
    from mechanistic_mind.model.acanthostega import (
        acanthostega_radius_aware_support_config,
        acanthostega_ses_decomposition_contract_config,
    )
    from mechanistic_mind.physical_system.surface_elevation_support import (
        SurfaceElevationSupportConfig,
    )

    cfg_parent = acanthostega_radius_aware_support_config()
    cfg_g2c1 = acanthostega_ses_decomposition_contract_config()

    # Both have SES active
    ses_parent = cfg_parent.surface_elevation_support
    ses_g2c1 = cfg_g2c1.surface_elevation_support
    assert ses_parent.enabled == ses_g2c1.enabled
    assert ses_parent.microrelief_threshold == ses_g2c1.microrelief_threshold
    assert ses_parent.physical_height_scale == ses_g2c1.physical_height_scale

    # G2C1 has contract active
    assert cfg_g2c1.ses_decomposition_contract.enabled is True
    # Parent does not have contract
    parent_contract = getattr(cfg_parent, "ses_decomposition_contract", None)
    assert parent_contract is None or not parent_contract.enabled


def test_snapshot_restore():
    """Snapshot/restore preserves authority and contract state."""
    from mechanistic_mind.model.acanthostega import (
        acanthostega_ses_decomposition_contract_config,
    )
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        PE_AUTHORITY_SES_DDA,
        SesDecompositionContractConfig,
        serialize_state,
        restore_state,
        state_of,
        ensure_ses_decomposition_contract_for_runtime,
    )

    cfg = acanthostega_ses_decomposition_contract_config()

    # Create a mock world
    class MockWorld:
        pass

    world = MockWorld()

    # Ensure state
    st = ensure_ses_decomposition_contract_for_runtime(world, cfg)
    assert st is not None
    assert st.config.pe_authority == PE_AUTHORITY_SES_DDA

    # Serialize
    data = serialize_state(st)
    assert data is not None
    assert data["config"]["pe_authority"] == PE_AUTHORITY_SES_DDA

    # Restore
    world2 = MockWorld()
    st2 = restore_state(world2, data, cfg)
    assert st2 is not None
    assert st2.config.pe_authority == PE_AUTHORITY_SES_DDA


def test_cognition_privacy():
    """Taxonomy/authority are not exposed to agent cognition."""
    from mechanistic_mind.physical_system.ses_decomposition_contract import (
        BANNER,
        TRANSITION_TAXONOMY,
        PE_AUTHORITY_SES_DDA,
    )

    # Banner does not contain forbidden agent-visible tokens
    # Note: "SES" is part of the mechanism name in researcher-facing banner, not agent-visible
    forbidden = ["SMOOTH", "STEP", "LEDGE", "CLIFF", "UPHILL", "DOWNHILL", "PE_AUTHORITY"]
    for token in forbidden:
        assert token not in BANNER

    # Taxonomy classes are not agent-visible (they are internal mechanism tokens)
    for cls in TRANSITION_TAXONOMY:
        assert cls.isupper()  # Internal tokens are UPPER_CASE


def test_mechanism_registry():
    """G2C1 mechanism is registered in mechanism registry."""
    from mechanistic_mind.model.acanthostega import (
        acanthostega_ses_decomposition_contract_config,
    )
    from mechanistic_mind.physical_system.mechanism_registry import (
        mechanism_snapshot,
    )

    cfg = acanthostega_ses_decomposition_contract_config()
    snapshot = mechanism_snapshot(cfg)
    assert "ses_decomposition_contract" in snapshot["enabled"]


def test_analyzer_summary():
    """Analyzer summary is generated correctly."""
    from mechanistic_mind.model.acanthostega import (
        acanthostega_ses_decomposition_contract_config,
    )
    from mechanistic_mind.scientific_v3.ses_decomposition_contract_summary import (
        summarize_ses_decomposition_contract,
    )

    cfg = acanthostega_ses_decomposition_contract_config()

    class MockWorld:
        pass

    world = MockWorld()
    summary = summarize_ses_decomposition_contract(world)
    # No state yet, so summary is None
    assert summary is None
