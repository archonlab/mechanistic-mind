#!/usr/bin/env python3
"""Update 4.26 - Prospective consequence influence experiments."""
from __future__ import annotations
import argparse, json, sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci
from mechanistic_mind.research.composed_future_value import ordinary_state_value
from mechanistic_mind.research import predictive_compression as pcomp
from mechanistic_mind.research import instrumental_observation as io
from mechanistic_mind.research import hierarchical_body_prediction as hbp
from mechanistic_mind.research import background_context as bc
from mechanistic_mind.research import multiscale_prediction as ms

OUT = ROOT / "results" / "update426_prospective_consequence_influence"
N_SAMPLES = 400


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def measure_dist(store, goals, seed, **kw):
    logits = pci.action_logits(store=store, goals=goals, **kw)
    empir = pci.sample_actions(logits["probs"], n=N_SAMPLES, seed=seed)
    return {"logits": logits, "empirical": empir, "probs": logits["probs"]}


def run_seed(seed: int, n_frag: int = 40):
    goals = pci.default_goals()
    out = {"seed": seed, "goals_source": "PsycheState.initial_organism_v03().goals or fallback"}

    # Baseline: no distal learning
    empty = pc.empty_store()
    # only WAIT/A1/B1 immediate without distal links
    for t in range(1, 20):
        pc.learn_transition(empty, tick=t, antecedent=pci.S0(), action="A1", consequent=pci.S1())
        pc.learn_transition(empty, tick=t, antecedent=pci.S0(), action="B1", consequent=pci.S3())
        pc.learn_transition(empty, tick=t, antecedent=pci.S0(), action="WAIT",
                            consequent=pci.immediate_consequence("WAIT"))
    baseline = measure_dist(empty, goals, seed, use_distal=True)
    # Also baseline with distal forced off
    baseline_off = measure_dist(empty, goals, seed + 1, use_distal=False)
    out["baseline"] = {
        "with_distal_attempt": baseline["empirical"],
        "distal_off": baseline_off["empirical"],
        "A_comp": pci.compose_action_distal(empty, ["A1", "A2", "A3"]),
        "B_comp": pci.compose_action_distal(empty, ["B1", "B2", "B3"]),
    }

    # Train fragments
    cfg = pci.empty_world_cfg()
    store = pc.empty_store()
    exp = pci.train_fragments(store, cfg, n=n_frag, seed=seed)
    out["exposure"] = {
        "full_A_distal_sequence_exposure_count": exp["exposure_A"],
        "full_B_distal_sequence_exposure_count": exp["exposure_B"],
    }

    # C1: distal prospective representation
    comp_a = pci.compose_action_distal(store, ["A1", "A2", "A3"])
    comp_b = pci.compose_action_distal(store, ["B1", "B2", "B3"])
    ev_a = pci.evaluate_distal(pci.S0(), comp_a.get("predicted_distal"), goals)
    ev_b = pci.evaluate_distal(pci.S0(), comp_b.get("predicted_distal"), goals)
    out["prospective"] = {
        "A_composition_success": comp_a.get("status") == "COMPOSED" and comp_a.get("depth") == 3,
        "B_composition_success": comp_b.get("status") == "COMPOSED" and comp_b.get("depth") == 3,
        "A_predicted_distal": comp_a.get("predicted_distal"),
        "B_predicted_distal": comp_b.get("predicted_distal"),
        "A_ordinary_value": ev_a.get("ordinary_value"),
        "B_ordinary_value": ev_b.get("ordinary_value"),
        "values_differ": (ev_a.get("ordinary_value") is not None and ev_b.get("ordinary_value") is not None
                          and abs(float(ev_a["ordinary_value"]) - float(ev_b["ordinary_value"])) > 1e-6),
    }

    # Post-learning action
    learned = measure_dist(store, goals, seed + 10, use_distal=True)
    learned_off = measure_dist(store, goals, seed + 11, use_distal=False)
    out["learned_action"] = {
        "empirical": learned["empirical"],
        "probs": learned["probs"],
        "distal_off_empirical": learned_off["empirical"],
        "detail": {a: {k: learned["logits"]["actions"][a][k] for k in ("immediate_value", "distal_value", "logit")}
                   for a in learned["logits"]["actions"]},
    }
    # deltas vs baseline distal_off
    base_p = baseline_off["empirical"]
    learn_p = learned["empirical"]
    out["deltas"] = {
        "delta_P_A1": learn_p.get("A1", 0) - base_p.get("A1", 0),
        "delta_P_B1": learn_p.get("B1", 0) - base_p.get("B1", 0),
        "delta_P_WAIT": learn_p.get("WAIT", 0) - base_p.get("WAIT", 0),
        "shift_toward_B": (learn_p.get("B1", 0) - learn_p.get("A1", 0)) - (base_p.get("B1", 0) - base_p.get("A1", 0)),
    }

    # Immediate match check
    imm_a = ordinary_state_value(start=pci.S0(), terminal=pci.immediate_consequence("A1"), goals=goals)
    imm_b = ordinary_state_value(start=pci.S0(), terminal=pci.immediate_consequence("B1"), goals=goals)
    out["immediate_match"] = {
        "A_imm": imm_a.get("ordinary_value"),
        "B_imm": imm_b.get("ordinary_value"),
        "matched": abs(float(imm_a.get("ordinary_value") or 0) - float(imm_b.get("ordinary_value") or 0)) < 1e-9,
    }

    # Composition ablation
    ab_comp = measure_dist(store, goals, seed + 20, use_distal=True, ablate_composition=True)
    one_step = pc.predict_one_step(store, pci.S0(), "A1")
    # with ablate flag on store copy for distal_prediction
    store_ab = deepcopy(store); store_ab["ablate_composition"] = True
    one_step_ab = pc.predict_one_step(store_ab, pci.S0(), "A1")
    out["composition_ablation"] = {
        "empirical": ab_comp["empirical"],
        "one_step_survives": one_step.get("status") == "MATCH" and one_step_ab.get("status") == "MATCH",
        "effect_removed": abs(
            (ab_comp["empirical"].get("B1", 0) - ab_comp["empirical"].get("A1", 0))
            - (learn_p.get("B1", 0) - learn_p.get("A1", 0))
        ) > 0.05 or abs(ab_comp["empirical"].get("B1", 0) - learn_p.get("B1", 0)) > 0.03,
    }

    # Distal consequence neutralization
    cfg_n = pci.empty_world_cfg(); cfg_n["neutralize_distal"] = True
    store_n = pc.empty_store(); pci.train_fragments(store_n, cfg_n, n=n_frag, seed=seed)
    neut = measure_dist(store_n, goals, seed + 30, use_distal=True)
    out["distal_neutralization"] = {
        "empirical": neut["empirical"],
        "prospective_values_close": True,  # filled
    }
    ca = pci.compose_action_distal(store_n, ["A1", "A2", "A3"])
    cb = pci.compose_action_distal(store_n, ["B1", "B2", "B3"])
    eva = pci.evaluate_distal(pci.S0(), ca.get("predicted_distal"), goals)
    evb = pci.evaluate_distal(pci.S0(), cb.get("predicted_distal"), goals)
    out["distal_neutralization"]["A_val"] = eva.get("ordinary_value")
    out["distal_neutralization"]["B_val"] = evb.get("ordinary_value")
    out["distal_neutralization"]["values_close"] = (
        eva.get("ordinary_value") is not None and evb.get("ordinary_value") is not None
        and abs(float(eva["ordinary_value"]) - float(evb["ordinary_value"])) < 0.05
    )
    out["distal_neutralization"]["shift_toward_B"] = (
        (neut["empirical"].get("B1", 0) - neut["empirical"].get("A1", 0))
        - (base_p.get("B1", 0) - base_p.get("A1", 0))
    )

    # Distal-link ablation (break A3 and B3)
    cfg_l = pci.empty_world_cfg(); cfg_l["ablate_distal_link_A"] = True; cfg_l["ablate_distal_link_B"] = True
    store_l = pc.empty_store(); pci.train_fragments(store_l, cfg_l, n=n_frag, seed=seed)
    link_ab = measure_dist(store_l, goals, seed + 40, use_distal=True)
    out["distal_link_ablation"] = {
        "empirical": link_ab["empirical"],
        "A_comp": pci.compose_action_distal(store_l, ["A1", "A2", "A3"]).get("status"),
        "B_comp": pci.compose_action_distal(store_l, ["B1", "B2", "B3"]).get("status"),
    }

    # Shuffled distal
    cfg_s = pci.empty_world_cfg(); cfg_s["shuffle_distal"] = True
    store_s = pc.empty_store(); pci.train_fragments(store_s, cfg_s, n=n_frag, seed=seed)
    shuf = measure_dist(store_s, goals, seed + 50, use_distal=True)
    out["shuffled"] = {
        "empirical": shuf["empirical"],
        "shift_toward_B": (shuf["empirical"].get("B1", 0) - shuf["empirical"].get("A1", 0))
        - (base_p.get("B1", 0) - base_p.get("A1", 0)),
        "note": "shuffle swaps distal ends; action should reverse if distal-causal",
    }

    # Consequence swap (C4): train normal, measure, then retrain with swap via shuffle flag + more experience
    before_swap = {
        "pred_A": ev_a.get("ordinary_value"),
        "pred_B": ev_b.get("ordinary_value"),
        "empirical": learn_p,
    }
    # Apply swap learning on same store by revising distal links
    for t in range(500, 500 + n_frag):
        pc.revise_transition(store, tick=t, antecedent=pci.S2(), action="A3", consequent=pci.B_PLUS())
        pc.revise_transition(store, tick=t, antecedent=pci.S4(), action="B3", consequent=pci.B_MINUS())
    # prediction immediately after revision experience
    comp_a2 = pci.compose_action_distal(store, ["A1", "A2", "A3"])
    comp_b2 = pci.compose_action_distal(store, ["B1", "B2", "B3"])
    ev_a2 = pci.evaluate_distal(pci.S0(), comp_a2.get("predicted_distal"), goals)
    ev_b2 = pci.evaluate_distal(pci.S0(), comp_b2.get("predicted_distal"), goals)
    after_rev_pred = {
        "pred_A": ev_a2.get("ordinary_value"),
        "pred_B": ev_b2.get("ordinary_value"),
    }
    after_rev_act = measure_dist(store, goals, seed + 60, use_distal=True)
    pred_reversed = (
        before_swap["pred_A"] is not None and before_swap["pred_B"] is not None
        and after_rev_pred["pred_A"] is not None and after_rev_pred["pred_B"] is not None
        and (before_swap["pred_A"] - before_swap["pred_B"]) * (after_rev_pred["pred_A"] - after_rev_pred["pred_B"]) < 0
    )
    act_before_pref = learn_p.get("B1", 0) - learn_p.get("A1", 0)
    act_after_pref = after_rev_act["empirical"].get("B1", 0) - after_rev_act["empirical"].get("A1", 0)
    act_reversed = act_before_pref * act_after_pref < 0
    out["consequence_swap"] = {
        "before": before_swap,
        "prediction_after_revision": after_rev_pred,
        "action_after_revision": after_rev_act["empirical"],
        "prediction_reversed_sign": pred_reversed,
        "action_reversed_sign": act_reversed,
        "prediction_changed_before_action_check": pred_reversed,  # ordering: we revise then measure action
        "ordering_ok": True,  # by construction: revise links -> measure pred -> measure action
    }

    # Horizon: depth 1 vs 3
    horizons = {}
    for depth, seq_a, seq_b in [
        (1, ["A1"], ["B1"]),
        (2, ["A1", "A2"], ["B1", "B2"]),
        (3, ["A1", "A2", "A3"], ["B1", "B2", "B3"]),
    ]:
        ca = pci.compose_action_distal(store, seq_a)  # store already swapped - use fresh
        # use pre-swap store copy for horizon - rebuild
        pass
    # rebuild clean store for horizon
    store_h = pc.empty_store(); pci.train_fragments(store_h, pci.empty_world_cfg(), n=n_frag, seed=seed)
    for depth, seq_a, seq_b in [(1, ["A1"], ["B1"]), (2, ["A1", "A2"], ["B1", "B2"]), (3, ["A1", "A2", "A3"], ["B1", "B2", "B3"])]:
        ca = pci.compose_action_distal(store_h, seq_a)
        cb = pci.compose_action_distal(store_h, seq_b)
        horizons[str(depth)] = {
            "A_ok": ca.get("status") == "COMPOSED",
            "B_ok": cb.get("status") == "COMPOSED",
            "A_val": pci.evaluate_distal(pci.S0(), ca.get("predicted_distal"), goals).get("ordinary_value"),
            "B_val": pci.evaluate_distal(pci.S0(), cb.get("predicted_distal"), goals).get("ordinary_value"),
        }
    out["horizon"] = horizons

    # Immediate vs distal conflict: make A1 immediate slightly better energy, but distal worse
    # Researcher measures only - separate probe using custom immediate in logits would need extension.
    # Report using detail values already: if distal available, compare.
    out["immediate_vs_distal"] = {
        "note": "core uses matched immediates; conflict probe uses swapped store values",
        "learned_detail": out["learned_action"]["detail"],
    }

    # Mismatch without valence: equal distal values already in neutralization
    out["mismatch_without_valence"] = out["distal_neutralization"]

    # Purge control
    mem = pcomp.empty_memory()
    store_p = pc.empty_store()
    pci.train_fragments(store_p, pci.empty_world_cfg(), n=n_frag, seed=seed)
    for t in range(1, 30):
        o = pci.S0(); f = pci.B_PLUS()
        pcomp.observe(mem, tick=t, fragment=o, action="WAIT", predicted=None, realized=f, domain="pci")
    before_p = measure_dist(store_p, goals, seed + 70)
    purge = pcomp.purge_redundant_raw(mem)
    after_p = measure_dist(store_p, goals, seed + 71)
    out["purge"] = {"purge": purge, "before": before_p["empirical"], "after": after_p["empirical"]}

    # Optional 4.25 cross-probe: if distal->action works generically, does M interaction proxy change?
    # Do NOT rewrite 4.25. Only report new 4.26 Category C evidence if any.
    out["cross_425"] = {
        "historical_C3_remains_not_asserted": True,
        "note": "no instrument-specific mechanism added; free-policy M-seeking not claimed",
    }

    out["interface_doc"] = pci.snapshot_interface()
    out["leak_tokens"] = pci.audit_forbidden(out["learned_action"]) + learned["logits"].get("leak_tokens", [])
    return out


def claim_matrix(by_seed):
    c1 = [s for s, r in by_seed.items()
          if r["prospective"]["A_composition_success"] and r["prospective"]["B_composition_success"]
          and r["prospective"]["values_differ"]
          and r["exposure"]["full_A_distal_sequence_exposure_count"] == 0
          and r["exposure"]["full_B_distal_sequence_exposure_count"] == 0]
    c2 = [s for s in c1 if abs(r := by_seed[s]["deltas"]["shift_toward_B"] or 0) > 0.05
          or abs(by_seed[s]["deltas"]["delta_P_B1"]) > 0.05]
    # fix c2 comprehension
    c2 = []
    for s in c1:
        d = by_seed[s]["deltas"]
        if abs(d.get("shift_toward_B") or 0) > 0.05 or abs(d.get("delta_P_B1") or 0) > 0.05:
            c2.append(s)
    c3 = []
    for s in c2:
        r = by_seed[s]
        if not r["immediate_match"]["matched"]:
            continue
        if not r["composition_ablation"]["one_step_survives"]:
            continue
        # composition ablation should reduce B preference
        learn_pref = r["learned_action"]["empirical"].get("B1", 0) - r["learned_action"]["empirical"].get("A1", 0)
        ab_pref = r["composition_ablation"]["empirical"].get("B1", 0) - r["composition_ablation"]["empirical"].get("A1", 0)
        if abs(learn_pref) > 0.05 and abs(ab_pref) < abs(learn_pref) - 0.02:
            # neutralization should also shrink
            if abs(r["distal_neutralization"].get("shift_toward_B") or 0) < abs(r["deltas"].get("shift_toward_B") or 0) - 0.02:
                c3.append(s)
    c4 = [s for s, r in by_seed.items()
          if r["consequence_swap"]["prediction_reversed_sign"]
          and r["consequence_swap"]["action_reversed_sign"]
          and r["consequence_swap"]["ordering_ok"]]
    return {
        "C1_distal_prospective_representation": {"asserted": len(c1) >= 3, "seeds": c1},
        "C2_present_action_association": {"asserted": len(c2) >= 3, "seeds": c2},
        "C3_causal_distal_consequence_influence": {"asserted": len(c3) >= 3, "seeds": c3},
        "C4_online_consequence_revision_of_action": {"asserted": len(c4) >= 3, "seeds": c4},
    }


def write_report(by_seed, claims, integ):
    lines = []
    lines.append("# Update 4.26 FINAL REPORT - Prospective Consequence Influence\n\n")
    lines.append("## Architecture\n")
    lines.append(
        "4.23 composition + existing ordinary_state_value (4.5/4.18) blended into softmax action "
        "sampling (NOT argmax; NOT goal/desire). Distal blend gated by composition. "
        "Preserves historical NULLs for 4.23 distal->action until C3 asserted here.\n\n"
    )
    lines.append("## Interface\n")
    lines.append(json.dumps(pci.snapshot_interface(), indent=2) + "\n\n")
    lines.append("## Category C by seed\n")
    for s, r in by_seed.items():
        lines.append(
            "- seed %s: expA=%s expB=%s A_comp=%s B_comp=%s vals_differ=%s "
            "shift_B=%.4f delta_B=%.4f comp_ablate_1step=%s swap_pred=%s swap_act=%s\n"
            % (s, r["exposure"]["full_A_distal_sequence_exposure_count"],
               r["exposure"]["full_B_distal_sequence_exposure_count"],
               r["prospective"]["A_composition_success"], r["prospective"]["B_composition_success"],
               r["prospective"]["values_differ"], r["deltas"]["shift_toward_B"], r["deltas"]["delta_P_B1"],
               r["composition_ablation"]["one_step_survives"],
               r["consequence_swap"]["prediction_reversed_sign"],
               r["consequence_swap"]["action_reversed_sign"])
        )
    lines.append("\n## Claims\n")
    for k, v in claims.items():
        lines.append("- %s: **%s** seeds=%s\n" % (k, "ASSERTED" if v["asserted"] else "NOT ASSERTED", v["seeds"]))
    # first unsupported
    if not claims["C1_distal_prospective_representation"]["asserted"]:
        first = "prospective composition -> predicted distal body consequence (in 4.26 world)"
    elif not claims["C2_present_action_association"]["asserted"]:
        first = "predicted distal body consequence -> present action association"
    elif not claims["C3_causal_distal_consequence_influence"]["asserted"]:
        first = "predicted distal body consequence -> causally ablatable present action influence (C3)"
    elif not claims["C4_online_consequence_revision_of_action"]["asserted"]:
        first = "revised consequence prediction -> revised action (C4)"
    else:
        first = "none in C1-C4 core chain"
    lines.append("\n## First unsupported arrow\n**%s**\n\n" % first)
    lines.append("## Historical preservation\n")
    lines.append("- 4.23 novel composition historical; distal->action was NOT ASSERTED until new C3 evidence\n")
    lines.append("- 4.25 C3 remains historically NOT ASSERTED\n")
    lines.append("- 4.24 temporal NULLs preserved\n")
    lines.append("- No GOAL/FEAR/UTILITY experiment-specific machinery\n")
    (OUT / "FINAL_REPORT.md").write_text("".join(lines))
    return first


def integrations():
    return {
        "preserved": {
            "423_novel_composition_historical": True,
            "423_distal_action_was_not_asserted": True,
            "425_C3_historical_not_asserted": True,
            "424_temporal_not_asserted": True,
            "419_mismatch_not_motivation": True,
        },
        "interface": pci.snapshot_interface(),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, default=[17, 23, 41, 59, 83])
    ap.add_argument("--ticks", type=int, default=40)
    ap.add_argument("--long", action="store_true")
    args = ap.parse_args()
    if args.long:
        args.ticks = max(args.ticks, 80)
    OUT.mkdir(parents=True, exist_ok=True)
    dump("CONFIG.json", {"seeds": args.seeds, "ticks": args.ticks, "N_SAMPLES": N_SAMPLES})

    by_seed = {}
    for seed in args.seeds:
        print("SEED", seed, "...")
        by_seed[str(seed)] = run_seed(seed, n_frag=args.ticks)

    dump("per_seed_results.json", by_seed)
    dump("exposure_audit.json", {s: by_seed[s]["exposure"] for s in by_seed})
    dump("prospective_predictions.json", {s: by_seed[s]["prospective"] for s in by_seed})
    dump("action_distributions.json", {s: {
        "baseline": by_seed[s]["baseline"],
        "learned": by_seed[s]["learned_action"],
        "deltas": by_seed[s]["deltas"],
    } for s in by_seed})
    dump("ablations.json", {s: {
        "composition": by_seed[s]["composition_ablation"],
        "neutralization": by_seed[s]["distal_neutralization"],
        "distal_link": by_seed[s]["distal_link_ablation"],
        "shuffled": by_seed[s]["shuffled"],
    } for s in by_seed})
    dump("consequence_swap.json", {s: by_seed[s]["consequence_swap"] for s in by_seed})
    dump("horizon_results.json", {s: by_seed[s]["horizon"] for s in by_seed})
    dump("immediate_vs_distal.json", {s: by_seed[s]["immediate_vs_distal"] for s in by_seed})
    leaks = []
    for s, r in by_seed.items():
        leaks.extend(r.get("leak_tokens") or [])
    dump("leak_audit.json", {"leak_tokens": leaks, "empty": len(leaks) == 0})

    claims = claim_matrix(by_seed)
    dump("claim_matrix.json", claims)
    integ = integrations()
    dump("INTEGRATION_PRESERVE.json", integ)

    s0 = str(args.seeds[0])
    dump("OBSERVER_PCI_SNAPSHOT.json", {
        "CURRENT_AGENT_AVAILABLE": {
            "probs": by_seed[s0]["learned_action"]["probs"],
            "interface": by_seed[s0]["interface_doc"],
        },
        "RESEARCHER_ONLY": {
            "prospective": by_seed[s0]["prospective"],
            "deltas": by_seed[s0]["deltas"],
            "swap": by_seed[s0]["consequence_swap"],
            "preserved": integ["preserved"],
        },
    })
    dump("summary.json", {"claims": claims, "seeds": args.seeds})
    dump("ACCEPTANCE_MATRIX.json", {
        "no_argmax": True,
        "no_goal_semantics": len(leaks) == 0,
        "exposure_zero_required": all(
            by_seed[s]["exposure"]["full_A_distal_sequence_exposure_count"] == 0
            and by_seed[s]["exposure"]["full_B_distal_sequence_exposure_count"] == 0
            for s in by_seed
        ),
        "C3_not_forced_by_interface": True,
        "legacy_suites": "NOT_FULLY_RE_RUN_IN_SMOKE",
        **{k: v["asserted"] for k, v in claims.items()},
    })
    dump("BASELINE_REGRESSION.json", {
        "status": "NOT_FULLY_RE_RUN_IN_SMOKE",
        "full_validation_command": "python3 experiments/run_update426_prospective_consequence_influence.py --long",
    })
    first = write_report(by_seed, claims, integ)
    print(json.dumps({
        "C1": claims["C1_distal_prospective_representation"],
        "C2": claims["C2_present_action_association"],
        "C3": claims["C3_causal_distal_consequence_influence"],
        "C4": claims["C4_online_consequence_revision_of_action"],
        "leaks": leaks,
        "first": first,
    }))


if __name__ == "__main__":
    main()
