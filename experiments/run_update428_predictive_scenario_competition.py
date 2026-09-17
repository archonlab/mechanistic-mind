#!/usr/bin/env python3
"""Update 4.28 - Competing predictive continuations experiments."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import predictive_scenario_competition as psc
from mechanistic_mind.research import prospective_consequence_influence as pci
from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import predictive_generalization as pg

OUT = ROOT / "results" / "update428_predictive_scenario_competition"
SEEDS = [17, 23, 41, 59, 83]
HISTORY = {"H0": 0, "H10": 10, "H50": 50, "H100": 100}
N_SAMPLES = 300
B_FRAG_INTRO = 40


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def run_seed(seed: int) -> dict:
    goals = pci.default_goals()
    out: dict = {"seed": seed}

    # --- Baseline A history characterization (B not available) ---
    baseline = {}
    for hname, hn in HISTORY.items():
        st = psc.build_history_store(a_n=hn, b_fragment_n=0, seed=seed)
        snap = psc.candidate_snapshot(st, goals)
        act = psc.measure_action(st, goals, seed=seed + hn)
        baseline[hname] = {
            "A_support_exposures": hn,
            "A_full_sequence_exposures": snap["A_full_sequence_exposures"],
            "B_full_sequence_exposures": snap["B_full_sequence_exposures"],
            "A_support_A1": snap["A_support_A1"],
            "candidates": snap["candidates"],
            "P_A": act["P_A"],
            "P_B": act["P_B"],
            "P_WAIT": act["P_WAIT"],
            "action_entropy": act["action_entropy"],
        }
    out["baseline_history"] = baseline

    # --- Introduce B (composed fragments, full end-to-end = 0) ---
    # Use H50 as primary history for competition suite
    primary_h = 50
    store = psc.build_history_store(
        a_n=primary_h,
        b_fragment_n=B_FRAG_INTRO,
        a_distal=pci.B_MINUS(),
        b_distal=pci.B_PLUS(),
        b_end_to_end=False,
        seed=seed,
    )
    snap = psc.candidate_snapshot(store, goals)
    act = psc.measure_action(store, goals, seed=seed + 1)
    out["competing_intro"] = {
        "snapshot": snap,
        "action": {k: act[k] for k in ("P_A", "P_B", "P_WAIT", "action_entropy", "probs", "logits")},
        "B_full_sequence_exposures": snap["B_full_sequence_exposures"],
        "A_composed": snap["candidates"]["A"].get("composition_status"),
        "B_composed": snap["candidates"]["B"].get("composition_status"),
    }
    c1 = (
        snap["candidates"]["A"].get("composition_status") == "COMPOSED"
        and snap["candidates"]["B"].get("composition_status") == "COMPOSED"
        and snap["B_full_sequence_exposures"] == 0
        and snap["candidates"]["A"].get("predicted_distal") is not None
        and snap["candidates"]["B"].get("predicted_distal") is not None
    )
    out["C1_competing_continuations"] = bool(c1)

    # --- Matched-consequence history test ---
    matched = {}
    for hname, hn in HISTORY.items():
        st = psc.build_history_store(
            a_n=hn,
            b_fragment_n=B_FRAG_INTRO,
            a_distal=psc.F_neutral(),
            b_distal=psc.F_neutral(),
            seed=seed,
        )
        snap_m = psc.candidate_snapshot(st, goals)
        act_m = psc.measure_action(st, goals, seed=seed + 11 + hn)
        va = snap_m["candidates"]["A"].get("ordinary_value")
        vb = snap_m["candidates"]["B"].get("ordinary_value")
        matched[hname] = {
            "P_A": act_m["P_A"],
            "P_B": act_m["P_B"],
            "P_WAIT": act_m["P_WAIT"],
            "ordinary_A": va,
            "ordinary_B": vb,
            "values_near": (
                va is not None and vb is not None and abs(float(va) - float(vb)) < 0.05
            ),
            "A_full": snap_m["A_full_sequence_exposures"],
            "B_full": snap_m["B_full_sequence_exposures"],
        }
    # Does P_A systematically increase with history under matched distal?
    pa_series = [matched[h]["P_A"] for h in ("H0", "H10", "H50", "H100")]
    history_effect_matched = (max(pa_series) - min(pa_series)) > 0.05
    out["matched_consequence_history"] = {
        "by_history": matched,
        "P_A_series": pa_series,
        "history_effect_candidate": history_effect_matched,
    }

    # --- Distal advantage sweep × history ---
    levels = psc.distal_levels()
    sweep = {}
    for hname, hn in HISTORY.items():
        rows = []
        for lname, b_dist in levels.items():
            st = psc.build_history_store(
                a_n=hn,
                b_fragment_n=B_FRAG_INTRO,
                a_distal=pci.B_MINUS(),
                b_distal=b_dist,
                seed=seed,
            )
            snap_s = psc.candidate_snapshot(st, goals)
            act_s = psc.measure_action(st, goals, seed=seed + hash(lname) % 1000 + hn)
            va = snap_s["candidates"]["A"].get("ordinary_value")
            vb = snap_s["candidates"]["B"].get("ordinary_value")
            rows.append({
                "level_observer": lname,
                "P_A": act_s["P_A"],
                "P_B": act_s["P_B"],
                "P_WAIT": act_s["P_WAIT"],
                "ordinary_A": va,
                "ordinary_B": vb,
                "distal_difference": (None if va is None or vb is None else float(vb) - float(va)),
            })
        sweep[hname] = {
            "rows": rows,
            "crossover": psc.find_crossover(rows),
        }
    out["distal_advantage_sweep"] = sweep

    # --- Evidence accumulation for B (hold physical distal fixed) ---
    # Start with strong A, weak B fragments; add B support over steps
    accum_points = []
    st_acc = psc.build_history_store(
        a_n=50,
        b_fragment_n=3,  # minimal B start
        a_distal=pci.B_MINUS(),
        b_distal=pci.B_PLUS(),
        seed=seed,
    )
    for step, add_n in enumerate([0, 5, 10, 20, 40, 80]):
        if add_n > 0:
            psc.learn_B_fragments(st_acc, n=add_n, distal=pci.B_PLUS(), tick0=8000 + step * 100, end_to_end=False)
        snap_a = psc.candidate_snapshot(st_acc, goals)
        act_a = psc.measure_action(st_acc, goals, seed=seed + 200 + step)
        accum_points.append({
            "evidence_step": step,
            "B_fragments_added_this_step": add_n,
            "B_support_B1": snap_a["B_support_B1"],
            "A_support_A1": snap_a["A_support_A1"],
            "B_status": snap_a["candidates"]["B"].get("composition_status"),
            "ordinary_A": snap_a["candidates"]["A"].get("ordinary_value"),
            "ordinary_B": snap_a["candidates"]["B"].get("ordinary_value"),
            "P_A": act_a["P_A"],
            "P_B": act_a["P_B"],
            "P_WAIT": act_a["P_WAIT"],
        })
    pb_series = [p["P_B"] for p in accum_points]
    pa_acc = [p["P_A"] for p in accum_points]
    transition_type = psc.classify_transition(pb_series)
    cross = psc.find_crossover(accum_points)
    # Real transition requires change over evidence, not already-B-dominant at step 0.
    delta_B = float(pb_series[-1] - pb_series[0]) if pb_series else 0.0
    already_B_at_start = bool(accum_points) and float(accum_points[0].get("P_B", 0)) >= float(accum_points[0].get("P_A", 0))
    crossover_after_start = bool(cross.get("found")) and int(cross.get("index") or 0) > 0
    transition_observed = (
        transition_type in ("gradual", "abrupt", "oscillation")
        and (abs(delta_B) > 0.05 or crossover_after_start)
        and not (transition_type == "no_transition")
    )
    # Explicit: flat series = no transition even if P_B>=P_A throughout
    if transition_type == "no_transition" or abs(delta_B) < 0.05:
        transition_observed = False
    out["evidence_accumulation"] = {
        "points": accum_points,
        "P_B_series": pb_series,
        "P_A_series": pa_acc,
        "transition_type": transition_type,
        "crossover": cross,
        "delta_P_B": delta_B,
        "already_B_at_start": already_B_at_start,
        "transition_observed": transition_observed,
    }

    # --- Ablations for C2 ---
    st_full = psc.build_history_store(
        a_n=50, b_fragment_n=B_FRAG_INTRO,
        a_distal=psc.F_neutral(), b_distal=psc.F_neutral(), seed=seed,
    )
    act_full = psc.measure_action(st_full, goals, seed=seed + 301)
    st_ab = psc.ablate_A_structure(st_full)
    act_ab = psc.measure_action(st_ab, goals, seed=seed + 302)
    st_ret = psc.reduce_A_retrieval(st_full, keep_frac=0.1)
    act_ret = psc.measure_action(st_ret, goals, seed=seed + 303)
    # composition ablation
    act_comp_off = psc.measure_action(st_full, goals, seed=seed + 304, ablate_composition=True)
    ablation = {
        "matched_neutral_baseline": {"P_A": act_full["P_A"], "P_B": act_full["P_B"]},
        "A_structure_ablation": {"P_A": act_ab["P_A"], "P_B": act_ab["P_B"],
                                "delta_P_A": act_ab["P_A"] - act_full["P_A"]},
        "A_retrieval_reduce": {"P_A": act_ret["P_A"], "P_B": act_ret["P_B"],
                               "delta_P_A": act_ret["P_A"] - act_full["P_A"]},
        "composition_ablation": {"P_A": act_comp_off["P_A"], "P_B": act_comp_off["P_B"]},
        "structure_ablation_shrinks_A": (act_ab["P_A"] < act_full["P_A"] - 0.03),
    }
    out["ablations"] = ablation

    # --- Raw repetition control ---
    st_raw = pc.empty_store()
    psc.learn_A_repetition_no_structure(st_raw, n=50, tick0=1)
    psc.learn_B_fragments(st_raw, n=B_FRAG_INTRO, distal=psc.F_neutral(), tick0=5000)
    # A distal not structured; give A a neutral one-step only. For fair distal on B:
    act_raw = psc.measure_action(st_raw, goals, seed=seed + 400)
    st_struct = psc.build_history_store(
        a_n=50, b_fragment_n=B_FRAG_INTRO,
        a_distal=psc.F_neutral(), b_distal=psc.F_neutral(), seed=seed,
    )
    act_struct = psc.measure_action(st_struct, goals, seed=seed + 401)
    out["raw_repetition_control"] = {
        "raw_no_stable_structure": {"P_A": act_raw["P_A"], "P_B": act_raw["P_B"]},
        "stable_predictive_structure": {"P_A": act_struct["P_A"], "P_B": act_struct["P_B"]},
        "structure_differs_from_raw": abs(act_struct["P_A"] - act_raw["P_A"]) > 0.05,
    }

    # --- History-neutral consequence control (≈4.26 style) ---
    st_hn = psc.build_history_store(
        a_n=40, b_fragment_n=40,
        a_distal=pci.B_MINUS(), b_distal=pci.B_PLUS(), seed=seed,
    )
    act_hn = psc.measure_action(st_hn, goals, seed=seed + 410)
    act_hn_off = psc.measure_action(st_hn, goals, seed=seed + 411, use_distal=False)
    out["history_neutral_consequence"] = {
        "P_B_distal_on": act_hn["P_B"],
        "P_B_distal_off": act_hn_off["P_B"],
        "shift_B": act_hn["P_B"] - act_hn_off["P_B"],
        "reproduces_426_style": (act_hn["P_B"] - act_hn_off["P_B"]) > 0.02,
    }

    # --- B_COMPOSED vs B_EXPERIENCED ---
    st_comp = psc.build_history_store(
        a_n=50, b_fragment_n=40, a_distal=pci.B_MINUS(), b_distal=pci.B_PLUS(),
        b_end_to_end=False, seed=seed,
    )
    st_exp = psc.build_history_store(
        a_n=50, b_fragment_n=40, a_distal=pci.B_MINUS(), b_distal=pci.B_PLUS(),
        b_end_to_end=True, seed=seed,
    )
    act_c = psc.measure_action(st_comp, goals, seed=seed + 420)
    act_e = psc.measure_action(st_exp, goals, seed=seed + 421)
    out["composed_vs_experienced"] = {
        "B_COMPOSED": {"P_B": act_c["P_B"], "full_B": psc.full_exposure(st_comp, "S0_B1_B2_B3")},
        "B_EXPERIENCED": {"P_B": act_e["P_B"], "full_B": psc.full_exposure(st_exp, "S0_B1_B2_B3")},
        "P_B_delta": act_e["P_B"] - act_c["P_B"],
    }

    # --- Same present / different history ---
    st_ha = psc.build_history_store(
        a_n=100, b_fragment_n=20, a_distal=psc.F_neutral(), b_distal=psc.F_neutral(), seed=seed,
    )
    st_hb = psc.build_history_store(
        a_n=10, b_fragment_n=20, a_distal=psc.F_neutral(), b_distal=psc.F_neutral(), seed=seed,
    )
    act_ha = psc.measure_action(st_ha, goals, seed=seed + 430)
    act_hb = psc.measure_action(st_hb, goals, seed=seed + 431)
    out["same_present_different_history"] = {
        "run_A_history_H100": {"P_A": act_ha["P_A"], "P_B": act_ha["P_B"], "P_WAIT": act_ha["P_WAIT"]},
        "run_B_history_H10": {"P_A": act_hb["P_A"], "P_B": act_hb["P_B"], "P_WAIT": act_hb["P_WAIT"]},
        "P_A_diff": act_ha["P_A"] - act_hb["P_A"],
        "differs": abs(act_ha["P_A"] - act_hb["P_A"]) > 0.05,
    }

    # --- Different history / matched current predictions ---
    # Both have composed A/B with same distal; histories differ — predictions should match
    snap_ha = psc.candidate_snapshot(st_ha, goals)
    snap_hb = psc.candidate_snapshot(st_hb, goals)
    pred_match = (
        snap_ha["candidates"]["A"].get("ordinary_value") is not None
        and snap_hb["candidates"]["A"].get("ordinary_value") is not None
        and abs(float(snap_ha["candidates"]["A"]["ordinary_value"]) - float(snap_hb["candidates"]["A"]["ordinary_value"])) < 0.05
        and abs(float(snap_ha["candidates"]["B"]["ordinary_value"] or 0) - float(snap_hb["candidates"]["B"]["ordinary_value"] or 0)) < 0.05
    )
    out["different_history_matched_predictions"] = {
        "predictions_matched": pred_match,
        "behavior_still_differs": bool(pred_match and abs(act_ha["P_A"] - act_hb["P_A"]) > 0.05),
        "ordinary_A_runA": snap_ha["candidates"]["A"].get("ordinary_value"),
        "ordinary_A_runB": snap_hb["candidates"]["A"].get("ordinary_value"),
    }

    # --- Shuffled history control (preserve counts, scramble distal assignment) ---
    st_shuf = pc.empty_store()
    # same n as H50 but A sometimes maps to B_PLUS and B to B_MINUS randomly by tick
    import random as _rnd
    rng = _rnd.Random(seed + 7)
    for i in range(50):
        d_a = pci.B_PLUS() if rng.random() < 0.5 else pci.B_MINUS()
        pc.learn_transition(st_shuf, tick=i + 1, antecedent=pci.S0(), action="A1", consequent=pci.S1())
        pc.learn_transition(st_shuf, tick=i + 1, antecedent=pci.S1(), action="A2", consequent=pci.S2())
        pc.learn_transition(st_shuf, tick=i + 1, antecedent=pci.S2(), action="A3", consequent=d_a)
    for i in range(B_FRAG_INTRO):
        d_b = pci.B_MINUS() if rng.random() < 0.5 else pci.B_PLUS()
        pc.learn_transition(st_shuf, tick=5000 + i, antecedent=pci.S0(), action="B1", consequent=pci.S3())
        pc.learn_transition(st_shuf, tick=5000 + i, antecedent=pci.S3(), action="B2", consequent=pci.S4())
        pc.learn_transition(st_shuf, tick=5000 + i, antecedent=pci.S4(), action="B3", consequent=d_b)
    act_shuf = psc.measure_action(st_shuf, goals, seed=seed + 440)
    act_ordered = psc.measure_action(
        psc.build_history_store(a_n=50, b_fragment_n=B_FRAG_INTRO, a_distal=pci.B_MINUS(), b_distal=pci.B_PLUS(), seed=seed),
        goals, seed=seed + 441,
    )
    out["shuffled_history_control"] = {
        "shuffled": {"P_A": act_shuf["P_A"], "P_B": act_shuf["P_B"]},
        "ordered": {"P_A": act_ordered["P_A"], "P_B": act_ordered["P_B"]},
        "ordered_differs_from_shuffle": abs(act_ordered["P_B"] - act_shuf["P_B"]) > 0.05,
    }

    # --- Reliability control ---
    st_unrel = pc.empty_store()
    for i in range(80):
        # frequent but unreliable A distal
        d = pci.B_PLUS() if (i % 3 == 0) else pci.B_MINUS()
        pc.learn_transition(st_unrel, tick=i + 1, antecedent=pci.S0(), action="A1", consequent=pci.S1())
        pc.learn_transition(st_unrel, tick=i + 1, antecedent=pci.S1(), action="A2", consequent=pci.S2())
        pc.learn_transition(st_unrel, tick=i + 1, antecedent=pci.S2(), action="A3", consequent=d)
    psc.learn_B_fragments(st_unrel, n=15, distal=pci.B_PLUS(), tick0=9000, end_to_end=False)
    st_rel = psc.build_history_store(a_n=80, b_fragment_n=15, a_distal=pci.B_MINUS(), b_distal=pci.B_PLUS(), seed=seed)
    act_u = psc.measure_action(st_unrel, goals, seed=seed + 450)
    act_r = psc.measure_action(st_rel, goals, seed=seed + 451)
    out["reliability_control"] = {
        "frequent_unreliable_A": {"P_A": act_u["P_A"], "P_B": act_u["P_B"]},
        "frequent_reliable_A": {"P_A": act_r["P_A"], "P_B": act_r["P_B"]},
    }

    # --- Optional generalized competitor (4.27) — separate ---
    gen = {"attempted": True}
    try:
        gstore = pg.empty_store()
        for _ in range(8):
            pg.observe(gstore, pg.instance(0.82, 0.82, c=0.15), pg.F_MINUS())
            pg.observe(gstore, pg.instance(0.82, 0.82, d=0.35), pg.F_MINUS())
            pg.observe(gstore, pg.instance(0.82, 0.82, e=0.55), pg.F_MINUS())
        novel = pg.instance(0.82, 0.82, f=0.72)
        pred = pg.predict(gstore, novel)
        gen["novel_exposure"] = int((gstore.get("exposure_exact") or {}).get(pg.feature_sig(novel), 0))
        gen["prediction_status"] = pred.get("status")
        gen["l1_F_MINUS"] = pg.l1(pred.get("predicted"), pg.F_MINUS())
        # competition with A is reported as separate diagnostic: ordinary values only
        if pred.get("predicted"):
            ev = pci.evaluate_distal(pci.S0(), pred["predicted"], goals)
            gen["generalized_ordinary_value"] = ev.get("ordinary_value")
            gen["note"] = "Separate from core 4.28; uses unchanged 4.27 machinery."
    except Exception as exc:
        gen["error"] = str(exc)
    out["generalized_competitor_separate"] = gen

    # --- Hysteresis probe (only meaningful if transition exists) ---
    # Forward: increase B advantage (observer levels)
    forward = []
    level_order = ["much_less", "slightly_less", "equal", "slightly_more", "substantially_more"]
    for i, lname in enumerate(level_order):
        st_f = psc.build_history_store(
            a_n=50, b_fragment_n=B_FRAG_INTRO,
            a_distal=pci.B_MINUS(), b_distal=levels[lname], seed=seed,
        )
        # also accumulate a bit of B support along forward path
        psc.learn_B_fragments(st_f, n=5 * i, distal=levels[lname], tick0=20000 + i * 50)
        act_f = psc.measure_action(st_f, goals, seed=seed + 500 + i)
        forward.append({"step": i, "level_observer": lname, "P_A": act_f["P_A"], "P_B": act_f["P_B"]})
    # Reverse: start from B-favoring history then go back
    reverse = []
    # Build B-established store then sweep levels backward with A support rebuild
    for i, lname in enumerate(reversed(level_order)):
        st_r = psc.build_history_store(
            a_n=10 + 5 * i,  # A support growing on reverse
            b_fragment_n=80,  # B historically established
            a_distal=pci.B_MINUS(), b_distal=levels[lname],
            b_end_to_end=True, seed=seed,
        )
        act_r = psc.measure_action(st_r, goals, seed=seed + 600 + i)
        reverse.append({"step": i, "level_observer": lname, "P_A": act_r["P_A"], "P_B": act_r["P_B"]})
    fwd_cross = psc.find_crossover(forward)
    # reverse crossover: first where P_A >= P_B when sweeping toward A
    rev_cross = {"found": False, "index": None, "point": None}
    for i, p in enumerate(reverse):
        if float(p["P_A"]) >= float(p["P_B"]):
            rev_cross = {"found": True, "index": i, "point": p}
            break
    hyst_gap = None
    if fwd_cross.get("found") and rev_cross.get("found"):
        # compare observer level indices
        fwd_lvl = fwd_cross["point"]["level_observer"]
        rev_lvl = rev_cross["point"]["level_observer"]
        hyst_gap = {
            "forward_level": fwd_lvl,
            "reverse_level": rev_lvl,
            "levels_differ": fwd_lvl != rev_lvl,
        }
    # Causal control: normalize histories on reverse path
    causal = {"attempted": False}
    if hyst_gap and hyst_gap.get("levels_differ"):
        causal["attempted"] = True
        # rematch A/B support then remeasure at equal level
        st_norm = psc.build_history_store(
            a_n=40, b_fragment_n=40,
            a_distal=pci.B_MINUS(), b_distal=levels["equal"], seed=seed,
        )
        act_n = psc.measure_action(st_norm, goals, seed=seed + 700)
        causal["normalized_equal_level"] = {"P_A": act_n["P_A"], "P_B": act_n["P_B"]}
        causal["gap_shrinks_under_normalization"] = abs(act_n["P_A"] - act_n["P_B"]) < 0.08

    out["hysteresis_probe"] = {
        "forward": forward,
        "reverse": reverse,
        "forward_transition": fwd_cross,
        "reverse_transition": rev_cross,
        "hysteresis_gap": hyst_gap,
        "causal_control": causal,
        "hysteresis_candidate_observed": bool(hyst_gap and hyst_gap.get("levels_differ")),
    }

    # --- Claim evaluation ---
    # C2: history effect under matched consequences + ablation shrinks + not raw-only
    c2 = (
        history_effect_matched
        and ablation["structure_ablation_shrinks_A"]
        and out["raw_repetition_control"]["structure_differs_from_raw"]
        and out["same_present_different_history"]["differs"]
    )
    # weaker C2 if matched history effect OR same-present differs, with ablation
    c2_partial = (
        (history_effect_matched or out["same_present_different_history"]["differs"])
        and ablation["structure_ablation_shrinks_A"]
    )
    out["C2_history_dependent_action"] = bool(c2)
    out["C2_partial_candidate"] = bool(c2_partial)

    c3 = bool(out["evidence_accumulation"]["transition_observed"]) and transition_type != "insufficient"
    # require no switching rule — architectural (always true here)
    out["C3_evidence_driven_transition"] = bool(c3)

    c4 = bool(
        out["hysteresis_probe"]["hysteresis_candidate_observed"]
        and (causal.get("gap_shrinks_under_normalization") is True)
    )
    out["C4_history_dependent_hysteresis"] = bool(c4)

    # leak audit on cognition-facing stores (no Observer labels in store)
    leak = psc.audit_forbidden({"transitions_keys": list(store.get("transitions", {}).keys())[:20],
                                "full_seq": store.get("full_sequence_patterns")})
    out["leak_tokens"] = leak

    # first unsupported arrow
    chain = [
        ("retained_predictive_structure", True),
        ("simultaneous_competition", out["C1_competing_continuations"]),
        ("history_dependent_action_distribution", out["C2_history_dependent_action"] or out["C2_partial_candidate"]),
        ("evidence_driven_behavioral_transition", out["C3_evidence_driven_transition"]),
        ("path_dependent_reverse_transition", bool(out["hysteresis_probe"]["hysteresis_candidate_observed"])),
        ("causal_hysteresis", out["C4_history_dependent_hysteresis"]),
    ]
    first_unsup = None
    for name, ok in chain:
        if not ok:
            first_unsup = name
            break
    out["first_unsupported_arrow"] = first_unsup or "NONE_ALL_SUPPORTED"
    out["claim_chain"] = chain
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    ap.add_argument("--ticks", type=int, default=50, help="primary A history n alias")
    args = ap.parse_args()
    seeds = args.seeds or SEEDS

    OUT.mkdir(parents=True, exist_ok=True)
    dump("CONFIG.json", {
        "update": "4.28",
        "seeds": seeds,
        "history_levels": HISTORY,
        "B_FRAG_INTRO": B_FRAG_INTRO,
        "N_SAMPLES": N_SAMPLES,
        "DISTAL_BLEND": pci.DISTAL_BLEND,
        "DEFAULT_TEMPERATURE": pci.DEFAULT_TEMPERATURE,
        "no_habit_semantics": True,
        "uses_unchanged_4_26_pathway": True,
    })

    per = [run_seed(s) for s in seeds]
    dump("per_seed_results.json", per)

    def seeds_where(pred):
        return [str(r["seed"]) for r in per if pred(r)]

    claim = {
        "C1_simultaneous_competing_predictive_continuations": {
            "asserted": all(r.get("C1_competing_continuations") for r in per),
            "seeds": seeds_where(lambda r: r.get("C1_competing_continuations")),
        },
        "C2_history_dependent_action_influence": {
            "asserted": all(r.get("C2_history_dependent_action") for r in per),
            "partial_seeds": seeds_where(lambda r: r.get("C2_partial_candidate")),
            "seeds": seeds_where(lambda r: r.get("C2_history_dependent_action")),
        },
        "C3_evidence_driven_behavioral_transition": {
            "asserted": all(r.get("C3_evidence_driven_transition") for r in per),
            "seeds": seeds_where(lambda r: r.get("C3_evidence_driven_transition")),
        },
        "C4_history_dependent_hysteresis": {
            "asserted": all(r.get("C4_history_dependent_hysteresis") for r in per),
            "seeds": seeds_where(lambda r: r.get("C4_history_dependent_hysteresis")),
        },
    }
    dump("claim_matrix.json", claim)

    dump("history_conditions.json", {str(r["seed"]): r["baseline_history"] for r in per})
    dump("competing_predictions.json", {str(r["seed"]): r["competing_intro"] for r in per})
    dump("action_distributions.json", {
        str(r["seed"]): {
            "intro": r["competing_intro"]["action"],
            "matched": r["matched_consequence_history"],
        }
        for r in per
    })
    dump("transition_sweeps.json", {str(r["seed"]): {
        "evidence_accumulation": r["evidence_accumulation"],
        "distal_advantage_sweep": r["distal_advantage_sweep"],
    } for r in per})
    dump("ablations.json", {str(r["seed"]): r["ablations"] for r in per})
    dump("hysteresis_probe.json", {str(r["seed"]): r["hysteresis_probe"] for r in per})
    dump("same_present_different_history.json", {str(r["seed"]): r["same_present_different_history"] for r in per})
    dump("control_results.json", {str(r["seed"]): {
        "raw_repetition": r["raw_repetition_control"],
        "shuffled": r["shuffled_history_control"],
        "reliability": r["reliability_control"],
        "history_neutral_consequence": r["history_neutral_consequence"],
        "composed_vs_experienced": r["composed_vs_experienced"],
        "matched_predictions": r["different_history_matched_predictions"],
        "generalized_separate": r["generalized_competitor_separate"],
    } for r in per})
    dump("leak_audit.json", {
        "per_seed": [{"seed": r["seed"], "tokens": r["leak_tokens"]} for r in per],
        "any_leak": any(r["leak_tokens"] for r in per),
    })
    dump("ACCEPTANCE_MATRIX.json", {
        "C1": claim["C1_simultaneous_competing_predictive_continuations"]["asserted"],
        "C2": claim["C2_history_dependent_action_influence"]["asserted"],
        "C3": claim["C3_evidence_driven_behavioral_transition"]["asserted"],
        "C4": claim["C4_history_dependent_hysteresis"]["asserted"],
        "no_forbidden_tokens": not any(r["leak_tokens"] for r in per),
    })
    dump("BASELINE_REGRESSION.json", {
        "preserve_4_25_C3_NOT_ASSERTED": True,
        "preserve_4_26_C3_ASSERTED": True,
        "preserve_4_26_C4_NOT_ASSERTED": True,
        "preserve_4_27_C1_C4_ASSERTED": True,
        "status": "NOT_FULLY_RE_RUN_IN_SMOKE",
        "note": "Do not rewrite prior FINAL_REPORTs; historical NULLs stand.",
    })
    dump("INTEGRATION_PRESERVE.json", {
        "metrics_affect_cognition": False,
        "observer_telemetry_only": True,
        "no_habit_belief_in_cognition": True,
        "unchanged_4_26_DISTAL_BLEND": pci.DISTAL_BLEND,
        "unchanged_4_26_T": pci.DEFAULT_TEMPERATURE,
    })

    first_arrows = [r["first_unsupported_arrow"] for r in per]
    dump("summary.json", {
        "claims": claim,
        "first_unsupported_arrows": first_arrows,
        "seeds": seeds,
    })

    # Observer snapshot
    obs = {
        "update": "4.28",
        "preset": "4.28 Predictive Scenario Competition",
        "layers": {
            "WORLD_TRUTH": "S0 with A/B/WAIT continuations; histories H0/H10/H50/H100",
            "BODY_TRUTH": "Distal body vectors for A/B (researcher levels)",
            "ACCESSIBLE_SIGNALS": "Same S0 body signals; no HABIT/CONFIDENCE tokens",
            "PSYCHE_MODEL": "4.23 transitions + 4.26 softmax; support=learn counts only",
            "PROSPECTIVE": [r["competing_intro"]["snapshot"]["candidates"] for r in per],
            "ACTION": [r["competing_intro"]["action"] for r in per],
            "CONSEQUENCE": claim,
        },
        "claim_matrix": claim,
        "hysteresis": {str(r["seed"]): {
            "observed": r["hysteresis_probe"]["hysteresis_candidate_observed"],
            "gap": r["hysteresis_probe"]["hysteresis_gap"],
        } for r in per},
        "same_present_different_history": {str(r["seed"]): r["same_present_different_history"] for r in per},
        "transition_types": {str(r["seed"]): r["evidence_accumulation"]["transition_type"] for r in per},
        "first_unsupported_arrows": first_arrows,
    }
    dump("OBSERVER_COMPETITION_SNAPSHOT.json", obs)

    lines = [
        "# Update 4.28 FINAL REPORT - Competing Predictive Continuations",
        "",
        "## Architecture",
        "Existing 4.23 composition + 4.26 ordinary_state_value → softmax.",
        "No HABIT/BELIEF/COMMITMENT/CONFIDENCE/ENTRENCHMENT/SWITCHING_COST in cognition.",
        "Historical support = ordinary learn_transition / full_sequence exposure counts.",
        "",
        "## Claims",
    ]
    for k, v in claim.items():
        st = "ASSERTED" if v["asserted"] else "NOT ASSERTED"
        lines.append(f"- {k}: **{st}** seeds={v.get('seeds')}")
        if "partial_seeds" in v:
            lines.append(f"  partial_seeds={v['partial_seeds']}")
    lines += ["", "## First unsupported arrow (per seed)"]
    for r in per:
        lines.append(f"- seed {r['seed']}: {r['first_unsupported_arrow']} "
                     f"C1={r['C1_competing_continuations']} C2={r['C2_history_dependent_action']} "
                     f"C2part={r['C2_partial_candidate']} C3={r['C3_evidence_driven_transition']} "
                     f"C4={r['C4_history_dependent_hysteresis']} "
                     f"trans={r['evidence_accumulation']['transition_type']}")
    lines += [
        "",
        "## Historical preserve",
        "- 4.25 C3 NULL, 4.26 C4 NULL untouched; no EMA retune.",
        "- 4.26 C3 / 4.27 C1–C4 preserved as historical ASSERTED.",
        "- Prior FINAL_REPORTs not rewritten.",
        "",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps(claim, indent=2))
    print("first_arrows", first_arrows)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
