"""Regression: every EXPERIMENTER_CONFIGURABLE mechanism has UI or allowlisted reason."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_control_coverage_inventory_or_generate():
    inv_path = ROOT / "results" / "mechanism_control_ui" / "control_coverage.json"
    if not inv_path.exists():
        # Generate on demand so CI without prior artifact still checks.
        from experiments.run_mechanism_control_ui import main as gen
        assert gen() in (0, 1)
    data = json.loads(inv_path.read_text())
    assert data.get("gaps") == [], f"Missing UI controls for: {data.get('gaps')}"
    assert data.get("n_covered", 0) >= 1


def test_vision_radius_live_syncs_configured_and_runtime():
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    s = ObserverSession(SessionConfig(seed=17))
    out = s.set_vision_radius(2)
    integ = out.get("mechanism_integrity") or s.mechanism_integrity_status()
    rows = (integ.get("preflight") or {}).get("rows") or integ.get("rows") or []
    vision = next(r for r in rows if r["mechanism"] == "physical_near_field_vision")
    assert vision["configured_radius"] == 2
    assert vision["runtime_radius"] == 2
    assert vision["status"] == "READY"
    assert integ.get("ready") is True


def test_frontend_vision_control_sources_exist():
    """Fail if VisionExperimenterControl or R1/R2/R3 wiring is removed."""
    app = (ROOT / "web" / "psy-observer" / "src" / "App.tsx").read_text()
    ctrl = (ROOT / "web" / "psy-observer" / "src" / "components" / "VisionExperimenterControl.tsx").read_text()
    assert "VisionExperimenterControl" in app
    assert "onSetRadius={setVisionRadius}" in app or "onSetRadius={setVisionRadius}" in app
    assert "R1" in ctrl and "R2" in ctrl and "R3" in ctrl
    assert "Configured" in ctrl and "Runtime" in ctrl
    # Coverage allowlist file must mention vision
    assert "setVisionRadius" in app


def test_live_ecology_does_not_leave_climate_mismatch():
    from mechanistic_mind.physical_system.ecology_presets import ECOLOGY_BASELINE
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    s = ObserverSession(SessionConfig(seed=17))
    out = s.apply_live_intervention({"ecology_preset": ECOLOGY_BASELINE})
    integ = out.get("mechanism_integrity") or s.mechanism_integrity_status()
    rows = (integ.get("preflight") or {}).get("rows") or integ.get("rows") or []
    clim = next(r for r in rows if r["mechanism"] == "spatiotemporal_climate_ecology")
    assert clim["configured"] is False
    assert clim["runtime"] is False
    assert clim["status"] == "READY"
    assert integ.get("ready") is True
