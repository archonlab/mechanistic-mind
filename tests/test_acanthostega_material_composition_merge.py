"""Acanthostega explicit material composition merge contracts."""
from __future__ import annotations

from mechanistic_mind.model.acanthostega import (
    acanthostega_bring_together_config,
    acanthostega_composition_merge_config,
)
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BRING_TOGETHER,
    PRESET_ACANTHOSTEGA_COMPOSITION_MERGE,
    PRESET_BETA31,
    canonical_fingerprint,
    preset_canonical,
)
from mechanistic_mind.physical_system.material_composition import (
    MATERIAL_COMPOSITION_MERGE,
    material_composition_merge_is_active,
)
from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT, MANIP_RIGHT
from mechanistic_mind.physical_system.resource_objects import MaterialComponent, PHYSICAL_STATE_HELD
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

FROZEN_BETA31_FP_SEED17 = "1621ef2c154864d1"


def _runtime(*, merge: bool = True) -> PhysicalSystemRuntime:
    cfg = acanthostega_composition_merge_config() if merge else acanthostega_bring_together_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    objects = list(rt.world.resource_objects)
    assert len(objects) == 2
    left, right = objects
    left.physical_state = right.physical_state = PHYSICAL_STATE_HELD
    left.holder_body_id = right.holder_body_id = "agent_0"
    left.manipulator_id = MANIP_LEFT
    right.manipulator_id = MANIP_RIGHT
    left.composition = (MaterialComponent("component_a", 1.0),)
    right.composition = (MaterialComponent("component_b", 1.0),)
    left.mass, left.quantity = 1.25, 1.0
    right.mass, right.quantity = 2.75, 1.0
    rt.pair_aperture = 0.4
    return rt


def _force(rt: PhysicalSystemRuntime, pair: str) -> None:
    rt._forced_motor_once = {
        "locomotion": "WAIT",
        "manipulator_left": "NONE",
        "manipulator_right": "NONE",
        "manipulator_pair": pair,
    }
    rt.step(1)


def _establish_contact(rt: PhysicalSystemRuntime) -> None:
    _force(rt, "NONE")
    assert rt.pair_contact is True


def test_preset_is_separate_and_tiktaalik_frozen():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    bring = preset_canonical(PRESET_ACANTHOSTEGA_BRING_TOGETHER, seed=17)
    merge = preset_canonical(PRESET_ACANTHOSTEGA_COMPOSITION_MERGE, seed=17)
    assert MATERIAL_COMPOSITION_MERGE not in bring["mechanisms"]
    assert merge["mechanisms"][MATERIAL_COMPOSITION_MERGE] is True
    assert "COMBINE" not in PhysicalSystemRuntime(seed=17, config=acanthostega_bring_together_config()).cognition["available_actions"]
    assert "COMBINE" in PhysicalSystemRuntime(seed=17, config=acanthostega_composition_merge_config()).cognition["available_actions"]


def test_contact_alone_never_merges():
    rt = _runtime(merge=True)
    _establish_contact(rt)
    assert len(rt.world.resource_objects) == 2
    _force(rt, "NONE")
    assert len(rt.world.resource_objects) == 2
    assert rt.last_material_transformation_receipt is None


def test_combine_requires_previously_confirmed_contact():
    rt = _runtime(merge=True)
    _force(rt, "COMBINE")
    assert len(rt.world.resource_objects) == 2
    assert rt.last_material_transformation_receipt["outcome"] == "MERGE_REQUIRES_CONFIRMED_CONTACT"


def test_combine_is_atomic_deterministic_and_conserved():
    rt = _runtime(merge=True)
    left_id = rt.world.resource_objects[0].object_id
    right_id = rt.world.resource_objects[1].object_id
    _establish_contact(rt)
    _force(rt, "COMBINE")
    assert len(rt.world.resource_objects) == 1
    survivor = rt.world.resource_objects[0]
    assert survivor.object_id == left_id
    assert survivor.mass == 4.0
    assert survivor.quantity == 2.0
    assert [(c.component_id, c.amount) for c in survivor.composition] == [
        ("component_a", 1.0), ("component_b", 1.0),
    ]
    assert survivor.manipulator_id == MANIP_LEFT
    receipt = rt.last_material_transformation_receipt
    assert receipt["outcome"] == "MERGE_COMMITTED"
    assert receipt["removed_object_id"] == right_id
    assert receipt["mass_residual"] == 0.0
    assert receipt["quantity_residual"] == 0.0
    assert all(v == 0.0 for v in receipt["component_residuals"].values())
    assert receipt["replacement_policy"] == "LEFT_OBJECT_SURVIVES_RIGHT_REMOVED"
    assert rt.pair_contact is False


def test_bring_together_stage_rejects_combine_and_snapshot_round_trip():
    old = _runtime(merge=False)
    _establish_contact(old)
    _force(old, "COMBINE")
    assert len(old.world.resource_objects) == 2
    assert material_composition_merge_is_active(old.config) is False

    rt = _runtime(merge=True)
    _establish_contact(rt)
    _force(rt, "COMBINE")
    restored = PhysicalSystemRuntime.restore(rt.snapshot())
    assert material_composition_merge_is_active(restored.config) is True
    assert len(restored.world.resource_objects) == 1
    assert restored.last_material_transformation_receipt["outcome"] == "MERGE_COMMITTED"
    assert restored.world.resource_objects[0].provenance["last_transformation_id"]
