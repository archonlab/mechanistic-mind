from copy import deepcopy

import numpy as np

from mechanistic_mind.physical_system import PhysicalSystemConfig, PhysicalSystemRuntime


def _equal(a, b):
    assert a["tick"] == b["tick"]
    assert np.array_equal(a["world"]["T"], b["world"]["T"])
    assert np.array_equal(a["world"]["M"], b["world"]["M"])
    assert a["body"] == b["body"]
    assert a["internal"] == b["internal"]


def test_one_owner_one_tick_and_instance_chain():
    runtime = PhysicalSystemRuntime(seed=17)
    world = runtime.world
    body = runtime.body
    internal = runtime.internal
    runtime.step()
    assert runtime.world is world and runtime.body is body and runtime.internal is internal
    assert runtime.tick == runtime.world.tick == runtime.body.tick == runtime.internal.tick == 1


def test_determinism_and_snapshot_replay():
    a = PhysicalSystemRuntime(seed=9)
    b = PhysicalSystemRuntime(seed=9)
    a.step(12)
    b.step(12)
    _equal(a.snapshot(), b.snapshot())
    checkpoint = deepcopy(a.snapshot())
    a.step(8)
    restored = PhysicalSystemRuntime.restore(checkpoint)
    restored.step(8)
    _equal(a.snapshot(), restored.snapshot())


def test_world_body_internal_causal_chain_and_ablation():
    live = PhysicalSystemRuntime(seed=17)
    cut_world_body_cfg = PhysicalSystemConfig()
    cut_world_body_cfg.body.thermal_enabled = False
    cut_world_body_cfg.body.material_enabled = False
    cut_world_body_cfg.body.mechanical_enabled = False
    cut_world_body = PhysicalSystemRuntime(seed=17, config=cut_world_body_cfg)
    cut_internal_cfg = PhysicalSystemConfig()
    cut_internal_cfg.internal.coupling_enabled = False
    cut_internal = PhysicalSystemRuntime(seed=17, config=cut_internal_cfg)
    live.step(25)
    cut_world_body.step(25)
    cut_internal.step(25)
    assert not np.array_equal(live.body.B, cut_world_body.body.B)
    assert not np.array_equal(live.internal.c, cut_world_body.internal.c)
    assert not np.array_equal(live.internal.c, cut_internal.internal.c)
    assert not np.array_equal(live.world.M, cut_world_body.world.M)


def test_internal_to_body_passive_reciprocal_exchange():
    rich = PhysicalSystemRuntime(seed=2)
    control = PhysicalSystemRuntime(seed=2)
    rich.internal.c[:] = 0.9
    rich.step()
    control.step()
    assert not np.array_equal(rich.body.B, control.body.B)
    assert abs(rich.last_internal_flux.material_residual) < 1e-12


def test_bounded_stability():
    runtime = PhysicalSystemRuntime(seed=17)
    runtime.step(200)
    arrays = (runtime.world.T, runtime.world.M, runtime.world.vx, runtime.world.vy,
              runtime.world.u, runtime.body.B, runtime.body.B_core, runtime.internal.c)
    assert all(np.isfinite(value).all() for value in arrays)
    assert all((value >= 0).all() for value in (runtime.world.M, runtime.body.B,
                                                runtime.body.B_core, runtime.internal.c))
