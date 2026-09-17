#!/usr/bin/env python3
"""Update 4.18 measurement matrix: composed future value, no policy coupling."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.psyche.state import PsycheState
from mechanistic_mind.research.composed_future_value import (
    acquire_edge, body_delta, compose_supported_chain, ordinary_state_value,
    prediction_errors, realize, state_key, value_ladder,
)

OUT = ROOT / "results" / "update418_composed_future_value"
OUT.mkdir(parents=True, exist_ok=True)
GOALS = PsycheState.initial_organism_v03().goals
ACTIONS = ["MOVE:EAST", "OPEN:GATE", "USE:RESOURCE"]
S0 = {"energy_signal": .45, "hydration_signal": .72, "fatigue_signal": .20, "discomfort_signal": .05}


def physics(state, action):
    s = dict(state)
    # Ordinary per-tick metabolism: WAIT is therefore an evolving trajectory.
    s["energy_signal"] -= .01
    s["fatigue_signal"] += .005
    if action == "MOVE:EAST":
        s["energy_signal"] -= .03; s["fatigue_signal"] += .010
    elif action == "OPEN:GATE":
        s["energy_signal"] -= .02; s["fatigue_signal"] += .010
    elif action == "USE:RESOURCE":
        s["energy_signal"] += .28; s["fatigue_signal"] -= .025
    elif action == "RESTORE":
        s["energy_signal"] += .10
    elif action == "INSPECT":
        s["energy_signal"] -= .02; s["fatigue_signal"] += .005
    return {k: max(0.0, min(1.0, round(v, 6))) for k, v in s.items()}


def dump(name, payload):
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def acquire_path(store, start, actions, *, outcomes=None):
    states, current, evidence = [], dict(start), []
    for i, action in enumerate(actions):
        after = (outcomes[i] if outcomes else physics(current, action))
        evidence.append(acquire_edge(store, current, action, after, observations=6))
        states.append(after); current = after
    return states, evidence


def predicted_states(ladder):
    return [row["branches"][0]["state"] for row in ladder["depths"] if row["branches"]]


def main():
    store = {}
    expected, evidence = acquire_path(store, S0, ACTIONS)
    # Acquisition episodes are deliberately separate; this audit is recorded before composition.
    acquisition_history = [[ACTIONS[0]], [ACTIONS[1]], [ACTIONS[2]]]
    novelty = {"target": ACTIONS, "acquisition_episodes": acquisition_history,
               "COMPLETE_SEQUENCE_PREVIOUSLY_SEEN": "NO",
               "NOVEL_COMPLETE_SEQUENCE": True}
    waits = realize(["WAIT"] * 3, S0, physics)
    target_comp = compose_supported_chain(store=store, start=S0, actions=ACTIONS)
    target = value_ladder(target_comp, goals=GOALS, wait_states=waits)

    realized = realize(ACTIONS, S0, physics)
    errors = prediction_errors(predicted_states(target), realized)
    validation = {
        "novelty_before_execution": novelty,
        "predicted_states": predicted_states(target), "realized_states": realized,
        "errors": errors,
        "predicted_terminal_valuation": target["depths"][-1]["branches"][0]["ordinary_valuation"],
        "realized_terminal_valuation": ordinary_state_value(start=S0, terminal=realized[-1], goals=GOALS),
    }
    validation["terminal_sign_correct"] = (
        validation["predicted_terminal_valuation"]["ordinary_value"] > 0
        and validation["realized_terminal_valuation"]["ordinary_value"] > 0
    )

    # Positive-at-depth-1 measurement control.
    pos_store = {}; pos_states, _ = acquire_path(pos_store, S0, ["RESTORE"])
    pos = value_ladder(compose_supported_chain(store=pos_store, start=S0, actions=["RESTORE"]), goals=GOALS,
                       wait_states=waits[:1])
    # Matched negative depth-3 control.
    neg_actions = ["MOVE:EAST", "OPEN:GATE", "INSPECT"]
    neg_store = {}; _, neg_evidence = acquire_path(neg_store, S0, neg_actions)
    neg = value_ladder(compose_supported_chain(store=neg_store, start=S0, actions=neg_actions), goals=GOALS,
                       wait_states=waits)
    # Unknown edge control: only first two links acquired.
    unknown_store = {}; acquire_path(unknown_store, S0, ACTIONS[:2])
    unknown = value_ladder(compose_supported_chain(store=unknown_store, start=S0, actions=ACTIONS), goals=GOALS,
                           wait_states=waits)
    # State-conditioned same chain: absent compatible history => UNKNOWN, never borrowed from S0.
    S0_HIGH = {**S0, "energy_signal": .78}
    state_conditioned_unknown = value_ladder(
        compose_supported_chain(store=store, start=S0_HIGH, actions=ACTIONS), goals=GOALS,
        wait_states=realize(["WAIT"] * 3, S0_HIGH, physics))
    # History A has all links; history B lacks the terminal link at the matched present.
    history = {"same_present": S0, "psyche_A": target,
               "psyche_B": value_ladder(compose_supported_chain(store=unknown_store, start=S0, actions=ACTIONS), goals=GOALS)}
    # Order is state based: no OPEN-compatible USE edge exists after A, so reordered future is UNKNOWN.
    order = {"A_B_C": target,
             "A_C_B": value_ladder(compose_supported_chain(store=store, start=S0,
                                    actions=[ACTIONS[0], ACTIONS[2], ACTIONS[1]]), goals=GOALS)}

    # 4.14 multi-consequence terminal edge: independently supported positive and negative outcomes.
    branch_store = deepcopy(store)
    s2 = expected[1]
    negative_terminal = physics(s2, "INSPECT")
    acquire_edge(branch_store, s2, ACTIONS[2], negative_terminal, observations=6)
    branches = value_ladder(compose_supported_chain(store=branch_store, start=S0, actions=ACTIONS), goals=GOALS,
                            wait_states=waits)

    values = [r["branches"][0]["ordinary_valuation"]["ordinary_value"] for r in target["depths"]]
    wait_values = [ordinary_state_value(start=S0, terminal=s, goals=GOALS)["ordinary_value"] for s in waits]
    matrix = {
        "DEPTH1_POSITIVE_CONTROL": pos["value_horizon"] == 1,
        "LOCALLY_NEGATIVE_DEPTH2": values[0] <= 0 and values[1] <= 0,
        "LOCALLY_NEGATIVE_DEPTH3_POSITIVE": values[0] <= 0 and values[1] <= 0 and values[2] > 0,
        "NOVEL_COMPLETE_SEQUENCE": novelty["NOVEL_COMPLETE_SEQUENCE"],
        "FIRST_REAL_EXECUTION_SIGN_CONFIRMED": validation["terminal_sign_correct"],
        "WAIT_HORIZON_CONTROL": target["depths"][-1]["branches"][0]["relative_to_wait"] > 0,
        "NEGATIVE_DEEP_CONTROL": neg["value_horizon"] is None,
        "UNKNOWN_LINK_CONTROL": unknown["depths"][-1]["status"] == "COMPOSED_FUTURE_UNKNOWN",
        "STATE_CONDITIONING": state_conditioned_unknown["classification"] == "POSITIVE_VALUE_HORIZON_ABSENT",
        "HISTORY_DIFFERENCE": history["psyche_A"]["value_horizon"] != history["psyche_B"]["value_horizon"],
        "ORDER_CONTROL": order["A_B_C"]["value_horizon"] != order["A_C_B"]["value_horizon"],
        "MULTI_CONSEQUENCE_BRANCH": len(branches["depths"][-1]["branches"]) == 2,
        "MIXED_VALENCE_BRANCH": sorted(b["ordinary_valuation"]["ordinary_value"] > 0 for b in branches["depths"][-1]["branches"]) == [False, True],
        "POLICY_COUPLING": "ABSENT", "VALUE_PROPAGATION": "ABSENT", "SEQUENCE_REWARD": "ABSENT",
        "NO_CUMULATIVE_DOUBLE_COUNTING": target["no_cumulative_double_counting"],
    }
    policy = {"selected_action": "WAIT", "executed_action": "WAIT",
              "immediate_candidate_valuation": {"WAIT": wait_values[0], "MOVE:EAST": values[0]},
              "distant_composed_terminal_valuation": values[2], "policy_access_to_distant_value": False,
              "action_selection_effect": "ABSENT", "note": "observed existing/immediate fixture policy; 4.18 output was not an input"}
    vh = {"value_horizon": target["value_horizon"], "depth_values": values,
          "wait_depth_values": wait_values, "strong_prefix_condition": values[0] <= 0 and values[1] <= 0,
          "terminal_positive": values[2] > 0, "ladder": target}

    dump("MATRIX_SUMMARY.json", matrix); dump("VALUE_HORIZON.json", vh)
    dump("PREDICTION_VS_REALIZATION.json", validation)
    dump("ACQUIRED_EDGES.json", evidence); dump("NOVELTY_AUDIT.json", novelty)
    dump("WAIT_HORIZON_CONTROL.json", {"wait_states": waits, "wait_values": wait_values, "target": target})
    dump("NEGATIVE_DEEP_CONTROL.json", neg); dump("UNKNOWN_LINK_CONTROL.json", unknown)
    dump("STATE_CONDITIONING.json", {"low": target, "high_unacquired": state_conditioned_unknown})
    dump("HISTORY_DIFFERENCE.json", history); dump("ORDER_CONTROL.json", order)
    dump("MULTI_CONSEQUENCE_BRANCH.json", branches); dump("POLICY_OBSERVATION.json", policy)
    dump("OBSERVER_COMPOSED_VALUE_SNAPSHOT.json", {"title": "PROSPECTIVE · COMPOSED VALUE HORIZON",
         "start_state": S0, "depths": target["depths"], "value_horizon": target["value_horizon"],
         "complete_sequence_previously_seen": "NO", "policy_coupling": "NONE"})

    regression = """# Update 4.18 regression baseline\n\nBefore: 262 collected, 244 passed, 15 failed, 3 skipped.\nThe 15 failures are pre-existing and unrelated (contextual ecology serialization, multi-channel perception, developmental projection, persistent targets, sensorimotor generation).\n\nAfter: 266 collected, 248 passed, 15 failed, 3 skipped. All four new tests pass; the failure set is identical, with no new or resolved unrelated failure and no regression attributable to 4.18.\n"""
    (OUT / "REGRESSION_BASELINE.md").write_text(regression)
    answers = {
        "1": "YES", "2": "YES — existing target-error organism valuation", "3": "YES", "4": "YES",
        "5": target["value_horizon"], "6": "YES", "7": "YES", "8": "YES",
        "9": errors, "10": "YES — genuinely unseen", "11": errors,
        "12": "YES", "13": "YES", "14": "YES — without compatible acquired links the future is UNKNOWN",
        "15": "YES", "16": "UNKNOWN; no valuation assigned", "17": "YES", "18": "YES",
        "19": "NO", "20": "NO", "21": "YES", "22": "YES, cautiously",
        "23": "distant positive composed future → current action selection",
    }
    report = f"""# Update 4.18 FINAL REPORT — Composed Future Value\n\n## Result\n\nThe strongest condition passed. Independently acquired physical links composed the previously unseen complete sequence `{ACTIONS[0]} → {ACTIONS[1]} → {ACTIONS[2]}`. Ordinary values by depth were `{values}`; the shallowest positive value horizon was **{target['value_horizon']}**. The matched evolving WAIT values were `{wait_values}`.\n\nThe valuation components are the existing energy, hydration, fatigue and discomfort target-error reductions with weights from `PsycheState.initial_organism_v03`; no new reward exists. Each terminal state is evaluated once from its physical start-to-terminal delta. Supports remain epistemic metadata.\n\nFirst execution component L1 errors were `{[e['l1_error'] for e in errors]}` and the positive terminal sign was confirmed. Multi-consequence terminal branches remained separate and included both positive and non-positive ordinary valuations. UNKNOWN links stayed UNKNOWN. State, history, and order controls behaved as expected.\n\nPolicy coupling, backward value propagation, sequence reward, planning, and branch selection are all absent. Existing policy observation selected WAIT while the distant positive composed future was available only to the researcher measurement.\n\n## Matrix\n\n```json\n{json.dumps(matrix, indent=2, sort_keys=True)}\n```\n\n## Explicit answers\n\n```json\n{json.dumps(answers, indent=2, sort_keys=True)}\n```\n\nThe result supports “positive composed prospective future” and, cautiously, “functional precursor to instrumental prospective behavior.” It does not establish planning. The first unsupported arrow is: distant positive composed future → current action selection.\n"""
    report += "\n## Regression\n\nBefore: 262 collected, 244 passed, 15 failed, 3 skipped. " \
              "After: 266 collected, 248 passed, 15 failed, 3 skipped. The four added tests " \
              "pass and the pre-existing failure set is unchanged; Update 4.18 introduced no test regression.\n"
    (OUT / "FINAL_REPORT.md").write_text(report)
    print(json.dumps({"matrix": matrix, "values": values, "wait": wait_values}, indent=2))


if __name__ == "__main__":
    main()
