"""MM-CURRENT-RUN-1.1 — left panel persistence across view switches."""
from __future__ import annotations

from pathlib import Path

import pytest

APP = Path("mechanistic_mind/ui/psychology_observer/app.py").read_text()


def test_remount_helper_exists_and_no_forgotten_before():
    assert "_remount_left_workspace" in APP
    assert "_left_managed_widgets" in APP
    # The bug pattern must be gone
    assert 'before = getattr(self, "run_identity_header"' not in APP


def test_tk_view_switch_restores_current_setup():
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
        app._bootstrap_current_physical_world()
        session = app.planet_session
        sid = id(session)
        assert app.view_mode_var.get() == "physical_world"
        assert str(app.current_setup_frame.winfo_manager()) == "pack"

        # pause at nonzero tick
        app._planet_step()
        app._planet_step()
        tick = app.planet_session.display.tick
        assert tick == 2
        state_obj = app.planet_session._state

        def assert_pw_left():
            assert str(app.current_setup_header.winfo_manager()) == "pack"
            assert str(app.current_setup_frame.winfo_manager()) == "pack"
            assert str(app.legacy_mode_gate_frame.winfo_manager()) == ""

        def assert_org_left_legacy_off():
            assert str(app.legacy_mode_gate_frame.winfo_manager()) == "pack"
            assert str(app.current_setup_frame.winfo_manager()) == ""
            assert bool(app.legacy_mode_enabled.get()) is False
            assert app.legacy_mode_snapshot().logical_active_experiment is None

        assert_pw_left()

        # round trip
        app.view_mode_var.set("organism")
        app._view_mode_changed()
        assert_org_left_legacy_off()
        assert id(app.planet_session) == sid
        assert app.planet_session.display.tick == tick
        assert app.planet_session._state is state_obj

        app.view_mode_var.set("physical_world")
        app._view_mode_changed()
        assert_pw_left()
        assert id(app.planet_session) == sid
        assert app.planet_session.display.tick == tick
        assert app.planet_session._state is state_obj

        # reverse
        app.view_mode_var.set("organism")
        app._view_mode_changed()
        app.view_mode_var.set("physical_world")
        app._view_mode_changed()
        assert_pw_left()

        # 10 repeats
        for _ in range(10):
            app.view_mode_var.set("organism")
            app._view_mode_changed()
            assert_org_left_legacy_off()
            app.view_mode_var.set("physical_world")
            app._view_mode_changed()
            assert_pw_left()
        assert app.planet_session.display.tick == tick
        assert app.planet_session._state is state_obj

        # boundary fixture survives
        app.planet_boundary_fixture_var.set("edge_strip_k016_mext_020304")
        app.planet_fixture_var_display.set(
            "edge_strip_k016_mext_020304 — ON · edge strips · K=0.16 · M_ext=[0.2,0.3,0.4]"
        )
        app._apply_current_planet_setup()
        assert app.planet_session.display.boundary.enabled is True
        t2 = app.planet_session.display.tick
        for _ in range(3):
            app.view_mode_var.set("organism")
            app._view_mode_changed()
            app.view_mode_var.set("physical_world")
            app._view_mode_changed()
        assert app.planet_session.display.boundary.enabled is True
        assert app.planet_session.display.tick == t2
        assert_pw_left()

        # Analyzer still same session
        from mechanistic_mind.ui.psychology_observer.planet_analyzer import analyze_physical_world
        r = analyze_physical_world(app.planet_session.display, history=app.planet_session.history.as_list())
        assert "RAW_FACT" in r.summary_text
    finally:
        root.destroy()
