"""Bounded locally adaptive internal dynamics for Update 4.41."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

DIMENSION=3
STATE_DECAY=.58
TRACE_DECAY=.62
WEIGHT_DECAY=.999
LEARNING_RATE=.075
WEIGHT_BOUND=.65
STATE_BOUND=1.0

def _clip(x,b): return max(-b,min(b,float(x)))

@dataclass
class AdaptiveInternalState:
    q: tuple[float,float,float]=(0.,0.,0.)
    trace: tuple[float,float,float]=(0.,0.,0.)
    weights: tuple[tuple[float,float,float],...]=((0.,0.,0.),(0.,0.,0.),(0.,0.,0.))
    tick:int=0
    def to_dict(self)->dict[str,Any]: return {"q":self.q,"trace":self.trace,"weights":self.weights,"tick":self.tick}

def step(state:AdaptiveInternalState, *, physical_input:tuple[float,...]=(), plasticity:bool=True)->AdaptiveInternalState:
    """Update from local prior trace and current numeric input only."""
    u=tuple(float(physical_input[i]) if i<len(physical_input) else 0. for i in range(DIMENSION))
    w=[list(row) for row in state.weights]
    for i in range(DIMENSION):
      for j in range(DIMENSION):
        changed=w[i][j]*WEIGHT_DECAY
        if plasticity: changed += LEARNING_RATE*state.trace[i]*u[j]
        w[i][j]=_clip(changed,WEIGHT_BOUND)
    propagated=[sum(state.q[i]*w[i][j] for i in range(DIMENSION)) for j in range(DIMENSION)]
    q=tuple(_clip(STATE_DECAY*state.q[j]+u[j]+propagated[j],STATE_BOUND) for j in range(DIMENSION))
    trace=tuple(_clip(TRACE_DECAY*state.trace[i]+u[i],STATE_BOUND) for i in range(DIMENSION))
    return AdaptiveInternalState(q,trace,tuple(tuple(row) for row in w),state.tick+1)

def ablate_weights(state:AdaptiveInternalState)->AdaptiveInternalState:
    return AdaptiveInternalState(state.q,state.trace,AdaptiveInternalState().weights,state.tick)

def representation(state:AdaptiveInternalState)->dict[str,Any]:
    flat=[x for row in state.weights for x in row]
    return {"dimension":DIMENSION,"active_couplings":sum(abs(x)>1e-9 for x in flat),"capacity":DIMENSION*DIMENSION,
            "nonzero_fraction":sum(abs(x)>1e-9 for x in flat)/(DIMENSION*DIMENSION),"max_abs_weight":max(map(abs,flat)),
            "trace_capacity":DIMENSION,"bytes":8*(DIMENSION*DIMENSION+DIMENSION*2+1)}
