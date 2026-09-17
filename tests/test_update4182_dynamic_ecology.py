import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'worlds'))

from contextual_object_ecology_v034 import dynamic_sustaining_ecology_config
from mechanistic_mind.agent import Action
from mechanistic_mind.core import DeterministicRandom
from mechanistic_mind.world_engine import ObjectiveWorldEngine


def use(engine,state,n=1):
    rows=[]; rng=DeterministicRandom(17)
    for _ in range(n):
        result=engine.transition_action(state,agent_id='A001',action=Action('USE:OBJ-12'),rng=rng,
            body_context={},advance_dynamics=False)
        state=result.state; rows.append(result.action_receipt)
    return state,rows


def test_partial_transformation_is_persistent_and_overcomeable():
    engine=ObjectiveWorldEngine(dynamic_sustaining_ecology_config(17,resistance_mode='OVERCOMEABLE'))
    state=engine.initial_state(start_position=(14,16)); state,rows=use(engine,state,4)
    assert [r['causal_effect_applied'] for r in rows]==[False,False,False,True]
    assert rows[0]['interaction_physics']['partial_transformation'] is True
    assert rows[1]['interaction_physics']['transformation_before']==rows[0]['interaction_physics']['transformation_after']


def test_impossible_resistance_never_crosses_physical_threshold():
    engine=ObjectiveWorldEngine(dynamic_sustaining_ecology_config(17,resistance_mode='IMPOSSIBLE'))
    state=engine.initial_state(start_position=(14,16)); state,rows=use(engine,state,100)
    assert not any(r['causal_effect_applied'] for r in rows)
    assert rows[-1]['interaction_physics']['transformation_after'] < rows[-1]['interaction_physics']['threshold']


def test_signal_is_world_space_local_scalar_without_target_semantics():
    engine=ObjectiveWorldEngine(dynamic_sustaining_ecology_config(17,condition='DYNAMIC_SIGNAL'))
    state=engine.initial_state(start_position=(10,16)); obs=engine.local_observation(state,agent_id='A001')
    waves=obs['physical_perception']['channels']['PASSIVE_WAVE']
    assert waves and 'amplitude' in waves[0]
    assert not ({'bearing_bin','distance_bin','object_id','source_id','useful'} & set(waves[0]))
    unsignaled=ObjectiveWorldEngine(dynamic_sustaining_ecology_config(17,condition='UNSIGNALED'))
    assert unsignaled.local_observation(unsignaled.initial_state(start_position=(10,16)),agent_id='A001')['physical_perception']['channels']['PASSIVE_WAVE']==[]


def test_legacy_objects_keep_immediate_interaction_semantics():
    from contextual_object_ecology_v034 import default_contextual_object_config
    engine=ObjectiveWorldEngine(default_contextual_object_config(17)); state=engine.initial_state(start_position=(14,16))
    _,rows=use(engine,state,1)
    assert rows[0]['interaction_physics']=={'enabled':False,'consequence_exposed':True}


def test_alternative_physical_push_changes_later_resistance_without_cognitive_label():
    engine=ObjectiveWorldEngine(dynamic_sustaining_ecology_config(17,resistance_mode='OVERCOMEABLE'))
    state=engine.initial_state(start_position=(13,16))
    state['objects']['OBJ-29']['position']=[20,20]
    result=engine.transition_action(state,agent_id='A001',action=Action('PUSH:OBJ-12:15,16'),
        rng=DeterministicRandom(17),body_context={},advance_dynamics=False)
    physical=result.action_receipt['alternative_interaction_physics']
    assert physical['resistance_after'] < physical['resistance_before']
    observation=engine.local_observation(result.state,agent_id='A001')
    assert 'alternative_interaction_physics' not in observation


def test_structured_and_random_resistance_are_world_configurations():
    structured=dynamic_sustaining_ecology_config(17,resistance_mode='STRUCTURED').objects[0]
    random_control=dynamic_sustaining_ecology_config(17,resistance_mode='RANDOM_CONTROL').objects[0]
    assert structured.interaction_physics['mode']=='STRUCTURED'
    assert random_control.interaction_physics['mode']=='RANDOM_CONTROL'
