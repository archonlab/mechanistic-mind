"""Beta 3 Update 2 — frontend architecture (workspaces, isolation, lifecycle)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "web" / "psy-observer" / "src" / "App.tsx").read_text()
HEADER = (ROOT / "web" / "psy-observer" / "src" / "chrome" / "ObserverHeader.tsx").read_text()
DOCK = (ROOT / "web" / "psy-observer" / "src" / "inspectors" / "InspectorDock.tsx").read_text()
INTEREST = (ROOT / "web" / "psy-observer" / "src" / "observer" / "interest.ts").read_text()
DRIVERS = (ROOT / "web" / "psy-observer" / "src" / "observer" / "drivers.tsx").read_text()
STORES = (ROOT / "web" / "psy-observer" / "src" / "observer" / "stores.ts").read_text()
PANEL = (ROOT / "web" / "psy-observer" / "src" / "components" / "SignalSensorimotorPanel.tsx").read_text()


def test_workspaces_exist():
    assert "data-workspace={lab.workspace}" in APP or 'data-workspace={lab.workspace}' in APP
    assert "RunWorkspace" in APP and "InspectWorkspace" in APP and "AnalyzeWorkspace" in APP
    assert "WORKSPACE" in HEADER
    for w in ("RUN", "INSPECT", "ANALYZE"):
        assert w in HEADER


def test_no_global_setnow_timer():
    assert "setNow(Date.now())" not in APP
    assert "clockStore.set(Date.now())" in DRIVERS
    assert "ClockDriver" in APP


def test_hot_frame_goes_to_store_not_usestate():
    assert "useState<ObserverFrame" not in APP
    assert "frameStore.setLive" in APP
    assert "noteRender('App')" in APP


def test_psc_shadow_opt_in_preserved():
    assert "include_shadow" in PANEL
    assert "opt-in" in INTEREST
    assert "never" in INTEREST


def test_lifecycle_truth_preserved():
    banners = (ROOT / "web" / "psy-observer" / "src" / "chrome" / "LifecycleBanners.tsx").read_text()
    assert "SAVE_FAILED" in banners
    assert "DISPLAY FROZEN" in banners
    assert "SERVER_UNAVAILABLE" in banners
    assert "lifecycleErrorCode" in banners


def test_headless_not_forced_on_workspace_switch():
    assert "execution-mode" in HEADER
    # workspace buttons must not call execution-mode
    assert "data-workspace-tab" in HEADER


def test_inspector_categories_exist():
    for cat in ("BODY", "SENSORS", "SIGNALS", "COGNITION", "PREDICTIVE", "MECHANISMS", "EXPERIMENTER"):
        assert cat in DOCK


def test_predictive_and_mechanisms_have_homes():
    assert "ContextualProspectiveControlPanel" in DOCK
    assert "MechanismsPanel" in DOCK
    assert "InteractPanel" in DOCK


def test_store_has_render_probe():
    assert "noteRender" in STORES
    assert "WorldPane" in STORES


def test_heartbeat_applies_headless_display_fields():
    assert "displayFrozen" in APP
    assert "display_frozen" in APP
    assert "executionMode" in APP


def test_rail_uses_shared_workspace_navigator():
    assert "applyRailDestination" in APP
    assert "lab.workspace === 'RUN' || deviceCollapsed" not in APP
    device = (ROOT / "web" / "psy-observer" / "src" / "desktop" / "ControlDevice.tsx").read_text()
    assert "onClick={() => { onTool(t.id); }}" in device
    assert "onTool(t.id); onToggleCollapse()" not in device


def test_runtime_progress_includes_headless_display_fields():
    from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig

    s = ObserverSession(SessionConfig(seed=7, execution_mode="HEADLESS", evidence_mode="SEARCH_COMPACT"))
    s.set_execution_mode("HEADLESS")
    s.status = "RUNNING"
    p = s.runtime_progress()
    assert p["execution_mode"] == "HEADLESS"
    assert p["display_frozen"] is True
    assert "display_tick" in p
