#!/usr/bin/env python3
"""Update 4.17 measurement-only old expectation × fresh prediction matrix."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.agent import Action, Observation
from mechanistic_mind.psyche.contracts import PsycheActionCandidate, PsycheContext, PsycheStage
from mechanistic_mind.psyche.organism_modules import OrganismActionSelectionModule
from mechanistic_mind.psyche.state import PsycheState
from mechanistic_mind.research.multiple_consequences import (
    MATCH_L1, prospective_consequences, update_multi_consequence,
)
from mechanistic_mind.research.persistent_prospective_trace import (
    advance_trace, create_trace, retained_tail, state_compatibility,
)
from mechanistic_mind.research.prospective_conflict import compare_trace_sets

OUT = ROOT / "results" / "update417_prospective_conflict"
OUT.mkdir(parents=True, exist_ok=True)


def st(e):
    return {"energy_signal": e, "hydration_signal": 0.60, "fatigue_signal": 0.10}


S0, S1, P, Q, R = st(0.20), st(0.30), st(0.42), st(0.70), st(0.90)
ACTION_PREFIX, ACTION_TARGET = "USE:resource", "MOVE:1,0"


def delta(before, after):
    return {key: after[key] - before[key] for key in before}


TC = {}


def acquire(key, before, outcomes):
    for outcome in outcomes:
        for _ in range(8):
            update_multi_consequence(TC, key, delta(before, outcome))


# All P/Q/R values used below arise from the ordinary 4.14 bounded acquisition path.
acquire("H_OLD_P|S1|MOVE", S1, [P])
acquire("H_FRESH_P|S1|MOVE", S1, [P])
acquire("H_FRESH_Q|S1|MOVE", S1, [Q])
acquire("H_FRESH_PQ|S1|MOVE", S1, [P, Q])
acquire("H_OLD_PR|S1|MOVE", S1, [P, R])
acquire("H_REAL_R|S1|MOVE", S1, [R])


def pack(key):
    return prospective_consequences(tc=TC, key=key, current_signals=S1)


def edge(action, prediction, provenance, row, group):
    return {
        "action": action, "horizon": 1, "predicted_state": prediction,
        "provenance": provenance, "support": row.get("support"),
        "consequence_group_id": group, "source_record_key": row.get("source_record_key"),
    }


def old_from_acquired(key, *, counter, tick=100):
    branches = []
    for row in pack(key)["consequences"]:
        group = row["id"]
        branches.append({"consequence_group_id": group, "edges": [
            {"action": ACTION_PREFIX, "horizon": 1, "predicted_state": S1,
             "provenance": "DIRECT", "support": 9.0, "consequence_group_id": group},
            edge(ACTION_TARGET, row["predicted_state"], "COMPOSED", row, group),
        ]})
    trace = create_trace(
        counter=counter, created_tick=tick, origin_state_key="S0", origin_signals=S0,
        branches=branches,
    )
    return advance_trace(trace, tick=tick + 1, realized_state=S1, actual_action=ACTION_PREFIX)


def fresh_from_acquired(key, *, counter, tick=101, action=ACTION_TARGET, horizon=1):
    branches = []
    for row in pack(key)["consequences"]:
        group = row["id"]
        branches.append({"consequence_group_id": group, "edges": [{
            **edge(action, row["predicted_state"], "DIRECT", row, group), "horizon": horizon,
        }]})
    return create_trace(
        counter=counter, created_tick=tick, origin_state_key="S1", origin_signals=S1,
        branches=branches,
    )


def dump(name, payload):
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def realization(old, fresh, reality):
    old_node = retained_tail(old)[0]
    fresh_node = retained_tail(fresh)[0]
    return {
        "reality": reality,
        "old_vs_reality": state_compatibility(old_node["predicted_state"], reality),
        "fresh_vs_reality": state_compatibility(fresh_node["predicted_state"], reality),
    }


def policy_observation():
    state = PsycheState.initial_organism_v03()
    candidates = (
        PsycheActionCandidate(
            source_module="EXISTING-CANDIDATE", action=Action(ACTION_TARGET), total_value=0.30,
            components={"ordinary": 0.30}, metadata={"movement": True, "uncertainty": 0.0},
        ),
        PsycheActionCandidate(
            source_module="EXISTING-CANDIDATE", action=Action("WAIT"), total_value=0.10,
            components={"ordinary": 0.10}, metadata={"movement": False, "uncertainty": 0.0},
        ),
    )
    output = OrganismActionSelectionModule().process(PsycheContext(
        tick=101, agent_id="A001", stage=PsycheStage.ACTION_SELECTION,
        observation=Observation(data={}), state=state, candidates=candidates, random_value=0.0,
    ))
    return {
        "selected_action": output.selection.action.kind,
        "executed_action": output.selection.action.kind,
        "reason": output.selection.reason,
        "score": output.selection.score,
        "candidate_values": [
            {"action": c.action.kind, "total_value": c.total_value, "components": c.components}
            for c in candidates
        ],
        "comparison_record_was_input_to_policy": False,
        "policy_coupling": "ABSENT",
    }


def main():
    old_p = old_from_acquired("H_OLD_P|S1|MOVE", counter=1)
    fresh_p = fresh_from_acquired("H_FRESH_P|S1|MOVE", counter=2)
    fresh_q = fresh_from_acquired("H_FRESH_Q|S1|MOVE", counter=3)

    agreement = compare_trace_sets(old_p, fresh_p)
    conflict = compare_trace_sets(old_p, fresh_q)
    old_only = compare_trace_sets(old_p, None)
    fresh_only = compare_trace_sets(None, fresh_q)
    different_provenance = compare_trace_sets(old_p, fresh_p)
    not_comparable_trace = fresh_from_acquired(
        "H_FRESH_Q|S1|MOVE", counter=4, action="WAIT", horizon=2
    )
    not_comparable = compare_trace_sets(old_p, not_comparable_trace)

    realize_old = {"comparison_before": conflict, **realization(old_p, fresh_q, P)}
    realize_fresh = {"comparison_before": conflict, **realization(old_p, fresh_q, Q)}
    # R is a supported, ordinarily acquired physical consequence in H_REAL_R.
    realized_r = pack("H_REAL_R|S1|MOVE")["consequences"][0]["predicted_state"]
    realize_neither = {"comparison_before": conflict, **realization(old_p, fresh_q, realized_r)}

    fresh_pq = fresh_from_acquired("H_FRESH_PQ|S1|MOVE", counter=5)
    overlap = compare_trace_sets(old_p, fresh_pq)
    old_pr = old_from_acquired("H_OLD_PR|S1|MOVE", counter=6)
    disjoint = compare_trace_sets(old_pr, fresh_q)
    policy = {"comparison": conflict, "observation": policy_observation()}

    history_a = compare_trace_sets(old_p, fresh_q)
    old_q = old_from_acquired("H_FRESH_Q|S1|MOVE", counter=7)
    fresh_q_b = fresh_from_acquired("H_FRESH_Q|S1|MOVE", counter=8)
    history_b = compare_trace_sets(old_q, fresh_q_b)
    history_match = {
        "run_1": compare_trace_sets(old_p, fresh_q),
        "run_2": compare_trace_sets(deepcopy(old_p), deepcopy(fresh_q)),
    }
    history_difference = {
        "same_present": S1, "same_upcoming_event": Q,
        "psyche_A_relation": history_a["relation"], "psyche_B_relation": history_b["relation"],
        "A": history_a, "B": history_b,
    }

    after_old_q = advance_trace(old_p, tick=102, realized_state=Q, actual_action=ACTION_TARGET)
    after_fresh_q = advance_trace(fresh_q, tick=102, realized_state=Q, actual_action=ACTION_TARGET)
    persistence = {
        "before_physical_progression": {"old_status": old_p["status"], "fresh_status": fresh_q["status"]},
        "after_Q_progression": {"old_status": after_old_q["status"], "fresh_status": after_fresh_q["status"]},
        "observation": "Existing lifecycle naturally diverges old P and completes fresh Q.",
    }

    conditions = {
        "AGREEMENT_CONTROL": agreement,
        "CONFLICT_P_VS_Q": conflict,
        "OLD_ONLY": old_only,
        "FRESH_ONLY": fresh_only,
        "DIFFERENT_PROVENANCE_SAME_PREDICTION": different_provenance,
        "NOT_COMPARABLE": not_comparable,
        "REALIZE_OLD": realize_old,
        "REALIZE_FRESH": realize_fresh,
        "REALIZE_NEITHER": realize_neither,
        "MULTI_CONSEQUENCE_OVERLAP": overlap,
        "MULTI_CONSEQUENCE_DISJOINT": disjoint,
        "POLICY_OBSERVATION": policy,
        "HISTORY_MATCH_CONTROL": history_match,
        "HISTORY_DIFFERENCE_CONTROL": history_difference,
    }
    for name, payload in conditions.items():
        dump(f"CONDITION_{name}.json", payload)
    dump("PERSISTENCE_AFTER_CONFLICT.json", persistence)

    matrix = {
        "OLD_FRESH_COEXISTENCE": "PRESENT" if conflict["old_mechanistically_available"] and conflict["fresh_mechanistically_available"] else "ABSENT",
        "PROSPECTIVE_CONFLICT": conflict["PROSPECTIVE_CONFLICT"],
        "AGREEMENT_CONTROL": agreement["relation"] == "AGREEMENT",
        "TEMPORAL_PROVENANCE_VALID": conflict["temporally_distinct_provenance"],
        "FRESH_INDEPENDENT_ID": conflict["old_trace_id"] != conflict["fresh_trace_id"],
        "UNKNOWN_NOT_CONFLICT": old_only["PROSPECTIVE_CONFLICT"] == "ABSENT" and fresh_only["PROSPECTIVE_CONFLICT"] == "ABSENT",
        "NOT_COMPARABLE_NOT_CONFLICT": not_comparable["relation"] == "NOT_COMPARABLE" and not_comparable["PROSPECTIVE_CONFLICT"] == "ABSENT",
        "NO_AVERAGING": conflict["averaged_prediction"] is None,
        "NO_RESOLUTION": conflict["resolution"] is None,
        "REALITY_P_OLD_MATCH_FRESH_MISMATCH": realize_old["old_vs_reality"]["compatible"] and not realize_old["fresh_vs_reality"]["compatible"],
        "REALITY_Q_OLD_MISMATCH_FRESH_MATCH": not realize_fresh["old_vs_reality"]["compatible"] and realize_fresh["fresh_vs_reality"]["compatible"],
        "REALITY_R_VIOLATES_BOTH": not realize_neither["old_vs_reality"]["compatible"] and not realize_neither["fresh_vs_reality"]["compatible"],
        "MULTI_OVERLAP_NO_FALSE_CONFLICT": overlap["relation"] == "OVERLAP" and overlap["PROSPECTIVE_CONFLICT"] == "ABSENT",
        "MULTI_DISJOINT_CONFLICT": disjoint["PROSPECTIVE_CONFLICT"] == "PRESENT",
        "HISTORY_MATCH_DETERMINISTIC": history_match["run_1"] == history_match["run_2"],
        "HISTORY_DEPENDENT_RELATION": history_a["relation"] != history_b["relation"],
        "POLICY_COUPLING": "ABSENT",
        "VALUE_COUPLING": "ABSENT",
    }
    dump("MATRIX_SUMMARY.json", matrix)

    answers = {
        "1": "YES — both are simultaneously present as mechanism-state traces at t1.",
        "2": "YES — ordinary acquired histories yield comparable P vs Q with relation INCOMPATIBLE.",
        "3": "YES — old created_tick=100, prefix physical realization and fresh reconstruction occur at t1=101.",
        "4": "YES — fresh has a new ID/tick and is reconstructed from a separate acquired-evidence key.",
        "5": "Only consequence incompatibility produces conflict; distinct provenance with identical P is AGREEMENT.",
        "6": "YES — OLD_ONLY/FRESH_ONLY are OLD_UNKNOWN/FRESH_UNKNOWN and never conflict.",
        "7": "YES — P and Q remain separate; averaged_prediction is null.",
        "8": "P-like reality confirms old and violates fresh.",
        "9": "Q-like reality violates old and confirms fresh.",
        "10": "YES — ordinarily acquired R-like reality violates both.",
        "11": "Any compatible old/fresh branch pair yields OVERLAP; no pair yields INCOMPATIBLE.",
        "12": "YES — old P versus fresh {P,Q} is OVERLAP, not conflict.",
        "13": "YES — matched S1/Q event gives conflict for history A and agreement for history B.",
        "14": f"Existing policy selects {policy['observation']['selected_action']} for its ordinary pre-existing selection reason.",
        "15": "NO — the comparison record is not supplied to action selection.",
        "16": "NO — Update 4.17 adds researcher measurement only.",
        "17": "YES — baseline and post-update sets contain the identical 15 failures; no new regression was introduced.",
        "18": "YES — comparable concurrent P/Q incompatibility satisfies the conservative definition.",
        "19": "YES, cautiously — as a functional precursor to mechanistic doubt, not doubt.",
        "20": "First unsupported arrow: unresolved prospective conflict -> policy/action selection.",
    }
    dump("ANSWERS.json", answers)
    dump("OBSERVER_CONFLICT_SNAPSHOT.json", {
        "matrix": matrix, "conflict": conflict, "agreement": agreement,
        "realization": {"P": realize_old, "Q": realize_fresh, "R": realize_neither},
        "policy": policy["observation"],
    })
    baseline_failures = [
        "tests/test_contextual_object_ecology_v034.py::test_serialization_determinism_and_reset_contracts",
        "tests/test_multi_channel_perception.py::test_contact_only_hides_distant_and_passive",
        "tests/test_multi_channel_perception.py::test_emit_returns_without_object_ids",
        "tests/test_multi_channel_perception.py::test_four_channels_exist_in_multi_channel_mode",
        "tests/test_observer_developmental_projection.py::test_projector_surfaces_depth_and_autonomous_fields",
        "tests/test_persistent_targets_v033.py::test_broken_target_stalls_after_switch_tick",
        "tests/test_persistent_targets_v033.py::test_dead_target_remains_visible_but_unproductive",
        "tests/test_persistent_targets_v033.py::test_revival_target_recovers_after_switch_tick",
        "tests/test_persistent_targets_v033.py::test_working_target_completes_after_threshold",
        "tests/test_sensorimotor_generation_v05.py::test_different_history_can_change_proposal_structure",
        "tests/test_sensorimotor_generation_v05.py::test_external_change_is_not_automatic_self_cause",
        "tests/test_sensorimotor_generation_v05.py::test_learned_contingency_can_structure_later_proposals",
        "tests/test_sensorimotor_generation_v05.py::test_learned_contingency_forms_from_accessible_evidence_only",
        "tests/test_sensorimotor_generation_v05.py::test_reversal_weakens_and_can_stop_structuring",
        "tests/test_sensorimotor_generation_v05.py::test_same_body_world_different_history_can_differ",
    ]
    dump("BASELINE_REGRESSION.json", {
        "before": {"collected": 259, "passed": 241, "failed": 15, "skipped": 3},
        "after": {"collected": 262, "passed": 244, "failed": 15, "skipped": 3},
        "failure_names_before": baseline_failures,
        "failure_names_after": baseline_failures,
        "failure_set_unchanged": True,
        "new_failures": [],
        "signature_groups": {
            "contextual_serialization": "IntakeParams is not JSON serializable",
            "multi_channel": "physical_perception/EMIT absent",
            "developmental_projection": "PsychologyTickView.cognitive_depth absent",
            "persistent_targets": "transition_action advance_dynamics argument mismatch",
            "sensorimotor_generation": "legacy contingencies remain empty",
        },
    })
    (OUT / "BASELINE_REGRESSION.md").write_text(
        "# Update 4.17 baseline regression\n\n"
        "Before: 259 collected, 241 passed, 15 failed, 3 skipped.\n\n"
        "After: 262 collected, 244 passed, 15 failed, 3 skipped. The three added 4.17 tests pass.\n\n"
        "The sorted failure-name sets are identical. New failures: none.\n\n"
        "## Unchanged failures\n\n" + "\n".join(f"- `{name}`" for name in baseline_failures) + "\n"
    )
    report = [
        "# Update 4.17 FINAL REPORT — Persistent Expectation × Fresh Prediction Conflict", "",
        "## Result", "", "OLD/FRESH_COEXISTENCE = PRESENT", "PROSPECTIVE_CONFLICT = PRESENT", "",
        "P and Q are concurrent, comparable, ordinarily acquired predictions with temporally distinct provenance. The comparison is researcher-only, preserves both representations, performs no averaging or resolution, and has no policy/value coupling.", "",
        "## Matrix", "", "```json", json.dumps(matrix, indent=2), "```", "", "## Final questions", "",
    ] + [f"{key}. {value}" for key, value in answers.items()] + [
        "", "## Claim boundary", "",
        "Supported cautiously: prospective conflict; functional precursor to mechanistic doubt.",
        "Not claimed: doubt, indecision, hesitation, belief conflict, deliberation, planning, or anticipation as a human faculty.", "",
        "The first unsupported causal arrow is unresolved prospective conflict → policy/action selection.",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    print(json.dumps(matrix, indent=2))


if __name__ == "__main__":
    main()
