"""O6 Researcher Physical Optical Audit / Exposed Surface View V1 — focused tests (<=20 ticks)."""
from __future__ import annotations

import json
from pathlib import Path

from mechanistic_mind.model.acanthostega import acanthostega_beta4_config
from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system.experiment_canonical import public_model_selector_entries
from mechanistic_mind.physical_system.observer_camera_occupancy_consumer import (
    build_observer_volume_render_description,
)
from mechanistic_mind.physical_system.researcher_physical_optical_audit_view import (
    AUTHORITY,
    CAPABILITY,
    PROFILE,
    SCHEMA,
    build_o6_analyzer_summary,
    build_surface_display_payload,
    composite_false_color,
    derive_from_saved_evidence,
    invalidate_o6_display_cache,
    researcher_summary,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime

RESULTS = Path("results/acanthostega_researcher_physical_optical_audit_and_exposed_surface_view_v1")
RESULTS.mkdir(parents=True, exist_ok=True)

TICKS = 0


def _budget(n: int = 1) -> None:
    global TICKS
    TICKS += n
    assert TICKS <= 20


def test_01_identity_selector_tiktaalik():
    assert SCHEMA == "RESEARCHER_PHYSICAL_OPTICAL_AUDIT_VIEW_V1"
    assert CAPABILITY == "researcher_physical_optical_audit_view"
    assert PROFILE == "EXPOSED_SURFACE_AND_DIRECT_LIGHT_DISPLAY_O6_V1"
    assert AUTHORITY == "RESEARCHER_TRANSFORM_OVER_O2_O3_O3A_O4_O5_READ_ONLY"
    assert len(public_model_selector_entries()) == 2
    tik = tiktaalik_config()
    rt = PhysicalSystemRuntime(seed=1, config=tik)
    p = build_surface_display_payload(rt.world, rt.config)
    assert p["status"] == "UNAVAILABLE_NO_O2"


def test_02_surface_o2_o3_o3a_and_fewer_than_volume_faces():
    cfg = acanthostega_beta4_config()
    rt = PhysicalSystemRuntime(seed=9, config=cfg)
    rt.step()
    _budget(1)
    p = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    assert p["status"] in ("READY", "PARTIAL_NO_O4_TRACE", "PARTIAL_NO_O3A", "PARTIAL_NO_O5_TIMING")
    assert p["surface_uses_o2_exposed_facets"] is True
    assert p["internal_vw1_faces_rendered"] is False
    assert p["vw7_pixels_used_as_authority"] is False
    assert p["display_rgb_is_physical_authority"] is False
    assert p["facet_count"] > 0
    assert p["entity_sample_count"] > 0
    assert "TOP" in (p.get("counts_by_face") or {})
    # pit walls/floors: side+bottom classes present on flat world (exposed bottom of slab)
    faces = p.get("counts_by_face") or {}
    assert faces.get("BOTTOM", 0) > 0
    assert (faces.get("NORTH", 0) + faces.get("SOUTH", 0) + faces.get("EAST", 0) + faces.get("WEST", 0)) > 0
    vol = build_observer_volume_render_description(rt)
    vol_prisms = len(vol.get("occupancy_volumes") or [])
    vol_faces = vol_prisms * 6
    surface_prims = int(p["facet_count"]) + int(p["entity_sample_count"])
    assert surface_prims < vol_faces
    (RESULTS / "primitive_baseline.json").write_text(json.dumps({
        "volume_prisms": vol_prisms,
        "volume_faces": vol_faces,
        "surface_facets": p["facet_count"],
        "surface_entities": p["entity_sample_count"],
        "surface_prims": surface_prims,
    }, indent=2))


def test_03_display_transforms_and_cache():
    cfg = acanthostega_beta4_config()
    rt = PhysicalSystemRuntime(seed=11, config=cfg)
    rt.step()
    _budget(1)
    p1 = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    assert p1["performance"]["cache_hit"] is False
    p2 = build_surface_display_payload(rt.world, rt.config, runtime=rt)
    assert p2["performance"]["cache_hit"] is True
    rgb = composite_false_color([1, 1, 0, 0, 0, 0])
    assert rgb == [1.0, 0.0, 0.0]
    assert p1["composite_transform"]["physical_authority"] is False
    assert p1["hidden_display_ambient_alters_physical_light"] is False
    col = p1["facets_columnar"]
    assert col["encoding"] == "O6_COLUMNAR_FACETS_V1"
    assert col["n"] == p1["facet_count"]
    # causal states present
    assert "DIRECT_ILLUMINATED" in (p1.get("state_counts") or {}) or "BACK_FACING_ZERO" in (p1.get("state_counts") or {})


def test_04_organism_o4_o5_and_privacy():
    cfg = acanthostega_beta4_config()
    rt = PhysicalSystemRuntime(seed=13, config=cfg)
    for _ in range(2):
        rt.step()
    _budget(2)
    # Force an observation reception for O4
    obs = rt.agent_observation()
    summ = researcher_summary(rt.world, rt.config, runtime=rt)
    org = summ.get("organism_comparison") or {}
    # May be available after observation if O4 ran inside NFE
    assert org.get("researcher_camera_is_organism_eye") is False
    assert org.get("conscious_recognition_claimed") is False
    assert org.get("recomputed_from_camera") is False
    blob = json.dumps(obs)
    for tok in (SCHEMA, CAPABILITY, "facets_columnar", "SURFACE_LIGHT"):
        assert tok not in blob
    assert summ.get("feeds_cognition") is False


def test_05_restore_clears_cache_no_replay():
    cfg = acanthostega_beta4_config()
    rt = PhysicalSystemRuntime(seed=15, config=cfg)
    rt.step()
    _budget(1)
    build_surface_display_payload(rt.world, rt.config, runtime=rt)
    snap = rt.snapshot()
    rt2 = PhysicalSystemRuntime.restore(snap)
    # restore invalidates O6 derived cache
    assert getattr(rt2.world, "_o6_display_cache", None) in (None, {})
    p = build_surface_display_payload(rt2.world, rt2.config, runtime=rt2)
    assert p["performance"]["cache_hit"] is False
    invalidate_o6_display_cache(rt2.world)
    assert getattr(rt2.world, "_o6_display_cache", None) is None


def test_06_analyzer_and_legacy():
    exact = {"schema": SCHEMA, "display": {"facet_count": 3, "facets_columnar": {"n": 3}}}
    d = derive_from_saved_evidence(exact)
    assert d["legacy_policy"] == "CURRENT_O6_EXACT"
    leg = derive_from_saved_evidence({"old": True})
    assert leg["status"] == "LEGACY_EVIDENCE"
    s = build_o6_analyzer_summary(d)
    assert s["uses_rendered_pixels"] is False


def test_07_frontend_mode_bar_strings():
    pane = Path("web/psy-observer/src/chrome/WorldPane.tsx").read_text()
    assert "world-view-map" in pane and "world-view-volume" in pane and "world-view-surface" in pane
    assert "SURFACE / LIGHT" in pane
    assert "VOLUME / X-RAY" in pane
    assert "SurfaceLightView" in pane
    assert "'MAP' | 'VOLUME' | 'SURFACE'" in pane


def test_08_tick_budget():
    assert TICKS <= 20
