#!/usr/bin/env python3
"""Update 4.35 - Predictive structure selection experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import predictive_structure_selection as pss
from mechanistic_mind.research import multimodal_consequence_learning as mm

OUT = ROOT / "results" / "update435_predictive_structure_selection"
SEEDS = [17, 23, 41, 59, 83]

# Pre-registered thresholds (fixed before outcome inspection)
MIN_USEFUL_DELTA = 0.01
MAX_NULL_DELTA = 0.005


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def strip(d):
    if not isinstance(d, dict):
        return d
    return {k: v for k, v in d.items() if k != "store"}


def run_seed(seed: int) -> dict:
    out = {"seed": seed, "architecture": pss.architecture_inspection()}

    pers = pss.run_process("persistent", pss.gen_persistent_regimes(n=600, seed=seed), seed=seed)
    iid = pss.run_process("broad_iid", pss.gen_broad_iid(n=600, seed=seed), seed=seed)
    mem = pss.run_process("memoryless_bimodal", pss.gen_memoryless_bimodal(n=600, seed=seed), seed=seed)
    drift = pss.run_process("drift", pss.gen_drift(n=600, seed=seed), seed=seed)
    sep = pss.run_process("separated_same_future", pss.gen_separated_same_future(n=600, seed=seed), seed=seed)
    hist_series, _tags = pss.gen_history_different_futures(n=750, seed=seed)
    hist = pss.run_process("hist_diff_future", hist_series, seed=seed)
    hist_same = pss.run_process("hist_same_future", pss.gen_history_same_future(n=750, seed=seed), seed=seed)

    # appearance / dissolution: compare mid vs end contribution via two-phase series
    app_series = pss.gen_appearance(n1=300, n2=400, seed=seed)
    app = pss.run_process("appearance", app_series, seed=seed)
    # phase-split: run separately
    app1 = pss.run_process("appearance_phase1", app_series[:300], seed=seed)
    app2 = pss.run_process("appearance_phase2", app_series[300:], seed=seed + 1)

    dis_series = pss.gen_dissolution(n1=400, n2=400, seed=seed)
    dis1 = pss.run_process("dis_phase1", dis_series[:400], seed=seed)
    dis2 = pss.run_process("dis_phase2", dis_series[400:], seed=seed + 2)

    # shuffle ablation on persistent
    shuf_store = pss.empty_pss_store()
    shuf = pss.prequential_stream(
        shuf_store, antecedent=pss.base_S(), action="A0",
        series=pss.gen_persistent_regimes(n=600, seed=seed), shuffle_follow=True, seed=seed,
    )

    # follow OFF
    off = pss.run_process("follow_off", pss.gen_persistent_regimes(n=400, seed=seed), seed=seed, ablate_follow=True, ablate_context=True)

    # purge
    pers2 = pss.run_process("pers_purge", pss.gen_persistent_regimes(n=500, seed=seed + 3), seed=seed + 3)
    probe = pss.gen_persistent_regimes(n=200, seed=seed + 99)
    purged = pss.purge_and_reprobe(pers2["store"], probe, seed=seed)

    # capacity pressure on follow: long persistent
    longp = pss.run_process("long", pss.gen_persistent_regimes(n=2000, seed=seed), seed=seed)

    # Claims
    c1 = pers["n_follow_keys"] >= 1 and pers["err_full"] is not None
    c2 = pss.contribution_ok(pers["delta_collapsed_minus_full"], min_delta=MIN_USEFUL_DELTA) and pers["n_components"] >= 2
    c3 = pss.little_contribution(iid["delta_collapsed_minus_full"], max_delta=MAX_NULL_DELTA)
    # C4: retain multimodal (n_comp>=2) AND no next-prediction from identity
    c4 = mem["n_components"] >= 2 and pss.little_contribution(mem["delta_collapsed_minus_full"], max_delta=MAX_NULL_DELTA)
    # C5: matched mean/var-ish: persistent useful, broad iid not
    c5 = c2 and c3
    # C6: drift should NOT show strong discrete predictive regimes
    # Pre-registered: n_components<=2 AND |delta|<0.02
    c6 = drift["n_components"] <= 2 and abs(drift["delta_collapsed_minus_full"] or 0) < 0.02
    # C7: history/context improves when futures differ; component-only may be weak
    c7 = pss.contribution_ok(hist["delta_collapsed_minus_context"], min_delta=MIN_USEFUL_DELTA)
    # C8: same future => context contribution negligible
    c8 = pss.little_contribution(hist_same["delta_collapsed_minus_context"], max_delta=MAX_NULL_DELTA)
    # C9: formation — phase1 little, phase2 useful
    c9 = (
        pss.little_contribution(app1["delta_collapsed_minus_full"], max_delta=0.01)
        and pss.contribution_ok(app2["delta_collapsed_minus_full"], min_delta=MIN_USEFUL_DELTA)
    )
    # C10: dissolution — phase1 useful, phase2 little
    c10 = (
        pss.contribution_ok(dis1["delta_collapsed_minus_full"], min_delta=MIN_USEFUL_DELTA)
        and pss.little_contribution(dis2["delta_collapsed_minus_full"], max_delta=0.01)
    )
    # C11 boundedness
    c11 = (
        longp["n_components"] <= mm.MAX_COMPONENTS
        and longp["n_follow_keys"] <= pss.MAX_FOLLOW_KEYS
        and longp["n_ctx_keys"] <= pss.MAX_CTX_FOLLOW
    )

    # shuffle should destroy advantage
    shuffle_breaks = not pss.contribution_ok(shuf["delta_collapsed_minus_full"], min_delta=MIN_USEFUL_DELTA)
    follow_off_flat = abs(off["delta_collapsed_minus_full"] or 0) <= MAX_NULL_DELTA
    sep_no_contrib = pss.little_contribution(sep["delta_collapsed_minus_full"], max_delta=MAX_NULL_DELTA)

    claims = {
        "C1_future_predictive_component_association": bool(c1),
        "C2_persistent_regime_predictive_contribution": bool(c2),
        "C3_iid_noise_rejection": bool(c3),
        "C4_memoryless_multimodal_distinction": bool(c4),
        "C5_structure_beyond_mean_variance": bool(c5),
        "C6_continuous_drift_control": bool(c6),
        "C7_same_present_different_history": bool(c7),
        "C8_history_irrelevance_control": bool(c8),
        "C9_online_formation": bool(c9),
        "C10_online_dissolution": bool(c10),
        "C11_boundedness": bool(c11),
    }

    ladder = [
        ("C1_future_predictive_component_association", "numerical_to_component_conditioned_association"),
        ("C2_persistent_regime_predictive_contribution", "association_to_measurable_predictive_contribution"),
        ("C3_iid_noise_rejection", "contribution_to_noise_rejection"),
        ("C4_memoryless_multimodal_distinction", "noise_rejection_to_memoryless_multimodal_distinction"),
        ("C5_structure_beyond_mean_variance", "multimodal_to_structure_beyond_mean_variance"),
        ("C6_continuous_drift_control", "structure_to_continuous_drift_control"),
        ("C7_same_present_different_history", "drift_control_to_history_dependent_prediction"),
        ("C8_history_irrelevance_control", "history_prediction_to_history_irrelevance_control"),
        ("C9_online_formation", "controls_to_online_formation"),
        ("C10_online_dissolution", "formation_to_online_dissolution"),
        ("C11_boundedness", "dissolution_to_boundedness"),
    ]
    first = None
    for key, arrow in ladder:
        if not claims[key]:
            first = arrow
            break

    leak = []
    for blob in (pers, iid, mem, drift, hist, claims, pss.architecture_inspection()):
        leak.extend(pss.audit_forbidden(strip(blob)))
    leak = sorted(set(leak))

    out.update(claims)
    out.update({
        "persistent": strip(pers),
        "broad_iid": strip(iid),
        "memoryless_bimodal": strip(mem),
        "drift": strip(drift),
        "separated_same_future": strip(sep),
        "hist_diff": strip(hist),
        "hist_same": strip(hist_same),
        "appearance_phase1": strip(app1),
        "appearance_phase2": strip(app2),
        "dissolution_phase1": strip(dis1),
        "dissolution_phase2": strip(dis2),
        "shuffle": strip(shuf),
        "follow_off": strip(off),
        "purge_probe": purged,
        "long": strip(longp),
        "ablations": {
            "shuffle_breaks": shuffle_breaks,
            "follow_off_flat": follow_off_flat,
            "separated_same_future_no_contrib": sep_no_contrib,
        },
        "first_unsupported_arrow": first,
        "leak_tokens": leak,
        "note_434": "4.34 geometric C4 remains historical NULL; not rewritten",
        "drift_note": (
            f"drift n_components={drift['n_components']} delta={drift['delta_collapsed_minus_full']} "
            "(discrete predictive organization of continuous correlation)"
        ),
    })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=",".join(map(str, SEEDS)))
    ap.add_argument("--ticks", type=int, default=40)
    args = ap.parse_args()
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    per = [run_seed(s) for s in seeds]
    dump("per_seed_results.json", per)

    keys = [k for k in per[0] if k.startswith("C") and k[1].isdigit()]
    # stable order
    keys = [
        "C1_future_predictive_component_association",
        "C2_persistent_regime_predictive_contribution",
        "C3_iid_noise_rejection",
        "C4_memoryless_multimodal_distinction",
        "C5_structure_beyond_mean_variance",
        "C6_continuous_drift_control",
        "C7_same_present_different_history",
        "C8_history_irrelevance_control",
        "C9_online_formation",
        "C10_online_dissolution",
        "C11_boundedness",
    ]

    def agg(k):
        hits = [str(r["seed"]) for r in per if r.get(k)]
        return {"status": "ASSERTED" if len(hits) == len(per) else "NOT ASSERTED", "seeds": hits, "n": len(hits), "n_total": len(per)}

    matrix = {k: agg(k) for k in keys}
    dump("claim_matrix.json", matrix)
    dump("architecture_inspection.json", pss.architecture_inspection())
    firsts = [r["first_unsupported_arrow"] for r in per]
    leaks = sorted({t for r in per for t in (r.get("leak_tokens") or [])})
    dump("leak_audit.json", {"leak": leaks})

    c = {k: matrix[k]["status"] == "ASSERTED" for k in keys}
    if c["C5_structure_beyond_mean_variance"] and not c["C6_continuous_drift_control"]:
        outcome = "C"
        outcome_text = (
            "Sequential predictive contribution distinguishes persistent regimes from iid/"
            "memoryless mixture, but continuous drift is also organized into apparently "
            "predictive discrete components (C6 NULL)."
        )
    elif c["C5_structure_beyond_mean_variance"] and c["C6_continuous_drift_control"] and not c["C7_same_present_different_history"]:
        outcome = "D"
        outcome_text = "Component-conditioned prediction works; history-dependent overlapping-present fails."
    elif all(c[k] for k in keys):
        outcome = "E"
        outcome_text = "Major claims including history-dependent controls pass."
    elif c["C1_future_predictive_component_association"] and c["C2_persistent_regime_predictive_contribution"] and not c["C5_structure_beyond_mean_variance"]:
        outcome = "B"
        outcome_text = "Component-conditioned prediction exists but structure-beyond-mean/variance insufficient."
    elif c["C1_future_predictive_component_association"] and c["C2_persistent_regime_predictive_contribution"] and c["C5_structure_beyond_mean_variance"]:
        outcome = "A_partial"
        outcome_text = "C1–C5-class sequential structure present; see remaining NULLs."
    else:
        outcome = "EARLY"
        outcome_text = "Early ladder failure."

    snap = {
        "UPDATE": "4.35",
        "OUTCOME": outcome,
        "OUTCOME_TEXT": outcome_text,
        "FIRST_UNSUPPORTED_ARROW": firsts,
        "per_seed": {str(r["seed"]): {k: r[k] for k in keys} | {"first": r["first_unsupported_arrow"]} for r in per},
        "examples": {
            "persistent": per[0]["persistent"],
            "broad_iid": per[0]["broad_iid"],
            "memoryless_bimodal": per[0]["memoryless_bimodal"],
            "drift": per[0]["drift"],
            "hist_diff": per[0]["hist_diff"],
        },
        "params_434_unchanged": {"MAX_COMPONENTS": mm.MAX_COMPONENTS, "ASSIGN_RADIUS_FLOOR": mm.ASSIGN_RADIUS_FLOOR},
        "note_434_C4": "historical NULL preserved",
        "bottleneck": firsts[0] if firsts else None,
    }
    dump("OBSERVER_PREDICTIVE_STRUCTURE_SNAPSHOT.json", snap)
    dump("summary.json", {"outcome": outcome, "outcome_text": outcome_text, "claims": matrix, "first": firsts, "leak": leaks})

    lines = [
        "# Update 4.35 FINAL REPORT - Predictive Structure Selection",
        "",
        "## Architecture",
        json.dumps(pss.architecture_inspection(), indent=2),
        "",
        "## 4.34 parameters",
        "Unchanged. Geometric C4 remains historical NULL.",
        "",
        "## Claims",
    ]
    for k in keys:
        lines.append(f"- {k}: **{matrix[k]['status']}** seeds={matrix[k]['seeds']}")
    lines += ["", "## Per seed"]
    for r in per:
        bits = " ".join(f"{k.split('_')[0]}={r[k]}" for k in keys)
        lines.append(f"- seed {r['seed']}: {bits} first={r['first_unsupported_arrow']}")
    lines += [
        "",
        "## First unsupported arrow",
        str(firsts),
        "",
        f"## Outcome {outcome}",
        outcome_text,
        "",
        "## Key deltas (seed 17)",
        f"- persistent delta={per[0]['persistent']['delta_collapsed_minus_full']}",
        f"- broad_iid delta={per[0]['broad_iid']['delta_collapsed_minus_full']}",
        f"- memoryless delta={per[0]['memoryless_bimodal']['delta_collapsed_minus_full']} n_comp={per[0]['memoryless_bimodal']['n_components']}",
        f"- drift delta={per[0]['drift']['delta_collapsed_minus_full']} n_comp={per[0]['drift']['n_components']}",
        f"- hist context delta={per[0]['hist_diff']['delta_collapsed_minus_context']}",
        "",
        "## Semantic leak",
        f"leak = {leaks}",
        "",
        "## Strongest allowed claim",
        "Bounded component identity can acquire online associations with subsequent physical",
        "consequences that improve prequential prediction under persistent regimes, while",
        "providing little contribution under broad iid and memoryless bimodal mixture.",
        "Continuous drift may still be discretized into predictively useful components",
        "(see C6). action_logits / prospective branching untouched.",
        "",
        "## NOT claimed",
        "latent-state inference / beliefs / causal understanding / planning / curiosity",
        "",
        "## Recommended next",
        "If C6 addressed with a generic continuous-vs-discrete criterion, then multimodal",
        "prospective propagation × continuation-specific action (revisit 4.33). Do not",
        "implement that here.",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "outcome": outcome,
        "matrix": {k: matrix[k]["status"] for k in keys},
        "first": firsts[0] if firsts else None,
        "leak": leaks,
    }, indent=2))


if __name__ == "__main__":
    main()
