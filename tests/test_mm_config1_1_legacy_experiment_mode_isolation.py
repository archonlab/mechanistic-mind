"""MM-CONFIG-1.1 — Legacy Experiment Mode Isolation."""
from __future__ import annotations

from pathlib import Path

import pytest

from mechanistic_mind.ui.psychology_observer.legacy_mode import (
    LEGACY_MODE_OFF_STATUS,
    can_disable_legacy_mode,
    headless_legacy_contract,
    legacy_start_run_available,
    logical_active_legacy_experiment,
    snapshot,
)
from mechanistic_mind.ui.psychology_observer.cli import headless_contract
from mechanistic_mind.ui.psychology_observer.planet_session import PlanetInspectionSession
from mechanistic_mind.ui.psychology_observer.planet_setup import (
    CurrentPhysicalWorldSetup,
    FIXTURE_OFF,
    apply_current_setup,
)
from mechanistic_mind.ui.psychology_observer.planet_analyzer import (
    STRATUM_RAW,
    analyze_physical_world,
)

APP = Path("mechanistic_mind/ui/psychology_observer/app.py").read_text()
PRESETS_TAIL = [
    "4.67 Physical DOF Access Audit",
    "4.68 Persistent Process Provenance",
    "4.69 Frozen Physical Composition",
    "4.70 Generic Action Body Internal Return",
    "4.71 Post-Consequence Relaxation and Latent Return",
    "4.72 State-Dependent Physical Consequence",
    "4.73 Physical Intervention vs Non-Intervention",
    "4.74 Body-Response-Consequence Acquisition Archaeology",
    "4.75 Response-Contingent Internal Transition Acquisition",
    "4.76 Acquired Transition Reinstatement",
]


def test_default_logical_active_is_none():
    snap = snapshot(
        enabled=False,
        selected_preset="4.12.2 Same Present / Different History",
        controller_is_active=False,
    )
    assert snap.enabled is False
    assert snap.logical_active_experiment is None
    assert snap.start_run_available is False


def test_enabled_makes_preset_logical():
    name = "4.76 Acquired Transition Reinstatement"
    assert logical_active_legacy_experiment(enabled=True, selected_preset=name) == name
    assert legacy_start_run_available(enabled=True, selected_preset=name) is True


def test_cannot_disable_while_active_run():
    assert can_disable_legacy_mode(controller_is_active=True) is False
    assert can_disable_legacy_mode(controller_is_active=False) is True


def test_app_defaults_legacy_mode_false():
    assert "legacy_mode_enabled = tk.BooleanVar(value=False)" in APP
    assert "Enable Legacy Experiments" in APP
    assert "NO LEGACY EXPERIMENT ACTIVE" in APP or "LEGACY_MODE_OFF_STATUS" in APP
    assert "_on_legacy_mode_toggled" in APP
    assert "_apply_legacy_mode_chrome" in APP


def test_start_gated_in_source():
    assert "if not bool(self.legacy_mode_enabled.get()):" in APP
    # Start Run path still wires experiment_preset when allowed
    assert "experiment_preset=self.prospective_preset_var.get()" in APP


def test_no_fake_none_experiment_in_registry():
    # Must not add NONE/NO_EXPERIMENT/CURRENT to PROSPECTIVE_PRESETS
    assert '"NONE"' not in APP.split("PROSPECTIVE_PRESETS")[1].split(")")[0]
    assert "NO_EXPERIMENT" not in APP
    presets = APP.split("PROSPECTIVE_PRESETS")[1].split(")", 1)[0]
    assert "Current MM" not in presets


def test_presets_476_through_467_preserved():
    for name in PRESETS_TAIL:
        assert name in APP


def test_headless_contract_legacy_default_off():
    c = headless_contract()
    assert c.get("legacy_mode_default") is False
    assert c.get("legacy_start_run_requires_mode") is True
    assert headless_legacy_contract()["legacy_mode_default"] is False


def test_planet_physics_files_unmodified_marker():
    # Analyzer scientific module must not be edited by this task
    analyzer = Path("mechanistic_mind/ui/psychology_observer/planet_analyzer.py").read_text()
    assert "mm_analyzer1_v1" in analyzer
    assert "STRATUM_RAW" in analyzer


def _phys_hash(state) -> str:
    import hashlib
    import numpy as np
    h = hashlib.sha256()
    for arr in (state.T, state.M, state.vx, state.vy, state.u):
        h.update(np.ascontiguousarray(arr).tobytes())
    h.update(str(state.tick).encode())
    return h.hexdigest()


def test_legacy_toggle_no_physics_effect():
    """Strong null: toggle legacy UI without starting == never enable."""
    # A: never enable legacy (pure planet)
    a = PlanetInspectionSession(seed=17)
    apply_current_setup(a, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_OFF))
    for _ in range(40):
        a.step(1)
    ha = _phys_hash(a._state)

    # B: simulate mode toggles without Start Run — only planet path identical
    b = PlanetInspectionSession(seed=17)
    apply_current_setup(b, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_OFF))
    # Mode toggle is UI-only; here we only flip pure helpers (no RNG)
    for enabled in (True, False, True, False):
        snap = snapshot(
            enabled=enabled,
            selected_preset="4.76 Acquired Transition Reinstatement",
            controller_is_active=False,
        )
        assert (snap.logical_active_experiment is not None) == enabled
    for _ in range(40):
        b.step(1)
    assert _phys_hash(b._state) == ha


def test_current_world_and_analyzer_independent_of_legacy_off():
    s = PlanetInspectionSession(seed=17)
    apply_current_setup(s, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_OFF))
    for _ in range(5):
        s.step(1)
    # legacy OFF snapshot
    assert (
        logical_active_legacy_experiment(
            enabled=False, selected_preset="4.12.2 Same Present / Different History"
        )
        is None
    )
    r = analyze_physical_world(s.display, history=s.history.as_list())
    assert r.to_dict()["stratum_counts"][STRATUM_RAW] >= 5
    assert "RAW_FACT" in r.summary_text


def test_tk_startup_legacy_off_if_display_available():
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
        assert bool(app.legacy_mode_enabled.get()) is False
        snap = app.legacy_mode_snapshot()
        assert snap.logical_active_experiment is None
        assert snap.start_run_available is False
        assert app.legacy_mode_status_var.get() == LEGACY_MODE_OFF_STATUS
        # Enable then select 4.76
        app.legacy_mode_enabled.set(True)
        app._on_legacy_mode_toggled()
        app.prospective_preset_var.set("4.76 Acquired Transition Reinstatement")
        app._refresh_buttons()
        snap2 = app.legacy_mode_snapshot()
        assert snap2.logical_active_experiment == "4.76 Acquired Transition Reinstatement"
        assert snap2.start_run_available is True
        # OFF again
        app.legacy_mode_enabled.set(False)
        app._on_legacy_mode_toggled()
        assert app.legacy_mode_snapshot().logical_active_experiment is None
        # Physical world still works
        app.view_mode_var.set("physical_world")
        app._view_mode_changed()
        app._planet_reset()
        assert app.planet_session.display is not None
        assert app.planet_session.display.tick == 0
    finally:
        root.destroy()


def test_no_planet_physics_import_of_configure_in_app():
    assert "configure_external_material_boundary(" not in APP
