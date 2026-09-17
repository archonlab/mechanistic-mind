from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState,step,ablate_weights,representation
from mechanistic_mind.research import acquired_internal_dynamics as aid
from experiments.run_update441_acquired_internal_dynamics import run_seed

def test_local_plasticity_is_bounded_and_teacher_free():
 s=AdaptiveInternalState()
 for _ in range(1000): s=step(s,physical_input=(.8,-.6,.4))
 rep=representation(s)
 assert rep["capacity"]==9 and rep["max_abs_weight"]<=.65
 assert all(abs(x)<=1 for x in s.q+s.trace)

def test_structured_history_changes_same_input_response():
 learned=aid.acquire([(aid.X,aid.Y),(aid.A,aid.B)],trials=36,seed=17)
 before=aid.probe(AdaptiveInternalState(),aid.X,seed=17)
 after=aid.probe(learned,aid.X,seed=17)
 assert aid.weight_l1(learned,AdaptiveInternalState())>.1
 assert aid.l1_trajectory(after["trajectory"],before["trajectory"])>.1
 assert after["event_present"] is False

def test_plasticity_and_weight_ablations_are_necessary():
 learned=aid.acquire([(aid.X,aid.Y)],trials=36,seed=23)
 off=aid.acquire([(aid.X,aid.Y)],trials=36,seed=23,plasticity=False)
 naive=aid.probe(AdaptiveInternalState(),aid.X,seed=23)
 assert aid.probe(off,aid.X,seed=23)["trajectory"]==naive["trajectory"]
 assert aid.probe(learned,aid.X,seed=23,coupling_ablation=True)["trajectory"]==naive["trajectory"]

def test_runtime_prediction_is_not_required_and_I_reaches_N():
 learned=aid.acquire([(aid.X,aid.Y)],trials=36,seed=41)
 on=aid.probe(learned,aid.X,seed=41,prediction_enabled=True)
 off=aid.probe(learned,aid.X,seed=41,prediction_enabled=False)
 blocked=aid.probe(learned,aid.X,seed=41,I_to_N=False)
 assert on["trajectory"]==off["trajectory"]
 assert on["I"]==blocked["I"] and on["N"]!=blocked["N"]
 assert on["prediction_runtime_contribution"]==0.0

def test_mapping_specificity_and_controls():
 xy=aid.acquire([(aid.X,aid.Y)],trials=36,seed=59);xz=aid.acquire([(aid.X,aid.Z)],trials=36,seed=59)
 assert aid.probe(xy,aid.X,seed=59)["trajectory"]!=aid.probe(xz,aid.X,seed=59)["trajectory"]
 row=run_seed(59)
 assert all(row["claims"].values())
 assert row["metrics"]["structured"]>row["metrics"]["shuffled"]
 assert row["metrics"]["structured"]>row["metrics"]["iid"]
 assert row["leak"]==[]
