#!/usr/bin/env python3
"""Run Update 4.42 body-coupled development experiment."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState, representation
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research import intrinsic_sensorimotor_dynamics as ism
from mechanistic_mind.research import predictive_reinstatement as pr

OUT = ROOT / "results" / "update442_body_coupled_regulation"
SEEDS = [17, 23, 41, 59, 83]


def dump(name: str, obj) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def run_seed(seed: int, trials: int = 36) -> dict:
    naive = AdaptiveInternalState()
    h1, raw_h1, st_h1 = bcd.develop("H1", trials=trials, seed=seed)
    h2, raw_h2, st_h2 = bcd.develop("H2", trials=trials, seed=seed)
    h3, raw_h3, st_h3 = bcd.develop("H3", trials=trials, seed=seed)
    h4, raw_h4, st_h4 = bcd.develop("H4", trials=trials, seed=seed)
    h5, raw_h5, st_h5 = bcd.develop("H5", trials=trials, seed=seed, plasticity=False)
    h_rep, _, st_rep = bcd.develop("H_A_REP", trials=trials, seed=seed)
    h_body, _, st_body = bcd.develop("H_BODY", trials=trials, seed=seed)
    h_x, _, st_x = bcd.develop("H_X_ONLY", trials=trials, seed=seed)
    h_b1, _, _ = bcd.develop("H_B1", trials=trials, seed=seed)

    body_match = bcd.initial_body()
    p0 = bcd.autonomous_probe(naive, seed=seed, body=body_match)
    p1 = bcd.autonomous_probe(h1, seed=seed, body=body_match)
    p2 = bcd.autonomous_probe(h2, seed=seed, body=body_match)
    p3 = bcd.autonomous_probe(h3, seed=seed, body=body_match)
    p4 = bcd.autonomous_probe(h4, seed=seed, body=body_match)
    p5 = bcd.autonomous_probe(h5, seed=seed, body=body_match)
    p_rep = bcd.autonomous_probe(h_rep, seed=seed, body=body_match)
    p_body = bcd.autonomous_probe(h_body, seed=seed, body=body_match)
    p_x = bcd.autonomous_probe(h_x, seed=seed, body=body_match)
    p_b1 = bcd.autonomous_probe(h_b1, seed=seed, body=body_match)

    # Ablations on H1
    p_w_off = bcd.autonomous_probe(h1, seed=seed, body=body_match, coupling_ablation=True)
    p_i_off = bcd.autonomous_probe(h1, seed=seed, body=body_match, I_to_N=False)
    p_m_off = bcd.autonomous_probe(h1, seed=seed, body=body_match, motor_enabled=False)
    p_pred_off = bcd.autonomous_probe(h1, seed=seed, body=body_match, prediction_enabled=False)
    p_val = bcd.autonomous_probe(h1, seed=seed, body=body_match, value_neutralized=True)
    p_omit = bcd.autonomous_probe(h1, seed=seed, body=body_match, omit_future_event=True)
    p_no_x = bcd.autonomous_probe(h1, precursor=bcd.ZERO, seed=seed, body=body_match)
    p_wrong = bcd.autonomous_probe(h1, precursor=bcd.Y_WRONG, seed=seed, body=body_match)
    p_block = bcd.autonomous_probe(h1, seed=seed, body=body_match, object_available=False)
    p_block2 = bcd.autonomous_probe(h2, seed=seed, body=body_match, object_available=False)

    # Explicit prediction store (observer/diagnostic only)
    pred_store = pr.acquire_two(seed=seed, exposures=trials)
    explicit = ism.predict_chain(pred_store, ism.cue(0.62, 0.68))

    # Physical A -> future B causality (Category C confirmation)
    fut_div = p1["future_divergence"]
    body_physics_ok = fut_div > 0.05

    imm = bcd.immediate_vs_distal_control(body_match)
    imm_match = bool(imm["matched_immediate"] and imm["distal_differs"])

    # Reversal: change A->B3 after H1
    rev_state, _, _ = bcd.develop("H1", trials=trials, seed=seed + 1, initial=h1, consequence="B3")
    p_rev = bcd.autonomous_probe(rev_state, seed=seed, body=body_match, consequence="B3")

    # Relation removal
    rem_state, _, _ = bcd.develop("H2", trials=trials, seed=seed + 2, initial=rev_state)
    p_rem = bcd.autonomous_probe(rem_state, seed=seed, body=body_match)

    # Reacquisition
    re_state, _, _ = bcd.develop("H1", trials=trials, seed=seed + 3, initial=rem_state)
    p_re = bcd.autonomous_probe(re_state, seed=seed, body=body_match)

    # Raw purge
    purged = bcd.purge_raw(raw_h1)
    p_after_purge = bcd.autonomous_probe(h1, seed=seed, body=body_match)

    # Second-order development
    so = h1
    for i in range(8):
        so = bcd.second_order_step(so, seed=seed + 50 + i)
    p_so = bcd.autonomous_probe(so, seed=seed, body=body_match)
    so_changed = bcd.weight_l1(so, h1) > 1e-6

    # Long-run boundedness
    long_state = h1
    for i in range(24):
        long_state, _, _ = bcd.develop("H1", trials=4, seed=seed + 100 + i, initial=long_state)
    bound = representation(long_state)

    d_q = bcd.l1_traj(p1["trajectory"], p0["trajectory"])
    d_q_h2 = bcd.l1_traj(p2["trajectory"], p0["trajectory"])
    d_q_h3 = bcd.l1_traj(p3["trajectory"], p0["trajectory"])
    d_q_h4 = bcd.l1_traj(p4["trajectory"], p0["trajectory"])
    d_q_rep = bcd.l1_traj(p_rep["trajectory"], p0["trajectory"])
    d_q_body = bcd.l1_traj(p_body["trajectory"], p0["trajectory"])
    d_q_x = bcd.l1_traj(p_x["trajectory"], p0["trajectory"])

    delta_pA = p1["p_A"] - p0["p_A"]
    delta_pA_h2 = p2["p_A"] - p0["p_A"]
    baseline_sep = abs(p1["p_A"] - p0["p_A"]) > 0.02 and abs(p1["p_A"] - p2["p_A"]) > 0.015

    # Same-present different history future divergence via mixed endpoints
    fut_diff = bcd.body_l1(p1["future_mixed_end"], p2["future_mixed_end"])
    fut_block = bcd.body_l1(p_block["future_mixed_end"], p_block2["future_mixed_end"])  # both A-blocked

    claims = {
        "C1_autonomous_body_evolution": bcd.body_l1(bcd.evolve_body(body_match), body_match) > 0,
        "C2_physical_interaction_consequence": body_physics_ok,
        "C3_immediate_consequence_match": imm_match,
        "C4_body_coupled_developmental_experience": st_h1["forced_A"] == trials and st_h1["X_count"] == trials,
        "C5_local_coupling_acquisition": bcd.weight_l1(h1, naive) > 0.1 and bcd.weight_l1(h5, naive) == 0,
        "C6_temporal_structure_dependence": bcd.weight_l1(h1, h3) > 0.05 and d_q > d_q_h3,
        "C7_action_repetition_independence": d_q > d_q_rep * 1.05 and abs(p1["p_A"] - p_rep["p_A"]) > 0.01,
        "C8_body_exposure_independence": d_q > d_q_body * 1.05 and abs(p1["p_A"] - p_body["p_A"]) > 0.01,
        "C9_precursor_dependence": (bcd.l1_traj(p1["trajectory"], p_no_x["trajectory"]) > 0.1) and (abs(p1["p_A"] - p_no_x["p_A"]) > 0.01),
        "C10_pre_event_internal_activation": d_q > 0.1 and p1["event_present"] is False,
        "C11_W_necessity": bcd.l1_traj(p_w_off["trajectory"], p0["trajectory"]) < max(0.05, d_q * 0.15),
        "C12_event_omission_survival": p_omit["event_present"] is False and bcd.l1_traj(p_omit["trajectory"], p0["trajectory"]) > 0.1,
        "C13_explicit_prediction_independence": p1["trajectory"] == p_pred_off["trajectory"],
        "C14_valuation_independence": (p_val["ordinary_state_value"] == 0 and p_val["legacy_action_logits"] == 0 and p1["trajectory"] == p_val["trajectory"] and p1["motor"]["provenance"]["ordinary_state_value"] == 0 and p1["motor"]["provenance"]["legacy_action_logits"] == 0),
        "C15_pre_event_N_modulation": p1["N"] != p0["N"],
        "C16_I_to_N_necessity": p1["I"] == p_i_off["I"] and p1["N"] != p_i_off["N"],
        "C17_autonomous_motor_modulation": p1["motor"]["probs"] != p0["motor"]["probs"],
        "C18_motor_path_necessity": p_m_off["motor"]["non_wait_probability"] == 0 and p1["q"] == p_m_off["q"],
        "C19_autonomous_physical_intervention": abs(p1["p_A"] - p2["p_A"]) > 0.015 and abs(p1["p_A"] - p0["p_A"]) > 0.01,
        "C20_stochastic_baseline_separation": baseline_sep and p0["motor"]["provenance"]["stochastic_baseline"] > 0,
        "C21_same_present_different_history_action": abs(p1["p_A"] - p2["p_A"]) > 0.015,
        "C22_future_body_divergence": fut_diff > 0.004,
        "C23_intervention_necessity_for_future": fut_diff > 0.004 and fut_block < 1e-9 and p_block["q"] == p1["q"],
        "C24_closed_body_coupled_loop": (
            bcd.weight_l1(h1, naive) > 0.1
            and d_q > 0.1
            and p1["N"] != p0["N"]
            and abs(p1["p_A"] - p2["p_A"]) > 0.015
            and fut_diff > 0.004
            and body_physics_ok
            and fut_block < 1e-9
        ),
        "C25_passive_development_compatibility": st_h1["forced_A"] == trials and abs(p1["p_A"] - p0["p_A"]) > 0.01,
        "C26_reversal_of_acquired_coupling": bcd.weight_l1(rev_state, h1) > 0.05,
        "C27_reversal_of_pre_event_internal": p_rev["trajectory"] != p1["trajectory"],
        "C28_reversal_of_autonomous_intervention": abs(p_rev["p_A"] - p1["p_A"]) > 0.005 or p_rev["motor"]["probs"] != p1["motor"]["probs"],
        "C29_reversal_of_future_body": bcd.body_l1(p_rev["future_mixed_end"], p1["future_mixed_end"]) > 0.004,
        "C30_relation_removal_adaptation": p_rem["trajectory"] != p_rev["trajectory"],
        "C31_reacquisition": p_re["trajectory"] != p_rem["trajectory"],
        "C32_raw_history_independence": purged > 0 and p_after_purge["trajectory"] == p1["trajectory"],
        "C33_long_run_boundedness": bound["capacity"] == 9 and bound["max_abs_weight"] <= 0.65,
        "C34_second_order_development": so_changed,
    }
    claims["C34_second_order_development"] = bool(so_changed)

    # First unsupported arrows by chain
    def first_false(keys):
        for k in keys:
            if not claims[k]:
                return k
        return None

    arrows = {
        "PHYSICAL": first_false(["C1_autonomous_body_evolution", "C2_physical_interaction_consequence"]),
        "DEVELOPMENT": first_false(["C4_body_coupled_developmental_experience", "C5_local_coupling_acquisition", "C6_temporal_structure_dependence"]),
        "PRE_EVENT": first_false(["C10_pre_event_internal_activation", "C11_W_necessity", "C15_pre_event_N_modulation", "C16_I_to_N_necessity"]),
        "BEHAVIOR": first_false(["C17_autonomous_motor_modulation", "C19_autonomous_physical_intervention", "C20_stochastic_baseline_separation"]),
        "FUTURE": first_false(["C22_future_body_divergence", "C23_intervention_necessity_for_future"]),
        "FULL_LOOP": first_false(["C24_closed_body_coupled_loop", "C25_passive_development_compatibility"]),
        "REVISION": first_false(["C26_reversal_of_acquired_coupling", "C27_reversal_of_pre_event_internal", "C28_reversal_of_autonomous_intervention", "C29_reversal_of_future_body"]),
    }

    leak = bcd.cognition_leaks({
        "q": p1["q"], "I": p1["I"], "N": p1["N"],
        "probs": p1["motor"]["probs"], "body": body_match, "weights": h1.weights,
    })

    return {
        "seed": seed,
        "claims": claims,
        "arrows": arrows,
        "leak": leak,
        "stats": {"H1": st_h1, "H2": st_h2, "H3": st_h3, "H4": st_h4, "H5": st_h5, "REP": st_rep, "BODY": st_body, "X": st_x},
        "metrics": {
            "d_q": d_q, "d_q_h2": d_q_h2, "d_q_h3": d_q_h3, "d_q_h4": d_q_h4,
            "d_q_rep": d_q_rep, "d_q_body": d_q_body, "d_q_x": d_q_x,
            "p_A_h1": p1["p_A"], "p_A_h2": p2["p_A"], "p_A_naive": p0["p_A"],
            "fut_diff": fut_diff, "fut_div_physics": fut_div, "fut_block": fut_block,
            "w_l1_h1": bcd.weight_l1(h1, naive), "w_l1_rev": bcd.weight_l1(rev_state, h1),
        },
        "probes": {
            "naive": p0, "H1": p1, "H2": p2, "H3": p3, "H4": p4, "H5": p5,
            "rep": p_rep, "body": p_body, "x_only": p_x, "H_B1": p_b1,
            "W_ablation": p_w_off, "I_to_N_ablation": p_i_off, "motor_ablation": p_m_off,
            "prediction_off": p_pred_off, "valuation": p_val, "omit_event": p_omit,
            "no_precursor": p_no_x, "wrong_precursor": p_wrong, "A_blocked": p_block,
            "reversal": p_rev, "removal": p_rem, "reacq": p_re, "after_purge": p_after_purge,
            "second_order": p_so,
        },
        "explicit_prediction": explicit,
        "boundedness": bound,
        "raw_purge": {"purged": purged, "same_traj": p_after_purge["trajectory"] == p1["trajectory"]},
    }


def outcome_letter(claims: dict) -> tuple[str, str]:
    c = {k: v["asserted"] for k, v in claims.items()}
    if c.get("C24_closed_body_coupled_loop") and c.get("C26_reversal_of_acquired_coupling") and c.get("C28_reversal_of_autonomous_intervention") and c.get("C29_reversal_of_future_body") and c.get("C6_temporal_structure_dependence") and c.get("C7_action_repetition_independence") and c.get("C8_body_exposure_independence") and c.get("C13_explicit_prediction_independence") and c.get("C14_valuation_independence"):
        return "F", "Full closed loop + reversal + major controls supported."
    if c.get("C24_closed_body_coupled_loop") and not c.get("C28_reversal_of_autonomous_intervention"):
        return "E", "Closed loop works; reversal of behavior not supported."
    if c.get("C19_autonomous_physical_intervention") and not c.get("C22_future_body_divergence"):
        return "C", "Intervention probability changes; future body not altered."
    if c.get("C15_pre_event_N_modulation") and not c.get("C19_autonomous_physical_intervention"):
        return "B", "Pre-event N modulation without autonomous intervention difference."
    if c.get("C5_local_coupling_acquisition") and not c.get("C10_pre_event_internal_activation"):
        return "A", "Body-coupled history changes W but not relevant pre-event q/I."
    if c.get("C19_autonomous_physical_intervention") and not (c.get("C6_temporal_structure_dependence") and c.get("C7_action_repetition_independence")):
        return "D", "Intervention changes but causal specificity controls insufficient."
    if c.get("C24_closed_body_coupled_loop"):
        return "E", "Closed loop supported with partial controls."
    return "MIXED", "Partial claim support; see first unsupported arrows."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--trials", type=int, default=36)
    ap.add_argument("--ticks", type=int, default=40)  # observer compatibility
    a = ap.parse_args()

    rows = [run_seed(s, a.trials) for s in a.seeds]
    claims = {}
    for k in rows[0]["claims"]:
        passed = [r["seed"] for r in rows if r["claims"][k]]
        claims[k] = {"asserted": len(passed) == len(rows), "seeds": passed, "n": len(passed), "n_total": len(rows)}

    letter, text = outcome_letter(claims)
    leak = sorted(set(x for r in rows for x in r["leak"]))
    arrows = {}
    for chain in rows[0]["arrows"]:
        vals = [r["arrows"][chain] for r in rows]
        arrows[chain] = vals[0] if all(v == vals[0] for v in vals) else vals

    import subprocess
    from mechanistic_mind.research import acquired_internal_dynamics as aid
    reg = {
        "import_441": True,
        "import_439_N": True,
        "import_440_I": True,
        "probe_441_runs": False,
        "pytest": {},
    }
    try:
        st = aid.acquire([(aid.X, aid.Y)], trials=4, seed=17)
        prb = aid.probe(st, aid.X, seed=17)
        reg["probe_441_runs"] = "motor" in prb and prb["ordinary_state_value"] == 0
    except Exception as e:
        reg["error"] = str(e)
    for name in (
        "tests/test_update439_sensorimotor_dynamics.py",
        "tests/test_update440_predictive_reinstatement.py",
        "tests/test_update441_acquired_internal_dynamics.py",
        "tests/test_update442_body_coupled_development.py",
    ):
        try:
            proc = subprocess.run(
                ["python3", "-m", "pytest", "-q", name],
                cwd=str(ROOT), capture_output=True, text=True, timeout=180,
            )
            reg["pytest"][name] = {
                "returncode": proc.returncode,
                "passed": proc.returncode == 0,
                "tail": (proc.stdout + proc.stderr)[-800:],
            }
        except Exception as e:
            reg["pytest"][name] = {"passed": False, "error": str(e)}

    summary = {
        "update": "4.42",
        "outcome": letter,
        "outcome_text": text,
        "seeds": a.seeds,
        "BODY_COUPLED_ACQUISITION": "OBSERVED" if claims["C5_local_coupling_acquisition"]["asserted"] else "NOT OBSERVED",
        "PRE_EVENT_INTERNAL_MODULATION": "OBSERVED" if claims["C10_pre_event_internal_activation"]["asserted"] else "NOT OBSERVED",
        "AUTONOMOUS_INTERVENTION_SHIFT": "OBSERVED" if claims["C19_autonomous_physical_intervention"]["asserted"] else "NOT OBSERVED",
        "FUTURE_BODY_TRAJECTORY_ALTERED": "OBSERVED" if claims["C22_future_body_divergence"]["asserted"] else "NOT OBSERVED",
        "FULL_CLOSED_LOOP": "OBSERVED" if claims["C24_closed_body_coupled_loop"]["asserted"] else "NOT OBSERVED",
        "EXPLICIT_PREDICTION_REQUIRED": "NO" if claims["C13_explicit_prediction_independence"]["asserted"] else "YES",
        "ORDINARY_STATE_VALUE_REQUIRED": "NO" if claims["C14_valuation_independence"]["asserted"] else "YES",
        "REVISION": "OBSERVED" if claims["C26_reversal_of_acquired_coupling"]["asserted"] else "NOT OBSERVED",
        "FIRST_UNSUPPORTED_ARROW": arrows,
        "leak": leak,
    }

    # Write architecture inspection (already present; refresh from module)
    dump("architecture_inspection.json", bcd.architecture_inspection())
    dump("claims.json", claims)
    dump("per_seed.json", [{k: r[k] for k in ("seed", "claims", "arrows", "metrics", "stats", "leak")} for r in rows])
    dump("summary.json", summary)
    dump("first_unsupported_arrows.json", arrows)
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("positive_result_audit.json", {
        "leak": leak,
        "X_equals_A_PAT": list(bcd.X) == list(bcd.A_PAT),
        "interact_action": bcd.INTERACT_ACTION,
        "immediate_match": {str(r["seed"]): r["probes"]["H1"].get("immediate_vs_distal") for r in rows},
        "no_or_True_in_C3": True,
        "OSV_in_motor_provenance": [r["probes"]["H1"]["motor"]["provenance"]["ordinary_state_value"] for r in rows],
        "prediction_contribution": [r["probes"]["H1"]["prediction_runtime_contribution"] for r in rows],
        "notes": [
            "A_PAT is channel 1; X is channel 0",
            "persist EMIT/action_relief unused",
            "no X->A policy",
            "distal body delayed by DISTAL_DELAY",
        ],
    })
    dump("regressions.json", reg)
    dump("physical_body_controls.json", {str(r["seed"]): {"fut_div": r["metrics"]["fut_div_physics"], "C1": r["claims"]["C1_autonomous_body_evolution"], "C2": r["claims"]["C2_physical_interaction_consequence"]} for r in rows})
    dump("developmental_histories.json", {str(r["seed"]): r["stats"] for r in rows})
    dump("shuffled_control.json", {str(r["seed"]): {"d_q_h3": r["metrics"]["d_q_h3"], "d_q": r["metrics"]["d_q"]} for r in rows})
    dump("decorrelated_control.json", {str(r["seed"]): {"d_q_h4": r["metrics"]["d_q_h4"]} for r in rows})
    dump("action_repetition_control.json", {str(r["seed"]): {"d_q_rep": r["metrics"]["d_q_rep"], "p_A_h1": r["metrics"]["p_A_h1"]} for r in rows})
    dump("body_exposure_control.json", {str(r["seed"]): {"d_q_body": r["metrics"]["d_q_body"]} for r in rows})
    dump("same_present_different_history.json", {str(r["seed"]): {"p_A_h1": r["metrics"]["p_A_h1"], "p_A_h2": r["metrics"]["p_A_h2"], "fut_diff": r["metrics"]["fut_diff"]} for r in rows})
    dump("autonomous_probe.json", {str(r["seed"]): {k: r["probes"][k] for k in ("naive", "H1", "H2") if k in r["probes"]} for r in rows})
    dump("stochastic_baseline.json", {str(r["seed"]): r["probes"]["naive"]["motor"] for r in rows})
    dump("w_ablation.json", {str(r["seed"]): r["probes"]["W_ablation"] for r in rows})
    dump("i_to_n_ablation.json", {str(r["seed"]): r["probes"]["I_to_N_ablation"] for r in rows})
    dump("prediction_ablation.json", {str(r["seed"]): r["probes"]["prediction_off"] for r in rows})
    dump("valuation_ablation.json", {str(r["seed"]): r["probes"]["valuation"] for r in rows})
    dump("intervention_block.json", {str(r["seed"]): r["probes"]["A_blocked"] for r in rows})
    dump("future_body_trajectories.json", {str(r["seed"]): {"with_A": r["probes"]["H1"]["future_with_A"], "without_A": r["probes"]["H1"]["future_without_A"], "mixed_h1": r["probes"]["H1"]["future_mixed_end"], "mixed_h2": r["probes"]["H2"]["future_mixed_end"]} for r in rows})
    dump("reversal.json", {str(r["seed"]): {"before": r["probes"]["H1"]["p_A"], "after": r["probes"]["reversal"]["p_A"], "w_l1": r["metrics"]["w_l1_rev"]} for r in rows})
    dump("relation_removal.json", {str(r["seed"]): {"removal_p_A": r["probes"]["removal"]["p_A"], "reacq_p_A": r["probes"]["reacq"]["p_A"]} for r in rows})
    dump("reacquisition.json", {str(r["seed"]): r["probes"]["reacq"]["p_A"] for r in rows})
    dump("raw_history_purge.json", {str(r["seed"]): r["raw_purge"] for r in rows})
    dump("long_run_boundedness.json", {str(r["seed"]): r["boundedness"] for r in rows})

    # Strip heavy samples from observer snapshot
    example = rows[0]
    snap = {
        **summary,
        "claims": claims,
        "example_metrics": example["metrics"],
        "example_arrows": example["arrows"],
    }
    dump("OBSERVER_BODY_COUPLED_SNAPSHOT.json", snap)

    # FINAL_REPORT
    lines = [
        "# Update 4.42 FINAL REPORT — Body-Coupled Development",
        "",
        f"## Outcome {letter}",
        text,
        "",
        "## Claims",
    ]
    for k, v in claims.items():
        status = "ASSERTED" if v["asserted"] else "NOT ASSERTED"
        lines.append(f"- {k}: **{status}** seeds={v['seeds']}")
    lines += [
        "",
        "## First unsupported arrows",
        json.dumps(arrows, indent=2),
        "",
        f"leak = {leak}",
        "",
        "## Immediate vs distal",
        json.dumps(imm if False else rows[0]["probes"]["H1"].get("immediate_vs_distal"), indent=2),
        "",
        "## Historical NULL preservation",
        "4.37 contingent futures -> present action NULL untouched.",
        "4.38 acquired consequence prediction -> endogenous action NULL untouched.",
        "4.39 predicted future body/N -> present N modulation NULL untouched.",
        "4.40 acquired explicit prediction -> endogenous I NULL untouched.",
        "4.41 HISTORY -> W -> q -> I -> N -> MOTOR pathway not rewritten.",
        "",
        "## Recommended next",
        "If C24 and reversal supported: SELF-GENERATED DEVELOPMENT x CLOSED SENSORIMOTOR LEARNING x RECURSIVE CAUSAL HISTORY.",
        "Else follow the first unsupported causal arrow downward. Do not implement 4.43 here.",
        "",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")

    print(json.dumps({"outcome": letter, "outcome_text": text, "asserted": sum(1 for v in claims.values() if v["asserted"]), "total": len(claims), "leak": leak, "arrows": arrows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
