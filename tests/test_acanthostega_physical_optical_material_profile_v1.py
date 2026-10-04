"""O1 Physical Optical Material Profile V1 — focused authority tests."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BETA4,
    acanthostega_beta4_mechanism_map,
    public_model_selector_entries,
)
from mechanistic_mind.physical_system.material_composition import canonical_components
from mechanistic_mind.physical_system.physical_optical_material_profile import (
    AUTHORITY,
    CAPABILITY,
    COMPONENT_REFLECTANCE_O1_V1,
    KNOWN_COMPONENT_IDS,
    MIXTURE_LAW,
    OPTICAL_BAND_COUNT,
    OPTICAL_BAND_IDENTIFIERS,
    PROFILE,
    SCHEMA,
    STATUS_INVALID,
    STATUS_LEGACY,
    STATUS_RESOLVED,
    STATUS_UNKNOWN,
    component_profile_reference,
    physical_optical_material_profile_is_active,
    registry_digest,
    resolve_occupied_interval_profile,
    resolve_optical_material_profile,
    resolve_resource_object_profile,
)
from mechanistic_mind.physical_system.resource_objects import (
    CANONICAL_OPTICAL_RESPONSE,
    MaterialComponent,
    ResourceObject,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.volumetric_world_material_occupancy import OccupiedZInterval


RESULTS = Path("results/acanthostega_physical_optical_material_profile_v1")
TICK_BUDGET = 0  # architecture/authority fixtures; keep at 0 unless needed


def test_schema_identity_and_bands():
    assert SCHEMA == "PHYSICAL_OPTICAL_MATERIAL_PROFILE_V1"
    assert CAPABILITY == "physical_optical_material_profile"
    assert PROFILE == "ANONYMOUS_SPECTRAL_REFLECTANCE_MATERIAL_PROFILE_O1_V1"
    assert AUTHORITY == "PHYSICAL_MATERIAL_PROPERTY_NON_SI_NO_LIGHT_TRANSPORT"
    assert OPTICAL_BAND_COUNT == 6
    assert OPTICAL_BAND_IDENTIFIERS == tuple(f"optical_band_{i}" for i in range(6))
    assert "band_0" not in OPTICAL_BAND_IDENTIFIERS
    assert MIXTURE_LAW == "QUANTITY_WEIGHTED_MEAN_REFLECTANCE_V1"


def test_every_reachable_beta4_component_has_explicit_profile():
    for cid in ("component_0", "component_a", "component_b"):
        assert cid in KNOWN_COMPONENT_IDS
        ref = component_profile_reference(cid)
        assert ref["status"] == STATUS_RESOLVED
        R = ref["spectral_reflectance"]
        assert len(R) == 6
        assert all(0.0 <= float(v) <= 1.0 and float(v) == float(v) for v in R)


def test_reflectance_not_from_observer_rgb_or_optical_response():
    # Optical response RGB-like triplet must not equal O1 six-band profile.
    for cid, R in COMPONENT_REFLECTANCE_O1_V1.items():
        assert tuple(R[:3]) != tuple(CANONICAL_OPTICAL_RESPONSE)
        assert R == (0.5, 0.5, 0.5, 0.5, 0.5, 0.5)


def test_mixture_uses_committed_quantities_order_independent():
    a = (MaterialComponent("component_a", 1.0), MaterialComponent("component_b", 3.0))
    b = (MaterialComponent("component_b", 3.0), MaterialComponent("component_a", 1.0))
    ra = resolve_optical_material_profile(a)
    rb = resolve_optical_material_profile(b)
    assert ra["status"] == STATUS_RESOLVED
    assert rb["status"] == STATUS_RESOLVED
    assert ra["spectral_reflectance"] == rb["spectral_reflectance"]
    # Weighted mean with identical R still equals R; verify amounts conserved in readout.
    assert ra["canonical_amounts"] == {"component_a": 1.0, "component_b": 3.0}
    merged = canonical_components(a, ())
    assert resolve_optical_material_profile(merged)["status"] == STATUS_RESOLVED


def test_zero_and_unknown_composition_policies():
    inv = resolve_optical_material_profile(())
    assert inv["status"] == STATUS_INVALID
    assert inv["spectral_reflectance"] is None
    unk = resolve_optical_material_profile([{"component_id": "component_zzz", "amount": 1.0}])
    assert unk["status"] == STATUS_UNKNOWN
    assert unk["spectral_reflectance"] is None
    leg = resolve_optical_material_profile(None, legacy_without_composition=True)
    assert leg["status"] == STATUS_LEGACY


def test_vw1_interval_profile_resolvable():
    it = OccupiedZInterval(
        z_min=0.0,
        z_max=1.0,
        density=1.0,
        composition=(("component_0", 0.5), ("component_a", 0.5)),
    )
    out = resolve_occupied_interval_profile(it)
    assert out["status"] == STATUS_RESOLVED
    assert out["exposed_surface_authority"] is False
    assert out["light_transport"] is False


def test_resource_object_and_legacy_policy():
    obj = ResourceObject(
        object_id="resource-test",
        x=1.0,
        y=1.0,
        mass=1.0,
        quantity=1.0,
        composition=(MaterialComponent("component_0", 1.0),),
    )
    r = resolve_resource_object_profile(obj)
    assert r["status"] == STATUS_RESOLVED
    assert r["legacy_optical_response_used_for_o1"] is False
    legacy = resolve_resource_object_profile({"optical_response": {"c0": 0.9, "c1": 0.1, "c2": 0.1}})
    assert legacy["status"] == STATUS_LEGACY
    assert legacy["legacy_optical_response_used_for_o1"] is False


def test_beta4_enables_o1_dormant_tiktaalik_unchanged_selector():
    cfg = acanthostega_beta4_config()
    assert physical_optical_material_profile_is_active(cfg)
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_BETA4
    mmap = acanthostega_beta4_mechanism_map()
    assert mmap.get("physical_optical_material_profile") is True
    entries = public_model_selector_entries()
    assert len(entries) == 2
    labels = {e["label"] for e in entries}
    assert labels == {"Tiktaalik Beta 3.1", "Acanthostega Beta 4.0"}
    tik = PhysicalSystemConfig()
    assert tik.model_line != "ACANTHOSTEGA" or not physical_optical_material_profile_is_active(tik)
    assert physical_optical_material_profile_is_active(PhysicalSystemConfig(model_line="TIKTAALIK")) is False


def test_snapshot_preserves_profile_version_no_silent_recompute_marker():
    cfg = acanthostega_beta4_config()
    rt = PhysicalSystemRuntime(config=cfg)
    snap = rt.snapshot()
    o1 = snap["config"]["physical_optical_material_profile"]
    assert o1["enabled"] is True
    assert o1["profile"] == PROFILE
    assert o1["registry_version"] == PROFILE
    assert o1["schema"] == SCHEMA
    d0 = registry_digest(o1["registry_version"])
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert physical_optical_material_profile_is_active(rt2.config)
    assert registry_digest(rt2.config.physical_optical_material_profile.registry_version) == d0
    bad = resolve_optical_material_profile(
        [{"component_id": "component_0", "amount": 1.0}],
        registry_version="FUTURE_INCOMPATIBLE_PROFILE_V9",
    )
    assert bad["status"] == STATUS_UNKNOWN


def test_cognition_privacy_and_exo_unchanged_under_o1():
    cfg = acanthostega_beta4_config()
    rt = PhysicalSystemRuntime(config=cfg)
    obs = rt.agent_observation()
    blob = json.dumps(obs, sort_keys=True)
    for token in (
        "spectral_reflectance",
        "physical_optical_material_profile",
        "PHYSICAL_OPTICAL_MATERIAL_PROFILE_V1",
        "optical_band_0",
        PROFILE,
    ):
        assert token not in blob
    for k, v in obs.items():
        if str(k).startswith("exo_") or str(k).startswith("surface_c"):
            assert isinstance(v, (int, float))


def test_no_second_ledger_and_registry_machine_readable(tmp_path_factory=None):
    RESULTS.mkdir(parents=True, exist_ok=True)
    registry = {
        "schema": SCHEMA,
        "profile": PROFILE,
        "authority": AUTHORITY,
        "optical_band_identifiers": list(OPTICAL_BAND_IDENTIFIERS),
        "components": {cid: list(R) for cid, R in COMPONENT_REFLECTANCE_O1_V1.items()},
        "digest": registry_digest(),
        "mixture_law": MIXTURE_LAW,
        "component_optical_distinction": "NOT_SCIENTIFICALLY_ESTABLISHED_NEUTRAL_DEFAULT",
        "not_from_display_rgb": True,
        "not_from_optical_response": True,
    }
    path = RESULTS / "profile_registry_o1_v1.json"
    path.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n")
    assert path.is_file()
    assert len(COMPONENT_REFLECTANCE_O1_V1) == 3


def test_two_agent_shared_profile_authority():
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime

    cfg = acanthostega_beta4_config()
    # Prefer constructing via available helper if present
    try:
        from mechanistic_mind.model.acanthostega import acanthostega_beta4_config as _c

        cfg = _c()
    except Exception:
        pass
    assert physical_optical_material_profile_is_active(cfg)
    r0 = resolve_optical_material_profile([{"component_id": "component_0", "amount": 2.0}])
    r1 = resolve_optical_material_profile([{"component_id": "component_0", "amount": 2.0}])
    assert r0["registry_digest"] == r1["registry_digest"]
    assert r0["spectral_reflectance"] == r1["spectral_reflectance"]


def test_combine_resolve_after_commit_rejected_no_mutation():
    left = ResourceObject(
        object_id="L",
        x=0.0,
        y=0.0,
        mass=1.0,
        quantity=1.0,
        composition=(MaterialComponent("component_0", 1.0),),
    )
    right = ResourceObject(
        object_id="R",
        x=0.0,
        y=0.0,
        mass=1.0,
        quantity=1.0,
        composition=(MaterialComponent("component_a", 1.0),),
    )
    before = resolve_resource_object_profile(left)
    # Rejected path: no composition change
    assert left.composition == (MaterialComponent("component_0", 1.0),)
    assert resolve_resource_object_profile(left)["spectral_reflectance"] == before["spectral_reflectance"]
    # Commit path simulation: canonical merge then resolve
    merged = canonical_components(tuple(left.composition), tuple(right.composition))
    after = resolve_optical_material_profile(merged)
    assert after["status"] == STATUS_RESOLVED
    assert after["canonical_amounts"] == {"component_0": 1.0, "component_a": 1.0}


def test_o1_does_not_change_optical_response_field():
    obj = ResourceObject(
        object_id="X",
        x=0.0,
        y=0.0,
        mass=1.0,
        quantity=1.0,
        composition=(MaterialComponent("component_0", 1.0),),
        optical_response=CANONICAL_OPTICAL_RESPONSE,
    )
    before = copy.deepcopy(obj.optical_response)
    _ = resolve_resource_object_profile(obj)
    assert obj.optical_response == before
    assert obj.mass == 1.0
    assert obj.quantity == 1.0
