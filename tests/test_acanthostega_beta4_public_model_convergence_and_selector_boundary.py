"""ACANTHOSTEGA_BETA4_PUBLIC_MODEL_CONVERGENCE_AND_SELECTOR_BOUNDARY_REPAIR_V1."""
from __future__ import annotations

from mechanistic_mind.model.acanthostega import (
    PUBLIC_PRESET_BETA4,
    PUBLIC_PRESET_VOLUMETRIC_WORLD_VW7,
    acanthostega_beta4_config,
    acanthostega_release_and_excavation_support_loss_integration_config,
    acanthostega_volumetric_world_vw7_config,
    model_metadata,
)
from mechanistic_mind.model.lines import identity_for_config, stamp_config_from_preset
from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
    REINTEGRATION_BLOCKER,
    effector_held_occupancy_exertion_bridge_is_active,
)
from mechanistic_mind.physical_system.experiment_canonical import (
    ACANTHOSTEGA_PUBLIC_PRESET_IDS,
    PRESET_ACANTHOSTEGA_BETA4,
    PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION,
    PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7,
    PRESET_TIKTAALIK_BETA31,
    PUBLIC_MODEL_PRESET_IDS,
    is_acanthostega_public_preset,
    is_public_model_selector_entry,
    normalize_preset_name,
    preset_canonical,
    public_model_selector_entries,
    visibility_class_for_preset,
)
from mechanistic_mind.physical_system.free_space_state_and_pe_authority_contract import (
    free_space_state_and_pe_authority_contract_is_active,
)
from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
    minimal_vision_3d_geometric_interface_is_active,
)
from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
    build_occupancy_volume_primitives,
    build_observer_volume_render_description,
    observer_camera_occupancy_consumer_is_active,
)
from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
    occupancy_support_and_contact_queries_is_active,
)
from mechanistic_mind.physical_system.release_and_excavation_support_loss_integration import (
    release_and_excavation_support_loss_integration_is_active,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime  # noqa: F401 — retained for shared-world probes
from mechanistic_mind.physical_system.vertical_impact_acoustic_emission import (
    vertical_impact_acoustic_emission_is_active,
)
from mechanistic_mind.physical_system.vertical_terrain_landing_contact_response import (
    vertical_terrain_landing_contact_response_is_active,
)
from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
    occupied_intervals_at,
    volumetric_world_material_occupancy_is_active,
)
from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
    volumetric_world_material_reintegration_is_active,
)
from mechanistic_mind.physical_system.volumetric_world_material_separation import (
    volumetric_world_material_separation_is_active,
)
from mechanistic_mind.ui.psy_observer_web.serialize import (
    _acanthostega_beta4_capability_payload,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession


TICKS = {"n": 0}


def _step(rt, n=1):
    for _ in range(n):
        rt.step()
        TICKS["n"] += 1


def _on(cfg, attr: str) -> bool:
    o = getattr(cfg, attr, None)
    return bool(getattr(o, "enabled", False)) if o is not None else False


# ---- PUBLIC BOUNDARY ----


def test_public_selector_exactly_two_entries():
    entries = public_model_selector_entries()
    assert len(entries) == 2
    assert entries[0]["public_preset"] == PRESET_TIKTAALIK_BETA31
    assert entries[0]["label"] == "Tiktaalik Beta 3.1"
    assert entries[1]["public_preset"] == PRESET_ACANTHOSTEGA_BETA4
    assert entries[1]["label"] == "Acanthostega Beta 4.0"
    assert PUBLIC_MODEL_PRESET_IDS == frozenset(
        {PRESET_TIKTAALIK_BETA31, PRESET_ACANTHOSTEGA_BETA4}
    )


def test_public_vs_development_classification():
    assert is_public_model_selector_entry(PRESET_TIKTAALIK_BETA31)
    assert is_public_model_selector_entry(PRESET_ACANTHOSTEGA_BETA4)
    assert not is_public_model_selector_entry(PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7)
    assert not is_public_model_selector_entry(
        PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
    )
    assert not is_public_model_selector_entry("CUSTOM")
    assert visibility_class_for_preset(PRESET_ACANTHOSTEGA_BETA4) == "PUBLIC_MODEL"
    assert (
        visibility_class_for_preset(PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7)
        == "DEVELOPMENT_FIXTURE"
    )


def test_vw7_fixture_still_resolvable():
    assert PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7 in ACANTHOSTEGA_PUBLIC_PRESET_IDS
    assert is_acanthostega_public_preset(PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7)
    assert (
        normalize_preset_name("ACANTHOSTEGA_BETA4_VOLUMETRIC_WORLD_VW7")
        == PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7)
    assert canon["builder"] == "acanthostega_volumetric_world_vw7_config"
    assert canon.get("visibility_class") == "DEVELOPMENT_FIXTURE"
    cfg = acanthostega_volumetric_world_vw7_config()
    assert cfg.public_preset == PUBLIC_PRESET_VOLUMETRIC_WORLD_VW7


# ---- BETA 4 IDENTITY / CUMULATIVE MATRIX ----


def test_beta4_builder_is_cumulative_v1d_plus_vw():
    cfg = acanthostega_beta4_config()
    assert cfg.public_preset == PUBLIC_PRESET_BETA4
    assert cfg.model_line == "ACANTHOSTEGA"
    # Free-Space V1A–V1D
    assert free_space_state_and_pe_authority_contract_is_active(cfg)
    assert vertical_terrain_landing_contact_response_is_active(cfg)
    assert vertical_impact_acoustic_emission_is_active(cfg)
    assert release_and_excavation_support_loss_integration_is_active(cfg)
    # VW1–VW6 + VW7 consumer
    assert volumetric_world_material_occupancy_is_active(cfg)
    assert occupancy_support_and_contact_queries_is_active(cfg)
    assert volumetric_world_material_separation_is_active(cfg)
    assert volumetric_world_material_reintegration_is_active(cfg)
    assert effector_held_occupancy_exertion_bridge_is_active(cfg)
    assert minimal_vision_3d_geometric_interface_is_active(cfg)
    assert observer_camera_occupancy_consumer_is_active(cfg)
    assert "NO_PHYSICAL_DEPOSITION_INTO_OCCUPANCY_EVENT" in REINTEGRATION_BLOCKER
    meta = model_metadata(cfg)
    assert meta["display_name"] == "MM 1.0 — Acanthostega Beta 4.0"
    assert meta["public_preset"] == PUBLIC_PRESET_BETA4
    assert meta["model_line"] == "ACANTHOSTEGA"
    ident = identity_for_config(cfg)
    assert ident["public_preset"] == PUBLIC_PRESET_BETA4
    assert "Acanthostega Beta 4.0" in str(ident.get("display_name") or "")
    canon = preset_canonical(PRESET_ACANTHOSTEGA_BETA4)
    assert canon["builder"] == "acanthostega_beta4_config"
    assert canon["parent"] == PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
    assert canon["visibility_class"] == "PUBLIC_MODEL"


def test_beta4_preserves_pre_vw_tip_flags():
    tip = acanthostega_release_and_excavation_support_loss_integration_config()
    b4 = acanthostega_beta4_config()
    for attr in (
        "free_space_state_and_pe_authority_contract",
        "vertical_terrain_landing_contact_response",
        "vertical_impact_acoustic_emission",
        "release_and_excavation_support_loss_integration",
        "flat_ground_gravity",
        "surface_elevation_support",
        "body_normal_load_traction",
        "continuous_surface_geometry",
        "conservative_surface_material_separation",
        "held_deposition_radius_shrink_transaction",
        "held_combine_radius_resize_transaction",
        "bnlt_move_breakaway_locomotion_repair",
        "active_locomotion_traction_vs_sliding_friction",
        "event_driven_crowded_placement_retry_contract",
        "detached_material_amount_scaled_collision_radius",
    ):
        if hasattr(tip, attr):
            assert _on(b4, attr) is True, attr


def test_apply_activates_beta4_identity_once():
    sess = ObserverSession()
    out = sess.apply_experiment(
        {
            "public_preset": PRESET_ACANTHOSTEGA_BETA4,
            "model_line": "TIKTAALIK",  # conflicting client line ignored
            "seed": 17,
            "agent_count": 1,
            "cognition_enabled": False,
            "load_preset": True,
        }
    )
    cfg = sess.runtime.config
    hdr = out.get("header") or {}
    banner = out.get("model_banner") or {}
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_BETA4
    assert cfg.model_line == "ACANTHOSTEGA"
    assert hdr.get("model_line") == "ACANTHOSTEGA" or banner.get("model_line") == "ACANTHOSTEGA"
    assert "Acanthostega Beta 4.0" in str(
        hdr.get("experiment") or banner.get("phase_label") or banner.get("display_name") or ""
    )
    assert volumetric_world_material_occupancy_is_active(cfg)
    assert free_space_state_and_pe_authority_contract_is_active(cfg)
    assert minimal_vision_3d_geometric_interface_is_active(cfg)
    _step(sess.runtime, 2)


def test_capability_payload_researcher_only():
    cfg = acanthostega_beta4_config()

    class R:
        def __init__(self, c):
            self.config = c

    payload = _acanthostega_beta4_capability_payload(R(cfg))
    assert payload is not None
    block = payload["acanthostega_beta4_capability"]
    assert block["researcher_only"] is True
    assert block["held_to_world_physical_trigger"] == "BLOCKED"
    assert block["stages"]["free_space_v1d"] is True
    assert block["stages"]["VW1_occupancy"] is True
    assert block["stages"]["VW6_minimal_vision_3d"] is True
    assert "Acanthostega Beta 4.0" in block["banner"]


# ---- BASELINE OCCUPANCY / VW7 ----


def test_baseline_vw7_renders_authoritative_intervals():
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(config=cfg, seed=17)
    intervals = occupied_intervals_at(rt.world, 8, 8)
    assert intervals, "canonical baseline must resolve nonempty intervals"
    prims = build_occupancy_volume_primitives(rt.world, config=cfg)
    assert len(prims) > 0
    desc = build_observer_volume_render_description(rt)
    assert desc.get("available") is True
    assert int(desc.get("occupancy_volume_count") or 0) > 0
    assert len(desc.get("occupancy_volumes") or []) > 0
    assert desc.get("heightfield_is_volume_authority") is False
    assert desc.get("renderer_writes_physics") is False
    _step(rt, 1)


# ---- DUPLICATION / SHARED WORLD ----


def test_two_agent_shared_occupancy_and_single_apply():
    sess = ObserverSession()
    sess.apply_experiment(
        {
            "public_preset": PRESET_ACANTHOSTEGA_BETA4,
            "seed": 17,
            "agent_count": 2,
            "cognition_enabled": False,
            "load_preset": True,
        }
    )
    assert volumetric_world_material_occupancy_is_active(sess.runtime.config)
    from mechanistic_mind.physical_system.volumetric_world_material_occupancy import state_of

    st = state_of(sess.runtime.world)
    assert st is not None
    prims = build_occupancy_volume_primitives(sess.runtime.world, config=sess.runtime.config)
    assert len(prims) > 0
    _step(sess.runtime, 2)


def test_snapshot_restore_preserves_beta4_identity():
    cfg = acanthostega_beta4_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=21, config=cfg)
    _step(rt, 2)
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert rt2.config.public_preset == PRESET_ACANTHOSTEGA_BETA4
    assert rt2.config.model_line == "ACANTHOSTEGA"
    assert volumetric_world_material_occupancy_is_active(rt2.config)
    assert free_space_state_and_pe_authority_contract_is_active(rt2.config)
    assert build_observer_volume_render_description(rt2).get("available") is True
    _step(rt2, 1)


def test_tiktaalik_fingerprint_unchanged_probe():
    a = preset_canonical(PRESET_TIKTAALIK_BETA31)
    b = preset_canonical(PRESET_TIKTAALIK_BETA31)
    assert a["public_preset"] == PRESET_TIKTAALIK_BETA31
    assert a == b
    cfg = PhysicalSystemConfig()
    stamp_config_from_preset(cfg, PRESET_TIKTAALIK_BETA31)
    assert cfg.model_line == "TIKTAALIK" or str(getattr(cfg, "public_preset", "")).startswith("TIKTAALIK")
    assert not volumetric_world_material_occupancy_is_active(cfg)


def test_probe_budget_under_100():
    assert TICKS["n"] <= 100
