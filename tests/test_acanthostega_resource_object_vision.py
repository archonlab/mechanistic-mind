"""Acanthostega physical ResourceObject vision — anonymous optical contribution only."""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from mechanistic_mind.model.acanthostega import (
    PUBLIC_PRESET_MATERIAL_VISION,
    PUBLIC_PRESET_MATERIALS,
    acanthostega_config,
    acanthostega_gentle_config,
    acanthostega_material_vision_config,
    acanthostega_materials_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA,
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_ACANTHOSTEGA_MATERIAL_VISION,
    PRESET_ACANTHOSTEGA_MATERIALS,
    PRESET_BETA31,
    acanthostega_mechanism_map,
    acanthostega_resource_mechanism_map,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.near_field_exteroception import sample_near_field
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.resource_objects import (
    CANONICAL_FIRST_OBJECT_ID,
    PHYSICAL_RESOURCE_OBJECT_VISION,
    PHYSICAL_RESOURCE_OBJECTS,
    object_vision_is_active,
    objects_is_active,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.serialize import header_info, world_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

FROZEN_BETA31_FP_SEED17 = "1621ef2c154864d1"
SEED = 17
FORBIDDEN_LEAKS = (
    "resource-000001",
    "RESOURCE_OBJECT",
    "FREE_STATIC",
    "component_0",
    "composition",
    "object_id",
    "RESOURCE_OBJECT_SURFACE",
    "physical_resource_object_vision",
)


def _objs(world):
    return list(getattr(world, "resource_objects", None) or [])


def _nfe_bright(cfg):
    cfg.cognition.cognition_enabled = False
    nfe = cfg.near_field_exteroception
    nfe.mode = "EXPERIMENTAL"
    nfe.perception_enabled = True
    nfe.illumination_enabled = False
    nfe.illumination_frozen = 1.0
    nfe.illumination_min = 1.0
    nfe.illumination_max = 1.0
    nfe.radius = 3
    nfe.threshold = 0.04
    nfe.body_optical_enabled = True
    nfe.visual_surface_discrimination = "RICH"
    nfe.spatial_vision = "LEGACY"
    return cfg


def _look_at_object(rt):
    obj = _objs(rt.world)[0]
    rt.body.x = float(obj.x) - 1.3
    rt.body.y = float(obj.y)
    rt.body.theta = 0.0
    rt.body.vx = rt.body.vy = 0.0
    if rt.world.surface_response is not None:
        rt.world.surface_response[:, :] = 0.0
    return obj


def _walk_blob(payload):
    text = repr(payload)
    return [tok for tok in FORBIDDEN_LEAKS if tok in text]


def test_preservation_maps_and_fingerprint():
    m = beta31_mechanism_map()
    assert PHYSICAL_RESOURCE_OBJECTS not in m
    assert PHYSICAL_RESOURCE_OBJECT_VISION not in m
    assert PHYSICAL_RESOURCE_OBJECT_VISION not in acanthostega_mechanism_map()
    assert PHYSICAL_RESOURCE_OBJECT_VISION not in acanthostega_resource_mechanism_map()
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    tik = PhysicalSystemRuntime(seed=SEED, config=_nfe_bright(tiktaalik_config()))
    tik.body.x, tik.body.y, tik.body.theta = 16.5, 16.5, 0.0
    a = dict(tik.agent_observation())
    tik2 = PhysicalSystemRuntime(seed=SEED, config=_nfe_bright(tiktaalik_config()))
    tik2.body.x, tik2.body.y, tik2.body.theta = 16.5, 16.5, 0.0
    assert tik2.agent_observation() == a
    assert objects_is_active(tik.config) is False
    assert object_vision_is_active(tik.config) is False


def test_preset_separation_visibility():
    assert normalize_preset_name("Acanthostega Phase A Material Vision") == PRESET_ACANTHOSTEGA_MATERIAL_VISION
    pm = preset_canonical(PRESET_ACANTHOSTEGA_MATERIALS, seed=17)
    pv = preset_canonical(PRESET_ACANTHOSTEGA_MATERIAL_VISION, seed=17)
    assert PHYSICAL_RESOURCE_OBJECT_VISION not in pm["mechanisms"]
    assert pv["mechanisms"][PHYSICAL_RESOURCE_OBJECT_VISION] is True
    assert pv["mechanisms"][PHYSICAL_RESOURCE_OBJECTS] is True
    mats = PhysicalSystemRuntime(seed=SEED, config=_nfe_bright(acanthostega_materials_config()))
    vis = PhysicalSystemRuntime(seed=SEED, config=_nfe_bright(acanthostega_material_vision_config()))
    assert len(_objs(mats.world)) == 1 and len(_objs(vis.world)) == 1
    _look_at_object(mats)
    _look_at_object(vis)
    assert object_vision_is_active(mats.config) is False
    assert object_vision_is_active(vis.config) is True
    exo_m = [mats.agent_observation().get(f"exo_{i}", 0.0) for i in range(3)]
    exo_v = [vis.agent_observation().get(f"exo_{i}", 0.0) for i in range(3)]
    assert sum(exo_m) < 1e-9
    assert sum(exo_v) > 1e-6


def test_in_fov_anonymous_contribution():
    rt = PhysicalSystemRuntime(seed=SEED, config=_nfe_bright(acanthostega_material_vision_config()))
    obj = _look_at_object(rt)
    obs = rt.agent_observation()
    assert sum(obs.get(f"exo_{i}", 0.0) for i in range(3)) > 1e-6
    assert any(obs.get(k, 0.0) > 0.0 for k in obs if k.startswith("surface_c"))
    snf = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True
    )
    rows = [r for r in snf["neighbors"] if float(r.get("resource_object_optical") or 0.0) > 0.0]
    assert rows
    assert any(CANONICAL_FIRST_OBJECT_ID in (r.get("resource_object_ids") or []) for r in rows)
    assert _walk_blob(obs) == []
    assert audit_cognition_payload(obs) == []
    assert abs(obj.optical_response[0] - 0.72) < 1e-9


def test_outside_radius_and_behind_head():
    rt = PhysicalSystemRuntime(seed=SEED, config=_nfe_bright(acanthostega_material_vision_config()))
    obj = _objs(rt.world)[0]
    rt.config.near_field_exteroception.radius = 1
    rt.body.x = float(obj.x) - 3.5
    rt.body.y = float(obj.y)
    rt.body.theta = 0.0
    if rt.world.surface_response is not None:
        rt.world.surface_response[:, :] = 0.0
    far = rt.agent_observation()
    assert sum(far.get(f"exo_{i}", 0.0) for i in range(3)) < 1e-9
    rt.config.near_field_exteroception.radius = 3
    _look_at_object(rt)
    rt.body.theta = float(np.pi)
    behind = rt.agent_observation()
    assert sum(behind.get(f"exo_{i}", 0.0) for i in range(3)) < 1e-9
    rt.body.theta = 0.0
    facing = rt.agent_observation()
    assert sum(facing.get(f"exo_{i}", 0.0) for i in range(3)) > 1e-6
    assert _walk_blob(behind) == [] and _walk_blob(facing) == []


def test_occlusion_nearest_sector():
    rt = PhysicalSystemRuntime(seed=SEED, config=_nfe_bright(acanthostega_material_vision_config()))
    rt.config.near_field_exteroception.spatial_vision = "OCCLUSION"
    obj = _objs(rt.world)[0]
    rt.body.x = float(obj.x) - 2.3
    rt.body.y = float(obj.y)
    rt.body.theta = 0.0
    rt.body.vx = rt.body.vy = 0.0
    if rt.world.surface_response is None:
        rt.world.surface_response = np.zeros_like(rt.world.T, dtype=np.float64)
    rt.world.surface_response[:, :] = 0.0
    occluder_ix = int(np.floor(rt.body.x)) + 1
    occluder_iy = int(np.floor(obj.y))
    obj_ix = int(np.floor(obj.x))
    assert occluder_ix != obj_ix
    rt.world.surface_response[occluder_iy, occluder_ix] = 0.99
    snf = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    obj_rows = [
        r for r in snf["neighbors"]
        if CANONICAL_FIRST_OBJECT_ID in (r.get("resource_object_ids") or [])
    ]
    assert obj_rows
    assert any(r.get("visibility") == "OCCLUDED" for r in obj_rows) or snf.get("n_occluded", 0) >= 1
    rt.world.surface_response[:, :] = 0.0
    snf2 = sample_near_field(world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception)
    obj_rows2 = [
        r for r in snf2["neighbors"]
        if CANONICAL_FIRST_OBJECT_ID in (r.get("resource_object_ids") or [])
    ]
    assert any(float(r.get("visible_contribution") or r.get("final_contribution") or 0.0) > 0.0 for r in obj_rows2)


def test_illumination_scales_contribution():
    rt = PhysicalSystemRuntime(seed=SEED, config=_nfe_bright(acanthostega_material_vision_config()))
    _look_at_object(rt)
    nfe = rt.config.near_field_exteroception
    nfe.illumination_enabled = False
    nfe.illumination_frozen = 1.0
    hi = sum(rt.agent_observation().get(f"exo_{i}", 0.0) for i in range(3))
    nfe.illumination_frozen = 0.2
    lo = sum(rt.agent_observation().get(f"exo_{i}", 0.0) for i in range(3))
    nfe.illumination_frozen = 0.0
    dark = sum(rt.agent_observation().get(f"exo_{i}", 0.0) for i in range(3))
    assert hi > lo >= dark
    assert dark < 1e-9 or dark < lo
    assert "resource_visible" not in rt.agent_observation()


def test_anonymous_spectra_differ_without_labels():
    rt = PhysicalSystemRuntime(seed=SEED, config=_nfe_bright(acanthostega_material_vision_config()))
    obj = _look_at_object(rt)
    obj.optical_response = (0.95, 0.05, 0.05)
    a = dict(rt.agent_observation())
    obj.optical_response = (0.05, 0.05, 0.95)
    b = dict(rt.agent_observation())
    surf_a = {k: a[k] for k in a if k.startswith("surface_c")}
    surf_b = {k: b[k] for k in b if k.startswith("surface_c")}
    assert surf_a != surf_b
    assert _walk_blob(a) == [] and _walk_blob(b) == []


def test_two_agent_viewpoints():
    cfg = _nfe_bright(acanthostega_material_vision_config())
    a = TwoAgentRuntime(seed=SEED, config=cfg, process_order=(0, 1))
    b = TwoAgentRuntime(seed=SEED, config=cfg, process_order=(1, 0))
    obj = _objs(a.world)[0]
    a.slots[0].body.x = float(obj.x) - 1.3
    a.slots[0].body.y = float(obj.y)
    a.slots[0].body.theta = 0.0
    a.slots[1].body.x = float(obj.x) + 1.3
    a.slots[1].body.y = float(obj.y)
    a.slots[1].body.theta = 0.0
    b.slots[0].body.x = a.slots[0].body.x
    b.slots[0].body.y = a.slots[0].body.y
    b.slots[0].body.theta = 0.0
    b.slots[1].body.x = a.slots[1].body.x
    b.slots[1].body.y = a.slots[1].body.y
    b.slots[1].body.theta = 0.0
    if a.world.surface_response is not None:
        a.world.surface_response[:, :] = 0.0
        b.world.surface_response[:, :] = 0.0
    o0 = a.agent_observation_for(0) if hasattr(a, "agent_observation_for") else a.slots[0].agent_observation(
        foreign_bodies=a.foreign_bodies_for(0)
    )
    o1 = a.slots[1].agent_observation(foreign_bodies=a.foreign_bodies_for(1))
    p0 = b.slots[0].agent_observation(foreign_bodies=b.foreign_bodies_for(0))
    p1 = b.slots[1].agent_observation(foreign_bodies=b.foreign_bodies_for(1))
    s0 = sum(o0.get(f"exo_{i}", 0.0) for i in range(3))
    s1 = sum(o1.get(f"exo_{i}", 0.0) for i in range(3))
    assert s0 > 1e-6
    assert s1 < 1e-9
    assert abs(s0 - sum(p0.get(f"exo_{i}", 0.0) for i in range(3))) < 1e-12
    assert abs(s1 - sum(p1.get(f"exo_{i}", 0.0) for i in range(3))) < 1e-12
    assert _walk_blob(o0) == [] and _walk_blob(o1) == []
    assert len(_objs(a.world)) == 1


def test_snapshot_restore_optical_match():
    cfg = _nfe_bright(acanthostega_material_vision_config())
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    _look_at_object(rt)
    before = dict(rt.agent_observation())
    snap = deepcopy(rt.snapshot())
    rest = PhysicalSystemRuntime.restore(snap)
    _look_at_object(rest)
    after = dict(rest.agent_observation())
    for k in before:
        if k.startswith("exo_") or k.startswith("surface_c"):
            assert abs(float(before[k]) - float(after.get(k, 0.0))) < 1e-9
    assert len(_objs(rest.world)) == 1
    mats_snap = PhysicalSystemRuntime(seed=SEED, config=_nfe_bright(acanthostega_materials_config())).snapshot()
    mats_rest = PhysicalSystemRuntime.restore(deepcopy(mats_snap))
    assert object_vision_is_active(mats_rest.config) is False
    _look_at_object(mats_rest)
    assert sum(mats_rest.agent_observation().get(f"exo_{i}", 0.0) for i in range(3)) < 1e-9


def test_legacy_optical_fields_default_without_agent_visibility():
    cfg = _nfe_bright(acanthostega_materials_config())
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    d = _objs(rt.world)[0].to_dict()
    d.pop("optical_radius", None)
    d.pop("optical_response", None)
    from mechanistic_mind.physical_system.resource_objects import ResourceObject
    restored = ResourceObject.from_dict(d)
    assert restored.optical_radius > 0.0
    assert restored.optical_response[0] > 0.0
    assert object_vision_is_active(rt.config) is False


def test_observer_apply_and_analyzer_forward():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_ACANTHOSTEGA_MATERIAL_VISION,
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
    })
    ident = s.runtime.model_identity()
    assert ident["public_preset"] == PUBLIC_PRESET_MATERIAL_VISION
    assert ident["physical_resource_object_vision"] is True
    assert ident["agent_resource_perception_implemented"] is False
    hdr = header_info(s.runtime, status="PAUSED", mode="LIVE", target_tick=None)
    assert hdr["physical_resource_object_vision"] is True
    ids = {m["id"] for m in (s.runtime.mechanisms().get("mechanisms") or [])}
    assert PHYSICAL_RESOURCE_OBJECT_VISION in ids
    wf = world_frame(s.runtime, max_side=32, detail="full")
    assert wf["resource_objects"][0]["agent_optical_contribution_enabled"] is True
    slot = s.runtime.slots[0]
    obs = slot.agent_observation(foreign_bodies=s.runtime.foreign_bodies_for(0))
    assert _walk_blob(obs) == []

    s_m = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s_m.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_ACANTHOSTEGA_MATERIALS,
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
    })
    ids_m = {m["id"] for m in (s_m.runtime.mechanisms().get("mechanisms") or [])}
    assert PHYSICAL_RESOURCE_OBJECTS in ids_m
    enabled = s_m.runtime.mechanisms().get("enabled") or {}
    assert not enabled.get(PHYSICAL_RESOURCE_OBJECT_VISION)
    wf_m = world_frame(s_m.runtime, max_side=32, detail="full")
    assert wf_m["resource_objects"][0]["agent_optical_contribution_enabled"] is False

    s_t = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s_t.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_BETA31,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    ids_t = {m["id"] for m in (s_t.runtime.mechanisms().get("mechanisms") or [])}
    assert PHYSICAL_RESOURCE_OBJECT_VISION not in ids_t
