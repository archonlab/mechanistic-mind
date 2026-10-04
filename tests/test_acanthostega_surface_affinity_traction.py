"""Surface affinity scales active MOVE on the next tick. Deposit state is unchanged."""
from __future__ import annotations

import inspect
from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    acanthostega_surface_deposition_config,
    acanthostega_surface_traction_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.body_contact import resolve_soft_contact
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
    EXPLICIT_SURFACE_DEPOSITION,
    SurfaceMaterialDeposit,
    deposit_id_for_cell,
)
from mechanistic_mind.physical_system.material_composition import MATERIAL_COMPOSITION_MERGE
from mechanistic_mind.physical_system.mechanism_registry import set_mechanism
from mechanistic_mind.physical_system.motor_work import ke_increment
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.passive_material_properties import (
    DERIVATION_VERSION,
    PASSIVE_MATERIAL_PROPERTIES,
    derive_effective_properties,
)
from mechanistic_mind.physical_system.physical_manipulator import MANIP_LEFT, MANIP_RIGHT
from mechanistic_mind.physical_system.resource_objects import (
    MaterialComponent,
    PHYSICAL_STATE_HELD,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.surface_affinity_traction import (
    CELL_POLICY,
    ENERGY_INTERPRETATION,
    EVENT_APPLIED,
    SURFACE_AFFINITY_TRACTION,
    traction_multiplier,
    surface_affinity_traction_is_active,
)
from mechanistic_mind.scientific_v3.deposition_summary import summarize_surface_depositions
from mechanistic_mind.scientific_v3.traction_summary import (
    AGENT_SYMBOLIC_TRACTION_SENSOR,
    INSTRUMENTAL_USE,
    LEARNING_FROM_TRACTION,
    RECIPE_SYSTEM,
    TRACTION_CAUSAL_EFFECT,
    summarize_surface_traction,
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
    PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION,
)


def _runtime(traction: bool = True) -> PhysicalSystemRuntime:
    cfg = acanthostega_surface_traction_config() if traction else acanthostega_surface_deposition_config()
    cfg.cognition.cognition_enabled = False
    return PhysicalSystemRuntime(seed=17, config=cfg)


def _park(rt: PhysicalSystemRuntime, x: float = 10.2, y: float = 10.2) -> None:
    rt.body.x = float(x)
    rt.body.y = float(y)
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    rt.body.mechanical_work_reservoir = 20.0


def _put(rt: PhysicalSystemRuntime, cell_x: int, cell_y: int, component: str, *, updated: int) -> SurfaceMaterialDeposit:
    deposit = SurfaceMaterialDeposit(
        deposit_id=deposit_id_for_cell(cell_x, cell_y),
        cell_x=int(cell_x),
        cell_y=int(cell_y),
        mass=1.0,
        quantity=1.0,
        composition=(MaterialComponent(component, 1.0),),
        provenance={"lineage_refs": [{"event_id": "surface-deposition-origin", "tick": updated}]},
        created_tick=int(updated),
        last_updated_tick=int(updated),
    )
    rt.world.surface_material_deposits[deposit.deposit_id] = deposit
    return deposit


def _move(rt: PhysicalSystemRuntime, command: str = "MOVE:E", **extra) -> None:
    rt._forced_motor_once = {"locomotion": command, **extra}
    rt.step(1)


def _realized_x(rt: PhysicalSystemRuntime) -> float:
    dv = (rt.last_action_work_ledger or {}).get("action_dv_realized") or [0.0, 0.0]
    return float(dv[0])


def test_fingerprint_previous_presets_and_inheritance():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    assert SURFACE_AFFINITY_TRACTION not in beta31_mechanism_map()
    for name in PREVIOUS:
        assert SURFACE_AFFINITY_TRACTION not in preset_canonical(name, seed=17)["mechanisms"]
    fresh = preset_canonical("ACANTHOSTEGA_PHASE_A_SURFACE_TRACTION", seed=17)
    assert fresh["mechanisms"][MATERIAL_COMPOSITION_MERGE] is True
    assert fresh["mechanisms"][PASSIVE_MATERIAL_PROPERTIES] is True
    assert fresh["mechanisms"][EXPLICIT_SURFACE_DEPOSITION] is True
    assert fresh["mechanisms"][SURFACE_AFFINITY_TRACTION] is True
    tik = tiktaalik_config()
    set_mechanism(tik, SURFACE_AFFINITY_TRACTION, True)
    assert surface_affinity_traction_is_active(tik) is False
    catalog = {row["id"] for row in PhysicalSystemRuntime(seed=17, config=tik).mechanisms()["mechanisms"]}
    assert SURFACE_AFFINITY_TRACTION not in catalog
    assert "surface_affinity_traction" not in PhysicalSystemRuntime(seed=17, config=tiktaalik_config()).snapshot()["config"]
    src = inspect.getsource(traction_multiplier)
    assert "component_" not in src


def test_formula_clip_and_equal_mixture():
    assert traction_multiplier(0.0) == 0.60
    assert traction_multiplier(0.25) == 0.80
    assert traction_multiplier(0.50) == 1.00
    assert abs(traction_multiplier(0.75) - 1.20) < 1e-12
    assert traction_multiplier(1.0) == 1.40
    assert traction_multiplier(-2.0) == 0.60
    assert traction_multiplier(3.0) == 1.40
    mixed = derive_effective_properties([
        {"component_id": "component_a", "amount": 1.0},
        {"component_id": "component_b", "amount": 1.0},
    ])
    assert abs(mixed["surface_affinity"] - 0.5) < 1e-12
    assert traction_multiplier(mixed["surface_affinity"]) == 1.0


def test_spawn_contrast_is_limited_to_the_new_preset():
    rt = _runtime()
    by_id = {obj.object_id: obj for obj in rt.world.resource_objects}
    assert set(by_id) == {"resource-000001", "resource-000002"}
    assert by_id["resource-000001"].composition[0].component_id == "component_a"
    assert by_id["resource-000002"].composition[0].component_id == "component_b"
    left, right = by_id["resource-000001"], by_id["resource-000002"]
    assert left.mass == right.mass
    assert left.quantity == right.quantity
    assert left.optical_radius == right.optical_radius
    assert left.interaction_radius == right.interaction_radius
    assert tuple(left.optical_response) == tuple(right.optical_response)
    previous = _runtime(traction=False)
    assert all(
        component.component_id == "component_0"
        for obj in previous.world.resource_objects
        for component in obj.composition
    )


def test_calibration_orders_realized_move_and_leaves_other_channels():
    def once(component: str | None) -> PhysicalSystemRuntime:
        rt = _runtime()
        _park(rt)
        if component is not None:
            _put(rt, 10, 10, component, updated=-1)
        _move(rt, "MOVE:E")
        return rt

    bare = once(None)
    neutral = once("component_0")
    low = once("component_b")
    high = once("component_a")
    assert abs(_realized_x(bare) - _realized_x(neutral)) < 1e-12
    assert _realized_x(low) < _realized_x(neutral) < _realized_x(high)
    assert bare.last_surface_traction_receipt is None
    assert neutral.last_surface_traction_receipt["traction_multiplier"] == 1.0
    assert abs(low.last_surface_traction_receipt["traction_multiplier"] - 0.8) < 1e-12
    assert abs(high.last_surface_traction_receipt["traction_multiplier"] - 1.2) < 1e-12
    assert high.last_surface_traction_receipt["resolved_cell"]["policy"] == CELL_POLICY
    assert high.last_surface_traction_receipt["deposit_eligible_this_tick"] is True
    assert high.last_surface_traction_receipt["causal_latency"] == "NEXT_TICK"
    assert high.last_surface_traction_receipt["energy_interpretation"] == ENERGY_INTERPRETATION
    assert high.last_surface_traction_receipt["recipe_match"] is False
    assert high.last_surface_traction_receipt["deposit_consumed"] is False
    assert high.body.x > neutral.body.x > low.body.x

    neighbor = _runtime()
    _park(neighbor)
    _put(neighbor, 11, 10, "component_a", updated=-1)
    _move(neighbor, "MOVE:E")
    assert abs(_realized_x(neighbor) - _realized_x(bare)) < 1e-12
    assert neighbor.last_surface_traction_receipt is None

    wrapped = _runtime()
    width = int(wrapped.world.T.shape[1])
    _park(wrapped, x=-0.25, y=10.2)
    _put(wrapped, width - 1, 10, "component_a", updated=-1)
    _move(wrapped, "MOVE:E")
    assert abs(wrapped.last_surface_traction_receipt["traction_multiplier"] - 1.2) < 1e-12
    assert wrapped.last_surface_traction_receipt["resolved_cell"]["cell_x"] == width - 1


def test_effect_starts_on_the_next_tick_and_deposit_is_conserved():
    rt = _runtime()
    _park(rt, x=10.1, y=10.1)
    deposit = _put(rt, 10, 10, "component_a", updated=0)
    before = deposit.to_dict()
    control = _runtime()
    _park(control, x=10.1, y=10.1)
    _move(control, "MOVE:E")
    _move(rt, "MOVE:E")
    assert rt.last_surface_traction_receipt["deposit_eligible_this_tick"] is False
    assert rt.last_surface_traction_receipt["traction_multiplier"] == 1.0
    assert abs(_realized_x(rt) - _realized_x(control)) < 1e-12
    _move(rt, "MOVE:E")
    assert rt.last_surface_traction_receipt["deposit_eligible_this_tick"] is True
    assert abs(rt.last_surface_traction_receipt["traction_multiplier"] - 1.2) < 1e-12
    assert rt.world.surface_material_deposits[deposit.deposit_id].to_dict() == before
    again = _runtime()
    _park(again, x=10.2, y=10.2)
    _put(again, 10, 10, "component_a", updated=-1)
    first = _runtime()
    _park(first, x=10.2, y=10.2)
    _put(first, 10, 10, "component_a", updated=-1)
    _move(first, "MOVE:E")
    _move(again, "MOVE:E")
    assert abs(_realized_x(first) - _realized_x(again)) < 1e-12


def test_wait_push_contact_and_rest_are_unchanged():
    def pair(command: str, **motor):
        left = _runtime()
        right = _runtime()
        _park(left)
        _park(right)
        _put(right, 10, 10, "component_a", updated=-1)
        _move(left, command, **motor)
        _move(right, command, **motor)
        return left, right

    wait_bare, wait_deposit = pair("WAIT")
    assert abs(wait_bare.body.x - wait_deposit.body.x) < 1e-12
    assert abs(wait_bare.body.vx - wait_deposit.body.vx) < 1e-12
    assert wait_deposit.last_surface_traction_receipt is None
    push_bare, push_deposit = pair("WAIT", push=True)
    assert abs(push_bare.body.vx - push_deposit.body.vx) < 1e-12
    assert abs(push_bare.body.vy - push_deposit.body.vy) < 1e-12
    rest_bare, rest_deposit = pair("WAIT")
    rest_bare.body.vx = 0.001
    rest_deposit.body.vx = 0.001
    _move(rest_bare, "WAIT")
    _move(rest_deposit, "WAIT")
    assert abs(rest_bare.body.vx) < 1e-12 and abs(rest_deposit.body.vx) < 1e-12
    assert "surface_affinity" not in inspect.getsource(resolve_soft_contact)
    host = _runtime()
    cfg = host.config.body
    a = deepcopy(host.body)
    b = deepcopy(host.body)
    a.x, a.y, a.vx, a.vy = 4.0, 4.0, 0.1, 0.0
    b.x, b.y, b.vx, b.vy = 4.4, 4.0, -0.1, 0.0
    a2, b2 = deepcopy(a), deepcopy(b)
    first = resolve_soft_contact(a, b, cfg, cfg, width=32, height=32)
    second = resolve_soft_contact(a2, b2, cfg, cfg, width=32, height=32)
    assert first["impulse_a"] == second["impulse_a"]


def test_work_matches_realized_delta_v_without_a_negative_boost():
    rt = _runtime()
    _park(rt)
    _put(rt, 10, 10, "component_a", updated=-1)
    _move(rt, "MOVE:E")
    ledger = rt.last_action_work_ledger
    dv = ledger["action_dv_realized"]
    signed = ke_increment(float(rt.config.body.mass), 0.0, 0.0, float(dv[0]), float(dv[1]))
    assert abs(float(ledger["action_work_signed_realized"]) - signed) < 1e-9
    assert float(ledger["action_negative_work_realized"]) == 0.0
    assert float(ledger["action_work_realized"]) > 0.0
    receipt = rt.last_surface_traction_receipt
    assert abs(float(receipt["work_signed_realized"]) - signed) < 1e-9
    assert receipt["v_max_clamped"] is False
    assert receipt["energy_interpretation"] == ENERGY_INTERPRETATION
    clamped = _runtime()
    _park(clamped)
    clamped.body.vx = float(clamped.config.body.v_max) - 0.01
    _put(clamped, 10, 10, "component_a", updated=-1)
    _move(clamped, "MOVE:E")
    assert clamped.last_surface_traction_receipt["v_max_clamped"] is True
    assert abs(clamped.body.vx) <= float(clamped.config.body.v_max) + 1e-12


def test_snapshot_restore_and_missing_config():
    rt = _runtime()
    _park(rt)
    _put(rt, 10, 10, "component_a", updated=-1)
    _move(rt, "MOVE:E")
    snap = rt.snapshot()
    assert snap["config"]["surface_affinity_traction"]["enabled"] is True
    restored = PhysicalSystemRuntime.restore(deepcopy(snap))
    assert surface_affinity_traction_is_active(restored.config) is True
    _park(restored)
    _move(restored, "MOVE:E")
    assert abs(restored.last_surface_traction_receipt["traction_multiplier"] - 1.2) < 1e-12
    missing = deepcopy(snap)
    missing["config"].pop("surface_affinity_traction")
    off = PhysicalSystemRuntime.restore(missing)
    assert surface_affinity_traction_is_active(off.config) is False
    _park(off)
    bare = _runtime(traction=False)
    _park(bare)
    _put(bare, 10, 10, "component_a", updated=-1)
    _put(off, 10, 10, "component_a", updated=-1)
    _move(off, "MOVE:E")
    _move(bare, "MOVE:E")
    assert abs(_realized_x(off) - _realized_x(bare)) < 1e-12
    old = _runtime(traction=False).snapshot()
    old["config"].pop("surface_affinity_traction", None)
    compatible = PhysicalSystemRuntime.restore(old)
    assert surface_affinity_traction_is_active(compatible.config) is False
    from mechanistic_mind.physical_system.explicit_surface_deposition import explicit_surface_deposition_is_active
    assert explicit_surface_deposition_is_active(compatible.config) is True


def test_cognition_leakage_observer_and_analyzer():
    rt = _runtime()
    _park(rt)
    _put(rt, 10, 10, "component_a", updated=-1)
    _move(rt, "MOVE:E")
    assert audit_cognition_payload(rt.agent_observation()) == []
    assert audit_cognition_payload(rt.cognition) == []
    frame = world_frame(rt)
    row = frame["surface_material_deposits"][0]
    assert row["researcher_only"] is True
    assert row["agent_accessible"] is False
    assert abs(float(row["traction_multiplier"]) - 1.2) < 1e-12
    assert row["not_a_recipe"] is True
    assert frame["surface_traction_researcher_only"] is True
    receipt = rt.last_surface_traction_receipt
    assert receipt["event"] == EVENT_APPLIED
    assert receipt["causal_source"] == "LOCAL_SURFACE_MATERIAL_PROPERTY"
    assert receipt["derivation_version"] == DERIVATION_VERSION
    assert receipt["deposition_event_ids"] == ["surface-deposition-origin"]
    summary = summarize_surface_traction([
        {"type": "RESOURCE_CHANGE", "evidence": {"amount": 3}},
        {"type": "SURFACE_DEPOSITION_COMMITTED", "evidence": {"event": "SURFACE_DEPOSITION_COMMITTED", "committed": True}},
        {"type": receipt["event"], "evidence": receipt},
    ])
    assert summary["move_attempts_on_deposited_cells"] == 1
    assert summary["high_multiplier_count"] == 1
    assert summary["deposit_state_conserved_across_traversal"] is True
    assert summary["TRACTION_CAUSAL_EFFECT"] == TRACTION_CAUSAL_EFFECT
    assert summary["AGENT_SYMBOLIC_TRACTION_SENSOR"] == AGENT_SYMBOLIC_TRACTION_SENSOR
    assert summary["RECIPE_SYSTEM"] == RECIPE_SYSTEM
    assert summary["INSTRUMENTAL_USE"] == INSTRUMENTAL_USE
    assert summary["LEARNING_FROM_TRACTION"] == LEARNING_FROM_TRACTION
    assert summary["mixed_with_resource_change"] is False
    assert "recognition" in summary["NOT_ESTABLISHED"]
    deposition = summarize_surface_depositions([
        {"type": receipt["event"], "evidence": receipt},
    ])
    assert deposition["deposition_attempts"] == 0
    left, right = list(rt.world.resource_objects)
    left.physical_state = PHYSICAL_STATE_HELD
    left.holder_body_id = "agent_0"
    left.manipulator_id = MANIP_LEFT
    right.physical_state = PHYSICAL_STATE_HELD
    right.holder_body_id = "agent_0"
    right.manipulator_id = MANIP_RIGHT
    rt.pair_aperture = 0.4
    _move(rt, "WAIT")
    _move(rt, "WAIT", manipulator_pair="COMBINE")
    assert rt.last_material_transformation_receipt["outcome"] == "MERGE_COMMITTED"
    survivor = rt.world.resource_objects[0]
    derived = derive_effective_properties(survivor.composition)
    assert abs(derived["surface_affinity"] - 0.5) < 1e-9
    assert traction_multiplier(derived["surface_affinity"]) == 1.0
