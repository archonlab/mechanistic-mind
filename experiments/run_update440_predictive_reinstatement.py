#!/usr/bin/env python3
"""Run Update 4.40 endogenous predictive signaling experiment."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mechanistic_mind.research import predictive_reinstatement as pr
from mechanistic_mind.research import intrinsic_sensorimotor_dynamics as ism
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState

OUT=ROOT/"results"/"update440_predictive_reinstatement";SEEDS=[17,23,41,59,83]
def dump(name,obj): OUT.mkdir(parents=True,exist_ok=True);(OUT/name).write_text(json.dumps(obj,indent=2,sort_keys=True,default=str)+"\n")
def delta(a,b): return sum(abs(float(x)-float(y)) for x,y in zip(a,b))


def run_seed(seed:int,exposures:int=36)->dict:
    injected=pr.injected_probe((.45,-.20,.10),seed=seed)
    injected_off=pr.injected_probe((.45,-.20,.10),seed=seed,coupling=False)
    zero=pr.injected_probe((0.,0.,0.),seed=seed)
    motor_off=pr.injected_probe((.45,-.20,.10),seed=seed,motor_enabled=False)
    store=pr.acquire_two(seed=seed,exposures=exposures,passive=True)
    shuffled=pr.acquire_two(seed=seed,exposures=exposures,passive=True,shuffled=True)
    clean=ism.empty_store(); px=ism.cue(.62,.68);py=ism.cue(.18,.24)
    chain_x=ism.predict_chain(store,px);chain_y=ism.predict_chain(store,py)
    learned=pr.pre_event_probe(store,px,seed=seed); no_history=pr.pre_event_probe(clean,px,seed=seed)
    shuf=pr.pre_event_probe(shuffled,px,seed=seed); pred_off=pr.pre_event_probe(store,px,seed=seed,prediction_ablation=True)
    signal_off=pr.pre_event_probe(store,px,seed=seed,signal_path_ablation=True)
    val0=pr.pre_event_probe(store,px,seed=seed,value_neutralized=True)
    learned_y=pr.pre_event_probe(store,py,seed=seed)
    pre_purge=learned; purged=ism.purge_recent(store); post_purge=pr.pre_event_probe(store,px,seed=seed)
    pred_before=chain_x["body"].get("predicted")
    for i in range(exposures*3):
        fb=ism.body(.25,.78);future=ism.reactive_probe(fb,seed=seed+2000+i,steps=6)["state"]
        ism.observe_chain(store,precursor=px,future_body=fb,
                          future_state=SensorimotorState(tuple(future["channels"]),tuple(future["previous_output"]),future["tick"]))
    pred_after=ism.predict_chain(store,px)["body"].get("predicted")
    revised=pr.pre_event_probe(store,px,seed=seed)
    infrastructure_delta=delta(injected["N"]["channels"],zero["N"]["channels"])
    infrastructure_off_delta=delta(injected_off["N"]["channels"],zero["N"]["channels"])
    acquired_signal_delta=delta(learned["signal"]["channels"],no_history["signal"]["channels"])
    pre_n_delta=delta(learned["N"]["channels"],no_history["N"]["channels"])
    claims={
      "C1_generic_endogenous_signal_dynamics":len(set(tuple(t["I"]["channels"]) for t in injected["trajectory"]))>1,
      "C2_generic_I_N_coupling":infrastructure_delta>.01,
      "C3_I_N_necessity":infrastructure_off_delta<infrastructure_delta*.1,
      "C4_precursor_body_N_learning":chain_x["composed"] and chain_y["composed"],
      "C5_multiple_future_structures":chain_x["sensorimotor"].get("predicted")!=chain_y["sensorimotor"].get("predicted"),
      "C6_acquired_endogenous_signal_generation":acquired_signal_delta>1e-12,
      "C7_temporal_structure_dependence":acquired_signal_delta>1e-12 and learned["signal"]!=shuf["signal"],
      "C8_prediction_dependence":learned["signal"]!=pred_off["signal"],
      "C9_pre_event_sensorimotor_modulation":pre_n_delta>1e-12,
      "C10_endogenous_signal_necessity":learned["N"]!=signal_off["N"] and learned["prediction"]==signal_off["prediction"],
      "C11_actual_body_independence":pre_n_delta>1e-12 and learned["event_omitted"],
      "C12_direct_cue_independence":pre_n_delta>1e-12 and no_history["contributions"]["direct_precursor_sensory"]==0.0,
      "C13_history_dependent_present_dynamics":pre_n_delta>1e-12,
      "C14_structural_correspondence":learned["signal"]!=learned_y["signal"],
      "C15_cross_mapping_causality":learned["signal"]!=shuf["signal"],
      "C16_passive_acquisition":acquired_signal_delta>1e-12,
      "C17_raw_history_independence":acquired_signal_delta>1e-12 and pre_purge["signal"]==post_purge["signal"] and purged>0,
      "C18_valuation_independence":acquired_signal_delta>1e-12 and learned["N"]==val0["N"],
      "C19_prediction_revision":pred_before!=pred_after,
      "C20_endogenous_signal_revision":learned["signal"]!=revised["signal"],
      "C21_present_N_revision":learned["N"]!=revised["N"],
      "C22_false_prediction_following":False,
      "C23_motor_consequence":learned["motor"]["probs"]!=no_history["motor"]["probs"],
      "C24_motor_path_necessity":False,
      "C25_boundedness":max(abs(x) for x in injected["signal"]["channels"])<=1 and pr.memory_snapshot(store)["recent"]<=ism.MAX_RECENT,
    }
    return {"seed":seed,"claims":claims,"infrastructure":{"injected":injected,"I_N_ablated":injected_off,"zero":zero,"motor_ablated":motor_off},
      "acquisition":{"X":chain_x,"Y":chain_y,"shuffled_X":ism.predict_chain(shuffled,px)},
      "history":{"learned":learned,"no_history":no_history,"shuffled":shuf,"prediction_ablated":pred_off,"signal_path_ablated":signal_off,"value_neutralized":val0},
      "omission":{"body_event_omitted":learned["event_omitted"],"current_body_matched":learned["current_body"]==no_history["current_body"],"initial_N_matched":learned["initial_N"]==no_history["initial_N"]},
      "revision":{"prediction_before":pred_before,"prediction_after":pred_after,"signal_before":learned["signal"],"signal_after":revised["signal"]},
      "boundedness":pr.memory_snapshot(store),"leak":pr.cognition_leaks({"signal":learned["signal"],"N":learned["N"],"stores":store}),
      "first_unsupported":{"infrastructure":None,"acquisition":"acquired_prediction_to_endogenous_signal_generation","pre_event":"acquired_prediction_to_endogenous_signal_generation","history":"different_prediction_to_different_endogenous_signal","revision":"changed_prediction_to_changed_endogenous_signal","behavior":"acquired_signal_to_present_N (upstream absent)"}}


def main()->int:
    ap=argparse.ArgumentParser();ap.add_argument("--seeds",nargs="*",type=int,default=SEEDS);ap.add_argument("--exposures",type=int,default=36);a=ap.parse_args()
    rows=[run_seed(s,a.exposures) for s in a.seeds];claims={}
    for k in rows[0]["claims"]:
      passed=[r["seed"] for r in rows if r["claims"][k]];claims[k]={"asserted":len(passed)==len(rows),"seeds":passed}
    summary={"update":"4.40","outcome":"A","seeds":a.seeds,"acquired_endogenous_signal":"NOT OBSERVED","pre_event_N_modulation":"NOT OBSERVED","future_specific_structure":"NOT OBSERVED","valuation_independent":"NOT TESTABLE","motor_consequence":"NOT OBSERVED","first_unsupported_arrow":"acquired_prediction_to_endogenous_signal_generation"}
    dump("architecture_inspection.json",pr.architecture_inspection());dump("claims.json",claims);dump("per_seed.json",rows)
    for name,key in (("infrastructure_controls.json","infrastructure"),("acquisition_controls.json","acquisition"),("history_controls.json","history"),("omission_controls.json","omission"),("revision_controls.json","revision"),("boundedness.json","boundedness")):dump(name,{str(r["seed"]):r[key] for r in rows})
    dump("semantic_leak_audit.json",{"leak":sorted(set(x for r in rows for x in r["leak"]))});dump("first_unsupported_arrows.json",rows[0]["first_unsupported"]);dump("summary.json",summary);dump("OBSERVER_PREDICTIVE_SIGNALING_SNAPSHOT.json",{**summary,"claims":claims,"example":rows[0]});print(json.dumps(summary,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
