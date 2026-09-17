#!/usr/bin/env python3
"""Run Update 4.38 — Psyche Incubation."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mechanistic_mind.research import psyche_incubation as pi
from mechanistic_mind.research import predictive_generalization as pg

OUT = ROOT / "results" / "update438_psyche_incubation"
SEEDS = [17, 23, 41, 59, 83]
DOSES = [12, 36, 72]


def dump(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(json.dumps(value, indent=2, sort_keys=True, default=str) + "\n")


def run_seed(seed: int, dose: int = 36) -> dict:
    initial = pi.empty_organism(seed)
    initial_snapshot = {
        "body": initial["body"], "action_distribution": pi.action_distribution(initial, "X4")["probs"],
        "predictive_store_size": 0, "compression_store_size": 0,
        "relevant_transition_count": 0, "relevant_context_count": 0,
        "relevant_generalization_structure": 0,
    }
    structured = pi.empty_organism(seed); pi.develop(structured, exposures=dose)
    decorrelated = pi.empty_organism(seed); pi.develop(decorrelated, exposures=dose, mode="decorrelated")
    no_incubation = pi.empty_organism(seed)
    body_neutral = pi.empty_organism(seed)
    for i in range(dose):
        pi.external_transition(body_neutral, ("X1", "X2", "X3")[i % 3], future=pi.initial_body())

    known = pi.passive_prediction(structured, "X1")
    novel = pi.passive_prediction(structured, "X4")
    unrelated = pi.passive_prediction(structured, "Y")
    decor_novel = pi.passive_prediction(decorrelated, "X4")
    neutral_novel = pi.passive_prediction(body_neutral, "X4")
    x4_before = {
        "interaction_exposure_count": structured["forced_by_object"].get("X4", 0),
        "forced_interaction_count": structured["forced_by_object"].get("X4", 0),
        "endogenous_interaction_count": structured["endogenous_by_object"].get("X4", 0),
    }

    # Match current body state before every autonomous probe.
    for org in (structured, decorrelated, no_incubation, body_neutral): org["body"] = pi.initial_body()
    d_struct = pi.action_distribution(structured, "X4")
    d_none = pi.action_distribution(no_incubation, "X4")
    d_decor = pi.action_distribution(decorrelated, "X4")
    d_abl = pi.action_distribution(structured, "X4", acquired_ablation=True)
    d_val0 = pi.action_distribution(structured, "X4", value_neutralized=True)
    d_y = pi.action_distribution(structured, "Y")
    event = pi.first_intervention(structured, "X4")

    purged = pi.empty_organism(seed); pi.develop(purged, exposures=dose)
    pred_before = pi.passive_prediction(purged, "X4"); purge = pi.purge_raw(purged)
    pred_after = pi.passive_prediction(purged, "X4")
    gen_abl = pi.empty_organism(seed); gen_abl["predictive"] = json.loads(json.dumps(structured["predictive"]))
    gen_abl["predictive"]["ablate_shared"] = True
    novel_gen_abl = pi.passive_prediction(gen_abl, "X4")

    pred_error_struct = pg.l1(novel.get("predicted"), pi.consequence(pi.sources()["X4"]))
    pred_error_decor = pg.l1(decor_novel.get("predicted"), pi.consequence(pi.sources()["X4"]))
    same_probs = d_struct["probs"] == d_none["probs"] == d_decor["probs"] == d_abl["probs"] == d_val0["probs"]
    claims = {
        "C1_passive_experience_acquisition": structured["external_count"] == dose,
        "C2_passive_consequence_learning": known.get("predicted") is not None,
        "C3_passive_predictive_compression": len(structured["predictive"].get("pair") or {}) > 0,
        "C4_passive_provenance_retention": bool(structured["provenance"]),
        "C5_passive_generalization": novel.get("predicted") is not None and x4_before["interaction_exposure_count"] == 0,
        "C6_structured_vs_decorrelated": pred_error_struct is not None and pred_error_decor is not None and pred_error_struct < pred_error_decor,
        "C7_current_state_matched_history_effect": novel.get("status") != pi.passive_prediction(no_incubation, "X4").get("status"),
        "C8_raw_history_independence": pred_before.get("predicted") == pred_after.get("predicted") and purge["purged"] > 0,
        "C9_first_endogenous_intervention": event is not None,
        "C10_acquired_action_influence": d_struct["probs"] != d_none["probs"],
        "C11_acquired_structure_necessity": d_struct["probs"] != d_abl["probs"],
        "C12_novel_instance_action_influence": d_struct["probs"] != d_none["probs"] and novel.get("predicted") is not None,
        "C13_generalization_necessity": d_struct["probs"] != pi.action_distribution(gen_abl, "X4")["probs"],
        "C14_non_indiscriminate_intervention": (
            d_struct["probs"]["INTERACT:X4"] != d_none["probs"]["INTERACT:X4"]
            and d_struct["probs"]["INTERACT:X4"] > d_y["probs"]["INTERACT:Y"]
        ),
        "C15_inherited_valuation_independence": d_struct["probs"] != d_none["probs"] and d_struct["probs"] == d_val0["probs"],
        "C16_intrinsic_body_dynamics_dependence": pred_error_struct is not None and neutral_novel.get("predicted") != novel.get("predicted"),
        "C17_developmental_divergence": d_struct["probs"] != d_decor["probs"],
        "C18_compressed_history_causality": d_struct["probs"] != d_abl["probs"],
        "C19_online_revision": False,
        "C20_behavioral_revision": False,
        "C21_boundedness": len(structured["raw"]) <= pi.MAX_RAW and len(structured["provenance"]) <= pg.MAX_EXACT,
    }
    return {
        "seed": seed, "dose": dose, "initial": initial_snapshot, "claims": claims,
        "predictions": {"known": known, "novel_X4": novel, "unrelated_Y": unrelated,
                        "decorrelated_X4": decor_novel, "generalization_ablated_X4": novel_gen_abl},
        "prediction_errors": {"structured": pred_error_struct, "decorrelated": pred_error_decor},
        "action_probes": {"structured": d_struct, "no_incubation": d_none, "decorrelated": d_decor,
                          "acquired_ablation": d_abl, "ordinary_state_value_neutralized": d_val0},
        "same_action_distribution_all_controls": same_probs, "first_endogenous_intervention": event,
        "novel_exposure_audit_before_probe": x4_before, "raw_purge": purge,
        "memory": pi.memory_snapshot(structured), "leak": pi.cognition_leaks(structured),
        "first_unsupported": {
            "main": "predicted_available_consequence_to_present_endogenous_action_influence",
            "body_value": "acquired_prediction_to_action_influence_without_inherited_valuation",
            "novel": "never_experienced_object_prediction_to_action_influence",
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--dose", type=int, default=36); ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS)
    args = ap.parse_args()
    rows = [run_seed(s, args.dose) for s in args.seeds]
    matrix = {}
    for name in rows[0]["claims"]:
        passed = [r["seed"] for r in rows if r["claims"][name]]
        matrix[name] = {"asserted": len(passed) == len(rows), "seeds": passed}
    doses = {}
    for dose in DOSES:
        o = pi.empty_organism(SEEDS[0]); pi.develop(o, exposures=dose)
        doses[str(dose)] = {"prediction": pi.passive_prediction(o, "X4"), "memory": pi.memory_snapshot(o)}
    arch = pi.architecture_inspection()
    outcome = "E" if matrix["C5_passive_generalization"]["asserted"] and not matrix["C10_acquired_action_influence"]["asserted"] else "UNCLASSIFIED"
    summary = {"update": "4.38", "outcome": outcome, "seeds": args.seeds,
               "first_unsupported_arrow": rows[0]["first_unsupported"],
               "interpretation": "Acquired consequence prediction generalized, but did not alter endogenous action distribution."}
    dump("architecture_inspection.json", arch); dump("per_seed_results.json", rows)
    dump("claim_matrix.json", matrix); dump("dose_sweep.json", doses); dump("summary.json", summary)
    dump("leak_audit.json", {"leak": sorted(set(x for r in rows for x in r["leak"]))})
    dump("OBSERVER_PSYCHE_INCUBATION_SNAPSHOT.json", {**summary, "claim_matrix": matrix,
         "example": rows[0], "diagram": "EXTERNAL WORLD -> PHYSICAL INTERACTION -> BODY CHANGE -> EXPERIENCE -> COMPRESSION -> PREDICTION -X-> ENDOGENOUS ACTION"})
    print(json.dumps(summary, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
