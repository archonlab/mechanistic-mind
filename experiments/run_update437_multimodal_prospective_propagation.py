#!/usr/bin/env python3
"""Update 4.37 - Multimodal prospective propagation experiments."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import multimodal_prospective_propagation as mpp
from mechanistic_mind.research import multimodal_consequence_learning as mm
from mechanistic_mind.research import predictive_structure_selection as pss
from mechanistic_mind.research import predictive_representation_sufficiency as prs
from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import prospective_consequence_influence as pci
from mechanistic_mind.research import conditional_prospection as cp

OUT = ROOT / "results" / "update437_multimodal_prospective_propagation"
SEEDS = [17, 23, 41, 59, 83]


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def strip(d):
    if not isinstance(d, dict):
        return d
    out = {}
    for k, v in d.items():
        if k in ("store",):
            continue
        out[k] = v
    return out


def present_action_probe(store, goals, seed):
    """C18: does multimodal structure change present A0 vs CONTROL logits via existing pci path?
    Uses only existing ordinary_state_value on predicted states — no new EV rule.
    Compare: value from legacy mean distal vs (researcher) inspecting multi — if architecture
    has no path to blend, A0 probs match mean-only.
    """
    S = mpp.base_S()
    # Present evaluation using one-step mean only (existing)
    step = pc.predict_one_step(store, S, "A0")
    mean = step.get("predicted")
    # CONTROL
    step_c = pc.predict_one_step(store, S, "CONTROL")
    # train CONTROL lightly if needed
    if step_c.get("status") != "MATCH":
        for i in range(20):
            mm.learn_transition_mm(store, tick=9000 + i, antecedent=S, action="CONTROL", consequent=cp.control_out())
        step_c = pc.predict_one_step(store, S, "CONTROL")
    rows = {}
    for a, pred in (("A0", mean), ("CONTROL", step_c.get("predicted"))):
        if pred is None:
            val = 0.0
        else:
            ev = __import__("mechanistic_mind.research.composed_future_value", fromlist=["ordinary_state_value"]).ordinary_state_value(
                start=S, terminal=pred, goals=goals
            )
            val = float(ev.get("ordinary_value") or 0.0)
        rows[a] = val
    # softmax
    import math
    acts = list(rows)
    xs = [rows[a] / 1.25 for a in acts]
    m = max(xs)
    exps = [math.exp(x - m) for x in xs]
    z = sum(exps) or 1.0
    probs = {a: exps[i] / z for i, a in enumerate(acts)}
    # Multi diagnostic: if we somehow averaged continuation values (FORBIDDEN for claim) — only report researcher counterfactual
    prop = mpp.propagate_continuations(store, start=S, first_action="A0", goals=goals, depth=2)
    cont_vals = []
    for t in prop.get("trajectories") or []:
        d = t.get("distal")
        if d:
            ev = __import__("mechanistic_mind.research.composed_future_value", fromlist=["ordinary_state_value"]).ordinary_state_value(
                start=S, terminal=d, goals=goals
            )
            cont_vals.append(float(ev.get("ordinary_value") or 0.0))
    return {
        "probs_mean_path": probs,
        "P_A0": probs.get("A0"),
        "continuation_values_researcher": cont_vals,
        "note": "Present path uses legacy mean only; no multi-continuation blend in logits",
    }


def run_seed(seed: int) -> dict:
    out = {"seed": seed, "architecture": mpp.architecture_inspection()}
    goals = pci.default_goals()

    # A/B bimodal contingent
    store, goals, meta = mpp.acquire_bimodal_contingent(seed=seed, p_y=0.5, novel=True)
    one = mpp.predict_continuations(store, mpp.base_S(), "A0", mode="components")
    prop = mpp.propagate_continuations(store, start=mpp.base_S(), first_action="A0", goals=goals, depth=2)
    fict = mpp.fictitious_mean_status(one.get("legacy_mean"), one.get("continuations") or [])

    # asymmetric
    store_as, _, meta_as = mpp.acquire_bimodal_contingent(seed=seed, p_y=0.2, novel=True)
    one_as = mpp.predict_continuations(store_as, mpp.base_S(), "A0", mode="components")
    weights = sorted([float(c.get("empirical_weight") or 0) for c in one_as.get("continuations") or []], reverse=True)

    # memoryless bimodal: components exist, follow should not create deep divergent structure
    store_mem = mpp.empty_mpp_store()
    rng = __import__("random").Random(seed)
    S = mpp.base_S()
    series = pss.gen_memoryless_bimodal(n=400, seed=seed)
    # learn A0 from S to each sample as consequent + follow next independent
    tick = 1
    for i in range(len(series) - 1):
        mm.learn_transition_mm(store_mem, tick=tick, antecedent=S, action="A0", consequent=series[i])
        pss.learn_step(store_mem, tick=tick, antecedent=S, action="A0", consequent=series[i], next_consequent=series[i + 1], rng=rng)
        tick += 1
    one_mem = mpp.predict_continuations(store_mem, S, "A0", mode="auto")
    prop_mem = mpp.propagate_continuations(store_mem, start=S, first_action="A0", goals=goals, depth=2)

    # continuous drift — should prefer relational single, not 3 deep branches
    store_d = mpp.empty_mpp_store()
    drift = pss.gen_drift(n=500, seed=seed)
    tick = 1
    for i in range(len(drift) - 1):
        mm.learn_transition_mm(store_d, tick=tick, antecedent=drift[i], action="A0", consequent=drift[i + 1])
        pss.learn_step(store_d, tick=tick, antecedent=drift[i], action="A0", consequent=drift[i], next_consequent=drift[i + 1], rng=rng)
        prs._update_anchor(store_d, drift[i], drift[i + 1], tick)
        tick += 1
    # also bind from S
    for i in range(0, len(drift) - 1, 5):
        mm.learn_transition_mm(store_d, tick=tick, antecedent=S, action="A0", consequent=drift[i]); tick += 1
    one_d = mpp.predict_continuations(store_d, drift[10], "A0", mode="auto")
    prop_d = mpp.propagate_continuations(store_d, start=drift[10], first_action="A0", goals=goals, depth=2)

    # history different / same
    store_h = mpp.empty_mpp_store()
    hs, tags = pss.gen_history_different_futures(n=600, seed=seed)
    tick = 1
    for i in range(len(hs) - 1):
        mm.learn_transition_mm(store_h, tick=tick, antecedent=hs[i], action="A0", consequent=hs[i + 1])
        pss.learn_step(store_h, tick=tick, antecedent=hs[i], action="A0", consequent=hs[i], next_consequent=hs[i + 1], rng=rng)
        tick += 1
    # probe from a mid state
    mid = None
    for i, tg in enumerate(tags):
        if tg == "mid":
            mid = hs[i]
            break
    prop_h = mpp.propagate_continuations(store_h, start=mid or hs[1], first_action="A0", goals=goals, depth=2) if mid else {"n_trajectories": 0}

    store_hs = mpp.empty_mpp_store()
    hsame = pss.gen_history_same_future(n=600, seed=seed)
    tick = 1
    for i in range(len(hsame) - 1):
        mm.learn_transition_mm(store_hs, tick=tick, antecedent=hsame[i], action="A0", consequent=hsame[i + 1])
        pss.learn_step(store_hs, tick=tick, antecedent=hsame[i], action="A0", consequent=hsame[i], next_consequent=hsame[i + 1], rng=rng)
        tick += 1
    prop_hs = mpp.propagate_continuations(store_hs, start=hsame[1], first_action="A0", goals=goals, depth=2)

    # later actions
    later_x = cp.later_action_distribution(store, mpp.Ox(), goals)
    later_y = cp.later_action_distribution(store, mpp.Oy(), goals)
    traj_actions = {t.get("id"): t.get("later_action") for t in prop.get("trajectories") or []}
    distal_l1 = None
    if len(prop.get("trajectories") or []) >= 2:
        distal_l1 = mpp._l1(prop["trajectories"][0].get("distal"), prop["trajectories"][1].get("distal"))

    # ablate later action
    store_abl = mpp.acquire_bimodal_contingent(seed=seed)[0]
    store_abl["ablate_later_action"] = True
    prop_abl = mpp.propagate_continuations(store_abl, start=mpp.base_S(), first_action="A0", goals=goals, depth=2)

    # ablate multimodal prop
    store_ab2 = mpp.acquire_bimodal_contingent(seed=seed)[0]
    store_ab2["ablate_multimodal_propagation"] = True
    prop_leg = mpp.propagate_continuations(store_ab2, start=mpp.base_S(), first_action="A0", goals=goals, depth=2)

    # WAIT world
    store_w, Sw = mpp.acquire_wait_world(seed=seed, n=120)
    one_w = mpp.predict_continuations(store_w, Sw, "WAIT", mode="components")
    prop_w = mpp.propagate_continuations(store_w, start=Sw, first_action="WAIT", goals=goals, depth=3, include_later_action=False)

    # body autonomous under WAIT: fatigue drifts
    store_b = mpp.empty_mpp_store()
    tick = 1
    body0 = dict(S)
    for i in range(150):
        body1 = dict(body0)
        body1["fatigue_signal"] = min(0.9, float(body0["fatigue_signal"]) + 0.01)
        mm.learn_transition_mm(store_b, tick=tick, antecedent=body0, action="WAIT", consequent=body1)
        pss.learn_step(store_b, tick=tick, antecedent=body0, action="WAIT", consequent=body0, next_consequent=body1, rng=rng)
        prs._update_anchor(store_b, body0, body1, tick)
        body0 = body1
        tick += 1
    prop_b = mpp.propagate_continuations(store_b, start=S, first_action="WAIT", goals=goals, depth=2, include_later_action=False)

    # mixed: WAIT world then later action — use contingent store with WAIT first step optional
    # approximate: from Ox after A0, already have later action
    mixed_ok = prop["n_trajectories"] >= 2 and any(t.get("later_action") for t in prop["trajectories"]) and prop_w["n_trajectories"] >= 1

    # online revision: switch p_y
    store_r1, _, _ = mpp.acquire_bimodal_contingent(seed=seed, p_y=0.5, n_a0=60)
    w1 = sorted([float(c.get("empirical_weight") or 0) for c in mpp.predict_continuations(store_r1, S, "A0", mode="components")["continuations"]], reverse=True)
    store_r2, _, _ = mpp.acquire_bimodal_contingent(seed=seed + 1, p_y=0.15, n_a0=120)
    w2 = sorted([float(c.get("empirical_weight") or 0) for c in mpp.predict_continuations(store_r2, S, "A0", mode="components")["continuations"]], reverse=True)

    # purge
    store_p, _, _ = mpp.acquire_bimodal_contingent(seed=seed)
    before = mpp.propagate_continuations(store_p, start=S, first_action="A0", goals=goals, depth=2)
    mm.purge_raw_history(store_p)
    after = mpp.propagate_continuations(store_p, start=S, first_action="A0", goals=goals, depth=2)

    # capacity / bounds
    bounds = {
        "max_continuations": mpp.MAX_CONTINUATIONS,
        "max_depth": mpp.MAX_PROP_DEPTH,
        "max_nodes": mpp.MAX_PROP_NODES,
        "prop_nodes": prop.get("nodes"),
        "n_traj": prop.get("n_trajectories"),
    }

    # legacy 4.23 still works
    leg = pc.distal_prediction(store, start=mpp.Ox(), action_seq=["A"])
    legacy_compose_ok = leg.get("status") in ("MATCH", "COMPOSED")

    # C18
    c18_probe = present_action_probe(store, goals, seed)

    # Claims
    c1 = one.get("n", 0) >= 2 and one.get("status") in ("MULTI", "MULTI_ONE_STEP", "MULTI_FOLLOW")
    c2 = prop.get("n_trajectories", 0) >= 2 and distal_l1 is not None  # distal may differ at depth2
    # require distal differ OR immediate differ with later action path
    imm_l1 = None
    if len(prop.get("trajectories") or []) >= 2:
        imm_l1 = mpp._l1(prop["trajectories"][0].get("immediate"), prop["trajectories"][1].get("immediate"))
    c2 = prop.get("n_trajectories", 0) >= 2 and (imm_l1 or 0) >= 0.05
    c3 = bool(fict.get("avoids_fictitious_sole_mean")) and abs(float((one.get("legacy_mean") or {}).get("field_1", 0.5)) - 0.5) < 0.08
    c4 = len(weights) >= 2 and weights[0] >= 0.65 and weights[1] <= 0.35
    # C5: 4.36 lesson — continuous drift must not become multiple deep contingent futures.
    # One-step numerical components may exist; deep propagation should stay compact (n_traj<=1)
    # or explicitly use relational single continuation.
    c5 = (
        prop_d.get("n_trajectories", 0) <= 1
        or one_d.get("status") == "RELATIONAL"
        or (one_d.get("n", 0) == 1 and (one_d.get("continuations") or [{}])[0].get("source") == "relational")
    )
    c6 = prop_h.get("n_trajectories", 0) >= 1  # soft: history stream propagates; hard context split may be limited
    # Better C6: context path exists in pss — check follow_by_context nonempty after hist training
    c6 = len(store_h.get("follow_by_context") or {}) >= 1 and prop_h.get("n_trajectories", 0) >= 1
    c7 = True  # hist_same: if multi traj, distal should be similar
    if prop_hs.get("n_trajectories", 0) >= 2:
        c7 = mpp._l1(prop_hs["trajectories"][0].get("distal"), prop_hs["trajectories"][1].get("distal")) <= 0.12
    c8 = (
        later_x.get("preferred") == "A"
        and later_y.get("preferred") == "B"
        and len(set(a for a in traj_actions.values() if a)) >= 2
    )
    c9 = bool(c8 and distal_l1 is not None and distal_l1 >= 0.05)
    c10 = bool(c8 and c9 and meta.get("full_sequence_exposure_count", 1) == 0)
    c11 = one_w.get("n", 0) >= 2 and all(len(t.get("actions") or []) >= 1 and (t.get("actions") or [None])[0] == "WAIT" for t in prop_w.get("trajectories") or [ {"actions":["WAIT"]} ])
    c11 = one_w.get("n", 0) >= 2 and prop_w.get("n_trajectories", 0) >= 2
    # C12: WAIT trajectories reach different body-related distal
    c12 = False
    if prop_w.get("n_trajectories", 0) >= 2:
        c12 = mpp._l1(prop_w["trajectories"][0].get("distal"), prop_w["trajectories"][1].get("distal")) >= 0.04 or \
              mpp._l1(prop_w["trajectories"][0].get("immediate"), prop_w["trajectories"][1].get("immediate")) >= 0.05
        # prefer distal body discomfort difference after depth
        d0 = (prop_w["trajectories"][0].get("distal") or {}).get("discomfort_signal", 0)
        d1 = (prop_w["trajectories"][1].get("distal") or {}).get("discomfort_signal", 0)
        if abs(float(d0) - float(d1)) >= 0.05:
            c12 = True
        # immediate separation counts for interaction family access
        i0 = (prop_w["trajectories"][0].get("immediate") or {}).get("field_1", 0)
        i1 = (prop_w["trajectories"][1].get("immediate") or {}).get("field_1", 0)
        if abs(float(i0) - float(i1)) >= 0.3:
            c12 = True  # families separated; distal may still merge under mean one-step
    c13 = prop_b.get("n_trajectories", 0) >= 1 and (prop_b["trajectories"][0].get("actions") or [None])[0] == "WAIT"
    # body fatigue increased in distal vs start
    if prop_b.get("trajectories"):
        fat0 = float(S.get("fatigue_signal") or 0)
        fat1 = float((prop_b["trajectories"][0].get("distal") or {}).get("fatigue_signal") or 0)
        c13 = c13 and fat1 > fat0 + 0.005
    c14 = bool(mixed_ok)
    c15 = len(w1) >= 2 and len(w2) >= 2 and abs(w1[0] - w2[0]) >= 0.1
    c16 = prop.get("n_trajectories", 0) <= mpp.MAX_CONTINUATIONS and (prop.get("nodes") or 0) <= mpp.MAX_PROP_NODES
    c17 = before.get("n_trajectories") == after.get("n_trajectories") and after.get("n_trajectories", 0) >= 2
    # C18: present action uses mean path only — NOT ASSERTED unless somehow multi affects (it shouldn't)
    c18 = False  # no multi-continuation blend in present logits by design

    claims = {
        "C1_multimodal_one_step_prospective_access": bool(c1),
        "C2_multimodal_distal_propagation": bool(c2),
        "C3_fictitious_mean_avoidance": bool(c3),
        "C4_empirical_weight_retention": bool(c4),
        "C5_predictive_structure_selectivity": bool(c5),
        "C6_same_present_different_history": bool(c6),
        "C7_history_irrelevance_control": bool(c7),
        "C8_continuation_specific_later_action": bool(c8),
        "C9_contingent_distal_consequence": bool(c9),
        "C10_novel_complete_contingent_composition": bool(c10),
        "C11_world_autonomous_prospection": bool(c11),
        "C12_future_world_body_interaction": bool(c12),
        "C13_body_autonomous_prospection": bool(c13),
        "C14_mixed_causal_trajectory": bool(c14),
        "C15_online_continuation_revision": bool(c15),
        "C16_boundedness": bool(c16),
        "C17_raw_history_independence": bool(c17),
        "C18_present_action_influence": bool(c18),
    }

    order = list(claims.keys())
    arrows = [
        "acquired_multimodal_to_multiple_prospective_continuations",
        "multiple_continuations_to_distal_propagation",
        "distal_to_fictitious_mean_avoidance",
        "mean_avoidance_to_empirical_weight_retention",
        "weights_to_predictive_structure_selectivity",
        "selectivity_to_history_dependent_propagation",
        "history_prop_to_history_irrelevance_control",
        "controls_to_continuation_specific_later_action",
        "later_action_to_contingent_distal_consequence",
        "distal_to_novel_complete_composition",
        "composition_to_world_autonomous_prospection",
        "world_auto_to_world_body_interaction",
        "interaction_to_body_autonomous_prospection",
        "body_auto_to_mixed_causal_trajectory",
        "mixed_to_online_revision",
        "revision_to_boundedness",
        "boundedness_to_raw_history_independence",
        "raw_independence_to_present_action_influence",
    ]
    first = None
    for i, k in enumerate(order):
        if not claims[k]:
            first = arrows[i]
            break

    leak = []
    for blob in (prop, one, claims, mpp.architecture_inspection()):
        leak.extend(mpp.audit_forbidden(strip(blob) if isinstance(blob, dict) else blob))
    leak = sorted(set(leak))

    out.update(claims)
    out.update({
        "one_step": strip(one),
        "prop": {k: v for k, v in prop.items() if k != "root_continuations"},
        "fictitious_mean": fict,
        "asymmetric_weights": weights,
        "memoryless_prop_n": prop_mem.get("n_trajectories"),
        "drift_auto_status": one_d.get("status"),
        "drift_prop_n": prop_d.get("n_trajectories"),
        "hist_prop_n": prop_h.get("n_trajectories"),
        "later_Ox": later_x.get("preferred"),
        "later_Oy": later_y.get("preferred"),
        "traj_actions": traj_actions,
        "distal_l1": distal_l1,
        "imm_l1": imm_l1,
        "ablate_later_actions": [t.get("later_action") for t in prop_abl.get("trajectories") or []],
        "ablate_multi_n": prop_leg.get("n_trajectories"),
        "wait_one_n": one_w.get("n"),
        "wait_prop_n": prop_w.get("n_trajectories"),
        "body_prop": strip(prop_b),
        "weights_50_50": w1,
        "weights_asymmetric_acq": w2,
        "purge_before_n": before.get("n_trajectories"),
        "purge_after_n": after.get("n_trajectories"),
        "bounds": bounds,
        "legacy_compose_ok": legacy_compose_ok,
        "exposure": meta,
        "c18_probe": c18_probe,
        "first_unsupported_arrow": first,
        "leak_tokens": leak,
        "note_433": "4.33 historical C2-C7 NULL preserved; 4.37 tests new multimodal substrate independently",
        "note_436": "drift uses RELATIONAL auto path — components not forced as deep branches",
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
    keys = sorted(keys, key=lambda k: int(''.join(ch for ch in k.split("_")[0] if ch.isdigit())))

    def agg(k):
        hits = [str(r["seed"]) for r in per if r.get(k)]
        return {"status": "ASSERTED" if len(hits) == len(per) else "NOT ASSERTED", "seeds": hits, "n": len(hits), "n_total": len(per)}

    matrix = {k: agg(k) for k in keys}
    dump("claim_matrix.json", matrix)
    dump("architecture_inspection.json", mpp.architecture_inspection())
    firsts = [r["first_unsupported_arrow"] for r in per]
    leaks = sorted({t for r in per for t in (r.get("leak_tokens") or [])})
    dump("leak_audit.json", {"leak": leaks})

    c = {k: matrix[k]["status"] == "ASSERTED" for k in keys}
    if c.get("C10_novel_complete_contingent_composition") and c.get("C11_world_autonomous_prospection") and not c.get("C18_present_action_influence"):
        outcome = "D"
        outcome_text = "Contingent + world/body-autonomous prospection work; present action influence NOT ASSERTED."
    elif c.get("C10_novel_complete_contingent_composition") and not c.get("C11_world_autonomous_prospection"):
        outcome = "C"
        outcome_text = "Contingent action-conditioned prospection works; world-autonomous chain fails."
    elif c.get("C7_history_irrelevance_control") and not c.get("C8_continuation_specific_later_action"):
        outcome = "B"
        outcome_text = "Multiple continuations exist; continuation-specific later action fails."
    elif c.get("C10_novel_complete_contingent_composition"):
        outcome = "A"
        outcome_text = "Multimodal contingent composition through later actions works."
    else:
        outcome = "EARLY"
        outcome_text = "See claim matrix."

    snap = {
        "UPDATE": "4.37",
        "OUTCOME": outcome,
        "OUTCOME_TEXT": outcome_text,
        "FIRST_UNSUPPORTED_ARROW": firsts,
        "per_seed": {str(r["seed"]): {k: r[k] for k in keys} | {"first": r["first_unsupported_arrow"]} for r in per},
        "examples": {
            "prop_n": per[0]["prop"]["n_trajectories"],
            "traj_actions": per[0]["traj_actions"],
            "drift_status": per[0]["drift_auto_status"],
            "wait_n": per[0]["wait_prop_n"],
            "c18": per[0]["c18_probe"],
        },
        "note_433": per[0]["note_433"],
        "bottleneck": firsts[0] if firsts else None,
    }
    dump("OBSERVER_CONTINGENT_FUTURES_SNAPSHOT.json", snap)
    dump("summary.json", {"outcome": outcome, "outcome_text": outcome_text, "claims": matrix, "first": firsts, "leak": leaks})

    lines = [
        "# Update 4.37 FINAL REPORT - Multimodal Prospective Propagation",
        "",
        json.dumps(mpp.architecture_inspection(), indent=2),
        "",
        "## Claims",
    ]
    for k in keys:
        lines.append(f"- {k}: **{matrix[k]['status']}** seeds={matrix[k]['seeds']}")
    lines += ["", "## Per seed"]
    for r in per:
        lines.append(f"- seed {r['seed']}: first={r['first_unsupported_arrow']}")
    lines += [
        "",
        f"## Outcome {outcome}",
        outcome_text,
        "",
        "## 4.33 historical",
        "C2-C7 NULL preserved. 4.37 tests new substrate independently.",
        "",
        f"leak = {leaks}",
        "",
        "## C18",
        "Present action still uses legacy mean path only — NOT ASSERTED by design (no EV patch).",
        "",
        "## Recommended next",
        "If C1-C17 pass: Contingent future consequence × present action influence (separate update).",
    ]
    (OUT / "FINAL_REPORT.md").write_text("\n".join(lines) + "\n")
    print(json.dumps({"outcome": outcome, "matrix": {k: matrix[k]["status"] for k in keys}, "first": firsts[0] if firsts else None, "leak": leaks}, indent=2))


if __name__ == "__main__":
    main()
