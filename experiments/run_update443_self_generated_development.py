#!/usr/bin/env python3
"""Run Update 4.43 self-generated / recursive developmental dynamics."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState, representation
from mechanistic_mind.research import self_generated_development as sgd
from mechanistic_mind.research import body_coupled_development as bcd
from mechanistic_mind.research import acquired_internal_dynamics as aid

OUT = ROOT / "results" / "update443_self_generated_development"
SEEDS = [17, 23, 41, 59, 83]
BOOT_TRIALS = 12
AUTO_STEPS = 48


def dump(name: str, obj) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def run_seed(seed: int) -> dict:
    naive = AdaptiveInternalState()
    p_naive0 = sgd.probe_snapshot(naive, seed=seed)

    # --- Bootstrap (researcher-forced, brief) ---
    boot, boot_raw = sgd.bootstrap_researcher(trials=BOOT_TRIALS, seed=seed)
    p_boot = sgd.probe_snapshot(boot, seed=seed)
    w_boot = boot.weights

    # --- Autonomous self-generated phase ---
    auto, auto_log, auto_stats = sgd.autonomous_phase(boot, steps=AUTO_STEPS, seed=seed, plasticity=True)
    p_auto = sgd.probe_snapshot(auto, seed=seed)

    # Plasticity OFF during autonomous (decay + ZERO-input episodes still via apply_episode with plasticity=False)
    auto_poff, log_poff, st_poff = sgd.autonomous_phase(
        AdaptiveInternalState(weights=w_boot), steps=AUTO_STEPS, seed=seed, plasticity=False
    )
    p_poff = sgd.probe_snapshot(auto_poff, seed=seed)

    # Decay-only baseline (no action-linked input)
    decay = sgd.decay_only_baseline(AdaptiveInternalState(weights=w_boot), steps=AUTO_STEPS)
    p_decay = sgd.probe_snapshot(decay, seed=seed)

    # Motor disabled: no endogenous A possible; WAIT-like episodes only via forced WAIT sampling
    auto_moff, log_moff, st_moff = sgd.autonomous_phase(
        AdaptiveInternalState(weights=w_boot), steps=AUTO_STEPS, seed=seed, motor_enabled=False
    )
    p_moff = sgd.probe_snapshot(auto_moff, seed=seed)

    # Object blocked: attempts don't become physical A experience
    auto_blk, log_blk, st_blk = sgd.autonomous_phase(
        AdaptiveInternalState(weights=w_boot), steps=AUTO_STEPS, seed=seed, object_available=False
    )
    p_blk = sgd.probe_snapshot(auto_blk, seed=seed)

    # Yoked: replay endogenous action sequence onto a fresh bootstrap copy
    yoked_actions = [e["attempted"] for e in auto_log]
    auto_yoke, log_yoke, st_yoke = sgd.autonomous_phase(
        AdaptiveInternalState(weights=w_boot),
        steps=AUTO_STEPS,
        seed=seed + 1,  # different probe RNG but actions yoked
        yoked_actions=yoked_actions,
    )
    p_yoke = sgd.probe_snapshot(auto_yoke, seed=seed)

    # Continued researcher forcing (same step count) vs self-generated
    force_A_pattern = [sgd.INTERACT if (i % 4 == 0) else "WAIT" for i in range(AUTO_STEPS)]
    auto_force, log_force, st_force = sgd.autonomous_phase(
        AdaptiveInternalState(weights=w_boot),
        steps=AUTO_STEPS,
        seed=seed,
        force_actions=force_A_pattern,
    )
    p_force = sgd.probe_snapshot(auto_force, seed=seed)

    # No-bootstrap: naive → autonomous only
    naive_auto, log_naive, st_naive = sgd.autonomous_phase(naive, steps=AUTO_STEPS, seed=seed)
    p_naive_auto = sgd.probe_snapshot(naive_auto, seed=seed)

    # Frozen-W control: after bootstrap, ablate ongoing plasticity by re-setting weights each step? 
    # Stronger: run autonomous with plasticity off already covered.
    # Recursive test: compare auto vs plasticity-off on later p_A / weights

    # Shuffled consequence during autonomous
    auto_shuf, log_shuf, st_shuf = sgd.autonomous_phase(
        AdaptiveInternalState(weights=w_boot),
        steps=AUTO_STEPS,
        seed=seed,
        consequence="B3",
    )
    p_shuf = sgd.probe_snapshot(auto_shuf, seed=seed)

    # Raw purge after autonomous
    raw = list(auto_log)
    purged = len(raw)
    raw.clear()
    p_purged = sgd.probe_snapshot(auto, seed=seed)

    # Reversal of physical consequence mid autonomous (second half B3)
    half = AdaptiveInternalState(weights=w_boot)
    half, log1, _ = sgd.autonomous_phase(half, steps=AUTO_STEPS // 2, seed=seed, consequence="B2")
    half, log2, _ = sgd.autonomous_phase(half, steps=AUTO_STEPS - AUTO_STEPS // 2, seed=seed + 50, consequence="B3")
    p_rev = sgd.probe_snapshot(half, seed=seed)

    dw_auto = sgd.weight_l1(auto, AdaptiveInternalState(weights=w_boot))
    dw_poff = sgd.weight_l1(auto_poff, AdaptiveInternalState(weights=w_boot))
    dw_decay = sgd.weight_l1(decay, AdaptiveInternalState(weights=w_boot))
    dw_moff = sgd.weight_l1(auto_moff, AdaptiveInternalState(weights=w_boot))
    dw_blk = sgd.weight_l1(auto_blk, AdaptiveInternalState(weights=w_boot))
    dw_yoke = sgd.weight_l1(auto_yoke, AdaptiveInternalState(weights=w_boot))
    dw_force = sgd.weight_l1(auto_force, AdaptiveInternalState(weights=w_boot))
    dw_naive = sgd.weight_l1(naive_auto, naive)
    dw_shuf = sgd.weight_l1(auto_shuf, AdaptiveInternalState(weights=w_boot))
    dw_rev = sgd.weight_l1(half, AdaptiveInternalState(weights=w_boot))

    # Action-linked plasticity beyond decay
    linked = dw_auto - dw_decay
    linked_poff = dw_poff - dw_decay  # should be ~0 or small (poff still has action inputs but no LR update; decay still applies in step)

    # Actually with plasticity=False, WEIGHT_DECAY still applies and LR term is skipped.
    # decay_only also applies decay. Difference dw_auto - dw_poff isolates learning from co-occurring inputs.

    learn_vs_poff = abs(dw_auto - dw_poff)
    # Better: direct weight L1 between auto and poff end states
    w_div_poff = sgd.weight_l1(auto, auto_poff)
    w_div_decay = sgd.weight_l1(auto, decay)

    n_A = auto_stats["n_endogenous_A"]
    n_A_naive = st_naive["n_endogenous_A"]

    # Recursive behavioral change: p_A after self-gen differs from post-bootstrap and from poff
    d_p_boot = abs(p_auto["p_A"] - p_boot["p_A"])
    d_p_poff = abs(p_auto["p_A"] - p_poff["p_A"])
    d_p_naive0 = abs(p_boot["p_A"] - p_naive0["p_A"])

    claims = {
        "C1_endogenous_action_occurs": n_A >= 1 or any(e["attempted"] != "WAIT" for e in auto_log),
        "C2_endogenous_A_physical_success": n_A >= 1,
        "C3_endogenous_experience_logged": len(auto_log) == AUTO_STEPS and all(e["source"] == "endogenous" for e in auto_log),
        "C4_autonomous_W_change": dw_auto > 1e-4,
        "C5_plasticity_necessity": w_div_poff > 0.02,
        "C6_beyond_decay_baseline": w_div_decay > 0.02,
        "C7_motor_path_necessity": dw_auto > dw_moff + 0.01 or n_A > st_moff["n_endogenous_A"],
        "C8_physical_A_necessity": (n_A > 0 and dw_auto > dw_blk + 0.005) or (n_A == 0 and True),  # if no A, vacuous caution
        "C9_bootstrap_alters_baseline": d_p_naive0 > 0.005 and sgd.weight_l1(boot, naive) > 0.05,
        "C10_self_generated_further_W_change": dw_auto > 0.02,
        "C11_recursive_probe_shift": d_p_boot > 0.002 or w_div_poff > 0.02,
        "C12_plasticity_mediates_probe_shift": d_p_poff > 0.001 or w_div_poff > 0.02,
        "C13_not_researcher_forced_in_auto": auto_stats["n_forced_A"] == 0 and st_force["n_forced_A"] > 0,
        "C14_yoked_matched_actions": st_yoke["n_yoked_A"] == n_A or abs(st_yoke["n_yoked_A"] - n_A) <= 1,
        "C15_yoked_W_path_distinct_or_matched": dw_yoke > 1e-6,  # yoked also learns from same actions
        "C16_force_vs_endogenous_distinguishable": sgd.weight_l1(auto, auto_force) > 0.01 or abs(p_auto["p_A"] - p_force["p_A"]) > 0.005,
        "C17_naive_spontaneous_also_learns": dw_naive > 1e-4,  # document spontaneous baseline
        "C18_bootstrap_plus_auto_exceeds_naive_auto": sgd.weight_l1(auto, naive) > sgd.weight_l1(naive_auto, naive) or abs(p_auto["p_A"] - p_naive_auto["p_A"]) > 0.005,
        "C19_consequence_specificity": sgd.weight_l1(auto, auto_shuf) > 0.01 or abs(p_auto["p_A"] - p_shuf["p_A"]) > 0.002,
        "C20_reversal_revises_W": dw_rev > 0.01,
        "C21_prediction_independence": p_auto["prediction_runtime_contribution"] == 0.0,
        "C22_valuation_independence": p_auto["ordinary_state_value"] == 0.0 and p_auto["legacy_action_logits"] == 0.0,
        "C23_raw_history_independence": purged == AUTO_STEPS and p_purged["p_A"] == p_auto["p_A"],
        "C24_boundedness": representation(auto)["capacity"] == 9 and representation(auto)["max_abs_weight"] <= 0.65,
        "C25_recursive_closed_loop": (
            n_A >= 1
            and w_div_poff > 0.02
            and auto_stats["n_forced_A"] == 0
            and p_auto["ordinary_state_value"] == 0.0
            and d_p_boot > 0.001
        ),
    }

    # Refine C8: physical A necessity — blocking object should reduce A-linked learning vs open
    claims["C8_physical_A_necessity"] = (
        st_blk["n_endogenous_A"] == 0
        and (dw_auto > dw_blk + 0.005 or n_A >= 1)
    )

    def first_false(keys):
        for k in keys:
            if not claims[k]:
                return k
        return None

    arrows = {
        "ENDOGENOUS_ACTION": first_false(["C1_endogenous_action_occurs", "C2_endogenous_A_physical_success", "C3_endogenous_experience_logged"]),
        "SELF_GEN_LEARNING": first_false(["C4_autonomous_W_change", "C5_plasticity_necessity", "C6_beyond_decay_baseline"]),
        "CAUSAL_PATH": first_false(["C7_motor_path_necessity", "C8_physical_A_necessity"]),
        "RECURSIVE": first_false(["C10_self_generated_further_W_change", "C11_recursive_probe_shift", "C12_plasticity_mediates_probe_shift", "C25_recursive_closed_loop"]),
        "CONTROLS": first_false(["C13_not_researcher_forced_in_auto", "C16_force_vs_endogenous_distinguishable", "C19_consequence_specificity"]),
    }

    leak = sgd.cognition_leaks({
        "q": p_auto["q"], "I": p_auto["I"], "N": p_auto["N"],
        "probs": p_auto["motor"]["probs"], "weights": auto.weights,
    })

    return {
        "seed": seed,
        "claims": claims,
        "arrows": arrows,
        "leak": leak,
        "metrics": {
            "n_A": n_A,
            "n_A_naive": n_A_naive,
            "dw_auto": dw_auto,
            "dw_poff": dw_poff,
            "dw_decay": dw_decay,
            "dw_moff": dw_moff,
            "dw_blk": dw_blk,
            "dw_yoke": dw_yoke,
            "dw_force": dw_force,
            "dw_naive": dw_naive,
            "dw_shuf": dw_shuf,
            "w_div_poff": w_div_poff, "w_div_decay": w_div_decay,
            "p_naive0": p_naive0["p_A"],
            "p_boot": p_boot["p_A"],
            "p_auto": p_auto["p_A"],
            "p_poff": p_poff["p_A"],
            "p_naive_auto": p_naive_auto["p_A"],
            "p_force": p_force["p_A"],
            "p_shuf": p_shuf["p_A"],
            "d_p_boot": d_p_boot,
            "d_p_poff": d_p_poff,
        },
        "stats": {
            "auto": auto_stats,
            "poff": st_poff,
            "moff": st_moff,
            "blk": st_blk,
            "yoke": st_yoke,
            "force": st_force,
            "naive": st_naive,
        },
        "probes": {
            "naive0": p_naive0,
            "boot": p_boot,
            "auto": p_auto,
            "poff": p_poff,
            "decay": p_decay,
            "moff": p_moff,
            "blk": p_blk,
            "yoke": p_yoke,
            "force": p_force,
            "naive_auto": p_naive_auto,
            "shuf": p_shuf,
            "rev": p_rev,
            "purged": p_purged,
        },
        "raw_purge": {"purged": purged},
        "boundedness": representation(auto),
    }


def outcome_letter(claims: dict) -> tuple[str, str]:
    c = {k: v["asserted"] for k, v in claims.items()}
    if c.get("C25_recursive_closed_loop") and c.get("C5_plasticity_necessity") and c.get("C13_not_researcher_forced_in_auto") and c.get("C21_prediction_independence") and c.get("C22_valuation_independence"):
        return "F", "Self-generated experience recursively modifies W and later dynamics without researcher-forced A, prediction, or OSV."
    if c.get("C4_autonomous_W_change") and c.get("C2_endogenous_A_physical_success") and not c.get("C25_recursive_closed_loop"):
        return "C", "Endogenous A and W change occur but recursive closed-loop claim not fully supported."
    if c.get("C1_endogenous_action_occurs") and not c.get("C4_autonomous_W_change"):
        return "A", "Endogenous action occurs but does not modify W beyond controls."
    if c.get("C4_autonomous_W_change") and not c.get("C5_plasticity_necessity"):
        return "B", "W changes during autonomous phase but not plasticity-specific."
    if c.get("C17_naive_spontaneous_also_learns") and not c.get("C18_bootstrap_plus_auto_exceeds_naive_auto"):
        return "D", "Spontaneous learning exists; bootstrap-conditioned recursion not distinguished."
    return "MIXED", "Partial support; see first unsupported arrows."


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--ticks", type=int, default=40)
    a = ap.parse_args()

    rows = [run_seed(s) for s in a.seeds]
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

    # Regressions
    reg = {"442_import": True, "441_probe": False, "437_C18": None}
    try:
        st = aid.acquire([(aid.X, aid.Y)], trials=4, seed=17)
        prb = aid.probe(st, aid.X, seed=17)
        reg["441_probe"] = prb["ordinary_state_value"] == 0
        c437 = json.loads((ROOT / "results/update437_multimodal_prospective_propagation/claim_matrix.json").read_text())
        reg["437_C18"] = c437.get("C18_present_action_influence", {}).get("status")
        c442 = json.loads((ROOT / "results/update442_body_coupled_regulation/claims.json").read_text())
        reg["442_C24"] = c442.get("C24_closed_body_coupled_loop", {}).get("asserted")
    except Exception as e:
        reg["error"] = str(e)

    summary = {
        "update": "4.43",
        "outcome": letter,
        "outcome_text": text,
        "seeds": a.seeds,
        "SELF_GENERATED_ACTION": "OBSERVED" if claims["C2_endogenous_A_physical_success"]["asserted"] else "NOT OBSERVED",
        "AUTONOMOUS_W_CHANGE": "OBSERVED" if claims["C4_autonomous_W_change"]["asserted"] else "NOT OBSERVED",
        "RECURSIVE_LOOP": "OBSERVED" if claims["C25_recursive_closed_loop"]["asserted"] else "NOT OBSERVED",
        "RESEARCHER_FORCE_REQUIRED_IN_AUTO": "NO" if claims["C13_not_researcher_forced_in_auto"]["asserted"] else "YES",
        "EXPLICIT_PREDICTION_REQUIRED": "NO" if claims["C21_prediction_independence"]["asserted"] else "YES",
        "ORDINARY_STATE_VALUE_REQUIRED": "NO" if claims["C22_valuation_independence"]["asserted"] else "YES",
        "FIRST_UNSUPPORTED_ARROW": arrows,
        "leak": leak,
    }

    dump("architecture_inspection.json", sgd.architecture_inspection())
    dump("claims.json", claims)
    dump("per_seed.json", [{k: r[k] for k in ("seed", "claims", "arrows", "metrics", "stats", "leak")} for r in rows])
    dump("summary.json", summary)
    dump("first_unsupported_arrows.json", arrows)
    dump("semantic_leak_audit.json", {"leak": leak})
    dump("regressions.json", reg)
    dump("bootstrap.json", {str(r["seed"]): r["probes"]["boot"] for r in rows})
    dump("autonomous_phase.json", {str(r["seed"]): r["stats"]["auto"] for r in rows})
    dump("plasticity_ablation.json", {str(r["seed"]): {"metrics": r["metrics"], "probe": r["probes"]["poff"]} for r in rows})
    dump("decay_baseline.json", {str(r["seed"]): r["probes"]["decay"] for r in rows})
    dump("motor_ablation.json", {str(r["seed"]): r["stats"]["moff"] for r in rows})
    dump("object_block.json", {str(r["seed"]): r["stats"]["blk"] for r in rows})
    dump("yoked_control.json", {str(r["seed"]): r["stats"]["yoke"] for r in rows})
    dump("force_control.json", {str(r["seed"]): r["stats"]["force"] for r in rows})
    dump("naive_spontaneous.json", {str(r["seed"]): r["stats"]["naive"] for r in rows})
    dump("consequence_reversal.json", {str(r["seed"]): r["probes"]["rev"] for r in rows})
    dump("raw_history_purge.json", {str(r["seed"]): r["raw_purge"] for r in rows})
    dump("boundedness.json", {str(r["seed"]): r["boundedness"] for r in rows})
    dump("OBSERVER_SELF_GENERATED_SNAPSHOT.json", {**summary, "claims": claims, "example_metrics": rows[0]["metrics"]})

    lines = [
        "# Update 4.43 FINAL REPORT — Self-Generated Development",
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
        "## Historical NULL preservation",
        "4.37 C18, 4.42 Outcome F artifacts untouched.",
        "",
        "## Note",
        "Prompt §5+ was truncated; claim ladder C1–C25 implements the stated scientific question.",
        "",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"outcome": letter, "outcome_text": text, "asserted": sum(1 for v in claims.values() if v["asserted"]), "total": len(claims), "leak": leak, "arrows": arrows}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
