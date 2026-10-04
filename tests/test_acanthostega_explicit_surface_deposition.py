"""Explicit LEFT-held APPLY_TO_SURFACE. Deposit state only; no terrain effects."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    acanthostega_material_properties_config,
    acanthostega_surface_deposition_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.actions import available_actions
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA,
    PRESET_ACANTHOSTEGA_BILATERAL_GRASP,
    PRESET_ACANTHOSTEGA_BRING_TOGETHER,
    PRESET_ACANTHOSTEGA_COMPOSITION_MERGE,
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES,
    PRESET_ACANTHOSTEGA_MATERIAL_VISION,
    PRESET_ACANTHOSTEGA_MATERIALS,
    PRESET_ACANTHOSTEGA_SINGLE_GRASP,
    PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION,
    PRESET_BETA31,
    beta31_mechanism_map,
    canonical_fingerprint,
    preset_canonical,
)
from mechanistic_mind.physical_system.explicit_surface_deposition import (
    APPLY_TO_SURFACE,
    CANONICAL_DEPOSIT_AMOUNT,
    DEPOSITION_WORK_ACCOUNTING,
    EXPLICIT_SURFACE_DEPOSITION,
    SOURCE_DEPLETED,
    SOURCE_MANIPULATOR,
    explicit_surface_deposition_is_active,
    resolve_deposit_cell,
)
from mechanistic_mind.physical_system.material_composition import MATERIAL_COMPOSITION_MERGE
from mechanistic_mind.physical_system.mechanism_registry import set_mechanism
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.passive_material_properties import (
    DERIVATION_VERSION,
    PASSIVE_MATERIAL_PROPERTIES,
    derive_effective_properties,
)
from mechanistic_mind.physical_system.physical_manipulator import (
    MANIP_LEFT,
    MANIP_RIGHT,
    effector_world_xy,
)
from mechanistic_mind.physical_system.resource_objects import MaterialComponent, PHYSICAL_STATE_FREE_STATIC, PHYSICAL_STATE_HELD
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.scientific_v3.deposition_summary import (
    AGENT_DEPOSIT_PERCEPTION,
    INSTRUMENTAL_USE,
    TERRAIN_CONSEQUENCE,
    summarize_surface_depositions,
)
from mechanistic_mind.ui.psy_observer_web.serialize import world_frame

FROZEN_BETA31_FP_SEED17 = "1621ef2c154864d1"
PREVIOUS = (
    PRESET_BETA31,
    PRESET_ACANTHOSTEGA,
    PRESET_ACANTHOSTEGA_GENTLE,
    PRESET_ACANTHOSTEGA_MATERIALS,
    PRESET_ACANTHOSTEGA_MATERIAL_VISION,
    PRESET_ACANTHOSTEGA_SINGLE_GRASP,
    PRESET_ACANTHOSTEGA_BILATERAL_GRASP,
    PRESET_ACANTHOSTEGA_BRING_TOGETHER,
    PRESET_ACANTHOSTEGA_COMPOSITION_MERGE,
    PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES,
)


def _runtime() -> PhysicalSystemRuntime:
    cfg = acanthostega_surface_deposition_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    left, right = list(rt.world.resource_objects)
    left.physical_state = PHYSICAL_STATE_HELD
    left.holder_body_id = "agent_0"
    left.manipulator_id = MANIP_LEFT
    right.physical_state = PHYSICAL_STATE_HELD
    right.holder_body_id = "agent_0"
    right.manipulator_id = MANIP_RIGHT
    left.composition = (
        MaterialComponent("component_a", 0.25),
        MaterialComponent("component_b", 0.75),
    )
    left.quantity = 1.0
    left.mass = 2.0
    right.composition = (MaterialComponent("component_b", 1.0),)
    right.quantity = 1.0
    right.mass = 3.5
    return rt


def _apply(rt: PhysicalSystemRuntime, *, left: str = "NONE", pair: str = "NONE", surface: bool = True) -> None:
    rt._forced_motor_once = {
        "locomotion": "WAIT",
        "manipulator_left": left,
        "manipulator_right": "NONE",
        "manipulator_pair": pair,
        "apply_to_surface": surface,
    }
    rt.step(1)


def test_fingerprint_and_previous_presets_exclude_deposition():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    assert EXPLICIT_SURFACE_DEPOSITION not in beta31_mechanism_map()
    for name in PREVIOUS:
        mechanisms = preset_canonical(name, seed=17)["mechanisms"]
        assert EXPLICIT_SURFACE_DEPOSITION not in mechanisms
        assert "APPLY_TO_SURFACE" not in available_actions(
            physical_bilateral_grasp_release=True,
            physical_bilateral_bring_together=True,
            material_composition_merge=bool(mechanisms.get(MATERIAL_COMPOSITION_MERGE)),
            explicit_surface_deposition=False,
        )
    fresh = preset_canonical(PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION, seed=17)
    assert fresh["mechanisms"][MATERIAL_COMPOSITION_MERGE] is True
    assert fresh["mechanisms"][PASSIVE_MATERIAL_PROPERTIES] is True
    assert fresh["mechanisms"][EXPLICIT_SURFACE_DEPOSITION] is True
    tik = tiktaalik_config()
    set_mechanism(tik, EXPLICIT_SURFACE_DEPOSITION, True)
    assert explicit_surface_deposition_is_active(tik) is False
    catalog = {row["id"] for row in PhysicalSystemRuntime(seed=17, config=tik).mechanisms()["mechanisms"]}
    assert EXPLICIT_SURFACE_DEPOSITION not in catalog
    previous = PhysicalSystemRuntime(seed=17, config=acanthostega_material_properties_config())
    previous._sync_embodiment_dofs()
    assert "APPLY_TO_SURFACE" not in previous.cognition["available_actions"]
    assert explicit_surface_deposition_is_active(previous.config) is False


def test_apply_transfers_proportionally_and_conserves():
    rt = _runtime()
    right_before = (rt.world.resource_objects[1].mass, rt.world.resource_objects[1].quantity, rt.world.resource_objects[1].object_id)
    optical = tuple(rt.world.resource_objects[0].optical_response)
    drag = None if rt.world.terrain_drag is None else rt.world.terrain_drag.copy()
    _apply(rt)
    left = next(obj for obj in rt.world.resource_objects if obj.manipulator_id == MANIP_LEFT)
    assert left.object_id == "resource-000001"
    assert left.physical_state == PHYSICAL_STATE_HELD
    assert abs(left.quantity - 0.90) < 1e-12
    assert abs(left.mass - 1.80) < 1e-12
    assert [(c.component_id, round(c.amount, 12)) for c in left.composition] == [
        ("component_a", 0.225),
        ("component_b", 0.675),
    ]
    assert tuple(left.optical_response) == optical
    right = next(obj for obj in rt.world.resource_objects if obj.object_id == right_before[2])
    assert (right.mass, right.quantity) == (right_before[0], right_before[1])
    assert right.manipulator_id == MANIP_RIGHT
    deposits = rt.world.surface_material_deposits
    assert len(deposits) == 1
    deposit = next(iter(deposits.values()))
    ex, ey = effector_world_xy(
        rt.body, width=rt.world.T.shape[1], height=rt.world.T.shape[0],
        config=rt.config, manipulator_id=MANIP_LEFT, runtime=rt,
    )
    cell_x, cell_y = resolve_deposit_cell(ex, ey, width=rt.world.T.shape[1], height=rt.world.T.shape[0])
    assert deposit.deposit_id == f"surface-deposit-x{cell_x}-y{cell_y}"
    assert (deposit.cell_x, deposit.cell_y) == (cell_x, cell_y)
    assert abs(deposit.quantity - CANONICAL_DEPOSIT_AMOUNT) < 1e-12
    assert abs(deposit.mass - 0.20) < 1e-12
    assert [(c.component_id, round(c.amount, 12)) for c in deposit.composition] == [
        ("component_a", 0.025),
        ("component_b", 0.075),
    ]
    derived = derive_effective_properties(deposit.composition)
    receipt = rt.last_surface_deposition_receipt
    assert receipt["outcome"] == "DEPOSITION_COMMITTED"
    assert receipt["source_manipulator"] == SOURCE_MANIPULATOR
    assert receipt["causal_reason"] == "EXPLICIT_MOTOR_COMMAND"
    assert receipt["source_held_at_tick_start"] is True
    assert receipt["deposit_properties_after"]["compliance"] == derived["compliance"]
    assert receipt["deposit_properties_after"]["surface_affinity"] == derived["surface_affinity"]
    assert receipt["derivation_version"] == DERIVATION_VERSION
    assert abs(receipt["mass_residual"]) < 1e-9
    assert abs(receipt["quantity_residual"]) < 1e-9
    assert max(abs(v) for v in receipt["component_residuals"].values()) < 1e-9
    assert receipt["terrain_effects_applied"] is False
    assert receipt["body_effects_applied"] is False
    assert receipt["traversal_effects_applied"] is False
    assert receipt["material_reactions_applied"] is False
    assert receipt["semantic_effects"] is False
    assert receipt["deposition_work_accounting"] == DEPOSITION_WORK_ACCOUNTING
    assert receipt["work_debit"] is None
    assert receipt["source_removed"] is False
    if drag is not None:
        assert (rt.world.terrain_drag == drag).all()


def test_repeat_updates_same_deposit_and_depletion_frees_left_hand():
    rt = _runtime()
    _apply(rt)
    first = next(iter(rt.world.surface_material_deposits.values()))
    first_id = first.deposit_id
    _apply(rt)
    assert list(rt.world.surface_material_deposits) == [first_id]
    deposit = rt.world.surface_material_deposits[first_id]
    assert abs(deposit.quantity - 0.20) < 1e-12
    assert rt.last_surface_deposition_receipt["deposit_created"] is False
    assert rt.last_surface_deposition_receipt["deposit_updated"] is True
    assert abs(
        derive_effective_properties(deposit.composition)["compliance"]
        - derive_effective_properties(
            (MaterialComponent("component_a", 0.05), MaterialComponent("component_b", 0.15))
        )["compliance"]
    ) < 1e-12
    left = next(obj for obj in rt.world.resource_objects if obj.manipulator_id == MANIP_LEFT)
    left.quantity = 0.05
    left.mass = 0.4
    left.composition = (MaterialComponent("component_a", 0.05),)
    _apply(rt)
    assert all(obj.manipulator_id != MANIP_LEFT for obj in rt.world.resource_objects)
    assert rt.last_surface_deposition_receipt["source_state_after"] == SOURCE_DEPLETED
    assert rt.last_surface_deposition_receipt["left_hand_freed"] is True
    assert abs(rt.world.surface_material_deposits[first_id].quantity - 0.25) < 1e-12
    assert abs(rt.world.surface_material_deposits[first_id].mass - 0.80) < 1e-12


def test_rejections_are_atomic_and_other_commands_do_not_deposit():
    rt = _runtime()
    _apply(rt, surface=False)
    assert rt.world.surface_material_deposits == {}
    _apply(rt, left="RELEASE", surface=False)
    assert rt.world.surface_material_deposits == {}
    bare = _runtime()
    for obj in bare.world.resource_objects:
        if obj.manipulator_id == MANIP_LEFT:
            obj.physical_state = PHYSICAL_STATE_FREE_STATIC
            obj.holder_body_id = None
            obj.manipulator_id = None
            obj.x, obj.y = bare.body.x, bare.body.y
    before = [(o.object_id, o.quantity, o.mass, o.physical_state) for o in bare.world.resource_objects]
    _apply(bare)
    assert bare.last_surface_deposition_receipt["outcome"] == "DEPOSITION_NO_LEFT_HELD_OBJECT"
    assert bare.world.surface_material_deposits == {}
    assert [(o.object_id, o.quantity, o.mass, o.physical_state) for o in bare.world.resource_objects] == before
    grasp = _runtime()
    for obj in grasp.world.resource_objects:
        if obj.manipulator_id == MANIP_LEFT:
            obj.physical_state = PHYSICAL_STATE_FREE_STATIC
            obj.holder_body_id = None
            obj.manipulator_id = None
    ex, ey = effector_world_xy(
        grasp.body, width=grasp.world.T.shape[1], height=grasp.world.T.shape[0],
        config=grasp.config, manipulator_id=MANIP_LEFT, runtime=grasp,
    )
    free = next(obj for obj in grasp.world.resource_objects if obj.physical_state == PHYSICAL_STATE_FREE_STATIC)
    free.x, free.y = ex, ey
    _apply(grasp, left="GRASP", surface=True)
    assert grasp.last_surface_deposition_receipt["outcome"] == "DEPOSITION_SOURCE_NOT_HELD_AT_TICK_START"
    assert grasp.world.surface_material_deposits == {}
    assert free.physical_state == PHYSICAL_STATE_HELD
    empty = _runtime()
    left = next(obj for obj in empty.world.resource_objects if obj.manipulator_id == MANIP_LEFT)
    left.quantity = 0.0
    left.mass = 0.0
    left.composition = (MaterialComponent("component_a", 0.0),)
    _apply(empty)
    assert empty.last_surface_deposition_receipt["outcome"] == "DEPOSITION_EMPTY_SOURCE"
    assert empty.world.surface_material_deposits == {}
    assert left.quantity == 0.0
    merged = _runtime()
    merged.pair_aperture = 0.4
    _apply(merged, surface=False)
    _apply(merged, pair="COMBINE", surface=False)
    assert merged.world.surface_material_deposits == {}
    assert merged.last_material_transformation_receipt["outcome"] == "MERGE_COMMITTED"


def test_snapshot_restore_missing_fields_and_analyzer():
    rt = _runtime()
    _apply(rt)
    snap = rt.snapshot()
    assert snap["config"]["explicit_surface_deposition"]["enabled"] is True
    restored = PhysicalSystemRuntime.restore(deepcopy(snap))
    assert explicit_surface_deposition_is_active(restored.config) is True
    deposit = next(iter(restored.world.surface_material_deposits.values()))
    assert deposit.deposit_id.startswith("surface-deposit-x")
    before_qty = deposit.quantity
    restored._forced_motor_once = {
        "locomotion": "WAIT",
        "manipulator_left": "NONE",
        "manipulator_right": "NONE",
        "manipulator_pair": "NONE",
        "apply_to_surface": True,
    }
    restored.step(1)
    again = restored.world.surface_material_deposits[deposit.deposit_id]
    assert abs(again.quantity - (before_qty + CANONICAL_DEPOSIT_AMOUNT)) < 1e-9
    assert len(restored.world.surface_material_deposits) == 1
    missing_cfg = deepcopy(snap)
    missing_cfg["config"].pop("explicit_surface_deposition")
    off = PhysicalSystemRuntime.restore(missing_cfg)
    assert explicit_surface_deposition_is_active(off.config) is False
    missing_world = deepcopy(snap)
    missing_world["world"].pop("surface_material_deposits", None)
    empty_world = PhysicalSystemRuntime.restore(missing_world)
    assert empty_world.world.surface_material_deposits == {}
    tik = PhysicalSystemRuntime(seed=17, config=tiktaalik_config()).snapshot()
    assert "explicit_surface_deposition" not in tik["config"]
    assert "surface_material_deposits" not in tik["world"]
    summary = summarize_surface_depositions([
        {"type": "RESOURCE_CHANGE", "evidence": {"amount": 5}},
        {"type": "MATERIAL_COMBINE_COMMITTED", "evidence": {"outcome": "MERGE_COMMITTED"}},
        {"type": rt.last_surface_deposition_receipt["event"], "evidence": rt.last_surface_deposition_receipt},
    ])
    assert summary["deposition_attempts"] == 1
    assert summary["deposition_committed"] == 1
    assert summary["deposits_created"] == 1
    assert summary["TERRAIN_CONSEQUENCE"] == TERRAIN_CONSEQUENCE
    assert summary["AGENT_DEPOSIT_PERCEPTION"] == AGENT_DEPOSIT_PERCEPTION
    assert summary["INSTRUMENTAL_USE"] == INSTRUMENTAL_USE
    assert summary["mixed_with_resource_change"] is False
    note = summary["note"].lower()
    for banned in ("intention", "discovery", "utility", "recipe", "learning", "beneficial", "harmful"):
        assert banned not in note


def test_cognition_excludes_deposit_state_and_observer_is_researcher_only():
    rt = _runtime()
    rt._sync_embodiment_dofs()
    assert APPLY_TO_SURFACE in rt.cognition["available_actions"]
    _apply(rt)
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    assert audit_cognition_payload(rt.cognition) == []
    frame = world_frame(rt)
    row = frame["surface_material_deposits"][0]
    assert row["researcher_only"] is True
    assert row["agent_accessible"] is False
    assert row["status"] == "no terrain consequence yet"
    assert row["access"] == "researcher-only"
    assert "compliance" in row and "surface_affinity" in row
