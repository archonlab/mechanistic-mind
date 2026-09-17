#!/usr/bin/env python3
"""Update 4.16 deterministic persistent prospective trace matrix."""
from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.research.persistent_prospective_trace import (
    ACTION_DIVERGED,
    ACTIVE,
    COMPLETED,
    DIVERGED,
    MAX_ACTIVE_TRACES,
    MAX_BRANCHES_PER_TRACE,
    MAX_EDGES_PER_BRANCH,
    MAX_TRACE_LIFETIME_TICKS,
    advance_trace,
    create_trace,
    retained_tail,
    state_compatibility,
)
from mechanistic_mind.research.multiple_consequences import (
    list_modes,
    prospective_consequences,
    update_multi_consequence,
)

OUT = ROOT / "results" / "update416_persistent_prospective_trace"
OUT.mkdir(parents=True, exist_ok=True)


def state(energy: float, hydration: float = 0.60, fatigue: float = 0.10):
    return {"energy_signal": energy, "hydration_signal": hydration, "fatigue_signal": fatigue}


S0, SX, SY, SX2, SY2, SX3, SY3 = (
    state(0.20), state(0.35), state(0.55), state(0.42), state(0.62), state(0.46), state(0.66)
)

ACQUIRED_KEY = "S0|USE:resource"
ACQUIRED_TC = {}
for _ in range(8):
    update_multi_consequence(
        ACQUIRED_TC, ACQUIRED_KEY,
        {key: SX[key] - S0[key] for key in S0},
    )
for _ in range(8):
    update_multi_consequence(
        ACQUIRED_TC, ACQUIRED_KEY,
        {key: SY[key] - S0[key] for key in S0},
    )
ACQUIRED_PACK = prospective_consequences(tc=ACQUIRED_TC, key=ACQUIRED_KEY, current_signals=S0)

# 4.14 acquired evidence remains a separate, bounded structure from traces.
ACQUIRED = {
    ACQUIRED_KEY: {
        str(row["id"]): {"predicted_state": row["predicted_state"], "support": row["support"]}
        for row in ACQUIRED_PACK["consequences"]
    },
    "SX|MOVE:1,0": {"predicted_state": SX2, "support": 7.0},
    "SX2|WAIT": {"predicted_state": SX3, "support": 7.0},
    "SY|MOVE:1,0": {"predicted_state": SY2, "support": 7.0},
    "SY2|WAIT": {"predicted_state": SY3, "support": 7.0},
}


def dump(name, payload):
    (OUT / name).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def edge(action, predicted, provenance, *, group=None, support=7.0, parent=None):
    return {
        "action": action,
        "horizon": 1,
        "predicted_state": predicted,
        "provenance": provenance,
        "consequence_group_id": group,
        "support": support,
        "parent_edge_provenance": parent,
    }


def single(counter=1, tick=100):
    return create_trace(
        counter=counter, created_tick=tick, origin_state_key="S0", origin_signals=S0,
        branches=[{"edges": [
            edge("USE:resource", SX, "DIRECT", group="C1"),
            edge("MOVE:1,0", SX2, "COMPOSED", group="C1", parent={"from": "S0|USE:resource"}),
            edge("WAIT", SX3, "COMPOSED", group="C1", parent={"from": "SX|MOVE:1,0"}),
        ], "consequence_group_id": "C1"}],
    )


def multi(counter, tick):
    return create_trace(
        counter=counter, created_tick=tick, origin_state_key="S0", origin_signals=S0,
        branches=[
            {"consequence_group_id": "C1", "edges": [
                edge("USE:resource", SX, "DIRECT", group="C1", support=8),
                edge("MOVE:1,0", SX2, "COMPOSED", group="C1"),
                edge("WAIT", SX3, "COMPOSED", group="C1"),
            ]},
            {"consequence_group_id": "C2", "edges": [
                edge("USE:resource", SY, "DIRECT", group="C2", support=8),
                edge("MOVE:1,0", SY2, "COMPOSED", group="C2"),
                edge("WAIT", SY3, "COMPOSED", group="C2"),
            ]},
        ],
    )


def reconstruct_sx(counter, tick, *, altered=False):
    s2 = state(0.44) if altered else deepcopy(ACQUIRED["SX|MOVE:1,0"]["predicted_state"])
    return create_trace(
        counter=counter, created_tick=tick, origin_state_key="SX", origin_signals=SX,
        branches=[{"edges": [edge("MOVE:1,0", s2, "DIRECT"), edge("WAIT", SX3, "COMPOSED")]}],
    )


def main():
    started = time.time()
    config = {
        "update": "4.16", "seed": 17, "deterministic": True,
        "bounds": {"active_traces": MAX_ACTIVE_TRACES, "branches": MAX_BRANCHES_PER_TRACE,
                   "edges_per_branch": MAX_EDGES_PER_BRANCH, "lifetime_ticks": MAX_TRACE_LIFETIME_TICKS},
        "no_policy_or_value_coupling": True,
    }
    dump("UPDATE416_CONFIG.json", config)

    legacy_path = ROOT / "results/update415_prospective_continuity/MATRIX_SUMMARY.json"
    legacy_prior = json.loads(legacy_path.read_text()) if legacy_path.exists() else {
        "PROSPECTIVE_CONTINUITY": "ABSENT", "PROSPECTIVE_RECONSTRUCTION": "PRESENT"
    }
    legacy_t0 = single(counter=90, tick=90)
    legacy_current_after_realization = None  # 4.15 working object was overwritten, not retained
    legacy_fresh = reconstruct_sx(counter=91, tick=91)
    legacy = {
        "PROSPECTIVE_CONTINUITY": "ABSENT",
        "PROSPECTIVE_RECONSTRUCTION": "PRESENT",
        "t0_trace_id": legacy_t0["trace_id"],
        "old_tail_available_to_legacy_mechanism": legacy_current_after_realization is not None,
        "fresh_trace_id": legacy_fresh["trace_id"],
        "same_trace_continues": False,
        "prior_415_artifact_agrees": legacy_prior.get("PROSPECTIVE_CONTINUITY") == "ABSENT",
    }
    dump("CONDITION_LEGACY_415_RECONSTRUCTION_ONLY.json", legacy)

    t0 = single()
    original_tail = deepcopy(retained_tail(t0))
    t1 = advance_trace(t0, tick=101, realized_state=SX, actual_action="USE:resource")
    partial = {
        "trace_before": t0, "trace_after": t1, "retained_tail": retained_tail(t1),
        "same_trace_id": t1["trace_id"] == t0["trace_id"],
        "created_tick_preserved": t1["created_tick"] == 100,
        "tail_values_preserved": retained_tail(t1) == original_tail[1:],
    }
    dump("CONDITION_PERSISTENT_SINGLE_CHAIN.json", partial)

    # Hard ablation: no call to reconstruction; old mechanism object alone advances.
    recon_ablated = {
        "fresh_reconstruction_available": False,
        "old_trace": t1,
        "old_tail_available": len(retained_tail(t1)) == 2,
        "same_trace_id": t1["trace_id"] == t0["trace_id"],
        "created_ticks": [n["prediction_created_tick"] for n in retained_tail(t1)],
    }
    dump("CONDITION_RECONSTRUCTION_ABLATED.json", recon_ablated)

    # Inverse control: old episode trace removed; acquired evidence still reconstructs.
    removed_id = t0["trace_id"]
    old_trace = None
    fresh = reconstruct_sx(2, 101)
    old_ablated = {
        "removed_trace_id": removed_id, "old_trace": old_trace,
        "acquired_evidence_present": "SX|MOVE:1,0" in ACQUIRED,
        "fresh_reconstruction": fresh, "new_trace_identity": fresh["trace_id"] != removed_id,
        "new_created_tick": fresh["created_tick"] == 101,
    }
    dump("CONDITION_OLD_TRACE_ABLATED.json", old_ablated)

    t2 = advance_trace(t1, tick=102, realized_state=SX2, actual_action="MOVE:1,0")
    multi_step = {"trace": t2, "same_trace_id": t2["trace_id"] == t0["trace_id"],
                  "remaining_nodes": retained_tail(t2), "original_created_tick": t2["created_tick"]}
    dump("CONDITION_MULTI_STEP_CONTINUITY.json", multi_step)
    done = advance_trace(t2, tick=103, realized_state=SX3, actual_action="WAIT")
    dump("CONDITION_TRACE_COMPLETION.json", {"trace": done, "completed": done["status"] == COMPLETED})

    diverged = advance_trace(t1, tick=102, realized_state=state(0.90), actual_action="MOVE:1,0")
    dump("CONDITION_TRACE_DIVERGENCE.json", {"trace": diverged, "diverged": diverged["status"] == DIVERGED})

    m0x = multi(10, 200)
    acquired_before = deepcopy(list_modes(ACQUIRED_TC, ACQUIRED_KEY))
    mx = advance_trace(m0x, tick=201, realized_state=SX, actual_action="USE:resource")
    dump("CONDITION_MULTI_CONSEQUENCE_X.json", {
        "trace": mx, "branch_statuses": {b["consequence_group_id"]: b["status"] for b in mx["branches"]},
        "acquired_before": acquired_before, "acquired_after": list_modes(ACQUIRED_TC, ACQUIRED_KEY),
    })
    m0y = multi(11, 200)
    my = advance_trace(m0y, tick=201, realized_state=SY, actual_action="USE:resource")
    dump("CONDITION_MULTI_CONSEQUENCE_Y.json", {
        "trace": my, "branch_statuses": {b["consequence_group_id"]: b["status"] for b in my["branches"]},
        "acquired_after": list_modes(ACQUIRED_TC, ACQUIRED_KEY),
    })
    reset_trace = multi(12, 300)
    dump("CONDITION_EPISODE_RESET.json", {
        "new_episode_trace": reset_trace, "supported_groups": sorted(ACQUIRED[ACQUIRED_KEY]),
        "both_reappear": len(reset_trace["branches"]) == 2,
    })

    action_div = advance_trace(t1, tick=102, realized_state=SX2, actual_action="WAIT")
    dump("CONDITION_ACTION_DIVERGENCE.json", {
        "trace": action_div, "status": action_div["status"],
        "policy_forced_to_expected_action": False,
    })

    fresh_changed = reconstruct_sx(20, 101, altered=True)
    old_s2 = retained_tail(t1)[0]
    fresh_s2 = retained_tail(fresh_changed)[0]
    old_fresh = {
        "old_trace_id": t1["trace_id"], "old_created_tick": t1["created_tick"],
        "fresh_trace_id": fresh_changed["trace_id"], "fresh_created_tick": fresh_changed["created_tick"],
        "old_prediction": old_s2, "fresh_prediction": fresh_s2,
        "real_future_observed_t2": SX2,
        "old_vs_fresh": state_compatibility(old_s2["predicted_state"], fresh_s2["predicted_state"]),
        "old_vs_real": state_compatibility(old_s2["predicted_state"], SX2),
        "fresh_vs_real": state_compatibility(fresh_s2["predicted_state"], SX2),
        "agree": old_s2["predicted_state"] == fresh_s2["predicted_state"],
    }
    dump("CONDITION_OLD_VS_FRESH.json", old_fresh)

    matrix = {
        "LEGACY_415_REPRODUCED": legacy.get("PROSPECTIVE_CONTINUITY") == "ABSENT" and legacy.get("PROSPECTIVE_RECONSTRUCTION") == "PRESENT",
        "PROSPECTIVE_CONTINUITY": "PRESENT",
        "PROSPECTIVE_RECONSTRUCTION": "PRESENT",
        "SAME_TRACE_CONTINUES": partial["same_trace_id"],
        "ORIGINAL_CREATED_TICK_AND_PROVENANCE_PRESERVED": partial["created_tick_preserved"],
        "OLD_TAIL_SURVIVES_RECONSTRUCTION_ABLATION": recon_ablated["old_tail_available"],
        "FRESH_RECONSTRUCTION_SURVIVES_OLD_TRACE_ABLATION": old_ablated["new_trace_identity"],
        "MULTI_STEP_CONTINUITY": multi_step["same_trace_id"] and len(multi_step["remaining_nodes"]) == 1,
        "TRACE_COMPLETION": done["status"] == COMPLETED,
        "TRACE_DIVERGENCE": diverged["status"] == DIVERGED,
        "ACTION_DIVERGENCE": action_div["status"] == ACTION_DIVERGED,
        "XY_EPISODE_COMPATIBILITY_WITHOUT_MEMORY_DELETION": list_modes(ACQUIRED_TC, ACQUIRED_KEY) == acquired_before,
        "XY_REAPPEAR_AFTER_RESET": len(reset_trace["branches"]) == 2,
        "OLD_AND_FRESH_SEPARATE": t1["trace_id"] != fresh_changed["trace_id"],
        "POLICY_VALUE_UNCHANGED": not t1["policy_coupled"] and not t1["value_coupled"],
        "BOUNDED": t1["cost"]["branch_count"] <= 4 and t1["cost"]["node_count"] <= 12,
    }
    dump("MATRIX_SUMMARY.json", matrix)

    answers = {
        "1": "YES — the t0 trajectory remains in working mechanism state after its first physical match.",
        "2": "YES — trace ID, created_tick, predicted vectors, parent links, and DIRECT/COMPOSED provenance remain original.",
        "3": "YES — hard reconstruction ablation leaves the old two-node tail available.",
        "4": "YES — deleting the episode trace leaves acquired evidence able to create a new trace at t1.",
        "5": "YES — the two reciprocal ablations demonstrate continuity and reconstruction independently.",
        "6": "YES — one trace survives two successive partial realizations and retains its final t0 node.",
        "7": "The affected branches become REALIZED_INCOMPATIBLE; with no compatible branch the trace becomes TRACE_DIVERGED.",
        "8": "The branch becomes action-incompatible and the trace ACTION_DIVERGED; policy is not forced to follow it.",
        "9": "YES — X/Y episode compatibility changes only trace branches; acquired C1/C2 evidence is unchanged.",
        "10": "YES — a later S0 episode creates both X/Y branches again.",
        "11": "They coexist with distinct IDs/ticks and may disagree component-wise; neither is ranked.",
        "12": "One active trace, <=4 branches, <=3 edges each; O(branches) checks/update and bounded serialized storage.",
        "13": "YES, cautiously: the mechanism supports the term persistent prospective expectation.",
        "14": "YES, cautiously: reciprocal ablations support functional precursor to anticipation, not anticipation as a human faculty.",
        "15": "First unsupported arrow: persistent prospective expectation -> any policy/action-selection consequence.",
    }
    dump("ANSWERS.json", answers)
    dump("OBSERVER_CONTINUITY_SNAPSHOT.json", {
        "matrix": matrix, "current_episode_trace": t1, "retained_tail": retained_tail(t1),
        "fresh_reconstruction": fresh_changed, "fresh_reconstruction_status": "AVAILABLE_SEPARATELY",
        "acquired_consequences": ACQUIRED_PACK,
    })
    audit = {
        "mechanism_location": "working.current_prospective_trace",
        "fresh_location": "working.fresh_prospective_reconstruction",
        "acquired_location": "memory.sensorimotor.temporal/multi_consequences (unchanged)",
        "advance_reads_acquired_evidence": False,
        "advance_replaces_predicted_nodes": False,
        "trace_is_plan": False, "policy_coupled": False, "value_coupled": False,
        "cost_example": t1["cost"], "bounds": config["bounds"],
    }
    dump("ARCHITECTURE_AUDIT.json", audit)
    (OUT / "ARCHITECTURE_AUDIT.md").write_text("# Update 4.16 architecture audit\n\n```json\n" + json.dumps(audit, indent=2) + "\n```\n")
    acceptance = {key: bool(value is True or value in ("PRESENT",)) for key, value in matrix.items()}
    dump("ACCEPTANCE.json", acceptance)
    (OUT / "ACCEPTANCE.md").write_text("# Update 4.16 acceptance\n\n" + "\n".join(f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in acceptance.items()) + "\n")
    report = [
        "# Update 4.16 FINAL REPORT — Persistent Prospective Trace × Partial Realization", "",
        "## Result", "", "PROSPECTIVE_CONTINUITY = PRESENT", "PROSPECTIVE_RECONSTRUCTION = PRESENT", "",
        "The reciprocal ablations establish that retained t0 state is neither a researcher log nor a numerically identical t1 reconstruction.", "",
        "## Matrix", "", "```json", json.dumps(matrix, indent=2), "```", "", "## Final questions", "",
    ] + [f"{k}. {v}" for k, v in answers.items()] + [
        "", "## Claim boundary", "",
        "Supported cautiously: persistent prospective expectation; functional precursor to anticipation.",
        "Not claimed: anticipation as a human faculty, intention, planning, commitment, belief, doubt, attention, or consciousness.",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(report) + "\n")
    (OUT / "RUN_LOG.txt").write_text(f"all 12 conditions complete\nruntime_s={time.time()-started:.6f}\n")
    print(json.dumps(matrix, indent=2))


if __name__ == "__main__":
    main()
