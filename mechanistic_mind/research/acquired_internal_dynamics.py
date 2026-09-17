"""Update 4.41 experiment helpers; no explicit prediction drives runtime."""
from __future__ import annotations
import json,re,random,math
from typing import Any
from mechanistic_mind.body.adaptive_internal_coupling import AdaptiveInternalState,step,ablate_weights,representation
from mechanistic_mind.body.endogenous_signaling import EndogenousSignalState,evolve_signal
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState,evolve,motor_distribution
from mechanistic_mind.research import intrinsic_sensorimotor_dynamics as ism
from mechanistic_mind.research import predictive_reinstatement as pr

X=(.70,0.,0.);Y=(0.,.70,0.);Z=(0.,0.,.70);A=(-.65,0.,0.);B=(0.,-.65,.15);ZERO=(0.,0.,0.)
FORBIDDEN=("MEMORY_ASSOCIATION","CONDITIONED","CONDITIONING","EXPECTATION","ANTICIPATION","PREPARATION","HUNGER","FOOD","PAIN","FEAR","ANXIETY","PLEASURE","WANT","NEED","DESIRE","DRIVE","MOTIVATION","GOAL","INTENTION","REWARD","PUNISHMENT","GOOD","BAD","VALUE","UTILITY","SURVIVAL","SELF_PRESERVATION","CURIOSITY","EXPLORATION","NOVELTY","ATTENTION","SALIENCE","IMPORTANCE","HABIT","REFLEX","EMOTION","READINESS","SEEK","AVOID")

def architecture_inspection()->dict[str,Any]:
 return {"A_self_modifying_existing":False,"B_plastic_outside_prediction":False,"C_cooccurrence_propagation":False,
 "D_learned_weights_in_active_dynamics":False,"E_retrieval":"returns stored information; does not alter state",
 "F_I_recurrent":True,"G_I_future_from_I":"decay/persistence only","H_generic_coupled_channels":False,"I_couplings_change":False,
 "J_local_information":["previous bounded eligibility trace","current numeric physical input"],"K_global_teacher":False,
 "L_local_temporal_plasticity":"new minimal substrate","M_forgetting":"weight and trace decay","N_bounds":"q/trace ±1; W ±0.65; fixed 3x3",
 "O_conclusion":"No generic plastic internal coupling existed; minimal bounded local substrate added.",
 "runtime_prediction_to_activity":False}

def _rest(state,n=8,plasticity=True):
 for _ in range(n): state=step(state,physical_input=ZERO,plasticity=plasticity)
 return state

def acquire(pairs:list[tuple[tuple[float,...],tuple[float,...]]],*,trials:int=36,plasticity:bool=True,mode:str="structured",seed:int=0,initial:AdaptiveInternalState|None=None)->AdaptiveInternalState:
 rng=random.Random(seed);state=initial or AdaptiveInternalState(); events=[]
 for _ in range(trials): events.extend(pairs)
 if mode=="shuffled":
  dest=[d for _,d in events];rng.shuffle(dest);events=[(s,dest[i]) for i,(s,_) in enumerate(events)]
 for source,dest in events:
  state=_rest(state,6,plasticity);state=step(state,physical_input=source,plasticity=plasticity)
  state=step(state,physical_input=ZERO,plasticity=plasticity);state=step(state,physical_input=ZERO,plasticity=plasticity)
  state=step(state,physical_input=dest,plasticity=plasticity)
 return _rest(state,10,plasticity)

def acquire_iid(*,events:int=144,seed:int=0)->AdaptiveInternalState:
 rng=random.Random(seed);state=AdaptiveInternalState(); pool=[X,Y,Z,A,B]
 for _ in range(events): state=step(state,physical_input=pool[rng.randrange(len(pool))]);state=_rest(state,3)
 return _rest(state,10)

def probe(state:AdaptiveInternalState,pattern:tuple[float,...],*,seed:int,coupling_ablation:bool=False,prediction_enabled:bool=True,I_to_N:bool=True)->dict[str,Any]:
 s=ablate_weights(state) if coupling_ablation else state
 # Matched present: q/trace reset while learned W remains.
 s=AdaptiveInternalState(weights=s.weights);I=EndogenousSignalState();N=SensorimotorState();traj=[]
 for t in range(8):
  s=step(s,physical_input=pattern if t==0 else ZERO,plasticity=False)
  I=evolve_signal(I,perturbation=s.q)
  N=evolve(N,body=ism.body(),sensory=(.5,.5),random_value=((seed*29+t*13)%101)/100,endogenous=I.channels,endogenous_coupling=I_to_N)
  traj.append({"q":s.q,"I":I.channels,"N":N.channels})
 return {"q":s.q,"I":I.to_dict(),"N":N.to_dict(),"motor":motor_distribution(N),"trajectory":traj,
         "weights":s.weights,"prediction_runtime_enabled":prediction_enabled,"prediction_runtime_contribution":0.0,
         "ordinary_state_value":0.0,"legacy_action_logits":0.0,"event_present":False,"representation":representation(s),
         "ablations":{"W":coupling_ablation,"prediction":not prediction_enabled,"I_to_N":not I_to_N}}

def l1_trajectory(a,b,key="q")->float: return sum(sum(abs(x-y) for x,y in zip(ra[key],rb[key])) for ra,rb in zip(a,b))
def weight_l1(a,b)->float:return sum(abs(x-y) for ra,rb in zip(a.weights,b.weights) for x,y in zip(ra,rb))
def purge_raw(raw:list)->int:n=len(raw);raw.clear();return n
def cognition_leaks(payload:Any)->list[str]:
 text=json.dumps(payload,sort_keys=True,default=str).upper();return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])",text)]
