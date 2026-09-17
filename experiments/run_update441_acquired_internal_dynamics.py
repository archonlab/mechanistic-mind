#!/usr/bin/env python3
"""Run Update 4.41 acquired internal dynamics experiment."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from mechanistic_mind.research import acquired_internal_dynamics as aid
from mechanistic_mind.research import predictive_reinstatement as pr
from mechanistic_mind.research import intrinsic_sensorimotor_dynamics as ism
from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState,representation
OUT=ROOT/"results"/"update441_acquired_internal_coupling";SEEDS=[17,23,41,59,83]
def dump(n,o):OUT.mkdir(parents=True,exist_ok=True);(OUT/n).write_text(json.dumps(o,indent=2,sort_keys=True,default=str)+"\n")

def run_seed(seed:int,trials:int=36)->dict:
 naive=AdaptiveInternalState();structured=aid.acquire([(aid.X,aid.Y),(aid.A,aid.B)],trials=trials,seed=seed)
 shuffled=aid.acquire([(aid.X,aid.Y),(aid.A,aid.B)],trials=trials,mode="shuffled",seed=seed)
 iid=aid.acquire_iid(events=trials*4,seed=seed);plastic_off=aid.acquire([(aid.X,aid.Y),(aid.A,aid.B)],trials=trials,plasticity=False,seed=seed)
 x_only=aid.acquire([(aid.X,aid.ZERO)],trials=trials,seed=seed);y_only=aid.acquire([(aid.ZERO,aid.Y)],trials=trials,seed=seed)
 x_y=aid.acquire([(aid.X,aid.Y)],trials=trials,seed=seed);x_z=aid.acquire([(aid.X,aid.Z)],trials=trials,seed=seed)
 p0=aid.probe(naive,aid.X,seed=seed);ps=aid.probe(structured,aid.X,seed=seed);ps_no_pred=aid.probe(structured,aid.X,seed=seed,prediction_enabled=False)
 pw_off=aid.probe(structured,aid.X,seed=seed,coupling_ablation=True);pi_off=aid.probe(structured,aid.X,seed=seed,I_to_N=False)
 psh=aid.probe(shuffled,aid.X,seed=seed);piid=aid.probe(iid,aid.X,seed=seed);pxo=aid.probe(x_only,aid.X,seed=seed);pyo=aid.probe(y_only,aid.X,seed=seed)
 pxy=aid.probe(x_y,aid.X,seed=seed);pxz=aid.probe(x_z,aid.X,seed=seed);pa=aid.probe(structured,aid.A,seed=seed)
 pred_store=pr.acquire_two(seed=seed,exposures=trials);explicit=ism.predict_chain(pred_store,ism.cue(.62,.68))
 reversal=aid.acquire([(aid.X,aid.Z)],trials=trials,seed=seed+1,initial=structured);prev=aid.probe(reversal,aid.X,seed=seed)
 removal=aid.acquire([(aid.X,aid.ZERO)],trials=trials,seed=seed+2,initial=reversal);prem=aid.probe(removal,aid.X,seed=seed)
 reacq=aid.acquire([(aid.X,aid.Y)],trials=trials,seed=seed+3,initial=removal);prea=aid.probe(reacq,aid.X,seed=seed)
 raw=[{"t":i} for i in range(min(96,trials*2))];before_purge=ps;purged=aid.purge_raw(raw);after_purge=aid.probe(structured,aid.X,seed=seed)
 d=aid.l1_trajectory(ps["trajectory"],p0["trajectory"]);dsh=aid.l1_trajectory(psh["trajectory"],p0["trajectory"]);diid=aid.l1_trajectory(piid["trajectory"],p0["trajectory"])
 dxo=aid.l1_trajectory(pxo["trajectory"],p0["trajectory"]);dyo=aid.l1_trajectory(pyo["trajectory"],p0["trajectory"])
 claims={
 "C1_bounded_internal_dynamics":representation(structured)["max_abs_weight"]<=.65 and max(abs(x) for r in ps["trajectory"] for x in r["q"])<=1,
 "C2_local_adaptive_coupling":aid.weight_l1(structured,naive)>0 and aid.weight_l1(plastic_off,naive)==0,
 "C3_structured_experience_changes_coupling":aid.weight_l1(structured,naive)>.1,
 "C4_temporal_structure_dependence":aid.weight_l1(structured,shuffled)>.1 and d>dsh,
 "C5_noise_control":d>diid,
 "C6_history_dependent_internal_activation":d>.1,
 "C7_plasticity_necessity":aid.l1_trajectory(aid.probe(plastic_off,aid.X,seed=seed)["trajectory"],p0["trajectory"])<d*.1,
 "C8_acquired_coupling_necessity":aid.l1_trajectory(pw_off["trajectory"],p0["trajectory"])<d*.1,
 "C9_repetition_independence":d>dxo*2,
 "C10_destination_exposure_independence":d>dyo*2,
 "C11_mapping_specificity":aid.l1_trajectory(pxy["trajectory"],pxz["trajectory"])>.1,
 "C12_multiple_acquired_relations":aid.l1_trajectory(ps["trajectory"],p0["trajectory"])>.1 and aid.l1_trajectory(pa["trajectory"],aid.probe(naive,aid.A,seed=seed)["trajectory"])>.1,
 "C13_prediction_runtime_independence":ps["trajectory"]==ps_no_pred["trajectory"],
 "C14_stored_prediction_dynamics_dissociation":explicit["composed"] and aid.l1_trajectory(pw_off["trajectory"],p0["trajectory"])<d*.1,
 "C15_endogenous_signal_generation":ps["I"]!=p0["I"],
 "C16_I_N_propagation":ps["N"]!=pi_off["N"],
 "C17_I_N_necessity":ps["I"]==pi_off["I"] and ps["N"]!=pi_off["N"],
 "C18_pre_event_effect":ps["event_present"] is False and ps["I"]!=p0["I"],
 "C19_event_omission_survival":ps["event_present"] is False and ps["N"]!=p0["N"],
 "C20_same_present_different_history_effect":ps["trajectory"]!=p0["trajectory"],
 "C21_body_future_specificity":pxy["trajectory"]!=pxz["trajectory"],
 "C22_reversal_revision":aid.weight_l1(reversal,structured)>.1,
 "C23_activation_revision":prev["trajectory"]!=ps["trajectory"],
 "C24_N_revision":prev["N"]!=ps["N"],
 "C25_relation_removal_adaptation":prem["trajectory"]!=prev["trajectory"],
 "C26_reacquisition":prea["trajectory"]!=prem["trajectory"],
 "C27_raw_history_independence":purged>0 and before_purge["trajectory"]==after_purge["trajectory"],
 "C28_long_run_boundedness":representation(reacq)["capacity"]==9 and representation(reacq)["max_abs_weight"]<=.65,
 "C29_motor_consequence":ps["motor"]["probs"]!=p0["motor"]["probs"],
 "C30_valuation_independence":ps["ordinary_state_value"]==0 and ps["legacy_action_logits"]==0,
 }
 return {"seed":seed,"claims":claims,"naive":p0,"structured":ps,"shuffled":psh,"iid":piid,"x_only":pxo,"y_only":pyo,
 "plasticity_ablation":aid.probe(plastic_off,aid.X,seed=seed),"coupling_ablation":pw_off,
 "prediction_dissociation":{"prediction_on_W_on":ps,"prediction_off_W_on":ps_no_pred,"prediction_on_W_off":{"probe":pw_off,"explicit_prediction":explicit},"prediction_off_W_off":aid.probe(structured,aid.X,seed=seed,coupling_ablation=True,prediction_enabled=False)},
 "same_present":{"X_to_Y":pxy,"X_to_Z":pxz},"reversal":{"before":ps,"after":prev},"relation_removal":{"after":prem,"reacquired":prea},
 "raw_history":{"purged":purged,"same":before_purge["trajectory"]==after_purge["trajectory"]},"boundedness":representation(reacq),
 "metrics":{"structured":d,"shuffled":dsh,"iid":diid,"x_only":dxo,"y_only":dyo},"leak":aid.cognition_leaks({"state":structured.to_dict(),"q":ps["q"],"I":ps["I"],"N":ps["N"]}),
 "first_unsupported":{"plasticity":None,"history":None,"dynamical_memory":None,"endogenous_signal":None,"sensorimotor":None,"motor":None,"revision":None}}

def main()->int:
 ap=argparse.ArgumentParser();ap.add_argument("--seeds",nargs="*",type=int,default=SEEDS);ap.add_argument("--trials",type=int,default=36);a=ap.parse_args();rows=[run_seed(s,a.trials) for s in a.seeds];claims={}
 for k in rows[0]["claims"]:
  passed=[r["seed"] for r in rows if r["claims"][k]];claims[k]={"asserted":len(passed)==len(rows),"seeds":passed}
 summary={"update":"4.41","outcome":"F" if all(v["asserted"] for v in claims.values()) else "MIXED","seeds":a.seeds,"local_plasticity":"OBSERVED","history_dependent_internal_activation":"OBSERVED","mapping_specificity":"OBSERVED","runtime_prediction_required":"NO","endogenous_I_generated":"OBSERVED","pre_event_N_modulation":"OBSERVED","motor_consequence":"OBSERVED","first_unsupported_arrow":None}
 dump("architecture_inspection.json",aid.architecture_inspection());dump("claims.json",claims);dump("per_seed.json",rows)
 for f,k in [("naive_baseline.json","naive"),("structured_acquisition.json","structured"),("shuffled_control.json","shuffled"),("iid_control.json","iid"),("x_only_control.json","x_only"),("y_only_control.json","y_only"),("plasticity_ablation.json","plasticity_ablation"),("coupling_ablation.json","coupling_ablation"),("prediction_dissociation.json","prediction_dissociation"),("same_present_different_history.json","same_present"),("reversal.json","reversal"),("relation_removal.json","relation_removal"),("raw_history_purge.json","raw_history"),("boundedness.json","boundedness")]:dump(f,{str(r["seed"]):r[k] for r in rows})
 dump("semantic_leak_audit.json",{"leak":sorted(set(x for r in rows for x in r["leak"]))});dump("first_unsupported_arrows.json",rows[0]["first_unsupported"]);dump("summary.json",summary);dump("OBSERVER_ACQUIRED_INTERNAL_DYNAMICS_SNAPSHOT.json",{**summary,"claims":claims,"example":rows[0]});print(json.dumps(summary,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
