"""Acanthostega passive ResourceObject — world ownership, spawn, snapshot, no A/B coupling."""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from mechanistic_mind.model.acanthostega import (
    PUBLIC_PRESET_GENTLE,
    PUBLIC_PRESET_MATERIALS,
    acanthostega_config,
    acanthostega_gentle_config,
    acanthostega_materials_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA,
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_ACANTHOSTEGA_MATERIALS,
    PRESET_BETA31,
    acanthostega_mechanism_map,
    acanthostega_resource_mechanism_map,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.locomotion_profile import GENTLE_TERRAIN_LOCOMOTION, profile_is_active
from mechanistic_mind.physical_system.observation import accessible_observation, audit_cognition_payload
from mechanistic_mind.physical_system.resource_objects import (
    CANONICAL_FIRST_OBJECT_ID,
    PHYSICAL_RESOURCE_OBJECTS,
    objects_is_active,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.serialize import header_info, world_frame
from mechanistic_mind.ui.psy_observer_web.scientific_history import _resource_sum
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

FROZEN_BETA31_FP_SEED17 = "1621ef2c154864d1"
SEED = 17


def _objs(world):
    return list(getattr(world, "resource_objects", None) or [])


def test_tiktaalik_preservation_contract():
    m = beta31_mechanism_map()
    assert PHYSICAL_RESOURCE_OBJECTS not in m
    assert GENTLE_TERRAIN_LOCOMOTION not in m
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    rt = PhysicalSystemRuntime(seed=SEED, config=tiktaalik_config())
    assert len(_objs(rt.world)) == 0
    assert objects_is_active(rt.config) is False


def test_preset_separation_object_counts():
    assert normalize_preset_name("Acanthostega Phase A Materials") == PRESET_ACANTHOSTEGA_MATERIALS
    p0 = preset_canonical(PRESET_ACANTHOSTEGA, seed=17)
    pg = preset_canonical(PRESET_ACANTHOSTEGA_GENTLE, seed=17)
    pm = preset_canonical(PRESET_ACANTHOSTEGA_MATERIALS, seed=17)
    assert PHYSICAL_RESOURCE_OBJECTS not in p0["mechanisms"]
    assert PHYSICAL_RESOURCE_OBJECTS not in pg["mechanisms"]
    assert pm["mechanisms"][PHYSICAL_RESOURCE_OBJECTS] is True
    assert pm["mechanisms"][GENTLE_TERRAIN_LOCOMOTION] is True
    assert p0["mechanisms"] == preset_canonical(PRESET_BETA31, seed=17)["mechanisms"]
    assert PHYSICAL_RESOURCE_OBJECTS not in acanthostega_mechanism_map()
    assert acanthostega_resource_mechanism_map()[PHYSICAL_RESOURCE_OBJECTS] is True

    counts = []
    for cfg in (tiktaalik_config(), acanthostega_config(), acanthostega_gentle_config(), acanthostega_materials_config()):
        cfg = cfg.copy()
        cfg.cognition.cognition_enabled = False
        rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
        counts.append(len(_objs(rt.world)))
    assert counts == [0, 0, 0, 1]


def test_initial_object_deterministic():
    a = PhysicalSystemRuntime(seed=SEED, config=acanthostega_materials_config())
    b = PhysicalSystemRuntime(seed=SEED, config=acanthostega_materials_config())
    oa, ob = _objs(a.world)[0], _objs(b.world)[0]
    assert oa.object_id == CANONICAL_FIRST_OBJECT_ID
    assert oa.object_id == ob.object_id
    assert (oa.x, oa.y, oa.mass, oa.quantity) == (ob.x, ob.y, ob.mass, ob.quantity)
    assert oa.physical_state == "FREE_STATIC"
    assert oa.composition[0].component_id == "component_0"
    assert abs(oa.quantity - oa.mass) < 1e-12
    assert a.tick == 0
    assert abs(oa.mass - oa.quantity) < 1e-15  # density 1 this slice


def test_no_automatic_transfer_wait_250():
    cfg = acanthostega_materials_config()
    cfg.cognition.cognition_enabled = False
    ce = getattr(cfg.planet, "climate_ecology", None)
    if ce is not None:
        ce.resource_ecology_A_enabled = False
        ce.resource_ecology_B_enabled = False
    cfg.complementary_resources.A_passive_loss = 0.0
    cfg.complementary_resources.B_passive_loss = 0.0
    cfg.complementary_resources.B_env_source_rate = 0.0
    cfg.deformation_work.passive_reservoir_trickle = 0.0
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    obj = _objs(rt.world)[0]
    rt.body.x = float(obj.x)
    rt.body.y = float(obj.y)
    rt.body.vx = rt.body.vy = 0.0
    rt.world.R_A[:] = 0.0
    rt.world.R_B[:] = 0.0
    if rt.world.R is not None:
        rt.world.R[:] = 0.0
    n = len(cfg.body.footprint)
    rt.body.R_A_site = np.zeros(n)
    rt.body.R_B_site = np.zeros(n)
    rt.body.R_site = np.zeros(n)
    rt.body.mechanical_work_reservoir = 0.0
    a0 = float(np.sum(rt.body.R_A_site))
    b0 = float(np.sum(rt.body.R_B_site))
    w0 = float(rt.body.mechanical_work_reservoir)
    snap0 = obj.to_dict()
    for _ in range(250):
        rt.step_forced_action("WAIT")
    after = _objs(rt.world)
    assert len(after) == 1
    o = after[0]
    assert o.object_id == snap0["object_id"]
    assert abs(o.x - snap0["x"]) < 1e-12
    assert abs(o.y - snap0["y"]) < 1e-12
    assert abs(o.mass - snap0["mass"]) < 1e-12
    assert abs(o.quantity - snap0["quantity"]) < 1e-12
    assert o.physical_state == snap0["physical_state"]
    assert o.composition[0].amount == snap0["composition"][0]["amount"]
    assert abs(float(np.sum(rt.body.R_A_site)) - a0) < 1e-12
    assert abs(float(np.sum(rt.body.R_B_site)) - b0) < 1e-12
    assert abs(float(rt.body.mechanical_work_reservoir) - w0) < 1e-12


def test_static_persistence_with_ecology():
    cfg = acanthostega_materials_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    before = _objs(rt.world)[0].to_dict()
    for _ in range(250):
        rt.step_forced_action("WAIT")
    after = _objs(rt.world)[0].to_dict()
    assert after["object_id"] == before["object_id"]
    assert after["x"] == before["x"] and after["y"] == before["y"]
    assert after["mass"] == before["mass"]
    assert after["physical_state"] == before["physical_state"]


def test_two_agent_shared_ownership_and_order():
    cfg = acanthostega_materials_config()
    cfg.cognition.cognition_enabled = False
    a = TwoAgentRuntime(seed=SEED, config=cfg, process_order=(0, 1))
    b = TwoAgentRuntime(seed=SEED, config=cfg, process_order=(1, 0))
    assert a.slots[0].world is a.slots[1].world
    assert len(_objs(a.world)) == 1
    assert len(_objs(b.world)) == 1
    assert _objs(a.world)[0].object_id == _objs(b.world)[0].object_id
    snap = a.snapshot()
    worlds = [snap["world"].get("resource_objects")]
    for ag in snap["agents"][1:]:
        worlds.append((ag.get("world") or {}).get("resource_objects"))
    assert worlds[0] is not None
    assert worlds[0]["objects"][0]["object_id"] == CANONICAL_FIRST_OBJECT_ID
    for extra in worlds[1:]:
        assert extra in (None, {}, {"objects": [], "next_id": 1}) or extra is None
    for _ in range(5):
        a.step()
        b.step()
    assert _objs(a.world)[0].to_dict()["x"] == _objs(b.world)[0].to_dict()["x"]


def test_snapshot_round_trip_and_continue():
    cfg = acanthostega_materials_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    for _ in range(7):
        rt.step_forced_action("WAIT")
    snap = deepcopy(rt.snapshot())
    cont = PhysicalSystemRuntime(seed=SEED, config=cfg)
    for _ in range(7):
        cont.step_forced_action("WAIT")
    live_obj = _objs(rt.world)[0].to_dict()
    rest = PhysicalSystemRuntime.restore(deepcopy(snap))
    assert len(_objs(rest.world)) == 1
    assert _objs(rest.world)[0].to_dict()["object_id"] == live_obj["object_id"]
    assert _objs(rest.world)[0].to_dict()["x"] == live_obj["x"]
    rt.step_forced_action("WAIT")
    rest.step_forced_action("WAIT")
    assert _objs(rt.world)[0].to_dict() == _objs(rest.world)[0].to_dict()
    ta = TwoAgentRuntime(seed=SEED, config=cfg)
    ta.step()
    tr = TwoAgentRuntime.restore(deepcopy(ta.snapshot()))
    assert len(_objs(tr.world)) == 1
    assert tr.slots[0].world is tr.slots[1].world
    assert _objs(tr.slots[0].world)[0].object_id == CANONICAL_FIRST_OBJECT_ID


def test_legacy_restore_empty_objects():
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    snap = rt.snapshot()
    assert "resource_objects" not in (snap.get("world") or {})
    rest = PhysicalSystemRuntime.restore(deepcopy(snap))
    assert _objs(rest.world) == []
    rest2 = PhysicalSystemRuntime.restore(deepcopy(rest.snapshot()))
    assert _objs(rest2.world) == []
    phase0 = PhysicalSystemRuntime(seed=SEED, config=acanthostega_config())
    s0 = phase0.snapshot()
    s0["world"].pop("resource_objects", None)
    r0 = PhysicalSystemRuntime.restore(deepcopy(s0))
    assert _objs(r0.world) == []


def test_agent_observation_excludes_object():
    cfg = acanthostega_materials_config()
    rt = PhysicalSystemRuntime(seed=SEED, config=cfg)
    obs = rt.agent_observation()
    blob = repr(obs)
    assert "resource-000001" not in blob
    assert "resource_objects" not in blob
    assert "component_0" not in blob
    assert audit_cognition_payload(obs) == []
    frag = accessible_observation(
        world=rt.world,
        body=rt.body,
        internal=rt.internal,
        planet_config=rt.config.planet,
        body_config=rt.config.body,
        include_signal_fields=True,
    )
    assert "resource_objects" not in frag
    assert all("object_id" not in k for k in frag)


def test_observer_and_analyzer_do_not_mix_ab():
    s = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_ACANTHOSTEGA_MATERIALS,
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
    })
    ident = s.runtime.model_identity()
    assert ident["public_preset"] == PUBLIC_PRESET_MATERIALS
    assert ident["physical_resource_objects"] is True
    assert ident["grasp_release_implemented"] is False
    assert ident["agent_resource_perception_implemented"] is False
    assert ident["material_conversion_implemented"] is False
    assert ident["lifecycle_implemented"] is False
    hdr = header_info(s.runtime, status="PAUSED", mode="LIVE", target_tick=None)
    assert hdr["physical_resource_objects"] is True
    ids = {m["id"] for m in (s.runtime.mechanisms().get("mechanisms") or [])}
    assert PHYSICAL_RESOURCE_OBJECTS in ids
    wf = world_frame(s.runtime, max_side=32, detail="full")
    assert len(wf["resource_objects"]) == 1
    assert wf["resource_objects"][0]["researcher_only"] is True
    assert wf["resource_objects"][0]["agent_accessible"] is False
    slot = s.runtime.slots[0]
    body_a = float(_resource_sum(slot.body, "R_A_site") or 0.0)
    assert body_a != float(wf["resource_objects"][0]["mass"]) or body_a == 0.0

    s2 = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s2.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PRESET_BETA31,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    ids2 = {m["id"] for m in (s2.runtime.mechanisms().get("mechanisms") or [])}
    assert PHYSICAL_RESOURCE_OBJECTS not in ids2
    wf2 = world_frame(s2.runtime, max_side=16, detail="full")
    assert wf2["resource_objects"] == []

    s3 = ObserverSession(SessionConfig(seed=17, buffer_capacity=8))
    s3.apply_experiment({
        "seed": 17,
        "load_preset": True,
        "public_preset": PUBLIC_PRESET_GENTLE,
        "world": {"width": 16, "height": 16, "boundary_mode": "WRAP_PERIODIC"},
    })
    cfg = s3.runtime.slots[0].config if hasattr(s3.runtime, "slots") else s3.runtime.config
    assert profile_is_active(cfg)
    assert objects_is_active(cfg) is False
    assert len(_objs(s3.runtime.world)) == 0
