"""ACANTHOSTEGA PROCEDURAL SURFACE COLUMNS.

Authority map (t116 correction):
  procedural baseline column = authoritative physical world description
  surface elevation          = authoritative geometry, no consequence kernel yet
  sparse delta               = authoritative persistent world mutation
  cache                      = derived, non-authoritative
  Observer representation    = researcher-only read view
physical_effects_active = false, agent_accessible = false, geometry_role = METADATA_ONLY.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

import numpy as np
import pytest

from mechanistic_mind.model.acanthostega import (
    acanthostega_multi_content_config,
    acanthostega_procedural_columns_config,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import procedural_surface_columns as psc
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_MULTI_CONTENT,
    PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
    PRESET_ACANTHOSTEGA_WORLD_MATERIAL,
    PRESET_BETA31,
    beta31_mechanism_map,
    canonical_fingerprint,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.locomotion_profile import ACANTHOSTEGA_ONLY_MECHANISM_IDS
from mechanistic_mind.physical_system.mechanism_registry import set_mechanism
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import checksum_of
from mechanistic_mind.scientific_v3.procedural_surface_columns_summary import (
    format_procedural_surface_columns_section,
    summarize_procedural_surface_columns,
)
from mechanistic_mind.ui.psy_observer_web.serialize import world_frame

FROZEN = "1621ef2c154864d1"
MID = psc.MECHANISM_ID


def _h(x) -> str:
    return hashlib.sha256(repr(x).encode()).hexdigest()[:16]


def _rt(seed: int = 17) -> PhysicalSystemRuntime:
    return PhysicalSystemRuntime(seed=seed, config=acanthostega_procedural_columns_config())


def _mc(seed: int = 17) -> PhysicalSystemRuntime:
    return PhysicalSystemRuntime(seed=seed, config=acanthostega_multi_content_config())


def _delta(world, x=3, y=5, q=0.1, rev=0, idx=0, tick=0):
    return psc.apply_surface_column_setup_delta(
        world, x, y, upper_layer_index=idx, transfer_quantity=q, expected_revision=rev,
        tick=tick, researcher_id="test", reason="unit",
    )


@pytest.fixture(scope="module")
def rt():
    return _rt()


# ---------------------------------------------------------------- preset / gate


def test_01_tiktaalik_beta31_fingerprint_frozen():
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN
    assert MID not in beta31_mechanism_map()


def test_02_new_preset_normalizes_and_is_distinct():
    assert normalize_preset_name("Acanthostega Phase B Procedural Columns") == PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS
    assert normalize_preset_name(PRESET_ACANTHOSTEGA_MULTI_CONTENT) == PRESET_ACANTHOSTEGA_MULTI_CONTENT
    assert PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS == "ACANTHOSTEGA_PHASE_B_PROCEDURAL_COLUMNS"


def test_03_new_preset_inherits_multi_content_map_plus_columns():
    mc = preset_canonical(PRESET_ACANTHOSTEGA_MULTI_CONTENT, seed=17)["mechanisms"]
    pc = preset_canonical(PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS, seed=17)["mechanisms"]
    assert pc[MID] is True
    assert {k: v for k, v in pc.items() if k != MID} == mc


def test_04_mechanism_off_in_every_previous_preset():
    for name in (PRESET_ACANTHOSTEGA_MULTI_CONTENT, PRESET_ACANTHOSTEGA_WORLD_MATERIAL, PRESET_BETA31):
        assert preset_canonical(name, seed=17)["mechanisms"].get(MID) in (None, False)
    assert psc.procedural_surface_columns_is_active(acanthostega_multi_content_config()) is False


def test_05_forcing_on_tiktaalik_stays_off():
    tik = tiktaalik_config()
    set_mechanism(tik, MID, True)
    assert psc.procedural_surface_columns_is_active(tik) is False
    psc.set_procedural_surface_columns(tik, True)
    assert psc.procedural_surface_columns_is_active(tik) is False


def test_06_missing_config_field_means_off():
    bare = acanthostega_procedural_columns_config()
    bare.procedural_surface_columns = psc.ProceduralSurfaceColumnsConfig.from_dict(None)
    assert psc.procedural_surface_columns_is_active(bare) is False
    bare.procedural_surface_columns = None
    assert psc.procedural_surface_columns_is_active(bare) is False


def test_07_stamp_config_from_preset_enables_only_for_new_preset():
    cfg = stamp_config_from_preset(acanthostega_multi_content_config(), PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS)
    assert psc.procedural_surface_columns_is_active(cfg) is True
    cfg2 = stamp_config_from_preset(acanthostega_procedural_columns_config(), PRESET_ACANTHOSTEGA_MULTI_CONTENT)
    assert psc.procedural_surface_columns_is_active(cfg2) is False
    assert MID in ACANTHOSTEGA_ONLY_MECHANISM_IDS


# ---------------------------------------------------------------- baseline


def test_08_baseline_deterministic_same_seed(rt):
    other = _rt()
    for x, y in [(0, 0), (3, 5), (17, 29), (63, 63)]:
        a = psc.baseline_column_at(rt.world, x, y)
        b = psc.baseline_column_at(other.world, x, y)
        assert a.baseline_checksum == b.baseline_checksum
        assert a.as_dict() == b.as_dict()


def test_09_baseline_differs_across_seeds():
    a, b = _rt(17), _rt(18)
    diffs = sum(
        psc.baseline_column_at(a.world, x, 7).baseline_checksum
        != psc.baseline_column_at(b.world, x, 7).baseline_checksum
        for x in range(8)
    )
    assert diffs >= 6


def test_10_query_order_independence():
    a, b = _rt(), _rt()
    cells = [(x, y) for x in range(0, 40, 7) for y in range(0, 40, 5)]
    fwd = {c: psc.baseline_column_at(a.world, *c).baseline_checksum for c in cells}
    rev = {c: psc.baseline_column_at(b.world, *c).baseline_checksum for c in reversed(cells)}
    assert fwd == rev


def test_11_cache_eviction_does_not_change_baseline():
    # Fixture correction (reported separately): the limit is derived from the real world
    # size, and every real cell is swept, so eviction is guaranteed on any grid.
    probe = _rt()
    st0 = psc.state_of(probe.world)
    cells = st0.width * st0.height
    limit = max(psc.CACHE_LIMIT_BOUNDS[0], cells // 4)
    assert limit < cells
    cfg = acanthostega_procedural_columns_config()
    cfg.procedural_surface_columns = psc.ProceduralSurfaceColumnsConfig.from_dict(
        {**cfg.procedural_surface_columns.to_dict(), "cache_limit": limit}
    )
    r = PhysicalSystemRuntime(seed=17, config=cfg)
    st = psc.state_of(r.world)
    first = psc.baseline_column_at(r.world, 2, 2).baseline_checksum
    for y in range(st.height):
        for x in range(st.width):
            psc.baseline_column_at(r.world, x, y)
    assert len(st.cache) == limit
    assert st.cache_evictions == cells - limit  # every unique cell beyond the limit evicts once
    st.cache.clear()
    assert psc.baseline_column_at(r.world, 2, 2).baseline_checksum == first
    assert psc.baseline_column_at(probe.world, 2, 2).baseline_checksum == first


def test_12_generator_does_not_touch_global_rng(rt):
    np_state = np.random.get_state()[1].copy()
    import random
    py_state = random.getstate()
    for x in range(20):
        psc.baseline_column_at(rt.world, x, x)
    assert np.array_equal(np.random.get_state()[1], np_state)
    assert random.getstate() == py_state


def test_13_toroidal_wrap_addresses(rt):
    st = psc.state_of(rt.world)
    a = psc.baseline_column_at(rt.world, -1, -1)
    b = psc.baseline_column_at(rt.world, st.width - 1, st.height - 1)
    c = psc.baseline_column_at(rt.world, st.width + 2.7, 3.2)
    d = psc.baseline_column_at(rt.world, 2, 3)
    assert a.baseline_checksum == b.baseline_checksum
    assert c.baseline_checksum == d.baseline_checksum


def test_14_layers_contiguous_ordered_and_reach_modelled_depth(rt):
    for x, y in [(0, 0), (9, 4), (31, 12)]:
        col = psc.baseline_column_at(rt.world, x, y)
        assert col.layers[0].top_depth == 0.0
        for up, lo in zip(col.layers, col.layers[1:]):
            assert up.bottom_depth == lo.top_depth
            assert up.thickness > 0.0
        assert col.layers[-1].bottom_depth == col.modelled_depth
        assert psc.validate_layers(col.layers, col.modelled_depth)["verified"] is True


def test_15_composition_sums_to_quantity_and_is_anonymous(rt):
    col = psc.baseline_column_at(rt.world, 5, 6)
    for layer in col.layers:
        total = sum(q for _, q in layer.composition)
        assert math.isclose(total, layer.quantity_per_area, abs_tol=psc.TOLERANCE * 10)
        assert {cid for cid, _ in layer.composition} <= set(psc.COMPONENT_IDS)
        assert layer.density > 0.0


def test_16_surface_elevation_is_authoritative_metadata_only(rt):
    col = psc.resolved_column_at(rt.world, 4, 4)
    assert math.isfinite(col["surface_elevation"])
    assert col["geometry_role"] == "METADATA_ONLY"
    assert col["authority"] == "WORLD_SIMULATION_STATE"
    assert col["physical_effects_active"] is False
    assert col["agent_accessible"] is False
    assert psc.AUTHORITY_FLAGS["surface_elevation_authority"] == "AUTHORITATIVE_GEOMETRY_NO_CONSEQUENCE_KERNEL"
    assert psc.AUTHORITY_FLAGS["baseline_authority"] == "AUTHORITATIVE_PHYSICAL_WORLD_DESCRIPTION"
    assert psc.AUTHORITY_FLAGS["cache_authority"] == "DERIVED_NON_AUTHORITATIVE"


def test_17_material_at_depth_half_open_boundaries(rt):
    col = psc.resolved_column_at(rt.world, 3, 5)
    b = col["layers"][0].bottom_depth
    assert psc.material_at_depth(rt.world, 3, 5, 0.0)["layer_index"] == 0
    assert psc.material_at_depth(rt.world, 3, 5, b)["layer_index"] == 1
    assert psc.material_at_depth(rt.world, 3, 5, -0.1)["status"] == psc.STATUS_ABOVE_SURFACE
    assert psc.material_at_depth(rt.world, 3, 5, col["modelled_depth"])["status"] == psc.STATUS_NOT_MODELLED
    assert psc.material_at_depth(rt.world, 3, 5, float("nan"))["status"] == psc.STATUS_NOT_MODELLED


def test_18_unrecorded_queries_emit_no_receipts():
    r = _rt()
    st = psc.state_of(r.world)
    before = len(st.history)
    for x in range(10):
        psc.resolved_column_at(r.world, x, 1)
        psc.material_at_depth(r.world, x, 1, 0.5)
    assert len(st.history) == before
    psc.resolved_column_at(r.world, 1, 1, record=True, reason="t")
    assert st.history[-1]["event"] == psc.EVENT_BASELINE_QUERIED


def test_19_invalid_config_rejected():
    with pytest.raises(psc.SurfaceColumnValidationError):
        psc.validate_config(psc.ProceduralSurfaceColumnsConfig(enabled=True, modelled_depth=0.1))
    with pytest.raises(psc.SurfaceColumnValidationError):
        psc.validate_config(psc.ProceduralSurfaceColumnsConfig(enabled=True, thickness_fractions=(0.5, 0.2)))


# ---------------------------------------------------------------- sparse delta


def test_20_setup_delta_commits_and_moves_boundary_only():
    r = _rt()
    before = psc.resolved_column_at(r.world, 3, 5)
    rec = _delta(r.world, q=0.1)
    assert rec["status"] == "COMMITTED"
    after = psc.resolved_column_at(r.world, 3, 5)
    assert math.isclose(after["layers"][0].bottom_depth, before["layers"][0].bottom_depth + 0.1, abs_tol=1e-12)
    assert after["surface_elevation"] == before["surface_elevation"]
    assert after["layers"][-1].bottom_depth == before["layers"][-1].bottom_depth
    assert after["has_persistent_delta"] is True and after["delta_revision"] == 1


def test_21_setup_delta_conserves_mass_quantity_components():
    r = _rt()
    rec = _delta(r.world, q=0.2)
    cons = rec["conservation"]
    assert cons["verified"] is True
    assert cons["external_source_sink"] is False
    assert abs(rec["after"]["total_mass_per_area"] - rec["before"]["total_mass_per_area"]) <= 1e-9


def test_22_stale_revision_rejected_without_mutation():
    r = _rt()
    _delta(r.world)
    ck = psc.deltas_checksum(r.world)
    rec = _delta(r.world, rev=0)
    assert rec["status"] == "REJECTED" and rec["event"] == psc.EVENT_VALIDATION_FAILED
    assert rec["rejection_reason"].startswith("stale_revision")
    assert psc.deltas_checksum(r.world) == ck


def test_23_invalid_layer_index_and_quantity_rejected():
    r = _rt()
    ck = psc.deltas_checksum(r.world)
    assert _delta(r.world, idx=9)["rejection_reason"] == "invalid_layer_index"
    assert _delta(r.world, q=0.0)["rejection_reason"] == "invalid_transfer_quantity"
    assert _delta(r.world, q=float("nan"))["rejection_reason"] == "invalid_transfer_quantity"
    assert _delta(r.world, q=100.0)["rejection_reason"] == "invalid_transfer_quantity"
    assert psc.deltas_checksum(r.world) == ck
    assert psc.deltas_of(r.world) == {}


def test_24_delta_revision_chain_and_stable_ids():
    r = _rt()
    a = _delta(r.world, rev=0, tick=3)
    b = _delta(r.world, rev=1, q=0.05, tick=4)
    assert a["delta_id"] == b["delta_id"] == "surface-column-delta-x3-y5"
    assert b["delta_revision"] == 2
    assert a["transaction_id"] != b["transaction_id"]
    d = psc.deltas_of(r.world)[(3, 5)]
    assert d.provenance["kind"] == psc.PROVENANCE_KIND and d.provenance["not_agent_action"] is True


def test_25_delta_does_not_touch_neighbours_or_baseline():
    r = _rt()
    nb = psc.baseline_column_at(r.world, 4, 5).baseline_checksum
    base = psc.baseline_column_at(r.world, 3, 5).baseline_checksum
    _delta(r.world)
    assert psc.baseline_column_at(r.world, 4, 5).baseline_checksum == nb
    assert psc.baseline_column_at(r.world, 3, 5).baseline_checksum == base
    assert psc.has_persistent_delta(r.world, 4, 5) is False


def test_26_receipts_are_wmt_compatible_and_not_agent_actions():
    r = _rt()
    rec = _delta(r.world)
    # Assertion correction (reported separately): the public receipt field is
    # ``schema_version`` (same name as WORLD_MATERIAL_TRANSACTION_V1 receipts).
    assert rec["schema_version"] == psc.TRANSACTION_SCHEMA == "WORLD_MATERIAL_TRANSACTION_V1"
    assert "transaction_schema" not in rec
    assert rec["operation_kind"] == psc.OPERATION_KIND
    assert rec["not_agent_action"] is True and rec["motor_vocabulary"] is False
    assert rec["recipe_match"] is False and rec["reward_created"] is False
    assert rec["physical_effects_active"] is False and rec["agent_accessible"] is False


def test_27_sparse_storage_is_o_modified_cells():
    r = _rt()
    for i in range(12):
        _delta(r.world, x=i, y=2 * i)
    s = psc.storage_summary(r.world)
    assert s["sparse_delta_count"] == 12
    assert s["dense_3d_volume_allocated"] is False
    assert s["cache_serialized"] is False
    assert s["materialized_baseline_storage_count"] <= s["cache_limit"]


# ---------------------------------------------------------------- snapshot / restore


def test_28_snapshot_contains_no_dense_volume():
    r = _rt()
    _delta(r.world)
    snap = r.snapshot()
    cols = snap["world"]["surface_columns"]
    text = json.dumps(cols)
    assert "cache" not in cols
    assert len(cols.get("deltas") or cols.get("sparse_deltas") or []) == 1
    assert len(text) < 64 * 1024


def test_29_json_roundtrip_restore_verified():
    r = _rt()
    _delta(r.world)
    back = PhysicalSystemRuntime.restore(json.loads(json.dumps(r.snapshot())))
    st = psc.state_of(back.world)
    assert st.restore_verification["status"] == "VERIFIED"
    assert psc.deltas_checksum(back.world) == psc.deltas_checksum(r.world)
    assert psc.resolved_column_dict(psc.resolved_column_at(back.world, 3, 5)) == psc.resolved_column_dict(
        psc.resolved_column_at(r.world, 3, 5)
    )


def test_30_restore_continuation_bitwise_equal():
    r = _rt()
    _delta(r.world)
    for _ in range(5):
        r.step()
    back = PhysicalSystemRuntime.restore(copy.deepcopy(r.snapshot()))
    for _ in range(5):
        r.step()
        back.step()
        assert _h(r.last_agent_observation) == _h(back.last_agent_observation)


def test_31_unknown_generator_version_rejected():
    r = _rt()
    snap = copy.deepcopy(r.snapshot())
    snap["world"]["surface_columns"]["generator_version"] = "SURFACE_COLUMN_GENERATOR_V999"
    if "config" in snap["world"]["surface_columns"]:
        snap["world"]["surface_columns"]["config"]["generator_version"] = "SURFACE_COLUMN_GENERATOR_V999"
    with pytest.raises((psc.SurfaceColumnValidationError, ValueError)):
        PhysicalSystemRuntime.restore(snap)


def test_32_tampered_delta_rejected_on_restore():
    r = _rt()
    _delta(r.world)
    snap = copy.deepcopy(r.snapshot())
    cols = snap["world"]["surface_columns"]
    key = "deltas" if "deltas" in cols else "sparse_deltas"
    row = cols[key][0]
    row["baseline_checksum"] = "0" * 16
    with pytest.raises((psc.SurfaceColumnValidationError, ValueError)):
        PhysicalSystemRuntime.restore(snap)


def test_33_old_snapshot_without_columns_restores_off():
    snap = copy.deepcopy(_mc().snapshot())
    snap["world"].pop("surface_columns", None)
    snap["config"].pop("procedural_surface_columns", None)
    back = PhysicalSystemRuntime.restore(snap)
    assert psc.state_of(back.world) is None
    assert psc.procedural_surface_columns_is_active(back.config) is False


def test_34_tiktaalik_snapshot_keys_unchanged():
    snap = PhysicalSystemRuntime(seed=17, config=tiktaalik_config()).snapshot()
    assert "procedural_surface_columns" not in snap["config"]
    assert "surface_columns" not in snap["world"]


def test_35_multi_content_snapshot_has_no_columns_state():
    snap = _mc().snapshot()
    assert "surface_columns" not in snap["world"]


def test_36_planet_copy_preserves_columns_and_deltas():
    r = _rt()
    _delta(r.world)
    dup = r.world.copy()
    assert psc.deltas_checksum(dup) == psc.deltas_checksum(r.world)
    _delta(dup, x=7, y=7)
    assert psc.has_persistent_delta(r.world, 7, 7) is False


# ---------------------------------------------------------------- agent / physics boundary


def test_37_agent_observations_bitwise_equal_to_multi_content():
    a, b = _mc(), _rt()
    _delta(b.world)
    psc.cell_inspection(b.world, 4, 4)
    for _ in range(30):
        a.step()
        b.step()
        assert _h(a.last_agent_observation) == _h(b.last_agent_observation)
        assert (a.body.x, a.body.y, a.body.vx, a.body.vy) == (b.body.x, b.body.y, b.body.vx, b.body.vy)


def test_38_optical_tensor_and_spatial_index_unchanged():
    a, b = _mc(), _rt()
    _delta(b.world)
    for _ in range(10):
        a.step()
        b.step()
    assert np.array_equal(a.world.surface_optical, b.world.surface_optical)
    assert checksum_of(a.world.spatial_contents) == checksum_of(b.world.spatial_contents)


def test_39_cognition_payload_audit_clean_and_tokens_registered():
    b = _rt()
    b.step()
    assert audit_cognition_payload(b.last_agent_observation) == []
    for tok in ("procedural_surface_columns", "surface_column", "surface_elevation", "modelled_depth"):
        assert tok in FORBIDDEN_TOKENS
    assert audit_cognition_payload(psc.cell_inspection(b.world, 1, 1))


def test_40_effect_flags_all_false():
    for key in ("agent_accessible", "physical_body_effect", "terrain_force_effect", "vision_effect",
                "traction_effect", "support_effect", "gravity_effect", "physical_effects_active"):
        assert psc.EFFECT_FLAGS[key] is False


# ---------------------------------------------------------------- Observer / V3


def test_41_observer_world_frame_researcher_only():
    b = _rt()
    b.step()
    frame = world_frame(b)
    cols = frame["surface_columns"]
    assert cols["researcher_only_view"] is True and cols["agent_accessible"] is False
    assert cols["geometry_role"] == "METADATA_ONLY"
    a = _mc()
    a.step()
    assert "surface_columns" not in world_frame(a)


def test_42_cell_inspection_distinct_from_indexed_contents():
    b = _rt()
    view = psc.cell_inspection(b.world, 3, 5)
    assert view["source_kind"] == "SURFACE_COLUMN_SUMMARY"
    assert view["layer_count"] == len(view["layers"])
    assert view["persistent_delta"] is False
    idx = b.world.spatial_contents
    assert all("surface-column" not in str(getattr(ref, "entity_id", "")) for ref in idx.by_entity.values())


def test_43_scientific_v3_section():
    empty = summarize_procedural_surface_columns([])
    assert empty["NOT_AVAILABLE"] == ["surface_column_event"]
    s = summarize_procedural_surface_columns([
        {"kind": "surface_column", "event": psc.EVENT_DELTA_COMMITTED, "interval_validation": True,
         "conservation_verified": True},
        {"kind": "surface_column", "event": psc.EVENT_DELTA_RESTORED},
    ])
    assert "setup_delta_conservation" in s["VERIFIED"]
    text = format_procedural_surface_columns_section(s)
    assert "PROCEDURAL SURFACE COLUMNS" in text and "PHYSICAL_EFFECTS_ACTIVE = NO" in text
    assert "support" in s["NOT_IMPLEMENTED"] and "gravity" in s["NOT_IMPLEMENTED"]


# ---------------------------------------------------------------- seed authority (t117 / t118)


def _pc_two_agent(seed=23):
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    return TwoAgentRuntime(seed=seed, config=acanthostega_procedural_columns_config())


def test_44_seed_comes_from_runtime_authority_not_terrain_meta():
    for seed in (17, 18, 1234):
        r = _rt(seed)
        st = psc.state_of(r.world)
        assert st.world_seed == r.seed == seed
        assert st.seed_source == psc.SEED_SOURCE
    assert not hasattr(psc, "world_seed_of")
    # A legacy terrain_meta seed present on the world is ignored.
    r = _rt(17)
    r.world.terrain_meta = {"experiment_seed": 999}
    r.world.surface_columns = None
    r.world.surface_column_deltas = {}
    st = psc.ensure_surface_columns_for_runtime(r.world, r.config, experiment_seed=17)
    assert st.world_seed == 17
    with pytest.raises(psc.SurfaceColumnValidationError):
        r.world.surface_columns = None
        psc.ensure_surface_columns_for_runtime(r.world, r.config, experiment_seed=None)


def test_45_missing_terrain_meta_does_not_change_column_identity():
    a, b = _rt(17), _rt(17)
    b.world.terrain_meta = None
    b.world.surface_columns = None
    b.world.surface_column_deltas = {}
    psc.ensure_surface_columns_for_runtime(b.world, b.config, experiment_seed=17)
    c = _rt(17)
    c.world.terrain_meta = {"experiment_seed": 5, "mode": "FLAT"}
    c.world.surface_columns = None
    psc.ensure_surface_columns_for_runtime(c.world, c.config, experiment_seed=17)
    ma = psc.state_of(a.world).manifest["manifest_checksum"]
    assert psc.state_of(b.world).manifest["manifest_checksum"] == ma
    assert psc.state_of(c.world).manifest["manifest_checksum"] == ma
    for x, y in [(0, 0), (3, 5), (20, 11)]:
        ref = psc.baseline_column_at(a.world, x, y).baseline_checksum
        assert psc.baseline_column_at(b.world, x, y).baseline_checksum == ref
        assert psc.baseline_column_at(c.world, x, y).baseline_checksum == ref


def test_46_single_two_agent_and_restore_resolve_same_world_seed():
    single = _rt(23)
    two = _pc_two_agent(23)
    st1, st2 = psc.state_of(single.world), psc.state_of(two.world)
    assert st2.world_seed == two.seed == 23
    assert [s.seed for s in two.slots] == [23, 24]  # agent streams differ, geology does not
    assert st1.manifest["manifest_checksum"] == st2.manifest["manifest_checksum"]
    psc.apply_surface_column_setup_delta(
        two.world, 3, 5, upper_layer_index=0, transfer_quantity=0.1, expected_revision=0,
        tick=0, researcher_id="t", reason="two-agent",
    )
    from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
    back = TwoAgentRuntime.restore(json.loads(json.dumps(two.snapshot())))
    st3 = psc.state_of(back.world)
    assert st3.world_seed == 23 and st3.restore_verification["status"] == "VERIFIED"
    assert psc.deltas_checksum(back.world) == psc.deltas_checksum(two.world)
    back_single = PhysicalSystemRuntime.restore(json.loads(json.dumps(single.snapshot())))
    assert psc.state_of(back_single.world).world_seed == 23


def test_47_terrain_config_change_does_not_replace_geology_seed():
    base = _rt(17)
    cfg = acanthostega_procedural_columns_config()
    cfg.planet.terrain.terrain_seed = 4242
    cfg.planet.terrain.correlation_scale = 3.0
    changed = PhysicalSystemRuntime(seed=17, config=cfg)
    sa, sb = psc.state_of(base.world), psc.state_of(changed.world)
    assert sb.world_seed == 17
    assert sa.manifest["manifest_checksum"] == sb.manifest["manifest_checksum"]
    assert psc.baseline_column_at(base.world, 7, 9).baseline_checksum == psc.baseline_column_at(
        changed.world, 7, 9
    ).baseline_checksum


def test_48_snapshot_stores_seed_provenance():
    r = _rt(31)
    prov = r.snapshot()["world"]["surface_columns"]["seed_provenance"]
    assert prov["world_seed"] == 31
    assert prov["authority"] == "EXPERIMENT_RUNTIME"
    assert prov["generator_version"] == psc.GENERATOR_VERSION
    assert prov["parameter_checksum"] == psc.state_of(r.world).parameter_checksum
    assert prov["terrain_meta_used"] is False and prov["terrain_seed_used"] is False


def test_49_columns_on_snapshot_without_seed_provenance_rejected():
    r = _rt(17)
    snap = copy.deepcopy(r.snapshot())
    snap["world"]["surface_columns"].pop("seed_provenance")
    with pytest.raises(psc.SurfaceColumnValidationError):
        PhysicalSystemRuntime.restore(snap)
    snap2 = copy.deepcopy(r.snapshot())
    snap2["world"]["surface_columns"]["seed_provenance"]["authority"] = "TERRAIN_META"
    with pytest.raises(psc.SurfaceColumnValidationError):
        PhysicalSystemRuntime.restore(snap2)


def test_50_snapshot_world_seed_mismatch_is_explicit_error():
    r = _rt(17)
    snap = copy.deepcopy(r.snapshot())
    snap["seed"] = 18  # runtime world seed authority disagrees with stored geology seed
    with pytest.raises(psc.SurfaceColumnValidationError, match="does not match"):
        PhysicalSystemRuntime.restore(snap)
    snap2 = copy.deepcopy(r.snapshot())
    snap2["world"]["surface_columns"]["world_seed"] = 18
    with pytest.raises(psc.SurfaceColumnValidationError):
        PhysicalSystemRuntime.restore(snap2)


def test_51_off_paths_need_no_seed_and_do_not_fail():
    for cfg in (tiktaalik_config(), acanthostega_multi_content_config()):
        r = PhysicalSystemRuntime(seed=17, config=cfg)
        assert psc.ensure_surface_columns_for_runtime(r.world, r.config, experiment_seed=None) is None
        back = PhysicalSystemRuntime.restore(json.loads(json.dumps(r.snapshot())))
        assert psc.state_of(back.world) is None
        back.step()
