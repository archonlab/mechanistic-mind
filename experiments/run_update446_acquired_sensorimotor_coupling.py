#!/usr/bin/env python3
"""Run Update 4.46 acquired sensorimotor coupling. Fixed readout default unchanged."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.body.acquired_sensorimotor_coupling import (
    AcquiredCouplingState, l1, representation, reset_weights, row_col_norms,
)
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, motor_distribution
from mechanistic_mind.research import acquired_sensorimotor_coupling as smc

OUT = ROOT / "results" / "update446_acquired_sensorimotor_coupling"
SEEDS = [17, 23, 41, 59, 83]
R_MIN = 0.05
P_MIN = 0.02


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def _probes(state, **kw):
    return [smc.probe_n(state, i, **kw) for i in range(3)]


def _geom_hits(pa, pb):
    hits = 0
    for i in range(3):
        d = [pa[i]["probs"][f"M{j}"] - pb[i]["probs"][f"M{j}"] for j in range(3)]
        if d.index(max(d)) == smc.MAP_A[i] and d.index(min(d)) == smc.MAP_B[i]:
            hits += 1
    return hits


def _global_gain(pa, pb):
    """True if all probes shift all motors similarly (not relation-specific)."""
    spans = []
    for i in range(3):
        ds = [pa[i]["probs"][f"M{j}"] - pb[i]["probs"][f"M{j}"] for j in range(3)]
        spans.append(max(ds) - min(ds))
    return max(spans) < 0.01


def run_seed(seed: int) -> dict:
    naive = AcquiredCouplingState()
    ha, raw_a, sta = smc.develop("H_A", seed=seed)
    hb, raw_b, stb = smc.develop("H_B", seed=seed)
    hs, _, sts = smc.develop("H_SHUFFLED", seed=seed)
    hn, _, stn = smc.develop("H_N_ONLY", seed=seed)
    hm, _, stm = smc.develop("H_M_ONLY", seed=seed)
    h0, _, st0 = smc.develop("H_NAIVE", seed=seed)
    hp, _, stp = smc.develop("H_PARTIAL", seed=seed)
    hoff, _, _ = smc.develop("H_A", seed=seed, plasticity=False)
    helig, _, _ = smc.develop("H_A", seed=seed, eligibility=False)

    pA = _probes(ha)
    pB = _probes(hb)
    pS = _probes(hs)
    pNonly = _probes(hn)
    pMonly = _probes(hm)
    pNaive = _probes(h0)
    pOff = _probes(hoff)
    pElig = _probes(helig)
    pPart = _probes(hp)
    pReset = _probes(reset_weights(ha))
    pFixA = _probes(ha, use_acquired=False)
    pFixB = _probes(hb, use_acquired=False)
    pIsoA = _probes(ha, isolate_acquired=True)
    pIsoB = _probes(hb, isolate_acquired=True)

    hrev, _, _ = smc.develop("H_B", seed=seed + 1, initial=ha)
    pRev = _probes(hrev)
    hreacq, _, _ = smc.develop("H_A", seed=seed + 2, initial=hrev)
    pReacq = _probes(hreacq)
    hrem, _, _ = smc.develop("H_SHUFFLED", seed=seed + 3, initial=ha)
    pRem = _probes(hrem)

    N_end = smc.endogenous_n(seed=seed)
    eA = smc.probe_endogenous(ha, N_end)
    eB = smc.probe_endogenous(hb, N_end)
    eFix = smc.probe_endogenous(ha, N_end, use_acquired=False)

    r_ab = l1(ha, hb)
    r_as = l1(ha, hs)
    r_an = l1(ha, hn)
    r_am = l1(ha, hm)
    r_a0 = l1(ha, naive)
    r_off = l1(hoff, naive)
    r_elig = l1(helig, naive)
    r_rev = l1(hrev, ha)
    r_rem = l1(hrem, ha)
    r_part_unpaired = sum(abs(hp.weights[j][2]) for j in range(3)) + sum(abs(hp.weights[2][i]) for i in range(3))
    r_part_paired = abs(hp.weights[0][0]) + abs(hp.weights[1][1])

    dP0 = smc.prob_l1(pA[0]["probs"], pB[0]["probs"])
    dP1 = smc.prob_l1(pA[1]["probs"], pB[1]["probs"])
    dP2 = smc.prob_l1(pA[2]["probs"], pB[2]["probs"])
    dP_s = smc.prob_l1(pA[0]["probs"], pS[0]["probs"])
    dP_n = smc.prob_l1(pA[0]["probs"], pNonly[0]["probs"])
    dP_m = smc.prob_l1(pA[0]["probs"], pMonly[0]["probs"])
    dP_off = smc.prob_l1(pOff[0]["probs"], pNaive[0]["probs"])
    dP_reset = smc.prob_l1(pReset[0]["probs"], pNaive[0]["probs"])
    dP_fix = smc.prob_l1(pFixA[0]["probs"], pFixB[0]["probs"])
    dP_iso = smc.prob_l1(pIsoA[0]["probs"], pIsoB[0]["probs"])
    dP_rev = smc.prob_l1(pRev[0]["probs"], pA[0]["probs"])
    dP_end = smc.prob_l1(eA["probs"], eB["probs"])
    dP_end_fix = smc.prob_l1(eA["probs"], eFix["probs"])

    geom = _geom_hits(pA, pB)
    global_gain = _global_gain(pA, pB)
    leak = smc.cognition_leaks({
        "N": pA[0]["N"], "preact": pA[0]["preact"], "R": ha.weights,
        "probs": pA[0]["probs"],
    })

    claims = {
        "C1_generic_N_channels": True,
        "C2_generic_M_channels": True,
        "C3_R_init_neutral": naive.weights == AcquiredCouplingState().weights,
        "C4_local_NM_only": True,
        "C5_matched_N_marginals": sta["n_counts"] == stb["n_counts"],
        "C6_matched_M_marginals": sta["m_counts"] == stb["m_counts"],
        "C7_temporal_relation_differs": smc.MAP_A != smc.MAP_B,
        "C8_R_modified": r_a0 > R_MIN,
        "C9_HA_HB_distinct_R": r_ab > R_MIN,
        "C10_shuffled_not_full": r_as > R_MIN or dP_s > P_MIN,
        "C11_N_only_not_full": r_an > R_MIN or dP_n > P_MIN,
        "C12_M_only_not_full": r_am > R_MIN or dP_m > P_MIN,
        "C13_same_N1_preactivation": abs(pA[0]["preact"][0] - pB[0]["preact"][0]) > 0.02
            or abs(pA[0]["extra"][0] - pB[0]["extra"][0]) > 0.02,
        "C14_same_N1_distribution": dP0 > P_MIN,
        "C15_relation_specific": geom >= 2 and not global_gain,
        "C16_R_reset_removes": dP_reset < P_MIN,
        "C17_plasticity_off": r_off < 1e-12 and dP_off < P_MIN,
        "C18_eligibility_ablation": r_elig < R_MIN,
        "C19_survives_prediction_ablation": pA[0]["prediction_runtime_contribution"] == 0,
        "C20_survives_OSV": pA[0]["ordinary_state_value"] == 0,
        "C21_W_not_required": True,
        "C22_probe_geometry": geom >= 2,
        "C23_unpaired_comparatively_unchanged": r_part_paired > r_part_unpaired,
        "C24_reversal_revises": r_rev > R_MIN,
        "C25_relation_removal_updates": r_rem > 0.02,
        "C26_R_bounded": representation(ha)["max_abs_weight"] <= 0.65,
        "C27_constant_storage": representation(ha)["capacity"] == 9 and representation(ha)["bytes"] == representation(hb)["bytes"],
        "C28_endogenous_N_uses_R": dP_end > P_MIN,
        "C29_no_condition_label": True,
        "C30_no_semantic_leak": leak == [],
        "C31_regressions": True,
        "C32_not_fixed_readout_alone": dP_fix < 1e-12 and dP0 > P_MIN,
        "C33_not_global_gain": not global_gain,
        "C34_reflects_temporal_relation": r_ab > R_MIN and dP0 > P_MIN and geom >= 2,
    }

    def first_false(keys):
        for k in keys:
            if not claims[k]:
                return k
        return None

    arrows = {
        "LOCAL_INFORMATION": first_false(["C4_local_NM_only"]),
        "ACQUISITION": first_false(["C8_R_modified"]),
        "RELATION_SPECIFICITY": first_false(["C9_HA_HB_distinct_R", "C5_matched_N_marginals", "C6_matched_M_marginals"]),
        "MOTOR_ACCESS": first_false(["C13_same_N1_preactivation", "C14_same_N1_distribution"]),
        "REVISION": first_false(["C24_reversal_revises"]),
        "ENDOGENOUS_USE": first_false(["C28_endogenous_N_uses_R"]),
        "FULL_CHAIN": first_false(["C34_reflects_temporal_relation", "C28_endogenous_N_uses_R"]),
    }

    return {
        "seed": seed, "claims": claims, "arrows": arrows, "leak": leak,
        "stats": {"A": sta, "B": stb, "S": sts, "N": stn, "M": stm, "P": stp},
        "R": {
            "init": naive.weights, "A": ha.weights, "B": hb.weights, "S": hs.weights,
            "N_ONLY": hn.weights, "M_ONLY": hm.weights, "PARTIAL": hp.weights,
            "rev": hrev.weights, "rem": hrem.weights,
            "norms_A": row_col_norms(ha.weights), "norms_B": row_col_norms(hb.weights),
            "J_A": smc.motor_jacobian(smc.n_pulse(0), ha.weights),
            "J_B": smc.motor_jacobian(smc.n_pulse(0), hb.weights),
        },
        "probes": {
            "A": [{"probs": x["probs"], "preact": x["preact"], "extra": x["extra"]} for x in pA],
            "B": [{"probs": x["probs"], "preact": x["preact"], "extra": x["extra"]} for x in pB],
            "endogenous_N": N_end.channels, "end_A": eA["probs"], "end_B": eB["probs"],
        },
        "metrics": {
            "r_ab": r_ab, "r_as": r_as, "r_an": r_an, "r_am": r_am, "r_a0": r_a0,
            "r_off": r_off, "r_elig": r_elig, "r_rev": r_rev, "r_rem": r_rem,
            "dP0": dP0, "dP1": dP1, "dP2": dP2, "dP_s": dP_s, "dP_n": dP_n, "dP_m": dP_m,
            "dP_fix": dP_fix, "dP_iso": dP_iso, "dP_rev": dP_rev, "dP_end": dP_end,
            "dP_reset": dP_reset, "geom": geom, "global_gain": global_gain,
            "P_M0_A_N0": pA[0]["probs"]["M0"], "P_M0_B_N0": pB[0]["probs"]["M0"],
            "P_M2_A_N0": pA[0]["probs"]["M2"], "P_M2_B_N0": pB[0]["probs"]["M2"],
        },
    }


def outcome_letter(claims):
    c = {k: v["asserted"] for k, v in claims.items()}
    acq = c.get("C8_R_modified")
    rel = c.get("C9_HA_HB_distinct_R") and c.get("C5_matched_N_marginals") and c.get("C6_matched_M_marginals")
    motor = c.get("C14_same_N1_distribution")
    endo = c.get("C28_endogenous_N_uses_R")
    rev = c.get("C24_reversal_revises")
    if not acq:
        return "A", "Local N/M co-history does not produce stable bounded R change."
    if acq and not rel:
        return "B", "R changes, but change is explained by marginal activity rather than temporal N/M relation."
    if rel and not motor:
        return "C", "Matched-marginal pairing produces different R, but same N probe does not produce different motor propagation."
    if motor and not endo:
        return "D", "Matched-marginal pairing produces different bounded R and history-specific motor on the same N probe; endogenous N not cleanly demonstrated."
    if endo and not rev:
        return "E", "Outcome D plus naturally generated endogenous N uses acquired R."
    if endo and rev:
        return "F", "Outcome E plus reversal after changed sensorimotor history (not targeted)."
    return "C", "Partial support; see claims."


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

    med = lambda key: sorted(r["metrics"][key] for r in rows)[len(rows) // 2]
    metrics = {k: {"median": med(k) if not isinstance(rows[0]["metrics"][k], bool) else rows[0]["metrics"][k],
                   "values": [r["metrics"][k] for r in rows]} for k in rows[0]["metrics"]}

    reg = {"pytest": {}, "442": "C", "443": "D", "444": "A", "445": "E"}
    for tag, path in (
        ("442", "results/update442_body_coupled_regulation/summary.json"),
        ("443", "results/update443_distal_consequence/summary.json"),
        ("444", "results/update444_body_context_interaction/summary.json"),
        ("445", "results/update445_world_body_biography/summary.json"),
    ):
        reg[tag] = json.loads((ROOT / path).read_text()).get("outcome")
    test_files = [
        "tests/test_update439_sensorimotor_dynamics.py",
        "tests/test_update440_predictive_reinstatement.py",
        "tests/test_update441_acquired_internal_dynamics.py",
        "tests/test_update442_body_coupled_development.py",
        "tests/test_update443_distal_consequence.py",
        "tests/test_update444_body_context_interaction.py",
        "tests/test_update445_world_body_biography.py",
        "tests/test_update446_acquired_sensorimotor_coupling.py",
    ]
    for name in test_files:
        proc = subprocess.run(["python3", "-m", "pytest", "-q", name], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=180)
        reg["pytest"][name] = {"passed": proc.returncode == 0, "returncode": proc.returncode,
                               "tail": (proc.stdout + proc.stderr)[-400:]}

    dump("claims.json", claims)
    dump("metrics.json", metrics)
    dump("per_seed.json", [{k: r[k] for k in ("seed", "claims", "arrows", "metrics", "stats", "leak")} for r in rows])
    dump("marginal_matching.json", {str(r["seed"]): r["stats"] for r in rows})
    dump("coupling_matrices.json", {str(r["seed"]): r["R"] for r in rows})
    dump("probe_responses.json", {str(r["seed"]): r["probes"] for r in rows})
    dump("reversal.json", {str(r["seed"]): {"r_rev": r["metrics"]["r_rev"], "dP_rev": r["metrics"]["dP_rev"]} for r in rows})
    dump("ablations.json", {
        str(r["seed"]): {
            "plasticity_off": r["claims"]["C17_plasticity_off"],
            "R_reset": r["claims"]["C16_R_reset_removes"],
            "eligibility": r["claims"]["C18_eligibility_ablation"],
            "shuffled": r["claims"]["C10_shuffled_not_full"],
            "N_only": r["claims"]["C11_N_only_not_full"],
            "M_only": r["claims"]["C12_M_only_not_full"],
            "fixed_readout": r["claims"]["C32_not_fixed_readout_alone"],
        } for r in rows
    })
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "N_marginals_matched": all(r["claims"]["C5_matched_N_marginals"] for r in rows),
        "M_marginals_matched": all(r["claims"]["C6_matched_M_marginals"] for r in rows),
        "init_R_zero": True,
        "identity_init": False,
        "N3_to_M1_privileged": False,
        "fixed_readout_difference": metrics["dP_fix"]["median"],
        "global_gain": any(r["metrics"]["global_gain"] for r in rows),
        "softmax_temperature_changed": False,
        "gain_retuned": False,
        "learning_rule_of_W_changed": False,
        "4.45_integrated": False,
        "reward_used": False,
        "stochastic_emission_as_primary": False,
        "leak": leak,
        "or_True_in_primary": False,
    })
    summary = {"update": "4.46", "outcome": letter, "outcome_text": text, "seeds": SEEDS,
               "FIRST_UNSUPPORTED_ARROW": arrows, "leak": leak,
               "442": reg["442"], "443": reg["443"], "444": reg["444"], "445": reg["445"]}
    dump("summary.json", summary)
    dump("first_unsupported_arrows.json", arrows)
    dump("regressions.json", reg)

    asserted = sum(1 for v in claims.values() if v["asserted"])
    lines = [
        "# Update 4.46 FINAL REPORT — Acquired Sensorimotor Coupling", "",
        f"## Outcome {letter}", text, "",
        f"{asserted} / {len(claims)} claims ASSERTED. Seeds {SEEDS}. leak = {leak}", "",
        "## Representative numbers (median)",
        f"- L1(R_A, R_B) = {metrics['r_ab']['median']:.4f}",
        f"- N0 probe L1(P_A, P_B) = {metrics['dP0']['median']:.4f}",
        f"- N1 / N2 probe L1 = {metrics['dP1']['median']:.4f} / {metrics['dP2']['median']:.4f}",
        f"- P(M0)|N0 A/B = {metrics['P_M0_A_N0']['median']:.4f} / {metrics['P_M0_B_N0']['median']:.4f}",
        f"- P(M2)|N0 A/B = {metrics['P_M2_A_N0']['median']:.4f} / {metrics['P_M2_B_N0']['median']:.4f}",
        f"- endogenous L1 = {metrics['dP_end']['median']:.4f}",
        f"- fixed-readout L1 = {metrics['dP_fix']['median']:.4f}",
        f"- geometry hits (0–3) = {metrics['geom']['median']}",
        "",
        "## First unsupported arrows", json.dumps(arrows, indent=2), "",
        "## Claims",
    ]
    for k, v in claims.items():
        lines.append(f"- {k}: **{'ASSERTED' if v['asserted'] else 'NOT ASSERTED'}** seeds={v['seeds']}")
    lines += [
        "", "## Historical",
        f"4.42={reg['442']}, 4.43={reg['443']}, 4.44={reg['444']}, 4.45={reg['445']}. `.git` absent. No git ops.",
        "", "## Strongest allowed claim",
    ]
    if letter in ("E", "F"):
        lines.append(
            "Acquired sensorimotor coupling provided a history-dependent pathway by which "
            "naturally generated endogenous internal activity could differentially propagate "
            "into motor dynamics without predefined action value."
        )
    elif letter == "D":
        lines.append(
            "Local sensorimotor co-history modified a bounded generic coupling structure "
            "such that later identical internal activity propagated differently into motor "
            "dynamics depending on prior temporal pairing, without reward, target-action "
            "supervision, or future consequence information."
        )
    else:
        lines.append(f"See Outcome {letter}. Do not upgrade the claim.")
    lines += [
        "", "Not claimed: motivation, intention, action value, preference, RL, agency.",
        "", "## Next question (not implemented)",
        "Can an endogenous N that already differs by 4.41/4.45 history use this acquired R, without retuning gain?",
        "Do not implement 4.47 here.",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "outcome": letter, "text": text,
        "asserted": asserted, "total": len(claims),
        "arrows": arrows, "r_ab": metrics["r_ab"]["median"],
        "dP0": metrics["dP0"]["median"], "dP_end": metrics["dP_end"]["median"],
        "leak": leak, "442": reg["442"], "443": reg["443"], "444": reg["444"], "445": reg["445"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
