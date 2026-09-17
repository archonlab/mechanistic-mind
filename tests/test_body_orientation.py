import numpy as np
import pytest
from mechanistic_mind.physical_system.body_orientation import (
    BodyOrientationConfig,
    wrap_theta,
    body_local_to_world,
    world_to_body_local,
    footprint_body_local,
    oriented_site_cells,
    torque_2d,
    step_orientation_mechanics,
)
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime, PhysicalSystemConfig
from mechanistic_mind.physical_system.morphology_mechanics import MorphologyMechanicsConfig
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.cognition import CognitionConfig


def _cfg(orient="OFF", morph="OFF", **ok):
    return PhysicalSystemConfig(
        cognition=CognitionConfig(cognition_enabled=False),
        endogenous_motor=EndogenousMotorCouplingConfig(mode="OFF"),
        morphology_mechanics=MorphologyMechanicsConfig(mode=morph, strength=0.5),
        body_orientation=BodyOrientationConfig(mode=orient, **ok),
    )


def test_theta_wrapping():
    assert abs(wrap_theta(0.0)) < 1e-12
    assert abs(wrap_theta(2 * np.pi)) < 1e-9
    assert abs(wrap_theta(np.pi) - np.pi) < 1e-12
    assert wrap_theta(3 * np.pi) == pytest.approx(np.pi) or abs(wrap_theta(3*np.pi)) <= np.pi + 1e-9


def test_body_local_world_roundtrip():
    center = (10.0, 12.0)
    theta = 0.37
    r = np.array([1.0, -2.0])
    w = body_local_to_world(r, theta, center)
    back = world_to_body_local(w, theta, center)
    assert np.allclose(r, back, atol=1e-10)


def test_footprint_rotation_changes_cells():
    rt = PhysicalSystemRuntime(seed=17, config=_cfg("EXPERIMENTAL", "EXPERIMENTAL"))
    fp = rt.config.body.footprint
    c0 = oriented_site_cells(rt.body, rt.world.T.shape[1], rt.world.T.shape[0], fp, theta=0.0)
    c1 = oriented_site_cells(rt.body, rt.world.T.shape[1], rt.world.T.shape[0], fp, theta=np.pi / 2)
    assert c0 != c1


def test_torque_symmetric_forces_zero():
    # equal opposite forces on +/- x with equal |F| parallel to x → zero torque
    assert abs(torque_2d(np.array([1.0, 0.0]), np.array([1.0, 0.0])) + torque_2d(np.array([-1.0, 0.0]), np.array([-1.0, 0.0]))) < 1e-12


def test_mirrored_forces_mirrored_torque():
    r = np.array([1.0, 0.5])
    F = np.array([0.2, -0.7])
    t = torque_2d(r, F)
    t2 = torque_2d(np.array([-r[0], r[1]]), np.array([-F[0], F[1]]))
    assert abs(t + t2) < 1e-12


def test_orientation_off_default():
    rt = PhysicalSystemRuntime(seed=17, config=_cfg("OFF"))
    for _ in range(8):
        rt.step()
    assert rt.last_orientation_meta == {"enabled": False} or rt.last_orientation_meta.get("enabled") is False
    assert abs(rt.body.theta) < 1e-15 or rt.body.theta == 0.0


def test_shear_produces_torque_and_theta():
    cfg = _cfg("EXPERIMENTAL", "EXPERIMENTAL", apply_net_force_to_com=False, angular_drag=0.1)
    cfg.planet.flow_enabled = False
    cfg.body.displacement_enabled = False
    rt = PhysicalSystemRuntime(seed=17, config=cfg)
    x0, y0 = rt.body.x, rt.body.y
    rt.body.theta = 0.0
    rt.body.omega = 0.0
    h, w = rt.world.T.shape
    cy, cx = rt.body.cell(w, h)
    for _ in range(15):
        rt.world.vx[:] = 0
        rt.world.vy[:] = 0
        for dy in range(-5, 6):
            for dx in range(-5, 6):
                iy = int((cy + dy) % h)
                ix = int((cx + dx) % w)
                rt.world.vx[iy, ix] = 2.5 * (dy / 5.0)
        rt.body.x, rt.body.y = x0, y0
        rt.body.vx = rt.body.vy = 0.0
        rt.step()
        rt.body.x, rt.body.y = x0, y0
    assert abs(rt.last_orientation_meta.get("tau") or 0) > 1e-6 or abs(rt.body.theta) > 1e-4
    assert abs(rt.body.theta) > 1e-4


def test_no_semantic_control_symbols():
    text = open("mechanistic_mind/physical_system/body_orientation.py").read()
    for bad in ("desired_theta", "look_direction", "facing_goal", "steering_angle", "preferred_direction"):
        assert bad not in text
