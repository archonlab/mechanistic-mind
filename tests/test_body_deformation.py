import copy

import numpy as np

from mechanistic_mind.physical_system.body_deformation import (
    BodyDeformationConfig,
    rest_geometry,
    step_deformation,
)
from mechanistic_mind.physical_system.morphology_mechanics import ensure_B_site
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime


def _body():
    rt = PhysicalSystemRuntime(seed=17)
    ensure_B_site(rt.body, len(rt.config.body.footprint))
    return rt


def test_local_material_drives_only_body_local_geometry():
    rt = _body()
    before = (rt.body.x, rt.body.y, rt.body.vx, rt.body.vy, rt.body.theta, rt.body.omega)
    rt.body.B_site[:] = 0.2
    rt.body.B_site[1] = 1.8
    meta = step_deformation(rt.body, rt.config.body.footprint, BodyDeformationConfig())
    after = (rt.body.x, rt.body.y, rt.body.vx, rt.body.vy, rt.body.theta, rt.body.omega)
    assert after == before
    assert np.linalg.norm(rt.body.deformation[1]) > np.linalg.norm(rt.body.deformation[2])
    assert meta["mechanical_energy_accounting"] == "NOT DEMONSTRATED"


def test_symmetric_material_preserves_footprint_symmetry():
    rt = _body()
    rt.body.B_site[:] = 1.5
    cfg = BodyDeformationConfig()
    for _ in range(20):
        step_deformation(rt.body, rt.config.body.footprint, cfg)
    actual = rest_geometry(rt.config.body.footprint) + rt.body.deformation
    assert np.allclose(actual[1], -actual[2])
    assert np.allclose(actual[3], -actual[4])
    assert np.allclose(actual[0], [0.0, 0.0])


def test_material_drive_and_geometry_edges_are_independently_ablatable():
    a = _body()
    a.body.B_site[:] = 1.8
    off_drive = BodyDeformationConfig(material_drive_enabled=False)
    step_deformation(a.body, a.config.body.footprint, off_drive)
    assert np.allclose(a.body.deformation, 0.0)

    b = _body()
    b.body.B_site[:] = 1.8
    geometry_off = BodyDeformationConfig(geometry_coupling_enabled=False)
    meta = step_deformation(b.body, b.config.body.footprint, geometry_off)
    assert np.linalg.norm(b.body.deformation) > 0
    assert np.allclose(meta["actual_geometry"], meta["rest_geometry"])


def test_snapshot_round_trip_preserves_deformation_and_historical_missing_is_off():
    rt = _body()
    rt.body.B_site[:] = 1.8
    step_deformation(rt.body, rt.config.body.footprint, rt.config.body_deformation)
    snap = rt.snapshot()
    restored = PhysicalSystemRuntime.restore(snap)
    assert np.allclose(restored.body.deformation, rt.body.deformation)
    historical = copy.deepcopy(snap)
    historical["config"].pop("body_deformation")
    old = PhysicalSystemRuntime.restore(historical)
    assert old.config.body_deformation.enabled is False


def test_integrated_runtime_is_bounded_and_emits_shape_evidence():
    for seed in (17, 23, 41, 59, 83):
        rt = PhysicalSystemRuntime(seed=seed)
        rt.config.cognition.cognition_enabled = False
        for _ in range(120):
            rt.step()
        assert np.isfinite(rt.body.deformation).all()
        assert np.max(np.linalg.norm(rt.body.deformation, axis=1)) <= rt.config.body_deformation.max_displacement + 1e-12
        assert abs(rt.body.vx) <= rt.config.body.v_max
        assert abs(rt.body.vy) <= rt.config.body.v_max
        assert abs(rt.body.omega) <= rt.config.body_orientation.omega_max
        assert rt.last_deformation_meta["actual_geometry"]
