"""Passive composition-weighted material coefficients. No causal effects."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    acanthostega_composition_merge_config,
    acanthostega_material_properties_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
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
    PRESET_BETA31,
    beta31_mechanism_map,
    canonical_fingerprint,
    preset_canonical,
)
from mechanistic_mind.physical_system.material_composition import MATERIAL_COMPOSITION_MERGE
from mechanistic_mind.physical_system.mechanism_registry import set_mechanism
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.passive_material_properties import (
    DERIVATION_VERSION,
    PASSIVE_MATERIAL_PROPERTIES,
    PRIMITIVE_COEFFICIENTS_V1,
    REGISTRY_VERSION,
    UNKNOWN_COMPONENT_POLICY,
    derive_effective_properties,
    passive_material_properties_is_active,
    primitive_coefficient_reference,
)
from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT, MANIP_RIGHT
from mechanistic_mind.physical_system.resource_objects import MaterialComponent, PHYSICAL_STATE_HELD
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.scientific_v3.material_summary import (
    CAUSAL_MATERIAL_EFFECTS,
    summarize_material_transformations,
)
from mechanistic_mind.ui.psy_observer_web.serialize import world_frame
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

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
)


def _runtime() -> PhysicalSystemRuntime:
    cfg = acanthostega_material_properties_config()
    cfg.cognition.cognition_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    left, right = list(rt.world.resource_objects)
    left.physical_state = right.physical_state = PHYSICAL_STATE_HELD
    left.holder_body_id = right.holder_body_id = "agent_0"
    left.manipulator_id = MANIP_LEFT
    right.manipulator_id = MANIP_RIGHT
    left.composition = (MaterialComponent("component_a", 1.0),)
    right.composition = (MaterialComponent("component_b", 3.0),)
    left.mass, left.quantity = 1.25, 1.0
    right.mass, right.quantity = 2.75, 3.0
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


def test_tiktaalik_fingerprint_and_previous_presets_exclude_mechanism():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    assert PASSIVE_MATERIAL_PROPERTIES not in beta31_mechanism_map()
    for name in PREVIOUS:
        assert PASSIVE_MATERIAL_PROPERTIES not in preset_canonical(name, seed=17)["mechanisms"]
    fresh = preset_canonical(PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES, seed=17)
    assert fresh["mechanisms"][MATERIAL_COMPOSITION_MERGE] is True
    assert fresh["mechanisms"][PASSIVE_MATERIAL_PROPERTIES] is True
    tik = tiktaalik_config()
    set_mechanism(tik, PASSIVE_MATERIAL_PROPERTIES, True)
    assert passive_material_properties_is_active(tik) is False
    assert PASSIVE_MATERIAL_PROPERTIES not in {row["id"] for row in PhysicalSystemRuntime(seed=17, config=tik).mechanisms()["mechanisms"]}


def test_primitive_coefficients_are_stable_finite_and_order_independent():
    again = dict(PRIMITIVE_COEFFICIENTS_V1)
    assert again == {
        "component_0": {"compliance": 0.5, "surface_affinity": 0.5},
        "component_a": {"compliance": 0.25, "surface_affinity": 0.75},
        "component_b": {"compliance": 0.75, "surface_affinity": 0.25},
    }
    for row in again.values():
        assert all(map(lambda v: v == v and abs(v) != float("inf") and 0.0 <= v <= 1.0, row.values()))
    forward = derive_effective_properties((
        MaterialComponent("component_b", 3.0),
        MaterialComponent("component_a", 1.0),
    ))
    reverse = derive_effective_properties((
        MaterialComponent("component_a", 1.0),
        MaterialComponent("component_b", 3.0),
    ))
    assert forward["compliance"] == reverse["compliance"] == 0.625
    assert forward["surface_affinity"] == reverse["surface_affinity"] == 0.375
    duplicated = derive_effective_properties((
        MaterialComponent("component_a", 0.25),
        MaterialComponent("component_a", 0.75),
    ))
    single = derive_effective_properties((MaterialComponent("component_a", 1.0),))
    assert duplicated["compliance"] == single["compliance"] == 0.25
    assert duplicated["canonical_amounts"] == {"component_a": 1.0}
    unknown = primitive_coefficient_reference("component_unknown_zz")
    assert unknown["source"] == "FALLBACK"
    assert unknown["fallback_policy"] == UNKNOWN_COMPONENT_POLICY
    assert unknown["compliance"] == 0.5 and unknown["surface_affinity"] == 0.5
    assert primitive_coefficient_reference("component_unknown_yy")["compliance"] == unknown["compliance"]
    assert primitive_coefficient_reference("component_0")["source"] == "REGISTRY"
    empty = derive_effective_properties(())
    assert empty["compliance"] == 0.0 and empty["surface_affinity"] == 0.0
    assert empty["property_derivation_verified"] is True
    heavy = derive_effective_properties((MaterialComponent("component_a", 1.0),))
    light = derive_effective_properties((MaterialComponent("component_a", 1.0),))
    assert heavy["compliance"] == light["compliance"]


def test_contact_alone_does_not_change_properties_and_combine_derives_output():
    rt = _runtime()
    before = [derive_effective_properties(o.composition) for o in rt.world.resource_objects]
    comps = [tuple((c.component_id, c.amount) for c in o.composition) for o in rt.world.resource_objects]
    _force(rt, "NONE")
    assert rt.pair_contact is True
    assert [tuple((c.component_id, c.amount) for c in o.composition) for o in rt.world.resource_objects] == comps
    assert [derive_effective_properties(o.composition)["compliance"] for o in rt.world.resource_objects] == [
        before[0]["compliance"], before[1]["compliance"],
    ]
    assert rt.last_material_transformation_receipt is None
    left_id = rt.world.resource_objects[0].object_id
    right_id = rt.world.resource_objects[1].object_id
    optical = tuple(rt.world.resource_objects[0].optical_response)
    _force(rt, "COMBINE")
    assert len(rt.world.resource_objects) == 1
    survivor = rt.world.resource_objects[0]
    assert survivor.object_id == left_id
    assert right_id not in {o.object_id for o in rt.world.resource_objects}
    assert survivor.manipulator_id == MANIP_LEFT
    assert all(o.manipulator_id != MANIP_RIGHT for o in rt.world.resource_objects)
    assert survivor.mass == 4.0
    assert survivor.quantity == 4.0
    assert [(c.component_id, c.amount) for c in survivor.composition] == [
        ("component_a", 1.0), ("component_b", 3.0),
    ]
    derived = derive_effective_properties(survivor.composition)
    assert derived["compliance"] == 0.625
    assert derived["surface_affinity"] == 0.375
    assert tuple(survivor.optical_response) == optical
    receipt = rt.last_material_transformation_receipt
    assert receipt["outcome"] == "MERGE_COMMITTED"
    assert receipt["effective_properties_after"] == {
        "compliance": derived["compliance"],
        "surface_affinity": derived["surface_affinity"],
    }
    assert receipt["property_derivation_verified"] is True
    assert receipt["property_derivation_residuals"] == {"compliance": 0.0, "surface_affinity": 0.0}
    assert receipt["derivation_version"] == DERIVATION_VERSION
    assert receipt["passive_properties_only"] is True
    assert receipt["world_effects_applied"] is False
    assert receipt["body_effects_applied"] is False
    assert receipt["material_interactions_applied"] is False
    assert receipt["semantic_effects"] is False
    assert receipt["primitive_coefficient_references"]["left"][0]["component_id"] == "component_a"
    assert receipt["primitive_coefficient_references"]["right"][0]["registry_version"] == REGISTRY_VERSION
    assert receipt["effective_properties_before"]["left"]["compliance"] == 0.25
    assert receipt["effective_properties_before"]["right"]["compliance"] == 0.75


def test_snapshot_restore_and_missing_config_field():
    rt = _runtime()
    _force(rt, "NONE")
    _force(rt, "COMBINE")
    expected = derive_effective_properties(rt.world.resource_objects[0].composition)
    snap = rt.snapshot()
    assert snap["config"]["passive_material_properties"]["enabled"] is True
    assert snap["config"]["passive_material_properties"]["registry_version"] == REGISTRY_VERSION
    restored = PhysicalSystemRuntime.restore(deepcopy(snap))
    assert passive_material_properties_is_active(restored.config) is True
    assert restored.config.passive_material_properties.registry_version == REGISTRY_VERSION
    survivor = restored.world.resource_objects[0]
    assert [(c.component_id, c.amount) for c in survivor.composition] == [
        ("component_a", 1.0), ("component_b", 3.0),
    ]
    assert derive_effective_properties(survivor.composition)["compliance"] == expected["compliance"]
    assert derive_effective_properties(survivor.composition)["surface_affinity"] == expected["surface_affinity"]
    legacy = deepcopy(snap)
    legacy["config"].pop("passive_material_properties")
    off = PhysicalSystemRuntime.restore(legacy)
    assert passive_material_properties_is_active(off.config) is False
    tik = PhysicalSystemRuntime(model="tiktaalik", seed=17).snapshot()
    assert "passive_material_properties" not in tik["config"]


def test_agent_payload_excludes_properties_and_observer_is_researcher_only():
    rt = _runtime()
    rt.step(1)
    obs = rt.agent_observation()
    assert audit_cognition_payload(obs) == []
    blob = repr(obs) + repr(rt.cognition)
    for token in (
        "component_a", "component_b", "compliance", "surface_affinity",
        "passive_material_properties", "effective_properties", DERIVATION_VERSION,
    ):
        assert token not in blob
    frame = world_frame(rt)
    shown = frame["resource_objects"][0]["passive_material_properties"]
    assert shown["access"] == "researcher-only"
    assert shown["agent_accessible"] is False
    assert shown["status"] == "passive — no consequence kernel"
    assert "compliance" in shown and "surface_affinity" in shown
    merge = PhysicalSystemRuntime(seed=17, config=acanthostega_composition_merge_config())
    hidden = world_frame(merge)["resource_objects"][0]
    assert "passive_material_properties" not in hidden


def test_analyzer_reconstructs_derivation_without_causal_claims():
    rt = _runtime()
    _force(rt, "NONE")
    _force(rt, "COMBINE")
    receipt = rt.last_material_transformation_receipt
    summary = summarize_material_transformations(
        [{"type": "MATERIAL_COMBINE_COMMITTED", "tick": receipt["tick"], "evidence": receipt}],
        objects=[{"composition": [c.to_dict() for c in rt.world.resource_objects[0].composition]}],
    )
    row = summary["transformations"][0]
    assert row["effective_properties_before"]["left"]["compliance"] == 0.25
    assert row["effective_properties_after"]["compliance"] == 0.625
    assert row["reconstructed_effective_properties"]["surface_affinity"] == 0.375
    assert summary["derivation_version"] == DERIVATION_VERSION
    assert summary["max_abs_derivation_residual"] == 0.0
    assert summary["objects_with_valid_derived_properties"] == 1
    assert summary["objects_with_invalid_derived_properties"] == 0
    assert summary["CAUSAL_MATERIAL_EFFECTS"] == CAUSAL_MATERIAL_EFFECTS
    assert summary["semantic_recipes_present"] is False
    text = repr(summary).lower()
    for banned in ("intention", "discovery", "learning", "beneficial", "harmful"):
        assert banned not in text


def test_properties_do_not_change_wait_motion_versus_composition_merge():
    def pose(cfg):
        cfg.cognition.cognition_enabled = False
        rt = PhysicalSystemRuntime(seed=17, config=cfg)
        rt._forced_motor_once = {"locomotion": "WAIT", "manipulator_pair": "NONE"}
        rt.step(1)
        body = rt.body
        return (round(body.x, 9), round(body.y, 9), round(body.vx, 9), round(body.vy, 9))

    assert pose(acanthostega_material_properties_config()) == pose(acanthostega_composition_merge_config())


def test_observer_apply_keeps_tiktaalik_flag_off():
    session = ObserverSession(SessionConfig(seed=17))
    session.apply_experiment({
        "public_preset": PRESET_BETA31,
        "agent_count": 1,
        "cognition_enabled": False,
        "mechanisms": {PASSIVE_MATERIAL_PROPERTIES: True},
    })
    assert passive_material_properties_is_active(session.runtime.config) is False
    ids = {row["id"] for row in session.runtime.mechanisms()["mechanisms"]}
    assert PASSIVE_MATERIAL_PROPERTIES not in ids
    session.apply_experiment({
        "public_preset": PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES,
        "agent_count": 1,
        "cognition_enabled": False,
    })
    assert session.runtime.config.public_preset == PRESET_ACANTHOSTEGA_MATERIAL_PROPERTIES
    assert passive_material_properties_is_active(session.runtime.config) is True
    assert "COMBINE" in session.runtime.cognition["available_actions"]
