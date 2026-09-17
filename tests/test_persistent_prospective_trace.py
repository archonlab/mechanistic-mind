from copy import deepcopy

from mechanistic_mind.research.persistent_prospective_trace import (
    ACTION_DIVERGED,
    ACTIVE,
    COMPLETED,
    DIVERGED,
    MAX_BRANCHES_PER_TRACE,
    MAX_EDGES_PER_BRANCH,
    advance_trace,
    create_trace,
    retained_tail,
)


def state(e, h=0.5, f=0.1):
    return {"energy_signal": e, "hydration_signal": h, "fatigue_signal": f}


def chain(counter=1, tick=10):
    return create_trace(
        counter=counter,
        created_tick=tick,
        origin_state_key="S0",
        origin_signals=state(0.2),
        branches=[
            {
                "edges": [
                    {"action": "USE:x", "horizon": 1, "predicted_state": state(0.3), "provenance": "DIRECT"},
                    {"action": "MOVE:1,0", "horizon": 1, "predicted_state": state(0.4), "provenance": "COMPOSED"},
                    {"action": "WAIT", "horizon": 1, "predicted_state": state(0.5), "provenance": "COMPOSED"},
                ]
            }
        ],
    )


def test_same_trace_and_frozen_provenance_survive_two_partial_realizations():
    original = chain()
    frozen_nodes = deepcopy(original["branches"][0]["nodes"])
    t1 = advance_trace(original, tick=11, realized_state=state(0.3), actual_action="USE:x")
    assert t1["status"] == ACTIVE
    assert t1["trace_id"] == original["trace_id"]
    assert t1["created_tick"] == 10
    assert [n["prediction_created_tick"] for n in retained_tail(t1)] == [10, 10]
    assert retained_tail(t1)[0]["predicted_state"] == frozen_nodes[1]["predicted_state"]
    assert retained_tail(t1)[0]["provenance"] == "COMPOSED"

    t2 = advance_trace(t1, tick=12, realized_state=state(0.4), actual_action="MOVE:1,0")
    assert t2["trace_id"] == original["trace_id"]
    assert [n["prediction_created_tick"] for n in retained_tail(t2)] == [10]
    assert retained_tail(t2)[0]["predicted_state"] == frozen_nodes[2]["predicted_state"]


def test_reconstruction_ablation_cannot_destroy_old_tail_and_old_ablation_does_not_destroy_evidence():
    acquired = {"S0|USE:x": [state(0.3)], "S1|MOVE:1,0": [state(0.4)]}
    old = chain()
    reconstruction_enabled = False
    advanced = advance_trace(old, tick=11, realized_state=state(0.3), actual_action="USE:x")
    fresh = None if not reconstruction_enabled else chain(counter=2, tick=11)
    assert fresh is None
    assert len(retained_tail(advanced)) == 2

    old = None
    assert acquired["S1|MOVE:1,0"]
    reconstructed = create_trace(
        counter=2, created_tick=11, origin_state_key="S1", origin_signals=state(0.3),
        branches=[{"edges": [{"action": "MOVE:1,0", "predicted_state": acquired["S1|MOVE:1,0"][0], "provenance": "DIRECT"}]}],
    )
    assert old is None
    assert reconstructed["trace_id"] == "PPT-000002"
    assert reconstructed["created_tick"] == 11


def test_completion_state_mismatch_and_action_divergence_are_neutral_lifecycle_results():
    tr = chain()
    tr = advance_trace(tr, tick=11, realized_state=state(0.3), actual_action="USE:x")
    tr = advance_trace(tr, tick=12, realized_state=state(0.4), actual_action="MOVE:1,0")
    tr = advance_trace(tr, tick=13, realized_state=state(0.5), actual_action="WAIT")
    assert tr["status"] == COMPLETED
    assert retained_tail(tr) == []

    mismatch = advance_trace(chain(), tick=11, realized_state=state(0.9), actual_action="USE:x")
    assert mismatch["status"] == DIVERGED
    assert mismatch["branches"][0]["nodes"][0]["compatibility"] == "NEXT_EDGE_INCOMPATIBLE"

    action = advance_trace(chain(), tick=11, realized_state=state(0.3), actual_action="WAIT")
    assert action["status"] == ACTION_DIVERGED
    assert action["branches"][0]["nodes"][0]["actual_action"] == "WAIT"


def test_multi_consequence_resolution_preserves_acquired_alternative_and_bounds():
    acquired = {"S0|USE:x": {"C1": state(0.3), "C2": state(0.7)}}
    branches = [
        {"consequence_group_id": cid, "edges": [{"action": "USE:x", "predicted_state": predicted,
          "provenance": "DIRECT", "consequence_group_id": cid}]}
        for cid, predicted in acquired["S0|USE:x"].items()
    ]
    tr = create_trace(counter=8, created_tick=20, origin_state_key="S0", origin_signals=state(0.2), branches=branches)
    x = advance_trace(tr, tick=21, realized_state=state(0.3), actual_action="USE:x")
    by_group = {b["consequence_group_id"]: b["status"] for b in x["branches"]}
    assert by_group == {"C1": "COMPLETED", "C2": "REALIZED_INCOMPATIBLE"}
    assert set(acquired["S0|USE:x"]) == {"C1", "C2"}

    oversized = create_trace(
        counter=9, created_tick=30, origin_state_key="S0", origin_signals=state(0.2),
        branches=[{"edges": [{"action": "WAIT", "predicted_state": state(0.2 + i / 100 + j / 1000)}
                              for j in range(8)]} for i in range(8)],
    )
    assert len(oversized["branches"]) == MAX_BRANCHES_PER_TRACE
    assert all(len(b["nodes"]) == MAX_EDGES_PER_BRANCH for b in oversized["branches"])
    assert oversized["policy_coupled"] is False
    assert oversized["value_coupled"] is False
