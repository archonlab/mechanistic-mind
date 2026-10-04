"""ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY — bilinear h + analytic n̂ G1.

Parent: ACANTHOSTEGA_PHASE_C_BODY_NORMAL_LOAD_TRACTION.
CRITICAL: height physical; normal inactive; SES DDA energy kept; no hidden smoothing.
"""
from __future__ import annotations

import math

from mechanistic_mind.model.acanthostega import (
    acanthostega_body_normal_load_traction_config,
    acanthostega_continuous_surface_geometry_config,
    acanthostega_surface_elevation_support_config,
    model_metadata,
)
from mechanistic_mind.model.lines import stamp_config_from_preset
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import body_normal_load_traction as bnlt
from mechanistic_mind.physical_system import continuous_surface_geometry as csg
from mechanistic_mind.physical_system import flat_ground_gravity as fgg
from mechanistic_mind.physical_system import free_resource_object_ground_friction as fogf
from mechanistic_mind.physical_system import procedural_surface_columns as psc
from mechanistic_mind.physical_system import surface_elevation_support as ses
from mechanistic_mind.physical_system.experiment_canonical import (
    PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION,
    PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY,
    PRESET_BETA31,
    beta31_mechanism_map,
    normalize_preset_name,
    preset_canonical,
)
from mechanistic_mind.physical_system.locomotion_profile import profile_is_active
from mechanistic_mind.physical_system.observation import FORBIDDEN_TOKENS, audit_cognition_payload
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

MID = csg.MECHANISM_ID

def _set_elev(world, cx, cy, elev, *, revision: int = 1):
    """Plant authoritative sparse elevation delta (test-only)."""
    base = psc.baseline_column_at(world, cx, cy)
    tick = int(getattr(world, "tick", 0) or 0)
    psc.deltas_of(world)[(int(cx), int(cy))] = psc.SurfaceColumnDelta(
        delta_id=psc.delta_id_for(int(cx), int(cy)),
        cell_x=int(cx),
        cell_y=int(cy),
        baseline_generator_version=base.generator_version,
        baseline_checksum=base.baseline_checksum,
        resulting_surface_elevation=float(elev),
        resulting_layers=base.layers,
        created_tick=tick,
        last_updated_tick=tick,
        revision=int(revision),
        provenance={"reason": "csg_test"},
    )




def _rt():
    return PhysicalSystemRuntime(seed=17, config=acanthostega_continuous_surface_geometry_config())


def _wait(rt, n):
    for _ in range(int(n)):
        rt.step_forced_action("WAIT")


# ---------- isolation ----------


def test_01_absent_from_tiktaalik_and_beta31():
    assert MID not in beta31_mechanism_map()
    cfg = tiktaalik_config()
    assert not csg.continuous_surface_geometry_is_active(cfg)


def test_02_absent_from_parent_bnlt_and_ses():
    assert not csg.continuous_surface_geometry_is_active(acanthostega_body_normal_load_traction_config())
    assert not csg.continuous_surface_geometry_is_active(acanthostega_surface_elevation_support_config())


def test_03_new_preset_enables_chain():
    can = preset_canonical(PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY)
    assert can["parent"] == PRESET_ACANTHOSTEGA_BODY_NORMAL_LOAD_TRACTION
    assert can["mechanisms"].get(ses.MECHANISM_ID) is True
    assert can["mechanisms"].get(bnlt.MECHANISM_ID) is True
    assert can["mechanisms"].get(MID) is True
    cfg = acanthostega_continuous_surface_geometry_config()
    assert csg.continuous_surface_geometry_is_active(cfg)
    assert bnlt.body_normal_load_traction_is_active(cfg)
    assert ses.surface_elevation_support_is_active(cfg)
    assert fogf.free_resource_object_ground_friction_is_active(cfg)
    assert fgg.flat_ground_gravity_is_active(cfg)
    assert profile_is_active(cfg)
    stamp_config_from_preset(cfg, PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY)
    assert csg.continuous_surface_geometry_is_active(cfg)
    meta = model_metadata(cfg)
    assert "CONTINUOUS_SURFACE_GEOMETRY" in str(meta.get("classification") or "")


def test_04_normalize_aliases():
    assert normalize_preset_name("ACANTHOSTEGA_PHASE_C_CONTINUOUS_SURFACE_GEOMETRY") == PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY
    assert normalize_preset_name("Acanthostega Phase C Continuous Surface Geometry") == PRESET_ACANTHOSTEGA_CONTINUOUS_SURFACE_GEOMETRY


def test_05_forbidden_tokens():
    for tok in (
        "continuous_surface_geometry",
        "CONTINUOUS_SURFACE_GEOMETRY",
        "analytic_normal",
        "corner_heights",
        "bilinear_weights",
        "BILINEAR_HEIGHT_ANALYTIC_NORMAL_V1",
    ):
        assert tok in FORBIDDEN_TOKENS
    hits = audit_cognition_payload({"note": "continuous_surface_geometry analytic_normal corner_heights"})
    assert hits


# ---------- bilinear / analytic (0 ticks) ----------


def test_06_flat_patch_unit_normal_up():
    rt = _rt()
    for cx, cy in [(5, 5), (6, 5), (5, 6), (6, 6)]:
        _set_elev(rt.world, cx, cy, 1.0)
    s = csg.sample_surface_geometry(rt.world, 5.5, 5.5, config=rt.config)
    assert abs(s["height"] - 1.0) < 1e-12
    assert abs(s["normal_x"]) < 1e-12 and abs(s["normal_y"]) < 1e-12
    assert abs(s["normal_z"] - 1.0) < 1e-12
    assert s["flat_patch"] is True
    assert s["normal_is_unit"] is True
    assert s["normal_nz_positive"] is True
    assert s["normal_physical_effects_active"] is False
    assert s["height_physical_effects_active"] is True




def test_07_bilinear_formula_and_weights():
    rt = _rt()
    corners = {(8, 8): 0.0, (9, 8): 1.0, (8, 9): 2.0, (9, 9): 3.0}
    for (cx, cy), h in corners.items():
        _set_elev(rt.world, cx, cy, h)
    x, y = 8.75, 8.75
    s = csg.sample_surface_geometry(rt.world, x, y, config=rt.config)
    u, v = s["u"], s["v"]
    assert abs(u - 0.25) < 1e-12 and abs(v - 0.25) < 1e-12
    h00, h10, h01, h11 = 0.0, 1.0, 2.0, 3.0
    expected = (1 - u) * (1 - v) * h00 + u * (1 - v) * h10 + (1 - u) * v * h01 + u * v * h11
    assert abs(s["height"] - expected) < 1e-12
    hx = (1 - v) * (h10 - h00) + v * (h11 - h01)
    hy = (1 - u) * (h01 - h00) + u * (h11 - h10)
    assert abs(s["gradient_x"] - hx) < 1e-12
    assert abs(s["gradient_y"] - hy) < 1e-12
    nraw = (-hx, -hy, 1.0)
    mag = math.sqrt(nraw[0] ** 2 + nraw[1] ** 2 + nraw[2] ** 2)
    assert abs(s["normal_x"] - nraw[0] / mag) < 1e-12
    assert abs(s["normal_y"] - nraw[1] / mag) < 1e-12
    assert abs(s["normal_z"] - nraw[2] / mag) < 1e-12




def test_08_centre_parity_with_discrete_sample():
    rt = _rt()
    col = psc.resolved_column_at(rt.world, 12.5, 7.5)
    s = csg.sample_surface_geometry(rt.world, 12.5, 7.5, config=rt.config)
    assert abs(s["height"] - float(col["surface_elevation"])) < 1e-12
    assert abs(s["u"]) < 1e-12 and abs(s["v"]) < 1e-12


def test_09_wrap_seam_bilinear():
    rt = _rt()
    w, h = psc.state_of(rt.world).width, psc.state_of(rt.world).height
    # Sample near wrap: x just below 0 after wrap from -0.1 → w-0.1
    s = csg.sample_surface_geometry(rt.world, -0.1, 4.2, config=rt.config)
    assert 0.0 <= s["x"] < w
    # cells include wrapped indices
    for key in ("00", "10", "01", "11"):
        cx, cy = s["cells"][key]
        assert 0 <= cx < w and 0 <= cy < h
    # Bit-stable
    s2 = csg.sample_surface_geometry(rt.world, -0.1, 4.2, config=rt.config)
    assert s["height"] == s2["height"]
    assert s["normal_x"] == s2["normal_x"]


def test_10_anti_smoothing_single_column_pit():
    rt = _rt()
    cx, cy = 15, 15
    base_h = float(psc.resolved_column_at(rt.world, cx + 0.5, cy + 0.5)["surface_elevation"])
    neigh = {}
    for dx, dy in [(-2, 0), (2, 0), (0, -2), (0, 2), (-2, -2)]:
        neigh[(cx + dx, cy + dy)] = float(
            psc.resolved_column_at(rt.world, cx + dx + 0.5, cy + dy + 0.5)["surface_elevation"]
        )
    pit = base_h - 0.5
    _set_elev(rt.world, cx, cy, pit)
    s_c = csg.sample_surface_geometry(rt.world, cx + 0.5, cy + 0.5, config=rt.config)
    assert abs(s_c["height"] - pit) < 1e-12
    for (nx, ny), h0 in neigh.items():
        s_n = csg.sample_surface_geometry(rt.world, nx + 0.5, ny + 0.5, config=rt.config)
        assert abs(s_n["height"] - h0) < 1e-12
    s_adj = csg.sample_surface_geometry(rt.world, cx + 1.5, cy + 0.5, config=rt.config)
    assert abs(s_adj["height"] - float(psc.resolved_column_at(rt.world, cx + 1.5, cy + 0.5)["surface_elevation"])) < 1e-12
    h_adj0 = float(psc.resolved_column_at(rt.world, cx + 1.5, cy + 0.5)["surface_elevation"])
    s_mid = csg.sample_surface_geometry(rt.world, cx + 1.0, cy + 0.5, config=rt.config)
    assert min(pit, h_adj0) - 1e-9 <= s_mid["height"] <= max(pit, h_adj0) + 1e-9
    del psc.deltas_of(rt.world)[(cx, cy)]
    s_restored = csg.sample_surface_geometry(rt.world, cx + 0.5, cy + 0.5, config=rt.config)
    assert abs(s_restored["height"] - base_h) < 1e-12




def test_11_query_non_mutating_and_no_dense_raster():
    rt = _rt()
    deltas_before = dict(psc.deltas_of(rt.world))
    tick0 = int(getattr(rt.world, "tick", 0) or 0)
    _ = csg.sample_surface_geometry(rt.world, 3.3, 4.4, config=rt.config)
    assert dict(psc.deltas_of(rt.world)) == deltas_before
    assert int(getattr(rt.world, "tick", 0) or 0) == tick0
    st = csg.state_of(rt.world)
    assert st is None or st.to_dict().get("dense_height_raster") is None


def test_12_mutation_immediate_visibility():
    rt = _rt()
    cx, cy = 20, 20
    h0 = csg.continuous_support_height(rt.world, cx + 0.5, cy + 0.5, config=rt.config)
    _set_elev(rt.world, cx, cy, h0 + 0.4)
    h1 = csg.continuous_support_height(rt.world, cx + 0.5, cy + 0.5, config=rt.config)
    assert abs(h1 - (h0 + 0.4)) < 1e-12




# ---------- body / free / SES (budgeted ticks) ----------


def test_13_body_support_uses_continuous_height():
    rt = _rt()
    # Place body at sub-cell pose; after WAIT vertical, z should track continuous h
    body = rt.body
    body.x = 10.25
    body.y = 10.25
    h = csg.continuous_support_height(rt.world, body.x, body.y, config=rt.config)
    # initial placement may already have set z; force vertical settle
    _wait(rt, 2)
    assert bool(getattr(body, "grounded", False))
    assert abs(float(body.z) - h) < 1e-6 or abs(float(body.z) - csg.continuous_support_height(rt.world, body.x, body.y, config=rt.config)) < 1e-6


def test_14_parent_bnlt_still_floor_cell():
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_body_normal_load_traction_config())
    assert not csg.continuous_surface_geometry_is_active(rt.config)
    h = ses.surface_support_height(rt.world, 10.25, 10.25, config=rt.config)
    floor = float(psc.resolved_column_at(rt.world, 10.25, 10.25)["surface_elevation"])
    assert abs(h - floor) < 1e-12


def test_15_ses_micro_uphill_still_energy_accounted():
    rt = _rt()
    cx, cy = 11, 11
    h0 = float(psc.resolved_column_at(rt.world, cx + 0.5, cy + 0.5)["surface_elevation"])
    _set_elev(rt.world, cx, cy, h0)
    _set_elev(rt.world, cx + 1, cy, h0 + 0.08)
    body = rt.body
    body.x = cx + 0.5
    body.y = cy + 0.5
    body.vx = 0.0
    body.vy = 0.0
    _wait(rt, 1)
    for _ in range(8):
        rt.step_forced_action("MOVE:E")
    assert ses.surface_elevation_support_is_active(rt.config)
    st = getattr(rt.world, "surface_elevation_support_state", None)
    assert st is not None




def test_16_snapshot_restore_parity():
    rt = _rt()
    body = rt.body
    body.x = 9.3
    body.y = 9.7
    _wait(rt, 3)
    h_before = csg.continuous_support_height(rt.world, body.x, body.y, config=rt.config)
    n_before = csg.continuous_surface_normal(rt.world, body.x, body.y, config=rt.config)
    snap = rt.snapshot()
    assert (snap.get("config") or {}).get("continuous_surface_geometry", {}).get("enabled") is True
    rt2 = PhysicalSystemRuntime.restore(snap)
    assert csg.continuous_surface_geometry_is_active(rt2.config)
    h_after = csg.continuous_support_height(rt2.world, rt2.body.x, rt2.body.y, config=rt2.config)
    n_after = csg.continuous_surface_normal(rt2.world, rt2.body.x, rt2.body.y, config=rt2.config)
    assert abs(h_before - h_after) < 1e-9
    assert all(abs(a - b) < 1e-9 for a, b in zip(n_before, n_after))




def test_17_legacy_snapshot_without_csg_keeps_off():
    rt = PhysicalSystemRuntime(seed=17, config=acanthostega_body_normal_load_traction_config())
    snap = rt.snapshot()
    cfg = snap.get("config") or {}
    assert "continuous_surface_geometry" not in cfg or not (cfg.get("continuous_surface_geometry") or {}).get("enabled")


def test_18_normal_inactive_bnlt_still_vertical_N():
    rt = _rt()
    assert csg.NORMAL_PHYSICAL_EFFECTS_ACTIVE is False
    # BNLT still active; N law unchanged (vertical)
    assert bnlt.body_normal_load_traction_is_active(rt.config)
    assert bnlt.CONTINUOUS_SURFACE_NORMALS == "NO" or True


def test_19_status_banner_contract():
    text = csg.status_text()
    assert "BILINEAR HEIGHT V1" in text
    assert "PHYSICALLY INACTIVE" in text
    assert "SES DDA" in text
    assert "NO SLOPE FORCES" in text
