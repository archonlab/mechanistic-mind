"""MM-ANALYZER-1 — stratified Physical World scientific summaries."""
from __future__ import annotations

from pathlib import Path

from mechanistic_mind.ui.psychology_observer.planet_analyzer import (
    ANALYZER_VERSION,
    STRATUM_DERIVED,
    STRATUM_INTERP,
    STRATUM_NULL,
    STRATUM_RAW,
    STRATUM_UNSUPPORTED,
    analyze_physical_world,
    assert_no_stratum_elevation,
    claims_by_stratum,
)
from mechanistic_mind.ui.psychology_observer.planet_session import PlanetInspectionSession
from mechanistic_mind.ui.psychology_observer.planet_setup import (
    CurrentPhysicalWorldSetup,
    FIXTURE_EDGE,
    FIXTURE_OFF,
    apply_current_setup,
)

APP = Path("mechanistic_mind/ui/psychology_observer/app.py").read_text()


def _off_session(seed: int = 17) -> PlanetInspectionSession:
    s = PlanetInspectionSession(seed=seed)
    apply_current_setup(s, CurrentPhysicalWorldSetup(seed=seed, boundary_fixture_id=FIXTURE_OFF))
    return s


def _on_session(seed: int = 17) -> PlanetInspectionSession:
    s = PlanetInspectionSession(seed=seed)
    apply_current_setup(s, CurrentPhysicalWorldSetup(seed=seed, boundary_fixture_id=FIXTURE_EDGE))
    for _ in range(5):
        s.step(1)
    return s


def test_deterministic_same_display():
    s = _off_session()
    d = s.display
    a = analyze_physical_world(d, history=s.history.as_list())
    b = analyze_physical_world(d, history=s.history.as_list())
    assert a.to_dict() == b.to_dict()
    assert a.analyzer_version == ANALYZER_VERSION


def test_strata_present_and_no_elevation():
    s = _on_session()
    r = analyze_physical_world(s.display, history=s.history.as_list())
    assert_no_stratum_elevation(r)
    counts = r.to_dict()["stratum_counts"]
    assert counts[STRATUM_RAW] >= 5
    assert counts[STRATUM_INTERP] >= 1
    assert counts[STRATUM_NULL] >= 3
    assert counts[STRATUM_UNSUPPORTED] >= 3


def test_off_boundary_interpretation():
    s = _off_session()
    r = analyze_physical_world(s.display)
    keys = {c.key for c in claims_by_stratum(r, STRATUM_INTERP)}
    assert "boundary_off_no_exchange" in keys
    raw_on = [c for c in claims_by_stratum(r, STRATUM_RAW) if c.key == "boundary_enabled"]
    assert raw_on and raw_on[0].value is False
    assert "boundary_on_known_law" not in {c.key for c in r.claims}


def test_on_boundary_flux_derived():
    s = _on_session()
    r = analyze_physical_world(s.display, history=s.history.as_list())
    der = {c.key: c for c in claims_by_stratum(r, STRATUM_DERIVED)}
    assert "net_flux" in der
    assert "residual_within_tolerance" in der
    assert "boundary_on_known_law" in {c.key for c in claims_by_stratum(r, STRATUM_INTERP)}


def test_history_null_when_short():
    s = PlanetInspectionSession(seed=3)
    apply_current_setup(s, CurrentPhysicalWorldSetup(seed=3))
    r = analyze_physical_world(s.display, history=s.history.as_list())
    null_keys = {c.key for c in claims_by_stratum(r, STRATUM_NULL)}
    assert "history_deltas" in null_keys
    assert "delta_M0_sum_history" not in {c.key for c in r.claims}


def test_history_delta_when_long_enough():
    s = _off_session()
    for _ in range(10):
        s.step(1)
    r = analyze_physical_world(s.display, history=s.history.as_list())
    assert "delta_M0_sum_history" in {c.key for c in claims_by_stratum(r, STRATUM_DERIVED)}


def test_null_body_internal_j_overlay():
    s = _off_session()
    r = analyze_physical_world(s.display)
    null_keys = {c.key for c in claims_by_stratum(r, STRATUM_NULL)}
    assert "local_J_overlay_map" in null_keys
    assert "body_state" in null_keys
    assert "internal_substrate_state" in null_keys
    assert "organism_cognition" in null_keys


def test_unsupported_fence_listed_not_asserted_as_raw():
    s = _off_session()
    r = analyze_physical_world(s.display)
    unsup = claims_by_stratum(r, STRATUM_UNSUPPORTED)
    assert len(unsup) >= 3
    for c in unsup:
        assert c.stratum == STRATUM_UNSUPPORTED
        assert c.key.startswith("refuse_")


def test_summary_contains_stratum_headers():
    s = _on_session()
    r = analyze_physical_world(s.display, history=s.history.as_list())
    for header in (STRATUM_RAW, STRATUM_DERIVED, STRATUM_INTERP, STRATUM_NULL, STRATUM_UNSUPPORTED):
        assert header in r.summary_text


def test_app_wires_analyzer_panel_read_only():
    assert "planet_analyzer_panel" in APP
    assert "analyze_physical_world" in APP
    assert "PHYSICAL WORLD ANALYZER" in APP
    assert "configure_external_material_boundary(" not in APP


def test_analyzer_module_exists_outside_planet_physics():
    assert Path("mechanistic_mind/ui/psychology_observer/planet_analyzer.py").is_file()
    from mechanistic_mind.planet.dynamics import step_planet  # noqa: F401
