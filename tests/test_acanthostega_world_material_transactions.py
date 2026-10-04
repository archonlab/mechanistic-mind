"""Atomic COMBINE and deposition transactions. Legacy physical outcomes stay."""
from __future__ import annotations

from copy import deepcopy

import mechanistic_mind.physical_system.material_composition as material_composition
from mechanistic_mind.model.acanthostega import (
    acanthostega_surface_optical_config,
    acanthostega_world_material_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA,
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
    PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
    PRESET_BETA31,
    beta31_mechanism_map,
    canonical_fingerprint,
    preset_canonical,
)
from mechanistic_mind.physical_system.explicit_surface_deposition import apply_explicit_surface_deposition
from mechanistic_mind.physical_system.material_composition import merge_held_materials
from mechanistic_mind.physical_system.mechanism_registry import set_mechanism
from mechanistic_mind.physical_system.near_field_exteroception import sample_near_field
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.passive_material_properties import derive_effective_properties
from mechanistic_mind.physical_system.physical_manipulator import (
    held_object_for_holder,
    resolve_shared_world_manipulators,
)
from mechanistic_mind.physical_system.physical_surface_optical_coating import (
    OPTICAL_VARIANT_A,
    OPTICAL_VARIANT_B,
)
from mechanistic_mind.physical_system.resource_objects import (
    PHYSICAL_STATE_HELD,
    MaterialComponent,
    ResourceObject,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.surface_affinity_traction import traction_multiplier
from mechanistic_mind.physical_system.world_material_transaction import (
    MECHANISM_ID,
    allocate_transaction_id,
    commit_material_transaction,
    plan_combine,
    plan_deposition,
    world_material_transactions_is_active,
)
from mechanistic_mind.scientific_v3.world_material_summary import format_world_material_section

FROZEN_BETA31_FP_SEED17 = "1621ef2c154864d1"


def _held(oid, optical, component, qty, hand, body="agent_0"):
    return ResourceObject(
        object_id=oid, x=10.2, y=10.2, mass=qty, quantity=qty,
        composition=(MaterialComponent(component, qty),),
        physical_state=PHYSICAL_STATE_HELD,
        holder_body_id=body,
        manipulator_id=hand,
        optical_response=optical,
    )


def _pair(cfg):
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    left = _held("resource-L", OPTICAL_VARIANT_A, "component_a", 1.0, "LEFT")
    right = _held("resource-R", OPTICAL_VARIANT_B, "component_b", 3.0, "RIGHT")
    rt.world.resource_objects = [left, right]
    rt.technical_id = "agent_0"
    return rt, left, right


def _source(cfg, qty=1.0):
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    rt.body.x, rt.body.y, rt.body.theta = 10.2, 10.2, 0.0
    src = _held("resource-S", OPTICAL_VARIANT_A, "component_a", qty, "LEFT")
    rt.world.resource_objects = [src]
    rt.technical_id = "agent_0"
    return rt, src


def _fingerprint(world):
    objects = []
    for obj in world.resource_objects:
        objects.append((
            obj.object_id, round(obj.mass, 12), round(obj.quantity, 12),
            tuple((c.component_id, round(c.amount, 12)) for c in obj.composition),
            tuple(round(v, 12) for v in obj.optical_response),
            obj.holder_body_id, obj.manipulator_id,
        ))
    deposits = []
    for key, dep in sorted((world.surface_material_deposits or {}).items()):
        deposits.append((
            key, round(dep.mass, 12), round(dep.quantity, 12),
            tuple((c.component_id, round(c.amount, 12)) for c in dep.composition),
            None if dep.optical_response is None else tuple(round(v, 12) for v in dep.optical_response),
        ))
    return objects, deposits


def test_preservation_and_previous_paths_stay_off():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    assert MECHANISM_ID not in beta31_mechanism_map()
    for name in (
        PRESET_ACANTHOSTEGA, PRESET_ACANTHOSTEGA_GENTLE, PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
        PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
    ):
        assert MECHANISM_ID not in preset_canonical(name, seed=17)["mechanisms"]
    fresh = preset_canonical("ACANTHOSTEGA_PHASE_B_WORLD_MATERIAL_TRANSACTIONS", seed=17)
    assert fresh["mechanisms"][MECHANISM_ID] is True
    assert fresh["mechanisms"]["physical_surface_optical_coating"] is True
    assert world_material_transactions_is_active(acanthostega_surface_optical_config()) is False
    assert world_material_transactions_is_active(acanthostega_world_material_config()) is True
    tik = tiktaalik_config()
    set_mechanism(tik, MECHANISM_ID, True)
    assert world_material_transactions_is_active(tik) is False
    snap = PhysicalSystemRuntime(seed=17, config=tiktaalik_config()).snapshot()
    assert "world_material_transactions" not in snap["config"]
    assert "material_transaction_sequence" not in snap["world"]
    assert traction_multiplier(0.75) == 1.2


def test_invalid_plan_and_exception_leave_state_unchanged():
    rt, left, right = _pair(acanthostega_world_material_config())
    before = _fingerprint(rt.world)
    plan = plan_combine(
        world=rt.world, config=rt.config, body_id="agent_0", left=left, right=right,
        confirmed_contact=False, tick=1,
    )
    commit_material_transaction(rt.world, plan)
    assert _fingerprint(rt.world) == before
    plan = plan_combine(
        world=rt.world, config=rt.config, body_id="agent_0", left=left, right=right,
        confirmed_contact=True, tick=2,
    )
    original = material_composition.merge_held_materials
    def explode(**_kwargs):
        raise RuntimeError("candidate failed")
    material_composition.merge_held_materials = explode
    try:
        receipt = commit_material_transaction(rt.world, plan)["receipt"]
    finally:
        material_composition.merge_held_materials = original
    assert receipt["status"] == "REJECTED"
    assert receipt["rejection_reason"] == "RuntimeError"
    assert _fingerprint(rt.world) == before


def test_commit_once_stable_ids_restore_and_stale_revision():
    rt, left, right = _pair(acanthostega_world_material_config())
    first = allocate_transaction_id(rt.world, 5)
    second = allocate_transaction_id(rt.world, 5)
    assert first == "material-tx-000000005-0000"
    assert second == "material-tx-000000005-0001"
    rt.world.material_transaction_sequence = 0
    plan = plan_combine(
        world=rt.world, config=rt.config, body_id="agent_0", left=left, right=right,
        confirmed_contact=True, tick=7,
    )
    committed = commit_material_transaction(rt.world, plan)
    assert committed["receipt"]["status"] == "COMMITTED"
    mass = left.mass
    again = commit_material_transaction(rt.world, plan)
    assert again["receipt"]["status"] == "REJECTED"
    assert again["receipt"]["rejection_reason"] == "ALREADY_COMMITTED"
    assert left.mass == mass
    snap = deepcopy(rt.snapshot())
    restored = PhysicalSystemRuntime.restore(snap)
    assert int(restored.world.material_transaction_sequence) == int(rt.world.material_transaction_sequence)
    nxt = allocate_transaction_id(restored.world, 8)
    assert nxt != plan["transaction_id"]
    assert nxt.endswith("0001") or int(nxt.rsplit("-", 1)[-1]) == int(rt.world.material_transaction_sequence)
    stale_rt, stale_left, stale_right = _pair(acanthostega_world_material_config())
    stale = plan_combine(
        world=stale_rt.world, config=stale_rt.config, body_id="agent_0",
        left=stale_left, right=stale_right, confirmed_contact=True, tick=1,
    )
    stale_left.material_revision = 4
    rejected = commit_material_transaction(stale_rt.world, stale)
    assert rejected["receipt"]["status"] == "REJECTED"
    assert str(rejected["receipt"]["rejection_reason"]).startswith("stale")
    assert len(stale_rt.world.resource_objects) == 2
    for _ in range(20):
        rejected_plan = plan_combine(
            world=rt.world, config=rt.config, body_id="agent_0", left=left, right=right,
            confirmed_contact=False, tick=9,
        )
        commit_material_transaction(rt.world, rejected_plan)
    assert len(rt.world.material_transaction_history) <= 16
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    assert "transaction_id" not in repr(obs)
    assert "material_revision" not in repr(obs)


def test_combine_matches_legacy_and_conserves():
    legacy_rt, left, right = _pair(acanthostega_surface_optical_config())
    tx_rt, tx_left, tx_right = _pair(acanthostega_world_material_config())
    legacy = merge_held_materials(
        world=legacy_rt.world, config=legacy_rt.config, body_id="agent_0",
        left=left, right=right, confirmed_contact=True, tick=3,
    )
    plan = plan_combine(
        world=tx_rt.world, config=tx_rt.config, body_id="agent_0",
        left=tx_left, right=tx_right, confirmed_contact=True, tick=3,
    )
    receipt = commit_material_transaction(tx_rt.world, plan)["receipt"]
    assert legacy["outcome"] == "MERGE_COMMITTED"
    assert receipt["status"] == "COMMITTED"
    assert [obj.object_id for obj in legacy_rt.world.resource_objects] == ["resource-L"]
    assert [obj.object_id for obj in tx_rt.world.resource_objects] == ["resource-L"]
    assert held_object_for_holder(tx_rt.world, "agent_0", "RIGHT") is None
    assert held_object_for_holder(tx_rt.world, "agent_0", "LEFT").object_id == "resource-L"
    assert abs(tx_left.mass - left.mass) < 1e-12
    assert abs(tx_left.quantity - left.quantity) < 1e-12
    assert tuple((c.component_id, c.amount) for c in tx_left.composition) == tuple(
        (c.component_id, c.amount) for c in left.composition
    )
    assert tx_left.optical_response == left.optical_response
    assert receipt["conservation"]["mass"]["verified"] is True
    assert receipt["conservation"]["quantity"]["verified"] is True
    assert receipt["conservation"]["components"]["verified"] is True
    assert receipt["optical_derivation"]["verified"] is True
    derived = derive_effective_properties(tx_left.composition)
    assert abs(derived["surface_affinity"] - receipt["property_derivation"]["surface_affinity"]) < 1e-12
    assert receipt["recipe_match"] is False
    assert "material_transformations" not in tx_left.provenance


def test_deposition_matches_legacy_including_depletion_and_rejection():
    legacy_rt, legacy_src = _source(acanthostega_surface_optical_config())
    tx_rt, tx_src = _source(acanthostega_world_material_config())
    legacy = apply_explicit_surface_deposition(
        world=legacy_rt.world, config=legacy_rt.config, body=legacy_rt.body, body_id="agent_0",
        command_requested=True, held_object_id_at_tick_start="resource-S", tick=2, runtime=legacy_rt,
    )
    plan = plan_deposition(
        world=tx_rt.world, config=tx_rt.config, body=tx_rt.body, body_id="agent_0",
        held_object_id_at_tick_start="resource-S", tick=2, runtime=tx_rt,
    )
    receipt = commit_material_transaction(tx_rt.world, plan)["receipt"]
    assert legacy["committed"] is True
    assert receipt["status"] == "COMMITTED"
    assert abs(tx_src.quantity - legacy_src.quantity) < 1e-12
    legacy_dep = next(iter(legacy_rt.world.surface_material_deposits.values()))
    tx_dep = next(iter(tx_rt.world.surface_material_deposits.values()))
    assert abs(tx_dep.quantity - legacy_dep.quantity) < 1e-12
    assert abs(tx_dep.mass - legacy_dep.mass) < 1e-12
    assert tx_dep.optical_response == legacy_dep.optical_response
    assert receipt["conservation"]["components"]["verified"] is True
    legacy_view = sample_near_field(world=legacy_rt.world, body=legacy_rt.body, cfg=legacy_rt.config.near_field_exteroception)
    tx_view = sample_near_field(world=tx_rt.world, body=tx_rt.body, cfg=tx_rt.config.near_field_exteroception)
    for key, value in legacy_view["surface_fragments"].items():
        assert abs(float(value) - float(tx_view["surface_fragments"][key])) < 1e-9
    # existing deposit updates atomically
    second = plan_deposition(
        world=tx_rt.world, config=tx_rt.config, body=tx_rt.body, body_id="agent_0",
        held_object_id_at_tick_start="resource-S", tick=3, runtime=tx_rt,
    )
    before_qty = tx_src.quantity + tx_dep.quantity
    updated = commit_material_transaction(tx_rt.world, second)["receipt"]
    assert updated["status"] == "COMMITTED"
    assert abs((tx_src.quantity + next(iter(tx_rt.world.surface_material_deposits.values())).quantity) - before_qty) < 1e-9
    # depleted source frees the hand
    small_rt, small = _source(acanthostega_world_material_config(), qty=0.05)
    depleted = plan_deposition(
        world=small_rt.world, config=small_rt.config, body=small_rt.body, body_id="agent_0",
        held_object_id_at_tick_start="resource-S", tick=4, runtime=small_rt,
    )
    dep_receipt = commit_material_transaction(small_rt.world, depleted)["receipt"]
    assert dep_receipt["status"] == "COMMITTED"
    assert held_object_for_holder(small_rt.world, "agent_0", "LEFT") is None
    assert small.holder_body_id is None
    # rejected deposition creates nothing
    empty_rt, _empty = _source(acanthostega_world_material_config())
    rejected = plan_deposition(
        world=empty_rt.world, config=empty_rt.config, body=empty_rt.body, body_id="agent_0",
        held_object_id_at_tick_start="other-object", tick=5, runtime=empty_rt,
    )
    commit_material_transaction(empty_rt.world, rejected)
    assert empty_rt.world.surface_material_deposits == {}


def test_independent_same_tick_transactions_both_commit():
    first = PhysicalSystemRuntime(seed=17, config=acanthostega_world_material_config())
    second = PhysicalSystemRuntime(seed=17, config=acanthostega_world_material_config())
    second.world = first.world
    first.technical_id = "agent_0"
    second.technical_id = "agent_1"
    first.body.x, first.body.y = 10.2, 10.2
    second.body.x, second.body.y = 14.2, 10.2
    first.world.resource_objects = [
        _held("resource-A", OPTICAL_VARIANT_A, "component_a", 1.0, "LEFT", "agent_0"),
        _held("resource-B", OPTICAL_VARIANT_B, "component_b", 1.0, "LEFT", "agent_1"),
    ]
    for rt in (first, second):
        rt.last_motor_output = {"apply_to_surface": True}
        rt.last_selected_action = "APPLY_TO_SURFACE"
        rt.structured_events = type("Events", (), {"emit": staticmethod(lambda *args, **kwargs: None)})()
    resolve_shared_world_manipulators([second, first], first.world, tick=6)
    assert len(first.world.surface_material_deposits) == 2
    committed = [row for row in first.world.material_transaction_history if row.get("status") == "COMMITTED"]
    assert {row["actor_body_id"] for row in committed} == {"agent_0", "agent_1"}


def test_same_tick_conflict_is_independent_of_runtime_order():
    def run(order):
        first = PhysicalSystemRuntime(seed=17, config=acanthostega_world_material_config())
        second = PhysicalSystemRuntime(seed=17, config=acanthostega_world_material_config())
        second.world = first.world
        first.technical_id = "agent_0"
        second.technical_id = "agent_1"
        first.body.x = second.body.x = 10.2
        first.body.y = second.body.y = 10.2
        first.body.theta = second.body.theta = 0.0
        first.world.resource_objects = [
            _held("resource-A", OPTICAL_VARIANT_A, "component_a", 1.0, "LEFT", "agent_0"),
            _held("resource-B", OPTICAL_VARIANT_B, "component_b", 1.0, "LEFT", "agent_1"),
        ]
        for rt in (first, second):
            rt.last_motor_output = {"apply_to_surface": True}
            rt.last_selected_action = "APPLY_TO_SURFACE"
            rt.structured_events = type("Events", (), {"emit": staticmethod(lambda *args, **kwargs: None)})()
        runtimes = [first, second] if order == "forward" else [second, first]
        resolve_shared_world_manipulators(runtimes, first.world, tick=6)
        deposit = next(iter(first.world.surface_material_deposits.values()))
        actors = [
            row.get("actor_body_id")
            for row in first.world.material_transaction_history
            if row.get("status") == "COMMITTED"
        ]
        return round(deposit.quantity, 12), actors, [
            row.get("status") for row in first.world.material_transaction_history
        ]
    forward = run("forward")
    reverse = run("reverse")
    assert forward[0] == reverse[0] == 0.1
    assert forward[1] == reverse[1] == ["agent_0"]
    assert "REJECTED" in forward[2]
    text = format_world_material_section({
        "committed_count": 1,
        "rejected_count": 1,
        "operation_counts": {"APPLY_TO_SURFACE": 2},
        "stale_conflicts": 1,
        "residual_max_abs": 0.0,
        "mass_conservation": "VERIFIED",
        "OBSERVED": ["transaction_receipt"],
        "VERIFIED": ["mass", "quantity", "components"],
        "NOT_ESTABLISHED": ["recipe", "excavation"],
    })
    assert "WORLD MATERIAL TRANSACTIONS" in text
    assert "RECIPE = NOT_ESTABLISHED" in text
