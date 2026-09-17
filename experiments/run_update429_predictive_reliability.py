#!/usr/bin/env python3
"""Update 4.29 - Predictive reliability / conflicting evidence experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import predictive_reliability as pr
from mechanistic_mind.research import prospective_consequence_influence as pci
from mechanistic_mind.research import prospective_composition as pc

OUT = ROOT / "results" / "update429_predictive_reliability"
SEEDS = [17, 23, 41, 59, 83]
N_SAMPLES = 300
# Action delta threshold for claiming distributional influence (pre-registered)
ACTION_DELTA_TOL = 0.03


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def strip_store(d: dict) -> dict:
    """JSON-safe copy without live store object."""
    return {k: v for k, v in d.items() if k not in ("store", "goals")}


def run_seed(seed: int) -> dict:
    out: dict = {"seed": seed}

    # A. Primary matched-mean / different-distribution
    primary = pr.build_matched_mean_condition(seed=seed)
    store = primary["store"]
    goals = primary["goals"]
    act = pr.action_probe(store, goals, seed=seed, n=N_SAMPLES)
    out["primary"] = {
        **strip_store(primary),
        "action": act,
        "full_seq_A": primary["meta_a"]["full_sequence_exposure_count"],
        "full_seq_B": primary["meta_b"]["full_sequence_exposure_count"],
    }

    # C1: multiple outcome structure retained as variance (var_sum) with different consistency
    c1 = bool(
        primary["distributions_differ"]
        and primary["compose_A"]["composition_status"] == "COMPOSED"
        and primary["compose_B"]["composition_status"] == "COMPOSED"
        and primary["meta_a"]["full_sequence_exposure_count"] == 0
        and primary["meta_b"]["full_sequence_exposure_count"] == 0
    )
    out["C1_multiple_outcome_structure"] = c1

    # C2: matched expected consequence validity
    c2 = bool(primary["matched_mean"] and primary["distributions_differ"])
    out["C2_matched_expected_consequence"] = c2

    # C3: distributional action influence
    # Requires C2 and |delta P| > ACTION_DELTA_TOL
    delta = abs(float(act["delta_P_A_minus_B"]))
    c3 = bool(c2 and delta > ACTION_DELTA_TOL and not act["reliability_in_action_row"])
    # If matched means but action identical → NULL (expected bottleneck)
    out["C3_distributional_action_influence"] = c3
    out["C3_diagnostics"] = {
        "delta_P_A_minus_B": act["delta_P_A_minus_B"],
        "abs_delta": delta,
        "action_delta_tol": ACTION_DELTA_TOL,
        "reliability_in_action_row": act["reliability_in_action_row"],
        "bottleneck": (
            "action_logits uses scalar ordinary_value of mean predicted_distal; "
            "var_sum/reliability not consumed"
        ),
    }

    # B. Matched-mean / matched-distribution control
    ctrl_same = pr.build_matched_distribution_control()
    act_same = pr.action_probe(ctrl_same["store"], ctrl_same["goals"], seed=seed + 1)
    out["control_matched_distribution"] = {
        **strip_store(ctrl_same),
        "action": act_same,
        "spurious_diff": abs(act_same["delta_P_A_minus_B"]) > ACTION_DELTA_TOL,
    }

    # C. Different-mean control (4.26 pathway still works)
    ctrl_diff = pr.build_different_mean_control()
    act_diff = pr.action_probe(ctrl_diff["store"], ctrl_diff["goals"], seed=seed + 2)
    out["control_different_mean"] = {
        **strip_store(ctrl_diff),
        "action": act_diff,
        "pathway_426_alive": abs(act_diff["delta_P_A_minus_B"]) > ACTION_DELTA_TOL,
    }

    # D. Shuffled outcome association
    shuf = pr.shuffle_terminal_outcomes(store, seed=seed)
    goals2 = pci.default_goals()
    act_shuf = pr.action_probe(shuf, goals2, seed=seed + 3)
    # After swap, values may flip; structure difference moves with rows
    va_s = pr.compose_and_value(shuf, ["A1", "A2", "A3"], goals2)
    vb_s = pr.compose_and_value(shuf, ["B1", "B2", "B3"], goals2)
    out["shuffle_control"] = {
        "action": act_shuf,
        "value_A": va_s.get("ordinary_value"),
        "value_B": vb_s.get("ordinary_value"),
        "delta_P": act_shuf["delta_P_A_minus_B"],
        "note": "terminal A3/B3 stats swapped",
    }

    # E. Support already matched in primary (support_matched)
    out["support_matched"] = primary["support_matched"]

    # F. Selective structure ablation: zero var_sum (mean-only)
    mean_only = pr.mean_only_baseline(store)
    act_mo = pr.action_probe(mean_only, goals, seed=seed + 4)
    out["ablation_mean_only_var_zeroed"] = {
        "action": act_mo,
        "delta_P": act_mo["delta_P_A_minus_B"],
        "delta_vs_primary": act_mo["delta_P_A_minus_B"] - act["delta_P_A_minus_B"],
        "effect_removed": abs(act_mo["delta_P_A_minus_B"] - act["delta_P_A_minus_B"]) < 0.005,
        "note": "If primary C3 NULL, ablation also unchanged — confirms variance unused",
    }

    # G. Collapse A mixture to single mean point
    collapsed = pr.ablate_multi_outcome_to_single(store, "A3", primary["designed_a_mean"])
    collapsed = pr.ablate_multi_outcome_to_single(collapsed, "B3", primary["designed_b_mean"])
    act_col = pr.action_probe(collapsed, goals, seed=seed + 5)
    out["ablation_collapse_mixture"] = {
        "action": act_col,
        "delta_P": act_col["delta_P_A_minus_B"],
        "unchanged_vs_primary": abs(act_col["delta_P_A_minus_B"] - act["delta_P_A_minus_B"]) < 0.01,
    }

    # C4: only if C3 positive
    c4 = False
    if c3:
        # effect should vanish when var zeroed OR when means forced equal after shuffle of structure
        c4 = bool(out["ablation_mean_only_var_zeroed"]["effect_removed"] is False)  # if C3 true, need effect depend on structure
        # Actually: selective dependence = removing structure removes effect
        c4 = abs(act_mo["delta_P_A_minus_B"]) < ACTION_DELTA_TOL and delta > ACTION_DELTA_TOL
    out["C4_selective_causal_dependence"] = c4

    # C5: experience-driven reliability reversal — only if natural; try brief probe without new mechanisms
    # Add contradictory experience to previously consistent A
    st_rev = store  # use copy
    from copy import deepcopy
    st_rev = deepcopy(store)
    # flood A with conflicting F_lo-like outcomes
    cat = pr.outcome_catalog()
    for i in range(80):
        pc.learn_transition(st_rev, tick=9000 + i, antecedent=pci.S2(), action="A3", consequent=cat["F_mid_lo"])
    met_a2 = pr.researcher_distribution_metrics(pr.terminal_row(st_rev, "A3"))
    met_b2 = pr.researcher_distribution_metrics(pr.terminal_row(st_rev, "B3"))
    act_rev = pr.action_probe(st_rev, goals, seed=seed + 6)
    va_r = pr.compose_and_value(st_rev, ["A1", "A2", "A3"], goals)
    # C5 requires prior C3 effect that reverses — without C3, NOT ASSERTED
    c5 = False
    if c3:
        # reliability ordering flipped and action delta flipped sign
        rel_flip = (met_a2.get("reliability_fn", 0) < met_b2.get("reliability_fn", 0)) != (
            primary["dist_A"].get("reliability_fn", 0) < primary["dist_B"].get("reliability_fn", 0)
        )
        sign_flip = (act_rev["delta_P_A_minus_B"] * act["delta_P_A_minus_B"]) < 0
        c5 = bool(rel_flip and sign_flip)
    out["C5_reliability_reversal"] = c5
    out["reversal_probe"] = {
        "dist_A_after": met_a2,
        "dist_B_after": met_b2,
        "action_after": act_rev,
        "value_A_after": va_r.get("ordinary_value"),
        "note": "Ordinary contradictory experience only; no semantic UPDATE_BELIEF",
    }

    # Leak
    out["leak_tokens"] = pr.audit_forbidden({
        "action_keys": list(act.keys()),
        "dist_keys": list(primary["dist_A"].keys()),
    })
    # Also audit that FORBIDDEN tokens aren't in store transition keys
    out["leak_tokens"] += pr.audit_forbidden({"tkeys": list(store.get("transitions", {}).keys())[:30]})

    # First unsupported arrow
    chain = [
        ("ordinary_experience", True),
        ("multiple_learned_predictive_continuations", c1),
        ("different_predictive_distributions", bool(primary["distributions_differ"])),
        ("matched_mean_distal_consequence", c2),
        ("differential_present_action_selection", c3),
    ]
    first = None
    for name, ok in chain:
        if not ok:
            first = name
            break
    out["first_unsupported_arrow"] = first or "NONE_ALL_SUPPORTED"
    out["claim_chain"] = chain

    # Information bottleneck note
    out["information_bottleneck"] = {
        "retained_in_store": ["mean (sum/n)", "var_sum", "pc.reliability(row) on one-step pred"],
        "used_by_action_logits": ["mean predicted_distal", "ordinary_state_value scalar", "softmax"],
        "not_used_by_action_logits": ["var_sum", "reliability", "outcome mixture modes"],
    }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--ticks", type=int, default=100, help="unused alias for Observer")
    args = ap.parse_args()
    seeds = args.seeds or SEEDS

    OUT.mkdir(parents=True, exist_ok=True)
    dump("CONFIG.json", {
        "update": "4.29",
        "seeds": seeds,
        "MATCHED_MEAN_TOLERANCE": pr.MATCHED_MEAN_TOLERANCE,
        "ACTION_DELTA_TOL": ACTION_DELTA_TOL,
        "N_SAMPLES": N_SAMPLES,
        "tolerance_rationale": (
            "MATCHED_MEAN_TOLERANCE=0.02 on ordinary_value pre-registered; "
            "ACTION_DELTA_TOL=0.03 for claiming action influence"
        ),
        "no_uncertainty_semantics": True,
        "unchanged_4_26_pathway": True,
        "DISTAL_BLEND": pci.DISTAL_BLEND,
        "DEFAULT_TEMPERATURE": pci.DEFAULT_TEMPERATURE,
    })

    per = [run_seed(s) for s in seeds]
    dump("per_seed_results.json", per)

    def sw(pred):
        return [str(r["seed"]) for r in per if pred(r)]

    claim = {
        "C1_multiple_outcome_structure": {
            "asserted": all(r["C1_multiple_outcome_structure"] for r in per),
            "seeds": sw(lambda r: r["C1_multiple_outcome_structure"]),
        },
        "C2_matched_expected_consequence": {
            "asserted": all(r["C2_matched_expected_consequence"] for r in per),
            "seeds": sw(lambda r: r["C2_matched_expected_consequence"]),
        },
        "C3_distributional_action_influence": {
            "asserted": all(r["C3_distributional_action_influence"] for r in per),
            "seeds": sw(lambda r: r["C3_distributional_action_influence"]),
        },
        "C4_selective_causal_dependence": {
            "asserted": all(r["C4_selective_causal_dependence"] for r in per),
            "seeds": sw(lambda r: r["C4_selective_causal_dependence"]),
        },
        "C5_experience_driven_reliability_reversal": {
            "asserted": all(r["C5_reliability_reversal"] for r in per),
            "seeds": sw(lambda r: r["C5_reliability_reversal"]),
        },
    }
    dump("claim_matrix.json", claim)

    dump("summary.json", {
        "claims": claim,
        "first_unsupported_arrows": [r["first_unsupported_arrow"] for r in per],
        "primary_deltas": {str(r["seed"]): r["C3_diagnostics"] for r in per},
        "seeds": seeds,
    })
    dump("condition_primary.json", {str(r["seed"]): r["primary"] for r in per})
    dump("controls.json", {str(r["seed"]): {
        "matched_distribution": r["control_matched_distribution"],
        "different_mean": r["control_different_mean"],
        "shuffle": r["shuffle_control"],
    } for r in per})
    dump("ablations.json", {str(r["seed"]): {
        "mean_only": r["ablation_mean_only_var_zeroed"],
        "collapse_mixture": r["ablation_collapse_mixture"],
    } for r in per})
    dump("leak_audit.json", {
        "per_seed": [{"seed": r["seed"], "tokens": r["leak_tokens"]} for r in per],
        "any_leak": any(r["leak_tokens"] for r in per),
    })
    dump("ACCEPTANCE_MATRIX.json", {
        "C1": claim["C1_multiple_outcome_structure"]["asserted"],
        "C2": claim["C2_matched_expected_consequence"]["asserted"],
        "C3": claim["C3_distributional_action_influence"]["asserted"],
        "C4": claim["C4_selective_causal_dependence"]["asserted"],
        "C5": claim["C5_experience_driven_reliability_reversal"]["asserted"],
        "no_forbidden": not any(r["leak_tokens"] for r in per),
        "pathway_426_alive": all(r["control_different_mean"]["pathway_426_alive"] for r in per),
    })
    dump("BASELINE_REGRESSION.json", {
        "preserve_4_25_C3_NOT_ASSERTED": True,
        "preserve_4_26_C4_NOT_ASSERTED": True,
        "preserve_4_28_C2_C3_C4_NOT_ASSERTED": True,
        "status": "NOT_FULLY_RE_RUN_IN_SMOKE",
        "note": "Do not rewrite prior FINAL_REPORTs; no variance term added to action_logits",
    })
    dump("INTEGRATION_PRESERVE.json", {
        "metrics_affect_cognition": False,
        "observer_telemetry_only": True,
        "no_uncertainty_in_cognition": True,
        "unchanged_DISTAL_BLEND": pci.DISTAL_BLEND,
        "unchanged_T": pci.DEFAULT_TEMPERATURE,
        "pc_reliability_exists_but_unused_by_action_logits": True,
    })

    obs = {
        "update": "4.29",
        "preset": "4.29 Predictive Reliability",
        "MATCHED_MEAN_TOLERANCE": pr.MATCHED_MEAN_TOLERANCE,
        "claim_matrix": claim,
        "DISTRIBUTIONAL_ACTION_INFLUENCE": (
            "OBSERVED" if claim["C3_distributional_action_influence"]["asserted"] else "NOT OBSERVED"
        ),
        "per_seed": {
            str(r["seed"]): {
                "value_A": r["primary"]["value_A"],
                "value_B": r["primary"]["value_B"],
                "abs_value_diff": r["primary"]["abs_value_diff"],
                "matched_mean": r["primary"]["matched_mean"],
                "var_A": (r["primary"]["dist_A"] or {}).get("mean_variance"),
                "var_B": (r["primary"]["dist_B"] or {}).get("mean_variance"),
                "rel_A": (r["primary"]["dist_A"] or {}).get("reliability_fn"),
                "rel_B": (r["primary"]["dist_B"] or {}).get("reliability_fn"),
                "P_A": r["primary"]["action"]["P_A"],
                "P_B": r["primary"]["action"]["P_B"],
                "delta_P": r["primary"]["action"]["delta_P_A_minus_B"],
            }
            for r in per
        },
        "information_bottleneck": per[0]["information_bottleneck"] if per else {},
        "first_unsupported_arrows": [r["first_unsupported_arrow"] for r in per],
        "layers": {
            "WORLD_TRUTH": "Mixture distal outcomes for A (consistent) vs B (conflicting)",
            "ACCESSIBLE_EVIDENCE": "Learned transitions only; full_sequence_exposure=0",
            "ACQUIRED_PREDICTIVE_CONTINUATIONS": "COMPOSED A/B chains; mean+var_sum retained",
            "RESEARCHER_ONLY_DISTRIBUTION_METRICS": "mean_variance, reliability_fn (not in logits)",
            "EXPECTED_DISTAL_VALUE": "ordinary_state_value of mean predicted_distal",
            "ACTION_LOGITS_PROBABILITIES": "unchanged 4.26 softmax",
            "ACTUAL_CONSEQUENCE": "see per_seed",
        },
    }
    dump("OBSERVER_RELIABILITY_SNAPSHOT.json", obs)

    lines = [
        "# Update 4.29 FINAL REPORT - Predictive Reliability",
        "",
        "## Architecture",
        "No new cognition variables. Existing 4.23 transitions retain mean + var_sum;",
        "pc.reliability(row) is computed on one-step predictions but is NOT consumed by",
        "4.26 action_logits (scalar ordinary_value of mean predicted_distal only).",
        "DISTAL_BLEND / T unchanged. No variance/reliability term added to force C3.",
        "",
        "## Experimental construction",
        f"MATCHED_MEAN_TOLERANCE = {pr.MATCHED_MEAN_TOLERANCE} (pre-registered).",
        f"ACTION_DELTA_TOL = {ACTION_DELTA_TOL}.",
        "A: 90/10 mid_hi/mid_lo; B: 50/50 extremes calibrated to matched channel mean.",
        "full_sequence_exposure_count = 0 for both chains.",
        "",
        "## Claims",
    ]
    for k, v in claim.items():
        st = "ASSERTED" if v["asserted"] else "NOT ASSERTED"
        lines.append(f"- {k}: **{st}** seeds={v['seeds']}")
    lines += ["", "## Per seed"]
    for r in per:
        p = r["primary"]
        lines.append(
            f"- seed {r['seed']}: matched={p['matched_mean']} dV={p['abs_value_diff']} "
            f"varA={ (p['dist_A'] or {}).get('mean_variance')} varB={ (p['dist_B'] or {}).get('mean_variance')} "
            f"dP={r['C3_diagnostics']['delta_P_A_minus_B']} "
            f"C1={r['C1_multiple_outcome_structure']} C2={r['C2_matched_expected_consequence']} "
            f"C3={r['C3_distributional_action_influence']} first={r['first_unsupported_arrow']} "
            f"426_alive={r['control_different_mean']['pathway_426_alive']}"
        )
    lines += [
        "",
        "## First unsupported arrow",
        f"Per seed: {[r['first_unsupported_arrow'] for r in per]}",
        "",
        "## Allowed NULL claim (if C3 false)",
        "Mechanistic Mind retained different predictive outcome structures (var_sum /",
        "reliability_fn differ), but those differences did not independently influence",
        "present action selection when expected distal consequence was matched. Action",
        "selection remained determined by the scalar consequence pathway from Update 4.26.",
        "",
        "## NOT claimed",
        "uncertainty / confidence / risk / doubt / metacognition / cautiousness",
        "",
        "## Historical preserve",
        "4.25 C3, 4.26 C4, 4.28 C2–C4 remain historical NULLs; not retuned.",
        "",
        "## Recommended next experiment",
        "Only if a future update introduces a generic pathway that preserves distributional",
        "structure into action WITHOUT semantic uncertainty — or investigate information-",
        "seeking under unavoidable physical evolution (explicitly deferred by 4.29 §22).",
        "",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(claim, indent=2))
    print("first", [r["first_unsupported_arrow"] for r in per])
    print("wrote", OUT)


if __name__ == "__main__":
    main()
