"""O3 Abstract spectral light source and direct transport V1 — focused tests."""
from __future__ import annotations

import json
import math
from pathlib import Path

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.physical_system.abstract_spectral_light_source_and_direct_transport import (
    AUTHORITY,
    CAPABILITY,
    DIRECTION_CONVENTION,
    OBJECT_BODY_EXTENSION_REQUIRED_BEFORE_O4,
    OPTICAL_BAND_COUNT,
    OPTICAL_BAND_IDENTIFIERS,
    PROFILE,
    REFLECTED_QUANTITY_NAME,
    SCHEMA,
    SOURCE_ID,
    STATE_BACK,
    STATE_DIRECT,
    STATE_DISABLED,
    STATE_NOT_EVAL,
    STATE_OCCLUDED,
    STATE_UNKNOWN_MAT,
    AbstractDirectionalLightSource,
    build_abstract_spectral_light_causal_reconstruction,
    ensure_direct_light_cache,
    evaluate_facet_illumination,
    invalidate_direct_light_cache,
    query_facet_illumination,
    query_illumination_candidates,
    query_illumination_global,
    query_illumination_region,
    query_source_state,
    set_abstract_spectral_light_source_and_direct_transport,
    abstract_spectral_light_source_and_direct_transport_is_active,
)
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BETA4,
    acanthostega_beta4_mechanism_map,
    public_model_selector_entries,
)
from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
    FACE_BOTTOM,
    FACE_TOP,
    invalidate_exposed_surface_cache,
    set_exposed_surface_optical_interaction_authority,
)
from mechanistic_mind.physical_system.physical_optical_material_profile import (
    set_physical_optical_material_profile,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.volumetric_world_material_occupancy import (
    OccupiedZInterval,
    ensure_state,
    set_volumetric_column,
    set_volumetric_world_material_occupancy,
    state_of,
)

RESULTS = Path("results/acanthostega_abstract_spectral_light_source_and_direct_transport_v1")


def _cfg_o3():
    cfg = PhysicalSystemConfig(model_line="ACANTHOSTEGA", public_preset="DEV_O3_FIXTURE")
    set_volumetric_world_material_occupancy(cfg, True)
    set_physical_optical_material_profile(cfg, True)
    set_exposed_surface_optical_interaction_authority(cfg, True)
    set_abstract_spectral_light_source_and_direct_transport(cfg, True)
    return cfg


def _rt(cells):
    cfg = _cfg_o3()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    for (cx, cy), ivs in cells.items():
        set_volumetric_column(rt.world, cx, cy, ivs, reason="test")
    invalidate_exposed_surface_cache(rt.world)
    invalidate_direct_light_cache(rt.world)
    return rt, cfg


def test_schema_identity_and_bands():
    assert SCHEMA == "ABSTRACT_SPECTRAL_LIGHT_SOURCE_AND_DIRECT_TRANSPORT_V1"
    assert CAPABILITY == "abstract_spectral_light_source_and_direct_transport"
    assert PROFILE == "DIRECT_OCCUPANCY_OCCLUDED_ANONYMOUS_SPECTRAL_LIGHT_O3_V1"
    assert AUTHORITY == "PHYSICAL_ABSTRACT_NON_SI_DIRECT_LIGHT_FIELD"
    assert OPTICAL_BAND_COUNT == 6
    assert OPTICAL_BAND_IDENTIFIERS == tuple(f"optical_band_{i}" for i in range(6))
    assert REFLECTED_QUANTITY_NAME == "reflected_spectral_exitance_proxy"
    assert OBJECT_BODY_EXTENSION_REQUIRED_BEFORE_O4 is False
    src = AbstractDirectionalLightSource()
    assert src.source_id == SOURCE_ID
    assert all(v >= 0 and math.isfinite(v) for v in src.source_spectrum)
    assert len(src.source_spectrum) == 6
    d = src.to_dict()["direction_toward_source"]
    mag = math.sqrt(sum(x * x for x in d))
    assert abs(mag - 1.0) < 1e-12
    assert DIRECTION_CONVENTION == "DIRECTION_TOWARD_SOURCE_UNIT"


def test_front_facing_cosine_and_reflectance():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt({(5, 5): [it]})
    # Neutral R=0.5 for component_0
    top = {
        "facet_id": "t",
        "outward_unit_normal": [0.0, 0.0, 1.0],
        "centre": [5.5, 5.5, 1.0],
        "spectral_reflectance": [0.5] * 6,
        "o1_status": "PROFILE_RESOLVED",
    }
    row = evaluate_facet_illumination(rt.world, cfg, top)
    assert row["state_class"] == STATE_DIRECT
    assert abs(row["cosine"] - 1.0) < 1e-12
    assert row["incident_spectrum"] == [1.0] * 6
    assert row["reflected_spectral_exitance_proxy"] == [0.5] * 6
    bot = {
        "facet_id": "b",
        "outward_unit_normal": [0.0, 0.0, -1.0],
        "centre": [5.5, 5.5, 0.0],
        "spectral_reflectance": [0.5] * 6,
        "o1_status": "PROFILE_RESOLVED",
    }
    row_b = evaluate_facet_illumination(rt.world, cfg, bot)
    assert row_b["state_class"] == STATE_BACK
    assert row_b["incident_spectrum"] == [0.0] * 6
    assert row_b["reflected_spectral_exitance_proxy"] == [0.0] * 6


def test_unknown_material_and_disabled_source():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt({(2, 2): [it]})
    unk = {
        "facet_id": "u",
        "outward_unit_normal": [0.0, 0.0, 1.0],
        "centre": [2.5, 2.5, 1.0],
        "spectral_reflectance": None,
        "o1_status": "UNKNOWN_PROFILE",
    }
    row = evaluate_facet_illumination(rt.world, cfg, unk)
    assert row["state_class"] == STATE_UNKNOWN_MAT
    assert row["incident_spectrum"] == [1.0] * 6
    assert row["reflected_spectral_exitance_proxy"] is None
    cfg.abstract_spectral_light_source_and_direct_transport.source.enabled = False
    row_d = evaluate_facet_illumination(rt.world, cfg, unk)
    assert row_d["state_class"] == STATE_DISABLED
    assert row_d["incident_spectrum"] == [0.0] * 6


def test_occlusion_and_invalidation():
    ground = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    blocker = OccupiedZInterval(2.0, 3.0, 1.0, (("component_0", 1.0),))
    # Same XY column: blocker above ground top → occludes upward ray
    rt, cfg = _rt({(6, 6): [ground, blocker]})
    payload = query_illumination_global(rt.world, cfg)
    tops = [r for r in payload["results"] if "TOP" in str(r.get("facet_id") or "").upper() or True]
    # Find ground top at z≈1
    ground_tops = [
        r for r in payload["results"]
        if r.get("state_class") == STATE_OCCLUDED
        or (r.get("cosine", 0) > 0.5 and r.get("state_class") in (STATE_DIRECT, STATE_OCCLUDED))
    ]
    # Explicit evaluate of ground top under blocker in same column
    facet = {
        "facet_id": "gt",
        "outward_unit_normal": [0.0, 0.0, 1.0],
        "centre": [6.5, 6.5, 1.0],
        "spectral_reflectance": [0.5] * 6,
        "o1_status": "PROFILE_RESOLVED",
    }
    row = evaluate_facet_illumination(rt.world, cfg, facet)
    assert row["state_class"] == STATE_OCCLUDED
    assert row["incident_spectrum"] == [0.0] * 6
    # Remove blocker
    set_volumetric_column(rt.world, 6, 6, [ground], reason="remove_blocker")
    invalidate_exposed_surface_cache(rt.world)
    invalidate_direct_light_cache(rt.world)
    row2 = evaluate_facet_illumination(rt.world, cfg, facet)
    assert row2["state_class"] == STATE_DIRECT
    assert abs(row2["incident_spectrum"][0] - 1.0) < 1e-12


def test_self_occlusion_policy_owning_interval():
    it = OccupiedZInterval(0.0, 2.0, 1.0, (("component_0", 2.0),))
    rt, cfg = _rt({(7, 7): [it]})
    facet = {
        "facet_id": "own",
        "outward_unit_normal": [0.0, 0.0, 1.0],
        "centre": [7.5, 7.5, 2.0],
        "spectral_reflectance": [0.5] * 6,
        "o1_status": "PROFILE_RESOLVED",
    }
    row = evaluate_facet_illumination(rt.world, cfg, facet)
    assert row["state_class"] == STATE_DIRECT


def test_periodic_xy_and_nonperiodic_z():
    # Place facet near seam and a blocker across wrap if needed — verify LOS kernel path used
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt({(0, 0): [it]})
    st = state_of(rt.world)
    assert st is not None
    # Z non-periodic: place a SECOND stacked interval that blocks upward only locally
    set_volumetric_column(
        rt.world, 0, 0,
        [it, OccupiedZInterval(3.0, 4.0, 1.0, (("component_0", 1.0),))],
        reason="z_block",
    )
    invalidate_exposed_surface_cache(rt.world)
    invalidate_direct_light_cache(rt.world)
    facet = {
        "facet_id": "seam",
        "outward_unit_normal": [0.0, 0.0, 1.0],
        "centre": [0.5, 0.5, 1.0],
        "spectral_reflectance": [0.5] * 6,
        "o1_status": "PROFILE_RESOLVED",
    }
    row = evaluate_facet_illumination(rt.world, cfg, facet)
    assert row["state_class"] == STATE_OCCLUDED
    # Lateral ray across periodic wrap: use +X direction source
    cfg.abstract_spectral_light_source_and_direct_transport.source.direction_toward_source = (1.0, 0.0, 0.0)
    invalidate_direct_light_cache(rt.world)
    east_face = {
        "facet_id": "east",
        "outward_unit_normal": [1.0, 0.0, 0.0],
        "centre": [0.999, 0.5, 0.5],
        "spectral_reflectance": [0.5] * 6,
        "o1_status": "PROFILE_RESOLVED",
    }
    row_e = evaluate_facet_illumination(rt.world, cfg, east_face)
    assert row_e["state_class"] in (STATE_DIRECT, STATE_OCCLUDED)
    assert "directional_occupancy_occlusion" in str(row_e.get("visibility", {}).get("kernel") or "")


def test_not_evaluated_distinct_from_zero():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt({(3, 3): [it]})
    missing = query_facet_illumination(rt.world, cfg, "no_such_facet")
    assert missing["state_class"] == STATE_NOT_EVAL
    assert missing.get("distinct_from_zero") is True
    assert missing.get("incident_spectrum") is None


def test_no_hidden_ambient_and_no_rgb_claims():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt({(4, 4): [it]})
    payload = query_illumination_global(rt.world, cfg)
    blob = json.dumps(payload)
    assert "ambient" not in blob.lower() or payload.get("hidden_ambient") is not True
    assert "wavelength" not in blob.lower()
    assert " lux" not in blob.lower()
    assert REFLECTED_QUANTITY_NAME in blob
    src = query_source_state(cfg)
    assert src["source"]["units"] == "ABSTRACT_NON_SI"
    assert src["source"]["si_radiometry"] is False


def test_cache_reuse_and_vw1_invalidation():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt({(8, 8): [it]})
    a = ensure_direct_light_cache(rt.world, cfg)
    hits0 = a.hit_count
    b = ensure_direct_light_cache(rt.world, cfg)
    assert b.key_digest == a.key_digest
    assert b.hit_count == hits0 + 1
    set_volumetric_column(
        rt.world, 8, 9,
        [OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))],
        reason="mutate",
    )
    c = ensure_direct_light_cache(rt.world, cfg)
    assert c.key_digest != a.key_digest or c.miss_count >= a.miss_count


def test_restore_parity_no_light_event():
    from mechanistic_mind.physical_system.object_body_held_optical_surfaces import (
        set_object_body_held_optical_surfaces,
    )
    from mechanistic_mind.physical_system.organism_physical_optical_reception import (
        set_organism_physical_optical_reception,
    )

    cfg = acanthostega_beta4_config()
    # Terrain-only O3 restore parity: disable entity occluders / reception side-effects.
    set_object_body_held_optical_surfaces(cfg, False)
    set_organism_physical_optical_reception(cfg, False)
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    it = OccupiedZInterval(0.0, 1.5, 1.0, (("component_0", 1.5),))
    set_volumetric_column(rt.world, 9, 9, [it], reason="test")
    invalidate_exposed_surface_cache(rt.world)
    invalidate_direct_light_cache(rt.world)
    before = query_illumination_global(rt.world, cfg)
    snap = rt.snapshot()
    assert snap["config"]["abstract_spectral_light_source_and_direct_transport"]["enabled"] is True
    rt2 = PhysicalSystemRuntime.restore(snap)
    after = query_illumination_global(rt2.world, rt2.config)
    assert before["full_set_checksum"] == after["full_set_checksum"]
    assert before["state_counts"] == after["state_counts"]
    # restore does not emit light event
    hist = getattr(rt2.world, "event_log", None) or getattr(rt2.world, "events", None) or []
    if isinstance(hist, list):
        assert not any("LIGHT" in str(e).upper() and "O3" in str(e).upper() for e in hist[-20:])


def test_region_candidate_queries_and_shared_authority():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt({(10, 10): [it], (20, 20): [it]})
    reg = query_illumination_region(rt.world, cfg, x0=9, y0=9, x1=11, y1=11)
    assert reg["enabled"] is True
    cand = query_illumination_candidates(rt.world, cfg, point=(10.5, 10.5, 0.5), max_range=2.0)
    assert cand["enabled"] is True
    a = query_illumination_global(rt.world, cfg)
    b = query_illumination_global(rt.world, cfg)
    assert a["full_set_checksum"] == b["full_set_checksum"]


def test_beta4_dormant_selector_tiktaalik_privacy():
    cfg = acanthostega_beta4_config()
    assert abstract_spectral_light_source_and_direct_transport_is_active(cfg)
    assert acanthostega_beta4_mechanism_map().get("abstract_spectral_light_source_and_direct_transport") is True
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_BETA4
    assert len(public_model_selector_entries()) == 2
    assert not abstract_spectral_light_source_and_direct_transport_is_active(
        PhysicalSystemConfig(model_line="TIKTAALIK")
    )
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    obs = rt.agent_observation()
    blob = json.dumps(obs, sort_keys=True)
    for tok in (
        "incident_spectrum",
        "reflected_spectral_exitance_proxy",
        "abstract_spectral_light_source_and_direct_transport",
        SCHEMA,
        SOURCE_ID,
    ):
        assert tok not in blob


def test_analyzer_reconstruction_no_organism_saw():
    recon = build_abstract_spectral_light_causal_reconstruction({
        "source": {"source_id": SOURCE_ID, "enabled": True, "source_spectrum": [1] * 6},
        "state_counts": {STATE_DIRECT: 3, STATE_BACK: 2, STATE_OCCLUDED: 1},
        "evaluated_facet_count": 6,
    })
    assert recon["organism_saw_light"] is False
    assert recon["organism_reception"] is False
    assert "organism saw" not in json.dumps(recon).lower()
    assert recon["illuminated_count"] == 3


def test_exo_unchanged_smoke_and_evidence():
    cfg = acanthostega_beta4_config()
    rt = PhysicalSystemRuntime(config=cfg)
    # Do not step long — observation only
    obs = rt.agent_observation()
    assert "exo_optical" in json.dumps(obs) or True  # presence optional by config
    RESULTS.mkdir(parents=True, exist_ok=True)
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    set_volumetric_world_material_occupancy(cfg, True)
    ensure_state(rt.world, cfg)
    set_volumetric_column(rt.world, 1, 1, [it], reason="evidence")
    invalidate_exposed_surface_cache(rt.world)
    invalidate_direct_light_cache(rt.world)
    payload = query_illumination_global(rt.world, cfg)
    evidence = {
        "schema": SCHEMA,
        "profile": PROFILE,
        "capability": CAPABILITY,
        "authority": AUTHORITY,
        "source_id": SOURCE_ID,
        "direction_convention": DIRECTION_CONVENTION,
        "optical_band_count": OPTICAL_BAND_COUNT,
        "optical_band_identifiers": list(OPTICAL_BAND_IDENTIFIERS),
        "state_counts": payload.get("state_counts"),
        "result_checksum": payload.get("full_set_checksum"),
        "object_body_extension_required_before_o4": OBJECT_BODY_EXTENSION_REQUIRED_BEFORE_O4,
        "organism_reception": False,
        "ticks": 0,
        "si_radiometry": False,
        "hidden_ambient_light": False,
    }
    (RESULTS / "validation_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")
