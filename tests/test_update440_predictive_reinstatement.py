from mechanistic_mind.body.endogenous_signaling import EndogenousSignalState,evolve_signal
from mechanistic_mind.research import predictive_reinstatement as pr
from mechanistic_mind.research import intrinsic_sensorimotor_dynamics as ism
from experiments.run_update440_predictive_reinstatement import run_seed

def test_generic_signal_is_bounded_and_perturbs_N():
 s=EndogenousSignalState()
 for _ in range(500):s=evolve_signal(s,perturbation=(.8,-.6,.3))
 assert all(-1<=x<=1 for x in s.channels)
 on=pr.injected_probe((.4,-.2,.1),seed=17);off=pr.injected_probe((.4,-.2,.1),seed=17,coupling=False);zero=pr.injected_probe((0,0,0),seed=17)
 assert on["N"]!=zero["N"] and off["N"]==zero["N"]

def test_prediction_exists_but_emits_no_signal():
 store=pr.acquire_two(seed=23);p=pr.pre_event_probe(store,ism.cue(.62,.68),seed=23);clean=pr.pre_event_probe(ism.empty_store(),ism.cue(.62,.68),seed=23)
 assert p["prediction"]["composed"]
 assert p["signal"]==clean["signal"] and p["N"]==clean["N"] and p["motor"]==clean["motor"]

def test_selective_prediction_and_signal_ablations_preserve_null():
 store=pr.acquire_two(seed=41);base=pr.pre_event_probe(store,ism.cue(.62,.68),seed=41)
 assert base["signal"]==pr.pre_event_probe(store,ism.cue(.62,.68),seed=41,prediction_ablation=True)["signal"]
 assert base["N"]==pr.pre_event_probe(store,ism.cue(.62,.68),seed=41,signal_path_ablation=True)["N"]

def test_claim_boundary_and_semantic_audit():
 r=run_seed(59)
 assert all(r["claims"][k] for k in list(r["claims"])[:5])
 assert not r["claims"]["C6_acquired_endogenous_signal_generation"]
 assert not r["claims"]["C9_pre_event_sensorimotor_modulation"]
 assert r["claims"]["C19_prediction_revision"] and r["claims"]["C25_boundedness"]
 assert r["leak"]==[]
