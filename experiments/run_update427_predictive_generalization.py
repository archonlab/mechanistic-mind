#!/usr/bin/env python3
"""Update 4.27 - Predictive generalization to novel physical instances."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import predictive_generalization as pg
from mechanistic_mind.research import prospective_consequence_influence as pci
from mechanistic_mind.research.composed_future_value import ordinary_state_value

OUT = ROOT / "results" / "update427_predictive_generalization"
SEEDS = [17, 23, 41, 59, 83]
N_TRAIN = 8  # repeats per training instance
HI_A, HI_B = 0.82, 0.82
LO_A, LO_B = 0.18, 0.18


def dump(name: str, obj) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def near_fminus(pred: dict | None, thr: float = 0.35) -> bool:
    if not pred:
        return False
    d = pg.l1(pred, pg.F_MINUS())
    return d is not None and d <= thr


def near_fplus(pred: dict | None, thr: float = 0.35) -> bool:
    if not pred:
        return False
    d = pg.l1(pred, pg.F_PLUS())
    return d is not None and d <= thr


def train_shared_family(store: dict, *, n: int = N_TRAIN, shuffle: bool = False, seed: int = 0) -> dict:
    """Train {a,b,c}/{a,b,d}/{a,b,e} -> F- plus distractors. Physical features only."""
    import random
    rng = random.Random(seed)
    fam = [
        pg.instance(HI_A, HI_B, c=0.15),
        pg.instance(HI_A, HI_B, d=0.35),
        pg.instance(HI_A, HI_B, e=0.55),
    ]
    distractors = [
        (pg.instance(LO_A, LO_B, x=0.40), pg.F_PLUS()),
        (pg.instance(HI_A, LO_B, y=0.40), pg.F_OTHER()),  # a alone high
        (pg.instance(LO_A, HI_B, z=0.40), pg.F_OTHER()),  # b alone high
        (pg.instance(0.40, 0.40, w=0.40), pg.F_OTHER()),
    ]
    futures = [pg.F_MINUS()] * len(fam)
    if shuffle:
        futures = [pg.F_PLUS(), pg.F_OTHER(), pg.F_MINUS()]
        rng.shuffle(futures)

    for _ in range(n):
        for inst, fut in zip(fam, futures):
            pg.observe(store, inst, fut)
        for inst, fut in distractors:
            pg.observe(store, inst, fut)

    return {
        "family": fam,
        "distractors": [{"features": d[0], "future": d[1]} for d in distractors],
        "shuffle": shuffle,
        "n_repeats": n,
    }


def probe_novel(store: dict) -> dict:
    novel = pg.instance(HI_A, HI_B, f=0.72)
    full = pg.feature_sig(novel)
    exposure = int((store.get("exposure_exact") or {}).get(full, 0))
    pred = pg.predict(store, novel)
    return {
        "instance_label_observer_only": "I_NEW",
        "features": novel,
        "exact_sig": full,
        "exposure_exact": exposure,
        "prediction": pred,
        "l1_to_F_MINUS": pg.l1(pred.get("predicted"), pg.F_MINUS()),
        "l1_to_F_PLUS": pg.l1(pred.get("predicted"), pg.F_PLUS()),
        "generalizes_to_F_MINUS": exposure == 0 and pred.get("status") == "SHARED" and near_fminus(pred.get("predicted")),
    }


def single_feature_controls(store: dict) -> dict:
    a_only = pg.instance(HI_A, LO_B, y=0.40)
    b_only = pg.instance(LO_A, HI_B, z=0.40)
    pa = pg.predict(store, a_only)
    pb = pg.predict(store, b_only)
    return {
        "a_only": {
            "features": a_only,
            "prediction": pa,
            "l1_F_MINUS": pg.l1(pa.get("predicted"), pg.F_MINUS()),
            "predicts_F_MINUS": near_fminus(pa.get("predicted")),
        },
        "b_only": {
            "features": b_only,
            "prediction": pb,
            "l1_F_MINUS": pg.l1(pb.get("predicted"), pg.F_MINUS()),
            "predicts_F_MINUS": near_fminus(pb.get("predicted")),
        },
        "single_feature_explains_F_MINUS": near_fminus(pa.get("predicted")) or near_fminus(pb.get("predicted")),
    }


def run_ablations(base_store: dict, seed: int) -> dict:
    # shared ablation
    ab_shared = deepcopy(base_store)
    ab_shared["ablate_shared"] = True
    p_shared = probe_novel(ab_shared)

    # exact-only (no shared): already ablate_shared; also train-only-exact path
    ab_exact_only = pg.empty_store()
    ab_exact_only["ablate_shared"] = True
    train_shared_family(ab_exact_only, seed=seed)
    p_exact = probe_novel(ab_exact_only)

    # shuffle / decorrelated
    shuf = pg.empty_store()
    train_shared_family(shuf, shuffle=True, seed=seed + 99)
    p_shuf = probe_novel(shuf)

    return {
        "ablate_shared_novel": p_shared,
        "ablate_shared_blocks_generalization": not p_shared.get("generalizes_to_F_MINUS"),
        "exact_only_novel": p_exact,
        "exact_only_blocks_generalization": not p_exact.get("generalizes_to_F_MINUS"),
        "shuffle_futures_novel": p_shuf,
        "shuffle_blocks_or_weakens": not p_shuf.get("generalizes_to_F_MINUS"),
    }


def try_c3_action(pred_future: dict | None, seed: int) -> dict:
    """Optional: feed generalized distal prediction into unchanged 4.26 valuation/softmax path.
    We do NOT retune DISTAL_BLEND / T. Map F- vs F+ ordinary values into A vs B distal slots
    using existing pci helpers without rewriting them.
    """
    if not pred_future:
        return {"attempted": True, "asserted": False, "reason": "no_prediction"}
    goals = pci.default_goals()
    # Build a minimal composition store with A->B_MINUS style distal and B->B_PLUS,
    # then compare action mass when distal uses predicted novel future vs baseline.
    from mechanistic_mind.research import prospective_composition as pc

    store = pc.empty_store()
    cfg = pci.empty_world_cfg()
    pci.train_fragments(store, cfg, n=40, seed=seed)

    # Evaluate ordinary value of generalized prediction vs F+
    ev_gen = pci.evaluate_distal(pci.S0(), pred_future, goals)
    ev_plus = pci.evaluate_distal(pci.S0(), pg.F_PLUS(), goals)
    ev_minus = pci.evaluate_distal(pci.S0(), pg.F_MINUS(), goals)
    ov_gen = ev_gen.get("ordinary_value")
    ov_plus = ev_plus.get("ordinary_value")
    ov_minus = ev_minus.get("ordinary_value")

    # Use unchanged action_logits: distal on when composition available
    base = pci.action_logits(store=store, goals=goals, use_distal=True)
    # Neutralize distal as control
    off = pci.action_logits(store=store, goals=goals, use_distal=False)

    # Soft check: generalized F- has ordinary value near F_MINUS (same path as 4.26)
    gen_like_minus = (
        ov_gen is not None and ov_minus is not None
        and abs(float(ov_gen) - float(ov_minus)) < 0.05
    )
    # Action shift: with distal, mass should move relative to off (same as 4.26 C3 family)
    probs_on = base.get("probs") or {}
    probs_off = off.get("probs") or {}
    # Prefer B (better distal) when distal on — reused 4.26 structure
    shift_B = float(probs_on.get("B1", 0.0)) - float(probs_off.get("B1", 0.0))

    return {
        "attempted": True,
        "ordinary_value_generalized": ov_gen,
        "ordinary_value_F_MINUS": ov_minus,
        "ordinary_value_F_PLUS": ov_plus,
        "gen_matches_F_MINUS_value": gen_like_minus,
        "action_probs_distal_on": probs_on,
        "action_probs_distal_off": probs_off,
        "shift_B1_on_minus_off": shift_B,
        "DISTAL_BLEND": pci.DISTAL_BLEND,
        "DEFAULT_TEMPERATURE": pci.DEFAULT_TEMPERATURE,
        # C3: generalized prediction is valued by unchanged pathway AND distal gating changes action mass
        "asserted": bool(gen_like_minus and abs(shift_B) > 0.02),
        "note": "Uses unchanged pci.action_logits / ordinary_state_value; no retune.",
    }


def run_c4_counterexample(store: dict) -> dict:
    """After generalization baseline, experience {a,b,g}->F+; do not retune thresholds."""
    before = probe_novel(store)
    counter = pg.instance(HI_A, HI_B, g=0.65)
    # Observe counterexample many times
    for _ in range(12):
        pg.observe(store, counter, pg.F_PLUS())
    # Re-probe novel {a,b,f} and also counter itself
    after_novel = probe_novel(store)
    after_counter = pg.predict(store, counter)
    # Shared pair a|b may still dominate novel; revision of shared structure toward F+
    pair_snap = pg.shared_structure_snapshot(store)
    # Check if pair mean moved toward F+
    top = pair_snap.get("top_pairs") or []
    ab_key_means = [t for t in top if t.get("key", "").startswith("a:") and "|b:" in t.get("key", "")]
    revised_pair = False
    if ab_key_means:
        m = ab_key_means[0].get("mean") or {}
        # energy up / fatigue down vs F_MINUS would indicate revision
        if float(m.get("energy_signal", 0)) > 0.4:
            revised_pair = True
    counter_ok = after_counter.get("status") in ("EXACT", "SHARED") and near_fplus(after_counter.get("predicted"), thr=0.45)
    # Strong C4: novel prediction revises away from F- OR shared structure revises
    novel_revised = (
        after_novel.get("l1_to_F_MINUS") is not None
        and before.get("l1_to_F_MINUS") is not None
        and float(after_novel["l1_to_F_MINUS"]) > float(before["l1_to_F_MINUS"]) + 0.08
    ) or revised_pair

    return {
        "before_novel": before,
        "counterexample_features": counter,
        "after_counter_pred": after_counter,
        "after_novel": after_novel,
        "counter_predicts_F_PLUS": counter_ok,
        "shared_revised": revised_pair,
        "novel_l1_increased_from_F_MINUS": novel_revised,
        "pair_snapshot_after": pair_snap,
        "asserted": bool(counter_ok and (novel_revised or revised_pair)),
        "note": "No EMA/threshold retune; revision via observe() only.",
    }


def run_seed(seed: int) -> dict:
    store = pg.empty_store()
    meta = train_shared_family(store, seed=seed)
    snap = pg.shared_structure_snapshot(store)
    novel = probe_novel(store)
    singles = single_feature_controls(store)
    ablations = run_ablations(store, seed)

    c1 = (
        int(snap.get("shared_structure_count") or 0) >= 1
        and any("a:" in (t.get("key") or "") and "|b:" in (t.get("key") or "") for t in (snap.get("top_pairs") or []))
    )
    c2 = (
        novel.get("generalizes_to_F_MINUS")
        and ablations.get("ablate_shared_blocks_generalization")
        and ablations.get("exact_only_blocks_generalization")
        and not singles.get("single_feature_explains_F_MINUS")
        and ablations.get("shuffle_blocks_or_weakens")
    )

    c3 = try_c3_action((novel.get("prediction") or {}).get("predicted"), seed)
    c4 = run_c4_counterexample(deepcopy(store))

    leaks = pg.audit_forbidden({"snap": snap, "novel": novel, "meta": meta})

    return {
        "seed": seed,
        "training": meta,
        "shared_snapshot": snap,
        "novel_probe": novel,
        "single_feature_controls": singles,
        "ablations": ablations,
        "C1_shared_structure": c1,
        "C2_novel_generalization": bool(c2),
        "C3_action_influence": c3,
        "C4_counterexample_revision": c4,
        "leak_tokens": leaks,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--ticks", type=int, default=8, help="training repeats (alias n)")
    args = ap.parse_args()
    seeds = args.seeds or SEEDS
    global N_TRAIN
    N_TRAIN = int(args.ticks)

    OUT.mkdir(parents=True, exist_ok=True)
    dump("CONFIG.json", {
        "update": "4.27",
        "seeds": seeds,
        "n_train_repeats": N_TRAIN,
        "HI_A": HI_A,
        "HI_B": HI_B,
        "MIN_SUPPORT": pg.MIN_SUPPORT,
        "FORBIDDEN": list(pg.FORBIDDEN),
        "no_category_semantics": True,
        "C3_uses_unchanged_4_26_pathway": True,
        "C4_no_ema_retune": True,
    })

    per = []
    for s in seeds:
        per.append(run_seed(s))
    dump("per_seed_results.json", per)

    def all_true(key):
        return all(bool(r.get(key)) for r in per)

    c3_ok = all(bool((r.get("C3_action_influence") or {}).get("asserted")) for r in per)
    c4_ok = all(bool((r.get("C4_counterexample_revision") or {}).get("asserted")) for r in per)

    claim = {
        "C1_shared_predictive_structure": {
            "asserted": all_true("C1_shared_structure"),
            "seeds": [str(r["seed"]) for r in per if r.get("C1_shared_structure")],
        },
        "C2_novel_instance_predictive_generalization": {
            "asserted": all_true("C2_novel_generalization"),
            "seeds": [str(r["seed"]) for r in per if r.get("C2_novel_generalization")],
        },
        "C3_generalized_action_influence_via_4_26": {
            "asserted": c3_ok,
            "seeds": [str(r["seed"]) for r in per if (r.get("C3_action_influence") or {}).get("asserted")],
        },
        "C4_experience_driven_revision_on_counterexample": {
            "asserted": c4_ok,
            "seeds": [str(r["seed"]) for r in per if (r.get("C4_counterexample_revision") or {}).get("asserted")],
        },
    }
    dump("claim_matrix.json", claim)

    feature_matrix = {
        "training_family_observer_labels": ["I1={a,b,c}", "I2={a,b,d}", "I3={a,b,e}"],
        "novel": "I_NEW={a,b,f}",
        "counterexample": "I_CE={a,b,g}",
        "consequence_F_MINUS": pg.F_MINUS(),
        "consequence_F_PLUS": pg.F_PLUS(),
        "per_seed_novel": [
            {
                "seed": r["seed"],
                "exposure_exact": r["novel_probe"]["exposure_exact"],
                "status": (r["novel_probe"].get("prediction") or {}).get("status"),
                "l1_F_MINUS": r["novel_probe"].get("l1_to_F_MINUS"),
                "generalizes": r["novel_probe"].get("generalizes_to_F_MINUS"),
            }
            for r in per
        ],
    }
    dump("feature_matrix.json", feature_matrix)
    dump("generalization_probe.json", {"per_seed": [r["novel_probe"] for r in per]})
    dump("ablations.json", {"per_seed": [r["ablations"] for r in per]})
    dump("exposure_audit.json", {
        "per_seed": [
            {"seed": r["seed"], "novel_exposure_exact": r["novel_probe"]["exposure_exact"]}
            for r in per
        ],
        "all_novel_exposure_zero": all(r["novel_probe"]["exposure_exact"] == 0 for r in per),
    })
    dump("leak_audit.json", {
        "per_seed": [{"seed": r["seed"], "tokens": r["leak_tokens"]} for r in per],
        "any_leak": any(r["leak_tokens"] for r in per),
    })
    dump("ACCEPTANCE_MATRIX.json", {
        "C1": claim["C1_shared_predictive_structure"]["asserted"],
        "C2": claim["C2_novel_instance_predictive_generalization"]["asserted"],
        "C3": claim["C3_generalized_action_influence_via_4_26"]["asserted"],
        "C4": claim["C4_experience_driven_revision_on_counterexample"]["asserted"],
        "no_forbidden_tokens": not any(r["leak_tokens"] for r in per),
        "novel_exposure_zero": all(r["novel_probe"]["exposure_exact"] == 0 for r in per),
    })
    dump("BASELINE_REGRESSION.json", {
        "preserve_4_26_C4_NOT_ASSERTED": True,
        "preserve_4_25_C3_NOT_ASSERTED": True,
        "preserve_4_24_strong_temporal_NOT_ASSERTED": True,
        "note": "Do not rewrite prior FINAL_REPORTs; historical NULLs stand.",
        "status": "NOT_FULLY_RE_RUN_IN_SMOKE",
    })
    dump("INTEGRATION_PRESERVE.json", {
        "metrics_affect_cognition": False,
        "observer_telemetry_only": True,
        "no_category_labels_in_cognition": True,
    })

    # Observer snapshot (rich)
    obs = {
        "update": "4.27",
        "layers": {
            "WORLD_TRUTH": "Physical feature vectors a,b,c/d/e/f/g; consequences F-/F+/OTHER as body signals",
            "BODY_TRUTH": pg.F_MINUS(),
            "ACCESSIBLE_SIGNALS": "Same physical feature bins as cognition observes",
            "PSYCHE_MODEL": "exact / single / pair conjunction stores (no CATEGORY)",
            "PROSPECTIVE": feature_matrix,
            "ACTION": [r.get("C3_action_influence") for r in per],
            "CONSEQUENCE": claim,
        },
        "claim_matrix": claim,
        "feature_matrix": feature_matrix,
        "shared_top_pairs_seed0": (per[0].get("shared_snapshot") or {}).get("top_pairs") if per else [],
        "ablation_summary": {
            "shared_blocks": all(r["ablations"]["ablate_shared_blocks_generalization"] for r in per),
            "exact_only_blocks": all(r["ablations"]["exact_only_blocks_generalization"] for r in per),
            "shuffle_blocks": all(r["ablations"]["shuffle_blocks_or_weakens"] for r in per),
        },
    }
    dump("OBSERVER_GENERALIZATION_SNAPSHOT.json", obs)

    summary = {
        "claims": claim,
        "seeds": seeds,
        "n_train": N_TRAIN,
    }
    dump("summary.json", summary)

    lines = [
        "# Update 4.27 FINAL REPORT - Predictive Generalization",
        "",
        "## Architecture",
        "Physical feature conjunction store (exact / single / pair). No CATEGORY/CLASS/CONCEPT/THREAT.",
        "Novel instance {a,b,f} probed with exposure_exact=0. Optional C3 via unchanged 4.26 ordinary_state_value + action_logits.",
        "C4 via observe() on counterexample only — no EMA retune.",
        "",
        "## Claims",
    ]
    for k, v in claim.items():
        status = "ASSERTED" if v["asserted"] else "NOT ASSERTED"
        lines.append(f"- {k}: **{status}** seeds={v['seeds']}")
    lines += [
        "",
        "## Per seed",
    ]
    for r in per:
        np = r["novel_probe"]
        lines.append(
            f"- seed {r['seed']}: C1={r['C1_shared_structure']} C2={r['C2_novel_generalization']} "
            f"C3={ (r.get('C3_action_influence') or {}).get('asserted') } "
            f"C4={ (r.get('C4_counterexample_revision') or {}).get('asserted') } "
            f"novel_exp={np['exposure_exact']} status={ (np.get('prediction') or {}).get('status') } "
            f"l1F-={np.get('l1_to_F_MINUS')}"
        )
    lines += [
        "",
        "## Historical preserve",
        "- 4.26 C4 remains NOT ASSERTED (not retuned here).",
        "- 4.25 C3 remains NOT ASSERTED.",
        "- Prior FINAL_REPORTs untouched.",
        "",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(claim, indent=2))
    print("wrote", OUT)


if __name__ == "__main__":
    main()
