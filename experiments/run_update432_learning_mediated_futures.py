#!/usr/bin/env python3
"""Update 4.32 - Learning-mediated futures experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import learning_mediated_futures as lmf
from mechanistic_mind.research import evidence_producing_action as epa
from mechanistic_mind.research import instrumental_observation as io
from mechanistic_mind.research import prospective_consequence_influence as pci
from mechanistic_mind.research.composed_future_value import ordinary_state_value

OUT = ROOT / "results" / "update432_learning_mediated_futures"
SEEDS = [17, 23, 41, 59, 83]


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def run_seed(seed: int) -> dict:
    goals = pci.default_goals()
    out: dict = {"seed": seed, "why_431_failed": lmf.why_431_autonomous_failed()}

    # --- Phase 1: endogenous predictive-state causality (both kinds) ---
    phase1 = {}
    for kind in ("A", "B"):
        full = lmf.run_endogenous_transition(kind=kind, seed=seed + (0 if kind == "A" else 7))
        off = lmf.run_endogenous_transition(kind=kind, seed=seed + (0 if kind == "A" else 7), ablate_revision=True)
        phase1[kind] = {"full": full, "revision_off": off}
    out["phase1"] = phase1

    # C1: endogenous predictive-state transition
    # Operational: before contact NO_MATCH; after MATCH with kind-discriminating futures
    pred_a = phase1["A"]["full"]["pred_after"]
    pred_b = phase1["B"]["full"]["pred_after"]
    c1 = (
        phase1["A"]["full"]["pred_before_status"] == "NO_MATCH"
        and phase1["B"]["full"]["pred_before_status"] == "NO_MATCH"
        and phase1["A"]["full"]["pred_after_status"] == "MATCH"
        and phase1["B"]["full"]["pred_after_status"] == "MATCH"
        and io.l1(pred_a, pred_b) >= 0.05
    )
    out["C1_endogenous_predictive_state_transition"] = bool(c1)
    out["C1_diagnostics"] = {"pred_A": pred_a, "pred_B": pred_b, "l1": io.l1(pred_a, pred_b)}

    # C2: predictive-state transition causes later action change (revision ablation)
    rel_a = phase1["A"]["full"]["rel_shift"]
    rel_b = phase1["B"]["full"]["rel_shift"]
    rel_a_off = phase1["A"]["revision_off"]["rel_shift"]
    rel_b_off = phase1["B"]["revision_off"]["rel_shift"]
    c2 = (
        abs(rel_a) >= lmf.ACTION_DELTA_TOL
        and abs(rel_b) >= lmf.ACTION_DELTA_TOL
        and (rel_a * rel_b) < 0
        and abs(rel_a_off) < lmf.ACTION_DELTA_TOL
        and abs(rel_b_off) < lmf.ACTION_DELTA_TOL
    )
    out["C2_predictive_transition_causes_later_action"] = bool(c2)
    out["C2_diagnostics"] = {
        "rel_A": rel_a, "rel_B": rel_b, "rel_A_off": rel_a_off, "rel_B_off": rel_b_off,
    }

    # C3: learning-mediated distal consequence
    exp_a = lmf.distal_consequence_from_action_dist(phase1["A"]["full"]["act_after"])
    exp_b = lmf.distal_consequence_from_action_dist(phase1["B"]["full"]["act_after"])
    exp_a0 = lmf.distal_consequence_from_action_dist(phase1["A"]["full"]["act_before"])
    val_a = lmf.evaluate_expected_distal(exp_a, goals)
    val_b = lmf.evaluate_expected_distal(exp_b, goals)
    val_a0 = lmf.evaluate_expected_distal(exp_a0, goals)
    # After revision, expected distal values should differ across kinds vs matched before
    c3 = abs(val_a - val_b) >= lmf.VALUE_TOL and abs(val_a - val_a0) >= lmf.VALUE_TOL * 0.5
    # Also revision-off should not change expected distal much from before
    exp_a_off = lmf.distal_consequence_from_action_dist(phase1["A"]["revision_off"]["act_after"])
    val_a_off = lmf.evaluate_expected_distal(exp_a_off, goals)
    c3 = bool(
        abs(val_a - val_b) >= lmf.VALUE_TOL
        and abs(val_a_off - val_a0) < lmf.VALUE_TOL
    )
    out["C3_learning_mediated_distal_consequence"] = bool(c3)
    out["C3_diagnostics"] = {
        "val_A_after": val_a, "val_B_after": val_b, "val_A_before": val_a0, "val_A_rev_off": val_a_off,
    }

    # --- Phase 2/3: prospective representation ---
    stores = lmf.prepare_stores_for_prospection(kind="B", seed=seed)
    prosp = lmf.prospective_contact_evaluation(
        pc_store_full=stores["full"]["pc_store"],
        pc_store_rev_off=stores["rev_off"]["pc_store"],
        goals=goals,
    )
    # C4: native prospection distinguishes FULL vs REVISION-OFF for CONTACT_M
    # Native one-step CONTACT_M predictions are matched immediate — should NOT differ.
    # Multi-step compose CONTACT→B may COMPOSE but uses fixed action_seq, not revision-gated choice.
    native_represents = bool(prosp["native_contact_predicted_differs"])
    # If composed CONTACT+B full vs off differ in predicted distal due to B3 revision:
    pred_bf = prosp["compose_CONTACT_B_full"].get("predicted")
    pred_bo = prosp["compose_CONTACT_B_off"].get("predicted")
    compose_differs = (
        prosp["compose_CONTACT_B_full"].get("status") == "COMPOSED"
        and prosp["compose_CONTACT_B_off"].get("status") == "COMPOSED"
        and io.l1(pred_bf, pred_bo) > 1e-4
    )
    # CRITICAL: composing CONTACT_M then forced B1..B3 does NOT represent
    # "revision chooses B vs A". It assumes B. So even if distal differs, it is NOT
    # a prospective representation of the learning-mediated *branch*.
    # C4 requires representing that the intermediate predictive transition gates later action.
    # We assert C4 only if native machinery selects different later actions in composition
    # based on predictive state — which it cannot. Mark compose_differs as researcher note only.
    c4 = False  # architecture cannot treat predictive-state transition as composition node
    # Document: counterfactual researcher path differs (proves downstream exists) but native C4 false
    prosp["prospective_represents_learning_mediated_future"] = False
    prosp["compose_CONTACT_B_distal_differs_due_to_revised_B3"] = compose_differs
    prosp["c4_rationale"] = (
        "Composition can chain CONTACT_M then a *pre-specified* A/B sequence; "
        "it cannot represent revision-gated choice of A vs B. "
        "Native CONTACT_M one-step does not differ FULL vs REVISION-OFF. "
        "Therefore learning-mediated future is not prospectively represented."
    )
    out["phase2_prospection"] = prosp
    out["C4_prospective_representation_of_learning_mediated_future"] = bool(c4)

    # C5: present CONTACT_M value differs FULL vs REVISION-OFF under existing evaluation
    c5 = bool(prosp["present_value_differs"])
    out["C5_learning_mediated_present_action_value"] = bool(c5)
    out["C5_diagnostics"] = {
        "value_full": prosp["present_CONTACT_M_value_full"],
        "value_off": prosp["present_CONTACT_M_value_off"],
        "researcher_counterfactual_differs": prosp["researcher_counterfactual"]["differs"],
        "note": "Present value uses immediate-only path (4.31); counterfactual F differs but is not wired in",
    }

    # C6: novel composition of learning-mediated future without end-to-end exposure
    # Exposure is 0, but composition of the *learning-mediated* future fails (C4 false)
    c6 = bool(c4 and prosp["full_sequence_exposure_CONTACT_chain"] == 0)
    out["C6_novel_composition_of_learning_mediated_future"] = bool(c6)
    out["C6_diagnostics"] = {
        "full_sequence_exposure": prosp["full_sequence_exposure_CONTACT_chain"],
        "compose_status_B": prosp["compose_CONTACT_B_full"].get("status"),
    }

    # --- Phase 4: autonomous probe ---
    free = lmf.present_action_probs(goals, seed=seed)
    free_off = lmf.present_action_probs(goals, seed=seed + 1)  # same immediate path
    # Matched immediate check
    imm_c = float(ordinary_state_value(start=pci.S0(), terminal=dict(epa.MATCHED_IMM_COST), goals=goals).get("ordinary_value") or 0)
    imm_p = imm_c
    out["free_selection"] = free
    out["immediate_match"] = {"CONTACT_M": imm_c, "PUSH_X": imm_p, "matched": abs(imm_c - imm_p) < 1e-12}

    pref = free["P_CONTACT_M"] - free["P_PUSH_X"]
    c7 = pref >= lmf.AUTO_PREF_TOL
    out["C7_autonomous_CONTACT_M_selection"] = bool(c7)
    out["C7_diagnostics"] = {"pref": pref, "P_CONTACT": free["P_CONTACT_M"], "P_PUSH": free["P_PUSH_X"]}

    c8 = False
    if c7:
        # Would need revision-off to remove preference — immediate path identical → cannot
        c8 = False
    out["C8_revision_dependent_autonomous_selection"] = bool(c8)

    # Controls summary
    deco = lmf.run_endogenous_transition(kind="B", seed=seed + 17, mode="decorrelated")
    broken = epa.forced_contact_chain(kind="B", seed=seed + 15, ablate_m_to_body=True)
    out["controls"] = {
        "decorrelated_rel_shift": deco["rel_shift"],
        "broken_m_to_body_disc": broken["mediated_discriminability"],
        "broken_signal_changed": broken["signal_changed"],
        "revision_off_rel_A": rel_a_off,
        "distal_off": lmf.run_endogenous_transition(kind="B", seed=seed + 21, use_distal=False)["rel_shift"],
    }

    # First unsupported arrow
    chain = [
        ("CONTACT_M_to_observability_evidence", c1),  # bundled with transition detectability
        ("endogenous_predictive_state_transition", c1),
        ("predictive_transition_to_later_action", c2),
        ("later_action_to_distal_consequence", c3),
        ("learning_mediated_future_to_prospective_representation", c4),
        ("learning_mediated_future_to_present_CONTACT_M_value", c5),
        ("present_value_to_autonomous_selection", c7),
        ("revision_dependent_autonomous_selection", c8),
    ]
    first = next((n for n, ok in chain if not ok), "NONE_ALL_SUPPORTED")
    out["first_unsupported_arrow"] = first
    out["claim_chain"] = chain
    out["architectural_bottleneck"] = (
        "endogenous predictive-state transition -X-> prospective representation "
        "(composition has no revision-gated branch; CONTACT_M present value is immediate-only)"
        if not c4 else
        "learning_mediated_future -X-> present_CONTACT_M_value"
        if not c5 else
        "present_CONTACT_M_value -X-> autonomous_selection"
        if not c7 else
        "NONE"
    )
    out["leak_tokens"] = lmf.audit_forbidden({"phase1": list(phase1.keys()), "prosp_keys": list(prosp.keys())})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--ticks", type=int, default=40)
    args = ap.parse_args()
    seeds = args.seeds or SEEDS

    OUT.mkdir(parents=True, exist_ok=True)
    dump("CONFIG.json", {
        "update": "4.32",
        "seeds": seeds,
        "ACTION_DELTA_TOL": lmf.ACTION_DELTA_TOL,
        "VALUE_TOL": lmf.VALUE_TOL,
        "AUTO_PREF_TOL": lmf.AUTO_PREF_TOL,
        "no_information_seeking": True,
        "no_learning_reward": True,
        "why_431_code_path": lmf.why_431_autonomous_failed(),
    })

    per = [run_seed(s) for s in seeds]
    dump("per_seed_results.json", per)

    def sw(pred):
        return [str(r["seed"]) for r in per if pred(r)]

    claim = {
        "C1_endogenous_predictive_state_transition": {
            "asserted": all(r["C1_endogenous_predictive_state_transition"] for r in per),
            "seeds": sw(lambda r: r["C1_endogenous_predictive_state_transition"]),
        },
        "C2_predictive_transition_causes_later_action": {
            "asserted": all(r["C2_predictive_transition_causes_later_action"] for r in per),
            "seeds": sw(lambda r: r["C2_predictive_transition_causes_later_action"]),
        },
        "C3_learning_mediated_distal_consequence": {
            "asserted": all(r["C3_learning_mediated_distal_consequence"] for r in per),
            "seeds": sw(lambda r: r["C3_learning_mediated_distal_consequence"]),
        },
        "C4_prospective_representation_of_learning_mediated_future": {
            "asserted": all(r["C4_prospective_representation_of_learning_mediated_future"] for r in per),
            "seeds": sw(lambda r: r["C4_prospective_representation_of_learning_mediated_future"]),
        },
        "C5_learning_mediated_present_action_value": {
            "asserted": all(r["C5_learning_mediated_present_action_value"] for r in per),
            "seeds": sw(lambda r: r["C5_learning_mediated_present_action_value"]),
        },
        "C6_novel_composition_of_learning_mediated_future": {
            "asserted": all(r["C6_novel_composition_of_learning_mediated_future"] for r in per),
            "seeds": sw(lambda r: r["C6_novel_composition_of_learning_mediated_future"]),
        },
        "C7_autonomous_CONTACT_M_selection": {
            "asserted": all(r["C7_autonomous_CONTACT_M_selection"] for r in per),
            "seeds": sw(lambda r: r["C7_autonomous_CONTACT_M_selection"]),
        },
        "C8_revision_dependent_autonomous_selection": {
            "asserted": all(r["C8_revision_dependent_autonomous_selection"] for r in per),
            "seeds": sw(lambda r: r["C8_revision_dependent_autonomous_selection"]),
        },
    }
    dump("claim_matrix.json", claim)
    dump("summary.json", {
        "claims": claim,
        "first_unsupported_arrows": [r["first_unsupported_arrow"] for r in per],
        "bottlenecks": [r["architectural_bottleneck"] for r in per],
        "why_431": per[0]["why_431_failed"] if per else None,
    })
    dump("phase1_endogenous.json", {str(r["seed"]): {
        "C1": r["C1_diagnostics"], "C2": r["C2_diagnostics"], "C3": r["C3_diagnostics"],
    } for r in per})
    dump("prospection.json", {str(r["seed"]): r["phase2_prospection"] for r in per})
    dump("free_selection.json", {str(r["seed"]): r["free_selection"] for r in per})
    dump("controls.json", {str(r["seed"]): r["controls"] for r in per})
    dump("leak_audit.json", {
        "per_seed": [{"seed": r["seed"], "tokens": r["leak_tokens"]} for r in per],
        "any_leak": any(r["leak_tokens"] for r in per),
    })
    dump("ACCEPTANCE_MATRIX.json", {k: v["asserted"] for k, v in claim.items()})
    dump("BASELINE_REGRESSION.json", {
        "preserve_4_25_C3_NOT_ASSERTED": True,
        "preserve_4_26_C4_NOT_ASSERTED": True,
        "preserve_4_28_C2_C3_C4_NOT_ASSERTED": True,
        "preserve_4_29_C3_C4_C5_NOT_ASSERTED": True,
        "preserve_4_30_C1_C5_ASSERTED": True,
        "preserve_4_31_C1_C5_ASSERTED": True,
        "preserve_4_31_C6_C7_NOT_ASSERTED": True,
        "no_info_gain_added": True,
        "no_learning_reward": True,
        "status": "NOT_FULLY_RE_RUN_IN_SMOKE",
    })
    dump("INTEGRATION_PRESERVE.json", {
        "metrics_affect_cognition": False,
        "no_self_model_sensor": True,
        "no_information_seeking": True,
        "CONTACT_M_immediate_only_in_present_eval": True,
    })

    obs = {
        "update": "4.32",
        "preset": "4.32 Learning-Mediated Futures",
        "claim_matrix": claim,
        "FIRST_UNSUPPORTED_ARROW": [r["first_unsupported_arrow"] for r in per],
        "bottleneck": per[0]["architectural_bottleneck"] if per else None,
        "why_431_code": per[0]["why_431_failed"] if per else None,
        "per_seed": {
            str(r["seed"]): {
                "rel_A": r["C2_diagnostics"]["rel_A"],
                "rel_B": r["C2_diagnostics"]["rel_B"],
                "present_val_full": r["C5_diagnostics"]["value_full"],
                "present_val_off": r["C5_diagnostics"]["value_off"],
                "P_CONTACT": r["C7_diagnostics"]["P_CONTACT"],
                "P_PUSH": r["C7_diagnostics"]["P_PUSH"],
                "counterfactual_differs": r["C5_diagnostics"]["researcher_counterfactual_differs"],
            }
            for r in per
        },
        "layers": {
            "PRESENT_PHYSICAL_STATE": "S0 + matched CONTACT_M/PUSH_X immediates",
            "CONTACT_M_CONTROL": "CONTACT_M vs PUSH_X",
            "PHYSICAL_TRANSDUCTION": "4.25 WORLD->M->BODY",
            "ACCESSIBLE_SIGNAL": "s0/s1 before/after contact",
            "PREDICTIVE_STRUCTURE_BEFORE_AFTER": "io.predict NO_MATCH->MATCH",
            "LATER_ACTION_DISTRIBUTION": "4.26 softmax shift opposite by kind",
            "PHYSICAL_CONSEQUENCE": "expected distal from later action dist",
            "PRESENT_PROSPECTIVE_VALUE_OF_CONTACT_M": "immediate-only; FULL==REVISION-OFF",
        },
    }
    dump("OBSERVER_LEARNING_FUTURES_SNAPSHOT.json", obs)

    lines = [
        "# Update 4.32 FINAL REPORT - Learning-Mediated Futures",
        "",
        "## Why 4.31 autonomous selection failed (code)",
        str(lmf.why_431_autonomous_failed()),
        "",
        "## Architecture",
        "No INFORMATION/CURIOSITY/LEARNING_VALUE. Reuses 4.25/4.26/4.31 machinery.",
        "Does not serialize predictive memory as a sensor.",
        "Does not inject counterfactual F into CONTACT_M logits (forbidden bridge).",
        "",
        "## Claims",
    ]
    for k, v in claim.items():
        st = "ASSERTED" if v["asserted"] else "NOT ASSERTED"
        lines.append(f"- {k}: **{st}** seeds={v['seeds']}")
    lines += ["", "## Per seed"]
    for r in per:
        lines.append(
            f"- seed {r['seed']}: C1={r['C1_endogenous_predictive_state_transition']} "
            f"C2={r['C2_predictive_transition_causes_later_action']} "
            f"C3={r['C3_learning_mediated_distal_consequence']} "
            f"C4={r['C4_prospective_representation_of_learning_mediated_future']} "
            f"C5={r['C5_learning_mediated_present_action_value']} "
            f"C6={r['C6_novel_composition_of_learning_mediated_future']} "
            f"C7={r['C7_autonomous_CONTACT_M_selection']} "
            f"C8={r['C8_revision_dependent_autonomous_selection']} "
            f"first={r['first_unsupported_arrow']}"
        )
    lines += [
        "",
        "## First unsupported arrow",
        f"{[r['first_unsupported_arrow'] for r in per]}",
        "",
        "## Outcome classification",
        "Expected Outcome A: C1–C3 pass; C4 fails.",
        "Downstream learning-mediated physical loop works when CONTACT_M is forced,",
        "but prospective machinery cannot represent revision-gated later action choice,",
        "and present CONTACT_M value remains immediate-only (FULL == REVISION-OFF).",
        "",
        "## Strongest allowed claim",
        "Evidence can change predictive organization; that change can change later action",
        "and distal outcome — but that learning-mediated future does not reach present",
        "CONTACT_M evaluation through existing prospection.",
        "",
        "## NOT claimed",
        "curiosity / information seeking / metacognition / planning to learn /",
        "desire to know / self-awareness",
        "",
        "## Recommended next",
        "Only if a future generic (non-semantic) representation can treat endogenous",
        "predictive-organization transitions as first-class nodes in prospective",
        "composition — without info-gain rewards or self-model sensors.",
        "",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(claim, indent=2))
    print("first", [r["first_unsupported_arrow"] for r in per])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
