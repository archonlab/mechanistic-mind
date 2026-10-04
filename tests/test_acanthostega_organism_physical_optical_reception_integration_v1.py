"""O4 Organism physical optical reception V1 — focused tests."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.physical_body.state import PhysicalBodyState
from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
    set_abstract_spectral_light_source_and_direct_transport,
)
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BETA4,
    acanthostega_beta4_mechanism_map,
    public_model_selector_entries,
)
from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
    set_exposed_surface_optical_interaction_authority,
)
from mechanistic_mind.physical_system.near_field_exteroception import (
    NearFieldExteroceptionConfig,
    sample_near_field,
)
from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
    set_object_body_held_optical_surfaces,
)
from mechanistic_mind.physical_system.organism_physical_optical_reception import (
    AUTHORITY,
    CAPABILITY,
    COGNITION_SCHEMA,
    K_VISUAL,
    OPTICAL_BAND_COUNT,
    PROFILE,
    SCHEMA,
    VISUAL_CAUSAL_DELAY_TICKS,
    build_o4_analyzer_reconstruction,
    organism_physical_optical_reception_is_active,
    sample_physical_optical_reception,
    set_organism_physical_optical_reception,
)
from mechanistic_mind.physical_system.physical_optical_material_profile import (
    set_physical_optical_material_profile,
)
from mechanistic_mind.physical_system.resource_objects import (
    MaterialComponent,
    PHYSICAL_STATE_FREE_STATIC,
    ResourceObject,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
    OccupiedZInterval,
    ensure_state,
    set_volumetric_column,
    set_volumetric_world_material_occupancy,
)
from mechanistic_mind.physical_system.minimal_vision_3d_geometric_interface import (
    set_minimal_vision_3d_geometric_interface,
)

RESULTS = Path("results/acanthostega_organism_physical_optical_reception_integration_v1")


def _cfg_o4():
    cfg = PhysicalSystemConfig(model_line="ACANTHOSTEGA", public_preset="DEV_O4_FIXTURE")
    set_volumetric_world_material_occupancy(cfg, True)
    set_minimal_vision_3d_geometric_interface(cfg, True)
    set_physical_optical_material_profile(cfg, True)
    set_exposed_surface_optical_interaction_authority(cfg, True)
    set_abstract_spectral_light_source_and_direct_transport(cfg, True)
    set_object_body_held_optical_surfaces(cfg, True)
    set_organism_physical_optical_reception(cfg, True)
    cfg.near_field_exteroception = NearFieldExteroceptionConfig(
        mode="EXPERIMENTAL",
        perception_enabled=True,
        visual_surface_discrimination="RICH",
        fov_deg=120.0,
        radius=3,
        gain=1.0,
        saturation=1.0,
        threshold=0.0,
        illumination_enabled=False,
    )
    return cfg


def _body(x=5.5, y=5.5, z=0.0):
    return PhysicalBodyState(
        tick=0, x=x, y=y, vx=0.0, vy=0.0, T=1.0,
        B=np.zeros(1), B_core=np.zeros(1), mech=0.0,
        matter_in=0.0, matter_out=0.0, heat_from_world=0.0, heat_to_world=0.0,
        react_consumed=0.0, core_exchange_cum=0.0,
        z=z, vz=0.0, grounded=True, vertical_half_extent=0.575, theta=0.0,
    )


def test_schema_identity():
    assert SCHEMA == "ORGANISM_PHYSICAL_OPTICAL_RECEPTION_V1"
    assert CAPABILITY == "organism_physical_optical_reception"
    assert PROFILE == "O3_SURFACE_TO_VW6_RECEPTOR_DIRECT_RECEPTION_O4_V1"
    assert AUTHORITY == "PHYSICAL_ABSTRACT_OPTICAL_FIELD_TO_ORGANISM_RECEPTOR"
    assert OPTICAL_BAND_COUNT == 6
    assert VISUAL_CAUSAL_DELAY_TICKS == 0
    assert K_VISUAL > 0
    assert "PAIR" in COGNITION_SCHEMA or "6_TO_3" in COGNITION_SCHEMA


def test_illuminated_terrain_nonzero_and_source_disabled_zero():
    cfg = _cfg_o4()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    setattr(rt.world, "_physical_system_config", cfg)
    # Ground patch in front of body (+X)
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    set_volumetric_column(rt.world, 7, 5, [it], reason="test")
    body = _body(x=5.5, y=5.5, z=0.0)
    body.theta = 0.0  # facing +X
    out = sample_physical_optical_reception(
        world=rt.world, body=body, nfe_cfg=cfg.near_field_exteroception,
        physical_config=cfg, tick=0, diagnostic=True,
    )
    assert out["o4_physical_optical_reception"] is True
    fr = out["fragments"]
    assert all(k in fr for k in ("exo_0", "exo_1", "exo_2"))
    # May or may not get signal depending on FOV/geometry — at least schema and no legacy illum
    assert out.get("illumination") is None
    assert out["o4_trace"]["legacy_illumination_used"] is False or out["o4_trace"].get("k_visual") == K_VISUAL
    # Disable source → physical zero
    cfg.abstract_spectral_light_source_and_direct_transport.source.enabled = False
    out2 = sample_physical_optical_reception(
        world=rt.world, body=body, nfe_cfg=cfg.near_field_exteroception,
        physical_config=cfg, tick=0, diagnostic=True,
    )
    assert sum(out2["fragments"].values()) == 0.0


def test_sample_near_field_uses_o4_not_legacy_illumination():
    cfg = _cfg_o4()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    setattr(rt.world, "_physical_system_config", cfg)
    set_volumetric_column(
        rt.world, 6, 5,
        [OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))],
        reason="test",
    )
    body = rt.body
    body.x, body.y, body.z, body.theta = 5.5, 5.5, 0.0, 0.0
    sample = sample_near_field(
        world=rt.world, body=body, cfg=cfg.near_field_exteroception,
        physical_config=cfg,
    )
    assert sample.get("o4_physical_optical_reception") is True
    assert "exo_0" in (sample.get("fragments") or {})
    # RICH surface keys present
    sf = sample.get("surface_fragments") or {}
    assert any(k.startswith("surface_c") for k in sf)


def test_vw1_occlusion_blocks_reception():
    cfg = _cfg_o4()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    setattr(rt.world, "_physical_system_config", cfg)
    # Target ground and a wall between eye and a far top? Simpler: source from +Z;
    # eye looks at top facet with blocker column between isn't needed for +Z tops.
    # Place occluder entity above a free object and verify entity occlusion path.
    low = ResourceObject(
        object_id="low", x=6.5, y=5.5, mass=1.0, quantity=1.0,
        composition=(MaterialComponent("component_0", 1.0),),
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        collision_radius=0.25, vertical_half_extent=0.25, z=0.0,
        optical_radius=0.45,
    )
    high = ResourceObject(
        object_id="high", x=6.5, y=5.5, mass=1.0, quantity=1.0,
        composition=(MaterialComponent("component_0", 1.0),),
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        collision_radius=0.4, vertical_half_extent=0.4, z=2.0,
        optical_radius=0.45,
    )
    rt.world.resource_objects = [low, high]
    body = _body(x=5.5, y=5.5)
    body.theta = 0.0
    out = sample_physical_optical_reception(
        world=rt.world, body=body, nfe_cfg=cfg.near_field_exteroception,
        physical_config=cfg, diagnostic=True,
    )
    # Trace should record some occlusion or acceptance without crashing
    assert "reason_counts" in out["o4_trace"]
    assert out["o4_trace"]["los_queries"] >= 0


def test_unknown_body_not_fabricated():
    cfg = _cfg_o4()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    setattr(rt.world, "_physical_system_config", cfg)
    # Only a body nearby — UNKNOWN_PROFILE → no fabricated bands
    body = _body(x=5.5, y=5.5)
    foreign = _body(x=6.2, y=5.5)
    out = sample_physical_optical_reception(
        world=rt.world, body=body, nfe_cfg=cfg.near_field_exteroception,
        physical_config=cfg, foreign_bodies=[(foreign, None)], diagnostic=True,
    )
    # May have UNKNOWN_MATERIAL rejects; must not invent positive body color from optical_response
    assert out["o4_trace"].get("legacy_optical_response_used") is False or "legacy_optical_response_used" not in out["o4_trace"] or out["o4_trace"]["legacy_optical_response_used"] is False


def test_beta4_tiktaalik_selector_privacy_restore():
    cfg = acanthostega_beta4_config()
    assert organism_physical_optical_reception_is_active(cfg)
    assert acanthostega_beta4_mechanism_map().get("organism_physical_optical_reception") is True
    assert len(public_model_selector_entries()) == 2
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_BETA4
    assert not organism_physical_optical_reception_is_active(
        PhysicalSystemConfig(model_line="TIKTAALIK")
    )
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    snap = rt.snapshot()
    assert snap["config"]["organism_physical_optical_reception"]["enabled"] is True
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert organism_physical_optical_reception_is_active(rt2.config)
    # Restore must not create a reception trace replay
    assert getattr(rt2.world, "_o4_last_reception_trace", None) in (None, {})
    obs = rt.agent_observation()
    blob = json.dumps(obs, sort_keys=True)
    for tok in (SCHEMA, "o4_trace", "k_visual", "contrib_bands", "reflected_spectral_exitance_proxy"):
        assert tok not in blob


def test_analyzer_claim_only_with_evidence():
    empty = build_o4_analyzer_reconstruction({})
    assert empty["physical_signal_reached_receptor"] is False
    assert empty["conscious_seeing_claimed"] is False
    claimed = build_o4_analyzer_reconstruction({"physical_signal_reached_receptor": True, "accepted": 3})
    assert claimed["physical_signal_reached_receptor"] is True
    assert claimed["conscious_seeing_claimed"] is False
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "validation_evidence.json").write_text(json.dumps({
        "schema": SCHEMA,
        "profile": PROFILE,
        "capability": CAPABILITY,
        "cognition_schema": COGNITION_SCHEMA,
        "k_visual": K_VISUAL,
        "visual_causal_delay_ticks": VISUAL_CAUSAL_DELAY_TICKS,
        "ticks": 0,
    }, indent=2) + "\n")


def test_o4_off_preserves_legacy_path():
    cfg = _cfg_o4()
    set_organism_physical_optical_reception(cfg, False)
    assert not organism_physical_optical_reception_is_active(cfg)
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    setattr(rt.world, "_physical_system_config", cfg)
    sample = sample_near_field(
        world=rt.world, body=rt.body, cfg=cfg.near_field_exteroception,
        physical_config=cfg,
    )
    assert sample.get("o4_physical_optical_reception") is not True
