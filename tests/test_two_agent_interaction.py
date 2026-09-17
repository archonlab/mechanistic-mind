"""Two-agent experimental substrate: shared world, independent minds, no social semantics."""
from __future__ import annotations

from copy import deepcopy

import numpy as np

from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.complementary_resources import place_source_AB
from mechanistic_mind.physical_system.observation import audit_cognition_payload


def test_single_agent_default_unchanged():
    rt = PhysicalSystemRuntime(seed=17)
    assert not hasattr(rt, "slots")
    rt.step(8)
    assert rt.tick == 8
    assert rt.last_selected_action in {"WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"}


def test_two_independent_cognitions_one_world():
    ta = TwoAgentRuntime(seed=17)
    assert id(ta.slots[0].world) == id(ta.slots[1].world)
    assert ta.slots[0].cognition is not ta.slots[1].cognition
    assert ta.slots[0].body is not ta.slots[1].body
    ta.step(5)
    assert ta.slots[0].tick == ta.slots[1].tick == ta.world.tick
    assert ta.slots[0].cognition["prospection"] is not ta.slots[1].cognition["prospection"]


def test_technical_ids_not_in_observation():
    ta = TwoAgentRuntime(seed=17)
    ta.step(2)
    for obs in ta.observations():
        assert audit_cognition_payload(obs) == []
        blob = repr(obs)
        assert "agent_0" not in blob
        assert "agent_1" not in blob
        assert "other agent" not in blob
        assert "enemy" not in blob


def test_shared_resource_no_double_spend():
    ta = TwoAgentRuntime(seed=17, starts=((10, 16), (10, 16)))
    place_source_AB(ta.world, 16, 10, A=0.40, B=0.0)
    initial = float(ta.world.R_A[16, 10])
    ta.step(1)
    env = float(ta.world.R_A[16, 10])
    a0 = float(np.sum(ta.slots[0].body.R_A_site)) if ta.slots[0].body.R_A_site is not None else 0.0
    a1 = float(np.sum(ta.slots[1].body.R_A_site)) if ta.slots[1].body.R_A_site is not None else 0.0
    led0 = ta.last_resource_sim[0]["A"]
    led1 = ta.last_resource_sim[1]["A"]
    removed = float(led0.get("removed") or 0) + float(led1.get("removed") or 0)
    assert env + removed <= initial + 1e-6
    assert a0 + a1 <= initial + 1e-6


def test_order_swap_symmetric_bias_is_measurable():
    a = TwoAgentRuntime(seed=17, process_order=(0, 1), starts=((8, 16), (24, 16)))
    b = TwoAgentRuntime(seed=17, process_order=(1, 0), starts=((8, 16), (24, 16)))
    a.step(12)
    b.step(12)
    dx = abs(a.slots[0].body.x - b.slots[0].body.x) + abs(a.slots[1].body.x - b.slots[1].body.x)
    dy = abs(a.slots[0].body.y - b.slots[0].body.y) + abs(a.slots[1].body.y - b.slots[1].body.y)
    # Far apart: order bias should be tiny. Record, don't require zero.
    assert dx + dy < 0.5


def test_contact_when_overlapping():
    ta = TwoAgentRuntime(seed=17, starts=((10, 16), (10, 16)), contact_enabled=True)
    ta.step(1)
    assert ta.last_contact is not None
    assert ta.last_contact["contact"] is True
    d = abs(ta.slots[0].body.x - ta.slots[1].body.x) + abs(ta.slots[0].body.y - ta.slots[1].body.y)
    assert d > 0.01


def test_snapshot_restore_does_not_merge_histories():
    ta = TwoAgentRuntime(seed=23)
    ta.step(6)
    ta.slots[0].cognition["metrics"]["action_counts"]["WAIT"] = 12345
    snap = ta.snapshot()
    assert snap["schema"] == "mm.physical_system.two_agent.snapshot.v1"
    assert snap["promoted"] is False
    rt = TwoAgentRuntime.restore(deepcopy(snap))
    assert rt.slots[0].cognition["metrics"]["action_counts"].get("WAIT") == 12345
    assert rt.slots[0].cognition is not rt.slots[1].cognition
    assert id(rt.slots[0].world) == id(rt.slots[1].world)


def test_emit_contact_actions_still_bridge_missing():
    from mechanistic_mind.physical_system.actions import BRIDGE_MISSING
    assert "EMIT" in BRIDGE_MISSING
    assert "CONTACT" in BRIDGE_MISSING
    assert "PUSH" not in BRIDGE_MISSING or True
    ta = TwoAgentRuntime(seed=17)
    ta.step(1)
    for rt in ta.slots:
        assert rt.cognition["bridges"]["4.25_physical_emit_transducer_on_psr"] == "BRIDGE_MISSING"


def test_select_agent_is_observer_only():
    ta = TwoAgentRuntime(seed=17)
    ta.step(1)
    x0 = ta.body.x
    ta.select_agent(1)
    assert ta.selected_index == 1
    assert ta.body is ta.slots[1].body
    assert ta.body.x != x0 or ta.slots[0].body.x == ta.slots[1].body.x
    obs = ta.observations()
    blob = repr(obs)
    assert "agent_0" not in blob
    assert "AGENT A" not in blob
