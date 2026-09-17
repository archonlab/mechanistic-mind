"""MM-CURRENT-RUN-1.2 — current runtime must not depend on legacy mode."""
from __future__ import annotations

from pathlib import Path

import pytest

from mechanistic_mind.ui.psychology_observer.cli import headless_contract
from mechanistic_mind.ui.psychology_observer.legacy_mode import (
    logical_active_legacy_experiment,
)
from mechanistic_mind.ui.psychology_observer.planet_setup import (
    CurrentPhysicalWorldSetup,
    FIXTURE_OFF,
    apply_current_setup,
)

APP = Path("mechanistic_mind/ui/psychology_observer/app.py").read_text()
OWN = Path(
    "results/mm_current_run1_2_current_legacy_runtime_separation/RUNTIME_OWNERSHIP.md"
).read_text()


def test_ownership_doc_freezes_planet_only():
    assert "PLANET_ONLY" in OWN
    assert "NO" in OWN and "organism runtime" in OWN.lower()


def test_headless_contract_flags():
    c = headless_contract()
    assert c["no_canonical_current_organism_runtime"] is False
    assert c["organism_view_is_legacy"] is True
    assert c["current_launch_depends_on_legacy_mode"] is False
    assert c["canonical_current_runtime"] == "PhysicalSystemRuntime"


def test_app_source_invariants():
    assert "PhysicalSystemRuntime: WORLD + BODY + INTERNAL" in APP
    assert "current_organism_null_frame" in APP
    assert "LEGACY EXPERIMENTS" in APP
    # Start Run still gated by legacy; Planet run is not
    assert "if not bool(self.legacy_mode_enabled.get()):" in APP
    assert "def _planet_run" in APP
    assert "Start Current MM" not in APP


def test_logical_legacy_independent_of_planet():
    assert (
        logical_active_legacy_experiment(
            enabled=False, selected_preset="4.76 Acquired Transition Reinstatement"
        )
        is None
    )


def test_tk_legacy_off_planet_works_organism_is_null():
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
        assert app.view_mode_var.get() == "physical_world"
        app._bootstrap_current_physical_world()
        # Current Physical World independent of legacy
        assert str(app.current_setup_frame.winfo_manager()) == "pack"
        app._planet_step()
        assert app.planet_session.display.tick == 1
        assert app.legacy_mode_snapshot().logical_active_experiment is None

        # Organism + legacy OFF → honesty null, no Start, no experiment active
        app.view_mode_var.set("organism")
        app._view_mode_changed()
        assert str(app.current_organism_null_frame.winfo_manager()) == "pack"
        assert str(app.legacy_setup_frame.winfo_manager()) == ""
        assert str(app.current_setup_frame.winfo_manager()) == ""
        assert app.legacy_mode_snapshot().start_run_available is False
        assert "HISTORICAL ORGANISM" in app.world_badge_var.get()

        # Enable legacy → historical setup, still not Planet
        app.legacy_mode_enabled.set(True)
        app._on_legacy_mode_toggled()
        assert str(app.legacy_setup_frame.winfo_manager()) == "pack"
        assert str(app.current_organism_null_frame.winfo_manager()) == ""
        app.prospective_preset_var.set("4.76 Acquired Transition Reinstatement")
        app._refresh_buttons()
        assert app.legacy_mode_snapshot().logical_active_experiment is not None
        assert app.legacy_mode_snapshot().start_run_available is True

        # Back to physical_world with legacy still ON: Planet launcher visible, not Start Run chrome
        app.view_mode_var.set("physical_world")
        app._view_mode_changed()
        assert str(app.current_setup_frame.winfo_manager()) == "pack"
        assert str(app.legacy_setup_frame.winfo_manager()) == ""
        # Planet still same session
        assert app.planet_session.display.tick == 1
    finally:
        root.destroy()
