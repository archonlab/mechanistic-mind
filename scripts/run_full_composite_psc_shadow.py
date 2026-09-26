#!/usr/bin/env python3
"""Wet-world FULL COMPOSITE PSC SHADOW REPLAY (observational; no production change)."""
from __future__ import annotations

import json
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from mechanistic_mind.ui.psy_observer_web.session import ObserverSession, SessionConfig
from mechanistic_mind.physical_system.full_composite_psc_shadow import (
    REUSED_PRODUCTION,
    replay_tick,
    support_proxy_class_from_prior,
)
from mechanistic_mind.physical_system import psc_motor_resolution_shadow as prior_shadow
from mechanistic_mind.physical_system import sensorimotor_consequence as smc

OUT = Path("results/full_composite_psc_shadow")
SEED = 111
PHASE_A = 150  # PSC OFF
PHASE_B = 100  # PSC ON
ADAPTIVE_THRESHOLDS = [0.01, 0.02, 0.05]


def _pct(vals):
    if not vals:
        return {"mean": None, "p50": None, "p95": None, "max": None, "n": 0}
    s = sorted(vals)
    def p(q):
        if not s:
            return None
        i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
        return s[i]
    return {
        "mean": round(sum(s) / len(s), 6),
        "p50": round(p(0.50), 6),
        "p95": round(p(0.95), 6),
        "max": round(s[-1], 6),
        "n": len(s),
    }


def _traj_motors(n_steps: int, shadow: bool, phase_a: int, phase_b: int):
    s = ObserverSession(SessionConfig(seed=SEED, evidence_mode="SEARCH_COMPACT"))
    s.apply_experiment({"seed": SEED, "agent_count": 2})
    s.set_observer_detail_preset("MINIMAL")
    for mech in [
        "sensorimotor_consequence_model",
        "sensorimotor_consequence_bilateral",
        "historical_sensorimotor_selection_bridge",
        "prospective_composition",
        "composite_motor",
        "retrieval",
    ]:
        try:
            s.set_mechanism(mech, True)
        except Exception:
            pass
    s.set_mechanism("prospective_scenario_competition", False)
    motors = []
    observations = []
    for i in range(phase_a + phase_b):
        if i == phase_a:
            s.set_mechanism("prospective_scenario_competition", True)
        s.step()
        slot = s.runtime.slots[0]
        cog = slot.cognition
        motor = cog.get("last_motor_output")
        motors.append(json.dumps(motor, sort_keys=True, default=str))
        if shadow and i >= phase_a:
            store = cog.get("sensorimotor_consequence") or {}
            prosp = cog.get("prospection") or {}
            comp = cog.get("compression")
            obs = slot.agent_observation(foreign_bodies=s.runtime.foreign_bodies_for(0))
            obs_f = {k: float(v) for k, v in (obs or {}).items() if isinstance(v, (int, float))}
            ls = cog.get("last_selection") or {}
            locos = list(ls.get("select_actions") or ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"])
            prod_loco = (motor or {}).get("locomotion") or ls.get("action")
            replay_tick(
                observation=obs_f,
                smc_store=store,
                prospection=prosp,
                compression=comp,
                loco_candidates=locos,
                seed=SEED,
                tick=int(s.runtime.tick),
                production_selected_loco=prod_loco,
                production_realized_motor=motor,
                run_adaptive=False,
            )
        observations.append(json.dumps(
            {k: slot.cognition.get(k) for k in ("last_selection",) },
            sort_keys=True, default=str,
        )[:200])
    return motors


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    t_wall0 = time.perf_counter()

    # EXACT_MATCH paired
    m_off = _traj_motors(PHASE_A + PHASE_B, shadow=False, phase_a=PHASE_A, phase_b=PHASE_B)
    m_on = _traj_motors(PHASE_A + PHASE_B, shadow=True, phase_a=PHASE_A, phase_b=PHASE_B)
    exact = m_off == m_on
    exact_match = {
        "SHADOW_EXACT_MATCH": exact,
        "n_ticks_compared": len(m_off),
        "first_divergence_index": next((i for i, (a, b) in enumerate(zip(m_off, m_on)) if a != b), None),
    }
    (OUT / "exact_match.json").write_text(json.dumps(exact_match, indent=2))
    if not exact:
        print("STOP: SHADOW_EXACT_MATCH failed", exact_match)
        return 2

    # Main wet replay
    s = ObserverSession(SessionConfig(seed=SEED, evidence_mode="SEARCH_COMPACT"))
    s.apply_experiment({"seed": SEED, "agent_count": 2})
    s.set_observer_detail_preset("MINIMAL")
    for mech in [
        "sensorimotor_consequence_model",
        "sensorimotor_consequence_bilateral",
        "historical_sensorimotor_selection_bridge",
        "prospective_composition",
        "composite_motor",
        "retrieval",
    ]:
        try:
            s.set_mechanism(mech, True)
        except Exception:
            pass

    log_path = OUT / "replay_log.jsonl"
    if log_path.exists():
        log_path.unlink()

    class_counts = Counter()
    funnel = Counter()
    motor_attr = Counter()
    sensory_first = Counter()
    perf_full = []
    perf_adapt = {th: [] for th in ADAPTIVE_THRESHOLDS}
    cand_full = []
    cand_adapt = {th: [] for th in ADAPTIVE_THRESHOLDS}
    proxy_vs_real = []
    developmental = []
    no_vision = []
    forensics = {"SAME_LOCOMOTION_SAME_COMPOSITE": None, "SAME_LOCOMOTION_DIFFERENT_COMPOSITE": None,
                 "DIFFERENT_LOCOMOTION": None, "NO_VISION_DIFFERENCE": None}
    adaptive_agree = {th: Counter() for th in ADAPTIVE_THRESHOLDS}

    s.set_mechanism("prospective_scenario_competition", False)
    for i in range(PHASE_A + PHASE_B):
        phase = "pre_psc" if i < PHASE_A else "psc_on"
        if i == PHASE_A:
            s.set_mechanism("prospective_scenario_competition", True)
        s.step()
        if i < PHASE_A:
            continue

        slot = s.runtime.slots[0]
        cog = slot.cognition
        store = cog.get("sensorimotor_consequence") or {}
        prosp = cog.get("prospection") or {}
        comp = cog.get("compression")
        obs = slot.agent_observation(foreign_bodies=s.runtime.foreign_bodies_for(0))
        obs_f = {k: float(v) for k, v in (obs or {}).items() if isinstance(v, (int, float))}
        ls = cog.get("last_selection") or {}
        locos = list(ls.get("select_actions") or ["WAIT", "MOVE:N", "MOVE:S", "MOVE:E", "MOVE:W"])
        motor = cog.get("last_motor_output")
        prod_loco = (motor or {}).get("locomotion") or ls.get("action")
        tick = int(s.runtime.tick)

        funnel["PSC_COMPETITIONS"] += 1

        # Prior support-proxy for confusion matrix
        prior = prior_shadow.shadow_tick(
            store, obs_f, locos, tick=tick, production_selected_loco=prod_loco,
        )
        proxy_class = support_proxy_class_from_prior(prior)

        rep = replay_tick(
            observation=obs_f,
            smc_store=store,
            prospection=prosp,
            compression=comp,
            loco_candidates=locos,
            seed=SEED,
            tick=tick,
            production_selected_loco=prod_loco,
            production_realized_motor=motor,
            divergence_refine_threshold=0.02,
            run_adaptive=True,
        )
        cls = rep["classification"]
        class_counts[cls] += 1
        fc = rep["full_composite"]
        funnel["COMPOSITE_CANDIDATES_AVAILABLE"] += int(fc.get("n_candidates_built") or 0)
        if int(fc.get("multi_composite_within_loco") or 0) > 0:
            funnel["MULTI_COMPOSITE_WITHIN_LOCO"] += 1
        funnel["COMPOSITE_EXACT_SMC_PREDICTIONS"] += int(fc.get("exact_smc_predictions") or 0)
        if int(fc.get("o_prime_differentiated_loco_branches") or 0) > 0:
            funnel["COMPOSITE_O_PRIME_DIFFERENTIATED"] += 1
        if fc.get("history_support_differentiated"):
            funnel["COMPOSITE_HISTORY_SUPPORT_DIFFERENTIATED"] += 1
        if int(fc.get("n_scenarios") or 0) > 0:
            funnel["COMPOSITE_HISTORY_QUERIED"] += 1
            funnel["COMPOSITE_EVIDENCE_AVAILABLE_TO_PSC"] += 1
            funnel["FULL_COMPETE_SCENARIOS_REPLAYED"] += 1
        funnel[cls] += 1
        perf_full.append(float(rep.get("elapsed_ms") or 0))
        cand_full.append(int(fc.get("n_actions") or 0))

        # motor / sensory attribution on differences
        if cls in {"SAME_LOCOMOTION_DIFFERENT_COMPOSITE", "DIFFERENT_LOCOMOTION"}:
            md = rep.get("motor_dimension_attribution") or {}
            for k in ("contains_neck", "contains_osc_emit", "contains_osc_freq", "contains_osc_amp", "contains_push"):
                if md.get(k):
                    motor_attr[k] += 1
            if md.get("single_dimension"):
                motor_attr[f"single_{md.get('single_dimension_name')}"] += 1
            sf = rep.get("sensory_family_attribution") or {}
            fams = (sf.get("families") or {}) if isinstance(sf, dict) else {}
            if fams:
                top = max(fams.items(), key=lambda kv: float(kv[1]))
                sensory_first[top[0]] += 1

        # no-vision subset: exo optical near-zero but bilateral/field present
        exo = sum(abs(float(obs_f.get(k, 0.0))) for k in ("exo_0", "exo_1", "exo_2"))
        bil = sum(abs(float(obs_f.get(f"osc_l_{i}", 0.0)) + float(obs_f.get(f"osc_r_{i}", 0.0))) for i in range(6))
        field = abs(float(obs_f.get("local.FIELD_A", 0.0))) + abs(float(obs_f.get("local.FIELD_B", 0.0)))
        if exo < 1e-6 and (bil > 1e-6 or field > 1e-6):
            no_vision.append({
                "tick": tick,
                "classification": cls,
                "bilateral_energy": bil,
                "field_energy": field,
                "shadow_sig": fc.get("selected_sig"),
                "production_realized": (rep.get("production") or {}).get("realized_composite_sig"),
            })
            if cls in {"SAME_LOCOMOTION_DIFFERENT_COMPOSITE", "DIFFERENT_LOCOMOTION"} and forensics["NO_VISION_DIFFERENCE"] is None:
                forensics["NO_VISION_DIFFERENCE"] = rep.get("forensic_compact")

        # developmental window
        rel = i - PHASE_A
        if rel < PHASE_B // 4:
            win = "early_psc"
        elif rel < PHASE_B // 2:
            win = "middle_psc"
        else:
            win = "late_psc"
        developmental.append({"tick": tick, "window": win, "classification": cls,
                              "n_cand": fc.get("n_candidates_built"),
                              "multi": fc.get("multi_composite_within_loco")})

        # proxy vs real
        real_bin = "DIFFERENT_LOCOMOTION" if cls == "DIFFERENT_LOCOMOTION" else "SAME_LOCOMOTION"
        proxy_bin = "DIFFERENT_LOCOMOTION" if proxy_class == "DIFFERENT_LOCOMOTION" else "SAME_LOCOMOTION"
        proxy_vs_real.append({"tick": tick, "proxy_class": proxy_class, "real_class": cls,
                              "proxy_bin": proxy_bin, "real_bin": real_bin})

        # forensics one of each
        if forensics.get(cls) is None and cls in forensics:
            forensics[cls] = {
                "tick": tick,
                "compact": rep.get("forensic_compact"),
                "earliest_divergence": rep.get("earliest_divergence"),
                "motor_dimension_attribution": rep.get("motor_dimension_attribution"),
                "sensory_family_attribution": rep.get("sensory_family_attribution"),
                "production": rep.get("production"),
                "full_composite": {k: fc.get(k) for k in (
                    "selected", "selected_loco", "selected_sig", "n_scenarios", "compete_outcome")},
            }

        # Adaptive frontier (subsample ticks; default 0.02 already in main rep)
        if (i - PHASE_A) % 5 == 0:
            for th in ADAPTIVE_THRESHOLDS:
                r2 = replay_tick(
                    observation=obs_f,
                    smc_store=store,
                    prospection=prosp,
                    compression=comp,
                    loco_candidates=locos,
                    seed=SEED,
                    tick=tick,
                    production_selected_loco=prod_loco,
                    production_realized_motor=motor,
                    divergence_refine_threshold=th,
                    run_adaptive=True,
                )
                perf_adapt[th].append(float(r2.get("elapsed_ms") or 0))
                cand_adapt[th].append(int((r2.get("adaptive") or {}).get("n_candidates") or 0))
                vs = (r2.get("adaptive") or {}).get("vs_full_composite") or {}
                if vs.get("same_locomotion"):
                    adaptive_agree[th]["loco_agree"] += 1
                if vs.get("same_composite"):
                    adaptive_agree[th]["composite_agree"] += 1
                if vs.get("same_classification"):
                    adaptive_agree[th]["class_agree"] += 1
                adaptive_agree[th]["n"] += 1
        # also fold default-threshold adaptive from main rep into 0.02 bucket when present
        if 0.02 in ADAPTIVE_THRESHOLDS and (i - PHASE_A) % 5 != 0:
            vs = (rep.get("adaptive") or {}).get("vs_full_composite") or {}
            th = 0.02
            perf_adapt[th].append(float(rep.get("elapsed_ms") or 0))
            cand_adapt[th].append(int((rep.get("adaptive") or {}).get("n_candidates") or 0))
            if vs.get("same_locomotion"):
                adaptive_agree[th]["loco_agree"] += 1
            if vs.get("same_composite"):
                adaptive_agree[th]["composite_agree"] += 1
            if vs.get("same_classification"):
                adaptive_agree[th]["class_agree"] += 1
            adaptive_agree[th]["n"] += 1

        with log_path.open("a") as f:
            f.write(json.dumps({
                "tick": tick,
                "classification": cls,
                "proxy_class": proxy_class,
                "full": fc,
                "adaptive": rep.get("adaptive"),
                "mutation_ok": (rep.get("mutation_audit") or {}).get("smc_counters_unchanged"),
                "elapsed_ms": rep.get("elapsed_ms"),
            }, default=str) + "\n")

    n_replayed = max(1, funnel["FULL_COMPETE_SCENARIOS_REPLAYED"])
    # confusion matrix
    cm = Counter()
    for row in proxy_vs_real:
        cm[(row["proxy_bin"], row["real_bin"])] += 1
    tp = cm[("DIFFERENT_LOCOMOTION", "DIFFERENT_LOCOMOTION")]
    fp = cm[("DIFFERENT_LOCOMOTION", "SAME_LOCOMOTION")]
    fn = cm[("SAME_LOCOMOTION", "DIFFERENT_LOCOMOTION")]
    tn = cm[("SAME_LOCOMOTION", "SAME_LOCOMOTION")]
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    agreement = (tp + tn) / max(1, tp + tn + fp + fn)

    # developmental aggregate
    dev_agg = defaultdict(Counter)
    for row in developmental:
        dev_agg[row["window"]][row["classification"]] += 1

    frontier = []
    for th in ADAPTIVE_THRESHOLDS:
        n = max(1, adaptive_agree[th]["n"])
        frontier.append({
            "threshold": th,
            "locomotion_agreement": adaptive_agree[th]["loco_agree"] / n,
            "composite_agreement": adaptive_agree[th]["composite_agree"] / n,
            "classification_agreement": adaptive_agree[th]["class_agree"] / n,
            "candidate_count": _pct(cand_adapt[th]),
            "runtime_ms": _pct(perf_adapt[th]),
            "full_candidate_count": _pct(cand_full),
            "candidate_reduction_mean": (
                (sum(cand_full) / n - sum(cand_adapt[th]) / n) if n else None
            ),
        })

    summary = {
        "schema": "mm.full_composite_psc_shadow.replay_summary.v1",
        "seed": SEED,
        "phase_a_psc_off": PHASE_A,
        "phase_b_psc_on": PHASE_B,
        "SHADOW_EXACT_MATCH": exact,
        "reused_production_functions": REUSED_PRODUCTION,
        "class_counts": dict(class_counts),
        "funnel": dict(funnel),
        "different_locomotion_rate": class_counts["DIFFERENT_LOCOMOTION"] / n_replayed,
        "same_loco_different_composite_rate": class_counts["SAME_LOCOMOTION_DIFFERENT_COMPOSITE"] / n_replayed,
        "elapsed_s": round(time.perf_counter() - t_wall0, 3),
        "analysis_only": True,
        "does_not_affect_agent": True,
        "claim_boundary": "architectural sensitivity only; not better/smarter behavior",
    }
    (OUT / "replay_summary.json").write_text(json.dumps(summary, indent=2))
    (OUT / "funnel.json").write_text(json.dumps(dict(funnel), indent=2))
    (OUT / "classifications.json").write_text(json.dumps(dict(class_counts), indent=2))
    (OUT / "proxy_vs_real.json").write_text(json.dumps({
        "prior_proxy_note": "previous support-proxy DIFFERENT_LOCOMOTION=52/200 was upper-bound diagnostic",
        "confusion_matrix": {
            "proxy_DIFF_real_DIFF": tp,
            "proxy_DIFF_real_SAME": fp,
            "proxy_SAME_real_DIFF": fn,
            "proxy_SAME_real_SAME": tn,
        },
        "precision_proxy_for_real_diff_loco": precision,
        "recall_proxy_for_real_diff_loco": recall,
        "agreement": agreement,
        "n": len(proxy_vs_real),
        "rows_sample": proxy_vs_real[:20],
    }, indent=2))
    (OUT / "motor_dimension_attribution.json").write_text(json.dumps(dict(motor_attr), indent=2))
    (OUT / "sensory_family_attribution.json").write_text(json.dumps(dict(sensory_first), indent=2))
    (OUT / "developmental_windows.json").write_text(json.dumps({k: dict(v) for k, v in dev_agg.items()}, indent=2))
    (OUT / "no_vision_subset.json").write_text(json.dumps({
        "n": len(no_vision),
        "class_counts": dict(Counter(r["classification"] for r in no_vision)),
        "rows": no_vision[:50],
    }, indent=2))
    (OUT / "adaptive_frontier.json").write_text(json.dumps(frontier, indent=2))
    (OUT / "performance.json").write_text(json.dumps({
        "full_composite_ms": _pct(perf_full),
        "adaptive_ms_by_threshold": {str(th): _pct(perf_adapt[th]) for th in ADAPTIVE_THRESHOLDS},
        "full_candidate_counts": _pct(cand_full),
        "adaptive_candidate_counts_by_threshold": {str(th): _pct(cand_adapt[th]) for th in ADAPTIVE_THRESHOLDS},
    }, indent=2))
    (OUT / "forensics.json").write_text(json.dumps(forensics, indent=2, default=str))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
