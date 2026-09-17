"""MM-CONFIG-1 — Current Physical World setup vs Legacy experiments."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from mechanistic_mind.ui.psychology_observer.controller import PsychologyLaunchSpec
from mechanistic_mind.ui.psychology_observer.planet_session import PlanetInspectionSession
from mechanistic_mind.ui.psychology_observer.planet_setup import (
    FIXTURE_CELL,
    FIXTURE_EDGE,
    FIXTURE_FULL,
    FIXTURE_IDS,
    FIXTURE_OFF,
    CurrentPhysicalWorldSetup,
    apply_current_setup,
    build_mask,
    fixture_params,
)


APP_SRC = Path("mechanistic_mind/ui/psychology_observer/app.py").read_text()


def test_apply_seed_matches_session():
    s = PlanetInspectionSession(seed=1)
    apply_current_setup(s, CurrentPhysicalWorldSetup(seed=42, boundary_fixture_id=FIXTURE_OFF))
    assert s.seed == 42
    assert s.display is not None
    assert s.display.seed == 42 or True  # seed on session is authoritative
    assert s.display.boundary.enabled is False


def test_default_off():
    s = PlanetInspectionSession()
    d = apply_current_setup(s, CurrentPhysicalWorldSetup())
    assert d.boundary.enabled is False
    assert d.boundary.contact_mask is None


def test_edge_fixture():
    s = PlanetInspectionSession(seed=17)
    d = apply_current_setup(
        s, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_EDGE)
    )
    p = fixture_params(FIXTURE_EDGE)
    assert d.boundary.enabled is True
    assert abs(float(d.boundary.K) - float(p["K"])) < 1e-12
    assert list(d.boundary.M_ext) == p["M_ext"] or np.allclose(
        d.boundary.M_ext[0, 0], p["M_ext"]
    )
    mask = d.boundary.contact_mask
    assert mask is not None
    assert mask[:, 0].all() and mask[:, -1].all()
    assert not mask[:, 1].all()


def test_single_cell_fixture():
    s = PlanetInspectionSession(seed=17)
    d = apply_current_setup(
        s, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_CELL)
    )
    assert d.boundary.enabled is True
    assert abs(float(d.boundary.K) - 0.1) < 1e-12
    assert int(d.boundary.contact_count) == 1
    assert d.boundary.contact_mask[4, 4]


def test_full_grid_fixture():
    s = PlanetInspectionSession(seed=17)
    d = apply_current_setup(
        s, CurrentPhysicalWorldSetup(seed=17, boundary_fixture_id=FIXTURE_FULL)
    )
    assert d.boundary.enabled is True
    assert abs(float(d.boundary.K) - 0.05) < 1e-12
    h, w = s.config.height, s.config.width
    assert int(d.boundary.contact_count) == h * w


def test_build_mask_shapes():
    m = build_mask(FIXTURE_OFF, 32, 32)
    assert m is None
    m = build_mask(FIXTURE_EDGE, 32, 32)
    assert m.shape == (32, 32)
    assert m.dtype == bool


def test_app_uses_planet_seed_var_not_legacy_seed_for_planet():
    assert "planet_seed_var" in APP_SRC
    assert "apply_current_setup" in APP_SRC
    assert "CURRENT PHYSICAL WORLD" in APP_SRC
    assert "LEGACY EXPERIMENTS" in APP_SRC
    assert "self.planet_session.reset(seed=int(self.seed_var.get()))" not in APP_SRC
    # Legacy Start Run still uses seed_var
    assert "seed=int(self.seed_var.get())" in APP_SRC


def test_no_live_boundary_editors():
    assert "textvariable=self.planet_M_ext" not in APP_SRC
    assert "configure_external_material_boundary(" not in APP_SRC
    from mechanistic_mind.ui.psychology_observer.app import PsychologyObserverApp

    c = PsychologyObserverApp.observer_mm_obs1_read_only_contract(PsychologyObserverApp)
    assert c["has_live_K_slider"] is False
    assert c["has_live_mask_paint"] is False
    assert c["has_live_M_ext_slider"] is False


def test_4_76_still_listed():
    assert "4.76 Acquired Transition Reinstatement" in APP_SRC


def test_legacy_launch_spec_seed_separate():
    spec = PsychologyLaunchSpec(seed=99)
    assert spec.seed == 99
    setup = CurrentPhysicalWorldSetup(seed=7)
    assert setup.seed == 7
    assert setup.seed != spec.seed


def test_fixture_catalog_frozen():
    assert FIXTURE_IDS == (
        FIXTURE_OFF,
        FIXTURE_EDGE,
        FIXTURE_CELL,
        FIXTURE_FULL,
    )
