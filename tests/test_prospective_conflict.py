from copy import deepcopy

from mechanistic_mind.research.persistent_prospective_trace import advance_trace, create_trace
from mechanistic_mind.research.prospective_conflict import compare_trace_sets


def st(e):
    return {"energy_signal": e, "hydration_signal": 0.6, "fatigue_signal": 0.1}


def old_trace(prediction=0.4, *, counter=1, tick=10, action="MOVE:1,0", horizon=1):
    trace = create_trace(
        counter=counter, created_tick=tick, origin_state_key="S0", origin_signals=st(0.2),
        branches=[{"edges": [
            {"action": "USE:x", "horizon": 1, "predicted_state": st(0.3), "provenance": "DIRECT"},
            {"action": action, "horizon": horizon, "predicted_state": st(prediction), "provenance": "COMPOSED"},
        ]}],
    )
    return advance_trace(trace, tick=tick + 1, realized_state=st(0.3), actual_action="USE:x")


def fresh_trace(prediction=0.4, *, counter=2, tick=11, action="MOVE:1,0", horizon=1):
    return create_trace(
        counter=counter, created_tick=tick, origin_state_key="S1", origin_signals=st(0.3),
        branches=[{"edges": [{"action": action, "horizon": horizon, "predicted_state": st(prediction),
                                "provenance": "DIRECT"}]}],
    )


def test_agreement_and_conflict_require_comparable_temporally_distinct_predictions():
    old = old_trace()
    agreement = compare_trace_sets(old, fresh_trace())
    assert agreement["relation"] == "AGREEMENT"
    assert agreement["PROSPECTIVE_CONFLICT"] == "ABSENT"
    assert agreement["temporally_distinct_provenance"] is True

    conflict = compare_trace_sets(old, fresh_trace(0.7))
    assert conflict["relation"] == "INCOMPATIBLE"
    assert conflict["PROSPECTIVE_CONFLICT"] == "PRESENT"
    pair = conflict["incompatible_pairs"][0]
    assert pair["comparison_action"] == "MOVE"
    assert pair["comparison_horizon"] == 1
    assert pair["absolute_L1"] > pair["compatibility_threshold"]


def test_unknown_and_not_comparable_are_not_conflict():
    old = old_trace()
    assert compare_trace_sets(old, None)["relation"] == "FRESH_UNKNOWN"
    assert compare_trace_sets(None, fresh_trace())["relation"] == "OLD_UNKNOWN"
    different_action = compare_trace_sets(old, fresh_trace(0.7, action="WAIT"))
    assert different_action["relation"] == "NOT_COMPARABLE"
    assert different_action["PROSPECTIVE_CONFLICT"] == "ABSENT"
    different_horizon = compare_trace_sets(old, fresh_trace(0.7, horizon=2))
    assert different_horizon["relation"] == "NOT_COMPARABLE"


def test_branch_overlap_prevents_false_conflict_and_comparison_does_not_mutate_or_average():
    old = old_trace()
    fresh = create_trace(
        counter=3, created_tick=11, origin_state_key="S1", origin_signals=st(0.3),
        branches=[
            {"consequence_group_id": "P", "edges": [{"action": "MOVE:1,0", "predicted_state": st(0.4), "provenance": "DIRECT"}]},
            {"consequence_group_id": "Q", "edges": [{"action": "MOVE:1,0", "predicted_state": st(0.7), "provenance": "DIRECT"}]},
        ],
    )
    old_before, fresh_before = deepcopy(old), deepcopy(fresh)
    result = compare_trace_sets(old, fresh)
    assert result["relation"] == "OVERLAP"
    assert result["PROSPECTIVE_CONFLICT"] == "ABSENT"
    assert result["averaged_prediction"] is None
    assert result["resolution"] is None
    assert old == old_before and fresh == fresh_before
    assert result["cognition_visible_relation"] is False
    assert result["policy_coupling"] == "ABSENT"
