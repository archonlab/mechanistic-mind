"""Experimental physical signal bridge: shared FIELD_A/FIELD_B, no social semantics."""
from __future__ import annotations

from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime, available_actions
from mechanistic_mind.physical_system.actions import BRIDGE_MISSING


def _ta(**kw) -> TwoAgentRuntime:
    kw.setdefault("seed", 17)
    kw.setdefault("starts", ((10, 16), (14, 16)))
    kw.setdefault("contact_enabled", False)
    kw.setdefault("field_coupling_enabled", False)
    return TwoAgentRuntime(**kw)


def test_default_psr_observation_unchanged():
    rt = PhysicalSystemRuntime(seed=17)
    obs = rt.agent_observation()
    assert "local.FIELD_A" not in obs
    assert "local.FIELD_B" not in obs
    assert getattr(rt.world, "FIELD_A", None) is None
    assert "EMIT" not in available_actions()
    assert "EMIT" in BRIDGE_MISSING


def test_emit_not_added_to_canonical_actions():
    ta = _ta(signal_enabled=True)
    ta.step(1)
    assert "EMIT" not in available_actions()
    assert ta.slots[0].cognition["bridges"]["4.25_physical_emit_transducer_on_psr"] == "BRIDGE_MISSING"


def test_shared_field_not_private_copies():
    ta = _ta(signal_enabled=True)
    assert ta.slots[0].world is ta.slots[1].world
    ta.inject_source(slot=0, channel="A", amplitude=0.9, trigger="experimenter_forced_source")
    ta.step(1)
    assert ta.world.FIELD_A is ta.slots[1].world.FIELD_A
    assert float(ta.world.FIELD_A.max()) > 0.0


def test_receiver_observation_via_ordinary_perception():
    ta = _ta(signal_enabled=True, starts=((10, 16), (10, 16)))
    before = ta.slots[1].agent_observation()
    ta.inject_source(slot=0, channel="A", amplitude=0.9, trigger="experimenter_forced_source")
    ta.step(1)
    after = ta.slots[1].agent_observation()
    assert "local.FIELD_A" in after
    assert after["local.FIELD_A"] > before.get("local.FIELD_A", 0.0)
    assert "agent_0" not in repr(after)
    assert "source_agent" not in repr(after)


def test_distance_changes_received_amplitude():
    near = _ta(signal_enabled=True, starts=((10, 16), (11, 16)))
    far = _ta(signal_enabled=True, starts=((10, 16), (18, 16)))
    near.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
    far.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
    near.step(6)
    far.step(6)
    n = near.slots[1].agent_observation()["local.FIELD_A"]
    f = far.slots[1].agent_observation()["local.FIELD_A"]
    assert n > f


def test_out_of_range_below_floor():
    ta = _ta(signal_enabled=True, starts=((4, 16), (28, 16)))
    ta.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
    ta.step(2)
    amp = ta.slots[1].agent_observation()["local.FIELD_A"]
    assert amp < 0.02


def test_perception_ablation_omits_keys_but_field_exists():
    ta = _ta(signal_enabled=True, starts=((10, 16), (10, 16)))
    ta.slots[0].config.physical_signal.perception_enabled = False
    ta.slots[1].config.physical_signal.perception_enabled = False
    ta.inject_source(slot=0, channel="A", amplitude=0.9, trigger="experimenter_forced_source")
    ta.step(1)
    assert float(ta.world.FIELD_A.max()) > 0
    assert "local.FIELD_A" not in ta.slots[1].agent_observation()


def test_propagation_ablation_does_not_teleport():
    ta = _ta(signal_enabled=True, starts=((10, 16), (16, 16)))
    ta.slots[0].config.physical_signal.propagation_enabled = False
    ta.slots[1].config.physical_signal.propagation_enabled = False
    ta.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
    ta.step(8)
    assert ta.slots[1].agent_observation()["local.FIELD_A"] < 1e-3
    assert float(ta.world.FIELD_A.max()) > 0


def test_emission_ablation_blocks_body_sources():
    ta = _ta(signal_enabled=True, starts=((10, 16), (10, 16)))
    ta.slots[0].config.physical_signal.emission_enabled = False
    ta.slots[1].config.physical_signal.emission_enabled = False
    ta.slots[0].body.vx = 0.2
    ta.step(1)
    motion_only = float(ta.world.FIELD_A.max())
    ta.inject_source(slot=0, channel="A", amplitude=0.8, trigger="experimenter_forced_source")
    ta.step(1)
    # extra_sources still deposit; body motion must not
    assert motion_only < 1e-6


def test_order_swap_symmetric_signal():
    a = TwoAgentRuntime(seed=17, starts=((8, 16), (24, 16)), signal_enabled=True, process_order=(0, 1), contact_enabled=False, field_coupling_enabled=False)
    b = TwoAgentRuntime(seed=17, starts=((8, 16), (24, 16)), signal_enabled=True, process_order=(1, 0), contact_enabled=False, field_coupling_enabled=False)
    a.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
    b.inject_source(slot=0, channel="A", amplitude=1.0, trigger="experimenter_forced_source")
    a.step(4)
    b.step(4)
    d = abs(float(a.world.FIELD_A.sum()) - float(b.world.FIELD_A.sum()))
    assert d < 1e-6


def test_env_and_agent_source_same_local_keys():
    agent = _ta(signal_enabled=True, starts=((10, 16), (10, 16)))
    env = _ta(signal_enabled=True, starts=((10, 16), (10, 16)))
    agent.slots[0].config.physical_signal.emission_enabled = False
    env.slots[0].config.physical_signal.emission_enabled = False
    agent.inject_source(slot=0, channel="A", amplitude=0.7, trigger="experimenter_forced_source")
    env.inject_source(iy=16, ix=10, channel="A", amplitude=0.7, trigger="environmental")
    agent.step(1)
    env.step(1)
    oa = agent.slots[1].agent_observation()
    oe = env.slots[1].agent_observation()
    assert set(oa) == set(oe)
    assert abs(oa["local.FIELD_A"] - oe["local.FIELD_A"]) < 0.08
    assert "agent_0" not in repr(oa) and "environment" not in repr(oe)


def test_signal_off_does_not_create_fields():
    ta = _ta(signal_enabled=False)
    ta.step(3)
    assert getattr(ta.world, "FIELD_A", None) is None
    assert "local.FIELD_A" not in ta.slots[0].agent_observation()
