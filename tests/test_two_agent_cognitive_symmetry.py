"""TwoAgentRuntime cognitive symmetry and WAIT-dominance diagnostics."""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.actions import available_actions, apply_physical_action
from mechanistic_mind.physical_system.cognition import run_cognition_before_action
from mechanistic_mind.physical_system.runtime import _rng_unit
from mechanistic_mind.physical_system.two_agent import agent_seed


def test_i_single_agent_tiktaalik_unchanged():
    rt = PhysicalSystemRuntime(seed=17)
    rt.step(8)
    assert rt.tick == 8
    assert rt.last_selected_action in set(available_actions())


def test_a_both_agents_execute_cognition_every_tick():
    ta = TwoAgentRuntime(seed=17)
    n = 40
    ta.step(n)
    for i, rt in enumerate(ta.slots):
        assert ta._agent_stats[i]["cognition_ticks"] == n
        counts = (rt.cognition.get("metrics") or {}).get("action_counts") or {}
        assert sum(int(v) for v in counts.values()) == n


def test_f_mutable_cognition_stores_not_shared():
    ta = TwoAgentRuntime(seed=17)
    a, b = ta.slots
    assert a.cognition is not b.cognition
    assert a.cognition["prospection"] is not b.cognition["prospection"]
    assert a.cognition["compression"] is not b.cognition["compression"]
    assert a.body is not b.body
    assert a.internal is not b.internal
    audit = ta.construction_audit()
    assert audit["shared_world"] is True
    assert audit["shared_cognition_object"] is False
    assert audit["same_architecture_flags"] is True
    assert audit["agent_seeds"] == [17, 18]


def test_d_e_independent_history_and_prospection():
    ta = TwoAgentRuntime(seed=17)
    ta.step(30)
    a, b = ta.slots
    assert len(a.cognition["compression"]["recent"]) > 0
    assert len(b.cognition["compression"]["recent"]) > 0
    # Distinct stores; contents may differ by local experience
    assert a.cognition["compression"]["recent"] is not b.cognition["compression"]["recent"]
    ma = (a.cognition.get("metrics") or {}).get("prospective_compositions", 0)
    mb = (b.cognition.get("metrics") or {}).get("prospective_compositions", 0)
    assert ma > 0 and mb > 0


def test_b_c_forced_move_realizable_on_both():
    """Architecture can select and realize every locomotor action (forced gate)."""
    ta = TwoAgentRuntime(seed=17)
    for act in available_actions():
        if not str(act).startswith("MOVE"):
            continue
        for i, rt in enumerate(ta.slots):
            before = (rt.body.x, rt.body.y, rt.body.vx, rt.body.vy)
            rt._forced_action_once = act
            ta.step(1)
            # Realized action recorded
            assert rt.last_selected_action == act
            # Bridge applied something (Δv or position may change depending on work)
            assert rt.cognition.get("last_apply", {}).get("action") == act


def test_g_observer_selection_does_not_affect_behavior():
    a = TwoAgentRuntime(seed=42)
    b = TwoAgentRuntime(seed=42)
    a.select_agent(0)
    b.select_agent(1)
    for _ in range(25):
        a.step(1)
        b.step(1)
    for i in range(2):
        assert a.slots[i].last_selected_action == b.slots[i].last_selected_action
        assert abs(a.slots[i].body.x - b.slots[i].body.x) < 1e-9
        assert abs(a.slots[i].body.y - b.slots[i].body.y) < 1e-9


def test_h_swapping_observer_labels_alone_noop():
    ta = TwoAgentRuntime(seed=17)
    ta.step(5)
    snap = [(rt.last_selected_action, rt.body.x, rt.body.y) for rt in ta.slots]
    ta.select_agent(1)
    ta.select_agent(0)
    after = [(rt.last_selected_action, rt.body.x, rt.body.y) for rt in ta.slots]
    assert snap == after


def test_independent_seeds_allow_divergent_endogenous_sampling():
    coupled = TwoAgentRuntime(seed=17, independent_agent_seeds=False)
    indep = TwoAgentRuntime(seed=17, independent_agent_seeds=True)
    assert coupled.slots[0].seed == coupled.slots[1].seed == 17
    assert indep.slots[0].seed == 17 and indep.slots[1].seed == 18
    assert agent_seed(17, 0) != agent_seed(17, 1)
    assert _rng_unit(17, 3) != _rng_unit(18, 3)


def test_controlled_equivalence_same_state_same_decision():
    """Matched cognition + observation + rng → identical selection."""
    ta = TwoAgentRuntime(seed=17)
    ta.step(20)
    obs = ta.slots[0].agent_observation()
    state_a = deepcopy(ta.slots[0].cognition)
    state_b = deepcopy(state_a)
    rng = _rng_unit(ta.slots[0].seed, ta.slots[0].tick)
    ra = run_cognition_before_action(state_a, observation=obs, tick=ta.slots[0].tick, rng_value=rng)
    rb = run_cognition_before_action(state_b, observation=obs, tick=ta.slots[0].tick, rng_value=rng)
    assert ra.selected_action == rb.selected_action
    assert ra.selection_source == rb.selection_source


def test_swap_spawn_locations_travel_follows_environment():
    """Immobility/travel pattern is not hard-wired to agent label."""
    base = TwoAgentRuntime(seed=17, starts=((8, 16), (12, 16)))
    swapped = TwoAgentRuntime(seed=17, starts=((12, 16), (8, 16)))
    base.step(80)
    swapped.step(80)
    # Agent at (8,16) start should have similar travel class regardless of slot index
    # Compare distance of whoever started at 8,16
    d_base_at_8 = base._agent_stats[0]["distance_travelled"]
    d_swap_at_8 = swapped._agent_stats[1]["distance_travelled"]
    # Same world seed + mirrored starts → comparable magnitude (not identity)
    ratio = min(d_base_at_8, d_swap_at_8) / max(1e-9, max(d_base_at_8, d_swap_at_8))
    assert ratio > 0.2  # not a hard label lock; environment matters


def test_wait_dominance_is_explained_by_single_supported():
    ta = TwoAgentRuntime(seed=17)
    ta.step(60)
    diag = ta.decision_diagnostics()
    for key in ("agent_0", "agent_1"):
        d = diag[key]
        # After lock-in, WAIT is typically SINGLE_SUPPORTED (documented mechanism)
        if d["selected_action"] == "WAIT" and d.get("outcome_class") == "SINGLE_SUPPORTED":
            assert d["supported_actions"] == ["WAIT"]
            assert set(d["unsupported_actions"] or []) >= {"MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"}
