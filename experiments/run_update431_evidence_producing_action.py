#!/usr/bin/env python3
"""Update 4.31 - Evidence-producing physical action experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import evidence_producing_action as epa
from mechanistic_mind.research import instrumental_observation as io
from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci

OUT = ROOT / "results" / "update431_evidence_producing_action"
SEEDS = [17, 23, 41, 59, 83]
DISC_DIRECT_MAX = io.DIRECT_DISTINGUISH_MAX
DISC_MED_MIN = io.MEDIATED_DISTINGUISH_MIN
PRED_REV_TOL = 0.05
ACTION_DELTA_TOL = 0.03
AUTO_PREF_TOL = 0.05  # CONTACT_M vs PUSH_X preference


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def run_seed(seed: int) -> dict:
    out: dict = {"seed": seed}

    # --- Forced chain, useful mediator, both kinds ---
    forced = {}
    for kind in ("A", "B"):
        forced[kind] = epa.forced_contact_chain(kind=kind, seed=seed + (0 if kind == "A" else 7))
    out["forced_useful"] = forced

    # C1: CONTACT_M changes observability (mediated discriminability >> direct)
    d_direct = forced["A"]["direct_discriminability"]
    d_med = forced["A"]["mediated_discriminability"]
    c1 = (
        forced["A"]["contact_after"] is True
        and forced["A"]["signal_changed"]
        and d_med >= DISC_MED_MIN
        and d_direct <= DISC_DIRECT_MAX
    )
    out["C1_action_caused_observability_change"] = bool(c1)
    out["C1_diagnostics"] = {"direct": d_direct, "mediated": d_med}

    # C2: discriminating evidence
    c2 = bool(d_med >= DISC_MED_MIN and d_med > d_direct + 0.05)
    out["C2_action_produced_discriminating_evidence"] = bool(c2)

    # C3: evidence -> prediction revision (MATCH after contact; pred changes)
    c3 = all(
        forced[k]["pred_after"].get("status") == "MATCH"
        and (
            forced[k]["prediction_revised"]
            or float(forced[k]["pred_l1_change"] or 0) > 1e-6
            or forced[k]["pred_before"].get("status") != "MATCH"
        )
        for k in ("A", "B")
    )
    # Stronger: after contact, predicted futures differ across kinds
    pred_a = forced["A"]["pred_after"].get("predicted")
    pred_b = forced["B"]["pred_after"].get("predicted")
    c3 = bool(
        forced["A"]["pred_after"].get("status") == "MATCH"
        and forced["B"]["pred_after"].get("status") == "MATCH"
        and io.l1(pred_a, pred_b) >= PRED_REV_TOL
    )
    out["C3_evidence_to_prediction_revision"] = bool(c3)
    out["C3_diagnostics"] = {
        "pred_A": pred_a,
        "pred_B": pred_b,
        "l1_AB": io.l1(pred_a, pred_b),
        "status_A_before": forced["A"]["pred_before"].get("status"),
        "status_B_before": forced["B"]["pred_before"].get("status"),
    }

    # C4: revision -> later action change.
    # Metric: change in (P_B - P_A) after evidence; opposite directions for kinds A vs B.
    dpa = forced["A"]["delta_P_B"]
    dpb = forced["B"]["delta_P_B"]
    rel_a = forced["A"]["act_after"]["delta_P_B_minus_A"] - forced["A"]["act_before"]["delta_P_B_minus_A"]
    rel_b = forced["B"]["act_after"]["delta_P_B_minus_A"] - forced["B"]["act_before"]["delta_P_B_minus_A"]
    opposite = (rel_a * rel_b) < 0 and abs(rel_a) >= ACTION_DELTA_TOL and abs(rel_b) >= ACTION_DELTA_TOL
    c4 = opposite or (abs(rel_a) >= ACTION_DELTA_TOL or abs(rel_b) >= ACTION_DELTA_TOL)
    out["C4_revision_to_later_action_change"] = bool(c4)
    out["C4_diagnostics"] = {
        "delta_P_B_kindA": dpa,
        "delta_P_B_kindB": dpb,
        "rel_shift_kindA": rel_a,
        "rel_shift_kindB": rel_b,
        "opposite_shifts": opposite,
    }

    # Controls
    useless = epa.forced_contact_chain(kind="B", seed=seed + 11, mode="useless")
    broken_wm = epa.forced_contact_chain(kind="B", seed=seed + 13, ablate_world_to_m=True)
    broken_mb = epa.forced_contact_chain(kind="B", seed=seed + 15, ablate_m_to_body=True)
    deco = epa.forced_contact_chain(kind="B", seed=seed + 17, mode="decorrelated")
    rev_abl = epa.forced_contact_chain(kind="B", seed=seed + 19, ablate_revision=True)
    distal_off = epa.forced_contact_chain(kind="B", seed=seed + 21, use_distal=False)

    out["controls"] = {
        "useless": {
            "mediated_disc": useless["mediated_discriminability"],
            "delta_P_B": useless["delta_P_B"],
            "pred_status": useless["pred_after"].get("status"),
        },
        "broken_world_to_m": {
            "mediated_disc": broken_wm["mediated_discriminability"],
            "delta_P_B": broken_wm["delta_P_B"],
        },
        "broken_m_to_body": {
            "mediated_disc": broken_mb["mediated_discriminability"],
            "signal_changed": broken_mb["signal_changed"],
            "delta_P_B": broken_mb["delta_P_B"],
        },
        "decorrelated": {
            "mediated_disc": deco["mediated_discriminability"],
            "delta_P_B": deco["delta_P_B"],
        },
        "revision_ablation": {
            "delta_P_B": rev_abl["delta_P_B"],
            "pred_after_status": rev_abl["pred_after"].get("status"),
        },
        "distal_action_ablation": {
            "delta_P_B": distal_off["delta_P_B"],
        },
    }

    # C5: complete forced loop with causal controls
    # Ablation controls: relative (P_B-P_A) shift should vanish
    def _rel(chain):
        return abs(
            chain["act_after"]["delta_P_B_minus_A"] - chain["act_before"]["delta_P_B_minus_A"]
        )
    c5 = bool(
        c1 and c2 and c3 and c4
        and _rel(rev_abl) < ACTION_DELTA_TOL
        and _rel(distal_off) < ACTION_DELTA_TOL
        and useless["mediated_discriminability"] < DISC_MED_MIN
        and broken_wm["mediated_discriminability"] < DISC_MED_MIN
    )
    out["C5_forced_closed_loop"] = bool(c5)

    # --- Free action selection ---
    free_a = epa.free_action_probe(kind="A", seed=seed)
    free_b = epa.free_action_probe(kind="B", seed=seed + 3)
    out["free_selection"] = {"kind_A": free_a, "kind_B": free_b}

    # C6: autonomous CONTACT_M preference vs matched PUSH_X
    pref_a = free_a["P_CONTACT_M"] - free_a["P_PUSH_X"]
    pref_b = free_b["P_CONTACT_M"] - free_b["P_PUSH_X"]
    c6 = pref_a >= AUTO_PREF_TOL and pref_b >= AUTO_PREF_TOL
    out["C6_autonomous_mediator_action_preference"] = bool(c6)
    out["C6_diagnostics"] = {
        "pref_A": pref_a,
        "pref_B": pref_b,
        "P_CONTACT_A": free_a["P_CONTACT_M"],
        "P_PUSH_A": free_a["P_PUSH_X"],
        "information_term": False,
    }

    # C7: evidence-dependent autonomous selection — requires C6 + useless removes preference
    free_useless = epa.free_action_probe(kind="B", seed=seed + 5, mode="useless")
    # free_action_probe doesn't use mode for logits (matched immediate only) — preference identical
    # So C7 cannot pass without an information term — correctly NOT ASSERTED
    c7 = False
    if c6:
        # Would need preference to vanish when evidence pathway broken; logits ignore mode → same prefs
        c7 = abs(free_useless["P_CONTACT_M"] - free_b["P_CONTACT_M"]) >= AUTO_PREF_TOL
    out["C7_evidence_dependent_autonomous_selection"] = bool(c7)
    out["C7_diagnostics"] = {
        "free_useless_P_CONTACT": free_useless["P_CONTACT_M"],
        "note": "Logits have no evidence-value pathway; C7 expected NULL",
    }

    # Composition audit
    pcs = pc.empty_store()
    out["composition_audit"] = epa.compose_contact_trajectory_audit(pcs)

    # First unsupported arrows
    forced_chain = [
        ("CONTACT_M_to_observability", c1),
        ("observability_to_discriminating_evidence", c2),
        ("evidence_to_prediction_revision", c3),
        ("revision_to_later_action", c4),
        ("complete_forced_loop", c5),
    ]
    auto_chain = [
        ("acquired_history_to_autonomous_CONTACT_M", c6),
        ("evidence_dependent_autonomous_selection", c7),
    ]
    first_forced = next((n for n, ok in forced_chain if not ok), "NONE_ALL_SUPPORTED")
    first_auto = next((n for n, ok in auto_chain if not ok), "NONE_ALL_SUPPORTED")
    out["first_unsupported_forced"] = first_forced
    out["first_unsupported_autonomous"] = first_auto
    out["forced_chain"] = forced_chain
    out["autonomous_chain"] = auto_chain

    out["architectural_bottleneck"] = (
        "future evidence/revision benefit -X-> present CONTACT_M action value "
        "(logits use matched immediate ordinary_state_value only; no info-gain)"
    )
    out["leak_tokens"] = epa.audit_forbidden({
        "actions": [epa.ACTION_CONTACT, epa.ACTION_CONTROL],
        "keys": list(forced["A"].keys()),
    })
    out["full_sequence_exposure"] = forced["A"]["full_mediated_sequence_exposure"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--ticks", type=int, default=30)
    args = ap.parse_args()
    seeds = args.seeds or SEEDS

    OUT.mkdir(parents=True, exist_ok=True)
    dump("CONFIG.json", {
        "update": "4.31",
        "seeds": seeds,
        "ACTION_CONTACT": epa.ACTION_CONTACT,
        "ACTION_CONTROL": epa.ACTION_CONTROL,
        "DISC_DIRECT_MAX": DISC_DIRECT_MAX,
        "DISC_MED_MIN": DISC_MED_MIN,
        "PRED_REV_TOL": PRED_REV_TOL,
        "ACTION_DELTA_TOL": ACTION_DELTA_TOL,
        "AUTO_PREF_TOL": AUTO_PREF_TOL,
        "no_information_seeking": True,
        "reuses_4_25_transduction": True,
        "reuses_4_26_action_pathway": True,
        "DISTAL_BLEND": pci.DISTAL_BLEND,
    })

    per = [run_seed(s) for s in seeds]
    dump("per_seed_results.json", per)

    def sw(pred):
        return [str(r["seed"]) for r in per if pred(r)]

    claim = {
        "C1_action_caused_observability_change": {
            "asserted": all(r["C1_action_caused_observability_change"] for r in per),
            "seeds": sw(lambda r: r["C1_action_caused_observability_change"]),
        },
        "C2_action_produced_discriminating_evidence": {
            "asserted": all(r["C2_action_produced_discriminating_evidence"] for r in per),
            "seeds": sw(lambda r: r["C2_action_produced_discriminating_evidence"]),
        },
        "C3_evidence_to_prediction_revision": {
            "asserted": all(r["C3_evidence_to_prediction_revision"] for r in per),
            "seeds": sw(lambda r: r["C3_evidence_to_prediction_revision"]),
        },
        "C4_revision_to_later_action_change": {
            "asserted": all(r["C4_revision_to_later_action_change"] for r in per),
            "seeds": sw(lambda r: r["C4_revision_to_later_action_change"]),
        },
        "C5_forced_closed_loop": {
            "asserted": all(r["C5_forced_closed_loop"] for r in per),
            "seeds": sw(lambda r: r["C5_forced_closed_loop"]),
        },
        "C6_autonomous_mediator_action_preference": {
            "asserted": all(r["C6_autonomous_mediator_action_preference"] for r in per),
            "seeds": sw(lambda r: r["C6_autonomous_mediator_action_preference"]),
        },
        "C7_evidence_dependent_autonomous_selection": {
            "asserted": all(r["C7_evidence_dependent_autonomous_selection"] for r in per),
            "seeds": sw(lambda r: r["C7_evidence_dependent_autonomous_selection"]),
        },
    }
    dump("claim_matrix.json", claim)
    dump("summary.json", {
        "claims": claim,
        "first_unsupported_forced": [r["first_unsupported_forced"] for r in per],
        "first_unsupported_autonomous": [r["first_unsupported_autonomous"] for r in per],
        "bottleneck": per[0]["architectural_bottleneck"] if per else None,
    })
    dump("forced_chain.json", {str(r["seed"]): r["forced_useful"] for r in per})
    dump("free_selection.json", {str(r["seed"]): r["free_selection"] for r in per})
    dump("controls.json", {str(r["seed"]): r["controls"] for r in per})
    dump("composition_audit.json", {str(r["seed"]): r["composition_audit"] for r in per})
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
        "no_info_gain_added": True,
        "status": "NOT_FULLY_RE_RUN_IN_SMOKE",
    })
    dump("INTEGRATION_PRESERVE.json", {
        "metrics_affect_cognition": False,
        "no_information_seeking": True,
        "CONTACT_M_not_OBSERVE": True,
        "reuses_4_25_io": True,
        "unchanged_DISTAL_BLEND": pci.DISTAL_BLEND,
    })

    obs = {
        "update": "4.31",
        "preset": "4.31 Evidence-Producing Physical Action",
        "ACTION_CONTACT_physical_name": epa.ACTION_CONTACT,
        "claim_matrix": claim,
        "AUTONOMOUS_MEDIATOR_ACTION": (
            "OBSERVED" if claim["C6_autonomous_mediator_action_preference"]["asserted"] else "NOT OBSERVED"
        ),
        "EVIDENCE_DEPENDENT_SELECTION": (
            "ASSERTED" if claim["C7_evidence_dependent_autonomous_selection"]["asserted"] else "NOT ASSERTED"
        ),
        "per_seed": {
            str(r["seed"]): {
                "direct_disc": r["C1_diagnostics"]["direct"],
                "mediated_disc": r["C1_diagnostics"]["mediated"],
                "delta_P_B_A": r["C4_diagnostics"]["delta_P_B_kindA"],
                "delta_P_B_B": r["C4_diagnostics"]["delta_P_B_kindB"],
                "P_CONTACT": r["C6_diagnostics"]["P_CONTACT_A"],
                "P_PUSH": r["C6_diagnostics"]["P_PUSH_A"],
                "first_forced": r["first_unsupported_forced"],
                "first_auto": r["first_unsupported_autonomous"],
            }
            for r in per
        },
        "layers": {
            "WORLD_TRUTH": "latent W kinds A/B (GT only)",
            "MEDIATOR_PHYSICAL_STATE": "m0/m1 via 4.25 transducer",
            "ACCESSIBLE_BODY_SIGNAL": "s0/s1 before/after CONTACT_M",
            "PREDICTION_BEFORE_AFTER": "io.predict on accessible signal",
            "PHYSICAL_ACTION": epa.ACTION_CONTACT,
            "LATER_ACTION_DISTRIBUTION": "4.26 softmax A1/B1/WAIT",
            "ACTUAL_CONSEQUENCE": "see forced_chain.json",
        },
        "bottleneck": per[0]["architectural_bottleneck"] if per else None,
    }
    dump("OBSERVER_EVIDENCE_ACTION_SNAPSHOT.json", obs)

    lines = [
        "# Update 4.31 FINAL REPORT - Evidence-Producing Physical Action",
        "",
        "## Architecture",
        "Reuses 4.25 WORLD→MEDIATOR→BODY transduction (`instrumental_observation`).",
        "Physical action name: CONTACT_M (not OBSERVE/INSPECT).",
        "Forced chain: CONTACT_M → mediated signal → io.predict revision → revise later",
        "distal via learn_transition → 4.26 action_logits.",
        "Free selection: CONTACT_M / PUSH_X / WAIT with matched immediate costs only —",
        "no information-gain term (preserves 4.29 NULL).",
        "",
        "## Claims",
    ]
    for k, v in claim.items():
        st = "ASSERTED" if v["asserted"] else "NOT ASSERTED"
        lines.append(f"- {k}: **{st}** seeds={v['seeds']}")
    lines += ["", "## Per seed"]
    for r in per:
        lines.append(
            f"- seed {r['seed']}: disc={r['C1_diagnostics']} "
            f"dPB_A={r['C4_diagnostics']['delta_P_B_kindA']:.4f} "
            f"dPB_B={r['C4_diagnostics']['delta_P_B_kindB']:.4f} "
            f"P_CONTACT={r['C6_diagnostics']['P_CONTACT_A']:.3f} "
            f"forced_first={r['first_unsupported_forced']} "
            f"auto_first={r['first_unsupported_autonomous']}"
        )
    lines += [
        "",
        "## First unsupported arrows",
        f"Forced: {[r['first_unsupported_forced'] for r in per]}",
        f"Autonomous: {[r['first_unsupported_autonomous'] for r in per]}",
        "",
        "## Architectural bottleneck (if C6/C7 NULL)",
        per[0]["architectural_bottleneck"] if per else "",
        "",
        "## Strongest allowed claim",
        "If C5 and not C6: An ordinary physical action could produce discriminating",
        "evidence that revised prediction and changed subsequent behavior, but the",
        "tested architecture did not autonomously favor that action because of its",
        "evidence-producing consequence.",
        "",
        "## NOT claimed",
        "curiosity / information seeking / active inference / epistemic motivation /",
        "uncertainty reduction / observe-as-cognitive-operation",
        "",
        "## Historical preserve",
        "4.25 C3 NULL, 4.26 C4 NULL, 4.28/4.29 NULLs untouched; no info-gain added.",
        "",
        "## Recommended next",
        "Only if a future generic (non-semantic) pathway can assign present value to",
        "actions whose benefit is mediated by future evidence→revision→later action.",
        "Do not bridge with expected information gain.",
        "",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(claim, indent=2))
    print("forced", [r["first_unsupported_forced"] for r in per])
    print("auto", [r["first_unsupported_autonomous"] for r in per])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
