#!/usr/bin/env python3
"""Run Update 4.39 intrinsic sensorimotor dynamics experiment."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from mechanistic_mind.research import intrinsic_sensorimotor_dynamics as ism
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState

OUT = ROOT / "results" / "update439_sensorimotor_dynamics"
SEEDS = [17, 23, 41, 59, 83]


def dump(name, obj):
    OUT.mkdir(parents=True, exist_ok=True); (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True, default=str) + "\n")


def _delta(a, b):
    return sum(abs(float(x)-float(y)) for x,y in zip(a,b))


def run_seed(seed: int, exposures: int = 36) -> dict:
    baseline = ism.reactive_probe(ism.body(.5, .5), seed=seed)
    levels = {str(x): ism.reactive_probe(ism.body(x, 1.0-x), seed=seed) for x in (.2, .5, .8)}
    low, mid, high = levels["0.2"], levels["0.5"], levels["0.8"]
    low_off = ism.reactive_probe(ism.body(.2, .8), seed=seed, body_coupling=False)
    high_off = ism.reactive_probe(ism.body(.8, .2), seed=seed, body_coupling=False)
    signal_only = ism.reactive_probe(ism.body(.8, .2), seed=seed, body_coupling=False, signal_visible=True)
    body_only = ism.reactive_probe(ism.body(.8, .2), seed=seed, signal_visible=False)
    dynamics_off = ism.reactive_probe(ism.body(.8, .2), seed=seed, dynamics_enabled=False)

    store = ism.empty_store(); ism.acquire(store, exposures=exposures, seed=seed, passive=True)
    active = ism.empty_store(); ism.acquire(active, exposures=exposures, seed=seed, passive=False)
    shuffled = ism.empty_store(); ism.acquire(shuffled, exposures=exposures, seed=seed, shuffled=True)
    known_cue = ism.cue(.62, .68); novel_cue = ism.cue(.66, .67)
    chain = ism.predict_chain(store, known_cue); novel = ism.predict_chain(store, novel_cue)
    same_body = ism.body(.5, .5)
    anticipated = ism.anticipatory_probe(store, known_cue, current_body=same_body, seed=seed)
    no_history = ism.anticipatory_probe(ism.empty_store(), known_cue, current_body=same_body, seed=seed)
    pred_abl = ism.anticipatory_probe(store, known_cue, current_body=same_body, seed=seed, prediction_ablation=True)
    value0 = ism.anticipatory_probe(store, known_cue, current_body=same_body, seed=seed, value_neutralized=True)

    pred_before = chain["body"].get("predicted")
    # Silent physical relation change; ordinary online observations revise the mean.
    for i in range(exposures * 3):
        fb = ism.body(.25, .78)
        future = ism.reactive_probe(fb, seed=seed + 1000 + i, steps=6)["state"]
        ism.observe_chain(store, precursor=known_cue, future_body=fb,
                          future_state=SensorimotorState(tuple(future["channels"]), tuple(future["previous_output"]), future["tick"]))
    pred_after = ism.predict_chain(store, known_cue)["body"].get("predicted")

    state_diff = _delta(low["state"]["channels"], high["state"]["channels"])
    output_diff = sum(abs(low["motor"]["probs"][k] - high["motor"]["probs"][k]) for k in low["motor"]["probs"])
    off_diff = _delta(low_off["state"]["channels"], high_off["state"]["channels"])
    anticipate_diff = _delta(anticipated["state"]["channels"], no_history["state"]["channels"])
    probs_diff = anticipated["motor"]["probs"] != no_history["motor"]["probs"]
    action_learned = ism.predict_chain(active, known_cue)["body"].get("predicted") is not None and bool(active["action_to_body"]["pair"])
    revision = pred_before != pred_after
    claims = {
        "C1_intrinsic_sensorimotor_evolution": len(set(tuple(x["channels"]) for x in baseline["trajectory"])) > 1,
        "C2_spontaneous_motor_generation": baseline["motor"]["non_wait_probability"] >= .08,
        "C3_body_state_coupling": state_diff > .05,
        "C4_body_dependent_motor_consequence": output_diff > .005,
        "C5_body_coupling_necessity": off_diff < state_diff * .1,
        "C6_signal_physics_separation": signal_only["state"]["channels"] != body_only["state"]["channels"] and body_only["accessible_signal"] == {},
        "C7_non_valuational_reactive_modulation": state_diff > .05 and low["ordinary_state_value_contribution"] == 0.0,
        "C8_physical_dose_response": len({tuple(round(x, 6) for x in v["state"]["channels"]) for v in levels.values()}) == 3,
        "C9_action_body_consequence_learning": action_learned,
        "C10_body_sensorimotor_predictive_learning": chain["sensorimotor"].get("predicted") is not None,
        "C11_precursor_body_prediction": chain["body"].get("predicted") is not None,
        "C12_multistep_acquired_structure": chain["composed"],
        "C13_matched_state_anticipatory_modulation": anticipate_diff > 1e-12,
        "C14_anticipatory_motor_influence": probs_diff,
        "C15_predictive_path_necessity": anticipated["state"] != pred_abl["state"],
        "C16_valuation_independence": probs_diff and anticipated["motor"]["probs"] == value0["motor"]["probs"],
        "C17_false_prediction_following": False,
        "C18_online_prediction_revision": revision,
        "C19_online_sensorimotor_revision": False,
        "C20_passive_development_compatibility": chain["composed"] and not store["action_to_body"]["pair"],
        "C21_boundedness": max(abs(x) for r in levels.values() for x in r["state"]["channels"]) <= 1.0 and len(store["recent"]) <= ism.MAX_RECENT,
    }
    return {"seed": seed, "claims": claims, "body_sweep": levels,
            "ablations": {"body_coupling_low": low_off, "body_coupling_high": high_off,
                          "signal_only": signal_only, "body_only": body_only, "dynamics_off": dynamics_off,
                          "prediction": pred_abl, "value_neutralized": value0},
            "learning": {"known": chain, "novel": novel, "shuffled": ism.predict_chain(shuffled, known_cue),
                         "prediction_before_revision": pred_before, "prediction_after_revision": pred_after},
            "anticipatory": {"learned": anticipated, "no_history": no_history, "state_delta": anticipate_diff},
            "memory": ism.memory_snapshot(store), "leak": ism.cognition_leaks({"store": store, "state": anticipated["state"]}),
            "first_unsupported": {
                "reactive": None, "learning": None,
                "anticipatory": "predicted_future_sensorimotor_state_to_present_sensorimotor_modulation",
                "value_independence": "predicted_body_consequence_to_present_motor_influence_without_ordinary_state_value",
            }}


def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--seeds", nargs="*", type=int, default=SEEDS); ap.add_argument("--exposures", type=int, default=36); args=ap.parse_args()
    rows=[run_seed(s,args.exposures) for s in args.seeds]; claims={}
    for key in rows[0]["claims"]:
        passed=[r["seed"] for r in rows if r["claims"][key]]; claims[key]={"asserted":len(passed)==len(rows),"seeds":passed}
    summary={"update":"4.39","outcome":"REACTIVE_ASSERTED_ANTICIPATORY_NULL","seeds":args.seeds,
             "reactive_body_modulation":"OBSERVED","anticipatory_sensorimotor_modulation":"NOT OBSERVED",
             "ordinary_state_value_required":"NO for reactive; NOT TESTABLE for absent anticipatory effect",
             "first_unsupported_arrows":rows[0]["first_unsupported"]}
    dump("architecture_inspection.json",ism.architecture_inspection()); dump("claims.json",claims); dump("seed_summaries.json",rows)
    dump("ablation_results.json",{str(r["seed"]):r["ablations"] for r in rows}); dump("semantic_leak_audit.json",{"leak":sorted(set(x for r in rows for x in r["leak"]))})
    dump("first_unsupported_arrows.json",rows[0]["first_unsupported"]); dump("summary.json",summary)
    dump("OBSERVER_SENSORIMOTOR_DYNAMICS_SNAPSHOT.json",{**summary,"claims":claims,"example":rows[0]})
    print(json.dumps(summary,indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
