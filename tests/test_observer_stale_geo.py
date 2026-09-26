"""Stale GEO / cache invalidation / LIVE vs SAVED provenance (Observer-only).

Does not change terrain/ambient physics or cognition — verifies display binding only.
"""
from __future__ import annotations

from mechanistic_mind.physical_system.ecology_presets import (
    ECOLOGY_STRUCTURED_TERRAIN,
    ECOLOGY_STRUCTURED_WORLD,
)
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig


def _exp(seed: int = 17, ecology: str | None = None, **extra):
    payload = {
        "seed": seed,
        "agent_count": 1,
        "cognition_enabled": False,
        "speed": 50.0,
        "ui_hz": 8.0,
        "world": {"width": 32, "height": 32, "boundary_mode": "WRAP_PERIODIC"},
        **extra,
    }
    if ecology is not None:
        payload["ecology_preset"] = ecology
    return payload


def _trav(frame: dict) -> dict:
    gi = frame.get("geometry_interpretation") or {}
    return gi.get("traversability") or {}


def _transport(frame: dict) -> dict:
    return frame.get("geo_transport") or (_trav(frame).get("provenance") and (frame.get("geometry_interpretation") or {}).get("geo_transport")) or {}


def _grid_is_empty(grid) -> bool:
    if grid is None:
        return True
    if grid == [] or grid == {}:
        return True
    if isinstance(grid, list) and all(
        (not row) or (isinstance(row, list) and all(int(v or 0) == 0 for v in row))
        for row in grid
    ):
        return True
    return False


def test_live_geo_unavailable_without_samples_no_class_grid():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    frame = sess.apply_experiment(_exp())
    trav = _trav(frame)
    transport = frame.get("geo_transport") or {}
    assert transport.get("geo_source") == "LIVE" or trav.get("geo_source") == "LIVE"
    assert trav.get("status") == "LIVE_GEO_UNAVAILABLE"
    assert _grid_is_empty(trav.get("class_grid"))
    assert int(trav.get("n_observations") or 0) == 0
    note = str(trav.get("note") or "")
    assert "LIVE GEO unavailable" in note or "Not falling back" in note


def test_apply_reset_clears_saved_geo_and_bumps_static_version():
    sess = ObserverSession(config=SessionConfig(seed=17, speed=50, ui_hz=8, buffer_capacity=64))
    frame0 = sess.apply_experiment(_exp(seed=17))
    v0 = int((frame0.get("geo_transport") or {}).get("static_version") or 0)

    fake_grid = [[1, 2], [3, 4]]
    with sess._step_lock:
        sess._geo_saved_overlay = {
            "status": "AVAILABLE",
            "geo_source": "SAVED",
            "n_observations": 99,
            "class_grid": fake_grid,
            "empirical_version": 99,
        }
        sess._geo_saved_provenance = {
            "geo_source": "SAVED",
            "run_id": "fake-old-run",
            "experiment_seed": 999,
            "terrain_checksum": "deadbeef",
        }
        sess._geo_overlay_source = "SAVED"
        sess._geo_static_version = v0

    # Synchronous capture while SAVED is selected must show SAVED, not invent LIVE grids.
    with sess._step_lock:
        saved_frame = sess._capture_locked(detail="full")
    assert (_trav(saved_frame).get("geo_source") == "SAVED")
    assert (_trav(saved_frame).get("n_observations") == 99)
    assert (_trav(saved_frame).get("class_grid") == fake_grid)
    assert (_trav(saved_frame).get("provenance") or {}).get("run_id") == "fake-old-run"

    # Apply & reset must invalidate SAVED and return to LIVE-only unavailable.
    frame1 = sess.apply_experiment(_exp(seed=17))
    trav1 = _trav(frame1)
    tr1 = frame1.get("geo_transport") or {}
    assert sess._geo_overlay_source == "LIVE"
    assert sess._geo_saved_overlay is None
    assert trav1.get("geo_source") == "LIVE"
    assert trav1.get("status") == "LIVE_GEO_UNAVAILABLE"
    assert _grid_is_empty(trav1.get("class_grid"))
    assert int(tr1.get("static_version") or 0) > v0
    prov = trav1.get("provenance") or tr1.get("provenance") or {}
    assert prov.get("experiment_seed") == 17
    assert "runtime_generation" in prov


def test_geometry_clear_saved_and_use_live():
    sess = ObserverSession(config=SessionConfig(seed=3, speed=50, ui_hz=8, buffer_capacity=32))
    sess.apply_experiment(_exp(seed=3))
    with sess._step_lock:
        sess._geo_saved_overlay = {
            "status": "AVAILABLE",
            "geo_source": "SAVED",
            "n_observations": 5,
            "class_grid": [[0]],
            "empirical_version": 5,
        }
        sess._geo_saved_provenance = {"geo_source": "SAVED", "run_id": "r1"}
        sess._geo_overlay_source = "SAVED"
    cleared = sess.geometry_clear_saved()
    assert cleared.get("accepted") is True
    assert cleared.get("geo_source") == "LIVE"
    assert sess._geo_saved_overlay is None
    assert sess._geo_overlay_source == "LIVE"
    live = sess.geometry_use_live()
    assert live.get("geo_source") == "LIVE"


def test_live_provenance_includes_terrain_and_ambient_checksums():
    sess = ObserverSession(config=SessionConfig(seed=0, speed=50, ui_hz=8, buffer_capacity=32))
    frame = sess.apply_experiment(_exp(seed=42, ecology=ECOLOGY_STRUCTURED_WORLD))
    trav = _trav(frame)
    tr = frame.get("geo_transport") or {}
    prov = trav.get("provenance") or tr.get("provenance") or {}
    gt = (frame.get("experiment") or {}).get("observer_ground_truth") or {}
    terr_cs = (gt.get("terrain") or {}).get("checksum")
    amb_cs = (gt.get("ambient") or {}).get("checksum")
    assert terr_cs
    assert amb_cs
    assert prov.get("terrain_checksum") == terr_cs
    assert prov.get("ambient_checksum") == amb_cs
    assert prov.get("experiment_seed") == 42
    assert tr.get("terrain_checksum") == terr_cs
    # WORLD can verify displayed GT vs runtime checksum
    assert sess.runtime.world.terrain_meta["checksum"] == terr_cs


def test_preset_switch_invalidates_geo_and_changes_ambient():
    sess = ObserverSession(config=SessionConfig(seed=0, speed=50, ui_hz=8, buffer_capacity=32))
    f_terr = sess.apply_experiment(_exp(seed=11, ecology=ECOLOGY_STRUCTURED_TERRAIN))
    cs_t = ((f_terr.get("experiment") or {}).get("observer_ground_truth") or {}).get("terrain", {}).get("checksum")
    with sess._step_lock:
        sess._geo_saved_overlay = {"status": "AVAILABLE", "n_observations": 1, "class_grid": [[9]]}
        sess._geo_overlay_source = "SAVED"
    f_world = sess.apply_experiment(_exp(seed=11, ecology=ECOLOGY_STRUCTURED_WORLD))
    assert sess._geo_overlay_source == "LIVE"
    assert sess._geo_saved_overlay is None
    assert _trav(f_world).get("status") == "LIVE_GEO_UNAVAILABLE"
    assert _grid_is_empty(_trav(f_world).get("class_grid"))
    gt = (f_world.get("experiment") or {}).get("observer_ground_truth") or {}
    assert (gt.get("ambient") or {}).get("enabled") is True
    # Same seed structured terrain→world: terrain may share seed family; ambient newly on.
    assert (gt.get("terrain") or {}).get("checksum")
    assert cs_t  # prior existed


def test_same_seed_structured_world_reset_reproduces_terrain_checksum():
    sess = ObserverSession(config=SessionConfig(seed=0, speed=50, ui_hz=8, buffer_capacity=32))
    f1 = sess.apply_experiment(_exp(seed=77, ecology=ECOLOGY_STRUCTURED_WORLD))
    cs1 = ((f1.get("experiment") or {}).get("observer_ground_truth") or {}).get("terrain", {}).get("checksum")
    amb1 = ((f1.get("experiment") or {}).get("observer_ground_truth") or {}).get("ambient", {}).get("checksum")
    f2 = sess.apply_experiment(_exp(seed=77, ecology=ECOLOGY_STRUCTURED_WORLD))
    cs2 = ((f2.get("experiment") or {}).get("observer_ground_truth") or {}).get("terrain", {}).get("checksum")
    amb2 = ((f2.get("experiment") or {}).get("observer_ground_truth") or {}).get("ambient", {}).get("checksum")
    assert cs1 and cs1 == cs2
    assert amb1 and amb1 == amb2
    prov = _trav(f2).get("provenance") or (f2.get("geo_transport") or {}).get("provenance") or {}
    assert prov.get("terrain_checksum") == cs2


def test_seed_change_changes_terrain_checksum_and_live_provenance():
    sess = ObserverSession(config=SessionConfig(seed=0, speed=50, ui_hz=8, buffer_capacity=32))
    f_a = sess.apply_experiment(_exp(seed=101, ecology=ECOLOGY_STRUCTURED_WORLD))
    f_b = sess.apply_experiment(_exp(seed=202, ecology=ECOLOGY_STRUCTURED_WORLD))
    cs_a = ((f_a.get("experiment") or {}).get("observer_ground_truth") or {}).get("terrain", {}).get("checksum")
    cs_b = ((f_b.get("experiment") or {}).get("observer_ground_truth") or {}).get("terrain", {}).get("checksum")
    assert cs_a and cs_b and cs_a != cs_b
    prov_b = _trav(f_b).get("provenance") or (f_b.get("geo_transport") or {}).get("provenance") or {}
    assert prov_b.get("experiment_seed") == 202
    assert prov_b.get("terrain_checksum") == cs_b


def test_publish_live_never_returns_saved_grids():
    sess = ObserverSession(config=SessionConfig(seed=5, speed=50, ui_hz=8, buffer_capacity=32))
    sess.apply_experiment(_exp(seed=5))
    with sess._step_lock:
        sess._geo_saved_overlay = {
            "status": "AVAILABLE",
            "n_observations": 50,
            "class_grid": [[7, 7], [7, 7]],
            "empirical_version": 50,
        }
        sess._geo_saved_provenance = {"run_id": "should-not-leak"}
        sess._geo_overlay_source = "LIVE"
        sess._geo_overlay_published = None
    overlay, transport = sess._publish_geo_overlay_outside_lock(detail="full")
    assert transport.get("geo_source") == "LIVE"
    assert overlay is not None
    assert overlay.get("geo_source") == "LIVE"
    assert overlay.get("status") == "LIVE_GEO_UNAVAILABLE"
    assert _grid_is_empty(overlay.get("class_grid")) or int(overlay.get("n_observations") or 0) == 0
    assert (overlay.get("provenance") or {}).get("run_id") != "should-not-leak"


def test_ui_exposes_load_saved_geo_not_hardcoded_run():
    from pathlib import Path

    app = Path(__file__).resolve().parents[1] / "web" / "psy-observer" / "src" / "App.tsx"
    text = app.read_text(encoding="utf-8")
    assert "LOAD SAVED GEO" in text
    assert "Use LIVE GEO" in text
    assert "LIVE GEO unavailable" in text
    assert "psyweb-20260918T021911" not in text
    assert "geometryUseLive" in text
    assert "geometryClearSaved" in text
