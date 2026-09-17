"""Update 4.40 acquisition and pre-event signaling probes."""
from __future__ import annotations
import json, re
from typing import Any

from mechanistic_mind.body.endogenous_signaling import EndogenousSignalState, evolve_signal, memory_cost_bytes
from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState, evolve, motor_distribution
from mechanistic_mind.research import intrinsic_sensorimotor_dynamics as ism

FORBIDDEN=("FEAR","ANXIETY","HUNGER","FOOD","THIRST","PAIN","PLEASURE","WANT","NEED","DESIRE","DRIVE","MOTIVATION","GOAL","INTENTION","REWARD","PUNISHMENT","GOOD","BAD","VALUE","UTILITY","SURVIVAL","SELF_PRESERVATION","CURIOSITY","EXPLORATION","INTEREST","NOVELTY","URGENCY","RISK","CONFIDENCE","ATTENTION","SALIENCE","IMPORTANT","PREPARE","READINESS","EXPECTED_BAD","EXPECTED_GOOD","SEEK","AVOID")


def architecture_inspection() -> dict[str, Any]:
    return {
        "A_N_inputs": ["actual internal_a/load_c", "bounded sensory vector", "previous N", "stochastic perturbation"],
        "B_exogenous": ["sensory vector", "researcher random sample"],
        "C_body": ["internal_a", "load_c"],
        "D_endogenous_non_body_before_440": False,
        "E_learned_emission": False,
        "F_learning_role": "queried/read only; activation is not a physical output",
        "G_retrieval_activation_state": False,
        "H_prediction_properties": ["predicted vector", "support", "source", "provenance-compatible structure"],
        "I_prediction_properties_causal_outside_retrieval": False,
        "J_internal_to_later_N_learning": True,
        "K_reverse_temporal_pre_event_learning": False,
        "L_generic_reinstatement_mechanism": False,
        "M_conclusion": "No mechanism maps acquired predictive activation into current physical signal. None added.",
        "new_category_A_infrastructure": "bounded generic I and source-agnostic I->N perturbation port",
    }


def injected_probe(pattern: tuple[float,float,float], *, seed: int, coupling: bool=True, motor_enabled: bool=True) -> dict[str,Any]:
    signal=EndogenousSignalState(); n=SensorimotorState(); trajectory=[]
    for t in range(8):
        signal=evolve_signal(signal,perturbation=pattern if t==0 else ())
        n=evolve(n,body=ism.body(),sensory=(.5,.5),random_value=((seed*31+t*17)%101)/100,
                 endogenous=signal.channels,endogenous_coupling=coupling)
        trajectory.append({"I":signal.to_dict(),"N":n.to_dict()})
    motor=motor_distribution(n) if motor_enabled else {"probs":{},"motor_magnitude":0.0,"non_wait_probability":0.0}
    return {"signal":signal.to_dict(),"N":n.to_dict(),"motor":motor,"trajectory":trajectory,
            "provenance":{"researcher_injection":True,"acquired_prediction":0.0,"actual_body":ism.body(),
                          "direct_sensory":(0.0,0.0),"ordinary_state_value":0.0,"legacy_action_logits":0.0},
            "ablations":{"I_to_N":not coupling,"N_to_motor":not motor_enabled}}


def acquire_two(*, seed:int, exposures:int=36, passive:bool=True, shuffled:bool=False) -> dict[str,Any]:
    store=ism.empty_store()
    # Existing ordinary learning; two physical precursor/future relations.
    pairs=[(ism.cue(.62,.68),ism.body(.80,.30)),(ism.cue(.18,.24),ism.body(.28,.76))]
    for i in range(exposures):
        precursor,future_body=pairs[i%2]
        if shuffled: future_body=pairs[(i+1)%2][1]
        future=ism.reactive_probe(future_body,seed=seed+i,steps=6)["state"]
        from mechanistic_mind.body.sensorimotor_dynamics import SensorimotorState
        ns=SensorimotorState(tuple(future["channels"]),tuple(future["previous_output"]),future["tick"])
        ism.observe_chain(store,precursor=precursor,future_body=future_body,future_state=ns,
                          action_features=None if passive else {"motor_0":.7,"motor_1":.3})
    return store


def pre_event_probe(store:dict[str,Any], precursor:dict[str,float], *, seed:int,
                    prediction_ablation:bool=False, signal_path_ablation:bool=False,
                    value_neutralized:bool=False) -> dict[str,Any]:
    prediction={"body":{"status":"ABLATION","predicted":None},"sensorimotor":{"status":"ABLATION","predicted":None},"composed":False} if prediction_ablation else ism.predict_chain(store,precursor)
    # Central experimental NULL: retrieval emits no physical perturbation.
    signal=EndogenousSignalState(); n=SensorimotorState()
    for t in range(8):
        signal=evolve_signal(signal)
        n=evolve(n,body=ism.body(),sensory=(.5,.5),random_value=((seed*31+t*17)%101)/100,
                 endogenous=signal.channels,endogenous_coupling=not signal_path_ablation)
    return {"prediction":prediction,"signal":signal.to_dict(),"N":n.to_dict(),"motor":motor_distribution(n),
            "event_omitted":True,"current_body":ism.body(),"initial_N":SensorimotorState().to_dict(),
            "contributions":{"actual_body":0.0,"direct_precursor_sensory":0.0,"stochastic_N":"matched",
                             "acquired_prediction":0.0,"endogenous_signal":0.0,"ordinary_state_value":0.0,
                             "legacy_action_logits":0.0,"hidden_future_event":0.0},
            "ablations":{"prediction":prediction_ablation,"I_to_N":signal_path_ablation,"value":value_neutralized}}


def memory_snapshot(store:dict[str,Any]) -> dict[str,int]:
    base=ism.memory_snapshot(store); base.update({"signal_dimension":3,"signal_memory_bytes":memory_cost_bytes(EndogenousSignalState()),"active_signal_count":0}); return base


def cognition_leaks(payload:Any)->list[str]:
    text=json.dumps(payload,sort_keys=True,default=str).upper()
    return [x for x in FORBIDDEN if re.search(rf"(?<![A-Z]){re.escape(x)}(?![A-Z])",text)]
