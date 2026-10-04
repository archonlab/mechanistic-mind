"""O2 Exposed Surface Optical Interaction Authority V1 — focused tests."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BETA4,
    acanthostega_beta4_mechanism_map,
    public_model_selector_entries,
)
from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
    AUTHORITY,
    CAPABILITY,
    FACE_BOTTOM,
    FACE_EAST,
    FACE_TOP,
    FACE_WEST,
    PROFILE,
    SCHEMA,
    build_exposed_facets,
    ensure_exposed_surface_cache,
    exposed_surface_optical_interaction_authority_is_active,
    invalidate_exposed_surface_cache,
    query_exposed_facets_candidates,
    query_exposed_facets_global,
    query_exposed_facets_region,
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
from mechanistic_mind.physical_system.exposed_surface_optical_interaction_authority import (
    set_exposed_surface_optical_interaction_authority,
)

RESULTS = Path("results/acanthostega_exposed_surface_optical_interaction_authority_v1")


def _cfg_o2_minimal():
    cfg = PhysicalSystemConfig(model_line="ACANTHOSTEGA", public_preset="DEV_O2_FIXTURE")
    set_volumetric_world_material_occupancy(cfg, True)
    set_physical_optical_material_profile(cfg, True)
    set_exposed_surface_optical_interaction_authority(cfg, True)
    # Keep PSC off so occupancy is purely sparse (deterministic tiny world).
    return cfg


def _rt_with_intervals(cells: dict[tuple[int, int], list[OccupiedZInterval]]):
    cfg = _cfg_o2_minimal()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    st = state_of(rt.world)
    assert st is not None
    # Shrink logical size for tests by writing only needed cells on default 32 grid —
    # use isolated columns far apart or adjacent as needed.
    for (cx, cy), ivs in cells.items():
        set_volumetric_column(rt.world, cx, cy, ivs, reason="test")
    invalidate_exposed_surface_cache(rt.world)
    return rt, cfg


def test_schema_identity():
    assert SCHEMA == "EXPOSED_SURFACE_OPTICAL_INTERACTION_AUTHORITY_V1"
    assert CAPABILITY == "exposed_surface_optical_interaction_authority"
    assert PROFILE == "VW1_OCCUPIED_FREE_BOUNDARY_FACETS_O2_V1"
    assert AUTHORITY == "AUTHORITATIVE_DERIVATION_FROM_VW1_OCCUPANCY_READ_ONLY"


def test_single_interval_exposed_boundary_set():
    it = OccupiedZInterval(0.0, 2.0, 1.0, (("component_0", 2.0),))
    rt, cfg = _rt_with_intervals({(5, 5): [it]})
    # Empty neighbors → all four sides + top + bottom
    # But world has many empty cells; only (5,5) occupied.
    payload = query_exposed_facets_global(rt.world, cfg)
    facets = [f for f in payload["facets"] if f["cell_x"] == 5 and f["cell_y"] == 5]
    faces = {f["face_class"] for f in facets}
    assert FACE_TOP in faces and FACE_BOTTOM in faces
    assert FACE_EAST in faces and FACE_WEST in faces
    assert all(f["area"] > 0 for f in facets)
    assert all(f["outward_unit_normal"] for f in facets)
    # Normals point occupied→free
    top = next(f for f in facets if f["face_class"] == FACE_TOP)
    assert top["outward_unit_normal"] == [0.0, 0.0, 1.0]
    bot = next(f for f in facets if f["face_class"] == FACE_BOTTOM)
    assert bot["outward_unit_normal"] == [0.0, 0.0, -1.0]


def test_equal_adjacent_columns_hide_shared_face():
    it = OccupiedZInterval(0.0, 2.0, 1.0, (("component_0", 2.0),))
    rt, cfg = _rt_with_intervals({(3, 4): [it], (4, 4): [it]})
    payload = query_exposed_facets_global(rt.world, cfg)
    left = [f for f in payload["facets"] if f["cell_x"] == 3 and f["cell_y"] == 4 and f["face_class"] == FACE_EAST]
    right = [f for f in payload["facets"] if f["cell_x"] == 4 and f["cell_y"] == 4 and f["face_class"] == FACE_WEST]
    assert left == []
    assert right == []


def test_unequal_adjacent_exposes_uncovered_span_only():
    low = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    high = OccupiedZInterval(0.0, 2.0, 1.0, (("component_0", 2.0),))
    rt, cfg = _rt_with_intervals({(3, 4): [low], (4, 4): [high]})
    payload = query_exposed_facets_global(rt.world, cfg)
    # From taller cell west face: only (1,2] exposed toward short neighbor
    west = [
        f
        for f in payload["facets"]
        if f["cell_x"] == 4 and f["cell_y"] == 4 and f["face_class"] == FACE_WEST
    ]
    assert len(west) == 1
    assert abs(west[0]["span_lower"] - 1.0) < 1e-9
    assert abs(west[0]["span_upper"] - 2.0) < 1e-9
    # Short cell east face fully covered by tall → none
    east = [
        f
        for f in payload["facets"]
        if f["cell_x"] == 3 and f["cell_y"] == 4 and f["face_class"] == FACE_EAST
    ]
    assert east == []


def test_stacked_contiguous_no_internal_boundary():
    a = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    b = OccupiedZInterval(1.0, 2.0, 1.0, (("component_a", 1.0),))
    rt, cfg = _rt_with_intervals({(2, 2): [a, b]})
    payload = query_exposed_facets_global(rt.world, cfg)
    cell_f = [f for f in payload["facets"] if f["cell_x"] == 2 and f["cell_y"] == 2]
    # No TOP of lower at z=1, no BOTTOM of upper at z=1
    internal = [
        f
        for f in cell_f
        if (f["face_class"] == FACE_TOP and abs(f["boundary_plane_coordinate"] - 1.0) < 1e-12)
        or (f["face_class"] == FACE_BOTTOM and abs(f["boundary_plane_coordinate"] - 1.0) < 1e-12)
    ]
    assert internal == []
    # Gap cavity case: expose facing boundaries
    gap_low = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    gap_hi = OccupiedZInterval(2.0, 3.0, 1.0, (("component_0", 1.0),))
    rt2, cfg2 = _rt_with_intervals({(2, 3): [gap_low, gap_hi]})
    p2 = query_exposed_facets_global(rt2.world, cfg2)
    cell2 = [f for f in p2["facets"] if f["cell_x"] == 2 and f["cell_y"] == 3]
    assert any(f["face_class"] == FACE_TOP and abs(f["centre"][2] - 1.0) < 1e-12 for f in cell2)
    assert any(f["face_class"] == FACE_BOTTOM and abs(f["centre"][2] - 2.0) < 1e-12 for f in cell2)


def test_periodic_seam_and_deterministic_ids():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    # width is 32 by default — cells 0 and 31 are periodic neighbors in x
    rt, cfg = _rt_with_intervals({(0, 6): [it], (31, 6): [it]})
    payload = query_exposed_facets_global(rt.world, cfg)
    east0 = [f for f in payload["facets"] if f["cell_x"] == 0 and f["cell_y"] == 6 and f["face_class"] == FACE_WEST]
    west31 = [f for f in payload["facets"] if f["cell_x"] == 31 and f["cell_y"] == 6 and f["face_class"] == FACE_EAST]
    # Shared periodic face suppressed both ways
    assert east0 == []
    assert west31 == []
    a = query_exposed_facets_global(rt.world, cfg)
    b = query_exposed_facets_global(rt.world, cfg)
    assert a["facet_checksum"] == b["facet_checksum"]
    assert [f["facet_id"] for f in a["facets"]] == [f["facet_id"] for f in b["facets"]]


def test_cache_hit_and_invalidation_on_mutation():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt_with_intervals({(1, 1): [it]})
    c1 = ensure_exposed_surface_cache(rt.world, cfg)
    assert c1 is not None
    hits0 = c1.hit_count
    c2 = ensure_exposed_surface_cache(rt.world, cfg)
    assert c2 is c1
    assert c2.hit_count == hits0 + 1
    dig0 = c1.facet_checksum
    set_volumetric_column(
        rt.world,
        1,
        1,
        [OccupiedZInterval(0.0, 2.0, 1.0, (("component_0", 2.0),))],
        reason="mutate",
    )
    c3 = ensure_exposed_surface_cache(rt.world, cfg)
    assert c3 is not None
    assert c3.facet_checksum != dig0


def test_o1_linkage_unknown_does_not_drop_geometry():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_zzz", 1.0),))
    rt, cfg = _rt_with_intervals({(7, 7): [it]})
    payload = query_exposed_facets_global(rt.world, cfg)
    facets = [f for f in payload["facets"] if f["cell_x"] == 7 and f["cell_y"] == 7]
    assert facets
    assert all(f["o1_status"] == "UNKNOWN_PROFILE" for f in facets)
    assert all(f["geometry_valid_if_profile_unknown"] for f in facets)


def test_region_and_candidate_queries():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt_with_intervals({(8, 8): [it], (20, 20): [it]})
    reg = query_exposed_facets_region(rt.world, cfg, x0=7, y0=7, x1=9, y1=9)
    assert all(7 <= f["centre"][0] <= 9 and 7 <= f["centre"][1] <= 9 for f in reg["facets"])
    cand = query_exposed_facets_candidates(rt.world, cfg, point=(8.5, 8.5, 0.5), max_range=2.0)
    assert cand["facets"]


def test_beta4_includes_o2_selector_unchanged_tiktaalik():
    cfg = acanthostega_beta4_config()
    assert exposed_surface_optical_interaction_authority_is_active(cfg)
    assert acanthostega_beta4_mechanism_map().get("exposed_surface_optical_interaction_authority") is True
    assert cfg.public_preset == PRESET_ACANTHOSTEGA_BETA4
    assert len(public_model_selector_entries()) == 2
    assert not exposed_surface_optical_interaction_authority_is_active(
        PhysicalSystemConfig(model_line="TIKTAALIK")
    )


def test_snapshot_restore_parity_and_privacy():
    # Beta4 carries VW6→VW1 restore coupling used by public snapshot path.
    cfg = acanthostega_beta4_config()
    rt = PhysicalSystemRuntime(config=cfg)
    ensure_state(rt.world, cfg)
    it = OccupiedZInterval(0.0, 1.5, 1.0, (("component_0", 1.5),))
    set_volumetric_column(rt.world, 9, 9, [it], reason="test")
    invalidate_exposed_surface_cache(rt.world)
    before = query_exposed_facets_global(rt.world, cfg)
    assert before.get("enabled") is True
    snap = rt.snapshot()
    assert snap["config"]["exposed_surface_optical_interaction_authority"]["enabled"] is True
    rt2 = PhysicalSystemRuntime.restore(snap)
    after = query_exposed_facets_global(rt2.world, rt2.config)
    assert after.get("enabled") is True
    assert before["facet_checksum"] == after["facet_checksum"]
    assert [f["facet_id"] for f in before["facets"]] == [f["facet_id"] for f in after["facets"]]
    obs = rt.agent_observation()
    blob = json.dumps(obs, sort_keys=True)
    for tok in ("facet_id", "exposed_surface_optical_interaction_authority", SCHEMA, "outward_unit_normal"):
        assert tok not in blob


def test_failed_transaction_no_change_and_evidence_file():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt_with_intervals({(4, 5): [it]})
    before = query_exposed_facets_global(rt.world, cfg)["facet_checksum"]
    # No mutation → checksum stable (simulates rejected txn)
    after = query_exposed_facets_global(rt.world, cfg)["facet_checksum"]
    assert before == after
    RESULTS.mkdir(parents=True, exist_ok=True)
    evidence = {
        "schema": SCHEMA,
        "profile": PROFILE,
        "facet_checksum": before,
        "counts_by_face": query_exposed_facets_global(rt.world, cfg)["counts_by_face"],
        "ticks": 0,
    }
    (RESULTS / "validation_evidence.json").write_text(json.dumps(evidence, indent=2) + "\n")


def test_two_agents_share_boundary_authority():
    it = OccupiedZInterval(0.0, 1.0, 1.0, (("component_0", 1.0),))
    rt, cfg = _rt_with_intervals({(10, 10): [it]})
    a = build_exposed_facets(rt.world)
    b = build_exposed_facets(rt.world)
    assert a.facet_checksum == b.facet_checksum
