"""Held deposition radius shrink transaction V1 — focused deterministic tests."""
from __future__ import annotations

from copy import deepcopy

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_held_deposition_radius_shrink_transaction_config,
    )

    cfg = acanthostega_held_deposition_radius_shrink_transaction_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _parent_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_held_combine_radius_resize_transaction_config,
    )

    cfg = acanthostega_held_combine_radius_resize_transaction_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _stamp(obj):
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        PROFILE_VERSION,
    )

    prov = dict(getattr(obj, "provenance", None) or {})
    prov["size_geometry_profile"] = PROFILE_VERSION
    obj.provenance = prov
    return obj


def _held_source(qty=0.25, *, stamp=True, x=10.0, y=10.0, z=0.5, optical_radius=0.25):
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        derive_detached_material_collision_radius,
    )
    from mechanistic_mind.physical_system.resource_objects import (
        PHYSICAL_STATE_HELD,
        MaterialComponent,
        ResourceObject,
    )

    der = derive_detached_material_collision_radius(float(qty))
    r = float(der.final_radius)
    obj = ResourceObject(
        object_id="resource-S",
        x=float(x),
        y=float(y),
        z=float(z),
        mass=float(qty),
        quantity=float(qty),
        composition=(MaterialComponent("component_a", float(qty)),),
        physical_state=PHYSICAL_STATE_HELD,
        holder_body_id="agent_0",
        manipulator_id="LEFT",
        collision_radius=r,
        vertical_half_extent=r,
        optical_radius=float(optical_radius),
        optical_response=(0.1, 0.2, 0.3),
    )
    if stamp:
        _stamp(obj)
    else:
        obj.collision_radius = 0.25
        obj.vertical_half_extent = 0.25
    return obj


def _rt(cfg=None, *, qty=0.25, stamp=True, work=10.0):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=17, config=cfg or _cfg())
    rt.body.x, rt.body.y, rt.body.theta = 10.0, 10.0, 0.0
    rt.body.mechanical_work_reservoir = float(work)
    rt.technical_id = "agent_0"
    src = _held_source(qty, stamp=stamp, x=10.0, y=10.0)
    rt.world.resource_objects = [src]
    rt.world.detached_placement_body_refs = [("agent_0", rt.body)]
    return rt, src


def _deposit(rt, src, *, tick=1):
    from mechanistic_mind.physical_system.world_material_transaction import (
        commit_material_transaction,
        plan_deposition,
    )

    plan = plan_deposition(
        world=rt.world,
        config=rt.config,
        body=rt.body,
        body_id="agent_0",
        held_object_id_at_tick_start=str(src.object_id),
        tick=tick,
        runtime=rt,
    )
    out = commit_material_transaction(rt.world, plan)
    _tick()
    return plan, out


def test_preset_identity_inheritance_matrix():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION,
        PUBLIC_PRESET_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION,
        acanthostega_held_deposition_radius_shrink_transaction_config,
        acanthostega_held_combine_radius_resize_transaction_config,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import (
        MECHANISM_ID,
        PROFILE_VERSION,
        held_deposition_radius_shrink_transaction_is_active,
    )
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        held_combine_radius_resize_transaction_is_active,
    )
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        detached_material_amount_scaled_collision_radius_is_active,
    )
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        event_driven_crowded_placement_retry_contract_is_active,
    )
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        active_locomotion_traction_vs_sliding_friction_is_active,
    )
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        repeated_conservative_surface_column_separation_is_active,
    )
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        bnlt_move_breakaway_locomotion_repair_is_active,
    )
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION,
        normalize_preset_name,
        preset_canonical,
        canonical_fingerprint,
        PRESET_BETA31,
    )

    child = acanthostega_held_deposition_radius_shrink_transaction_config()
    parent = acanthostega_held_combine_radius_resize_transaction_config()
    assert child.public_preset == PUBLIC_PRESET_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
    assert parent.public_preset == PUBLIC_PRESET_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
    assert held_deposition_radius_shrink_transaction_is_active(child) is True
    assert held_deposition_radius_shrink_transaction_is_active(parent) is False
    assert held_combine_radius_resize_transaction_is_active(child) is True
    assert detached_material_amount_scaled_collision_radius_is_active(child) is True
    assert event_driven_crowded_placement_retry_contract_is_active(child) is True
    assert active_locomotion_traction_vs_sliding_friction_is_active(child) is True
    assert repeated_conservative_surface_column_separation_is_active(child) is True
    assert bnlt_move_breakaway_locomotion_repair_is_active(child) is True
    assert held_deposition_radius_shrink_transaction_is_active(tiktaalik_config()) is False
    assert PROFILE_VERSION == "HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_V1"
    assert MECHANISM_ID == "held_deposition_radius_shrink_transaction"
    assert (
        normalize_preset_name("HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION_V1")
        == PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_HELD_DEPOSITION_RADIUS_SHRINK_TRANSACTION)
    assert canon["model_line"] == "ACANTHOSTEGA"
    assert canon["parent"] == PUBLIC_PRESET_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
    assert canon["mechanisms"][MECHANISM_ID] is True
    assert canon["mechanisms"]["held_combine_radius_resize_transaction"] is True
    assert child.model_line == "ACANTHOSTEGA"
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == "1621ef2c154864d1"


def test_partial_shrink_atomic_anchor_energy_conservation():
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        derive_detached_material_collision_radius,
    )
    from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import (
        CLS_COMMITTED,
        PE_LEDGER,
        gravity_g,
    )

    rt, src = _rt(qty=0.25, stamp=True, work=10.0)
    r_before = float(src.collision_radius)
    z_before = float(src.z)
    x_before, y_before = float(src.x), float(src.y)
    optical_before = float(src.optical_radius)
    q_before = float(src.quantity)
    mass_before = float(src.mass)
    w0 = float(rt.body.mechanical_work_reservoir)
    expected_q = q_before - 0.10
    expected_r = float(derive_detached_material_collision_radius(expected_q).final_radius)
    expected_mass = mass_before * (expected_q / q_before)
    expected_pe = expected_mass * gravity_g(rt.config) * (r_before - expected_r)

    plan, out = _deposit(rt, src, tick=1)
    assert plan["status"] == "PLANNED"
    geo = plan["held_deposition_geometry_shrink"]
    assert geo["geometry_eligible"] is True
    assert abs(float(geo["quantity_after"]) - expected_q) < 1e-12
    assert abs(float(geo["radius_proposed"]) - expected_r) < 1e-12
    receipt = out["receipt"]
    assert receipt["status"] == "COMMITTED"
    shrink = receipt["held_deposition_geometry_shrink"]
    assert shrink["resize_classification"] == CLS_COMMITTED
    assert shrink["energy_classification"] == PE_LEDGER
    assert shrink["released_pe_credited_to_agent"] is False
    assert shrink["global_energy_conservation_claimed"] is False
    assert shrink["impact_sound_emitted"] is False
    assert shrink["impulse_emitted"] is False
    assert abs(float(shrink["released_pe_magnitude"]) - expected_pe) < 1e-12
    assert abs(float(rt.body.mechanical_work_reservoir) - w0) < 1e-12
    assert len(rt.world.resource_objects) == 1
    surv = rt.world.resource_objects[0]
    assert surv.object_id == "resource-S"
    assert abs(float(surv.quantity) - expected_q) < 1e-12
    assert abs(float(surv.mass) - expected_mass) < 1e-12
    assert abs(float(surv.collision_radius) - expected_r) < 1e-12
    assert abs(float(surv.vertical_half_extent) - expected_r) < 1e-12
    assert abs(float(surv.z) - z_before) < 1e-12
    assert abs(float(surv.x) - x_before) < 1e-12
    assert abs(float(surv.y) - y_before) < 1e-12
    assert abs(float(surv.optical_radius) - optical_before) < 1e-12
    assert surv.manipulator_id == "LEFT"
    assert surv.holder_body_id == "agent_0"
    assert abs((z_before + expected_r) - (z_before + float(surv.collision_radius))) < 1e-12
    assert abs(receipt["conservation"]["quantity"]["residual"]) < 1e-9
    assert abs(receipt["conservation"]["mass"]["residual"]) < 1e-9
    assert rt.world.surface_material_deposits
    # sticky radius
    rt.step(1)
    _tick()
    assert abs(float(surv.collision_radius) - expected_r) < 1e-12


def test_parent_preset_does_not_shrink_on_deposit():
    rt, src = _rt(cfg=_parent_cfg(), qty=0.25, stamp=True)
    r0 = float(src.collision_radius)
    plan, out = _deposit(rt, src, tick=1)
    assert "held_deposition_geometry_shrink" not in plan or plan.get("held_deposition_geometry_shrink") is None
    assert out["receipt"]["status"] == "COMMITTED"
    assert abs(float(rt.world.resource_objects[0].collision_radius) - r0) < 1e-12
    assert abs(float(rt.world.resource_objects[0].quantity) - 0.15) < 1e-12


def test_fixed_legacy_keeps_radius():
    from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import CLS_FIXED

    rt, src = _rt(qty=0.25, stamp=False)
    r0 = float(src.collision_radius)
    plan, out = _deposit(rt, src, tick=1)
    assert plan["held_deposition_geometry_shrink"]["resize_classification"] == CLS_FIXED
    assert out["receipt"]["status"] == "COMMITTED"
    assert abs(float(rt.world.resource_objects[0].collision_radius) - r0) < 1e-12


def test_full_exhaustion_removes_no_rmin_survivor():
    from mechanistic_mind.physical_system.held_deposition_radius_shrink_transaction import CLS_EXHAUSTED

    rt, src = _rt(qty=0.05, stamp=True)
    plan, out = _deposit(rt, src, tick=1)
    assert plan["held_deposition_geometry_shrink"]["resize_classification"] == CLS_EXHAUSTED
    assert plan["held_deposition_geometry_shrink"]["depleted"] is True
    assert out["receipt"]["status"] == "COMMITTED"
    assert out["receipt"]["held_deposition_geometry_shrink"]["resize_classification"] == CLS_EXHAUSTED
    assert len(rt.world.resource_objects) == 0
    assert out["receipt"]["attachment_changes"][0]["freed"] is True
    assert out["receipt"]["attachment_changes"][0]["manipulator_id"] == "LEFT"
    assert not any(
        abs(float(getattr(o, "collision_radius", 0) or 0) - 0.08) < 1e-12
        for o in rt.world.resource_objects
    )


def test_snapshot_restore_no_replay():
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        derive_detached_material_collision_radius,
    )

    rt, src = _rt(qty=0.25, stamp=True, work=10.0)
    expected_r = float(derive_detached_material_collision_radius(0.15).final_radius)
    w0 = float(rt.body.mechanical_work_reservoir)
    plan, out = _deposit(rt, src, tick=1)
    assert out["receipt"]["status"] == "COMMITTED"
    snap = deepcopy(rt.snapshot())
    restored = PhysicalSystemRuntime.restore(snap)
    _tick()
    assert len(restored.world.resource_objects) == 1
    surv = restored.world.resource_objects[0]
    assert abs(float(surv.collision_radius) - expected_r) < 1e-12
    assert abs(float(surv.vertical_half_extent) - expected_r) < 1e-12
    assert abs(float(surv.quantity) - 0.15) < 1e-12
    assert restored.world.surface_material_deposits
    assert abs(float(restored.body.mechanical_work_reservoir) - w0) < 1e-12


def test_cognition_privacy_and_no_impulse_sound_claims():
    from mechanistic_mind.physical_system.observation import audit_cognition_payload

    rt, src = _rt(qty=0.25, stamp=True)
    _deposit(rt, src, tick=1)
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    blob = repr(obs)
    assert "HELD_DEPOSITION_GEOMETRY_SHRINK" not in blob
    assert "released_pe_magnitude" not in blob
    assert "SURVIVOR_GEOMETRY_DISSIPATED_NON_RECOVERABLE" not in blob


def test_tick_budget():
    assert TICKS["n"] <= 200
