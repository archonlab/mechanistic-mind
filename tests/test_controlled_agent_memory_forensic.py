"""Bounded controlled-agent spawn/remove memory forensic (no 15 GB reproduction)."""
from __future__ import annotations

from mechanistic_mind.physical_system.runtime import PhysicalSystemRuntime
from mechanistic_mind.physical_system.two_agent import TwoAgentRuntime
from mechanistic_mind.ui.psy_observer_web.experimenter_control import (
    ExperimenterController,
    promote_physical_to_two_agent_host,
    remove_experimenter_body,
    spawn_experimenter_body,
)
from mechanistic_mind.ui.psy_observer_web.session import FULL_PUBLIC_FRAME_RETAIN

from experiments.run_controlled_agent_memory_forensic import (
    _cog_ids,
    _count_psr,
    run_cycles,
    run_observer_cycles,
    run_promotion_cases,
)


def test_frame_cap_still_one():
    assert FULL_PUBLIC_FRAME_RETAIN == 1


def test_ten_spawn_remove_cycles_stable():
    r = run_cycles(10, ticks=2)
    assert r["n_agents_end"] == 2
    assert r["duplicate_cognition"] is False
    assert r["n_psr_end"] <= r["n_psr_start"] + 1
    assert r["classification"] in ("STABLE", "ALLOCATOR_RETENTION")
    assert r["rss_delta_per_cycle_mb"] < 8.0


def test_fifty_spawn_remove_cycles_bounded():
    r = run_cycles(50, ticks=2)
    assert r["classification"] in ("STABLE", "ALLOCATOR_RETENTION")
    assert r["duplicate_cognition"] is False
    assert r["n_psr_end"] <= r["n_psr_start"] + 2
    assert abs(r["rss_delta_per_cycle_mb"]) < 5.0 or r["classification"] == "ALLOCATOR_RETENTION"


def test_promotion_preserves_cognition_and_does_not_demote():
    p = run_promotion_cases()
    assert p["A"]["same_cognition"] is True
    assert p["A"]["same_body"] is True
    assert p["A"]["runtime_after_remove"] == "TwoAgentRuntime"
    assert p["A"]["n_slots"] == 1
    assert p["C"]["n_slots_second_spawn"] == 3
    # two-agent start: spawn → 3, remove → 2, spawn → 3
    assert p["D"]["n_slots"] == 2


def test_observer_spawn_remove_does_not_grow_frame_ring():
    r = run_observer_cycles(8, eye=False)
    assert r["full_frames_retained"] <= 1
    assert r["controller_active"] is False
    assert r["n_agents"] == 2
    assert r["rss_delta_per_cycle_mb"] < 15.0


def test_direct_ownership_returns():
    rt = TwoAgentRuntime(seed=3)
    psr0 = _count_psr()
    cog = _cog_ids(rt)
    c = ExperimenterController()
    spawn_experimenter_body(rt, x=5, y=5, controller=c)
    assert len(rt.slots) == 3
    assert _count_psr() >= psr0 + 1
    remove_experimenter_body(rt, c)
    assert len(rt.slots) == 2
    assert rt.experimenter_slot is None
    assert _cog_ids(rt) == cog
    import gc

    gc.collect()
    assert _count_psr() <= psr0 + 1


def test_promote_discards_constructor_slots():
    psr = PhysicalSystemRuntime(seed=9)
    host = promote_physical_to_two_agent_host(psr)
    assert host.slots == [psr]
    c = ExperimenterController()
    spawn_experimenter_body(host, x=4, y=4, controller=c)
    remove_experimenter_body(host, c)
    assert host.slots[0] is psr
