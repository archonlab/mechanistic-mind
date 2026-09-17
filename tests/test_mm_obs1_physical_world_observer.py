"""MM-OBS-1 Physical World Observer — mapping & read-only contracts."""
from __future__ import annotations

import hashlib
import json

import numpy as np
import pytest

from mechanistic_mind.planet.boundary import ACCOUNTING_TOL, LAW_VERSION
from mechanistic_mind.planet.config import PlanetConfig
from mechanistic_mind.planet.runtime import serialize_planet_state
from mechanistic_mind.ui.psychology_observer.cli import headless_contract
from mechanistic_mind.ui.psychology_observer.planet_model import (
    SIGN_CONVENTION,
    assert_read_only_surface,
    boundary_display_from_mapping,
    cell_inspector,
    display_from_serialized,
    ephemeral_local_J,
    field_array,
    format_boundary_panel,
    format_world_status,
)
from mechanistic_mind.ui.psychology_observer.planet_session import PlanetInspectionSession


BASELINE_OFF = {
    # Current Observer now inspects canonical WORLD after reciprocal BODY coupling.
    "seed17_h200_Firreg0": "82a760fb5718518c77ece288bc636728f63552d47d137da4e65be070c23654ad",
}


def _phys_hash(st) -> str:
    h = hashlib.sha256()
    for arr in (st.T, st.M, st.vx, st.vy, st.u, st.u_prev, st.capacity, st.conductivity):
        h.update(np.ascontiguousarray(arr).tobytes())
    h.update(int(st.tick).to_bytes(8, "little"))
    return h.hexdigest()


def test_headless_contract_exposes_physical_world():
    c = headless_contract()
    assert "physical_world" in c["view_modes"]
    assert "external_material_boundary" in c["observer_panels_extra"]
    assert c["mm_obs1_read_only"] is True


def test_boundary_off_display():
    s = PlanetInspectionSession(seed=17)
    d = s.reset()
    text = format_boundary_panel(d)
    assert "OFF" in text
    assert d.boundary.enabled is False
    assert d.boundary.contact_mask is None
    assert "ON" not in text.splitlines()[1]


def test_boundary_on_metadata():
    s = PlanetInspectionSession(seed=17)
    s.reset()
    mask = np.zeros((32, 32), dtype=bool)
    mask[1:4, 2:5] = True
    s.apply_boundary_fixture(enabled=True, contact_mask=mask, K=0.16, M_ext=[0.2, 0.3, 0.4])
    d = s.step(3)
    text = format_boundary_panel(d)
    assert "ON" in text
    assert LAW_VERSION in text
    assert "0.16" in text
    assert "M0: 0.2" in text or "M0: 0.200" in text
    assert d.boundary.contact_count == 9
    assert d.boundary.mask_sha256 is not None
    assert SIGN_CONVENTION.split(";")[0] in text or "external -> WORLD" in text


def test_asymmetric_mask_orientation():
    s = PlanetInspectionSession(seed=17)
    s.reset()
    mask = np.zeros((32, 32), dtype=bool)
    mask[7, 1] = True
    mask[2, 10] = True
    s.apply_boundary_fixture(enabled=True, contact_mask=mask, K=0.1, M_ext=[0.25, 0.25, 0.25])
    d = s.display
    assert d.boundary.contact_mask[7, 1]
    assert d.boundary.contact_mask[2, 10]
    assert not d.boundary.contact_mask[1, 7]
    assert not d.boundary.contact_mask[10, 2]


def test_material_orientation_matches_mask_coords():
    s = PlanetInspectionSession(seed=17)
    s.reset()
    mask = np.zeros((32, 32), dtype=bool)
    mask[5, 8] = True
    s.apply_boundary_fixture(enabled=True, contact_mask=mask, K=0.5, M_ext=[0.9, 0.9, 0.9])
    # force known M
    s._state.M[:] = 0.01
    d = s.step(1)
    J = ephemeral_local_J(d)
    assert J is not None
    assert J[0, 5, 8] > 0
    assert abs(J[0, 8, 5]) < 1e-15


def test_import_export_and_residual():
    s = PlanetInspectionSession(seed=17)
    s.reset()
    mask = np.ones((32, 32), dtype=bool)
    s.apply_boundary_fixture(enabled=True, contact_mask=mask, K=0.2, M_ext=[0.25, 0.25, 0.25])
    s._state.M[:] = 0.05
    d = s.step(1)
    assert sum(d.boundary.cum_import) > 0
    s2 = PlanetInspectionSession(seed=17)
    s2.reset()
    s2.apply_boundary_fixture(enabled=True, contact_mask=mask, K=0.2, M_ext=[0.05, 0.05, 0.05])
    s2._state.M[:] = 0.8
    d2 = s2.step(1)
    assert sum(d2.boundary.cum_export) > 0
    assert d.boundary.last_residual_max <= ACCOUNTING_TOL
    assert d.boundary.residual_within_tolerance


def test_mixed_channel_directions():
    s = PlanetInspectionSession(seed=17)
    s.reset()
    mask = np.ones((32, 32), dtype=bool)
    s.apply_boundary_fixture(enabled=True, contact_mask=mask, K=0.2, M_ext=[0.9, 0.05, 0.25])
    s._state.M[0] = 0.05
    s._state.M[1] = 0.9
    s._state.M[2] = 0.25
    d = s.step(1)
    assert d.boundary.last_signed_flux[0] > 0
    assert d.boundary.last_signed_flux[1] < 0


def test_full_and_irregular_mask():
    s = PlanetInspectionSession(seed=17)
    s.reset()
    full = np.ones((32, 32), dtype=bool)
    s.apply_boundary_fixture(enabled=True, contact_mask=full, K=0.05, M_ext=[0.25, 0.25, 0.25])
    assert s.display.boundary.contact_count == 32 * 32
    irreg = np.zeros((32, 32), dtype=bool)
    for y, x in [(0, 0), (3, 17), (31, 4), (12, 12), (20, 1)]:
        irreg[y, x] = True
    s.apply_boundary_fixture(enabled=True, contact_mask=irreg, K=0.05, M_ext=[0.25, 0.25, 0.25])
    assert s.display.boundary.contact_count == 5
    for y, x in [(0, 0), (3, 17), (31, 4), (12, 12), (20, 1)]:
        assert s.display.boundary.contact_mask[y, x]


def test_snapshot_and_legacy():
    s = PlanetInspectionSession(seed=17)
    s.reset()
    mask = np.zeros((32, 32), dtype=bool)
    mask[4:6, 4:6] = True
    s.apply_boundary_fixture(enabled=True, contact_mask=mask, K=0.12, M_ext=[0.25, 0.25, 0.25])
    s.step(10)
    payload = s.snapshot_payload()
    d = display_from_serialized(payload)
    assert d.boundary.enabled
    assert d.boundary.K == pytest.approx(0.12)
    assert d.boundary.contact_mask[4, 4]
    legacy = dict(payload)
    del legacy["external_material_boundary"]
    d2 = display_from_serialized(legacy, source="legacy")
    assert d2.boundary.enabled is False
    assert "OFF" in format_boundary_panel(d2)


def test_physical_run_is_saved_and_restorable(tmp_path):
    s = PlanetInspectionSession(seed=17)
    s.reset()
    s.step(3)
    run_dir = s.save_run(
        tmp_path, stop_reason="reset", boundary_fixture_id="off"
    )
    assert run_dir is not None
    manifest = json.loads((run_dir / "run.json").read_text())
    snapshot = json.loads((run_dir / "physical_system_snapshot.json").read_text())
    assert manifest["final_tick"] == 3
    assert manifest["stop_reason"] == "reset"
    restored = PlanetInspectionSession(seed=1)
    restored.load_snapshot(snapshot)
    assert restored.display.tick == 3


def test_empty_physical_run_is_not_saved(tmp_path):
    s = PlanetInspectionSession(seed=17)
    s.reset()
    assert s.save_run(tmp_path, stop_reason="reset", boundary_fixture_id="off") is None


def test_malformed_telemetry_graceful():
    b = boundary_display_from_mapping(
        {"enabled": True, "K": 0.1, "M_ext": [0.1, 0.1, 0.1], "contact_mask": [[True]]},
        height=32,
        width=32,
        n_materials=3,
    )
    # wrong shape mask dropped
    assert b.enabled is True
    assert b.contact_mask is None
    b2 = boundary_display_from_mapping(None, height=32, width=32, n_materials=3)
    assert b2.enabled is False


def test_cell_inspector_observer_only():
    s = PlanetInspectionSession(seed=17)
    s.reset()
    d = s.display
    info = cell_inspector(d, 3, 5)
    assert info["y"] == 3 and info["x"] == 5
    assert info["observer_only"] is True
    assert "agent observation" in info["note"]


def test_world_status_and_layers():
    s = PlanetInspectionSession(seed=17)
    d = s.reset()
    text = format_world_status(d)
    assert "PHYSICAL WORLD STATUS" in text
    assert "toroidal" in text
    for layer in ("M0", "M1", "M2", "Temperature", "Flow", "Wave"):
        arr = field_array(d, layer)
        assert arr.shape == (32, 32)


def test_no_new_control_path_symbols():
    forbidden = assert_read_only_surface()
    assert "live_K_slider" in forbidden
    from mechanistic_mind.ui.psychology_observer.app import PsychologyObserverApp
    assert hasattr(PsychologyObserverApp, "observer_mm_obs1_read_only_contract")
    contract = PsychologyObserverApp.observer_mm_obs1_read_only_contract(PsychologyObserverApp)
    assert contract["has_live_K_slider"] is False
    assert contract["has_live_mask_paint"] is False
    assert contract["has_live_M_ext_slider"] is False
    src = open("mechanistic_mind/ui/psychology_observer/app.py").read()
    assert "configure_external_material_boundary(" not in src
    assert "H_ret" not in src
    assert "tau_erase" not in src
    assert "mask_corr" not in src
    # audit helper may name forbidden controls; ensure no Scale/Entry editors for K/M_ext/mask
    assert "textvariable=self.planet_K" not in src
    assert "textvariable=self.planet_M_ext" not in src


def test_physics_off_equivalence_noninterference():
    cfg = PlanetConfig(F_irregular_amp=0.0)
    s = PlanetInspectionSession(seed=17, config=cfg)
    s.reset()
    for _ in range(200):
        s.step(1)
    assert _phys_hash(s._state) == BASELINE_OFF["seed17_h200_Firreg0"]


def test_counters_match_production_state():
    s = PlanetInspectionSession(seed=17)
    s.reset()
    mask = np.zeros((32, 32), dtype=bool)
    mask[0:8, 0:8] = True
    s.apply_boundary_fixture(enabled=True, contact_mask=mask, K=0.16, M_ext=[0.25, 0.25, 0.25])
    d = s.step(5)
    b = s._state.external_material_boundary
    assert tuple(float(x) for x in b.cum_import) == d.boundary.cum_import
    assert tuple(float(x) for x in b.cum_export) == d.boundary.cum_export
