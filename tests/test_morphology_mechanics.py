import numpy as np
from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime, PhysicalSystemConfig
from mechanistic_mind.physical_system.morphology_mechanics import MorphologyMechanicsConfig, ensure_B_site
from mechanistic_mind.physical_system.endogenous_motor import EndogenousMotorCouplingConfig
from mechanistic_mind.physical_system.cognition import CognitionConfig


def _cfg(morph="OFF", **kw):
    return PhysicalSystemConfig(
        cognition=CognitionConfig(cognition_enabled=False),
        endogenous_motor=EndogenousMotorCouplingConfig(mode="OFF"),
        morphology_mechanics=MorphologyMechanicsConfig(mode=morph, **kw),
    )


def test_default_off_no_B_site():
    rt = PhysicalSystemRuntime(seed=17, config=_cfg("OFF"))
    for _ in range(10):
        rt.step()
    assert rt.body.B_site is None
    assert rt.last_morphology_meta == {"enabled": False} or rt.last_morphology_meta.get("enabled") is False


def test_experimental_creates_B_site_and_forces():
    rt = PhysicalSystemRuntime(seed=17, config=_cfg("EXPERIMENTAL", strength=0.5))
    for _ in range(10):
        rt.step()
    assert rt.body.B_site is not None
    assert rt.body.B_site.shape[0] >= 1
    assert rt.last_morphology_meta.get("enabled") is True
    assert "net_force" in rt.last_morphology_meta


def test_zero_flow_no_morphology_propulsion():
    cfg = _cfg("EXPERIMENTAL", strength=0.5)
    cfg.planet.flow_enabled = False
    cfg.planet.flow_gain = 0.0
    cfg.body.flow_coupling = 0.0
    cfg.body.wave_coupling = 0.0
    rt = PhysicalSystemRuntime(seed=23, config=cfg)
    for _ in range(30):
        rt.step()
    assert abs(rt.body.vx) < 1e-9 and abs(rt.body.vy) < 1e-9


def test_same_env_different_B_site_changes_force():
    cfg = _cfg("EXPERIMENTAL", strength=0.8)
    a = PhysicalSystemRuntime(seed=41, config=cfg)
    b = PhysicalSystemRuntime(seed=41, config=_cfg("EXPERIMENTAL", strength=0.8))
    for _ in range(12):
        a.step(); b.step()
    ensure_B_site(a.body, 5); ensure_B_site(b.body, 5)
    for name in ("T", "M", "vx", "vy", "u"):
        getattr(b.world, name)[:] = np.asarray(getattr(a.world, name))
    b.body.x, b.body.y = a.body.x, a.body.y
    a.body.vx = a.body.vy = b.body.vx = b.body.vy = 0.0
    b.internal.c[:] = a.internal.c
    a.body.B_site[:] = 0.2
    b.body.B_site[:] = 0.2
    b.body.B_site[2] = 1.8
    a.step(); b.step()
    fa = np.array(a.last_morphology_meta["net_force"])
    fb = np.array(b.last_morphology_meta["net_force"])
    assert float(np.hypot(*(fa - fb))) > 1e-6
