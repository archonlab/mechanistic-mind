"""Derived multi-content spatial index. Co-location is not collision."""
from __future__ import annotations

from mechanistic_mind.model.acanthostega import (
    acanthostega_multi_content_config,
    acanthostega_world_material_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
    PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
    PRESET_BETA31,
    beta31_mechanism_map,
    canonical_fingerprint,
    preset_canonical,
)
from mechanistic_mind.physical_system.explicit_surface_deposition import SurfaceMaterialDeposit
from mechanistic_mind.physical_system.material_composition import merge_held_materials
from mechanistic_mind.physical_system.mechanism_registry import set_mechanism
from mechanistic_mind.physical_system.near_field_exteroception import sample_near_field
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.resource_objects import (
    PHYSICAL_STATE_FREE_STATIC,
    PHYSICAL_STATE_HELD,
    MaterialComponent,
    ResourceObject,
    ensure_resource_object_state,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import (
    KIND_BODY,
    KIND_RESOURCE_OBJECT,
    KIND_SURFACE_DEPOSIT,
    MECHANISM_ID,
    checksum_of,
    contents_at_cell,
    multi_content_spatial_index_is_active,
    rebuild_from_world,
    reconcile_contents,
    validate_against_world,
    world_cell,
)
from mechanistic_mind.physical_system.world_material_transaction import (
    commit_material_transaction,
    plan_combine,
    plan_deposition,
)
from mechanistic_mind.ui.psy_observer_web.serialize import world_frame

FROZEN = "1621ef2c154864d1"


def _obj(oid, x, y, state=PHYSICAL_STATE_FREE_STATIC):
    return ResourceObject(
        object_id=oid, x=x, y=y, mass=1.0, quantity=1.0,
        composition=(MaterialComponent("component_a", 1.0),),
        physical_state=state,
        optical_response=(0.2, 0.3, 0.4),
    )


def _runtime():
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_multi_content_config())
    return rt


def test_preservation_and_mechanism_gate():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN
    assert MECHANISM_ID not in beta31_mechanism_map()
    for name in (PRESET_ACANTHOSTEGA_SURFACE_OPTICAL, PRESET_ACANTHOSTEGA_WORLD_MATERIAL):
        assert MECHANISM_ID not in preset_canonical(name, seed=17)["mechanisms"]
    fresh = preset_canonical("ACANTHOSTEGA_PHASE_B_MULTI_CONTENT_INDEX", seed=17)
    assert fresh["mechanisms"][MECHANISM_ID] is True
    assert fresh["mechanisms"]["world_material_transactions"] is True
    assert multi_content_spatial_index_is_active(acanthostega_world_material_config()) is False
    assert multi_content_spatial_index_is_active(acanthostega_multi_content_config()) is True
    tik = tiktaalik_config()
    set_mechanism(tik, MECHANISM_ID, True)
    assert multi_content_spatial_index_is_active(tik) is False
    snap = PhysicalSystemRuntime(seed=17, config=tiktaalik_config()).snapshot()
    assert "multi_content_spatial_index" not in snap["config"]
    assert "spatial_index_generation" not in snap["world"]
    bare = acanthostega_multi_content_config()
    bare.multi_content_spatial_index = type(bare.multi_content_spatial_index).from_dict(None)
    assert multi_content_spatial_index_is_active(bare) is False


def test_one_cell_holds_body_objects_and_deposit_in_canonical_order():
    rt = _runtime()
    rt.body.x, rt.body.y = 10.2, 10.2
    rt.world.resource_objects = [
        _obj("resource-000002", 10.4, 10.6),
        _obj("resource-000001", 10.1, 10.2),
    ]
    rt.world.surface_material_deposits = {
        "surface-deposit-C": SurfaceMaterialDeposit(
            deposit_id="surface-deposit-C", cell_x=10, cell_y=10,
            mass=0.1, quantity=0.1, composition=(MaterialComponent("component_a", 0.1),),
            provenance={}, created_tick=0, last_updated_tick=0,
        )
    }
    rebuild_from_world(rt.world, [("body-0", rt.body)], tick=1, reason="test", config=rt.config)
    reverse = list(rt.world.resource_objects)
    rt.world.resource_objects = list(reversed(reverse))
    rebuild_from_world(rt.world, [("body-0", rt.body)], tick=1, reason="reverse", config=rt.config)
    refs = contents_at_cell(rt.world, 10, 10)
    assert [ref.entity_id for ref in refs] == [
        "body-0", "resource-000001", "resource-000002", "surface-deposit-C",
    ]
    assert len({ref.entity_id for ref in refs}) == 4
    frame = world_frame(rt)
    cell = next(row for row in frame["spatial_cell_contents"] if row["cell_x"] == 10 and row["cell_y"] == 10)
    assert cell["physical_contents"] == 4
    assert frame["spatial_contents_note"] == "co-location is not collision. no vertical ordering."
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    assert "spatial_index" not in repr(obs)
    assert "resource-000001" not in repr(obs)


def test_membership_movement_wrap_and_held_body():
    rt = _runtime()
    obj = _obj("resource-000001", 10.1, 10.1)
    rt.world.resource_objects = [obj]
    rt.body.x, rt.body.y = 4.2, 4.2
    rebuild_from_world(rt.world, [("body-0", rt.body)], tick=1, reason="init", config=rt.config)
    generation = rt.world.spatial_contents.generation
    obj.x = 10.8
    reconcile_contents(rt.world, [("body-0", rt.body)], tick=2, reason="same_cell", config=rt.config)
    assert rt.world.spatial_contents.generation == generation
    assert contents_at_cell(rt.world, 10, 10)[0].entity_id == "resource-000001"
    obj.x = 11.1
    reconcile_contents(rt.world, [("body-0", rt.body)], tick=3, reason="cross_cell", config=rt.config)
    assert contents_at_cell(rt.world, 10, 10) == []
    assert contents_at_cell(rt.world, 11, 10)[0].entity_id == "resource-000001"
    obj.x, obj.y = -0.2, -0.4
    cell = world_cell(obj.x, obj.y, width=32, height=32)
    reconcile_contents(rt.world, [("body-0", rt.body)], tick=4, reason="wrap", config=rt.config)
    assert cell == (31, 31)
    assert contents_at_cell(rt.world, 31, 31)[0].entity_id == "resource-000001"
    obj.physical_state = PHYSICAL_STATE_HELD
    obj.holder_body_id = "agent_0"
    obj.x, obj.y = 6.2, 6.2
    rt.body.x, rt.body.y = 8.2, 3.1
    before = rt.world.spatial_contents.generation
    reconcile_contents(rt.world, [("body-0", rt.body)], tick=5, reason="held_and_body", config=rt.config)
    assert rt.world.spatial_contents.generation != before
    assert any(ref.entity_id == "resource-000001" for ref in contents_at_cell(rt.world, 6, 6))
    assert any(ref.entity_kind == KIND_BODY for ref in contents_at_cell(rt.world, 8, 3))
    rt.technical_id = "undercover"
    from mechanistic_mind.physical_system.spatial_contents import body_refs_for_runtime

    assert body_refs_for_runtime(rt)[0][0] == "body-0"


def test_transactions_restore_audit_and_vision():
    rt = _runtime()
    left = _obj("resource-L", 10.2, 10.2, PHYSICAL_STATE_HELD)
    right = _obj("resource-R", 10.3, 10.2, PHYSICAL_STATE_HELD)
    left.holder_body_id = right.holder_body_id = "agent_0"
    left.manipulator_id = "LEFT"
    right.manipulator_id = "RIGHT"
    rt.world.resource_objects = [left, right]
    rebuild_from_world(rt.world, [("body-0", rt.body)], tick=1, reason="init", config=rt.config)
    rejected = plan_combine(
        world=rt.world, config=rt.config, body_id="agent_0", left=left, right=right,
        confirmed_contact=False, tick=2,
    )
    before = checksum_of(rt.world.spatial_contents)
    commit_material_transaction(rt.world, rejected)
    assert checksum_of(rt.world.spatial_contents) == before
    plan = plan_combine(
        world=rt.world, config=rt.config, body_id="agent_0", left=left, right=right,
        confirmed_contact=True, tick=3,
    )
    commit_material_transaction(rt.world, plan)
    ids = [ref.entity_id for ref in contents_at_cell(rt.world, 10, 10)]
    assert "resource-L" in ids
    assert "resource-R" not in ids
    src = _obj("resource-S", rt.body.x, rt.body.y, PHYSICAL_STATE_HELD)
    src.holder_body_id = "agent_0"
    src.manipulator_id = "LEFT"
    rt.world.resource_objects = [src]
    rt.body.x, rt.body.y = 12.2, 12.2
    src.x, src.y = rt.body.x, rt.body.y
    rebuild_from_world(rt.world, [("body-0", rt.body)], tick=4, reason="source", config=rt.config)
    deposit_plan = plan_deposition(
        world=rt.world, config=rt.config, body=rt.body, body_id="agent_0",
        held_object_id_at_tick_start="resource-S", tick=5, runtime=rt,
    )
    commit_material_transaction(rt.world, deposit_plan)
    assert any(ref.entity_kind == KIND_SURFACE_DEPOSIT for ref in rt.world.spatial_contents.by_entity.values())
    stale = plan_deposition(
        world=rt.world, config=rt.config, body=rt.body, body_id="agent_0",
        held_object_id_at_tick_start="missing", tick=6, runtime=rt,
    )
    checksum = checksum_of(rt.world.spatial_contents)
    commit_material_transaction(rt.world, stale)
    assert checksum_of(rt.world.spatial_contents) == checksum
    pre = checksum_of(rt.world.spatial_contents)
    snap = rt.snapshot()
    src.x += 3
    reconcile_contents(rt.world, [("body-0", rt.body)], tick=7, reason="mutate", config=rt.config)
    restored = PhysicalSystemRuntime.restore(snap)
    assert checksum_of(restored.world.spatial_contents) == pre
    extra = list(restored.world.spatial_contents.by_entity.values())[0]
    restored.world.spatial_contents.by_cell.setdefault((0, 0), []).append(extra)
    report = validate_against_world(restored.world, [("body-0", restored.body)], tick=8, repair=False)
    assert report["mismatch_count"] > 0
    assert report["repaired"] is False
    repaired = validate_against_world(restored.world, [("body-0", restored.body)], tick=9, repair=True)
    assert repaired["repaired"] is True
    assert validate_against_world(restored.world, [("body-0", restored.body)], tick=10)["mismatch_count"] == 0
    for _ in range(20):
        src.x = (float(src.x) + 1.1) % 32
        reconcile_contents(rt.world, [("body-0", rt.body)], tick=11, reason="history", config=rt.config)
    assert len(rt.world.spatial_index_history) <= 16
    legacy = PhysicalSystemRuntime(seed=17, config=acanthostega_world_material_config())
    indexed = PhysicalSystemRuntime(seed=17, config=acanthostega_multi_content_config())
    for runtime in (legacy, indexed):
        runtime.body.x, runtime.body.y, runtime.body.theta = 8.0, 8.0, 0.2
        runtime.world.resource_objects = [_obj("resource-000001", 8.4, 8.2), _obj("resource-000002", 8.6, 8.3)]
    rebuild_from_world(indexed.world, [("body-0", indexed.body)], tick=1, reason="vision", config=indexed.config)
    left_view = sample_near_field(world=legacy.world, body=legacy.body, cfg=legacy.config.near_field_exteroception)
    right_view = sample_near_field(world=indexed.world, body=indexed.body, cfg=indexed.config.near_field_exteroception)
    for key, value in left_view["fragments"].items():
        assert abs(float(value) - float(right_view["fragments"][key])) < 1e-9
    calls = {"n": 0}
    original = ensure_resource_object_state

    def counting(world):
        calls["n"] += 1
        return original(world)

    import mechanistic_mind.physical_system.resource_objects as resource_objects
    resource_objects.ensure_resource_object_state = counting
    try:
        contents_at_cell(indexed.world, 8, 8)
    finally:
        resource_objects.ensure_resource_object_state = original
    assert calls["n"] == 0
    assert merge_held_materials.__name__ == "merge_held_materials"
