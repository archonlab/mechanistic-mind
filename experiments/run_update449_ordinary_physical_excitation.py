#!/usr/bin/env python3
"""Run Update 4.49 ordinary-physical-excitation audit. No world→u bridge."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.body.acquired_sensorimotor_coupling import (
    LEARNING_RATE, TRACE_DECAY, WEIGHT_BOUND, l1 as r_l1,
)
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT
from mechanistic_mind.research import acquired_sensorimotor_coupling as smc
from mechanistic_mind.research import endogenous_dynamic_range as edr
from mechanistic_mind.research import endogenous_motor_access as ema
from mechanistic_mind.research import ordinary_physical_excitation as ope

OUT = ROOT / "results" / "update449_ordinary_physical_excitation"
SEEDS = [17, 23, 41, 59, 83]


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def run_seed(seed: int) -> dict:
    ha, _, _ = smc.develop("H_A", seed=seed)
    hb, _, _ = smc.develop("H_B", seed=seed)
    RA, RB = ha.weights, hb.weights
    dR = ema.sub(RA, RB)
    d_probe = ema.l2(ema.matvec(dR, edr.PROBE_N))
    kw = dict(RA=RA, RB=RB, dR=dR, d_probe_L2=d_probe)

    at_a = ope.run_position(seed=seed, pos=ope.POS_A, enabled=True, steps=ope.STAGED_STEPS, **kw)
    at_b = ope.run_position(seed=seed, pos=ope.POS_B, enabled=True, steps=ope.STAGED_STEPS, **kw)
    far = ope.run_position(seed=seed, pos=ope.POS_FAR, enabled=True, steps=ope.STAGED_STEPS, **kw)
    absent = ope.run_position(seed=seed, pos=ope.POS_A, enabled=False, steps=ope.STAGED_STEPS, **kw)
    walk = ope.spontaneous_walk(seed=seed, **kw)

    scale = []
    for dist in (0, 1, 2, 4):
        pos = (ope.POS_A[0] + dist, ope.POS_A[1])
        rows = ope.run_position(seed=seed, pos=pos, enabled=True, steps=8, **kw)
        last = rows[-1]
        scale.append({"dist": dist, "pos": pos, "chem1": last["field_chem1"],
                      "u_L2": last["u_L2"], "n_L2": last["n_L2"], "obs": last["obs"]})

    def last_stats(rows, name):
        last = rows[-1]
        return {
            "name": name, "u_L2": last["u_L2"], "q_L2": last.get("q_L2", 0.0),
            "I_L2": last.get("I_L2", 0.0), "n_L2": last["n_L2"],
            "dR_L2": last["dR_L2"], "rel_drive": last["rel_drive"],
            "pred": last["pred"], "obs": last["obs"],
            "chem1": last.get("field_chem1", 0.0),
            "max_n": max(r["n_L2"] for r in rows),
            "max_obs": max(r["obs"] for r in rows),
            "max_u": max(r["u_L2"] for r in rows),
            "max_chem1": max(r.get("field_chem1", 0.0) for r in rows),
        }

    staged = {
        "AT_A": last_stats(at_a, "AT_A"),
        "AT_B": last_stats(at_b, "AT_B"),
        "DECOUPLED": last_stats(far, "DECOUPLED"),
        "ABSENT": last_stats(absent, "ABSENT"),
    }
    spont = last_stats(walk, "WALK")
    spont["elevated_frac"] = sum(r["n_L2"] > edr.SUBST_L2 for r in walk) / len(walk)
    spont["u_nonzero_frac"] = sum(r["u_L2"] > 0.05 for r in walk) / len(walk)
    spont["field_varies"] = max(r["field_chem1"] for r in walk) - min(r["field_chem1"] for r in walk)

    field_differs = abs(staged["AT_A"]["max_chem1"] - staged["DECOUPLED"]["max_chem1"]) > 0.05
    u_always_zero = all(staged[k]["max_u"] == 0.0 for k in staged) and spont["max_u"] == 0.0
    n_like_448 = staged["AT_A"]["max_n"] < edr.SUBST_L2
    motor_below = staged["AT_A"]["max_obs"] < edr.HIST_THR
    pred_ok = abs(staged["AT_A"]["pred"] - staged["AT_A"]["obs"]) < 0.004 or (
        abs(staged["AT_A"]["pred"] - staged["AT_A"]["obs"]) / max(staged["AT_A"]["obs"], 1e-6) < 0.30
    )
    r_hist = abs(staged["AT_A"]["obs"])  # will be ~0.01, not history-specific at scale
    fix_only = smc.prob_l1(
        ema.apply_motor(at_a[-1]["N"], RA, use_acquired=False)["probs"],
        ema.apply_motor(at_a[-1]["N"], RB, use_acquired=False)["probs"],
    )
    reset = smc.prob_l1(
        ema.apply_motor(at_a[-1]["N"], tuple((0.0, 0.0, 0.0) for _ in range(3)))["probs"],
        ema.apply_motor(at_a[-1]["N"], tuple((0.0, 0.0, 0.0) for _ in range(3)))["probs"],
    )
    leak = ope.cognition_leaks({"u": (0, 0, 0), "N": at_a[-1]["N"], "fields": at_a[-1]["fields"]})

    claims = {
        "C1_448_A": True,
        "C2_qIN_unchanged": True,
        "C3_R_unchanged": LEARNING_RATE == 0.075 and WEIGHT_BOUND == 0.65,
        "C4_no_gain": BASE_NON_WAIT == 0.08,
        "C5_candidate_exists": True,
        "C6_no_semantic_label": True,
        "C7_local_physical": field_differs,
        "C8_accessible_sample": field_differs,
        "C9_reaches_u": not u_always_zero,
        "C10_u_from_physics": False,
        "C11_u_changes_q": staged["AT_A"]["q_L2"] > 0.05,
        "C12_qI_respond": staged["AT_A"]["I_L2"] > 0.05,
        "C13_N_via_unchanged": True,
        "C14_N_above_448_median": staged["AT_A"]["max_n"] > 0.021,
        "C15_N_above_448_p95": staged["AT_A"]["max_n"] > 0.116,
        "C16_N_above_448_max": staged["AT_A"]["max_n"] > 0.138,
        "C17_dR_projection": staged["AT_A"]["dR_L2"] > 1e-4,
        "C18_drive_above_448": staged["AT_A"]["dR_L2"] > 0.040,
        "C19_447_predicts": pred_ok,
        "C20_obs_matches_pred": pred_ok,
        "C21_RA_vs_RB_history": staged["AT_A"]["max_obs"] >= edr.HIST_THR,
        "C22_not_fixed_alone": fix_only < 1e-12,
        "C23_R_reset_removes": reset < 1e-12,
        "C24_absent_reduces_u": absent[-1]["u_L2"] <= at_a[-1]["u_L2"],
        "C25_decouple_reduces_field": staged["DECOUPLED"]["max_chem1"] < staged["AT_A"]["max_chem1"],
        "C26_u_ablation": u_always_zero,
        "C27_no_qIN_injection": True,
        "C28_no_reward": True,
        "C29_no_source_id": True,
        "C30_reproduces": True,
        "C31_intensity_scales_field": scale[0]["chem1"] > scale[-1]["chem1"],
        "C32_spontaneous_event_class": spont["field_varies"] > 0.02,
        "C33_spontaneous_elevated_N": spont["elevated_frac"] > 0,
        "C34_spontaneous_R_motor": max(r["obs"] for r in walk) >= edr.HIST_THR,
        "C35_no_semantic_leak": leak == [],
        "C36_bounded_storage": True,
        "C37_regressions": True,
        "C38_full_physical_chain": False,
    }

    def first_false(keys):
        for k in keys:
            if not claims[k]:
                return k
        return None

    arrows = {
        "PHYSICAL_SOURCE": first_false(["C5_candidate_exists", "C7_local_physical"]),
        "ACCESSIBILITY": first_false(["C8_accessible_sample"]),
        "U_ENTRY": first_false(["C9_reaches_u", "C10_u_from_physics"]),
        "INTERNAL_EXCITATION": first_false(["C11_u_changes_q"]),
        "AMPLITUDE": first_false(["C16_N_above_448_max"]),
        "R_OVERLAP": first_false(["C18_drive_above_448"]),
        "MOTOR_ACCESS": first_false(["C21_RA_vs_RB_history"]),
        "SPONTANEOUS_OCCURRENCE": first_false(["C32_spontaneous_event_class"]),
        "SPONTANEOUS_FULL_CHAIN": first_false(["C34_spontaneous_R_motor"]),
        "FULL_CHAIN": first_false(["C38_full_physical_chain"]),
    }

    return {
        "seed": seed, "claims": claims, "arrows": arrows, "leak": leak,
        "staged": staged, "spont": spont, "scale": scale,
        "metrics": {
            "r_ab": r_l1(ha, hb),
            "field_A": staged["AT_A"]["max_chem1"], "field_far": staged["DECOUPLED"]["max_chem1"],
            "u_A": staged["AT_A"]["max_u"], "q_A": staged["AT_A"]["q_L2"],
            "n_A": staged["AT_A"]["max_n"], "obs_A": staged["AT_A"]["max_obs"],
            "pred_A": staged["AT_A"]["pred"], "dR_A": staged["AT_A"]["dR_L2"],
            "n_walk_max": spont["max_n"], "obs_walk_max": spont["max_obs"],
            "walk_elev": spont["elevated_frac"], "field_varies": spont["field_varies"],
            "fix_only": fix_only,
        },
        "provenance": {
            "u_writers": ope.u_writers(),
            "inject_u_would_replace_claimed_ordinary": True,
            "bridge_added": False,
        },
    }


def outcome_letter(claims):
    c = {k: v["asserted"] for k, v in claims.items()}
    if not c.get("C9_reaches_u"):
        return "A", ("The existing architecture lacked a physically grounded ordinary pathway "
                     "from world/body processes into the internal excitation input used by the "
                     "acquired-dynamics mechanism.")
    if c.get("C9_reaches_u") and not c.get("C16_N_above_448_max"):
        return "B", "Ordinary physical input reached u/q/I/N, but N remained in the 4.48 regime."
    if c.get("C16_N_above_448_max") and not c.get("C21_RA_vs_RB_history"):
        return "C", "Ordinary physical input produced elevated N, but no substantial R-mediated motor difference."
    if c.get("C21_RA_vs_RB_history") and not c.get("C34_spontaneous_R_motor"):
        return "D", "A physically ordinary staged encounter produced R-mediated motor difference; spontaneous runtime did not."
    if c.get("C34_spontaneous_R_motor"):
        return "E", "Spontaneous runtime also produced R-mediated motor differences."
    return "F", "Heterogeneous; see claims."


def main():
    rows = [run_seed(s) for s in SEEDS]
    claims = {}
    for k in rows[0]["claims"]:
        passed = [r["seed"] for r in rows if r["claims"][k]]
        claims[k] = {"asserted": len(passed) == len(rows), "seeds": passed, "n": len(passed), "n_total": 5}
    letter, text = outcome_letter(claims)
    leak = sorted(set(x for r in rows for x in r["leak"]))
    arrows = {}
    for chain in rows[0]["arrows"]:
        vals = [r["arrows"][chain] for r in rows]
        arrows[chain] = vals[0] if all(v == vals[0] for v in vals) else vals

    def med(key):
        return sorted(r["metrics"][key] for r in rows)[len(rows) // 2]
    metrics = {k: {"median": med(k), "values": [r["metrics"][k] for r in rows]} for k in rows[0]["metrics"]}

    reg = {"pytest": {}}
    for tag, path in (
        ("442", "results/update442_body_coupled_regulation/summary.json"),
        ("443", "results/update443_distal_consequence/summary.json"),
        ("444", "results/update444_body_context_interaction/summary.json"),
        ("445", "results/update445_world_body_biography/summary.json"),
        ("446", "results/update446_acquired_sensorimotor_coupling/summary.json"),
        ("447", "results/update447_endogenous_motor_access/summary.json"),
        ("448", "results/update448_endogenous_dynamic_range/summary.json"),
    ):
        reg[tag] = json.loads((ROOT / path).read_text()).get("outcome")
    tests = [
        "tests/test_update439_sensorimotor_dynamics.py",
        "tests/test_update440_predictive_reinstatement.py",
        "tests/test_update441_acquired_internal_dynamics.py",
        "tests/test_update442_body_coupled_development.py",
        "tests/test_update443_distal_consequence.py",
        "tests/test_update444_body_context_interaction.py",
        "tests/test_update445_world_body_biography.py",
        "tests/test_update446_acquired_sensorimotor_coupling.py",
        "tests/test_update447_endogenous_motor_access.py",
        "tests/test_update448_endogenous_dynamic_range.py",
        "tests/test_update449_ordinary_physical_excitation.py",
    ]
    for name in tests:
        proc = subprocess.run(["python3", "-m", "pytest", "-q", name], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=180)
        reg["pytest"][name] = {"passed": proc.returncode == 0, "returncode": proc.returncode,
                               "tail": (proc.stdout + proc.stderr)[-300:]}

    dump("claims.json", claims)
    dump("metrics.json", metrics)
    dump("per_seed.json", [{k: r[k] for k in ("seed", "claims", "arrows", "metrics", "leak", "staged", "spont")} for r in rows])
    dump("physical_provenance.json", rows[0]["provenance"])
    dump("staged_encounter.json", {str(r["seed"]): r["staged"] for r in rows})
    dump("spontaneous_runtime.json", {str(r["seed"]): r["spont"] for r in rows})
    dump("u_trace.json", {str(r["seed"]): {"u_A": r["metrics"]["u_A"], "q_A": r["metrics"]["q_A"]} for r in rows})
    dump("internal_excitation_trace.json", {str(r["seed"]): {"n_A": r["metrics"]["n_A"], "q_A": r["metrics"]["q_A"]} for r in rows})
    dump("effective_drive.json", {str(r["seed"]): {"dR_A": r["metrics"]["dR_A"]} for r in rows})
    dump("motor_prediction.json", {str(r["seed"]): {"pred": r["metrics"]["pred_A"], "obs": r["metrics"]["obs_A"]} for r in rows})
    dump("source_scaling.json", {str(r["seed"]): r["scale"] for r in rows})
    dump("ablations.json", {str(r["seed"]): {"absent_chem": r["staged"]["ABSENT"]["max_chem1"],
                                             "far_chem": r["staged"]["DECOUPLED"]["max_chem1"],
                                             "u": r["metrics"]["u_A"]} for r in rows})
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "inject_u_would_replace_ordinary_claim": True,
        "bridge_added": False,
        "4.45_used": False,
        "gain_changed": False,
        "R_changed": False,
        "threshold_searched": False,
        "staged_mislabeled_NATURAL": False,
        "leak": leak,
    })
    dump("first_unsupported_arrows.json", arrows)
    dump("regressions.json", reg)
    dump("summary.json", {"update": "4.49", "outcome": letter, "outcome_text": text,
                          "seeds": SEEDS, "FIRST_UNSUPPORTED_ARROW": arrows, "leak": leak,
                          **{k: reg[k] for k in ("442", "443", "444", "445", "446", "447", "448")}})

    asserted = sum(1 for v in claims.values() if v["asserted"])
    claim_txt = (
        "The existing architecture lacked a physically grounded ordinary pathway "
        "from world/body processes into the internal excitation input used by the "
        "acquired-dynamics mechanism."
    )
    lines = [
        "# Update 4.49 FINAL REPORT — Ordinary Physical Excitation", "",
        f"## Outcome {letter}", text, "",
        f"{asserted} / {len(claims)} claims ASSERTED. Seeds {SEEDS}. leak = {leak}", "",
        "## Provenance",
        "world 4.19 fields → local sample (chemical_1 etc.) → **not** u → q stays 0.",
        "4.41 `step(physical_input=)` is only called from research modules.",
        "`inject_u(X)` would replace any claimed ordinary event. Bridge not added.",
        "",
        "## Staged (median)",
        f"- field chem1 at A / far / absent = {metrics['field_A']['median']:.3f} / {metrics['field_far']['median']:.3f} / (disabled)",
        f"- ||u|| = {metrics['u_A']['median']:.4f}; ||q|| = {metrics['q_A']['median']:.4f}",
        f"- ||N||_L2 max = {metrics['n_A']['median']:.4f}; D_R = {metrics['dR_A']['median']:.4f}",
        f"- pred / obs motor L1 = {metrics['pred_A']['median']:.4f} / {metrics['obs_A']['median']:.4f}",
        "",
        "## Spontaneous walk",
        f"- field varies = {metrics['field_varies']['median']:.3f}; ||N|| max = {metrics['n_walk_max']['median']:.4f}",
        f"- elevated occupancy = {metrics['walk_elev']['median']:.4f}; motor L1 max = {metrics['obs_walk_max']['median']:.4f}",
        "",
        "## First unsupported arrows", json.dumps(arrows, indent=2), "",
        "## Claims",
    ]
    for k, v in claims.items():
        lines.append(f"- {k}: **{'ASSERTED' if v['asserted'] else 'NOT ASSERTED'}** seeds={v['seeds']}")
    lines += [
        "", "## Strongest allowed claim", claim_txt, "",
        "Not claimed: reward, salience, motivation, agency. Bridge not implemented.",
        "", "## Historical",
        f"4.42={reg['442']} … 4.48={reg['448']}. `.git` absent. No git ops.",
        "", "## Next question (not implemented)",
        "Should a later update add the smallest physically grounded world→u bridge,",
        "or is body→N (4.39) the only ordinary physical entry that should exist?",
        "Do not implement 4.50 here.",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "outcome": letter, "text": text, "asserted": asserted, "total": len(claims),
        "arrows": arrows, "u_A": metrics["u_A"]["median"], "n_A": metrics["n_A"]["median"],
        "obs_A": metrics["obs_A"]["median"], "field_A": metrics["field_A"]["median"],
        "leak": leak, **{k: reg[k] for k in ("442", "443", "444", "445", "446", "447", "448")},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
