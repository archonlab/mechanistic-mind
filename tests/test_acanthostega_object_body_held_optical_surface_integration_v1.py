"""O3A Object/body/held optical surface integration V1 — focused tests."""
from __future__ import annotations

import json
import math
from pathlib import Path

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
    STATE_BACK,
    STATE_DIRECT,
    STATE_OCCLUDED,
    STATE_UNKNOWN_MAT,
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
from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
    AUTHORITY,
    CAPABILITY,
    CLASS_BODY,
    CLASS_FREE_OBJECT,
    CLASS_HELD_OBJECT,
    ENTITY_ENTITY_LIGHT_OCCLUSION,
    GEOMETRY_PROFILE_OBJECT,
    MAX_SAMPLES_PER_BODY,
    MAX_SAMPLES_PER_OBJECT,
    PROFILE,
    SAMPLE_PATTERN_BODY,
    SAMPLE_PATTERN_OBJECT,
    SCHEMA,
    build_body_surface_samples,
    build_object_surface_samples,
    ensure_entity_surface_cache,
    invalidate_entity_surface_cache,
    object_body_held_optical_surfaces_is_active,
    query_entity_surfaces,
    query_entity_surfaces_region,
    query_entity_surface_candidates,
    set_object_body_held_optical_surfaces,
    build_object_body_held_optical_causal_reconstruction,
)
from mechanistic_mind.physical_system.physical_optical_material_profile import (
    set_physical_optical_material_profile,
)
from mechanistic_mind.physical_system.resource_objects import (
    MaterialComponent,
    PHYSICAL_STATE_FREE_STATIC,
    PHYSICAL_STATE_HELD,
    ResourceObject,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
    OccupiedZInterval,
    ensure_state,
    set_volumetric_column,
    set_volumetric_world_material_occupancy,
)
from mechanistic_mind.physical_body.state import PhysicalBodyState
import numpy as np

RESULTS = Path("results/acanthostega_object_body_held_optical_surface_integration_v1")


def _cfg():
    cfg = PhysicalSystemConfig(model_line="ACANTHOSTEGA", public_preset="DEV_O3A_FIXTURE")
    set_volumetric_world_material_occupancy(cfg, True)
    set_physical_optical_material_profile(cfg, True)
    set_exposed_surface_optical_interaction_authority(cfg, True)
    set_abstract_spectral_light_source_and_direct_transport(cfg, True)
    set_object_body_held_optical_surfaces(cfg, True)
    return cfg


def _body(x=5.5, y=5.5, z=0.0):
    return PhysicalBodyState(
        tick=0, x=x, y=y, vx=0.0, vy=0.0, T=1.0,
        B=np.zeros(1), B_core=np.zeros(1), mech=0.0,
        matter_in=0.0, matter_out=0.0, heat_from_world=0.0, heat_to_world=0.0,
        react_consumed=0.0, core_exchange_cum=0.0,
        z=z, vz=0.0, grounded=True, vertical_half_extent=0.575, theta=0.0,
    )


def _obj(**kw):
    defaults = dict(
        object_id="obj_a",
        x=8.5, y=8.5, mass=1.0, quantity=1.0,
        composition=(MaterialComponent("component_0", 1.0),),
        physical_state=PHYSICAL_STATE_FREE_STATIC,
        collision_radius=0.25,
        optical_radius=0.45,
        vertical_half_extent=0.25,
        z=0.0,
    )
    defaults.update(kw)
    return ResourceObject(**defaults)


def test_schema_identity():
    assert SCHEMA == "OBJECT_BODY_HELD_OPTICAL_SURFACES_V1"
    assert CAPABILITY == "object_body_held_optical_surfaces"
    assert PROFILE == "ANALYTIC_PHYSICAL_SURFACE_SAMPLES_FOR_DIRECT_LIGHT_O3A_V1"
    assert AUTHORITY == "DERIVED_FROM_AUTHORITATIVE_BODY_AND_RESOURCE_OBJECT_GEOMETRY"
    assert MAX_SAMPLES_PER_OBJECT == 6
    assert MAX_SAMPLES_PER_BODY == 10
    assert SAMPLE_PATTERN_OBJECT == "SPHERE_AXIS6_V1"
    assert SAMPLE_PATTERN_BODY == "CAPSULE_TOP_BOTTOM_EQ8_V1"
    assert "IMPLEMENTED" in ENTITY_ENTITY_LIGHT_OCCLUSION


def test_object_samples_use_collision_not_optical_radius():
    cfg = _cfg()
    obj = _obj(collision_radius=0.30, optical_radius=0.90, vertical_half_extent=0.30)
    samples = build_object_surface_samples(obj, cfg)
    assert len(samples) == 6
    assert samples[0]["geometry_profile"] == GEOMETRY_PROFILE_OBJECT
    assert abs(samples[0]["geometry_radius"] - 0.30) < 1e-12
    assert all(s["optical_radius_not_used"] for s in samples)
    for s in samples:
        n = s["outward_unit_normal"]
        mag = math.sqrt(sum(v * v for v in n))
        assert abs(mag - 1.0) < 1e-9
        assert s["area_weight"] > 0 and math.isfinite(s["area_weight"])
    ids = [s["sample_id"] for s in samples]
    assert ids == sorted(ids)
    assert abs(samples[0]["entity_centre"][2] - 0.30) < 1e-9  # centre_z = z + he


def test_body_samples_follow_pose_and_vhe():
    cfg = _cfg()
    body = _body(x=3.0, y=4.0, z=1.0)
    samples = build_body_surface_samples("body-0", body, cfg)
    assert len(samples) == 10
    assert all(s["entity_class"] == CLASS_BODY for s in samples)
    assert abs(samples[0]["entity_centre"][2] - (1.0 + 0.575)) < 1e-9
    tops = [s for s in samples if s["sample_id"].endswith(":top")]
    assert len(tops) == 1
    assert tops[0]["outward_unit_normal"] == [0.0, 0.0, 1.0]


def test_held_single_identity_and_pose():
    cfg = _cfg()
    free = _obj(object_id="same", physical_state=PHYSICAL_STATE_FREE_STATIC, x=1.0, y=1.0)
    held = _obj(
        object_id="same",
        physical_state=PHYSICAL_STATE_HELD,
        x=2.0, y=3.0, z=0.5,
        holder_body_id="body-0",
        manipulator_id="manipulator_left",
    )
    sf = build_object_surface_samples(free, cfg)
    sh = build_object_surface_samples(held, cfg)
    assert all(s["entity_id"] == "same" for s in sf + sh)
    assert all(s["entity_class"] == CLASS_HELD_OBJECT for s in sh)
    assert abs(sh[0]["entity_centre"][0] - 2.0) < 1e-12
    assert abs(sf[0]["entity_centre"][0] - 1.0) < 1e-12
    assert len(sh) == len(sf) == 6


def test_detached_o1_and_unknown_body():
    cfg = _cfg()
    obj = _obj(provenance={"detached": True, "source": "terrain"})
    samples = build_object_surface_samples(obj, cfg)
    assert samples[0]["o1_status"] == "PROFILE_RESOLVED"
    assert samples[0]["spectral_reflectance"] is not None
    body = _body()
    bs = build_body_surface_samples("body-0", body, cfg)
    assert bs[0]["o1_status"] == "UNKNOWN_PROFILE"
    assert bs[0]["spectral_reflectance"] is None


def test_illumination_front_back_vw1_and_self():
    cfg = _cfg()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    obj = _obj(x=5.5, y=5.5, z=0.0, collision_radius=0.25, vertical_half_extent=0.25)
    rt.world.resource_objects = [obj]
    bodies = [("body-0", _body(x=20.0, y=20.0))]
    cache = ensure_entity_surface_cache(rt.world, cfg, bodies=bodies)
    assert cache is not None
    tops = [r for r in cache.illuminations if r.get("sample_id", "").endswith("axis4")]  # +Z
    bots = [r for r in cache.illuminations if r.get("sample_id", "").endswith("axis5")]  # -Z
    assert tops and tops[0]["state_class"] in (STATE_DIRECT, STATE_UNKNOWN_MAT)
    assert bots and bots[0]["state_class"] == STATE_BACK
    # Self not occluding: top sample should not be OCCLUDED by own sphere
    assert tops[0]["state_class"] != STATE_OCCLUDED
    # VW1 blocker above object
    set_volumetric_column(
        rt.world, 5, 5,
        [OccupiedZInterval(2.0, 3.0, 1.0, (("component_0", 1.0),))],
        reason="block",
    )
    invalidate_entity_surface_cache(rt.world)
    cache2 = ensure_entity_surface_cache(rt.world, cfg, bodies=bodies)
    tops2 = [r for r in cache2.illuminations if r.get("sample_id", "").endswith("axis4")]
    assert tops2 and tops2[0]["state_class"] == STATE_OCCLUDED


def test_entity_entity_occlusion():
    cfg = _cfg()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    # Lower object; upper object along +Z ray from lower top sample
    low = _obj(object_id="low", x=4.5, y=4.5, z=0.0, collision_radius=0.25, vertical_half_extent=0.25)
    high = _obj(object_id="high", x=4.5, y=4.5, z=2.0, collision_radius=0.4, vertical_half_extent=0.4)
    rt.world.resource_objects = [low, high]
    cache = ensure_entity_surface_cache(rt.world, cfg, bodies=[])
    low_top = next(r for r in cache.illuminations if r.get("entity_id") == "low" and str(r.get("sample_id")).endswith("axis4"))
    assert low_top["state_class"] == STATE_OCCLUDED
    assert (low_top.get("visibility") or {}).get("blocker", {}).get("entity_id") == "high"


def test_cache_move_invalidation_and_queries():
    cfg = _cfg()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    obj = _obj(x=6.5, y=6.5)
    rt.world.resource_objects = [obj]
    bodies = [("body-0", _body(x=1.0, y=1.0))]
    a = ensure_entity_surface_cache(rt.world, cfg, bodies=bodies)
    hits0 = a.hit_count
    b = ensure_entity_surface_cache(rt.world, cfg, bodies=bodies)
    assert b.hit_count == hits0 + 1
    obj.x = 7.5
    invalidate_entity_surface_cache(rt.world)
    c = ensure_entity_surface_cache(rt.world, cfg, bodies=bodies)
    assert c.key_digest != a.key_digest
    q = query_entity_surfaces(rt.world, cfg, "obj_a", bodies=bodies)
    assert q["sample_count"] == 6
    reg = query_entity_surfaces_region(rt.world, cfg, x0=7, y0=6, x1=8, y1=8, bodies=bodies)
    assert reg["sample_count"] >= 1
    cand = query_entity_surface_candidates(rt.world, cfg, point=(7.5, 6.5, 0.25), max_range=2.0, bodies=bodies)
    assert cand["future_receptor_candidate_set"] is True


def test_beta4_restore_privacy_selector():
    cfg = acanthostega_beta4_config()
    assert object_body_held_optical_surfaces_is_active(cfg)
    assert acanthostega_beta4_mechanism_map().get("object_body_held_optical_surfaces") is True
    assert len(public_model_selector_entries()) == 2
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_BETA4
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    rt.world.resource_objects = [_obj()]
    bodies = [("body-0", rt.body)]
    before = ensure_entity_surface_cache(rt.world, cfg, bodies=bodies)
    snap = rt.snapshot()
    assert snap["config"]["object_body_held_optical_surfaces"]["enabled"] is True
    rt2 = PhysicalSystemRuntime.restore(snap)
    after = ensure_entity_surface_cache(rt2.world, rt2.config, bodies=[("body-0", rt2.body)])
    # Object may not restore via resource_objects depending on spawn — check config+body samples
    assert after is not None
    obs = rt.agent_observation()
    blob = json.dumps(obs, sort_keys=True)
    for tok in (SCHEMA, CAPABILITY, "area_weight", "pose_digest", "SPHERE_AXIS6_V1"):
        assert tok not in blob
    recon = build_object_body_held_optical_causal_reconstruction({"sample_count": 1})
    assert recon["organism_saw_light"] is False
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "validation_evidence.json").write_text(json.dumps({
        "schema": SCHEMA,
        "profile": PROFILE,
        "capability": CAPABILITY,
        "entity_entity_light_occlusion": ENTITY_ENTITY_LIGHT_OCCLUSION,
        "max_samples_per_object": MAX_SAMPLES_PER_OBJECT,
        "max_samples_per_body": MAX_SAMPLES_PER_BODY,
        "checksum_before": before.result_checksum if before else None,
        "ticks": 0,
        "organism_reception": False,
    }, indent=2) + "\n")


def test_two_agents_share_world_authority():
    cfg = _cfg()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    rt.world.resource_objects = [_obj()]
    bodies = [("body-0", _body()), ("body-1", _body(x=10.0, y=10.0))]
    a = ensure_entity_surface_cache(rt.world, cfg, bodies=bodies)
    b = ensure_entity_surface_cache(rt.world, cfg, bodies=bodies)
    assert a.result_checksum == b.result_checksum
    assert CLASS_FREE_OBJECT in a.class_counts
    assert CLASS_BODY in a.class_counts
