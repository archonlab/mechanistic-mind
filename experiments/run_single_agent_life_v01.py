from __future__ import annotations
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(ROOT/'worlds'))
from mechanistic_mind.adapters.archon import ArchonAdapterSink, InMemoryArchonSink
from mechanistic_mind.agent import Agent
from mechanistic_mind.core import Engine
from mechanistic_mind.mechanisms import MechanismRegistry
from mechanistic_mind.observer import CompositeSink, InMemorySink, PsychologyObserver
from mechanistic_mind.psyche import PsycheState, SingleAgentPsycheV01, build_life_modules
from single_agent_life import SingleAgentLifeWorld

def main():
    ticks=220; canonical=InMemorySink(); archon=InMemoryArchonSink(); observer=PsychologyObserver(CompositeSink((canonical,ArchonAdapterSink(archon))))
    registry=MechanismRegistry(); registry.register(SingleAgentPsycheV01(modules=build_life_modules(),initial_state=PsycheState.initial_life_v01()))
    engine=Engine(world=SingleAgentLifeWorld(),agents={'A001':Agent(agent_id='A001')},seed=17,mechanisms=registry,observer=observer,run_config={'experiment':'SINGLE_AGENT_LIFE_WORLD_V01','ticks':ticks})
    engine.run(ticks); engine.close(); world=engine.state.world.variables; psyche=engine.state.agents['A001'].mechanism_states['PSYCHE-SINGLE-AGENT-V01']['psyche']; actions=[r.actions['A001']['kind'] for r in canonical.records]
    result={'experiment':'SINGLE_AGENT_LIFE_WORLD_V01','ticks':ticks,'world':{'final_position':world['agent_position'],'unique_positions_visited':len(world['visited_positions']),'movement_count':world['movement_count'],'total_progress':world['total_progress'],'object_use_counts':world['object_use_counts']},'actions':{'unique_action_tokens':len(set(actions)),'movement_actions':sum(a.startswith('MOVE:') for a in actions),'interaction_actions':sum(a.startswith('USE:') for a in actions),'wait_actions':actions.count('WAIT')},'psyche':{'internal':psyche['internal'],'known_positions':len(psyche['memory']['spatial']['visited']),'known_objects':psyche['memory']['spatial']['objects'],'learned_action_models':len(psyche['learning']['action_models']),'memory_episodes':len(psyche['memory']['episodes']),'prediction_error_magnitude':psyche['prediction_errors'].get('magnitude'),'self_model':psyche['self_model']},'observer':{'ticks':len(canonical.records),'archon_observations':len(archon.observations),'archon_events':len(archon.events)},'interpretation':'One continuous psyche operates in a partially observed spatial world; hidden object outcomes must be discovered, remembered, and used under changing internal constraints.'}
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
