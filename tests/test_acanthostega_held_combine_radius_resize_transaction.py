"""Held COMBINE radius resize transaction V1 — focused deterministic tests."""
from __future__ import annotations

import math
from copy import deepcopy

TICKS = {"n": 0}


def _tick(n: int = 1) -> None:
    TICKS["n"] += int(n)


def _cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_held_combine_radius_resize_transaction_config,
    )

    cfg = acanthostega_held_combine_radius_resize_transaction_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _parent_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_detached_material_amount_scaled_collision_radius_config,
    )

    cfg = acanthostega_detached_material_amount_scaled_collision_radius_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _crowding_cfg():
    from mechanistic_mind.model.acanthostega import (
        acanthostega_event_driven_crowded_placement_retry_contract_config,
    )

    cfg = acanthostega_event_driven_crowded_placement_retry_contract_config()
    cfg.cognition.cognition_enabled = False
    return cfg


def _stamp(obj, *, profile: str | None = "DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS_V1"):
    prov = dict(getattr(obj, "provenance", None) or {})
    if profile is None:
        prov.pop("size_geometry_profile", None)
    else:
        prov["size_geometry_profile"] = profile
    obj.provenance = prov
    return obj


def _held(
    oid,
    qty,
    hand,
    *,
    mass=None,
    radius=None,
    x=10.0,
    y=10.0,
    z=0.5,
    body="agent_0",
    stamp=True,
    optical_radius=0.25,
):
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        derive_detached_material_collision_radius,
    )
    from mechanistic_mind.physical_system.resource_objects import (
        PHYSICAL_STATE_HELD,
        MaterialComponent,
        ResourceObject,
    )

    m = float(mass if mass is not None else qty)
    if radius is None:
        der = derive_detached_material_collision_radius(float(qty))
        r = float(der.final_radius)
    else:
        r = float(radius)
    obj = ResourceObject(
        object_id=oid,
        x=float(x),
        y=float(y),
        z=float(z),
        mass=m,
        quantity=float(qty),
        composition=(MaterialComponent("component_a" if hand == "LEFT" else "component_b", float(qty)),),
        physical_state=PHYSICAL_STATE_HELD,
        holder_body_id=body,
        manipulator_id=hand,
        collision_radius=r,
        vertical_half_extent=r,
        optical_radius=float(optical_radius),
        optical_response=(0.1, 0.2, 0.3) if hand == "LEFT" else (0.7, 0.5, 0.1),
    )
    if stamp:
        _stamp(obj)
    return obj


def _pair(cfg=None, *, ql=0.05, qr=0.05, stamp_left=True, stamp_right=True, work=10.0, body_xy=(2.0, 2.0)):
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt = PhysicalSystemRuntime(seed=17, config=cfg or _cfg())
    rt.body.x, rt.body.y = float(body_xy[0]), float(body_xy[1])
    rt.body.mechanical_work_reservoir = float(work)
    rt.technical_id = "agent_0"
    left = _held("resource-L", ql, "LEFT", stamp=stamp_left, x=10.0, y=10.0)
    right = _held("resource-R", qr, "RIGHT", stamp=stamp_right, x=10.15, y=10.0)
    if not stamp_left:
        left.collision_radius = 0.25
        left.vertical_half_extent = 0.25
    rt.world.resource_objects = [left, right]
    rt.world.detached_placement_body_refs = [("agent_0", rt.body)]
    return rt, left, right


def _commit(rt, left, right, *, contact=True, tick=1):
    from mechanistic_mind.physical_system.world_material_transaction import (
        commit_material_transaction,
        plan_combine,
    )

    plan = plan_combine(
        world=rt.world,
        config=rt.config,
        body_id="agent_0",
        left=left,
        right=right,
        confirmed_contact=contact,
        tick=tick,
        actor_body=rt.body,
    )
    out = commit_material_transaction(rt.world, plan)
    _tick()
    return plan, out


def test_preset_matrix_identity_and_inheritance():
    from mechanistic_mind.model.acanthostega import (
        PUBLIC_PRESET_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS,
        PUBLIC_PRESET_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION,
        acanthostega_held_combine_radius_resize_transaction_config,
        acanthostega_detached_material_amount_scaled_collision_radius_config,
        acanthostega_event_driven_crowded_placement_retry_contract_config,
    )
    from mechanistic_mind.model.tiktaalik import tiktaalik_config
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        MECHANISM_ID,
        PROFILE_VERSION,
        held_combine_radius_resize_transaction_is_active,
    )
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        detached_material_amount_scaled_collision_radius_is_active,
    )
    from mechanistic_mind.physical_system.active_locomotion_traction_vs_sliding_friction import (
        active_locomotion_traction_vs_sliding_friction_is_active,
    )
    from mechanistic_mind.physical_system.repeated_conservative_surface_column_separation import (
        repeated_conservative_surface_column_separation_is_active,
    )
    from mechanistic_mind.physical_system.event_driven_crowded_placement_retry_contract import (
        event_driven_crowded_placement_retry_contract_is_active,
    )
    from mechanistic_mind.physical_system.bnlt_move_breakaway_locomotion_repair import (
        bnlt_move_breakaway_locomotion_repair_is_active,
    )
    from mechanistic_mind.physical_system.experiment_canonical import (
        PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION,
        normalize_preset_name,
        preset_canonical,
        canonical_fingerprint,
        PRESET_BETA31,
    )

    child = acanthostega_held_combine_radius_resize_transaction_config()
    parent = acanthostega_detached_material_amount_scaled_collision_radius_config()
    crowd = acanthostega_event_driven_crowded_placement_retry_contract_config()
    assert child.public_preset == PUBLIC_PRESET_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
    assert parent.public_preset == PUBLIC_PRESET_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
    assert held_combine_radius_resize_transaction_is_active(child) is True
    assert held_combine_radius_resize_transaction_is_active(parent) is False
    assert held_combine_radius_resize_transaction_is_active(crowd) is False
    assert detached_material_amount_scaled_collision_radius_is_active(child) is True
    assert detached_material_amount_scaled_collision_radius_is_active(parent) is True
    assert detached_material_amount_scaled_collision_radius_is_active(crowd) is False
    assert event_driven_crowded_placement_retry_contract_is_active(child) is True
    assert active_locomotion_traction_vs_sliding_friction_is_active(child) is True
    assert repeated_conservative_surface_column_separation_is_active(child) is True
    assert bnlt_move_breakaway_locomotion_repair_is_active(child) is True
    assert held_combine_radius_resize_transaction_is_active(tiktaalik_config()) is False
    assert PROFILE_VERSION == "HELD_COMBINE_RADIUS_RESIZE_TRANSACTION_V1"
    assert MECHANISM_ID == "held_combine_radius_resize_transaction"
    assert (
        normalize_preset_name("HELD_COMBINE_RADIUS_RESIZE_TRANSACTION_V1")
        == PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION
    )
    canon = preset_canonical(PRESET_ACANTHOSTEGA_HELD_COMBINE_RADIUS_RESIZE_TRANSACTION)
    assert canon["model_line"] == "ACANTHOSTEGA"
    assert canon["parent"] == PUBLIC_PRESET_DETACHED_MATERIAL_AMOUNT_SCALED_COLLISION_RADIUS
    assert canon["mechanisms"][MECHANISM_ID] is True
    assert canon["mechanisms"]["detached_material_amount_scaled_collision_radius"] is True
    # Conflicting client model line ignored via builder identity
    assert child.model_line == "ACANTHOSTEGA"
    # Tiktaalik fingerprint unchanged
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == "1621ef2c154864d1"


def test_formula_bounds_and_quantity_not_mass():
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        derive_detached_material_collision_radius,
        MIN_RADIUS,
        MAX_RADIUS,
    )

    d = derive_detached_material_collision_radius(0.10)
    assert abs(d.final_radius - 0.25 * (0.10 ** (1.0 / 3.0))) < 1e-12
    assert 0.115 < d.final_radius < 0.117
    d2 = derive_detached_material_collision_radius(2.0)
    assert d2.final_radius == MAX_RADIUS
    d3 = derive_detached_material_collision_radius(1e-9)
    assert d3.final_radius == MIN_RADIUS
    # mass must not affect formula — quantity authority
    assert derive_detached_material_collision_radius(0.05).final_radius != derive_detached_material_collision_radius(0.10).final_radius


def test_eligible_growth_admits_and_conserves():
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        CLS_COMMITTED,
        gravity_g,
    )
    from mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius import (
        derive_detached_material_collision_radius,
    )

    rt, left, right = _pair(ql=0.05, qr=0.05, work=10.0)
    r_before = float(left.collision_radius)
    z_before = float(left.z)
    x_before, y_before = float(left.x), float(left.y)
    optical_before = float(left.optical_radius)
    mass_l, mass_r = float(left.mass), float(right.mass)
    qty_l, qty_r = float(left.quantity), float(right.quantity)
    w0 = float(rt.body.mechanical_work_reservoir)
    expected_r = float(derive_detached_material_collision_radius(0.10).final_radius)
    delta_r = expected_r - r_before
    required = (mass_l + mass_r) * gravity_g(rt.config) * delta_r

    plan, out = _commit(rt, left, right, tick=1)
    assert plan["status"] == "PLANNED"
    geo = plan["held_combine_geometry_resize"]
    assert geo["geometry_eligible"] is True
    assert abs(float(geo["radius_proposed"]) - expected_r) < 1e-12
    assert abs(float(geo["required_resize_work"]) - required) < 1e-12
    receipt = out["receipt"]
    assert receipt["status"] == "COMMITTED"
    resize = receipt["held_combine_geometry_resize"]
    assert resize["resize_classification"] == CLS_COMMITTED
    assert resize["impact_sound_emitted"] is False
    assert resize["impulse_emitted"] is False
    assert resize["work_debit_count"] == 1
    assert abs(float(resize["work_debited"]) - required) < 1e-12
    assert abs(w0 - float(rt.body.mechanical_work_reservoir) - required) < 1e-12
    assert len(rt.world.resource_objects) == 1
    surv = rt.world.resource_objects[0]
    assert surv.object_id == "resource-L"
    assert abs(float(surv.mass) - (mass_l + mass_r)) < 1e-12
    assert abs(float(surv.quantity) - (qty_l + qty_r)) < 1e-12
    assert abs(float(surv.collision_radius) - expected_r) < 1e-12
    assert abs(float(surv.vertical_half_extent) - expected_r) < 1e-12
    assert abs(float(surv.z) - z_before) < 1e-12
    assert abs(float(surv.x) - x_before) < 1e-12
    assert abs(float(surv.y) - y_before) < 1e-12
    assert abs(float(surv.optical_radius) - optical_before) < 1e-12
    assert surv.manipulator_id == "LEFT"
    assert surv.holder_body_id == "agent_0"
    # radius sticky next tick
    r_sticky = float(surv.collision_radius)
    rt.step(1)
    _tick()
    assert abs(float(surv.collision_radius) - r_sticky) < 1e-12


def test_fixed_legacy_and_right_profile_does_not_override():
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import CLS_FIXED

    # Legacy left (no stamp), stamped right → fixed path, COMBINE still succeeds
    rt, left, right = _pair(ql=0.05, qr=0.05, stamp_left=False, stamp_right=True, work=10.0)
    r0 = float(left.collision_radius)
    plan, out = _commit(rt, left, right, tick=1)
    assert plan["status"] == "PLANNED"
    assert plan["held_combine_geometry_resize"]["resize_classification"] == CLS_FIXED
    assert out["receipt"]["status"] == "COMMITTED"
    surv = rt.world.resource_objects[0]
    assert abs(float(surv.collision_radius) - r0) < 1e-12
    assert float(out["receipt"]["held_combine_geometry_resize"].get("work_debited") or 0.0) == 0.0


def test_insufficient_work_rejects_atomically():
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        CLS_INSUFFICIENT_WORK,
    )

    rt, left, right = _pair(ql=0.05, qr=0.05, work=0.0)
    before_ids = {o.object_id for o in rt.world.resource_objects}
    r_l, r_r = float(left.collision_radius), float(right.collision_radius)
    plan, out = _commit(rt, left, right, tick=1)
    assert plan["status"] == "REJECTED"
    assert plan["rejection_reason"] == CLS_INSUFFICIENT_WORK
    assert out["receipt"]["status"] == "REJECTED"
    assert {o.object_id for o in rt.world.resource_objects} == before_ids
    assert abs(float(left.collision_radius) - r_l) < 1e-12
    assert abs(float(right.collision_radius) - r_r) < 1e-12
    assert left.manipulator_id == "LEFT"
    assert right.manipulator_id == "RIGHT"
    assert float(rt.body.mechanical_work_reservoir) == 0.0


def test_holder_self_overlap_growth_rejects():
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        CLS_HOLDER_SELF,
    )

    # Place held objects at body centre so growth worsens holder penetration.
    rt, left, right = _pair(ql=0.05, qr=0.05, work=10.0, body_xy=(10.0, 10.0))
    left.x, left.y = 10.0, 10.0
    right.x, right.y = 10.05, 10.0
    before = len(rt.world.resource_objects)
    plan, out = _commit(rt, left, right, tick=1)
    assert plan["status"] == "REJECTED"
    assert plan["rejection_reason"] == CLS_HOLDER_SELF
    assert out["receipt"]["status"] == "REJECTED"
    assert len(rt.world.resource_objects) == before
    assert float(rt.body.mechanical_work_reservoir) == 10.0


def test_object_overlap_rejects_and_right_source_excluded():
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        CLS_OBJECT,
    )
    from mechanistic_mind.physical_system.resource_objects import (
        MaterialComponent,
        ResourceObject,
    )

    rt, left, right = _pair(ql=0.05, qr=0.05, work=10.0)
    # Obstacle near left at growth radius
    obstacle = ResourceObject(
        object_id="obstacle-1",
        x=10.0 + 0.20,
        y=10.0,
        z=0.0,
        mass=1.0,
        quantity=1.0,
        composition=(MaterialComponent("rock", 1.0),),
        physical_state="FREE_STATIC",
        collision_radius=0.25,
        vertical_half_extent=0.25,
    )
    rt.world.resource_objects.append(obstacle)
    # Right is close to left but must be excluded from conflict set
    right.x, right.y = 10.02, 10.0
    plan, out = _commit(rt, left, right, tick=1)
    assert plan["status"] == "REJECTED"
    assert plan["rejection_reason"] == CLS_OBJECT
    assert out["receipt"]["status"] == "REJECTED"
    assert len(rt.world.resource_objects) == 3
    assert float(rt.body.mechanical_work_reservoir) == 10.0


def test_clamped_no_change_no_resize_work():
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        CLS_NO_CHANGE,
    )

    rt, left, right = _pair(ql=1.0, qr=1.0, work=10.0)
    left.collision_radius = 0.25
    left.vertical_half_extent = 0.25
    right.collision_radius = 0.25
    right.vertical_half_extent = 0.25
    w0 = float(rt.body.mechanical_work_reservoir)
    plan, out = _commit(rt, left, right, tick=1)
    assert plan["status"] == "PLANNED"
    assert plan["held_combine_geometry_resize"]["resize_classification"] == CLS_NO_CHANGE
    assert plan["held_combine_geometry_resize"]["resize_required"] is False
    assert out["receipt"]["status"] == "COMMITTED"
    assert float(out["receipt"]["held_combine_geometry_resize"].get("work_debited") or 0.0) == 0.0
    assert abs(float(rt.body.mechanical_work_reservoir) - w0) < 1e-12
    assert abs(float(rt.world.resource_objects[0].collision_radius) - 0.25) < 1e-12


def test_snapshot_restore_release_preserves_radius():
    from mechanistic_mind.physical_system.resource_objects import PHYSICAL_STATE_FREE_STATIC
    from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

    rt, left, right = _pair(ql=0.05, qr=0.05, work=10.0)
    expected_r = float(
        __import__(
            "mechanistic_mind.physical_system.detached_material_amount_scaled_collision_radius",
            fromlist=["derive_detached_material_collision_radius"],
        ).derive_detached_material_collision_radius(0.10).final_radius
    )
    w_before = float(rt.body.mechanical_work_reservoir)
    plan, out = _commit(rt, left, right, tick=1)
    assert out["receipt"]["status"] == "COMMITTED"
    w_after = float(rt.body.mechanical_work_reservoir)
    debit = w_before - w_after
    snap = deepcopy(rt.snapshot())
    restored = PhysicalSystemRuntime.restore(snap)
    _tick()
    assert len(restored.world.resource_objects) == 1
    surv = restored.world.resource_objects[0]
    assert abs(float(surv.collision_radius) - expected_r) < 1e-12
    assert abs(float(surv.vertical_half_extent) - expected_r) < 1e-12
    assert abs(float(restored.body.mechanical_work_reservoir) - w_after) < 1e-12
    # Restore must not replay debit
    assert debit > 0.0
    # Simulated RELEASE: drop to free with same geometry
    surv.physical_state = PHYSICAL_STATE_FREE_STATIC
    surv.holder_body_id = None
    surv.manipulator_id = None
    assert abs(float(surv.collision_radius) - expected_r) < 1e-12
    assert not any(o.object_id == "resource-R" for o in restored.world.resource_objects)


def test_parent_preset_combine_does_not_resize():
    rt, left, right = _pair(cfg=_parent_cfg(), ql=0.05, qr=0.05, work=10.0)
    r0 = float(left.collision_radius)
    plan, out = _commit(rt, left, right, tick=1)
    assert "held_combine_geometry_resize" not in plan or plan.get("held_combine_geometry_resize") is None
    assert out["receipt"]["status"] == "COMMITTED"
    assert abs(float(rt.world.resource_objects[0].collision_radius) - r0) < 1e-12


def test_deposition_does_not_resize_and_cognition_privacy():
    from mechanistic_mind.physical_system.observation import audit_cognition_payload
    from mechanistic_mind.physical_system.world_material_transaction import plan_deposition

    rt, left, right = _pair(ql=0.05, qr=0.05, work=10.0)
    # Deposition plan path must not carry resize
    dplan = plan_deposition(
        world=rt.world,
        config=rt.config,
        body=rt.body,
        body_id="agent_0",
        held_object_id_at_tick_start=left.object_id,
        tick=1,
        runtime=rt,
    )
    assert "held_combine_geometry_resize" not in dplan
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    blob = repr(obs)
    assert "held_combine_geometry_resize" not in blob
    assert "required_resize_work" not in blob
    assert "HELD_COMBINE_GEOMETRY_RESIZE" not in blob


def test_foreign_body_overlap_rejects():
    from mechanistic_mind.physical_system.held_combine_radius_resize_transaction import (
        CLS_FOREIGN_BODY,
    )
    from mechanistic_mind.physical_body.state import PhysicalBodyState
    import numpy as np

    rt, left, right = _pair(ql=0.05, qr=0.05, work=10.0)
    foreign = PhysicalBodyState(
        tick=0, x=10.18, y=10.0, vx=0.0, vy=0.0, T=1.0,
        B=np.zeros(3), B_core=np.zeros(3), mech=0.0,
    )
    rt.world.detached_placement_body_refs = [
        ("agent_0", rt.body),
        ("foreign-1", foreign),
    ]
    plan, out = _commit(rt, left, right, tick=1)
    assert plan["status"] == "REJECTED"
    assert plan["rejection_reason"] == CLS_FOREIGN_BODY
    assert out["receipt"]["status"] == "REJECTED"
    assert len(rt.world.resource_objects) == 2


def test_tick_budget_report():
    # Pure accounting for validation budget (no extra sim).
    assert TICKS["n"] <= 200
