
import numpy as np
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime, PhysicalSystemConfig
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.cognition import CognitionConfig

def _rt(mode, seed=17):
    cfg = PhysicalSystemConfig(
        cognition=CognitionConfig(cognition_enabled=False),
        endogenous_motor=EndogenousMotorCouplingConfig(mode=mode, strength=0.12),
    )
    cfg.planet.flow_enabled = False
    cfg.planet.flow_gain = 0.0
    cfg.body.flow_coupling = 0.0
    cfg.body.wave_coupling = 0.0
    return PhysicalSystemRuntime(seed=seed, config=cfg)

def test_off_reproduces_zero_motor_and_no_motion_in_zero_flow():
    rt = _rt("OFF")
    for _ in range(40):
        rt.step()
    assert rt.body.motor_ux == 0.0 and rt.body.motor_uy == 0.0
    assert abs(rt.body.x - (rt.config.body.start_x + 0.5)) < 1e-9

def test_on_creates_nonzero_motor_or_motion_in_zero_flow():
    rt = _rt("EXPERIMENTAL")
    for _ in range(40):
        rt.step()
    assert abs(rt.body.motor_ux) + abs(rt.body.motor_uy) > 0.0 or abs(rt.body.vx) + abs(rt.body.vy) > 0.0

def test_current_integrated_default_is_on():
    rt = PhysicalSystemRuntime(seed=17)
    assert rt.config.endogenous_motor.mode == "EXPERIMENTAL"
