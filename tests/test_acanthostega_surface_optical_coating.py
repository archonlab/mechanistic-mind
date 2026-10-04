"""Anonymous surface optical coating. No material sensor and no new learner."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.acanthostega import (
    acanthostega_surface_optical_config,
    acanthostega_traction_adaptation_config,
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
    PRESET_ACANTHOSTEGA_SURFACE_DEPOSITION,
    PRESET_ACANTHOSTEGA_SURFACE_OPTICAL,
    PRESET_ACANTHOSTEGA_SURFACE_TRACTION,
    PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
    PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE,
    PRESET_BETA31,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.explicit_surface_deposition import (
    SurfaceMaterialDeposit,
    deposit_id_for_cell,
)
from mechanistic_mind.physical_system.mechanism_registry import set_mechanism
from mechanistic_mind.physical_system.near_field_exteroception import sample_near_field
from mechanistic_mind.physical_system.observation import audit_cognition_payload
from mechanistic_mind.physical_system.passive_material_properties import derive_effective_properties
from mechanistic_mind.physical_system.physical_surface_optical_coating import (
    DERIVATION_VERSION,
    EVENT_OBSERVED,
    MECHANISM_ID,
    OPTICAL_VARIANT_A,
    OPTICAL_VARIANT_B,
    coat_cell_optical,
    coverage_from_quantity,
    mix_coating,
    mix_survivor_optical,
    physical_surface_optical_coating_is_active,
    quantity_weighted_optical,
    transfer_optical_on_deposition,
)
from mechanistic_mind.physical_system.resource_objects import (
    CANONICAL_OPTICAL_RESPONSE,
    MaterialComponent,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.sensorimotor_consequence import (
    FAMILY_VISUAL,
    extract_sensory,
    sensory_signature,
)
from mechanistic_mind.physical_system.surface_affinity_traction import (
    traction_contrast_spawn_objects,
    traction_multiplier,
)
from mechanistic_mind.physical_system.surface_traction_prediction import _context_hash
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.scientific_v3.surface_optical_summary import format_surface_optical_section
from mechanistic_mind.ui.psy_observer_web.serialize import header_info, world_frame

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
    PRESET_ACANTHOSTEGA_SURFACE_TRACTION,
    PRESET_ACANTHOSTEGA_TRACTION_EXPERIENCE,
    PRESET_ACANTHOSTEGA_TRACTION_ADAPTATION,
)
SURFACE_KEYS = tuple(k for k in FAMILY_VISUAL if k.startswith("surface_"))
FORBIDDEN = (
    "deposit_id",
    "component_id",
    "component_a",
    "component_b",
    "surface_affinity",
    "traction_multiplier",
    "SLIPPERY",
    "STICKY",
    "physical_surface_optical_coating",
    "SURFACE_OPTICAL_COATING",
    "SURFACE_OPTICAL_COATING_OBSERVED",
    "SURFACE_OPTICAL_COATING_V1",
    "material_identity",
)


def _runtime(seed: int = 17) -> PhysicalSystemRuntime:
    return PhysicalSystemRuntime(seed=seed, config=acanthostega_surface_optical_config())


def _park(rt: PhysicalSystemRuntime) -> None:
    rt.body.x = 10.2
    rt.body.y = 10.2
    rt.body.vx = 0.0
    rt.body.vy = 0.0
    rt.body.theta = 0.0
    rt.body.omega = 0.0


def _base_triplet(rt: PhysicalSystemRuntime, cell_x: int = 11, cell_y: int = 10):
    optical = rt.world.surface_optical
    return tuple(float(optical[k, cell_y, cell_x]) for k in range(3))


def _put(rt: PhysicalSystemRuntime, optical, quantity: float, component: str = "component_0", *, cell=(11, 10)):
    rt.world.surface_material_deposits.clear()
    if optical is None:
        return None
    deposit = SurfaceMaterialDeposit(
        deposit_id=deposit_id_for_cell(cell[0], cell[1]),
        cell_x=cell[0],
        cell_y=cell[1],
        mass=float(quantity),
        quantity=float(quantity),
        composition=(MaterialComponent(component, 1.0),),
        provenance={"lineage_refs": [{"event_id": "setup-deposit", "tick": -1}]},
        created_tick=-1,
        last_updated_tick=-1,
        optical_response=tuple(optical),
        optical_derivation_version=DERIVATION_VERSION,
        optical_source_event_ids=("setup-deposit",),
    )
    rt.world.surface_material_deposits[deposit.deposit_id] = deposit
    rt.world.surface_optical_coating_generation = int(
        getattr(rt.world, "surface_optical_coating_generation", 0) or 0
    ) + 1
    return deposit


def _surface(obs: dict) -> dict[str, float]:
    return {key: float(obs.get(key, 0.0)) for key in SURFACE_KEYS}


def _context(obs: dict) -> str:
    signature = sensory_signature(extract_sensory(obs, FAMILY_VISUAL), FAMILY_VISUAL)
    return _context_hash(signature)


def _close(a: dict, b: dict, tol: float = 1e-9) -> bool:
    return all(abs(a[key] - b[key]) <= tol for key in SURFACE_KEYS)


class _Spectrum:
    def __init__(self, optical):
        self.optical_response = optical


def test_fingerprint_previous_presets_and_tiktaalik_vision():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN_BETA31_FP_SEED17
    assert MECHANISM_ID not in beta31_mechanism_map()
    for name in PREVIOUS:
        assert MECHANISM_ID not in preset_canonical(name, seed=17)["mechanisms"]
    fresh = preset_canonical(PRESET_ACANTHOSTEGA_SURFACE_OPTICAL, seed=17)
    assert fresh["mechanisms"][MECHANISM_ID] is True
    assert fresh["mechanisms"]["sensorimotor_consequence_model"] is True
    assert fresh["vision"]["visual_surface_discrimination"] == "RICH"
    assert normalize_preset_name("Acanthostega Phase A Surface Optical") == PRESET_ACANTHOSTEGA_SURFACE_OPTICAL
    assert normalize_preset_name("ACANTHOSTEGA PHASE A SURFACE OPTICAL") == PRESET_ACANTHOSTEGA_SURFACE_OPTICAL
    assert normalize_preset_name(PRESET_ACANTHOSTEGA_SURFACE_OPTICAL) != PRESET_ACANTHOSTEGA_GENTLE
    adaptation = acanthostega_traction_adaptation_config()
    assert physical_surface_optical_coating_is_active(adaptation) is False
    cfg = acanthostega_surface_optical_config()
    assert physical_surface_optical_coating_is_active(cfg) is True
    assert cfg.cognition.prediction_error_revision is False
    assert traction_multiplier(0.75) == 1.2
    assert traction_multiplier(0.25) == 0.8
    left = traction_contrast_spawn_objects()[0]["optical_c0"]
    right = traction_contrast_spawn_objects()[1]["optical_c0"]
    assert abs(left - CANONICAL_OPTICAL_RESPONSE[0]) < 1e-12
    assert abs(right - CANONICAL_OPTICAL_RESPONSE[0]) < 1e-12
    spawned = cfg.physical_resource_objects.spawn_objects
    assert abs(spawned[0]["optical_c0"] - OPTICAL_VARIANT_A[0]) < 1e-12
    assert abs(spawned[1]["optical_c0"] - OPTICAL_VARIANT_B[0]) < 1e-12
    tik_a = PhysicalSystemRuntime(seed=17, config=tiktaalik_config())
    tik_b_cfg = tiktaalik_config()
    set_mechanism(tik_b_cfg, MECHANISM_ID, True)
    tik_b_cfg.near_field_exteroception.surface_optical_coating_enabled = True
    tik_b = PhysicalSystemRuntime(seed=17, config=tik_b_cfg)
    assert physical_surface_optical_coating_is_active(tik_b.config) is False
    assert tik_a.agent_observation() == tik_b.agent_observation()
    catalog = {row["id"] for row in tik_b.mechanisms()["mechanisms"]}
    assert MECHANISM_ID not in catalog


def test_coverage_law_and_neutral_noop():
    base = (0.40, 0.50, 0.60)
    assert coverage_from_quantity(0.0) == 0.0
    assert abs(coverage_from_quantity(0.5) - 0.5) < 1e-12
    assert coverage_from_quantity(4.0) == 1.0
    assert mix_coating(base, OPTICAL_VARIANT_A, 0.0) == mix_coating(base, OPTICAL_VARIANT_A, -1.0)
    half = mix_coating(base, OPTICAL_VARIANT_A, 0.5)
    assert abs(half[0] - (0.5 * base[0] + 0.5 * OPTICAL_VARIANT_A[0])) < 1e-12
    assert mix_coating(base, OPTICAL_VARIANT_A, 2.0) == mix_coating(base, OPTICAL_VARIANT_A, 1.0)
    assert mix_coating(base, base, 0.7) == tuple(float(v) for v in base) or all(
        abs(mix_coating(base, base, 0.7)[i] - base[i]) < 1e-12 for i in range(3)
    )
    rt = _runtime()
    _park(rt)
    empty = _surface(rt.agent_observation())
    terrain = _base_triplet(rt)
    _put(rt, terrain, 1.0)
    neutral = _surface(rt.agent_observation())
    assert _close(empty, neutral)
    _put(rt, OPTICAL_VARIANT_A, 0.0)
    assert _close(empty, _surface(rt.agent_observation()))
    _put(rt, OPTICAL_VARIANT_A, 0.5)
    snf = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True,
    )
    row = next(r for r in snf["neighbors"] if r["cell"] == [11, 10])
    expected = mix_coating(terrain, OPTICAL_VARIANT_A, 0.5)
    for index, value in enumerate(expected):
        assert abs(float(row["surface_optical"][index]) - value) < 1e-9
    _put(rt, OPTICAL_VARIANT_A, 5.0)
    snf = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True,
    )
    row = next(r for r in snf["neighbors"] if r["cell"] == [11, 10])
    for index, value in enumerate(OPTICAL_VARIANT_A):
        assert abs(float(row["surface_optical"][index]) - value) < 1e-9
    assert row["surface_optical_coating"]["coverage"] == 1.0


def test_transfer_repeat_and_merge_are_quantity_weighted():
    cfg = acanthostega_surface_optical_config()
    rt = _runtime()
    source = _Spectrum(OPTICAL_VARIANT_A)
    deposit = SurfaceMaterialDeposit(
        deposit_id=deposit_id_for_cell(11, 10),
        cell_x=11, cell_y=10, mass=0.25, quantity=0.25,
        composition=(MaterialComponent("component_a", 0.25),),
        provenance={}, created_tick=1, last_updated_tick=1,
    )
    transfer_optical_on_deposition(cfg, rt.world, deposit, None, source, 0.25, "event-a")
    assert deposit.optical_response == OPTICAL_VARIANT_A
    assert source.optical_response == OPTICAL_VARIANT_A
    again = SurfaceMaterialDeposit(
        deposit_id=deposit.deposit_id, cell_x=11, cell_y=10, mass=1.0, quantity=1.0,
        composition=deposit.composition, provenance={}, created_tick=1, last_updated_tick=2,
    )
    transfer_optical_on_deposition(cfg, rt.world, again, deposit, _Spectrum(OPTICAL_VARIANT_B), 0.75, "event-b")
    expected = quantity_weighted_optical([
        (OPTICAL_VARIANT_A, 0.25),
        (OPTICAL_VARIANT_B, 0.75),
    ])
    for index in range(3):
        assert abs(again.optical_response[index] - expected[index]) < 1e-12
    assert again.optical_source_event_ids == ("event-a", "event-b")
    forward = quantity_weighted_optical([(OPTICAL_VARIANT_A, 0.4), (OPTICAL_VARIANT_B, 0.6)])
    reverse = quantity_weighted_optical([(OPTICAL_VARIANT_B, 0.6), (OPTICAL_VARIANT_A, 0.4)])
    for index in range(3):
        assert abs(forward[index] - reverse[index]) < 1e-12
    left = _Spectrum(OPTICAL_VARIANT_A)
    right = _Spectrum(OPTICAL_VARIANT_B)
    mix_survivor_optical(cfg, left, right, 1.0, 3.0)
    merged = quantity_weighted_optical([(OPTICAL_VARIANT_A, 1.0), (OPTICAL_VARIANT_B, 3.0)])
    for index in range(3):
        assert abs(left.optical_response[index] - merged[index]) < 1e-12
    untouched = _Spectrum(OPTICAL_VARIANT_A)
    mix_survivor_optical(acanthostega_traction_adaptation_config(), untouched, right, 1.0, 3.0)
    assert untouched.optical_response == OPTICAL_VARIANT_A
    old = SurfaceMaterialDeposit.from_dict({
        "deposit_id": "surface-deposit-x1-y1",
        "cell_x": 1, "cell_y": 1, "mass": 0.1, "quantity": 0.1,
        "composition": [{"component_id": "component_0", "amount": 0.1}],
        "provenance": {}, "created_tick": 0, "last_updated_tick": 0,
    })
    assert old.optical_response is None
    assert "optical_response" not in old.to_dict()


def test_optics_and_traction_are_independent():
    rt = _runtime()
    _park(rt)
    _put(rt, OPTICAL_VARIANT_A, 1.0, "component_a")
    same_a = _surface(rt.agent_observation())
    _put(rt, OPTICAL_VARIANT_A, 1.0, "component_b")
    same_b = _surface(rt.agent_observation())
    assert _close(same_a, same_b)
    assert traction_multiplier(derive_effective_properties(
        (MaterialComponent("component_a", 1.0),)
    )["surface_affinity"]) == 1.2
    assert traction_multiplier(derive_effective_properties(
        (MaterialComponent("component_b", 1.0),)
    )["surface_affinity"]) == 0.8
    _put(rt, OPTICAL_VARIANT_B, 1.0, "component_a")
    other = _surface(rt.agent_observation())
    assert not _close(same_a, other, tol=1e-6)
    assert derive_effective_properties((MaterialComponent("component_a", 1.0),))["surface_affinity"] == 0.75
    off = PhysicalSystemRuntime(seed=17, config=acanthostega_traction_adaptation_config())
    _park(off)
    before = _surface(off.agent_observation())
    _put(off, OPTICAL_VARIANT_B, 1.0, "component_b")
    assert physical_surface_optical_coating_is_active(off.config) is False
    assert _close(before, _surface(off.agent_observation()))


def test_pre_action_fields_differ_and_smc_bucket_does_not():
    rt = _runtime()
    _park(rt)
    empty = rt.agent_observation()
    terrain = _base_triplet(rt)
    _put(rt, terrain, 1.0)
    neutral = rt.agent_observation()
    _put(rt, OPTICAL_VARIANT_A, 1.0)
    variant_a = rt.agent_observation()
    _put(rt, OPTICAL_VARIANT_B, 1.0)
    variant_b = rt.agent_observation()
    assert _close(_surface(empty), _surface(neutral))
    assert not _close(_surface(variant_a), _surface(variant_b), tol=1e-4)
    assert not _close(_surface(empty), _surface(variant_a), tol=1e-4)
    assert _context(variant_a) == _context(variant_b) == _context(empty)
    for obs in (empty, neutral, variant_a, variant_b):
        assert audit_cognition_payload(obs) == []
        blob = repr(obs)
        assert all(token not in blob for token in FORBIDDEN)
    text = format_surface_optical_section({
        "causal_sequence": "deposition at T → coated surface at observation T+1",
        "coating_observation_ticks": 1,
        "coverage_values": [1.0],
        "visible_count": 1,
        "occluded_count": 0,
        "pre_action_context_discrimination": "NOT_OBSERVED",
        "perceptually_conditioned_prediction": "NOT_AVAILABLE",
        "OBSERVED": ["coated_surface_sample"],
        "DERIVED": ["coverage"],
        "NOT_ESTABLISHED": ["material_identity_recognition", "instrumental_use"],
    })
    assert "PHYSICAL SURFACE OPTICAL COATING" in text
    assert "PRE_ACTION_CONTEXT_DISCRIMINATION = NOT_OBSERVED" in text
    assert "PERCEPTUALLY_CONDITIONED_PREDICTION = NOT_AVAILABLE" in text
    assert "INSTRUMENTAL_USE = NOT_ESTABLISHED" in text


def test_visibility_geometry_occlusion_and_two_agents():
    rt = _runtime()
    _park(rt)
    _put(rt, OPTICAL_VARIANT_A, 1.0)
    facing = _surface(rt.agent_observation())
    rt.body.theta = 3.141592653589793
    behind = _surface(rt.agent_observation())
    rt.world.surface_material_deposits.clear()
    rt.world.surface_optical_coating_generation += 1
    behind_empty = _surface(rt.agent_observation())
    assert _close(behind, behind_empty, tol=1e-9)
    rt.body.theta = 0.0
    rt.body.x = 8.2
    outside_empty = _surface(rt.agent_observation())
    _put(rt, OPTICAL_VARIANT_A, 1.0)
    rt.body.x = 8.2
    rt.body.theta = 0.0
    outside = _surface(rt.agent_observation())
    _park(rt)
    _put(rt, None, 0.0)
    empty_facing = _surface(rt.agent_observation())
    assert not _close(facing, empty_facing, tol=1e-4)
    assert _close(outside, outside_empty, tol=1e-9)
    _park(rt)
    _put(rt, OPTICAL_VARIANT_A, 1.0)
    rt.config.near_field_exteroception.illumination_enabled = False
    rt.config.near_field_exteroception.illumination_frozen = 1.0
    bright = _surface(rt.agent_observation())
    rt.config.near_field_exteroception.illumination_frozen = 0.25
    dim = _surface(rt.agent_observation())
    assert sum(dim.values()) < sum(bright.values())
    rt.config.near_field_exteroception.illumination_enabled = True
    rt.config.near_field_exteroception.illumination_frozen = None
    rt.config.near_field_exteroception.radius = 3
    rt.config.near_field_exteroception.spatial_vision = "OCCLUSION"
    _put(rt, OPTICAL_VARIANT_A, 1.0, cell=(13, 10))
    occluded = rt.agent_observation()
    snf = sample_near_field(
        world=rt.world, body=rt.body, cfg=rt.config.near_field_exteroception, diagnostic=True,
    )
    far = next(r for r in snf["neighbors"] if r["cell"] == [13, 10])
    assert far["visibility"] == "OCCLUDED"
    assert float(far["visible_contribution"]) == 0.0
    rt.world.surface_material_deposits.clear()
    rt.world.surface_optical_coating_generation += 1
    assert _close(_surface(occluded), _surface(rt.agent_observation()), tol=1e-9)
    pair = TwoAgentRuntime(seed=17, config=acanthostega_surface_optical_config(), process_order=(0, 1))
    _put(pair.slots[0], OPTICAL_VARIANT_A, 1.0)
    pair.slots[0].body.x, pair.slots[0].body.y, pair.slots[0].body.theta = 10.2, 10.2, 0.0
    pair.slots[1].body.x, pair.slots[1].body.y, pair.slots[1].body.theta = 12.2, 10.2, 0.0
    view_near = pair.slots[0].agent_observation(foreign_bodies=pair.foreign_bodies_for(0))
    view_far = pair.slots[1].agent_observation(foreign_bodies=pair.foreign_bodies_for(1))
    assert not _close(_surface(view_near), _surface(view_far), tol=1e-4)
    assert audit_cognition_payload(view_near) == []
    assert any(row.get("event") == EVENT_OBSERVED for row in pair.slots[0].surface_optical_coating_history)


def test_causality_cache_snapshot_and_constant_lookup():
    rt = _runtime()
    _park(rt)
    before = dict(rt.agent_observation())
    quantity_before = 0.0
    deposit = _put(rt, OPTICAL_VARIANT_A, 1.0)
    after = rt.agent_observation()
    assert _close(_surface(before), _surface(before))
    assert not _close(_surface(before), _surface(after), tol=1e-4)
    assert deposit.quantity == 1.0
    again = rt.agent_observation()
    assert deposit.quantity == 1.0
    assert _close(_surface(after), _surface(again))
    assert quantity_before == 0.0
    frame = world_frame(rt)
    row = next(item for item in frame["surface_material_deposits"] if item["cell_x"] == 11)
    assert abs(float(row["optical_c0"]) - OPTICAL_VARIANT_A[0]) < 1e-9
    assert row["researcher_only"] is True
    assert row["not_a_traction_label"] is True
    assert header_info(rt, status="PAUSED", mode="LIVE", target_tick=None)["physical_surface_optical_coating"] is True
    snap = deepcopy(rt.snapshot())
    restored = PhysicalSystemRuntime.restore(snap)
    _park(restored)
    assert _close(_surface(after), _surface(restored.agent_observation()))
    restored_deposit = next(iter(restored.world.surface_material_deposits.values()))
    assert abs(restored_deposit.quantity - 1.0) < 1e-12
    assert int(getattr(restored.world, "surface_optical_coating_generation", 0)) == int(
        getattr(rt.world, "surface_optical_coating_generation", 0)
    )
    old = PhysicalSystemRuntime(seed=17, config=acanthostega_traction_adaptation_config())
    old_snap = old.snapshot()
    old_snap["config"].pop("physical_surface_optical_coating", None)
    revived = PhysicalSystemRuntime.restore(old_snap)
    assert physical_surface_optical_coating_is_active(revived.config) is False
    _park(revived)
    bare = _surface(revived.agent_observation())
    _put(revived, OPTICAL_VARIANT_B, 1.0)
    assert _close(bare, _surface(revived.agent_observation()))

    class _Counting(dict):
        def __init__(self):
            super().__init__()
            self.gets = 0

        def get(self, key, default=None):
            self.gets += 1
            return super().get(key, default)

    counting = _Counting()
    for index in range(40):
        counting[f"other-{index}"] = deposit
    counting[deposit.deposit_id] = deposit
    rt.world.surface_material_deposits = counting
    coated, info = coat_cell_optical(rt.world, 11, 10, (0.2, 0.2, 0.2))
    assert counting.gets == 1
    assert info is not None
    assert abs(coated[0] - OPTICAL_VARIANT_A[0]) < 1e-9
    assert deposit.quantity == 1.0
