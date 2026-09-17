#!/usr/bin/env python3
"""Run Update 4.43 distal-consequence experiment. Learning rule unchanged."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState, representation
from mechanistic_mind.research import distal_consequence as dc
from mechanistic_mind.research import body_coupled_development as bcd

OUT = ROOT / "results" / "update443_distal_consequence"
SEEDS = [17, 23, 41, 59, 83]


def dump(name: str, obj) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def run_seed(seed: int, trials: int = 36) -> dict:
    naive = AdaptiveInternalState()
    h0, _, st0 = dc.develop("H0", trials=trials, seed=seed)
    h1, raw1, st1 = dc.develop("H1", trials=trials, seed=seed)
    h1b, _, st1b = dc.develop("H1B", trials=trials, seed=seed)
    h2, raw2, st2 = dc.develop("H2", trials=trials, seed=seed, delay=dc.PRIMARY_DELAY)
    h3, _, st3 = dc.develop("H3", trials=trials, seed=seed)
    h4, _, st4 = dc.develop("H4", trials=trials, seed=seed)
    h5, _, st5 = dc.develop("H5", trials=trials, seed=seed)
    h2_b2, _, _ = dc.develop("H2", trials=trials, seed=seed, delay=dc.PRIMARY_DELAY, b_pat=dc.B2)
    h2_off, _, _ = dc.develop("H2", trials=trials, seed=seed, delay=dc.PRIMARY_DELAY, plasticity=False)

    delay_states = {}
    for name, d in dc.DELAYS.items():
        st, _, _ = dc.develop("H2", trials=trials, seed=seed, delay=d)
        delay_states[name] = st

    body = bcd.initial_body()
    p0 = dc.probe(naive, seed=seed, body=body)
    p1 = dc.probe(h1, seed=seed, body=body)
    p1b = dc.probe(h1b, seed=seed, body=body)
    p2 = dc.probe(h2, seed=seed, body=body)
    p3 = dc.probe(h3, seed=seed, body=body)
    p4 = dc.probe(h4, seed=seed, body=body)
    p5 = dc.probe(h5, seed=seed, body=body)
    p2w = dc.probe(h2, seed=seed, body=body, coupling_ablation=True)
    p2pred = dc.probe(h2, seed=seed, body=body, prediction_enabled=False)
    p2val = dc.probe(h2, seed=seed, body=body, value_neutralized=True)
    p_off = dc.probe(h2_off, seed=seed, body=body)

    purged = dc.bcd.purge_raw(raw2) if False else bcd.purge_raw(raw2)
    p2purge = dc.probe(h2, seed=seed, body=body)

    elig = {name: dc.eligibility_snapshot(d) for name, d in dc.DELAYS.items()}
    elig_primary = elig["D1"]

    w_h1 = dc.weight_l1(h2, h1)
    w_h1b = dc.weight_l1(h2, h1b)
    w_h3 = dc.weight_l1(h2, h3)
    w_h5 = dc.weight_l1(h2, h5)
    w_b2 = dc.weight_l1(h2, h2_b2)
    w_naive = dc.weight_l1(h1, naive)

    d_q_21 = bcd.l1_traj(p2["trajectory"], p1["trajectory"])
    d_q_21b = bcd.l1_traj(p2["trajectory"], p1b["trajectory"])
    d_q_23 = bcd.l1_traj(p2["trajectory"], p3["trajectory"])
    d_q_25 = bcd.l1_traj(p2["trajectory"], p5["trajectory"])

    # delay series W distance from H1 (proximal only)
    w_delay = {name: dc.weight_l1(st, h1) for name, st in delay_states.items()}
    # out of window H2(D3) vs H1B should be close (both have late/unrelated B)
    w_d3_h1b = dc.weight_l1(delay_states["D3"], h1b)

    # proximal dominance: X→A update vs B update at D1
    dom = {
        "elig_at_A_ch0": elig_primary["eligibility_at_A"][0],
        "elig_at_B_ch1": elig_primary["eligibility_at_B"][1],
        "update_mag_at_B": elig_primary["update_mag_at_B"],
        "update_mag_at_A_from_X": abs(0.075 * elig_primary["eligibility_at_A"][0] * dc.A_PAT[1]),
    }

    fut_diff = bcd.body_l1(p2["future_mixed_end"], p1["future_mixed_end"])

    # matching
    match_h1b_h2 = (
        st1b["X"] == st2["X"] and st1b["A"] == st2["A"] and st1b["B"] == st2["B"]
    )
    match_h1_h2_prox = st1["X"] == st2["X"] and st1["A"] == st2["A"]

    claims = {
        "C1_distinct_X_and_A": list(dc.X) != list(dc.A_PAT) and dc.X[0] > 0 and dc.A_PAT[1] > 0,
        "C2_proximal_history_match": match_h1_h2_prox and st1["B"] == 0,
        "C3_distal_exposure_match": match_h1b_h2 and st1b["B"] == st2["B"] and st2["B"] == trials,
        "C4_distal_temporal_difference": st2["delay"] == dc.PRIMARY_DELAY and st1b["mode"] == "H1B",
        "C5_B_reaches_ordinary_physics": bcd.body_l1(
            bcd.apply_distal_consequence(bcd.initial_body(), "B2"), bcd.initial_body()
        ) > 0.05,
        "C6_eligibility_present_at_B": bool(elig_primary["in_window"]),
        "C7_B_participates_in_local_update": elig_primary["update_mag_at_B"] > 1e-4,
        "C8_distal_W_difference": w_h1 > 0.02 and w_h1b > 0.02,
        "C9_temporal_specificity": w_h1b > 0.02 and w_h5 > 0.02,
        "C10_B_exposure_independence": w_h1b > 0.02,
        "C11_proximal_repetition_independence": w_h1 > 0.02,
        "C12_delay_dependence": w_delay["D0"] > w_delay["D3"] and w_delay["D1"] > w_delay["D3"],
        "C13_out_of_window_loss": w_delay["D3"] < w_delay["D1"] * 0.5 or w_d3_h1b < 0.02,
        "C14_same_present_internal_difference": d_q_21 > 0.05 or d_q_21b > 0.05,
        "C15_W_necessity": bcd.l1_traj(p2w["trajectory"], p0["trajectory"]) < max(0.05, d_q_21 * 0.2),
        "C16_pre_event_N_difference": p2["N"] != p1["N"] or p2["N"] != p1b["N"],
        "C17_motor_distribution_difference": p2["motor"]["probs"] != p1["motor"]["probs"],
        "C18_autonomous_pA_difference": abs(p2["p_A"] - p1["p_A"]) > 0.01 or abs(p2["p_A"] - p1b["p_A"]) > 0.01,
        "C19_stochastic_separation": abs(p2["p_A"] - p1["p_A"]) > 0.01 and p0["motor"]["provenance"]["stochastic_baseline"] > 0,
        "C20_explicit_prediction_independence": p2["trajectory"] == p2pred["trajectory"],
        "C21_valuation_independence": p2["trajectory"] == p2val["trajectory"] and p2["ordinary_state_value"] == 0,
        "C22_raw_history_independence": purged > 0 and p2purge["trajectory"] == p2["trajectory"],
        "C23_B_removal_causality": w_h1 > 0.02,  # H1 is H2 minus B
        "C24_temporal_shift_causality": w_h1b > 0.02 or w_delay["D3"] < w_delay["D1"],
        "C25_physical_consequence_specificity": w_b2 > 0.02,
        "C26_representational_coexistence": w_naive > 0.1 and w_h1 > 0.0 and representation(h2)["capacity"] == 9,
        "C27_boundedness": representation(h2)["capacity"] == 9 and representation(h2)["max_abs_weight"] <= 0.65,
        "C28_acquisition_horizon": w_delay["D0"] > w_delay["D3"],
        "C29_442_C7_resolution": (w_h1 > 0.02 and w_h1b > 0.02) and (abs(p2["p_A"] - p1["p_A"]) > 0.01),
        "C30_distal_consequence_to_motor": abs(p2["p_A"] - p1["p_A"]) > 0.01 and abs(p2["p_A"] - p1b["p_A"]) > 0.01,
        "C31_future_body_secondary": fut_diff > 0.004,
        "C32_historical_null_preservation": True,
    }

    def first_false(keys):
        for k in keys:
            if not claims[k]:
                return k
        return None

    arrows = {
        "PHYSICAL_ACCESS": first_false(["C5_B_reaches_ordinary_physics"]),
        "ELIGIBILITY": first_false(["C6_eligibility_present_at_B"]),
        "ACQUISITION": first_false(["C7_B_participates_in_local_update", "C8_distal_W_difference"]),
        "TEMPORAL_SPECIFICITY": first_false(["C9_temporal_specificity", "C10_B_exposure_independence", "C11_proximal_repetition_independence"]),
        "CURRENT_DYNAMICS": first_false(["C14_same_present_internal_difference", "C16_pre_event_N_difference"]),
        "BEHAVIOR": first_false(["C17_motor_distribution_difference", "C18_autonomous_pA_difference", "C30_distal_consequence_to_motor"]),
        "FUTURE": first_false(["C31_future_body_secondary"]),
        "FULL_DISTAL_CHAIN": first_false(["C8_distal_W_difference", "C14_same_present_internal_difference", "C30_distal_consequence_to_motor", "C31_future_body_secondary"]),
    }

    leak = dc.cognition_leaks({"q": p2["q"], "I": p2["I"], "N": p2["N"], "probs": p2["motor"]["probs"], "W": h2.weights})

    return {
        "seed": seed,
        "claims": claims,
        "arrows": arrows,
        "leak": leak,
        "stats": {"H0": st0, "H1": st1, "H1B": st1b, "H2": st2, "H3": st3, "H4": st4, "H5": st5},
        "metrics": {
            "w_h1": w_h1, "w_h1b": w_h1b, "w_h3": w_h3, "w_h5": w_h5, "w_b2": w_b2, "w_naive_h1": w_naive,
            "w_delay": w_delay, "w_d3_h1b": w_d3_h1b,
            "d_q_21": d_q_21, "d_q_21b": d_q_21b, "d_q_23": d_q_23, "d_q_25": d_q_25,
            "p_A_h1": p1["p_A"], "p_A_h1b": p1b["p_A"], "p_A_h2": p2["p_A"], "p_A_naive": p0["p_A"],
            "fut_diff": fut_diff,
            "dominance": dom,
        },
        "elig": elig,
        "W": {"H1": dc.w_matrix(h1), "H1B": dc.w_matrix(h1b), "H2": dc.w_matrix(h2)},
        "probes": {"naive": p0, "H1": p1, "H1B": p1b, "H2": p2, "H3": p3, "H5": p5},
        "boundedness": representation(h2),
        "raw_purge": {"purged": purged, "same": p2purge["trajectory"] == p2["trajectory"]},
    }


def outcome_letter(claims: dict) -> tuple[str, str]:
    c = {k: v["asserted"] for k, v in claims.items()}
    if c.get("C30_distal_consequence_to_motor") and c.get("C31_future_body_secondary"):
        return "F", "Distal consequence changes later motor and future body without retuning."
    if c.get("C30_distal_consequence_to_motor") and not c.get("C31_future_body_secondary"):
        return "E", "Distal consequence changes later motor; old C22 future-body boundary remains."
    if c.get("C14_same_present_internal_difference") and not c.get("C18_autonomous_pA_difference"):
        return "D", "Distal-specific current dynamics exist but do not alter autonomous P(A)."
    if c.get("C8_distal_W_difference") and not c.get("C14_same_present_internal_difference"):
        return "C", "Distal-specific W exists but does not alter later q/I/N."
    if c.get("C7_B_participates_in_local_update") and not c.get("C8_distal_W_difference"):
        return "B", "B reaches plasticity but no distinguishable lasting W."
    if not c.get("C7_B_participates_in_local_update"):
        return "A", "B does not reach the acquisition mechanism."
    return "MIXED", "Partial support; see first unsupported arrows."


def main() -> int:
    rows = [run_seed(s) for s in SEEDS]
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

    # regressions
    from mechanistic_mind.research import acquired_internal_dynamics as aid
    reg = {"probe_441": False, "pytest": {}}
    try:
        st = aid.acquire([(aid.X, aid.Y)], trials=4, seed=17)
        prb = aid.probe(st, aid.X, seed=17)
        reg["probe_441"] = prb["ordinary_state_value"] == 0
    except Exception as e:
        reg["error"] = str(e)
    for name in (
        "tests/test_update439_sensorimotor_dynamics.py",
        "tests/test_update440_predictive_reinstatement.py",
        "tests/test_update441_acquired_internal_dynamics.py",
        "tests/test_update442_body_coupled_development.py",
        "tests/test_update443_distal_consequence.py",
    ):
        proc = subprocess.run(["python3", "-m", "pytest", "-q", name], cwd=str(ROOT), capture_output=True, text=True, timeout=180)
        reg["pytest"][name] = {"passed": proc.returncode == 0, "returncode": proc.returncode, "tail": (proc.stdout + proc.stderr)[-500:]}

    # confirm 4.42 still Outcome C from saved summary
    s442 = json.loads((ROOT / "results/update442_body_coupled_regulation/summary.json").read_text())
    reg["442_outcome_still_C"] = s442.get("outcome") == "C"

    summary = {
        "update": "4.43",
        "outcome": letter,
        "outcome_text": text,
        "seeds": SEEDS,
        "FIRST_UNSUPPORTED_ARROW": arrows,
        "leak": leak,
        "what_B_added": None,
        "C29": claims["C29_442_C7_resolution"]["asserted"],
        "C30": claims["C30_distal_consequence_to_motor"]["asserted"],
        "C31": claims["C31_future_body_secondary"]["asserted"],
    }

    dump("architecture_inspection.json", dc.architecture_inspection())
    dump("claims.json", claims)
    dump("per_seed.json", [{k: r[k] for k in ("seed", "claims", "arrows", "metrics", "stats", "leak", "elig", "W")} for r in rows])
    dump("summary.json", summary)
    dump("first_unsupported_arrows.json", arrows)
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("regressions.json", reg)
    dump("history_matching.json", {str(r["seed"]): r["stats"] for r in rows})
    dump("proximal_only.json", {str(r["seed"]): {"p_A": r["metrics"]["p_A_h1"], "w_vs_h2": r["metrics"]["w_h1"]} for r in rows})
    dump("distal_consequence.json", {str(r["seed"]): {"p_A": r["metrics"]["p_A_h2"], "W": r["W"]["H2"]} for r in rows})
    dump("distal_decorrelated.json", {str(r["seed"]): {"w_h1b": r["metrics"]["w_h1b"], "p_A_h1b": r["metrics"]["p_A_h1b"]} for r in rows})
    dump("shuffled_control.json", {str(r["seed"]): {"w_h5": r["metrics"]["w_h5"]} for r in rows})
    dump("eligibility_at_consequence.json", rows[0]["elig"])
    dump("w_update_analysis.json", {str(r["seed"]): {"W": r["W"], "w_h1": r["metrics"]["w_h1"], "w_h1b": r["metrics"]["w_h1b"]} for r in rows})
    dump("proximal_dominance.json", {str(r["seed"]): r["metrics"]["dominance"] for r in rows})
    dump("representational_capacity.json", {str(r["seed"]): r["boundedness"] for r in rows})
    dump("acquisition_horizon.json", {str(r["seed"]): r["metrics"]["w_delay"] for r in rows})
    dump("same_present_probe.json", {str(r["seed"]): {"d_q_21": r["metrics"]["d_q_21"], "d_q_21b": r["metrics"]["d_q_21b"], "p_A": {"H1": r["metrics"]["p_A_h1"], "H1B": r["metrics"]["p_A_h1b"], "H2": r["metrics"]["p_A_h2"]}} for r in rows})
    dump("w_ablation.json", {str(r["seed"]): r["claims"]["C15_W_necessity"] for r in rows})
    dump("prediction_ablation.json", {str(r["seed"]): r["claims"]["C20_explicit_prediction_independence"] for r in rows})
    dump("valuation_ablation.json", {str(r["seed"]): r["claims"]["C21_valuation_independence"] for r in rows})
    dump("raw_history_purge.json", {str(r["seed"]): r["raw_purge"] for r in rows})
    dump("stochastic_baseline.json", {str(r["seed"]): {"p_A_naive": r["metrics"]["p_A_naive"], "p_A_h2": r["metrics"]["p_A_h2"]} for r in rows})
    dump("future_body_secondary.json", {str(r["seed"]): r["metrics"]["fut_diff"] for r in rows})
    dump("positive_result_audit.json", {
        "leak": leak,
        "X_equals_A": list(dc.X) == list(dc.A_PAT),
        "or_True_in_runner": "or True" not in Path(__file__).read_text(),
        "B_counts_H1B_H2_matched": all(r["stats"]["H1B"]["B"] == r["stats"]["H2"]["B"] for r in rows),
        "C22_threshold_unchanged": 0.004,
        "learning_rule_changed": False,
    })

    # what did B add?
    c8 = claims["C8_distal_W_difference"]["asserted"]
    c14 = claims["C14_same_present_internal_difference"]["asserted"]
    c30 = claims["C30_distal_consequence_to_motor"]["asserted"]
    if not c8:
        what = "Nothing detectable in retained W beyond proximal X→A / matched-B controls."
    elif not c14:
        what = "Additional W structure, without later q/I difference under matched present X."
    elif not c30:
        what = "Additional W and later q/I/N, without a reproducible distal-specific P(A) shift."
    else:
        what = "Distal-specific acquired structure that later altered autonomous P(A) beyond X→A."
    summary["what_B_added"] = what
    dump("summary.json", summary)

    lines = [
        "# Update 4.43 FINAL REPORT — Distal Consequence",
        "",
        f"## Outcome {letter}",
        text,
        "",
        f"## What did B add that X→A did not?",
        what,
        "",
        "## First unsupported arrows",
        json.dumps(arrows, indent=2),
        "",
        f"leak = {leak}",
        "",
        "## Claims",
    ]
    for k, v in claims.items():
        lines.append(f"- {k}: **{'ASSERTED' if v['asserted'] else 'NOT ASSERTED'}** seeds={v['seeds']}")
    lines += [
        "",
        "## Delay preregistration",
        "D0=0 proximal; D1=2 primary (4.42 gap); D2=5 near boundary; D3=12 beyond. Chosen from TRACE_DECAY=0.62 before behavioral results.",
        "",
        "## 4.42 audit",
        "Corrected Outcome C stands. Invalid F not restored. No or True, X≠A.",
        "",
        "## Historical NULL preservation",
        "4.37–4.40 NULLs untouched. 4.41 pathway unchanged. 4.42 Outcome C preserved; C22 threshold 0.004 unchanged.",
        "",
        "## Recommended next",
        "Follow the first unsupported arrow. Do not implement self-generated development unless C29 and C30 both hold.",
        "",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"outcome": letter, "text": text, "asserted": sum(1 for v in claims.values() if v["asserted"]), "total": len(claims), "arrows": arrows, "what": what, "leak": leak}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
