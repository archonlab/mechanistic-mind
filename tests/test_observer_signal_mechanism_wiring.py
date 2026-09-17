"""Observer/Experiment wiring: experimental_physical_signal must allocate SIGNAL fields."""
from __future__ import annotations

from mechanistic_mind.physical_system.runtime import PhysicalSystemConfig, PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.serialize import discover_world_fields
from mechanistic_mind.ui.psy_observer_web.session import ObserverSession


def test_two_agent_set_mechanism_allocates_signal_fields():
    ta = TwoAgentRuntime(seed=41)
    assert ta.signal_enabled is False
    ids = {f["id"] for f in discover_world_fields(ta)}
    assert "FIELD_A" not in ids
    ta.set_mechanism("experimental_physical_signal", True)
    assert ta.signal_enabled is True
    assert ta.world.FIELD_A is not None
    assert ta.slots[0].config.physical_signal.enabled
    assert ta.slots[1].config.physical_signal.enabled
    ids = {f["id"] for f in discover_world_fields(ta)}
    assert "FIELD_A" in ids and "FIELD_B" in ids
    ta.set_mechanism("experimental_physical_signal", False)
    assert ta.signal_enabled is False
    assert ta.world.FIELD_A is None


def test_apply_experiment_honors_signal_mechanism():
    s = ObserverSession()
    frame = s.apply_experiment({
        "seed": 42,
        "agent_count": 2,
        "cognition_enabled": True,
        "world": {"width": 12, "height": 12, "boundary_mode": "WRAP_PERIODIC"},
        "mechanisms": {
            "cognition_enabled": True,
            "experimental_physical_signal": True,
        },
    })
    assert isinstance(s.runtime, TwoAgentRuntime)
    assert s.runtime.signal_enabled is True
    world = frame.get("world") or {}
    ids = {f["id"] for f in (world.get("fields_available") or [])}
    assert "FIELD_A" in ids
    assert "FIELD_B" in ids
    mechs = {m["id"]: m.get("enabled") for m in s.runtime.mechanisms().get("mechanisms", [])}
    assert mechs.get("experimental_physical_signal") is True


def test_single_agent_set_mechanism_allocates_signal_fields():
    rt = PhysicalSystemRuntime(seed=7, config=PhysicalSystemConfig())
    rt.set_mechanism("experimental_physical_signal", True)
    assert rt.world.FIELD_A is not None
    assert "FIELD_A" in {f["id"] for f in discover_world_fields(rt)}
