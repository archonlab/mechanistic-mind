"""Forensic regression: TwoAgentRuntime mechanism / cognition architectural parity.

Architectural parity ≠ behavioral equality. Different seeds/observations/histories
may diverge; enabled mechanism sets and configs must not.
"""
from __future__ import annotations

from copy import deepcopy

from mechanistic_mind.model.tiktaalik import tiktaalik_config
from mechanistic_mind.physical_system import PhysicalSystemRuntime, TwoAgentRuntime
from mechanistic_mind.physical_system.cognition import run_cognition_before_action
from mechanistic_mind.physical_system.mechanism_registry import MECHANISM_DEFS, mechanism_snapshot
from mechanistic_mind.physical_system.runtime import _rng_unit
from mechanistic_mind.ui.psy_observer_web.serialize import collect_observer_events, enrich_structured_event


def _tik_two(*, seed: int = 143, starts=((3, 6), (8, 6))) -> TwoAgentRuntime:
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = True
    cfg.planet.width = 12
    cfg.planet.height = 12
    return TwoAgentRuntime(seed=seed, config=cfg, starts=starts)


def test_mechanism_set_parity_at_construction():
    ta = _tik_two()
    audit = ta.construction_audit()
    assert audit["same_architecture_flags"] is True
    assert audit["shared_cognition_object"] is False
    assert audit["agent_seeds"] == [143, 144]
    s0 = mechanism_snapshot(ta.slots[0].config)
    s1 = mechanism_snapshot(ta.slots[1].config)
    assert len(s0["mechanisms"]) == len(MECHANISM_DEFS)
    for a, b in zip(s0["mechanisms"], s1["mechanisms"]):
        assert a["id"] == b["id"]
        assert a.get("enabled") == b.get("enabled"), a["id"]
    parity = ta.mechanism_parity_audit()
    assert parity["cognition_config_equal"] is True
    assert parity["mechanism_mismatches"] == []


def test_mechanism_configuration_parity_except_identity():
    ta = _tik_two()
    c0 = ta.slots[0].config.cognition.to_dict()
    c1 = ta.slots[1].config.cognition.to_dict()
    assert c0 == c1
    # Intentional identity-only diffs
    assert ta.slots[0].seed != ta.slots[1].seed
    assert (ta.slots[0].config.body.start_x, ta.slots[0].config.body.start_y) != (
        ta.slots[1].config.body.start_x,
        ta.slots[1].config.body.start_y,
    )
    assert ta.slots[0].config.cognition is not ta.slots[1].config.cognition


def test_independent_mutable_cognition_stores():
    ta = _tik_two()
    ta.step(15)
    a, b = ta.slots
    assert a.cognition is not b.cognition
    assert a.cognition["compression"] is not b.cognition["compression"]
    assert a.cognition["prospection"] is not b.cognition["prospection"]
    assert a.cognition["multiscale"] is not b.cognition["multiscale"]
    assert a.cognition.get("instrumental") is not b.cognition.get("instrumental")
    assert a.structured_events is not b.structured_events
    assert a.body is not b.body
    assert a.internal is not b.internal
    # Mutating one store must not affect the other
    a.cognition["metrics"]["prospective_compositions"] = -999
    assert b.cognition["metrics"].get("prospective_compositions") != -999


def test_both_agents_execute_cognition_and_prospection():
    ta = _tik_two()
    n = 40
    ta.step(n)
    for i, rt in enumerate(ta.slots):
        assert ta._agent_stats[i]["cognition_ticks"] == n
        metrics = rt.cognition.get("metrics") or {}
        assert int(metrics.get("prospective_compositions") or 0) > 0
        counts = metrics.get("action_counts") or {}
        assert sum(int(v) for v in counts.values()) == n
        sel = rt.cognition.get("last_selection") or {}
        assert sel.get("source")  # cognition produced a selection record


def test_both_agents_can_produce_cognition_structured_events():
    """SCENARIO_SELECTED is gated on non-WAIT; DISCRETE_ACTION_SELECTED always records."""
    ta = _tik_two()
    ta.step(30)
    for i, rt in enumerate(ta.slots):
        types = {e.get("type") for e in rt.structured_events.list(limit=500)}
        assert "DISCRETE_ACTION_SELECTED" in types, f"agent_{i} missing action events"
        # Cognition executed even if SCENARIO_SELECTED absent under WAIT lock-in
        assert ta._agent_stats[i]["cognition_ticks"] == 30


def test_agent_1_events_survive_serialization_with_identity():
    ta = _tik_two()
    ta.step(20)
    events = collect_observer_events(ta, limit=500)
    by_agent = {}
    for e in events:
        aid = e.get("agent_id") or e.get("actor_agent_id")
        by_agent.setdefault(aid, 0)
        by_agent[aid] += 1
    assert by_agent.get("agent_0", 0) > 0
    assert by_agent.get("agent_1", 0) > 0
    # Enrichment stamps buffer owner
    raw = dict(ta.slots[1].structured_events.list(limit=1)[0])
    enriched = enrich_structured_event(raw, agent_id="agent_1", body_id="body-1")
    assert enriched["agent_id"] == "agent_1"
    assert enriched["actor_agent_id"] == "agent_1"


def test_experiment_toggle_applies_to_both_agents_regardless_of_selection():
    ta = _tik_two()
    assert ta.slots[0].config.cognition.prospective_composition is True
    assert ta.slots[1].config.cognition.prospective_composition is True

    ta.select_agent(0)
    ta.set_mechanism("prospective_composition", False)
    assert ta.slots[0].config.cognition.prospective_composition is False
    assert ta.slots[1].config.cognition.prospective_composition is False

    ta.select_agent(1)
    ta.set_mechanism("prospective_composition", True)
    assert ta.slots[0].config.cognition.prospective_composition is True
    assert ta.slots[1].config.cognition.prospective_composition is True

    ta.set_mechanism("predictive_conflict", True)
    assert ta.slots[0].config.cognition.predictive_conflict is True
    assert ta.slots[1].config.cognition.predictive_conflict is True
    assert ta.mechanism_parity_audit()["mechanism_mismatches"] == []


def test_reset_preserves_parity():
    ta = _tik_two()
    ta.set_mechanism("instrumental_observation", False)
    ta.reset()
    # reset rebuilds from base_config — live toggle is not in base_config
    # Parity between slots must still hold after reset
    assert ta.slots[0].config.cognition.to_dict() == ta.slots[1].config.cognition.to_dict()
    assert ta.construction_audit()["same_architecture_flags"] is True


def test_snapshot_restore_preserves_parity():
    ta = _tik_two()
    ta.set_mechanism("predictive_conflict", True)
    ta.step(12)
    rest = TwoAgentRuntime.restore(ta.snapshot())
    assert rest.slots[0].seed == 143 and rest.slots[1].seed == 144
    assert rest.slots[0].config.cognition.to_dict() == rest.slots[1].config.cognition.to_dict()
    assert rest.slots[0].cognition is not rest.slots[1].cognition
    assert rest.slots[0].world is rest.slots[1].world
    assert rest.slots[0].config.cognition.predictive_conflict is True
    assert rest.slots[1].config.cognition.predictive_conflict is True


def test_controlled_execution_parity_matched_state():
    """Same observation + cognition state + rng → same selection (execution parity)."""
    ta = _tik_two()
    ta.step(10)
    obs = ta.slots[0].agent_observation()
    state_a = deepcopy(ta.slots[0].cognition)
    state_b = deepcopy(state_a)
    rng = _rng_unit(ta.slots[0].seed, ta.slots[0].tick)
    ra = run_cognition_before_action(state_a, observation=obs, tick=ta.slots[0].tick, rng_value=rng)
    rb = run_cognition_before_action(state_b, observation=obs, tick=ta.slots[0].tick, rng_value=rng)
    assert ra.selected_action == rb.selected_action
    assert ra.selection_source == rb.selection_source


def test_same_seed_label_still_two_independent_slots():
    """Independent seeds off → same seed value, still independent minds."""
    cfg = tiktaalik_config()
    cfg.cognition.cognition_enabled = True
    ta = TwoAgentRuntime(seed=143, config=cfg, independent_agent_seeds=False)
    assert ta.slots[0].seed == ta.slots[1].seed == 143
    assert ta.slots[0].cognition is not ta.slots[1].cognition
    assert ta.slots[0].config.cognition.to_dict() == ta.slots[1].config.cognition.to_dict()


def test_single_agent_unchanged():
    rt = PhysicalSystemRuntime(seed=17, model="tiktaalik")
    rt.step(5)
    assert rt.tick == 5
    assert rt.config.cognition.cognition_enabled is True


def test_forensic_seed_143_both_process_cognition():
    """Seed 143/144 diagnostic: both execute cognition; behavior may diverge."""
    ta = _tik_two(seed=143)
    n = 80
    ta.step(n)
    reports = []
    for i, rt in enumerate(ta.slots):
        metrics = rt.cognition.get("metrics") or {}
        counts = dict(metrics.get("action_counts") or {})
        reports.append({
            "agent": f"agent_{i}",
            "seed": rt.seed,
            "cognition_ticks": ta._agent_stats[i]["cognition_ticks"],
            "prospective_compositions": metrics.get("prospective_compositions"),
            "prediction_count": metrics.get("prediction_count"),
            "wait": int(counts.get("WAIT") or 0),
            "move": sum(int(v) for k, v in counts.items() if str(k).startswith("MOVE")),
        })
    assert reports[0]["cognition_ticks"] == n
    assert reports[1]["cognition_ticks"] == n
    assert reports[0]["prospective_compositions"] > 0
    assert reports[1]["prospective_compositions"] > 0
    assert reports[0]["seed"] == 143 and reports[1]["seed"] == 144
