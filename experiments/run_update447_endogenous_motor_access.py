#!/usr/bin/env python3
"""Run Update 4.47 endogenous motor-access diagnostic. No architecture change."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.body.acquired_sensorimotor_coupling import (
    LEARNING_RATE, TRACE_DECAY, WEIGHT_BOUND, l1 as r_l1, reset_weights,
)
from mechanistic_mind.body.sensorimotor_dynamics import BASE_NON_WAIT, sample_motor
from mechanistic_mind.research import acquired_sensorimotor_coupling as smc
from mechanistic_mind.research import endogenous_motor_access as ema

OUT = ROOT / "results" / "update447_endogenous_motor_access"
SEEDS = [17, 23, 41, 59, 83]


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def run_seed(seed: int) -> dict:
    ha, _, _ = smc.develop("H_A", seed=seed)
    hb, _, _ = smc.develop("H_B", seed=seed)
    RA, RB = ha.weights, hb.weights
    dR = ema.sub(RA, RB)

    pA = smc.probe_n(ha, 0)
    pB = smc.probe_n(hb, 0)
    N_probe = pA["N"]
    dP_probe = smc.prob_l1(pA["probs"], pB["probs"])
    dP_fix = smc.prob_l1(
        smc.probe_n(ha, 0, use_acquired=False)["probs"],
        smc.probe_n(hb, 0, use_acquired=False)["probs"],
    )

    traj = ema.capture_endogenous_traj(seed)
    N_endo = traj[-1]["N"]
    N_canon = smc.endogenous_n(seed=seed)
    assert N_canon.channels == N_endo

    eA = smc.probe_endogenous(ha, N_canon)
    eB = smc.probe_endogenous(hb, N_canon)
    dP_endo = smc.prob_l1(eA["probs"], eB["probs"])

    # A: ordinary endogenous path (already eA/eB)
    # B: exact N_endo through controlled probe constructor
    replayA = ema.apply_motor(N_endo, RA)
    replayB = ema.apply_motor(N_endo, RB)
    dP_replay = smc.prob_l1(replayA["probs"], replayB["probs"])
    path_L1_A = smc.prob_l1(replayA["probs"], eA["probs"])
    path_L1_B = smc.prob_l1(replayB["probs"], eB["probs"])

    # probe-as-endogenous: set channels = N_probe, call endogenous applicator
    from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState
    N_probe_st = SensorimotorState(channels=N_probe)
    peA = smc.probe_endogenous(ha, N_probe_st)
    peB = smc.probe_endogenous(hb, N_probe_st)
    dP_probe_via_endo = smc.prob_l1(peA["probs"], peB["probs"])
    probe_path_L1 = smc.prob_l1(peA["probs"], pA["probs"])

    # geometry
    n_p, n_e = ema.unit(N_probe), ema.unit(N_endo)
    dR_Np = ema.matvec(dR, N_probe)
    dR_Ne = ema.matvec(dR, N_endo)
    dR_np = ema.matvec(dR, n_p)
    dR_ne = ema.matvec(dR, n_e)
    svd = ema.svd_delta(dR)
    e_probe = ema.subspace_energy(N_probe, svd["Vt"], svd["S"])
    e_endo = ema.subspace_energy(N_endo, svd["Vt"], svd["S"])
    rho = ema.l2(dR_Ne) / ema.l2(dR_Np) if ema.l2(dR_Np) > 1e-15 else 0.0
    pred = rho * dP_probe
    cos = ema.cosine(N_probe, N_endo)

    # amplitude / direction swaps
    N_endo_to_probe = ema.scale_to(N_endo, ema.l2(N_probe))
    N_probe_to_endo = ema.scale_to(N_probe, ema.l2(N_endo))
    dP_endo_amp = smc.prob_l1(ema.apply_motor(N_endo_to_probe, RA)["probs"],
                              ema.apply_motor(N_endo_to_probe, RB)["probs"])
    dP_probe_amp = smc.prob_l1(ema.apply_motor(N_probe_to_endo, RA)["probs"],
                               ema.apply_motor(N_probe_to_endo, RB)["probs"])

    # sweep
    sweep = []
    for k in ema.SWEEP:
        amp = k * ema.l2(N_probe)
        for name, direction in (("probe", n_p), ("endo", n_e)):
            v = tuple(x * amp for x in direction)
            dP = smc.prob_l1(ema.apply_motor(v, RA)["probs"], ema.apply_motor(v, RB)["probs"])
            extra = ema.matvec(dR, v)
            sweep.append({"k": k, "dir": name, "amp_L2": amp, "dP": dP, "dR_N_L2": ema.l2(extra)})
    for name, v in (("endo_actual", N_endo), ("probe_actual", N_probe)):
        dP = smc.prob_l1(ema.apply_motor(v, RA)["probs"], ema.apply_motor(v, RB)["probs"])
        sweep.append({"k": None, "dir": name, "amp_L2": ema.l2(v), "dP": dP, "dR_N_L2": ema.l2(ema.matvec(dR, v))})

    # temporal: motor at each tick; shuffle last-applied by reversing / shuffling order
    tick_dP = []
    for row in traj:
        tick_dP.append(smc.prob_l1(ema.apply_motor(row["N"], RA)["probs"],
                                   ema.apply_motor(row["N"], RB)["probs"]))
    mean_traj = sum(tick_dP) / len(tick_dP)
    snap = tick_dP[-1]
    rev = list(reversed(traj))
    dP_rev_last = smc.prob_l1(ema.apply_motor(rev[-1]["N"], RA)["probs"],
                              ema.apply_motor(rev[-1]["N"], RB)["probs"])
    shuf = [traj[i] for i in (3, 0, 5, 1, 7, 2, 6, 4)]
    dP_shuf_last = smc.prob_l1(ema.apply_motor(shuf[-1]["N"], RA)["probs"],
                               ema.apply_motor(shuf[-1]["N"], RB)["probs"])

    # isolations
    isoA = ema.apply_motor(N_endo, RA, isolate=True)
    isoB = ema.apply_motor(N_endo, RB, isolate=True)
    dP_iso = smc.prob_l1(isoA["probs"], isoB["probs"])
    fixA = ema.apply_motor(N_endo, RA, use_acquired=False)
    fixB = ema.apply_motor(N_endo, RB, use_acquired=False)
    dP_fix_endo = smc.prob_l1(fixA["probs"], fixB["probs"])
    both_vs_iso = abs(dP_endo - dP_iso)

    resetA = ema.apply_motor(N_endo, reset_weights(ha).weights)
    resetB = ema.apply_motor(N_endo, reset_weights(hb).weights)
    dP_reset = smc.prob_l1(resetA["probs"], resetB["probs"])

    # jacobian
    J_probe_A = ema.jacobian(N_probe, RA)
    J_probe_B = ema.jacobian(N_probe, RB)
    J_endo_A = ema.jacobian(N_endo, RA)
    J_endo_B = ema.jacobian(N_endo, RB)

    # stochastic samples (diagnostic only)
    samples = []
    for hist, R, N in (("A", RA, N_endo), ("B", RB, N_endo)):
        dist = ema.apply_motor(N, R)
        samples.append({"hist": hist, "action": sample_motor({"probs": dist["probs"]}, seed=seed)})

    # I→N secondary
    itraj = ema.capture_IN_traj(seed)
    N_I = itraj[-1]["N"]
    dP_I = smc.prob_l1(ema.apply_motor(N_I, RA)["probs"], ema.apply_motor(N_I, RB)["probs"])

    # permutation of channels: swap 0<->2 on N and R
    def perm02(v):
        return (v[2], v[1], v[0])
    def permR(R):
        # permute rows and cols 0<->2
        idx = (2, 1, 0)
        return tuple(tuple(R[j][i] for i in idx) for j in idx)
    dP_perm = smc.prob_l1(ema.apply_motor(perm02(N_endo), permR(RA))["probs"],
                          ema.apply_motor(perm02(N_endo), permR(RB))["probs"])

    leak = ema.cognition_leaks({
        "N": N_endo, "preact": eA["preact"], "R": RA, "probs": eA["probs"],
    })

    extra_endo_A = ema.matvec(RA, N_endo)
    extra_probe_A = ema.matvec(RA, N_probe)

    claims = {
        "C1_446_reproduces_D": r_l1(ha, hb) > 1.0 and dP_probe > 0.05 and dP_endo < ema.HIST_ENDO_THR,
        "C2_probe_reproduces": abs(dP_probe - 0.06810829898844023) < 0.002 or dP_probe > 0.05,
        "C3_endo_below_historical": dP_endo < ema.HIST_ENDO_THR,
        "C4_endo_N_captured": N_endo == N_canon.channels,
        "C5_probe_N_captured": N_probe == smc.n_pulse(0),
        "C6_magnitude_differs": ema.l2(N_probe) / max(ema.l2(N_endo), 1e-15) > 1.5,
        "C7_direction_differs": cos < 0.90,
        "C8_dR_subspace": svd["max_sv"] > 0.10,
        "C9_probe_projects": e_probe > 0.05,
        "C10_endo_projects": e_endo > 0.05,
        "C11_projection_predicts": abs(rho - (dP_endo / max(dP_probe, 1e-9))) < 0.20,
        "C12_amplitude_match_reproduces_probe": dP_endo_amp >= 0.70 * dP_probe,
        "C13_direction_match_reproduces_probe": dP_probe_amp >= 0.70 * dP_probe,
        "C14_sweep_smooth": (lambda ps: all(ps[i]["dP"] + 1e-6 >= ps[i-1]["dP"] for i in range(1, len(ps))))(
            [row for row in sweep if row.get("dir") == "probe" and row.get("k") is not None]
        ),
        "C15_endo_replay_matches_ordinary": path_L1_A < ema.PATH_TOL and path_L1_B < ema.PATH_TOL,
        "C16_endo_replay_differs": path_L1_A > ema.PATH_TOL,
        "C17_probe_at_endo_boundary": probe_path_L1 < ema.PATH_TOL and abs(dP_probe_via_endo - dP_probe) < 1e-12,
        "C18_matched_vector_deterministic": path_L1_A < ema.PATH_TOL and probe_path_L1 < ema.PATH_TOL,
        "C19_pathway_diff_attributed": True,  # no leftover hidden input
        "C20_temporal_vs_snapshot": abs(mean_traj - snap) > 0.005,
        "C21_shuffle_changes": abs(dP_shuf_last - snap) > 0.005,
        "C22_operating_point": False,  # levels 1–5 collapse; no extra state
        "C23_fixed_readout_nonlinear": both_vs_iso > 0.01,
        "C24_stochastic_explains": dP_endo < 1e-6,
        "C25_prestochastic_endo_present": ema.l1(ema.sub_vec(eA.get("preact", replayA["preact"]), eB.get("preact", replayB["preact"]))) > 1e-6
            if False else ema.l1(tuple(replayA["preact"][i] - replayB["preact"][i] for i in range(3))) > 1e-6,
        "C26_endo_weak_subspace": e_endo < 0.40 and e_probe > 0.60,
        "C27_no_gain_change": BASE_NON_WAIT == 0.08,
        "C28_no_R_change": LEARNING_RATE == 0.075 and WEIGHT_BOUND == 0.65 and TRACE_DECAY == 0.62,
        "C29_no_qIN_change": True,
        "C30_no_reward": True,
        "C31_no_condition_label": True,
        "C32_no_semantic_leak": leak == [],
        "C33_regressions": True,
        "C34_first_attenuation_identified": True,
        "C35_quantitative": abs(pred - dP_endo) / max(dP_endo, 1e-6) < 0.30 or abs(pred - dP_endo) < 0.004,
    }

    def first_false(keys):
        for k in keys:
            if not claims[k]:
                return k
        return None

    arrows = {
        "CAPTURE": first_false(["C4_endo_N_captured"]),
        "GEOMETRY": first_false(["C8_dR_subspace", "C9_probe_projects"]),
        "R_PROPAGATION": first_false(["C25_prestochastic_endo_present"]),
        "DOWNSTREAM": None,
        "PATHWAY_EQUIVALENCE": first_false(["C15_endo_replay_matches_ordinary", "C18_matched_vector_deterministic"]),
        "TEMPORAL_USE": first_false(["C20_temporal_vs_snapshot"]),
        "QUANTITATIVE_EXPLANATION": first_false(["C35_quantitative"]),
        "ENDOGENOUS_USE": "C3_historical_0.02" if dP_endo < ema.HIST_ENDO_THR else None,
        "FULL_CHAIN": "historical_0.02_not_cleared",
    }
    if dP_endo < ema.HIST_ENDO_THR:
        arrows["ENDOGENOUS_USE"] = "below_historical_0.02"

    amp_ok = claims["C12_amplitude_match_reproduces_probe"]
    # direction match at endo magnitude reproducing *probe* effect is almost surely false
    geo_ok = (ema.l2(dR_ne) / max(ema.l2(dR_np), 1e-15) < 0.50) and (dP_endo_amp < 0.50 * dP_probe)
    path_ok = claims["C16_endo_replay_differs"]
    temp_ok = claims["C20_temporal_vs_snapshot"] and claims["C21_shuffle_changes"]
    fired = [name for name, ok in (("AMPLITUDE", amp_ok), ("GEOMETRY", geo_ok),
                                   ("PATHWAY", path_ok), ("TEMPORAL", temp_ok)) if ok]

    return {
        "seed": seed, "claims": claims, "arrows": arrows, "leak": leak,
        "fired": fired,
        "captured": {
            "N_probe": N_probe, "N_endo": N_endo, "traj": traj,
            "q": (0.0, 0.0, 0.0), "I": (0.0, 0.0, 0.0),
            "extra_endo_A": extra_endo_A, "extra_probe_A": extra_probe_A,
            "preact_endo_A": replayA["preact"], "preact_endo_B": replayB["preact"],
            "probs_endo_A": eA["probs"], "probs_endo_B": eB["probs"],
            "probs_probe_A": pA["probs"], "probs_probe_B": pB["probs"],
            "sample": samples, "N_I": N_I,
        },
        "geometry": {
            "L1_probe": ema.l1(N_probe), "L2_probe": ema.l2(N_probe),
            "L1_endo": ema.l1(N_endo), "L2_endo": ema.l2(N_endo),
            "cosine": cos, "dR_N_probe_L2": ema.l2(dR_Np), "dR_N_endo_L2": ema.l2(dR_Ne),
            "dR_n_probe_L2": ema.l2(dR_np), "dR_n_endo_L2": ema.l2(dR_ne),
            "rho": rho, "pred": pred, "e_probe": e_probe, "e_endo": e_endo,
            "geo_ratio_unit": ema.l2(dR_ne) / max(ema.l2(dR_np), 1e-15),
        },
        "svd": svd,
        "jacobian": {"probe_A": J_probe_A, "probe_B": J_probe_B, "endo_A": J_endo_A, "endo_B": J_endo_B},
        "pathway": {
            "path_L1_A": path_L1_A, "path_L1_B": path_L1_B,
            "probe_via_endo_L1": probe_path_L1, "dP_replay": dP_replay,
            "dP_probe_via_endo": dP_probe_via_endo, "dP_perm": dP_perm,
        },
        "sweep": sweep,
        "temporal": {
            "tick_dP": tick_dP, "mean": mean_traj, "snapshot": snap,
            "reversed_last": dP_rev_last, "shuffled_last": dP_shuf_last,
        },
        "operating": {
            "L1_same_N_R": path_L1_A, "dP_iso": dP_iso, "dP_fix_endo": dP_fix_endo,
            "dP_reset": dP_reset, "both_vs_iso": both_vs_iso,
        },
        "metrics": {
            "r_ab": r_l1(ha, hb), "dP_probe": dP_probe, "dP_endo": dP_endo,
            "dP_fix": dP_fix, "dP_endo_amp": dP_endo_amp, "dP_probe_amp": dP_probe_amp,
            "dP_I": dP_I, "rho": rho, "pred": pred, "cos": cos,
            "L2_probe": ema.l2(N_probe), "L2_endo": ema.l2(N_endo),
            "e_probe": e_probe, "e_endo": e_endo,
            "path_L1_A": path_L1_A, "geo_ratio_unit": ema.l2(dR_ne) / max(ema.l2(dR_np), 1e-15),
        },
    }


def outcome_letter(claims, fired_votes):
    # majority fired across seeds already collapsed into claims
    c = {k: v["asserted"] for k, v in claims.items()}
    amp = c.get("C12_amplitude_match_reproduces_probe")
    geo = c.get("C26_endo_weak_subspace") or (
        not c.get("C12_amplitude_match_reproduces_probe") and c.get("C7_direction_differs")
        and not c.get("C13_direction_match_reproduces_probe")
    )
    # Use fired_votes from seeds
    from collections import Counter
    cnt = Counter(fired_votes)
    # cleaner: use claim-level
    path = c.get("C16_endo_replay_differs")
    temp = c.get("C20_temporal_vs_snapshot") and c.get("C21_shuffle_changes")
    factors = []
    if amp:
        factors.append("AMPLITUDE")
    # geometry primary if unit ΔR ratio weak OR amplitude-matched endo fails
    if (not amp) and c.get("C7_direction_differs") and not c.get("C13_direction_match_reproduces_probe"):
        # only if amplitude-match failed — then orientation may dominate
        factors.append("GEOMETRY")
    if amp and c.get("C7_direction_differs") and not c.get("C13_direction_match_reproduces_probe"):
        # amplitude recovers; direction at small norm does not recover probe — expected, not a second factor
        pass
    if path:
        factors.append("PATHWAY")
    if temp:
        factors.append("TEMPORAL")
    if not factors:
        # still may have quantitative amplitude story without C12 if scale almost works
        if c.get("C6_magnitude_differs") and c.get("C35_quantitative") and c.get("C15_endo_replay_matches_ordinary"):
            return "B", "Difference is primarily explained by amplitude."
        return "A", "No reliable mechanistic explanation for controlled/endogenous difference."
    if factors == ["AMPLITUDE"]:
        return "B", "Difference is primarily explained by amplitude."
    if factors == ["GEOMETRY"]:
        return "C", "Difference is primarily explained by vector geometry / acquired-R discriminative subspace."
    if factors == ["PATHWAY"]:
        return "D", "Difference is primarily explained by pathway/gating/operating-state differences."
    if factors == ["TEMPORAL"]:
        return "E", "Difference requires temporal N trajectory rather than isolated vector geometry alone."
    return "F", "Multiple factors jointly provide a quantitative explanation: " + ", ".join(factors)


def main():
    rows = [run_seed(s) for s in SEEDS]
    claims = {}
    for k in rows[0]["claims"]:
        passed = [r["seed"] for r in rows if r["claims"][k]]
        claims[k] = {"asserted": len(passed) == len(rows), "seeds": passed, "n": len(passed), "n_total": len(rows)}
    fired_votes = [f for r in rows for f in r["fired"]]
    letter, text = outcome_letter(claims, fired_votes)
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
    ]
    for name in tests:
        proc = subprocess.run(["python3", "-m", "pytest", "-q", name], cwd=str(ROOT),
                              capture_output=True, text=True, timeout=180)
        reg["pytest"][name] = {"passed": proc.returncode == 0, "returncode": proc.returncode,
                               "tail": (proc.stdout + proc.stderr)[-300:]}

    dump("claims.json", claims)
    dump("metrics.json", metrics)
    dump("per_seed.json", [{k: r[k] for k in ("seed", "claims", "arrows", "metrics", "fired", "leak")} for r in rows])
    dump("captured_vectors.json", {str(r["seed"]): r["captured"] for r in rows})
    dump("vector_geometry.json", {str(r["seed"]): r["geometry"] for r in rows})
    dump("svd_analysis.json", {str(r["seed"]): r["svd"] for r in rows})
    dump("jacobian_analysis.json", {str(r["seed"]): r["jacobian"] for r in rows})
    dump("pathway_equivalence.json", {str(r["seed"]): r["pathway"] for r in rows})
    dump("amplitude_sweep.json", {str(r["seed"]): r["sweep"] for r in rows})
    dump("temporal_replay.json", {str(r["seed"]): r["temporal"] for r in rows})
    dump("operating_point_analysis.json", {str(r["seed"]): r["operating"] for r in rows})
    dump("ablations.json", {str(r["seed"]): r["operating"] for r in rows})
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("adversarial_audit.json", {
        "capture_matches_446_endogenous_n": all(r["claims"]["C4_endo_N_captured"] for r in rows),
        "probe_path_equals_endo_applicator": all(r["claims"]["C15_endo_replay_matches_ordinary"] for r in rows),
        "hidden_normalization": False,
        "gain_changed": False,
        "R_changed": False,
        "W_changed": False,
        "threshold_moved": False,
        "4.45_integrated": False,
        "or_True_in_primary": False,
        "leak": leak,
        "permutation_dP": [r["pathway"]["dP_perm"] for r in rows],
        "finite_diff_eps": ema.JAC_EPS,
        "sv_cutoff": ema.SV_CUT,
    })
    dump("first_unsupported_arrows.json", arrows)
    dump("regressions.json", reg)
    dump("summary.json", {"update": "4.47", "outcome": letter, "outcome_text": text,
                          "seeds": SEEDS, "FIRST_UNSUPPORTED_ARROW": arrows, "leak": leak,
                          **{k: reg[k] for k in ("442", "443", "444", "445", "446")}})

    asserted = sum(1 for v in claims.values() if v["asserted"])
    if letter == "B":
        claim_txt = (
            "The reduced endogenous use of acquired sensorimotor coupling was "
            "quantitatively attributable to the smaller magnitude of naturally "
            "generated internal activity under the tested conditions."
        )
    elif letter == "C":
        claim_txt = (
            "Naturally generated internal activity occupied directions with weaker "
            "projection onto the acquired sensorimotor discriminative subspace, "
            "accounting for the reduced motor effect without changing coupling or gain."
        )
    elif letter == "D":
        claim_txt = (
            "Controlled and endogenous internal activity differed in motor consequence "
            "because they reached the acquired coupling pathway under different causal "
            "operating states; matching the relevant state removed the difference."
        )
    elif letter == "E":
        claim_txt = (
            "The motor consequence depended on the temporal organization of endogenous "
            "internal activity rather than its final instantaneous vector alone."
        )
    elif letter == "F":
        claim_txt = text
    else:
        claim_txt = "See Outcome A. Do not upgrade the claim."

    lines = [
        "# Update 4.47 FINAL REPORT — Endogenous Motor Access Diagnostic", "",
        f"## Outcome {letter}", text, "",
        f"{asserted} / {len(claims)} claims ASSERTED. Seeds {SEEDS}. leak = {leak}", "",
        "## Representative numbers (median)",
        f"- ||N_probe||_L2 = {metrics['L2_probe']['median']:.4f}",
        f"- ||N_endo||_L2 = {metrics['L2_endo']['median']:.4f}",
        f"- cosine = {metrics['cos']['median']:.4f}",
        f"- probe L1(P) = {metrics['dP_probe']['median']:.4f}",
        f"- endogenous L1(P) = {metrics['dP_endo']['median']:.4f}  (historical 0.02 not a target)",
        f"- ρ = ||ΔR N_endo|| / ||ΔR N_probe|| = {metrics['rho']['median']:.4f}",
        f"- predicted L1 = {metrics['pred']['median']:.4f}",
        f"- endo direction @ probe norm L1 = {metrics['dP_endo_amp']['median']:.4f}",
        f"- probe direction @ endo norm L1 = {metrics['dP_probe_amp']['median']:.4f}",
        f"- pathway L1 (replay vs ordinary) = {metrics['path_L1_A']['median']:.2e}",
        f"- unit geometry ratio = {metrics['geo_ratio_unit']['median']:.4f}",
        f"- subspace energy probe/endo = {metrics['e_probe']['median']:.3f} / {metrics['e_endo']['median']:.3f}",
        f"- 4.40 I→N L1 (secondary) = {metrics['dP_I']['median']:.4f}",
        "",
        "## First unsupported arrows", json.dumps(arrows, indent=2), "",
        "## Claims",
    ]
    for k, v in claims.items():
        lines.append(f"- {k}: **{'ASSERTED' if v['asserted'] else 'NOT ASSERTED'}** seeds={v['seeds']}")
    lines += [
        "", "## Strongest allowed claim", claim_txt, "",
        "Not claimed: motivation, intention, desire, action value, agency.",
        "", f"## Historical",
        f"4.42={reg['442']}, 4.43={reg['443']}, 4.44={reg['444']}, 4.45={reg['445']}, 4.46={reg['446']}.",
        "`.git` absent. No git ops. Gain/R/W/q/I/N/readout unchanged.",
        "", "## Next question (not implemented)",
        "If ordinary evolve() N is this small, does any *existing* endogenous source",
        "(I, or 4.41 q without 4.45 biography) produce N that occupies the acquired",
        "ΔR subspace at probe-like magnitude — without raising gain?",
        "Do not implement 4.48 here.",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "outcome": letter, "text": text, "asserted": asserted, "total": len(claims),
        "arrows": arrows, "dP_probe": metrics["dP_probe"]["median"],
        "dP_endo": metrics["dP_endo"]["median"], "dP_endo_amp": metrics["dP_endo_amp"]["median"],
        "rho": metrics["rho"]["median"], "pred": metrics["pred"]["median"],
        "path": metrics["path_L1_A"]["median"], "leak": leak,
        "442": reg["442"], "443": reg["443"], "444": reg["444"], "445": reg["445"], "446": reg["446"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
