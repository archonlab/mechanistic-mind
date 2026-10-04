"""ACANTHOSTEGA CONSERVATIVE SURFACE COLUMN TRANSFER (tests 1-53, numbered as in the stage spec).

One researcher-only TRANSFER_SURFACE_COLUMN_SLICE: a contiguous top slice leaves one
procedural column and becomes the new top layer of another, as one atomic WMT pair
commit with sparse persistent deltas. physical_effects_active = false,
agent_accessible = false, geometry_role = METADATA_ONLY.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from mechanistic_mind.model.acanthostega import (
    acanthostega_column_transfer_config,
    acanthostega_procedural_columns_config,
)
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import conservative_surface_column_transfer as cst
from mechanistic_mind.physical_system import procedural_surface_columns as psc
from mechanistic_mind.physical_system import world_material_transaction as wmt
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_COLUMN_TRANSFER,
    PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS,
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
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.passive_material_properties import derive_effective_properties
from mechanistic_mind.physical_system.physical_surface_optical_coating import DERIVATION_VERSION
from mechanistic_mind.physical_system.resource_objects import MaterialComponent
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.spatial_contents import checksum_of
from mechanistic_mind.scientific_v3.surface_column_transfer_summary import (
    format_surface_column_transfer_section,
    summarize_surface_column_transfer,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "acanthostega_column_transfer"
FROZEN = "1621ef2c154864d1"
MID = cst.MECHANISM_ID
TOL = 1e-12
SRC, DST = (3, 5), (4, 5)


def _h(x) -> str:
    return hashlib.sha256(repr(x).encode()).hexdigest()[:16]


def _rt(seed: int = 17) -> PhysicalSystemRuntime:
    return PhysicalSystemRuntime(seed=seed, config=acanthostega_column_transfer_config())


def _pc(seed: int = 17) -> PhysicalSystemRuntime:
    return PhysicalSystemRuntime(seed=seed, config=acanthostega_procedural_columns_config())


def _kw(src=SRC, dst=DST, t=0.25, rs=0, rd=0, tick=0, **extra):
    out = dict(
        source_cell_x=src[0], source_cell_y=src[1], destination_cell_x=dst[0], destination_cell_y=dst[1],
        requested_thickness=t, expected_source_revision=rs, expected_destination_revision=rd, tick=tick,
    )
    out.update(extra)
    return out


def _transfer(r, **kw):
    return cst.apply_surface_column_transfer(r.world, r.config, world_seed=r.seed, **_kw(**kw))


def _col(r, cell):
    return psc.resolved_column_at(r.world, *cell)


def _state(r, cells=(SRC, DST)):
    """Complete authoritative state of the given columns + delta map checksum."""
    return (
        tuple(psc.resolved_column_dict(_col(r, c))["resolved_checksum"] for c in cells),
        tuple(_col(r, c)["delta_revision"] for c in cells),
        tuple(_col(r, c)["surface_elevation"] for c in cells),
        psc.deltas_checksum(r.world),
        len(psc.deltas_of(r.world)),
    )


def _summary(r, cell):
    return psc.mass_summary(_col(r, cell)["layers"])


@pytest.fixture()
def done():
    """Fresh runtime with one committed 0.25 transfer SRC -> DST, plus the pre-transfer columns."""
    r = _rt()
    before = {c: dict(_col(r, c)) for c in (SRC, DST)}
    receipt = _transfer(r)
    assert receipt["status"] == "COMMITTED", receipt
    return r, before, receipt


# ---------------------------------------------------------------- transfer (1-15)


def test_01_valid_top_slice_transfer_commits(done):
    r, _, receipt = done
    assert receipt["receipt_kind"] == "SURFACE_COLUMN_TRANSFER"
    assert receipt["operation_kind"] == "TRANSFER_SURFACE_COLUMN_SLICE"
    assert receipt["event"] == cst.EVENT_COMMITTED
    assert receipt["selection_provenance"] == "INTERVENTION_SETUP"
    for flag in ("agent_action", "agent_accessible", "physical_effects_active", "resource_spawned",
                 "recipe_match", "semantic_effect"):
        assert receipt[flag] is False
    assert receipt["researcher_only"] is True
    assert receipt["committed_thickness"] == 0.25
    assert receipt["source_cell"] == list(SRC) and receipt["destination_cell"] == list(DST)


def test_02_source_elevation_decreases_exactly_by_thickness(done):
    r, before, receipt = done
    e0 = before[SRC]["surface_elevation"]
    e1 = _col(r, SRC)["surface_elevation"]
    assert e1 == e0 - 0.25
    assert abs((e0 - e1) - 0.25) <= TOL
    assert receipt["source_elevation_after"] == e1
    assert abs(_col(r, SRC)["modelled_depth"] - (4.0 - 0.25)) <= TOL


def test_03_destination_elevation_increases_exactly_by_thickness(done):
    r, before, receipt = done
    e0 = before[DST]["surface_elevation"]
    e1 = _col(r, DST)["surface_elevation"]
    assert e1 == e0 + 0.25
    assert abs((e1 - e0) - 0.25) <= TOL
    assert abs(_col(r, DST)["modelled_depth"] - (4.0 + 0.25)) <= TOL
    # fixed lower datum is unchanged for both columns
    for cell in (SRC, DST):
        base = psc.baseline_column_at(r.world, *cell)
        c = _col(r, cell)
        assert abs((c["surface_elevation"] - c["modelled_depth"]) - cst.fixed_lower_datum(base)) <= TOL


def test_04_source_top_layer_decreases_correctly(done):
    r, before, _ = done
    top0 = before[SRC]["layers"][0]
    after = _col(r, SRC)["layers"]
    assert len(after) == len(before[SRC]["layers"])
    assert abs(after[0].thickness - (top0.thickness - 0.25)) <= TOL
    assert after[0].top_depth == 0.0
    assert after[0].density == top0.density
    for old, new in zip(before[SRC]["layers"][1:], after[1:]):
        assert abs(new.top_depth - (old.top_depth - 0.25)) <= TOL
        assert new.thickness == old.thickness and new.density == old.density
        assert new.composition == old.composition
    assert psc.validate_layers(after, _col(r, SRC)["modelled_depth"])["verified"]


def test_05_destination_receives_identical_physical_slice(done):
    r, before, receipt = done
    top0 = before[SRC]["layers"][0]
    dst_layers = _col(r, DST)["layers"]
    sl = dst_layers[0]
    assert receipt["layer_merge_status"] == cst.SEPARATE
    assert (sl.top_depth, sl.bottom_depth, sl.thickness) == (0.0, 0.25, 0.25)
    assert sl.density == top0.density
    assert sl.material_property_derivation_version == top0.material_property_derivation_version
    expect = {cid: a * (0.25 / top0.thickness) for cid, a in top0.composition}
    assert {cid: a for cid, a in sl.composition} == expect
    assert receipt["transferred_component_amounts"] == expect
    for old, new in zip(before[DST]["layers"], dst_layers[1:]):
        assert abs(new.top_depth - (old.top_depth + 0.25)) <= TOL
        assert new.composition == old.composition and new.density == old.density


def test_06_mass_conserved(done):
    r, before, receipt = done
    b = sum(psc.mass_summary(before[c]["layers"])["total_mass_per_area"] for c in (SRC, DST))
    a = sum(_summary(r, c)["total_mass_per_area"] for c in (SRC, DST))
    assert abs(a - b) <= TOL
    loss = psc.mass_summary(before[SRC]["layers"])["total_mass_per_area"] - _summary(r, SRC)["total_mass_per_area"]
    gain = _summary(r, DST)["total_mass_per_area"] - psc.mass_summary(before[DST]["layers"])["total_mass_per_area"]
    assert abs(loss - receipt["transferred_mass_per_area"]) <= TOL
    assert abs(gain - receipt["transferred_mass_per_area"]) <= TOL
    assert receipt["transferred_mass_per_area"] == 0.25 * before[SRC]["layers"][0].density
    assert receipt["conservation"]["mass"]["verified"] is True


def test_07_quantity_conserved(done):
    r, before, receipt = done
    b = sum(psc.mass_summary(before[c]["layers"])["total_quantity_per_area"] for c in (SRC, DST))
    a = sum(_summary(r, c)["total_quantity_per_area"] for c in (SRC, DST))
    assert abs(a - b) <= TOL
    assert receipt["transferred_quantity_per_area"] == 0.25
    # quantity is volume per area, not mass: mass == quantity * density
    assert receipt["transferred_mass_per_area"] != receipt["transferred_quantity_per_area"]
    assert receipt["conservation"]["quantity"]["verified"] is True


def test_08_every_component_conserved(done):
    r, before, receipt = done
    comps_b, comps_a = {}, {}
    for c in (SRC, DST):
        for cid, v in psc.mass_summary(before[c]["layers"])["component_quantity_per_area"].items():
            comps_b[cid] = comps_b.get(cid, 0.0) + v
        for cid, v in _summary(r, c)["component_quantity_per_area"].items():
            comps_a[cid] = comps_a.get(cid, 0.0) + v
    assert set(comps_a) == set(comps_b) == set(psc.COMPONENT_IDS)
    for cid in comps_b:
        assert abs(comps_a[cid] - comps_b[cid]) <= TOL, cid
    assert receipt["conservation"]["components"]["verified"] is True
    assert all(v > 0 and math.isfinite(v) for v in receipt["transferred_component_amounts"].values())


def test_09_density_preserved(done):
    r, before, receipt = done
    assert receipt["slice_density"] == before[SRC]["layers"][0].density
    assert _col(r, DST)["layers"][0].density == before[SRC]["layers"][0].density
    assert _col(r, SRC)["layers"][0].density == before[SRC]["layers"][0].density


def test_10_passive_properties_derive_consistently(done):
    r, before, _ = done
    def props(layer):
        return derive_effective_properties([{"component_id": c, "amount": a} for c, a in layer.composition])
    src_top = props(before[SRC]["layers"][0])
    slice_ = props(_col(r, DST)["layers"][0])
    rest = props(_col(r, SRC)["layers"][0])
    for key, val in src_top.items():
        if isinstance(val, float):
            assert abs(slice_[key] - val) <= 1e-9, key
            assert abs(rest[key] - val) <= 1e-9, key


def test_11_revisions_increment(done):
    r, _, receipt = done
    assert _col(r, SRC)["delta_revision"] == 1 and _col(r, DST)["delta_revision"] == 1
    assert (receipt["source_revision_before"], receipt["source_revision_after"]) == (0, 1)
    assert (receipt["destination_revision_before"], receipt["destination_revision_after"]) == (0, 1)
    again = _transfer(r, t=0.1, rs=1, rd=1, tick=1)
    assert again["status"] == "COMMITTED"
    assert _col(r, SRC)["delta_revision"] == 2 and _col(r, DST)["delta_revision"] == 2


def test_12_both_deltas_share_transaction_and_transfer_ref(done):
    r, _, receipt = done
    ds, dd = psc.deltas_of(r.world)[SRC], psc.deltas_of(r.world)[DST]
    assert ds.delta_id == "surface-column-delta-x3-y5" and dd.delta_id == "surface-column-delta-x4-y5"
    for d, role, opp in ((ds, "SOURCE", list(DST)), (dd, "DESTINATION", list(SRC))):
        p = d.provenance
        assert p["last_transaction_id"] == receipt["transaction_id"]
        assert p["last_transfer_id"] == receipt["transfer_id"]
        assert p["transfer_role"] == role and p["opposite_cell"] == opp
        assert p["previous_delta_revision"] == 0
        assert p["baseline_checksum"] == d.baseline_checksum
        assert receipt["transaction_id"] in d.source_transaction_ids
        assert len(p["transfer_refs"]) <= cst.TRANSFER_REF_LIMIT
        assert "resulting_layers" not in json.dumps(p) and "layers" not in p  # never the opposite column


def test_13_neighbours_unchanged(done):
    r, _, _ = done
    fresh = _rt()
    for cell in ((2, 5), (5, 5), (3, 4), (3, 6), (4, 4), (4, 6)):
        assert _col(r, cell)["resolved_checksum"] == _col(fresh, cell)["resolved_checksum"]
        assert _col(r, cell)["has_persistent_delta"] is False
    assert set(psc.deltas_of(r.world)) == {SRC, DST}


def test_14_baselines_unchanged(done):
    r, before, _ = done
    for cell in (SRC, DST):
        base = psc.baseline_column_at(r.world, *cell)
        assert base.baseline_checksum == before[cell]["baseline_checksum"]
        regen = psc.generate_baseline_v1(world_seed=17, cell_x=cell[0], cell_y=cell[1], width=32, height=32,
                                         cfg=psc.state_of(r.world).config)
        assert regen == base
        assert _col(r, cell)["resolved_checksum"] != base.baseline_checksum


def test_15_repeated_query_does_not_mutate(done):
    r, _, _ = done
    s0 = _state(r)
    for _ in range(5):
        psc.resolved_column_at(r.world, *SRC)
        psc.cell_inspection(r.world, *DST)
        cst.cell_transfer_view(r.world, *SRC)
        cst.researcher_summary(r.world)
        psc.column_mass_summary(r.world, *DST)
    assert _state(r) == s0


# ---------------------------------------------------------------- rejections (16-27)


def _rejected(r, code, **kw):
    s0 = _state(r)
    receipt = _transfer(r, **kw)
    assert receipt["status"] == "REJECTED", receipt
    assert receipt["rejection_reason"] == code, receipt
    assert receipt["event"] == cst.EVENT_REJECTED
    assert receipt["committed_thickness"] == 0.0
    assert receipt["atomic_pair"]["touched_columns"] == 0
    assert _state(r) == s0
    return receipt


def test_16_zero_thickness_rejected():
    _rejected(_rt(), "ZERO_THICKNESS", t=0.0)


def test_17_negative_thickness_rejected():
    _rejected(_rt(), "NEGATIVE_THICKNESS", t=-0.1)


def test_18_non_finite_thickness_rejected():
    r = _rt()
    for bad in (float("nan"), float("inf"), float("-inf"), "abc", None):
        _rejected(r, "NON_FINITE_THICKNESS", t=bad)


def test_19_same_wrapped_source_and_destination_rejected():
    r = _rt()
    _rejected(r, "SAME_WRAPPED_CELL", src=(3, 5), dst=(3, 5))
    _rejected(r, "SAME_WRAPPED_CELL", src=(3, 5), dst=(35, -27))  # 35 % 32 == 3, -27 % 32 == 5
    # wrapping is applied before preflight in world (x, y) order
    ok = _transfer(r, src=(-29, 37), dst=(4, 5))
    assert ok["status"] == "COMMITTED" and ok["source_cell"] == [3, 5]


def test_20_crossing_layer_boundary_rejected():
    r = _rt()
    top = _col(r, SRC)["layers"][0].thickness
    rec = _rejected(r, "CROSSES_LAYER_BOUNDARY", t=top + 1e-6)
    assert rec["preconditions"]["within_source_top_layer"] is False
    # exactly the whole top layer is allowed (does not cross)
    whole = _transfer(r, t=top)
    assert whole["status"] == "COMMITTED" and whole["source_layer_removed"] is True
    assert len(_col(r, SRC)["layers"]) == 2


def test_21_insufficient_source_depth_rejected():
    r = _rt()
    rs = rd = 0
    for _ in range(2):  # remove two whole top layers: depth 4.0 -> ~1.67
        top = _col(r, SRC)["layers"][0].thickness
        assert _transfer(r, t=top, rs=rs, rd=rd)["status"] == "COMMITTED"
        rs += 1
        rd += 1
    depth = _col(r, SRC)["modelled_depth"]
    assert depth > 0.5
    rec = _rejected(r, "INSUFFICIENT_SOURCE_DEPTH", t=depth - 0.4, rs=rs, rd=rd)
    assert rec["preconditions"]["source_depth_above_minimum"] is False
    assert cst.ConservativeSurfaceColumnTransferConfig().minimum_resolved_depth == 0.5


def test_22_stale_source_revision_rejected():
    r = _rt()
    _rejected(r, "STALE_SOURCE_REVISION", rs=3)


def test_23_stale_destination_revision_rejected():
    r = _rt()
    _rejected(r, "STALE_DESTINATION_REVISION", rd=1)


def test_24_unknown_generator_rejected():
    r = _rt()
    assert _transfer(r)["status"] == "COMMITTED"
    psc.deltas_of(r.world)[SRC].baseline_generator_version = "SURFACE_COLUMN_GENERATOR_V999"
    _rejected(r, "UNKNOWN_GENERATOR_VERSION", t=0.1, rs=1, rd=1)
    r2 = _rt()
    _state(r2)  # baselines cached before the config claims an unknown generator
    psc.state_of(r2.world).config.generator_version = "SURFACE_COLUMN_GENERATOR_V999"
    _rejected(r2, "UNKNOWN_GENERATOR_VERSION")


def test_25_baseline_checksum_mismatch_rejected():
    r = _rt()
    assert _transfer(r)["status"] == "COMMITTED"
    psc.deltas_of(r.world)[SRC].baseline_checksum = "0" * 16
    _rejected(r, "SOURCE_BASELINE_CHECKSUM_MISMATCH", t=0.1, rs=1, rd=1)
    r2 = _rt()
    assert _transfer(r2)["status"] == "COMMITTED"
    psc.deltas_of(r2.world)[DST].baseline_checksum = "f" * 16
    _rejected(r2, "DESTINATION_BASELINE_CHECKSUM_MISMATCH", t=0.1, rs=1, rd=1)


def test_26_layer_limit_overflow_rejected():
    r = _rt()
    dst = (10, 10)
    sources = [(12, 12), (14, 14), (16, 16), (18, 18), (20, 20), (22, 22)]
    assert cst.transfer_state_of(r.world).config.max_layers_per_column == 8
    for i, src in enumerate(sources[:5]):
        rec = _transfer(r, src=src, dst=dst, t=0.05, rs=0, rd=i)
        assert rec["status"] == "COMMITTED" and rec["layer_merge_status"] == cst.SEPARATE
    assert len(_col(r, dst)["layers"]) == 8
    rec = _rejected(r, "LAYER_LIMIT_EXCEEDED", src=sources[5], dst=dst, t=0.05, rs=0, rd=5)
    assert rec["preconditions"]["destination_layer_limit_ok"] is False


def test_27_any_rejection_leaves_both_columns_unchanged():
    r = _rt()
    assert _transfer(r)["status"] == "COMMITTED"
    s0 = _state(r)
    bad = [dict(t=0.0, rs=1, rd=1), dict(t=-1.0, rs=1, rd=1), dict(t=float("nan"), rs=1, rd=1),
           dict(t=10.0, rs=1, rd=1), dict(t=0.1, rs=0, rd=1), dict(t=0.1, rs=1, rd=0),
           dict(src=SRC, dst=SRC, t=0.1, rs=1, rd=1),
           dict(t=0.1, rs=1, rd=1, selection_provenance="AGENT_MOTOR"),
           dict(t=0.1, rs=1, rd=1, agent_action=True)]
    for kw in bad:
        rec = _transfer(r, **kw)
        assert rec["status"] == "REJECTED", kw
    assert _state(r) == s0
    tiny = _rt()
    tiny_cfg = acanthostega_procedural_columns_config()
    rec = cst.apply_surface_column_transfer(tiny.world, tiny_cfg, world_seed=17, **_kw())
    assert rec["status"] == "REJECTED" and rec["rejection_reason"] == "MECHANISM_INACTIVE"


# ---------------------------------------------------------------- atomicity / conflicts (28-33)


def _boom(*_a, **_k):
    raise RuntimeError("forced")


def test_28_forced_exception_before_commit_changes_neither(monkeypatch):
    r = _rt()
    s0 = _state(r)
    monkeypatch.setattr(cst, "_hook_before_publish", _boom)
    rec = _transfer(r)
    assert rec["status"] == "REJECTED" and rec["rejection_reason"].startswith("COMMIT_EXCEPTION")
    assert _state(r) == s0
    assert cst.transfer_state_of(r.world).committed_transfer_ids == []


def test_29_forced_exception_during_candidate_construction_changes_neither(monkeypatch):
    for stage in ("resolve", "split", "place", "deltas"):
        r = _rt()
        s0 = _state(r)
        monkeypatch.setattr(cst, "_hook_candidate_construction",
                            lambda s, _stage=stage: _boom() if s == _stage else None)
        rec = _transfer(r)
        assert rec["status"] == "REJECTED" and rec["rejection_reason"] == "CANDIDATE_CONSTRUCTION_FAILED", stage
        assert _state(r) == s0


def test_30_cannot_leave_only_source_changed(monkeypatch):
    r = _rt()
    s0 = _state(r)
    monkeypatch.setattr(cst, "_hook_before_destination_write", _boom)
    rec = _transfer(r)
    assert rec["status"] == "REJECTED"
    assert _state(r) == s0
    assert not psc.has_persistent_delta(r.world, *SRC) and not psc.has_persistent_delta(r.world, *DST)
    monkeypatch.undo()
    ok = _transfer(r)
    assert ok["status"] == "COMMITTED"
    assert psc.has_persistent_delta(r.world, *SRC) and psc.has_persistent_delta(r.world, *DST)


def test_31_duplicate_transaction_id_does_not_repeat_transfer():
    r = _rt()
    plan = cst.plan_surface_column_transfer(r.world, r.config, world_seed=17, **_kw())
    first = cst.commit_surface_column_transfer(r.world, plan)
    assert first["status"] == "COMMITTED"
    s1 = _state(r)
    second = cst.commit_surface_column_transfer(r.world, plan)
    assert second["status"] == "REJECTED" and second["rejection_reason"] == "ALREADY_COMMITTED"
    assert _state(r) == s1
    assert wmt.commit_material_transaction(r.world, plan)["receipt"]["rejection_reason"] == "ALREADY_COMMITTED"
    assert _state(r) == s1


def _proposals():
    return [
        dict(proposer_id="researcher_b", **{k: v for k, v in _kw(src=SRC, dst=(8, 8), t=0.2).items() if k != "tick"}),
        dict(proposer_id="researcher_a", **{k: v for k, v in _kw(src=SRC, dst=DST, t=0.3).items() if k != "tick"}),
        dict(proposer_id="researcher_c", **{k: v for k, v in _kw(src=(9, 9), dst=(10, 9), t=0.1).items() if k != "tick"}),
    ]


def test_32_same_tick_conflicting_proposals_resolve_deterministically():
    r = _rt()
    out = cst.resolve_transfer_proposals(r.world, r.config, _proposals(), tick=4, world_seed=17)
    by = {rec["researcher_id"]: rec for rec in out}
    assert by["researcher_a"]["status"] == "COMMITTED"          # first in proposer order
    assert by["researcher_b"]["status"] == "REJECTED"
    assert by["researcher_b"]["rejection_reason"] == "STALE_SOURCE_REVISION"
    assert by["researcher_c"]["status"] == "COMMITTED"          # independent cells
    assert cst.transfer_state_of(r.world).counters["stale_conflicts"] == 1
    assert not psc.has_persistent_delta(r.world, 8, 8)


def test_33_process_order_permutation_gives_same_result():
    import itertools

    results = []
    for perm in itertools.permutations(_proposals()):
        r = _rt()
        out = cst.resolve_transfer_proposals(r.world, r.config, list(perm), tick=4, world_seed=17)
        results.append((
            tuple((rec["researcher_id"], rec["status"], rec["rejection_reason"], rec["transfer_id"]) for rec in out),
            psc.deltas_checksum(r.world),
        ))
    assert len(set(results)) == 1


# ---------------------------------------------------------------- persistence (34-40)


def test_34_cache_eviction_preserves_both_deltas_and_reset_is_canonical(done):
    r, _, _ = done
    s0 = _state(r)
    st = psc.state_of(r.world)
    for x in range(32):
        for y in range(12):
            psc.baseline_column_at(r.world, x, y)
    assert st.cache_evictions > 0 and len(st.cache) <= st.config.cache_limit
    assert _state(r) == s0
    reset = _rt()  # reset = new canonical world from the same runtime seed
    assert psc.deltas_of(reset.world) == {}
    assert _col(reset, SRC)["resolved_checksum"] == _col(reset, SRC)["baseline_checksum"]


def test_35_snapshot_stores_deltas_not_baselines(done):
    r, _, _ = done
    cols = r.snapshot()["world"]["surface_columns"]
    assert len(cols["deltas"]) == 2
    assert "cache" not in cols and "baselines" not in cols
    tr = cols["column_transfer"]
    assert tr["schema"] == cst.STATE_SCHEMA
    assert "resulting_layers" not in json.dumps(tr) and "baseline_layers" not in json.dumps(tr)
    assert len(tr["history"]) <= cst.HISTORY_LIMIT
    assert len(json.dumps(cols)) < 64 * 1024
    # the receipt carries bounded rows only, never a full column
    for row in tr["history"]:
        assert "resulting_layers" not in json.dumps(row)


def test_36_restore_reproduces_checksums(done):
    r, _, _ = done
    back = PhysicalSystemRuntime.restore(json.loads(json.dumps(r.snapshot())))
    for cell in (SRC, DST):
        assert _col(back, cell)["resolved_checksum"] == _col(r, cell)["resolved_checksum"]
        assert _col(back, cell)["surface_elevation"] == _col(r, cell)["surface_elevation"]
    assert psc.deltas_checksum(back.world) == psc.deltas_checksum(r.world)
    ver = cst.transfer_state_of(back.world).restore_verification
    assert ver["verified"] is True and ver["transfer_delta_count"] == 2
    assert ver["closed_world_residual_max"] <= 1e-9 and ver["per_column_residual_max"] <= 1e-9
    assert all(row["conservation_vs_baseline_verified"] for row in psc.state_of(back.world).restore_verification["deltas"])


def test_37_restore_does_not_repeat_transfer_or_reuse_ids(done):
    r, _, receipt = done
    back = PhysicalSystemRuntime.restore(json.loads(json.dumps(r.snapshot())))
    assert len(psc.deltas_of(back.world)) == 2
    assert _col(back, SRC)["delta_revision"] == 1
    ts = cst.transfer_state_of(back.world)
    assert ts.counters["committed"] == 1 and ts.committed_transfer_ids == [receipt["transfer_id"]]
    nxt = _transfer(back, t=0.1, rs=1, rd=1, tick=0)
    assert nxt["status"] == "COMMITTED"
    assert nxt["transaction_id"] != receipt["transaction_id"]
    assert nxt["transfer_id"] != receipt["transfer_id"]
    assert receipt["transaction_id"] in back.world.material_transaction_committed_ids


def test_38_seed_provenance_mismatch_rejects(done):
    r, _, _ = done
    snap = copy.deepcopy(r.snapshot())
    snap["world"]["surface_columns"]["column_transfer"]["seed_provenance_checksum"] = "0" * 16
    with pytest.raises((psc.SurfaceColumnValidationError, ValueError)):
        PhysicalSystemRuntime.restore(snap)
    snap = copy.deepcopy(r.snapshot())
    snap["world"]["surface_columns"]["column_transfer"]["world_seed"] = 99
    with pytest.raises((psc.SurfaceColumnValidationError, ValueError)):
        PhysicalSystemRuntime.restore(snap)
    with pytest.raises((psc.SurfaceColumnValidationError, ValueError)):
        PhysicalSystemRuntime.restore(copy.deepcopy(r.snapshot()), world_seed=99)
    # live preflight also refuses a seed that is not the runtime authority
    rec = cst.apply_surface_column_transfer(r.world, r.config, world_seed=99, **_kw(rs=1, rd=1))
    assert rec["rejection_reason"] == "SEED_AUTHORITY_INVALID"


def test_39_unknown_generator_version_rejects(done):
    r, _, _ = done
    snap = copy.deepcopy(r.snapshot())
    snap["world"]["surface_columns"]["column_transfer"]["generator_version"] = "SURFACE_COLUMN_GENERATOR_V999"
    with pytest.raises((psc.SurfaceColumnValidationError, ValueError)):
        PhysicalSystemRuntime.restore(snap)
    snap = copy.deepcopy(r.snapshot())
    snap["world"]["surface_columns"]["deltas"][0]["baseline_generator_version"] = "SURFACE_COLUMN_GENERATOR_V999"
    with pytest.raises((psc.SurfaceColumnValidationError, ValueError)):
        PhysicalSystemRuntime.restore(snap)
    snap = copy.deepcopy(r.snapshot())
    snap["world"]["surface_columns"]["deltas"][0]["provenance"]["net_exchange"]["mass_per_area"] += 1.0
    with pytest.raises((psc.SurfaceColumnValidationError, ValueError)):
        PhysicalSystemRuntime.restore(snap)


def test_40_old_snapshot_restores_mechanism_off(done):
    old = PhysicalSystemRuntime.restore(copy.deepcopy(_pc().snapshot()))
    assert cst.conservative_surface_column_transfer_is_active(old.config) is False
    assert cst.transfer_state_of(old.world) is None
    assert getattr(old.config, "conservative_surface_column_transfer", None) is None
    r, _, _ = done
    snap = copy.deepcopy(r.snapshot())
    snap["config"].pop("conservative_surface_column_transfer")
    snap["world"]["surface_columns"].pop("column_transfer")
    back = PhysicalSystemRuntime.restore(snap)
    assert cst.conservative_surface_column_transfer_is_active(back.config) is False
    assert cst.transfer_state_of(back.world) is None
    # committed deltas remain authoritative geometry even with the mechanism OFF
    assert _col(back, SRC)["resolved_checksum"] == _col(r, SRC)["resolved_checksum"]
    rec = cst.apply_surface_column_transfer(back.world, back.config, world_seed=17, **_kw(rs=1, rd=1))
    assert rec["status"] == "REJECTED" and rec["rejection_reason"] == "MECHANISM_INACTIVE"


# ---------------------------------------------------------------- preservation (41-53)


@pytest.fixture(scope="module")
def probe():
    """Re-run the preservation probe (captured before any code change) and load the frozen baseline."""
    before = json.loads((RESULTS / "preservation_before.json").read_text())
    proc = subprocess.run(
        [sys.executable, str(RESULTS / "preservation_probe.py")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=600,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT)},
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    return before, json.loads(proc.stdout)


def test_41_tiktaalik_fingerprint_unchanged(probe):
    before, now = probe
    assert canonical_fingerprint(preset_canonical(PRESET_BETA31, seed=17)) == FROZEN
    assert now["beta31_fingerprint"] == before["beta31_fingerprint"] == FROZEN


def test_42_tiktaalik_mechanism_map_unchanged(probe):
    before, now = probe
    assert now["beta31_mechanism_map"] == before["beta31_mechanism_map"]
    assert MID not in beta31_mechanism_map()
    tik = tiktaalik_config()
    set_mechanism(tik, MID, True)
    cst.set_conservative_surface_column_transfer(tik, True)
    assert cst.conservative_surface_column_transfer_is_active(tik) is False
    assert getattr(tik, "conservative_surface_column_transfer", None) is None


def test_43_tiktaalik_snapshot_unchanged(probe):
    before, now = probe
    assert now["runtime"]["TIKTAALIK"] == before["runtime"]["TIKTAALIK"]
    snap = PhysicalSystemRuntime(seed=17, config=tiktaalik_config()).snapshot()
    assert "conservative_surface_column_transfer" not in snap["config"]
    assert "surface_columns" not in snap["world"]


def test_44_previous_acanthostega_presets_unchanged(probe):
    before, now = probe
    assert now == before  # preset canonical, identity, mechanism snapshot, runtime obs/body/snapshot/optical/T
    pc = preset_canonical(PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS, seed=17)["mechanisms"]
    ct = preset_canonical(PRESET_ACANTHOSTEGA_COLUMN_TRANSFER, seed=17)["mechanisms"]
    assert ct[MID] is True and MID not in pc
    assert {k: v for k, v in ct.items() if k != MID} == pc
    snap = _pc().snapshot()
    assert "column_transfer" not in snap["world"]["surface_columns"]
    assert "conservative_surface_column_transfer" not in snap["config"]


def test_45_material_combine_and_deposition_transactions_unchanged():
    import tests.test_acanthostega_world_material_transactions as W

    W.test_combine_matches_legacy_and_conserves()
    W.test_deposition_matches_legacy_including_depletion_and_rejection()
    W.test_same_tick_conflict_is_independent_of_runtime_order()
    W.test_invalid_plan_and_exception_leave_state_unchanged()


def test_46_multi_content_index_checksum_unchanged():
    r = _rt()
    before = checksum_of(r.world.spatial_contents)
    n_refs = len(r.world.spatial_contents.by_entity)
    assert _transfer(r)["status"] == "COMMITTED"
    assert checksum_of(r.world.spatial_contents) == before
    assert len(r.world.spatial_contents.by_entity) == n_refs
    assert all("column" not in str(k) for k in r.world.spatial_contents.by_entity)
    assert all("column" not in str(getattr(o, "object_id", "")) for o in r.world.resource_objects)


def _agent_cell(r):
    return (int(math.floor(r.body.x)) % 32, int(math.floor(r.body.y)) % 32)


def test_47_locomotion_unchanged():
    a, b = _pc(), _rt()
    cell = _agent_cell(b)
    assert _transfer(b, src=((cell[0] + 1) % 32, cell[1]), dst=cell, t=0.3)["status"] == "COMMITTED"
    for _ in range(25):
        a.step()
        b.step()
        assert (a.body.x, a.body.y, a.body.vx, a.body.vy) == (b.body.x, b.body.y, b.body.vx, b.body.vy)


def _put_deposit(r, cell, qty=0.4):
    deposit = SurfaceMaterialDeposit(
        deposit_id=deposit_id_for_cell(cell[0], cell[1]),
        cell_x=cell[0],
        cell_y=cell[1],
        mass=float(qty),
        quantity=float(qty),
        composition=(MaterialComponent("component_a", 1.0),),
        provenance={"lineage_refs": [{"event_id": "setup-deposit", "tick": -1}]},
        created_tick=-1,
        last_updated_tick=-1,
        optical_response=(0.2, 0.3, 0.4),
        optical_derivation_version=DERIVATION_VERSION,
        optical_source_event_ids=("setup-deposit",),
    )
    r.world.surface_material_deposits[deposit.deposit_id] = deposit
    return deposit


def _world_arrays(world):
    out = {}
    for k, v in sorted(vars(world).items()):
        if isinstance(v, np.ndarray):
            out[k] = _h(v.tobytes())
    return out


def test_48_traction_and_terrain_fields_unchanged():
    from mechanistic_mind.physical_system.surface_affinity_traction import plan_surface_traction

    r = _rt()
    _put_deposit(r, SRC)
    arrays = _world_arrays(r.world)
    assert "T" in arrays
    def lookups():
        return [repr(plan_surface_traction(world=r.world, x=c[0] + 0.5, y=c[1] + 0.5, tick=0, width=32, height=32))
                for c in (SRC, DST, (5, 5))]
    tr_before = lookups()
    assert _transfer(r)["status"] == "COMMITTED"
    assert _world_arrays(r.world) == arrays  # terrain potential/drag/gradients/optical/climate/resource fields
    assert lookups() == tr_before


def test_49_vision_and_surface_optical_unchanged():
    a, b = _pc(), _rt()
    assert _transfer(b)["status"] == "COMMITTED"
    opt = np.array(b.world.surface_optical, copy=True)
    for _ in range(10):
        a.step()
        b.step()
    assert np.array_equal(a.world.surface_optical, b.world.surface_optical)
    assert opt.shape == np.asarray(b.world.surface_optical).shape
    assert int(getattr(a.world, "surface_optical_coating_generation", 0) or 0) == int(
        getattr(b.world, "surface_optical_coating_generation", 0) or 0)


def test_50_agent_observation_unchanged():
    a, b = _pc(), _rt()
    cell = _agent_cell(b)
    assert _transfer(b, src=cell, dst=((cell[0] + 2) % 32, cell[1]), t=0.2)["status"] == "COMMITTED"
    for _ in range(30):
        a.step()
        b.step()
        assert _h(a.last_agent_observation) == _h(b.last_agent_observation)


def test_51_no_geology_or_transfer_tokens_leak_to_cognition(done):
    r, _, receipt = done
    for _ in range(3):
        r.step()
    assert audit_cognition_payload(r.last_agent_observation) == []
    for tok in ("conservative_surface_column_transfer", "TRANSFER_SURFACE_COLUMN_SLICE", "transfer_id",
                "fixed_lower_datum", "requested_thickness", "transferred_mass", "net_exchange",
                "surface-column", "surface_elevation", "transaction_id", "INTERVENTION_SETUP"):
        assert tok in FORBIDDEN_TOKENS, tok
    assert audit_cognition_payload(receipt)
    assert audit_cognition_payload(cst.cell_transfer_view(r.world, *SRC))
    from mechanistic_mind.physical_system import observation

    src = Path(observation.__file__).read_text()
    assert "conservative_surface_column_transfer import" not in src


def test_52_frontend_sources_and_bundle():
    app = (ROOT / "web" / "psy-observer" / "src" / "App.tsx").read_text()
    preset = (ROOT / "web" / "psy-observer" / "src" / "observer" / "modelPreset.ts").read_text()
    assert "Acanthostega Phase B Column Transfer" in preset
    assert "UI_PRESET_ACANTHOSTEGA_COLUMN_TRANSFER" in app
    assert 'data-testid="surface-column-transfer-inspector"' in app
    for label in ("researcher-only", "not agent-accessible", "authoritative world geometry",
                  "physical body effects inactive", "not an excavation action"):
        assert label in cst.VIEW_LABELS
    assert "surface-column-transfer" not in app.replace("surface-column-transfer-inspector", "").replace(
        "surface-column-transfer-labels", "")  # no transfer button / agent control
    dist = ROOT / "mechanistic_mind" / "ui" / "psy_observer_web" / "web_dist"
    bundle = "".join(p.read_text(errors="ignore") for p in dist.rglob("*.js"))
    assert "Acanthostega Phase B Column Transfer" in bundle
    assert "surface-column-transfer-inspector" in bundle
    assert (RESULTS / "frontend_tests.log").exists()


def test_53_acanthostega_suite_sentinel():
    names = sorted(p.name for p in (ROOT / "tests").glob("test_acanthostega_*.py"))
    assert "test_acanthostega_procedural_surface_columns.py" in names
    assert "test_acanthostega_column_transfer.py" in names
    assert normalize_preset_name("Acanthostega Phase B Column Transfer") == PRESET_ACANTHOSTEGA_COLUMN_TRANSFER
    assert normalize_preset_name("Acanthostega Phase B Procedural Columns") == PRESET_ACANTHOSTEGA_PROCEDURAL_COLUMNS


# ---------------------------------------------------------------- additional boundary checks


def test_54_surface_deposit_stays_on_its_horizontal_address():
    r = _rt()
    dep = _put_deposit(r, SRC)
    before = repr(dep.as_dict() if hasattr(dep, "as_dict") else vars(dep))
    gen = int(getattr(r.world, "surface_optical_coating_generation", 0) or 0)
    col_mass = _summary(r, SRC)["total_mass_per_area"]
    rec = _transfer(r)
    assert rec["status"] == "COMMITTED"
    now = r.world.surface_material_deposits[deposit_id_for_cell(*SRC)]
    assert now is dep and repr(now.as_dict() if hasattr(now, "as_dict") else vars(now)) == before
    assert (now.cell_x, now.cell_y) == SRC and deposit_id_for_cell(*DST) not in r.world.surface_material_deposits
    assert int(getattr(r.world, "surface_optical_coating_generation", 0) or 0) == gen
    # the deposit is not column material: column mass change == slice mass only
    assert abs((col_mass - _summary(r, SRC)["total_mass_per_area"]) - rec["transferred_mass_per_area"]) <= TOL
    assert not hasattr(now, "z") and not hasattr(now, "surface_elevation")


def test_55_canonical_adjacent_merge_policy():
    r = _rt()
    # back-and-forth: the slice returned to its source matches the source top layer exactly -> merge
    assert _transfer(r, t=0.25)["status"] == "COMMITTED"
    back = _transfer(r, src=DST, dst=SRC, t=0.25, rs=1, rd=1)
    assert back["status"] == "COMMITTED"
    assert back["layer_merge_status"] == cst.MERGED
    assert len(_col(r, SRC)["layers"]) == 3 and len(_col(r, DST)["layers"]) == 3
    fresh = _rt()
    for cell in (SRC, DST):
        assert abs(_col(r, cell)["surface_elevation"] - _col(fresh, cell)["surface_elevation"]) <= TOL
        a, b = _summary(r, cell), _summary(fresh, cell)
        assert abs(a["total_mass_per_area"] - b["total_mass_per_area"]) <= 1e-12
    # different density never merges; no component-id special cases
    l1, l2 = _col(fresh, SRC)["layers"][0], _col(fresh, DST)["layers"][0]
    assert cst.layers_mergeable(l1, l2, 1e-12)["mergeable"] is False
    assert "density" in cst.layers_mergeable(l1, l2, 1e-12)["mismatch"]
    assert cst.transfer_state_of(r.world).counters["merged"] == 1


def test_56_researcher_only_operation_not_in_agent_vocabularies():
    from mechanistic_mind.ui.psy_observer_web import session as session_mod

    assert cst.OPERATION_KIND == "TRANSFER_SURFACE_COLUMN_SLICE"
    pkg = ROOT / "mechanistic_mind"
    # endogenous motor vocabulary, composite motor, cognition / psyche / agent / PSC candidates
    files = [pkg / "physical_system" / "actions.py", pkg / "physical_system" / "composite_motor.py",
             pkg / "physical_system" / "psc_motor_resolution_shadow.py"]
    for rel in ("psyche", "agent", "mechanisms", "multi_agent"):
        files += list((pkg / rel).rglob("*.py"))
    assert len(files) > 5
    for f in files:
        text = f.read_text(errors="ignore")
        assert "TRANSFER_SURFACE_COLUMN_SLICE" not in text, f
        assert "conservative_surface_column_transfer" not in text, f
    src = Path(session_mod.__file__).read_text()
    assert "def researcher_surface_column_transfer" in src
    assert "selection_provenance=cst.SELECTION_PROVENANCE" in src and "agent_action=False" in src
    app = (ROOT / "web" / "psy-observer" / "src" / "App.tsx").read_text()
    assert "/api/research/surface-column-transfer" not in app  # no Observer control wired to it
    r = _rt()
    rec = _transfer(r, agent_action=True)
    assert rec["rejection_reason"] == "AGENT_ACTION_FORBIDDEN"
    rec = _transfer(r, selection_provenance="ENDOGENOUS")
    assert rec["rejection_reason"] == "INVALID_SELECTION_PROVENANCE"


def test_57_scientific_v3_and_analyzer_section(done):
    r, _, receipt = done
    snap_back = PhysicalSystemRuntime.restore(json.loads(json.dumps(r.snapshot())))
    events = list(cst.transfer_state_of(r.world).history) + [psc.state_of(snap_back.world).history[-1]]
    stale = _transfer(r, rs=0, rd=0)
    events.append(stale)
    s = summarize_surface_column_transfer(events, agent_leakage_hits=0, sparse_delta_count=2)
    assert s["section"] == "CONSERVATIVE SURFACE COLUMN TRANSFER"
    assert s["committed_count"] == 1 and s["rejected_count"] == 1 and s["stale_conflict_count"] == 1
    assert s["atomic_pair_verification"] == "VERIFIED"
    assert s["persistence_restore_verification"] == "VERIFIED"
    assert "mass_quantity_component_conservation" in s["VERIFIED"]
    for item in ("agent_excavation", "gravity", "support", "explicit_carried_material"):
        assert item in s["NOT_IMPLEMENTED"]
    assert s["conservation_residual_max"]["mass"] <= TOL
    text = format_surface_column_transfer_section(s)
    for needle in ("CONSERVATIVE SURFACE COLUMN TRANSFER", "OBSERVED:", "VERIFIED:", "REJECTED:",
                   "NOT_IMPLEMENTED:", "agent excavation not implemented", "gravity not implemented",
                   "support not implemented", "explicit carried material not implemented"):
        assert needle in text
    assert "progress" not in text.lower() and "█" not in text


def test_58_cost_touches_only_two_columns(done):
    r, _, receipt = done
    cost = receipt["cost"]
    assert cost["touched_columns"] == 2 and cost["full_world_scan"] is False and cost["world_clone"] is False
    assert cost["layer_ops"] <= 2 * 8 + len(psc.COMPONENT_IDS)
    assert len(psc.state_of(r.world).cache) <= 8  # no neighbourhood materialization
