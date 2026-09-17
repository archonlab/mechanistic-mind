from pathlib import Path
from types import SimpleNamespace
import tkinter as tk

import pytest

from mechanistic_mind.ui.psychology_observer.app import PsychologyObserverApp
from mechanistic_mind.ui.psychology_observer.controller import (
    MEMORY_ARCHITECTURES,
    OBSTACLE_CONDITIONS,
    PERSISTENT_CONDITIONS,
    RESOURCE_LAYOUTS,
    WORLD_MODES,
)


class _Controller:
    def __init__(self):
        self.started = None
        self.launch_id = "test-run"
        self.run_dir = Path("results/test-run")
        self.state = "IDLE"
        self.error = None
        self.projector = SimpleNamespace(available_agent_ids=("A001",), selected_agent_id="A001")
        self.view = SimpleNamespace(ticks=[], latest=None, source_run_id=None)
        self.psychology_jsonl = None

    @property
    def is_active(self):
        return False

    def start(self, spec):
        self.started = spec

    def stop(self):
        pass

    def poll_telemetry(self):
        pass


@pytest.fixture
def compact_app():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display unavailable")
    root.withdraw()
    controller = _Controller()
    app = PsychologyObserverApp(root, controller)
    root.update_idletasks()
    yield root, app, controller
    root.destroy()


def test_discrete_choices_are_preserved_and_not_duplicated(compact_app):
    _root, app, _controller = compact_app
    assert tuple(app.world_combo.cget("values")) == WORLD_MODES
    assert tuple(app.memory_architecture_combo.cget("values")) == MEMORY_ARCHITECTURES
    assert tuple(app.obstacle_combo.cget("values")) == OBSTACLE_CONDITIONS
    assert tuple(app.persistent_combo.cget("values")) == PERSISTENT_CONDITIONS
    assert tuple(app.layout_combo.cget("values")) == RESOURCE_LAYOUTS
    assert tuple(app.prospective_preset_combo.cget("values")) == app.PROSPECTIVE_PRESETS
    assert app.prospective_preset_combo.winfo_parent() != app.prospective_settings_panel.winfo_parent()


def test_groups_remove_layout_height_without_losing_values(compact_app):
    root, app, _controller = compact_app
    app.ticks_var.set(777)
    app.seed_var.set(42)
    app.world_var.set("organism")
    app.layout_var.set("far")
    simulation = app._run_setup_groups["SIMULATION"]
    before = app.run_setup_form.winfo_reqheight()
    app._toggle_run_setup_group("SIMULATION")
    root.update_idletasks()
    assert simulation["body"].winfo_manager() == ""
    assert app.run_setup_form.winfo_reqheight() < before
    app._toggle_run_setup_group("SIMULATION")
    root.update_idletasks()
    assert simulation["body"].winfo_manager() == "pack"
    assert (app.ticks_var.get(), app.seed_var.get(), app.layout_var.get()) == (777, 42, "far")


def test_scoped_scroll_preset_reset_and_start_spec(compact_app):
    root, app, controller = compact_app
    app._toggle_run_setup_group("COGNITION")
    app.run_setup_viewport.configure(height=170)
    root.update_idletasks()
    app._update_run_setup_scrollregion()
    app._run_setup_mousewheel(SimpleNamespace(num=None, delta=-120))
    assert app.run_setup_canvas.yview()[0] >= 0.0

    app.prospective_preset_var.set("4.17 Persistent Expectation × Fresh Prediction Conflict")
    app._apply_prospective_preset()
    assert app.run_setup_canvas.yview()[0] == 0.0
    assert (app.ticks_var.get(), app.seed_var.get()) == (120, 17)

    app.ticks_var.set(321)
    app.seed_var.set(23)
    app.world_var.set("organism")
    app.layout_var.set("near")
    app.random_rate_var.set(0.02)
    app.memory_architecture_var.set("BOUNDED_RAW")
    app.start()
    spec = controller.started
    assert (spec.ticks, spec.seed, spec.world) == (321, 23, "organism")
    assert (spec.resource_layout, spec.random_event_rate) == ("near", 0.02)
    assert spec.memory_architecture == "BOUNDED_RAW"
    assert spec.experiment_preset == "4.17 Persistent Expectation × Fresh Prediction Conflict"
    # Primary actions are siblings of the viewport, not children of its canvas.
    assert app.start_button.winfo_toplevel() is root
    assert app.start_button.winfo_parent() != str(app.run_setup_canvas)
