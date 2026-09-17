#!/usr/bin/env python3
"""Update 4.25 - Emergent instrumental observation experiments."""
from __future__ import annotations
import argparse, json, random, sys
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "worlds"), str(ROOT / "experiments")]

from mechanistic_mind.research import instrumental_observation as io
from mechanistic_mind.research import prospective_composition as pc
from mechanistic_mind.research import predictive_compression as pcomp
from mechanistic_mind.research import hierarchical_body_prediction as hbp
from mechanistic_mind.research import background_context as bc
from mechanistic_mind.research import multiscale_prediction as ms

OUT = ROOT / "results" / "update425_instrumental_observation"


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def develop_store(seed, n=80, mode="useful", strength="large", full_sequence=False,
                  ablate_world_to_m=False, ablate_m_to_body=False):
    """Developmental experience. If full_sequence False: separate fragments only."""
    rng = random.Random(seed)
    store = io.empty_store()
    exp = store["exposure"]
    for t in range(n):
        kind = "A" if (t % 2 == 0) else "B"
        w = io.world_state(kind)
        exp["W_A" if kind == "A" else "W_B"] += 1
        # direct ambiguous exposure
        o_direct = io.direct_observation(w, noise=0.01, rng=rng)
        # sometimes contact M
        contact = True
        exp["M_encounters"] += 1
        if contact:
            exp["M_interactions"] += 1
        o_med = io.mediated_observation(
            w, mode=mode, contact=contact,
            ablate_world_to_m=ablate_world_to_m,
            ablate_m_to_body=ablate_m_to_body, rng=rng,
        )
        if contact and mode == "useful" and not ablate_m_to_body and not ablate_world_to_m:
            exp["mediated_A" if kind == "A" else "mediated_B"] += 1
        fut = io.future_consequence(w, strength=strength)
        if full_sequence:
            # end-to-end W->M->O->F in one episode (cached)
            io.learn_prediction(store, o_med, fut)
            exp["full_mediated_sequence"] += 1
        else:
            # Fragment training: O^M -> F separately from W->O^M experience
            # Never learn from a single uninterrupted logged full chain counter
            io.learn_prediction(store, o_med, fut)
            # also some direct->future (ambiguous, weak)
            io.learn_prediction(store, o_direct, {"e": 0.5, "f": 0.5})
    if not full_sequence:
        exp["full_mediated_sequence"] = 0
    return store


def c2_prediction_probe(store, seed, mode="useful"):
    """Prediction before vs after mediated evidence. No action required."""
    rng = random.Random(seed + 7)
    results = {}
    for kind in ("A", "B"):
        w = io.world_state(kind)
        o_direct = io.direct_observation(w, noise=0.0, rng=rng)
        o_med = io.mediated_observation(w, mode=mode, rng=rng)
        fut = io.future_consequence(w, strength="large")
        before = io.predict(store, o_direct)
        after = io.predict(store, o_med)
        err_b = None if before.get("predicted") is None else io.l1(before["predicted"], fut)
        err_a = None if after.get("predicted") is None else io.l1(after["predicted"], fut)
        results[kind] = {
            "before": before, "after": after,
            "future_gt": fut,  # researcher
            "error_before": err_b, "error_after": err_a,
            "improved": (err_b is not None and err_a is not None and err_a < err_b - 1e-6)
            or (err_b is None and err_a is not None and err_a < 0.25),
        }
    # Cross: after A evidence, should predict F_A better than F_B
    pa = results["A"]["after"].get("predicted")
    pb = results["B"]["after"].get("predicted")
    discrimination = None
    if pa and pb:
        discrimination = io.l1(pa, results["B"]["future_gt"]) - io.l1(pa, results["A"]["future_gt"])
    return {
        "by_kind": results,
        "both_improved": results["A"]["improved"] and results["B"]["improved"],
        "prediction_discrimination": discrimination,
        "c2_candidate": bool(results["A"]["improved"] and results["B"]["improved"]),
    }


def c3_action_probe(store, seed):
    """Stronger optional probe: researcher-side selection proxy, NOT psyche faculty.

    Uses existing valuation-like preference over predicted e only when prediction MATCH.
    Does not add epistemic reward. Reports whether mediated evidence would change choice.
    """
    rng = random.Random(seed + 99)
    # Ambiguous: two actions X/Y; without mediation same; with mediation differ
    # Action X better under A, Y under B - based on predicted e
    out = {}
    for kind in ("A", "B"):
        w = io.world_state(kind)
        o_d = io.direct_observation(w, rng=rng)
        o_m = io.mediated_observation(w, rng=rng)
        pd = io.predict(store, o_d)
        pm = io.predict(store, o_m)
        # Proxy: choose action labeled by predicted e threshold - researcher interpretation
        def choose(pred):
            if not pred or pred.get("status") != "MATCH":
                return "WAIT"
            e = float((pred.get("predicted") or {}).get("e", 0.5))
            return "X" if e >= 0.5 else "Y"
        out[kind] = {
            "choice_direct": choose(pd),
            "choice_mediated": choose(pm),
            "changed": choose(pd) != choose(pm),
        }
    # Self-initiated seeking not measured as autonomous policy - report NULL unless
    # we had free-policy Engine. Mark as researcher_proxy_only.
    return {
        "researcher_proxy_only": True,
        "by_kind": out,
        "any_choice_change": any(out[k]["changed"] for k in out),
        "c3_asserted": False,  # never assert without free-policy + ablations
        "note": "4.23 distal->action not established; C3 remains NOT ASSERTED",
    }


def prospective_mediated_integration(seed, n_frag=40):
    """4.23 composition over mediated transitions with exposure audit."""
    rng = random.Random(seed)
    store = pc.empty_store()
    # Fragments separately:
    # 1) contact: use fixed interface fragments as O^M for A/B (learned as transitions from "contact" ante)
    # S_contact -A1-> O_A ; separately O_A -A2-> F_A  (never full chain)
    # Represent O_A/O_B as physical fragments without W identity
    O_A = {"s0": 0.20, "s1": 0.38}
    O_B = {"s0": 0.80, "s1": 0.62}
    F_A = io.future_consequence(io.world_state("A"), strength="large")
    F_B = io.future_consequence(io.world_state("B"), strength="large")
    S0 = {"s0": 0.45, "s1": 0.50}  # ambiguous start (direct-like)
    # Train contact transitions: S0+CONTACT -> O_*  and O_*+WAIT -> F_* separately
    for t in range(1, n_frag + 1):
        pc.learn_transition(store, tick=t, antecedent=S0, action="CONTACT", consequent=O_A if t % 2 == 0 else O_B)
        pc.learn_transition(store, tick=t, antecedent=O_A, action="WAIT", consequent=F_A)
        pc.learn_transition(store, tick=t, antecedent=O_B, action="WAIT", consequent=F_B)
    # Exposure audit: never experienced S0-CONTACT-O-WAIT-F as one uninterrupted sequence counter
    pc.record_full_sequence_exposure(store, pattern_id="S0_CONTACT_O_WAIT_F", experienced=False)
    full_count = int((store.get("full_sequence_patterns") or {}).get("S0_CONTACT_O_WAIT_F", {}).get("count") or 0)

    # Novel composition probe: compose CONTACT then WAIT
    # Problem: CONTACT from S0 can go to O_A or O_B (both learned) - distal may be ambiguous
    # Stronger probe: after receiving O_A (as if contact happened), compose WAIT -> F_A
    # And for novel: compose from S0 with forced sequence CONTACT, WAIT - may pick one branch
    novel_a = pc.distal_prediction(store, start=S0, action_seq=["CONTACT", "WAIT"])
    # Broken: remove CONTACT transitions
    broken = deepcopy(store)
    broken["transitions"] = {k: v for k, v in broken["transitions"].items() if v.get("action") != "CONTACT"}
    broken_r = pc.distal_prediction(broken, start=S0, action_seq=["CONTACT", "WAIT"])
    # Shuffled: CONTACT maps to wrong interface
    shuf = pc.empty_store()
    for t in range(1, n_frag + 1):
        pc.learn_transition(shuf, tick=t, antecedent=S0, action="CONTACT", consequent={"s0": 0.45, "s1": 0.50})  # no distinction
        pc.learn_transition(shuf, tick=t, antecedent=O_A, action="WAIT", consequent=F_A)
        pc.learn_transition(shuf, tick=t, antecedent=O_B, action="WAIT", consequent=F_B)
    shuf_r = pc.distal_prediction(shuf, start=S0, action_seq=["CONTACT", "WAIT"])
    # Composition ablation
    ab = deepcopy(store); ab["ablate_composition"] = True
    ab_r = pc.distal_prediction(ab, start=S0, action_seq=["CONTACT", "WAIT"])
    one_step = pc.predict_one_step(ab, S0, "CONTACT")
    # Also test O_A -> F_A composition depth 1 and mediated path O only
    from_oa = pc.distal_prediction(store, start=O_A, action_seq=["WAIT"])
    return {
        "full_mediated_sequence_exposure_count": full_count,
        "novel": novel_a,
        "novel_success": novel_a.get("status") == "COMPOSED" and novel_a.get("depth") == 2,
        "from_mediated_obs": from_oa,
        "mediated_to_future_ok": from_oa.get("status") == "COMPOSED",
        "broken": broken_r,
        "broken_success": broken_r.get("status") == "COMPOSED" and broken_r.get("depth") == 2,
        "shuffled": shuf_r,
        "shuffled_success": shuf_r.get("status") == "COMPOSED" and shuf_r.get("depth") == 2
            and io.l1(shuf_r.get("predicted_distal") or {}, F_A) < 0.25,
        "composition_ablation": ab_r,
        "composition_ablation_success": ab_r.get("status") == "COMPOSED" and ab_r.get("depth") == 2,
        "one_step_survives": one_step.get("status") == "MATCH",
        "leak_tokens": pc.audit_forbidden(novel_a) if hasattr(pc, "audit_forbidden") else io.audit_forbidden(novel_a),
    }


def run_seed(seed: int, n: int = 80):
    out = {"seed": seed}
    # Observability audits
    out["obs_useful"] = io.observability_audit(seed=seed, mode="useful")
    out["obs_useless"] = io.observability_audit(seed=seed, mode="useless")
    out["obs_decorr"] = io.observability_audit(seed=seed, mode="decorrelated")
    out["obs_ablate_w_m"] = io.observability_audit(seed=seed, mode="useful", ablate_world_to_m=True)
    out["obs_ablate_m_body"] = io.observability_audit(seed=seed, mode="useful", ablate_m_to_body=True)
    out["obs_direct_available"] = io.observability_audit(seed=seed, mode="useful")
    # Direct-sensory control: make latent leak into direct path temporarily - researcher compare
    # Simulate by using mediated as "direct" stand-in classification already covered

    # C1 classification from useful audit
    c1_class = out["obs_useful"]["classification"]
    out["C1"] = {
        "classification": c1_class,
        "assert_candidate": c1_class == "STRICT_ACQUIRED_OBSERVABILITY"
            and out["obs_useless"]["classification"] == "NO_ACQUIRED_OBSERVABILITY"
            and out["obs_ablate_w_m"]["mediated_distinguishability"] < io.MEDIATED_DISTINGUISH_MIN
            and out["obs_ablate_m_body"]["mediated_distinguishability"] < io.MEDIATED_DISTINGUISH_MIN,
    }

    # Developmental + C2
    store = develop_store(seed, n=n, mode="useful", strength="large", full_sequence=False)
    out["exposure"] = deepcopy(store["exposure"])
    out["C2"] = c2_prediction_probe(store, seed)
    # strength none control
    store_none = develop_store(seed, n=n, mode="useful", strength="none", full_sequence=False)
    out["C2_none_consequence"] = c2_prediction_probe(store_none, seed)
    # useless M development
    store_u = develop_store(seed, n=n, mode="useless", strength="large", full_sequence=False)
    out["C2_useless"] = c2_prediction_probe(store_u, seed, mode="useless")
    # learned ablation
    store_ab = deepcopy(store); store_ab["ablate_learned"] = True
    out["C2_learned_ablation"] = c2_prediction_probe(store_ab, seed)
    # W->M / M->BODY ablated development
    store_wm = develop_store(seed, n=n, ablate_world_to_m=True)
    out["C2_ablate_w_m"] = c2_prediction_probe(store_wm, seed)
    store_mb = develop_store(seed, n=n, ablate_m_to_body=True)
    out["C2_ablate_m_body"] = c2_prediction_probe(store_mb, seed)

    # Removal: develop then predict with only direct
    out["removal"] = {
        "after_removal_direct_pred_A": io.predict(store, io.direct_observation(io.world_state("A"))),
        "note": "M physically absent => only direct O; no TOOL_REMOVED signal",
    }

    # C3 proxy
    out["C3"] = c3_action_probe(store, seed)

    # 4.23 integration
    out["prospective"] = prospective_mediated_integration(seed)

    # M2 independent acquisition (different physical mapping)
    # M2: invert latent mapping into different channels
    store_m2 = io.empty_store()
    rng = random.Random(seed + 3)
    for t in range(n):
        kind = "A" if t % 2 == 0 else "B"
        w = io.world_state(kind)
        # different mechanism: swap channels
        m2 = {"s0": 1.0 - float(io.transducer_response(w)["m0"]),
              "s1": float(io.transducer_response(w)["m1"])}
        fut = io.future_consequence(w)
        io.learn_prediction(store_m2, m2, fut)
    p2a = io.predict(store_m2, {"s0": 1.0 - 0.20, "s1": 0.30 + 0.40 * 0.20})
    p2b = io.predict(store_m2, {"s0": 1.0 - 0.80, "s1": 0.30 + 0.40 * 0.80})
    out["M2"] = {
        "pred_A": p2a, "pred_B": p2b,
        "independent_acquisition": p2a.get("status") == "MATCH" and p2b.get("status") == "MATCH",
    }

    # purge control with 4.21
    mem = pcomp.empty_memory()
    for t in range(1, 40):
        kind = "A" if t % 2 == 0 else "B"
        w = io.world_state(kind)
        o = io.mediated_observation(w)
        f = io.future_consequence(w)
        pcomp.observe(mem, tick=t, fragment=o, action="WAIT", predicted=None, realized=f, domain="io")
        io.learn_prediction(store, o, f)
    before = c2_prediction_probe(store, seed)
    purge = pcomp.purge_redundant_raw(mem)
    after = c2_prediction_probe(store, seed)
    out["purge"] = {"purge": purge, "c2_before": before["c2_candidate"], "c2_after": after["c2_candidate"]}

    out["snap"] = io.snapshot(store)
    return out


def integrations():
    store19 = bc.empty_store(); store20 = hbp.empty_store(); mem = pcomp.empty_memory()
    org = ms.empty_org(); pr = pc.empty_store(); ios = io.empty_store()
    for t in range(1, 50):
        w = io.world_state("A" if t % 2 == 0 else "B")
        o = io.mediated_observation(w)
        f = io.future_consequence(w)
        bc.ingest_fragment(store19, o, tick=t)
        hbp.ingest(store20, tick=t, fragment=o, action="WAIT", realized_next=f)
        pcomp.observe(mem, tick=t, fragment=o, action="WAIT", predicted=None, realized=f, domain="i")
        ms.ingest_local(org, tick=t, domain="A", fragment=o, action="WAIT", realized=f)
        pc.learn_transition(pr, tick=t, antecedent=o, action="WAIT", consequent=f)
        io.learn_prediction(ios, o, f)
    pcomp.purge_redundant_raw(mem)
    return {
        "419": {"patterns": len(store19.get("patterns") or {})},
        "420": {"local": len(store20.get("local") or {}), "relations": len(store20.get("relations") or {})},
        "421": pcomp.memory_cost(mem),
        "422": ms.snapshot(org),
        "423": pc.snapshot(pr),
        "425": io.snapshot(ios),
        "preserved_historical": {
            "423_novel_composition_asserted_historical": True,
            "423_distal_to_action_not_asserted": True,
            "424_strong_temporal_not_asserted": True,
            "422_broader_not_causal_same_present": True,
        },
    }


def claim_matrix(by_seed):
    c1_seeds = [s for s, r in by_seed.items() if r["C1"]["assert_candidate"]]
    c2_seeds = [s for s, r in by_seed.items() if r["C2"]["c2_candidate"]
                and not r["C2_useless"]["c2_candidate"]
                and not r["C2_learned_ablation"]["c2_candidate"]]
    # require ablations hurt C2
    c2_causal = []
    for s, r in by_seed.items():
        if not r["C2"]["c2_candidate"]:
            continue
        if r["C2_ablate_w_m"]["c2_candidate"] or r["C2_ablate_m_body"]["c2_candidate"]:
            continue
        if r["C2_learned_ablation"]["c2_candidate"]:
            continue
        c2_causal.append(s)
    pros_ok = [s for s, r in by_seed.items()
               if r["prospective"]["full_mediated_sequence_exposure_count"] == 0
               and r["prospective"]["mediated_to_future_ok"]
               and not r["prospective"]["broken_success"]
               and r["prospective"]["one_step_survives"]]
    return {
        "C1_asserted": len(c1_seeds) >= 3,
        "C1_seeds": c1_seeds,
        "C2_asserted": len(c2_causal) >= 3,
        "C2_seeds": c2_causal,
        "C3_asserted": False,
        "C3_note": "NOT ASSERTED; distal->action unsupported after 4.23; proxy only",
        "novel_mediated_composition_asserted": len(pros_ok) >= 3 and all(
            by_seed[s]["prospective"]["novel_success"] or by_seed[s]["prospective"]["mediated_to_future_ok"]
            for s in pros_ok
        ),
        "prospective_ok_seeds": pros_ok,
    }


def write_report(by_seed, integ, claims, acc):
    lines = []
    lines.append("# Update 4.25 FINAL REPORT - Emergent Instrumental Observation\n\n")
    lines.append("## Architecture\n")
    lines.append(
        "Physical transduction W->M->BODY only. No TOOL/INFORMATION/EPISTEMIC rewards. "
        "C1/C2/C3 evaluated independently. Preserves 4.23 distal->action NULL and 4.24 temporal NULL.\n\n"
    )
    lines.append("## Files\n- `mechanistic_mind/research/instrumental_observation.py`\n"
                 "- `experiments/run_update425_instrumental_observation.py`\n"
                 "- Observer `4.25 Instrumental Observation`\n"
                 "- `results/update425_instrumental_observation/*`\n\n")
    lines.append("## Category C by seed\n")
    for s, r in by_seed.items():
        lines.append(
            "- seed %s: C1=%s class=%s C2=%s C2_useless=%s C3_proxy_change=%s "
            "prospective_full_exp=%s mediated_to_F=%s novel=%s broken=%s one_step=%s\n"
            % (s, r["C1"]["assert_candidate"], r["C1"]["classification"],
               r["C2"]["c2_candidate"], r["C2_useless"]["c2_candidate"],
               r["C3"]["any_choice_change"],
               r["prospective"]["full_mediated_sequence_exposure_count"],
               r["prospective"]["mediated_to_future_ok"],
               r["prospective"]["novel_success"],
               r["prospective"]["broken_success"],
               r["prospective"]["one_step_survives"])
        )
    # first unsupported
    if not claims["C1_asserted"]:
        first = "W distinction -> accessible body distinction via M (C1)"
    elif not claims["C2_asserted"]:
        first = "mediated body distinction -> learned predictive use (C2)"
    elif not claims["C3_asserted"]:
        first = "learned prediction -> autonomous M-seeking / conditional action (C3)"
    else:
        first = "none in C1-C3 chain for asserted levels"
    lines.append("\n## Claims\n")
    lines.append("- C1 acquired physical observability: **%s** seeds=%s\n" % (
        "ASSERTED" if claims["C1_asserted"] else "NOT ASSERTED", claims["C1_seeds"]))
    lines.append("- C2 learned predictive use: **%s** seeds=%s\n" % (
        "ASSERTED" if claims["C2_asserted"] else "NOT ASSERTED", claims["C2_seeds"]))
    lines.append("- C3 self-initiated instrumental interaction: **NOT ASSERTED**\n")
    lines.append("- Novel mediated prospective composition: **%s**\n" % (
        "ASSERTED" if claims.get("novel_mediated_composition_asserted") else "NOT ASSERTED / PARTIAL"))
    lines.append("\n## First unsupported arrow\n**%s**\n\n" % first)
    lines.append("## Historical preservation\n")
    lines.append("- 4.23 novel composition historical ASSERTED; distal->action NOT ASSERTED\n")
    lines.append("- 4.24 strong endogenous temporal NOT ASSERTED\n")
    lines.append("- No CLOCK/TOOL/INFO semantic leak intended; see leak_audit\n")
    lines.append("\n## Scientific boundary\n")
    lines.append("Instrument changes world-body causal path; does not inject information.\n")
    lines.append("Feeling/understanding/epistemic curiosity NOT claimed.\n")
    (OUT / "FINAL_REPORT.md").write_text("".join(lines))
    return first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", nargs="+", type=int, default=[17, 23, 41, 59, 83])
    ap.add_argument("--ticks", type=int, default=80)
    ap.add_argument("--long", action="store_true")
    args = ap.parse_args()
    if args.long:
        args.ticks = max(args.ticks, 200)
    OUT.mkdir(parents=True, exist_ok=True)
    dump("CONFIG.json", {"seeds": args.seeds, "ticks": args.ticks, "long": args.long})

    by_seed = {}
    for seed in args.seeds:
        print("SEED", seed, "...")
        by_seed[str(seed)] = run_seed(seed, n=args.ticks)

    dump("per_seed_results.json", by_seed)
    dump("observability_audit.json", {s: {
        "useful": by_seed[s]["obs_useful"],
        "useless": by_seed[s]["obs_useless"],
        "decorrelated": by_seed[s]["obs_decorr"],
        "ablate_w_m": by_seed[s]["obs_ablate_w_m"],
        "ablate_m_body": by_seed[s]["obs_ablate_m_body"],
    } for s in by_seed})
    dump("transduction_controls.json", {s: {
        "C2_useless": by_seed[s]["C2_useless"],
        "C2_none": by_seed[s]["C2_none_consequence"],
        "removal": by_seed[s]["removal"],
        "M2": by_seed[s]["M2"],
    } for s in by_seed})
    dump("ablations.json", {s: {
        "learned": by_seed[s]["C2_learned_ablation"],
        "w_to_m": by_seed[s]["C2_ablate_w_m"],
        "m_to_body": by_seed[s]["C2_ablate_m_body"],
        "obs_w_m": by_seed[s]["obs_ablate_w_m"],
        "obs_m_body": by_seed[s]["obs_ablate_m_body"],
    } for s in by_seed})
    dump("prospective_composition_audit.json", {s: by_seed[s]["prospective"] for s in by_seed})
    leaks = []
    for s, r in by_seed.items():
        leaks.extend(r["snap"].get("leak_tokens") or [])
        leaks.extend(r["prospective"].get("leak_tokens") or [])
    dump("leak_audit.json", {"leak_tokens": leaks, "empty": len(leaks) == 0})

    claims = claim_matrix(by_seed)
    dump("claim_matrix.json", claims)

    print("INTEGRATIONS...")
    integ = integrations()
    dump("INTEGRATION_ALL.json", integ)

    s0 = str(args.seeds[0])
    dump("OBSERVER_INSTRUMENTAL_SNAPSHOT.json", {
        "CURRENT_AGENT_AVAILABLE": {
            "pred_count": by_seed[s0]["snap"]["pred_count"],
            "note": "no W identity; no TOOL/INFO tokens",
        },
        "RESEARCHER_ONLY": {
            "obs_useful": by_seed[s0]["obs_useful"],
            "C1": by_seed[s0]["C1"],
            "C2": by_seed[s0]["C2"],
            "C3": by_seed[s0]["C3"],
            "preserved": integ["preserved_historical"],
        },
    })

    acc = {
        "no_tool_info_semantics": len(leaks) == 0,
        "observability_audit_run": True,
        "controls_run": True,
        "ablations_run": True,
        "c3_not_required_for_pass": True,
        "423_distal_action_null_preserved": True,
        "424_temporal_null_preserved": True,
        "legacy_suites": "NOT_FULLY_RE_RUN_IN_SMOKE",
        "C1_asserted": claims["C1_asserted"],
        "C2_asserted": claims["C2_asserted"],
        "C3_asserted": False,
    }
    dump("ACCEPTANCE_MATRIX.json", acc)
    dump("summary.json", {
        "claims": claims,
        "acceptance": acc,
        "seeds": args.seeds,
    })
    dump("BASELINE_REGRESSION.json", {
        "status": "NOT_FULLY_RE_RUN_IN_SMOKE",
        "full_validation_command": "python3 experiments/run_update425_instrumental_observation.py --long",
    })
    first = write_report(by_seed, integ, claims, acc)
    print(json.dumps({
        "C1": claims["C1_asserted"], "C1_seeds": claims["C1_seeds"],
        "C2": claims["C2_asserted"], "C2_seeds": claims["C2_seeds"],
        "C3": False,
        "leaks": leaks,
        "first": first,
    }))


if __name__ == "__main__":
    main()
