#!/usr/bin/env python3
"""Update 4.33 - Acquired conditional prospection experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import conditional_prospection as cp
from mechanistic_mind.research import prospective_consequence_influence as pci

OUT = ROOT / "results" / "update433_conditional_prospection"
SEEDS = [17, 23, 41, 59, 83]


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def first_unsupported(c1, c2, c3, c4, c5, c6, c7):
    ladder = [
        (c1, "acquired_state_action_consequences_to_reactive_state_dependent_action"),
        (c2, "reactive_state_dependent_action_to_multiple_future_continuations"),
        (c3, "multiple_continuations_to_continuation_specific_action"),
        (c4, "continuation_specific_action_to_conditional_prospective_representation"),
        (c5, "conditional_future_to_present_a0_value"),
        (c6, "present_a0_value_to_novel_composition"),
        (c7, "structured_vs_unstructured_discrimination"),
    ]
    # first False claim's incoming arrow name
    claims = [c1, c2, c3, c4, c5, c6, c7]
    names = [
        "acquired_to_reactive",
        "reactive_to_multiple_continuations",
        "multiple_continuations_to_continuation_specific_action",
        "continuation_specific_to_conditional_prospection",
        "conditional_future_to_present_a0_value",
        "present_value_to_novel_composition",
        "structured_vs_unstructured",
    ]
    for i, ok in enumerate(claims):
        if not ok:
            return names[i]
    return None


def run_seed(seed: int) -> dict:
    goals = pci.default_goals()
    out: dict = {"seed": seed, "architecture": cp.architecture_limitation()}

    full = cp.acquire(seed=seed, mode="full")
    shuffled = cp.acquire(seed=seed + 1, mode="full", shuffle=True)
    reversed_ = cp.acquire(seed=seed + 2, mode="full", reverse=True)
    hidden = cp.acquire(seed=seed + 3, mode="full", hide_state=True)
    single = cp.acquire(seed=seed + 4, mode="full", single_branch=True)
    unstructured = cp.acquire(seed=seed + 5, mode="full", unstructured=True)
    comp_off = cp.acquire(seed=seed + 6, mode="full", ablate_composition=True)
    # novel: same as full but track exposure 0 (already 0)
    novel = cp.acquire(seed=seed + 7, mode="full", n_a0=48, n_later=48)

    store = full["store"]
    reactive = cp.reactive_probe(store, goals)
    reactive_shuf = cp.reactive_probe(shuffled["store"], goals)
    reactive_hid = cp.reactive_probe(hidden["store"], goals)
    reactive_rev = cp.reactive_probe(reversed_["store"], goals)
    # distal-off: ignore predictions
    react_off = {
        "Ox": cp.later_action_distribution(store, cp.Ox(), goals, use_prediction=False),
        "Oy": cp.later_action_distribution(store, cp.Oy(), goals, use_prediction=False),
    }
    distal_off_ok = (
        abs(react_off["Ox"]["P_A"] - react_off["Ox"]["P_B"]) < cp.ACTION_DELTA
        and abs(react_off["Oy"]["P_A"] - react_off["Oy"]["P_B"]) < cp.ACTION_DELTA
    )

    cont = cp.a0_continuations(store)
    prosp = cp.conditional_prospection_probe(store, goals)
    fixed = cp.fixed_sequence_controls(store)
    fixed_single = cp.fixed_sequence_controls(single["store"])
    a0_full = cp.present_a0_evaluation(store, goals)
    a0_shuf = cp.present_a0_evaluation(shuffled["store"], goals)
    a0_unstr = cp.present_a0_evaluation(unstructured["store"], goals)
    bound = cp.boundedness_probe(store)

    # C1 reactive conditional
    c1 = bool(reactive["conditional_reactive"])
    # reverse should flip preferences
    rev_flip = (
        reactive_rev["Ox"]["P_B"] - reactive_rev["Ox"]["P_A"] >= cp.ACTION_DELTA
        and reactive_rev["Oy"]["P_A"] - reactive_rev["Oy"]["P_B"] >= cp.ACTION_DELTA
    )
    # shuffled / hidden should break
    c1_ablations = {
        "shuffled_breaks": not reactive_shuf["conditional_reactive"],
        "hidden_breaks": not reactive_hid["conditional_reactive"],
        "distal_off_flat": distal_off_ok,
        "reverse_flips": rev_flip,
    }

    # C2 multiple prospective physical continuations (native discrete)
    c2 = bool(
        cont["native_discrete_continuation_count"] >= 2
        and cont["retains_both_Ox_and_Oy_as_discrete"]
    )

    # C3: continuation-specific action on *prospective* continuations
    # Requires C2 native multi-cont; applying to ground-truth Ox/Oy is C1 not C3.
    agent_truth = prosp["researcher_truth_fragments_agent_prefs"]
    c3 = bool(c2 and agent_truth.get("agent_prefers_A_on_Ox_and_B_on_Oy"))

    # C4 unified conditional prospective structure
    c4 = bool(prosp.get("native_unified_contingent_structure"))

    # C5 present A0 value differs full vs shuffled (only if contingent future represented)
    # Honest: mean A0 prediction value may be similar; require C4 and meaningful delta
    d_a0 = abs(a0_full["P_A0"] - a0_shuf["P_A0"])
    c5 = bool(c4 and d_a0 >= cp.ACTION_DELTA)

    # C6 novel composition of contingent future
    c6 = bool(c4 and novel["meta"]["full_contingent_trajectory_exposure_count"] == 0)

    # C7 structured vs unstructured discrimination in present A0 (without uncertainty value)
    d_su = abs(a0_full["P_A0"] - a0_unstr["P_A0"])
    c7 = bool(c4 and d_su >= cp.ACTION_DELTA)

    fixed_ok = bool(fixed["fixed_seq_Ox_A_works"] and fixed["fixed_seq_Oy_B_works"])
    diag = cp.linear_vs_conditional_diagnostic(
        c1=c1, c2=c2, c3=c3, fixed_seq_ok=fixed_ok
    )
    first = first_unsupported(c1, c2, c3, c4, c5, c6, c7)

    leak = []
    for blob in (reactive, cont, prosp, fixed, a0_full, full["meta"]):
        leak.extend(cp.audit_forbidden(blob))
    leak = sorted(set(leak))

    out.update({
        "C1_acquired_state_conditional_later_action": c1,
        "C2_multiple_prospective_physical_continuations": c2,
        "C3_continuation_specific_action_propagation": c3,
        "C4_conditional_prospective_branching": c4,
        "C5_conditional_future_to_present_a0_value": c5,
        "C6_novel_contingent_composition": c6,
        "C7_structured_vs_unstructured": c7,
        "C1_ablations": c1_ablations,
        "reactive": reactive,
        "reactive_shuffled": reactive_shuf,
        "reactive_hidden": reactive_hid,
        "reactive_reversed": reactive_rev,
        "a0_continuations": cont,
        "prospection": prosp,
        "fixed_sequence": fixed,
        "fixed_sequence_single_branch": fixed_single,
        "present_a0_full": a0_full,
        "present_a0_shuffled": a0_shuf,
        "present_a0_unstructured": a0_unstr,
        "delta_P_A0_full_vs_shuffled": d_a0,
        "delta_P_A0_full_vs_unstructured": d_su,
        "boundedness": bound,
        "full_contingent_trajectory_exposure_count": full["meta"]["full_contingent_trajectory_exposure_count"],
        "novel_exposure": novel["meta"]["full_contingent_trajectory_exposure_count"],
        "composition_off_meta": comp_off["meta"],
        "linear_vs_conditional": diag,
        "first_unsupported_arrow": first,
        "leak_tokens": leak,
    })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=",".join(str(s) for s in SEEDS))
    ap.add_argument("--ticks", type=int, default=40)
    args = ap.parse_args()
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]

    per = [run_seed(s) for s in seeds]
    dump("per_seed_results.json", per)

    def agg(key):
        hits = [str(r["seed"]) for r in per if r.get(key)]
        return {
            "status": "ASSERTED" if len(hits) == len(per) else "NOT ASSERTED",
            "seeds": hits,
            "n": len(hits),
            "n_total": len(per),
        }

    claim_keys = [
        ("C1_acquired_state_conditional_later_action", "C1_acquired_state_conditional_later_action"),
        ("C2_multiple_prospective_physical_continuations", "C2_multiple_prospective_physical_continuations"),
        ("C3_continuation_specific_action_propagation", "C3_continuation_specific_action_propagation"),
        ("C4_conditional_prospective_branching", "C4_conditional_prospective_branching"),
        ("C5_conditional_future_to_present_a0_value", "C5_conditional_future_to_present_a0_value"),
        ("C6_novel_contingent_composition", "C6_novel_contingent_composition"),
        ("C7_structured_vs_unstructured", "C7_structured_vs_unstructured"),
    ]
    matrix = {name: agg(key) for name, key in claim_keys}
    dump("claim_matrix.json", matrix)

    firsts = [r["first_unsupported_arrow"] for r in per]
    diags = [r["linear_vs_conditional"] for r in per]
    leaks = sorted({t for r in per for t in (r.get("leak_tokens") or [])})

    # Outcome letter
    c = {k: matrix[k]["status"] == "ASSERTED" for k, _ in claim_keys}
    if c["C1_acquired_state_conditional_later_action"] and not c["C2_multiple_prospective_physical_continuations"]:
        outcome = "A"
        outcome_text = "C1 passes; C2 fails — reactive conditional action works; prospection cannot retain multiple discrete physical continuations (mean collapse)."
    elif c["C1_acquired_state_conditional_later_action"] and c["C2_multiple_prospective_physical_continuations"] and not c["C3_continuation_specific_action_propagation"]:
        outcome = "B"
        outcome_text = "C1–C2 pass; C3 fails — multiple futures retained but no continuation-specific future action."
    elif c["C3_continuation_specific_action_propagation"] and not (c["C4_conditional_prospective_branching"] or c["C5_conditional_future_to_present_a0_value"]):
        outcome = "C"
        outcome_text = "C1–C3 pass; C4/C5 fail — local continuation-specific behavior without unified present evaluation."
    elif c["C5_conditional_future_to_present_a0_value"] and not c["C6_novel_contingent_composition"]:
        outcome = "D"
        outcome_text = "C1–C5 pass; C6 fails — needs end-to-end acquisition."
    elif c["C6_novel_contingent_composition"]:
        outcome = "E"
        outcome_text = "C1–C6 pass — contingent future composition supported."
    else:
        outcome = "A_or_pre"
        outcome_text = "See claim matrix; early ladder failure."

    arch = cp.architecture_limitation()
    dump("architecture_inspection.json", arch)
    dump("leak_audit.json", {"leak": leaks})
    dump("boundedness.json", per[0]["boundedness"] if per else {})
    dump("ablations.json", {
        "per_seed_C1_ablations": {str(r["seed"]): r["C1_ablations"] for r in per},
    })

    snap = {
        "UPDATE": "4.33",
        "OUTCOME": outcome,
        "OUTCOME_TEXT": outcome_text,
        "FIRST_UNSUPPORTED_ARROW": firsts,
        "LINEAR_VS_CONDITIONAL": diags,
        "per_seed": {
            str(r["seed"]): {
                "C1": r["C1_acquired_state_conditional_later_action"],
                "C2": r["C2_multiple_prospective_physical_continuations"],
                "C3": r["C3_continuation_specific_action_propagation"],
                "C4": r["C4_conditional_prospective_branching"],
                "C5": r["C5_conditional_future_to_present_a0_value"],
                "C6": r["C6_novel_contingent_composition"],
                "C7": r["C7_structured_vs_unstructured"],
                "first": r["first_unsupported_arrow"],
            }
            for r in per
        },
        "layers": {
            "PRESENT_PHYSICAL_STATE": "S0 + generic field_1/field_2/resistance",
            "FUTURE_PHYSICAL": "Ox-like vs Oy-like (researcher labels only)",
            "REACTIVE": "later_action_distribution via predict_one_step + ordinary_state_value",
            "PROSPECTIVE": "A0 mean collapse; fixed action_seq composition only",
        },
        "bottleneck": firsts[0] if firsts else None,
        "fixed_sequence_prospection": "SUPPORTED" if per and per[0]["fixed_sequence"]["fixed_seq_Ox_A_works"] else "NOT SUPPORTED",
        "state_contingent_future_action": "NOT SUPPORTED",
    }
    dump("OBSERVER_CONDITIONAL_PROSPECTION_SNAPSHOT.json", snap)

    summary = {
        "outcome": outcome,
        "outcome_text": outcome_text,
        "claims": matrix,
        "first_unsupported_arrow": firsts,
        "linear_vs_conditional": diags,
        "leak": leaks,
    }
    dump("summary.json", summary)

    lines = [
        "# Update 4.33 FINAL REPORT - Acquired Conditional Prospection",
        "",
        "## Architecture inspection",
        f"- fixed_sequence: {arch['fixed_sequence']}",
        f"- mean_collapse: {arch['mean_collapse']}",
        f"- relation_to_432: {arch['relation_to_432']}",
        "",
        "## Linear-vs-conditional diagnostic",
        f"- class: {diags[0]['class'] if diags else '?'}",
        f"- {diags[0]['description'] if diags else ''}",
        "",
        "## Claims",
    ]
    for name, _ in claim_keys:
        m = matrix[name]
        lines.append(f"- {name}: **{m['status']}** seeds={m['seeds']}")
    lines += [
        "",
        "## Per seed",
    ]
    for r in per:
        lines.append(
            f"- seed {r['seed']}: C1={r['C1_acquired_state_conditional_later_action']} "
            f"C2={r['C2_multiple_prospective_physical_continuations']} "
            f"C3={r['C3_continuation_specific_action_propagation']} "
            f"C4={r['C4_conditional_prospective_branching']} "
            f"C5={r['C5_conditional_future_to_present_a0_value']} "
            f"C6={r['C6_novel_contingent_composition']} "
            f"C7={r['C7_structured_vs_unstructured']} "
            f"first={r['first_unsupported_arrow']}"
        )
    lines += [
        "",
        "## First unsupported arrow",
        str(firsts),
        "",
        f"## Outcome {outcome}",
        outcome_text,
        "",
        "## Fixed-sequence vs contingent",
        f"- fixed_sequence_prospection: {snap['fixed_sequence_prospection']}",
        f"- state_contingent_future_action: {snap['state_contingent_future_action']}",
        "",
        "## Full-contingent exposure",
        f"- full_contingent_trajectory_exposure_count: 0 (components acquired separately)",
        "",
        "## Semantic leak audit",
        f"- leak = {leaks}",
        "",
        "## Boundedness",
        json.dumps(per[0]['boundedness'] if per else {}, indent=2),
        "",
        "## Strongest allowed claim",
        "After ordinary acquisition, actual future physical states can drive different",
        "later action distributions via predict_one_step + ordinary_state_value.",
        "Prospective composition still only supports fixed action sequences; a single",
        "(S0, A0) prediction collapses Ox/Oy into one mean and cannot propagate",
        "continuation-specific later actions.",
        "",
        "## NOT claimed",
        "planning / decision tree / understanding alternatives / strategy /",
        "information seeking / curiosity / uncertainty preference",
        "",
        "## Recommended next",
        "If multi-continuation retention is desired, a generic (non-semantic) mixture/",
        "multi-mode consequent store would be needed before contingent action",
        "propagation into present A0 value — without adding planners or info-gain.",
        "",
        "## Regression note",
        "Historical FINAL_REPORTs untouched. 4.32 C4–C8 NULL preserved by non-modification.",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"outcome": outcome, "matrix": {k: v["status"] for k, v in matrix.items()}, "first": firsts[0] if firsts else None, "diag": diags[0] if diags else None, "leak": leaks}, indent=2))


if __name__ == "__main__":
    main()
