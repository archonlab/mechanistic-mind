"""MM-CURRENT-RUN-1 — Current Physical World run workspace (Planet-only)."""
from __future__ import annotations

from pathlib import Path

import pytest

from mechanistic_mind.ui.psychology_observer.legacy_mode import (
    logical_active_legacy_experiment,
)
from mechanistic_mind.ui.psychology_observer.planet_analyzer import (
    STRATUM_RAW,
    analyze_physical_world,
)
from mechanistic_mind.ui.psychology_observer.planet_session import PlanetInspectionSession
from mechanistic_mind.ui.psychology_observer.planet_setup import (
    CurrentPhysicalWorldSetup,
    FIXTURE_EDGE,
    FIXTURE_OFF,
    apply_current_setup,
)

APP = Path("mechanistic_mind/ui/psychology_observer/app.py").read_text()
COMP = Path("results/mm_current_run1_current_runtime_launcher/artifacts/current_runtime_composition.json")


def _hash(state) -> str:
    import hashlib
    import numpy as np
    h = hashlib.sha256()
    for arr in (state.T, state.M, state.vx, state.vy, state.u):
        h.update(np.ascontiguousarray(arr).tobytes())
    h.update(str(state.tick).encode())
    return h.hexdigest()


def test_composition_planet_only_frozen():
    import json
    c = json.loads(COMP.read_text())
    assert c["canonical_launch_target"] == "PLANET_ONLY_CURRENT_RUNTIME"
    assert c["start_current_mm_justified"] is False
    assert c["truthful_ui_name"] == "CURRENT PHYSICAL WORLD"


def test_session_is_planet_only():
    src = Path("mechanistic_mind/ui/psychology_observer/planet_session.py").read_text()
    assert "physical_body" not in src
    assert "internal_substrate" not in src
    assert "internal_medium" not in src
    assert "step_planet" in src


def test_app_defaults_physical_world_not_start_current_mm():
    assert 'view_mode_var = tk.StringVar(value="physical_world")' in APP
    assert "CURRENT PHYSICAL WORLD" in APP
    assert "Start Current MM" not in APP
    assert "current_pw_run_button" in APP
    assert "_bootstrap_current_physical_world" in APP
    assert "WAITING FOR PSYCHOLOGY TELEMETRY" not in Path(
        "mechanistic_mind/ui/psychology_observer/planet_view.py"
    ).read_text()


def test_ui_direct_runtime_equality():
    direct = PlanetInspectionSession(seed=17)
    apply_current_setup(direct, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_OFF))
    for _ in range(25):
        direct.step(1)
    ui = PlanetInspectionSession(seed=17)
    apply_current_setup(ui, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_OFF))
    for _ in range(25):
        ui.step(1)
    assert _hash(direct._state) == _hash(ui._state)


def test_boundary_fixture_edge():
    s = PlanetInspectionSession(seed=17)
    apply_current_setup(s, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_EDGE))
    assert s.display.boundary.enabled is True
    assert abs(float(s.display.boundary.K) - 0.16) < 1e-12


def test_analyzer_same_runtime():
    s = PlanetInspectionSession(seed=17)
    apply_current_setup(s, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_OFF))
    for _ in range(6):
        s.step(1)
    a = analyze_physical_world(s.display, history=s.history.as_list())
    b = analyze_physical_world(s.display, history=s.history.as_list())
    assert a.to_dict() == b.to_dict()
    assert a.to_dict()["stratum_counts"][STRATUM_RAW] >= 5


def test_legacy_toggle_noninterference():
    a = PlanetInspectionSession(seed=17)
    apply_current_setup(a, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_OFF))
    for _ in range(30):
        a.step(1)
    ha = _hash(a._state)
    b = PlanetInspectionSession(seed=17)
    apply_current_setup(b, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_OFF))
    for en in (True, False, True, False):
        assert (logical_active_legacy_experiment(enabled=en, selected_preset="4.76 Acquired Transition Reinstatement") is not None) == en
    for _ in range(30):
        b.step(1)
    assert _hash(b._state) == ha


def test_pause_does_not_require_psychology():
    assert "one physical system" in APP


def test_tk_startup_current_workspace():
    tk = pytest.importorskip("tkinter")
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("no display")
    root.withdraw()
    try:
        from mechanistic_mind.ui.psychology_observer.app import PsychologyObserverApp
        from mechanistic_mind.ui.psychology_observer.controller import (
            PsychologyObserverController,
            SubprocessRunner,
        )

        ctrl = PsychologyObserverController(
            mechanistic_mind_root=Path(".").resolve(),
            process_runner=SubprocessRunner(),
        )
        app = PsychologyObserverApp(root, ctrl)
        assert app.view_mode_var.get() == "physical_world"
        assert bool(app.legacy_mode_enabled.get()) is False
        assert app.legacy_mode_snapshot().logical_active_experiment is None
        app._bootstrap_current_physical_world()
        assert app.planet_session.display is not None
        assert app.planet_lifecycle_var.get() in {"READY", "PAUSED", "UNCONFIGURED"}
        # lifecycle
        app._planet_step()
        assert app.planet_session.display.tick == 1
        app._planet_run()
        assert app._planet_running is True
        app._planet_pause()
        assert app._planet_running is False
        t = app.planet_session.display.tick
        app._draw_map()  # repaint must not advance
        assert app.planet_session.display.tick == t
        app._planet_reset()
        assert app.planet_session.display.tick == 0
        # Analyzer on same session
        r = analyze_physical_world(app.planet_session.display, history=app.planet_session.history.as_list())
        assert "RAW_FACT" in r.summary_text
        # 4.76 still listed
        assert "4.76 Acquired Transition Reinstatement" in app.PROSPECTIVE_PRESETS
    finally:
        root.destroy()
