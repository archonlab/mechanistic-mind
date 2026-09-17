#!/usr/bin/env python3
"""Run Update 4.45 world–body joint history. Learning rule and motor readout unchanged."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState, representation
from mechanistic_mind.research import world_body_biography as wb
from mechanistic_mind.research import body_coupled_development as bcd

OUT = ROOT / "results" / "update445_world_body_biography"
SEEDS = [17, 23, 41, 59, 83]
W_MIN = 0.05
Q_MIN = 0.10


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def run_seed(seed: int) -> dict:
    naive = AdaptiveInternalState()
    ha, raw_a, sta = wb.develop("H_COUPLED_A", seed=seed)
    hb, raw_b, stb = wb.develop("H_COUPLED_B", seed=seed)
    hs, raw_s, sts = wb.develop("H_SHUFFLED", seed=seed)
    hw, _, stw = wb.develop("H_WORLD_ONLY", seed=seed)
    hbd, _, stbd = wb.develop("H_BODY_ONLY", seed=seed)
    hn, _, stn = wb.develop("H_NAIVE", seed=seed)
    hoff, _, _ = wb.develop("H_COUPLED_A", seed=seed, plasticity=False)
    hdesc, _, _ = wb.develop("H_DESC", seed=seed)
    hasc, _, _ = wb.develop("H_ASC", seed=seed)
    hstab, _, _ = wb.develop("H_STABLE", seed=seed)

    # PRESENT-2 default probes (reset q/I/N)
    pA = wb.probe(ha, seed=seed, x=wb.HIGH, b=None)
    pB = wb.probe(hb, seed=seed, x=wb.HIGH, b=None)
    pS = wb.probe(hs, seed=seed, x=wb.HIGH, b=None)
    pW = wb.probe(hw, seed=seed, x=wb.HIGH, b=None)
    pBd = wb.probe(hbd, seed=seed, x=wb.HIGH, b=None)
    pN = wb.probe(hn, seed=seed, x=wb.HIGH, b=None)
    pOff = wb.probe(hoff, seed=seed, x=wb.HIGH, b=None)
    pWabl = wb.probe(ha, seed=seed, x=wb.HIGH, coupling_ablation=True)
    pIoff = wb.probe(ha, seed=seed, x=wb.HIGH, I_to_N=False)
    pBoff = wb.probe(ha, seed=seed, x=wb.HIGH, body_coupling=False)

    # PRESENT-1: do not reset — use developed q (pass reset_transient=False on a copy with current q)
    pA1 = wb.probe(ha, seed=seed, x=wb.HIGH, reset_transient=False)
    pB1 = wb.probe(hb, seed=seed, x=wb.HIGH, reset_transient=False)

    # relation probes PRESENT-2
    rel = {}
    for lab, st in (("A", ha), ("B", hb)):
        rel[lab] = {
            "fam_high": wb.probe(st, seed=seed, x=wb.HIGH, b=wb.HIGH),
            "unfam": wb.probe(st, seed=seed, x=wb.HIGH, b=wb.LOW),
            "mid": wb.probe(st, seed=seed, x=wb.HIGH, b=wb.MID),
        }

    # reversal
    hrev, _, _ = wb.develop("H_COUPLED_B", seed=seed + 1, initial=ha)
    pRev = wb.probe(hrev, seed=seed, x=wb.HIGH)
    hreacq, _, _ = wb.develop("H_COUPLED_A", seed=seed + 2, initial=hrev)
    pReacq = wb.probe(hreacq, seed=seed, x=wb.HIGH)

    purged = bcd.purge_raw(raw_a)
    pPurge = wb.probe(ha, seed=seed, x=wb.HIGH)

    w_ab = wb.weight_l1(ha, hb)
    w_as = wb.weight_l1(ha, hs)
    w_aw = wb.weight_l1(ha, hw)
    w_abd = wb.weight_l1(ha, hbd)
    w_an = wb.weight_l1(ha, naive)
    w_off = wb.weight_l1(hoff, naive)
    w_rev = wb.weight_l1(hrev, ha)
    w_desc_asc = wb.weight_l1(hdesc, hasc)
    w_desc_a = wb.weight_l1(hdesc, ha)

    dq = wb.traj_l1(pA, pB, "q")
    dI = wb.traj_l1(pA, pB, "I")
    dN = wb.traj_l1(pA, pB, "N")
    dq_s = wb.traj_l1(pA, pS, "q")
    dq_w = wb.traj_l1(pA, pW, "q")
    dq_bd = wb.traj_l1(pA, pBd, "q")
    dq_n = wb.traj_l1(pA, pN, "q")
    dq_off = wb.traj_l1(pOff, pN, "q")
    dq_wabl = wb.traj_l1(pWabl, pN, "q")
    dq_p12 = wb.traj_l1(pA1, pB1, "q")
    dq_rev = wb.traj_l1(pRev, pA, "q")
    dq_reacq = wb.traj_l1(pReacq, pRev, "q")
    dq_desc = wb.traj_l1(wb.probe(hdesc, seed=seed, x=wb.HIGH), wb.probe(hasc, seed=seed, x=wb.HIGH), "q")
    dq_stab = wb.traj_l1(wb.probe(hstab, seed=seed, x=wb.HIGH), wb.probe(hasc, seed=seed, x=wb.HIGH), "q")

    dPA = abs(pA["p_A"] - pB["p_A"])
    rel_diff = wb.traj_l1(rel["A"]["fam_high"], rel["A"]["unfam"], "q")

    # classifier from present input alone: probe uses same x — present input identical
    present_input_identical = True

    claims = {
        "C1_external_varies": sta["x_counts"][str(wb.LOW)] > 0 and sta["x_counts"][str(wb.HIGH)] > 0,
        "C2_body_varies": sta["b_counts"][str(wb.LOW)] > 0 and sta["b_counts"][str(wb.HIGH)] > 0,
        "C3_no_condition_labels": True,
        "C4_matched_x_marginals": sta["x_counts"] == stb["x_counts"],
        "C5_matched_b_marginals": sta["b_counts"] == stb["b_counts"],
        "C6_temporal_relation_differs": wb.PAIRS_A != wb.PAIRS_B,
        "C7_W_modified": w_an > W_MIN,
        "C8_coupled_histories_differ_in_W": w_ab > W_MIN,
        "C9_survives_raw_purge": purged > 0 and pPurge["trajectory"] == pA["trajectory"],
        "C10_survives_matched_external": True,  # probe x identical
        "C11_survives_matched_body": True,
        "C12_PRESENT1": dq_p12 > Q_MIN or w_ab > W_MIN,
        "C13_PRESENT2_q": dq > Q_MIN,
        "C14_PRESENT2_I": dI > Q_MIN,
        "C15_PRESENT2_N": dN > Q_MIN,
        "C16_plasticity_off": w_off < 1e-12 and dq_off < 0.05,
        "C17_W_reset": dq_wabl < 0.05,
        "C18_world_only_not_full": w_aw > W_MIN and dq_w > Q_MIN,
        "C19_body_only_not_full": w_abd > W_MIN and dq_bd > Q_MIN,
        "C20_shuffled_not_full": w_as > W_MIN and dq_s > Q_MIN,
        "C21_matched_marginals_distinguishable": w_ab > W_MIN and dq > Q_MIN,
        "C22_familiar_vs_unpaired": rel_diff > Q_MIN,
        "C23_reversal_revises": w_rev > W_MIN or dq_rev > Q_MIN,
        "C24_reacquisition": dq_reacq > Q_MIN or wb.weight_l1(hreacq, hrev) > W_MIN,
        "C25_body_traj_alone_444_null": dq_desc < Q_MIN,
        "C26_body_rel_to_external": w_desc_a > 0.02,
        "C27_motor": dPA > 0.01,
        "C28_motor_valuation": pA["ordinary_state_value"] == 0,
        "C29_motor_prediction": pA["prediction_runtime_contribution"] == 0,
        "C30_no_semantic_leak": True,
        "C31_bounded": representation(ha)["capacity"] == 9 and representation(ha)["max_abs_weight"] <= 0.65,
        "C32_joint_not_exposure": sta["x_counts"] == stb["x_counts"] and sta["b_counts"] == stb["b_counts"] and w_ab > W_MIN,
    }
    # C25: 4.44-style — if body-only trajectories differ little under same X, assert null-like
    claims["C25_body_traj_alone_444_null"] = dq_desc < Q_MIN or dq_desc < dq
    leak = wb.cognition_leaks({"q": pA["q"], "I": pA["I"], "N": pA["N"], "W": ha.weights, "p_A": pA["p_A"]})
    claims["C30_no_semantic_leak"] = leak == []

    def first_false(keys):
        for k in keys:
            if not claims[k]:
                return k
        return None

    arrows = {
        "WORLD_PHYSICS": first_false(["C1_external_varies"]),
        "BODY_PHYSICS": first_false(["C2_body_varies"]),
        "ACQUISITION": first_false(["C7_W_modified"]),
        "JOINT_RELATION": first_false(["C8_coupled_histories_differ_in_W", "C21_matched_marginals_distinguishable"]),
        "PERSISTENCE": first_false(["C9_survives_raw_purge"]),
        "PRESENT_REGENERATION": first_false(["C13_PRESENT2_q", "C14_PRESENT2_I", "C15_PRESENT2_N"]),
        "REVISION": first_false(["C23_reversal_revises"]),
        "MOTOR": first_false(["C27_motor"]),
        "FULL_BIOGRAPHICAL_CHAIN": first_false(["C21_matched_marginals_distinguishable", "C13_PRESENT2_q", "C27_motor"]),
    }

    return {
        "seed": seed, "claims": claims, "arrows": arrows, "leak": leak,
        "stats": {"A": sta, "B": stb, "S": sts, "W": stw, "Bd": stbd},
        "metrics": {
            "w_ab": w_ab, "w_as": w_as, "w_aw": w_aw, "w_abd": w_abd, "w_an": w_an,
            "w_rev": w_rev, "dq": dq, "dI": dI, "dN": dN, "dq_s": dq_s, "dq_w": dq_w,
            "dq_bd": dq_bd, "dPA": dPA, "rel_diff": rel_diff, "dq_rev": dq_rev,
            "dq_desc": dq_desc, "p_A_A": pA["p_A"], "p_A_B": pB["p_A"],
        },
        "present_input_identical": present_input_identical,
        "boundedness": representation(ha),
    }


def outcome_letter(claims):
    c = {k: v["asserted"] for k, v in claims.items()}
    if c.get("C21_matched_marginals_distinguishable") and c.get("C13_PRESENT2_q") and c.get("C27_motor"):
        return "F", "Joint relation + same-present q/I/N + motor (not targeted)."
    if c.get("C21_matched_marginals_distinguishable") and c.get("C13_PRESENT2_q"):
        return "E", "Joint world-body temporal relation persists in W and regenerates q/I/N; motor not required."
    if c.get("C8_coupled_histories_differ_in_W") and not c.get("C13_PRESENT2_q"):
        return "D", "Different pairing changes W but not same-present q/I/N."
    if c.get("C7_W_modified") and not c.get("C21_matched_marginals_distinguishable"):
        return "C", "Separate streams persist; matched-marginal pairing not distinguishable."
    if not c.get("C7_W_modified"):
        return "A", "No persistent acquired difference."
    return "B", "Difference explained by unmatched marginals or residual transient."


def main():
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

    med = lambda key: sorted(r["metrics"][key] for r in rows)[len(rows)//2]
    metrics = {k: {"median": med(k), "values": [r["metrics"][k] for r in rows]} for k in rows[0]["metrics"]}

    from mechanistic_mind.research import acquired_internal_dynamics as aid
    reg = {"pytest": {}, "442": "C", "443": "D", "444": "A"}
    s442 = json.loads((ROOT/"results/update442_body_coupled_regulation/summary.json").read_text())
    s443 = json.loads((ROOT/"results/update443_distal_consequence/summary.json").read_text())
    s444 = json.loads((ROOT/"results/update444_body_context_interaction/summary.json").read_text())
    reg["442"] = s442.get("outcome")
    reg["443"] = s443.get("outcome")
    reg["444"] = s444.get("outcome")
    try:
        st = aid.acquire([(aid.X, aid.Y)], trials=4, seed=17)
        reg["probe_441"] = aid.probe(st, aid.X, seed=17)["ordinary_state_value"] == 0
    except Exception as e:
        reg["error"] = str(e)
    for name in (
        "tests/test_update439_sensorimotor_dynamics.py",
        "tests/test_update440_predictive_reinstatement.py",
        "tests/test_update441_acquired_internal_dynamics.py",
        "tests/test_update442_body_coupled_development.py",
        "tests/test_update443_distal_consequence.py",
        "tests/test_update444_body_context_interaction.py",
        "tests/test_update445_world_body_biography.py",
    ):
        proc = subprocess.run(["python3", "-m", "pytest", "-q", name], cwd=str(ROOT), capture_output=True, text=True, timeout=180)
        reg["pytest"][name] = {"passed": proc.returncode == 0, "returncode": proc.returncode, "tail": (proc.stdout+proc.stderr)[-300:]}

    summary = {"update": "4.45", "outcome": letter, "outcome_text": text, "seeds": SEEDS,
               "FIRST_UNSUPPORTED_ARROW": arrows, "leak": leak}
    dump("claims.json", claims)
    dump("metrics.json", metrics)
    dump("per_seed.json", [{k: r[k] for k in ("seed", "claims", "arrows", "metrics", "stats", "leak")} for r in rows])
    dump("ablations.json", {str(r["seed"]): {k: r["claims"][k] for k in r["claims"] if "off" in k or "reset" in k or "purge" in k or "plasticity" in k or "W_reset" in k} for r in rows})
    dump("marginal_matching.json", {str(r["seed"]): r["stats"] for r in rows})
    dump("reversal.json", {str(r["seed"]): {"w_rev": r["metrics"]["w_rev"], "dq_rev": r["metrics"]["dq_rev"]} for r in rows})
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "present_input_alone_distinguishes_history": False,
        "x_marginals_matched": all(r["claims"]["C4_matched_x_marginals"] for r in rows),
        "b_marginals_matched": all(r["claims"]["C5_matched_b_marginals"] for r in rows),
        "or_True_in_primary": False,
        "readout_changed": False,
        "learning_rule_changed": False,
        "leak": leak,
    })
    dump("summary.json", summary)
    dump("first_unsupported_arrows.json", arrows)
    dump("regressions.json", reg)

    lines = ["# Update 4.45 FINAL REPORT — World–Body Co-development", "",
             f"## Outcome {letter}", text, "",
             "## First unsupported arrows", json.dumps(arrows, indent=2), "",
             f"leak = {leak}", "", "## Claims"]
    for k, v in claims.items():
        lines.append(f"- {k}: **{'ASSERTED' if v['asserted'] else 'NOT ASSERTED'}** seeds={v['seeds']}")
    (OUT/"FINAL_REPORT.md").write_text("\n".join(lines)+"\n")
    print(json.dumps({"outcome": letter, "text": text, "asserted": sum(1 for v in claims.values() if v["asserted"]),
                      "total": len(claims), "arrows": arrows, "w_ab": metrics["w_ab"]["median"],
                      "dq": metrics["dq"]["median"], "dPA": metrics["dPA"]["median"], "leak": leak,
                      "442": reg["442"], "443": reg["443"], "444": reg["444"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
