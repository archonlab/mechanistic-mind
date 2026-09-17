from pathlib import Path

from mechanistic_mind.ui.psychology_observer.planet_session import PlanetInspectionSession
from mechanistic_mind.ui.psychology_observer.planet_setup import (
    CurrentPhysicalWorldSetup,
    apply_current_setup,
)


APP = Path("mechanistic_mind/ui/psychology_observer/app.py").read_text()


def test_current_adapter_resolves_one_runtime_and_one_agent():
    session = PlanetInspectionSession(seed=17)
    apply_current_setup(session, CurrentPhysicalWorldSetup())
    runtime = session.runtime
    assert runtime is not None
    assert session._state is runtime.world
    world, body, internal = runtime.world, runtime.body, runtime.internal
    position = (body.x, body.y)
    runtime_id = id(runtime)
    session.step()
    assert id(session.runtime) == runtime_id
    assert session._state is world
    assert runtime.body is body and runtime.internal is internal
    assert runtime.tick == world.tick == body.tick == internal.tick == 1
    assert position == (8.5, 16.5)
    assert body.cells(32, 32, runtime.config.body.footprint)


def test_user_modes_and_current_lifecycle_are_explicit():
    assert 'values=("Current MM", "Legacy Experiments")' in APP
    assert 'value="Current MM"' in APP
    assert "return self.planet_session.runtime" in APP
    assert "self.planet_session.step(1)" in APP
    assert "CURRENT AGENT (RAW PHYSICAL FACTS)" in APP
    assert "runtime.body" in APP and "runtime.internal" in APP
    assert "import numpy as np" in APP
    assert "TICK  {runtime.tick:,}" in APP
    assert "CURRENT AGENT" in APP
    assert '"Planet run"' not in APP


def test_obsolete_current_claims_removed():
    assert "Canonical runtime: Planet only" not in APP
    assert "BODY/INTERNAL not composed here" not in APP
    assert "NO CANONICAL CURRENT ORGANISM RUNTIME" not in APP


def test_view_mapping_has_no_simulation_mutation():
    start = APP.index("def _mode_selector_changed")
    end = APP.index("def legacy_mode_snapshot", start)
    source = APP[start:end]
    assert ".step(" not in source
    assert ".reset(" not in source
    assert "PhysicalSystemRuntime(" not in source


def test_legacy_not_required_by_current_controls():
    assert '"current_launch_depends_on_legacy_mode": False' in APP
    assert "if not bool(self.legacy_mode_enabled.get()):" in APP  # legacy Start guard only
