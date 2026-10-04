"""Focused tests for ACANTHOSTEGA_BETA4_VOLUMETRIC_WORLD_VW7 public tip."""
from __future__ import annotations

from mechanistic_mind.model.acanthostega import (
    PUBLIC_PRESET_VOLUMETRIC_WORLD_VW7,
    PUBLIC_PRESET_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION,
    acanthostega_volumetric_world_vw7_config,
    acanthostega_release_and_excavation_support_loss_integration_config,
)
from mechanistic_mind.model.lines import stamp_config_from_preset, identity_for_config
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7,
    PRESET_ACANTHOSTEGA_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION,
    PRESET_ACANTHOSTEGA_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE,
    is_acanthostega_public_preset,
    normalize_preset_name,
    preset_canonical,
    ACANTHOSTEGA_PUBLIC_PRESET_IDS,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession
from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
    volumetric_world_material_occupancy_is_active,
    column_view,
    state_of,
)
from mechanistic_mind.physical_system.occupancy_support_and_contact_queries import (
    occupancy_support_and_contact_queries_is_active,
)
from mechanistic_mind.physical_system.volumetric_world_material_separation import (
    volumetric_world_material_separation_is_active,
)
from mechanistic_mind.physical_system.volumetric_world_material_reintegration import (
    volumetric_world_material_reintegration_is_active,
)
from mechanistic_mind.physical_system.effector_held_occupancy_exertion_bridge import (
    effector_held_occupancy_exertion_bridge_is_active,
    REINTEGRATION_BLOCKER,
)
from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
    minimal_vision_3d_geometric_interface_is_active,
)
from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
    observer_camera_occupancy_consumer_is_active,
    build_observer_volume_render_description,
)


TICKS = {"n": 0}


def _step(rt, n=1):
    for _ in range(n):
        rt.step()
        TICKS["n"] += 1


def test_public_registry_and_normalize():
    assert PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7 in ACANTHOSTEGA_PUBLIC_PRESET_IDS
    assert is_acanthostega_public_preset(PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7)
    assert normalize_preset_name("ACANTHOSTEGA_BETA4_VOLUMETRIC_WORLD_VW7") == PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7
    assert normalize_preset_name("Volumetric World VW7") == PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7
    canon = preset_canonical(PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7)
    assert canon["builder"] == "acanthostega_volumetric_world_vw7_config"
    assert canon["model_line"] == "ACANTHOSTEGA"
    assert canon["parent"] == PRESET_ACANTHOSTEGA_SURFACE_EXERTION_TERRAIN_MATERIAL_RESISTANCE
    assert canon.get("held_to_world_physical_trigger") == "BLOCKED"
    assert canon.get("vw7_observer_consumer") == "PASSIVE"


def test_builder_matrix_and_identity():
    cfg = acanthostega_volumetric_world_vw7_config()
    assert cfg.public_preset == PUBLIC_PRESET_VOLUMETRIC_WORLD_VW7
    assert cfg.model_line == "ACANTHOSTEGA"
    assert volumetric_world_material_occupancy_is_active(cfg)
    assert occupancy_support_and_contact_queries_is_active(cfg)
    assert volumetric_world_material_separation_is_active(cfg)
    assert volumetric_world_material_reintegration_is_active(cfg)
    assert effector_held_occupancy_exertion_bridge_is_active(cfg)
    assert minimal_vision_3d_geometric_interface_is_active(cfg)
    assert observer_camera_occupancy_consumer_is_active(cfg)
    assert REINTEGRATION_BLOCKER
    ident = identity_for_config(cfg)
    assert ident["model_line"] == "ACANTHOSTEGA"
    assert ident["public_preset"] == PUBLIC_PRESET_VOLUMETRIC_WORLD_VW7
    assert "Volumetric World" in str(ident.get("display_name") or ident.get("phase") or "")


def test_conflicting_tiktaalik_model_line_ignored():
    cfg = PhysicalSystemConfig()
    cfg.model_line = "TIKTAALIK"
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7)
    assert cfg.model_line == "ACANTHOSTEGA"
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7
    assert volumetric_world_material_occupancy_is_active(cfg)


def test_parent_v1d_does_not_activate_vw3_to_vw6():
    cfg = acanthostega_release_and_excavation_support_loss_integration_config()
    assert cfg.public_preset == PUBLIC_PRESET_RELEASE_AND_EXCAVATION_SUPPORT_LOSS_INTEGRATION
    assert volumetric_world_material_occupancy_is_active(cfg)
    assert occupancy_support_and_contact_queries_is_active(cfg)
    assert not volumetric_world_material_separation_is_active(cfg)
    assert not volumetric_world_material_reintegration_is_active(cfg)
    assert not effector_held_occupancy_exertion_bridge_is_active(cfg)
    assert not minimal_vision_3d_geometric_interface_is_active(cfg)


def test_apply_readback_and_occupancy_authority():
    s = ObserverSession()
    out = s.apply_experiment({
        "public_preset": PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7,
        "seed": 17,
        "agent_count": 1,
        "cognition_enabled": False,
        "load_preset": True,
        "model_line": "TIKTAALIK",
    })
    cfg = s.runtime.config
    hdr = out.get("header") or {}
    banner = out.get("model_banner") or {}
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7
    assert cfg.model_line == "ACANTHOSTEGA"
    assert hdr.get("model_line") == "ACANTHOSTEGA" or banner.get("model_line") == "ACANTHOSTEGA"
    assert "Volumetric World" in str(hdr.get("experiment") or banner.get("phase_label") or "")
    assert volumetric_world_material_occupancy_is_active(cfg)
    assert minimal_vision_3d_geometric_interface_is_active(cfg)
    st = state_of(s.runtime.world)
    assert st is not None
    cv = column_view(s.runtime.world, 5, 5)
    assert cv and cv.get("occupied_intervals")
    assert cv.get("authority") == "AUTHORITATIVE_WORLD_MATERIAL_OCCUPANCY_ABSOLUTE_Z"
    desc = build_observer_volume_render_description(s.runtime)
    assert desc.get("available") is True
    # VW7 does not fabricate heightfield; unavailable only when VW1 off
    assert desc.get("reason") in (None, "", "OK") or desc.get("available") is True


def test_snapshot_restore_preserves_preset_and_occupancy():
    cfg = acanthostega_volumetric_world_vw7_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=21, config=cfg)
    _step(rt, 2)
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert rt2.config.public_preset == PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7
    assert rt2.config.model_line == "ACANTHOSTEGA"
    assert volumetric_world_material_occupancy_is_active(rt2.config)
    assert state_of(rt2.world) is not None
    assert build_observer_volume_render_description(rt2).get("available") is True


def test_two_agent_shared_occupancy():
    s = ObserverSession()
    s.apply_experiment({
        "public_preset": PRESET_ACANTHOSTEGA_VOLUMETRIC_WORLD_VW7,
        "seed": 17,
        "agent_count": 2,
        "cognition_enabled": False,
        "load_preset": True,
    })
    assert isinstance(s.runtime, TwoAgentRuntime)
    assert volumetric_world_material_occupancy_is_active(s.runtime.config)
    # single world occupancy attribute
    w = s.runtime.world
    assert state_of(w) is not None


def test_vw7_unavailable_without_vw1_preset():
    from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig
    cfg = PhysicalSystemConfig()
    stamp_config_from_preset(cfg, "TIKTAALIK_BETA31")
    rt = PhysicalSystemRuntime(seed=3, config=cfg)
    assert not observer_camera_occupancy_consumer_is_active(cfg)
    desc = build_observer_volume_render_description(rt)
    assert desc.get("available") is False
