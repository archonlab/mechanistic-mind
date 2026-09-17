"""MM-OPEN-6 production external material boundary — frozen OPEN-5 contract."""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from mechanistic_mind.planet.boundary import (
    ExternalMaterialBoundaryConfigError,
    LAW_VERSION,
    configure_external_material_boundary,
    validate_external_material_boundary,
)
from mechanistic_mind.planet.config import PlanetConfig
from mechanistic_mind.planet.dynamics import step_planet
from mechanistic_mind.planet.runtime import restore_planet_state, serialize_planet_state, snapshot_stats
from mechanistic_mind.planet.state import initialize_planet


def _phys_hash(st) -> str:
    h = hashlib.sha256()
    for arr in (st.T, st.M, st.vx, st.vy, st.u, st.u_prev, st.capacity, st.conductivity):
        h.update(np.ascontiguousarray(arr).tobytes())
    h.update(int(st.tick).to_bytes(8, "little"))
    return h.hexdigest()


def _run(seed: int, horizon: int, *, firreg: float = 0.0, configure=None):
    cfg = PlanetConfig(F_irregular_amp=firreg)
    st = initialize_planet(cfg, seed=seed)
    if configure is not None:
        configure(st)
    for _ in range(horizon):
        step_planet(st, cfg, seed=seed)
    return st, cfg


# --- OFF equivalence (baseline hashes from pre-edit) ---
BASELINE_HASHES = {
    "seed17_h200_Firreg0": "55757ea886daa175c249b242c28921e73a99df54ac1bba770f808ea63301059b",
    "seed23_h200_Firreg0": "473ea6351b5a492f34451791f3a4ab005dfc218500ecacf19ed29f6b57ba4996",
    "seed41_h200_Firreg0": "81f386c7120e715adb4adeb4da4063855d5a2046e035cfbf5be9ffaa333b7334",
    "seed17_h100_default": "ab278be0cb28916272460b15acfaba771f8e19643bac6d7bb4ec9a7bdbd53e86",
}


@pytest.mark.parametrize(
    "key,seed,horizon,firreg",
    [
        ("seed17_h200_Firreg0", 17, 200, 0.0),
        ("seed23_h200_Firreg0", 23, 200, 0.0),
        ("seed41_h200_Firreg0", 41, 200, 0.0),
        ("seed17_h100_default", 17, 100, 0.05),
    ],
)
def test_off_bitwise_equivalence(key, seed, horizon, firreg):
    st, _ = _run(seed, horizon, firreg=firreg)
    assert not st.external_material_boundary.enabled
    assert _phys_hash(st) == BASELINE_HASHES[key]


def test_default_boundary_off():
    st = initialize_planet(seed=17)
    assert st.external_material_boundary.enabled is False
    assert st.external_material_boundary.contact_mask is None


def test_law_version():
    assert LAW_VERSION == "open1_signed_v1"


def test_missing_mask_errors():
    st = initialize_planet(seed=17)
    with pytest.raises(ExternalMaterialBoundaryConfigError):
        configure_external_material_boundary(st, enabled=True, contact_mask=None, K=0.1, M_ext=[0.25, 0.25, 0.25])


def test_missing_K_errors():
    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0:4, 0:4] = True
    with pytest.raises(ExternalMaterialBoundaryConfigError):
        configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=None, M_ext=[0.25, 0.25, 0.25])


def test_missing_M_ext_errors():
    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0:4, 0:4] = True
    with pytest.raises(ExternalMaterialBoundaryConfigError):
        configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.1, M_ext=None)


def test_empty_mask_errors():
    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    with pytest.raises(ExternalMaterialBoundaryConfigError):
        configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.1, M_ext=[0.25, 0.25, 0.25])


def test_wrong_mask_dims_errors():
    st = initialize_planet(seed=17)
    mask = np.ones((16, 16), dtype=bool)
    with pytest.raises(ExternalMaterialBoundaryConfigError):
        configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.1, M_ext=[0.25, 0.25, 0.25])


def test_wrong_M_ext_channels_errors():
    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0, 0] = True
    with pytest.raises(ExternalMaterialBoundaryConfigError):
        configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.1, M_ext=[0.25, 0.25])


def test_K_ge_2_rejected():
    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0, 0] = True
    with pytest.raises(ExternalMaterialBoundaryConfigError):
        configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=2.0, M_ext=[0.25, 0.25, 0.25])


def test_negative_K_rejected():
    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0, 0] = True
    with pytest.raises(ExternalMaterialBoundaryConfigError):
        configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=-0.1, M_ext=[0.25, 0.25, 0.25])


def test_nan_K_rejected():
    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0, 0] = True
    with pytest.raises(ExternalMaterialBoundaryConfigError):
        configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=float("nan"), M_ext=[0.25, 0.25, 0.25])


def test_full_mask_allowed():
    st = initialize_planet(seed=17)
    mask = np.ones((32, 32), dtype=bool)
    configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.1, M_ext=[0.25, 0.25, 0.25])
    assert st.external_material_boundary.enabled


def test_equal_concentration_zero_net():
    st = initialize_planet(PlanetConfig(F_irregular_amp=0.0), seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0:8, 0:8] = True
    st.M[:] = 0.25
    configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.5, M_ext=[0.25, 0.25, 0.25])
    step_planet(st, PlanetConfig(F_irregular_amp=0.0), seed=17)
    # after full step matter changes; check pure boundary apply
    from mechanistic_mind.planet.boundary import step_external_material_boundary

    st.M[:] = 0.25
    st.external_material_boundary.cum_import[:] = 0
    st.external_material_boundary.cum_export[:] = 0
    step_external_material_boundary(st)
    assert float(np.sum(np.abs(st.external_material_boundary.last_signed_flux))) == 0.0


def test_import_when_M_ext_greater():
    from mechanistic_mind.planet.boundary import step_external_material_boundary

    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0:4, 0:4] = True
    st.M[:] = 0.05
    configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.5, M_ext=[0.25, 0.25, 0.25])
    before = float(st.M.sum())
    step_external_material_boundary(st)
    assert float(st.M.sum()) > before
    assert float(st.external_material_boundary.cum_import.sum()) > 0


def test_export_when_M_ext_less():
    from mechanistic_mind.planet.boundary import step_external_material_boundary

    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0:4, 0:4] = True
    st.M[:] = 0.8
    configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.5, M_ext=[0.25, 0.25, 0.25])
    before = float(st.M.sum())
    step_external_material_boundary(st)
    assert float(st.M.sum()) < before
    assert float(st.external_material_boundary.cum_export.sum()) > 0


def test_contact_locality_before_transport():
    from mechanistic_mind.planet.boundary import step_external_material_boundary

    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0:4, 0:4] = True
    M0 = st.M.copy()
    configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.5, M_ext=[0.25, 0.25, 0.25])
    step_external_material_boundary(st)
    assert np.allclose(st.M[:, ~mask], M0[:, ~mask])


def test_accounting_residual():
    from mechanistic_mind.planet.boundary import step_external_material_boundary, ACCOUNTING_TOL

    st = initialize_planet(seed=17)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0:8, 0:8] = True
    configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.16, M_ext=[0.25, 0.25, 0.25])
    step_external_material_boundary(st)
    assert st.external_material_boundary.last_residual_max < ACCOUNTING_TOL


def test_no_rectification_signed():
    from mechanistic_mind.planet.boundary import step_external_material_boundary

    st = initialize_planet(seed=17)
    mask = np.ones((32, 32), dtype=bool)
    # mixed: half low half high
    st.M[:] = 0.05
    st.M[:, 16:] = 0.8
    configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.2, M_ext=[0.25, 0.25, 0.25])
    step_external_material_boundary(st)
    assert float(st.external_material_boundary.cum_import.sum()) > 0
    assert float(st.external_material_boundary.cum_export.sum()) > 0


def test_snapshot_replay_on():
    cfg = PlanetConfig(F_irregular_amp=0.0)
    mask = np.zeros((32, 32), dtype=bool)
    mask[0:8, 0:8] = True

    def run_n(n, st=None, cfg=None):
        if st is None:
            cfg = PlanetConfig(F_irregular_amp=0.0)
            st = initialize_planet(cfg, seed=17)
            configure_external_material_boundary(st, enabled=True, contact_mask=mask, K=0.16, M_ext=[0.25, 0.25, 0.25])
        for _ in range(n):
            step_planet(st, cfg, seed=17)
        return st, cfg

    cont, cfg = run_n(200)
    mid, cfg = run_n(100)
    payload = serialize_planet_state(mid, cfg)
    st2, cfg2 = restore_planet_state(payload)
    for _ in range(100):
        step_planet(st2, cfg2, seed=17)
    assert _phys_hash(cont) == _phys_hash(st2)
    assert np.allclose(cont.external_material_boundary.cum_import, st2.external_material_boundary.cum_import)


def test_snapshot_replay_off():
    cont, cfg = _run(17, 150, firreg=0.0)
    mid, cfg = _run(17, 75, firreg=0.0)
    payload = serialize_planet_state(mid, cfg)
    # strip boundary key to simulate legacy
    payload2 = dict(payload)
    payload2.pop("external_material_boundary", None)
    st2, cfg2 = restore_planet_state(payload2)
    assert st2.external_material_boundary.enabled is False
    for _ in range(75):
        step_planet(st2, cfg2, seed=17)
    assert _phys_hash(cont) == _phys_hash(st2)


def test_legacy_missing_boundary_off():
    st, cfg = _run(17, 10, firreg=0.0)
    payload = serialize_planet_state(st, cfg)
    del payload["external_material_boundary"]
    st2, _ = restore_planet_state(payload)
    assert st2.external_material_boundary.enabled is False


def test_serialization_roundtrip():
    st, cfg = _run(17, 5, firreg=0.0)

    def cfg_on(s):
        mask = np.zeros((32, 32), dtype=bool)
        mask[2:6, 2:6] = True
        configure_external_material_boundary(s, enabled=True, contact_mask=mask, K=0.3, M_ext=[0.2, 0.2, 0.2])

    st, cfg = _run(17, 5, firreg=0.0, configure=cfg_on)
    p1 = serialize_planet_state(st, cfg)
    st2, cfg2 = restore_planet_state(p1)
    p2 = serialize_planet_state(st2, cfg2)
    assert p1["external_material_boundary"]["enabled"] == p2["external_material_boundary"]["enabled"]
    assert p1["external_material_boundary"]["K"] == p2["external_material_boundary"]["K"]
    assert p1["external_material_boundary"]["contact_mask"] == p2["external_material_boundary"]["contact_mask"]
    assert p1["external_material_boundary"]["M_ext"] == p2["external_material_boundary"]["M_ext"]


def test_zero_organism_on_and_off():
    # no organism API involved
    st_off, _ = _run(17, 20, firreg=0.0)
    assert not st_off.external_material_boundary.enabled

    def cfg_on(s):
        mask = np.ones((32, 32), dtype=bool)
        configure_external_material_boundary(s, enabled=True, contact_mask=mask, K=0.05, M_ext=[0.25, 0.25, 0.25])

    st_on, _ = _run(17, 20, firreg=0.0, configure=cfg_on)
    assert st_on.external_material_boundary.enabled


def test_snapshot_stats_includes_boundary_primitives():
    st = initialize_planet(PlanetConfig(F_irregular_amp=0.0), seed=17)
    stats = snapshot_stats(st, PlanetConfig(F_irregular_amp=0.0), seed=17)
    assert "external_material_boundary" in stats
    assert stats["external_material_boundary"]["enabled"] is False


def test_config_default_enabled_false():
    cfg = PlanetConfig()
    assert cfg.external_material_boundary_enabled is False
