#!/usr/bin/env python3
"""Update 4.34 - Bounded multimodal consequence learning experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import multimodal_consequence_learning as mm

OUT = ROOT / "results" / "update434_multimodal_consequence_learning"
SEEDS = [17, 23, 41, 59, 83]


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def strip_store(d):
    if not isinstance(d, dict):
        return d
    return {k: v for k, v in d.items() if k != "store"}


def run_seed(seed: int) -> dict:
    out: dict = {"seed": seed, "architecture": mm.architecture_inspection()}

    uni = mm.run_unimodal(seed=seed, n=400)
    bi = mm.run_bimodal(seed=seed, n=400)
    tri = mm.run_trimodal(seed=seed, n=600)
    broad = mm.run_broad(seed=seed, n=400, noise=0.28)
    appear = mm.run_appearance(seed=seed)
    disappear = mm.run_disappearance(seed=seed)
    drift = mm.run_drift(seed=seed)
    cap = mm.run_capacity_pressure(seed=seed)
    outlier = mm.run_outlier(seed=seed)
    multi = mm.run_multidim(seed=seed)
    asy = mm.run_bimodal(seed=seed, n=600, p_right=0.2)
    rare = mm.run_bimodal(seed=seed, n=2000, p_right=0.05)
    legacy_only = mm.run_bimodal(seed=seed, n=400, ablate_components=True)
    cap1 = mm.run_bimodal(seed=seed, n=400, force_max_components=1)
    uni_cap1 = mm.run_unimodal(seed=seed, n=200)
    # force cap1 on unimodal via store flag mid-run
    store_u1 = mm.empty_mm_store(force_max_components=1)
    import random
    rng = random.Random(seed)
    mm.acquire_stream(store_u1, antecedent=mm.base_S(), action="A0", n=200,
                      sample_fn=lambda: mm.regime(0.55, noise=0.02, rng=rng))
    uni_cap1_pred = mm.predict_components(store_u1, mm.base_S(), "A0")

    # purge test on bimodal copy
    bi_purge = mm.run_bimodal(seed=seed + 11, n=400)
    before = mm.predict_components(bi_purge["store"], mm.base_S(), "A0")
    purge_info = mm.purge_raw_history(bi_purge["store"])
    after = mm.predict_components(bi_purge["store"], mm.base_S(), "A0")

    scaling = mm.run_scaling(seed=seed, ns=(200, 1000, 5000))
    passive = mm.passive_prospection_diagnostic(bi["store"])

    # Claims
    c1 = uni["n_supported"] == 1 and abs(uni["centers_field1"][0] - uni["true_mu"]) < 0.08
    c2 = (
        bi["n_supported"] >= 2
        and bi["fictitious_mean"]
        and all(d is not None and d < 0.12 for d in bi["component_nearest_regime_distances"])
    )
    c3 = tri["n_supported"] >= 3
    # C4: structure beyond mean/variance — bimodal retains 2 AND broad does NOT fragment to >=2
    # Pre-registered: broad_unimodal n_supported must be 1 for ASSERTED.
    c4 = c2 and broad["n_supported"] == 1
    c5 = appear["n_after_phase1"] == 1 and appear["n_final"] >= 2 and appear["appear_tick"] is not None
    c6 = bool(disappear["adapted"])
    # C7: at n=5000, component count <= MAX_COMPONENTS and bytes not linear in n vs n=200
    scale_ok = True
    if len(scaling) >= 2:
        b0, b1 = scaling[0], scaling[-1]
        # bytes should not grow ~linear with n (ratio bytes << ratio n)
        n_ratio = b1["n"] / max(1, b0["n"])
        byte_ratio = b1["bimodal_bytes"] / max(1, b0["bimodal_bytes"])
        scale_ok = b1["bimodal_n_comp"] <= mm.MAX_COMPONENTS and byte_ratio < 0.5 * n_ratio
    c7 = scale_ok and cap["n_supported"] <= mm.MAX_COMPONENTS and cap["n_raw"] <= mm.MAX_COMPONENTS
    c8 = before["n_supported"] >= 2 and after["n_supported"] >= 2 and after["n_supported"] == before["n_supported"]
    # C9 asymmetric weights: majority weight > 0.65 for ~80% side when p_right=0.2 -> left majority
    w = asy.get("weights") or []
    c9 = asy["n_supported"] >= 2 and (max(w) if w else 0) >= 0.65

    first = None
    for ok, name in [
        (c1, "repeated_to_unimodal_compression"),
        (c2, "unimodal_to_bimodal_retention"),
        (c3, "bimodal_to_multimodal_generality"),
        (c4, "multimodal_to_structure_beyond_mean_variance"),
        (c5, "structure_to_online_mode_formation"),
        (c6, "formation_to_online_revision"),
        (c7, "revision_to_boundedness"),
        (c8, "boundedness_to_raw_history_independence"),
        (c9, "raw_independence_to_empirical_weight_retention"),
    ]:
        if not ok:
            first = name
            break

    leak = []
    for blob in (uni, bi, tri, broad, appear, disappear, passive, mm.architecture_inspection()):
        leak.extend(mm.audit_forbidden(strip_store(blob)))
    leak = sorted(set(leak))

    out.update({
        "C1_unimodal_compression": bool(c1),
        "C2_bimodal_consequence_retention": bool(c2),
        "C3_multimodal_generality": bool(c3),
        "C4_structure_beyond_mean_variance": bool(c4),
        "C5_online_mode_formation": bool(c5),
        "C6_online_revision_disappearance": bool(c6),
        "C7_boundedness": bool(c7),
        "C8_raw_history_independence": bool(c8),
        "C9_empirical_weight_retention": bool(c9),
        "unimodal": strip_store(uni),
        "bimodal": strip_store(bi),
        "trimodal": strip_store(tri),
        "broad_unimodal": strip_store(broad),
        "appearance": strip_store(appear),
        "disappearance": strip_store(disappear),
        "drift": strip_store(drift),
        "capacity_pressure": strip_store(cap),
        "outlier": strip_store(outlier),
        "multidim": strip_store(multi),
        "asymmetric": strip_store(asy),
        "rare": strip_store(rare),
        "legacy_ablate_components": strip_store(legacy_only),
        "capacity1_bimodal_n_supported": cap1["n_supported"],
        "capacity1_unimodal_n_supported": uni_cap1_pred["n_supported"],
        "purge": {"before": before["n_supported"], "after": after["n_supported"], "info": purge_info},
        "scaling": scaling,
        "passive_prospection": passive,
        "first_unsupported_arrow": first,
        "leak_tokens": leak,
        "c4_note": (
            "C4 requires broad_unimodal n_supported==1; "
            f"observed broad n_supported={broad['n_supported']} (fragmentation under matched variance)"
        ),
    })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", default=",".join(str(s) for s in SEEDS))
    ap.add_argument("--ticks", type=int, default=40)
    args = ap.parse_args()
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    per = [run_seed(s) for s in seeds]
    dump("per_seed_results.json", per)

    keys = [
        "C1_unimodal_compression",
        "C2_bimodal_consequence_retention",
        "C3_multimodal_generality",
        "C4_structure_beyond_mean_variance",
        "C5_online_mode_formation",
        "C6_online_revision_disappearance",
        "C7_boundedness",
        "C8_raw_history_independence",
        "C9_empirical_weight_retention",
    ]

    def agg(k):
        hits = [str(r["seed"]) for r in per if r.get(k)]
        return {
            "status": "ASSERTED" if len(hits) == len(per) else "NOT ASSERTED",
            "seeds": hits, "n": len(hits), "n_total": len(per),
        }

    matrix = {k: agg(k) for k in keys}
    dump("claim_matrix.json", matrix)
    dump("architecture_inspection.json", mm.architecture_inspection())
    firsts = [r["first_unsupported_arrow"] for r in per]
    leaks = sorted({t for r in per for t in (r.get("leak_tokens") or [])})
    dump("leak_audit.json", {"leak": leaks})

    # Outcome narrative
    c = {k: matrix[k]["status"] == "ASSERTED" for k in keys}
    if c["C2_bimodal_consequence_retention"] and not c["C4_structure_beyond_mean_variance"]:
        outcome = "BIMODAL_OK_BUT_NOISE_FRAGMENTS"
        outcome_text = (
            "Bimodal retention works, but matched broad unimodal noise also fragments "
            "into multiple persistent components — structure-beyond-mean/variance NOT established."
        )
    elif c["C2_bimodal_consequence_retention"] and c["C4_structure_beyond_mean_variance"]:
        outcome = "STRUCTURE_OK"
        outcome_text = "Bounded multimodal retention distinguishes separated structure from broad noise."
    else:
        outcome = "EARLY_NULL"
        outcome_text = "Early ladder failure before structure discrimination."

    snap = {
        "UPDATE": "4.34",
        "OUTCOME": outcome,
        "OUTCOME_TEXT": outcome_text,
        "FIRST_UNSUPPORTED_ARROW": firsts,
        "per_seed": {str(r["seed"]): {k: r[k] for k in keys} | {"first": r["first_unsupported_arrow"]} for r in per},
        "example_bimodal": per[0]["bimodal"] if per else {},
        "example_broad": per[0]["broad_unimodal"] if per else {},
        "passive_prospection": per[0]["passive_prospection"] if per else {},
        "params": mm.architecture_inspection()["params"],
        "layers": {
            "LEGACY_MEAN": "single mean_cons (fictitious mid under bimodal)",
            "COMPONENTS": "bounded online centers + support + spread",
            "PROSPECTION": "NOT wired — predict_one_step still mean",
        },
        "bottleneck": firsts[0] if firsts else None,
    }
    dump("OBSERVER_MULTIMODAL_CONSEQUENCE_SNAPSHOT.json", snap)
    dump("summary.json", {
        "outcome": outcome, "outcome_text": outcome_text, "claims": matrix,
        "first_unsupported_arrow": firsts, "leak": leaks,
    })
    dump("scaling.json", per[0]["scaling"] if per else [])
    dump("passive_prospection.json", per[0]["passive_prospection"] if per else {})

    lines = [
        "# Update 4.34 FINAL REPORT - Bounded Multimodal Consequence Learning",
        "",
        "## Architecture inspection",
        json.dumps(mm.architecture_inspection(), indent=2),
        "",
        "## Claims",
    ]
    for k in keys:
        m = matrix[k]
        lines.append(f"- {k}: **{m['status']}** seeds={m['seeds']}")
    lines += ["", "## Per seed"]
    for r in per:
        lines.append(
            f"- seed {r['seed']}: " + " ".join(f"{k[3:5]}={r[k]}" for k in keys)
            + f" first={r['first_unsupported_arrow']}"
        )
    lines += [
        "",
        "## First unsupported arrow",
        str(firsts),
        "",
        f"## Outcome: {outcome}",
        outcome_text,
        "",
        "## Fictitious-mean (bimodal seed 17)",
        f"- legacy field_1 ≈ {per[0]['bimodal']['legacy_field1']}",
        f"- component centers ≈ {per[0]['bimodal']['centers_field1']}",
        f"- legacy nearest-regime distance ≈ {per[0]['bimodal']['legacy_nearest_regime_distance']}",
        "",
        "## Broad unimodal control",
        f"- n_supported={per[0]['broad_unimodal']['n_supported']} centers={per[0]['broad_unimodal']['centers_field1']}",
        "",
        "## Passive prospection diagnostic",
        json.dumps(per[0]['passive_prospection'], indent=2),
        "",
        "## Semantic leak",
        f"leak = {leaks}",
        "",
        "## Strongest allowed claim",
        "For the same (antecedent, action), a bounded online component store can retain",
        "multiple recurring consequence centers instead of only their mean, under separated",
        "bimodal/trimodal regimes. Under the pre-registered parameters it does NOT yet",
        "reliably distinguish that structure from matched broad unimodal noise (C4 NULL).",
        "Multimodal structure is not propagated into prospective composition or action_logits.",
        "",
        "## NOT claimed",
        "imagination / awareness of possibilities / planning / uncertainty awareness / curiosity",
        "",
        "## Relation to 4.33",
        "Historical 4.33 C2–C7 NULL unchanged. 4.34 is representational substrate only.",
        "",
        "## Recommended next",
        "If C4 can be addressed with a generic (non-retuned-to-fixture) criterion that resists",
        "noise fragmentation, then a separate update: multimodal prospective propagation ×",
        "continuation-specific action — without info-gain or planners.",
        "If keeping C4 NULL: first improve structure-vs-noise discrimination before revisiting 4.33.",
        "",
        "## Regression note",
        "Historical FINAL_REPORTs untouched. action_logits / 4.29 NULL not modified.",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "outcome": outcome,
        "matrix": {k: matrix[k]["status"] for k in keys},
        "first": firsts[0] if firsts else None,
        "leak": leaks,
        "broad_n": per[0]["broad_unimodal"]["n_supported"],
        "bi_n": per[0]["bimodal"]["n_supported"],
    }, indent=2))


if __name__ == "__main__":
    main()
